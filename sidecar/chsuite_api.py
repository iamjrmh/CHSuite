#!/usr/bin/env python3
"""CHSuite headless API sidecar.

This process hosts every piece of Clone Hero tooling logic behind a tiny
localhost JSON/HTTP API. The Tauri shell launches it, reads the ephemeral port
it announces on stdout (``CHSUITE_PORT=<n>``), and the web frontend talks to it
directly.

Design rules
------------
* The server core depends on the Python standard library ONLY, so it always
  boots even on a fresh machine. Heavy third-party libraries (UnityPy, Pillow,
  requests) are imported lazily inside the handlers that need them; a missing
  dependency yields a clean ``503`` instead of crashing the whole sidecar.
* Every route handler takes the parsed JSON body (a dict) and returns a plain
  Python object that is JSON-serialised back to the caller. Raising
  ``ApiError`` produces a structured error response.
"""

from __future__ import annotations

import json
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core import cleaner, config, manager, menuchanger, namegen, notegen, songmanager, updater
from core.errors import ApiError

# ---------------------------------------------------------------------------
# Route table: (METHOD, path) -> handler(body: dict) -> object
# ---------------------------------------------------------------------------

ROUTES = {
    ("GET", "/health"): lambda body: {"ok": True, "service": "chsuite", "version": config.APP_VERSION},

    # Config + Clone Hero path discovery
    ("GET", "/config"): lambda body: config.get_config(),
    ("POST", "/config"): lambda body: config.update_config(body),
    ("POST", "/config/detect"): lambda body: config.detect_installs(body),

    # Self-update check (same GitHub repo/releases as the original CHSuite)
    ("GET", "/updater/check"): lambda body: updater.check(body),

    # CHCleaner
    ("POST", "/cleaner/parse"): lambda body: cleaner.parse_bad_songs(body),
    ("POST", "/cleaner/delete"): lambda body: cleaner.delete_songs(body),

    # CHPatcher
    ("GET", "/patcher/installs"): lambda body: manager.list_installs(),
    ("POST", "/patcher/patch"): lambda body: manager.patch_installs(body, manual=True),
    ("POST", "/patcher/unpatch"): lambda body: manager.patch_installs(body, manual=False),

    # CHNameGen (export only - preview is rendered in the frontend)
    ("POST", "/namegen/export"): lambda body: namegen.export_profile_name(body),
    ("POST", "/namegen/profiles"): lambda body: namegen.list_profiles(body),

    # CHNoteGen (export INI + note textures)
    ("POST", "/notegen/export"): lambda body: notegen.export(body),
    ("GET", "/notegen/profiles"): lambda body: notegen.list_profiles(body),

    # CHSongManager (ChorusEncore)
    ("POST", "/songs/search"): lambda body: songmanager.search(body),
    ("POST", "/songs/download"): lambda body: songmanager.start_download(body),
    ("POST", "/songs/download/status"): lambda body: songmanager.download_status(body),
    ("POST", "/songs/library/scan"): lambda body: songmanager.start_library_scan(body),
    ("POST", "/songs/library/scan/status"): lambda body: songmanager.library_scan_status(body),
    ("POST", "/songs/library/delete"): lambda body: songmanager.delete_downloaded(body),

    # CHManager (installs + GitHub releases)
    ("GET", "/manager/installs"): lambda body: manager.list_installs(),
    ("GET", "/manager/releases"): lambda body: manager.list_releases(),
    ("POST", "/manager/launch"): lambda body: manager.launch(body),
    ("POST", "/manager/open-folder"): lambda body: manager.open_folder(body),
    ("POST", "/manager/set-default"): lambda body: manager.set_default(body),
    ("POST", "/manager/rename"): lambda body: manager.rename_install(body),
    ("POST", "/manager/install"): lambda body: manager.start_install(body),
    ("POST", "/manager/install/status"): lambda body: manager.install_status(body),
    ("POST", "/manager/add"): lambda body: manager.add_install(body),
    ("POST", "/manager/delete"): lambda body: manager.delete_install(body),

    # CHMenuChanger (UnityPy texture swapping)
    ("POST", "/menu/scan"): lambda body: menuchanger.scan(body),
    ("POST", "/menu/preview"): lambda body: menuchanger.preview(body),
    ("POST", "/menu/apply"): lambda body: menuchanger.apply(body),
    ("POST", "/menu/restore"): lambda body: menuchanger.restore(body),
    ("GET", "/menu/backgrounds"): lambda body: menuchanger.backgrounds(),
}


class Handler(BaseHTTPRequestHandler):
    # Silence the default per-request logging to stderr.
    def log_message(self, *args):  # noqa: D401, ANN001
        pass

    def _send(self, status: int, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        # The frontend runs from tauri://localhost / http://localhost:1420.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):  # noqa: N802 - CORS preflight
        self._send(204, {})

    def _dispatch(self, method: str):
        path = urlparse(self.path).path.rstrip("/") or "/"
        handler = ROUTES.get((method, path))
        if handler is None:
            self._send(404, {"error": "not_found", "message": f"{method} {path}"})
            return

        body = {}
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._send(400, {"error": "bad_json", "message": "invalid request body"})
                return

        try:
            result = handler(body if isinstance(body, dict) else {"_": body})
            self._send(200, {"ok": True, "data": result})
        except ApiError as e:
            self._send(e.status, {"error": e.code, "message": str(e), "data": e.data})
        except Exception as e:  # noqa: BLE001 - surface unexpected failures cleanly
            traceback.print_exc()
            self._send(500, {"error": "internal", "message": str(e)})

    def _serve_album_art(self, path_str: str):
        p = Path(path_str) if path_str else None
        if not p or not p.is_file():
            self._send(404, {"error": "not_found", "message": "Album art not found."})
            return

        if p.suffix.lower() == ".sng":
            result = songmanager.extract_sng_art(p)
            if not result:
                self._send(404, {"error": "not_found", "message": "Album art not found."})
                return
            data, mime = result
        else:
            mime = songmanager.ART_MIME.get(p.suffix.lower())
            if not mime:
                self._send(404, {"error": "not_found", "message": "Album art not found."})
                return
            try:
                data = p.read_bytes()
            except OSError as e:
                self._send(500, {"error": "internal", "message": str(e)})
                return

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") == "/songs/library/art":
            self._serve_album_art(parse_qs(parsed.query).get("path", [""])[0])
            return
        self._dispatch("GET")

    def do_POST(self):  # noqa: N802
        self._dispatch("POST")


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    # FIRST line on stdout - the Tauri shell parses this to learn the port.
    print(f"CHSUITE_PORT={port}", flush=True)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Block forever; the parent process kills us on app exit.
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())

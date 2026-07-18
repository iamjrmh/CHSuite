"""CHSongManager - ChorusEncore search + .sng download.

Search proxies the public ChorusEncore API; downloads stream the single-file
``.sng`` chart to the user's songs directory. Requires the ``requests`` package
(lazily imported so the sidecar still boots without it).

Library scanning and downloading both run as background jobs polled by the
frontend, so the UI can show live progress instead of blocking on one big
request/response.
"""

from __future__ import annotations

import configparser
import copy
import json
import re
import shutil
import struct
import threading
import uuid
from pathlib import Path

from . import config
from .errors import ApiError, MissingDependency

API_URL = "https://api.enchor.us/search"
FILES_URL = "https://files.enchor.us"
PER_PAGE = 25
_UA = {"User-Agent": "CHSuite/8.0 CHSongManager"}
_CHART_FILES = ("notes.chart", "notes.mid")
_MAX_SCAN_DEPTH = 5
_ART_STEM_PRIORITY = ("album", "cover", "folder", "albumart", "album_art")
_ART_NAME_RE = re.compile(r"^(?:album|cover|folder)\.(?:png|jpe?g)$", re.IGNORECASE)
_SNG_MAGIC = b"SNGPKG"
ART_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
}

_scan_jobs: dict[str, dict] = {}
_scan_lock = threading.Lock()
_download_jobs: dict[str, dict] = {}
_download_lock = threading.Lock()


def _requests():
    try:
        import requests  # noqa: PLC0415
        return requests
    except ImportError as e:
        raise MissingDependency("requests", "song search & download") from e


def _safe_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", (s or "").strip())
    return s[:140] or "song"


def _expected_filename(artist: str, name: str) -> str:
    return _safe_name(f"{artist} - {name}" if artist else name) + ".sng"


def _songs_dir(body: dict) -> Path:
    songs_dir = body.get("dir") or config.get_config().get("sm_songs_dir", "")
    if not songs_dir:
        songs_dir = str(config.documents_clone_hero() / "songs")
    return Path(songs_dir)


# --- library scan cache -----------------------------------------------------
# Keyed by songs-folder path so switching folders doesn't mix libraries.
# Rescans reuse a cached entry's metadata as-is instead of reparsing song.ini
# / re-summing folder size / re-checking for art - only paths missing from the
# cache (newly added songs) get that work done, and paths no longer found on
# disk (deleted songs) simply drop out when the tree is walked again.

def _cache_file() -> Path:
    d = Path.home() / "Documents" / "CHSuite"
    d.mkdir(parents=True, exist_ok=True)
    return d / "song_cache.json"


def _load_cache() -> dict:
    f = _cache_file()
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    try:
        _cache_file().write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        pass


def search(body: dict) -> dict:
    requests = _requests()
    sort_prop = body.get("sort")
    payload = {
        "search": body.get("query", "") or "",
        "page": int(body.get("page", 1)),
        "per_page": PER_PAGE,
        "instrument": body.get("instrument"),
        "difficulty": body.get("difficulty"),
        "sort": {"type": sort_prop, "direction": body.get("sortDir", "asc")} if sort_prop else None,
        "source": "bridge",
    }
    try:
        r = requests.post(API_URL, json=payload, timeout=20, headers=_UA)
        r.raise_for_status()
        resp = r.json()
    except Exception as e:  # noqa: BLE001
        raise ApiError(f"Search failed: {e}", code="search", status=502)

    songs_dir = _songs_dir(body)
    data = resp.get("data", [])
    found = resp.get("found", 0)
    songs = []
    for s in data:
        artist = s.get("artist", "")
        name = s.get("name", "")
        songs.append({
            "md5": s.get("md5", ""),
            "name": name,
            "artist": artist,
            "album": s.get("album", ""),
            "genre": s.get("genre", ""),
            "year": s.get("year", ""),
            "charter": s.get("charter", ""),
            "length": s.get("song_length", 0) or s.get("length", 0),
            "albumArtMd5": s.get("albumArtMd5", ""),
            "hasVideoBackground": bool(s.get("hasVideoBackground")),
            "diffGuitar": s.get("diff_guitar", -1),
            "diffDrums": s.get("diff_drums", -1),
            "alreadyDownloaded": (songs_dir / _expected_filename(artist, name)).is_file(),
        })
    page = int(body.get("page", 1))
    return {"found": found, "page": page, "hasMore": page * PER_PAGE < found, "songs": songs}


def start_download(body: dict) -> dict:
    requests = _requests()
    songs = body.get("songs")
    if songs is None and body.get("md5"):
        songs = [{"md5": body["md5"], "name": body.get("name", ""), "artist": body.get("artist", "")}]
    if not songs:
        raise ApiError("No songs supplied for download.", code="empty")

    out_dir = _songs_dir(body)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ApiError(f"Could not create songs folder: {e}", code="mkdir", status=500)
    config.update_config({"sm_songs_dir": str(out_dir)})

    job_id = uuid.uuid4().hex
    queue = [
        {"md5": s.get("md5", ""), "name": s.get("name", "") or s.get("md5", ""), "artist": s.get("artist", ""), "status": "pending"}
        for s in songs
    ]
    with _download_lock:
        _download_jobs[job_id] = {"status": "running", "dir": str(out_dir), "total": len(queue), "done": 0, "queue": queue}

    def run() -> None:
        for i, song in enumerate(songs):
            with _download_lock:
                _download_jobs[job_id]["queue"][i]["status"] = "downloading"
            md5 = song.get("md5", "")
            name = song.get("name", "") or md5
            artist = song.get("artist", "")
            if not md5:
                with _download_lock:
                    _download_jobs[job_id]["queue"][i]["status"] = "failed"
                    _download_jobs[job_id]["queue"][i]["error"] = "no md5"
                    _download_jobs[job_id]["done"] += 1
                continue
            fname = _expected_filename(artist, name)
            dest = out_dir / fname
            if dest.is_file():
                with _download_lock:
                    _download_jobs[job_id]["queue"][i]["status"] = "skipped"
                    _download_jobs[job_id]["queue"][i]["path"] = str(dest)
                    _download_jobs[job_id]["done"] += 1
                continue
            try:
                with requests.get(f"{FILES_URL}/{md5}.sng", stream=True, timeout=60, headers=_UA) as r:
                    r.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                with _download_lock:
                    _download_jobs[job_id]["queue"][i]["status"] = "done"
                    _download_jobs[job_id]["queue"][i]["path"] = str(dest)
            except Exception as e:  # noqa: BLE001
                with _download_lock:
                    _download_jobs[job_id]["queue"][i]["status"] = "failed"
                    _download_jobs[job_id]["queue"][i]["error"] = str(e)
            with _download_lock:
                _download_jobs[job_id]["done"] += 1
        with _download_lock:
            _download_jobs[job_id]["status"] = "done"

    threading.Thread(target=run, daemon=True).start()
    return {"jobId": job_id}


def download_status(body: dict) -> dict:
    job_id = body.get("jobId", "")
    with _download_lock:
        job = _download_jobs.get(job_id)
        if job is None:
            raise ApiError("Unknown download job.", code="not_found", status=404)
        return copy.deepcopy(job)


def _parse_song_ini(path: Path) -> dict:
    if not path.is_file():
        return {}
    # interpolation=None: song.ini values routinely contain literal "%"
    # (e.g. "100% Orange Juice"), which ConfigParser's default interpolation
    # would otherwise choke on with an InterpolationSyntaxError.
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cp.read(path, encoding="utf-8-sig")
    except (OSError, configparser.Error):
        return {}
    section = next((s for s in cp.sections() if s.lower() == "song"), None)
    if section is None:
        return {}
    return {
        "name": cp.get(section, "name", fallback="").strip(),
        "artist": cp.get(section, "artist", fallback="").strip(),
        "charter": (cp.get(section, "charter", fallback="") or cp.get(section, "frets", fallback="")).strip(),
    }


# --- .sng embedded album art -----------------------------------------------
# Container format: https://github.com/mdsitton/SngFileFormat. Header + a
# length-prefixed metadata section (skipped, we don't need it) + a file index
# (name/size/absolute-offset triples) + the raw file bytes, each individually
# XOR-masked with header.xorMask (key cycles with period 256: xorMask[i % 16]
# ^ (i & 0xFF), i = the byte's own index within that file's contents).

def _sng_index(path: Path) -> tuple[bytes, list[tuple[str, int, int]]] | None:
    try:
        with open(path, "rb") as f:
            if f.read(6) != _SNG_MAGIC:
                return None
            f.read(4)  # version, unused
            xor_mask = f.read(16)
            if len(xor_mask) != 16:
                return None
            metadata_len = struct.unpack("<Q", f.read(8))[0]
            f.seek(metadata_len, 1)  # skip metadata entirely, we don't need it here
            struct.unpack("<Q", f.read(8))[0]  # fileIndexLen, unused (we read entries directly)
            file_count = struct.unpack("<Q", f.read(8))[0]
            entries: list[tuple[str, int, int]] = []
            for _ in range(file_count):
                name_len = f.read(1)
                if not name_len:
                    return None
                name = f.read(name_len[0]).decode("utf-8", "replace")
                size = struct.unpack("<Q", f.read(8))[0]
                offset = struct.unpack("<Q", f.read(8))[0]
                entries.append((name, size, offset))
            return xor_mask, entries
    except (OSError, struct.error):
        return None


def _unmask_sng_bytes(data: bytes, xor_mask: bytes) -> bytes:
    n = len(data)
    if n == 0:
        return b""
    key_table = bytes((xor_mask[i % 16] ^ (i & 0xFF)) for i in range(256))
    key_stream = (key_table * ((n + 255) // 256))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(key_stream, "big")).to_bytes(n, "big")


def _sng_art_candidates(entries: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    matches = [e for e in entries if _ART_NAME_RE.match(e[0].rsplit("/", 1)[-1])]
    matches.sort(key=lambda e: 0 if e[0].lower().startswith("album.") else 1)
    return matches


def _sng_has_art(path: Path) -> bool:
    idx = _sng_index(path)
    if not idx:
        return False
    return bool(_sng_art_candidates(idx[1]))


def extract_sng_art(path: Path) -> tuple[bytes, str] | None:
    """Return (raw image bytes, mime type) for the embedded album art, or None."""
    idx = _sng_index(path)
    if not idx:
        return None
    xor_mask, entries = idx
    candidates = _sng_art_candidates(entries)
    if not candidates:
        return None
    name, size, offset = candidates[0]
    mime = ART_MIME.get(Path(name).suffix.lower(), "application/octet-stream")
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            masked = f.read(size)
    except OSError:
        return None
    return _unmask_sng_bytes(masked, xor_mask), mime


def _find_album_art_in(folder: Path) -> Path | None:
    try:
        images = [e for e in folder.iterdir() if e.is_file() and e.suffix.lower() in ART_MIME]
    except OSError:
        return None
    for stem in _ART_STEM_PRIORITY:
        for entry in images:
            if entry.stem.lower() == stem:
                return entry
    for entry in images:
        name = entry.stem.lower()
        if "album" in name or "cover" in name:
            return entry
    return None


def _scan_library(root: Path, cached_by_path: dict[str, dict] | None = None, on_item=None) -> list[dict]:
    cached_by_path = cached_by_path or {}
    items: list[dict] = []

    def walk(directory: Path, depth: int) -> None:
        if depth > _MAX_SCAN_DEPTH:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda e: e.name.lower())
        except OSError:
            return
        if any((directory / f).is_file() for f in _CHART_FILES):
            key = str(directory)
            cached = cached_by_path.get(key)
            if cached is not None:
                items.append(cached)
            else:
                meta = _parse_song_ini(directory / "song.ini")
                size = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
                art = _find_album_art_in(directory)
                items.append({
                    "path": key,
                    "name": meta.get("name") or directory.name,
                    "artist": meta.get("artist", ""),
                    "charter": meta.get("charter", ""),
                    "type": "folder",
                    "size": size,
                    "art": str(art) if art else "",
                })
            if on_item:
                on_item(len(items))
            return
        for entry in entries:
            if entry.is_dir():
                walk(entry, depth + 1)
            elif entry.is_file() and entry.suffix.lower() == ".sng":
                key = str(entry)
                cached = cached_by_path.get(key)
                if cached is not None:
                    items.append(cached)
                else:
                    stem = entry.stem
                    artist, sep, name = stem.partition(" - ")
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    items.append({
                        "path": key,
                        "name": name if sep else stem,
                        "artist": artist if sep else "",
                        "charter": "",
                        "type": "sng",
                        "size": size,
                        "art": str(entry) if _sng_has_art(entry) else "",
                    })
                if on_item:
                    on_item(len(items))

    walk(root, 0)
    items.sort(key=lambda i: (i["artist"].lower(), i["name"].lower()))
    return items


def cached_library(body: dict) -> dict:
    """Return whatever was saved from the last scan of this folder, with no disk I/O.

    Lets the frontend paint the library instantly on startup/tab-switch while
    a real scan (which reconciles adds/removals) runs in the background.
    """
    root = _songs_dir(body)
    cache = _load_cache()
    entry = cache.get(str(root))
    if not entry:
        return {"songs": [], "dir": str(root), "totalSize": 0}
    songs = entry.get("songs", [])
    return {"songs": songs, "dir": str(root), "totalSize": sum(s["size"] for s in songs)}


def start_library_scan(body: dict) -> dict:
    root = _songs_dir(body)
    job_id = uuid.uuid4().hex
    with _scan_lock:
        _scan_jobs[job_id] = {"status": "running", "count": 0, "dir": str(root)}

    def run() -> None:
        if not root.is_dir():
            with _scan_lock:
                _scan_jobs[job_id] = {"status": "done", "count": 0, "dir": str(root), "songs": [], "totalSize": 0}
            return

        def on_item(n: int) -> None:
            with _scan_lock:
                _scan_jobs[job_id]["count"] = n

        try:
            cache = _load_cache()
            cached_by_path = {s["path"]: s for s in cache.get(str(root), {}).get("songs", [])}
            items = _scan_library(root, cached_by_path, on_item)
            cache[str(root)] = {"songs": items}
            _save_cache(cache)
            with _scan_lock:
                _scan_jobs[job_id] = {
                    "status": "done",
                    "count": len(items),
                    "dir": str(root),
                    "songs": items,
                    "totalSize": sum(i["size"] for i in items),
                }
        except Exception as e:  # noqa: BLE001
            with _scan_lock:
                _scan_jobs[job_id] = {"status": "error", "error": str(e), "dir": str(root)}

    threading.Thread(target=run, daemon=True).start()
    return {"jobId": job_id}


def library_scan_status(body: dict) -> dict:
    job_id = body.get("jobId", "")
    with _scan_lock:
        job = _scan_jobs.get(job_id)
        if job is None:
            raise ApiError("Unknown scan job.", code="not_found", status=404)
        return copy.deepcopy(job)


def delete_downloaded(body: dict) -> dict:
    paths = body.get("paths") or []
    if not isinstance(paths, list) or not paths:
        raise ApiError("No songs supplied for deletion.", code="empty")

    deleted, failed = [], []
    for raw in paths:
        p = Path(raw)
        try:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.is_file():
                p.unlink()
            else:
                failed.append({"path": raw, "error": "not found"})
                continue
            deleted.append(raw)
        except OSError as e:
            failed.append({"path": raw, "error": str(e)})

    if deleted:
        cache = _load_cache()
        deleted_set = set(deleted)
        for entry in cache.values():
            entry["songs"] = [s for s in entry.get("songs", []) if s["path"] not in deleted_set]
        _save_cache(cache)

    return {"deleted": deleted, "failed": failed}

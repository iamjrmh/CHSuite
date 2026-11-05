"""CHSongManager - ChorusEncore search + .sng download.

Search proxies the public ChorusEncore API; downloads stream the single-file
``.sng`` chart to the user's songs directory. Requires the ``requests`` package
(lazily imported so the sidecar still boots without it).

Library scanning, downloading, and format conversion all run as background
jobs polled by the frontend, so the UI can show live progress instead of
blocking on one big request/response.

.sng container format: https://github.com/mdsitton/SngFileFormat. A 26-byte
header (magic + version + a random 16-byte xorMask), then three length-prefixed
sections in order - Metadata (song.ini's [song] keys as string pairs),
FileIndex (name/size/absolute-offset per contained file), and FileData (the
files themselves, each individually XOR-masked with a key that cycles with
period 256: ``xorMask[i % 16] ^ (i & 0xFF)``, ``i`` = the byte's own index
within *that file's* contents - not the .sng file as a whole). ``song.ini``
itself is never stored as a file entry; its data lives only in Metadata and
is reconstructed as a plain INI on unpack.
"""

from __future__ import annotations

import configparser
import copy
import json
import os
import re
import shutil
import struct
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import config
from .errors import ApiError, MissingDependency

API_URL = "https://api.enchor.us/search"
FILES_URL = "https://files.enchor.us"
PER_PAGE = 25
# The API enforces both a hard per-request cap (250 - a bigger value gets a
# 400) and a rolling rate limit (X-Ratelimit-* response headers - measured at
# 50 requests/60s). Collecting the ~95k-song catalog at the interactive
# search's PER_PAGE=25 with no pacing means ~3,800 back-to-back requests,
# which blows through that limit almost instantly and 429s out the rest of
# the collection - "download all" silently truncating after ~1,250 songs is
# exactly that failure. 250/page cuts it to ~380 requests, and _throttle()
# below paces those against the server's own reported remaining/reset instead
# of guessing a fixed delay.
_COLLECT_PER_PAGE = 250
_RATE_LIMIT_SAFETY_MARGIN = 3  # stop and wait before actually hitting 0 remaining
_UA = {"User-Agent": "CHSuite/8.0 CHSongManager"}
_CHART_FILES = ("notes.chart", "notes.mid")
_MAX_SCAN_DEPTH = 5
_ART_STEM_PRIORITY = ("album", "cover", "folder", "albumart", "album_art")
_ART_NAME_RE = re.compile(r"^(?:album|cover|folder)\.(?:png|jpe?g)$", re.IGNORECASE)
_SNG_MAGIC = b"SNGPKG"
_SNG_VERSION = 1
# Registry name for background video, https://github.com/mdsitton/SngFileFormat#filename-registry
_VIDEO_EXTS = {".mp4", ".avi", ".webm", ".vp8", ".ogv", ".mpeg"}
_MASK_CHUNK = 1 << 20  # must be a multiple of 256 (the xorMask keystream period)
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
_convert_jobs: dict[str, dict] = {}
_convert_lock = threading.Lock()


class _Cancelled(Exception):
    """Raised internally to unwind a chart download that was cancelled mid-stream."""


class _Stalled(Exception):
    """Raised internally to unwind a single chart's download that made no byte
    progress for too long (or was manually skipped) - distinct from
    `_Cancelled`, which unwinds the whole job."""


def _requests():
    try:
        import requests  # noqa: PLC0415
        return requests
    except ImportError as e:
        raise MissingDependency("requests", "song search & download") from e


def _safe_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", (s or "").strip())
    return s[:140] or "song"


def _expected_base(artist: str, name: str) -> str:
    return _safe_name(f"{artist} - {name}" if artist else name)


def _expected_filename(artist: str, name: str) -> str:
    return _expected_base(artist, name) + ".sng"


def _songs_dir(body: dict) -> Path:
    songs_dir = body.get("dir") or config.get_config().get("sm_songs_dir", "")
    if not songs_dir:
        songs_dir = str(config.documents_clone_hero() / "songs")
    return Path(songs_dir)


def _already_downloaded(songs_dir: Path, artist: str, name: str) -> Path | None:
    """Return the existing path (either format) for this song, or None."""
    base = _expected_base(artist, name)
    sng_path = songs_dir / f"{base}.sng"
    if sng_path.is_file():
        return sng_path
    folder_path = songs_dir / base
    if folder_path.is_dir():
        return folder_path
    return None


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
    # Compact, not indent=2: this file is machine-only and, at a large library's
    # scale (tens of thousands of songs), pretty-printing roughly doubles both
    # the bytes written and the dumps() time for zero benefit.
    try:
        _cache_file().write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    except OSError:
        pass


def _invalidate_cache_paths(songs_dir: Path, paths: list[str]) -> None:
    """Drop specific song entries (and their mtime fingerprints) from the scan cache.

    _scan_library's own mtime check already catches this on its own - an
    in-place rewrite (repacking a .sng, stripping video from a folder) always
    changes that path's mtime, so the next scan reclassifies it regardless.
    This is belt-and-suspenders: it also covers a rename (folder<->.sng) by
    purging the *old* path's mtime, so a later song that happens to land back
    on that exact path can never be mistaken for it, however unlikely.
    """
    cache = _load_cache()
    entry = cache.get(str(songs_dir))
    if not entry:
        return
    remove = set(paths)
    entry["songs"] = [s for s in entry.get("songs", []) if s["path"] not in remove]
    mtimes = entry.get("mtimes", {})
    for p in remove:
        mtimes.pop(p, None)
    entry["mtimes"] = mtimes
    _save_cache(cache)


def _dedupe_by_md5(entries: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for e in entries:
        md5 = e.get("md5", "")
        if not md5 or md5 in seen:
            continue
        seen.add(md5)
        out.append(e)
    return out


def _throttled_search_page(requests, payload: dict, state: dict):
    """POST one search page, pacing against the API's own X-Ratelimit-* headers.

    ``state`` carries ``remaining``/``reset`` across calls so the caller
    doesn't need a module-level lock; a 429 (or any transient failure) is
    retried with backoff instead of aborting the whole collection, since one
    blip used to kill the entire "download all" job.
    """
    remaining = state.get("remaining")
    reset = state.get("reset")
    if remaining is not None and remaining <= _RATE_LIMIT_SAFETY_MARGIN and reset:
        wait = reset - time.time()
        if wait > 0:
            time.sleep(min(wait, 60) + 0.25)

    last_err: Exception | None = None
    for attempt in range(5):
        try:
            r = requests.post(API_URL, json=payload, timeout=20, headers=_UA)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else max(float(r.headers.get("X-Ratelimit-Reset", 0)) - time.time(), 5)
                time.sleep(min(max(wait, 1), 60))
                last_err = ApiError("Rate limited", code="rate_limited", status=429)
                continue
            r.raise_for_status()
            rem_hdr = r.headers.get("X-Ratelimit-Remaining")
            reset_hdr = r.headers.get("X-Ratelimit-Reset")
            if rem_hdr is not None:
                state["remaining"] = int(rem_hdr)
            if reset_hdr is not None:
                state["reset"] = float(reset_hdr)
            return r.json()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(min(1.5 * (attempt + 1), 8))
    raise last_err if last_err else ApiError("Search failed", code="search", status=502)


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
            "alreadyDownloaded": _already_downloaded(songs_dir, artist, name) is not None,
        })
    page = int(body.get("page", 1))
    return {"found": found, "page": page, "hasMore": page * PER_PAGE < found, "songs": songs}


def _download_format_settings() -> tuple[str, bool]:
    cfg = config.get_config()
    fmt = cfg.get("sm_download_format", "sng")
    if fmt not in ("sng", "folder"):
        fmt = "sng"
    return fmt, bool(cfg.get("sm_skip_video", False))


def _download_one(entry: dict, out_dir: Path, fmt: str, skip_video: bool) -> None:
    """Download (or skip, if already on disk) a single queue entry, mutating
    it in place. Field writes are lock-protected so a concurrent status read
    (deepcopy'd for the frontend) never sees a status without its matching
    path/error - the network I/O itself runs unlocked.

    The already-downloaded check runs first and is a couple of stat() calls,
    so a queue built against a huge existing library races through anything
    already present almost instantly instead of re-downloading it.
    """
    md5 = entry.get("md5", "")
    name = entry.get("name", "") or md5
    artist = entry.get("artist", "")
    if not md5:
        with _download_lock:
            entry["status"] = "failed"
            entry["error"] = "no md5"
        return

    existing = _already_downloaded(out_dir, artist, name)
    if existing is not None:
        with _download_lock:
            entry["status"] = "skipped"
            entry["path"] = str(existing)
        return

    requests = _requests()
    base = _expected_base(artist, name)
    final_dest = out_dir / (f"{base}.sng" if fmt == "sng" else base)
    # Raw download lands on the destination volume (not the system temp
    # drive) so any later unpack/repack is a same-volume, atomic finish.
    raw_sng = out_dir / f".chsuite-dl-{uuid.uuid4().hex}.sng"
    tmp_extract = None
    try:
        with requests.get(f"{FILES_URL}/{md5}.sng", stream=True, timeout=60, headers=_UA) as r:
            r.raise_for_status()
            with open(raw_sng, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)

        idx = _sng_index(raw_sng)
        has_video = bool(idx and any(_is_video_name(n) for n, _, _ in idx[1]))

        if fmt == "sng":
            if skip_video and has_video:
                tmp_extract = Path(tempfile.mkdtemp(prefix="chsuite-dl-", dir=out_dir))
                unpack_sng(raw_sng, tmp_extract, skip_video=True)
                pack_folder_to_sng(tmp_extract, final_dest, skip_video=False)
            else:
                raw_sng.replace(final_dest)
        else:  # folder
            unpack_sng(raw_sng, final_dest, skip_video=skip_video)

        with _download_lock:
            entry["status"] = "done"
            entry["path"] = str(final_dest)
    except Exception as e:  # noqa: BLE001
        with _download_lock:
            entry["status"] = "failed"
            entry["error"] = str(e)
    finally:
        raw_sng.unlink(missing_ok=True)
        if tmp_extract is not None:
            shutil.rmtree(tmp_extract, ignore_errors=True)


def _run_download_queue(job_id: str, out_dir: Path, fmt: str, skip_video: bool) -> None:
    """Download a queue that's already fully known (explicit selection, or a
    cached full-catalog replay)."""
    with _download_lock:
        queue_len = len(_download_jobs[job_id]["queue"])

    for i in range(queue_len):
        with _download_lock:
            entry = _download_jobs[job_id]["queue"][i]
            entry["status"] = "downloading"
        _download_one(entry, out_dir, fmt, skip_video)
        with _download_lock:
            _download_jobs[job_id]["done"] += 1

    with _download_lock:
        _download_jobs[job_id]["status"] = "done"


def _run_download_queue_streaming(job_id: str, out_dir: Path, fmt: str, skip_video: bool, collection: dict) -> None:
    """Download entries as they're queued by a concurrent collector thread,
    instead of waiting for the full search collection to finish first.

    Downloads start on page 1's results immediately; if the downloader
    catches up to the collector (common - stat-only skips of already-owned
    songs are far faster than paging a rate-limited API) it briefly polls
    for more entries rather than exiting. ``collection`` is the shared dict
    the collector thread updates: ``done`` flips true once no more pages are
    coming, ``error`` carries a message if collection failed partway.
    """
    i = 0
    while True:
        with _download_lock:
            queue = _download_jobs[job_id]["queue"]
            if i < len(queue):
                entry = queue[i]
                entry["status"] = "downloading"
            else:
                entry = None
        if entry is None:
            if collection["done"]:
                break
            time.sleep(0.15)
            continue
        _download_one(entry, out_dir, fmt, skip_video)
        with _download_lock:
            _download_jobs[job_id]["done"] += 1
        i += 1

    with _download_lock:
        if collection.get("error"):
            _download_jobs[job_id]["error"] = collection["error"]
        _download_jobs[job_id]["status"] = "done"


def start_download(body: dict) -> dict:
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

    fmt, skip_video = _download_format_settings()

    job_id = uuid.uuid4().hex
    queue = [
        {"md5": s.get("md5", ""), "name": s.get("name", "") or s.get("md5", ""), "artist": s.get("artist", ""), "status": "pending"}
        for s in songs
    ]
    with _download_lock:
        _download_jobs[job_id] = {"status": "running", "dir": str(out_dir), "total": len(queue), "done": 0, "queue": queue}

    threading.Thread(target=_run_download_queue, args=(job_id, out_dir, fmt, skip_video), daemon=True).start()
    return {"jobId": job_id}


def start_download_all(body: dict) -> dict:
    requests = _requests()
    out_dir = _songs_dir(body)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ApiError(f"Could not create songs folder: {e}", code="mkdir", status=500)
    config.update_config({"sm_songs_dir": str(out_dir)})

    fmt, skip_video = _download_format_settings()

    job_id = uuid.uuid4().hex
    with _download_lock:
        _download_jobs[job_id] = {"status": "collecting", "dir": str(out_dir), "total": 0, "done": 0, "queue": []}

    query = body.get("query", "") or ""
    instrument = body.get("instrument")
    difficulty = body.get("difficulty")
    sort_prop = body.get("sort")

    payload_base = {
        "search": query,
        "per_page": _COLLECT_PER_PAGE,
        "instrument": instrument,
        "difficulty": difficulty,
        "sort": {"type": sort_prop, "direction": body.get("sortDir", "asc")} if sort_prop else None,
        "source": "bridge",
    }

    def run() -> None:
        # Collect and download at the same time, on two threads, instead of
        # paging the whole result set before a single download starts.
        # Rate-limit pacing alone can take a while to walk a large result
        # set, and there's no reason to sit through all of that before the
        # first (very likely already-owned, near-instant skip) entry is even
        # checked against disk.
        collection = {"done": False, "error": None}

        def collect() -> None:
            page = 1
            rate_state: dict = {}
            while True:
                try:
                    resp = _throttled_search_page(requests, {**payload_base, "page": page}, rate_state)
                except Exception as e:  # noqa: BLE001
                    collection["error"] = f"Search failed while collecting: {e}"
                    break

                data = resp.get("data", [])
                found = resp.get("found", 0)
                if not data:
                    break
                new_entries = _dedupe_by_md5([
                    {"md5": s.get("md5", ""), "name": s.get("name", "") or s.get("md5", ""), "artist": s.get("artist", ""), "status": "pending"}
                    for s in data
                ])
                with _download_lock:
                    job = _download_jobs[job_id]
                    job["queue"] = _dedupe_by_md5(job["queue"] + new_entries)
                    job["total"] = len(job["queue"])
                if page * _COLLECT_PER_PAGE >= found:
                    break
                page += 1

            collection["done"] = True

        threading.Thread(target=collect, daemon=True).start()
        with _download_lock:
            _download_jobs[job_id]["status"] = "running"
        _run_download_queue_streaming(job_id, out_dir, fmt, skip_video, collection)

    threading.Thread(target=run, daemon=True).start()
    return {"jobId": job_id}


def download_status(body: dict) -> dict:
    job_id = body.get("jobId", "")
    with _download_lock:
        job = _download_jobs.get(job_id)
        if job is None:
            raise ApiError("Unknown download job.", code="not_found", status=404)
        return copy.deepcopy(job)


# --- bulk "download everything" -----------------------------------------------
# The one-click "download all songs" button. Unlike the job-based flows above,
# this walks the *entire* unfiltered catalog on a single long-lived worker
# thread, checkpointed to disk so it survives an app restart, with per-chart
# stall detection, a circuit breaker for repeated failures, and a low-disk
# guard - built for genuinely downloading the whole library unattended, not a
# short filtered batch.

_BULK_SORT = {"type": "modifiedTime", "direction": "asc"}
# Sorting by modifiedTime asc keeps page N stable across a run that spans
# hours - new charts land at the end of the catalog instead of shifting
# earlier pages, so resuming at a saved page number never skips or repeats
# entries the way an unsorted (freshness-first) order would as the catalog
# grows underneath a long-running collection.
_BULK_MAX_FAILED = 200
_BULK_LOW_DISK_BYTES = 5 * 1024 * 1024 * 1024
_BULK_ITEM_DELAY = 0.35
_BULK_RETRY_DELAYS = (5, 30, 120)
_BULK_CIRCUIT_BREAKER_THRESHOLD = 5
_BULK_CIRCUIT_BREAKER_PAUSE = 300
_BULK_STALL_SECONDS = 15

_bulk_lock = threading.Lock()
_bulk_state: dict = {"status": "none"}
_bulk_stop_event: threading.Event | None = None
_bulk_skip_event: threading.Event | None = None
_bulk_thread: threading.Thread | None = None


def _bulk_checkpoint_file() -> Path:
    d = Path.home() / "Documents" / "CHSuite"
    d.mkdir(parents=True, exist_ok=True)
    return d / "bulk_download.json"


def _load_bulk_checkpoint() -> dict | None:
    f = _bulk_checkpoint_file()
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_bulk_checkpoint(state: dict) -> None:
    try:
        _bulk_checkpoint_file().write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


def _bulk_publish_live(state: dict) -> None:
    """Publish to the in-memory mirror status() reads, without touching disk -
    cheap enough to call on every progress tick (per chunk, throttled) without
    turning a big file's download into hundreds of small disk writes."""
    with _bulk_lock:
        _bulk_state.clear()
        _bulk_state.update(state)


def _bulk_sync(state: dict) -> None:
    """Persist to disk AND publish to the in-memory mirror - for real
    checkpoints (an item finished, a page turned, status changed), not
    high-frequency in-flight progress."""
    _save_bulk_checkpoint(state)
    _bulk_publish_live(state)


def _bulk_download_one(requests_mod, md5: str, name: str, artist: str, out_dir: Path, stop_event, on_progress=None) -> dict:
    """Download one chart. Streams to a `.part` sibling and atomically renames on
    success, so a mid-transfer crash/kill never leaves a truncated file that
    skip-if-exists would mistake for a completed download. `on_progress`, if
    given, is called after every chunk with (bytesSoFar, totalBytesOrZero) -
    totalBytes is 0 when the server doesn't send a Content-Length - and may
    return a truthy value to abort this one download early (used for stall
    detection and the manual Skip button; the whole job keeps running)."""
    if not md5:
        return {"status": "failed", "error": "no md5"}

    fname = _expected_filename(artist, name)
    dest = out_dir / fname
    if dest.is_file():
        return {"status": "skipped", "path": str(dest)}

    part = dest.with_name(dest.name + ".part")
    size = 0
    try:
        with requests_mod.get(f"{FILES_URL}/{md5}.sng", stream=True, timeout=60, headers=_UA) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            with open(part, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if stop_event is not None and stop_event.is_set():
                        raise _Cancelled
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)
                        if on_progress is not None and on_progress(size, total):
                            raise _Stalled

        os.replace(part, dest)
        return {"status": "done", "path": str(dest), "size": size}

    except _Cancelled:
        part.unlink(missing_ok=True)
        return {"status": "cancelled"}
    except _Stalled:
        part.unlink(missing_ok=True)
        return {"status": "stalled"}
    except Exception as e:  # noqa: BLE001
        part.unlink(missing_ok=True)
        requests = _requests()
        status_code = None
        retry_after = None
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
            status_code = e.response.status_code
            ra = e.response.headers.get("Retry-After")
            if ra:
                try:
                    retry_after = float(ra)
                except ValueError:
                    retry_after = None
        return {"status": "failed", "error": str(e), "statusCode": status_code, "retryAfter": retry_after}


def _process_item(state: dict, stop_event, skip_event, requests_mod, out_dir: Path,
                   md5: str, name: str, artist: str, allow_stall_defer: bool) -> str:
    """Attempt one chart, retrying genuine failures with backoff. Mutates
    state's counters/sample lists for done/skipped/failed outcomes (the
    caller decides what a "stalled" outcome means - deferred on the main
    pass, a real failure on the final sweep). Returns the terminal outcome:
    "done" | "skipped" | "failed" | "stalled" | "cancelled"."""
    state["currentName"] = f"{artist} - {name}" if artist else name
    state["currentBytes"] = 0
    state["currentTotal"] = 0
    skip_event.clear()
    _bulk_sync(state)

    result: dict = {"status": "failed"}
    for attempt in range(len(_BULK_RETRY_DELAYS) + 1):
        state["currentBytes"] = 0
        state["currentTotal"] = 0

        last_pub = [0.0]
        last_marker = [-1]
        last_change = [time.monotonic()]

        def _on_progress(done_bytes: int, total_bytes: int) -> bool:
            now = time.monotonic()
            marker = (done_bytes * 100 // total_bytes) if total_bytes else done_bytes
            if marker != last_marker[0]:
                last_marker[0] = marker
                last_change[0] = now
            stalled = skip_event.is_set() or (allow_stall_defer and (now - last_change[0]) >= _BULK_STALL_SECONDS)
            if now - last_pub[0] >= 0.25 or done_bytes == total_bytes or stalled:
                last_pub[0] = now
                state["currentBytes"] = done_bytes
                state["currentTotal"] = total_bytes
                _bulk_publish_live(state)
            return stalled

        result = _bulk_download_one(requests_mod, md5, name, artist, out_dir, stop_event, _on_progress)
        if result["status"] in ("stalled", "cancelled"):
            break
        if result["status"] != "failed":
            break
        if attempt >= len(_BULK_RETRY_DELAYS):
            break
        delay = result.get("retryAfter") or _BULK_RETRY_DELAYS[attempt]
        stop_event.wait(delay)
        if stop_event.is_set():
            break

    state["currentBytes"] = 0
    state["currentTotal"] = 0
    skip_event.clear()

    if result["status"] == "cancelled" or stop_event.is_set():
        return "cancelled"
    if result["status"] == "stalled":
        return "stalled"
    if result["status"] == "done":
        state["done"] = state.get("done", 0) + 1
        state["bytesDownloaded"] = state.get("bytesDownloaded", 0) + (result.get("size") or 0)
        return "done"
    if result["status"] == "skipped":
        state["skipped"] = state.get("skipped", 0) + 1
        skipped_sample = state.setdefault("skippedSample", [])
        if len(skipped_sample) < _BULK_MAX_FAILED:
            existing_name = Path(result["path"]).name if result.get("path") else "an existing file"
            skipped_sample.append({"md5": md5, "name": state["currentName"], "reason": f"Already saved as {existing_name}"})
        return "skipped"

    state["failedCount"] = state.get("failedCount", 0) + 1
    failed_list = state.setdefault("failed", [])
    if len(failed_list) < _BULK_MAX_FAILED:
        failed_list.append({"md5": md5, "name": state["currentName"], "error": result.get("error", "")})
    return "failed"


def _bulk_worker(state: dict, stop_event, skip_event) -> None:
    requests = _requests()
    out_dir = Path(state["dir"])
    consecutive_failures = 0
    state.setdefault("deferred", [])
    state.setdefault("deferredCount", 0)
    state["phase"] = "catalog"

    while True:
        if stop_event.is_set():
            state["status"] = "stopped"
            _bulk_sync(state)
            return

        try:
            free = shutil.disk_usage(out_dir).free
        except OSError:
            free = None
        if free is not None and free < _BULK_LOW_DISK_BYTES:
            state["status"] = "stopped"
            state["stopReason"] = f"Stopped - only {free / 1073741824:.1f} GB free on disk"
            _bulk_sync(state)
            return

        payload = {
            "search": "",
            "page": state["page"],
            "per_page": PER_PAGE,
            "instrument": None,
            "difficulty": None,
            "sort": _BULK_SORT,
            "source": "bridge",
        }
        try:
            r = requests.post(API_URL, json=payload, timeout=20, headers=_UA)
            r.raise_for_status()
            resp = r.json()
        except Exception as e:  # noqa: BLE001
            consecutive_failures += 1
            if consecutive_failures >= _BULK_CIRCUIT_BREAKER_THRESHOLD:
                state["status"] = "stopped"
                state["stopReason"] = f"Stopped after repeated search errors: {e}"
                _bulk_sync(state)
                return
            state["currentName"] = f"Search failed, retrying: {e}"
            _bulk_sync(state)
            stop_event.wait(_BULK_RETRY_DELAYS[min(consecutive_failures, len(_BULK_RETRY_DELAYS)) - 1])
            continue

        items = resp.get("data", [])
        state["found"] = resp.get("found", state.get("found", 0))
        if not items:
            break

        for item in items:
            if stop_event.is_set():
                state["status"] = "stopped"
                _bulk_sync(state)
                return
            md5 = item.get("md5", "")
            name = item.get("name", "") or md5
            artist = item.get("artist", "")
            outcome = _process_item(state, stop_event, skip_event, requests, out_dir, md5, name, artist, allow_stall_defer=True)

            if outcome == "cancelled":
                state["status"] = "stopped"
                _bulk_sync(state)
                return
            elif outcome == "stalled":
                state["deferred"].append({"md5": md5, "name": name, "artist": artist})
                state["deferredCount"] = state.get("deferredCount", 0) + 1
                consecutive_failures = 0
            elif outcome in ("done", "skipped"):
                consecutive_failures = 0
            else:  # "failed"
                consecutive_failures += 1
                if consecutive_failures >= _BULK_CIRCUIT_BREAKER_THRESHOLD:
                    state["currentName"] = "Paused after repeated failures - retrying in 5 minutes"
                    _bulk_sync(state)
                    stop_event.wait(_BULK_CIRCUIT_BREAKER_PAUSE)
                    consecutive_failures = 0
                    if stop_event.is_set():
                        state["status"] = "stopped"
                        _bulk_sync(state)
                        return

            _bulk_sync(state)
            stop_event.wait(_BULK_ITEM_DELAY)

        state["page"] += 1
        _bulk_sync(state)

    state["phase"] = "deferred"
    _bulk_sync(state)
    while state.get("deferred"):
        if stop_event.is_set():
            state["status"] = "stopped"
            _bulk_sync(state)
            return
        item = state["deferred"][0]
        outcome = _process_item(
            state, stop_event, skip_event, requests, out_dir,
            item.get("md5", ""), item.get("name", ""), item.get("artist", ""), allow_stall_defer=False,
        )
        if outcome == "cancelled":
            state["status"] = "stopped"
            _bulk_sync(state)
            return
        elif outcome == "stalled":
            state["failedCount"] = state.get("failedCount", 0) + 1
            failed_list = state.setdefault("failed", [])
            if len(failed_list) < _BULK_MAX_FAILED:
                failed_list.append({"md5": item.get("md5", ""), "name": state["currentName"], "error": "Still too slow on its final attempt"})
        state["deferred"].pop(0)
        _bulk_sync(state)
        stop_event.wait(_BULK_ITEM_DELAY)

    state["status"] = "done"
    state["phase"] = "catalog"
    state["currentName"] = ""
    state["currentBytes"] = 0
    state["currentTotal"] = 0
    _bulk_sync(state)


def bulk_download_status(body: dict) -> dict:
    with _bulk_lock:
        if _bulk_state.get("status") != "none":
            return copy.deepcopy(_bulk_state)

    checkpoint = _load_bulk_checkpoint()
    if checkpoint is None:
        return {"status": "none"}

    checkpoint["status"] = "interrupted" if checkpoint.get("status") == "running" else checkpoint.get("status", "stopped")
    return checkpoint


def start_bulk_download(body: dict) -> dict:
    global _bulk_stop_event, _bulk_skip_event, _bulk_thread

    with _bulk_lock:
        if _bulk_thread is not None and _bulk_thread.is_alive():
            return copy.deepcopy(_bulk_state)

    out_dir = _songs_dir(body)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ApiError(f"Could not create songs folder: {e}", code="mkdir", status=500)
    config.update_config({"sm_songs_dir": str(out_dir)})

    resume = bool(body.get("resume"))
    checkpoint = _load_bulk_checkpoint() if resume else None
    if checkpoint and checkpoint.get("dir") == str(out_dir) and checkpoint.get("status") in ("running", "interrupted", "stopped"):
        state = checkpoint
    else:
        state = {
            "dir": str(out_dir), "page": 1, "found": 0, "done": 0, "skipped": 0,
            "failedCount": 0, "failed": [], "skippedSample": [], "deferred": [], "deferredCount": 0,
            "currentName": "", "currentBytes": 0, "currentTotal": 0, "bytesDownloaded": 0,
            "startedAt": datetime.now(timezone.utc).isoformat(),
        }

    state["currentBytes"] = 0
    state["currentTotal"] = 0
    state.setdefault("skippedSample", [])
    state.setdefault("deferred", [])
    state.setdefault("deferredCount", 0)
    state["status"] = "running"
    _bulk_sync(state)

    stop_event = threading.Event()
    skip_event = threading.Event()
    thread = threading.Thread(target=_bulk_worker, args=(state, stop_event, skip_event), daemon=True)

    with _bulk_lock:
        _bulk_stop_event = stop_event
        _bulk_skip_event = skip_event
        _bulk_thread = thread

    thread.start()
    return copy.deepcopy(state)


def stop_bulk_download(body: dict) -> dict:
    with _bulk_lock:
        if _bulk_stop_event is not None:
            _bulk_stop_event.set()
        return copy.deepcopy(_bulk_state)


def skip_current_bulk_download(body: dict) -> dict:
    with _bulk_lock:
        if not (_bulk_thread is not None and _bulk_thread.is_alive() and _bulk_skip_event is not None):
            raise ApiError("No bulk download is currently running.", code="not_running", status=404)
        _bulk_skip_event.set()
        return copy.deepcopy(_bulk_state)


def discard_bulk_download(body: dict) -> dict:
    with _bulk_lock:
        if _bulk_thread is not None and _bulk_thread.is_alive():
            raise ApiError("Stop the running bulk download before discarding it.", code="running")
        _bulk_state.clear()
        _bulk_state["status"] = "none"
    try:
        _bulk_checkpoint_file().unlink(missing_ok=True)
    except OSError:
        pass
    return {"status": "none"}


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


# --- .sng container: read, write, and video-file filtering ------------------

def _is_video_name(name: str) -> bool:
    p = PurePosixPath(name.replace("\\", "/"))
    return p.stem.lower() == "video" and p.suffix.lower() in _VIDEO_EXTS


def _mask_stream(src, dst, length: int, xor_mask: bytes) -> None:
    """Copy ``length`` bytes from ``src`` to ``dst``, XOR-masking each chunk.

    The keystream cycles with period 256, and every chunk here is either a
    full _MASK_CHUNK (a multiple of 256) or the final short remainder, so each
    chunk's local byte index 0..N always equals its true index modulo 256 -
    the same guarantee _unmask_sng_bytes relies on when it builds a keystream
    starting from index 0. That lets each chunk be masked independently,
    without ever holding the whole file in memory (matters for video.mp4).
    """
    remaining = length
    while remaining > 0:
        n = min(_MASK_CHUNK, remaining)
        chunk = src.read(n)
        if len(chunk) != n:
            raise ApiError("Unexpected end of file while reading .sng contents.", code="bad_sng")
        dst.write(_unmask_sng_bytes(chunk, xor_mask))
        remaining -= n


def _sng_parse(path: Path) -> dict | None:
    """Full header + metadata + file-index parse (no file contents read)."""
    try:
        with open(path, "rb") as f:
            if f.read(6) != _SNG_MAGIC:
                return None
            version = struct.unpack("<I", f.read(4))[0]
            xor_mask = f.read(16)
            if len(xor_mask) != 16:
                return None

            metadata_len = struct.unpack("<Q", f.read(8))[0]
            metadata_start = f.tell()
            metadata_count = struct.unpack("<Q", f.read(8))[0]
            metadata: list[tuple[str, str]] = []
            for _ in range(metadata_count):
                key_len = struct.unpack("<i", f.read(4))[0]
                key = f.read(key_len).decode("utf-8", "replace")
                val_len = struct.unpack("<i", f.read(4))[0]
                value = f.read(val_len).decode("utf-8", "replace")
                metadata.append((key, value))
            f.seek(metadata_start + metadata_len)  # authoritative - skip any trailing padding

            struct.unpack("<Q", f.read(8))[0]  # fileMetaLen, unused (entries read directly)
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
            return {"version": version, "xor_mask": xor_mask, "metadata": metadata, "entries": entries}
    except (OSError, struct.error):
        return None


def _sng_index(path: Path) -> tuple[bytes, list[tuple[str, int, int]]] | None:
    parsed = _sng_parse(path)
    if not parsed:
        return None
    return parsed["xor_mask"], parsed["entries"]


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


def _ini_to_metadata(ini_path: Path) -> list[tuple[str, str]]:
    if not ini_path.is_file():
        return []
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str  # preserve key casing instead of lowercasing
    try:
        cp.read(ini_path, encoding="utf-8-sig")
    except (OSError, configparser.Error):
        return []
    section = next((s for s in cp.sections() if s.lower() == "song"), None)
    if section is None:
        return []
    pairs = []
    for key, value in cp.items(section):
        # Metadata strings can't safely round-trip through an INI file with
        # these characters - https://github.com/mdsitton/SngFileFormat#metadata-strings
        clean_key = key.replace(";", "").replace("=", "").replace("\r", "").replace("\n", "")
        clean_val = value.replace(";", "").replace("\r", "").replace("\n", "")
        if clean_key:
            pairs.append((clean_key, clean_val))
    return pairs


def _metadata_to_ini(pairs: list[tuple[str, str]]) -> str:
    lines = ["[song]"]
    lines.extend(f"{key} = {value}" for key, value in pairs)
    return "\n".join(lines) + "\n"


def unpack_sng(sng_path: Path, dest_dir: Path, *, skip_video: bool = False) -> list[str]:
    """Extract a .sng into ``dest_dir`` as a normal song folder.

    Reconstructs song.ini from the embedded Metadata section. Returns the
    list of file names that were skipped because they matched the video
    filename registry and ``skip_video`` was set.
    """
    parsed = _sng_parse(sng_path)
    if not parsed:
        raise ApiError(f"Not a valid .sng file: {sng_path.name}", code="bad_sng")
    dest_dir.mkdir(parents=True, exist_ok=True)
    xor_mask = parsed["xor_mask"]
    skipped: list[str] = []
    try:
        with open(sng_path, "rb") as f:
            for name, size, offset in parsed["entries"]:
                if skip_video and _is_video_name(name):
                    skipped.append(name)
                    continue
                out_path = dest_dir / Path(name.replace("\\", "/"))
                out_path.parent.mkdir(parents=True, exist_ok=True)
                f.seek(offset)
                with open(out_path, "wb") as out:
                    _mask_stream(f, out, size, xor_mask)
        (dest_dir / "song.ini").write_text(_metadata_to_ini(parsed["metadata"]), encoding="utf-8")
    except Exception:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise
    return skipped


def pack_folder_to_sng(folder: Path, dest_sng: Path, *, skip_video: bool = False) -> list[str]:
    """Pack a song folder into a .sng file at ``dest_sng`` (written atomically).

    Returns the list of relative file names skipped because they matched the
    video filename registry and ``skip_video`` was set.
    """
    files: list[tuple[str, Path, int]] = []
    skipped: list[str] = []
    for p in sorted(folder.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(folder).as_posix()
        if rel.lower() == "song.ini":
            continue  # reserved: its data lives in the Metadata section instead
        if skip_video and _is_video_name(rel):
            skipped.append(rel)
            continue
        files.append((rel, p, p.stat().st_size))

    metadata = _ini_to_metadata(folder / "song.ini")
    xor_mask = os.urandom(16)

    meta_pairs = bytearray()
    for key, value in metadata:
        kb, vb = key.encode("utf-8"), value.encode("utf-8")
        meta_pairs += struct.pack("<i", len(kb)) + kb + struct.pack("<i", len(vb)) + vb
    meta_body = struct.pack("<Q", len(metadata)) + bytes(meta_pairs)
    metadata_len = len(meta_body)

    name_bytes_list = []
    for rel, _p, _size in files:
        nb = rel.encode("utf-8")
        if len(nb) > 255:
            raise ApiError(f"File name too long for .sng: {rel}", code="name_too_long")
        name_bytes_list.append(nb)

    entries_body_size = sum(1 + len(nb) + 8 + 8 for nb in name_bytes_list)
    file_meta_len = 8 + entries_body_size

    header_size = 6 + 4 + 16
    base_offset = header_size + 8 + metadata_len + 8 + file_meta_len + 8

    offsets = []
    running = base_offset
    for _rel, _p, size in files:
        offsets.append(running)
        running += size
    total_file_bytes = running - base_offset

    idx_body = bytearray(struct.pack("<Q", len(files)))
    for nb, (_rel, _p, size), offset in zip(name_bytes_list, files, offsets):
        idx_body += bytes([len(nb)]) + nb + struct.pack("<Q", size) + struct.pack("<Q", offset)

    dest_sng.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_sng.parent / f".chsuite-pack-{uuid.uuid4().hex}.sng"
    try:
        with open(tmp, "wb") as out:
            out.write(_SNG_MAGIC)
            out.write(struct.pack("<I", _SNG_VERSION))
            out.write(xor_mask)
            out.write(struct.pack("<Q", metadata_len))
            out.write(meta_body)
            out.write(struct.pack("<Q", file_meta_len))
            out.write(bytes(idx_body))
            out.write(struct.pack("<Q", total_file_bytes))
            for _rel, p, size in files:
                with open(p, "rb") as src:
                    _mask_stream(src, out, size, xor_mask)
        os.replace(tmp, dest_sng)
    finally:
        tmp.unlink(missing_ok=True)
    return skipped


def _find_album_art_in(folder: Path) -> Path | None:
    try:
        with os.scandir(folder) as it:
            images = [Path(e.path) for e in it if e.is_file() and Path(e.name).suffix.lower() in ART_MIME]
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


def _folder_size(folder: Path) -> int:
    """Recursive size sum via os.scandir - DirEntry.stat() reuses the file
    metadata Windows' FindNextFile already returned when listing the
    directory, so this avoids one syscall per file that pathlib's rglob()
    would otherwise cost."""
    total = 0
    try:
        with os.scandir(folder) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        total += _folder_size(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _classify_folder(directory: Path) -> dict:
    meta = _parse_song_ini(directory / "song.ini")
    art = _find_album_art_in(directory)
    return {
        "path": str(directory),
        "name": meta.get("name") or directory.name,
        "artist": meta.get("artist", ""),
        "charter": meta.get("charter", ""),
        "type": "folder",
        "size": _folder_size(directory),
        "art": str(art) if art else "",
    }


def _classify_sng(sng_path: Path, size: int) -> dict:
    stem = sng_path.stem
    artist, sep, name = stem.partition(" - ")
    return {
        "path": str(sng_path),
        "name": name if sep else stem,
        "artist": artist if sep else "",
        "charter": "",
        "type": "sng",
        "size": size,
        "art": str(sng_path) if _sng_has_art(sng_path) else "",
    }


def _scan_library(
    root: Path,
    cached_by_path: dict[str, dict] | None = None,
    cached_mtimes: dict[str, float] | None = None,
    on_item=None,
) -> tuple[list[dict], dict[str, float]]:
    """Walk the songs folder, reusing cached metadata for anything unchanged.

    Every song folder and .sng file's mtime is compared against the value
    recorded on the previous scan (``cached_mtimes``). On NTFS (and most
    filesystems), a directory's own mtime only moves when a direct child is
    added or removed - editing a file in place doesn't touch it - so an
    unchanged mtime is a reliable signal that nothing was added to or removed
    from that song, and it's reused wholesale without even listing its
    contents (no song.ini parse, no size sum, no art lookup). Only genuinely
    new or changed entries get re-classified. That's what turns a rescan of a
    stable library into O(what changed) instead of O(whole library) - the
    first scan (empty cache) still walks everything, same as before.
    """
    cached_by_path = cached_by_path or {}
    cached_mtimes = cached_mtimes or {}
    items: list[dict] = []
    mtimes: dict[str, float] = {}

    def emit(key: str, item: dict, mtime: float) -> None:
        # Recorded only once classification has actually produced an item,
        # so a mid-scan exception never leaves a path's mtime cached without
        # a matching library entry to go with it.
        mtimes[key] = mtime
        items.append(item)
        if on_item:
            on_item(len(items))

    def walk(directory: Path, depth: int, known_mtime: float | None) -> None:
        if depth > _MAX_SCAN_DEPTH:
            return
        try:
            with os.scandir(directory) as it:
                entries = sorted(it, key=lambda e: e.name.lower())
        except OSError:
            return

        if any(e.name.lower() in _CHART_FILES and e.is_file() for e in entries):
            key = str(directory)
            dir_mtime = known_mtime
            if dir_mtime is None:
                try:
                    dir_mtime = directory.stat().st_mtime
                except OSError:
                    dir_mtime = 0.0
            cached = cached_by_path.get(key)
            if cached is not None and cached_mtimes.get(key) == dir_mtime:
                emit(key, cached, dir_mtime)
            else:
                emit(key, _classify_folder(directory), dir_mtime)
            return

        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if is_dir:
                key = entry.path
                try:
                    dmtime = entry.stat().st_mtime
                except OSError:
                    dmtime = None
                cached = cached_by_path.get(key)
                # Fully pruned on a hit: never even scandir()s into it.
                if dmtime is not None and cached is not None and cached_mtimes.get(key) == dmtime:
                    emit(key, cached, dmtime)
                    continue
                walk(Path(key), depth + 1, dmtime)
            elif entry.name.lower().endswith(".sng"):
                key = entry.path
                try:
                    st = entry.stat()
                except OSError:
                    continue
                cached = cached_by_path.get(key)
                if cached is not None and cached_mtimes.get(key) == st.st_mtime:
                    emit(key, cached, st.st_mtime)
                else:
                    emit(key, _classify_sng(Path(key), st.st_size), st.st_mtime)

    walk(root, 0, None)
    items.sort(key=lambda i: (i["artist"].lower(), i["name"].lower()))
    return items, mtimes


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
            prev = cache.get(str(root), {})
            cached_by_path = {s["path"]: s for s in prev.get("songs", [])}
            cached_mtimes = prev.get("mtimes", {})
            items, mtimes = _scan_library(root, cached_by_path, cached_mtimes, on_item)
            # mtimes exactly matching the previous scan's means every path was
            # rediscovered unchanged and nothing was added or removed - skip
            # rewriting the cache file (tens of MB at a large library's scale)
            # entirely rather than doing it on every single load.
            if mtimes != cached_mtimes:
                cache[str(root)] = {"songs": items, "mtimes": mtimes}
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
            mtimes = entry.get("mtimes", {})
            for p in deleted_set:
                mtimes.pop(p, None)
            entry["mtimes"] = mtimes
        _save_cache(cache)

    return {"deleted": deleted, "failed": failed}


# --- format conversion (folder <-> .sng) + in-place video stripping --------
# Runs the same way for both a fresh download's post-processing decisions and
# an explicit user action on already-downloaded songs, so switching format
# preference or turning off video backgrounds never requires re-downloading.

def _convert_one(path: Path, target: str, strip_video: bool) -> dict:
    is_sng = path.is_file() and path.suffix.lower() == ".sng"
    if not is_sng and not path.is_dir():
        return {"path": str(path), "status": "failed", "error": "not found"}
    cur_type = "sng" if is_sng else "folder"
    final_type = cur_type if target == "keep" else target

    try:
        if is_sng and final_type == "sng":
            if not strip_video:
                return {"path": str(path), "status": "skipped"}
            idx = _sng_index(path)
            has_video = bool(idx and any(_is_video_name(n) for n, _, _ in idx[1]))
            if not has_video:
                return {"path": str(path), "status": "skipped"}
            tmp_extract = Path(tempfile.mkdtemp(prefix="chsuite-cvt-", dir=path.parent))
            try:
                unpack_sng(path, tmp_extract, skip_video=True)
                tmp_sng = path.parent / f".chsuite-cvt-{uuid.uuid4().hex}.sng"
                try:
                    pack_folder_to_sng(tmp_extract, tmp_sng, skip_video=False)
                    os.replace(tmp_sng, path)  # same-volume, atomic
                finally:
                    tmp_sng.unlink(missing_ok=True)
            finally:
                shutil.rmtree(tmp_extract, ignore_errors=True)
            return {"path": str(path), "status": "done", "newPath": str(path)}

        if is_sng and final_type == "folder":
            dest = path.with_suffix("")
            if dest.exists():
                return {"path": str(path), "status": "failed", "error": f"'{dest.name}' already exists"}
            unpack_sng(path, dest, skip_video=strip_video)
            path.unlink()
            return {"path": str(path), "status": "done", "newPath": str(dest)}

        if not is_sng and final_type == "sng":
            dest = path.parent / f"{path.name}.sng"
            if dest.exists():
                return {"path": str(path), "status": "failed", "error": f"'{dest.name}' already exists"}
            pack_folder_to_sng(path, dest, skip_video=strip_video)
            shutil.rmtree(path)
            return {"path": str(path), "status": "done", "newPath": str(dest)}

        # folder -> folder: nothing to repack, just strip video files in place.
        if strip_video:
            removed = False
            for f in list(path.rglob("*")):
                if f.is_file() and _is_video_name(f.relative_to(path).as_posix()):
                    f.unlink()
                    removed = True
            return {"path": str(path), "status": "done" if removed else "skipped", "newPath": str(path)}
        return {"path": str(path), "status": "skipped"}
    except (OSError, ApiError) as e:
        return {"path": str(path), "status": "failed", "error": str(e)}


def start_library_convert(body: dict) -> dict:
    paths = body.get("paths") or []
    target = body.get("target", "keep")
    strip_video = bool(body.get("stripVideo"))
    if not isinstance(paths, list) or not paths:
        raise ApiError("No songs supplied for conversion.", code="empty")
    if target not in ("sng", "folder", "keep"):
        raise ApiError("Invalid conversion target.", code="bad_target")
    if target == "keep" and not strip_video:
        raise ApiError("Nothing to do: keep the same format with video stripping off.", code="noop")

    songs_dir = _songs_dir(body)
    job_id = uuid.uuid4().hex
    queue = [{"path": p, "status": "pending"} for p in paths]
    with _convert_lock:
        _convert_jobs[job_id] = {"status": "running", "total": len(queue), "done": 0, "queue": queue}

    def run() -> None:
        for i, p in enumerate(paths):
            with _convert_lock:
                _convert_jobs[job_id]["queue"][i]["status"] = "converting"
            result = _convert_one(Path(p), target, strip_video)
            with _convert_lock:
                _convert_jobs[job_id]["queue"][i] = result
                _convert_jobs[job_id]["done"] += 1
        _invalidate_cache_paths(songs_dir, paths)
        with _convert_lock:
            _convert_jobs[job_id]["status"] = "done"

    threading.Thread(target=run, daemon=True).start()
    return {"jobId": job_id}


def library_convert_status(body: dict) -> dict:
    job_id = body.get("jobId", "")
    with _convert_lock:
        job = _convert_jobs.get(job_id)
        if job is None:
            raise ApiError("Unknown conversion job.", code="not_found", status=404)
        return copy.deepcopy(job)

"""CHManager + CHPatcher backend.

Covers the Clone Hero install registry (game_installs.json): listing installs,
patching/unpatching the ``isFromLauncher`` flag, launching the game, opening the
folder, and fetching available releases/PTB builds from GitHub.
"""

from __future__ import annotations

import copy
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from . import config, menuchanger
from .errors import ApiError, MissingDependency

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

# Clone Hero's data folder is named differently per platform.
_CH_DATA_DIR = "clonehero_Data" if IS_LINUX else ("Data" if IS_MAC else "Clone Hero_Data")

_GITHUB_RELEASES = "https://api.github.com/repos/clonehero-game/releases/releases"

_install_jobs: dict[str, dict] = {}
_install_lock = threading.Lock()


def _requests():
    try:
        import requests  # noqa: PLC0415
        return requests
    except ImportError as e:
        raise MissingDependency("requests", "downloading Clone Hero releases") from e


def _is_64bit() -> bool:
    machine = platform.machine().lower()
    return machine in ("amd64", "x86_64") or (machine == "x86" and platform.architecture()[0] == "64bit")


def _norm(p: str) -> str:
    try:
        return os.path.normcase(os.path.normpath(p))
    except (TypeError, ValueError):
        return p or ""


def _read_raw() -> dict:
    f = config.installs_file()
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"installs": []}
    return {"installs": []}


def _write_raw(data: dict) -> None:
    f = config.installs_file()
    try:
        if f.is_file():
            shutil.copy2(str(f), str(f) + ".bak")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        raise ApiError(f"Could not write game_installs.json: {e}", code="installs_write", status=500)


def find_ch_exe(directory: str) -> str | None:
    d = Path(directory)
    if not d.is_dir():
        return None
    if IS_WINDOWS:
        for name in ("Clone Hero.exe", "clonehero.exe"):
            if (d / name).is_file():
                return str(d / name)
    elif IS_MAC:
        app = d if d.suffix == ".app" else next(iter(d.glob("*.app")), None)
        if app:
            exe = app / "Contents" / "MacOS" / "Clone Hero"
            if exe.is_file():
                return str(exe)
    else:
        for name in ("clonehero", "Clone Hero", "CloneHero"):
            if (d / name).is_file():
                return str(d / name)
    return None


# --- Release asset selection ------------------------------------------------
# Ported from the original CHSuite's CHManager (_win_asset/_linux_asset/
# _mac_asset/_pick_asset) - same priority rules, just OS-detected server-side
# instead of per-button in the UI.

def _pick_win_asset(assets: list[dict]) -> dict | None:
    win_exts = (".exe", ".7z", ".zip")
    is64 = _is_64bit()
    arch_tag, anti_tag = ("64", "32") if is64 else ("32", "64")
    candidates, fallback = [], []
    for a in assets:
        n = a["name"].lower()
        if not any(n.endswith(ext) for ext in win_exts):
            continue
        if "win" not in n and "windows" not in n:
            continue
        if anti_tag in n:
            continue
        (candidates if arch_tag in n else fallback).append(a)
    pool = candidates or fallback
    if not pool:
        return None

    def rank(a: dict) -> int:
        n = a["name"].lower()
        for i, ext in enumerate(win_exts):
            if n.endswith(ext):
                return i
        return 99

    pool.sort(key=rank)
    return pool[0]


def _pick_linux_asset(assets: list[dict]) -> dict | None:
    linux_exts = (".appimage", ".tar.xz", ".tar", ".7z")
    is64 = _is_64bit()
    arch_tag = "x86_64" if is64 else "x86"
    candidates, fallback = [], []
    for a in assets:
        n = a["name"].lower()
        if not any(n.endswith(ext) for ext in linux_exts):
            continue
        if "launcher" in n:
            continue
        if "win" in n or "windows" in n or "mac" in n or "osx" in n:
            continue
        if is64 and re.search(r"x86(?!_64)", n):
            continue
        if not is64 and "x86_64" in n:
            continue
        (candidates if (arch_tag in n or "linux" in n or "standalone" in n) else fallback).append(a)
    pool = candidates or fallback
    if not pool:
        return None

    def rank(a: dict) -> int:
        n = a["name"].lower()
        if "standalone" in n and n.endswith(".tar.xz"):
            return 0
        if "standalone" in n and n.endswith(".tar"):
            return 1
        if n.endswith(".tar.xz"):
            return 2
        if n.endswith(".tar"):
            return 3
        if n.endswith(".7z"):
            return 4
        if n.endswith(".appimage"):
            return 5
        return 99

    pool.sort(key=rank)
    return pool[0]


def _pick_mac_asset(assets: list[dict]) -> dict | None:
    candidates = [a for a in assets if a["name"].lower().endswith((".pkg", ".dmg")) and "launcher" not in a["name"].lower()]
    if not candidates:
        return None
    candidates.sort(key=lambda a: 0 if a["name"].lower().endswith(".pkg") else 1)
    return candidates[0]


def pick_asset(assets: list[dict]) -> dict | None:
    """Return the best release asset for the current OS/architecture, or None."""
    if IS_WINDOWS:
        return _pick_win_asset(assets)
    if IS_MAC:
        return _pick_mac_asset(assets)
    return _pick_linux_asset(assets) or _pick_win_asset(assets)


# --- Extraction / installation ----------------------------------------------

def _flatten_single_subdir(dest_dir: Path) -> None:
    """If dest_dir contains exactly one subfolder, move its contents up and
    remove it. Handles archives that nest an extra level, e.g. Windows zips
    shaped like Windows/CloneHero-Win-x64/<files>."""
    try:
        subdirs = [p for p in dest_dir.iterdir() if p.is_dir()]
    except OSError:
        return
    if len(subdirs) != 1:
        return
    sub = subdirs[0]
    for item in list(sub.iterdir()):
        shutil.move(str(item), str(dest_dir / item.name))
    try:
        sub.rmdir()
    except OSError:
        shutil.rmtree(str(sub), ignore_errors=True)


def _flatten_platform_subdir(dest_dir: Path, platform_name: str) -> None:
    """If dest_dir contains exactly one subfolder named after the platform
    (e.g. "Windows"), flatten it into dest_dir. Windows archives nest a
    second level inside that folder, so flatten once more in that case."""
    try:
        subdirs = [p for p in dest_dir.iterdir() if p.is_dir()]
    except OSError:
        return
    if len(subdirs) != 1 or subdirs[0].name.lower() != platform_name:
        return
    sub = subdirs[0]
    for item in list(sub.iterdir()):
        shutil.move(str(item), str(dest_dir / item.name))
    try:
        sub.rmdir()
    except OSError:
        shutil.rmtree(str(sub), ignore_errors=True)
    if platform_name == "windows":
        _flatten_single_subdir(dest_dir)


def _watch_and_click_yes(stop_evt: threading.Event) -> None:
    """Inno Setup's /VERYSILENT install can still pop a "Portable Mode?"
    confirmation dialog. Poll for it and auto-click Yes until the installer
    finishes. Windows-only; no-op elsewhere."""
    if not IS_WINDOWS:
        return
    import ctypes  # noqa: PLC0415
    import ctypes.wintypes  # noqa: PLC0415

    user32 = ctypes.windll.user32
    bm_click = 0x00F5
    gw_child = 5
    gw_hwndnext = 2

    def get_text(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def get_class(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    def find_yes_in(parent: int) -> int | None:
        child = user32.GetWindow(parent, gw_child)
        while child:
            if get_class(child) == "Button" and get_text(child).replace("&", "").strip().lower() == "yes":
                return child
            child = user32.GetWindow(child, gw_hwndnext)
        return None

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    clicked: set[int] = set()
    while not stop_evt.is_set():
        wins: list[int] = []

        def collect(hwnd: int, _lparam: int, _out: list[int] = wins) -> bool:
            _out.append(hwnd)
            return True

        user32.EnumWindows(enum_windows_proc(collect), 0)
        for hwnd in wins:
            if hwnd in clicked or get_class(hwnd) != "#32770":
                continue
            yes_btn = user32.GetDlgItem(hwnd, 6) or find_yes_in(hwnd)
            if yes_btn:
                clicked.add(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.PostMessageW(yes_btn, bm_click, 0, 0)
        stop_evt.wait(0.2)


def _run_silent_exe_installer(file_path: Path, dest_dir: Path) -> None:
    stop_evt = threading.Event()
    watcher = threading.Thread(target=_watch_and_click_yes, args=(stop_evt,), daemon=True)
    watcher.start()
    try:
        result = subprocess.run(
            [str(file_path), "/VERYSILENT", "/CURRENTUSER", "/TYPE=portable", f"/DIR={dest_dir}"],
            timeout=300,
        )
    finally:
        stop_evt.set()
    if result.returncode != 0:
        raise ApiError(f"Installer exited with code {result.returncode}.", code="installer", status=500)


def _extract_7z(file_path: Path, dest_dir: Path) -> None:
    try:
        import py7zr  # noqa: PLC0415
        with py7zr.SevenZipFile(file_path, mode="r") as z:
            z.extractall(path=dest_dir)
        return
    except ImportError:
        pass
    for cmd in ("7z", "7za", r"C:\Program Files\7-Zip\7z.exe"):
        try:
            subprocess.run([cmd, "i"], capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        subprocess.run([cmd, "x", str(file_path), f"-o{dest_dir}", "-y"], check=True)
        return
    raise ApiError("Cannot extract .7z: install py7zr (pip install py7zr) or 7-Zip.", code="no_7z", status=500)


def _install_from_dmg(file_path: Path, dest_dir: Path) -> Path:
    import plistlib  # noqa: PLC0415
    mount_result = subprocess.run(
        ["hdiutil", "attach", str(file_path), "-nobrowse", "-readonly", "-plist"],
        capture_output=True, text=True, timeout=60,
    )
    if mount_result.returncode != 0:
        raise ApiError(f"hdiutil attach failed: {mount_result.stderr}", code="dmg_mount", status=500)
    plist_data = plistlib.loads(mount_result.stdout.encode())
    mount_point = next((e["mount-point"] for e in plist_data.get("system-entities", []) if "mount-point" in e), None)
    if not mount_point:
        raise ApiError("Could not determine DMG mount point.", code="dmg_mount", status=500)
    try:
        apps = list(Path(mount_point).glob("*.app"))
        if not apps:
            raise ApiError("No .app bundle found inside the DMG.", code="dmg_noapp", status=500)
        src_app = apps[0]
        dst_app = dest_dir / src_app.name
        if dst_app.exists():
            shutil.rmtree(str(dst_app))
        shutil.copytree(str(src_app), str(dst_app))
        return dst_app
    finally:
        subprocess.run(["hdiutil", "detach", mount_point, "-quiet"], capture_output=True, timeout=30)


def _extract_asset(file_path: Path, dest_dir: Path) -> Path:
    """Extract/install the downloaded asset into dest_dir. Returns the actual
    install directory (differs for .dmg, which mounts and copies an .app)."""
    name_lower = file_path.name.lower()
    actual_dest = dest_dir

    if name_lower.endswith(".exe"):
        _run_silent_exe_installer(file_path, dest_dir)
        file_path.unlink(missing_ok=True)
    elif name_lower.endswith(".7z"):
        _extract_7z(file_path, dest_dir)
        file_path.unlink(missing_ok=True)
        if IS_WINDOWS:
            _flatten_platform_subdir(dest_dir, "windows")
    elif name_lower.endswith(".appimage"):
        file_path.chmod(file_path.stat().st_mode | 0o111)
    elif name_lower.endswith(".pkg") and IS_MAC:
        result = subprocess.run(["sudo", "installer", "-pkg", str(file_path), "-target", "/"], timeout=300)
        file_path.unlink(missing_ok=True)
        if result.returncode != 0:
            raise ApiError(f"pkg installer exited with code {result.returncode}.", code="pkg_install", status=500)
    elif name_lower.endswith(".dmg") and IS_MAC:
        actual_dest = _install_from_dmg(file_path, dest_dir)
        file_path.unlink(missing_ok=True)
    elif name_lower.endswith((".tar.xz", ".tar.gz", ".tar.bz2", ".tar")):
        import tarfile  # noqa: PLC0415
        with tarfile.open(file_path, "r:*") as tf:
            tf.extractall(dest_dir)
        file_path.unlink(missing_ok=True)
        if IS_LINUX:
            _flatten_platform_subdir(dest_dir, "linux")
    else:
        import zipfile  # noqa: PLC0415
        with zipfile.ZipFile(file_path, "r") as zf:
            zf.extractall(dest_dir)
        file_path.unlink(missing_ok=True)
        if IS_WINDOWS:
            _flatten_platform_subdir(dest_dir, "windows")

    # The archive may have nested the actual game one folder deep.
    if actual_dest == dest_dir and find_ch_exe(str(dest_dir)) is None:
        for item in dest_dir.iterdir():
            if item.is_dir() and find_ch_exe(str(item)):
                actual_dest = item
                break
    return actual_dest


def _detect_version(path: Path) -> str:
    """Read the real installed version from Clone Hero_Data/version.json,
    rather than trusting a release tag or a manually-typed value."""
    vf = path / _CH_DATA_DIR / "version.json"
    if not vf.is_file():
        return ""
    try:
        data = json.loads(vf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(data.get("version") or "").strip()


_USER_DATA_ITEMS = ("GameData", "PlayerData", "Replays", "profiles.ini", "scorestats.json")


def _copy_user_data(old_dir: Path, new_dir: Path) -> list[str]:
    """Carry saves/settings (GameData, PlayerData, Replays, profiles.ini,
    scorestats.json) from a previous install into a freshly installed one."""
    if not old_dir or not old_dir.is_dir() or _norm(str(old_dir)) == _norm(str(new_dir)):
        return []
    copied = []
    for item in _USER_DATA_ITEMS:
        src = old_dir / item
        if not src.exists():
            continue
        dst = new_dir / item
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            copied.append(item)
        except OSError:
            pass
    return copied


def _register_new_install(actual: Path, tag: str) -> None:
    data = _read_raw()
    norm_actual = _norm(str(actual))
    existing = {_norm(i.get("directoryPath", "")) for i in data.get("installs", [])}
    if norm_actual not in existing:
        data.setdefault("installs", []).append({
            "directoryPath": str(actual),
            "isFromLauncher": False,
            "version": _detect_version(actual) or tag.lstrip("v"),
            "manifestVersion": None,
            "manifestDate": None,
            "releaseChannel": "stable",
        })
        _write_raw(data)

    patch = {"ch_default_install": str(actual)}
    data_path = actual / _CH_DATA_DIR
    if data_path.is_dir():
        patch["default_data_path"] = str(data_path)
    config.update_config(patch)


def _resolve_install_dest(body: dict, tag: str) -> Path:
    explicit = body.get("dest") or ""
    if explicit:
        return Path(explicit)
    base = config.get_config().get("default_install_dir", "")
    if not base:
        raise ApiError(
            "No install location set. Choose a folder for this install, or set a default install location in Settings.",
            code="no_dest", status=400,
        )
    return Path(base) / tag


def start_install(body: dict) -> dict:
    tag = body.get("tag") or ""
    url = body.get("url") or ""
    name = body.get("name") or ""
    size = int(body.get("size") or 0)
    if not tag or not url or not name:
        raise ApiError("Missing release info.", code="empty")

    requests = _requests()
    dest_dir = _resolve_install_dest(body, tag)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ApiError(f"Could not create install folder: {e}", code="mkdir", status=500)

    # Snapshot the current default install now - by the time extraction
    # finishes, _register_new_install will have overwritten this to the
    # new install, so it's this new install's own contents by then.
    old_default = config.get_config().get("ch_default_install", "")

    job_id = uuid.uuid4().hex
    with _install_lock:
        _install_jobs[job_id] = {
            "status": "running", "phase": "downloading",
            "downloaded": 0, "total": size, "dest": str(dest_dir), "message": "Starting download…",
        }

    def run() -> None:
        try:
            file_path = dest_dir / name
            downloaded = 0
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        with _install_lock:
                            _install_jobs[job_id]["downloaded"] = downloaded
                            mb = downloaded / 1_048_576
                            total_mb = size / 1_048_576
                            _install_jobs[job_id]["message"] = f"Downloading… {mb:.1f} / {total_mb:.1f} MB"

            with _install_lock:
                _install_jobs[job_id]["phase"] = "extracting"
                _install_jobs[job_id]["message"] = "Extracting…"

            actual_dest = _extract_asset(file_path, dest_dir)

            copied: list[str] = []
            copied_bgs: list[str] = []
            if old_default:
                with _install_lock:
                    _install_jobs[job_id]["phase"] = "copying"
                    _install_jobs[job_id]["message"] = "Copying your saves and settings…"
                copied = _copy_user_data(Path(old_default), actual_dest)

                with _install_lock:
                    _install_jobs[job_id]["phase"] = "backgrounds"
                    _install_jobs[job_id]["message"] = "Carrying over menu backgrounds…"
                try:
                    old_data_dir = Path(old_default) / _CH_DATA_DIR
                    new_data_dir = actual_dest / _CH_DATA_DIR
                    bg_result = menuchanger.copy_menu_backgrounds(str(old_data_dir), str(new_data_dir))
                    copied_bgs = bg_result.get("copied", [])
                except Exception:  # noqa: BLE001 - optional step, never fail the whole install over it
                    pass

            with _install_lock:
                _install_jobs[job_id]["phase"] = "registering"
                _install_jobs[job_id]["message"] = "Registering install…"

            _register_new_install(actual_dest, tag)

            with _install_lock:
                _install_jobs[job_id] = {
                    "status": "done", "phase": "done",
                    "downloaded": downloaded, "total": size,
                    "dest": str(actual_dest), "message": f"Installed to {actual_dest}",
                    "copiedUserData": copied,
                    "copiedBackgrounds": copied_bgs,
                }
        except Exception as e:  # noqa: BLE001
            with _install_lock:
                _install_jobs[job_id] = {"status": "error", "phase": "error", "error": str(e), "dest": str(dest_dir)}

    threading.Thread(target=run, daemon=True).start()
    return {"jobId": job_id}


def install_status(body: dict) -> dict:
    job_id = body.get("jobId", "")
    with _install_lock:
        job = _install_jobs.get(job_id)
        if job is None:
            raise ApiError("Unknown install job.", code="not_found", status=404)
        return copy.deepcopy(job)


def list_installs() -> dict:
    cfg = config.get_config()
    default = _norm(cfg.get("ch_default_install", ""))
    names = cfg.get("install_names") or {}
    data = _read_raw()
    out = []
    for inst in data.get("installs", []):
        path = inst.get("directoryPath") or inst.get("path") or ""
        exe = find_ch_exe(path)
        detected_version = _detect_version(Path(path)) if path else ""
        out.append({
            "path": path,
            "name": names.get(_norm(path), ""),
            "version": detected_version or inst.get("version") or inst.get("buildVersion") or "?",
            "fromLauncher": bool(inst.get("isFromLauncher", True)),
            "channel": inst.get("releaseChannel", "stable"),
            "exists": bool(exe),
            "exe": exe or "",
            "isDefault": _norm(path) == default and bool(default),
        })
    return {"registry": str(config.installs_file()), "installs": out}


def rename_install(body: dict) -> dict:
    path = body.get("path") or ""
    if not path:
        raise ApiError("No install path supplied.", code="empty")
    name = (body.get("name") or "").strip()

    cfg = config.get_config()
    names = dict(cfg.get("install_names") or {})
    key = _norm(path)
    if name:
        names[key] = name
    else:
        names.pop(key, None)
    config.update_config({"install_names": names})
    return {"path": path, "name": name}


def patch_installs(body: dict, *, manual: bool) -> dict:
    paths = body.get("paths") or ([] if "path" not in body else [body["path"]])
    if not paths:
        raise ApiError("No installs selected.", code="empty")

    data = _read_raw()
    if not data.get("installs"):
        raise ApiError(
            "game_installs.json not found or empty - the Clone Hero Launcher may not be installed.",
            code="no_registry", status=404,
        )

    targets = {_norm(p) for p in paths}
    patched = []
    for inst in data.get("installs", []):
        path = inst.get("directoryPath") or inst.get("path") or ""
        if _norm(path) in targets:
            if manual:
                inst["isFromLauncher"] = False
                inst["manifestVersion"] = None
                inst["manifestDate"] = None
            else:
                inst["isFromLauncher"] = True
                ver = inst.get("version")
                if ver and not inst.get("manifestVersion"):
                    channel = inst.get("releaseChannel", "stable")
                    suffix = f"-{channel}" if channel != "stable" else ""
                    inst["manifestVersion"] = f"{ver}{suffix}-win64.json"
            patched.append(path)

    if not patched:
        raise ApiError("No matching installs were found in the registry.", code="no_match", status=404)

    _write_raw(data)
    verb = "patched to Manual" if manual else "restored to Launcher"
    return {"patched": patched, "count": len(patched), "message": f"{len(patched)} install(s) {verb}."}


def set_default(body: dict) -> dict:
    path = body.get("path") or ""
    if not path:
        raise ApiError("No install path supplied.", code="empty")
    cfg = config.update_config({"ch_default_install": path})
    return {"ch_default_install": cfg.get("ch_default_install", "")}


def add_install(body: dict) -> dict:
    path = body.get("path") or ""
    if not Path(path).is_dir():
        raise ApiError("That folder does not exist.", code="bad_path", status=404)
    if not find_ch_exe(path):
        raise ApiError("No Clone Hero executable found in that folder.", code="no_exe", status=404)
    data = _read_raw()
    if any(_norm(i.get("directoryPath", "")) == _norm(path) for i in data.get("installs", [])):
        return {"message": "Install already registered.", "added": False}
    data.setdefault("installs", []).append({
        "directoryPath": path,
        "version": _detect_version(Path(path)) or body.get("version") or "manual",
        "isFromLauncher": False,
        "releaseChannel": "stable",
    })
    _write_raw(data)
    return {"message": "Install registered.", "added": True}


def delete_install(body: dict) -> dict:
    path = body.get("path") or ""
    # Unregistering deletes the install's files by default - there's no
    # point keeping a multi-hundred-MB game folder around after removing it
    # from the list. Pass removeFiles: false explicitly to keep the files.
    remove_files = bool(body.get("removeFiles", True))
    data = _read_raw()
    before = len(data.get("installs", []))
    data["installs"] = [
        i for i in data.get("installs", [])
        if _norm(i.get("directoryPath", "")) != _norm(path)
    ]
    _write_raw(data)

    names = dict(config.get_config().get("install_names") or {})
    if names.pop(_norm(path), None) is not None:
        config.update_config({"install_names": names})
    removed_files = False
    if remove_files and Path(path).is_dir():
        try:
            shutil.rmtree(path)
            removed_files = True
        except OSError as e:
            raise ApiError(f"Unregistered, but could not delete files: {e}", code="rmtree", status=500)
    return {"unregistered": before - len(data["installs"]), "removedFiles": removed_files}


def launch(body: dict) -> dict:
    path = body.get("path") or config.get_config().get("ch_default_install", "")
    exe = find_ch_exe(path)
    if not exe:
        raise ApiError("Could not find a Clone Hero executable to launch.", code="no_exe", status=404)
    try:
        subprocess.Popen([exe], cwd=str(Path(exe).parent))
    except OSError as e:
        raise ApiError(f"Failed to launch Clone Hero: {e}", code="launch", status=500)
    return {"launched": exe}


def open_folder(body: dict) -> dict:
    path = body.get("path") or ""
    if not Path(path).exists():
        raise ApiError("Folder does not exist.", code="bad_path", status=404)
    try:
        if IS_WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        elif IS_MAC:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as e:
        raise ApiError(f"Could not open folder: {e}", code="open", status=500)
    return {"opened": path}


def list_releases() -> dict:
    requests = _requests()
    try:
        resp = requests.get(_GITHUB_RELEASES, timeout=20, headers={"Accept": "application/vnd.github+json"})
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:  # noqa: BLE001
        raise ApiError(f"Could not reach GitHub: {e}", code="github", status=502)

    arch = "x64" if _is_64bit() else "x86"
    releases, ptb = [], []
    for rel in raw:
        assets = [
            {"name": a.get("name", ""), "url": a.get("browser_download_url", ""), "size": a.get("size", 0)}
            for a in rel.get("assets", [])
        ]
        asset = pick_asset(assets)
        if not asset:
            continue  # no build for this OS/architecture - hide it, matching the original CHManager
        entry = {
            "tag": rel.get("tag_name", ""),
            "name": rel.get("name") or rel.get("tag_name", ""),
            "prerelease": bool(rel.get("prerelease")),
            "publishedAt": rel.get("published_at", ""),
            "asset": asset,
        }
        (ptb if entry["prerelease"] else releases).append(entry)

    return {"arch": arch, "releases": releases, "ptb": ptb}

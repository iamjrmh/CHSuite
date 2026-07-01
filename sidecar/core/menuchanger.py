"""CHMenuChanger - Unity .assets menu-background texture swapping.

This is a faithful port of the original ``AssetManager`` (UnityPy + Pillow +
texture2ddecoder), adapted to a headless request/response model. A single
manager instance is cached per ``data_dir`` so a scan can be reused by the
subsequent preview/apply calls. Current in-game textures are returned to the
frontend as base64 PNG data URIs.
"""

from __future__ import annotations

import io
import os
import shutil
import threading
from base64 import b64encode
from pathlib import Path

from .errors import ApiError, MissingDependency

BACKGROUNDS = [
    "Spray", "Pastel Burst", "Groovy", "Grains",
    "Blue Rays", "Alien", "Autumn", "Light", "Dark",
    "Classic", "Surfer", "SurferAlt", "Rainbow", "Animated",
    "Logo_Transparent",
]
EXACT_ASSET_FILE = {"Logo_Transparent": "globalgamemanagers.assets"}
BACKUP_DIR_NAME = "_CH_BG_Backups"
_PREVIEW_MAX_W = 512


def required_size(name: str):
    return (2030, 1328) if name == "Logo_Transparent" else (1920, 1080)


def _norm(s: str) -> str:
    import re
    return re.sub(r"[\s_\-]", "", s).lower()


def _require_libs():
    try:
        import UnityPy  # noqa: PLC0415
    except ImportError as e:
        raise MissingDependency("UnityPy", "menu background editing") from e
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError as e:
        raise MissingDependency("Pillow", "menu background editing") from e
    return UnityPy, Image


class AssetManager:
    def __init__(self, data_dir: str):
        UnityPy, _ = _require_libs()
        self._UnityPy = UnityPy
        self.data_dir = str(data_dir)
        self._data = {}
        self._env_map = {}
        self._envs = {}
        self._dirty: set[str] = set()
        self._scan()

    def _scan(self):
        data_dir = Path(self.data_dir)
        if not data_dir.is_dir():
            raise ApiError(f"Folder not found: {data_dir}", code="bad_path", status=404)
        candidates = []
        for f in data_dir.iterdir():
            if not f.is_file():
                continue
            lo = f.name.lower()
            if f.suffix.lower() == ".assets" or lo == "globalgamemanagers":
                candidates.append(f)

        def sort_key(p: Path):
            n = p.name.lower()
            if n == "sharedassets1.assets":
                return 0
            if n == "globalgamemanagers.assets":
                return 1
            if n == "globalgamemanagers":
                return 2
            if "sharedassets" in n:
                return 3
            if "resources" in n:
                return 4
            return 5

        candidates.sort(key=sort_key)
        for fpath in candidates:
            self._load_file(fpath)

    def _load_file(self, fpath: Path):
        key = str(fpath)
        if key in self._envs:
            return
        try:
            env = self._UnityPy.load(key)
            self._envs[key] = env
            for obj in env.objects:
                if obj.type.name == "Texture2D":
                    try:
                        d = obj.read()
                        n = getattr(d, "m_Name", None) or getattr(d, "name", None)
                        if n and n not in self._data:
                            self._data[n] = d
                            self._env_map[n] = (env, key)
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass

    def find_for_bg(self, bg: str):
        required_file = EXACT_ASSET_FILE.get(bg)
        if required_file:
            req_lo = required_file.lower()
            for name, (_env, fpath) in self._env_map.items():
                if Path(fpath).name.lower() != req_lo:
                    continue
                if _norm(name) == _norm(bg) or _norm(bg) in _norm(name):
                    return name
            return None
        nb = _norm(bg)
        names = list(self._data.keys())
        for n in names:
            if _norm(n) == nb:
                return n
        for n in names:
            if nb in _norm(n):
                return n
        for n in names:
            nn = _norm(n)
            if len(nn) >= 3 and nn in nb:
                return n
        return None

    def export_image(self, asset_name: str):
        _, Image = _require_libs()
        d = self._data.get(asset_name)
        if d is None:
            return None, f"Asset '{asset_name}' not in cache"
        try:
            img = d.image
            if img is not None:
                return img.convert("RGBA"), None
        except Exception as e:  # noqa: BLE001
            return None, str(e)
        return None, "no decodable image"

    def import_image(self, asset_name: str, pil) -> bool:
        d = self._data.get(asset_name)
        if d is None:
            return False
        rgba = pil.convert("RGBA")
        for attempt in ("set_image", "image"):
            try:
                if attempt == "set_image" and hasattr(d, "set_image"):
                    d.set_image(rgba)
                    d.save()
                elif attempt == "image":
                    d.image = rgba
                    d.save()
                else:
                    continue
                self._dirty.add(asset_name)
                return True
            except Exception:  # noqa: BLE001
                continue
        try:
            from UnityPy.enums import TextureFormat as TF  # noqa: PLC0415
            d.m_TextureFormat = TF.RGBA32
            d.image = rgba
            d.save()
            self._dirty.add(asset_name)
            return True
        except Exception:  # noqa: BLE001
            return False

    def backup_dir(self) -> str:
        return os.path.join(self.data_dir, BACKUP_DIR_NAME)

    def needs_backup(self):
        bd = self.backup_dir()
        return [fp for fp in self._envs if not os.path.isfile(os.path.join(bd, Path(fp).name))]

    def has_full_backup(self) -> bool:
        return len(self.needs_backup()) == 0

    def create_backups(self):
        bd = self.backup_dir()
        os.makedirs(bd, exist_ok=True)
        created, errors = [], []
        for fpath in self.needs_backup():
            dest = os.path.join(bd, Path(fpath).name)
            try:
                shutil.copy2(fpath, dest)
                created.append(dest)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{Path(fpath).name}: {e}")
        return created, errors

    def restore_backups(self):
        bd = self.backup_dir()
        if not os.path.isdir(bd):
            raise ApiError("No backups found to restore.", code="no_backup", status=404)
        restored, errors = [], []
        for fpath in list(self._envs):
            src = os.path.join(bd, Path(fpath).name)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, fpath)
                    restored.append(fpath)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{Path(fpath).name}: {e}")
        return restored, errors

    def save_modified(self):
        dirty_files = {}
        for name in self._dirty:
            entry = self._env_map.get(name)
            if entry:
                env, fpath = entry
                dirty_files[fpath] = env
        if not dirty_files:
            return [], ["No textures were imported - nothing to save."]
        saved, errors = [], []
        for fpath, env in dirty_files.items():
            try:
                data = env.file.save()
                with open(fpath, "wb") as f:
                    f.write(data)
                saved.append(fpath)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{Path(fpath).name}: {e}")
        self._dirty.clear()
        return saved, errors


# ---------------------------------------------------------------------------
# Per-data_dir cache + request handlers
# ---------------------------------------------------------------------------

_managers: dict[str, AssetManager] = {}
_lock = threading.Lock()


def _get_manager(data_dir: str, *, refresh: bool = False) -> AssetManager:
    key = os.path.normcase(os.path.normpath(data_dir))
    with _lock:
        if refresh or key not in _managers:
            _managers[key] = AssetManager(data_dir)
        return _managers[key]


def _close_env(env) -> None:
    """UnityPy keeps a raw file handle open per loaded .assets file for lazy
    reads (it never reads the whole file into memory). Reach into each
    loaded file's reader and close the underlying stream directly."""
    for f in list(getattr(env, "files", {}).values()):
        reader = getattr(f, "reader", f)  # SerializedFile wraps a reader; raw entries ARE the reader
        stream = getattr(reader, "stream", None)
        if stream is not None:
            try:
                stream.close()
            except Exception:  # noqa: BLE001
                pass


def release(data_dir: str) -> None:
    """Drop a cached AssetManager and close its file handles. Without this,
    a scanned install's .assets files stay open for the sidecar's whole
    lifetime, which blocks deleting or moving that install's folder on
    Windows - most visibly after installing a new version, since that now
    scans both the old and new install to carry over menu backgrounds."""
    key = os.path.normcase(os.path.normpath(data_dir))
    with _lock:
        am = _managers.pop(key, None)
    if am is None:
        return
    for env in am._envs.values():  # noqa: SLF001
        _close_env(env)


def _png_data_uri(pil, max_w: int = _PREVIEW_MAX_W) -> str:
    if pil.width > max_w:
        ratio = max_w / pil.width
        pil = pil.resize((max_w, max(1, int(pil.height * ratio))))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return "data:image/png;base64," + b64encode(buf.getvalue()).decode("ascii")


def backgrounds() -> dict:
    return {
        "backgrounds": [
            {"name": b, "requiredSize": list(required_size(b)), "exact": b in EXACT_ASSET_FILE}
            for b in BACKGROUNDS
        ]
    }


def scan(body: dict) -> dict:
    data_dir = body.get("dataDir") or ""
    if not data_dir:
        raise ApiError("No Clone Hero_Data folder supplied.", code="empty")
    want_previews = bool(body.get("previews", True))
    am = _get_manager(data_dir, refresh=True)

    created, _ = am.create_backups()
    items = []
    for bg in BACKGROUNDS:
        matched = am.find_for_bg(bg)
        entry = {
            "name": bg,
            "matched": bool(matched),
            "asset": matched or "",
            "requiredSize": list(required_size(bg)),
            "preview": "",
        }
        if matched and want_previews:
            img, err = am.export_image(matched)
            if img is not None and err is None:
                try:
                    entry["preview"] = _png_data_uri(img)
                except Exception:  # noqa: BLE001
                    pass
        items.append(entry)

    return {
        "dataDir": data_dir,
        "hasBackup": am.has_full_backup(),
        "backupsCreated": len(created),
        "backgrounds": items,
    }


def preview(body: dict) -> dict:
    data_dir = body.get("dataDir") or ""
    bg = body.get("background") or ""
    am = _get_manager(data_dir)
    matched = am.find_for_bg(bg)
    if not matched:
        raise ApiError(f"No texture matched for '{bg}'.", code="no_match", status=404)
    img, err = am.export_image(matched)
    if img is None:
        raise ApiError(f"Could not decode '{bg}': {err}", code="decode", status=500)
    return {"background": bg, "asset": matched, "preview": _png_data_uri(img)}


def apply(body: dict) -> dict:
    _, Image = _require_libs()
    data_dir = body.get("dataDir") or ""
    # replacements: [{ background, imagePath }]
    replacements = body.get("replacements") or []
    if not replacements:
        raise ApiError("No replacement images supplied.", code="empty")

    am = _get_manager(data_dir)
    if not am.has_full_backup():
        am.create_backups()

    applied, errors = [], []
    for rep in replacements:
        bg = rep.get("background", "")
        img_path = rep.get("imagePath", "")
        matched = am.find_for_bg(bg)
        if not matched:
            errors.append({"background": bg, "error": "no matching texture"})
            continue
        if not Path(img_path).is_file():
            errors.append({"background": bg, "error": "image not found"})
            continue
        try:
            pil = Image.open(img_path)
        except Exception as e:  # noqa: BLE001
            errors.append({"background": bg, "error": f"open failed: {e}"})
            continue
        need_w, need_h = required_size(bg)
        if bg in EXACT_ASSET_FILE:
            if (pil.width, pil.height) != (need_w, need_h):
                errors.append({"background": bg, "error": f"must be exactly {need_w}x{need_h}"})
                continue
        elif pil.width < need_w or pil.height < need_h:
            errors.append({"background": bg, "error": f"must be at least {need_w}x{need_h}"})
            continue
        if am.import_image(matched, pil):
            applied.append(bg)
        else:
            errors.append({"background": bg, "error": "write failed"})

    saved, save_errors = am.save_modified()
    for se in save_errors:
        errors.append({"background": "*", "error": se})

    return {"applied": applied, "saved": len(saved), "errors": errors}


def copy_menu_backgrounds(old_data_dir: str, new_data_dir: str) -> dict:
    """Carry every currently-applied background texture from one install's
    Clone Hero_Data straight onto another's - used when installing a new
    version so it inherits whatever the previous default install was
    showing, custom or stock, without needing the original source images."""
    if not old_data_dir or not Path(old_data_dir).is_dir() or not Path(new_data_dir).is_dir():
        return {"copied": [], "errors": []}

    try:
        old_am = _get_manager(old_data_dir, refresh=True)
        new_am = _get_manager(new_data_dir, refresh=True)
        if not new_am.has_full_backup():
            new_am.create_backups()

        copied, errors = [], []
        for bg in BACKGROUNDS:
            old_matched = old_am.find_for_bg(bg)
            if not old_matched:
                continue
            img, err = old_am.export_image(old_matched)
            if img is None:
                continue
            new_matched = new_am.find_for_bg(bg)
            if not new_matched:
                continue
            if new_am.import_image(new_matched, img):
                copied.append(bg)
            else:
                errors.append({"background": bg, "error": "write failed"})

        saved, save_errors = new_am.save_modified()
        for se in save_errors:
            errors.append({"background": "*", "error": se})

        return {"copied": copied, "errors": errors}
    finally:
        # This is a one-shot background-carryover, not an interactive
        # CHMenuChanger session - release both handles immediately so the
        # install folders aren't left locked for the rest of the process.
        release(old_data_dir)
        release(new_data_dir)


def restore(body: dict) -> dict:
    data_dir = body.get("dataDir") or ""
    am = _get_manager(data_dir, refresh=True)
    restored, errors = am.restore_backups()
    _get_manager(data_dir, refresh=True)  # reload from restored files
    return {"restored": len(restored), "errors": errors}

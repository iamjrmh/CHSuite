"""
write_spec.py  --  writes CHSuite.spec to the current directory.
Called by build.bat during the build process.
All project files live in E:\\Downloads\\JURMR CHSuite
"""
import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve texture2ddecoder .pyd on the build machine.
# ---------------------------------------------------------------------------
try:
    import texture2ddecoder as _t2d
    _t2d_file = Path(_t2d.__file__)
    _t2d_binaries = [(str(_t2d_file), ".")]
    for ext in ("*.pyd", "*.dll"):
        for f in _t2d_file.parent.glob(ext):
            entry = (str(f), ".")
            if entry not in _t2d_binaries:
                _t2d_binaries.append(entry)
    _t2d_binaries_repr = repr(_t2d_binaries)
    print(f"  texture2ddecoder .pyd: {_t2d_file.name}")
except Exception as e:
    print(f"  WARNING: texture2ddecoder inspection failed: {e}")
    _t2d_binaries_repr = "[]"

# ---------------------------------------------------------------------------
# Same for etcpak
# ---------------------------------------------------------------------------
try:
    import etcpak as _etcpak
    _etcpak_file = Path(_etcpak.__file__)
    _etcpak_binaries = [(str(_etcpak_file), ".")]
    for ext in ("*.pyd", "*.dll"):
        for f in _etcpak_file.parent.glob(ext):
            entry = (str(f), ".")
            if entry not in _etcpak_binaries:
                _etcpak_binaries.append(entry)
    _etcpak_binaries_repr = repr(_etcpak_binaries)
    print(f"  etcpak .pyd:           {_etcpak_file.name}")
except Exception:
    _etcpak_binaries_repr = "[]"

# ---------------------------------------------------------------------------
# Images folder — bundle alongside the exe so NoteGen finds its templates
# ---------------------------------------------------------------------------
IMAGES_DIR = r"E:\Downloads\JURMR CHSuite\Images"
if os.path.isdir(IMAGES_DIR):
    images_datas = [(IMAGES_DIR, "Images")]
    print(f"  Images folder: {IMAGES_DIR}")
else:
    images_datas = []
    print(f"  WARNING: Images folder not found at {IMAGES_DIR!r} -- NoteGen templates won't be bundled.")

# ---------------------------------------------------------------------------
# Icon path  (update if your icon lives elsewhere)
# ---------------------------------------------------------------------------
ICON_PATH = r"E:\Downloads\JURMR CHSuite\JURMRWEED.ico"
if not os.path.isfile(ICON_PATH):
    print(f"  WARNING: icon not found at {ICON_PATH!r} -- building without icon.")
    icon_line = "    # icon not found at build time"
else:
    icon_line = f'    icon={ICON_PATH!r},'
    print(f"  Icon: {ICON_PATH}")

# ---------------------------------------------------------------------------
# Write the spec
# ---------------------------------------------------------------------------
spec = f"""# =============================================================================
#  CHSuite.spec  --  Production PyInstaller spec
#  Auto-generated  |  Targets: Windows x64, Python 3.11, UnityPy 1.25.0
# =============================================================================

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None


def _safe_collect(pkg):
    try:
        d, b, h = collect_all(pkg)
        return d, b, h
    except Exception:
        return [], [], []


# -- Collect all UnityPy pieces -----------------------------------------------
up_datas,     up_binaries,    up_hidden    = collect_all("UnityPy")

# -- Pillow image plugins ------------------------------------------------------
pil_datas,    pil_binaries,   pil_hidden   = collect_all("PIL")

# -- Compression backends ------------------------------------------------------
brotli_d,     brotli_b,       brotli_h     = _safe_collect("brotli")
brotlicffi_d, brotlicffi_b,  brotlicffi_h = _safe_collect("brotlicffi")
lz4_d,        lz4_b,          lz4_h        = _safe_collect("lz4")

# -- Native texture decoders via collect_all ----------------------------------
t2d_d,        t2d_b,          t2d_h        = _safe_collect("texture2ddecoder")
etcpak_d,     etcpak_b,       etcpak_h     = _safe_collect("etcpak")

# -- archspec: CPU detection library pulled in by etcpak ----------------------
archspec_d,   archspec_b,     archspec_h   = _safe_collect("archspec")

# -- fmod_toolkit + pyfmodex --------------------------------------------------
fmod_d,       fmod_b,         fmod_h       = _safe_collect("fmod_toolkit")
pyfmod_d,     pyfmod_b,       pyfmod_h     = _safe_collect("pyfmodex")

# -- Requests (used by Name Generator for update checks) ----------------------
req_d,        req_b,          req_h        = _safe_collect("requests")

# -- Discord Rich Presence ----------------------------------------------------
discord_d,    discord_b,      discord_h    = _safe_collect("pypresence")

# -- Explicit top-level .pyd copies -------------------------------------------
_t2d_forced    = {_t2d_binaries_repr}
_etcpak_forced = {_etcpak_binaries_repr}

# -- Images folder (NoteGen templates) — value baked in at spec-generation time
_images_datas_repr = {repr(images_datas)}

# -- Merge all collected pieces ------------------------------------------------
all_datas = (
    up_datas + pil_datas +
    brotli_d + brotlicffi_d + lz4_d +
    t2d_d + etcpak_d + archspec_d +
    fmod_d + pyfmod_d +
    req_d + discord_d +
    _images_datas_repr
)

all_binaries = (
    up_binaries + pil_binaries +
    brotli_b + brotlicffi_b + lz4_b +
    t2d_b + etcpak_b + archspec_b +
    fmod_b + pyfmod_b +
    req_b + discord_b +
    _t2d_forced +
    _etcpak_forced
)

all_hidden = list(set(
    up_hidden + pil_hidden +
    brotli_h + brotlicffi_h + lz4_h +
    t2d_h + etcpak_h + archspec_h +
    fmod_h + pyfmod_h +
    req_h +

    # UnityPy 1.25.0 full submodule tree
    collect_submodules("UnityPy") +
    collect_submodules("UnityPy.files") +
    collect_submodules("UnityPy.classes") +
    collect_submodules("UnityPy.streams") +
    collect_submodules("UnityPy.helpers") +
    collect_submodules("UnityPy.enums") +
    collect_submodules("UnityPy.tools") +
    collect_submodules("UnityPy.export") +
    collect_submodules("UnityPy.math") +
    collect_submodules("UnityPy.downloader") +
    collect_submodules("fmod_toolkit") +
    collect_submodules("pyfmodex") +

    # Pillow plugins
    collect_submodules("PIL") +

    # archspec (CPU detection, required by etcpak)
    collect_submodules("archspec") +
    collect_submodules("archspec.cpu") +

    # Requests + urllib3
    collect_submodules("requests") +
    collect_submodules("urllib3") +
    collect_submodules("certifi") +
    collect_submodules("charset_normalizer") +
    collect_submodules("idna") +

    # Discord Rich Presence
    collect_submodules("pypresence") +
    ["pypresence", "pypresence.presence", "pypresence.baseclient",
     "pypresence.exceptions", "pypresence.payloads", "pypresence.utils"] +

    # Compression
    [
        "brotli", "brotlicffi", "_brotli",
        "lz4", "lz4.block", "lz4.frame", "lz4.stream",
    ] +

    # Native decoders
    [
        "texture2ddecoder",
        "texture2ddecoder.texture2ddecoder",
        "etcpak",
    ] +

    # stdlib items PyInstaller sometimes misses
    [
        "ctypes", "ctypes.util", "ctypes.wintypes",
        "xml.etree.ElementTree",
        "logging",
        "logging.handlers",
        "importlib.metadata",
        "importlib.resources",
        "zlib", "_struct",
        "configparser",
        "shutil",
        "pathlib",
        "datetime",
        "threading",
        "platform",
        "tempfile",
        "re",
        "json",
        "copy",
        "colorsys",
        "math",
    ] +

    # tkinter
    [
        "tkinter", "tkinter.ttk",
        "tkinter.filedialog", "tkinter.messagebox",
        "tkinter.simpledialog", "tkinter.colorchooser",
        "tkinter.scrolledtext", "_tkinter",
    ]
))

a = Analysis(
    ["CHSuite.py"],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=["rthook_texture2d.py"],
    excludes=[
        "setuptools",
        "setuptools.logging",
        "test", "unittest",
        "IPython", "jupyter", "notebook",
        # matplotlib excluded: its typing.py shadows stdlib typing in frozen
        # exes and causes a circular-import crash at startup.
        # Color math is handled by pure-Python helpers in CHSuite.py instead.
        "matplotlib", "matplotlib.backends", "matplotlib.testing",
        "numpy", "scipy", "pandas",
        "PyQt5", "PyQt6", "wx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CHSuite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
{icon_line}
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CHSuite",
)
"""

with open("CHSuite.spec", "w", encoding="utf-8") as f:
    f.write(spec.lstrip())

print("  Spec file written: CHSuite.spec")

"""
write_spec.py  --  writes CHSuite.spec to the current directory.
Called by build.bat (Windows), build.sh (Linux), or build_mac.sh (macOS).

Windows project root : E:\\Downloads\\JURMR CHSuite
Linux project root   : ~/Documents/Clone Hero  (or any directory)
macOS project root   : any directory (resolved relative to CWD)

Produces two executables inside dist/CHSuite/ sharing one _internal folder:
  CHSuite.exe / CHSuite   -- the main app
  ThemeGen.exe / ThemeGen -- the live theme designer (hidden, launched by CHSuite)
"""
import sys
import os
from pathlib import Path

_IS_LINUX = sys.platform.startswith("linux")
_IS_WIN   = sys.platform == "win32"
_IS_MAC   = sys.platform == "darwin"

# ---------------------------------------------------------------------------
# Resolve texture2ddecoder .pyd/.so on the build machine.
# ---------------------------------------------------------------------------
try:
    import texture2ddecoder as _t2d
    _t2d_file = Path(_t2d.__file__)
    _t2d_binaries = [(str(_t2d_file), ".")]
    for ext in ("*.pyd", "*.dll", "*.so", "*.dylib"):
        for f in _t2d_file.parent.glob(ext):
            entry = (str(f), ".")
            if entry not in _t2d_binaries:
                _t2d_binaries.append(entry)
    _t2d_binaries_repr = repr(_t2d_binaries)
    print(f"  texture2ddecoder: {_t2d_file.name}")
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
    for ext in ("*.pyd", "*.dll", "*.so", "*.dylib"):
        for f in _etcpak_file.parent.glob(ext):
            entry = (str(f), ".")
            if entry not in _etcpak_binaries:
                _etcpak_binaries.append(entry)
    _etcpak_binaries_repr = repr(_etcpak_binaries)
    print(f"  etcpak:           {_etcpak_file.name}")
except Exception:
    _etcpak_binaries_repr = "[]"

# ---------------------------------------------------------------------------
# base64.txt — embedded icon / font data used by load_base64() at runtime.
# Destination "." places it directly in _internal/ (sys._MEIPASS) so the
# frozen load_base64() function finds it via sys._MEIPASS/base64.txt.
# ---------------------------------------------------------------------------
BASE64_FILE = str(Path.cwd() / "base64.txt")
if os.path.isfile(BASE64_FILE):
    base64_datas = [(BASE64_FILE, ".")]
    print(f"  base64.txt: {BASE64_FILE}")
else:
    base64_datas = []
    print(f"  WARNING: base64.txt not found at {BASE64_FILE!r} -- embedded icons/fonts will fail at runtime.")

# ---------------------------------------------------------------------------
# Images folder — bundle alongside the exe so NoteGen finds its templates
# ---------------------------------------------------------------------------
if _IS_WIN:
    IMAGES_DIR = r"E:\Downloads\JURMR CHSuite\Images"
else:
    # Images live inside _internal/Images relative to the project root
    IMAGES_DIR = str(Path.cwd() / "_internal" / "Images")

if os.path.isdir(IMAGES_DIR):
    images_datas = [(IMAGES_DIR, "Images")]
    print(f"  Images folder: {IMAGES_DIR}")
else:
    images_datas = []
    print(f"  WARNING: Images folder not found at {IMAGES_DIR!r} -- NoteGen templates won't be bundled.")

# ---------------------------------------------------------------------------
# Themes folder — ship all built-in themes with the app
# ---------------------------------------------------------------------------
THEMES_DIR = str(Path.cwd() / "themes")
if os.path.isdir(THEMES_DIR):
    themes_datas = [(THEMES_DIR, "themes")]
    print(f"  themes folder: {THEMES_DIR}")
else:
    themes_datas = []
    print(f"  WARNING: themes/ not found at {THEMES_DIR!r} -- theme picker will be empty.")

# ---------------------------------------------------------------------------
# Icon path
#   Windows : .ico
#   macOS   : .icns (preferred) → .png fallback → None
#             build_mac.sh converts JURMRWEED.png → JURMRWEED.icns before
#             calling this script, so .icns should always be present.
#   Linux   : no icon in spec (handled by .desktop + .png in AppImage)
# ---------------------------------------------------------------------------
if _IS_WIN:
    ICON_PATH = r"JURMRWEED.ico"
    if not os.path.isfile(ICON_PATH):
        print(f"  WARNING: icon not found at {ICON_PATH!r} -- building without icon.")
        icon_line_exe    = "    # icon not found at build time"
        icon_line_bundle = "    icon=None,"
    else:
        icon_line_exe    = f"    icon={ICON_PATH!r},"
        icon_line_bundle = f"    icon={ICON_PATH!r},"
        print(f"  Icon: {ICON_PATH}")

elif _IS_MAC:
    # Prefer .icns (created by build_mac.sh), fall back to .png, then nothing
    _icns = Path.cwd() / "JURMRWEED.icns"
    _png  = Path.cwd() / "JURMRWEED.png"
    if _icns.exists():
        MAC_ICON = str(_icns)
        print(f"  Icon: {MAC_ICON}  (.icns)")
    elif _png.exists():
        MAC_ICON = str(_png)
        print(f"  Icon: {MAC_ICON}  (.png fallback — .icns preferred)")
    else:
        MAC_ICON = None
        print("  Icon: not found (JURMRWEED.icns / JURMRWEED.png missing)")
    icon_line_exe    = f"    icon={MAC_ICON!r},"
    icon_line_bundle = f"    icon={MAC_ICON!r},"

else:  # Linux
    icon_line_exe    = "    # icon: set via .desktop file on Linux"
    icon_line_bundle = "    icon=None,"
    print("  Icon: skipped on Linux (handled by .desktop + .png in AppImage)")

# ---------------------------------------------------------------------------
# Write the spec
# ---------------------------------------------------------------------------
spec = f"""# =============================================================================
#  CHSuite.spec  --  Production PyInstaller spec
#  Auto-generated  |  Targets: Windows x64 / Linux / macOS, Python 3.11
#
#  Produces two executables in dist/CHSuite/ sharing one _internal folder:
#    CHSuite[.exe]   -- main application
#    ThemeGen[.exe]  -- live theme designer (hidden, launched by CHSuite)
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

# -- Explicit top-level native copies -----------------------------------------
_t2d_forced    = {_t2d_binaries_repr}
_etcpak_forced = {_etcpak_binaries_repr}

# -- base64.txt (embedded icon / font data) — baked in at spec-generation time
_base64_datas_repr = {repr(base64_datas)}

# -- Images folder (NoteGen templates) ----------------------------------------
_images_datas_repr = {repr(images_datas)}

# -- Themes folder (built-in theme picker themes) -----------------------------
_themes_datas_repr = {repr(themes_datas)}

# -- Merge all collected pieces ------------------------------------------------
all_datas = (
    up_datas + pil_datas +
    brotli_d + brotlicffi_d + lz4_d +
    t2d_d + etcpak_d + archspec_d +
    fmod_d + pyfmod_d +
    req_d + discord_d +
    _base64_datas_repr +
    _images_datas_repr +
    _themes_datas_repr
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
        "ctypes", "ctypes.util",
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

# =============================================================================
#  Analysis 1 — CHSuite (main application)
# =============================================================================
a = Analysis(
    ["CHSuite.py"],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=["rthook_texture2d_mac.py"],
    excludes=[
        "setuptools",
        "setuptools.logging",
        "test", "unittest",
        "IPython", "jupyter", "notebook",
        # matplotlib excluded: its typing.py shadows stdlib typing in frozen
        # exes and causes a circular-import crash at startup.
        "matplotlib", "matplotlib.backends", "matplotlib.testing",
        "numpy", "scipy", "pandas",
        "PyQt5", "PyQt6", "wx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# =============================================================================
#  Analysis 2 — ThemeGen (live theme designer, launched as hidden executable)
# =============================================================================
a_tg = Analysis(
    ["ThemeGen.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "tkinter", "tkinter.colorchooser", "tkinter.filedialog",
        "tkinter.messagebox", "_tkinter",
        "json", "os", "socket", "struct", "subprocess",
        "sys", "threading", "time", "pathlib",
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        "setuptools", "test", "unittest",
        "numpy", "scipy", "pandas",
        "PIL", "UnityPy",
        "PyQt5", "PyQt6", "wx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Share modules between the two analyses so _internal isn't duplicated
MERGE((a, "CHSuite", "CHSuite"), (a_tg, "ThemeGen", "ThemeGen"))

# =============================================================================
#  macOS crash fix: strip astc_encoder/enum.py from the frozen archive
# =============================================================================
# astc_encoder (pulled in by UnityPy) ships a file called enum.py that
# re-exports IntEnum / IntFlag from the stdlib.  Inside a frozen macOS .app
# the PyInstaller frozen importer resolves the bare name 'enum' to THIS file
# instead of the real stdlib enum, causing a circular import that crashes
# the app during PyInstaller's own bootstrap hooks before any user code runs.
#
# Removing it from a.pure is safe: it is only a thin re-export shim.
# After removal 'import enum' resolves to the real stdlib correctly, and
# 'from astc_encoder import ...' still works via the native extension.
import sys as _pyi_sys
if _pyi_sys.platform == "darwin":
    a.pure = [e for e in a.pure if e[0] != 'astc_encoder.enum']

# =============================================================================
#  PYZ archives
# =============================================================================
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
pyz_tg = PYZ(a_tg.pure, a_tg.zipped_data, cipher=block_cipher)

# =============================================================================
#  EXE 1 — CHSuite[.exe]
# =============================================================================
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
{icon_line_exe}
)

# =============================================================================
#  EXE 2 — ThemeGen[.exe]  (placed alongside CHSuite in dist/CHSuite/)
# =============================================================================
exe_tg = EXE(
    pyz_tg,
    a_tg.scripts,
    [],
    exclude_binaries=True,
    name="ThemeGen",
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
{icon_line_exe}
)

# =============================================================================
#  COLLECT — one output folder containing both executables + shared _internal
# =============================================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    exe_tg,
    a_tg.binaries,
    a_tg.zipfiles,
    a_tg.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CHSuite",
)
"""

with open("CHSuite.spec", "w", encoding="utf-8") as f:
    f.write(spec.lstrip())

print("  Spec file written: CHSuite.spec  (CHSuite + ThemeGen)")

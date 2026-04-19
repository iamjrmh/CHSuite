#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
#  CHSuite — macOS Automated Build Script
#  Produces:
#    dist/CHSuite.app      — runnable app bundle
#    dist/CHSuiteMac.dmg   — drag-to-install disk image
#    dist/CHSuiteMac.pkg   — flat installer package
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " ============================================================="
echo "  CHSuite -- Automated macOS Build Script"
echo " ============================================================="
echo ""

# ── Sanity checks ─────────────────────────────────────────────────────────────
for f in CHSuite.py write_spec_mac.py ThemeGen.py rthook_texture2d_mac.py; do
    if [[ ! -f "$f" ]]; then
        echo " [ERROR] $f not found in this folder."
        exit 1
    fi
done

if [[ ! -d "themes" ]]; then
    echo " [WARNING] themes/ folder not found -- the theme picker will show no themes."
fi

# ── [1/8] Convert icon to .icns ───────────────────────────────────────────────
# macOS app bundles require .icns format.  We generate it from JURMRWEED.png
# (preferred) or JURMRWEED.ico using Pillow + LANCZOS resampling, which
# produces sharper results than sips at every icon size.
# iconutil (built into macOS) assembles the final .icns from the iconset.
echo " [1/8] Preparing app icon..."

ICNS_OUT="JURMRWEED.icns"

# Shared Pillow-based iconset generator — called with the source PNG path.
# Uses LANCZOS (high-quality Sinc filter) to downsample each required size,
# preserving alpha channel throughout.  Falls back to BICUBIC if Pillow is
# unexpectedly old, but Pillow 9+ (bundled in step 4) always has LANCZOS.
_make_iconset_py() {
    local SRC="$1"
    local ICONSET_DIR="$2"
    python3 - "$SRC" "$ICONSET_DIR" <<'PYEOF'
import sys
from pathlib import Path
from PIL import Image

src_path     = sys.argv[1]
iconset_dir  = Path(sys.argv[2])
iconset_dir.mkdir(parents=True, exist_ok=True)

src = Image.open(src_path).convert("RGBA")
src_w, src_h = src.size
print(f"  Source image: {src_w}×{src_h}")

# All required .icns sizes: (filename, pixel_width, pixel_height)
SIZES = [
    ("icon_16x16.png",       16,   16),
    ("icon_16x16@2x.png",    32,   32),
    ("icon_32x32.png",       32,   32),
    ("icon_32x32@2x.png",    64,   64),
    ("icon_128x128.png",    128,  128),
    ("icon_128x128@2x.png", 256,  256),
    ("icon_256x256.png",    256,  256),
    ("icon_256x256@2x.png", 512,  512),
    ("icon_512x512.png",    512,  512),
    ("icon_512x512@2x.png",1024, 1024),
]

resample = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", Image.BICUBIC))

for fname, w, h in SIZES:
    # Always resample from the full-resolution source so each size is as
    # sharp as the source allows — never resample a previously shrunk copy.
    resized = src.resize((w, h), resample)
    out = iconset_dir / fname
    resized.save(str(out), "PNG", optimize=True)

print(f"  Generated {len(SIZES)} iconset sizes using LANCZOS resampling.")
PYEOF
}

if [[ -f "JURMRWEED.icns" ]]; then
    echo " JURMRWEED.icns already exists -- skipping conversion."

elif [[ -f "JURMRWEED.png" ]]; then
    echo " Converting JURMRWEED.png → JURMRWEED.icns (Pillow LANCZOS)..."
    python3 -m pip install --quiet Pillow 2>/dev/null || true
    ICONSET_DIR="JURMRWEED.iconset"
    _make_iconset_py "JURMRWEED.png" "$ICONSET_DIR"
    if [[ $? -ne 0 ]]; then
        echo " [WARNING] Icon generation failed -- app will use a generic icon."
        ICNS_OUT=""
    else
        iconutil -c icns "$ICONSET_DIR" -o "$ICNS_OUT"
        rm -rf "$ICONSET_DIR"
        echo " Created: $ICNS_OUT"
    fi

elif [[ -f "JURMRWEED.ico" ]]; then
    echo " Converting JURMRWEED.ico → JURMRWEED.icns (Pillow LANCZOS)..."
    python3 -m pip install --quiet Pillow 2>/dev/null || true

    # Extract the largest frame from the .ico as a temporary PNG, then
    # feed that PNG through the same high-quality iconset generator above.
    python3 - <<'PYEOF'
from PIL import Image
import sys

ico = Image.open("JURMRWEED.ico")

# Collect every frame; pick the largest by pixel area
frames = []
try:
    while True:
        frames.append((ico.size[0] * ico.size[1], ico.size, ico.copy().convert("RGBA")))
        ico.seek(ico.tell() + 1)
except EOFError:
    pass

if not frames:
    print("  [ERROR] Could not read any frames from JURMRWEED.ico")
    sys.exit(1)

frames.sort(key=lambda x: x[0], reverse=True)
best = frames[0][2]
best.save("_icon_source.png", "PNG")
print(f"  Extracted largest frame: {frames[0][1][0]}×{frames[0][1][1]} px")
PYEOF

    if [[ ! -f "_icon_source.png" ]]; then
        echo " [WARNING] Icon frame extraction failed -- skipping icon."
        ICNS_OUT=""
    else
        ICONSET_DIR="JURMRWEED.iconset"
        _make_iconset_py "_icon_source.png" "$ICONSET_DIR"
        if [[ $? -ne 0 ]]; then
            echo " [WARNING] Iconset generation failed -- app will use a generic icon."
            ICNS_OUT=""
        else
            iconutil -c icns "$ICONSET_DIR" -o "$ICNS_OUT"
            rm -rf "$ICONSET_DIR" _icon_source.png
            echo " Created: $ICNS_OUT"
        fi
    fi

else
    echo " [WARNING] No icon file found (JURMRWEED.png or JURMRWEED.ico)."
    echo "           App bundle will have a generic icon."
    ICNS_OUT=""
fi
echo ""

# ── [2/8] Locate Python 3.11 ──────────────────────────────────────────────────
echo " [2/8] Locating Python 3.11..."
PYTHON=""

for candidate in \
    "$(command -v python3.11 2>/dev/null)" \
    "/usr/local/bin/python3.11" \
    "/opt/homebrew/bin/python3.11" \
    "/usr/bin/python3.11"; do
    if [[ -x "$candidate" ]] && "$candidate" --version 2>&1 | grep -q "3\.11"; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo " [ERROR] Python 3.11 not found."
    echo " Install via Homebrew:  brew install python@3.11"
    echo " Or download from:      https://www.python.org/downloads/release/python-3119/"
    exit 1
fi

echo " Found: $PYTHON"
"$PYTHON" --version
echo ""

# ── [3/8] Create virtual environment ──────────────────────────────────────────
echo " [3/8] Setting up virtual environment (.venv)..."
if [[ -d ".venv" ]]; then
    echo " .venv already exists -- skipping creation."
else
    "$PYTHON" -m venv .venv
    echo " .venv created."
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"
echo " Activated: $VIRTUAL_ENV"
echo ""

# ── [4/8] Install dependencies ─────────────────────────────────────────────────
echo " [4/8] Installing dependencies..."

python -m pip install --upgrade pip setuptools wheel

pip install "Pillow==10.4.0"
pip install "UnityPy==1.25.0"
pip install brotli brotlicffi lz4 texture2ddecoder
pip install requests
pip install pypresence
pip install "pyinstaller==6.10.0"

echo ""
echo " All dependencies installed."
echo ""

# ── [5/8] Verify critical imports ──────────────────────────────────────────────
echo " [5/8] Verifying critical imports..."

python -c "import UnityPy; print('  UnityPy          OK  v' + UnityPy.__version__)"
python -c "import texture2ddecoder; print('  texture2ddecoder OK')"
python -c "import lz4.block; print('  lz4.block        OK')"
python -c "from PIL import Image; print('  Pillow           OK  v' + Image.__version__)"
python -c "import requests; print('  requests         OK  v' + requests.__version__)"
python -c "import pypresence; print('  pypresence       OK  v' + pypresence.__version__)"
echo ""

# ── [6/8] Write spec file + inject macOS BUNDLE ───────────────────────────────
echo " [6/8] Writing CHSuite.spec..."
python write_spec_mac.py
if [[ ! -f "CHSuite.spec" ]]; then
    echo " [ERROR] CHSuite.spec was not created."
    exit 1
fi

# write_spec.py generates a COLLECT-only spec (shared with Linux/Windows).
# On macOS, PyInstaller needs a BUNDLE() directive to produce a proper
# .app bundle.  We inject it here if not already present.
ICNS_ABS=""
if [[ -n "$ICNS_OUT" && -f "$ICNS_OUT" ]]; then
    ICNS_ABS="$(cd "$(dirname "$ICNS_OUT")" && pwd)/$(basename "$ICNS_OUT")"
fi

python3 - "$ICNS_ABS" <<'PYEOF'
import re, sys

icon_path = sys.argv[1] if len(sys.argv) > 1 else ""
icon_value = repr(icon_path) if icon_path else "None"

with open("CHSuite.spec", "r") as f:
    content = f.read()

if "BUNDLE(" in content:
    print("  BUNDLE already present in CHSuite.spec -- nothing to inject.")
    sys.exit(0)

# Locate the variable assigned by the COLLECT() call
m = re.search(r'^(\w+)\s*=\s*COLLECT\s*\(', content, re.MULTILINE)
if not m:
    print("  [ERROR] Could not find a COLLECT(...) block in CHSuite.spec.")
    sys.exit(1)

coll_var = m.group(1)
bundle_block = f"""
# ── macOS app bundle (injected by build_mac.sh) ──────────────────────────────
app = BUNDLE(
    {coll_var},
    name='CHSuite.app',
    icon={icon_value},
    bundle_identifier='com.jurmr.chsuite',
    info_plist={{
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '6.1',
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'NSHumanReadableCopyright': 'JURMR',
    }},
)
"""

with open("CHSuite.spec", "w") as f:
    f.write(content + bundle_block)

icon_display = icon_path if icon_path else "none (generic icon)"
print(f"  Injected BUNDLE (wrapping '{coll_var}', icon={icon_display}).")
PYEOF

if [[ $? -ne 0 ]]; then
    echo " [ERROR] Failed to inject BUNDLE into CHSuite.spec."
    exit 1
fi
echo ""

# ── [7/8] Clean old build artifacts ────────────────────────────────────────────
echo " [7/8] Cleaning previous build and dist folders..."

pkill -x "CHSuite"  2>/dev/null || true
pkill -x "ThemeGen" 2>/dev/null || true
sleep 1

[[ -d "build" ]] && rm -rf "build" && echo " Removed: build/"
[[ -d "dist"  ]] && rm -rf "dist"  && echo " Removed: dist/"
echo ""

# ── [8/8] Run PyInstaller ──────────────────────────────────────────────────────
echo " [8/8] Running PyInstaller (takes 1-3 minutes)..."
echo " ---------------------------------------------------------"
echo ""

pyinstaller --noconfirm CHSuite.spec

APP_BUNDLE="dist/CHSuite.app"
if [[ ! -d "$APP_BUNDLE" ]]; then
    echo ""
    echo " [ERROR] PyInstaller did not produce dist/CHSuite.app"
    echo " Read the output above for details."
    exit 1
fi

# ── Copy icon into the bundle Resources (belt-and-suspenders) ─────────────────
if [[ -n "$ICNS_OUT" && -f "$ICNS_OUT" ]]; then
    cp "$ICNS_OUT" "$APP_BUNDLE/Contents/Resources/JURMRWEED.icns"
    echo " Icon copied into bundle Resources."
fi

# ── Copy themes/ into app bundle Resources ────────────────────────────────────
echo " Copying themes/ into app bundle Resources..."
THEMES_SRC=""
[[ -d "themes" ]] && THEMES_SRC="themes"
if [[ -n "$THEMES_SRC" ]]; then
    cp -R "$THEMES_SRC" "$APP_BUNDLE/Contents/Resources/themes"
    echo " themes/ copied → Contents/Resources/themes/"
else
    echo " [WARNING] themes/ not found -- skipping."
fi
echo ""

# ── Copy Images/ into app bundle Resources ────────────────────────────────────
echo " Copying Images/ into app bundle Resources..."
IMAGES_SRC=""
[[ -d "_internal/Images" ]] && IMAGES_SRC="_internal/Images"
[[ -d "Images"           ]] && IMAGES_SRC="Images"
if [[ -n "$IMAGES_SRC" ]]; then
    cp -R "$IMAGES_SRC" "$APP_BUNDLE/Contents/Resources/Images"
    echo " Images/ copied → Contents/Resources/Images/"
else
    echo " [WARNING] Images/ not found (checked _internal/Images and Images/) -- NoteGen templates won't load."
fi
echo ""

# ── Hide ThemeGen inside the bundle ───────────────────────────────────────────
THEMEGEN_SRC="$APP_BUNDLE/Contents/MacOS/ThemeGen"
THEMEGEN_DST="$APP_BUNDLE/Contents/MacOS/.ThemeGen"
if [[ -f "$THEMEGEN_SRC" ]]; then
    mv "$THEMEGEN_SRC" "$THEMEGEN_DST"
    echo " Moved ThemeGen to .ThemeGen (hidden on macOS)."
else
    echo " [WARNING] ThemeGen not found inside bundle -- skipping."
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════════
#  Create .pkg FIRST (before .dmg so dist/ only has the .app)
# ══════════════════════════════════════════════════════════════════════════════
echo " Creating dist/CHSuiteMac.pkg..."

PKG_OUT="dist/CHSuiteMac.pkg"
[[ -f "$PKG_OUT" ]] && rm -f "$PKG_OUT"

if command -v pkgbuild &>/dev/null; then
    PKG_STAGE="$(mktemp -d)"
    cp -R "$APP_BUNDLE" "$PKG_STAGE/"

    pkgbuild \
        --root "$PKG_STAGE" \
        --install-location "/Applications" \
        --identifier "com.jurmr.chsuite" \
        --version "6.1" \
        "$PKG_OUT"

    rm -rf "$PKG_STAGE"
    echo " Created: $PKG_OUT"
else
    echo " [WARNING] pkgbuild not found -- skipping .pkg."
    echo "           Install Xcode Command Line Tools: xcode-select --install"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════════
#  Create .dmg  (drag-to-install disk image)
# ══════════════════════════════════════════════════════════════════════════════
echo " Creating dist/CHSuiteMac.dmg..."

DMG_OUT="dist/CHSuiteMac.dmg"
[[ -f "$DMG_OUT" ]] && rm -f "$DMG_OUT"

if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "CHSuite" \
        --window-size 540 380 \
        --icon-size 128 \
        --icon "CHSuite.app" 140 190 \
        --hide-extension "CHSuite.app" \
        --app-drop-link 400 190 \
        "$DMG_OUT" \
        "dist/"
    echo " Created (create-dmg): $DMG_OUT"
else
    TMP_DMG_DIR="$(mktemp -d)"
    cp -R "$APP_BUNDLE" "$TMP_DMG_DIR/"
    ln -s /Applications "$TMP_DMG_DIR/Applications"

    hdiutil create \
        -volname "CHSuite" \
        -srcfolder "$TMP_DMG_DIR" \
        -ov -format UDZO \
        "$DMG_OUT"
    rm -rf "$TMP_DMG_DIR"
    echo " Created (hdiutil): $DMG_OUT"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════════
#  Done
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo " ============================================================="
echo "  BUILD SUCCESSFUL"
echo " ============================================================="
echo ""
echo "  App bundle : dist/CHSuite.app"
echo "  DMG        : dist/CHSuiteMac.dmg   (drag-to-install)"
echo "  PKG        : dist/CHSuiteMac.pkg   (silent/enterprise install)"
echo ""
echo "  Distribute the .dmg for end-users (drag CHSuite → Applications)."
echo "  Use the .pkg for scripted/enterprise deployment."
echo ""
echo "  NOTE: Run this script as a normal user, NOT with sudo."
echo "        sudo causes PyInstaller deprecation warnings and pip cache errors."
echo ""
echo "  To test now:"
echo "    open dist/CHSuite.app"
echo ""

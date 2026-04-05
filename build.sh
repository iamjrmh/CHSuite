#!/usr/bin/env bash
# =============================================================================
#  build.sh  —  Linux build script for CHSuite
#  Counterpart to build.bat (Windows).
#
#  Produces:
#    dist/CHSuite/CHSuite          (plain PyInstaller bundle, runnable as-is)
#    CHSuiteLinux.zip              (zip of full bundle including themes + Images)
#    CHSuiteLinux.AppImage         (self-contained portable AppImage)
#
#  Requirements:
#    • Python 3.11   (python3.11 or python3 resolving to 3.11)
#    • appimagetool  (downloaded automatically if not found in PATH)
#    • Standard Linux tools: wget/curl, chmod, cp, find
#
#  Typical usage:
#    cd ~/Documents/"Clone Hero"
#    bash build.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "  $1"; }
ok()    { echo -e "  ${GRN}✔${NC}  $1"; }
warn()  { echo -e "  ${YEL}⚠${NC}  $1"; }
fail()  { echo -e "  ${RED}✘${NC}  $1"; exit 1; }

echo
echo " ============================================================="
echo "  CHSuite — Linux Automated Build Script"
echo " ============================================================="
echo

# ── [1/8] Sanity checks ───────────────────────────────────────────────────────
info "[1/8] Sanity checks…"

[[ -f "CHSuite.py"          ]] || fail "CHSuite.py not found. Run build.sh from the project root."
[[ -f "ThemeGen.py"         ]] || fail "ThemeGen.py not found."
[[ -f "write_spec.py"       ]] || fail "write_spec.py not found."
[[ -f "rthook_texture2d.py" ]] || fail "rthook_texture2d.py not found."

if [[ ! -d "themes" ]]; then
    warn "themes/ folder not found — users will see no themes at runtime."
fi

ok "All required source files present."
echo

# ── [2/8] Locate Python 3.11 ──────────────────────────────────────────────────
info "[2/8] Locating Python 3.11…"

PYTHON=""
for candidate in python3.11 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        VER=$("$candidate" -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
        if [[ "$VER" == "(3, 11)" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    fail "Python 3.11 not found.\nInstall with: sudo apt install python3.11 python3.11-venv"
fi

ok "Found: $PYTHON ($($PYTHON --version))"
echo

# ── [3/8] Virtual environment ─────────────────────────────────────────────────
info "[3/8] Setting up virtual environment (.venv)…"

if [[ -d ".venv" ]]; then
    info ".venv already exists — skipping creation."
else
    "$PYTHON" -m venv .venv
    ok ".venv created."
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"
ok "Activated: $VIRTUAL_ENV"
echo

# ── [4/8] Install dependencies ────────────────────────────────────────────────
info "[4/8] Installing dependencies (this may take a minute)…"

python -m pip install --upgrade --quiet pip setuptools wheel
python -m pip install --quiet "Pillow==10.4.0"
python -m pip install --quiet "UnityPy==1.25.0"
python -m pip install --quiet brotli brotlicffi lz4 texture2ddecoder
python -m pip install --quiet requests pypresence
python -m pip install --quiet "pyinstaller==6.10.0"

ok "All dependencies installed."
echo

# ── [4b] Patch astc_encoder: rename enum.py to avoid shadowing stdlib enum ────
# astc_encoder ships a file called enum.py which PyInstaller places inside
# _internal/.  Because _internal/ lands on sys.path at runtime, Python finds
# astc_encoder/enum.py instead of the stdlib enum module, causing a
# circular-import crash before any user code even runs.
# Fix: rename the file to _astc_enum.py and rewrite internal imports to match.
info "[4b] Patching astc_encoder/enum.py (stdlib shadow fix)…"

ASTC_DIR=$(python -c "import astc_encoder, os; print(os.path.dirname(astc_encoder.__file__))" 2>/dev/null || true)

if [[ -n "$ASTC_DIR" && -f "$ASTC_DIR/enum.py" ]]; then
    # Move the file so it no longer shadows stdlib enum
    cp "$ASTC_DIR/enum.py" "$ASTC_DIR/_astc_enum.py"
    rm "$ASTC_DIR/enum.py"

    # Rewrite every .py in the package that references the old name
    for pyfile in "$ASTC_DIR"/*.py; do
        sed -i \
            's/from \.enum import/from ._astc_enum import/g;
             s/from \.enum\b/from ._astc_enum/g;
             s/from astc_encoder\.enum import/from astc_encoder._astc_enum import/g;
             s/from astc_encoder\.enum\b/from astc_encoder._astc_enum/g;
             s/import astc_encoder\.enum\b/import astc_encoder._astc_enum/g' \
            "$pyfile"
    done

    ok "astc_encoder/enum.py → _astc_enum.py  (imports patched)"
else
    warn "astc_encoder/enum.py not found — no patching needed (already fixed or not installed)."
fi
echo

# ── [5/8] Verify critical imports ─────────────────────────────────────────────
info "[5/8] Verifying critical imports…"

python -c "import UnityPy;          print(f'  UnityPy          OK  v{UnityPy.__version__}')"
python -c "import texture2ddecoder; print('  texture2ddecoder OK')"
python -c "import lz4.block;        print('  lz4.block        OK')"
python -c "from PIL import Image;   print(f'  Pillow           OK  v{Image.__version__}')"
python -c "import requests;         print(f'  requests         OK  v{requests.__version__}')"
python -c "import pypresence;       print(f'  pypresence       OK  v{pypresence.__version__}')"

ok "All imports verified."
echo

# ── [6/8] Write spec ──────────────────────────────────────────────────────────
info "[6/8] Writing CHSuite.spec…"

python write_spec.py
[[ -f "CHSuite.spec" ]] || fail "CHSuite.spec was not created by write_spec.py."

ok "Spec written: CHSuite.spec"
echo

# ── [7/8] Clean + run PyInstaller ─────────────────────────────────────────────
info "[7/8] Running PyInstaller…"

rm -rf build dist
pyinstaller CHSuite.spec

ok "PyInstaller finished."
echo

# ── [7b] Stage assets into dist/CHSuite/ before packaging ────────────────────
info "[7b] Staging assets into dist/CHSuite/…"

# Mark ThemeGen non-executable so users can't launch it directly;
# CHSuite re-adds the execute bit at runtime when it needs to open it.
if [[ -f "dist/CHSuite/ThemeGen" ]]; then
    chmod a-x "dist/CHSuite/ThemeGen"
    ok "ThemeGen marked non-executable (launched only by CHSuite internally)."
fi

# Copy themes folder if present
if [[ -d "themes" ]]; then
    cp -r themes dist/CHSuite/themes
    ok "themes/ copied to dist/CHSuite/themes/"
else
    warn "themes/ not found — skipping."
fi

# Copy Images folder if present
if [[ -d "Images" ]]; then
    cp -r Images dist/CHSuite/Images
    ok "Images/ copied to dist/CHSuite/Images/"
else
    warn "Images/ not found — NoteGen templates will be missing."
fi

echo

# ── [7c] Package dist/CHSuite/ into CHSuiteLinux.zip ─────────────────────────
# Runs AFTER all assets are staged so themes/ and Images/ are included.
info "[7c] Creating CHSuiteLinux.zip from dist/CHSuite/…"

ZIP_OUT="$SCRIPT_DIR/CHSuiteLinux.zip"
rm -f "$ZIP_OUT"
(cd "$SCRIPT_DIR/dist/CHSuite" && zip -r "$ZIP_OUT" .)

if [[ -f "$ZIP_OUT" ]]; then
    ok "Zip created: $ZIP_OUT"
else
    warn "zip command ran but CHSuiteLinux.zip was not found — is 'zip' installed?"
fi
echo

# ── [8/8] Build AppImage ──────────────────────────────────────────────────────
info "[8/8] Building AppImage…"

# ── Locate or download appimagetool ──────────────────────────────────────────
APPIMAGETOOL=""
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="appimagetool"
else
    TOOL_PATH="$SCRIPT_DIR/.appimagetool"
    if [[ ! -f "$TOOL_PATH" ]]; then
        info "appimagetool not in PATH — downloading…"
        AITOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
        if command -v wget &>/dev/null; then
            wget -q -O "$TOOL_PATH" "$AITOOL_URL"
        elif command -v curl &>/dev/null; then
            curl -sSL -o "$TOOL_PATH" "$AITOOL_URL"
        else
            warn "Neither wget nor curl found — cannot download appimagetool."
            warn "Install it manually: https://github.com/AppImage/AppImageKit/releases"
            warn "Skipping AppImage creation. The dist/CHSuite/ folder is still usable."
            echo
            goto_done=1
        fi
        if [[ -z "${goto_done:-}" ]]; then
            chmod +x "$TOOL_PATH"
            ok "appimagetool downloaded."
        fi
    fi
    [[ -z "${goto_done:-}" ]] && APPIMAGETOOL="$TOOL_PATH"
fi

if [[ -n "$APPIMAGETOOL" ]]; then
    # ── Build the AppDir structure ────────────────────────────────────────────
    APPDIR="$SCRIPT_DIR/AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/applications"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

    # Copy the full PyInstaller bundle into AppDir/usr/bin/
    cp -r dist/CHSuite/* "$APPDIR/usr/bin/"

    # Make CHSuite executable (PyInstaller output should already be +x)
    chmod +x "$APPDIR/usr/bin/CHSuite"

    # AppRun entrypoint — launches CHSuite from its own directory so
    # relative paths (_internal, themes, Images) resolve correctly.
    cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/CHSuite" "$@"
APPRUN
    chmod +x "$APPDIR/AppRun"

    # .desktop file
    cat > "$APPDIR/usr/share/applications/chsuite.desktop" << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=CHSuite
Comment=All-in-one Clone Hero utility suite
Exec=CHSuite
Icon=chsuite
Categories=Game;Utility;
Terminal=false
DESKTOP
    # Symlink .desktop to AppDir root (required by AppImage spec)
    ln -sf usr/share/applications/chsuite.desktop "$APPDIR/chsuite.desktop"

    # Icon: use JURMRWEED.png if present, else create a placeholder 256×256
    PNG_SRC="$SCRIPT_DIR/JURMRWEED.png"
    ICON_DEST="$APPDIR/usr/share/icons/hicolor/256x256/apps/chsuite.png"
    if [[ -f "$PNG_SRC" ]]; then
        cp "$PNG_SRC" "$ICON_DEST"
    else
        warn "JURMRWEED.png not found — AppImage will use a blank icon."
        # Write a minimal 1×1 white PNG so appimagetool doesn't fail
        printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82' > "$ICON_DEST"
    fi
    # Symlink icon to AppDir root (required)
    ln -sf usr/share/icons/hicolor/256x256/apps/chsuite.png "$APPDIR/chsuite.png"

    # ── Run appimagetool ──────────────────────────────────────────────────────
    ARCH=x86_64
    OUTPUT="$SCRIPT_DIR/CHSuiteLinux.AppImage"
    ARCH=$ARCH "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

    if [[ -f "$OUTPUT" ]]; then
        chmod +x "$OUTPUT"
        ok "AppImage created: $OUTPUT"
        rm -rf "$APPDIR"
    else
        warn "appimagetool ran but output file not found — check the log above."
    fi
fi

echo
echo " ============================================================="
echo "  BUILD SUCCESSFUL"
echo " ============================================================="
echo
echo "  Portable bundle : dist/CHSuite/CHSuite"
echo "  Portable zip    : CHSuiteLinux.zip        ← distribute this"
if [[ -f "CHSuiteLinux.AppImage" ]]; then
echo "  AppImage        : CHSuiteLinux.AppImage   ← or distribute this"
fi
echo
echo "  The AppImage is fully self-contained."
echo "  The dist/CHSuite/ folder also works if you prefer the raw bundle."
echo
echo "  Typical Clone Hero install path on Linux:"
echo "    ~/Documents/Clone Hero/"
echo "  CHSuite will look for clonehero_Data inside that folder."
echo

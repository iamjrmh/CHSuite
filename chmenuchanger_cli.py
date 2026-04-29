#!/usr/bin/env python3
"""
CHMenuChanger CLI — Server-side background replacement for Clone Hero
========================================================================
Command-line tool to replace menu backgrounds in Clone Hero .assets files.
Used by GitHub Actions workflow for CHSuiteLite web interface.
"""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import UnityPy
except ImportError:
    print("ERROR: UnityPy is required. Install with: pip install UnityPy")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


# Constants from CHMenuChanger.py
BACKGROUNDS = [
    "Spray", "Pastel Burst", "Groovy", "Grains",
    "Blue Rays", "Alien", "Autumn", "Light", "Dark",
    "Classic", "Surfer", "SurferAlt", "Rainbow", "Animated",
    "Logo_Transparent",
]
EXACT_ASSET_FILE = {"Logo_Transparent": "globalgamemanagers.assets"}


def _norm(s):
    return re.sub(r"[\s_\-]", "", s).lower()


def required_size(name):
    return (2030, 1328) if name == "Logo_Transparent" else (1920, 1080)


class AssetManager:
    """Lightweight asset manager for CLI operations."""

    def __init__(self, data_dir):
        self.data_dir = str(data_dir)
        self._data = {}
        self._env_map = {}
        self._envs = {}
        self._dirty = set()
        self._scan()

    def _scan(self):
        data_dir = Path(self.data_dir)
        candidates = []
        for f in data_dir.iterdir():
            if not f.is_file():
                continue
            lo = f.name.lower()
            if f.suffix.lower() == ".assets":
                candidates.append(f)
            elif lo == "globalgamemanagers":
                candidates.append(f)

        def sort_key(p):
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

    def _load_file(self, fpath):
        key = str(fpath)
        if key in self._envs:
            return
        try:
            env = UnityPy.load(key)
            self._envs[key] = env
            for obj in env.objects:
                if obj.type.name == "Texture2D":
                    try:
                        d = obj.read()
                        n = getattr(d, "m_Name", None) or getattr(d, "name", None)
                        if n and n not in self._data:
                            self._data[n] = d
                            self._env_map[n] = (env, key)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[scan] skipped {Path(fpath).name}: {e}")

    def texture_names(self):
        return list(self._data.keys())

    def find_for_bg(self, bg):
        required_file = EXACT_ASSET_FILE.get(bg)
        if required_file:
            req_lo = required_file.lower()
            for name, (env, fpath) in self._env_map.items():
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

    def import_image(self, asset_name, pil):
        d = self._data.get(asset_name)
        if d is None:
            return False

        rgba = pil.convert("RGBA")

        try:
            if hasattr(d, "set_image"):
                d.set_image(rgba)
                d.save()
                self._dirty.add(asset_name)
                return True
        except Exception as e:
            print(f"[WRITE FAIL] set_image '{asset_name}': {e}")

        try:
            d.image = rgba
            d.save()
            self._dirty.add(asset_name)
            return True
        except Exception as e:
            print(f"[WRITE FAIL] image= setter '{asset_name}': {e}")

        # Fallback: force-convert to RGBA32
        try:
            from UnityPy.enums import TextureFormat as TF
            d.m_TextureFormat = TF.RGBA32
            if hasattr(d, "set_image"):
                d.set_image(rgba)
                d.save()
                self._dirty.add(asset_name)
                return True
            d.image = rgba
            d.save()
            self._dirty.add(asset_name)
            return True
        except Exception as e:
            print(f"[WRITE FAIL] force-RGBA32 '{asset_name}': {e}")
            return False

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
            fname = Path(fpath).name
            try:
                data = env.file.save()
                with open(fpath, "wb") as f:
                    f.write(data)
                saved.append(fpath)
            except Exception as e:
                errors.append(f"{fname}: {e}")

        return saved, errors


def main():
    parser = argparse.ArgumentParser(
        description="CHMenuChanger CLI - Replace Clone Hero menu backgrounds"
    )
    parser.add_argument(
        "-i", "--input-dir",
        required=True,
        help="Directory containing .assets files (e.g., sharedassets1.assets)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        required=True,
        help="Output directory for modified .assets files"
    )
    parser.add_argument(
        "-r", "--replacement",
        required=True,
        help="Path to replacement PNG/JPG image"
    )
    parser.add_argument(
        "-b", "--background",
        required=True,
        choices=BACKGROUNDS,
        help="Background name to replace"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    replacement_path = Path(args.replacement)

    # Validate input directory
    if not input_dir.is_dir():
        print(f"ERROR: Input directory not found: {input_dir}")
        sys.exit(1)

    # Validate replacement image
    if not replacement_path.is_file():
        print(f"ERROR: Replacement image not found: {replacement_path}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load replacement image and validate size
    try:
        repl_img = Image.open(replacement_path).convert("RGBA")
    except Exception as e:
        print(f"ERROR: Could not open replacement image: {e}")
        sys.exit(1)

    req_w, req_h = required_size(args.background)
    repl_w, repl_h = repl_img.size

    if args.background == "Logo_Transparent":
        if repl_w != req_w or repl_h != req_h:
            print(f"ERROR: Image must be exactly {req_w}x{req_h}, got {repl_w}x{repl_h}")
            sys.exit(1)
    else:
        if repl_w < req_w or repl_h < req_h:
            print(f"ERROR: Image must be at least {req_w}x{req_h}, got {repl_w}x{repl_h}")
            sys.exit(1)

    if args.verbose:
        print(f"Processing background: {args.background}")
        print(f"Replacement image: {repl_w}x{repl_h}")
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")

    # Initialize asset manager
    print("Scanning asset files...")
    am = AssetManager(input_dir)

    # Find the target texture
    asset_name = am.find_for_bg(args.background)
    if not asset_name:
        print(f"ERROR: Could not find texture for background '{args.background}'")
        print(f"Available textures: {', '.join(am.texture_names()[:20])}...")
        sys.exit(1)

    if args.verbose:
        print(f"Found texture: {asset_name}")

    # Import the replacement image
    print(f"Replacing {args.background} with {replacement_path}...")
    success = am.import_image(asset_name, repl_img)

    if not success:
        print("ERROR: Failed to import replacement image")
        sys.exit(1)

    # Save modified files
    print("Saving modified assets...")
    saved, errors = am.save_modified()

    if errors:
        print("Warnings during save:")
        for err in errors:
            print(f"  - {err}")

    if not saved:
        print("ERROR: No files were saved")
        sys.exit(1)

    # Copy modified files to output directory
    print("Copying to output directory...")
    for src_path in saved:
        src = Path(src_path)
        dst = output_dir / src.name
        # Read and write to ensure clean copy
        with open(src, "rb") as f:
            data = f.read()
        with open(dst, "wb") as f:
            f.write(data)
        if args.verbose:
            print(f"  Copied: {src.name}")

    print(f"SUCCESS: Modified files saved to {output_dir}")
    print(f"  Output files: {', '.join(f.name for f in output_dir.iterdir() if f.is_file())}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
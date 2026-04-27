# rthook_texture2d.py
# PyInstaller runtime hook -- runs before any user code.
#
# FIX (macOS crash): The previous version walked ALL subdirectories under
# _MEIPASS and added any dir containing a .so/.pyd to sys.path.  This
# accidentally put astc_encoder/ on sys.path, so Python found
# astc_encoder/enum.py before the real stdlib enum -- causing a circular
# import that crashes the app immediately on macOS.
#
# The rule now is: only add a directory to sys.path if it is NOT a Python
# package (i.e. does not contain __init__.py or __init__.pyc).  Package
# dirs are imported by their parent path entry, not by being path entries
# themselves.

import sys
import os
import ctypes

if getattr(sys, "frozen", False):
    base = sys._MEIPASS

    # ------------------------------------------------------------------
    # Step 1 -- collect native-extension dirs that are safe to add to
    # sys.path (not Python packages, so they can't shadow stdlib names).
    # ------------------------------------------------------------------
    native_dirs = set()
    native_dirs.add(base)   # _MEIPASS itself is always correct

    for root, dirs, files in os.walk(base):
        # ── KEY FIX ───────────────────────────────────────────────────
        # If this directory is a Python package it has an __init__ file.
        # Adding it to sys.path would let its internal modules (e.g.
        # astc_encoder/enum.py) shadow same-named stdlib modules.
        # Skip it; the package is importable via its *parent* on sys.path.
        if root != base:
            is_package = (
                "__init__.py"  in files or
                "__init__.pyc" in files or
                any(f.startswith("__init__") and f.endswith(".pyc")
                    for f in files)
            )
            if is_package:
                dirs.clear()   # don't recurse into sub-packages either
                continue

        for fname in files:
            if fname.lower().endswith((".pyd", ".so")):
                native_dirs.add(root)
                break

    # Add safe dirs to sys.path
    for d in native_dirs:
        if d not in sys.path:
            sys.path.insert(0, d)

    # Add to PATH for macOS/Linux dylib resolution
    existing_path = os.environ.get("PATH", "")
    extra_path = os.pathsep.join(
        d for d in native_dirs if d not in existing_path
    )
    if extra_path:
        os.environ["PATH"] = extra_path + os.pathsep + existing_path

    # ------------------------------------------------------------------
    # Step 2 -- pre-load fmod if present (Windows/Linux only; macOS
    # doesn't ship fmod.dll, it uses .dylib but UnityPy handles that)
    # ------------------------------------------------------------------
    for root, dirs, files in os.walk(base):
        for fname in files:
            if fname.lower() in ("fmod.dll", "libfmod.so", "libfmod.dylib"):
                fmod_path = os.path.join(root, fname)
                try:
                    ctypes.CDLL(fmod_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Step 3 -- force-load texture decoders via ctypes then import them
    # ------------------------------------------------------------------
    _targets = ("texture2ddecoder", "etcpak")
    for root, dirs, files in os.walk(base):
        for fname in files:
            if any(t in fname for t in _targets) and fname.endswith(
                (".pyd", ".so", ".dylib")
            ):
                fpath = os.path.join(root, fname)
                try:
                    ctypes.CDLL(fpath)
                except OSError:
                    pass

    try:
        import texture2ddecoder  # noqa
    except ImportError:
        pass

    try:
        import etcpak  # noqa
    except ImportError:
        pass

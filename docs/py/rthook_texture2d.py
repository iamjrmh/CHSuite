"""
rthook_texture2d.py — web stub for CHSuite Lite (Pyodide).
The original rthook is a PyInstaller runtime hook that loads native DLLs and .pyd
files before user code runs in a frozen executable.
In Pyodide (browser), native extension loading is handled by Pyodide itself —
this stub exists so the import succeeds without error.
"""

# No frozen-executable or DLL-loading logic needed in Pyodide.
# texture2ddecoder and etcpak are not available in Pyodide's package set;
# UnityPy's pure-Python fallbacks are used instead when available.

import sys as _sys

def _noop(*a, **k):
    pass

# Provide harmless stubs so any code that calls these doesn't crash
load_native_decoders = _noop
preload_fmod = _noop

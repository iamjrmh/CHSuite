"""
write_spec.py — web stub for CHSuite Lite (Pyodide).
The original write_spec.py generates a PyInstaller .spec file for desktop builds.
In the web version, this module is a no-op stub so imports succeed without error.
"""

# No filesystem or build-tool access in Pyodide — this is intentionally empty.

def write_spec(*args, **kwargs):
    """No-op: spec generation is not available in the browser."""
    return None

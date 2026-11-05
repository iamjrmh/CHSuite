"""CHPatcher "Fast boot": skip Clone Hero's per-.sng open on the cache read.

Why
---
When Clone Hero v1.1 loads ``songcache.bin`` at boot, the trusted-cache path
does this for every cached entry (reverse engineered from GameAssembly.dll,
v1.1.0.6142)::

    if (entry.isSng) { if (entry.Sng == null) <error> }   # OPENS the package
    AddSong(entry)                                         # pure in-memory
    if (entry.isSng && entry.Sng != null) entry.Sng.Close()

Folder songs never touch the disk there, but each ``.sng`` costs one or two
random seeks just to prove it opens. On a hard drive that is ~50 songs/sec,
i.e. ~25-30 minutes for an 80k ``.sng`` library, on every single boot. The
package is loaded lazily again when a song is previewed or played, so both
``isSng`` checks can become unconditional jumps (``je rel8`` -> ``jmp rel8``)
and the cache read finishes in seconds. Verified live: the last 19,784 songs
of a stuck boot loaded in under 2 seconds after the flip.

Surviving updates
-----------------
The two sites are found by byte signature, not a fixed address, and every
match is cross-checked (same ``isSng`` field offset, both ``get_Sng`` calls
hitting one function). If anything disagrees, nothing is patched. When the
GameAssembly.dll on disk is locked (the game is running) the running process
is patched in memory instead and the disk copy is fixed on the next launch.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import re
import shutil
import struct
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import config
from .errors import ApiError

log = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

DLL_NAME = "GameAssembly.dll"
BACKUP_SUFFIX = ".chsuite-fastboot.bak"
CONFIG_KEY = "fastboot_auto"

JE_SHORT = 0x74
JMP_SHORT = 0xEB
CALL_REL32 = 0xE8

MODULE_WAIT_SECONDS = 60.0
MODULE_POLL_SECONDS = 0.05


class FastBootError(Exception):
    """The signatures could not be matched safely; nothing may be patched."""


class State(Enum):
    ON = "on"
    OFF = "off"


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signature:
    name: str
    pattern: str
    patch_index: int
    """Offset of the je/jmp opcode byte that gets flipped."""
    field_index: int
    """Offset of the SongEntry.isSng field-offset byte in ``cmp byte [r13+X], 0``."""
    call_indices: tuple[int, ...]
    """Offsets of ``call SongEntry.get_Sng``; all must resolve to one target."""

    def regex(self) -> re.Pattern[bytes]:
        parts = []
        for i, tok in enumerate(self.pattern.split()):
            if i == self.patch_index:
                parts.append(b"[" + bytes([JE_SHORT, JMP_SHORT]) + b"]")
            elif tok == "??":
                parts.append(b".")
            else:
                parts.append(re.escape(bytes([int(tok, 16)])))
        return re.compile(b"".join(parts), re.DOTALL)


# test dil,dil / je / cmp byte [r13+isSng],0 / JE / xor edx,edx / mov rcx,r13 /
# call get_Sng / test rax,rax / je rel32
SIG_OPEN = Signature(
    name="open-check",
    pattern="40 84 FF 74 ?? 41 80 BD ?? 00 00 00 00 74 ?? 33 D2 49 8B CD E8 ?? ?? ?? ?? 48 85 C0 0F 84",
    patch_index=13,
    field_index=8,
    call_indices=(20,),
)

# cmp byte [r13+isSng],0 / JE / call get_Sng / test / je / call get_Sng /
# test / je rel32 / xor edx,edx / mov rcx,rax / call Sng.Close
SIG_CLOSE = Signature(
    name="close-check",
    pattern=(
        "41 80 BD ?? 00 00 00 00 74 ?? 33 D2 49 8B CD E8 ?? ?? ?? ?? 48 85 C0 74 ?? "
        "33 D2 49 8B CD E8 ?? ?? ?? ?? 48 85 C0 0F 84 ?? ?? ?? ?? 33 D2 48 8B C8 E8"
    ),
    patch_index=8,
    field_index=3,
    call_indices=(15, 30),
)

SIGNATURES = (SIG_OPEN, SIG_CLOSE)


@dataclass(frozen=True)
class Sites:
    offsets: tuple[int, ...]
    """Buffer offsets of the opcode bytes to flip, one per signature."""
    state: State


def _call_target(data: bytes, at: int) -> int:
    if data[at] != CALL_REL32:
        raise FastBootError(f"expected a call at +0x{at:x}")
    return at + 5 + struct.unpack_from("<i", data, at + 1)[0]


def find_sites(data: bytes) -> Sites:
    """Locate both patch sites in a file image or one mapped code section."""
    offsets: list[int] = []
    fields: set[int] = set()
    targets: set[int] = set()
    opcodes: set[int] = set()
    for sig in SIGNATURES:
        matches = [m.start() for m in sig.regex().finditer(data)]
        if len(matches) != 1:
            raise FastBootError(f"{sig.name}: expected 1 match, found {len(matches)}")
        start = matches[0]
        fields.add(data[start + sig.field_index])
        targets.update(_call_target(data, start + i) for i in sig.call_indices)
        offsets.append(start + sig.patch_index)
        opcodes.add(data[start + sig.patch_index])
    if len(fields) != 1:
        raise FastBootError("signatures disagree on the isSng field offset")
    if len(targets) != 1:
        raise FastBootError("get_Sng calls point at different functions")
    if len(opcodes) != 1:
        raise FastBootError("sites are half patched")
    return Sites(tuple(offsets), State.ON if opcodes == {JMP_SHORT} else State.OFF)


def _opcode(state: State) -> int:
    return JMP_SHORT if state is State.ON else JE_SHORT


# ---------------------------------------------------------------------------
# On-disk patching
# ---------------------------------------------------------------------------

_status_cache: dict[str, tuple[tuple[int, int], dict]] = {}
_cache_lock = threading.Lock()


def _dll(install_dir: str) -> Path:
    return Path(install_dir) / DLL_NAME


def status(install_dir: str) -> dict:
    """Fast-boot state of one install: on / off / unsupported / missing."""
    dll = _dll(install_dir)
    if not IS_WINDOWS or not dll.is_file():
        return {"state": "missing", "reason": f"{DLL_NAME} not found"}
    st = dll.stat()
    key = (st.st_mtime_ns, st.st_size)
    with _cache_lock:
        hit = _status_cache.get(str(dll))
        if hit and hit[0] == key:
            return dict(hit[1])
    try:
        result = {"state": find_sites(dll.read_bytes()).state.value, "reason": ""}
    except FastBootError as e:
        result = {"state": "unsupported", "reason": str(e)}
    except OSError as e:
        result = {"state": "missing", "reason": str(e)}
    with _cache_lock:
        _status_cache[str(dll)] = (key, result)
    return dict(result)


def _write_disk(dll: Path, want: State) -> State:
    """Flip the sites in ``dll`` to ``want``. Returns the state before the call."""
    data = dll.read_bytes()
    sites = find_sites(data)
    if sites.state is want:
        return sites.state
    backup = dll.with_name(dll.name + BACKUP_SUFFIX)
    if want is State.ON and not backup.exists():
        shutil.copy2(dll, backup)
    with open(dll, "r+b") as f:
        for off in sites.offsets:
            f.seek(off)
            f.write(bytes([_opcode(want)]))
    with _cache_lock:
        _status_cache.pop(str(dll), None)
    log.info("fast boot %s on disk: %s", want.value, dll)
    return sites.state


def set_state(install_dir: str, want: State) -> dict:
    """Apply ``want`` to an install, falling back to its running process."""
    dll = _dll(install_dir)
    if not IS_WINDOWS:
        raise ApiError("Fast boot is Windows-only for now.", code="unsupported_os")
    if not dll.is_file():
        raise ApiError(f"No {DLL_NAME} in that install.", code="no_dll", status=404)
    try:
        before = _write_disk(dll, want)
    except FastBootError as e:
        raise ApiError(
            f"This Clone Hero build doesn't match the fast-boot signature, so nothing was changed ({e}).",
            code="fastboot_unsupported",
        ) from e
    except PermissionError:
        before = None
    if before is not None:
        changed = before is not want
        msg = "already " + want.value if not changed else ("enabled" if want is State.ON else "disabled")
        return {"state": want.value, "message": f"Fast boot {msg}.", "running": False}

    # The DLL is mapped by a running game: patch that process instead.
    patched = patch_running(install_dir, want)
    if not patched:
        raise ApiError("GameAssembly.dll is locked, but no running Clone Hero from this install was found.",
                       code="locked", status=409)
    return {
        "state": want.value,
        "running": True,
        "message": "Applied to the running game. It's saved to disk automatically on the next launch.",
    }


def sweep() -> list[dict]:
    """Enable fast boot on every registered install (auto mode). Never raises."""
    if not IS_WINDOWS or not config.get_config().get(CONFIG_KEY, True):
        return []
    from .manager import list_installs  # noqa: PLC0415  (manager imports us)

    results = []
    for inst in list_installs().get("installs", []):
        path = inst.get("path") or ""
        if not _dll(path).is_file():
            continue
        try:
            _write_disk(_dll(path), State.ON)
            results.append({"path": path, "ok": True})
        except (FastBootError, OSError) as e:
            log.warning("fast boot sweep skipped %s: %s", path, e)
            results.append({"path": path, "ok": False, "error": str(e)})
    return results


def sweep_async() -> None:
    threading.Thread(target=sweep, name="fastboot-sweep", daemon=True).start()


# ---------------------------------------------------------------------------
# In-memory patching (game already running / DLL locked)
# ---------------------------------------------------------------------------

if IS_WINDOWS:
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PAGE_EXECUTE_READWRITE = 0x40
    LIST_MODULES_ALL = 0x03
    TH32CS_SNAPPROCESS = 0x2
    INVALID_HANDLE = ctypes.c_void_p(-1).value

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    class _MODULEINFO(ctypes.Structure):
        _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wintypes.DWORD),
                    ("EntryPoint", ctypes.c_void_p)]

    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    _k32.WriteProcessMemory.argtypes = _k32.ReadProcessMemory.argtypes
    _k32.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                      wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _k32.FlushInstructionCache.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t]
    _k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
    _psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
                                            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    _psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    _psapi.GetModuleInformation.argtypes = [wintypes.HANDLE, wintypes.HMODULE,
                                            ctypes.POINTER(_MODULEINFO), wintypes.DWORD]


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))


def _pids_for_install(install_dir: str) -> list[int]:
    """PIDs whose executable lives directly in ``install_dir``."""
    want = _norm(install_dir)
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return []
    pids = []
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() in ("clone hero.exe", "clonehero.exe"):
                h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, entry.th32ProcessID)
                if h:
                    buf = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(len(buf))
                    if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                        if _norm(os.path.dirname(buf.value)) == want:
                            pids.append(entry.th32ProcessID)
                    _k32.CloseHandle(h)
            ok = _k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        _k32.CloseHandle(snap)
    return pids


def _find_module(handle, name: str) -> tuple[int, int] | None:
    mods = (wintypes.HMODULE * 1024)()
    needed = wintypes.DWORD()
    if not _psapi.EnumProcessModulesEx(handle, mods, ctypes.sizeof(mods), ctypes.byref(needed), LIST_MODULES_ALL):
        return None
    buf = ctypes.create_unicode_buffer(1024)
    for i in range(min(needed.value // ctypes.sizeof(wintypes.HMODULE), len(mods))):
        if _psapi.GetModuleFileNameExW(handle, mods[i], buf, len(buf)) and \
                os.path.basename(buf.value).lower() == name.lower():
            info = _MODULEINFO()
            if _psapi.GetModuleInformation(handle, mods[i], ctypes.byref(info), ctypes.sizeof(info)):
                return int(info.lpBaseOfDll), int(info.SizeOfImage)
    return None


def _read(handle, addr: int, size: int) -> bytes:
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if not _k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        raise OSError(ctypes.get_last_error(), "ReadProcessMemory failed")
    return buf.raw[: got.value]


def _write_byte(handle, addr: int, value: int) -> None:
    old = wintypes.DWORD()
    if not _k32.VirtualProtectEx(handle, ctypes.c_void_p(addr), 1, PAGE_EXECUTE_READWRITE, ctypes.byref(old)):
        raise OSError(ctypes.get_last_error(), "VirtualProtectEx failed")
    try:
        data = ctypes.c_ubyte(value)
        if not _k32.WriteProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(data), 1, None):
            raise OSError(ctypes.get_last_error(), "WriteProcessMemory failed")
    finally:
        _k32.VirtualProtectEx(handle, ctypes.c_void_p(addr), 1, old.value, ctypes.byref(wintypes.DWORD()))
    _k32.FlushInstructionCache(handle, ctypes.c_void_p(addr), 1)


def _code_sections(headers: bytes) -> list[tuple[int, int]]:
    """(virtual address, virtual size) of every executable PE section."""
    pe = struct.unpack_from("<I", headers, 0x3C)[0]
    count = struct.unpack_from("<H", headers, pe + 6)[0]
    table = pe + 24 + struct.unpack_from("<H", headers, pe + 20)[0]
    out = []
    for i in range(count):
        o = table + 40 * i
        vsize, va = struct.unpack_from("<II", headers, o + 8)
        if struct.unpack_from("<I", headers, o + 36)[0] & 0x20000000:
            out.append((va, vsize))
    return out


def patch_pid(pid: int, want: State, wait: float = 0.0) -> bool:
    """Patch GameAssembly.dll inside a running process. True on success."""
    access = PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE
    handle = _k32.OpenProcess(access, False, pid)
    if not handle:
        log.warning("fast boot: cannot open pid %s (%s)", pid, ctypes.get_last_error())
        return False
    try:
        deadline = time.monotonic() + wait
        module = _find_module(handle, DLL_NAME)
        while module is None and time.monotonic() < deadline:
            time.sleep(MODULE_POLL_SECONDS)
            module = _find_module(handle, DLL_NAME)
        if module is None:
            return False
        base, _size = module
        for va, vsize in _code_sections(_read(handle, base, 0x1000)):
            code = _read(handle, base + va, vsize)
            try:
                sites = find_sites(code)
            except FastBootError:
                continue
            if sites.state is not want:
                for off in sites.offsets:
                    _write_byte(handle, base + va + off, _opcode(want))
            log.info("fast boot %s in memory: pid %s", want.value, pid)
            return True
        return False
    except OSError as e:
        log.warning("fast boot memory patch failed for pid %s: %s", pid, e)
        return False
    finally:
        _k32.CloseHandle(handle)


def patch_running(install_dir: str, want: State) -> bool:
    if not IS_WINDOWS:
        return False
    return any([patch_pid(pid, want) for pid in _pids_for_install(install_dir)])


def ensure_for_launch(install_dir: str) -> bool:
    """Called before launching: make sure the DLL on disk is patched.

    Returns True when the disk copy is in the ON state; False means the caller
    should patch the new process in memory instead.
    """
    if not IS_WINDOWS or not config.get_config().get(CONFIG_KEY, True):
        return True
    dll = _dll(install_dir)
    if not dll.is_file():
        return True
    try:
        _write_disk(dll, State.ON)
        return True
    except FastBootError as e:
        log.warning("fast boot not applied (%s): %s", dll, e)
        return True  # unsupported build: nothing to do in memory either
    except OSError as e:
        log.warning("fast boot disk write failed (%s): %s", dll, e)
        return False


def patch_new_process_async(pid: int) -> None:
    threading.Thread(target=patch_pid, args=(pid, State.ON, MODULE_WAIT_SECONDS),
                     name="fastboot-mem", daemon=True).start()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def route_enable(body: dict) -> dict:
    return set_state(body.get("path") or "", State.ON)


def route_disable(body: dict) -> dict:
    return set_state(body.get("path") or "", State.OFF)


def route_set_auto(body: dict) -> dict:
    enabled = bool(body.get("enabled", True))
    config.update_config({CONFIG_KEY: enabled})
    if enabled:
        sweep_async()
    return {"enabled": enabled}

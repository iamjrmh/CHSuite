"""Tests for core.fastboot (signature matching + on-disk patching)."""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import fastboot  # noqa: E402
from core.errors import ApiError  # noqa: E402

# Bytes 0x27e420..0x27e4b0 (RVA) of GameAssembly.dll from Clone Hero
# v1.1.0.6142-final: the tail of the cache-read loop holding both isSng checks.
REAL_SNIPPET = bytes.fromhex(
    "a303488bcbe83689d8ff4084ff743c4180bdb300000000741333d2498bcde8dd250e00"
    "4885c00f847d010000488b0d45eca10383b9e0000000007505e88f28ce0233d2498bcd"
    "e8c538efff4180bdb300000000742c33d2498bcde8a1250e004885c0741d33d2498bcd"
    "e892250e004885c00f845a02000033d2488bc8e85f4dfeff4c8bb424b0010000498b86"
    "a8000000"
)
OPEN_SITE = 0x17  # je at RVA 0x27e437
CLOSE_SITE = 0x53  # je at RVA 0x27e473
PADDING = b"\xcc" * 4096

# Bytes 0x2246e8..0x224778 (RVA) of v1.1.0.5977-PTB: the second cache reader,
# compiled without the ``test dil,dil / je`` guard in front of the open-check.
# Both je opcodes sit at the same snippet offsets as in REAL_SNIPPET.
UNGUARDED_SNIPPET = bytes.fromhex(
    "488b15091ba503488bcbe8e989dfff4180bdb300000000741333d2498bcde825eef1ff"
    "4885c00f8414f9ffff488b0d7d47a30383b9e0000000007505e867c1d60233d2498bcd"
    "e86d70e6ff4180bdb300000000742c33d2498bcde8e9edf1ff4885c0741d33d2498bcd"
    "e8daedf1ff4885c00f844702000033d2488bc8e8a725e5ff488b8424a0010000488b80"
    "a8000000"
)
GET_SNG_REL32_OFFSETS = (0x1F, 0x5B, 0x6A)  # the three ``call get_Sng`` operands

# Bytes 0xd03b0..0xd042d (RVA) of v1.1.0.6161-final: the third cache reader,
# whose open-check bails out with a short ``je`` instead of a near one.
SHORT_BAIL_SNIPPET = bytes.fromhex(
    "488bcbe85861f3ff4180bdb300000000740f33d2498bcde8b47825004885c0746b488b"
    "0de056be0383b9e0000000007505e82a19ea0233d2498bcde890581f004180bdb30000"
    "0000742c33d2498bcde87c7825004885c0741d33d2498bcde86d7825004885c00f8459"
    "02000033d2488bc8e8ba370800498b86a8000000"
)
SHORT_BAIL_OPEN_SITE = 0x10  # je at RVA 0xd03c0
SHORT_BAIL_CLOSE_SITE = 0x48  # je at RVA 0xd03f8


def image(snippet: bytes = REAL_SNIPPET) -> bytearray:
    return bytearray(PADDING + snippet + PADDING)


def moved(snippet: bytes, delta: int) -> bytes:
    """``snippet`` as it would look ``delta`` bytes further on, still calling the same get_Sng."""
    out = bytearray(snippet)
    for off in GET_SNG_REL32_OFFSETS:
        struct.pack_into("<i", out, off, struct.unpack_from("<i", out, off)[0] - delta)
    return bytes(out)


def two_readers() -> bytearray:
    gap = len(REAL_SNIPPET) + len(PADDING)
    return image(REAL_SNIPPET + PADDING + moved(REAL_SNIPPET, gap))


def test_finds_both_sites_unpatched():
    sites = fastboot.find_sites(bytes(image()))
    assert sites.state is fastboot.State.OFF
    assert sites.offsets == (len(PADDING) + OPEN_SITE, len(PADDING) + CLOSE_SITE)


def test_detects_patched_state():
    data = image()
    for off in fastboot.find_sites(bytes(data)).offsets:
        data[off] = fastboot.JMP_SHORT
    assert fastboot.find_sites(bytes(data)).state is fastboot.State.ON


def test_half_patched_is_rejected():
    data = image()
    data[len(PADDING) + OPEN_SITE] = fastboot.JMP_SHORT
    with pytest.raises(fastboot.FastBootError, match="half patched"):
        fastboot.find_sites(bytes(data))


def test_missing_signature_is_rejected():
    with pytest.raises(fastboot.FastBootError, match="no match"):
        fastboot.find_sites(PADDING)


def test_unguarded_reader_is_found():
    sites = fastboot.find_sites(bytes(image(UNGUARDED_SNIPPET)))
    assert sites.state is fastboot.State.OFF
    assert sites.offsets == (len(PADDING) + OPEN_SITE, len(PADDING) + CLOSE_SITE)


def test_short_bail_reader_is_found():
    sites = fastboot.find_sites(bytes(image(SHORT_BAIL_SNIPPET)))
    assert sites.offsets == (len(PADDING) + SHORT_BAIL_OPEN_SITE, len(PADDING) + SHORT_BAIL_CLOSE_SITE)


def test_every_reader_copy_is_found():
    first = len(PADDING)
    second = first + len(REAL_SNIPPET) + len(PADDING)
    sites = fastboot.find_sites(bytes(two_readers()))
    assert sites.offsets == (first + OPEN_SITE, first + CLOSE_SITE, second + OPEN_SITE, second + CLOSE_SITE)


def test_one_patched_reader_of_two_is_rejected():
    data = two_readers()
    data[len(PADDING) + OPEN_SITE] = fastboot.JMP_SHORT
    data[len(PADDING) + CLOSE_SITE] = fastboot.JMP_SHORT
    with pytest.raises(fastboot.FastBootError, match="half patched"):
        fastboot.find_sites(bytes(data))


def test_copy_calling_another_function_is_rejected():
    unmoved = image(REAL_SNIPPET + PADDING + REAL_SNIPPET)  # same rel32 elsewhere = other target
    with pytest.raises(fastboot.FastBootError, match="different functions"):
        fastboot.find_sites(bytes(unmoved))


def test_close_check_without_open_check_is_rejected():
    data = image()
    data[len(PADDING) + OPEN_SITE + 2] ^= 0xFF  # break the open-check's ``xor edx,edx``
    with pytest.raises(fastboot.FastBootError, match="expected 1 match before"):
        fastboot.find_sites(bytes(data))


def test_open_check_outside_the_window_is_ignored():
    stray = REAL_SNIPPET[: CLOSE_SITE - 8]  # an open-check with no close-check after it
    sites = fastboot.find_sites(bytes(image(stray + PADDING + REAL_SNIPPET)))
    base = len(PADDING) + len(stray) + len(PADDING)
    assert sites.offsets == (base + OPEN_SITE, base + CLOSE_SITE)


def test_mismatched_call_targets_are_rejected():
    data = image()
    data[len(PADDING) + OPEN_SITE + 8] ^= 0x01  # nudge the open-check call's rel32
    with pytest.raises(fastboot.FastBootError, match="different functions"):
        fastboot.find_sites(bytes(data))


def test_mismatched_field_offset_is_rejected():
    data = image()
    data[len(PADDING) + CLOSE_SITE - 5] = 0xB4  # cmp byte [r13+0xb4] in close-check
    with pytest.raises(fastboot.FastBootError, match="field offset"):
        fastboot.find_sites(bytes(data))


@pytest.fixture
def install(tmp_path, monkeypatch):
    monkeypatch.setattr(fastboot, "IS_WINDOWS", True)
    monkeypatch.setattr(fastboot.config, "get_config", lambda: {fastboot.CONFIG_KEY: True})
    (tmp_path / fastboot.DLL_NAME).write_bytes(bytes(image()))
    return tmp_path


def test_enable_writes_disk_and_backup(install):
    res = fastboot.set_state(str(install), fastboot.State.ON)
    assert res["state"] == "on" and not res["running"]
    data = (install / fastboot.DLL_NAME).read_bytes()
    assert fastboot.find_sites(data).state is fastboot.State.ON
    backup = install / (fastboot.DLL_NAME + fastboot.BACKUP_SUFFIX)
    assert fastboot.find_sites(backup.read_bytes()).state is fastboot.State.OFF


def test_enable_twice_is_a_no_op(install):
    fastboot.set_state(str(install), fastboot.State.ON)
    assert "already" in fastboot.set_state(str(install), fastboot.State.ON)["message"]


def test_enable_patches_every_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(fastboot, "IS_WINDOWS", True)
    original = bytes(two_readers())
    dll = tmp_path / fastboot.DLL_NAME
    dll.write_bytes(original)
    fastboot.set_state(str(tmp_path), fastboot.State.ON)
    patched = dll.read_bytes()
    sites = fastboot.find_sites(patched)
    assert sites.state is fastboot.State.ON and len(sites.offsets) == 4
    assert [i for i in range(len(original)) if original[i] != patched[i]] == list(sites.offsets)
    fastboot.set_state(str(tmp_path), fastboot.State.OFF)
    assert dll.read_bytes() == original


def test_disable_restores_original_bytes(install):
    original = (install / fastboot.DLL_NAME).read_bytes()
    fastboot.set_state(str(install), fastboot.State.ON)
    fastboot.set_state(str(install), fastboot.State.OFF)
    assert (install / fastboot.DLL_NAME).read_bytes() == original


def test_unsupported_build_is_left_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(fastboot, "IS_WINDOWS", True)
    dll = tmp_path / fastboot.DLL_NAME
    dll.write_bytes(PADDING)
    with pytest.raises(ApiError) as exc:
        fastboot.set_state(str(tmp_path), fastboot.State.ON)
    assert exc.value.code == "fastboot_unsupported"
    assert dll.read_bytes() == PADDING
    assert fastboot.status(str(tmp_path))["state"] == "unsupported"


def test_status_reflects_disk_state(install):
    assert fastboot.status(str(install))["state"] == "off"
    fastboot.set_state(str(install), fastboot.State.ON)
    assert fastboot.status(str(install))["state"] == "on"


def test_locked_dll_falls_back_to_running_process(install, monkeypatch):
    def locked(*_a, **_k):
        raise PermissionError("in use")

    monkeypatch.setattr(fastboot, "_write_disk", locked)
    monkeypatch.setattr(fastboot, "patch_running", lambda path, want: True)
    res = fastboot.set_state(str(install), fastboot.State.ON)
    assert res["running"] is True


def test_ensure_for_launch_reports_locked_dll(install, monkeypatch):
    def locked(*_a, **_k):
        raise PermissionError("in use")

    monkeypatch.setattr(fastboot, "_write_disk", locked)
    assert fastboot.ensure_for_launch(str(install)) is False


def test_ensure_for_launch_respects_auto_off(install, monkeypatch):
    monkeypatch.setattr(fastboot.config, "get_config", lambda: {fastboot.CONFIG_KEY: False})
    assert fastboot.ensure_for_launch(str(install)) is True
    assert fastboot.status(str(install))["state"] == "off"


REAL_DLLS = [p for p in os.environ.get("CHSUITE_TEST_GAMEASSEMBLY", "").split(os.pathsep) if p]


@pytest.mark.skipif(not REAL_DLLS, reason="set CHSUITE_TEST_GAMEASSEMBLY to real GameAssembly.dll path(s)")
@pytest.mark.parametrize("dll", REAL_DLLS)
def test_real_gameassembly_matches(dll):
    sites = fastboot.find_sites(Path(dll).read_bytes())
    assert sites.offsets and len(sites.offsets) % 2 == 0

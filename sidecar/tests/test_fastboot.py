"""Tests for core.fastboot (signature matching + on-disk patching)."""

from __future__ import annotations

import os
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


def image(snippet: bytes = REAL_SNIPPET) -> bytearray:
    return bytearray(PADDING + snippet + PADDING)


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
    with pytest.raises(fastboot.FastBootError, match="expected 1 match, found 0"):
        fastboot.find_sites(PADDING)


def test_duplicate_match_is_rejected():
    with pytest.raises(fastboot.FastBootError, match="found 2"):
        fastboot.find_sites(bytes(image(REAL_SNIPPET + PADDING + REAL_SNIPPET)))


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


REAL_DLL = os.environ.get("CHSUITE_TEST_GAMEASSEMBLY")


@pytest.mark.skipif(not REAL_DLL, reason="set CHSUITE_TEST_GAMEASSEMBLY to a real GameAssembly.dll")
def test_real_gameassembly_matches():
    sites = fastboot.find_sites(Path(REAL_DLL).read_bytes())
    assert len(sites.offsets) == 2

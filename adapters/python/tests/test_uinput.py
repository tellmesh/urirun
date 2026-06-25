# Author: Tom Sapletta · https://tom.sapletta.com
# The generic absolute-uinput pointer (urirun.connectors.inputs.uinput). The coordinate math is
# the heart of the Wayland hot-corner fix: a raw pixel must be SCALED into the [0,65535] ABS
# range, else the cursor lands near (0,0) and trips Activities. Tested without /dev/uinput.
from __future__ import annotations

import struct

import pytest

from urirun.connectors.inputs import uinput as U


def test_compute_abs_scales_pixel_into_abs_range():
    # the bug it fixes: raw pixel 720 must NOT stay 720 (≈11px once mapped) — it must become the
    # ABS midpoint so the click lands at the screen centre, not the hot-corner.
    assert U.compute_abs(0, 0, 1440, 900) == (0, 0)
    assert U.compute_abs(1440, 900, 1440, 900) == (U.ABS_RANGE, U.ABS_RANGE)
    ax, ay = U.compute_abs(720, 450, 1440, 900)
    assert abs(ax - U.ABS_RANGE // 2) <= 1 and abs(ay - U.ABS_RANGE // 2) <= 1   # centre
    assert ax != 720, "raw pixel must be scaled, not passed through (the hot-corner bug)"


def test_compute_abs_inverts_calibration():
    # landing = 1.0*commanded + 100 (a 100px offset). To LAND at pixel 600 we must COMMAND 500.
    calib = (1.0, 100.0, 1.0, 0.0)
    ax, _ = U.compute_abs(600, 0, 1000, 1000, calib)
    assert ax == int(500 / 1000 * U.ABS_RANGE)        # commanded 500, then scaled


def test_compute_abs_zero_screen_passes_through():
    # unknown screen size -> treat coords as already absolute (no division by zero)
    assert U.compute_abs(123, 456, 0, 0) == (123, 456)


def test_calib_from_env(monkeypatch):
    monkeypatch.setenv("URIRUN_ABS_CALIB", "1.1,2.2,3.3,4.4")
    assert U.calib_from_env() == (1.1, 2.2, 3.3, 4.4)
    monkeypatch.setenv("URIRUN_ABS_CALIB", "garbage")
    assert U.calib_from_env() is None


def test_abs_click_raises_cleanly_without_uinput(monkeypatch):
    monkeypatch.setattr(U, "uinput_available", lambda: False)
    with pytest.raises(U.BackendError) as ei:
        U.abs_click(10, 10, 1000, 1000)
    assert "/dev/uinput" in str(ei.value)


def test_configure_injects_screen_size_resolver(monkeypatch):
    seen = {}
    monkeypatch.setattr(U, "uinput_available", lambda: True)
    monkeypatch.setattr(U, "_create_abs", lambda: 7)
    monkeypatch.setattr(U._fcntl, "ioctl", lambda *a: 0)
    monkeypatch.setattr(U.os, "close", lambda fd: None)
    monkeypatch.setattr(U.time, "sleep", lambda s: None)

    def fake_write(fd, data):
        t, c, v = struct.unpack("llHHi", data)[2:]
        if t == U._EV_ABS:
            seen[c] = v
    monkeypatch.setattr(U.os, "write", fake_write)
    try:
        U.configure(screen_size=lambda: (1000, 1000))     # injected, used because sw/sh omitted
        r = U.abs_click(500, 500, do_click=False, settle=0)   # no sw/sh -> resolver gives 1000×1000
        assert r["abs"] == [U.ABS_RANGE // 2, U.ABS_RANGE // 2]   # centre, via injected size
        assert seen[U._ABS_X] == U.ABS_RANGE // 2                 # the ABS_X event carried it
    finally:
        U.configure(screen_size=lambda: (0, 0))

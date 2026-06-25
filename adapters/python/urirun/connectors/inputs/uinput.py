# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# GENERIC pixel-accurate absolute pointer via a raw Linux /dev/uinput device — the
# connector-agnostic core extracted from urirun-connector-kvm/backends.py.
#
# An ABSOLUTE (tablet-style) device bypasses pointer acceleration and maps [0,65535] linearly
# onto the desktop, so a click at fraction (x/sw, y/sh) of a screenshot lands at THAT pixel —
# the fix for the Wayland hot-corner / capture-space≠action-space bug (ydotool's mousemove -a
# mis-mapped raw pixels and trips the GNOME hot-corner). stdlib only; needs r/w on /dev/uinput.
#
# Connector-agnostic: the SCREEN SIZE (the space coords live in) and the optional CALIBRATION
# transform are supplied by the caller / injected via configure() — this module never reads a
# connector's screen/calib env. Linux-only; on other OSes uinput_available() is False.
from __future__ import annotations

import fcntl as _fcntl
import os
import struct as _struct
import time
from typing import Callable

try:
    from urirun.connectors.backend_registry import BackendError
except Exception:  # pragma: no cover - allow flat use without the registry
    class BackendError(RuntimeError):  # type: ignore
        pass

ABS_RANGE = 65535

_UI = ord("U")
def _ui_io(nr: int) -> int:           return (0 << 30) | (_UI << 8) | nr
def _ui_iow(nr: int, sz: int) -> int: return (1 << 30) | (sz << 16) | (_UI << 8) | nr
_UI_DEV_CREATE, _UI_DEV_DESTROY = _ui_io(1), _ui_io(2)
_UI_SET_EVBIT, _UI_SET_KEYBIT, _UI_SET_ABSBIT = _ui_iow(100, 4), _ui_iow(101, 4), _ui_iow(103, 4)
_EV_SYN, _EV_KEY, _EV_ABS = 0, 1, 3
_ABS_X, _ABS_Y = 0, 1
_BTN_CODE = {"left": 0x110, "right": 0x111, "middle": 0x112}
_BTN_TOUCH = 0x14A

_CFG: dict[str, Callable] = {
    "screen_size": lambda: (0, 0),   # connector injects its capture-surface size resolver
    "calib": lambda: None,           # connector injects its calibration (ax,bx,ay,by) | None
}


def configure(*, screen_size: Callable[[], tuple] | None = None,
              calib: Callable[[], tuple | None] | None = None) -> None:
    """A connector wires its screen-size resolver (used when a caller omits sw/sh) and an optional
    calibration provider here — so the generic never reads kvm's URIRUN_KVM_SCREEN / _CALIB env."""
    if screen_size is not None:
        _CFG["screen_size"] = screen_size
    if calib is not None:
        _CFG["calib"] = calib


def calib_from_env(var: str = "URIRUN_ABS_CALIB") -> tuple | None:
    """Parse ``ax,bx,ay,by`` from an env var into a calibration tuple, or None if unset/invalid.
    Encodes ``landing_pixel = a*commanded + b`` per axis (fit by a host calibration pass)."""
    try:
        ax, bx, ay, by = (float(v) for v in os.environ.get(var, "").split(","))
        return ax, bx, ay, by
    except (ValueError, TypeError):
        return None


def uinput_available() -> bool:
    return os.path.exists("/dev/uinput") and os.access("/dev/uinput", os.W_OK)


def compute_abs(px: float, py: float, sw: int, sh: int, calib: tuple | None = None) -> tuple[int, int]:
    """Map pixel (px,py) on a sw×sh surface to the uinput [0,ABS_RANGE] range. If ``calib`` is
    given it INVERTS ``landing=a*commanded+b`` first, so the cursor LANDS at (px,py) on a
    fractional-HiDPI / multi-region display. The pure-math heart of the coordinate fix."""
    if calib:
        ca_x, cb_x, ca_y, cb_y = calib
        if ca_x:
            px = (px - cb_x) / ca_x
        if ca_y:
            py = (py - cb_y) / ca_y
        px = max(0.0, min(float(sw), px))
        py = max(0.0, min(float(sh), py))
    ax = max(0, min(ABS_RANGE, int(px / sw * ABS_RANGE) if sw else int(px)))
    ay = max(0, min(ABS_RANGE, int(py / sh * ABS_RANGE) if sh else int(py)))
    return ax, ay


def _create_abs() -> int:
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    for ev in (_EV_KEY, _EV_ABS, _EV_SYN):
        _fcntl.ioctl(fd, _UI_SET_EVBIT, ev)
    for b in (0x110, 0x111, 0x112, _BTN_TOUCH):
        _fcntl.ioctl(fd, _UI_SET_KEYBIT, b)
    _fcntl.ioctl(fd, _UI_SET_ABSBIT, _ABS_X)
    _fcntl.ioctl(fd, _UI_SET_ABSBIT, _ABS_Y)
    absmax = [0] * 64
    absmax[_ABS_X] = absmax[_ABS_Y] = ABS_RANGE
    dev = _struct.pack("<80s4HI", b"urirun-abs-pointer", 0x03, 0x1234, 0x5678, 1, 0)
    dev += _struct.pack("<64i", *absmax) + _struct.pack("<192i", *([0] * 192))
    os.write(fd, dev)
    _fcntl.ioctl(fd, _UI_DEV_CREATE)
    return fd


def _emit_clicks(ev: Callable, fd: int, button: str, clicks: int) -> None:
    """Emit ``clicks`` press/release pairs on the open uinput ``fd`` — N presses on ONE device
    is a real double/triple-click."""
    bc = _BTN_CODE.get(button, 0x110)
    for _i in range(max(1, int(clicks))):
        ev(fd, _EV_KEY, bc, 1); ev(fd, _EV_KEY, _BTN_TOUCH, 1); ev(fd, _EV_SYN, 0, 0)
        time.sleep(0.06)
        ev(fd, _EV_KEY, bc, 0); ev(fd, _EV_KEY, _BTN_TOUCH, 0); ev(fd, _EV_SYN, 0, 0)
        time.sleep(0.06)


def abs_click(x: int, y: int, sw: int = 0, sh: int = 0, *, button: str = "left",
              do_click: bool = True, settle: float = 0.9, clicks: int = 1,
              calib: tuple | None = None) -> dict:
    """Position (and optionally click) at pixel (x,y) via a fresh raw absolute uinput device.
    ``sw``/``sh`` default to the injected screen-size resolver; ``calib`` to the injected one.
    Coordinate-exact: what a screenshot shows at (x,y) is where the click lands."""
    if not uinput_available():
        raise BackendError("no write access to /dev/uinput (add user to 'input' group or a udev rule)")
    if not sw or not sh:
        dsw, dsh = _CFG["screen_size"]()
        sw, sh = sw or dsw, sh or dsh
    if calib is None:
        calib = _CFG["calib"]()
    ax, ay = compute_abs(float(x), float(y), sw, sh, calib)

    def ev(fd: int, t: int, c: int, v: int) -> None:
        os.write(fd, _struct.pack("llHHi", 0, 0, t, c, v))
    fd = _create_abs()
    try:
        time.sleep(float(settle))      # compositor discovers + maps the new device
        ev(fd, _EV_ABS, _ABS_X, ax); ev(fd, _EV_ABS, _ABS_Y, ay); ev(fd, _EV_SYN, 0, 0)
        time.sleep(0.25)
        if do_click:
            _emit_clicks(ev, fd, button, clicks)
        time.sleep(0.2)
        return {"via": "uinput-absolute", "abs": [ax, ay], "pixel": [x, y],
                "clicked": bool(do_click), "clicks": int(clicks) if do_click else 0}
    finally:
        try:
            _fcntl.ioctl(fd, _UI_DEV_DESTROY)
        except Exception:  # noqa: BLE001
            pass
        os.close(fd)

"""System-wide mute controller built on Windows Core Audio via pycaw.

Provides a small, best-effort helper for reading and toggling the system
master mute state. Safe to import when pycaw is unavailable: all methods
become cheap no-ops that never raise.

All methods are synchronous and intended to be called from short-lived
worker tasks scheduled via :mod:`core.threading.manager`.
"""
from __future__ import annotations

from typing import Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)

_endpoint_volume = None
_available = False

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import]

    devices = AudioUtilities.GetSpeakers()
    if devices is not None:
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        _endpoint_volume = cast(interface, POINTER(IAudioEndpointVolume))
        _available = True
        logger.debug("[SYSTEM_MUTE] IAudioEndpointVolume acquired successfully")
    else:
        logger.info("[SYSTEM_MUTE] No default speakers found")
except Exception:
    logger.info("[SYSTEM_MUTE] pycaw/Core Audio not available; system mute disabled")


def is_available() -> bool:
    """Return True when system mute control is available."""
    return _available


def get_mute() -> Optional[bool]:
    """Return current system mute state, or None if unavailable."""
    if not _available or _endpoint_volume is None:
        return None
    try:
        return bool(_endpoint_volume.GetMute())
    except Exception:
        logger.debug("[SYSTEM_MUTE] GetMute failed", exc_info=True)
        return None


def set_mute(muted: bool) -> bool:
    """Set system mute state. Returns True on success."""
    if not _available or _endpoint_volume is None:
        return False
    try:
        _endpoint_volume.SetMute(int(muted), None)
        logger.debug("[SYSTEM_MUTE] SetMute(%s)", muted)
        return True
    except Exception:
        logger.debug("[SYSTEM_MUTE] SetMute failed", exc_info=True)
        return False


def get_volume() -> Optional[float]:
    """Return current master volume in [0.0, 1.0], or None if unavailable."""
    if not _available or _endpoint_volume is None:
        return None
    try:
        return float(_endpoint_volume.GetMasterVolumeLevelScalar())
    except Exception:
        logger.debug("[SYSTEM_MUTE] GetMasterVolumeLevelScalar failed", exc_info=True)
        return None


def set_volume(level: float) -> bool:
    """Set current master volume to ``level`` in [0.0, 1.0]."""
    if not _available or _endpoint_volume is None:
        return False
    try:
        clamped = max(0.0, min(1.0, float(level)))
        _endpoint_volume.SetMasterVolumeLevelScalar(clamped, None)
        logger.debug("[SYSTEM_MUTE] SetMasterVolumeLevelScalar(%.3f)", clamped)
        return True
    except Exception:
        logger.debug("[SYSTEM_MUTE] SetMasterVolumeLevelScalar failed", exc_info=True)
        return False


def step_volume(delta: float) -> Optional[float]:
    """Adjust master volume by ``delta`` and return the new level on success."""
    current = get_volume()
    if current is None:
        return None
    target = max(0.0, min(1.0, float(current) + float(delta)))
    if set_volume(target):
        return target
    return None


def toggle_mute() -> Optional[bool]:
    """Toggle system mute. Returns new mute state, or None on failure."""
    current = get_mute()
    if current is None:
        return None
    new_state = not current
    if set_mute(new_state):
        return new_state
    return None

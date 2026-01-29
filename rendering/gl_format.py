"""
Utilities for constructing QSurfaceFormat instances that respect user settings.

Centralizes GL surface configuration so we consistently honour refresh sync
(vsync) while preferring a simple double-buffered swap behaviour. Any
"prefer triple buffer" setting is now treated as a legacy hint and does not
change the requested swap behaviour; modern drivers control true triple
buffering at their own layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, TYPE_CHECKING

import threading

from PySide6.QtCore import QSettings
from PySide6.QtGui import QSurfaceFormat

from core.logging.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from core.settings.settings_manager import SettingsManager

logger = get_logger(__name__)

_DEFAULT_ORG = "ShittyRandomPhotoScreenSaver"
_DEFAULT_APP = "Screensaver"

_log_lock = threading.Lock()
_logged_reasons: set[str] = set()


@dataclass(frozen=True)
class SurfacePreferences:
    prefer_triple_buffer: bool
    depth_bits: int = 24
    stencil_bits: int = 8


def _coerce_bool(value, default: bool) -> bool:
    """Normalise a settings value to bool using SettingsManager semantics.

    When core.settings.settings_manager is importable, this delegates to
    SettingsManager.to_bool so GL surface preferences are interpreted
    identically to the rest of the application. In early-startup or
    test-only contexts where importing SettingsManager would be unsafe,
    it falls back to a local implementation with the same rules.
    """

    try:
        from core.settings.settings_manager import SettingsManager as _SM  # type: ignore

        return _SM.to_bool(value, default)
    except Exception as e:
        logger.debug("[MISC] Exception suppressed: %s", e)
        if value is None:
            return default
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1", "yes", "on"}:
                return True
            if v in {"false", "0", "no", "off"}:
                return False
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        try:
            return bool(value)
        except Exception as e:
            logger.debug("[MISC] Exception suppressed: %s", e)
            return default


def _coerce_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        logger.debug("[GL FORMAT] Failed to coerce %r to int, using default %d: %s", value, default, e, exc_info=True)
        return default


def read_surface_preferences(
    settings_manager: Optional["SettingsManager"] = None,
    *,
    organization: str = _DEFAULT_ORG,
    application: str = _DEFAULT_APP,
) -> SurfacePreferences:
    """Resolve GL surface preferences from settings or persisted storage."""
    triple_default = True
    depth_default = 24
    stencil_default = 8

    if settings_manager is not None:
        try:
            triple_value = settings_manager.get("display.prefer_triple_buffer", triple_default)
            depth_value = settings_manager.get("display.gl_depth_bits", depth_default)
            stencil_value = settings_manager.get("display.gl_stencil_bits", stencil_default)
        except Exception as e:
            logger.debug(
                "[GL FORMAT] Failed to read surface preferences from SettingsManager, using defaults: %s",
                e,
                exc_info=True,
            )
            triple_value = triple_default
            depth_value = depth_default
            stencil_value = stencil_default
    else:
        qsettings = QSettings(organization, application)
        triple_value = qsettings.value("display.prefer_triple_buffer", triple_default)
        depth_value = qsettings.value("display.gl_depth_bits", depth_default)
        stencil_value = qsettings.value("display.gl_stencil_bits", stencil_default)

    preferences = SurfacePreferences(
        prefer_triple_buffer=_coerce_bool(triple_value, triple_default),
        depth_bits=_coerce_int(depth_value, depth_default),
        stencil_bits=_coerce_int(stencil_value, stencil_default),
    )
    return preferences


def _infer_settings_manager(widget) -> Optional["SettingsManager"]:
    """Attempt to locate a SettingsManager attached to widget ancestry."""
    try:
        candidate = getattr(widget, "settings_manager", None)
        if candidate is not None:
            return candidate
        parent_getter = getattr(widget, "parent", None)
        if callable(parent_getter):
            parent = parent_getter()
        else:
            parent = None
        depth = 0
        while parent is not None and depth < 5:
            candidate = getattr(parent, "settings_manager", None)
            if candidate is not None:
                return candidate
            parent_getter = getattr(parent, "parent", None)
            parent = parent_getter() if callable(parent_getter) else None
            depth += 1
    except Exception as e:
        logger.debug("[GL FORMAT] Failed to infer SettingsManager from widget ancestry: %s", e, exc_info=True)
        return None
    return None


def build_surface_format(
    settings_manager: Optional["SettingsManager"] = None,
    *,
    reason: str = "",
) -> Tuple[QSurfaceFormat, SurfacePreferences]:
    """Build a QSurfaceFormat according to the user's GL preferences."""
    prefs = read_surface_preferences(settings_manager)

    fmt = QSurfaceFormat()

    # Always request a double-buffered surface; modern drivers manage any
    # true triple buffering themselves and explicit TripleBuffer requests
    # tend to be brittle across stacks.
    requested_swap = QSurfaceFormat.SwapBehavior.DoubleBuffer
    try:
        fmt.setSwapBehavior(requested_swap)
    except Exception as e:
        logger.debug("[GL FORMAT] Failed to set requested swap behaviour %s: %s", requested_swap, e, exc_info=True)
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DefaultSwapBehavior)

    swap_interval = 0
    try:
        fmt.setSwapInterval(swap_interval)
    except Exception as e:
        logger.debug("[GL FORMAT] Failed to set swap interval 0: %s", e, exc_info=True)

    try:
        fmt.setDepthBufferSize(prefs.depth_bits)
    except Exception as e:
        logger.debug("[GL FORMAT] Failed to set depth buffer size %s: %s", prefs.depth_bits, e, exc_info=True)

    try:
        fmt.setStencilBufferSize(prefs.stencil_bits)
    except Exception as e:
        logger.debug("[GL FORMAT] Failed to set stencil buffer size %s: %s", prefs.stencil_bits, e, exc_info=True)

    log_key = reason or "__default__"
    should_log = False
    with _log_lock:
        if log_key not in _logged_reasons:
            _logged_reasons.add(log_key)
            should_log = True

    if should_log:
        logger.debug(
            "[GL FORMAT] Requested swap=%s interval=%s depth=%s stencil=%s (prefer_triple=%s)%s",
            requested_swap,
            swap_interval,
            prefs.depth_bits,
            prefs.stencil_bits,
            prefs.prefer_triple_buffer,
            f" reason={reason}" if reason else "",
        )

    return fmt, prefs


def apply_widget_surface_format(
    widget,
    settings_manager: Optional["SettingsManager"] = None,
    *,
    reason: str = "",
) -> SurfacePreferences:
    """Apply a surface format to the given QOpenGLWidget-derived widget."""
    if settings_manager is None:
        settings_manager = _infer_settings_manager(widget)
    fmt, prefs = build_surface_format(settings_manager, reason=reason)
    try:
        widget.setFormat(fmt)
    except Exception as exc:
        logger.warning("[GL FORMAT] Failed to apply format (%s): %s", reason or "", exc)
    return prefs

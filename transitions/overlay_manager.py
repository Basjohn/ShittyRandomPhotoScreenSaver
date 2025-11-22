"""
Overlay manager utilities for transition overlays.

Centralizes access and cleanup for persistent overlay widgets created by
transitions (both GL and software overlays).
"""
from __future__ import annotations

import time
from typing import Callable, Optional, Type, TypeVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from core.threading.manager import ThreadManager
from core.logging.logger import get_logger


# Known overlay attribute names on DisplayWidget
GL_OVERLAY_KEYS: tuple[str, ...] = (
    "_srpss_gl_xfade_overlay",
    "_srpss_gl_slide_overlay",
    "_srpss_gl_wipe_overlay",
    "_srpss_gl_diffuse_overlay",
    "_srpss_gl_blockflip_overlay",
    "_srpss_gl_blinds_overlay",
)

SW_OVERLAY_KEYS: tuple[str, ...] = (
    "_srpss_sw_xfade_overlay",
)

BACKEND_FALLBACK_OVERLAY_KEY = "_srpss_backend_fallback_overlay"

ALL_OVERLAY_KEYS: tuple[str, ...] = GL_OVERLAY_KEYS + SW_OVERLAY_KEYS + (
    BACKEND_FALLBACK_OVERLAY_KEY,
)

OverlayT = TypeVar("OverlayT", bound=QWidget)

logger = get_logger(__name__)


def hide_all_overlays(widget) -> None:
    """Hide all known overlays on the given widget if present."""
    for key in ALL_OVERLAY_KEYS:
        try:
            ov = getattr(widget, key, None)
            if ov is not None:
                ov.hide()
        except Exception:
            pass


def any_visible_gl_overlay_has_drawn(widget) -> bool:
    """Return True if any GL overlay is visible and has drawn at least once."""
    for key in GL_OVERLAY_KEYS:
        ov = getattr(widget, key, None)
        if ov is None:
            continue
        try:
            if ov.isVisible():
                # Some overlays expose has_drawn()
                try:
                    if bool(ov.has_drawn()):
                        return True
                except Exception:
                    # If no has_drawn(), be conservative and do not skip base paint
                    continue
        except Exception:
            continue
    return False


def any_gl_overlay_visible(widget) -> bool:
    """Return True if any GL overlay is currently visible (regardless of draw state)."""
    for key in GL_OVERLAY_KEYS:
        try:
            ov = getattr(widget, key, None)
            if ov is not None and ov.isVisible():
                return True
        except Exception:
            continue
    return False


def any_overlay_ready_for_display(widget) -> bool:
    """
    Thread-safe check if any overlay (GL or SW) is visible AND ready to display.
    
    Uses atomic ready flags from overlays to avoid paint-event race conditions.
    An overlay is "ready" when it has both initialized and drawn its first frame.
    """
    # Check GL overlays with atomic ready flags
    for key in GL_OVERLAY_KEYS:
        try:
            ov = getattr(widget, key, None)
            if ov is not None and ov.isVisible():
                # Try atomic ready check first (new pattern)
                if hasattr(ov, 'is_ready_for_display'):
                    if ov.is_ready_for_display():
                        return True
                # Fallback to legacy has_drawn() check
                elif hasattr(ov, 'has_drawn') and ov.has_drawn():
                    return True
        except Exception:
            continue
    
    # Check SW overlays (legacy pattern)
    for key in SW_OVERLAY_KEYS:
        try:
            ov = getattr(widget, key, None)
            if ov is not None and ov.isVisible():
                # SW overlays use _has_drawn directly
                if hasattr(ov, '_has_drawn') and ov._has_drawn:
                    return True
        except Exception:
            continue
    
    return False


def raise_clock_if_present(widget) -> None:
    """Raise the clock overlay above any transition overlays if present."""
    try:
        for attr_name in ("clock_widget", "clock2_widget", "clock3_widget"):
            if hasattr(widget, attr_name):
                clock = getattr(widget, attr_name)
                if clock:
                    try:
                        clock.raise_()
                        if hasattr(clock, "_tz_label") and clock._tz_label:
                            clock._tz_label.raise_()
                    except Exception:
                        continue
    except Exception:
        pass


def get_or_create_overlay(
    widget: QWidget,
    attr_name: str,
    overlay_type: Type[OverlayT],
    factory: Callable[[], OverlayT],
    on_create: Optional[Callable[[OverlayT], None]] = None,
) -> OverlayT:
    """Fetch an existing persistent overlay or create a new one via factory."""
    overlay = getattr(widget, attr_name, None)
    created = overlay is None or not isinstance(overlay, overlay_type)
    if created:
        overlay = factory()
        # Ensure predictable naming for diagnostics
        try:
            if not overlay.objectName():
                overlay.setObjectName(attr_name)
        except Exception:
            pass
        setattr(widget, attr_name, overlay)
        # Attach to widget parent immediately
        try:
            if overlay.parent() is not widget:
                overlay.setParent(widget)
        except Exception:
            pass
        # Register with widget ResourceManager if present
        try:
            resource_manager = getattr(widget, "_resource_manager", None)
            if resource_manager and not getattr(overlay, "_resource_id", None):
                overlay._resource_id = resource_manager.register_qt(  # type: ignore[attr-defined]
                    overlay,
                    description=f"Persistent overlay {attr_name}",
                )
        except Exception:
            pass
        if on_create:
            try:
                on_create(overlay)
            except Exception:
                pass
    else:
        # Ensure existing overlay remains parented and tracked
        try:
            if overlay.parent() is not widget:
                overlay.setParent(widget)
        except Exception:
            pass
        try:
            resource_manager = getattr(widget, "_resource_manager", None)
            if resource_manager and not getattr(overlay, "_resource_id", None):
                overlay._resource_id = resource_manager.register_qt(  # type: ignore[attr-defined]
                    overlay,
                    description=f"Persistent overlay {attr_name}",
                )
        except Exception:
            pass

    # Make sure overlay geometry matches widget bounds on retrieval
    try:
        overlay.setGeometry(0, 0, widget.width(), widget.height())
    except Exception:
        pass
    return overlay


def show_backend_fallback_overlay(
    widget: QWidget,
    message: str,
    *,
    on_create: Optional[Callable[[QWidget], None]] = None,
) -> QLabel:
    """Show (or update) a red diagnostic overlay indicating backend fallback."""

    def _factory() -> QLabel:
        label = QLabel(widget)
        label.setObjectName("BackendFallbackOverlay")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return label

    overlay = get_or_create_overlay(
        widget,
        BACKEND_FALLBACK_OVERLAY_KEY,
        QLabel,
        _factory,
        on_create,
    )

    overlay.setText(message)
    overlay.setStyleSheet(
        "background-color: rgba(160, 0, 0, 180); color: #ffffff; "
        "font-weight: bold; padding: 16px; border: 2px solid rgba(255, 255, 255, 120);"
    )
    overlay.show()
    set_overlay_geometry(widget, overlay)
    raise_overlay(widget, overlay)
    return overlay


def hide_backend_fallback_overlay(widget: QWidget) -> None:
    """Hide the backend fallback diagnostic overlay if present."""

    try:
        overlay = getattr(widget, BACKEND_FALLBACK_OVERLAY_KEY, None)
        if overlay is not None:
            overlay.hide()
    except Exception:
        pass


def set_overlay_geometry(widget: QWidget, overlay: QWidget) -> None:
    """Resize overlay to fully cover the widget."""
    try:
        overlay.setGeometry(0, 0, widget.width(), widget.height())
    except Exception:
        pass


def raise_overlay(widget: QWidget, overlay: QWidget) -> None:
    """Raise overlay above the base widget while keeping clock/weather above."""
    try:
        overlay.raise_()
    except Exception:
        pass
    raise_clock_if_present(widget)
    try:
        if hasattr(widget, "weather_widget") and getattr(widget, "weather_widget"):
            widget.weather_widget.raise_()
    except Exception:
        pass
    try:
        # Ensure the media widget (Spotify overlay) stays above transition
        # overlays as well so that transport controls and track text remain
        # visible in both software and GL compositor modes.
        mw = getattr(widget, "media_widget", None)
        if mw is not None:
            mw.raise_()
    except Exception:
        pass

    try:
        # Spotify Beat Visualizer should sit just above the media widget so
        # that its bars remain visible across transitions.
        sv = getattr(widget, "spotify_visualizer_widget", None)
        if sv is not None:
            sv.raise_()
    except Exception:
        pass


def notify_overlay_stage(overlay: QWidget, stage: str, **details) -> None:
    """Forward overlay readiness diagnostics to the parent DisplayWidget."""
    try:
        parent = overlay.parent()
        if parent and hasattr(parent, "notify_overlay_ready"):
            name = overlay.objectName() or overlay.__class__.__name__
            parent.notify_overlay_ready(name, stage, **details)
    except Exception:
        pass


def schedule_raise_when_ready(
    widget: QWidget,
    overlay: QWidget,
    *,
    poll_ms: int = 8,
    timeout_ms: int = 120,
    stage: str = "initial_raise",
    on_ready: Optional[Callable[[], None]] = None,
    on_timeout: Optional[Callable[[], None]] = None,
) -> None:
    """Poll overlay readiness without blocking the event loop and raise when ready."""
    start = time.monotonic()

    def _check() -> None:
        try:
            # Many overlays expose is_ready_for_display(); fall back to has_drawn when absent
            ready = False
            if hasattr(overlay, "is_ready_for_display"):
                ready = bool(overlay.is_ready_for_display())  # type: ignore[attr-defined]
            elif hasattr(overlay, "has_drawn"):
                ready = bool(overlay.has_drawn())  # type: ignore[attr-defined]
        except Exception:
            ready = False

        elapsed_ms = (time.monotonic() - start) * 1000.0
        if ready:
            raise_overlay(widget, overlay)
            notify_overlay_stage(overlay, stage, status="ready", wait_ms=f"{elapsed_ms:.2f}")
            if on_ready:
                try:
                    on_ready()
                except Exception:
                    pass
            return

        if elapsed_ms >= timeout_ms:
            notify_overlay_stage(overlay, stage, status="timeout", wait_ms=f"{elapsed_ms:.2f}")
            if on_timeout:
                try:
                    on_timeout()
                except Exception:
                    pass
            return

        ThreadManager.single_shot(poll_ms, _check)

    ThreadManager.single_shot(0, _check)


def prepare_gl_overlay(
    widget: QWidget,
    overlay: QWidget,
    *,
    stage: str,
    make_current: bool = True,
    grab_framebuffer: bool = True,
    repaint: bool = True,
    prepaint_description: str | None = None,
) -> None:
    """Standardize GL overlay initialization sequence."""

    overlay.setVisible(True)
    set_overlay_geometry(widget, overlay)
    notify_overlay_stage(overlay, "prepaint_start")

    if make_current:
        try:
            overlay.makeCurrent()  # type: ignore[attr-defined]
        except Exception:
            pass

    if grab_framebuffer:
        try:
            _ = overlay.grabFramebuffer()  # type: ignore[attr-defined]
            notify_overlay_stage(overlay, "prepaint_ready")
        except Exception as exc:
            if prepaint_description:
                logger.warning("[%s] Prepaint failed: %s", prepaint_description, exc)
            else:
                logger.debug("[GL] Prepaint grabFramebuffer failed", exc_info=True)

    if repaint:
        try:
            overlay.repaint()
        except Exception:
            pass

    schedule_raise_when_ready(widget, overlay, stage=stage)

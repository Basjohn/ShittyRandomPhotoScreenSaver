"""
Overlay manager utilities for transition overlays.

Centralizes access and cleanup for persistent overlay widgets created by
transitions (both GL and software overlays).
"""
from __future__ import annotations

# Known overlay attribute names on DisplayWidget
GL_OVERLAY_KEYS: tuple[str, ...] = (
    "_srpss_gl_xfade_overlay",
    "_srpss_gl_slide_overlay",
    "_srpss_gl_wipe_overlay",
    "_srpss_gl_diffuse_overlay",
    "_srpss_gl_blockflip_overlay",
)

SW_OVERLAY_KEYS: tuple[str, ...] = (
    "_srpss_sw_xfade_overlay",
)

ALL_OVERLAY_KEYS: tuple[str, ...] = GL_OVERLAY_KEYS + SW_OVERLAY_KEYS


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
        if hasattr(widget, "clock_widget") and getattr(widget, "clock_widget"):
            widget.clock_widget.raise_()
    except Exception:
        pass

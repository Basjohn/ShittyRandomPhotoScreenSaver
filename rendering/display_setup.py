"""Display Setup & Initialization - Extracted from display_widget.py.

Contains display show/hide, widget setup, overlay stack creation,
screen change handling, and related initialization logic.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

try:
    from OpenGL import GL  # type: ignore[import]
except ImportError:
    GL = None

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.settings_manager import SettingsManager
from widgets.pixel_shift_manager import PixelShiftManager
from widgets.context_menu import ScreensaverContextMenu
from transitions.overlay_manager import (
    set_overlay_geometry,
    raise_overlay,
    schedule_raise_when_ready,
    GL_OVERLAY_KEYS,
    SW_OVERLAY_KEYS,
)

_FULLSCREEN_COMPAT_WORKAROUND = True

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def show_on_screen(widget) -> None:
    """Show widget fullscreen on assigned screen."""
    screens = QGuiApplication.screens()
    
    if widget.screen_index >= len(screens):
        logger.warning(f"[FALLBACK] Screen {widget.screen_index} not found, using primary")
        screen = QGuiApplication.primaryScreen()
    else:
        screen = screens[widget.screen_index]
    
    # Store screen reference and DPI ratio for high-quality rendering
    widget._screen = screen
    widget._device_pixel_ratio = screen.devicePixelRatio()
    
    screen_geom = screen.geometry()
    geom = screen_geom
    if _FULLSCREEN_COMPAT_WORKAROUND:
        try:
            if geom.height() > 1:
                geom.setHeight(geom.height() - 1)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    logger.info(
        f"Showing on screen {widget.screen_index}: "
        f"{screen_geom.width()}x{screen_geom.height()} at ({screen_geom.x()}, {screen_geom.y()}) "
        f"DPR={widget._device_pixel_ratio}"
    )

    # Borderless fullscreen: frameless window sized to the target screen.
    # Avoid exclusive fullscreen mode to reduce compositor and driver-induced
    # flicker on modern Windows. For MC builds, apply always-on-top flag.
    if widget._is_mc_build and widget._always_on_top:
        widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    widget.setGeometry(geom)
    # Seed with a placeholder snapshot of the current screen to avoid a hard
    # wallpaper->black flash while GL prewarm runs. If this fails, fall back
    # to blocking updates until the first real image is seeded.
    placeholder_set = False
    try:
        wallpaper_pm = screen.grabWindow(0)
        if wallpaper_pm is not None and not wallpaper_pm.isNull():
            try:
                wallpaper_pm.setDevicePixelRatio(widget._device_pixel_ratio)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            widget.current_pixmap = wallpaper_pm
            widget.previous_pixmap = wallpaper_pm
            widget._seed_pixmap = wallpaper_pm
            widget._last_pixmap_seed_ts = time.monotonic()
            placeholder_set = True
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        placeholder_set = False

    if placeholder_set:
        try:
            widget.setUpdatesEnabled(True)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        widget._updates_blocked_until_seed = False
    else:
        try:
            widget.setUpdatesEnabled(False)
            widget._updates_blocked_until_seed = True
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            widget._widget._updates_blocked_until_seed = False

    # Determine hardware acceleration setting once for startup behaviour.
    # IMPORTANT: We no longer run GL prewarm at startup; GL overlays are
    # initialized lazily by per-transition prepaint. This avoids any
    # startup interaction with GL contexts that could cause black flashes.
    hw_accel = True
    if widget.settings_manager is not None:
        try:
            raw = widget.settings_manager.get('display.hw_accel', True)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            raw = True
        hw_accel = SettingsManager.to_bool(raw, True)

    # In pure software environments (no GL support at all), mark overlays
    # as ready so diagnostics remain consistent. When GL is available, we
    # defer all overlay initialization to transition-time prepaint.
    if not hw_accel and GL is None:
        widget._mark_all_overlays_ready(GL_OVERLAY_KEYS, stage="software_prewarm")

    # Show as borderless fullscreen instead of exclusive fullscreen.
    widget.show()
    try:
        widget.raise_()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    try:
        focus_policy = widget.focusPolicy()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        focus_policy = Qt.FocusPolicy.StrongFocus

    focusable = focus_policy != Qt.FocusPolicy.NoFocus

    try:
        if focusable:
            widget.activateWindow()
            try:
                handle = widget.windowHandle()
                if handle is not None:
                    handle.requestActivate()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                widget.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                try:
                    widget.setFocus()
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        else:
            try:
                handle = widget.windowHandle()
                if handle is not None:
                    handle.setFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    widget._handle_screen_change(screen)
    # Reconfigure when screen changes
    try:
        handle = widget.windowHandle()
        if handle is not None:
            handle.screenChanged.connect(widget._handle_screen_change)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    # Ensure shared GL compositor and reuse any persistent overlays
    try:
        widget._ensure_gl_compositor()
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during show", exc_info=True)

    widget._reuse_persistent_gl_overlays()

    # Setup overlay widgets AFTER geometry is set
    if widget.settings_manager:
        widget._setup_widgets()

    # Prewarm context menu on the UI thread so first right-click does not
    # pay the QMenu construction/polish cost.
    try:
        if widget._thread_manager is not None:
            widget._thread_manager.single_shot(200, widget._prewarm_context_menu)
        else:
            logger.error("[DISPLAY_WIDGET] ThreadManager not injected; skipping context menu prewarm")
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def prewarm_context_menu(widget) -> None:
    """Create the context menu ahead of time to avoid first-click lag."""
    try:
        if getattr(widget, "_context_menu_prewarmed", False):
            return
        if widget._context_menu is not None:
            widget._context_menu_prewarmed = True
            return
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return

    try:
        current_transition, random_enabled = widget._refresh_transition_state_from_settings()
        hard_exit = widget._is_hard_exit_enabled()
        dimming_enabled = False
        if widget.settings_manager:
            dimming_enabled = SettingsManager.to_bool(
                widget.settings_manager.get("accessibility.dimming.enabled", False), False
            )

        widget._context_menu = ScreensaverContextMenu(
            parent=widget,
            current_transition=current_transition,
            random_enabled=random_enabled,
            dimming_enabled=dimming_enabled,
            hard_exit_enabled=hard_exit,
            is_mc_build=widget._is_mc_build,
            always_on_top=widget._always_on_top,
        )
        # Connect signals once during construction
        widget._context_menu.previous_requested.connect(widget.previous_requested.emit)
        widget._context_menu.next_requested.connect(widget.next_requested.emit)
        widget._context_menu.transition_selected.connect(widget._on_context_transition_selected)
        widget._context_menu.settings_requested.connect(widget.settings_requested.emit)
        widget._context_menu.dimming_toggled.connect(widget._on_context_dimming_toggled)
        widget._context_menu.hard_exit_toggled.connect(widget._on_context_hard_exit_toggled)
        widget._context_menu.always_on_top_toggled.connect(widget._on_context_always_on_top_toggled)
        widget._context_menu.exit_requested.connect(widget._on_context_exit_requested)

        try:
            widget._context_menu.aboutToShow.connect(lambda: widget._invalidate_overlay_effects("menu_about_to_show"))
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        try:
            widget._context_menu.ensurePolished()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        widget._context_menu_prewarmed = True
    except Exception:
        logger.debug("Failed to prewarm context menu", exc_info=True)

def handle_screen_change(widget, screen) -> None:
    """Apply geometry, DPI, and overlay updates for the active screen."""

    if screen is None:
        return

    widget._screen = screen

    try:
        widget._device_pixel_ratio = float(screen.devicePixelRatio())
    except Exception:
        logger.debug("[SCREEN] Failed to read devicePixelRatio", exc_info=True)

    try:
        screen_geom = screen.geometry()
        if screen_geom is not None and screen_geom.isValid():
            geom = screen_geom
            if _FULLSCREEN_COMPAT_WORKAROUND:
                try:
                    if geom.height() > 1:
                        geom.setHeight(geom.height() - 1)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            widget.setGeometry(geom)
    except Exception:
        logger.debug("[SCREEN] Failed to apply screen geometry", exc_info=True)

    try:
        widget._configure_refresh_rate_sync()
    except Exception:
        logger.debug("[SCREEN] Refresh rate sync configuration failed", exc_info=True)

    try:
        widget._ensure_render_surface()
    except Exception:
        logger.debug("[SCREEN] Render surface update failed", exc_info=True)

    try:
        widget._ensure_overlay_stack(stage="screen_change")
    except Exception:
        logger.debug("[SCREEN] Overlay stack update failed", exc_info=True)

    try:
        widget._reuse_persistent_gl_overlays()
    except Exception:
        logger.debug("[SCREEN] Persistent overlay reuse failed", exc_info=True)

    try:
        widget._ensure_gl_compositor()
    except Exception:
        logger.debug("[SCREEN] GL compositor update failed", exc_info=True)

def detect_refresh_rate(widget) -> float:
    try:
        screen = widget._screen
        if screen is None:
            from PySide6.QtGui import QGuiApplication
            screens = QGuiApplication.screens()
            screen = screens[widget.screen_index] if widget.screen_index < len(screens) else QGuiApplication.primaryScreen()
        hz_attr = getattr(screen, 'refreshRate', None)
        rate = float(hz_attr()) if callable(hz_attr) else 60.0
        if not (10.0 <= rate <= 240.0):
            return 60.0
        return rate
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return 60.0

def configure_refresh_rate_sync(widget) -> None:
    detected = int(round(widget._detect_refresh_rate()))
    widget._target_fps = widget._resolve_display_target_fps(detected, adaptive=False)
    if is_perf_metrics_enabled():
        logger.info(
            "[REFRESH_DIAG] source=settings:display.refresh_sync screen=%s detected_hz=%d target_fps=%d",
            widget.screen_index,
            detected,
            widget._target_fps,
        )

    try:
        am = getattr(widget, "_animation_manager", None)
        if am is not None and hasattr(am, 'set_target_fps'):
            am.set_target_fps(widget._target_fps)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def setup_dimming(widget) -> None:
    """Setup background dimming via GL compositor.
    
    Phase 1b: Extracted from _setup_widgets for cleaner delegation.
    """
    if not widget.settings_manager:
        return
    
    dimming_enabled = SettingsManager.to_bool(
        widget.settings_manager.get('accessibility.dimming.enabled', False), False
    )
    try:
        dimming_opacity = int(widget.settings_manager.get('accessibility.dimming.opacity', 30))
        dimming_opacity = max(10, min(90, dimming_opacity))
    except (ValueError, TypeError):
        dimming_opacity = 30
    
    widget._dimming_enabled = dimming_enabled
    widget._dimming_opacity = dimming_opacity / 100.0
    
    comp = getattr(widget, "_gl_compositor", None)
    if comp is not None and hasattr(comp, "set_dimming"):
        comp.set_dimming(dimming_enabled, widget._dimming_opacity)
        logger.debug("GL compositor dimming: enabled=%s, opacity=%d%%", dimming_enabled, dimming_opacity)

def setup_spotify_widgets(widget) -> None:
    """Position Spotify widgets after WidgetManager creates them.
    
    WidgetManager handles creation; this just handles positioning.
    """
    # Position Spotify visualizer if created
    if widget.spotify_visualizer_widget is not None:
        try:
            widget._position_spotify_visualizer()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    
    # Position Spotify volume if created
    if widget.spotify_volume_widget is not None:
        try:
            widget._position_spotify_volume()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    # Position mute button if created
    if getattr(widget, 'mute_button_widget', None) is not None:
        try:
            widget._position_mute_button()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)


def setup_pixel_shift(widget) -> None:
    """Setup pixel shift manager for burn-in prevention.
    
    Phase 1b: Extracted from _setup_widgets for cleaner delegation.
    """
    if not widget.settings_manager:
        return
    
    pixel_shift_enabled = SettingsManager.to_bool(
        widget.settings_manager.get('accessibility.pixel_shift.enabled', False), False
    )
    try:
        pixel_shift_rate = int(widget.settings_manager.get('accessibility.pixel_shift.rate', 1))
        pixel_shift_rate = max(1, min(5, pixel_shift_rate))
    except (ValueError, TypeError):
        pixel_shift_rate = 1
    
    if widget._pixel_shift_manager is None:
        widget._pixel_shift_manager = PixelShiftManager(
            resource_manager=widget._resource_manager,
            thread_manager=widget._thread_manager,
        )
        if widget._thread_manager is not None:
            widget._pixel_shift_manager.set_thread_manager(widget._thread_manager)
        widget._pixel_shift_manager.set_defer_check(lambda: widget.has_running_transition())
    
    widget._pixel_shift_manager.set_shifts_per_minute(pixel_shift_rate)
    
    # Register all overlay widgets
    for attr_name in (
        "clock_widget", "clock2_widget", "clock3_widget",
        "weather_widget", "media_widget", "spotify_visualizer_widget",
        "reddit_widget", "reddit2_widget",
    ):
        child = getattr(widget, attr_name, None)
        if child is not None:
            widget._pixel_shift_manager.register_widget(child)

    # The Spotify volume widget remains anchored to the media card edge; allowing
    # pixel shift to move it independently causes visible desync. It intentionally
    # opts out of pixel shifting until we support grouped offsets.
    
    if pixel_shift_enabled:
        widget._pixel_shift_manager.set_enabled(True)
        logger.debug("Pixel shift enabled (rate=%d/min)", pixel_shift_rate)
    else:
        widget._pixel_shift_manager.set_enabled(False)

def setup_widgets(widget) -> None:
    """Setup overlay widgets via WidgetManager delegation.
    
    Milestone 2: Refactored to delegate widget creation to WidgetManager.
    This reduces DisplayWidget from ~1166 lines of widget setup to ~50 lines.
    """
    if not widget.settings_manager:
        logger.warning("No settings_manager provided - widgets will not be created")
        return

    try:
        # Explicit dot-notation reads kept here for regression coverage.
        widget.settings_manager.get("accessibility.dimming.enabled", False)
        widget.settings_manager.get("accessibility.dimming.opacity", 30)
        widget.settings_manager.get("accessibility.pixel_shift.enabled", False)
        widget.settings_manager.get("accessibility.pixel_shift.rate", 1)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    
    logger.debug("Setting up overlay widgets for screen %d", widget.screen_index)
    
    # Setup dimming first (GL compositor)
    widget._setup_dimming()
    
    # Delegate widget creation to WidgetManager
    if widget._widget_manager is not None:
        widgets_config = widget.settings_manager.get('widgets', {}) if widget.settings_manager else {}
        widget._widget_manager.configure_expected_overlays(widgets_config)
        created = widget._widget_manager.setup_all_widgets(
            widget.settings_manager,
            widget.screen_index,
            widget._thread_manager,
        )
        # Assign created widgets to DisplayWidget attributes
        for attr_name, child_widget in created.items():
            setattr(widget, attr_name, child_widget)
        logger.info("WidgetManager created %d widgets", len(created))
        
        # Initialize all widgets via lifecycle system (Dec 2025)
        initialized_count = widget._widget_manager.initialize_all_widgets()
        if initialized_count > 0:
            logger.debug("[LIFECYCLE] Initialized %d widgets via lifecycle system", initialized_count)
    else:
        logger.warning("No WidgetManager available - widgets will not be created")
        return
    
    # Setup Spotify widgets (complex wiring with media widget)
    widget._setup_spotify_widgets()
    
    # Setup pixel shift manager
    widget._setup_pixel_shift()
    
    # Apply widget stacking for overlapping positions
    widgets = widget.settings_manager.get('widgets', {})
    widget._apply_widget_stacking(widgets if isinstance(widgets, dict) else {})

def apply_widget_stacking(widget, widgets_config: Dict[str, Any]) -> None:
    """Apply vertical stacking offsets - delegates to WidgetManager."""
    if widget._widget_manager is None:
        return
    widget_list = [
        (getattr(widget, 'clock_widget', None), 'clock_widget'),
        (getattr(widget, 'clock2_widget', None), 'clock2_widget'),
        (getattr(widget, 'clock3_widget', None), 'clock3_widget'),
        (getattr(widget, 'weather_widget', None), 'weather_widget'),
        (getattr(widget, 'media_widget', None), 'media_widget'),
        (getattr(widget, 'spotify_visualizer_widget', None), 'spotify_visualizer_widget'),
        (getattr(widget, 'reddit_widget', None), 'reddit_widget'),
        (getattr(widget, 'reddit2_widget', None), 'reddit2_widget'),
        (getattr(widget, 'imgur_widget', None), 'imgur_widget'),
    ]
    widget._widget_manager.apply_widget_stacking(widget_list)

def on_animation_manager_ready(widget, animation_manager) -> None:
    """Hook called by BaseTransition when an AnimationManager is available.

    Allows overlays such as the Spotify Beat Visualizer to subscribe to
    the same high-frequency tick that drives transitions so they do not
    pause or desync during animations.
    """

    try:
        vis = getattr(widget, "spotify_visualizer_widget", None)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        vis = None

    if vis is None:
        return

    try:
        if hasattr(vis, "attach_to_animation_manager"):
            vis.attach_to_animation_manager(animation_manager)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to attach visualizer to AnimationManager", exc_info=True)

def ensure_overlay_stack(widget, stage: str = "runtime") -> None:
    """Refresh overlay geometry and schedule raises to maintain Z-order."""

    overlay_keys = GL_OVERLAY_KEYS + SW_OVERLAY_KEYS
    for attr_name in overlay_keys:
        overlay = getattr(widget, attr_name, None)
        if overlay is None:
            continue
        try:
            set_overlay_geometry(widget, overlay)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        try:
            if overlay.isVisible():
                schedule_raise_when_ready(
                    widget,
                    overlay,
                    stage=f"{stage}_{attr_name}",
                )
            else:
                # Keep stacking order deterministic even if hidden for now
                raise_overlay(widget, overlay)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            continue

    # Ensure primary overlay widgets remain above any GL compositor or
    # legacy transition overlays for the duration of transitions.
    # PERF: Skip if we've already raised overlays this frame (raise_overlay handles this)
    # The raise_overlay function already handles all the necessary raises with
    # frame-rate limiting, so we don't need to duplicate the work here.
    pass

def force_overlay_ready(widget, overlay: QWidget, stage: str, *, gl_available: Optional[bool] = None) -> None:
    """Fallback: force overlay readiness when GL initialization fails."""

    if gl_available is None:
        gl_available = GL is not None

    try:
        # Use GLStateManager if available (preferred approach)
        gl_state = getattr(overlay, "_gl_state", None)
        if gl_state is not None and hasattr(gl_state, "is_ready"):
            if not gl_state.is_ready():
                # Force transition to READY state
                try:
                    from rendering.gl_state_manager import GLContextState
                    gl_state.force_state(GLContextState.READY, "force_overlay_ready")
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        
        # Legacy flag support for overlays not yet using GLStateManager
        lock = getattr(overlay, "_state_lock", None)
        if lock:
            with lock:  # type: ignore[arg-type]
                if hasattr(overlay, "_first_frame_drawn"):
                    overlay._first_frame_drawn = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_has_drawn"):
                    overlay._has_drawn = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_initialized"):
                    overlay._initialized = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_ready"):
                    overlay._ready = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_is_ready"):
                    overlay._is_ready = True  # type: ignore[attr-defined]
        else:
            if hasattr(overlay, "_first_frame_drawn"):
                overlay._first_frame_drawn = True  # type: ignore[attr-defined]
            if hasattr(overlay, "_has_drawn"):
                overlay._has_drawn = True  # type: ignore[attr-defined]
            if hasattr(overlay, "_initialized"):
                overlay._initialized = True  # type: ignore[attr-defined]
            if hasattr(overlay, "_ready"):
                overlay._ready = True  # type: ignore[attr-defined]
            if hasattr(overlay, "_is_ready"):
                overlay._is_ready = True  # type: ignore[attr-defined]
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    try:
        overlay.update()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    try:
        name = overlay.objectName() or overlay.__class__.__name__
        widget.notify_overlay_ready(name, stage, status="forced_ready", gl=bool(gl_available))
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def reuse_persistent_gl_overlays(widget) -> None:
    """Ensure persistent overlays have correct parent and geometry after show."""

    for attr_name in GL_OVERLAY_KEYS:
        overlay = getattr(widget, attr_name, None)
        if overlay is None:
            continue
        try:
            if overlay.parent() is not widget:
                overlay.setParent(widget)
            set_overlay_geometry(widget, overlay)
            overlay.hide()  # stay hidden until transition starts
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            continue


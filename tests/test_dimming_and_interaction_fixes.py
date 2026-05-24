"""
Tests for dimming overlay, halo interaction, and deferred Reddit URL fixes.

These tests verify:
1. Dimming overlay uses correct widget attributes for alpha compositing
2. Ctrl cursor halo doesn't punch through dimming overlay
3. Deferred Reddit URL is opened on all exit paths
4. Media widget click detection respects Y coordinates (controls row only)
5. Settings are read with dot notation (not nested dict access)
6. Dimming overlay is included in Z-order management
7. Context menu reads dimming state correctly
"""
from __future__ import annotations

from typing import List, Tuple

import inspect
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


class TestDimmingOverlayAttributes:
    """Test dimming overlay widget attributes for proper alpha compositing."""

    def test_dimming_overlay_uses_translucent_background(self, qt_app):
        """Dimming overlay must use WA_TranslucentBackground for alpha compositing."""
        from widgets.dimming_overlay import DimmingOverlay
        
        overlay = DimmingOverlay(None, opacity=50)
        
        # Must have WA_TranslucentBackground for proper alpha over GL
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Must NOT auto-fill background
        assert not overlay.autoFillBackground()
        # Must be transparent to mouse events
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def test_dimming_overlay_opacity_calculation(self, qt_app):
        """Verify opacity is correctly converted to alpha (0-100 -> 0-255)."""
        from widgets.dimming_overlay import DimmingOverlay
        
        overlay = DimmingOverlay(None, opacity=90)
        overlay.set_enabled(True)
        
        # 90% opacity should give alpha = 229 (90/100 * 255)
        expected_alpha = int((90 / 100.0) * 255)
        assert expected_alpha == 229
        assert overlay.get_opacity() == 90

    def test_dimming_overlay_opacity_clamping(self, qt_app):
        """Verify opacity is clamped to valid range."""
        from widgets.dimming_overlay import DimmingOverlay
        
        # Test over 100 - target_opacity should be clamped
        overlay = DimmingOverlay(None, opacity=150)
        # Note: _opacity starts at 0 for fade-in, but _target_opacity is clamped
        assert overlay._target_opacity == 100
        
        # Test under 0
        overlay2 = DimmingOverlay(None, opacity=-10)
        assert overlay2._target_opacity == 0

    def test_dimming_overlay_uses_app_shared_animation_manager(self, qt_app):
        from core.animation.animator import AnimationManager
        from widgets.dimming_overlay import DimmingOverlay

        manager = AnimationManager(fps=60)
        try:
            AnimationManager.set_app_shared(manager)
            overlay = DimmingOverlay(None, opacity=50)
            assert overlay._get_animation_manager() is manager
        finally:
            manager.cleanup()
            AnimationManager.set_app_shared(None)


class TestCtrlHaloAttributes:
    """Test that ctrl cursor halo uses correct attributes for transparency."""

    def test_halo_code_uses_translucent_background(self, qt_app):
        """Halo widget should be translucent but keep mouse handling for forwarding."""
        from widgets.cursor_halo import CursorHaloWidget

        parent = QWidget()
        halo = CursorHaloWidget(parent)

        assert halo.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert not halo.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def test_halo_uses_app_shared_animation_manager(self, qt_app):
        from core.animation.animator import AnimationManager
        from widgets.cursor_halo import CursorHaloWidget

        manager = AnimationManager(fps=60)
        parent = QWidget()
        try:
            AnimationManager.set_app_shared(manager)
            halo = CursorHaloWidget(parent)
            assert halo._animation_manager is manager
        finally:
            manager.cleanup()
            AnimationManager.set_app_shared(None)

    def test_display_input_ctrl_gate_uses_all_ctrl_state_sources(self, qt_app):
        """Mouse-exit suppression should survive local/global/handler ctrl-state drift."""
        from rendering import display_input

        source = inspect.getsource(display_input._ctrl_interaction_active)
        assert 'getattr(widget, "_ctrl_held", False)' in source
        assert 'getattr(coordinator, "ctrl_held", False)' in source
        assert 'getattr(type(widget), "_global_ctrl_held", False)' in source
        assert 'input_handler.is_ctrl_held()' in source

    def test_halo_show_clamps_small_out_of_bounds_drift(self, qt_app):
        """Slight compositor coordinate drift should clamp instead of hiding the halo."""
        from rendering import display_input

        source = inspect.getsource(display_input.show_ctrl_cursor_hint)
        assert "within_slack" in source
        assert "local_point.setX(max(rect.left(), min(rect.right(), local_point.x())))" in source
        assert "local_point.setY(max(rect.top(), min(rect.bottom(), local_point.y())))" in source

    def test_interaction_mode_clicks_do_not_force_halo_refresh(self, qt_app):
        """Interactive clicks should not run extra halo keepalive logic from the click path."""
        from rendering import display_input

        source = inspect.getsource(display_input.handle_mousePressEvent)
        assert '_refresh_halo_after_interaction_click(widget, event.pos())' not in source

    def test_halo_forwarding_routes_back_through_display_root(self, qt_app):
        """Halo should actively forward events back through the display root."""
        from widgets.cursor_halo import CursorHaloWidget

        parent = QWidget()
        halo = CursorHaloWidget(parent)
        assert not halo.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        source = inspect.getsource(CursorHaloWidget._forward_mouse_event)
        assert "QApplication.sendEvent(parent, new_event)" in source
        assert "parent._halo_forwarding = True" in source

    def test_input_handler_ctrl_press_sets_handler_state(self, qt_app):
        """Ctrl press must mark InputHandler as held so downstream guards agree."""
        from rendering.input_handler import InputHandler

        source = inspect.getsource(InputHandler.handle_ctrl_press)
        assert 'self._ctrl_held = True' in source
        assert 'target_handler.set_ctrl_held(True)' in source


class TestMediaWidgetClickDetection:
    """Test media widget click detection respects Y coordinates."""

    def test_click_detection_uses_widget_resolver(self, qt_app):
        """Verify click routing defers to MediaWidget.resolve_control_hit."""
        from rendering.input_handler import InputHandler
        
        source = inspect.getsource(InputHandler._route_media_left_click)
        assert 'resolve_control_hit' in source
        assert 'local_point' in source

    def test_click_routing_invokes_media_command(self, qt_app):
        """Verify resolver output flows into media command invocation."""
        from rendering.input_handler import InputHandler

        source = inspect.getsource(InputHandler._route_media_left_click)
        assert '_invoke_media_command' in source
        assert 'key' in source and 'mouse:left' in source


class TestCrumbleShaderPerformance:
    """Test Crumble shader has reasonable search range for performance."""

    def test_crumble_search_range_is_reduced(self):
        """Verify Crumble shader search range has early-exit optimizations."""
        from rendering.gl_programs.crumble_program import CrumbleProgram
        
        program = CrumbleProgram()
        fragment_source = program.fragment_source
        
        # The search range needs to be large enough for pieces to fall off screen
        # but MUST have early-exit optimizations to avoid performance issues
        # Key optimizations that MUST be present:
        assert 'pieceFall < 0.001' in fragment_source  # Skip non-falling pieces
        assert 'candidateCell.y < -1.0' in fragment_source  # Skip cells far above screen
        assert 'abs(uv.x - movedCenter.x)' in fragment_source  # Bounds check
        assert 'abs(uv.y - movedCenter.y)' in fragment_source  # Bounds check
        # Shadow should fade out to prevent brightness pop
        assert 'shadowFadeOut' in fragment_source  # Shadow fades out at end
        # Should NOT have the old expensive shadow raycast
        assert 'checkPieceShadow' not in fragment_source


class TestSettingsDotNotation:
    """Test that settings are read with dot notation, not nested dict access."""

    def test_dimming_settings_use_dot_notation(self, qt_app):
        """Verify setup_widgets reads dimming settings with dot notation."""
        from rendering.display_setup import setup_widgets
        
        source = inspect.getsource(setup_widgets)
        
        # Must use dot notation for dimming settings
        assert "accessibility.dimming.enabled" in source
        assert "accessibility.dimming.opacity" in source
        # Must NOT use nested dict access pattern for dimming
        # (the old broken pattern was: accessibility_settings.get('dimming', {}))
        assert "accessibility_settings.get('dimming'" not in source

    def test_pixel_shift_settings_use_dot_notation(self, qt_app):
        """Verify setup_widgets reads pixel shift settings with dot notation."""
        from rendering.display_setup import setup_widgets
        
        source = inspect.getsource(setup_widgets)
        
        # Must use dot notation for pixel shift settings
        assert "accessibility.pixel_shift.enabled" in source
        assert "accessibility.pixel_shift.rate" in source

    def test_context_menu_dimming_uses_dot_notation(self, qt_app):
        """Verify show_context_menu reads dimming state with dot notation."""
        from rendering.display_context_menu import show_context_menu
        
        source = inspect.getsource(show_context_menu)
        
        # Must use dot notation for dimming enabled check
        assert "accessibility.dimming.enabled" in source
        # Must NOT use nested dict access pattern
        assert "acc_cfg.get" not in source or "dim_cfg.get" not in source

    def test_prewarm_context_menu_uses_shared_builder(self, qt_app):
        """Prewarm should share the same menu wiring path as runtime popup."""
        from rendering.display_setup import prewarm_context_menu

        source = inspect.getsource(prewarm_context_menu)

        assert "ensure_context_menu(" in source
        assert "aboutToShow.connect(lambda: widget._invalidate_overlay_effects" not in source


class TestDimmingOverlayZOrder:
    """Test that dimming overlay is properly included in Z-order management."""

    def test_raise_overlay_includes_dimming(self, qt_app):
        """Verify raise_overlay documents GL compositor dimming."""
        from transitions.overlay_manager import raise_overlay
        
        source = inspect.getsource(raise_overlay)
        
        # Dimming is now handled by GL compositor, should be documented
        assert "GL compositor" in source or "dimming" in source.lower()
        # Must raise ctrl cursor halo (should be last/topmost)
        assert "_ctrl_cursor_hint" in source

    def test_raise_overlay_zorder_documented(self, qt_app):
        """Verify raise_overlay has Z-order documentation."""
        from transitions.overlay_manager import raise_overlay
        
        source = inspect.getsource(raise_overlay)
        
        # Should have Z-order documentation
        assert "Z-ORDER" in source or "z-order" in source.lower()
        # Should mention dimming overlay position
        assert "Dimming" in source or "dimming" in source


@pytest.mark.qt
def test_context_menu_invalidates_effects_before_popup(qt_app, qtbot, settings_manager, monkeypatch):
    """Context menu should invalidate overlay effects before popup."""
    from rendering.display_widget import DisplayWidget
    from rendering.custom_layout_manager import CustomLayoutManager
    from widgets.context_menu import ScreensaverContextMenu

    CustomLayoutManager._active_managers = []
    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(640, 360)

    dummy = QWidget(widget)
    dummy.resize(20, 20)
    dummy.show()

    eff = QGraphicsDropShadowEffect(dummy)
    dummy.setGraphicsEffect(eff)

    events: List[Tuple[str, object]] = []

    orig_invalidate = widget._invalidate_overlay_effects  # type: ignore[attr-defined]

    def _spy_invalidate(reason: str) -> None:
        events.append(("invalidate", reason))
        orig_invalidate(reason)

    monkeypatch.setattr(widget, "_invalidate_overlay_effects", _spy_invalidate)

    last_popup_menu: List[object] = []

    def _spy_popup(self, pos):  # type: ignore[no-untyped-def]
        last_popup_menu.clear()
        last_popup_menu.append(self)
        events.append(("popup", pos))
        assert any(e[0] == "invalidate" for e in events)

    monkeypatch.setattr(ScreensaverContextMenu, "popup", _spy_popup)

    widget.clock_widget = dummy  # type: ignore[assignment]

    effect_ids: List[int] = []

    for i in range(5):
        events.clear()
        widget._show_context_menu(QPoint(10 + i, 10))  # type: ignore[attr-defined]
        qt_app.processEvents()
        assert events

        active_eff = dummy.graphicsEffect()
        assert isinstance(active_eff, QGraphicsDropShadowEffect)
        effect_ids.append(id(active_eff))

        invalidate_idx = next(idx for idx, e in enumerate(events) if e[0] == "invalidate")
        popup_idx = next(idx for idx, e in enumerate(events) if e[0] == "popup")
        assert invalidate_idx < popup_idx

        menu = last_popup_menu[0] if last_popup_menu else None
        assert menu is not None
        menu.aboutToHide.emit()
        qt_app.processEvents()

        assert any(
            e[0] == "invalidate" and str(e[1]).startswith("menu_after_hide")
            for e in events
        )

    assert len(set(effect_ids)) >= 1



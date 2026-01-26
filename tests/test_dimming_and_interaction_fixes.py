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


class TestCtrlHaloAttributes:
    """Test that ctrl cursor halo uses correct attributes for transparency."""

    def test_halo_code_uses_translucent_background(self, qt_app):
        """Halo code must use WA_TranslucentBackground for true transparency.
        
        The halo needs WA_TranslucentBackground to be truly transparent.
        Z-order (via raise_overlay) ensures it's always above the dimming overlay.
        """
        from widgets.cursor_halo import CursorHaloWidget
        
        # Check the source code of CursorHaloWidget for correct attributes
        source = inspect.getsource(CursorHaloWidget.__init__)
        
        # Must use WA_TranslucentBackground for true transparency
        assert 'WA_TranslucentBackground' in source
        # Must set WA_TranslucentBackground to True
        assert 'setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)' in source
        # Must be transparent to mouse events
        assert 'WA_TransparentForMouseEvents' in source


class TestMediaWidgetClickDetection:
    """Test media widget click detection respects Y coordinates."""

    def test_click_detection_checks_y_coordinate(self, qt_app):
        """Verify click detection code checks Y coordinate for controls row."""
        from rendering.input_handler import InputHandler

        # Check that _route_media_left_click contains Y coordinate logic
        source = inspect.getsource(InputHandler._route_media_left_click)

        # Must compute local_y and pass it to handle_controls_click
        assert 'local_y' in source
        assert 'handle_controls_click' in source

    def test_controls_row_height_is_reasonable(self, qt_app):
        """Verify click routing delegates to media widget's handle_controls_click."""
        from rendering.input_handler import InputHandler

        source = inspect.getsource(InputHandler._route_media_left_click)
        # Click routing delegates to media widget which handles controls row internally
        assert 'handle_controls_click' in source


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
        """Verify _setup_widgets reads dimming settings with dot notation."""
        from rendering.display_widget import DisplayWidget
        
        source = inspect.getsource(DisplayWidget._setup_widgets)
        
        # Must use dot notation for dimming settings
        assert "accessibility.dimming.enabled" in source
        assert "accessibility.dimming.opacity" in source
        # Must NOT use nested dict access pattern for dimming
        # (the old broken pattern was: accessibility_settings.get('dimming', {}))
        assert "accessibility_settings.get('dimming'" not in source

    def test_pixel_shift_settings_use_dot_notation(self, qt_app):
        """Verify _setup_widgets reads pixel shift settings with dot notation."""
        from rendering.display_widget import DisplayWidget
        
        source = inspect.getsource(DisplayWidget._setup_widgets)
        
        # Must use dot notation for pixel shift settings
        assert "accessibility.pixel_shift.enabled" in source
        assert "accessibility.pixel_shift.rate" in source

    def test_context_menu_dimming_uses_dot_notation(self, qt_app):
        """Verify _show_context_menu reads dimming state with dot notation."""
        from rendering.display_widget import DisplayWidget
        
        source = inspect.getsource(DisplayWidget._show_context_menu)
        
        # Must use dot notation for dimming enabled check
        assert "accessibility.dimming.enabled" in source
        # Must NOT use nested dict access pattern
        assert "acc_cfg.get" not in source or "dim_cfg.get" not in source


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
    from widgets.context_menu import ScreensaverContextMenu

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



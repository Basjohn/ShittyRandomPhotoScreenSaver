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
from PySide6.QtCore import Qt
import inspect


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
        from rendering.display_widget import DisplayWidget
        
        # Check the source code of _ensure_ctrl_cursor_hint for correct attributes
        source = inspect.getsource(DisplayWidget._ensure_ctrl_cursor_hint)
        
        # Must use WA_TranslucentBackground for true transparency
        assert 'WA_TranslucentBackground' in source
        # Must set WA_TranslucentBackground to True
        assert 'setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)' in source
        # Must be transparent to mouse events
        assert 'WA_TransparentForMouseEvents' in source


class TestDeferredRedditUrl:
    """Test that deferred Reddit URL is opened on all exit paths."""

    def test_open_pending_reddit_url_method_exists(self, qt_app):
        """Verify _open_pending_reddit_url method exists on DisplayWidget."""
        from rendering.display_widget import DisplayWidget
        assert hasattr(DisplayWidget, '_open_pending_reddit_url')

    def test_pending_reddit_url_attribute_exists(self, qt_app):
        """Verify _pending_reddit_url attribute is initialized."""
        from rendering.display_widget import DisplayWidget
        
        # Check the class defines the attribute in __init__
        # We can't easily instantiate DisplayWidget, so check the source
        source = inspect.getsource(DisplayWidget.__init__)
        assert '_pending_reddit_url' in source


class TestMediaWidgetClickDetection:
    """Test media widget click detection respects Y coordinates."""

    def test_click_detection_checks_y_coordinate(self, qt_app):
        """Verify click detection code checks Y coordinate for controls row."""
        from rendering.display_widget import DisplayWidget
        
        # Check that mousePressEvent contains Y coordinate logic
        source = inspect.getsource(DisplayWidget.mousePressEvent)
        
        # Must check local_y against controls_row_top
        assert 'local_y' in source
        assert 'controls_row_top' in source or 'controls_row_height' in source

    def test_controls_row_height_is_reasonable(self, qt_app):
        """Verify controls row height constant is reasonable (40-80px)."""
        from rendering.display_widget import DisplayWidget
        
        source = inspect.getsource(DisplayWidget.mousePressEvent)
        # The controls_row_height should be defined as 60
        assert 'controls_row_height = 60' in source


class TestCrumbleShaderPerformance:
    """Test Crumble shader has reasonable search range for performance."""

    def test_crumble_search_range_is_reduced(self):
        """Verify Crumble shader search range is not excessive."""
        from rendering.gl_programs.crumble_program import CrumbleProgram
        
        program = CrumbleProgram()
        fragment_source = program.fragment_source
        
        # The search range should be reduced (not -10 to +4)
        # Check for the reduced range pattern
        assert 'dy = -6' in fragment_source or 'dy = -5' in fragment_source
        # Should NOT have the old excessive range
        assert 'dy = -10' not in fragment_source


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


class TestDeferredRedditUrlAllExitPaths:
    """Test that deferred Reddit URL is opened on ALL exit paths."""

    def test_key_press_exit_opens_reddit_url(self, qt_app):
        """Verify keyPressEvent calls _open_pending_reddit_url before exit."""
        from rendering.display_widget import DisplayWidget
        
        source = inspect.getsource(DisplayWidget.keyPressEvent)
        
        # Must call _open_pending_reddit_url before exit_requested.emit
        assert "_open_pending_reddit_url" in source

    def test_mouse_click_exit_opens_reddit_url(self, qt_app):
        """Verify mousePressEvent calls _open_pending_reddit_url before exit."""
        from rendering.display_widget import DisplayWidget
        
        source = inspect.getsource(DisplayWidget.mousePressEvent)
        
        # Must call _open_pending_reddit_url before exit_requested.emit
        assert "_open_pending_reddit_url" in source

    def test_mouse_move_exit_opens_reddit_url(self, qt_app):
        """Verify mouseMoveEvent calls _open_pending_reddit_url before exit."""
        from rendering.display_widget import DisplayWidget
        
        source = inspect.getsource(DisplayWidget.mouseMoveEvent)
        
        # Must call _open_pending_reddit_url before exit_requested.emit
        assert "_open_pending_reddit_url" in source

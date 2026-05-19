"""
Tests for MC Context Menu features.

Tests cover:
- Always On Top toggle visibility (MC mode only)
- Signal emission for always on top toggle
- State update methods
"""
import pytest

from widgets.context_menu import ScreensaverContextMenu


class TestContextMenuMCFeatures:
    """Tests for MC-specific context menu features."""
    
    def test_always_on_top_hidden_in_normal_mode(self, qtbot):
        """Test that Always On Top is not shown in normal (non-MC) mode."""
        menu = ScreensaverContextMenu(is_mc_build=False)
        qtbot.addWidget(menu)
        
        # Should not have the on_top_action
        assert menu._on_top_action is None
    
    def test_always_on_top_removed_in_mc_mode(self, qtbot):
        """Test that Always On Top was removed from MC mode per user request."""
        menu = ScreensaverContextMenu(is_mc_build=True)
        qtbot.addWidget(menu)
        
        # _on_top_action was intentionally removed from MC context menu
        assert menu._on_top_action is None
    
    def test_always_on_top_action_none_in_mc_mode(self, qtbot):
        """Test that _on_top_action is None since it was removed."""
        menu = ScreensaverContextMenu(is_mc_build=True, always_on_top=False)
        qtbot.addWidget(menu)
        assert menu._on_top_action is None
    
    def test_update_always_on_top_state_safe_when_removed(self, qtbot):
        """Test that update_always_on_top_state is safe with no action."""
        menu = ScreensaverContextMenu(is_mc_build=True, always_on_top=False)
        qtbot.addWidget(menu)
        
        # Should not raise even though action is None
        menu.update_always_on_top_state(True)
        assert menu._always_on_top is True
    
    def test_update_always_on_top_state_non_mc(self, qtbot):
        """Test that update_always_on_top_state is safe in non-MC mode."""
        menu = ScreensaverContextMenu(is_mc_build=False)
        qtbot.addWidget(menu)
        
        # Should not raise even though _on_top_action is None
        menu.update_always_on_top_state(True)
        
        # Internal state should still update
        assert menu._always_on_top is True

    def test_interaction_mode_locked_in_mc_mode(self, qtbot):
        """MC menus should keep Interaction Mode enabled and non-toggleable."""
        menu = ScreensaverContextMenu(is_mc_build=True, interaction_mode_enabled=False)
        qtbot.addWidget(menu)

        assert menu._interaction_mode_locked is True
        assert menu._interaction_mode_action.isEnabled() is False
        assert menu._interaction_mode_action.isChecked() is True

    def test_interaction_mode_locked_mc_mode_does_not_emit_false(self, qtbot):
        """MC menu should not emit a disabling toggle for Interaction Mode."""
        menu = ScreensaverContextMenu(is_mc_build=True, interaction_mode_enabled=True)
        qtbot.addWidget(menu)

        signals_received = []
        menu.interaction_mode_toggled.connect(lambda v: signals_received.append(v))

        menu._interaction_mode_action.setChecked(False)
        menu._on_interaction_mode_toggled()

        assert signals_received == []
        assert menu._interaction_mode_action.isChecked() is True


class TestContextMenuSignals:
    """Tests for context menu signal emissions."""
    
    def test_dimming_signal(self, qtbot):
        """Test dimming toggle signal."""
        menu = ScreensaverContextMenu()
        qtbot.addWidget(menu)
        
        signals_received = []
        menu.dimming_toggled.connect(lambda v: signals_received.append(v))
        
        menu._dimming_action.setChecked(True)
        menu._on_dimming_toggled()
        
        assert len(signals_received) == 1
        assert signals_received[0] is True
    
    def test_interaction_mode_signal(self, qtbot):
        """Test Interaction Mode toggle signal."""
        menu = ScreensaverContextMenu()
        qtbot.addWidget(menu)
        
        signals_received = []
        menu.interaction_mode_toggled.connect(lambda v: signals_received.append(v))
        
        menu._interaction_mode_action.setChecked(True)
        menu._on_interaction_mode_toggled()
        
        assert len(signals_received) == 1
        assert signals_received[0] is True
    
    def test_exit_signal(self, qtbot):
        """Test exit request signal."""
        menu = ScreensaverContextMenu()
        qtbot.addWidget(menu)
        
        signals_received = []
        menu.exit_requested.connect(lambda: signals_received.append(True))
        
        menu.exit_requested.emit()

        assert len(signals_received) == 1

    def test_reset_edit_mode_signal(self, qtbot):
        """Edit-mode reset emits the dedicated authored-layout reset signal."""
        menu = ScreensaverContextMenu()
        qtbot.addWidget(menu)

        signals_received = []
        menu.reset_edit_mode_requested.connect(lambda: signals_received.append(True))

        menu.reset_edit_mode_requested.emit()

        assert len(signals_received) == 1

    def test_edit_mode_state_shows_reset_action_only_when_active(self, qtbot):
        menu = ScreensaverContextMenu()
        qtbot.addWidget(menu)

        menu.update_edit_mode_state(False)
        assert menu._reset_edit_mode_action.isVisible() is False

        menu.update_edit_mode_state(True)
        assert menu._reset_edit_mode_action.isVisible() is True


class TestContextMenuTransitions:
    """Tests for transition selection in context menu."""
    
    def test_transition_selection(self, qtbot):
        """Test transition selection signal."""
        menu = ScreensaverContextMenu(current_transition="Crossfade")
        qtbot.addWidget(menu)
        
        signals_received = []
        menu.transition_selected.connect(lambda v: signals_received.append(v))
        
        menu._on_transition_selected("Slide")
        
        assert len(signals_received) == 1
        assert signals_received[0] == "Slide"
    
    def test_update_current_transition(self, qtbot):
        """Test updating current transition."""
        menu = ScreensaverContextMenu(current_transition="Crossfade")
        qtbot.addWidget(menu)
        
        menu.update_current_transition("Ripple")
        
        assert menu._current_transition == "Ripple"
        # Check that the action is checked
        assert menu._transition_actions["Ripple"].isChecked()
        assert not menu._transition_actions["Crossfade"].isChecked()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

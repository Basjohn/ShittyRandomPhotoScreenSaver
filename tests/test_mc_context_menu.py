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
    
    def test_always_on_top_visible_in_mc_mode(self, qtbot):
        """Test that Always On Top is shown in MC mode."""
        menu = ScreensaverContextMenu(is_mc_build=True)
        qtbot.addWidget(menu)
        
        # Should have the on_top_action
        assert menu._on_top_action is not None
        assert menu._on_top_action.isCheckable()
    
    def test_always_on_top_initial_state_false(self, qtbot):
        """Test that Always On Top starts unchecked by default."""
        menu = ScreensaverContextMenu(is_mc_build=True, always_on_top=False)
        qtbot.addWidget(menu)
        
        assert menu._on_top_action is not None
        assert not menu._on_top_action.isChecked()
    
    def test_always_on_top_initial_state_true(self, qtbot):
        """Test that Always On Top can start checked."""
        menu = ScreensaverContextMenu(is_mc_build=True, always_on_top=True)
        qtbot.addWidget(menu)
        
        assert menu._on_top_action is not None
        assert menu._on_top_action.isChecked()
    
    def test_always_on_top_signal_emitted(self, qtbot):
        """Test that toggling Always On Top emits signal."""
        menu = ScreensaverContextMenu(is_mc_build=True, always_on_top=False)
        qtbot.addWidget(menu)
        
        signals_received = []
        menu.always_on_top_toggled.connect(lambda v: signals_received.append(v))
        
        # Simulate toggle
        menu._on_top_action.setChecked(True)
        menu._on_always_on_top_toggled()
        
        assert len(signals_received) == 1
        assert signals_received[0] is True
    
    def test_update_always_on_top_state(self, qtbot):
        """Test updating always on top state programmatically."""
        menu = ScreensaverContextMenu(is_mc_build=True, always_on_top=False)
        qtbot.addWidget(menu)
        
        assert not menu._on_top_action.isChecked()
        
        menu.update_always_on_top_state(True)
        
        assert menu._on_top_action.isChecked()
        assert menu._always_on_top is True
    
    def test_update_always_on_top_state_non_mc(self, qtbot):
        """Test that update_always_on_top_state is safe in non-MC mode."""
        menu = ScreensaverContextMenu(is_mc_build=False)
        qtbot.addWidget(menu)
        
        # Should not raise even though _on_top_action is None
        menu.update_always_on_top_state(True)
        
        # Internal state should still update
        assert menu._always_on_top is True


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
    
    def test_hard_exit_signal(self, qtbot):
        """Test hard exit toggle signal."""
        menu = ScreensaverContextMenu()
        qtbot.addWidget(menu)
        
        signals_received = []
        menu.hard_exit_toggled.connect(lambda v: signals_received.append(v))
        
        menu._hard_exit_action.setChecked(True)
        menu._on_hard_exit_toggled()
        
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

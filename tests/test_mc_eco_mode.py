"""
Tests for MC Eco Mode Manager.

Tests cover:
- Eco Mode state transitions
- Visibility detection and occlusion calculation
- Pause/resume of transitions and visualizer
- Isolation from "On Top" mode
- Statistics tracking
"""
import pytest
from unittest.mock import MagicMock

from core.eco_mode import (
    EcoModeManager,
    EcoModeState,
    EcoModeConfig,
    EcoModeStats,
    is_mc_build,
)


class TestEcoModeState:
    """Tests for Eco Mode state enum."""
    
    def test_states_exist(self):
        """Test all expected states exist."""
        assert EcoModeState.DISABLED is not None
        assert EcoModeState.MONITORING is not None
        assert EcoModeState.ECO_ACTIVE is not None


class TestEcoModeConfig:
    """Tests for Eco Mode configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = EcoModeConfig()
        assert config.enabled is True
        assert config.occlusion_threshold == 0.95
        assert config.check_interval_ms == 1000
        assert config.recovery_delay_ms == 100
        assert config.pause_transitions is True
        assert config.pause_visualizer is True
        assert config.pause_prefetch is False
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = EcoModeConfig(
            enabled=False,
            occlusion_threshold=0.80,
            check_interval_ms=500,
        )
        assert config.enabled is False
        assert config.occlusion_threshold == 0.80
        assert config.check_interval_ms == 500


class TestEcoModeStats:
    """Tests for Eco Mode statistics."""
    
    def test_initial_stats(self):
        """Test initial statistics are zero."""
        stats = EcoModeStats()
        assert stats.activations == 0
        assert stats.deactivations == 0
        assert stats.total_eco_time_ms == 0.0
    
    def test_record_activation(self):
        """Test recording an activation."""
        stats = EcoModeStats()
        stats.record_activation()
        assert stats.activations == 1
        assert stats.last_activation_ts > 0
    
    def test_record_deactivation(self):
        """Test recording a deactivation."""
        stats = EcoModeStats()
        stats.record_activation()
        stats.record_deactivation()
        assert stats.deactivations == 1
        assert stats.total_eco_time_ms >= 0


class TestEcoModeManager:
    """Tests for Eco Mode Manager."""
    
    def test_initial_state(self):
        """Test initial state is DISABLED."""
        manager = EcoModeManager()
        assert manager.get_state() == EcoModeState.DISABLED
        assert not manager.is_eco_active()
    
    def test_set_always_on_top_disables(self):
        """Test that setting always-on-top disables Eco Mode."""
        manager = EcoModeManager()
        manager.set_always_on_top(True)
        assert manager.get_state() == EcoModeState.DISABLED
    
    def test_set_always_on_top_enables_monitoring(self):
        """Test that clearing always-on-top enables monitoring."""
        manager = EcoModeManager()
        manager.set_always_on_top(True)
        manager.set_always_on_top(False)
        assert manager.get_state() == EcoModeState.MONITORING
    
    def test_disabled_config_prevents_monitoring(self):
        """Test that disabled config prevents monitoring."""
        config = EcoModeConfig(enabled=False)
        manager = EcoModeManager(config)
        manager.start_monitoring()
        assert manager.get_state() == EcoModeState.DISABLED
    
    def test_on_top_prevents_monitoring(self):
        """Test that always-on-top prevents monitoring."""
        manager = EcoModeManager()
        manager.set_always_on_top(True)
        manager.start_monitoring()
        assert manager.get_state() == EcoModeState.DISABLED
    
    def test_stop_monitoring_deactivates(self):
        """Test that stopping monitoring deactivates Eco Mode."""
        manager = EcoModeManager()
        manager.start_monitoring()
        manager.stop_monitoring()
        assert manager.get_state() == EcoModeState.DISABLED
    
    def test_get_stats(self):
        """Test getting statistics."""
        manager = EcoModeManager()
        stats = manager.get_stats()
        assert isinstance(stats, EcoModeStats)
    
    def test_cleanup(self):
        """Test cleanup stops monitoring."""
        manager = EcoModeManager()
        manager.start_monitoring()
        manager.cleanup()
        assert manager.get_state() == EcoModeState.DISABLED


class TestEcoModeComponents:
    """Tests for component integration."""
    
    def test_set_display_widget(self):
        """Test setting display widget."""
        manager = EcoModeManager()
        mock_widget = MagicMock()
        manager.set_display_widget(mock_widget)
        assert manager._display_widget is mock_widget
    
    def test_set_transition_controller(self):
        """Test setting transition controller."""
        manager = EcoModeManager()
        mock_controller = MagicMock()
        manager.set_transition_controller(mock_controller)
        assert manager._transition_controller is mock_controller
    
    def test_set_visualizer(self):
        """Test setting visualizer."""
        manager = EcoModeManager()
        mock_visualizer = MagicMock()
        manager.set_visualizer(mock_visualizer)
        assert manager._visualizer is mock_visualizer
    
    def test_set_prefetch_callbacks(self):
        """Test setting prefetch callbacks."""
        manager = EcoModeManager()
        pause_cb = MagicMock()
        resume_cb = MagicMock()
        manager.set_prefetch_callbacks(pause_cb, resume_cb)
        assert manager._prefetch_pause_callback is pause_cb
        assert manager._prefetch_resume_callback is resume_cb


class TestEcoModeIsolation:
    """Tests for Eco Mode isolation from On Top mode."""
    
    def test_on_top_deactivates_eco(self):
        """Test that switching to on-top deactivates Eco Mode."""
        manager = EcoModeManager()
        
        # Simulate Eco Mode being active
        manager._state = EcoModeState.ECO_ACTIVE
        
        # Switch to on-top
        manager.set_always_on_top(True)
        
        # Should be disabled now
        assert manager.get_state() == EcoModeState.DISABLED
    
    def test_eco_never_activates_when_on_top(self):
        """Test that Eco Mode never activates when on top."""
        manager = EcoModeManager()
        manager.set_always_on_top(True)
        
        # Try to check visibility (would normally trigger Eco Mode)
        manager._check_visibility()
        
        # Should still be disabled
        assert manager.get_state() == EcoModeState.DISABLED


class TestIsMcBuild:
    """Tests for MC build detection."""
    
    def test_is_mc_build_returns_bool(self):
        """Test that is_mc_build returns a boolean."""
        result = is_mc_build()
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

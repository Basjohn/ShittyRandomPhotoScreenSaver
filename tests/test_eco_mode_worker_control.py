"""
Tests for EcoModeManager worker control integration.

Tests the P1 fix from the architectural audit that stops/restarts
workers when eco mode activates/deactivates to save CPU.
"""

import pytest
from unittest.mock import MagicMock

from core.eco_mode import EcoModeManager, EcoModeState, EcoModeConfig


class TestEcoModeWorkerControl:
    """Tests for eco mode worker control integration."""

    def test_set_process_supervisor(self):
        """set_process_supervisor should store the supervisor reference."""
        manager = EcoModeManager()
        mock_supervisor = MagicMock()
        
        manager.set_process_supervisor(mock_supervisor)
        
        assert manager._process_supervisor is mock_supervisor

    def test_workers_stop_on_eco_activate(self):
        """Workers should stop when eco mode activates."""
        manager = EcoModeManager(EcoModeConfig(
            occlusion_threshold=0.5,
            pause_transitions=False,
            pause_visualizer=False,
            pause_prefetch=False,
        ))
        
        mock_supervisor = MagicMock()
        mock_supervisor.is_running.return_value = True
        mock_supervisor.stop.return_value = True
        
        manager.set_process_supervisor(mock_supervisor)
        manager._state = EcoModeState.MONITORING
        
        # Activate eco mode
        manager._activate_eco_mode(0.8)
        
        # Should have called stop for IMAGE and FFT workers
        assert mock_supervisor.stop.call_count >= 1
        assert manager._state == EcoModeState.ECO_ACTIVE

    def test_workers_restart_on_eco_deactivate(self):
        """Workers should restart when eco mode deactivates."""
        manager = EcoModeManager(EcoModeConfig(
            occlusion_threshold=0.5,
            pause_transitions=False,
            pause_visualizer=False,
            pause_prefetch=False,
        ))
        
        mock_supervisor = MagicMock()
        mock_supervisor.is_running.return_value = True
        mock_supervisor.stop.return_value = True
        mock_supervisor.start.return_value = True
        
        manager.set_process_supervisor(mock_supervisor)
        manager._state = EcoModeState.MONITORING
        
        # Activate eco mode first
        manager._activate_eco_mode(0.8)
        
        # Reset mock to track restart calls
        mock_supervisor.start.reset_mock()
        
        # Deactivate eco mode
        manager._deactivate_eco_mode("test")
        
        # Should have called start for workers that were running
        assert mock_supervisor.start.call_count >= 1
        assert manager._state == EcoModeState.MONITORING

    def test_workers_not_stopped_without_supervisor(self):
        """No errors should occur if supervisor not set."""
        manager = EcoModeManager(EcoModeConfig(
            occlusion_threshold=0.5,
        ))
        
        # No supervisor set
        manager._state = EcoModeState.MONITORING
        
        # Should not raise
        manager._activate_eco_mode(0.8)
        assert manager._state == EcoModeState.ECO_ACTIVE

    def test_workers_track_running_state(self):
        """Should track which workers were running before stopping."""
        manager = EcoModeManager(EcoModeConfig(
            occlusion_threshold=0.5,
            pause_transitions=False,
            pause_visualizer=False,
            pause_prefetch=False,
        ))
        
        mock_supervisor = MagicMock()
        # IMAGE running, FFT not running
        def is_running_side_effect(worker_type):
            return worker_type.value == "image"
        mock_supervisor.is_running.side_effect = is_running_side_effect
        mock_supervisor.stop.return_value = True
        
        manager.set_process_supervisor(mock_supervisor)
        manager._state = EcoModeState.MONITORING
        
        # Activate eco mode
        manager._activate_eco_mode(0.8)
        
        # Should have tracked which workers were running
        assert len(manager._workers_were_running) > 0

    def test_only_running_workers_restarted(self):
        """Only workers that were running should be restarted."""
        manager = EcoModeManager(EcoModeConfig(
            occlusion_threshold=0.5,
            pause_transitions=False,
            pause_visualizer=False,
            pause_prefetch=False,
        ))
        
        mock_supervisor = MagicMock()
        # Only IMAGE was running
        def is_running_side_effect(worker_type):
            return worker_type.value == "image"
        mock_supervisor.is_running.side_effect = is_running_side_effect
        mock_supervisor.stop.return_value = True
        mock_supervisor.start.return_value = True
        
        manager.set_process_supervisor(mock_supervisor)
        manager._state = EcoModeState.MONITORING
        
        # Activate then deactivate
        manager._activate_eco_mode(0.8)
        mock_supervisor.start.reset_mock()
        manager._deactivate_eco_mode("test")
        
        # Should only restart IMAGE (the one that was running)
        start_calls = [call[0][0].value for call in mock_supervisor.start.call_args_list]
        assert "image" in start_calls
        # FFT should not be restarted since it wasn't running
        assert start_calls.count("fft") == 0 or "fft" not in start_calls


class TestEcoModeWorkerControlExceptions:
    """Tests for exception handling in worker control."""

    def test_stop_exception_handled(self):
        """Exceptions during worker stop should be handled gracefully."""
        manager = EcoModeManager(EcoModeConfig(
            occlusion_threshold=0.5,
            pause_transitions=False,
            pause_visualizer=False,
            pause_prefetch=False,
        ))
        
        mock_supervisor = MagicMock()
        mock_supervisor.is_running.return_value = True
        mock_supervisor.stop.side_effect = RuntimeError("Stop failed")
        
        manager.set_process_supervisor(mock_supervisor)
        manager._state = EcoModeState.MONITORING
        
        # Should not raise
        manager._activate_eco_mode(0.8)
        assert manager._state == EcoModeState.ECO_ACTIVE

    def test_start_exception_handled(self):
        """Exceptions during worker start should be handled gracefully."""
        manager = EcoModeManager(EcoModeConfig(
            occlusion_threshold=0.5,
            pause_transitions=False,
            pause_visualizer=False,
            pause_prefetch=False,
        ))
        
        mock_supervisor = MagicMock()
        mock_supervisor.is_running.return_value = True
        mock_supervisor.stop.return_value = True
        mock_supervisor.start.side_effect = RuntimeError("Start failed")
        
        manager.set_process_supervisor(mock_supervisor)
        manager._state = EcoModeState.MONITORING
        
        # Activate then deactivate
        manager._activate_eco_mode(0.8)
        
        # Should not raise
        manager._deactivate_eco_mode("test")
        assert manager._state == EcoModeState.MONITORING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

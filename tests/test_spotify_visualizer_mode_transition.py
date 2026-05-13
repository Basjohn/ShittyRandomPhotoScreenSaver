"""Tests for Spotify visualizer mode transition logic."""

import pytest


def test_on_mode_fade_out_complete_clears_bar_arrays_before_prepare_engine_reset(monkeypatch):
    """Prove the old-mode display bars cannot survive into prepare_engine_for_mode_reset()."""
    from widgets.spotify_visualizer import mode_transition
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    observed = {}

    class FakeWidget:
        _bar_count = 4
        _display_bars = [0.9, 0.8, 0.7, 0.6]
        _target_bars = [0.8, 0.7, 0.6, 0.5]
        _visual_bars = [0.7, 0.6, 0.5, 0.4]
        _per_bar_energy = [0.6, 0.5, 0.4, 0.3]

        _vis_mode = VisualizerMode.SPECTRUM
        _mode_transition_pending = None
        _mode_teardown_state = "fading_out"
        _mode_transition_phase = 1
        _pending_shadow_cache_invalidation = False
        _mode_teardown_block_until_ready = False
        _mode_teardown_wait_started_ts = 0.0
        _mode_teardown_target_generation = -1

        def _clear_gl_overlay(self):
            pass

        def _clear_runtime_bar_state(self):
            self._display_bars = [0.0] * self._bar_count
            self._target_bars = [0.0] * self._bar_count
            self._visual_bars = [0.0] * self._bar_count
            self._per_bar_energy = [0.0] * self._bar_count

    widget = FakeWidget()

    def fake_prepare_engine_for_mode_reset(w):
        observed["display"] = list(w._display_bars)
        observed["target"] = list(w._target_bars)
        observed["visual"] = list(w._visual_bars)
        observed["energy"] = list(w._per_bar_energy)

    monkeypatch.setattr(mode_transition, "prepare_engine_for_mode_reset", fake_prepare_engine_for_mode_reset)

    mode_transition.on_mode_fade_out_complete(widget)

    assert max(observed["display"]) == 0.0
    assert max(observed["target"]) == 0.0
    assert max(observed["visual"]) == 0.0
    assert max(observed["energy"]) == 0.0


def test_reset_mode_owned_runtime_state_clears_runtime_bar_arrays():
    """Prevent future regressions where someone calls the reset helper without also calling _clear_runtime_bar_state()."""
    from widgets.spotify_visualizer.mode_transition import reset_mode_owned_runtime_state

    class FakeWidget:
        _bar_count = 4
        _display_bars = [0.9, 0.8, 0.7, 0.6]
        _target_bars = [0.8, 0.7, 0.6, 0.5]
        _visual_bars = [0.7, 0.6, 0.5, 0.4]
        _per_bar_energy = [0.6, 0.5, 0.4, 0.3]
        _has_pushed_first_frame = True
        _last_gpu_geom = object()
        _last_gpu_fade_sent = 0.5
        _bubble_simulation = None

        # Source tracking fields
        _display_bars_source_generation = 2
        _display_bars_source_activation = 2
        _target_bars_source_generation = 2
        _target_bars_source_activation = 2
        _visual_bars_source_generation = 2
        _visual_bars_source_activation = 2
        _per_bar_energy_source_generation = 2
        _per_bar_energy_source_activation = 2

    widget = FakeWidget()

    reset_mode_owned_runtime_state(widget, reason="test")

    assert widget._display_bars == [0.0, 0.0, 0.0, 0.0]
    assert widget._target_bars == [0.0, 0.0, 0.0, 0.0]
    assert widget._visual_bars == [0.0, 0.0, 0.0, 0.0]
    assert widget._per_bar_energy == [0.0, 0.0, 0.0, 0.0]
    assert widget._has_pushed_first_frame is False
    assert widget._last_gpu_geom is None
    assert widget._last_gpu_fade_sent == -1.0

    # Source tracking fields should be reset to -1
    assert widget._display_bars_source_generation == -1
    assert widget._display_bars_source_activation == -1
    assert widget._target_bars_source_generation == -1
    assert widget._target_bars_source_activation == -1
    assert widget._visual_bars_source_generation == -1
    assert widget._visual_bars_source_activation == -1
    assert widget._per_bar_energy_source_generation == -1
    assert widget._per_bar_energy_source_activation == -1


def test_prepare_engine_for_mode_reset_does_not_call_replay_engine_config():
    """Ensure the previous technical-config cleanup remains intact."""
    from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    class FakeEngine:
        def cancel_pending_compute_tasks(self):
            pass

        def reset_smoothing_state(self):
            pass

        def reset_floor_state(self):
            pass

        def set_smoothing(self, value):
            pass

        def set_playback_state(self, value):
            pass

        def get_generation_id(self):
            return 7

    class FakeWidget:
        _engine = FakeEngine()
        _bar_count = 4
        _vis_mode = VisualizerMode.SPECTRUM
        _smoothing = 0.18
        _spotify_playing = False
        _mode_teardown_target_generation = -1
        _settings_model = None

        replay_called = False
        technical_called = False
        full_called = False

        def _apply_full_runtime_config_for_mode(self, mode, reason):
            self.full_called = True

        def _replay_engine_config(self, engine):
            self.replay_called = True

        def _apply_technical_config_for_mode(self, mode, reason):
            self.technical_called = True

        def _get_mode_technical_config(self, mode):
            return {
                "dynamic_floor": True,
                "manual_floor": 0.45,
                "sensitivity": 1.0,
                "audio_block_size": 128,
                "input_gain": 1.1,
            }

        def _track_engine_generation(self, engine):
            pass

    widget = FakeWidget()

    prepare_engine_for_mode_reset(widget)

    assert widget.full_called is True
    assert widget.technical_called is True
    assert widget.replay_called is False


def test_stale_activation_frame_cannot_commit_display_bars_after_mode_reset():
    """Prove an old activation/generation cannot write bars after a mode reset."""
    from widgets.spotify_visualizer.mode_transition import reset_mode_owned_runtime_state
    from widgets.spotify_visualizer.tick_pipeline import consume_engine_bars

    class FakeEngine:
        def __init__(self):
            self._latest_generation_with_frame = 4
            self._generation_id = 4
            self._activation_id = 2
            self._smoothed = [0.9, 0.8, 0.7, 0.6]

        def tick(self):
            return None

        def get_latest_generation_with_frame(self):
            return self._latest_generation_with_frame

        def get_activation_id(self):
            return self._activation_id

        def get_smoothed_bars(self):
            return list(self._smoothed)

        def get_generation_id(self):
            return self._generation_id

    class FakeWidget:
        _bar_count = 4
        _display_bars = [0.0, 0.0, 0.0, 0.0]
        _target_bars = [0.0, 0.0, 0.0, 0.0]
        _visual_bars = [0.0, 0.0, 0.0, 0.0]
        _per_bar_energy = [0.0, 0.0, 0.0, 0.0]

        # Source tracking fields - initially set to activation 2
        _display_bars_source_generation = 2
        _display_bars_source_activation = 2
        _target_bars_source_generation = 2
        _target_bars_source_activation = 2
        _visual_bars_source_generation = 2
        _visual_bars_source_activation = 2
        _per_bar_energy_source_generation = 2
        _per_bar_energy_source_activation = 2
        _has_pushed_first_frame = False
        _last_gpu_geom = None
        _last_gpu_fade_sent = -1.0
        _bubble_simulation = None
        _spotify_playing = True
        _vis_mode_str = "spectrum"
        _waiting_for_fresh_engine_frame = True
        _pending_engine_generation = 5
        _pending_engine_activation_id = 3
        _latency_pending_probe = []
        _engine = FakeEngine()

        def _log_audio_latency_metrics(self, engine, now_ts, force_reason=None):
            return None

    widget = FakeWidget()

    reset_mode_owned_runtime_state(widget, reason="mode_reset")

    assert widget._display_bars_source_activation == -1
    assert widget._target_bars_source_activation == -1
    assert widget._visual_bars_source_activation == -1
    assert widget._per_bar_energy_source_activation == -1

    changed, any_nonzero = consume_engine_bars(widget, now_ts=100.0)

    assert changed is False
    assert any_nonzero is False
    assert widget._display_bars == [0.0, 0.0, 0.0, 0.0]
    assert widget._display_bars_source_activation == -1
    assert widget._waiting_for_fresh_engine_frame is True

    widget._engine._latest_generation_with_frame = 5
    widget._engine._generation_id = 5
    widget._engine._activation_id = 3

    changed, any_nonzero = consume_engine_bars(widget, now_ts=101.0)

    assert changed is True
    assert any_nonzero is True
    assert widget._waiting_for_fresh_engine_frame is False
    assert widget._display_bars == pytest.approx([0.9, 0.8, 0.7, 0.6])
    assert widget._display_bars_source_generation == 5
    assert widget._display_bars_source_activation == 3

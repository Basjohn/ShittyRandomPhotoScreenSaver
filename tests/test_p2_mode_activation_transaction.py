"""P2-MODE-ACTIVATION: one target activation transaction per mode switch.

The installed run showed every mode switch performing three complete runtime
configuration passes - ``mode_switch``, ``mode_fade_out_complete`` and
``mode_prepare_reset`` - plus duplicate engine-generation churn. Each of those
call sites is the ONLY apply for some entry shape, so they are guarded by a
single-use transaction stamp rather than deleted:

* a real mode change stamps at ``mode_switch``, and the later two skip;
* a same-mode preset cycle never stamps, so its fade-out apply still runs;
* a plain engine reset or settings apply never stamps, so it still applies.

These bars pin that, and pin that the stamp cannot leak past its own switch -
which would make a later preset cycle silently skip config it needs, and was the
exact failure encountered while building this.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer import mode_transition


@pytest.fixture
def modes():
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    return VisualizerMode


class _Engine:
    def __init__(self):
        self.generation = 5
        self.started = 0
        self.smoothing_resets = 0

    def cancel_pending_compute_tasks(self):
        pass

    def reset_smoothing_state(self):
        self.smoothing_resets += 1

    def reset_floor_state(self):
        pass

    def set_smoothing(self, value):
        pass

    def set_playback_state(self, playing):
        pass

    def ensure_started(self):
        self.started += 1

    def get_generation_id(self):
        return self.generation


def _widget(modes, *, mode=None, stamp=None):
    engine = _Engine()
    calls: list[tuple] = []

    class W:
        _engine = engine
        _bar_count = 24
        _vis_mode = mode or modes.SPECTRUM
        _vis_mode_str = "spectrum"
        _smoothing = 0.18
        _spotify_playing = False
        _mode_teardown_target_generation = -1
        _settings_model = SimpleNamespace()
        _mode_activation_committed_for = stamp
        _technical_config_cache: dict = {}

        def _apply_full_runtime_config_for_mode(self, m, reason):
            calls.append(("full", m, reason))

        def _apply_technical_config_for_mode(self, m, reason):
            calls.append(("technical", m, reason))

        def _build_technical_cache(self, model):
            calls.append(("cache",))
            return {}

        def _get_mode_technical_config(self, m):
            return {"audio_block_size": 128}

        def _reset_latency_diagnostics(self):
            pass

        def _track_engine_generation(self, e):
            calls.append(("generation", e.get_generation_id()))

        def _log_active_render_state_snapshot(self, reason):
            pass

    return W(), calls, engine


class TestSingleTransactionPerModeSwitch:
    def test_committed_transaction_suppresses_the_reset_applies(self, modes):
        """The switch's own reset must not repeat the transaction's work."""
        widget, calls, _engine = _widget(
            modes, mode=modes.BUBBLE, stamp=modes.BUBBLE
        )
        mode_transition.prepare_engine_for_mode_reset(widget)

        assert not [c for c in calls if c[0] == "full"], (
            "the full runtime apply belongs to the activation transaction"
        )
        assert not [c for c in calls if c[0] == "technical"], (
            "repeating technical config restarted audio and advanced a second "
            "engine generation"
        )
        assert not [c for c in calls if c[0] == "cache"]

    def test_exactly_one_engine_generation_advance_per_switch(self, modes):
        widget, calls, _engine = _widget(
            modes, mode=modes.BUBBLE, stamp=modes.BUBBLE
        )
        mode_transition.prepare_engine_for_mode_reset(widget)
        generations = [c for c in calls if c[0] == "generation"]
        assert len(generations) == 1, (
            f"one crossover per switch, saw {len(generations)}"
        )

    def test_audio_capture_starts_at_most_once_per_reset(self, modes):
        widget, _calls, engine = _widget(
            modes, mode=modes.BUBBLE, stamp=modes.BUBBLE
        )
        widget._spotify_playing = True
        mode_transition.prepare_engine_for_mode_reset(widget)
        assert engine.started <= 1


class TestOtherEntryShapesStillApply:
    """Each apply site is the only apply for some shape; none may be lost."""

    def test_plain_engine_reset_still_applies_config(self, modes):
        widget, calls, _engine = _widget(modes, mode=modes.SPECTRUM, stamp=None)
        mode_transition.prepare_engine_for_mode_reset(widget)

        assert [c for c in calls if c[0] == "full"], (
            "a reset outside a transaction is the only apply for that shape"
        )
        assert [c for c in calls if c[0] == "technical"], (
            "technical config is what prevents cross-mode state bleed"
        )

    def test_a_stamp_for_a_different_mode_does_not_suppress(self, modes):
        widget, calls, _engine = _widget(
            modes, mode=modes.SPECTRUM, stamp=modes.BUBBLE
        )
        mode_transition.prepare_engine_for_mode_reset(widget)
        assert [c for c in calls if c[0] == "technical"], (
            "a stamp from another mode must never suppress this mode's config"
        )


class TestStampIsSingleUse:
    def test_stamp_is_cleared_once_consumed(self, modes):
        """A leaked stamp made a later preset cycle skip config it needed."""
        widget, _calls, _engine = _widget(
            modes, mode=modes.BUBBLE, stamp=modes.BUBBLE
        )
        mode_transition.prepare_engine_for_mode_reset(widget)
        assert widget._mode_activation_committed_for is None

    def test_second_reset_after_a_transaction_applies_normally(self, modes):
        widget, calls, _engine = _widget(
            modes, mode=modes.BUBBLE, stamp=modes.BUBBLE
        )
        mode_transition.prepare_engine_for_mode_reset(widget)
        calls.clear()

        # A later preset cycle / settings apply on the same mode.
        mode_transition.prepare_engine_for_mode_reset(widget)
        assert [c for c in calls if c[0] == "technical"], (
            "the stamp must not survive its own transaction"
        )

    def test_a_new_switch_request_clears_any_stale_stamp(self, modes):
        widget = SimpleNamespace(
            _mode_transition_phase=0,
            _vis_mode=modes.SPECTRUM,
            _mode_transition_pending=None,
            _mode_transition_ts=0.0,
            _mode_activation_committed_for=modes.BUBBLE,
        )
        assert mode_transition._begin_mode_transition_request(
            widget, modes.BUBBLE, request_kind="switch"
        )
        assert widget._mode_activation_committed_for is None


class TestResolutionIsNotGloballyCached:
    def test_activation_resolution_is_not_memoised(self):
        """A per-mode cache served a stale preset for the same mode.

        A preset cycle changes the resolved configuration for the SAME mode
        through inputs that are not all visible in the widgets config mapping,
        so caching by mode broke first-visible-frame equivalence. Correctness
        outranks skipping cheap resolution; the real saving comes from applying
        once instead of three times.
        """
        import inspect

        from widgets.spotify_visualizer import activation_runtime

        source = inspect.getsource(activation_runtime.apply_full_runtime_config_for_mode)
        for cache_hint in ("_mode_activation_resolution", "lru_cache", "_cached"):
            assert cache_hint not in source, (
                f"activation resolution must not be memoised ({cache_hint})"
            )

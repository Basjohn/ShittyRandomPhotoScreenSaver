"""P2-R2: one real cross-mode activation, one real engine generation.

The installed Bubble -> Spectrum switch advanced the REAL BeatEngine twice:

    generation=1 activation=1   before the switch
    mode_switch:activation_payload   -> generation=2 activation=2
    smoothing_reset                  -> generation=3 activation=3

and the mode teardown then reached its 1.51-second timeout waiting for target
generation 3.

Two production ownership faults produced it:

1. ``activate_visualization_mode()`` assigned ``widget._vis_mode = mode`` before
   calling the activation apply, so ``apply_resolved_activation_payload()``
   computed ``mode_changed == False`` for a genuine cross-mode switch and never
   ran the target reset inside its transaction;
2. the target reset therefore ran afterwards - from
   ``activate_visualization_mode`` on the direct/Settings path and from
   ``on_mode_fade_out_complete`` on the crossfade path - committing a second
   generation outside the transaction.

The previous bars missed this because they drove ``apply_resolved_activation_payload``
directly rather than the production entry points, so they never reproduced the
premature ``_vis_mode`` assignment.

These bars use the REAL BeatEngine, the REAL activation runtime and the REAL
mode-transition sequence. The only fakes are the settings mapping and the
per-mode technical apply, which stands in for the settings-driven bar-count
change while calling the real engine reconfiguration.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject

from widgets.spotify_visualizer import mode_transition
from widgets.spotify_visualizer.audio_worker import VisualizerMode

BUBBLE_BARS = 48
SPECTRUM_BARS = 35


@pytest.fixture
def np_module():
    return pytest.importorskip("numpy")


class _SettingsManager:
    """The external boundary: the widgets settings mapping."""

    def __init__(self, mode: str):
        self._mode = mode
        self.sets: list[tuple] = []

    def get(self, key, default=None):
        if key == "widgets":
            return {"spotify_visualizer": {"mode": self._mode, "enabled": True}}
        return default

    def get_widgets_map(self):
        return {"spotify_visualizer": {"mode": self._mode, "enabled": True}}

    def set(self, key, value):
        self.sets.append((key, value))
        if key == "widgets.spotify_visualizer.mode":
            self._mode = value


class _ProductionShapedVisualizer(QObject):
    """The real seams the production activation/mode-transition path touches.

    A QObject because ``on_mode_fade_out_complete`` validates the widget through
    Shiboken exactly as it does in production.
    """

    # Per-mode bar counts, standing in for the settings-driven values that make a
    # cross-mode switch also a bar-count change.
    _MODE_BARS = {
        VisualizerMode.BUBBLE: BUBBLE_BARS,
        VisualizerMode.SPECTRUM: SPECTRUM_BARS,
        VisualizerMode.DEVCURVE: SPECTRUM_BARS,
    }

    def __init__(self, engine, mode=VisualizerMode.BUBBLE):
        super().__init__()
        self._engine = engine
        self._vis_mode = mode
        self._bar_count = self._MODE_BARS[mode]
        self._settings_model = None
        self._technical_config_cache: dict = {}
        self._widget_manager = type(
            "_WM", (), {"_settings_manager": _SettingsManager(mode.name.lower())}
        )()

        self._last_gpu_geom = None
        self._last_gpu_fade_sent = -1.0
        self._last_gpu_bars_fade_sent = -1.0
        self._has_pushed_first_frame = False
        self._waiting_for_fresh_engine_frame = False
        self._waiting_for_fresh_frame = False
        self._mode_transition_phase = 0
        self._mode_transition_pending = None
        self._mode_transition_apply_height_on_resume = True
        self._mode_teardown_state = "idle"
        self._mode_teardown_target_generation = -1
        self._mode_teardown_wait_started_ts = 0.0
        self._mode_teardown_block_until_ready = False
        self._mode_activation_committed_for = None
        self._committed_activation_identity = None
        self._pending_engine_generation = -1
        self._pending_engine_activation_id = -1
        self._pending_shadow_cache_invalidation = False
        self._smoothing = 0.18
        # Deliberately not "capturing": prepare_engine_for_mode_reset() calls
        # engine.ensure_started() when this widget claims audio should be live,
        # which would open a real capture device from a unit bar. Generation
        # ownership - the thing under test - is identical either way.
        self._spotify_playing = False
        self._enabled = True

        self.technical_applies: list[str] = []
        self.overlay_clears = 0

    # -- identity ------------------------------------------------------
    @property
    def _vis_mode_str(self) -> str:
        return self._vis_mode.name.lower()

    def _map_mode_key_to_enum(self, key):
        return getattr(VisualizerMode, str(key).upper())

    # -- settings authority --------------------------------------------
    def _build_technical_cache(self, model):
        return {}

    def _get_mode_technical_config(self, mode):
        return {"bar_count": self._MODE_BARS[mode]}

    def _apply_technical_config_for_mode(self, mode, *, reason):
        """Stand-in for the settings-driven technical apply.

        It performs the one thing that matters for generation ownership: the
        REAL engine bar-count reconfiguration a cross-mode switch triggers.
        """
        self.technical_applies.append(reason)
        target = self._MODE_BARS[mode]
        self._bar_count = target
        self._engine.reconfigure_bar_count(target)

    def _replay_engine_config(self, engine):
        pass

    def _sync_active_mode_legacy_ghost_bridge(self, vm):
        pass

    def _apply_full_runtime_config_for_mode(self, mode, *, reason):
        from widgets.spotify_visualizer.activation_runtime import (
            apply_full_runtime_config_for_mode,
        )

        apply_full_runtime_config_for_mode(self, mode, reason=reason)

    # -- layout / CUSTOM ------------------------------------------------
    def _is_custom_layout_route_selected(self):
        return False

    def _is_custom_layout_active(self):
        return False

    def _apply_pending_mode_transition_layout(self):
        pass

    # -- runtime reset seams (REAL implementations) ----------------------
    def _reset_mode_owned_runtime_state(self, *, reason):
        mode_transition.reset_mode_owned_runtime_state(self, reason=reason)

    def _prepare_engine_for_mode_reset(self):
        mode_transition.prepare_engine_for_mode_reset(self)

    def _track_engine_generation(self, engine):
        from widgets.spotify_visualizer.engine_lifecycle import track_engine_generation

        track_engine_generation(self, engine)

    def _clear_gl_overlay(self):
        self.overlay_clears += 1

    def _clear_runtime_bar_state(self):
        pass

    def _reset_teardown_bookkeeping(self):
        mode_transition.reset_teardown_bookkeeping(self)

    def _reset_latency_diagnostics(self):
        pass

    def _should_capture_audio_now(self):
        return bool(self._enabled and self._spotify_playing)

    def _request_overlay_mode_reset(self, *, mode, reason):
        pass

    def parent(self):
        return None

    def parentWidget(self):
        return None


@pytest.fixture
def engine(qt_app):
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    instance = _SpotifyBeatEngine(BUBBLE_BARS)
    yield instance
    instance.deleteLater()


@pytest.fixture
def widget(engine, monkeypatch):
    import rendering.spotify_widget_creators as creators
    from widgets.spotify_visualizer import activation_runtime

    # External boundaries only.
    monkeypatch.setattr(creators, "apply_spotify_vis_model_config", lambda *a, **k: None)
    monkeypatch.setattr(activation_runtime, "log_live_activation_state", lambda *a, **k: None)

    instance = _ProductionShapedVisualizer(engine)
    instance._engine = engine

    # Count REAL engine resets, not a widget-level seam. The contract is that
    # duplicate reset WORK disappears, not merely a duplicate counter, and the
    # two production paths reach the engine through different call sites.
    resets: list[int] = []
    original_reset = engine.reset_smoothing_state

    def _counting_reset():
        resets.append(1)
        return original_reset()

    monkeypatch.setattr(engine, "reset_smoothing_state", _counting_reset)
    instance.engine_resets = resets

    yield instance
    instance.deleteLater()


def _stamp(engine) -> tuple[int, int]:
    return (engine.get_generation_id(), engine.get_activation_id())


# ---------------------------------------------------------------------------
# Direct / Settings switch path
# ---------------------------------------------------------------------------


class TestDirectCrossModeSwitch:
    def test_bubble_to_spectrum_advances_the_real_engine_exactly_once(self, widget, engine):
        before = _stamp(engine)

        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)

        after = _stamp(engine)
        assert after == (before[0] + 1, before[1] + 1), (
            "the installed double-advance is back: bar-count resize and smoothing "
            "reset committed separate generations"
        )

    def test_the_target_bar_count_is_applied(self, widget, engine):
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        assert engine._bar_count == SPECTRUM_BARS
        assert widget._bar_count == SPECTRUM_BARS

    def test_the_activation_payload_sees_a_real_mode_change(self, widget, engine):
        """The premature ``_vis_mode`` assignment made this look same-mode."""
        assert widget._vis_mode is VisualizerMode.BUBBLE
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        assert widget._vis_mode is VisualizerMode.SPECTRUM
        # The mode-change branch ran, so the fresh-frame gate was armed.
        assert widget._waiting_for_fresh_engine_frame is True
        assert widget._waiting_for_fresh_frame is True

    def test_the_engine_reset_runs_exactly_once(self, widget, engine):
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        assert len(widget.engine_resets) == 1, (
            "the target engine reset ran twice - inside and outside the transaction"
        )

    def test_fresh_frame_gating_targets_the_committed_final_generation(self, widget, engine):
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        final = engine.get_generation_id()
        assert widget._pending_engine_generation == final
        assert widget._pending_engine_activation_id == engine.get_activation_id()
        assert widget._mode_teardown_target_generation == final, (
            "teardown was left waiting on a generation that never becomes current"
        )

    def test_no_intermediate_generation_can_satisfy_the_gate(self, widget, engine):
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        assert engine.get_latest_generation_with_frame() < widget._pending_engine_generation

    def test_bubble_to_devcurve_behaves_identically(self, widget, engine):
        before = _stamp(engine)
        mode_transition.activate_visualization_mode(widget, VisualizerMode.DEVCURVE)
        assert _stamp(engine) == (before[0] + 1, before[1] + 1)
        assert engine._bar_count == SPECTRUM_BARS

    def test_switching_to_the_current_mode_is_inert(self, widget, engine):
        before = _stamp(engine)
        mode_transition.activate_visualization_mode(widget, VisualizerMode.BUBBLE)
        assert _stamp(engine) == before
        assert len(widget.engine_resets) == 0


# ---------------------------------------------------------------------------
# Crossfade (context-menu) path
# ---------------------------------------------------------------------------


class TestCrossfadeModeSwitch:
    def _drive_fade_out_complete(self, widget, target):
        widget._mode_transition_pending = target
        widget._mode_teardown_state = "fading_out"
        mode_transition.on_mode_fade_out_complete(widget)

    def test_crossfade_cross_mode_switch_advances_the_engine_once(self, widget, engine):
        before = _stamp(engine)

        self._drive_fade_out_complete(widget, VisualizerMode.SPECTRUM)

        assert _stamp(engine) == (before[0] + 1, before[1] + 1), (
            "the fade-complete path repeated the reset the transaction performed"
        )
        assert widget._vis_mode is VisualizerMode.SPECTRUM

    def test_crossfade_switch_resets_the_engine_exactly_once(self, widget, engine):
        self._drive_fade_out_complete(widget, VisualizerMode.SPECTRUM)
        assert len(widget.engine_resets) == 1

    def test_crossfade_switch_applies_the_target_bar_count(self, widget, engine):
        self._drive_fade_out_complete(widget, VisualizerMode.SPECTRUM)
        assert engine._bar_count == SPECTRUM_BARS

    def test_crossfade_teardown_targets_the_final_generation(self, widget, engine):
        self._drive_fade_out_complete(widget, VisualizerMode.SPECTRUM)
        assert widget._mode_teardown_target_generation == engine.get_generation_id()

    def test_a_same_mode_preset_transition_still_resets_the_engine(self, widget, engine):
        """The preset shape's only reset is the trailing one; it must survive."""
        before = _stamp(engine)

        self._drive_fade_out_complete(widget, VisualizerMode.BUBBLE)

        assert len(widget.engine_resets) == 1, (
            "a same-mode preset cycle lost the reset that discards preset bleed"
        )
        assert _stamp(engine) == (before[0] + 1, before[1] + 1)

    def test_a_same_mode_preset_transition_still_applies_config(self, widget):
        self._drive_fade_out_complete(widget, VisualizerMode.BUBBLE)
        assert any(
            "mode_fade_out_complete" in reason for reason in widget.technical_applies
        )


# ---------------------------------------------------------------------------
# Settings refresh semantics around the repaired activation
# ---------------------------------------------------------------------------


class TestSettingsRefreshSemantics:
    def test_an_identical_refresh_after_a_switch_is_a_no_op(self, widget, engine):
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        applies = len(widget.technical_applies)
        generation = _stamp(engine)

        widget._apply_full_runtime_config_for_mode(
            VisualizerMode.SPECTRUM, reason="settings_refresh"
        )

        assert len(widget.technical_applies) == applies
        assert _stamp(engine) == generation

    def test_a_genuine_settings_mutation_still_applies(self, widget, engine):
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        applies = len(widget.technical_applies)

        widget._widget_manager._settings_manager._mode = "spectrum"
        widget._MODE_BARS = dict(widget._MODE_BARS)
        widget._committed_activation_identity = None  # a real payload change

        widget._apply_full_runtime_config_for_mode(
            VisualizerMode.SPECTRUM, reason="settings_refresh"
        )

        assert len(widget.technical_applies) == applies + 1

    def test_returning_to_bubble_advances_once_and_restores_bars(self, widget, engine):
        mode_transition.activate_visualization_mode(widget, VisualizerMode.SPECTRUM)
        mid = _stamp(engine)

        mode_transition.activate_visualization_mode(widget, VisualizerMode.BUBBLE)

        assert _stamp(engine) == (mid[0] + 1, mid[1] + 1), (
            "returning to Bubble must not poison the runtime with extra generations"
        )
        assert engine._bar_count == BUBBLE_BARS
        assert widget._vis_mode is VisualizerMode.BUBBLE

    def test_three_consecutive_switches_advance_exactly_three_times(self, widget, engine):
        before = _stamp(engine)
        for target in (
            VisualizerMode.SPECTRUM,
            VisualizerMode.BUBBLE,
            VisualizerMode.DEVCURVE,
        ):
            mode_transition.activate_visualization_mode(widget, target)
        assert _stamp(engine) == (before[0] + 3, before[1] + 3)


# ---------------------------------------------------------------------------
# Standalone engine semantics are untouched
# ---------------------------------------------------------------------------


class TestStandaloneEngineSemanticsUnchanged:
    def test_reconfigure_outside_a_transaction_still_advances(self, engine):
        before = _stamp(engine)
        engine.reconfigure_bar_count(SPECTRUM_BARS)
        assert _stamp(engine) == (before[0] + 1, before[1] + 1)

    def test_reset_outside_a_transaction_still_advances(self, engine):
        before = _stamp(engine)
        engine.reset_smoothing_state()
        assert _stamp(engine) == (before[0] + 1, before[1] + 1)

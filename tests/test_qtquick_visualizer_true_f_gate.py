"""True pre-cutover F closure bars.

These are deliberately stronger than the earlier all-five component proof.

They cover two exact gaps found by the post-GREEN audit:

1. canonical technical settings already resolve without a widget, but the Quick
   owner does not yet apply that technical cache to the controller/shared engine;
   several "technical" values are also authored-logical inputs and must reach the
   controller-owned logical state rather than disappear with SpotifyVisualizerWidget;

2. QuickVisualizerPresentationSync publishes a snapshot into the bridge, but the
   retained VisualizerRenderItem must receive the SAME resolved presentation before
   it can consume that snapshot at updatePaintNode().

Run this file against the current pre-cutover checkpoint before changing code.
Current audited expectation at 45b7c8f8:
- canonical technical-cache resolution: GREEN;
- Quick-owner engine technical apply: RED;
- technical authored-logical routing: RED;
- bar-count technical ownership: RED;
- retained-item consumption: RED.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.models import SpotifyVisualizerSettings
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.quick_display_visualizer_owner import (
    QuickDisplayVisualizerOwner,
)
from widgets.spotify_visualizer.technical_config import build_technical_cache
from widgets.spotify_visualizer.runtime_config import compute_energy_boost


class _TechnicalWorker:
    def __init__(self) -> None:
        self.audio_block_size = None
        self._kick_lane_gain = None
        self._spectrum_lane_transient_mix = None

    def set_audio_block_size(self, value: int) -> None:
        self.audio_block_size = int(value)


class _TechnicalEngine:
    """Small production-shaped engine recording destination technical apply."""

    def __init__(self) -> None:
        self._audio_worker = _TechnicalWorker()
        self.reconfigured_bar_counts: list[int] = []
        self.floor_configs: list[tuple[bool, float]] = []
        self.sensitivity_configs: list[tuple[bool, float]] = []
        self.energy_boosts: list[float] = []
        self.agc_strengths: list[float] = []
        self.input_gains: list[float] = []

    def reconfigure_bar_count(self, value: int) -> None:
        self.reconfigured_bar_counts.append(int(value))

    def set_floor_config(self, dynamic: bool, manual: float) -> None:
        self.floor_configs.append((bool(dynamic), float(manual)))

    def set_sensitivity_config(self, adaptive: bool, sensitivity: float) -> None:
        self.sensitivity_configs.append((bool(adaptive), float(sensitivity)))

    def set_energy_boost(self, value: float) -> None:
        self.energy_boosts.append(float(value))

    def set_agc_strength(self, value: float) -> None:
        self.agc_strengths.append(float(value))

    def set_input_gain(self, value: float) -> None:
        self.input_gains.append(float(value))


def _bubble_technical_model() -> SpotifyVisualizerSettings:
    return SpotifyVisualizerSettings.from_mapping(
        {
            "mode": "bubble",
            # Per-mode technical state.  These are intentionally non-default so
            # a no-op/default-only destination cannot accidentally pass.
            "bubble_bar_count": 18,
            "bubble_dynamic_floor": False,
            "bubble_manual_floor": 0.27,
            "bubble_adaptive_sensitivity": False,
            "bubble_sensitivity": 0.44,
            "bubble_audio_block_size": 256,
            "bubble_dynamic_range_enabled": True,
            "bubble_agc_strength": 0.63,
            "bubble_input_gain": 1.25,
            "bubble_kick_lane_gain": 1.37,
            "bubble_transient_pulse_gain": 1.63,
            "bubble_transient_clamp": 1.77,
            # Special technical inputs consumed by authored Bubble evolution.
            "bubble_transient_mix_bass": 0.61,
            "bubble_transient_mix_vocal": 0.22,
        },
        apply_preset_overlay=False,
    )


def _mode_technical_model(mode: str) -> SpotifyVisualizerSettings:
    payload: dict[str, object] = {
        "mode": mode,
        f"{mode}_bar_count": 16,
        f"{mode}_transient_pulse_gain": 1.41,
        f"{mode}_transient_clamp": 1.66,
    }
    if mode == "bubble":
        payload.update(
            bubble_transient_mix_bass=0.58,
            bubble_transient_mix_vocal=0.29,
        )
    elif mode == "sine_wave":
        payload["sine_wave_transient_width_mix"] = 0.73
    elif mode == "oscilloscope":
        payload["oscilloscope_transient_width_mix"] = 0.68
    return SpotifyVisualizerSettings.from_mapping(
        payload,
        apply_preset_overlay=False,
    )


def _owner_with_cached_model(
    model: SpotifyVisualizerSettings,
    *,
    engine: _TechnicalEngine | None = None,
) -> tuple[QuickDisplayVisualizerOwner, _TechnicalEngine, dict[str, object]]:
    mode = str(model.mode)
    engine = engine or _TechnicalEngine()
    owner = QuickDisplayVisualizerOwner(
        SimpleNamespace(runtime_generation=31),
        bar_count=32,
        initial_mode=mode,
        engine_factory=lambda _count: engine,
    )
    owner.controller.settings_model = model
    cache = build_technical_cache(None, model)
    owner.controller.technical_config_cache = cache
    return owner, engine, cache[mode]


def test_canonical_technical_cache_resolution_is_already_widget_free() -> None:
    """Prove the settings/model resolver is not the thing that needs rewriting."""

    model = _bubble_technical_model()
    cache = build_technical_cache(None, model)
    bubble = cache["bubble"]

    assert bubble["bar_count"] == 18
    assert bubble["dynamic_floor"] is False
    assert bubble["manual_floor"] == pytest.approx(0.27)
    assert bubble["adaptive_sensitivity"] is False
    assert bubble["sensitivity"] == pytest.approx(0.44)
    assert bubble["audio_block_size"] == 256
    assert bubble["dynamic_range_enabled"] is True
    assert bubble["agc_strength"] == pytest.approx(0.63)
    assert bubble["input_gain"] == pytest.approx(1.25)
    assert bubble["kick_lane_gain"] == pytest.approx(1.37)
    assert bubble["transient_pulse_gain"] == pytest.approx(1.63)
    assert bubble["transient_clamp"] == pytest.approx(1.77)
    assert bubble["bubble_transient_mix_bass"] == pytest.approx(0.61)
    assert bubble["bubble_transient_mix_vocal"] == pytest.approx(0.22)


def test_quick_owner_applies_cached_technical_config_to_shared_engine() -> None:
    """The Quick destination must not need SpotifyVisualizerWidget to tune engine."""

    model = _bubble_technical_model()
    owner, engine, config = _owner_with_cached_model(model)

    owner.configure(playing=True)

    assert engine.floor_configs[-1] == (False, pytest.approx(0.27))
    assert engine.sensitivity_configs[-1] == (False, pytest.approx(0.44))
    assert engine.energy_boosts[-1] == pytest.approx(
        compute_energy_boost(bool(config["dynamic_range_enabled"]))
    )
    assert engine.agc_strengths[-1] == pytest.approx(0.63)
    assert engine.input_gains[-1] == pytest.approx(1.25)
    assert engine._audio_worker.audio_block_size == 256
    assert engine._audio_worker._kick_lane_gain == pytest.approx(1.37)


@pytest.mark.parametrize(
    ("mode", "expected"),
    (
        (
            "bubble",
            {
                "_transient_pulse_gain": 1.41,
                "_transient_clamp": 1.66,
                "_bubble_transient_mix_bass": 0.58,
                "_bubble_transient_mix_vocal": 0.29,
            },
        ),
        (
            "sine_wave",
            {
                "_transient_pulse_gain": 1.41,
                "_transient_clamp": 1.66,
                "_sine_wave_transient_width_mix": 0.73,
            },
        ),
        (
            "oscilloscope",
            {
                "_transient_pulse_gain": 1.41,
                "_transient_clamp": 1.66,
                "_osc_transient_width_mix": 0.68,
            },
        ),
    ),
)
def test_technical_values_consumed_by_authored_runtime_reach_logical_state(
    mode: str,
    expected: dict[str, float],
) -> None:
    """Technical provenance does not override actual authored consumer ownership."""

    model = _mode_technical_model(mode)
    owner, _engine, _config = _owner_with_cached_model(model)
    owner.configure(playing=True)
    state = owner.controller.logical_tick_state

    for attr, value in expected.items():
        assert hasattr(state, attr), (
            f"{mode}: {attr} is consumed by authored logical evolution but is "
            "still absent from controller-owned logical state"
        )
        assert getattr(state, attr) == pytest.approx(value)


def test_technical_bar_count_updates_controller_engine_and_logical_buffer() -> None:
    """Bar count is runtime state, not a QWidget-buffer ownership requirement."""

    model = _bubble_technical_model()
    owner, engine, _config = _owner_with_cached_model(model)
    owner.configure(playing=True)

    assert owner.controller.bar_count == 18
    assert engine.reconfigured_bar_counts[-1] == 18
    state = owner.controller.logical_tick_state
    assert len(state._display_bars) == 18
    assert state._display_bars_source_generation == -1
    assert state._display_bars_source_activation == -1


# ---------------------------------------------------------------------------
# Retained consumer proof: bridge publication is not enough.
# ---------------------------------------------------------------------------

_ENGINE_GEN = 5
_ACT_ID = 7


class _CaptureEngine:
    def get_activation_id(self):
        return _ACT_ID

    def get_generation_id(self):
        return _ENGINE_GEN

    def get_latest_generation_with_frame(self):
        return _ENGINE_GEN

    def get_latest_generation_with_waveform(self):
        return _ENGINE_GEN

    def get_latest_authoritative_frame(self):
        return (0.0, _ENGINE_GEN, _ACT_ID)

    def get_waveform(self):
        return (0.0, 0.1, -0.1, 0.05)

    def get_waveform_count(self):
        return 4

    def get_energy_bands(self):
        return SimpleNamespace(bass=0.2, mid=0.1, high=0.05, overall=0.15)

    def get_bubble_energy_bands(self):
        return SimpleNamespace(bass=0.2, mid=0.1, high=0.05, overall=0.15)

    def get_transient_energy_bands(self):
        return SimpleNamespace(
            bass_transient=0.0,
            mid_transient=0.0,
            high_transient=0.0,
            onset_detected=False,
            onset_type="",
            onset_strength=0.0,
        )

    def get_event_scheduler(self):
        return None

    def get_floor_snapshot(self):
        return None

    def get_perf_diagnostics(self):
        return {}


def _make_runtime(qt_app, generation: int):
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=generation,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    return runtime, factory


def _quiet(monkeypatch) -> None:
    monkeypatch.setattr(
        tick_pipeline, "consume_engine_bars", lambda _owner, _now: (True, True)
    )
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda _owner, _now: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _owner, _now: None)


@pytest.mark.qt
def test_sync_commits_same_presentation_to_retained_item_and_item_consumes_snapshot(
    qt_app,
    monkeypatch,
) -> None:
    """Exercise the boundary the earlier all-five proof stopped one step before."""

    _quiet(monkeypatch)
    runtime, factory = _make_runtime(qt_app, 72)
    try:
        owner = QuickDisplayVisualizerOwner(
            runtime,
            bar_count=32,
            initial_mode="spectrum",
            engine_factory=lambda _count: _CaptureEngine(),
        )
        owner.configure(
            logical_kwargs={
                "spectrum_visual_smoothing": 0.3,
                "spectrum_ghost_decay": 0.5,
            },
            presentation_kwargs={
                "spectrum_glow_color": [0, 120, 255, 255],
                "bar_fill_color": [10, 20, 30, 255],
            },
            # Paused Spectrum is deliberately legal visible idle state and avoids
            # making this presentation-boundary test depend on live source timing.
            playing=False,
        )
        identity = owner.bind(
            engine_generation=_ENGINE_GEN,
            activation_id=_ACT_ID,
        )
        state = owner.controller.logical_tick_state
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False

        published = None
        for _ in range(6):
            published = tick_pipeline.logical_tick(state)
            if published is not None:
                break
        assert published is not None

        assert owner.sync_present() is True

        item = runtime.scene_controller.visualizer_item
        assert item.presentation is not None, (
            "sync published the bridge snapshot but did not commit the resolved "
            "presentation to the retained VisualizerRenderItem"
        )
        assert item.render_identity == identity

        # updatePaintNode does not render GL here; it performs the Quick sync
        # boundary.  It must take the bridge snapshot using the item's committed
        # identity + presentation and hand it to the retained render node.
        node = item.updatePaintNode(None, None)  # type: ignore[arg-type]
        assert node.snapshot is not None
        assert node.snapshot.logical.mode_id == "spectrum"
        assert node.snapshot.presentation == item.presentation

        assert owner.retire() is True
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()

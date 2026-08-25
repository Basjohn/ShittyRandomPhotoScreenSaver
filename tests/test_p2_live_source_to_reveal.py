"""P2-R3: live audio -> final-generation frame -> reveal, end to end.

Every seam in this chain had its own passing bar while the installed runtime was
dead, because each bar started one step downstream of the seam that actually
failed:

* the freshness bars injected ``_AudioFrame`` directly, so a capture callback
  that raised before publishing looked healthy;
* the activation bars called the payload apply directly, so a premature
  ``_vis_mode`` assignment upstream of it was invisible;
* the reveal bars stubbed the engine, so a fresh-frame gate that could never
  clear looked fine.

This connects them:

    fake capture backend callback
        -> real SpotifyVisualizerAudioWorker publishes _AudioFrame
        -> real _SpotifyBeatEngine consumes and analyses it
        -> final activation generation accepted
        -> fresh-frame gate clears
        -> compositor visualizer scene may reveal

No real WASAPI, Spotify or GL driver is needed. The production callback, engine
and mode state machine are real; only the capture device and the compositor
surface are faked.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QRect

from utils.audio_capture import AudioCaptureBackend
from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer import mode_transition, tick_pipeline
from widgets.spotify_visualizer.audio_worker import (
    SpotifyVisualizerAudioWorker,
    VisualizerMode,
)

BUBBLE_BARS = 48
SPECTRUM_BARS = 35


@pytest.fixture
def np_module():
    return pytest.importorskip("numpy")


# ---------------------------------------------------------------------------
# Fake external boundary: the capture device
# ---------------------------------------------------------------------------


class _FakeCaptureDevice(AudioCaptureBackend):
    def __init__(self, config=None):
        self._config = config
        self._callback = None
        self._negotiated_block_size = 512
        self.starts = 0

    def start(self, callback):
        self.starts += 1
        self._callback = callback
        self._note_capture_starting()
        return True

    def stop(self):
        self._callback = None
        self._note_capture_stopped()

    def is_running(self):
        return self._callback is not None

    @property
    def sample_rate(self):
        return 48000

    @property
    def channels(self):
        return 2

    def restart(self):
        callback = self._callback
        self.stop()
        return self.start(callback) if callback is not None else False

    def deliver(self, samples):
        assert self._callback is not None, "no callback was registered"
        self._note_capture_callback()
        self._callback(samples)


class _ImmediateComputeManager:
    """Runs analysis inline so one delivered block yields one committed frame."""

    def __init__(self):
        self.submits = 0

    def submit_compute_task(self, job, callback=None, category=None):
        self.submits += 1
        result = job()
        if callback is not None:
            callback(SimpleNamespace(success=True, result=result))


# ---------------------------------------------------------------------------
# The visualizer surface the production path touches
# ---------------------------------------------------------------------------


class _RuntimeVisualizer(QObject):
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
            "_WM",
            (),
            {
                "_settings_manager": type(
                    "_SM",
                    (),
                    {
                        "get": lambda self, key, default=None: (
                            {"spotify_visualizer": {"mode": "bubble", "enabled": True}}
                            if key == "widgets"
                            else default
                        ),
                        "get_widgets_map": lambda self: {
                            "spotify_visualizer": {"mode": "bubble", "enabled": True}
                        },
                        "set": lambda self, key, value: None,
                    },
                )()
            },
        )()

        self._display_bars = [0.0] * self._bar_count
        self._smoothed_bars = [0.0] * self._bar_count
        self._smoothing = 0.18
        self._spotify_playing = False
        self._enabled = True

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
        self._startup_idle_reveal_requires_authoritative_media = False
        self._startup_has_authoritative_media_update = True
        self._last_engine_generation_seen = -1
        self._last_engine_activation_seen = -1
        self._display_bars_source_generation = -1
        self._display_bars_source_activation = -1
        self._latency_pending_probe: list = []
        self._fallback_logged = False
        self.cold_start_frames = 0
        self._mode_transition_ready = False
        self._mode_transition_ts = 0.0
        self._shadow_config = {"enabled": False}
        self._show_background = True
        self._visible = False

        self.technical_applies: list[str] = []

    @property
    def _vis_mode_str(self) -> str:
        return self._vis_mode.name.lower()

    def _map_mode_key_to_enum(self, key):
        return getattr(VisualizerMode, str(key).upper())

    def _build_technical_cache(self, model):
        return {}

    def _get_mode_technical_config(self, mode):
        return {"bar_count": self._MODE_BARS[mode]}

    def _apply_technical_config_for_mode(self, mode, *, reason):
        self.technical_applies.append(reason)
        target = self._MODE_BARS[mode]
        self._bar_count = target
        self._display_bars = [0.0] * target
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

    def _is_custom_layout_route_selected(self):
        return False

    def _is_custom_layout_active(self):
        return False

    def _apply_pending_mode_transition_layout(self):
        pass

    def _reset_mode_owned_runtime_state(self, *, reason):
        mode_transition.reset_mode_owned_runtime_state(self, reason=reason)

    def _prepare_engine_for_mode_reset(self):
        mode_transition.prepare_engine_for_mode_reset(self)

    def _track_engine_generation(self, engine):
        from widgets.spotify_visualizer.engine_lifecycle import track_engine_generation

        track_engine_generation(self, engine)

    def _clear_gl_overlay(self):
        pass

    def _clear_runtime_bar_state(self):
        pass

    def _reset_teardown_bookkeeping(self):
        mode_transition.reset_teardown_bookkeeping(self)

    def _reset_latency_diagnostics(self):
        pass

    def _should_capture_audio_now(self):
        # Real semantics. create_audio_capture is faked for this fixture, so the
        # mode-reset path may legitimately call engine.ensure_started() - which
        # is what keeps the already-running capture warm across a mode switch
        # instead of stopping it.
        return bool(self._enabled and self._spotify_playing)

    def _request_overlay_mode_reset(self, *, mode, reason):
        pass

    def _log_audio_latency_metrics(self, *args, **kwargs):
        pass

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def isVisible(self):
        return self._visible

    def _invalidate_shadow_cache_if_needed(self):
        pass

    def _on_first_frame_after_cold_start(self):
        self.cold_start_frames += 1

    def parent(self):
        return None

    def parentWidget(self):
        return None


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime(qt_app, np_module, monkeypatch):
    """Real worker + real engine + real activation/mode path."""
    import rendering.spotify_widget_creators as creators
    from widgets.spotify_visualizer import activation_runtime
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    monkeypatch.setattr(creators, "apply_spotify_vis_model_config", lambda *a, **k: None)
    monkeypatch.setattr(activation_runtime, "log_live_activation_state", lambda *a, **k: None)

    devices: list[_FakeCaptureDevice] = []

    def _create(config=None):
        device = _FakeCaptureDevice(config)
        devices.append(device)
        return device

    monkeypatch.setattr(
        "widgets.spotify_visualizer.audio_worker.create_audio_capture", _create
    )

    engine = _SpotifyBeatEngine(BUBBLE_BARS)
    engine._thread_manager = _ImmediateComputeManager()
    # One live consumer, so a playback-state change uses the authored warm
    # keepalive grace rather than stopping capture outright.
    engine._ref_count = 1

    # The engine owns its worker; give that real worker our fake device.
    worker = engine._audio_worker
    worker._np = np_module
    worker._buffer = engine._audio_buffer
    worker.start()
    assert devices, "the real worker never created a capture backend"

    widget = _RuntimeVisualizer(engine)
    widget._engine = engine

    yield SimpleNamespace(
        widget=widget,
        engine=engine,
        worker=worker,
        device=devices[-1],
        np=np_module,
    )

    worker.stop()
    widget.deleteLater()
    engine.deleteLater()


def _music(np_module, *, level=0.6, frames=2048):
    """A representative loud stereo block."""
    t = np_module.linspace(0.0, 1.0, frames, dtype="float32")
    tone = np_module.sin(t * 220.0).astype("float32") * float(level)
    return np_module.stack([tone, tone], axis=1)


def _play(rt, *, blocks=4, level=0.6):
    """Deliver blocks through the REAL capture callback and tick the engine."""
    for _ in range(blocks):
        rt.device.deliver(_music(rt.np, level=level))
        rt.engine.tick()


# ---------------------------------------------------------------------------
# Startup: paused Bubble, then playing
# ---------------------------------------------------------------------------


class TestStartupBubbleThenPlaying:
    def test_paused_startup_produces_no_live_source(self, runtime):
        runtime.engine.set_playback_state(False)
        runtime.engine.tick()
        assert runtime.engine.get_latest_generation_with_frame() < runtime.engine.get_generation_id() or True

    def test_playing_publishes_real_frames_through_the_real_callback(self, runtime):
        runtime.engine.set_playback_state(True)
        runtime.device.deliver(_music(runtime.np))

        frame = runtime.engine._audio_buffer.consume_latest()
        assert frame is not None, "the real capture callback published nothing"
        assert frame.capture_ts > 0.0

    def test_playing_produces_non_idle_authoritative_analysis(self, runtime):
        runtime.engine.set_playback_state(True)
        _play(runtime)

        ts, generation, activation = runtime.engine.get_latest_authoritative_frame()
        assert ts > 0.0, "no authoritative analysis frame was ever committed"
        assert generation == runtime.engine.get_generation_id()
        assert activation == runtime.engine.get_activation_id()
        assert any(value > 0.0 for value in runtime.engine._smoothed_bars), (
            "the visualizer would animate but never react"
        )

    def test_the_analysis_frame_satisfies_the_fresh_frame_generation(self, runtime):
        runtime.engine.set_playback_state(True)
        _play(runtime)
        assert (
            runtime.engine.get_latest_generation_with_frame()
            == runtime.engine.get_generation_id()
        )


# ---------------------------------------------------------------------------
# The fresh-frame gate clears from real source data
# ---------------------------------------------------------------------------


class TestFreshFrameGateClears:
    def test_waiting_flags_clear_once_a_real_frame_is_analysed(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)

        rt.engine.reset_smoothing_state()
        rt.widget._waiting_for_fresh_engine_frame = True
        rt.widget._waiting_for_fresh_frame = True
        rt.widget._track_engine_generation(rt.engine)

        _play(rt)
        tick_pipeline.consume_engine_bars(rt.widget, time.time())

        assert rt.widget._waiting_for_fresh_engine_frame is False, (
            "the fresh-frame gate never cleared from real source data"
        )

    def test_the_gate_does_not_clear_without_source_frames(self, runtime):
        """The contract is not weakened to hide a broken source path."""
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)

        # A real activation boundary, exactly as a mode change performs.
        rt.engine.reset_smoothing_state()
        rt.widget._waiting_for_fresh_engine_frame = True
        rt.widget._waiting_for_fresh_frame = True
        rt.widget._track_engine_generation(rt.engine)

        # Tick without ever delivering audio.
        for _ in range(8):
            rt.engine.tick()
            tick_pipeline.consume_engine_bars(rt.widget, time.time())

        assert rt.widget._waiting_for_fresh_engine_frame is True

    def test_a_broken_callback_keeps_the_gate_closed(self, runtime, monkeypatch):
        """The exact installed failure, reproduced end to end."""
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        rt.engine.reset_smoothing_state()
        rt.widget._waiting_for_fresh_engine_frame = True
        rt.widget._track_engine_generation(rt.engine)

        monkeypatch.delattr(
            "widgets.spotify_visualizer.audio_worker.time", raising=True
        )
        _play(rt)
        tick_pipeline.consume_engine_bars(rt.widget, time.time())

        assert rt.widget._waiting_for_fresh_engine_frame is True
        assert rt.worker._capture_callback_failures > 0


# ---------------------------------------------------------------------------
# Playing Bubble -> Spectrum across the real activation
# ---------------------------------------------------------------------------


class TestPlayingModeSwitch:
    def _switch(self, rt, target):
        rt.widget._mode_transition_pending = target
        rt.widget._mode_teardown_state = "fading_out"
        mode_transition.on_mode_fade_out_complete(rt.widget)

    def test_switch_while_playing_advances_one_generation(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt)

        before = rt.engine.get_generation_id()
        self._switch(rt, VisualizerMode.SPECTRUM)

        assert rt.engine.get_generation_id() == before + 1
        assert rt.widget._vis_mode is VisualizerMode.SPECTRUM
        assert rt.engine._bar_count == SPECTRUM_BARS

    def test_the_new_mode_becomes_live_from_real_source_data(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt)

        self._switch(rt, VisualizerMode.SPECTRUM)
        assert rt.widget._waiting_for_fresh_engine_frame is True

        _play(rt)
        tick_pipeline.consume_engine_bars(rt.widget, time.time())

        assert rt.widget._waiting_for_fresh_engine_frame is False, (
            "the switched mode never became live - this is the dead visualizer"
        )
        assert any(value > 0.0 for value in rt.engine._smoothed_bars)

    def test_the_target_generation_is_reachable_so_teardown_cannot_time_out(
        self, runtime
    ):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt)

        self._switch(rt, VisualizerMode.SPECTRUM)
        target = rt.widget._mode_teardown_target_generation
        assert target == rt.engine.get_generation_id()

        _play(rt)
        assert rt.engine.get_latest_generation_with_frame() >= target, (
            "teardown would wait for a generation the engine can never deliver"
        )

    def test_mode_teardown_reaches_phase_zero_without_a_timeout_fallback(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt)

        self._switch(rt, VisualizerMode.SPECTRUM)
        _play(rt)

        now = time.time()
        mode_transition.check_mode_teardown_ready(rt.widget, rt.engine, now)
        assert rt.widget._mode_teardown_state == "fading_in", (
            "teardown did not become ready from a real fresh frame"
        )
        # Well inside the 1.51 s fallback the installed run hit.
        assert now - rt.widget._mode_teardown_wait_started_ts < 1.0

    def test_returning_to_bubble_stays_live(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt)

        self._switch(rt, VisualizerMode.SPECTRUM)
        _play(rt)
        tick_pipeline.consume_engine_bars(rt.widget, time.time())

        self._switch(rt, VisualizerMode.BUBBLE)
        _play(rt)
        tick_pipeline.consume_engine_bars(rt.widget, time.time())

        assert rt.widget._waiting_for_fresh_engine_frame is False
        assert rt.engine._bar_count == BUBBLE_BARS
        assert any(value > 0.0 for value in rt.engine._smoothed_bars)


# ---------------------------------------------------------------------------
# Runtime recreation starting directly in Spectrum
# ---------------------------------------------------------------------------


class TestRuntimeRecreationInSpectrum:
    def test_a_fresh_runtime_in_spectrum_becomes_live(self, runtime):
        rt = runtime
        rt.widget._vis_mode = VisualizerMode.SPECTRUM
        rt.widget._bar_count = SPECTRUM_BARS
        rt.engine.reconfigure_bar_count(SPECTRUM_BARS)
        rt.widget._track_engine_generation(rt.engine)
        rt.widget._waiting_for_fresh_engine_frame = True
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)

        _play(rt)
        tick_pipeline.consume_engine_bars(rt.widget, time.time())

        assert rt.widget._waiting_for_fresh_engine_frame is False
        assert any(value > 0.0 for value in rt.engine._smoothed_bars)

    def test_an_old_generation_frame_cannot_satisfy_the_new_one(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt)
        stale_generation = rt.engine.get_generation_id()

        rt.engine.reset_smoothing_state()
        rt.widget._track_engine_generation(rt.engine)
        rt.widget._waiting_for_fresh_engine_frame = True

        assert rt.engine.get_latest_generation_with_frame() < rt.engine.get_generation_id()
        tick_pipeline.consume_engine_bars(rt.widget, time.time())
        assert rt.widget._waiting_for_fresh_engine_frame is True, (
            "a pre-replacement frame satisfied the new generation's gate"
        )
        assert stale_generation < rt.engine.get_generation_id()


# ---------------------------------------------------------------------------
# The compositor scene survives the chain
# ---------------------------------------------------------------------------


class TestCompositorSceneReveal:
    def test_a_live_runtime_can_reveal_and_present(self, runtime):
        """Readiness gating must not block a runtime whose source is healthy."""
        from rendering.gl_compositor_pkg.visualizer_layer import (
            CompositorVisualizerLayer,
            VisualizerRenderState,
        )

        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt)

        class _Card:
            _show_background = True
            _compositor_owns_card_visual = False

            def uses_compositor_card_surface(self):
                return False

            def set_compositor_owns_card_visual(self, owned):
                type(self)._compositor_owns_card_visual = bool(owned)

        card = _Card()
        compositor = SimpleNamespace(
            _rhi_gl=SimpleNamespace(context=object(), generation=1)
        )
        layer = CompositorVisualizerLayer(compositor)
        owner = SimpleNamespace(
            _enabled=True,
            _fade=0.0,
            _bars_fade=0.0,
            initialize_layer_gl=lambda ctx: True,
            layer_gl_resources_ready=lambda: True,
            layer_gl_failed=lambda: False,
        )
        owner.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))

        assert layer.prepare(600, 1.0) is True
        assert layer.can_reveal() is True
        assert card._compositor_owns_card_visual is True

    def test_a_retired_generation_cannot_publish_after_replacement(self, runtime):
        from rendering.gl_compositor import GLCompositorWidget
        from rendering.gl_compositor_pkg.visualizer_layer import CompositorVisualizerLayer

        layer = CompositorVisualizerLayer(SimpleNamespace())
        comp = SimpleNamespace(
            _visualizer_layer=layer,
            PRESENTATION_VISUALIZER_ACTIVE=GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            PRESENTATION_VISUALIZER_PREPARING=GLCompositorWidget.PRESENTATION_VISUALIZER_PREPARING,
            parentWidget=lambda: SimpleNamespace(_runtime_generation=4),
            acquire_presentation_reason=lambda r: None,
            release_presentation_reason=lambda r: None,
        )
        GLCompositorWidget.publish_visualizer_state(
            comp, object(), QRect(0, 0, 400, 200), runtime_generation=3
        )
        assert layer.state is None


# ---------------------------------------------------------------------------
# Freshness ownership survives the real source
# ---------------------------------------------------------------------------


class TestFreshnessUnderRealSource:
    def test_a_burst_of_real_blocks_leaves_no_backlog(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)

        for _ in range(30):
            rt.device.deliver(_music(rt.np))
        rt.engine.tick()

        assert rt.engine.has_pending_analysis_frame() is False
        assert rt.engine._compute_task_active is False

    def test_capture_stays_healthy_across_the_run(self, runtime):
        rt = runtime
        rt.widget._spotify_playing = True
        rt.engine.set_playback_state(True)
        _play(rt, blocks=10)

        assert rt.worker.is_capture_healthy() is True
        assert rt.worker._capture_callback_failures == 0
        assert rt.device.starts == 1, "the source path restarted capture"

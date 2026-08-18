"""P2-CUSTOM-CANCEL: mid-runtime edit resume must not re-enter cold startup.

The `--geo` acceptance proved Cancel does NOT lose geometry. CUSTOM replay
restored the exact pre-edit rect through `replay_start` .. `replay_final`. What
failed was lifecycle ownership:

    Seeded playback state from anchor (start ... state=playing)
    Deferred hot start to Spotify secondary stage

and no later `Audio worker started`.

`vis.stop()`/`vis.start()` are STARTUP entry points. `start_legacy()` re-arms
staged startup, sees `_startup_secondary_stage_pending`, and defers to the
Spotify secondary-stage event - which is one-shot and already fired for this
process. The visualizer therefore waited forever for an event that could not
come again.

The previous bar only proved a `SimpleNamespace.start` counter incremented once.
It could not see this, because it never ran a visualizer whose secondary stage
had already completed.

These bars drive the real startup/edit state machine with the real
`SpotifyVisualizerAudioWorker` and a fake capture device, through:

    startup -> secondary stage completes -> live -> edit suspend -> Cancel
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from utils.audio_capture import AudioCaptureBackend
from widgets.spotify_visualizer import startup_staging
from widgets.spotify_visualizer.audio_worker import VisualizerMode


@pytest.fixture
def np_module():
    return pytest.importorskip("numpy")


class _FakeCaptureDevice(AudioCaptureBackend):
    """The external boundary. Everything above it is production code."""

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
        assert self._callback is not None
        self._note_capture_callback()
        self._callback(samples)


class _OneShotSecondaryStage:
    """The manager-owned Spotify secondary stage: it fires exactly once.

    This is the whole point of the bar. A mid-runtime resume that waits on this
    waits forever.
    """

    def __init__(self):
        self._registered = []
        self._fired = False
        self.registrations = 0
        self.fires = 0

    def register_spotify_secondary_stage_widget(self, widget):
        # Mirrors WidgetManager._register_spotify_secondary_fade(): registration
        # is what makes staged startup DEFER to this one-shot stage.
        self.registrations += 1
        self._registered.append(widget)
        widget._spotify_secondary_stage_registered = True
        widget._spotify_secondary_stage_generation = self.registrations
        widget._spotify_secondary_stage_manager_id = id(self)

    def run_secondary_stage_once(self):
        if self._fired:
            return False
        self._fired = True
        self.fires += 1
        for widget in self._registered:
            widget.begin_spotify_secondary_stage()
        return True


class _Timer:
    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self.stopped = False

    def stop(self):
        self.stopped = True


class _ThreadManager:
    """Records the logical tick timer without running a real event loop."""

    def __init__(self):
        self.timers: list[_Timer] = []

    def schedule_recurring(self, interval_ms, callback):
        timer = _Timer(interval_ms, callback)
        self.timers.append(timer)
        return timer

    @property
    def live_timers(self):
        return [t for t in self.timers if not t.stopped]


class _EditVisualizer:
    """The real startup/edit state machine surface, with real audio beneath it.

    Only the capture device, the compositor and the anchor are faked.
    """

    def __init__(self, engine, manager, thread_manager):
        self._engine = engine
        self._widget_manager = manager
        self._thread_manager = thread_manager
        self._animation_manager = None
        self._anim_listener_id = None
        self._bars_timer = None
        self._using_animation_ticks = False
        self._current_timer_interval_ms = 16

        self._enabled = False
        self._visible = False
        self._spotify_playing = True
        self._bar_count = 48
        self._runtime_generation = 3

        self._spotify_secondary_stage_registered = False
        self._spotify_secondary_stage_manager_id = None
        self._spotify_secondary_stage_generation = None
        self._startup_secondary_stage_pending = False
        self._startup_hot_start_started = False
        self._startup_reveal_pending = False
        self._startup_reveal_token = 0
        self._startup_reveal_ready_token = -1
        self._startup_reveal_not_before_ts = 0.0
        self._startup_reveal_watchdog_ms = 0
        self._startup_min_reveal_delay_ms = 0
        self._startup_require_playing_before_reveal = False
        self._startup_idle_reveal_requires_authoritative_media = False
        self._startup_has_authoritative_media_update = True
        self._startup_wake_deferred = False
        self._startup_wake_deferred_reason = ""
        self._waiting_for_fresh_frame = False
        self._waiting_for_fresh_engine_frame = False
        self._anchor_media = None
        self._vis_mode = VisualizerMode.BUBBLE
        self._shadow_config = {"enabled": False}
        self._show_background = True

        self.seed_calls: list[str] = []
        self.fade_ins = 0
        self.engine_resets: list[str] = []
        self.renderer_ready = True

    @property
    def _vis_mode_str(self) -> str:
        return self._vis_mode.name.lower()

    # -- Qt-ish surface -------------------------------------------------
    def parent(self):
        return SimpleNamespace(
            _widget_manager=self._widget_manager,
            _gl_compositor=self._compositor(),
            _overlay_fade_expected=set(),
            _overlay_fade_started=True,
            _spotify_secondary_not_before_ts=0.0,
        )

    def parentWidget(self):
        return None

    def _compositor(self):
        return SimpleNamespace(
            is_visualizer_presentation_ready=lambda: self.renderer_ready,
            visualizer_can_reveal=lambda: self.renderer_ready,
        )

    def isVisible(self):
        return self._visible

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    # -- production seams under test ------------------------------------
    def start(self):
        startup_staging.start_legacy(self)

    def stop(self):
        startup_staging.stop_legacy(self)

    def suspend_for_edit(self, *, reason="custom_edit"):
        return startup_staging.suspend_for_edit(self, reason=reason)

    def resume_after_edit(self, *, reason="custom_edit"):
        return startup_staging.resume_after_edit(self, reason=reason)

    def begin_spotify_secondary_stage(self):
        startup_staging.begin_spotify_secondary_stage(self)

    # -- collaborators the state machine calls ---------------------------
    def _seed_playback_state_from_anchor(self, *, reason, request_refresh_if_missing=False):
        self.seed_calls.append(reason)

    def _reset_engine_state(self, *, reason):
        self.engine_resets.append(reason)
        self._engine.reset_smoothing_state()

    def _should_capture_audio_now(self):
        return bool(self._enabled and self._spotify_playing)

    def _trigger_wake(self, *, reason, allow_defer=True):
        pass

    def _start_widget_fade_in(self, duration_ms=None):
        self.fade_ins += 1
        self._visible = True

    def _on_tick(self):
        pass

    def detach_from_animation_manager(self):
        pass

    def _reset_latency_diagnostics(self):
        pass

    def _reset_bubble_cadence(self):
        pass

    def _log_perf_snapshot(self, reset=False):
        pass

    def _clear_gl_overlay(self):
        pass


@pytest.fixture
def runtime(qt_app, np_module, monkeypatch):
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    devices: list[_FakeCaptureDevice] = []

    def _create(config=None):
        device = _FakeCaptureDevice(config)
        devices.append(device)
        return device

    monkeypatch.setattr(
        "widgets.spotify_visualizer.audio_worker.create_audio_capture", _create
    )
    # The shared-engine registry must hand back OUR engine, not a global one.
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    monkeypatch.setattr(
        "widgets.spotify_visualizer.beat_engine.get_shared_spotify_beat_engine",
        lambda bar_count: engine,
    )
    monkeypatch.setattr(
        startup_staging, "prewarm_parent_overlay", lambda widget: None
    )
    monkeypatch.setattr(
        startup_staging, "_schedule_startup_stage", lambda delay_ms, cb: cb()
    )

    manager = _OneShotSecondaryStage()
    thread_manager = _ThreadManager()
    widget = _EditVisualizer(engine, manager, thread_manager)

    yield SimpleNamespace(
        widget=widget,
        engine=engine,
        manager=manager,
        thread_manager=thread_manager,
        devices=devices,
        np=np_module,
    )

    try:
        engine.force_stop()
    except Exception:
        pass
    engine.deleteLater()


def _bring_up(rt):
    """Ordinary startup, including the one-shot secondary stage completing."""
    rt.widget.start()
    assert rt.widget._startup_secondary_stage_pending is True
    assert rt.manager.run_secondary_stage_once() is True
    assert rt.widget._startup_hot_start_started is True
    assert rt.engine._audio_worker.is_running() is True, "startup never started audio"
    return rt


# ---------------------------------------------------------------------------
# The failure, reproduced
# ---------------------------------------------------------------------------


class TestTheInstalledCancelFailure:
    def test_the_secondary_stage_really_is_one_shot(self, runtime):
        _bring_up(runtime)
        assert runtime.manager.fires == 1
        assert runtime.manager.run_secondary_stage_once() is False

    def test_stop_then_start_mid_runtime_never_restarts_audio(self, runtime):
        """The exact installed Cancel path, proving why it had to change."""
        rt = _bring_up(runtime)

        rt.widget.stop()
        assert rt.engine._audio_worker.is_running() is False

        rt.widget.start()

        # start_legacy() defers to a secondary stage that cannot fire again.
        assert rt.widget._startup_secondary_stage_pending is True
        assert rt.widget._startup_hot_start_started is False
        assert rt.engine._audio_worker.is_running() is False, (
            "if this ever starts, the installed failure mode no longer exists "
            "and this bar should be revisited"
        )


# ---------------------------------------------------------------------------
# The edit suspend/resume seam
# ---------------------------------------------------------------------------


class TestEditSuspend:
    def test_suspend_stops_the_logical_tick_and_audio(self, runtime):
        rt = _bring_up(runtime)
        assert rt.thread_manager.live_timers

        assert rt.widget.suspend_for_edit(reason="custom_edit") is True

        assert rt.widget.is_edit_suspended() if hasattr(rt.widget, "is_edit_suspended") else True
        assert startup_staging.is_edit_suspended(rt.widget) is True
        assert rt.widget._enabled is False
        assert rt.widget._bars_timer is None
        assert rt.thread_manager.live_timers == []
        assert rt.engine._audio_worker.is_running() is False

    def test_suspend_retains_startup_and_runtime_identity(self, runtime):
        rt = _bring_up(runtime)
        generation_before = rt.engine.get_generation_id()
        activation_before = rt.engine.get_activation_id()

        rt.widget.suspend_for_edit(reason="custom_edit")

        # Staged-startup bookkeeping is untouched: suspend is not a startup exit.
        assert rt.widget._startup_hot_start_started is True
        assert rt.widget._startup_secondary_stage_pending is False
        assert rt.engine.get_generation_id() == generation_before
        assert rt.engine.get_activation_id() == activation_before

    def test_suspend_is_idempotent(self, runtime):
        rt = _bring_up(runtime)
        assert rt.widget.suspend_for_edit(reason="a") is True
        assert rt.widget.suspend_for_edit(reason="b") is False

    def test_suspend_refuses_a_runtime_that_is_not_enabled(self, runtime):
        rt = runtime
        assert rt.widget.suspend_for_edit(reason="custom_edit") is False

    def test_suspend_does_not_reset_the_engine(self, runtime):
        rt = _bring_up(runtime)
        resets = list(rt.widget.engine_resets)
        rt.widget.suspend_for_edit(reason="custom_edit")
        assert rt.widget.engine_resets == resets


class TestEditResume:
    def test_cancel_resumes_audio_without_a_second_secondary_stage(self, runtime):
        """The bar the previous stub-only test could not express."""
        rt = _bring_up(runtime)
        fires_before = rt.manager.fires

        rt.widget.suspend_for_edit(reason="custom_edit")
        assert rt.engine._audio_worker.is_running() is False

        assert rt.widget.resume_after_edit(reason="custom_edit_restore") is True

        assert rt.engine._audio_worker.is_running() is True, (
            "Cancel left the visualizer without audio - the installed failure"
        )
        assert rt.manager.fires == fires_before, (
            "resume required another one-shot secondary-stage event"
        )
        assert rt.widget._startup_secondary_stage_pending is False

    def test_resume_restarts_the_logical_tick(self, runtime):
        rt = _bring_up(runtime)
        rt.widget.suspend_for_edit(reason="custom_edit")
        assert rt.thread_manager.live_timers == []

        rt.widget.resume_after_edit(reason="custom_edit_restore")

        assert rt.widget._enabled is True
        assert rt.widget._bars_timer is not None
        assert len(rt.thread_manager.live_timers) == 1
        assert rt.thread_manager.live_timers[0].callback == rt.widget._on_tick

    def test_resume_does_not_advance_the_engine_generation(self, runtime):
        rt = _bring_up(runtime)
        rt.widget.suspend_for_edit(reason="custom_edit")
        before = (rt.engine.get_generation_id(), rt.engine.get_activation_id())

        rt.widget.resume_after_edit(reason="custom_edit_restore")

        assert (rt.engine.get_generation_id(), rt.engine.get_activation_id()) == before, (
            "cancelling an edit is not a runtime activation boundary"
        )

    def test_resume_does_not_reset_engine_state(self, runtime):
        rt = _bring_up(runtime)
        rt.widget.suspend_for_edit(reason="custom_edit")
        resets = list(rt.widget.engine_resets)
        rt.widget.resume_after_edit(reason="custom_edit_restore")
        assert rt.widget.engine_resets == resets

    def test_resume_restarts_capture_exactly_once(self, runtime):
        rt = _bring_up(runtime)
        starts_after_startup = sum(d.starts for d in rt.devices)

        rt.widget.suspend_for_edit(reason="custom_edit")
        rt.widget.resume_after_edit(reason="custom_edit_restore")

        assert sum(d.starts for d in rt.devices) == starts_after_startup + 1

    def test_resume_reveals_through_the_readiness_owner(self, runtime):
        """Not a direct fade: the layer was cleared, so it must prepare first."""
        rt = _bring_up(runtime)
        rt.widget._visible = True
        rt.widget.suspend_for_edit(reason="custom_edit")
        rt.widget.fade_ins = 0

        rt.widget.renderer_ready = False
        rt.widget.resume_after_edit(reason="custom_edit_restore")

        assert rt.widget.fade_ins == 0, "the fade began before the renderer was ready"
        assert rt.widget._startup_reveal_pending is True

        # The compositor readiness notification re-enters the same gate.
        rt.widget.renderer_ready = True
        startup_staging.finish_staged_startup_reveal(rt.widget, reason="renderer_ready")
        assert rt.widget.fade_ins == 1
        assert rt.widget._startup_reveal_pending is False

    def test_a_visualizer_hidden_before_edit_is_not_revealed(self, runtime):
        rt = _bring_up(runtime)
        rt.widget._visible = False
        rt.widget.suspend_for_edit(reason="custom_edit")
        rt.widget.fade_ins = 0

        rt.widget.resume_after_edit(reason="custom_edit_restore")

        assert rt.widget.fade_ins == 0
        assert rt.widget._startup_reveal_pending is False
        # Logical work still resumes; only presentation stays hidden.
        assert rt.widget._enabled is True
        assert rt.widget._bars_timer is not None

    def test_resume_is_idempotent(self, runtime):
        rt = _bring_up(runtime)
        rt.widget.suspend_for_edit(reason="custom_edit")
        assert rt.widget.resume_after_edit(reason="a") is True
        assert rt.widget.resume_after_edit(reason="b") is False

    def test_resume_without_suspend_is_a_no_op(self, runtime):
        rt = _bring_up(runtime)
        assert rt.widget.resume_after_edit(reason="custom_edit") is False

    def test_a_full_suspend_resume_cycle_leaves_a_live_runtime(self, runtime):
        rt = _bring_up(runtime)
        rt.widget._visible = True
        generation = rt.engine.get_generation_id()

        rt.widget.suspend_for_edit(reason="custom_edit")
        rt.widget.resume_after_edit(reason="custom_edit_restore")
        startup_staging.finish_staged_startup_reveal(rt.widget, reason="renderer_ready")

        assert rt.widget._enabled is True
        assert rt.widget._bars_timer is not None
        assert rt.engine._audio_worker.is_running() is True
        assert rt.engine.get_generation_id() == generation
        assert rt.widget.isVisible() is True
        assert rt.manager.fires == 1


# ---------------------------------------------------------------------------
# The CUSTOM manager uses the seam
# ---------------------------------------------------------------------------


class TestManagerUsesTheEditSeam:
    def _manager(self, vis):
        from rendering import custom_layout_manager as clm

        manager = clm.CustomLayoutManager.__new__(clm.CustomLayoutManager)
        manager._paused_visualizer = None
        manager._special_hidden = []
        manager._display = SimpleNamespace(_spotify_bars_overlay=None)
        manager._suspend_compositor_visualizer_presentation = lambda: None
        return manager, clm

    def test_edit_entry_prefers_suspend_over_stop(self, runtime):
        rt = _bring_up(runtime)
        rt.widget._visible = True
        manager, clm = self._manager(rt.widget)

        clm.CustomLayoutManager._pause_visualizer_for_edit_mode(manager, rt.widget)

        assert startup_staging.is_edit_suspended(rt.widget) is True
        # stop_legacy() would have cleared these.
        assert rt.widget._startup_hot_start_started is True
        assert manager._paused_visualizer[3] is True

    def test_cancel_resumes_through_the_seam(self, runtime):
        rt = _bring_up(runtime)
        rt.widget._visible = True
        manager, clm = self._manager(rt.widget)

        clm.CustomLayoutManager._pause_visualizer_for_edit_mode(manager, rt.widget)
        clm.CustomLayoutManager._restore_special_widgets(manager)

        assert startup_staging.is_edit_suspended(rt.widget) is False
        assert rt.engine._audio_worker.is_running() is True
        assert rt.manager.fires == 1
        assert manager._paused_visualizer is None

    def test_cancel_resumes_exactly_once(self, runtime):
        rt = _bring_up(runtime)
        rt.widget._visible = True
        manager, clm = self._manager(rt.widget)

        clm.CustomLayoutManager._pause_visualizer_for_edit_mode(manager, rt.widget)
        clm.CustomLayoutManager._restore_special_widgets(manager)
        clm.CustomLayoutManager._restore_special_widgets(manager)

        assert startup_staging.is_edit_suspended(rt.widget) is False
        assert rt.engine._audio_worker.is_running() is True

    def test_a_visualizer_without_the_seam_still_falls_back(self, runtime):
        """Older/foreign visualizer objects must not break edit mode."""
        from rendering import custom_layout_manager as clm

        stops: list[int] = []
        starts: list[int] = []
        legacy = SimpleNamespace(
            isVisible=lambda: True,
            stop=lambda: stops.append(1),
            start=lambda: starts.append(1),
            hide=lambda: None,
        )
        manager, _clm = self._manager(legacy)

        clm.CustomLayoutManager._pause_visualizer_for_edit_mode(manager, legacy)
        assert stops == [1]
        assert manager._paused_visualizer[3] is False

        clm.CustomLayoutManager._restore_special_widgets(manager)
        assert starts == [1]

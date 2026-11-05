"""Console display power: one event-driven authority pauses every per-frame consumer and resumes them clean.

Each test drives a production seam (the real window procedure, the authority's queued dispatch, the logical
runtime's park, the owners' power edges) and carries a negative control that the pre-authority code fails: there
was no listener, no park and no rebase, so a display-off changed nothing and a resume integrated the whole gap.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from core.display_power import (
    DisplayPowerAuthority,
    InertDisplayPowerBackend,
    create_display_power_backend,
    mutter_power_save_mode_is_on,
)

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="needs the real Windows message pump")


class _Backend:
    name = "test"

    def __init__(self, *_args, **_kwargs):
        self.started = self.closed = 0

    def start(self):
        self.started += 1
        return True

    def close(self):
        self.closed += 1


def _authority(qt_app):
    backends = []

    def factory(*args, **kwargs):
        backends.append(_Backend())
        return backends[-1]

    authority = DisplayPowerAuthority(backend_factory=factory)
    edges = []
    authority.power_changed.connect(lambda on, generation: edges.append((on, generation)))
    authority.start()
    return authority, edges, backends


# -- authority: coalescing, generations, retirement -------------------------------------------------------------

def test_a_burst_in_one_event_loop_turn_is_one_edge_and_a_round_trip_is_none(qt_app):
    authority, edges, _ = _authority(qt_app)
    for state in (0, 1, 0):
        authority.deliver_console_state(state)
    assert edges == []                     # queued, never re-entrant from the delivering call
    qt_app.processEvents()
    assert edges == [(False, 1)] and authority.is_on is False
    authority.deliver_console_state(1)
    authority.deliver_console_state(0)     # off -> on -> off ends where it started: no rebuild, no edge
    qt_app.processEvents()
    assert edges == [(False, 1)] and authority.generation == 1
    authority.deliver_console_state(2)     # dimmed counts as on
    qt_app.processEvents()
    assert edges == [(False, 1), (True, 2)]
    authority.deliver_console_state(1)     # dimmed -> on is not an edge
    qt_app.processEvents()
    assert edges == [(False, 1), (True, 2)]
    assert authority.describe()["coalesced"] >= 3


def test_retirement_closes_the_backend_once_and_ignores_later_deliveries(qt_app):
    authority, edges, backends = _authority(qt_app)
    authority.deliver_console_state(0)
    authority.retire()
    authority.retire()
    qt_app.processEvents()
    assert backends[0].closed == 1 and edges == [] and authority.is_retired
    authority.deliver_console_state(0)
    qt_app.processEvents()
    assert edges == []
    with pytest.raises(RuntimeError):
        authority.start()


def test_an_unregistrable_platform_source_falls_back_to_the_explicit_inert_backend(qt_app):
    class Failing(_Backend):
        def start(self):
            return False

    authority = DisplayPowerAuthority(backend_factory=lambda *a, **k: Failing())
    authority.start()
    assert isinstance(authority.backend, InertDisplayPowerBackend) and authority.is_on
    authority.retire()


def test_inert_and_linux_mapping_report_on_unless_the_platform_says_off(qt_app, monkeypatch):
    # The Linux branch itself is exercised in tests/test_linux_display_power.py; this is the shared contract.
    monkeypatch.setattr(sys, "platform", "sunos5")
    backend = create_display_power_backend(lambda _s: None, lambda _o: None)
    assert isinstance(backend, InertDisplayPowerBackend) and backend.start() is True
    assert [mutter_power_save_mode_is_on(v) for v in (0, 1, 2, 3, -1, "x", None)] == [
        True, False, False, False, None, None, None]


# -- the Windows production seam --------------------------------------------------------------------------------

@windows_only
def test_the_real_window_procedure_turns_the_console_state_into_one_edge_and_unregisters(qt_app):
    from ctypes import wintypes

    from core.windows.display_power_notifier import (
        GUID, PBT_POWERSETTINGCHANGE, WM_POWERBROADCAST, WindowsDisplayPowerNotifier, display_state_payload,
    )

    user32 = ctypes.WinDLL("user32")
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.IsWindow.argtypes = [wintypes.HWND]
    authority = DisplayPowerAuthority()
    edges = []
    authority.power_changed.connect(lambda on, generation: edges.append((on, generation)))
    authority.start()
    notifier = authority.backend
    assert isinstance(notifier, WindowsDisplayPowerNotifier) and notifier.registered
    hwnd = notifier.hwnd
    qt_app.processEvents()                 # Windows' immediate current-state notification (on): no edge
    if not authority.is_on:
        authority.retire()
        pytest.skip("the console display is really off")
    assert edges == []

    def send(payload):
        return user32.SendMessageW(hwnd, WM_POWERBROADCAST, PBT_POWERSETTINGCHANGE, ctypes.addressof(payload))

    # Negative controls: another power setting, and another broadcast kind, are not the display state.
    other = GUID(0x02731015, 0x4510, 0x4526, (ctypes.c_ubyte * 8)(0x99, 0xE6, 0xE5, 0xA1, 0x7E, 0xBD, 0x1A, 0xEA))
    send(display_state_payload(0, setting=other))
    user32.SendMessageW(hwnd, WM_POWERBROADCAST, 0x0004, 0)    # PBT_APMSUSPEND
    qt_app.processEvents()
    assert edges == [] and authority.is_on

    assert send(display_state_payload(0)) == 1
    qt_app.processEvents()
    assert edges == [(False, 1)]
    send(display_state_payload(1))
    qt_app.processEvents()
    assert edges == [(False, 1), (True, 2)]

    authority.retire()
    assert not notifier.registered and not user32.IsWindow(hwnd)


# -- the logical runtime parks with no cadence and resumes on a fresh deadline sequence --------------------------

def _counting_runtime(**kwargs):
    from widgets.spotify_visualizer.logical_runtime import VisualizerLogicalRuntime

    steps, stepped = [], threading.Event()

    def step(now):
        steps.append(now)
        stepped.set()

    return VisualizerLogicalRuntime(step=step, interval_s=0.005, generation=0, **kwargs), steps, stepped


def test_a_parked_logical_runtime_takes_no_steps_and_resumes_without_counting_the_gap():
    runtime, steps, stepped = _counting_runtime()
    runtime.start()
    try:
        assert stepped.wait(2.0)
        assert runtime.park() is True and runtime.is_parked()
        parked_at = len(steps)
        time.sleep(0.25)                   # ~50 deadlines of wall time
        assert len(steps) == parked_at     # no cadence at all while parked
        skipped = runtime.describe()["skipped_deadlines"]
        stepped.clear()
        assert runtime.unpark() is True
        assert stepped.wait(2.0)
        # The parked interval is not a run of missed deadlines (it would be ~50 on a continuing sequence).
        assert runtime.describe()["skipped_deadlines"] - skipped < 5
        assert runtime.describe()["parks"] == 1
    finally:
        assert runtime.stop() is True      # stop also releases a parked loop


def test_stop_releases_a_parked_runtime_and_a_runtime_started_parked_never_steps():
    runtime, steps, _ = _counting_runtime(parked=True)
    runtime.start()
    time.sleep(0.05)
    assert steps == [] and runtime.is_parked()
    assert runtime.stop(timeout_s=2.0) is True and not runtime.is_running()


def test_the_controller_keeps_the_park_request_for_a_runtime_started_later():
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    controller = VisualizerRuntimeController(runtime_generation=0, engine_factory=lambda _n: None)
    steps = []
    assert controller.set_logical_parked(True) is True
    runtime = controller.start_logical_runtime(step=steps.append, interval_s=0.005)
    try:
        time.sleep(0.05)
        assert steps == [] and runtime.park_requested
        controller.set_logical_parked(False)
        deadline = time.monotonic() + 2.0
        while not steps and time.monotonic() < deadline:
            time.sleep(0.005)
        assert steps
    finally:
        controller.stop_logical_runtime()


# -- resume integrates no parked gap -----------------------------------------------------------------------------

def test_resume_rebase_keeps_an_unclamped_phase_from_integrating_the_parked_hours():
    from tests.test_neon_terrain_reaction import _advance, _lanes
    from widgets.spotify_visualizer.shockwave_frame_runtime import ShockwaveGridFrameRuntime
    from widgets.spotify_visualizer.tick_pipeline import rebase_logical_clocks_after_park

    hit = _lanes(1, 3, 1, 1, 1)
    control, resumed = ShockwaveGridFrameRuntime(), ShockwaveGridFrameRuntime()
    for runtime in (control, resumed):
        for t in (10.0, 10.011, 10.022):
            _advance(runtime, t, hit)
    before = resumed._terrain_phase
    state = SimpleNamespace(_last_update_ts=10.022, _bubble_last_tick_ts=10.022, _perf_tick_last_ts=10.022)
    assert rebase_logical_clocks_after_park(state, (resumed, object())) == 1
    assert (state._last_update_ts, state._bubble_last_tick_ts, state._perf_tick_last_ts) == (-1.0, 0.0, None)
    later = 10.022 + 3 * 3600.0
    resumed_phase = _advance(resumed, later, hit).phase
    # Negative control: the old resume integrated three hours of phase in one step.
    assert abs(_advance(control, later, hit).phase - before) > 1.0
    assert resumed_phase == pytest.approx(before)
    # Warm state survives the rebase: the next ordinary step advances from it.
    assert _advance(resumed, later + 0.011, hit).phase != pytest.approx(0.0)


def test_every_dt_integrating_mode_state_exposes_the_rebase():
    from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime
    from widgets.spotify_visualizer.oscilloscope_frame_runtime import OscilloscopeFrameRuntime
    from widgets.spotify_visualizer.sphere_frame_runtime import SphereFrameRuntime
    from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime

    eb, waveform, sphere = ExtrudedBubbleFrameRuntime(), WaveformRibbonFrameRuntime(), SphereFrameRuntime()
    eb._last_ts = waveform._last_ts = 5.0
    sphere._activation_identity, sphere._last_ts = (0, 0, 0), 5.0
    devcurve, scope = DevCurveFrameRuntime(), OscilloscopeFrameRuntime()
    devcurve._last_timestamp = scope._last_timestamp = 5.0
    for runtime in (eb, waveform, sphere, devcurve, scope):
        runtime.rebase_clock()
    assert eb._last_ts is None and waveform._last_ts is None and sphere._last_ts is None
    assert devcurve._last_timestamp == 0.0 and scope._last_timestamp == 0.0


# -- consumers: frame pacer, display runtime, Visualizer owner, DisplayManager, engine, clock ---------------------

def test_power_suspension_stops_transition_frames_independently_of_visibility():
    from tests.test_qtquick_frame_pacer import _pacer

    pacer, window, native = _pacer()
    pacer.set_transition_active(True)
    assert pacer.is_active() and native.calls[-1][0] is True
    assert pacer.set_power_suspended(True) is True
    assert not pacer.is_active() and native.calls[-1][0] is False
    assert pacer.set_power_suspended(True) is False
    pacer.pause()                                  # hidden while off: power-on must not restart frames
    pacer.set_power_suspended(False)
    assert not pacer.is_active()
    pacer.resume()
    assert pacer.is_active() and native.calls[-1][0] is True
    assert pacer.describe()["power_suspended"] is False


def test_display_runtime_off_snaps_the_transition_and_suspends_its_frames():
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.state import QuickRuntimePhase
    from tests.test_qtquick_frame_pacer import _pacer

    pacer, _window, _native = _pacer()
    pacer.set_transition_active(True)
    cancelled = []
    fake = SimpleNamespace(_phase=QuickRuntimePhase.VISIBLE, _pacer=pacer,
                           _transition=SimpleNamespace(cancel_current=lambda *, reason: cancelled.append(reason)))
    assert QuickDisplayRuntime.set_display_power(fake, False) is True
    assert cancelled == ["display-power-off"] and not pacer.is_active()
    assert QuickDisplayRuntime.set_display_power(fake, True) is True
    assert cancelled == ["display-power-off"] and pacer.is_active()
    fake._phase = QuickRuntimePhase.RETIRING
    assert QuickDisplayRuntime.set_display_power(fake, False) is False


class _Engine:
    def __init__(self):
        self.refs, self.events = 0, []

    def acquire(self):
        self.refs += 1
        self.events.append("acquire")

    def release(self):
        self.refs -= 1
        self.events.append("release")

    def ensure_started(self):
        self.events.append("ensure_started")

    def get_latest_authoritative_frame(self):
        return 12.0, 3, 4

    def get_generation_id(self):
        return 3

    def get_activation_id(self):
        return 4

    def get_authoritative_frame_commit_seq(self):
        return 77


def _owner(engine):
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    controller = VisualizerRuntimeController(runtime_generation=0, engine_factory=lambda _n: engine)
    controller.ensure_engine()
    controller.playing = True
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._retired, owner._started, owner._controller = False, True, controller
    owner._display_power_on, owner._engine_released_for_display_power = True, False
    engine.acquire()
    owner._engine_acquired = True
    return owner, controller


def test_visualizer_off_parks_and_releases_capture_and_on_resumes_warm_fenced_and_rebased():
    engine = _Engine()
    owner, controller = _owner(engine)
    steps = []
    runtime = controller.start_logical_runtime(step=steps.append, interval_s=0.005)
    state = controller.logical_tick_state
    try:
        deadline = time.monotonic() + 2.0
        while not steps and time.monotonic() < deadline:
            time.sleep(0.005)
        controller.logical_mailbox.publish(object(), generation=0)
        assert owner.set_display_power(False) is True
        assert runtime.is_parked() and controller.logical_mailbox.peek() is None
        assert engine.refs == 0 and engine.events[-1] == "release"
        assert owner.set_display_power(False) is False          # idempotent: no double release
        state._last_update_ts = 99.0
        assert owner.set_display_power(True) is True
        assert engine.refs == 1 and engine.events[-2:] == ["acquire", "ensure_started"]
        assert state._waiting_for_fresh_engine_frame is True and state._pending_engine_frame_epoch == 77
        assert state._last_update_ts == -1.0                    # rebased while parked
        assert not runtime.park_requested and controller.logical_runtime is runtime
    finally:
        controller.stop_logical_runtime()


def test_display_manager_applies_edges_in_generation_order_to_units_and_owner():
    from engine.display_manager import DisplayManager
    from rendering.quick.display_unit import QuickDisplayUnit

    calls = []
    unit = QuickDisplayUnit.__new__(QuickDisplayUnit)
    unit._retired, unit._screen_index = False, 1
    unit._runtime = SimpleNamespace(set_display_power=lambda on: calls.append(("runtime", on)) or True)
    manager = DisplayManager.__new__(DisplayManager)
    manager._retired, manager.displays = False, [unit, SimpleNamespace()]
    manager._display_power_on, manager._display_power_generation = True, 0
    manager._quick_visualizer_owner = SimpleNamespace(set_display_power=lambda on: calls.append(("owner", on)))
    assert DisplayManager.set_display_power(manager, False, generation=2) == 1
    assert calls == [("runtime", False), ("owner", False)] and manager.display_power_on is False
    assert DisplayManager.set_display_power(manager, True, generation=1) == 0   # stale edge
    assert calls == [("runtime", False), ("owner", False)] and manager.display_power_on is False


def test_engine_pauses_rotation_and_clock_and_resumes_with_a_fresh_hold(monkeypatch):
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    import widgets.clock_ticker as clock_ticker

    class Timer:
        def __init__(self):
            self.active, self.starts = True, 0

        def isActive(self):  # noqa: N802
            return self.active

        def stop(self):
            self.active = False

        def start(self):
            self.active, self.starts = True, self.starts + 1

        def interval(self):
            return 30_000

    ticker = []
    monkeypatch.setattr(clock_ticker, "get_global_clock_ticker",
                        lambda: SimpleNamespace(set_display_power_suspended=ticker.append))
    applied = []
    engine = ScreensaverEngine.__new__(ScreensaverEngine)
    engine._state = EngineState.RUNNING
    engine._rotation_timer = timer = Timer()
    engine._display_power = authority = SimpleNamespace(generation=1, is_on=False)
    engine.display_manager = SimpleNamespace(set_display_power=lambda on, generation: applied.append((on, generation)))
    engine._display_selection_suspended = lambda: False
    engine._on_display_power_changed(False, 1)
    assert not timer.active and applied == [(False, 1)] and ticker == [True]
    engine._on_display_power_changed(True, 0)                   # stale: ignored
    assert not timer.active and applied == [(False, 1)]
    authority.generation, authority.is_on = 2, True
    engine._on_display_power_changed(True, 2)
    assert timer.active and timer.starts == 1 and applied[-1] == (True, 2) and ticker == [True, False]


def test_one_power_edge_pauses_the_whole_chain_and_the_next_resumes_it(qt_app, monkeypatch):
    """Authority -> engine -> DisplayManager -> display runtime + Visualizer owner, through production methods."""
    from engine.display_manager import DisplayManager
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    from rendering.quick.display_unit import QuickDisplayUnit
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.state import QuickRuntimePhase
    from tests.test_qtquick_frame_pacer import _pacer
    import widgets.clock_ticker as clock_ticker

    monkeypatch.setattr(clock_ticker, "get_global_clock_ticker",
                        lambda: SimpleNamespace(set_display_power_suspended=lambda _s: None))
    authority, _edges, _ = _authority(qt_app)
    pacer, _window, _native = _pacer()
    pacer.set_transition_active(True)
    display_runtime = SimpleNamespace(_phase=QuickRuntimePhase.VISIBLE, _pacer=pacer,
                                      _transition=SimpleNamespace(cancel_current=lambda *, reason: True))
    display_runtime.set_display_power = lambda on: QuickDisplayRuntime.set_display_power(display_runtime, on)
    unit = QuickDisplayUnit.__new__(QuickDisplayUnit)
    unit._retired, unit._screen_index, unit._runtime = False, 0, display_runtime
    engine_source = _Engine()
    owner, controller = _owner(engine_source)
    steps = []
    logical = controller.start_logical_runtime(step=steps.append, interval_s=0.005)
    manager = DisplayManager.__new__(DisplayManager)
    manager._retired, manager.displays, manager._quick_visualizer_owner = False, [unit], owner
    manager._display_power_on, manager._display_power_generation = True, 0
    engine = ScreensaverEngine.__new__(ScreensaverEngine)
    engine._state, engine._rotation_timer, engine.display_manager = EngineState.RUNNING, None, manager
    engine._display_power = authority
    engine._display_selection_suspended = lambda: False
    authority.power_changed.connect(engine._on_display_power_changed)
    try:
        authority.deliver_console_state(0)
        assert pacer.is_active() and not logical.is_parked()      # nothing acts inside the delivering call
        qt_app.processEvents()
        assert not pacer.is_active() and logical.is_parked() and engine_source.refs == 0
        parked_steps = len(steps)
        time.sleep(0.05)
        assert len(steps) == parked_steps
        authority.deliver_console_state(1)
        qt_app.processEvents()
        assert pacer.is_active() and not logical.park_requested and engine_source.refs == 1
        deadline = time.monotonic() + 2.0
        while len(steps) == parked_steps and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(steps) > parked_steps
    finally:
        controller.stop_logical_runtime()
        authority.retire()


def test_engine_start_while_off_leaves_rotation_waiting():
    from engine.screensaver_engine import ScreensaverEngine

    engine = ScreensaverEngine.__new__(ScreensaverEngine)
    engine._display_power = SimpleNamespace(is_on=False)
    assert engine._display_power_on() is False
    engine._display_power = None
    assert engine._display_power_on() is True


def test_clock_ticker_stops_while_off_and_ticks_at_once_on_resume(qt_app, monkeypatch):
    from widgets.clock_ticker import get_global_clock_ticker

    class Timer:
        stopped = 0

        def stop(self):
            Timer.stopped += 1

    ticker = get_global_clock_ticker()
    scheduled, ticks = [], []
    for name, value in (("_subscribers", []), ("_timer_handle", None), ("_is_running", False),
                        ("_display_power_suspended", False),
                        ("_thread_manager", SimpleNamespace(schedule_recurring=lambda interval_ms, func, description:
                                                            scheduled.append(interval_ms) or Timer()))):
        monkeypatch.setattr(ticker, name, value)
    callback = lambda: ticks.append(1)  # noqa: E731
    ticker.subscribe(callback)
    assert scheduled == [1000]
    assert ticker.set_display_power_suspended(True) is True
    assert ticker._timer_handle is None and Timer.stopped == 1
    ticker._start()
    assert scheduled == [1000]                                  # nothing restarts it while off
    assert ticker.set_display_power_suspended(False) is True
    assert scheduled == [1000, 1000] and ticks == [1]           # one immediate tick, then the cadence
    ticker.unsubscribe(callback)

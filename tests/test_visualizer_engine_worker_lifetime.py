"""Native core P2b, work order 5 slice 5.7 (dormancy, the supervisor's restart ownership, a session whose steps keep
failing) and checkpoint audit 9's A9-L1/A9-L2: the engine worker exists only while a Visualizer uses it.

The supervisor tests use process and queue stand-ins (no child process). The lifetime policy runs against a supervisor
stand-in and an inline IO lane, with the real queued settle on the GUI thread. The failing-step test runs a
worker-paced session in this process. One end-to-end test drives the REAL owner on a real ``WorkerType.VISUALIZER``
process (the gate rig: an unshown runtime, recorded PCM, no device). Every fix is shown with its negative control.
"""
from __future__ import annotations

import multiprocessing
import queue
import threading
import time

import pytest

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerResponse, WorkerState, WorkerType
from tools.visualizer_replay import owner_worker_gate as gate


@pytest.fixture(autouse=True)
def _no_device_and_a_fresh_run(monkeypatch):
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    yield
    engine_worker_link.reset_run_state_for_testing()


class _Process:
    """A child process stand-in: alive until killed; a graceful stop is honoured at once."""

    _pids = iter(range(50_000, 60_000))

    def __init__(self) -> None:
        self.pid = next(self._pids)
        self.alive = True
        self.stopped = False

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout=None) -> None:
        return None

    def terminate(self) -> None:
        self.alive = False

    kill = terminate

    def close(self) -> None:
        return None


class _RequestQueue:
    """A request queue whose SHUTDOWN stops its process (the worker's graceful exit)."""

    def __init__(self, process: _Process) -> None:
        self._process = process

    def put_nowait(self, data) -> None:
        if data.get("msg_type") in (MessageType.SHUTDOWN.value, MessageType.SHUTDOWN):
            self._process.alive = False
            self._process.stopped = True

    def cancel_join_thread(self) -> None:
        return None

    close = join_thread = cancel_join_thread


class _ResponseQueue(queue.Queue):
    def cancel_join_thread(self) -> None:
        return None

    def close(self) -> None:
        return None

    def join_thread(self) -> None:
        return None


def _install(supervisor: ProcessSupervisor, worker_type: WorkerType) -> _Process:
    """What ``_start_role`` leaves behind for a started, ready worker (no child process)."""
    process = _Process()
    with supervisor._lock:
        supervisor._workers[worker_type] = process
        supervisor._request_queues[worker_type] = _RequestQueue(process)
        supervisor._response_queues[worker_type] = _ResponseQueue()
        supervisor._health[worker_type].state = WorkerState.RUNNING
        supervisor._health[worker_type].record_heartbeat()
    return process


def _reply(correlation: str) -> dict:
    return WorkerResponse(msg_type=MessageType.VIS_START, seq_no=1, correlation_id=correlation, success=True).to_dict()


# ----------------------------------------------------------------------------------------- the supervisor (3a, 3b)


@pytest.mark.parametrize("pre_fix", (False, True))
def test_starting_a_dead_role_retires_its_stale_response_listener(monkeypatch, pre_fix):
    # 5.7 (3a): the worker died with a listener blocked on its queue. Starting the role again must retire that listener
    # in the supervisor (the link used to stop the role first), or a callback registered for the fresh worker waits on a
    # listener that never reads the fresh queue. Negative control: without the retirement, the fresh reply never
    # arrives and the dead worker's callback is never cancelled.
    supervisor = ProcessSupervisor()
    try:
        dead = _install(supervisor, WorkerType.VISUALIZER)
        cancelled: list = []
        assert supervisor.register_response_callback(WorkerType.VISUALIZER, "old", cancelled.append)
        dead.alive = False
        if pre_fix:
            monkeypatch.setattr(supervisor, "_retire_dead_role", lambda _worker_type: None)

        def start_role(worker_type):
            _install(supervisor, worker_type)
            return True

        monkeypatch.setattr(supervisor, "_start_role", start_role)
        assert supervisor.start(WorkerType.VISUALIZER)
        delivered = threading.Event()
        assert supervisor.register_response_callback(WorkerType.VISUALIZER, "fresh", lambda _r: delivered.set())
        supervisor._response_queues[WorkerType.VISUALIZER].put(_reply("fresh"))
        if pre_fix:
            assert not delivered.wait(0.5) and cancelled == []
            return
        assert delivered.wait(2.0)
        assert cancelled == [None]                                  # the dead worker's correlation was cancelled
    finally:
        supervisor.shutdown(timeout=1.0)


@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_heartbeat_retirement_never_stops_the_fresh_worker_its_client_started(monkeypatch, pre_fix):
    # 5.7 (3b): the heartbeat judged the engine worker dead; before it acts, the link (the role's one starter) has
    # started a fresh worker. The heartbeat only retires the process it judged (fenced by identity) and never starts
    # one. Negative control (the pre-5.7 heartbeat: an unfenced restart): the fresh worker is stopped.
    supervisor = ProcessSupervisor()
    try:
        judged = _install(supervisor, WorkerType.VISUALIZER)
        judged.alive = False
        decisions: list = []
        act = supervisor._retire_judged_process
        monkeypatch.setattr(supervisor, "_retire_judged_process",
                            lambda worker_type, process: decisions.append((worker_type, process)))
        supervisor._heartbeat_check()
        assert decisions == [(WorkerType.VISUALIZER, judged)]
        supervisor._stop_role(WorkerType.VISUALIZER, 0.0)           # the link's start: the dead entry, then a fresh one
        fresh = _install(supervisor, WorkerType.VISUALIZER)
        starts: list = []
        monkeypatch.setattr(supervisor, "start", lambda worker_type: starts.append(worker_type) or True)
        if pre_fix:
            supervisor._health[WorkerType.VISUALIZER].state = WorkerState.ERROR    # as the heartbeat judged it
            supervisor._health[WorkerType.VISUALIZER].restart_count = 0
            supervisor.restart(WorkerType.VISUALIZER)
            assert fresh.stopped and supervisor._workers.get(WorkerType.VISUALIZER) is None
            return
        assert act(WorkerType.VISUALIZER, judged) is False
        assert supervisor._workers[WorkerType.VISUALIZER] is fresh and fresh.alive and not fresh.stopped
        assert starts == []                                          # the heartbeat never starts the role
    finally:
        supervisor.shutdown(timeout=1.0)


def _fake_time(sleeps: list):
    """The supervisor module's clock with ``sleep`` recorded instead of slept (the restart's backoff)."""
    from types import SimpleNamespace

    return SimpleNamespace(time=time.time, monotonic=time.monotonic, perf_counter=time.perf_counter,
                           sleep=sleeps.append)


@pytest.mark.parametrize("role", (WorkerType.IMAGE, WorkerType.IMAGE_PREFETCH))
def test_the_heartbeat_restarts_a_dead_image_worker_once_after_its_backoff(monkeypatch, role):
    # Checkpoint audit 10, A10-L3: the image roles keep the heartbeat's restart (only the engine worker's belongs to
    # its client), fenced by the judged process's identity since 5.7. A dead image worker: one stop of the dead entry,
    # the backoff, one start; one restart counted; the role running its fresh process.
    import core.process.supervisor as supervisor_module

    supervisor = ProcessSupervisor()
    try:
        dead = _install(supervisor, role)
        dead.alive = False
        sleeps: list = []
        starts: list = []
        monkeypatch.setattr(supervisor_module, "time", _fake_time(sleeps))

        def start_role(worker_type):
            starts.append(worker_type)
            _install(supervisor, worker_type)
            return True

        monkeypatch.setattr(supervisor, "_start_role", start_role)
        supervisor._heartbeat_check()
        assert starts == [role] and len(sleeps) == 1 and sleeps[0] > 0.0
        health = supervisor.get_health(role)
        assert health.restart_count == 1 and health.state == WorkerState.RUNNING
        assert supervisor._workers[role] is not dead and supervisor._workers[role].alive
    finally:
        supervisor.shutdown(timeout=1.0)


def test_a_heartbeat_restart_of_an_image_worker_replaced_meanwhile_does_nothing_and_charges_nothing(monkeypatch):
    # A10-L3: the heartbeat judged the image worker dead; a foreground ``start(IMAGE)`` (holding the role's lifecycle
    # lock) replaces it before the restart acts. The restart stops nothing, starts nothing, and since it restarted
    # nothing it uses none of the role's MAX_RESTARTS_PER_WINDOW. Negative control (the pre-fix restart: an unlocked
    # identity check, then ``record_restart``, then the fenced stop): the skip still charged one restart.
    import core.process.supervisor as supervisor_module

    role = WorkerType.IMAGE
    supervisor = ProcessSupervisor()
    try:
        judged = _install(supervisor, role)
        judged.alive = False
        supervisor._health[role].state = WorkerState.ERROR          # as the heartbeat judged it ("Process died")
        sleeps: list = []
        starts: list = []
        monkeypatch.setattr(supervisor_module, "time", _fake_time(sleeps))
        monkeypatch.setattr(supervisor, "start", lambda worker_type: starts.append(worker_type) or True)
        real_lock = supervisor._lifecycle_locks[role]
        waiting = threading.Event()

        class _Signalling:
            """The role's lifecycle lock, announcing the restart's attempt to take it."""

            def __enter__(self):
                waiting.set()
                return real_lock.__enter__()

            def __exit__(self, *exc):
                return real_lock.__exit__(*exc)

        supervisor._lifecycle_locks[role] = _Signalling()
        result: list = []
        real_lock.acquire()                           # the foreground start, mid-flight
        try:
            restart = threading.Thread(target=lambda: result.append(supervisor.restart(role, judged=judged)))
            restart.start()
            assert waiting.wait(5.0)
            supervisor._stop_role(role, 0.0)          # what the start does: the dead entry, then its fresh process
            fresh = _install(supervisor, role)
        finally:
            real_lock.release()
        restart.join(5.0)
        assert result == [True]
        assert supervisor._workers[role] is fresh and fresh.alive and not fresh.stopped
        assert starts == [] and sleeps == []
        assert supervisor.get_health(role).restart_count == 0
    finally:
        supervisor.shutdown(timeout=1.0)


def test_a_hung_engine_worker_is_retired_not_restarted_and_without_a_restart_limit():
    # A hung engine worker (no heartbeat ack) is retired once the misses reach the threshold, whatever the restart
    # window says (a retirement is not a restart); the image roles keep their restart policy.
    from core.process.types import HealthStatus

    supervisor = ProcessSupervisor()
    try:
        hung = _install(supervisor, WorkerType.VISUALIZER)
        health = supervisor._health[WorkerType.VISUALIZER]
        health.last_heartbeat = time.time() - 3600.0
        health.missed_heartbeats = HealthStatus.MISSED_HEARTBEAT_THRESHOLD
        health.restart_count, health.last_restart = HealthStatus.MAX_RESTARTS_PER_WINDOW, time.time()
        supervisor._heartbeat_check()
        assert hung.stopped and WorkerType.VISUALIZER not in supervisor._workers
        assert supervisor.get_health(WorkerType.VISUALIZER).state == WorkerState.STOPPED
    finally:
        supervisor.shutdown(timeout=1.0)


def test_the_supervisor_names_the_engine_workers_pid_without_an_os_query():
    supervisor = ProcessSupervisor()
    try:
        assert supervisor.get_visualizer_worker_usage_snapshot() == {"visualizer_worker_pid": None}
        process = _install(supervisor, WorkerType.VISUALIZER)
        assert supervisor.get_visualizer_worker_usage_snapshot() == {"visualizer_worker_pid": process.pid}
    finally:
        supervisor.shutdown(timeout=1.0)


# ------------------------------------------------------------------------------ a session that keeps failing (3c)


@pytest.fixture(scope="module")
def pcm():
    from tools.visualizer_replay.live_engine_gate import paced_pcm

    return paced_pcm(3.0)


@pytest.mark.qt
@pytest.mark.parametrize("bounded", (True, False))
def test_a_session_whose_steps_keep_failing_fails_closed_into_the_owners_recovery(qt_app, pcm, monkeypatch, bounded):
    # A6-M3's open half: a worker-paced session whose every step raises publishes nothing. After
    # FAILED_STEPS_BEFORE_CLOSE consecutive failures it fails closed: its wake pipe ends (the owner's listener sees the
    # session's end, the existing recovery path), its cadence parks (no more steps), and a later edge is answered with
    # ``session_closed``. Negative control (no bound, the pre-5.7 session): the pipe never ends and it keeps stepping.
    from core.visualizer_engine.engine_worker import EngineSession, VisualizerEngineWorker
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from core.process.types import WorkerMessage
    from widgets.spotify_visualizer import tick_pipeline

    monkeypatch.setattr(EngineSession, "FAILED_STEPS_BEFORE_CLOSE", 30 if bounded else 10**9)

    def failing(_state):
        raise RuntimeError("injected tick failure")

    reader = PacketMailbox(role="reader")
    receiver, sender = multiprocessing.Pipe(duplex=False)
    ended = threading.Event()
    reader.listen_for_wakes(receiver, on_closed=ended.set)
    worker, serial = VisualizerEngineWorker(None, None), [0]

    def send(kind, **payload):
        serial[0] += 1
        return worker.handle_message(WorkerMessage(msg_type=kind, seq_no=serial[0], correlation_id=str(serial[0]),
                                                   payload=payload))

    try:
        samples, rate = pcm
        assert send(MessageType.VIS_CONFIGURE, mapping=reader.mapping_name, mode="spectrum", runtime_generation=1,
                    inputs="live", order="free", cadence="worker", pcm=samples, pcm_rate=rate, wake=sender).success
        monkeypatch.setattr(tick_pipeline, "logical_tick", failing)
        assert send(MessageType.VIS_START, playing=True).success
        session = worker._session
        runtime = session._controller.logical_runtime
        if not bounded:
            assert not ended.wait(1.5)
            assert runtime.describe()["step_failures"] > 60 and session.failed is None
            return
        assert ended.wait(5.0), runtime.describe()
        assert session.failed is not None and "consecutive steps failed" in session.failed
        deadline = time.monotonic() + 5.0
        while not runtime.is_parked() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert runtime.is_parked()
        failures = runtime.describe()["step_failures"]
        time.sleep(0.2)
        assert runtime.describe()["step_failures"] == failures            # parked: no step after the close
        reply = send(MessageType.VIS_SET_PLAYING, playing=False)
        assert not reply.success and reply.payload.get("session_closed") is True and worker._session is None
    finally:
        monkeypatch.undo()
        worker._close_session()
        reader.close()
        receiver.close()


# --------------------------------------------------------------------------------------------- the lifetime policy


class _Supervisor:
    """The lifetime's view of the supervisor: whether the worker runs, its start and its stop (recorded)."""

    def __init__(self, running: bool = True) -> None:
        self.running = running
        self.events: list[str] = []

    def is_running(self, _worker_type) -> bool:
        return self.running

    def start(self, _worker_type) -> bool:
        self.events.append("start")
        self.running = True
        return True

    def stop(self, _worker_type, timeout=None) -> bool:
        self.events.append("stop")
        self.running = False
        return True

    def get_visualizer_worker_usage_snapshot(self) -> dict:
        return {"visualizer_worker_pid": 1234 if self.running else None}


class _Lane:
    """An IO lane that runs each task when the test says (``inline``: at once)."""

    def __init__(self, inline: bool = True) -> None:
        self.inline = inline
        self.tasks: list = []

    def submit_io_task(self, func, *args, **_kwargs):
        if self.inline:
            func(*args)
        else:
            self.tasks.append((func, args))

    def run_all(self) -> None:
        while self.tasks:
            func, args = self.tasks.pop(0)
            func(*args)


@pytest.mark.qt
def test_the_last_lease_retires_the_worker_at_the_end_of_its_turn_unless_a_successor_leases_it(qt_app):
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime

    supervisor, lane = _Supervisor(), _Lane()
    first = lifetime.lease(supervisor, lane)
    lifetime.release(first)
    second = lifetime.lease(supervisor, lane)          # a recovery's replacement, in the same GUI turn
    qt_app.processEvents()
    assert supervisor.events == []                      # the worker stays with its new session
    lifetime.release(second)
    assert supervisor.events == []                      # not inside the turn: the settle is queued
    qt_app.processEvents()
    assert supervisor.events == ["stop"] and lifetime.describe()["retirements"] == 1


@pytest.mark.qt
def test_a_reload_hold_keeps_the_worker_across_turns_until_the_replacement_is_built(qt_app):
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime

    supervisor, lane = _Supervisor(), _Lane()
    old = lifetime.lease(supervisor, lane)
    hold = lifetime.hold_for_reload("custom_edit")      # the reload's stop, before the old owner retires
    lifetime.release(old)
    for _ in range(5):                                  # the destruction barrier's turns
        qt_app.processEvents()
    assert supervisor.events == []
    rebuilt = lifetime.lease(supervisor, lane)          # the replacement's owner configures on the worker
    lifetime.end_hold(hold)
    qt_app.processEvents()
    assert supervisor.events == []
    # A reload whose replacement has no owner on the worker (the Visualizer off, or in process) retires it.
    hold = lifetime.hold_for_reload("monitor_topology")
    lifetime.release(rebuilt)
    qt_app.processEvents()
    assert supervisor.events == []
    lifetime.end_hold(hold)
    qt_app.processEvents()
    assert supervisor.events == ["stop"]


@pytest.mark.qt
def test_a_retirement_task_that_finds_a_new_lease_leaves_the_worker_and_a_start_waits_for_one_in_flight(qt_app):
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime

    supervisor, lane = _Supervisor(), _Lane(inline=False)
    lifetime.release(lifetime.lease(supervisor, lane))
    qt_app.processEvents()                              # settled: the retirement is queued on the IO lane
    late = lifetime.lease(supervisor, lane)             # a link configures before the task runs
    lane.run_all()
    assert supervisor.events == [] and supervisor.running
    lifetime.release(late)
    # A retirement in flight: a link's start waits for it (one lock orders the two IO tasks).
    stopping, release_stop = threading.Event(), threading.Event()
    stop = supervisor.stop

    def slow_stop(worker_type, timeout=None):
        stopping.set()
        release_stop.wait(5.0)
        return stop(worker_type, timeout)

    supervisor.stop = slow_stop
    qt_app.processEvents()
    retire = threading.Thread(target=lane.run_all)
    retire.start()
    assert stopping.wait(5.0) and lifetime.retiring()
    started = threading.Event()

    def link_start():
        with lifetime.serialised_start():
            supervisor.start(WorkerType.VISUALIZER)
        started.set()

    threading.Thread(target=link_start).start()
    assert not started.wait(0.3)
    release_stop.set()
    retire.join(5.0)
    assert started.wait(5.0) and supervisor.events == ["stop", "start"]


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_stale_spawn_task_never_touches_a_later_links_worker(qt_app, monkeypatch, pre_fix):
    # Checkpoint audit 9, A9-L2: the first configure's deadline retired a link while its spawn task was still queued
    # (the IO pool has two threads); a later link has started a fresh worker meanwhile. The stale task stops nothing
    # and starts nothing. Negative control (the pre-5.7 task: stop, then start, unconditionally): the later link's
    # worker is stopped.
    from widgets.spotify_visualizer.engine_worker_link import ACTIVATION_KEYS, EngineWorkerLink

    class _Spawning(_Supervisor):
        def register_worker_factory(self, *_args) -> None:
            return None

    supervisor, lane = _Spawning(running=False), _Lane(inline=False)
    link = EngineWorkerLink(supervisor, on_lost=lambda *_args: None, thread_manager=lane)
    link.configure(runtime_generation=1, mode="spectrum", bar_count=32,
                   activation={key: None for key in ACTIVATION_KEYS}, on_configured=lambda _identity: None)
    assert len(lane.tasks) == 1 and link.busy                       # the spawn is queued; the configure waits for it
    link.retire()                                                   # the deadline: the link closes mid-spawn
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime

    lifetime_lease = lifetime.lease(supervisor, lane)               # a later owner's link, its worker started
    supervisor.start(WorkerType.VISUALIZER)
    supervisor.events.clear()
    if pre_fix:
        stale, _args = lane.tasks.pop(0)
        supervisor.stop(WorkerType.VISUALIZER, timeout=1.0)        # what the pre-5.7 task did first
        supervisor.start(WorkerType.VISUALIZER)
        assert supervisor.events == ["stop", "start"]
        lifetime.release(lifetime_lease)
        return
    lane.run_all()
    assert supervisor.events == [] and supervisor.running
    lifetime.release(lifetime_lease)


@pytest.mark.qt
def test_a_spawn_that_finishes_after_its_link_closed_retires_the_worker_it_started(qt_app):
    # A9-L2's other half: a spawn already inside ``start`` when its link closes leaves no idle worker behind: with no
    # lease, the task retires what it started (before: owned by the supervisor until its shutdown).
    from widgets.spotify_visualizer.engine_worker_link import ACTIVATION_KEYS, EngineWorkerLink

    link_ref: list = []

    class _ClosingDuringStart(_Supervisor):
        def register_worker_factory(self, *_args) -> None:
            return None

        def start(self, worker_type) -> bool:
            link_ref[0].close()                      # the deadline lands while the process starts
            return super().start(worker_type)

    supervisor, lane = _ClosingDuringStart(running=False), _Lane(inline=False)
    link = EngineWorkerLink(supervisor, on_lost=lambda *_args: None, thread_manager=lane)
    link_ref.append(link)
    link.configure(runtime_generation=1, mode="spectrum", bar_count=32,
                   activation={key: None for key in ACTIVATION_KEYS}, on_configured=lambda _identity: None)
    lane.run_all()
    assert supervisor.events == ["start", "stop"] and not supervisor.running


# --------------------------------------------------------------------------------------------- the engine's reload


@pytest.mark.parametrize("admitted", (True, False))
def test_a_display_reload_holds_the_worker_and_settings_or_the_exit_never_do(admitted):
    import dataclasses
    from types import SimpleNamespace

    from core.diagnostics import experiment_flags
    from engine.engine_lifecycle import end_engine_worker_reload_hold, hold_engine_worker_for_reload
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime

    flags = experiment_flags.active_experiment_flags()
    experiment_flags.override_active_flags_for_testing(dataclasses.replace(flags, visualizer_engine_worker=admitted))
    try:
        engine = SimpleNamespace(_engine_worker_reload_hold=None)
        hold_engine_worker_for_reload(engine, "settings")
        assert engine._engine_worker_reload_hold is None and lifetime.describe()["holds"] == []
        hold_engine_worker_for_reload(engine, "custom_edit")
        if not admitted:
            assert engine._engine_worker_reload_hold is None
            return
        assert lifetime.describe()["holds"] == ["custom_edit"]
        hold_engine_worker_for_reload(engine, "monitor_topology")      # a newer reload replaces the older hold
        assert lifetime.describe()["holds"] == ["monitor_topology"]
        end_engine_worker_reload_hold(engine)
        end_engine_worker_reload_hold(engine)                          # idempotent
        assert lifetime.describe()["holds"] == [] and engine._engine_worker_reload_hold is None
    finally:
        experiment_flags.override_active_flags_for_testing(flags)


@pytest.mark.qt
@pytest.mark.parametrize("configure", ("synchronous", "later_turn"))
def test_a_custom_reload_hands_the_running_worker_to_the_replacements_owner(qt_app, pcm, monkeypatch, tmp_path,
                                                                            configure):
    # Checkpoint audit 10, A10-L5: the reload hold, end to end through the engine. A CUSTOM commit runs the real
    # ``engine_lifecycle.stop`` (the hold), the old generation's teardown (its owner retires, its lease goes), the
    # strict destruction barrier (later turns) and ``_construct_and_start_replacement_runtime``, whose real
    # ``_initialize_display`` wires the supervisor and builds the replacement; the display manager is a stand-in whose
    # ``initialize_displays`` admits the REAL owner through the host binding (the owner rig, an unshown runtime), as
    # the real manager does, synchronously. The rebuilt owner adopts the held worker: no stop, no start, one lease once
    # the turn settled. Negative control (the owner configured on a later turn, the regression A10-L5 guards): the
    # hold ends with no lease, the worker is retired, and the late configure has to start a fresh one.
    import dataclasses
    import uuid
    import weakref

    from PySide6.QtCore import QCoreApplication, QEvent

    from core.diagnostics import experiment_flags
    from core.settings import SettingsManager
    from engine import engine_handlers
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    from tests.test_settings_roundtrip_retired_generations import _cyclic_display_manager_class
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime

    class _Worker(_InProcessSupervisor):
        """The engine worker in this process; whether it runs, its start and its stop recorded."""

        def __init__(self) -> None:
            super().__init__()
            self.running = True
            self.events: list[str] = []
            self.stopped = threading.Event()

        def is_running(self, _worker_type) -> bool:
            return self.running

        def start(self, _worker_type) -> bool:
            self.events.append("start")
            self.running = True
            return True

        def stop(self, _worker_type, timeout=None) -> bool:
            self.events.append("stop")
            self.running = False
            self.stopped.set()
            return True

        def get_visualizer_worker_usage_snapshot(self) -> dict:
            return {"visualizer_worker_pid": 4242 if self.running else None}

    rigs: list = []
    pending: list = []

    class _Manager(_cyclic_display_manager_class()):
        """The display manager stand-in: its one display's Visualizer owner is the owner rig's real one."""

        build_now = True

        def __init__(self, *, runtime_generation, **kwargs):
            super().__init__(runtime_generation=runtime_generation, **kwargs)
            self._supervisor = None
            self._rig = None

        def set_process_supervisor(self, supervisor) -> None:
            self._supervisor = supervisor

        def initialize_displays(self) -> int:
            self._rig = gate.OwnerRig("spectrum", worker=True, supervisor=self._supervisor, cadence="thread")
            rigs.append(self._rig)
            if type(self).build_now:
                self._rig.build()                      # the owner admitted (and configured) inside, as in production
            else:
                pending.append(self._rig)              # the regression: configured on a later turn
            return 1

        def cleanup(self) -> None:
            if self._rig is not None and self._rig.owner is not None:
                self._rig.owner.retire()               # the display's owner retires with its generation

    worker = _Worker()
    engine = ScreensaverEngine()
    engine.settings_manager = SettingsManager(organization="Test", application=f"EngineWorkerReload_{uuid.uuid4().hex}",
                                              storage_base_dir=tmp_path)
    engine._process_supervisor = worker

    def _start(*, show_first_image=True):
        engine._transition_state(EngineState.RUNNING)
        return True

    monkeypatch.setattr("engine.screensaver_engine.DisplayManager", _Manager)
    monkeypatch.setattr(engine, "_initialize_image_sources", lambda: True)
    monkeypatch.setattr(engine, "_start_rss_background_refresh_if_needed", lambda: None)
    monkeypatch.setattr(engine, "_setup_rotation_timer", lambda: None)
    monkeypatch.setattr(engine, "_arm_replacement_watchdog", lambda label=None: None)
    monkeypatch.setattr(engine, "start", _start)
    monkeypatch.setattr(engine_handlers, "log_lifecycle_resource_snapshot", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_handlers, "suppress_runtime_pointer_input", lambda *_a, **_k: None)
    monkeypatch.setattr("core.windows.reddit_helper_runtime.clear_session_ticket", lambda **_k: True)
    flags = experiment_flags.active_experiment_flags()
    experiment_flags.override_active_flags_for_testing(dataclasses.replace(flags, visualizer_engine_worker=True))
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            assert engine._initialize_display()        # the first generation, its owner on the running worker
            _start()
            old = weakref.ref(engine.display_manager)          # never kept alive by the test (the barrier's watch)
            assert rigs[0].owner._worker is not None and lifetime.describe()["leases"] == 1
            _Manager.build_now = configure == "synchronous"
            engine_handlers.on_custom_layout_reload_requested(engine, "custom_layout_commit",
                                                              old()._runtime_generation, id(old()))

            def rebuilt() -> bool:
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)    # the barrier's destruction
                return (len(rigs) == 2 and engine._engine_worker_reload_hold is None
                        and engine._get_state() == EngineState.RUNNING)

            gate._event_loop_for(qt_app, 20.0, until=rebuilt)
            assert rebuilt(), (len(rigs), engine._engine_worker_reload_hold, engine._get_state())
            assert engine.display_manager is not None and engine.display_manager is not old()
            gate._event_loop_for(qt_app, 0.3)             # the turn settles (the lifetime's queued settle runs)
            if configure == "synchronous":
                assert worker.events == [] and worker.running
                assert lifetime.describe() == {"leases": 1, "holds": [], "retiring": False, "retirements": 0}
                assert rigs[1].owner._worker is not None and rigs[1].owner._worker.configured
                return
            assert worker.stopped.wait(10.0) and worker.events == ["stop"]
            late = pending.pop()
            late.build()                                # the late configure finds no worker and starts one
            assert worker.events == ["stop", "start"] and lifetime.describe()["retirements"] == 1
    finally:
        experiment_flags.override_active_flags_for_testing(flags)
        for rig in reversed(rigs):
            rig.close()
        worker.close()
        engine.display_manager = None
        gate_installed = engine._refresh_transition_gate       # the replacement generation's admission gate
        if gate_installed is not None:
            from core.threading.refresh_transition_gate import install_gate

            gate_installed.close()
            install_gate(None)


def test_the_engine_wires_the_supervisor_before_the_displays_admit_the_visualizer():
    # 5.7 (4): the Visualizer owner is admitted synchronously inside ``initialize_displays`` and reads the supervisor at
    # its configure; wired after it, the first owner never had one (on the worker path it ran in process).
    import ast
    import inspect
    import textwrap

    from engine.screensaver_engine import ScreensaverEngine

    tree = ast.parse(textwrap.dedent(inspect.getsource(ScreensaverEngine._initialize_display)))
    lines: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in (
                "set_process_supervisor", "initialize_displays"):
            lines[node.func.attr] = min(lines.get(node.func.attr, node.lineno), node.lineno)
    assert set(lines) == {"set_process_supervisor", "initialize_displays"}
    assert lines["set_process_supervisor"] < lines["initialize_displays"]


# ----------------------------------------------------------------------------------- the owner (A9-L1, real worker)


@pytest.mark.qt
@pytest.mark.parametrize("fenced", (True, False))
def test_the_first_configure_deadline_is_inert_on_a_half_retired_owner(qt_app, pcm, monkeypatch, fenced):
    # Checkpoint audit 9, A9-L1: the first configure is unanswered and the owner's retire fails its logical join (it
    # returns before ``_retired``, its routes detached). The deadline must not fall back in process and start a logical
    # runtime on that half-retired owner. Negative control (the pre-fix fence, without ``_retiring``): it does.
    from tests.test_visualizer_owner_engine_worker_liveness import _HungSupervisor
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 300)
    monkeypatch.setattr(gate.OwnerRig, "settle", lambda self: None)
    stand_in = _HungSupervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            link = owner._worker
            assert link is not None and not link.configured
            controller = owner.controller
            monkeypatch.setattr(controller, "stop_logical_runtime", lambda: False)
            assert owner.retire() is False and not owner.is_retired
            # Since checkpoint audit 10 (A10-L1) the link is retired before the join, so the failed join leaves none.
            assert owner._worker is None and link._closed
            if not fenced:
                owner._retiring = False                       # what the pre-fix deadline saw: no fence, the link set
                owner._worker = link
            gate._event_loop_for(qt_app, 1.0)
        if fenced:
            assert owner._worker is None and controller.logical_runtime is None
        else:
            assert owner._worker is None and controller.logical_runtime is not None
    finally:
        monkeypatch.undo()
        runtime = rig.owner.controller.logical_runtime if rig.owner is not None else None
        if runtime is not None:
            rig.owner.controller.stop_logical_runtime()
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("join", ("fails", "raises"))
def test_a_retire_whose_logical_join_fails_still_stops_the_session_and_releases_its_lease(qt_app, pcm, monkeypatch,
                                                                                           join):
    # Checkpoint audit 10, A10-L1: ``retire()`` returned (join failed) or propagated (join raised) before it retired
    # the link, so the session's VIS_STOP was never sent and its lease kept the worker, and its session's cadence and
    # capture, until the supervisor's shutdown. The link is retired before the join now (its retire never waits).
    # Negative control: the pre-fix order (the link retired after the join) leaves the lease held and no VIS_STOP.
    from core.process.types import MessageType
    from tests.test_visualizer_owner_engine_worker_liveness import _HungSupervisor
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 60_000)   # never fires in this test
    monkeypatch.setattr(gate.OwnerRig, "settle", lambda self: None)
    stand_in = _HungSupervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            link = owner._worker
            assert link is not None and lifetime.describe()["leases"] == 1

            def failing_join():
                if join == "raises":
                    raise RuntimeError("injected join failure")
                return False

            monkeypatch.setattr(owner.controller, "stop_logical_runtime", failing_join)
            if join == "raises":
                with pytest.raises(RuntimeError, match="injected join failure"):
                    owner.retire()
            else:
                assert owner.retire() is False
        assert not owner.is_retired and owner._worker is None and link._closed
        assert lifetime.describe()["leases"] == 0
        stops = [payload for message, payload in stand_in.sent if message == MessageType.VIS_STOP]
        assert stops and stops[-1].get("mapping") == link.mapping_name
    finally:
        monkeypatch.undo()
        rig.close()
        stand_in.close()


@pytest.mark.parametrize("raising", ("mailbox", "events"))
def test_a_link_close_that_raises_still_releases_its_lease(monkeypatch, raising):
    # A10-L1: ``close()`` released the lease last, after steps that can raise (the mailbox's ``SharedMemory.close()``
    # raises ``BufferError`` while a view is exported); ``_closed`` is already set then, so no retry released it.
    # Negative control: the pre-fix order leaves ``leases == 1``.
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime
    from widgets.spotify_visualizer.engine_worker_link import ACTIVATION_KEYS, EngineWorkerLink

    class _Spawning(_Supervisor):
        def register_worker_factory(self, *_args) -> None:
            return None

    supervisor, lane = _Spawning(running=False), _Lane(inline=False)
    link = EngineWorkerLink(supervisor, on_lost=lambda *_args: None, thread_manager=lane)
    link.configure(runtime_generation=1, mode="spectrum", bar_count=32,
                   activation={key: None for key in ACTIVATION_KEYS}, on_configured=lambda _identity: None)
    assert lifetime.describe()["leases"] == 1
    mailbox = link.mailbox

    def boom(*_args, **_kwargs):
        raise BufferError("cannot close exported pointers exist")

    if raising == "mailbox":
        monkeypatch.setattr(mailbox, "close", boom)
    else:
        monkeypatch.setattr(link._events, "deleteLater", boom)
    try:
        with pytest.raises(BufferError):
            link.close()
        assert lifetime.describe()["leases"] == 0
        link.close()                                                 # idempotent: nothing left to release
        assert lifetime.describe()["leases"] == 0
    finally:
        monkeypatch.undo()
        mailbox.close()
        lane.tasks.clear()


@pytest.mark.qt
def test_the_worker_process_is_spawned_by_its_first_owner_and_retired_with_its_last(qt_app, pcm):
    # 5.7 (1): no worker process before the first owner configures on the worker path; one while it runs; none (the
    # process reaped) once the owner retires and nothing holds it. Recorded PCM, no device, an unshown runtime.
    import psutil

    from core.visualizer_engine.engine_worker import visualizer_worker_main
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import engine_worker_lifetime as lifetime

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread")
    try:
        assert not supervisor.is_running(WorkerType.VISUALIZER)
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            gate._event_loop_for(qt_app, 1.0)
            pid = supervisor.get_visualizer_worker_usage_snapshot()["visualizer_worker_pid"]
            assert pid is not None and psutil.pid_exists(pid) and lifetime.describe()["leases"] == 1
            presented = len(rig.published)
            assert presented > 10
            assert owner.retire()
            gate._event_loop_for(qt_app, 15.0, until=lambda: not supervisor.is_running(WorkerType.VISUALIZER)
                                 and not lifetime.retiring())
        assert not supervisor.is_running(WorkerType.VISUALIZER) and lifetime.describe()["retirements"] == 1
        assert supervisor.get_visualizer_worker_usage_snapshot()["visualizer_worker_pid"] is None
        assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    finally:
        rig.close()
        supervisor.shutdown()

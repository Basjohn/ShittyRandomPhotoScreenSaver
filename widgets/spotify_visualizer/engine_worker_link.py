"""The production Visualizer owner on the engine worker, main-process side (native core P2b, work order 5 slices 5.2 and
5.5).

The default path (``core.diagnostics.experiment_flags.visualizer_engine_worker_admitted``, read once per owner
construction; ``--viz-in-process`` runs in process; Linux's default is source-level only and has never run:
``Linux_Plan.md``). In process, nothing here is imported and no worker process exists. On the worker path, the owner
(``quick_display_visualizer_owner.QuickDisplayVisualizerOwner``) keeps no beat engine and runs no tick: one
``EngineWorkerLink`` per session sends the ``logical_edges`` control edges to the ``WorkerType.VISUALIZER`` process
(``core.visualizer_engine.engine_worker``: ``VIS_CONFIGURE`` with the host binding's own resolved activation and
``presentation_kwargs``, ``VIS_START``, Media's ``VIS_SET_PLAYING``, ``VIS_SET_DISPLAY_POWER``, ``VIS_SET_VIEW``,
``VIS_SET_MODE``, ``VIS_STOP``) and owns the reader side of the session's frame mapping (``PacketMailbox(role="reader")``:
the main process creates, holds and unlinks it). The worker paces its own ticks (slice 5.1) and in production opens the
loopback device itself (slice 5.3). Frames reach presentation through the owner's existing path: the worker's wake byte
per publish -> ``listen_for_wakes`` (one daemon thread blocked on the pipe, never a poll) -> the owner's
``QuickVisualizerPublicationWake.request`` (a queued Qt signal: it never blocks, and coalesces) -> ``sync_present`` on
the GUI thread -> ``QuickVisualizerPresentationSync.sync_latest`` takes the newest whole frame from the mapping.

**Control edges never wait (slice 5.5, checkpoint audit 7 A7-M4).** The GUI thread sends an edge and continues: every
request registers its correlation with the supervisor's response listener (``register_response_callback``: one
blocking listener per worker, no poll, no per-request thread), and its reply comes back as a queued Qt signal, applied
on the GUI thread (``on_reply``); an edge that needs a reply's identity (the configure's engine identity, a hidden
activation's committed identity) proceeds on that event. A request that could not be sent, a failed reply, or a
correlation the supervisor cancels (the worker restarted or died: the listener hands back ``None``) is a failure,
always delivered as an event, never inside the caller (no re-entrant failure path, A7-L2). The first configure never
waits for the worker's spawn: a worker that is not running is (re)started on a ``ThreadManager`` IO task (the supervisor
retires what a dead one left behind, its stale response listener included, slice 5.7), the requests sent meanwhile wait
in the link's outbox, in order, and leave when the spawn reports back (an event). The link is the role's one starter;
the supervisor's heartbeat only retires a dead or hung worker, and the worker process lives while a link holds a lease
on it (``engine_worker_lifetime``, slice 5.7). The framed view (``VIS_SET_VIEW``) is latest-wins state: at
most one in flight, writes inside one GUI turn coalesce into one send (a queued flush), and the newest view leaves when
the previous one is answered.

**Liveness.** A dead worker is seen by an event: the session's wake pipe ends (the worker held the only writer end), and
the supervisor cancels the outstanding correlations when it retires the process. A hung-but-alive worker (no reply, the
process alive) is the supervisor's heartbeat's: missed heartbeats retire the worker (bounded: ``HealthStatus
.MISSED_HEARTBEAT_THRESHOLD`` intervals, then the stop's graceful bound and termination; since slice 5.7 never a restart,
which the owner's reconfigure makes through its next link), which ends the pipe and cancels the correlations, so the
owner's failure path runs; nothing on the GUI thread waits meanwhile.

What the link owns, once:

- **The label namespace counter** (``next_label_namespace``): one process-wide counter, owned by this module for the
  app's life, never repeated across sessions or restarted workers; every ``VIS_CONFIGURE`` takes a fresh value
  (Extruded Bubble's drift-family revisions are a renderer cache identity: ``engine_worker``'s ``label_namespace``).
- **The session's end:** the main process closes its copy of the wake pipe's writer end once the worker holds its own
  (the configure's reply), so the pipe ends exactly when the session does (closed after a failure, or its process
  died); the listener reports that once, through a queued signal, to the owner's GUI thread (``on_lost``). A capture
  device that fails to open is not the session's end (A7-L4): the session keeps running, reports it in later replies
  (``capture_failed``) and retries the device on the next edge that opens capture. Nor is a device that stops
  delivering while Media plays (slice 5.3): the session reopens it once on the current default output and reports its
  reopens in later replies; the link logs changed device state and its detached STOP callback logs the final state.
  The worker writes its own diagnostic file, whose path is recorded in the main log.
- **The run's failure record** (``worker_disabled_for_run``): after a session failed twice for an owner (the reconfigure
  included), or failed once more after the run's ``MAX_RECOVERIES_PER_RUN`` recoveries (``claim_recovery_for_run``,
  A11-M1), the engine worker stays off for the rest of the run, and every later owner runs in process.

Tests never open a device: ``recorded_capture_for_testing`` (a test-only control) adds a recorded-PCM source and its
cadence to every configure the link sends, and the session refuses the device for its life. ``stop`` and
``feed_for_testing`` still wait for their reply (tests and tools); the owner retires a link with ``retire`` (no wait).
"""
from __future__ import annotations

import contextlib
import itertools
import threading
import uuid
import weakref
from typing import Any, Callable, Iterator, Mapping

from PySide6.QtCore import QObject, Qt, Signal

from core.logging.logger import get_logger
from core.process.types import VISUALIZER_STOP_REPORT_PREFIX

logger = get_logger(__name__)
# Chronological process evidence must remain in the main log under --viz/--life.
diagnostic_logger = get_logger('core.process.visualizer_diagnostics')

#: ``stop`` / ``feed_for_testing``'s bounded wait (tests and tools only: the owner never waits on the worker).
EDGE_TIMEOUT_MS = 30_000
#: The stop at the end of a test or tool run (the worker closes the session even when its finish raises, A6-L7).
STOP_TIMEOUT_MS = 10_000

#: The activation inputs the owner sends (the host binding's own; checkpoint audit 6, A6-L4).
ACTIVATION_KEYS = ("settings_model", "resolved_activation", "technical_cache", "logical_kwargs", "presentation_kwargs")


class EngineWorkerFailure(RuntimeError):
    """A control edge found no healthy session: not sent, no reply, a failed reply, or the session closed."""

    def __init__(self, message: str, *, session_closed: bool = False) -> None:
        super().__init__(message)
        self.session_closed = bool(session_closed)


# ------------------------------------------------------------------------------------------- process-wide state

_namespace_lock = threading.Lock()
_namespaces = itertools.count(1)


def next_label_namespace() -> int:
    """A fresh label namespace (>= 1, never repeated in this process): the counter's one owner, for the app's life."""
    with _namespace_lock:
        value = next(_namespaces)
    if value >= 1 << 30:
        raise RuntimeError("the engine worker's label namespaces are exhausted")
    return value


#: The engine-worker recoveries one run allows (checkpoint audit 11, A11-M1). A recovery whose reveal completes starts
#: the owner's two strikes again (A10-L4), so without a bound a failure that recurs some time after every reveal (a
#: mode that fails once its history fills, a fault at a fixed point in a song, a device path that fails closed at each
#: reopen) would fade out, rebuild a session and fade in for the whole run. A count, not a span: a failure minutes after
#: each reveal outlives any "ran long enough" threshold, and a count needs no timer. Three: an isolated failure (a
#: device change, a crash) still recovers on the worker a few times in a run; past that the worker path has shown it is
#: not healthy for this run and the in-process path (the known-good fallback) takes over.
MAX_RECOVERIES_PER_RUN = 3

_run_lock = threading.Lock()
_run_disabled_reason: str | None = None
_run_recoveries = 0


def worker_disabled_for_run() -> bool:
    """Whether a second failure turned the engine worker off for the rest of the run."""
    with _run_lock:
        return _run_disabled_reason is not None


def claim_recovery_for_run() -> bool:
    """Take one of the run's ``MAX_RECOVERIES_PER_RUN`` recoveries; False once they are spent (the caller then leaves
    the worker for the run)."""
    global _run_recoveries
    with _run_lock:
        if _run_recoveries >= MAX_RECOVERIES_PER_RUN:
            return False
        _run_recoveries += 1
        return True


def disable_worker_for_run(reason: str) -> bool:
    """Turn the engine worker off for the rest of the run (idempotent); True the first time (the caller logs it)."""
    global _run_disabled_reason
    with _run_lock:
        if _run_disabled_reason is not None:
            return False
        _run_disabled_reason = str(reason)
        return True


def reset_run_state_for_testing() -> None:
    """Tests only: forget the run's failure record and its recoveries."""
    global _run_disabled_reason, _run_recoveries
    with _run_lock:
        _run_disabled_reason = None
        _run_recoveries = 0
    from widgets.spotify_visualizer import engine_worker_lifetime

    engine_worker_lifetime.reset_for_testing()


_test_session_overrides: dict | None = None


@contextlib.contextmanager
def recorded_capture_for_testing(**overrides: Any) -> Iterator[None]:
    """Tests only: every configure the link sends while this is entered carries ``overrides`` (a recorded-PCM source:
    ``pcm`` / ``pcm_rate`` with the worker's own cadence, or ``cadence="input"`` with ``order`` / ``seed`` for the
    identity gate, fed through ``EngineWorkerLink.feed_for_testing``). The session then refuses the device for its
    life (``EngineSession``); production never enters this. ``payload="native"``: the session writes its mode's native
    schema instead of the tagged codec, which this process's codec reader refuses at the first slot head (native core
    N2.3: the refusal path end to end with a real worker)."""
    global _test_session_overrides
    allowed = {"pcm", "pcm_rate", "cadence", "order", "seed", "interval_s", "payload"}
    unknown = set(overrides) - allowed
    if unknown:
        raise ValueError(f"not a recorded-capture override: {sorted(unknown)}")
    previous, _test_session_overrides = _test_session_overrides, dict(overrides)
    try:
        yield
    finally:
        _test_session_overrides = previous


# ----------------------------------------------------------------------------------------------------- the link

#: A request the supervisor refused to send (its reply, delivered as an event like any other).
_NOT_SENT = "not sent"


class _LinkEvents(QObject):
    """Everything that reaches a link from another thread, queued onto its (GUI) thread: a reply (or a cancelled
    correlation), the session's end (the wake listener), the worker's spawn (an IO task), and the view flush (one per GUI
    turn). It reaches its link weakly and is disarmed when the link closes, so a late delivery is a no-op."""

    replied = Signal(object, object, object)  # token, correlation, the WorkerResponse (None: cancelled; _NOT_SENT)
    ended = Signal(str)
    spawned = Signal(str)                     # "" started, else why not
    view = Signal()

    def __init__(self, link: "EngineWorkerLink") -> None:
        super().__init__()
        self._link = weakref.ref(link)
        self._armed = True
        self.replied.connect(self._on_replied, Qt.ConnectionType.QueuedConnection)
        self.ended.connect(self._on_ended, Qt.ConnectionType.QueuedConnection)
        self.spawned.connect(self._on_spawned, Qt.ConnectionType.QueuedConnection)
        self.view.connect(self._on_view, Qt.ConnectionType.QueuedConnection)

    def _target(self) -> "EngineWorkerLink | None":
        return self._link() if self._armed else None

    def _on_replied(self, token: Any, correlation: Any, response: Any) -> None:
        link = self._target()
        if link is not None:
            link._deliver_reply(token, correlation, response)

    def _on_ended(self, reason: str) -> None:
        link = self._target()
        if link is not None:
            link._deliver_end(reason)

    def _on_spawned(self, error: str) -> None:
        link = self._target()
        if link is not None:
            link._deliver_spawned(error)

    def _on_view(self) -> None:
        link = self._target()
        if link is not None:
            link._flush_view()

    def disarm(self) -> None:
        self._armed = False


class EngineWorkerLink:
    """One engine-worker session seen from the main process: its control edges (sent, never awaited) and its frame
    reader. Every method runs on the owner's (GUI) thread; replies and failures arrive there as events."""

    def __init__(self, supervisor: Any, *, on_lost: Callable[["EngineWorkerLink", str], None],
                 thread_manager: Any = None) -> None:
        if supervisor is None:
            raise EngineWorkerFailure("no process supervisor")
        self._supervisor = supervisor
        self._thread_manager = thread_manager
        self._on_lost = on_lost
        self._mailbox: Any = None
        # The session's wake pipe as the main side holds it (``wake_channel``): its own writer end, and on POSIX the
        # pipe's name, until the session answers the configure.
        self._wake_channel: Any = None
        self._closed = False
        self._stopping = False                    # an ordered stop: the session's end that follows is not a loss
        self._lost_reported = False
        self.label_namespace = 0
        self.mapping_name: str | None = None
        self.capacity_failure_report: dict | None = None
        self.payload_failure_report: dict | None = None   # the reader refused a slot at its head (N2.3)
        self._capacity_candidates: tuple[str, ...] = ()
        self.configured = False                   # the configure's reply arrived
        self.bar_count: int | None = None         # the session's bar count, from its configure and commit replies
        self.capture_failed = False               # the newest reply said the session's device did not open (A7-L4)
        self.capture_reopens = 0                  # the session's reopens of a silent device, and those that delivered
        self.capture_resumed = 0                  # again (slice 5.3), as the newest reply carried them
        self._events = _LinkEvents(self)
        self._emit_lock = threading.Lock()        # a late emit from another thread never races ``close``
        self._tokens = itertools.count(1)
        self._pending: dict[int, tuple] = {}      # token -> (message, payload, correlation, on_reply, on_failed)
        self._outbox: list | None = None          # requests waiting for the worker's spawn, in order
        self._respawned = False                   # the unanswered configure went out again once (a restarted worker)
        self._view_source: Callable[[], tuple] | None = None
        self._presentation_sent: dict = {}         # the presentation inputs the session holds (sent so far)
        self._view_sent: Any = None
        self._view_in_flight = False
        self._view_scheduled = False
        self._lease: int | None = None            # the session's lease on the worker process (slice 5.7)

    @property
    def mailbox(self) -> Any:
        """The reader side of the session's frame mapping (the owner's controller's logical mailbox)."""
        return self._mailbox

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def busy(self) -> bool:
        """Whether a request is unanswered or waiting for the spawn (rigs settle on it; the owner never waits)."""
        return bool(self._pending) or self._outbox is not None or self._view_scheduled

    # -------------------------------------------------------------------------------------------- the worker

    def _worker_type(self) -> Any:
        from core.process.types import WorkerType

        return WorkerType.VISUALIZER

    def _emit(self, signal_name: str, *args: Any) -> None:
        """Queue an event onto the link's thread from any thread (dropped once the link closed)."""
        with self._emit_lock:
            if self._closed:
                return
            getattr(self._events, signal_name).emit(*args)

    def _ensure_worker(self) -> bool:
        """True when the worker runs (requests go out now); otherwise its (re)start is submitted to an IO task and the
        requests wait in the outbox until it reports back."""
        from core.visualizer_engine.engine_worker import visualizer_worker_main
        from core.logging.logger import worker_logging_bootstrap
        from functools import partial

        from widgets.spotify_visualizer import engine_worker_lifetime

        supervisor, worker_type = self._supervisor, self._worker_type()
        diagnostics = worker_logging_bootstrap()
        supervisor.register_worker_factory(worker_type, partial(visualizer_worker_main, diagnostics=diagnostics))
        if diagnostics.log_directory is not None:
            from pathlib import Path
            directory = Path(diagnostics.log_directory)
            diagnostic_logger.info('[ENGINE_WORKER] Child diagnostics: log=%s native_fault_directory=%s '
                        'native_fault_capture=%s perf=%s viz=%s', directory/'worker_visualizer.log',
                        directory/'worker_visualizer', diagnostics.native_fault_capture,
                        diagnostics.profile.perf, diagnostics.profile.viz)
        # A worker being retired (its last lease went before this link's) is not reused: a fresh one is started after it.
        if supervisor.is_running(worker_type) and not engine_worker_lifetime.retiring():
            return True
        self._outbox = []
        self._spawn()
        return False

    def _spawn(self) -> None:
        """(Re)start the worker off this thread; the outbox leaves when it reports back (an event). The link is the one
        starter of its role (slice 5.7): the supervisor's heartbeat only retires a dead or hung worker, a start retires
        what a dead one left behind (its response listener included) in the supervisor itself, and the start waits for
        a retirement in flight (``engine_worker_lifetime``), so it never stops or reuses a worker on its way out.

        The task belongs to this link (checkpoint audit 9, A9-L2): it stops nothing, starts nothing once its link has
        closed (the first configure's deadline retired it mid-spawn), and a worker it started for a link that closed
        meanwhile is retired at once when no other link leased it, instead of idling until the supervisor's shutdown."""
        from widgets.spotify_visualizer import engine_worker_lifetime

        supervisor, worker_type = self._supervisor, self._worker_type()

        def spawn() -> None:
            error = ""
            try:
                with engine_worker_lifetime.serialised_start():
                    started = False if self._closed else supervisor.start(worker_type)
                if self._closed:
                    engine_worker_lifetime.retire_if_unused(supervisor)
                    return
                if not started:
                    error = "the engine worker process did not start"
            except Exception as exc:  # reported to the owner as a failure, never lost on the IO thread
                error = f"the engine worker process did not start: {type(exc).__name__}: {exc}"
            self._emit("spawned", error)

        manager = self._thread_manager
        if manager is None:
            spawn()                                   # no IO lane (a bare rig): the spawn's report is still an event
        else:
            manager.submit_io_task(spawn, category="engine_worker_spawn")

    def _respawn_unconfigured(self) -> None:
        """The supervisor retired the worker before the configure was answered (the process the configure was queued
        to had died, and the supervisor's heartbeat retired it: the session never existed). Once per link, every
        unanswered request goes out again, in order, to a (re)started worker; a second retirement is a failure."""
        self._respawned = True
        pending, self._pending = self._pending, {}
        for message, _payload, correlation, _on_reply, _on_failed in pending.values():
            if correlation:
                self._supervisor.abandon_response(self._worker_type(), correlation, reason="respawned")
        self._outbox = [(token, message, payload, on_reply, on_failed)
                        for token, (message, payload, _correlation, on_reply, on_failed) in sorted(pending.items())]
        logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] The engine worker retired before the configure was answered; "
                       "sending it again to a restarted worker")
        self._spawn()

    def _deliver_spawned(self, error: str) -> None:
        outbox, self._outbox = self._outbox, None
        if self._closed or outbox is None:
            return
        if error:
            for token, message, payload, _on_reply, on_failed in outbox:
                self._pending[token] = (message, payload, "", None, on_failed)
                self._deliver_reply(token, "", _NOT_SENT, reason=error)
            return
        for token, message, payload, on_reply, on_failed in outbox:
            self._dispatch(token, message, payload, on_reply, on_failed)

    def _send(self, message: Any, payload: Mapping[str, Any], *, on_reply: Callable[[dict], None] | None = None,
              on_failed: Callable[[EngineWorkerFailure], None] | None = None) -> int:
        """Send one request and return at once; its reply runs ``on_reply(payload)`` on this thread, a failure
        ``on_failed(failure)`` (default: the session is lost, ``on_lost``), both as events."""
        if self._closed:
            raise EngineWorkerFailure("the link is closed")
        token = next(self._tokens)
        if self._outbox is not None:
            self._outbox.append((token, message, dict(payload), on_reply, on_failed))
        else:
            self._dispatch(token, message, dict(payload), on_reply, on_failed)
        return token

    def _dispatch(self, token: int, message: Any, payload: dict, on_reply: Any, on_failed: Any) -> None:
        supervisor, worker_type = self._supervisor, self._worker_type()
        correlation = uuid.uuid4().hex
        self._pending[token] = (message, payload, correlation, on_reply, on_failed)

        def replied(response: Any, _token: int = token, _correlation: str = correlation) -> None:   # listener thread
            self._emit("replied", _token, _correlation, response)

        sent = False
        try:
            if supervisor.register_response_callback(worker_type, correlation, replied):
                sent = supervisor.send_message(worker_type, message, payload, correlation_id=correlation) is not None
        except Exception as exc:
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] %s could not be sent: %s", message.value, exc)
        if not sent:
            supervisor.abandon_response(worker_type, correlation, reason="not_sent")
            self._emit("replied", token, correlation, _NOT_SENT)

    def _deliver_reply(self, token: Any, correlation: Any, response: Any, *, reason: str | None = None) -> None:
        """A reply (or cancellation) for ``token``, matched by its correlation (A8-L4): a late event for a correlation
        the link abandoned (``_respawn_unconfigured`` re-dispatched the token under a new one) is dropped, never taken
        as the new request's answer."""
        entry = self._pending.get(token)
        if entry is None or self._closed or entry[2] != correlation:
            return
        if response is None and not self.configured and not self._respawned:
            self._respawn_unconfigured()
            return
        del self._pending[token]
        message, _payload, _correlation, on_reply, on_failed = entry
        if response is None or isinstance(response, str) or not response.success:
            if response is None:
                failure = EngineWorkerFailure(f"{message.value}: the engine worker retired before replying")
            elif isinstance(response, str):
                failure = EngineWorkerFailure(f"{message.value}: {reason or 'the request could not be sent'}")
            else:
                failure = EngineWorkerFailure(f"{message.value}: {response.error}",
                                              session_closed=bool((response.payload or {}).get("session_closed")))
            (on_failed or self._report_lost)(failure)
            return
        reply = response.payload or {}
        if "bar_count" in reply:
            self.bar_count = int(reply["bar_count"])     # the session's bar count (its mode's technical config)
        self._note_device_state_in(reply)
        if on_reply is not None:
            on_reply(reply)

    def _note_device_state_in(self, reply: Mapping[str, Any]) -> None:
        """Log the device state wherever the reply carries it (checkpoint audit 11, A11-L5): an edge's reply at its top
        level, ``VIS_STOP``'s report under ``report["engine"]`` (``EngineSession.finish``). A retirement's final
        report uses the detached logging callback instead, after the GUI link may have been destroyed."""
        if "capture_failed" in reply:
            self._note_device_report(reply)
            return
        report = reply.get("report")
        engine = report.get("engine") if isinstance(report, Mapping) else None
        if isinstance(engine, Mapping) and "capture_failed" in engine:
            self._note_device_report(engine)

    def _note_device_report(self, reply: Mapping[str, Any]) -> None:
        """The session's device state as a reply carries it (``EngineSession.device_report``, work order 5 slice 5.3),
        logged here when it changed: the worker process's own log lines never reach the main log, so this is where a
        device that did not open, the session's reopen of a device that stopped delivering, and the device delivering
        again become visible (at the reply of the next edge after them, or the detached final STOP report).
        The owner does nothing else with it: a device problem is never the
        session's end (as in process, the Visualizer shows the engine's idle frames until audio comes back)."""
        failed = bool(reply["capture_failed"])
        reopens = int(reply.get("capture_reopens", self.capture_reopens))
        resumed = int(reply.get("capture_resumed", self.capture_resumed))
        if reopens != self.capture_reopens or resumed != self.capture_resumed:
            logger.info("[SPOTIFY_VIS][ENGINE_WORKER] The engine worker reopened its loopback device after it stopped "
                        "delivering while playing: %d reopen(s) this session, %d delivering again", reopens, resumed)
        if failed != self.capture_failed:
            if failed:
                logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] The engine worker's loopback device is not open; the "
                               "session keeps running and retries it at the next capture edge")
            else:
                logger.info("[SPOTIFY_VIS][ENGINE_WORKER] The engine worker's loopback device is open again")
        self.capture_failed, self.capture_reopens, self.capture_resumed = failed, reopens, resumed

    def _report_lost(self, failure: Exception) -> None:
        self._deliver_end(str(failure))

    # ---------------------------------------------------------------------------------------- control edges

    def configure(self, *, runtime_generation: int, mode: str, bar_count: int, activation: Mapping[str, Any],
                  on_configured: Callable[[tuple[int, int]], None]) -> None:
        """``VIS_CONFIGURE``: a fresh mapping, wake pipe and label namespace; the session configured with the host
        binding's own activation. Returns at once (the worker's spawn included); the reply calls ``on_configured`` with
        the engine's (generation, activation id) for the owner's render binding. The reader listens from now on (the
        main side holds the writer end until the reply, so the pipe cannot end before the session exists).

        What crosses in ``wake`` is the wake channel's transfer (``core.visualizer_engine.wake_channel``): the writer
        end on Windows, duplicated into the worker process by the control channel; the pipe's name on POSIX, where
        the session opens its own end and nothing is handed over through the resource sharer."""
        from core.process.types import MessageType
        from core.visualizer_engine.packet_mailbox import PacketMailbox
        from core.visualizer_engine.frame_capacity import required_slot_bytes
        from core.visualizer_engine.wake_channel import open_wake_channel

        missing = [key for key in ACTIVATION_KEYS if key not in activation]
        if missing:
            raise EngineWorkerFailure(f"incomplete activation inputs: {missing}")
        slot_bytes = required_slot_bytes(str(mode), activation['logical_kwargs'])
        channel = open_wake_channel()
        receiver = channel.receiver
        try:
            mailbox = PacketMailbox(role="reader", slot_bytes=slot_bytes)
        except BaseException:
            receiver.close()
            channel.release_sender()
            raise
        logger.info('[SPOTIFY_VIS][ENGINE_WORKER] Frame capacity admitted mode=%s slot_bytes=%d', mode, slot_bytes)
        self.label_namespace = next_label_namespace()
        payload: dict[str, Any] = {
            "mapping": mailbox.mapping_name, "mode": str(mode), "runtime_generation": int(runtime_generation),
            "bar_count": int(bar_count), "label_namespace": self.label_namespace, "wake": channel.transfer,
            # Production: the live engine on the worker's own cadence and the loopback device (no ``pcm``).
            "inputs": "live", "order": "free", "cadence": "worker",
            "activation": {key: activation[key] for key in ACTIVATION_KEYS},
            # Only while this process's ``--frame-trace`` is admitted: each slot then carries its publish time, which
            # the reader records as the trace's publish (native core P2 gate 3). Nothing is stamped at rest.
            "publish_stamps": mailbox.traces_publications,
        }
        if _test_session_overrides is not None:
            payload.update(_test_session_overrides)
        self._mailbox = mailbox
        self._wake_channel = channel
        self.mapping_name = mailbox.mapping_name
        try:
            mailbox.listen_for_wakes(receiver, on_closed=self._session_ended)
            # The session's lease on the worker process (slice 5.7), before looking for a running worker: released
            # at ``close``; the last release retires the worker (``engine_worker_lifetime``).
            from widgets.spotify_visualizer import engine_worker_lifetime

            self._lease = engine_worker_lifetime.lease(self._supervisor, self._thread_manager)
            self._ensure_worker()

            def configured(reply: dict) -> None:
                self._close_sender()                 # the worker holds its own end now: the pipe's end is the session's
                self.configured = True
                on_configured((int(reply["engine_generation"]), int(reply["activation_id"])))

            self._send(MessageType.VIS_CONFIGURE, payload, on_reply=configured)
        except BaseException:
            self.close()
            receiver.close()
            raise

    def _close_sender(self) -> None:
        """Give back the main side's writer end of the wake pipe and, on POSIX, the pipe's name (idempotent)."""
        channel, self._wake_channel = self._wake_channel, None
        if channel is not None:
            channel.release_sender()

    def start(self, playing: bool, *, on_failed: Callable[[EngineWorkerFailure], None] | None = None) -> None:
        """``VIS_START``: the host binding's play edge and the owner's ``start`` (the worker's cadence)."""
        from core.process.types import MessageType

        self._send(MessageType.VIS_START, {"playing": bool(playing)}, on_failed=on_failed)

    def set_playing(self, playing: bool, *, on_reply: Callable[[dict], None] | None = None) -> None:
        """``VIS_SET_PLAYING``: Media's playback truth (Media stays the one owner of "playing")."""
        from core.process.types import MessageType

        self._send(MessageType.VIS_SET_PLAYING, {"playing": bool(playing)}, on_reply=on_reply)

    def set_display_power(self, on: bool, *, on_reply: Callable[[dict], None] | None = None) -> None:
        """``VIS_SET_DISPLAY_POWER``: its reply follows the worker's park or unpark (and the worker's last pre-park
        publish, so the owner clears its reader in ``on_reply``: A6-L8)."""
        from core.process.types import MessageType

        self._send(MessageType.VIS_SET_DISPLAY_POWER, {"on": bool(on)}, on_reply=on_reply)

    # The framed view (latest-wins state) ------------------------------------------------------------------------

    def set_view_source(self, source: Callable[[], tuple] | None) -> None:
        """Where the view comes from: ``(layout_metrics_snapshot, presentation inputs)`` (the owner's controller's
        layout metrics with the drawn card's framed view, and ``logical_edges.presentation_inputs_snapshot`` of its
        presentation state), read once per send. The layout goes whole (``VIS_SET_VIEW`` version
        ``core.framed_view.VIEW_MESSAGE_VERSION``); the presentation inputs as the attributes changed since the last
        send."""
        self._view_source = source
        self._view_sent = None
        self._presentation_sent = {}

    def view_changed(self) -> None:
        """The view changed: one send per GUI turn at most (a queued flush), never more than one in flight."""
        if self._view_scheduled or self._closed:
            return
        self._view_scheduled = True
        self._events.view.emit()

    def _flush_view(self) -> None:
        self._view_scheduled = False
        if not self._view_in_flight:
            self.send_view()

    def send_view(self, *, force: bool = False) -> bool:
        """``VIS_SET_VIEW`` with the newest view when it differs from the last one sent; ``force`` sends it now even
        while one is in flight (a hidden activation: it must reach the session before ``VIS_SET_MODE``). Whether one
        was sent."""
        source = self._view_source
        if source is None or self._closed or (self._view_in_flight and not force):
            return False
        snapshot, presentation = source()
        sent = self._presentation_sent
        # By value (A8-L6): ``sent`` holds detached copies, so an in-place edit of the state's list or dict differs.
        changed = {attr: value for attr, value in presentation.items() if attr not in sent or sent[attr] != value}
        if snapshot == self._view_sent and not changed:
            return False
        from core.process.types import MessageType
        from widgets.spotify_visualizer.logical_edges import (detach_presentation_value,
                                                              report_unforwarded_presentation_input)

        refused: dict[str, Any] = {}
        for attr, value in tuple(changed.items()):
            try:
                changed[attr] = detach_presentation_value(value)
            except TypeError as exc:
                # A Qt value with no plain form nested in the input (audit L4): never pickled to the worker (its
                # process loads QtCore only), reported once, and recorded as it is so the same value is not tried
                # again at every presentation; the session keeps what it holds until the state's value changes.
                report_unforwarded_presentation_input(attr, exc)
                refused[attr] = changed.pop(attr)
        sent.update(refused)
        if snapshot == self._view_sent and not changed:
            return False
        from core.framed_view import VIEW_MESSAGE_VERSION

        extent, rotations, override_extent, override_rotations, framed_view = snapshot
        self._view_sent = snapshot
        sent.update(changed)
        self._view_in_flight = True
        payload = {"version": VIEW_MESSAGE_VERSION, "extent": extent, "rotations": rotations,
                   "override_extent": override_extent, "override_rotations": override_rotations,
                   "framed_view": None if framed_view is None else tuple(float(v) for v in framed_view)}
        if changed:
            payload["presentation"] = changed
        self._send(MessageType.VIS_SET_VIEW, payload, on_reply=self._view_answered)
        return True

    def adopt_presentation_inputs(self, values: Mapping[str, Any]) -> None:
        """Presentation inputs the session itself wrote (a preset commit's view records, A8-L2), which the main side
        adopts: recorded as held by the session, so they are not sent back."""
        from widgets.spotify_visualizer.logical_edges import detach_presentation_value

        self._presentation_sent.update({attr: detach_presentation_value(value) for attr, value in values.items()})

    def _view_answered(self, _reply: dict) -> None:
        self._view_in_flight = False
        self.send_view()                              # the newest view, if it moved on meanwhile

    # -------------------------------------------------------------------------------------------------------------

    def set_mode(self, mode: str, activation: Mapping[str, Any], *,
                 on_committed: Callable[[tuple[int, int], dict], None],
                 on_failed: Callable[[EngineWorkerFailure], None]) -> None:
        """``VIS_SET_MODE`` applied at once (the owner's hidden activation commit, in the worker): another mode, or the
        same mode as a preset / settings re-activation. The reply calls ``on_committed`` with the committed (generation,
        activation id) and the session's view records as the commit left them (A8-L2: the owner adopts them, see
        ``adopt_presentation_inputs``); a failure calls ``on_failed`` (the session closes on a failed apply, A6-M2)."""
        from core.process.types import MessageType

        from core.visualizer_engine.frame_capacity import required_slot_bytes

        change = self._mailbox.stage_capacity(required_slot_bytes(str(mode), activation['logical_kwargs']))
        if change is not None:
            self._capacity_candidates = (change['previous_mapping'], change['mapping'])

        def committed(reply: dict) -> None:
            if change is not None:
                if reply.get('mapping') != change['mapping']:
                    failed(EngineWorkerFailure('capacity activation acknowledged a different mapping'))
                    return
                try:
                    self._mailbox.commit_capacity(change)
                except Exception as exc:
                    failed(EngineWorkerFailure(f'capacity commit failed: {exc}'))
                    return
                self.mapping_name = self._mailbox.mapping_name
                self._capacity_candidates = ()
            on_committed((int(reply["engine_generation"]), int(reply["activation_id"])),
                         dict(reply.get("view_records") or {}))

        def failed(failure):
            if self._mailbox is not None:
                self.capacity_failure_report = self._mailbox.capacity_failure
            if change is not None and self._mailbox is not None:
                self._mailbox.abort_capacity(change)
            on_failed(failure)

        payload = {'mode': str(mode), 'activation': {key: activation[key] for key in ACTIVATION_KEYS}, 'at_once': True}
        if change is not None:
            payload['capacity_change'] = change
            logger.info('[SPOTIFY_VIS][ENGINE_WORKER] Frame capacity growth admitted mode=%s old_slot_bytes=%d '
                        'required_slot_bytes=%d', mode, self._mailbox.slot_bytes,
                        required_slot_bytes(str(mode), activation['logical_kwargs']))
        try:
            self._send(MessageType.VIS_SET_MODE, payload, on_reply=committed, on_failed=failed)
        except BaseException:
            if change is not None:
                self._mailbox.abort_capacity(change)
            raise

    def _await(self, message: Any, payload: Mapping[str, Any], *, timeout_ms: int) -> Any:
        """Tests and tools only: send and wait for the reply on the calling thread (the owner never does)."""
        if self._closed:
            raise EngineWorkerFailure("the link is closed")
        response = self._supervisor.send_request_and_await_response(
            self._worker_type(), message, dict(payload), timeout_ms=int(timeout_ms))
        if response is None:
            raise EngineWorkerFailure(f"{message.value}: no reply from the engine worker")
        if not response.success:
            raise EngineWorkerFailure(f"{message.value}: {response.error}",
                                      session_closed=bool((response.payload or {}).get("session_closed")))
        return response

    def feed_for_testing(self, feature: Any) -> int:
        """Tests only: one recorded input to an input-paced session (``recorded_capture_for_testing(cadence="input")``);
        the mailbox revision after its tick (waits for its reply)."""
        from core.process.types import MessageType

        return int(self._await(MessageType.VIS_INPUT, {"frame": feature}, timeout_ms=EDGE_TIMEOUT_MS)
                   .payload["revision"])

    def stop(self, *, timeout_ms: int = STOP_TIMEOUT_MS) -> dict | None:
        """Tests and tools: ``VIS_STOP`` and wait for its report (the session ends in the worker: capture, compute
        lane and its mapping view released), or None when the worker did not answer (logged)."""
        from core.process.types import MessageType

        if self._closed:
            return None
        self._stopping = True
        # A link that never configured has no mapping: its stop is addressed to no session in particular.
        mailbox = self._mailbox
        candidates = self._capacity_candidates or (mailbox.mapping_candidates if mailbox is not None else ())
        try:
            response = self._await(MessageType.VIS_STOP,
                                   {"mapping": self.mapping_name, 'mapping_candidates': candidates},
                                   timeout_ms=timeout_ms)
        except EngineWorkerFailure as exc:
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Stop: %s", exc)
            return None
        self._note_device_state_in(response.payload or {})     # a reopen after the last edge (A11-L5)
        _consume_stop_report(self.mapping_name, response)
        return (response.payload or {}).get("report")

    def retire(self) -> None:
        """Send STOP without waiting, retain its detached log callback, close the GUI resources at once.

        The report holds no link/Qt/mapping/lease; the supervisor completes or cancels it at worker retirement.
        A later configure follows STOP on the same queue. Idempotent.
        """
        from core.process.types import MessageType
        from functools import partial

        if self._closed:
            return
        self._stopping = True
        if self._outbox is None and self._mailbox is not None:
            supervisor, role = self._supervisor, self._worker_type()
            correlation = VISUALIZER_STOP_REPORT_PREFIX + uuid.uuid4().hex
            mappings = tuple(self._capacity_candidates or self._mailbox.mapping_candidates)
            callback = partial(_consume_stop_report, mappings)
            try:
                # Addressed to this session's mapping: a stop that lands after another session was configured is a
                # no-op there (the worker hosts one session at a time).
                sent = supervisor.register_response_callback(role, correlation, callback, retain_until_stopped=True)
                if sent:
                    sent = supervisor.send_message(role, MessageType.VIS_STOP,
                        {'mapping': self.mapping_name, 'mapping_candidates': mappings},
                        correlation_id=correlation) is not None
                if not sent:
                    supervisor.abandon_response(role, correlation, reason='stop_not_sent')
                    callback(None)
            except Exception:
                try:
                    supervisor.abandon_response(role, correlation, reason='stop_send_failed')
                except Exception:
                    logger.exception('[SPOTIFY_VIS][ENGINE_WORKER] Stop correlation cancellation failed')
                logger.exception('[SPOTIFY_VIS][ENGINE_WORKER] Stop report request failed mapping=%s', self.mapping_name)
        self.close()

    def close(self) -> None:
        """Close the reader (its listener ends without reporting), drop the unanswered correlations and unlink the
        mapping (idempotent). The session's lease is taken out first and released whatever the rest raises
        (checkpoint audit 10, A10-L1: ``_closed`` is set first, so a close that raised is never retried, and a lease
        left behind kept the worker, and possibly its session, until the supervisor's shutdown)."""
        if self._closed:
            return
        with self._emit_lock:
            self._closed = True
        lease, self._lease = self._lease, None
        try:
            self._events.disarm()
            pending, self._pending = self._pending, {}
            for _message, _payload, correlation, _on_reply, _on_failed in pending.values():
                if correlation:
                    try:
                        self._supervisor.abandon_response(self._worker_type(), correlation, reason="link_closed")
                    except Exception:
                        pass
            self._outbox = None
            self._close_sender()
            mailbox, self._mailbox = self._mailbox, None
            if mailbox is not None:
                mailbox.close()
            self._events.deleteLater()
        finally:
            if lease is not None:
                from widgets.spotify_visualizer import engine_worker_lifetime

                engine_worker_lifetime.release(lease)

    # -------------------------------------------------------------------------------------- session's end

    def _session_ended(self) -> None:
        """The listener thread saw the wake pipe end while the reader was open: the session is gone. Also the edge
        the reader reports a refused frame payload on (N2.3: the stream failed at a slot head; the GUI thread's take)."""
        if not self._stopping:
            refused = getattr(self._mailbox, 'payload_failure', None)
            if refused is not None:
                self.payload_failure_report = refused
                self._emit('ended', f"frame payload refused ({refused['cause']}, sequence {refused['sequence']}): "
                                    f"{refused['reason']}")
                return
            failure = self._mailbox.capacity_failure if self._mailbox is not None else None
            if failure is not None:
                self.capacity_failure_report = failure
                self.capacity_failure_reason = (f"frame capacity violation: actual_bytes={failure['actual_bytes']} "
                                                f"capacity_bytes={failure['capacity_bytes']}")
                self._emit('ended', self.capacity_failure_reason)
                return
            self._emit("ended", "the engine worker's session ended (closed after a failure, or the process died)")

    def _deliver_end(self, reason: str) -> None:
        if self._closed or self._stopping or self._lost_reported:
            return
        self._lost_reported = True
        self._on_lost(self, str(reason))


def _consume_stop_report(mapping: str | tuple[str, ...], response: Any) -> None:
    """Logging-only completion: safe after the entire GUI generation is gone."""
    prefix = '[ENGINE_WORKER] Stop report'
    if response is None:
        diagnostic_logger.warning('%s unavailable mapping=%s (report not received before completion retired)', prefix, mapping)
        return
    if not response.success:
        diagnostic_logger.error('%s failed mapping=%s: %s', prefix, mapping, response.error)
        return
    payload = response.payload or {}
    if payload.get('stale'):
        diagnostic_logger.info('%s stale mapping=%s (the addressed session already ended)', prefix, mapping)
        return
    report = payload.get('report')
    if not isinstance(report, Mapping):
        diagnostic_logger.warning('%s empty mapping=%s', prefix, mapping)
        return
    candidates = (mapping,) if isinstance(mapping, str) else tuple(mapping or ())
    if candidates and report.get('mapping') not in candidates:      # an unaddressed stop names no mapping to match
        diagnostic_logger.error('%s mapping mismatch expected=%s actual=%s', prefix, candidates, report.get('mapping'))
        return
    engine = report.get('engine') or {}
    failed = report.get('failed')
    write = diagnostic_logger.error if failed else diagnostic_logger.info
    write('%s mapping=%s revision=%s failed=%s capture_failed=%s capture_reopens=%s capture_resumed=%s',
          prefix, report.get('mapping'), report.get('revision'), failed, engine.get('capture_failed'),
          engine.get('capture_reopens'), engine.get('capture_resumed'))


def configure_presentation_side(
    controller: Any,
    *,
    activation: Mapping[str, Any],
    thread_manager: Any | None,
    process_supervisor: Any | None,
    playing: bool,
    refresh_presentation: Callable[[], None] | None,
) -> None:
    """The owner's configuration on the engine-worker path, main-process side: only what presentation reads. The
    activation's inputs recorded (what Settings, menus and the Edit routes read from the controller), the presentation
    state configured from ``presentation_kwargs`` exactly as ``logical_edges.apply_logical_configuration`` configures
    it, Media's state, and the owner's backdrop step. No engine, technical (DSP) config, logical tick state or mode
    state: those are the worker's, the one owner of logical state (no second copy on the main side)."""
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.logical_edges import record_activation_inputs
    from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
    from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config

    record_activation_inputs(controller, settings_model=activation["settings_model"],
                             resolved_activation=activation["resolved_activation"],
                             technical_cache=activation["technical_cache"])
    presentation_kwargs = activation["presentation_kwargs"]
    resolved = (resolve_mode_source_config(controller.mode_id, presentation_kwargs)
                if presentation_kwargs is not None else None)
    install_default_presentation_state(controller.presentation_state)
    if resolved:
        apply_presentation_vis_mode_kwargs(controller.presentation_state, resolved)
    controller.enabled = True
    controller.playing = bool(playing)
    if thread_manager is not None:
        controller.thread_manager = thread_manager
    if process_supervisor is not None:
        controller.process_supervisor = process_supervisor
    if refresh_presentation is not None:
        refresh_presentation()


__all__ = [
    "ACTIVATION_KEYS",
    "MAX_RECOVERIES_PER_RUN",
    "EngineWorkerFailure",
    "EngineWorkerLink",
    "claim_recovery_for_run",
    "configure_presentation_side",
    "disable_worker_for_run",
    "next_label_namespace",
    "recorded_capture_for_testing",
    "reset_run_state_for_testing",
    "worker_disabled_for_run",
]

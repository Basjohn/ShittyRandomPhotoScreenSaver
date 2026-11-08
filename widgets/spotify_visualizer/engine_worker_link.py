"""The production Visualizer owner on the engine worker, main-process side (native core P2b, work order 5 slices 5.2 and
5.5).

Admitted by ``core.diagnostics.experiment_flags.visualizer_engine_worker_admitted`` (``--viz-engine-worker``, default
OFF), read once per owner construction. Off, nothing here is imported and no worker process exists. On, the owner
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
waits for the worker's spawn: a worker that is not running is (re)started on a ``ThreadManager`` IO task (a dead one is
stopped first, which retires its stale response listener), the requests sent meanwhile wait in the link's outbox, in
order, and leave when the spawn reports back (an event). The framed view (``VIS_SET_VIEW``) is latest-wins state: at
most one in flight, writes inside one GUI turn coalesce into one send (a queued flush), and the newest view leaves when
the previous one is answered.

**Liveness.** A dead worker is seen by an event: the session's wake pipe ends (the worker held the only writer end), and
the supervisor cancels the outstanding correlations when it retires the process. A hung-but-alive worker (no reply, the
process alive) is the supervisor's heartbeat's: missed heartbeats restart the worker (bounded: ``HealthStatus
.MISSED_HEARTBEAT_THRESHOLD`` intervals, then the stop's graceful bound and termination), which ends the pipe and cancels
the correlations, so the owner's failure path runs; nothing on the GUI thread waits meanwhile.

What the link owns, once:

- **The label namespace counter** (``next_label_namespace``): one process-wide counter, owned by this module for the
  app's life, never repeated across sessions or restarted workers; every ``VIS_CONFIGURE`` takes a fresh value
  (Extruded Bubble's drift-family revisions are a renderer cache identity: ``engine_worker``'s ``label_namespace``).
- **The session's end:** the main process closes its copy of the wake pipe's writer end once the worker holds its own
  (the configure's reply), so the pipe ends exactly when the session does (closed after a failure, or its process
  died); the listener reports that once, through a queued signal, to the owner's GUI thread (``on_lost``). A capture
  device that fails to open is not the session's end (A7-L4): the session keeps running, reports it in later replies
  (``capture_failed``) and retries the device on the next edge that opens capture.
- **The run's failure record** (``worker_disabled_for_run``): after a session failed twice for an owner (the reconfigure
  included), the engine worker stays off for the rest of the run, and every later owner runs in process.

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

logger = get_logger(__name__)

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


_run_lock = threading.Lock()
_run_disabled_reason: str | None = None


def worker_disabled_for_run() -> bool:
    """Whether a second failure turned the engine worker off for the rest of the run."""
    with _run_lock:
        return _run_disabled_reason is not None


def disable_worker_for_run(reason: str) -> bool:
    """Turn the engine worker off for the rest of the run (idempotent); True the first time (the caller logs it)."""
    global _run_disabled_reason
    with _run_lock:
        if _run_disabled_reason is not None:
            return False
        _run_disabled_reason = str(reason)
        return True


def reset_run_state_for_testing() -> None:
    """Tests only: forget the run's failure record."""
    global _run_disabled_reason
    with _run_lock:
        _run_disabled_reason = None


_test_session_overrides: dict | None = None


@contextlib.contextmanager
def recorded_capture_for_testing(**overrides: Any) -> Iterator[None]:
    """Tests only: every configure the link sends while this is entered carries ``overrides`` (a recorded-PCM source:
    ``pcm`` / ``pcm_rate`` with the worker's own cadence, or ``cadence="input"`` with ``order`` / ``seed`` for the
    identity gate, fed through ``EngineWorkerLink.feed_for_testing``). The session then refuses the device for its
    life (``EngineSession``); production never enters this."""
    global _test_session_overrides
    allowed = {"pcm", "pcm_rate", "cadence", "order", "seed", "interval_s"}
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

    replied = Signal(object, object)          # token, the WorkerResponse (None: cancelled; _NOT_SENT: not sent)
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

    def _on_replied(self, token: Any, response: Any) -> None:
        link = self._target()
        if link is not None:
            link._deliver_reply(token, response)

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
        self._sender: Any = None                  # the main side's copy of the wake pipe's writer end, until configured
        self._closed = False
        self._stopping = False                    # an ordered stop: the session's end that follows is not a loss
        self._lost_reported = False
        self.label_namespace = 0
        self.mapping_name: str | None = None
        self.configured = False                   # the configure's reply arrived
        self.bar_count: int | None = None         # the session's bar count, from its configure and commit replies
        self.capture_failed = False               # the newest reply said the session's device did not open (A7-L4)
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

        supervisor, worker_type = self._supervisor, self._worker_type()
        supervisor.register_worker_factory(worker_type, visualizer_worker_main)
        if supervisor.is_running(worker_type):
            return True
        self._outbox = []
        self._spawn()
        return False

    def _spawn(self) -> None:
        """(Re)start the worker off this thread; the outbox leaves when it reports back (an event). A dead worker is
        stopped first: that retires its response listener, which would otherwise keep blocking on the dead process's
        queue."""
        supervisor, worker_type = self._supervisor, self._worker_type()

        def spawn() -> None:
            error = ""
            try:
                supervisor.stop(worker_type, timeout=1.0)        # a dead worker's queues and listener, if any
                if not supervisor.start(worker_type):
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
        to had died, and the supervisor's heartbeat restarted it: the session never existed). Once per link, every
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
                self._deliver_reply(token, _NOT_SENT, reason=error)
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

        def replied(response: Any, _token: int = token) -> None:     # the supervisor's listener thread
            self._emit("replied", _token, response)

        sent = False
        try:
            if supervisor.register_response_callback(worker_type, correlation, replied):
                sent = supervisor.send_message(worker_type, message, payload, correlation_id=correlation) is not None
        except Exception as exc:
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] %s could not be sent: %s", message.value, exc)
        if not sent:
            supervisor.abandon_response(worker_type, correlation, reason="not_sent")
            self._emit("replied", token, _NOT_SENT)

    def _deliver_reply(self, token: Any, response: Any, *, reason: str | None = None) -> None:
        entry = self._pending.get(token)
        if entry is None or self._closed:
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
        if "capture_failed" in reply:
            self.capture_failed = bool(reply["capture_failed"])
        if on_reply is not None:
            on_reply(reply)

    def _report_lost(self, failure: Exception) -> None:
        self._deliver_end(str(failure))

    # ---------------------------------------------------------------------------------------- control edges

    def configure(self, *, runtime_generation: int, mode: str, bar_count: int, activation: Mapping[str, Any],
                  on_configured: Callable[[tuple[int, int]], None]) -> None:
        """``VIS_CONFIGURE``: a fresh mapping, wake pipe and label namespace; the session configured with the host
        binding's own activation. Returns at once (the worker's spawn included); the reply calls ``on_configured`` with
        the engine's (generation, activation id) for the owner's render binding. The reader listens from now on (the
        main side holds the writer end until the reply, so the pipe cannot end before the session exists)."""
        import multiprocessing

        from core.process.types import MessageType
        from core.visualizer_engine.packet_mailbox import PacketMailbox

        missing = [key for key in ACTIVATION_KEYS if key not in activation]
        if missing:
            raise EngineWorkerFailure(f"incomplete activation inputs: {missing}")
        mailbox = PacketMailbox(role="reader")
        receiver, sender = multiprocessing.Pipe(duplex=False)
        self.label_namespace = next_label_namespace()
        payload: dict[str, Any] = {
            "mapping": mailbox.mapping_name, "mode": str(mode), "runtime_generation": int(runtime_generation),
            "bar_count": int(bar_count), "label_namespace": self.label_namespace, "wake": sender,
            # Production: the live engine on the worker's own cadence and the loopback device (no ``pcm``).
            "inputs": "live", "order": "free", "cadence": "worker",
            "activation": {key: activation[key] for key in ACTIVATION_KEYS},
        }
        if _test_session_overrides is not None:
            payload.update(_test_session_overrides)
        self._mailbox = mailbox
        self._sender = sender
        self.mapping_name = mailbox.mapping_name
        try:
            mailbox.listen_for_wakes(receiver, on_closed=self._session_ended)
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
        sender, self._sender = self._sender, None
        if sender is not None:
            try:
                sender.close()
            except OSError:
                pass

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
        layout metrics, and ``logical_edges.presentation_inputs_snapshot`` of its presentation state), read once per
        send. The layout goes whole; the presentation inputs as the attributes changed since the last send."""
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
        changed = {attr: value for attr, value in presentation.items() if attr not in sent or sent[attr] != value}
        if snapshot == self._view_sent and not changed:
            return False
        from core.process.types import MessageType

        extent, rotations, override_extent, override_rotations = snapshot
        self._view_sent = snapshot
        sent.update(changed)
        self._view_in_flight = True
        payload = {"extent": extent, "rotations": rotations, "override_extent": override_extent,
                   "override_rotations": override_rotations}
        if changed:
            payload["presentation"] = changed
        self._send(MessageType.VIS_SET_VIEW, payload, on_reply=self._view_answered)
        return True

    def _view_answered(self, _reply: dict) -> None:
        self._view_in_flight = False
        self.send_view()                              # the newest view, if it moved on meanwhile

    # -------------------------------------------------------------------------------------------------------------

    def set_mode(self, mode: str, activation: Mapping[str, Any], *, on_committed: Callable[[tuple[int, int]], None],
                 on_failed: Callable[[EngineWorkerFailure], None]) -> None:
        """``VIS_SET_MODE`` applied at once (the owner's hidden activation commit, in the worker): another mode, or the
        same mode as a preset / settings re-activation. The reply calls ``on_committed`` with the committed (generation,
        activation id); a failure calls ``on_failed`` (the session closes on a failed apply, A6-M2)."""
        from core.process.types import MessageType

        def committed(reply: dict) -> None:
            on_committed((int(reply["engine_generation"]), int(reply["activation_id"])))

        self._send(MessageType.VIS_SET_MODE, {
            "mode": str(mode), "activation": {key: activation[key] for key in ACTIVATION_KEYS}, "at_once": True},
            on_reply=committed, on_failed=on_failed)

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
        try:
            response = self._await(MessageType.VIS_STOP, {"mapping": self.mapping_name}, timeout_ms=timeout_ms)
        except EngineWorkerFailure as exc:
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Stop: %s", exc)
            return None
        return (response.payload or {}).get("report")

    def retire(self) -> None:
        """The owner's stop (retirement, or a failed session): ``VIS_STOP`` sent, never awaited (the worker ends the
        session in order: a later configure follows it on the same queue), then the reader closed and the mapping
        unlinked. Idempotent."""
        from core.process.types import MessageType

        if self._closed:
            return
        self._stopping = True
        if self._outbox is None and self._mailbox is not None:
            try:
                # Addressed to this session's mapping: a stop that lands after another session was configured is a
                # no-op there (the worker hosts one session at a time).
                self._send(MessageType.VIS_STOP, {"mapping": self.mapping_name}, on_failed=lambda _failure: None)
            except EngineWorkerFailure:
                pass
        self.close()

    def close(self) -> None:
        """Close the reader (its listener ends without reporting), drop the unanswered correlations and unlink the
        mapping (idempotent)."""
        if self._closed:
            return
        with self._emit_lock:
            self._closed = True
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

    # -------------------------------------------------------------------------------------- session's end

    def _session_ended(self) -> None:
        """The listener thread saw the wake pipe end while the reader was open: the session is gone."""
        if not self._stopping:
            self._emit("ended", "the engine worker's session ended (closed after a failure, or the process died)")

    def _deliver_end(self, reason: str) -> None:
        if self._closed or self._stopping or self._lost_reported:
            return
        self._lost_reported = True
        self._on_lost(self, str(reason))


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
    "EngineWorkerFailure",
    "EngineWorkerLink",
    "configure_presentation_side",
    "disable_worker_for_run",
    "next_label_namespace",
    "recorded_capture_for_testing",
    "reset_run_state_for_testing",
    "worker_disabled_for_run",
]

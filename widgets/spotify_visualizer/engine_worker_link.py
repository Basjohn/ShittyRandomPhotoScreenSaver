"""The production Visualizer owner on the engine worker, main-process side (native core P2b, work order 5 slice 5.2).

Admitted by ``core.diagnostics.experiment_flags.visualizer_engine_worker_admitted`` (``--viz-engine-worker``, default
OFF), read once per owner construction. Off, nothing here is imported and no worker process exists. On, the owner
(``quick_display_visualizer_owner.QuickDisplayVisualizerOwner``) keeps no beat engine and runs no tick: one
``EngineWorkerLink`` per session sends the ``logical_edges`` control edges to the ``WorkerType.VISUALIZER`` process
(``core.visualizer_engine.engine_worker``: ``VIS_CONFIGURE`` with the host binding's own resolved activation and
``presentation_kwargs``, ``VIS_START``, Media's ``VIS_SET_PLAYING``, ``VIS_SET_DISPLAY_POWER``, ``VIS_SET_MODE``,
``VIS_STOP``) and owns the reader side of the session's frame mapping (``PacketMailbox(role="reader")``: the main
process creates, holds and unlinks it). The worker paces its own ticks (slice 5.1) and in production opens the
loopback device itself (slice 5.3). Frames reach presentation through the owner's existing path: the worker's wake byte
per publish -> ``listen_for_wakes`` (one daemon thread blocked on the pipe, never a poll) -> the owner's
``QuickVisualizerPublicationWake.request`` (a queued Qt signal: it never blocks, and coalesces) -> ``sync_present`` on
the GUI thread -> ``QuickVisualizerPresentationSync.sync_latest`` takes the newest whole frame from the mapping.

What the link owns, once:

- **The label namespace counter** (``next_label_namespace``): one process-wide counter, owned by this module for the
  app's life, never repeated across sessions or restarted workers; every ``VIS_CONFIGURE`` takes a fresh value
  (Extruded Bubble's drift-family revisions are a renderer cache identity: ``engine_worker``'s ``label_namespace``).
- **The session's end:** the main process closes its copy of the wake pipe's writer end once the worker holds its own,
  so the pipe ends exactly when the session does (closed after a failure, its capture device failed to open, or its
  process died); the listener reports that once, through a queued signal, to the owner's GUI thread (``on_lost``).
- **The run's failure record** (``worker_disabled_for_run``): after a session failed twice for an owner (the reconfigure
  included), the engine worker stays off for the rest of the run, and every later owner runs in process.

Control edges wait for their reply on the calling (GUI) thread, bounded (``EDGE_TIMEOUT_MS``); a missing or failed
reply raises ``EngineWorkerFailure`` (the owner's failure path: fade, reconfigure once, then in process). Interim
(slice 5.5 completes it): the wait itself, a hung worker's timeout, the wake pipe's backpressure.

Tests never open a device: ``recorded_capture_for_testing`` (a test-only control) adds a recorded-PCM source and its
cadence to every configure the link sends, and the session refuses the device for its life.
"""
from __future__ import annotations

import contextlib
import itertools
import threading
import weakref
from typing import Any, Callable, Iterator, Mapping

from PySide6.QtCore import QObject, Qt, Signal

from core.logging.logger import get_logger

logger = get_logger(__name__)

#: The configure's bounded wait: a cold session imports the tick and mode runtimes and builds its engine (~1-2 s).
CONFIGURE_TIMEOUT_MS = 60_000
#: Every other control edge's bounded wait.
EDGE_TIMEOUT_MS = 30_000
#: The stop at retirement or after a failure (the worker closes the session even when its finish raises, A6-L7).
STOP_TIMEOUT_MS = 10_000

#: The activation inputs the owner sends (the host binding's own; checkpoint audit 6, A6-L4).
ACTIVATION_KEYS = ("settings_model", "resolved_activation", "technical_cache", "logical_kwargs", "presentation_kwargs")


class EngineWorkerFailure(RuntimeError):
    """A control edge found no healthy session: no reply, a failed reply, or the session closed."""

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


class _SessionEnd(QObject):
    """The listener thread's report of the session's end, queued onto the owner's (GUI) thread. It reaches its link
    weakly and is disarmed when the link closes, so a late delivery is a no-op."""

    ended = Signal(str)

    def __init__(self, link: "EngineWorkerLink") -> None:
        super().__init__()
        self._link = weakref.ref(link)
        self._armed = True
        self.ended.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    def _deliver(self, reason: str) -> None:
        link = self._link() if self._armed else None
        if link is not None:
            link._deliver_end(reason)

    def disarm(self) -> None:
        self._armed = False


class EngineWorkerLink:
    """One engine-worker session seen from the main process: its control edges and its frame reader."""

    def __init__(self, supervisor: Any, *, on_lost: Callable[["EngineWorkerLink", str], None]) -> None:
        if supervisor is None:
            raise EngineWorkerFailure("no process supervisor")
        self._supervisor = supervisor
        self._on_lost = on_lost
        self._mailbox: Any = None
        self._closed = False
        self._stopping = False                    # an ordered stop: the session's end that follows is not a loss
        self._lost_reported = False
        self.label_namespace = 0
        self.mapping_name: str | None = None
        self._end = _SessionEnd(self)

    @property
    def mailbox(self) -> Any:
        """The reader side of the session's frame mapping (the owner's controller's logical mailbox)."""
        return self._mailbox

    @property
    def closed(self) -> bool:
        return self._closed

    # -------------------------------------------------------------------------------------------- the worker

    def _ensure_worker(self) -> None:
        from core.process.types import WorkerType
        from core.visualizer_engine.engine_worker import visualizer_worker_main

        supervisor = self._supervisor
        supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
        if not supervisor.is_running(WorkerType.VISUALIZER) and not supervisor.start(WorkerType.VISUALIZER):
            raise EngineWorkerFailure("the engine worker process did not start")

    def _request(self, message: Any, payload: Mapping[str, Any], *, timeout_ms: int = EDGE_TIMEOUT_MS) -> Any:
        from core.process.types import WorkerType

        if self._closed:
            raise EngineWorkerFailure("the link is closed")
        response = self._supervisor.send_request_and_await_response(
            WorkerType.VISUALIZER, message, dict(payload), timeout_ms=int(timeout_ms))
        if response is None:
            raise EngineWorkerFailure(f"{message.value}: no reply from the engine worker")
        if not response.success:
            raise EngineWorkerFailure(f"{message.value}: {response.error}",
                                      session_closed=bool((response.payload or {}).get("session_closed")))
        return response

    # ---------------------------------------------------------------------------------------- control edges

    def configure(self, *, runtime_generation: int, mode: str, bar_count: int,
                  activation: Mapping[str, Any]) -> tuple[int, int]:
        """``VIS_CONFIGURE``: a fresh mapping, wake pipe and label namespace; the session configured with the host
        binding's own activation. The engine's (generation, activation id) for the owner's render binding."""
        import multiprocessing

        from core.process.types import MessageType
        from core.visualizer_engine.packet_mailbox import PacketMailbox

        missing = [key for key in ACTIVATION_KEYS if key not in activation]
        if missing:
            raise EngineWorkerFailure(f"incomplete activation inputs: {missing}")
        self._ensure_worker()
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
        try:
            response = self._request(MessageType.VIS_CONFIGURE, payload, timeout_ms=CONFIGURE_TIMEOUT_MS)
        except BaseException:
            sender.close()
            receiver.close()
            mailbox.close()
            raise
        # The worker holds its own end now: closing ours makes the pipe's end the session's end.
        sender.close()
        self._mailbox = mailbox
        self.mapping_name = mailbox.mapping_name
        mailbox.listen_for_wakes(receiver, on_closed=self._session_ended)
        reply = response.payload or {}
        return int(reply["engine_generation"]), int(reply["activation_id"])

    def start(self, playing: bool) -> None:
        """``VIS_START``: the host binding's play edge and the owner's ``start`` (the worker's cadence)."""
        from core.process.types import MessageType

        self._request(MessageType.VIS_START, {"playing": bool(playing)})

    def set_playing(self, playing: bool) -> None:
        """``VIS_SET_PLAYING``: Media's playback truth (Media stays the one owner of "playing")."""
        from core.process.types import MessageType

        self._request(MessageType.VIS_SET_PLAYING, {"playing": bool(playing)})

    def set_display_power(self, on: bool) -> None:
        """``VIS_SET_DISPLAY_POWER``: returns after the worker parked or unparked (the reply follows the worker's last
        pre-park publish, so the owner clears its reader after it: A6-L8)."""
        from core.process.types import MessageType

        self._request(MessageType.VIS_SET_DISPLAY_POWER, {"on": bool(on)})

    def set_view(self, snapshot: tuple) -> None:
        """``VIS_SET_VIEW``: the owner's controller's layout metrics (``layout_metrics_snapshot``), which the worker's
        tick reads (the framed view: committed extent and rotations, the live CUSTOM override)."""
        from core.process.types import MessageType

        extent, rotations, override_extent, override_rotations = snapshot
        self._request(MessageType.VIS_SET_VIEW, {"extent": extent, "rotations": rotations,
                                                  "override_extent": override_extent,
                                                  "override_rotations": override_rotations})

    def set_mode(self, mode: str, activation: Mapping[str, Any]) -> tuple[int, int]:
        """``VIS_SET_MODE`` applied at once (the owner's hidden activation commit, in the worker): another mode, or the
        same mode as a preset / settings re-activation. The committed (generation, activation id)."""
        from core.process.types import MessageType

        response = self._request(MessageType.VIS_SET_MODE, {
            "mode": str(mode), "activation": {key: activation[key] for key in ACTIVATION_KEYS}, "at_once": True})
        reply = response.payload or {}
        return int(reply["engine_generation"]), int(reply["activation_id"])

    def feed_for_testing(self, feature: Any) -> int:
        """Tests only: one recorded input to an input-paced session (``recorded_capture_for_testing(cadence="input")``);
        the mailbox revision after its tick."""
        from core.process.types import MessageType

        return int(self._request(MessageType.VIS_INPUT, {"frame": feature}).payload["revision"])

    def stop(self, *, timeout_ms: int = STOP_TIMEOUT_MS) -> dict | None:
        """``VIS_STOP``: the session ends in the worker (capture, compute lane and its mapping view released). Its
        report, or None when the worker did not answer (logged)."""
        from core.process.types import MessageType

        if self._closed:
            return None
        self._stopping = True
        try:
            response = self._request(MessageType.VIS_STOP, {}, timeout_ms=timeout_ms)
        except EngineWorkerFailure as exc:
            logger.warning("[SPOTIFY_VIS][ENGINE_WORKER] Stop: %s", exc)
            return None
        return (response.payload or {}).get("report")

    def close(self) -> None:
        """Close the reader (its listener ends without reporting) and unlink the mapping (idempotent)."""
        if self._closed:
            return
        self._closed = True
        self._end.disarm()
        mailbox, self._mailbox = self._mailbox, None
        if mailbox is not None:
            mailbox.close()
        self._end.deleteLater()

    # -------------------------------------------------------------------------------------- session's end

    def _session_ended(self) -> None:
        """The listener thread saw the wake pipe end while the reader was open: the session is gone."""
        if not self._closed and not self._stopping:
            self._end.ended.emit("the engine worker's session ended (closed after a failure, or the process died)")

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

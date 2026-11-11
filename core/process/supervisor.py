"""
Process Supervisor for worker process management.

Manages lifecycle of worker processes including:
- Starting/stopping/restarting workers
- Health monitoring via heartbeat
- Exponential backoff restart policy
- Graceful shutdown integration with ResourceManager
- Supervisor-owned correlated response waiting/buffering for shared worker queues
"""
from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time
import uuid
from multiprocessing import Queue
from queue import Empty as QueueEmpty
from typing import Any, Callable, Optional

from core.constants.timing import (
    PROCESS_TERMINATE_TIMEOUT_S,
)
from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.default_contract import require_canonical_default
from core.process.types import (
    VISUALIZER_STOP_REPORT_PREFIX,
    HealthStatus,
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerState,
    WorkerType,
)
from core.process.shared_memory_transport import (
    SharedMemoryAccounting,
    SharedMemoryDescriptor,
    SharedMemoryReadLease,
    dispose_malformed_shared_memory_payload,
    dispose_shared_memory_descriptor,
)

logger = get_logger(__name__)


def process_has_exited(process: Any) -> bool:
    """Whether a worker process has exited or is on its way out (R-185).

    ``Process.is_alive()`` on Windows waits on the process handle, which is signalled only when teardown has finished:
    measured 5 to 24 ms after a kill, growing with the child's memory. For that long a dead worker still reads as
    alive, while its handle table is already gone: the session's wake pipe has ended (the owner is already
    recovering) and ``DuplicateHandle`` into it is refused. The exit status is set when termination begins, before the
    handles go, so it is read as well. Anywhere else, and for a stand-in without a process handle, ``is_alive()``
    decides."""
    if not process.is_alive():
        return True
    if os.name == "nt":
        try:
            import _winapi

            return _winapi.GetExitCodeProcess(process.sentinel) != _winapi.STILL_ACTIVE
        except (AttributeError, OSError, TypeError, ValueError):
            return False
    return False


class ProcessSupervisor:
    """
    Supervisor for managing worker processes.
    
    Provides:
    - Worker lifecycle management (start/stop/restart)
    - Health monitoring with heartbeat
    - Exponential backoff restart policy
    - Non-blocking message passing
    - Supervisor-owned correlated response waiting/buffering
    - Integration with ResourceManager for cleanup
    - Settings-based worker enable/disable
    
    Thread Safety:
    - All state access protected by _lock
    - Queue operations are process-safe
    - UI dispatch uses ThreadManager patterns
    """
    
    # Queue configuration
    REQUEST_QUEUE_SIZE = 64    # Max pending requests per worker
    RESPONSE_QUEUE_SIZE = 64   # Max pending responses per worker
    MAX_BUFFERED_RESPONSES = 128
    POLL_TIMEOUT_MS = 10       # Non-blocking poll timeout
    WORKER_READY_TIMEOUT_S = 10.0  # Longest wait for a spawned child's ready signal
    _RESPONSE_LISTENER_STOP = "__SRPSS_RESPONSE_LISTENER_STOP__"
    #: Roles whose (re)starts belong to their client, never to the heartbeat (native core P2b, work order 5 slice
    #: 5.7). The engine worker's client (``engine_worker_link``) starts it on its owner's demand and owns its recovery
    #: (fade, reconfigure once); the heartbeat only retires a dead or hung process of such a role (which ends the
    #: session's pipe and cancels its correlations, so the client sees the failure as an event). A heartbeat restart
    #: racing the client's own start could otherwise stop the fresh worker the client had just started.
    CLIENT_RESTARTED_ROLES = frozenset({WorkerType.VISUALIZER})
    
    def __init__(
        self,
        resource_manager: Optional[Any] = None,
        settings_manager: Optional[Any] = None,
        event_system: Optional[Any] = None,
    ):
        """
        Initialize the process supervisor.
        
        Args:
            resource_manager: Optional ResourceManager for lifecycle tracking
            settings_manager: Optional SettingsManager for worker enable/disable
            event_system: Optional EventSystem for health broadcasts
        """
        # ``_lock`` guards supervisor state and is only ever held for short,
        # non-blocking sections. Anything that waits on a child process (ready
        # signal, graceful join, terminate, kill) happens under the per-role
        # lifecycle lock instead, so a GUI-thread ``is_running()`` or a
        # telemetry snapshot can never queue behind a worker start or stop.
        self._lock = threading.RLock()
        self._lifecycle_locks: dict[WorkerType, threading.RLock] = {
            wt: threading.RLock() for wt in WorkerType
        }
        # Roles whose child process is being started or stopped right now
        # (guarded by ``_lock``). Such a role is "not available": no new
        # messages, listeners or heartbeat decisions until it settles.
        self._transitioning: set[WorkerType] = set()
        self._shutdown = False
        self._initialized = False

        self._resource_manager = resource_manager
        self._settings_manager = settings_manager
        self._event_system = event_system
        
        # Worker tracking
        self._workers: dict[str, mp.Process] = {}
        self._health: dict[str, HealthStatus] = {}
        self._request_queues: dict[str, Queue] = {}
        self._response_queues: dict[str, Queue] = {}
        self._worker_factories: dict[str, Callable] = {}
        self._seq_counters: dict[str, int] = {wt: 0 for wt in WorkerType}
        
        # Heartbeat monitoring: one persistent thread for the supervisor's life.
        # A threading.Timer per tick started a new OS thread every interval, and
        # a GL driver keeps per-thread state for every thread a process ever
        # creates (NVIDIA: ~70 KB each, never returned) -- 86 MB/h (R-97).
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_interval_s = HealthStatus.HEARTBEAT_INTERVAL_MS / 1000.0
        
        # Correlated response buffering so one caller cannot steal another
        # worker response from the shared queue.
        self._buffered_responses: dict[WorkerType, dict[str, list[WorkerResponse]]] = {
            wt: {} for wt in WorkerType
        }
        self._abandoned_correlations: dict[WorkerType, dict[str, str]] = {
            wt: {} for wt in WorkerType
        }
        # Optional correlated-completion ownership for callers that must not
        # occupy a shared ThreadManager worker while a child process runs.  One
        # supervisor-owned blocking listener may own a worker response queue at
        # a time.  While active it is the sole queue reader: internal messages
        # are processed here, registered correlations are delivered directly,
        # and everything else enters the same bounded response buffer consumed
        # by poll_responses()/await_response().
        self._response_callbacks: dict[
            WorkerType,
            dict[str, Callable[[Optional[WorkerResponse]], None]],
        ] = {wt: {} for wt in WorkerType}
        # Logging-only visualizer STOP reports outlive their GUI link, through
        # the listener-to-direct-drain handoff; never retain a runtime callback.
        self._stop_report_correlations: set[tuple[WorkerType, str]] = set()
        self._response_listener_threads: dict[WorkerType, threading.Thread] = {}
        self._response_listener_stopping: set[WorkerType] = set()
        self._response_condition = threading.Condition(self._lock)
        self._shared_memory_accounting = SharedMemoryAccounting()
        
        # Initialize health status for all worker types
        for wt in WorkerType:
            self._health[wt] = HealthStatus(
                worker_type=wt,
                state=WorkerState.STOPPED,
            )
        
        self._initialized = True

        # Safety net: ensure shutdown() runs at interpreter exit so workers
        # receive a graceful SHUTDOWN and release log file handles.
        import atexit
        import weakref
        _self_ref = weakref.ref(self)
        def _atexit_shutdown():
            obj = _self_ref()
            if obj is not None:
                try:
                    obj.shutdown(timeout=5.0)
                except Exception:
                    pass
        atexit.register(_atexit_shutdown)

        logger.info("ProcessSupervisor initialized")
    
    def register_worker_factory(
        self,
        worker_type: WorkerType,
        factory: Callable[[Queue, Queue], None],
    ) -> None:
        """
        Register a factory function for creating workers.
        
        Args:
            worker_type: Type of worker this factory creates
            factory: Callable that takes (request_queue, response_queue)
                     and runs the worker loop
        """
        with self._lock:
            self._worker_factories[worker_type] = factory
            logger.debug("Registered factory for %s worker", worker_type.value)
    
    def start(self, worker_type: WorkerType) -> bool:
        """
        Start a worker process.
        
        Args:
            worker_type: Type of worker to start
            
        Returns:
            True if worker started successfully
        """
        if self._shutdown:
            logger.warning("Cannot start worker during shutdown")
            return False

        # One start/stop/restart per role at a time. This lock is held across
        # the spawn and the ready wait, so it is never taken by availability
        # queries, messaging or telemetry (those use ``_lock`` alone).
        with self._lifecycle_locks[worker_type]:
            self._retire_dead_role(worker_type)
            started = self._start_role(worker_type)
            if self._shutdown and worker_type in self._workers:
                # shutdown() began while this start was waiting for ready; it
                # may already have walked the worker table, so retire the child
                # here rather than leave it registered but unowned.
                self._stop_role(worker_type, 1.0)
                return False
            return started

    def _start_role(self, worker_type: WorkerType) -> bool:
        with self._lock:
            # Check if already running
            if worker_type in self._workers and not process_has_exited(self._workers[worker_type]):
                logger.debug("%s worker already running", worker_type.value)
                return True

            # Check if worker is enabled in settings
            if not self._is_worker_enabled(worker_type):
                logger.info("%s worker disabled in settings", worker_type.value)
                return False

            # Check for factory
            if worker_type not in self._worker_factories:
                logger.error("No factory registered for %s worker", worker_type.value)
                return False

            try:
                # Create queues
                req_q = Queue(self.REQUEST_QUEUE_SIZE)
                resp_q = Queue(self.RESPONSE_QUEUE_SIZE)
                self._request_queues[worker_type] = req_q
                self._response_queues[worker_type] = resp_q

                # Update health state
                self._health[worker_type].state = WorkerState.STARTING

                factory = self._worker_factories[worker_type]
                process = mp.Process(
                    target=factory,
                    args=(req_q, resp_q),
                    name=f"SRPSS_{worker_type.value}_worker",
                    daemon=True,  # Die with parent
                )
                # From here until the role settles, nothing else may use it.
                self._transitioning.add(worker_type)
            except Exception as e:
                logger.exception("Failed to start %s worker: %s", worker_type.value, e)
                self._health[worker_type].state = WorkerState.ERROR
                self._health[worker_type].error_message = str(e)
                self._broadcast_health(worker_type)
                return False

        # Spawning and the ready wait take as long as the child needs (seconds
        # on a loaded machine) and run without the state lock.
        try:
            process.start()
            self._apply_worker_process_priority(worker_type, process.pid)

            with self._lock:
                self._workers[worker_type] = process
                self._health[worker_type].pid = process.pid

            logger.info(
                "Started %s worker (PID: %d), waiting for ready signal...",
                worker_type.value,
                process.pid,
            )

            # Wait for WORKER_READY signal before marking as RUNNING.
            # Without this, callers may send messages before the worker's
            # message loop has started, causing timeouts on the first
            # request (e.g. display 0's initial image load).
            ready = False
            deadline = time.time() + self.WORKER_READY_TIMEOUT_S
            while time.time() < deadline and process.is_alive() and not self._shutdown:
                try:
                    data = resp_q.get(timeout=0.25)
                    resp = self._response_from_data(data)
                    if resp.msg_type == MessageType.WORKER_READY:
                        ready = True
                        break
                    if self._process_internal_response(worker_type, resp):
                        continue
                    if self._dispose_if_abandoned(worker_type, resp):
                        continue
                    self._buffer_response(worker_type, resp)
                except QueueEmpty:
                    continue
                except Exception:
                    break

            with self._lock:
                if not ready:
                    logger.error(
                        "%s worker started but never signalled ready",
                        worker_type.value,
                    )
                    self._health[worker_type].state = WorkerState.ERROR
                    self._health[worker_type].error_message = "Worker never signalled ready"
                    self._broadcast_health(worker_type)
                    return False

                self._health[worker_type].state = WorkerState.RUNNING
                self._health[worker_type].record_heartbeat()
                logger.info("%s worker ready", worker_type.value)

                # Start heartbeat monitoring if not already running
                self._ensure_heartbeat_monitoring()

                # Broadcast health update
                self._broadcast_health(worker_type)

                return True

        except Exception as e:
            logger.exception("Failed to start %s worker: %s", worker_type.value, e)
            with self._lock:
                self._health[worker_type].state = WorkerState.ERROR
                self._health[worker_type].error_message = str(e)
                self._broadcast_health(worker_type)
            return False
        finally:
            with self._lock:
                self._transitioning.discard(worker_type)

    def _retire_dead_role(self, worker_type: WorkerType) -> None:
        """Before a start (the role's lifecycle lock held): retire what a dead process left behind, its response
        listener included (native core P2b, work order 5 slice 5.7). ``_start_role`` replaces the role's queues; the old
        listener, still blocked on the dead process's queue, would otherwise count as the role's active listener, and a
        callback registered for the fresh worker would wait on a listener that never reads the fresh queue. Until 5.7
        the engine worker's link stopped the role itself before every start."""
        with self._lock:
            process = self._workers.get(worker_type)
            dead = process is not None and process_has_exited(process)
            orphaned_listener = process is None and worker_type in self._response_listener_threads
        if not dead and not orphaned_listener:
            return
        logger.info("Retiring the dead %s worker before its start", worker_type.value)
        self._stop_response_listener(worker_type, reason="worker_died")
        if dead:
            # A process still being torn down (``process_has_exited``) finishes within milliseconds: wait for it
            # here (the role's lifecycle lock, never the state lock or the GUI thread), so its handle is closed with
            # the role instead of being terminated again as a worker that would not stop.
            join = getattr(process, "join", None)
            if callable(join):
                join(timeout=PROCESS_TERMINATE_TIMEOUT_S)
            self._stop_role(worker_type, 0.0)

    def _stop_if_current(self, worker_type: WorkerType, process: Any, timeout: float) -> bool:
        """Stop ``process`` only while it is still the role's process (checked and stopped under the role's lifecycle
        lock, so a start cannot land in between): a decision taken about one process never stops its successor. Whether
        it was stopped."""
        with self._lifecycle_locks[worker_type]:
            with self._lock:
                if self._workers.get(worker_type) is not process:
                    return False
            self._stop_response_listener(worker_type, reason="worker_stopping")
            self._stop_role(worker_type, timeout)
            return True

    def _retire_judged_process(self, worker_type: WorkerType, process: Any) -> bool:
        """The heartbeat's action for a client-restarted role (``CLIENT_RESTARTED_ROLES``): retire the dead or hung
        process it judged, never start one (the client restarts it on its owner's demand). Fenced by the process's
        identity, so a fresh worker the client started meanwhile is left alone."""
        retired = self._stop_if_current(worker_type, process, 5.0)
        if retired:
            logger.warning(
                "Retired the %s worker (dead or unresponsive); its client restarts it on demand",
                worker_type.value,
            )
        else:
            logger.info(
                "The %s worker the heartbeat judged was already replaced; the fresh worker is left running",
                worker_type.value,
            )
        return retired

    def stop(self, worker_type: WorkerType, timeout: float = 5.0) -> bool:
        """
        Stop a worker process gracefully.
        
        Args:
            worker_type: Type of worker to stop
            timeout: Seconds to wait for graceful shutdown
            
        Returns:
            True if worker stopped successfully
        """
        # Listener ownership and direct shutdown draining must never race the
        # same multiprocessing response queue.  Stop/cancel correlated callback
        # ownership before entering the worker-stop critical section.
        self._stop_response_listener(
            worker_type,
            reason="worker_stopping",
        )

        with self._lifecycle_locks[worker_type]:
            return self._stop_role(worker_type, timeout)

    def _stop_role(self, worker_type: WorkerType, timeout: float) -> bool:
        with self._lock:
            if worker_type not in self._workers:
                return True

            process = self._workers[worker_type]
            if not process.is_alive():
                self._cleanup_worker(worker_type)
                return True

            self._health[worker_type].state = WorkerState.STOPPING
            req_queue = self._request_queues.get(worker_type)
            if req_queue is None:
                return False
            self._transitioning.add(worker_type)
            shutdown_seq = self._next_seq(worker_type)          # the counters are lock-guarded state

        # The graceful wait, terminate and kill below take seconds when a child
        # is wedged or starved. They run without the state lock: holding it here
        # froze every is_running()/telemetry caller (the GUI thread among them)
        # for the whole stop.
        try:
            # Send shutdown message
            shutdown_msg = WorkerMessage(
                msg_type=MessageType.SHUTDOWN,
                seq_no=shutdown_seq,
                correlation_id=str(uuid.uuid4()),
                worker_type=worker_type,
            )
            try:
                req_queue.put_nowait(shutdown_msg.to_dict())
            except Exception:
                pass

            # Drain response resources while waiting.  In particular this
            # acknowledges a published ImageWorker mapping so the worker
            # can close its producer handle and reach SHUTDOWN cleanly.
            deadline = time.monotonic() + max(0.0, float(timeout))
            while process.is_alive() and time.monotonic() < deadline:
                self._drain_worker_response_queue(
                    worker_type,
                    dispose_application=True,
                    reason="worker_stopping",
                )
                remaining = max(0.0, deadline - time.monotonic())
                process.join(timeout=min(0.05, remaining))

            self._drain_worker_response_queue(
                worker_type,
                dispose_application=True,
                reason="worker_stopping",
            )

            if process.is_alive():
                logger.warning(
                    "%s worker did not stop gracefully, terminating",
                    worker_type.value,
                )
                process.terminate()
                process.join(timeout=PROCESS_TERMINATE_TIMEOUT_S)

                if process.is_alive():
                    logger.error(
                        "%s worker did not terminate, killing",
                        worker_type.value,
                    )
                    process.kill()
                    process.join(timeout=PROCESS_TERMINATE_TIMEOUT_S)

            with self._lock:
                self._cleanup_worker(worker_type)
            logger.info("Stopped %s worker", worker_type.value)
            return True

        except Exception as e:
            logger.exception("Error stopping %s worker: %s", worker_type.value, e)
            with self._lock:
                self._cleanup_worker(worker_type)
            return False
        finally:
            with self._lock:
                self._transitioning.discard(worker_type)

    def restart(self, worker_type: WorkerType, *, judged: Any = None) -> bool:
        """
        Restart a worker process with backoff.

        Args:
            worker_type: Type of worker to restart
            judged: The process the caller judged (the heartbeat's decision): the
                restart stops only that process, so a successor started meanwhile
                is never stopped (slice 5.7). None: whatever runs now.

        Returns:
            True if worker restarted successfully
        """
        if judged is not None:
            return self._restart_judged(worker_type, judged)
        with self._lock:
            health = self._health[worker_type]
            
            if not health.should_restart():
                logger.warning(
                    "Cannot restart %s worker: restart limit exceeded",
                    worker_type.value,
                )
                return False
            
            health.state = WorkerState.RESTARTING
            health.record_restart()
            
            # Calculate backoff delay
            backoff_ms = health.get_restart_backoff_ms()
            logger.info(
                "Restarting %s worker after %dms backoff (attempt %d)",
                worker_type.value,
                backoff_ms,
                health.restart_count,
            )
        
        # Stop then start (outside lock to avoid deadlock)
        self.stop(worker_type)

        # Apply backoff delay
        time.sleep(backoff_ms / 1000.0)

        return self.start(worker_type)

    def _restart_judged(self, worker_type: WorkerType, judged: Any) -> bool:
        """The heartbeat's restart of the process it judged dead or hung (the image roles; slice 5.7's fence).

        The identity check, the restart budget and the stop happen under the role's lifecycle lock, so a start cannot
        land in between: a role already replaced (a foreground start won the race) is left alone and the skip is not
        charged against ``MAX_RESTARTS_PER_WINDOW``, since it restarted nothing (checkpoint audit 10, A10-L3; until
        then the check ran unlocked and ``record_restart`` came before the fenced stop). The backoff and the start
        follow outside the lock, as an unfenced restart's do."""
        with self._lifecycle_locks[worker_type]:
            with self._lock:
                replaced = self._workers.get(worker_type) is not judged
                if not replaced:
                    health = self._health[worker_type]
                    if not health.should_restart():
                        logger.warning(
                            "Cannot restart %s worker: restart limit exceeded",
                            worker_type.value,
                        )
                        return False
                    health.state = WorkerState.RESTARTING
                    health.record_restart()
                    backoff_ms = health.get_restart_backoff_ms()
                    logger.info(
                        "Restarting %s worker after %dms backoff (attempt %d)",
                        worker_type.value,
                        backoff_ms,
                        health.restart_count,
                    )
            if not replaced:
                self._stop_response_listener(worker_type, reason="worker_stopping")
                self._stop_role(worker_type, 5.0)
        if replaced:
            logger.info(
                "Skipping the %s worker restart: the judged process was already replaced (not counted)",
                worker_type.value,
            )
            return self.is_running(worker_type)
        time.sleep(backoff_ms / 1000.0)
        return self.start(worker_type)
    
    def send_message(
        self,
        worker_type: WorkerType,
        msg_type: MessageType,
        payload: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send a message to a worker (non-blocking).
        
        Args:
            worker_type: Target worker type
            msg_type: Message type
            payload: Message payload (must be picklable)
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Correlation ID if sent, None if queue full or worker not running
        """
        with self._lock:
            if worker_type in self._transitioning or worker_type not in self._workers:
                return None
            
            if process_has_exited(self._workers[worker_type]):
                return None

            req_queue = self._request_queues.get(worker_type)
            if not req_queue:
                return None
            
            corr_id = correlation_id or str(uuid.uuid4())
            message = WorkerMessage(
                msg_type=msg_type,
                seq_no=self._next_seq(worker_type),
                correlation_id=corr_id,
                payload=payload,
                worker_type=worker_type,
            )
            
            # Validate size
            if not message.validate_size():
                logger.warning(
                    "Message payload too large for %s worker",
                    worker_type.value,
                )
                return None

            if worker_type in self.CLIENT_RESTARTED_ROLES:
                from core.process.control_messages import EncodedControl
                process = self._workers[worker_type]
                # Queue's feeder must never serialize user payloads: that can
                # fail after the caller already accepted an ordered edge.
                try:
                    encoded = EncodedControl(message.to_dict(), process)
                except OSError:
                    # The target died between the check above and its handle transfer (R-185): not running, as
                    # documented, never an exception out of a send to a dead worker.
                    if process_has_exited(process):
                        logger.warning('Ordered %s control %s not sent: the worker process has exited',
                                       worker_type.value, msg_type.value)
                        return None
                    raise
                try:
                    req_queue.put_nowait(encoded.data)
                except Exception as exc:
                    encoded.close_unsubmitted()
                    logger.warning('Ordered %s control %s refused without evicting an earlier edge: %s',
                                   worker_type.value, msg_type.value, type(exc).__name__)
                    return None
                encoded.submitted()
                return corr_id
            
            try:
                req_queue.put_nowait(message.to_dict())
                return corr_id
            except Exception:
                # Queue full - drop oldest policy
                try:
                    req_queue.get_nowait()  # Drop oldest
                    req_queue.put_nowait(message.to_dict())
                    logger.debug("Dropped oldest message for %s worker", worker_type.value)
                    return corr_id
                except Exception:
                    return None
    
    def poll_responses(
        self,
        worker_type: WorkerType,
        max_count: int = 10,
    ) -> list:
        """
        Poll for responses from a worker (non-blocking).
        
        Args:
            worker_type: Worker type to poll
            max_count: Maximum responses to retrieve
            
        Returns:
            List of WorkerResponse objects
        """
        responses = []

        responses.extend(self._pop_buffered_responses(worker_type, max_count))
        if len(responses) >= max_count:
            return responses[:max_count]

        with self._lock:
            # A response listener is the sole queue reader while active.  Pollers
            # consume only the listener-populated buffer so they cannot steal a
            # registered completion or race internal heartbeat processing.
            if self._response_listener_active_locked(worker_type):
                return responses
            resp_queue = self._response_queues.get(worker_type)
            if not resp_queue or worker_type in self._transitioning:
                return responses
        
        # Poll outside lock to avoid blocking
        for _ in range(max(0, max_count - len(responses))):
            try:
                data = resp_queue.get_nowait()
                response = self._response_from_data(data)
                if self._process_internal_response(worker_type, response):
                    continue
                if self._dispose_if_abandoned(worker_type, response):
                    continue
                responses.append(response)
            except QueueEmpty:
                # Normal condition - queue is empty, stop polling
                break
            except Exception as e:
                # Only log actual errors, not empty queue
                logger.debug("[WORKER] Error polling response: %s", e)
                break
        
        return responses

    def register_response_callback(
        self,
        worker_type: WorkerType,
        correlation_id: str,
        callback: Callable[[Optional[WorkerResponse]], None],
        *,
        retain_until_stopped: bool = False,
    ) -> bool:
        """Deliver one correlated application response without a pool waiter.

        The first registered callback for a worker starts exactly one persistent
        supervisor-owned blocking queue listener.  No timer, polling cadence, or
        per-request thread is introduced.  The callback receives ``None`` only
        when worker teardown/restart cancels an outstanding completion owner.
        Explicit ``abandon_response()`` removes the callback silently because
        the abandoning caller already owns its local cancellation cleanup.
        ``retain_until_stopped`` is reserved for detached, logging-only
        VISUALIZER STOP reports: they survive orderly listener shutdown and
        complete during its bounded drain or cancel at final worker cleanup.
        """
        if not correlation_id or not callable(callback):
            return False
        reserved_stop = (worker_type == WorkerType.VISUALIZER
                         and correlation_id.startswith(VISUALIZER_STOP_REPORT_PREFIX))
        if retain_until_stopped != reserved_stop:
            raise ValueError('Only reserved visualizer STOP diagnostics may outlive the response listener')
        buffered: Optional[WorkerResponse] = None
        registered = True
        superseded: list[tuple[str, Callable[[Optional[WorkerResponse]], None]]] = []
        with self._lock:
            if self._shutdown or worker_type in self._response_listener_stopping:
                return False
            if worker_type in self._transitioning:
                return False
            if self._response_queues.get(worker_type) is None:
                return False
            if correlation_id in self._abandoned_correlations[worker_type]:
                return False
            callbacks = self._response_callbacks[worker_type]
            if correlation_id in callbacks:
                raise ValueError(
                    f"response callback already registered for {worker_type.value} "
                    f"correlation {correlation_id}"
                )

            worker_buffer = self._buffered_responses[worker_type]
            queued = worker_buffer.get(correlation_id)
            if queued:
                buffered = queued.pop(0)
                if not queued:
                    worker_buffer.pop(correlation_id, None)
            else:
                if retain_until_stopped:
                    # One worker hosts one session. A lost report must not
                    # accumulate while reload holds keep that worker reusable.
                    superseded = [(corr, old) for corr, old in callbacks.items()
                                  if (worker_type, corr) in self._stop_report_correlations]
                    for corr, _old in superseded:
                        callbacks.pop(corr)
                        self._stop_report_correlations.discard((worker_type, corr))
                callbacks[correlation_id] = callback
                if retain_until_stopped:
                    self._stop_report_correlations.add((worker_type, correlation_id))
                if not self._ensure_response_listener_locked(worker_type):
                    callbacks.pop(correlation_id, None)
                    self._stop_report_correlations.discard((worker_type, correlation_id))
                    registered = False

        for corr, old in superseded:
            self._invoke_response_callback(worker_type, corr, old, None,
                                           cancellation_reason='newer_stop_report')
        if buffered is not None:
            self._invoke_response_callback(
                worker_type,
                correlation_id,
                callback,
                buffered,
            )
        return registered

    def await_response(
        self,
        worker_type: WorkerType,
        correlation_id: str,
        *,
        timeout_ms: int = 5000,
        poll_slice_ms: int = 50,
    ) -> Optional[WorkerResponse]:
        """Wait for a correlated worker response without stealing others.

        Unmatched non-internal responses are buffered so later callers or
        pollers can still consume them.
        """
        buffered = self._pop_buffered_response(worker_type, correlation_id)
        if buffered is not None:
            return buffered

        with self._lock:
            resp_queue = self._response_queues.get(worker_type)
            if not resp_queue or worker_type in self._transitioning:
                return None
            listener_active = self._response_listener_active_locked(worker_type)

        deadline = time.monotonic() + max(0.0, timeout_ms / 1000.0)

        if listener_active:
            # The listener owns the queue, so a synchronous waiter sleeps on the
            # supervisor buffer condition rather than competing for queue items.
            with self._response_condition:
                while True:
                    worker_buffer = self._buffered_responses[worker_type]
                    queued = worker_buffer.get(correlation_id)
                    if queued:
                        response = queued.pop(0)
                        if not queued:
                            worker_buffer.pop(correlation_id, None)
                        return response
                    remaining = deadline - time.monotonic()
                    if remaining <= 0.0:
                        break
                    self._response_condition.wait(timeout=remaining)
            self.abandon_response(
                worker_type,
                correlation_id,
                reason="timeout",
            )
            return None

        timeout_s = max(0.0, poll_slice_ms / 1000.0)

        while time.monotonic() < deadline:
            buffered = self._pop_buffered_response(
                worker_type,
                correlation_id,
            )
            if buffered is not None:
                return buffered
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            try:
                data = resp_queue.get(timeout=min(timeout_s, remaining))
                response = self._response_from_data(data)
            except QueueEmpty:
                continue
            except Exception as e:
                logger.debug("[WORKER] Error awaiting response: %s", e)
                self.abandon_response(
                    worker_type,
                    correlation_id,
                    reason="await_error",
                )
                return None

            if self._process_internal_response(worker_type, response):
                continue
            if self._dispose_if_abandoned(worker_type, response):
                continue

            if response.correlation_id == correlation_id:
                return response

            self._buffer_response(worker_type, response)

        buffered = self._pop_buffered_response(worker_type, correlation_id)
        if buffered is not None:
            return buffered
        self.abandon_response(
            worker_type,
            correlation_id,
            reason="timeout",
        )
        return None

    def send_request_and_await_response(
        self,
        worker_type: WorkerType,
        msg_type: MessageType,
        payload: dict[str, Any],
        *,
        timeout_ms: int = 5000,
        correlation_id: Optional[str] = None,
    ) -> Optional[WorkerResponse]:
        """Send a worker request and wait for its correlated response."""
        corr_id = self.send_message(
            worker_type,
            msg_type,
            payload,
            correlation_id=correlation_id,
        )
        if not corr_id:
            return None
        return self.await_response(
            worker_type,
            corr_id,
            timeout_ms=timeout_ms,
        )
    
    def is_running(self, worker_type: WorkerType) -> bool:
        """Check if a worker is currently running.
        
        Args:
            worker_type: Type of worker to check
            
        Returns:
            True if worker process is alive and running
        """
        with self._lock:
            if worker_type in self._transitioning or worker_type not in self._workers:
                return False
            return not process_has_exited(self._workers[worker_type])
    
    def get_health(self, worker_type: WorkerType) -> HealthStatus:
        """Get health status for a worker."""
        with self._lock:
            return self._health.get(worker_type, HealthStatus(
                worker_type=worker_type,
                state=WorkerState.STOPPED,
            ))
    
    def get_all_health(self) -> dict[WorkerType, HealthStatus]:
        """Get health status for all workers."""
        with self._lock:
            return {wt: self._health[wt] for wt in WorkerType}
    
    def get_detailed_health(self, worker_type: WorkerType) -> dict[str, Any]:
        """Get detailed health diagnostics for a worker.
        
        Returns comprehensive health information including:
        - Basic health status
        - Queue depths
        - Memory usage (if available)
        - Processing statistics
        
        Args:
            worker_type: Type of worker to check
            
        Returns:
            Dict with detailed health information
        """
        memory_pid: int | None = None
        with self._lock:
            health = self._health.get(worker_type)
            if not health:
                return {"error": "Worker not found", "worker_type": worker_type.value}
            
            # Basic health info
            diagnostics = health.to_dict()
            
            # Add queue depths
            req_queue = self._request_queues.get(worker_type)
            resp_queue = self._response_queues.get(worker_type)
            
            try:
                diagnostics["request_queue_size"] = req_queue.qsize() if req_queue else 0
            except Exception as e:
                logger.debug("[WORKER] Exception suppressed: %s", e)
                diagnostics["request_queue_size"] = -1  # Queue doesn't support qsize
            
            try:
                diagnostics["response_queue_size"] = resp_queue.qsize() if resp_queue else 0
            except Exception as e:
                logger.debug("[WORKER] Exception suppressed: %s", e)
                diagnostics["response_queue_size"] = -1
            
            # Add process info if running
            process = self._workers.get(worker_type)
            if process and process.is_alive():
                diagnostics["process_alive"] = True
                diagnostics["process_pid"] = process.pid
                memory_pid = process.pid
            else:
                diagnostics["process_alive"] = False
                diagnostics["process_pid"] = None
            
            # Add timing info
            diagnostics["time_since_heartbeat_ms"] = (
                (time.time() - health.last_heartbeat) * 1000 
                if health.last_heartbeat > 0 else None
            )
            diagnostics["time_busy_ms"] = (
                (time.time() - health.busy_since) * 1000 
                if health.is_busy and health.busy_since > 0 else None
            )
            if worker_type in (WorkerType.IMAGE, WorkerType.IMAGE_PREFETCH):
                diagnostics["shared_memory"] = (
                    self._shared_memory_accounting.snapshot()
                )
            diagnostics["response_listener_active"] = (
                self._response_listener_active_locked(worker_type)
            )
            diagnostics["response_callbacks_pending"] = len(
                self._response_callbacks[worker_type]
            )

        # Process memory comes from the OS, not supervisor state: query it
        # outside the state lock so a slow query cannot stall other callers.
        if memory_pid is not None:
            try:
                import psutil
                proc = psutil.Process(memory_pid)
                mem_info = proc.memory_info()
                diagnostics["memory_rss_mb"] = mem_info.rss / (1024 * 1024)
                diagnostics["memory_vms_mb"] = mem_info.vms / (1024 * 1024)
                diagnostics["cpu_percent"] = proc.cpu_percent(interval=0)
            except Exception as e:
                logger.debug("[WORKER] Exception suppressed: %s", e)
                diagnostics["memory_rss_mb"] = None
                diagnostics["memory_vms_mb"] = None
                diagnostics["cpu_percent"] = None
        return diagnostics

    def get_shared_memory_accounting_snapshot(self) -> dict[str, int]:
        """Return a detached ImageWorker transfer-accounting snapshot."""
        return self._shared_memory_accounting.snapshot()

    def get_image_worker_usage_snapshot(self) -> dict[str, Any]:
        """Return PID-labelled foreground/speculative image worker usage."""
        foreground = self.get_detailed_health(WorkerType.IMAGE)
        speculative = self.get_detailed_health(WorkerType.IMAGE_PREFETCH)
        snapshot: dict[str, Any] = {
            "image_worker_pid": foreground.get("process_pid"),
            "image_worker_rss_mb": foreground.get("memory_rss_mb"),
            "image_worker_vms_mb": foreground.get("memory_vms_mb"),
            "image_prefetch_worker_pid": speculative.get("process_pid"),
            "image_prefetch_worker_rss_mb": speculative.get("memory_rss_mb"),
            "image_prefetch_worker_vms_mb": speculative.get("memory_vms_mb"),
        }
        snapshot.update(self._shared_memory_accounting.snapshot())
        return snapshot

    def get_visualizer_worker_usage_snapshot(self) -> dict[str, Any]:
        """The engine worker's PID while it runs (None otherwise), for the usage sampler's labelled per-process
        breakdown (native core P2b slice 5.7). Supervisor state only, no OS query: the sampler reads the process's CPU,
        memory and threads in its own per-process pass."""
        with self._lock:
            process = self._workers.get(WorkerType.VISUALIZER)
            pid = process.pid if process is not None and WorkerType.VISUALIZER not in self._transitioning else None
        return {"visualizer_worker_pid": pid}

    def consume_shared_memory_response(
        self,
        response: WorkerResponse,
        consumer: Callable[[memoryview, SharedMemoryDescriptor], Any],
    ) -> Any:
        """Consume one response mapping and finalize it exactly once."""
        descriptor = self._claim_shared_memory_descriptor(response)
        if descriptor is None:
            raise ValueError("Worker response has no shared-memory descriptor")

        lease = SharedMemoryReadLease(descriptor)
        consumed = False
        try:
            payload_view = lease.open()
            result = consumer(payload_view, descriptor)
            consumed = True
            return result
        finally:
            lease.close()
            self._shared_memory_accounting.finalize(
                descriptor,
                consumed=consumed,
                close_failed=lease.close_failed,
                unlink_failed=lease.unlink_failed,
            )

    def dispose_response(
        self,
        response: WorkerResponse,
        *,
        reason: str,
    ) -> bool:
        """Release payload-owned resources from a discarded response."""
        try:
            descriptor = self._claim_shared_memory_descriptor(response)
        except Exception as e:
            emergency_descriptor, unlink_failed = (
                dispose_malformed_shared_memory_payload(response.payload)
            )
            response.payload.pop("shared_memory_name", None)
            if emergency_descriptor is not None:
                self._shared_memory_accounting.finalize(
                    emergency_descriptor,
                    consumed=False,
                    unlink_failed=unlink_failed,
                )
            logger.warning(
                "[WORKER] Invalid shared-memory response discarded "
                "reason=%s reclaimed=%s: %s",
                reason,
                emergency_descriptor is not None,
                e,
            )
            return emergency_descriptor is not None
        if descriptor is None:
            return False

        _opened, unlink_failed = dispose_shared_memory_descriptor(descriptor)
        self._shared_memory_accounting.finalize(
            descriptor,
            consumed=False,
            unlink_failed=unlink_failed,
        )
        if is_perf_metrics_enabled():
            logger.info(
                "[PERF] [WORKER] reclaimed image shared memory "
                "name=%s bytes=%d reason=%s",
                descriptor.name,
                descriptor.data_size,
                reason,
            )
        return True

    def abandon_response(
        self,
        worker_type: WorkerType,
        correlation_id: str,
        *,
        reason: str = "cancelled",
    ) -> int:
        """Cancel ownership of a response and tombstone a possible late reply."""
        if not correlation_id:
            return 0
        with self._lock:
            self._abandoned_correlations[worker_type][correlation_id] = reason
            self._response_callbacks[worker_type].pop(correlation_id, None)
            self._stop_report_correlations.discard((worker_type, correlation_id))
            buffered = self._buffered_responses[worker_type].pop(
                correlation_id,
                [],
            )
            if buffered:
                self._abandoned_correlations[worker_type].pop(
                    correlation_id,
                    None,
                )
        for response in buffered:
            self.dispose_response(response, reason=reason)
        return len(buffered)
    
    def log_all_health_diagnostics(self) -> None:
        """Log detailed health diagnostics for all workers.
        
        Useful for debugging worker issues.
        """
        for worker_type in WorkerType:
            diag = self.get_detailed_health(worker_type)
            if diag.get("process_alive"):
                logger.info(
                    "[WORKER_HEALTH] %s: state=%s, pid=%s, rss=%.1fMB, "
                    "heartbeat_age=%.0fms, queue_depth=%d, restarts=%d",
                    worker_type.value,
                    diag.get("state", "UNKNOWN"),
                    diag.get("process_pid"),
                    diag.get("memory_rss_mb", 0) or 0,
                    diag.get("time_since_heartbeat_ms", 0) or 0,
                    diag.get("request_queue_size", 0),
                    diag.get("restart_count", 0),
                )
            else:
                logger.debug(
                    "[WORKER_HEALTH] %s: state=%s (not running)",
                    worker_type.value,
                    diag.get("state", "UNKNOWN"),
                )
    
    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Shutdown all workers and cleanup.
        
        Args:
            timeout: Total timeout for all workers
        """
        if self._shutdown:
            return
        
        logger.info("ProcessSupervisor shutting down...")
        self._shutdown = True

        # Stop heartbeat monitoring. Like the old timer cancel this does not
        # wait: the loop sees the event at its next wait and exits.
        self._heartbeat_stop.set()
        self._heartbeat_thread = None

        for worker_type in WorkerType:
            self._stop_response_listener(
                worker_type,
                reason="supervisor_shutdown",
            )

        for worker_type in WorkerType:
            self._dispose_buffered_responses(
                worker_type,
                reason="supervisor_shutdown",
            )
        
        # Stop all workers
        per_worker_timeout = timeout / max(len(self._workers), 1)
        for worker_type in list(self._workers.keys()):
            try:
                self.stop(worker_type, timeout=per_worker_timeout)
            except Exception as e:
                logger.error("Error stopping %s worker: %s", worker_type.value, e)

        if is_perf_metrics_enabled():
            shared = self._shared_memory_accounting.snapshot()
            logger.info(
                "[PERF] [WORKER] shared_memory_final "
                "segments_created=%d segments_live=%d live_bytes=%d "
                "segments_consumed=%d segments_reclaimed_late=%d "
                "close_failures=%d unlink_failures=%d",
                shared["segments_created"],
                shared["segments_live"],
                shared["live_bytes"],
                shared["segments_consumed"],
                shared["segments_reclaimed_late"],
                shared["close_failures"],
                shared["unlink_failures"],
            )
        logger.info("ProcessSupervisor shutdown complete")
    
    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------
    
    def _next_seq(self, worker_type: WorkerType) -> int:
        """Get next sequence number for worker (must hold lock)."""
        self._seq_counters[worker_type] += 1
        return self._seq_counters[worker_type]

    def _process_internal_response(self, worker_type: WorkerType, response: WorkerResponse) -> bool:
        """Apply supervisor-owned side effects for internal worker responses."""
        if response.msg_type == MessageType.WORKER_READY:
            return True

        if response.msg_type == MessageType.HEARTBEAT_ACK:
            with self._lock:
                self._health[worker_type].record_heartbeat()
            return True

        if response.msg_type == MessageType.WORKER_BUSY:
            with self._lock:
                self._health[worker_type].set_busy(True)
                if is_perf_metrics_enabled():
                    logger.debug(
                        "[PERF] [WORKER] %s marked as BUSY",
                        worker_type.value,
                    )
            return True

        if response.msg_type == MessageType.WORKER_IDLE:
            with self._lock:
                self._health[worker_type].set_busy(False)
                self._health[worker_type].record_heartbeat()
            return True

        return False

    def _response_from_data(self, data: Any) -> WorkerResponse:
        """Decode one queue item and register any resource descriptor."""
        response = WorkerResponse.from_dict(data)
        try:
            descriptor = SharedMemoryDescriptor.from_payload(response.payload)
        except Exception:
            # The response remains caller-owned so the normal disposal path can
            # report the malformed descriptor without silently losing it.
            descriptor = None
        if descriptor is not None:
            self._shared_memory_accounting.register(descriptor)
        return response

    def _claim_shared_memory_descriptor(
        self,
        response: WorkerResponse,
    ) -> SharedMemoryDescriptor | None:
        descriptor = SharedMemoryDescriptor.from_payload(response.payload)
        if descriptor is None:
            return None
        # Claim by removing the handle.  Repeated finalizers are therefore
        # harmless even when shutdown races a consumer exception.
        response.payload.pop("shared_memory_name", None)
        self._shared_memory_accounting.register(descriptor)
        return descriptor

    def _dispose_if_abandoned(
        self,
        worker_type: WorkerType,
        response: WorkerResponse,
    ) -> bool:
        correlation_id = response.correlation_id
        if not correlation_id:
            self.dispose_response(response, reason="uncorrelated_drop")
            return True
        with self._lock:
            reason = self._abandoned_correlations[worker_type].pop(
                correlation_id,
                None,
            )
        if reason is None:
            return False
        self.dispose_response(response, reason=f"late_{reason}")
        return True

    def _response_listener_active_locked(self, worker_type: WorkerType) -> bool:
        thread = self._response_listener_threads.get(worker_type)
        return bool(
            thread is not None
            and thread.is_alive()
            and worker_type not in self._response_listener_stopping
        )

    def _ensure_response_listener_locked(self, worker_type: WorkerType) -> bool:
        """Start the one blocking response listener for ``worker_type``.

        Must be called with ``_lock`` held.  The listener owns no cadence; it
        sleeps inside the multiprocessing response queue until the child emits
        a message or supervisor teardown posts the private stop sentinel.
        """
        if self._response_listener_active_locked(worker_type):
            return True
        if worker_type in self._response_listener_stopping:
            return False
        response_queue = self._response_queues.get(worker_type)
        if response_queue is None:
            return False

        existing = self._response_listener_threads.get(worker_type)
        if existing is not None and existing.is_alive():
            return False

        thread = threading.Thread(
            target=self._response_listener_loop,
            args=(worker_type, response_queue),
            name=f"SRPSS_{worker_type.value}_response_listener",
            daemon=True,
        )
        self._response_listener_threads[worker_type] = thread
        thread.start()
        return True

    @staticmethod
    def _configure_response_listener_priority(worker_type: WorkerType) -> None:
        """Keep speculative *parent-side* RGBA handoff below Quick priority.

        Demoting only the child IMAGE_PREFETCH process was insufficient: its
        supervisor callback runs on this listener and can copy/admit tens of
        megabytes of QImage data.  Reuse the existing native scheduling helper
        on the listener itself; foreground and other listeners stay untouched.
        The transport remains functional if Windows rejects priority tuning.
        """
        if worker_type != WorkerType.IMAGE_PREFETCH:
            return
        from core.windows.thread_priority import apply_best_effort_thread_priority
        applied, mode, native_priority = apply_best_effort_thread_priority()
        if not applied:
            # Operational priority is best-effort; aborting the listener here
            # could strand an already-admitted shared-memory response.
            import os
            if os.name == "nt":
                logger.warning(
                    "Speculative response listener could not lower OS thread priority: %s",
                    mode,
                )
            return
        logger.info(
            "Speculative image response listener priority=%s native=%s",
            mode,
            native_priority,
        )

    def _response_listener_loop(self, worker_type: WorkerType, response_queue: Queue) -> None:
        """Block on one worker queue and route responses to their owners."""
        self._configure_response_listener_priority(worker_type)
        unexpected_callbacks: list[
            tuple[str, Callable[[Optional[WorkerResponse]], None]]
        ] = []
        try:
            while True:
                try:
                    data = response_queue.get()
                except (EOFError, OSError, ValueError):
                    break
                except Exception as e:
                    logger.debug(
                        "[WORKER] %s response listener stopped by queue error: %s",
                        worker_type.value,
                        e,
                    )
                    break

                if data == self._RESPONSE_LISTENER_STOP:
                    break

                try:
                    response = self._response_from_data(data)
                except Exception as e:
                    logger.warning(
                        "[WORKER] %s response listener discarded malformed item: %s",
                        worker_type.value,
                        e,
                    )
                    continue

                if self._process_internal_response(worker_type, response):
                    continue
                if self._dispose_if_abandoned(worker_type, response):
                    continue
                self._buffer_response(worker_type, response)
        finally:
            with self._response_condition:
                unexpected_exit = worker_type not in self._response_listener_stopping
                current = self._response_listener_threads.get(worker_type)
                if current is threading.current_thread():
                    self._response_listener_threads.pop(worker_type, None)
                if unexpected_exit:
                    unexpected_callbacks = self._take_response_callbacks_locked(worker_type)
                self._response_condition.notify_all()
            for correlation_id, callback in unexpected_callbacks:
                self._invoke_response_callback(
                    worker_type,
                    correlation_id,
                    callback,
                    None,
                    cancellation_reason="response_listener_stopped",
                )

    def _stop_response_listener(
        self,
        worker_type: WorkerType,
        *,
        reason: str,
        join_timeout: float = 2.0,
    ) -> None:
        """Stop one queue listener before direct shutdown draining begins."""
        with self._lock:
            thread = self._response_listener_threads.get(worker_type)
            response_queue = self._response_queues.get(worker_type)
            if thread is None:
                callbacks = self._take_response_callbacks_locked(
                    worker_type, preserve_stop_reports=reason in ('worker_stopping', 'supervisor_shutdown'))
            else:
                self._response_listener_stopping.add(worker_type)
                callbacks = []

        if thread is not None:
            if response_queue is not None:
                try:
                    # Blocking put is bounded and used only on explicit worker
                    # retirement.  The live listener is consuming this queue, so
                    # this cannot create an application cadence or polling loop.
                    response_queue.put(self._RESPONSE_LISTENER_STOP, timeout=1.0)
                except Exception as e:
                    logger.debug(
                        "[WORKER] Failed to wake %s response listener: %s",
                        worker_type.value,
                        e,
                    )
            thread.join(timeout=max(0.0, float(join_timeout)))

            with self._lock:
                if thread.is_alive():
                    logger.warning(
                        "[WORKER] %s response listener did not stop before worker teardown",
                        worker_type.value,
                    )
                elif self._response_listener_threads.get(worker_type) is thread:
                    self._response_listener_threads.pop(worker_type, None)
                self._response_listener_stopping.discard(worker_type)
                callbacks = self._take_response_callbacks_locked(
                    worker_type, preserve_stop_reports=reason in ('worker_stopping', 'supervisor_shutdown'))

        for correlation_id, callback in callbacks:
            self._invoke_response_callback(
                worker_type,
                correlation_id,
                callback,
                None,
                cancellation_reason=reason,
            )

    def _take_response_callbacks_locked(
        self,
        worker_type: WorkerType,
        *,
        preserve_stop_reports: bool = False,
    ) -> list[tuple[str, Callable[[Optional[WorkerResponse]], None]]]:
        callbacks = self._response_callbacks[worker_type]
        items = [(corr, callback) for corr, callback in callbacks.items()
                 if not preserve_stop_reports or (worker_type, corr) not in self._stop_report_correlations]
        for corr, _callback in items:
            callbacks.pop(corr)
            self._stop_report_correlations.discard((worker_type, corr))
        return items

    def _invoke_response_callback(
        self,
        worker_type: WorkerType,
        correlation_id: str,
        callback: Callable[[Optional[WorkerResponse]], None],
        response: Optional[WorkerResponse],
        *,
        cancellation_reason: str | None = None,
    ) -> None:
        try:
            callback(response)
        except Exception:
            logger.exception(
                "[WORKER] %s response callback failed correlation=%s cancellation=%s",
                worker_type.value,
                correlation_id,
                cancellation_reason,
            )
            if response is not None:
                self.dispose_response(response, reason="response_callback_failed")

    def _buffer_response(self, worker_type: WorkerType, response: WorkerResponse) -> None:
        """Route a registered correlation or buffer it for later retrieval."""
        corr_id = response.correlation_id
        if not corr_id:
            self.dispose_response(response, reason="uncorrelated_drop")
            return
        dropped: list[WorkerResponse] = []
        callback: Callable[[Optional[WorkerResponse]], None] | None = None
        abandoned_reason: str | None = None
        unclaimed_stop_report = False
        with self._lock:
            abandoned_reason = self._abandoned_correlations[worker_type].pop(
                corr_id,
                None,
            )
            if abandoned_reason is None:
                callback = self._response_callbacks[worker_type].pop(corr_id, None)
                self._stop_report_correlations.discard((worker_type, corr_id))
            if abandoned_reason is None and callback is None:
                unclaimed_stop_report = (worker_type == WorkerType.VISUALIZER
                                         and corr_id.startswith(VISUALIZER_STOP_REPORT_PREFIX))
                if not unclaimed_stop_report:
                    worker_buffer = self._buffered_responses[worker_type]
                    worker_buffer.setdefault(corr_id, []).append(response)
                    buffered_count = sum(len(items) for items in worker_buffer.values())
                    while buffered_count > self.MAX_BUFFERED_RESPONSES and worker_buffer:
                        oldest_id = next(iter(worker_buffer))
                        oldest_queue = worker_buffer[oldest_id]
                        dropped.append(oldest_queue.pop(0))
                        buffered_count -= 1
                        if not oldest_queue:
                            worker_buffer.pop(oldest_id, None)
                    self._response_condition.notify_all()

        if abandoned_reason is not None:
            self.dispose_response(response, reason=f"late_{abandoned_reason}")
            return
        if unclaimed_stop_report:
            self.dispose_response(response, reason='unclaimed_stop_report')
            return
        if callback is not None:
            self._invoke_response_callback(
                worker_type,
                corr_id,
                callback,
                response,
            )
        for item in dropped:
            self.dispose_response(item, reason="response_buffer_overflow")

    def _dispose_buffered_responses(
        self,
        worker_type: WorkerType,
        *,
        reason: str,
    ) -> int:
        with self._lock:
            worker_buffer = self._buffered_responses[worker_type]
            responses = [
                response
                for queue in worker_buffer.values()
                for response in queue
            ]
            worker_buffer.clear()
        for response in responses:
            self.dispose_response(response, reason=reason)
        return len(responses)

    def _drain_worker_response_queue(
        self,
        worker_type: WorkerType,
        *,
        dispose_application: bool,
        reason: str,
        max_count: int = RESPONSE_QUEUE_SIZE * 2,
    ) -> int:
        """Drain queue items without ever dropping payload-owned resources."""
        with self._lock:
            response_queue = self._response_queues.get(worker_type)
        if response_queue is None:
            return 0

        drained = 0
        for _ in range(max(0, int(max_count))):
            try:
                data = response_queue.get_nowait()
                response = self._response_from_data(data)
            except QueueEmpty:
                break
            except Exception as e:
                logger.debug("[WORKER] Error draining response queue: %s", e)
                break

            drained += 1
            if self._process_internal_response(worker_type, response):
                continue
            if self._dispose_if_abandoned(worker_type, response):
                continue
            if dispose_application:
                with self._lock:
                    retained = (worker_type, response.correlation_id) in self._stop_report_correlations
                if retained:
                    self._buffer_response(worker_type, response)
                else:
                    self.dispose_response(response, reason=reason)
            else:
                self._buffer_response(worker_type, response)
        return drained

    def _pop_buffered_response(
        self,
        worker_type: WorkerType,
        correlation_id: str,
    ) -> Optional[WorkerResponse]:
        """Pop one buffered response for a specific correlation id."""
        with self._lock:
            worker_buffer = self._buffered_responses[worker_type]
            queue = worker_buffer.get(correlation_id)
            if not queue:
                return None
            response = queue.pop(0)
            if not queue:
                worker_buffer.pop(correlation_id, None)
            return response

    def _pop_buffered_responses(
        self,
        worker_type: WorkerType,
        max_count: int,
    ) -> list[WorkerResponse]:
        """Pop buffered responses in FIFO correlation order for polling callers."""
        responses: list[WorkerResponse] = []
        with self._lock:
            worker_buffer = self._buffered_responses[worker_type]
            for corr_id in list(worker_buffer.keys()):
                queue = worker_buffer.get(corr_id)
                while queue and len(responses) < max_count:
                    responses.append(queue.pop(0))
                if not queue:
                    worker_buffer.pop(corr_id, None)
                if len(responses) >= max_count:
                    break
        return responses
    
    def _apply_worker_process_priority(
        self,
        worker_type: WorkerType,
        pid: int | None,
    ) -> None:
        """Make speculative derivative work lower-criticality at the OS scheduler.

        Process isolation removes Python-GIL sharing with the main runtime.  This
        best-effort priority reduction additionally prevents the speculative child
        from competing as an equal peer with the foreground image worker and Qt
        process.  Failure to tune priority is observable but not a startup veto.
        """
        if worker_type != WorkerType.IMAGE_PREFETCH or not pid:
            return
        try:
            import os
            import psutil

            process = psutil.Process(int(pid))
            if os.name == "nt":
                process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                priority_label = "below_normal"
            else:
                current = int(process.nice())
                target = max(current, 10)
                process.nice(target)
                priority_label = f"nice={target}"
            logger.info(
                "Applied speculative image worker process priority pid=%d priority=%s",
                pid,
                priority_label,
            )
        except Exception as e:
            logger.warning(
                "Unable to lower speculative image worker process priority pid=%s: %s",
                pid,
                e,
            )

    def _is_worker_enabled(self, worker_type: WorkerType) -> bool:
        """Check if worker is enabled in settings."""
        if not self._settings_manager:
            return True  # Default to enabled if no settings
        if worker_type == WorkerType.VISUALIZER:
            # The engine worker has no Settings switch of its own: the Visualizer's own enable decides whether an
            # owner exists, and its process path (``experiment_flags.visualizer_engine_worker_admitted``: the worker
            # by default) whether that owner starts this worker (native core P2b, work order 5).
            return True

        key = (
            "workers.image.enabled"
            if worker_type == WorkerType.IMAGE_PREFETCH
            else f"workers.{worker_type.value}.enabled"
        )
        try:
            return bool(self._settings_manager.get(key))
        except Exception as e:
            logger.debug("[WORKER] Exception suppressed: %s", e)
            # Defensive recovery still resolves through canonical product state.
            return bool(require_canonical_default(key))
    
    def _cleanup_worker(self, worker_type: WorkerType) -> None:
        """Clean up worker resources (must hold lock)."""
        self._drain_worker_response_queue(
            worker_type,
            dispose_application=True,
            reason="worker_cleanup_queue",
        )
        self._dispose_buffered_responses(
            worker_type,
            reason="worker_cleanup_buffer",
        )
        # Only detached STOP log callbacks can remain after listener shutdown.
        # Cleanup is the final bound, including death/forced termination/no ACK.
        for correlation, callback in self._take_response_callbacks_locked(worker_type):
            self._invoke_response_callback(worker_type, correlation, callback, None,
                                           cancellation_reason='worker_stopped_without_report')

        process = self._workers.pop(worker_type, None)
        if process is not None:
            try:
                process.close()
            except Exception as e:
                logger.debug("[WORKER] Exception suppressed: %s", e)
        
        # Close queues
        for queue_dict in [self._request_queues, self._response_queues]:
            queue = queue_dict.pop(worker_type, None)
            if queue:
                try:
                    queue.cancel_join_thread()
                except Exception as e:
                    logger.debug("[WORKER] Exception suppressed: %s", e)
                try:
                    queue.close()
                except Exception as e:
                    logger.debug("[WORKER] Exception suppressed: %s", e)
                try:
                    queue.join_thread()
                except Exception as e:
                    logger.debug("[WORKER] Exception suppressed: %s", e)
        
        self._health[worker_type].state = WorkerState.STOPPED
        self._health[worker_type].pid = None
        self._abandoned_correlations[worker_type].clear()
        self._broadcast_health(worker_type)
    
    def _ensure_heartbeat_monitoring(self) -> None:
        """Start heartbeat monitoring if not already running.

        POLICY EXEMPTION: uses a plain ``threading.Thread`` because this is
        core process infrastructure that operates independently of Qt.
        ThreadManager requires QCoreApplication which may not be available
        in all contexts where ProcessSupervisor operates. It is one thread for
        the supervisor's lifetime, never one per tick (R-97).
        """
        if self._heartbeat_thread is None and not self._shutdown:
            thread = threading.Thread(
                target=self._heartbeat_loop,
                name="srpss-worker-heartbeat",
                daemon=True,
            )
            self._heartbeat_thread = thread
            thread.start()

    def _heartbeat_loop(self) -> None:
        """Check workers every interval until shutdown; first check after one interval."""
        while not self._heartbeat_stop.wait(self._heartbeat_interval_s):
            if self._shutdown:
                return
            self._heartbeat_check()
    
    def _heartbeat_check(self) -> None:
        """Check heartbeat status of all running workers."""
        if self._shutdown:
            return
        
        workers_to_restart = []
        
        # First, poll ALL worker response queues to process any pending HEARTBEAT_ACKs
        # This is CRITICAL - without this, heartbeat responses are never processed
        # and workers get restarted unnecessarily
        with self._lock:
            # A role being started or stopped is owned by that transition; the
            # monitor must neither drain its queue nor judge its heartbeat.
            worker_types = [wt for wt in self._workers if wt not in self._transitioning]
        
        for worker_type in worker_types:
            # Poll responses to process HEARTBEAT_ACK messages
            with self._lock:
                listener_active = self._response_listener_active_locked(worker_type)
            if not listener_active:
                self._drain_worker_response_queue(
                    worker_type,
                    dispose_application=False,
                    reason="heartbeat_drain",
                    max_count=20,
                )
        
        with self._lock:
            for worker_type, process in list(self._workers.items()):
                if worker_type in self._transitioning:
                    continue
                if process_has_exited(process):
                    logger.warning(
                        "%s worker process died unexpectedly",
                        worker_type.value,
                    )
                    self._health[worker_type].state = WorkerState.ERROR
                    self._health[worker_type].error_message = "Process died"
                    workers_to_restart.append((worker_type, process))
                    continue
                
                # Send heartbeat
                self.send_message(
                    worker_type,
                    MessageType.HEARTBEAT,
                    {"timestamp": time.time()},
                )
                
                # Check for missed heartbeats
                health = self._health[worker_type]
                time_since_heartbeat = time.time() - health.last_heartbeat
                if time_since_heartbeat > self._heartbeat_interval_s * 2:
                    health.record_missed_heartbeat()
                    if is_perf_metrics_enabled():
                        logger.warning(
                            "[PERF] [WORKER] %s missed heartbeat (%d consecutive)",
                            worker_type.value,
                            health.missed_heartbeats,
                        )
                    
                    if worker_type in self.CLIENT_RESTARTED_ROLES:
                        # Retired, never restarted: no restart limit applies to a retirement.
                        if health.missed_heartbeats >= HealthStatus.MISSED_HEARTBEAT_THRESHOLD:
                            workers_to_restart.append((worker_type, process))
                    elif health.should_restart():
                        workers_to_restart.append((worker_type, process))

        # Act on the processes judged above (outside lock), each fenced by its identity: a role restarted or replaced
        # meanwhile is left alone. A client-restarted role is only retired (``CLIENT_RESTARTED_ROLES``).
        for worker_type, process in workers_to_restart:
            try:
                if worker_type in self.CLIENT_RESTARTED_ROLES:
                    self._retire_judged_process(worker_type, process)
                else:
                    self.restart(worker_type, judged=process)
            except Exception as e:
                logger.exception("Failed to restart %s worker: %s", worker_type.value, e)
    
    def _broadcast_health(self, worker_type: WorkerType) -> None:
        """Broadcast health status change via EventSystem."""
        if not self._event_system:
            return
        
        try:
            health = self._health[worker_type]
            self._event_system.publish(
                "worker.health_changed",
                data={
                    "worker_type": worker_type.value,
                    "state": health.state.name,
                    "is_healthy": health.is_healthy(),
                    "pid": health.pid,
                },
                source=self,
            )
        except Exception as e:
            logger.debug("Failed to broadcast health: %s", e)

"""
Process Supervisor for worker process management.

Manages lifecycle of worker processes including:
- Starting/stopping/restarting workers
- Health monitoring via heartbeat
- Exponential backoff restart policy
- Graceful shutdown integration with ResourceManager
"""
from __future__ import annotations

import multiprocessing as mp
import threading
import time
import uuid
from multiprocessing import Queue
from typing import Any, Callable, Dict, Optional

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.process.types import (
    HealthStatus,
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerState,
    WorkerType,
)

logger = get_logger(__name__)

# Type alias for response callbacks
ResponseCallback = Callable[[WorkerResponse], None]


class ProcessSupervisor:
    """
    Supervisor for managing worker processes.
    
    Provides:
    - Worker lifecycle management (start/stop/restart)
    - Health monitoring with heartbeat
    - Exponential backoff restart policy
    - Non-blocking message passing
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
    POLL_TIMEOUT_MS = 10       # Non-blocking poll timeout
    
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
        self._lock = threading.RLock()
        self._shutdown = False
        self._initialized = False
        
        self._resource_manager = resource_manager
        self._settings_manager = settings_manager
        self._event_system = event_system
        
        # Worker tracking
        self._workers: Dict[WorkerType, mp.Process] = {}
        self._health: Dict[WorkerType, HealthStatus] = {}
        self._request_queues: Dict[WorkerType, Queue] = {}
        self._response_queues: Dict[WorkerType, Queue] = {}
        self._worker_factories: Dict[WorkerType, Callable] = {}
        
        # Sequence tracking per worker type
        self._seq_counters: Dict[WorkerType, int] = {wt: 0 for wt in WorkerType}
        
        # Heartbeat monitoring
        self._heartbeat_timer: Optional[threading.Timer] = None
        self._heartbeat_interval_s = HealthStatus.HEARTBEAT_INTERVAL_MS / 1000.0
        
        # Async response handling - callbacks keyed by correlation_id
        self._response_callbacks: Dict[str, ResponseCallback] = {}
        self._response_listener_thread: Optional[threading.Thread] = None
        self._response_listener_running = False
        
        # Initialize health status for all worker types
        for wt in WorkerType:
            self._health[wt] = HealthStatus(
                worker_type=wt,
                state=WorkerState.STOPPED,
            )
        
        self._initialized = True
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
        
        with self._lock:
            # Check if already running
            if worker_type in self._workers and self._workers[worker_type].is_alive():
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
                self._request_queues[worker_type] = Queue(self.REQUEST_QUEUE_SIZE)
                self._response_queues[worker_type] = Queue(self.RESPONSE_QUEUE_SIZE)
                
                # Update health state
                self._health[worker_type].state = WorkerState.STARTING
                
                # Create and start process
                factory = self._worker_factories[worker_type]
                process = mp.Process(
                    target=factory,
                    args=(
                        self._request_queues[worker_type],
                        self._response_queues[worker_type],
                    ),
                    name=f"SRPSS_{worker_type.value}_worker",
                    daemon=True,  # Die with parent
                )
                process.start()
                
                self._workers[worker_type] = process
                self._health[worker_type].pid = process.pid
                self._health[worker_type].state = WorkerState.RUNNING
                self._health[worker_type].record_heartbeat()
                
                logger.info(
                    "Started %s worker (PID: %d)",
                    worker_type.value,
                    process.pid,
                )
                
                # Start heartbeat monitoring if not already running
                self._ensure_heartbeat_monitoring()
                
                # Broadcast health update
                self._broadcast_health(worker_type)
                
                return True
                
            except Exception as e:
                logger.exception("Failed to start %s worker: %s", worker_type.value, e)
                self._health[worker_type].state = WorkerState.ERROR
                self._health[worker_type].error_message = str(e)
                self._broadcast_health(worker_type)
                return False
    
    def stop(self, worker_type: WorkerType, timeout: float = 5.0) -> bool:
        """
        Stop a worker process gracefully.
        
        Args:
            worker_type: Type of worker to stop
            timeout: Seconds to wait for graceful shutdown
            
        Returns:
            True if worker stopped successfully
        """
        with self._lock:
            if worker_type not in self._workers:
                return True
            
            process = self._workers[worker_type]
            if not process.is_alive():
                self._cleanup_worker(worker_type)
                return True
            
            self._health[worker_type].state = WorkerState.STOPPING
            
            try:
                # Send shutdown message
                shutdown_msg = WorkerMessage(
                    msg_type=MessageType.SHUTDOWN,
                    seq_no=self._next_seq(worker_type),
                    correlation_id=str(uuid.uuid4()),
                    worker_type=worker_type,
                )
                
                req_queue = self._request_queues.get(worker_type)
                if req_queue:
                    try:
                        req_queue.put_nowait(shutdown_msg.to_dict())
                    except Exception:
                        pass
                
                # Wait for graceful shutdown
                process.join(timeout=timeout)
                
                if process.is_alive():
                    logger.warning(
                        "%s worker did not stop gracefully, terminating",
                        worker_type.value,
                    )
                    process.terminate()
                    process.join(timeout=1.0)
                    
                    if process.is_alive():
                        logger.error(
                            "%s worker did not terminate, killing",
                            worker_type.value,
                        )
                        process.kill()
                
                self._cleanup_worker(worker_type)
                logger.info("Stopped %s worker", worker_type.value)
                return True
                
            except Exception as e:
                logger.exception("Error stopping %s worker: %s", worker_type.value, e)
                self._cleanup_worker(worker_type)
                return False
    
    def restart(self, worker_type: WorkerType) -> bool:
        """
        Restart a worker process with backoff.
        
        Args:
            worker_type: Type of worker to restart
            
        Returns:
            True if worker restarted successfully
        """
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
    
    def send_message(
        self,
        worker_type: WorkerType,
        msg_type: MessageType,
        payload: Dict[str, Any],
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
            if worker_type not in self._workers:
                return None
            
            if not self._workers[worker_type].is_alive():
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
        
        with self._lock:
            resp_queue = self._response_queues.get(worker_type)
            if not resp_queue:
                return responses
        
        # Poll outside lock to avoid blocking
        for _ in range(max_count):
            try:
                data = resp_queue.get_nowait()
                response = WorkerResponse.from_dict(data)
                responses.append(response)
                
                # Handle heartbeat acks
                if response.msg_type == MessageType.HEARTBEAT_ACK:
                    with self._lock:
                        self._health[worker_type].record_heartbeat()
                
                # Handle worker busy/idle state changes
                elif response.msg_type == MessageType.WORKER_BUSY:
                    with self._lock:
                        self._health[worker_type].set_busy(True)
                        if is_perf_metrics_enabled():
                            logger.debug(
                                "[PERF] [WORKER] %s marked as BUSY",
                                worker_type.value,
                            )
                
                elif response.msg_type == MessageType.WORKER_IDLE:
                    with self._lock:
                        self._health[worker_type].set_busy(False)
                        self._health[worker_type].record_heartbeat()  # Reset heartbeat on idle
                        
            except Exception:
                break
        
        return responses
    
    def is_running(self, worker_type: WorkerType) -> bool:
        """Check if a worker is currently running.
        
        Args:
            worker_type: Type of worker to check
            
        Returns:
            True if worker process is alive and running
        """
        with self._lock:
            if worker_type not in self._workers:
                return False
            return self._workers[worker_type].is_alive()
    
    def get_health(self, worker_type: WorkerType) -> HealthStatus:
        """Get health status for a worker."""
        with self._lock:
            return self._health.get(worker_type, HealthStatus(
                worker_type=worker_type,
                state=WorkerState.STOPPED,
            ))
    
    def get_all_health(self) -> Dict[WorkerType, HealthStatus]:
        """Get health status for all workers."""
        with self._lock:
            return {wt: self._health[wt] for wt in WorkerType}
    
    def register_response_callback(
        self,
        correlation_id: str,
        callback: ResponseCallback,
        timeout_ms: int = 5000,
    ) -> None:
        """
        Register a callback for async response handling.
        
        The callback will be invoked from the response listener thread
        when a response with the matching correlation_id is received.
        Callbacks are automatically removed after invocation or timeout.
        
        Args:
            correlation_id: The correlation ID to match
            callback: Function to call with the WorkerResponse
            timeout_ms: Timeout after which callback is removed (default 5s)
        """
        with self._lock:
            self._response_callbacks[correlation_id] = callback
            
            # Start response listener if not running
            self._ensure_response_listener()
            
            # Schedule timeout cleanup
            def _timeout_cleanup():
                with self._lock:
                    if correlation_id in self._response_callbacks:
                        del self._response_callbacks[correlation_id]
                        if is_perf_metrics_enabled():
                            logger.debug(
                                "[PERF] [WORKER] Response callback timeout: %s",
                                correlation_id[:8],
                            )
            
            timer = threading.Timer(timeout_ms / 1000.0, _timeout_cleanup)
            timer.daemon = True
            timer.start()
    
    def send_message_async(
        self,
        worker_type: WorkerType,
        msg_type: MessageType,
        payload: Dict[str, Any],
        callback: ResponseCallback,
        timeout_ms: int = 5000,
    ) -> Optional[str]:
        """
        Send a message and register a callback for the response.
        
        This is the preferred method for non-blocking worker communication.
        The callback will be invoked from a background thread when the
        response arrives.
        
        Args:
            worker_type: Target worker type
            msg_type: Message type
            payload: Message payload
            callback: Function to call with the response
            timeout_ms: Timeout for response
            
        Returns:
            Correlation ID if sent, None if failed
        """
        correlation_id = self.send_message(worker_type, msg_type, payload)
        if correlation_id:
            self.register_response_callback(correlation_id, callback, timeout_ms)
        return correlation_id
    
    def _ensure_response_listener(self) -> None:
        """Start response listener thread if not already running.
        
        NOTE: The response listener is DISABLED for now because it conflicts
        with the existing poll_responses() pattern used by _load_image_via_worker.
        The async callback system (send_message_async) is available but not
        recommended until the image loading is refactored to use callbacks.
        """
        # DISABLED: Response listener conflicts with poll_responses()
        # The listener drains the queue, preventing poll_responses from seeing responses
        # TODO: Refactor image loading to use send_message_async callbacks
        return
        
        if self._response_listener_running or self._shutdown:
            return
        
        self._response_listener_running = True
        self._response_listener_thread = threading.Thread(
            target=self._response_listener_loop,
            name="SRPSS_ResponseListener",
            daemon=True,
        )
        self._response_listener_thread.start()
        logger.debug("Response listener thread started")
    
    def _response_listener_loop(self) -> None:
        """Background thread that polls response queues ONLY for registered callbacks.
        
        IMPORTANT: This thread only processes responses that have registered callbacks.
        Responses without callbacks are left in the queue for poll_responses() to handle.
        This prevents the listener from consuming responses meant for synchronous polling.
        """
        while not self._shutdown and self._response_listener_running:
            try:
                # Only run if there are pending callbacks
                with self._lock:
                    if not self._response_callbacks:
                        time.sleep(0.01)  # Sleep longer when no callbacks
                        continue
                    pending_ids = set(self._response_callbacks.keys())
                
                # Poll all worker response queues
                for worker_type in WorkerType:
                    with self._lock:
                        resp_queue = self._response_queues.get(worker_type)
                        if not resp_queue:
                            continue
                    
                    # Peek and selectively consume responses
                    try:
                        # Collect responses to process
                        responses_to_process = []
                        responses_to_requeue = []
                        
                        # Drain queue
                        while True:
                            try:
                                data = resp_queue.get_nowait()
                            except Exception:
                                break
                            
                            response = WorkerResponse.from_dict(data)
                            
                            # Handle internal messages (always consume)
                            if response.msg_type == MessageType.HEARTBEAT_ACK:
                                with self._lock:
                                    self._health[worker_type].record_heartbeat()
                                continue
                            
                            if response.msg_type == MessageType.WORKER_BUSY:
                                with self._lock:
                                    self._health[worker_type].set_busy(True)
                                continue
                            
                            if response.msg_type == MessageType.WORKER_IDLE:
                                with self._lock:
                                    self._health[worker_type].set_busy(False)
                                    self._health[worker_type].record_heartbeat()
                                continue
                            
                            # Check if this response has a registered callback
                            if response.correlation_id in pending_ids:
                                responses_to_process.append(response)
                            else:
                                # Requeue for poll_responses() to handle
                                responses_to_requeue.append(data)
                        
                        # Requeue responses without callbacks
                        for data in responses_to_requeue:
                            try:
                                resp_queue.put_nowait(data)
                            except Exception:
                                pass  # Queue full - drop
                        
                        # Process responses with callbacks
                        for response in responses_to_process:
                            callback = None
                            with self._lock:
                                callback = self._response_callbacks.pop(
                                    response.correlation_id, None
                                )
                            
                            if callback:
                                try:
                                    callback(response)
                                except Exception as e:
                                    logger.error(
                                        "Response callback error: %s", e
                                    )
                    except Exception as e:
                        logger.debug("Response poll error for %s: %s", worker_type.value, e)
                
                # Brief sleep to avoid busy-waiting (1ms)
                time.sleep(0.001)
                
            except Exception as e:
                logger.error("Response listener error: %s", e)
                time.sleep(0.01)
        
        logger.debug("Response listener thread stopped")
    
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
        
        # Stop response listener
        self._response_listener_running = False
        if self._response_listener_thread and self._response_listener_thread.is_alive():
            self._response_listener_thread.join(timeout=1.0)
        
        # Stop heartbeat monitoring
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None
        
        # Clear pending callbacks
        with self._lock:
            self._response_callbacks.clear()
        
        # Stop all workers
        per_worker_timeout = timeout / max(len(self._workers), 1)
        for worker_type in list(self._workers.keys()):
            try:
                self.stop(worker_type, timeout=per_worker_timeout)
            except Exception as e:
                logger.error("Error stopping %s worker: %s", worker_type.value, e)
        
        logger.info("ProcessSupervisor shutdown complete")
    
    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------
    
    def _next_seq(self, worker_type: WorkerType) -> int:
        """Get next sequence number for worker (must hold lock)."""
        self._seq_counters[worker_type] += 1
        return self._seq_counters[worker_type]
    
    def _is_worker_enabled(self, worker_type: WorkerType) -> bool:
        """Check if worker is enabled in settings."""
        if not self._settings_manager:
            return True  # Default to enabled if no settings
        
        key = f"workers.{worker_type.value}.enabled"
        try:
            return self._settings_manager.get(key, True)
        except Exception:
            return True
    
    def _cleanup_worker(self, worker_type: WorkerType) -> None:
        """Clean up worker resources (must hold lock)."""
        self._workers.pop(worker_type, None)
        
        # Close queues
        for queue_dict in [self._request_queues, self._response_queues]:
            queue = queue_dict.pop(worker_type, None)
            if queue:
                try:
                    queue.close()
                    queue.join_thread()
                except Exception:
                    pass
        
        self._health[worker_type].state = WorkerState.STOPPED
        self._health[worker_type].pid = None
        self._broadcast_health(worker_type)
    
    def _ensure_heartbeat_monitoring(self) -> None:
        """Start heartbeat monitoring if not already running."""
        if self._heartbeat_timer is None and not self._shutdown:
            self._heartbeat_timer = threading.Timer(
                self._heartbeat_interval_s,
                self._heartbeat_check,
            )
            self._heartbeat_timer.daemon = True
            self._heartbeat_timer.start()
    
    def _heartbeat_check(self) -> None:
        """Check heartbeat status of all running workers."""
        if self._shutdown:
            return
        
        workers_to_restart = []
        
        with self._lock:
            for worker_type, process in list(self._workers.items()):
                if not process.is_alive():
                    logger.warning(
                        "%s worker process died unexpectedly",
                        worker_type.value,
                    )
                    self._health[worker_type].state = WorkerState.ERROR
                    self._health[worker_type].error_message = "Process died"
                    workers_to_restart.append(worker_type)
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
                    
                    if health.should_restart():
                        workers_to_restart.append(worker_type)
        
        # Restart unhealthy workers (outside lock)
        for worker_type in workers_to_restart:
            try:
                self.restart(worker_type)
            except Exception as e:
                logger.exception("Failed to restart %s worker: %s", worker_type.value, e)
        
        # Schedule next check
        if not self._shutdown:
            self._heartbeat_timer = threading.Timer(
                self._heartbeat_interval_s,
                self._heartbeat_check,
            )
            self._heartbeat_timer.daemon = True
            self._heartbeat_timer.start()
    
    def _broadcast_health(self, worker_type: WorkerType) -> None:
        """Broadcast health status change via EventSystem."""
        if not self._event_system:
            return
        
        try:
            health = self._health[worker_type]
            self._event_system.publish(
                "worker.health_changed",
                worker_type=worker_type.value,
                state=health.state.name,
                is_healthy=health.is_healthy(),
                pid=health.pid,
            )
        except Exception as e:
            logger.debug("Failed to broadcast health: %s", e)

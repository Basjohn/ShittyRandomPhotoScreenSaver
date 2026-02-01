"""
Base worker class for process isolation.

Provides common functionality for all workers:
- Message loop with heartbeat handling
- Graceful shutdown
- Error reporting
- Logging setup for worker processes
"""
from __future__ import annotations

import logging
import os
import time
from multiprocessing import Queue
from typing import Optional

from core.process.types import (
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerType,
)
from core.logging.logger import get_log_dir, is_perf_metrics_enabled


def setup_worker_logging(worker_type: WorkerType) -> logging.Logger:
    """
    Set up logging for a worker process.
    
    Workers can't use the main process logger, so we set up
    a basic file logger for debugging.
    """
    logger = logging.getLogger(f"worker.{worker_type.value}")
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if run() is invoked multiple times.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    if not is_perf_metrics_enabled():
        # Suppress worker logs entirely unless perf metrics are enabled.
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    log_dir = get_log_dir()
    os.makedirs(log_dir, exist_ok=True)

    log_file = log_dir / f"worker_{worker_type.value}.log"
    handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger


class BaseWorker:
    """
    Base class for worker processes.
    
    Subclasses must implement:
    - worker_type: WorkerType property
    - handle_message(msg): Process a message and return response
    """
    
    POLL_TIMEOUT_S = 0.1  # 100ms poll timeout
    HEARTBEAT_RESPONSE_TIMEOUT_S = 0.5  # Max time to prepare heartbeat response
    
    def __init__(
        self,
        request_queue: Queue,
        response_queue: Queue,
    ):
        """
        Initialize the base worker.
        
        Args:
            request_queue: Queue for receiving requests from UI process
            response_queue: Queue for sending responses to UI process
        """
        self._request_queue = request_queue
        self._response_queue = response_queue
        self._shutdown = False
        self._logger: Optional[logging.Logger] = None
        self._seq_counter = 0
        self._start_time = time.time()
        self._messages_processed = 0
    
    @property
    def worker_type(self) -> WorkerType:
        """Override in subclass to return worker type."""
        raise NotImplementedError("Subclass must define worker_type")
    
    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        """
        Handle a message and return a response.
        
        Override in subclass to implement message handling.
        
        Args:
            msg: The message to handle
            
        Returns:
            Response to send back, or None for no response
        """
        raise NotImplementedError("Subclass must implement handle_message")
    
    def run(self) -> None:
        """
        Main worker loop.
        
        Polls for messages, handles them, and sends responses.
        Continues until shutdown message received.
        """
        from queue import Empty as QueueEmpty
        
        self._logger = setup_worker_logging(self.worker_type)
        self._logger.info(
            "Worker %s started (PID: %d)",
            self.worker_type.value,
            os.getpid(),
        )
        
        try:
            while not self._shutdown:
                try:
                    # Use blocking get with timeout instead of polling loop
                    # This avoids race condition between empty() check and get_nowait()
                    try:
                        msg_data = self._request_queue.get(timeout=self.POLL_TIMEOUT_S)
                    except QueueEmpty:
                        # Normal - no messages, continue polling
                        continue
                    
                    # Parse message
                    try:
                        msg = WorkerMessage.from_dict(msg_data)
                    except Exception as e:
                        self._logger.error("Failed to parse message: %s", e)
                        continue
                    
                    # Handle special messages
                    if msg.msg_type == MessageType.SHUTDOWN:
                        self._logger.info("Received shutdown message")
                        self._shutdown = True
                        self._send_response(WorkerResponse(
                            msg_type=MessageType.SHUTDOWN,
                            seq_no=msg.seq_no,
                            correlation_id=msg.correlation_id,
                            success=True,
                        ))
                        break
                    
                    if msg.msg_type == MessageType.HEARTBEAT:
                        self._handle_heartbeat(msg)
                        continue
                    
                    # Handle worker-specific message
                    start_time = time.time()
                    try:
                        response = self.handle_message(msg)
                        if response:
                            response.processing_time_ms = (time.time() - start_time) * 1000
                            self._send_response(response)
                        self._messages_processed += 1
                    except Exception as e:
                        self._logger.exception("Error handling message: %s", e)
                        self._send_response(WorkerResponse(
                            msg_type=MessageType.ERROR,
                            seq_no=msg.seq_no,
                            correlation_id=msg.correlation_id,
                            success=False,
                            error=str(e),
                            processing_time_ms=(time.time() - start_time) * 1000,
                        ))
                        
                except Exception as e:
                    self._logger.exception("Error in worker loop: %s", e)
                    time.sleep(self.POLL_TIMEOUT_S)
                    
        except KeyboardInterrupt:
            self._logger.info("Worker interrupted")
        finally:
            self._cleanup()
            self._logger.info(
                "Worker %s stopped (processed %d messages in %.1fs)",
                self.worker_type.value,
                self._messages_processed,
                time.time() - self._start_time,
            )
    
    def _handle_heartbeat(self, msg: WorkerMessage) -> None:
        """Handle heartbeat message."""
        self._send_response(WorkerResponse(
            msg_type=MessageType.HEARTBEAT_ACK,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=True,
            payload={
                "uptime_s": time.time() - self._start_time,
                "messages_processed": self._messages_processed,
                "pid": os.getpid(),
            },
        ))
    
    def _send_response(self, response: WorkerResponse) -> None:
        """Send a response to the UI process."""
        try:
            self._response_queue.put_nowait(response.to_dict())
        except Exception as e:
            if self._logger:
                self._logger.error("Failed to send response: %s", e)
    
    def _send_busy_notification(self, correlation_id: str) -> None:
        """Send WORKER_BUSY notification to prevent heartbeat timeout during long operations."""
        self._send_response(WorkerResponse(
            msg_type=MessageType.WORKER_BUSY,
            seq_no=self._next_seq(),
            correlation_id=correlation_id,
            success=True,
            payload={"worker_type": self.worker_type.value},
        ))
    
    def _send_idle_notification(self, correlation_id: str) -> None:
        """Send WORKER_IDLE notification after completing a long operation."""
        self._send_response(WorkerResponse(
            msg_type=MessageType.WORKER_IDLE,
            seq_no=self._next_seq(),
            correlation_id=correlation_id,
            success=True,
            payload={"worker_type": self.worker_type.value},
        ))
    
    def _cleanup(self) -> None:
        """
        Clean up resources before shutdown.
        
        Override in subclass for worker-specific cleanup.
        """
        pass
    
    def _next_seq(self) -> int:
        """Get next sequence number."""
        self._seq_counter += 1
        return self._seq_counter

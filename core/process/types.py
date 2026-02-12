"""
Type definitions for process isolation module.

Defines worker types, message schemas, shared memory headers,
and health status structures for multiprocessing communication.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional

from core.constants.timing import (
    WORKER_HEARTBEAT_INTERVAL_MS,
    RETRY_BASE_DELAY_MS,
    RETRY_MAX_DELAY_MS,
)


class WorkerType(Enum):
    """Types of worker processes."""
    IMAGE = "image"           # decode/prescale with path|scaled:WxH cache keys
    RSS = "rss"               # fetch/parse/mirror with validated ImageMetadata
    FFT = "fft"               # loopback ingest + smoothing + ghost envelopes
    TRANSITION = "transition" # CPU precompute payloads


class WorkerState(Enum):
    """Worker process lifecycle states."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()
    RESTARTING = auto()


class MessageType(Enum):
    """Types of messages sent between UI and workers."""
    # Control messages
    SHUTDOWN = "shutdown"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    CONFIG_UPDATE = "config_update"
    WORKER_READY = "worker_ready"     # Worker message loop started, ready for messages
    WORKER_BUSY = "worker_busy"       # Worker is busy with long operation
    WORKER_IDLE = "worker_idle"       # Worker finished long operation
    
    # Image worker messages
    IMAGE_DECODE = "image_decode"
    IMAGE_PRESCALE = "image_prescale"
    IMAGE_RESULT = "image_result"
    
    # RSS worker messages
    RSS_FETCH = "rss_fetch"
    RSS_REFRESH = "rss_refresh"
    RSS_RESULT = "rss_result"
    
    # FFT worker messages
    FFT_FRAME = "fft_frame"
    FFT_BARS = "fft_bars"
    FFT_CONFIG = "fft_config"
    
    # Transition worker messages
    TRANSITION_PRECOMPUTE = "transition_precompute"
    TRANSITION_RESULT = "transition_result"
    
    # Error messages
    ERROR = "error"


@dataclass
class WorkerMessage:
    """
    Immutable message sent to a worker process.
    
    All messages include common tracking fields for correlation
    and latency measurement. Payloads must be picklable and
    must not contain Qt objects.
    """
    msg_type: MessageType
    seq_no: int
    correlation_id: str
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    worker_type: Optional[WorkerType] = None
    
    # Size caps per channel (bytes)
    MAX_IMAGE_PAYLOAD = 50 * 1024 * 1024   # 50MB for large images
    MAX_RSS_PAYLOAD = 1 * 1024 * 1024      # 1MB for RSS data
    MAX_FFT_PAYLOAD = 64 * 1024            # 64KB for FFT frames
    MAX_TRANSITION_PAYLOAD = 1 * 1024 * 1024  # 1MB for transition data
    
    def validate_size(self) -> bool:
        """Validate payload size against channel limits."""
        import sys
        payload_size = sys.getsizeof(self.payload)
        
        limits = {
            WorkerType.IMAGE: self.MAX_IMAGE_PAYLOAD,
            WorkerType.RSS: self.MAX_RSS_PAYLOAD,
            WorkerType.FFT: self.MAX_FFT_PAYLOAD,
            WorkerType.TRANSITION: self.MAX_TRANSITION_PAYLOAD,
        }
        
        if self.worker_type and self.worker_type in limits:
            return payload_size <= limits[self.worker_type]
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary."""
        return {
            "msg_type": self.msg_type.value,
            "seq_no": self.seq_no,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "worker_type": self.worker_type.value if self.worker_type else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerMessage":
        """Deserialize message from dictionary."""
        return cls(
            msg_type=MessageType(data["msg_type"]),
            seq_no=data["seq_no"],
            correlation_id=data["correlation_id"],
            timestamp=data.get("timestamp", time.time()),
            payload=data.get("payload", {}),
            worker_type=WorkerType(data["worker_type"]) if data.get("worker_type") else None,
        )


@dataclass
class WorkerResponse:
    """
    Response from a worker process.
    
    Includes success/error status, timing information,
    and optional shared memory handle for large results.
    """
    msg_type: MessageType
    seq_no: int
    correlation_id: str
    success: bool
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    error_code: Optional[int] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    shm_handle: Optional[str] = None  # Shared memory name if used
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize response to dictionary."""
        return {
            "msg_type": self.msg_type.value,
            "seq_no": self.seq_no,
            "correlation_id": self.correlation_id,
            "success": self.success,
            "timestamp": self.timestamp,
            "error": self.error,
            "error_code": self.error_code,
            "payload": self.payload,
            "shm_handle": self.shm_handle,
            "processing_time_ms": self.processing_time_ms,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerResponse":
        """Deserialize response from dictionary."""
        return cls(
            msg_type=MessageType(data["msg_type"]),
            seq_no=data["seq_no"],
            correlation_id=data["correlation_id"],
            success=data["success"],
            timestamp=data.get("timestamp", time.time()),
            error=data.get("error"),
            error_code=data.get("error_code"),
            payload=data.get("payload", {}),
            shm_handle=data.get("shm_handle"),
            processing_time_ms=data.get("processing_time_ms", 0.0),
        )


@dataclass
class SharedMemoryHeader:
    """
    Base header for shared memory buffers.
    
    Includes ownership tracking and generation counters
    for freshness detection.
    """
    handle: str                    # Shared memory name
    size_bytes: int                # Total buffer size
    producer_pid: int              # PID of producing process
    generation: int                # Monotonic counter for freshness
    timestamp: float = field(default_factory=time.time)
    valid: bool = True             # False if buffer should be discarded
    
    def to_bytes(self) -> bytes:
        """Serialize header to bytes for shared memory prefix."""
        import struct
        # Format: handle (64 bytes), size (8), pid (4), gen (4), ts (8), valid (1)
        handle_bytes = self.handle.encode('utf-8')[:64].ljust(64, b'\x00')
        return struct.pack(
            '64sQIIdB',
            handle_bytes,
            self.size_bytes,
            self.producer_pid,
            self.generation,
            self.timestamp,
            1 if self.valid else 0,
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "SharedMemoryHeader":
        """Deserialize header from bytes."""
        import struct
        handle_bytes, size, pid, gen, ts, valid = struct.unpack('64sQIIdB', data[:89])
        return cls(
            handle=handle_bytes.rstrip(b'\x00').decode('utf-8'),
            size_bytes=size,
            producer_pid=pid,
            generation=gen,
            timestamp=ts,
            valid=valid == 1,
        )
    
    HEADER_SIZE = 89  # Size in bytes


@dataclass
class RGBAHeader(SharedMemoryHeader):
    """
    Header for RGBA image data in shared memory.
    
    Extends base header with image-specific metadata.
    """
    width: int = 0
    height: int = 0
    stride: int = 0
    format: str = "RGBA8"  # RGBA8, RGB8, etc.
    
    def to_bytes(self) -> bytes:
        """Serialize RGBA header to bytes."""
        import struct
        base = super().to_bytes()
        format_bytes = self.format.encode('utf-8')[:16].ljust(16, b'\x00')
        return base + struct.pack(
            'III16s',
            self.width,
            self.height,
            self.stride,
            format_bytes,
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "RGBAHeader":
        """Deserialize RGBA header from bytes."""
        import struct
        base = SharedMemoryHeader.from_bytes(data)
        offset = SharedMemoryHeader.HEADER_SIZE
        width, height, stride, format_bytes = struct.unpack(
            'III16s', data[offset:offset + 28]
        )
        return cls(
            handle=base.handle,
            size_bytes=base.size_bytes,
            producer_pid=base.producer_pid,
            generation=base.generation,
            timestamp=base.timestamp,
            valid=base.valid,
            width=width,
            height=height,
            stride=stride,
            format=format_bytes.rstrip(b'\x00').decode('utf-8'),
        )
    
    HEADER_SIZE = SharedMemoryHeader.HEADER_SIZE + 28


@dataclass
class FFTHeader(SharedMemoryHeader):
    """
    Header for FFT data in shared memory.
    
    Extends base header with FFT-specific metadata.
    """
    bins_len: int = 0              # Number of FFT bins
    window_size: int = 0           # FFT window size
    sample_rate: int = 0           # Audio sample rate
    smoothing_tau: float = 0.0     # Smoothing time constant
    decay_rate: float = 0.0        # Decay rate for bars
    
    def to_bytes(self) -> bytes:
        """Serialize FFT header to bytes."""
        import struct
        base = super().to_bytes()
        return base + struct.pack(
            'IIIdd',
            self.bins_len,
            self.window_size,
            self.sample_rate,
            self.smoothing_tau,
            self.decay_rate,
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "FFTHeader":
        """Deserialize FFT header from bytes."""
        import struct
        base = SharedMemoryHeader.from_bytes(data)
        offset = SharedMemoryHeader.HEADER_SIZE
        bins_len, window_size, sample_rate, smoothing_tau, decay_rate = struct.unpack(
            'IIIdd', data[offset:offset + 32]
        )
        return cls(
            handle=base.handle,
            size_bytes=base.size_bytes,
            producer_pid=base.producer_pid,
            generation=base.generation,
            timestamp=base.timestamp,
            valid=base.valid,
            bins_len=bins_len,
            window_size=window_size,
            sample_rate=sample_rate,
            smoothing_tau=smoothing_tau,
            decay_rate=decay_rate,
        )
    
    HEADER_SIZE = SharedMemoryHeader.HEADER_SIZE + 32  # IIIdd with alignment padding


@dataclass
class HealthStatus:
    """
    Health status for a worker process.
    
    Used by supervisor for monitoring and restart decisions.
    """
    worker_type: WorkerType
    state: WorkerState
    pid: Optional[int] = None
    last_heartbeat: float = 0.0
    missed_heartbeats: int = 0
    restart_count: int = 0
    last_restart: float = 0.0
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    is_busy: bool = False              # Worker is processing a long operation
    busy_since: float = 0.0            # Timestamp when worker became busy
    
    # Health thresholds
    # Increased interval to 3s - workers may be busy processing for 500ms+
    HEARTBEAT_INTERVAL_MS = WORKER_HEARTBEAT_INTERVAL_MS
    MISSED_HEARTBEAT_THRESHOLD = 5     # Restart after this many misses (was 3)
    MAX_RESTARTS_PER_WINDOW = 5        # Max restarts in time window
    RESTART_WINDOW_SECONDS = 300       # 5 minute window for restart counting
    RESTART_BACKOFF_BASE_MS = RETRY_BASE_DELAY_MS
    RESTART_BACKOFF_MAX_MS = RETRY_MAX_DELAY_MS
    
    def is_healthy(self) -> bool:
        """Check if worker is considered healthy."""
        if self.state != WorkerState.RUNNING:
            return False
        # Don't count missed heartbeats while worker is busy
        if self.is_busy:
            return True
        if self.missed_heartbeats >= self.MISSED_HEARTBEAT_THRESHOLD:
            return False
        return True
    
    def should_restart(self) -> bool:
        """Check if worker should be restarted."""
        if self.state == WorkerState.ERROR:
            return self._can_restart()
        # Don't restart while worker is busy processing
        if self.is_busy:
            # But if busy for too long (>30s), something is wrong
            if time.time() - self.busy_since > 30.0:
                return self._can_restart()
            return False
        if self.missed_heartbeats >= self.MISSED_HEARTBEAT_THRESHOLD:
            return self._can_restart()
        return False
    
    def set_busy(self, busy: bool) -> None:
        """Set worker busy state."""
        self.is_busy = busy
        if busy:
            self.busy_since = time.time()
            self.missed_heartbeats = 0  # Reset on busy start
        else:
            self.busy_since = 0.0
    
    def _can_restart(self) -> bool:
        """Check if restart is allowed based on limits."""
        now = time.time()
        window_start = now - self.RESTART_WINDOW_SECONDS
        if self.last_restart > window_start:
            return self.restart_count < self.MAX_RESTARTS_PER_WINDOW
        return True
    
    def get_restart_backoff_ms(self) -> int:
        """Calculate exponential backoff for restart delay."""
        backoff = self.RESTART_BACKOFF_BASE_MS * (2 ** min(self.restart_count, 5))
        return min(backoff, self.RESTART_BACKOFF_MAX_MS)
    
    def record_heartbeat(self) -> None:
        """Record successful heartbeat."""
        self.last_heartbeat = time.time()
        self.missed_heartbeats = 0
    
    def record_missed_heartbeat(self) -> None:
        """Record missed heartbeat."""
        self.missed_heartbeats += 1
    
    def record_restart(self) -> None:
        """Record restart attempt."""
        now = time.time()
        window_start = now - self.RESTART_WINDOW_SECONDS
        if self.last_restart < window_start:
            self.restart_count = 1
        else:
            self.restart_count += 1
        self.last_restart = now
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize health status to dictionary."""
        return {
            "worker_type": self.worker_type.value,
            "state": self.state.name,
            "pid": self.pid,
            "last_heartbeat": self.last_heartbeat,
            "missed_heartbeats": self.missed_heartbeats,
            "restart_count": self.restart_count,
            "last_restart": self.last_restart,
            "error_message": self.error_message,
            "is_healthy": self.is_healthy(),
            "is_busy": self.is_busy,
            "metrics": self.metrics,
        }

"""
Process isolation module for SRPSS v2.0.

Provides multiprocessing infrastructure for offloading heavy work:
- ImageWorker: decode/prescale with shared-memory output
- RSSWorker: fetch/parse/mirror with validated metadata
- TransitionPrepWorker: CPU precompute payloads

All workers communicate via queues with immutable messages.
No Qt objects cross process boundaries.
"""
from .types import (
    WorkerType,
    WorkerState,
    MessageType,
    WorkerMessage,
    WorkerResponse,
    SharedMemoryHeader,
    RGBAHeader,
    HealthStatus,
)
from .supervisor import ProcessSupervisor

__all__ = [
    "WorkerType",
    "WorkerState", 
    "MessageType",
    "WorkerMessage",
    "WorkerResponse",
    "SharedMemoryHeader",
    "RGBAHeader",
    "HealthStatus",
    "ProcessSupervisor",
]

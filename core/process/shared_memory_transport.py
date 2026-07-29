"""Bounded ownership helpers for ImageWorker shared-memory transfers.

Windows removes a named mapping when its final open handle closes.  The image
worker therefore keeps only the currently published mapping open until the
parent proves that it has attached by setting a one-byte acknowledgement.  The
parent owns every mapping after attachment and always closes/unlinks it.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Mapping


IMAGE_SHARED_MEMORY_PREFIX = "srpss_img_"
SHARED_MEMORY_HANDOFF_VERSION = 1
SHARED_MEMORY_ACK_PENDING = 0
SHARED_MEMORY_ACK_ATTACHED = 0xA5
SHARED_MEMORY_ACK_OFFSET = 0
SHARED_MEMORY_PAYLOAD_OFFSET = 1
MAX_IMAGE_SHARED_MEMORY_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class SharedMemoryDescriptor:
    """Validated, picklable metadata for one RGBA shared-memory transfer."""

    name: str
    data_size: int
    payload_offset: int = SHARED_MEMORY_PAYLOAD_OFFSET
    ack_offset: int = SHARED_MEMORY_ACK_OFFSET
    handoff_version: int = SHARED_MEMORY_HANDOFF_VERSION

    @property
    def required_size(self) -> int:
        return self.payload_offset + self.data_size

    def payload_fields(self) -> dict[str, int | str]:
        return {
            "shared_memory_name": self.name,
            # Keep the established field while making the data-only meaning
            # explicit for the versioned handoff.
            "shared_memory_size": self.data_size,
            "shared_memory_data_size": self.data_size,
            "shared_memory_payload_offset": self.payload_offset,
            "shared_memory_ack_offset": self.ack_offset,
            "shared_memory_handoff_version": self.handoff_version,
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any] | None,
    ) -> "SharedMemoryDescriptor | None":
        if not payload:
            return None
        raw_name = payload.get("shared_memory_name")
        if not raw_name:
            return None

        name = str(raw_name)
        if not name.startswith(IMAGE_SHARED_MEMORY_PREFIX):
            raise ValueError("Unexpected image shared-memory name")

        raw_size = payload.get(
            "shared_memory_data_size",
            payload.get("shared_memory_size", 0),
        )
        data_size = int(raw_size or 0)
        if data_size <= 0 or data_size > MAX_IMAGE_SHARED_MEMORY_BYTES:
            raise ValueError(f"Invalid image shared-memory size: {data_size}")

        version = int(payload.get("shared_memory_handoff_version", 0) or 0)
        if version not in (0, SHARED_MEMORY_HANDOFF_VERSION):
            raise ValueError(f"Unsupported shared-memory handoff version: {version}")

        # Version 0 is the old no-ack layout.  It remains disposable so a
        # mixed buffered response can be reclaimed during an upgrade.
        default_offset = SHARED_MEMORY_PAYLOAD_OFFSET if version else 0
        payload_offset = int(
            payload.get("shared_memory_payload_offset", default_offset) or 0
        )
        ack_offset = int(
            payload.get("shared_memory_ack_offset", SHARED_MEMORY_ACK_OFFSET) or 0
        )
        if payload_offset < 0 or ack_offset < 0:
            raise ValueError("Negative shared-memory offsets are invalid")
        if version and (
            payload_offset != SHARED_MEMORY_PAYLOAD_OFFSET
            or ack_offset != SHARED_MEMORY_ACK_OFFSET
        ):
            raise ValueError("Invalid versioned shared-memory layout")

        return cls(
            name=name,
            data_size=data_size,
            payload_offset=payload_offset,
            ack_offset=ack_offset,
            handoff_version=version,
        )


def create_image_shared_memory(
    rgba_data: bytes,
    *,
    name: str,
) -> tuple[SharedMemory, SharedMemoryDescriptor]:
    """Create and fill one producer-owned image transfer."""
    if not name.startswith(IMAGE_SHARED_MEMORY_PREFIX):
        raise ValueError("Image shared-memory names must use the SRPSS prefix")
    data_size = len(rgba_data)
    if data_size <= 0 or data_size > MAX_IMAGE_SHARED_MEMORY_BYTES:
        raise ValueError(f"Invalid image shared-memory size: {data_size}")

    descriptor = SharedMemoryDescriptor(name=name, data_size=data_size)
    shm = SharedMemory(name=name, create=True, size=descriptor.required_size)
    try:
        shm.buf[descriptor.ack_offset] = SHARED_MEMORY_ACK_PENDING
        shm.buf[
            descriptor.payload_offset:descriptor.required_size
        ] = rgba_data
    except Exception:
        try:
            shm.unlink()
        except Exception:
            pass
        shm.close()
        raise
    return shm, descriptor


def wait_for_shared_memory_attachment(
    shm: SharedMemory,
    descriptor: SharedMemoryDescriptor,
    *,
    timeout_s: float,
    poll_interval_s: float = 0.005,
) -> bool:
    """Wait briefly for the consumer to prove it holds its own mapping."""
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    while time.monotonic() < deadline:
        try:
            if shm.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED:
                return True
        except Exception:
            return False
        time.sleep(max(0.001, float(poll_interval_s)))
    try:
        return shm.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED
    except Exception:
        return False


def close_producer_shared_memory(
    shm: SharedMemory,
    *,
    attached: bool,
) -> None:
    """Release the producer handle, reclaiming unpublished transfers."""
    if not attached:
        try:
            shm.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
    try:
        shm.close()
    except Exception:
        pass


class SharedMemoryReadLease:
    """Parent-side mapping that acknowledges, exposes, and finally releases."""

    def __init__(self, descriptor: SharedMemoryDescriptor) -> None:
        self.descriptor = descriptor
        self._shm: SharedMemory | None = None
        self._root_view: memoryview | None = None
        self._payload_view: memoryview | None = None
        self.close_failed = False
        self.unlink_failed = False

    def open(self) -> memoryview:
        try:
            self._shm = SharedMemory(name=self.descriptor.name, create=False)
            self._root_view = self._shm.buf

            # ACK only after this process owns a mapping.  The worker may now
            # close without destroying the Windows mapping beneath us.
            if self.descriptor.handoff_version:
                if self.descriptor.ack_offset >= len(self._root_view):
                    raise ValueError("Shared-memory acknowledgement offset is invalid")
                self._root_view[
                    self.descriptor.ack_offset
                ] = SHARED_MEMORY_ACK_ATTACHED

            if self.descriptor.required_size > len(self._root_view):
                raise ValueError(
                    "Shared-memory payload is smaller than its descriptor"
                )
            self._payload_view = self._root_view[
                self.descriptor.payload_offset:self.descriptor.required_size
            ]
            return self._payload_view
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        payload_view = self._payload_view
        self._payload_view = None
        if payload_view is not None:
            try:
                payload_view.release()
            except Exception:
                self.close_failed = True

        root_view = self._root_view
        self._root_view = None
        if root_view is not None:
            try:
                root_view.release()
            except Exception:
                self.close_failed = True

        shm = self._shm
        self._shm = None
        if shm is None:
            return
        try:
            shm.close()
        except Exception:
            self.close_failed = True
        try:
            shm.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            self.unlink_failed = True


def dispose_shared_memory_descriptor(
    descriptor: SharedMemoryDescriptor,
) -> tuple[bool, bool]:
    """Acknowledge and release an unconsumed transfer.

    Returns ``(opened, unlink_failed)``.  A missing mapping is already
    reclaimed and is therefore not an unlink failure.
    """
    lease = SharedMemoryReadLease(descriptor)
    opened = False
    try:
        lease.open()
        opened = True
    except FileNotFoundError:
        pass
    except Exception:
        pass
    finally:
        lease.close()
    return opened, lease.unlink_failed


def dispose_malformed_shared_memory_payload(
    payload: Mapping[str, Any] | None,
) -> tuple[SharedMemoryDescriptor | None, bool]:
    """Best-effort reclaim for an invalid descriptor from our image worker.

    Only the exact worker-generated name shape is eligible.  Descriptor
    metadata is intentionally ignored: the mapping's real size and the fixed
    version-1 acknowledgement byte are used so corrupt offsets cannot direct
    cleanup outside the transfer.
    """
    if not payload:
        return None, False
    raw_name = payload.get("shared_memory_name")
    if not raw_name:
        return None, False
    name = str(raw_name)
    suffix = name.removeprefix(IMAGE_SHARED_MEMORY_PREFIX)
    if (
        not name.startswith(IMAGE_SHARED_MEMORY_PREFIX)
        or len(suffix) != 12
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        return None, False

    try:
        shm = SharedMemory(name=name, create=False)
    except Exception:
        return None, False

    mapped_size = int(shm.size)
    unlink_failed = False
    try:
        if mapped_size > SHARED_MEMORY_ACK_OFFSET:
            shm.buf[SHARED_MEMORY_ACK_OFFSET] = SHARED_MEMORY_ACK_ATTACHED
    except Exception:
        pass
    finally:
        try:
            shm.close()
        except Exception:
            pass
        try:
            shm.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            unlink_failed = True

    descriptor = SharedMemoryDescriptor(
        name=name,
        data_size=max(0, mapped_size - SHARED_MEMORY_PAYLOAD_OFFSET),
    )
    return descriptor, unlink_failed


class SharedMemoryAccounting:
    """Thread-safe exact accounting for parent-visible image transfers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._live: dict[str, int] = {}
        self._segments_created = 0
        self._segments_consumed = 0
        self._segments_reclaimed_late = 0
        self._unlink_failures = 0

    def register(self, descriptor: SharedMemoryDescriptor) -> None:
        with self._lock:
            if descriptor.name in self._live:
                return
            self._live[descriptor.name] = descriptor.data_size
            self._segments_created += 1

    def finalize(
        self,
        descriptor: SharedMemoryDescriptor,
        *,
        consumed: bool,
        unlink_failed: bool = False,
    ) -> None:
        with self._lock:
            if descriptor.name not in self._live:
                self._live[descriptor.name] = descriptor.data_size
                self._segments_created += 1

            was_live = self._live.pop(descriptor.name, None) is not None
            if was_live:
                if consumed:
                    self._segments_consumed += 1
                else:
                    self._segments_reclaimed_late += 1
            if unlink_failed:
                self._unlink_failures += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "segments_created": self._segments_created,
                "segments_live": len(self._live),
                "live_bytes": sum(self._live.values()),
                "segments_consumed": self._segments_consumed,
                "segments_reclaimed_late": self._segments_reclaimed_late,
                "unlink_failures": self._unlink_failures,
            }

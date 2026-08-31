"""Process-scoped ordered persistence for canonical settings snapshots.

Settings mutation remains owned by :class:`SettingsManager`.  This module owns
only the blocking durability work: JSON serialization, temporary-file writes,
flush/fsync, and atomic replacement.  It deliberately does not use
``ThreadManager`` because settings durability spans runtime generations and
must remain available while display/widget workers are being retired.
"""

from __future__ import annotations

import atexit
import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from core.settings.structured_roots import STRUCTURED_SETTINGS_ROOTS


_CompletionCallback = Callable[[int, int, bool, Optional[str]], None]


class PersistenceTicket:
    """Waitable acknowledgement for one accepted persistence revision."""

    def __init__(self, *, revision: int, path: Path) -> None:
        self.revision = int(revision)
        self.path = path
        self._event = threading.Event()
        self._success: Optional[bool] = None
        self._error: Optional[str] = None

    @property
    def done(self) -> bool:
        return self._event.is_set()

    @property
    def success(self) -> Optional[bool]:
        return self._success if self.done else None

    @property
    def error(self) -> Optional[str]:
        return self._error if self.done else None

    def wait(self, timeout: float | None = None) -> bool:
        if not self._event.wait(timeout):
            return False
        return self._success is True

    def _complete(self, *, success: bool, error: Optional[str]) -> None:
        self._success = bool(success)
        self._error = error
        self._event.set()


@dataclass
class _WriteRequest:
    owner_key: int
    path: Path
    profile: str
    snapshot_version: int
    state_revision: int
    persistence_revision: int
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    callback: _CompletionCallback
    enqueued_ns: int
    tickets: list[PersistenceTicket] = field(default_factory=list)


class OrderedSettingsPersistence:
    """One process-owned writer for all settings profiles in this process."""

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._pending: dict[int, _WriteRequest] = {}
        self._owner_order: deque[int] = deque()
        self._inflight: Optional[_WriteRequest] = None
        self._accepting = True
        self._stop_requested = False
        self._next_revision = 0
        self._latest_state_revision_by_owner: dict[int, int] = {}

        self._enqueued = 0
        self._coalesced = 0
        self._writes_started = 0
        self._writes_completed = 0
        self._writes_failed = 0
        self._queue_high_water = 0
        self._last_submitted_revision = 0
        self._last_durable_revision = 0
        self._writer_lag_total_ns = 0
        self._writer_lag_max_ns = 0
        self._write_total_ns = 0
        self._write_max_ns = 0
        self._flush_count = 0
        self._flush_total_ns = 0
        self._flush_max_ns = 0
        self._flush_timeouts = 0
        self._close_duration_ns = 0
        self._close_timed_out = False

        self._thread = threading.Thread(
            target=self._run,
            name="SRPSSSettingsWriter",
            daemon=True,
        )
        self._thread.start()

    @property
    def accepting(self) -> bool:
        with self._condition:
            return self._accepting

    @property
    def writer_thread(self) -> threading.Thread:
        return self._thread

    def submit(
        self,
        *,
        owner_key: int,
        path: Path,
        profile: str,
        snapshot_version: int,
        state_revision: int,
        data: Dict[str, Any],
        metadata: Dict[str, Any],
        callback: _CompletionCallback,
    ) -> PersistenceTicket:
        """Accept one immutable store snapshot without doing file I/O."""

        with self._condition:
            if not self._accepting:
                raise RuntimeError("settings persistence writer is closing")

            self._next_revision += 1
            persistence_revision = self._next_revision
            ticket = PersistenceTicket(
                revision=persistence_revision,
                path=path,
            )
            request = _WriteRequest(
                owner_key=int(owner_key),
                path=path,
                profile=str(profile),
                snapshot_version=int(snapshot_version),
                state_revision=int(state_revision),
                persistence_revision=persistence_revision,
                data=data,
                metadata=metadata,
                callback=callback,
                enqueued_ns=time.perf_counter_ns(),
                tickets=[ticket],
            )

            latest_state_revision = self._latest_state_revision_by_owner.get(
                request.owner_key,
                -1,
            )
            if request.state_revision < latest_state_revision:
                raise ValueError(
                    "out-of-order settings snapshot: "
                    f"owner={request.owner_key} state_revision={request.state_revision} "
                    f"latest={latest_state_revision}"
                )
            self._latest_state_revision_by_owner[request.owner_key] = max(
                latest_state_revision,
                request.state_revision,
            )

            previous = self._pending.get(request.owner_key)
            if previous is not None:
                # The same store owner supplied a newer complete snapshot.  It
                # includes every prior mutation, so pending (not in-flight)
                # revisions may share the newer durable acknowledgement.
                request.tickets = [*previous.tickets, ticket]
                self._pending[request.owner_key] = request
                self._coalesced += 1
            else:
                self._pending[request.owner_key] = request
                self._owner_order.append(request.owner_key)

            self._enqueued += 1
            self._last_submitted_revision = persistence_revision
            depth = len(self._pending) + (1 if self._inflight is not None else 0)
            self._queue_high_water = max(self._queue_high_water, depth)
            self._condition.notify()
            return ticket

    def flush_ticket(
        self,
        ticket: PersistenceTicket | None,
        *,
        timeout: float = 5.0,
    ) -> bool:
        if ticket is None:
            return True
        started_ns = time.perf_counter_ns()
        success = ticket.wait(max(0.0, float(timeout)))
        elapsed_ns = time.perf_counter_ns() - started_ns
        with self._condition:
            self._record_flush_locked(elapsed_ns, timed_out=not ticket.done)
        return success

    def flush_path(self, path: Path, *, timeout: float = 5.0) -> bool:
        resolved = path.resolve()
        with self._condition:
            tickets: list[PersistenceTicket] = []
            if self._inflight is not None and self._inflight.path == resolved:
                tickets.extend(self._inflight.tickets)
            for request in self._pending.values():
                if request.path == resolved:
                    tickets.extend(request.tickets)
        return self._wait_tickets(tickets, timeout=timeout)

    def flush_all(self, *, timeout: float = 5.0) -> bool:
        with self._condition:
            tickets = self._outstanding_tickets_locked()
        return self._wait_tickets(tickets, timeout=timeout)

    def close(self, *, timeout: float = 5.0) -> dict[str, Any]:
        started_ns = time.perf_counter_ns()
        with self._condition:
            self._accepting = False
            self._stop_requested = True
            tickets = self._outstanding_tickets_locked()
            self._condition.notify_all()

        deadline = time.monotonic() + max(0.0, float(timeout))
        tickets_ok = self._wait_tickets(
            tickets,
            timeout=max(0.0, deadline - time.monotonic()),
        )
        self._thread.join(max(0.0, deadline - time.monotonic()))
        timed_out = self._thread.is_alive() or any(not ticket.done for ticket in tickets)
        with self._condition:
            self._close_duration_ns = time.perf_counter_ns() - started_ns
            self._close_timed_out = timed_out
            metrics = self.metrics_snapshot()
        metrics["close_success"] = bool(tickets_ok and not timed_out)
        return metrics

    def metrics_snapshot(self) -> dict[str, Any]:
        with self._condition:
            lag_records = self._writes_started
            write_records = self._writes_completed + self._writes_failed
            return {
                "active": self._thread.is_alive(),
                "accepting": self._accepting,
                "queue_depth": len(self._pending)
                + (1 if self._inflight is not None else 0),
                "queue_high_water": self._queue_high_water,
                "enqueued": self._enqueued,
                "coalesced": self._coalesced,
                "writes_started": self._writes_started,
                "writes_completed": self._writes_completed,
                "writes_failed": self._writes_failed,
                "last_submitted_revision": self._last_submitted_revision,
                "last_durable_revision": self._last_durable_revision,
                "writer_lag_avg_ms": (
                    self._writer_lag_total_ns / lag_records / 1_000_000.0
                    if lag_records
                    else 0.0
                ),
                "writer_lag_max_ms": self._writer_lag_max_ns / 1_000_000.0,
                "write_avg_ms": (
                    self._write_total_ns / write_records / 1_000_000.0
                    if write_records
                    else 0.0
                ),
                "write_max_ms": self._write_max_ns / 1_000_000.0,
                "flush_count": self._flush_count,
                "flush_avg_ms": (
                    self._flush_total_ns / self._flush_count / 1_000_000.0
                    if self._flush_count
                    else 0.0
                ),
                "flush_max_ms": self._flush_max_ns / 1_000_000.0,
                "flush_timeouts": self._flush_timeouts,
                "close_duration_ms": self._close_duration_ns / 1_000_000.0,
                "close_timed_out": self._close_timed_out,
                "writer_alive": self._thread.is_alive(),
            }

    def _wait_tickets(
        self,
        tickets: list[PersistenceTicket],
        *,
        timeout: float,
    ) -> bool:
        started_ns = time.perf_counter_ns()
        deadline = time.monotonic() + max(0.0, float(timeout))
        success = True
        for ticket in tickets:
            remaining = max(0.0, deadline - time.monotonic())
            if not ticket.wait(remaining):
                success = False
                if not ticket.done:
                    break
        elapsed_ns = time.perf_counter_ns() - started_ns
        timed_out = any(not ticket.done for ticket in tickets)
        with self._condition:
            self._record_flush_locked(elapsed_ns, timed_out=timed_out)
        return bool(success and not timed_out)

    def _record_flush_locked(self, elapsed_ns: int, *, timed_out: bool) -> None:
        self._flush_count += 1
        self._flush_total_ns += int(elapsed_ns)
        self._flush_max_ns = max(self._flush_max_ns, int(elapsed_ns))
        if timed_out:
            self._flush_timeouts += 1

    def _outstanding_tickets_locked(self) -> list[PersistenceTicket]:
        tickets: list[PersistenceTicket] = []
        if self._inflight is not None:
            tickets.extend(self._inflight.tickets)
        for request in self._pending.values():
            tickets.extend(request.tickets)
        return tickets

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._owner_order and not self._stop_requested:
                    self._condition.wait()
                if not self._owner_order:
                    if self._stop_requested:
                        return
                    continue
                owner_key = self._owner_order.popleft()
                request = self._pending.pop(owner_key, None)
                if request is None:
                    continue
                self._inflight = request
                self._writes_started += 1
                lag_ns = max(0, time.perf_counter_ns() - request.enqueued_ns)
                self._writer_lag_total_ns += lag_ns
                self._writer_lag_max_ns = max(self._writer_lag_max_ns, lag_ns)

            write_started_ns = time.perf_counter_ns()
            error: Optional[str] = None
            try:
                _write_snapshot(request)
                success = True
            except Exception as exc:  # pragma: no cover - exact OS errors vary
                success = False
                error = f"{type(exc).__name__}: {exc}"
            elapsed_ns = time.perf_counter_ns() - write_started_ns

            with self._condition:
                self._write_total_ns += elapsed_ns
                self._write_max_ns = max(self._write_max_ns, elapsed_ns)
                if success:
                    self._writes_completed += 1
                    self._last_durable_revision = max(
                        self._last_durable_revision,
                        request.persistence_revision,
                    )
                else:
                    self._writes_failed += 1

            try:
                request.callback(
                    request.state_revision,
                    request.persistence_revision,
                    success,
                    error,
                )
            except Exception:
                pass
            for ticket in request.tickets:
                ticket._complete(success=success, error=error)
            with self._condition:
                # Keep the request discoverable by flush_path()/flush_all()
                # until every acknowledgement is visible.  Otherwise a flush
                # racing the disk-write -> ticket handoff could return early.
                self._inflight = None
                self._condition.notify_all()


def _write_snapshot(request: _WriteRequest) -> None:
    snapshot: Dict[str, Any] = {}
    for key, value in request.data.items():
        if key in STRUCTURED_SETTINGS_ROOTS and isinstance(value, Mapping):
            snapshot[key] = value
            continue
        if "." in key:
            section, subkey = key.split(".", 1)
            container = snapshot.setdefault(section, {})
            if isinstance(container, dict):
                container[subkey] = value
            else:
                snapshot[section] = {subkey: value}
        else:
            snapshot[key] = value

    payload = {
        "version": request.snapshot_version,
        "profile": request.profile,
        "snapshot": snapshot,
        "metadata": request.metadata,
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)

    request.path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = request.path.with_name(
        f".{request.path.name}.{os.getpid()}.tmp"
    )
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        _atomic_replace_durable(temp_path, request.path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _atomic_replace_durable(temp_path: Path, target_path: Path) -> None:
    """Atomically replace *target_path* with platform durability semantics."""

    if os.name == "nt":
        import ctypes

        movefile_replace_existing = 0x00000001
        movefile_write_through = 0x00000008
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file_ex = kernel32.MoveFileExW
        move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        move_file_ex.restype = ctypes.c_int
        if not move_file_ex(
            str(temp_path),
            str(target_path),
            movefile_replace_existing | movefile_write_through,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return

    os.replace(temp_path, target_path)
    # POSIX requires the containing directory entry to be flushed separately
    # from the file contents.  Unsupported directory fsync is a real write
    # failure because callers use flush() as a durability acknowledgement.
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(target_path.parent), directory_flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


_CONTROLLER_LOCK = threading.RLock()
_CONTROLLER: Optional[OrderedSettingsPersistence] = None
_CONTROLLER_CLOSING = False


def get_settings_persistence() -> OrderedSettingsPersistence:
    global _CONTROLLER
    with _CONTROLLER_LOCK:
        if _CONTROLLER_CLOSING:
            raise RuntimeError("settings persistence is closing")
        if _CONTROLLER is None or not _CONTROLLER.accepting:
            _CONTROLLER = OrderedSettingsPersistence()
        return _CONTROLLER


def flush_settings_path(path: Path, *, timeout: float = 5.0) -> bool:
    with _CONTROLLER_LOCK:
        controller = _CONTROLLER
    if controller is None:
        return True
    return controller.flush_path(path, timeout=timeout)


def flush_settings_persistence(*, timeout: float = 5.0) -> bool:
    with _CONTROLLER_LOCK:
        controller = _CONTROLLER
    if controller is None:
        return True
    return controller.flush_all(timeout=timeout)


def flush_and_close_settings_persistence(
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    global _CONTROLLER, _CONTROLLER_CLOSING
    with _CONTROLLER_LOCK:
        if _CONTROLLER_CLOSING:
            controller = _CONTROLLER
            if controller is None:
                return _empty_metrics()
            metrics = controller.metrics_snapshot()
            metrics["close_success"] = False
            return metrics
        _CONTROLLER_CLOSING = True
        controller = _CONTROLLER
    try:
        if controller is None:
            return _empty_metrics()
        metrics = controller.close(timeout=timeout)
        return metrics
    finally:
        with _CONTROLLER_LOCK:
            if controller is None or not controller.writer_thread.is_alive():
                _CONTROLLER = None
                _CONTROLLER_CLOSING = False


def _empty_metrics() -> dict[str, Any]:
    return {
        "active": False,
        "accepting": False,
        "queue_depth": 0,
        "queue_high_water": 0,
        "enqueued": 0,
        "coalesced": 0,
        "writes_started": 0,
        "writes_completed": 0,
        "writes_failed": 0,
        "last_submitted_revision": 0,
        "last_durable_revision": 0,
        "writer_lag_avg_ms": 0.0,
        "writer_lag_max_ms": 0.0,
        "write_avg_ms": 0.0,
        "write_max_ms": 0.0,
        "flush_count": 0,
        "flush_avg_ms": 0.0,
        "flush_max_ms": 0.0,
        "flush_timeouts": 0,
        "close_duration_ms": 0.0,
        "close_timed_out": False,
        "writer_alive": False,
        "close_success": True,
    }


def _atexit_close() -> None:
    try:
        flush_and_close_settings_persistence(timeout=2.0)
    except Exception:
        pass


atexit.register(_atexit_close)

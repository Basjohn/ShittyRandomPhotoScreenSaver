"""Ordered controls: one serialization and rollback before queue admission.

Accepted POSIX descriptors keep stdlib resource-sharer ownership, including its
unread-transfer retention limitation. Only unpublished IDs can be rolled back
locally: no receiver can request them, so no service handshake/barrier is needed.
"""
from __future__ import annotations

from io import BytesIO
from multiprocessing import connection, reduction, resource_sharer
import os
import sys

from core.logging.logger import get_logger

logger = get_logger(__name__)


def _registration_service():
    service = resource_sharer._resource_sharer
    if (sys.implementation.name != 'cpython' or sys.version_info[:2] != (3, 14)
            or not isinstance(getattr(service, '_cache', None), dict)
            or not hasattr(getattr(service, '_lock', None), '__enter__')
            or not hasattr(service, '_address') or not callable(getattr(service, 'register', None))):
        raise RuntimeError('Ordered FD transfer requires the audited CPython 3.14 resource-sharer contract')
    return service


class _UnsubmittedRegistration:
    """Pinned CPython 3.14 local rollback for IDs which have never escaped."""

    def __init__(self, service, identifier):
        self.service, self.identifier = service, identifier

    def cancel(self) -> None:
        address, key = self.identifier
        with self.service._lock:
            owned = (self.service._cache.pop(key, None) if self.service._address == address else None)
        if owned is not None:
            _send, close = owned
            close()


class _TargetPipeTransfer:
    def __init__(self, handle, process):
        self.handle, self.process = handle, process

    def cancel(self) -> None:
        import _winapi
        # An unread duplicate already belongs to the target process. Exit has
        # reclaimed it. The supervisor lock keeps the original process handle
        # open through admission/rollback; no PID lookup or reuse can occur.
        target = self.process.sentinel
        if _winapi.WaitForSingleObject(target, 0) == _winapi.WAIT_OBJECT_0:
            return
        try:
            local = _winapi.DuplicateHandle(target, self.handle, _winapi.GetCurrentProcess(),
                                           0, False, _winapi.DUPLICATE_CLOSE_SOURCE | _winapi.DUPLICATE_SAME_ACCESS)
        except OSError:
            if _winapi.WaitForSingleObject(target, 0) != _winapi.WAIT_OBJECT_0:
                raise
        else:
            _winapi.CloseHandle(local)


def _rebuild_target_pipe(handle: int, readable: bool, writable: bool):
    """The numeric handle already belongs to this receiving child process."""
    return connection.PipeConnection(handle, readable, writable)


class EncodedControl:
    def __init__(self, message: dict, process) -> None:
        self._transfers = []
        buffer = BytesIO()
        pickler = reduction.ForkingPickler(buffer)
        def registered(value, reducer=pickler.dispatch_table[connection.Connection]):
            service = _registration_service()  # validate before creating a registration
            rebuilt = reducer(value)
            self._transfers.append(_UnsubmittedRegistration(service, rebuilt[1][0]._id))
            return rebuilt
        pickler.dispatch_table[connection.Connection] = registered
        if os.name == 'nt':
            import _winapi
            def target_pipe(value):
                access = ((_winapi.FILE_GENERIC_READ if value.readable else 0)
                          | (_winapi.FILE_GENERIC_WRITE if value.writable else 0))
                duplicate = _winapi.DuplicateHandle(_winapi.GetCurrentProcess(), value.fileno(),
                                                    process.sentinel, access, False, 0)
                self._transfers.append(_TargetPipeTransfer(duplicate, process))
                return _rebuild_target_pipe, (duplicate, value.readable, value.writable)
            pickler.dispatch_table[connection.PipeConnection] = target_pipe
        try:
            pickler.dump(message)
            self.data = buffer.getvalue()
        except BaseException:
            self.close_unsubmitted()
            logger.exception('Ordered control serialization refused before queue admission')
            raise

    def submitted(self) -> None:
        # From this edge on, native pipes are target-owned; other Connection
        # transfers use the same supported ownership as ordinary mp.Queue sends.
        self._transfers.clear()

    def close_unsubmitted(self) -> None:
        transfers, self._transfers = self._transfers, []
        failures = []
        for transfer in transfers:
            try:
                transfer.cancel()
            except Exception as exc:
                logger.exception('Unsubmitted ordered control transfer cleanup failed')
                failures.append(exc)
        if failures:
            raise RuntimeError('Unsubmitted control transfer cleanup failed') from failures[0]


def decode_control(data: bytes) -> dict:
    return reduction.ForkingPickler.loads(data)

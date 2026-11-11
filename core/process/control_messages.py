"""Ordered controls: one serialization and rollback before queue admission.

A control may carry a pipe end only where its ownership is exact, and that is Windows alone: the pipe handle is
duplicated straight into the supervised process, so the duplicate belongs to that process even if the message is
never decoded, and the process's exit reclaims it.

Everywhere else a ``multiprocessing.Connection`` crosses a queue through the stdlib resource sharer: pickling it
registers a duplicate descriptor on the sender's side, which the sharer keeps until the receiver asks for it. A worker
that dies before decoding the message never asks, and the supported API has no cancellation for an accepted
registration (its service pops entries without the registration lock, so popping one from outside races it). The
ordered channel therefore creates no such registration at all: a sharer-backed ``Connection`` is refused before
anything is registered (``SharerBackedTransferRefused``), on every platform, and the one descriptor the Visualizer
needs across this channel on POSIX, the session's wake pipe, travels as a name instead
(``core.visualizer_engine.wake_channel``). No private resource-sharer state is read or written here.
"""
from __future__ import annotations

from io import BytesIO
from multiprocessing import connection, reduction
import os
import socket

from core.logging.logger import get_logger

logger = get_logger(__name__)


class SharerBackedTransferRefused(TypeError):
    """An ordered control carried a ``Connection`` that only the resource sharer could hand over."""


def _refuse_sharer_backed(value):
    raise SharerBackedTransferRefused(
        f"an ordered control cannot carry a {type(value).__name__}: the resource sharer would keep a sender-side "
        "duplicate that a worker dying before it decodes the message never collects; send a name the receiver opens "
        "(core.visualizer_engine.wake_channel)")


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
        # POSIX: every Connection. Windows: the socket-backed class (pipes are ``PipeConnection``, below). A socket
        # crosses through the sharer the same way.
        pickler.dispatch_table[connection.Connection] = _refuse_sharer_backed
        pickler.dispatch_table[socket.socket] = _refuse_sharer_backed
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
        # From this edge on, native pipes are target-owned (Windows). Nothing else was transferred.
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

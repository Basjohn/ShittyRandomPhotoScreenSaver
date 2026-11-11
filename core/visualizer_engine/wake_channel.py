"""The engine worker session's wake channel: one pipe from the session (the writer) to its owner's listener.

One byte per publish goes down it (``packet_mailbox.send_wake_byte_without_blocking``); its end is the session's end
(``PacketMailbox.listen_for_wakes``' ``on_closed``). This module owns how the session comes to hold its writer end,
which differs by platform because of who owns a descriptor that crosses a process boundary:

- **Windows:** an anonymous pipe. ``VIS_CONFIGURE`` carries the writer end and the ordered control channel duplicates
  it straight into the worker process (``core.process.control_messages``): the duplicate belongs to the worker even
  if it is never decoded, and the worker's exit reclaims it.
- **POSIX:** a named pipe (a FIFO) in a private directory. ``VIS_CONFIGURE`` carries its **name** (``WakeName``, plain
  data) and the session opens its own writer end by that name. Nothing is transferred, so nothing can be left behind:
  a ``multiprocessing.Connection`` sent through a queue is handed over by the stdlib resource sharer, whose
  sender-side registration keeps a duplicate descriptor until the receiver asks for it, and a worker that dies before
  decoding the message never asks (phase-boundary audit, L1's inherited finding). The ordered control channel
  therefore refuses a sharer-backed ``Connection`` outright.

Ownership on the main side, both platforms: the link holds the reader end (its mailbox's listener), its own writer end
until the session answers the configure (so the pipe cannot end before the session exists), and on POSIX the name
until then. ``WakeChannel.release_sender`` gives back the writer end and the name; the link calls it at the
configure's reply and at ``close``. So a worker that dies before decoding its configure leaves the link holding
exactly what the link's own ``close`` releases: two descriptors and one name, per link, with no service, handshake or
timer involved.

POSIX status: source-level only. It is covered by unit tests of the ordering and the rollback (the system calls
injected) and has never run on Linux; forkserver, the FIFO's open and end-of-file behaviour and the listener are
unverified there (``Linux_Plan.md``, Phase 4).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class WakeName:
    """The POSIX wake pipe's name, as ``VIS_CONFIGURE`` carries it (plain data: it pickles to a string)."""

    path: str


class WakeChannel:
    """The main side's ends of one session's wake pipe. ``transfer`` is what ``VIS_CONFIGURE`` carries."""

    def __init__(self, receiver: Any, sender: Any, transfer: Any,
                 release_name: Callable[[], None] | None = None) -> None:
        self.receiver = receiver
        self.transfer = transfer
        self._sender = sender
        self._release_name = release_name

    @property
    def holds_sender(self) -> bool:
        return self._sender is not None

    def release_sender(self) -> None:
        """Give back the main side's writer end and (POSIX) the pipe's name (idempotent). From now on the pipe's end
        is the session's: with no session holding a writer end, the listener sees it at once."""
        sender, self._sender = self._sender, None
        release_name, self._release_name = self._release_name, None
        try:
            if sender is not None:
                try:
                    sender.close()
                except OSError:
                    pass
        finally:
            if release_name is not None:
                release_name()


def open_wake_channel() -> WakeChannel:
    """A fresh wake pipe for one session (the main process). Never blocks: local system calls only."""
    if sys.platform == "win32":
        import multiprocessing

        receiver, sender = multiprocessing.Pipe(duplex=False)
        return WakeChannel(receiver, sender, sender)
    return open_named_wake_channel()


def open_named_wake_channel(*, ops: Any = os, make_directory: Callable[..., str] | None = None,
                            connection: Callable[..., Any] | None = None) -> WakeChannel:
    """POSIX: a FIFO in a fresh directory only this user can enter, with both of the main side's ends open.

    The reader is opened first, without blocking (a FIFO's blocking open waits for the other side), then the main
    side's own writer (it needs a reader to exist), then the reader is made blocking for the listener. Holding a
    writer here is what keeps the reader from seeing the end of a pipe nobody has opened for writing yet. A step that
    fails gives back every descriptor opened so far and the name. ``ops``, ``make_directory`` and ``connection`` are
    the system calls (``os``, ``tempfile.mkdtemp``, ``multiprocessing.connection.Connection``): injected by the unit
    tests, which is the only way this runs on Windows."""
    if make_directory is None:
        import tempfile

        make_directory = tempfile.mkdtemp
    if connection is None:
        from multiprocessing.connection import Connection as connection
    directory = make_directory(prefix="srpss-viz-wake-")       # mode 0o700
    path = directory.rstrip("/") + "/wake"
    opened: list[int] = []
    wrapped: list[Any] = []

    def release_name() -> None:
        for remove, target in ((ops.unlink, path), (ops.rmdir, directory)):
            try:
                remove(target)
            except OSError:
                pass

    try:
        ops.mkfifo(path, 0o600)
        reader = ops.open(path, ops.O_RDONLY | ops.O_NONBLOCK)
        opened.append(reader)
        writer = ops.open(path, ops.O_WRONLY | ops.O_NONBLOCK)
        opened.append(writer)
        ops.set_blocking(reader, True)
        receiver = connection(reader, writable=False)
        opened.remove(reader)
        wrapped.append(receiver)
        sender = connection(writer, readable=False)
        opened.remove(writer)
        wrapped.append(sender)
    except BaseException:
        for end in wrapped:
            try:
                end.close()
            except OSError:
                pass
        for descriptor in opened:
            try:
                ops.close(descriptor)
            except OSError:
                pass
        release_name()
        raise
    return WakeChannel(receiver, sender, WakeName(path), release_name)


def open_wake_sender(transfer: Any, *, ops: Any = os, connection: Callable[..., Any] | None = None) -> Any:
    """The session's writer end from what ``VIS_CONFIGURE`` carried (the worker process): a ``WakeName`` is opened by
    name, without blocking (the owner holds the reader; an owner that already gave the pipe up makes this fail, and
    with it the configure: no session for an owner that is gone); anything else is the writer end itself (Windows,
    the in-process gates) or None (no wake)."""
    if not isinstance(transfer, WakeName):
        return transfer
    if connection is None:
        from multiprocessing.connection import Connection as connection
    descriptor = ops.open(transfer.path, ops.O_WRONLY | ops.O_NONBLOCK)
    try:
        return connection(descriptor, readable=False)
    except BaseException:
        ops.close(descriptor)
        raise

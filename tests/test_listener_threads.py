"""The blocking-listener primitive: one thread per listener, registered while it runs, gone when its source closes;
the engine mailbox's wake listener runs on it (no raw ``threading.Thread`` in production code)."""
from __future__ import annotations

import multiprocessing
import threading

from core.threading import listener_threads


def _names() -> list[str]:
    return [row["name"] for row in listener_threads.snapshot()["listeners"]]


def test_listener_lives_exactly_as_long_as_its_source():
    receiver, sender = multiprocessing.Pipe(duplex=False)
    started, got = threading.Event(), []

    def listen() -> None:
        started.set()
        while True:
            try:
                got.append(receiver.recv_bytes())
            except (EOFError, OSError):
                return

    handle = listener_threads.start_listener(listen, name="test-listener-source", category="test")
    assert started.wait(5.0)
    sender.send_bytes(b"x")
    assert handle.alive and "test-listener-source" in _names()
    sender.close()                                   # the owner closes the source, never the thread
    assert handle.join(5.0)
    assert got == [b"x"] and "test-listener-source" not in _names()
    receiver.close()


def test_a_listener_that_raises_is_forgotten():
    def boom() -> None:
        raise RuntimeError("planted")

    handle = listener_threads.start_listener(boom, name="test-listener-raises", category="test")
    assert handle.join(5.0)
    assert "test-listener-raises" not in _names()


def test_mailbox_wake_listener_is_the_primitive_and_ends_with_the_mailbox():
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    receiver, sender = multiprocessing.Pipe(duplex=False)
    reader = PacketMailbox(role="reader")
    try:
        woke = threading.Event()
        reader.set_wake_callback(woke.set)
        reader.listen_for_wakes(receiver)
        handle = reader._wake_thread
        assert isinstance(handle, listener_threads.ListenerHandle)
        assert "srpss-visualizer-engine-wake" in _names()
        sender.send_bytes(b"\x01")
        assert woke.wait(5.0)
    finally:
        reader.close()
        sender.close()
    assert handle.join(5.0)

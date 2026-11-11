"""The engine worker session's wake channel (``core/visualizer_engine/wake_channel.py``): the POSIX
transfer-lifetime repair.

On POSIX a ``multiprocessing.Connection`` crosses a queue through the stdlib resource sharer, whose sender-side
registration keeps a duplicate descriptor until the receiver collects it; a worker that died before decoding its
``VIS_CONFIGURE`` never did. The wake pipe is now a named pipe there: the configure carries its name, the session opens
its own end, and the ordered control channel refuses a sharer-backed Connection
(``tests/test_visualizer_ordered_control_delivery.py``).

What these tests are, and are not: the POSIX branch's ordering, rollback and ownership with its system calls injected
(``os.mkfifo`` does not exist on Windows), the Windows branch for real, and the link and session wiring over a named
transfer with the name's "open" stood in by a duplicate of the pipe end. **Nothing here runs a FIFO, forkserver or a
Linux worker: the POSIX runtime is unverified.**
"""
from __future__ import annotations

import errno
import multiprocessing
import pickle
import sys

import pytest

from tools.visualizer_replay import owner_worker_gate as gate


class _FakePosix:
    """The POSIX calls the named channel makes, recorded, with descriptors as integers and a fault to inject."""

    O_RDONLY, O_WRONLY, O_NONBLOCK = 0x0, 0x1, 0x800

    def __init__(self, fail_at: str | None = None) -> None:
        self.calls: list[tuple] = []
        self.open_descriptors: set[int] = set()
        self.closed: list[int] = []
        self.names: set[str] = set()
        self.directories: set[str] = set()
        self.fail_at = fail_at
        self._next = 10

    def _step(self, name: str, *args) -> None:
        self.calls.append((name, *args))
        if self.fail_at == name:
            raise OSError(errno.EIO, f"injected at {name}")

    def make_directory(self, *, prefix: str) -> str:
        directory = f"/tmp/{prefix}abc123"
        self.directories.add(directory)
        self._step("mkdtemp", prefix)
        return directory

    def mkfifo(self, path: str, mode: int) -> None:
        self._step("mkfifo", path, mode)
        self.names.add(path)

    def open(self, path: str, flags: int) -> int:
        self._step("open_writer" if flags & self.O_WRONLY else "open_reader", path, flags)
        if path not in self.names:
            raise FileNotFoundError(errno.ENOENT, "no such FIFO", path)
        descriptor, self._next = self._next, self._next + 1
        self.open_descriptors.add(descriptor)
        return descriptor

    def set_blocking(self, descriptor: int, blocking: bool) -> None:
        self._step("set_blocking", descriptor, blocking)

    def close(self, descriptor: int) -> None:
        self.calls.append(("close", descriptor))
        self.closed.append(descriptor)
        self.open_descriptors.remove(descriptor)          # a second close of one descriptor fails the test

    def unlink(self, path: str) -> None:
        self.calls.append(("unlink", path))
        if path not in self.names:
            raise FileNotFoundError(errno.ENOENT, "gone", path)
        self.names.remove(path)

    def rmdir(self, directory: str) -> None:
        self.calls.append(("rmdir", directory))
        if directory not in self.directories:
            raise FileNotFoundError(errno.ENOENT, "gone", directory)
        self.directories.remove(directory)

    def connection(self, descriptor: int, readable: bool = True, writable: bool = True):
        self._step("wrap_writer" if writable else "wrap_reader", descriptor)
        return _FakeConnection(self, descriptor, readable, writable)


class _FakeConnection:
    def __init__(self, posix: _FakePosix, descriptor: int, readable: bool, writable: bool) -> None:
        self.posix, self.descriptor, self.readable, self.writable = posix, descriptor, readable, writable
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.posix.close(self.descriptor)


def _named(posix: _FakePosix):
    from core.visualizer_engine.wake_channel import open_named_wake_channel

    return open_named_wake_channel(ops=posix, make_directory=posix.make_directory, connection=posix.connection)


def test_the_named_channel_opens_its_reader_first_and_hands_over_only_a_name():
    from core.process.control_messages import EncodedControl, decode_control
    from core.visualizer_engine.wake_channel import WakeName

    posix = _FakePosix()
    channel = _named(posix)
    steps = [call[0] for call in posix.calls]
    # The reader before the writer (a writer's non-blocking open needs a reader), both without blocking (a FIFO's
    # blocking open waits for the other side), the reader blocking only once the main side's writer holds the pipe
    # open (so the listener never reads the end of a pipe nobody has opened for writing yet).
    assert steps == ["mkdtemp", "mkfifo", "open_reader", "open_writer", "set_blocking", "wrap_reader", "wrap_writer"]
    (_m, path, mode), (_r, reader_path, reader_flags), (_w, writer_path, writer_flags) = posix.calls[1:4]
    assert mode == 0o600 and reader_path == writer_path == path
    assert reader_flags == posix.O_RDONLY | posix.O_NONBLOCK and writer_flags == posix.O_WRONLY | posix.O_NONBLOCK
    assert posix.calls[4] == ("set_blocking", channel.receiver.descriptor, True)
    assert not channel.receiver.writable and not channel._sender.readable and channel.holds_sender
    # What crosses is plain data: a name, picklable by anything, with no descriptor for a sharer to keep.
    assert channel.transfer == WakeName(path) and pickle.loads(pickle.dumps(channel.transfer)) == channel.transfer
    encoded = EncodedControl({"payload": {"wake": channel.transfer}}, process=None)
    assert decode_control(encoded.data) == {"payload": {"wake": WakeName(path)}} and not encoded._transfers


def test_releasing_the_sender_closes_it_and_removes_the_name_exactly_once():
    posix = _FakePosix()
    channel = _named(posix)
    path = channel.transfer.path
    before = len(posix.calls)
    channel.release_sender()
    assert posix.calls[before:] == [("close", channel_sender_descriptor(posix)), ("unlink", path),
                                    ("rmdir", path.rsplit("/", 1)[0])]
    assert not channel.holds_sender and not posix.names and not posix.directories
    assert posix.open_descriptors == {channel.receiver.descriptor}       # the listener's end is the mailbox's
    channel.release_sender()
    channel.release_sender()
    assert len(posix.calls) == before + 3


def channel_sender_descriptor(posix: _FakePosix) -> int:
    (wrapped,) = [call[1] for call in posix.calls if call[0] == "wrap_writer"]
    return wrapped


@pytest.mark.parametrize("fail_at", ("mkfifo", "open_reader", "open_writer", "set_blocking", "wrap_reader",
                                     "wrap_writer"))
def test_a_step_that_fails_gives_back_every_descriptor_and_the_name(fail_at):
    posix = _FakePosix(fail_at=fail_at)
    with pytest.raises(OSError, match="injected"):
        _named(posix)
    assert posix.open_descriptors == set()                # each opened descriptor closed, none twice
    assert not posix.names and not posix.directories      # the FIFO (when made) and its directory are gone


def test_the_session_opens_a_named_pipe_for_writing_without_blocking_and_passes_anything_else_through():
    from core.visualizer_engine.wake_channel import WakeName, open_wake_sender

    posix = _FakePosix()
    channel = _named(posix)
    sender = open_wake_sender(channel.transfer, ops=posix, connection=posix.connection)
    assert posix.calls[-2] == ("open_writer", channel.transfer.path, posix.O_WRONLY | posix.O_NONBLOCK)
    assert sender.writable and not sender.readable and sender.descriptor in posix.open_descriptors
    # The owner gave the pipe up before the session got to its configure (its link closed): the open fails, and with
    # it the configure. No session is built for an owner that is gone, and nothing is left open.
    channel.release_sender()
    held = set(posix.open_descriptors)
    with pytest.raises(FileNotFoundError):
        open_wake_sender(WakeName(channel.transfer.path), ops=posix, connection=posix.connection)
    assert posix.open_descriptors == held
    # A wrap that fails closes the descriptor it had opened.
    late = _named(_FakePosix())
    faulty = late.posix_for_test = late.receiver.posix
    faulty.fail_at = "wrap_writer"
    with pytest.raises(OSError, match="injected"):
        open_wake_sender(late.transfer, ops=faulty, connection=faulty.connection)
    assert faulty.open_descriptors == {late.receiver.descriptor, late._sender.descriptor}
    # Windows and the in-process gates: the writer end itself, or no wake at all.
    marker = object()
    assert open_wake_sender(marker) is marker and open_wake_sender(None) is None


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows branch: an anonymous pipe, its writer end transferred")
def test_the_windows_channel_is_a_pipe_whose_end_is_the_sessions_once_the_sender_is_released():
    from core.visualizer_engine.wake_channel import open_wake_channel
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor

    channel = open_wake_channel()
    try:
        assert channel.transfer is channel._sender                       # the writer end itself crosses
        session_end = _InProcessSupervisor._duplicate(channel.transfer)  # as the control channel hands it over
        channel.release_sender()
        channel.release_sender()
        assert not channel.holds_sender
        session_end.send_bytes(b"w")
        assert channel.receiver.poll(5.0) and channel.receiver.recv_bytes() == b"w"
        session_end.close()                                              # the session ends: the pipe ends
        with pytest.raises((EOFError, OSError)):                         # what the listener takes as the end
            channel.receiver.recv_bytes()
    finally:
        channel.release_sender()
        channel.receiver.close()


# ---------------------------------------------------------------------- the link and the session over a name


class _NamedPipes:
    """A named transfer for the real link and session on this platform: the pipe is this platform's own, and "opening
    the name" (the session's side) gives a duplicate of its writer end, as a FIFO's second open gives a second
    descriptor on the same pipe, for as long as the name exists."""

    def __init__(self) -> None:
        self.live: dict = {}                    # path -> the main side's writer end, while the name exists
        self.released: list[str] = []
        self.opened: list[str] = []
        self.channels: list = []

    def open_wake_channel(self):
        from core.visualizer_engine.wake_channel import WakeChannel, WakeName

        receiver, sender = multiprocessing.Pipe(duplex=False)
        path = f"test-wake-{len(self.channels)}"
        self.live[path] = sender

        def release_name() -> None:
            self.released.append(path)
            del self.live[path]

        channel = WakeChannel(receiver, sender, WakeName(path), release_name)
        self.channels.append(channel)
        return channel

    def open_wake_sender(self, transfer):
        from core.visualizer_engine.wake_channel import WakeName
        from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor

        if not isinstance(transfer, WakeName):
            return transfer
        self.opened.append(transfer.path)
        if transfer.path not in self.live:
            raise FileNotFoundError(errno.ENOENT, "the owner gave the pipe up", transfer.path)
        return _InProcessSupervisor._duplicate(self.live[transfer.path])


@pytest.fixture
def named_pipes(monkeypatch):
    from core.visualizer_engine import wake_channel

    pipes = _NamedPipes()
    monkeypatch.setattr(wake_channel, "open_wake_channel", pipes.open_wake_channel)
    monkeypatch.setattr(wake_channel, "open_wake_sender", pipes.open_wake_sender)
    return pipes


def _connections_in(value) -> list:
    if isinstance(value, dict):
        return [found for item in value.values() for found in _connections_in(item)]
    if isinstance(value, (list, tuple)):
        return [found for item in value for found in _connections_in(item)]
    return [value] if hasattr(value, "fileno") else []


@pytest.fixture
def _no_device_and_a_fresh_run(monkeypatch):
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    yield
    engine_worker_link.reset_run_state_for_testing()


@pytest.mark.qt
def test_the_owner_runs_on_a_session_that_opened_its_wake_pipe_by_name(qt_app, named_pipes,
                                                                        _no_device_and_a_fresh_run):
    # The real owner and the real session (the worker in this process), the configure carrying a name: no pipe end is
    # in the payload, the session's publishes wake the owner through the end the session opened itself, the main side
    # gives back its own writer end and the name at the configure's reply, and the session's end is still seen as the
    # pipe's end (the owner recovers onto a second session, opened by name again).
    from core.process.types import MessageType
    from core.visualizer_engine.wake_channel import WakeName
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from widgets.spotify_visualizer import engine_worker_link

    pcm = paced_pcm(3.0)
    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        _pump(rig, 0.8)
        (configure,) = [payload for message, payload in stand_in.sent if message == MessageType.VIS_CONFIGURE]
        assert isinstance(configure["wake"], WakeName) and not _connections_in(configure)
        pickle.dumps({key: value for key, value in configure.items() if key != "activation"})   # plain data
        first = owner._worker
        assert first is not None and first.configured
        assert named_pipes.opened == named_pipes.released == [configure["wake"].path]   # opened, then given back
        assert not named_pipes.channels[0].holds_sender and not named_pipes.live
        presented = len(rig.published)
        _pump(rig, 1.0)
        assert len(rig.published) > presented + 20                 # woken through the session's own end
        stand_in.worker._close_session()                           # the session ends behind the owner's back
        _pump(rig, 20.0, until=lambda: owner._worker is not first and owner._worker is not None
              and owner._worker.configured and owner._mode_transition_phase == "idle")
        assert owner._worker is not None and owner._worker is not first
        assert len(named_pipes.opened) == len(named_pipes.released) == 2 and not named_pipes.live
    finally:
        rig.close()
        stand_in.close()
    assert all(not channel.holds_sender for channel in named_pipes.channels)


@pytest.mark.qt
@pytest.mark.parametrize("answered", (False, True))
def test_a_configure_that_is_never_decoded_leaves_the_link_holding_nothing_after_its_close(qt_app, named_pipes,
                                                                                         monkeypatch, answered):
    # The worker dies before it decodes its configure (the supervisor here never answers): until the link closes it
    # holds its reader, its own writer end and the name, and its close gives all three back. Nothing was registered
    # with the resource sharer at any point, so there is nothing a dead worker could have left uncollected. With an
    # answer the writer end and the name go at the reply instead.
    from core.process.types import MessageType, WorkerResponse
    from core.visualizer_engine.wake_channel import WakeName
    from tests.test_visualizer_ordered_control_delivery import _SharerSpy
    from tests.test_visualizer_owner_engine_worker_liveness import _ManualSupervisor
    from widgets.spotify_visualizer.engine_worker_link import ACTIVATION_KEYS, EngineWorkerLink

    spy = _SharerSpy(monkeypatch)
    supervisor = _ManualSupervisor()
    link = EngineWorkerLink(supervisor, on_lost=lambda _link, _reason: None)
    try:
        link.configure(runtime_generation=1, mode="spectrum", bar_count=32,
                       activation={key: None for key in ACTIVATION_KEYS}, on_configured=lambda _identity: None)
        (channel,) = named_pipes.channels
        (payload,) = supervisor.payloads
        assert isinstance(payload["wake"], WakeName) and not _connections_in(payload)
        pickle.dumps(payload)                                       # the whole configure is plain data
        assert channel.holds_sender and named_pipes.live and not named_pipes.released
        if answered:
            (_message, correlation), = supervisor.sent
            supervisor.callbacks[correlation](WorkerResponse(
                msg_type=MessageType.VIS_CONFIGURE, seq_no=0, correlation_id=correlation, success=True,
                payload={"engine_generation": 1, "activation_id": 1}))
            gate._event_loop_for(qt_app, 5.0, until=lambda: link.configured)
            assert not channel.holds_sender and not named_pipes.live and len(named_pipes.released) == 1
    finally:
        link.close()
    assert not channel.holds_sender and not named_pipes.live and len(named_pipes.released) == 1
    assert channel.receiver.closed and spy.made == []

"""Native core P2b, work order 5 slice 5.3 (the rest): audio device changes in the engine worker's device session.

The production session (worker-paced, no recorded PCM) opens the loopback device through the audio worker's normal path
on its capture lane. Here the device constructor is replaced by a loopback stand-in (no device is ever opened): a
stream with its own delivery thread (a device's own clock, concurrent with the tick, unlike the paced source), bound
at open to the default output, delivering one 10 ms block per period while the player renders to that output (a WASAPI
loopback stream delivers nothing for an output nothing renders to). The session's delivery watch (a count of cadence
steps with no new capture publication while Media plays, ``EngineSession.SILENT_CAPTURE_STEPS_BEFORE_REOPEN``) reopens
the stream once, through the audio worker's own restart, which binds the current default. Each test runs the session
with the watch and, as its negative control, without it (the count out of reach: the pre-5.3 session).
"""
from __future__ import annotations

import logging
import multiprocessing
import sys
import threading
import time

import pytest

from utils.audio_capture import AudioCaptureBackend


@pytest.fixture(autouse=True)
def _no_device(monkeypatch):
    from core.visualizer_engine.engine_worker import EngineSession

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)


class _Outputs:
    """The system's audio outputs as the loopback sees them: which one is the default, which one the player renders to
    (it follows the default unless pinned; None: nothing renders), whether it renders digital silence, and each one's
    format. Records the output every stream open bound to."""

    FORMATS = {"A": (48000, 2), "B": (44100, 6)}

    def __init__(self) -> None:
        self.default: str | None = "A"
        self.rendering: str | None = "A"
        self.silent = False
        self.opened: list[str] = []
        self._lock = threading.Lock()

    def note_open(self, endpoint: str) -> None:
        with self._lock:
            self.opened.append(endpoint)

    def switch_default(self, endpoint: str | None, *, player_follows: bool = True) -> None:
        self.default = endpoint
        if player_follows:
            self.rendering = endpoint


class _LoopbackStandIn(AudioCaptureBackend):
    """A loopback stream stand-in (see the module docstring). ``die`` ends its delivery thread as an invalidated
    stream's thread ends (no stop: ``is_running`` stays True); ``garble`` makes every later packet raise in the audio
    worker's capture callback (a device that fails mid-stream: callbacks arrive, nothing is published). ``restart``
    stops and opens again on the current default, as PyAudioWPatch's restart re-initialises PortAudio; a reopen clears
    what made the old stream fail."""

    def __init__(self, outputs: _Outputs, config=None) -> None:
        self._outputs = outputs
        self._config = config
        self._negotiated_block_size = 0
        self._callback = None
        self._saved_callback = None
        self._endpoint: str | None = None
        self._rate, self._channels = 48000, 2
        self._halt = threading.Event()
        self._thread: threading.Thread | None = None
        self.garbled = False
        self.restarts = 0

    def start(self, callback) -> bool:
        endpoint = self._outputs.default
        if endpoint is None:
            self._note_capture_failed()
            return False                                   # no output device: the open fails
        self._endpoint = endpoint
        self._rate, self._channels = self._outputs.FORMATS[endpoint]
        self._callback = self._saved_callback = callback
        self._halt = threading.Event()
        self._note_capture_starting()
        self._thread = threading.Thread(target=self._deliver, args=(self._halt, callback), daemon=True,
                                        name="loopback-stand-in")
        self._thread.start()
        self._outputs.note_open(endpoint)
        return True

    def _deliver(self, halt: threading.Event, callback) -> None:
        import numpy as np

        rate, channels, endpoint = self._rate, self._channels, self._endpoint
        block = rate // 100
        phase = 0
        while not halt.wait(0.01):                         # the device's own period
            if self._outputs.rendering != endpoint:
                continue                                   # nothing renders here: the loopback delivers nothing
            if self.garbled:
                packet = np.full((block, channels), "x", dtype=object)
            elif self._outputs.silent:
                packet = np.zeros((block, channels), dtype=np.float32)
            else:
                t = (np.arange(block) + phase) / rate
                tone = (0.3 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
                packet = np.repeat(tone[:, None], channels, axis=1)
            phase += block
            callback(packet)
            self._note_capture_callback()

    def die(self) -> None:
        self._halt.set()                                   # the stream's thread ends; nobody stopped the stream

    def garble(self) -> None:
        self.garbled = True

    def stop(self) -> None:
        self._halt.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(2.0)
        self._callback = None
        self._note_capture_stopped()

    def restart(self) -> bool:
        self.restarts += 1
        self.stop()
        self.garbled = False
        return self._saved_callback is not None and self.start(self._saved_callback)

    def is_running(self) -> bool:
        return self._callback is not None

    @property
    def sample_rate(self) -> int:
        return self._rate

    @property
    def channels(self) -> int:
        return self._channels


def _duplicate(conn):
    from multiprocessing import reduction

    if sys.platform == "win32":
        return type(conn)(reduction.duplicate(conn.fileno(), inheritable=False), readable=False, writable=True)
    import os

    return type(conn)(os.dup(conn.fileno()), readable=False, writable=True)


def _device_session(monkeypatch, outputs: _Outputs, *, watch: bool):
    """A production session (worker-paced, no recorded PCM) in this process on the stand-in device. ``watch`` False
    puts the delivery watch's count out of reach (the pre-5.3 session)."""
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    monkeypatch.setattr(EngineSession, "SILENT_CAPTURE_STEPS_BEFORE_REOPEN", 30 if watch else 10**9)
    backends: list[_LoopbackStandIn] = []

    def device(config=None):
        backend = _LoopbackStandIn(outputs, config)
        backends.append(backend)
        return backend

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", device)
    reader = PacketMailbox(role="reader")
    receiver, sender = multiprocessing.Pipe(duplex=False)
    ended = threading.Event()
    reader.listen_for_wakes(receiver, on_closed=ended.set)
    session = EngineSession(mapping=reader.mapping_name, mode="spectrum", runtime_generation=1, inputs="live",
                            order="free", cadence="worker", wake=_duplicate(sender))
    sender.close()
    return session, reader, receiver, ended, backends


def _until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _publishing(session, *, for_s: float = 0.3) -> bool:
    """Whether the engine accepts new capture publications: five more within about ``for_s`` (a second's slack)."""
    engine = session._engine
    before = engine.capture_publications()
    return _until(lambda: engine.capture_publications() >= before + 5, for_s + 1.0)


def _steps(session) -> int:
    return int(session._controller.logical_runtime.describe()["steps"])


def _wait_steps(session, count: int) -> None:
    start = _steps(session)
    assert _until(lambda: _steps(session) >= start + count, count / 30.0 + 5.0)


def _started(session, outputs) -> None:
    session.start(True)
    assert _until(lambda: outputs.opened == ["A"]) and _publishing(session)


def _closed(session, reader, receiver) -> None:
    session.close()
    reader.close()
    receiver.close()


def _no_worker_failure(session, ended) -> None:
    """A device problem is never a worker failure: no failed step (nothing towards ``FAILED_STEPS_BEFORE_CLOSE``), the
    session not failed closed and its wake pipe open (the owner sees no session end, so nothing counts towards the
    two-strike rule)."""
    assert session._controller.logical_runtime.describe()["step_failures"] == 0
    assert session.failed is None and not ended.is_set()


# --------------------------------------------------------------------------------------- a default-output switch


@pytest.mark.qt
@pytest.mark.parametrize("watch", (True, False), ids=("watch", "pre_fix"))
def test_a_default_output_switch_mid_song_is_followed_without_waiting_for_a_play_edge(qt_app, monkeypatch, watch):
    # The player moves to the new default (B: another rate and six channels) and the old output's loopback goes quiet.
    # With the watch the session reopens once on B, mid-song, and the device publishes again. Negative control (the
    # pre-5.3 session): the capture stays on A, silent, until Media's next play edge, whose wake restarts the stale
    # capture onto B (in process, the only trigger; the worker shares it through ``apply_playback_edge``).
    outputs = _Outputs()
    session, reader, receiver, ended, backends = _device_session(monkeypatch, outputs, watch=watch)
    try:
        _started(session, outputs)
        outputs.switch_default("B")
        if not watch:
            _wait_steps(session, 120)
            assert outputs.opened == ["A"] and not _publishing(session, for_s=0.2)
            assert session.capture_reopens == 0
            session.set_playing(False)
            session.set_playing(True)                      # Media's play edge: the in-process trigger
            assert _until(lambda: outputs.opened == ["A", "B"]) and _publishing(session)
            return
        assert _until(lambda: outputs.opened == ["A", "B"]), outputs.opened
        assert _publishing(session)
        assert _until(lambda: session.device_report()["capture_resumed"] == 1)
        assert session.device_report() == {"capture_failed": False, "capture_reopens": 1, "capture_resumed": 1}
        assert len(backends) == 1 and backends[0].restarts == 1          # the audio worker's restart, not a new owner
        _no_worker_failure(session, ended)
        report = session.finish()
        assert report["engine"]["capture_reopens"] == 1 and report["engine"]["capture_resumed"] == 1
    finally:
        _closed(session, reader, receiver)


@pytest.mark.qt
def test_a_player_pinned_to_the_old_output_keeps_the_capture_where_the_music_is(qt_app, monkeypatch):
    # Windows' default moves to B but the player stays on A: A's loopback still carries the music, so nothing reopens
    # (an IMMNotificationClient follow of the default would have moved capture to the silent output).
    outputs = _Outputs()
    session, reader, receiver, ended, _backends = _device_session(monkeypatch, outputs, watch=True)
    try:
        _started(session, outputs)
        outputs.switch_default("B", player_follows=False)
        _wait_steps(session, 120)
        assert outputs.opened == ["A"] and _publishing(session) and session.capture_reopens == 0
        _no_worker_failure(session, ended)
    finally:
        _closed(session, reader, receiver)


# ------------------------------------------------------------------------------------ a device that fails mid-stream


@pytest.mark.qt
@pytest.mark.parametrize("watch", (True, False), ids=("watch", "pre_fix"))
def test_a_device_that_raises_mid_stream_is_reopened(qt_app, monkeypatch, watch):
    # Its callbacks keep arriving but every packet raises in the audio worker's capture callback, so nothing is
    # published (the dead stream is silent: the session saw nothing wrong). With the watch: one reopen, and the reopened
    # stream publishes. Negative control: nothing is published again for the rest of the song.
    outputs = _Outputs()
    session, reader, receiver, ended, backends = _device_session(monkeypatch, outputs, watch=watch)
    try:
        _started(session, outputs)
        backends[0].garble()
        if not watch:
            _wait_steps(session, 120)
            assert backends[0].restarts == 0 and not _publishing(session, for_s=0.2)
            assert not session.capture_failed                # running, and silent: nothing reports it
            return
        assert _until(lambda: backends[0].restarts == 1)
        assert _publishing(session) and session.capture_reopens == 1
        _no_worker_failure(session, ended)
    finally:
        _closed(session, reader, receiver)


# ---------------------------------------------------------------------------------- a device whose callbacks stop


@pytest.mark.qt
@pytest.mark.parametrize("watch", (True, False), ids=("watch", "pre_fix"))
def test_a_device_whose_callbacks_stop_is_reopened_once_per_silent_run(qt_app, monkeypatch, watch):
    # The stream's thread ends (an invalidated device: nobody stopped the stream, so the audio worker still calls it
    # running). With the watch: one reopen; while the reopened stream stays silent (nothing renders) there is no second
    # one (never a retry loop); it publishing again re-arms the watch, and a later stop is reopened again. Negative
    # control: never reopened.
    outputs = _Outputs()
    session, reader, receiver, ended, backends = _device_session(monkeypatch, outputs, watch=watch)
    try:
        _started(session, outputs)
        outputs.rendering = None                             # the stream goes quiet ...
        backends[0].die()                                    # ... and its thread ends
        if not watch:
            _wait_steps(session, 120)
            assert backends[0].restarts == 0 and session.capture_reopens == 0
            assert not session.capture_failed
            return
        assert _until(lambda: backends[0].restarts == 1)
        _wait_steps(session, 150)                            # five silent runs' worth: still one reopen
        assert backends[0].restarts == 1 and session.capture_reopens == 1
        outputs.rendering = "A"                              # the reopened stream delivers: the watch re-arms
        assert _publishing(session)
        assert _until(lambda: session.device_report()["capture_resumed"] == 1)
        backends[0].die()
        assert _until(lambda: backends[0].restarts == 2) and _publishing(session)
        assert session.capture_reopens == 2
        _no_worker_failure(session, ended)
    finally:
        _closed(session, reader, receiver)


@pytest.mark.qt
@pytest.mark.parametrize("watch", (True, False), ids=("watch", "pre_fix"))
def test_an_unplugged_device_with_no_output_left_is_a_device_failure_never_a_worker_failure(qt_app, monkeypatch,
                                                                                             watch):
    # The only output goes away: the stream dies and its reopen finds no default output. With the watch that reopen
    # fails and the session reports the device failure in its replies (A7-L4's state: ``capture_failed``), keeps
    # running (no step failure, no session end: nothing counts towards the owner's two-strike rule) and retries at the
    # next capture edge, which opens the output plugged in meanwhile. Negative control: the dead stream is never
    # reported (``capture_failed`` stays False, the replies say all is well).
    from core.process.types import MessageType, WorkerMessage
    from core.visualizer_engine.engine_worker import VisualizerEngineWorker

    outputs = _Outputs()
    session, reader, receiver, ended, backends = _device_session(monkeypatch, outputs, watch=watch)
    worker = VisualizerEngineWorker(None, None)
    worker._session = session

    def view() -> dict:
        reply = worker.handle_message(WorkerMessage(msg_type=MessageType.VIS_SET_VIEW, seq_no=1, correlation_id="1",
                                                    payload={"extent": (400.0, 300.0), "rotations": {}}))
        assert reply.success
        return reply.payload

    try:
        _started(session, outputs)
        outputs.switch_default(None)
        backends[0].die()
        if not watch:
            _wait_steps(session, 120)
            assert view() == {"capture_failed": False, "capture_reopens": 0, "capture_resumed": 0}
            return
        assert _until(lambda: session.capture_failed)
        assert view() == {"capture_failed": True, "capture_reopens": 1, "capture_resumed": 0}
        assert not session._engine.is_capture_running()
        _no_worker_failure(session, ended)
        outputs.switch_default("B")                          # plugged in; the next capture edge retries
        session.set_playing(False)
        session.set_playing(True)
        assert _until(lambda: outputs.opened == ["A", "B"]) and _publishing(session)
        assert _until(lambda: not session.capture_failed)
        assert view()["capture_failed"] is False
        _no_worker_failure(session, ended)
    finally:
        worker._session = None
        _closed(session, reader, receiver)


# ------------------------------------------------------------------------------ what never triggers the watch


@pytest.mark.qt
def test_digital_silence_or_a_pause_never_reopens_the_device(qt_app, monkeypatch):
    # A playing silent passage renders zeros: they arrive and are published, so the watch never counts them (a watch on
    # the analysis energy would reopen here). Paused, nothing renders and nothing arrives: not counted either (Media is
    # the one owner of "playing"). Positive control at the end: the same quiet output while Media says playing reopens.
    outputs = _Outputs()
    session, reader, receiver, ended, backends = _device_session(monkeypatch, outputs, watch=True)
    try:
        _started(session, outputs)
        outputs.silent = True
        _wait_steps(session, 150)
        assert _publishing(session) and backends[0].restarts == 0 and session.capture_reopens == 0
        session.set_playing(False)
        outputs.rendering = None
        _wait_steps(session, 150)
        assert backends[0].restarts == 0 and session.capture_reopens == 0
        session.set_playing(True)                            # Media says playing, the output stays quiet
        assert _until(lambda: session.capture_reopens == 1)
        _no_worker_failure(session, ended)
    finally:
        _closed(session, reader, receiver)


# ----------------------------------------------------------------------------- the main side logs the device state


@pytest.mark.qt
def test_the_link_logs_the_sessions_device_state_when_a_reply_changes_it(qt_app, caplog):
    # The worker process logs nowhere the main log sees, so the main side logs the device state each reply carries,
    # once per change. Negative control (the pre-5.3 link): the flag was stored without a log record.
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink

    link = EngineWorkerLink(object(), on_lost=lambda *_args: None)
    states = (
        {"capture_failed": False, "capture_reopens": 0, "capture_resumed": 0},
        {"capture_failed": False, "capture_reopens": 1, "capture_resumed": 0},
        {"capture_failed": False, "capture_reopens": 1, "capture_resumed": 1},
        {"capture_failed": False, "capture_reopens": 1, "capture_resumed": 1},
        {"capture_failed": True, "capture_reopens": 2, "capture_resumed": 1},
        {"capture_failed": False},                           # a reply from an older worker: the counts kept
    )
    try:
        with caplog.at_level(logging.INFO, logger="widgets.spotify_visualizer.engine_worker_link"):
            counts = []
            for state in states:
                before = len(caplog.records)
                link._note_device_report(state)
                counts.append(len(caplog.records) - before)
        assert counts == [0, 1, 1, 0, 2, 1]
        assert (link.capture_failed, link.capture_reopens, link.capture_resumed) == (False, 2, 1)
        assert [record.levelno for record in caplog.records].count(logging.WARNING) == 1
    finally:
        link.close()

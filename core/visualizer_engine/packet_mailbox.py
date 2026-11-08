"""The logical mailbox over the frame packet ABI (native core P2, work order 3: in-process loopback).

A drop-in for ``logical_runtime.LatestStateMailbox`` whose publications cross a real shared-memory triple buffer:
the producer encodes each logical frame (``frame_codec``) and publishes it with ``FramePacketWriter``; the consumer
reads the newest whole frame with ``FramePacketReader``, decodes it and acknowledges it. Same contract as the
in-process mailbox: one latest-wins slot (never a queue), superseded states counted, a GUI wake on the
empty -> populated edge in process (one lock serialises publish and take), and across processes one wake byte per
publish (audit C1: the reader acknowledges only after decoding, so an edge derived from its acknowledgement can be
missed for good; the owner's wake emitter coalesces repeated wakes), short-lived protected edges carried into the newest unread state until the reader
acknowledges, and a retired generation's frame never handed to a replacement runtime.

Work order 3 proves the codec and the reader on the production owner's live publication path with identical frame
digests (``tests/test_visualizer_engine_packet_mailbox.py``). Production keeps the in-process mailbox until the
engine worker (work order 4) owns the writer side; nothing here runs at rest.
"""
from __future__ import annotations

import sys
import threading
import time
import uuid
import zlib
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Callable, Literal, Optional

from core.authored_clock import authored_now
from core.performance.frame_trace import FrameTraceEvent, logical_timestamp_ns
from core.visualizer_engine import frame_codec
from core.visualizer_engine.packet_abi import (
    FIRST_SEQUENCE,
    FLAG_CHANGED,
    FLAG_MODE_REVEAL_READY,
    FLAG_PLAYING,
    FLAG_PRESENT_FRAME,
    FramePacketReader,
    FramePacketWriter,
    create_frame_mapping,
    mode_code,
)
from widgets.spotify_visualizer.logical_runtime import (
    LatestStateMailbox,
    LogicalPublication,
    _coalesce_protected_state,
)

#: 1 MiB slots hold every mode's frame (Extruded Bubble's ~617 KiB is the largest; P2 design, measured 8 Nov).
DEFAULT_SLOT_BYTES = 1 << 20


def publication_flags(state: Any) -> int:
    """The slot's ``flags``: the publication's changed / present / mode-reveal-ready / playing bits."""
    flags = 0
    for name, bit in (("changed", FLAG_CHANGED), ("present_frame", FLAG_PRESENT_FRAME),
                      ("mode_reveal_ready", FLAG_MODE_REVEAL_READY), ("playing", FLAG_PLAYING)):
        if getattr(state, name, False):
            flags |= bit
    return flags


def protected_edge_mask(state: Any) -> int:
    """The ABI's coalesced edge-kind mask: one stable bit per edge kind (process-independent, unlike ``hash``)."""
    mask = 0
    for edge in getattr(state, "protected_edges", ()) or ():
        mask |= 1 << (zlib.crc32(str(getattr(edge, "kind", "")).encode("utf-8")) % 32)
    return mask


def send_wake_byte_without_blocking(sender: Any) -> bool:
    """Write one wake byte down ``sender`` (a ``multiprocessing.Pipe`` writer end) unless its pipe is full; whether it
    was written (native core P2b slice 5.5: a full wake pipe never blocks the worker's tick).

    ``Connection.send_bytes`` blocks a writer whose reader stopped draining once the pipe's buffer fills (a stalled or
    exiting owner process), and the writer here is the worker's cadence thread. A dropped byte loses nothing: a full
    pipe means the reader already has wakes pending, and the reader takes the newest whole frame per wake (latest wins).
    Windows: one overlapped write (the pipe's handles are overlapped), cancelled when it would wait. POSIX: a
    non-blocking write of the connection's framed message (at most ``PIPE_BUF`` bytes: whole or not at all)."""
    if sys.platform == "win32":
        import _winapi

        overlapped, error = _winapi.WriteFile(sender.fileno(), b"w", overlapped=True)
        try:
            if error == _winapi.ERROR_IO_PENDING:
                overlapped.cancel()
        finally:
            written, _error = overlapped.GetOverlappedResult(True)
        return written == 1
    import os
    import struct

    descriptor = sender.fileno()
    if os.get_blocking(descriptor):
        os.set_blocking(descriptor, False)
    try:
        os.write(descriptor, struct.pack("!i", 1) + b"w")
    except BlockingIOError:
        return False
    return True


class PacketMailbox(LatestStateMailbox):
    """``LatestStateMailbox`` whose single slot is the frame packet ABI's newest whole frame.

    ``role``: "both" (in-process loopback), "reader" (the main process: creates, owns and finally unlinks the
    mapping, takes frames) or "writer" (the engine worker: attaches to ``attach`` by name and publishes).

    ``publish_stamps`` (writer side; native core P2 gate 3): stamp every slot's ``publish_ns`` with
    ``time.perf_counter_ns()`` at publish (``packet_abi``: the clock every process shares). The engine worker's
    configure turns it on only while the main process's ``--frame-trace`` is admitted (``traces_publications``);
    otherwise the slot carries 0 and nothing reads a clock. Reader side, with ``--frame-trace`` admitted in this
    process: every frame taken that carries a stamp is recorded as the trace's ``LOGICAL_PUBLISH`` at its publish time
    (the in-process mailbox records it at publish; across processes the main side sees a frame first when it takes it).
    """

    def __init__(self, *, slot_bytes: int = DEFAULT_SLOT_BYTES, generation: int = 0, engine_generation: int = 0,
                 activation_id: int = 0, mode_code: int = 0, role: Literal["both", "reader", "writer"] = "both",
                 attach: str | None = None, wake_sender: Any = None, publish_stamps: bool = False) -> None:
        super().__init__()
        self._publish_stamps = bool(publish_stamps)
        self._peeked_publish_ns = 0                  # reader side: the peeked frame's publish stamp (0: none) ...
        self._peeked_logical = 0.0                   # ... and its logical timestamp (the slot head's)
        # Across processes the GUI wake is one byte down a pipe per publish (the writer's side of
        # ``multiprocessing.Pipe``); the reader's ``listen_for_wakes`` turns it back into the wake callback, and the
        # owner's emitter coalesces repeats (``quick_presentation_sync``).
        self._wake_sender = wake_sender
        self._wakes_dropped = 0                      # writer side: wake bytes a full pipe refused (never blocked)
        self._wake_lock = threading.Lock()          # a sender close (``close_wake_sender``) never races a send
        self._wake_thread: threading.Thread | None = None
        self._wake_receiver: Any = None
        self._last_taken: LogicalPublication | None = None   # reader side: the newest publication handed out
        self._frame_completion: Callable[[Any], Any] | None = None   # reader side: the owner's frame completion
        if (role == "writer") != (attach is not None):
            raise ValueError("a writer attaches to the owner's mapping by name; readers and loopbacks create it")
        if attach is None:
            self._memory = create_frame_mapping(
                generation=generation, slot_bytes=slot_bytes, engine_generation=engine_generation,
                activation_id=activation_id, mode_code=mode_code, token=uuid.uuid4().hex[:12],
            )
        else:
            self._memory = SharedMemory(name=attach)
        self._owner = attach is None
        self._writer = FramePacketWriter(self._memory.buf) if role in ("both", "writer") else None
        self._reader = FramePacketReader(self._memory.buf) if role in ("both", "reader") else None
        # Producer side: the newest publication not yet acknowledged (its edges carry into the next one).
        self._unread: tuple[Any, int, int, int] | None = None     # (state, generation, activation, sequence)
        self._peeked: LogicalPublication | None = None
        self._closed = False
        # Writer side: checked before every publish, so a host can refuse a frame before it reaches the mapping
        # (the engine session's production-order admission failure; None otherwise: one attribute read).
        self._publish_guard: Callable[[], None] | None = None

    # ---------------------------------------------------------------------------------------------- producer

    def publish(self, state: Any, *, generation: int, activation_id: int = -1,
                now_ts: Optional[float] = None) -> int:
        wake: Optional[Callable[[], None]] = None
        guard = self._publish_guard
        if guard is not None:
            guard()                                   # raises: nothing of this frame is published
        with self._lock:
            consumed = self._writer.consumed_sequence
            previous = self._unread if self._unread is not None and self._unread[3] > consumed else None
            if previous is not None:
                self._dropped += 1
                if previous[1] == int(generation) and previous[2] == int(activation_id):
                    state = _coalesce_protected_state(previous[0], state)
            produced = float(now_ts if now_ts is not None else authored_now())
            payload = frame_codec.encode((int(generation), int(activation_id), produced, state))
            source = getattr(state, "source_timestamp", None)
            sequence = self._writer.publish(
                payload, payload_schema=frame_codec.CODEC_SCHEMA,
                logical_timestamp=float(getattr(state, "logical_timestamp", 0.0) or 0.0),
                source_timestamp=None if source is None else float(source),
                flags=publication_flags(state),
                protected_edges=protected_edge_mask(state),
                # The slot's own identity, under its seqlock (ABI 2): an in-place mode switch changes it.
                runtime_generation=int(generation), engine_generation=int(getattr(state, "engine_generation", -1)),
                activation_id=int(activation_id), mode_code=mode_code(getattr(state, "mode_id", None)),
                publish_ns=time.perf_counter_ns() if self._publish_stamps else 0,
            )
            self._unread = (state, int(generation), int(activation_id), sequence)
            self._revision += 1
            if self._wake_sender is not None:
                wake = self._send_wake                # every publish across processes (never a missed edge)
            elif previous is None:
                wake = self._wake_callback
            revision = self._revision
        if wake is not None:
            wake()
        return revision

    def set_publish_guard(self, guard: Callable[[], None] | None) -> None:
        """Writer side: ``guard()`` runs before every publish and raises to refuse the frame (None: no guard)."""
        if guard is not None and not callable(guard):
            raise TypeError("a publish guard must be callable or None")
        self._publish_guard = guard

    def write_identity(self, *, runtime_generation: int, engine_generation: int, activation_id: int,
                       mode: str | None) -> None:
        """Writer side: the header's configure-time identity (a session's configure, before any frame). Each slot
        carries its own frame's identity; the header is not updated in place."""
        with self._lock:
            self._writer.write_identity(runtime_generation=runtime_generation, engine_generation=engine_generation,
                                        activation_id=activation_id, mode_code=mode_code(mode))

    def _send_wake(self) -> None:
        with self._wake_lock:
            sender = self._wake_sender
            if sender is None:
                return
            try:
                if not send_wake_byte_without_blocking(sender):
                    self._wakes_dropped += 1        # the pipe is full: the reader has wakes pending (it coalesces)
            except (OSError, ValueError):
                pass                                # the owner has gone; its reader no longer needs waking

    @property
    def wakes_dropped(self) -> int:
        """Writer side: wake bytes a full pipe refused (the reader had wakes pending; nothing blocked)."""
        return self._wakes_dropped

    def close_wake_sender(self) -> None:
        """Writer side: close this end of the wake pipe now (idempotent). With no other writer end open the
        reader's listener sees the end of the pipe (``listen_for_wakes``' ``on_closed``): a session that fails
        outside a control message (its capture device failed to open, work order 5 slice 5.3) reports itself to the
        owner this way, without a message of its own. Publishing goes on into the mapping; nobody is woken."""
        with self._wake_lock:
            sender, self._wake_sender = self._wake_sender, None
        if sender is not None:
            try:
                sender.close()
            except OSError:
                pass

    # ---------------------------------------------------------------------------------------------- consumer

    def _read(self) -> LogicalPublication | None:
        if self._closed:
            return None                               # a closed reader has nothing (its views are released)
        if self._peeked is not None:
            return self._peeked
        packet = self._reader.read_latest()
        if packet is None:
            return None
        generation, activation_id, produced, state = frame_codec.decode(packet.payload)
        completion = self._frame_completion
        if completion is not None:
            state = completion(state)
        self._peeked = LogicalPublication(
            state=state, revision=(packet.sequence-FIRST_SEQUENCE)//2+1, generation=generation,
            activation_id=activation_id, produced_ts=produced,
        )
        self._peeked_sequence = packet.sequence
        self._peeked_publish_ns = packet.publish_ns
        self._peeked_logical = packet.logical_timestamp
        return self._peeked

    def _consume(self) -> LogicalPublication | None:
        publication = self._read()
        if publication is not None:
            self._reader.acknowledge(self._peeked_sequence)
            self._peeked = None
            self._last_taken = publication
            trace = self._frame_trace
            if trace is not None and self._peeked_publish_ns:
                # The frame's publish, at the writer's own stamp (the shared clock), recorded when this side first
                # sees it: the trace's age chain (publish -> sync -> render -> swap) then reads as in process.
                trace.record(FrameTraceEvent.LOGICAL_PUBLISH, screen_index=self._trace_screen_index,
                             revision=publication.revision,
                             logical_timestamp_ns=logical_timestamp_ns(self._peeked_logical),
                             auxiliary=int(publication.generation), timestamp_ns=self._peeked_publish_ns)
        return publication

    @property
    def traces_publications(self) -> bool:
        """Whether this process's ``--frame-trace`` is admitted (read once, at construction): the reader then wants
        the writer's ``publish_stamps``."""
        return self._frame_trace is not None

    def set_frame_completion(self, completion: Callable[[Any], Any] | None) -> None:
        """Reader side: ``completion(state)`` runs on every decoded frame and returns the frame presentation reads
        (work order 5 slice 5.4: the owner completes a frame with the presentation data it holds and the worker never
        sees, the reflected wallpaper; checkpoint audit 7, A7-M1). None: frames as decoded (one attribute read)."""
        if completion is not None and not callable(completion):
            raise TypeError("a frame completion must be callable or None")
        with self._lock:
            self._frame_completion = completion

    @property
    def last_taken(self) -> LogicalPublication | None:
        """Reader side: the newest publication a take handed out (the owner holds it while a failed session is
        replaced, work order 5 slice 5.2), or None."""
        with self._lock:
            return self._last_taken

    def peek(self) -> Optional[LogicalPublication]:
        with self._lock:
            return self._read()

    def take(self) -> Optional[LogicalPublication]:
        with self._lock:
            return self._consume()

    def take_for_generation(self, generation: int) -> Optional[LogicalPublication]:
        with self._lock:
            publication = self._consume()
            if publication is None or int(publication.generation) != int(generation):
                return None
            return publication

    def set_wake_callback(self, callback: Optional[Callable[[], None]]) -> None:
        with self._lock:
            if callback is not None and not callable(callback):
                raise TypeError("logical mailbox wake callback must be callable or None")
            self._wake_callback = callback
            pending = not self._closed and (self._peeked is not None or (
                self._writer is not None and self._unread is not None
                and self._unread[3] > self._writer.consumed_sequence) or (
                self._writer is None and self._reader is not None and self._reader.has_unread()))
        if callback is not None and pending:
            callback()

    def listen_for_wakes(self, receiver: Any, *, on_closed: Optional[Callable[[], None]] = None) -> None:
        """Reader side: a daemon thread blocks on ``receiver`` (the pipe's other end) and runs the wake callback for
        each byte. It blocks, never polls; closing the mailbox closes the pipe and ends it. ``on_closed`` runs once
        (on the listener thread) when the pipe ends while this mailbox is still open: every writer end is closed, so
        the session that held it ended (closed after a failure, or its process died; work order 5 slice 5.2). The
        reader must have closed its own copy of the writer end for that edge to exist."""
        if self._reader is None or self._wake_thread is not None:
            raise RuntimeError("only a reader listens for wakes, once")
        if on_closed is not None and not callable(on_closed):
            raise TypeError("on_closed must be callable or None")
        self._wake_receiver = receiver

        def listen() -> None:
            while True:
                try:
                    receiver.recv_bytes()
                except (EOFError, OSError, ValueError):
                    with self._lock:
                        closed = self._closed
                    if on_closed is not None and not closed:
                        on_closed()
                    return
                with self._lock:
                    callback = self._wake_callback
                if callback is not None:
                    callback()

        self._wake_thread = threading.Thread(target=listen, name="srpss-visualizer-engine-wake", daemon=True)
        self._wake_thread.start()

    def clear(self) -> None:
        with self._lock:
            if self._reader is None:
                # Writer (the engine worker): the producer forgets its unread record and the writer its pending edges,
                # so the next publication carries none of them, neither in the frame (no coalesce) nor in the slot's
                # edge mask, whatever its identity (checkpoint audit 5, A5-L3: the mask kept same-identity edges, and
                # only the identity filter dropped them across a switch). As the in-process mailbox's clear drops
                # them. The newest slot already in the mapping stays: it is the reader's to drop (the main process
                # clears its own mailbox), and a written slot never changes under a reader.
                self._unread = None
                self._writer.drop_pending_edges()
                return
            self._consume()
            self._peeked = None

    # ----------------------------------------------------------------------------------------------- lifetime

    @property
    def mapping_name(self) -> str:
        return self._memory.name

    def close(self) -> None:
        """Release both views, then close and unlink the mapping (the owner's job; idempotent)."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            with self._wake_lock:
                sender, self._wake_sender = self._wake_sender, None
            for end in (self._wake_receiver, sender):
                if end is not None:
                    try:
                        end.close()
                    except OSError:
                        pass
            for side in (self._writer, self._reader):
                if side is not None:
                    side.release()
            self._memory.close()
            if self._owner:
                self._memory.unlink()

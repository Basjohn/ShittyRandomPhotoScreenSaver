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

import threading
import uuid
import zlib
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Callable, Literal, Optional

from core.authored_clock import authored_now
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


class PacketMailbox(LatestStateMailbox):
    """``LatestStateMailbox`` whose single slot is the frame packet ABI's newest whole frame.

    ``role``: "both" (in-process loopback), "reader" (the main process: creates, owns and finally unlinks the
    mapping, takes frames) or "writer" (the engine worker: attaches to ``attach`` by name and publishes).
    """

    def __init__(self, *, slot_bytes: int = DEFAULT_SLOT_BYTES, generation: int = 0, engine_generation: int = 0,
                 activation_id: int = 0, mode_code: int = 0, role: Literal["both", "reader", "writer"] = "both",
                 attach: str | None = None, wake_sender: Any = None) -> None:
        super().__init__()
        # Across processes the GUI wake is one byte down a pipe per publish (the writer's side of
        # ``multiprocessing.Pipe``); the reader's ``listen_for_wakes`` turns it back into the wake callback, and the
        # owner's emitter coalesces repeats (``quick_presentation_sync``).
        self._wake_sender = wake_sender
        self._wake_thread: threading.Thread | None = None
        self._wake_receiver: Any = None
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
        try:
            self._wake_sender.send_bytes(b"w")
        except (OSError, ValueError):
            pass                                    # the owner has gone; its reader no longer needs waking

    # ---------------------------------------------------------------------------------------------- consumer

    def _read(self) -> LogicalPublication | None:
        if self._peeked is not None:
            return self._peeked
        packet = self._reader.read_latest()
        if packet is None:
            return None
        generation, activation_id, produced, state = frame_codec.decode(packet.payload)
        self._peeked = LogicalPublication(
            state=state, revision=(packet.sequence-FIRST_SEQUENCE)//2+1, generation=generation,
            activation_id=activation_id, produced_ts=produced,
        )
        self._peeked_sequence = packet.sequence
        return self._peeked

    def _consume(self) -> LogicalPublication | None:
        publication = self._read()
        if publication is not None:
            self._reader.acknowledge(self._peeked_sequence)
            self._peeked = None
        return publication

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
            pending = self._peeked is not None or (
                self._writer is not None and self._unread is not None
                and self._unread[3] > self._writer.consumed_sequence) or (
                self._writer is None and self._reader is not None and self._reader.has_unread())
        if callback is not None and pending:
            callback()

    def listen_for_wakes(self, receiver: Any) -> None:
        """Reader side: a daemon thread blocks on ``receiver`` (the pipe's other end) and runs the wake callback for
        each byte. It blocks, never polls; closing the mailbox closes the pipe and ends it."""
        if self._reader is None or self._wake_thread is not None:
            raise RuntimeError("only a reader listens for wakes, once")
        self._wake_receiver = receiver

        def listen() -> None:
            while True:
                try:
                    receiver.recv_bytes()
                except (EOFError, OSError, ValueError):
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
                # Writer (the engine worker): the unread frame is the reader's to drop (the main process clears its
                # own mailbox); the producer forgets its unread record, so the next publication coalesces none of its
                # edges, as the in-process mailbox's clear drops them.
                self._unread = None
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
            for end in (self._wake_receiver, self._wake_sender):
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

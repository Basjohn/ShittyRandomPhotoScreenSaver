"""Native core P2 work order 3: the logical mailbox over the frame packet ABI (in-process loopback).

The production owner replays a shipped clip for every mode with its logical mailbox replaced by ``PacketMailbox``:
every frame then crosses a real shared-memory triple buffer through the exact codec, and the published frame digests
equal the in-process mailbox's. The mailbox keeps the in-process contract: latest wins, superseded states counted,
one wake per empty -> populated edge, protected edges survive skipped frames, a retired generation never leaks."""
from dataclasses import dataclass, field

import pytest

from core.visualizer_engine.packet_mailbox import PacketMailbox, protected_edge_mask


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


@pytest.mark.qt
@pytest.mark.parametrize('mode', _modes())
def test_the_production_owner_publishes_identical_frames_through_the_packet_abi(qt_app, monkeypatch, mode):
    import tools.expanded_visualizer_evidence as evidence
    import widgets.spotify_visualizer.runtime_controller as runtime_controller
    from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge

    # What the owner hands the renderer: the frames it took out of its logical mailbox (the tick digests the replay
    # returns are taken before the mailbox, so they cannot see the crossing).
    delivered: list[str] = []
    publish = VisualizerSnapshotBridge.publish

    def recording_publish(self, snapshot):
        delivered.append(evidence.frame_digest(snapshot.logical))
        return publish(self, snapshot)

    monkeypatch.setattr(VisualizerSnapshotBridge, "publish", recording_publish)
    clip = evidence.shipped_clip(1.5)
    ticked = evidence.owner_replay(clip, mode)["digests"]
    direct, delivered[:] = list(delivered), []
    made = []

    def packet_mailbox():
        mailbox = PacketMailbox()
        made.append(mailbox)
        return mailbox

    monkeypatch.setattr(runtime_controller, "LatestStateMailbox", packet_mailbox)
    try:
        assert evidence.owner_replay(clip, mode)["digests"] == ticked                # same ticks either way
        assert made and sum(mailbox.revision for mailbox in made) >= len(ticked)    # every frame crossed the ABI
    finally:
        for mailbox in made:
            mailbox.close()
    assert len(direct) > 30 and delivered == direct, mode


@dataclass(frozen=True)
class _Edge:
    kind: str
    token: int


@dataclass(frozen=True)
class _Frame:                      # a stand-in with a logical frame's identity fields, through the generic codec
    value: float
    mode_id: str = "spectrum"
    engine_generation: int = 1
    protected_edges: tuple = field(default=())
    logical_timestamp: float = 0.0


@pytest.fixture
def mailbox(monkeypatch):
    from core.visualizer_engine import frame_codec
    # Register the stand-in like a canonical frame type, for these tests only.
    ids, layouts, frozen = frame_codec._types()
    monkeypatch.setitem(ids, _Frame, len(layouts))
    monkeypatch.setitem(ids, _Edge, len(layouts)+1)
    layouts = list(layouts) + [(_Frame, tuple(_Frame.__dataclass_fields__)), (_Edge, ("kind", "token"))]
    monkeypatch.setattr(frame_codec, "_tables", (ids, layouts, frozen))
    box = PacketMailbox(slot_bytes=64 * 1024)
    yield box
    box.close()


def test_latest_wins_and_superseded_states_are_counted(mailbox):
    for value in (1.0, 2.0, 3.0):
        mailbox.publish(_Frame(value), generation=4)
    assert mailbox.peek().state.value == 3.0 and mailbox.take().state.value == 3.0
    assert mailbox.take() is None and mailbox.superseded_count == 2 and mailbox.revision == 3


def test_a_protected_edge_survives_a_skipped_frame_until_acknowledged(mailbox):
    mailbox.publish(_Frame(1.0, protected_edges=(_Edge("reveal", 7),)), generation=4, activation_id=2)
    mailbox.publish(_Frame(2.0), generation=4, activation_id=2)           # the reader skipped frame 1
    taken = mailbox.take()
    assert taken.state.value == 2.0 and taken.state.protected_edges == (_Edge("reveal", 7),)
    mailbox.publish(_Frame(3.0), generation=4, activation_id=2)           # acknowledged: not carried again
    assert mailbox.take().state.protected_edges == ()
    assert protected_edge_mask(taken.state) != 0


def test_one_wake_per_empty_to_populated_edge(mailbox):
    wakes = []
    mailbox.set_wake_callback(lambda: wakes.append(True))
    mailbox.publish(_Frame(1.0), generation=1)
    mailbox.publish(_Frame(2.0), generation=1)                            # unread: no second wake
    assert len(wakes) == 1
    mailbox.take()
    mailbox.publish(_Frame(3.0), generation=1)
    assert len(wakes) == 2


def test_a_retired_generation_never_reaches_its_replacement(mailbox):
    mailbox.publish(_Frame(1.0), generation=5)
    assert mailbox.take_for_generation(6) is None and mailbox.take() is None   # consumed and dropped
    mailbox.publish(_Frame(2.0), generation=6)
    mailbox.clear()
    assert mailbox.take() is None


def test_a_writer_side_clear_drops_its_pending_edges_from_the_frame_and_the_slot(mailbox):
    # A5-L3: the producer's clear (the session's ``stop_logical_runtime``) drops the unread frame's edges entirely: the
    # next publication of the same identity carries none, in the decoded frame or in the slot's edge mask. The slot
    # already published stays readable (the reader's to drop).
    writer = PacketMailbox(role="writer", attach=mailbox.mapping_name)
    try:
        writer.publish(_Frame(1.0, protected_edges=(_Edge("reveal", 7),)), generation=4, activation_id=2)
        writer.clear()
        writer.publish(_Frame(2.0), generation=4, activation_id=2)
        packet = mailbox._reader.read_latest()
        assert packet.protected_edge_mask == 0
    finally:
        writer.close()
    # Control: without the clear the unread edge is carried (the survival contract).
    writer = PacketMailbox(role="writer", attach=mailbox.mapping_name)
    try:
        writer.publish(_Frame(3.0, protected_edges=(_Edge("reveal", 8),)), generation=4, activation_id=2)
        writer.publish(_Frame(4.0), generation=4, activation_id=2)
        assert mailbox._reader.read_latest().protected_edge_mask != 0
    finally:
        writer.close()


def test_close_unlinks_the_mapping():
    from multiprocessing.shared_memory import SharedMemory
    box = PacketMailbox(slot_bytes=4096)
    name = box.mapping_name
    box.close()
    box.close()                                                           # idempotent
    with pytest.raises(FileNotFoundError):
        SharedMemory(name=name)

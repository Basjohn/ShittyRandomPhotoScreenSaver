"""N5.6: Extruded Bubble drawn natively in process (``--viz-in-process``, the engine worker's fallback) has its D3
geometry arena. The worker path's arena is opened by ``engine_worker_link.configure`` and written inside
``PacketMailbox.publish``; in process the ``LatestStateMailbox`` holds ``InProcessStreamArena``, which opens the arena
under label namespace 0 once a bound native item draws the stream and writes each frame's new keys before the frame is
named, so the route names every drift family instead of none. Nothing is opened for the Python route, another mode's
frame closes it, the mailbox's end closes it, and an arena another in-process stream owns is left alone."""
from __future__ import annotations

import gc
from types import SimpleNamespace

import core.visualizer_engine.extruded_bubble_native_schema as schema
from core.visualizer_engine.geometry_arena import key_of_words
from tests.test_native_eb_record_route import _Item, _family, _state
from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox

_IDENTITY = {"runtime_generation": 7, "engine_generation": 2, "activation_id": 3}


def _logical(serial: int, revision: int):
    return SimpleNamespace(runtime_generation=7, **vars(_state(_family(revision, fill=revision), serials=(serial,))))


def _publish_through(mailbox: LatestStateMailbox, *, bind: bool = True) -> dict:
    """Three in-process frames (label namespace 0) through ``mailbox`` and the route's projection: each chain key, the
    names the bound item was told, whether the arena holds the newest keys, and the arena after the mailbox's end."""
    item = _Item()
    if bind:
        schema.DRIFT.bound(item, _IDENTITY)
    keys = []
    try:
        for serial, revision in ((1, 1), (2, 1), (3, 2)):             # a new revision at the third frame
            mailbox.publish(_logical(serial, revision), generation=7, activation_id=3)
            fields = schema.DRIFT.project(mailbox.take().state)
            keys.append(key_of_words(fields["chains_geometry_key"]))
        arena = schema.stream_arena(schema.IN_PROCESS_NAMESPACE)
        result = {"keys": keys, "names": list(item.names), "arena": None if arena is None else arena.name,
                  "held": arena is not None and all(arena.holds(key) for key in keys[1:])}
    finally:
        del mailbox
        gc.collect()
        schema.DRIFT._projectors, schema.DRIFT._items = {}, []
    result["after"] = schema.stream_arena(schema.IN_PROCESS_NAMESPACE)
    return result


def test_a_natively_drawn_in_process_stream_names_every_frames_geometry():
    run = _publish_through(LatestStateMailbox())
    assert all(any(key) for key in run["keys"]) and run["keys"][0] == run["keys"][1] != run["keys"][2]
    assert run["names"] == ["", run["arena"]] and run["held"]
    assert run["after"] is None                                     # closed and unregistered with its mailbox


def test_the_python_route_opens_no_arena_and_another_mode_closes_it():
    run = _publish_through(LatestStateMailbox(), bind=False)
    assert run["arena"] is None and not any(any(key) for key in run["keys"])
    mailbox = LatestStateMailbox()
    item = _Item()
    schema.DRIFT.bound(item, _IDENTITY)
    try:
        mailbox.publish(_logical(1, 1), generation=7, activation_id=3)
        assert schema.stream_arena(schema.IN_PROCESS_NAMESPACE) is mailbox._geometry.owner is not None
        mailbox.publish(SimpleNamespace(mode_state=SimpleNamespace(), engine_generation=2, activation_id=3),
                        generation=7, activation_id=3)              # another mode's frame
        assert schema.stream_arena(schema.IN_PROCESS_NAMESPACE) is None
    finally:
        del mailbox
        gc.collect()
        schema.DRIFT._projectors, schema.DRIFT._items = {}, []


def test_an_arena_another_in_process_stream_owns_is_left_alone():
    from widgets.spotify_visualizer.extruded_bubble_drift_log import CHAIN_GEOMETRY_BYTES

    held = schema.open_stream_arena(schema.IN_PROCESS_NAMESPACE, CHAIN_GEOMETRY_BYTES * 4)
    try:
        run = _publish_through(LatestStateMailbox())
        assert run["arena"] == held.name and not any(any(key) for key in run["keys"])   # no writer of its own
        assert schema.stream_arena(schema.IN_PROCESS_NAMESPACE) is held
    finally:
        schema.close_stream_arena(held)


class _BeforeN56(LatestStateMailbox):
    """The mailbox before N5.6: no in-process arena."""

    def _geometry_for(self, state):
        return None


def test_control_without_the_in_process_arena_no_family_is_named():
    run = _publish_through(_BeforeN56())
    assert run["arena"] is None and run["names"] == [""] and not any(any(key) for key in run["keys"])

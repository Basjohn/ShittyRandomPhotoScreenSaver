"""N5.6 P: the owner replay runs Extruded Bubble's native route in process, with no engine worker and so no D3 arena
(``DriftStream.project`` then names no drift family and the core holds every drift draw). The harness's in-process
arena (``owner_render_parity.in_process_drift_arena``) stands in for the worker's side: the route names each frame's
geometry keys, their bytes are in the arena it names to the item, and everything is restored at the end."""
from __future__ import annotations

from types import SimpleNamespace

import core.visualizer_engine.extruded_bubble_native_schema as schema_module
import core.visualizer_engine.geometry_arena as arena_module
from tests.test_native_eb_record_route import _Item, _family, _state
from tools.visualizer_replay import owner_render_parity as parity


def _frames(project_through):
    """Three in-process frames (label namespace 0) through a bound route; each projection's chain key and the item's
    arena names."""
    route, item = schema_module.DriftStream(), _Item()
    route.bound(item, {"runtime_generation": 7, "engine_generation": 2, "activation_id": 3, "mode_code": 9})
    keys = []
    for serial, revision in ((1, 1), (2, 1), (3, 2)):              # a new revision at the third frame
        state = _state(_family(revision, fill=revision), serials=(serial,))
        fields = project_through(route, SimpleNamespace(runtime_generation=7, **vars(state)))
        keys.append(arena_module.key_of_words(fields["chains_geometry_key"]))
    return keys, item.names


def test_the_in_process_arena_names_every_frames_geometry():
    project = schema_module.DriftStream.project
    with parity.in_process_drift_arena() as writer:
        owner = schema_module.stream_arena(0)
        keys, names = _frames(lambda route, logical: route.project(logical))
        assert names == ["", owner.name]
        assert all(owner.holds(key) for key in keys[1:])           # the newest key and its predecessor stay resident
        assert [key[0] for key in keys] == [writer.namespace] * 3
        assert keys[0] == keys[1] != keys[2]
    assert schema_module.stream_arena(0) is None and owner.closed
    assert schema_module.DriftStream.project is project


def test_control_without_the_arena_no_family_is_named():
    # The replay as it was: no session opened an arena, so every family is absent (a zero key) and no arena is named.
    keys, names = _frames(lambda route, logical: route.project(logical))
    assert names == [""]
    assert all(not any(key) for key in keys)

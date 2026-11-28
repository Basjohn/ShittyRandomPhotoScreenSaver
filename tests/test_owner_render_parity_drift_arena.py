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


def _two_runs(arena):
    """Two in-process runs of one take through the route's shared projector (``schema.DRIFT``): each run's chain keys
    (serials 1 to 3), or the error the second run raised."""
    runs = []
    for _run in range(2):
        with arena() as _writer:
            keys = []
            try:
                for serial in (1, 2, 3):
                    state = _state(_family(1), serials=(serial,))
                    fields = schema_module.DRIFT.project(SimpleNamespace(runtime_generation=7, **vars(state)))
                    keys.append(arena_module.key_of_words(fields["chains_geometry_key"]))
            except schema_module.NativeSchemaError as exc:
                keys = str(exc)
            runs.append(keys)
    return runs


def test_two_runs_of_a_take_name_the_same_keys():
    # A coverage window against the continuous run, layer L's runs: one record bytes only under one writer namespace,
    # and the second run's serials start again (the shared projector forgets the first run's stream).
    first, second = _two_runs(parity.in_process_drift_arena)
    assert isinstance(second, list) and first == second
    assert {key[0] for key in first} == {parity.IN_PROCESS_WRITER_NAMESPACE}


def _arena_without(line: str):
    import contextlib
    import inspect
    import textwrap

    source = textwrap.dedent(inspect.getsource(parity.in_process_drift_arena.__wrapped__))
    source = source.replace("@contextlib.contextmanager\n", "")
    assert line in source
    namespace = dict(vars(parity))
    exec(compile(source.replace(line, "pass"), parity.__file__, "exec"), namespace)
    return contextlib.contextmanager(namespace["in_process_drift_arena"])


def test_control_a_random_writer_namespace_is_seen():
    arena = _arena_without("writer.namespace = IN_PROCESS_WRITER_NAMESPACE")
    first, second = _two_runs(arena)
    assert first != second


def test_control_a_projector_kept_across_runs_is_seen():
    arena = _arena_without("schema.DRIFT._projectors = {}")
    _first, second = _two_runs(arena)
    assert isinstance(second, str) and "backwards" in second


def _two_planned_runs(monkeypatch, tmp_path, run_context):
    """``_run_native`` over two planned runs (display and overscan), each projecting the take's first three frames
    through the route's shared projector; per run, its arena and its chain keys or the error it raised."""
    import rendering.native
    import rendering.quick.visualizer.native_route as route_module
    import tools.expanded_visualizer_evidence as evidence

    monkeypatch.setattr(rendering.native, "load", lambda _dir: SimpleNamespace(module=None))
    monkeypatch.setattr(evidence, "shipped_clip", lambda _seconds: SimpleNamespace(name="clip", frames=()))
    monkeypatch.setattr(route_module, "NATIVE_MODE_IDS", frozenset({"extruded_bubble"}))
    monkeypatch.setattr(parity, "_placed_runs", lambda *_a: [("extruded_bubble", "", {}, "display"),
                                                              ("extruded_bubble@overscan", "", {}, "overscan")])
    seen = []

    def native_parity(*_args, **_kwargs):
        arena = schema_module.stream_arena(0)
        try:
            keys = [arena_module.key_of_words(schema_module.DRIFT.project(SimpleNamespace(
                runtime_generation=7, **vars(_state(_family(1), serials=(serial,)))))["chains_geometry_key"])
                for serial in (1, 2, 3)]
        except schema_module.NativeSchemaError as exc:
            keys = str(exc)
        seen.append((arena, keys))
        return {"frames_drawn": [3, 3], "native_published": 3, "differing_inputs": 0, "differing_pixels_total": 0,
                "max_level": 0, "outer_origin": (0, 0), "outer_origin_device_fraction": (0, 0), "identical": True,
                "pass": True, "carried_from_accepted": [], "rule_a": {"edge_pixels_worst_frame": 0, "bound": {}}}

    monkeypatch.setattr(parity, "native_parity", native_parity)
    parity._run_native(tmp_path, module_dir=tmp_path, offers=False, mode="extruded_bubble", run_context=run_context)
    return seen


def test_each_planned_run_gets_a_fresh_arena(monkeypatch, tmp_path):
    # The overscan run replays the take from its first step: it needs its own arena and projector.
    (first_arena, first), (second_arena, second) = _two_planned_runs(monkeypatch, tmp_path, parity.in_process_drift_arena)
    assert isinstance(second, list) and first == second
    assert first_arena is not None and second_arena is not None and first_arena is not second_arena
    assert schema_module.stream_arena(0) is None


def test_control_one_arena_across_planned_runs_is_seen(monkeypatch, tmp_path):
    import contextlib

    with parity.in_process_drift_arena():
        (_a, _first), (_b, second) = _two_planned_runs(monkeypatch, tmp_path, contextlib.nullcontext)
    assert isinstance(second, str) and "backwards" in second


def test_control_without_the_arena_no_family_is_named():
    # The replay as it was: no session opened an arena, so every family is absent (a zero key) and no arena is named.
    keys, names = _frames(lambda route, logical: route.project(logical))
    assert names == [""]
    assert all(not any(key) for key in keys)

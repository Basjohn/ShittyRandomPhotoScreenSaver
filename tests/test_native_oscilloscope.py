"""N5.1: the Oscilloscope on the native core as generic mode content (D12, with N3.1's target, N3.2's instanced pass over
a storage stream and N3.4's bloom and composite).

- Its record (``core.visualizer_engine.oscilloscope_native_schema``) is a runtime schema, never compiled, carrying the
  beam's per-frame members by name (``OSCILLOSCOPE_FRAME_MEMBERS``), the composite's bloom strength, the traces' points
  as a storage stream with its used length, the beam's instances and the graticule's vertices; the route's slot holds it.
- Every member of both passes has exactly one source: the core's conventions, the settings
  (``oscilloscope_settings_values``) or the record (``oscilloscope_frame_values``), the functions the Python renderer
  calls too; the settings follow Settings and the card only, the record the logical frame only.
- With the module built: the core's blocks for both passes are the Python renderer's, byte for byte, but ``uMatrix``
  (the core's own item-to-target matrix).
- The beam's shader reads the points buffer within its length whatever the counts say.
"""
from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
WINDOW = (1920.0, 1080.0)


def _presentation(dpr: float = 1.5, **overrides):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation

    kwargs = dict(policy=get_visualizer_presentation_policy("oscilloscope"), display_size=WINDOW,
                  viewport_extent=(640.0, 360.0), outer_origin=(803.0, 517.0), dpr=dpr, border_width=2.0,
                  corner_radius=8.0)
    kwargs.update(overrides)
    return resolve_presentation(**kwargs)


def _parameters(**overrides) -> dict:
    """Test inputs (not a preset): every parameter the renderer and the route read."""
    from rendering.gl_programs.oscilloscope_options import OSC_DISPLAYS, OSC_GRATICULES

    values = {
        "osc_display": OSC_DISPLAYS[0], "osc_beam_color": (90, 255, 140, 255),
        "osc_beam_glow_color": (60, 200, 255, 255), "osc_beam_width": 1.7, "osc_glow": 0.6, "osc_analog": 0.4,
        "osc_spectral": 0.5, "osc_flare": 0.8, "osc_pulse": 0.7, "osc_graticule": OSC_GRATICULES[1],
        "osc_graticule_color": (200, 120, 80, 90),
    }
    values.update(overrides)
    return values


def _logical(step: int = 0, *, traces: int = 3, points: int = 384, **parameters):
    from widgets.spotify_visualizer.render_state import (
        OscilloscopeFrame,
        VisualizerCommonState,
        VisualizerLogicalFrame,
        freeze_render_fields,
    )

    x = np.linspace(-1.0, 1.0, points, dtype=np.float32)
    rows = [np.stack((x, 0.6 * np.sin(6.0 * x + 0.4 * step + k)), axis=1).astype(np.float32) for k in range(traces)]
    data = b"".join(row.tobytes() for row in rows)
    alphas = tuple(0.6 * (k + 1) / traces for k in range(traces - 1)) + (1.0,) if traces else ()
    return VisualizerLogicalFrame(
        runtime_generation=1, engine_generation=2, activation_id=3, source_generation=2, source_activation_id=3,
        mode_id="oscilloscope", playing=True, logical_timestamp=1.0 + step / 60.0, source_timestamp=1.0, changed=True,
        present_frame=True, mode_reveal_ready=True, common=VisualizerCommonState(bars=(), bar_count=0),
        mode_state=OscilloscopeFrame(points=data, trace_alphas=alphas, flare=0.3 + 0.05 * step, drive=0.4, tone=0.6,
                                     animation_time=step / 60.0,
                                     parameters=freeze_render_fields(_parameters(**parameters))),
    )


def _card(presentation) -> dict:
    from rendering.native.composite import composite_geometry, window_pixel_ratio
    from rendering.quick.visualizer.native_route import NativeVisualizerRoute

    dpr = float(presentation.dpr)
    pixels = (int(round(WINDOW[0] * dpr)), int(round(WINDOW[1] * dpr)))
    geometry = composite_geometry(presentation, quad_aligned=True, pixel_ratio=window_pixel_ratio(WINDOW, pixels))
    route = NativeVisualizerRoute(None, SimpleNamespace())
    return route.card(presentation, SimpleNamespace(presentation=presentation), geometry, (WINDOW, pixels))


def _settings(logical, presentation, card) -> dict:
    from rendering.quick.visualizer.native_route import OSCILLOSCOPE_SETTINGS

    return OSCILLOSCOPE_SETTINGS(SimpleNamespace(logical=logical, presentation=presentation), card)


_BLOCKS = (("oscilloscope_beam.vert", "OscilloscopeBeam"), ("oscilloscope_graticule.vert", "OscilloscopeGraticule"))


def _members(filename: str, block: str) -> set[str]:
    from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl
    from widgets.spotify_visualizer import shaders

    source = shaders.compose_shader_source(Path(shaders.__file__).resolve().parent / filename)
    return {name for name, _kind in block_layout_from_glsl(block_declaration(source, block)).fields}


_STREAM_FIELDS = {"osc_points", "osc_point_floats"}
_COUNT_FIELDS = {"osc_segments", "osc_graticule_vertices"}
#: The composite step's members (the core's shader; ``post_stages`` STAGE_MEMBERS' overlay_glow).
_COMPOSITE_MEMBERS = {"u_bloom_strength", "u_hdr_exposure"}


# ------------------------------------------------------------------------------------------------- the record

def test_the_record_is_a_runtime_schema_of_the_frame_members_streams_and_counts():
    from core.visualizer_engine import native_schema
    from core.visualizer_engine import oscilloscope_native_schema as schema_module
    from core.visualizer_engine.packet_abi import SLOT_OVERHEAD
    from rendering.gl_programs.oscilloscope_program import MAX_TRACES, TRACE_POINTS
    from rendering.quick.visualizer import native_route
    from rendering.quick.visualizer.implementations.oscilloscope import OSCILLOSCOPE_FRAME_MEMBERS

    schema = schema_module.SCHEMA
    assert schema.schema_id in native_schema.runtime_schemas()
    assert schema.schema_id not in native_schema.compiled_schemas()
    assert native_schema.schema_for_mode("oscilloscope") is schema
    assert set(schema.fields) == set(OSCILLOSCOPE_FRAME_MEMBERS) | _STREAM_FIELDS | _COUNT_FIELDS
    # The capacities are the runtime's (derived, never restated): every trace of the afterglow and the live one.
    assert (schema_module.TRACES, schema_module.TRACE_POINTS) == (MAX_TRACES, TRACE_POINTS)
    assert schema.layout.field("osc_points").size == MAX_TRACES * TRACE_POINTS * 8
    # Version 1's layout (a change is a new version).
    assert (schema.layout.size, schema.layout.fingerprint()) == (49376, "c1f1de544477b807")
    # The route's slot holds it in whole 4096-byte steps.
    assert schema.layout.size <= native_route._slot_bytes("oscilloscope") - SLOT_OVERHEAD
    assert native_route._slot_bytes("oscilloscope") % native_route._SLOT_BYTES == 0


def test_the_record_round_trips_and_carries_the_renderers_values():
    from core.visualizer_engine import oscilloscope_native_schema as schema_module
    from core.visualizer_engine.native_schema import NativeSchemaError
    from rendering.quick.visualizer.implementations.oscilloscope import oscilloscope_frame_values

    logical = _logical(4)
    decoded = schema_module.decode(schema_module.encode(logical))
    assert decoded == schema_module.project(logical)
    values = oscilloscope_frame_values(logical)
    state = logical.mode_state
    count = len(state.trace_alphas)
    assert decoded["u_alpha"][:count] == pytest.approx(state.trace_alphas)
    assert all(alpha == 0.0 for alpha in decoded["u_alpha"][count:])
    assert decoded["osc_points"][:len(state.points)] == state.points
    assert decoded["osc_points"][len(state.points):] == bytes(len(decoded["osc_points"]) - len(state.points))
    assert decoded["osc_point_floats"] == len(state.points) // 4
    assert decoded["osc_segments"] == count * (state.trace_points - 1)
    assert decoded["u_points"] == state.trace_points
    for name in ("u_widen", "u_bright", "u_hot", "u_bloom_strength"):
        assert decoded[name] == values[name]
    assert decoded["osc_graticule_vertices"] == 4
    # The graticule's style off draws none; Glow 0 sends no light.
    from rendering.gl_programs.oscilloscope_options import OSC_GRATICULES

    off = schema_module.decode(schema_module.encode(_logical(4, osc_graticule=OSC_GRATICULES[0], osc_glow=0.0)))
    assert off["osc_graticule_vertices"] == 0 and off["u_bloom_strength"] == 0.0
    # The flare moves the widening and the strength; the frame alone carries them.
    assert schema_module.project(_logical(9))["u_widen"] != decoded["u_widen"]
    # A non-finite value is refused by the writer (control: the encoder checks what it writes).
    broken = _logical(1)
    object.__setattr__(broken.mode_state, "flare", float("nan"))
    with pytest.raises(NativeSchemaError):
        schema_module.encode(broken)


# ------------------------------------------------------------------------------------------------- the sources

@pytest.mark.parametrize("fraction", (0.0, 0.0002, -0.0002, 0.0005, 0.0009, -0.0009, 0.25))
def test_the_cards_scene_item_is_pythons_item_pixel_rect(fraction):
    # Checkpoint audit 10, M2: one owner of the item's rect. The card's scene_item, mapped back to the window through
    # the card's exact window_from_target, is the Python renderer's item_pixel_rect of its own float32 item matrix, also
    # where an edge lies within 1e-3 of a whole device pixel (the core's own snap disagreed there at ABI 27).
    from rendering.native.spectrum import _ortho_item_matrix
    from rendering.quick.scene3d.frame import item_pixel_rect
    from rendering.quick.visualizer.native_route import content_host_origin

    dpr = 1.5
    origin = ((46.0 + fraction) / dpr, (44.0 + fraction) / dpr)
    presentation = _presentation(dpr, outer_origin=origin)
    card = _card(presentation)
    pixels = (int(round(WINDOW[0] * dpr)), int(round(WINDOW[1] * dpr)))
    host = content_host_origin(presentation)
    frame = SimpleNamespace(matrix_values=_ortho_item_matrix(WINDOW, host, single=True),
                            logical_size=tuple(float(v) for v in card["item_size"]), viewport=(0, 0, *pixels))
    expected = item_pixel_rect(frame)                                   # (left, bottom, width, height), window pixels
    left, top, width, height = card["scene_item"]
    a, b, c, d, e, f = card["window_from_target"]
    corners = [(a * x + b * y + c, d * x + e * y + f) for x, y in ((left, top), (left + width, top + height))]
    xs, ys = sorted(p[0] for p in corners), sorted(p[1] for p in corners)
    assert (xs[0], ys[0], xs[1] - xs[0], ys[1] - ys[0]) == tuple(float(v) for v in expected)
    assert all(v == int(v) for v in card["scene_item"]) and width >= 1 and height >= 1


def test_rule_a_judges_the_beams_one_level_pixels_against_pythons_own_placement_variance():
    # D12 "The pixel tolerance", Oscilloscope (lead's decision 21 Nov): one-level pixels outside the translucency mask
    # up to Python's own measured placement variance (52 a frame); rule (a)'s 2-level ties and every other limit as
    # for any composite mode. Spline Curve keeps none (the class is the Oscilloscope's only).
    from tools.visualizer_replay import owner_render_parity as parity

    reference = np.full((40, 80, 3), 40, np.uint8)
    cap = parity.RULE_A_SCATTER_PIXELS["oscilloscope"]
    mask = np.zeros((40, 80), bool)

    def frame(count: int, level: int = 1):
        drawn = reference.copy()
        for k in range(count):                      # spread out: every pixel its own (no neighbour past allowance)
            drawn[(k * 3) % 40, (k * 7) % 80] += level
        return drawn

    assert parity.rule_a_frame(frame(cap), reference, mask, "oscilloscope")["pass"]
    assert not parity.rule_a_frame(frame(cap + 1), reference, mask, "oscilloscope")["pass"]
    tie_cap = parity.RULE_A_EDGE_PIXELS_PER_FRAME
    assert not parity.rule_a_frame(frame(tie_cap + 1), reference, mask, "devcurve")["pass"]
    # A one-level shift of the whole beam (here the whole frame) is far past the class.
    assert not parity.rule_a_frame(reference + 1, reference, mask, "oscilloscope")["pass"]


def test_a_record_drawing_segments_with_fewer_than_two_points_is_refused(monkeypatch):
    # Checkpoint audit 10, L2: the beam divides by u_points - 1; the schema's checks are "at most" only.
    from core.visualizer_engine import oscilloscope_native_schema as schema_module
    from core.visualizer_engine.native_schema import NativeSchemaError
    from rendering.quick.visualizer.implementations import oscilloscope as implementation

    logical = _logical(0)
    real = implementation.oscilloscope_frame_values
    schema_module.encode(logical)                                       # control: the frame as drawn is admitted
    monkeypatch.setattr(implementation, "oscilloscope_frame_values", lambda frame: dict(real(frame), u_points=1))
    with pytest.raises(NativeSchemaError, match="at least 2 points"):
        schema_module.encode(logical)
    # No segments, no division: one point a trace and nothing drawn is admitted.
    monkeypatch.setattr(implementation, "oscilloscope_frame_values",
                        lambda frame: dict(real(frame), u_points=1, osc_segments=0))
    schema_module.encode(logical)


def test_every_member_of_both_passes_has_exactly_one_source():
    from core.visualizer_engine import oscilloscope_native_schema as schema_module
    from rendering.native.mode import MODE_CORE_MEMBERS

    presentation = _presentation()
    settings = _settings(_logical(), presentation, _card(presentation))
    record = set(schema_module.FIELD_NAMES)
    core = set(MODE_CORE_MEMBERS)
    assert not (set(settings) & record) and not (set(settings) & core) and not (record & core)
    declared = set().union(*(_members(f, b) for f, b in _BLOCKS))
    for filename, block in _BLOCKS:
        members = _members(filename, block)
        assert members <= set(settings) | record | core, (filename, members - (set(settings) | record | core))
    # Every setting and every record field has a reader: a block member, the composite's, a stream or a draw count.
    assert set(settings) <= declared | _COMPOSITE_MEMBERS
    assert record - _STREAM_FIELDS - _COUNT_FIELDS <= declared | _COMPOSITE_MEMBERS
    # Control: a member left out of the settings is caught.
    assert not _members(*_BLOCKS[0]) <= (set(settings) - {"uCoreBase"}) | record | core


def test_the_settings_follow_settings_and_the_card_only():
    presentation = _presentation()
    card = _card(presentation)
    base = _settings(_logical(0), presentation, card)
    assert _settings(_logical(7, traces=5), presentation, card) == base     # another frame, the same settings
    # Controls: a Setting and the card's content rect each change them.
    assert _settings(_logical(0, osc_beam_width=3.0), presentation, card) != base
    moved = dict(card, content_rect=[v + 1.0 for v in card["content_rect"]])
    assert _settings(_logical(0), presentation, moved) != base


def test_the_programs_follow_the_glow_setting():
    from rendering.native.mode import BloomStep, CompositeStep
    from rendering.quick.visualizer import native_route

    glowing = native_route.oscilloscope_program(True)
    plain = native_route.oscilloscope_program(False)
    assert [len(t.colour) for t in glowing["targets"]] == [2] and [len(t.colour) for t in plain["targets"]] == [1]
    assert any(isinstance(p, BloomStep) for p in glowing["passes"])
    assert not any(isinstance(p, BloomStep) for p in plain["passes"])
    forms = {p.form for p in plain["passes"] if isinstance(p, CompositeStep)}
    assert forms == {"overlay"} and plain["unread"] == ["u_bloom_strength"] and "unread" not in glowing
    presentation = _presentation()
    assert native_route.oscilloscope_glow(SimpleNamespace(logical=_logical(0))) is True
    assert native_route.oscilloscope_glow(SimpleNamespace(logical=_logical(0, osc_glow=0.0))) is False
    # Glow 0's settings carry no exposure (no composite reads one).
    assert "u_hdr_exposure" not in _settings(_logical(0, osc_glow=0.0), presentation, _card(presentation))


def test_the_beam_reads_its_points_within_the_buffer():
    from rendering.quick.visualizer.implementations.oscilloscope import OSC_BEAM_VERTEX_SOURCE

    # robustBufferAccess is off: every read of the points is clamped to the buffer's own length.
    assert OSC_BEAM_VERTEX_SOURCE.count("oscPoint[") == 3                  # the declaration and the two reads
    assert OSC_BEAM_VERTEX_SOURCE.count("= oscPoint[min(") == 2
    assert "oscPoint.length() - 1" in OSC_BEAM_VERTEX_SOURCE
    assert "u_alpha[clamp(trace, 0, 15)]" in OSC_BEAM_VERTEX_SOURCE


# ------------------------------------------------------------------------------------------------- the route

class _Composite:
    def __init__(self, log: list) -> None:
        from rendering.native.composite import ContentStatus

        self.log = log
        self.status = ContentStatus(draws=0, failures=0, refused_run=0, failing=False)

    def set(self, **config):
        self.log.append(("set", config))

    def place(self, geometry, origin, **config):
        self.log.append(("place", config))

    def destroy(self):
        self.log.append(("destroy",))

    def window_pixels(self):
        return (2560, 1440)

    def update(self):
        self.log.append(("composite_update",))

    def content_status(self):
        return self.status


class _Mode:
    def __init__(self, log: list) -> None:
        self.log = log
        self.composite = _Composite(log)

    def program(self, passes, settings=None, *, targets=(), streams=(), unread=()):
        self.log.append(("program", [p.name for p in passes], [len(t.colour) for t in targets],
                         [s.name for s in streams], list(unread), "u_hdr_exposure" in (settings or {})))

    def bind(self, name, schema, *, expect=None):
        self.log.append(("bind", schema.mode_id))

    def settings(self, values):
        self.log.append(("settings",))

    def target_size(self, name, size):
        self.log.append(("target_size", name, tuple(size)))

    def card(self, card):
        self.log.append(("card",))

    def unbind(self):
        self.log.append(("unbind",))

    def update(self):
        self.log.append(("update",))

    def drop_retained_frame(self):
        self.log.append(("drop",))


class _Core:
    def __init__(self) -> None:
        self.log: list = []

    def mode(self, _host):
        return _Mode(self.log)

    def spectrum(self, _host):
        raise AssertionError("the Oscilloscope is drawn on the generic item")


class _Bridge:
    def __init__(self, snapshots) -> None:
        self.snapshots = list(snapshots)

    def admit_at_sync(self):
        pass

    def take_for_render(self, **_kwargs):
        return self.snapshots.pop(0) if self.snapshots else None


def test_the_route_draws_the_oscilloscope_and_follows_glow_at_the_settings_edge(monkeypatch):
    from rendering.native import program_values
    from rendering.quick.visualizer import native_route

    monkeypatch.setattr(program_values, "mode_fragment_pack", lambda _mode: b"pack")
    monkeypatch.setattr(native_route, "_shader_pack", lambda _name: b"pack")
    # The route's registration stays process-local until the port's last step (playbook checklist 18).
    if "oscilloscope" not in native_route.GENERIC_MODE_SETTINGS:
        monkeypatch.setattr(native_route, "GENERIC_MODE_SETTINGS",
                            {**native_route.GENERIC_MODE_SETTINGS, "oscilloscope": native_route.OSCILLOSCOPE_SETTINGS})
        monkeypatch.setattr(native_route, "NATIVE_MODE_IDS", native_route.NATIVE_MODE_IDS | {"oscilloscope"})
    window = SimpleNamespace(width=lambda: 1707, height=lambda: 960,
                             afterSynchronizing=SimpleNamespace(connect=lambda *a: None, disconnect=lambda *a: None),
                             afterRendering=SimpleNamespace(connect=lambda *a: None, disconnect=lambda *a: None))
    core = _Core()
    route = native_route.NativeVisualizerRoute(core, SimpleNamespace(window=lambda: window))
    presentation = _presentation()

    def snapshot(step, **kwargs):
        return SimpleNamespace(logical=_logical(step, **kwargs), presentation=presentation)

    try:
        identity = SimpleNamespace(mode_id="oscilloscope", runtime_generation=1, engine_generation=2, activation_id=3)
        bridge = _Bridge([snapshot(0), snapshot(1)])
        assert route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True) is True
        names = [entry[0] for entry in core.log]
        assert names.index("program") < names.index("bind")
        program = next(entry for entry in core.log if entry[0] == "program")
        assert program[1:] == (["oscilloscope_graticule", "oscilloscope_beam", "oscilloscope_bloom",
                                "oscilloscope_show"], [2], ["osc_points"], [], True)
        # Another frame of the same Settings: no program, no settings (the record carries the frame).
        mark = len(core.log)
        route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True)
        assert "program" not in [entry[0] for entry in core.log[mark:]]
        # Glow to 0 at the Settings edge: the plain program once, its bloom strength unread, no exposure.
        bridge.snapshots = [snapshot(2, osc_glow=0.0), snapshot(3, osc_glow=0.0)]
        mark = len(core.log)
        route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True)
        route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True)
        programs = [entry for entry in core.log[mark:] if entry[0] == "program"]
        assert programs == [("program", ["oscilloscope_graticule", "oscilloscope_beam", "oscilloscope_show"], [1],
                             ["osc_points"], ["u_bloom_strength"], False)]
        # Control: Glow back above 0 builds the glowing program again.
        bridge.snapshots = [snapshot(4, osc_glow=0.3)]
        mark = len(core.log)
        route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True)
        assert [entry[2] for entry in core.log[mark:] if entry[0] == "program"] == [[2]]
    finally:
        route.close()


# --------------------------------------------------------------------------------------- the module's blocks

def _abi() -> int:
    """The built module's ABI (0: none, or one this package does not speak)."""
    from rendering import native

    try:
        return int(native.load(MODULE_DIR).abi) if BUILT else 0
    except native.NativeCoreUnavailable:
        return 0


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout")
@pytest.mark.qt
def test_glow_0_leaves_the_bloom_strength_unread_by_declaration_only(qt_app):
    """ABI 26: the Glow 0 program (no composite reads ``u_bloom_strength``) is admitted with the field named unread and
    refused without; a name the record lacks, or a field a pass reads, is refused as unread."""
    if _abi() < 26:
        pytest.skip("the module predates ABI 26 (a program's unread fields): its GitHub build is pending")
    from core.visualizer_engine import oscilloscope_native_schema as schema_module
    from rendering import native
    from rendering.native.mode import _card as card_json, _settings as settings_json, program_json, schema_table_entry
    from rendering.quick.visualizer import native_route
    from rendering.quick.visualizer.native_route import _ModeContent

    core = native.load(MODULE_DIR)
    presentation = _presentation(1.5)
    card = _card(presentation)
    shown = card_json(_ModeContent.shown_card(None, card, SimpleNamespace(presentation=presentation)))
    target = tuple(int(v) for v in card["target_size"])
    logical = _logical(0, osc_glow=0.0)
    settings = settings_json(_settings(logical, presentation, card))
    record = schema_module.encode(logical)
    table = json.dumps(dict(schema_table_entry(schema_module.SCHEMA)))
    program = native_route.oscilloscope_program(False)

    def blocks(unread):
        declared, packs = program_json(program["passes"], program["targets"], program["streams"], unread=unread)
        return core.module.mode_blocks(table, declared, packs, settings, record, shown, target)

    blocks(program["unread"])
    with pytest.raises(ValueError, match="u_bloom_strength"):
        blocks(())
    with pytest.raises(ValueError, match="no field of the record"):
        blocks([*program["unread"], "u_nothing"])
    with pytest.raises(ValueError, match="reads it"):
        blocks([*program["unread"], "u_widen"])

@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout")
@pytest.mark.qt
def test_a_bloom_or_composite_under_a_turned_card_is_refused(qt_app):
    """ABI 28 (checkpoint audit 10, M3): the item-anchored bloom and composite are built for an unturned scene; under a
    turned card (whose surface is turned against Python's SceneTarget) a program with either step is refused, fail
    closed, until a turned consumer builds it. Control: the same card unturned packs."""
    if _abi() < 28:
        pytest.skip("the module predates ABI 28: its GitHub build is pending")
    from core.visualizer_engine import oscilloscope_native_schema as schema_module
    from rendering import native
    from rendering.native.mode import _card as card_json, _settings as settings_json, program_json, schema_table_entry
    from rendering.quick.visualizer import native_route
    from rendering.quick.visualizer.native_route import _ModeContent

    core = native.load(MODULE_DIR)
    presentation = _presentation(1.5)
    card = _card(presentation)
    shown = _ModeContent.shown_card(None, card, SimpleNamespace(presentation=presentation))
    target = tuple(int(v) for v in card["target_size"])
    table = json.dumps(dict(schema_table_entry(schema_module.SCHEMA)))
    for glow in (True, False):
        logical = _logical(0) if glow else _logical(0, osc_glow=0.0)
        settings = settings_json(_settings(logical, presentation, card))
        record = schema_module.encode(logical)
        program = native_route.oscilloscope_program(glow)
        declared, packs = program_json(program["passes"], program["targets"], program["streams"],
                                       unread=program.get("unread", ()))
        core.module.mode_blocks(table, declared, packs, settings, record, card_json(shown), target)
        with pytest.raises(ValueError, match="turned card"):
            core.module.mode_blocks(table, declared, packs, settings, record, card_json(dict(shown, quarters=1)),
                                    target)


def _python_blocks(logical, presentation, card) -> tuple[bytes, bytes]:
    """Both passes' blocks as ``QuickOscilloscopeRenderer.render`` packs them for this card (its item the card's)."""
    from rendering.gl_programs.portable import pack_block
    from rendering.quick.visualizer.implementations.oscilloscope import (
        OSC_BEAM_BLOCK,
        OSC_GRATICULE_BLOCK,
        oscilloscope_frame_values,
        oscilloscope_settings_values,
    )

    settings = oscilloscope_settings_values(logical, card["content_rect"], card["oriented_size"], presentation.dpr,
                                            presentation.uniform_visual_scale)
    shown = {"uMatrix": (0.0,) * 16, "u_resolution": tuple(card["oriented_size"]),
             "uContentRotationQuarters": int(card["quarters"])}
    values = {**settings, **oscilloscope_frame_values(logical), **shown}
    return pack_block(OSC_GRATICULE_BLOCK, values), pack_block(OSC_BEAM_BLOCK, values)


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout")
@pytest.mark.qt
@pytest.mark.parametrize("dpr", (1.0, 1.5))
def test_the_modules_blocks_are_the_python_renderers(dpr, qt_app):
    from core.visualizer_engine import oscilloscope_native_schema as schema_module
    from rendering import native
    from rendering.gl_programs.scene3d import _std140_type
    from rendering.native.mode import _card as card_json, _settings as settings_json, program_json, schema_table_entry
    from rendering.quick.visualizer import native_route
    from rendering.quick.visualizer.implementations.oscilloscope import OSC_BEAM_BLOCK, OSC_GRATICULE_BLOCK
    from rendering.quick.visualizer.native_route import _ModeContent

    core = native.load(MODULE_DIR)
    program = native_route.oscilloscope_program(True)
    declared, packs = program_json(program["passes"], program["targets"], program["streams"])
    table = json.dumps(dict(schema_table_entry(schema_module.SCHEMA)))
    presentation = _presentation(dpr)
    card = _card(presentation)
    shown = _ModeContent.shown_card(None, card, SimpleNamespace(presentation=presentation))
    target = tuple(int(v) for v in card["target_size"])

    def blocks(settings, record, shown_card):
        found, facts = core.module.mode_blocks(table, declared, packs, settings_json(settings), bytes(record),
                                               card_json(shown_card), target)
        return [bytes(block) for block in found], json.loads(facts)

    sizes = {"float": 4, "int": 4, "vec2": 8, "vec4": 16, "mat4": 64}
    compared = 0
    for step, logical in enumerate((_logical(0), _logical(5, traces=16), _logical(3, osc_display="Ring"),
                                    _logical(2, osc_display="Phase", osc_spectral=0.0))):
        settings = _settings(logical, presentation, card)
        record = schema_module.encode(logical)
        found, facts = blocks(settings, record, shown)
        expected = _python_blocks(logical, presentation, card)
        for index, layout in ((0, OSC_GRATICULE_BLOCK), (1, OSC_BEAM_BLOCK)):
            rows = {row[0]: row for row in facts["program"]["passes"][index]["block"]["members"]}
            for (name, glsl_type), offset in zip(layout.fields, layout.offsets):
                _element, count, _alignment, stride = _std140_type(glsl_type)
                size = count * stride if "[" in glsl_type else sizes[glsl_type]
                assert rows[name][2] == offset, name     # the module's reflection is the Python packer's layout
                if name == "uMatrix":
                    continue                             # the core's own item-to-target matrix
                assert found[index][offset:offset + size] == expected[index][offset:offset + size], (step, name)
                compared += 1
        # Controls: the flare's widening nudged in the record and a Setting changed each change the beam's block.
        mutated = bytearray(record)
        at = schema_module.LAYOUT.field("u_widen").offset
        struct.pack_into("<d", mutated, at, struct.unpack_from("<d", mutated, at)[0] + 0.25)
        assert blocks(settings, bytes(mutated), shown)[0][1] != found[1]
        assert blocks(dict(settings, uAnalog=float(settings["uAnalog"]) + 0.5), record, shown)[0][1] != found[1]
    assert compared == 4 * (len(OSC_GRATICULE_BLOCK.fields) + len(OSC_BEAM_BLOCK.fields) - 2)

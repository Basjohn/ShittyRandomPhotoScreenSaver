"""N5.1: Bubble on the native core as generic mode content (D12, with N3.1's target, N3.2's quads and N4.a's samplers).

- Its record (``core.visualizer_engine.bubble_native_schema``) is a runtime schema, never compiled, carrying BubbleDraw's
  per-frame members (``BUBBLE_FRAME_MEMBERS``) by name and the ambient layer's two instance streams with their used
  lengths; the route's slot holds it.
- Every member of each of Bubble's three passes has exactly one source: the core's conventions, the settings
  (``bubble_settings_values``, ``bubble_ambient_settings_values``) or the record.
- The settings follow Settings and the card only; the ambient target's size follows the card and is sent only when it
  changes.
- The route draws Bubble on the generic item: its program (targets, streams, three passes) with the first settings, then
  the stream with the schema.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

WINDOW = (1920.0, 1080.0)


def _presentation(dpr: float = 1.5, **overrides):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation

    kwargs = dict(policy=get_visualizer_presentation_policy("bubble"), display_size=WINDOW,
                  viewport_extent=(640.0, 360.0), outer_origin=(803.0, 517.0), dpr=dpr, border_width=2.0,
                  corner_radius=8.0)
    kwargs.update(overrides)
    return resolve_presentation(**kwargs)


def _parameters(**overrides) -> dict:
    """Test inputs (not a preset): every parameter the renderer and the route read."""
    values = {
        "bubble_trail_strength": 0.8, "bubble_tail_opacity": 0.5, "bubble_ghosting_enabled": True,
        "bubble_ghost_alpha": 0.4, "bubble_ghost_decay": 0.4, "bubble_specular_direction": "top_left",
        "bubble_gradient_direction": "top", "bubble_gradient_light": (210, 170, 120, 255),
        "bubble_gradient_dark": (30, 40, 60, 255), "bubble_outline_color": (255, 255, 255, 255),
        "bubble_specular_color": (255, 255, 255, 255), "bubble_pop_color": (255, 255, 255, 255),
        "rainbow_enabled": True, "rainbow_speed": 0.7, "bubble_particle_glow_spread": 1.2,
        "bubble_particle_color": (255, 180, 90, 255), "bubble_particle_glow": True,
        "bubble_microbubble_stream": True, "bubble_microbubble_drift": False, "bubble_particle_stream": False,
        "bubble_particle_drift": True,
    }
    values.update(overrides)
    return values


def _logical(step: int = 0, *, trails: bool = True, ambient: bool = True, **parameters):
    from widgets.spotify_visualizer.render_state import (
        BubbleFrame,
        VisualizerCommonState,
        VisualizerLogicalFrame,
        freeze_render_fields,
    )

    count = 3
    positions = tuple(v for i in range(count)
                      for v in (0.2 + 0.25 * i + 0.01 * step, 0.5 + 0.1 * math.sin(step + i), 0.03 + 0.01 * i, 1.0))
    extras = tuple(v for i in range(count) for v in (0.8, 0.0, 0.05 * i, -0.05 * i))
    trail = tuple(v for i in range(count) for s in range(3)
                  for v in (0.2 + 0.25 * i - 0.02 * (3 - s), 0.5, 0.15 * (s + 1))) if trails else ()
    points = tuple(v for k in range(5) for v in (0.1 + 0.15 * k, 0.3 + 0.05 * k, 3.0, 0.8, 0.5 * k, float(k % 2)))
    return VisualizerLogicalFrame(
        runtime_generation=1, engine_generation=2, activation_id=3, source_generation=2, source_activation_id=3,
        mode_id="bubble", playing=True, logical_timestamp=1.0 + step / 60.0, source_timestamp=1.0, changed=True,
        present_frame=True, mode_reveal_ready=True, common=VisualizerCommonState(bars=(), bar_count=0),
        mode_state=BubbleFrame(
            positions=positions, extras=extras, trails=trail, bubble_count=count, big_class_bits=(2, 0, 0, 0),
            ambient_points=points if ambient else (),
            ambient_occluders=(0.45, 0.5, 0.04, 1.0) if ambient else (),
            source_timestamp=1.0, simulation_timestamp=1.0 + step / 60.0,
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
    from rendering.quick.visualizer.native_route import BUBBLE_SETTINGS

    return BUBBLE_SETTINGS(SimpleNamespace(logical=logical, presentation=presentation), card)


def _members(filename: str, block: str) -> set[str]:
    from pathlib import Path

    from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl
    from widgets.spotify_visualizer import shaders

    source = shaders.compose_shader_source(Path(shaders.__file__).resolve().parent / filename)
    return {name for name, _kind in block_layout_from_glsl(block_declaration(source, block)).fields}


# ------------------------------------------------------------------------------------------------- the record

def test_the_record_is_a_runtime_schema_of_the_frame_members_and_the_ambient_streams():
    from core.visualizer_engine import bubble_native_schema as schema_module
    from core.visualizer_engine import native_schema
    from core.visualizer_engine.packet_abi import SLOT_OVERHEAD
    from rendering.quick.visualizer import native_route
    from rendering.quick.visualizer.implementations.bubble import BUBBLE_FRAME_MEMBERS

    schema = schema_module.SCHEMA
    assert schema.schema_id in native_schema.runtime_schemas()
    assert schema.schema_id not in native_schema.compiled_schemas()
    assert native_schema.schema_for_mode("bubble") is schema
    streams = {"ambient_points", "ambient_point_floats", "ambient_occluders", "ambient_occluder_floats"}
    assert set(schema.fields) == set(BUBBLE_FRAME_MEMBERS) | streams
    # Version 1's layout (a change is a new version).
    assert (schema.layout.size, schema.layout.fingerprint()) == (24048, "520ca3fa9ccdadc7")
    # The route's slot holds it (whole 4096-byte steps); Spline Curve's stays one step.
    assert schema.layout.size <= native_route._slot_bytes("bubble") - SLOT_OVERHEAD
    assert native_route._slot_bytes("bubble") % native_route._SLOT_BYTES == 0
    assert native_route._slot_bytes("devcurve") == native_route._SLOT_BYTES


def test_the_record_round_trips_and_carries_the_renderers_values():
    from core.visualizer_engine import bubble_native_schema as schema_module
    from core.visualizer_engine.native_schema import NativeSchemaError

    logical = _logical(4)
    payload = schema_module.encode(logical)
    decoded = schema_module.decode(payload)
    assert decoded == schema_module.project(logical)
    mode_state = logical.mode_state
    count = mode_state.bubble_count
    assert decoded["u_bubble_count"] == count
    assert decoded["u_big_class_bits"] == tuple(mode_state.big_class_bits)
    flat = [v for row in decoded["u_bubbles_pos"][:count] for v in row]
    assert flat == pytest.approx(mode_state.positions)
    assert all(row == (0.0,) * 4 for row in decoded["u_bubbles_pos"][count:])
    samples = decoded["u_bubbles_trail"][:3 * count]
    assert [v for row in samples for v in row[:3]] == pytest.approx(mode_state.trails)
    assert decoded["ambient_point_floats"] == len(mode_state.ambient_points)
    assert decoded["ambient_occluder_floats"] == len(mode_state.ambient_occluders)
    assert decoded["u_ambient_enabled"] == 1 and decoded["u_ambient_light_enabled"] == 1
    # R-225: a frame without trail samples carries zeros (no ghost from an earlier frame) and no wake.
    quiet = schema_module.decode(schema_module.encode(_logical(4, trails=False)))
    assert all(row == (0.0,) * 4 for row in quiet["u_bubbles_trail"])
    assert quiet["u_trail_strength"] == 0.0 and quiet["u_tail_opacity"] == 0.0
    # The ambience off: both switches off, no stream in use.
    off = schema_module.decode(schema_module.encode(_logical(4, ambient=False)))
    assert (off["u_ambient_enabled"], off["ambient_point_floats"], off["ambient_occluder_floats"]) == (0, 0, 0)
    # The clock moves the hue.
    assert schema_module.project(_logical(9))["u_rainbow_hue_offset"] != decoded["u_rainbow_hue_offset"]
    # A non-finite value is refused by the writer (control: the encoder checks what it writes).
    broken = _logical(1)
    object.__setattr__(broken.mode_state, "positions", (float("nan"),) + broken.mode_state.positions[1:])
    with pytest.raises(NativeSchemaError):
        schema_module.encode(broken)


def test_a_four_number_array_field_packs_every_element():
    # The record's f64x4 arrays (Bubble's positions) pack and unpack every element; a single f64x4 is unchanged.
    from core.visualizer_engine.native_schema import NativeLayout, NativeSchemaError

    layout = NativeLayout.build((("rows", "f64x4", 3), ("one", "f64x4", 1)))
    rows = ((1.0, 2.0, 3.0, 4.0), (5.0, 6.0, 7.0, 8.0), (9.0, 10.0, 11.0, 12.0))
    unpacked = layout.unpack(layout.pack(7, {"rows": rows, "one": (1.0, 2.0, 3.0, 4.0)}))
    assert unpacked["rows"] == rows and unpacked["one"] == (1.0, 2.0, 3.0, 4.0)
    assert layout.unpack(layout.pack(7, {"rows": [v for r in rows for v in r], "one": (0.0,) * 4}))["rows"] == rows
    # Control: too few numbers are refused rather than packed as one element.
    with pytest.raises(NativeSchemaError):
        layout.pack(7, {"rows": rows[:2], "one": (0.0,) * 4})


def test_class_words_round_trip_into_the_shader_block_without_unsigned_or_stride_loss():
    import struct

    from core.visualizer_engine import bubble_native_schema as schema_module
    from rendering.gl_programs.portable import pack_block
    from rendering.quick.visualizer.implementations.bubble import BUBBLE_BLOCK

    # Synthetic membership boundaries, including the high bit of each word and nonzero later words.
    words = tuple((1 << 31) | (1 << index) for index in range(4))
    logical = _logical()
    object.__setattr__(logical.mode_state, "big_class_bits", words)
    record = schema_module.decode(schema_module.encode(logical))
    assert record["u_big_class_bits"] == words
    layout = BUBBLE_BLOCK
    index = next(i for i, (name, _kind) in enumerate(layout.fields) if name == "u_big_class_bits")
    packed = pack_block(layout, record)
    assert struct.unpack_from("<4I", packed, layout.offsets[index]) == words


# ------------------------------------------------------------------------------------------------- the sources

def test_every_member_of_every_pass_has_exactly_one_source():
    from core.visualizer_engine import bubble_native_schema as schema_module
    from rendering.native.mode import MODE_CORE_MEMBERS

    presentation = _presentation()
    settings = _settings(_logical(), presentation, _card(presentation))
    record = set(schema_module.FIELD_NAMES)
    core = set(MODE_CORE_MEMBERS)
    assert not (set(settings) & record) and not (set(settings) & core) and not (record & core)
    for filename, block in (("bubble.frag", "BubbleDraw"), ("bubble_ambient_points.vert", "BubbleAmbientPoints"),
                            ("bubble_ambient_mask.vert", "BubbleAmbientMask")):
        members = _members(filename, block)
        assert members <= set(settings) | record | core, (filename, members - (set(settings) | record | core))
    # Every setting and every block field has a reader (the streams' fields are the streams').
    declared = set().union(*(_members(f, b) for f, b in (("bubble.frag", "BubbleDraw"),
                                                         ("bubble_ambient_points.vert", "BubbleAmbientPoints"),
                                                         ("bubble_ambient_mask.vert", "BubbleAmbientMask"))))
    assert set(settings) <= declared
    streams = {"ambient_points", "ambient_point_floats", "ambient_occluders", "ambient_occluder_floats"}
    assert record - streams <= declared
    # Control: a member left out of the settings is caught.
    assert not _members("bubble.frag", "BubbleDraw") <= (set(settings) - {"u_ghost_alpha"}) | record | core


def test_the_settings_follow_settings_and_the_card_only():
    presentation = _presentation()
    card = _card(presentation)
    base = _settings(_logical(0), presentation, card)
    assert _settings(_logical(7), presentation, card) == base            # another frame, the same settings
    assert _settings(_logical(7, trails=False, ambient=False), presentation, card) == base
    # Controls: a Setting and the card's content rect each change them.
    assert _settings(_logical(0, bubble_ghost_alpha=0.9), presentation, card) != base
    moved = dict(card, content_rect=[v + 1.0 for v in card["content_rect"]])
    assert _settings(_logical(0), presentation, moved) != base


def test_the_ambient_target_follows_its_content_and_rests_at_the_smallest_with_the_ambience_off():
    from rendering.quick.visualizer.native_route import GENERIC_MODE_TARGET_SIZES
    from widgets.spotify_visualizer.bubble_ambient_geometry import ambient_target_size

    sizer = GENERIC_MODE_TARGET_SIZES["bubble"]
    presentation = _presentation()
    card = _card(presentation)
    snapshot = SimpleNamespace(logical=_logical(), presentation=presentation)
    settings = _settings(snapshot.logical, presentation, card)
    width, height, _scale = ambient_target_size(card["content_rect"], presentation.dpr)
    assert sizer(snapshot, settings) == {"ambient": (width, height)}
    # A frame without ambient points (the ambience off) rests the target at the smallest size.
    quiet = SimpleNamespace(logical=_logical(ambient=False), presentation=presentation)
    assert sizer(quiet, settings)["ambient"] < (width, height)
    # Control (the owner run's defect, 15 Nov): the frame's parameters with every ambience switch off still draw the
    # target at its content's size while the frame carries points (the switches are the runtime's, not the frame's).
    off = {name: False for name in ("bubble_microbubble_stream", "bubble_microbubble_drift", "bubble_particle_stream",
                                    "bubble_particle_drift", "bubble_particle_glow")}
    carried = SimpleNamespace(logical=_logical(**off), presentation=presentation)
    assert sizer(carried, settings) == {"ambient": (width, height)}


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

    def program(self, passes, settings=None, *, targets=(), streams=()):
        self.log.append(("program", [p.name for p in passes], [t.name for t in targets], [s.name for s in streams]))

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
        raise AssertionError("Bubble is drawn on the generic item")


class _Bridge:
    def __init__(self, snapshots) -> None:
        self.snapshots = list(snapshots)

    def admit_at_sync(self):
        pass

    def take_for_render(self, **_kwargs):
        return self.snapshots.pop(0) if self.snapshots else None


def test_the_route_draws_bubble_with_its_target_streams_and_three_passes(monkeypatch):
    from rendering.native import program_values
    from rendering.quick.visualizer import native_route

    # Registered once its rule (a) passed (D10).
    assert "bubble" in native_route.NATIVE_MODE_IDS
    monkeypatch.setattr(program_values, "mode_fragment_pack", lambda _mode: b"pack")
    monkeypatch.setattr(native_route, "_shader_pack", lambda _name: b"pack")
    window = SimpleNamespace(width=lambda: 1707, height=lambda: 960,
                             afterSynchronizing=SimpleNamespace(connect=lambda *a: None, disconnect=lambda *a: None),
                             afterRendering=SimpleNamespace(connect=lambda *a: None, disconnect=lambda *a: None))
    core = _Core()
    route = native_route.NativeVisualizerRoute(core, SimpleNamespace(window=lambda: window))
    presentation = _presentation()

    def snapshot(step, **kwargs):
        return SimpleNamespace(logical=_logical(step, **kwargs), presentation=presentation)

    try:
        identity = SimpleNamespace(mode_id="bubble", runtime_generation=1, engine_generation=2, activation_id=3)
        bridge = _Bridge([snapshot(0), snapshot(1), snapshot(2)])
        assert route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True) is True
        names = [entry[0] for entry in core.log]
        assert names.index("program") < names.index("bind")
        program = next(entry for entry in core.log if entry[0] == "program")
        assert program[1:] == (["bubble_ambient_points", "bubble_ambient_mask", "bubble"], ["ambient"],
                               ["ambient_points", "ambient_occluders"])
        # The program's declaration holds the first size: nothing more is sent, at rest or for another frame.
        assert "target_size" not in names
        mark = len(core.log)
        route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True)
        assert [entry[0] for entry in core.log[mark:]] == ["update"]
        # Control: the card's content changes size, and the target's size is sent once.
        moved = _presentation(viewport_extent=(700.0, 360.0))
        bridge.snapshots = [SimpleNamespace(logical=_logical(3), presentation=moved)]
        mark = len(core.log)
        route.sync(bridge=bridge, identity=identity, presentation=moved, authority=True)
        assert [entry for entry in core.log[mark:] if entry[0] == "target_size"][:1] != []
        assert sum(1 for entry in core.log[mark:] if entry[0] == "target_size") == 1
    finally:
        route.close()


def test_rule_a_admits_bubbles_scatter_and_nothing_wider():
    # D12 bounds (lead, 17 Nov): Bubble's owner rule (a) admits scatter, isolated pixels exactly one level off outside
    # the reference mask, up to its own cap a frame; ties and flips stay the composite's; no other mode gains it.
    # Bounds come from the harness's constants.
    import numpy as np

    from tools.visualizer_replay import owner_render_parity as parity

    cap = parity.RULE_A_SCATTER_PIXELS["bubble"]
    ties = parity.RULE_A_EDGE_PIXELS_PER_FRAME
    reference = np.full((240, 400, 4), 90, np.uint8)
    reference[..., 3] = 255                                    # opaque: the mask is empty
    mask = np.zeros(reference.shape[:2], bool)

    def frame(pixels: int, level: int = 1, mode: str | None = "bubble"):
        drawn = reference.astype(np.int16)
        for k in range(pixels):                                # isolated: every third pixel on a grid
            drawn[3 + 3 * (k // 40), 3 + 3 * (k % 40), 1] += level
        return parity.rule_a_verdict([parity.rule_a_frame(drawn.astype(np.uint8), reference, mask, mode)], mode)

    assert frame(cap)["pass"]
    assert frame(cap)["bound"]["scatter_pixels"] == cap
    # Negative controls: one scatter pixel past the cap; scatter-sized sets at two levels (ties past their cap); the
    # same scatter for a mode without the decision; a uniform one-level shift.
    assert not frame(cap + 1)["pass"]
    assert not frame(ties + 1, level=2)["pass"]
    assert not frame(cap, mode=None)["pass"]
    assert not frame(cap, mode="spectrum")["pass"]
    shifted = reference.astype(np.int16)
    shifted[..., 1] += 1
    assert not parity.rule_a_verdict([parity.rule_a_frame(shifted.astype(np.uint8), reference, mask, "bubble")],
                                     "bubble")["pass"]


def test_bubbles_scatter_must_be_spread_and_counts_as_a_ties_neighbour():
    # Checkpoint audit 7 M1: scatter is a spread field of single levels; a compact one-level patch within the count
    # fails, and ties inside a one-level patch are not isolated. Bounds come from the harness's constants.
    import numpy as np

    from tools.visualizer_replay import owner_render_parity as parity

    cap = parity.RULE_A_SCATTER_PIXELS["bubble"]
    group = parity.RULE_A_SCATTER_GROUP["bubble"]
    reference = np.full((240, 400, 4), 90, np.uint8)
    reference[..., 3] = 255                                    # opaque, flat: no mask, no content edge
    mask = np.zeros(reference.shape[:2], bool)

    def verdict(drawn):
        return parity.rule_a_frame(drawn.astype(np.uint8), reference, mask, "bubble")

    def row_run(drawn, top: int, left: int, length: int, level: int = 1):
        drawn[top, left:left + length, 1] += level

    # A scattered field passes: groups of the largest admitted size, apart from each other, up to the count.
    spread = reference.astype(np.int16)
    placed = 0
    for k in range(cap // group):
        row_run(spread, 10 + 4 * k, 10, group)
        placed += group
    assert verdict(spread)["pass"] and verdict(spread)["scatter"] == placed
    # Negative controls (each seen passing before the spread rule): one more touching pixel; a solid 7x7 block plus
    # two (51 pixels, within the count); a 41-pixel block with ten 2-level ties inside it.
    longer = reference.astype(np.int16)
    row_run(longer, 10, 10, group + 1)
    assert not verdict(longer)["pass"]
    block = reference.astype(np.int16)
    block[50:57, 50:57, 1] += 1
    block[60, 60, 1] += 1
    block[62, 62, 1] += 1
    assert (block != reference).any(axis=2).sum() == 51 <= cap
    assert not verdict(block)["pass"]
    tied = reference.astype(np.int16)
    tied[100:107, 100:107, 1] += 1                             # 49 pixels ...
    for y in (101, 103, 105):                                  # ... nine of them, apart, raised to 2 levels
        for x in (101, 103, 105):
            tied[y, x, 1] += 1
    tied[200, 300, 1] += 2                                     # and one isolated tie elsewhere
    result = verdict(tied)
    assert result["ties"] == parity.RULE_A_EDGE_PIXELS_PER_FRAME and result["scatter"] == 40 <= cap
    assert not result["pass"]
    assert any("neither isolated" in reason for reason in result["reasons"])

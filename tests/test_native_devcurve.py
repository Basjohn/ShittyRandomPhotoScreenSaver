"""N5.1: Spline Curve (mode id ``devcurve``) on the native core as generic mode content (D12).

- Its record (``core.visualizer_engine.devcurve_native_schema``) is a runtime schema, never compiled, carrying exactly
  DevCurveDraw's per-frame members (``DEVCURVE_FRAME_MEMBERS``) by their names; it fits the route's slot.
- Every DevCurveDraw member has exactly one source: the core's conventions, ``devcurve_settings_values`` or the record.
- The Python renderer's block and the module's (``mode_blocks``, GPU-free) are equal member by member for the same frame
  and card (uMatrix aside: the Python quad's matrix against the core's zeros, unread by the fragment stage); controls:
  a curve sample and the card's fade each change the module's block.
- The route draws Spline Curve on the generic item: its program with the first settings, then the stream with the
  schema; the card in the core's keys; settings sent only when they change; a second activation keeps the program.
"""
from __future__ import annotations

import math
import os
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
LAYERS = ("bass", "vocals", "mids", "transients")
WINDOW = (1920.0, 1080.0)


def _presentation(dpr: float = 1.5, **overrides):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation

    kwargs = dict(policy=get_visualizer_presentation_policy("devcurve"), display_size=WINDOW,
                  viewport_extent=(820.0, 210.0), outer_origin=(803.0, 517.0), dpr=dpr, border_width=2.0,
                  content_inset=3.0)
    kwargs.update(overrides)
    return resolve_presentation(**kwargs)


def _logical(step: int = 0, *, enabled=(True, True, True, True), rainbow: bool = True, order=(1, 2, 3, 4)):
    """A Spline Curve logical frame (test inputs, not a preset): moving curves, three specular slots."""
    from widgets.spotify_visualizer.render_state import (
        DevCurveFrame,
        VisualizerCommonState,
        VisualizerEnergyState,
        VisualizerLogicalFrame,
        freeze_render_fields,
    )

    samples = 96
    curves = tuple((name, tuple(0.4 + 0.07 * index + 0.05 * math.sin(k / 9.0 + step * 0.3 + index)
                                for k in range(samples))) for index, name in enumerate(LAYERS))
    parameters = {
        "devcurve_sample_count": samples, "devcurve_foreground_shadow_enabled": True,
        "devcurve_foreground_shadow_alpha": 0.7, "devcurve_foreground_shadow_darken": 0.5,
        "devcurve_foreground_shadow_offset": 0.11, "devcurve_foreground_specular_enabled": True,
        "devcurve_foreground_specular_alpha": 0.9, "devcurve_foreground_specular_width": 0.05,
        "devcurve_foreground_specular_offset": 0.03, "devcurve_foreground_specular_crest_bias": 1.1,
        "devcurve_specular_activity_alpha": 0.37 + 0.01 * step, "rainbow_enabled": rainbow, "rainbow_speed": 0.7,
    }
    for index, name in enumerate(LAYERS):
        parameters.update({f"devcurve_layer_{name}_enabled": enabled[index],
                           f"devcurve_layer_{name}_color": (50 + 40 * index, 120, 230, 220),
                           f"devcurve_layer_{name}_alpha": 0.5 + 0.1 * index,
                           f"devcurve_layer_{name}_outline_color": (255, 250, 240, 200),
                           f"devcurve_layer_{name}_outline_width": 0.004 + 0.001 * index,
                           f"devcurve_layer_{name}_order": order[index]})
    drawn = [name for _o, name in sorted(zip(order, LAYERS))]
    shown = [name for name in drawn if enabled[LAYERS.index(name)]]
    return VisualizerLogicalFrame(
        runtime_generation=1, engine_generation=2, activation_id=3, source_generation=2, source_activation_id=3,
        mode_id="devcurve", playing=True, logical_timestamp=1.0 + step / 60.0, source_timestamp=1.0, changed=True,
        present_frame=True, mode_reveal_ready=True,
        common=VisualizerCommonState(bars=(), bar_count=0,
                                     energy=VisualizerEnergyState(bass=0.5, mid=0.4, high=0.2, overall=0.6)),
        mode_state=DevCurveFrame(
            curves=curves, draw_order=tuple(drawn),
            foreground_layer_id=LAYERS.index(shown[-1]) if shown else -1,
            specular_slots=((0.28, 0.3, 1.0, 0.08), (0.58, 0.34, 0.9, 0.42), (0.82, 0.38, 0.8, 0.76)),
            parameters=freeze_render_fields(parameters)),
    )


def _card(presentation) -> dict:
    """The route's own whole card for ``presentation`` in a WINDOW-sized window at its dpr (``NativeVisualizerRoute
    .card`` with its geometry: the quad-aligned composite on the window's own ratio)."""
    from rendering.native.composite import composite_geometry, window_pixel_ratio
    from rendering.quick.visualizer.native_route import NativeVisualizerRoute

    dpr = float(presentation.dpr)
    pixels = (int(round(WINDOW[0] * dpr)), int(round(WINDOW[1] * dpr)))
    geometry = composite_geometry(presentation, quad_aligned=True, pixel_ratio=window_pixel_ratio(WINDOW, pixels))
    route = NativeVisualizerRoute(None, SimpleNamespace())
    return route.card(presentation, SimpleNamespace(presentation=presentation), geometry, (WINDOW, pixels))


def _settings(logical, presentation, card) -> dict:
    from rendering.quick.visualizer.native_route import GENERIC_MODE_SETTINGS

    return GENERIC_MODE_SETTINGS["devcurve"](SimpleNamespace(logical=logical, presentation=presentation), card)


def _block_members() -> list[str]:
    from rendering.quick.visualizer.implementations.devcurve import DEVCURVE_BLOCK

    return [name for name, _kind in DEVCURVE_BLOCK.fields]


# ------------------------------------------------------------------------------------------------- the record

def test_the_record_is_a_runtime_schema_of_exactly_the_frame_members():
    from core.visualizer_engine import devcurve_native_schema as schema_module
    from core.visualizer_engine import native_schema
    from rendering.quick.visualizer import native_route
    from rendering.quick.visualizer.implementations.devcurve import DEVCURVE_FRAME_MEMBERS

    schema = schema_module.SCHEMA
    assert schema.schema_id in native_schema.runtime_schemas()
    assert schema.schema_id not in native_schema.compiled_schemas()
    assert native_schema.schema_for_mode("devcurve") is schema
    assert set(schema.fields) == set(DEVCURVE_FRAME_MEMBERS) and len(schema.fields) == len(DEVCURVE_FRAME_MEMBERS)
    # Version 1's layout (a change is a new version).
    assert (schema.layout.size, schema.layout.fingerprint()) == (3200, "126aaefa82ac5d45")
    from core.visualizer_engine.packet_abi import SLOT_OVERHEAD

    assert schema.layout.size <= native_route._SLOT_BYTES - SLOT_OVERHEAD
    # Every curve member holds the shader's sample count.
    for name in LAYERS:
        assert schema.layout.field(f"u_devcurve_curve_{name}").count == schema_module.CURVE_SAMPLES == 96


def test_the_record_round_trips_and_carries_the_renderers_values():
    from core.visualizer_engine import devcurve_native_schema as schema_module
    from rendering.quick.visualizer.implementations.devcurve import devcurve_frame_values

    logical = _logical(4)
    payload = schema_module.encode(logical)
    decoded = schema_module.decode(payload)
    assert decoded == schema_module.project(logical)
    values = devcurve_frame_values(logical)
    for name in schema_module.FIELD_NAMES:
        expected = values[name]
        assert decoded[name] == (tuple(expected) if isinstance(expected, (tuple, list)) else expected), name
    # The per-frame values move: the play/pause ramp and the clock.
    later = schema_module.project(_logical(9))
    assert later["u_devcurve_foreground_specular_alpha"] != decoded["u_devcurve_foreground_specular_alpha"]
    assert later["u_rainbow_hue_offset"] != decoded["u_rainbow_hue_offset"]
    # A non-finite value is refused by the writer (control: the encoder checks what it writes).
    from core.visualizer_engine.native_schema import NativeSchemaError

    broken = _logical(1)
    object.__setattr__(broken.mode_state, "specular_slots", ((float("nan"), 0.3, 1.0, 0.08),))
    with pytest.raises(NativeSchemaError):
        schema_module.encode(broken)


def test_every_member_has_exactly_one_source():
    from core.visualizer_engine import devcurve_native_schema as schema_module
    from rendering.native.mode import MODE_CORE_MEMBERS

    presentation = _presentation()
    logical = _logical()
    settings = _settings(logical, presentation, _card(presentation))
    members = set(_block_members())
    core = members & set(MODE_CORE_MEMBERS)
    record = set(schema_module.FIELD_NAMES)
    assert not (set(settings) & record) and not (set(settings) & core) and not (record & core)
    assert set(settings) | record | core == members
    # Control: a member left out of the settings is caught.
    assert (set(settings) - {"u_ghost_alpha"}) | record | core != members


def test_the_settings_follow_settings_and_the_card_only():
    presentation = _presentation()
    card = _card(presentation)
    base = _settings(_logical(0), presentation, card)
    assert _settings(_logical(7), presentation, card) == base          # another frame, the same settings
    # Controls: a layer order change and the card's content rect each change them.
    assert _settings(_logical(0, order=(4, 3, 2, 1)), presentation, card) != base
    moved = dict(card, content_rect=[v + 1.0 for v in card["content_rect"]])
    assert _settings(_logical(0), presentation, moved) != base
    # Every layer disabled: no foreground (-1), an int setting (a u32 record field could not carry it).
    assert _settings(_logical(0, enabled=(False,) * 4), presentation, card)["u_devcurve_foreground_layer_id"] == -1


_ARRAY_PARAMETER = r"^\w[\w ]*\([^)]*\b\w+\s+\w+\s*\[\d*\][^)]*\)\s*\{"


def test_no_product_shader_passes_an_array_to_a_function_by_value():
    # SPIR-V copies a by-value array argument whole into function memory at every call: Spline Curve's curve sampling
    # did so and its pass cost 1.97 ms on Vulkan against 0.030 ms on OpenGL at dpr 1 (N5.1).
    import re

    sources = [path for folder in ("widgets/spotify_visualizer/shaders", "rendering/quick/qml/shaders",
                                   "native/core/shaders")
               for path in (ROOT / folder).rglob("*") if path.suffix in (".frag", ".vert", ".comp", ".glsl")]
    assert sources
    found = [f"{path.name}: {match.group(0)}" for path in sources
             for match in re.finditer(_ARRAY_PARAMETER, path.read_text(encoding="utf-8"), flags=re.M)]
    assert found == []
    # Control: the old signature is caught.
    assert re.search(_ARRAY_PARAMETER, "float _sample_curve(const float curve[96], float x, int count) {", flags=re.M)


# --------------------------------------------------------------------------------------- the module's blocks

def _python_block(logical, presentation, card) -> dict:
    """DevCurveDraw's values as ``QuickDevCurveRenderer.render`` writes them for this card (its item the card's)."""
    from rendering.quick.visualizer.implementations.devcurve import (
        devcurve_frame_values,
        devcurve_presentation_layout,
        devcurve_settings_values,
    )

    layout = devcurve_presentation_layout(presentation, card["content_rect"])
    values = {"uMatrix": (0.0,) * 16, "uItemSize": tuple(card["item_size"]),
              "uContentRotationQuarters": int(card["quarters"]), "u_resolution": tuple(card["oriented_size"]),
              "u_dpr": presentation.dpr, "u_viewport_origin_px": (0.0, 0.0), "u_quick_item_coords": 1,
              "u_border_width": presentation.border_width, "u_fade": presentation.content_fade,
              # fragPixel's target: the render target's pixels (the core's own target; the window's in Python).
              "u_target_px": tuple(float(v) for v in card["target_size"])}
    values.update(devcurve_settings_values(logical, layout))
    values.update(devcurve_frame_values(logical))
    return values


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout")
@pytest.mark.qt
@pytest.mark.parametrize("dpr", (1.0, 1.5))
def test_the_modules_block_is_the_python_renderers(dpr, qt_app):
    from core.visualizer_engine import devcurve_native_schema as schema_module
    from rendering import native
    from rendering.gl_programs.portable import pack_block
    from rendering.native.mode import ModePass
    from rendering.native.program_values import mode_fragment_pack
    from rendering.quick.visualizer.implementations.devcurve import DEVCURVE_BLOCK
    from rendering.quick.visualizer.native_route import _ModeContent

    core = native.load(MODULE_DIR)
    passes = [ModePass("devcurve", mode_fragment_pack("devcurve"), "alpha")]
    presentation = _presentation(dpr)
    card = _card(presentation)
    shown = _ModeContent.shown_card(None, card, SimpleNamespace(presentation=presentation))
    target = tuple(int(v) for v in card["target_size"])
    from rendering.gl_programs.scene3d import _std140_type

    sizes = {"float": 4, "int": 4, "vec2": 8, "vec4": 16, "mat4": 64}
    members = {}
    for (name, glsl_type), offset in zip(DEVCURVE_BLOCK.fields, DEVCURVE_BLOCK.offsets):
        _element, count, _alignment, stride = _std140_type(glsl_type)
        members[name] = (offset, count * stride if "[" in glsl_type else sizes[glsl_type])
    compared = 0
    for step, logical in enumerate((_logical(0), _logical(5, rainbow=False), _logical(3, enabled=(1, 0, 1, 0)))):
        settings = _settings(logical, presentation, card)
        record = schema_module.encode(logical)
        (block,), facts = core.mode_blocks(schema_module.SCHEMA, passes, settings, record, shown, target)
        expected = pack_block(DEVCURVE_BLOCK, _python_block(logical, presentation, card))
        rows = {row[0]: row for row in facts["program"]["passes"][0]["block"]["members"]}
        for name, (offset, size) in members.items():
            assert rows[name][2] == offset, name           # the module's reflection is the Python packer's layout
            if name == "uMatrix":
                continue                       # the Python quad's matrix against the core's zeros: vertex stage only
            assert block[offset:offset + size] == expected[offset:offset + size], (step, name)
            compared += 1
        # Controls: a curve sample raised and the card's fade nudged each change the block.
        mutated = bytearray(record)
        at = schema_module.LAYOUT.field("u_devcurve_curve_bass").offset
        struct.pack_into("<d", mutated, at, struct.unpack_from("<d", mutated, at)[0] + 0.25)
        assert core.mode_blocks(schema_module.SCHEMA, passes, settings, bytes(mutated), shown, target)[0][0] != block
        faded = dict(shown, content_fade=float(shown["content_fade"]) * 0.5)
        assert core.mode_blocks(schema_module.SCHEMA, passes, settings, record, faded, target)[0][0] != block
    assert compared == 3 * (len(DEVCURVE_BLOCK.fields) - 1)


def test_rule_a_is_the_composite_tolerance_for_every_composite_mode():
    # The lead's decision on N5.1's per-pixel proof: a fill within the fill level, edge pixels within the edge level and
    # at most the cap a frame; one rule for every mode drawn through the composite, Spectrum included. Bounds are read
    # from the harness's own constants.
    # Judged pixel by pixel (tools/pixel_tolerance.py): the fill level only on the pixels the reference draws
    # translucent (here its own alpha), edge pixels isolated (tests/test_pixel_tolerance.py has the rest).
    import numpy as np

    from tools import pixel_tolerance as pt
    from tools.visualizer_replay import owner_render_parity as parity

    fill, edge, cap = parity.RULE_A_FILL_LEVEL, parity.RULE_A_EDGE_LEVEL, parity.RULE_A_EDGE_PIXELS_PER_FRAME
    reference = np.zeros((200, 600, 4), np.uint8)
    reference[..., :3] = 60
    reference[..., 3] = 128                                    # translucent content everywhere ...
    reference[150:, :, 3] = 255                                # ... but an opaque band
    mask = pt.translucent_by_alpha(reference)

    def frame(fill_pixels: int, edge_pixels: int, edge_level: int, *, opaque: bool = False, level: int = fill):
        drawn = reference.astype(np.int16)
        rows = (slice(150, 200) if opaque else slice(0, 150))
        region = drawn[rows, :, :3].copy()
        flat = region.reshape(-1, 3)
        flat[:fill_pixels] += level
        drawn[rows, :, :3] = flat.reshape(region.shape)
        for k in range(edge_pixels):
            drawn[10 + 3 * (k % 10), 400 + 3 * (k // 10), :3] = reference[0, 0, :3] + edge_level
        return parity.rule_a_frame(drawn.astype(np.uint8), reference, mask)

    assert parity.rule_a_verdict([frame(80000, cap, edge)])["pass"]
    assert parity.rule_a_verdict([])["pass"]
    # Controls: one edge pixel too many in a frame, one level too far.
    assert not parity.rule_a_verdict([frame(10, cap + 1, edge)])["pass"]
    assert not parity.rule_a_verdict([frame(10, 1, edge + 1)])["pass"]
    # Spectrum under the same rule: its owner runs' shape (every differing pixel at 1 level, translucent) passes; a
    # Spectrum frame with those pixels at 2 levels fails, and so do the same pixels at 1 level on opaque content.
    assert parity.rule_a_verdict([frame(17000, 0, edge)])["pass"]
    assert not parity.rule_a_verdict([frame(17000, 0, edge, level=fill + 1)])["pass"]
    assert not parity.rule_a_verdict([frame(17000, 0, edge, opaque=True)])["pass"]


# ------------------------------------------------------------------------------------------------- the route

def test_a_self_animating_modes_frames_are_admitted_without_a_current_source():
    # The core admits a playing frame only with FLAG_SOURCE_CURRENT (the Python node's rule for Spectrum). Spline Curve
    # animates by itself: the Python node draws its frames before its source is current, so the route's flags admit
    # them (rule (a): the activation's first frames were refused, measured at 243 levels on the first input).
    import dataclasses

    from core.visualizer_engine.packet_abi import FLAG_PLAYING, FLAG_SOURCE_CURRENT
    from core.visualizer_engine.packet_mailbox import publication_flags
    from rendering.quick.visualizer.native_route import _admission_flags

    waiting = dataclasses.replace(_logical(), source_generation=-1, source_activation_id=-1)
    assert publication_flags(waiting) & FLAG_PLAYING and not publication_flags(waiting) & FLAG_SOURCE_CURRENT
    assert _admission_flags(waiting) & FLAG_SOURCE_CURRENT
    # Control: a mode that needs its tracked source (Spectrum) keeps the frame's own bit.
    spectrum = SimpleNamespace(mode_id="spectrum", playing=True, present_frame=True, source_generation=-1,
                               source_activation_id=-1, engine_generation=2, activation_id=3)
    assert not _admission_flags(spectrum) & FLAG_SOURCE_CURRENT

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

    def program(self, passes, settings=None):
        self.log.append(("program", [p.name for p in passes], settings is not None))

    def bind(self, name, schema, *, expect=None):
        self.log.append(("bind", schema.mode_id))

    def settings(self, values):
        self.log.append(("settings",))

    def card(self, card):
        self.log.append(("card", tuple(sorted(card))))

    def unbind(self):
        self.log.append(("unbind",))

    def update(self):
        self.log.append(("update",))

    def drop_retained_frame(self):
        self.log.append(("drop",))


class _Core:
    def __init__(self) -> None:
        self.log: list = []
        self.modes: list = []

    def mode(self, _host):
        made = _Mode(self.log)
        self.modes.append(made)
        return made

    def spectrum(self, _host):
        raise AssertionError("Spline Curve is drawn on the generic item")


class _Bridge:
    def __init__(self, snapshots) -> None:
        self.snapshots = list(snapshots)

    def admit_at_sync(self):
        pass

    def take_for_render(self, **_kwargs):
        return self.snapshots.pop(0) if self.snapshots else None


def test_the_route_draws_spline_curve_on_the_generic_item(monkeypatch):
    from rendering.native import program_values
    from rendering.native.mode import MODE_CARD_KEYS
    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS, NativeVisualizerRoute

    assert "devcurve" in NATIVE_MODE_IDS
    monkeypatch.setattr(program_values, "mode_fragment_pack", lambda _mode: b"pack")
    window = SimpleNamespace(width=lambda: 1707, height=lambda: 960,
                             afterSynchronizing=SimpleNamespace(connect=lambda *a: None, disconnect=lambda *a: None),
                             afterRendering=SimpleNamespace(connect=lambda *a: None, disconnect=lambda *a: None))
    core = _Core()
    route = NativeVisualizerRoute(core, SimpleNamespace(window=lambda: window))
    presentation = _presentation()

    def snapshot(step):
        return SimpleNamespace(logical=_logical(step), presentation=presentation)

    try:
        first = SimpleNamespace(mode_id="devcurve", runtime_generation=1, engine_generation=2, activation_id=3)
        bridge = _Bridge([snapshot(0), snapshot(1)])
        assert route.sync(bridge=bridge, identity=first, presentation=presentation, authority=True) is True
        names = [entry[0] for entry in core.log]
        # The program with its first settings, then the stream with the schema; the card in the core's keys.
        assert names.index("program") < names.index("bind")
        assert ("program", ["devcurve"], True) in core.log and ("bind", "devcurve") in core.log
        assert ("card", tuple(sorted(MODE_CARD_KEYS))) in core.log
        assert len(core.modes) == 1 and route.published == 1
        mark = len(core.log)
        assert route.sync(bridge=bridge, identity=first, presentation=presentation, authority=True) is True
        assert [entry[0] for entry in core.log[mark:]] == ["update"]      # settings and card unchanged: not sent
        # A second activation keeps the item and its program: settings, then the stream.
        second = SimpleNamespace(mode_id="devcurve", runtime_generation=1, engine_generation=2, activation_id=4)
        bridge.snapshots = [snapshot(2)]
        mark = len(core.log)
        assert route.sync(bridge=bridge, identity=second, presentation=presentation, authority=True) is True
        sent = [entry[0] for entry in core.log[mark:]]
        assert "program" not in sent and sent.index("settings") < sent.index("bind") and len(core.modes) == 1
        # Control: the settings for another frame of the same Settings are the same (nothing re-sent per frame).
        bridge.snapshots = [snapshot(3)]
        mark = len(core.log)
        route.sync(bridge=bridge, identity=second, presentation=presentation, authority=True)
        assert "settings" not in [entry[0] for entry in core.log[mark:]]
    finally:
        route.close()

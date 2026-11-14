"""The native Spectrum's Python face and its sources (Current_Plan.md item 8b, N2.5; native/core/src/spectrum.h).

GPU-free: the card a native Spectrum is handed (``rendering.native.spectrum.spectrum_presentation``), the face's calls on
a stand-in module, and the C++ sources held to the Python they port (the shader is the product's own file; every
constant of the renderer's arithmetic is the Python module's). The module's own proof is
``native/core/python/spectrum_check.py`` (uniform parity, the item's contract, pixels; needs the built module).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"


def _presentation(**overrides):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation

    kwargs = dict(policy=get_visualizer_presentation_policy("spectrum"), display_size=(1380.0, 280.0),
                  viewport_extent=(1380.0, 280.0), outer_origin=(37.0, 21.0), dpr=1.5,
                  border_width=2.0, corner_radius=12.0, content_inset=4.0)
    kwargs.update(overrides)
    return resolve_presentation(**kwargs)


@pytest.mark.parametrize("quarters", [0, 1, 2, 3])
def test_the_card_maps_the_targets_pixel_to_the_items_oriented_coordinate(quarters) -> None:
    """The target is the composite's rect (whole device pixels) in the content's orientation: its pixel centre p maps to
    the item's oriented logical coordinate (target origin in the item, oriented) + p / dpr, and the rest of the card is
    the Python renderer's own inputs (rendering/quick/visualizer/render_contract.py logical_content_rect)."""
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import SPECTRUM_PRESENTATION_KEYS, spectrum_presentation
    from widgets.spotify_visualizer.presentation_orientation import logical_rect_from_physical_rect

    presentation = _presentation(content_rotation_quarters=quarters)
    geometry = composite_geometry(presentation)
    card = spectrum_presentation(presentation, geometry)
    assert set(card) == set(SPECTRUM_PRESENTATION_KEYS)
    json.dumps(card)                                                    # plain data for the module
    outer = tuple(float(v) for v in presentation.outer_rect)
    item = (outer[2], outer[3])
    assert card["oriented_size"] == ([item[1], item[0]] if quarters % 2 else list(item))
    target = (geometry.rect[0] - outer[0], geometry.rect[1] - outer[1], geometry.rect[2], geometry.rect[3])
    oriented = target if quarters == 0 else tuple(logical_rect_from_physical_rect(
        target, physical_size=item, content_rotation_quarters=quarters))
    dpr = float(presentation.dpr)
    assert card["item_from_target"] == pytest.approx([1 / dpr, 0.0, oriented[0], 0.0, 1 / dpr, oriented[1]])
    assert card["target_size"] == [float(v) for v in geometry.texture_size]
    # The far corner of the target lands on the oriented target rect's far corner.
    far = (card["target_size"][0] * card["item_from_target"][0] + card["item_from_target"][2],
           card["target_size"][1] * card["item_from_target"][4] + card["item_from_target"][5])
    assert far == pytest.approx((oriented[0] + oriented[2], oriented[1] + oriented[3]))


def test_the_face_speaks_the_modules_entries(monkeypatch) -> None:
    """Every NativeSpectrum call reaches its module entry with the composite's handle, and the card is checked whole
    before it is sent."""
    from rendering.native.composite import CompositeItem
    from rendering.native.spectrum import NativeSpectrum, SPECTRUM_PRESENTATION_KEYS

    calls = []

    class Module:
        def __getattr__(self, name):
            def call(*args):
                calls.append((name, args))
                if name == "composite_spectrum_state":
                    return json.dumps({"ok": True})
                return None
            return call

    module = Module()
    spectrum = NativeSpectrum(module, CompositeItem(module, 5))
    spectrum.bind("srpss_viz_abc_1", expect={"runtime_generation": 1, "engine_generation": 2, "activation_id": 3,
                                             "mode_code": 1}, controls=("pause_in_copy",))
    spectrum.present_raw({key: 0 for key in SPECTRUM_PRESENTATION_KEYS})
    with pytest.raises(ValueError):
        spectrum.present_raw({"quarters": 0})
    spectrum.update()
    spectrum.drop_retained_frame()
    spectrum.retire()
    spectrum.unbind()
    assert spectrum.state() == {"ok": True}
    names = [name for name, _args in calls]
    assert names == ["composite_spectrum_bind", "composite_spectrum_present", "composite_update",
                     "composite_spectrum_drop", "composite_spectrum_retire", "composite_spectrum_unbind",
                     "composite_spectrum_state"]
    assert all(args[0] == 5 for _name, args in calls)
    bound = json.loads(calls[0][1][2])
    assert bound["controls"] == ["pause_in_copy"] and bound["expect"]["mode_code"] == 1


def test_the_native_bake_draws_the_products_own_spectrum_shader() -> None:
    """One fragment shader for both renderers: the module bakes widgets/spotify_visualizer/shaders/spectrum.frag from
    where the Python renderer loads it (no copy under native/core/shaders), with the conventions marker both splice."""
    from widgets.spotify_visualizer.shaders import CONVENTIONS_MARKER

    cmake = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "widgets/spotify_visualizer/shaders/spectrum.frag" in cmake
    assert not (CORE / "shaders" / "spectrum.frag").exists()
    assert CONVENTIONS_MARKER in (CORE / "cmake" / "compose_shader.cmake").read_text(encoding="utf-8")
    source = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "spectrum.frag").read_text(encoding="utf-8")
    assert source.count(CONVENTIONS_MARKER) == 1
    code = re.sub(r"//[^\n]*", "", source)
    assert "gl_FragCoord" not in code                                   # the pixel comes through fragPixel (N1.4)


def _cpp_constant(name: str) -> float:
    text = (CORE / "src" / "spectrum.cpp").read_text(encoding="utf-8")
    match = re.search(rf"constexpr (?:int|double) {name} = ([0-9.]+);", text)
    assert match, name
    return float(match.group(1))


def test_the_ports_constants_are_the_python_renderers() -> None:
    """Each constant of the ported arithmetic equals the Python module that owns it (never a pinned value)."""
    from rendering.quick.visualizer.implementations.spectrum import MAX_BAR_GAP
    from widgets.spotify_visualizer import spectrum_display_bar_count, spectrum_solid_hysteresis
    from widgets.spotify_visualizer.spectrum_frame_inputs import MAX_LEVELS

    assert _cpp_constant("kMaxBars") == MAX_LEVELS == spectrum_display_bar_count.SPECTRUM_MAX_DISPLAY_BARS
    assert _cpp_constant("kShaderInputScale") == spectrum_solid_hysteresis.SPECTRUM_SHADER_INPUT_SCALE
    assert _cpp_constant("kBaseHeight") == spectrum_solid_hysteresis._SPECTRUM_BASE_HEIGHT
    assert _cpp_constant("kExpandedGain") == spectrum_display_bar_count.SPECTRUM_EXPANDED_HORIZONTAL_BAR_GAIN
    assert _cpp_constant("kMaxBarGap") == MAX_BAR_GAP


@pytest.mark.parametrize("source, playing", [((5, 7), True), ((5, 8), True), ((-1, -1), True), ((4, 7), False)])
def test_the_slot_carries_the_nodes_admission(source, playing) -> None:
    """The native item cannot see a frame's source identity (not in the record), so the writer states it in the slot:
    FLAG_SOURCE_CURRENT is set exactly when render_contract.snapshot_has_current_reactive_source holds, and the item's
    admission (spectrum.cpp) is snapshot_is_render_admissible over the head's bits, for a mode that requires its tracked
    source (Spectrum does; the item hard-codes that, so this holds it to mode_capabilities)."""
    from types import SimpleNamespace

    from core.visualizer_engine.packet_abi import FLAG_PLAYING, FLAG_PRESENT_FRAME, FLAG_SOURCE_CURRENT
    from core.visualizer_engine.packet_mailbox import publication_flags
    from rendering.quick.visualizer.render_contract import (
        snapshot_has_current_reactive_source,
        snapshot_is_render_admissible,
    )
    from widgets.spotify_visualizer import mode_capabilities

    assert mode_capabilities.requires_authoritative_first_source("spectrum")
    logical = SimpleNamespace(mode_id="spectrum", present_frame=True, playing=playing, changed=True,
                              mode_reveal_ready=False, source_generation=source[0], source_activation_id=source[1],
                              engine_generation=5, activation_id=7)
    snapshot = SimpleNamespace(logical=logical)
    flags = publication_flags(logical)
    assert bool(flags & FLAG_SOURCE_CURRENT) == snapshot_has_current_reactive_source(snapshot)
    native = bool(flags & FLAG_PRESENT_FRAME) and (not flags & FLAG_PLAYING or bool(flags & FLAG_SOURCE_CURRENT))
    assert native == snapshot_is_render_admissible(snapshot)
    text = (CORE / "src" / "spectrum.cpp").read_text(encoding="utf-8")
    assert "kFlagPresentFrame" in text and "kFlagSourceCurrent" in text


def test_every_block_member_the_python_renderer_writes_is_set_by_the_port() -> None:
    """The port names every member of SpectrumDraw the Python renderer writes (the block declared in spectrum.frag),
    except the quad's matrix, which the core's full-target triangle does not read."""
    from rendering.quick.visualizer.implementations.spectrum import SPECTRUM_BLOCK

    text = (CORE / "src" / "spectrum.cpp").read_text(encoding="utf-8")
    set_names = set(re.findall(r'values\.set\("(\w+)"', text)) | {"u_bars", "u_peaks"}
    declared = {name for name, _kind in SPECTRUM_BLOCK.fields}
    assert declared - set_names == {"uMatrix"}
    assert set_names <= declared

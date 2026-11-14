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

    import struct

    from rendering.native.spectrum import _ortho_item_matrix
    from rendering.quick.visualizer.implementations.spectrum import item_from_fragment

    presentation = _presentation(content_rotation_quarters=quarters)
    geometry = composite_geometry(presentation)
    window_size, window_pixels = (1920.0, 1080.0), (2880, 1620)
    card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels)
    assert set(card) == set(SPECTRUM_PRESENTATION_KEYS)
    json.dumps(card)                                                    # plain data for the module
    outer = tuple(float(v) for v in presentation.outer_rect)
    item = (outer[2], outer[3])
    assert card["oriented_size"] == ([item[1], item[0]] if quarters % 2 else list(item))
    target = (geometry.rect[0] - outer[0], geometry.rect[1] - outer[1], geometry.rect[2], geometry.rect[3])
    oriented = target if quarters == 0 else tuple(logical_rect_from_physical_rect(
        target, physical_size=item, content_rotation_quarters=quarters))
    dpr = float(presentation.dpr)
    assert card["target_size"] == [float(v) for v in geometry.texture_size]
    # The window map is the Python renderer's own: item_from_fragment of Qt's float32 item matrix, bit for bit as
    # float32 (what the GPU reads).
    python_rows = item_from_fragment(_ortho_item_matrix(window_size, outer[:2], single=True), (0, 0, *window_pixels),
                                     item, quarters, card["oriented_size"])
    f32 = lambda values: struct.pack(f"<{len(values)}f", *values)                     # noqa: E731
    assert f32(card["item_from_window"]) == f32((*python_rows[0], *python_rows[1]))
    # The target's pixel is rebuilt as the window's by whole pixels and signs only (exact in float32)...
    rebuild = card["window_from_target"]
    assert all(value == round(value) for value in rebuild)
    assert sorted(abs(v) for v in (rebuild[0], rebuild[1], rebuild[3], rebuild[4])) == [0.0, 0.0, 1.0, 1.0]
    # ...and lands, through the window map, where the target's pixel lies in the oriented item (both corners).
    for u, v in ((0.5, 0.5), (card["target_size"][0] - 0.5, card["target_size"][1] - 0.5)):
        x = rebuild[0] * u + rebuild[1] * v + rebuild[2]
        y = rebuild[3] * u + rebuild[4] * v + rebuild[5]
        mapped = (card["item_from_window"][0] * x + card["item_from_window"][1] * y + card["item_from_window"][2],
                  card["item_from_window"][3] * x + card["item_from_window"][4] * y + card["item_from_window"][5])
        assert mapped == pytest.approx((oriented[0] + u / dpr, oriented[1] + v / dpr), abs=1e-3)


#: Displays whose logical window size times the scale is not the framebuffer (Qt rounds the logical size): 2560x1440
#: at 150 % is a 1707x960 window, 3840x2160 at 175 % a 2194x1234 one (audit 14 Nov, H1).
FRACTIONAL_DISPLAYS = (((2560, 1440), 1.5), ((3840, 2160), 1.75))


@pytest.mark.parametrize("display", FRACTIONAL_DISPLAYS, ids=("2560x1440@150", "3840x2160@175"))
@pytest.mark.parametrize("quarters", [0, 1, 2, 3])
def test_the_card_maps_at_a_fractional_scale_with_the_windows_own_ratio(display, quarters) -> None:
    """Audit 14 Nov, H1: on a display whose logical size times dpr is not its framebuffer, the composite lies on the
    window's own device pixels (framebuffer over logical size, per axis) and the card's window map is whole pixels.
    Control: the same card placed on dpr's grid (the code before the fix) raises."""
    from rendering.native.composite import composite_geometry, window_pixel_ratio
    from rendering.native.spectrum import spectrum_presentation
    from widgets.spotify_visualizer.presentation_orientation import logical_rect_from_physical_rect

    (device_width, device_height), dpr = display
    window_size = (float(round(device_width / dpr)), float(round(device_height / dpr)))
    # The framebuffer as Qt's own swapchain or redirect target reports it (CompositeItem.window_pixels, audit N29 L1).
    window_pixels = (device_width, device_height)
    ratio = window_pixel_ratio(window_size, window_pixels)
    assert ratio != (dpr, dpr)                                     # the case: the two ratios differ
    # A card well away from the window's left and top edge (the offset error grows with the distance).
    presentation = _presentation(content_rotation_quarters=quarters, dpr=dpr, display_size=window_size,
                                 viewport_extent=(820.0, 210.0), outer_origin=(803.0, 517.0))
    assert tuple(presentation.outer_rect[:2]) == (803.0, 517.0)
    geometry = composite_geometry(presentation, quad_aligned=True, pixel_ratio=ratio)
    for edge, axis in ((geometry.rect[0], 0), (geometry.rect[1], 1), (geometry.rect[0] + geometry.rect[2], 0),
                       (geometry.rect[1] + geometry.rect[3], 1)):
        device = edge * ratio[axis]
        assert device == pytest.approx(round(device), abs=1e-6) and round(device) % 2 == 0
    assert geometry.item_config()["pixel_ratio"] == list(ratio)
    card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels)
    rebuild = card["window_from_target"]
    assert all(value == round(value) for value in rebuild)
    outer = tuple(float(v) for v in presentation.outer_rect)
    item = (outer[2], outer[3])
    target = (geometry.rect[0] - outer[0], geometry.rect[1] - outer[1], geometry.rect[2], geometry.rect[3])
    oriented = target if quarters == 0 else tuple(logical_rect_from_physical_rect(
        target, physical_size=item, content_rotation_quarters=quarters))
    oriented_ratio = (ratio[1], ratio[0]) if quarters % 2 else ratio
    for u, v in ((0.5, 0.5), (card["target_size"][0] - 0.5, card["target_size"][1] - 0.5)):
        x = rebuild[0] * u + rebuild[1] * v + rebuild[2]
        y = rebuild[3] * u + rebuild[4] * v + rebuild[5]
        assert 0.0 <= x <= window_pixels[0] and 0.0 <= y <= window_pixels[1]
        mapped = (card["item_from_window"][0] * x + card["item_from_window"][1] * y + card["item_from_window"][2],
                  card["item_from_window"][3] * x + card["item_from_window"][4] * y + card["item_from_window"][5])
        assert mapped == pytest.approx((oriented[0] + u / oriented_ratio[0], oriented[1] + v / oriented_ratio[1]),
                                       abs=1e-3)
    # Control: placed on dpr's grid, as before the fix, the card's map is not whole pixels.
    with pytest.raises(ValueError, match="whole-pixel"):
        spectrum_presentation(presentation, composite_geometry(presentation, quad_aligned=True),
                              window_size=window_size, window_pixels=window_pixels)


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
    # The admission is every mode item's (N2.9 round 2: stream_source.cpp's syncStream, under SpectrumSource too).
    text = (CORE / "src" / "stream_source.cpp").read_text(encoding="utf-8")
    assert "kFlagPresentFrame" in text and "kFlagSourceCurrent" in text and "kFlagPlaying" in text
    assert "class SpectrumSource final : public StreamSource" in (CORE / "src" / "spectrum.h").read_text(encoding="utf-8")


def test_the_port_sets_exactly_the_frame_members_by_name() -> None:
    """Since round 4 (the standing port rule) the core's C++ sets only the per-frame members of SpectrumDraw, by name
    (``setFrame``); every other member arrives from Python by name (``spectrum_settings_values``; its coverage of the
    block is ``test_native_program_values``). The C++'s list, its writes and Python's ``SPECTRUM_FRAME_MEMBERS`` are
    one set, all declared in the block."""
    from rendering.quick.visualizer.implementations.spectrum import SPECTRUM_BLOCK, SPECTRUM_FRAME_MEMBERS

    text = (CORE / "src" / "spectrum.cpp").read_text(encoding="utf-8")
    written = set(re.findall(r'setFrame\(packed, "(\w+)"', text))
    listed = set(re.findall(r'"(u_\w+)"', text.split("kSpectrumFrameMembers[] = {", 1)[1].split("};", 1)[0]))
    declared = {name for name, _kind in SPECTRUM_BLOCK.fields}
    assert written and written == listed == set(SPECTRUM_FRAME_MEMBERS)
    assert written <= declared

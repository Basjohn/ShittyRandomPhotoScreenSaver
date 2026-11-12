"""N2.4's composite (native/core: composite, surfaces; rendering/native/composite.py; native/core/python/composite_check.py
and composite_analysis.py), the parts that need no built module:

- the composite's geometry comes from the one record (presentation_geometry): the target on whole device pixels, the
  card's clip path as its coverage in every display style, the coverage skipped only for an admitted overflow;
- the analysis reads one-to-one texels and the coverage off a frame, and fails a shifted, stretched or unturned frame
  and a pixel changed outside the coverage;
- the composite's coverage never covers a pixel the card contract calls outside the card's inner edge;
- the C++ material reads only the members its shader declares;
- the Python face refuses what the module would refuse and passes the rest through, on a stand-in module;
- the harness fails a run that leaves a composite behind, and a contract reading with a seam or nothing lit.
The built module's runs are tests/test_native_core_module.py (skipped where no build is in the checkout).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
sys.path.insert(0, str(CORE / "python"))

import composite_analysis as ca  # noqa: E402
import composite_check  # noqa: E402

from core.settings.fullscreen_overlays import (  # noqa: E402
    DISPLAY_STYLE_DEFAULT,
    DISPLAY_STYLES,
)
from core.settings.visualizer_mode_registry import (  # noqa: E402
    VisualizerClipPolicy,
    VisualizerModePresentationPolicy,
    VisualizerShellPolicy,
    iter_all_visualizer_mode_descriptors,
)
from rendering.native import composite_geometry  # noqa: E402
from rendering.native.composite import CompositeGeometry  # noqa: E402
from tools import card_clip_contract as contract  # noqa: E402
from widgets.spotify_visualizer.presentation_geometry import (  # noqa: E402
    resolve_card_clip_path,
    resolve_expanded_visualizer_presentation,
    resolve_visualizer_presentation,
)

CARD_POLICY = VisualizerModePresentationPolicy(
    shell_policy=VisualizerShellPolicy.CARD, clip_policy=VisualizerClipPolicy.CARD_INTERIOR,
    viewport_resize_capable=True, content_rotation_capable=True)
FRAMELESS_POLICY = next(d.presentation_policy for d in iter_all_visualizer_mode_descriptors()
                        if d.presentation_policy.shell_policy is VisualizerShellPolicy.FRAMELESS)
DISPLAY = (960.0, 600.0)


def _record(dpr: float, *, policy=CARD_POLICY, scale: float = 1.0, quarters: int = 0, shift: float = 0.0):
    return resolve_visualizer_presentation(
        policy=policy, display_size=DISPLAY, dpr=dpr, uniform_visual_scale=scale, content_rotation_quarters=quarters,
        outer_origin=(24.0 + contract.OFF_GRID + shift, 40.0 + contract.OFF_GRID + shift), **contract.CONTRACT_CARD)


def _whole(value: float) -> bool:
    return abs(value - round(value)) < 1e-6


# ------------------------------------------------------------------------------------------------- the geometry


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5])
@pytest.mark.parametrize("scale", [1.0, 0.85, 1.37])
@pytest.mark.parametrize("shift", [0.0, 1.0, 3.0])
def test_the_target_lies_on_whole_device_pixels_with_the_cards_clip_as_its_coverage(dpr, scale, shift):
    record = _record(dpr, scale=scale, shift=shift)
    geometry = composite_geometry(record)
    x, y, w, h = geometry.rect
    assert all(_whole(v * dpr) for v in (x, y, w, h)), geometry.rect
    assert geometry.pixel_size == (round(w * dpr), round(h * dpr))
    (clip_x, clip_y, clip_w, clip_h), radius = resolve_card_clip_path(record)
    (cx, cy, cw, ch), cover_radius = geometry.coverage
    assert (cx + x, cy + y, cw, ch) == pytest.approx((clip_x, clip_y, clip_w, clip_h), abs=1e-9)
    assert cover_radius == radius and not geometry.overflow_admitted
    # Negative control: the record's own outer rect is off the device grid (what the drawn rect snaps).
    assert not all(_whole(v * dpr) for v in record.outer_rect[:2])


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5])
def test_a_frameless_shell_gets_the_smallest_device_rect_around_it(dpr):
    record = _record(dpr, policy=FRAMELESS_POLICY)
    geometry = composite_geometry(record)
    x, y, w, h = geometry.rect
    ox, oy, ow, oh = record.outer_rect
    assert all(_whole(v * dpr) for v in (x, y, w, h))
    assert x <= ox and y <= oy and x + w >= ox + ow and y + h >= oy + oh
    assert x > ox - 1.0 / dpr and x + w < ox + ow + 1.0 / dpr
    (cx, cy, cw, ch), _radius = geometry.coverage
    assert (cx + x, cy + y, cw, ch) == pytest.approx(tuple(record.content_rect))


@pytest.mark.parametrize("style", DISPLAY_STYLES)
def test_each_display_style_keeps_its_own_clip_and_holds_an_overflow_to_the_display(style):
    dpr = 1.25
    ordinary = _record(dpr, policy=FRAMELESS_POLICY)
    record = resolve_expanded_visualizer_presentation(ordinary, display_size=DISPLAY, dpr=dpr, display_style=style)
    window = (0.0, 0.0, 2 * DISPLAY[0], 2 * DISPLAY[1])
    held = composite_geometry(record, overflow_requested=True, overflow_rect=window)
    if style == DISPLAY_STYLE_DEFAULT:
        # The one admitted exception: the coverage skipped, the target reaching as far as the overflow may.
        assert held.overflow_admitted and held.coverage is None and held.rect == window
    else:
        # Held: the card's own coverage (the display rect), the target the card's.
        assert not held.overflow_admitted and held.coverage == composite_geometry(record).coverage
        (cx, cy, cw, ch), _radius = held.coverage
        assert (held.rect[0] + cx, held.rect[1] + cy, cw, ch) == pytest.approx((0.0, 0.0, *DISPLAY))
    with pytest.raises(ValueError, match="overflow_rect"):
        composite_geometry(_record(dpr, policy=FRAMELESS_POLICY), overflow_requested=True)


def test_a_quarter_turn_transposes_the_surface_and_reaches_the_item():
    turned = composite_geometry(_record(1.25, quarters=1))
    assert turned.quarters == 1 and turned.texture_size == turned.pixel_size[::-1]
    assert composite_geometry(_record(1.25, quarters=2)).texture_size == composite_geometry(_record(1.25)).pixel_size
    config = turned.item_config((turned.rect[0], turned.rect[1]))
    assert config["rect"][:2] == [0.0, 0.0] and config["quarters"] == 1
    assert set(config["coverage"]) == {"rect", "radius"}


# ------------------------------------------------------------------------------------------------- the analysis

SHAPE = (120, 200)


def _geometry(quarters: int = 0, coverage=((5.0, 5.0, 110.0, 70.0), 8.0)) -> dict:
    return ca.geometry_px((20.0, 10.0, 120.0, 80.0), (120, 80), coverage, quarters, 1.0)


def _render(geometry: dict, hidden: np.ndarray) -> np.ndarray:
    """What a one-to-one composite of the texel pattern draws over ``hidden``."""
    out = hidden.copy()
    covered = ca.coverage_distance(geometry, SHAPE) <= 0.0
    ex, ey = ca.expected_texels(geometry, SHAPE)
    high = ((ex >> 8) & 15) | (((ey >> 8) & 15) << 4)
    pattern = np.stack([ex & 255, ey & 255, high, np.full(SHAPE, 255)], axis=-1).astype(np.uint8)
    out[covered] = pattern[covered]
    return out


def _hidden() -> np.ndarray:
    hidden = np.zeros((*SHAPE, 4), np.uint8)
    hidden[...] = (32, 48, 64, 255)
    return hidden


@pytest.mark.parametrize("quarters", [0, 1, 2, 3])
def test_a_one_to_one_frame_passes_and_a_shifted_stretched_or_unturned_one_fails(quarters):
    hidden = _hidden()
    geometry = _geometry(quarters)
    drawn = _render(geometry, hidden)
    result = ca.analyse_texels(drawn, hidden, geometry)
    assert result["pass"], result
    # Shifted one pixel right: every covered pixel shows its neighbour's texel.
    shifted = hidden.copy()
    shifted[:, 1:] = drawn[:, :-1]
    assert ca.analyse_texels(shifted, hidden, geometry)["checks"]["every_covered_pixel_shows_its_texel"] is False
    # Stretched: one column repeated (what an item off its device size does).
    stretched = drawn.copy()
    stretched[:, 60:] = drawn[:, 59:-1]
    assert ca.analyse_texels(stretched, hidden, geometry)["pass"] is False
    # Read with another quarter turn than drawn.
    other = dict(geometry, quarters=(quarters + 1) % 4)
    assert ca.analyse_texels(drawn, hidden, other)["checks"]["every_covered_pixel_shows_its_texel"] is False


def test_a_pixel_changed_outside_the_coverage_fails_and_a_skipped_coverage_covers_the_item():
    hidden = _hidden()
    geometry = _geometry()
    drawn = _render(geometry, hidden)
    escaped = drawn.copy()
    escaped[12, 21] = (255, 255, 255, 255)          # the item's corner, outside its rounded coverage
    result = ca.analyse_texels(escaped, hidden, geometry)
    assert result["checks"]["nothing_changed_outside_the_coverage"] is False and result["escaped"] == 1
    skipped = _geometry(coverage=None)
    assert ca.analyse_texels(_render(skipped, hidden), hidden, skipped)["covered"] == 120 * 80


def test_frame_rows_turn_a_y_up_framebuffer_the_right_way_up():
    rows = np.zeros((4, 3, 4), np.uint8)
    rows[0, 0] = (255, 0, 255, 255)                  # the scene's top-left marker, first row in memory
    frame = {"rgba": rows.tobytes(), "width": 3, "height": 4, "y_up_in_framebuffer": False}
    assert ca.oriented_marker(ca.frame_rows(frame), (255, 0, 255), 1)
    flipped = {"rgba": rows[::-1].tobytes(), "width": 3, "height": 4, "y_up_in_framebuffer": True}
    assert ca.oriented_marker(ca.frame_rows(flipped), (255, 0, 255), 1)
    # Negative control: the same memory read without the flip is upside down.
    assert not ca.oriented_marker(ca.frame_rows(dict(flipped, y_up_in_framebuffer=False)), (255, 0, 255), 1)


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5])
@pytest.mark.parametrize("style", [None, *DISPLAY_STYLES])
def test_the_composites_coverage_never_covers_a_pixel_outside_the_cards_inner_edge(dpr, style):
    record = _record(dpr)
    if style is not None:
        record = resolve_expanded_visualizer_presentation(record, display_size=DISPLAY, dpr=dpr, display_style=style)
    geometry = composite_geometry(record)
    shape = (int(DISPLAY[1] * dpr), int(DISPLAY[0] * dpr))
    decided = ca.geometry_px(geometry.rect, geometry.pixel_size, geometry.coverage, geometry.quarters, dpr)
    covered = ca.coverage_distance(decided, shape) <= 0.0
    outside = contract.outside_inner_edge(contract.inner_path(geometry.rect, record, dpr), shape, dpr)
    assert covered.sum() > 0 and int((covered & outside).sum()) == 0
    # Negative control: the coverage widened by two device pixels each side reaches past the inner edge (by more than
    # the contract's OUTSIDE_PX).
    (cx, cy, cw, ch), radius = geometry.coverage
    step = 2.0 / dpr
    wider = ca.geometry_px(geometry.rect, geometry.pixel_size,
                           ((cx - step, cy - step, cw + 2 * step, ch + 2 * step), radius + step), 0, dpr)
    if style != "hide_borders":     # Hide Borders' coverage is the whole display: there is no beyond inside it
        assert int(((ca.coverage_distance(wider, shape) <= 0.0) & outside).sum()) > 0


# ------------------------------------------------------------------------------------------------- the C++ material


def _material_members(source: str) -> set[str]:
    """The block members the C++ material looks up by their reflected names."""
    return set(re.findall(r'member\.name == QByteArrayLiteral\("(\w+)"\)', source))


def _declared_members(shader: str) -> set[str]:
    block = re.search(r"uniform buf \{(.*?)\};", shader, re.S).group(1)
    return set(re.findall(r"\b(?:mat4|float|vec4)\s+(\w+);", block))


def test_the_material_reads_exactly_the_members_both_stages_declare():
    source = (CORE / "src" / "composite.cpp").read_text(encoding="utf-8")
    read = _material_members(source)
    for stage in ("composite.vert", "composite.frag"):
        assert read == _declared_members((CORE / "shaders" / stage).read_text(encoding="utf-8")), stage
    # Negative control: the same reading of a source that looks up a member no stage declares.
    renamed = source.replace('QByteArrayLiteral("coverageOn")', 'QByteArrayLiteral("coverageOff")')
    assert renamed != source
    assert _material_members(renamed) != _declared_members((CORE / "shaders" / "composite.frag").read_text("utf-8"))


# ------------------------------------------------------------------------------------------------- the Python face


def test_the_python_face_passes_the_composite_through_and_refuses_what_the_module_would():
    from rendering.native import loader

    calls: list = []

    def record(name, result=None):
        return lambda *args: (calls.append((name, args)), result)[1]

    module = SimpleNamespace(
        host_attach=record("host_attach", 7), composite_set=record("composite_set"),
        composite_state=record("composite_state", json.dumps({"draws": 3})),
        composite_destroy=record("composite_destroy", True), composite_live=record("composite_live", "{}"),
        host_set_dpr=record("host_set_dpr"),
        host_read=record("host_read", {"rgba": b"\0" * 8, "width": 2, "height": 1, "y_up_in_framebuffer": True,
                                       "frame": 4, "prime": "not Vulkan"}))
    core = loader.NativeCore(module, {"abi": loader.EXPECTED_ABI})
    host = core.hidden_host(64, 32, dpr=1.25)
    assert calls[-1] == ("host_attach", ("hidden", 0, 64, 32, True, 1.25))
    host.set_device_pixel_ratio(1.5)
    assert calls[-1] == ("host_set_dpr", (7, 1.5))
    frame = host.read()
    assert (frame.width, frame.height, frame.y_up_in_framebuffer, frame.frame) == (2, 1, True, 4)
    with pytest.raises(TypeError, match="QQuickItem"):
        core.composite(object())
    from rendering.native.composite import CompositeItem

    item = CompositeItem(module, 3)
    geometry = CompositeGeometry((10.0, 20.0, 40.0, 30.0), (40, 30), ((5.0, 5.0, 30.0, 20.0), 2.0), 0, 1.0)
    item.place(geometry, (10.0, 0.0), pattern="white")
    name, (handle, text) = calls[-1]
    assert name == "composite_set" and handle == 3
    assert json.loads(text) == {"rect": [0.0, 20.0, 40.0, 30.0], "coverage": {"rect": [5.0, 5.0, 30.0, 20.0],
                                                                              "radius": 2.0},
                                "quarters": 0, "pattern": "white"}
    with pytest.raises(ValueError, match="unknown composite option"):
        item.set(colour="red")
    with pytest.raises(ValueError, match="unknown pattern"):
        item.set(pattern="checker")
    assert item.state() == {"draws": 3}
    assert item.destroy() is True and item.destroy() is False
    assert [c for c in calls if c[0] == "composite_destroy"] == [("composite_destroy", (3,))]
    with pytest.raises(RuntimeError, match="destroyed"):
        item.state()


# ------------------------------------------------------------------------------------------------- the harness


def test_the_harness_fails_a_run_that_leaves_a_composite_behind():
    record = {"rounds": ["texels"], "texels": {"pass": True, "checks": {"x": True}}, "live_hosts_at_end": 0,
              "module_loaded": True, "composites_at_end": {"items": 0, "surfaces": 0, "surface_resources": 0}}
    assert composite_check.api_verdict("opengl", record, require_validation=True)[0] is True
    left = dict(record, composites_at_end={"items": 0, "surfaces": 1, "surface_resources": 8})
    ok, reasons = composite_check.api_verdict("opengl", left, require_validation=True)
    assert ok is False and "composites left" in reasons[-1]


def test_the_contract_reading_fails_a_seam_an_escape_and_nothing_lit():
    held = contract.ContractReading(escapes=0, lit=10, under_frame=0, gaps={"left": 0, "right": 0, "top": 0,
                                                                           "bottom": 0})
    assert composite_check._contract_holds(held)
    assert composite_check._contract_holds(contract.ContractReading(0, 10, 0, None))      # Hide Borders: no frame
    assert not composite_check._contract_holds(contract.ContractReading(0, 10, 0, dict(held.gaps, left=1)))
    assert not composite_check._contract_holds(contract.ContractReading(0, 10, 0, dict(held.gaps, top=None)))
    assert not composite_check._contract_holds(contract.ContractReading(3, 10, 0, held.gaps))
    assert not composite_check._contract_holds(contract.ContractReading(0, 10, 2, held.gaps))
    assert not composite_check._contract_holds(contract.ContractReading(0, 0, 0, held.gaps))

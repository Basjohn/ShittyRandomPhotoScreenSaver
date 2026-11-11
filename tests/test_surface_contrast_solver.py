"""The card legibility solver (rendering/quick/qml/SurfaceContrast.js), run in a QJSEngine.

Contract: Docs/Architecture/Card_Surface_Materials.md 3.3 "Dark ink: bounded surface and
corrected ink". Colours here are test-owned inputs, never theme values.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "rendering" / "quick" / "qml" / "SurfaceContrast.js"

# Test-owned material uniforms of the shape MaterialSurface.qml passes (blurTint, lightNoise,
# glassLegibility): one with a luminosity pull and tint, one with haze, one plain glass.
PARAMS = {
    "mica": ((1.0, 0.5, 0.6, 0.7), (0.3, 0.0, 0.0, 0.0), (0.0, 0.0, 0.30, 0.0)),
    "frosted": ((1.0, 0.16, 0.34, 0.8), (0.0, 0.045, 0.18, 0.0), (0.05, 0.0, 0.20, 0.0)),
    "glass": ((0.0, 0.05, 0.28, 1.15), (0.0, 0.0, 0.0, 0.0), (0.2, 4.5, 0.20, 0.0)),
}


@pytest.fixture
def solver(qt_app):
    from PySide6.QtQml import QJSEngine

    engine = QJSEngine()
    source = JS.read_text(encoding="utf-8").replace(".pragma library", "")
    result = engine.evaluate(source)
    assert not result.isError(), result.toString()

    def call(expression: str):
        value = engine.evaluate(expression)
        assert not value.isError(), value.toString()
        return value.toVariant()

    yield call
    del engine


def _colour(rgba) -> str:
    r, g, b, a = rgba
    return f"({{r: {r / 255}, g: {g / 255}, b: {b / 255}, a: {a}}})"


def _params(material: str) -> str:
    rows = ", ".join("{x: %s, y: %s, z: %s, w: %s}" % row for row in PARAMS[material])
    return f"[{rows}]"


def _luminance(rgb) -> float:
    def linear(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * linear(rgb[0]) + 0.7152 * linear(rgb[1]) + 0.0722 * linear(rgb[2])


def _contrast(a, b) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


DARK_INK = (28, 32, 38, 1.0)
LIGHT_TINT = (225, 228, 232, 0.93)
LIGHT_INK = (240, 242, 246, 1.0)
DARK_TINT = (30, 32, 40, 0.45)


def test_settings_calibration_table_is_the_python_one() -> None:
    from core.settings.surface_opacity import SETTINGS_DENSITY_BASELINE

    text = JS.read_text(encoding="utf-8")
    table = re.search(r"SETTINGS_DENSITY_BASELINE = \{(.*?)\}", text, re.S).group(1)
    parsed = {key: float(value) for key, value in re.findall(r'"(\w+)":\s*(-?[\d.]+)', table)}
    assert parsed == SETTINGS_DENSITY_BASELINE


def test_faint_dark_ink_never_saturates_the_panel_to_white(solver) -> None:
    faint = DARK_INK[:3] + (0.55,)
    ratio = solver(f"requiredReferenceContrast({_colour(DARK_INK)}, {_colour(faint)})")
    limits = solver(f"limits({_colour(DARK_INK)}, {ratio})")
    assert limits[1] == 0 and 0.0 < limits[2] < 0.9       # reachable, far from white
    # The full-strength reference ink reaches the same limit: the faint ink is the ink's job.
    assert ratio == pytest.approx(solver(f"requiredReferenceContrast({_colour(DARK_INK)}, {_colour(DARK_INK)})"))


def test_light_ink_keeps_its_faint_ink_floor(solver) -> None:
    faint = LIGHT_INK[:3] + (0.55,)
    faint_ratio = solver(f"requiredReferenceContrast({_colour(LIGHT_INK)}, {_colour(faint)})")
    full_ratio = solver(f"requiredReferenceContrast({_colour(LIGHT_INK)}, {_colour(LIGHT_INK)})")
    assert faint_ratio > full_ratio > 1.0                 # dark themes still carry faint ink on the panel
    limits = solver(f"limits({_colour(LIGHT_INK)}, {faint_ratio})")
    assert solver(f"panelCeiling('glass', {_params('glass')}, {_colour(DARK_TINT)}, {limits}, 0)") == 1.0


@pytest.mark.parametrize("material", sorted(PARAMS))
@pytest.mark.parametrize("adjustment", (-1.0, 0.0, 0.5))
def test_bounded_panel_carries_the_reference_ink_and_keeps_the_backdrop(solver, material, adjustment) -> None:
    ratio = solver(f"requiredReferenceContrast({_colour(DARK_INK)}, {_colour(DARK_INK[:3] + (0.55,))})")
    limits = solver(f"limits({_colour(DARK_INK)}, {ratio})")
    params, tint = _params(material), _colour(LIGHT_TINT)
    ceiling = solver(f"panelCeiling('{material}', {params}, {tint}, {limits}, {adjustment})")
    assert 0.0 <= ceiling < 1.0
    shell = solver(f"shellDensity('{material}', {tint}, {adjustment})")
    transmission = solver(f"materialTransmission({params}, {tint}, {adjustment})")
    poles = solver(f"inkPoles({params}, {tint}, {limits}, {ceiling}, {adjustment})")
    ink = tuple(v / 255 for v in DARK_INK[:3])
    # The reference ink reads over the composed panel on a black and a white backdrop (the
    # poles carry the grain at its darkest; the 4.8 target's headroom is for that grain).
    grain = 0.5 * PARAMS[material][1][1]
    poles = [[min(1.0, c + grain) for c in pole] for pole in poles]
    assert min(_contrast(ink, pole) for pole in poles) >= 4.8 - 0.02
    # The panel stops at the Settings-variant shell density unless the reference ink needs more.
    assert _luminance(poles[1]) - _luminance(poles[0]) > 0.0      # the backdrop still moves it
    shell_cap = min(1.0, max(0.0, 1.0 - (1.0 - shell) / transmission))
    if ceiling > shell_cap + 1e-6:
        # Only the reference ink's own need lifts it past the shell: just to its limit over black.
        assert _luminance(poles[0]) == pytest.approx(limits[2], abs=0.02)
    else:
        assert ceiling == pytest.approx(shell_cap)


@pytest.mark.parametrize("opacity", (1.0, 0.7))
def test_faint_dark_ink_is_corrected_not_the_panel(solver, opacity) -> None:
    ratio = solver(f"requiredReferenceContrast({_colour(DARK_INK)}, {_colour(DARK_INK[:3] + (0.55,))})")
    limits = solver(f"limits({_colour(DARK_INK)}, {ratio})")
    params, tint = _params("frosted"), _colour(LIGHT_TINT)
    ceiling = solver(f"panelCeiling('frosted', {params}, {tint}, {limits}, 0)")
    poles = solver(f"inkPoles({params}, {tint}, {limits}, {ceiling}, 0)")
    faint = DARK_INK[:3] + (0.5,)
    ink = solver(f"legibleInk({_colour(faint)}, {opacity}, {poles}, true)")
    assert ink[4] is True
    alpha = ink[3] * opacity
    for pole in poles:
        composed = [p + (c - p) * alpha for p, c in zip(pole, ink[:3])]
        assert _contrast(composed, pole) >= 4.8 - 1e-3
    # Hue kept: a darkened ink is a scaled copy of the authored channels.
    if ink[3] == 1.0 and ink[0] < DARK_INK[0] / 255:
        scale = ink[0] / (DARK_INK[0] / 255)
        assert ink[1] == pytest.approx(DARK_INK[1] / 255 * scale, abs=1e-6)
    # An ink that already reads is returned exactly.
    same = solver(f"legibleInk({_colour(DARK_INK)}, 1.0, {poles}, true)")
    assert same[:4] == pytest.approx([DARK_INK[0] / 255, DARK_INK[1] / 255, DARK_INK[2] / 255, 1.0])


def test_an_opacity_faded_run_that_black_cannot_rescue_asks_for_a_plate(solver) -> None:
    poles = [[0.55, 0.55, 0.55], [0.95, 0.95, 0.95]]
    ink = solver(f"legibleInk({_colour(DARK_INK)}, 0.4, {poles}, true)")
    assert ink[4] is False and ink[:4] == [0, 0, 0, 1]

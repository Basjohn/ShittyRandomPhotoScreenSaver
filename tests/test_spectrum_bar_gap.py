"""Spectrum's Bar Gap: one spec control, carried to the renderer's layout; the default is the former fixed gap."""
from __future__ import annotations


import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings
from rendering.quick.visualizer.implementations.spectrum import (
    DEFAULT_BAR_GAP, MAX_BAR_GAP, compute_quick_spectrum_layout,
)

KEY = "spectrum_bar_gap"


def _layout(scale: float = 1.0, count: int = 37, **extra):
    return compute_quick_spectrum_layout(local_content_rect=(0.0, 0.0, 420.0 * scale, 280.0 * scale),
                                         viewport_extent=(420.0, 280.0), visual_scale=scale, bar_count=count, **extra)


def test_the_spec_declares_the_gap_and_its_default_is_the_former_fixed_gap():
    control = require_mode_settings("spectrum").control(KEY)
    default = require_canonical_default(f"widgets.spotify_visualizer.{KEY}")
    assert (control.low, control.high) == (0.0, MAX_BAR_GAP)
    assert default == DEFAULT_BAR_GAP
    assert control.admit(default, default) == default
    assert control.admit(99.0, default) == MAX_BAR_GAP and control.admit(-1.0, default) == 0.0


@pytest.mark.parametrize("scale", (1.0, 2.5))
def test_the_default_gap_lays_the_bars_out_as_before(scale):
    assert _layout(scale) == _layout(scale, bar_gap=DEFAULT_BAR_GAP)
    assert _layout(scale).bar_gap == pytest.approx(2.0 * scale)


@pytest.mark.parametrize("scale", (1.0, 2.5))
def test_the_gap_trades_width_inside_one_span(scale):
    joined, classic, airy = (_layout(scale, bar_gap=gap) for gap in (0.0, DEFAULT_BAR_GAP, MAX_BAR_GAP))
    assert joined.bar_gap == 0.0 and joined.bar_width * 37 == pytest.approx(joined.bar_span)
    assert joined.bar_span == pytest.approx(classic.bar_span) == pytest.approx(airy.bar_span)
    assert joined.bars_left == classic.bars_left == airy.bars_left
    assert joined.bar_width > classic.bar_width > airy.bar_width > 0.0
    assert airy.bar_gap == pytest.approx(MAX_BAR_GAP * scale)
    # Negative control: a gap outside the admitted range is clamped, never drawn.
    assert _layout(scale, bar_gap=50.0) == airy and _layout(scale, bar_gap=-3.0) == joined


def test_the_gap_is_presentation_owned():
    """It travels in the frame's common style beside Border Radius (``tests/test_spectrum_settings_spec.py`` follows a
    value from Settings to that style); it is neither a source nor a logical control."""
    spec = require_mode_settings("spectrum")
    assert KEY in {control.key for control in spec.presentation_controls()}
    assert KEY not in {control.key for control in (*spec.source_controls(), *spec.logical_controls())}

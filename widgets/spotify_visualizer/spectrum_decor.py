"""Spectrum's optional decoration (ghost colour, fill gradient, gloss, peak caps, pattern, the rim glow's placement and
sharpness) as renderer parameters.

The values are the presentation owner's spec'd controls (``core/settings/visualizer_mode_settings.py``). A toggled
decoration fades in and out instead of popping: ``SpectrumDecorFade`` keeps one envelope per decoration on the
presentation owner and advances it on the capture's own logical timestamp (``now_ts``), so it adds no clock, timer
or thread, and a fresh owner (a new activation, an exact Studio replay) starts settled at the current settings. A
pattern switched to another pattern (or another anchor) dips through zero and comes back as the new one.

Every envelope at rest is exactly 0 or 1, so the default (all off) parameters are constants and the shader takes
none of the decoration branches. The rim glow's two side envelopes rest at 1 with Rim Placement's default (Both),
where the shader draws today's rim exactly.
"""
from __future__ import annotations

from typing import Any

from rendering.gl_programs.spectrum_options import SPECTRUM_PATTERNS, SPECTRUM_RIM_PLACEMENTS

FADE_SECONDS = 0.6            # a full fade in or out
_MAX_STEP = 0.1               # a capture gap longer than this (pause, stall) advances at most this much
_SNAP = 1e-6                  # an envelope this close to its end has arrived (exactly 0 or 1 at rest)


def _toward(level: float, target: float, step: float) -> float:
    level = min(target, level + step) if target > level else max(target, level - step)
    return target if abs(target - level) <= _SNAP else level

DECOR_KEYS = (
    "spectrum_ghost_color_source", "spectrum_ghost_color", "spectrum_ghost_gradient", "spectrum_ghost_tip_color",
    "spectrum_gloss", "spectrum_fill_gradient", "spectrum_fill_tip_color", "spectrum_peak_caps",
    "spectrum_peak_cap_color", "spectrum_peak_cap_thickness", "spectrum_pattern", "spectrum_pattern_color",
    "spectrum_pattern_scale", "spectrum_pattern_strength", "spectrum_pattern_anchor",
    "spectrum_glow_placement", "spectrum_glow_sharpness",
)
_ATTRS = tuple((key, "_" + key) for key in DECOR_KEYS)
_TOGGLES = {
    "ghost_custom": lambda pres: pres._spectrum_ghost_color_source == "Custom",
    "ghost_fill": lambda pres: pres._spectrum_ghost_color_source == "Bar Fill",
    "ghost_gradient": lambda pres: bool(pres._spectrum_ghost_gradient),
    "fill_gradient": lambda pres: bool(pres._spectrum_fill_gradient),
    "peak_caps": lambda pres: bool(pres._spectrum_peak_caps),
    # Rim Placement as one envelope per side, so a side's rim fades in or out when the placement changes. Any value
    # but Left or Right is Both (an unknown stored value falls back quietly).
    "glow_left": lambda pres: pres._spectrum_glow_placement != SPECTRUM_RIM_PLACEMENTS[1],
    "glow_right": lambda pres: pres._spectrum_glow_placement != SPECTRUM_RIM_PLACEMENTS[0],
}


def _smooth(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


class SpectrumDecorFade:
    """Fade envelopes for Spectrum's optional decorations, advanced on the capture timestamp."""

    def __init__(self, pres: Any) -> None:
        self._levels = {name: (1.0 if wanted(pres) else 0.0) for name, wanted in _TOGGLES.items()}
        self._pattern, self._anchor = self._wanted_pattern(pres)
        self._pattern_level = 0.0 if self._pattern == SPECTRUM_PATTERNS[0] else 1.0
        self._last_ts: float | None = None
        self._mixes: dict[str, object] | None = None      # rebuilt only when a level moves

    @staticmethod
    def _wanted_pattern(pres: Any) -> tuple[str, str]:
        return str(pres._spectrum_pattern), str(pres._spectrum_pattern_anchor)

    def advance(self, pres: Any, now_ts: float) -> bool:
        """Move every envelope toward the current settings; True while any is still moving."""
        now = float(now_ts)
        dt = 0.0 if self._last_ts is None else max(0.0, min(_MAX_STEP, now - self._last_ts))
        self._last_ts = now
        step = dt / FADE_SECONDS
        moving = False
        for name, wanted in _TOGGLES.items():
            target = 1.0 if wanted(pres) else 0.0
            level = self._levels[name]
            if level != target:
                level = _toward(level, target, step)
                self._levels[name] = level
                self._mixes = None
                moving = moving or level != target
        target_pattern = self._wanted_pattern(pres)
        shown = (self._pattern, self._anchor)
        if target_pattern != shown or (self._pattern != SPECTRUM_PATTERNS[0] and self._pattern_level < 1.0):
            self._mixes = None
        if target_pattern != shown:
            # Fade the shown pattern out; then show the new one (Off shows nothing) and fade it in.
            self._pattern_level = _toward(self._pattern_level, 0.0, step)
            if self._pattern_level <= 0.0:
                self._pattern, self._anchor = target_pattern
        elif self._pattern != SPECTRUM_PATTERNS[0] and self._pattern_level < 1.0:
            self._pattern_level = _toward(self._pattern_level, 1.0, step)
        moving = moving or target_pattern != (self._pattern, self._anchor) or (
            self._pattern != SPECTRUM_PATTERNS[0] and self._pattern_level < 1.0)
        return moving

    def mixes(self) -> dict[str, object]:
        if self._mixes is None:
            out: dict[str, object] = {f"spectrum_{name}_mix": _smooth(level) for name, level in self._levels.items()}
            out["spectrum_pattern_shown"] = self._pattern
            out["spectrum_pattern_anchor_shown"] = self._anchor
            out["spectrum_pattern_mix"] = (0.0 if self._pattern == SPECTRUM_PATTERNS[0]
                                           else _smooth(self._pattern_level))
            self._mixes = out
        return dict(self._mixes)


def decor_fade(pres: Any) -> SpectrumDecorFade:
    fade = getattr(pres, "_spectrum_decor_fade", None)
    if fade is None:
        fade = SpectrumDecorFade(pres)
        pres._spectrum_decor_fade = fade
    return fade


def advance_decor_fade(pres: Any, now_ts: float) -> bool:
    """Advance the owner's envelopes to ``now_ts`` (Spectrum's capture); True while a fade is in progress."""
    return decor_fade(pres).advance(pres, now_ts)


def spectrum_decor_parameters(pres: Any) -> dict[str, object]:
    """The decoration controls (colours as tuples) and their current fade levels, for Spectrum's renderer."""
    values = decor_fade(pres).mixes()
    for key, attr in _ATTRS:
        value = getattr(pres, attr)
        values[key] = tuple(value) if isinstance(value, list) else value
    return values


__all__ = ["DECOR_KEYS", "FADE_SECONDS", "SpectrumDecorFade", "advance_decor_fade", "decor_fade",
           "spectrum_decor_parameters"]

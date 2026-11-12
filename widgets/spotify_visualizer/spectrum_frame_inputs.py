"""Every value Spectrum's renderer reads from its logical frame, declared once (native core N2.3).

Spectrum's Quick renderer (``rendering/quick/visualizer/implementations/spectrum.py``) reads its style and parameter
inputs through this declaration, and Spectrum's fixed-layout native schema
(``core/visualizer_engine/spectrum_native_schema.py``) is built from it: one field list for both, so the record the
native renderer will read cannot drift from what the Python renderer draws with. Import-safe (no Qt, no OpenGL): the
engine worker builds the schema from it.

``source`` says where a value lives in a ``VisualizerLogicalFrame``:

- ``logical``: an attribute of the logical frame itself (timing and play state);
- ``common``: ``logical.common`` (the bars and their count);
- ``mode_state``: the ``SpectrumFrame`` (peaks, the animation clock);
- ``style``: ``logical.common.style`` (the shared bar appearance);
- ``parameters``: the ``SpectrumFrame``'s ``parameters`` (Spectrum's own presentation inputs and decoration).

``kind`` is the value's shape as the renderer converts it: ``f64`` (``float(value)``), ``bool`` (``bool(value)``),
``rgba`` (a channel sequence ``implementation_values.rgba`` normalises: 3 or 4 channels, alpha 255 when absent),
``enum`` (``str(value)``'s position in ``table``; the renderer's own fallback applies to a value outside it),
``count`` (a non-negative integer) and ``levels`` (a float sequence the renderer reads at most ``MAX_LEVELS`` of).

``per_frame``: the renderer reads the parameter on every frame; ``decor``: it is one of the optional decoration's
inputs, fetched and compared only when the frame's parameters changed (``resolve_spectrum_decor_uniforms``).
"""
from __future__ import annotations

from dataclasses import dataclass

from rendering.gl_programs.spectrum_options import SPECTRUM_PATTERN_ANCHORS, SPECTRUM_PATTERNS

#: The most bars the renderer draws (``spectrum.frag``'s ``u_bars[64]``); a longer sequence is cut there.
MAX_LEVELS = 64
#: The space between bars in px at scale 1 when the style does not carry one (the long-standing fixed value).
DEFAULT_BAR_GAP = 2.0

_REQUIRED = object()


@dataclass(frozen=True, slots=True)
class SpectrumFrameInput:
    source: str
    name: str
    kind: str
    table: tuple[str, ...] = ()
    per_frame: bool = False
    decor: bool = False
    default: object = _REQUIRED

    @property
    def required(self) -> bool:
        return self.default is _REQUIRED


def _logical(name: str, kind: str) -> SpectrumFrameInput:
    return SpectrumFrameInput("logical", name, kind)


def _style(name: str, kind: str, **extra) -> SpectrumFrameInput:
    return SpectrumFrameInput("style", name, kind, per_frame=True, **extra)


def _frame(name: str, kind: str) -> SpectrumFrameInput:
    return SpectrumFrameInput("parameters", name, kind, per_frame=True)


def _decor(name: str, kind: str, table: tuple[str, ...] = (), *, per_frame: bool = False) -> SpectrumFrameInput:
    return SpectrumFrameInput("parameters", name, kind, table, per_frame=per_frame, decor=True)


SPECTRUM_FRAME_INPUTS: tuple[SpectrumFrameInput, ...] = (
    # Timing and play state.
    _logical("playing", "bool"),
    _logical("logical_timestamp", "f64"),
    SpectrumFrameInput("mode_state", "animation_time", "f64"),
    # The bars.
    SpectrumFrameInput("common", "bar_count", "count"),
    SpectrumFrameInput("common", "bars", "levels"),
    SpectrumFrameInput("mode_state", "peaks", "levels"),
    # The shared bar appearance.
    _style("fill_color", "rgba"),
    _style("border_color", "rgba"),
    _style("bar_gap", "f64", default=DEFAULT_BAR_GAP),
    _style("single_piece", "bool"),
    _style("border_radius", "f64"),
    # Spectrum's own presentation inputs, read every frame.
    _frame("spectrum_glow_color", "rgba"),
    _frame("rainbow_enabled", "bool"),
    _frame("rainbow_per_bar", "bool"),
    _frame("rainbow_speed", "f64"),
    _frame("spectrum_ghosting_enabled", "bool"),
    _frame("spectrum_ghost_alpha", "f64"),
    _frame("spectrum_glow_enabled", "bool"),
    _frame("spectrum_glow_intensity", "f64"),
    _frame("spectrum_rainbow_ghost", "bool"),
    _frame("spectrum_rainbow_fill", "bool"),
    _frame("spectrum_rainbow_border", "bool"),
    # The optional decoration (the presentation owner's resolved values and fade envelopes).
    _decor("spectrum_ghost_custom_mix", "f64"),
    _decor("spectrum_ghost_color", "rgba"),
    _decor("spectrum_ghost_fill_mix", "f64"),
    _decor("spectrum_ghost_gradient_mix", "f64"),
    _decor("spectrum_ghost_tip_color", "rgba"),
    _decor("spectrum_gloss", "f64"),
    _decor("spectrum_fill_gradient_mix", "f64"),
    _decor("spectrum_fill_tip_color", "rgba"),
    _decor("spectrum_peak_caps_mix", "f64"),
    _decor("spectrum_peak_cap_color", "rgba"),
    _decor("spectrum_peak_cap_thickness", "f64"),
    # The pattern is also read every frame: only a flag sheet's wave reads the clock.
    _decor("spectrum_pattern_shown", "enum", SPECTRUM_PATTERNS, per_frame=True),
    _decor("spectrum_pattern_anchor_shown", "enum", SPECTRUM_PATTERN_ANCHORS),
    _decor("spectrum_pattern_mix", "f64"),
    _decor("spectrum_pattern_strength", "f64"),
    _decor("spectrum_pattern_color", "rgba"),
    _decor("spectrum_pattern_scale", "f64"),
)

#: ``SpectrumFrame`` fields the Spectrum renderer does not draw from (so the native schema does not carry them):
#: the ghost bars feed Extruded Spectrum's renderer; Spectrum's ghost trail is drawn from the peaks.
SPECTRUM_FRAME_FIELDS_NOT_DRAWN = ("ghost_bars",)


def input_names(*, source: str, per_frame: bool | None = None, decor: bool | None = None) -> tuple[str, ...]:
    """The declared names from ``source``, in declaration order, optionally only the per-frame or decoration ones."""
    return tuple(entry.name for entry in SPECTRUM_FRAME_INPUTS
                 if entry.source == source
                 and (per_frame is None or entry.per_frame == per_frame)
                 and (decor is None or entry.decor == decor))


def read_style(style) -> dict[str, object]:
    """The renderer's style inputs from ``logical.common.style`` (a declared default where the style has none)."""
    values = {}
    for entry in SPECTRUM_FRAME_INPUTS:
        if entry.source == "style":
            values[entry.name] = style[entry.name] if entry.required else style.get(entry.name, entry.default)
    return values


__all__ = [
    "DEFAULT_BAR_GAP",
    "MAX_LEVELS",
    "SPECTRUM_FRAME_FIELDS_NOT_DRAWN",
    "SPECTRUM_FRAME_INPUTS",
    "SpectrumFrameInput",
    "input_names",
    "read_style",
]

"""Qt Quick Spectrum renderer consuming only one immutable snapshot."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Sequence

from OpenGL import GL as gl

from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block
from rendering.quick.render.gl_resources import compile_program, delete_program
from rendering.quick.scene3d.uniforms import PassBlocks
from widgets.spotify_visualizer.render_state import SpectrumFrame
from widgets.spotify_visualizer.shaders import load_fragment_shader
from widgets.spotify_visualizer.spectrum_display_bar_count import resample_levels, resolve_display_bar_count
from widgets.spotify_visualizer.spectrum_frame_inputs import DEFAULT_BAR_GAP, MAX_LEVELS, input_names, read_style
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    SPECTRUM_SHADER_INPUT_SCALE,
    compute_spectrum_height_scale,
)

from ..render_contract import (
    QuickVisualizerRenderFrame,
    quick_visualizer_vertex_source,
)
from ..implementation_values import parameter, rgba, safe_hue
from rendering.gl_programs.spectrum_options import SPECTRUM_FLAG_PATTERNS, SPECTRUM_PATTERN_ANCHORS, SPECTRUM_PATTERNS


_MAX_BARS = MAX_LEVELS


def _spectrum_program_parts():
    """(the quad's vertex stage, the block layout) from ``spectrum.frag``'s own ``SpectrumDraw`` declaration (N1.6):
    one declaration for both stages and for the packing. (None, None) when the shader file is unavailable."""
    fragment = load_fragment_shader("spectrum")
    if fragment is None:
        return None, None
    declaration = block_declaration(fragment, "SpectrumDraw")
    return quick_visualizer_vertex_source(declaration), block_layout_from_glsl(declaration)


SPECTRUM_VERTEX_SOURCE, SPECTRUM_BLOCK = _spectrum_program_parts()
# The space between bars in px at scale 1: the long-standing fixed value (``DEFAULT_BAR_GAP``, declared with the
# frame inputs), and the most Bar Gap admits.
MAX_BAR_GAP = 4.0


def resolve_spectrum_decor_uniforms(
    parameters, visual_scale: float,
) -> tuple[tuple[str, str, tuple], ...]:
    """(uniform, kind, values) for Spectrum's optional decoration from its frame parameters.

    Every value is already resolved by the presentation owner (``spectrum_decor``): this only maps it to the
    shader's units. Mixes are the owner's fade envelopes; a strength rides on its mix.
    """

    def unit(name: str) -> float:
        return max(0.0, min(1.0, float(parameter(parameters, name))))

    pattern = str(parameter(parameters, "spectrum_pattern_shown"))
    pattern_index = SPECTRUM_PATTERNS.index(pattern) if pattern in SPECTRUM_PATTERNS else 0
    return (
        ("u_ghost_custom_mix", "1f", (unit("spectrum_ghost_custom_mix"),)),
        ("u_ghost_color", "4f", rgba(parameter(parameters, "spectrum_ghost_color"))),
        ("u_ghost_fill_mix", "1f", (unit("spectrum_ghost_fill_mix"),)),
        ("u_ghost_gradient_mix", "1f", (unit("spectrum_ghost_gradient_mix"),)),
        ("u_ghost_tip_color", "4f", rgba(parameter(parameters, "spectrum_ghost_tip_color"))),
        ("u_gloss", "1f", (unit("spectrum_gloss"),)),
        ("u_fill_gradient_mix", "1f", (unit("spectrum_fill_gradient_mix"),)),
        ("u_fill_tip_color", "4f", rgba(parameter(parameters, "spectrum_fill_tip_color"))),
        ("u_peak_cap_mix", "1f", (unit("spectrum_peak_caps_mix"),)),
        ("u_peak_cap_color", "4f", rgba(parameter(parameters, "spectrum_peak_cap_color"))),
        ("u_peak_cap_thickness", "1f", (
            max(1.0, min(6.0, float(parameter(parameters, "spectrum_peak_cap_thickness"))))
            * max(0.01, float(visual_scale)),)),
        ("u_pattern", "1i", (pattern_index,)),
        ("u_pattern_shared", "1i", (
            1 if str(parameter(parameters, "spectrum_pattern_anchor_shown")) == SPECTRUM_PATTERN_ANCHORS[1] else 0,)),
        ("u_pattern_mix", "1f", (
            unit("spectrum_pattern_mix") * unit("spectrum_pattern_strength") if pattern_index else 0.0,)),
        ("u_pattern_color", "4f", rgba(parameter(parameters, "spectrum_pattern_color"))),
        ("u_pattern_scale", "1f", (
            max(0.25, min(4.0, float(parameter(parameters, "spectrum_pattern_scale")))),)),
    )


# Every frame parameter ``resolve_spectrum_decor_uniforms`` reads, fetched in ONE C call so a frame whose decoration
# did not change costs no per-option Python work (the options are default-off; at rest they must cost nothing).
# The names are the frame-input declaration's (``spectrum_frame_inputs``), the one list the native schema is built
# from (N2.3).
_DECOR_SOURCES = input_names(source="parameters", decor=True)
_decor_sources = operator.itemgetter(*_DECOR_SOURCES)
# The parameters read on every frame, likewise fetched in one call and only through the declaration.
_PER_FRAME_PARAMETERS = input_names(source="parameters", per_frame=True)
_per_frame_parameters = operator.itemgetter(*_PER_FRAME_PARAMETERS)


def _read_per_frame_parameters(parameters) -> dict[str, object]:
    try:
        return dict(zip(_PER_FRAME_PARAMETERS, _per_frame_parameters(parameters)))
    except KeyError:
        # The required-parameter contract names the missing one.
        return {name: parameter(parameters, name) for name in _PER_FRAME_PARAMETERS}


_DECOR_UNIFORMS = (
    "u_ghost_custom_mix", "u_ghost_color", "u_ghost_fill_mix", "u_ghost_gradient_mix", "u_ghost_tip_color",
    "u_gloss", "u_fill_gradient_mix", "u_fill_tip_color", "u_peak_cap_mix", "u_peak_cap_color", "u_peak_cap_thickness",
    "u_pattern", "u_pattern_shared", "u_pattern_mix", "u_pattern_color", "u_pattern_scale",
)


def prepare_spectrum_shader_levels(
    bars: Sequence[object],
    peaks: Sequence[object],
    *,
    bar_count: int,
) -> tuple[list[float], list[float]]:
    """Return fixed-width shader arrays with the historical final transfer.

    Authored Spectrum bars stay in their canonical logical domain.  The old GL
    renderer applied ``0.55`` only at upload time; retained Quick presentation
    must do the same rather than weakening the BeatEngine or frame runtime.
    """

    count = min(_MAX_BARS, max(0, int(bar_count)))
    resolved_bars = [float(value) for value in bars[:count]]
    if len(resolved_bars) < count:
        resolved_bars.extend([0.0] * (count - len(resolved_bars)))

    resolved_peaks = [float(value) for value in peaks[:count]]
    if len(resolved_peaks) < count:
        resolved_peaks.extend(resolved_bars[len(resolved_peaks):count])

    for index in range(count):
        resolved_bars[index] *= SPECTRUM_SHADER_INPUT_SCALE
        resolved_peaks[index] *= SPECTRUM_SHADER_INPUT_SCALE

    resolved_bars.extend([0.0] * (_MAX_BARS - len(resolved_bars)))
    resolved_peaks.extend([0.0] * (_MAX_BARS - len(resolved_peaks)))
    return resolved_bars, resolved_peaks


def item_from_fragment(
    matrix_values: Sequence[float],
    viewport: Sequence[float],
    item_size: Sequence[float],
    content_rotation_quarters: int,
    resolution: Sequence[float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """The affine map from window pixels (``gl_FragCoord.xy``) to the item-local logical coordinates the quad's
    interpolated ``v_uv * u_resolution`` stands for, as two rows (x, y) of a 2 x 3 matrix; None when the item's
    matrix is not affine (a 3D transform) or degenerate.

    It inverts exactly what the rasteriser does (viewport, the item matrix, the quad's ``aPosition * uItemSize``, the
    content rotation of ``logicalUvFromPhysicalUv``), so every fragment of the full-field quad gets its coordinate from
    one continuous function: the quad's two triangles, which each interpolate ``v_uv`` with their own rounding, no
    longer disagree about which side of a bar edge lying on a pixel centre a column falls (1B.10's diagonal seam)."""
    m = [float(value) for value in matrix_values]
    # Column-major: m[col * 4 + row]. The w row must be (0, 0, *, 1) for the item plane (z = 0).
    if abs(m[3]) > 1e-12 or abs(m[7]) > 1e-12 or abs(m[15] - 1.0) > 1e-12:
        return None
    a00, a01, a10, a11 = m[0], m[4], m[1], m[5]
    det = a00 * a11 - a01 * a10
    vx, vy, vw, vh = (float(value) for value in viewport)
    width, height = (float(value) for value in item_size)
    if abs(det) < 1e-18 or vw <= 0.0 or vh <= 0.0 or width <= 0.0 or height <= 0.0:
        return None
    i00, i01, i10, i11 = a11 / det, -a01 / det, -a10 / det, a00 / det
    # ndc = (2 / vw, 2 / vh) * window + (-2 vx / vw - 1, -2 vy / vh - 1); position = A^-1 (ndc - translation).
    ox, oy = -2.0 * vx / vw - 1.0 - m[12], -2.0 * vy / vh - 1.0 - m[13]
    sx, sy = 2.0 / vw, 2.0 / vh
    ux = (i00 * sx / width, i01 * sy / width, (i00 * ox + i01 * oy) / width)      # physical uv (aPosition)
    uy = (i10 * sx / height, i11 * sy / height, (i10 * ox + i11 * oy) / height)

    def one_minus(row):
        return (-row[0], -row[1], 1.0 - row[2])
    quarters = int(content_rotation_quarters) & 3
    lx, ly = {0: (ux, uy), 1: (uy, one_minus(ux)), 2: (one_minus(ux), one_minus(uy)), 3: (one_minus(uy), ux)}[quarters]
    rx, ry = (float(value) for value in resolution)
    return (tuple(rx * value for value in lx), tuple(ry * value for value in ly))


@dataclass(frozen=True, slots=True)
class QuickSpectrumLayout:
    content_rect: tuple[float, float, float, float]
    bars_left: float
    bar_width: float
    bar_gap: float
    bar_span: float
    segment_count: int
    height_scale: float


def compute_quick_spectrum_layout(
    *,
    local_content_rect: Sequence[object],
    viewport_extent: Sequence[object],
    visual_scale: float,
    bar_count: int,
    bar_gap: float = DEFAULT_BAR_GAP,
) -> QuickSpectrumLayout:
    """``bar_gap``: the authored space between bars (``spectrum_bar_gap``, px at scale 1, 0 to ``MAX_BAR_GAP``);
    the bars always fill the same span, so a narrower gap widens them and 0 joins them into one field."""
    if len(local_content_rect) != 4 or len(viewport_extent) != 2:
        raise ValueError("Spectrum layout geometry is incomplete")
    content_x, content_y, content_width, content_height = (
        float(value) for value in local_content_rect
    )
    extent_height = float(viewport_extent[1])
    scale = float(visual_scale)
    count = int(bar_count)
    if min(content_width, content_height, extent_height, scale) <= 0.0:
        raise ValueError("Spectrum layout geometry must be positive")
    if count <= 0 or count > _MAX_BARS:
        raise ValueError("Spectrum bar count must be in [1, 64]")

    margin = 8.0 * scale
    left_inset = 1.0 * scale
    right_inset = 3.0 * scale
    gap = max(0.0, min(MAX_BAR_GAP, float(bar_gap))) * scale
    bar_region_width = (
        content_width - (2.0 * margin) - left_inset - right_inset
    )
    total_gap = gap * max(0, count - 1)
    usable_width = bar_region_width - total_gap
    if usable_width <= 0.0:
        raise ValueError("Spectrum viewport is too narrow for its bars")
    bar_width = usable_width / count
    span = (bar_width * count) + total_gap
    inner_height = max(0.0, extent_height - 12.0)
    segments = max(8, min(64, int(inner_height // 5.0)))
    return QuickSpectrumLayout(
        content_rect=(content_x, content_y, content_width, content_height),
        bars_left=content_x + margin + left_inset,
        bar_width=bar_width,
        bar_gap=gap,
        bar_span=span,
        segment_count=segments,
        height_scale=compute_spectrum_height_scale(extent_height),
    )


class QuickSpectrumRenderer:
    mode_id = "spectrum"

    def __init__(self) -> None:
        self._program = 0
        # The block's values as the program's uniforms held them: zero at link, kept between frames (N1.6).
        self._values: dict[str, object] = {}
        self._blocks = PassBlocks("Quick Spectrum", block_bytes=SPECTRUM_BLOCK.size if SPECTRUM_BLOCK else 256)
        self._last_content_rotation_quarters: int | None = None
        self._last_placement: tuple | None = None
        self._last_decor: tuple | None = None
        self._last_decor_inputs: tuple | None = None
        self._last_decor_parameters: object | None = None
        self._last_decor_scale: float | None = None

    @property
    def has_resources(self) -> bool:
        return bool(self._program) or self._blocks.has_resources

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        logical = snapshot.logical
        mode_state = logical.mode_state
        if not isinstance(mode_state, SpectrumFrame):
            raise TypeError("Spectrum renderer received another mode frame")
        count = min(_MAX_BARS, int(logical.common.bar_count))
        if count <= 0:
            return
        presentation = snapshot.presentation
        logical_bars, logical_peaks = logical.common.bars, mode_state.peaks
        if presentation.expanded_display:
            # The display-wide card may draw more bars than the engine computes (one rule, its own module).
            drawn = resolve_display_bar_count(
                "spectrum", count, expanded=True,
                content_rotation_quarters=presentation.content_rotation_quarters,
            )
            if drawn != count:
                levels = list(logical_bars[:count]) + [0.0] * max(0, count - len(logical_bars))
                peak_levels = list(logical_peaks[:count])
                peak_levels += levels[len(peak_levels):count]
                logical_bars = resample_levels(levels, drawn)
                logical_peaks = resample_levels(peak_levels, drawn)
                count = drawn
        bars, peaks = prepare_spectrum_shader_levels(
            logical_bars,
            logical_peaks,
            bar_count=count,
        )

        # Style and per-frame parameters are read only through the frame-input declaration (``spectrum_frame_inputs``).
        style = read_style(logical.common.style)
        local_content_rect = frame.logical_content_rect
        layout = compute_quick_spectrum_layout(
            local_content_rect=local_content_rect,
            viewport_extent=presentation.logical_viewport_extent,
            visual_scale=presentation.uniform_visual_scale,
            bar_count=count,
            bar_gap=style["bar_gap"],
        )
        if not self._program:
            self._initialize()

        parameters = mode_state.parameters
        inputs = _read_per_frame_parameters(parameters)
        fill = rgba(
            style["fill_color"],
        )
        border = rgba(
            style["border_color"],
        )
        glow_color = rgba(
            inputs["spectrum_glow_color"],
        )
        rainbow_enabled = bool(
            inputs["rainbow_enabled"]
        )
        rainbow_per_bar = bool(
            inputs["rainbow_per_bar"]
        )
        rainbow_speed = max(
            0.01,
            min(5.0, float(inputs["rainbow_speed"])),
        )
        if rainbow_enabled:
            hue = safe_hue(
                mode_state.animation_time * rainbow_speed * 0.1
            )
        elif rainbow_per_bar:
            hue = safe_hue(mode_state.animation_time * 0.05)
        else:
            hue = 0.0

        # The program's values persist between frames as its uniforms did: a value is written when it changes
        # (or every frame, as before) and the whole block is bound for the draw (N1.6).
        values = self._values
        gl.glUseProgram(self._program)
        values["uMatrix"] = frame.matrix_values
        values["uItemSize"] = tuple(frame.logical_size)
        content_rotation_quarters = frame.content_rotation_quarters
        if content_rotation_quarters != self._last_content_rotation_quarters:
            values["uContentRotationQuarters"] = content_rotation_quarters
            self._last_content_rotation_quarters = content_rotation_quarters
        values["u_resolution"] = tuple(frame.oriented_logical_size)
        values["u_dpr"] = presentation.dpr
        values["u_viewport_origin_px"] = (0.0, 0.0)
        values["u_quick_item_coords"] = 1
        # Coverage from one continuous coordinate (gl_FragCoord through the item's own affine map), resolved only when
        # the item's placement changes.
        placement = (frame.matrix_values, frame.viewport, frame.logical_size, content_rotation_quarters)
        if placement != self._last_placement:
            mapping = item_from_fragment(frame.matrix_values, frame.viewport, frame.logical_size,
                                         content_rotation_quarters, frame.oriented_logical_size)
            values["u_item_from_frag"] = 0 if mapping is None else 1
            if mapping is not None:
                values["u_item_from_frag_x"] = mapping[0]
                values["u_item_from_frag_y"] = mapping[1]
            self._last_placement = placement
        values["u_content_rect"] = tuple(layout.content_rect)
        values["u_visual_scale"] = presentation.uniform_visual_scale
        values["u_bar_count"] = count
        values["u_segments"] = layout.segment_count
        values["u_bars"] = bars
        values["u_peaks"] = peaks
        values["u_fill_color"] = tuple(fill)
        values["u_border_color"] = tuple(border)
        values["u_fade"] = presentation.content_fade
        values["u_bar_height_scale"] = layout.height_scale
        values["u_single_piece"] = 1 if bool(style["single_piece"]) else 0
        values["u_border_radius"] = max(0.0, float(style["border_radius"])) * presentation.uniform_visual_scale
        ghost_enabled = bool(
            inputs["spectrum_ghosting_enabled"]
        )
        ghost_alpha = float(
            inputs["spectrum_ghost_alpha"]
        )
        values["u_ghost_alpha"] = max(0.0, min(1.0, ghost_alpha)) if ghost_enabled else 0.0
        values["u_spectrum_glow_enabled"] = 1 if bool(inputs["spectrum_glow_enabled"]) else 0
        values["u_spectrum_glow_intensity"] = max(
            0.0, min(1.5, float(inputs["spectrum_glow_intensity"])))
        values["u_spectrum_glow_color"] = tuple(glow_color)
        values["u_rainbow_hue_offset"] = hue
        values["u_rainbow_ghost"] = 1 if bool(inputs["spectrum_rainbow_ghost"]) else 0
        values["u_ghost_hue_offset"] = safe_hue(mode_state.animation_time * rainbow_speed * 0.1)
        values["u_rainbow_per_bar"] = 1 if rainbow_per_bar else 0
        values["u_rainbow_fill"] = 1 if bool(inputs["spectrum_rainbow_fill"]) else 0
        values["u_rainbow_border"] = 1 if bool(inputs["spectrum_rainbow_border"]) else 0
        if inputs["spectrum_pattern_shown"] in SPECTRUM_FLAG_PATTERNS:
            # Only a flag sheet's wave reads the clock (wrapped so a long session keeps float precision).
            values["u_time"] = float(mode_state.animation_time) % 3600.0
        values["u_bars_left"] = layout.bars_left
        values["u_bar_width_px"] = layout.bar_width
        values["u_bar_gap_px"] = layout.bar_gap
        values["u_bar_span_px"] = layout.bar_span
        # Optional decoration: program state persists, so resolve and upload only when its inputs change. Each tick
        # carries a fresh but equal parameter mapping at rest: comparing it whole is one call (the frozen mapping's
        # entries compare in C); only when something changed are the decoration inputs fetched (one C call, though
        # each key is a Python lookup) and compared, so an unrelated change does not resolve. A missing key falls
        # through to the resolver, which names it.
        visual_scale = presentation.uniform_visual_scale
        if parameters == self._last_decor_parameters and visual_scale == self._last_decor_scale:
            inputs = self._last_decor_inputs
        else:
            try:
                inputs = (_decor_sources(parameters), visual_scale)
            except KeyError:
                inputs = None
            self._last_decor_parameters = parameters if inputs is not None else None
            self._last_decor_scale = visual_scale
        if inputs is None or inputs != self._last_decor_inputs:
            decor = resolve_spectrum_decor_uniforms(
                parameters, presentation.uniform_visual_scale,
            )
            if decor != self._last_decor:
                for name, _kind, decor_values in decor:
                    values[name] = decor_values if len(decor_values) > 1 else decor_values[0]
                self._last_decor = decor
            self._last_decor_inputs = inputs
        values["u_playing"] = 1 if logical.playing else 0
        with self._blocks.bound(pack_block(SPECTRUM_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program and not self._blocks.has_resources:
            return
        if self._program:
            delete_program(self._program)
        self._program = 0
        self._blocks.release()
        self._last_content_rotation_quarters = None
        self._last_placement = None
        self._last_decor = None
        self._last_decor_inputs = None
        self._last_decor_parameters = None
        self._last_decor_scale = None
        self._values = {}    # a new program's values start at zero, as its uniforms did

    def _initialize(self) -> None:
        fragment_source = load_fragment_shader("spectrum")
        if fragment_source is None or SPECTRUM_VERTEX_SOURCE is None:
            raise RuntimeError("canonical Spectrum shader is unavailable")
        written = ("uMatrix", "uItemSize", "uContentRotationQuarters", "u_resolution", "u_dpr",
                   "u_viewport_origin_px", "u_quick_item_coords", "u_item_from_frag", "u_item_from_frag_x",
                   "u_item_from_frag_y", "u_content_rect", "u_visual_scale", "u_bar_count", "u_segments", "u_bars",
                   "u_peaks", "u_fill_color", "u_border_color", "u_fade", "u_ghost_alpha", "u_bar_height_scale",
                   "u_single_piece", "u_border_radius", "u_spectrum_glow_enabled", "u_spectrum_glow_intensity",
                   "u_spectrum_glow_color", "u_rainbow_hue_offset", "u_rainbow_ghost", "u_ghost_hue_offset",
                   "u_rainbow_per_bar", "u_rainbow_fill", "u_rainbow_border", "u_bars_left", "u_bar_width_px",
                   "u_bar_gap_px", "u_bar_span_px", *_DECOR_UNIFORMS, "u_playing", "u_time")
        held = {name for name, _kind in SPECTRUM_BLOCK.fields}
        missing = [name for name in written if name not in held]
        if missing:
            raise RuntimeError("Quick Spectrum's block is incomplete: " + ", ".join(missing))
        self._program = compile_program(SPECTRUM_VERTEX_SOURCE, fragment_source, label="Quick Spectrum")
        self._values = {}
        # The block's ring, allocated with the program (the first frame compiles it anyway).
        self._blocks.warm()


def create_visualizer_renderer() -> QuickSpectrumRenderer:
    return QuickSpectrumRenderer()


__all__ = [
    "item_from_fragment",
    "resolve_spectrum_decor_uniforms",
    "QuickSpectrumLayout",
    "QuickSpectrumRenderer",
    "compute_quick_spectrum_layout",
    "create_visualizer_renderer",
]

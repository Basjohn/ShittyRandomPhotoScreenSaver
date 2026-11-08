"""Spectrum's optional decoration: ghost colour and gradient, fill gradient, gloss, peak caps and the bar pattern.

Inputs are synthetic or the code-owned canonical defaults, never a curated preset (presets are authored, mutable
content). The renders go through the production ``QuickVisualizerRenderHost`` -> ``QuickSpectrumRenderer`` into an
offscreen FBO (no window): each option, switched on, changes only the pixels it owns (with a negative control), and
every option off draws exactly what the decoration-free renderer draws whatever its colours and sizes hold. The fade
envelopes advance only on the capture timestamp.
"""
from __future__ import annotations

import dataclasses
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.gl_programs.spectrum_options import SPECTRUM_PATTERN_ANCHORS, SPECTRUM_PATTERNS
from tests._visualizer_presentation import resolve_presentation
from widgets.spotify_visualizer.spectrum_decor import DECOR_KEYS, FADE_SECONDS, SpectrumDecorFade

WIDTH, HEIGHT = 840, 280
FILL = (0, 0, 255, 255)
BORDER = (255, 0, 0, 255)
COUNT = 12
BARS = tuple(0.25 + 0.04 * i for i in range(COUNT))
PEAKS = tuple(min(1.0, b + 0.25) for b in BARS)

# Distinct test colours for every option (never preset values).
ON = {
    "pattern": {"spectrum_pattern": "Dots", "spectrum_pattern_color": [0, 255, 0, 255],
                "spectrum_pattern_strength": 1.0},
    "ghost_custom": {"spectrum_ghost_color_source": "Custom", "spectrum_ghost_color": [0, 255, 0, 255]},
    "ghost_fill": {"spectrum_ghost_color_source": "Bar Fill"},
    "ghost_gradient": {"spectrum_ghost_gradient": True, "spectrum_ghost_tip_color": [0, 255, 0, 255]},
    "fill_gradient": {"spectrum_fill_gradient": True, "spectrum_fill_tip_color": [0, 255, 0, 255]},
    "gloss": {"spectrum_gloss": 1.0},
    "peak_caps": {"spectrum_peak_caps": True, "spectrum_peak_cap_color": [0, 255, 0, 255]},
}


# ------------------------------------------------------------------------------------------- fades
class Owner(SimpleNamespace):
    pass


def _owner(**values) -> Owner:
    from core.settings.default_contract import require_canonical_default
    owner = Owner(**{"_" + key: require_canonical_default(f"widgets.spotify_visualizer.{key}") for key in DECOR_KEYS})
    for key, value in values.items():
        setattr(owner, "_" + key, value)
    return owner


def test_a_fresh_owner_starts_settled_at_its_settings():
    off = SpectrumDecorFade(_owner()).mixes()
    assert {k: v for k, v in off.items() if k.endswith("_mix")} == dict.fromkeys(
        [k for k in off if k.endswith("_mix")], 0.0)
    on = SpectrumDecorFade(_owner(spectrum_peak_caps=True, spectrum_pattern=SPECTRUM_PATTERNS[2])).mixes()
    assert on["spectrum_peak_caps_mix"] == 1.0 and on["spectrum_pattern_mix"] == 1.0
    assert on["spectrum_pattern_shown"] == SPECTRUM_PATTERNS[2]


def test_a_toggle_fades_on_the_capture_clock_and_settles():
    owner = _owner()
    fade = SpectrumDecorFade(owner)
    assert fade.advance(owner, 10.0) is False
    owner._spectrum_peak_caps = True
    levels, moving = [], []
    t = 10.0
    while t < 10.0 + FADE_SECONDS + 0.2:
        t += 1.0 / 60.0
        moving.append(fade.advance(owner, t))
        levels.append(fade.mixes()["spectrum_peak_caps_mix"])
    assert levels == sorted(levels) and 0.0 < levels[0] < 0.05 and levels[-1] == 1.0
    assert any(0.4 < v < 0.6 for v in levels)                       # a real ramp, not a cut
    assert moving[0] and not moving[-1]
    # The capture timestamp is the only clock: no time passing, no progress.
    owner._spectrum_peak_caps = False
    before = fade.mixes()["spectrum_peak_caps_mix"]
    fade.advance(owner, t)
    assert fade.mixes()["spectrum_peak_caps_mix"] == before == 1.0


def test_a_pattern_change_dips_through_zero_and_off_fades_the_old_pattern_out():
    owner = _owner(spectrum_pattern=SPECTRUM_PATTERNS[1])
    fade = SpectrumDecorFade(owner)
    fade.advance(owner, 0.0)
    owner._spectrum_pattern = SPECTRUM_PATTERNS[3]
    seen, t = [], 0.0
    for _ in range(200):
        t += 1.0 / 60.0
        fade.advance(owner, t)
        mixes = fade.mixes()
        seen.append((mixes["spectrum_pattern_shown"], mixes["spectrum_pattern_mix"]))
    shown = [s for s, _m in seen]
    switch = shown.index(SPECTRUM_PATTERNS[3])
    assert set(shown[:switch]) == {SPECTRUM_PATTERNS[1]}
    assert [m for _s, m in seen[:switch]] == sorted((m for _s, m in seen[:switch]), reverse=True)
    assert seen[switch][1] < 0.05 and seen[-1] == (SPECTRUM_PATTERNS[3], 1.0)
    owner._spectrum_pattern = SPECTRUM_PATTERNS[0]
    fade.advance(owner, t + 0.2)
    assert fade.mixes()["spectrum_pattern_shown"] == SPECTRUM_PATTERNS[3]     # the old pattern fades out
    assert 0.0 < fade.mixes()["spectrum_pattern_mix"] < 1.0
    fade.advance(owner, t + 0.3)
    fade.advance(owner, t + 0.4)
    fade.advance(owner, t + 0.5)
    fade.advance(owner, t + 0.6)
    fade.advance(owner, t + 0.7)
    assert fade.mixes()["spectrum_pattern_mix"] == 0.0


def test_the_production_capture_carries_every_decoration_parameter(qt_app):
    """Spectrum's own capture (production offline replay) publishes the decoration controls and fade levels."""
    from ui.studio.spectrum_recorded_inputs import extract
    from core.settings.default_contract import require_canonical_default
    values = dict(require_canonical_default("widgets.spotify_visualizer"), spectrum_pattern=SPECTRUM_PATTERNS[4])
    captured: list = []
    extract("synthetic:mid", values, seconds=0.3, frames_out=captured)
    parameters = captured[-1][1].mode_state.parameters
    assert set(DECOR_KEYS) <= set(parameters)
    assert parameters["spectrum_pattern_shown"] == SPECTRUM_PATTERNS[4] and parameters["spectrum_pattern_mix"] == 1.0
    assert parameters["spectrum_peak_caps_mix"] == 0.0


# ------------------------------------------------------------------------------------------- renders
@pytest.fixture(scope="module")
def render(qt_app):
    """Draw a synthetic Spectrum frame with the given settings through the production render host."""
    import numpy as np
    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat
    from core.settings.models import SpotifyVisualizerSettings
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from widgets.spotify_visualizer.config_applier import (
        _populate_shared_visualizer_extras, apply_presentation_vis_mode_kwargs,
    )
    from widgets.spotify_visualizer.render_state import (
        SpectrumFrame, VisualizerCommonState, VisualizerLogicalFrame, compose_visualizer_render_snapshot,
        freeze_render_fields,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.spectrum_decor import spectrum_decor_parameters

    disable_per_call_gl_error_checking()
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 6)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.6 context unavailable")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        surface.destroy()
        pytest.skip("offscreen OpenGL context unavailable")
    color = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, color)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, WIDTH, HEIGHT, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
    fbo = gl.glGenFramebuffers(1)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
    host = QuickVisualizerRenderHost()
    presentation = resolve_presentation(policy=get_visualizer_presentation_policy("spectrum"),
                                        display_size=(float(WIDTH), float(HEIGHT)),
                                        viewport_extent=(float(WIDTH), float(HEIGHT)))

    def parameters(settings: dict, *, ghosting: bool) -> dict:
        model = SpotifyVisualizerSettings.from_mapping(settings, apply_preset_overlay=False)
        controller = VisualizerRuntimeController(runtime_generation=2, initial_mode="spectrum")
        apply_presentation_vis_mode_kwargs(controller.presentation_state, asdict(model))
        host_state = SimpleNamespace(presentation_config_host=controller.presentation_state,
                                     _spectrum_ghosting_enabled=ghosting, _spectrum_ghost_decay=0.18,
                                     _osc_ghosting_enabled=False, _osc_ghost_intensity=0.0, _osc_ghost_decay=0.5)
        out: dict = {}
        _populate_shared_visualizer_extras(out, host_state)
        out.update(spectrum_decor_parameters(controller.presentation_state))
        return out

    def draw(overrides: dict | None = None, *, ghosting: bool = True, solid: bool = True, bars=BARS, peaks=PEAKS,
             raw_parameters: dict | None = None, border=BORDER, radius: float = 0.0):
        settings = {"spectrum_rainbow_enabled": False, "spectrum_unique_colors": False,
                    "spectrum_rainbow_ghost": False, "spectrum_glow_enabled": False,
                    "spectrum_ghost_alpha": 0.9, "spectrum_border_radius": 0.0, **(overrides or {})}
        params = parameters(settings, ghosting=ghosting)
        params.update(raw_parameters or {})
        logical = VisualizerLogicalFrame(
            runtime_generation=2, engine_generation=5, activation_id=7, source_generation=5,
            source_activation_id=7, mode_id="spectrum", playing=True, logical_timestamp=1.0,
            source_timestamp=1.0, changed=True, present_frame=True, mode_reveal_ready=True,
            common=VisualizerCommonState(bars=tuple(bars), bar_count=len(bars), style=freeze_render_fields({
                "fill_color": FILL, "border_color": border, "single_piece": solid, "border_radius": radius})),
            mode_state=SpectrumFrame(peaks=tuple(peaks), ghost_bars=tuple(peaks),
                                     parameters=freeze_render_fields(params)))
        snapshot = compose_visualizer_render_snapshot(logical, presentation, logical_revision=1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, WIDTH, HEIGHT)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        matrix = (2 / WIDTH, 0, 0, 0, 0, 2 / HEIGHT, 0, 0, 0, 0, 1, 0, -1, -1, 0, 1)
        assert host.render(snapshot=snapshot, viewport=(0, 0, WIDTH, HEIGHT),
                           logical_size=(float(WIDTH), float(HEIGHT)), matrix_values=matrix) == "spectrum"
        raw = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.frombuffer(bytes(raw), dtype=np.uint8).reshape(HEIGHT, WIDTH, 4).astype(int)

    yield draw
    host.release_resources()
    gl.glDeleteFramebuffers(1, [fbo])
    gl.glDeleteTextures([color])
    context.doneCurrent()
    surface.destroy()


def _changed(a, b):
    import numpy as np
    return np.abs(a - b).max(axis=2) > 0


def _is(pixels, colour):
    import numpy as np
    return (pixels == np.array(colour)).all(axis=2)


@pytest.mark.qt
@pytest.mark.parametrize("solid", (True, False), ids=("bars", "segments"))
def test_options_off_draw_the_same_pixels_whatever_their_colours_and_sizes_hold(render, solid):
    """Every option off (canonical defaults) versus off with wild colours, scales and strengths: identical, so
    nothing an inactive option holds reaches the screen."""
    import numpy as np
    from core.settings.visualizer_mode_settings import Colour, Slider, require_mode_settings
    spec = require_mode_settings("spectrum")
    wild = {}
    for key in DECOR_KEYS:
        control = spec.control(key)
        if isinstance(control, Colour):
            wild[key] = [11, 222, 33, 200]
        elif isinstance(control, Slider) and key != "spectrum_gloss":
            wild[key] = control.high
    wild["spectrum_pattern_anchor"] = SPECTRUM_PATTERN_ANCHORS[-1]
    base = render(solid=solid)
    assert (base[..., 3] > 0).sum() > 1000
    assert np.array_equal(base, render(wild, solid=solid))


@pytest.mark.qt
@pytest.mark.parametrize("solid", (True, False), ids=("bars", "segments"))
@pytest.mark.parametrize("option", ("pattern", "fill_gradient", "gloss"))
def test_fill_options_change_only_fill_pixels(render, option, solid):
    import numpy as np
    off = render(solid=solid)
    on = render(ON[option], solid=solid)
    changed = _changed(off, on)
    fill = _is(off, FILL)
    assert changed.sum() > 200, option
    assert not (changed & ~fill).any(), option                # borders, ghosts and background untouched
    # Negative control: the same option with no bar body to draw over (silent solid bars) changes nothing.
    empty = dict(bars=(0.0,) * COUNT, peaks=(0.0,) * COUNT, ghosting=False, solid=True)
    assert np.array_equal(render(**empty), render(ON[option], **empty))


@pytest.mark.qt
@pytest.mark.parametrize("solid", (True, False), ids=("bars", "segments"))
@pytest.mark.parametrize("option", ("ghost_custom", "ghost_gradient", "ghost_fill"))
def test_ghost_options_change_only_ghost_pixels(render, option, solid):
    import numpy as np
    off = render(solid=solid)
    ghost = _changed(off, render(ghosting=False, solid=solid))
    changed = _changed(off, render(ON[option], solid=solid))
    assert changed.sum() > 100 and not (changed & ~ghost).any(), option
    # Negative controls: no ghosts, no effect; Rainbow Ghost on overrides a custom colour.
    assert np.array_equal(render(ghosting=False, solid=solid), render(ON[option], ghosting=False, solid=solid))
    if option in ("ghost_custom", "ghost_fill"):
        rainbow = {"spectrum_rainbow_ghost": True}
        assert np.array_equal(render(rainbow, solid=solid), render({**rainbow, **ON[option]}, solid=solid))


@pytest.mark.qt
@pytest.mark.parametrize("solid", (True, False), ids=("bars", "segments"))
def test_peak_caps_draw_only_above_each_bar_and_its_ghost(render, solid):
    import numpy as np
    off = render(solid=solid)
    on = render(ON["peak_caps"], solid=solid)
    changed = _changed(off, on)
    assert not (changed & (off[..., 3] > 0)).any()            # only on empty pixels above the bar and ghost
    assert (on[changed][:, 1] > 0).all()                      # in the cap colour
    rows, cols = np.nonzero(changed)
    for column in np.unique(cols):
        drawn = rows[cols == column]
        covered = np.nonzero(off[:, column, 3] > 0)[0]
        if covered.size:
            # The cap rests just above the column's top (bar or ghost), not anywhere else.
            assert drawn.max() < covered.min() and covered.min() - drawn.max() <= 8
    # One cap per bar: the changed columns form COUNT runs.
    runs = np.count_nonzero(np.diff(np.unique(cols)) > 1) + 1
    assert runs == COUNT


@pytest.mark.qt
def test_the_pattern_is_fixed_in_place_while_the_bars_move(render):
    """No shimmer: where a bar's body covers the same pixel in two frames of different heights, the pattern colours
    it identically (patterns are anchored to the baseline and the bar, not to the bar's moving top)."""
    import numpy as np
    for pattern, anchor in ((p, a) for p in SPECTRUM_PATTERNS[1:] for a in SPECTRUM_PATTERN_ANCHORS):
        settings = dict(ON["pattern"], spectrum_pattern=pattern, spectrum_pattern_anchor=anchor)
        low = render(settings, bars=tuple(b * 0.8 for b in BARS), ghosting=False)
        high = render(settings, bars=BARS, ghosting=False)
        body_low = _is(render(bars=tuple(b * 0.8 for b in BARS), ghosting=False), FILL)
        body_high = _is(render(bars=BARS, ghosting=False), FILL)
        both = body_low & body_high
        assert both.sum() > 1000
        assert np.array_equal(low[both], high[both]), (pattern, anchor)


def _sheet_mismatch(render, pattern: str, anchor: str) -> tuple[int, int]:
    """(differing, compared) pattern pixels between two bar layouts (12 and 7 bars: other widths and positions) over
    the fill pixels both layouts cover."""
    import numpy as np
    other = tuple(0.3 + 0.08 * i for i in range(7))
    settings = dict(ON["pattern"], spectrum_pattern=pattern, spectrum_pattern_anchor=anchor)
    many = render(settings, ghosting=False)
    few = render(settings, bars=other, peaks=other, ghosting=False)
    both = _is(render(ghosting=False), FILL) & _is(render(bars=other, peaks=other, ghosting=False), FILL)
    return int(np.abs(many[both] - few[both]).max(axis=1).astype(bool).sum()), int(both.sum())


@pytest.mark.qt
@pytest.mark.parametrize("pattern", ("Dots", "Diagonal Stripes", "Grid", "Chevrons"))
def test_a_shared_pattern_is_one_sheet_over_the_field_whatever_the_bars(render, pattern):
    """Shared: the pattern belongs to the bar field, so two layouts with different bar counts (different widths and
    positions) show the identical sheet wherever both have fill. Negative control: Per Bar fits the pattern to each
    bar, so the same comparison differs (Diagonal Stripes already run across the field in both)."""
    differing, compared = _sheet_mismatch(render, pattern, SPECTRUM_PATTERN_ANCHORS[1])
    assert compared > 2000 and differing == 0, pattern
    if pattern != "Diagonal Stripes":
        assert _sheet_mismatch(render, pattern, SPECTRUM_PATTERN_ANCHORS[0])[0] > 200, pattern


@pytest.mark.qt
def test_the_anchor_changes_only_patterns_with_a_horizontal_frame(render):
    """Shared re-frames a pattern horizontally; bands and scanlines have none, so the anchor leaves them unchanged
    (negative control), while chevrons change; only fill pixels are touched."""
    import numpy as np
    def both(pattern):
        return [render(dict(ON["pattern"], spectrum_pattern=pattern, spectrum_pattern_anchor=a))
                for a in SPECTRUM_PATTERN_ANCHORS]
    for pattern in ("Horizontal Bands", "Scanlines"):
        per_bar, shared = both(pattern)
        assert np.array_equal(per_bar, shared), pattern
    per_bar, shared = both("Chevrons")
    changed = _changed(per_bar, shared)
    assert changed.sum() > 200 and not (changed & ~_is(render(), FILL)).any()


def test_an_anchor_change_dips_the_pattern_through_zero():
    owner = _owner(spectrum_pattern=SPECTRUM_PATTERNS[6])
    fade = SpectrumDecorFade(owner)
    fade.advance(owner, 0.0)
    owner._spectrum_pattern_anchor = SPECTRUM_PATTERN_ANCHORS[1]
    fade.advance(owner, 0.2)
    mixes = fade.mixes()
    assert mixes["spectrum_pattern_anchor_shown"] == SPECTRUM_PATTERN_ANCHORS[0] and 0.0 < mixes[
        "spectrum_pattern_mix"] < 1.0
    t = 0.2
    for _ in range(30):
        t += 0.05
        fade.advance(owner, t)
    assert fade.mixes()["spectrum_pattern_anchor_shown"] == SPECTRUM_PATTERN_ANCHORS[1]
    assert fade.mixes()["spectrum_pattern_mix"] == 1.0


@pytest.mark.qt
def test_every_pattern_draws_its_own_figure_and_off_draws_none(render):
    import numpy as np
    images = {p: render(dict(ON["pattern"], spectrum_pattern=p)) for p in SPECTRUM_PATTERNS}
    off = images[SPECTRUM_PATTERNS[0]]
    assert np.array_equal(off, render())
    figures = [images[p] for p in SPECTRUM_PATTERNS[1:]]
    for index, image in enumerate(figures):
        assert _changed(off, image).sum() > 200
        for other in figures[index + 1:]:
            assert _changed(image, other).sum() > 200


@pytest.mark.qt
def test_a_half_faded_option_lies_between_off_and_on(render):
    """The fade envelope reaches the shader: half way, every pixel sits between its off and on colours."""
    import numpy as np
    off = render()
    on = render(ON["pattern"])
    half = render(ON["pattern"], raw_parameters={"spectrum_pattern_mix": 0.5})
    low, high = np.minimum(off, on), np.maximum(off, on)
    assert ((half >= low - 1) & (half <= high + 1)).all()
    share = np.abs(half - off).sum() / np.abs(on - off).sum()
    assert 0.3 < share < 0.7


# ------------------------------------------------------------------------------------- flags, gradient, rim (7 Nov)
FULL = (1.0,) * COUNT
NARROW = tuple(0.8 for _ in range(37))          # 37 bars across the card: each only a few pixels wide


def _body_box(render, bars):
    """Rows/columns spanned by the bar bodies (fill pixels) of ``bars`` with no decoration."""
    import numpy as np
    body = _is(render(bars=bars, peaks=bars, ghosting=False), FILL)
    rows, cols = np.nonzero(body)
    return body, rows.min(), rows.max(), cols.min(), cols.max()


@pytest.mark.qt
def test_a_flag_sheet_paints_its_flag_across_the_field_and_only_the_fills(render):
    """Each flag draws its own picture over the whole field, only in fill pixels, and Strength 0 draws nothing
    (negative control). Japan: the crimson disc sits at the field's centre on white."""
    import numpy as np
    from rendering.gl_programs.spectrum_options import SPECTRUM_FLAG_PATTERNS
    body, r0, r1, c0, c1 = _body_box(render, FULL)
    off = render(bars=FULL, peaks=FULL, ghosting=False)
    images = {}
    for flag in SPECTRUM_FLAG_PATTERNS:
        on = render({"spectrum_pattern": flag, "spectrum_pattern_strength": 1.0}, bars=FULL, peaks=FULL,
                    ghosting=False)
        changed = _changed(off, on)
        assert changed.sum() > 0.5 * body.sum() and not (changed & ~body).any(), flag
        none = render({"spectrum_pattern": flag, "spectrum_pattern_strength": 0.0}, bars=FULL, peaks=FULL,
                      ghosting=False)
        assert np.array_equal(off, none), flag
        images[flag] = on
    for index, flag in enumerate(SPECTRUM_FLAG_PATTERNS):
        for other in SPECTRUM_FLAG_PATTERNS[index + 1:]:
            assert _changed(images[flag], images[other]).sum() > 0.2 * body.sum(), (flag, other)
    japan = images["Japan Flag"]
    rows, cols = np.nonzero(body)
    cy, cx = (r0 + r1) / 2.0, (c0 + c1) / 2.0
    radius = 0.3 * (r1 - r0)                     # three fifths of the height across
    distance = np.hypot(rows - cy, cols - cx)
    inside = japan[rows[distance < 0.7 * radius], cols[distance < 0.7 * radius]]
    outside = japan[rows[distance > 1.3 * radius], cols[distance > 1.3 * radius]]
    assert inside.size and outside.size
    assert (inside[:, 0] > 150).mean() > 0.95 and (inside[:, 1] < 60).mean() > 0.95      # crimson
    assert (outside[:, :3] > 170).all(axis=1).mean() > 0.95                                # white


@pytest.mark.qt
def test_the_fill_gradient_keeps_its_saturation_through_the_middle(render):
    """Blue to green turns through bright cyan, not the dark teal an RGB mix gives (green to red likewise passes
    yellow, not olive). Mid-field body pixels: both green and blue near full (an RGB mix holds them near half)."""
    import numpy as np
    body, r0, r1, _, _ = _body_box(render, FULL)
    on = render(ON["fill_gradient"], bars=FULL, peaks=FULL, ghosting=False)
    rows, cols = np.nonzero(body)
    middle = np.abs(rows - (r0 + 0.47 * (r1 - r0))) < 3
    pixels = on[rows[middle], cols[middle]]
    assert pixels.size
    assert (pixels[:, 1] > 200).mean() > 0.95 and (pixels[:, 2] > 200).mean() > 0.95
    assert (pixels[:, 0] < 40).mean() > 0.95


@pytest.mark.qt
def test_rim_glow_stays_a_rim_on_narrow_bars(render):
    """At the strongest intensity on 37 narrow bars the glow tints each bar's edges, never its middle (it used to
    reach in (3 + 4 x intensity) x scale pixels from each side, recolouring every bar whole)."""
    import numpy as np
    body, r0, r1, _, _ = _body_box(render, NARROW)
    off = render(bars=NARROW, peaks=NARROW, ghosting=False)
    glow = {"spectrum_glow_enabled": True, "spectrum_glow_intensity": 1.5, "spectrum_glow_color": [0, 255, 0, 255]}
    on = render(glow, bars=NARROW, peaks=NARROW, ghosting=False)
    changed = _changed(off, on)
    row = int(r0 + 0.4 * (r1 - r0))              # well below the bar tops
    spans = np.split(np.nonzero(body[row])[0], np.nonzero(np.diff(np.nonzero(body[row])[0]) > 1)[0] + 1)
    assert len(spans) >= 30
    for span in spans:
        middle = span[len(span) // 2]
        assert not changed[row, middle], span    # the middle of every bar keeps its fill
        assert changed[row, span[0]] or changed[row, span[-1]], span   # the edges glow


# ------------------------------------------------------------------------------------------- cost at rest
def test_the_renderer_fetches_every_decoration_input_it_resolves():
    """At rest the renderer compares the raw decoration inputs fetched in one call (``_DECOR_SOURCES``): every
    parameter the resolver reads must be in that fetch, or a change to it would go unseen."""
    from rendering.quick.visualizer.implementations import spectrum as owner

    class Recording(dict):
        def __init__(self):
            super().__init__()
            self.read = set()

        def __getitem__(self, key):
            self.read.add(key)
            if key.endswith("_color"):
                return (10, 20, 30, 255)
            if key == "spectrum_pattern_shown":
                return SPECTRUM_PATTERNS[-1]                # a real pattern, so its mix and strength are read
            if key == "spectrum_pattern_anchor_shown":
                return SPECTRUM_PATTERN_ANCHORS[-1]
            return 0.5

    parameters = Recording()
    owner.resolve_spectrum_decor_uniforms(parameters, 1.0)
    assert parameters.read and parameters.read <= set(owner._DECOR_SOURCES)


@pytest.mark.qt
def test_unchanged_decoration_is_neither_resolved_nor_uploaded_again(render, monkeypatch):
    """The options are default-off: a frame whose decoration inputs did not change costs one fetch and one
    comparison, not a resolve; a changed input is resolved (negative control)."""
    from rendering.quick.visualizer.implementations import spectrum as owner
    calls = []
    real = owner.resolve_spectrum_decor_uniforms

    def counted(parameters, visual_scale):
        calls.append(visual_scale)
        return real(parameters, visual_scale)
    monkeypatch.setattr(owner, "resolve_spectrum_decor_uniforms", counted)
    render()
    first = len(calls)
    render()
    render()
    assert len(calls) == first                              # at rest: no resolve
    render({"spectrum_gloss": 1.0})
    assert len(calls) == first + 1                          # a change is seen


@pytest.mark.qt
def test_an_equal_parameter_mapping_skips_even_the_decoration_fetch(render, monkeypatch):
    """Each tick hands the renderer a fresh, equal parameter mapping; at rest it is compared whole (one call) and
    the per-key decoration fetch is skipped. A change to an unrelated parameter is fetched and compared but not
    resolved; a decoration change is resolved (negative controls)."""
    from rendering.quick.visualizer.implementations import spectrum as owner
    fetches, resolves = [], []
    real_fetch, real_resolve = owner._decor_sources, owner.resolve_spectrum_decor_uniforms

    def fetch(parameters):
        fetches.append(1)
        return real_fetch(parameters)

    def resolve(parameters, visual_scale):
        resolves.append(1)
        return real_resolve(parameters, visual_scale)
    monkeypatch.setattr(owner, "_decor_sources", fetch)
    monkeypatch.setattr(owner, "resolve_spectrum_decor_uniforms", resolve)
    render()
    fetched, resolved = len(fetches), len(resolves)
    render()
    render()
    assert (len(fetches), len(resolves)) == (fetched, resolved)          # at rest: no fetch, no resolve
    render(raw_parameters={"spectrum_unrelated_probe": 1.0})
    assert (len(fetches), len(resolves)) == (fetched + 1, resolved)      # unrelated change: fetched, not resolved
    render({"spectrum_gloss": 1.0}, raw_parameters={"spectrum_unrelated_probe": 1.0})
    assert len(resolves) == resolved + 1                                 # a decoration change is resolved


# ------------------------------------------------------------------------------------- Bar Fill ghosts (8 Nov)
def _unpremultiplied(pixels):
    """The render target holds premultiplied colour: straight RGB of each pixel (0 where nothing is drawn)."""
    import numpy as np
    alpha = pixels[..., 3:4].astype(float)
    return np.where(alpha > 0, pixels[..., :3] * 255.0 / np.maximum(alpha, 1.0), 0.0)


def test_bar_fill_has_its_own_fade_envelope():
    owner = _owner()
    fade = SpectrumDecorFade(owner)
    fade.advance(owner, 0.0)
    owner._spectrum_ghost_color_source = "Bar Fill"
    fade.advance(owner, 0.05)
    assert 0.0 < fade.mixes()["spectrum_ghost_fill_mix"] < 1.0           # fades in, never pops
    t = 0.05
    for _ in range(30):
        t += 0.05
        fade.advance(owner, t)
    assert fade.mixes()["spectrum_ghost_fill_mix"] == 1.0 and fade.mixes()["spectrum_ghost_custom_mix"] == 0.0


@pytest.mark.qt
@pytest.mark.parametrize("solid", (True, False), ids=("bars", "segments"))
def test_a_bar_fill_ghost_is_a_blurred_trail_of_its_own_bar(render, solid):
    """Ghost Colour Bar Fill: wherever a ghost is drawn, its straight colour is the bar's own surface around that
    pixel, blurred: it lies within the colours the same bar shows nearby when it really reaches that height (fill
    gradient and pattern included) and close to their local mean; on the bar's border it is the border colour.
    Negative control: the Bar Colour source paints the border colour over the fill and fails the same comparison."""
    import numpy as np
    look = {"spectrum_fill_gradient": True, "spectrum_fill_tip_color": [0, 255, 0, 255],
            "spectrum_pattern": "Dots", "spectrum_pattern_color": [255, 255, 255, 255],
            "spectrum_pattern_strength": 1.0}
    tall = render(look, bars=PEAKS, peaks=PEAKS, ghosting=False, solid=solid)[..., :3]
    tall_plain = render(bars=PEAKS, peaks=PEAKS, ghosting=False, solid=solid)
    fill = _is(tall_plain, FILL)
    ghost = _changed(render(look, solid=solid), render(look, ghosting=False, solid=solid))
    reach_y, reach_x = HEIGHT // 9, HEIGHT // 18           # past the blur's half extent (0.1 / 0.05 of the field)

    def compare(source):
        drawn = render(dict(look, spectrum_ghost_color_source=source), solid=solid)
        image = _unpremultiplied(drawn)
        readable = ghost & (drawn[..., 3] > 60)
        outside, off_mean = [], []
        rows, cols = np.nonzero(readable & fill)
        for r, c in list(zip(rows, cols))[::7]:
            window = (slice(max(0, r - reach_y), r + reach_y + 1), slice(max(0, c - reach_x), c + reach_x + 1))
            near = tall[window][fill[window]]
            low, high = near.min(axis=0), near.max(axis=0)
            outside.append(np.maximum(low - image[r, c], image[r, c] - high).max())
            off_mean.append(np.abs(image[r, c] - near.mean(axis=0)).max())
        edge = readable & _is(tall_plain, BORDER)
        return (np.array(outside), np.array(off_mean),
                np.abs(image[edge] - np.array(BORDER[:3])).max(axis=1), tall[rows, cols])

    outside, off_mean, edge_error, expected = compare("Bar Fill")
    assert outside.size > 50 and outside.max() <= 6
    assert np.median(off_mean) <= 40
    assert len(np.unique(expected // 48, axis=0)) > 2                   # gradient and dots really vary under it
    assert edge_error.size == 0 or edge_error.max() <= 4
    control, _mean, _edge, _expected = compare("Bar Colour")
    assert (control > 40).mean() > 0.9


@pytest.mark.qt
def test_a_bar_fill_ghost_blurs_its_bars_pattern(render):
    """The operator (8 Nov 2026): Bar Fill ghosts were "too solid and not blurred". Down each ghost column its
    straight colour changes slowly: its high-frequency energy across Horizontal Bands' sharp white/blue boundaries is
    far below the bar's own over the same rows. Negative control: the bar itself at that height (what the old crisp
    ghost copied pixel for pixel) carries the bands' full energy."""
    import numpy as np
    look = {"spectrum_pattern": "Horizontal Bands", "spectrum_pattern_color": [255, 255, 255, 255],
            "spectrum_pattern_strength": 1.0, "spectrum_ghost_color_source": "Bar Fill"}
    tall = render(look, bars=PEAKS, peaks=PEAKS, ghosting=False).astype(float)[..., :3]
    drawn = render(look)
    ghost = _changed(drawn, render(look, ghosting=False)) & (drawn[..., 3] > 30)
    image = _unpremultiplied(drawn)
    fill = _is(render(bars=PEAKS, peaks=PEAKS, ghosting=False), FILL)
    ghost_energy, bar_energy = [], []
    for column in np.unique(np.nonzero(ghost & fill)[1]):
        rows = np.nonzero(ghost[:, column] & fill[:, column])[0]
        if rows.size < 30:
            continue
        rows = rows[3:-3]
        ghost_energy.append(np.abs(np.diff(image[rows, column], axis=0)).sum(axis=1).mean())
        bar_energy.append(np.abs(np.diff(tall[rows, column], axis=0)).sum(axis=1).mean())
    assert len(ghost_energy) > 100
    assert np.mean(bar_energy) > 20                                     # the bands really are sharp in the bar
    assert np.mean(ghost_energy) < 0.25 * np.mean(bar_energy)


@pytest.mark.qt
def test_a_bar_fill_ghost_is_softer_than_a_plain_ghost(render):
    """A Bar Fill ghost is more transparent than a Bar Colour ghost at every pixel and fades out sooner toward its
    top (a light surface reads far brighter than a hue at the same opacity). Negative control: the Bar Colour
    ghost against itself shows no such gap."""
    import numpy as np
    light = {"spectrum_pattern": "Horizontal Bands", "spectrum_pattern_color": [255, 255, 255, 255],
             "spectrum_pattern_strength": 1.0}
    plain = render(dict(light, spectrum_ghost_color_source="Bar Colour"))
    soft = render(dict(light, spectrum_ghost_color_source="Bar Fill"))
    ghost = _changed(plain, render(light, ghosting=False)) & _is(render(bars=PEAKS, peaks=PEAKS, ghosting=False), FILL)
    assert ghost.sum() > 1000
    assert (soft[..., 3][ghost] <= plain[..., 3][ghost] + 1).all()
    rows, cols = np.nonzero(ghost)
    top = np.zeros_like(ghost)
    for column in np.unique(cols):
        column_rows = rows[cols == column]
        top[column_rows[column_rows < np.quantile(column_rows, 0.3)], column] = True
    assert soft[..., 3][top].mean() < 0.6 * plain[..., 3][top].mean()
    again = render(dict(light, spectrum_ghost_color_source="Bar Colour"))
    assert not again[..., 3][top].mean() < 0.6 * plain[..., 3][top].mean()


@pytest.mark.qt
@pytest.mark.parametrize("radius", (0.0, 12.0), ids=("square", "rounded"))
def test_a_bar_fill_ghost_meets_its_bar_without_a_dark_seam(render, radius):
    """Over a bar whose border is transparent (the flag presets), a Bar Fill ghost begins at the bar's fill top: the
    rows where the lit fill meets its ghost are never darker than both of their neighbours, square or rounded (the
    bar's transparent top stroke, and two roundings pinching each other, used to open a 1 px dark seam there).
    Negative control: a Bar Colour ghost over the same bars keeps that seam."""
    import numpy as np
    clear = (255, 0, 0, 0)
    backdrop = np.array([18.0, 18.0, 22.0])

    def seams(source):
        settings = {"spectrum_ghost_color_source": source, "spectrum_border_radius": radius}
        drawn = render(settings, border=clear, radius=radius).astype(float)
        bare = render(settings, border=clear, radius=radius, ghosting=False)
        shown = drawn[..., :3] + backdrop * (1.0 - drawn[..., 3:4] / 255.0)        # premultiplied over the card
        luma = shown.max(axis=2)                                                   # HSV value: blue reads too
        dark = checked = 0
        for column in np.unique(np.nonzero(bare[..., 3] > 0)[1]):
            lit = np.nonzero(bare[:, column, 3] > 0)[0]
            top = lit.min()                                                 # the bar's highest lit row
            if top < 8 or drawn[top - 6, column, 3] == 0:
                continue                                                    # no ghost above this column
            checked += 1
            for row in range(top - 4, top + 2):
                if luma[row, column] < min(luma[row - 1, column], luma[row + 1, column]) - 3:
                    dark += 1
                    break
        return dark, checked

    dark, checked = seams("Bar Fill")
    assert checked > 100 and dark == 0
    control, control_checked = seams("Bar Colour")
    assert control > 0.5 * control_checked


@pytest.mark.qt
def test_nothing_draws_a_line_over_a_fading_ghost_unless_peak_caps_are_on(render):
    """Every ghost fades out toward its top: down each ghost column, from whatever is drawn highest to the ghost's
    lowest row, opacity never falls, so the ghost's top is the faintest thing there (Bar Fill and Bar Colour
    alike). Negative control: Peak Caps draw an opaque line right above that faint top, the hard line the curated
    presets 2-15 showed over their ghosts until 8 Nov."""
    import numpy as np

    def hard_tops(settings):
        image = render(settings)
        ghost = _changed(image, render(settings, ghosting=False))
        columns = np.unique(np.nonzero(ghost)[1])
        hard = 0
        for column in columns:
            bottom = np.nonzero(ghost[:, column])[0].max()
            rows = np.nonzero(image[:bottom + 1, column, 3] > 0)[0]          # top row first
            if rows.size >= 4 and (np.diff(image[rows, column, 3]) < -2).any():
                hard += 1
        return hard, len(columns)

    for source in ("Bar Fill", "Bar Colour"):
        hard, columns = hard_tops({"spectrum_ghost_color_source": source})
        assert columns > 100 and hard == 0, source
    hard, columns = hard_tops(dict(ON["peak_caps"], spectrum_ghost_color_source="Bar Fill"))
    assert hard > columns // 2

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
             raw_parameters: dict | None = None):
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
                "fill_color": FILL, "border_color": BORDER, "single_piece": solid, "border_radius": 0.0})),
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
@pytest.mark.parametrize("option", ("ghost_custom", "ghost_gradient"))
def test_ghost_options_change_only_ghost_pixels(render, option, solid):
    import numpy as np
    off = render(solid=solid)
    ghost = _changed(off, render(ghosting=False, solid=solid))
    changed = _changed(off, render(ON[option], solid=solid))
    assert changed.sum() > 100 and not (changed & ~ghost).any(), option
    # Negative controls: no ghosts, no effect; Rainbow Ghost on overrides a custom colour.
    assert np.array_equal(render(ghosting=False, solid=solid), render(ON[option], ghosting=False, solid=solid))
    if option == "ghost_custom":
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

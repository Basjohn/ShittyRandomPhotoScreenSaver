"""No Visualizer pixel lands outside the card's inner edge or under its frame, for every registered mode (R-188, 1C.4).

The production ``DisplayScene.qml`` and scene controller draw the card through a hidden ``QQuickRenderControl`` host
(``tools/expanded_visualizer_evidence.HiddenDisplayHost``; no window is ever shown). Each mode replays a shipped
clip at frozen test settings (never a curated preset). At each check the frame is read three times: as drawn; with a
full-brightness white line along each edge drawn after the mode, inside the same clip (from outside the card, across
the border, a few pixels into the content: bright content touching every edge and corner); and with the mode's draw
suppressed (``QuickVisualizerRenderHost.render`` returns without drawing), the same scene, chrome and frame with the
Visualizer hidden. Against the hidden read:

* every pixel whose centre lies more than 0.71 device pixel outside the card's inner edge (the rounded inner path the
  card draws: the card item where the scene put it, inset by the frame as Qt draws it, so the corners are included)
  is unchanged in both reads;
* along the straight edges, every pixel the card frame covers at all (the frame's green shows in the hidden read: its
  anti-aliased inner and outer edge pixels and the band between) is unchanged in both reads (1C.4: content under the
  frame's blended edge pixel shows through it, and over bright content it reads as the content reaching into the
  border). The card sits on whole device pixels, so a straight edge has no blended pixel to hide content under;
* in the corners, where Qt anti-aliases the frame's inner arc against whatever lies beneath it as any rounded edge,
  content lies only under pixels the frame covers by at most half (``tools/card_clip_contract.CORNER_BLEND``),
  never under its body;
* the white lines touch the frame on all four sides: no card surface shows between the frame's last pixel and the
  content (no seam).

Each within 2 levels per channel, the run-to-run floor.

Checks, on the card as drawn now (the item's own record):

* ``steady``: the ordinary card, coherent snapshot.
* ``shrunk``: the card takes a smaller record (a wheel resize) before a coherent snapshot exists, so the node draws
  the retained snapshot, whose record is larger than the card.
* ``expanded_<style>``: the display-wide card (Expanded Visualizer) for every mode that supports it, in each display
  style (1D.2): Default, Borders To Edge (the frame's outer edge on the display's, square corners) and Hide Borders
  (no frame: the clip is the whole display, so nothing may change outside it).
* ``collapsed_<style>``: the ordinary card taken back from that display-wide one before a coherent snapshot exists
  (the retained snapshot's record is display-wide).

Each runs with Normal and with Glass card material, at 100 %, 125 % and 150 %, on a card the layout requests off the
device-pixel grid (as pixel shift, CUSTOM scale and centred layouts put it; the resolver snaps it). Before R-188 the
node built its stencil clip from the retained snapshot's record, so ``shrunk`` and ``collapsed`` let Spline Curve's
fill and lines cross the card's rounded corners; before 1C.4 the card sat where the layout put it and the clip ended
at the record's border width, so the white lines lay under the frame's anti-aliased edge pixel.
"""
from __future__ import annotations

import ctypes

import pytest

from core.settings.fullscreen_overlays import DISPLAY_STYLES
from core.settings.visualizer_mode_registry import (
    VisualizerShellPolicy,
    get_visualizer_mode_descriptor,
    get_visualizer_presentation_policy,
    iter_all_visualizer_mode_descriptors,
)
from tools import card_clip_contract as contract
from tools.card_clip_contract import TOLERANCE

DISPLAY = (960, 600)
FRAMES = 150               # replayed frames before the first check (every mode has drawn by then)
OFF_GRID = contract.OFF_GRID
CARD = contract.CONTRACT_CARD
WHITE_LINE_REACH = 3.0     # logical px the white lines reach past the border into the content
MODES = [descriptor.mode_id for descriptor in iter_all_visualizer_mode_descriptors()]
# The checks themselves are tools/card_clip_contract.py's (one reading, shared with the native composite's harness).


class _WhiteEdgeLines:
    """Full-brightness white lines along each edge of the Visualizer item, drawn inside the current clip."""

    def __init__(self) -> None:
        self._resources: tuple[int, int, int] | None = None

    def draw(self, logical_size, matrix_values, band: float) -> None:
        from OpenGL import GL as gl

        from rendering.quick.render.gl_resources import compile_program

        if self._resources is None:
            program = compile_program(
                "#version 460 core\nlayout(location = 0) in vec2 aPosition;\nuniform mat4 uMatrix;\n"
                "void main() { gl_Position = uMatrix * vec4(aPosition, 0.0, 1.0); }\n",
                "#version 460 core\nout vec4 fragColor;\nvoid main() { fragColor = vec4(1.0); }\n",
                label="card clip contract white edge lines")
            self._resources = (program, int(gl.glGenVertexArrays(1)), int(gl.glGenBuffers(1)))
        program, vao, vbo = self._resources
        width, height = logical_size
        outside = 4.0
        quads = ((-outside, -outside, band + outside, height + 2 * outside),
                 (width - band, -outside, band + outside, height + 2 * outside),
                 (-outside, -outside, width + 2 * outside, band + outside),
                 (-outside, height - band, width + 2 * outside, band + outside))
        vertices = []
        for x, y, w, h in quads:
            vertices += [x, y, x + w, y, x, y + h, x + w, y, x + w, y + h, x, y + h]
        data = (ctypes.c_float * len(vertices))(*vertices)
        prior_program = int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM))
        prior_vao = int(gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING))
        prior_buffer = int(gl.glGetIntegerv(gl.GL_ARRAY_BUFFER_BINDING))
        prior_caps = {cap: bool(gl.glIsEnabled(cap)) for cap in (gl.GL_BLEND, gl.GL_DEPTH_TEST, gl.GL_CULL_FACE)}
        try:
            for cap in prior_caps:
                gl.glDisable(cap)
            gl.glUseProgram(program)
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(data), data, gl.GL_STREAM_DRAW)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, False, 2 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))
            gl.glUniformMatrix4fv(gl.glGetUniformLocation(program, "uMatrix"), 1, gl.GL_FALSE, matrix_values)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(vertices) // 2)
        finally:
            gl.glUseProgram(prior_program)
            gl.glBindVertexArray(prior_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_buffer)
            for cap, enabled in prior_caps.items():
                (gl.glEnable if enabled else gl.glDisable)(cap)


def _settings(mode: str) -> dict:
    from tests._visualizer_frozen_settings import frozen_visualizer_settings

    settings = frozen_visualizer_settings(mode)
    overflow = get_visualizer_mode_descriptor(mode).renderer_overflow_setting
    if overflow:
        # A free-standing overflow renderer may draw past the card by its own declared choice; the card contract
        # binds every mode on the card's clip.
        settings[overflow] = False
    return settings


@pytest.fixture
def host(qt_app, dpr):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    display = HiddenDisplayHost(*DISPLAY, dpr=dpr)
    try:
        yield display
    finally:
        display.close()


@pytest.mark.qt
@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5])
@pytest.mark.parametrize("material", ["normal", "glass"])
@pytest.mark.parametrize("mode", MODES)
def test_no_visualizer_pixel_lands_outside_the_cards_inner_edge(host, mode, material, dpr):
    from unittest.mock import patch

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.expanded_visualizer_evidence import shipped_clip
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.feature_replay import (
        PcmReanalysis, configure_offline_controller, deterministic_clock,
    )
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    descriptor = get_visualizer_mode_descriptor(mode)
    carded = get_visualizer_presentation_policy(mode).shell_policy is VisualizerShellPolicy.CARD
    width, height = DISPLAY
    scene = host.scene

    def ordinary(scale: float = 1.0):
        return resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy(mode), display_size=DISPLAY,
            outer_origin=(24.0 + OFF_GRID, height - 280.0 * scale - 24.0 + OFF_GRID), dpr=dpr,
            uniform_visual_scale=scale, **CARD)

    route = {"record": ordinary()}
    mode_render = QuickVisualizerRenderHost.render
    white_lines = _WhiteEdgeLines()

    def suppressed(self, *, snapshot, **_kwargs):
        return snapshot.logical.mode_id

    def with_white_lines(self, *, snapshot, logical_size, matrix_values, **kwargs):
        mode_id = mode_render(self, snapshot=snapshot, logical_size=logical_size, matrix_values=matrix_values,
                              **kwargs)
        white_lines.draw(logical_size, matrix_values, CARD["border_width"] + WHITE_LINE_REACH)
        return mode_id

    def read_three():
        host.render()
        drawn = host.read()
        reads = [drawn]
        for render in (with_white_lines, suppressed):
            with patch.object(QuickVisualizerRenderHost, "render", render):
                scene.request_visualizer_present()
                host.render()
                reads.append(host.read())
        return reads

    escapes: dict[str, int] = {}
    under_frame: dict[str, int] = {}
    gaps: dict[str, dict] = {}
    lit: dict[str, int] = {}

    def check(name: str) -> None:
        drawn, white, hidden = read_three()
        card = scene.visualizer_item.presentation
        loader = scene._visualizer_loader
        card_rect = (loader.x(), loader.y(), loader.width(), loader.height())   # where the scene put the card
        reading = contract.read_contract(drawn, white, hidden, card_rect=card_rect, presentation=card, dpr=dpr,
                                         border_alpha=CARD["border_color"][3])
        escapes[name] = reading.escapes
        lit[name] = reading.lit
        if carded:
            under_frame[name] = reading.under_frame
            if reading.gaps is not None:
                # A frame to meet (Hide Borders has none: its coverage is the display, checked above).
                gaps[name] = reading.gaps

    clip = shipped_clip(4.0)
    with deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        configure_offline_controller(controller, mode, settings=_settings(mode))
        reanalysis = PcmReanalysis() if descriptor.raw_musical_signals else None
        identity = controller.begin_render_activation(
            engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
        scene.set_visualizer_render_source(controller.render_bridge, identity)
        sync = QuickVisualizerPresentationSync(
            controller, resolve_presentation=lambda: route["record"],
            commit_presentation=lambda presentation: scene.apply_visualizer_presentation(presentation, active=True),
            request_present=scene.request_visualizer_present,
        )
        frames = iter(clip.frames)

        def step() -> None:
            feature = next(frames)
            clock[0] = feature.timestamp_us / 1_000_000.0
            controller.playing = feature.playing
            engine.set_playback_state(feature.playing)
            assert engine.accept_feature_frame(feature)
            if reanalysis is not None:
                reanalysis.accept(engine, feature)
            assert logical_tick(controller.logical_tick_state) is not None
            assert sync.sync_latest()
            host.render()

        step()
        if material != "normal":
            assert scene.apply_visualizer_surface_material(material)
            host.render()
            # The material is card chrome: a frameless shell draws no card to put it on.
            assert bool(scene._visualizer_root.property("cardSurfaceMaterialActive")) is carded
        for _ in range(FRAMES):
            step()
        check("steady")

        # A smaller record reaches the card before a coherent snapshot does.
        route["record"] = ordinary(0.85)
        scene.apply_visualizer_presentation(route["record"], active=True)
        check("shrunk")
        route["record"] = ordinary()
        for _ in range(4):
            step()

        if descriptor.supports_expanded_display:
            # Every display style (1D.2): Default, Borders To Edge (the frame on the display's edges) and Hide
            # Borders (no frame: the coverage is the whole display).
            for style in DISPLAY_STYLES:
                route["record"] = resolve_expanded_visualizer_presentation(ordinary(), display_size=DISPLAY, dpr=dpr,
                                                                           display_style=style)
                for _ in range(8):
                    step()
                check(f"expanded_{style}")
                # The ordinary card comes back before a coherent snapshot does.
                route["record"] = ordinary()
                scene.apply_visualizer_presentation(route["record"], active=True)
                check(f"collapsed_{style}")
                for _ in range(4):
                    step()
        controller.close_render_admission()

    assert lit["steady"] > 0, f"{mode} drew nothing inside the card: the check would be vacuous"
    if descriptor.supports_expanded_display:
        assert all(lit.get(f"expanded_{style}", 0) > 0 for style in DISPLAY_STYLES), lit
    assert escapes == {name: 0 for name in escapes}, (
        f"{mode} ({material}, {dpr}) changed pixels outside the card's inner edge: {escapes}")
    assert under_frame == {name: 0 for name in under_frame}, (
        f"{mode} ({material}, {dpr}) changed pixels the card frame covers (content under its edge): {under_frame}")
    for name, sides in gaps.items():
        assert all(gap == 0 for gap in sides.values()), (
            f"{mode} ({material}, {dpr}, {name}): card surface between the frame and the white lines (a seam): {sides}")


OVERFLOW_MODES = [d.mode_id for d in iter_all_visualizer_mode_descriptors() if d.renderer_overflow_setting]
OVERFLOW_REACH = {
    "sphere": {"sphere_shadow_enabled": True, "sphere_shadow_distance": 2.5, "sphere_shadow_size": 1.6,
               "sphere_particle_distance": 1.0, "sphere_fragment_strength": 1.0},
    "extruded_spectrum": {"extruded_spectrum_tilt": 1.0, "extruded_spectrum_turn": 1.0,
                          "extruded_spectrum_depth": 4.0, "extruded_spectrum_reflection": 1.0},
}


def _overflow_escapes(host, mode: str, dpr: float, display: tuple[float, float], *, held: bool) -> tuple[int, int]:
    """(pixels changed outside ``display`` -- the window's part past the display, as the R-63 overscan lies --, pixels
    changed inside it), Hide Borders card on ``display``, the mode's overflow ON."""
    import numpy
    from unittest.mock import patch

    from core.settings.fullscreen_overlays import DISPLAY_STYLE_HIDE_BORDERS
    from rendering.quick.visualizer import node as node_module
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.expanded_visualizer_evidence import shipped_clip
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller, deterministic_clock
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    scene = host.scene
    settings = _settings(mode)
    settings[get_visualizer_mode_descriptor(mode).renderer_overflow_setting] = True
    # Test-owned settings that push the overflow's reach as far as they go (a long shadow; a deep, tilted and turned
    # bar field).
    for key, value in OVERFLOW_REACH.get(mode, {}).items():
        assert key in settings, key
        settings[key] = value
    ordinary = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode), display_size=display, outer_origin=(24.0, 24.0), dpr=dpr,
        **CARD)
    record = resolve_expanded_visualizer_presentation(ordinary, display_size=display, dpr=dpr,
                                                      display_style=DISPLAY_STYLE_HIDE_BORDERS)
    clip = shipped_clip(3.0)
    held_patch = patch.object(node_module, "renderer_overflow_held", lambda _card: False) if not held else None
    admitted = node_module.VisualizerRenderNode._overflow_admitted
    decisions: list[bool] = []

    def recorded(snapshot, card):
        decisions.append(bool(admitted(snapshot, card)))
        return decisions[-1]
    with deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        configure_offline_controller(controller, mode, settings=settings)
        identity = controller.begin_render_activation(
            engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
        scene.set_visualizer_render_source(controller.render_bridge, identity)
        sync = QuickVisualizerPresentationSync(
            controller, resolve_presentation=lambda: record,
            commit_presentation=lambda presentation: scene.apply_visualizer_presentation(presentation, active=True),
            request_present=scene.request_visualizer_present)
        spy = patch.object(node_module.VisualizerRenderNode, "_overflow_admitted", staticmethod(recorded))
        try:
            spy.start()
            if held_patch is not None:
                held_patch.start()
            for feature in clip.frames[:120]:
                clock[0] = feature.timestamp_us / 1_000_000.0
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                engine.accept_feature_frame(feature)
                assert logical_tick(controller.logical_tick_state) is not None
                assert sync.sync_latest()
                host.render()
            drawn = host.read()
            with patch.object(QuickVisualizerRenderHost, "render", lambda self, *, snapshot, **_kw:
                              snapshot.logical.mode_id):
                scene.request_visualizer_present()
                host.render()
                hidden = host.read()
        finally:
            if held_patch is not None:
                held_patch.stop()
            spy.stop()
            controller.close_render_admission()
    changed = numpy.abs(drawn[..., :3].astype(int) - hidden[..., :3].astype(int)).max(axis=2) > TOLERANCE
    inside = numpy.zeros(changed.shape, bool)
    inside[:round(display[1] * dpr), :round(display[0] * dpr)] = True
    return int((changed & ~inside).sum()), int((changed & inside).sum()), set(decisions)


@pytest.mark.qt
@pytest.mark.parametrize("dpr", [1.25])
@pytest.mark.parametrize("mode", OVERFLOW_MODES)
def test_hide_borders_holds_a_renderers_overflow_to_the_display_rect(host, mode, dpr):
    """1D.2, lead's decision 3: no style draws past the visible rect. A Hide Borders card is the whole display; a
    renderer whose overflow is on (Sphere, Extruded Spectrum) is held to it (the render node's clipped path, its clip
    the display rect), never into the window's part past the display (the overscan). The display here is the
    window's top-left quarter, so the rest of the window stands for what lies past it.

    Neither mode can expand today (``supports_expanded_display``), so this binds the rule ahead of them. With these
    test-owned settings neither reaches past a whole-display card even unheld (measured: 0 pixels outside), so the
    pixels alone cannot discriminate; the bar is the render node's decision on every frame (the clipped path, held)
    plus nothing drawn outside. Negative control: the pre-1D.2 decision (overflow never held) takes the unclipped
    path on every frame."""
    display = (DISPLAY[0] / 4.0, DISPLAY[1] / 2.0)
    outside, inside, decisions = _overflow_escapes(host, mode, dpr, display, held=True)
    _outside, _inside, control = _overflow_escapes(host, mode, dpr, display, held=False)
    assert inside > 0, f"{mode} drew nothing on the display: the check would be vacuous"
    assert decisions == {False}, f"{mode}'s overflow was not held on every frame: {decisions}"
    assert control == {True}, f"the control did not take the unclipped path: {control}"
    assert outside == 0, f"{mode}'s overflow drew {outside} pixels past the display rect"

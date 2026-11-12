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
  content lies only under pixels the frame covers by at most half (``CORNER_BLEND``), never under its body;
* the white lines touch the frame on all four sides: no card surface shows between the frame's last pixel and the
  content (no seam).

Each within 2 levels per channel, the run-to-run floor.

Checks, on the card as drawn now (the item's own record):

* ``steady``: the ordinary card, coherent snapshot.
* ``shrunk``: the card takes a smaller record (a wheel resize) before a coherent snapshot exists, so the node draws
  the retained snapshot, whose record is larger than the card.
* ``expanded``: the display-wide card (Expanded Visualizer) for every mode that supports it.
* ``collapsed``: the ordinary card taken back from the display-wide one before a coherent snapshot exists (the
  retained snapshot's record is display-wide).

Each runs with Normal and with Glass card material, at 100 %, 125 % and 150 %, on a card the layout requests off the
device-pixel grid (as pixel shift, CUSTOM scale and centred layouts put it; the resolver snaps it). Before R-188 the
node built its stencil clip from the retained snapshot's record, so ``shrunk`` and ``collapsed`` let Spline Curve's
fill and lines cross the card's rounded corners; before 1C.4 the card sat where the layout put it and the clip ended
at the record's border width, so the white lines lay under the frame's anti-aliased edge pixel.
"""
from __future__ import annotations

import ctypes

import pytest

from core.settings.visualizer_mode_registry import (
    VisualizerShellPolicy,
    get_visualizer_mode_descriptor,
    get_visualizer_presentation_policy,
    iter_all_visualizer_mode_descriptors,
)

DISPLAY = (960, 600)
TOLERANCE = 2              # 8-bit levels per channel
OUTSIDE_PX = 0.71          # a pixel whose centre lies this far out has no footprint inside the inner edge
FRAMES = 150               # replayed frames before the first check (every mode has drawn by then)
OFF_GRID = 0.3             # logical offset of the card's origin: its edges fall inside device pixels at every DPR
CARD = {
    # A non-default width and a half-transparent border: content drawn under the border band would show through
    # it and count, not hide beneath an opaque frame.
    "border_width": 5.0, "corner_radius": 8.0, "content_inset": 0.0,
    "background_color": (0, 0, 0, 255), "border_color": (0, 255, 0, 128),
    "shadow_enabled": False, "shadow_color": (0, 0, 0, 0), "shadow_blur": 0.0,
    "shadow_offset": (0.0, 0.0), "shadow_spread": 0.0, "shadow_extensions": (0.0, 0.0, 0.0, 0.0),
}
WHITE_LINE_REACH = 3.0     # logical px the white lines reach past the border into the content
CORNER_BLEND = 0.5         # the most frame coverage a corner pixel with content under it may have (the arc's own AA)
MODES = [descriptor.mode_id for descriptor in iter_all_visualizer_mode_descriptors()]


def _drawn_inner_path(scene, presentation, dpr):
    """The card's rounded inner path as the scene draws it: the card item's own geometry (where the scene put it),
    inset by the frame's width as Qt Quick draws it (rounded to whole device pixels, half up); a frameless shell's is
    its content rect."""
    import math

    if presentation.shell_policy is not VisualizerShellPolicy.CARD:
        return tuple(presentation.content_rect), float(presentation.shell_style["inner_corner_radius"])
    loader = scene._visualizer_loader
    x, y, w, h = loader.x(), loader.y(), loader.width(), loader.height()
    inset = math.floor(presentation.border_width * dpr + 0.5) / dpr
    radius = max(0.0, float(presentation.shell_style["corner_radius"]) - inset)
    return (x + inset, y + inset, w - 2 * inset, h - 2 * inset), radius


def _outside_inner_edge(path, shape, dpr):
    """Device pixels lying wholly outside the card's rounded inner path."""
    import numpy

    height, width = shape
    ys, xs = numpy.mgrid[0:height, 0:width].astype(numpy.float64)
    lx, ly = (xs + 0.5) / dpr, (ys + 0.5) / dpr
    (x, y, w, h), radius = path
    radius = min(radius, w / 2.0, h / 2.0)
    qx = numpy.abs(lx - (x + w / 2.0)) - (w / 2.0 - radius)
    qy = numpy.abs(ly - (y + h / 2.0)) - (h / 2.0 - radius)
    distance = (numpy.sqrt(numpy.maximum(qx, 0.0) ** 2 + numpy.maximum(qy, 0.0) ** 2)
                + numpy.minimum(numpy.maximum(qx, qy), 0.0) - radius)
    return distance * dpr > OUTSIDE_PX


def _frame_coverage(hidden):
    """How much of each pixel the card frame covers: its half-transparent green over the surface (neither green)."""
    import numpy

    rgb = hidden[..., :3].astype(int)
    return (rgb[..., 1] - numpy.maximum(rgb[..., 0], rgb[..., 2])) / float(CARD["border_color"][3])


def _frame_pixels(hidden):
    """Pixels the card frame covers at all."""
    return _frame_coverage(hidden) * CARD["border_color"][3] > TOLERANCE


def _corner_zones(card_rect, corner_radius, shape, dpr):
    """Device pixels in the four corner squares of the card (the arc and a pixel either side of where it meets an edge)."""
    import numpy

    zones = numpy.zeros(shape, bool)
    x, y, w, h = card_rect
    reach = int(corner_radius * dpr) + 2
    left, top = int(x * dpr) - 1, int(y * dpr) - 1
    right, bottom = int((x + w) * dpr) + 1, int((y + h) * dpr) + 1
    for x0, y0 in ((left, top), (right - reach, top), (left, bottom - reach), (right - reach, bottom - reach)):
        zones[max(0, y0):max(0, y0 + reach), max(0, x0):max(0, x0 + reach)] = True
    return zones


def _surface_gaps(frame, white, card_rect, dpr):
    """Device pixels of card surface between the frame's last pixel and the white line, on each side (middle row/col)."""
    import numpy

    ox, oy, ow, oh = card_rect
    height, width = frame.shape
    row, col = int((oy + oh / 2.0) * dpr), int((ox + ow / 2.0) * dpr)
    left, right = max(0, int(ox * dpr) - 2), min(width, int((ox + ow) * dpr) + 3)
    top, bottom = max(0, int(oy * dpr) - 2), min(height, int((oy + oh) * dpr) + 3)
    gaps = {}
    for side, (frame_line, white_line) in {
        # From outside the card's edge to its middle.
        "left": (frame[row, left:col], white[row, left:col]),
        "right": (frame[row, col:right][::-1], white[row, col:right][::-1]),
        "top": (frame[top:row, col], white[top:row, col]),
        "bottom": (frame[row:bottom, col][::-1], white[row:bottom, col][::-1]),
    }.items():
        hits = numpy.flatnonzero(frame_line)
        if hits.size == 0:
            gaps[side] = None
            continue
        breaks = numpy.flatnonzero(numpy.diff(hits) > 1)
        frame_end = int(hits[breaks[0]] if breaks.size else hits[-1])
        first_white = numpy.flatnonzero(white_line[frame_end + 1:])
        gaps[side] = int(first_white[0]) if first_white.size else None
    return gaps


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
    import numpy
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

        def changed(read):
            return numpy.abs(read[..., :3].astype(int) - hidden[..., :3].astype(int)).max(axis=2) > TOLERANCE

        drawn_changed, white_changed = changed(drawn), changed(white)
        outside = _outside_inner_edge(_drawn_inner_path(scene, card, dpr), drawn_changed.shape, dpr)
        escapes[name] = int((drawn_changed & outside).sum() + (white_changed & outside).sum())
        lit[name] = int((drawn_changed & ~outside).sum())
        if carded:
            frame = _frame_pixels(hidden)
            loader = scene._visualizer_loader
            card_rect = (loader.x(), loader.y(), loader.width(), loader.height())
            corners = _corner_zones(card_rect, float(card.shell_style["corner_radius"]), frame.shape, dpr)
            # Straight edges: no content under any frame pixel. Corners: only under the arc's own blend.
            forbidden = (frame & ~corners) | (corners & (_frame_coverage(hidden) > CORNER_BLEND))
            under_frame[name] = int((drawn_changed & forbidden).sum() + (white_changed & forbidden).sum())
            gaps[name] = _surface_gaps(frame, white_changed, card_rect, dpr)

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
            route["record"] = resolve_expanded_visualizer_presentation(ordinary(), display_size=DISPLAY, dpr=dpr)
            for _ in range(8):
                step()
            check("expanded")
            # The ordinary card comes back before a coherent snapshot does.
            route["record"] = ordinary()
            scene.apply_visualizer_presentation(route["record"], active=True)
            check("collapsed")
        controller.close_render_admission()

    assert lit["steady"] > 0, f"{mode} drew nothing inside the card: the check would be vacuous"
    assert escapes == {name: 0 for name in escapes}, (
        f"{mode} ({material}, {dpr}) changed pixels outside the card's inner edge: {escapes}")
    assert under_frame == {name: 0 for name in under_frame}, (
        f"{mode} ({material}, {dpr}) changed pixels the card frame covers (content under its edge): {under_frame}")
    for name, sides in gaps.items():
        assert all(gap == 0 for gap in sides.values()), (
            f"{mode} ({material}, {dpr}, {name}): card surface between the frame and the white lines (a seam): {sides}")

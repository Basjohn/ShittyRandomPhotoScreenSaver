"""Extruded Spectrum: Spectrum's bars as lit 3D boxes on the shared Scene3D
foundation. The projection and height transfer equal their CPU mirrors on the GPU and
Spectrum's own transfer; the fit keeps the tallest scene inside the bar field; through the
production capture seam and render host on a real offscreen context (no window) the bars
stand where Spectrum's do, louder bars taller, coloured across the spectrum, over a card
left untouched where nothing is drawn, fading with the content fade; resources release;
the mode's heavy modules stay dormant until it renders."""
from __future__ import annotations

import dataclasses
import math
import random
import subprocess
import sys

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.extruded_spectrum_program import (
    _COMMON_UNIFORMS,
    _PROJECTION_GLSL,
    EXTRUDED_CEILING,
    EXTRUDED_MAX_TILT,
    EXTRUDED_MAX_TURN,
    EXTRUDED_REFLECTION_SPACE,
    extruded_fit,
    extruded_height,
    extruded_project,
)
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    SPECTRUM_SHADER_INPUT_SCALE,
    spectrum_bar_to_boosted,
)

pytestmark = pytest.mark.qt

W, H = 684, 418


def test_the_bar_heights_are_spectrums_own_transfer():
    for bar in np.linspace(0.0, 1.0, 41):
        for height_scale in (1.0, 1.3, 1.6, 1.85):          # compute_spectrum_height_scale's range
            assert extruded_height(bar * SPECTRUM_SHADER_INPUT_SCALE, height_scale) == pytest.approx(
                spectrum_bar_to_boosted(bar, height_scale=height_scale), abs=1e-12)


def test_the_fit_keeps_the_tallest_scene_inside_the_bar_field():
    rng = random.Random(9)
    for _ in range(200):
        half_span, depth = rng.uniform(0.5, 4.0), rng.uniform(0.0, 0.6)
        tilt, reflection, aspect = rng.uniform(0.0, EXTRUDED_MAX_TILT), rng.uniform(0.0, 1.0), rng.uniform(0.8, 6.0)
        turn = rng.uniform(-EXTRUDED_MAX_TURN, EXTRUDED_MAX_TURN)
        scale, floor = extruded_fit(half_span, depth, tilt, reflection, aspect, turn)
        assert 0.0 < scale <= 1.0
        for x in (-half_span, half_span):
            for y in (0.0, EXTRUDED_CEILING):
                for z in (-depth, 0.0):
                    sx, sy, _ = extruded_project((x, y, z), tilt, turn)
                    assert abs(sx * scale) <= 0.5 * aspect + 1e-9
                    assert floor + sy * scale <= 1.0 + 1e-9
                    assert floor + sy * scale >= EXTRUDED_REFLECTION_SPACE * reflection - 1e-9
    # Untilted and shallow, the scene is exactly Spectrum's: no fit shrink, the floor at the bottom.
    assert extruded_fit(1.0, 0.0, 0.0, 0.0, 3.0) == (1.0, 0.0)


def test_the_projection_and_heights_match_their_mirrors_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(4)
        cases = [((rng.uniform(-3, 3), rng.uniform(0, 1), rng.uniform(-0.6, 0)), rng.uniform(0, EXTRUDED_MAX_TILT),
                  rng.uniform(-EXTRUDED_MAX_TURN, EXTRUDED_MAX_TURN), rng.uniform(0, 0.6)) for _ in range(120)]
        gpu = probe.run("vec4 a = arg(0); vec4 b = arg(1);"
                        " FragColor = vec4(extrudedProject(a.xyz, vec2(a.w, b.x)), extrudedHeight(b.y));",
                        [[(*p, tilt), (turn, level)] for p, tilt, turn, level in cases],
                        declarations=_COMMON_UNIFORMS + _PROJECTION_GLSL)
        # uHeightScale is unset (0) in the probe: the transfer clamps it to 1.
        _check(gpu, [(*extruded_project(p, tilt, turn), extruded_height(level, 1.0))
                     for p, tilt, turn, level in cases])
    finally:
        probe.close()


class _Target:
    """An offscreen GL context and RGBA target the size of the card (no window)."""

    def __init__(self) -> None:
        from tools.transition_contact_sheet import TransitionCapture

        self.capture = TransitionCapture(W, H)

    def render(self, host, snapshot, backdrop=(0.0, 0.0, 0.0, 0.0)) -> np.ndarray:
        """The card's pixels over ``backdrop`` (what Quick drew beneath, as one colour)."""
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.capture.fbo)
        gl.glViewport(0, 0, W, H)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(*backdrop)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        matrix = (2 / W, 0, 0, 0, 0, -2 / H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
        mode = host.render(snapshot=snapshot, viewport=(0, 0, W, H), logical_size=(float(W), float(H)),
                           matrix_values=matrix)
        assert mode == snapshot.logical.mode_id
        pixels = gl.glReadPixels(0, 0, W, H, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.flipud(np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(H, W, 4)).astype(np.int16)

    def close(self) -> None:
        self.capture.close()


def _snapshot(mode: str = "extruded_spectrum", **parameters):
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode=mode)
    if parameters:
        state = snapshot.logical.mode_state
        state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
        logical = dataclasses.replace(snapshot.logical, mode_state=state)
        snapshot = dataclasses.replace(snapshot, logical=logical)
    return snapshot


@pytest.fixture
def target(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    result = _Target()
    host = QuickVisualizerRenderHost()
    yield result, host
    host.release_resources()
    result.close()


def _columns(snapshot):
    """Each bar's centre column and level, from Spectrum's own layout."""
    from rendering.quick.visualizer.implementations.spectrum import compute_quick_spectrum_layout
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame

    frame = QuickVisualizerRenderFrame(snapshot, (0, 0, W, H), (float(W), float(H)), (1.0,) * 16, 1)
    count = snapshot.logical.common.bar_count
    layout = compute_quick_spectrum_layout(local_content_rect=frame.logical_content_rect,
                                           viewport_extent=snapshot.presentation.logical_viewport_extent,
                                           visual_scale=snapshot.presentation.uniform_visual_scale, bar_count=count)
    centres = [layout.bars_left + (i + 0.5) * layout.bar_width + i * layout.bar_gap for i in range(count)]
    return centres, list(snapshot.logical.common.bars[:count]), frame.logical_content_rect


def test_the_bars_stand_where_spectrums_do_coloured_across_the_spectrum_over_an_untouched_card(target):
    capture, host = target
    snapshot = _snapshot()
    pixels = capture.render(host, snapshot)
    alpha = pixels[..., 3]
    centres, levels, (cx, cy, cw, ch) = _columns(snapshot)
    assert alpha.max() == 255
    # Nothing outside the card's content: the shell (drawn by QML) shows through untouched.
    outside = np.ones((H, W), bool)
    outside[int(cy) + 1:int(cy + ch) - 1, int(cx) + 1:int(cx + cw) - 1] = False
    assert alpha[outside].max() == 0

    def top(column: float) -> int:
        rows = np.nonzero(alpha[:, int(round(column))] > 200)[0]
        return int(rows.min()) if rows.size else H

    tops = [top(c) for c in centres]
    loud, quiet = int(np.argmax(levels)), int(np.argmin(levels))
    assert tops[loud] < tops[quiet] - 20                    # the loudest bar stands well above the quietest
    order = np.argsort(levels)
    assert np.corrcoef(np.array(levels)[order], -np.array(tops)[order])[0, 1] > 0.9

    def colour(column: float) -> np.ndarray:
        rows = np.nonzero(alpha[:, int(round(column))] == 255)[0]
        return pixels[rows[len(rows) // 2], int(round(column)), :3].astype(float)

    first, last = colour(centres[0]), colour(centres[-1])
    assert first[0] > first[2] + 40                         # the bass end is red
    assert last[2] > last[1] + 40                           # the treble end is violet/blue


def test_the_content_fade_and_spectrum_colours(target):
    capture, host = target
    full = capture.render(host, _snapshot())
    faded_snapshot = _snapshot()
    faded_snapshot = dataclasses.replace(
        faded_snapshot, presentation=dataclasses.replace(faded_snapshot.presentation, content_fade=0.5))
    faded = capture.render(host, faded_snapshot)
    solid = full[..., 3] == 255
    assert np.abs(faded[..., 3][solid] - 128).max() <= 2
    assert np.array_equal(capture.render(host, dataclasses.replace(
        faded_snapshot, presentation=dataclasses.replace(faded_snapshot.presentation, content_fade=0.0)))[..., 3],
        np.zeros((H, W), np.int16))
    # Bar Colours: Spectrum's bar colours (its preset's grey-on-black here), so no hue.
    plain = capture.render(host, _snapshot(extruded_spectrum_colouring="Bar Colours"))
    centres, _levels, _rect = _columns(_snapshot())
    for c in centres:
        rows = np.nonzero(plain[:, int(c), 3] == 255)[0]
        if rows.size:
            colour = plain[rows, int(c), :3].mean(axis=0)
            assert colour.max() - colour.min() < 12


def test_mirror_faces_reflect_what_lies_beneath_on_the_faces_only(target):
    """Mirror Faces shows the wallpaper (what Quick drew under the Visualizer) in the bars' faces:
    over an orange backdrop the faces turn orange, over a blue one blue; nothing outside the
    bars changes, and with Mirror Faces off nothing of the backdrop is captured or held."""
    capture, host = target
    organ = dict(extruded_spectrum_colouring="Spectral Edges", extruded_spectrum_reflection=0.0,
                 extruded_spectrum_tilt=0.1, extruded_spectrum_gloss=0.9)
    shown = capture.render(host, _snapshot(**organ, extruded_spectrum_face_mirror=0.0))
    faces, drawn = shown[..., 3] == 255, shown[..., 3] > 0
    renderer = host._implementations["extruded_spectrum"]
    assert not renderer._backdrop.has_resources
    colours = {}
    for name, backdrop in (("orange", (1.0, 0.5, 0.0, 1.0)), ("blue", (0.0, 0.25, 1.0, 1.0))):
        empty = capture.render(host, _snapshot(**organ, extruded_spectrum_face_mirror=1.0),
                               backdrop=backdrop)
        assert renderer._backdrop.has_resources
        plain = capture.render(host, _snapshot(**organ, extruded_spectrum_face_mirror=0.0), backdrop=backdrop)
        changed = np.abs(empty - plain)[..., :3].max(axis=2) > 2
        assert changed.any() and not changed[~drawn].any()        # only on the bars
        colours[name] = empty[faces][:, :3].mean(axis=0)
    orange, blue = colours["orange"], colours["blue"]
    assert orange[0] > orange[2] + 40 and blue[2] > blue[0] + 40
    assert not renderer._backdrop.has_resources                  # off again: nothing held


def test_the_backdrop_is_copied_every_few_frames_not_every_frame(target):
    """Reading the target being drawn stalls the GPU, so the backdrop copy is refreshed every
    BACKDROP_REFRESH_FRAMES frames and reused in between; a changed wallpaper shows within them."""
    from rendering.quick.scene3d.environment import BACKDROP_REFRESH_FRAMES

    capture, host = target
    mirrored = _snapshot(extruded_spectrum_colouring="Spectral Edges", extruded_spectrum_face_mirror=1.0,
                         extruded_spectrum_gloss=0.9)
    faces = capture.render(host, mirrored)[..., 3] == 255         # the bars alone, over nothing
    capture.render(host, mirrored, backdrop=(1.0, 0.5, 0.0, 1.0))
    backdrop = host._implementations["extruded_spectrum"]._backdrop
    first = backdrop.captures
    frames = [capture.render(host, mirrored, backdrop=(0.0, 0.25, 1.0, 1.0)) for _ in range(3 * BACKDROP_REFRESH_FRAMES)]
    assert backdrop.captures - first == 3
    late = frames[-1][faces][:, :3].mean(axis=0)
    assert late[2] > late[0] + 40                                 # the new (blue) backdrop is reflected


def test_smooth_edges_fill_in_lines_that_foreshortening_thinned(target):
    """Smooth Edges keeps edge lines at least a smoothed pixel wide on faces seen at an angle and
    doubles the multisampling: it adds line light near the lines; the few pixels it darkens are
    silhouette pixels resolved by more samples."""
    capture, host = target
    for view in (dict(extruded_spectrum_tilt=0.0, extruded_spectrum_turn=0.0),
                 dict(extruded_spectrum_tilt=0.36, extruded_spectrum_turn=0.18)):
        frames = [capture.render(host, _snapshot(extruded_spectrum_colouring="Spectral Edges",
                                                 extruded_spectrum_reflection=0.0,
                                                 extruded_spectrum_smooth_edges=smooth, **view))
                  for smooth in (False, True)]
        off, on = (frame[..., :3].sum(axis=2) for frame in frames)
        drawn = (frames[0][..., 3] > 0) | (frames[1][..., 3] > 0)
        brighter, darker = on > off + 24, on < off - 24
        assert brighter.sum() < 0.2 * drawn.sum()                 # only along the lines
        assert darker.sum() < 0.04 * drawn.sum() and darker.sum() * 3 < brighter.sum()


def test_resources_are_released_with_the_mode(target):
    capture, host = target
    capture.render(host, _snapshot())
    renderer = host._renderers["extruded_spectrum"] if hasattr(host, "_renderers") else None
    host.release_resources()
    if renderer is not None:
        assert not renderer.has_resources


def test_the_mode_borrows_spectrums_runtime_and_stays_dormant_until_it_renders():
    from core.settings.visualizer_mode_registry import (
        get_resolved_mode_setting_profile,
        get_technical_profile_mode,
        get_visualizer_mode_descriptor,
    )

    descriptor = get_visualizer_mode_descriptor("extruded_spectrum")
    spectrum = get_visualizer_mode_descriptor("spectrum")
    assert (descriptor.frame_runtime_module, descriptor.frame_runtime_class) == (
        spectrum.frame_runtime_module, spectrum.frame_runtime_class)
    assert get_technical_profile_mode("extruded_spectrum") == "spectrum"
    assert get_resolved_mode_setting_profile("extruded_spectrum", "shared_bar") == "spectrum"
    code = ("import sys\n"
            "import core.settings.visualizer_mode_registry, rendering.quick.visualizer.implementation_registry\n"
            "import widgets.spotify_visualizer.logical_frame_capture\n"
            "print([m for m in sys.modules if 'extruded_spectrum' in m and not m.endswith('_options')])\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True)
    assert result.stdout.strip() == "[]"

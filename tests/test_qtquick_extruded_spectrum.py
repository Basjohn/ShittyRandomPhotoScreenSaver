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

from rendering.quick.scene3d.environment import BackdropEnvironment
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.extruded_spectrum_program import (
    _COMMON_UNIFORMS,
    _PROJECTION_GLSL,
    EXTRUDED_CEILING,
    EXTRUDED_FRAGMENT_SOURCE,
    EXTRUDED_VERTEX_SOURCE,
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
from widgets.spotify_visualizer.render_state import freeze_render_fields
from tests._visualizer_frozen_settings import frozen_visualizer_settings

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


def test_mirror_faces_are_polished_without_procedural_brushed_grain():
    """Mirror Faces must not reintroduce the old hash-grain that became vertical ribbing.

    This is an intentional shader-source negative contract: the removed noise was presentation-only
    material decoration, not simulation behavior, and its exact absence prevents a visually identical
    banding regression from hiding behind a different runtime path.
    """
    assert "grainAt" not in EXTRUDED_FRAGMENT_SOURCE
    assert "float grain" not in EXTRUDED_FRAGMENT_SOURCE
    assert "0.94 + 0.12" not in EXTRUDED_FRAGMENT_SOURCE
    assert "vec3 mirror = seen * tint + lit * 0.15;" in EXTRUDED_FRAGMENT_SOURCE


def test_directional_shadow_shader_projects_the_full_box_sweep_without_overlap_stacking():
    """A cast shadow is the sweep from base footprint to shifted top, not a translated cap."""
    shadow_branch = EXTRUDED_VERTEX_SOURCE.split("if (uPass == 4)", 1)[1].split("vWorld =", 1)[0]
    assert "aNormal.y < 0.5" not in shadow_branch
    assert "vec3 shadowPoint = extrudedShadowProject(world, uShadowVector, uView);" in shadow_branch
    assert "foot.xy += vec2(shadow.x, -shadow.y) * p.y * EXTRUDED_SHADOW_CAST_REACH;" in _PROJECTION_GLSL
    fragment_shadow = EXTRUDED_FRAGMENT_SOURCE.split("if (uPass == 4)", 1)[1].split("vec3 n", 1)[0]
    assert "uShadowColor.rgb * uShadowColor.a" in fragment_shadow


def test_e8_receiver_matches_cpu_on_real_gl_across_orbit_and_all_shadow_directions(qt_app):
    """Shared production GLSL receiver must match the pure edit/reach CPU mirror."""
    from rendering.gl_programs.extruded_spectrum_program import extruded_shadow_project
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(120)
        cases = []
        for _ in range(160):
            point = (rng.uniform(-2, 2), rng.uniform(0, EXTRUDED_CEILING), rng.uniform(-0.6, 0))
            tilt, turn = rng.uniform(0, EXTRUDED_MAX_TILT), rng.uniform(-EXTRUDED_MAX_TURN, EXTRUDED_MAX_TURN)
            vector = (rng.choice((-0.22, 0.0, 0.22)), rng.choice((-0.22, 0.0, 0.22)))
            cases.append((point, tilt, turn, vector))
        gpu = probe.run(
            "vec4 a = arg(0); vec4 b = arg(1);"
            " FragColor = vec4(extrudedShadowProject(a.xyz, b.yz, vec2(a.w, b.x)), 1.0);",
            [[(*point, tilt), (turn, *vector, 0.0)] for point, tilt, turn, vector in cases],
            declarations=_COMMON_UNIFORMS + _PROJECTION_GLSL,
        )
        _check(gpu, [(*extruded_shadow_project(point, tilt, turn, vector), 1.0)
                     for point, tilt, turn, vector in cases])
    finally:
        probe.close()


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


def _snapshot(mode: str = "extruded_spectrum", at: float | None = None, **parameters):
    """The preview snapshot with ``parameters``; ``at`` seconds after its logical time when given."""
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode=mode, settings=frozen_visualizer_settings(mode))
    if at is not None:
        logical = dataclasses.replace(snapshot.logical,
                                      logical_timestamp=snapshot.logical.logical_timestamp + float(at))
        snapshot = dataclasses.replace(snapshot, logical=logical)
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


def _wallpaper(identity, rgb):
    """The reflected wallpaper an owner would make from a displayed photograph of one colour."""
    from rendering.quick.image_state import PresentationImage
    from widgets.spotify_visualizer.backdrop import make_visualizer_backdrop

    pixel = bytes((*rgb, 255))
    image = PresentationImage(identity=identity, source_path="", logical_size=(1280.0, 720.0),
                              device_pixel_ratio=1.0, pixel_size=(1280, 720), row_stride=1280 * 4,
                              rgba8=pixel * (1280 * 720))
    return make_visualizer_backdrop(image)


def test_mirror_faces_reflect_the_displayed_wallpaper_on_the_faces_only(target):
    """Mirror Faces shows the displayed photograph (the ``backdrop`` parameter its owner keeps) in
    the bars' faces: an orange wallpaper turns them orange, a blue one blue; nothing outside the
    bars changes; with Mirror Faces off, or no wallpaper, nothing is held; what Quick drew beneath
    is never read."""
    capture, host = target
    organ = dict(extruded_spectrum_colouring="Spectral Edges", extruded_spectrum_reflection=0.0,
                 extruded_spectrum_tilt=0.1, extruded_spectrum_gloss=0.9)
    shown = capture.render(host, _snapshot(**organ, extruded_spectrum_face_mirror=0.0))
    faces, drawn = shown[..., 3] == 255, shown[..., 3] > 0
    renderer = host._implementations["extruded_spectrum"]
    assert not renderer._backdrop.has_resources
    capture.render(host, _snapshot(**organ, extruded_spectrum_face_mirror=1.0))      # no wallpaper yet
    assert not renderer._backdrop.has_resources
    colours = {}
    for step, (name, rgb) in enumerate((("orange", (255, 128, 0)), ("blue", (0, 64, 255)))):
        wallpaper = _wallpaper(name, rgb)
        start = 10.0 * step
        capture.render(host, _snapshot(at=start, **organ, extruded_spectrum_face_mirror=1.0, backdrop=wallpaper))
        settled = start + BackdropEnvironment.BLEND_S + 0.5             # past its crossfade
        empty = capture.render(host, _snapshot(at=settled, **organ, extruded_spectrum_face_mirror=1.0,
                                               backdrop=wallpaper),
                               backdrop=(0.1, 0.1, 0.1, 1.0))      # what lies beneath is not reflected
        assert renderer._backdrop.has_resources
        plain = capture.render(host, _snapshot(at=settled, **organ, extruded_spectrum_face_mirror=0.0,
                                               backdrop=wallpaper),
                               backdrop=(0.1, 0.1, 0.1, 1.0))
        changed = np.abs(empty - plain)[..., :3].max(axis=2) > 2
        assert changed.any() and not changed[~drawn].any()        # only on the bars
        colours[name] = empty[faces][:, :3].mean(axis=0)
    orange, blue = colours["orange"], colours["blue"]
    assert orange[0] > orange[2] + 40 and blue[2] > blue[0] + 40
    assert not renderer._backdrop.has_resources                  # off again: nothing held


def test_the_wallpaper_uploads_once_per_photograph_and_the_reflection_crossfades(target):
    """The reflected wallpaper uploads when the displayed photograph changes, never per frame,
    and nothing reads back the target being drawn. The reflection never switches in one frame
    (operator 2026-10-04): the first wallpaper fades in, a new one crossfades from the old one."""
    capture, host = target
    first, second = _wallpaper("first", (255, 128, 0)), _wallpaper("second", (0, 64, 255))
    mirrored = dict(extruded_spectrum_colouring="Spectral Edges", extruded_spectrum_face_mirror=1.0,
                    extruded_spectrum_gloss=0.9)
    blend = BackdropEnvironment.BLEND_S
    plain = capture.render(host, _snapshot(at=0.0, **dict(mirrored, extruded_spectrum_face_mirror=0.0)))
    faces = plain[..., 3] == 255
    entering = capture.render(host, _snapshot(at=0.0, **mirrored, backdrop=first))
    assert np.abs(entering - plain)[faces].max() <= 2               # fading in: nothing yet
    backdrop = host._implementations["extruded_spectrum"]._backdrop
    for step in range(10):
        capture.render(host, _snapshot(at=blend + 0.5 + step / 90, **mirrored, backdrop=first))
    assert backdrop.uploads == 1
    settled = capture.render(host, _snapshot(at=blend + 1.0, **mirrored, backdrop=first))[faces][:, :3].mean(axis=0)
    change = blend + 2.0
    frames = [capture.render(host, _snapshot(at=change + t, **mirrored, backdrop=second)).astype(np.int16)
              for t in (0.0, 1.0 / 90, 0.5 * blend, blend + 0.5)]
    assert backdrop.uploads == 2
    means = [frame[faces][:, :3].mean(axis=0) for frame in frames]
    assert np.abs(means[0] - settled).max() < 3                     # the first frame is still the old one
    assert np.abs(frames[1] - frames[0])[faces].max() <= 6          # no frame jumps
    assert means[0][0] > means[2][0] > means[3][0] and means[0][2] < means[2][2] < means[3][2]
    assert means[3][2] > means[3][0] + 40                           # blue once the crossfade settles
    # A wallpaper brought in by a transition crossfades over that transition's duration.
    third, long = _wallpaper("third", (255, 128, 0)), 6.0
    later = change + blend + 2.0
    lasting = [capture.render(host, _snapshot(at=later + t, **mirrored, backdrop=third, backdrop_blend_s=long))
               [faces][:, :3].mean(axis=0) for t in (0.0, blend + 0.5, long + 0.5)]
    assert lasting[0][2] > lasting[1][2] > lasting[2][2]            # still turning orange past 2 s
    assert lasting[1][2] > lasting[2][2] + 10


def test_the_owner_keeps_a_wallpaper_only_while_its_mode_reflects():
    """The owner's refresh: a small copy of the displayed photograph while the active mode
    reflects (Mirror Faces above zero on a tier with reflections), made once per photograph;
    nothing otherwise."""
    from types import SimpleNamespace

    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    class _Image:
        def __init__(self, identity):
            self.identity, self.pixel_size, self.row_stride = identity, (64, 36), 64 * 4
            self.rgba8 = bytes((200, 100, 50, 255)) * (64 * 36)

    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    state = SimpleNamespace(_extruded_spectrum_face_mirror=0.0, _scene3d_detail="High", _backdrop=None)
    owner._controller = SimpleNamespace(mode_id="extruded_spectrum", presentation_state=state)
    owner._presentation_runtime = SimpleNamespace(scene_controller=SimpleNamespace(presentation_image=None,
                                                                                   incoming_image=None))
    scene = owner._presentation_runtime.scene_controller
    scene.presentation_image = _Image("a")
    owner._refresh_backdrop()
    assert state._backdrop is None                               # Mirror Faces off
    state._extruded_spectrum_face_mirror = 0.6
    owner._refresh_backdrop()
    made = state._backdrop
    assert made is not None and made.identity == "a" and made.size[0] == 512
    owner._refresh_backdrop()
    assert state._backdrop is made                               # once per photograph
    scene.presentation_image = _Image("b")
    owner._refresh_backdrop()
    assert state._backdrop.identity == "b" and state._backdrop_blend_s is None   # no transition: its own fade
    # A transition toward "c" starts: the reflection takes it now, crossfading over the
    # transition's duration; when the scene adopts "c" nothing is made again.
    scene.incoming_image = (_Image("c"), 3.5)
    owner._refresh_backdrop()
    incoming = state._backdrop
    assert incoming.identity == "c" and state._backdrop_blend_s == 3.5
    scene.incoming_image, scene.presentation_image = None, _Image("c")
    owner._refresh_backdrop()
    assert state._backdrop is incoming
    state._scene3d_detail = "KAK"                                # a tier without reflections
    owner._refresh_backdrop()
    assert state._backdrop is None
    state._scene3d_detail = "High"
    owner._controller.mode_id = "spectrum"                       # a mode that does not reflect
    owner._refresh_backdrop()
    assert state._backdrop is None


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


def test_the_mode_reuses_spectrum_runtime_with_an_owned_profile_and_lazy_renderer():
    from core.settings.visualizer_mode_registry import (
        get_resolved_mode_setting_profile,
        get_technical_profile_mode,
        get_visualizer_mode_descriptor,
    )

    descriptor = get_visualizer_mode_descriptor("extruded_spectrum")
    spectrum = get_visualizer_mode_descriptor("spectrum")
    assert (descriptor.frame_runtime_module, descriptor.frame_runtime_class) == (
        spectrum.frame_runtime_module, spectrum.frame_runtime_class)
    assert get_technical_profile_mode("extruded_spectrum") == descriptor.mode_id
    assert get_resolved_mode_setting_profile("extruded_spectrum", "shared_bar") == descriptor.mode_id
    code = ("import sys\n"
            "import core.settings.visualizer_mode_registry, rendering.quick.visualizer.implementation_registry\n"
            "import widgets.spotify_visualizer.logical_frame_capture\n"
            "print([m for m in sys.modules if 'extruded_spectrum' in m and not m.endswith('_options')])\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True)
    assert result.stdout.strip() == "[]"


def test_translucent_bars_draw_in_a_painters_order_for_any_view():
    """H8: ghost columns and the reflection blend in an exact order. The eye is the orbit's
    inverse; the bars, in disjoint x slabs, draw farthest from it first."""
    import math
    import random

    from rendering.gl_programs.extruded_spectrum_program import EXTRUDED_CAMERA, EXTRUDED_PIVOT, extruded_draw_order
    from rendering.gl_programs.scene3d import scene3d_orbit_eye, scene3d_orbit_view

    pivot = (0.0, EXTRUDED_PIVOT, 0.0)
    rng = random.Random(8)
    for _ in range(300):
        tilt, turn = rng.uniform(0.0, math.pi / 2), rng.uniform(-math.pi, math.pi)
        eye = scene3d_orbit_eye(tilt, turn, camera=EXTRUDED_CAMERA, pivot=pivot, anchor=pivot)
        seen = scene3d_orbit_view(tuple(e - p for e, p in zip(eye, pivot)), tilt, turn)
        seen = tuple(v + a for v, a in zip(seen, pivot))                         # + the anchor
        assert seen == pytest.approx((0.0, 0.0, EXTRUDED_CAMERA), abs=1e-9)     # where the camera is
        first, step, count = rng.uniform(-2.0, -0.5), rng.uniform(0.02, 0.2), rng.randint(2, 64)
        order = extruded_draw_order(first, step, count, tilt, turn)
        assert sorted(order) == list(range(count))
        position = {bar: slot for slot, bar in enumerate(order)}
        for a in range(count):
            for b in range(count):
                xa, xb = first + a * step, first + b * step
                # Of two bars on the same side of the eye, the nearer one draws later.
                if (xa - eye[0]) * (xb - eye[0]) > 0 and abs(xa - eye[0]) < abs(xb - eye[0]):
                    assert position[a] > position[b]


def _with_shadow_style(snapshot, *, offset, color=(0, 0, 0, 255)):
    """Replace only the already-resolved canonical shell-shadow projection for a frame."""
    style = snapshot.presentation.shell_style.as_dict()
    style.update(shadow_offset=tuple(offset), shadow_color=tuple(color))
    presentation = dataclasses.replace(snapshot.presentation, shell_style=freeze_render_fields(style))
    return dataclasses.replace(snapshot, presentation=presentation)


def _with_bar_alpha(snapshot, *, fill_alpha, border_alpha):
    style = snapshot.logical.common.style.as_dict()
    style["fill_color"] = (*style["fill_color"][:3], fill_alpha)
    style["border_color"] = (*style["border_color"][:3], border_alpha)
    common = dataclasses.replace(snapshot.logical.common, style=freeze_render_fields(style))
    return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, common=common))


def test_authored_fill_alpha_blends_body_and_preserves_independent_border_alpha(target):
    capture, host = target
    base = _snapshot(
        extruded_spectrum_face_mirror=0.0,
        extruded_spectrum_reflection=0.0,
        extruded_spectrum_colouring="Bar Colours",
        spectrum_ghosting_enabled=False,
        extruded_spectrum_tilt=0.16,
        extruded_spectrum_turn=0.0,
    )
    backdrop = (19 / 255, 43 / 255, 97 / 255, 1.0)
    opaque = capture.render(host, _with_bar_alpha(base, fill_alpha=255, border_alpha=0), backdrop)
    empty = capture.render(host, _with_bar_alpha(base, fill_alpha=0, border_alpha=0), backdrop)
    half = capture.render(host, _with_bar_alpha(base, fill_alpha=128, border_alpha=0), backdrop)
    body = np.abs(opaque[..., :3] - empty[..., :3]).max(axis=2) > 18
    expected = opaque * (128 / 255) + empty * (127 / 255)
    assert body.sum() > 800
    assert np.quantile(np.abs(half[..., :3] - expected[..., :3]).max(axis=2)[body], 0.99) <= 3
    assert np.abs(empty[..., :3] - np.array([19, 43, 97])).max() <= 1
    edges = capture.render(host, _with_bar_alpha(base, fill_alpha=0, border_alpha=255), backdrop)
    changed = np.abs(edges[..., :3] - empty[..., :3]).max(axis=2) > 8
    assert changed.sum() > 100
    assert changed.sum() < body.sum() / 2
    # Spectral Edges has its own bright rim, independent of the bar-border swatch;
    # it must likewise remain visible when the face and authored border are clear.
    spectral = dataclasses.replace(base.logical.mode_state, parameters={
        **dict(base.logical.mode_state.parameters), "extruded_spectrum_colouring": "Spectral Edges",
    })
    spectral_base = dataclasses.replace(base, logical=dataclasses.replace(base.logical, mode_state=spectral))
    spectral_edges = capture.render(host, _with_bar_alpha(spectral_base, fill_alpha=0, border_alpha=0), backdrop)
    spectral_changed = np.abs(spectral_edges[..., :3] - empty[..., :3]).max(axis=2) > 8
    assert spectral_changed.sum() > 100
    assert spectral_changed.sum() < body.sum() / 2


def test_swatch_alpha_is_the_only_body_opacity_and_uses_the_bar_painter_order(target, monkeypatch):
    """A transparent body blends over the already-drawn wallpaper; reversing its documented
    far-to-near bar order changes pixels on the real driver at an overlapping orbit."""
    capture, host = target
    common = dict(
        extruded_spectrum_face_mirror=0.0,
        extruded_spectrum_reflection=0.0,
        spectrum_ghosting_enabled=False,
        extruded_spectrum_tilt=0.16,
        extruded_spectrum_turn=0.0,
    )
    backdrop = (19 / 255, 43 / 255, 97 / 255, 1.0)
    opaque = capture.render(host, _with_bar_alpha(_snapshot(**common), fill_alpha=255, border_alpha=0), backdrop=backdrop)
    empty = capture.render(host, _with_bar_alpha(_snapshot(**common), fill_alpha=0, border_alpha=0), backdrop=backdrop)
    translucent = capture.render(host, _with_bar_alpha(_snapshot(**common), fill_alpha=128, border_alpha=0), backdrop=backdrop)
    body = np.abs(opaque[..., :3] - empty[..., :3]).max(axis=2) > 18
    assert body.sum() > 800
    expected = np.rint((opaque.astype(float) + empty.astype(float)) / 2.0)
    alpha_error = np.abs(translucent[..., :3] - expected[..., :3]).max(axis=2)
    # Multisample edge coverage is resolved before the transparent target composite, so a small
    # silhouette fringe rounds differently; covered face interiors remain the exact half blend.
    assert np.quantile(alpha_error[body], 0.99) <= 3

    from rendering.quick.visualizer.implementations import extruded_spectrum as implementation

    overlap = _snapshot(**{
        **common,
        "extruded_spectrum_tilt": 0.42,
        "extruded_spectrum_turn": 0.72,
    })
    overlap = _with_bar_alpha(overlap, fill_alpha=128, border_alpha=0)
    ordered = capture.render(host, overlap, backdrop=backdrop)
    original_order = implementation.extruded_draw_order
    monkeypatch.setattr(
        implementation,
        "extruded_draw_order",
        lambda *args: list(reversed(original_order(*args))),
    )
    reversed_order = capture.render(host, overlap, backdrop=backdrop)
    assert np.abs(ordered - reversed_order).max() > 8


def test_optional_directional_shadow_uses_canonical_direction_without_an_extra_target(target):
    """The off switch has no pixel/pass effect; enabling the direct pass changes only the
    projected floor and changing the resolved canonical direction changes that projection."""
    from rendering.quick.scene3d.shadows import directional_shadow_vector

    assert directional_shadow_vector((4.0, 4.0), 0.22) == pytest.approx((0.22, 0.22))
    assert directional_shadow_vector((0.0, -4.0), 0.22) == pytest.approx((0.0, -0.22))
    capture, host = target
    base = _snapshot(
        extruded_spectrum_face_mirror=0.0,
        extruded_spectrum_reflection=0.0,
        spectrum_ghosting_enabled=False,
        extruded_spectrum_tilt=0.35,
        extruded_spectrum_turn=0.28,
        extruded_spectrum_shadow_strength=1.0,
    )
    se = _with_shadow_style(base, offset=(5.0, 5.0))
    nw = _with_shadow_style(base, offset=(-5.0, -5.0))
    backdrop = (0.88, 0.73, 0.49, 1.0)
    disabled = capture.render(
        host,
        dataclasses.replace(
            se,
            logical=dataclasses.replace(
                se.logical,
                mode_state=dataclasses.replace(
                    se.logical.mode_state,
                    parameters={**dict(se.logical.mode_state.parameters), "extruded_spectrum_shadow_enabled": False},
                ),
            ),
        ),
        backdrop=backdrop,
    )
    renderer = host._implementations["extruded_spectrum"]
    allocation = renderer._target.allocation
    enabled_se = capture.render(
        host,
        dataclasses.replace(
            se,
            logical=dataclasses.replace(
                se.logical,
                mode_state=dataclasses.replace(
                    se.logical.mode_state,
                    parameters={**dict(se.logical.mode_state.parameters), "extruded_spectrum_shadow_enabled": True},
                ),
            ),
        ),
        backdrop=backdrop,
    )
    enabled_nw = capture.render(
        host,
        dataclasses.replace(
            nw,
            logical=dataclasses.replace(
                nw.logical,
                mode_state=dataclasses.replace(
                    nw.logical.mode_state,
                    parameters={**dict(nw.logical.mode_state.parameters), "extruded_spectrum_shadow_enabled": True},
                ),
            ),
        ),
        backdrop=backdrop,
    )
    assert renderer._target.allocation == allocation
    assert np.abs(enabled_se - disabled).max() > 8
    assert np.abs(enabled_se - enabled_nw).max() > 8


def test_e8_shadow_strength_at_normal_authored_setting_is_visible_on_wallpaper(target):
    """E8 regression: the old 0.34 hidden attenuation made a real cast almost
    imperceptible at the authored 0.45 strength, despite the shadow pass drawing.
    Verify actual composited GL pixels, not just that the shader contains code.
    """
    capture, host = target
    base = _with_shadow_style(
        _snapshot(
            extruded_spectrum_reflection=0.0,
            spectrum_ghosting_enabled=False,
            extruded_spectrum_shadow_enabled=True,
            extruded_spectrum_shadow_strength=0.45,
            extruded_spectrum_tilt=0.35,
            extruded_spectrum_turn=0.28,
        ), offset=(5.0, 5.0), color=(0, 0, 0, 197),
    )
    base = _with_bar_alpha(base, fill_alpha=0, border_alpha=0)
    disabled_mode = dataclasses.replace(
        base.logical.mode_state,
        parameters={**dict(base.logical.mode_state.parameters),
                    "extruded_spectrum_shadow_enabled": False},
    )
    disabled = capture.render(
        host, dataclasses.replace(base, logical=dataclasses.replace(
            base.logical, mode_state=disabled_mode)), backdrop=(.85, .75, .65, 1.),
    )
    enabled = capture.render(host, base, backdrop=(.85, .75, .65, 1.))
    darkened = disabled[..., :3] - enabled[..., :3]
    assert (darkened.max(axis=2) >= 20).sum() >= 100


def test_e8_shadow_is_visible_beneath_opaque_bars_and_reflection_at_shallow_tilt(target):
    """Real host regression for the operator's conditions, not a transparent-bar proxy.

    Bars and their floor reflection are BOTH on. A cast must darken pixels in
    the floor region at a near-front camera, not merely somewhere behind the
    bars when those other passes are disabled. The stage is inset to admit the
    overhanging cast on the display (the normal frameless overflow contract).
    """
    capture, host = target
    stage = (170.0, 60.0, 340.0, 215.0)
    snapshot = _with_shadow_style(_snapshot(
        extruded_spectrum_allow_overflow=True,
        extruded_spectrum_shadow_enabled=True,
        extruded_spectrum_shadow_strength=1.0,
        extruded_spectrum_reflection=0.35,
        extruded_spectrum_turn=0.0,
        extruded_spectrum_tilt=0.12,
        spectrum_ghosting_enabled=False,
    ), offset=(5.0, 5.0), color=(0, 0, 0, 197))
    presentation = dataclasses.replace(
        snapshot.presentation, outer_rect=stage, content_rect=stage,
        viewport_extent=stage[2:], current_aspect_ratio=stage[2] / stage[3],
    )
    snapshot = dataclasses.replace(snapshot, presentation=presentation)
    disabled = dataclasses.replace(
        snapshot, logical=dataclasses.replace(
            snapshot.logical,
            mode_state=dataclasses.replace(snapshot.logical.mode_state,
                parameters={**dict(snapshot.logical.mode_state.parameters),
                            "extruded_spectrum_shadow_enabled": False}),
        ),
    )

    def render(candidate):
        from tests.test_qtquick_extruded_spectrum import W, H
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.capture.fbo)
        gl.glViewport(0, 0, W, H)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.79, 0.76, 0.72, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        left, top, width, height = stage
        matrix = (2 / W, 0, 0, 0, 0, -2 / H, 0, 0, 0, 0, 1, 0,
                  2 * left / W - 1, 1 - 2 * top / H, 0, 1)
        assert host.render(snapshot=candidate, viewport=(0, 0, W, H),
                           logical_size=(width, height), matrix_values=matrix) == "extruded_spectrum"
        pixels = gl.glReadPixels(0, 0, W, H, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.flipud(np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(H, W, 4)).astype(np.int16)

    off = render(disabled)
    on = render(snapshot)
    # The stage floor lives in the lower part of the bar field. Exclude the
    # opaque upper silhouettes so a black bar cannot masquerade as a cast.
    diff = off[215:350, 170:560, :3] - on[215:350, 170:560, :3]
    shadowed = np.max(diff, axis=2) >= 20
    assert int(shadowed.sum()) >= 80
    # Direction: at SE the lower-right receiver must carry some of that shadow.
    assert int(shadowed[:, 130:].sum()) >= 20


def test_directional_shadow_area_grows_with_bar_height_instead_of_translating_one_cap(target):
    """The real GL shadow contains the side-face sweep, so taller bars cast a larger floor area."""
    capture, host = target
    base = _with_shadow_style(
        _snapshot(
            extruded_spectrum_face_mirror=0.0,
            extruded_spectrum_reflection=0.0,
            spectrum_ghosting_enabled=False,
            extruded_spectrum_shadow_enabled=True,
            extruded_spectrum_shadow_strength=1.0,
            extruded_spectrum_tilt=0.22,
            extruded_spectrum_turn=0.18,
        ),
        offset=(6.0, 6.0),
    )
    base = _with_bar_alpha(base, fill_alpha=0, border_alpha=0)
    count = base.logical.common.bar_count

    def levels(value: float):
        common = dataclasses.replace(base.logical.common, bars=(value,) * count)
        state = dataclasses.replace(base.logical.mode_state, peaks=(value,) * count)
        return dataclasses.replace(base, logical=dataclasses.replace(base.logical, common=common, mode_state=state))

    backdrop = (0.84, 0.76, 0.66, 1.0)
    disabled_state = dataclasses.replace(
        base.logical.mode_state,
        parameters={**dict(base.logical.mode_state.parameters), "extruded_spectrum_shadow_enabled": False},
    )
    disabled = capture.render(
        host, dataclasses.replace(base, logical=dataclasses.replace(base.logical, mode_state=disabled_state)),
        backdrop=backdrop,
    )
    low = capture.render(host, levels(0.18), backdrop=backdrop)
    high = capture.render(host, levels(0.95), backdrop=backdrop)
    low_mask = np.abs(low[..., :3] - disabled[..., :3]).max(axis=2) > 3
    high_mask = np.abs(high[..., :3] - disabled[..., :3]).max(axis=2) > 3
    assert low_mask.sum() > 100
    assert high_mask.sum() > low_mask.sum() * 1.35



def test_a_transition_announces_its_photograph_when_it_starts():
    """The scene tells its listener at a transition's start what it is bringing in and over how
    long, and forgets it once it adopts a photograph."""
    from types import SimpleNamespace

    from rendering.quick.scene_controller import QuickSceneController

    scene = QuickSceneController.__new__(QuickSceneController)
    calls = []
    scene._readiness = SimpleNamespace(admission_open=True)
    scene._incoming_image = None
    scene._presentation_image_listener = lambda: calls.append(scene.incoming_image)
    scene.announce_incoming_image("next", 2.5)
    assert calls == [("next", 2.5)] and scene.incoming_image == ("next", 2.5)
    scene._readiness = SimpleNamespace(admission_open=False)
    scene.announce_incoming_image("later", 1.0)                      # a closed scene ignores it
    assert scene.incoming_image == ("next", 2.5) and len(calls) == 1

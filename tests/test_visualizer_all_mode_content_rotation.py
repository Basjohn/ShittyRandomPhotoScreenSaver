"""Real renderer outputs turn rigidly at their logical aspect; the physical stage never changes."""
from dataclasses import replace

import numpy as np
import pytest
from OpenGL import GL as gl

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy, iter_visualizer_mode_descriptors
from rendering.quick.offscreen_target import OffscreenRenderTarget
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tests._visualizer_presentation import resolve_presentation
from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

MODES = [pytest.param(d.mode_id, False, id=d.mode_id) for d in iter_visualizer_mode_descriptors()
         if d.mode_id != "sphere"] + [pytest.param("extruded_spectrum", True, id="extruded_spectrum_overflow")]

SCENES = [d.mode_id for d in iter_visualizer_mode_descriptors() if d.mode_id != "sphere" and d.view_orbit_settings]


@pytest.mark.qt
@pytest.mark.parametrize("mode,overflow", MODES)
def test_each_renderer_turns_pixels_at_swapped_aspect_with_the_same_camera_and_world(qt_app, mode, overflow):
    target = OffscreenRenderTarget(352, 352)
    host = QuickVisualizerRenderHost()
    try:
        settings = frozen_visualizer_settings(mode)
        if mode == "oscilloscope":
            # Screen-space analogue grain is intentionally unrelated to content geometry.
            settings.update(osc_analog=0.0, osc_glow=0.0)
        if overflow:
            settings.update(extruded_spectrum_allow_overflow=True, extruded_spectrum_depth=0.8,
                            extruded_spectrum_turn=0.65, extruded_spectrum_tilt=-0.3)
        snapshot = _build_spectrum_preview_snapshot(width=240, height=160, mode=mode, settings=settings)
        if overflow:
            snapshot = replace(snapshot, logical=replace(snapshot.logical, common=replace(
                snapshot.logical.common, bars=(1.0,) * snapshot.logical.common.bar_count)))
        logical = snapshot.logical
        state = logical.mode_state

        def draw(width, height, quarter):
            origin = (16, 96) if overflow and not quarter else (16, 16)
            world = ((128, 408) if not quarter else (408, 128)) if overflow else (width, height)
            presentation = resolve_presentation(policy=get_visualizer_presentation_policy(mode),
                display_size=(352, 352), outer_origin=origin, viewport_extent=world,
                committed_outer_size=(width, height) if overflow else None,
                uniform_visual_scale=0.65 if overflow else 1.0, content_rotation_quarters=quarter)
            frame = replace(snapshot, presentation=presentation)
            target.bind()
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0, 0, 0, 0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            matrix = (2/352, 0, 0, 0, 0, -2/352, 0, 0, 0, 0, 1, 0,
                      -1+2*origin[0]/352, 1-2*origin[1]/352, 0, 1)
            host.render(snapshot=frame, viewport=(0, 0, 352, 352), logical_size=(float(width), float(height)),
                        matrix_values=matrix)
            pixels = target.read_rgba()
            assert frame.logical is logical and frame.logical.mode_state is state
            assert frame.presentation.outer_rect == (*origin, width, height)
            return (pixels if overflow else pixels[16:16+height, 16:16+width]).astype(np.int16)

        reference = draw(160, 240, 0)
        rotated = draw(240, 160, 1)
        expected = np.rot90(reference, -1)
        difference = np.abs(rotated - expected)
        # Shared integer-texel remapping is exact in its dedicated GL gate. The real modes also rasterise meshes,
        # whose multisample edge coverage may turn with a different sample order; interiors must stay the same.
        assert (reference[..., 3] > 0).sum() > 30
        assert float(difference.mean()) < 0.8, (mode, difference.max(), difference.mean())
        assert float((difference.max(axis=2) > 10).mean()) < 0.01, mode
        assert logical.mode_state is state
        if overflow:
            outside = rotated[..., 3] > 0
            outside[16:176, 16:256] = False
            assert outside.sum() > 30  # The reach frame really draws past its frameless stage and clips at the window.
    finally:
        target.make_current()
        host.release_resources()
        target.close()


@pytest.mark.qt
@pytest.mark.parametrize("mode", SCENES)
def test_active_quarter_turn_is_prepared_before_its_visible_frame(qt_app, monkeypatch, mode):
    from rendering.quick.scene3d import resources
    from rendering.quick.visualizer.implementation_registry import resolve_quick_visualizer_renderer
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame

    target = OffscreenRenderTarget(352, 352)
    renderer = resolve_quick_visualizer_renderer(mode)
    try:
        snapshot = _build_spectrum_preview_snapshot(width=240, height=160, mode=mode,
                                                     settings=frozen_visualizer_settings(mode))
        presentation = resolve_presentation(policy=get_visualizer_presentation_policy(mode),
            display_size=(352, 352), outer_origin=(16, 16), viewport_extent=(240, 160), content_rotation_quarters=1)
        frame = QuickVisualizerRenderFrame(snapshot=replace(snapshot, presentation=presentation),
            viewport=(0, 0, 352, 352), logical_size=(240.0, 160.0), quad_vao=target.vao,
            matrix_values=(2/352, 0, 0, 0, 0, -2/352, 0, 0, 0, 0, 1, 0, -1+32/352, 1-32/352, 0, 1))
        for _ in range(200):
            if renderer.prepare_step(frame):
                break
        else:
            pytest.fail("the scene did not finish its bounded preparation")

        def forbidden(*_args, **_kwargs):
            pytest.fail("a prepared turned scene compiled or allocated on its visible frame")

        with monkeypatch.context() as gate:
            gate.setattr(resources, "compile_program", forbidden)
            gate.setattr(resources, "compile_compute_program", forbidden)
            for name in ("glCreateProgram", "glCreateShader", "glCreateTextures", "glCreateBuffers",
                         "glCreateVertexArrays", "glCreateFramebuffers"):
                gate.setattr(gl, name, forbidden)
            target.bind()
            renderer.render(frame)
            assert (target.read_rgba()[..., 3] > 0).sum() > 30
    finally:
        target.make_current()
        renderer.release_resources()
        target.close()


@pytest.mark.parametrize("mode", [d.mode_id for d in iter_visualizer_mode_descriptors()])
def test_studio_frame_builders_explicitly_declare_unrotated_content(qt_app, mode):
    from ui.studio.adapter import RenderCard
    from ui.studio.registry import create_adapter
    from rendering.quick.scene3d.frame import orient_visualizer_scene_frame

    renderer = create_adapter(mode).create_renderer()
    card = RenderCard(viewport=(0, 0, 240, 160), logical_size=(240.0, 160.0),
                      matrix_values=(2/240, 0, 0, 0, 0, -2/160, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1), quad_vao=1)
    try:
        frame = renderer._frame(card, object())
        assert frame.content_rotation_quarters == frame.scene_output_rotation == 0
        assert frame.scene_output_viewport is None
        assert orient_visualizer_scene_frame(frame) is frame
        assert not renderer._impl.has_resources  # Contract assembly must not need a GL allocation.
    finally:
        renderer.release()

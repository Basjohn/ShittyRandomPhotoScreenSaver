"""Lazy Quick renderer for Cube Turn: the picture is a box that turns to show the next one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.cube_turn_program import (
    CUBE_TURN_BACKDROP_FRAGMENT_SOURCE,
    CUBE_TURN_FRAGMENT_SOURCE,
    CUBE_TURN_VERTEX_SOURCE,
    cube_turn_axis,
    cube_turn_lift,
    cube_turn_state,
)
from rendering.gl_programs.scene3d import SCENE3D_BOX_ATTRIBUTES, SCENE3D_BOX_VERTICES, scene3d_request_samples
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..render_contract import QuickTransitionRenderFrame


def cube_turn_parameters(parameters: Mapping[str, object]) -> float:
    """The resolved gloss, validated before any GL state changes."""
    gloss = parameters.get("gloss")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Cube Turn needs a resolved gloss between 0 and 1")
    return float(gloss)


class QuickCubeTurnRenderer:
    transition_id = "cube_turn"

    _BOX_UNIFORMS = ("uMatrix", "uItemSize", "uAngle", "uFinal", "uAxis", "uZoom", "uOldTex", "uNewTex",
                     "uEnvironment", "uGloss", "uLift")
    _BACKDROP_UNIFORMS = ("uMatrix", "uItemSize", "uEnvironment")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Cube Turn")
        self._target = SceneTarget("Quick Cube Turn")
        self._environment = PhotoEnvironment("Quick Cube Turn")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._environment.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        axis, sign = cube_turn_axis(str(frame.run.request.direction))
        parameters = frame.run.request.parameter_dict()
        gloss = cube_turn_parameters(parameters)
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            samples = scene3d_request_samples(parameters)
            environment = self._environment.texture(frame, self._resources)
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw(frame, progress, axis, sign, gloss, environment)
            else:
                self._draw(frame, progress, axis, sign, gloss, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        cube_turn_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "backdrop", ITEM_QUAD_VERTEX_SOURCE, CUBE_TURN_BACKDROP_FRAGMENT_SOURCE),
                   (r, "box", CUBE_TURN_VERTEX_SOURCE, CUBE_TURN_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        if not r.has_mesh("box"):
            r.mesh("box", SCENE3D_BOX_VERTICES, SCENE3D_BOX_ATTRIBUTES)
            return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and environment; programs and the box stay warm."""
        self._target.release()
        self._environment.release()

    def _draw(self, frame, progress: float, axis: int, sign: float, gloss: float, environment: int) -> None:
        angle, zoom = cube_turn_state(progress, sign)
        r = self._resources
        program = r.program("backdrop", ITEM_QUAD_VERTEX_SOURCE, CUBE_TURN_BACKDROP_FRAGMENT_SOURCE)
        uniforms = r.uniforms("backdrop", self._BACKDROP_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        r.begin_depth(frame)
        program = r.program("box", CUBE_TURN_VERTEX_SOURCE, CUBE_TURN_FRAGMENT_SOURCE)
        uniforms = r.uniforms("box", self._BOX_UNIFORMS)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uAngle"], angle)
        gl.glUniform1f(uniforms["uFinal"], sign * 1.5707963267948966)
        gl.glUniform1i(uniforms["uAxis"], axis)
        gl.glUniform1f(uniforms["uZoom"], zoom)
        gl.glUniform1f(uniforms["uGloss"], gloss)
        gl.glUniform1f(uniforms["uLift"], cube_turn_lift(angle))
        gl.glUniform1i(uniforms["uEnvironment"], 2)      # still bound on unit 2
        vao, vertices = r.mesh("box", SCENE3D_BOX_VERTICES, SCENE3D_BOX_ATTRIBUTES)
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertices)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickCubeTurnRenderer:
    return QuickCubeTurnRenderer()

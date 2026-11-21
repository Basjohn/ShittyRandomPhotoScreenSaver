"""Lazy Quick renderer for Cube Turn: the picture is a box that turns to show the next one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.cube_turn_program import (
    CUBE_TURN_BACKDROP_BLOCK,
    CUBE_TURN_BACKDROP_FRAGMENT_SOURCE,
    CUBE_TURN_BACKDROP_VERTEX_SOURCE,
    CUBE_TURN_BLOCK,
    CUBE_TURN_FRAGMENT_SOURCE,
    CUBE_TURN_VERTEX_SOURCE,
    cube_turn_axis,
    cube_turn_lift,
    cube_turn_state,
)
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import SCENE3D_BOX_ATTRIBUTES, SCENE3D_BOX_VERTICES, scene3d_request_samples
from rendering.quick.scene3d.environment import (PHOTO_ENVIRONMENT_MIPS_PROGRAM, PHOTO_ENVIRONMENT_PROGRAM,
                                                 PhotoEnvironment)
from rendering.quick.scene3d.resources import (UNDERLAY_PROGRAM, MeshResources, bind_frame, pack_floats, warm_programs,
                                               warm_pass_blocks)
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..native_scene import (native_clip_depth, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show,
                            item_quad_pass)
from ..render_contract import QuickTransitionRenderFrame

#: N5.2c: the box's attributes by name (``SCENE3D_BOX_ATTRIBUTES``' order: position, outward normal).
_BOX_INPUTS = (("aPosition", 3), ("aNormal", 3))
_SCENE_PASSES = (
    item_quad_pass("backdrop", CUBE_TURN_BACKDROP_VERTEX_SOURCE, CUBE_TURN_BACKDROP_FRAGMENT_SOURCE,
                   (("uEnvironment", "environment"),)),
    NativeScenePass("box", native_clip_depth(CUBE_TURN_VERTEX_SOURCE), CUBE_TURN_FRAGMENT_SOURCE, mesh="box",
                    samplers=(("uOldTex", "old"), ("uNewTex", "new"), ("uEnvironment", "environment")), depth=True),
)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def cube_turn_parameters(parameters: Mapping[str, object]) -> float:
    """The resolved gloss, validated before any GL state changes."""
    gloss = parameters.get("gloss")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Cube Turn needs a resolved gloss between 0 and 1")
    return float(gloss)


class QuickCubeTurnRenderer(NativeScenePasses):
    transition_id = "cube_turn"

    _BOX_SAMPLERS = ("uOldTex", "uNewTex")   # every other value is in the programs' pass blocks

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Cube Turn")
        self._target = SceneTarget("Quick Cube Turn")
        self._environment = PhotoEnvironment("Quick Cube Turn")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._environment.has_resources

    # ------------------------------------------------------------------------------- N5.2c: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        cube_turn_parameters(parameters)
        box = NativeSceneMesh("box", pack_floats(SCENE3D_BOX_VERTICES), _BOX_INPUTS)
        return NativeScene(_SCENE_PASSES, (box,), scene3d_request_samples(parameters), True)

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample))

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        """The box's values for the frame (the backdrop's are the core's: the matrix and the item size)."""
        axis, sign = cube_turn_axis(str(run.request.direction))
        gloss = cube_turn_parameters(run.request.parameter_dict())
        angle, zoom = cube_turn_state(_progress(sample), sign)
        return {"uAngle": angle, "uFinal": sign * 1.5707963267948966, "uAxis": axis, "uZoom": zoom, "uGloss": gloss,
                "uLift": cube_turn_lift(angle)}

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = _progress(frame.sample)
        cube_turn_axis(str(frame.run.request.direction))
        parameters = frame.run.request.parameter_dict()
        cube_turn_parameters(parameters)
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
                    self._draw(frame, environment)
            else:
                self._draw(frame, environment)
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
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM), (r, *PHOTO_ENVIRONMENT_MIPS_PROGRAM),
                   (r, "backdrop", CUBE_TURN_BACKDROP_VERTEX_SOURCE, CUBE_TURN_BACKDROP_FRAGMENT_SOURCE),
                   (r, "box", CUBE_TURN_VERTEX_SOURCE, CUBE_TURN_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        if not r.has_mesh("box"):
            r.mesh("box", SCENE3D_BOX_VERTICES, SCENE3D_BOX_ATTRIBUTES)
            return False
        if not warm_pass_blocks(self._resources, size):
            return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and environment; programs and the box stay warm."""
        self._target.release()
        self._environment.release()

    def _draw(self, frame, environment: int) -> None:
        r = self._resources
        program = r.program("backdrop", CUBE_TURN_BACKDROP_VERTEX_SOURCE, CUBE_TURN_BACKDROP_FRAGMENT_SOURCE)
        uniforms = r.uniforms("backdrop", ())
        values = r.values("backdrop")
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame, values)
        gl.glActiveTexture(gl.GL_TEXTURE2)                # the environment's binding in both programs
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        with r.pass_blocks.bound(pack_block(CUBE_TURN_BACKDROP_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        r.begin_depth(frame)
        program = r.program("box", CUBE_TURN_VERTEX_SOURCE, CUBE_TURN_FRAGMENT_SOURCE)
        uniforms = r.uniforms("box", self._BOX_SAMPLERS)
        values = r.values("box")
        bind_frame(program, uniforms, frame, values)
        values.update(self.scene_values(frame.run, frame.sample, frame.logical_size))   # the one owner (N5.2c)
        vao, vertices = r.mesh("box", SCENE3D_BOX_VERTICES, SCENE3D_BOX_ATTRIBUTES)
        with r.pass_blocks.bound(pack_block(CUBE_TURN_BLOCK, values)):
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

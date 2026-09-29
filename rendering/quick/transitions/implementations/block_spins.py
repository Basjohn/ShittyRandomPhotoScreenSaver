"""Lazy Quick renderer for the authored single-slab 3D BlockSpin effect."""

from __future__ import annotations

import ctypes
import math

from OpenGL import GL as gl

from rendering.gl_programs.blockspin_program import (
    BLOCK_SPIN_BOX_VERTEX_COUNT,
    BLOCK_SPIN_BOX_VERTICES,
    BLOCK_SPIN_FRAGMENT_SOURCE,
    BLOCK_SPIN_GHOST_FRAGMENT_SOURCE,
    BLOCK_SPIN_MOTION_FRAGMENT_SOURCE,
    BLOCK_SPIN_MOTION_VERTEX_SOURCE,
    BLOCK_SPIN_QUICK_VERTEX_SOURCE,
    BLOCK_SPIN_VERTEX_STRIDE_FLOATS,
    block_spin_edge_glass_mode,
    block_spin_progress,
)
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.motion import motion_uniform_names, set_motion_uniforms
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, trail_program
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_DIRECTION_STATES = {
    "left": (0, 1.0),
    "right": (0, -1.0),
    "up": (1, 1.0),
    "down": (1, -1.0),
    "diag_tl_br": (2, 1.0),
    "diag_tr_bl": (3, -1.0),
}


_VOID_FRAGMENT_SOURCE = """#version 410 core
out vec4 FragColor;

void main() {
    FragColor = vec4(0.0, 0.0, 0.0, 1.0);
}
"""


def _block_spin_direction_state(direction: object) -> tuple[int, float]:
    value = str(direction).strip().lower()
    state = _DIRECTION_STATES.get(value)
    if state is None:
        raise ValueError(f"unknown resolved 3D Block Spins direction: {direction!r}")
    return state


class QuickBlockSpinsRenderer:
    transition_id = "block_spins"

    def __init__(self) -> None:
        self._void_program = 0
        self._slab_program = 0
        self._box_vao = 0
        self._box_vbo = 0
        self._void_uniforms: dict[str, int] = {}
        self._slab_uniforms: dict[str, int] = {}
        # The scene target (anti-aliasing, motion blur), its composite and the slab's
        # motion-writing variant.
        self._target = SceneTarget("Quick 3D Block Spins")
        self._target_resources = MeshResources("Quick 3D Block Spins")
        # Edge Glass reflections: the next image as a per-run blurred environment.
        self._environment = PhotoEnvironment("Quick 3D Block Spins")
        self._trails = MotionTrails("Quick 3D Block Spins")

    @property
    def has_resources(self) -> bool:
        return bool(
            self._void_program
            or self._slab_program
            or self._box_vao
            or self._box_vbo
            or self._target.has_resources
            or self._target_resources.has_resources
            or self._environment.has_resources
            or self._trails.has_resources
        )

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._slab_program:
            self._initialize()
        parameters = frame.run.request.parameter_dict()
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        edge_glass = block_spin_edge_glass_mode(parameters.get("edge_glass", "Off"))
        # Reflection and Both read the next image's environment (copied once per run).
        environment = self._environment.texture(frame, self._target_resources) if edge_glass in (1, 3) else 0
        if samples:
            with self._target.scope(frame, samples, self._target_resources, motion_blur=motion):
                self._draw_scene(frame, edge_glass, motion, environment, trails)
        else:
            self._draw_scene(frame, edge_glass, False, environment)

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        r = self._target_resources
        if not warm_programs(self._base_programs()):
            return False
        if not self._box_vao:
            self._initialize()   # the slab mesh and uniform lookups (its programs are compiled)
            return False
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        entries = []
        if motion:
            entries.append((r, "slab_motion", BLOCK_SPIN_MOTION_VERTEX_SOURCE, BLOCK_SPIN_MOTION_FRAGMENT_SOURCE))
        if trails:
            entries += [(r, "slab_ghost", BLOCK_SPIN_MOTION_VERTEX_SOURCE, BLOCK_SPIN_GHOST_FRAGMENT_SOURCE),
                        (r, *TRAIL_EDGES_PROGRAM)]
        if block_spin_edge_glass_mode(parameters.get("edge_glass", "Off")) in (1, 3):
            entries.append((r, *PHOTO_ENVIRONMENT_PROGRAM))
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, motion)]
        if not warm_programs(entries):
            return False
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion,
                                  bloom=False, with_trails=trails)

    def _base_programs(self):
        r = self._target_resources
        return ((r, "void", QUICK_TRANSITION_VERTEX_SOURCE, _VOID_FRAGMENT_SOURCE),
                (r, "slab", BLOCK_SPIN_QUICK_VERTEX_SOURCE, BLOCK_SPIN_FRAGMENT_SOURCE))

    def park(self) -> None:
        """Drop the per-run target, environment and trails; programs and the slab stay warm."""
        self._target.release()
        self._environment.release()
        self._trails.release()

    def _draw_scene(self, frame: QuickTransitionRenderFrame, edge_glass: int, motion: bool,
                    environment: int, trails: bool = False) -> None:
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glUseProgram(self._void_program)
        gl.glUniformMatrix4fv(
            self._void_uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(
            self._void_uniforms["uItemSize"],
            *frame.logical_size,
        )
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        if trails:
            now = frame.sample.eased_progress
            self._trails.draw(self._target, frame, self._target_resources,
                              scene3d_trail_ghosts(now, frame.run.request.duration_ms),
                              lambda time, fade: self._draw_slab(frame, time, edge_glass, False, environment,
                                                                 (fade, now)))

        gl.glDepthMask(gl.GL_TRUE)
        gl.glClearDepth(1.0)
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        self._draw_slab(frame, frame.sample.eased_progress, edge_glass, motion, environment)

    def _draw_slab(self, frame: QuickTransitionRenderFrame, progress: float, edge_glass: int, motion: bool,
                   environment: int, ghost: tuple[float, float] | None = None) -> None:
        """``ghost``: (fade, the moment now) to draw the slab as a motion-trail ghost."""
        axis_mode, spin_direction = _block_spin_direction_state(
            frame.run.request.direction
        )
        spin = block_spin_progress(progress)
        uniforms = self._slab_uniforms
        program = self._slab_program
        if ghost is not None:
            program, uniforms = trail_program(self._target_resources, "slab", BLOCK_SPIN_MOTION_VERTEX_SOURCE,
                                              BLOCK_SPIN_GHOST_FRAGMENT_SOURCE,
                                              tuple(self._slab_uniforms) + motion_uniform_names("uAngle"))
        elif motion:
            program = self._target_resources.program("slab_motion", BLOCK_SPIN_MOTION_VERTEX_SOURCE,
                                                     BLOCK_SPIN_MOTION_FRAGMENT_SOURCE)
            uniforms = self._target_resources.uniforms("slab_motion", tuple(self._slab_uniforms)
                                                       + motion_uniform_names("uAngle"))
        gl.glUseProgram(program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["uAngle"],
            math.pi * spin * spin_direction,
        )
        gl.glUniform1f(uniforms["uSpecDirection"], spin_direction)
        gl.glUniform1i(uniforms["uAxisMode"], axis_mode)
        gl.glUniform1i(uniforms["uEdgeGlass"], edge_glass)
        if ghost is not None:
            gl.glUniform1f(uniforms["uGhostFade"], ghost[0])
            set_motion_uniforms(uniforms, frame, math.pi * block_spin_progress(ghost[1]) * spin_direction, "uAngle")
        if motion:
            # The slab's angle one shutter ago.
            before = max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0)
            set_motion_uniforms(uniforms, frame, math.pi * block_spin_progress(before) * spin_direction, "uAngle")
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTexture"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTexture"], 1)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindVertexArray(self._box_vao)
        with self._target.velocity_writes():
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, BLOCK_SPIN_BOX_VERTEX_COUNT)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._trails.release,
                        self._target_resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(f"scene target:{type(exc).__name__}:{exc}")
        # The void and slab programs belong to the resources released above.
        if not self._target_resources.has_program("slab"):
            self._slab_program = 0
        if not self._target_resources.has_program("void"):
            self._void_program = 0
        for attribute, delete in (
            ("_box_vbo", lambda value: gl.glDeleteBuffers(1, [value])),
            ("_box_vao", lambda value: gl.glDeleteVertexArrays(1, [value])),
        ):
            value = int(getattr(self, attribute))
            if not value:
                continue
            try:
                delete(value)
            except Exception as exc:
                errors.append(f"{attribute}:{type(exc).__name__}:{exc}")
            else:
                setattr(self, attribute, 0)
        if not self._slab_program:
            self._slab_uniforms.clear()
        if not self._void_program:
            self._void_uniforms.clear()
        if errors:
            raise RuntimeError(
                "Quick 3D Block Spins cleanup incomplete: " + " | ".join(errors)
            )

    def _initialize(self) -> None:
        try:
            (void_resources, *void), (slab_resources, *slab) = self._base_programs()
            self._void_program = void_resources.program(*void)
            self._slab_program = slab_resources.program(*slab)
            self._void_uniforms = self._uniform_locations(
                self._void_program,
                ("uMatrix", "uItemSize"),
            )
            self._slab_uniforms = self._uniform_locations(
                self._slab_program,
                (
                    "uMatrix",
                    "uItemSize",
                    "uAngle",
                    "uSpecDirection",
                    "uAxisMode",
                    "uEdgeGlass",
                    "uOldTexture",
                    "uNewTexture",
                    "uEnvironment",
                ),
            )

            vertex_data = (ctypes.c_float * len(BLOCK_SPIN_BOX_VERTICES))(
                *BLOCK_SPIN_BOX_VERTICES
            )
            self._box_vao = int(gl.glGenVertexArrays(1))
            self._box_vbo = int(gl.glGenBuffers(1))
            if not self._box_vao or not self._box_vbo:
                raise RuntimeError("Quick 3D Block Spins box allocation failed")
            gl.glBindVertexArray(self._box_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._box_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                ctypes.sizeof(vertex_data),
                vertex_data,
                gl.GL_STATIC_DRAW,
            )
            stride = BLOCK_SPIN_VERTEX_STRIDE_FLOATS * ctypes.sizeof(
                ctypes.c_float
            )
            for location, size, offset in (
                (0, 3, 0),
                (1, 3, 3 * ctypes.sizeof(ctypes.c_float)),
                (2, 2, 6 * ctypes.sizeof(ctypes.c_float)),
            ):
                gl.glEnableVertexAttribArray(location)
                gl.glVertexAttribPointer(
                    location,
                    size,
                    gl.GL_FLOAT,
                    gl.GL_FALSE,
                    stride,
                    ctypes.c_void_p(offset),
                )
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindVertexArray(0)
        except Exception:
            self.release_resources()
            raise

    @staticmethod
    def _uniform_locations(
        program: int,
        names: tuple[str, ...],
    ) -> dict[str, int]:
        uniforms = {
            name: int(gl.glGetUniformLocation(program, name)) for name in names
        }
        missing = [name for name, location in uniforms.items() if location < 0]
        if missing:
            raise RuntimeError(
                "Quick 3D Block Spins uniforms are incomplete: "
                + ", ".join(missing)
            )
        return uniforms


def create_transition_renderer() -> QuickBlockSpinsRenderer:
    return QuickBlockSpinsRenderer()

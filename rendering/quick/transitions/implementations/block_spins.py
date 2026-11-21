"""Lazy Quick renderer for the authored single-slab 3D BlockSpin effect."""

from __future__ import annotations

import ctypes
import math

from OpenGL import GL as gl

from rendering.gl_programs.blockspin_program import (
    BLOCK_SPIN_BLOCK,
    BLOCK_SPIN_BOX_VERTEX_COUNT,
    BLOCK_SPIN_BOX_VERTICES,
    BLOCK_SPIN_FRAGMENT_SOURCE,
    BLOCK_SPIN_GHOST_FRAGMENT_SOURCE,
    BLOCK_SPIN_MOTION_BLOCK,
    BLOCK_SPIN_MOTION_FRAGMENT_SOURCE,
    BLOCK_SPIN_MOTION_VERTEX_SOURCE,
    BLOCK_SPIN_QUICK_VERTEX_SOURCE,
    BLOCK_SPIN_SAMPLERS,
    BLOCK_SPIN_VERTEX_STRIDE_FLOATS,
    block_spin_edge_glass_mode,
    block_spin_progress,
)
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import (
    SCENE3D_TRAIL_GHOSTS,
    scene3d_request_samples,
    scene3d_shutter_progress,
    scene3d_trail_ghosts,
)
from rendering.quick.scene3d.environment import (PHOTO_ENVIRONMENT_MIPS_PROGRAM, PHOTO_ENVIRONMENT_PROGRAM,
                                                 PhotoEnvironment)
from rendering.quick.scene3d.motion import motion_program, set_motion_values
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, draw_ghosts, trail_program
from rendering.quick.scene3d.resources import MeshResources, warm_pass_blocks, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from rendering.gl_programs.item_quad import item_quad_program
from rendering.quick.scene3d.resources import pack_floats
from ..native_scene import (SHOW_EFFECT, TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass,
                            NativeScenePasses, ghost_values, item_quad_pass, native_clip_depth)
from ..render_contract import QuickTransitionRenderFrame


_DIRECTION_STATES = {
    "left": (0, 1.0),
    "right": (0, -1.0),
    "up": (1, 1.0),
    "down": (1, -1.0),
    "diag_tl_br": (3, 1.0),
    "diag_tr_bl": (2, 1.0),
}


_VOID_FRAGMENT_SOURCE = """#version 460 core
out vec4 FragColor;

void main() {
    FragColor = vec4(0.0, 0.0, 0.0, 1.0);
}
"""
# N1.6: the void is drawn over the item quad, its values (the quad's) one std140 pass block.
_VOID_VERTEX_SOURCE, _VOID_FRAGMENT_SOURCE, _VOID_BLOCK = item_quad_program(
    _VOID_FRAGMENT_SOURCE, block="BlockSpinsVoid", samplers={})


def _block_spin_direction_state(direction: object) -> tuple[int, float]:
    value = str(direction).strip().lower()
    state = _DIRECTION_STATES.get(value)
    if state is None:
        raise ValueError(f"unknown resolved 3D Block Spins direction: {direction!r}")
    return state


# N5.2d: the native scene's passes (their texts the ones this renderer compiles); the slab's mesh by name.
_SLAB_INPUTS = (("aPosition", 3), ("aNormal", 3), ("aUv", 2))
_SLAB_SAMPLERS = (("uOldTexture", "old"), ("uNewTexture", "new"), ("uEnvironment", "environment"))
# The slab's stages write their own clip depth (``native_clip_depth``).
_SLAB_VERTEX = native_clip_depth(BLOCK_SPIN_QUICK_VERTEX_SOURCE)
_SLAB_MOTION_VERTEX = native_clip_depth(BLOCK_SPIN_MOTION_VERTEX_SOURCE)
_SCENE_PASSES = (
    item_quad_pass("void", _VOID_VERTEX_SOURCE, _VOID_FRAGMENT_SOURCE),
    NativeScenePass("slab_ghost", _SLAB_MOTION_VERTEX, BLOCK_SPIN_GHOST_FRAGMENT_SOURCE, mesh="slab",
                    samplers=_SLAB_SAMPLERS, target="ghosts"),
    TRAIL_EDGES_PASS,
    NativeScenePass("slab", _SLAB_VERTEX, BLOCK_SPIN_FRAGMENT_SOURCE, mesh="slab", samplers=_SLAB_SAMPLERS,
                    depth=True),
    NativeScenePass("slab_motion", _SLAB_MOTION_VERTEX, BLOCK_SPIN_MOTION_FRAGMENT_SOURCE, mesh="slab",
                    samplers=_SLAB_SAMPLERS, depth=True, moves=True),
)


def _scene_pass(name: str) -> NativeScenePass:
    return next(p for p in _SCENE_PASSES if p.name == name)


def _without_environment(scene_pass: NativeScenePass) -> NativeScenePass:
    """Edge Glass Off or Refraction reads no environment (Python binds none): its sampler bound to the new picture,
    which the shader then never reads (``uEdgeGlass`` 0 or 2)."""
    from dataclasses import replace

    return replace(scene_pass, samplers=tuple((name, "new" if kind == "environment" else kind)
                                              for name, kind in scene_pass.samplers))


class QuickBlockSpinsRenderer(NativeScenePasses):
    transition_id = "block_spins"
    scene_pixels = True                  # N5.2d: its motion reads the item's device pixels (uViewport)

    # ------------------------------------------------------------------------------- N5.2d: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        _block_spin_direction_state(run.request.direction)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        reflections = block_spin_edge_glass_mode(parameters.get("edge_glass", "Off")) in (1, 3)
        names = ["void"] + (["slab_ghost", TRAIL_EDGES_PASS.name] if trails else []) + [
            "slab_motion" if motion else "slab"]
        passes = tuple(p if reflections or p.core_triangle else _without_environment(p)
                       for p in map(_scene_pass, names))
        slab = NativeSceneMesh("slab", pack_floats(BLOCK_SPIN_BOX_VERTICES), _SLAB_INPUTS)
        return NativeScene(passes, (slab,), samples, reflections, motion=motion, trails=trails)

    def scene_show(self, run, sample) -> int:
        return SHOW_EFFECT                   # the slab is drawn at every progress (its faces are the photographs)

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """The slab's values for the frame (``render``'s, one owner): its turn, and with motion blur its turn one
        shutter ago; with trails each ghost's turn and fade (``<member>@slab_ghost_<k>``)."""
        parameters = run.request.parameter_dict()
        axis_mode, spin_direction = _block_spin_direction_state(run.request.direction)
        progress = float(sample.eased_progress)
        angle = lambda time: math.pi * block_spin_progress(time) * spin_direction  # noqa: E731
        values: dict[str, object] = {
            "uSpecDirection": spin_direction, "uAxisMode": axis_mode,
            "uEdgeGlass": block_spin_edge_glass_mode(parameters.get("edge_glass", "Off")), "uAngle": angle(progress)}
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        if motion or trails:
            width, height = pixels if pixels is not None else logical_size
            values["uViewport"] = (float(width), float(height))
        if motion:
            before = max(progress - scene3d_shutter_progress(run.request.duration_ms), 0.0)
            values["uAngleBefore"] = angle(before)
            values["uGhostFade@slab_motion"] = 0.0      # the shared motion block's ghost member, read by no stage here
        if trails:
            values.update(ghost_values("slab_ghost", scene3d_trail_ghosts(progress, run.request.duration_ms), "uAngle",
                                       lambda time: {"uAngle": angle(time)}, progress))
        return values

    def __init__(self) -> None:
        self._void_program = 0
        self._slab_program = 0
        self._box_vao = 0
        self._box_vbo = 0
        # The scene target (anti-aliasing, motion blur), its composite and the slab's
        # motion-writing variant. A ghost pass gives each of its draws its own pass block copy.
        self._target = SceneTarget("Quick 3D Block Spins")
        self._target_resources = MeshResources("Quick 3D Block Spins", copies=SCENE3D_TRAIL_GHOSTS)
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
        reflections = block_spin_edge_glass_mode(parameters.get("edge_glass", "Off")) in (1, 3)
        if reflections:
            entries += [(r, *PHOTO_ENVIRONMENT_PROGRAM), (r, *PHOTO_ENVIRONMENT_MIPS_PROGRAM)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, motion)]
        if not warm_programs(entries):
            return False
        # The void (and the photo environment's copy) draws through these resources' pass blocks.
        if not warm_pass_blocks(r, size):
            return False
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion,
                                  bloom=False, with_trails=trails)

    def _base_programs(self):
        r = self._target_resources
        return ((r, "void", _VOID_VERTEX_SOURCE, _VOID_FRAGMENT_SOURCE),
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
        with self._target_resources.pass_blocks.bound(_VOID_BLOCK.pack({"uMatrix": frame.matrix_values,
                                                                        "uItemSize": frame.logical_size})):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        if trails:
            now = frame.sample.eased_progress
            self._trails.draw(self._target, frame, self._target_resources,
                              scene3d_trail_ghosts(now, frame.run.request.duration_ms),
                              lambda ghosts: self._draw_slab_ghosts(frame, ghosts, edge_glass, environment, now))

        gl.glDepthMask(gl.GL_TRUE)
        gl.glClearDepth(1.0)
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        self._draw_slab(frame, frame.sample.eased_progress, edge_glass, motion, environment)

    @staticmethod
    def _slab_values(values: dict, frame: QuickTransitionRenderFrame, edge_glass: int) -> float:
        """The slab's invariant values into its pass-block ``values``; returns its spin direction."""
        axis_mode, spin_direction = _block_spin_direction_state(frame.run.request.direction)
        values["uMatrix"] = frame.matrix_values
        values["uItemSize"] = frame.logical_size
        values["uSpecDirection"] = spin_direction
        values["uAxisMode"] = axis_mode
        values["uEdgeGlass"] = edge_glass
        return spin_direction

    @staticmethod
    def _bind_textures(frame: QuickTransitionRenderFrame, environment: int) -> None:
        """The photographs and the environment on the units the slab's sources bind (0, 1, 2)."""
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def _draw_slab(self, frame: QuickTransitionRenderFrame, progress: float, edge_glass: int, motion: bool,
                   environment: int) -> None:
        r = self._target_resources
        program, _samplers, values, block = motion_program(
            r, "slab", (BLOCK_SPIN_QUICK_VERTEX_SOURCE, BLOCK_SPIN_FRAGMENT_SOURCE, BLOCK_SPIN_BLOCK),
            (BLOCK_SPIN_MOTION_VERTEX_SOURCE, BLOCK_SPIN_MOTION_FRAGMENT_SOURCE, BLOCK_SPIN_MOTION_BLOCK),
            tuple(BLOCK_SPIN_SAMPLERS), motion)
        gl.glUseProgram(program)
        spin_direction = self._slab_values(values, frame, edge_glass)
        values["uAngle"] = math.pi * block_spin_progress(progress) * spin_direction
        if motion:
            # The slab's angle one shutter ago.
            before = max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0)
            set_motion_values(values, frame, math.pi * block_spin_progress(before) * spin_direction, "uAngle")
        self._bind_textures(frame, environment)
        gl.glBindVertexArray(self._box_vao)
        with self._target.velocity_writes(), r.pass_blocks.bound(pack_block(block, values)):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, BLOCK_SPIN_BOX_VERTEX_COUNT)

    def _draw_slab_ghosts(self, frame: QuickTransitionRenderFrame, ghosts, edge_glass: int, environment: int,
                          now: float) -> None:
        """One ghost pass: static slab state once, then each ghost's angle and fade."""
        r = self._target_resources
        program, _samplers = trail_program(
            r, "slab", BLOCK_SPIN_MOTION_VERTEX_SOURCE, BLOCK_SPIN_GHOST_FRAGMENT_SOURCE, tuple(BLOCK_SPIN_SAMPLERS))
        gl.glUseProgram(program)
        values = r.values("slab_ghost")
        spin_direction = self._slab_values(values, frame, edge_glass)
        set_motion_values(values, frame, math.pi * block_spin_progress(now) * spin_direction, "uAngle")
        self._bind_textures(frame, environment)
        gl.glBindVertexArray(self._box_vao)
        with self._target.velocity_writes():
            draw_ghosts(r.pass_blocks, BLOCK_SPIN_MOTION_BLOCK, values, ghosts,
                        lambda time: {"uAngle": math.pi * block_spin_progress(time) * spin_direction},
                        lambda: gl.glDrawArrays(gl.GL_TRIANGLES, 0, BLOCK_SPIN_BOX_VERTEX_COUNT))

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
        if errors:
            raise RuntimeError(
                "Quick 3D Block Spins cleanup incomplete: " + " | ".join(errors)
            )

    def _initialize(self) -> None:
        try:
            (void_resources, *void), (slab_resources, *slab) = self._base_programs()
            self._void_program = void_resources.program(*void)   # its values: _VOID_BLOCK
            self._slab_program = slab_resources.program(*slab)   # its values: BLOCK_SPIN_BLOCK

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


def create_transition_renderer() -> QuickBlockSpinsRenderer:
    return QuickBlockSpinsRenderer()

"""Lazy closed-solid Crumble renderer with static instanced debris."""

from __future__ import annotations
import ctypes
from OpenGL import GL as gl
from rendering.gl_programs.crumble_program import (
    CRUMBLE_BLOCK,
    CRUMBLE_CHIP_VERTICES,
    CRUMBLE_FRAGMENT,
    CRUMBLE_GHOST_FRAGMENT,
    CRUMBLE_MOTION_BLOCK,
    CRUMBLE_MOTION_FRAGMENT,
    CRUMBLE_MOTION_VERTEX,
    CRUMBLE_VERTEX,
    DEBRIS_BLOCK,
    DEBRIS_FRAGMENT,
    DEBRIS_GHOST_FRAGMENT,
    DEBRIS_MOTION_BLOCK,
    DEBRIS_MOTION_FRAGMENT,
    DEBRIS_MOTION_VERTEX,
    DEBRIS_VERTEX,
)
from ..crumble_dynamics import MOTION_FRAMES
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import (
    SCENE3D_TRAIL_GHOSTS,
    scene3d_request_samples,
    scene3d_shutter_progress,
    scene3d_trail_ghosts,
)
from rendering.quick.scene3d.motion import motion_program, set_motion_values
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, draw_ghosts, trail_program
from rendering.quick.scene3d.resources import (UNDERLAY_PROGRAM, MeshResources, bind_frame, pack_floats, warm_programs,
                                               warm_pass_blocks)
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..native_scene import (TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses,
                            NativeSceneTexture, eased_show, ghost_values, item_quad_pass, native_clip_depth)
from ..render_contract import QuickTransitionRenderFrame
from ..run_geometry import (
    CRUMBLE_CHUNK_ATTRIBUTES,
    CRUMBLE_DEBRIS_STRIDE,
    PREPARED_GEOMETRY,
    CrumbleGeometry,
    build_crumble_geometry,
    crumble_geometry_key,
    crumble_parameters,
)


# N5.2d: the native scene's passes (their texts the ones this renderer compiles, each vertex stage with its native clip
# depth); the chunks' and the chips' meshes by name. Chunks read the old picture and the motion table (nearest).
_CHUNK_INPUTS = tuple(zip(("aUv", "aCenter", "aZ", "aNormal", "aInset", "aFace", "aVariation", "aRadius", "aCrack",
                           "aRelease", "aAxis"), CRUMBLE_CHUNK_ATTRIBUTES))
_CHIP_INPUTS = (("aPosition", 3), ("aNormal", 3))
_CHIP_INSTANCE_INPUTS = (("aEdge", 2), ("aParent", 2), ("aMeta", 2), ("aRelease", 2))
_NATIVE_CHUNK_SAMPLERS = (("uOldTex", "old"), ("uMotion", "motion"))
_SCENE_PASSES = (
    item_quad_pass("underlay", UNDERLAY_PROGRAM[1], UNDERLAY_PROGRAM[2], (("uImage", "new"),)),
    NativeScenePass("chunks_ghost", native_clip_depth(CRUMBLE_MOTION_VERTEX), CRUMBLE_GHOST_FRAGMENT, mesh="chunks",
                    samplers=_NATIVE_CHUNK_SAMPLERS, target="ghosts"),
    NativeScenePass("debris_ghost", native_clip_depth(DEBRIS_MOTION_VERTEX), DEBRIS_GHOST_FRAGMENT, mesh="chips",
                    instances="mesh", target="ghosts"),
    TRAIL_EDGES_PASS,
    NativeScenePass("chunks", native_clip_depth(CRUMBLE_VERTEX), CRUMBLE_FRAGMENT, mesh="chunks",
                    samplers=_NATIVE_CHUNK_SAMPLERS, depth=True),
    NativeScenePass("chunks_motion", native_clip_depth(CRUMBLE_MOTION_VERTEX), CRUMBLE_MOTION_FRAGMENT, mesh="chunks",
                    samplers=_NATIVE_CHUNK_SAMPLERS, depth=True, moves=True),
    NativeScenePass("debris", native_clip_depth(DEBRIS_VERTEX), DEBRIS_FRAGMENT, mesh="chips", instances="mesh",
                    depth=True),
    NativeScenePass("debris_motion", native_clip_depth(DEBRIS_MOTION_VERTEX), DEBRIS_MOTION_FRAGMENT, mesh="chips",
                    instances="mesh", depth=True, moves=True),
)


def _scene_pass(name: str) -> NativeScenePass:
    return next(p for p in _SCENE_PASSES if p.name == name)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def _run_geometry(run, logical_size: tuple[float, float]) -> CrumbleGeometry:
    """The run's prepared geometry (COMPUTE's, ``prepare_run_geometry``; built here when it has not prepared it)."""
    key = crumble_geometry_key(run.request.parameter_dict(), logical_size[0] / logical_size[1])
    return PREPARED_GEOMETRY.get_or_build(key, build_crumble_geometry)


class QuickCrumbleRenderer(NativeScenePasses):
    transition_id = "crumble"
    scene_pixels = True                  # N5.2d: its motion reads the item's device pixels (uViewport)

    # ------------------------------------------------------------------------------- N5.2d: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        debris = crumble_parameters(parameters)[6]
        geometry = _run_geometry(run, logical_size)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        chips = debris > 0.0 and bool(geometry.debris)
        names = ["underlay"]
        if trails:                       # _draw_scene: the ghosts (MAX into their buffer) and their edges first
            names += ["chunks_ghost"] + (["debris_ghost"] if chips else []) + [TRAIL_EDGES_PASS.name]
        names += ["chunks_motion" if motion else "chunks"]
        if chips:
            names += ["debris_motion" if motion else "debris"]
        meshes = [NativeSceneMesh("chunks", bytes(geometry.chunks), _CHUNK_INPUTS)]
        if chips:
            meshes.append(NativeSceneMesh("chips", pack_floats(CRUMBLE_CHIP_VERTICES), _CHIP_INPUTS,
                                          bytes(geometry.debris), _CHIP_INSTANCE_INPUTS))
        table = NativeSceneTexture("motion", bytes(geometry.motion), (MOTION_FRAMES, geometry.chunk_count))
        return NativeScene(tuple(map(_scene_pass, names)), tuple(meshes), samples, False, motion=motion,
                           trails=trails, textures=(table,))

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample))

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """The chunks' and chips' values for the frame (``render``'s, one owner): their time, and with motion blur
        their time one shutter ago; with trails each ghost's time and fade (``<member>@<pass>_<k>``)."""
        parameters = run.request.parameter_dict()
        seed, _pieces, _complexity, _weight, depth, thickness, debris = crumble_parameters(parameters)
        progress = _progress(sample)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        values: dict[str, object] = {"uProgress": progress, "uDepth": depth, "uThickness": thickness, "uSeed": seed,
                                     "uMotionFrames": float(MOTION_FRAMES)}
        if debris > 0.0:
            values["uDebris"] = debris
        if motion or trails:
            width, height = pixels if pixels is not None else logical_size
            values["uViewport"] = (float(width), float(height))
        chips = ("debris",) if debris > 0.0 else ()
        if motion:
            values["uProgressBefore"] = max(progress - scene3d_shutter_progress(run.request.duration_ms), 0.0)
            for name in ("chunks", *chips):         # the shared motion blocks' ghost member, read by no stage here
                values[f"uGhostFade@{name}_motion"] = 0.0
        if trails:
            ghosts = scene3d_trail_ghosts(progress, run.request.duration_ms)
            for name in (f"{piece}_ghost" for piece in ("chunks", *chips)):
                values.update(ghost_values(name, ghosts, "uProgress", lambda time: {"uProgress": time}, progress))
        return values

    def __init__(self) -> None:
        # A ghost pass gives each of its draws its own pass block copy.
        self._resources = MeshResources("Quick Crumble", copies=SCENE3D_TRAIL_GHOSTS)
        self._target = SceneTarget("Quick Crumble")
        self._trails = MotionTrails("Quick Crumble")
        self._geometry_key = None
        self._chunk_vao = self._chunk_count = self._debris_vbo = self._debris_count = 0
        self._motion_texture = 0

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._trails.has_resources
                or bool(self._debris_vbo) or bool(self._motion_texture))

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            parameters = frame.run.request.parameter_dict()
            seed, _pieces, _complexity, _weight, depth, thickness, debris = (
                crumble_parameters(parameters)
            )
            aspect = frame.logical_size[0] / frame.logical_size[1]
            geometry_key = crumble_geometry_key(parameters, aspect)
            if geometry_key != self._geometry_key:
                # Identical keys are identical bytes: a run whose geometry the warm-up uploaded
                # (or a previous run had) draws it as it is.
                self._rebuild_geometry(
                    PREPARED_GEOMETRY.get_or_build(geometry_key, build_crumble_geometry)
                )
                self._geometry_key = geometry_key
            motion = bool(parameters.get("motion_blur", False))
            trails = bool(parameters.get("motion_trails", False))
            samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
            # With motion blur, where the chunks and chips were one shutter ago.
            before = max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0) if motion else None
            if samples:
                with self._target.scope(frame, samples, self._resources, motion_blur=motion):
                    self._draw_scene(frame, progress, seed, depth, thickness, debris, before, trails)
            else:
                self._draw_scene(frame, progress, seed, depth, thickness, debris, None)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing. The chunks, motion table and debris
        upload once COMPUTE has prepared them (``prepare_run_geometry``); the render thread
        never builds them here."""
        debris = crumble_parameters(parameters)[6]
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM),
                   (r, "chunks_motion", CRUMBLE_MOTION_VERTEX, CRUMBLE_MOTION_FRAGMENT) if motion
                   else (r, "chunks", CRUMBLE_VERTEX, CRUMBLE_FRAGMENT)]
        if debris > 0.0:
            entries.append((r, "debris_motion", DEBRIS_MOTION_VERTEX, DEBRIS_MOTION_FRAGMENT) if motion
                           else (r, "debris", DEBRIS_VERTEX, DEBRIS_FRAGMENT))
        if trails:
            entries += [(r, "chunks_ghost", CRUMBLE_MOTION_VERTEX, CRUMBLE_GHOST_FRAGMENT), (r, *TRAIL_EDGES_PROGRAM)]
            if debris > 0.0:
                entries.append((r, "debris_ghost", DEBRIS_MOTION_VERTEX, DEBRIS_GHOST_FRAGMENT))
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, motion)]
        if not warm_programs(entries):
            return False
        if size and size[0] > 0 and size[1] > 0:
            key = crumble_geometry_key(parameters, size[0] / size[1])
            if key != self._geometry_key:
                geometry = PREPARED_GEOMETRY.get(key)
                if geometry is not None:
                    self._rebuild_geometry(geometry)
                    self._geometry_key = key
                    return False
        if not warm_pass_blocks(self._resources, size):
            return False
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion,
                                  bloom=False, with_trails=trails)

    def _draw_scene(self, frame, progress, seed, depth, thickness, debris, before, trails=False) -> None:
        self._resources.draw_image(frame, frame.destination_texture_id)
        if trails:
            self._trails.draw(self._target, frame, self._resources,
                              scene3d_trail_ghosts(progress, frame.run.request.duration_ms),
                              lambda ghosts: self._draw_ghosts(frame, ghosts, seed, depth, thickness, debris, progress))
        self._resources.begin_depth(frame)
        self._draw_chunks(frame, progress, seed, depth, thickness, before)
        if debris > 0.0:
            self._draw_debris(frame, progress, depth, debris, before)

    def park(self) -> None:
        """Drop the per-run scene target and trails; programs and geometry stay warm."""
        self._target.release()
        self._trails.release()

    def _rebuild_geometry(self, geometry: CrumbleGeometry) -> None:
        self._resources.drop_mesh("chunks")
        if self._debris_vbo:
            gl.glDeleteBuffers(1, [self._debris_vbo])
            self._debris_vbo = 0
        self._chunk_vao, self._chunk_count = self._resources.mesh(
            "chunks", geometry.chunks, CRUMBLE_CHUNK_ATTRIBUTES
        )
        self._upload_motion(geometry)
        if not geometry.debris:
            self._debris_count = 0
            self._resources.drop_mesh("debris_chip")
            return
        vao, _ = self._resources.mesh("debris_chip", CRUMBLE_CHIP_VERTICES, (3, 3))
        float_count = len(geometry.debris) // 4
        self._debris_count = float_count // CRUMBLE_DEBRIS_STRIDE
        self._debris_vbo = int(gl.glGenBuffers(1))
        if not self._debris_vbo:
            raise RuntimeError("Quick Crumble debris allocation failed")
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._debris_vbo)
        # Plain bytes: a per-run ``c_float * n`` type would be cached forever.
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER, len(geometry.debris), geometry.debris, gl.GL_STATIC_DRAW
        )
        for location, offset in ((2, 0), (3, 2), (4, 4), (5, 6)):
            gl.glEnableVertexAttribArray(location)
            gl.glVertexAttribPointer(
                location, 2, gl.GL_FLOAT, gl.GL_FALSE, CRUMBLE_DEBRIS_STRIDE * 4,
                ctypes.c_void_p(offset * 4),
            )
            gl.glVertexAttribDivisor(location, 1)

    def _upload_motion(self, geometry: CrumbleGeometry) -> None:
        """One RGBA32F row of keyframes per chunk; texel-fetched, never filtered.

        Uploaded on unit 1, which the chunk program does not otherwise use and
        which the transition host restores after every frame.
        """
        if not self._motion_texture:
            self._motion_texture = int(gl.glGenTextures(1))
            if not self._motion_texture:
                raise RuntimeError("Quick Crumble motion table allocation failed")
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._motion_texture)
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_NEAREST)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, MOTION_FRAMES, geometry.chunk_count, 0,
            gl.GL_RGBA, gl.GL_FLOAT, geometry.motion,
        )
        gl.glActiveTexture(gl.GL_TEXTURE0)

    # The old picture bind_frame binds (unit 0; the motion table is bound on unit 1 here); every other value is in
    # the programs' pass blocks.
    _CHUNK_SAMPLERS = ("uOldTex",)

    def _chunk_values(self, values: dict, seed, depth, thickness) -> None:
        """The chunks' invariant values into the pass-block ``values``, and the motion table on unit 1."""
        values["uDepth"] = depth
        values["uThickness"] = thickness
        values["uSeed"] = seed
        values["uMotionFrames"] = float(MOTION_FRAMES)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._motion_texture)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def _draw_chunks(self, frame, progress, seed, depth, thickness, before) -> None:
        # Release order and motion are per-chunk attributes; uSeed only varies
        # the crack stroke timing in the fragment stage.
        program, u, values, block = motion_program(
            self._resources, "chunks", (CRUMBLE_VERTEX, CRUMBLE_FRAGMENT, CRUMBLE_BLOCK),
            (CRUMBLE_MOTION_VERTEX, CRUMBLE_MOTION_FRAGMENT, CRUMBLE_MOTION_BLOCK), self._CHUNK_SAMPLERS,
            before is not None,
        )
        bind_frame(program, u, frame, values)
        values["uProgress"] = progress
        self._chunk_values(values, seed, depth, thickness)
        if before is not None:
            set_motion_values(values, frame, before)
        gl.glBindVertexArray(self._chunk_vao)
        with self._target.velocity_writes(), self._resources.pass_blocks.bound(pack_block(block, values)):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._chunk_count)

    def _draw_debris(self, frame, progress, depth, debris, before) -> None:
        program, u, values, block = motion_program(
            self._resources, "debris", (DEBRIS_VERTEX, DEBRIS_FRAGMENT, DEBRIS_BLOCK),
            (DEBRIS_MOTION_VERTEX, DEBRIS_MOTION_FRAGMENT, DEBRIS_MOTION_BLOCK), (), before is not None,
        )
        bind_frame(program, u, frame, values)
        values["uProgress"] = progress
        values["uDepth"] = depth
        values["uDebris"] = debris
        if before is not None:
            set_motion_values(values, frame, before)
        vao, count = self._resources.mesh("debris_chip", CRUMBLE_CHIP_VERTICES, (3, 3))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes(), self._resources.pass_blocks.bound(pack_block(block, values)):
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, self._debris_count)

    def _draw_ghosts(self, frame, ghosts, seed: float, depth: float, thickness: float, debris: float,
                     now: float) -> None:
        """Group MAX-blended ghosts by program so each variant's invariant state binds once."""
        ghosts = tuple(ghosts)
        self._draw_chunk_ghosts(frame, ghosts, seed, depth, thickness, now)
        if debris > 0.0:
            self._draw_debris_ghosts(frame, ghosts, depth, debris, now)

    def _draw_chunk_ghosts(self, frame, ghosts, seed: float, depth: float, thickness: float, now: float) -> None:
        r = self._resources
        program, uniforms = trail_program(r, "chunks", CRUMBLE_MOTION_VERTEX, CRUMBLE_GHOST_FRAGMENT,
                                          self._CHUNK_SAMPLERS)
        values = r.values("chunks_ghost")
        bind_frame(program, uniforms, frame, values)
        self._chunk_values(values, seed, depth, thickness)
        set_motion_values(values, frame, now)
        gl.glBindVertexArray(self._chunk_vao)
        with self._target.velocity_writes():
            draw_ghosts(r.pass_blocks, CRUMBLE_MOTION_BLOCK, values, ghosts, lambda time: {"uProgress": time},
                        lambda: gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._chunk_count))

    def _draw_debris_ghosts(self, frame, ghosts, depth: float, debris: float, now: float) -> None:
        r = self._resources
        program, uniforms = trail_program(r, "debris", DEBRIS_MOTION_VERTEX, DEBRIS_GHOST_FRAGMENT, ())
        values = r.values("debris_ghost")
        bind_frame(program, uniforms, frame, values)
        values["uDepth"] = depth
        values["uDebris"] = debris
        set_motion_values(values, frame, now)
        vao, count = r.mesh("debris_chip", CRUMBLE_CHIP_VERTICES, (3, 3))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes():
            draw_ghosts(r.pass_blocks, DEBRIS_MOTION_BLOCK, values, ghosts, lambda time: {"uProgress": time},
                        lambda: gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, self._debris_count))

    def release_resources(self) -> None:
        errors = []
        for release in (self._target.release, self._trails.release):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if self._debris_vbo:
            try:
                gl.glDeleteBuffers(1, [self._debris_vbo])
            except Exception as exc:
                errors.append(f"debris instances: {exc}")
            else:
                self._debris_vbo = 0
        if self._motion_texture:
            try:
                gl.glDeleteTextures(1, [self._motion_texture])
            except Exception as exc:
                errors.append(f"motion table: {exc}")
            else:
                self._motion_texture = 0
        try:
            self._resources.release_resources()
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise RuntimeError(
                f"Quick Crumble cleanup incomplete: {' | '.join(errors)}"
            )
        self._geometry_key = None
        self._chunk_vao = self._chunk_count = self._debris_count = 0


def create_transition_renderer() -> QuickCrumbleRenderer:
    return QuickCrumbleRenderer()

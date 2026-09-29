"""Lazy closed-solid Crumble renderer with static instanced debris."""

from __future__ import annotations
import ctypes
from OpenGL import GL as gl
from rendering.gl_programs.crumble_program import (
    CRUMBLE_CHIP_VERTICES,
    CRUMBLE_FRAGMENT,
    CRUMBLE_GHOST_FRAGMENT,
    CRUMBLE_MOTION_FRAGMENT,
    CRUMBLE_MOTION_VERTEX,
    CRUMBLE_VERTEX,
    DEBRIS_FRAGMENT,
    DEBRIS_GHOST_FRAGMENT,
    DEBRIS_MOTION_FRAGMENT,
    DEBRIS_MOTION_VERTEX,
    DEBRIS_VERTEX,
)
from ..crumble_dynamics import MOTION_FRAMES
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.motion import motion_program, motion_uniform_names, set_motion_uniforms
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, trail_program
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
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


class QuickCrumbleRenderer:
    transition_id = "crumble"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Crumble")
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
            key = (frame.run.run_id, geometry_key)
            if key != self._geometry_key:
                self._rebuild_geometry(
                    PREPARED_GEOMETRY.get_or_build(geometry_key, build_crumble_geometry)
                )
                self._geometry_key = key
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
        render ``size`` in device pixels, allocate nothing."""
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
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion,
                                  bloom=False, with_trails=trails)

    def _draw_scene(self, frame, progress, seed, depth, thickness, debris, before, trails=False) -> None:
        self._resources.draw_image(frame, frame.destination_texture_id)
        if trails:
            def ghost(time, fade):
                self._draw_chunks(frame, time, seed, depth, thickness, None, (fade, progress))
                if debris > 0.0:
                    self._draw_debris(frame, time, depth, debris, None, (fade, progress))
            self._trails.draw(self._target, frame, self._resources,
                              scene3d_trail_ghosts(progress, frame.run.request.duration_ms), ghost)
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

    _CHUNK_UNIFORMS = (
        "uMatrix", "uItemSize", "uOldTex", "uProgress", "uDepth", "uThickness", "uSeed", "uMotion", "uMotionFrames",
    )
    _DEBRIS_UNIFORMS = ("uMatrix", "uItemSize", "uProgress", "uDepth", "uDebris")

    def _draw_chunks(self, frame, progress, seed, depth, thickness, before, ghost=None) -> None:
        # Release order and motion are per-chunk attributes; uSeed only varies
        # the crack stroke timing in the fragment stage.
        if ghost is not None:   # (fade, the moment now): a motion-trail ghost
            program, u = trail_program(self._resources, "chunks", CRUMBLE_MOTION_VERTEX, CRUMBLE_GHOST_FRAGMENT,
                                       self._CHUNK_UNIFORMS + motion_uniform_names())
        else:
            program, u = motion_program(
                self._resources, "chunks", (CRUMBLE_VERTEX, CRUMBLE_FRAGMENT),
                (CRUMBLE_MOTION_VERTEX, CRUMBLE_MOTION_FRAGMENT), self._CHUNK_UNIFORMS, before is not None,
            )
        bind_frame(program, u, frame)
        for name, value in (
            ("uProgress", progress),
            ("uDepth", depth),
            ("uThickness", thickness),
            ("uSeed", seed),
            ("uMotionFrames", float(MOTION_FRAMES)),
        ):
            gl.glUniform1f(u[name], value)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._motion_texture)
        gl.glUniform1i(u["uMotion"], 1)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        if ghost is not None:
            gl.glUniform1f(u["uGhostFade"], ghost[0])
            set_motion_uniforms(u, frame, ghost[1])
        if before is not None:
            set_motion_uniforms(u, frame, before)
        gl.glBindVertexArray(self._chunk_vao)
        with self._target.velocity_writes():
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._chunk_count)

    def _draw_debris(self, frame, progress, depth, debris, before, ghost=None) -> None:
        if ghost is not None:   # (fade, the moment now): a motion-trail ghost
            program, u = trail_program(self._resources, "debris", DEBRIS_MOTION_VERTEX, DEBRIS_GHOST_FRAGMENT,
                                       self._DEBRIS_UNIFORMS + motion_uniform_names())
        else:
            program, u = motion_program(
                self._resources, "debris", (DEBRIS_VERTEX, DEBRIS_FRAGMENT),
                (DEBRIS_MOTION_VERTEX, DEBRIS_MOTION_FRAGMENT), self._DEBRIS_UNIFORMS, before is not None,
            )
        bind_frame(program, u, frame)
        for name, value in (
            ("uProgress", progress),
            ("uDepth", depth),
            ("uDebris", debris),
        ):
            gl.glUniform1f(u[name], value)
        if ghost is not None:
            gl.glUniform1f(u["uGhostFade"], ghost[0])
            set_motion_uniforms(u, frame, ghost[1])
        if before is not None:
            set_motion_uniforms(u, frame, before)
        vao, count = self._resources.mesh("debris_chip", CRUMBLE_CHIP_VERTICES, (3, 3))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes():
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, self._debris_count)

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

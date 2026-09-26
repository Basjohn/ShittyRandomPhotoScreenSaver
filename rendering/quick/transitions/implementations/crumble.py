"""Lazy closed-solid Crumble renderer with static instanced debris."""

from __future__ import annotations
import ctypes
from OpenGL import GL as gl
from rendering.gl_programs.crumble_program import (
    CRUMBLE_CHIP_VERTICES,
    CRUMBLE_FRAGMENT,
    CRUMBLE_VERTEX,
    DEBRIS_FRAGMENT,
    DEBRIS_VERTEX,
)
from ..crumble_dynamics import MOTION_FRAMES
from ..mesh_support import MeshResources, bind_frame
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
        self._geometry_key = None
        self._chunk_vao = self._chunk_count = self._debris_vbo = self._debris_count = 0
        self._motion_texture = 0

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or bool(self._debris_vbo) or bool(self._motion_texture)

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
            self._resources.draw_image(frame, frame.destination_texture_id)
            self._resources.begin_depth(frame)
            self._draw_chunks(frame, progress, seed, depth, thickness)
            if debris > 0.0:
                self._draw_debris(frame, progress, depth, debris)
        except Exception:
            self.release_resources()
            raise

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

    def _draw_chunks(self, frame, progress, seed, depth, thickness) -> None:
        program = self._resources.program("chunks", CRUMBLE_VERTEX, CRUMBLE_FRAGMENT)
        # Release order and motion are per-chunk attributes; uSeed only varies
        # the crack stroke timing in the fragment stage.
        u = self._resources.uniforms(
            "chunks",
            (
                "uMatrix",
                "uItemSize",
                "uOldTex",
                "uProgress",
                "uDepth",
                "uThickness",
                "uSeed",
                "uMotion",
                "uMotionFrames",
            ),
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
        gl.glBindVertexArray(self._chunk_vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._chunk_count)

    def _draw_debris(self, frame, progress, depth, debris) -> None:
        program = self._resources.program("debris", DEBRIS_VERTEX, DEBRIS_FRAGMENT)
        u = self._resources.uniforms(
            "debris",
            (
                "uMatrix",
                "uItemSize",
                "uProgress",
                "uDepth",
                "uDebris",
            ),
        )
        bind_frame(program, u, frame)
        for name, value in (
            ("uProgress", progress),
            ("uDepth", depth),
            ("uDebris", debris),
        ):
            gl.glUniform1f(u[name], value)
        vao, count = self._resources.mesh("debris_chip", CRUMBLE_CHIP_VERTICES, (3, 3))
        gl.glBindVertexArray(vao)
        gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, self._debris_count)

    def release_resources(self) -> None:
        errors = []
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

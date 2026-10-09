"""Lazy Quick renderer for Jigsaw Piece Flip: jigsaw pieces flip over one by one to the next picture."""

from __future__ import annotations

from collections.abc import Mapping
import math

import numpy as np
from OpenGL import GL as gl

from rendering.gl_programs.jigsaw_options import JIGSAW_ORDERS, JIGSAW_PIECES_RANGE
from rendering.gl_programs.jigsaw_program import (
    JIGSAW_FLAT_FRAGMENT_SOURCE,
    JIGSAW_FLAT_VERTEX_SOURCE,
    JIGSAW_FLIGHT_FRAGMENT_SOURCE,
    JIGSAW_FLIGHT_VERTEX_SOURCE,
    JIGSAW_HOP,
    JIGSAW_SHADOW_FRAGMENT_SOURCE,
    JIGSAW_SHADOW_VERTEX_SOURCE,
    JIGSAW_THICKNESS,
)
from rendering.gl_programs.scene3d import scene3d_detail, scene3d_request_samples
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.passes import blend_scope
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..piece_layout import PIECE_VERTEX_ATTRIBUTES
from ..render_contract import QuickTransitionRenderFrame
from ..run_geometry import PREPARED_GEOMETRY, build_jigsaw_geometry, jigsaw_geometry_key

_ORDER_CODES = frozenset(JIGSAW_ORDERS.values())


def jigsaw_parameters(parameters: Mapping[str, object]) -> tuple[int, int, str]:
    """The resolved seed, piece count and order, validated before any GL state changes."""
    seed, pieces, order = parameters.get("seed"), parameters.get("pieces"), parameters.get("order")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Jigsaw Piece Flip seed must be an integer between 1 and 65535")
    low, high = JIGSAW_PIECES_RANGE
    if isinstance(pieces, bool) or not isinstance(pieces, int) or not low <= pieces <= high:
        raise ValueError(f"Jigsaw Piece Flip pieces must be an integer between {low} and {high}")
    if order not in _ORDER_CODES:
        raise ValueError(f"unknown resolved Jigsaw Piece Flip order: {order!r}")
    return seed, pieces, str(order)


def _shadows(parameters: Mapping[str, object]) -> bool:
    return scene3d_detail(parameters.get("detail", "High")).shadows


class QuickJigsawRenderer:
    transition_id = "jigsaw"

    _FLAT_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uProgress", "uCount", "uPieces")
    _MOTION_UNIFORMS = ("uProgress", "uCount", "uPieces", "uThick", "uRadius", "uHop")
    _FLIGHT_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uEnvironment") + _MOTION_UNIFORMS
    _SHADOW_UNIFORMS = ("uMatrix", "uItemSize", "uCell") + _MOTION_UNIFORMS

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Jigsaw Piece Flip")
        self._target = SceneTarget("Quick Jigsaw Piece Flip")
        self._environment = PhotoEnvironment("Quick Jigsaw Piece Flip")
        self._geometry_key = None
        self._geometry = None
        self._pieces = np.zeros(0, dtype=np.float32)
        self._vao = self._count = 0

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._environment.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        parameters = frame.run.request.parameter_dict()
        jigsaw_parameters(parameters)
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            aspect = frame.logical_size[0] / frame.logical_size[1]
            self._upload(jigsaw_geometry_key(parameters, aspect), build=True)
            samples = scene3d_request_samples(parameters)
            environment = self._environment.texture(frame, self._resources)
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw(frame, progress, aspect, environment, _shadows(parameters))
            else:
                self._draw(frame, progress, aspect, environment, _shadows(parameters))
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing. The pieces upload once COMPUTE has
        prepared them (``prepare_run_geometry``); the render thread never builds them here."""
        jigsaw_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "flat", JIGSAW_FLAT_VERTEX_SOURCE, JIGSAW_FLAT_FRAGMENT_SOURCE),
                   (r, "flight", JIGSAW_FLIGHT_VERTEX_SOURCE, JIGSAW_FLIGHT_FRAGMENT_SOURCE)]
        if _shadows(parameters):
            entries.append((r, "shadow", JIGSAW_SHADOW_VERTEX_SOURCE, JIGSAW_SHADOW_FRAGMENT_SOURCE))
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        if size and size[0] > 0 and size[1] > 0:
            key = jigsaw_geometry_key(parameters, size[0] / size[1])
            if key != self._geometry_key and self._upload(key, build=False):
                return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target, environment and pieces; programs stay warm."""
        self._target.release()
        self._environment.release()
        self._drop_pieces()

    def _upload(self, key: tuple, *, build: bool) -> bool:
        """Hold the pieces for ``key``: True when this call uploaded them. Without ``build`` only
        prepared pieces are taken."""
        if key == self._geometry_key:
            return False
        if build:
            geometry = PREPARED_GEOMETRY.get_or_build(key, build_jigsaw_geometry)
        else:
            geometry = PREPARED_GEOMETRY.get(key)
            if geometry is None:
                return False
        self._drop_pieces()
        self._vao, self._count = self._resources.mesh("pieces", geometry.vertices, PIECE_VERTEX_ATTRIBUTES)
        self._geometry, self._geometry_key = geometry, key
        self._pieces = np.frombuffer(geometry.pieces, dtype=np.float32)
        return True

    def _drop_pieces(self) -> None:
        self._resources.drop_mesh("pieces")
        self._geometry_key = self._geometry = None
        self._pieces = np.zeros(0, dtype=np.float32)
        self._vao = self._count = 0

    def _motion_uniforms(self, uniforms, progress: float, aspect: float) -> None:
        geometry = self._geometry
        cell_w, cell_h = aspect / geometry.cols, 1.0 / geometry.rows
        knob = min(cell_w, cell_h)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1i(uniforms["uCount"], geometry.count)
        gl.glUniform4fv(uniforms["uPieces"], geometry.count, self._pieces)
        if "uCell" in uniforms:
            gl.glUniform2f(uniforms["uCell"], cell_w, cell_h)
        if "uThick" in uniforms:
            gl.glUniform1f(uniforms["uThick"], JIGSAW_THICKNESS * knob)
            gl.glUniform1f(uniforms["uRadius"], 0.5 * math.hypot(cell_w, cell_h) + 0.3 * knob)
            gl.glUniform1f(uniforms["uHop"], JIGSAW_HOP * knob)

    def _draw(self, frame, progress: float, aspect: float, environment: int, shadows: bool) -> None:
        r, geometry = self._resources, self._geometry
        # The pieces where they rest: old picture, board, or new picture, with the cut lines.
        program = r.program("flat", JIGSAW_FLAT_VERTEX_SOURCE, JIGSAW_FLAT_FRAGMENT_SOURCE)
        uniforms = r.uniforms("flat", self._FLAT_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        self._motion_uniforms(uniforms, progress, aspect)
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, geometry.flat_vertices)
        if shadows:
            program = r.program("shadow", JIGSAW_SHADOW_VERTEX_SOURCE, JIGSAW_SHADOW_FRAGMENT_SOURCE)
            uniforms = r.uniforms("shadow", self._SHADOW_UNIFORMS)
            bind_frame(program, uniforms, frame)
            self._motion_uniforms(uniforms, progress, aspect)
            gl.glBindVertexArray(frame.quad_vao)
            with blend_scope(gl.GL_FUNC_ADD, gl.GL_DST_COLOR, gl.GL_ZERO):
                gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, geometry.count)
        # The pieces in the air.
        r.begin_depth(frame)
        program = r.program("flight", JIGSAW_FLIGHT_VERTEX_SOURCE, JIGSAW_FLIGHT_FRAGMENT_SOURCE)
        uniforms = r.uniforms("flight", self._FLIGHT_UNIFORMS)
        bind_frame(program, uniforms, frame)
        self._motion_uniforms(uniforms, progress, aspect)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        self._geometry_key = self._geometry = None
        self._pieces = np.zeros(0, dtype=np.float32)
        self._vao = self._count = 0
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickJigsawRenderer:
    return QuickJigsawRenderer()

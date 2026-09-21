"""Lazy closed-solid Crumble renderer with static instanced debris."""

from __future__ import annotations
import ctypes
import math
import random
from collections.abc import Mapping
from OpenGL import GL as gl
from rendering.gl_programs.crumble_program import (
    CRUMBLE_CHIP_VERTICES,
    CRUMBLE_FRAGMENT,
    CRUMBLE_VERTEX,
    DEBRIS_FRAGMENT,
    DEBRIS_VERTEX,
)
from ..fracture_geometry import fracture_cells, fracture_vertices
from ..mesh_support import MeshResources, bind_frame
from ..render_contract import QuickTransitionRenderFrame


def _number(
    parameters: Mapping[str, object], name: str, low: float, high: float
) -> float:
    value = parameters.get(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ValueError(f"Crumble requires resolved finite numeric parameter {name!r}")
    value = float(value)
    if not low <= value <= high:
        raise ValueError(f"Crumble {name} must be between {low} and {high}")
    return value


def _crumble_parameters(
    parameters: Mapping[str, object],
) -> tuple[float, int, float, float, float, float, float]:
    seed = _number(parameters, "seed", 0.0, 1000.0)
    pieces = parameters.get("piece_count")
    if (
        isinstance(pieces, bool)
        or not isinstance(pieces, int)
        or not 4 <= pieces <= 128
    ):
        raise ValueError("Crumble piece_count must be an integer between 4 and 128")
    complexity = _number(parameters, "crack_complexity", 0.5, 2.0)
    weight = _number(parameters, "weight_mode", 0.0, 4.0)
    if weight not in {0.0, 1.0, 2.0, 3.0, 4.0}:
        raise ValueError("Crumble weight_mode must be one of 0, 1, 2, 3, 4")
    return (
        seed,
        pieces,
        complexity,
        weight,
        _number(parameters, "depth", 0.2, 1.5),
        _number(parameters, "thickness", 0.0, 1.0),
        _number(parameters, "debris", 0.0, 1.0),
    )


def _debris_instances(seed: float, shards, amount: float) -> tuple[float, ...]:
    rng = random.Random(seed)
    count = max(12, min(512, round(len(shards) * (3 + 9 * amount))))
    values = []
    for index in range(count):
        shard = shards[index % len(shards)]
        first = shard.polygon[index % len(shard.polygon)]
        second = shard.polygon[(index + 1) % len(shard.polygon)]
        fraction = rng.random()
        x = first[0] + (second[0] - first[0]) * fraction
        y = first[1] + (second[1] - first[1]) * fraction
        parent_x, parent_y = shard.center
        values.extend(
            (
                x,
                y,
                parent_x,
                parent_y,
                shard.variation,
                0.35 + rng.random() * 0.65,
            )
        )
    return tuple(values)


class QuickCrumbleRenderer:
    transition_id = "crumble"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Crumble")
        self._geometry_key = None
        self._chunk_vao = self._chunk_count = self._debris_vbo = self._debris_count = 0

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or bool(self._debris_vbo)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            seed, pieces, complexity, weight, depth, thickness, debris = (
                _crumble_parameters(frame.run.request.parameter_dict())
            )
            aspect = frame.logical_size[0] / frame.logical_size[1]
            key = (frame.run.run_id, seed, pieces, complexity, aspect, debris)
            if key != self._geometry_key:
                self._rebuild_geometry(seed, pieces, complexity, aspect, debris)
                self._geometry_key = key
            self._resources.draw_image(frame, frame.destination_texture_id)
            self._resources.begin_depth(frame)
            self._draw_chunks(frame, progress, seed, weight, depth, thickness)
            if debris > 0.0:
                self._draw_debris(frame, progress, seed, weight, depth, debris)
        except Exception:
            self.release_resources()
            raise

    def _rebuild_geometry(self, seed, pieces, complexity, aspect, debris) -> None:
        self._resources.drop_mesh("chunks")
        if self._debris_vbo:
            gl.glDeleteBuffers(1, [self._debris_vbo])
            self._debris_vbo = 0
        shards = fracture_cells(seed, pieces, aspect, complexity)
        self._chunk_vao, self._chunk_count = self._resources.mesh(
            "chunks", fracture_vertices(shards, aspect), (2, 2, 1, 3, 1, 1, 1, 1)
        )
        if debris <= 0.0:
            self._debris_count = 0
            self._resources.drop_mesh("debris_chip")
            return
        vao, _ = self._resources.mesh("debris_chip", CRUMBLE_CHIP_VERTICES, (3, 3))
        values = _debris_instances(seed, shards, debris)
        self._debris_count = len(values) // 6
        self._debris_vbo = int(gl.glGenBuffers(1))
        if not self._debris_vbo:
            raise RuntimeError("Quick Crumble debris allocation failed")
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._debris_vbo)
        packed = (ctypes.c_float * len(values))(*values)
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER, ctypes.sizeof(packed), packed, gl.GL_STATIC_DRAW
        )
        for location, offset in ((2, 0), (3, 2), (4, 4)):
            gl.glEnableVertexAttribArray(location)
            gl.glVertexAttribPointer(
                location, 2, gl.GL_FLOAT, gl.GL_FALSE, 24, ctypes.c_void_p(offset * 4)
            )
            gl.glVertexAttribDivisor(location, 1)

    def _draw_chunks(self, frame, progress, seed, weight, depth, thickness) -> None:
        program = self._resources.program("chunks", CRUMBLE_VERTEX, CRUMBLE_FRAGMENT)
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
                "uWeightMode",
            ),
        )
        bind_frame(program, u, frame)
        for name, value in (
            ("uProgress", progress),
            ("uDepth", depth),
            ("uThickness", thickness),
            ("uSeed", seed),
            ("uWeightMode", weight),
        ):
            gl.glUniform1f(u[name], value)
        gl.glBindVertexArray(self._chunk_vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._chunk_count)

    def _draw_debris(self, frame, progress, seed, weight, depth, debris) -> None:
        program = self._resources.program("debris", DEBRIS_VERTEX, DEBRIS_FRAGMENT)
        u = self._resources.uniforms(
            "debris",
            (
                "uMatrix",
                "uItemSize",
                "uProgress",
                "uDepth",
                "uDebris",
                "uSeed",
                "uWeightMode",
            ),
        )
        bind_frame(program, u, frame)
        for name, value in (
            ("uProgress", progress),
            ("uDepth", depth),
            ("uDebris", debris),
            ("uSeed", seed),
            ("uWeightMode", weight),
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

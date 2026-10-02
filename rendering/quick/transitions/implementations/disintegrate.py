"""Lazy Quick renderer for Disintegrate: the old picture blows away as grains over the new one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.disintegrate_program import (
    DISINTEGRATE_FRAME_BLOCK,
    DISINTEGRATE_GRAIN_FRAGMENT_SOURCE,
    DISINTEGRATE_GRAIN_VERTEX_SOURCE,
    DISINTEGRATE_HOOKS,
    DISINTEGRATE_INTACT_FRAGMENT_SOURCE,
    DISINTEGRATE_VERTICES,
    disintegrate_grid,
)
from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.passes import blend_scope
from rendering.quick.scene3d.population import CompactedPopulation, population_programs
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from rendering.quick.scene3d.uniforms import UniformBlock
from ..directions import direction_vector
from ..render_contract import QuickTransitionRenderFrame


def disintegrate_parameters(parameters: Mapping[str, object]) -> tuple[int, int, float]:
    """The resolved seed, grain size and wind, validated before any GL state changes."""
    seed, grain, wind = parameters.get("seed"), parameters.get("grain_size"), parameters.get("wind")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Disintegrate seed must be an integer between 1 and 65535")
    if isinstance(grain, bool) or not isinstance(grain, int) or not 2 <= grain <= 8:
        raise ValueError("Disintegrate grain size must be an integer between 2 and 8")
    if isinstance(wind, bool) or not isinstance(wind, (int, float)) or not 0.5 <= float(wind) <= 2.0:
        raise ValueError("Disintegrate wind must be between 0.5 and 2")
    return seed, grain, float(wind)


class QuickDisintegrateRenderer:
    transition_id = "disintegrate"

    _INTACT_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex")
    _GRAIN_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uGrid")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Disintegrate")
        self._target = SceneTarget("Quick Disintegrate")
        self._grains = CompactedPopulation("Quick Disintegrate")
        self._stream = StreamRing("Quick Disintegrate")
        self._frame_block = UniformBlock(DISINTEGRATE_FRAME_BLOCK, "Quick Disintegrate", self._stream)

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._grains.has_resources
                or self._stream.has_resources)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        parameters = frame.run.request.parameter_dict()
        seed, grain, wind = disintegrate_parameters(parameters)
        direction = direction_vector(frame.run.request.direction)
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            columns, rows, _size = disintegrate_grid(frame.viewport[2], frame.viewport[3], grain)
            samples = scene3d_request_samples(parameters)
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw(frame, progress, seed, wind, direction, columns, rows)
            else:
                self._draw(frame, progress, seed, wind, direction, columns, rows)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        _seed, grain, _wind = disintegrate_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM),
                   (r, "intact", ITEM_QUAD_VERTEX_SOURCE, DISINTEGRATE_INTACT_FRAGMENT_SOURCE),
                   (r, "grains", DISINTEGRATE_GRAIN_VERTEX_SOURCE, DISINTEGRATE_GRAIN_FRAGMENT_SOURCE)]
        entries += [(r, *program) for program in population_programs("grains", DISINTEGRATE_HOOKS)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries) or not self._stream.warm():
            return False
        if size is not None:
            columns, rows, _size = disintegrate_grid(size[0], size[1], grain)
            if not self._grains.warm(columns * rows):
                return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and grain population; programs and the stream ring stay warm."""
        self._target.release()
        self._grains.release()

    def _draw(self, frame, progress: float, seed: int, wind: float, direction, columns: int, rows: int) -> None:
        values = {"uGrid": (columns, rows), "uDirection": direction, "uFrameSize": frame.logical_size,
                  "uProgress": progress, "uSeed": seed, "uWind": wind}
        with self._frame_block.bound(values):
            self._draw_bound(frame, columns, rows)

    def _draw_bound(self, frame, columns: int, rows: int) -> None:
        r = self._resources
        program = r.program("intact", ITEM_QUAD_VERTEX_SOURCE, DISINTEGRATE_INTACT_FRAGMENT_SOURCE)
        self._frame_block.attach(program)
        uniforms = r.uniforms("intact", self._INTACT_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        population = columns * rows
        self._grains.warm(population)              # a no-op when warmed for this run's size

        def configure(_key: str, hook_program: int) -> None:
            self._frame_block.attach(hook_program)   # the hooks read the streamed frame block

        with self._grains.bound():
            self._grains.update(r, "grains", DISINTEGRATE_HOOKS, population, DISINTEGRATE_VERTICES, configure)
            program = r.program("grains", DISINTEGRATE_GRAIN_VERTEX_SOURCE, DISINTEGRATE_GRAIN_FRAGMENT_SOURCE)
            uniforms = r.uniforms("grains", self._GRAIN_UNIFORMS)
            bind_frame(program, uniforms, frame)
            gl.glUniform2ui(uniforms["uGrid"], columns, rows)
            gl.glBindVertexArray(frame.quad_vao)
            with blend_scope(gl.GL_FUNC_ADD, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA):
                self._grains.draw(gl.GL_TRIANGLE_STRIP)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._grains.release, self._frame_block.release, self._stream.release,
                        self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickDisintegrateRenderer:
    return QuickDisintegrateRenderer()

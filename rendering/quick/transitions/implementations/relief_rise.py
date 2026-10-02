"""Lazy Quick renderer for Relief Rise: a relief wave carries the old picture into the new."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.relief_rise_program import RELIEF_FRAGMENT_SOURCE, RELIEF_VERTEX_SOURCE
from rendering.gl_programs.scene3d import (
    scene3d_detail,
    scene3d_grid_size,
    scene3d_grid_vertices,
    scene3d_request_samples,
)
from rendering.quick import gl_query
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.grid import draw_grid
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..directions import direction_vector
from ..render_contract import QuickTransitionRenderFrame


def relief_parameters(parameters: Mapping[str, object]) -> tuple[float, float, str]:
    """The resolved depth, gloss and 3D Detail tier, validated before any GL state changes."""
    depth, gloss, detail = parameters.get("depth"), parameters.get("gloss"), parameters.get("detail")
    for name, value in (("depth", depth), ("gloss", gloss)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Relief Rise needs a resolved {name} between 0 and 1")
    if not isinstance(detail, str):
        raise ValueError("Relief Rise needs a resolved 3D Detail tier")
    return float(depth), float(gloss), detail


class QuickReliefRiseRenderer:
    transition_id = "relief_rise"

    _UNIFORMS = ("uMatrix", "uItemSize", "uGridCells", "uDirection", "uProgress", "uDepth", "uGloss", "uOldTex",
                 "uNewTex", "uSourceHeights", "uDestinationHeights")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Relief Rise")
        self._target = SceneTarget("Quick Relief Rise")
        self._heights = PhotoEnvironment("Quick Relief Rise")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._heights.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        direction = direction_vector(frame.run.request.direction)
        parameters = frame.run.request.parameter_dict()
        depth, gloss, detail = relief_parameters(parameters)
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            samples = scene3d_request_samples(parameters)
            source = self._heights.texture(frame, self._resources, "source")
            destination = self._heights.texture(frame, self._resources, "destination")
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw(frame, progress, direction, depth, gloss, detail, source, destination)
            else:
                self._draw(frame, progress, direction, depth, gloss, detail, source, destination)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        _depth, _gloss, detail = relief_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "relief", RELIEF_VERTEX_SOURCE, RELIEF_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        if size is not None:
            columns, rows = scene3d_grid_size(scene3d_detail(detail), size[0] / max(1, size[1]))
            key = f"scene_grid_{columns}x{rows}"
            if not r.has_mesh(key):
                r.mesh(key, scene3d_grid_vertices(columns, rows), (2,))
                return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and photo copies; programs and grids stay warm."""
        self._target.release()
        self._heights.release()

    def _draw(self, frame, progress: float, direction, depth: float, gloss: float, detail: str,
              source: int, destination: int) -> None:
        r = self._resources
        r.begin_depth(frame)
        program = r.program("relief", RELIEF_VERTEX_SOURCE, RELIEF_FRAGMENT_SOURCE)
        uniforms = r.uniforms("relief", self._UNIFORMS)
        bind_frame(program, uniforms, frame)
        width, height = frame.logical_size
        columns, rows = scene3d_grid_size(scene3d_detail(detail), width / height)
        gl.glUniform2f(uniforms["uGridCells"], float(columns), float(rows))
        gl.glUniform2f(uniforms["uDirection"], *direction)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uDepth"], depth)
        gl.glUniform1f(uniforms["uGloss"], gloss)
        # Units 0 and 1 hold the photographs (bind_frame); the copies go on 2 and 3. The host
        # fence restores units 0-2; unit 3 is handed back here.
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, source)
        gl.glUniform1i(uniforms["uSourceHeights"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        inherited = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, destination)
        gl.glUniform1i(uniforms["uDestinationHeights"], 3)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        try:
            draw_grid(r, columns, rows)
        finally:
            gl.glActiveTexture(gl.GL_TEXTURE3)
            gl.glBindTexture(gl.GL_TEXTURE_2D, inherited)
            gl.glActiveTexture(gl.GL_TEXTURE0)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._heights.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickReliefRiseRenderer:
    return QuickReliefRiseRenderer()

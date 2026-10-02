"""Lazy Quick renderer for Accordion Fold: the old picture folds up against an edge and leaves."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.accordion_fold_options import ACCORDION_EDGES, ACCORDION_PLEATS_RANGE
from rendering.gl_programs.accordion_fold_program import (
    ACCORDION_BACKDROP_FRAGMENT_SOURCE,
    ACCORDION_FRAGMENT_SOURCE,
    ACCORDION_VERTEX_SOURCE,
    accordion_edge,
    accordion_grid,
    accordion_shade_weight,
    accordion_state,
)
from rendering.gl_programs.scene3d import scene3d_detail, scene3d_grid_vertices, scene3d_request_samples
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.grid import draw_grid
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..render_contract import QuickTransitionRenderFrame

_EDGES = frozenset(ACCORDION_EDGES.values())


def accordion_parameters(parameters: Mapping[str, object]) -> tuple[int, float, str]:
    """The resolved pleat count, gloss and 3D Detail tier, validated before any GL state changes."""
    pleats, gloss, detail = parameters.get("pleats"), parameters.get("gloss"), parameters.get("detail")
    low, high = ACCORDION_PLEATS_RANGE
    if isinstance(pleats, bool) or not isinstance(pleats, int) or not low <= pleats <= high:
        raise ValueError(f"Accordion Fold needs a resolved pleat count between {low} and {high}")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Accordion Fold needs a resolved gloss between 0 and 1")
    if not isinstance(detail, str):
        raise ValueError("Accordion Fold needs a resolved 3D Detail tier")
    return pleats, float(gloss), detail


class QuickAccordionFoldRenderer:
    transition_id = "accordion_fold"

    _PAGE_UNIFORMS = ("uMatrix", "uItemSize", "uGridCells", "uEdge", "uLength", "uPleats", "uAngle", "uSlide",
                      "uOldTex", "uEnvironment", "uGloss")
    _BACKDROP_UNIFORMS = ("uMatrix", "uItemSize", "uNewTex", "uShade", "uFront", "uEdge", "uLength")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Accordion Fold")
        self._target = SceneTarget("Quick Accordion Fold")
        self._environment = PhotoEnvironment("Quick Accordion Fold")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._environment.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        edge = str(frame.run.request.direction)
        if edge not in _EDGES:
            raise ValueError(f"unknown resolved Accordion Fold edge: {edge!r}")
        parameters = frame.run.request.parameter_dict()
        pleats, gloss, detail = accordion_parameters(parameters)
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
                    self._draw(frame, progress, edge, pleats, gloss, detail, environment)
            else:
                self._draw(frame, progress, edge, pleats, gloss, detail, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing (both fold axes' grids)."""
        pleats, _gloss, detail = accordion_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "backdrop", ITEM_QUAD_VERTEX_SOURCE, ACCORDION_BACKDROP_FRAGMENT_SOURCE),
                   (r, "page", ACCORDION_VERTEX_SOURCE, ACCORDION_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        if size is not None:
            aspect = size[0] / max(1, size[1])
            for vertical in (False, True):
                columns, rows = accordion_grid(pleats, scene3d_detail(detail).grid_cells, aspect, vertical)
                key = f"scene_grid_{columns}x{rows}"
                if not r.has_mesh(key):
                    r.mesh(key, scene3d_grid_vertices(columns, rows), (2,))
                    return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and environment; programs and grids stay warm."""
        self._target.release()
        self._environment.release()

    def _draw(self, frame, progress: float, edge: str, pleats: int, gloss: float, detail: str,
              environment: int) -> None:
        width, height = frame.logical_size
        aspect = width / height
        vertical = edge in ("top", "bottom")
        length = 1.0 if vertical else aspect
        angle, slide = accordion_state(progress, length, pleats)
        direction = accordion_edge(edge)
        front = length * math.cos(angle) - slide
        r = self._resources

        program = r.program("backdrop", ITEM_QUAD_VERTEX_SOURCE, ACCORDION_BACKDROP_FRAGMENT_SOURCE)
        uniforms = r.uniforms("backdrop", self._BACKDROP_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform2f(uniforms["uEdge"], *direction)
        gl.glUniform1f(uniforms["uLength"], length)
        gl.glUniform1f(uniforms["uFront"], front)
        gl.glUniform1f(uniforms["uShade"], accordion_shade_weight(progress))
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        r.begin_depth(frame)
        program = r.program("page", ACCORDION_VERTEX_SOURCE, ACCORDION_FRAGMENT_SOURCE)
        # Flat-shaded pleats never read the grid normal, so uGridCells may be dropped.
        uniforms = r.uniforms("page", self._PAGE_UNIFORMS, required=False)
        bind_frame(program, uniforms, frame)
        columns, rows = accordion_grid(pleats, scene3d_detail(detail).grid_cells, aspect, vertical)
        gl.glUniform2f(uniforms["uGridCells"], float(columns), float(rows))
        gl.glUniform2f(uniforms["uEdge"], *direction)
        gl.glUniform1f(uniforms["uLength"], length)
        gl.glUniform1f(uniforms["uPleats"], float(pleats))
        gl.glUniform1f(uniforms["uAngle"], angle)
        gl.glUniform1f(uniforms["uSlide"], slide)
        gl.glUniform1f(uniforms["uGloss"], gloss)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        draw_grid(r, columns, rows)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickAccordionFoldRenderer:
    return QuickAccordionFoldRenderer()

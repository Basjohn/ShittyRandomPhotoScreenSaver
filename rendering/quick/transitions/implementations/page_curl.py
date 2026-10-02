"""Lazy Quick renderer for Page Curl: the old picture peels away over the new one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.page_curl_program import (
    PAGE_CURL_BACKDROP_FRAGMENT_SOURCE,
    PAGE_CURL_FRAGMENT_SOURCE,
    PAGE_CURL_VERTEX_SOURCE,
    page_curl_direction,
    page_curl_line,
    page_curl_shade_weight,
    page_curl_span,
)
from rendering.gl_programs.page_curl_options import PAGE_CURL_ORIGINS
from rendering.gl_programs.scene3d import (
    scene3d_detail,
    scene3d_grid_size,
    scene3d_grid_vertices,
    scene3d_request_samples,
)
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.grid import draw_grid
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..render_contract import QuickTransitionRenderFrame

_ORIGINS = frozenset(PAGE_CURL_ORIGINS.values())


def page_curl_parameters(parameters: Mapping[str, object]) -> tuple[float, str]:
    """The resolved gloss and 3D Detail tier, validated before any GL state changes."""
    gloss, detail = parameters.get("gloss"), parameters.get("detail")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Page Curl needs a resolved gloss between 0 and 1")
    if not isinstance(detail, str):
        raise ValueError("Page Curl needs a resolved 3D Detail tier")
    return float(gloss), detail


class QuickPageCurlRenderer:
    transition_id = "page_curl"

    _PAGE_UNIFORMS = ("uMatrix", "uItemSize", "uGridCells", "uDirection", "uLine", "uOldTex", "uEnvironment",
                      "uGloss")
    _BACKDROP_UNIFORMS = ("uMatrix", "uItemSize", "uNewTex", "uShade", "uDirection", "uLine")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Page Curl")
        self._target = SceneTarget("Quick Page Curl")
        self._environment = PhotoEnvironment("Quick Page Curl")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._environment.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        origin = str(frame.run.request.direction)
        if origin not in _ORIGINS:
            raise ValueError(f"unknown resolved Page Curl origin: {origin!r}")
        parameters = frame.run.request.parameter_dict()
        gloss, detail = page_curl_parameters(parameters)
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
                    self._draw(frame, progress, origin, gloss, detail, environment)
            else:
                self._draw(frame, progress, origin, gloss, detail, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        _gloss, detail = page_curl_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "backdrop", ITEM_QUAD_VERTEX_SOURCE, PAGE_CURL_BACKDROP_FRAGMENT_SOURCE),
                   (r, "page", PAGE_CURL_VERTEX_SOURCE, PAGE_CURL_FRAGMENT_SOURCE)]
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
        """Drop the per-run target and environment; programs and grids stay warm."""
        self._target.release()
        self._environment.release()

    def _draw(self, frame, progress: float, origin: str, gloss: float, detail: str, environment: int) -> None:
        width, height = frame.logical_size
        aspect = width / height
        direction = page_curl_direction(origin, aspect)
        near, far = page_curl_span(direction, aspect)
        line = page_curl_line(progress, near, far)
        r = self._resources

        program = r.program("backdrop", ITEM_QUAD_VERTEX_SOURCE, PAGE_CURL_BACKDROP_FRAGMENT_SOURCE)
        uniforms = r.uniforms("backdrop", self._BACKDROP_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform2f(uniforms["uDirection"], *direction)
        gl.glUniform1f(uniforms["uLine"], line)
        gl.glUniform1f(uniforms["uShade"], page_curl_shade_weight(line, far))
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        r.begin_depth(frame)
        program = r.program("page", PAGE_CURL_VERTEX_SOURCE, PAGE_CURL_FRAGMENT_SOURCE)
        uniforms = r.uniforms("page", self._PAGE_UNIFORMS)
        bind_frame(program, uniforms, frame)
        columns, rows = scene3d_grid_size(scene3d_detail(detail), aspect)
        gl.glUniform2f(uniforms["uGridCells"], float(columns), float(rows))
        gl.glUniform2f(uniforms["uDirection"], *direction)
        gl.glUniform1f(uniforms["uLine"], line)
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


def create_transition_renderer() -> QuickPageCurlRenderer:
    return QuickPageCurlRenderer()

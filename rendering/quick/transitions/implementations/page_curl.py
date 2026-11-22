"""Lazy Quick renderer for Page Curl: the old picture peels away and rolls up over the new one."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.page_curl_program import (
    PAGE_CURL_BACKDROP_BLOCK,
    PAGE_CURL_BACKDROP_FRAGMENT_SOURCE,
    PAGE_CURL_BACKDROP_VERTEX_SOURCE,
    PAGE_CURL_BLOCK,
    PAGE_CURL_FRAGMENT_SOURCE,
    PAGE_CURL_VERTEX_SOURCE,
    page_curl_direction,
    page_curl_line,
    page_curl_roll,
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
from rendering.quick.scene3d.environment import (PHOTO_ENVIRONMENT_MIPS_PROGRAM, PHOTO_ENVIRONMENT_PROGRAM,
                                                 PhotoEnvironment)
from rendering.gl_programs.portable import pack_block
from rendering.quick.scene3d.grid import draw_grid
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from rendering.quick.scene3d.resources import pack_floats
from ..native_scene import (NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show,
                            item_quad_pass, native_clip_depth)
from ..render_contract import QuickTransitionRenderFrame

_ORIGINS = frozenset(PAGE_CURL_ORIGINS.values())
# N5.2e (N4.l's bendable grid): the native scene's passes, the texts this renderer compiles (the page's vertex stage
# with its native clip depth): the new picture under the roll's shadow, then the page over the run's grid.
_GRID_INPUTS = (("aGrid", 2),)
_SCENE_PASSES = (
    item_quad_pass("backdrop", PAGE_CURL_BACKDROP_VERTEX_SOURCE, PAGE_CURL_BACKDROP_FRAGMENT_SOURCE,
                   (("uNewTex", "new"),)),
    NativeScenePass("page", native_clip_depth(PAGE_CURL_VERTEX_SOURCE), PAGE_CURL_FRAGMENT_SOURCE, mesh="grid",
                    samplers=(("uOldTex", "old"), ("uEnvironment", "environment")), depth=True),
)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def page_curl_parameters(parameters: Mapping[str, object]) -> tuple[float, float, str]:
    """The resolved gloss, curl size and 3D Detail tier, validated before any GL state changes."""
    values = []
    for name in ("gloss", "size"):
        value = parameters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Page Curl needs a resolved {name} between 0 and 1")
        values.append(float(value))
    detail = parameters.get("detail")
    if not isinstance(detail, str):
        raise ValueError("Page Curl needs a resolved 3D Detail tier")
    return values[0], values[1], detail


class QuickPageCurlRenderer(NativeScenePasses):
    transition_id = "page_curl"

    # ------------------------------------------------------------------------------- N5.2e: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        _gloss, _size, detail = page_curl_parameters(parameters)
        columns, rows = scene3d_grid_size(scene3d_detail(detail), logical_size[0] / logical_size[1])
        grid = NativeSceneMesh("grid", pack_floats(scene3d_grid_vertices(columns, rows)), _GRID_INPUTS)
        return NativeScene(_SCENE_PASSES, (grid,), scene3d_request_samples(parameters), True)

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample))

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        """The backdrop's and the page's values for the frame (``_curl_values``, one owner)."""
        origin = str(run.request.direction)
        if origin not in _ORIGINS:
            raise ValueError(f"unknown resolved Page Curl origin: {origin!r}")
        gloss, size, detail = page_curl_parameters(run.request.parameter_dict())
        return self._curl_values(_progress(sample), origin, gloss, page_curl_roll(size), detail, logical_size)

    @staticmethod
    def _curl_values(progress: float, origin: str, gloss: float, roll, detail: str,
                     logical_size: tuple[float, float]) -> dict[str, object]:
        """Both programs' values by name (the backdrop reads the line, roll, direction and shade; the page the grid,
        the line, roll, direction and gloss)."""
        aspect = logical_size[0] / logical_size[1]
        direction = page_curl_direction(origin, aspect)
        near, far = page_curl_span(direction, aspect)
        line = page_curl_line(progress, near, far, roll)
        columns, rows = scene3d_grid_size(scene3d_detail(detail), aspect)
        return {"uDirection": direction, "uLine": line, "uRoll": roll,
                "uShade": page_curl_shade_weight(line, near, far, roll), "uGloss": gloss,
                "uGridCells": (float(columns), float(rows))}

    # The photographs each program reads (bind_frame binds them); every other value is in its pass block.
    _PAGE_SAMPLERS = ("uOldTex",)
    _BACKDROP_SAMPLERS = ("uNewTex",)

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
        gloss, size, detail = page_curl_parameters(parameters)
        roll = page_curl_roll(size)
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
                    self._draw(frame, progress, origin, gloss, roll, detail, environment)
            else:
                self._draw(frame, progress, origin, gloss, roll, detail, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        _gloss, _size, detail = page_curl_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM), (r, *PHOTO_ENVIRONMENT_MIPS_PROGRAM),
                   (r, "backdrop", PAGE_CURL_BACKDROP_VERTEX_SOURCE, PAGE_CURL_BACKDROP_FRAGMENT_SOURCE),
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
        if not warm_pass_blocks(self._resources, size):
            return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and environment; programs and grids stay warm."""
        self._target.release()
        self._environment.release()

    def _draw(self, frame, progress: float, origin: str, gloss: float, roll: tuple[float, float], detail: str,
              environment: int) -> None:
        curl = self._curl_values(progress, origin, gloss, roll, detail, frame.logical_size)   # the one owner (N5.2e)
        r = self._resources

        program = r.program("backdrop", PAGE_CURL_BACKDROP_VERTEX_SOURCE, PAGE_CURL_BACKDROP_FRAGMENT_SOURCE)
        uniforms = r.uniforms("backdrop", self._BACKDROP_SAMPLERS)
        values = r.values("backdrop")
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame, values)
        values.update(curl)
        with r.pass_blocks.bound(pack_block(PAGE_CURL_BACKDROP_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        r.begin_depth(frame)
        program = r.program("page", PAGE_CURL_VERTEX_SOURCE, PAGE_CURL_FRAGMENT_SOURCE)
        uniforms = r.uniforms("page", self._PAGE_SAMPLERS)
        values = r.values("page")
        bind_frame(program, uniforms, frame, values)
        values.update(curl)
        columns, rows = (int(v) for v in curl["uGridCells"])
        gl.glActiveTexture(gl.GL_TEXTURE2)               # the environment's binding
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        with r.pass_blocks.bound(pack_block(PAGE_CURL_BLOCK, values)):
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

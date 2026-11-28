"""Lazy Quick renderer for Page Curl: the old picture peels away and rolls up over the new one."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.page_curl_program import (
    PAGE_CURL_BACKDROP_FRAGMENT_SOURCE,
    PAGE_CURL_BACKDROP_VERTEX_SOURCE,
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
from rendering.quick.scene3d.resources import pack_floats
from ..native_scene import (NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show,
                            item_quad_pass, native_clip_depth)

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


def create_transition_renderer() -> QuickPageCurlRenderer:
    return QuickPageCurlRenderer()

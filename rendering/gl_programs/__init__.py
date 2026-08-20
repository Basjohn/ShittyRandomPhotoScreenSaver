"""Lazy public exports for built-in GL shader helpers.

Transition catalog imports must not import every implementation module. The
legacy compositor can continue using these public names, but each helper is
loaded only when that exact attribute is requested.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING


_LAZY_EXPORTS = {
    "BaseGLProgram": ("rendering.gl_programs.base_program", "BaseGLProgram"),
    "BlockFlipProgram": (
        "rendering.gl_programs.blockflip_program",
        "BlockFlipProgram",
    ),
    "blockflip_program": (
        "rendering.gl_programs.blockflip_program",
        "blockflip_program",
    ),
    "CrossfadeProgram": (
        "rendering.gl_programs.crossfade_program",
        "CrossfadeProgram",
    ),
    "crossfade_program": (
        "rendering.gl_programs.crossfade_program",
        "crossfade_program",
    ),
    "BlindsProgram": ("rendering.gl_programs.blinds_program", "BlindsProgram"),
    "blinds_program": ("rendering.gl_programs.blinds_program", "blinds_program"),
    "DiffuseProgram": (
        "rendering.gl_programs.diffuse_program",
        "DiffuseProgram",
    ),
    "diffuse_program": (
        "rendering.gl_programs.diffuse_program",
        "diffuse_program",
    ),
    "SlideProgram": ("rendering.gl_programs.slide_program", "SlideProgram"),
    "slide_program": ("rendering.gl_programs.slide_program", "slide_program"),
    "WipeProgram": ("rendering.gl_programs.wipe_program", "WipeProgram"),
    "wipe_program": ("rendering.gl_programs.wipe_program", "wipe_program"),
    "WarpProgram": ("rendering.gl_programs.warp_program", "WarpProgram"),
    "warp_program": ("rendering.gl_programs.warp_program", "warp_program"),
    "RaindropsProgram": (
        "rendering.gl_programs.raindrops_program",
        "RaindropsProgram",
    ),
    "raindrops_program": (
        "rendering.gl_programs.raindrops_program",
        "raindrops_program",
    ),
    "GLProgramCache": (
        "rendering.gl_programs.program_cache",
        "GLProgramCache",
    ),
    "GLGeometryManager": (
        "rendering.gl_programs.geometry_manager",
        "GLGeometryManager",
    ),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted((*globals(), *_LAZY_EXPORTS))


if TYPE_CHECKING:
    from .base_program import BaseGLProgram as BaseGLProgram
    from .blinds_program import BlindsProgram as BlindsProgram
    from .blinds_program import blinds_program as blinds_program
    from .blockflip_program import BlockFlipProgram as BlockFlipProgram
    from .blockflip_program import blockflip_program as blockflip_program
    from .crossfade_program import CrossfadeProgram as CrossfadeProgram
    from .crossfade_program import crossfade_program as crossfade_program
    from .diffuse_program import DiffuseProgram as DiffuseProgram
    from .diffuse_program import diffuse_program as diffuse_program
    from .geometry_manager import GLGeometryManager as GLGeometryManager
    from .program_cache import GLProgramCache as GLProgramCache
    from .raindrops_program import RaindropsProgram as RaindropsProgram
    from .raindrops_program import raindrops_program as raindrops_program
    from .slide_program import SlideProgram as SlideProgram
    from .slide_program import slide_program as slide_program
    from .warp_program import WarpProgram as WarpProgram
    from .warp_program import warp_program as warp_program
    from .wipe_program import WipeProgram as WipeProgram
    from .wipe_program import wipe_program as wipe_program

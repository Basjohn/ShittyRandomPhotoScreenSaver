"""GL shader program helpers for per-transition rendering.

Each helper encapsulates the GLSL source, compilation, uniform caching, and
draw logic for a single transition type. The compositor delegates rendering
to these helpers while retaining ownership of the GL context, textures, and
transition state.
"""

from rendering.gl_programs.base_program import BaseGLProgram
from rendering.gl_programs.peel_program import PeelProgram, peel_program
from rendering.gl_programs.blockflip_program import BlockFlipProgram, blockflip_program
from rendering.gl_programs.crossfade_program import CrossfadeProgram, crossfade_program
from rendering.gl_programs.blinds_program import BlindsProgram, blinds_program
from rendering.gl_programs.diffuse_program import DiffuseProgram, diffuse_program
from rendering.gl_programs.slide_program import SlideProgram, slide_program
from rendering.gl_programs.wipe_program import WipeProgram, wipe_program
from rendering.gl_programs.warp_program import WarpProgram, warp_program
from rendering.gl_programs.raindrops_program import RaindropsProgram, raindrops_program
from rendering.gl_programs.program_cache import GLProgramCache, get_program_cache, cleanup_program_cache
from rendering.gl_programs.geometry_manager import GLGeometryManager, get_geometry_manager, cleanup_geometry_manager

__all__ = [
    "BaseGLProgram",
    "PeelProgram",
    "peel_program",
    "BlockFlipProgram",
    "blockflip_program",
    "CrossfadeProgram",
    "crossfade_program",
    "BlindsProgram",
    "blinds_program",
    "DiffuseProgram",
    "diffuse_program",
    "SlideProgram",
    "slide_program",
    "WipeProgram",
    "wipe_program",
    "WarpProgram",
    "warp_program",
    "RaindropsProgram",
    "raindrops_program",
    "GLProgramCache",
    "get_program_cache",
    "cleanup_program_cache",
    "GLGeometryManager",
    "get_geometry_manager",
    "cleanup_geometry_manager",
]

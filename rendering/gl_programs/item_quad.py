"""The item quad (N1.6): attribute 0 is a unit square placed in Qt Quick item pixels by ``uMatrix`` and ``uItemSize``;
``vUv`` keeps the bottom-up convention the transition fragments were authored in. Pure: strings only.

A program drawn over the quad declares the quad's two values in its own std140 pass block, with its fragment's values
(``item_quad_program``): Vulkan GLSL has no loose uniforms, and one block per program is what its owner packs and binds
once per draw (``rendering.quick.scene3d.uniforms.PassBlocks``).
"""
from __future__ import annotations

from typing import Mapping

from rendering.gl_programs.portable import portable_program

# The quad's own values, as the OpenGL-era sources declared them; ``item_quad_program`` moves them into the block.
_QUAD_VALUES = "uniform mat4 uMatrix;\nuniform vec2 uItemSize;\n"


def item_quad_vertex_source(block_glsl: str) -> str:
    """The item quad's vertex stage for a program whose values are one std140 block: ``block_glsl`` is that program's
    block declaration, holding ``uMatrix`` and ``uItemSize``, so the vertex and fragment stages declare the same
    block."""
    return f"""#version 460 core
layout(location = 0) in vec2 aPosition;
{block_glsl}
layout(location = 0) out vec2 vUv;

void main() {{
    vUv = vec2(aPosition.x, 1.0 - aPosition.y);
    gl_Position = uMatrix * vec4(aPosition * uItemSize, 0.0, 1.0);
}}
"""


def item_quad_program(fragment: str, *, block: str, samplers: Mapping[str, int]):
    """(vertex, fragment, block layout) of ``fragment`` drawn over the item quad: the fragment as written for OpenGL
    (loose uniforms, samplers given units by their owner) rewritten by ``portable_program``, its values and the quad's
    in one pass block named ``block``, each sampler bound at its unit in ``samplers``. The owner packs the layout with
    the values it set with ``glUniform*`` (the frame's matrix and item size among them) and draws inside it."""
    vertex, (converted,), layout = portable_program(item_quad_vertex_source(_QUAD_VALUES), (fragment,), block=block,
                                                    samplers=samplers)
    return vertex, converted, layout


__all__ = ["item_quad_program", "item_quad_vertex_source"]

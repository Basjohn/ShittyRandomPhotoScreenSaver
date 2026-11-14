"""Smooth light written to an 8-bit target is dithered, so slow dark gradients do not step into contour bands.

1B.10 review (Neon Lake): a red sun's halo showed concentric rings and the far end of its light shafts a stair-stepped
dark block. Both were one 8-bit output step every few pixels of a slow gradient: the overlay composite wrote its
float glow and shafts, and the Neon sky pass its dark gradient, to 8-bit colour undithered.
``scene3d.SCENE_OUTPUT_DITHER_GLSL`` (``sceneOutputDither``) is the one dither; the overlay-bloom composites add it
where they add glow, and the Neon sky adds it to its background.
"""
from __future__ import annotations

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE_OUTPUT_DITHER_GLSL

_VERTEX = """#version 460 core
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

WIDTH, HEIGHT = 256, 32
STEPS = 4.0          # the gradient spans four output steps over the whole width: one step every 64 pixels


def _fragment(dithered: bool) -> str:
    add = " + sceneOutputDither(ivec2(gl_FragCoord.xy))" if dithered else ""
    return f"""#version 460 core
out vec4 FragColor;
{SCENE_OUTPUT_DITHER_GLSL}
void main() {{
    float level = (8.0 + {STEPS:.1f} * gl_FragCoord.x / {WIDTH:.1f}) / 255.0;
    FragColor = vec4(vec3(level){add}, 1.0);
}}
"""


def _longest_run(row) -> int:
    longest = run = 1
    for left, right in zip(row[:-1], row[1:]):
        run = run + 1 if left == right else 1
        longest = max(longest, run)
    return longest


@pytest.mark.qt
def test_a_slow_gradient_keeps_its_level_without_contour_bands(qt_app):
    from rendering.quick.render.gl_resources import compile_program, delete_program
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(WIDTH, HEIGHT)
    programs = {name: compile_program(_VERTEX, _fragment(name == "dithered"), label=f"dither probe {name}")
                for name in ("plain", "dithered")}
    vao = int(gl.glGenVertexArrays(1))
    try:
        def draw(name):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glViewport(0, 0, WIDTH, HEIGHT)
            gl.glDisable(gl.GL_BLEND)
            gl.glUseProgram(programs[name])
            gl.glBindVertexArray(vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            raw = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            return np.frombuffer(bytes(raw), dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)[..., :3].astype(np.int16)

        plain, dithered = draw("plain"), draw("dithered")
        truth = 8.0 + STEPS * (np.arange(WIDTH) + 0.5) / WIDTH
        # The plain write stands flat for a quarter of the width between steps: the contour bands.
        assert min(_longest_run(row) for row in plain[..., 0]) >= WIDTH / STEPS / 2
        # Dithered: flat stretches are a few pixels on average on every row and channel, not a quarter of the width ...
        rows = dithered.transpose(2, 0, 1).reshape(-1, WIDTH)
        assert max(WIDTH / (1 + np.count_nonzero(np.diff(row))) for row in rows) <= 4.0
        # ... never more than one step from the true level, and the true level on average (no tint, no shift).
        assert np.abs(dithered - truth[None, :, None]).max() <= 1.5
        assert abs(float(dithered.mean()) - float(truth.mean())) < 0.1
        for channel in range(3):
            columns = dithered[..., channel].mean(axis=0)
            assert np.abs(np.convolve(columns - truth, np.ones(32) / 32, mode="valid")).max() < 0.25
        # The same pixel always gets the same dither (an exact integer hash, no frame-to-frame shimmer).
        assert np.array_equal(draw("dithered"), dithered)
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteVertexArrays(1, [vao])
        for program in programs.values():
            delete_program(program)
        capture.close()


def test_every_overlay_glow_composite_dithers_only_where_it_adds_glow():
    from rendering.quick.scene3d import target

    sources = [target._COMPOSITE_OVERLAY_BLOOM_FRAGMENT, target._COMPOSITE_OVERLAY_BLOOM_SAMPLES_FRAGMENT,
               target._COMPOSITE_OVERLAY_SHAFTS_FRAGMENT, target._COMPOSITE_OVERLAY_SHAFTS_SAMPLES_FRAGMENT]
    sources += [target._ORIENTED_COMPOSITES[source] for source in list(sources)]
    for source in sources:
        body = source.split("vec4 sceneOverlayBloom(", 1)[1]
        assert "sceneOutputDither(texel)" in body
        # Gated on the glow actually added: a pixel without glow (a photograph, the empty card) stays exact.
        gate = body.split("sceneOutputDither(texel)", 1)[0].rsplit("\n", 1)[-1]
        assert "glow" in gate and "SCENE_DITHER_FLOOR" in gate
        # The shafts join the glow before the gate, so they are dithered too.
        if "uShafts" in source:
            assert body.index("uShaftColour") < body.index("sceneOutputDither(texel)")


def test_the_neon_sky_dithers_its_background_gradient():
    from rendering.gl_programs.neon_lake_basin_program import NEON_SKY_FRAGMENT_SOURCE

    background = NEON_SKY_FRAGMENT_SOURCE.split("FragColor=basinSkyBackground(", 1)[1].split("gl_FragDepth", 1)[0]
    assert "sceneOutputDither(ivec2(gl_FragCoord.xy))" in background

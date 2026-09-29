"""The bendable grid surface: a closed, consistently wound subdivision of the photograph,
denser on higher tiers, that draws the photograph exactly at rest and lights any bend.

GPU checks render offscreen through the transition capture harness; no window is shown.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs import scene3d as lib


@pytest.mark.parametrize("columns,rows", ((1, 1), (3, 2), (16, 9), (7, 12)))
def test_the_grid_tiles_the_photograph_once_with_one_winding(columns, rows):
    values = np.asarray(lib.scene3d_grid_vertices(columns, rows)).reshape(-1, 3, 2)
    assert len(values) == 2 * columns * rows
    assert values.min() == 0.0 and values.max() == 1.0
    a, b, c = values[:, 0], values[:, 1], values[:, 2]
    signed = 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    assert (np.sign(signed) == np.sign(signed[0])).all()          # one winding
    assert abs(np.abs(signed).sum() - 1.0) < 1e-9                  # covers the photograph exactly once
    edges = Counter()
    for triangle in values:
        points = [tuple(np.round(point * [columns, rows]).astype(int)) for point in triangle]
        for i in range(3):
            edges[tuple(sorted((points[i], points[(i + 1) % 3])))] += 1
    boundary = [edge for edge, count in edges.items() if count == 1]
    assert set(edges.values()) <= {1, 2}                           # closed: no crack, no overlap
    assert len(boundary) == 2 * (columns + rows)                   # only the photograph's outline is open


def test_grid_density_follows_the_tier_and_the_aspect():
    tiers = lib.SCENE3D_DETAIL_TIERS
    sizes = [lib.scene3d_grid_size(tiers[name], 16 / 9) for name in ("Performance", "Balanced", "High")]
    assert sizes[0][0] < sizes[1][0] < sizes[2][0]
    for tier in tiers.values():
        wide, tall = lib.scene3d_grid_size(tier, 16 / 9), lib.scene3d_grid_size(tier, 9 / 16)
        assert wide == (tall[1], tall[0])                         # square cells either way round
        assert wide[0] == tier.grid_cells and wide[1] < wide[0]
    assert min(lib.scene3d_grid_size(tiers["Performance"], 1000.0)) >= 2


def test_the_grid_source_needs_a_displacement():
    source = lib.scene3d_grid_vertex_source("vec3 sceneDisplace(vec2 uv) { return scenePlanePoint(uv, 1.0); }")
    assert source.startswith("#version 410 core\n") and source.count("void main()") == 1
    with pytest.raises(ValueError):
        lib.scene3d_grid_vertex_source("vec3 bend(vec2 uv) { return vec3(uv, 0.0); }")


_DECLARATIONS = "uniform float uTilt;\n"
_DISPLACE = """
vec3 sceneDisplace(vec2 uv) {
    vec3 point = scenePlanePoint(uv, uItemSize.x / uItemSize.y);
    point.z += uTilt * point.x;   // a plane leaning back toward its right edge
    return point;
}
"""
_PHOTO_FRAGMENT = """#version 410 core
in vec2 vUv; in vec3 vWorld; in vec3 vNormal;
out vec4 FragColor;
uniform sampler2D uImage;
uniform int uShowNormal;
void main() {
    FragColor = uShowNormal == 1 ? vec4(normalize(vNormal) * 0.5 + 0.5, 1.0) : texture(uImage, vUv);
}
"""


@pytest.mark.qt
def test_a_flat_grid_draws_the_photograph_and_a_bend_turns_its_normals(qt_app):
    from rendering.quick.scene3d.grid import draw_grid
    from rendering.quick.scene3d.resources import MeshResources, bind_frame
    from tools.transition_contact_sheet import TransitionCapture

    width, height = 256, 144
    capture = TransitionCapture(width, height)
    resources = MeshResources("grid test")
    try:
        run = capture.run("block_spins", direction="left")
        frame = capture.frame(run, 0.5)

        def read():
            pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            return np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(height, width, 4).astype(np.int16)

        def clear():
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glViewport(0, 0, width, height)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glClearColor(1.0, 0.0, 1.0, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        clear()
        resources.draw_image(frame, capture.textures[0])
        photograph = read()

        columns, rows = lib.scene3d_grid_size(lib.SCENE3D_DETAIL_TIERS["Performance"], width / height)
        program = resources.program("grid", lib.scene3d_grid_vertex_source(_DISPLACE, _DECLARATIONS), _PHOTO_FRAGMENT)
        names = ("uMatrix", "uItemSize", "uGridCells", "uImage", "uTilt", "uShowNormal")

        def draw(tilt, show_normal):
            clear()
            uniforms = resources.uniforms("grid", names)
            bind_frame(program, uniforms, frame)
            gl.glUniform2f(uniforms["uGridCells"], float(columns), float(rows))
            gl.glUniform1f(uniforms["uTilt"], tilt)
            gl.glUniform1i(uniforms["uShowNormal"], show_normal)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, capture.textures[0])
            gl.glUniform1i(uniforms["uImage"], 0)
            draw_grid(resources, columns, rows)
            return read()

        # At rest the subdivided surface is the photograph.
        assert np.abs(draw(0.0, 0) - photograph).max() <= 1
        # Its normal faces the viewer everywhere...
        flat = draw(0.0, 1)
        assert np.abs(flat[..., :3] - np.array([128, 128, 255])).max() <= 1
        # ...and follows a bend: leaning back to the right turns it toward -x, evenly.
        leaning = draw(0.4, 1)
        covered = ~((leaning[..., 0] == 255) & (leaning[..., 1] == 0) & (leaning[..., 2] == 255))   # not the clear
        assert covered.mean() > 0.5
        seen = leaning[..., 0][covered]
        assert seen.max() < 128 - 10 and seen.max() - seen.min() <= 2
        assert not np.array_equal(draw(0.4, 0), photograph)
    finally:
        resources.release_resources()
        capture.close()

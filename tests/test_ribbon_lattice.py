"""The ribbon sheet lattice: two diagonal line families woven in the sheet's own surface coordinates (offscreen)."""
from types import SimpleNamespace

import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from core.ribbon_ring import RibbonRing
from tests.test_ribbon_gpu import parallel_mvp
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.ribbon import RIBBON_BLOCK
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import RibbonMaterial, RibbonPrimitive
from rendering.quick.scene3d.target import SceneTarget
from tools.labs.render_target import OffscreenRenderTarget

pytestmark = pytest.mark.qt
W, H = 200, 120
VIEW = tuple(np.identity(4).flatten(order='F'))
MVP = parallel_mvp((2.5, 1.5), .1, 100)
# Everything but the lattice dark: what remains on screen is the lattice alone.
LATTICE_ONLY = dict(strand_light=0., rim_light=0., fill_light=0., rim_glow_light=0., glint_light=0., strand_warp=0.,
                    strand_jitter=0.)


@pytest.fixture
def scene(qt_app):
    target = OffscreenRenderTarget(W, H)
    parts = SimpleNamespace(target=target, primitive=RibbonPrimitive(), resources=MeshResources('lattice test', block_bytes=RIBBON_BLOCK.size),
                            scene=SceneTarget('lattice test'))
    parts.card = SimpleNamespace(viewport=(0, 0, W, H), logical_size=(float(W), float(H)),
                                 matrix_values=(2/W, 0, 0, 0, 0, -2/H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1), quad_vao=target.vao)
    yield parts
    with target.current():
        parts.primitive.release()
        parts.scene.release()
        parts.resources.release_resources()
    target.close()


def strip(*, start=0., emission=1., width=.6):
    ring = RibbonRing(1, colours=[(.2, .8, 1., 1.)])
    for i in range(6):
        ring.append(start + i, [(i - 2.5, 0., -10.)], width, 0., emission)
    return ring.packet()


def light(parts, packet, material):
    """The light pass alone (additive, no tone map): the material's own emitted light."""
    parts.target.bind(clear=(0., 0., 0., 0.))
    gl.glDisable(gl.GL_DEPTH_TEST)
    parts.primitive.draw(packet, MVP, shading='light', view=VIEW, material=material)
    return parts.target.read_rgba()[:, :, :3].astype(float)


def scene_render(parts, packet, material):
    """Body through OIT, then light with bloom and the scene's single tone map, as the Visualizer draws it."""
    parts.target.bind(clear=(0., 0., 0., 0.))
    with parts.scene.scope(parts.card, 4, parts.resources, overlay=1.0, bloom=.4, oit=True, hdr=1.0):
        gl.glViewport(0, 0, W, H)
        gl.glClearBufferfv(gl.GL_COLOR, 0, (0., 0., 0., 1.))
        gl.glEnable(gl.GL_DEPTH_TEST)
        with parts.scene.transparent_writes(parts.card, parts.resources):
            parts.primitive.draw(packet, MVP, shading='body', view=VIEW, material=material)
        with parts.scene.emission_writes():
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            gl.glDepthMask(gl.GL_FALSE)
            parts.primitive.draw(packet, MVP, shading='light', view=VIEW, material=material)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisablei(gl.GL_BLEND, 0)
    return parts.target.read_rgba()[:, :, :3].astype(float)


# A synthetic sheet: surface coordinates are linear in the pixel position, so the CPU knows where every line belongs.
SURFACE_VERTEX = '''#version 460 core
layout(location=0) out vec3 vWorld; layout(location=1) out vec3 vNormal; layout(location=2) out float vPhase;
layout(location=3) out float vAcross; layout(location=4) out float vEmission; layout(location=5) out float vLocal;
layout(location=6) out float vCoverage; layout(location=7) out float vExpanded; layout(location=8) out float vFaceScale;
layout(location=9) flat out vec4 vColour; layout(location=10) flat out vec4 vColourB; layout(location=11) out vec4 vTint;
uniform vec3 uSheet;  // phase per pixel, across per pixel, phase offset
void main() {
    vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2)*2.0-1.0;
    gl_Position=vec4(p,0,1);
    vec2 pixel=p*vec2(100,60);
    vPhase=uSheet.z+pixel.x*uSheet.x;
    vAcross=.5+pixel.y*uSheet.y;
    vWorld=vec3(0,0,-10); vNormal=vec3(0,0,1); vEmission=.6; vLocal=0;
    vCoverage=1; vExpanded=0; vFaceScale=1; vColour=vec4(1); vColourB=vec4(1); vTint=vec4(0);
}
'''


def surface(parts, material, phase_per_pixel, across_per_pixel, phase_offset=0.):
    from rendering.gl_programs.ribbon import RIBBON_LIGHT_FRAGMENT
    parts.target.bind(clear=(0., 0., 0., 0.))
    program = parts.resources.program('lattice surface', SURFACE_VERTEX, RIBBON_LIGHT_FRAGMENT)
    gl.glUseProgram(program)
    gl.glUniform3f(gl.glGetUniformLocation(program, 'uSheet'), phase_per_pixel, across_per_pixel, phase_offset)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glDisable(gl.GL_BLEND)
    gl.glBindVertexArray(parts.target.vao)
    with parts.resources.pass_blocks.bound(pack_block(RIBBON_BLOCK, material.uniforms())):
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
    image = parts.target.read_rgba()[:, :, 0].astype(float)
    # Rows inside the sheet (across in 0..1) and away from its rims.
    return image[H//2 - 25:H//2 + 25, 10:W - 10]


def expected_lines(material, phase_per_pixel, across_per_pixel, phase_offset=0.):
    """CPU mirror of where the two diagonal families lie, in the readback's (bottom-up) pixel rows."""
    y, x = np.indices((H, W), dtype=float)
    pixel_x, pixel_y = x + .5 - W/2, y + .5 - H/2
    u = (.5 + pixel_y*across_per_pixel)*material.lattice_cells
    v = (phase_offset + pixel_x*phase_per_pixel)*material.lattice_along
    near = lambda f: np.abs(f - np.floor(f) - .5)  # lines sit mid-spacing, like the strands
    lines = np.minimum(near(u + v), near(u - v))
    return lines[H//2 - 25:H//2 + 25, 10:W - 10]


def test_lattice_values_are_validated_and_published_as_uniforms():
    material = RibbonMaterial()
    uniforms = material.uniforms()
    assert uniforms['uLattice'] == (material.lattice_cells, material.lattice_along, material.lattice_half_width,
                                    material.lattice_light)
    assert uniforms['uLatticeTone'] == (material.lattice_reactivity, material.lattice_glow)
    for bad in (dict(lattice_cells=0.), dict(lattice_cells=float('inf')), dict(lattice_along=2.5),
                dict(lattice_along=0.), dict(lattice_half_width=0.), dict(lattice_half_width=.6),
                dict(lattice_light=-1.), dict(lattice_light=float('nan')), dict(lattice_glow=1.1),
                dict(lattice_reactivity=-.1), dict(lattice_cells=True)):
        with pytest.raises(ValueError):
            RibbonMaterial(**bad)


def test_lattice_uniforms_reach_the_light_pass(scene):
    packet = strip()
    off = light(scene, packet, RibbonMaterial(**LATTICE_ONLY, lattice_light=0.))
    on = light(scene, packet, RibbonMaterial(**LATTICE_ONLY, lattice_light=1.))
    assert not off.any() and on.sum() > 0
    program = scene.primitive.resources._programs['light']
    assert gl.glGetUniformBlockIndex(program, RIBBON_BLOCK.name) != gl.GL_INVALID_INDEX
    for name in ('uLattice', 'uLatticeTone'):
        assert name in dict(RIBBON_BLOCK.fields)


def test_lattice_lines_lie_on_the_sheet_coordinates_and_travel_with_its_phase(scene):
    material = RibbonMaterial(**LATTICE_ONLY, strands=1., lattice_light=1., lattice_cells=4., lattice_along=4.,
                              lattice_half_width=.08)
    phase, across = .004, .01  # ~15 px between lines: resolved
    for offset in (0., .037):
        image = surface(scene, material, phase, across, offset)
        distance = expected_lines(material, phase, across, offset)
        on_line, off_line = image[distance < .03], image[distance > .2]
        assert on_line.mean() > 4*max(off_line.mean(), 1.), (offset, on_line.mean(), off_line.mean())
    # Advancing the phase moves the net along the sheet (no screen-space pattern stays put).
    still, moved = surface(scene, material, phase, across, 0.), surface(scene, material, phase, across, .037)
    assert np.abs(still - moved).mean() > .2*still.mean()


def test_unresolved_lattice_settles_into_an_even_glow_with_its_average_light(scene):
    resolved = RibbonMaterial(**LATTICE_ONLY, strands=1., lattice_light=1., lattice_cells=4., lattice_along=4.,
                              lattice_half_width=.1)
    fine = RibbonMaterial(**LATTICE_ONLY, strands=1., lattice_light=1., lattice_cells=128., lattice_along=64.,
                          lattice_half_width=.1)
    coarse = surface(scene, resolved, .004, .01)
    dense = surface(scene, fine, .004, .01)  # spacings of a fraction of a pixel
    # No aliased moire: an even sheet; and no energy pops while lines shrink below a pixel.
    assert dense.std() < .1*dense.mean(), (dense.std(), dense.mean())
    assert .6 < dense.mean()/coarse.mean() < 1.4, (dense.mean(), coarse.mean())
    # Half-pixel motion of a resolved net keeps its total light (no shimmer as lines cross pixel centres).
    shifted = surface(scene, resolved, .004, .01, .5*.004)
    assert abs(shifted.mean()/coarse.mean() - 1.) < .05


def test_lattice_is_attached_to_the_absolute_path_coordinate_across_phase_rebases(scene):
    material = RibbonMaterial(**LATTICE_ONLY, lattice_light=1.)
    # A whole number of strand periods apart: the packet's phase origin differs, the woven net may not.
    a = light(scene, strip(start=.25), material)
    b = light(scene, strip(start=3.25), material)
    np.testing.assert_allclose(a, b, atol=1.)
    c = light(scene, strip(start=.4), material)  # a different place along the history
    assert np.abs(a - c).mean() > .05*a.mean()


def test_lattice_brightens_with_the_music_only_above_quiet_emission(scene):
    calm, reactive = (RibbonMaterial(**LATTICE_ONLY, lattice_light=.3, lattice_reactivity=r) for r in (0., 3.))
    quiet = strip(emission=.6)
    np.testing.assert_array_equal(light(scene, quiet, calm), light(scene, quiet, reactive))
    loud = strip(emission=1.5)
    assert light(scene, loud, reactive).sum() > 1.5*light(scene, loud, calm).sum()


def test_lattice_bloom_share_is_separate_from_the_sheet(scene):
    packet = strip(emission=2.)
    low = scene_render(scene, packet, RibbonMaterial(**LATTICE_ONLY, lattice_light=1., lattice_glow=0.))
    high = scene_render(scene, packet, RibbonMaterial(**LATTICE_ONLY, lattice_light=1., lattice_glow=1.))
    # The bloom spills beyond the sheet: rows beside it get more halo with a larger glow share.
    rows = np.abs(np.arange(H) + .5 - H/2)
    halo = (rows > 28) & (rows < 50)
    assert high[halo].sum() > low[halo].sum()

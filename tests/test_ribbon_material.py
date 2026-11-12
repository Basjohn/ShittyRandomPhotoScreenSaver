"""Native proof of the ribbon filament material through the Visualizer-shaped scene scope (offscreen)."""
from types import SimpleNamespace

import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from core.ribbon_ring import RibbonRing
from tests.test_ribbon_gpu import parallel_mvp
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import RibbonMaterial, RibbonPrimitive
from rendering.quick.scene3d.target import SceneTarget
from tools.labs.render_target import OffscreenRenderTarget

pytestmark = pytest.mark.qt
W, H = 200, 120
VIEW = tuple(np.identity(4).flatten(order='F'))  # eye at the origin looking down -z
MVP = parallel_mvp((2.5, 1.5), .1, 100)


def strip(y, z, colour, *, width=.3, emission=1.):
    ring = RibbonRing(1, colours=[colour])
    for i in range(6):
        ring.append(i, [(i - 2.5, y, z)], width, 0., emission)
    return ring.packet()


@pytest.fixture
def scene(qt_app):
    target = OffscreenRenderTarget(W, H)
    parts = SimpleNamespace(target=target, primitive=RibbonPrimitive(), resources=MeshResources('material test'),
                            scene=SceneTarget('material test'))
    parts.card = SimpleNamespace(viewport=(0, 0, W, H), logical_size=(float(W), float(H)),
                                 matrix_values=(2/W, 0, 0, 0, 0, -2/H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1), quad_vao=target.vao)
    yield parts
    with target.current():
        parts.primitive.release()
        parts.scene.release()
        parts.resources.release_resources()
    target.close()


def render(parts, packets, *, opaque=None, material=None):
    """Body through OIT, then additive light, as the Visualizer draws it; optional opaque strip first."""
    parts.target.bind(clear=(0., 0., 0., 0.))
    with parts.scene.scope(parts.card, 4, parts.resources, overlay=1.0, bloom=.4, oit=True, hdr=1.0):
        gl.glViewport(0, 0, W, H)
        gl.glClearBufferfv(gl.GL_COLOR, 0, (.01, .01, .02, 1.))
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDepthMask(gl.GL_TRUE)
        if opaque is not None:
            parts.primitive.draw(opaque, MVP)
        with parts.scene.transparent_writes(parts.card, parts.resources):
            for packet in packets:
                parts.primitive.draw(packet, MVP, shading='body', view=VIEW, material=material)
        with parts.scene.emission_writes():
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            gl.glDepthMask(gl.GL_FALSE)
            for packet in packets:
                parts.primitive.draw(packet, MVP, shading='light', view=VIEW, material=material)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisablei(gl.GL_BLEND, 0)
    return parts.target.read_rgba().astype(int)


def test_header_alpha_fades_body_coverage_and_zero_removes_it(scene):
    material = RibbonMaterial(body_alpha=.4, strand_light=0., rim_light=0., fill_light=0.,
                              rim_glow_light=0., glint_light=0.)
    background = render(scene, [], material=material)
    full = render(scene, [strip(0.,-5.,(.1,.7,.9,1.),emission=0.)], material=material)
    half = render(scene, [strip(0.,-5.,(.1,.7,.9,.5),emission=0.)], material=material)
    zero = render(scene, [strip(0.,-5.,(.1,.7,.9,0.),emission=0.)], material=material)
    np.testing.assert_array_equal(zero, background)
    assert np.abs(full-background).sum() > np.abs(half-background).sum() > 0


def test_crossing_ribbons_give_the_same_picture_in_either_order_and_brighten(scene):
    cyan = strip(0., -10., (.1, .7, 1., 1.))
    magenta = strip(.15, -12., (.9, .2, .9, 1.))
    forward, backward = render(scene, [cyan, magenta]), render(scene, [magenta, cyan])
    assert np.abs(forward - backward).max() <= 1
    alone = render(scene, [cyan])
    column = W//2
    # Where both sheets cover the pixel, light adds: brighter than either alone, and still finite colour.
    rows = np.where((forward[:, column, :3].sum(1) > 0))[0]
    assert rows.size and forward[:, column, :3].sum(1).max() > alone[:, column, :3].sum(1).max()


def test_opaque_geometry_in_front_hides_body_and_light(scene):
    glowing = strip(0., -12., (.1, .7, 1., 1.), emission=4.)
    wall = strip(0., -5., (0., 1., 0., 1.), width=.6)  # opaque diagnostic strip, nearer, writes depth
    covered, bare, behind = render(scene, [glowing], opaque=wall), render(scene, [], opaque=wall), render(scene, [glowing])
    centre = np.s_[H//2, W//2 - 20:W//2 + 20]
    assert behind[centre][:, 2].min() > 100  # the glowing strip is bright where the wall will be
    # Through the (tone-mapped) wall nothing of the strip behind shows: bloom spill may only touch its edges.
    assert np.abs(covered[centre] - bare[centre]).max() <= 2


def test_extreme_hdr_overlap_stays_finite(scene):
    hot = [strip(0., -10. - i*.2, (1., 1., 1., 1.), width=.5, emission=64.) for i in range(8)]
    pixels = render(scene, hot, material=RibbonMaterial(strand_light=8., rim_light=8., body_alpha=.9))
    centre = pixels[H//2 - 5:H//2 + 5, W//2 - 20:W//2 + 20]
    # NaN/inf accumulation resolves to black holes or garbage; saturated light must read as white.
    assert (centre[:, :, :3] >= 200).all()


def test_material_programs_compile_only_when_used_and_inputs_are_validated(scene):
    packet = strip(0., -10., (.1, .7, 1., 1.))
    scene.target.bind()
    scene.primitive.draw(packet, MVP)
    assert scene.primitive.resources.has_program('diagnostic')
    assert not scene.primitive.resources.has_program('body') and not scene.primitive.resources.has_program('light')
    with pytest.raises(ValueError, match='view matrix'):
        scene.primitive.draw(packet, MVP, shading='light')
    with pytest.raises(ValueError):
        scene.primitive.draw(packet, MVP, shading='glow', view=VIEW)
    for bad in (dict(strands=0), dict(body_alpha=1.), dict(rim_light=-1.), dict(strand_half_width=float('nan')),
                dict(cross_curve=1.1), dict(strand_variation=1.1)):
        with pytest.raises(ValueError):
            RibbonMaterial(**bad)
    from rendering.quick.scene3d.ribbon import _sweep_axis
    assert _sweep_axis((1e308,0.,0.)) == (1.,0.,0.)
    np.testing.assert_allclose(_sweep_axis((1.7e308,1.7e308,0.)), (2**-.5,2**-.5,0.))
    for axis in ((0.,0.,0.), (1.,2.), (1.,float('nan'),0.)):
        with pytest.raises(ValueError):
            scene.primitive.draw(packet,MVP,sweep_axis=axis)


def test_native_filament_coordinates_never_reverse_even_at_maximum_gather(scene):
    from rendering.gl_programs.ribbon import RIBBON_STRAND_COORDINATE_GLSL
    # Evaluate the actual GLSL over width and phase; reversing this mapping produces sharp folds in the lines.
    source = '#version 460 core\n' + RIBBON_STRAND_COORDINATE_GLSL + '''
layout(local_size_x=64) in;
layout(std430,binding=1) buffer Results { float values[]; };
void main() {
    uint i=gl_GlobalInvocationID.x;
    float across=float(i%257U)/256.0, phase=float(i/257U)/32.0;
    values[i]=ribbonStrandCoordinate(across,phase,4.0,1.0,.9);
}
'''
    scene.target.bind()
    program = scene.resources.compute_program('monotone strands', source)
    count = 257*33
    allocation = ((count+63)//64)*64
    buffer = int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0])
    try:
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
        gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,allocation*4,None,gl.GL_STREAM_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,1,buffer)
        gl.glUseProgram(program)
        gl.glDispatchCompute(allocation//64,1,1)
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
        values = np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER,0,count*4),np.float32).reshape(33,257)
        assert np.isfinite(values).all() and (np.diff(values,axis=1)>0).all()
    finally:
        gl.glUseProgram(0)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,1,0)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,0)
        gl.glDeleteBuffers(1,[buffer])



def test_edge_on_slivers_cannot_overflow_into_the_bloom(qt_app):
    # The probe's high scene folds sheets edge-on: MSAA shades sliver pixels at centres far outside the triangle.
    # Unclamped across-width inputs there overflowed exp() to infinity and the bloom spread solid colour blocks.
    from tools.labs import ribbon_material_probe as probe
    target = OffscreenRenderTarget(640, 709)
    primitive, resources, scene = RibbonPrimitive(), MeshResources('sliver test'), SceneTarget('sliver test')
    try:
        for state in probe.STATES:  # without the clamp the low scene showed 4862 garbage pixels, high none
            pixels, _ = probe.render(primitive, target, resources, scene, probe.card_frame(target, 640, 709),
                                     (640, 709), state, RibbonMaterial())
            rgb = pixels[:, :, :3].astype(int)
            garbage = (rgb.max(2) >= 250) & (np.sort(rgb, axis=2)[:, :, 1] < 20)  # a saturated pure primary/secondary
            assert rgb.max() > 200 and not garbage.any(), state
    finally:
        with target.current():
            primitive.release()
            scene.release()
            resources.release_resources()
        target.close()


def test_history_sparks_cover_the_whole_ribbon_statelessly(scene):
    # Sparks re-emit for as long as their knot lives (knots are born far off view at a flowing head), are gated by
    # per-knot sparkle, and are a pure function of the packet and the clock: no state, nothing per tick.
    from rendering.quick.scene3d.ribbon import RibbonSparks
    sparks = RibbonSparks(light=40., lifetime=2., per_knot=12, rise=0.)

    def draw(sparkle, now):
        ring = RibbonRing(1)
        for i in range(48):
            ring.append(i*.25, [(i*.1 - 2.4, 0., -10.)], .3, 0., 1., sparkle)
        scene.target.bind(clear=(0., 0., 0., 1.))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_ONE, gl.GL_ONE)
        scene.primitive.draw(ring.packet(), MVP, shading='sparks', sparks=sparks, now=now)
        gl.glDisable(gl.GL_BLEND)
        return scene.target.read_rgba()[:, :, :3].max(2) > 30
    lit = draw(1., 11.75)
    columns = np.where(lit.any(0))[0]
    # The oldest knots (11.75 s old, far beyond the 2 s lifetime) still carry sparks: across most of the ribbon.
    assert lit.sum() > 40 and columns.min() < W*.3 and columns.max() > W*.7
    assert not draw(0., 11.75).any()
    np.testing.assert_array_equal(lit, draw(1., 11.75))
    assert (lit != draw(1., 12.6)).any()


def test_both_boundary_filaments_keep_their_light_on_a_curved_quiet_sheet(scene):
    # The two boundaries have different normals on a bowed sheet. Multiplying their light by the sheet's
    # grazing path length made one bright and the other disappear, despite identical authored boundary light.
    ring=RibbonRing(1,colours=[(1.,1.,1.,1.)])
    for i in range(6):
        ring.append(i,[(i-2.5,0.,-10.)],.6,.6,.2)
    material=RibbonMaterial(cross_curve=.35,strand_light=0.,fill_light=0.,rim_glow_light=0.,
                            glint_light=0.,rim_light=1.,rim_white=1.,lattice_light=0.)
    scene.target.bind(clear=(0.,0.,0.,0.))
    gl.glDisable(gl.GL_DEPTH_TEST)
    scene.primitive.draw(ring.packet(),MVP,shading='light',view=VIEW,material=material,sweep_axis=(1.,0.,0.))
    profile=scene.target.read_rgba()[:,W//2,0].astype(float)
    rows=np.where(profile>2)[0]
    groups=np.split(rows,np.where(np.diff(rows)>1)[0]+1)
    assert len(groups)==2
    energies=[profile[g].sum() for g in groups]
    assert min(energies)>15 and max(energies)/min(energies)<1.25, energies


def test_surface_glints_stay_round_when_sheet_coordinates_are_skewed(scene):
    from rendering.gl_programs.ribbon import RIBBON_LIGHT_FRAGMENT
    # Feed the production fragment a sheared surface coordinate grid. Orthogonal per-coordinate fwidths
    # make its glint a diagonal dash; screen-space distance must recover a round point in the centre cell.
    vertex = '''#version 460 core
layout(location=0) out vec3 vWorld; layout(location=1) out vec3 vNormal; layout(location=2) out float vPhase;
layout(location=3) out float vAcross; layout(location=4) out float vEmission; layout(location=5) out float vLocal;
layout(location=6) out float vCoverage; layout(location=7) out float vExpanded; layout(location=8) out float vFaceScale;
layout(location=9) flat out vec4 vColour; layout(location=10) flat out vec4 vColourB; layout(location=11) out vec4 vTint;
void main() {
    vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2)*2.0-1.0;
    gl_Position=vec4(p,0,1);
    vec2 pixel=p*vec2(100,60);
    float h=fract(sin(3.1)*43758.5453);
    vPhase=.5-h*7.0+pixel.x*.01+pixel.y*.035;
    vAcross=.5+pixel.y*.01;
    vWorld=vec3(0,0,-10); vNormal=vec3(0,0,1); vEmission=.2; vLocal=0;
    vCoverage=1; vExpanded=0; vFaceScale=1; vColour=vec4(1); vColourB=vec4(1); vTint=vec4(0);
}
'''
    material=RibbonMaterial(strands=1.,strand_warp=0.,strand_light=0.,rim_light=0.,rim_glow_light=0.,
                            fill_light=0.,glint_density=1.,glint_chance=1.,glint_light=1.,
                            glint_radius=.03,glint_min_pixels=3.)
    scene.target.bind(clear=(0.,0.,0.,0.))
    from rendering.gl_programs.portable import pack_block
    from rendering.gl_programs.ribbon import RIBBON_BLOCK
    from rendering.quick.scene3d.uniforms import PassBlocks
    program=scene.resources.program('skewed glint',vertex,RIBBON_LIGHT_FRAGMENT)
    gl.glUseProgram(program)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glDisable(gl.GL_BLEND)
    gl.glBindVertexArray(scene.target.vao)
    blocks=PassBlocks('skewed glint',block_bytes=RIBBON_BLOCK.size)
    with blocks.bound(pack_block(RIBBON_BLOCK,material.uniforms())):
        gl.glDrawArrays(gl.GL_TRIANGLES,0,3)
    blocks.release()
    crop=scene.target.read_rgba()[H//2-15:H//2+15,W//2-15:W//2+15,0].astype(float)
    y,x=np.indices(crop.shape,dtype=float)
    assert crop.sum()>30
    x-=np.sum(x*crop)/crop.sum(); y-=np.sum(y*crop)/crop.sum()
    covariance=np.array([[np.sum(x*x*crop),np.sum(x*y*crop)],
                         [np.sum(x*y*crop),np.sum(y*y*crop)]])/crop.sum()
    eigenvalues=np.linalg.eigvalsh(covariance)
    assert eigenvalues[-1]/eigenvalues[0]<1.3, eigenvalues


def test_light_pass_alpha_carries_luminance_weighted_world_height(scene):
    # Reflection receivers recover the height of reflected light as alpha/luminance (contact hardening).
    # The packet's own rebased origin and the caller's frame both count; scene targets keep their alpha.
    from rendering.quick.scene3d.reflection import PlanarReflection
    reflection = PlanarReflection('height test')
    try:
        for height in (.6, 1.8):
            scene.target.bind()
            reflection.begin(W, H)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            scene.primitive.draw(strip(height - 1., -10., (.1, .7, 1., 1.)), MVP, shading='light', view=VIEW,
                                 mist_frame=(0., 1., 0.))
            gl.glDisablei(gl.GL_BLEND, 0)
            reflection.end()
            pixels = np.empty((H, W, 4), np.float32)
            gl.glGetTextureImage(reflection.texture, 0, gl.GL_RGBA, gl.GL_FLOAT, pixels.nbytes, pixels)
            luminance = pixels[..., :3] @ np.array((.2126, .7152, .0722), np.float32)
            lit = luminance > .05
            assert lit.sum() > 100
            np.testing.assert_allclose(pixels[..., 3][lit].sum()/luminance[lit].sum(), height, rtol=.02)
    finally:
        with scene.target.current():
            reflection.release()


def _light_only(parts, packet, **draw):
    parts.target.bind(clear=(0., 0., 0., 0.))
    gl.glViewport(0, 0, W, H)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glEnablei(gl.GL_BLEND, 0)
    gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
    parts.primitive.draw(packet, MVP, shading='light', view=VIEW, **draw)
    gl.glDisablei(gl.GL_BLEND, 0)
    return parts.target.read_rgba().astype(int)


def test_floor_contact_deforms_a_sheet_onto_the_floor_instead_of_through_it(scene):
    # The strip's centre is below the floor (world y 0, screen row H/2): without contact it is drawn there; with
    # contact every lit row stays above the floor and the sheet is still drawn (squashed, not culled).
    sunk = strip(-.5, -10., (.1, .7, 1., 1.))
    free = _light_only(scene, sunk)
    pressed = _light_only(scene, sunk, floor=(0., .03, .2))
    rows = lambda image: np.nonzero(image[..., :3].max(axis=(1, 2)) > 20)[0]
    assert rows(free).max() > H//2 + 10
    assert rows(pressed).size > 0 and rows(pressed).max() <= H//2
    with pytest.raises(ValueError):
        _light_only(scene, sunk, floor=(0., .03, 0.))


def test_grade_nodes_colour_the_sheet_across_world_x(scene):
    from rendering.quick.scene3d.ribbon import ribbon_grade
    nodes = ((0., (1., 0., 0.)), (.5, (0., 1., 0.)), (1., (0., 0., 1.)))
    image = _light_only(scene, strip(0., -10., (1., 1., 1., 1.)), grade=ribbon_grade(nodes, (-2., 2.), 1.))
    lit = image[..., :3].max(axis=2) > 20
    for column, channel in ((int(W*.12), 0), (W//2, 1), (int(W*.88), 2)):
        colour = image[lit[:, column], column, :3].sum(axis=0)
        assert colour.argmax() == channel
    for bad in (((.5, (1., 0., 0.)), (.5, (0., 1., 0.))), ((0., (2., 0., 0.)),), ()):
        with pytest.raises(ValueError):
            ribbon_grade(bad, (-2., 2.), 1.)


def test_free_strands_follow_sparkle_and_leave_the_sheet(scene):
    from rendering.quick.scene3d.ribbon import RibbonStrays

    def sheet(sparkle):
        ring = RibbonRing(1, colours=[(1., .5, .1, 1.)])
        for i in range(24):
            ring.append(i*.25, [(i*.2 - 2.3, 0., -10.)], .15, 0., 1., sparkle)
        return ring.packet()
    strays = RibbonStrays(per_knot=4, length=4., reach=.8, chance=1., width=2., light=4., peel_time=.5)
    rows = lambda image: np.nonzero(image[..., :3].max(axis=(1, 2)) > 20)[0]
    for sparkle, expect in ((0., False), (1., True)):
        scene.target.bind(clear=(0., 0., 0., 0.))
        gl.glViewport(0, 0, W, H)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnablei(gl.GL_BLEND, 0)
        gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
        scene.primitive.draw(sheet(sparkle), MVP, shading='strays', strays=strays, now=12., view=VIEW)
        gl.glDisablei(gl.GL_BLEND, 0)
        lit = rows(scene.target.read_rgba().astype(int))
        assert (lit.size > 0) == expect
        if expect:  # the sheet spans 0.3 world units (12 rows); peeled strands reach well beyond it
            assert lit.max() - lit.min() > 24
    with pytest.raises(ValueError):
        RibbonStrays(per_knot=9)


def test_glow_sends_more_light_to_the_bloom_without_brightening_the_sheet(scene):
    packet = strip(0., -10., (.2, .5, 1., 1.), width=.2)
    plain, glowing = (render(scene, [packet], material=RibbonMaterial(glow=g)) for g in (1., 3.))
    rows = np.arange(H)
    # Strip rows +-0.2 world units around the centre (H/2); bloom spreads light well beyond them.
    inside, outside = abs(rows - H//2) <= 6, (abs(rows - H//2) >= 14) & (abs(rows - H//2) <= 30)
    assert glowing[outside, 40:-40, :3].sum() > 1.5*plain[outside, 40:-40, :3].sum()
    assert glowing[inside, 40:-40, :3].sum() < 1.6*plain[inside, 40:-40, :3].sum()
    with pytest.raises(ValueError):
        RibbonMaterial(hot=1.5)

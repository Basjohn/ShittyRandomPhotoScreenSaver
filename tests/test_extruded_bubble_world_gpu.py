"""Native production sphere/union geometry, opacity and near-layer admission."""
import math

import numpy as np
import pytest


@pytest.fixture
def sphere_pixels(qt_app, request):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import (
        BUBBLE_VERTEX, BUBBLE_FRAGMENT, CLUSTER_VERTEX, CLUSTER_FRAGMENT,
        NEAR_FRAGMENT, NEAR_CLUSTER_FRAGMENT,
    )
    from rendering.gl_programs.extruded_bubble_scene import camera
    from rendering.quick.render.gl_resources import compile_program
    from rendering.quick.visualizer.implementations.extruded_bubble import _near_spread
    from tools.transition_contact_sheet import TransitionCapture

    width,height=getattr(request,'param',(480,320))
    target=TransitionCapture(width,height)
    programs={}; texture=vao=cube=circle_texture=0
    try:
        texture=int(gl.glGenTextures(1));gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,width,height,0,gl.GL_RGBA,gl.GL_FLOAT,None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,target.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,texture,0)
        gl.glDrawBuffers(1,[gl.GL_COLOR_ATTACHMENT0])
        circle_texture=int(gl.glGenTextures(1));gl.glBindTexture(gl.GL_TEXTURE_2D,circle_texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,width,height,0,gl.GL_RGBA,gl.GL_FLOAT,None)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT1,gl.GL_TEXTURE_2D,circle_texture,0)
        gl.glBindTexture(gl.GL_TEXTURE_2D,target.textures[0])
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D,0,0,0,width,height,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,
                          np.full((height,width,4),128,dtype='u1'))
        cube=int(gl.glGenTextures(1));gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP,cube)
        for face in range(6):
            gl.glTexImage2D(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X+face,0,gl.GL_RGBA8,4,4,0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,
                            np.full((4,4,4),127,dtype='u1'))
        gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        vao=int(gl.glGenVertexArrays(1));gl.glBindVertexArray(vao)
        for kind,vertex,fragment in (('ordinary',BUBBLE_VERTEX,BUBBLE_FRAGMENT),('cluster',CLUSTER_VERTEX,CLUSTER_FRAGMENT),
                                     ('near',BUBBLE_VERTEX,NEAR_FRAGMENT),('near_cluster',CLUSTER_VERTEX,NEAR_CLUSTER_FRAGMENT)):
            programs[kind]=compile_program(vertex,fragment,label='physical geometry '+kind)
        tan=camera(0,0,width/height)[2];projection=camera(0,0,width/height)[3]
        gl.glViewport(0,0,width,height)
        for option in (gl.GL_BLEND,gl.GL_DEPTH_TEST,gl.GL_CULL_FACE):gl.glDisable(option)

        def draw(kind,centre=(0.,0.,-6.),radius=.6,alpha=1.,second=None,alphas=None,diag=5,
                 circle=False,composite=False,orientation=None,extra=(.3,0.),**uniforms):
            from rendering.quick.scene3d.defocus import DefocusLayer
            budget=_near_spread(height)
            layer=DefocusLayer('native EB lens protection') if composite else None
            if layer is not None:
                layer.begin(width,height)
            else:
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,target.fbo)
                gl.glDrawBuffers(2 if kind.startswith('near') else 1,
                                 [gl.GL_COLOR_ATTACHMENT0,gl.GL_COLOR_ATTACHMENT1] if kind.startswith('near')
                                 else [gl.GL_COLOR_ATTACHMENT0])
            program=programs[kind];gl.glUseProgram(program)
            loc=lambda key:gl.glGetUniformLocation(program,key)
            for name,value in {'uPixel':2*tan[1]/height,'uPixelSize':2*tan[1]/height,'uCrisp':1.,
                               'uEye':(0.,0.,0.),
                               'uFocus':0.,'uAperture':0.,'uNearCoc':22.*height/941.,'uNearMax':budget,
                               'uNearLayer':float(kind.startswith('near')),'uNearGain':1.,'uProbeLevels':1.,
                               'uLens':1.,'uReflect':.5,'uBehind':8.,'uFrameShare':1.,'uShell':.03,**uniforms}.items():
                if isinstance(value, tuple):
                    gl.glUniform3f(loc(name), *value)
                else:
                    gl.glUniform1f(loc(name),value)
            gl.glUniform1i(loc('uDiag'),diag)
            gl.glUniform1i(loc('uProbe'),2);gl.glUniform1i(loc('uBackground'),0);gl.glUniform1i(loc('uEnvironment'),0)
            gl.glUniform3f(loc('uIors'),1.15,2.,1.)
            gl.glUniform2f(loc('uFrameSize'),width,height);gl.glUniform2f(loc('uTargetSize'),width,height)
            gl.glUniform2f(loc('uTan'),*tan)
            basis = np.eye(3) if orientation is None else np.asarray(orientation)
            for name, matrix in (('uWorldToView', basis.T), ('uViewToWorld', basis)):
                gl.glUniformMatrix3fv(loc(name), 1, False, np.asarray(matrix, dtype='f4').ravel(order='F'))
            gl.glUniformMatrix4fv(loc('uProjection'),1,False,projection)
            gl.glVertexAttrib4f(0,*centre,radius)
            if kind in ('ordinary','near'):
                gl.glVertexAttrib2f(1,*extra);gl.glVertexAttrib1f(2,alpha);gl.glVertexAttrib1f(3,radius)  # steady lens radius = the drawn one
            else:
                gl.glVertexAttrib4f(1,*(second or (*centre,1e-6)))
                gl.glVertexAttrib4f(2,0,0,0,0)
                gl.glVertexAttrib4f(3,2,0,.3,0)
                gl.glVertexAttrib3f(4,*(alphas or (alpha,alpha,0.)))
            gl.glClearColor(0,0,0,0);gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,1)
            if layer is not None:
                layer.end()
                gl.glClearColor(0,0,0,0);gl.glClear(gl.GL_COLOR_BUFFER_BIT)
                layer.composite(budget)
            gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
            raw=gl.glReadPixels(0,0,width,height,gl.GL_RGBA,gl.GL_FLOAT)
            pixels=np.frombuffer(raw,dtype='f4').reshape(height,width,4)
            assert np.isfinite(pixels).all() and gl.glGetError()==gl.GL_NO_ERROR
            coverage=np.divide(pixels[:,:,0],pixels[:,:,3],out=np.zeros((height,width),dtype='f4'),where=pixels[:,:,3]>1e-10)
            if circle:
                gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT1)
                coverage=np.frombuffer(gl.glReadPixels(0,0,width,height,gl.GL_RGBA,gl.GL_FLOAT),dtype='f4').reshape(height,width,4)
                gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
            if layer is not None:
                layer.release()
            return pixels,coverage
        draw.frame_size=(width,height)
        draw.near_budget=_near_spread(height)
        yield draw
    finally:
        for program in programs.values():gl.glDeleteProgram(program)
        if vao:gl.glDeleteVertexArrays(1,[vao])
        if texture:gl.glDeleteTextures([texture])
        if circle_texture:gl.glDeleteTextures([circle_texture])
        if cube:gl.glDeleteTextures([cube])
        target.close()


@pytest.mark.qt
def test_ordinary_and_fused_coverage_share_true_pinhole_projection(sphere_pixels):
    from rendering.gl_programs.extruded_bubble_scene import camera

    tan = camera(0., 0., 480 / 320)[2]
    # The former (-4,-2.4,-6) fixture was clipped on two edges at 45 degrees:
    # a visible ellipse fragment cannot satisfy a whole-ellipse covariance oracle.
    for centre in ((0.,0.,-6.),(-2.8,-1.6,-6.),(2.8,1.6,-6.)):
        radius = .6
        depth = -centre[2]
        denominator = depth * depth - radius * radius
        for axis, half_angle in enumerate(tan):
            root = math.sqrt(centre[axis] ** 2 + denominator)
            bounds = [(centre[axis] * depth + side * radius * root) /
                      (denominator * half_angle) for side in (-1., 1.)]
            assert -0.95 < bounds[0] < bounds[1] < 0.95, "whole silhouette must fit"
        ratios=[]
        for kind in ('ordinary','cluster'):
            _,coverage=sphere_pixels(kind,centre)
            yy,xx=np.nonzero(coverage>.5)
            eigen=np.linalg.eigvalsh(np.cov(np.vstack((xx,yy)),bias=True))
            ratios.append(math.sqrt(eigen[1]/eigen[0]))
        expected=math.sqrt(1+(centre[0]**2+centre[1]**2)/(centre[2]**2-.6**2))
        assert ratios==pytest.approx((expected,expected),abs=.02)


@pytest.mark.qt
@pytest.mark.parametrize('kind', ['ordinary', 'cluster'])
def test_small_shell_keeps_authored_wall_geometry(sphere_pixels, kind):
    # ~4px radius: the former 1.5px wall floor silently replaced both material
    # thicknesses with the same ~39%-radius solid-looking wall. Filtering may
    # widen the optical lookup, but must not change the traced inner sphere.
    samples = [sphere_pixels(kind, radius=.06, diag=2, uShell=wall,
                             uSpecThrough=1., uSpecColour=(1., 1., 1.),
                             uLightDir=(.25, .8, .5), uSpecShape=(.05, .25, .012))[0]
               for wall in (.03, .3)]
    assert np.abs(samples[1] - samples[0]).sum() > .01


@pytest.mark.qt
def test_tiny_same_identity_material_does_not_jump_when_radius_crosses_former_hash_threshold(sphere_pixels):
    # The fixture carries seed=.3. This radius straddles the old 0.8 sparkle
    # threshold while changing projected geometry by much less than one pixel.
    radius = (32.8 - .3 * 17.31) / 913.7
    samples = []
    for offset in (-1e-7, 1e-7):
        pixels, _ = sphere_pixels('ordinary', radius=radius+offset, diag=0,
                                  uSkyTint=(.3,.4,.5), uShaftColour=(.5,.6,.7), uSpeckGlow=.6)
        samples.append(pixels)
    energy = sum(float(np.abs(p).sum()) for p in samples)
    assert energy > .01
    assert float(np.abs(samples[1] - samples[0]).sum()) / energy < .001


@pytest.mark.qt
def test_deep_glass_tracks_source_at_physical_points_and_ignores_directional_end(sphere_pixels):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _glass

    base = {**require_canonical_default('widgets.spotify_visualizer'),
            'extruded_bubble_light_type': 'Deep Light'}
    paths = ((0., .25, -.1667, -.6, -.6, -.7),
             (0., .25, -.1667, .6, -.6, -.7),
             (.5, .25, -.1667, .6, -.6, -.7))
    for kind in ('ordinary', 'cluster', 'near', 'near_cluster'):
        for diag in (1, 2):
            samples = []
            for path in paths:
                knobs = scene_knobs({**base, 'extruded_bubble_light_direction': path})
                material = _glass(knobs, kind.startswith('near'))
                uniforms = {key: material[key] for key in
                            ('uLightDir', 'uSpecColour', 'uSpecShape', 'uSpecThrough', 'uReflect')}
                uniforms.update(uLightSource=knobs['light_source'],
                                uPositionalLight=float(knobs['mode'] == 'deep'))
                if kind.startswith('near'):
                    uniforms.update(uFocus=10., uAperture=1.)
                lit, _ = sphere_pixels(kind, diag=diag, **uniforms)
                samples.append(lit)
            assert np.array_equal(samples[0], samples[1]), 'Deep End changed fixed-source glass lighting'
            assert np.abs(samples[2] - samples[1]).sum() > .01, 'Moving Deep Source did not move highlights'
            translation = (3., -2., 4.)
            translated = {**uniforms, 'uEye': translation,
                          'uLightSource': tuple(s + t for s, t in zip(uniforms['uLightSource'], translation))}
            moved, _ = sphere_pixels(kind, centre=(translation[0], translation[1], -6. + translation[2]),
                                     diag=diag, **translated)
            assert np.allclose(moved, samples[2], atol=2e-4, rtol=2e-4), (kind, diag)
            # Rotate the entire physical configuration and camera basis together.
            # A non-symmetric quarter-turn catches a transposed light transform.
            basis = np.array(((0., 0., 1.), (0., 1., 0.), (-1., 0., 0.)))
            rotated = {**uniforms, 'uLightSource': tuple(basis @ uniforms['uLightSource'])}
            turned, _ = sphere_pixels(kind, centre=tuple(basis @ (0., 0., -6.)),
                                      orientation=basis, diag=diag, **rotated)
            assert np.allclose(turned, samples[2], atol=2e-4, rtol=2e-4), (kind, diag)
    # A point-emitter direction is undefined exactly at its source; it must at
    # least remain finite near the physical front surface pending area/falloff work.
    sphere_pixels('ordinary', diag=0, **{**uniforms, 'uFocus':0., 'uAperture':0.,
                                      'uLightSource': (0., 0., -5.4)})


@pytest.mark.qt
def test_surface_authored_direction_moves_all_glass_highlights_with_refracted_sun(sphere_pixels):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _glass

    base = {**require_canonical_default("widgets.spotify_visualizer"),
            "extruded_bubble_light_type": "Sunlit Surface"}
    # Mirror-image oblique sunlight. Equal Y/Z preserves refraction elevation;
    # the mirrored native highlight must move, not remain under world-up.
    paths = ((-.6, .8, .3, .6, -.8, -.3), (.6, .8, .3, -.6, -.8, -.3))
    knobs = [scene_knobs({**base, "extruded_bubble_light_direction": path}) for path in paths]
    for value in knobs:
        assert value['spec_dir'] == pytest.approx(value['sun_below'])
    for kind, radius in (('ordinary', .06), ('ordinary', .6), ('cluster', .6),
                         ('near', .6), ('near_cluster', .6)):
        for diag in (1, 2):
            highlights = []
            for value in knobs:
                material = _glass(value, kind.startswith('near'))
                uniforms = {key: material[key] for key in
                            ('uLightDir', 'uSpecColour', 'uSpecShape', 'uSpecThrough', 'uReflect')}
                if kind.startswith('near'):
                    uniforms.update(uFocus=10., uAperture=1.)  # admit the real near-only path
                lit, _ = sphere_pixels(kind, radius=radius, diag=diag, **uniforms)
                dark, _ = sphere_pixels(kind, radius=radius, diag=diag, **{**uniforms, 'uSpecColour': (0., 0., 0.)})
                signal = (lit[:, :, :3] - dark[:, :, :3]).sum(axis=2)
                if radius < .1 and diag == 2:
                    assert signal.sum() == 0.  # existing sub-8px lens suppression remains explicit
                    continue
                assert signal.sum() > .001, (kind, radius, diag)
                xx = np.arange(signal.shape[1])[None, :]
                highlights.append(float((signal * xx).sum() / signal.sum()))
            # The front mirror normal bisects view-to-eye and light direction;
            # the diverging transmitted lens also shows it on the source side.
            if highlights:
                assert highlights[1] - highlights[0] > (1. if radius < .1 else 5.)
    translated = tuple(v + d for v, d in zip(paths[0], (.1, 0., -.1, .1, 0., -.1)))
    moved = scene_knobs({**base, 'extruded_bubble_light_direction': translated})
    assert moved['spec_dir'] == pytest.approx(knobs[0]['spec_dir'])


@pytest.mark.qt
@pytest.mark.parametrize("light_type", ("Sunlit Surface", "Deep Light"))
def test_authored_light_strength_reaches_reflected_and_transmitted_pixels(sphere_pixels, light_type):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _glass

    parameters = {**require_canonical_default("widgets.spotify_visualizer"),
                  "extruded_bubble_light_type": light_type}
    for kind in ("ordinary", "cluster"):
        for diag in (1, 2):
            energies = []
            for strength in (0., .5, 1.):
                knobs = scene_knobs({**parameters, "extruded_bubble_light_strength": strength})
                material = _glass(knobs, False)
                # Cross Settings -> scene mapping -> production uniforms -> real shader pixels.
                for near in (False, True):
                    assert _glass(knobs, near)["uSpecColour"] == pytest.approx(
                        tuple(c * 300. * strength for c in knobs["light"]))
                uniforms = {key: material[key] for key in
                            ("uLightDir", "uSpecColour", "uSpecShape", "uSpecThrough", "uReflect")}
                pixels, _ = sphere_pixels(kind, diag=diag, **uniforms)
                energies.append(float(pixels[:, :, :3].sum()))
            assert energies[1] > energies[0] + .001
            assert energies[2] - energies[0] == pytest.approx(2. * (energies[1] - energies[0]), rel=.002)


@pytest.mark.qt
@pytest.mark.parametrize('light_type', ('Sunlit Surface', 'Deep Light'))
@pytest.mark.parametrize('material', (0., 1., 3.))
def test_small_shell_bead_and_snow_glints_obey_strength_without_erasing_ambient(sphere_pixels, light_type, material):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common, _glass

    parameters = {**require_canonical_default('widgets.spotify_visualizer'),
                  'extruded_bubble_light_type': light_type}
    samples = []
    for strength in (0., .5, 1.):
        knobs = scene_knobs({**parameters, 'extruded_bubble_light_strength': strength})
        common = _common(knobs, view_to_world=np.eye(3).ravel(), tan=(1., 1.), time=0.,
                         surface_travel=0., rays=0., streak=(0., 1.))
        # This radius is fully in the ordinary subpixel fallback. Kind3 is
        # stable bead glass; kind1 is marine snow's seeded sparkle branch.
        pixels, _ = sphere_pixels('ordinary', radius=.0125, diag=0, extra=(.912, material),
                                  uLightStrength=common['uLightStrength'], uSparkle=.7,
                                  uSkyTint=(.3, .4, .5), uShaftColour=(.5, .6, .7),
                                  uSpeckGlow=_glass(knobs, False)['uSpeckGlow'])
        samples.append(pixels)
    assert samples[0][:, :, :3].sum() > .001  # transmitted/probe/snow ambient is retained
    delta = samples[2] - samples[0]
    assert delta[:, :, :3].sum() > .001
    np.testing.assert_allclose(samples[1] - samples[0], delta * .5, atol=1e-6, rtol=2e-5)
    np.testing.assert_array_equal(samples[0][:, :, 3], samples[2][:, :, 3])


@pytest.mark.qt
@pytest.mark.parametrize('centre',[(0.,0.,-.1),(0.,0.,0.),(0.,0.,.1)])
def test_near_plane_and_eye_inside_shells_cull_instead_of_covering_viewport(sphere_pixels,centre):
    # Operator explicitly replaces the former full-screen exit-surface presentation.
    # Raw ray intersections remain a shared geometry contract, not permission to
    # draw an overwhelming shell after its render-only proximity fade reaches zero.
    for kind in ('ordinary','cluster','near','near_cluster'):
        pixels,_=sphere_pixels(kind,centre,radius=.7)
        assert pixels.sum()==0


@pytest.mark.qt
def test_eye_inside_union_bound_but_outside_members_does_not_collapse_quad_or_fill_gap(sphere_pixels):
    _,coverage=sphere_pixels('near_cluster',(-.5,0.,-.4),radius=.3,second=(.5,0.,-.4,.3))
    assert (coverage>.5).sum()>100
    assert coverage[160,240]==0


@pytest.mark.qt
def test_lifetime_changes_opacity_without_moving_ordinary_or_union_coverage(sphere_pixels):
    for kind in ('ordinary','cluster'):
        full,coverage=sphere_pixels(kind)
        partial,partial_coverage=sphere_pixels(kind,alpha=.25)
        zero,_=sphere_pixels(kind,alpha=0.)
        assert 0 < partial[:,:,3].sum() < full[:,:,3].sum()
        assert zero.sum()==0
        assert np.array_equal(coverage>.5,partial_coverage>.5)
    left,_=sphere_pixels('cluster',(-.7,0.,-6.),radius=.5,second=(.7,0.,-6.,.5),alphas=(1.,0.,0.))
    right,_=sphere_pixels('cluster',(-.7,0.,-6.),radius=.5,second=(.7,0.,-6.,.5),alphas=(0.,1.,0.))
    assert left[:,:240,3].sum()>0 and left[:,240:,3].sum()==0
    assert right[:,240:,3].sum()>0 and right[:,:240,3].sum()==0


@pytest.mark.qt
def test_both_primitive_types_choose_exactly_one_near_layer_and_aperture_reaches_selection(sphere_pixels):
    for kind in ('ordinary','cluster'):
        for aperture in (.3,3.):
            layers=[]
            for near in (0.,1.):
                pixels,_=sphere_pixels(kind,(0.,0.,-4.5),radius=.5,uFocus=5.,uAperture=aperture,uNearLayer=near)
                layers.append(pixels[:,:,3].sum()>0)
            assert layers==([True,False] if aperture==.3 else [False,True])


@pytest.mark.qt
@pytest.mark.parametrize('kind,near_kind',[('ordinary','near'),('cluster','near_cluster')])
def test_half_viewport_shell_blurs_even_at_zero_aperture_and_uses_only_near_pass(sphere_pixels,kind,near_kind):
    radius=.6
    tan_y=math.tan(math.radians(45)/2.)
    depth=radius*math.sqrt(1.+1./(.5*tan_y)**2)
    sharp,_=sphere_pixels(kind,(0.,0.,-depth),radius=radius)
    near,circle=sphere_pixels(near_kind,(0.,0.,-depth),radius=radius,circle=True)
    assert sharp.sum()==0
    assert near[:,:,3].max()>.99
    coc=np.divide(circle[:,:,0],circle[:,:,1],out=np.zeros((320,480)),where=circle[:,:,1]>1e-6)
    assert coc.max()>=.8*sphere_pixels.near_budget
    assert coc.max()<=sphere_pixels.near_budget+1e-4
    blurred,_=sphere_pixels(near_kind,(0.,0.,-depth),radius=radius,composite=True)
    # Actual shared defocus composite must soften the white diagnostic silhouette.
    edge=blurred[160,:,0]
    assert np.count_nonzero((edge>.1)&(edge<.9))>=8


@pytest.mark.qt
@pytest.mark.parametrize('near_kind',['near','near_cluster'])
def test_near_full_viewport_shell_fades_continuously_then_culls(sphere_pixels,near_kind):
    radius=.6
    tan_y=math.tan(math.radians(45)/2.)
    alphas=[]
    for share in (.7,.8,.85,.9,.95,1.02):
        depth=radius*math.sqrt(1.+1./(share*tan_y)**2)
        pixels,_=sphere_pixels(near_kind,(0.,0.,-depth),radius=radius)
        alphas.append(float(pixels[:,:,3].max()))
    assert alphas[0]>.99 and alphas[-1]==0.
    assert all(a>b for a,b in zip(alphas[1:],alphas[2:]))


@pytest.mark.qt
@pytest.mark.parametrize('kind,near_kind',[('ordinary','near'),('cluster','near_cluster')])
@pytest.mark.parametrize('depths',[(1.051,1.049),(1.001,.999)])
def test_offaxis_near_crossing_retains_continuous_visible_sliver(sphere_pixels,kind,near_kind,depths):
    energies=[]
    for depth in depths:
        total=0.
        for layer in (kind,near_kind):
            pixels,_=sphere_pixels(layer,(1.7,0.,-depth),radius=1.)
            total+=float(pixels[:,:,3].sum())
        energies.append(total)
    assert min(energies)>100.
    assert energies[0]==pytest.approx(energies[1],rel=.03)


@pytest.mark.qt
def test_sparse_union_bound_does_not_hide_or_blur_its_small_members(sphere_pixels):
    pixels,coverage=sphere_pixels('cluster',(-2.4,0.,-6.),radius=.4,second=(2.4,0.,-6.,.4))
    assert (coverage>.5).sum()>1000
    assert pixels[:,:,3].max()>0.
    assert coverage[160,240]==0.
    near,_=sphere_pixels('near_cluster',(-2.4,0.,-6.),radius=.4,second=(2.4,0.,-6.,.4))
    assert near.sum()==0.


@pytest.mark.qt
@pytest.mark.parametrize('sphere_pixels',[(640,360),(360,640),(960,640)],indirect=True)
def test_proximity_blur_scales_with_framebuffer_and_survives_tall_cards(sphere_pixels):
    width,height=sphere_pixels.frame_size
    radius=.6
    share=.5*min(width,height)/height
    depth=radius*math.sqrt(1.+1./(share*math.tan(math.radians(45)/2.))**2)
    for kind in ('near','near_cluster'):
        pixels,circle=sphere_pixels(kind,(0.,0.,-depth),radius=radius,circle=True)
        coc=np.divide(circle[:,:,0],circle[:,:,1],out=np.zeros((height,width)),where=circle[:,:,1]>1e-6)
        assert pixels[:,:,3].max()>.99
        assert .8*sphere_pixels.near_budget <= coc.max() <= sphere_pixels.near_budget+1e-4


@pytest.mark.qt
@pytest.mark.parametrize('kind,near_kind',[('ordinary','near'),('cluster','near_cluster')])
def test_offaxis_shell_reaching_the_lens_eases_out_instead_of_filling_the_view(sphere_pixels,kind,near_kind):
    # Off axis its clipped screen share stays small, so only its surface's distance to the eye can fade it.
    energies=[]
    for gap in (1.0,.33,.2,.12,.03):
        direction=np.array((.8,0.,-.6))
        centre=tuple(direction*(1.+gap))         # radius 1: the surface lies `gap` radii from the eye
        total=0.
        for layer in (kind,near_kind):
            pixels,_=sphere_pixels(layer,centre,radius=1.)
            total+=float(pixels[:,:,3].sum())
        energies.append(total)
    assert energies[0]>100. and energies[1]>.9*energies[0]
    assert all(a>b for a,b in zip(energies[1:],energies[2:]))
    assert energies[-1]<.05*energies[0]

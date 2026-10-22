"""Native production sphere/union geometry, opacity and near-layer admission."""
import math

import numpy as np
import pytest


@pytest.fixture
def sphere_pixels(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BUBBLE_VERTEX, BUBBLE_FRAGMENT, CLUSTER_VERTEX, CLUSTER_FRAGMENT
    from rendering.gl_programs.extruded_bubble_scene import camera
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    width,height=480,320
    target=TransitionCapture(width,height)
    programs={}; texture=vao=cube=0
    try:
        texture=int(gl.glGenTextures(1));gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,width,height,0,gl.GL_RGBA,gl.GL_FLOAT,None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,target.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,texture,0)
        gl.glDrawBuffers(1,[gl.GL_COLOR_ATTACHMENT0])
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
        for kind,vertex,fragment in (('ordinary',BUBBLE_VERTEX,BUBBLE_FRAGMENT),('cluster',CLUSTER_VERTEX,CLUSTER_FRAGMENT)):
            programs[kind]=compile_program(vertex,fragment,label='physical geometry '+kind)
        tan=camera(0,0,width/height)[2];projection=camera(0,0,width/height)[3]
        gl.glViewport(0,0,width,height)
        for option in (gl.GL_BLEND,gl.GL_DEPTH_TEST,gl.GL_CULL_FACE):gl.glDisable(option)

        def draw(kind,centre=(0.,0.,-6.),radius=.6,alpha=1.,second=None,alphas=None,diag=5,**uniforms):
            program=programs[kind];gl.glUseProgram(program)
            loc=lambda key:gl.glGetUniformLocation(program,key)
            for name,value in {'uPixel':2*tan[1]/height,'uPixelSize':2*tan[1]/height,'uCrisp':1.,
                               'uFocus':0.,'uAperture':0.,'uNearCoc':22.,'uNearLayer':0.,'uProbeLevels':1.,
                               'uLens':1.,'uReflect':.5,'uBehind':8.,'uFrameShare':1.,'uShell':.03,**uniforms}.items():
                gl.glUniform1f(loc(name),value)
            gl.glUniform1i(loc('uDiag'),diag)
            gl.glUniform1i(loc('uProbe'),2);gl.glUniform1i(loc('uBackground'),0);gl.glUniform1i(loc('uEnvironment'),0)
            gl.glUniform3f(loc('uIors'),1.15,2.,1.)
            gl.glUniform2f(loc('uFrameSize'),width,height);gl.glUniform2f(loc('uTargetSize'),width,height)
            gl.glUniform2f(loc('uTan'),*tan)
            for name in ('uWorldToView','uViewToWorld'):gl.glUniformMatrix3fv(loc(name),1,False,np.eye(3,dtype='f4'))
            gl.glUniformMatrix4fv(loc('uProjection'),1,False,projection)
            gl.glVertexAttrib4f(0,*centre,radius)
            if kind=='ordinary':
                gl.glVertexAttrib2f(1,.3,0.);gl.glVertexAttrib1f(2,alpha)
            else:
                gl.glVertexAttrib4f(1,*(second or (*centre,1e-6)))
                gl.glVertexAttrib4f(2,0,0,0,0)
                gl.glVertexAttrib4f(3,2,0,.3,0)
                gl.glVertexAttrib3f(4,*(alphas or (alpha,alpha,0.)))
            gl.glClearColor(0,0,0,0);gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,1)
            raw=gl.glReadPixels(0,0,width,height,gl.GL_RGBA,gl.GL_FLOAT)
            pixels=np.frombuffer(raw,dtype='f4').reshape(height,width,4)
            assert np.isfinite(pixels).all() and gl.glGetError()==gl.GL_NO_ERROR
            coverage=np.divide(pixels[:,:,0],pixels[:,:,3],out=np.zeros((height,width),dtype='f4'),where=pixels[:,:,3]>1e-10)
            return pixels,coverage
        yield draw
    finally:
        for program in programs.values():gl.glDeleteProgram(program)
        if vao:gl.glDeleteVertexArrays(1,[vao])
        if texture:gl.glDeleteTextures([texture])
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
@pytest.mark.parametrize('centre',[(0.,0.,-.1),(0.,0.,.1)])
def test_near_plane_and_eye_inside_surfaces_remain_finite_and_visible(sphere_pixels,centre):
    for kind in ('ordinary','cluster'):
        _,coverage=sphere_pixels(kind,centre,radius=.7)
        assert (coverage>.5).mean()>.95


@pytest.mark.qt
@pytest.mark.parametrize('centre',[(0.,0.,0.),(0.,0.,.1)])
def test_inside_material_uses_forward_exit_surface_and_real_probe_background(sphere_pixels,centre):
    normals,_=sphere_pixels('ordinary',centre,radius=.7,diag=4)
    pixel=normals[160,240]
    assert pixel[3]>0 and pixel[2]/pixel[3]<.05  # exit points toward -Z, never the negative-t surface behind the eye
    for diag in (0,1,2):
        pixels,_=sphere_pixels('ordinary',centre,radius=.7,diag=diag)
        assert pixels[:,:,3].sum()>0 and pixels[:,:,:3].sum()>0


@pytest.mark.qt
def test_eye_inside_union_bound_but_outside_members_does_not_collapse_quad_or_fill_gap(sphere_pixels):
    _,coverage=sphere_pixels('cluster',(-.5,0.,-.4),radius=.3,second=(.5,0.,-.4,.3))
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

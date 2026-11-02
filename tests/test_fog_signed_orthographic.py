"""Signed ray integration and sampling must agree across the Orthographic eye plane."""
import math
import numpy as np
import pytest
from OpenGL import GL as gl
from rendering.gl_programs.fog_volume import fog_inject_source, FOG_FULLSCREEN_VERTEX
from rendering.gl_programs.mist import MIST_GLSL
from rendering.quick.render.gl_resources import compile_compute_program
from rendering.quick.scene3d.fog_volume import FogVolume
from rendering.quick.scene3d.resources import MeshResources
from tools.labs.render_target import OffscreenRenderTarget

pytestmark=pytest.mark.qt


@pytest.mark.parametrize('orthographic,depth_range,focus,depths',(
    (True,(-20.,30.),0.,(-20.,-12.,0.,12.,29.)),
    (False,(.3,30.),12.,(.3,4.,12.,18.,29.)),
))
def test_signed_and_focused_integrals_share_the_surface_sampling_map(qt_app,orthographic,depth_range,focus,depths):
    target=OffscreenRenderTarget(8,8);volume=FogVolume('signed test');resources=MeshResources('signed sample')
    inject=0
    try:
        with target.current():
            inject=compile_compute_program(fog_inject_source('''
void fogMedium(vec3 p,out vec3 light,out float extinction,out float steady) {
light=vec3(0.2,0.4,0.8);extinction=0.03;steady=extinction;}
'''),label='signed constant')
            volume.update(inject,view=np.identity(4),lens=(1.,1.,orthographic),depth_range=depth_range,
                          grid=(8,8,128),focus_depth=focus)
            fragment='#version 460 core\n'+MIST_GLSL+'''
uniform float uDepth;out vec4 FragColor;
void main(){FragColor=fogVolumeAt(vec3(0,0,-uDepth));}
'''
            program=resources.program('sample',FOG_FULLSCREEN_VERTEX,fragment)
            vao,_=resources.mesh('coverage',np.zeros((3,3),np.float32).tobytes(),(3,))
            target.bind();gl.glDisable(gl.GL_DEPTH_TEST);gl.glDisable(gl.GL_BLEND)
            with volume.bound() as values:
                gl.glUseProgram(program);gl.glBindVertexArray(vao)
                for name,value in values.items():
                    loc=gl.glGetUniformLocation(program,name)
                    if name=='uFogView':gl.glUniformMatrix4fv(loc,1,gl.GL_FALSE,np.array(value,np.float32))
                    elif isinstance(value,int):gl.glUniform1i(loc,value)
                    else:gl.glUniform4f(loc,*value)
                for depth in depths:
                    gl.glUniform1f(gl.glGetUniformLocation(program,'uDepth'),depth)
                    gl.glDrawArrays(gl.GL_TRIANGLES,0,3)
                    pixel=target.read_rgba()[4,4]/255.
                    stretch=1. if orthographic else math.sqrt(1.+2.*(.125**2))
                    transmittance=math.exp(-.03*(depth-depth_range[0])*stretch)
                    np.testing.assert_allclose(pixel,(*((1.-transmittance)*np.array((.2,.4,.8))),transmittance),atol=.012)
            with pytest.raises(ValueError,match='signed depths require Orthographic'):
                volume.update(inject,view=np.identity(4),lens=(1.,1.,False),depth_range=(-20.,30.),grid=(8,8,128))
    finally:
        with target.current():
            resources.release_resources();volume.release()
            if inject:gl.glDeleteProgram(inject)
        target.close()

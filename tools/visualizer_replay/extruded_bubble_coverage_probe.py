"""Disposable native coverage comparison; no runtime/settings mutation."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
import math
import numpy as np
from PIL import Image, ImageDraw
from rendering.gl_error_policy import disable_per_call_gl_error_checking
if not disable_per_call_gl_error_checking():
    raise RuntimeError("GL imported before production policy")
from OpenGL import GL as gl
from tools.transition_contact_sheet import TransitionCapture
from rendering.quick.render.gl_resources import compile_program
from rendering.gl_programs.extruded_bubble_program import BUBBLE_VERTEX, BUBBLE_FRAGMENT, CLUSTER_VERTEX, CLUSTER_FRAGMENT
from rendering.gl_programs.extruded_bubble_scene import camera

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
OUT=args.output
OUT.mkdir(parents=True,exist_ok=False)
root=Path(__file__).resolve().parents[2]
paths=[root/'rendering/gl_programs/extruded_bubble_program.py',root/'rendering/gl_programs/scene3d_spheres.py']
source_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
W,H=1200,800
capture=TransitionCapture(W,H)
programs=[]
objects=[]
rows=[]
images=[]
try:
    tex=int(gl.glGenTextures(1)); objects.append(tex)
    gl.glBindTexture(gl.GL_TEXTURE_2D,tex)
    gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,W,H,0,gl.GL_RGBA,gl.GL_FLOAT,None)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,capture.fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,tex,0)
    gl.glDrawBuffers(1,[gl.GL_COLOR_ATTACHMENT0])
    cube=int(gl.glGenTextures(1)); objects.append(cube)
    gl.glActiveTexture(gl.GL_TEXTURE2)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP,cube)
    for face in range(6):
        gl.glTexImage2D(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X+face,0,gl.GL_RGBA8,4,4,0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,np.full((4,4,4),127,dtype='u1'))
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindTexture(gl.GL_TEXTURE_2D,capture.textures[0])
    projection=camera(0,0,W/H)[3]
    tan=camera(0,0,W/H)[2]
    gl.glVertexAttrib1f(2,1.0)
    gl.glVertexAttrib3f(4,1.0,1.0,1.0)
    gl.glDisable(gl.GL_BLEND);gl.glDisable(gl.GL_DEPTH_TEST);gl.glDisable(gl.GL_CULL_FACE)
    vao=int(gl.glGenVertexArrays(1));vbo=int(gl.glGenBuffers(1))
    for kind,vs,fs in [('ordinary',BUBBLE_VERTEX,BUBBLE_FRAGMENT),('cluster',CLUSTER_VERTEX,CLUSTER_FRAGMENT)]:
        program=compile_program(vs,fs,label='distortion audit '+kind);programs.append(program)
        gl.glUseProgram(program)
        loc=lambda name:gl.glGetUniformLocation(program,name)
        for name,val in [('uDiag',5),('uProbe',2),('uBackground',0),('uEnvironment',0)]:gl.glUniform1i(loc(name),val)
        for name,val in [('uPixel',2*math.tan(math.radians(31))/H),('uPixelSize',2*math.tan(math.radians(31))/H),('uFocus',0),('uAperture',0),('uCrisp',1),('uNearLayer',0),('uNearCoc',0),('uProbeLevels',1),('uBehind',8),('uLens',1),('uShell',.03),('uFrameShare',1)]:gl.glUniform1f(loc(name),val)
        gl.glUniform3f(loc('uIors'),1.15,2,1)
        gl.glUniform2f(loc('uTan'),*tan)
        gl.glUniform2f(loc('uFrameSize'),W,H);gl.glUniform2f(loc('uTargetSize'),W,H)
        for name in ('uWorldToView','uViewToWorld'):gl.glUniformMatrix3fv(loc(name),1,False,np.eye(3,dtype='f4'))
        gl.glUniformMatrix4fv(loc('uProjection'),1,False,projection)
        gl.glBindVertexArray(vao);gl.glBindBuffer(gl.GL_ARRAY_BUFFER,vbo)
        for placement,centre in [('centre',(0.,0.,-6.)),('edge',(-4.,-2.4,-6.))]:
            radius=.6
            # A tiny fully contained second member admits the real cluster shader without changing its SDF silhouette.
            data=np.array((*centre,radius, .3,0) if kind=='ordinary' else (*centre,radius,*centre,.000001,0,0,0,0,2,0,.3,0),dtype='f4')
            gl.glBufferData(gl.GL_ARRAY_BUFFER,data.nbytes,data,gl.GL_STATIC_DRAW)
            import ctypes
            offsets=(0,16) if kind=='ordinary' else (0,16,32,48)
            for index,offset in enumerate(offsets):
                gl.glEnableVertexAttribArray(index)
                gl.glVertexAttribPointer(index,2 if kind=='ordinary' and index==1 else 4,gl.GL_FLOAT,False,data.nbytes,ctypes.c_void_p(offset))
                gl.glVertexAttribDivisor(index,1)
            gl.glViewport(0,0,W,H);gl.glClearColor(0,0,0,0);gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,1)
            raw=gl.glReadPixels(0,0,W,H,gl.GL_RGBA,gl.GL_FLOAT)
            accum=np.frombuffer(raw,dtype='f4').reshape(H,W,4)
            # Production OIT writes (diagnostic coverage * alpha * weight, alpha * weight).
            coverage=np.divide(accum[:,:,0],accum[:,:,3],out=np.zeros((H,W),dtype='f4'),where=accum[:,:,3]>1e-10)
            coverage=np.nan_to_num(coverage).clip(0,1)
            yy,xx=np.nonzero(coverage>.5)
            eigenvalues=np.linalg.eigvalsh(np.cov(np.vstack((xx,yy)),bias=True))
            ratio=float(np.sqrt(eigenvalues[1]/eigenvalues[0]))
            expected=math.sqrt(1+(centre[0]**2+centre[1]**2)/(centre[2]**2-radius**2))
            name=kind+'_'+placement
            image=Image.fromarray(np.flipud((coverage*255).astype('u1')))
            image.save(OUT/(name+'.png'))
            rows.append(dict(name=name,centre=centre,radius=radius,pixels=len(xx),axis_ratio_covariance=ratio,expected_pinhole_ratio=expected,bounds=[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())],gl_error=int(gl.glGetError())))
            images.append((name,image))
    sheet=Image.new('RGB',(W*2,H*2+80),'#171717');draw=ImageDraw.Draw(sheet)
    for index,(name,image) in enumerate(images):
        x=(index%2)*W;y=(index//2)*(H+40)
        sheet.paste(image.convert('RGB'),(x,y+40));draw.text((x+15,y+12),name,fill='white')
    sheet.save(OUT/'comparison.png')
    metadata=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_hashes=source_hashes,driver=capture.driver,size=[W,H],projection=projection,world_to_view='identity fixed',snapshot='one fixed view-space sphere; two placements, no simulation advance',diagnostic=5,intervention='Unmodified production BUBBLE/CLUSTER vertex+fragment shaders. Direct RGBA32F OIT accumulation readback normalized by accumulation alpha to recover coverage. Blend/depth test disabled for one isolated draw. No environment/light/phase changes between cases; identical dummy probe and fixed captured background. Cluster second member radius 1e-6 coincident inside first; count 2; blend 0.',results=rows)
    (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2))
    if {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths} != source_hashes:
        raise RuntimeError('source changed during coverage probe; reject this output')
    print(json.dumps(metadata,indent=2))
finally:
    for program in programs:gl.glDeleteProgram(program)
    if 'vbo' in locals():gl.glDeleteBuffers(1,[vbo])
    if 'vao' in locals():gl.glDeleteVertexArrays(1,[vao])
    if objects:gl.glDeleteTextures(objects)
    capture.close()

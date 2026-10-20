"""Optional Linux Mesa/EGL shaft shader link gate, without Qt/OpenGL Python modules.

Run from the checkout/Godzip root: python tools/visualizer_replay/eb_shaft_mesa_compile.py
GLSL 4.6 is changed to 4.5 only for this diagnostic; native 4.6 and operator
visual acceptance are separate mandatory gates. Never called by application.
"""
import ctypes as C,sys,types,importlib
# Isolate GLSL constants from Qt/OpenGL imports that belong to runtime, not shader source.
for name,path in [('rendering','rendering'),('rendering.quick','rendering/quick'),('rendering.quick.scene3d','rendering/quick/scene3d')]:
 p=types.ModuleType(name);p.__path__=[path];sys.modules[name]=p
for n,var in [('defocus','SCENE_DEFOCUS_GLSL'),('probe','SCENE3D_PROBE_GLSL'),('target','SCENE_OIT_GLSL')]:
 m=types.ModuleType('rendering.quick.scene3d.'+n);setattr(m,var,'');sys.modules[m.__name__]=m
mod=importlib.import_module('rendering.gl_programs.extruded_bubble_program')
egl=C.CDLL('libEGL.so.1'); GL=C.CDLL('libGL.so.1')
getproc=egl.eglGetProcAddress;getproc.argtypes=[C.c_char_p];getproc.restype=C.c_void_p

def fn(name,restype,atypes):
 ptr=getproc(name.encode());assert ptr,(name,'not found')
 return C.CFUNCTYPE(restype,*atypes)(ptr)
EGLint=C.c_int;EGLDisplay=C.c_void_p
getdisplay=fn('eglGetPlatformDisplayEXT',EGLDisplay,[C.c_uint,C.c_void_p,C.POINTER(EGLint)])
display=getdisplay(0x31DD,None,None)
egl.eglInitialize.argtypes=[EGLDisplay,C.POINTER(EGLint),C.POINTER(EGLint)];egl.eglInitialize.restype=C.c_uint
major,minor=EGLint(),EGLint();assert egl.eglInitialize(display,C.byref(major),C.byref(minor)),hex(egl.eglGetError())
egl.eglBindAPI.argtypes=[C.c_uint];assert egl.eglBindAPI(0x30A2)
egl.eglChooseConfig.argtypes=[EGLDisplay,C.POINTER(EGLint),C.POINTER(C.c_void_p),EGLint,C.POINTER(EGLint)];egl.eglChooseConfig.restype=C.c_uint
attrs=(EGLint*7)(0x3040,0x0008,0x3033,0x0001,0x3024,8,0x3038)
config=C.c_void_p();count=EGLint();assert egl.eglChooseConfig(display,attrs,C.byref(config),1,C.byref(count)) and count.value
ctxattr=(EGLint*7)(0x3098,4,0x30FB,5,0x30FD,1,0x3038) # core 4.5
egl.eglCreateContext.argtypes=[EGLDisplay,C.c_void_p,C.c_void_p,C.POINTER(EGLint)];egl.eglCreateContext.restype=C.c_void_p
ctx=egl.eglCreateContext(display,config,None,ctxattr);assert ctx, 'context creation failed'
egl.eglMakeCurrent.argtypes=[EGLDisplay,C.c_void_p,C.c_void_p,C.c_void_p];egl.eglMakeCurrent.restype=C.c_uint
assert egl.eglMakeCurrent(display,None,None,ctx)
glCreateShader=fn('glCreateShader',C.c_uint,[C.c_uint]);glShaderSource=fn('glShaderSource',None,[C.c_uint,C.c_int,C.POINTER(C.c_char_p),C.POINTER(C.c_int)]);glCompileShader=fn('glCompileShader',None,[C.c_uint]);glGetShaderiv=fn('glGetShaderiv',None,[C.c_uint,C.c_uint,C.POINTER(C.c_int)]);glGetShaderInfoLog=fn('glGetShaderInfoLog',None,[C.c_uint,C.c_int,C.POINTER(C.c_int),C.c_char_p]);glDeleteShader=fn('glDeleteShader',None,[C.c_uint])
glCreateProgram=fn('glCreateProgram',C.c_uint,[])
glAttachShader=fn('glAttachShader',None,[C.c_uint,C.c_uint])
glLinkProgram=fn('glLinkProgram',None,[C.c_uint])
glGetProgramiv=fn('glGetProgramiv',None,[C.c_uint,C.c_uint,C.POINTER(C.c_int)])
glGetProgramInfoLog=fn('glGetProgramInfoLog',None,[C.c_uint,C.c_int,C.POINTER(C.c_int),C.c_char_p])
glDeleteProgram=fn('glDeleteProgram',None,[C.c_uint])
program=glCreateProgram()
for shader_type,source in [(0x8B31,mod.FULL_VERTEX),(0x8B30,mod.SHAFT_FRAGMENT)]:
 source=source.replace('#version 460 core','#version 450 core')
 shader=glCreateShader(shader_type);b=source.encode();p=C.c_char_p(b);glShaderSource(shader,1,C.byref(p),None);glCompileShader(shader)
 status=C.c_int();glGetShaderiv(shader,0x8B81,C.byref(status));length=C.c_int();glGetShaderiv(shader,0x8B84,C.byref(length));buf=C.create_string_buffer(max(length.value,1));glGetShaderInfoLog(shader,len(buf),None,buf)
 print('VERT' if shader_type==0x8B31 else 'FRAG','status',status.value,'info:',buf.value[:2400].decode(errors='replace'))
 glAttachShader(program,shader)
 glDeleteShader(shader)
 assert status.value == 1
glLinkProgram(program)
status=C.c_int();glGetProgramiv(program,0x8B82,C.byref(status))
length=C.c_int();glGetProgramiv(program,0x8B84,C.byref(length))
buf=C.create_string_buffer(max(length.value,1));glGetProgramInfoLog(program,len(buf),None,buf)
print('LINK status',status.value,'info:',buf.value.decode(errors='replace')[:2000])
glDeleteProgram(program)
assert status.value == 1
print('OFFSCREEN_GL45_LINK_PASS; not native GL46 or visual acceptance')

# The procedural speck emitter now reads real Stream Source/End coordinates;
# syntax/link-check its changed vertex stage without importing PySide6/OpenGL.
particle_program=glCreateProgram()
for shader_type,source in [(0x8B31,mod.SPECK_VERTEX),(0x8B30,mod.PARTICLE_FRAGMENT)]:
    source=source.replace('#version 460 core','#version 450 core')
    shader=glCreateShader(shader_type)
    b=source.encode();p=C.c_char_p(b)
    glShaderSource(shader,1,C.byref(p),None);glCompileShader(shader)
    status=C.c_int();glGetShaderiv(shader,0x8B81,C.byref(status))
    length=C.c_int();glGetShaderiv(shader,0x8B84,C.byref(length))
    buf=C.create_string_buffer(max(length.value,1));glGetShaderInfoLog(shader,len(buf),None,buf)
    print('SPECK VERT' if shader_type==0x8B31 else 'SPECK FRAG',status.value,buf.value[:1200].decode(errors='replace'))
    assert status.value==1
    glAttachShader(particle_program,shader);glDeleteShader(shader)
glLinkProgram(particle_program)
status=C.c_int();glGetProgramiv(particle_program,0x8B82,C.byref(status))
length=C.c_int();glGetProgramiv(particle_program,0x8B84,C.byref(length))
buf=C.create_string_buffer(max(length.value,1));glGetProgramInfoLog(particle_program,len(buf),None,buf)
print('SPECK LINK',status.value,buf.value[:1200].decode(errors='replace'))
glDeleteProgram(particle_program)
assert status.value==1
print('OFFSCREEN_SPECK_GL45_LINK_PASS; not native rendering or GPU timing')

# Path-enabled free chains, marine snow and parent-attached fizz share the
# production bead generator. Link against a minimal diagnostic fragment instead
# of the Qt scene's transparent-OIT owner; this checks actual vertex GLSL.
bead_program=glCreateProgram()
for shader_type,source in [(0x8B31,mod.BEAD_VERTEX),
                           (0x8B30,'#version 450 core\nout vec4 colour;\nvoid main(){colour=vec4(0.0);}')]:
    source=source.replace('#version 460 core','#version 450 core')
    if shader_type == 0x8B31:
        # The shared sphere GLSL embeds sceneSphereCoverage(), fragment-only
        # fwidth code unused by the vertex stage. Mesa eagerly rejects the
        # unreachable definition, while the production binary is untouched.
        source=source.replace('float derivative = fwidth(miss);', 'float derivative = 0.0;')
    shader=glCreateShader(shader_type)
    b=source.encode();p=C.c_char_p(b)
    glShaderSource(shader,1,C.byref(p),None);glCompileShader(shader)
    status=C.c_int();glGetShaderiv(shader,0x8B81,C.byref(status))
    length=C.c_int();glGetShaderiv(shader,0x8B84,C.byref(length))
    buf=C.create_string_buffer(max(length.value,1));glGetShaderInfoLog(shader,len(buf),None,buf)
    print('BEAD VERT' if shader_type==0x8B31 else 'BEAD FRAG',status.value,buf.value[:1800].decode(errors='replace'))
    assert status.value == 1
    glAttachShader(bead_program,shader);glDeleteShader(shader)
glLinkProgram(bead_program)
status=C.c_int();glGetProgramiv(bead_program,0x8B82,C.byref(status))
length=C.c_int();glGetProgramiv(bead_program,0x8B84,C.byref(length))
buf=C.create_string_buffer(max(length.value,1));glGetProgramInfoLog(bead_program,len(buf),None,buf)
print('BEAD LINK',status.value,buf.value[:1800].decode(errors='replace'))
glDeleteProgram(bead_program)
assert status.value == 1
print('OFFSCREEN_BEAD_GL45_LINK_PASS; not native rendering or visual acceptance')

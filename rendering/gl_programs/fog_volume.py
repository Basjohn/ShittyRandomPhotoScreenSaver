"""S3D-7 froxel fog volume programs: inject a consumer's medium, integrate along view rays. Pure; no GL state.

The volume is a reduced-resolution grid over the camera's view: x/y follow the viewport, z is exponential in view
depth between ``near`` and ``far`` (fine where the scene is, coarse far away). Orthographic cells are boxes,
Perspective cells frusta; both use the same view matrix the scene is drawn with. A consumer writes
``void fogMedium(vec3 world, out vec3 radiance, out float extinction, out float steady)``: extinction per world unit,
the share of it a detail march must not erode (smooth haze), and the radiance the medium scatters toward the eye
there (lighting and albedo folded in). It is evaluated once per cell per update;
``fog_inject_source`` wraps it. ``FOG_INTEGRATE_COMPUTE`` accumulates in-scatter and transmittance front to back,
exactly per slice (radiance x (1 - exp(-extinction x length))), into the texture ``MIST_GLSL`` samples.
"""

FOG_SLICE_GLSL = """
uniform vec4 uFogLens;     // half-extent x, y (Orthographic) or tangent x, y (Perspective); orthographic flag; unused
uniform vec4 uFogRange;    // near, far view depth, slices, enabled
float fogSliceDepth(float f) { return uFogRange.x*pow(uFogRange.y/uFogRange.x,f/uFogRange.z); }
"""

_INJECT_HEAD = """#version 460 core
layout(local_size_x=4,local_size_y=4,local_size_z=4) in;
layout(rgba16f,binding=0) uniform writeonly image3D uFogInject;
layout(r16f,binding=1) uniform writeonly image3D uFogSteady;
uniform mat4 uFogInvView;  // the volume camera's view -> world
""" + FOG_SLICE_GLSL

_INJECT_MAIN = """
void main() {
    ivec3 size=imageSize(uFogInject);
    ivec3 cell=ivec3(gl_GlobalInvocationID);
    if(any(greaterThanEqual(cell,size))) return;
    vec2 ndc=(vec2(cell.xy)+0.5)/vec2(size.xy)*2.0-1.0;
    float depth=fogSliceDepth(float(cell.z)+0.5);
    vec3 view=uFogLens.z>0.5?vec3(ndc*uFogLens.xy,-depth):vec3(ndc*uFogLens.xy*depth,-depth);
    vec3 radiance; float extinction, steady=0.0;
    fogMedium((uFogInvView*vec4(view,1.0)).xyz,radiance,extinction,steady);
    extinction=max(extinction,0.0);
    imageStore(uFogInject,cell,vec4(radiance,extinction));
    imageStore(uFogSteady,cell,vec4(clamp(steady,0.0,extinction)));
}
"""


def fog_inject_source(medium_glsl: str) -> str:
    """Compute source evaluating the consumer's ``fogMedium`` at every cell centre."""
    if 'fogMedium' not in medium_glsl:
        raise ValueError('A fog medium must define fogMedium(vec3 world, out vec3 radiance, out float extinction, '
                         'out float steady)')
    return _INJECT_HEAD + medium_glsl + _INJECT_MAIN


FOG_INTEGRATE_COMPUTE = """#version 460 core
layout(local_size_x=8,local_size_y=8) in;
layout(rgba16f,binding=0) uniform readonly image3D uFogInject;
layout(rgba16f,binding=1) uniform writeonly image3D uFogIntegrated;
""" + FOG_SLICE_GLSL + """
void main() {
    ivec3 size=imageSize(uFogInject);
    ivec2 column=ivec2(gl_GlobalInvocationID.xy);
    if(any(greaterThanEqual(column,size.xy))) return;
    vec2 ndc=(vec2(column)+0.5)/vec2(size.xy)*2.0-1.0;
    // World length per unit of view depth along this column's ray.
    float stretch=uFogLens.z>0.5?1.0:length(vec3(ndc*uFogLens.xy,1.0));
    vec3 scatter=vec3(0.0);
    float transmittance=1.0;
    for(int k=0;k<size.z;k++) {
        vec4 medium=imageLoad(uFogInject,ivec3(column,k));
        float slice=exp(-medium.a*(fogSliceDepth(float(k+1))-fogSliceDepth(float(k)))*stretch);
        scatter+=transmittance*medium.rgb*(1.0-slice);
        transmittance*=slice;
        imageStore(uFogIntegrated,ivec3(column,k),vec4(scatter,transmittance));
    }
}
"""


# Fullscreen triangle for the detail march and composite (needs a bound VAO, no attributes).
FOG_FULLSCREEN_VERTEX = """#version 460 core
out vec2 vNdc;
void main() {
    vec2 corner=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));
    vNdc=corner*2.0-1.0;
    gl_Position=vec4(vNdc,0.0,1.0);
}
"""


# Detail march: the coarse volume holds the medium's light and coverage (extinction over its maximum); a per-pixel
# march at reduced resolution erodes that coverage with tiling detail noise, self-shadows each lump toward clearer
# air (where a consumer's lights sit) and stops at an analytic ground plane. Output: in-scatter (rgb) and
# transmittance (a) to the ground or the far depth, composited as dst x a + rgb. Froxel resolution alone smears
# clouds into washes; the detail lives here, the expensive lighting stays coarse.
_FOG_MARCH_HEAD = """#version 460 core
in vec2 vNdc;
uniform sampler3D uFogMedium;    // coarse medium: radiance rgb, extinction a
uniform sampler3D uFogDetail;    // tiling detail noise in [0, 1]
uniform sampler3D uFogSteady;    // coarse share of extinction that is never eroded (smooth haze)
uniform mat4 uFogView;
uniform mat4 uFogInvView;
uniform vec4 uFogLens;
uniform vec4 uFogRange;
uniform vec4 uMarch;             // maximum steps, maximum extinction, erosion, detail frequency (per world unit)
uniform vec4 uMarchShade;        // shadow reach (world), shadow strength, ground height, ground enabled
uniform vec3 uMarchStep;         // view-depth step inside the medium, through clear air; least self-shadow
uniform vec4 uMarchEdge;         // extra light on thin eroded wisps (curl rims), 0 off; unboosted base radiance
uniform vec2 uViewportSize;
layout(location=0) out vec4 FragColor;
vec3 coarseUvw(vec3 world) {
    vec3 v=(uFogView*vec4(world,1.0)).xyz;
    float depth=max(-v.z,1e-4);
    vec2 ndc=uFogLens.z>0.5?v.xy/uFogLens.xy:v.xy/(uFogLens.xy*depth);
    float f=log(max(depth,uFogRange.x)/uFogRange.x)/log(uFogRange.y/uFogRange.x)*uFogRange.z;
    return clamp(vec3(ndc*0.5+0.5,f/uFogRange.z),vec3(0.0),vec3(1.0));
}
// The erodible part of the coarse medium: radiance and the extinction beyond its steady share.
vec4 coarse(vec3 world) {
    vec3 uvw=coarseUvw(world);
    vec4 medium=texture(uFogMedium,uvw);
    return vec4(medium.rgb,max(medium.a-texture(uFogSteady,uvw).r,0.0));
}
"""

_FOG_MARCH_MAIN = """
float detail(vec3 p) {
    vec3 q=p*uMarch.w;
    return 0.62*texture(uFogDetail,q).r+0.38*texture(uFogDetail,q*2.71+vec3(0.31,0.17,0.53)).r;
}
float eroded(float coverage, vec3 p) {
    float e=uMarch.z*detail(p);
    return clamp((coverage-e)/max(1.0-e,1e-3),0.0,1.0);
}
void main() {
    vec3 origin, direction;
    float stretch=1.0;
    if(uFogLens.z>0.5) {
        origin=(uFogInvView*vec4(vNdc*uFogLens.xy,0.0,1.0)).xyz;
        direction=normalize((uFogInvView*vec4(0.0,0.0,-1.0,0.0)).xyz);
    } else {
        origin=(uFogInvView*vec4(0.0,0.0,0.0,1.0)).xyz;
        vec3 ray=vec3(vNdc*uFogLens.xy,-1.0);
        stretch=length(ray);
        direction=normalize((uFogInvView*vec4(ray,0.0)).xyz);
    }
    float end=uFogRange.y;
    if(uMarchShade.w>0.5 && direction.y<-1e-5)
        end=min(end,max((uMarchShade.z-origin.y)/direction.y/stretch,uFogRange.x));
    // Adaptive steps along view depth: long through clear air, short inside the medium, where the eroded detail
    // lives (exponential steps were ~2 units long at the mist and aliased billows into speckle). The start is
    // offset per pixel by an unstructured hash: interleaved gradient noise drew diagonal hatching.
    uvec2 cell=uvec2(gl_FragCoord.xy);
    uint bits=cell.x*1973u+cell.y*9277u+89173u;
    bits=(bits<<13u)^bits; bits=bits*(bits*bits*15731u+789221u)+1376312589u;
    float jitter=float(bits&0x00ffffffu)/16777216.0;
    vec3 scatter=vec3(0.0);
    float transmittance=1.0;
    float depth=uFogRange.x+jitter*uMarchStep.y;
    // On meeting the medium after a long clear-air step, step back and enter at fine steps (a jittered long-step
    // entry speckled the edges); stay fine until a long step's length of clear air has passed.
    float clearRun=uMarchStep.y;
    for(int i=0;i<int(uMarch.x) && depth<end;i++) {
        vec3 p=origin+direction*depth*stretch;
        vec3 uvw=coarseUvw(p);
        vec4 total=texture(uFogMedium,uvw);
        float steady=texture(uFogSteady,uvw).r;
        vec4 medium=vec4(total.rgb,max(total.a-steady,0.0));
        float coverage=fogCoverage(p,medium.a/max(uMarch.y,1e-6));
        if(coverage<=0.002 && steady<=0.002*uMarch.y) {
            bool coarseStep=clearRun>=uMarchStep.y;
            float advance=coarseStep?uMarchStep.y:uMarchStep.x;
            clearRun+=advance; depth+=advance;
            continue;
        }
        if(clearRun>=uMarchStep.y && i>0) { depth=max(depth-uMarchStep.y,uFogRange.x); clearRun=0.0; continue; }
        clearRun=0.0;
        float step=min(uMarchStep.x,end-depth);
        float density=uMarch.y*eroded(coverage,p)+steady;
        if(density>0.0) {
            vec3 toward=fogLightDirection(p);
            vec3 q=p+toward*uMarchShade.x;
            float shade=exp(-uMarchShade.y*uMarch.y*eroded(fogCoverage(q,coarse(q).a/max(uMarch.y,1e-6)),q)*uMarchShade.x);
            float slice=exp(-density*step*stretch);
            // A floor on self-shadow keeps the cloud bodies' own structure visible behind their lit faces.
            // Thin, eroded wisps let light through and read as bright curl rims around denser cores.
            // Only light above the medium's base (its unlit ambient) is boosted: boosting the base greyed the bodies.
            float wisp=uMarchEdge.x*(1.0-clamp(density/max(uMarch.y,1e-6),0.0,1.0));
            vec3 lit=medium.rgb+max(medium.rgb-uMarchEdge.yzw,vec3(0.0))*wisp;
            scatter+=transmittance*lit*mix(uMarchStep.z,1.0,shade)*(1.0-slice);
            transmittance*=slice;
            if(transmittance<0.003) break;
        }
        depth+=step;
    }
    FragColor=vec4(scatter,transmittance);
}
"""

_FOG_COARSE_COVERAGE = """
float fogCoverage(vec3 world, float coarse) { return coarse; }
"""

# Self-shadow direction: toward clearer air by default (the coarse coverage gradient; lights sit in the clear air).
_FOG_GRADIENT_DIRECTION = """
vec3 fogLightDirection(vec3 p) {
    float h=0.6;
    vec3 gradient=vec3(coarse(p+vec3(h,0,0)).a-coarse(p-vec3(h,0,0)).a,
                       coarse(p+vec3(0,h,0)).a-coarse(p-vec3(0,h,0)).a,
                       coarse(p+vec3(0,0,h)).a-coarse(p-vec3(0,0,h)).a);
    return -gradient/max(length(gradient),1e-6);
}
"""


def fog_march_source(coverage_glsl: str | None = None) -> str:
    """The detail march; ``coverage_glsl`` may define ``float fogCoverage(vec3 world, float coarse)`` returning the
    erodible coverage (0..1) from the consumer's own fine shape (a coarse grid stair-steps shapes that change within
    a cell), and ``vec3 fogLightDirection(vec3 world)``, the unit direction toward its light for self-shadowing
    (default: toward clearer air). The coarse grid still supplies the light and the steady share."""
    coverage = _FOG_COARSE_COVERAGE if coverage_glsl is None else coverage_glsl
    if 'fogCoverage' not in coverage:
        raise ValueError('A coverage source must define float fogCoverage(vec3 world, float coarse)')
    if 'fogLightDirection' not in coverage:
        coverage += _FOG_GRADIENT_DIRECTION
    return _FOG_MARCH_HEAD + coverage + _FOG_MARCH_MAIN


FOG_COMPOSITE_FRAGMENT = """#version 460 core
in vec2 vNdc;
uniform sampler2D uFogMarch;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
uniform float uFogGlow;          // share of the in-scatter that feeds bloom
uniform float uFogScale;         // in-scatter gain (a reflection may take less of the mist than the eye sees)
uniform vec4 uFogCrackle;        // gain, filament frequency (per pixel), sharpness, edge width (march texels); 0 off
uniform vec2 uFogCrackleSeed;    // the line's bloom share; unused
uniform sampler2D uFogCrackleLimit; // per screen column: the lowest screen v (0..1, up) the line may reach
uniform int uFogCrackleLimited;
float crackleHash(vec2 p) { p=fract(p*vec2(0.1031,0.1030)); p+=dot(p,p.yx+33.33); return fract((p.x+p.y)*p.x); }
float crackleNoise(vec2 x) {
    vec2 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
    return mix(mix(crackleHash(i),crackleHash(i+vec2(1,0)),f.x),mix(crackleHash(i+vec2(0,1)),crackleHash(i+vec2(1,1)),f.x),f.y);
}
// Silhouette crackle: the bank's edge as seen is where its transmittance changes fastest. Thin ridged filaments run
// along that edge (ridges of noise warped along the edge direction), lit in the in-scatter's own colour there.
// Full resolution and screen space: a volume cannot confine a line to a silhouette.
float crackleLum(vec2 uv, vec2 t) {
    vec3 w=vec3(0.2126,0.7152,0.0722);
    vec2 h=t*0.5;
    return 0.25*(dot(texture(uFogMarch,uv+vec2(h.x,h.y)).rgb,w)+dot(texture(uFogMarch,uv+vec2(-h.x,h.y)).rgb,w)
                +dot(texture(uFogMarch,uv+vec2(h.x,-h.y)).rgb,w)+dot(texture(uFogMarch,uv+vec2(-h.x,-h.y)).rgb,w));
}
vec3 crackle(vec2 uv, vec4 fog) {
    if(uFogCrackle.x<=0.0) return vec3(0.0);
    float limit=uFogCrackleLimited==1?texture(uFogCrackleLimit,vec2(uv.x,0.5)).r:-1.0;
    float allowed=smoothstep(limit-0.01,limit+0.02,uv.y);
    if(allowed<=0.0) return vec3(0.0);
    // The edge as seen: where lit in-scatter falls off into the dark body (log luminance gradient). Behind the bank
    // is more mist, so transmittance is ~0 across it and has no edge.
    vec2 t=uFogCrackle.w/vec2(textureSize(uFogMarch,0));
    vec3 w=vec3(0.2126,0.7152,0.0722);
    // Each gradient tap is a small blur: the march's per-pixel step jitter otherwise turns the line into sand.
    float lx=log(crackleLum(uv+vec2(t.x,0),t)+1e-3)-log(crackleLum(uv-vec2(t.x,0),t)+1e-3);
    float ly=log(crackleLum(uv+vec2(0,t.y),t)+1e-3)-log(crackleLum(uv-vec2(0,t.y),t)+1e-3);
    float tx=lx, ty=ly;
    float edge=smoothstep(0.15,0.9,length(vec2(tx,ty)));
    if(edge<=0.01) return vec3(0.0);
    vec2 normal=normalize(vec2(tx,ty)+1e-6), along=vec2(-normal.y,normal.x);
    // Faces lit from below (the light lies above the edge, toward the bank): the bank's underside facing the waveform.
    // Its top against the dark sky stays dark, as in the mock. uFogCrackleSeed.y blends toward all edges.
    edge*=mix(smoothstep(0.1,0.6,normal.y),1.0,uFogCrackleSeed.y);
    vec2 p=gl_FragCoord.xy;
    // Coordinates stretched along the edge: filaments run with it and wander across it.
    // Only the bright side of the edge: the gradient points into the light, so step against it and compare.
    float here=crackleLum(uv,t);
    float darker=crackleLum(uv-normal*t*2.0,t);
    edge*=smoothstep(1.2,2.5,(here+1e-3)/(darker+1e-3));
    vec2 q=vec2(dot(p,along)*0.08,dot(p,normal)*0.5)*uFogCrackle.y;
    q.y+=2.0*crackleNoise(vec2(q.x*0.6,0.0)+7.1);   // filaments wander slowly across the edge
    float r1=1.0-abs(2.0*crackleNoise(q)-1.0);
    float r2=1.0-abs(2.0*crackleNoise(q*vec2(1.7,2.3)+vec2(3.7,1.3))-1.0);
    float ridge=pow(r1,uFogCrackle.z)+0.6*pow(r2,uFogCrackle.z);
    // The fringe's own hue at full saturation (normalised by its strongest channel), at an absolute brightness:
    // the mock's edge is a luminous line, far brighter than the dim mist it sits on.
    vec3 tone=texture(uFogMarch,uv,1.0).rgb;  // the fringe colour, not its grain
    float top=max(max(tone.r,max(tone.g,tone.b)),1e-4);
    // Only coloured fringes: a pale edge (the floor mist's boundary, low haze) is not a rim and bloomed into a bar.
    edge*=smoothstep(0.35,0.6,(top-min(tone.r,min(tone.g,tone.b)))/top);
    vec3 hue=tone/top;
    hue=mix(vec3(dot(hue,w)),hue,1.4);
    return max(hue,vec3(0.0))*edge*allowed*(0.7+0.3*ridge)*uFogCrackle.x;  // mostly a smooth line, gently fibrous
}
void main() {
    // A tent over the march's texels: its per-pixel step jitter is grain, not detail.
    vec2 uv=vNdc*0.5+0.5, texel=0.75/vec2(textureSize(uFogMarch,0));
    vec4 fog=0.25*(texture(uFogMarch,uv+vec2(-texel.x,-texel.y))+texture(uFogMarch,uv+vec2(texel.x,-texel.y))
                  +texture(uFogMarch,uv+vec2(-texel.x,texel.y))+texture(uFogMarch,uv+vec2(texel.x,texel.y)));
    vec3 line=crackle(uv,fog)*uFogScale;
    fog.rgb=fog.rgb*uFogScale+line;
    FragColor=fog;               // blend: dst x src alpha + src
    vec3 glow=fog.rgb*uFogGlow+line*uFogCrackleSeed.x;   // the line blooms broadly (its own share)
    Emission=vec4(glow,dot(glow,vec3(0.2126,0.7152,0.0722)));
}
"""


def fog_detail_noise(size: int = 64, seed: int = 7):
    """Tiling fractal value noise in [0, 1] (size^3 float32): baked once, sampled with GL_REPEAT."""
    import numpy as np
    rng = np.random.default_rng(seed)
    total = np.zeros((size, size, size), np.float32)
    weight = 0.
    for period, amplitude in ((4, .5), (8, .25), (16, .15), (32, .1)):
        lattice = rng.random((period, period, period)).astype(np.float32)
        coordinate = np.arange(size, dtype=np.float32)*period/size
        base = np.floor(coordinate).astype(int)
        f = coordinate - base
        f = f*f*(3 - 2*f)
        i0, i1 = base % period, (base + 1) % period
        def along(a, axis, i0, i1, f):
            shape = [1, 1, 1]; shape[axis] = -1
            f = f.reshape(shape)
            return np.take(a, i0, axis=axis)*(1 - f) + np.take(a, i1, axis=axis)*f
        layer = along(along(along(lattice, 0, i0, i1, f), 1, i0, i1, f), 2, i0, i1, f)
        total += amplitude*layer
        weight += amplitude
    total /= weight
    return (total - total.min())/(total.max() - total.min())

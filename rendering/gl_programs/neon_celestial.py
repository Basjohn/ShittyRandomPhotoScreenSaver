"""Pure position math and GLSL for Neon Lake Basin's optional celestial scene.

The caller owns its logical animation clock, scene pose, shader program and render
resources.  ``basin_body_position`` is only an analytic mirror for the body orbit;
the GLSL fragment below owns no clock or camera transform.
"""
from __future__ import annotations

import math

from rendering.gl_programs.scene3d_sky import SCENE3D_SKY_GLSL


def basin_body_position(
    x: float,
    y: float,
    z: float,
    half_width: float,
    animation_time: float,
    orbit_enabled: bool,
    orbit_speed: float,
) -> tuple[float, float, float]:
    """Resolve authored basin body coordinates and optional logical-clock orbit.

    ``x`` is authored as a multiple of ``half_width``; ``y`` and ``z`` are scene
    units.  Orbit speed is revolutions per second around the visible basin centre
    at ``(0, 0, -1.2)``.  When disabled, time and speed are deliberately unused
    and the authored world position is returned directly.
    """
    x = float(x)
    y = float(y)
    z = float(z)
    half_width = float(half_width)
    authored_x = x * half_width
    if not all(math.isfinite(value) for value in (x, y, z, half_width, authored_x)):
        raise ValueError("celestial body position must be finite")
    if half_width <= 0.0:
        raise ValueError("basin half-width must be positive")
    if not orbit_enabled:
        return authored_x, y, z

    animation_time = float(animation_time)
    orbit_speed = float(orbit_speed)
    if not math.isfinite(animation_time) or not math.isfinite(orbit_speed):
        raise ValueError("celestial orbit time and speed must be finite")
    angle = animation_time * orbit_speed * math.tau
    if not math.isfinite(angle):
        raise ValueError("celestial orbit angle must be finite")

    cosine = math.cos(angle)
    sine = math.sin(angle)
    offset_z = z + 1.2
    world_x = authored_x * cosine + offset_z * sine
    world_z = -1.2 - authored_x * sine + offset_z * cosine
    return world_x, y, world_z


def basin_body_camera_coverage(camera_distance: float, body_radius: float) -> float:
    """Visible-disc attenuation only, leaving the orbit and scene radiance intact.

    Near-camera spheres create an enormous angular disc even though their
    centre and radius are valid. Blend the visible body out before the eye can
    intersect it; glass/reflection and light continue to use the real sphere.
    """
    camera_distance, body_radius = float(camera_distance), float(body_radius)
    if not math.isfinite(camera_distance) or not math.isfinite(body_radius):
        raise ValueError("celestial camera distance and radius must be finite")
    if body_radius <= 0.0:
        return 0.0
    ratio = body_radius / max(camera_distance, 1e-6)
    t = max(0.0, min(1.0, (ratio - 0.16) / (0.28 - 0.16)))
    return 1.0 - t*t*(3.0 - 2.0*t)


NEON_CELESTIAL_GLSL = SCENE3D_SKY_GLSL + r"""
uniform vec3 uBodyPosition;
uniform float uBodySize;
uniform int uBodyKind;              // 0 Sun, 1 Moon
uniform int uSunEnabled;            // canonical Show Sun / Moon body gate
uniform vec4 uSunColor;
uniform vec4 uMoonColor;
uniform float uMoonPhase;
// Camera-nearbody attenuation affects visible sky only, not reflections/light.
float basinCameraBodyCoverage(float cameraDistance,float radius) {
    if (radius<=0.0) return 0.0;
    float ratio=radius/max(cameraDistance,1e-6);
    return 1.0-smoothstep(0.16,0.28,ratio);
}
uniform int uSkyEnabled;
uniform vec4 uSkyColor;
uniform float uSkyStrength;
uniform vec4 uStarColor;
uniform vec4 uStarGlowColor; // beat stars' colour; alpha mixes it in over the star colour
vec3 basinBeatStarColour() { return mix(uStarColor.rgb, uStarGlowColor.rgb, clamp(uStarGlowColor.a, 0.0, 1.0)); }
uniform vec2 uStarGlow; // intensity and response for selected beat stars
uniform int uBeatStarCount;
uniform vec4 uBeatStarCells[6];  // panorama star-grid x/y, fade strength
uniform vec4 uCloudColor;
uniform vec4 uHorizonColor;
uniform vec4 uClouds;      // volumetric clouds: coverage, softness, scale, opacity (opacity 0 = off)
uniform vec2 uCloudDrift;  // their drift so far, on the scene's animation clock
uniform vec2 uNebula;      // intensity (0 = off), scale
uniform float uNebulaTurn; // its slow turn about the vertical so far, on the scene's animation clock
uniform vec4 uNebulaColorA;
uniform vec4 uNebulaColorB;

float basinCelestialHash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

// Stable spherical lunar albedo: every feature is sampled in 3-D direction
// space, never longitude/latitude UV. This prevents meridian seams, polar
// stretching, and repeated rectangular crater tiles as the camera orbits.
float basinMoonHash(vec3 cell) {
    return fract(sin(dot(cell, vec3(127.1, 311.7, 74.7))) * 43758.5453123);
}
float basinMoonNoise(vec3 p) {
    vec3 cell=floor(p), f=fract(p);
    f=f*f*(3.0-2.0*f);
    float c000=basinMoonHash(cell);
    float c100=basinMoonHash(cell+vec3(1.0,0.0,0.0));
    float c010=basinMoonHash(cell+vec3(0.0,1.0,0.0));
    float c110=basinMoonHash(cell+vec3(1.0,1.0,0.0));
    float c001=basinMoonHash(cell+vec3(0.0,0.0,1.0));
    float c101=basinMoonHash(cell+vec3(1.0,0.0,1.0));
    float c011=basinMoonHash(cell+vec3(0.0,1.0,1.0));
    float c111=basinMoonHash(cell+vec3(1.0,1.0,1.0));
    return mix(mix(mix(c000,c100,f.x),mix(c010,c110,f.x),f.y),
               mix(mix(c001,c101,f.x),mix(c011,c111,f.x),f.y),f.z);
}

vec3 basinMoonLightDirection(vec3 eye) {
    // Moon Phase is authored, not a date clock or an orbit-speed derivative.
    // Resolve its light in the current viewing basis: moving the camera or
    // orbiting the Moon must not silently turn a selected crescent into a full
    // Moon. Keep the material's 3-D crater/maria sampling in world space.
    vec3 towardViewer=normalize(eye-uBodyPosition);
    vec3 right=cross(vec3(0.0,1.0,0.0),towardViewer);
    if (dot(right,right)<1e-5) right=cross(vec3(0.0,0.0,1.0),towardViewer);
    right=normalize(right);
    float angle=clamp(uMoonPhase,0.0,1.0)*6.28318530718;
    return normalize(right*sin(angle)-towardViewer*cos(angle));
}
float basinMoonIllumination(vec3 normal,vec3 eye) {
    // Single terminator authority for the lit lunar surface, inner feather and
    // optional illuminated rim marks. The ordinary exterior halo is phase-free.
    // Keep crescents thin, but soften the transition so the phase does not read
    // as a hard mechanical cut.
    return smoothstep(0.0,0.055,dot(normal,basinMoonLightDirection(eye)));
}

float basinMoonSurfaceBrightness(vec3 normal,vec3 eye) {
    vec3 lightDir=basinMoonLightDirection(eye);
    float ndl=dot(normal,lightDir);
    float lambert=max(ndl,0.0);
    // A bright lunar face with restrained relief. The shaded hemisphere is
    // retained below as dim earthshine for a solid 3-D body. Surface emission
    // follows the resulting albedo in the celestial presentation pass.
    return 0.82+0.18*pow(lambert,0.70);
}

float basinMoonRimIllumination(vec3 eye, vec3 ray) {
    // The illuminated visible limb, feathered rather than sampled at one hard
    // tangent point, so crescent and gibbous halo ends taper naturally.
    vec3 toCentre=uBodyPosition-eye;
    float distanceToCentre=length(toCentre);
    if (distanceToCentre<=1e-6) return 0.0;
    vec3 forward=toCentre/distanceToCentre;
    float facing=dot(ray,forward);
    if (facing<=0.0) return 0.0;
    vec3 radial=ray-forward*facing;
    float radialLength=length(radial);
    if (radialLength<=1e-6) return 0.0;
    vec3 radialDir=radial/radialLength;
    vec3 normalA=normalize(radialDir-0.03*forward);
    vec3 normalB=normalize(radialDir-0.10*forward);
    float litA=smoothstep(0.0,0.06,dot(normalA,basinMoonLightDirection(eye)));
    float litB=smoothstep(0.0,0.08,dot(normalB,basinMoonLightDirection(eye)));
    return clamp(0.70*litA+0.30*litB,0.0,1.0);
}

float basinMoonInnerRimEmission(vec3 eye,vec3 hitPoint) {
    vec3 normal=normalize(hitPoint-uBodyPosition);
    vec3 toEye=normalize(eye-hitPoint);
    float facing=clamp(dot(normal,toEye),0.0,1.0);
    // This subordinate feather stays near the illuminated rim; whole-surface
    // emission is supplied separately by the celestial presentation pass.
    float innerBand=(1.0-smoothstep(0.04,0.34,facing))*(0.56+0.44*(1.0-smoothstep(0.0,0.17,facing)));
    return innerBand*basinMoonRimIllumination(eye,normalize(hitPoint-eye));
}

float basinCelestialHaloGain(vec2 glow,float midband,float beatPulse) {
    // Preserve acoustic headroom before applying authored Reactivity. A hard
    // clamp after Reactivity pinned real music at its ceiling for most frames.
    float drive=0.22*max(midband,0.0)+1.35*max(beatPulse,0.0);
    float response=drive/(0.45+drive);
    return max(glow.x,0.0)*(0.54+0.92*clamp(glow.y,0.0,2.0)*response);
}

float basinCelestialRimMarks(vec3 eye,vec3 ray,float normalizedAngle) {
    // Sparse screen-antialiased marks on the same analytic outer silhouette.
    // This helper is evaluated only for the optional experiment, never a mesh.
    vec3 forward=normalize(uBodyPosition-eye);
    vec3 right=cross(vec3(0.0,1.0,0.0),forward);
    if (dot(right,right)<1e-5) right=cross(vec3(0.0,0.0,1.0),forward);
    right=normalize(right);
    vec3 up=cross(forward,right);
    float angle=atan(dot(ray,up),dot(ray,right));
    float radialPixel=max(length(vec2(dFdx(normalizedAngle),dFdy(normalizedAngle))),1e-5);
    float circumference=6.28318530718/radialPixel;
    // Fixed angular slots: resizing fades additional marks into place rather
    // than moving every mark whenever an integer population changes.
    float desired=clamp(circumference/24.0,8.0,32.0);
    float sector=6.28318530718/32.0;
    float index=floor((angle+0.5*sector)/sector);
    float membership=mod(index,4.0)==0.0 ? 1.0 :
                     (mod(index,2.0)==0.0 ? smoothstep(8.0,16.0,desired)
                                          : smoothstep(16.0,32.0,desired));
    float tangent=abs(mod(angle+0.5*sector,sector)-0.5*sector)/radialPixel;
    float radial=(normalizedAngle-1.0)/radialPixel;
    float mark=1.0-smoothstep(0.65,1.65,length(vec2(tangent,radial)));
    float lit=uBodyKind==1 ? basinMoonRimIllumination(eye,ray) : 1.0;
    return mark*lit*membership;
}

float basinMoonCraters(vec3 normal) {
    vec3 p=normal*7.6;
    vec3 cell=floor(p);
    float shade=1.0, rimLight=0.0;
    // Impacts remain continuous across the sphere, but stay subordinate to the
    // broad lunar form instead of reading as a noisy polka-dot field.
    for (int z=-1; z<=1; ++z) {
        for (int y=-1; y<=1; ++y) {
            for (int x=-1; x<=1; ++x) {
                vec3 c=cell+vec3(float(x),float(y),float(z));
                float seed=basinMoonHash(c+vec3(11.3,7.1,19.2));
                if (seed<0.72) continue;
                vec3 centre=c+vec3(basinMoonHash(c),
                                   basinMoonHash(c+vec3(17.0,1.0,0.0)),
                                   basinMoonHash(c+vec3(0.0,23.0,1.0)))*0.55+0.225;
                float radius=mix(0.12,0.31,basinMoonHash(c+vec3(3.0,5.0,13.0)));
                float distanceToImpact=length(p-centre);
                float edge=0.022;
                float bowl=1.0-smoothstep(radius-edge,radius+edge,distanceToImpact);
                float rim=1.0-smoothstep(edge,edge+0.050,abs(distanceToImpact-radius));
                shade=min(shade,1.0-(0.05+0.08*seed)*bowl);
                rimLight=max(rimLight,rim*(0.012+0.014*seed));
            }
        }
    }
    return clamp(shade+rimLight,0.78,1.04);
}

float basinMoonAlbedo(vec3 normal) {
    // Subtle, world-stable lunar detail stays subordinate to the luminous
    // silhouette. No map islands, contour print or repeated surface lattice.
    float broad=basinMoonNoise(normal*2.8+vec3(2.3,7.1,1.7));
    float mottled=basinMoonNoise(normal*6.1+vec3(13.8,2.4,9.3));
    return (0.97-0.045*broad-0.020*mottled)
           *(0.96+0.04*basinMoonCraters(normal));
}

// A nearest positive ray-sphere hit.  ``hitPoint`` is in the caller's shared
// Scene3D world space and can be projected through that scene's camera for depth.
float basinCelestialSkyMask(vec3 eye,vec3 worldRay) {
    if ((uBodyKind != 0 && uBodyKind != 1) || uSunEnabled == 0 || uBodySize <= 0.0) {
        return 0.0;
    }
    // Transparent/near-camera-cull bodies may not carve starless holes in sky.
    float bodyAlpha=(uBodyKind==1 ? uMoonColor.a : uSunColor.a);
    if (bodyAlpha<=0.0001) return 0.0;
    float rayLength=length(worldRay);
    if (rayLength<=1e-8) return 0.0;
    vec3 ray=worldRay/rayLength;
    vec3 offset=eye-uBodyPosition;
    float halfB=dot(offset,ray);
    float discriminant=halfB*halfB-(dot(offset,offset)-uBodySize*uBodySize);
    if (discriminant<0.0) return 0.0;
    float root=sqrt(max(discriminant,0.0));
    float distance=-halfB-root;
    if (distance<=1e-5) distance=-halfB+root;
    if (distance<=1e-5) return 0.0;
    vec3 centre=uBodyPosition-eye;
    float separation=length(centre);
    vec3 forward=centre/max(separation,1e-5);
    float facing=dot(ray,forward);
    float radius=uBodySize/max(separation,1e-5);
    float normalizedAngle=length(cross(ray,forward))/max(facing*radius,1e-5);
    float bodyCoverage=basinCameraBodyCoverage(separation,uBodySize);
    if (uBodyKind==1) {
        // The Moon is a solid 3-D body, including its dim shaded hemisphere.
        // Its exact antialiased disc coverage also owns star suppression.
        vec3 normal=(eye+ray*distance-uBodyPosition)/uBodySize;
        float limb=smoothstep(0.015,0.10,max(dot(normal,-ray),0.0));
        return bodyCoverage*bodyAlpha*limb;
    }
    return bodyCoverage*step(0.0,facing)*(1.0-smoothstep(0.998,1.014,normalizedAngle));
}

vec4 basinCelestial(vec3 eye, vec3 worldRay, out vec3 hitPoint) {
    hitPoint = vec3(0.0);
    if ((uBodyKind != 0 && uBodyKind != 1) || uSunEnabled == 0 || uBodySize <= 0.0) {
        return vec4(0.0);
    }
    float rayLength = length(worldRay);
    if (rayLength <= 1e-8) return vec4(0.0);
    vec3 ray = worldRay / rayLength;
    vec3 offset = eye - uBodyPosition;
    float halfB = dot(offset, ray);
    float discriminant = halfB * halfB - (dot(offset, offset) - uBodySize * uBodySize);
    if (discriminant < 0.0) return vec4(0.0);
    float root = sqrt(max(discriminant, 0.0));
    float distance = -halfB - root;
    if (distance <= 1e-5) distance = -halfB + root;
    if (distance <= 1e-5) return vec4(0.0);

    hitPoint = eye + ray * distance;
    vec3 normal = (hitPoint - uBodyPosition) / uBodySize;
    float facing = max(dot(normal, -ray), 0.0);
    float limb = smoothstep(0.015, 0.10, facing);
    if (uBodyKind == 0) {
        float intensity = 1.0;
        float cutCoverage = 1.0;
        if (normal.y < 0.0) {
            float lowerHemisphere = -normal.y;
            float stripePhase = lowerHemisphere * 7.0;
            float cutDistance = abs(fract(stripePhase) - 0.5);
            float aa = max(fwidth(stripePhase), 0.004);
            cutCoverage = smoothstep(0.11 - aa, 0.11 + aa, cutDistance);
            intensity = mix(0.82, 1.0, 0.5 + 0.5 * sin(lowerHemisphere * 3.14159265));
        }
        vec3 sun = max(uSunColor.rgb, vec3(0.0)) * intensity;
        float alpha = clamp(uSunColor.a, 0.0, 1.0) * limb * cutCoverage;
        return vec4(sun, alpha);
    }

    float illumination=basinMoonIllumination(normal,eye);
    float lunarRock=basinMoonAlbedo(normal);
    float earthshine=0.018+0.020*pow(max(dot(normal,-ray),0.0),0.7);
    float brightness=mix(earthshine,basinMoonSurfaceBrightness(normal,eye)*lunarRock,illumination);
    vec3 moon=max(uMoonColor.rgb,vec3(0.0))*brightness;
    return vec4(moon,clamp(uMoonColor.a,0.0,1.0)*limb);
}

float basinStarHash(vec2 cell) {
    return fract(sin(dot(cell, vec2(41.37, 289.13))) * 24634.6345);
}

float basinStarField(vec3 ray) {
    vec2 grid = vec2(atan(ray.x, -ray.z), asin(clamp(ray.y, -1.0, 1.0))) * 420.0;
    vec2 cell = floor(grid);
    vec2 pixelDistance = (fract(grid) - 0.5) / max(fwidth(grid), vec2(1e-4));
    float pixelAlpha = 1.0 - smoothstep(0.15, 0.65, length(pixelDistance));
    float aboveHorizon = smoothstep(-0.45, -0.25, ray.y);
    return step(0.985, basinStarHash(cell)) * pixelAlpha * aboveHorizon;
}

float basinBeatStarLight(vec3 ray,vec2 glow) {
    if (uBeatStarCount<=0) return 0.0;
    vec2 grid=vec2(atan(ray.x,-ray.z),asin(clamp(ray.y,-1.0,1.0)))*420.0;
    float light=0.0;
    vec2 pixelScale=max(fwidth(grid),vec2(1e-4));
    for (int i=0; i<6; ++i) {
        if (i>=uBeatStarCount) break;
        // Cull far cells before costly halo math. This is an opt-in effect,
        // and only three (occasionally six) small star regions participate.
        vec2 difference=grid-uBeatStarCells[i].xy-0.5;
        if (any(greaterThan(abs(difference),vec2(1.0)+6.0*pixelScale))) continue;
        // Actual panorama cells, with a several-pixel halo and a restrained
        // star-like cross/ray core at strong settings rather than a soft blob.
        vec2 delta=difference/pixelScale;
        float radius=length(delta);
        float core=1.0-smoothstep(0.0,1.35,radius);
        float halo=1.0-smoothstep(1.0,6.0,radius);
        float cross=(1.0-smoothstep(0.0,0.85,min(abs(delta.x),abs(delta.y))))
                   *(1.0-smoothstep(1.4,5.8,max(abs(delta.x),abs(delta.y))));
        float diagonal=(1.0-smoothstep(0.0,0.9,abs(abs(delta.x)-abs(delta.y))))
                      *(1.0-smoothstep(1.5,5.2,radius));
        float gain=glow.x*(0.62+0.78*clamp(glow.y*uBeatStarCells[i].z*2.2,0.0,1.0));
        light+=gain*uBeatStarCells[i].z*(1.70*core+0.72*halo+0.40*cross+0.22*diagonal);
    }
    return light;
}

// Straight-alpha sky radiance.  The independent enable gate makes the sky
// transparent when disabled; the Sun/Moon remains a separate body pass.
// detail: the clouds' and nebula's octaves are full for the visible sky (1) and two for reflections (0),
// which glass samples five times per fragment and roughness blurs anyway.
vec4 basinSkyBackground(vec3 worldRay,float starVisibility,int detail) {
    if (uSkyEnabled == 0 || uSkyStrength <= 0.0) return vec4(0.0);
    float rayLength = length(worldRay);
    if (rayLength <= 1e-8) return vec4(0.0);
    vec3 ray = worldRay / rayLength;
    float latitude = asin(clamp(ray.y, -1.0, 1.0));
    float dusk = exp(-pow((ray.y + 0.50) / 0.16, 2.0));
    vec3 colour = max(uSkyColor.rgb, vec3(0.0)) * (0.65 + 0.35 * dusk);
    colour += max(uHorizonColor.rgb, vec3(0.0)) *
              clamp(uHorizonColor.a, 0.0, 1.0) * dusk;

    float longitude = atan(ray.x, -ray.z);
    float clouds = 0.0;
    for (int band = 0; band < 3; ++band) {
        float bandIndex = float(band);
        float phase = bandIndex * 1.7;
        // Wide, discontinuous wisps rather than three near-constant latitude
        // strokes. Those narrow parallel strokes read as a false geometric
        // horizon when the camera swivels above the real mountains.
        float centre = -0.32 - bandIndex * 0.055 +
                       0.024 * sin(longitude * 5.0 + phase) +
                       0.014 * sin(longitude * 17.0 - phase);
        float thickness = 0.014 + 0.004 * bandIndex;
        float shape = 1.0 - smoothstep(thickness, thickness + 0.013,
                                       abs(latitude - centre));
        float gaps = 0.35 + 0.24 * sin(longitude * 11.0 + phase)
                    + 0.24 * sin(longitude * 27.0 - phase);
        float broken = smoothstep(0.33, 0.66, gaps);
        float density = 0.5 + 0.5 * sin(ray.y * 170.0 + longitude * 7.0);
        clouds += shape * broken * density;
    }
    // Volumetric clouds replace the thin bands.
    if (uClouds.w <= 0.0)
        colour += max(uCloudColor.rgb, vec3(0.0)) *
                  clamp(uCloudColor.a, 0.0, 1.0) * clamp(clouds, 0.0, 1.0);
    vec3 nebulaRay = vec3(ray.x * cos(uNebulaTurn) - ray.z * sin(uNebulaTurn), ray.y,
                          ray.x * sin(uNebulaTurn) + ray.z * cos(uNebulaTurn));
    colour += skyNebula(nebulaRay, uNebulaColorA.rgb * uNebulaColorA.a, uNebulaColorB.rgb * uNebulaColorB.a, uNebula, 29u,
                        detail == 1 ? 4 : 2);

    float stars = basinStarField(ray) * clamp(uStarColor.a, 0.0, 1.0) * starVisibility;
    colour += max(uStarColor.rgb, vec3(0.0)) * stars;
    colour += max(basinBeatStarColour(), vec3(0.0)) * basinBeatStarLight(ray,uStarGlow) * starVisibility;
    if (uClouds.w > 0.0) {
        // Lit from the body's side; a dimmer, cooler underside. Clouds pass in front of the stars.
        vec3 bodyColour = uSunEnabled == 1 ? (uBodyKind == 0 ? uSunColor.rgb : uMoonColor.rgb) : uCloudColor.rgb;
        vec3 lit = mix(uCloudColor.rgb, bodyColour, 0.6);
        vec3 shade = uCloudColor.rgb * 0.55 + max(uSkyColor.rgb, vec3(0.0)) * 0.3;
        vec4 cloud = skyClouds(ray, normalize(uBodyPosition + vec3(0.0, 1e-3, 0.0)),
                               vec4(uClouds.xyz, uClouds.w * clamp(uCloudColor.a, 0.0, 1.0)), uCloudDrift,
                               shade, lit, 17u, detail == 1 ? 5 : 2);
        colour = colour * (1.0 - cloud.a) + cloud.rgb;
    }
    // Keep sky alpha continuous across the camera. The old latitude-based
    // opacity transition created a ruler-straight wallpaper seam unrelated
    // to the terrain skyline, especially when the distant skirt faded out.
    // Dusk/horizon atmosphere varies in *colour* above, not in coverage.
    // Terrain owns its fade/occlusion independently, so no second horizon
    // authority is needed in the sky shader.
    float alpha = clamp(uSkyColor.a * uSkyStrength, 0.0, 1.0);
    return vec4(colour, alpha);
}

// Premultiplied radiance for reflection.  The caller supplies the exact visible
// body after its scene-depth/terrain tests, so buried celestial geometry cannot
// leak into the sky's reflection.
vec3 basinCompositeSkyBody(vec4 sky, vec4 body) {
    float bodyAlpha = clamp(body.a, 0.0, 1.0);
    float skyAlpha = clamp(sky.a, 0.0, 1.0);
    return body.rgb * bodyAlpha + sky.rgb * skyAlpha * (1.0 - bodyAlpha);
}
"""

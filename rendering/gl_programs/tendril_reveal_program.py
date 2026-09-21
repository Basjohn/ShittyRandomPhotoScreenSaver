"""Bounded branching and thickening tendril reveal shader."""

from __future__ import annotations


TENDRIL_REVEAL_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform float u_seed;
uniform float u_detail;

float hash21(vec2 p) { return fract(sin(dot(p, vec2(41.3, 289.1))) * 24634.6345); }
float segmentDistance(vec2 p, vec2 a, vec2 b) {
    vec2 ab = b - a;
    return length(p - (a + ab * clamp(dot(p-a, ab) / max(dot(ab,ab), 1e-5), 0.0, 1.0)));
}
float tendrilField(vec2 p, float seed, float t, float detail) {
    float nearest = 9.0;
    vec2 root = vec2(0.5, 0.52);
    // Fixed, well-separated directions keep a visible branching network.
    // Only the travelled length changes with time; branch roots never wander.
    float growth=clamp(t/.72,0.0,1.0);
    for (int i = 0; i < 9; ++i) {
        float fi=float(i);
        float variation=hash21(vec2(seed, fi));
        float a=6.28318530718*(fi/9.0 + hash21(vec2(seed, 31.0))*.12
            + (variation-.5)*.055);
        vec2 direction=vec2(cos(a),sin(a));
        vec2 perpendicular=vec2(-direction.y,direction.x);
        float length1=.52+.22*hash21(vec2(fi,seed));
        vec2 fullTip=root+direction*length1;
        vec2 elbow=mix(root,fullTip,.48)+perpendicular*(variation-.5)*.10;
        vec2 firstTip=mix(root,elbow,clamp(growth/.48,0.0,1.0));
        nearest=min(nearest,segmentDistance(p,root,firstTip));
        if(growth>.48) {
            vec2 tip=mix(elbow,fullTip,clamp((growth-.48)/.52,0.0,1.0));
            nearest=min(nearest,segmentDistance(p,elbow,tip));
            float childAngle=a+mix(-.85,.85,step(.5,variation));
            vec2 child=elbow+vec2(cos(childAngle),sin(childAngle))
                *(.20+.14*hash21(vec2(fi+23.0,seed)))
                *clamp((growth-.48)/.40,0.0,1.0);
            nearest=min(nearest,segmentDistance(p,elbow,child));
        }
    }
    // Thin branches lead, then their distance field expands to seal the plane.
    // Final expansion is independent of detail so every authored setting ends
    // continuously before the exact destination endpoint.
    float thickness=(.003+.008*t)*detail*smoothstep(0.0,.06,t)
        + .80*smoothstep(.60,.99,t);
    return nearest - thickness;
}
void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);
    if (t <= 0.0) { FragColor = texture(uOldTex, uv); return; }
    if (t >= 1.0) { FragColor = texture(uNewTex, uv); return; }
    float veins = 1.0 - smoothstep(-0.004, 0.012, tendrilField(uv, u_seed, t, u_detail));
    FragColor = mix(texture(uOldTex, uv), texture(uNewTex, uv), veins);
}
"""

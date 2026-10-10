"""Edge Bloom Reveal: shader and CPU mirrors (loaded only when Edge Bloom Reveal renders).

The glow is one chosen colour, the next picture's accent colour, or each picture's own accent for its own
lines (``rendering/gl_programs/photo_colour``).

The old picture sinks into night while its own contours light up; then the new picture's contours
appear over it as luminous lines, strongest first, crackling. Light spreads out from the lines,
and the new picture fills in from its contours outward (a glowing rim on the front) until its flat
regions, farthest from any contour, close last. The glow fades and every effect is gone by
``EDGE_BLOOM_SETTLED``, so both ends are the exact photographs.

Both pictures' contours come from an edge field each (``rendering/quick/scene3d/edge_field``):
the distance to the nearest contour and its strength. Lines are drawn from the distance, so they
are smooth at any field size; the fill depends on distance and a smooth seeded bloom order, so its
front stays continuous while the picture blooms area by area.
"""

from __future__ import annotations

from rendering.gl_programs.analog_signal import ANALOG_SIGNAL_GLSL
from rendering.quick.scene3d.edge_field import EDGE_FIELD_GLSL

# The old picture sinks into night over this window, and its own lines glow over this one
# (rise start, full, fade start, gone).
EDGE_BLOOM_NIGHT = (0.0, 0.22)
EDGE_BLOOM_OLD_LINES = (0.02, 0.14, 0.2, 0.36)
# A seeded, low-frequency bloom order (0-1 over the picture) delays whole areas by up to
# EDGE_BLOOM_ORDER of the run, so the picture blooms patch by patch instead of all at once.
EDGE_BLOOM_ORDER = 0.4
# A line of strength s in an area of order o appears at
# EDGE_BLOOM_APPEAR[0] + EDGE_BLOOM_APPEAR[1] * (1 - s) + 0.6 * EDGE_BLOOM_ORDER * o: strongest first.
EDGE_BLOOM_APPEAR = (0.1, 0.12)
# The fill leaves the lines at EDGE_BLOOM_FILL_START (plus the area's order delay) and travels
# EDGE_BLOOM_SPEED picture heights per run, softer the farther it has come; nothing fills later
# than EDGE_BLOOM_LATEST.
EDGE_BLOOM_FILL_START = 0.3
EDGE_BLOOM_SPEED = 0.6
EDGE_BLOOM_SOFT = (0.05, 0.12)
EDGE_BLOOM_JITTER = 0.06
EDGE_BLOOM_LATEST = 0.8
# Lines are this many field texels wide.
EDGE_BLOOM_LINE_TEXELS = 1.8
# The glow fades over this window; from EDGE_BLOOM_SETTLED on, the frame is the new picture.
EDGE_BLOOM_FADE = (0.78, 0.95)
EDGE_BLOOM_SETTLED = 0.97


def edge_bloom_thresholds(detail: float) -> tuple[float, float]:
    """The contour-strength window for Detail ``detail`` (0: only the strongest contours, 1: fine detail)."""
    detail = max(0.0, min(1.0, float(detail)))
    low = 0.11 + (0.025 - 0.11) * detail
    return low, low * 2.5


def edge_bloom_appear(strength: float, order: float = 0.0) -> float:
    """When a line of ``strength`` (0-1) appears in an area of bloom ``order`` (0-1)."""
    strength = max(0.0, min(1.0, strength))
    return EDGE_BLOOM_APPEAR[0] + EDGE_BLOOM_APPEAR[1] * (1.0 - strength) + 0.6 * EDGE_BLOOM_ORDER * order


def edge_bloom_fill_time(distance: float, order: float = 0.0, jitter: float = 0.0) -> float:
    """When the fill reaches a point ``distance`` picture heights from its nearest contour, in an
    area of bloom ``order`` (0-1; ``jitter`` in -0.5..0.5 roughens the front)."""
    time = (EDGE_BLOOM_FILL_START + EDGE_BLOOM_ORDER * order + distance / EDGE_BLOOM_SPEED
            + EDGE_BLOOM_JITTER * jitter)
    return min(time, EDGE_BLOOM_LATEST)


def edge_bloom_softness(distance: float) -> float:
    """How long the fill takes to pass a point ``distance`` picture heights from its contour."""
    lo, hi = EDGE_BLOOM_SOFT
    return lo + (hi - lo) * max(0.0, min(1.0, distance / 0.35))


EDGE_BLOOM_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uOldField;\nuniform sampler2D uNewField;\n"
    "uniform float uProgress;\nuniform float uTime;\nuniform float uLineWidth;\n"
    "uniform float uGlow;\nuniform float uSeed;\nuniform vec3 uColor;\nuniform vec3 uOldColor;\n"
    + ANALOG_SIGNAL_GLSL
    + EDGE_FIELD_GLSL
    + f"""
float bloomNoise(vec2 x, uint salt, uint seed) {{
    vec2 i = floor(x), f = x - i;
    f = f * f * (3.0 - 2.0 * f);
    uint ix = uint(int(i.x) + 65536), iy = uint(int(i.y) + 65536);
    float a = signalRandom(ix + iy * 131071u, salt, seed), b = signalRandom(ix + 1u + iy * 131071u, salt, seed);
    float c = signalRandom(ix + (iy + 1u) * 131071u, salt, seed);
    float d = signalRandom(ix + 1u + (iy + 1u) * 131071u, salt, seed);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}}

void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    uint seed = uint(uSeed);
    float p = uProgress;
    vec3 oldColour = texture(uOldTex, uv).rgb;
    vec3 newColour = texture(uNewTex, uv).rgb;

    // The old picture sinks into night.
    float night = smoothstep({EDGE_BLOOM_NIGHT[0]:.4f}, {EDGE_BLOOM_NIGHT[1]:.4f}, p);
    float luma = dot(oldColour, vec3(0.299, 0.587, 0.114));
    vec3 old = mix(oldColour, (0.22 * oldColour + 0.3 * luma) * vec3(0.55, 0.7, 1.0), night);

    // The new picture fills in from its contours outward, area by area in a seeded bloom order:
    // a continuous function of position and distance, so the front never breaks into cells.
    vec2 field = edgeFieldSample(uNewField, uv);
    float order = smoothstep(0.25, 0.75, 0.7 * bloomNoise(uv * vec2(2.4, 1.8), 4u, seed)
                                         + 0.3 * bloomNoise(uv * 5.0, 5u, seed));
    float jitter = bloomNoise(uv * vec2(9.0, 7.0), 1u, seed) * 0.65 + bloomNoise(uv * 31.0, 2u, seed) * 0.35 - 0.5;
    float fill = min({EDGE_BLOOM_FILL_START:.4f} + {EDGE_BLOOM_ORDER:.4f} * order + field.x / {EDGE_BLOOM_SPEED:.4f}
                     + {EDGE_BLOOM_JITTER:.4f} * jitter, {EDGE_BLOOM_LATEST:.4f});
    float soft = mix({EDGE_BLOOM_SOFT[0]:.4f}, {EDGE_BLOOM_SOFT[1]:.4f}, clamp(field.x / 0.35, 0.0, 1.0));
    float reveal = smoothstep(fill, fill + soft, p);
    vec3 colour = mix(old, newColour, reveal);

    // Light: the new picture's lines (strongest first, crackling), a glow spreading out from them
    // over the dark old picture, and a rim on the fill front. All fade before the end.
    float fade = 1.0 - smoothstep({EDGE_BLOOM_FADE[0]:.4f}, {EDGE_BLOOM_FADE[1]:.4f}, p);
    float appear = {EDGE_BLOOM_APPEAR[0]:.4f} + {EDGE_BLOOM_APPEAR[1]:.4f} * (1.0 - field.y)
                 + {0.6 * EDGE_BLOOM_ORDER:.4f} * order;
    float shown = smoothstep(appear, appear + 0.04, p);
    float width = uLineWidth;
    float crackle = 0.6 + 0.4 * bloomNoise(uv * 140.0 + vec2(uTime * 7.0, -uTime * 5.0), 3u, seed);
    // A line dims once the picture around it has filled in.
    float settled = 1.0 - 0.85 * smoothstep(fill + soft, fill + soft + 0.18, p);
    float line = field.y * shown * settled * exp(-pow(field.x / width, 2.0)) * crackle;
    float core = field.y * shown * settled * exp(-pow(field.x / (0.45 * width), 2.0));
    float spread = clamp((p - appear) / 0.3, 0.0, 1.0);
    float halo = field.y * shown * exp(-pow(field.x / (width + 0.025 * spread), 2.0)) * (1.0 - 0.6 * reveal);
    float rim = exp(-pow((p - fill - 0.5 * soft) / (0.5 * soft), 2.0)) * smoothstep(appear, appear + 0.1, p);
    colour += uGlow * fade * (uColor * (line * 1.2 + halo * 0.45 + rim * 0.3) + vec3(core * 0.5));

    // First the old picture's own contours light up as it darkens.
    vec2 oldField = edgeFieldSample(uOldField, uv);
    float oldLines = oldField.y * exp(-pow(oldField.x / width, 2.0))
                   * smoothstep({EDGE_BLOOM_OLD_LINES[0]:.4f}, {EDGE_BLOOM_OLD_LINES[1]:.4f}, p)
                   * (1.0 - smoothstep({EDGE_BLOOM_OLD_LINES[2]:.4f}, {EDGE_BLOOM_OLD_LINES[3]:.4f}, p));
    colour += uGlow * uOldColor * oldLines * (1.0 - reveal);

    FragColor = vec4(clamp(colour, 0.0, 1.0), 1.0);
}}
"""
)

"""Edge field: a per-run, renderer-owned map of a photograph's contours and the distance to them.

A shared primitive for reveals that grow out of a picture's structure (Edge Bloom Reveal first;
organic fills such as Capillary Bloom or Surface Tension Merge can seed it differently later).
Built once per run and photograph on the render thread, from the lent presentation texture, by
five compute stages at a reduced size (``EDGE_FIELD_SIZE`` on the longer side, the render's aspect):

1. luma: a box-filtered luma copy of the photograph (16 taps over each field texel's footprint);
2. blur: a 5x5 binomial blur applied twice (9x9 in effect), so texture and grain stop
   reading as edges;
3. edges: Sobel gradient magnitude thinned to its ridges (non-maximum suppression across the
   gradient, as Canny does) and mapped to a 0-1 strength by ``low``/``high``: the picture's
   structural contours, one texel wide. Texels from ``EDGE_FIELD_SEED`` strength seed the flood at
   their sub-texel ridge position (a parabola through the magnitudes across the ridge), so lines
   drawn from the distance do not stair-step on the texel grid;
4. jump flooding (one dispatch per step, N/2 ... 1 plus a final 1) on 32-bit seed positions: every
   texel finds its nearest seed;
5. resolve: the field texture holds, per texel, the distance to the nearest contour (picture
   heights) and that contour's strength. It is sampled with linear filtering at the photograph's
   uv; a consumer draws smooth lines of any width from the distance.

``EDGE_FIELD_GLSL`` gives consumers ``edgeFieldSample``. ``edge_field_reference`` is the exact CPU
mirror of stages 2-5 for tests (brute-force distances where the flood approximates).

Dormancy: nothing exists until a consumer warms it for a render size; ``release()`` (at the
consumer's ``park()``) drops every texture. No readback, queue or polling; the build is a handful
of dispatches in the frame that first needs the field.
"""
from __future__ import annotations

import ctypes
import math

import numpy as np
from OpenGL import GL as gl

from .compute import bound_image, dispatch

EDGE_FIELD_SIZE = 768
EDGE_FIELD_NONE = 4.0          # distance reported where a picture has no contour at all (picture heights)
EDGE_FIELD_SEED = 0.25         # strength from which a texel seeds the flood
_GROUP = 16
_LUMA = (0.299, 0.587, 0.114)

# Sobel magnitude of luma, normalised so a hard black-white step reads about 1.
_SOBEL_SCALE = 0.25

EDGE_FIELD_GLSL = """
// (distance to the nearest contour in picture heights, that contour's strength 0-1)
vec2 edgeFieldSample(sampler2D field, vec2 uv) {
    return texture(field, uv).rg;
}
"""

_HEADER = f"#version 460 core\nlayout(local_size_x = {_GROUP}, local_size_y = {_GROUP}) in;\nuniform ivec2 uSize;\n"

_LUMA_COMPUTE = _HEADER + f"""
uniform sampler2D uPhoto;
uniform vec2 uStep;                 // a quarter of one field texel, in uv
layout(r16f, binding = 0) writeonly uniform image2D uLuma;
void main() {{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= uSize.x || p.y >= uSize.y) return;
    vec2 uv = (vec2(p) + 0.5) / vec2(uSize);
    vec3 sum = vec3(0.0);
    for (int y = 0; y < 4; ++y)
        for (int x = 0; x < 4; ++x)
            sum += texture(uPhoto, uv + (vec2(x, y) - 1.5) * uStep).rgb;
    imageStore(uLuma, p, vec4(dot(sum / 16.0, vec3({_LUMA[0]}, {_LUMA[1]}, {_LUMA[2]})), 0.0, 0.0, 0.0));
}}
"""

_BLUR_COMPUTE = _HEADER + """
layout(r16f, binding = 0) readonly uniform image2D uLuma;
layout(r16f, binding = 1) writeonly uniform image2D uBlur;
const float W[5] = float[5](1.0, 4.0, 6.0, 4.0, 1.0);
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= uSize.x || p.y >= uSize.y) return;
    float sum = 0.0;
    for (int y = -2; y <= 2; ++y)
        for (int x = -2; x <= 2; ++x)
            sum += W[x + 2] * W[y + 2] * imageLoad(uLuma, clamp(p + ivec2(x, y), ivec2(0), uSize - 1)).r;
    imageStore(uBlur, p, vec4(sum / 256.0, 0.0, 0.0, 0.0));
}
"""

_EDGES_COMPUTE = _HEADER + f"""
uniform float uLow;
uniform float uHigh;
layout(r16f, binding = 0) readonly uniform image2D uLuma;
layout(r16f, binding = 1) writeonly uniform image2D uEdge;
layout(rg32f, binding = 2) writeonly uniform image2D uSeed;
float lumaAt(ivec2 q) {{
    return imageLoad(uLuma, clamp(q, ivec2(0), uSize - 1)).r;
}}
vec2 gradientAt(ivec2 p) {{
    float a = lumaAt(p + ivec2(-1, -1)), b = lumaAt(p + ivec2(0, -1)), c = lumaAt(p + ivec2(1, -1));
    float d = lumaAt(p + ivec2(-1, 0)), f = lumaAt(p + ivec2(1, 0));
    float g = lumaAt(p + ivec2(-1, 1)), h = lumaAt(p + ivec2(0, 1)), i = lumaAt(p + ivec2(1, 1));
    return vec2(c + 2.0 * f + i - a - 2.0 * d - g, g + 2.0 * h + i - a - 2.0 * b - c) * {_SOBEL_SCALE};
}}
void main() {{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= uSize.x || p.y >= uSize.y) return;
    vec2 gradient = gradientAt(p);
    float magnitude = length(gradient);
    vec2 seed = vec2(p);
    // Thin to the ridge: keep a texel only if it is the strongest across the gradient, and place it
    // where a parabola through the three magnitudes across the ridge peaks.
    if (magnitude > 0.0) {{
        ivec2 o = ivec2(floor(gradient / magnitude + 0.5));
        ivec2 ahead = clamp(p + o, ivec2(0), uSize - 1), behind = clamp(p - o, ivec2(0), uSize - 1);
        float forward = length(gradientAt(ahead)), backward = length(gradientAt(behind));
        if (magnitude < forward || magnitude <= backward) {{
            magnitude = 0.0;
        }} else {{
            float curve = backward - 2.0 * magnitude + forward;
            float shift = curve < -1e-6 ? clamp(0.5 * (backward - forward) / curve, -0.49, 0.49) : 0.0;
            seed += shift * vec2(o);
        }}
    }}
    float strength = smoothstep(uLow, uHigh, magnitude);
    imageStore(uEdge, p, vec4(strength, 0.0, 0.0, 0.0));
    imageStore(uSeed, p, strength >= {EDGE_FIELD_SEED} ? vec4(seed, 0.0, 0.0) : vec4(-1.0, -1.0, 0.0, 0.0));
}}
"""

_FLOOD_COMPUTE = _HEADER + """
uniform int uJump;
layout(rg32f, binding = 0) readonly uniform image2D uSeedIn;
layout(rg32f, binding = 1) writeonly uniform image2D uSeedOut;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= uSize.x || p.y >= uSize.y) return;
    vec2 best = vec2(-1.0);
    float bestDistance = 1e20;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            ivec2 q = p + ivec2(x, y) * uJump;
            if (q.x < 0 || q.y < 0 || q.x >= uSize.x || q.y >= uSize.y) continue;
            vec2 seed = imageLoad(uSeedIn, q).rg;
            if (seed.x < 0.0) continue;
            vec2 delta = seed - vec2(p);
            float distance = dot(delta, delta);
            if (distance < bestDistance) {
                bestDistance = distance;
                best = seed;
            }
        }
    }
    imageStore(uSeedOut, p, vec4(best, 0.0, 0.0));
}
"""

_RESOLVE_COMPUTE = _HEADER + f"""
layout(rg32f, binding = 0) readonly uniform image2D uSeed;
layout(r16f, binding = 1) readonly uniform image2D uEdge;
layout(rg16f, binding = 2) writeonly uniform image2D uField;
void main() {{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= uSize.x || p.y >= uSize.y) return;
    vec2 seed = imageLoad(uSeed, p).rg;
    vec2 value = vec2({EDGE_FIELD_NONE:.1f}, 0.0);
    if (seed.x >= 0.0) {{
        value = vec2(length(seed - vec2(p)) / float(uSize.y), imageLoad(uEdge, ivec2(floor(seed + 0.5))).r);
    }}
    imageStore(uField, p, vec4(value, 0.0, 0.0));
}}
"""

EDGE_FIELD_PROGRAMS = (("edge_field_luma", _LUMA_COMPUTE), ("edge_field_blur", _BLUR_COMPUTE),
                       ("edge_field_edges", _EDGES_COMPUTE), ("edge_field_flood", _FLOOD_COMPUTE),
                       ("edge_field_resolve", _RESOLVE_COMPUTE))


def edge_field_size(pixel_size: tuple[int, int]) -> tuple[int, int]:
    """The field's size for a render of ``pixel_size``: its aspect, ``EDGE_FIELD_SIZE`` on the longer side."""
    width, height = max(1, int(pixel_size[0])), max(1, int(pixel_size[1]))
    scale = min(1.0, EDGE_FIELD_SIZE / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def edge_field_jumps(size: tuple[int, int]) -> tuple[int, ...]:
    """Jump-flood step lengths for ``size``: N/2 ... 1, then 1 again (the 1+JFA refinement)."""
    n = 1 << max(1, math.ceil(math.log2(max(size))))
    jumps = []
    step = n // 2
    while step >= 1:
        jumps.append(step)
        step //= 2
    return (*jumps, 1)


def edge_field_warm_entries(resources) -> list[tuple]:
    """The gradual warm-up entries for the field's compute programs."""
    return [(resources, key, source) for key, source in EDGE_FIELD_PROGRAMS]


def _blur_reference(luma: np.ndarray) -> np.ndarray:
    weights = np.array([1.0, 4.0, 6.0, 4.0, 1.0])
    rows, cols = luma.shape
    padded = np.pad(np.asarray(luma, dtype=np.float64), 2, mode="edge")
    out = np.zeros((rows, cols))
    for y in range(5):
        for x in range(5):
            out += weights[x] * weights[y] * padded[y:y + rows, x:x + cols]
    return out / 256.0


def edge_strength_reference(luma: np.ndarray, low: float, high: float) -> np.ndarray:
    """CPU mirror of the blur and edges stages on a luma image (rows top to bottom, as the field)."""
    return edge_ridge_reference(_blur_reference(_blur_reference(luma)), low, high)


def edge_ridge_reference(blurred: np.ndarray, low: float, high: float) -> np.ndarray:
    """CPU mirror of the edges stage's strengths, on an already blurred luma image."""
    return edge_seed_reference(blurred, low, high)[0]


def edge_seed_reference(blurred: np.ndarray, low: float, high: float) -> tuple[np.ndarray, np.ndarray]:
    """CPU mirror of the edges stage on an already blurred luma image: the strengths, and the seeds'
    sub-texel positions as an (N, 2) array of (row, column)."""
    blurred = np.asarray(blurred, dtype=np.float64)
    rows, cols = blurred.shape
    padded = np.pad(blurred, 1, mode="edge")
    a, b, c = padded[:-2, :-2], padded[:-2, 1:-1], padded[:-2, 2:]
    d, f = padded[1:-1, :-2], padded[1:-1, 2:]
    g, h, i = padded[2:, :-2], padded[2:, 1:-1], padded[2:, 2:]
    gx = (c + 2 * f + i - a - 2 * d - g) * _SOBEL_SCALE
    gy = (g + 2 * h + i - a - 2 * b - c) * _SOBEL_SCALE
    magnitude = np.hypot(gx, gy)
    safe = np.where(magnitude > 0, magnitude, 1.0)
    ox = np.floor(gx / safe + 0.5).astype(int)
    oy = np.floor(gy / safe + 0.5).astype(int)
    ys, xs = np.mgrid[0:rows, 0:cols]
    ahead = magnitude[np.clip(ys + oy, 0, rows - 1), np.clip(xs + ox, 0, cols - 1)]
    behind = magnitude[np.clip(ys - oy, 0, rows - 1), np.clip(xs - ox, 0, cols - 1)]
    ridge = np.where((magnitude > 0) & ((magnitude < ahead) | (magnitude <= behind)), 0.0, magnitude)
    t = np.clip((ridge - low) / (high - low), 0.0, 1.0)
    strength = t * t * (3.0 - 2.0 * t)
    curve = behind - 2.0 * magnitude + ahead
    shift = np.where(curve < -1e-6, np.clip(0.5 * (behind - ahead) / np.where(curve < -1e-6, curve, -1.0),
                                            -0.49, 0.49), 0.0)
    seeded = strength >= EDGE_FIELD_SEED
    points = np.stack(((ys + shift * oy)[seeded], (xs + shift * ox)[seeded]), axis=1)
    return strength, points


def edge_field_reference(luma: np.ndarray, low: float, high: float) -> tuple[np.ndarray, np.ndarray]:
    """Exact distance (picture heights) to the nearest seed and its strength, by brute force
    (small images only): the field jump flooding approximates."""
    return edge_distance_reference(*edge_seed_reference(_blur_reference(_blur_reference(luma)), low, high))


def edge_distance_reference(strength: np.ndarray, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Brute-force distance (picture heights) from every texel to the nearest sub-texel seed, and
    that seed's strength."""
    rows, cols = strength.shape
    if not len(points):
        return np.full(strength.shape, EDGE_FIELD_NONE), np.zeros(strength.shape)
    ys, xs = np.mgrid[0:rows, 0:cols]
    d2 = (ys[..., None] - points[:, 0]) ** 2 + (xs[..., None] - points[:, 1]) ** 2
    nearest = d2.argmin(axis=-1)
    texels = np.floor(points + 0.5).astype(int)
    return np.sqrt(d2.min(axis=-1)) / rows, strength[texels[nearest, 0], texels[nearest, 1]]


class EdgeField:
    """One photograph's edge field, rebuilt when the run, photograph or thresholds change."""

    _ROLES = (("luma", gl.GL_R16F, False), ("blur", gl.GL_R16F, False), ("edge", gl.GL_R16F, False),
              ("ping", gl.GL_RG32F, False), ("pong", gl.GL_RG32F, False), ("field", gl.GL_RG16F, True))

    def __init__(self, label: str) -> None:
        self.label = label
        self._textures: dict[str, int] = {}
        self._size: tuple[int, int] | None = None
        self._key: tuple | None = None
        self.builds = 0     # fields built (once per run; for tests and traces)

    @property
    def has_resources(self) -> bool:
        return bool(self._textures)

    def warm(self, pixel_size: tuple[int, int]) -> bool:
        """Allocate for a render of ``pixel_size`` if not yet; True if it already was."""
        size = edge_field_size(pixel_size)
        if self._size == size and len(self._textures) == len(self._ROLES):
            return True
        self.release()
        try:
            for role, internal, linear in self._ROLES:
                self._allocate(size, internal, linear, role)
        except Exception:
            self.release()
            raise
        self._size = size
        return False

    def texture(self, resources, photo: int, pixel_size: tuple[int, int], key: tuple, low: float,
                high: float) -> int:
        """The field of ``photo`` (sampler-readable, linear), built on the first call for ``key``."""
        self.warm(pixel_size)
        full_key = (key, float(low), float(high))
        if self._key == full_key:
            return self._textures["field"]
        self._key = None
        self._build(resources, photo, low, high)
        self._key = full_key
        self.builds += 1
        return self._textures["field"]

    def _build(self, resources, photo: int, low: float, high: float) -> None:
        width, height = self._size
        groups = (-(-width // _GROUP), -(-height // _GROUP), 1)
        t = self._textures
        image_barrier = gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT

        def use(key: str, source: str, names: tuple[str, ...]) -> dict[str, int]:
            gl.glUseProgram(resources.compute_program(key, source))
            uniforms = resources.uniforms(key, ("uSize", *names))
            gl.glUniform2i(uniforms["uSize"], width, height)
            return uniforms

        uniforms = use("edge_field_luma", _LUMA_COMPUTE, ("uPhoto", "uStep"))
        gl.glUniform1i(uniforms["uPhoto"], 0)
        gl.glUniform2f(uniforms["uStep"], 0.25 / width, 0.25 / height)
        gl.glBindTextureUnit(0, photo)
        with bound_image(0, t["luma"], gl.GL_WRITE_ONLY, gl.GL_R16F):
            dispatch(groups, image_barrier)

        use("edge_field_blur", _BLUR_COMPUTE, ())
        for read, write in (("luma", "blur"), ("blur", "luma")):
            with bound_image(0, t[read], gl.GL_READ_ONLY, gl.GL_R16F), \
                    bound_image(1, t[write], gl.GL_WRITE_ONLY, gl.GL_R16F):
                dispatch(groups, image_barrier)

        uniforms = use("edge_field_edges", _EDGES_COMPUTE, ("uLow", "uHigh"))
        gl.glUniform1f(uniforms["uLow"], low)
        gl.glUniform1f(uniforms["uHigh"], high)
        with bound_image(0, t["luma"], gl.GL_READ_ONLY, gl.GL_R16F), \
                bound_image(1, t["edge"], gl.GL_WRITE_ONLY, gl.GL_R16F), \
                bound_image(2, t["ping"], gl.GL_WRITE_ONLY, gl.GL_RG32F):
            dispatch(groups, image_barrier)

        uniforms = use("edge_field_flood", _FLOOD_COMPUTE, ("uJump",))
        source, target = t["ping"], t["pong"]
        for jump in edge_field_jumps(self._size):
            gl.glUniform1i(uniforms["uJump"], jump)
            with bound_image(0, source, gl.GL_READ_ONLY, gl.GL_RG32F), \
                    bound_image(1, target, gl.GL_WRITE_ONLY, gl.GL_RG32F):
                dispatch(groups, image_barrier)
            source, target = target, source

        use("edge_field_resolve", _RESOLVE_COMPUTE, ())
        with bound_image(0, source, gl.GL_READ_ONLY, gl.GL_RG32F), \
                bound_image(1, t["edge"], gl.GL_READ_ONLY, gl.GL_R16F), \
                bound_image(2, t["field"], gl.GL_WRITE_ONLY, gl.GL_RG16F):
            dispatch(groups, gl.GL_TEXTURE_FETCH_BARRIER_BIT)

    def _allocate(self, size: tuple[int, int], internal: int, linear: bool, role: str) -> None:
        name = (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        texture = int(name[0])
        if not texture:
            raise RuntimeError(f"{self.label} edge field {role} texture allocation failed")
        self._textures[role] = texture      # registered before storage can fail, so release() owns it
        mode = gl.GL_LINEAR if linear else gl.GL_NEAREST
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTextureParameteri(texture, parameter, mode)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
        gl.glTextureStorage2D(texture, 1, internal, *size)

    def release(self) -> None:
        errors: list[str] = []
        kept: dict[str, int] = {}
        for role, texture in self._textures.items():
            try:
                gl.glDeleteTextures([texture])
            except Exception as exc:
                errors.append(str(exc))
                kept[role] = texture
        self._textures = kept
        self._size = None
        self._key = None
        if errors:
            raise RuntimeError(f"{self.label} edge field cleanup incomplete: {' | '.join(errors)}")

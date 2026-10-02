"""Motion blur for the scene target: each moving surface blurs along its own screen motion.

While a scene renders into a motion-blur target, the passes that move write into
its second attachment how far each pixel's surface moved on screen over the
shutter (``SCENE3D_SHUTTER_SECONDS`` of real time), evaluated analytically at
t and t - shutter (``sceneVelocity``). Everything else leaves it cleared to zero.

The reconstruction follows McGuire et al., "A Reconstruction Filter for Plausible
Motion Blur" (2012), without a depth buffer: moving surfaces are taken to be in
front of still ones, which holds for pieces flying off a photograph. The passes:
the longest motion in each K x K tile (one compute dispatch writing a tile-sized
image: one workgroup per tile, one invocation per tile row, so the work spreads
without a K x K loop per invocation), then a bounded gather along the longest
motion in the pixel's 3 x 3 tile neighbourhood. A moving surface smears
over what is behind it and turns translucent within its own blur. Where nothing
in the neighbourhood moves the gather returns the pixel unchanged, so a still
frame, the run's endpoints and every static region are exact (nine tile fetches, one scene fetch).

The blur never exceeds two tiles (K is 1/40 of the target's height), which the
neighbourhood covers. Textures are sized from the target's allocation bucket and
dropped with it; no allocation per frame.
"""
from __future__ import annotations

import ctypes

from OpenGL import GL as gl

from .compute import bound_image, dispatch
from .post import FULLSCREEN_VERTEX_SOURCE

MOTION_BLUR_TAPS = 16
# Rows one tile-max workgroup can hold: K <= 256 covers targets up to ~10,000 px high.
MOTION_BLUR_MAX_TILE = 256
_TILE_ROW_INVOCATIONS = 64

# The longest motion in each K x K tile, one workgroup per tile: each invocation takes a row
# and finds its longest motion left to right, then the first invocation takes the longest of
# those rows top to bottom. The first strictly longer motion wins at both steps, so ties
# resolve exactly as a column-then-row scan. Every value is a velocity texel (RG16F), stored
# back unchanged.
_TILE_MAX_COMPUTE = f"""#version 460 core
layout(local_size_x = {_TILE_ROW_INVOCATIONS}) in;
layout(binding = 0) uniform sampler2D uVelocity;
layout(rg16f, binding = 0) writeonly uniform image2D uTiles;
uniform int uTile;
shared vec2 rowLongest[{MOTION_BLUR_MAX_TILE}];
void main() {{
    ivec2 size = textureSize(uVelocity, 0);
    ivec2 tile = ivec2(gl_WorkGroupID.xy);
    ivec2 origin = tile * uTile;
    int rows = min(uTile, size.y - origin.y);
    for (int row = int(gl_LocalInvocationIndex); row < rows; row += {_TILE_ROW_INVOCATIONS}) {{
        vec2 longest = vec2(0.0);
        float longestSquared = 0.0;
        for (int i = 0; i < uTile; ++i) {{
            ivec2 texel = origin + ivec2(i, row);
            if (texel.x >= size.x) break;
            vec2 motion = texelFetch(uVelocity, texel, 0).xy;
            float squared = dot(motion, motion);
            if (squared > longestSquared) {{
                longestSquared = squared;
                longest = motion;
            }}
        }}
        rowLongest[row] = longest;
    }}
    barrier();
    if (gl_LocalInvocationIndex != 0u) return;
    vec2 longest = vec2(0.0);
    float longestSquared = 0.0;
    for (int row = 0; row < rows; ++row) {{
        vec2 motion = rowLongest[row];
        float squared = dot(motion, motion);
        if (squared > longestSquared) {{
            longestSquared = squared;
            longest = motion;
        }}
    }}
    imageStore(uTiles, tile, vec4(longest, 0.0, 1.0));
}}
"""

_GATHER_FRAGMENT = f"""#version 460 core
out vec4 FragColor;
uniform sampler2D uScene;
uniform sampler2D uVelocity;
uniform sampler2D uTiles;
uniform int uTile;
uniform ivec2 uSize;
uniform float uLongest;   // the longest blur, in pixels
const int TAPS = {MOTION_BLUR_TAPS};

vec2 bounded(vec2 motion) {{
    float length2 = dot(motion, motion);
    return length2 > uLongest * uLongest ? motion * (uLongest * inversesqrt(length2)) : motion;
}}
float halfSpan(vec2 motion) {{
    return max(0.5 * length(bounded(motion)), 0.5);
}}
float cone(float distance, float span) {{
    return clamp(1.0 - distance / span, 0.0, 1.0);
}}
float cylinder(float distance, float span) {{
    return 1.0 - smoothstep(0.95 * span, 1.05 * span, distance);
}}
uint mixBits(uint value) {{
    value ^= value >> 16; value *= 0x7feb352du;
    value ^= value >> 15; value *= 0x846ca68bu;
    value ^= value >> 16;
    return value;
}}

void main() {{
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    vec4 centre = texelFetch(uScene, pixel, 0);
    // The longest motion in this pixel's 3 x 3 tile neighbourhood, rows then columns, first longest wins.
    ivec2 tileCount = textureSize(uTiles, 0);
    ivec2 home = pixel / uTile;
    vec2 longest = vec2(0.0);
    float longestSquared = 0.0;
    for (int y = -1; y <= 1; ++y) {{
        for (int x = -1; x <= 1; ++x) {{
            vec2 motion = texelFetch(uTiles, clamp(home + ivec2(x, y), ivec2(0), tileCount - 1), 0).xy;
            float squared = dot(motion, motion);
            if (squared > longestSquared) {{
                longestSquared = squared;
                longest = motion;
            }}
        }}
    }}
    vec2 dominant = bounded(longest);
    if (dot(dominant, dominant) < 0.25) {{
        FragColor = centre;   // nothing nearby moves: exact
        return;
    }}
    float centreSpan = halfSpan(texelFetch(uVelocity, pixel, 0).xy);
    float total = 1.0 / centreSpan;
    vec4 sum = centre * total;
    // Integer-hash jitter (R-94) of a quarter tap either way: enough to break up banding,
    // too little to leave the sandy speckle a full tap of jitter left along blur edges.
    float jitter = (float(mixBits(uint(pixel.x) * 1973u + uint(pixel.y) * 9277u) & 0xffffu) / 65535.0 - 0.5) * 0.5;
    for (int i = 0; i < TAPS; ++i) {{
        float along = mix(-1.0, 1.0, (float(i) + 0.5 + jitter) / float(TAPS));
        vec2 offset = dominant * 0.5 * along;
        ivec2 tap = clamp(ivec2(floor(vec2(pixel) + 0.5 + offset)), ivec2(0), uSize - 1);
        float distance = length(offset);
        float tapSpan = halfSpan(texelFetch(uVelocity, tap, 0).xy);
        // The tap smears over this pixel if its blur reaches it; this pixel shows what is
        // behind it within its own blur; two surfaces blurring together blend.
        float weight = cone(distance, tapSpan) + cone(distance, centreSpan)
                     + 2.0 * cylinder(distance, tapSpan) * cylinder(distance, centreSpan);
        sum += texelFetch(uScene, tap, 0) * weight;
        total += weight;
    }}
    FragColor = sum / total;
}}
"""


def motion_blur_tile(height: int) -> int:
    """Tile edge K in pixels: 1/40 of the height (36 at 1440p), never under 8; the longest blur is 2K."""
    tile = max(8, round(int(height) / 40))
    if tile > MOTION_BLUR_MAX_TILE:
        raise ValueError(f"motion blur tile {tile} exceeds the {MOTION_BLUR_MAX_TILE}-row tile-max capacity")
    return tile


class MotionBlur:
    def __init__(self, label: str) -> None:
        self.label = label
        self._key: tuple[int, int] | None = None
        # (texture, fbo, width, height): the tile max (a compute-written image, no framebuffer), blurred scene.
        self._passes: list[tuple[int, int, int, int]] = []

    @property
    def has_resources(self) -> bool:
        return bool(self._passes)

    def apply(self, scene_texture: int, velocity_texture: int, allocation: tuple[int, int], resources,
              vao: int) -> int:
        """Blur ``scene_texture`` along ``velocity_texture``; returns the blurred scene.

        Both cover the whole allocation (outside the drawn rect: black, no motion);
        so does the result. The caller has turned depth testing and writes off, and
        the host fence restores texture units 0-2 and the program, so none of that is
        repeated here (every GL call costs the render thread ~2 us). Image unit 0 is
        handed back by ``bound_image``.
        """
        self.warm(allocation)
        width, height = allocation
        tile = motion_blur_tile(height)
        (tiles, _tiles_fbo, tile_w, tile_h), (blurred, blurred_fbo, _bw, _bh) = self._passes

        # The gather samples the tile image, so the dispatch owns a texture-fetch barrier.
        gl.glUseProgram(resources.compute_program("motion_tile_max", _TILE_MAX_COMPUTE))
        gl.glUniform1i(resources.uniforms("motion_tile_max", ("uTile",))["uTile"], tile)
        gl.glBindTextureUnit(0, velocity_texture)
        with bound_image(0, tiles, gl.GL_WRITE_ONLY, gl.GL_RG16F):
            dispatch((tile_w, tile_h, 1), gl.GL_TEXTURE_FETCH_BARRIER_BIT)

        gl.glBindVertexArray(vao)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        program = resources.program("motion_gather", FULLSCREEN_VERTEX_SOURCE, _GATHER_FRAGMENT)
        uniforms = resources.uniforms("motion_gather", ("uScene", "uVelocity", "uTiles", "uTile", "uSize",
                                                        "uLongest"))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, blurred_fbo)
        gl.glViewport(0, 0, width, height)
        gl.glUseProgram(program)
        gl.glBindTexture(gl.GL_TEXTURE_2D, scene_texture)
        gl.glUniform1i(uniforms["uScene"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, velocity_texture)
        gl.glUniform1i(uniforms["uVelocity"], 1)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tiles)
        gl.glUniform1i(uniforms["uTiles"], 2)
        gl.glUniform1i(uniforms["uTile"], tile)
        gl.glUniform2i(uniforms["uSize"], width, height)
        gl.glUniform1f(uniforms["uLongest"], 2.0 * tile)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        return blurred

    def warm(self, allocation: tuple[int, int]) -> bool:
        """Allocate for ``allocation`` if not yet (ahead of a run, or at first use); True if it was."""
        if self._key == allocation:
            return True
        self.release()
        self._allocate(*allocation)
        self._key = allocation
        return False

    def _allocate_texture(self, width: int, height: int, internal: int) -> int:
        """Register a pass texture before its named immutable allocation can fail."""
        texture_name = (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, texture_name)
        texture = int(texture_name[0])
        if not texture:
            raise RuntimeError(f"{self.label} motion blur texture allocation failed")
        self._passes.append((texture, 0, width, height))
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTextureParameteri(texture, parameter, gl.GL_NEAREST)
        gl.glTextureStorage2D(texture, 1, internal, width, height)
        return texture

    def _allocate(self, width: int, height: int) -> None:
        tile = motion_blur_tile(height)
        tile_w, tile_h = -(-width // tile), -(-height // tile)
        # The tile max is a compute-written image; only the blurred scene is drawn.
        self._allocate_texture(tile_w, tile_h, gl.GL_RG16F)
        texture = self._allocate_texture(width, height, gl.GL_RGBA8)
        framebuffer_name = (ctypes.c_uint * 1)()
        gl.glCreateFramebuffers(1, framebuffer_name)
        fbo = int(framebuffer_name[0])
        if not fbo:
            raise RuntimeError(f"{self.label} motion blur framebuffer allocation failed")
        self._passes[-1] = (texture, fbo, width, height)
        gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0, texture, 0)
        if gl.glCheckNamedFramebufferStatus(fbo, gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"{self.label} motion blur pass incomplete at {width}x{height}")

    def release(self) -> None:
        errors: list[str] = []
        kept: list[tuple[int, int, int, int]] = []
        for texture, fbo, width, height in self._passes:
            try:
                if fbo:
                    gl.glDeleteFramebuffers(1, [fbo])
                    fbo = 0
                if texture:
                    gl.glDeleteTextures([texture])
                    texture = 0
            except Exception as exc:
                errors.append(str(exc))
            if texture or fbo:
                kept.append((texture, fbo, width, height))
        self._passes = kept
        self._key = None
        if errors:
            raise RuntimeError(f"{self.label} motion blur cleanup incomplete: {' | '.join(errors)}")


def motion_uniform_names(time_uniform: str = "uProgress") -> tuple[str, str]:
    """The uniforms a ``scene3d_motion_vertex`` / ``scene3d_motion_fragment`` variant adds."""
    return f"{time_uniform}Before", "uViewport"


def motion_program(resources, key: str, sources: tuple[str, str], motion_sources: tuple[str, str],
                   names: tuple[str, ...], motion: bool, time_uniform: str = "uProgress") -> tuple[int, dict[str, int]]:
    """An effect's program and uniforms: its own, or (with motion blur) the variant that writes motion.

    Without motion blur the effect draws with exactly its own program, so its pixels
    cannot change.
    """
    if motion:
        key = key + "_motion"
        return resources.program(key, *motion_sources), resources.uniforms(key, names + motion_uniform_names(time_uniform))
    return resources.program(key, *sources), resources.uniforms(key, names)


def set_motion_uniforms(uniforms: dict[str, int], frame, before: float, time_uniform: str = "uProgress") -> None:
    """The time input one shutter ago, and the viewport the motion is measured in."""
    gl.glUniform1f(uniforms[f"{time_uniform}Before"], float(before))
    gl.glUniform2f(uniforms["uViewport"], float(frame.viewport[2]), float(frame.viewport[3]))

# (key, vertex, fragment) or (key, compute) of the programs ``MotionBlur.apply`` uses (for a gradual warm-up).
MOTION_BLUR_PROGRAMS = (
    ("motion_tile_max", _TILE_MAX_COMPUTE),
    ("motion_gather", FULLSCREEN_VERTEX_SOURCE, _GATHER_FRAGMENT),
)

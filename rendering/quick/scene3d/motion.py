"""Motion blur for the scene target: each moving surface blurs along its own screen motion.

While a scene renders into a motion-blur target, the passes that move write into
its second attachment how far each pixel's surface moved on screen over the
shutter (``SCENE3D_SHUTTER_SECONDS`` of real time), evaluated analytically at
t and t - shutter (``sceneVelocity``). Everything else leaves it cleared to zero.

The reconstruction follows McGuire et al., "A Reconstruction Filter for Plausible
Motion Blur" (2012), without a depth buffer: moving surfaces are taken to be in
front of still ones, which holds for pieces flying off a photograph. The passes:
the longest motion in each K x K tile (separably: across K columns, then down K
rows, so the work spreads over many fragments), the longest in each tile's 3 x 3
neighbourhood, then a bounded gather along that motion. A moving surface smears
over what is behind it and turns translucent within its own blur. Where nothing
in the neighbourhood moves the gather returns the pixel unchanged, so a still
frame, the run's endpoints and every static region are exact and cost one fetch.

The blur never exceeds two tiles (K is 1/40 of the target's height), which the
neighbourhood covers. Textures are sized from the target's allocation bucket and
dropped with it; no allocation per frame.
"""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.quick import gl_query

from .post import FULLSCREEN_VERTEX_SOURCE

MOTION_BLUR_TAPS = 16

# The longest motion along K texels of one axis: uStep (1, 0) across a tile's columns,
# (0, 1) down its rows. Separable, so the tile max is 2K fetches per texel, not K^2 in one.
_TILE_MAX_FRAGMENT = """#version 410 core
out vec4 FragColor;
uniform sampler2D uVelocity;
uniform int uTile;
uniform ivec2 uStep;
uniform ivec2 uSize;   // uVelocity's size
void main() {
    ivec2 origin = ivec2(gl_FragCoord.xy) * (ivec2(1) + uStep * (uTile - 1));
    vec2 longest = vec2(0.0);
    float longestSquared = 0.0;
    for (int i = 0; i < uTile; ++i) {
        ivec2 texel = origin + uStep * i;
        if (texel.x >= uSize.x || texel.y >= uSize.y) break;
        vec2 motion = texelFetch(uVelocity, texel, 0).xy;
        float squared = dot(motion, motion);
        if (squared > longestSquared) {
            longestSquared = squared;
            longest = motion;
        }
    }
    FragColor = vec4(longest, 0.0, 1.0);
}
"""

_NEIGHBOUR_MAX_FRAGMENT = """#version 410 core
out vec4 FragColor;
uniform sampler2D uTiles;
uniform ivec2 uTileCount;
void main() {
    ivec2 centre = ivec2(gl_FragCoord.xy);
    vec2 longest = vec2(0.0);
    float longestSquared = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            ivec2 tile = clamp(centre + ivec2(x, y), ivec2(0), uTileCount - 1);
            vec2 motion = texelFetch(uTiles, tile, 0).xy;
            float squared = dot(motion, motion);
            if (squared > longestSquared) {
                longestSquared = squared;
                longest = motion;
            }
        }
    }
    FragColor = vec4(longest, 0.0, 1.0);
}
"""

_GATHER_FRAGMENT = f"""#version 410 core
out vec4 FragColor;
uniform sampler2D uScene;
uniform sampler2D uVelocity;
uniform sampler2D uNeighbours;
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
    vec2 dominant = bounded(texelFetch(uNeighbours, pixel / uTile, 0).xy);
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
    return max(8, round(int(height) / 40))


def _texture(width: int, height: int, internal: int, data_type: int) -> int:
    texture = int(gl.glGenTextures(1))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
        gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_NEAREST)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal, width, height, 0, gl.GL_RGBA, data_type, None)
    return texture


class MotionBlur:
    def __init__(self, label: str) -> None:
        self.label = label
        self._key: tuple[int, int] | None = None
        # (texture, fbo, width, height): column max, tile max, neighbour max, blurred scene.
        self._passes: list[tuple[int, int, int, int]] = []

    @property
    def has_resources(self) -> bool:
        return bool(self._passes)

    def apply(self, scene_texture: int, velocity_texture: int, allocation: tuple[int, int], resources,
              vao: int) -> int:
        """Blur ``scene_texture`` along ``velocity_texture``; returns the blurred scene.

        Both cover the whole allocation (outside the drawn rect: black, no motion);
        so does the result. The caller has turned depth testing and writes off, and
        the host fence restores texture bindings, so none of that is repeated here
        (every GL call costs the render thread ~2 us).
        """
        self.warm(allocation)
        width, height = allocation
        tile = motion_blur_tile(height)
        ((columns, columns_fbo, tile_w, _h), (tiles, tiles_fbo, _w, tile_h), (neighbours, neighbours_fbo, _nw, _nh),
         (blurred, blurred_fbo, _bw, _bh)) = self._passes
        gl.glBindVertexArray(vao)
        gl.glActiveTexture(gl.GL_TEXTURE0)

        program = resources.program("motion_tile_max", FULLSCREEN_VERTEX_SOURCE, _TILE_MAX_FRAGMENT)
        uniforms = resources.uniforms("motion_tile_max", ("uVelocity", "uTile", "uStep", "uSize"))
        gl.glUseProgram(program)
        gl.glUniform1i(uniforms["uVelocity"], 0)
        gl.glUniform1i(uniforms["uTile"], tile)
        for fbo, size, step, source, source_size in ((columns_fbo, (tile_w, height), (1, 0), velocity_texture,
                                                      (width, height)),
                                                     (tiles_fbo, (tile_w, tile_h), (0, 1), columns,
                                                      (tile_w, height))):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glViewport(0, 0, *size)
            gl.glBindTexture(gl.GL_TEXTURE_2D, source)
            gl.glUniform2i(uniforms["uStep"], *step)
            gl.glUniform2i(uniforms["uSize"], *source_size)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

        program = resources.program("motion_neighbour_max", FULLSCREEN_VERTEX_SOURCE, _NEIGHBOUR_MAX_FRAGMENT)
        uniforms = resources.uniforms("motion_neighbour_max", ("uTiles", "uTileCount"))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, neighbours_fbo)
        gl.glViewport(0, 0, tile_w, tile_h)
        gl.glUseProgram(program)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tiles)
        gl.glUniform1i(uniforms["uTiles"], 0)
        gl.glUniform2i(uniforms["uTileCount"], tile_w, tile_h)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

        program = resources.program("motion_gather", FULLSCREEN_VERTEX_SOURCE, _GATHER_FRAGMENT)
        uniforms = resources.uniforms("motion_gather", ("uScene", "uVelocity", "uNeighbours", "uTile", "uSize",
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
        gl.glBindTexture(gl.GL_TEXTURE_2D, neighbours)
        gl.glUniform1i(uniforms["uNeighbours"], 2)
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

    def _allocate(self, width: int, height: int) -> None:
        previous = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        tile = motion_blur_tile(height)
        tile_w, tile_h = -(-width // tile), -(-height // tile)
        try:
            for w, h, internal, data_type in ((tile_w, height, gl.GL_RG16F, gl.GL_HALF_FLOAT),
                                              (tile_w, tile_h, gl.GL_RG16F, gl.GL_HALF_FLOAT),
                                              (tile_w, tile_h, gl.GL_RG16F, gl.GL_HALF_FLOAT),
                                              (width, height, gl.GL_RGBA8, gl.GL_UNSIGNED_BYTE)):
                texture = _texture(w, h, internal, data_type)
                self._passes.append((texture, 0, w, h))
                fbo = int(gl.glGenFramebuffers(1))
                self._passes[-1] = (texture, fbo, w, h)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
                gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
                if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError(f"{self.label} motion blur pass incomplete at {w}x{h}")
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, previous)

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

# (key, vertex, fragment) of the programs ``MotionBlur.apply`` draws with (for a gradual warm-up).
MOTION_BLUR_PROGRAMS = (
    ("motion_tile_max", FULLSCREEN_VERTEX_SOURCE, _TILE_MAX_FRAGMENT),
    ("motion_neighbour_max", FULLSCREEN_VERTEX_SOURCE, _NEIGHBOUR_MAX_FRAGMENT),
    ("motion_gather", FULLSCREEN_VERTEX_SOURCE, _GATHER_FRAGMENT),
)

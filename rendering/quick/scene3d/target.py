"""The multisampled scene target: smooth 3D edges for any pixel rect of Quick's target.

``begin`` redirects drawing into a colour+depth multisampled framebuffer that
covers ``rect`` (by default the item's pixel bounds) and offsets the viewport,
so the frame's own matrix draws exactly as it would directly. ``end`` resolves
and composites it back through the item quad; Quick's scissor, stencil (the
Visualizer card clip) and item bounds then apply as for a direct draw.

The colour attachment is a texture the composite reads directly, averaging the
samples itself: there is no resolve blit. (A ``glBlitFramebuffer`` resolve of
drawn content measured ~0.5 ms at 2560x1440 on an RTX 4090, 1 or 4 samples
alike; the shader average costs a few hundredths of that.) Bloom and motion blur
need one resolved image, so with either a resolve pass writes it first.

With motion blur the target has a second attachment, the screen motion of each
pixel's surface over the shutter (see ``motion.MotionBlur``). It is write-protected
while the scene draws; a pass that moves opens it with ``velocity_writes()``.

An **overlay** scope (``overlay=`` an opacity) is for a scene drawn over what Quick has
already drawn (a Visualizer over its card): the target clears to transparent and the
composite hands the resolved scene back as straight alpha, times the opacity, to the
caller's blend state (the Visualizer host blends straight alpha). Where nothing was drawn
the composite discards, so the card shows through untouched. Motion blur is a transition
facility and is refused in an overlay.

An overlay's alpha is coverage, so its **bloom** cannot read emitted light from alpha as an
opaque scene's does: with ``bloom`` an overlay target has a second attachment (location 1,
RGBA16F) for the light each pixel emits, written only inside ``emission_writes()`` (the
passes write ``sceneEmission(light)``, ``SCENE_EMISSION_GLSL``). The emission is blurred by the
shared bloom chain, and the composite lays the scene over what is drawn with its glow added:
premultiplied, under a blend this target sets and restores for that one draw, so the glow
brightens the backdrop exactly and never darkens it. Without emission writes nothing glows.

``scope`` restores Quick's framebuffers, viewport and scissor even when the
scene raises, so a consumer needs no fence change of its own (the Visualizer
fence stays as it is: modes that do not use a target pay nothing).

Allocation rounds up to 64 px and is reused while the rect fits, so a CUSTOM
resize drag does not reallocate per frame. The owner releases the target: a
transition at the host's ``park()`` after each run, a Visualizer mode when it
retires. Failed deletions keep their handles for retry.

``warm`` allocates the same textures ahead of a run, one unit per call (S10): the
target, its resolve copies, the motion-blur chain, the bloom chain. At 3840x2160 each
unit costs 1-3.5 ms of CPU; allocated at the run's first frame together they cost the
render thread 10-29 ms. Nothing is held between runs that ``park()`` does not already
release: the next transition's warm-up allocates again.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from typing import Iterator

from OpenGL import GL as gl

from rendering.quick import gl_query

from .frame import ITEM_QUAD_VERTEX_SOURCE, SceneFrame, item_pixel_rect
from .motion import MOTION_BLUR_PROGRAMS, MotionBlur
from .post import BLOOM_PROGRAMS, FULLSCREEN_VERTEX_SOURCE, BloomChain

SCENE_TARGET_BUCKET = 64

# The average of a multisampled texel's samples (what a resolve blit computes).
_RESOLVE_GLSL = """
uniform sampler2DMS uSceneSamples;
uniform int uSamples;
vec4 sceneResolved(ivec2 texel) {
    vec4 sum = vec4(0.0);
    for (int i = 0; i < uSamples; ++i) sum += texelFetch(uSceneSamples, texel, i);
    return sum / float(uSamples);
}
"""

_COMPOSITE_HEADER = """#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform ivec2 uOrigin;
uniform ivec2 uExtent;
"""

# From a single-sample (or resolved) scene, with the glow added.
_COMPOSITE_FRAGMENT = _COMPOSITE_HEADER + """
uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform vec2 uBloomScale;      // 1 / allocation size: the glow covers the allocation at half size
uniform float uBloomStrength;  // 0 without bloom
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    vec3 colour = texelFetch(uScene, texel, 0).rgb;
    if (uBloomStrength > 0.0) colour += texture(uBloom, (vec2(texel) + 0.5) * uBloomScale).rgb * uBloomStrength;
    // The target's alpha may carry emissive light for the bloom; Quick gets opaque pixels.
    FragColor = vec4(colour, 1.0);
}
"""

# Straight from the multisampled scene: resolve and composite in one pass.
_COMPOSITE_SAMPLES_FRAGMENT = _COMPOSITE_HEADER + _RESOLVE_GLSL + """
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    FragColor = vec4(sceneResolved(texel).rgb, 1.0);
}
"""

# What an overlay pass writes to its emission output: the light, with its brightness in alpha
# (the bloom chain's bright pass scales colour to alpha's brightness).
SCENE_EMISSION_GLSL = """
vec4 sceneEmission(vec3 light) {
    return vec4(light, dot(light, vec3(0.2126, 0.7152, 0.0722)));
}
"""

# An overlay with bloom: the scene premultiplied, its glow added, for a premultiplied blend.
_OVERLAY_BLOOM_GLSL = """
uniform float uOpacity;
uniform sampler2D uBloom;
uniform vec2 uBloomScale;      // 1 / allocation size: the glow covers the allocation at half size
uniform float uBloomStrength;
vec4 sceneOverlayBloom(vec4 scene, ivec2 texel) {
    vec3 glow = texture(uBloom, (vec2(texel) + 0.5) * uBloomScale).rgb * uBloomStrength;
    if (scene.a <= 0.0 && max(glow.r, max(glow.g, glow.b)) < 1.0 / 512.0) discard;
    return vec4((scene.rgb + glow) * uOpacity, scene.a * uOpacity);
}
"""
_COMPOSITE_OVERLAY_BLOOM_FRAGMENT = _COMPOSITE_HEADER + "uniform sampler2D uScene;\n" + _OVERLAY_BLOOM_GLSL + """
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    FragColor = sceneOverlayBloom(texelFetch(uScene, texel, 0), texel);
}
"""
_COMPOSITE_OVERLAY_BLOOM_SAMPLES_FRAGMENT = _COMPOSITE_HEADER + _RESOLVE_GLSL + _OVERLAY_BLOOM_GLSL + """
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    FragColor = sceneOverlayBloom(sceneResolved(texel), texel);
}
"""

# An overlay: the resolved scene as straight alpha (its colour was blended over transparent
# black, so it is premultiplied), times the opacity; nothing drawn shows what lies below.
_OVERLAY_GLSL = """
uniform float uOpacity;
vec4 sceneOverlay(vec4 colour) {
    if (colour.a <= 0.0) discard;
    return vec4(colour.rgb / colour.a, colour.a * uOpacity);
}
"""
_COMPOSITE_OVERLAY_FRAGMENT = _COMPOSITE_HEADER + "uniform sampler2D uScene;\n" + _OVERLAY_GLSL + """
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    FragColor = sceneOverlay(texelFetch(uScene, texel, 0));
}
"""
_COMPOSITE_OVERLAY_SAMPLES_FRAGMENT = _COMPOSITE_HEADER + _RESOLVE_GLSL + _OVERLAY_GLSL + """
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    FragColor = sceneOverlay(sceneResolved(texel));
}
"""

# The whole allocation, resolved for the post effects (outside the rect it is cleared black).
_RESOLVE_FRAGMENT = "#version 460 core\nout vec4 FragColor;\n" + _RESOLVE_GLSL + """
void main() {
    FragColor = sceneResolved(ivec2(gl_FragCoord.xy));
}
"""

# The same, with the screen motion averaged into the second output.
_RESOLVE_MOTION_FRAGMENT = ("#version 460 core\nlayout(location = 0) out vec4 FragColor;\n"
                            "layout(location = 1) out vec4 Motion;\n" + _RESOLVE_GLSL + """
uniform sampler2DMS uMotionSamples;
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy);
    FragColor = sceneResolved(texel);
    vec2 sum = vec2(0.0);
    for (int i = 0; i < uSamples; ++i) sum += texelFetch(uMotionSamples, texel, i).xy;
    Motion = vec4(sum / float(uSamples), 0.0, 1.0);
}
""")


def scene_target_programs(samples: int, bloom: bool, motion: bool,
                          overlay: bool = False) -> tuple[tuple[str, str, str], ...]:
    """(key, vertex, fragment) of every program ``end`` draws with for this setup, for a gradual
    warm-up. Keep in step with ``end`` (the warm-up bar renders a first frame that must compile
    nothing)."""
    multisampled = int(samples) > 1
    if overlay:
        if motion:
            raise ValueError("an overlay scene target has no motion blur")
        if bloom:
            programs = [("scene_resolve", FULLSCREEN_VERTEX_SOURCE, _RESOLVE_FRAGMENT)] if multisampled else []
            programs.extend(BLOOM_PROGRAMS)
            programs.append(("scene_overlay_bloom_samples", ITEM_QUAD_VERTEX_SOURCE,
                             _COMPOSITE_OVERLAY_BLOOM_SAMPLES_FRAGMENT) if multisampled
                            else ("scene_overlay_bloom", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_OVERLAY_BLOOM_FRAGMENT))
            return tuple(programs)
        if multisampled:
            return (("scene_overlay_samples", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_OVERLAY_SAMPLES_FRAGMENT),)
        return (("scene_overlay", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_OVERLAY_FRAGMENT),)
    if not (bloom or motion):
        if multisampled:
            return (("scene_composite_samples", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_SAMPLES_FRAGMENT),)
        return (("scene_composite", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_FRAGMENT),)
    programs: list[tuple[str, str, str]] = []
    if multisampled:
        programs.append(("scene_resolve_motion", FULLSCREEN_VERTEX_SOURCE, _RESOLVE_MOTION_FRAGMENT) if motion
                        else ("scene_resolve", FULLSCREEN_VERTEX_SOURCE, _RESOLVE_FRAGMENT))
    if motion:
        programs.extend(MOTION_BLUR_PROGRAMS)
    if bloom:
        programs.extend(BLOOM_PROGRAMS)
    programs.append(("scene_composite", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_FRAGMENT))
    return tuple(programs)


def warm_run_resources(target: "SceneTarget", trails, size: tuple[int, int] | None, samples: int, *,
                       motion_blur: bool = False, bloom: bool = False, with_trails: bool = False,
                       overlay: bool = False) -> bool:
    """One step of allocating ahead what a run will allocate at its first frames, for a
    renderer whose scene draws through ``target`` at ``size`` device pixels (and ``trails``
    when on). True once nothing is left, or when the run draws without a target."""
    if size is None or not samples:
        return True
    if not target.warm(size, samples, motion_blur=motion_blur, bloom=bloom, overlay=overlay):
        return False
    return not with_trails or trails.warm(target)


def _blend_state() -> tuple:
    """The current blend enable, functions and equations (to hand back to the caller)."""
    return (gl_query.is_enabled(gl.GL_BLEND),
            *(gl_query.get_int(name) for name in (gl.GL_BLEND_SRC_RGB, gl.GL_BLEND_DST_RGB, gl.GL_BLEND_SRC_ALPHA,
                                                  gl.GL_BLEND_DST_ALPHA, gl.GL_BLEND_EQUATION_RGB,
                                                  gl.GL_BLEND_EQUATION_ALPHA)))


def _bucket(size: int) -> int:
    return max(SCENE_TARGET_BUCKET, -(-int(size) // SCENE_TARGET_BUCKET) * SCENE_TARGET_BUCKET)


def _new_texture(target: int, label: str) -> int:
    """Create one owned texture without changing a Quick texture-unit binding."""
    name = (ctypes.c_uint * 1)()
    gl.glCreateTextures(target, 1, name)
    texture = int(name[0])
    if not texture:
        raise RuntimeError(f"{label} texture allocation failed")
    return texture


def _new_framebuffer(label: str) -> int:
    """Create one owned framebuffer without replacing Quick's draw/read target."""
    name = (ctypes.c_uint * 1)()
    gl.glCreateFramebuffers(1, name)
    framebuffer = int(name[0])
    if not framebuffer:
        raise RuntimeError(f"{label} framebuffer allocation failed")
    return framebuffer


class SceneTarget:
    def __init__(self, label: str) -> None:
        self.label = label
        # allocated width, height, requested samples, with motion, with emission
        self._key: tuple[int, int, int, bool, bool] | None = None
        self._samples = 0                                # samples allocated (1 = a plain texture)
        # colour / velocity: the scene's attachments (multisampled when _samples > 1);
        # resolve_*: their resolved copies for the post effects.
        self._names = {"fbo": 0, "colour": 0, "velocity": 0, "depth": 0, "resolve_fbo": 0, "resolve_texture": 0,
                       "resolve_velocity": 0, "emission": 0, "emission_resolve_fbo": 0, "emission_resolve": 0}
        self._inherited = (0, 0)
        self._scissor = False
        self._rect = (0, 0, 0, 0)
        self._overlay: float | None = None
        # The caller's blend state, kept by an overlay with bloom (the bloom chain resets blending).
        self._inherited_blend: tuple | None = None
        self._bloom = BloomChain(label)
        self._motion = MotionBlur(label)

    @property
    def has_resources(self) -> bool:
        return any(self._names.values()) or self._bloom.has_resources or self._motion.has_resources

    @property
    def allocation(self) -> tuple[int, int, int] | None:
        """(width, height, samples) currently allocated, if any."""
        return None if self._key is None else (self._key[0], self._key[1], self._samples)

    @contextmanager
    def scope(self, frame: SceneFrame, samples: int, resources,
              rect: tuple[int, int, int, int] | None = None, bloom: float = 0.0,
              motion_blur: bool = False, overlay: float | None = None) -> Iterator[None]:
        """Draw the enclosed passes through the target; Quick's bindings come back either way.

        With ``bloom`` > 0 the emissive light the passes wrote into alpha glows
        (see ``post.BloomChain``); the passes must then write alpha deliberately.
        With ``motion_blur`` the passes that move write their screen motion inside
        ``velocity_writes()`` (see ``motion.MotionBlur``). With ``overlay`` (an opacity)
        the scene is laid over what is already drawn (see the module notes).
        """
        if overlay is not None and motion_blur:
            raise ValueError(f"{self.label}: an overlay scene target has no motion blur")
        self.begin(frame, samples, rect, motion_blur, overlay=overlay,
                   emission=overlay is not None and bloom > 0.0)
        try:
            yield
        except BaseException:
            self._restore_inherited(frame)
            self._restore_inherited_blend()
            raise
        self.end(frame, resources, bloom)

    @contextmanager
    def emission_writes(self) -> Iterator[None]:
        """Let the enclosed passes write emitted light (location 1); a no-op without overlay bloom."""
        if not self._names["emission"]:
            yield
            return
        gl.glColorMaski(1, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        try:
            yield
        finally:
            gl.glColorMaski(1, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE)

    @contextmanager
    def velocity_writes(self) -> Iterator[None]:
        """Let the enclosed passes write their screen motion (location 1); a no-op without motion blur."""
        if not self._names["velocity"]:
            yield
            return
        gl.glColorMaski(1, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        try:
            yield
        finally:
            gl.glColorMaski(1, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE)

    def warm(self, size: tuple[int, int], samples: int, *, motion_blur: bool = False,
             bloom: bool = False, overlay: bool = False) -> bool:
        """Allocate ahead, one unit per call, what ``scope`` will use at ``size`` (device
        pixels) with these settings; True once all of it is allocated. ``begin`` reuses it."""
        width, height = (int(value) for value in size)
        samples, motion_blur = max(1, int(samples)), bool(motion_blur)
        emission = bool(overlay and bloom)
        key = self._key
        if (key is None or key[2] != samples or key[3] != motion_blur or key[4] != emission
                or width > key[0] or height > key[1]):
            self.release()
            self._inherited = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING),
                               gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING))
            self._allocate(_bucket(width), _bucket(height), samples, motion_blur, emission)
            self._commit()
            return False
        allocation = (self._key[0], self._key[1])
        if emission:
            if self._samples > 1 and not self._names["emission_resolve"]:
                self._allocate_emission_resolve()
                return False
        elif self._samples > 1 and (motion_blur or bloom) and not self._names["resolve_texture"]:
            self._allocate_resolve()
            return False
        if motion_blur and not self._motion.warm(allocation):
            return False
        if bloom and not self._bloom.warm(allocation):
            return False
        return True

    def _commit(self) -> None:
        """Clear the new allocation once, so the driver commits its memory now and not at the
        run's first frame."""
        scissor = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        clear = gl_query.get_floats(gl.GL_COLOR_CLEAR_VALUE, 4)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["fbo"])
        gl.glDisable(gl.GL_SCISSOR_TEST)
        try:
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            gl.glClearDepth(1.0)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        finally:
            gl.glClearColor(*clear)
            if scissor:
                gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._inherited[0])
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._inherited[1])

    def begin(self, frame: SceneFrame, samples: int, rect: tuple[int, int, int, int] | None = None,
              motion_blur: bool = False, overlay: float | None = None, emission: bool = False) -> None:
        x, y, width, height = tuple(int(v) for v in (rect if rect is not None else item_pixel_rect(frame)))
        if width <= 0 or height <= 0:
            raise ValueError(f"{self.label} scene target needs a positive rect, got {(x, y, width, height)}")
        samples = max(1, int(samples))
        self._inherited = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING),
                           gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING))
        self._scissor = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        motion_blur, emission = bool(motion_blur), bool(emission)
        key = self._key
        if (key is None or key[2] != samples or key[3] != motion_blur or key[4] != emission
                or width > key[0] or height > key[1]):
            self.release()
            self._allocate(_bucket(width), _bucket(height), samples, motion_blur, emission)
        self._rect = (x, y, width, height)
        self._overlay = None if overlay is None else max(0.0, min(1.0, float(overlay)))
        self._inherited_blend = _blend_state() if emission else None
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["fbo"])
        gl.glDisable(gl.GL_SCISSOR_TEST)
        clear = gl_query.get_floats(gl.GL_COLOR_CLEAR_VALUE, 4)
        try:
            # The motion attachment clears to no motion; an overlay's colour to transparent.
            gl.glClearColor(0.0, 0.0, 0.0, 0.0 if self._overlay is not None else 1.0)
            gl.glClearDepth(1.0)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        finally:
            gl.glClearColor(*clear)
        if self._names["velocity"] or self._names["emission"]:
            # The second attachment is written only inside velocity_writes() / emission_writes().
            gl.glColorMaski(1, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE)
        vx, vy, vw, vh = frame.viewport
        gl.glViewport(vx - x, vy - y, vw, vh)

    def end(self, frame: SceneFrame, resources, bloom: float = 0.0) -> None:
        x, y, width, height = self._rect
        allocated_width, allocated_height = self._key[0], self._key[1]
        multisampled = self._samples > 1
        motion = bool(self._names["velocity"])
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        if motion:
            gl.glColorMaski(1, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        scene, glow = self._names["colour"], 0
        if (bloom > 0.0 and not self._names["emission"]) or motion:
            velocity = self._names["velocity"]
            if multisampled:
                scene, velocity = self._resolve(frame, resources)
            if motion:
                scene = self._motion.apply(scene, velocity, (allocated_width, allocated_height), resources,
                                           frame.quad_vao)
            if bloom > 0.0:
                glow = self._bloom.apply(scene, (allocated_width, allocated_height), resources, frame.quad_vao)
        if self._overlay is not None and self._names["emission"] and bloom > 0.0:
            try:
                emitted = self._resolve_emission(frame, resources) if multisampled else self._names["emission"]
                glow = self._bloom.apply(emitted, (allocated_width, allocated_height), resources, frame.quad_vao)
                self._restore_inherited(frame)
                self._composite_overlay_bloom(frame, resources, glow, bloom)
            finally:
                self._restore_inherited_blend()
            return
        self._restore_inherited(frame)
        if self._overlay is not None:
            key = "scene_overlay_samples" if multisampled else "scene_overlay"
            program = resources.program(key, ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_OVERLAY_SAMPLES_FRAGMENT
                                        if multisampled else _COMPOSITE_OVERLAY_FRAGMENT)
            names = ("uMatrix", "uItemSize", "uOrigin", "uExtent", "uOpacity")
            uniforms = resources.uniforms(key, names + (("uSceneSamples", "uSamples") if multisampled
                                                         else ("uScene",)))
            gl.glUseProgram(program)
            gl.glUniform1f(uniforms["uOpacity"], self._overlay)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            if multisampled:
                gl.glUniform1i(uniforms["uSamples"], self._samples)
                gl.glUniform1i(uniforms["uSceneSamples"], 0)
                gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, scene)
            else:
                gl.glUniform1i(uniforms["uScene"], 0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, scene)
        elif scene == self._names["colour"] and multisampled:
            program = resources.program("scene_composite_samples", ITEM_QUAD_VERTEX_SOURCE,
                                        _COMPOSITE_SAMPLES_FRAGMENT)
            uniforms = resources.uniforms("scene_composite_samples", ("uMatrix", "uItemSize", "uOrigin", "uExtent",
                                                                       "uSceneSamples", "uSamples"))
            gl.glUseProgram(program)
            gl.glUniform1i(uniforms["uSamples"], self._samples)
            gl.glUniform1i(uniforms["uSceneSamples"], 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, scene)
        else:
            program = resources.program("scene_composite", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_FRAGMENT)
            uniforms = resources.uniforms("scene_composite", ("uMatrix", "uItemSize", "uScene", "uBloom", "uOrigin",
                                                               "uExtent", "uBloomScale", "uBloomStrength"))
            gl.glUseProgram(program)
            gl.glUniform2f(uniforms["uBloomScale"], 1.0 / allocated_width, 1.0 / allocated_height)
            gl.glUniform1f(uniforms["uBloomStrength"], float(bloom) if glow else 0.0)
            gl.glActiveTexture(gl.GL_TEXTURE1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, glow or scene)
            gl.glUniform1i(uniforms["uBloom"], 1)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, scene)
            gl.glUniform1i(uniforms["uScene"], 0)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform2i(uniforms["uOrigin"], x, y)
        gl.glUniform2i(uniforms["uExtent"], width, height)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        if scene == self._names["colour"] and multisampled:
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, 0)
        self._overlay = None

    def _resolve(self, frame: SceneFrame, resources) -> tuple[int, int]:
        """Average the samples of the whole allocation into plain textures (for the post effects).

        Returns the resolved colour and motion (0 without motion blur).
        """
        width, height = self._key[0], self._key[1]
        motion = bool(self._names["velocity"])
        if not self._names["resolve_texture"]:
            self._allocate_resolve()
        key = "scene_resolve_motion" if motion else "scene_resolve"
        program = resources.program(key, FULLSCREEN_VERTEX_SOURCE,
                                    _RESOLVE_MOTION_FRAGMENT if motion else _RESOLVE_FRAGMENT)
        uniforms = resources.uniforms(key, ("uSceneSamples", "uSamples", "uMotionSamples") if motion
                                      else ("uSceneSamples", "uSamples"))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["resolve_fbo"])
        gl.glViewport(0, 0, width, height)
        gl.glUseProgram(program)
        gl.glUniform1i(uniforms["uSamples"], self._samples)
        gl.glUniform1i(uniforms["uSceneSamples"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._names["colour"])
        if motion:
            gl.glUniform1i(uniforms["uMotionSamples"], 1)
            gl.glActiveTexture(gl.GL_TEXTURE1)
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._names["velocity"])
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        if motion:
            gl.glActiveTexture(gl.GL_TEXTURE0)
        return self._names["resolve_texture"], self._names["resolve_velocity"]

    def _composite_overlay_bloom(self, frame: SceneFrame, resources, glow: int, bloom: float) -> None:
        """The overlay with its glow added, premultiplied, under a blend set and restored here."""
        x, y, width, height = self._rect
        multisampled = self._samples > 1
        key = "scene_overlay_bloom_samples" if multisampled else "scene_overlay_bloom"
        program = resources.program(key, ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_OVERLAY_BLOOM_SAMPLES_FRAGMENT
                                    if multisampled else _COMPOSITE_OVERLAY_BLOOM_FRAGMENT)
        names = ("uMatrix", "uItemSize", "uOrigin", "uExtent", "uOpacity", "uBloom", "uBloomScale", "uBloomStrength")
        uniforms = resources.uniforms(key, names + (("uSceneSamples", "uSamples") if multisampled else ("uScene",)))
        gl.glUseProgram(program)
        gl.glUniform1f(uniforms["uOpacity"], self._overlay)
        gl.glUniform2f(uniforms["uBloomScale"], 1.0 / self._key[0], 1.0 / self._key[1])
        gl.glUniform1f(uniforms["uBloomStrength"], float(bloom))
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, glow)
        gl.glUniform1i(uniforms["uBloom"], 1)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        if multisampled:
            gl.glUniform1i(uniforms["uSamples"], self._samples)
            gl.glUniform1i(uniforms["uSceneSamples"], 0)
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._names["colour"])
        else:
            gl.glUniform1i(uniforms["uScene"], 0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._names["colour"])
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform2i(uniforms["uOrigin"], x, y)
        gl.glUniform2i(uniforms["uExtent"], width, height)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendEquation(gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        try:
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        finally:
            if multisampled:
                gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, 0)
        self._overlay = None

    def _restore_inherited_blend(self) -> None:
        blend, self._inherited_blend = self._inherited_blend, None
        if blend is None:
            return
        enabled, source_rgb, destination_rgb, source_alpha, destination_alpha, equation_rgb, equation_alpha = blend
        gl.glBlendFuncSeparate(source_rgb, destination_rgb, source_alpha, destination_alpha)
        gl.glBlendEquationSeparate(equation_rgb, equation_alpha)
        (gl.glEnable if enabled else gl.glDisable)(gl.GL_BLEND)

    def _resolve_emission(self, frame: SceneFrame, resources) -> int:
        """Average the emission's samples over the whole allocation into a plain texture."""
        width, height = self._key[0], self._key[1]
        if not self._names["emission_resolve"]:
            self._allocate_emission_resolve()
        program = resources.program("scene_resolve", FULLSCREEN_VERTEX_SOURCE, _RESOLVE_FRAGMENT)
        uniforms = resources.uniforms("scene_resolve", ("uSceneSamples", "uSamples"))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["emission_resolve_fbo"])
        gl.glViewport(0, 0, width, height)
        gl.glUseProgram(program)
        gl.glUniform1i(uniforms["uSamples"], self._samples)
        gl.glUniform1i(uniforms["uSceneSamples"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._names["emission"])
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        return self._names["emission_resolve"]

    def _allocate_emission_resolve(self) -> None:
        width, height = self._key[0], self._key[1]
        self._allocate_plain_texture("emission_resolve", width, height, gl.GL_RGBA16F)
        self._names["emission_resolve_fbo"] = _new_framebuffer(f"{self.label} emission resolve")
        gl.glNamedFramebufferTexture(self._names["emission_resolve_fbo"], gl.GL_COLOR_ATTACHMENT0,
                                     self._names["emission_resolve"], 0)
        if (gl.glCheckNamedFramebufferStatus(self._names["emission_resolve_fbo"], gl.GL_FRAMEBUFFER)
                != gl.GL_FRAMEBUFFER_COMPLETE):
            raise RuntimeError(f"{self.label} emission resolve incomplete at {width}x{height}")

    def _allocate_resolve(self) -> None:
        """The resolved copies the post effects read (colour, and motion with motion blur)."""
        width, height = self._key[0], self._key[1]
        motion = bool(self._names["velocity"])
        self._allocate_plain_texture("resolve_texture", width, height, gl.GL_RGBA8)
        self._names["resolve_fbo"] = _new_framebuffer(f"{self.label} scene resolve")
        gl.glNamedFramebufferTexture(self._names["resolve_fbo"], gl.GL_COLOR_ATTACHMENT0,
                                     self._names["resolve_texture"], 0)
        if motion:
            self._allocate_plain_texture("resolve_velocity", width, height, gl.GL_RG16F)
            gl.glNamedFramebufferTexture(self._names["resolve_fbo"], gl.GL_COLOR_ATTACHMENT1,
                                         self._names["resolve_velocity"], 0)
            gl.glNamedFramebufferDrawBuffers(self._names["resolve_fbo"], 2,
                                              [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
        if (gl.glCheckNamedFramebufferStatus(self._names["resolve_fbo"], gl.GL_FRAMEBUFFER)
                != gl.GL_FRAMEBUFFER_COMPLETE):
            raise RuntimeError(f"{self.label} scene resolve incomplete at {width}x{height}")

    def _restore_inherited(self, frame: SceneFrame) -> None:
        if self._names["velocity"] or self._names["emission"]:
            gl.glColorMaski(1, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)   # GL's default
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._inherited[0])
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._inherited[1])
        gl.glViewport(*frame.viewport)
        if self._scissor:
            gl.glEnable(gl.GL_SCISSOR_TEST)
        else:
            gl.glDisable(gl.GL_SCISSOR_TEST)

    def _allocate_plain_texture(self, key: str, width: int, height: int, internal: int) -> None:
        """Register a plain attachment before configuring immutable storage for cleanup retry."""
        texture = _new_texture(gl.GL_TEXTURE_2D, f"{self.label} scene target")
        self._names[key] = texture
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTextureParameteri(texture, parameter, gl.GL_NEAREST)
        gl.glTextureStorage2D(texture, 1, internal, width, height)

    def _allocate_attachment(self, key: str, samples: int, width: int, height: int, internal: int) -> None:
        """Register a scene attachment before its immutable storage can fail."""
        if samples > 1:
            texture = _new_texture(gl.GL_TEXTURE_2D_MULTISAMPLE, f"{self.label} scene target")
            self._names[key] = texture
            gl.glTextureStorage2DMultisample(texture, samples, internal, width, height, True)
            return
        self._allocate_plain_texture(key, width, height, internal)

    def _allocate(self, width: int, height: int, requested: int, motion_blur: bool = False,
                  emission: bool = False) -> None:
        samples = min(requested, gl_query.get_int(gl.GL_MAX_SAMPLES),
                      gl_query.get_int(gl.GL_MAX_COLOR_TEXTURE_SAMPLES))
        self._names["fbo"] = _new_framebuffer(f"{self.label} scene target")
        self._allocate_attachment("colour", samples, width, height, gl.GL_RGBA8)
        if motion_blur:
            self._allocate_attachment("velocity", samples, width, height, gl.GL_RG16F)
        if emission:
            self._allocate_attachment("emission", samples, width, height, gl.GL_RGBA16F)
        name = (ctypes.c_uint * 1)()
        gl.glCreateRenderbuffers(1, name)
        self._names["depth"] = int(name[0])
        if not self._names["depth"]:
            raise RuntimeError(f"{self.label} scene depth allocation failed")
        gl.glNamedRenderbufferStorageMultisample(self._names["depth"], samples if samples > 1 else 0,
                                                  gl.GL_DEPTH_COMPONENT24, width, height)
        gl.glNamedFramebufferTexture(self._names["fbo"], gl.GL_COLOR_ATTACHMENT0, self._names["colour"], 0)
        second = self._names["velocity"] or self._names["emission"]
        if second:
            gl.glNamedFramebufferTexture(self._names["fbo"], gl.GL_COLOR_ATTACHMENT1, second, 0)
            gl.glNamedFramebufferDrawBuffers(self._names["fbo"], 2,
                                              [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
        gl.glNamedFramebufferRenderbuffer(self._names["fbo"], gl.GL_DEPTH_ATTACHMENT,
                                           gl.GL_RENDERBUFFER, self._names["depth"])
        if (gl.glCheckNamedFramebufferStatus(self._names["fbo"], gl.GL_FRAMEBUFFER)
                != gl.GL_FRAMEBUFFER_COMPLETE):
            raise RuntimeError(f"{self.label} scene target incomplete at {width}x{height}x{samples}")
        self._key = (width, height, requested, bool(motion_blur), bool(emission))
        self._samples = max(1, samples)

    def release(self) -> None:
        errors: list[str] = []
        for chain in (self._bloom, self._motion):
            try:
                chain.release()
            except Exception as exc:
                errors.append(str(exc))
        for key, delete in (
            ("fbo", lambda name: gl.glDeleteFramebuffers(1, [name])),
            ("resolve_fbo", lambda name: gl.glDeleteFramebuffers(1, [name])),
            ("colour", lambda name: gl.glDeleteTextures([name])),
            ("velocity", lambda name: gl.glDeleteTextures([name])),
            ("depth", lambda name: gl.glDeleteRenderbuffers(1, [name])),
            ("resolve_texture", lambda name: gl.glDeleteTextures([name])),
            ("resolve_velocity", lambda name: gl.glDeleteTextures([name])),
            ("emission", lambda name: gl.glDeleteTextures([name])),
            ("emission_resolve_fbo", lambda name: gl.glDeleteFramebuffers(1, [name])),
            ("emission_resolve", lambda name: gl.glDeleteTextures([name])),
        ):
            name = self._names[key]
            if not name:
                continue
            try:
                delete(name)
            except Exception as exc:
                errors.append(f"{key}: {exc}")
            else:
                self._names[key] = 0
        self._key = None
        self._samples = 0
        if errors:
            raise RuntimeError(f"{self.label} scene target cleanup incomplete: {' | '.join(errors)}")

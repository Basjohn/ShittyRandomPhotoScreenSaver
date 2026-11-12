"""Compute pass identity (N1.2, N1.7): run each converted pass through its real owner on fixed inputs, in a hidden
offscreen GL context, and record its outputs, the GL calls the owner made for it, its GPU time and its memory.

A conversion (loose uniforms into a dispatch block, explicit bindings, a storage format widened or narrowed) must
leave every output bit-identical: record the outputs before the change, again after, and compare. GL calls are
counted per name for the owner call alone (calls through ``OpenGL.GL`` in the render modules, the stream ring's raw
multi-binds, and ``gl_query`` reads as ``query:<helper>``). Memory is each owner texture's allocated bytes (every
level and sample); outputs read the channels a stage means, never the storage format's, so a widened target
compares against its narrower self. The N1.7 passes (heightfield, Waveform's slope map, the defocus layer, the
scene target's motion blur, Bubble's light attachment) also record what a consumer samples or the final pixels.

    python tools/compute_pass_identity.py record --out .artifacts/evidence/architecture/<topic>/<YYYYMMDD>_<label>
    python tools/compute_pass_identity.py compare <before folder> <after folder>

No window: a hidden offscreen surface. Writes only into the evidence layout (``tools/artifact_paths.py``).
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

_QUERY_HELPERS = ("get_int", "get_ints", "get_bool", "get_bools", "get_float", "get_floats", "is_enabled",
                  "get_indexed_int", "get_indexed_bools", "get_indexed_int64")


class _Counting:
    """Stands in for a GL function module: counts each ``gl*`` call made through it."""

    def __init__(self, module, counter, prefix=""):
        self._module, self._counter, self._prefix, self._cache = module, counter, prefix, {}

    def __getattr__(self, name):
        value = getattr(self._module, name)
        if not callable(value) or not name.startswith("gl"):
            return value
        wrapped = self._cache.get(name)
        if wrapped is None:
            counter, key = self._counter, self._prefix + name

            def wrapped(*a, _f=value, **k):
                counter[key] = counter.get(key, 0) + 1
                return _f(*a, **k)
            self._cache[name] = wrapped
        return wrapped


@contextmanager
def counting(counter: dict[str, int]):
    """Count every GL call the render modules make inside the scope."""
    from OpenGL import GL
    from OpenGL.raw.GL.VERSION import GL_4_4
    from rendering.quick import gl_query
    swapped, helpers = [], []
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith("rendering."):
            continue
        for attribute, original in (("gl", GL), ("_gl44", GL_4_4)):
            if getattr(module, attribute, None) is original:
                swapped.append((module, attribute, original))
                setattr(module, attribute, _Counting(original, counter))
    for helper in _QUERY_HELPERS:
        original = getattr(gl_query, helper)

        def counted(*a, _f=original, _n=f"query:{helper}", **k):
            counter[_n] = counter.get(_n, 0) + 1
            return _f(*a, **k)
        helpers.append((helper, original))
        setattr(gl_query, helper, counted)
    try:
        yield counter
    finally:
        for module, attribute, original in swapped:
            setattr(module, attribute, original)
        for helper, original in helpers:
            setattr(gl_query, helper, original)


def gpu_ms(run, repeats: int = 25, warm: int = 8) -> float:
    """Median GPU time (GL_TIME_ELAPSED) of ``run()`` over ``repeats`` calls, in milliseconds, after ``warm``
    untimed calls (the GPU leaves its idle clocks first; without them run-to-run medians varied 3x)."""
    from OpenGL import GL as gl
    times = []
    for index in range(warm):
        run(index)
    gl.glFinish()
    query = int(np.asarray(gl.glGenQueries(1)).reshape(-1)[0])
    try:
        for index in range(repeats):
            gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
            run(index)
            gl.glEndQuery(gl.GL_TIME_ELAPSED)
            value = ctypes.c_uint64(0)
            gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
            times.append(value.value / 1e6)
    finally:
        gl.glDeleteQueries(1, [query])
    return float(np.median(times))


def _texture(width, height, internal, data=None, layout=None):
    from OpenGL import GL as gl
    name = (gl.GLuint * 1)()
    gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
    texture = int(name[0])
    for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
        gl.glTextureParameteri(texture, parameter, gl.GL_NEAREST)
    gl.glTextureStorage2D(texture, 1, internal, width, height)
    if data is not None:
        gl.glTextureSubImage2D(texture, 0, 0, 0, width, height, *(layout or (gl.GL_RG, gl.GL_FLOAT)),
                               np.ascontiguousarray(data))
    return texture


def _read_texture(texture, width, height, channels, fmt=None):
    from OpenGL import GL as gl
    out = np.zeros((height, width, channels), np.float32)
    gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT | gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
    fmt = fmt or {1: gl.GL_RED, 2: gl.GL_RG, 4: gl.GL_RGBA}[channels]
    gl.glGetTextureImage(texture, 0, fmt, gl.GL_FLOAT, out.nbytes, out)
    return out


def _read_levels(texture, width, height, channels, levels):
    """Every mip level of a 2D texture, as {level: float array}."""
    return {level: _read_level(texture, max(width >> level, 1), max(height >> level, 1), channels, level)
            for level in range(levels)}


def _read_level(texture, width, height, channels, level):
    from OpenGL import GL as gl
    out = np.zeros((height, width, channels), np.float32)
    gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT | gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
    fmt = {1: gl.GL_RED, 2: gl.GL_RG, 3: gl.GL_RGB, 4: gl.GL_RGBA}[channels]
    gl.glGetTextureImage(texture, level, fmt, gl.GL_FLOAT, out.nbytes, out)
    return out


def _texel_bytes():
    from OpenGL import GL as gl
    return {gl.GL_R16F: 2, gl.GL_R32F: 4, gl.GL_RG16F: 4, gl.GL_RG32F: 8, gl.GL_RGBA16F: 8, gl.GL_RGBA32F: 16,
            gl.GL_R11F_G11F_B10F: 4, gl.GL_RGBA8: 4, gl.GL_SRGB8_ALPHA8: 4, gl.GL_DEPTH_COMPONENT32F: 4}


def texture_bytes(texture) -> int:
    """GPU bytes of one texture as allocated (every mip level and sample; formats in ``_texel_bytes``)."""
    from OpenGL import GL as gl
    value = np.zeros(1, np.int32)

    def level_parameter(level, name):
        gl.glGetTextureLevelParameteriv(texture, level, name, value)
        return int(value[0])
    gl.glGetTextureParameteriv(texture, gl.GL_TEXTURE_IMMUTABLE_LEVELS, value)
    levels = max(int(value[0]), 1)
    internal = level_parameter(0, gl.GL_TEXTURE_INTERNAL_FORMAT)
    per_texel = _texel_bytes()[internal]
    samples = max(level_parameter(0, gl.GL_TEXTURE_SAMPLES), 1)
    total = 0
    for level in range(levels):
        total += (level_parameter(level, gl.GL_TEXTURE_WIDTH) * level_parameter(level, gl.GL_TEXTURE_HEIGHT)
                  * max(level_parameter(level, gl.GL_TEXTURE_DEPTH), 1))
    return total * per_texel * samples


def _memory(prefix, textures) -> dict[str, int]:
    """{"memory_bytes:<prefix>:<role>": bytes} for each named texture (0 skipped)."""
    return {f"memory_bytes:{prefix}:{role}": texture_bytes(texture) for role, texture in textures.items() if texture}


_QUAD_VERTEX = """#version 460 core
layout(location = 0) in vec2 aPosition;
out vec2 vUv;
void main() { vUv = aPosition; gl_Position = vec4(aPosition * 2.0 - 1.0, 0.0, 1.0); }
"""

# What a consumer reads from a two-channel texture (.rg) through filtering: trilinear and anisotropic over a
# perspective-like warp, so mip selection and the anisotropic footprint vary across the image.
_SAMPLE_RG_FRAGMENT = """#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uTexture;
uniform float uLod;   // < 0: implicit derivatives (trilinear/anisotropic); otherwise that explicit level
void main() {
    vec2 uv = vec2(vUv.x * (0.6 + 2.4 * vUv.y), 1.0 / (0.15 + 0.85 * vUv.y)) * vec2(1.0, 0.35);
    vec2 rg = uLod < 0.0 ? texture(uTexture, uv).rg : textureLod(uTexture, uv, uLod).rg;
    FragColor = vec4(rg, 0.0, 0.0);
}
"""


def _sample_rg(target, resources, texture, size, lod=-1.0):
    """``.rg`` of ``texture`` sampled across a warped grid into an RGBA32F image (size), as a consumer reads it."""
    from OpenGL import GL as gl
    width, height = size
    out = _texture(width, height, gl.GL_RGBA32F)
    fbo = (gl.GLuint * 1)()
    gl.glCreateFramebuffers(1, fbo)
    try:
        gl.glNamedFramebufferTexture(int(fbo[0]), gl.GL_COLOR_ATTACHMENT0, out, 0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, int(fbo[0]))
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        program = resources.program("identity_sample_rg", _QUAD_VERTEX, _SAMPLE_RG_FRAGMENT)
        gl.glUseProgram(program)
        gl.glBindTextureUnit(0, texture)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uTexture"), 0)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uLod"), float(lod))
        gl.glBindVertexArray(target.vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        return _read_texture(out, width, height, 4)[..., :2].copy()
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glDeleteFramebuffers(1, fbo)
        gl.glDeleteTextures([out])


def _read_buffer(buffer, count, dtype):
    from OpenGL import GL as gl
    gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
    out = np.zeros(count, dtype=dtype)
    gl.glGetNamedBufferSubData(buffer, 0, out.nbytes, out)
    return out


# ---- passes: each returns ({output name: array}, {call name: count}) for one owner call on fixed inputs ----

def pass_motion_tile_max(target):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.motion import MotionBlur
    from rendering.quick.scene3d.resources import MeshResources
    outputs, calls = {}, {}
    rng = np.random.default_rng(1234)
    for width, height in ((97, 61), (300, 770), (1920, 1080), (2560, 1440)):
        resources, blur = MeshResources("identity"), MotionBlur("identity")
        pixels = rng.integers(0, 256, size=(height, width, 4)).astype(np.uint8)
        scene = _texture(width, height, gl.GL_RGBA8, pixels, (gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))
        field = rng.integers(-64, 65, size=(height, width, 2)).astype(np.float32) / 4.0
        velocity = _texture(width, height, gl.GL_RG16F, field)
        try:
            blur.apply(scene, velocity, (width, height), resources, target.vao)   # compiles and allocates
            counter = {}
            with counting(counter):
                blurred = blur.apply(scene, velocity, (width, height), resources, target.vao)
            tiles, _fbo, tile_w, tile_h = blur._passes[0]
            outputs[f"tiles_{width}x{height}"] = _read_texture(tiles, tile_w, tile_h, 2)
            outputs[f"gather_{width}x{height}"] = _read_texture(blurred, width, height, 4)
            calls = calls or counter
            calls.update(_memory(f"{width}x{height}", {"tiles": tiles}))
            if width >= 1920:
                run = lambda _i: blur.apply(scene, velocity, (width, height), resources, target.vao)
                calls[f"gpu_ms:{width}x{height}"] = gpu_ms(run)
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            gl.glDeleteTextures([scene, velocity])
            blur.release()
            resources.release_resources()
    return outputs, calls


def pass_population_scan(target):
    from OpenGL import GL as gl
    from rendering.gl_programs.scene3d import SCENE3D_GLSL
    from rendering.quick.scene3d.population import POPULATION_FIRST_BINDING, CompactedPopulation
    from rendering.quick.scene3d.resources import MeshResources
    hooks = SCENE3D_GLSL + """
uniform float uThreshold;
uniform uint uSeed;
bool populationActive(uint id) { return sceneRandom(id, 1u, uSeed) < uThreshold; }
vec4 populationState(uint id) { return vec4(float(id), sceneRandom(id, 2u, uSeed), uThreshold, 1.0); }
"""

    def configure(_key, program):
        gl.glUniform1f(gl.glGetUniformLocation(program, "uThreshold"), 0.3)
        gl.glUniform1ui(gl.glGetUniformLocation(program, "uSeed"), 77)

    outputs, calls = {}, {}
    for population in (1, 9483, 300_000):
        resources, pool = MeshResources("identity"), CompactedPopulation("identity")
        try:
            pool.warm(population)
            with pool.bound():
                pool.update(resources, "probe", hooks, population, 4, configure)
            counter = {}
            with counting(counter), pool.bound():
                pool.update(resources, "probe", hooks, population, 4, configure)
            groups = -(-population // 256)
            names = pool._names
            outputs[f"offsets_{population}"] = _read_buffer(names[POPULATION_FIRST_BINDING + 1], groups, np.uint32)
            command = _read_buffer(names[POPULATION_FIRST_BINDING + 2], 4, np.uint32)
            outputs[f"command_{population}"] = command
            outputs[f"ids_{population}"] = _read_buffer(names[POPULATION_FIRST_BINDING + 3], int(command[1]), np.uint32)
            calls = counter if population == 9483 else calls
        finally:
            pool.release()
            resources.release_resources()
    return outputs, calls


def _photo(width, height, seed):
    """A fixed synthetic photograph: smooth gradients, hard-edged shapes and grain (linear filtered, as the lent
    presentation texture is)."""
    from OpenGL import GL as gl
    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    image = np.zeros((height, width, 4), np.float32)
    image[..., 0] = xs / width
    image[..., 1] = ys / height
    image[..., 2] = 0.5 + 0.5 * np.sin(xs * 0.05) * np.cos(ys * 0.07)
    for _ in range(12):
        cx, cy, r = rng.uniform(0, width), rng.uniform(0, height), rng.uniform(10, 0.3 * height)
        image[(xs - cx) ** 2 + (ys - cy) ** 2 < r * r, :3] = rng.uniform(0, 1, 3)
    image[..., :3] += rng.normal(0, 0.03, (height, width, 3))
    image[..., 3] = 1.0
    pixels = (np.clip(image, 0, 1) * 255).astype(np.uint8)
    texture = _texture(width, height, gl.GL_RGBA8, pixels, (gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))
    for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
        gl.glTextureParameteri(texture, parameter, gl.GL_LINEAR)
    return texture


_EDGE_FIELD_CHANNELS = {"luma": 1, "blur": 1, "edge": 1, "ping": 2, "pong": 2, "field": 2}


def pass_edge_field(target):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.edge_field import EdgeField
    from rendering.quick.scene3d.resources import MeshResources
    outputs, calls = {}, {}
    for (width, height), (low, high) in (((1920, 1080), (0.04, 0.2)), ((333, 517), (0.02, 0.1))):
        resources, field = MeshResources("identity"), EdgeField("identity")
        photo = _photo(width, height, width)
        try:
            field.texture(resources, photo, (width, height), ("warm",), low, high)   # compiles and allocates
            counter = {}
            with counting(counter):
                field.texture(resources, photo, (width, height), ("run",), low, high)
            fw, fh = field._size
            for role, _internal, _linear in EdgeField._ROLES:
                # The channels each stage means (stable across a storage format change).
                channels = _EDGE_FIELD_CHANNELS[role]
                outputs[f"{role}_{width}x{height}"] = _read_texture(field._textures[role], fw, fh, channels)
            outputs[f"field_sampled_{width}x{height}"] = _sample_rg(target, resources, field._textures["field"],
                                                                    (fw, fh))
            calls = calls or counter
            calls.update(_memory(f"{width}x{height}", field._textures))
            build = lambda index: field.texture(resources, photo, (width, height), ("time", index), low, high)
            calls[f"gpu_ms:{width}x{height}"] = gpu_ms(build)
        finally:
            gl.glDeleteTextures([photo])
            field.release()
            resources.release_resources()
    return outputs, calls


_PROPAGATION_COST = ("uniform float uChannel;\n"
                     "float propagationCost(vec2 p) { return abs(p.y) < 0.03 ? uChannel : 2.0 + sin(9.0 * p.x); }\n")


def pass_propagation_field(target):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.propagation_field import PropagationField
    from rendering.quick.scene3d.resources import MeshResources
    outputs, calls = {}, {}
    sources = [(-0.7, 0.0, 0.0), (0.5, 0.3, 0.2), (0.1, -0.35, 0.05)]
    set_cost = {"uChannel": 0.3}     # the cost's values (the seed's pass block since N1.6)
    for size in ((1920, 1080), (300, 700)):
        resources = MeshResources("identity")
        field = PropagationField("identity", "identity", _PROPAGATION_COST)
        try:
            field.textures(resources, size, ("warm",), sources, 2.6, set_cost)   # compiles and allocates
            counter = {}
            with counting(counter):
                while not field.build_step(resources, size, ("run",), sources, 2.6, set_cost):
                    pass
            fw, fh = field._size
            for role in ("cost", "arrival"):
                outputs[f"{role}_{size[0]}x{size[1]}"] = _read_texture(field._textures[role], fw, fh, 1)
            outputs[f"extent_{size[0]}x{size[1]}"] = _read_texture(field._textures["extent"], 1, 1, 1)
            calls = calls or counter
            build = lambda index: field.textures(resources, size, ("time", index), sources, 2.6, set_cost)
            calls[f"gpu_ms:{size[0]}x{size[1]}"] = gpu_ms(build, repeats=5)
        finally:
            field.release()
            resources.release_resources()
    return outputs, calls


def _ribbon_packet(lower: float):
    """A fixed four-ribbon cloth history (as tests/test_waveform_atmosphere_field.py builds), ``lower`` world units
    nearer the floor."""
    from core.ribbon_ring import RibbonRing
    ring = RibbonRing(4, colours=[(.1 + .1 * i, .5, .9, 1.) for i in range(4)])
    for index in range(256):
        x = -95.6 + .4 * index
        ring.append(index / 6, [(x, 1.8 - lower + .6 * np.sin(x * .4 + i), i * .35) for i in range(4)],
                    [.4] * 4, twists=[.07 * index + .4 * i for i in range(4)], emission=.5 + index / 256)
    return ring.packet()


def pass_waveform_fields(target):
    """The Waveform world field (atmosphere) and the yielding floor's field (section + blur) from one packet."""
    from dataclasses import replace
    from core.waveform_ribbon_scene import FLOOR_CONTACT, Floor
    from rendering.quick.scene3d.floor_give import FloorGiveField
    from rendering.quick.scene3d.ribbon import RibbonPrimitive
    from rendering.quick.scene3d.waveform_field import WaveformField
    from rendering.gl_programs.waveform_atmosphere import FIELD_ROWS, FIELD_RIBBONS
    from rendering.gl_programs.waveform_floor_give import FLOOR_GIVE_ROWS
    outputs, calls = {}, {}
    grade = (((0., (.1, .5, .9)), (.4, (.9, .3, .2)), (1., (.2, .9, .4))), (-60., 60.), 0., .6)
    floor = replace(Floor(), give=.8)
    for side, lower in ((1., 1.6), (-1., 2.2)):
        packet = _ribbon_packet(lower)
        field, give, primitive = WaveformField(), FloorGiveField(), RibbonPrimitive()
        try:
            with primitive.packet_scope(packet):
                run_field = lambda: field.update(packet, translation=(.3, -.1, .2), span=(-80., 80., 1024),
                                                 grade=grade, side=side, restore=False)
                run_give = lambda: give.update(packet, translation=(.3, -.1, .2), floor=floor, contact=FLOOR_CONTACT,
                                               camber=.35, side=side, restore=False)
                run_field()
                run_give()                                        # compiled and allocated
                field_calls, give_calls = {}, {}
                with counting(field_calls):
                    run_field()
                with counting(give_calls):
                    run_give()
            samples = int(floor.give_span[2])
            outputs[f"world_field_side{side:+.0f}"] = _read_texture(field.texture, 1024, FIELD_ROWS, 4)
            outputs[f"give_sections_side{side:+.0f}"] = _read_texture(give._sections, samples, FIELD_RIBBONS, 4)
            outputs[f"give_field_side{side:+.0f}"] = _read_texture(give.texture, samples, FLOOR_GIVE_ROWS, 4)
            if not calls:
                calls = {**{f"field:{k}": v for k, v in field_calls.items()},
                         **{f"give:{k}": v for k, v in give_calls.items()}}
        finally:
            from OpenGL import GL as gl
            gl.glUseProgram(0)
            field.release()
            give.release()
            primitive.release()
    return outputs, calls


_FOG_MEDIUM = """
uniform vec4 uSphere;   // clear-air centre xyz, radius
uniform float uSteady;  // the steady share
void fogMedium(vec3 world, out vec3 radiance, out float extinction, out float steady) {
    float lump=0.5+0.5*sin(world.x*1.3)*cos(world.y*0.9+world.z*0.4);
    bool slab=world.z<-4.0 && world.z>-30.0 && length(world-uSphere.xyz)>uSphere.w;
    extinction=slab?0.35*lump:0.0;
    radiance=vec3(0.2,0.4,0.8)*(0.5+lump);
    steady=uSteady*extinction*(1.0-lump);
}
"""


def _read_texture_3d(texture, grid, channels):
    from OpenGL import GL as gl
    out = np.zeros((grid[2], grid[1], grid[0], channels), np.float32)
    gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT | gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
    gl.glGetTextureImage(texture, 0, gl.GL_RED if channels == 1 else gl.GL_RGBA, gl.GL_FLOAT, out.nbytes, out)
    return out


def pass_fog_volume(target):
    """The fog volume's inject (the volume's own head with a fixed medium) and integrate, and the detail march that
    samples the medium, the steady share and the camera mapping."""
    from OpenGL import GL as gl
    from rendering.gl_programs.fog_volume import fog_inject_source
    from rendering.quick.render.gl_resources import compile_compute_program, delete_program
    from rendering.quick.scene3d.fog_volume import FogMarch, FogVolume
    outputs, calls = {}, {}
    program = compile_compute_program(fog_inject_source(_FOG_MEDIUM), label="identity fog medium")
    medium = lambda p: (gl.glUniform4f(gl.glGetUniformLocation(p, "uSphere"), .5, .2, -9., 2.5),
                        gl.glUniform1f(gl.glGetUniformLocation(p, "uSteady"), .6))
    view = np.identity(4)
    view[:3, :3] = [[.96, 0., .28], [.05, .98, -.17], [-.27, .18, .94]]
    view[:3, 3] = (-.4, -1.1, .3)
    try:
        for grid, focus in (((128, 72, 128), 0.), ((80, 45, 96), 9.)):
            volume, march = FogVolume("identity"), FogMarch("identity")
            try:
                run = lambda *_: volume.update(program, view=view, lens=(.7, .4), depth_range=(1., 60.), grid=grid,
                                               medium=medium, focus_depth=focus, restore=False)
                run()
                counter = {}
                with counting(counter):
                    run()
                label = "x".join(map(str, grid))
                outputs[f"medium_{label}"] = _read_texture_3d(volume.medium_texture, grid, 4)
                outputs[f"steady_{label}"] = _read_texture_3d(volume.steady_texture, grid, 1)
                outputs[f"integrated_{label}"] = _read_texture_3d(volume.texture, grid, 4)
                march.march(volume, size=(320, 180), steps=64, ground=-1.5)
                outputs[f"march_{label}"] = _read_texture(march.texture, 320, 180, 4)
                calls = calls or counter
                calls.update(_memory(label, {"medium": volume.medium_texture, "steady": volume.steady_texture,
                                             "integrated": volume.texture}))
                calls[f"gpu_ms:{label}"] = gpu_ms(run)
            finally:
                gl.glUseProgram(0)
                volume.release()
                march.release()
    finally:
        delete_program(program)
    return outputs, calls


# ---- N1.7: the render targets and sampled textures in a format QRhi lacks (two-channel floats, R11G11B10F) ----

def pass_heightfield(target):
    """Neon Lake's two-component heightfield (height, distance to the bank): the upload and what a consumer
    samples (``.r``/``.g``, linear) from it."""
    from rendering.gl_programs.heightfield import HEIGHTFIELD_MAX_SIZE
    from rendering.quick.scene3d.heightfield import HeightfieldTexture
    from rendering.quick.scene3d.resources import MeshResources
    outputs, calls = {}, {}
    rng = np.random.default_rng(57)
    for size in (65, HEIGHTFIELD_MAX_SIZE):
        data = rng.normal(0.0, 1.0, (size, size, 2)).astype(np.float32)
        data[..., 1] = np.abs(data[..., 1]) * 30.0
        resources, field = MeshResources("identity"), HeightfieldTexture("identity", components=2)
        try:
            counter = {}
            with counting(counter):
                texture = field.ensure(size, data.tobytes())
            outputs[f"texels_{size}"] = _read_texture(texture, size, size, 2)
            outputs[f"sampled_{size}"] = _sample_rg(target, resources, texture, (320, 240), lod=0.0)
            calls = calls or counter
            calls.update(_memory(str(size), {"heightfield": texture}))
        finally:
            field.release()
            resources.release_resources()
    return outputs, calls


def pass_waveform_slope(target):
    """Waveform's floor slope map (baked once from the height map): every mip level and what the floor shader
    samples (``.rg``, trilinear and anisotropic)."""
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.waveform import _slope_texture
    outputs, calls = {}, {}
    rng = np.random.default_rng(91)
    for size in (256, 1024):
        # A periodic, smooth height map (as the saved floor's is): a few random sine octaves.
        ys, xs = np.mgrid[0:size, 0:size].astype(np.float32) * (2.0 * np.pi / size)
        height = np.zeros((size, size), np.float32)
        for octave in range(1, 6):
            fx, fy, phase = rng.integers(1, 4 * octave, 2).tolist() + [rng.uniform(0, 6.3)]
            height += np.sin(fx * xs + fy * ys + phase).astype(np.float32) / octave
        resources = MeshResources("identity")
        texture = 0
        try:
            counter = {}
            with counting(counter):
                texture = _slope_texture(height)
            levels = size.bit_length()
            for level, image in _read_levels(texture, size, size, 2, levels).items():
                outputs[f"level{level}_{size}"] = image
            outputs[f"sampled_{size}"] = _sample_rg(target, resources, texture, (640, 360))
            calls = calls or counter
            calls.update(_memory(str(size), {"slope": texture}))
        finally:
            if texture:
                gl.glDeleteTextures([texture])
            resources.release_resources()
    return outputs, calls


_DEFOCUS_SCENE_FRAGMENT = """#version 460 core
in vec2 vUv;
uniform vec2 uSize;
{defocus}
void main() {{
    // A grid of discs, each with its own colour, radius and circle of confusion, and a bright core (a highlight).
    vec2 p = vUv * uSize;
    vec2 cell = floor(p / 96.0);
    vec2 centre = (cell + 0.5) * 96.0 + 9.0 * sin(cell.yx * 2.3);
    float radius = 10.0 + mod(cell.x * 7.0 + cell.y * 3.0, 5.0) * 7.0;
    float d = length(p - centre);
    if (d > radius) discard;
    float alpha = clamp(radius - d, 0.0, 1.0) * (0.55 + 0.45 * fract(cell.x * 0.37 + cell.y * 0.61));
    vec3 colour = 0.5 + 0.5 * sin(vec3(cell.x, cell.y, cell.x + cell.y) * 1.7 + vec3(0.0, 2.1, 4.2));
    if (d < 3.0) colour *= 5.0;
    float coc = 1.5 + mod(cell.x * 5.0 + cell.y * 11.0, 9.0) * 4.5;
    sceneDefocusWrite(colour * alpha, alpha, coc);
}}
"""


def pass_defocus(target):
    """Extruded Bubble's near-layer defocus: a fixed layer (colour and circle of confusion, max-blended), every
    level of the circle after the composite's mip build, and the composite's pixels over a fixed background."""
    from OpenGL import GL as gl
    from rendering.quick.scene3d.defocus import SCENE_DEFOCUS_GLSL, DefocusLayer
    from rendering.quick.scene3d.resources import MeshResources
    outputs, calls = {}, {}
    fragment = _DEFOCUS_SCENE_FRAGMENT.format(defocus=SCENE_DEFOCUS_GLSL)
    max_radius = 40.0
    for width, height in ((1920, 1080), (2560, 1440), (3840, 2160)):
        target.resize(width, height)
        resources, layer = MeshResources("identity"), DefocusLayer("identity")
        try:
            program = resources.program("identity_defocus_scene", _QUAD_VERTEX, fragment)

            def run(_index=0):
                target.bind(clear=(0.08, 0.1, 0.16, 1.0))
                layer.begin(width, height)
                gl.glUseProgram(program)
                gl.glUniform2f(gl.glGetUniformLocation(program, "uSize"), float(width), float(height))
                gl.glBindVertexArray(target.vao)
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                layer.end()
                layer.composite(max_radius)
            run()                                                   # compiles and allocates
            counter = {}
            with counting(counter):
                run()
            label = f"{width}x{height}"
            if width < 3840:
                levels = max(width, height).bit_length()
                for level, image in _read_levels(layer._circle, width, height, 2, levels).items():
                    outputs[f"circle_level{level}_{label}"] = image
                outputs[f"composite_{label}"] = target.read_rgba()
            calls = calls or counter
            calls.update(_memory(label, {"colour": layer._colour, "circle": layer._circle, "below": layer._below}))
            calls[f"gpu_ms:{label}"] = gpu_ms(run)
        finally:
            layer.release()
            resources.release_resources()
    target.resize(64, 64)
    return outputs, calls


_MOVING_FRAGMENT = """#version 460 core
layout(location = 0) out vec4 FragColor;
layout(location = 1) out vec4 Motion;
uniform vec2 uMotion;
uniform vec4 uColour;
void main() {
    FragColor = uColour;
    Motion = vec4(uMotion, 0.0, 1.0);
}
"""


def _moving_program():
    """(vertex, fragment, pass block) of the moving squares: ``_MOVING_FRAGMENT`` over the item quad (N1.6)."""
    from rendering.gl_programs.item_quad import item_quad_program

    return item_quad_program(_MOVING_FRAGMENT, block="IdentityMoving", samplers={})


def pass_scene_motion_blur(target):
    """The scene target's motion blur end to end: a photograph and moving squares drawn into the velocity
    attachment, the resolve (multisampled), the tile max and the gather: final pixels and the velocity the post
    pass reads."""
    from types import SimpleNamespace
    from OpenGL import GL as gl
    from rendering.gl_programs.portable import pack_block
    from rendering.quick.scene3d.motion import motion_blur_tile
    from rendering.quick.scene3d.resources import MeshResources, bind_frame
    from rendering.quick.scene3d.target import SceneTarget
    outputs, calls = {}, {}
    vertex, fragment, block = _moving_program()

    def frame(width, height, left=0.0, top=0.0, w=None, h=None):
        w, h = (width if w is None else w), (height if h is None else h)
        matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0,
                  2 * left / width - 1, 1 - 2 * top / height, 0, 1)
        return SimpleNamespace(viewport=(0, 0, width, height), logical_size=(float(w), float(h)),
                               matrix_values=matrix, quad_vao=target.vao)

    for (width, height), samples in (((1920, 1080), 1), ((1920, 1080), 4), ((2560, 1440), 4)):
        target.resize(width, height)
        resources, scene = MeshResources("identity"), SceneTarget("identity")
        photo = _photo(width, height, width + samples)
        tile = motion_blur_tile(height)
        rng = np.random.default_rng(width + samples)
        squares = [(rng.uniform(0, width - 200), rng.uniform(0, height - 200), rng.uniform(40, 200),
                    rng.uniform(-1.6, 1.6, 2) * tile, rng.uniform(0, 1, 4)) for _ in range(14)]
        full = frame(width, height)
        try:
            def run(_index=0):
                target.bind(clear=(0.0, 0.0, 0.0, 1.0))
                with scene.scope(full, samples, resources, rect=(0, 0, width, height), motion_blur=True):
                    resources.draw_image(full, photo)
                    program = resources.program("identity_moving", vertex, fragment)
                    uniforms = resources.uniforms("identity_moving", ())
                    values = resources.values("identity_moving")
                    with scene.velocity_writes():
                        for left, top, size, motion, colour in squares:
                            square = frame(width, height, left, top, size, size)
                            bind_frame(program, uniforms, square, values)
                            values["uMotion"] = tuple(motion)
                            values["uColour"] = tuple(colour)
                            with resources.pass_blocks.bound(pack_block(block, values)):
                                gl.glBindVertexArray(target.vao)
                                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            run()                                                   # compiles and allocates
            counter = {}
            with counting(counter):
                run()
            label = f"{width}x{height}_s{samples}"
            aw, ah = scene._key[0], scene._key[1]
            velocity = scene._names["velocity"] if samples == 1 else scene._names["resolve_velocity"]
            outputs[f"velocity_{label}"] = _read_texture(velocity, aw, ah, 2)
            outputs[f"final_{label}"] = target.read_rgba()
            calls = calls or counter
            tiles = scene._motion._passes[0][0] if scene._motion is not None and scene._motion._passes else 0
            calls.update(_memory(label, {"velocity": scene._names["velocity"],
                                         "resolve_velocity": scene._names["resolve_velocity"], "tiles": tiles}))
            calls[f"gpu_ms:{label}"] = gpu_ms(run)
        finally:
            gl.glDeleteTextures([photo])
            scene.release()
            resources.release_resources()
    target.resize(64, 64)
    return outputs, calls


def pass_bubble_light(target):
    """Bubble's ambience pass with glowing particles: the 8-bit coverage and the additive light attachment (linear
    radiance), at a TV-wide card and a 1080p one."""
    from OpenGL import GL as gl
    from rendering.quick.visualizer.implementations.bubble_ambient_gl import QuickBubbleAmbientPoints
    outputs, calls = {}, {}
    rng = np.random.default_rng(3)
    for width, height in ((1920, 1080), (3874, 1450)):
        records = []
        for index in range(160):
            particle = index >= 40
            records += [rng.uniform(0.02, 0.98), rng.uniform(0.02, 0.98), rng.uniform(0.9, 7.0),
                        rng.uniform(0.4, 1.0), rng.uniform(0.1, 6.0) if particle else 0.0, 1.0 if particle else 0.0]
        occluders = tuple(v for _ in range(6) for v in (rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9),
                                                        rng.uniform(0.03, 0.12), 1.0))
        renderer = QuickBubbleAmbientPoints()
        gl.glUseProgram(0)    # the pass restores what it found; an earlier pass's deleted program is no state
        try:
            def run(_index=0):
                return renderer.render_texture((0.0, 0.0, float(width), float(height)), 1.0, tuple(records),
                                               sprite_scale=1.0, glow_spread=1.2,
                                               micro_color=(0.9, 0.95, 1.0, 0.8),
                                               particle_color=(0.55, 0.75, 1.0, 1.0), occluders=occluders,
                                               response_radius_scale=1.0)
            run()
            counter = {}
            with counting(counter):
                coverage, light = run()
            tw, th = renderer._target_size
            label = f"{width}x{height}"
            outputs[f"coverage_{label}"] = _read_texture(coverage, tw, th, 4)
            outputs[f"light_{label}"] = _read_level(light, tw, th, 3, 0)
            calls = calls or counter
            calls.update(_memory(label, {"coverage": coverage, "light": light}))
            calls[f"gpu_ms:{label}"] = gpu_ms(run)
        finally:
            renderer.release_resources()
    return outputs, calls


PASSES = {
    "motion_tile_max": pass_motion_tile_max,
    "population_scan": pass_population_scan,
    "edge_field": pass_edge_field,
    "propagation_field": pass_propagation_field,
    "waveform_fields": pass_waveform_fields,
    "fog_volume": pass_fog_volume,
    "heightfield": pass_heightfield,
    "waveform_slope": pass_waveform_slope,
    "defocus": pass_defocus,
    "scene_motion_blur": pass_scene_motion_blur,
    "bubble_light": pass_bubble_light,
}


# ---- paired GPU time: a git revision's owner against the working tree's, interleaved in one process ----
#
# Separate runs are not comparable on this machine: a whole process lands in one GPU clock state (the same pass
# measured 1.50 ms in one run and 0.45 ms in the next). ``paired`` loads the named modules a second time from a git
# revision (``git show <ref>:<path>``, executed as a sibling module so relative imports resolve to the live package)
# and alternates the revision's owner and the working tree's call by call on the same context.

def _module_copy(module_name: str, ref: str, copies: dict):
    import importlib
    import subprocess
    import types
    live = importlib.import_module(module_name)
    path = Path(live.__file__).resolve().relative_to(ROOT).as_posix()
    source = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout
    package, _, leaf = module_name.rpartition(".")
    copy_name = f"{package}._paired_{leaf}"
    module = types.ModuleType(copy_name)
    module.__package__, module.__file__ = package, str(ROOT / path)
    sys.modules[copy_name] = module
    exec(compile(source, f"{ref}:{path}", "exec"), module.__dict__)
    # An earlier copy's classes replace the live ones this copy imported (the revision's owners use each other).
    for name, value in list(vars(module).items()):
        owner = getattr(value, "__module__", None)
        if owner in copies and hasattr(copies[owner], name):
            setattr(module, name, getattr(copies[owner], name))
    copies[module_name] = module
    return module


def _paired_edge_field(mod, target, size):
    from rendering.quick.scene3d.resources import MeshResources
    resources, field = MeshResources("paired"), mod("rendering.quick.scene3d.edge_field").EdgeField("paired")
    photo = _photo(*size, 1)
    run = lambda index: field.texture(resources, photo, size, ("time", index), 0.04, 0.2)

    def release():
        from OpenGL import GL as gl
        gl.glDeleteTextures([photo])
        field.release()
        resources.release_resources()
    return run, release


def _paired_fog(mod, target, grid):
    from OpenGL import GL as gl
    from rendering.quick.render.gl_resources import compile_compute_program
    volume = mod("rendering.quick.scene3d.fog_volume").FogVolume("paired")
    source = mod("rendering.gl_programs.fog_volume").fog_inject_source(_FOG_MEDIUM)
    program = compile_compute_program(source, label="paired fog medium")
    medium = lambda p: (gl.glUniform4f(gl.glGetUniformLocation(p, "uSphere"), .5, .2, -9., 2.5),
                        gl.glUniform1f(gl.glGetUniformLocation(p, "uSteady"), .6))
    view = np.identity(4)
    view[:3, 3] = (-.4, -1.1, .3)
    run = lambda _i: volume.update(program, view=view, lens=(.7, .4), depth_range=(1., 60.), grid=grid,
                                   medium=medium, restore=False)

    def release():
        gl.glUseProgram(0)
        volume.release()
        gl.glDeleteProgram(program)
    return run, release


def _paired_motion(mod, target, size):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    width, height = size
    rng = np.random.default_rng(5)
    resources, blur = MeshResources("paired"), mod("rendering.quick.scene3d.motion").MotionBlur("paired")
    scene = _texture(width, height, gl.GL_RGBA8, rng.integers(0, 256, (height, width, 4)).astype(np.uint8),
                     (gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))
    velocity = _texture(width, height, gl.GL_RG16F, rng.integers(-64, 65, (height, width, 2)).astype(np.float32) / 4)
    run = lambda _i: blur.apply(scene, velocity, size, resources, target.vao)

    def release():
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glDeleteTextures([scene, velocity])
        blur.release()
        resources.release_resources()
    return run, release


def _paired_defocus(mod, target, size):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    module = mod("rendering.quick.scene3d.defocus")
    width, height = size
    target.resize(width, height)
    resources, layer = MeshResources("paired"), module.DefocusLayer("paired")
    program = resources.program("paired_defocus_scene", _QUAD_VERTEX,
                                _DEFOCUS_SCENE_FRAGMENT.format(defocus=module.SCENE_DEFOCUS_GLSL))

    def run(_i):
        target.bind(clear=(0.08, 0.1, 0.16, 1.0))
        layer.begin(width, height)
        gl.glUseProgram(program)
        gl.glUniform2f(gl.glGetUniformLocation(program, "uSize"), float(width), float(height))
        gl.glBindVertexArray(target.vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        layer.end()
        layer.composite(40.0)

    def release():
        layer.release()
        resources.release_resources()
    return run, release


def _paired_scene_motion(mod, target, size, samples):
    from types import SimpleNamespace
    from OpenGL import GL as gl
    from rendering.gl_programs.portable import pack_block
    from rendering.quick.scene3d.resources import MeshResources, bind_frame
    vertex, fragment, block = _moving_program()
    mod("rendering.quick.scene3d.motion")
    target_module = mod("rendering.quick.scene3d.target")
    width, height = size
    target.resize(width, height)
    resources, scene = MeshResources("paired"), target_module.SceneTarget("paired")
    photo = _photo(width, height, 2)
    tile = max(8, round(height / 40))
    rng = np.random.default_rng(9)
    squares = [(rng.uniform(0, width - 200), rng.uniform(0, height - 200), rng.uniform(40, 200),
                rng.uniform(-1.6, 1.6, 2) * tile, rng.uniform(0, 1, 4)) for _ in range(14)]

    def frame(left=0.0, top=0.0, w=None, h=None):
        matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0,
                  2 * left / width - 1, 1 - 2 * top / height, 0, 1)
        return SimpleNamespace(viewport=(0, 0, width, height),
                               logical_size=(float(w or width), float(h or height)),
                               matrix_values=matrix, quad_vao=target.vao)
    full = frame()

    def run(_i):
        target.bind(clear=(0.0, 0.0, 0.0, 1.0))
        with scene.scope(full, samples, resources, rect=(0, 0, width, height), motion_blur=True):
            resources.draw_image(full, photo)
            program = resources.program("paired_moving", vertex, fragment)
            uniforms = resources.uniforms("paired_moving", ())
            values = resources.values("paired_moving")
            with scene.velocity_writes():
                for left, top, side, motion, colour in squares:
                    bind_frame(program, uniforms, frame(left, top, side, side), values)
                    values["uMotion"] = tuple(motion)
                    values["uColour"] = tuple(colour)
                    with resources.pass_blocks.bound(pack_block(block, values)):
                        gl.glBindVertexArray(target.vao)
                        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release():
        gl.glDeleteTextures([photo])
        scene.release()
        resources.release_resources()
    return run, release


def _paired_bubble_light(mod, target, size):
    from OpenGL import GL as gl
    renderer = mod("rendering.quick.visualizer.implementations.bubble_ambient_gl").QuickBubbleAmbientPoints()
    rng = np.random.default_rng(3)
    records = []
    for index in range(160):
        particle = index >= 40
        records += [rng.uniform(0.02, 0.98), rng.uniform(0.02, 0.98), rng.uniform(0.9, 7.0), rng.uniform(0.4, 1.0),
                    rng.uniform(0.1, 6.0) if particle else 0.0, 1.0 if particle else 0.0]
    gl.glUseProgram(0)
    run = lambda _i: renderer.render_texture((0.0, 0.0, float(size[0]), float(size[1])), 1.0, tuple(records),
                                             sprite_scale=1.0, glow_spread=1.2, micro_color=(0.9, 0.95, 1.0, 0.8),
                                             particle_color=(0.55, 0.75, 1.0, 1.0))
    return run, renderer.release_resources


def _paired_sampled(kind):
    def factory(mod, target, size):
        from OpenGL import GL as gl
        from rendering.quick.scene3d.resources import MeshResources
        resources = MeshResources("paired")
        if kind == "heightfield":
            from rendering.gl_programs.heightfield import HEIGHTFIELD_MAX_SIZE
            field = mod("rendering.quick.scene3d.heightfield").HeightfieldTexture("paired", components=2)
            data = np.random.default_rng(1).normal(0, 1, (HEIGHTFIELD_MAX_SIZE,) * 2 + (2,)).astype(np.float32)
            texture, drop = field.ensure(HEIGHTFIELD_MAX_SIZE, data.tobytes()), field.release
        else:
            height = np.random.default_rng(1).normal(0, 1, (1024, 1024)).astype(np.float32)
            texture = mod("rendering.quick.scene3d.waveform")._slope_texture(height)
            drop = lambda: gl.glDeleteTextures([texture])
        # The consumer's fetches alone: the sampling draw into a kept RGBA32F image, no allocation or readback.
        width, height = size
        out = _texture(width, height, gl.GL_RGBA32F)
        fbo = (gl.GLuint * 1)()
        gl.glCreateFramebuffers(1, fbo)
        gl.glNamedFramebufferTexture(int(fbo[0]), gl.GL_COLOR_ATTACHMENT0, out, 0)
        program = resources.program("identity_sample_rg", _QUAD_VERTEX, _SAMPLE_RG_FRAGMENT)

        def run(_i):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, int(fbo[0]))
            gl.glViewport(0, 0, width, height)
            gl.glDisable(gl.GL_BLEND)
            gl.glUseProgram(program)
            gl.glBindTextureUnit(0, texture)
            gl.glUniform1i(gl.glGetUniformLocation(program, "uTexture"), 0)
            gl.glUniform1f(gl.glGetUniformLocation(program, "uLod"), 0.0 if kind == "heightfield" else -1.0)
            gl.glBindVertexArray(target.vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        def release():
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            gl.glDeleteFramebuffers(1, fbo)
            gl.glDeleteTextures([out])
            drop()
            resources.release_resources()
        return run, release
    return factory


PAIRED = {
    "edge_field": (("rendering.quick.scene3d.edge_field",), _paired_edge_field, ((1920, 1080),)),
    "fog_volume": (("rendering.gl_programs.fog_volume", "rendering.quick.scene3d.fog_volume"), _paired_fog,
                   ((128, 72, 128),)),
    "motion_tile_max": (("rendering.quick.scene3d.motion",), _paired_motion, ((2560, 1440), (3840, 2160))),
    "defocus": (("rendering.quick.scene3d.defocus",), _paired_defocus, ((2560, 1440), (3840, 2160))),
    "scene_motion_blur": (("rendering.quick.scene3d.motion", "rendering.quick.scene3d.target"),
                          lambda mod, target, case: _paired_scene_motion(mod, target, *case),
                          (((1920, 1080), 1), ((2560, 1440), 4), ((3840, 2160), 4))),
    "bubble_light": (("rendering.quick.visualizer.implementations.bubble_ambient_gl",), _paired_bubble_light,
                     ((1920, 1080), (3874, 1450))),
    "heightfield": (("rendering.quick.scene3d.heightfield",), _paired_sampled("heightfield"), ((2560, 1440),)),
    "waveform_slope": (("rendering.quick.scene3d.waveform",), _paired_sampled("slope"), ((2560, 1440),)),
}


def paired(out: Path, ref: str, names, rounds: int) -> int:
    """GPU time of each named owner at ``ref`` and in the working tree, alternated call by call (``rounds`` pairs
    after warm-up); medians, the median paired difference and its p10..p90 spread."""
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    out.mkdir(parents=True, exist_ok=True)
    target = OffscreenRenderTarget(64, 64, label="compute pass identity paired")
    report = {"driver": target.driver, "ref": ref, "rounds": rounds, "cases": {}}
    query = 0
    try:
        with target.current():
            query = int(np.asarray(gl.glGenQueries(1)).reshape(-1)[0])

            def timed(run, index):
                gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
                run(index)
                gl.glEndQuery(gl.GL_TIME_ELAPSED)
                value = ctypes.c_uint64(0)
                gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
                return value.value / 1e6
            for name in names:
                modules, factory, cases = PAIRED[name]
                copies: dict = {}
                for module_name in modules:
                    _module_copy(module_name, ref, copies)
                import importlib
                live = lambda m: importlib.import_module(m)
                before = lambda m, _c=copies: _c.get(m) or importlib.import_module(m)
                for case in cases:
                    gl.glUseProgram(0)
                    runs = {"before": factory(before, target, case), "after": factory(live, target, case)}
                    try:
                        for index in range(8):
                            for key in ("before", "after"):
                                runs[key][0](index)
                        gl.glFinish()
                        times = {"before": [], "after": []}
                        for index in range(rounds):
                            order = ("before", "after") if index % 2 == 0 else ("after", "before")
                            for key in order:
                                times[key].append(timed(runs[key][0], 100 + index))
                    finally:
                        for key in ("before", "after"):
                            runs[key][1]()
                        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
                    differences = np.subtract(times["after"], times["before"])
                    label = f"{name}:{case}"
                    row = {"before_ms": float(np.median(times["before"])), "after_ms": float(np.median(times["after"])),
                           "difference_ms": float(np.median(differences)),
                           "difference_p10_ms": float(np.percentile(differences, 10)),
                           "difference_p90_ms": float(np.percentile(differences, 90))}
                    report["cases"][label] = row
                    print(f"{label}: before {row['before_ms']:.4f} ms, after {row['after_ms']:.4f} ms, "
                          f"paired difference {row['difference_ms']:+.4f} ms "
                          f"(p10 {row['difference_p10_ms']:+.4f}, p90 {row['difference_p90_ms']:+.4f})", flush=True)
                for copy_name in [m.__name__ for m in copies.values()]:
                    sys.modules.pop(copy_name, None)
                target.resize(64, 64)
    finally:
        if query:
            with target.current():
                gl.glDeleteQueries(1, [query])
        target.close()
    (out / "paired.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


def record(out: Path, names) -> int:
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    out.mkdir(parents=True, exist_ok=True)
    target = OffscreenRenderTarget(64, 64, label="compute pass identity")
    from PySide6 import QtCore
    summary = {"driver": target.driver, "qt": QtCore.qVersion(), "passes": {}}
    try:
        with target.current():
            for name in names:
                outputs, measured = PASSES[name](target)
                timing = {key: value for key, value in measured.items() if key.startswith("gpu_ms")}
                memory = {key[len("memory_bytes:"):]: value for key, value in measured.items()
                          if key.startswith("memory_bytes:")}
                calls = {key: value for key, value in measured.items()
                         if key not in timing and not key.startswith("memory_bytes:")}
                np.savez_compressed(out / f"{name}.npz", **outputs)
                summary["passes"][name] = {
                    "outputs": {key: hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
                                for key, value in sorted(outputs.items())},
                    "gl_calls": sum(calls.values()), "gl_calls_by_name": dict(sorted(calls.items())),
                    "gpu_ms": timing, "memory_bytes": dict(sorted(memory.items()))}
                print(f"{name}: {len(outputs)} outputs, {sum(calls.values())} GL calls, GPU {timing}", flush=True)
    finally:
        target.close()
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


def compare(before: Path, after: Path) -> int:
    a_summary = json.loads((before / "summary.json").read_text(encoding="utf-8"))
    b_summary = json.loads((after / "summary.json").read_text(encoding="utf-8"))
    print(f"Qt {a_summary.get('qt', '?')} -> {b_summary.get('qt', '?')}; driver {a_summary['driver']}")
    a, b = a_summary["passes"], b_summary["passes"]
    for name in sorted(set(a) & set(b)):
        old, new = np.load(before / f"{name}.npz"), np.load(after / f"{name}.npz")
        for key in sorted(set(old.files) | set(new.files)):
            if key not in old.files or key not in new.files:
                print(f"{name}.{key}: missing on one side")
                continue
            x, y = old[key], new[key]
            same = x.shape == y.shape and x.dtype == y.dtype and x.tobytes() == y.tobytes()
            detail = ""
            if not same and x.shape == y.shape:
                diff = np.abs(x.astype(np.float64) - y.astype(np.float64))
                scale = np.maximum(np.abs(x.astype(np.float64)), 1e-12)
                detail = (f"  max |diff| {diff.max():.3g}, max relative {(diff / scale).max():.3g}, "
                          f"{np.count_nonzero(diff)}/{diff.size} values differ")
            elif not same:
                detail = f"  shape {x.shape} -> {y.shape}"
            print(f"{name}.{key}: {'IDENTICAL' if same else 'DIFFERENT'}{detail}")
        print(f"{name}: GL calls {a[name]['gl_calls']} -> {b[name]['gl_calls']}; GPU ms {a[name].get('gpu_ms', {})} -> "
              f"{b[name].get('gpu_ms', {})}")
        before_memory, after_memory = a[name].get("memory_bytes", {}), b[name].get("memory_bytes", {})
        for key in sorted(set(before_memory) | set(after_memory)):
            old_bytes, new_bytes = before_memory.get(key, 0), after_memory.get(key, 0)
            if old_bytes != new_bytes:
                print(f"{name}: memory {key} {old_bytes / 2**20:.3f} MB -> {new_bytes / 2**20:.3f} MB "
                      f"({(new_bytes - old_bytes) / 2**20:+.3f} MB)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    rec = commands.add_parser("record", help="run the passes and record outputs and GL calls")
    rec.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    rec.add_argument("--passes", default=",".join(PASSES), help=f"comma-separated, of: {', '.join(PASSES)}")
    cmp_ = commands.add_parser("compare", help="compare two recorded folders bit by bit")
    cmp_.add_argument("before", type=Path)
    cmp_.add_argument("after", type=Path)
    pair = commands.add_parser("paired", help="GPU time of a git revision's owners against the working tree's, "
                                              "alternated in one process")
    pair.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    pair.add_argument("--ref", default="HEAD", help="the revision to compare the working tree against")
    pair.add_argument("--passes", default=",".join(PAIRED), help=f"comma-separated, of: {', '.join(PAIRED)}")
    pair.add_argument("--rounds", type=int, default=41)
    args = parser.parse_args(argv)
    if args.command == "record":
        return record(Path(args.out), [name for name in args.passes.split(",") if name])
    if args.command == "paired":
        return paired(Path(args.out), args.ref, [name for name in args.passes.split(",") if name], args.rounds)
    return compare(args.before, args.after)


if __name__ == "__main__":
    raise SystemExit(main())

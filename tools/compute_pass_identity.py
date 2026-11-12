"""Compute pass identity (N1.2): run each converted compute pass through its real owner on fixed inputs, in a hidden
offscreen GL context, and record its outputs and the GL calls the owner made for it.

A conversion (loose uniforms into a dispatch block, explicit bindings) must leave every output bit-identical: record
the outputs before the change, again after, and compare. GL calls are counted per name for the owner call alone
(calls through ``OpenGL.GL`` in the render modules, the stream ring's raw multi-binds, and ``gl_query`` reads as
``query:<helper>``).

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


def gpu_ms(run, repeats: int = 9) -> float:
    """Median GPU time (GL_TIME_ELAPSED) of ``run()`` over ``repeats`` calls, in milliseconds."""
    from OpenGL import GL as gl
    times = []
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
    for width, height in ((97, 61), (300, 770), (1920, 1080)):
        resources, blur = MeshResources("identity"), MotionBlur("identity")
        scene = _texture(width, height, gl.GL_RGBA8)
        field = rng.integers(-64, 65, size=(height, width, 2)).astype(np.float32) / 4.0
        velocity = _texture(width, height, gl.GL_RG16F, field)
        try:
            blur.apply(scene, velocity, (width, height), resources, target.vao)   # compiles and allocates
            counter = {}
            with counting(counter):
                blur.apply(scene, velocity, (width, height), resources, target.vao)
            tiles, _fbo, tile_w, tile_h = blur._passes[0]
            outputs[f"tiles_{width}x{height}"] = _read_texture(tiles, tile_w, tile_h, 2)
            calls = calls or counter
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
            for role, internal, _linear in EdgeField._ROLES:
                channels = 2 if internal in (gl.GL_RG32F, gl.GL_RG16F) else 1
                outputs[f"{role}_{width}x{height}"] = _read_texture(field._textures[role], fw, fh, channels)
            calls = calls or counter
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
    set_cost = lambda locate: gl.glUniform1f(locate("uChannel"), 0.3)
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


PASSES = {
    "motion_tile_max": pass_motion_tile_max,
    "population_scan": pass_population_scan,
    "edge_field": pass_edge_field,
    "propagation_field": pass_propagation_field,
    "waveform_fields": pass_waveform_fields,
}


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
                calls = {key: value for key, value in measured.items() if key not in timing}
                np.savez_compressed(out / f"{name}.npz", **outputs)
                summary["passes"][name] = {
                    "outputs": {key: hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
                                for key, value in sorted(outputs.items())},
                    "gl_calls": sum(calls.values()), "gl_calls_by_name": dict(sorted(calls.items())),
                    "gpu_ms": timing}
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
            detail = "" if same else f"  max |diff| {np.abs(x.astype(np.float64) - y.astype(np.float64)).max():.3g}"
            print(f"{name}.{key}: {'IDENTICAL' if same else 'DIFFERENT'}{detail}")
        print(f"{name}: GL calls {a[name]['gl_calls']} -> {b[name]['gl_calls']}; GPU ms {a[name].get('gpu_ms', {})} -> "
              f"{b[name].get('gpu_ms', {})}")
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
    args = parser.parse_args(argv)
    if args.command == "record":
        return record(Path(args.out), [name for name in args.passes.split(",") if name])
    return compare(args.before, args.after)


if __name__ == "__main__":
    raise SystemExit(main())

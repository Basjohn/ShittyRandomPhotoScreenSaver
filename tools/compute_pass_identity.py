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


PASSES = {
    "motion_tile_max": pass_motion_tile_max,
    "population_scan": pass_population_scan,
}


def record(out: Path, names) -> int:
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    out.mkdir(parents=True, exist_ok=True)
    target = OffscreenRenderTarget(64, 64, label="compute pass identity")
    summary = {"driver": target.driver, "passes": {}}
    try:
        with target.current():
            for name in names:
                outputs, calls = PASSES[name](target)
                np.savez_compressed(out / f"{name}.npz", **outputs)
                summary["passes"][name] = {
                    "outputs": {key: hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
                                for key, value in sorted(outputs.items())},
                    "gl_calls": sum(calls.values()), "gl_calls_by_name": dict(sorted(calls.items()))}
                print(f"{name}: {len(outputs)} outputs, {sum(calls.values())} GL calls", flush=True)
    finally:
        target.close()
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


def compare(before: Path, after: Path) -> int:
    a = json.loads((before / "summary.json").read_text(encoding="utf-8"))["passes"]
    b = json.loads((after / "summary.json").read_text(encoding="utf-8"))["passes"]
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
        print(f"{name}: GL calls {a[name]['gl_calls']} -> {b[name]['gl_calls']}")
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

"""Conventions identity (N1.4): every transition and every Visualizer mode drawn through its production renderer, in
a hidden offscreen context, frame by frame: a hash of each frame's pixels and the GL calls the renderers made for it.

N1.4 routes the shaders' OpenGL assumptions (``gl_FragCoord`` as a texel or uv, the hand-written ``ndc * 0.5 + 0.5``,
the winding choice) through one include whose OpenGL values make every function an identity of today's arithmetic.
That is proved here, bitwise: record before the change, record after, compare.

- **Transitions** (``TransitionCapture``, the production transition host on an offscreen target): every showcase case
  of the release-media catalogue, plus, for each transition whose Settings page has Motion Blur or Motion Trails, the
  same run with both on (the motion-blur gather and the trail edges are drawn only then). ``FRAMES`` progress points in
  order on one run (trails and motion read the frames before).
- **Visualizer modes** (``owner_render_parity.drawn_run``: the production owner in process, its presentations drawn
  by the production ``DisplayScene.qml`` into a hidden texture): every registered mode at variant ``a``'s non-default
  settings, through its script (play, pause, park, the switch to its partner mode).

Every scene target is opened single-sampled for the run (``single_sample_scene_targets``): a multisampled target is
not bit-reproducible draw to draw on this GPU (``owner_render_parity``'s measurement), a single-sampled one is. Each
item records its frame hashes, its GL calls per frame (the render modules' ``OpenGL.GL`` calls, counted as
``compute_pass_identity.counting`` counts them) and one PNG still from the middle of the run.

    python tools/conventions_identity.py record --out .artifacts/evidence/native_core/<topic>/<YYYYMMDD>_<label>
        [--part transitions|modes|all] [--only NAME ...]
    python tools/conventions_identity.py compare <before folder> <after folder>

No window: offscreen targets and the hidden Quick host. Writes only into the evidence layout.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import pkgutil
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths, evidence_media  # noqa: E402

TRANSITION_SIZE = (640, 360)
FRAMES = 12          # progress points per transition run, 0 to 1 in order


def _import_render_modules() -> None:
    """Every ``rendering`` module imported before counting starts (counting swaps the ``gl`` of loaded modules)."""
    import importlib

    import rendering
    for info in pkgutil.walk_packages(rendering.__path__, "rendering."):
        with contextlib.suppress(Exception):
            importlib.import_module(info.name)


def _frame_calls(counter: dict) -> int:
    return sum(counter.values())


def _check_conventions_binding(tally: dict) -> None:
    """After a drawn frame (its context current): while the context holds a conventions buffer, its reserved point
    still names it (Qt Quick's own drawing in between never takes it)."""
    import ctypes

    from OpenGL import GL as gl
    from PySide6.QtGui import QOpenGLContext

    from rendering.gl_programs.conventions import SCENE3D_CONVENTIONS_BLOCK_BINDING
    from rendering.quick.render import gl_resources

    context = QOpenGLContext.currentContext()
    entry = gl_resources._conventions.get(id(context)) if context is not None else None
    if entry is None:
        return
    value = (ctypes.c_int * 1)()
    gl.glGetIntegeri_v(gl.GL_UNIFORM_BUFFER_BINDING, SCENE3D_CONVENTIONS_BLOCK_BINDING, value)
    tally["held" if int(value[0]) == entry[0] else "lost"] += 1


def transition_cases():
    """(name, identity, settings, duration_ms): the showcase cases, and a motion variant where the page has one."""
    from rendering.transition_registry import get_transition_descriptor
    from rendering.transition_settings import transition_settings
    from tools.release_media import catalogue

    cases, seen = [], set()
    for case in catalogue():
        if case.kind != "transition":
            continue
        cases.append((f"{case.identity}/{case.variant}", case.identity, case.settings or {}, case.duration_ms))
        if case.identity in seen:
            continue
        seen.add(case.identity)
        descriptor = get_transition_descriptor(case.identity)
        spec = transition_settings(descriptor.setting_name) if descriptor is not None else None
        fields = set(spec.fields()) if spec is not None else set()
        motion = {name: "On" for name in ("motion_blur", "motion_trails", "bloom") if name in fields}
        if motion:
            settings = dict(case.settings or {})
            settings[spec.section] = {**settings.get(spec.section, {}), **motion}
            cases.append((f"{case.identity}/motion", case.identity, settings, case.duration_ms))
    return cases


def record_transitions(out: Path, only, summary: dict) -> None:
    import numpy as np

    from tools.compute_pass_identity import counting
    from tools.transition_contact_sheet import TransitionCapture
    from tools.visualizer_replay.owner_render_parity import single_sample_scene_targets

    capture = TransitionCapture(*TRANSITION_SIZE)
    try:
        for name, identity, settings, duration_ms in transition_cases():
            if only and name not in only and identity not in only:
                continue
            run = capture.production_run(identity, duration_ms, settings, seed=713)
            hashes, calls = [], []
            still = None
            counter: dict = {}
            binding = {"held": 0, "lost": 0}
            with single_sample_scene_targets(), counting(counter):
                for index in range(FRAMES):
                    before = _frame_calls(counter)
                    image, _ms = capture.render(run, index / (FRAMES - 1))
                    calls.append(_frame_calls(counter) - before)
                    with capture._target.current():
                        _check_conventions_binding(binding)
                    pixels = np.asarray(image)
                    hashes.append(hashlib.sha256(pixels.tobytes()).hexdigest())
                    if index == FRAMES // 2:
                        still = image
            capture.host.park()
            key = f"transition:{name}"
            summary["items"][key] = {"hashes": hashes, "gl_calls": calls,
                                     "gl_calls_by_name": dict(sorted(counter.items())), "conventions_binding": binding}
            if still is not None:
                still.convert("RGB").save(out / f"transition_{name.replace('/', '_')}.png")
            print(f"{key}: {len(set(hashes))} distinct of {len(hashes)} frames, GL calls/frame {calls}", flush=True)
    finally:
        capture.close()


def record_modes(out: Path, only, summary: dict) -> None:
    import zlib

    import numpy as np
    from PIL import Image

    import tools.expanded_visualizer_evidence as evidence
    from tools.compute_pass_identity import counting
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    clip = evidence.shipped_clip(5.5)
    for mode in gate.modes():
        if only and mode not in only:
            continue
        engine_worker_link.reset_run_state_for_testing()
        script = parity.parity_script(clip.frames, mode)
        counter: dict = {}
        calls: list[int] = []
        binding = {"held": 0, "lost": 0}

        class CountedMirror(parity.SceneMirror):
            def frame(self, index):
                before = _frame_calls(counter)
                record = super().frame(index)
                calls.append(_frame_calls(counter) - before)
                _check_conventions_binding(binding)
                return record

        mirror = CountedMirror()
        with parity.single_sample_scene_targets(), counting(counter):
            report = gate.identity_run(mode, script, worker=False, supervisor=None, namespace=None,
                                       settings=parity.section_settings(mode, "a"), scene_mirror=mirror)
        hashes = [record["hash"] for record in report["pixels"]]
        middle = len(mirror.frames) // 2
        if mirror.frames:
            shape, data = mirror.frames[middle]
            pixels = np.frombuffer(zlib.decompress(data), dtype=np.uint8).reshape(shape)
            Image.fromarray(pixels[..., :3], "RGB").save(out / f"mode_{mode}.png")
        key = f"mode:{mode}"
        summary["items"][key] = {"hashes": hashes, "gl_calls": calls, "final_mode": report.get("final_mode"),
                                 "gl_calls_by_name": dict(sorted(counter.items())),
                                 "conventions_binding": binding}
        if binding["lost"]:
            print(f"{key}: the conventions block's binding was lost on {binding['lost']} frames", flush=True)
        print(f"{key}: {len(set(hashes))} distinct of {len(hashes)} frames, GL calls total {sum(calls)}", flush=True)


def record(out: Path, part: str, only) -> int:
    out.mkdir(parents=True, exist_ok=True)
    from rendering.quick.bootstrap import configure_quick_graphics

    configure_quick_graphics(reason="conventions-identity")
    from PySide6 import QtCore
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["conventions-identity"])
    _import_render_modules()
    summary: dict = {"qt": QtCore.qVersion(), "part": part, "items": {}}
    started = time.perf_counter()
    try:
        if part in ("transitions", "all"):
            record_transitions(out, only, summary)
        if part in ("modes", "all"):
            record_modes(out, only, summary)
    finally:
        summary["elapsed_s"] = round(time.perf_counter() - started, 1)
        (out / f"summary_{part}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    del app
    return 0


# ---- program pairs: a revision's fragment shader and the working tree's, on the same inputs, in one process ----------
#
# Multisampled targets are not bit-reproducible draw to draw, so the programs only a multisampled scene draws (the
# resolves, the per-sample OIT composite, the multisampled background capture and shaft downsample) cannot be proved
# by recorded frames; nor can programs no product path draws in these runs (the fog march, a tools-only owner).
# ``pairs`` proves every changed fragment source directly: the revision's text and the working tree's, each compiled
# through the production compile path, drawn over the same generated inputs (interpolated varyings, random textures
# of every sampler kind the pair reads, multisampled ones with a distinct value per sample, fixed uniform values),
# into float targets, compared bit for bit. Control: the working tree's program drawn again with the conventions
# block's flip on must change its output wherever it reads ``gl_FragCoord`` through the include (the block is live).

PAIR_SIZE = (96, 64)
PAIR_SAMPLES = 4
_DUMP_SCRIPT = """import json, sys
sys.path.insert(0, sys.argv[1])
from tools.vulkan_shader_readiness import discover
sources, _ = discover()
json.dump({s.key: [s.stage, s.text] for s in sources}, open(sys.argv[2], "w", encoding="utf-8"))
"""


def revision_sources(ref: str, scratch: Path) -> dict:
    """{key: (stage, text)} of every shader source the readiness check discovers at ``ref`` (an extracted tree)."""
    import shutil
    import subprocess
    import zipfile

    archive = scratch / "tree.zip"
    packages = sorted(path.parent.name for path in ROOT.glob("*/__init__.py") if path.parent.name != "tests")
    subprocess.run(["git", "archive", "--format=zip", "-o", str(archive), ref, *packages, "tools"], cwd=ROOT,
                   check=True)
    tree = scratch / "tree"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(tree)
    for name in ("assets.rcc", "onboarding_assets.rcc"):
        if (ROOT / "ui" / "resources" / name).exists():
            shutil.copy2(ROOT / "ui" / "resources" / name, tree / "ui" / "resources" / name)
    script, output = scratch / "dump_sources.py", scratch / "sources.json"
    script.write_text(_DUMP_SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, str(script), str(tree), str(output)], cwd=tree, check=True, timeout=600)
    return {key: tuple(value) for key, value in json.loads(output.read_text(encoding="utf-8")).items()}


def _seed(name: str) -> int:
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)


_IN = re.compile(r"^\s*(layout\s*\([^)]*\)\s*)?((?:flat|smooth|noperspective|centroid)\s+)*in\s+(\w+)\s+(\w+)\s*"
                 r"(?:\[\s*(\d+)\s*\])?\s*;", re.M)
_OUT = re.compile(r"^\s*(?:layout\s*\(\s*location\s*=\s*(\d+)\s*\)\s*)?out\s+(\w+)\s+(\w+)\s*;", re.M)


def pair_vertex_source(fragment: str) -> str:
    """A fullscreen triangle writing every varying ``fragment`` reads, each a different smooth function of position."""
    lines, assigns = [], []
    for index, match in enumerate(_IN.finditer(re.sub(r"//[^\n]*", "", fragment))):
        layout, qualifiers, kind, name = match.group(1) or "", match.group(2) or "", match.group(3), match.group(4)
        count = int(match.group(5)) if match.group(5) else 0
        integer = kind.startswith(("i", "u")) and not kind.startswith("int") or kind in ("int", "uint")
        flat = "flat " if integer or "flat" in qualifiers else ""
        lines.append(f"{layout}{flat}out {kind} {name}{f'[{count}]' if count else ''};")
        width = int(kind[-1]) if kind[-1].isdigit() else 1
        for element in range(max(count, 1)):
            salt = index + 3 * element
            if integer:
                base = "uint" if kind.startswith("u") else "int"
                value = f"{kind}({', '.join([f'{base}({salt + k + 1})' for k in range(width)])})"
            else:
                parts = [f"fract(p.x * {0.37 + 0.11 * (salt + k):.4f} + p.y * {0.61 - 0.07 * k:.4f} + {0.13 * k:.4f})"
                         for k in range(width)]
                value = f"{kind}({', '.join(parts)})" if width > 1 else parts[0]
            assigns.append(f"    {name}{f'[{element}]' if count else ''} = {value};")
    return ("#version 460 core\n" + "\n".join(lines) + "\nvoid main() {\n"
            "    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));\n"
            + "\n".join(assigns) + "\n    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n}\n")


_FILL_MS_FRAGMENT = """#version 460 core
layout(location = 0) out vec4 Colour;
uniform uint uSeed;
uint mixBits(uint v) { v ^= v >> 16; v *= 0x7feb352du; v ^= v >> 15; v *= 0x846ca68bu; v ^= v >> 16; return v; }
float unit(uint v) { return float(mixBits(v) & 0xffffffu) / 16777216.0; }
void main() {
    uint base = uint(gl_FragCoord.x) * 73856093u ^ uint(gl_FragCoord.y) * 19349663u ^ uint(gl_SampleID) * 83492791u
                ^ uSeed;
    Colour = vec4(unit(base), unit(base + 1u), unit(base + 2u), unit(base + 3u));
}
"""
_FILL_MS_VERTEX = """#version 460 core
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""


class _PairInputs:
    """Textures per sampler name (the same for both programs of a pair), made once per name and kind."""

    def __init__(self, vao: int) -> None:
        self._textures: dict[tuple[str, int], int] = {}
        self._fill = 0
        self._vao = vao

    def texture(self, name: str, kind: int) -> tuple[int, int] | None:
        import ctypes

        import numpy as np
        from OpenGL import GL as gl

        key = (name, kind)
        if key in self._textures:
            return self._textures[key]
        rng = np.random.default_rng(_seed(name))
        width, height = PAIR_SIZE
        handle = (ctypes.c_uint * 1)()
        if kind in (gl.GL_SAMPLER_2D, gl.GL_INT_SAMPLER_2D, gl.GL_UNSIGNED_INT_SAMPLER_2D):
            target = gl.GL_TEXTURE_2D
            gl.glCreateTextures(target, 1, handle)
            texture = int(handle[0])
            levels = max(width, height).bit_length()
            gl.glTextureStorage2D(texture, levels, gl.GL_RGBA32F, width, height)
            for level in range(levels):
                w, h = max(width >> level, 1), max(height >> level, 1)
                data = rng.random((h, w, 4), dtype=np.float32)
                gl.glTextureSubImage2D(texture, level, 0, 0, w, h, gl.GL_RGBA, gl.GL_FLOAT, data)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        elif kind == gl.GL_SAMPLER_3D:
            target = gl.GL_TEXTURE_3D
            gl.glCreateTextures(target, 1, handle)
            texture = int(handle[0])
            gl.glTextureStorage3D(texture, 1, gl.GL_RGBA32F, 16, 16, 16)
            data = rng.random((16, 16, 16, 4), dtype=np.float32)
            gl.glTextureSubImage3D(texture, 0, 0, 0, 0, 16, 16, 16, gl.GL_RGBA, gl.GL_FLOAT, data)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        elif kind == gl.GL_SAMPLER_CUBE:
            target = gl.GL_TEXTURE_CUBE_MAP
            gl.glCreateTextures(target, 1, handle)
            texture = int(handle[0])
            levels = 5
            gl.glTextureStorage2D(texture, levels, gl.GL_RGBA32F, 16, 16)
            for level in range(levels):
                side = max(16 >> level, 1)
                data = rng.random((6, side, side, 4), dtype=np.float32)
                gl.glTextureSubImage3D(texture, level, 0, 0, 0, side, side, 6, gl.GL_RGBA, gl.GL_FLOAT, data)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        elif kind == gl.GL_SAMPLER_2D_MULTISAMPLE:
            target = gl.GL_TEXTURE_2D_MULTISAMPLE
            gl.glCreateTextures(target, 1, handle)
            texture = int(handle[0])
            gl.glTextureStorage2DMultisample(texture, PAIR_SAMPLES, gl.GL_RGBA32F, width, height, gl.GL_TRUE)
            self._fill_samples(texture, _seed(name))
        else:
            return None
        self._textures[key] = (target, texture)
        return self._textures[key]

    def _fill_samples(self, texture: int, seed: int) -> None:
        import ctypes

        from OpenGL import GL as gl
        from rendering.quick.render.gl_resources import compile_program

        if not self._fill:
            self._fill = compile_program(_FILL_MS_VERTEX, _FILL_MS_FRAGMENT, label="pair multisample fill")
        handle = (ctypes.c_uint * 1)()
        gl.glCreateFramebuffers(1, handle)
        fbo = int(handle[0])
        gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0, texture, 0)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, *PAIR_SIZE)
        gl.glEnable(gl.GL_MULTISAMPLE)
        gl.glEnable(gl.GL_SAMPLE_SHADING)
        gl.glMinSampleShading(1.0)
        gl.glUseProgram(self._fill)
        gl.glUniform1ui(gl.glGetUniformLocation(self._fill, "uSeed"), seed & 0xFFFFFFFF)
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glDisable(gl.GL_SAMPLE_SHADING)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])

    def release(self) -> None:
        from OpenGL import GL as gl
        from rendering.quick.render.gl_resources import delete_program

        for _target, texture in self._textures.values():
            gl.glDeleteTextures(1, [texture])
        self._textures.clear()
        if self._fill:
            delete_program(self._fill)
            self._fill = 0


def _set_uniforms(program: int, inputs: _PairInputs, integer: int = 1) -> str | None:
    """Every default-block uniform of ``program`` set from its name (textures bound to units in name order); a
    reason when a sampler kind has no generated input."""
    import ctypes

    from OpenGL import GL as gl

    count = int(gl.glGetProgramiv(program, gl.GL_ACTIVE_UNIFORMS))
    found = []
    for index in range(count):
        name, size, kind = gl.glGetActiveUniform(program, index)
        name = name.decode() if isinstance(name, bytes) else str(name)
        block = (ctypes.c_int * 1)()
        gl.glGetActiveUniformsiv(program, 1, (ctypes.c_uint * 1)(index), gl.GL_UNIFORM_BLOCK_INDEX, block)
        if block[0] != -1:
            continue
        found.append((name, int(size), int(kind)))
    unit = 0
    for name, size, kind in sorted(found):
        base = name.split("[")[0]
        for element in range(size):
            label = f"{base}[{element}]" if size > 1 else name
            location = int(gl.glGetUniformLocation(program, label))
            if location < 0:
                continue
            h = _seed(label)
            value = [0.25 + 4.0 * (((h >> (8 * k)) & 0xFF) / 255.0) for k in range(16)]
            if kind in (gl.GL_SAMPLER_2D, gl.GL_SAMPLER_3D, gl.GL_SAMPLER_2D_MULTISAMPLE, gl.GL_INT_SAMPLER_2D,
                        gl.GL_UNSIGNED_INT_SAMPLER_2D, gl.GL_SAMPLER_CUBE, gl.GL_SAMPLER_2D_SHADOW,
                        gl.GL_SAMPLER_2D_ARRAY):
                made = inputs.texture(base, kind)
                if made is None:
                    return f"sampler {name} of kind {kind} has no generated input"
                target, texture = made
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(target, texture)
                try:
                    gl.glUniform1i(location, unit)
                except gl.GLError as error:
                    raise RuntimeError(f"sampler {label} (type {kind:#x}) at {location}: {error}") from None
                unit += 1
            elif kind == gl.GL_FLOAT:
                gl.glUniform1f(location, value[0])
            elif kind == gl.GL_FLOAT_VEC2:
                gl.glUniform2f(location, *value[:2])
            elif kind == gl.GL_FLOAT_VEC3:
                gl.glUniform3f(location, *value[:3])
            elif kind == gl.GL_FLOAT_VEC4:
                gl.glUniform4f(location, *value[:4])
            elif kind == gl.GL_FLOAT_MAT3:
                gl.glUniformMatrix3fv(location, 1, gl.GL_FALSE, (ctypes.c_float * 9)(*value[:9]))
            elif kind == gl.GL_FLOAT_MAT4:
                gl.glUniformMatrix4fv(location, 1, gl.GL_FALSE, (ctypes.c_float * 16)(*value[:16]))
            elif kind in (gl.GL_INT, gl.GL_BOOL, gl.GL_UNSIGNED_INT):
                number = PAIR_SAMPLES if base.endswith("Samples") else integer
                (gl.glUniform1ui if kind == gl.GL_UNSIGNED_INT else gl.glUniform1i)(location, number)
            elif kind in (gl.GL_INT_VEC2, gl.GL_UNSIGNED_INT_VEC2):
                size2 = PAIR_SIZE if "Size" in base or "Extent" in base else (1, 1)
                (gl.glUniform2ui if kind == gl.GL_UNSIGNED_INT_VEC2 else gl.glUniform2i)(location, *size2)
            elif kind in (gl.GL_INT_VEC4,):
                gl.glUniform4i(location, 0, 0, *PAIR_SIZE)
            else:
                return f"uniform {name} of type {kind} has no generated value"
    return None


def _draw_pair_program(vertex: str, fragment: str, inputs: _PairInputs, vao: int, *, flip: bool = False,
                       integer: int = 1):
    """The program's outputs (every colour location it writes) over the generated inputs, as float32 arrays."""
    import ctypes

    import numpy as np
    from OpenGL import GL as gl
    from rendering.gl_programs.conventions import SCENE3D_CONVENTIONS_BLOCK_BINDING, conventions_block
    from rendering.quick.render.gl_resources import compile_program, delete_program

    try:
        program = compile_program(vertex, fragment, label="conventions pair")
    except RuntimeError as error:
        return None, f"the generated pair does not link: {str(error).splitlines()[-1][:160]}"
    # Inputs first: filling a multisampled input draws, with its own program and framebuffer.
    for index in range(int(gl.glGetProgramiv(program, gl.GL_ACTIVE_UNIFORMS))):
        name, _size, kind = gl.glGetActiveUniform(program, index)
        name = (name.decode() if isinstance(name, bytes) else str(name)).split("[")[0]
        if int(kind) in (gl.GL_SAMPLER_2D, gl.GL_SAMPLER_3D, gl.GL_SAMPLER_2D_MULTISAMPLE, gl.GL_SAMPLER_CUBE):
            inputs.texture(name, int(kind))
    outputs = sorted({int(m.group(1) or 0) for m in _OUT.finditer(fragment)} or {0})
    width, height = PAIR_SIZE
    handle = (ctypes.c_uint * 1)()
    gl.glCreateFramebuffers(1, handle)
    fbo = int(handle[0])
    textures = []
    for location in range(max(outputs) + 1):
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, handle)
        texture = int(handle[0])
        gl.glTextureStorage2D(texture, 1, gl.GL_RGBA32F, width, height)
        gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0 + location, texture, 0)
        textures.append(texture)
    gl.glNamedFramebufferDrawBuffers(fbo, len(textures), [gl.GL_COLOR_ATTACHMENT0 + i for i in range(len(textures))])
    previous_block = (ctypes.c_int * 1)()
    flipped = 0
    try:
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, width, height)
        for location in range(len(textures)):
            gl.glClearBufferfv(gl.GL_COLOR, location, (0.125, 0.25, 0.375, 0.5))
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(program)
        reason = _set_uniforms(program, inputs, integer)
        if reason:
            return None, reason
        if flip:
            gl.glGetIntegeri_v(gl.GL_UNIFORM_BUFFER_BINDING, SCENE3D_CONVENTIONS_BLOCK_BINDING, previous_block)
            gl.glCreateBuffers(1, handle)
            flipped = int(handle[0])
            data = conventions_block((1.0, 0.0, 0.0, 0.0))
            gl.glNamedBufferStorage(flipped, len(data), data, 0)
            gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_CONVENTIONS_BLOCK_BINDING, flipped)
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        result = {}
        for location, texture in enumerate(textures):
            data = np.empty((height, width, 4), dtype=np.float32)
            gl.glGetTextureImage(texture, 0, gl.GL_RGBA, gl.GL_FLOAT, data.nbytes, data)
            result[location] = data
        if gl.glGetError() != gl.GL_NO_ERROR:
            return None, "GL error while drawing"
        return result, None
    finally:
        if flipped:
            gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_CONVENTIONS_BLOCK_BINDING, int(previous_block[0]))
            gl.glDeleteBuffers(1, [flipped])
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures(len(textures), textures)
        delete_program(program)


def pairs(out: Path, ref: str) -> int:
    """Every fragment source whose text differs between ``ref`` and the working tree, drawn both ways."""
    import ctypes

    import numpy as np
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from tools.vulkan_shader_readiness import discover

    out.mkdir(parents=True, exist_ok=True)
    with artifact_paths.scratch("conventions_identity") as scratch:
        old = revision_sources(ref, scratch)
    new = {source.key: (source.stage, source.text) for source in discover()[0]}
    changed = sorted(key for key in set(old) & set(new) if old[key][1] != new[key][1])
    report = {"ref": ref, "pairs": {}, "changed_not_fragment": [], "only_in_one": sorted(set(old) ^ set(new))}
    target = OffscreenRenderTarget(16, 16, label="conventions pairs")
    try:
        with target.current():
            handle = (ctypes.c_uint * 1)()
            gl.glCreateVertexArrays(1, handle)
            vao = int(handle[0])
            inputs = _PairInputs(vao)
            try:
                for key in changed:
                    stage = new[key][0]
                    if stage != "frag":
                        report["changed_not_fragment"].append(key)
                        continue
                    before_text, after_text = old[key][1], new[key][1]
                    vertex = pair_vertex_source(after_text)
                    entry, reason = {"identical": True, "flip_changes_output": False,
                                     "distinct_output_values": [], "outputs": 0}, None
                    # Integer uniforms (switches, modes, counts) at 0 and at 1: two paths through each program.
                    for integer in (0, 1):
                        before, reason_a = _draw_pair_program(pair_vertex_source(before_text), before_text, inputs,
                                                              vao, integer=integer)
                        after, reason_b = _draw_pair_program(vertex, after_text, inputs, vao, integer=integer)
                        flipped, reason_c = _draw_pair_program(vertex, after_text, inputs, vao, flip=True,
                                                               integer=integer)
                        reason = reason_a or reason_b or reason_c
                        if reason:
                            break
                        entry["identical"] &= set(before) == set(after) and all(
                            before[k].tobytes() == after[k].tobytes() for k in before)
                        entry["flip_changes_output"] |= any(after[k].tobytes() != flipped[k].tobytes() for k in after)
                        entry["distinct_output_values"].append(
                            int(sum(len(np.unique(after[k].view(np.uint32))) for k in after)))
                        entry["outputs"] = len(after)
                    if reason:
                        report["pairs"][key] = {"skipped": reason}
                        print(f"{key}: SKIPPED ({reason})", flush=True)
                        continue
                    report["pairs"][key] = entry
                    print(f"{key}: {'IDENTICAL' if entry['identical'] else 'DIFFERENT'}; flip changes output: "
                          f"{entry['flip_changes_output']}; distinct output values (integers 0, 1) "
                          f"{entry['distinct_output_values']} over {entry['outputs']} outputs", flush=True)
            finally:
                inputs.release()
                gl.glDeleteVertexArrays(1, [vao])
    finally:
        target.close()
    judged = [entry for entry in report["pairs"].values() if "identical" in entry]
    report["all_identical"] = bool(judged) and all(entry["identical"] for entry in judged)
    (out / "pairs.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"{sum(e['identical'] for e in judged)}/{len(judged)} changed fragment sources identical; "
          f"{len(report['pairs']) - len(judged)} skipped; changed non-fragment: {report['changed_not_fragment']}")
    return 0


def _median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else 0


def compare(before: Path, after: Path) -> int:
    """Each item's frames bit for bit, and its GL calls per frame (median and total)."""
    def load(folder):
        items = {}
        for path in sorted(folder.glob("summary_*.json")):
            items.update(json.loads(path.read_text(encoding="utf-8"))["items"])
        return items

    a, b = load(before), load(after)
    identical = True
    for key in sorted(set(a) | set(b)):
        if key not in a or key not in b:
            print(f"{key}: only {'before' if key in a else 'after'}")
            identical = False
            continue
        x, y = a[key], b[key]
        differing = [i for i, (p, q) in enumerate(zip(x["hashes"], y["hashes"])) if p != q]
        same = not differing and len(x["hashes"]) == len(y["hashes"])
        identical &= same
        calls = (f"GL calls/frame median {_median(x['gl_calls'])} -> {_median(y['gl_calls'])}, "
                 f"total {sum(x['gl_calls'])} -> {sum(y['gl_calls'])}")
        changed = {name: (x["gl_calls_by_name"].get(name, 0), y["gl_calls_by_name"].get(name, 0))
                   for name in set(x["gl_calls_by_name"]) | set(y["gl_calls_by_name"])
                   if x["gl_calls_by_name"].get(name, 0) != y["gl_calls_by_name"].get(name, 0)}
        held = y.get("conventions_binding")
        if held and held["lost"]:
            identical = False
        binding = f"; conventions binding held {held['held']}/lost {held['lost']} frames" if held else ""
        print(f"{key}: {'IDENTICAL' if same else f'DIFFERENT at frames {differing[:8]}'} "
              f"({len(x['hashes'])} frames); {calls}{binding}{'; by name ' + json.dumps(changed) if changed else ''}")
    print("ALL IDENTICAL" if identical else "DIFFERENCES FOUND")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    rec = commands.add_parser("record", help="draw every transition and mode; record frame hashes and GL calls")
    rec.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    rec.add_argument("--part", choices=("transitions", "modes", "all"), default="all")
    rec.add_argument("--only", nargs="*", default=(), help="transition identities, case names or mode ids")
    cmp_ = commands.add_parser("compare", help="compare two recorded folders frame by frame")
    cmp_.add_argument("before", type=Path)
    cmp_.add_argument("after", type=Path)
    pair = commands.add_parser("pairs", help="each changed fragment source drawn at a revision and in the working "
                                             "tree over the same inputs, compared bit for bit")
    pair.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    pair.add_argument("--ref", default="HEAD")
    args = parser.parse_args(argv)
    if args.command == "compare":
        return compare(args.before, args.after)
    # Stills (PNG) and reports are written into owner scratch and published to --out when the run succeeds.
    evidence_media.redirect_output(args, "out", "conventions_identity")
    try:
        if args.command == "record":
            code = record(Path(args.out), args.part, set(args.only))
        else:
            code = pairs(Path(args.out), args.ref)
    except BaseException:
        evidence_media.finish(1)
        raise
    evidence_media.finish(0)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

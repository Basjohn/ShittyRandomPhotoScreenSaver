"""Waveform Ribbon's shader files are the Python renderer's texts (N5.4; ``rendering.gl_programs.waveform_shader_files``),
and each variant renames only its members: it compiles, and every member sits at the base text's offset (the Python
renderer packs by those)."""
from __future__ import annotations

from pathlib import Path

import pytest

#: Each pass program the native port draws: (vertex file, fragment file) or (compute file,).
PROGRAMS = (
    ("waveform_ribbon.vert", "waveform_ribbon_body.frag"),
    ("waveform_ribbon.vert", "waveform_ribbon_light.frag"),
    ("waveform_ribbon_mirror.vert", "waveform_ribbon_light_mirror.frag"),
    ("waveform_strays.vert", "waveform_strays.frag"),
    ("waveform_strays_mirror.vert", "waveform_strays_mirror.frag"),
    ("waveform_bursts.vert", "waveform_bursts.frag"),
    ("waveform_bursts_mirror.vert", "waveform_bursts_mirror.frag"),
    ("waveform_floor.vert", "waveform_floor.frag"),
    ("waveform_floor_prepass.vert", "waveform_floor_prepass.frag"),
    ("waveform_sky.vert", "waveform_sky.frag"),
    ("waveform_sky_mirror.vert", "waveform_sky_mirror.frag"),
    ("waveform_field.comp",),
    ("waveform_medium.comp",),
    ("waveform_medium_mirror.comp",),
    ("waveform_fog_integrate.comp",),
    ("waveform_fog_integrate_mirror.comp",),
    ("waveform_give_section.comp",),
    ("waveform_give_blur.comp",),
)


def _folder() -> Path:
    from widgets.spotify_visualizer import shaders

    return Path(shaders.__file__).resolve().parent


def test_every_file_is_its_python_text(monkeypatch):
    import tools.waveform_shader_files as tool
    from rendering.gl_programs import waveform_shader_files as files

    assert tool.differences() == []
    names = set(files.waveform_shader_files())
    assert {name for program in PROGRAMS for name in program} <= names
    # The base variant composes back to the Python renderer's own text (its comment line aside).
    from widgets.spotify_visualizer.shaders import compose_shader_source

    for wrapper, body, variant in files.PASS_FILES:
        if variant:
            continue
        composed = compose_shader_source(_folder() / wrapper).split("\n")
        assert composed[1].startswith("// Waveform Ribbon"), wrapper
        assert "\n".join([composed[0], *composed[2:]]) == files._bodies()[body], wrapper
    # Negative control: a text that moved is reported.
    original = files._bodies

    def moved():
        bodies = original()
        bodies["waveform_floor_fragment"] = bodies["waveform_floor_fragment"].replace("0.6,-0.8", "0.6,-0.7", 1)
        return bodies
    monkeypatch.setattr(files, "_bodies", moved)
    assert tool.differences() == ["waveform_floor_fragment.glsl"]


def _offsets(program: int) -> dict[str, int]:
    """Every block member's byte offset in ``program`` by its name."""
    from OpenGL import GL as gl

    import ctypes

    count = int(gl.glGetProgramiv(program, gl.GL_ACTIVE_UNIFORMS))
    found = {}
    for index in range(count):
        name = gl.glGetActiveUniform(program, index)[0]
        name = name.decode() if isinstance(name, bytes) else str(name)
        indices = (gl.GLuint * 1)(index)
        block, offset = (gl.GLint * 1)(), (gl.GLint * 1)()
        gl.glGetActiveUniformsiv(program, 1, indices, gl.GL_UNIFORM_BLOCK_INDEX, ctypes.cast(block, ctypes.POINTER(gl.GLint)))
        gl.glGetActiveUniformsiv(program, 1, indices, gl.GL_UNIFORM_OFFSET, ctypes.cast(offset, ctypes.POINTER(gl.GLint)))
        if block[0] >= 0:
            found[name.rstrip("\x00").split("[")[0]] = int(offset[0])
    return found


@pytest.mark.qt
def test_every_pass_program_compiles_and_its_renames_keep_the_offsets(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking

    disable_per_call_gl_error_checking()
    from rendering.gl_programs.waveform_shader_files import VARIANTS
    from rendering.quick.render.gl_resources import compile_compute_program, compile_program, delete_program
    from tools.labs.render_target import OffscreenRenderTarget
    from widgets.spotify_visualizer.shaders import compose_shader_source

    target = OffscreenRenderTarget(16, 16)
    offsets = {}
    try:
        with target.current():
            for program_files in PROGRAMS:
                texts = [compose_shader_source(_folder() / name) for name in program_files]
                program = (compile_program(*texts, label=program_files[0]) if len(texts) == 2
                           else compile_compute_program(texts[0], label=program_files[0]))
                offsets[program_files] = _offsets(program)
                delete_program(program)
    finally:
        target.close()
    inverse = {variant: {new: old for old, new in renames.items()} for variant, renames in VARIANTS.items()}
    pairs = {("waveform_ribbon_mirror.vert", "waveform_ribbon_light_mirror.frag"):
             ("waveform_ribbon.vert", "waveform_ribbon_light.frag")}
    for program_files in PROGRAMS:
        stem = program_files[0].rsplit(".", 1)[0]
        variant = next((v for v in ("_mirror", "_prepass") if stem.endswith(v)), "")
        if not variant:
            continue
        base = pairs.get(program_files) or tuple(name.replace(variant, "") for name in program_files)
        renamed = {inverse[variant].get(name, name): offset for name, offset in offsets[program_files].items()}
        assert renamed == offsets[base], program_files
        assert any(name in inverse[variant] for name in offsets[program_files]), program_files
    assert offsets[("waveform_ribbon.vert", "waveform_ribbon_light.frag")]

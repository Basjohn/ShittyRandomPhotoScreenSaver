"""Waveform Ribbon's shader files are the Python renderer's texts (N5.4; ``rendering.gl_programs.waveform_shader_files``),
and each pass file renames only its block's members: it compiles, and every member sits at the Python text's offset
(the Python renderer packs by those)."""
from __future__ import annotations

from pathlib import Path

import pytest

#: Each pass program the native port draws: (vertex file, fragment file) or (compute file,).
PROGRAMS = (
    ("waveform_ribbon.vert", "waveform_ribbon_body.frag"),
    ("waveform_ribbon.vert", "waveform_ribbon_body_sorted.frag"),
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
    # Every pass file composes back to the Python renderer's own text once its member names are put back.
    from widgets.spotify_visualizer.shaders import compose_shader_source

    for wrapper, body, pass_id in files.PASS_FILES:
        lines = compose_shader_source(_folder() / wrapper).split("\n")
        defines = [line for line in lines if line.startswith("#define ") and f" {pass_id}_" in line]
        assert len(defines) == len(files.block_members(files._bodies()[body])), wrapper
        kept = [line for line in lines if line not in defines and not line.startswith("// Waveform Ribbon")]
        assert "\n".join(kept) == files._bodies()[body], wrapper
    # Negative control: a text that moved is reported.
    original = files._bodies

    def moved():
        bodies = original()
        bodies["waveform_floor_fragment"] = bodies["waveform_floor_fragment"].replace("0.6,-0.8", "0.6,-0.7", 1)
        return bodies
    monkeypatch.setattr(files, "_bodies", moved)
    assert tool.differences() == ["waveform_floor_fragment.glsl"]


def test_every_pass_names_each_member_once_across_the_program():
    from rendering.gl_programs.waveform_shader_files import member_name, pass_members

    names = [member_name(pass_id, member) for pass_id, members in pass_members().items() for member in members]
    assert len(names) == len(set(names))
    # Negative control: without the prefix the passes' members collide (the reason for the pass files).
    bare = [member for members in pass_members().values() for member in members]
    assert len(bare) > len(set(bare))


def _offsets(program: int) -> dict[str, int]:
    """Every block member's byte offset in ``program`` by its name."""
    import ctypes

    from OpenGL import GL as gl

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
def test_every_pass_program_compiles_and_keeps_the_python_texts_offsets(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking

    disable_per_call_gl_error_checking()
    from rendering.gl_programs.waveform_shader_files import PASS_FILES, _bodies
    from rendering.quick.render.gl_resources import compile_compute_program, compile_program, delete_program
    from tools.labs.render_target import OffscreenRenderTarget
    from widgets.spotify_visualizer.shaders import compose_shader_source

    passes = {name: (body, pass_id) for name, body, pass_id in PASS_FILES}
    bodies = _bodies()
    target = OffscreenRenderTarget(16, 16)

    def compiled(texts, label):
        return (compile_program(*texts, label=label) if len(texts) == 2
                else compile_compute_program(texts[0], label=label))
    checked = 0
    try:
        with target.current():
            for program_files in PROGRAMS:
                pass_id = passes[program_files[0]][1]
                program = compiled([compose_shader_source(_folder() / name) for name in program_files], program_files[0])
                python = compiled([bodies[passes[name][0]] for name in program_files], f"python {program_files[0]}")
                files, texts = _offsets(program), _offsets(python)
                delete_program(program)
                delete_program(python)
                prefix = f"{pass_id}_"
                own = {name[len(prefix):]: offset for name, offset in files.items() if name.startswith(prefix)}
                conventions = {name: offset for name, offset in files.items() if not name.startswith(prefix)}
                assert own and {**own, **conventions} == texts, program_files
                assert not set(conventions) & set(own), program_files
                checked += 1
    finally:
        target.close()
    assert checked == len(PROGRAMS)

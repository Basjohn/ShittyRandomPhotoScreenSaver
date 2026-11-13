"""Extruded Bubble: every pass-block program that refracts the captured background reads it at the unit the renderer
binds it to (the wake trails read unit 0 from f0ead35b until 1D.11: whatever another pass had left there)."""
import re

import numpy as np
import pytest

from rendering.quick.render.gl_resources import delete_program


def _declares_background(source: str) -> bool:
    return re.search(r"uniform\s+sampler2D\s+uBackground\s*;", source) is not None


@pytest.mark.qt
def test_block_programs_read_the_captured_background_at_the_renderers_unit(qt_app):
    from OpenGL import GL as gl
    from rendering.quick.render.gl_resources import compile_program
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from tools.transition_contact_sheet import TransitionCapture

    # The programs whose samplers a pass-block family binds in the shader (the loose ones take _glass's value).
    rows = [(key, vertex, fragment) for key, vertex, fragment in eb._PROGRAMS
            if key in eb._BLOCKS and _declares_background(fragment)]
    assert any(key == "trails" for key, _v, _f in rows)
    target = TransitionCapture(1, 1)
    programs = []
    try:
        units = {}
        for key, vertex, fragment in rows:
            program = compile_program(vertex, fragment, label=f"EB background unit {key}")
            programs.append(program)
            location = gl.glGetUniformLocation(program, "uBackground")
            assert location >= 0, key
            unit = np.zeros(1, dtype=np.int32)
            gl.glGetUniformiv(program, location, unit)
            units[key] = int(unit[0])
        assert gl.glGetError() == gl.GL_NO_ERROR
        # The unit the renderer binds the captured background to before the transparent pass.
        assert units == {key: eb._UNIT_BACKGROUND for key in units}
        # The loose traced glass is given the same unit by the renderer's values.
        assert eb._glass({"spec_dir": (0.0, 1.0, 0.0), "specular_light": (1.0, 1.0, 1.0), "light_strength": 1.0},
                         False)["uBackground"] == eb._UNIT_BACKGROUND
    finally:
        for program in programs:
            delete_program(program)
        target.close()

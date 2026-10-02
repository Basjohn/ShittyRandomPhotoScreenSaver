"""Small OpenGL resource helpers for Quick render-thread owners."""

from __future__ import annotations

from OpenGL import GL as gl


def _info_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def compile_program(vertex_source: str, fragment_source: str, *, label: str) -> int:
    """Compile and link one program in the caller's current GL context."""

    return _link(((gl.GL_VERTEX_SHADER, vertex_source, "vertex"),
                  (gl.GL_FRAGMENT_SHADER, fragment_source, "fragment")), label)


def compile_compute_program(source: str, *, label: str) -> int:
    """Compile and link one compute program in the caller's current GL context."""

    return _link(((gl.GL_COMPUTE_SHADER, source, "compute"),), label)


def _link(stages, label: str) -> int:
    shaders: list[int] = []
    program = 0
    try:
        for shader_type, source, stage in stages:
            shader = int(gl.glCreateShader(shader_type))
            if not shader:
                raise RuntimeError(f"{label} {stage} shader creation failed")
            shaders.append(shader)
            gl.glShaderSource(shader, source)
            gl.glCompileShader(shader)
            if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
                info = _info_text(gl.glGetShaderInfoLog(shader))
                raise RuntimeError(f"{label} {stage} shader compile failed: {info}")

        program = int(gl.glCreateProgram())
        if not program:
            raise RuntimeError(f"{label} program creation failed")
        for shader in shaders:
            gl.glAttachShader(program, shader)
        gl.glLinkProgram(program)
        if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
            info = _info_text(gl.glGetProgramInfoLog(program))
            raise RuntimeError(f"{label} program link failed: {info}")
        linked_program = program
        program = 0
        return linked_program
    finally:
        if program:
            gl.glDeleteProgram(program)
        for shader in shaders:
            gl.glDeleteShader(shader)

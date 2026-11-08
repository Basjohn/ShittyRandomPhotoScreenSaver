"""Small OpenGL resource helpers for Quick render-thread owners.

``_link`` is the one place a custom GL program is linked (every Visualizer mode, transition and scene3d program goes
through ``compile_program`` / ``compile_compute_program``). It first tries the app-owned program binary store
(``gl_program_cache``): a stored binary for the same sources and driver is loaded with ``glProgramBinary`` and kept
only if ``GL_LINK_STATUS`` says it linked. Otherwise it compiles and links as always and saves the linked binary. A
cold driver link (Neon Lake's basin: ~6 s, R-180) is then paid once per machine and driver, not once per build.
"""

from __future__ import annotations

import ctypes
import time

from OpenGL import GL as gl

from core.logging.logger import get_logger

from .gl_program_cache import DriverIdentity, ProgramBinaryCache, program_binary_cache, program_key

logger = get_logger(__name__)


def _info_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def compile_program(vertex_source: str, fragment_source: str, *, label: str,
                    geometry_source: str | None = None) -> int:
    """Compile and link one program in the caller's current GL context (optionally with a geometry stage)."""

    stages = [(gl.GL_VERTEX_SHADER, vertex_source, "vertex")]
    if geometry_source is not None:
        stages.append((gl.GL_GEOMETRY_SHADER, geometry_source, "geometry"))
    stages.append((gl.GL_FRAGMENT_SHADER, fragment_source, "fragment"))
    return _link(tuple(stages), label)


def compile_compute_program(source: str, *, label: str) -> int:
    """Compile and link one compute program in the caller's current GL context."""

    return _link(((gl.GL_COMPUTE_SHADER, source, "compute"),), label)


def _driver_identity() -> DriverIdentity | None:
    """The current context's driver strings and program binary formats; None when binaries are unavailable."""

    try:
        strings = tuple(gl.glGetString(name) for name in (gl.GL_VENDOR, gl.GL_RENDERER, gl.GL_VERSION))
        if not all(strings):
            return None
        count = int(gl.glGetIntegerv(gl.GL_NUM_PROGRAM_BINARY_FORMATS))
        if count <= 0:
            return None
        formats = (gl.GLint * count)()
        gl.glGetIntegerv(gl.GL_PROGRAM_BINARY_FORMATS, formats)
    except Exception:
        return None
    vendor, renderer, version = (_info_text(value) for value in strings)
    return DriverIdentity(vendor, renderer, version, tuple(int(value) & 0xFFFFFFFF for value in formats))


def _load_binary(cache: ProgramBinaryCache, key: str, driver: DriverIdentity) -> int:
    """A linked program from the stored binary, or 0 (absent, damaged, or refused by the driver)."""

    entry = cache.load(key)
    if entry is None:
        return 0
    binary_format, payload = entry
    if binary_format not in driver.formats:   # never hand the driver a format it would reject with a GL error
        return 0
    program = int(gl.glCreateProgram())
    if not program:
        return 0
    try:
        gl.glProgramBinary(program, binary_format, payload, len(payload))
        linked = bool(gl.glGetProgramiv(program, gl.GL_LINK_STATUS))
    except Exception:
        linked = False
    if linked:
        return program
    gl.glDeleteProgram(program)
    return 0


def _save_binary(cache: ProgramBinaryCache, key: str, program: int) -> int:
    """Store the linked program's binary; returns the bytes stored (0 when nothing was)."""

    try:
        length = int(gl.glGetProgramiv(program, gl.GL_PROGRAM_BINARY_LENGTH))
        if length <= 0:
            return 0
        buffer = ctypes.create_string_buffer(length)
        written = gl.GLsizei(0)
        binary_format = gl.GLenum(0)
        gl.glGetProgramBinary(program, length, ctypes.byref(written), ctypes.byref(binary_format), buffer)
        payload = buffer.raw[:max(0, int(written.value))]
    except Exception:
        return 0
    if not payload or not cache.store(key, int(binary_format.value), payload):
        return 0
    return len(payload)


def _link(stages, label: str) -> int:
    cache = program_binary_cache()
    driver = _driver_identity() if cache.enabled else None
    key = program_key(((shader_type, source) for shader_type, source, _stage in stages), driver) if driver else ""
    if key:
        started = time.perf_counter()
        loaded = _load_binary(cache, key, driver)
        if loaded:
            hits, misses = cache.count(hit=True)
            logger.debug("[GL_PROGRAM_CACHE] %s loaded in %.1f ms (hits=%d misses=%d)", label,
                         (time.perf_counter() - started) * 1000.0, hits, misses)
            return loaded
    started = time.perf_counter()
    program = _compile_and_link(stages, label, retrievable=bool(key))
    if key:
        link_ms = (time.perf_counter() - started) * 1000.0
        hits, misses = cache.count(hit=False)
        stored = _save_binary(cache, key, program)
        if stored:
            logger.info("[GL_PROGRAM_CACHE] %s linked cold in %.0f ms, saved %d KB (hits=%d misses=%d)", label,
                        link_ms, (stored + 1023) // 1024, hits, misses)
    return program


def _compile_and_link(stages, label: str, *, retrievable: bool) -> int:
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
        if retrievable:
            gl.glProgramParameteri(program, gl.GL_PROGRAM_BINARY_RETRIEVABLE_HINT, gl.GL_TRUE)
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

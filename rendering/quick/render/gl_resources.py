"""Small OpenGL resource helpers for Quick render-thread owners.

``_link`` is the one place a custom GL program is linked (every Visualizer mode, transition and scene3d program goes
through ``compile_program`` / ``compile_compute_program``). It first tries the app-owned program binary store
(``gl_program_cache``): a stored binary for the same sources and driver is loaded with ``glProgramBinary`` and kept
only if ``GL_LINK_STATUS`` says it linked. Otherwise it compiles and links as always and saves the linked binary. A
cold driver link (Neon Lake's basin: ~6 s, R-180) is then paid once per machine and driver, not once per build.

A program that declares the conventions block (``rendering.gl_programs.conventions``; an active block after link)
holds that context's one conventions buffer, bound at its reserved point; every program linked here is deleted with
``delete_program``, which hands a hold back (the last one deletes the buffer).
"""

from __future__ import annotations

import ctypes
import threading
import time

from OpenGL import GL as gl
from OpenGL.raw.GL.VERSION import GL_4_4 as _gl44

from core.logging.logger import get_logger
from rendering.gl_programs.conventions import (CONVENTIONS_BLOCK_NAME, SCENE3D_CONVENTIONS_BLOCK_BINDING,
                                               conventions_block)

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
    program = _link_program(stages, label)
    # The text only says a source may declare the block: the mapping-only include carries the name inside a false
    # ``#if``. The linked program says whether it declares it (a std140 block declared is an active block).
    if any(CONVENTIONS_BLOCK_NAME in source for _shader_type, source, _stage in stages) and _declares_conventions(program):
        _acquire_conventions(program)
    return program


def _declares_conventions(program: int) -> bool:
    index = int(gl.glGetUniformBlockIndex(program, CONVENTIONS_BLOCK_NAME.encode("ascii"))) & 0xFFFFFFFF
    return index != 0xFFFFFFFF            # GL_INVALID_INDEX: no active block of that name


def delete_program(program: int) -> None:
    """Delete a program linked here (in its own current context), releasing its hold on the conventions block. Every
    owner of a program linked through ``compile_program``/``compile_compute_program`` deletes it here, never with a raw
    ``glDeleteProgram``: whether a program holds is decided at link, by the driver."""

    gl.glDeleteProgram(program)
    _release_conventions(program)


# The conventions block (``rendering.gl_programs.conventions``): one buffer per context, created and bound at its
# reserved point when the first program declaring the block links there, deleted with the last such program. Its
# values never change for a context, so nothing is written or bound per frame.
#
# A context is identified by its native QOpenGLContext pointer, never by ``id()`` of the Python wrapper: for a context
# Qt created in C++ (Qt Quick's render-thread context) PySide makes a new wrapper per ``currentContext()`` call
# whenever Python holds none, so ``id()`` changed between two calls in one context and was reused across contexts
# (R-198: one buffer per link, none released, another context left unbound at the block's binding). The native pointer
# lives exactly as long as the context and is never kept alive by the registry (holding the wrapper would extend the
# life of a context Python owns). Its ``aboutToBeDestroyed`` is connected once per context (the connection is Qt's and
# outlives any wrapper) and forgets the context's entry, so a pointer reused by a later context starts clean. Buffer
# and programs belong to the share group, which outlives the context when others share it; they are not deleted then.
_conventions_lock = threading.Lock()
_conventions: dict[int, list] = {}              # native context -> [buffer, holding programs, native share group]
_convention_programs: set[tuple[int, int]] = set()   # (native context, program)
_watched_contexts: set[int] = set()             # native contexts whose aboutToBeDestroyed is connected


def _native(qobject) -> int:
    import shiboken6

    return int(shiboken6.getCppPointer(qobject)[0])


def _current_context():
    from PySide6.QtGui import QOpenGLContext

    return QOpenGLContext.currentContext()


def _forget_context(key: int) -> None:
    with _conventions_lock:
        _conventions.pop(key, None)
        _watched_contexts.discard(key)
        for entry in [entry for entry in _convention_programs if entry[0] == key]:
            _convention_programs.discard(entry)


def _acquire_conventions(program: int) -> None:
    context = _current_context()
    if context is None:
        raise RuntimeError("the conventions block needs the program's current context")
    key = _native(context)
    with _conventions_lock:
        if (key, program) in _convention_programs:
            return
        entry = _conventions.get(key)
        if entry is None:
            data = conventions_block()
            name = (ctypes.c_uint * 1)()
            gl.glCreateBuffers(1, name)
            buffer = int(name[0])
            gl.glNamedBufferStorage(buffer, len(data), data, 0)
            # Multi-bind sets the indexed point only, never the generic uniform-buffer binding Qt Quick may hold.
            _gl44.glBindBuffersBase(gl.GL_UNIFORM_BUFFER, SCENE3D_CONVENTIONS_BLOCK_BINDING, 1, name)
            entry = _conventions[key] = [buffer, 0, _native(context.shareGroup())]
            if key not in _watched_contexts:
                _watched_contexts.add(key)
                context.aboutToBeDestroyed.connect(lambda key=key: _forget_context(key))
        entry[1] += 1
        _convention_programs.add((key, program))


def _release_conventions(program: int) -> None:
    context = _current_context()
    key = None if context is None else _native(context)
    with _conventions_lock:
        if (key, program) not in _convention_programs:
            group = None if context is None else _native(context.shareGroup())
            if any(held == program and _conventions[other][2] == group for other, held in _convention_programs):
                # Deleted in another context of the share group than the one that holds it: the hold stays rather
                # than unbinding the block in a context that may still draw with it.
                logger.error("[GL_CONVENTIONS] program %d deleted outside the context that holds its conventions "
                             "buffer; the hold is kept", program)
            return
        _convention_programs.discard((key, program))
        entry = _conventions[key]
        entry[1] -= 1
        if entry[1] > 0:
            return
        del _conventions[key]
        buffer = entry[0]
    gl.glDeleteBuffers(1, [buffer])


def _link_program(stages, label: str) -> int:
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

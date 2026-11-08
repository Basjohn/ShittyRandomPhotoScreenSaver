"""The app-owned program binary cache behind the one link owner (``gl_resources._link``), R-180's follow-up.

Real offscreen GL (no window): a miss compiles, links and saves; a hit loads with no compile or link and draws the
same picture; a source edit, a driver-string change, a damaged file and a binary the driver refuses all fall back to
the compile and replace the entry; the store stays within its size bound, oldest-used first. The negative control
runs the hit test with the store disabled and sees the compile.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.quick.render import gl_program_cache, gl_resources
from rendering.quick.render.gl_program_cache import ProgramBinaryCache, program_key

pytestmark = pytest.mark.qt

ROOT = Path(__file__).resolve().parents[1]

_VERTEX = """#version 460 core
void main() {
    vec2 corner = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
"""


def _fragment(red: float) -> str:
    # A per-test nonce keeps every test's sources distinct, so no driver-side cache decides the outcome.
    return (f"#version 460 core\n// {uuid.uuid4().hex}\nout vec4 FragColor;\n"
            f"void main() {{ FragColor = vec4({red:.3f}, 0.25, 0.75, 1.0); }}\n")


@pytest.fixture
def target(qt_app):
    from rendering.quick.offscreen_target import OffscreenRenderTarget

    target = OffscreenRenderTarget(8, 8, label="gl program cache test")
    yield target
    target.close()


@pytest.fixture
def store(tmp_path, monkeypatch):
    cache = ProgramBinaryCache(tmp_path / "gl_program_cache")
    monkeypatch.setattr(gl_program_cache, "_cache", cache)
    return cache


@pytest.fixture
def calls(monkeypatch):
    """Counts of the driver's compile and link entry points, still calling through."""

    counted = {"glCompileShader": 0, "glLinkProgram": 0}
    for name in counted:
        real = getattr(gl, name)

        def wrapper(*args, _name=name, _real=real):
            counted[_name] += 1
            return _real(*args)
        monkeypatch.setattr(gl, name, wrapper)
    return counted


def _draw(target, program: int) -> tuple[int, ...]:
    with target.current():
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glViewport(0, 0, target.width, target.height)
        gl.glUseProgram(program)
        gl.glBindVertexArray(target.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        pixel = np.zeros(4, np.uint8)
        gl.glReadPixels(4, 4, 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, pixel)
        gl.glUseProgram(0)
    return tuple(int(value) for value in pixel)


def _entries(cache: ProgramBinaryCache) -> list[Path]:
    return sorted(cache.root.glob("*.bin")) if cache.root.exists() else []


def _link(fragment: str, label: str = "cache test") -> int:
    return gl_resources.compile_program(_VERTEX, fragment, label=label)


def test_a_miss_compiles_links_and_saves_once(target, store, calls, caplog):
    fragment = _fragment(1.0)
    with target.current(), caplog.at_level(logging.INFO):
        program = _link(fragment)
    assert calls == {"glCompileShader": 2, "glLinkProgram": 1}
    assert len(_entries(store)) == 1
    assert store.stats() == {"hits": 0, "misses": 1, "saved": 1}
    saved = [record.getMessage() for record in caplog.records if "[GL_PROGRAM_CACHE]" in record.getMessage()]
    assert len(saved) == 1 and "linked cold" in saved[0] and "cache test" in saved[0]
    assert _draw(target, program) == (255, 64, 191, 255)
    with target.current():
        gl.glDeleteProgram(program)


def test_a_hit_loads_without_compiling_and_draws_the_same(target, store, calls):
    fragment = _fragment(0.5)
    with target.current():
        first = _link(fragment)
    picture = _draw(target, first)
    calls.update(glCompileShader=0, glLinkProgram=0)
    with target.current():
        second = _link(fragment)
        assert gl.glGetProgramiv(second, gl.GL_LINK_STATUS)
    assert calls == {"glCompileShader": 0, "glLinkProgram": 0}
    assert second != first and _draw(target, second) == picture
    assert store.stats() == {"hits": 1, "misses": 1, "saved": 1}
    with target.current():
        gl.glDeleteProgram(first)
        gl.glDeleteProgram(second)


def test_negative_control_with_the_store_disabled_the_hit_case_compiles(target, monkeypatch, calls, tmp_path):
    disabled = ProgramBinaryCache(None)
    monkeypatch.setattr(gl_program_cache, "_cache", disabled)
    fragment = _fragment(0.5)
    with target.current():
        first = _link(fragment)
        second = _link(fragment)
        gl.glDeleteProgram(first)
        gl.glDeleteProgram(second)
    assert calls == {"glCompileShader": 4, "glLinkProgram": 2}
    assert disabled.stats() == {"hits": 0, "misses": 0, "saved": 0}
    assert not list(tmp_path.rglob("*.bin"))


def test_a_source_edit_misses(target, store, calls):
    with target.current():
        first = _link(_fragment(0.2))
        calls.update(glCompileShader=0, glLinkProgram=0)
        second = _link(_fragment(0.2))     # same colour, different nonce: an edited source
        gl.glDeleteProgram(first)
        gl.glDeleteProgram(second)
    assert calls == {"glCompileShader": 2, "glLinkProgram": 1}
    assert len(_entries(store)) == 2


def test_a_driver_string_change_misses(target, store, calls, monkeypatch):
    fragment = _fragment(0.3)
    with target.current():
        first = _link(fragment)
    real_get_string = gl.glGetString

    def updated_driver(name):
        value = real_get_string(name)
        return value + b" (updated)" if name == gl.GL_VERSION else value
    monkeypatch.setattr(gl, "glGetString", updated_driver)
    calls.update(glCompileShader=0, glLinkProgram=0)
    with target.current():
        second = _link(fragment)
        gl.glDeleteProgram(first)
        gl.glDeleteProgram(second)
    assert calls == {"glCompileShader": 2, "glLinkProgram": 1}
    assert len(_entries(store)) == 2


@pytest.mark.parametrize("damage", ["truncated", "flipped", "refused_by_driver", "foreign_key"])
def test_a_damaged_entry_falls_back_to_the_compile_and_is_replaced(target, store, calls, damage):
    fragment = _fragment(0.8)
    with target.current():
        first = _link(fragment)
    picture = _draw(target, first)
    (path,) = _entries(store)
    key = path.stem
    data = path.read_bytes()
    if damage == "truncated":
        path.write_bytes(data[: len(data) // 2])
    elif damage == "flipped":
        path.write_bytes(data[:-10] + bytes([data[-10] ^ 0xFF]) + data[-9:])
    elif damage == "refused_by_driver":
        # An intact file whose payload the driver does not accept (as after a driver change it cannot see).
        binary_format, _payload = store.load(key)
        store.store(key, binary_format, b"\x00not a program binary\x00" * 64)
    else:
        other = ProgramBinaryCache(store.root)
        other.store("0" * 64, 1, b"x")
        path.write_bytes((store.root / f"{'0' * 64}.bin").read_bytes())
    calls.update(glCompileShader=0, glLinkProgram=0)
    with target.current():
        second = _link(fragment)
    assert calls == {"glCompileShader": 2, "glLinkProgram": 1}
    assert _draw(target, second) == picture
    replaced = store.load(key)
    assert replaced is not None and replaced[1] != b"\x00not a program binary\x00" * 64
    calls.update(glCompileShader=0, glLinkProgram=0)
    with target.current():
        third = _link(fragment)
        for program in (first, second, third):
            gl.glDeleteProgram(program)
    assert calls == {"glCompileShader": 0, "glLinkProgram": 0}


def test_a_failed_compile_stores_nothing(target, store):
    with target.current(), pytest.raises(RuntimeError, match="fragment shader compile failed"):
        _link("#version 460 core\nout vec4 FragColor;\nvoid main() { nope; }\n")
    assert not _entries(store)
    assert store.stats() == {"hits": 0, "misses": 0, "saved": 0}


def test_the_size_bound_prunes_least_recently_used_entries(tmp_path):
    cache = ProgramBinaryCache(tmp_path, max_bytes=3000)
    keys = [f"{index:064x}" for index in range(4)]
    for index, key in enumerate(keys[:3]):
        assert cache.store(key, 7, bytes([index]) * 900)
        os.utime(tmp_path / f"{key}.bin", (1000.0 + index, 1000.0 + index))
    stale = tmp_path / f"{keys[0]}.123.456.tmp"
    stale.write_bytes(b"partial")
    os.utime(stale, (1000.0, 1000.0))
    assert cache.load(keys[0]) == (7, bytes([0]) * 900)          # a hit makes the oldest the most recently used
    assert cache.store(keys[3], 7, bytes([3]) * 900)
    remaining = {path.stem for path in tmp_path.glob("*.bin")}
    assert remaining == {keys[0], keys[2], keys[3]}              # keys[1] was least recently used
    assert sum(path.stat().st_size for path in tmp_path.glob("*.bin")) <= 3000
    assert not stale.exists()
    assert not cache.store(keys[1], 7, b"x" * 3001)             # larger than the whole bound: never stored


def test_the_key_covers_every_stage_and_every_driver_field():
    driver = gl_program_cache.DriverIdentity("V", "R", "4.6", (0x8E21,))
    stages = ((gl.GL_VERTEX_SHADER, "a"), (gl.GL_FRAGMENT_SHADER, "b"))
    base = program_key(stages, driver)
    assert base == program_key(list(stages), driver)
    variants = [
        program_key(((gl.GL_VERTEX_SHADER, "a"), (gl.GL_FRAGMENT_SHADER, "b ")), driver),
        program_key(((gl.GL_VERTEX_SHADER, "ab"), (gl.GL_FRAGMENT_SHADER, "")), driver),
        program_key(((gl.GL_COMPUTE_SHADER, "a"), (gl.GL_FRAGMENT_SHADER, "b")), driver),
        program_key(stages, gl_program_cache.DriverIdentity("V2", "R", "4.6", (0x8E21,))),
        program_key(stages, gl_program_cache.DriverIdentity("V", "R2", "4.6", (0x8E21,))),
        program_key(stages, gl_program_cache.DriverIdentity("V", "R", "4.6.1", (0x8E21,))),
        program_key(stages, gl_program_cache.DriverIdentity("V", "R", "4.6", (0x8E21, 1))),
    ]
    assert len({base, *variants}) == len(variants) + 1


def test_the_store_lives_in_the_per_user_local_root_and_is_off_without_one(monkeypatch, tmp_path):
    from core import platform_paths

    monkeypatch.setattr(platform_paths, "user_local_root", lambda: tmp_path)
    assert gl_program_cache.default_cache_root() == tmp_path / "SRPSS" / "gl_program_cache"
    monkeypatch.setattr(gl_program_cache, "_cache", None)
    assert gl_program_cache.program_binary_cache().root == tmp_path / "SRPSS" / "gl_program_cache"
    monkeypatch.setattr(platform_paths, "user_local_root", lambda: None)
    monkeypatch.setattr(gl_program_cache, "_cache", None)
    assert not gl_program_cache.program_binary_cache().enabled


def test_no_production_module_links_a_program_outside_the_one_owner():
    owner = ROOT / "rendering" / "quick" / "render" / "gl_resources.py"
    offenders = []
    for folder in ("core", "engine", "helpers", "rendering", "ui", "utilities", "utils", "widgets"):
        for path in (ROOT / folder).rglob("*.py") if (ROOT / folder).exists() else ():
            if path != owner and "glLinkProgram(" in path.read_text(encoding="utf-8", errors="replace"):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []

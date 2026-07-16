from __future__ import annotations

from rendering.gl_programs import program_cache


class _FakeGL:
    GL_LINK_STATUS = 1

    def __init__(self) -> None:
        self.deleted: list[int] = []

    def glIsProgram(self, _program_id: int) -> bool:
        return True

    def glGetProgramiv(self, _program_id: int, _field: int) -> int:
        return 1

    def glDeleteProgram(self, program_id: int) -> None:
        self.deleted.append(int(program_id))


class _FakeProgram:
    def __init__(self) -> None:
        self.create_calls = 0

    def create_program(self) -> int:
        self.create_calls += 1
        # Deliberately reuse the same numeric name across fake share groups.
        return 17

    def cache_uniforms(self, _program_id: int) -> dict[str, int]:
        return {"generation": self.create_calls}


def test_program_cache_scopes_numeric_ids_to_current_share_group(monkeypatch):
    current = {"key": ("share_group", 1), "wrapper": object()}
    fake_gl = _FakeGL()
    fake_program = _FakeProgram()

    monkeypatch.setattr(
        program_cache,
        "_current_share_group_identity",
        lambda: (current["key"], current["wrapper"]),
    )
    monkeypatch.setattr(program_cache, "_load_gl", lambda: fake_gl)

    cache = program_cache.GLProgramCache()
    monkeypatch.setattr(cache, "_load_program_instance", lambda _name: fake_program)

    assert cache.get_program("wipe") == 17
    assert cache.get_uniforms("wipe") == {"generation": 1}
    assert cache.get_program("wipe") == 17
    assert fake_program.create_calls == 1

    current["key"] = ("share_group", 2)
    current["wrapper"] = object()

    assert cache.get_program("wipe") == 17
    assert cache.get_uniforms("wipe") == {"generation": 2}
    assert fake_program.create_calls == 2


def test_program_cache_cleans_only_the_current_share_group(monkeypatch):
    current = {"key": ("share_group", 1), "wrapper": object()}
    fake_gl = _FakeGL()
    fake_program = _FakeProgram()

    monkeypatch.setattr(
        program_cache,
        "_current_share_group_identity",
        lambda: (current["key"], current["wrapper"]),
    )
    monkeypatch.setattr(program_cache, "_load_gl", lambda: fake_gl)

    cache = program_cache.GLProgramCache()
    monkeypatch.setattr(cache, "_load_program_instance", lambda _name: fake_program)

    assert cache.get_program("warp") == 17
    current["key"] = ("share_group", 2)
    current["wrapper"] = object()
    assert cache.get_program("warp") == 17

    current["key"] = ("share_group", 1)
    current["wrapper"] = object()
    assert cache.cleanup_current_group() == 1
    assert fake_gl.deleted == [17]

    current["key"] = ("share_group", 2)
    current["wrapper"] = object()
    assert cache.get_program("warp") == 17
    assert fake_program.create_calls == 2

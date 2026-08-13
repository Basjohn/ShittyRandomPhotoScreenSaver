from __future__ import annotations

from pathlib import Path

import pytest

from rendering.gl_timer_queries import GLTimerQueryRing


class _Format:
    def __init__(self, major: int = 3, minor: int = 3) -> None:
        self._major = major
        self._minor = minor

    def majorVersion(self) -> int:
        return self._major

    def minorVersion(self) -> int:
        return self._minor


class _Context:
    def __init__(
        self,
        *,
        major: int = 3,
        minor: int = 3,
        extension: bool = False,
    ) -> None:
        self._format = _Format(major, minor)
        self._extension = extension

    def format(self) -> _Format:
        return self._format

    def hasExtension(self, _name) -> bool:
        return self._extension


class _ResourceManager:
    def __init__(self) -> None:
        self.registered: list[tuple[int, str]] = []
        self.released: list[str] = []

    def register_gl_handle(self, handle: int, handle_type: str, **_metadata) -> str:
        self.registered.append((int(handle), str(handle_type)))
        return f"rid-{handle}"

    def release_tracking(self, resource_id: str) -> None:
        self.released.append(resource_id)


class _FakeGL:
    GL_TIME_ELAPSED = 1
    GL_QUERY_RESULT_AVAILABLE = 2
    GL_QUERY_RESULT = 3

    def __init__(self, *, start: int = 11) -> None:
        self._start = start
        self.available: dict[int, int] = {}
        self.results_ns: dict[int, int] = {}
        self.generated = 0
        self.begin_calls: list[tuple[int, int]] = []
        self.end_calls: list[int] = []
        self.availability_calls: list[int] = []
        self.result_calls: list[int] = []
        self.delete_calls: list[int] = []
        self.fail_delete: set[int] = set()

    def glGenQueries(self, count: int):
        self.generated += 1
        return list(range(self._start, self._start + int(count)))

    def glBeginQuery(self, target: int, handle: int) -> None:
        self.begin_calls.append((int(target), int(handle)))

    def glEndQuery(self, target: int) -> None:
        self.end_calls.append(int(target))

    def glGetQueryObjectiv(self, handle: int, _pname: int) -> int:
        self.availability_calls.append(int(handle))
        return int(self.available.get(int(handle), 0))

    def glGetQueryObjectui64v(self, handle: int, _pname: int) -> int:
        self.result_calls.append(int(handle))
        return int(self.results_ns.get(int(handle), 0))

    def glDeleteQueries(self, _count: int, handles) -> None:
        handle = int(handles[0])
        if handle in self.fail_delete:
            raise RuntimeError("driver refused query delete")
        self.delete_calls.append(handle)


def _ring(*, size: int = 4, manager: _ResourceManager | None = None) -> GLTimerQueryRing:
    return GLTimerQueryRing(
        owner="test-owner",
        generation=7,
        ring_size=size,
        resource_manager=manager,
    )


def test_timer_queries_collect_only_after_result_is_available() -> None:
    gl = _FakeGL()
    ring = _ring()

    assert ring.initialize(gl, context=_Context()) is True
    assert ring.begin(gl, label="bubble") is True
    ring.end(gl)

    ring.poll(gl)
    assert gl.availability_calls == [11]
    assert gl.result_calls == []

    gl.available[11] = 1
    gl.results_ns[11] = 1_500_000
    ring.poll(gl)

    assert gl.result_calls == [11]
    snapshot = ring.consume_window(include_labels=("bubble",))
    assert snapshot["supported"] is True
    assert snapshot["reason"] == "supported"
    assert snapshot["pending"] == 0
    assert snapshot["errors"] == 0
    assert snapshot["by_label"]["bubble"] == {
        "submitted": 1,
        "collected": 1,
        "pending": 0,
        "dropped_pending": 0,
        "discarded": 0,
        "samples": 1,
        "p50_ms": 1.5,
        "p95_ms": 1.5,
        "max_ms": 1.5,
    }


def test_timer_query_ring_drops_samples_instead_of_waiting() -> None:
    gl = _FakeGL()
    ring = _ring(size=4)
    assert ring.initialize(gl, context=_Context()) is True

    for _ in range(4):
        assert ring.begin(gl, label="spectrum") is True
        ring.end(gl)
    assert ring.begin(gl, label="spectrum") is False
    assert gl.result_calls == []

    snapshot = ring.consume_window(include_labels=("spectrum",))
    assert snapshot["pending"] == 4
    assert snapshot["by_label"]["spectrum"]["submitted"] == 4
    assert snapshot["by_label"]["spectrum"]["pending"] == 4
    assert snapshot["by_label"]["spectrum"]["dropped_pending"] == 1
    assert snapshot["by_label"]["spectrum"]["samples"] == 0


def test_timer_query_probe_reports_unsupported_without_allocating() -> None:
    gl = _FakeGL()
    ring = _ring()

    assert ring.initialize(
        gl,
        context=_Context(major=3, minor=2, extension=False),
    ) is False
    assert ring.supported is False
    assert ring.support_reason == "context_unsupported"
    assert gl.generated == 0
    assert ring.has_live_queries() is False


def test_strict_query_cleanup_retains_only_failed_owner_ids() -> None:
    manager = _ResourceManager()
    gl = _FakeGL(start=31)
    ring = _ring(size=2, manager=manager)
    assert ring.initialize(gl, context=_Context()) is True
    assert manager.registered == [(31, "query"), (32, "query")]

    for label in ("bubble", "spectrum"):
        assert ring.begin(gl, label=label) is True
        ring.end(gl)
    gl.fail_delete.add(32)

    with pytest.raises(RuntimeError, match="query:32"):
        ring.cleanup(gl)

    assert gl.delete_calls == [31]
    assert manager.released == ["rid-31"]
    assert ring.has_live_queries() is True
    snapshot = ring.consume_window(include_labels=("bubble", "spectrum"))
    assert snapshot["by_label"]["bubble"]["discarded"] == 1
    assert snapshot["by_label"]["spectrum"]["discarded"] == 1

    gl.fail_delete.clear()
    ring.cleanup(gl)
    assert gl.delete_calls == [31, 32]
    assert manager.released == ["rid-31", "rid-32"]
    assert ring.has_live_queries() is False


def test_timer_query_helper_has_no_blocking_gpu_sync_call() -> None:
    source = Path("rendering/gl_timer_queries.py").read_text(encoding="utf-8")
    assert "glFinish" not in source
    assert "glFlush" not in source
    assert "GL_QUERY_RESULT_AVAILABLE" in source


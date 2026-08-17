"""Bars for the --diag-p4-stages GL_TIMESTAMP stage ring.

Observational only: fixed-size, availability-checked, drops rather than waits,
no finish/flush/fence, and allocated only when the CLI gate is active.
"""
from __future__ import annotations

import ctypes
import inspect
import pathlib

import pytest

from rendering import gl_stage_timestamps as mod
from rendering.gl_stage_timestamps import (
    CLI_FLAG,
    STAGE_MARKERS,
    GLStageTimestampRing,
    cli_enabled,
)


class _FakeGL:
    GL_TIMESTAMP = 0x8E28
    GL_QUERY_RESULT = 0x8866
    GL_QUERY_RESULT_AVAILABLE = 0x8867

    def __init__(self, available=True, base_ns=1_000_000):
        self._next = 1
        self.available = available
        self.base_ns = base_ns
        self.deleted: list[int] = []
        self.counters: list[int] = []
        self.delete_should_fail = False

    def glGenQueries(self, n):
        out = [self._next + i for i in range(n)]
        self._next += n
        return out

    def glQueryCounter(self, handle, target):
        self.counters.append(handle)

    def glGetQueryObjectuiv(self, handle, pname, out):
        out[0] = 1 if self.available else 0

    def glGetQueryObjectui64v(self, handle, pname, out):
        out[0] = self.base_ns + handle * 1_000_000

    def glDeleteQueries(self, n, handles):
        if self.delete_should_fail:
            raise RuntimeError("simulated deletion failure")
        self.deleted.extend(handles)


def _ring(gl=None, capacity=2, manager=None):
    ring = GLStageTimestampRing(owner="test", generation=1, capacity=capacity)
    ring.initialize(gl or _FakeGL(), context=object(), resource_manager=manager)
    return ring


class TestCliGateOnly:
    def test_flag_is_the_documented_cli_diagnostic(self):
        assert CLI_FLAG == "--diag-p4-stages"
        assert cli_enabled(["main.py", "--perf", "--diag-p4-stages"]) is True
        assert cli_enabled(["main.py", "--perf"]) is False

    def test_no_environment_variable_path_exists(self):
        source = inspect.getsource(mod)
        assert "os.environ" not in source
        assert "getenv" not in source

    def test_flag_is_registered_in_the_known_flag_inventory(self):
        main_src = pathlib.Path("main.py").read_text(encoding="utf-8")
        assert '"--diag-p4-stages"' in main_src

    def test_no_blocking_primitives_are_called_in_the_helper(self):
        """AST-checked: prose naming them in the docstring is not a call."""
        import ast

        tree = ast.parse(inspect.getsource(mod))
        forbidden = {"glFinish", "glFlush", "glFenceSync", "glWaitSync", "sleep"}
        called = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in forbidden:
                called.add(name)
        assert not called, f"blocking primitives called in stage helper: {called}"


class TestFixedSizeAndDropping:
    def test_allocates_nothing_until_initialized(self):
        ring = GLStageTimestampRing(owner="test", generation=1, capacity=2)
        assert ring.has_live_queries() is False
        assert ring.supported is False

    def test_capacity_is_fixed_and_frames_drop_rather_than_wait(self):
        ring = _ring(capacity=1)
        assert ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        ring.end_frame()
        # Slot is still in flight; a second frame must drop, not block.
        assert ring.begin_frame(
            scene_generation=1, frame_index=2, transition="burn", render_path="shader"
        ) is False
        assert ring.dropped_no_capacity >= 1

    def test_reentrant_begin_is_refused(self):
        ring = _ring()
        assert ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        assert ring.begin_frame(
            scene_generation=1, frame_index=2, transition="burn", render_path="shader"
        ) is False


class TestAvailabilityCheckedCollection:
    def test_results_are_not_fetched_until_available(self):
        gl = _FakeGL(available=False)
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=2, frame_index=7, transition="warp", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()

        ring.poll(gl)
        assert ring.take_completed() == [], "collected before results were available"

        gl.available = True
        ring.poll(gl)
        done = ring.take_completed()
        assert len(done) == 1
        assert done[0].complete is True

    def test_completed_packet_retains_authoritative_identity(self):
        gl = _FakeGL()
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=5, frame_index=42, transition="blockspin", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        ring.poll(gl)

        packet = ring.take_completed()[0]
        assert packet.scene_generation == 5
        assert packet.frame_index == 42
        assert packet.transition == "blockspin"
        assert packet.render_path == "shader"

    def test_spans_are_derived_only_from_resolved_endpoints(self):
        gl = _FakeGL()
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        ring.poll(gl)

        spans = ring.take_completed()[0].spans_ms()
        for name in ("prep_gpu_ms", "core_draw_gpu_ms", "dimming_gpu_ms",
                     "overlay_gpu_ms", "marked_gpu_ms"):
            assert name in spans and spans[name] >= 0.0

    def test_markers_coexist_with_an_outer_elapsed_scope(self):
        """glQueryCounter is legal inside an active GL_TIME_ELAPSED block."""
        gl = _FakeGL()
        ring = _ring(gl)
        # Simulate the outer elapsed query being active around the markers.
        outer_active = True
        ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        assert outer_active
        assert len(gl.counters) == len(STAGE_MARKERS)


class TestStrictCleanupAndAccounting:
    def test_successful_cleanup_deletes_every_query(self):
        gl = _FakeGL()
        ring = _ring(gl, capacity=2)
        expected = 2 * len(STAGE_MARKERS)
        ring.cleanup(gl)
        assert len(gl.deleted) == expected
        assert ring.has_live_queries() is False

    def test_failed_deletion_retains_ownership_and_raises(self):
        gl = _FakeGL()
        ring = _ring(gl, capacity=1)
        gl.delete_should_fail = True

        with pytest.raises(RuntimeError):
            ring.cleanup(gl)

        assert ring.has_live_queries() is True, (
            "failed deletion must retain ownership, never manufacture a clean count"
        )

    def test_cleanup_without_a_context_refuses_rather_than_leaking_silently(self):
        gl = _FakeGL()
        ring = _ring(gl, capacity=1)
        with pytest.raises(RuntimeError):
            ring.cleanup(None)
        assert ring.has_live_queries() is True

"""Single-surface GPU timing must not nest GL_TIME_ELAPSED on one context.

The visualizer used to own a separate presentation surface and context, so a
visualizer-local GL_TIME_ELAPSED query could safely overlap the compositor's.
Under P2-SINGLE-SURFACE the visualizer renders INSIDE the compositor on the SAME
context, and GL_TIME_ELAPSED cannot nest: the inner begin raises GLError and the
installed run degraded to

    gpu_supported=False gpu_reason=begin_error:GLError

for the rest of the session.

The compositor's outer query is the owner. These bars pin that the visualizer
defers to it, that no GL error is produced, and that CPU metrics survive.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest

from rendering.gl_timer_queries import GLTimerQueryRing
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay


class _FakeContext:
    """Reports GL 3.3 so the ring's support probe allocates its slots."""

    class _Format:
        @staticmethod
        def majorVersion():
            return 3

        @staticmethod
        def minorVersion():
            return 3

    def format(self):
        return self._Format()


class _FakeGL:
    """Records query calls and raises on a nested begin, like a real driver."""

    GL_TIME_ELAPSED = "time_elapsed"
    GL_QUERY_RESULT = "result"
    GL_QUERY_RESULT_AVAILABLE = "available"

    def __init__(self):
        self.depth = 0
        self.begins = 0
        self.errors = 0
        self._next_id = 1

    def __init_subclass__(cls):  # pragma: no cover - defensive
        pass

    def glGenQueries(self, n):
        base = self._next_id
        self._next_id += n
        ids = list(range(base, base + n))
        return ids if n > 1 else ids[0]

    def glBeginQuery(self, target, qid):
        if self.depth:
            self.errors += 1
            raise RuntimeError("GLError: nested GL_TIME_ELAPSED")
        self.depth += 1
        self.begins += 1

    def glEndQuery(self, target):
        self.depth = max(0, self.depth - 1)

    def glGetQueryObjectiv(self, qid, pname):
        return 0

    def glGetQueryObjectui64v(self, qid, pname):
        return 0

    def glDeleteQueries(self, n, ids):
        pass


class TestRingExposesActiveQuery:
    def test_ring_reports_no_active_query_when_idle(self):
        ring = GLTimerQueryRing(owner="t", generation=1, ring_size=2)
        assert ring.has_active_query() is False

    def test_ring_reports_an_active_query_between_begin_and_end(self):
        ring = GLTimerQueryRing(owner="t", generation=1, ring_size=2)
        gl = _FakeGL()
        if not ring.initialize(gl, context=_FakeContext()):
            pytest.skip("timer query ring unavailable in this environment")

        assert ring.begin(gl, label="outer") is True
        assert ring.has_active_query() is True
        ring.end(gl)
        assert ring.has_active_query() is False


class TestVisualizerDefersToTheOuterQuery:
    def _overlay(self, *, outer_active: bool):
        ring = SimpleNamespace(has_active_query=lambda: outer_active)
        compositor = SimpleNamespace(_gpu_timer_queries=ring)
        overlay = SimpleNamespace(
            _publication_target_compositor=lambda: compositor
        )
        return overlay

    def test_active_outer_query_is_detected(self):
        overlay = self._overlay(outer_active=True)
        assert SpotifyBarsGLOverlay._compositor_gpu_query_active(overlay) is True

    def test_idle_outer_query_permits_visualizer_sampling(self):
        overlay = self._overlay(outer_active=False)
        assert SpotifyBarsGLOverlay._compositor_gpu_query_active(overlay) is False

    def test_missing_compositor_is_not_an_active_query(self):
        overlay = SimpleNamespace(_publication_target_compositor=lambda: None)
        assert SpotifyBarsGLOverlay._compositor_gpu_query_active(overlay) is False

    def test_compositor_without_a_ring_is_not_an_active_query(self):
        compositor = SimpleNamespace(_gpu_timer_queries=None)
        overlay = SimpleNamespace(_publication_target_compositor=lambda: compositor)
        assert SpotifyBarsGLOverlay._compositor_gpu_query_active(overlay) is False


class TestNoNestedBeginOccurs:
    def test_paint_layer_checks_the_outer_query_before_beginning(self):
        method = ast.parse(
            textwrap.dedent(inspect.getsource(SpotifyBarsGLOverlay.paint_layer))
        ).body[0]
        source = inspect.getsource(SpotifyBarsGLOverlay.paint_layer)
        guard = source.index("_compositor_gpu_query_active")
        begin = source.index("begin_sampled")
        assert guard < begin, (
            "the outer-query check must dominate the visualizer query begin"
        )

        self_calls = {
            n.func.attr
            for n in ast.walk(method)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "self"
        }
        assert "_compositor_gpu_query_active" in self_calls

    def test_nested_begin_would_have_errored(self):
        """Proves the fake driver models the real failure being prevented."""
        ring = GLTimerQueryRing(owner="t", generation=1, ring_size=2)
        gl = _FakeGL()
        if not ring.initialize(gl, context=_FakeContext()):
            pytest.skip("timer query ring unavailable in this environment")

        inner = GLTimerQueryRing(owner="inner", generation=1, ring_size=2)
        if not inner.initialize(gl, context=_FakeContext()):
            pytest.skip("timer query ring unavailable in this environment")

        assert ring.begin(gl, label="outer") is True
        # An unguarded inner begin is exactly what produced begin_error:GLError.
        inner.begin(gl, label="inner")
        assert gl.errors == 1
        ring.end(gl)

    def test_guarded_inner_query_produces_no_gl_error(self):
        """With the guard, the inner ring never calls begin at all."""
        gl = _FakeGL()
        outer = GLTimerQueryRing(owner="outer", generation=1, ring_size=2)
        if not outer.initialize(gl, context=_FakeContext()):
            pytest.skip("timer query ring unavailable in this environment")
        assert outer.begin(gl, label="outer") is True

        compositor = SimpleNamespace(_gpu_timer_queries=outer)
        overlay = SimpleNamespace(_publication_target_compositor=lambda: compositor)

        if SpotifyBarsGLOverlay._compositor_gpu_query_active(overlay):
            pass  # visualizer sampling skipped, no begin issued
        else:  # pragma: no cover - would be the bug
            pytest.fail("guard failed to detect the outer query")

        outer.end(gl)
        assert gl.errors == 0, "the guarded path must produce no GL error"


class TestCpuMetricsSurvive:
    def test_cpu_paint_and_state_to_paint_accounting_is_unconditional(self):
        """Skipping GPU sampling must not remove CPU metrics."""
        source = inspect.getsource(SpotifyBarsGLOverlay.paint_layer)
        assert "_perf_paint_cpu_ms" in source
        assert "_perf_state_to_paint_ms" in source

    def test_a_stable_skip_reason_is_recorded(self):
        source = inspect.getsource(SpotifyBarsGLOverlay.paint_layer)
        assert "shared_context_outer_query" in source, (
            "PERF reporting needs a stable reason rather than a silent skip"
        )

    def test_no_new_timestamp_query_subsystem_was_added(self):
        source = inspect.getsource(SpotifyBarsGLOverlay.paint_layer)
        for forbidden in ("GL_TIMESTAMP", "glQueryCounter"):
            assert forbidden not in source

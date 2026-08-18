"""P4-RHI-C: an established compositor may not sit silently in QPainter fallback.

Active-transition shader failure was already loud. The steady retained-base path
was not: a healthy compositor could drop to the QPainter base-image path and stay
there with no record at all, which is exactly the "change lands with no effect and
the fallback explains it" failure mode the guardrails call out.

These bars pin the state-change contract:

* legitimate startup / no-base / not-ready states stay quiet;
* an established compositor entering fallback records once, loudly;
* repeated fallback frames with the same reason never spam;
* recovery records once and clears the latch;
* active-transition fallback keeps its existing loud signature behaviour;
* PERF being on or off changes none of it.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from rendering.gl_compositor_pkg import paint, shader_dispatch


def _widget(*, ready: bool = True, reason: str | None = None):
    return SimpleNamespace(
        _gl_state=SimpleNamespace(is_ready=lambda: ready),
        _retained_base_fallback_reason=reason,
        _gl_disabled_for_session=False,
    )


def _records(caplog):
    return [r for r in caplog.records if "[GL PAINT][FALLBACK]" in r.getMessage()]


class TestQuietWhenFallbackIsLegitimate:
    def test_no_base_image_is_silent(self, caplog):
        widget = _widget(reason="no_base_image")
        with caplog.at_level(logging.DEBUG):
            for _ in range(20):
                paint._note_retained_base_fallback(widget)
        assert _records(caplog) == []
        assert getattr(widget, "_retained_base_fallback_latch", None) is None

    def test_gl_unavailable_is_silent(self, caplog):
        widget = _widget(reason="gl_unavailable")
        with caplog.at_level(logging.DEBUG):
            paint._note_retained_base_fallback(widget)
        assert _records(caplog) == []

    def test_not_ready_compositor_is_silent(self, caplog):
        """Startup before GL READY must never warn."""
        widget = _widget(ready=False, reason="pipeline_unavailable")
        with caplog.at_level(logging.DEBUG):
            for _ in range(10):
                paint._note_retained_base_fallback(widget)
        assert _records(caplog) == []
        assert getattr(widget, "_retained_base_fallback_latch", None) is None


class TestEstablishedFallbackIsLoudAndBounded:
    def test_established_failure_records_once_despite_repeated_frames(self, caplog):
        widget = _widget(reason="texture_cache_miss")
        with caplog.at_level(logging.DEBUG):
            for _ in range(120):
                paint._note_retained_base_fallback(widget)

        records = _records(caplog)
        assert len(records) == 1, "repeated fallback frames must not spam"
        assert records[0].levelno >= logging.ERROR
        assert "texture_cache_miss" in records[0].getMessage()
        assert widget._retained_base_fallback_latch == "texture_cache_miss"
        assert widget._retained_base_fallback_frames == 119

    def test_a_changed_reason_records_again(self, caplog):
        widget = _widget(reason="texture_cache_miss")
        with caplog.at_level(logging.DEBUG):
            paint._note_retained_base_fallback(widget)
            for _ in range(5):
                paint._note_retained_base_fallback(widget)
            widget._retained_base_fallback_reason = "program_missing"
            paint._note_retained_base_fallback(widget)

        records = _records(caplog)
        assert len(records) == 2
        assert "program_missing" in records[1].getMessage()
        # The suppressed count of the previous state is reported, not lost.
        assert "suppressed_previous_frames=5" in records[1].getMessage()

    def test_each_distinct_failure_reason_is_reachable(self):
        """The reasons the latch reports must be the ones the path can produce."""
        comp = SimpleNamespace()
        for reason in (
            "gl_unavailable",
            "gl_disabled_for_session",
            "no_base_image",
            "pipeline_unavailable",
            "program_missing",
            "texture_manager_missing",
            "texture_cache_miss",
            "draw_rejected",
            "draw_exception",
        ):
            assert shader_dispatch._retained_base_unavailable(comp, reason) is False
            assert comp._retained_base_fallback_reason == reason


class TestRecovery:
    def test_recovery_records_once_and_clears_the_latch(self, caplog):
        widget = _widget(reason="draw_rejected")
        with caplog.at_level(logging.DEBUG):
            for _ in range(4):
                paint._note_retained_base_fallback(widget)
            paint._note_retained_base_recovered(widget)
            # Further healthy frames must stay quiet.
            for _ in range(10):
                paint._note_retained_base_recovered(widget)

        records = _records(caplog)
        assert len(records) == 2, "one fallback record and exactly one recovery"
        assert records[1].levelno == logging.INFO
        assert "recovered" in records[1].getMessage()
        assert widget._retained_base_fallback_latch is None

    def test_recovery_without_a_prior_fallback_is_silent(self, caplog):
        widget = _widget()
        with caplog.at_level(logging.DEBUG):
            for _ in range(10):
                paint._note_retained_base_recovered(widget)
        assert _records(caplog) == []

    def test_fallback_can_latch_again_after_recovery(self, caplog):
        widget = _widget(reason="draw_rejected")
        with caplog.at_level(logging.DEBUG):
            paint._note_retained_base_fallback(widget)
            paint._note_retained_base_recovered(widget)
            paint._note_retained_base_fallback(widget)
        assert len(_records(caplog)) == 3


class TestPerfIndependence:
    @pytest.mark.parametrize("perf_enabled", [False, True])
    def test_behaviour_is_identical_with_perf_off_and_on(self, caplog, monkeypatch, perf_enabled):
        monkeypatch.setattr(paint, "is_perf_metrics_enabled", lambda: perf_enabled)
        widget = _widget(reason="pipeline_unavailable")
        with caplog.at_level(logging.DEBUG):
            for _ in range(30):
                paint._note_retained_base_fallback(widget)
            paint._note_retained_base_recovered(widget)

        records = _records(caplog)
        assert len(records) == 2
        assert widget._retained_base_fallback_latch is None


class TestActiveTransitionFallbackUnchanged:
    def test_transition_fallback_keeps_its_loud_signature_behaviour(self, caplog):
        widget = SimpleNamespace(
            _last_shader_path_failure="capability_unavailable",
            _gl_disabled_for_session=False,
            _use_shaders=True,
            _current_transition_name="Slide",
            _last_shader_fallback_signature=None,
            _shader_fallback_suppressed_count=0,
        )
        with caplog.at_level(logging.DEBUG):
            for _ in range(25):
                paint._log_shader_fallback_once(widget, ["slide"])

        records = [
            r for r in caplog.records
            if "All active shader paths failed" in r.getMessage()
        ]
        assert len(records) == 1
        assert records[0].levelno >= logging.ERROR

    def test_the_two_fallback_owners_are_separate(self):
        """Steady and transition fallback must not share one latch."""
        widget = _widget(reason="draw_rejected")
        widget._last_shader_fallback_signature = None
        widget._shader_fallback_suppressed_count = 0
        widget._last_shader_path_failure = ""
        widget._use_shaders = True
        widget._current_transition_name = None

        paint._note_retained_base_fallback(widget)
        assert widget._retained_base_fallback_latch == "draw_rejected"
        assert widget._last_shader_fallback_signature is None


class TestRenderPathWiring:
    def test_steady_fallback_and_recovery_are_wired_into_the_render_path(self):
        """The latch is worthless if the render path never calls it."""
        import ast
        import inspect
        import textwrap

        source = textwrap.dedent(inspect.getsource(paint.paintGL_impl))
        called = {
            node.func.id
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "_note_retained_base_fallback" in called
        assert "_note_retained_base_recovered" in called
        assert "_log_shader_fallback_once" in called

    def test_steady_fallback_is_not_reported_for_active_transitions(self):
        """Transition frames keep the existing owner, not the steady one."""
        import inspect

        source = inspect.getsource(paint.paintGL_impl)
        transition_branch = source.index("_log_shader_fallback_once")
        steady_branch = source.index("_note_retained_base_fallback")
        between = source[transition_branch:steady_branch]
        assert "else:" in between, (
            "steady fallback must be the else-branch of the active-transition case"
        )

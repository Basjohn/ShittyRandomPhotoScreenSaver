from __future__ import annotations

from types import SimpleNamespace

from rendering.gl_compositor_pkg import paint
from rendering.gl_compositor_pkg.gl_lifecycle import gl_pipeline_has_live_resources


class _FakeTimerQueries:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def poll(self, gl_api) -> None:
        self.calls.append(("poll", gl_api))

    def begin(self, gl_api, *, label: str) -> bool:
        self.calls.append(("begin", gl_api, label))
        return True

    def end(self, gl_api) -> None:
        self.calls.append(("end", gl_api))


def test_compositor_gpu_query_wraps_existing_paint_without_scheduling(monkeypatch) -> None:
    timer_queries = _FakeTimerQueries()
    calls: list[str] = []
    fake_gl = object()

    class _Widget:
        _frame_state = None
        _gpu_timer_queries = timer_queries
        _gpu_timer_query_last_log_ts = 10**12
        _current_transition_name = "Burn"
        _paint_warning_last_ts = 0.0

        _gl_state = SimpleNamespace(
            is_ready=lambda: True,
            get_transition_history=lambda limit=5: (),
        )

        def _record_paint_start_metrics(self, _started: float) -> None:
            calls.append("metrics_start")

        def _record_paint_metrics(self, *_args, **_kwargs) -> None:
            calls.append("metrics_end")

    monkeypatch.setattr(paint, "gl", fake_gl)
    monkeypatch.setattr(paint, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(paint, "paintGL_impl", lambda _widget: calls.append("paint"))
    monkeypatch.setattr(paint, "_mark_widget_update_consumed", lambda _widget: None)

    paint.handle_paintGL(_Widget())

    assert timer_queries.calls == [
        ("poll", fake_gl),
        ("begin", fake_gl, "burn"),
        ("end", fake_gl),
    ]
    assert calls[:2] == ["metrics_start", "paint"]
    assert calls[-1] == "metrics_end"


def test_compositor_gpu_label_falls_back_to_active_descriptor_then_steady() -> None:
    active = SimpleNamespace(
        _current_transition_name=None,
        _blockspin=object(),
    )
    assert paint._gpu_timer_query_label(active) == "blockspin"

    steady = SimpleNamespace(_current_transition_name=None)
    assert paint._gpu_timer_query_label(steady) == "steady"


def test_compositor_live_resource_probe_includes_timer_query_handles() -> None:
    timer_queries = SimpleNamespace(has_live_queries=lambda: True)
    widget = SimpleNamespace(
        _gl_pipeline=None,
        _geometry_manager=None,
        _program_cache=None,
        _texture_manager=None,
        _gpu_timer_queries=timer_queries,
    )

    assert gl_pipeline_has_live_resources(widget) is True

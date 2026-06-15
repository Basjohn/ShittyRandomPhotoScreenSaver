from core.performance.frame_budget import FrameBudget, FrameBudgetConfig


def test_frame_budget_logs_first_spike_immediately(monkeypatch):
    budget = FrameBudget(FrameBudgetConfig(target_fps=60, spike_threshold_ms=33.33))
    warnings = []

    times = iter([1.0, 1.040])
    monkeypatch.setattr("core.performance.frame_budget.is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr("core.performance.frame_budget.time.perf_counter", lambda: next(times))
    monkeypatch.setattr("core.performance.frame_budget.logger.warning", lambda msg, *args: warnings.append(msg % args))

    budget.begin_frame()
    budget.begin_frame()

    assert warnings == ["[PERF] [FRAME] Frame spike: 40.0ms (target: 16.7ms)"]


def test_frame_budget_throttles_spike_warning_bursts(monkeypatch):
    budget = FrameBudget(FrameBudgetConfig(target_fps=60, spike_threshold_ms=33.33))
    warnings = []

    # First spike logs immediately, next two are suppressed inside cooldown,
    # final spike after cooldown emits an aggregated burst warning.
    times = iter([1.0, 1.040, 1.080, 1.120, 1.560])
    monkeypatch.setattr("core.performance.frame_budget.is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr("core.performance.frame_budget.time.perf_counter", lambda: next(times))
    monkeypatch.setattr("core.performance.frame_budget.logger.warning", lambda msg, *args: warnings.append(msg % args))

    budget.begin_frame()
    budget.begin_frame()
    budget.begin_frame()
    budget.begin_frame()
    budget.begin_frame()

    assert warnings == [
        "[PERF] [FRAME] Frame spike: 40.0ms (target: 16.7ms)",
        "[PERF] [FRAME] Frame spike burst: count=3 max=440.0ms last=440.0ms (target: 16.7ms)",
    ]

"""Offline coverage for the A/B/C harness scorer + classifier.

Builds synthetic diagnostic logs (real line grammar + driver markers) and drives
the scorer/classifier so the corrective contract is verified without a live app:
named windows kept distinct (both C windows), fail-closed validity (INVALID
marker, missing/short/sparse window, unhealthy freshness), the >=60 s persistence
requirement, metric-matched C recovery, and the >=3 matched-valid-reps gate.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import visualizer_switch_abc_harness as h  # noqa: E402

_BASE = 1_700_000_000  # fixed epoch base for deterministic timestamps


def test_line_epoch_parses_seconds_and_millis_formats():
    # The app's file handlers emit seconds precision; the harness must parse both
    # that and the comma-millis form. A None here would zero every window's samples.
    secs = "2026-09-12 15:04:41 - core.performance.event_loop_recorder - INFO - x"
    millis = "2026-09-12 15:04:41,123 - core.performance - INFO - x"
    e_secs = h._line_epoch(secs)
    e_millis = h._line_epoch(millis)
    assert e_secs is not None and e_millis is not None
    assert abs((e_millis - e_secs) - 0.123) < 1e-6


def _ts(epoch: float) -> str:
    secs = int(epoch)
    ms = int(round((epoch - secs) * 1000))
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(secs)) + f",{ms:03d}"


def _value(spec, offset: float) -> float:
    return float(spec(offset)) if callable(spec) else float(spec)


def _window_lines(
    start: float,
    *,
    duration: float,
    p99,
    skip,
    label: str,
    rolling_p99=None,
    rev_hz=90.0,
    age=8.0,
):
    lines: list[str] = []
    # Match the real recorder report cadence so persistence represents actual
    # non-overlapping report periods rather than synthetic one-second duplicates.
    step = 15.0
    offset = 0.0
    while offset < duration:
        epoch = start + offset
        prefix = f"{_ts(epoch)} INFO "
        period_p99 = _value(p99, offset)
        rolling = period_p99 if rolling_p99 is None else _value(rolling_p99, offset)
        lines.append(
            prefix
            + "[PERF] [EVENT LOOP] summary samples=100 retained=100 interval_ms=16 "
            + f"late_p50_ms=0.50 late_p90_ms=1.00 late_p95_ms={rolling * 0.8:.2f} "
            + f"late_p99_ms={rolling:.2f} late_max_ms={rolling * 1.5:.2f} "
            + "over_25_ms=0 over_50_ms=0 over_100_ms=0 "
            + f"period_samples=300 period_elapsed_s=15.000 period_epoch={epoch:.3f} period_p50_ms=0.50 "
            + f"period_p90_ms=1.00 period_p95_ms={period_p99 * 0.8:.2f} "
            + f"period_p99_ms={period_p99:.2f} period_max_ms={period_p99 * 1.5:.2f} "
            + "period_over_25_ms=0 period_over_50_ms=0 period_over_100_ms=0 "
            + f"score_reset_seq=1 score_label={label} outcome=sampled"
        )
        lines.append(
            prefix
            + "[PERF] [PERF_HUD] screen=0 scene_fps=60.00 dt_max_ms=3.00 "
            + f"pacer_target_hz=60.000 pacer_skip_pct={_value(skip, offset):.2f} "
            + "transition=idle viz_mode=bubble "
            + f"viz_draw_fps=59.90 viz_revision_hz={_value(rev_hz, offset):.2f} "
            + f"viz_age_ms={_value(age, offset):.2f} viz_geometry_mismatches=0"
        )
        lines.append(prefix + "[SPOTIFY_VIS] integration_ratio=1.000 integration_failures=0")
        offset += step
    return lines


def _marker(condition: str, phase: str, state: str, epoch: float) -> str:
    return (
        f"{_ts(epoch)} INFO [ABC] condition={condition} phase={phase} "
        f"state={state} epoch={epoch:.3f} runtime_generation=2"
    )


def _write_run(
    tmp_path: Path,
    name: str,
    condition: str,
    windows: dict[str, dict],
    *,
    invalid_reason: str | None = None,
) -> Path:
    """windows: {window_name: {start_offset, duration, p99, skip, rev_hz?, age?}}."""
    lines = [f"{_ts(_BASE)} INFO [ABC] condition={condition} phase=driver state=start epoch={_BASE:.3f} runtime_generation=1"]
    if invalid_reason is not None:
        lines.append(
            f"{_ts(_BASE + 1)} ERROR [ABC] condition={condition} INVALID "
            f"reason={invalid_reason} epoch={_BASE + 1:.3f} runtime_generation=2"
        )
    for phase, spec in windows.items():
        start = _BASE + float(spec["start_offset"])
        duration = float(spec["duration"])
        lines.append(_marker(condition, phase, "start", start))
        lines.extend(
            _window_lines(
                start,
                duration=duration,
                p99=spec["p99"],
                skip=spec["skip"],
                label=phase,
                rolling_p99=spec.get("rolling_p99"),
                rev_hz=spec.get("rev_hz", 90.0),
                age=spec.get("age", 8.0),
            )
        )
        lines.append(_marker(condition, phase, "end", start + duration))
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _a_run(tmp_path, name="a.log", *, p99=1.0, skip=0.5, **kw):
    return _write_run(tmp_path, name, "A",
                      {"steady_A": {"start_offset": 100, "duration": 120, "p99": p99, "skip": skip, **kw}})


def _b_run(tmp_path, name="b.log", *, p99=5.0, skip=0.6, **kw):
    return _write_run(tmp_path, name, "B",
                      {"steady_B": {"start_offset": 100, "duration": 120, "p99": p99, "skip": skip, **kw}})


def _c_run(tmp_path, name="c.log", *, pre_p99=5.0, post_p99=1.2, pre_skip=0.6, post_skip=0.6):
    return _write_run(
        tmp_path, name, "C",
        {
            "steady_C_pre": {"start_offset": 100, "duration": 120, "p99": pre_p99, "skip": pre_skip},
            "steady_C_post": {"start_offset": 400, "duration": 120, "p99": post_p99, "skip": post_skip},
        },
    )


# --- scoring / validity -----------------------------------------------------


def test_score_run_valid_b(tmp_path):
    run = h.score_run(_b_run(tmp_path))
    assert run["valid"] is True
    assert run["condition"] == "B"
    window = run["windows"]["steady_B"]
    assert window["eventloop_p99_ms"]["mean"] == pytest.approx(5.0, abs=0.01)
    assert window["viz_revision_hz"]["mean"] == pytest.approx(90.0, abs=0.01)


def test_named_windows_keeps_both_c_windows(tmp_path):
    run = h.score_run(_c_run(tmp_path))
    assert run["valid"] is True
    assert set(run["windows"]) == {"steady_C_pre", "steady_C_post"}
    assert run["windows"]["steady_C_pre"]["eventloop_p99_ms"]["mean"] == pytest.approx(5.0, abs=0.01)
    assert run["windows"]["steady_C_post"]["eventloop_p99_ms"]["mean"] == pytest.approx(1.2, abs=0.01)


def test_scoring_uses_window_local_period_not_contaminated_rolling_p99(tmp_path):
    path = _write_run(
        tmp_path,
        "contaminated.log",
        "B",
        {
            "steady_B": {
                "start_offset": 100,
                "duration": 120,
                "p99": 3.0,
                "rolling_p99": 60.0,
                "skip": 0.5,
            }
        },
    )
    run = h.score_run(path)
    assert run["valid"] is True
    assert run["windows"]["steady_B"]["eventloop_p99_ms"]["mean"] == pytest.approx(3.0)


def test_old_rolling_only_event_loop_log_fails_closed(tmp_path):
    path = _b_run(tmp_path, "old.log")
    text = path.read_text(encoding="utf-8")
    text = "\n".join(
        line.split(" period_samples=", 1)[0] + " outcome=sampled"
        if "[EVENT LOOP] summary" in line
        else line
        for line in text.splitlines()
    ) + "\n"
    path.write_text(text, encoding="utf-8")
    run = h.score_run(path)
    assert run["valid"] is False
    assert "event-loop samples" in run["reason"]



def test_wrong_scoring_window_label_is_rejected(tmp_path):
    path = _b_run(tmp_path, "wrong-label.log")
    text = path.read_text(encoding="utf-8").replace(
        "score_label=steady_B", "score_label=steady_A"
    )
    path.write_text(text, encoding="utf-8")
    run = h.score_run(path)
    assert run["valid"] is False
    assert "event-loop samples" in run["reason"]

def test_invalid_marker_makes_run_invalid(tmp_path):
    path = _write_run(
        tmp_path, "inv.log", "B",
        {"steady_B": {"start_offset": 100, "duration": 120, "p99": 5.0, "skip": 0.6}},
        invalid_reason="mode transition did not complete: spectrum",
    )
    run = h.score_run(path)
    assert run["valid"] is False
    assert "INVALID" in run["reason"] and "spectrum" in run["reason"]


def test_missing_required_window_is_invalid(tmp_path):
    # A C run missing the post-recreation window.
    path = _write_run(
        tmp_path, "cmiss.log", "C",
        {"steady_C_pre": {"start_offset": 100, "duration": 120, "p99": 5.0, "skip": 0.6}},
    )
    run = h.score_run(path)
    assert run["valid"] is False
    assert "steady_C_post" in run["reason"]


def test_short_window_is_invalid(tmp_path):
    run = h.score_run(
        _write_run(tmp_path, "short.log", "A",
                   {"steady_A": {"start_offset": 100, "duration": 30, "p99": 1.0, "skip": 0.5}})
    )
    assert run["valid"] is False
    assert "too short" in run["reason"]


def test_unhealthy_freshness_is_invalid(tmp_path):
    run = h.score_run(_b_run(tmp_path, "stall.log", rev_hz=10.0))  # revision starved
    assert run["valid"] is False
    assert "starved" in run["reason"] or "revision" in run["reason"]


def test_high_source_age_is_invalid(tmp_path):
    run = h.score_run(_b_run(tmp_path, "aged.log", age=500.0))
    assert run["valid"] is False
    assert "age" in run["reason"]


# --- classification ---------------------------------------------------------


def test_classify_insufficient_reps(tmp_path):
    a = [h.score_run(_a_run(tmp_path, "a1.log"))]
    b = [h.score_run(_b_run(tmp_path, "b1.log"))]
    c = [h.score_run(_c_run(tmp_path, "c1.log"))]
    result = h.classify(a, b, c)
    assert result["verdict"] == "insufficient_valid_reps"


def _triples(tmp_path, b_kwargs, c_kwargs, a_kwargs=None):
    a = [h.score_run(_a_run(tmp_path, f"a{i}.log", **(a_kwargs or {}))) for i in range(3)]
    b = [h.score_run(_b_run(tmp_path, f"b{i}.log", **b_kwargs)) for i in range(3)]
    c = [h.score_run(_c_run(tmp_path, f"c{i}.log", **c_kwargs)) for i in range(3)]
    return a, b, c


def test_classify_swap_sensitive(tmp_path):
    a, b, c = _triples(
        tmp_path,
        b_kwargs={"p99": 5.0},
        c_kwargs={"pre_p99": 5.0, "post_p99": 1.2},
    )
    result = h.classify(a, b, c)
    assert result["verdict"] == "swap_sensitive"
    assert result["b_vs_a_regressed_count"] == 3
    assert result["c_cleared_count"] == 3


def test_classify_not_reproduced_when_b_matches_a(tmp_path):
    a, b, c = _triples(
        tmp_path,
        b_kwargs={"p99": 1.1},  # within noise of A (1.0)
        c_kwargs={"pre_p99": 1.1, "post_p99": 1.0},
    )
    result = h.classify(a, b, c)
    assert result["verdict"] == "not_reproduced"


def test_classify_b_regressed_c_did_not_clear(tmp_path):
    a, b, c = _triples(
        tmp_path,
        b_kwargs={"p99": 5.0},
        c_kwargs={"pre_p99": 5.0, "post_p99": 4.8},  # recreation barely helps
    )
    result = h.classify(a, b, c)
    assert result["verdict"] == "b_regressed_c_did_not_clear"


def test_recovery_is_metric_matched_to_the_trigger(tmp_path):
    # B regresses ONLY on skip; recovery must be computed on skip, not p99.
    a, b, c = _triples(
        tmp_path,
        b_kwargs={"p99": 1.1, "skip": 6.0},
        c_kwargs={"pre_p99": 1.1, "post_p99": 1.05, "pre_skip": 6.0, "post_skip": 0.6},
    )
    result = h.classify(a, b, c)
    pair = result["pairs"][0]
    assert pair["b_vs_a"]["triggered"] == ["skip"]
    assert set(pair["c_recovery_fraction_by_metric"]) == {"skip"}
    assert result["verdict"] == "swap_sensitive"


def test_persistence_required_spike_does_not_count(tmp_path):
    # p99 elevated only in the first 20 s, healthy afterwards -> not persistent.
    def spike(offset):
        return 6.0 if offset < 20.0 else 1.0

    a = [h.score_run(_a_run(tmp_path, f"a{i}.log")) for i in range(3)]
    b = [h.score_run(_b_run(tmp_path, f"b{i}.log", p99=spike)) for i in range(3)]
    c = [h.score_run(_c_run(tmp_path, f"c{i}.log")) for i in range(3)]
    result = h.classify(a, b, c)
    assert result["b_vs_a_regressed_count"] == 0
    assert result["verdict"] == "not_reproduced"

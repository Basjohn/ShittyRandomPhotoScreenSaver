"""The GPU timer harness's judgements (timer_check.py), as pure functions over its records so tests can hold them to
their negative controls without a built module (tests/test_native_core_timer.py).

- scaling: a pass drawn N times must take N times one draw plus a constant: a least-squares line through the medians,
  its fit, its slope against the noise, and every median within a tolerance of the line;
- flat: the negative control's empty bracket must not scale with N;
- agreement: two timers of one pass (the per-pass figure and QRhi's whole frame; the Vulkan and OpenGL forms) agree
  within a stated tolerance;
- off: a host whose timer is off holds no timer and no query object, and no edge touched one;
- latched: every result is read at a later frame edge than its own, no read waited, and the reads cost little CPU.
"""
from __future__ import annotations

import statistics
from typing import Iterable, Mapping, Sequence

# The tolerances the harness states (summary.json carries them beside every verdict).
SCALING_MIN_R2 = 0.98             # the line explains the medians
SCALING_RESIDUAL = 0.15           # each median within 15 % of the line ...
SCALING_RESIDUAL_FLOOR_MS = 0.02  # ... or within 0.02 ms of it
SCALING_MIN_SLOPE_MS = 0.005      # one draw costs measurably more than nothing
FLAT_MAX_SLOPE_RATIO = 0.1        # an empty bracket grows by less than a tenth of the pass's per-draw cost
AGREEMENT_RATIO = 0.10            # a pass's figure and its frame's within 10 % of the frame ...
AGREEMENT_FLOOR_MS = 0.15         # ... or 0.15 ms (Qt Quick's own pass and the frame's edges)
FORMS_RATIO = (0.67, 1.5)         # the Vulkan form's per-draw cost over the OpenGL form's
RESOLVE_MAX_MS = 0.5              # one edge's non-blocking reads, at most
STALL_MIN_MS = 1.0                # the waiting control must show at least this, or it shows nothing


def median_ms(values_ns: Iterable[int]) -> float | None:
    values = [v / 1e6 for v in values_ns]
    return statistics.median(values) if values else None


def fit_line(xs: Sequence[float], ys: Sequence[float]) -> dict:
    """Least squares y = intercept + slope * x, with r^2."""
    n = len(xs)
    if n < 2:
        return {"slope": None, "intercept": None, "r2": None}
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 0.0
    return {"slope": slope, "intercept": intercept, "r2": r2}


def scaling_verdict(medians: Mapping[int, float]) -> dict:
    """``medians``: draws -> median ms. Proportional: a good line, a measurable slope, every point on it."""
    xs = sorted(medians)
    ys = [medians[x] for x in xs]
    fit = fit_line([float(x) for x in xs], ys)
    if fit["slope"] is None:
        return {"pass": False, "fit": fit, "error": "fewer than two draw counts"}
    residuals = {}
    for x, y in zip(xs, ys):
        predicted = fit["intercept"] + fit["slope"] * x
        residuals[x] = {"measured": y, "predicted": predicted,
                        "ok": abs(y - predicted) <= max(SCALING_RESIDUAL * predicted, SCALING_RESIDUAL_FLOOR_MS)}
    checks = {"line_fits": fit["r2"] >= SCALING_MIN_R2,
              "a_draw_costs_measurably": fit["slope"] >= SCALING_MIN_SLOPE_MS,
              "every_count_on_the_line": all(r["ok"] for r in residuals.values()),
              "largest_over_smallest_grows": ys[-1] > ys[0] * 2.0}
    return {"pass": all(checks.values()), "fit": fit, "residuals": residuals, "checks": checks}


def flat_verdict(medians: Mapping[int, float], pass_slope: float | None) -> dict:
    """The negative control: an empty bracket in front of the same pass does not grow with N."""
    xs = sorted(medians)
    fit = fit_line([float(x) for x in xs], [medians[x] for x in xs])
    ok = (fit["slope"] is not None and pass_slope is not None and pass_slope > 0
          and abs(fit["slope"]) <= FLAT_MAX_SLOPE_RATIO * pass_slope)
    return {"pass": bool(ok), "fit": fit, "pass_slope": pass_slope}


def agreement_verdict(pass_ms: float | None, frame_ms: float | None) -> dict:
    """The per-pass figure inside its frame's: never more than the frame (beyond the tolerance), and the frame's rest small
    when the pass dominates it."""
    if pass_ms is None or frame_ms is None:
        return {"pass": False, "pass_ms": pass_ms, "frame_ms": frame_ms, "error": "a figure is missing"}
    tolerance = max(AGREEMENT_RATIO * frame_ms, AGREEMENT_FLOOR_MS)
    return {"pass": abs(frame_ms - pass_ms) <= tolerance, "pass_ms": pass_ms, "frame_ms": frame_ms,
            "tolerance_ms": tolerance}


def forms_verdict(vulkan_slope: float | None, opengl_slope: float | None) -> dict:
    """The two native forms time the same pass: per-draw cost ratio within FORMS_RATIO."""
    if not vulkan_slope or not opengl_slope:
        return {"pass": False, "error": "a form's slope is missing", "vulkan": vulkan_slope, "opengl": opengl_slope}
    ratio = vulkan_slope / opengl_slope
    return {"pass": FORMS_RATIO[0] <= ratio <= FORMS_RATIO[1], "ratio": ratio, "vulkan": vulkan_slope,
            "opengl": opengl_slope, "bounds": list(FORMS_RATIO)}


def off_verdict(driver: Mapping, live: Mapping, *, edges_before: int, samples: int) -> dict:
    """Off is free: the driver holds no timer, no edge since ``edges_before`` touched one, nothing was queued, and the
    process holds no timer or query object."""
    checks = {"driver_holds_no_timer": driver.get("gpu_timer") is None,
              "no_edge_touched_a_timer": int(driver.get("gpu_timer_edges", 0)) == int(edges_before),
              "nothing_queued": samples == 0,
              "no_timer_in_the_process": int(live.get("timers", -1)) == 0,
              "no_query_object_in_the_process": int(live.get("query_pools", -1)) == 0
              and int(live.get("queries", -1)) == 0}
    return {"pass": all(checks.values()), "checks": checks}


def latched_verdict(timer: Mapping, latencies: Sequence[int], *, require_late_read: bool) -> dict:
    """Read without stalling: every result read at a later edge than its own, none waited for, the reads cheap; with
    ``require_late_read`` (a GPU-bound real window) some result was not ready at the next edge and was read later."""
    resolve_ms = int(timer.get("resolve_ns_max", 0)) / 1e6
    checks = {"results_arrived": bool(latencies),
              "never_read_in_its_own_frame": bool(latencies) and min(latencies) >= 1,
              "no_read_waited": int(timer.get("blocking_reads", -1)) == 0,
              "reads_cost_little": resolve_ms <= RESOLVE_MAX_MS}
    if require_late_read:
        checks["a_result_not_ready_was_read_later"] = (int(timer.get("not_ready_reads", 0)) > 0
                                                       and max(latencies or [0]) >= 2)
    return {"pass": all(checks.values()), "checks": checks, "resolve_ms_max": resolve_ms,
            "latency_min": min(latencies) if latencies else None, "latency_max": max(latencies) if latencies else None}


def stall_control_verdict(control_timer: Mapping, latched_timer: Mapping) -> dict:
    """The negative control: the same frames read with a blocking wait must show it (reads waited, and an edge's reads
    cost far more CPU than the latched reads did)."""
    control_ms = int(control_timer.get("resolve_ns_max", 0)) / 1e6
    latched_ms = int(latched_timer.get("resolve_ns_max", 0)) / 1e6
    ok = (int(control_timer.get("blocking_reads", 0)) > 0 and control_ms >= STALL_MIN_MS
          and control_ms >= 4.0 * max(latched_ms, 1e-6))
    return {"pass": bool(ok), "control_resolve_ms_max": control_ms, "latched_resolve_ms_max": latched_ms,
            "blocking_reads": int(control_timer.get("blocking_reads", 0))}


__all__ = ["AGREEMENT_FLOOR_MS", "AGREEMENT_RATIO", "FLAT_MAX_SLOPE_RATIO", "FORMS_RATIO", "RESOLVE_MAX_MS",
           "SCALING_MIN_R2", "SCALING_MIN_SLOPE_MS", "SCALING_RESIDUAL", "SCALING_RESIDUAL_FLOOR_MS", "STALL_MIN_MS",
           "agreement_verdict", "fit_line", "flat_verdict", "forms_verdict", "latched_verdict", "median_ms",
           "off_verdict", "scaling_verdict", "stall_control_verdict"]

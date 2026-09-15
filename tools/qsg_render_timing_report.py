#!/usr/bin/env python3
"""Summarize Qt Quick native scenegraph timing from ``screensaver_qml.log``.

The retired R-87 ``--qsg-render-timing`` diagnostic set ``QSG_RENDER_TIMING=1``
before Qt Quick bootstrap. Qt then emits native render-loop timing messages via
its own message handler. SRPSS already captures that handler into
``screensaver_qml.log``; this tool reduces the verbose per-frame text to a small
summary so agents never need to reason from thousands of log lines manually.

Supported Qt output includes the Qt 6 threaded-render-loop form::

    syncAndRender: start, elapsed since last call: 11 ms
    syncAndRender: frame rendered in 8ms, sync=2, render=5, swap=1

and the older ``window Time: sinceLast=..., sync=..., first render=...`` form.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import statistics
from typing import Iterable

_FRAME_RE = re.compile(
    r"syncAndRender:\s*frame rendered in\s*(?P<total>\d+)ms,\s*"
    r"sync=(?P<sync>\d+),\s*render=(?P<render>\d+),\s*swap=(?P<swap>\d+)"
)
_START_RE = re.compile(
    r"syncAndRender:\s*start,\s*elapsed since last call:\s*(?P<since>\d+)\s*ms"
)
_LEGACY_RE = re.compile(
    r"window Time:\s*sinceLast=(?P<since>\d+),\s*sync=(?P<sync>\d+),\s*"
    r"first render=(?P<render>\d+),\s*after final swap=(?P<swap>\d+)"
)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(ordered[lo])
    frac = pos - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def _summary(label: str, values: list[float]) -> str:
    if not values:
        return f"{label}_ms n=0"
    return (
        f"{label}_ms n={len(values)} "
        f"median={statistics.median(values):.3f} "
        f"p95={_percentile(values, 0.95):.3f} "
        f"p99={_percentile(values, 0.99):.3f} "
        f"max={max(values):.3f}"
    )


def parse_lines(lines: Iterable[str]) -> dict[str, list[float]]:
    metrics: dict[str, list[float]] = {
        "frame_total": [],
        "sync": [],
        "render": [],
        "swap": [],
        "since_last": [],
    }
    for line in lines:
        match = _FRAME_RE.search(line)
        if match:
            metrics["frame_total"].append(float(match.group("total")))
            metrics["sync"].append(float(match.group("sync")))
            metrics["render"].append(float(match.group("render")))
            metrics["swap"].append(float(match.group("swap")))
            continue
        match = _START_RE.search(line)
        if match:
            metrics["since_last"].append(float(match.group("since")))
            continue
        match = _LEGACY_RE.search(line)
        if match:
            since = float(match.group("since"))
            sync = float(match.group("sync"))
            render = float(match.group("render"))
            swap = float(match.group("swap"))
            metrics["since_last"].append(since)
            metrics["sync"].append(sync)
            metrics["render"].append(render)
            metrics["swap"].append(swap)
            metrics["frame_total"].append(sync + render + swap)
    return metrics


def render_report(metrics: dict[str, list[float]]) -> str:
    frame_count = len(metrics["frame_total"])
    lines = [f"qsg_native_frames={frame_count}"]
    for label in ("since_last", "frame_total", "sync", "render", "swap"):
        lines.append(_summary(label, metrics[label]))
    if frame_count:
        sync = metrics["sync"]
        render = metrics["render"]
        swap = metrics["swap"]
        total_component_ms = sum(sync) + sum(render) + sum(swap)
        if total_component_ms > 0:
            lines.append(
                "component_share_pct "
                f"sync={100.0 * sum(sync) / total_component_ms:.2f} "
                f"render={100.0 * sum(render) / total_component_ms:.2f} "
                f"swap={100.0 * sum(swap) / total_component_ms:.2f}"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("qml_log", type=Path)
    args = parser.parse_args()
    text = args.qml_log.read_text(encoding="utf-8", errors="replace")
    print(render_report(parse_lines(text.splitlines())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

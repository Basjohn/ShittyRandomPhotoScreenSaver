from __future__ import annotations

import json
from pathlib import Path

import pytest


_BUBBLE_EDGE_GOLDEN = (
    Path(__file__).resolve().parent
    / "goldens"
    / "visualizer_temporal"
    / "v1"
    / "bubble_discrete_edge_general_compute.json"
)


def _historical_rate_gate_requests(
    *,
    producer_hz: float,
    target_hz: float,
    duration_s: float,
    paint_ack_hz: float | None = None,
) -> list[float]:
    """Model the rejected producer-timestamp gate from the R-27 negative control."""
    producer_interval = 1.0 / producer_hz
    request_interval = (1.0 / target_hz) * 0.92
    last_request = float("-inf")
    next_paint_ack = 1.0 / paint_ack_hz if paint_ack_hz else None
    update_pending = False
    requests: list[float] = []
    tick = 0
    while True:
        now = tick * producer_interval
        if now > duration_s + 1e-12:
            break
        if next_paint_ack is not None and update_pending:
            if next_paint_ack <= now + 1e-12:
                update_pending = False
                while next_paint_ack <= now + 1e-12:
                    next_paint_ack += 1.0 / paint_ack_hz
        if not update_pending and now - last_request >= request_interval:
            requests.append(now)
            last_request = now
            update_pending = paint_ack_hz is not None
        tick += 1
    return requests


def _latest_state_samples(
    values: list[float], *, logical_hz: float, presentation_hz: float, phase_s: float
) -> list[float]:
    logical_interval = 1.0 / logical_hz
    presentation_interval = 1.0 / presentation_hz
    end_s = (len(values) - 1) * logical_interval
    samples: list[float] = []
    opportunity = phase_s
    while opportunity <= end_s + 1e-12:
        source_index = min(int(opportunity / logical_interval), len(values) - 1)
        samples.append(values[source_index])
        opportunity += presentation_interval
    return samples


def test_rejected_target_fps_gate_turns_100_hz_input_into_50_hz_requests() -> None:
    requests = _historical_rate_gate_requests(
        producer_hz=100.0,
        target_hz=60.0,
        duration_s=2.0,
    )

    intervals = [later - earlier for earlier, later in zip(requests, requests[1:])]
    observed_hz = (len(requests) - 1) / (requests[-1] - requests[0])

    assert observed_hz == pytest.approx(50.0)
    assert set(round(interval, 6) for interval in intervals) == {0.02}


def test_rejected_pending_until_paint_latch_turns_delivery_into_admission() -> None:
    requests = _historical_rate_gate_requests(
        producer_hz=100.0,
        target_hz=60.0,
        duration_s=4.0,
        paint_ack_hz=40.0,
    )

    observed_hz = (len(requests) - 1) / (requests[-1] - requests[0])

    assert observed_hz == pytest.approx(40.0, abs=0.3)


def test_latest_at_60_hz_can_hide_the_protected_bubble_edge() -> None:
    golden = json.loads(_BUBBLE_EDGE_GOLDEN.read_text(encoding="utf-8"))
    values = [float(tick["visible_edge"]) for tick in golden["ticks"]]

    missed = _latest_state_samples(
        values,
        logical_hz=100.0,
        presentation_hz=60.0,
        phase_s=0.0,
    )
    observed = _latest_state_samples(
        values,
        logical_hz=100.0,
        presentation_hz=60.0,
        phase_s=0.008,
    )

    assert 1.0 not in missed
    assert observed.count(1.0) == 1

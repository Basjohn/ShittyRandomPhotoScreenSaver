"""Phase C2 gates for immutable transition requests and runs."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.animation.types import EasingCurve
from rendering.quick.image_state import PresentationImage
from rendering.quick.transitions.state import (
    TransitionRequest,
    TransitionRun,
)
from rendering.transition_registry import iter_transition_descriptors


def _image(identity: str) -> PresentationImage:
    return PresentationImage(
        identity=identity,
        source_path="synthetic",
        logical_size=(1, 1),
        device_pixel_ratio=1,
        pixel_size=(1, 1),
        row_stride=4,
        rgba8=b"\x00\x00\x00\xff",
    )


def _request(**changes) -> TransitionRequest:
    values = {
        "runtime_generation": 4,
        "transition_id": "slide",
        "requested_name": "Slide",
        "selected_from_random": False,
        "duration_ms": 1000,
        "direction": "left",
        "parameters": {"grid": [4, 6], "strength": 0.75},
        "source_image": _image("old"),
        "destination_image": _image("new"),
    }
    values.update(changes)
    return TransitionRequest(**values)


def test_request_uses_registry_identity_and_deep_freezes_authored_parameters():
    request = _request(
        transition_id="Rain Drops",
        requested_name="Random",
        selected_from_random=1,
        direction=None,
        parameters={"ripple_count": 5, "centres": [[0.25, 0.75]]},
    )

    assert request.transition_id == "ripple"
    assert request.setting_name == "Ripple"
    assert request.requested_name == "Random"
    assert request.selected_from_random is True
    assert request.easing_curve is EasingCurve.LINEAR
    assert request.include_in_cycle is True
    assert request.source_image_identity == "old"
    assert request.destination_image_identity == "new"
    assert request.parameter_dict() == {
        "centres": ((0.25, 0.75),),
        "ripple_count": 5,
    }
    with pytest.raises(FrozenInstanceError):
        request.duration_ms = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"runtime_generation": -1}, ValueError),
        ({"transition_id": "not-a-transition"}, ValueError),
        ({"duration_ms": 0}, ValueError),
        ({"source_image": object()}, TypeError),
        ({"parameters": {"bad": float("nan")}}, ValueError),
        ({"parameters": {"bad": object()}}, TypeError),
    ],
)
def test_request_rejects_non_renderable_or_mutable_state(changes, error):
    with pytest.raises(error):
        _request(**changes)


def test_run_samples_monotonic_time_and_authored_easing_without_mutation():
    request = _request()
    run = TransitionRun.start(
        run_id=9,
        request=request,
        start_ns=10_000_000_000,
    )

    before = run.sample(9_000_000_000)
    halfway = run.sample(10_500_000_000)
    terminal = run.sample(11_500_000_000)

    assert before.linear_progress == before.eased_progress == 0.0
    assert before.complete is False
    assert halfway.linear_progress == 0.5
    assert halfway.eased_progress == pytest.approx(0.5)
    assert halfway.complete is False
    assert terminal.linear_progress == terminal.eased_progress == 1.0
    assert terminal.complete is True
    assert halfway.run_id == 9
    assert halfway.runtime_generation == 4


def test_run_deadline_is_exactly_the_authored_duration():
    request = _request(duration_ms=2750)
    run = TransitionRun.start(run_id=1, request=request, start_ns=123)

    assert run.end_ns == 123 + 2_750_000_000
    with pytest.raises(ValueError, match="deadline mismatch"):
        TransitionRun(
            run_id=1,
            request=request,
            start_ns=123,
            end_ns=124,
        )


def test_every_canonical_transition_identity_is_lightweight_request_state():
    requests = [
        _request(transition_id=descriptor.stable_id)
        for descriptor in iter_transition_descriptors()
    ]

    assert [request.transition_id for request in requests] == [
        descriptor.stable_id for descriptor in iter_transition_descriptors()
    ]
    assert [request.easing_curve for request in requests] == [
        descriptor.easing_curve for descriptor in iter_transition_descriptors()
    ]


def test_request_does_not_admit_a_user_or_callsite_easing_override():
    with pytest.raises(TypeError, match="easing"):
        _request(easing_curve=EasingCurve.BACK_IN_OUT)

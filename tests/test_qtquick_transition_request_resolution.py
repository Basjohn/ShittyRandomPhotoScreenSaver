"""Settings-to-request admission for production Quick transition batches."""

from __future__ import annotations

import pytest

from rendering.quick.transitions.request_resolution import (
    resolve_quick_transition_spec,
)


class _Settings:
    def __init__(self, transitions: dict, *, hw_accel: bool = False) -> None:
        self.transitions = transitions
        self.hw_accel = hw_accel

    def get(self, key: str, default=None):
        if key == "transitions":
            return self.transitions
        if key == "display.hw_accel":
            return self.hw_accel
        return default


class _Rng:
    def __init__(self, choice_value: object) -> None:
        self.choice_value = choice_value
        self.choice_calls = 0

    def choice(self, values):
        assert self.choice_value in values
        self.choice_calls += 1
        return self.choice_value

    def randint(self, a: int, _b: int) -> int:
        return a

    def random(self) -> float:
        return 0.25


def test_manual_transition_resolves_canonical_duration_and_direction() -> None:
    spec = resolve_quick_transition_spec(
        _Settings(
            {
                "type": "Slide",
                "random_always": False,
                "durations": {"Slide": 321},
                "slide": {"direction": "Right to Left"},
            }
        )
    )

    assert spec is not None
    assert spec.transition_id == "slide"
    assert spec.requested_name == "Slide"
    assert spec.selected_from_random is False
    assert spec.duration_ms == 321
    assert spec.direction == "right"
    assert spec.parameters == ()


def test_random_direction_is_resolved_once_into_the_batch_value() -> None:
    rng = _Rng("down")
    spec = resolve_quick_transition_spec(
        _Settings(
            {
                "type": "Slide",
                "random_always": False,
                "durations": {"Slide": 500},
                "slide": {"direction": "Random"},
            }
        ),
        random_source=rng,
    )

    assert spec is not None
    assert spec.direction == "down"
    assert rng.choice_calls == 1


@pytest.mark.parametrize(
    ("choice", "pool", "activation", "hw_accel"),
    [
        (None, {"Slide": True}, {}, False),
        ("Slide", {"Wipe": True}, {}, False),
        ("Slide", {"Slide": True}, {"Slide": False}, False),
        ("Ripple", {"Ripple": True}, {}, False),
    ],
)
def test_random_choice_fails_closed_when_not_currently_admissible(
    choice,
    pool,
    activation,
    hw_accel,
) -> None:
    spec = resolve_quick_transition_spec(
        _Settings(
            {
                "type": "Crossfade",
                "random_always": True,
                "random_choice": choice,
                "pool": pool,
                "activation": activation,
            },
            hw_accel=hw_accel,
        )
    )

    assert spec is None


def test_admitted_random_choice_and_block_flip_geometry_are_frozen() -> None:
    spec = resolve_quick_transition_spec(
        _Settings(
            {
                "type": "Crossfade",
                "random_always": True,
                "random_choice": "Block Puzzle Flip",
                "pool": {"Block Puzzle Flip": True},
                "durations": {"Block Puzzle Flip": 777},
                "block_flip": {
                    "direction": "Diagonal TL-BR",
                    "rows": 7,
                    "cols": 11,
                },
            }
        )
    )

    assert spec is not None
    assert spec.transition_id == "block_flip"
    assert spec.requested_name == "Crossfade"
    assert spec.selected_from_random is True
    assert spec.duration_ms == 777
    assert spec.direction == "diag_tl_br"
    assert spec.parameters == (("cols", 11), ("rows", 7))

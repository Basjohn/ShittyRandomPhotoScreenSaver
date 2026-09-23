"""freeze_render_fields freezes each value once and keeps its validation (VZ-05)."""

from __future__ import annotations

import pytest

import widgets.spotify_visualizer.render_state as render_state
from widgets.spotify_visualizer.render_state import FrozenFields, freeze_render_fields


def _sample() -> dict[str, object]:
    return {
        "zeta": 0.25,
        "alpha": (1, 2, 3, 255),
        "flags": [True, False],
        "nested": {"b": 2.0, "a": {"c": 3.0}},
        "label": "x",
        "none": None,
    }


def test_output_equals_the_public_constructor_result() -> None:
    fast = freeze_render_fields(_sample())
    reference = FrozenFields(fast.entries)
    assert fast == reference
    assert fast.entries == reference.entries
    assert hash(fast) == hash(reference)
    assert [name for name, _ in fast.entries] == sorted(_sample())
    assert fast.as_dict()["nested"] == {"a": {"c": 3.0}, "b": 2.0}


def test_each_value_is_frozen_once(monkeypatch) -> None:
    calls: list[object] = []
    real = render_state.freeze_render_value

    def _counting(value):
        calls.append(value)
        return real(value)

    monkeypatch.setattr(render_state, "freeze_render_value", _counting)
    freeze_render_fields({"a": 1.0, "b": 2.0, "c": 3.0})
    assert len(calls) == 3


def test_existing_frozen_fields_are_reused_not_rebuilt() -> None:
    inner = freeze_render_fields({"c": 3.0})
    outer = freeze_render_fields({"inner": inner})
    assert outer["inner"] is inner


@pytest.mark.parametrize(
    "values",
    [
        {"": 1.0},
        {"nan": float("nan")},
        {"inf": float("inf")},
        {"obj": object()},
    ],
)
def test_validation_is_unchanged(values) -> None:
    with pytest.raises((ValueError, TypeError)):
        freeze_render_fields(values)

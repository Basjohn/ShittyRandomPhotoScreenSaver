"""Settings-to-request admission for production Quick transition batches."""

from __future__ import annotations

import pytest

from core.settings.default_contract import require_canonical_default
from rendering.quick.transitions.request_resolution import (
    RandomTransitionSelection,
    resolve_quick_transition_spec,
)


class _Settings:
    def __init__(self, transitions: dict, *, hw_accel: bool = False, scene3d: dict | None = None) -> None:
        self.transitions = transitions
        self.hw_accel = hw_accel
        self.scene3d = dict(scene3d or {})

    def get(self, key: str, default=None):
        if key == "transitions":
            return self.transitions
        if key == "display.hw_accel":
            return self.hw_accel
        if key.startswith("scene3d.") and key[len("scene3d."):] in self.scene3d:
            return self.scene3d[key[len("scene3d."):]]
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        return bool(value) if value is not None else bool(default)


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
    assert spec.direction == "left"
    assert dict(spec.parameters) == {
        "motion_style": str(require_canonical_default("transitions.slide.motion_style"))
    }


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
        # TEST INPUT, NOT A DEFAULT GOLDEN: out of the pool explicitly (an absent key
        # inherits the canonical pool default, which the operator may change).
        ("Slide", {"Wipe": True, "Slide": False}, {}, False),
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
                "pool": pool,
                "activation": activation,
            },
            hw_accel=hw_accel,
        ),
        random_selection=(
            None if choice is None else RandomTransitionSelection(choice)
        ),
    )

    assert spec is None


def test_persisted_random_choice_is_not_a_selection_authority() -> None:
    """A stale persisted ``random_choice`` from older builds is ignored (TX-02)."""

    spec = resolve_quick_transition_spec(
        _Settings(
            {
                "type": "Crossfade",
                "random_always": True,
                "random_choice": "Slide",
                "pool": {"Slide": True},
            }
        )
    )

    assert spec is None


@pytest.mark.parametrize(
    ("name", "section", "authored", "picked", "expected"),
    [
        ("Slide", "slide", "Right to Left", "Top to Bottom", "down"),
        ("Wipe", "wipe", "Bottom to Top", "Diagonal TR-BL", "diag_tr_bl"),
    ],
)
def test_random_selection_direction_overrides_without_touching_authored_value(
    name,
    section,
    authored,
    picked,
    expected,
) -> None:
    transitions = {
        "type": "Crossfade",
        "random_always": True,
        "pool": {name: True},
        section: {"direction": authored},
    }

    spec = resolve_quick_transition_spec(
        _Settings(transitions),
        random_selection=RandomTransitionSelection(name, direction=picked),
    )

    assert spec is not None
    assert spec.direction == expected
    assert transitions[section] == {"direction": authored}

    manual = resolve_quick_transition_spec(
        _Settings({**transitions, "type": name, "random_always": False}),
    )
    assert manual is not None
    assert manual.direction != expected


def test_admitted_random_choice_and_its_direction_are_frozen() -> None:
    spec = resolve_quick_transition_spec(
        _Settings(
            {
                "type": "Crossfade",
                "random_always": True,
                "pool": {"3D Block Spins": True},
                "activation": {"3D Block Spins": True},
                "durations": {"3D Block Spins": 777},
                "blockspin": {"direction": "Diagonal TL-BR"},
            },
            hw_accel=True,
        ),
        random_selection=RandomTransitionSelection("3D Block Spins"),
    )

    assert spec is not None
    assert spec.transition_id == "block_spins"
    assert spec.requested_name == "Crossfade"
    assert spec.selected_from_random is True
    assert spec.duration_ms == 777
    assert spec.direction == "diag_tl_br"
    assert isinstance(spec.parameters, tuple)


_FUTURE_TRANSITIONS = (
    ("Glass Shatter", "glass_shatter", {"direction": "Center Out", "shards": 120, "depth": 1.1}),
    ("Exploding Tiles", "exploding_tiles", {"direction": "Diagonal TL-BR", "columns": 22, "depth": 1.0}),
    ("Directional Pixel Accretion", "pixel_accretion", {"direction": "Diagonal BR-TL", "tile_size": 12, "travel": 0.6}),
    ("Melt Drip", "melt_drip", {"detail": 1.2, "direction": "Top Center"}),
)


@pytest.mark.parametrize("setting_name,transition_id,section", _FUTURE_TRANSITIONS)
def test_new_transition_ids_resolve_through_manual_and_random_admission(
    setting_name, transition_id, section
) -> None:
    durations = {setting_name: 2100}
    activation = {setting_name: True}
    pool = {setting_name: True}
    manual = resolve_quick_transition_spec(
        _Settings(
            {
                "type": setting_name,
                "random_always": False,
                "activation": activation,
                "durations": durations,
                transition_id: section,
            },
            hw_accel=True,
        ),
        random_source=_Rng("left"),
    )
    assert manual is not None
    assert manual.transition_id == transition_id
    assert manual.duration_ms == 2100
    assert dict(manual.parameters)["seed"] == 1

    random = resolve_quick_transition_spec(
        _Settings(
            {
                "type": "Crossfade",
                "random_always": True,
                "activation": activation,
                "pool": pool,
                "durations": durations,
                transition_id: section,
            },
            hw_accel=True,
        ),
        random_selection=RandomTransitionSelection(setting_name),
        random_source=_Rng("left"),
    )
    assert random is not None
    assert random.transition_id == transition_id
    assert random.selected_from_random is True
    assert random.duration_ms == 2100
    assert dict(random.parameters)["seed"] == 1


@pytest.mark.parametrize("stored", ["Performance", None])
def test_every_3d_transition_request_carries_the_3d_detail_tier(stored) -> None:
    from core.settings.scene3d_quality import resolve_scene3d_tier
    from rendering.quick.bootstrap import last_validated_gpu

    expected = stored or resolve_scene3d_tier(None, "transitions", gpu=last_validated_gpu())
    for name, stable_id in (("3D Block Spins", "block_spins"), ("Glass Shatter", "glass_shatter"),
                            ("Exploding Tiles", "exploding_tiles"), ("Directional Pixel Accretion", "pixel_accretion"),
                            ("Crumble", "crumble")):
        transitions = {"type": name, "random_always": False, "activation": {name: True}}
        # The 3D Transitions tier from the 3D Settings; a retired Transitions leaf is ignored.
        transitions["detail_3d"] = "KAK"
        scene3d = {"transitions_detail": stored} if stored else {}
        spec = resolve_quick_transition_spec(_Settings(transitions, scene3d=scene3d), random_source=_Rng("left"))
        assert spec is not None and spec.transition_id == stable_id
        assert dict(spec.parameters)["detail"] == expected, stable_id

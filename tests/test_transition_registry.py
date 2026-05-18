from __future__ import annotations

from rendering.transition_registry import (
    canonicalize_transition_name,
    get_cycle_transition_names,
    get_hw_accel_transition_names,
    get_transition_program_map,
    get_transition_program_specs,
    get_transition_setting_names,
    is_transition_available_for_hw,
)
from engine.screensaver_engine import ScreensaverEngine
from rendering.transition_factory import TransitionFactory


def test_transition_registry_canonicalizes_legacy_names() -> None:
    assert canonicalize_transition_name("Rain Drops") == "Ripple"
    assert canonicalize_transition_name("Claw Marks") == "Crossfade"
    assert canonicalize_transition_name("Shuffle") == "Crossfade"
    assert canonicalize_transition_name("Random", fallback="Crossfade") == "Random"


def test_transition_registry_cycle_names_include_burn() -> None:
    names = get_cycle_transition_names()
    assert "Burn" in names
    assert names == get_transition_setting_names()


def test_engine_cycle_list_comes_from_transition_registry() -> None:
    engine = ScreensaverEngine()
    assert engine._transition_types == get_cycle_transition_names()


def test_transition_registry_hw_gating_metadata_is_queryable() -> None:
    hw_names = set(get_hw_accel_transition_names())
    assert "Burn" in hw_names
    assert is_transition_available_for_hw("Crossfade", False) is True
    assert is_transition_available_for_hw("Burn", False) is False


class _FactorySettings:
    def __init__(self, *, hw_accel: bool) -> None:
        self.hw_accel = hw_accel

    def get(self, key: str, default=None):
        if key == "display.hw_accel":
            return self.hw_accel
        if key == "transitions.last_random_choice":
            return None
        if key == "transitions.random_choice":
            return None
        return default


def test_transition_factory_random_fallback_respects_hw_gating() -> None:
    factory = object.__new__(TransitionFactory)
    factory._settings = _FactorySettings(hw_accel=False)
    choice = TransitionFactory._pick_random_transition(
        factory,
        {
            "pool": {
                "Crossfade": True,
                "Slide": False,
                "Wipe": False,
                "Diffuse": False,
                "Block Puzzle Flip": False,
                "Blinds": False,
                "3D Block Spins": False,
                "Ripple": False,
                "Warp Dissolve": False,
                "Crumble": False,
                "Particle": False,
                "Burn": True,
            }
        },
    )
    assert choice == "Crossfade"


def test_transition_registry_program_specs_keep_crossfade_startup_only() -> None:
    startup_specs = get_transition_program_specs(startup_only=True)
    deferred_specs = get_transition_program_specs(startup_only=False)

    assert startup_specs == [("crossfade", "crossfade_program", "crossfade_uniforms")]
    assert ("burn", "burn_program", "burn_uniforms") in deferred_specs
    assert ("warp", "warp_program", "warp_uniforms") in deferred_specs


def test_transition_registry_program_map_covers_runtime_classes() -> None:
    program_map = get_transition_program_map()

    assert program_map["GLCompositorCrossfadeTransition"] == "crossfade"
    assert program_map["GLCompositorBurnTransition"] == "burn"
    assert program_map["GLCompositorRainDropsTransition"] == "raindrops"

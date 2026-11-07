from __future__ import annotations

from core.animation.types import EasingCurve
from rendering.transition_registry import (
    canonicalize_transition_name,
    get_cycle_transition_names,
    get_transition_descriptor_for_runtime_identity,
    get_hw_accel_transition_names,
    get_transition_setting_names,
    is_transition_available_for_hw,
    iter_transition_descriptors,
)
from engine.screensaver_engine import ScreensaverEngine


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


def test_runtime_identity_accepts_only_labels_stable_ids_and_legacy_labels() -> None:
    # The GL-compositor era's internal spellings (program keys, runtime labels and
    # GLCompositor*Transition class names) had no production producer and were removed;
    # they must not resolve, or agents keep chasing them as live identities.
    for retired in ("raindrops", "warp", "blockspin", "block_spin", "GLCompositorBurnTransition",
                    "GLCompositorRainDropsTransition", "GLCompositorBlockSpinTransition"):
        assert get_transition_descriptor_for_runtime_identity(retired) is None, retired
    for descriptor in iter_transition_descriptors():
        assert get_transition_descriptor_for_runtime_identity(descriptor.setting_name) is descriptor
        assert get_transition_descriptor_for_runtime_identity(descriptor.stable_id) is descriptor
        for legacy in descriptor.legacy_names:
            assert get_transition_descriptor_for_runtime_identity(legacy) is descriptor
    for field in ("gl_program_key", "program_attr", "uniforms_attr", "compositor_transition_class",
                  "startup_compile"):
        assert not hasattr(iter_transition_descriptors()[0], field), field


def test_transition_registry_owns_each_authored_progress_curve() -> None:
    # EXACT-VALUE INVARIANT: each transition must make a deliberate authored easing
    # choice. A new registry member should fail here until that semantic is reviewed.
    assert {
        descriptor.stable_id: descriptor.easing_curve
        for descriptor in iter_transition_descriptors()
    } == {
        "ripple": EasingCurve.LINEAR,
        "wipe": EasingCurve.QUAD_IN_OUT,
        "block_spins": EasingCurve.LINEAR,
        "slide": EasingCurve.SINE_IN_OUT,
        "crossfade": EasingCurve.QUAD_IN_OUT,
        "warp_dissolve": EasingCurve.LINEAR,
        "blinds": EasingCurve.LINEAR,
        "crumble": EasingCurve.LINEAR,
        "particle": EasingCurve.LINEAR,
        "burn": EasingCurve.LINEAR,
        "glass_shatter": EasingCurve.LINEAR,
        "exploding_tiles": EasingCurve.LINEAR,
        "pixel_accretion": EasingCurve.LINEAR,
        "melt_drip": EasingCurve.LINEAR,
        "page_curl": EasingCurve.LINEAR,   # eases its own curl line
        "disintegrate": EasingCurve.LINEAR,
        "cube_turn": EasingCurve.LINEAR,
        "beam": EasingCurve.LINEAR,
        "jigsaw": EasingCurve.LINEAR,
        "volumetric_dissolve": EasingCurve.LINEAR,
        "vhs": EasingCurve.LINEAR,
        "edge_bloom": EasingCurve.LINEAR,
        "liquid_lens": EasingCurve.LINEAR,
        "membrane": EasingCurve.LINEAR,
        "surface_tension": EasingCurve.LINEAR,
        "chromatic_shear": EasingCurve.LINEAR,
        "depth_cascade": EasingCurve.LINEAR,
        "capillary_bloom": EasingCurve.LINEAR,
    }


def test_every_transition_section_belongs_to_one_transition() -> None:
    from core.settings.defaults import get_default_settings
    from rendering.transition_registry import iter_transition_descriptors

    transitions = get_default_settings()["transitions"]
    sections = {key for key, value in transitions.items()
                if isinstance(value, dict) and key not in {"activation", "pool", "durations"}}
    owners = [descriptor.settings_section for descriptor in iter_transition_descriptors()]
    assert len(owners) == len(set(owners))
    assert sections <= set(owners)

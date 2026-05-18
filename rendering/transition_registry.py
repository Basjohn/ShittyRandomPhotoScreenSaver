"""Canonical transition descriptor registry.

This module centralizes stable transition identity, UI labels, legacy aliases,
GL warmup policy, and engine/runtime participation so transition additions do
not have to update several unrelated lists by hand.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from rendering.gl_programs.program_cache import GLProgramCache


@dataclass(frozen=True)
class TransitionDescriptor:
    """Canonical metadata for one transition family."""

    setting_name: str
    stable_id: str
    gl_program_key: Optional[str] = None
    program_attr: Optional[str] = None
    uniforms_attr: Optional[str] = None
    compositor_transition_class: Optional[str] = None
    startup_compile: bool = False
    include_in_cycle: bool = True
    requires_hw_accel: bool = False
    random_pool_name: Optional[str] = None
    legacy_names: tuple[str, ...] = ()


_TRANSITION_DESCRIPTORS: tuple[TransitionDescriptor, ...] = (
    TransitionDescriptor(
        setting_name="Ripple",
        stable_id="ripple",
        gl_program_key=GLProgramCache.RAINDROPS,
        program_attr="raindrops_program",
        uniforms_attr="raindrops_uniforms",
        compositor_transition_class="GLCompositorRainDropsTransition",
        requires_hw_accel=True,
        random_pool_name="Ripple",
        legacy_names=("Rain Drops",),
    ),
    TransitionDescriptor(
        setting_name="Wipe",
        stable_id="wipe",
        gl_program_key=GLProgramCache.WIPE,
        program_attr="wipe_program",
        uniforms_attr="wipe_uniforms",
        compositor_transition_class="GLCompositorWipeTransition",
    ),
    TransitionDescriptor(
        setting_name="3D Block Spins",
        stable_id="block_spins",
        gl_program_key=GLProgramCache.WARP,
        compositor_transition_class="GLCompositorBlockSpinTransition",
        requires_hw_accel=True,
    ),
    TransitionDescriptor(
        setting_name="Diffuse",
        stable_id="diffuse",
        gl_program_key=GLProgramCache.DIFFUSE,
        program_attr="diffuse_program",
        uniforms_attr="diffuse_uniforms",
        compositor_transition_class="GLCompositorDiffuseTransition",
    ),
    TransitionDescriptor(
        setting_name="Slide",
        stable_id="slide",
        gl_program_key=GLProgramCache.SLIDE,
        program_attr="slide_program",
        uniforms_attr="slide_uniforms",
        compositor_transition_class="GLCompositorSlideTransition",
    ),
    TransitionDescriptor(
        setting_name="Crossfade",
        stable_id="crossfade",
        gl_program_key=GLProgramCache.CROSSFADE,
        program_attr="crossfade_program",
        uniforms_attr="crossfade_uniforms",
        compositor_transition_class="GLCompositorCrossfadeTransition",
        startup_compile=True,
    ),
    TransitionDescriptor(
        setting_name="Block Puzzle Flip",
        stable_id="block_flip",
        gl_program_key=GLProgramCache.BLOCK_FLIP,
        program_attr="blockflip_program",
        uniforms_attr="blockflip_uniforms",
        compositor_transition_class="GLCompositorBlockFlipTransition",
    ),
    TransitionDescriptor(
        setting_name="Warp Dissolve",
        stable_id="warp_dissolve",
        gl_program_key=GLProgramCache.WARP,
        program_attr="warp_program",
        uniforms_attr="warp_uniforms",
        compositor_transition_class="GLCompositorWarpTransition",
        requires_hw_accel=True,
    ),
    TransitionDescriptor(
        setting_name="Blinds",
        stable_id="blinds",
        gl_program_key=GLProgramCache.BLINDS,
        program_attr="blinds_program",
        uniforms_attr="blinds_uniforms",
        compositor_transition_class="GLCompositorBlindsTransition",
        requires_hw_accel=True,
    ),
    TransitionDescriptor(
        setting_name="Crumble",
        stable_id="crumble",
        gl_program_key=GLProgramCache.CRUMBLE,
        program_attr="crumble_program",
        uniforms_attr="crumble_uniforms",
        compositor_transition_class="GLCompositorCrumbleTransition",
        requires_hw_accel=True,
    ),
    TransitionDescriptor(
        setting_name="Particle",
        stable_id="particle",
        gl_program_key=GLProgramCache.PARTICLE,
        program_attr="particle_program",
        uniforms_attr="particle_uniforms",
        compositor_transition_class="GLCompositorParticleTransition",
        requires_hw_accel=True,
    ),
    TransitionDescriptor(
        setting_name="Burn",
        stable_id="burn",
        gl_program_key=GLProgramCache.BURN,
        program_attr="burn_program",
        uniforms_attr="burn_uniforms",
        compositor_transition_class="GLCompositorBurnTransition",
        requires_hw_accel=True,
    ),
)

_BY_SETTING_NAME = {item.setting_name: item for item in _TRANSITION_DESCRIPTORS}
_BY_STABLE_ID = {item.stable_id: item for item in _TRANSITION_DESCRIPTORS}
_LEGACY_TO_SETTING = {
    alias: item.setting_name
    for item in _TRANSITION_DESCRIPTORS
    for alias in item.legacy_names
}
_LEGACY_TO_SETTING["Claw Marks"] = "Crossfade"
_LEGACY_TO_SETTING["Shuffle"] = "Crossfade"


def iter_transition_descriptors() -> tuple[TransitionDescriptor, ...]:
    return _TRANSITION_DESCRIPTORS


def get_transition_descriptor(value: str) -> Optional[TransitionDescriptor]:
    canonical = canonicalize_transition_name(value)
    if canonical == "Random":
        return None
    return _BY_SETTING_NAME.get(canonical) or _BY_STABLE_ID.get(canonical)


def canonicalize_transition_name(value: object, fallback: str = "Crossfade") -> str:
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    if not text:
        return fallback
    if text == "Random":
        return "Random"
    if text in _BY_SETTING_NAME:
        return text
    if text in _LEGACY_TO_SETTING:
        return _LEGACY_TO_SETTING[text]
    if text in _BY_STABLE_ID:
        return _BY_STABLE_ID[text].setting_name
    return fallback


def get_transition_setting_names() -> list[str]:
    return [item.setting_name for item in _TRANSITION_DESCRIPTORS]


def get_cycle_transition_names() -> list[str]:
    return [item.setting_name for item in _TRANSITION_DESCRIPTORS if item.include_in_cycle]


def get_hw_accel_transition_names() -> list[str]:
    return [item.setting_name for item in _TRANSITION_DESCRIPTORS if item.requires_hw_accel]


def get_transition_program_specs(*, startup_only: bool | None = None) -> list[tuple[str, str, str]]:
    specs: list[tuple[str, str, str]] = []
    for item in _TRANSITION_DESCRIPTORS:
        if item.gl_program_key is None or item.program_attr is None or item.uniforms_attr is None:
            continue
        if startup_only is True and not item.startup_compile:
            continue
        if startup_only is False and item.startup_compile:
            continue
        specs.append((item.gl_program_key, item.program_attr, item.uniforms_attr))
    return specs


def get_transition_program_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for item in _TRANSITION_DESCRIPTORS:
        if item.compositor_transition_class and item.gl_program_key:
            result[item.compositor_transition_class] = item.gl_program_key
    return result


def resolve_transition_pool_names(names: Iterable[str]) -> list[str]:
    resolved: list[str] = []
    for name in names:
        descriptor = get_transition_descriptor(name)
        if descriptor is None:
            continue
        resolved.append(descriptor.random_pool_name or descriptor.setting_name)
    return resolved


def is_transition_available_for_hw(setting_name: str, hw_accel_enabled: bool) -> bool:
    descriptor = get_transition_descriptor(setting_name)
    if descriptor is None:
        return False
    return hw_accel_enabled or not descriptor.requires_hw_accel

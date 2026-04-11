from __future__ import annotations

from dataclasses import dataclass, field
from math import exp


_POCKET_COUNT = 6
_KICK_SLOTS = (0, 1)
_SNARE_SLOTS = (2, 3)
_HIGH_SLOTS = (4, 5)
_KICK_ANGLES = (0.17, 0.33, 0.67, 0.83)
_SNARE_ANGLES = (0.08, 0.25, 0.58, 0.75)
_HIGH_ANGLES = (0.02, 0.42, 0.52, 0.92)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class BlobPocket:
    angle_frac: float = 0.0
    amplitude: float = 0.0
    width: float = 0.12
    phase: float = 0.0
    bass_mix: float = 0.0
    mid_mix: float = 0.0
    high_mix: float = 0.0
    transient_mix: float = 0.0
    release_s: float = 0.32


@dataclass
class BlobPocketState:
    pockets: list[BlobPocket] = field(default_factory=lambda: [BlobPocket() for _ in range(_POCKET_COUNT)])
    kick_cursor: int = 0
    snare_cursor: int = 0
    high_cursor: int = 0
    kick_cooldown: float = 0.0
    snare_cooldown: float = 0.0
    high_cooldown: float = 0.0
    last_kick_strength: float = 0.0
    last_snare_strength: float = 0.0
    last_high_strength: float = 0.0


def make_blob_pocket_state() -> BlobPocketState:
    return BlobPocketState()


def reset_blob_pocket_state(state: BlobPocketState | None = None) -> BlobPocketState:
    if state is None:
        return make_blob_pocket_state()
    state.pockets = [BlobPocket() for _ in range(_POCKET_COUNT)]
    state.kick_cursor = 0
    state.snare_cursor = 0
    state.high_cursor = 0
    state.kick_cooldown = 0.0
    state.snare_cooldown = 0.0
    state.high_cooldown = 0.0
    state.last_kick_strength = 0.0
    state.last_snare_strength = 0.0
    state.last_high_strength = 0.0
    return state


def _decay_pockets(state: BlobPocketState, dt: float) -> None:
    if dt <= 0.0:
        return
    state.kick_cooldown = max(0.0, state.kick_cooldown - dt)
    state.snare_cooldown = max(0.0, state.snare_cooldown - dt)
    state.high_cooldown = max(0.0, state.high_cooldown - dt)
    for pocket in state.pockets:
        if pocket.amplitude <= 0.0001:
            pocket.amplitude = 0.0
            continue
        release = max(0.08, pocket.release_s)
        pocket.amplitude *= exp(-dt / release)
        if pocket.amplitude < 0.005:
            pocket.amplitude = 0.0


def _slot_and_angle(state: BlobPocketState, family: str) -> tuple[int, float]:
    if family == "kick":
        slot = _KICK_SLOTS[state.kick_cursor % len(_KICK_SLOTS)]
        angle = _KICK_ANGLES[state.kick_cursor % len(_KICK_ANGLES)]
        state.kick_cursor += 1
        return slot, angle
    if family == "snare":
        slot = _SNARE_SLOTS[state.snare_cursor % len(_SNARE_SLOTS)]
        angle = _SNARE_ANGLES[state.snare_cursor % len(_SNARE_ANGLES)]
        state.snare_cursor += 1
        return slot, angle
    slot = _HIGH_SLOTS[state.high_cursor % len(_HIGH_SLOTS)]
    angle = _HIGH_ANGLES[state.high_cursor % len(_HIGH_ANGLES)]
    state.high_cursor += 1
    return slot, angle


def _spawn_pocket(
    state: BlobPocketState,
    *,
    family: str,
    strength: float,
    time_seconds: float,
) -> None:
    slot, angle = _slot_and_angle(state, family)
    pocket = state.pockets[slot]
    amp = _clamp(strength, 0.0, 1.0)
    pocket.angle_frac = angle
    pocket.amplitude = max(pocket.amplitude * 0.28, amp)
    pocket.phase = time_seconds + slot * 0.017
    if family == "kick":
        pocket.width = 0.17
        pocket.bass_mix = 1.00
        pocket.mid_mix = 0.18
        pocket.high_mix = 0.04
        pocket.transient_mix = 0.58
        pocket.release_s = 0.34
        state.kick_cooldown = 0.024
    elif family == "snare":
        pocket.width = 0.14
        pocket.bass_mix = 0.10
        pocket.mid_mix = 0.90
        pocket.high_mix = 0.34
        pocket.transient_mix = 0.62
        pocket.release_s = 0.30
        state.snare_cooldown = 0.022
    else:
        pocket.width = 0.11
        pocket.bass_mix = 0.02
        pocket.mid_mix = 0.22
        pocket.high_mix = 0.94
        pocket.transient_mix = 0.50
        pocket.release_s = 0.22
        state.high_cooldown = 0.018


def advance_blob_pocket_state(
    state: BlobPocketState | None,
    *,
    dt: float,
    time_seconds: float,
    playing: bool,
    shaper_enabled: bool,
    kick_raw: float,
    snare_raw: float,
    bass_transient: float,
    mid_transient: float,
    high_transient: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
) -> BlobPocketState:
    pocket_state = state if state is not None else make_blob_pocket_state()
    _decay_pockets(pocket_state, dt)
    if not playing or shaper_enabled:
        return pocket_state

    kick_strength = _clamp(
        max(
            kick_raw * 0.98,
            bass_transient * 1.30,
            bass_energy * 0.18 + bass_transient * 0.82,
        ),
        0.0,
        1.0,
    )
    snare_strength = _clamp(
        max(
            snare_raw * 0.98,
            mid_transient * 1.16 + high_transient * 0.26,
            mid_energy * 0.18 + mid_transient * 0.72 + high_transient * 0.12,
        ),
        0.0,
        1.0,
    )
    high_strength = _clamp(
        max(
            high_transient * 0.96,
            high_energy * 0.42 + mid_transient * 0.18 + overall_energy * 0.08,
        ),
        0.0,
        1.0,
    )

    kick_fresh = kick_strength >= max(0.10, pocket_state.last_kick_strength + 0.045)
    snare_fresh = snare_strength >= max(0.09, pocket_state.last_snare_strength + 0.040)
    high_fresh = high_strength >= max(0.08, pocket_state.last_high_strength + 0.035)

    if kick_strength >= 0.10 and (pocket_state.kick_cooldown <= 0.0 or kick_fresh):
        _spawn_pocket(pocket_state, family="kick", strength=kick_strength, time_seconds=time_seconds)
    if snare_strength >= 0.09 and (pocket_state.snare_cooldown <= 0.0 or snare_fresh):
        _spawn_pocket(pocket_state, family="snare", strength=snare_strength, time_seconds=time_seconds)
    if high_strength >= 0.08 and (pocket_state.high_cooldown <= 0.0 or high_fresh):
        _spawn_pocket(pocket_state, family="high", strength=high_strength, time_seconds=time_seconds)

    pocket_state.last_kick_strength = kick_strength
    pocket_state.last_snare_strength = snare_strength
    pocket_state.last_high_strength = high_strength

    return pocket_state


def build_blob_pocket_uniform_payload(state: BlobPocketState | None) -> tuple[list[float], list[float]]:
    pocket_state = state if state is not None else make_blob_pocket_state()
    data: list[float] = []
    mix: list[float] = []
    for pocket in pocket_state.pockets:
        data.extend(
            [
                float(pocket.angle_frac),
                float(pocket.amplitude),
                float(pocket.width),
                float(pocket.phase),
            ]
        )
        mix.extend(
            [
                float(pocket.bass_mix),
                float(pocket.mid_mix),
                float(pocket.high_mix),
                float(pocket.transient_mix),
            ]
        )
    return data, mix

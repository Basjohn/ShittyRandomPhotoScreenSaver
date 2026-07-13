"""Blob-owned curved tendril transport for Mighty and Shaped.

The radial contour remains useful for the breathing body and vocal outline,
but a single radius per angle cannot form bent limbs, hooked tips, or the deep
negative space of an actual goo silhouette.  This module produces a small,
bounded set of curved tendrils for the Blob shader to smooth-union with that
body.  It also owns the displayed-geometry transport: audio is allowed to make
decisive targets, while reach, curvature, and anchor changes morph toward those
targets without changing shared audio or another visualizer mode.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from core.settings.visualizer_blob_contract import BLOB_TYPE_SHAPED

TENDRIL_COUNT = 12
TENDRIL_PAYLOAD_SIZE = TENDRIL_COUNT * 4


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = _clamp((float(value) - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _soft_energy(value: float) -> float:
    raw = max(0.0, float(value)) * 0.72
    if raw <= 0.88:
        return raw
    return min(1.16, 0.88 + 0.30 * (1.0 - math.exp(-(raw - 0.88) / 0.30)))


def _live_bands(state: Any) -> tuple[float, float, float, float, float]:
    fallback = getattr(state, "_energy_bands", None)

    def _read(attr: str, band: str) -> float:
        value = getattr(state, attr, None)
        if value is None:
            value = getattr(fallback, band, 0.0) if fallback is not None else 0.0
        return _soft_energy(float(value or 0.0))

    transient = getattr(state, "_transient_energy", None)
    transient_peak = max(
        float(getattr(transient, "bass_transient", 0.0) if transient else 0.0),
        float(getattr(transient, "mid_transient", 0.0) if transient else 0.0),
        float(getattr(transient, "high_transient", 0.0) if transient else 0.0),
        float(getattr(state, "_blob_kick_event_envelope", 0.0) or 0.0),
        float(getattr(state, "_blob_snare_event_envelope", 0.0) or 0.0),
    )
    return (
        _read("_blob_live_bass_energy", "bass"),
        _read("_blob_live_mid_energy", "mid"),
        _read("_blob_live_high_energy", "high"),
        _read("_blob_live_overall_energy", "overall"),
        _soft_energy(transient_peak),
    )


def _profile_anchor_bias(profile: Sequence[float], angle_frac: float) -> float:
    if not profile:
        return 1.0
    idx = int((float(angle_frac) % 1.0) * len(profile)) % len(profile)
    mean = math.fsum(float(value) for value in profile) / len(profile)
    return _clamp(0.82 + (float(profile[idx]) - mean) * 1.4, 0.70, 1.18)


def _hash01(seed: float, lane: int, generation: int, salt: float) -> float:
    value = math.sin(
        (lane + 1) * 12.9898
        + (generation + 17) * 78.233
        + float(seed) * 37.719
        + float(salt) * 19.193
    ) * 43758.5453
    return value - math.floor(value)


def _lane_lifecycle(
    *,
    time_value: float,
    seed: float,
    lane: int,
    salt: float,
    duration_min: float,
    duration_span: float,
) -> tuple[int, float, float]:
    """Return generation, phase, and a grow/hold/retract envelope.

    Each lane spends a substantial dormant interval at zero reach. Its anchor
    may be reassigned only for a new generation, while the display transport
    uses that hidden interval to move to the next site. This makes mutation a
    sequence of organic births and retractions instead of one permanent splat.
    """

    duration = duration_min + _hash01(seed, lane, 0, salt + 0.31) * duration_span
    phase_offset = _hash01(seed, lane, 0, salt + 0.77) * duration
    clock = max(0.0, time_value + phase_offset) / max(0.25, duration)
    generation = int(math.floor(clock))
    phase = clock - generation
    grow = _smoothstep(0.08, 0.15, phase)
    retract = 1.0 - _smoothstep(0.34, 0.56, phase)
    envelope = grow * retract
    return generation, phase, envelope


def _coordinated_slot_lifecycle(
    *,
    time_value: float,
    seed: float,
    slot: int,
    slot_count: int,
    salt: float,
    duration: float,
) -> tuple[int, float, float]:
    """Stagger sparse outward slots so music never falls back to a bare body."""

    clock = (
        max(0.0, time_value) / max(0.5, duration)
        + slot / max(1, slot_count)
        + _hash01(seed, slot, 0, salt) * 0.035
    )
    generation = int(math.floor(clock))
    phase = clock - generation
    grow = _smoothstep(0.08, 0.15, phase)
    retract = 1.0 - _smoothstep(0.34, 0.56, phase)
    return generation, phase, grow * retract


def _mighty_payload(
    state: Any,
    *,
    profile: Sequence[float],
    time_value: float,
    seed: float,
) -> tuple[list[float], list[float]]:
    bass, mid, high, overall, transient = _live_bands(state)
    vocal = _clamp(mid * 0.90 + high * 0.22, 0.0, 1.16)
    playing = bool(getattr(state, "_playing", False))
    stretch = _clamp(getattr(state, "_blob_stretch_tendency", 0.35), 0.0, 1.0)
    outer = _clamp(getattr(state, "_blob_stretch_outer", 0.35), 0.0, 1.0)
    shape = _clamp(getattr(state, "_blob_reactive_deformation", 1.0), 0.0, 3.0)
    wobble = _clamp(getattr(state, "_blob_reactive_wobble", 1.0), 0.0, 3.0)
    reach_control = stretch * (0.34 + outer * 0.66) * (0.72 + min(shape, 2.0) * 0.34)
    if not playing:
        reach_control *= 0.16

    phases = (0.20, 2.60, 5.00, 1.10, 3.50, 5.90, 1.80, 4.20, 0.70, 3.10, 5.50, 2.00)
    drivers = (
        vocal * 0.82 + overall * 0.18,
        bass * 0.90 + transient * 0.30,
        mid * 0.70 + transient * 0.44,
        overall * 0.52 + vocal * 0.48,
        high * 0.72 + vocal * 0.34,
        transient * 0.72 + bass * 0.24 + high * 0.20,
        vocal * 0.54 + transient * 0.42 + overall * 0.18,
        bass * 0.42 + mid * 0.36 + high * 0.34,
        mid * 0.62 + overall * 0.28,
        high * 0.54 + transient * 0.38 + vocal * 0.20,
        bass * 0.58 + vocal * 0.32,
        overall * 0.44 + mid * 0.34 + transient * 0.30,
    )
    pockets = list(getattr(getattr(state, "_blob_pocket_state", None), "pockets", ()) or ())
    lane_lifecycles = [
        _lane_lifecycle(
            time_value=time_value,
            seed=seed,
            lane=idx,
            salt=1.7,
            duration_min=2.55,
            duration_span=1.55,
        )
        for idx in range(TENDRIL_COUNT)
    ]
    groove_indices = (3, 8, 11)
    outward_slots = (0, 4, 7)
    groove_slot = 11
    for slot, idx in enumerate(outward_slots):
        lane_lifecycles[idx] = _coordinated_slot_lifecycle(
            time_value=time_value,
            seed=seed,
            slot=slot,
            slot_count=len(outward_slots),
            salt=6.2,
            duration=3.45,
        )
    geometry: list[float] = []
    motion: list[float] = []
    for idx in range(TENDRIL_COUNT):
        generation, _life_phase, life = lane_lifecycles[idx]
        if idx in groove_indices and idx != groove_slot:
            life = 0.0
        elif idx not in groove_indices and idx not in outward_slots:
            life = 0.0
        anchor = (
            idx * 0.61803398875
            + generation * 0.2871
            + _hash01(seed, idx, generation, 2.3) * 0.34
            + seed * 0.037
        ) % 1.0
        pocket = pockets[idx] if idx < len(pockets) else None
        pocket_amp = _clamp(getattr(pocket, "amplitude", 0.0), 0.0, 1.0) if pocket else 0.0
        angle = anchor
        opposite_phase = phases[(TENDRIL_COUNT - 1 - idx) % TENDRIL_COUNT]
        driver_index = int(
            _hash01(seed, idx, generation, 3.1) * len(drivers)
        ) % len(drivers)
        driver = float(drivers[driver_index])
        activity = _clamp(
            (driver * (0.34 + life * 0.66) + pocket_amp * 0.30) * life,
            0.0,
            1.18,
        )
        if playing:
            sustained_support = max(vocal, overall, bass * 0.82, high * 0.74)
            activity = max(
                activity,
                sustained_support
                * reach_control
                * (0.12 + _hash01(seed, idx, generation, 3.7) * 0.05)
                * life,
            )
        activity *= _profile_anchor_bias(profile, angle)
        reach_scale = 0.68 + _hash01(seed, idx, generation, 4.1) * 0.88
        length = _clamp(
            activity
            * reach_control
            * (0.045 + reach_control * 0.112)
            * reach_scale,
            0.0,
            0.19,
        )
        if idx in groove_indices:
            # Mighty grooves are shallow rounded valleys, never radial cuts.
            length = min(0.045, length * 0.34)
        if length <= 0.00001:
            root_width = 0.0
            tip_width = 0.0
        else:
            root_width = _clamp(
                0.024 + length * 0.22 + activity * 0.011,
                0.021,
                0.066,
            )
            tip_ratio = 0.60 + _hash01(seed, idx, generation, 4.7) * 0.16
            tip_width = _clamp(root_width * tip_ratio, 0.012, root_width * 0.80)
        bend_sign = -1.0 if _hash01(seed, idx, generation, 5.1) < 0.5 else 1.0
        hook_sign = -1.0 if _hash01(seed, idx, generation, 5.7) < 0.5 else 1.0
        slow_flex = 0.82 + math.sin(time_value * 0.48 + phases[idx]) * 0.18
        bend = bend_sign * (0.24 + activity * 0.46) * slow_flex
        hook = hook_sign * (0.16 + activity * 0.38) * (
            0.84 + math.sin(time_value * 0.37 + opposite_phase) * 0.16
        )
        light = _clamp(vocal * 0.58 + high * 0.22 + transient * 0.32, 0.0, 1.0)
        geometry.extend((angle % 1.0, length, root_width, tip_width))
        # Three lanes are inward liquid channels. They subtract rounded, curved
        # negative space from the body instead of adding another radial limb.
        kind_or_light = (
            -max(0.18, activity)
            if idx in groove_indices
            else light * (0.55 + wobble * 0.15)
        )
        motion.extend((bend, hook, activity, kind_or_light))
    return geometry, motion


def _shaped_payload(
    state: Any,
    *,
    profile: Sequence[float],
    time_value: float,
    seed: float,
) -> tuple[list[float], list[float]]:
    bass, mid, high, overall, transient = _live_bands(state)
    vocal = _clamp(mid * 0.86 + high * 0.26, 0.0, 1.16)
    playing = bool(getattr(state, "_playing", False))
    idle = _clamp(getattr(state, "_blob_shaper_idle_motion", 0.18), 0.0, 2.0) / 2.0
    audio = _clamp(getattr(state, "_blob_shaper_audio_motion", 1.20), 0.0, 3.0) / 3.0
    react = _clamp(getattr(state, "_blob_shaper_react_strength", 0.5), 0.0, 1.0)
    ring_topology = getattr(state, "_blob_topology", "circle") == "ring"
    reach_scale = 1.65 if ring_topology else 1.48
    reach_limit = 0.180 if ring_topology else 0.165
    anchors = (0.035, 0.120, 0.205, 0.290, 0.375, 0.460, 0.545, 0.630, 0.715, 0.800, 0.885, 0.965)
    phases = (0.50, 2.70, 4.60, 1.50, 3.60, 5.50, 2.20, 4.10, 0.90, 3.00, 5.00, 1.90)
    reach_scales = (1.22, 0.70, 1.18, 0.76, 1.34, 0.66, 1.12, 1.26, 0.72, 1.30, 1.10, 0.64)
    drivers = (
        vocal,
        overall * 0.48 + transient * 0.62,
        mid * 0.62 + high * 0.30,
        bass * 0.52 + overall * 0.38,
        high * 0.68 + vocal * 0.28,
        transient * 0.72 + vocal * 0.26,
        vocal * 0.48 + overall * 0.26 + transient * 0.30,
        mid * 0.38 + high * 0.42 + bass * 0.20,
        overall * 0.40 + vocal * 0.38,
        high * 0.58 + transient * 0.30,
        bass * 0.44 + mid * 0.34 + transient * 0.22,
        vocal * 0.52 + high * 0.26 + overall * 0.18,
    )
    lane_lifecycles = [
        _lane_lifecycle(
            time_value=time_value,
            seed=seed,
            lane=idx,
            salt=7.4,
            duration_min=2.90,
            duration_span=1.70,
        )
        for idx in range(TENDRIL_COUNT)
    ]
    groove_indices = (2, 7, 10)
    outward_slots = (0, 3, 6, 9) if ring_topology else (0, 4, 9)
    groove_slot = 10
    for slot, idx in enumerate(outward_slots):
        lane_lifecycles[idx] = _coordinated_slot_lifecycle(
            time_value=time_value,
            seed=seed,
            slot=slot,
            slot_count=len(outward_slots),
            salt=11.6 if ring_topology else 12.4,
            duration=3.85 if ring_topology else 3.55,
        )
    geometry: list[float] = []
    motion: list[float] = []
    for idx in range(TENDRIL_COUNT):
        generation, _life_phase, life = lane_lifecycles[idx]
        if idx in groove_indices and idx != groove_slot:
            life = 0.0
        elif idx not in groove_indices and idx not in outward_slots:
            life = 0.0
        driver_index = int(
            _hash01(seed, idx, generation, 8.1) * len(drivers)
        ) % len(drivers)
        driver = float(drivers[driver_index])
        audio_activity = (
            driver * audio * (0.30 + life * 0.70) * life if playing else 0.0
        )
        idle_activity = idle * 0.14 * life
        activity = _clamp(audio_activity + idle_activity, 0.0, 1.0)
        if playing:
            activity = max(
                activity,
                max(vocal, overall, high * 0.86)
                * audio
                * (0.12 + react * 0.07)
                * life,
            )
        opposite_phase = phases[(TENDRIL_COUNT - 1 - idx) % TENDRIL_COUNT]
        migration_span = 0.22 if ring_topology else 0.15
        angle = anchors[idx] + (
            _hash01(seed, idx, generation, 8.7) - 0.5
        ) * migration_span
        activity *= _profile_anchor_bias(profile, angle)
        lane_reach_scale = 0.72 + _hash01(seed, idx, generation, 9.1) * 0.72
        length = _clamp(
            (
                idle_activity * 0.035
                + activity * (0.028 + audio * 0.092) * (0.62 + react * 0.38)
            ) * reach_scale * reach_scales[idx] * lane_reach_scale,
            0.0,
            reach_limit,
        )
        if idx in groove_indices:
            length = min(
                0.105 if ring_topology else 0.055,
                length * (0.86 if ring_topology else 0.55),
            )
        if length <= 0.00001:
            root_width = 0.0
            tip_width = 0.0
        else:
            root_width = _clamp(
                0.018 + length * 0.20 + activity * 0.009,
                0.016,
                0.048,
            )
            tip_ratio = 0.56 + _hash01(seed, idx, generation, 9.7) * 0.16
            tip_width = _clamp(root_width * tip_ratio, 0.010, root_width * 0.76)
        bend_sign = -1.0 if _hash01(seed, idx, generation, 10.1) < 0.5 else 1.0
        hook_sign = -1.0 if _hash01(seed, idx, generation, 10.7) < 0.5 else 1.0
        bend = bend_sign * (0.18 + activity * 0.48) * (
            0.86 + math.sin(time_value * 0.41 + phases[idx]) * 0.14
        )
        hook = hook_sign * (0.14 + activity * 0.40) * (
            0.86 + math.sin(time_value * 0.35 + opposite_phase) * 0.14
        )
        light = _clamp(vocal * 0.64 + high * 0.24 + transient * 0.38, 0.0, 1.0)
        geometry.extend((angle % 1.0, length, root_width, tip_width))
        kind_or_light = -max(0.16, activity) if idx in groove_indices else light
        motion.extend((bend, hook, activity, kind_or_light))
    return geometry, motion


def build_blob_tendril_payload(
    state: Any,
    *,
    blob_type: str,
    profile: Sequence[float],
) -> tuple[list[float], list[float]]:
    """Return flattened vec4 geometry/motion arrays for the selected subtype."""

    time_value = max(0.0, float(getattr(state, "_blob_runtime_time", 0.0) or 0.0))
    if blob_type == BLOB_TYPE_SHAPED:
        seed = float(getattr(state, "_blob_shaper_solver_seed", 0.0) or 0.0)
        return _shaped_payload(state, profile=profile, time_value=time_value, seed=seed)
    seed = float(getattr(state, "_blob_unshaped_solver_seed", 0.0) or 0.0)
    return _mighty_payload(state, profile=profile, time_value=time_value, seed=seed)


def _exp_alpha(dt: float, tau: float) -> float:
    return 1.0 - math.exp(-max(0.0, float(dt)) / max(0.001, float(tau)))


def _ease_scalar(
    current: float,
    target: float,
    *,
    dt: float,
    attack: float,
    release: float,
) -> float:
    tau = attack if target > current else release
    return current + (target - current) * _exp_alpha(dt, tau)


def _ease_angle(
    current: float,
    target: float,
    *,
    dt: float,
    tau: float,
    max_rate: float,
) -> float:
    """Ease cyclic angle fractions over the shortest arc with a speed guard."""

    delta = ((target - current + 0.5) % 1.0) - 0.5
    desired_step = delta * _exp_alpha(dt, tau)
    max_step = max(0.00035, dt * max_rate)
    step = _clamp(desired_step, -max_step, max_step)
    return (current + step) % 1.0


def advance_blob_tendril_state(
    state: Any,
    *,
    blob_type: str,
    target_geometry: Sequence[float],
    target_motion: Sequence[float],
) -> tuple[list[float], list[float]]:
    """Morph displayed Blob geometry toward a deliberately reactive target.

    This is visual geometry smoothing, not source/audio smoothing. Reach and
    activity attack fast enough to read as musical, release more slowly so
    limbs visibly retract, and retired anchors use cyclic interpolation so
    they cannot teleport across the 0/1 seam.
    """

    target_geometry = [float(value) for value in target_geometry]
    target_motion = [float(value) for value in target_motion]
    if (
        len(target_geometry) != TENDRIL_PAYLOAD_SIZE
        or len(target_motion) != TENDRIL_PAYLOAD_SIZE
    ):
        raise ValueError("Blob tendril payload must contain twelve vec4 lanes")

    setattr(state, "_blob_tendril_target_geometry", list(target_geometry))
    setattr(state, "_blob_tendril_target_motion", list(target_motion))
    target_max_reach = max(target_geometry[1::4], default=0.0)
    setattr(state, "_blob_tendril_target_max_reach", target_max_reach)

    current_geometry = getattr(state, "_blob_tendril_geometry", None)
    current_motion = getattr(state, "_blob_tendril_motion", None)
    transport_type = getattr(state, "_blob_tendril_transport_type", None)
    now = max(0.0, float(getattr(state, "_blob_runtime_time", 0.0) or 0.0))
    previous_ts = float(getattr(state, "_blob_tendril_transport_ts", 0.0) or 0.0)
    valid_current = (
        transport_type == blob_type
        and isinstance(current_geometry, (list, tuple))
        and isinstance(current_motion, (list, tuple))
        and len(current_geometry) == TENDRIL_PAYLOAD_SIZE
        and len(current_motion) == TENDRIL_PAYLOAD_SIZE
    )
    if not valid_current:
        # A reset/type boundary seeds from this activation's own target. This
        # avoids both a circular first frame and inheritance from the prior
        # subtype; the activation fade owns visual introduction.
        displayed_geometry = list(target_geometry)
        displayed_motion = list(target_motion)
        setattr(state, "_blob_tendril_geometry", displayed_geometry)
        setattr(state, "_blob_tendril_motion", displayed_motion)
        setattr(state, "_blob_tendril_transport_type", blob_type)
        setattr(state, "_blob_tendril_transport_ts", now)
        setattr(state, "_blob_tendril_max_step_reach", 0.0)
        setattr(state, "_blob_tendril_max_step_angle", 0.0)
        return displayed_geometry, displayed_motion

    dt = now - previous_ts if now > previous_ts else 0.0
    # A compositor hitch must not turn the visual filter into a one-frame snap.
    dt = min(0.050, dt)
    if dt <= 0.0:
        return list(current_geometry), list(current_motion)

    displayed_geometry: list[float] = []
    displayed_motion: list[float] = []
    max_reach_step = 0.0
    max_angle_step = 0.0
    for idx in range(TENDRIL_COUNT):
        offset = idx * 4
        old_angle = float(current_geometry[offset]) % 1.0
        old_reach = max(0.0, float(current_geometry[offset + 1]))
        target_reach = max(0.0, target_geometry[offset + 1])
        old_activity = max(0.0, float(current_motion[offset + 2]))
        target_activity = max(0.0, target_motion[offset + 2])
        hidden_retarget = (
            max(old_reach, target_reach) < 0.004
            and max(old_activity, target_activity) < 0.030
        )
        new_angle = _ease_angle(
            old_angle,
            target_geometry[offset] % 1.0,
            dt=dt,
            tau=0.075 if hidden_retarget else 0.34,
            max_rate=1.10 if hidden_retarget else 0.12,
        )
        new_reach = _ease_scalar(
            old_reach,
            target_reach,
            dt=dt,
            attack=0.052,
            release=0.235,
        )
        old_root = max(0.0, float(current_geometry[offset + 2]))
        new_root = _ease_scalar(
            old_root,
            max(0.0, target_geometry[offset + 2]),
            dt=dt,
            attack=0.080,
            release=0.155,
        )
        old_tip = max(0.0, float(current_geometry[offset + 3]))
        new_tip = _ease_scalar(
            old_tip,
            max(0.0, target_geometry[offset + 3]),
            dt=dt,
            attack=0.090,
            release=0.165,
        )
        displayed_geometry.extend(
            (new_angle, new_reach, new_root, min(new_tip, new_root))
        )

        old_bend = float(current_motion[offset])
        old_hook = float(current_motion[offset + 1])
        new_bend = old_bend + (
            target_motion[offset] - old_bend
        ) * _exp_alpha(dt, 0.125)
        new_hook = old_hook + (
            target_motion[offset + 1] - old_hook
        ) * _exp_alpha(dt, 0.145)
        new_activity = _ease_scalar(
            old_activity,
            target_activity,
            dt=dt,
            attack=0.045,
            release=0.205,
        )
        target_kind = -1.0 if target_motion[offset + 3] < 0.0 else 1.0
        old_kind_value = float(current_motion[offset + 3])
        old_light = abs(old_kind_value) if old_kind_value * target_kind >= 0.0 else 0.0
        target_light = abs(target_motion[offset + 3])
        new_light = _ease_scalar(
            old_light,
            target_light,
            dt=dt,
            attack=0.070,
            release=0.185,
        )
        displayed_motion.extend(
            (new_bend, new_hook, new_activity, target_kind * new_light)
        )

        max_reach_step = max(max_reach_step, abs(new_reach - old_reach))
        max_angle_step = max(
            max_angle_step,
            abs(((new_angle - old_angle + 0.5) % 1.0) - 0.5),
        )

    setattr(state, "_blob_tendril_geometry", displayed_geometry)
    setattr(state, "_blob_tendril_motion", displayed_motion)
    setattr(state, "_blob_tendril_transport_type", blob_type)
    setattr(state, "_blob_tendril_transport_ts", now)
    setattr(state, "_blob_tendril_max_step_reach", max_reach_step)
    setattr(state, "_blob_tendril_max_step_angle", max_angle_step)
    return displayed_geometry, displayed_motion


def gpu_vocal_wobble_strength(state: Any, *, blob_type: str) -> float:
    """Map the subtype's exposed motion controls to per-paint contour wobble."""

    if blob_type == BLOB_TYPE_SHAPED:
        audio_motion = _clamp(getattr(state, "_blob_shaper_audio_motion", 1.20), 0.0, 3.0)
        react = _clamp(getattr(state, "_blob_shaper_react_strength", 0.5), 0.0, 1.0)
        return _clamp((audio_motion / 2.40) * (0.70 + react * 0.30), 0.0, 1.25)
    reactive = _clamp(getattr(state, "_blob_reactive_wobble", 1.0), 0.0, 3.0)
    shape = _clamp(getattr(state, "_blob_reactive_deformation", 1.0), 0.0, 3.0)
    return _clamp((reactive / 2.40) * (0.55 + min(shape, 2.0) * 0.30), 0.0, 1.25)


__all__ = [
    "TENDRIL_COUNT",
    "TENDRIL_PAYLOAD_SIZE",
    "advance_blob_tendril_state",
    "build_blob_tendril_payload",
    "gpu_vocal_wobble_strength",
]

"""Activation-fenced authored state for the experimental Voxel Sphere mode.

Sphere is deliberately isolated from the accepted visualizers.  This runtime owns
only Sphere's logical envelopes and consumes immutable/public audio seams; it does
not add a timer, poller, worker, alternate audio capture owner, or shared visualizer
reactivity rule.

The response hierarchy is intentionally split by timescale:

* detached cube fragmentation is a *punch* reward. It may be authored only by
  typed vocal/kick/snare/onset events or Sphere-local peak-picked spectral flux over
  the existing temporally-unsmoothed pre-shape/pre-AGC analysis spectrum; generic
  crest/sustained level cannot spray packets;
* ``size_pulse`` is a slowly changing sustained-fullness growth envelope.  Despite
  the historical field name it is not a beat pulse: attack/release are deliberately
  slow so loud passages read heavier without flicker;
* ``tracer_drive``/``tracer_phase`` are event-owned. Each accepted onset queues a
  small amount of tracer travel; there is no free-running tracer clock;
* optional fragment interpolation is visual-only: audio packets still land on the
  exact event frame while rendered displacement remains position/velocity-continuous;
* whole-shell rotation follows current articulation with a short release rather than
  holding near maximum for the duration of active playback.

The accepted stable-face/bevel renderer contract is independent of all of this and
must remain anchored to each cube's unrotated local face identity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from widgets.spotify_visualizer.frame_runtime_lifecycle import RetirableFrameRuntime, retirement_fenced
from widgets.spotify_visualizer.render_state import (
    FrozenFields,
    SphereParticleCohort,
    VisualizerEnergyState,
    VisualizerTransientState,
)

logger = get_logger(__name__)


SECTION_COUNT = 8

# Packet reward/fallout remains generous; this pass changes who may author a
# packet, not the accepted detached travel once one is earned.
_SPHERE_SECTION_RELEASE_S = 0.34
_SPHERE_INCOMING_MIN_INTERVAL_S = 0.26
# Playing-state silence is not permission to author new incoming voxels.  This
# hysteretic gate uses the same live pre-AGC lane that already owns Sphere
# fullness; it is a bug fix/guardrail and is always active.  The accepted
# four-corner pass was subsequently calibrated ~20% less eager without changing
# event ownership or the four-corner participation floor.
_INCOMING_GATE_OPEN = 0.090
_INCOMING_GATE_CLOSE = 0.042
_INCOMING_TYPED_FORCE_FLOOR = 0.030
# Optional energy-scaled cohort density changes only how many members of each
# stable four-corner population launch for a qualified event.  Its full-density
# endpoint is deliberately ~20% higher than the initially accepted calibration.
_INCOMING_DENSITY_MIN_ACTIVE = 0.28
_INCOMING_DENSITY_LOW = 0.096
_INCOMING_DENSITY_HIGH = 1.50
# Optional transient velocity is a cohort accent, not a continuously modulated
# global particle speed.  Strong events return faster initially, then settle
# toward the existing comfortable landing speed.
# Preserve admission at the existing typed-event thresholds, but make the
# optional speed accent wait until ~20% farther through each event's usable
# strength range. This is presentation calibration only: it does not suppress
# the event/cohort itself.
# Real Sphere-local travel cohorts replace the old single exponential
# ``incoming_drive`` decay. Event strength is admission/confidence, not travel
# authority: the shared transient bus legitimately clamps strong events to 1.0,
# so Sphere derives a separate continuous *motion intensity* from local acoustic
# contrast (positive live pre-AGC jump + raw-spectrum flux-over-threshold).
# Intake intentionally has a gentler ordinary return than outtake; strong real
# attacks may still earn the same fast endpoint.
_PARTICLE_COHORT_COUNT = 4
_INCOMING_TRAVEL_FIXED_S = 1.42
_INCOMING_TRAVEL_NORMAL_S = 1.90
_INCOMING_TRAVEL_FAST_S = 0.84
_OUTTAKE_TRAVEL_FIXED_S = 1.12
_OUTTAKE_TRAVEL_NORMAL_S = 1.45
_OUTTAKE_TRAVEL_FAST_S = 0.82
_INCOMING_RECYCLE_PROGRESS = 0.90
_INTAKE_IMPACT_BASELINE_S = 0.48
_INTAKE_IMPACT_ENERGY_LOW = 0.040
_INTAKE_IMPACT_ENERGY_HIGH = 0.62
_INTAKE_IMPACT_FLUX_RATIO_LOW = 0.88
_INTAKE_IMPACT_FLUX_RATIO_HIGH = 2.20
# Ingress dominance is visual state, not a new audio authority.  The stable
# 46% population never changes identity; only the 24% dominant fringe crosses
# between corners over this short presentation interval.
_SPHERE_INCOMING_DOMINANCE_BLEND_S = 0.11
_SPHERE_MAX_STEP_S = 0.05

# Sustained passage weight is intentionally slow.  It must never look like a
# pulse or reproduce transient flicker through whole-shell scaling.
_SUSTAINED_ATTACK_S = 0.52
_SUSTAINED_RELEASE_S = 1.08

# Rotation/tracer respond quickly but are allowed to fall again during active
# music.  The rejected runtime's ~0.93 average rotation drive is explicitly not
# the target architecture.
_SPHERE_ROTATION_ATTACK_S = 0.040
_SPHERE_ROTATION_RELEASE_S = 0.34
_TRACER_ATTACK_S = 0.045
_TRACER_RELEASE_S = 0.34
_TRACER_EVENT_DEBOUNCE_S = 0.090
_TRACER_TARGET_STEP_MIN = 0.28
_TRACER_TARGET_STEP_MAX = 0.44
_TRACER_MAX_BACKLOG = 1.05
_TRACER_PHASE_SPEED_MIN = 0.38
_TRACER_PHASE_SPEED_MAX = 0.78
_TRACER_SETTLE_EPS = 0.012

# Optional visual-only interpolation for detached fragment geometry.  Audio
# admission and packet amplitude remain immediate; only the rendered section
# displacement follows the target through a short critically-damped response.
_FRAGMENT_VISUAL_SMOOTH_TIME_S = 0.030

# Support-aware reactive energy supplies contour/articulation only.  It is never
# sufficient by itself to author detached geometry.
_BASS_FAST_S = 0.030
_BASS_SLOW_S = 0.260
_VOCAL_FAST_S = 0.034
_VOCAL_SLOW_S = 0.300
_BASS_ACTIVITY_GAIN = 7.0
_VOCAL_ACTIVITY_GAIN = 8.5
_ACTIVITY_DEAD_ZONE = 0.045

_VOCAL_PRESENCE_LOW = 0.035
_VOCAL_PRESENCE_HIGH = 0.115
_BASS_PRESENCE_LOW = 0.045
_BASS_PRESENCE_HIGH = 0.150

# Sphere onset authority uses half-wave spectral flux over the existing
# temporally-unsmoothed pre-shape/pre-AGC analysis spectrum, followed by
# adaptive thresholding and peak-picking.  This is the
# only generic (non-typed) fragmentation authority; three-band rise latches
# were rejected because they fired continuously on support-shaped energy.
_FLUX_MEAN_RISE_S = 2.4
_FLUX_MEAN_FALL_S = 0.85
_FLUX_DEV_S = 1.8
_FLUX_THRESHOLD_SIGMA = 1.45
_FLUX_MIN_THRESHOLD = 0.040
_FLUX_MIN_PEAK_AGE_S = 0.012
_FLUX_MAX_PEAK_AGE_S = 0.075
_FLUX_EVENT_REFRACTORY_S = 0.15

# Fragmentation admission. Hardware logs rejected generic crest and reduced-band
# rise latches as counterfeit event authorities. Crest remains diagnostic /
# whole-shell articulation only; generic packet authority is spectral peak-picking.
_PACKET_MIN_INTERVAL_S = 0.16
_TRANSIENT_BASELINE_S = 0.42
_TYPED_VOCAL_MIN_STRENGTH = 0.12
_TYPED_KICK_MIN_STRENGTH = 0.16
_TYPED_SNARE_MIN_STRENGTH = 0.17
_ONSET_MIN_STRENGTH = 0.18

# Incoming sparse blocks are a secondary form of strong local fallout, never an
# ambient particle system.
_INCOMING_VOCAL_MIN = 0.48
_INCOMING_KICK_MIN = 0.48
_INCOMING_SNARE_MIN = 0.52
_INCOMING_ONSET_MIN = 0.58

# Sustained body weight uses the existing pre-AGC lane, whose purpose is to
# preserve real song loudness variance.  The dynamic floor/peak remain Sphere
# local and intentionally very slow to erase historical quiet/heavy contrast.
_FULLNESS_FLOOR_FALL_S = 0.65
_FULLNESS_FLOOR_RISE_S = 120.0
_FULLNESS_PEAK_RISE_S = 0.28
_FULLNESS_PEAK_FALL_S = 24.0
_FULLNESS_MIN_SPAN = 0.10

_DIAG_INTERVAL_S = 0.50


@dataclass(frozen=True, slots=True)
class SphereResolvedFrame:
    authored_time: float
    size_pulse: float
    rotation_drive: float
    rotation_phase: float
    tracer_drive: float
    tracer_phase: float
    section_drives: tuple[float, ...]
    incoming_drive: float
    incoming_density: float
    incoming_section: int
    incoming_previous_section: int
    incoming_blend: float
    particle_cohorts: tuple[SphereParticleCohort, ...]
    parameters: FrozenFields
    energy: VisualizerEnergyState
    transient: VisualizerTransientState
    changed: bool


def _clamp01(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number))


def _bounded_nonnegative(value: object, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(float(maximum), number))


def _ema(current: float, target: float, dt: float, tau: float) -> float:
    if dt <= 0.0:
        return target
    alpha = 1.0 - math.exp(-dt / max(1.0e-6, tau))
    return current + (target - current) * alpha


def _decay(current: float, dt: float, tau: float) -> float:
    if current <= 0.0:
        return 0.0
    if dt <= 0.0:
        return current
    value = current * math.exp(-dt / max(1.0e-6, tau))
    return 0.0 if value < 1.0e-5 else value


def _critical_damp(
    current: float,
    velocity: float,
    target: float,
    dt: float,
    smooth_time: float,
) -> tuple[float, float]:
    """Stable critically-damped visual follower for one scalar geometry lane.

    This is presentation interpolation only: ``target`` may jump on the exact
    audio frame while ``current`` keeps position/velocity continuous.
    """

    if dt <= 0.0:
        return current, velocity
    smooth_time = max(1.0e-4, float(smooth_time))
    omega = 2.0 / smooth_time
    x = omega * dt
    # Unity-style rational approximation of exp(-x), stable for long frames.
    decay = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
    change = current - target
    temp = (velocity + omega * change) * dt
    new_velocity = (velocity - omega * temp) * decay
    raw_value = target + (change + temp) * decay
    new_value = max(0.0, min(1.0, raw_value))
    if (new_value <= 0.0 and new_velocity < 0.0) or (new_value >= 1.0 and new_velocity > 0.0):
        new_velocity = 0.0
    return new_value, new_velocity


def _smooth_gate(value: float, low: float, high: float) -> float:
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    x = (value - low) / max(1.0e-6, high - low)
    return x * x * (3.0 - 2.0 * x)


def _incoming_motion_intensity(event_strength: float, acoustic_impact: float) -> float:
    """Continuous cohort motion authority, deliberately separate from admission.

    The shared transient/event lanes clamp sufficiently strong events to 1.0.  A
    clamped event is still excellent evidence that *something happened*, but it
    cannot tell Sphere whether that event was a mild flat-passage transient or a
    large kick/vocal jump.  Keep only a modest event-confidence floor and let the
    Sphere-local acoustic contrast own the rest of the 0..1 travel range.
    """

    event = _clamp01(event_strength)
    impact = _clamp01(acoustic_impact)
    confidence_floor = 0.07 + 0.19 * event
    return _clamp01(confidence_floor + (1.0 - confidence_floor) * pow(impact, 1.16))


def _motion_activity(fast: float, slow: float, gain: float) -> float:
    raw = abs(float(fast) - float(slow)) * float(gain)
    if raw <= _ACTIVITY_DEAD_ZONE:
        return 0.0
    return _clamp01((raw - _ACTIVITY_DEAD_ZONE) / (1.0 - _ACTIVITY_DEAD_ZONE))


def _consume_event(scheduler: Any, event_type: str, *, max_age_s: float):
    if scheduler is None:
        return None
    consume = getattr(scheduler, "consume_next", None)
    if not callable(consume):
        return None
    try:
        return consume(event_type, max_age_s=max_age_s)
    except Exception:
        return None


def _event_strength(event: object | None) -> float:
    return _clamp01(getattr(event, "strength", 0.0) if event is not None else 0.0)


def _event_packet(strength: float, *, floor: float = 0.0) -> float:
    s = _clamp01(strength)
    if s <= 0.0:
        return 0.0
    return _clamp01(float(floor) + (1.0 - float(floor)) * math.sqrt(s))


@dataclass(slots=True)
class _ParticleCohort:
    active: bool = False
    progress: float = 1.0
    duration: float = _INCOMING_TRAVEL_NORMAL_S
    strength: float = 0.0
    density: float = 0.0
    section: int = 0
    lane: int = 0
    velocity_accent: float = 0.0
    vocal_bounce: float = 0.0
    outtake: bool = False


class SphereFrameRuntime(RetirableFrameRuntime):
    """Own Sphere-only packet, sustained, tracer and rotation envelopes."""

    def __init__(self) -> None:
        super().__init__()
        self._activation_identity: tuple[int, int, int] | None = None
        self._started_at = 0.0
        self._last_ts = 0.0
        self._size_pulse = 0.0
        self._sustained_drive = 0.0
        self._rotation_drive = 0.0
        self._rotation_phase = 0.0
        self._tracer_drive = 0.0
        self._tracer_phase = 0.0
        self._section_targets = [0.0] * SECTION_COUNT
        self._section_drives = [0.0] * SECTION_COUNT
        self._section_velocities = [0.0] * SECTION_COUNT
        self._incoming_drive = 0.0
        self._incoming_density = 1.0
        self._incoming_gate_open = False
        self._incoming_section = 0
        self._incoming_previous_section = 0
        self._incoming_blend = 1.0
        self._incoming_sequence = 0
        self._last_incoming_ts = -1.0e9
        self._intake_energy_slow = 0.0
        self._last_intake_motion_intensity = 0.0
        self._particle_cohorts = [_ParticleCohort() for _ in range(_PARTICLE_COHORT_COUNT)]

        self._bass_fast = 0.0
        self._bass_slow = 0.0
        self._vocal_fast = 0.0
        self._vocal_slow = 0.0
        self._shape_slow = [0.5, 0.5]
        self._transient_slow = [0.0, 0.0, 0.0]
        self._prev_spectrum: tuple[float, ...] = ()
        self._flux_mean = 0.0
        self._flux_dev = 0.0
        self._flux_peak_active = False
        self._flux_peak = 0.0
        self._flux_peak_threshold = 0.0
        self._flux_peak_band = 1
        self._flux_peak_started = 0.0
        self._last_flux_event_ts = -1.0e9
        self._fragment_sequence = 0
        self._tracer_target_phase = 0.0
        self._tracer_impulse = 0.0
        self._last_tracer_event_ts = -1.0e9
        self._fullness_floor = 0.0
        self._fullness_peak = 0.0
        self._fullness_initialized = False
        self._last_packet_ts = -1.0e9
        self._source_active = False

        self._last_diag_ts = 0.0
        self._packets_since_diag = 0
        self._packet_sources_since_diag = {
            "vocal": 0,
            "spectral": 0,
            "kick": 0,
            "snare": 0,
            "onset": 0,
        }

        self._latest = SphereResolvedFrame(
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            tuple(0.0 for _ in range(SECTION_COUNT)),
            0.0,
            1.0,
            0,
            0,
            1.0,
            (),
            FrozenFields(),
            VisualizerEnergyState(),
            VisualizerTransientState(),
            False,
        )

    def reset(self) -> None:
        self.__init__()

    def _section_for_change(
        self,
        *,
        bass: float,
        mid: float,
        high: float,
        source: str,
    ) -> int:
        """Map current spectral balance/contour to one deterministic octant."""

        vocal = max(1.0e-6, float(mid) + float(high))
        brightness = float(high) / vocal
        vocal_weight = vocal / max(1.0e-6, float(bass) + vocal)
        rising = self._vocal_fast >= self._vocal_slow

        section = 0
        if brightness < 0.31:
            section |= 1
        if not rising:
            section |= 2
        if vocal_weight < 0.48:
            section |= 4

        if source in {"kick", "spectral"}:
            section ^= 4
        elif source == "snare":
            section ^= 3
        elif source == "onset":
            section ^= 1
        return section % SECTION_COUNT

    def _emit_packet(
        self,
        *,
        now: float,
        source: str,
        section: int,
        amplitude: float,
    ) -> bool:
        if now - self._last_packet_ts < _PACKET_MIN_INTERVAL_S:
            return False
        idx = int(section) % SECTION_COUNT
        value = _clamp01(amplitude)
        if value <= 0.0:
            return False
        self._section_targets[idx] = max(self._section_targets[idx], value)
        # One onset should read as a fragmented *patch*, not a single hidden
        # octant. Give it one weaker companion region while keeping the event
        # globally sparse in time. The coprime walk prevents a persistent corner.
        neighbor = (idx + 3 + (self._fragment_sequence & 1) * 2) % SECTION_COUNT
        self._section_targets[neighbor] = max(
            self._section_targets[neighbor],
            value * (0.46 if value >= 0.65 else 0.34),
        )
        self._fragment_sequence = (self._fragment_sequence + 1) % SECTION_COUNT
        self._last_packet_ts = now
        self._packets_since_diag += 1
        if source in self._packet_sources_since_diag:
            self._packet_sources_since_diag[source] += 1
        return True

    def _advance_particle_cohorts(self, dt: float) -> None:
        """Advance bounded detached-voxel cohorts without changing audio authority."""

        if dt <= 0.0:
            return
        for cohort in self._particle_cohorts:
            if not cohort.active:
                continue
            cohort.progress = min(1.0, cohort.progress + dt / max(1.0e-6, cohort.duration))
            if cohort.progress >= 1.0:
                cohort.active = False
                cohort.progress = 1.0

        active = [cohort for cohort in self._particle_cohorts if cohort.active]
        if active:
            # Retain the legacy aggregate fields only as diagnostics/backward
            # compatibility for renderer history; cohort progress is the actual
            # travel authority.
            self._incoming_drive = max(
                cohort.strength * (1.0 - cohort.progress) for cohort in active
            )
            newest = min(active, key=lambda cohort: cohort.progress)
            self._incoming_density = newest.density
        else:
            self._incoming_drive = 0.0

    def _particle_cohort_snapshot(self) -> tuple[SphereParticleCohort, ...]:
        return tuple(
            SphereParticleCohort(
                progress=_clamp01(cohort.progress),
                strength=_clamp01(cohort.strength),
                density=_clamp01(cohort.density),
                section=int(cohort.section) & 3,
                lane=int(cohort.lane) & 3,
                velocity_accent=_clamp01(cohort.velocity_accent),
                vocal_bounce=_clamp01(cohort.vocal_bounce),
                outtake=bool(cohort.outtake),
            )
            for cohort in self._particle_cohorts
            if cohort.active
        )

    def _author_incoming(
        self,
        *,
        now: float,
        section: int,
        strength: float,
        density: float,
        velocity_accent: float,
        velocity_response_enabled: bool,
        source: str,
        outtake: bool,
    ) -> None:
        if now - self._last_incoming_ts < _SPHERE_INCOMING_MIN_INTERVAL_S:
            return
        value = _clamp01(strength)
        if value <= 0.0:
            return

        # Reuse an inactive slot first. If all four are still travelling, only
        # recycle only a cohort already visually at the settle boundary. Otherwise
        # the detached layer is visibly full and this secondary reward may coalesce
        # rather than teleport an in-flight population.
        slot = next((item for item in self._particle_cohorts if not item.active), None)
        if slot is None:
            oldest = max(self._particle_cohorts, key=lambda item: item.progress)
            if oldest.progress < _INCOMING_RECYCLE_PROGRESS:
                self._last_incoming_ts = now
                return
            slot = oldest

        velocity = _clamp01(velocity_accent) if velocity_response_enabled else 0.0
        # Duration carries the primary velocity semantics.  Curve velocity rather
        # than linearly mapping it so moderate events occupy the middle of the
        # range instead of visually collapsing toward the fast endpoint.
        speed_mix = pow(velocity, 1.35)
        if outtake:
            duration = (
                _OUTTAKE_TRAVEL_NORMAL_S
                + (_OUTTAKE_TRAVEL_FAST_S - _OUTTAKE_TRAVEL_NORMAL_S) * speed_mix
                if velocity_response_enabled
                else _OUTTAKE_TRAVEL_FIXED_S
            )
            minimum_duration = _OUTTAKE_TRAVEL_FAST_S
        else:
            duration = (
                _INCOMING_TRAVEL_NORMAL_S
                + (_INCOMING_TRAVEL_FAST_S - _INCOMING_TRAVEL_NORMAL_S) * speed_mix
                if velocity_response_enabled
                else _INCOMING_TRAVEL_FIXED_S
            )
            minimum_duration = _INCOMING_TRAVEL_FAST_S

        # Incoming fallout uses four visible ingress quadrants rather than one
        # 3D octant. Each cohort captures one dominant quadrant while all four
        # retain the accepted distributed participation floor.
        next_section = (int(section) + self._incoming_sequence * 3) % 4
        self._incoming_sequence = (self._incoming_sequence + 1) % 4
        if next_section != self._incoming_section:
            self._incoming_previous_section = self._incoming_section
            self._incoming_section = next_section
            self._incoming_blend = 0.0

        slot_index = self._particle_cohorts.index(slot)
        slot.active = True
        slot.progress = 0.0
        slot.duration = max(minimum_duration, float(duration))
        # Keep every admitted event visibly reactive, but let flat transients use
        # modestly less travel amplitude than a genuine acoustic jump.  Bounce is
        # intentionally independent below so vocal recoil keeps its full reward.
        slot.strength = value * (0.76 + 0.24 * velocity) if velocity_response_enabled else value
        slot.density = _clamp01(density)
        slot.section = next_section
        # Fixed lane partitions make overlapping cohorts genuinely independent:
        # each active cohort owns a disjoint quarter of the stable eligible
        # population instead of repeatedly resetting the same 46% foundation.
        slot.lane = slot_index & 3
        slot.velocity_accent = velocity
        # Preserve the physically liked vocal return: a vocal-owned incoming
        # cohort gets one modest late-flight outward recoil before settling.
        slot.vocal_bounce = _clamp01(value if source == "vocal" else 0.0)
        slot.outtake = bool(outtake)

        self._incoming_drive = max(self._incoming_drive, value)
        self._incoming_density = slot.density
        self._last_incoming_ts = now

    def _transient_crest(self, transient: VisualizerTransientState) -> tuple[float, tuple[float, float, float]]:
        raw = (
            _bounded_nonnegative(transient.bass, 3.0),
            _bounded_nonnegative(transient.mid, 3.0),
            _bounded_nonnegative(transient.high, 3.0),
        )
        components: list[float] = []
        for value, baseline in zip(raw, self._transient_slow):
            # Baseline-relative headroom preserves a real edge when the shared
            # transient bus is hot or even pinned at 2.5, then naturally tends
            # back to zero while that plateau remains held.
            denominator = max(0.18, 0.26 + baseline * 0.24)
            components.append(_clamp01(max(0.0, value - baseline) / denominator))
        # Bass is useful for one-hit kicks, while mid/high are slightly preferred
        # so vocals and piano attacks do not have to compete with a hot low-end bed.
        score = _clamp01(max(components[0] * 0.90, components[1] * 0.98, components[2]))
        return score, (components[0], components[1], components[2])

    def _spectral_onset(
        self,
        *,
        now: float,
        dt: float,
        spectrum: tuple[float, ...],
    ) -> tuple[float, int, float, float, float]:
        """Peak-pick half-wave flux from the raw existing analysis spectrum.

        ``spectrum`` is published at the verified FFT commit boundary before
        Spectrum shape, temporal bar smoothing and AGC. It is already frequency
        binned by the existing analysis worker, so Sphere adds no FFT/worker.

        Flux uses positive log-ratio movement with a support gate. This preserves
        attacks across quiet and loud songs without letting tiny near-zero noise
        bins win merely because their relative ratio is large.
        """
        current = tuple(_bounded_nonnegative(value, 1.0e6) for value in spectrum)
        spectrum_level = sum(current) / max(1, len(current)) if current else 0.0
        if len(current) < 8:
            self._prev_spectrum = current
            self._flux_peak_active = False
            return 0.0, 1, 0.0, 0.0, spectrum_level
        if len(self._prev_spectrum) != len(current):
            self._prev_spectrum = current
            self._flux_peak_active = False
            threshold = max(
                _FLUX_MIN_THRESHOLD,
                self._flux_mean + _FLUX_THRESHOLD_SIGMA * self._flux_dev,
            )
            return 0.0, 1, self._flux_mean, threshold, spectrum_level

        previous = self._prev_spectrum
        previous_level = sum(previous) / max(1, len(previous))
        epsilon = max(1.0e-8, min(spectrum_level, previous_level) * 0.012)
        support_scale = max(1.0e-8, spectrum_level * 0.34)
        diffs: list[float] = []
        for value, prior in zip(current, previous):
            log_rise = max(
                0.0,
                math.log(value + epsilon) - math.log(prior + epsilon),
            )
            support = value / (value + support_scale) if value > 0.0 else 0.0
            diffs.append(log_rise * support)
        self._prev_spectrum = current

        count = len(diffs)
        low_end = max(1, int(count * 0.23))
        mid_end = max(low_end + 1, int(count * 0.68))
        weighted: list[float] = []
        band_sums = [0.0, 0.0, 0.0]
        band_counts = [0, 0, 0]
        for index, diff in enumerate(diffs):
            if index < low_end:
                band, weight = 0, 0.88
            elif index < mid_end:
                band, weight = 1, 1.08
            else:
                band, weight = 2, 1.16
            sample = diff * weight
            weighted.append(sample)
            band_sums[band] += sample
            band_counts[band] += 1
        mean_flux = sum(weighted) / max(1, count)
        top_count = max(3, count // 10)
        top_flux = sum(sorted(weighted)[-top_count:]) / top_count
        flux = mean_flux * 0.40 + top_flux * 0.60
        band_means = [band_sums[i] / max(1, band_counts[i]) for i in range(3)]
        dominant_band = max(range(3), key=band_means.__getitem__)

        threshold = max(
            _FLUX_MIN_THRESHOLD,
            self._flux_mean + _FLUX_THRESHOLD_SIGMA * self._flux_dev,
        )
        onset_strength = 0.0
        onset_band = dominant_band
        if flux > threshold:
            if not self._flux_peak_active:
                self._flux_peak_active = True
                self._flux_peak = flux
                self._flux_peak_threshold = threshold
                self._flux_peak_band = dominant_band
                self._flux_peak_started = now
            elif flux > self._flux_peak:
                self._flux_peak = flux
                self._flux_peak_band = dominant_band
            peak_age = max(0.0, now - self._flux_peak_started)
            if peak_age >= _FLUX_MAX_PEAK_AGE_S:
                if now - self._last_flux_event_ts >= _FLUX_EVENT_REFRACTORY_S:
                    excess = max(0.0, self._flux_peak - self._flux_peak_threshold)
                    onset_strength = _clamp01(
                        0.30 + excess / max(0.020, self._flux_peak_threshold * 2.2)
                    )
                    onset_band = self._flux_peak_band
                    self._last_flux_event_ts = now
                self._flux_peak_active = False
        elif self._flux_peak_active:
            peak_age = max(0.0, now - self._flux_peak_started)
            if (
                peak_age >= _FLUX_MIN_PEAK_AGE_S
                and now - self._last_flux_event_ts >= _FLUX_EVENT_REFRACTORY_S
            ):
                excess = max(0.0, self._flux_peak - self._flux_peak_threshold)
                onset_strength = _clamp01(
                    0.30 + excess / max(0.020, self._flux_peak_threshold * 2.2)
                )
                onset_band = self._flux_peak_band
                self._last_flux_event_ts = now
            self._flux_peak_active = False

        if dt > 0.0:
            mean_tau = _FLUX_MEAN_RISE_S if flux > self._flux_mean else _FLUX_MEAN_FALL_S
            old_mean = self._flux_mean
            self._flux_mean = _ema(self._flux_mean, flux, dt, mean_tau)
            self._flux_dev = _ema(
                self._flux_dev, abs(flux - old_mean), dt, _FLUX_DEV_S
            )
        return onset_strength, onset_band, flux, threshold, spectrum_level

    def _trigger_tracer(self, *, now: float, strength: float) -> None:
        value = _clamp01(strength)
        if value <= 0.0 or now - self._last_tracer_event_ts < _TRACER_EVENT_DEBOUNCE_S:
            return
        step = _TRACER_TARGET_STEP_MIN + (
            _TRACER_TARGET_STEP_MAX - _TRACER_TARGET_STEP_MIN
        ) * value
        remaining = max(0.0, self._tracer_target_phase - self._tracer_phase)
        queued = min(_TRACER_MAX_BACKLOG, remaining + step)
        self._tracer_target_phase = self._tracer_phase + queued
        self._tracer_impulse = max(self._tracer_impulse, 0.72 + 0.28 * value)
        self._last_tracer_event_ts = now

    @retirement_fenced
    def resolve(
        self,
        *,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        source_active: bool,
        energy: VisualizerEnergyState,
        reactive_energy: VisualizerEnergyState,
        presence_energy: VisualizerEnergyState,
        transient: VisualizerTransientState,
        analysis_spectrum: tuple[float, ...],
        event_scheduler: Any,
        parameters: FrozenFields,
    ) -> SphereResolvedFrame | None:
        if not isinstance(parameters, FrozenFields):
            raise TypeError("Sphere runtime requires configure-owned FrozenFields")
        for value, name in (
            (energy, "energy"),
            (reactive_energy, "reactive energy"),
            (presence_energy, "presence energy"),
        ):
            if not isinstance(value, VisualizerEnergyState):
                raise TypeError(f"Sphere runtime requires VisualizerEnergyState for {name}")
        if not isinstance(transient, VisualizerTransientState):
            raise TypeError("Sphere runtime requires VisualizerTransientState")
        if not isinstance(analysis_spectrum, tuple):
            raise TypeError("Sphere runtime requires immutable pre-AGC analysis spectrum tuple")

        now = float(now_ts)
        active = bool(source_active)
        identity = (int(runtime_generation), int(engine_generation), int(activation_id))
        first_identity = identity != self._activation_identity
        if first_identity:
            self._activation_identity = identity
            self._started_at = now
            self._last_ts = now
            self._size_pulse = 0.0
            self._sustained_drive = 0.0
            self._rotation_drive = 0.0
            self._rotation_phase = 0.0
            self._tracer_drive = 0.0
            self._tracer_phase = 0.0
            self._section_targets = [0.0] * SECTION_COUNT
            self._section_drives = [0.0] * SECTION_COUNT
            self._section_velocities = [0.0] * SECTION_COUNT
            self._incoming_drive = 0.0
            self._incoming_density = 1.0
            self._incoming_gate_open = False
            self._incoming_section = 0
            self._incoming_previous_section = 0
            self._incoming_blend = 1.0
            self._incoming_sequence = 0
            self._last_incoming_ts = -1.0e9
            self._particle_cohorts = [_ParticleCohort() for _ in range(_PARTICLE_COHORT_COUNT)]

            bass_now = _clamp01(reactive_energy.bass) if active else 0.0
            mid_now = _clamp01(reactive_energy.mid) if active else 0.0
            high_now = _clamp01(reactive_energy.high) if active else 0.0
            vocal_now = mid_now * 0.66 + high_now * 0.34
            self._bass_fast = self._bass_slow = bass_now
            self._vocal_fast = self._vocal_slow = vocal_now
            shape_total = max(1.0e-6, mid_now + high_now)
            self._shape_slow = [mid_now / shape_total, high_now / shape_total]
            self._transient_slow = [
                _bounded_nonnegative(transient.bass, 3.0) if active else 0.0,
                _bounded_nonnegative(transient.mid, 3.0) if active else 0.0,
                _bounded_nonnegative(transient.high, 3.0) if active else 0.0,
            ]
            self._prev_spectrum = tuple(_bounded_nonnegative(value, 1.0e6) for value in analysis_spectrum) if active else ()
            self._flux_mean = 0.0
            self._flux_dev = 0.0
            self._flux_peak_active = False
            self._flux_peak = 0.0
            self._flux_peak_threshold = 0.0
            self._flux_peak_band = 1
            self._flux_peak_started = now
            self._last_flux_event_ts = -1.0e9
            self._fragment_sequence = 0
            self._tracer_target_phase = 0.0
            self._tracer_impulse = 0.0
            self._last_tracer_event_ts = -1.0e9
            initial_live_bass = _bounded_nonnegative(presence_energy.bass, 2.5) if active else 0.0
            initial_live_mid = _bounded_nonnegative(presence_energy.mid, 2.5) if active else 0.0
            initial_live_high = _bounded_nonnegative(presence_energy.high, 2.5) if active else 0.0
            initial_fullness = (
                initial_live_bass * 0.18
                + initial_live_mid * 0.58
                + initial_live_high * 0.24
            ) if active else 0.0
            self._intake_energy_slow = max(
                initial_fullness,
                initial_live_bass * 0.55,
                initial_live_mid * 0.70,
                initial_live_high * 0.70,
            ) if active else 0.0
            self._last_intake_motion_intensity = 0.0
            self._fullness_floor = initial_fullness
            self._fullness_peak = initial_fullness
            self._fullness_initialized = bool(active)
            self._last_packet_ts = -1.0e9
            self._source_active = active
            self._last_diag_ts = now
            self._packets_since_diag = 0
            for key in self._packet_sources_since_diag:
                self._packet_sources_since_diag[key] = 0
            dt = 0.0
        else:
            dt = max(0.0, min(_SPHERE_MAX_STEP_S, now - self._last_ts))
            self._last_ts = now

        # Existing detached cohorts are presentation state and finish naturally
        # even when the source becomes quiet or inactive. Playback state only
        # controls whether another cohort may be authored.
        self._advance_particle_cohorts(dt)

        bass_now = _clamp01(reactive_energy.bass) if active else 0.0
        mid_now = _clamp01(reactive_energy.mid) if active else 0.0
        high_now = _clamp01(reactive_energy.high) if active else 0.0
        vocal_now = mid_now * 0.66 + high_now * 0.34

        live_bass = _bounded_nonnegative(presence_energy.bass, 2.5) if active else 0.0
        live_mid = _bounded_nonnegative(presence_energy.mid, 2.5) if active else 0.0
        live_high = _bounded_nonnegative(presence_energy.high, 2.5) if active else 0.0
        presence_bass = _clamp01(live_bass)
        presence_mid = _clamp01(live_mid)
        presence_high = _clamp01(live_high)
        presence_vocal = (presence_mid * 0.68 + presence_high * 0.32) if active else 0.0
        loudness_now = (
            live_bass * 0.18 + live_mid * 0.58 + live_high * 0.24
        ) if active else 0.0
        bass_presence_gate = _smooth_gate(presence_bass, _BASS_PRESENCE_LOW, _BASS_PRESENCE_HIGH)
        vocal_presence_gate = _smooth_gate(
            presence_vocal,
            _VOCAL_PRESENCE_LOW,
            _VOCAL_PRESENCE_HIGH,
        )
        # Intake authority is intentionally separate from playback state.  The
        # max-lane term keeps a real isolated kick/vocal eligible while true PCM
        # silence (all live pre-AGC lanes ~0) closes the gate deterministically.
        intake_energy = max(
            loudness_now,
            live_bass * 0.55,
            live_mid * 0.70,
            live_high * 0.70,
        ) if active else 0.0
        if not active:
            self._incoming_gate_open = False
        elif self._incoming_gate_open:
            if intake_energy <= _INCOMING_GATE_CLOSE:
                self._incoming_gate_open = False
        elif intake_energy >= _INCOMING_GATE_OPEN:
            self._incoming_gate_open = True

        if dt > 0.0:
            for index, current in enumerate(self._section_targets):
                self._section_targets[index] = _decay(current, dt, _SPHERE_SECTION_RELEASE_S)
            if self._incoming_blend < 1.0:
                self._incoming_blend = min(
                    1.0,
                    self._incoming_blend + dt / _SPHERE_INCOMING_DOMINANCE_BLEND_S,
                )

        if not active:
            self._bass_fast = self._bass_slow = 0.0
            self._vocal_fast = self._vocal_slow = 0.0
            self._shape_slow = [0.5, 0.5]
            self._transient_slow = [0.0, 0.0, 0.0]
            self._prev_spectrum = ()
            self._flux_peak_active = False
            self._flux_mean = 0.0
            self._flux_dev = 0.0
            self._tracer_impulse = 0.0
            self._tracer_target_phase = self._tracer_phase
            self._incoming_gate_open = False
            self._intake_energy_slow = 0.0
            self._last_intake_motion_intensity = 0.0
            self._fullness_floor = 0.0
            self._fullness_peak = 0.0
            self._fullness_initialized = False
            self._source_active = False
            bass_activity = vocal_activity = 0.0
            gated_bass_activity = gated_vocal_activity = 0.0
            spectral_onset_strength = 0.0
            spectral_onset_band = 1
            spectral_flux = spectral_threshold = spectrum_level = 0.0
            kick_event_strength = vocal_event_strength = snare_event_strength = 0.0
            onset_strength = 0.0
            shape_change = envelope_change = 0.0
            crest_score = 0.0
            crest_components = (0.0, 0.0, 0.0)
            articulation_score = 0.0
            sustained_target = 0.0
            fullness = 0.0
            relative_fullness = 0.0
            staged_growth = 0.0
            rotation_target = 0.0
            acoustic_impact = 0.0
        else:
            if not self._source_active:
                self._bass_fast = self._bass_slow = bass_now
                self._vocal_fast = self._vocal_slow = vocal_now
                self._transient_slow = [
                    _bounded_nonnegative(transient.bass, 3.0),
                    _bounded_nonnegative(transient.mid, 3.0),
                    _bounded_nonnegative(transient.high, 3.0),
                ]
                self._prev_spectrum = tuple(_bounded_nonnegative(value, 1.0e6) for value in analysis_spectrum)
                self._flux_peak_active = False
                self._flux_mean = 0.0
                self._flux_dev = 0.0
                initial_fullness = loudness_now
                self._intake_energy_slow = intake_energy
                self._last_intake_motion_intensity = 0.0
                self._fullness_floor = initial_fullness
                self._fullness_peak = initial_fullness
                self._fullness_initialized = True
                self._source_active = True
            elif dt > 0.0:
                self._bass_fast = _ema(self._bass_fast, bass_now, dt, _BASS_FAST_S)
                self._bass_slow = _ema(self._bass_slow, bass_now, dt, _BASS_SLOW_S)
                self._vocal_fast = _ema(self._vocal_fast, vocal_now, dt, _VOCAL_FAST_S)
                self._vocal_slow = _ema(self._vocal_slow, vocal_now, dt, _VOCAL_SLOW_S)

            bass_activity = _motion_activity(self._bass_fast, self._bass_slow, _BASS_ACTIVITY_GAIN)
            vocal_activity = _motion_activity(self._vocal_fast, self._vocal_slow, _VOCAL_ACTIVITY_GAIN)
            gated_bass_activity = bass_activity * bass_presence_gate
            gated_vocal_activity = vocal_activity * vocal_presence_gate
            (
                spectral_onset_strength,
                spectral_onset_band,
                spectral_flux,
                spectral_threshold,
                spectrum_level,
            ) = self._spectral_onset(
                now=now,
                dt=dt,
                spectrum=analysis_spectrum,
            )

            kick_event_strength = _event_strength(
                _consume_event(event_scheduler, "kick", max_age_s=0.28)
            )
            vocal_event_strength = _event_strength(
                _consume_event(event_scheduler, "vocal_swell", max_age_s=0.32)
            )
            snare_event_strength = _event_strength(
                _consume_event(event_scheduler, "snare", max_age_s=0.22)
            )
            onset_strength = (
                _clamp01(transient.onset_strength)
                if transient.onset_detected
                else 0.0
            )

            # Spectral-shape and envelope movement remain useful *articulation*
            # evidence for tracer/rotation.  They are explicitly not packet
            # candidates anymore.
            vocal_shape_total = max(1.0e-6, mid_now + high_now)
            shape_now = (mid_now / vocal_shape_total, high_now / vocal_shape_total)
            shape_delta = (
                abs(shape_now[0] - self._shape_slow[0]) * 1.35
                + abs(shape_now[1] - self._shape_slow[1]) * 1.55
            )
            shape_change = _clamp01(shape_delta * 2.75)
            envelope_change = _clamp01(
                abs(self._vocal_fast - self._vocal_slow)
                / max(0.075, 0.13 + self._vocal_slow)
            )
            if dt > 0.0:
                for idx, value in enumerate(shape_now):
                    self._shape_slow[idx] = _ema(self._shape_slow[idx], value, dt, 0.36)

            crest_score, crest_components = self._transient_crest(transient)
            # Update the transient baseline *after* measuring the rising crest.
            # A held 2.5 plateau therefore converges to zero crest and cannot keep
            # authoring packets just because the shared bus remains saturated.
            if dt > 0.0:
                raw_transient = (
                    _bounded_nonnegative(transient.bass, 3.0),
                    _bounded_nonnegative(transient.mid, 3.0),
                    _bounded_nonnegative(transient.high, 3.0),
                )
                for idx, value in enumerate(raw_transient):
                    self._transient_slow[idx] = _ema(
                        self._transient_slow[idx], value, dt, _TRANSIENT_BASELINE_S
                    )

            vocal_response = max(0.0, min(1.35, float(parameters["sphere_vocal_response"])))
            response_scale = vocal_response
            candidates: list[tuple[float, str, float]] = []

            if vocal_response > 0.0 and vocal_event_strength >= _TYPED_VOCAL_MIN_STRENGTH:
                amplitude = (0.42 + 0.54 * math.sqrt(vocal_event_strength)) * response_scale
                candidates.append((amplitude + 0.18, "vocal", amplitude))

            # Generic fragmentation now follows a real onset-detection shape:
            # half-wave spectral flux across the existing bar spectrum, adaptive
            # threshold, then local peak-picking. Three-band rise latches were
            # rejected by hardware because they re-armed on ordinary bass chatter.
            if spectral_onset_strength > 0.0:
                amplitude = 0.70 + 0.30 * math.sqrt(spectral_onset_strength)
                candidates.append((amplitude + 0.15, "spectral", amplitude))

            if kick_event_strength >= _TYPED_KICK_MIN_STRENGTH:
                amplitude = 0.58 + 0.40 * math.sqrt(kick_event_strength)
                candidates.append((amplitude + 0.22, "kick", amplitude))

            if snare_event_strength >= _TYPED_SNARE_MIN_STRENGTH:
                amplitude = 0.44 + 0.46 * math.sqrt(snare_event_strength)
                candidates.append((amplitude + 0.19, "snare", amplitude))

            if onset_strength >= _ONSET_MIN_STRENGTH:
                amplitude = 0.46 + 0.46 * math.sqrt(onset_strength)
                candidates.append((amplitude + 0.16, "onset", amplitude))

            if candidates:
                _priority, packet_source, packet_amplitude = max(candidates, key=lambda item: item[0])
                packet_section = self._section_for_change(
                    bass=bass_now,
                    mid=mid_now,
                    high=high_now,
                    source=packet_source,
                )
                emitted = self._emit_packet(
                    now=now,
                    source=packet_source,
                    section=packet_section,
                    amplitude=packet_amplitude,
                )
                _ = emitted

            # Density and velocity are captured per cohort on its event frame.
            # They do not continuously modulate already travelling voxels.
            density_enabled = bool(parameters["sphere_incoming_density_response_enabled"])
            velocity_enabled = bool(parameters["sphere_incoming_transient_velocity_enabled"])
            outtake_enabled = bool(parameters["sphere_particle_outtake_enabled"])

            # Incoming fallout is independently owned by strong typed/onset
            # events. A rise packet winning the fragmentation race must not hide a
            # real vocal/kick arrival, and generic crest/shape activity can never
            # turn this into an ambient particle emitter.
            #
            # Crucially, event strength is *not* velocity strength. The shared
            # transient bus clamps large events to 1.0, which is correct for event
            # confidence but previously made quiet/flat and huge attacks travel at
            # effectively the same speed. Derive a continuous Sphere-local acoustic
            # impact from positive live-pre-AGC jump plus raw-spectrum flux ratio.
            positive_jump = max(0.0, intake_energy - self._intake_energy_slow)
            jump_impact = _smooth_gate(
                positive_jump, _INTAKE_IMPACT_ENERGY_LOW, _INTAKE_IMPACT_ENERGY_HIGH
            )
            flux_ratio = spectral_flux / max(_FLUX_MIN_THRESHOLD, spectral_threshold)
            flux_impact = _smooth_gate(
                flux_ratio, _INTAKE_IMPACT_FLUX_RATIO_LOW, _INTAKE_IMPACT_FLUX_RATIO_HIGH
            )
            acoustic_impact = _clamp01(max(jump_impact, flux_impact))
            if dt > 0.0:
                self._intake_energy_slow = _ema(
                    self._intake_energy_slow, intake_energy, dt, _INTAKE_IMPACT_BASELINE_S
                )

            incoming_candidates: list[tuple[float, str, int, float, float]] = []
            if vocal_event_strength >= _INCOMING_VOCAL_MIN:
                incoming_candidates.append((
                    vocal_event_strength + 0.08,
                    "vocal",
                    self._section_for_change(bass=bass_now, mid=mid_now, high=high_now, source="vocal"),
                    0.34 + 0.46 * math.sqrt(vocal_event_strength),
                    vocal_event_strength,
                ))
            if kick_event_strength >= _INCOMING_KICK_MIN:
                incoming_candidates.append((
                    kick_event_strength + 0.12,
                    "kick",
                    self._section_for_change(bass=bass_now, mid=mid_now, high=high_now, source="kick"),
                    0.38 + 0.42 * math.sqrt(kick_event_strength),
                    kick_event_strength,
                ))
            if snare_event_strength >= _INCOMING_SNARE_MIN:
                incoming_candidates.append((
                    snare_event_strength + 0.10,
                    "snare",
                    self._section_for_change(bass=bass_now, mid=mid_now, high=high_now, source="snare"),
                    0.30 + 0.38 * math.sqrt(snare_event_strength),
                    snare_event_strength,
                ))
            if onset_strength >= _INCOMING_ONSET_MIN:
                incoming_candidates.append((
                    onset_strength + 0.06,
                    "onset",
                    self._section_for_change(bass=bass_now, mid=mid_now, high=high_now, source="onset"),
                    0.26 + 0.38 * math.sqrt(onset_strength),
                    onset_strength,
                ))
            typed_force_gate = bool(
                incoming_candidates and intake_energy >= _INCOMING_TYPED_FORCE_FLOOR
            )
            if incoming_candidates and (self._incoming_gate_open or typed_force_gate):
                _incoming_priority, incoming_source, incoming_section, incoming_strength, event_confidence = max(
                    incoming_candidates, key=lambda item: item[0]
                )
                motion_intensity = _incoming_motion_intensity(event_confidence, acoustic_impact)
                self._last_intake_motion_intensity = motion_intensity
                if density_enabled:
                    density_activity = _smooth_gate(
                        intake_energy, _INCOMING_DENSITY_LOW, _INCOMING_DENSITY_HIGH
                    )
                    incoming_density = (
                        _INCOMING_DENSITY_MIN_ACTIVE
                        + (1.0 - _INCOMING_DENSITY_MIN_ACTIVE)
                        * math.sqrt(density_activity)
                    )
                else:
                    incoming_density = 1.0
                self._author_incoming(
                    now=now,
                    section=incoming_section,
                    strength=incoming_strength,
                    density=incoming_density,
                    velocity_accent=motion_intensity if velocity_enabled else 0.0,
                    velocity_response_enabled=velocity_enabled,
                    source=incoming_source,
                    outtake=outtake_enabled,
                )
            elif not incoming_candidates:
                self._last_intake_motion_intensity = 0.0

            # Sustained passage weight uses the existing PRE-AGC loudness seam.
            # The support-shaped Bubble feed is intentionally excellent for
            # continuous motion, but hardware showed it is the wrong authority for
            # quiet->heavy body weight because it stays deliberately normalized.
            fullness = loudness_now
            sustained_target = fullness
            if not self._fullness_initialized:
                self._fullness_floor = fullness
                self._fullness_peak = fullness
                self._fullness_initialized = True
            elif dt > 0.0:
                floor_tau = (
                    _FULLNESS_FLOOR_FALL_S
                    if fullness < self._fullness_floor
                    else _FULLNESS_FLOOR_RISE_S
                )
                peak_tau = (
                    _FULLNESS_PEAK_RISE_S
                    if fullness > self._fullness_peak
                    else _FULLNESS_PEAK_FALL_S
                )
                self._fullness_floor = _ema(
                    self._fullness_floor, fullness, dt, floor_tau
                )
                self._fullness_peak = _ema(
                    self._fullness_peak, fullness, dt, peak_tau
                )

            articulation_score = _clamp01(max(
                crest_score,
                _event_packet(kick_event_strength) * 0.98,
                _event_packet(vocal_event_strength) * 0.92,
                _event_packet(snare_event_strength) * 0.90,
                onset_strength * 0.92,
                gated_vocal_activity * 0.72,
                gated_bass_activity * 0.34,
                shape_change * 0.34 * vocal_presence_gate,
                envelope_change * 0.56 * vocal_presence_gate,
            ))
            # One event stream owns tracer travel. Spectral and typed evidence
            # are coalesced so one sound cannot queue several copies of itself.
            tracer_enabled = bool(parameters["sphere_light_tracer_enabled"])
            tracer_event_strength = _clamp01(max(
                spectral_onset_strength,
                _event_packet(kick_event_strength),
                _event_packet(vocal_event_strength) * 0.92,
                _event_packet(snare_event_strength) * 0.94,
                onset_strength * 0.92,
            ))
            if tracer_enabled and tracer_event_strength > 0.0:
                self._trigger_tracer(now=now, strength=tracer_event_strength)

            rotation_target = _clamp01(max(
                articulation_score * 0.76,
                crest_score * 0.92,
                _event_packet(kick_event_strength) * 0.86,
                _event_packet(vocal_event_strength) * 0.76,
                onset_strength * 0.74,
                sustained_target * 0.08 * max(bass_presence_gate, vocal_presence_gate),
            ))

        relative_fullness = 0.0
        staged_growth = 0.0
        if dt > 0.0:
            sustained_tau = (
                _SUSTAINED_ATTACK_S
                if sustained_target > self._sustained_drive
                else _SUSTAINED_RELEASE_S
            )
            self._sustained_drive = _ema(
                self._sustained_drive,
                sustained_target,
                dt,
                sustained_tau,
            )
            size_response = max(0.0, min(2.54, float(parameters["sphere_size_response"])))
            max_growth = min(0.42, 0.040 + 0.150 * size_response)
            if active:
                dynamic_span = max(
                    _FULLNESS_MIN_SPAN,
                    self._fullness_peak - self._fullness_floor,
                )
                relative_fullness = _clamp01(
                    (self._sustained_drive - self._fullness_floor) / dynamic_span
                )
                # Do not let near-silence calibrate itself into a false top stage.
                relative_fullness *= _smooth_gate(self._sustained_drive, 0.04, 0.16)
                # Four visibly separated song-relative stages. The first three are
                # graduated; the last remains deliberately hard so only a real
                # sustained peak reaches the largest shell state.
                stage0 = 0.16 * _smooth_gate(relative_fullness, 0.12, 0.30)
                stage1 = 0.22 * _smooth_gate(relative_fullness, 0.30, 0.48)
                stage2 = 0.27 * _smooth_gate(relative_fullness, 0.48, 0.68)
                stage3 = 0.35 * _smooth_gate(relative_fullness, 0.76, 0.94)
                staged_growth = _clamp01(stage0 + stage1 + stage2 + stage3)
                size_target = max_growth * staged_growth
            else:
                relative_fullness = 0.0
                staged_growth = 0.0
                size_target = 0.0
            self._size_pulse = _ema(
                self._size_pulse,
                size_target,
                dt,
                _SUSTAINED_ATTACK_S if size_target > self._size_pulse else _SUSTAINED_RELEASE_S,
            )

            tracer_enabled = active and bool(parameters["sphere_light_tracer_enabled"])
            if not tracer_enabled:
                self._tracer_impulse = 0.0
                self._tracer_target_phase = self._tracer_phase
                tracer_target = 0.0
            else:
                remaining = max(0.0, self._tracer_target_phase - self._tracer_phase)
                moving = remaining > _TRACER_SETTLE_EPS
                if moving:
                    backlog = _clamp01(remaining / _TRACER_MAX_BACKLOG)
                    phase_speed = _TRACER_PHASE_SPEED_MIN + (
                        _TRACER_PHASE_SPEED_MAX - _TRACER_PHASE_SPEED_MIN
                    ) * backlog
                    self._tracer_phase += min(remaining, phase_speed * dt)
                    tracer_target = max(0.72, self._tracer_impulse)
                else:
                    self._tracer_phase = self._tracer_target_phase
                    self._tracer_impulse = _decay(self._tracer_impulse, dt, 0.30)
                    tracer_target = self._tracer_impulse
            tracer_tau = _TRACER_ATTACK_S if tracer_target > self._tracer_drive else _TRACER_RELEASE_S
            self._tracer_drive = _ema(self._tracer_drive, tracer_target, dt, tracer_tau)

            rotation_tau = (
                _SPHERE_ROTATION_ATTACK_S
                if rotation_target > self._rotation_drive
                else _SPHERE_ROTATION_RELEASE_S
            )
            self._rotation_drive = _ema(self._rotation_drive, rotation_target, dt, rotation_tau)

            base_rotation_speed = max(0.0, min(0.5, float(parameters["sphere_base_rotation_speed"])))
            velocity_reaction = max(0.0, min(2.0, float(parameters["sphere_rotation_speed"])))
            rotation_velocity = base_rotation_speed + velocity_reaction * self._rotation_drive
            self._rotation_phase += rotation_velocity * dt
        else:
            base_rotation_speed = max(0.0, min(0.5, float(parameters["sphere_base_rotation_speed"])))
            velocity_reaction = max(0.0, min(2.0, float(parameters["sphere_rotation_speed"])))
            rotation_velocity = base_rotation_speed + velocity_reaction * self._rotation_drive

        # Audio packets always update ``_section_targets`` immediately.  The
        # optional visual interpolation changes only rendered geometry continuity;
        # it never delays/filters onset detection or lowers authored packet strength.
        interpolate_fragments = bool(parameters["sphere_fragment_interpolation_enabled"])
        if interpolate_fragments and dt > 0.0:
            for index, target in enumerate(self._section_targets):
                value, velocity = _critical_damp(
                    self._section_drives[index],
                    self._section_velocities[index],
                    target,
                    dt,
                    _FRAGMENT_VISUAL_SMOOTH_TIME_S,
                )
                self._section_drives[index] = value
                self._section_velocities[index] = velocity
        else:
            self._section_drives = list(self._section_targets)
            self._section_velocities = [0.0] * SECTION_COUNT

        authored_time = max(0.0, now - self._started_at)
        section_tuple = tuple(self._section_drives)
        particle_cohorts = self._particle_cohort_snapshot()
        resolved = SphereResolvedFrame(
            authored_time,
            self._size_pulse,
            self._rotation_drive,
            self._rotation_phase,
            self._tracer_drive,
            self._tracer_phase,
            section_tuple,
            self._incoming_drive,
            self._incoming_density,
            self._incoming_section,
            self._incoming_previous_section,
            self._incoming_blend,
            particle_cohorts,
            parameters,
            energy,
            transient,
            resolved_differs(
                self._latest,
                authored_time,
                self._size_pulse,
                self._rotation_drive,
                self._rotation_phase,
                self._tracer_drive,
                self._tracer_phase,
                section_tuple,
                self._incoming_drive,
                self._incoming_density,
                self._incoming_section,
                self._incoming_previous_section,
                self._incoming_blend,
                particle_cohorts,
                parameters,
                energy,
                transient,
            ),
        )
        self._latest = resolved

        if is_viz_diagnostics_enabled() and now - self._last_diag_ts >= _DIAG_INTERVAL_S:
            logger.debug(
                "[SPHERE_AUDIO] active=%s reactive=%.3f/%.3f/%.3f live=%.3f/%.3f/%.3f presence=%.3f/%.3f "
                "activity=%.3f/%.3f spectrum=%.5f flux=%.4f threshold=%.4f spectral_evt=%.3f/%d crest=%.3f crest_bmh=%.3f/%.3f/%.3f shape=%.3f envelope=%.3f "
                "events=%.3f/%.3f/%.3f onset=%.3f loudness=%.3f floor=%.3f peak=%.3f sustained=%.3f relative=%.3f stage=%.3f body=%.3f tracer=%.3f tracer_phase=%.3f tracer_target=%.3f tracer_remaining=%.3f rotation=%.3f target=%.3f velocity=%.4f phase=%.3f intake=%.3f gate=%s density=%.3f impact=%.3f motion=%.3f cohorts=%d in/out=%d/%d progress=%.3f-%.3f cohort_v=%.3f-%.3f incoming=%.3f/%d<-%d@%.2f section_target=%.3f section_visual=%.3f active_sections=%d packets=%d packet_src=%d/%d/%d/%d/%d",
                active,
                bass_now,
                mid_now,
                high_now,
                live_bass,
                live_mid,
                live_high,
                presence_bass,
                presence_vocal,
                gated_bass_activity,
                gated_vocal_activity,
                spectrum_level,
                spectral_flux,
                spectral_threshold,
                spectral_onset_strength,
                spectral_onset_band,
                crest_score,
                crest_components[0],
                crest_components[1],
                crest_components[2],
                shape_change,
                envelope_change,
                kick_event_strength,
                vocal_event_strength,
                snare_event_strength,
                onset_strength,
                fullness,
                self._fullness_floor,
                self._fullness_peak,
                self._sustained_drive,
                relative_fullness,
                staged_growth,
                self._size_pulse,
                self._tracer_drive,
                self._tracer_phase,
                self._tracer_target_phase,
                max(0.0, self._tracer_target_phase - self._tracer_phase),
                self._rotation_drive,
                rotation_target,
                rotation_velocity,
                self._rotation_phase,
                intake_energy,
                self._incoming_gate_open,
                self._incoming_density,
                acoustic_impact,
                self._last_intake_motion_intensity,
                len(particle_cohorts),
                sum(1 for cohort in particle_cohorts if not cohort.outtake),
                sum(1 for cohort in particle_cohorts if cohort.outtake),
                min((cohort.progress for cohort in particle_cohorts), default=1.0),
                max((cohort.progress for cohort in particle_cohorts), default=1.0),
                min((cohort.velocity_accent for cohort in particle_cohorts), default=0.0),
                max((cohort.velocity_accent for cohort in particle_cohorts), default=0.0),
                self._incoming_drive,
                self._incoming_section,
                self._incoming_previous_section,
                self._incoming_blend,
                max(self._section_targets, default=0.0),
                max(section_tuple, default=0.0),
                sum(1 for value in section_tuple if value > 0.08),
                self._packets_since_diag,
                self._packet_sources_since_diag["vocal"],
                self._packet_sources_since_diag["spectral"],
                self._packet_sources_since_diag["kick"],
                self._packet_sources_since_diag["snare"],
                self._packet_sources_since_diag["onset"],
            )
            self._last_diag_ts = now
            self._packets_since_diag = 0
            for key in self._packet_sources_since_diag:
                self._packet_sources_since_diag[key] = 0

        return resolved


def resolved_differs(
    previous: SphereResolvedFrame,
    time_value: float,
    size_pulse: float,
    rotation_drive: float,
    rotation_phase: float,
    tracer_drive: float,
    tracer_phase: float,
    section_drives: tuple[float, ...],
    incoming_drive: float,
    incoming_density: float,
    incoming_section: int,
    incoming_previous_section: int,
    incoming_blend: float,
    particle_cohorts: tuple[SphereParticleCohort, ...],
    parameters: FrozenFields,
    energy: VisualizerEnergyState,
    transient: VisualizerTransientState,
) -> bool:
    return (
        previous.authored_time != time_value
        or previous.size_pulse != size_pulse
        or previous.rotation_drive != rotation_drive
        or previous.rotation_phase != rotation_phase
        or previous.tracer_drive != tracer_drive
        or previous.tracer_phase != tracer_phase
        or previous.section_drives != section_drives
        or previous.incoming_drive != incoming_drive
        or previous.incoming_density != incoming_density
        or previous.incoming_section != incoming_section
        or previous.incoming_previous_section != incoming_previous_section
        or previous.incoming_blend != incoming_blend
        or previous.particle_cohorts != particle_cohorts
        or previous.parameters != parameters
        or previous.energy != energy
        or previous.transient != transient
    )


__all__ = [
    "SECTION_COUNT",
    "SphereFrameRuntime",
    "SphereResolvedFrame",
]

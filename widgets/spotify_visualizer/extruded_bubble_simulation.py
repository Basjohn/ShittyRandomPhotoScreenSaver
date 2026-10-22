"""Extruded Bubble's own logical simulation: the large and mid bubbles of a framed 3D volume.

A real mode of its own (original Bubble is only a guideline for gradients, drift, breathing motion and visual
smoothing). Advanced once per logical capture with dt from the sole Visualizer clock and the existing audio feeds; it
adds no clock, DSP or floor and never touches Qt or GL. Deterministic: the same inputs give the same frames.

**World.** Positions and radii are physical world units in the fixed water domain.
The camera never participates in spawning, movement, contacts or instance placement.

**What it owns.** What music and collisions move: up to ``MAX_BUBBLES`` large and mid bubbles, each with an identity, position, velocity, base radius, a breathing response, a fade, and fuse-cluster membership. Bead chains,
fizz and particulate are procedural on the GPU from the snapshot's scalars (stream, speed, level, flash).

**Music.** The existing full-dynamic bass/mid/high bands drive separate large and mid envelopes;
the passage-presence scalar is diagnostic only. Clean body changes drive size; discrete events
accent motion/light instead of holding bodies inflated. Authored reaction strengths span contracted rest and musical expansion,
with quick attack and slower release. Sustained Response strengthens held body support and motion
through this same production path. No independent oscillator manufactures size changes.
Drift and stream speed settle slowly to very low resting motion. Particle emission retains its
authored quiet amount; render-only size/glow carry its idle contraction. Sway, surface motion and shimmer use integrated musical phases, never raw time
multiplied by a changing rate. Playback stopping clears the input, then lets the followers release;
idle size converges to a contracted constant rather than continuing periodic breathing.

**Collisions.** Overlapping bubbles admitted by ``collision_scope`` resolve once per contact, chosen by the
Fuse / Pop / Bounce shares from the pair's identities: Fuse joins them into a cluster (at most ``CLUSTER_MAX``
members) that then moves as one; Pop fades the smaller one out softly; Bounce pushes them gently apart.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from core.settings.visualizer_paths import direction_of, world_point
from widgets.spotify_visualizer.extruded_bubble_geometry import (
    WORLD_CENTER, WORLD_HALF, WORLD_MARGIN, WORLD_UNIT, WATER_SURFACE_Y, stream_basis, upstream_source, box_entry, scene_track_length, scene_source_face_weights,
)

MAX_BUBBLES = 192
CLUSTER_MAX = 3
BUBBLE_STRIDE = 8          # x, y, z, radius, alpha, breath, identity, cluster (-1: none)
CLUSTER_STRIDE = 4         # members, then up to three member slots (indices into the bubble records), -1 if unused
_FADE_IN = 0.6             # seconds
_FADE_OUT = 0.9
_POP_SECONDS = 2.4         # extremely gentle opacity retirement, never geometric implosion
_LARGE_RADIUS = (0.075 * WORLD_UNIT, 0.16 * WORLD_UNIT)
_MID_RADIUS = (0.025 * WORLD_UNIT, 0.07 * WORLD_UNIT)
# (musical expansion, quiet contraction). Large keeps the existing .13 nominal
# minimum at the normal .15 quiet strength; smalls need their own readable rest.
# These are response calibrations, not optical/physical constants or 2D mechanics.
_LARGE_REACTION = (4.0, 5.8)
_SMALL_REACTION = (4.0, 1.45)
_MINIMUM_REACTION_RADIUS = .13
_LANE = 0.26 * WORLD_UNIT  # fixed world spacing transverse to the stream
_WAKE_RETIRE_SECONDS = 1.1  # front-to-tail dissolve of a wake whose emitter pops, merges or exits
_WAKE_STRIDE = 8           # x, y, z, reacted radius, stable ident, retirement progress (-1 active), alpha, nominal radius


@dataclass(frozen=True, slots=True)
class ExtrudedBubbleControls:
    """The simulation's inputs from the mode's Settings (ranges are (quiet, loud))."""

    large_count: tuple[float, float] = (6.0, 14.0)
    mid_count: tuple[float, float] = (20.0, 48.0)
    large_size: float = 1.0                # physical-radius multiplier; existing controls preserve 1.0
    small_size: float = 1.0                # independent mid population radius multiplier
    size_variety: float = 0.6               # 0 all alike .. 1 strongly varied (biased small)
    columns: float = 0.0                    # 0..1 share of bubbles that rise in lines along the stream
    bubble_spread: float = 1.0               # source-patch width; independent from Columns and particle width
    emission_geometry: str = "BEAM"           # BEAM authored patch / SCENE all physical upstream faces
    surface_scene: bool = False              # authored Sunlit Surface light mode; only governs real water-plane retirement
    stream_direction: tuple[float, float] = (0.0, 0.0)   # legacy angle for standalone callers
    stream_path: tuple[float, ...] | None = None       # normalized source/end xyz, authoritative when supplied
    stream_speed: tuple[float, float] = (0.05, 0.16)     # authored normalized length/s, converted once to physical world units
    drift: tuple[float, float] = (0.3, 0.8)  # lateral wander 0..1 at quiet, loud
    sway: float = 0.4                       # 0..1 side-to-side swing
    emission: tuple[float, float] = (0.3, 1.0)   # particle emission (specks, dust, trails) 0..1 at quiet, loud
    idle: float = 0.5                       # 0..1 gentle resting motion; never a size oscillator
    breathing: tuple[float, float] = (0.04, 0.18)        # large reaction strength, quiet..loud
    small_pulse: tuple[float, float] = (0.02, 0.10)      # mid reaction strength, quiet..loud
    sustained: float = 0.6                  # 0..1 loud-passage large support and change response; no held-small inflation
    smoothing: float = 0.5                  # 0 snappy .. 1 soft; DISPLAYED radius only, not audio/physics
    collision: tuple[float, float, float] = (0.4, 0.3, 0.3)   # Fuse, Pop, Bounce shares
    collision_scope: str = "all"            # "all", "big", "small" or "off"


@dataclass(frozen=True, slots=True)
class MusicInput:
    dt: float
    playing: bool
    intensity: float = 0.0                  # passage intensity 0..1
    onsets: tuple[tuple[str, float], ...] = ()   # (kind, weight 0..1) taken this step
    body_bands: tuple[float, float, float] = (0.0, 0.0, 0.0)  # existing full-dynamic bass/mid/high feed
    play_ramping: bool = False               # existing BeatEngine AGC warmup, NOT a new clock


@dataclass(frozen=True, slots=True)
class ExtrudedBubbleSnapshot:
    time: float = 0.0
    bubbles: tuple[float, ...] = ()         # BUBBLE_STRIDE floats each
    clusters: tuple[float, ...] = ()        # CLUSTER_STRIDE floats each
    level: float = 0.0
    flash: float = 0.0
    stream: tuple[float, float, float] = (0.0, 1.0, 0.0)
    stream_speed: float = 0.0
    drift: float = 0.0
    emission: float = 0.0
    sustain: float = 0.0
    travel: float = 0.0                     # how far the stream has carried the water (physical world units, ever rising)
    rays: float = 0.0                       # the light rays' driver (0..1, eased below the top: never pinned)
    shimmer: float = 0.0                    # the rays' shimmer phase (ever rising, faster on the hits)
    motion_phase: float = 0.0              # Integrated music-owned phase for surface, veils, rays and ambient effects
    wakes: tuple[float, ...] = ()          # stable live/retiring emitter records; immutable, wake-only, 8 floats each

    @property
    def count(self) -> int:
        return len(self.bubbles) // BUBBLE_STRIDE


@dataclass(slots=True)
class _Bubble:
    ident: int
    large: bool
    x: float
    y: float
    z: float
    radius: float
    phase: float
    current_radius: float = 0.0  # physical target: contacts and collision authority
    visual_radius: float = 0.0   # display-only follower per stable ID
    alpha: float = 0.0
    leaving: bool = False
    popping: float = -1.0       # seconds into its pop, -1 when not popping
    pop_alpha: float = 1.0
    cluster: int = -1
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)   # from its cluster's centre


@dataclass(slots=True)
class _Cluster:
    ident: int
    x: float
    y: float
    z: float
    members: list[int] = field(default_factory=list)
    # Connected tree: stable member IDs, admitted world direction and distance / summed radii.
    edges: list[tuple[int, int, tuple[float, float, float], float]] = field(default_factory=list)


def stream_vector(around: float, height: float) -> tuple[float, float, float]:
    """Fixed world direction: around 0 is +Y, height tips toward world -Z."""
    a, h = math.radians(around), math.radians(height)
    return math.sin(a) * math.cos(h), math.cos(a) * math.cos(h), -math.sin(h)


def _lerp(pair: tuple[float, float], t: float) -> float:
    return pair[0] + (pair[1] - pair[0]) * t


def _soft_top(value: float, top: float = 1.0, knee: float = 0.8) -> float:
    """``value`` unchanged below ``knee`` x ``top``, then easing toward ``top`` without ever flattening on it."""
    start = knee * top
    if value <= start:
        return value
    room = top - start
    return start + room * (1.0 - math.exp(-(value - start) / room))


def _follow(current: float, target: float, dt: float, attack: float, release: float) -> float:
    tau = attack if target > current else release
    return target + (current - target) * math.exp(-dt / max(tau, 1e-4))


def _reaction_scale(pair: tuple[float, float], drive: float, expansion: float, contraction: float) -> float:
    """Authored strength spans contracted rest and musical expansion; zero disables both.

    Base radius is nominal size, not an uncontractable lower bound. A silent/held
    input converges to one size; no clock or independent oscillator creates pulses.
    """
    # Silence belongs to the quiet handle. A high-handle edit must not secretly
    # contract the resting population. The shared minimum bounds contraction;
    # strengths above it still affect intermediate musical expansion.
    strength = max(0.0, min(1.0, pair[0]))
    rest = max(_MINIMUM_REACTION_RADIUS, 1.0 - contraction * strength)
    # Keep the response shape separate from the resting radius: simply lifting
    # rest makes a larger share of the remaining motion quadratic, accelerating
    # the perceived release despite unchanged followers. Normalize the existing
    # .13-reference curve, then span the independently authored rest and crest.
    reference_rest_span = 1.0 - _MINIMUM_REACTION_RADIUS
    reference_span = reference_rest_span + expansion * pair[1]
    response = (reference_rest_span * drive + expansion * _lerp(pair, drive) * drive) / reference_span
    return rest + (1.0 - rest + expansion * pair[1]) * response


def _pair_choice(a: int, b: int) -> float:
    """A stable 0..1 number for a pair of identities (the same pair always resolves the same way)."""
    low, high = (a, b) if a < b else (b, a)
    value = (low * 0x9E3779B1 ^ high * 0x85EBCA77) & 0xFFFFFFFF
    value = (value ^ (value >> 15)) * 0x2C1B3C6D & 0xFFFFFFFF
    return ((value ^ (value >> 12)) & 0xFFFFFF) / float(0x1000000)


class ExtrudedBubbleSimulation:
    """The large and mid bubbles of the framed volume, advanced on the logical clock."""

    def __init__(self, seed: int = 0x5EB0) -> None:
        self._seed = int(seed)
        self.reset()

    def reset(self) -> None:
        self._rng = random.Random(self._seed)
        self._bubbles: list[_Bubble] = []
        self._clusters: dict[int, _Cluster] = {}
        self._contacts: dict[tuple[int, int], str] = {}
        self._next_ident = 1
        self._time = 0.0
        self._level = 0.0
        self._flash = 0.0
        self._sustain = 0.0
        self._travel = 0.0
        self._motion_phase = 0.0
        self._motion_rate: float | None = None
        self._body_big_envelope = 0.0
        self._body_small_envelope = 0.0
        self._population_drive = 0.0  # separate audio-owned occupancy eligibility; no display Smoothing
        self._big_body_reference = 0.0
        self._last_big_body: float | None = None
        self._was_play_ramping = False
        self._big_phrase_edge = 0.0
        self._small_body_reference = 0.0
        self._last_small_body: float | None = None
        self._ray_lift = 0.0
        self._ray_body_reference: float | None = None
        self._ray_phrase = 0.0
        self._rays = 0.0
        self._shimmer = 0.0
        self._speed: float | None = None
        self._drift: float | None = None
        self._emission: float | None = None
        self._filled = False
        self._applied_sizes = {True: 1.0, False: 1.0}   # live edits scale SAME-ID radii at the logical owner
        self._spawn_credit = {True: 0.0, False: 0.0}
        self._wake_live: dict[int, tuple[float, float, float, float, int, float, float, float]] = {}
        self._wake_retiring: dict[int, tuple[float, float, float, float, int, float, float, float]] = {}

    @property
    def time(self) -> float:
        return self._time

    # -- population ------------------------------------------------------------------------------------------------

    def _radius(self, large: bool, variety: float) -> float:
        low, high = _LARGE_RADIUS if large else _MID_RADIUS
        mid = (low + high) * 0.5
        # Strong variation with a slight bias to small: a skewed draw widened by the variety.
        draw = self._rng.random() ** 1.6
        return max(low * 0.6, mid + (low + (high - low) * draw - mid) * (0.25 + 0.75 * variety) * 1.4)

    def _spawn(self, large: bool, controls: ExtrudedBubbleControls, direction, *, anywhere: bool) -> None:
        rng = self._rng
        # Columns are localized BEAM authoring; SCENE has whole-face physical
        # distribution rather than assembling lane stripes at the inlet.
        column = (controls.emission_geometry != "SCENE" and controls.columns > 0.0
                  and rng.random() < controls.columns)
        # Admit a prospective PHYSICAL shell, not an arbitrary fixed-size dot.
        # The R42 1.8-world-unit spacing cap was smaller than the sum of two
        # reacted large radii, so apparently well-separated births still clipped
        # and stacked into dense bands on the very next frame.
        radius = self._radius(large, controls.size_variety) * self._applied_sizes[large]
        envelope = self._body_big_envelope if large else self._body_small_envelope
        strength = controls.breathing if large else controls.small_pulse
        prospective = radius * _reaction_scale(strength, envelope, *(_LARGE_REACTION if large else _SMALL_REACTION))
        scene = controls.emission_geometry == "SCENE"
        face_weights = (scene_source_face_weights(controls.stream_path[:3], direction)
                        if scene and controls.stream_path is not None else None)
        # BEAM uses an authored local patch; SCENE samples all real upstream
        # faces, weighted by their physical projected areas. Never spawn
        # against the camera and never clamp a rejected birth to a wall.
        # Resample in the world domain. A crowded inlet MUST defer admission,
        # never force a mid-volume birth or manufacture a hidden backlog.
        for _ in range(32):
            if scene:
                point = upstream_source(rng, direction, face_weights)
                if anywhere:
                    # At activation only: a mature tank, not an instant column
                    # in front of the eye. After startup, births use the same
                    # source-only admission as BEAM.
                    fraction = rng.uniform(0.025, 0.965)
                    distance = scene_track_length(point, direction)
                    point = tuple(p + d * distance * fraction for p, d in zip(point, direction))
            elif controls.stream_path is not None:
                across, deep_axis = stream_basis(direction)
                anchor = world_point(controls.stream_path[:3], WORLD_HALF)
                noise_a = rng.uniform(-0.55, 0.55) * WORLD_UNIT * max(0.0, controls.bubble_spread)
                noise_b = rng.uniform(-0.55, 0.55) * WORLD_UNIT * max(0.0, controls.bubble_spread)
                point = tuple(anchor[i] + across[i] * noise_a + deep_axis[i] * noise_b for i in range(3))
            else:
                point = (tuple(WORLD_CENTER[i] + rng.uniform(-WORLD_HALF[i], WORLD_HALF[i]) for i in range(3))
                         if anywhere else upstream_source(rng, direction))
            if column:
                across, _ = stream_basis(direction)
                distance = sum(p * a for p, a in zip(point, across))
                lane = round(distance / _LANE) * _LANE + rng.gauss(0.0, _LANE * .06)
                point = tuple(p + a * (lane - distance) for p, a in zip(point, across))
            if controls.stream_path is None and not anywhere and not scene:
                point = box_entry(point, direction)
                if point is None:
                    continue
            elif any(abs(p-c) > h + 1e-8 for p, c, h in zip(point, WORLD_CENTER, WORLD_HALF)):
                continue
            if not anywhere:
                point = tuple(p - d * .08 * WORLD_UNIT for p, d in zip(point, direction))
            # Entry spacing is independent of musical count changes and camera.
            # A new bubble cannot materialize already overlapping a recent birth.
            # If every bounded candidate is crowded, defer admission to a later
            # logical capture instead of forcing an intersecting spawn or burst.
            if not anywhere or scene:
                # Never clip newly admitted bubbles through already visible ones.
                # Also keep mature SCENE startup shells from intersecting.
                # Existing BEAM legacy startup distribution is unchanged.
                # Use the physical radius and the displayed shell's current size;
                # downstream Smoothing must not affect the musical admission rate.
                if any(sum((p-q)**2 for p, q in zip(point, (b.x, b.y, b.z))) <
                       (prospective + max(b.current_radius, b.radius * 0.35) + WORLD_UNIT * .08)**2
                       for b in self._bubbles if b.popping < 0 and not b.leaving):
                    continue
            break
        else:
            return False  # crowded inlet: no queued burst and no fake mid-volume birth
        bubble = _Bubble(self._next_ident, large, *point,
                         radius, rng.uniform(0.0, math.tau),
                         current_radius=prospective, visual_radius=prospective,
                         alpha=1.0 if anywhere else 0.0)
        self._next_ident += 1
        self._bubbles.append(bubble)
        return True

    def _outside(self, b: _Bubble, *, surface_scene: bool) -> bool:
        return (any(abs(p - c) > h + WORLD_MARGIN + b.current_radius
                    for p, c, h in zip((b.x, b.y, b.z), WORLD_CENTER, WORLD_HALF))
                or (surface_scene and b.y - b.current_radius > WATER_SURFACE_Y))

    # -- one step ----------------------------------------------------------------------------------------------------

    def advance(self, music: MusicInput, controls: ExtrudedBubbleControls) -> ExtrudedBubbleSnapshot:
        dt = max(0.0, min(0.1, float(music.dt)))
        self._time += dt
        # Musical analysis, activity, flow, emission, and contacts must NEVER use the display smoother.
        # The earlier `soft` multiplier cascaded into already-AGC-processed audio.
        soft = 1.0

        # One band-driven path for live capture and tests. The presence scalar is diagnostic:
        # it can remain at 1 through music and must not manufacture body motion or an idle sine.
        bass, mid, high = (max(0.0, min(1.0, float(v))) if music.playing else 0.0
                           for v in music.body_bands)
        big_body = _soft_top(bass + 0.28 * mid + 0.10 * high)
        vocal_body = 0.70 * mid + 0.35 * high
        small_body = _soft_top(vocal_body)
        intensity = min(1.0, max(bass, vocal_body))  # population/motion retain their existing normalized driver
        self._level = _follow(self._level, intensity, dt, 0.08 * soft, 0.45 * soft)
        onsets = music.onsets if music.playing else ()
        if onsets:
            self._flash = max(self._flash, max(w for _kind, w in onsets))
        self._flash = _follow(self._flash, 0.0, dt, 0.02, 0.6 * soft)

        level = self._level
        self._sustain = _follow(self._sustain, max(0.0, min(1.0, (intensity - 0.35) / 0.5)), dt, 1.2, 2.0)
        sustain = self._sustain * controls.sustained
        # Clean body-delta authority opens each lane on actual phrase changes, not
        # a kick/snare tail that keeps the field inflated between attacks.
        # Activation may join music already playing: its first valid bands are NOT a new onset.
        # Separately, the engine's legitimate quadratic play-ramp arrives as many small rises;
        # treating each of those as a fresh transient makes a giant swell then a yank-down.
        # A genuinely sudden musical step still gets the original fast, full-size response.
        finishing_source_ramp = self._was_play_ramping and not music.play_ramping
        self._was_play_ramping = bool(music.playing and music.play_ramping)
        if music.playing and (self._last_big_body is None or music.play_ramping or finishing_source_ramp):
            self._big_body_reference = big_body
        rising_step = max(0.0, big_body - (self._last_big_body if self._last_big_body is not None else big_body))
        abrupt_step = not (music.play_ramping or finishing_source_ramp) and rising_step > max(0.05, 2.0 * dt)
        self._last_big_body = big_body if music.playing else None
        self._big_body_reference = _follow(self._big_body_reference, big_body, dt,
                                           (0.45 if abrupt_step else 0.10) * soft, 0.25 * soft)
        big_change = max(0.0, big_body - self._big_body_reference)
        if abrupt_step:
            self._big_phrase_edge = max(self._big_phrase_edge, rising_step)
        self._big_phrase_edge = _follow(self._big_phrase_edge, 0.0, dt, 0.01, 0.25 * soft)
        # A genuine step carries a short, continuous musical body response. A smooth engine
        # ramp cannot repeatedly fake that step, and a held plateau does not sustain it.
        if music.play_ramping or finishing_source_ramp:
            self._big_phrase_edge = 0.0
            big_change = 0.0
        else:
            big_change = min(0.11, big_change) + self._big_phrase_edge
        # Silence still settles over seconds. Blend into that release continuously;
        # the previous .01 threshold abruptly changed release by 7.5x inside music.
        quiet = max(0.0, 1.0 - intensity / 0.10)
        body_release = (0.10 + 1.40 * quiet * quiet) * soft
        self._body_big_envelope = _follow(self._body_big_envelope,
            _soft_top((0.22 + 0.70 * sustain) * big_body + 3.0 * big_change), dt, 0.06 * soft, body_release)
        # Small bubbles open on changing vocal/body energy, with restrained held support.
        # A hot mid/high plateau must not inflate the whole small field to hero size.
        # The small lane had the same zero-reference hot-start problem as large,
        # amplified by its 6x clean-change coefficient. During the engine's actual
        # playback warmup, track the source's ramped body without manufacturing
        # repeated vocal onsets; ordinary musical changes keep the original gain.
        if music.playing and (self._last_small_body is None or music.play_ramping or finishing_source_ramp):
            self._small_body_reference = small_body
        self._last_small_body = small_body if music.playing else None
        self._small_body_reference = _follow(self._small_body_reference, small_body, dt, 0.55 * soft, 0.25 * soft)
        small_change = 0.0 if (music.play_ramping or finishing_source_ramp) else max(0.0, small_body - self._small_body_reference)
        self._body_small_envelope = _follow(self._body_small_envelope,
            _soft_top(0.18 * small_body + (6.0 + 2.0 * sustain) * small_change), dt, 0.06 * soft, body_release)
        # Counts describe passage occupancy. Flow/light/emission must still express
        # changing vocals while that occupancy is held high by bass. Reuse the
        # existing clean small-body envelope; no second band read or response clock.
        change_drive = _soft_top(0.60 * level + 0.60 * self._body_small_envelope + 0.15 * self._flash)
        # Resting phases barely advance. Sway and shader animation share this integrated musical time.
        idle_rate = 0.03 + 0.06 * max(0.0, min(1.0, controls.idle))
        # Operator-requested +10% RESTING activity for moving actors, NOT for
        # water/surface time or the musical bands. Keep the shared motion_phase
        # untouched: the ocean surface consumes it and must remain unchanged.
        rest_motion_boost = 1.0 + 0.10 * quiet
        motion_target = idle_rate + 1.10 * level + 1.10 * self._body_small_envelope + 0.22 * self._flash + 0.20 * sustain
        if self._motion_rate is None:
            self._motion_rate = motion_target
        self._motion_rate = _follow(self._motion_rate, motion_target, dt, 0.24 * soft, 1.1 * soft)
        self._motion_phase += dt * self._motion_rate
        # The ray brightness has its OWN phrase follower: the held musical presence
        # opens the fan but cannot consume the whole authored brightening range.
        # A rising bass/mid/high body, including changes WITHIN playback, adds a
        # short lift; falls decay gently. This does not touch audio AGC, the
        # size/body envelopes, or the operator's Ray Strength endpoints.
        ray_body = 0.34 * bass + 0.46 * mid + 0.20 * high
        if self._ray_body_reference is None or music.play_ramping:
            self._ray_body_reference = ray_body
        self._ray_body_reference = _follow(self._ray_body_reference, ray_body, dt, 0.42, 0.70)
        positive_phrase = max(0.0, ray_body - self._ray_body_reference)
        if music.play_ramping:
            positive_phrase = 0.0
        self._ray_phrase = _follow(self._ray_phrase, min(1.0, positive_phrase * 2.3), dt,
                                    0.07, 0.62)
        # Discrete musical event lifts have their own short life; following the
        # already-smoothed flash twice blended successive beats into a bright
        # plateau. Admit the real onset weight once, then decay continuously.
        if onsets and not music.play_ramping:
            self._ray_lift = max(self._ray_lift, min(1.0, max(w for _kind, w in onsets)))
        self._ray_lift = _follow(self._ray_lift, 0.0, dt, 0.08, 0.42)
        ray_target = (0.24 * level + 0.26 * self._body_small_envelope
                      + 0.06 * sustain + 0.23 * self._ray_phrase + 0.32 * self._ray_lift)
        ray_release = 0.58 + 0.25 * quiet * quiet
        self._rays = _follow(self._rays, min(0.90, ray_target), dt, 0.12,
                             ray_release + min(0.15, 0.20 * ray_release))
        # Integrated phase keeps the shimmer pattern continuous. The transient
        # brightening above is separate from this cosmetic shimmer; no flashing.
        self._shimmer += dt * (idle_rate * rest_motion_boost + 0.6 * change_drive + 1.4 * self._ray_lift)
        direction = (direction_of(controls.stream_path, WORLD_HALF) if controls.stream_path is not None
                     else stream_vector(*controls.stream_direction))
        # Drift, stream speed and emission: quick attack, slow decay (the stream slowest), onsets only through them.
        low_speed, high_speed = controls.stream_speed
        activity = min(1.0, idle_rate * rest_motion_boost + 1.6 * level)
        speed_target = (_lerp(controls.stream_speed, change_drive) + (high_speed - low_speed) * (0.35 * self._flash + 0.15 * sustain)) * activity
        drift_target = _soft_top(_lerp(controls.drift, change_drive) + 0.2 * sustain * (controls.drift[1] - controls.drift[0])) * activity
        emission_target = _soft_top(_lerp(controls.emission, change_drive)
                                    + 0.2 * (controls.emission[1] - controls.emission[0]) * self._flash)
        if self._speed is None:
            self._speed, self._drift, self._emission = speed_target, drift_target, emission_target
        # Flow accelerates continuously, rather than stepping at a vocal accent;
        # release into silence retains the long resting transition.
        self._speed = _follow(self._speed, speed_target, dt, 0.68 * soft, (0.65 + 2.35 * quiet * quiet) * soft)
        self._drift = _follow(self._drift, drift_target, dt, 0.20 * soft, (0.35 + 2.15 * quiet * quiet) * soft)
        emission_release = (0.25 + 1.25 * quiet * quiet) * soft
        self._emission = _follow(self._emission, emission_target, dt, 0.08 * soft,
                                 emission_release + min(0.15, 0.20 * emission_release))
        speed = self._speed * WORLD_UNIT
        # The procedural layers (bead chains, snow) move by this distance, never by time x a changing speed, so a
        # change of speed never makes them jump.
        self._travel += speed * dt

        # Nominal sizes belong to the physical simulation. Changing Settings acts on existing stable IDs,
        # and is reflected in contacts, wakes, and rendering; no camera-dependent scaling or respawn.
        for large, requested in ((True, controls.large_size), (False, controls.small_size)):
            target_size = max(0.5, min(2.0, requested))
            previous = self._applied_sizes[large]
            if target_size != previous:
                ratio = target_size / previous
                for bubble in self._bubbles:
                    if bubble.large is large:
                        bubble.radius *= ratio
                self._applied_sizes[large] = target_size

        # Population is a distinct, slowly settling music consumer. The earlier max-band
        # `level` jumped to its ceiling on a single normalized bass/vocal band and
        # handed BOTH populations their authored loud-end counts almost continuously.
        # Broad-body eligibility must be strong to reach that endpoint; unlike a binary
        # gate, the monotonic curve remains responsive throughout the range. The
        # follower shares this logical tick and is deliberately independent of the
        # display-radius Smoothing setting.
        breadth = 0.52 * intensity + 0.48 * (0.42 * bass + 0.39 * mid + 0.19 * high)
        population_target = max(0.0, min(1.0, breadth)) ** 1.8
        self._population_drive = (population_target if not self._filled else
                                  _follow(self._population_drive, population_target, dt, 0.28, 1.05))
        # Preserve authored quiet/loud endpoints, operator's identity/fade semantics,
        # and the existing bounded entry/retirement path. No burst from audio peaks.
        targets = {True: int(round(min(MAX_BUBBLES, _lerp(controls.large_count, self._population_drive)))),
                   False: int(round(min(MAX_BUBBLES, _lerp(controls.mid_count, self._population_drive))))}
        if targets[True] + targets[False] > MAX_BUBBLES:
            targets[False] = MAX_BUBBLES - targets[True]
        live = {True: [b for b in self._bubbles if b.large and not b.leaving and b.popping < 0],
                False: [b for b in self._bubbles if not b.large and not b.leaving and b.popping < 0]}
        present_large = sum(b.large for b in self._bubbles)
        present = {True: present_large, False: len(self._bubbles) - present_large}
        limits = {True: min(MAX_BUBBLES, round(max(controls.large_count))),
                  False: min(MAX_BUBBLES, round(max(controls.mid_count)))}
        for large in (True, False):
            if not self._filled:
                # A physical Source node does not imply a mature population has
                # magically appeared halfway through its journey on startup.
                # Admit it using the same bounded inflow as later music changes.
                if controls.stream_path is None or controls.emission_geometry == "SCENE":
                    for _ in range(targets[large]):
                        # Finite attempts; never weaken spacing just to reach
                        # authored occupancy or allocate beyond MAX_BUBBLES.
                        self._spawn(large, controls, direction, anywhere=True)
                continue
            shortage = targets[large] - len(live[large])
            if shortage > 0 and present[large] < limits[large]:
                # Population handles are an OCCUPANCY ceiling, not permission to
                # generate an entire deficit in a few frames. The old threshold
                # 1/target made the inlet deliver O(target) bubbles per second,
                # causing musical and startup bands even with large Spread.
                # Admit by actual stream throughput (distance/s) over authored
                # path length, with a small resting inlet. No new timer/clock.
                if controls.emission_geometry == "SCENE":
                    # One finite physical tank. Distributed births admit at
                    # the faces, never through a screen-space viewport.
                    passage = max(WORLD_UNIT, 2.0 * max(WORLD_HALF))
                elif controls.stream_path is not None:
                    source = world_point(controls.stream_path[:3], WORLD_HALF)
                    end = world_point(controls.stream_path[3:], WORLD_HALF)
                    passage = max(WORLD_UNIT, math.dist(source, end))
                else:
                    passage = 2.0 * WORLD_HALF[1]
                inlet_per_second = min(12.0, 0.4 + max(0.0, speed) * targets[large] / passage)
                self._spawn_credit[large] = min(1.0, self._spawn_credit[large] + dt * inlet_per_second)
                # At most one birth per logical capture; never accumulate a
                # multi-birth burst while Source is blocked.
                if self._spawn_credit[large] >= 1.0 and len(self._bubbles) < MAX_BUBBLES:
                    self._spawn_credit[large] -= 1.0
                    if self._spawn(large, controls, direction, anywhere=False):
                        present[large] += 1
                    else:
                        self._spawn_credit[large] = 0.0
            elif shortage < 0:
                self._spawn_credit[large] = 0.0
                # Reduced musical occupancy closes the inlet; it must NOT kill
                # already travelling identities midstream. They continue to
                # their physical end/boundary and release there. The next high
                # passage opens the same inlet again, without scene-wide pops.
                # Counts can temporarily exceed the musical target during this
                # physical drain. MAX_BUBBLES/limits still bound total residency.
        self._filled = True

        # Motion: the stream, sized (big bubbles a little faster), with drift and sway across it.
        across, depth_axis = stream_basis(direction)
        big_scale = _reaction_scale(controls.breathing, self._body_big_envelope, *_LARGE_REACTION)
        small_scale = _reaction_scale(controls.small_pulse, self._body_small_envelope, *_SMALL_REACTION)
        # Per-identity visual radius is display-only: no oscillators, no threshold hold/deadband,
        # no smoothing of music or of the instantaneous physical collision radius.
        visual_smoothing = max(0.0, min(1.0, float(controls.smoothing)))
        attack = 0.010 + 0.085 * visual_smoothing
        release = 0.012 + 0.165 * visual_smoothing
        for b in self._bubbles:
            b.current_radius = b.radius * (big_scale if b.large else small_scale)
            if b.visual_radius <= 0.0:
                b.visual_radius = b.current_radius
            else:
                b.visual_radius = _follow(b.visual_radius, b.current_radius, dt, attack, release)
        t = self._motion_phase
        for b in self._bubbles:
            if b.cluster >= 0:
                continue
            size = (b.radius - _MID_RADIUS[0]) / (_LARGE_RADIUS[1] - _MID_RADIUS[0])
            forward = speed * (0.65 + 0.6 * max(0.0, min(1.0, size)))
            wander = self._drift * WORLD_UNIT * 0.05 * (math.sin(t * 0.37 + b.phase) + 0.6 * math.sin(t * 0.83 + 2.1 * b.phase))
            # A slowly changing sine can still be a fast velocity; its amplitude must settle too.
            swing = (controls.sway * WORLD_UNIT * 0.06 * min(1.0, self._motion_rate) * rest_motion_boost
                     * math.sin(t * (1.1 + 0.5 * math.sin(b.phase)) + 3.0 * b.phase))
            deep = self._drift * WORLD_UNIT * 0.015 * math.sin(t * 0.29 + 1.7 * b.phase)
            b.x += dt * (direction[0] * forward + across[0] * (wander + swing) + depth_axis[0] * deep)
            b.y += dt * (direction[1] * forward + across[1] * (wander + swing) + depth_axis[1] * deep)
            b.z += dt * (direction[2] * forward + across[2] * (wander + swing) + depth_axis[2] * deep)
        for c in self._clusters.values():
            members = [self._find(i) for i in c.members]
            members = [m for m in members if m is not None]
            if not members:
                continue
            forward = speed * 0.9
            wander = self._drift * WORLD_UNIT * 0.04 * math.sin(t * 0.31 + c.ident)
            c.x += dt * (direction[0] * forward + across[0] * wander)
            c.y += dt * (direction[1] * forward + across[1] * wander)
            c.z += dt * (direction[2] * forward + across[2] * wander)
            self._place_cluster(c, members)

        self._collide(controls, dt)

        # In Sunlit Surface, let the bubble visibly REACH the ACTUAL water plane
        # before starting its EOL fade. R42 triggered on the upper rim, then
        # spent the entire 0.9 s fade while the centre was still submerged.
        # At low stream speed that looked like an early death far below the sky. In Deep Light, retain the finite authored
        # End plane (including horizontal / descending streams) exactly as before.
        # Neither camera pose nor musical occupancy can trigger retirement.
        if controls.surface_scene and direction[1] > 0.1:
            for b in self._bubbles:
                if b.popping < 0.0 and not b.leaving:
                    if b.y >= WATER_SURFACE_Y:
                        b.leaving = True
        elif controls.emission_geometry == "SCENE":
            # SCENE's exit is the far physical box face for each individual
            # track, not the global End dot acting as a sink. The ordinary
            # world-boundary EOL below already handles this, and retains
            # stable identities through their gentle fade.
            pass
        elif controls.stream_path is not None:
            end = world_point(controls.stream_path[3:], WORLD_HALF)
            for b in self._bubbles:
                if b.popping >= 0.0 or b.leaving:
                    continue
                passed_end = sum((p - stop) * axis for p, stop, axis in
                                 zip((b.x, b.y, b.z), end, direction))
                if passed_end >= 0.0:
                    b.leaving = True

        # Fades, pops and leaving.
        kept: list[_Bubble] = []
        for b in self._bubbles:
            if b.popping >= 0.0:
                b.popping += dt
                t = min(1.0, b.popping / _POP_SECONDS)
                b.alpha = b.pop_alpha * (1.0 - t * t * (3.0 - 2.0 * t))
            elif b.leaving or self._outside(b, surface_scene=controls.surface_scene):
                b.leaving = True
                b.alpha = max(0.0, b.alpha - dt / _FADE_OUT)
            else:
                b.alpha = min(1.0, b.alpha + dt / _FADE_IN)
            if b.alpha > 0.0 or (b.popping < 0.0 and not b.leaving):
                kept.append(b)
            else:
                self._contacts = {pair: response for pair, response in self._contacts.items() if b.ident not in pair}
        self._bubbles = kept
        self._prune_clusters()
        return self._snapshot(direction, speed, controls, dt)

    # -- collisions --------------------------------------------------------------------------------------------------

    def _find(self, ident: int) -> _Bubble | None:
        for b in self._bubbles:
            if b.ident == ident:
                return b
        return None

    def _admitted(self, b: _Bubble, scope: str) -> bool:
        if scope == "off" or b.popping >= 0.0 or b.leaving or b.alpha < 0.6:
            return False
        return scope == "all" or (scope == "big") == b.large

    def _collide(self, controls: ExtrudedBubbleControls, dt: float) -> None:
        scope = controls.collision_scope
        fuse, pop, bounce = controls.collision
        total = fuse + pop + bounce
        if scope == "off" or total <= 0.0:
            self._contacts.clear()
            return
        fuse, pop = fuse / total, pop / total
        # Neighboring cells suffice only when a cell covers the largest contact diameter.
        cell = max(.1, 2.0 * max((b.current_radius for b in self._bubbles), default=0.0))
        grid: dict[tuple[int, int, int], list[_Bubble]] = {}
        for b in self._bubbles:
            if self._admitted(b, scope):
                grid.setdefault((int(math.floor(b.x / cell)), int(math.floor(b.y / cell)),
                                 int(math.floor(b.z / cell))), []).append(b)
        # Freeze discovery before any response moves a member or changes cluster ownership.
        candidates: list[tuple[_Bubble, _Bubble]] = []
        for (cx, cy, cz), bucket in grid.items():
            neighbours = [b for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                          for b in grid.get((cx + dx, cy + dy, cz + dz), ())]
            for a in bucket:
                for b in neighbours:
                    if b.ident <= a.ident:
                        continue
                    candidates.append((a, b))
        touching: set[tuple[int, int]] = set()
        for a, b in candidates:
            if not self._admitted(a, scope) or not self._admitted(b, scope):
                continue
            if a.cluster >= 0 and a.cluster == b.cluster:
                continue
            dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
            reach = a.current_radius + b.current_radius
            pair = (a.ident, b.ident)
            if pair in self._contacts:
                reach *= 1.03  # avoid reselecting an event at a grazing numerical boundary
            if dx * dx + dy * dy + dz * dz >= reach * reach:
                continue
            touching.add(pair)
            if pair not in self._contacts:
                choice = _pair_choice(*pair)
                if choice < fuse:
                    response = "fuse" if self._fuse(a, b) else "bounce"
                elif choice < fuse + pop:
                    loser = a if a.current_radius < b.current_radius else b
                    loser.pop_alpha = loser.alpha
                    loser.popping = 0.0
                    response = "pop"
                else:
                    response = "bounce"
                self._contacts[pair] = response
            if self._contacts[pair] == "bounce":
                self._bounce(a, b, dt)
        # Contacts end when the pair separates (so a later meeting resolves anew).
        self._contacts = {pair: response for pair, response in self._contacts.items()
                          if pair in touching or self._clustered(pair)}

    def _clustered(self, pair: tuple[int, int]) -> bool:
        a, b = self._find(pair[0]), self._find(pair[1])
        return a is not None and b is not None and a.cluster >= 0 and a.cluster == b.cluster

    def _fuse(self, a: _Bubble, b: _Bubble) -> bool:
        members_a = self._clusters[a.cluster].members if a.cluster >= 0 else [a.ident]
        members_b = self._clusters[b.cluster].members if b.cluster >= 0 else [b.ident]
        if len(members_a) + len(members_b) > CLUSTER_MAX:
            return False
        bubbles = [self._find(i) for i in members_a + members_b]
        bubbles = [m for m in bubbles if m is not None]
        weight = sum(m.radius ** 3 for m in bubbles)
        cx, cy, cz = (sum(getattr(m, axis) * m.radius ** 3 for m in bubbles) / weight for axis in ("x", "y", "z"))
        # Preserve the exact admitted layout, including existing edges when adding a third member.
        edges = [edge for ident in {a.cluster, b.cluster} - {-1} for edge in self._clusters[ident].edges]
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        axis = (dx / distance, dy / distance, dz / distance) if distance > 1e-9 else (1.0, 0.0, 0.0)
        edges.append((a.ident, b.ident, axis, distance / (a.current_radius + b.current_radius)))
        for old in {a.cluster, b.cluster} - {-1}:
            self._clusters.pop(old, None)
        ident = min(m.ident for m in bubbles)
        cluster = _Cluster(ident, cx, cy, cz, [m.ident for m in bubbles], edges)
        self._clusters[ident] = cluster
        for m in bubbles:
            m.cluster = ident
            m.offset = (m.x - cx, m.y - cy, m.z - cz)
        return True

    def _place_cluster(self, cluster: _Cluster, members: list[_Bubble]) -> None:
        """Connected offsets follow the existing smoothed radii; preserve nominal mass center."""
        by_id = {m.ident: m for m in members}
        positions = {members[0].ident: (0.0, 0.0, 0.0)}
        for _ in range(CLUSTER_MAX - 1):
            for left, right, axis, ratio in cluster.edges:
                if left not in by_id or right not in by_id:
                    continue
                length = ratio * (by_id[left].current_radius + by_id[right].current_radius)
                if left in positions and right not in positions:
                    positions[right] = tuple(p + a * length for p, a in zip(positions[left], axis))
                elif right in positions and left not in positions:
                    positions[left] = tuple(p - a * length for p, a in zip(positions[right], axis))
        weight = sum(m.radius ** 3 for m in members)
        center = tuple(sum(positions[m.ident][i] * m.radius ** 3 for m in members) / weight for i in range(3))
        for m in members:
            m.offset = tuple(positions[m.ident][i] - center[i] for i in range(3))
            m.x, m.y, m.z = (c + d for c, d in zip((cluster.x, cluster.y, cluster.z), m.offset))

    def _bounce(self, a: _Bubble, b: _Bubble, dt: float) -> None:
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        overlap = (a.current_radius + b.current_radius) - distance
        if overlap <= 0.0:
            return
        # Continue a gentle dt-bounded response after the once-per-contact event choice.
        groups = [([self._find(i) for i in self._clusters[bubble.cluster].members]
                   if bubble.cluster >= 0 else [bubble]) for bubble in (a, b)]
        weights = [sum(m.radius ** 3 for m in group) for group in groups]
        move = min(overlap * (1.0 - math.exp(-dt / .35)), WORLD_UNIT * .2 * dt)
        axis = (dx / distance, dy / distance, dz / distance) if distance > 1e-8 else (1.0, 0.0, 0.0)
        for bubble, group, sign, share in ((a, groups[0], -1.0, weights[1] / sum(weights)),
                                          (b, groups[1], 1.0, weights[0] / sum(weights))):
            delta = tuple(sign * move * share * v for v in axis)
            for m in group:
                m.x += delta[0]; m.y += delta[1]; m.z += delta[2]
            if bubble.cluster >= 0:
                cluster = self._clusters[bubble.cluster]
                cluster.x += delta[0]; cluster.y += delta[1]; cluster.z += delta[2]

    def _prune_clusters(self) -> None:
        live = {b.ident: b for b in self._bubbles}
        for ident in list(self._clusters):
            cluster = self._clusters[ident]
            previous = len(cluster.members)
            cluster.members = [m for m in cluster.members if m in live]
            cluster.edges = [edge for edge in cluster.edges if edge[0] in cluster.members and edge[1] in cluster.members]
            if len(cluster.members) == 2 and not cluster.edges:
                # Losing a tree's middle member may separate the remaining surfaces.
                a, b = (live[i] for i in cluster.members)
                distance = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
                if distance < a.current_radius + b.current_radius:
                    axis = tuple((v - u) / distance for u, v in zip((a.x, a.y, a.z), (b.x, b.y, b.z))) \
                        if distance > 1e-9 else (1., 0., 0.)
                    cluster.edges.append((a.ident, b.ident, axis, distance / (a.current_radius + b.current_radius)))
                else:
                    for m in cluster.members:
                        live[m].cluster = -1
                    del self._clusters[ident]
                    continue
            if len(cluster.members) < 2:
                for m in cluster.members:
                    live[m].cluster = -1
                del self._clusters[ident]
            elif previous != len(cluster.members):
                members = [live[m] for m in cluster.members]
                weight = sum(m.radius ** 3 for m in members)
                cluster.x, cluster.y, cluster.z = (sum(getattr(m, axis) * m.radius ** 3 for m in members) / weight
                                                   for axis in ("x", "y", "z"))

    # -- snapshot ----------------------------------------------------------------------------------------------------

    def _wakes(self, dt: float) -> tuple[float, ...]:
        """Logical emitter identity survives compaction, fusion, pop and surface exit.

        Retiring wakes retain their last *own* physical world source, never rebind to the shell currently occupying
        the old GPU instance slot. The shader wipes each wake from the travel-facing head backwards over its life.
        """
        current: dict[int, tuple[float, float, float, float, int, float, float, float]] = {}
        for b in self._bubbles:
            if b.cluster < 0 and b.popping < 0 and not b.leaving and b.alpha > 0.02:
                current[b.ident] = (b.x, b.y, b.z, b.visual_radius,
                                    b.ident, -1.0, b.alpha, b.radius)
        # Advance existing tombstones on the sole logical tick, never in the renderer.
        retained = {}
        for ident, old in self._wake_retiring.items():
            age = old[5] + dt / _WAKE_RETIRE_SECONDS
            if age < 1.0:
                retained[ident] = (*old[:5], age, old[6], old[7])
        # Begin retirement immediately when pop/fuse/exit takes its source out of the free population.
        for ident, old in self._wake_live.items():
            if ident not in current and ident not in retained:
                retained[ident] = (*old[:5], 0.0, old[6], old[7])
        # The total lifetime history is bounded as well as its GPU upload: intense collisions cannot grow it.
        if len(retained) > MAX_BUBBLES:
            retained = dict(sorted(retained.items(), key=lambda item: item[1][5])[:MAX_BUBBLES])
        self._wake_live, self._wake_retiring = current, retained
        records = list(current.values())[:MAX_BUBBLES]
        records.extend(retained.values())
        return tuple(value for row in records for value in row)

    def _snapshot(self, direction, speed, controls: ExtrudedBubbleControls, dt: float) -> ExtrudedBubbleSnapshot:
        level = self._level
        index = {b.ident: i for i, b in enumerate(self._bubbles)}
        bubbles: list[float] = []
        for b in self._bubbles:
            swell = b.visual_radius / b.radius - 1.0
            bubbles.extend((b.x, b.y, b.z, b.visual_radius, b.alpha, swell, float(b.ident), float(b.cluster)))
        clusters: list[float] = []
        for cluster in self._clusters.values():
            slots = [float(index[m]) for m in cluster.members if m in index][:CLUSTER_MAX]
            clusters.extend((float(len(slots)), *slots, *([-1.0] * (CLUSTER_MAX - len(slots)))))
        return ExtrudedBubbleSnapshot(self._time, tuple(bubbles), tuple(clusters), level,
                                      self._flash, direction, speed, self._drift, self._emission, self._sustain,
                                      self._travel, self._rays, self._shimmer, self._motion_phase,
                                      self._wakes(dt))


__all__ = ["BUBBLE_STRIDE", "CLUSTER_MAX", "CLUSTER_STRIDE", "ExtrudedBubbleControls", "ExtrudedBubbleSimulation",
           "ExtrudedBubbleSnapshot", "MAX_BUBBLES", "MusicInput", "stream_vector"]

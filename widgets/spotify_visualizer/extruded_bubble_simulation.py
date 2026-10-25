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
members) that then moves as one; Pop fades the smaller one out softly; Bounce sends them apart along the
contact normal with a decaying separation velocity. A popping bubble keeps its space until its fade ends, so
neither the survivor nor a third bubble slides through it; no pair is left grinding against another.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from core.settings.visualizer_paths import direction_of, world_point
from itertools import chain

from core.constants.extruded_bubble_world import WAKE_POINTS
from widgets.spotify_visualizer.extruded_bubble_wake import WakeField, trails as wake_trails
from widgets.spotify_visualizer.extruded_bubble_geometry import (
    WORLD_CENTER, WORLD_HALF, WORLD_MARGIN, WORLD_UNIT, WATER_SURFACE_Y, stream_basis,
    upstream_source, box_entry, scene_track_length, scene_source_face_weights, scene_mean_passage,
)

MAX_BUBBLES = 192
CLUSTER_MAX = 3
BUBBLE_STRIDE = 8          # x, y, z, radius, alpha, breath, identity, cluster (-1: none)
CLUSTER_STRIDE = 4         # members, then up to three member slots (indices into the bubble records), -1 if unused
_FADE_IN = 0.6             # seconds
_FADE_OUT = 0.9
_POP_SECONDS = 2.4         # extremely gentle opacity retirement, never geometric implosion
# Contact separation: a bounced (or popped) pair moves apart along its contact normal with a decaying
# separation velocity, and any remaining overlap is corrected within about a tenth of a second.
_SEPARATION_SPEED = (0.15, 0.6)   # x WORLD_UNIT per second, scaled by overlap
_SEPARATION_DECAY = 0.45          # seconds
_OVERLAP_CORRECTION = 0.10        # seconds
# A fused pair draws together from where it touched (separation ratio ~1: two shells pressed surface to surface,
# which read as rubbing) to a visible merge, over about this long.
_FUSE_RATIO = 0.72                 # centre distance / (sum of the members' displayed radii) once merged
_FUSE_SECONDS = 0.35
# Drift Direction, in the stream's own frame (across = sideways, depth = toward/away from the stream's side).
# "wander" is the original per-bubble meander; the others steer the field and keep some meander so it is
# never robotic. Swirls orbit the stream axis and widen slowly, so BEAM births spiral out from the source.
DRIFT_DIRECTIONS = ("wander", "left", "right", "diagonal", "swish_across", "swish_depth", "random",
                    "swirl_cw", "swirl_ccw")
_STEER_SPEED = 0.10        # x WORLD_UNIT per second at full drift (left/right/diagonal)
_RANDOM_SPEED = 0.08
_SWISH_SPEED = 0.14
_SWISH_RATE = 0.55         # radians of motion phase per second of the shared swish carrier
_SWIRL_SPEED = 0.30        # tangential
_SWIRL_WIDEN = 0.06        # outward, so the orbit becomes a widening spiral
_STEERED_WANDER = 0.4      # share of the original meander kept under a steered direction
_LARGE_RADIUS = (0.075 * WORLD_UNIT, 0.16 * WORLD_UNIT)
_MID_RADIUS = (0.025 * WORLD_UNIT, 0.07 * WORLD_UNIT)
# (musical expansion, deepest rest). The quiet handle is a contraction depth: 0 keeps the nominal size at rest,
# 1 rests at the class's deepest size (large at the old .13 minimum; smalls keep a readable shell). Until
# 2026-10-24 it was a slope that saturated at .15 and also fed expansion, so raising it ABOVE .15 made quiet
# bubbles bigger. These are response calibrations, not optical/physical constants or 2D mechanics.
_LARGE_REACTION = (4.0, 0.13)
_SMALL_REACTION = (4.0, 0.35)
# Large held-body knee/span on the fixed-scale EB body feed (beat_engine.get_extruded_bubble_body_bands):
# about p25 and p95 of bass + .28 mid + .10 high pooled over four full songs (2026-10-24). A p10 knee held
# large bubbles open through nearly all music (p95/p05 ~1.8x vs accepted 2D's 2.6-9x); a p40 knee
# collapsed a quieter-captured song. The knee is a fixed real level, never learned from the track.
_LARGE_HELD_KNEE = 0.55
_LARGE_HELD_SPAN = 0.52
_LARGE_HELD_SOFTNESS = 0.08
# Per-identity excursion (amplitude at the class's smallest size, spread to its largest):
# large 1.12 -> 0.88, small 1.18 -> 0.82, around the authored class response.
_PER_ID_LARGE = (1.12, 0.24)
_PER_ID_SMALL = (1.18, 0.36)
_MINIMUM_REACTION_RADIUS = .13
_QUIET_DEPTH_FULL = 0.5   # Breathing / Small Bubble Pulse quiet handle at which the class reaches its deepest rest
_LANE = 0.26 * WORLD_UNIT  # fixed world spacing transverse to the stream
_WAKE_RETIRE_SECONDS = 1.1  # front-to-tail dissolve of a wake whose emitter pops, merges or exits
_NO_WAKE_PATH = (0.0,) * (3 + 3 * WAKE_POINTS)   # trails, length, span, path: a bubble without a trail


@dataclass(frozen=True, slots=True)
class ExtrudedBubbleControls:
    """The simulation's inputs from the mode's Settings (ranges are (quiet, loud))."""

    large_count: tuple[float, float] = (6.0, 14.0)
    mid_count: tuple[float, float] = (20.0, 48.0)
    large_size: float = 1.0                # physical-radius multiplier; existing controls preserve 1.0
    small_size: float = 1.0                # independent mid population radius multiplier
    size_variety: float = 0.6               # 0 all alike .. 1 strongly varied (biased small)
    doublets: float = 0.0                   # chance a birth rises already fused with a smaller companion (or two)
    wake_trails: float = 0.0                # share of bubbles trailing a wake of the water they pass through
    columns: float = 0.0                    # 0..1 share of bubbles that rise in lines along the stream
    bubble_spread: float = 1.0               # source-patch width; independent from Columns and particle width
    emission_geometry: str = "BEAM"           # BEAM authored patch / SCENE all physical upstream faces
    surface_scene: bool = False              # authored Sunlit Surface light mode; only governs real water-plane retirement
    stream_direction: tuple[float, float] = (0.0, 0.0)   # legacy angle for standalone callers
    stream_path: tuple[float, ...] | None = None       # normalized source/end xyz, authoritative when supplied
    stream_speed: tuple[float, float] = (0.05, 0.16)     # authored normalized length/s, converted once to physical world units
    drift: tuple[float, float] = (0.3, 0.8)  # lateral wander 0..1 at quiet, loud
    drift_direction: str = "wander"          # one of DRIFT_DIRECTIONS
    sway: float = 0.4                       # 0..1 side-to-side swing
    emission: tuple[float, float] = (0.3, 1.0)   # particle emission (specks, dust, trails) 0..1 at quiet, loud
    idle: float = 0.5                       # 0..1 gentle resting motion; never a size oscillator
    breathing: tuple[float, float] = (0.0355, 0.18)      # large: quiet contraction depth, loud expansion
    small_pulse: tuple[float, float] = (0.001, 0.10)     # mid: quiet contraction depth, loud expansion
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
    passage: float = 0.0                   # how loud the passage is (0 quiet .. 1 loud): where every Range sits

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
    push: tuple[float, float, float] = (0.0, 0.0, 0.0)     # decaying contact separation velocity


@dataclass(slots=True)
class _Cluster:
    ident: int
    x: float
    y: float
    z: float
    members: list[int] = field(default_factory=list)
    # Connected tree: stable member IDs, admitted world direction and distance / summed radii.
    edges: list[tuple[int, int, tuple[float, float, float], float]] = field(default_factory=list)
    push: tuple[float, float, float] = (0.0, 0.0, 0.0)


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


def _softplus(x: float) -> float:
    return x + math.log1p(math.exp(-x)) if x > 0.0 else math.log1p(math.exp(x))


def _smooth_above(value: float, knee: float, softness: float) -> float:
    """``max(0, value - knee)`` with a softplus corner ``softness`` wide, exactly 0 at value 0."""
    return max(0.0, softness * (_softplus((value - knee) / softness) - _softplus(-knee / softness)))


def _follow(current: float, target: float, dt: float, attack: float, release: float) -> float:
    tau = attack if target > current else release
    return target + (current - target) * math.exp(-dt / max(tau, 1e-4))


def _passage_curve(intensity: float) -> float:
    """The engine's passage intensity (0 near-silence, ~0.65 a usual passage, 1 loud) as where a Range sits: a usual
    passage a little past the middle, the quietest music near the quiet handle, the loudest at the loud one."""
    value = max(0.0, min(1.0, float(intensity)))
    return value * value * (3.0 - 2.0 * value)


def _shown_radius(bubble) -> float:
    """The radius the bubble is drawn with (its smoothed display radius), for laying out fused shapes."""
    return bubble.visual_radius if bubble.visual_radius > 0.0 else bubble.current_radius


def _decayed(vector: tuple[float, float, float], dt: float) -> tuple[float, float, float]:
    if vector == (0.0, 0.0, 0.0):
        return vector
    k = math.exp(-dt / _SEPARATION_DECAY)
    out = tuple(v * k for v in vector)
    return (0.0, 0.0, 0.0) if sum(v * v for v in out) < (1e-4 * WORLD_UNIT) ** 2 else out


def _drift_steer(kind: str, position, phase: float, t: float, direction, across, depth_axis, axis_origin,
                 amount: float) -> tuple[float, float, float]:
    """Extra drift velocity for a Drift Direction; ``amount`` is the musical drift in world units/s."""
    def combine(a: float, b: float) -> tuple[float, float, float]:
        return tuple(amount * (a * u + b * v) for u, v in zip(across, depth_axis))

    if kind == "left":
        return combine(-_STEER_SPEED, 0.0)
    if kind == "right":
        return combine(_STEER_SPEED, 0.0)
    if kind == "diagonal":
        return combine(_STEER_SPEED * math.sqrt(.5), _STEER_SPEED * math.sqrt(.5))
    if kind == "random":  # a fixed heading per bubble, from its stable phase
        return combine(_RANDOM_SPEED * math.cos(phase), _RANDOM_SPEED * math.sin(phase))
    if kind in ("swish_across", "swish_depth"):
        # One shared carrier moves the field together; a small per-bubble lag keeps it organic.
        sway = _SWISH_SPEED * math.sin(t * _SWISH_RATE - 0.35 * math.sin(phase))
        return combine(sway, 0.0) if kind == "swish_across" else combine(0.0, sway)
    if kind in ("swirl_cw", "swirl_ccw"):
        r = tuple(p - o for p, o in zip(position, axis_origin))
        along = sum(a * d for a, d in zip(r, direction))
        radial = tuple(a - along * d for a, d in zip(r, direction))
        distance = math.sqrt(sum(a * a for a in radial))
        if distance < 1e-3 * WORLD_UNIT:  # on the axis: leave along the bubble's own heading
            radial = tuple(math.cos(phase) * u + math.sin(phase) * v for u, v in zip(across, depth_axis))
        else:
            radial = tuple(a / distance for a in radial)
        # Counter-clockwise seen from the stream's end looking back at its source (right-hand rule).
        tangent = (direction[1] * radial[2] - direction[2] * radial[1],
                   direction[2] * radial[0] - direction[0] * radial[2],
                   direction[0] * radial[1] - direction[1] * radial[0])
        sign = 1.0 if kind == "swirl_ccw" else -1.0
        return tuple(amount * (sign * _SWIRL_SPEED * g + _SWIRL_WIDEN * q) for g, q in zip(tangent, radial))
    return (0.0, 0.0, 0.0)


def _reaction_scale(pair: tuple[float, float], drive: float, expansion: float, deepest: float) -> float:
    """Authored strength spans contracted rest and musical expansion; zero disables both.

    Base radius is nominal size, not an uncontractable lower bound. A silent/held
    input converges to one size; no clock or independent oscillator creates pulses.
    """
    # Silence belongs to the quiet handle alone: a contraction depth, monotonic from the nominal size (0) to the
    # class's deepest rest (_QUIET_DEPTH_FULL, half way), eased (square root) so its low part still reads. It never
    # feeds expansion. The deepest rest sits half way, not at the end: the slider's handles cannot cross, so a rest
    # authored at the far end forced the loud handle (the crest) to its maximum with it.
    strength = max(0.0, min(1.0, pair[0] / _QUIET_DEPTH_FULL))
    rest = 1.0 - (1.0 - deepest) * math.sqrt(strength)
    # Keep the response shape separate from the resting radius: simply lifting
    # rest makes a larger share of the remaining motion quadratic, accelerating
    # the perceived release despite unchanged followers. Normalize the existing
    # .13-reference curve, then span the independently authored rest and crest.
    reference_rest_span = 1.0 - _MINIMUM_REACTION_RADIUS
    reference_span = reference_rest_span + expansion * pair[1]
    response = (reference_rest_span * drive + expansion * pair[1] * drive * drive) / reference_span
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
        self._surge = 0.0             # the flow's beat surge: a quick push on each onset, released over half a second
        self._onset_mean = 0.0        # the recent onsets' usual weight, so only accents push the flow
        self._surge_target = 0.0
        self._drift_shown = 0.0       # drift with its surge, as the bubbles move by it
        self._sustain = 0.0
        self._travel = 0.0
        self._motion_phase = 0.0
        self._motion_rate: float | None = None
        self._body_big_envelope = 0.0
        self._body_small_envelope = 0.0
        self._flow_body = 0.0
        self._population_drive = 0.0  # separate audio-owned occupancy eligibility; no display Smoothing
        self._passage = 0.0           # the passage drive every quiet-to-loud Range ramps on (see advance)
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
        self._wake_live: dict[int, tuple[float, ...]] = {}
        self._wake_retiring: dict[int, tuple[float, ...]] = {}
        self._wake_field = WakeField(2 * MAX_BUBBLES)   # trailing bubbles' wakes (live and retiring), by identity
        self._wake_share = 0.0
        self._wake_chosen: dict[int, bool] = {}

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
        # Never draw from the stream when Doublets is 0: the population stays exactly what it was.
        if controls.doublets > 0.0 and rng.random() < controls.doublets:
            self._companions(bubble, prospective)
        return True

    def _companions(self, parent: _Bubble, prospective: float) -> None:
        """A birth that rises already fused: one smaller companion touching it (now and then a second), merged as a
        contact fuse merges them (the goals' doublets and triplets). Physical births at the parent, never placed by
        the camera; a crowded spot simply leaves the parent single."""
        rng = self._rng
        for _ in range(1 if rng.random() < 0.8 else 2):
            if len(self._bubbles) >= MAX_BUBBLES:
                return
            share = rng.uniform(0.3, 0.85)
            current = prospective * share
            gap = (prospective + current) * rng.uniform(0.8, 0.95)
            theta, z = rng.uniform(0.0, math.tau), rng.uniform(-1.0, 1.0)
            ring = math.sqrt(max(0.0, 1.0 - z * z))
            axis = (ring * math.cos(theta), ring * math.sin(theta), z)
            point = tuple(p + a * gap for p, a in zip((parent.x, parent.y, parent.z), axis))
            # Inlet births sit on a face: the companion may lie as far outside as the pair's own span, entering with it.
            if any(abs(p - c) > h + gap + current for p, c, h in zip(point, WORLD_CENTER, WORLD_HALF)):
                continue
            family = set(self._clusters[parent.cluster].members) if parent.cluster >= 0 else {parent.ident}
            if any(sum((p - q) ** 2 for p, q in zip(point, (b.x, b.y, b.z))) <
                   (current + max(b.current_radius, b.radius * 0.35) + WORLD_UNIT * .08) ** 2
                   for b in self._bubbles if b.ident not in family and b.popping < 0 and not b.leaving):
                continue
            companion = _Bubble(self._next_ident, parent.large, *point, parent.radius * share,
                                rng.uniform(0.0, math.tau), current_radius=current, visual_radius=current,
                                alpha=parent.alpha)
            self._next_ident += 1
            self._bubbles.append(companion)
            if not self._fuse(parent, companion):
                self._bubbles.pop()
                return

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
        body_sum = bass + 0.28 * mid + 0.10 * high
        big_body = _soft_top(body_sum)
        vocal_body = 0.70 * mid + 0.35 * high
        small_body = _soft_top(vocal_body)
        intensity = min(1.0, max(bass, vocal_body))  # population/motion retain their existing normalized driver
        self._level = _follow(self._level, intensity, dt, 0.08 * soft, 0.45 * soft)
        # Where every quiet-to-loud Range sits: how loud the PASSAGE is (the shared PassageIntensity on the fixed
        # real-music scale, already eased by the engine), eased once more so a phrase, not a beat, moves the
        # endpoints. The band-driven drives above follow beats on a fixed scale that sits mid-range in nearly all
        # music, so ranges never reached their quiet or loud ends (audit 2026-10-24); beats still add motion on top.
        passage_target = _passage_curve(music.intensity) if music.playing else 0.0
        # Activation can join music already playing: the first fill starts at the passage heard, not at silence.
        self._passage = (passage_target if not self._filled else
                         _follow(self._passage, passage_target, dt, 0.6 * soft, 1.5 * soft))
        passage = self._passage
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
        if music.play_ramping or finishing_source_ramp:
            self._big_phrase_edge = 0.0
            big_change = 0.0
        else:
            # An edge can support the current positive body change, never
            # survive it: the old independent tail stayed hot through actual
            # falling bass/body and stacked consecutive rises into inflation.
            big_change = min(0.11, big_change) + min(self._big_phrase_edge, big_change)
        # Silence still settles over seconds. Blend into that release continuously;
        # the previous .01 threshold abruptly changed release by 7.5x inside music.
        quiet = max(0.0, 1.0 - intensity / 0.10)
        body_release = (0.10 + 1.40 * quiet * quiet) * soft
        # Large bodies carry the phrase, not the beat: release over ~0.3 s inside
        # music like accepted 2D's large decay (2.85-3.85/s), so kick-rate body
        # changes no longer wobble them near the top. Small keeps body_release.
        large_release = (0.30 + 1.20 * quiet * quiet) * soft
        # Held body spans the passage, as accepted 2D's sustained knee does: softer
        # phrases (body below the knee) contract and full ones expand. The knee is
        # smooth (softplus), so steady quiet music still sits just above silence
        # without lifting louder levels. It reads the unsquashed body sum;
        # big_body's soft top compresses its upper half.
        held_body = _soft_top(_smooth_above(body_sum, _LARGE_HELD_KNEE, _LARGE_HELD_SOFTNESS) / _LARGE_HELD_SPAN)
        # Phrase changes swell in proportion to how full the passage is: in a soft
        # passage a kick no longer refills the envelope (that pump kept p05 near
        # mid-size), while full passages crest further.
        change_authority = 0.15 + 0.85 * held_body
        self._body_big_envelope = _follow(self._body_big_envelope,
            _soft_top((0.45 + 0.55 * sustain) * held_body + 3.0 * big_change * change_authority),
            dt, 0.12 * soft, large_release)
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
        # The passage scales the small swell (x0.7 quiet .. x1.3 loud): vocal CHANGE thins out in a loud, held
        # passage, so without it soft songs breathed less as they got louder (audit 2026-10-25). Never a held
        # passage term: a hot vocal plateau must not inflate the whole small field.
        self._body_small_envelope = _follow(self._body_small_envelope,
            _soft_top((0.18 * small_body + (6.0 + 2.0 * sustain) * small_change) * (0.7 + 0.6 * passage)),
            dt, 0.06 * soft, body_release)
        # Counts describe passage occupancy. Flow/light/emission must still express
        # changing vocals while that occupancy is held high by bass. Reuse the
        # existing clean small-body envelope; no second band read or response clock.
        # The passage part is the large lane's held body (same fixed-scale knee), eased
        # so flow follows passages, not beats. Level instead sat ~0.7 in ordinary music
        # on the fixed scale and held speed/drift at their loud ends (p05..p95 0.13..0.21
        # of a 0.06..0.20 range on four songs).
        self._flow_body = _follow(self._flow_body, held_body, dt, 0.35 * soft, 1.0 * soft)
        change_drive = _soft_top(0.70 * self._flow_body + 0.30 * self._body_small_envelope + 0.15 * self._flash)
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
        # The passage sets where the fan sits in its Range; beats swing it around that (x0.6 .. x1.3), never
        # lift a quiet passage off its quiet handle (additive beat terms held every passage mid-range). The swing
        # stays wide enough to move a saturated passage under its soft top.
        ray_beats = min(1.0, 0.35 * self._body_small_envelope + 0.6 * self._ray_phrase + 0.6 * self._ray_lift
                        + 0.1 * sustain)
        ray_target = _soft_top(passage * (0.6 + 0.7 * ray_beats))
        ray_release = 0.58 + 0.25 * quiet * quiet
        self._rays = _follow(self._rays, ray_target, dt, 0.12,
                             ray_release + min(0.15, 0.20 * ray_release))
        # Integrated phase keeps the shimmer pattern continuous. The transient
        # brightening above is separate from this cosmetic shimmer; no flashing.
        self._shimmer += dt * (idle_rate * rest_motion_boost + 0.6 * change_drive + 1.4 * self._ray_lift)
        direction = (direction_of(controls.stream_path, WORLD_HALF) if controls.stream_path is not None
                     else stream_vector(*controls.stream_direction))
        # Drift, stream speed and emission: quick attack, slow decay (the stream slowest), onsets only through them.
        low_speed, high_speed = controls.stream_speed
        # A resting floor (scaled by Idle) keeps the stream, drift and the particles it carries slowly moving in
        # silence, as 2D Bubble rests at its authored baseline speed; the resting factor alone (idle_rate, ~0.06)
        # froze them. A floor, never an addition: quiet music is never slower than silence, and ordinary music
        # (already above it) keeps its full quiet-to-loud contrast.
        rest_activity = (0.15 + 0.45 * max(0.0, min(1.0, controls.idle))) * rest_motion_boost
        activity = min(1.0, max(idle_rate * rest_motion_boost + 1.6 * level, rest_activity))
        # Onset and sustained lifts stay inside the authored range: the loud handle is the maximum.
        # The passage sets where flow sits in each Range; phrase changes and onsets swing it around that.
        flow_drive = passage * (0.55 + 0.5 * change_drive)    # headroom under the loud handle for the beat surge
        speed_target = _lerp(controls.stream_speed,
                             _soft_top(flow_drive * (1.0 + 0.20 * self._flash + 0.10 * sustain))) * activity
        drift_target = _lerp(controls.drift, _soft_top(flow_drive * (1.0 + 0.15 * sustain))) * activity
        # Particles have no beat surge: they keep the full passage share.
        emission_target = _soft_top(_lerp(controls.emission, passage * (0.7 + 0.6 * change_drive))
                                    + 0.2 * (controls.emission[1] - controls.emission[0]) * self._flash * passage)
        if self._speed is None:
            self._speed, self._drift, self._emission = speed_target, drift_target, emission_target
        # Flow accelerates continuously, rather than stepping at a vocal accent;
        # release into silence retains the long resting transition.
        self._speed = _follow(self._speed, speed_target, dt, 0.68 * soft, (0.65 + 2.35 * quiet * quiet) * soft)
        self._drift = _follow(self._drift, drift_target, dt, 0.20 * soft, (0.35 + 2.15 * quiet * quiet) * soft)
        emission_release = (0.25 + 1.25 * quiet * quiet) * soft
        self._emission = _follow(self._emission, emission_target, dt, 0.08 * soft,
                                 emission_release + min(0.15, 0.20 * emission_release))
        # The beat surge: each onset pushes the flow toward its loud handle (never past it) and lets go over about
        # half a second, so the stream visibly answers the beat. The followers above carry the passage only; they
        # smooth beats away (speed and drift moved 2-4% with the beats on recorded music, audit 2026-10-25).
        # Only onsets that stand out from the recent ones push (music sends ~10 a second: every one pushing held the
        # surge as a constant offset, not pulses).
        if onsets and not music.play_ramping:
            weight = min(1.0, max(w for _kind, w in onsets))
            accent = 1.6 * max(0.0, weight - 1.15 * self._onset_mean) / max(0.25, 1.0 - self._onset_mean)
            self._onset_mean = _follow(self._onset_mean, weight, dt, 1.5, 1.5)
            self._surge_target = max(self._surge_target, min(1.0, accent))
        self._surge_target = _follow(self._surge_target, 0.0, dt, 0.02, 0.32)
        # Eased in over about a tenth of a second: a push, never a step in velocity.
        self._surge = _follow(self._surge, self._surge_target, dt, 0.1, 0.05)
        push = self._surge * (0.25 + 0.75 * passage)
        speed_live = self._speed + max(0.0, high_speed * activity - self._speed) * push
        drift_live = self._drift + max(0.0, controls.drift[1] * activity - self._drift) * push
        self._drift_shown = drift_live
        speed = speed_live * WORLD_UNIT
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
        breadth = passage * (0.8 + 0.4 * (0.42 * bass + 0.39 * mid + 0.19 * high))
        population_target = max(0.0, min(1.0, breadth))
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
                        # Fused companions count toward the occupancy they join.
                        if sum(1 for b in self._bubbles if b.large == large) >= targets[large]:
                            break
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
                    faces = (scene_source_face_weights(controls.stream_path[:3], direction)
                             if controls.stream_path is not None else None)
                    passage = max(WORLD_UNIT, scene_mean_passage(direction, faces))
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
        # Authored rest (drive 0): per-identity variation never moves it.
        big_rest = _reaction_scale(controls.breathing, 0.0, *_LARGE_REACTION)
        small_rest = _reaction_scale(controls.small_pulse, 0.0, *_SMALL_REACTION)
        # Authored loud handle = the class's maximum expansion; per-identity excursion
        # eases toward it and never passes it.
        big_top = _reaction_scale(controls.breathing, 1.0, *_LARGE_REACTION)
        small_top = _reaction_scale(controls.small_pulse, 1.0, *_SMALL_REACTION)
        # Per-identity visual radius is display-only: no oscillators, no threshold hold/deadband,
        # no smoothing of music or of the instantaneous physical collision radius.
        visual_smoothing = max(0.0, min(1.0, float(controls.smoothing)))
        attack = 0.010 + 0.085 * visual_smoothing
        release = 0.012 + 0.165 * visual_smoothing
        for b in self._bubbles:
            # Per-identity response, as accepted 2D sizes each bubble's sensitivity and
            # timing by its own size: within its class a smaller bubble swings a little
            # further above the authored rest and settles a little faster, so identities
            # stop breathing in lockstep. The rest itself is shared and unchanged.
            # Deterministic from nominal size; no oscillator or randomness.
            low, high = _LARGE_RADIUS if b.large else _MID_RADIUS
            size_t = max(0.0, min(1.0, (b.radius / self._applied_sizes[b.large] - low) / (high - low)))
            amplitude, spread = _PER_ID_LARGE if b.large else _PER_ID_SMALL
            class_scale, rest, top = (big_scale, big_rest, big_top) if b.large else (small_scale, small_rest, small_top)
            scale = rest + (class_scale - rest) * (amplitude - spread * size_t)
            if scale > rest and top > rest:
                scale = rest + _soft_top(scale - rest, top - rest, 0.85)
            b.current_radius = b.radius * scale
            pace = 0.75 + 0.5 * size_t
            if b.visual_radius <= 0.0:
                b.visual_radius = b.current_radius
            else:
                b.visual_radius = _follow(b.visual_radius, b.current_radius, dt, attack * pace, release * pace)
        t = self._motion_phase
        steering = controls.drift_direction if controls.drift_direction in DRIFT_DIRECTIONS else "wander"
        meander = 1.0 if steering == "wander" else _STEERED_WANDER
        axis_origin = (world_point(controls.stream_path[:3], WORLD_HALF)
                       if controls.stream_path is not None and controls.emission_geometry != "SCENE"
                       else WORLD_CENTER)
        for b in self._bubbles:
            if b.cluster >= 0:
                continue
            size = (b.radius - _MID_RADIUS[0]) / (_LARGE_RADIUS[1] - _MID_RADIUS[0])
            forward = speed * (0.65 + 0.6 * max(0.0, min(1.0, size)))
            wander = meander * drift_live * WORLD_UNIT * 0.05 * (
                math.sin(t * 0.37 + b.phase) + 0.6 * math.sin(t * 0.83 + 2.1 * b.phase))
            # A slowly changing sine can still be a fast velocity; its amplitude must settle too.
            swing = (controls.sway * WORLD_UNIT * 0.06 * min(1.0, self._motion_rate) * rest_motion_boost
                     * math.sin(t * (1.1 + 0.5 * math.sin(b.phase)) + 3.0 * b.phase))
            deep = meander * drift_live * WORLD_UNIT * 0.015 * math.sin(t * 0.29 + 1.7 * b.phase)
            steer = _drift_steer(steering, (b.x, b.y, b.z), b.phase, t, direction, across, depth_axis, axis_origin,
                                 drift_live * WORLD_UNIT)
            b.x += dt * (direction[0] * forward + across[0] * (wander + swing) + depth_axis[0] * deep + b.push[0] + steer[0])
            b.y += dt * (direction[1] * forward + across[1] * (wander + swing) + depth_axis[1] * deep + b.push[1] + steer[1])
            b.z += dt * (direction[2] * forward + across[2] * (wander + swing) + depth_axis[2] * deep + b.push[2] + steer[2])
            b.push = _decayed(b.push, dt)
        for c in self._clusters.values():
            members = [self._find(i) for i in c.members]
            members = [m for m in members if m is not None]
            if not members:
                continue
            forward = speed * 0.9
            wander = meander * drift_live * WORLD_UNIT * 0.04 * math.sin(t * 0.31 + c.ident)
            steer = _drift_steer(steering, (c.x, c.y, c.z), 1.3 * c.ident, t, direction, across, depth_axis,
                                 axis_origin, drift_live * WORLD_UNIT)
            c.x += dt * (direction[0] * forward + across[0] * wander + c.push[0] + steer[0])
            c.y += dt * (direction[1] * forward + across[1] * wander + c.push[1] + steer[1])
            c.z += dt * (direction[2] * forward + across[2] * wander + c.push[2] + steer[2])
            c.push = _decayed(c.push, dt)
            merge = 1.0 - math.exp(-dt / _FUSE_SECONDS)
            c.edges = [(left, right, axis, ratio + (min(ratio, _FUSE_RATIO) - ratio) * merge)
                       for left, right, axis, ratio in c.edges]
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

    def _obstacle(self, b: _Bubble, scope: str) -> bool:
        """A popping bubble fades for seconds: it still occupies space (no new event, separation only)."""
        if scope == "off" or b.popping < 0.0 or b.leaving or b.alpha <= 0.05:
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
            if self._admitted(b, scope) or self._obstacle(b, scope):
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
            if a.popping >= 0.0 or b.popping >= 0.0:
                # A fading pop keeps its space until it is gone; the survivor and any third bubble
                # are separated from it instead of sliding through it.
                if self._obstacle(a, scope) or self._obstacle(b, scope):
                    if all(self._admitted(m, scope) or self._obstacle(m, scope) for m in (a, b)) \
                            and not (a.cluster >= 0 and a.cluster == b.cluster) and self._bounce(a, b, dt):
                        touching.add((a.ident, b.ident))
                continue
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
            if self._contacts[pair] in ("bounce", "pop"):
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
        edges.append((a.ident, b.ident, axis, distance / (_shown_radius(a) + _shown_radius(b))))
        # The joined body keeps its members' mass-weighted separation velocity.
        pushes = [self._clusters[m.cluster].push if m.cluster >= 0 else m.push for m in bubbles]
        push = tuple(sum(v[i] * m.radius ** 3 for v, m in zip(pushes, bubbles)) / weight for i in range(3))
        for old in {a.cluster, b.cluster} - {-1}:
            self._clusters.pop(old, None)
        ident = min(m.ident for m in bubbles)
        cluster = _Cluster(ident, cx, cy, cz, [m.ident for m in bubbles], edges, push)
        self._clusters[ident] = cluster
        for m in bubbles:
            m.cluster = ident
            m.offset = (m.x - cx, m.y - cy, m.z - cz)
            m.push = (0.0, 0.0, 0.0)
        return True

    def _place_cluster(self, cluster: _Cluster, members: list[_Bubble]) -> None:
        """Connected offsets follow the members' displayed (smoothed) radii; preserve nominal mass center.

        The layout is the shape you see: the instantaneous physical radius jumps with every beat, and laying members
        out from it shoved two smoothly drawn shells back and forth along their contact ~15 times a second."""
        by_id = {m.ident: m for m in members}
        positions = {members[0].ident: (0.0, 0.0, 0.0)}
        for _ in range(CLUSTER_MAX - 1):
            for left, right, axis, ratio in cluster.edges:
                if left not in by_id or right not in by_id:
                    continue
                length = ratio * (_shown_radius(by_id[left]) + _shown_radius(by_id[right]))
                if left in positions and right not in positions:
                    positions[right] = tuple(p + a * length for p, a in zip(positions[left], axis))
                elif right in positions and left not in positions:
                    positions[left] = tuple(p - a * length for p, a in zip(positions[right], axis))
        weight = sum(m.radius ** 3 for m in members)
        center = tuple(sum(positions[m.ident][i] * m.radius ** 3 for m in members) / weight for i in range(3))
        for m in members:
            m.offset = tuple(positions[m.ident][i] - center[i] for i in range(3))
            m.x, m.y, m.z = (c + d for c, d in zip((cluster.x, cluster.y, cluster.z), m.offset))

    def _bounce(self, a: _Bubble, b: _Bubble, dt: float) -> bool:
        """Drive an overlapping pair apart; False once they no longer overlap.

        Motion is kinematic (stream, drift, sway), so a bounce needs its own separation velocity:
        the old positional nudge (0.35 s, capped at 0.2 units/s) was slower than the flow and
        breathing that close a gap, and pairs ground against each other instead of bouncing away.
        """
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        overlap = (a.current_radius + b.current_radius) - distance
        if overlap <= 0.0:
            return False
        groups = [([m for m in (self._find(i) for i in self._clusters[bubble.cluster].members) if m is not None]
                   if bubble.cluster >= 0 else [bubble]) for bubble in (a, b)]
        weights = [sum(m.radius ** 3 for m in group) for group in groups]
        move = min(overlap * (1.0 - math.exp(-dt / _OVERLAP_CORRECTION)), WORLD_UNIT * 1.5 * dt)
        axis = (dx / distance, dy / distance, dz / distance) if distance > 1e-8 else (1.0, 0.0, 0.0)
        low, high = _SEPARATION_SPEED
        speed = WORLD_UNIT * max(low, min(high, overlap / (0.3 * WORLD_UNIT)))
        for bubble, group, sign, share in ((a, groups[0], -1.0, weights[1] / sum(weights)),
                                          (b, groups[1], 1.0, weights[0] / sum(weights))):
            delta = tuple(sign * move * share * v for v in axis)
            for m in group:
                m.x += delta[0]; m.y += delta[1]; m.z += delta[2]
            owner = self._clusters[bubble.cluster] if bubble.cluster >= 0 else bubble
            if bubble.cluster >= 0:
                owner.x += delta[0]; owner.y += delta[1]; owner.z += delta[2]
            # Raise (never lower) the outward component of the separation velocity while touching.
            outward = sum(p * sign * v for p, v in zip(owner.push, axis))
            needed = speed * share
            if outward < needed:
                owner.push = tuple(p + sign * (needed - outward) * v for p, v in zip(owner.push, axis))
        return True

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
                    cluster.edges.append((a.ident, b.ident, axis, distance / (_shown_radius(a) + _shown_radius(b))))
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

    def _wakes(self, dt: float, share: float) -> tuple[float, ...]:
        """Logical emitter identity survives compaction, fusion, pop and surface exit.

        Retiring wakes retain their last *own* physical world source, never rebind to the shell currently occupying
        the old GPU instance slot. The shader wipes each wake from the travel-facing head backwards over its life.
        A trailing bubble's path is the water it has passed through (``WakeField``), drifting on after it is gone.
        """
        field = self._wake_field
        field.flow(dt, self._motion_phase)
        if share != self._wake_share:                    # the trailing set is chosen once per Wake Trails value
            self._wake_share, self._wake_chosen = share, {}
        current: dict[int, tuple[float, ...]] = {}
        for b in self._bubbles:
            if b.cluster < 0 and b.popping < 0 and not b.leaving and b.alpha > 0.02:
                head = (b.x, b.y, b.z)
                chosen = self._wake_chosen.get(b.ident)
                if chosen is None:
                    chosen = self._wake_chosen[b.ident] = wake_trails(b.ident, share)
                if chosen and b.ident in field and b.ident in self._wake_retiring:
                    field.remove(b.ident)                # back from a fusion: its old wake stays behind, a new one starts
                if chosen and b.ident not in field:
                    field.add(b.ident, b.radius, head)
                elif not chosen and b.ident in field:
                    field.remove(b.ident)
                if b.ident in field:
                    field.follow(b.ident, head, dt, max(4.0 * b.radius, 0.1 * WORLD_UNIT))
                    current[b.ident] = (b.x, b.y, b.z, b.visual_radius, b.ident, -1.0, b.alpha, b.radius,
                                        1.0, *field.record(b.ident, head))
                else:
                    current[b.ident] = (b.x, b.y, b.z, b.visual_radius, b.ident, -1.0, b.alpha, b.radius,
                                        *_NO_WAKE_PATH)
        # Advance existing tombstones on the sole logical tick, never in the renderer; a retiring wake's water keeps
        # drifting as it dissolves.
        retained = {}
        for ident, old in self._wake_retiring.items():
            age = old[5] + dt / _WAKE_RETIRE_SECONDS
            if age < 1.0:
                retained[ident] = ((*old[:5], age, *old[6:9], *field.record(ident, old[:3])) if ident in field
                                   else (*old[:5], age, *old[6:]))
        # Begin retirement immediately when pop/fuse/exit takes its source out of the free population.
        for ident, old in self._wake_live.items():
            if ident not in current and ident not in retained:
                retained[ident] = (*old[:5], 0.0, *old[6:])
        # The total lifetime history is bounded as well as its GPU upload: intense collisions cannot grow it.
        if len(retained) > MAX_BUBBLES:
            retained = dict(sorted(retained.items(), key=lambda item: item[1][5])[:MAX_BUBBLES])
        self._wake_live, self._wake_retiring = current, retained
        for ident in field.idents():
            if ident not in current and ident not in retained:
                field.remove(ident)
        if len(self._wake_chosen) > 4 * MAX_BUBBLES:
            self._wake_chosen = {ident: self._wake_chosen[ident] for ident in current if ident in self._wake_chosen}
        records = list(current.values())[:MAX_BUBBLES]
        records.extend(retained.values())
        return tuple(chain.from_iterable(records))

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
                                      self._flash, direction, speed, self._drift_shown, self._emission, self._sustain,
                                      self._travel, self._rays, self._shimmer, self._motion_phase,
                                      self._wakes(dt, controls.wake_trails), self._passage)


__all__ = ["BUBBLE_STRIDE", "CLUSTER_MAX", "CLUSTER_STRIDE", "ExtrudedBubbleControls", "ExtrudedBubbleSimulation",
           "ExtrudedBubbleSnapshot", "MAX_BUBBLES", "MusicInput", "stream_vector"]

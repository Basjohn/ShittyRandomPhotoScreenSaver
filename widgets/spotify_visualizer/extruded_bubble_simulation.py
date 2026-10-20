"""Extruded Bubble's own logical simulation: the large and mid bubbles of a framed 3D volume.

A real mode of its own (original Bubble is only a guideline for gradients, drift, breathing motion and visual
smoothing). Advanced once per logical capture with dt from the sole Visualizer clock and the existing audio feeds; it
adds no clock, DSP or floor and never touches Qt or GL. Deterministic: the same inputs give the same frames.

**Volume.** x and y span -1..1 (screen right and up), z spans 0..1 (near to far). The renderer maps it into the
framed camera's view.

**What it owns.** What music and collisions move: up to ``MAX_BUBBLES`` large and mid bubbles, each with an identity, position, velocity, base radius, a breathing response, a fade, and fuse-cluster membership. Bead chains,
fizz and particulate are procedural on the GPU from the snapshot's scalars (stream, speed, level, flash).

**Music.** The existing full-dynamic bass/mid/high bands drive separate large and mid envelopes;
the passage-presence scalar is diagnostic only. Weighted kick/snare events add accents with headroom
above the body response. Authored reaction strengths span contracted rest and musical expansion,
with quick attack and slower release. Sustained Response strengthens held body support and motion
through this same production path. No independent oscillator manufactures size changes.
Drift, stream speed and emission resolve their authored ranges once and settle slowly to a very low
resting activity. Sway, surface motion and shimmer use integrated musical phases, never raw time
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

MAX_BUBBLES = 192
CLUSTER_MAX = 3
BUBBLE_STRIDE = 8          # x, y, z, radius, alpha, breath, identity, cluster (-1: none)
CLUSTER_STRIDE = 4         # members, then up to three member slots (indices into the bubble records), -1 if unused
_FADE_IN = 0.6             # seconds
_FADE_OUT = 0.9
_POP_SECONDS = 0.35
_LARGE_RADIUS = (0.075, 0.16)
_MID_RADIUS = (0.025, 0.07)
_MARGIN = 0.25             # how far outside the volume a bubble may be before it is gone
_LANE = 0.26               # spacing of the columns across the stream (shares of the half view)
_WAKE_RETIRE_SECONDS = 1.1  # front-to-tail dissolve of a wake whose emitter pops, merges or exits
_WAKE_STRIDE = 8           # x, y, z, reacted radius, stable ident, retirement progress (-1 active), alpha, nominal radius


@dataclass(frozen=True, slots=True)
class ExtrudedBubbleControls:
    """The simulation's inputs from the mode's Settings (ranges are (quiet, loud))."""

    large_count: tuple[float, float] = (6.0, 14.0)
    mid_count: tuple[float, float] = (20.0, 48.0)
    size_variety: float = 0.6               # 0 all alike .. 1 strongly varied (biased small)
    columns: float = 0.0                    # 0..1 share of bubbles that rise in lines along the stream
    stream_direction: tuple[float, float] = (0.0, 0.0)   # (around, height) degrees: 0 up; height into the scene
    stream_speed: tuple[float, float] = (0.05, 0.16)     # volume units per second
    drift: tuple[float, float] = (0.3, 0.8)  # lateral wander 0..1 at quiet, loud
    sway: float = 0.4                       # 0..1 side-to-side swing
    emission: tuple[float, float] = (0.3, 1.0)   # particle emission (specks, dust, trails) 0..1 at quiet, loud
    idle: float = 0.5                       # 0..1 gentle resting motion; never a size oscillator
    breathing: tuple[float, float] = (0.04, 0.18)        # large reaction strength, quiet..loud
    small_pulse: tuple[float, float] = (0.02, 0.10)      # mid reaction strength, quiet..loud
    sustained: float = 0.6                  # 0..1 how much a sustained loud passage moves the mid bubbles
    smoothing: float = 0.5                  # 0 snappy .. 1 soft (visual smoothing of level and breath)
    collision: tuple[float, float, float] = (0.4, 0.3, 0.3)   # Fuse, Pop, Bounce shares
    collision_scope: str = "all"            # "all", "big", "small" or "off"


@dataclass(frozen=True, slots=True)
class MusicInput:
    dt: float
    playing: bool
    intensity: float = 0.0                  # passage intensity 0..1
    onsets: tuple[tuple[str, float], ...] = ()   # (kind, weight 0..1) taken this step
    body_bands: tuple[float, float, float] = (0.0, 0.0, 0.0)  # existing full-dynamic bass/mid/high feed


@dataclass(frozen=True, slots=True)
class ExtrudedBubbleSnapshot:
    time: float = 0.0
    bubbles: tuple[float, ...] = ()         # BUBBLE_STRIDE floats each
    clusters: tuple[float, ...] = ()        # CLUSTER_STRIDE floats each
    level: float = 0.0
    breath: float = 0.0
    flash: float = 0.0
    stream: tuple[float, float, float] = (0.0, 1.0, 0.0)
    stream_speed: float = 0.0
    drift: float = 0.0
    emission: float = 0.0
    sustain: float = 0.0
    travel: float = 0.0                     # how far the stream has carried the water (volume units, ever rising)
    rays: float = 0.0                       # the light rays' driver (0..1, eased below the top: never pinned)
    shimmer: float = 0.0                    # the rays' shimmer phase (ever rising, faster on the hits)
    near_bubbles: tuple[float, ...] = ()    # Compatibility transport; the separate near-field cohort is disabled.
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
    alpha: float = 0.0
    leaving: bool = False
    popping: float = -1.0       # seconds into its pop, -1 when not popping
    cluster: int = -1
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)   # from its cluster's centre


@dataclass(slots=True)
class _Cluster:
    ident: int
    x: float
    y: float
    z: float
    members: list[int] = field(default_factory=list)


def stream_vector(around: float, height: float) -> tuple[float, float, float]:
    """The stream's unit direction: around 0 is up the screen (clockwise), height tips it into the scene."""
    a, h = math.radians(around), math.radians(height)
    return math.sin(a) * math.cos(h), math.cos(a) * math.cos(h), math.sin(h)


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


def _reaction_scale(pair: tuple[float, float], drive: float, expansion: float) -> float:
    """Authored strength spans contracted rest and musical expansion; zero disables both.

    Base radius is nominal size, not an uncontractable lower bound. A silent/held
    input converges to one size; no clock or independent oscillator creates pulses.
    """
    strength = max(0.0, min(1.0, max(pair)))
    # Normal reaction strength must reach a genuinely tiny rest. Accepted 2D's
    # big population can settle near 0.13x nominal radius; a 0.49x EB floor still
    # leaves its large shells inflated. Expansion retains the full authored range.
    rest = max(0.13, 1.0 - 1.45 * strength)
    return rest + (1.0 - rest) * drive + expansion * _lerp(pair, drive) * drive


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
        self._contacts: set[tuple[int, int]] = set()
        self._next_ident = 1
        self._time = 0.0
        self._level = 0.0
        self._breath = 0.0
        self._pulse = 0.0
        self._flash = 0.0
        self._sustain = 0.0
        self._travel = 0.0
        self._motion_phase = 0.0
        self._motion_rate: float | None = None
        self._body_big_envelope = 0.0
        self._body_small_envelope = 0.0
        self._small_body_reference = 0.0
        self._kick_swell = 0.0
        self._ray_lift = 0.0
        self._rays = 0.0
        self._shimmer = 0.0
        self._speed: float | None = None
        self._drift: float | None = None
        self._emission: float | None = None
        self._filled = False
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
        x, y, z = rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(0.05, 1.0)
        if controls.columns > 0.0 and rng.random() < controls.columns:
            # Columns (the mocks' lines of bubbles): the place across the stream on screen snaps to a lane, so the
            # bubble rises along it. A stream straight into the scene has no lanes.
            dx, dy = direction[0], direction[1]
            length = math.hypot(dx, dy)
            if length > 0.2:
                ax, ay = -dy / length, dx / length
                across = x * ax + y * ay
                lane = round(across / _LANE) * _LANE + rng.gauss(0.0, _LANE * 0.06)
                x, y = x + ax * (lane - across), y + ay * (lane - across)
        if not anywhere:
            # Upstream: walk back against the stream until just outside the volume.
            dx, dy, dz = direction
            steps = []
            for p, d, low, high in ((x, dx, -1.0, 1.0), (y, dy, -1.0, 1.0), (z, dz, 0.0, 1.0)):
                if d > 1e-6:
                    steps.append((p - low) / d)
                elif d < -1e-6:
                    steps.append((p - high) / d)
            back = (min(steps) if steps else 0.0) + 0.08
            x, y, z = x - dx * back, y - dy * back, z - dz * back
        bubble = _Bubble(self._next_ident, large, x, y, z, self._radius(large, controls.size_variety),
                         rng.uniform(0.0, math.tau), alpha=1.0 if anywhere else 0.0)
        self._next_ident += 1
        self._bubbles.append(bubble)

    def _outside(self, b: _Bubble) -> bool:
        return (abs(b.x) > 1.0 + _MARGIN + b.radius or abs(b.y) > 1.0 + _MARGIN + b.radius
                or b.z < -_MARGIN or b.z > 1.0 + _MARGIN)

    # -- one step ----------------------------------------------------------------------------------------------------

    def advance(self, music: MusicInput, controls: ExtrudedBubbleControls) -> ExtrudedBubbleSnapshot:
        dt = max(0.0, min(0.1, float(music.dt)))
        self._time += dt
        soft = 0.5 + 1.5 * max(0.0, min(1.0, controls.smoothing))       # visual smoothing scales every follower

        # One band-driven path for live capture and tests. The presence scalar is diagnostic:
        # it can remain at 1 through music and must not manufacture body motion or an idle sine.
        bass, mid, high = (max(0.0, min(1.0, float(v))) if music.playing else 0.0
                           for v in music.body_bands)
        big_body = max(bass, 0.28 * mid + 0.10 * high)
        small_body = min(1.0, max(0.70 * mid + 0.35 * high, 0.45 * bass))
        intensity = max(big_body, small_body)
        self._level = _follow(self._level, intensity, dt, 0.08 * soft, 0.45 * soft)
        onsets = music.onsets if music.playing else ()
        kick = max((w for kind, w in onsets if kind == "kick"), default=0.0)
        snare = max((w for kind, w in onsets if kind != "kick"), default=0.0)
        self._breath = _follow(max(self._breath, kick), 0.0, dt, 0.05, 0.25 * soft)
        self._kick_swell = _follow(self._kick_swell, self._breath, dt, 0.06 * soft, 0.34 * soft)
        self._pulse = max(self._pulse, snare)
        self._pulse = _follow(self._pulse, 0.0, dt, 0.03, 0.25 * soft)
        if onsets:
            self._flash = max(self._flash, max(w for _kind, w in onsets))
        self._flash = _follow(self._flash, 0.0, dt, 0.02, 0.6 * soft)

        level = self._level
        self._sustain = _follow(self._sustain, max(0.0, min(1.0, (intensity - 0.35) / 0.5)), dt, 1.2, 2.0)
        sustain = self._sustain * controls.sustained
        # Sustain strengthens the actual body response, not a discarded legacy snapshot term.
        # Silence settles gently over seconds; musical phrase changes retain their faster release.
        body_release = (1.5 if intensity < 0.01 else 0.20) * soft
        self._body_big_envelope = _follow(self._body_big_envelope,
            _soft_top(0.75 * big_body + 0.50 * self._kick_swell + 0.10 * sustain * big_body), dt, 0.06 * soft, body_release)
        # Small bubbles open on changing vocal/body energy, with restrained held support.
        # A hot mid/high plateau must not inflate the whole small field to hero size.
        self._small_body_reference = _follow(self._small_body_reference, small_body, dt, 0.7 * soft, 0.9 * soft)
        small_change = max(0.0, small_body - self._small_body_reference)
        self._body_small_envelope = _follow(self._body_small_envelope,
            _soft_top(0.50 * small_body + 1.10 * small_change + 0.40 * self._pulse
                      + 0.12 * sustain * small_body), dt, 0.06 * soft, body_release)
        # Resting phases barely advance. Sway and shader animation share this integrated musical time.
        idle_rate = 0.03 + 0.06 * max(0.0, min(1.0, controls.idle))
        motion_target = idle_rate + 1.60 * level + 0.22 * self._flash + 0.20 * sustain
        if self._motion_rate is None:
            self._motion_rate = motion_target
        self._motion_rate = _follow(self._motion_rate, motion_target, dt, 0.24 * soft, 1.1 * soft)
        self._motion_phase += dt * self._motion_rate
        # The light rays: the passage, a lift from the onsets (quick rise, slow fall) and a held loud passage, eased
        # below the top, so a saturated passage (the level held at 1) still moves them with its hits. Their shimmer
        # advances faster on the hits: a phase integral, so a change of rate never makes the pattern jump.
        self._ray_lift = _follow(self._ray_lift, self._flash, dt, 0.1, 0.4 * soft)
        # Follow the continuous light separately; do not smear its already-eased onset accent again.
        self._rays = _follow(self._rays, 0.65 * level + 0.05 * sustain,
                             dt, 0.08 * soft, 0.65 * soft)
        self._shimmer += dt * (idle_rate + 0.6 * level + 2.5 * self._ray_lift)
        direction = stream_vector(*controls.stream_direction)
        # Drift, stream speed and emission: quick attack, slow decay (the stream slowest), onsets only through them.
        low, high = controls.stream_speed
        activity = min(1.0, idle_rate + 1.6 * level)
        speed_target = (_lerp(controls.stream_speed, level) + (high - low) * (0.35 * self._flash + 0.15 * sustain)) * activity
        drift_target = _soft_top(_lerp(controls.drift, level) + 0.2 * sustain * (controls.drift[1] - controls.drift[0])) * activity
        emission_target = _soft_top(_lerp(controls.emission, level)
                                    + 0.2 * (controls.emission[1] - controls.emission[0]) * self._flash) * max(0.25, activity)
        if self._speed is None:
            self._speed, self._drift, self._emission = speed_target, drift_target, emission_target
        self._speed = _follow(self._speed, speed_target, dt, 0.36 * soft, 3.0 * soft)
        self._drift = _follow(self._drift, drift_target, dt, 0.5 * soft, 2.5 * soft)
        self._emission = _follow(self._emission, emission_target, dt, 0.1 * soft, 1.5 * soft)
        speed = self._speed
        # The procedural layers (bead chains, snow) move by this distance, never by time x a changing speed, so a
        # change of speed never makes them jump.
        self._travel += speed * dt

        # Population: fill at once on the first step, then grow toward the target upstream and thin by fading.
        targets = {True: int(round(min(MAX_BUBBLES, _lerp(controls.large_count, level)))),
                   False: int(round(min(MAX_BUBBLES, _lerp(controls.mid_count, level))))}
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
                for _ in range(targets[large]):
                    self._spawn(large, controls, direction, anywhere=True)
                continue
            shortage = targets[large] - len(live[large])
            if shortage > 0 and present[large] < limits[large]:
                # A steady inflow, faster the further below target (never a burst).
                self._spawn_credit[large] += dt * (0.5 + 1.5 * shortage / max(1, targets[large]))
                while self._spawn_credit[large] >= 1.0 / max(1, targets[large]) and shortage > 0 \
                        and len(self._bubbles) < MAX_BUBBLES:
                    if present[large] >= limits[large]:
                        break  # retiring identities retain their slot until their gentle fade completes
                    self._spawn_credit[large] -= 1.0 / max(1, targets[large])
                    self._spawn(large, controls, direction, anywhere=False)
                    present[large] += 1
                    shortage -= 1
            elif shortage < 0:
                self._spawn_credit[large] = 0.0
                # The furthest downstream leave first, fading out.
                ordered = sorted(live[large], key=lambda b: -(b.x * direction[0] + b.y * direction[1] + b.z * direction[2]))
                for b in ordered[:-shortage]:
                    b.leaving = True
        self._filled = True

        # Motion: the stream, sized (big bubbles a little faster), with drift and sway across it.
        across = (direction[1], -direction[0], 0.0) if abs(direction[2]) < 0.99 else (1.0, 0.0, 0.0)
        norm = math.hypot(*across) or 1.0
        across = (across[0] / norm, across[1] / norm, across[2] / norm)
        depth_axis = (direction[1] * across[2] - direction[2] * across[1],
                      direction[2] * across[0] - direction[0] * across[2],
                      direction[0] * across[1] - direction[1] * across[0])
        t = self._motion_phase
        for b in self._bubbles:
            if b.cluster >= 0:
                continue
            size = (b.radius - _MID_RADIUS[0]) / (_LARGE_RADIUS[1] - _MID_RADIUS[0])
            forward = speed * (0.65 + 0.6 * max(0.0, min(1.0, size)))
            wander = self._drift * 0.05 * (math.sin(t * 0.37 + b.phase) + 0.6 * math.sin(t * 0.83 + 2.1 * b.phase))
            # A slowly changing sine can still be a fast velocity; its amplitude must settle too.
            swing = (controls.sway * 0.06 * min(1.0, self._motion_rate)
                     * math.sin(t * (1.1 + 0.5 * math.sin(b.phase)) + 3.0 * b.phase))
            deep = self._drift * 0.015 * math.sin(t * 0.29 + 1.7 * b.phase)
            b.x += dt * (direction[0] * forward + across[0] * (wander + swing) + depth_axis[0] * deep)
            b.y += dt * (direction[1] * forward + across[1] * (wander + swing) + depth_axis[1] * deep)
            b.z += dt * (direction[2] * forward + across[2] * (wander + swing) + depth_axis[2] * deep)
        for c in self._clusters.values():
            members = [self._find(i) for i in c.members]
            members = [m for m in members if m is not None]
            if not members:
                continue
            forward = speed * 0.9
            wander = self._drift * 0.04 * math.sin(t * 0.31 + c.ident)
            c.x += dt * (direction[0] * forward + across[0] * wander)
            c.y += dt * (direction[1] * forward + across[1] * wander)
            c.z += dt * (direction[2] * forward + across[2] * wander)
            for m in members:
                m.x, m.y, m.z = c.x + m.offset[0], c.y + m.offset[1], c.z + m.offset[2]

        self._collide(controls)

        # Fades, pops and leaving.
        kept: list[_Bubble] = []
        for b in self._bubbles:
            if b.popping >= 0.0:
                b.popping += dt
                b.alpha = max(0.0, 1.0 - b.popping / _POP_SECONDS)
            elif b.leaving or self._outside(b):
                b.leaving = True
                b.alpha = max(0.0, b.alpha - dt / _FADE_OUT)
            else:
                b.alpha = min(1.0, b.alpha + dt / _FADE_IN)
            if b.alpha > 0.0 or (b.popping < 0.0 and not b.leaving):
                kept.append(b)
            else:
                self._contacts = {pair for pair in self._contacts if b.ident not in pair}
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

    def _collide(self, controls: ExtrudedBubbleControls) -> None:
        scope = controls.collision_scope
        fuse, pop, bounce = controls.collision
        total = fuse + pop + bounce
        if scope == "off" or total <= 0.0:
            self._contacts.clear()
            return
        fuse, pop = fuse / total, pop / total
        cell = 0.25
        grid: dict[tuple[int, int, int], list[_Bubble]] = {}
        for b in self._bubbles:
            if self._admitted(b, scope):
                grid.setdefault((int(math.floor(b.x / cell)), int(math.floor(b.y / cell)),
                                 int(math.floor(b.z / cell))), []).append(b)
        touching: set[tuple[int, int]] = set()
        for (cx, cy, cz), bucket in grid.items():
            neighbours = [b for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                          for b in grid.get((cx + dx, cy + dy, cz + dz), ())]
            for a in bucket:
                for b in neighbours:
                    if b.ident <= a.ident or (a.cluster >= 0 and a.cluster == b.cluster):
                        continue
                    dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
                    reach = (a.radius + b.radius) * 0.95
                    if dx * dx + dy * dy + dz * dz >= reach * reach:
                        continue
                    pair = (a.ident, b.ident)
                    touching.add(pair)
                    if pair in self._contacts:
                        continue          # each contact resolves once
                    self._contacts.add(pair)
                    choice = _pair_choice(*pair)
                    if choice < fuse:
                        self._fuse(a, b)
                    elif choice < fuse + pop:
                        loser = a if a.radius < b.radius else b
                        loser.popping = 0.0
                    else:
                        self._bounce(a, b)
        # Contacts end when the pair separates (so a later meeting resolves anew).
        self._contacts &= touching | {pair for pair in self._contacts if self._clustered(pair)}

    def _clustered(self, pair: tuple[int, int]) -> bool:
        a, b = self._find(pair[0]), self._find(pair[1])
        return a is not None and b is not None and a.cluster >= 0 and a.cluster == b.cluster

    def _fuse(self, a: _Bubble, b: _Bubble) -> None:
        members_a = self._clusters[a.cluster].members if a.cluster >= 0 else [a.ident]
        members_b = self._clusters[b.cluster].members if b.cluster >= 0 else [b.ident]
        if len(members_a) + len(members_b) > CLUSTER_MAX:
            self._bounce(a, b)
            return
        bubbles = [self._find(i) for i in members_a + members_b]
        bubbles = [m for m in bubbles if m is not None]
        weight = sum(m.radius ** 3 for m in bubbles) or 1.0
        cx = sum(m.x * m.radius ** 3 for m in bubbles) / weight
        cy = sum(m.y * m.radius ** 3 for m in bubbles) / weight
        cz = sum(m.z * m.radius ** 3 for m in bubbles) / weight
        # Joined with a neck: centres drawn in to 80-90% of their touching distance (it varies by pair).
        squeeze = 0.8 + 0.1 * _pair_choice(a.ident + 7, b.ident + 13)
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        wanted = (a.radius + b.radius) * squeeze
        shift = (wanted - distance) * 0.5 / distance
        if a.cluster < 0 and b.cluster < 0:
            a.x, a.y, a.z = a.x - dx * shift, a.y - dy * shift, a.z - dz * shift
            b.x, b.y, b.z = b.x + dx * shift, b.y + dy * shift, b.z + dz * shift
        for old in {a.cluster, b.cluster} - {-1}:
            self._clusters.pop(old, None)
        ident = min(m.ident for m in bubbles)
        cluster = _Cluster(ident, cx, cy, cz, [m.ident for m in bubbles])
        self._clusters[ident] = cluster
        for m in bubbles:
            m.cluster = ident
            m.offset = (m.x - cx, m.y - cy, m.z - cz)

    def _bounce(self, a: _Bubble, b: _Bubble) -> None:
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        overlap = (a.radius + b.radius) - distance
        if overlap <= 0.0:
            return
        # A gentle elastic push: each moves apart in proportion to the other's size.
        total = a.radius ** 3 + b.radius ** 3
        for bubble, sign, share in ((a, -1.0, b.radius ** 3 / total), (b, 1.0, a.radius ** 3 / total)):
            if bubble.cluster >= 0:
                continue
            push = sign * overlap * share * 1.05 / distance
            bubble.x += dx * push
            bubble.y += dy * push
            bubble.z += dz * push

    def _prune_clusters(self) -> None:
        live = {b.ident: b for b in self._bubbles}
        for ident in list(self._clusters):
            cluster = self._clusters[ident]
            cluster.members = [m for m in cluster.members if m in live and live[m].popping < 0.0]
            if len(cluster.members) < 2:
                for m in cluster.members:
                    live[m].cluster = -1
                del self._clusters[ident]

    # -- snapshot ----------------------------------------------------------------------------------------------------

    def _wakes(self, dt: float, big_scale: float, small_scale: float) -> tuple[float, ...]:
        """Logical emitter identity survives compaction, fusion, pop and surface exit.

        Retiring wakes retain their last *own* world-volume source, never rebind to the shell currently occupying
        the old GPU instance slot. The shader wipes each wake from the travel-facing head backwards over its life.
        """
        current: dict[int, tuple[float, float, float, float, int, float, float, float]] = {}
        for b in self._bubbles:
            if b.cluster < 0 and b.popping < 0 and not b.leaving and b.alpha > 0.02:
                current[b.ident] = (b.x, b.y, b.z, b.radius * (big_scale if b.large else small_scale),
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
        big_scale = _reaction_scale(controls.breathing, self._body_big_envelope, 4.0)
        small_scale = _reaction_scale(controls.small_pulse, self._body_small_envelope, 3.0)
        index = {b.ident: i for i, b in enumerate(self._bubbles)}
        bubbles: list[float] = []
        for b in self._bubbles:
            swell = (big_scale if b.large else small_scale) - 1.0
            radius = b.radius * (1.0 + swell + (0.25 * min(1.0, b.popping / _POP_SECONDS) if b.popping >= 0 else 0.0))
            bubbles.extend((b.x, b.y, b.z, radius, b.alpha, swell, float(b.ident), float(b.cluster)))
        clusters: list[float] = []
        for cluster in self._clusters.values():
            slots = [float(index[m]) for m in cluster.members if m in index][:CLUSTER_MAX]
            clusters.extend((float(len(slots)), *slots, *([-1.0] * (CLUSTER_MAX - len(slots)))))
        return ExtrudedBubbleSnapshot(self._time, tuple(bubbles), tuple(clusters), level, self._breath,
                                      self._flash, direction, speed, self._drift, self._emission, self._sustain,
                                      self._travel, _soft_top(self._rays + 0.3 * self._ray_lift, knee=0.9), self._shimmer, (), self._motion_phase,
                                      self._wakes(dt, big_scale, small_scale))


__all__ = ["BUBBLE_STRIDE", "CLUSTER_MAX", "CLUSTER_STRIDE", "ExtrudedBubbleControls", "ExtrudedBubbleSimulation",
           "ExtrudedBubbleSnapshot", "MAX_BUBBLES", "MusicInput", "stream_vector"]

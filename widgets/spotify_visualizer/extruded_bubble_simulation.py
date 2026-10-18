"""Extruded Bubble's own logical simulation: the large and mid bubbles of a framed 3D volume.

A real mode of its own (original Bubble is only a guideline for gradients, drift, breathing motion and visual
smoothing). Advanced once per logical capture with dt from the sole Visualizer clock and the existing audio feeds; it
adds no clock, DSP or floor and never touches Qt or GL. Deterministic: the same inputs give the same frames.

**Volume.** x and y span -1..1 (screen right and up), z spans 0..1 (near to far). The renderer maps it into the
framed camera's view.

**What it owns.** Only what music and collisions move: up to ``MAX_BUBBLES`` large and mid bubbles, each with an
identity, position, velocity, base radius, a breathing response, a fade, and fuse-cluster membership. Bead chains,
fizz and particulate are procedural on the GPU from the snapshot's scalars (stream, speed, level, flash).

**Music.** Fixed-scale drivers only, no dynamic floors: ``level`` is the passage intensity
(``BeatEngine.get_musical_intensity``: 0..1 on the fixed real-music scale) and onsets count by ``musical_weight`` (a
near-silent passage barely moves anything). Every quiet..loud range is read at ``level``. Kicks make the large bubbles
breathe, snares pulse the mid ones. Drift, stream speed and particle emission each follow their target with a quick
attack and a slow decay (the stream slowest of all), and onsets feed them only through those followers, so nothing
stutters, judders or stops suddenly. Sustained loud passages have their own response: ``sustain`` (the level held
for seconds: slow to rise, slow to fall) lets the large bubbles hold large (kicks add less on top as it rises: better
than flickering), while the mid bubbles shimmer on their own phases and drift and the stream lift, so a saturated
passage stays alive between hits. Nothing pins: values near the top of their range pass a soft knee, never a clamp. In silence a light idle energy keeps the bubbles gently
breathing.

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


@dataclass(frozen=True, slots=True)
class ExtrudedBubbleControls:
    """The simulation's inputs from the mode's Settings (ranges are (quiet, loud))."""

    large_count: tuple[float, float] = (6.0, 14.0)
    mid_count: tuple[float, float] = (20.0, 48.0)
    size_variety: float = 0.6               # 0 all alike .. 1 strongly varied (biased small)
    stream_direction: tuple[float, float] = (0.0, 0.0)   # (around, height) degrees: 0 up; height into the scene
    stream_speed: tuple[float, float] = (0.05, 0.16)     # volume units per second
    drift: tuple[float, float] = (0.3, 0.8)  # lateral wander 0..1 at quiet, loud
    sway: float = 0.4                       # 0..1 side-to-side swing
    emission: tuple[float, float] = (0.3, 1.0)   # particle emission (specks, dust, trails) 0..1 at quiet, loud
    idle: float = 0.5                       # 0..1 the light energy kept in silence
    breathing: tuple[float, float] = (0.04, 0.18)        # large bubbles' swell (share of radius)
    small_pulse: tuple[float, float] = (0.02, 0.10)      # mid bubbles' pulse (share of radius)
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
        self._speed: float | None = None
        self._drift: float | None = None
        self._emission: float | None = None
        self._filled = False
        self._spawn_credit = {True: 0.0, False: 0.0}

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

        # Music: the passage level, breathing from kicks, a pulse from snares, a flash per onset.
        intensity = max(0.0, min(1.0, float(music.intensity))) if music.playing else 0.0
        self._level = _follow(self._level, intensity, dt, 0.25 * soft, 1.2 * soft)
        kick = max((w for kind, w in music.onsets if kind == "kick"), default=0.0)
        snare = max((w for kind, w in music.onsets if kind != "kick"), default=0.0)
        if kick > 0.0:
            self._breath = max(self._breath, kick)
        # Between kicks the breath settles toward a gentle idle sway (stronger in silence, never zero while alive).
        quietness = 1.0 - self._level
        idle_breath = controls.idle * (0.12 + 0.18 * quietness) * (0.5 + 0.5 * math.sin(self._time * 0.6))
        self._breath = _follow(self._breath, idle_breath, dt, 0.04 * soft, 0.35 * soft)
        self._pulse = max(self._pulse, snare)
        self._pulse = _follow(self._pulse, 0.0, dt, 0.03, 0.25 * soft)
        if music.onsets:
            self._flash = max(self._flash, max(w for _kind, w in music.onsets))
        self._flash = _follow(self._flash, 0.0, dt, 0.02, 0.6 * soft)

        level = self._level
        # A loud passage held for seconds: slow to build, slow to fade.
        self._sustain = _follow(self._sustain, max(0.0, (intensity - 0.45) / 0.55), dt, 2.5, 3.5)
        sustain = self._sustain
        direction = stream_vector(*controls.stream_direction)
        # Drift, stream speed and emission: quick attack, slow decay (the stream slowest), onsets only through them.
        low, high = controls.stream_speed
        speed_target = _lerp(controls.stream_speed, level) + (high - low) * (0.35 * self._flash + 0.15 * sustain)
        drift_target = _soft_top(_lerp(controls.drift, level) + 0.2 * sustain * (controls.drift[1] - controls.drift[0]))
        emission_target = _soft_top(_lerp(controls.emission, level)
                                    + 0.2 * (controls.emission[1] - controls.emission[0]) * self._flash)
        if self._speed is None:
            self._speed, self._drift, self._emission = speed_target, drift_target, emission_target
        self._speed = _follow(self._speed, speed_target, dt, 0.35 * soft, 3.0 * soft)
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
        for large in (True, False):
            if not self._filled:
                for _ in range(targets[large]):
                    self._spawn(large, controls, direction, anywhere=True)
                continue
            shortage = targets[large] - len(live[large])
            if shortage > 0:
                # A steady inflow, faster the further below target (never a burst).
                self._spawn_credit[large] += dt * (0.5 + 1.5 * shortage / max(1, targets[large]))
                while self._spawn_credit[large] >= 1.0 / max(1, targets[large]) and shortage > 0 \
                        and len(self._bubbles) < MAX_BUBBLES:
                    self._spawn_credit[large] -= 1.0 / max(1, targets[large])
                    self._spawn(large, controls, direction, anywhere=False)
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
        t = self._time
        for b in self._bubbles:
            if b.cluster >= 0:
                continue
            size = (b.radius - _MID_RADIUS[0]) / (_LARGE_RADIUS[1] - _MID_RADIUS[0])
            forward = speed * (0.65 + 0.6 * max(0.0, min(1.0, size)))
            wander = self._drift * 0.05 * (math.sin(t * 0.37 + b.phase) + 0.6 * math.sin(t * 0.83 + 2.1 * b.phase))
            swing = controls.sway * 0.06 * math.sin(t * (1.1 + 0.5 * math.sin(b.phase)) + 3.0 * b.phase)
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
        return self._snapshot(direction, speed, controls)

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

    def _snapshot(self, direction, speed, controls: ExtrudedBubbleControls) -> ExtrudedBubbleSnapshot:
        level = self._level
        # Large bubbles: kicks make them breathe; through a sustained loud passage they hold large instead, the kicks
        # adding less on top (holding beats flickering on every beat).
        hold = self._sustain
        breathing = _lerp(controls.breathing, level) * max(hold * 0.85, self._breath * (1.0 - 0.6 * hold))
        pulse = _lerp(controls.small_pulse, level) * self._pulse
        shimmer = _lerp(controls.small_pulse, 1.0) * controls.sustained * self._sustain
        index = {b.ident: i for i, b in enumerate(self._bubbles)}
        bubbles: list[float] = []
        for b in self._bubbles:
            # Mid bubbles: the snare pulse, and through a sustained passage a shimmer on each one's own phase.
            swell = breathing if b.large else max(pulse, shimmer * (0.5 + 0.5 * math.sin(self._time * 3.1 + b.phase)))
            radius = b.radius * (1.0 + swell + (0.25 * min(1.0, b.popping / _POP_SECONDS) if b.popping >= 0 else 0.0))
            bubbles.extend((b.x, b.y, b.z, radius, b.alpha, swell, float(b.ident), float(b.cluster)))
        clusters: list[float] = []
        for cluster in self._clusters.values():
            slots = [float(index[m]) for m in cluster.members if m in index][:CLUSTER_MAX]
            clusters.extend((float(len(slots)), *slots, *([-1.0] * (CLUSTER_MAX - len(slots)))))
        return ExtrudedBubbleSnapshot(self._time, tuple(bubbles), tuple(clusters), level, self._breath,
                                      self._flash, direction, speed, self._drift, self._emission, self._sustain,
                                      self._travel)


__all__ = ["BUBBLE_STRIDE", "CLUSTER_MAX", "CLUSTER_STRIDE", "ExtrudedBubbleControls", "ExtrudedBubbleSimulation",
           "ExtrudedBubbleSnapshot", "MAX_BUBBLES", "MusicInput", "stream_vector"]

"""The straightforward forms of Extruded Bubble's logical-tick hot paths, as they were before the 6 Nov 2026 cut.

The production forms were rewritten for the live logical thread (fewer dictionary probes, written-out arithmetic,
per-settings caches) with byte-identical output. These copies are the readable oracle the exactness tests compare the
production forms against; they are test-owned and must never be imported by production.
"""
from __future__ import annotations

import math
from itertools import chain

from widgets.spotify_visualizer import extruded_bubble_drift as drift
from widgets.spotify_visualizer import extruded_bubble_simulation as sim
from widgets.spotify_visualizer.extruded_bubble_drift import steer as _drift_steer
from widgets.spotify_visualizer.extruded_bubble_wake import trails as wake_trails


def contact_candidates(members, cell):
    """The dictionary-grid scan: every same-or-neighbouring-cell pair, lower identity first, in scan order."""
    grid = {}
    for b in members:
        grid.setdefault((int(math.floor(b.x / cell)), int(math.floor(b.y / cell)),
                         int(math.floor(b.z / cell))), []).append(b)
    columns = {}
    for (cx, cy, cz), bucket in grid.items():
        columns.setdefault((cx, cy), {})[cz] = bucket
    around = {(cx, cy): [column for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                         if (column := columns.get((cx + dx, cy + dy))) is not None]
              for cx, cy in columns}
    candidates = []
    for (cx, cy, cz), bucket in grid.items():
        neighbours = []
        for column in around[(cx, cy)]:
            for dz in (-1, 0, 1):
                near = column.get(cz + dz)
                if near is not None:
                    neighbours.extend(near)
        for a in bucket:
            for b in neighbours:
                if b.ident <= a.ident:
                    continue
                candidates.append((a, b))
    return candidates


def collide(self, controls, dt):
    scope = controls.collision_scope
    fuse, pop, bounce = controls.collision
    total = fuse + pop + bounce
    if scope == "off" or total <= 0.0:
        self._contacts.clear()
        return
    fuse, pop = fuse / total, pop / total
    cell = max(.1, 2.0 * max((b.current_radius for b in self._bubbles), default=0.0))
    every, big = scope == "all", scope == "big"
    candidates = contact_candidates(
        [b for b in self._bubbles
         if not b.leaving and (every or big == b.large) and (b.alpha >= 0.6 if b.popping < 0.0 else b.alpha > 0.05)],
        cell)
    touching = set()
    for a, b in candidates:
        if a.popping >= 0.0 or b.popping >= 0.0:
            if self._obstacle(a, scope) or self._obstacle(b, scope):
                if all(self._admitted(m, scope) or self._obstacle(m, scope) for m in (a, b)) \
                        and not (a.cluster >= 0 and a.cluster == b.cluster) and self._bounce(a, b, dt):
                    touching.add((a.ident, b.ident))
            continue
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        reach = a.current_radius + b.current_radius
        pair = (a.ident, b.ident)
        if pair in self._contacts:
            reach *= 1.03
        if dx * dx + dy * dy + dz * dz >= reach * reach:
            continue
        if not self._admitted(a, scope) or not self._admitted(b, scope):
            continue
        if a.cluster >= 0 and a.cluster == b.cluster:
            continue
        touching.add(pair)
        if pair not in self._contacts:
            choice = sim._pair_choice(*pair)
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
    by_ident = {b.ident: b for b in self._bubbles} if self._contacts else {}
    self._contacts = {pair: response for pair, response in self._contacts.items()
                      if pair in touching or self._clustered(pair, by_ident)}


def place_cluster(self, cluster, members):
    by_id = {m.ident: m for m in members}
    positions = {members[0].ident: (0.0, 0.0, 0.0)}
    for _ in range(sim.CLUSTER_MAX - 1):
        for left, right, axis, ratio in cluster.edges:
            if left not in by_id or right not in by_id:
                continue
            length = ratio * (sim._shown_radius(by_id[left]) + sim._shown_radius(by_id[right]))
            if left in positions and right not in positions:
                positions[right] = tuple(p + a * length for p, a in zip(positions[left], axis))
            elif right in positions and left not in positions:
                positions[left] = tuple(p - a * length for p, a in zip(positions[right], axis))
    weight = sum(m.radius ** 3 for m in members)
    center = tuple(sum(positions[m.ident][i] * m.radius ** 3 for m in members) / weight for i in range(3))
    for m in members:
        m.offset = tuple(positions[m.ident][i] - center[i] for i in range(3))
        m.x, m.y, m.z = (c + d for c, d in zip((cluster.x, cluster.y, cluster.z), m.offset))


def advance_clusters(self, steering, meander, group_drift, t, direction, across, depth_axis, axis_origin, speed, dt):
    by_ident = {b.ident: b for b in self._bubbles} if self._clusters else {}
    for c in self._clusters.values():
        members = [by_ident.get(i) for i in c.members]
        members = [m for m in members if m is not None]
        if not members:
            continue
        forward = speed
        wander = meander * group_drift * sim.WORLD_UNIT * 0.04 * math.sin(t * 0.31 + c.ident)
        steer = _drift_steer(steering, (c.x, c.y, c.z), 1.3 * c.ident, t, direction, across, depth_axis,
                             axis_origin, group_drift * sim.WORLD_UNIT)
        c.x += dt * (direction[0] * forward + across[0] * wander + c.push[0] + steer[0])
        c.y += dt * (direction[1] * forward + across[1] * wander + c.push[1] + steer[1])
        c.z += dt * (direction[2] * forward + across[2] * wander + c.push[2] + steer[2])
        c.push = sim._decayed(c.push, dt)
        merge = 1.0 - math.exp(-dt / sim._FUSE_SECONDS)
        c.edges = [(left, right, axis, ratio + (min(ratio, sim._FUSE_RATIO) - ratio) * merge)
                   for left, right, axis, ratio in c.edges]
        self._place_cluster(c, members)


def wakes(self, dt, share):
    field = self._wake_field
    field.flow(dt, self._motion_phase)
    if share != self._wake_share:
        self._wake_share, self._wake_chosen = share, {}
    current = {}
    chosen_by_ident, retiring = self._wake_chosen, self._wake_retiring
    for b in self._bubbles:
        if b.cluster < 0 and b.popping < 0 and not b.leaving and b.alpha > 0.02:
            ident, head = b.ident, (b.x, b.y, b.z)
            chosen = chosen_by_ident.get(ident)
            if chosen is None:
                chosen = chosen_by_ident[ident] = wake_trails(ident, share)
            trailing = ident in field
            if chosen and trailing and ident in retiring:
                field.remove(ident)
                trailing = False
            if chosen and not trailing:
                trailing = field.add(ident, b.radius, head)
            elif not chosen and trailing:
                field.remove(ident)
                trailing = False
            if trailing:
                field.follow(ident, head, b.visual_radius, dt, max(4.0 * b.radius, 0.1 * sim.WORLD_UNIT))
                current[ident] = (b.x, b.y, b.z, b.visual_radius, ident, -1.0, b.alpha, b.radius,
                                  1.0, *field.record(ident, head))
            else:
                current[ident] = (b.x, b.y, b.z, b.visual_radius, ident, -1.0, b.alpha, b.radius,
                                  *sim._NO_WAKE_PATH)
    retained = {}
    for ident, old in self._wake_retiring.items():
        age = old[5] + dt / sim._WAKE_RETIRE_SECONDS
        if age < 1.0:
            retained[ident] = ((*old[:5], age, *old[6:9], *field.record(ident, old[:3])) if ident in field
                               else (*old[:5], age, *old[6:]))
    for ident, old in self._wake_live.items():
        if ident not in current and ident not in retained:
            retained[ident] = (*old[:5], 0.0, *old[6:])
    if len(retained) > sim.MAX_BUBBLES:
        retained = dict(sorted(retained.items(), key=lambda item: item[1][5])[:sim.MAX_BUBBLES])
    self._wake_live, self._wake_retiring = current, retained
    for ident in field.idents():
        if ident not in current and ident not in retained:
            field.remove(ident)
    if len(self._wake_chosen) > 4 * sim.MAX_BUBBLES:
        self._wake_chosen = {ident: self._wake_chosen[ident] for ident in current if ident in self._wake_chosen}
    records = list(current.values())[:sim.MAX_BUBBLES]
    records.extend(retained.values())
    return tuple(chain.from_iterable(records))


def snapshot(self, direction, speed, controls, dt):
    index = {b.ident: i for i, b in enumerate(self._bubbles)}
    bubbles = []
    for b in self._bubbles:
        swell = b.visual_radius / b.radius - 1.0
        bubbles.extend((b.x, b.y, b.z, b.visual_radius, b.alpha, swell, float(b.ident), float(b.cluster)))
    clusters = []
    for cluster in self._clusters.values():
        slots = [float(index[m]) for m in cluster.members if m in index][:sim.CLUSTER_MAX]
        clusters.extend((float(len(slots)), *slots, *([-1.0] * (sim.CLUSTER_MAX - len(slots)))))
    return sim.ExtrudedBubbleSnapshot(self._time, tuple(bubbles), tuple(clusters), self._level,
                                      self._flash, direction, speed, self._drift_shown, self._emission, self._sustain,
                                      self._travel, self._rays, self._shimmer, self._motion_phase,
                                      self._wakes(dt, controls.wake_trails), self._passage, self._chain_activity,
                                      self._drift_log.families, self._drift_log.steps,
                                      chain_drive=self._chain_drive)


def steer(kind, position, phase, t, direction, across, depth_axis, axis_origin, amount, *, ops=math):
    """The closure form of extruded_bubble_drift.steer."""
    def combine(a, b):
        return (amount * (a * across[0] + b * depth_axis[0]), amount * (a * across[1] + b * depth_axis[1]),
                amount * (a * across[2] + b * depth_axis[2]))

    if kind == "left":
        return combine(-drift._STEER_SPEED, 0.0)
    if kind == "right":
        return combine(drift._STEER_SPEED, 0.0)
    if kind == "diagonal":
        return combine(drift._STEER_SPEED * ops.sqrt(.5), drift._STEER_SPEED * ops.sqrt(.5))
    if kind == "random":
        return combine(drift._RANDOM_SPEED * ops.cos(phase), drift._RANDOM_SPEED * ops.sin(phase))
    if kind in ("swish_across", "swish_depth"):
        sway = drift._SWISH_SPEED * ops.sin(t * drift._SWISH_RATE - 0.35 * ops.sin(phase))
        return combine(sway, 0.0) if kind == "swish_across" else combine(0.0, sway)
    if kind in ("swirl_cw", "swirl_ccw"):
        d0, d1, d2 = direction
        r0, r1, r2 = position[0] - axis_origin[0], position[1] - axis_origin[1], position[2] - axis_origin[2]
        along = 0 + r0 * d0 + r1 * d1 + r2 * d2
        radial = (r0 - along * d0, r1 - along * d1, r2 - along * d2)
        distance = ops.sqrt(0 + radial[0] * radial[0] + radial[1] * radial[1] + radial[2] * radial[2])
        if ops is math:
            if distance < 1e-3 * sim.WORLD_UNIT:
                cosine, sine = math.cos(phase), math.sin(phase)
                radial = (cosine * across[0] + sine * depth_axis[0], cosine * across[1] + sine * depth_axis[1],
                          cosine * across[2] + sine * depth_axis[2])
            else:
                radial = (radial[0] / distance, radial[1] / distance, radial[2] / distance)
        else:
            near_axis = distance < 1e-3 * sim.WORLD_UNIT
            if not near_axis.any():
                radial = tuple(a / distance for a in radial)
            else:
                safe_distance = ops.maximum(distance, 1e-12)
                cosine, sine = ops.cos(phase), ops.sin(phase)
                radial = tuple(ops.where(near_axis, cosine * u + sine * v, a / safe_distance)
                               for a, u, v in zip(radial, across, depth_axis))
        tangent = (direction[1] * radial[2] - direction[2] * radial[1],
                   direction[2] * radial[0] - direction[0] * radial[2],
                   direction[0] * radial[1] - direction[1] * radial[0])
        sign = 1.0 if kind == "swirl_ccw" else -1.0
        return (amount * (sign * drift._SWIRL_SPEED * tangent[0] + drift._SWIRL_WIDEN * radial[0]),
                amount * (sign * drift._SWIRL_SPEED * tangent[1] + drift._SWIRL_WIDEN * radial[1]),
                amount * (sign * drift._SWIRL_SPEED * tangent[2] + drift._SWIRL_WIDEN * radial[2]))
    return (0.0, 0.0, 0.0)

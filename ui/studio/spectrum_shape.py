"""The Spectrum family's authored shape for the Studio (mode-neutral over the family's key prefix).

Spectrum, Extruded Spectrum and Neon Lake's Frequency Response store the same shape (``<prefix>mirrored``,
``<prefix>shape_nodes``, the mirrored / linear frequency lanes and their strengths) under the rules of Settings'
former ``SpectrumShapeEditor``. This module owns those rules for the Studio: the admission of each stored value, the
structural edits (add / remove node, lane swap), the shape instrument's spec (``ui.studio.shape``: one canvas with
the curve, its nodes and the lanes) and the preview the canvas draws under the curve, computed by the engine's own
functions. Adapters pass their prefix and never copy any of it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Mapping

from ui.studio.schema import SHAPE, SHAPE_BLEND, SWITCH, ShapeLayout, ShapeSpec

MIN_NODES = 1                                # the shape's node count (Settings' former editor: 1..5)
MAX_NODES = 5

ADD_NODE = "shape.add_node"
REMOVE_NODE = "shape.remove_node."          # + node index
LANE_PREVIOUS = "shape.lane_previous."      # + "1." (mirrored) / "0." (linear) + boundary index
LANE_NEXT = "shape.lane_next."


@dataclass(frozen=True)
class ShapeKeys:
    """A family mode's shape keys from its prefix (``spectrum_``, ``extruded_spectrum_``)."""

    prefix: str

    @property
    def nodes(self) -> str:
        return self.prefix + "shape_nodes"

    @property
    def mirrored(self) -> str:
        return self.prefix + "mirrored"

    @property
    def notches(self) -> dict[bool, str]:
        return {True: self.prefix + "notch_positions_mirrored", False: self.prefix + "notch_positions_linear"}

    @property
    def lanes(self) -> dict[bool, str]:
        return {True: self.prefix + "lane_strengths_mirrored", False: self.prefix + "lane_strengths_linear"}

    @property
    def all(self) -> tuple[str, ...]:
        return (self.mirrored, self.nodes, *self.notches.values(), *self.lanes.values())

    @property
    def bar_count(self) -> str:
        return self.prefix + "bar_count"

    @property
    def profile_floor(self) -> str:
        return self.prefix + "profile_floor"


def canonical(key: str):
    from core.settings.default_contract import require_canonical_default
    return require_canonical_default("widgets.spotify_visualizer")[key]


def node_limits() -> tuple[int, int]:
    return MIN_NODES, MAX_NODES


# ------------------------------------------------------------------------------- admission
def unit(value: Any, previous: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(previous)
    return max(0.0, min(1.0, number)) if math.isfinite(number) else float(previous)


def percent(value: Any, previous: Any, low: float = 0.0) -> float:
    """A Settings 0..100 % slider's stored value (hundredths)."""
    return round(max(low, unit(value, previous)), 2)


def admit_nodes(candidate: Any, previous: Any, fallback: str = "spectrum_shape_nodes") -> list:
    """The shape editor's rules: 1..5 nodes of [x, y] in 0..1, kept in x order. A candidate that keeps the order
    is taken as it is (the shape instrument hands over the list with the dragged node already in its place, as
    Settings re-sorted one dragged past a neighbour); a node moved out of order stops at its neighbours."""
    low, high = node_limits()
    try:
        old = [[float(x), float(y)] for x, y in previous]
    except (TypeError, ValueError):
        old = [list(map(float, node)) for node in canonical(fallback)]
    try:
        new = [[unit(x, 0.0), unit(y, 0.0)] for x, y in candidate]
    except (TypeError, ValueError):
        return old
    if not low <= len(new) <= high:
        return old
    if len(new) == len(old):
        for index, (node, before) in enumerate(zip(new, old)):
            if abs(node[0] - before[0]) > 1e-12:
                left = new[index - 1][0] if index > 0 else 0.0
                right = new[index + 1][0] if index + 1 < len(new) else 1.0
                node[0] = max(left, min(right, node[0]))
    return sorted(new, key=lambda node: node[0])


def admit_notches(candidate: Any, previous: Any) -> list:
    """Frequency boundaries [[x, label], ...]: the count and the set of lanes never change (Settings keeps both).
    The lanes' order may change, as Settings' boundary drag past a neighbour reorders them (the Studio reorders
    with its lane swap actions); a candidate naming other lanes keeps the previous ones. A moved boundary stops
    at its neighbours, then the list stays in x order."""
    try:
        old = [[float(x), str(label)] for x, label in previous]
        new = [[unit(x, 0.0), str(label)] for x, label in candidate]
    except (TypeError, ValueError):
        return [list(n) for n in previous]
    if len(new) != len(old):
        return old
    reordered = sorted(label for _x, label in new) == sorted(label for _x, label in old)
    for index, (node, before) in enumerate(zip(new, old)):
        if not reordered:
            node[1] = before[1]
        if abs(node[0] - before[0]) > 1e-12:
            low = new[index - 1][0] if index > 0 else 0.0
            high = new[index + 1][0] if index + 1 < len(new) else 1.0
            node[0] = max(low, min(high, node[0]))
    return sorted(new, key=lambda node: node[0])


def admit_lanes(candidate: Any, previous: Any) -> dict:
    """Lane strengths {label: 0..1} for the labels the profile already has (``_normalize_lane_strengths``)."""
    old = dict(previous) if isinstance(previous, Mapping) else {}
    source = candidate if isinstance(candidate, Mapping) else {}
    return {label: unit(source.get(label, value), value) for label, value in old.items()}


def admit_colour(candidate: Any, previous: Any) -> list:
    try:
        values = [int(round(float(v))) for v in candidate]
    except (TypeError, ValueError):
        return list(previous)
    if len(values) == 3:
        values.append(int(previous[3]) if len(previous) > 3 else 255)
    if len(values) != 4:
        return list(previous)
    return [max(0, min(255, v)) for v in values]


def admit_shape(keys: ShapeKeys, key: str, candidate: Any, previous: Any):
    """Admission of one shape key, or ``NotImplemented`` when ``key`` is not one."""
    if key == keys.nodes:
        return admit_nodes(candidate, previous, keys.nodes)
    if key in keys.notches.values():
        return admit_notches(candidate, previous)
    if key in keys.lanes.values():
        return admit_lanes(candidate, previous)
    if key == keys.mirrored:
        return bool(candidate)
    return NotImplemented


# -------------------------------------------------------------------------- structural edits
def added_node(nodes) -> list:
    """Settings adds a node where the user clicks; the Studio adds one at the middle of the widest gap along the
    bars (the ends included), on the current silhouette (``interpolate_nodes``, the curve the engine samples), so
    adding a node barely changes the shape until it is moved."""
    from utils.curve_nodes import interpolate_nodes
    current = [[float(x), float(y)] for x, y in nodes]
    xs = [0.0] + [x for x, _y in current] + [1.0]
    width, left = max((xs[i + 1] - xs[i], xs[i]) for i in range(len(xs) - 1))
    x = left + width / 2.0
    samples = 1001
    y = interpolate_nodes(current, samples)[int(round(x * (samples - 1)))]
    return sorted(current + [[x, max(0.0, min(1.0, float(y)))]], key=lambda n: n[0])


def structure_edit(keys: ShapeKeys, action_id: str, values: Mapping[str, Any]):
    """(undo label, {path: value}) for one of the shape editor's structural edits, or None while it is not
    admissible: Add Node below the maximum, Remove Node above the minimum (Settings' click / right-click rules),
    and swapping a frequency lane with its neighbour (what Settings' boundary drag past a neighbour does)."""
    low, high = node_limits()
    nodes = [[float(x), float(y)] for x, y in values.get(keys.nodes, ())]
    if action_id == ADD_NODE:
        return ("Add Shape Node", {(keys.nodes,): added_node(nodes)}) if len(nodes) < high else None
    if action_id.startswith(REMOVE_NODE):
        index = int(action_id[len(REMOVE_NODE):])
        if len(nodes) <= low or not 0 <= index < len(nodes):
            return None
        return f"Remove Shape Node {index + 1}", {(keys.nodes,): nodes[:index] + nodes[index + 1:]}
    for prefix, step in ((LANE_PREVIOUS, -1), (LANE_NEXT, 1)):
        if action_id.startswith(prefix):
            layout, _dot, index_text = action_id[len(prefix):].partition(".")
            key, index = keys.notches[layout == "1"], int(index_text)
            notches = [list(n) for n in values.get(key, ())]
            other = index + step
            if not (0 <= index < len(notches) and 0 <= other < len(notches)):
                return None
            notches[index][1], notches[other][1] = notches[other][1], notches[index][1]
            return f"Swap {notches[other][1]} And {notches[index][1]} Lanes", {(key,): notches}
    return None


def profile(keys: ShapeKeys, values: Mapping[str, Any]) -> dict:
    """What the shape does to the bars, for the instrument's preview under the curve: per bar, the authored
    silhouette and that height at the lane's authored strength; and the lane strength along the lane axis. All of it
    is the engine's own (``bar_computation``: the functions ``fft_to_bars`` shapes the bars with), on the Studio's
    current values. ``bars`` run left to right as drawn; ``lanes`` are (position, strength) corner points."""
    import numpy as np
    from widgets.spotify_visualizer.bar_computation import (
        lane_sample_positions, lane_strength_profile, shape_bar_profile,
    )
    mirrored = bool(values[keys.mirrored])
    nodes = [[float(x), float(y)] for x, y in values[keys.nodes]]
    notches, strengths = values[keys.notches[mirrored]], values[keys.lanes[mirrored]]
    bands = max(2, int(values[keys.bar_count]))
    silhouette = shape_bar_profile(np, nodes, bands, mirrored, float(values[keys.profile_floor]))
    driven = silhouette * lane_strength_profile(np, lane_sample_positions(np, bands, mirrored), notches, strengths)
    # The strength is linear between the lanes and held outside them, so its corner points draw it exactly.
    corners = sorted({0.0, 1.0, *(max(0.0, min(1.0, float(x))) for x, _label in notches)})
    weights = lane_strength_profile(np, np.asarray(corners, dtype="float32"), notches, strengths)
    return {"bars": [[float(a), float(b)] for a, b in zip(silhouette, driven)],
            "lanes": [[x, float(w)] for x, w in zip(corners, weights)]}


def shape_properties(keys: ShapeKeys, add: Callable[..., None], workspace: str, group: str,
                     label: str = "Silhouette") -> ShapeSpec:
    """The shape through the adapter's ``add(id, path, label, workspace, group, instrument, **extra)``: ONE shape
    instrument. Its row is the curve's nodes; the layout switch and both layouts' lanes and strengths are values it
    edits and the session carries (``instrument_only``). Returns the instrument's spec for the schema's ``shapes``."""
    low, high = node_limits()
    add(keys.mirrored, (keys.mirrored,), "Mirrored Layout", workspace, group, SWITCH, instrument_only=True,
        tooltip="On: the shape is mirrored around the centre (centre <-> edge). Off: a left-to-right profile.")
    add(keys.nodes, (keys.nodes,), label, workspace, group, SHAPE, priority=200,
        tooltip=f"The authored silhouette across the bars ({low} to {high} nodes) and the frequency lanes that "
                "drive it.")
    layouts = {}
    for mirrored in (False, True):
        name = "Mirrored" if mirrored else "Linear"
        notches, lanes = keys.notches[mirrored], keys.lanes[mirrored]
        add(notches, (notches,), f"Lane Positions ({name})", workspace, group, SHAPE, instrument_only=True)
        add(lanes, (lanes,), f"Lane Strengths ({name})", workspace, group, SHAPE, instrument_only=True)
        flag = "1" if mirrored else "0"
        layouts[mirrored] = ShapeLayout((notches,), (lanes,), name=name, low="Centre" if mirrored else "Low",
                                        high="Edge" if mirrored else "High", mirrored=mirrored,
                                        previous=f"{LANE_PREVIOUS}{flag}.", next=f"{LANE_NEXT}{flag}.")
    return ShapeSpec(keys.nodes, (layouts[False], layouts[True]), layout_switch=(keys.mirrored,),
                     node_limits=(low, high), lane_mode=SHAPE_BLEND, add=ADD_NODE, remove=REMOVE_NODE,
                     profile=partial(profile, keys), reads=(keys.bar_count, keys.profile_floor))


__all__ = [
    "ADD_NODE", "LANE_NEXT", "LANE_PREVIOUS", "REMOVE_NODE", "ShapeKeys", "added_node",
    "admit_colour", "admit_lanes", "admit_notches", "admit_nodes", "admit_shape", "canonical", "node_limits",
    "percent", "profile", "shape_properties", "structure_edit", "unit",
]

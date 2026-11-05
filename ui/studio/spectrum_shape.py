"""The Spectrum family's authored shape editor as Studio rows (mode-neutral over the family's key prefix).

Spectrum and Extruded Spectrum store the same shape (``<prefix>mirrored``, ``<prefix>shape_nodes``, the mirrored /
linear frequency boundaries and lane strengths) and Settings edits both through the same ``SpectrumShapeEditor``
rules. This module turns those rules into Studio properties, admission and structural edits for any family mode;
adapters pass their prefix and never copy them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ui.studio.schema import SCALAR, SWITCH, StudioAction, StudioProperty

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


def canonical(key: str):
    from core.settings.default_contract import require_canonical_default
    return require_canonical_default("widgets.spotify_visualizer")[key]


def node_limits() -> tuple[int, int]:
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES, _MIN_NODES
    return _MIN_NODES, _MAX_NODES


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
    """The shape editor's rules: 1..5 nodes of [x, y] in 0..1, kept in x order. A moved node stops at its
    neighbours (Settings re-sorts a node dragged past one; a Studio slider keeps addressing the same node)."""
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
    from ui.tabs.media.spectrum_shape_editor import interpolate_nodes
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


def row_label(keys: ShapeKeys, prop: StudioProperty, values: Mapping[str, Any]) -> str:
    """A boundary row is titled by the lane it currently bounds (lanes can be reordered)."""
    key = prop.path[0]
    if key in keys.notches.values() and len(prop.path) == 3:
        layout = "Mirrored" if key == keys.notches[True] else "Linear"
        return f"{values[key][prop.path[1]][1]} Boundary ({layout})"
    return prop.label


def add_node_action() -> StudioAction:
    _low, high = node_limits()
    return StudioAction(ADD_NODE, "Add Node", "plus", f"Add a node to the silhouette in its widest gap (at most {high}).")


def shape_properties(keys: ShapeKeys, add: Callable[..., None], workspace: str, group: str) -> None:
    """The shape editor's rows through the adapter's ``add(id, path, label, workspace, group, instrument, **extra)``:
    the layout switch, every node slot (both axes), and both layouts' boundaries and lane strengths (shown only
    under their layout)."""
    _low, high = node_limits()
    add(keys.mirrored, (keys.mirrored,), "Mirrored Layout", workspace, group, SWITCH,
        tooltip="On: the shape is mirrored around the centre (centre <-> edge). Off: a left-to-right profile.")
    for index in range(high):
        for axis, word in ((0, "Position"), (1, "Height")):
            remove = (StudioAction(f"{REMOVE_NODE}{index}", f"Remove Node {index + 1}", "minus",
                                   "Remove this node (the shape keeps at least one)."),) if axis == 0 else ()
            add(f"{keys.nodes}.{index}.{axis}", (keys.nodes, index, axis), f"Node {index + 1} {word}", workspace,
                group, SCALAR, minimum=0.0, maximum=1.0, decimals=3, priority=200 + 2 * index + axis,
                actions=remove,
                tooltip="A control node of the authored silhouette (across the bars, then its height). A node "
                        "stops at its neighbours; Add Node adds one in the widest gap.")
    for mirrored in (True, False):
        layout = "Mirrored" if mirrored else "Linear"
        notches, lanes = keys.notches[mirrored], keys.lanes[mirrored]
        flag = "1" if mirrored else "0"
        for index, (_x, lane) in enumerate(canonical(notches)):
            swaps = (StudioAction(f"{LANE_PREVIOUS}{flag}.{index}", "Swap With Previous Lane", "chevron-left",
                                  "Exchange this lane with the one before it (the boundaries stay)."),
                     StudioAction(f"{LANE_NEXT}{flag}.{index}", "Swap With Next Lane", "chevron-right",
                                  "Exchange this lane with the one after it (the boundaries stay)."))
            add(f"{notches}.{index}", (notches, index, 0), f"{lane} Boundary ({layout})", workspace, group, SCALAR,
                minimum=0.0, maximum=1.0, decimals=3, priority=300 + index, when=((keys.mirrored, (mirrored,)),),
                actions=swaps,
                tooltip="Where this frequency lane sits across the bars. A boundary stops at its neighbours.")
        for index, lane in enumerate(canonical(lanes)):
            add(f"{lanes}.{lane}", (lanes, lane), f"{lane} Strength ({layout})", workspace, group, SCALAR,
                minimum=0.0, maximum=1.0, decimals=2, priority=320 + index, when=((keys.mirrored, (mirrored,)),),
                tooltip="How strongly this lane drives its bars.")


__all__ = [
    "ADD_NODE", "LANE_NEXT", "LANE_PREVIOUS", "REMOVE_NODE", "ShapeKeys", "add_node_action", "added_node",
    "admit_colour", "admit_lanes", "admit_notches", "admit_nodes", "admit_shape", "canonical", "node_limits",
    "percent", "row_label", "shape_properties", "structure_edit", "unit",
]

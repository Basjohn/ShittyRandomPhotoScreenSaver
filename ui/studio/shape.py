"""The shared shape instrument: a node curve and its frequency lanes edited on one canvas (mode-neutral).

A mode names the instrument in its schema (``ShapeSpec`` on a ``SHAPE`` property); this module is everything the
shell's canvas needs from Python and nothing mode-specific:

* **The display model** (``ShapeInstrument.view``): the stored nodes, lanes and layout as they are, the curve sampled
  by the production interpolation (``utils.curve_nodes.interpolate_nodes``, the function the engine and the terrain
  baker sample), and the mode's own preview of what the shape does (``ShapeSpec.profile``). The canvas draws these
  numbers; it interpolates nothing itself.
* **The gestures** (``StudioShapes``): press, the held pointer position applied once per frame, release. A dragged
  node or lane goes where the pointer is and the list is kept in order, as Settings' shape editor did; every
  candidate then passes the schema's ``admit`` (the mode's rules: counts, ranges, pinned lanes) through the edit
  session, so the canvas always shows the admitted value. Release commits once (one save, one undo entry).

Node add at the widest gap, node removal and lane swaps are not here: they are the adapter's ``structure_edit``
actions the spec names, run by the bridge's ``runAction`` like any other structural edit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from ui.studio.schema import SHAPE, ShapeLayout, ShapeSpec, StudioProperty, StudioSchema
from ui.studio.session import StudioEditSession, read_path

NODE, LANE, STRENGTH, ADD = "node", "lane", "strength", "add"
PARTS = frozenset({NODE, LANE, STRENGTH, ADD})
CURVE_SAMPLES = 161              # the drawn curve: the production interpolation at this many points along the axis
POSITION_DECIMALS = 4            # a dragged position, stored to a tenth of a pixel of a 1000 px canvas
STRENGTH_DECIMALS = 3
STEP = 0.01                      # one keyboard step (Shift: ten)


def _unit(value: Any, decimals: int) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("a shape value must be a finite number")
    return round(max(0.0, min(1.0, number)), decimals)


def _placed(items: list, item: list, origin: int) -> tuple[list, int]:
    """``items`` (in x order) with ``item`` put where its x belongs, and its index. Equal x keeps the order the
    items had: an item that came from ``origin`` stays after those that were before it."""
    at = sum(1 for index, other in enumerate(items)
             if other[0] < item[0] or (other[0] == item[0] and index < origin))
    return items[:at] + [item] + items[at:], at


class ShapeInstrument:
    """One SHAPE row: what its canvas shows and the candidate values its gestures ask for."""

    def __init__(self, prop: StudioProperty, spec: ShapeSpec, layout_switch: str = "") -> None:
        self.prop = prop
        self.spec = spec
        self.layout_switch = layout_switch       # id of the property holding the layout choice ("": one layout)
        # Every key whose change re-shows the canvas.
        self.keys = frozenset({prop.path[0]}) | spec.keys

    # ------------------------------------------------------------------ stored state
    def layout(self, values: Mapping[str, Any]) -> ShapeLayout:
        spec = self.spec
        if spec.layout_switch is None:
            return spec.layouts[0]
        return spec.layouts[1 if bool(read_path(values, spec.layout_switch)) else 0]

    def nodes(self, values: Mapping[str, Any]) -> list:
        return [[float(x), float(y)] for x, y in read_path(values, self.prop.path)]

    def notches(self, values: Mapping[str, Any]) -> list:
        return [[float(x), str(label)] for x, label in read_path(values, self.layout(values).notches)]

    def strengths(self, values: Mapping[str, Any]) -> dict:
        return {str(label): float(value) for label, value in read_path(values, self.layout(values).lanes).items()}

    # ------------------------------------------------------------------ display model
    def view(self, values: Mapping[str, Any], gesture: "ShapeGesture | None" = None) -> dict:
        """Everything the canvas draws, as plain data."""
        from utils.curve_nodes import interpolate_nodes
        spec, layout = self.spec, self.layout(values)
        nodes, notches, strengths = self.nodes(values), self.notches(values), self.strengths(values)
        low, high = spec.node_limits
        profile = dict(spec.profile(values) or {}) if spec.profile is not None else {}
        view = {
            "nodes": nodes,
            "curve": [round(float(v), 5) for v in interpolate_nodes(nodes, CURVE_SAMPLES)],
            "lanes": [{"label": label, "x": x, "strength": float(strengths.get(label, 0.0)),
                       "pinned": index < spec.pinned_lanes} for index, (x, label) in enumerate(notches)],
            "mirrored": bool(layout.mirrored), "laneMode": spec.lane_mode,
            "layouts": [item.name for item in spec.layouts] if self.layout_switch else [],
            "layoutSwitch": self.layout_switch,
            "bars": [[round(float(a), 5), round(float(b), 5)] for a, b in profile.get("bars", ())],
            "laneProfile": [[round(float(x), 5), round(float(w), 5)] for x, w in profile.get("lanes", ())],
            "low": layout.low, "high": layout.high, "valueLabel": spec.value_label,
            "nodeNoun": spec.node_noun, "laneNoun": spec.lane_noun,
            "minNodes": int(low), "maxNodes": int(high),
            "canAdd": len(nodes) < high, "canRemove": len(nodes) > low,
            "addAction": spec.add, "removeAction": spec.remove,
            "previousAction": layout.previous, "nextAction": layout.next,
        }
        if gesture is not None and gesture.property_id == self.prop.id:
            view["active"] = {"part": gesture.part, "index": gesture.index(self, values)}
        return view

    # ------------------------------------------------------------------ candidates (admitted by the session)
    def moved_node(self, values: Mapping[str, Any], index: int, x: Any = None, y: Any = None
                   ) -> tuple[list, int] | None:
        """The nodes with node ``index`` at (x, y), in order, and its index there. An axis left None keeps its
        stored value exactly."""
        nodes = self.nodes(values)
        if not 0 <= index < len(nodes):
            return None
        node = [nodes[index][0] if x is None else _unit(x, POSITION_DECIMALS),
                nodes[index][1] if y is None else _unit(y, POSITION_DECIMALS)]
        return _placed(nodes[:index] + nodes[index + 1:], node, index)

    def added_node(self, values: Mapping[str, Any], x: Any, y: Any) -> tuple[list, int]:
        nodes = self.nodes(values)
        return _placed(nodes, [_unit(x, POSITION_DECIMALS), _unit(y, POSITION_DECIMALS)], len(nodes))

    def moved_lane(self, values: Mapping[str, Any], label: str, x: Any) -> list | None:
        """The lanes with ``label``'s at ``x``, in order. A pinned lane does not move and nothing is put before one."""
        notches = self.notches(values)
        index = next((i for i, (_x, name) in enumerate(notches) if name == label), -1)
        pinned = self.spec.pinned_lanes
        if index < pinned:
            return None
        position = _unit(x, POSITION_DECIMALS)
        if pinned:
            position = max(position, notches[pinned - 1][0])
        placed, at = _placed(notches[:index] + notches[index + 1:], [position, label], index)
        if at < pinned:
            placed.insert(pinned, placed.pop(at))
        return placed

    def lane_index(self, values: Mapping[str, Any], label: str) -> int:
        return next((i for i, (_x, name) in enumerate(self.notches(values)) if name == label), -1)


@dataclass
class ShapeGesture:
    """The one live gesture: which part of which instrument the pointer holds."""
    property_id: str
    part: str
    node: int = -1               # NODE / ADD (once the node exists): its current index
    label: str = ""              # LANE / STRENGTH: the lane, by name (its index moves when lanes pass each other)

    def index(self, instrument: ShapeInstrument, values: Mapping[str, Any]) -> int:
        if self.part in (LANE, STRENGTH):
            return instrument.lane_index(values, self.label)
        return self.node


class StudioShapes:
    """Every SHAPE instrument of one Studio session and its live gesture."""

    def __init__(self, schema: StudioSchema, session: StudioEditSession) -> None:
        self._session = session
        self._instruments = {}
        for spec in schema.shapes:
            switch = "" if spec.layout_switch is None else next(
                (prop.id for prop in schema.properties if tuple(prop.path) == tuple(spec.layout_switch)), "")
            self._instruments[spec.property] = ShapeInstrument(schema.find(spec.property), spec, switch)
        self.gesture: ShapeGesture | None = None
        self.previews = 0                    # previews applied (tests: one per frame)

    def __contains__(self, property_id: object) -> bool:
        return property_id in self._instruments

    def instrument(self, property_id: str) -> ShapeInstrument:
        return self._instruments[property_id]

    def keys(self, property_id: str) -> frozenset[str]:
        return self._instruments[property_id].keys

    def view(self, property_id: str, values: Mapping[str, Any]) -> dict:
        return self._instruments[property_id].view(values, self.gesture)

    # ------------------------------------------------------------------ labels
    def _label(self, instrument: ShapeInstrument, part: str, label: str = "") -> str:
        node, lane = instrument.spec.node_noun, instrument.spec.lane_noun
        return {NODE: f"Move {node}", ADD: f"Add {node}", LANE: f"Move {label} {lane}",
                STRENGTH: f"Set {label} {lane} Strength"}[part]

    # ------------------------------------------------------------------ the pointer gesture
    def press(self, property_id: str, part: str, index: int) -> bool:
        """The pointer took hold of a part (``index``: the node or lane; ignored for ADD). Nothing changes yet."""
        instrument = self._instruments.get(property_id)
        if instrument is None or part not in PARTS:
            return False
        values = self._session.values
        gesture = ShapeGesture(property_id, part)
        if part == NODE:
            if not 0 <= index < len(instrument.nodes(values)):
                return False
            gesture.node = int(index)
        elif part in (LANE, STRENGTH):
            notches = instrument.notches(values)
            if not 0 <= index < len(notches) or (part == LANE and index < instrument.spec.pinned_lanes):
                return False
            gesture.label = notches[index][1]
        self._session.begin_gesture(self._label(instrument, part, gesture.label))
        self.gesture = gesture
        return True

    def drag(self, x: float, y: float) -> None:
        """The held pointer position (axis position, value), applied as one admitted preview."""
        gesture = self.gesture
        if gesture is None:
            return
        if not self._session.gesture_active:         # the session's gesture was ended or cancelled elsewhere
            self.gesture = None
            return
        instrument, session = self._instruments[gesture.property_id], self._session
        values, path = session.values, instrument.prop.path
        self.previews += 1
        # The gesture names the node's new index before the preview: the session's change is what re-shows the canvas.
        if gesture.part == ADD and gesture.node < 0:
            before = len(instrument.nodes(values))
            if before >= instrument.spec.node_limits[1]:
                return                               # a full curve: nothing to ask the mode's admission for
            candidate, gesture.node = instrument.added_node(values, x, y)
            if len(session.preview(path, candidate)) != before + 1:
                gesture.node = -1                    # the mode refused it
            return
        if gesture.part in (NODE, ADD):
            moved = instrument.moved_node(values, gesture.node, x, y)
            if moved is not None:
                gesture.node = moved[1]
                session.preview(path, moved[0])
            return
        layout = instrument.layout(values)
        if gesture.part == LANE:
            moved = instrument.moved_lane(values, gesture.label, x)
            if moved is not None:
                session.preview(layout.notches, moved)
        elif gesture.part == STRENGTH:
            session.preview((*layout.lanes, gesture.label), _unit(y, STRENGTH_DECIMALS))

    def release(self) -> bool:
        """The gesture ends: one commit (and one undo entry) when anything changed."""
        if self.gesture is None:
            return False
        self.gesture = None
        return self._session.end_gesture()

    def cancel(self) -> None:
        if self.gesture is not None:
            self.gesture = None
            self._session.cancel_gesture()

    # ------------------------------------------------------------------ exact entry and keyboard steps
    def element(self, property_id: str, part: str, index: int) -> tuple[float, float] | None:
        """(axis position, value) of a node, or (position, strength) of a lane; None when there is none."""
        instrument = self._instruments.get(property_id)
        if instrument is None:
            return None
        values = self._session.values
        if part == NODE:
            nodes = instrument.nodes(values)
            return tuple(nodes[index]) if 0 <= index < len(nodes) else None
        notches = instrument.notches(values)
        if not 0 <= index < len(notches):
            return None
        return notches[index][0], instrument.strengths(values).get(notches[index][1], 0.0)

    def set(self, property_id: str, part: str, index: int, x: float | None, y: float | None) -> int:
        """An exact value or a keyboard step: the element's position and / or value, as one committed edit.
        ``part`` is NODE or LANE (a lane's value is its strength). Returns the element's index afterwards (it moves
        when the element passes a neighbour), or -1 when there is no such element."""
        current = self.element(property_id, part, index)
        if current is None or part not in (NODE, LANE):
            return -1
        instrument, session = self._instruments[property_id], self._session
        values = session.values
        self.gesture = None
        if part == NODE:
            moved = instrument.moved_node(values, index, x, y)
            session.begin_gesture(f"Set {instrument.spec.node_noun}")
            session.preview(instrument.prop.path, moved[0])
            session.end_gesture()
            return moved[1]
        layout, label = instrument.layout(values), instrument.notches(values)[index][1]
        session.begin_gesture(f"Set {label} {instrument.spec.lane_noun}")
        if x is not None:
            moved = instrument.moved_lane(values, label, x)
            if moved is not None:
                session.preview(layout.notches, moved)
        if y is not None:
            session.preview((*layout.lanes, label), _unit(y, STRENGTH_DECIMALS))
        session.end_gesture()
        return instrument.lane_index(session.values, label)


def is_row(prop: StudioProperty) -> bool:
    """A SHAPE property drawn as an instrument (a carried one only holds a value the instrument edits)."""
    return prop.instrument == SHAPE and not prop.instrument_only


__all__ = ["ADD", "CURVE_SAMPLES", "LANE", "NODE", "STEP", "STRENGTH", "ShapeGesture", "ShapeInstrument",
           "StudioShapes", "is_row"]

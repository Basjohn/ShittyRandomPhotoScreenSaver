"""The Studio's shared heightfield brush instrument (mode-neutral; no Qt).

A mode that authors a heightfield (Neon Lake's terrain) offers a ``BrushTarget`` (``StudioModeAdapter.brush_target``):
the record's settings key and how a viewport point lands on the scene (``pick``: presented-frame pixels -> grid uv on
the drawn ground, through the mode's production camera) and how the brush's footprint is drawn back over it
(``footprint``). How a stroke paints is ``rendering.gl_programs.heightfield_brush`` (one owner).

Pointer input is batched like every other Studio drag: a press, moves and the hover only hold the newest pointer
points; ``flush`` (the controller's frame start) picks them, continues the stroke along all of them in order (the
path, not the event rate, decides the result) and previews the record once. Release flushes and commits once: one
save through the canonical store, one undo entry. Cancel (Escape, a lost window) restores the record.

While a stroke runs, points are picked on the ground as it was when the stroke began: picking on the land being
raised would land each next point on the new slope's face, nearer the camera, and a stroke would climb toward the
viewer as a wall.

A target may let its grid grow under the brush (``BrushTarget.grow``: Neon Lake's land past its authored grid). The
stroke then carries on over the grown record with its path re-mapped (``_placed``), still one preview a frame and
one commit: the growth and the paint are one undo step. Land past the largest grid's reach is refused out loud:
``refused`` while the pointer is over it (the cursor's state) and ``refusals`` for the points a stroke dropped
there (the controller's one-line notice).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from rendering.gl_programs.heightfield_brush import (
    MODES, RADIUS_RANGE, BrushSettings, HeightfieldStroke, brush_reach,
)

Point = tuple[float, float]
# (presented-frame size, the live card's world extent, the card style): what a pick projects through.
Geometry = tuple[tuple[float, float], Any, Any]


@dataclass(frozen=True)
class BrushTarget:
    """What a mode hands the brush. ``pick(frame, values, point, geometry)`` returns the grid uv under ``point`` on the
    drawn ground (None on the sky; outside 0..1 where the ground lies past the stored grid);
    ``footprint(frame, values, uv, rings, geometry)`` returns one screen polyline (presented-frame pixels) per ring
    radius (in brush radius units, ``heightfield_brush.RADIUS_RANGE``), resting on the drawn ground.

    A target whose grid can grow under the brush also gives ``grow(record, uv, reach)``: the record grown to hold a
    brush touching ``reach`` (grid uv) round ``uv`` with the whole cells added before its first column and row,
    ``(record, left, front)``; the same record and zeros when it already fits or cannot grow further; None when
    ``uv`` itself is out of the largest grid's reach. ``reachable(size, uv)`` answers that last question alone for a
    grid of ``size`` cells a side (the hover's check: nothing grows), and ``refusal`` is the one-line notice for it.
    Without ``grow`` only the stored grid is paintable."""

    key: str
    label: str
    pick: Callable[[Any, Mapping[str, Any], Point, Geometry], Point | None]
    footprint: Callable[[Any, Mapping[str, Any], Point, tuple[float, ...], Geometry], list]
    grow: Callable[[Mapping[str, Any], Point, float], tuple[Mapping[str, Any], int, int] | None] | None = None
    reachable: Callable[[int, Point], bool] | None = None
    refusal: str = ""


class StudioBrush:
    """One Studio's brush: the tool settings, the held pointer points and the stroke of the current gesture.

    ``session`` is the Studio's ``StudioEditSession``; ``scene()`` returns ``(frame, values, geometry)`` of the frame on
    screen (None while nothing is presented); ``request_frame()`` asks for a frame start (where ``flush`` runs)."""

    def __init__(self, target: BrushTarget, session, scene: Callable[[], tuple | None],
                 request_frame: Callable[[], None]) -> None:
        self.target = target
        self._session = session
        self._scene = scene
        self._request_frame = request_frame
        self.settings = BrushSettings()
        self.active = False
        self._points: list[Point] = []
        self._pressed = False
        self._stroke: HeightfieldStroke | None = None
        self._base: dict | None = None    # the values the stroke picks on (the record as the stroke began)
        # Where a point picked on that record lies in the stroke's own (it may have grown): uv * scale + offset.
        self._map: tuple[float, float, float] = (1.0, 0.0, 0.0)
        self._full = False               # the stroke's grid cannot grow further
        self._changed = False
        self._hover: Point | None = None
        self._hover_dirty = False
        self.cursor: list = []           # the footprint over the hovered point (screen polylines)
        self.refused = False             # the pointer is over land past the largest grid's reach
        self.refusals = 0                # presses and stroke points refused there
        self.previews = 0                # previews applied (at most one per frame start while painting)
        self.pointer_events = 0          # pointer points handed over (any number per frame)

    # ------------------------------------------------------------ tool state
    @property
    def modes(self) -> tuple[str, ...]:
        return MODES

    def set_value(self, name: str, value: Any) -> bool:
        settings = self.settings.admitted(str(name), value)
        if settings == self.settings:
            return False
        self.settings = settings
        self._hover_dirty = self._hover is not None
        if self._hover_dirty:
            self._request_frame()
        return True

    def set_active(self, active: bool) -> None:
        active = bool(active)
        if active == self.active:
            return
        if not active:
            self.cancel()
            self.hover(None)
        self.active = active

    @property
    def painting(self) -> bool:
        return self._pressed

    # ------------------------------------------------------------ pointer
    def press(self, point: Point) -> None:
        """Begin a stroke at ``point`` (presented-frame pixels); nothing is painted until the next frame start."""
        if not self.active:
            return
        if self._pressed:
            self.release()
        self._pressed = True
        self._end_stroke()
        self._changed = False
        self._points = [(float(point[0]), float(point[1]))]
        self._hover = self._points[0]
        self._hover_dirty = True
        self.pointer_events += 1
        self._request_frame()

    def move(self, point: Point) -> None:
        self.pointer_events += 1
        point = (float(point[0]), float(point[1]))
        self._hover, self._hover_dirty = point, True
        if self._pressed:
            self._points.append(point)
        self._request_frame()

    def hover(self, point: Point | None) -> None:
        self._hover = None if point is None else (float(point[0]), float(point[1]))
        self._hover_dirty = True
        if self._hover is None:
            self.cursor = []
            self.refused = False
        else:
            self._request_frame()

    def _end_stroke(self) -> None:
        self._stroke = None
        self._base = None
        self._map = (1.0, 0.0, 0.0)
        self._full = False

    def release(self) -> bool:
        """Apply the held points and commit the stroke once. Returns True when something was saved."""
        if not self._pressed:
            return False
        self.flush()
        self._pressed = False
        self._end_stroke()
        self._points = []
        if not self._changed:
            if self._session.gesture_active:
                self._session.cancel_gesture()
            return False
        self._changed = False
        return bool(self._session.end_gesture())

    def cancel(self) -> None:
        """Drop the stroke: the record returns to what it was before the press."""
        if not self._pressed:
            return
        self._pressed = False
        self._end_stroke()
        self._points = []
        if self._changed:
            self._session.cancel_gesture()
        self._changed = False

    # ------------------------------------------------------------ frame start
    def flush(self) -> None:
        """Frame start: pick the held points on the frame on screen, continue the stroke along all of them and
        preview the record once; re-project the cursor if the pointer or a setting moved."""
        scene = None
        if self._pressed and self._points:
            scene = self._scene()
            points, self._points = self._points, []
            if scene is not None:
                self._paint(scene, points)
        if self._hover_dirty:
            self._hover_dirty = False
            scene = scene or self._scene()
            self.cursor = self._footprint(scene) if scene is not None and self._hover is not None else []

    def _picked_on(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        """The values a pick reads: during a stroke, the record as the stroke began."""
        if self._base is None:
            return values
        return {**values, self.target.key: self._base}

    def _paint(self, scene, points: list[Point]) -> None:
        frame, values, geometry = scene
        if self._base is None:
            self._base = values[self.target.key]
        values = self._picked_on(values)
        moved = False
        for point in points:
            uv = self.target.pick(frame, values, point, geometry)
            if uv is None:
                continue                                    # over the sky: the stroke waits
            if self._stroke is None:
                self._stroke = HeightfieldStroke(self._session.values[self.target.key], self.settings)
            uv = self._placed(uv)
            if uv is None:
                self.refusals += 1                          # past the largest grid's reach: the stroke waits
                continue
            self._stroke.to(uv)                             # the first point presses
            moved = True
        if not moved or self._stroke is None:
            return
        record = self._stroke.record()
        if record == self._session.values[self.target.key] and not self._changed:
            return
        if not self._session.gesture_active:
            self._session.begin_gesture(f"Paint {self.target.label} ({self.settings.mode})")
        self._session.preview((self.target.key,), record)
        self._changed = True
        self.previews += 1

    def _placed(self, uv: Point) -> Point | None:
        """Where a point picked on the stroke's first record lies in the stroke's own, growing that record first when
        the brush would reach past its edge (the path so far is carried along); None past the largest grid's reach."""
        stroke = self._stroke
        scale, du, dv = self._map
        u, v = uv[0] * scale + du, uv[1] * scale + dv
        reach = stroke.reach()
        inside = 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0
        if reach <= u <= 1.0 - reach and reach <= v <= 1.0 - reach:
            return u, v
        if self.target.grow is None or self._full:
            return (u, v) if inside else None
        grown = self.target.grow(stroke.record(), (u, v), reach)
        if grown is None:
            return None
        record, left, front = grown
        old, new = stroke.size - 1, int(record["size"]) - 1
        if new == old:
            self._full = True                               # at the largest grid: the footprint is clipped
            return (u, v) if inside else None
        stroke.regrid(record, left, front)
        ratio = old / new
        self._map = (scale * ratio, du * ratio + left / new, dv * ratio + front / new)
        return (u * old + left) / new, (v * old + front) / new

    def _reachable(self, values: Mapping[str, Any], uv: Point) -> bool:
        """Whether a stroke could paint at ``uv`` (picked on ``values``' record)."""
        if self._stroke is not None:
            scale, du, dv = self._map
            uv, size = (uv[0] * scale + du, uv[1] * scale + dv), self._stroke.size
        else:
            size = int(values[self.target.key]["size"])
        if 0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 1.0:
            return True
        return self.target.reachable is not None and not self._full and bool(self.target.reachable(size, uv))

    def _footprint(self, scene) -> list:
        frame, values, geometry = scene
        values = self._picked_on(values)
        uv = self.target.pick(frame, values, self._hover, geometry)
        self.refused = uv is not None and not self._reachable(values, uv)
        if uv is None:
            return []
        radius = self.settings.radius
        rings = [radius * brush_reach(self.settings.falloff)]
        core = radius * (1.0 - self.settings.falloff)
        if core > 1e-6:
            rings.append(core)
        return self.target.footprint(frame, values, uv, tuple(rings), geometry)

    def as_map(self) -> dict:
        return {"active": self.active, "painting": self._pressed, "modes": list(MODES), "label": self.target.label,
                "refused": self.refused, "radius_range": list(RADIUS_RANGE), **self.settings.as_map()}


__all__ = ["BrushTarget", "Geometry", "StudioBrush"]

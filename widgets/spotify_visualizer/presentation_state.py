"""Controller-owned presentation-neutral visualizer presentation state (H).

The authored logical inputs live in ``VisualizerLogicalTickState``; this is the
symmetric owner for the pure renderer/presentation-only config the legacy adapter
historically read straight off ``SpotifyVisualizerWidget`` fields (bar/line/glow
colours, glow sizing/reactivity, per-line styling, ghost-line toggles, rainbow,
Bubble gradient/outline/specular colours and Bubble/DevCurve-independent styling).

Design (mirrors the logical-state extraction):

- ``VisualizerRuntimeController`` owns exactly one of these per generation.
- Nothing here is an authored logical input: the mode ``*FrameRuntime.resolve`` /
  DevCurve field solve never read this object. It is consumed only when composing
  the immutable renderer parameters (``mode_state.parameters`` / common ``style``)
  for the Quick render snapshot.
- It is a sparse config holder: the legacy adapter's extras builders read each
  field with a canonical default, so an unset field is not an error. The neutral
  owner therefore stores exactly what canonical settings resolved, and the widget
  (pre-cutover) delegates its presentation fields here so one storage serves both
  the legacy compositor and the widget-free Quick capture.

No QML/QQuickItem/QScreen/render-thread object ever enters this state. This is an
ownership move; renderer values, defaults and semantics are unchanged.
"""

from __future__ import annotations

from typing import Any


class VisualizerPresentationState:
    """Single presentation-neutral host for one generation's renderer config."""

    def __init__(self, controller: Any) -> None:
        object.__setattr__(self, "_controller", controller)

    @property
    def runtime_controller(self) -> Any:
        return self._controller


__all__ = ["VisualizerPresentationState"]

"""The contract a visualizer mode implements to be edited in the Studio.

Everything mode-specific lives behind this interface: which values exist and how
to author them (schema), how the mode's real logical model turns inputs and values
into an immutable frame (evaluator), which preview inputs exist (fixtures) and how
the mode's production renderer draws that frame on the Quick render thread.

The Studio never assumes a framed 3D scene. What the viewport offers is declared by the
adapter through ``capabilities()`` (see ``StudioCapabilities``): a flat 2D mode (Spectrum,
Oscilloscope, Bubble, ...) declares no camera and no scene handles, and the shell then shows
no navigation, view readout, Keep View / Reset or handle overlay and never calls
``navigation()`` / ``scene_handles()``. Inspector extras (material/starting-point tiles,
lifetime timelines, schematic cards, signal traces, the response editor) are optional parts of
the schema: an empty tuple / ``None`` simply hides them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from ui.studio.schema import Path, SceneObject, StudioSchema


# Fixture kinds, in the order the transport presents them.
REFERENCE = "reference"    # a held Quiet / Mid / Peak reference state
SYNTHETIC = "synthetic"    # an authored, independently varying test input
RECORDED = "recorded"      # a project recording replayed through production analysis


@dataclass(frozen=True)
class StudioFixture:
    id: str
    label: str
    kind: str
    duration: float
    description: str = ""


@dataclass(frozen=True)
class RenderCard:
    """What a render-thread renderer receives from the viewport node for one draw."""

    viewport: tuple[int, int, int, int]       # render-target pixels
    logical_size: tuple[float, float]         # item size in logical (device-independent) pixels
    matrix_values: tuple[float, ...]          # item pixels -> clip space (Qt column-major)
    quad_vao: int                             # a unit quad for item-space composition
    extent: tuple[float, float] | None = None # the world extent presented (letterboxed), when framed
    style: tuple = ()                         # the framing's (key, value) presentation style (e.g. card chrome)


@dataclass(frozen=True)
class StudioCapabilities:
    """What a mode's Studio viewport supports. The default is the most basic: a live 2D preview of
    the production renderer and nothing else.

    ``viewport``: the mode draws a live preview (False: inspector-only Studio; no renderer is created).
    ``camera``: the mode has a navigable camera; ``navigation()`` maps orbit / zoom / dolly / pan.
    ``handles``: ``scene_handles()`` supplies direct-manipulation handles over the preview.
    ``objects``: the mode has scene objects (``scene_objects()``) listed beside the viewport (False: no list; the
    viewport takes its width).
    ``brush``: ``brush_target()`` names a heightfield the shared brush instrument paints on the preview
    (``ui.studio.brush``)."""
    viewport: bool = True
    camera: bool = False
    handles: bool = False
    objects: bool = True
    brush: bool = False

    def as_map(self) -> dict:
        return {"viewport": self.viewport, "camera": self.camera and self.viewport,
                "handles": self.handles and self.viewport, "objects": self.objects,
                "brush": self.brush and self.viewport}


@dataclass(frozen=True)
class StudioPreview:
    """One small render the Studio asks the mode's renderer for (a tile or a rendered card).

    ``frame`` is drawn at ``logical`` item size (twice that in pixels) presenting ``extent``/``style``,
    then cropped to ``crop`` (normalised x, y, w, h, origin top-left)."""
    frame: Any
    extent: tuple[float, float] | None
    style: tuple = ()
    logical: tuple[float, float] = (96.0, 64.0)
    crop: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)


class StudioEvaluator(Protocol):
    """Deterministic: the same fixture, values and time always yield the same frame."""

    def fixtures(self) -> tuple[StudioFixture, ...]: ...

    def select(self, fixture_id: str) -> StudioFixture: ...

    @property
    def fixture(self) -> StudioFixture: ...

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True,
                 revision: Any = None) -> Any:
        """Return an immutable render frame for ``time`` seconds into the selected fixture.

        ``exact=False`` permits a cheap live-gesture approximation; exact results must be
        identical for identical fixture, values and time."""

    def release(self) -> None: ...


class StudioRenderer(Protocol):
    """Lives on the Quick render thread; owns its GL resources in that context only."""

    def prepare(self, card: RenderCard, frame: Any) -> bool:
        """One bounded preparation step; True once the frame can be drawn."""

    def render(self, card: RenderCard, frame: Any) -> None: ...

    def release(self) -> None: ...


class StudioModeAdapter(ABC):
    """One mode's Studio plug-in. The framework never imports a concrete mode."""

    mode_id: str = ""
    title: str = ""

    @abstractmethod
    def schema(self) -> StudioSchema: ...

    @abstractmethod
    def scene_objects(self, values: Mapping[str, Any]) -> tuple[SceneObject, ...]: ...

    @abstractmethod
    def create_evaluator(self) -> StudioEvaluator: ...

    @abstractmethod
    def create_renderer(self) -> StudioRenderer:
        """Called on the render thread with the scene-graph context current (only when the
        capabilities declare a viewport)."""

    def capabilities(self) -> StudioCapabilities:
        """What the viewport supports; override to declare a camera and/or scene handles."""
        return StudioCapabilities()

    def orbit_paths(self) -> tuple[Path, Path, tuple[float, float], tuple[float, float]] | None:
        """(horizontal path, vertical path, horizontal bounds, vertical bounds) for viewport
        orbit drags, or None when the mode has no orbit pose."""
        nav = self.navigation()
        if nav is None or nav.orbit_h is None or nav.orbit_v is None:
            return None
        return (nav.orbit_h.key,), (nav.orbit_v.key,), nav.orbit_h.bounds, nav.orbit_v.bounds

    def navigation(self) -> "StudioNavigation | None":
        """Viewport navigation axes (orbit, zoom, dolly, pan) bound to the mode's camera values.
        Consulted only when ``capabilities().camera`` is True."""
        return None

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        return ()

    def framings(self, card_extent: tuple[float, float] | None,
                 card_style: dict | None = None) -> tuple["StudioFraming", ...]:
        """Presentation frames the viewport can show, first = default. ``card_extent`` is the live
        card's world extent and ``card_style`` its chrome when the store knows them. Empty: fill the
        viewport (no letterbox)."""
        return ()

    def set_object_visible(self, values: Mapping[str, Any], object_id: str, visible: bool):
        """(path, value) edit that shows/hides a scene object, or None when it cannot be toggled."""
        return None

    def add_object(self, values: Mapping[str, Any]):
        """(path, value) edit that adds one scene object, or None at capacity / unsupported."""
        return None

    def brush_target(self):
        """The heightfield the shared brush paints (``ui.studio.brush.BrushTarget``), consulted only when
        ``capabilities().brush``."""
        return None

    def structure_edit(self, action_id: str, values: Mapping[str, Any]):
        """(undo label, {path: value}) for a schema ``StudioAction`` (add / remove / reorder a list element) under
        ``values``, or None while it is not admissible (e.g. a node list at its maximum). Applied as ONE undoable
        edit through the session, so the schema's ``admit`` and the canonical save path see it like any edit."""
        return None

    def apply_preset(self, group: str, preset_id: str, baseline: Mapping[str, Any],
                     values: Mapping[str, Any]) -> dict:
        """{path: value} changes for a group preset (relative to ``baseline``: reversible)."""
        return {}

    def preset_preview(self, group: str, preset_id: str, values: Mapping[str, Any],
                       object_id: str = "") -> "StudioPreview | None":
        """The tile render for a starting point (``values`` already has it applied; ``object_id`` is the
        selected scene object), drawn once by the mode's renderer; None keeps the swatch. Consulted
        only with a viewport, after commits while the tiles are on screen (never per frame)."""
        return None

    def card_preview(self, group: str, values: Mapping[str, Any], endpoint: int,
                     framing: "StudioFraming | None", evaluator: Any = None) -> "StudioPreview | None":
        """A rendered card for a group whose ``CardSpec.rendered`` is set: the scene on screen (``evaluator``
        is the Studio's evaluator at the instant shown; ``values`` the current values) with the group's
        Quiet/Peak pairs held at ``endpoint`` (0 quiet, 1 peak), through the production renderer at the live
        ``framing``. Same rules as tiles: once per commit while visible, never per frame."""
        return None

    def scene_handles(self, frame: Any, values: Mapping[str, Any], object_id: str,
                      size: tuple[float, float], extent, style) -> dict:
        """Direct-manipulation handles for the selected object, projected through the mode's real camera
        (2D modes: through their own item mapping). Consulted only when ``capabilities().handles``.

        Returns {"outline": [[x, y], ...], "handles": [{"id", "property", "endpoint", "axis" ("x"|"y"),
        "x", "y", "perPixel", "label"}]} in presented-frame pixels (origin top-left); ``perPixel`` is the value change per
        screen pixel of drag along ``axis`` (y grows downwards). ``axis`` "xy" is a combined move gizmo:
        ``property``/``perPixel`` follow x and ``propertyY``/``perPixelY`` follow y, in one undoable edit."""
        return {"outline": [], "handles": []}

    def release(self) -> None:
        """Drop anything the adapter itself holds (e.g. a private preview evaluator) when the Studio
        closes or switches mode."""

    def default_framing(self) -> str:
        """The framing id the viewport opens on ("" = the first of ``framings``)."""
        return ""

    def default_fixture(self, evaluator) -> str | None:
        """The preview input the transport starts on (None: the evaluator's own default)."""
        return None


@dataclass(frozen=True)
class NavAxis:
    key: str
    bounds: tuple[float, float]
    label: str = ""
    units: str = ""


@dataclass(frozen=True)
class StudioNavigation:
    """How viewport gestures map onto the mode's own camera values, and how each may be saved.

    ``orbit_*``: drag. ``zoom``: wheel (multiplicative; ``zoom_inverts`` when a smaller value is a
    closer view, e.g. a field of view). ``dolly``: Shift+wheel. ``pan_*``: middle/right drag.
    ``saved_with_camera_policy``: keys saved only when the store's camera policy allows it;
    ``saved_on_keep``: ordinary settings the "Keep View" action commits; anything else is preview only."""
    orbit_h: NavAxis | None = None
    orbit_v: NavAxis | None = None
    zoom: NavAxis | None = None
    zoom_inverts: bool = False
    dolly: NavAxis | None = None
    pan_x: NavAxis | None = None
    pan_y: NavAxis | None = None
    saved_with_camera_policy: frozenset = frozenset()
    saved_on_keep: frozenset = frozenset()


@dataclass(frozen=True)
class StudioFraming:
    id: str
    label: str
    extent: tuple[float, float]
    description: str = ""
    style: tuple = ()          # (key, value) pairs the mode's renderer needs to present this frame
    # Grow with the viewport: the presented extent is ``extent`` widened (or heightened) to the viewport's
    # own shape, so the picture fills the viewport and still shows at least all of ``extent``'s world.
    fill: bool = False


def control_condition(control) -> tuple:
    """A registry control's ``when`` as Studio terms: ((key, (accepted values...)), ...)."""
    when = getattr(control, "when", None)
    if not when:
        return ()
    terms = (when,) if isinstance(when[0], str) else when
    return tuple((key, tuple(value) if isinstance(value, tuple) else (value,)) for key, value in terms)


def fill_extent(extent, aspect: float) -> tuple[float, float]:
    """``extent`` grown on one axis to ``aspect`` (width / height): never less world than ``extent``."""
    width, height = float(extent[0]), float(extent[1])
    if aspect <= 0.0 or width <= 0.0 or height <= 0.0:
        return width, height
    if width / height < aspect:
        return height * aspect, height
    return width, width / aspect


__all__ = [
    "NavAxis", "RECORDED", "REFERENCE", "SYNTHETIC", "RenderCard", "StudioCapabilities", "StudioEvaluator",
    "StudioFixture", "StudioPreview", "control_condition", "fill_extent",
    "StudioFraming", "StudioNavigation",
    "StudioModeAdapter", "StudioRenderer",
]

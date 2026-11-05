"""The contract a visualizer mode implements to be edited in the Studio.

Everything mode-specific lives behind this interface: which values exist and how
to author them (schema), how the mode's real logical model turns inputs and values
into an immutable frame (evaluator), which preview inputs exist (fixtures) and how
the mode's production renderer draws that frame on the Quick render thread.
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
        """Called on the render thread with the scene-graph context current."""

    def orbit_paths(self) -> tuple[Path, Path, tuple[float, float], tuple[float, float]] | None:
        """(horizontal path, vertical path, horizontal bounds, vertical bounds) for viewport
        orbit drags, or None when the mode has no orbit pose."""
        nav = self.navigation()
        if nav is None or nav.orbit_h is None or nav.orbit_v is None:
            return None
        return (nav.orbit_h.key,), (nav.orbit_v.key,), nav.orbit_h.bounds, nav.orbit_v.bounds

    def navigation(self) -> "StudioNavigation | None":
        """Viewport navigation axes (orbit, zoom, dolly, pan) bound to the mode's camera values."""
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


__all__ = [
    "NavAxis", "RECORDED", "REFERENCE", "SYNTHETIC", "RenderCard", "StudioEvaluator", "StudioFixture",
    "StudioFraming", "StudioNavigation",
    "StudioModeAdapter", "StudioRenderer",
]

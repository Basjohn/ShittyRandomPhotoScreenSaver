"""Typed, mode-supplied description of what a Studio can edit.

A property addresses one canonical persisted value (``path[0]`` is the settings key;
further elements index into a nested list/dict value). The framework never stores
mode defaults: ``admit`` is the mode's canonical validator and the hydrated session
is the only value authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# Instruments the shell knows how to draw. A mode picks one per property; the
# framework never infers an instrument from the storage shape alone (brief §9).
SCALAR = "scalar"            # one bounded number: compact slider + exact entry
COUNT = "count"              # small integer count: segmented 1..N
SWITCH = "switch"            # boolean
CHOICE = "choice"            # categorical: chips
QUIET_PEAK = "quiet_peak"    # two response endpoints of ONE quantity: Quiet|Peak A/B selector + one slider
COLOUR = "colour"            # display swatch + exact hex entry
INSTRUMENTS = frozenset({SCALAR, COUNT, SWITCH, CHOICE, QUIET_PEAK, COLOUR})

Path = tuple  # (settings_key, *index)


@dataclass(frozen=True)
class StudioProperty:
    """One editable value and how to author it."""

    id: str
    path: Path
    label: str
    workspace: str
    group: str
    instrument: str
    minimum: float = 0.0
    maximum: float = 1.0
    decimals: int = 2
    units: str = ""
    choices: tuple[str, ...] = ()
    tooltip: str = ""
    # QUIET_PEAK only: what the two endpoints mean, in plain words.
    quiet_meaning: str = "Quiet music"
    peak_meaning: str = "Loud music"
    # Scene object ids (from the adapter) this property affects; empty = global.
    targets: tuple[str, ...] = ()
    # Shown only when the scene object with this id is selected (per-object inspector).
    object_scope: str = ""
    integer: bool = False
    # COLOUR only: "srgb255" (0..255 display channels, alpha kept) or "linear01" (0..1 linear-light RGB).
    colour_format: str = "srgb255"
    # Edited by a dedicated instrument (e.g. the response tuner / routing table), not as an inspector row.
    instrument_only: bool = False
    # A live view-pose value (camera navigation): edited as a preview pose, saved only by the store's
    # camera policy, never as an ordinary committed edit.
    view_pose: bool = False
    # Lower first within its group (stable otherwise): headline controls lead their group.
    priority: int = 100
    # CHOICE only: one plain-language line per choice, shown for the current choice and as chip tooltips.
    choice_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.instrument not in INSTRUMENTS:
            raise ValueError(f"Unknown Studio instrument {self.instrument!r} for {self.id}")
        if not self.path or not isinstance(self.path[0], str):
            raise ValueError(f"Studio property {self.id} needs a settings-key path")
        if self.instrument in (SCALAR, QUIET_PEAK, COUNT) and not self.minimum <= self.maximum:
            raise ValueError(f"Studio property {self.id} has inverted bounds")
        if self.instrument == CHOICE and not self.choices:
            raise ValueError(f"Studio choice {self.id} declares no choices")


@dataclass(frozen=True)
class SceneObject:
    """A selectable thing in the viewport (identity swatch, label, visibility)."""

    id: str
    label: str
    swatch: str = "#808080"
    visible: bool = True
    # Path of a boolean-ish value that hides it, if the mode has one; None = not hideable.
    visibility_path: Path | None = None


@dataclass(frozen=True)
class Workspace:
    id: str
    title: str
    groups: tuple[str, ...]
    # Groups open when the workspace is shown (default: the first two).
    open_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResponseSource:
    id: str
    label: str


@dataclass(frozen=True)
class ResponseCell:
    """How one source drives one target: two property ids the session edits."""
    source: str
    gain: str
    power: str


@dataclass(frozen=True)
class ResponseTarget:
    id: str
    label: str
    description: str
    cells: tuple[ResponseCell, ...]
    range_property: str = ""           # the target's quiet/peak endpoints, if it has them


@dataclass(frozen=True)
class StudioResponse:
    """A provider-driven target x source response model (any count of either)."""
    sources: tuple[ResponseSource, ...]
    targets: tuple[ResponseTarget, ...]
    gain_bounds: tuple[float, float]
    power_bounds: tuple[float, float]
    timing_properties: tuple[str, ...] = ()
    timing_note: str = ""
    # (label, power) starting shapes for a source's transfer curve; they set only the power.
    curve_presets: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class StudioSchema:
    """A mode's complete editable surface."""

    mode_id: str
    title: str
    workspaces: tuple[Workspace, ...]
    properties: tuple[StudioProperty, ...]
    # The mode's canonical validator for one settings key: (key, candidate, previous) -> admitted.
    admit: Callable[[str, Any, Any], Any] = field(compare=False, repr=False, default=lambda _k, v, _p: v)
    response: StudioResponse | None = None
    # Live signal channels (names the evaluator measures) to trace beside an inspector group.
    group_traces: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        ids = [prop.id for prop in self.properties]
        if len(ids) != len(set(ids)):
            raise ValueError("Studio property ids must be unique")
        known = {workspace.id for workspace in self.workspaces}
        for prop in self.properties:
            if prop.workspace not in known:
                raise ValueError(f"Studio property {prop.id} names unknown workspace {prop.workspace}")

    def find(self, property_id: str) -> StudioProperty:
        for prop in self.properties:
            if prop.id == property_id:
                return prop
        raise KeyError(property_id)

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(prop.path[0] for prop in self.properties)


__all__ = [
    "ResponseCell", "ResponseSource", "ResponseTarget", "StudioResponse",
    "CHOICE", "COLOUR", "COUNT", "INSTRUMENTS", "QUIET_PEAK", "SCALAR", "SWITCH",
    "SceneObject", "StudioProperty", "StudioSchema", "Workspace",
]

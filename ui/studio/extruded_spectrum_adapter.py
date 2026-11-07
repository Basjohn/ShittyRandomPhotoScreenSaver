"""Extruded Spectrum's Studio adapter (Rainbow Ghost included): schema, evaluator, fixtures and renderer.

Truthfulness: the Studio changes no Extruded Spectrum simulation, timing, engine or render code and re-implements
none of it.

* **Spectrum's step under the Extruded identity.** Extruded Spectrum reuses Spectrum's frame runtime and capture
  (``logical_frame_capture._capture_spectrum_family`` with ``extruded_spectrum_parameters``), so its bars are the
  beat engine's own processing on the process clock, exactly as Spectrum's are. It therefore uses the Spectrum
  family's recorded engine answers (``ui.studio.engine_answers``): the worker
  ``ui.studio.extruded_spectrum_recorded_inputs`` replays the source through the production offline replay out of
  process and records every answer the engine gave the step; the Studio runs the production step in process from
  those answers. Engine-owned values (the shape editor, Reactivity / Shape Floor / Falloff and the technical
  analysis: what the production source projection hands the engine) re-run the worker; everything else (depth,
  colouring, hue drift, finish, reflection, overflow, ghosts and Rainbow Ghost, smoothing, bar colours, the view)
  is the mode's own and replays exactly at once.
* **Display context.** The store's 3D Detail tier reaches the presentation as the display manager hands it, and
  Mirror Faces reflect the saver's own photograph (``ui.studio.environment``) through production's reflection rule.
* **Camera.** A free-orbit mode (not the framed camera: no lens, dolly or pan): viewport drags orbit the
  descriptor's live view pose (turn, tilt), a preview view saved only through the store's camera policy.
* The production ``QuickExtrudedSpectrumRenderer`` draws the resulting ``VisualizerLogicalFrame`` at the live card's
  presentation (Fill by default), its reflection settled as on a photograph already on screen.
"""
from __future__ import annotations

import math
from functools import cache
from typing import Any, Callable, Mapping

from core.settings.visualizer_mode_settings import Choice, Colour, Custom, Slider, Toggle, require_mode_settings
from ui.studio import engine_answers, framed, spectrum_shape
from ui.studio.adapter import StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition
from ui.studio.engine_answers import EngineAnswerEvaluator, EngineAnswerMode
from ui.studio.schema import (
    CHOICE, COLOUR, SCALAR, SWITCH, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.spectrum_shape import ShapeKeys
from ui.studio.technical import TECHNICAL_GROUP, admit_technical, technical_properties

MODE = "extruded_spectrum"
PREFIX = "extruded_spectrum_"
EXTRUDED_SPECTRUM = EngineAnswerMode(MODE)
SHAPE = ShapeKeys(PREFIX)
BAR_COLOUR_GROUP = "Bar Colours"
VIEW_GROUP = "View"
# A bucketless registry control is edited in Settings by the Custom row of this name (Rainbow writes the colouring).
_CUSTOM_OWNER = {PREFIX + "colouring": "rainbow"}

_BUCKET_WORKSPACE = {"appearance": "look", "shape": "shape", "response": "shape", "effects": "effects"}
_WORKSPACES = (
    ("look", "Colour", "palette", "The bars' fill and border colours, the rainbow surface and its hue drift."),
    ("shape", "Shape & Response", "wave", "Bar depth, the authored silhouette and its frequency lanes, how hard the "
                                          "music drives them, and the audio analysis feeding the bars."),
    ("effects", "3D & Ghosts", "sparkle", "Finish, mirror faces, floor reflection, overflow, the falling peak "
                                          "ghosts (Rainbow Ghost) and the preview view."),
)
_GROUP_PANEL = {
    "appearance": ("gradient", "Rainbow surface and hue drift"), "shape": ("bars", "Depth and silhouette"),
    "response": ("bolt", "Reactivity, falloff and smoothing"), "effects": ("sparkle", "Finish, reflection, ghosts"),
}
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "bar_fill_color", "bar_border_color", "bar_border_opacity", "colouring", "hue_drift", "depth", "mirrored",
    "wave_amplitude", "profile_floor", "drop_speed", "visual_smoothing_enabled", "visual_smoothing",
    "solid_bar_hysteresis_enabled", "gloss", "face_mirror", "reflection", "smooth_edges", "allow_overflow",
    "ghosting_enabled", "rainbow_ghost", "ghost_alpha", "ghost_decay"))}
_ROW_ICONS = {"bar_fill_color": "colour", "bar_border_color": "colour", "colouring": "gradient", "depth": "height",
              "mirrored": "wave", "wave_amplitude": "bolt", "drop_speed": "height", "gloss": "material",
              "face_mirror": "material", "reflection": "floor", "ghosting_enabled": "sparkle",
              "rainbow_ghost": "sparkle"}
_SMOOTHING = (
    ("visual_smoothing_enabled", "Smooth Sudden Bar Changes", SWITCH,
     "Interpolate bar heights on the existing visualizer tick. Audio analysis remains unchanged."),
    ("visual_smoothing", "Smoothing Strength", SCALAR,
     "Higher values soften one-tick spikes and drops more strongly."),
    ("solid_bar_hysteresis_enabled", "Stabilize Bar Heights", SWITCH,
     "Use the shared bar evaluator's hysteresis to suppress tiny height fluctuations."),
)


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


def _family_keys(family: str) -> dict[str, str]:
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    return get_owned_mode_setting_keys(MODE, family)


def control_available(control) -> bool:
    """Settings' own availability rule (``spec_mode_builder._apply_availability``): a control whose capability flag
    is off is disabled there (not editable), so the Studio does not offer it either."""
    if not getattr(control, "availability", ()):
        return True
    from ui.tabs.media.spec_mode_builder import _resolve
    return bool(_resolve(control.availability[0]))


@cache
def owned_keys() -> frozenset[str]:
    """Settings Extruded Spectrum's own step, capture or renderer reads (``EngineAnswerMode.owned_keys``)."""
    return EXTRUDED_SPECTRUM.owned_keys()


def engine_values(values: Mapping[str, Any]) -> dict:
    """The engine-owned subset of ``values`` (``tests/test_extruded_spectrum_studio.py`` proves both directions)."""
    return EXTRUDED_SPECTRUM.engine_values(values)


def engine_key(values: Mapping[str, Any]) -> str:
    return EXTRUDED_SPECTRUM.engine_key(values)


def structure_edit(action_id: str, values: Mapping[str, Any]):
    return spectrum_shape.structure_edit(SHAPE, action_id, values)


def row_label(prop: StudioProperty, values: Mapping[str, Any]) -> str:
    return spectrum_shape.row_label(SHAPE, prop, values)


# ---------------------------------------------------------------------------------- schema
def build_schema() -> StudioSchema:
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    customs = {entry.name: entry for entry in spec.entries if isinstance(entry, Custom) and entry.bucket}
    view_keys = tuple(get_visualizer_mode_descriptor(MODE).view_orbit_settings)
    props: list[StudioProperty] = []
    placed: dict[str, list[str]] = {w[0]: [] for w in _WORKSPACES}

    def place(workspace: str, group: str) -> None:
        if group not in placed[workspace]:
            placed[workspace].append(group)

    def add(key_id: str, path: tuple, label: str, workspace: str, group: str, instrument: str, **extra) -> None:
        place(workspace, group)
        root = path[0]
        extra.setdefault("priority", _PRIORITY.get(root, 100))
        extra.setdefault("icon", _ROW_ICONS.get(root[len(PREFIX):], "") if len(path) == 1 else "")
        props.append(StudioProperty(id=key_id, path=path, label=label, workspace=workspace, group=group,
                                    instrument=instrument, **extra))

    for control in spec.body_controls:
        if control.key in view_keys or not control_available(control):
            continue                                    # the live view below; unavailable as in Settings
        owner = customs.get(_CUSTOM_OWNER.get(control.key, ""))
        bucket = control.bucket or (owner.bucket if owner is not None else "")
        if not bucket:
            raise KeyError(f"{control.key} has no Settings owner the Studio knows")
        workspace, group = _BUCKET_WORKSPACE.get(bucket, "effects"), titles.get(bucket, bucket)
        text = getattr(control, "text", "") if isinstance(control, Toggle) else ""
        label = _label(control.label) or _label(text) or control.key[len(PREFIX):].replace("_", " ").title()
        common = dict(tooltip=getattr(control, "tooltip", "") or text, when=control_condition(control))
        if isinstance(control, Slider):
            extra = max(0, int(round(math.log10(control.display_multiplier)))) if control.display_multiplier > 1 else 0
            decimals = 0 if control.integer else max(control.decimals + extra, 2)
            add(control.key, (control.key,), label, workspace, group, SCALAR, minimum=control.low,
                maximum=control.high, decimals=decimals, units="" if control.percent else control.suffix,
                integer=control.integer, **common)
        elif isinstance(control, Toggle):
            add(control.key, (control.key,), label, workspace, group, SWITCH, **common)
        elif isinstance(control, Choice):
            stored = tuple(control.choices)
            add(control.key, (control.key,), label, workspace, group, CHOICE,
                choices=tuple(control.labels) if control.labels else tuple(str(c) for c in stored),
                choice_values=stored, **common)
        elif isinstance(control, Colour):
            add(control.key, (control.key,), label, workspace, group, COLOUR, **common)
        # Any other control type is deliberately not guessed at: the full-coverage test names it.

    # The live view pose (turn / tilt): a preview view, saved only through the store's camera policy.
    for key in view_keys:
        control = spec.control(key)
        add(key, (key,), "View " + key[len(PREFIX):].title(), "effects", VIEW_GROUP, SCALAR, minimum=control.low,
            maximum=control.high, decimals=3, view_pose=True,
            tooltip="Preview view. Drag the viewport to orbit. The live orbit is a view, not artwork: it is saved "
                    "only when the preset's camera choice includes the view.")

    # The smoothing row (Custom): Spectrum's own one-pole on the resolved bars and the solid-bar stabilization.
    response = titles["response"]
    smoothing = customs["smoothing"]
    for suffix, label, instrument, tooltip in _SMOOTHING:
        key = PREFIX + suffix
        if key not in smoothing.keys:
            raise KeyError(f"{key} is no longer a smoothing row key")
        extra = (dict(minimum=0.0, maximum=1.0, decimals=2, when=((PREFIX + "visual_smoothing_enabled", (True,)),))
                 if instrument == SCALAR else {})
        add(key, (key,), label, "shape", response, instrument, tooltip=tooltip, **extra)

    # The shared bar colours (Settings shows them on the mode's page; stored per mode).
    shared = _family_keys("shared_bar")
    for suffix, label in (("bar_fill_color", "Bar Fill Color"), ("bar_border_color", "Bar Border Color")):
        key = shared[suffix]
        add(key, (key,), label, "look", BAR_COLOUR_GROUP, COLOUR)
        add(f"{key}.3", (key, 3), f"{label} Opacity", "look", BAR_COLOUR_GROUP, SCALAR, minimum=0.0,
            maximum=255.0, decimals=0, integer=True, icon="", priority=_PRIORITY.get(key, 100) + 1)
    border = shared["bar_border_opacity"]
    add(border, (border,), "Border Opacity", "look", BAR_COLOUR_GROUP, SCALAR, minimum=0.0, maximum=1.0, decimals=2,
        tooltip="Opacity of the bar edge lines.")

    # The shape editor (Custom): layout, curve nodes, frequency boundaries and lane strengths.
    shape = titles["shape"]
    spectrum_shape.shape_properties(SHAPE, add, "shape", shape)

    technical = technical_properties(MODE, workspace="shape")
    props.extend(prop for prop, _defn in technical.values())
    placed["shape"].append(TECHNICAL_GROUP)

    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(("appearance", "shape", "response", "effects"))}
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = placed[workspace_id]
        if not groups:
            continue
        groups = sorted(groups, key=lambda g: (g != BAR_COLOUR_GROUP, g == VIEW_GROUP, g == TECHNICAL_GROUP,
                                               order.get(bucket_of.get(g, ""), len(order))))
        columns = []
        for group in groups:
            if group == BAR_COLOUR_GROUP:
                glyph, subtitle = "colour", "Fill, border and border opacity"
            elif group == VIEW_GROUP:
                glyph, subtitle = "view", "The preview orbit"
            else:
                glyph, subtitle = _GROUP_PANEL.get(bucket_of.get(group, ""), ("bars", "Live analysis feeding the bars"))
            columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
        workspaces.append(Workspace(workspace_id, title, tuple(groups), open_groups=tuple(groups), icon=icon,
                                    help=help_text, columns=tuple(columns)))

    controls = {control.key: control for control in spec.controls}
    colours = {shared["bar_fill_color"], shared["bar_border_color"]}
    switches = {PREFIX + suffix for suffix, _l, instrument, _t in _SMOOTHING if instrument == SWITCH}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key in controls:
            return controls[key].admit(candidate, previous)
        shaped = spectrum_shape.admit_shape(SHAPE, key, candidate, previous)
        if shaped is not NotImplemented:
            return shaped
        if key in colours:
            return spectrum_shape.admit_colour(candidate, previous)
        if key in (border, PREFIX + "visual_smoothing"):
            return spectrum_shape.percent(candidate, previous)
        if key in switches:
            return bool(candidate)
        raise KeyError(f"{key} is not an Extruded Spectrum Studio value")

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _GROUP_PANEL.items() if key in titles}
    group_icons.update({TECHNICAL_GROUP: "bars", BAR_COLOUR_GROUP: "colour", VIEW_GROUP: "view"})
    return StudioSchema(MODE, "Extruded Spectrum Studio", tuple(workspaces), tuple(props), admit,
                        group_traces=((titles["response"], ("Level", "Peak")), (titles["effects"], ("Ghost",)),
                                      (titles["shape"], ("Level",))),
                        group_icons=tuple(group_icons.items()), object_noun="Bar",
                        group_actions=((shape, (spectrum_shape.add_node_action(),)),), row_label=row_label)


# ------------------------------------------------------------------------------- evaluator
class ExtrudedSpectrumStudioEvaluator(EngineAnswerEvaluator):
    """Extruded Spectrum's production step and capture, run in process from recorded engine answers
    (``engine_answers.EngineAnswerEvaluator``), with the photograph Mirror Faces reflect."""

    def __init__(self, loader: Callable | None = None) -> None:
        super().__init__(EXTRUDED_SPECTRUM, loader)


# ------------------------------------------------------------------------------- renderer
def face_mirror(parameters) -> float:
    """The production renderer's own Mirror Faces amount for a frame (0 without a tier reflection or backdrop)."""
    from rendering.quick.visualizer.implementations.extruded_spectrum import extruded_quality
    return extruded_quality(parameters)[1]


class ExtrudedSpectrumStudioRenderer(framed.ContractModeRenderer):
    """The production ``QuickExtrudedSpectrumRenderer`` handed the production render-frame contract (the full logical
    frame), the live card's presentation and the item mapping. Mirror Faces show the photograph settled, as on one
    already on screen (``environment.settle_backdrop``)."""

    def __init__(self) -> None:
        from rendering.quick.visualizer.implementations.extruded_spectrum import create_visualizer_renderer
        super().__init__(MODE, create_visualizer_renderer)
        self._settled = None

    def _settle(self, frame) -> None:
        from ui.studio.environment import settle_backdrop
        self._settled = settle_backdrop(self._impl, frame, face_mirror, self._settled)

    def prepare(self, card, frame) -> bool:
        self._settle(frame)
        return super().prepare(card, frame)

    def render(self, card, frame) -> None:
        self._settle(frame)
        super().render(card, frame)


# --------------------------------------------------------------------------------- adapter
class ExtrudedSpectrumStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "Extruded Spectrum Studio"

    def __init__(self) -> None:
        self._schema: StudioSchema | None = None

    def capabilities(self) -> StudioCapabilities:
        return StudioCapabilities(viewport=True, camera=True, handles=False, objects=False)

    def schema(self) -> StudioSchema:
        if self._schema is None:
            self._schema = build_schema()
        return self._schema

    def scene_objects(self, values: Mapping[str, Any]):
        return ()

    def structure_edit(self, action_id: str, values: Mapping[str, Any]):
        return structure_edit(action_id, values)

    def create_evaluator(self) -> ExtrudedSpectrumStudioEvaluator:
        return ExtrudedSpectrumStudioEvaluator()

    def create_renderer(self):
        return ExtrudedSpectrumStudioRenderer()

    def navigation(self):
        return framed.orbit_navigation(MODE)

    def framings(self, card_extent, card_style=None):
        return framed.card_framings(card_extent, card_style)

    def default_framing(self) -> str:
        return "fill"           # the live card's world and scale, filling the viewport; Live Card is exact

    def default_fixture(self, evaluator) -> str | None:
        return "mid"

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        """The Studios' shared recorded music (the shipped clips first, then a checkout's recordings)."""
        from ui.studio.waveform_adapter import recordings_directory
        from ui.studio.waveform_recorded_inputs import studio_clips
        return studio_clips(recordings_directory())

    def start_clip_load(self, clip: StudioFixture, values: Mapping[str, Any], finished):
        """Analyse ``clip`` under ``values``' engine-owned settings out of process (cached per engine values)."""
        return engine_answers.start_clip_load(EXTRUDED_SPECTRUM, clip, values, finished)


__all__ = [
    "EXTRUDED_SPECTRUM", "ExtrudedSpectrumStudioAdapter", "ExtrudedSpectrumStudioEvaluator",
    "ExtrudedSpectrumStudioRenderer", "build_schema", "control_available", "engine_key", "engine_values",
    "face_mirror", "owned_keys", "structure_edit",
]

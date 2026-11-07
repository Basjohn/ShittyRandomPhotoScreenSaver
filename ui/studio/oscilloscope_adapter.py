"""Oscilloscope's Studio adapter: schema, evaluator, fixtures and renderer, on the shared framework.

Truthfulness: the Studio changes no Oscilloscope trace, timing, engine or render code and re-implements none of it.

* **Engine answers.** Oscilloscope's capture (``logical_frame_capture._capture_oscilloscope``) draws the live trace
  and its afterglow from what the beat engine answers every tick (the capture history, the 256-sample waveform,
  onsets, the musical level and intensity, the analysis spectrum, the history's rate, the source identities), and
  ``consume_engine_bars`` ticks the engine on the process clock. It therefore uses the shared recorded engine answers
  (``ui.studio.engine_answers``): the worker ``ui.studio.oscilloscope_recorded_inputs`` replays the source through the
  production offline replay out of process and records every answer the engine gave the step; the Studio runs the
  production step in process from those answers. The capture history is recorded by *identity*
  (``replay_engine.RecordedArrays``): the frame runtime rebuilds the trace only for a new history object, so the
  Studio serves one array object per recorded number, exactly as the engine held it.
* **The split.** Engine-owned are the audio analysis (technical) values; every ``osc_*`` setting (Display, Beam,
  Reaction, Screen) is the mode's own and replays exactly at once.
* **Flat card.** No camera, handles or scene objects; the production ``QuickOscilloscopeRenderer`` draws the
  resulting ``VisualizerLogicalFrame`` at the live card's presentation (Fill by default).
* **Instruments.** Studio-only reads of the frame on screen: the live trace's swing (Level), the newest afterglow
  trace's brightness and how many are held (Afterglow, Ghosts), and the beam's Flare, Drive and Tone.
"""
from __future__ import annotations

import math
from functools import cache
from typing import Any, Callable, Mapping

from core.settings.visualizer_mode_settings import Choice, Colour, Slider, Toggle, require_mode_settings
from ui.studio import engine_answers, framed
from ui.studio.adapter import StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition
from ui.studio.engine_answers import EngineAnswerEvaluator
from ui.studio.oscilloscope_recorded_inputs import OSCILLOSCOPE
from ui.studio.schema import CHOICE, COLOUR, SCALAR, SWITCH, StudioProperty, StudioSchema, Workspace, WorkspaceColumn
from ui.studio.technical import TECHNICAL_GROUP, admit_technical, technical_properties

MODE = "oscilloscope"
PREFIX = "osc_"

# Workspace of each canonical bucket (group titles are the registry's bucket titles).
_BUCKET_WORKSPACE = {"display": "trace", "beam": "beam", "screen": "beam", "reaction": "reaction"}
_WORKSPACES = (
    ("trace", "Trace", "wave", "How the audio is drawn: the triggered trace, the ring or the X/Y phase figure, its "
                               "time span, detail and gain."),
    ("beam", "Beam & Screen", "sparkle", "The beam's colours, width, glow and afterglow, and the scale behind it."),
    ("reaction", "Reaction", "bolt", "How the beam answers the music (spectral colour, hit flare, loudness glow) "
                                     "and the audio analysis feeding it."),
)
_BUCKET_PANEL = {
    "display": ("wave", "Display, span, detail and gain"), "beam": ("sparkle", "Colour, width, glow, afterglow"),
    "reaction": ("bolt", "Colour, flare and loudness glow"), "screen": ("grid", "The graticule behind the beam"),
}
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "display", "span", "detail", "gain", "delay", "beam_color", "beam_glow_color", "beam_width", "glow", "afterglow",
    "analog", "spectral", "flare", "pulse", "graticule", "graticule_color"))}
_ROW_ICONS = {"display": "wave", "span": "flow", "gain": "height", "beam_color": "colour",
              "beam_glow_color": "colour", "glow": "sparkle", "afterglow": "sparkle", "flare": "bolt",
              "pulse": "sun", "spectral": "gradient", "graticule": "grid", "graticule_color": "colour"}


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


@cache
def owned_keys() -> frozenset[str]:
    """Settings Oscilloscope's own step, capture or renderer reads (``EngineAnswerMode.owned_keys``)."""
    return OSCILLOSCOPE.owned_keys()


def engine_values(values: Mapping[str, Any]) -> dict:
    """The engine-owned subset of ``values`` (``tests/test_oscilloscope_studio.py`` proves both directions)."""
    return OSCILLOSCOPE.engine_values(values)


def engine_key(values: Mapping[str, Any]) -> str:
    return OSCILLOSCOPE.engine_key(values)


# ---------------------------------------------------------------------------------- schema
def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
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
        bucket = control.bucket
        if not bucket:
            raise KeyError(f"{control.key} has no Settings owner the Studio knows")
        workspace, group = _BUCKET_WORKSPACE[bucket], titles.get(bucket, bucket)
        text = getattr(control, "text", "") if isinstance(control, Toggle) else ""
        label = _label(control.label) or _label(text) or control.key[len(PREFIX):].replace("_", " ").title()
        common = dict(tooltip=getattr(control, "tooltip", "") or text, when=control_condition(control))
        if isinstance(control, Slider):
            extra = max(0, int(round(math.log10(control.display_multiplier)))) if control.display_multiplier > 1 else 0
            decimals = 0 if control.integer else max(control.decimals + extra, 2 if control.percent else 0)
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
            if control.alpha:
                add(f"{control.key}.3", (control.key, 3), f"{label} Opacity", workspace, group, SCALAR,
                    minimum=0.0, maximum=255.0, decimals=0, integer=True, icon="",
                    priority=_PRIORITY.get(control.key, 100) + 1, **common)
        # Any other control type is deliberately not guessed at: the full-coverage test names it.

    technical = technical_properties(MODE, workspace="reaction")
    props.extend(prop for prop, _defn in technical.values())
    placed["reaction"].append(TECHNICAL_GROUP)

    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(bucket.key for bucket in spec.buckets)}     # Settings' order
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = placed[workspace_id]
        if not groups:
            continue
        groups = sorted(groups, key=lambda g: (g == TECHNICAL_GROUP, order.get(bucket_of.get(g, ""), len(order))))
        columns = []
        for group in groups:
            glyph, subtitle = _BUCKET_PANEL.get(bucket_of.get(group, ""), ("bars", "Live analysis feeding the beam"))
            columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
        workspaces.append(Workspace(workspace_id, title, tuple(groups), open_groups=tuple(groups), icon=icon,
                                    help=help_text, columns=tuple(columns)))

    controls = {control.key: control for control in spec.controls}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key in controls:
            return controls[key].admit(candidate, previous)
        raise KeyError(f"{key} is not an Oscilloscope Studio value")

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _BUCKET_PANEL.items() if key in titles}
    group_icons[TECHNICAL_GROUP] = "bars"
    return StudioSchema(MODE, "Oscilloscope Studio", tuple(workspaces), tuple(props), admit,
                        group_traces=((titles["display"], ("Level",)), (titles["beam"], ("Afterglow", "Ghosts")),
                                      (titles["reaction"], ("Flare", "Drive", "Tone"))),
                        group_icons=tuple(group_icons.items()), object_noun="Trace")


# ---------------------------------------------------------------------------- instruments
def trace_swing(frame) -> float:
    """0..1: how far the live trace swings from its rest (the flat line, the ring's circle, the phase dot), read
    from the frame's own points in the display's own units (``oscilloscope_program``)."""
    import numpy as np
    from rendering.gl_programs.oscilloscope_program import PHASE_SCALE, RING_RADIUS, RING_SWING
    state = frame.mode_state
    count = len(state.trace_alphas)
    if not count or not state.points:
        return 0.0
    points = np.frombuffer(state.points, dtype=np.float32).reshape(count, -1, 2)[-1]
    display = str(dict(state.parameters).get("osc_display", "Trace"))
    if display == "Ring":
        swing = np.abs(np.hypot(points[:, 0], points[:, 1]) - RING_RADIUS) / RING_SWING
    elif display == "Phase":
        swing = np.hypot(points[:, 0], points[:, 1]) / PHASE_SCALE
    else:
        swing = np.abs(points[:, 1])
    return float(min(1.0, swing.max()))


def afterglow_reading(frame) -> tuple[float, float]:
    """(the newest afterglow trace's brightness against a fresh ghost's, held ghosts against the capacity)."""
    from rendering.gl_programs.oscilloscope_program import GHOST_CAPACITY, ghost_alpha
    ghosts = frame.mode_state.trace_alphas[:-1]
    fresh = ghost_alpha(0.0, 1.0) or 1.0
    return (max(ghosts, default=0.0) / fresh, len(ghosts) / GHOST_CAPACITY)


def loudness_level(answers: Mapping[str, Any]) -> float:
    """The transport overview's level: the recorded musical loudness of a tick (``get_musical_level``)."""
    from ui.studio.replay_engine import decode_answer
    level = answers.get("get_musical_level")
    return float(decode_answer(level)[0]) if level is not None else 0.0


# ------------------------------------------------------------------------------- evaluator
class OscilloscopeStudioEvaluator(EngineAnswerEvaluator):
    """Oscilloscope's production step and capture, run in process from recorded engine answers
    (``engine_answers.EngineAnswerEvaluator``)."""

    timeline_measure = staticmethod(loudness_level)

    def __init__(self, loader: Callable | None = None) -> None:
        super().__init__(OSCILLOSCOPE, loader)

    def measurements(self) -> dict[str, dict[str, float]]:
        """Studio-only reads of the frame on screen: the live trace's swing, the afterglow's decay and fill, and
        the beam's flare, drive and tone (no saver work: the frame already carries them)."""
        frame = self._last
        if frame is None:
            return {"sources": {}, "targets": {}, "signals": {}}
        state = frame.mode_state
        glow, held = afterglow_reading(frame)
        return {"sources": {}, "targets": {}, "signals": {
            "Level": trace_swing(frame), "Afterglow": glow, "Ghosts": held, "Flare": min(1.0, float(state.flare)),
            "Drive": float(state.drive), "Tone": float(state.tone)}}


# --------------------------------------------------------------------------------- adapter
class OscilloscopeStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "Oscilloscope Studio"

    def __init__(self) -> None:
        self._schema: StudioSchema | None = None

    def capabilities(self) -> StudioCapabilities:
        return StudioCapabilities(viewport=True, camera=False, handles=False, objects=False)

    def schema(self) -> StudioSchema:
        if self._schema is None:
            self._schema = build_schema()
        return self._schema

    def scene_objects(self, values: Mapping[str, Any]):
        return ()

    def create_evaluator(self) -> OscilloscopeStudioEvaluator:
        return OscilloscopeStudioEvaluator()

    def create_renderer(self):
        """The production ``QuickOscilloscopeRenderer`` handed the production render-frame contract."""
        from rendering.quick.visualizer.implementations.oscilloscope import create_visualizer_renderer
        return framed.ContractModeRenderer(MODE, create_visualizer_renderer)

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
        return engine_answers.start_clip_load(OSCILLOSCOPE, clip, values, finished)


__all__ = [
    "OSCILLOSCOPE", "OscilloscopeStudioAdapter", "OscilloscopeStudioEvaluator", "afterglow_reading", "build_schema",
    "engine_key", "engine_values", "loudness_level", "owned_keys", "trace_swing",
]

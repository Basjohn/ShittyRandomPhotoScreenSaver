"""Temporary old-presenter capture into the immutable Quick-era contract.

This adapter exists only while the QWidget/QRhiWidget presenter is still the
live production path.  It copies the authored logical result and current
visual parameters into detached immutable values.  Quick render code must
consume those values, never the legacy widget or its compositor overlay.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from widgets.spotify_visualizer import config_applier, mode_capabilities
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from widgets.spotify_visualizer.logical_runtime import coerce_identity
from widgets.spotify_visualizer.oscilloscope_frame_runtime import (
    OscilloscopeFrameRuntime,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    DevCurveFrame,
    ModeFrame,
    OscilloscopeFrame,
    SineFrame,
    SpectrumFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    VisualizerProtectedEdge,
    VisualizerTransientState,
    freeze_render_fields,
)
from widgets.spotify_visualizer.spectrum_frame_runtime import (
    SpectrumFrameRuntime,
)
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    compute_spectrum_height_scale,
)
from widgets.spotify_visualizer.sine_frame_runtime import SineFrameRuntime


_SIGNAL_FIELDS = {
    "activation_id",
    "engine_generation",
    "latest_frame_generation",
    "latest_waveform_generation",
    "waveform",
    "waveform_count",
    "energy_bands",
    "transient_energy",
}


def _identity_from_engine(engine: Any, method_name: str, fallback: object) -> int:
    if engine is not None:
        getter = getattr(engine, method_name, None)
        if callable(getter):
            try:
                return coerce_identity(getter())
            except Exception:
                pass
    return coerce_identity(fallback)


def _source_identity(
    widget: Any,
    engine: Any,
    mode_id: str,
) -> tuple[int, int, float | None]:
    if mode_id == "bubble":
        getter = getattr(engine, "get_latest_authoritative_frame", None)
        if callable(getter):
            try:
                timestamp, generation, activation_id = getter()
                return (
                    coerce_identity(generation),
                    coerce_identity(activation_id),
                    float(timestamp),
                )
            except Exception:
                pass
        generation = _identity_from_engine(
            engine,
            "get_latest_generation_with_frame",
            None,
        )
        activation_id = (
            _identity_from_engine(engine, "get_activation_id", None)
            if generation >= 0
            else -1
        )
    elif mode_id in {"oscilloscope", "sine_wave"}:
        generation = _identity_from_engine(
            engine,
            "get_latest_generation_with_waveform",
            None,
        )
        activation_id = (
            _identity_from_engine(engine, "get_activation_id", None)
            if generation >= 0
            else -1
        )
    else:
        generation = coerce_identity(
            getattr(widget, "_display_bars_source_generation", None)
        )
        activation_id = coerce_identity(
            getattr(widget, "_display_bars_source_activation", None)
        )
    timestamp: float | None = None
    getter = getattr(engine, "get_latest_authoritative_frame", None)
    if callable(getter):
        try:
            raw_timestamp, frame_generation, frame_activation = getter()
            if (
                coerce_identity(frame_generation) == generation
                and coerce_identity(frame_activation) == activation_id
                and generation >= 0
                and activation_id >= 0
            ):
                timestamp = float(raw_timestamp)
        except Exception:
            timestamp = None
    return generation, activation_id, timestamp


def _energy_state(value: Any) -> VisualizerEnergyState:
    return VisualizerEnergyState(
        bass=float(getattr(value, "bass", 0.0) if value is not None else 0.0),
        mid=float(getattr(value, "mid", 0.0) if value is not None else 0.0),
        high=float(getattr(value, "high", 0.0) if value is not None else 0.0),
        overall=float(getattr(value, "overall", 0.0) if value is not None else 0.0),
    )


def _transient_state(value: Any) -> VisualizerTransientState:
    return VisualizerTransientState(
        bass=float(
            getattr(value, "bass_transient", 0.0) if value is not None else 0.0
        ),
        mid=float(
            getattr(value, "mid_transient", 0.0) if value is not None else 0.0
        ),
        high=float(
            getattr(value, "high_transient", 0.0) if value is not None else 0.0
        ),
        onset_detected=bool(
            getattr(value, "onset_detected", False) if value is not None else False
        ),
        onset_type=str(
            getattr(value, "onset_type", "") if value is not None else ""
        ),
        onset_strength=float(
            getattr(value, "onset_strength", 0.0) if value is not None else 0.0
        ),
    )


def _base_extras(widget: Any, mode_id: str, engine: Any) -> dict[str, Any]:
    """Build a fresh dict; never mutate Spectrum's legacy cached payload."""

    extra: dict[str, Any] = {}
    config_applier._populate_shared_visualizer_extras(extra, widget)
    if engine is None:
        return extra

    def _safe_call(name: str, default: object = None) -> object:
        getter = getattr(engine, name, None)
        if not callable(getter):
            return default
        try:
            return getter()
        except Exception:
            return default

    extra["activation_id"] = _safe_call("get_activation_id")
    extra["engine_generation"] = _safe_call("get_generation_id")
    extra["latest_frame_generation"] = _safe_call(
        "get_latest_generation_with_frame"
    )
    extra["latest_waveform_generation"] = _safe_call(
        "get_latest_generation_with_waveform"
    )
    waveform = _safe_call("get_waveform", ())
    extra["waveform"] = waveform if waveform is not None else ()
    waveform_count = _safe_call("get_waveform_count")
    extra["waveform_count"] = (
        len(extra["waveform"])
        if waveform_count is None
        else int(waveform_count)
    )
    energy = _safe_call("get_energy_bands")
    if energy is None and mode_id == "bubble":
        energy = _safe_call("get_bubble_energy_bands")
    extra["energy_bands"] = energy
    extra["transient_energy"] = _safe_call("get_transient_energy_bands")
    floor_snapshot = _safe_call("get_floor_snapshot")
    if floor_snapshot is not None:
        extra["floor_snapshot"] = floor_snapshot

    if mode_id in {"sine_wave", "oscilloscope"}:
        scheduler = _safe_call("get_event_scheduler")
        peek = getattr(scheduler, "peek_latest", None)
        for event_name, field_name, max_age_s in (
            ("kick", "line_kick_event_strength", 0.16),
            ("snare", "line_snare_event_strength", 0.20),
        ):
            event = None
            if callable(peek):
                try:
                    event = peek(event_name, max_age_s=max_age_s)
                except Exception:
                    event = None
            extra[field_name] = float(getattr(event, "strength", 0.0) or 0.0)
    return extra


def _render_parameters(
    extra: Mapping[str, object],
    *,
    omit: set[str] | frozenset[str] = frozenset(),
):
    excluded = _SIGNAL_FIELDS | set(omit)
    return freeze_render_fields(
        {name: value for name, value in extra.items() if name not in excluded}
    )


@dataclass(frozen=True, slots=True)
class _CaptureContext:
    now_ts: float
    runtime_generation: int
    engine_generation: int
    activation_id: int
    source_generation: int
    source_activation_id: int
    playing: bool
    first_frame: bool


def _spectrum_segment_count(viewport_height: float) -> int:
    inner_height = max(0.0, float(viewport_height) - 12.0)
    return max(8, min(64, int(inner_height // 5.0)))


def _capture_spectrum(
    widget: Any,
    engine: Any,
    context: _CaptureContext,
) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "spectrum", engine)
    controller = getattr(widget, "runtime_controller", None)
    if controller is None:
        raise RuntimeError(
            "Spectrum logical capture requires its runtime controller owner"
        )
    runtime = controller.resolve_logical_mode_state(
        "spectrum",
        SpectrumFrameRuntime,
    )
    if not isinstance(runtime, SpectrumFrameRuntime):
        raise TypeError("Spectrum logical mode state has the wrong type")
    _viewport_width, viewport_height = (
        controller.presentation_viewport_extent
    )
    resolved = runtime.resolve(
        tuple(getattr(widget, "_display_bars", ()) or ()),
        bar_count=int(getattr(widget, "_bar_count", 0) or 0),
        now_ts=context.now_ts,
        runtime_generation=context.runtime_generation,
        engine_generation=context.engine_generation,
        activation_id=context.activation_id,
        source_generation=context.source_generation,
        source_activation_id=context.source_activation_id,
        playing=context.playing,
        first_frame=context.first_frame,
        smoothing_enabled=bool(
            getattr(widget, "_spectrum_visual_smoothing_enabled", True)
        ),
        smoothing_strength=float(
            getattr(widget, "_spectrum_visual_smoothing", 0.5)
        ),
        single_piece=bool(getattr(widget, "_spectrum_single_piece", False)),
        segments=_spectrum_segment_count(viewport_height),
        viewport_height=viewport_height,
        ghosting_enabled=bool(
            getattr(widget, "_spectrum_ghosting_enabled", True)
        ),
        ghost_decay=float(getattr(widget, "_spectrum_ghost_decay", 0.4)),
        animation_enabled=bool(
            getattr(widget, "_rainbow_enabled", False)
            or getattr(widget, "_rainbow_per_bar", False)
        ),
    )
    extra["spectrum_height_scale"] = compute_spectrum_height_scale(
        viewport_height
    )
    extra["_quick_resolved_bars"] = resolved.bars
    extra["_quick_spectrum_changed"] = resolved.changed
    return (
        SpectrumFrame(
            peaks=resolved.peaks,
            ghost_bars=resolved.ghost_bars,
            animation_time=resolved.animation_time,
            parameters=_render_parameters(
                {
                    name: value
                    for name, value in extra.items()
                    if not name.startswith("_quick_")
                }
            ),
        ),
        extra,
    )


def _capture_oscilloscope(
    widget: Any,
    engine: Any,
    context: _CaptureContext,
) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "oscilloscope", engine)
    config_applier._append_line_mode_visual_extras(extra, widget, is_sine=False)
    extra["osc_transient_width_mix"] = getattr(
        widget,
        "_osc_transient_width_mix",
        0.35,
    )
    controller = getattr(widget, "runtime_controller", None)
    if controller is None:
        raise RuntimeError(
            "Oscilloscope logical capture requires its runtime controller owner"
        )
    runtime = controller.resolve_logical_mode_state(
        "oscilloscope",
        OscilloscopeFrameRuntime,
    )
    if not isinstance(runtime, OscilloscopeFrameRuntime):
        raise TypeError("Oscilloscope logical mode state has the wrong type")
    resolved = runtime.resolve(
        tuple(extra.get("waveform", ()) or ()),
        waveform_count=int(extra.get("waveform_count", 0) or 0),
        now_ts=context.now_ts,
        runtime_generation=context.runtime_generation,
        engine_generation=context.engine_generation,
        activation_id=context.activation_id,
        source_generation=context.source_generation,
        source_activation_id=context.source_activation_id,
        playing=context.playing,
        line_speed=float(extra.get("line_speed", 1.0) or 1.0),
        ghosting_enabled=bool(
            extra.get("osc_ghosting_enabled", False)
            and float(extra.get("osc_ghost_intensity", 0.0) or 0.0) > 0.001
        ),
        ghost_decay=float(extra.get("osc_ghost_decay", 0.4) or 0.4),
        energy=_energy_state(extra.get("energy_bands")),
        kick_event=float(extra.get("line_kick_event_strength", 0.0) or 0.0),
        snare_event=float(
            extra.get("line_snare_event_strength", 0.0) or 0.0
        ),
        transient_width_mix=float(
            extra.get("osc_transient_width_mix", 0.35)
        ),
        base_sensitivity=float(extra.get("line_sensitivity", 3.0) or 3.0),
        animation_enabled=bool(extra.get("rainbow_enabled", False)),
    )
    extra["_quick_resolved_waveform"] = resolved.waveform
    extra["_quick_resolved_waveform_count"] = resolved.waveform_count
    extra["_quick_resolved_energy"] = resolved.energy
    extra["_quick_mode_changed"] = resolved.changed
    parameter_values = {
        name: value
        for name, value in extra.items()
        if not name.startswith("_quick_")
    }
    parameter_values["resolved_sensitivity"] = resolved.resolved_sensitivity
    return (
        OscilloscopeFrame(
            previous_waveform=resolved.previous_waveform,
            ghost_waveforms=(
                (resolved.previous_waveform,)
                if resolved.previous_waveform
                else ()
            ),
            animation_time=resolved.animation_time,
            parameters=_render_parameters(parameter_values),
        ),
        extra,
    )


def _capture_sine(
    widget: Any,
    engine: Any,
    context: _CaptureContext,
) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "sine_wave", engine)
    config_applier._append_line_mode_visual_extras(extra, widget, is_sine=True)
    extra["sine_wave_transient_width_mix"] = getattr(
        widget,
        "_sine_wave_transient_width_mix",
        0.4,
    )
    controller = getattr(widget, "runtime_controller", None)
    if controller is None:
        raise RuntimeError("Sine logical capture requires its runtime controller owner")
    runtime = controller.resolve_logical_mode_state("sine_wave", SineFrameRuntime)
    if not isinstance(runtime, SineFrameRuntime):
        raise TypeError("Sine logical mode state has the wrong type")
    resolved = runtime.resolve(
        now_ts=context.now_ts,
        runtime_generation=context.runtime_generation,
        engine_generation=context.engine_generation,
        activation_id=context.activation_id,
        source_generation=context.source_generation,
        source_activation_id=context.source_activation_id,
        playing=context.playing,
        energy=_energy_state(extra.get("energy_bands")),
        kick_event=float(extra.get("line_kick_event_strength", 0.0) or 0.0),
        snare_event=float(extra.get("line_snare_event_strength", 0.0) or 0.0),
        ghosting_enabled=bool(
            extra.get("sine_ghosting_enabled", False)
            and float(extra.get("sine_ghost_alpha", 0.0) or 0.0) > 0.001
        ),
        ghost_decay=float(extra.get("sine_ghost_decay", 0.3) or 0.3),
        line_count=int(extra.get("line_count", 1) or 1),
        line_speed=float(extra.get("line_speed", 0.5) or 0.5),
        travels=tuple(
            extra.get(name, 0)
            for name in (
                "sine_wave_travel",
                "sine_travel_line2",
                "sine_travel_line3",
                "sine_travel_line4",
                "sine_travel_line5",
                "sine_travel_line6",
            )
        ),
        line_shifts=tuple(
            extra.get(f"sine_line{index}_shift", 0.0)
            for index in range(1, 7)
        ),
        transient_width_mix=float(
            extra.get("sine_wave_transient_width_mix", 0.4)
        ),
        base_width_reaction=float(extra.get("sine_width_reaction", 0.0)),
        base_sensitivity=float(extra.get("line_sensitivity", 1.0) or 1.0),
        base_heartbeat=float(extra.get("heartbeat_intensity", 0.0) or 0.0),
        heartbeat_slider=float(extra.get("sine_heartbeat", 0.0) or 0.0),
    )
    extra["_quick_resolved_energy"] = resolved.energy
    extra["_quick_mode_changed"] = resolved.changed
    parameter_values = {
        name: value
        for name, value in extra.items()
        if not name.startswith("_quick_")
    }
    parameter_values["line_speed"] = resolved.line_speed
    for name, value in zip(
        (
            "sine_wave_travel",
            "sine_travel_line2",
            "sine_travel_line3",
            "sine_travel_line4",
            "sine_travel_line5",
            "sine_travel_line6",
        ),
        resolved.travels,
    ):
        parameter_values[name] = value
    for index, value in enumerate(resolved.line_shifts, start=1):
        parameter_values[f"sine_line{index}_shift"] = value
    parameter_values["resolved_sensitivity"] = resolved.sensitivity
    parameter_values["resolved_width_reaction"] = resolved.width_reaction
    parameter_values["wave_effect_gate"] = resolved.wave_effect_gate
    return (
        SineFrame(
            heartbeat_intensity=resolved.heartbeat_intensity,
            ghost_energy=resolved.ghost_energy,
            animation_time=resolved.animation_time,
            parameters=_render_parameters(parameter_values),
        ),
        extra,
    )


_BUBBLE_ARRAY_FIELDS = {
    "bubble_pos_data",
    "bubble_extra_data",
    "bubble_trail_data",
    "bubble_count",
}


def _capture_bubble(
    widget: Any,
    engine: Any,
    _context: _CaptureContext,
) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "bubble", engine)
    config_applier._append_bubble_visual_extras(extra, widget)
    controller = getattr(widget, "runtime_controller", None)
    if controller is None:
        raise RuntimeError("Bubble logical capture requires its runtime controller")
    runtime = controller.resolve_logical_mode_state(
        "bubble",
        BubbleFrameRuntime,
    )
    if not isinstance(runtime, BubbleFrameRuntime):
        raise TypeError("Bubble logical mode state has the wrong type")
    resolved = runtime.latest
    extra["_quick_protected_edges"] = resolved.protected_edges
    extra["_quick_bubble_identity_admitted"] = bool(
        resolved.engine_generation >= 0 and resolved.activation_id >= 0
    )
    extra["_quick_bubble_runtime_generation"] = resolved.runtime_generation
    extra["_quick_bubble_engine_generation"] = resolved.engine_generation
    extra["_quick_bubble_activation_id"] = resolved.activation_id
    extra["_quick_bubble_source_generation"] = resolved.source_generation
    extra["_quick_bubble_source_activation_id"] = (
        resolved.source_activation_id
    )
    extra["_quick_bubble_source_timestamp"] = resolved.source_timestamp
    extra["_quick_bubble_logical_timestamp"] = resolved.simulation_timestamp
    extra["_quick_bubble_playing"] = resolved.playing
    return (
        BubbleFrame(
            positions=resolved.positions,
            extras=resolved.extras,
            trails=resolved.trails,
            bubble_count=resolved.bubble_count,
            source_timestamp=resolved.source_timestamp,
            simulation_timestamp=resolved.simulation_timestamp,
            parameters=_render_parameters(
                {
                    name: value
                    for name, value in extra.items()
                    if not name.startswith("_quick_")
                },
                omit=_BUBBLE_ARRAY_FIELDS,
            ),
        ),
        extra,
    )


_DEVCURVE_ARRAY_FIELDS = {
    "devcurve_curve_bass",
    "devcurve_curve_vocals",
    "devcurve_curve_mids",
    "devcurve_curve_transients",
    "devcurve_specular_slot0",
    "devcurve_specular_slot1",
    "devcurve_specular_slot2",
}


def _capture_devcurve(
    widget: Any,
    engine: Any,
    _context: _CaptureContext,
) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "devcurve", engine)
    config_applier._append_devcurve_visual_extras(extra, widget)
    curves = tuple(
        (
            name,
            tuple(extra.get(f"devcurve_curve_{name}", ()) or ()),
        )
        for name in ("bass", "vocals", "mids", "transients")
    )
    specular_slots = tuple(
        tuple(extra.get(f"devcurve_specular_slot{index}", ()) or ())
        for index in range(3)
    )
    return (
        DevCurveFrame(
            curves=curves,
            draw_order=tuple(
                getattr(
                    widget,
                    "_devcurve_draw_order",
                    ("bass", "vocals", "mids", "transients"),
                )
            ),
            foreground_layer_id=int(
                -1
                if extra.get("devcurve_foreground_layer_id") is None
                else extra["devcurve_foreground_layer_id"]
            ),
            specular_slots=specular_slots,
            parameters=_render_parameters(extra, omit=_DEVCURVE_ARRAY_FIELDS),
        ),
        extra,
    )


ModeCapture = Callable[
    [Any, Any, _CaptureContext],
    tuple[ModeFrame, dict[str, Any]],
]

_MODE_CAPTURE: dict[str, ModeCapture] = {
    "spectrum": _capture_spectrum,
    "oscilloscope": _capture_oscilloscope,
    "sine_wave": _capture_sine,
    "bubble": _capture_bubble,
    "devcurve": _capture_devcurve,
}


def _common_style(widget: Any) -> dict[str, object]:
    return {
        "fill_color": getattr(widget, "_bar_fill_color", None),
        "border_color": getattr(widget, "_bar_border_color", None),
        "ghosting_enabled": bool(getattr(widget, "_ghosting_enabled", True)),
        "ghost_alpha": float(getattr(widget, "_ghost_alpha", 0.4)),
        "ghost_decay": float(getattr(widget, "_ghost_decay_rate", -1.0)),
        "single_piece": bool(getattr(widget, "_spectrum_single_piece", False)),
        "border_radius": float(getattr(widget, "_spectrum_border_radius", 0.0)),
    }


def capture_legacy_visualizer_logical_frame(
    widget: Any,
    *,
    now_ts: float,
    changed: bool,
    mode_reveal_ready: bool,
    present_frame: bool = True,
    protected_edges: Sequence[VisualizerProtectedEdge] = (),
) -> VisualizerLogicalFrame:
    """Copy one completed old-runtime logical step into immutable state."""

    mode_id = mode_capabilities.widget_mode_key(widget)
    capture = _MODE_CAPTURE.get(mode_id)
    if capture is None:
        raise ValueError(f"unsupported visualizer mode: {mode_id}")

    engine = getattr(widget, "_engine", None)
    runtime_generation = coerce_identity(
        getattr(widget, "_runtime_generation", None)
    )
    engine_generation = _identity_from_engine(
        engine,
        "get_generation_id",
        getattr(widget, "_last_engine_generation_seen", None),
    )
    activation_id = _identity_from_engine(
        engine,
        "get_activation_id",
        getattr(widget, "_last_engine_activation_seen", None),
    )
    source_generation, source_activation, source_timestamp = _source_identity(
        widget,
        engine,
        mode_id,
    )
    context = _CaptureContext(
        now_ts=float(now_ts),
        runtime_generation=runtime_generation,
        engine_generation=engine_generation,
        activation_id=activation_id,
        source_generation=source_generation,
        source_activation_id=source_activation,
        playing=bool(getattr(widget, "_spotify_playing", False)),
        first_frame=not bool(getattr(widget, "_has_pushed_first_frame", False)),
    )
    mode_state, extra = capture(widget, engine, context)
    playing = bool(getattr(widget, "_spotify_playing", False))
    logical_timestamp = float(now_ts)
    if bool(extra.get("_quick_bubble_identity_admitted", False)):
        runtime_generation = coerce_identity(
            extra.get("_quick_bubble_runtime_generation")
        )
        engine_generation = coerce_identity(
            extra.get("_quick_bubble_engine_generation")
        )
        activation_id = coerce_identity(
            extra.get("_quick_bubble_activation_id")
        )
        source_generation = coerce_identity(
            extra.get("_quick_bubble_source_generation")
        )
        source_activation = coerce_identity(
            extra.get("_quick_bubble_source_activation_id")
        )
        source_timestamp = (
            float(extra.get("_quick_bubble_source_timestamp", 0.0) or 0.0)
            if source_generation >= 0 and source_activation >= 0
            else None
        )
        logical_timestamp = float(
            extra.get("_quick_bubble_logical_timestamp", now_ts)
        )
        playing = bool(extra.get("_quick_bubble_playing", False))

    waveform = tuple(
        extra.get(
            "_quick_resolved_waveform",
            extra.get("waveform", ()) or (),
        )
    )
    waveform_count = int(
        extra.get(
            "_quick_resolved_waveform_count",
            extra.get("waveform_count", len(waveform)) or 0,
        )
    )
    common = VisualizerCommonState(
        bars=tuple(
            extra.get(
                "_quick_resolved_bars",
                getattr(widget, "_display_bars", ()) or (),
            )
        ),
        bar_count=int(getattr(widget, "_bar_count", 0) or 0),
        waveform=waveform,
        waveform_count=waveform_count,
        energy=_energy_state(
            extra.get(
                "_quick_resolved_energy",
                extra.get("energy_bands"),
            )
        ),
        transient=_transient_state(extra.get("transient_energy")),
        style=freeze_render_fields(_common_style(widget)),
    )
    return VisualizerLogicalFrame(
        runtime_generation=runtime_generation,
        engine_generation=engine_generation,
        activation_id=activation_id,
        source_generation=source_generation,
        source_activation_id=source_activation,
        mode_id=mode_id,
        playing=playing,
        logical_timestamp=logical_timestamp,
        source_timestamp=source_timestamp,
        changed=bool(
            changed
            or extra.get("_quick_spectrum_changed", False)
            or extra.get("_quick_mode_changed", False)
        ),
        present_frame=bool(present_frame),
        mode_reveal_ready=bool(mode_reveal_ready),
        common=common,
        mode_state=mode_state,
        protected_edges=(
            tuple(protected_edges)
            + tuple(extra.get("_quick_protected_edges", ()) or ())
        ),
    )


__all__ = ["capture_legacy_visualizer_logical_frame"]

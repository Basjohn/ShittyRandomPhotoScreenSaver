"""Temporary old-presenter capture into the immutable Quick-era contract.

This adapter exists only while the QWidget/QRhiWidget presenter is still the
live production path.  It copies the authored logical result and current
visual parameters into detached immutable values.  Quick render code must
consume those values, never the legacy widget or its compositor overlay.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from widgets.spotify_visualizer import config_applier, mode_capabilities
from widgets.spotify_visualizer.logical_runtime import coerce_identity
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
    if mode_id in {"oscilloscope", "sine_wave"}:
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


def _capture_spectrum(widget: Any, engine: Any) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "spectrum", engine)
    return SpectrumFrame(parameters=_render_parameters(extra)), extra


def _capture_oscilloscope(
    widget: Any,
    engine: Any,
) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "oscilloscope", engine)
    config_applier._append_line_mode_visual_extras(extra, widget, is_sine=False)
    return OscilloscopeFrame(parameters=_render_parameters(extra)), extra


def _capture_sine(widget: Any, engine: Any) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "sine_wave", engine)
    config_applier._append_line_mode_visual_extras(extra, widget, is_sine=True)
    return (
        SineFrame(
            heartbeat_intensity=float(
                getattr(widget, "_heartbeat_intensity", 0.0)
            ),
            parameters=_render_parameters(extra),
        ),
        extra,
    )


_BUBBLE_ARRAY_FIELDS = {
    "bubble_pos_data",
    "bubble_extra_data",
    "bubble_trail_data",
    "bubble_count",
}


def _capture_bubble(widget: Any, engine: Any) -> tuple[ModeFrame, dict[str, Any]]:
    extra = _base_extras(widget, "bubble", engine)
    config_applier._append_bubble_visual_extras(extra, widget)
    return (
        BubbleFrame(
            positions=tuple(extra.get("bubble_pos_data", ()) or ()),
            extras=tuple(extra.get("bubble_extra_data", ()) or ()),
            trails=tuple(extra.get("bubble_trail_data", ()) or ()),
            bubble_count=int(extra.get("bubble_count", 0) or 0),
            source_timestamp=float(
                getattr(widget, "_bubble_visible_source_ts", 0.0) or 0.0
            ),
            simulation_timestamp=float(
                getattr(widget, "_bubble_visible_simulation_ts", 0.0) or 0.0
            ),
            parameters=_render_parameters(extra, omit=_BUBBLE_ARRAY_FIELDS),
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


def _capture_devcurve(widget: Any, engine: Any) -> tuple[ModeFrame, dict[str, Any]]:
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


ModeCapture = Callable[[Any, Any], tuple[ModeFrame, dict[str, Any]]]

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
    mode_state, extra = capture(widget, engine)
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

    waveform = tuple(extra.get("waveform", ()) or ())
    waveform_count = int(extra.get("waveform_count", len(waveform)) or 0)
    common = VisualizerCommonState(
        bars=tuple(getattr(widget, "_display_bars", ()) or ()),
        bar_count=int(getattr(widget, "_bar_count", 0) or 0),
        waveform=waveform,
        waveform_count=waveform_count,
        energy=_energy_state(extra.get("energy_bands")),
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
        playing=bool(getattr(widget, "_spotify_playing", False)),
        logical_timestamp=float(now_ts),
        source_timestamp=source_timestamp,
        changed=bool(changed),
        present_frame=bool(present_frame),
        mode_reveal_ready=bool(mode_reveal_ready),
        common=common,
        mode_state=mode_state,
        protected_edges=tuple(protected_edges),
    )


__all__ = ["capture_legacy_visualizer_logical_frame"]

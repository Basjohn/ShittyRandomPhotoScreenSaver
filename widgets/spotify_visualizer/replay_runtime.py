"""Deterministic, logical-state replay through the production visualizer tick.

This module intentionally does not implement a second visualizer.  It supplies
immutable post-DSP feature lanes to a real beat engine, calls
``tick_pipeline.on_tick`` on a real ``SpotifyVisualizerWidget``, and captures
the state accepted by a real ``SpotifyBarsGLOverlay.set_state`` implementation.
OpenGL presentation is suppressed; overlay state preparation is not.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import json
import math
import random
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from unittest.mock import patch

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

from core.settings.models import SpotifyVisualizerSettings
from core.threading.manager import TaskResult
from rendering.spotify_widget_creators import apply_spotify_vis_model_config
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.feature_frame import (
    FeatureClip,
    FeatureFrame,
    SUPPORTED_MODES,
    canonical_json,
)
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget


REPLAY_SCHEMA_VERSION = 1
BASELINE_BEHAVIOR_COMMIT = "00edb57a3076b845cb8ee4b6cb7f36ea83411f0c"
DEFAULT_RANDOM_SEED = 0x53525053
MODE_ORDER = ("spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve")
_MODE_ENUM = {
    "spectrum": VisualizerMode.SPECTRUM,
    "oscilloscope": VisualizerMode.OSCILLOSCOPE,
    "sine_wave": VisualizerMode.SINE_WAVE,
    "bubble": VisualizerMode.BUBBLE,
    "devcurve": VisualizerMode.DEVCURVE,
}


def _round_float(value: Any, digits: int = 7) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number) or abs(number) < 0.5 * (10.0 ** -digits):
        return 0.0
    return round(number, digits)


def _normalise(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return _round_float(value)
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return _normalise(asdict(value))
    return str(value)


def stable_digest(value: Any) -> str:
    """Return the stable SHA-256 digest of normalized JSON-ready state."""
    return hashlib.sha256(canonical_json(_normalise(value))).hexdigest()


class _ReplayClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.now


@contextmanager
def deterministic_runtime(seed: int = DEFAULT_RANDOM_SEED):
    """Scope deterministic wall/monotonic clocks and the global RNG.

    ``perf_counter`` is deliberately untouched because worker-duration and
    diagnostic timing are outside the fidelity contract.
    """
    clock = _ReplayClock()
    random_state = random.getstate()
    random.seed(int(seed))
    try:
        with patch.object(time, "time", clock.time), patch.object(time, "monotonic", clock.monotonic):
            yield clock
    finally:
        random.setstate(random_state)


class ImmediateComputeThreadManager:
    """Narrow deterministic compute executor preserving callback publication."""

    def __init__(self) -> None:
        self.submissions: list[str] = []

    def submit_compute_task(
        self,
        worker,
        *args,
        callback=None,
        task_id: str | None = None,
        category: str = "uncategorized",
        **kwargs,
    ) -> str:
        resolved_id = task_id or f"replay_compute_{len(self.submissions)}"
        self.submissions.append(str(category))
        try:
            result = worker(*args, **kwargs)
            task_result = TaskResult(success=True, result=result, task_id=resolved_id)
        except Exception as exc:  # production callback receives failures too
            task_result = TaskResult(success=False, error=exc, task_id=resolved_id)
        if callback is not None:
            callback(task_result)
        return resolved_id

    def cancel_task(self, _task_id: str) -> bool:
        return False


def _bands(source: Any) -> EnergyBands:
    return EnergyBands(
        bass=float(source.bass),
        mid=float(source.mid),
        high=float(source.high),
        overall=float(source.overall),
    )


class ReplayBeatEngine(_SpotifyBeatEngine):
    """Real beat engine with immutable replay-only post-DSP lane getters."""

    def __init__(self, bar_count: int) -> None:
        super().__init__(bar_count)
        self._replay_pre_agc = EnergyBands()
        self._replay_bubble = EnergyBands()
        self._replay_transient = TransientEnergyBands()

    def ensure_started(self) -> None:
        """Keep the external audio producer inert during feature replay."""
        return None

    def accept_feature_frame(self, frame: FeatureFrame) -> bool:
        lanes = frame.energy
        self._replay_pre_agc = _bands(lanes.pre_agc)
        self._replay_bubble = _bands(lanes.bubble)
        transient = lanes.transient
        onset_map = {
            "bass": "kick",
            "mid": "snare",
            "high": "vocal_swell",
            "broadband": "snare",
        }
        self._replay_transient = TransientEnergyBands(
            bass_transient=float(transient.bass),
            mid_transient=float(transient.mid),
            high_transient=float(transient.high),
            onset_detected=bool(transient.onset_detected),
            onset_type=onset_map.get(str(transient.onset_type), "") if transient.onset_detected else "",
            onset_strength=float(transient.onset_strength),
        )
        waveform = list(frame.waveform)
        raw_bars = list(frame.raw_bars)
        if len(raw_bars) != self._bar_count:
            source_last = len(raw_bars) - 1
            target_last = self._bar_count - 1
            if target_last <= 0:
                raw_bars = [raw_bars[0]]
            else:
                resampled = []
                for index in range(self._bar_count):
                    source_position = index * source_last / target_last
                    lower = int(source_position)
                    upper = min(source_last, lower + 1)
                    fraction = source_position - lower
                    resampled.append(
                        raw_bars[lower]
                        + (raw_bars[upper] - raw_bars[lower]) * fraction
                    )
                raw_bars = resampled
        return self.accept_analysis_frame(
            raw_bars,
            frame.timestamp_us / 1_000_000.0,
            activation_id=self.get_activation_id(),
            waveform=waveform,
            waveform_count=len(waveform),
            energy_override=_bands(lanes.continuous),
        )

    def get_pre_agc_energy_bands(self) -> EnergyBands:
        return self._replay_pre_agc

    def get_bubble_energy_bands(self) -> EnergyBands:
        return self._replay_bubble

    def get_transient_energy_bands(self) -> TransientEnergyBands:
        return self._replay_transient

    def get_event_scheduler(self):
        # Exact onset authority is carried by the immutable transient frame.
        # Returning no scheduler avoids replaying stale live-worker events.
        return None


class LogicalSpotifyBarsGLOverlay(SpotifyBarsGLOverlay):
    """Production overlay state logic with all GL presentation suppressed."""

    def show(self) -> None:  # type: ignore[override]
        return None

    def hide(self) -> None:  # type: ignore[override]
        return None

    def isVisible(self) -> bool:  # type: ignore[override]
        return False

    def update(self, *args) -> None:  # type: ignore[override]
        del args

    def repaint(self, *args) -> None:  # type: ignore[override]
        del args


class ReplayDisplay(QWidget):
    """Display parent that owns and captures a real logical GL overlay."""

    def __init__(self, initial_mode: str) -> None:
        super().__init__()
        self.resize(640, 240)
        self._spotify_bars_overlay = LogicalSpotifyBarsGLOverlay(self, initial_mode=initial_mode)
        self.logical_pushes: list[dict[str, Any]] = []

    def push_spotify_visualizer_frame(self, **kwargs) -> bool:
        rect = kwargs.pop("rect", QRect(0, 0, self.width(), self.height()))
        self._spotify_bars_overlay.set_state(rect=rect, visible=True, **kwargs)
        self.logical_pushes.append(capture_overlay_state(self._spotify_bars_overlay))
        return True

    def transition_context(self) -> dict[str, bool]:
        return {"running": False}


def _array(obj: Any, name: str) -> list[Any]:
    value = getattr(obj, name, [])
    try:
        return list(value)
    except TypeError:
        return []


def _energy_payload(value: Any) -> dict[str, float]:
    return {
        name: _round_float(getattr(value, name, 0.0))
        for name in ("bass", "mid", "high", "overall")
    }


def capture_overlay_state(overlay: SpotifyBarsGLOverlay) -> dict[str, Any]:
    """Capture stable mode-neutral and mode-owned logical overlay state."""
    mode = str(getattr(overlay, "_vis_mode", "spectrum"))
    common: dict[str, Any] = {
        "mode": mode,
        "bars": _array(overlay, "_bars"),
        "waveform": _array(overlay, "_waveform"),
        "energy": _energy_payload(getattr(overlay, "_energy_bands", None)),
        "activation_id": int(getattr(overlay, "_activation_id", -1) or 0),
        "engine_generation": int(getattr(overlay, "_engine_generation", -1) or 0),
        "playing": bool(getattr(overlay, "_playing", False)),
    }
    if mode == "spectrum":
        common["spectrum"] = {
            "peaks": _array(overlay, "_peaks"),
            "single_piece": bool(getattr(overlay, "_single_piece", False)),
            "solid_display_segments": _array(
                overlay,
                "_spectrum_solid_display_segments",
            ),
            "solid_display_values": _array(
                overlay,
                "_spectrum_solid_display_segment_values",
            ),
            "solid_last_update_ts": _array(
                overlay,
                "_spectrum_solid_last_update_ts",
            ),
        }
    elif mode == "oscilloscope":
        common["oscilloscope"] = {
            "ghost_waveform": _array(overlay, "_prev_waveform"),
            "ghost_ring": _array(overlay, "_ghost_waveform_ring"),
            "ghost_ring_index": int(getattr(overlay, "_ghost_ring_idx", 0)),
            "waveform_count": int(getattr(overlay, "_waveform_count", 0)),
            "blend_alpha": _round_float(
                getattr(overlay, "_osc_last_waveform_blend_alpha", 0.0)
            ),
            "waveform_delta": _round_float(
                getattr(overlay, "_osc_last_waveform_delta", 0.0)
            ),
            "transient_width_drive": _round_float(
                getattr(overlay, "_osc_last_transient_width_drive", 0.0)
            ),
            "line_energy": {
                "bass": _round_float(
                    getattr(overlay, "_line_smoothed_bass", 0.0)
                ),
                "mid": _round_float(
                    getattr(overlay, "_line_smoothed_mid", 0.0)
                ),
                "high": _round_float(
                    getattr(overlay, "_line_smoothed_high", 0.0)
                ),
            },
            "accumulated_time": _round_float(
                getattr(overlay, "_accumulated_time", 0.0)
            ),
            "kick_envelope": _round_float(getattr(overlay, "_line_kick_event_envelope", 0.0)),
            "snare_envelope": _round_float(getattr(overlay, "_line_snare_event_envelope", 0.0)),
        }
    elif mode == "sine_wave":
        common["sine_wave"] = {
            "peak_bass": _round_float(getattr(overlay, "_sine_peak_bass", 0.0)),
            "peak_mid": _round_float(getattr(overlay, "_sine_peak_mid", 0.0)),
            "peak_high": _round_float(getattr(overlay, "_sine_peak_high", 0.0)),
            "peak_hold": _round_float(getattr(overlay, "_sine_peak_hold_remaining", 0.0)),
            "heartbeat": _round_float(
                getattr(overlay, "_heartbeat_intensity", 0.0)
            ),
            "line_energy": {
                "bass": _round_float(
                    getattr(overlay, "_line_smoothed_bass", 0.0)
                ),
                "mid": _round_float(
                    getattr(overlay, "_line_smoothed_mid", 0.0)
                ),
                "high": _round_float(
                    getattr(overlay, "_line_smoothed_high", 0.0)
                ),
            },
            "accumulated_time": _round_float(
                getattr(overlay, "_accumulated_time", 0.0)
            ),
        }
    elif mode == "bubble":
        common["bubble"] = {
            "count": int(getattr(overlay, "_bubble_count", 0)),
            "positions": _array(overlay, "_bubble_pos_data"),
            "extra": _array(overlay, "_bubble_extra_data"),
            "trails": _array(overlay, "_bubble_trail_data"),
            "trail_strength": _round_float(getattr(overlay, "_bubble_trail_strength", 0.0)),
            "tail_opacity": _round_float(getattr(overlay, "_bubble_tail_opacity", 0.0)),
        }
    elif mode == "devcurve":
        common["devcurve"] = {
            "sample_count": int(getattr(overlay, "_devcurve_sample_count", 0)),
            "bass": _array(overlay, "_devcurve_curve_bass"),
            "vocals": _array(overlay, "_devcurve_curve_vocals"),
            "mids": _array(overlay, "_devcurve_curve_mids"),
            "transients": _array(overlay, "_devcurve_curve_transients"),
            "foreground_layer_id": int(
                getattr(overlay, "_devcurve_foreground_layer_id", -1)
            ),
            "draw_order": _array(overlay, "_devcurve_draw_order"),
            "specular_slots": [
                _array(overlay, "_devcurve_specular_slot0"),
                _array(overlay, "_devcurve_specular_slot1"),
                _array(overlay, "_devcurve_specular_slot2"),
            ],
        }
    return _normalise(common)


_BUBBLE_PARTICLE_FIELDS = (
    "x",
    "y",
    "vx",
    "vy",
    "impulse_vx",
    "impulse_vy",
    "radius",
    "display_radius",
    "pulse_energy",
    "size_gate_energy",
    "alpha",
    "age",
    "rotation",
    "is_big",
    "promoted",
    "popping",
    "exiting",
    "trail_tail_x",
    "trail_tail_y",
    "trail_strength",
    "trail_ready",
)


def _capture_bubble_simulation(widget: SpotifyVisualizerWidget) -> dict[str, Any]:
    simulation = getattr(widget, "_bubble_simulation", None)
    if simulation is None:
        return {}

    particles = [
        {
            name: getattr(particle, name)
            for name in _BUBBLE_PARTICLE_FIELDS
        }
        for particle in getattr(simulation, "_bubbles", ())
    ]
    return {
        "time": getattr(simulation, "_time", 0.0),
        "smoothed_speed_energy": getattr(
            simulation,
            "_smoothed_speed_energy",
            0.0,
        ),
        "sustained_loud_energy": getattr(
            simulation,
            "_sustained_loud_energy",
            0.0,
        ),
        "render_body_energy": getattr(
            simulation,
            "_render_body_energy",
            0.0,
        ),
        "hot_crest_energy": getattr(simulation, "_hot_crest_energy", 0.0),
        "burst_active": getattr(simulation, "_burst_active", False),
        "burst_cooldown": getattr(simulation, "_burst_cooldown", 0.0),
        "group_drift": [
            getattr(simulation, "_group_drift_dx", 0.0),
            getattr(simulation, "_group_drift_dy", 0.0),
        ],
        "particles": particles,
    }


def _capture_devcurve_runtime(widget: SpotifyVisualizerWidget) -> dict[str, Any]:
    state = getattr(widget, "_devcurve_runtime_state", None)
    if state is None:
        return {}
    return {
        "phase": getattr(state, "phase", 0.0),
        "smooth_energy": dict(getattr(state, "smooth_energy", {})),
        "previous_layers": dict(getattr(state, "previous_layers", {})),
        "smoothness_max_step": getattr(state, "smoothness_max_step", 0.0),
        "active_amplitude": getattr(state, "active_amplitude", 0.0),
        "idle_amplitude": getattr(state, "idle_amplitude", 0.0),
        "foreground_travel_rate": getattr(
            state,
            "foreground_travel_rate",
            0.0,
        ),
        "specular_travel_rate": getattr(
            state,
            "specular_travel_rate",
            0.0,
        ),
        "specular_streams": list(getattr(state, "specular_streams", ())),
        "specular_spawn_counter": getattr(
            state,
            "specular_spawn_counter",
            0,
        ),
        "draw_order": list(getattr(widget, "_devcurve_draw_order", ())),
        "foreground_layer": getattr(widget, "_devcurve_foreground_layer", ""),
    }


def _widget_state(
    widget: SpotifyVisualizerWidget,
    frame: FeatureFrame,
    *,
    published: bool,
) -> dict[str, Any]:
    engine = widget._engine
    state = {
        "timestamp_us": frame.timestamp_us,
        "mode": frame.mode,
        "control_event": frame.control_event,
        "input_playing": frame.playing,
        "input_visible": frame.visible,
        "published": published,
        "raw_bars": list(frame.raw_bars),
        "accepted_raw_bars": list(getattr(engine, "_latest_bars", ()) or ()),
        "smoothed_bars": engine.get_smoothed_bars() if engine is not None else [],
        "display_bars": list(widget._display_bars),
        "waveform": engine.get_waveform() if engine is not None else [],
        "energy_lanes": _normalise(asdict(frame.energy)),
        "activation_id": engine.get_activation_id() if engine is not None else -1,
        "generation_id": engine.get_generation_id() if engine is not None else -1,
    }
    if frame.mode == "bubble":
        state["bubble_simulation"] = _capture_bubble_simulation(widget)
    elif frame.mode == "devcurve":
        state["devcurve_runtime"] = _capture_devcurve_runtime(widget)
    return _normalise(state)


def _apply_authored_preset_zero(widget: SpotifyVisualizerWidget, mode: str) -> None:
    model = SpotifyVisualizerSettings.from_mapping(
        {"mode": mode, f"preset_{mode}": 0}
    )
    widget.set_settings_model(model, apply_now=False)
    widget.set_visualization_mode(_MODE_ENUM[mode])
    apply_spotify_vis_model_config(widget, model, apply_mode=False)


def _prepare_widget(mode: str) -> tuple[ReplayDisplay, SpotifyVisualizerWidget, ReplayBeatEngine]:
    if QApplication.instance() is None:
        QApplication([])
    display = ReplayDisplay(mode)
    widget = SpotifyVisualizerWidget(display, bar_count=32, initial_mode=mode)
    widget.setGeometry(QRect(0, 0, 640, 240))
    engine = ReplayBeatEngine(widget._bar_count)
    manager = ImmediateComputeThreadManager()
    engine.set_thread_manager(manager)
    widget._engine = engine
    widget._bind_engine_aliases(engine)
    widget._thread_manager = manager
    widget._enabled = True
    widget._spotify_playing = True
    widget._has_seen_media = True
    widget._has_pushed_first_frame = False
    widget._waiting_for_fresh_engine_frame = False
    widget._waiting_for_fresh_frame = False
    widget._mode_transition_phase = 0
    widget._mode_teardown_block_until_ready = False
    widget._mode_transition_ready = True
    widget._get_transition_context = lambda _parent: {"running": False}
    widget._pause_timer_during_transition = lambda _active: None
    widget._update_timer_interval = lambda _fps: None
    widget.update = lambda *args: None
    widget._log_tick_spike = lambda _dt, _ctx: None
    _apply_authored_preset_zero(widget, mode)
    # Establish the same non-zero activation/generation boundary as a real
    # startup before the first authoritative feature frame is accepted.
    engine.reset_smoothing_state()
    widget._track_engine_generation(engine)
    widget._waiting_for_fresh_engine_frame = True
    widget._waiting_for_fresh_frame = True
    widget._mode_teardown_block_until_ready = False
    return display, widget, engine


def _presentation_opportunities(
    frames: Sequence[Mapping[str, Any]],
    *,
    presentation_hz: float | None,
    presentation_intervals_ms: Sequence[int],
    presentation_stalls_ms: Sequence[int],
) -> list[int]:
    if not frames:
        return []

    start_us = int(frames[0]["timestamp_us"])
    end_us = int(frames[-1]["timestamp_us"])
    opportunities: list[int] = []

    if presentation_intervals_ms:
        current_us = start_us
        interval_index = 0
        positive_intervals = [
            max(1, int(interval_ms))
            for interval_ms in presentation_intervals_ms
        ]
        while current_us <= end_us:
            opportunities.append(current_us)
            current_us += positive_intervals[
                interval_index % len(positive_intervals)
            ] * 1_000
            interval_index += 1
    elif presentation_hz is not None and presentation_hz > 0.0:
        step_us = 1_000_000.0 / float(presentation_hz)
        opportunity = float(start_us)
        while opportunity <= end_us:
            opportunities.append(int(round(opportunity)))
            opportunity += step_us
    else:
        opportunities = [int(frame["timestamp_us"]) for frame in frames]

    if presentation_stalls_ms:
        span_us = max(1, end_us - start_us)
        for stall_index, stall_ms in enumerate(presentation_stalls_ms):
            stall_start_us = start_us + int(
                span_us * (stall_index + 1) / (len(presentation_stalls_ms) + 1)
            )
            stall_end_us = stall_start_us + max(0, int(stall_ms)) * 1_000
            opportunities = [
                opportunity
                for opportunity in opportunities
                if not stall_start_us <= opportunity < stall_end_us
            ]
            opportunities.append(stall_end_us)

    opportunities.append(end_us)
    return sorted(set(opportunities))


def sample_presentation_trace(
    frames: Sequence[Mapping[str, Any]],
    *,
    presentation_hz: float | None = None,
    presentation_intervals_ms: Sequence[int] = (),
    presentation_stalls_ms: Sequence[int] = (),
) -> list[dict[str, Any]]:
    """Sample latest completed logical state at independent paint opportunities."""
    opportunities = _presentation_opportunities(
        frames,
        presentation_hz=presentation_hz,
        presentation_intervals_ms=presentation_intervals_ms,
        presentation_stalls_ms=presentation_stalls_ms,
    )
    trace: list[dict[str, Any]] = []
    source_index = -1
    for opportunity_us in opportunities:
        while (
            source_index + 1 < len(frames)
            and int(frames[source_index + 1]["timestamp_us"])
            <= opportunity_us
        ):
            source_index += 1
        if source_index < 0:
            continue
        source = frames[source_index]
        source_timestamp_us = int(source["timestamp_us"])
        trace.append(
            {
                "opportunity_us": opportunity_us,
                "source_index": source_index,
                "source_timestamp_us": source_timestamp_us,
                "scene_age_us": opportunity_us - source_timestamp_us,
                "state_digest": stable_digest(source),
            }
        )
    return trace

def replay_clip(
    clip: FeatureClip,
    *,
    presentation_hz: float | None = None,
    presentation_intervals_ms: Sequence[int] = (),
    presentation_stalls_ms: Sequence[int] = (),
    seed: int = DEFAULT_RANDOM_SEED,
    source_clip_name: str | None = None,
    source_input_sha256: str | None = None,
) -> dict[str, Any]:
    """Replay one feature clip and return deterministic JSON-ready output.

    Presentation opportunities are deliberately separate from logical ticks.
    They sample the latest completed state after simulation, so paint cadence
    and deliberate stalls cannot feed back into the produced logical series.
    """
    first_mode = clip.frames[0].mode
    if first_mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported initial mode: {first_mode}")
    display: ReplayDisplay | None = None
    widget: SpotifyVisualizerWidget | None = None
    frames_out: list[dict[str, Any]] = []
    with deterministic_runtime(seed) as clock:
        display, widget, engine = _prepare_widget(first_mode)
        active_mode = first_mode
        for feature in clip.frames:
            clock.now = feature.timestamp_us / 1_000_000.0
            if feature.control_event == "mode_switch" or feature.mode != active_mode:
                _apply_authored_preset_zero(widget, feature.mode)
                active_mode = feature.mode
                widget._track_engine_generation(engine)
                widget._waiting_for_fresh_engine_frame = True
                widget._waiting_for_fresh_frame = True
                widget._mode_teardown_block_until_ready = False
            widget._enabled = bool(feature.visible)
            widget._spotify_playing = bool(feature.playing)
            engine._is_spotify_playing = bool(feature.playing)
            engine._play_ramp_start_ts = 0.0
            if not engine.accept_feature_frame(feature):
                raise ValueError(f"engine rejected feature frame at {feature.timestamp_us}us")
            before_pushes = len(display.logical_pushes)
            from widgets.spotify_visualizer import tick_pipeline

            tick_pipeline.on_tick(widget)
            overlay_state = (
                display.logical_pushes[-1]
                if len(display.logical_pushes) > before_pushes
                else capture_overlay_state(display._spotify_bars_overlay)
            )
            published = len(display.logical_pushes) > before_pushes
            state = _widget_state(widget, feature, published=published)
            state["overlay"] = overlay_state
            state["tick_path"] = "widgets.spotify_visualizer.tick_pipeline.on_tick"
            state["overlay_path"] = "SpotifyBarsGLOverlay.set_state"
            frames_out.append(_normalise(state))

    logical = {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "clip": clip.name,
        "source_clip": source_clip_name or clip.name,
        "input_sha256": source_input_sha256 or clip.sha256(),
        "effective_input_sha256": clip.sha256(),
        "frames": frames_out,
    }
    logical["metrics"] = calculate_metrics(frames_out)
    logical["digest"] = stable_digest(frames_out)
    presentation_trace = sample_presentation_trace(
        frames_out,
        presentation_hz=presentation_hz,
        presentation_intervals_ms=presentation_intervals_ms,
        presentation_stalls_ms=presentation_stalls_ms,
    )
    logical["presentation"] = {
        "hz": _round_float(presentation_hz or 0.0),
        "intervals_ms": [
            int(value) for value in presentation_intervals_ms
        ],
        "stalls_ms": [int(value) for value in presentation_stalls_ms],
        "logical_digest": logical["digest"],
        "trace": presentation_trace,
        "trace_digest": stable_digest(presentation_trace),
    }
    if widget is not None:
        widget.setParent(None)
        widget.deleteLater()
    if display is not None:
        display._spotify_bars_overlay.setParent(None)
        display._spotify_bars_overlay.deleteLater()
        display.deleteLater()
    return _normalise(logical)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def calculate_metrics(frames: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Calculate deterministic response, decay, continuity, and mode metrics."""
    timestamps = [int(frame.get("timestamp_us", 0)) for frame in frames]
    bar_means: list[float] = []
    bar_peaks: list[float] = []
    input_energy: list[float] = []
    centroids: list[float] = []
    waveform_values: list[float] = []
    state_derivatives: list[float] = []
    total_flux = 0.0
    integrated_energy = 0.0
    zero_crossings = 0
    beat_count = 0
    onset_count = 0
    previous_bars: list[float] | None = None
    mode_summary: dict[str, dict[str, float]] = {}
    bubble_speed_peak = 0.0
    bubble_radius_peak = 0.0
    bubble_particle_peak = 0
    bubble_mean_radii: list[float] = []
    bubble_centroids: list[tuple[float, float]] = []
    bubble_counts: list[int] = []

    for index, frame in enumerate(frames):
        bars = [float(value) for value in frame.get("display_bars", [])]
        bar_mean = _mean(bars)
        bar_peak = max(bars, default=0.0)
        bar_means.append(bar_mean)
        bar_peaks.append(bar_peak)

        continuous = frame.get("energy_lanes", {}).get("continuous", {})
        input_energy.append(float(continuous.get("overall", 0.0)))

        if previous_bars is not None:
            absolute_delta = sum(
                abs(current - previous)
                for current, previous in zip(bars, previous_bars)
            )
            total_flux += absolute_delta
            rms_delta = math.sqrt(
                _mean(
                    [
                        (current - previous) ** 2
                        for current, previous in zip(bars, previous_bars)
                    ]
                )
            )
            delta_seconds = max(
                1e-6,
                (timestamps[index] - timestamps[index - 1]) / 1_000_000.0,
            )
            state_derivatives.append(rms_delta / delta_seconds)
            integrated_energy += (
                bar_means[index - 1] + bar_mean
            ) * 0.5 * delta_seconds
        previous_bars = bars

        denominator = sum(bars)
        centroids.append(
            sum(position * value for position, value in enumerate(bars))
            / denominator
            if denominator > 0.0
            else 0.0
        )

        waveform = [float(value) for value in frame.get("waveform", [])]
        waveform_values.extend(waveform)
        zero_crossings += sum(
            1
            for left, right in zip(waveform, waveform[1:])
            if (left < 0.0 <= right) or (left > 0.0 >= right)
        )

        transient = frame.get("energy_lanes", {}).get("transient", {})
        if transient.get("onset_detected"):
            onset_count += 1
            if transient.get("onset_type") == "bass":
                beat_count += 1

        mode = str(frame.get("overlay", {}).get("mode", "unknown"))
        summary = mode_summary.setdefault(
            mode,
            {"frames": 0.0, "activity": 0.0},
        )
        summary["frames"] += 1.0
        summary["activity"] += bar_mean

        particles = frame.get("bubble_simulation", {}).get("particles", [])
        bubble_particle_peak = max(bubble_particle_peak, len(particles))
        bubble_counts.append(len(particles))
        frame_radii: list[float] = []
        frame_x: list[float] = []
        frame_y: list[float] = []
        for particle in particles:
            vx = float(particle.get("vx", 0.0)) + float(
                particle.get("impulse_vx", 0.0)
            )
            vy = float(particle.get("vy", 0.0)) + float(
                particle.get("impulse_vy", 0.0)
            )
            bubble_speed_peak = max(
                bubble_speed_peak,
                math.hypot(vx, vy),
            )
            radius = max(
                float(particle.get("display_radius", 0.0)),
                float(particle.get("radius", 0.0)),
            )
            bubble_radius_peak = max(bubble_radius_peak, radius)
            frame_radii.append(radius)
            frame_x.append(float(particle.get("x", 0.0)))
            frame_y.append(float(particle.get("y", 0.0)))
        bubble_mean_radii.append(_mean(frame_radii))
        bubble_centroids.append((_mean(frame_x), _mean(frame_y)))

    global_peak = max(bar_peaks, default=0.0)
    peak_index = bar_peaks.index(global_peak) if bar_peaks else 0
    input_peak = max(input_energy, default=0.0)
    input_start_index = next(
        (index for index, value in enumerate(input_energy) if value > 0.02),
        None,
    )
    response_index = None
    if input_start_index is not None:
        response_index = next(
            (
                index
                for index in range(input_start_index, len(bar_peaks))
                if bar_peaks[index] > 0.02
            ),
            None,
        )

    response_latency_ms = -1.0
    time_to_peak_ms = -1.0
    attack_slope_per_s = 0.0
    if input_start_index is not None and timestamps:
        if response_index is not None:
            response_latency_ms = (
                timestamps[response_index] - timestamps[input_start_index]
            ) / 1_000.0
        if peak_index >= input_start_index:
            time_to_peak_ms = (
                timestamps[peak_index] - timestamps[input_start_index]
            ) / 1_000.0
            if time_to_peak_ms > 0.0:
                attack_seconds = time_to_peak_ms / 1_000.0
            elif input_start_index + 1 < len(timestamps):
                attack_seconds = max(
                    1e-6,
                    (
                        timestamps[input_start_index + 1]
                        - timestamps[input_start_index]
                    )
                    / 1_000_000.0,
                )
            else:
                attack_seconds = 1e-6
            attack_slope_per_s = global_peak / attack_seconds

    half_peak = global_peak * 0.5
    decay_frames = 0
    decay_to_half_ms = -1.0
    if global_peak > 0.0:
        for offset, value in enumerate(bar_peaks[peak_index + 1 :], start=1):
            if value <= half_peak:
                decay_frames = offset
                decay_to_half_ms = (
                    timestamps[peak_index + offset] - timestamps[peak_index]
                ) / 1_000.0
                break

    settling_time_ms = -1.0
    settling_threshold = max(0.01, global_peak * 0.05)
    for index in range(peak_index, len(bar_peaks)):
        if all(value <= settling_threshold for value in bar_peaks[index:]):
            settling_time_ms = (
                timestamps[index] - timestamps[peak_index]
            ) / 1_000.0
            break

    for summary in mode_summary.values():
        summary["activity"] = _round_float(
            summary["activity"] / max(1.0, summary["frames"])
        )
        summary["frames"] = int(summary["frames"])

    bubble_centroid_speed_peak = 0.0
    bubble_radius_change_peak_per_s = 0.0
    bubble_count_change_peak = 0
    for index in range(1, len(frames)):
        delta_seconds = max(
            1e-6,
            (timestamps[index] - timestamps[index - 1]) / 1_000_000.0,
        )
        bubble_count_change_peak = max(
            bubble_count_change_peak,
            abs(bubble_counts[index] - bubble_counts[index - 1]),
        )
        if bubble_counts[index] and bubble_counts[index - 1]:
            previous_centroid = bubble_centroids[index - 1]
            current_centroid = bubble_centroids[index]
            bubble_centroid_speed_peak = max(
                bubble_centroid_speed_peak,
                math.hypot(
                    current_centroid[0] - previous_centroid[0],
                    current_centroid[1] - previous_centroid[1],
                )
                / delta_seconds,
            )
            bubble_radius_change_peak_per_s = max(
                bubble_radius_change_peak_per_s,
                abs(
                    bubble_mean_radii[index]
                    - bubble_mean_radii[index - 1]
                )
                / delta_seconds,
            )

    bubble_radius_excursion = 0.0
    bubble_radius_overshoot_ratio = 0.0
    bubble_radius_settling_time_ms = -1.0
    bubble_radius_rebound_count = 0
    if bubble_particle_peak > 0 and bubble_mean_radii:
        radius_min = min(bubble_mean_radii)
        radius_peak = max(bubble_mean_radii)
        radius_peak_index = bubble_mean_radii.index(radius_peak)
        radius_final = bubble_mean_radii[-1]
        bubble_radius_excursion = radius_peak - radius_min
        if radius_final > 0.0:
            bubble_radius_overshoot_ratio = max(
                0.0,
                (radius_peak - radius_final) / radius_final,
            )
        settle_threshold = max(1e-5, bubble_radius_excursion * 0.05)
        for index in range(radius_peak_index, len(bubble_mean_radii)):
            if all(
                abs(value - radius_final) <= settle_threshold
                for value in bubble_mean_radii[index:]
            ):
                bubble_radius_settling_time_ms = (
                    timestamps[index] - timestamps[radius_peak_index]
                ) / 1_000.0
                break
        derivative_signs = []
        derivative_floor = max(1e-6, settle_threshold * 0.1)
        for left, right in zip(
            bubble_mean_radii[radius_peak_index:],
            bubble_mean_radii[radius_peak_index + 1 :],
        ):
            delta = right - left
            if abs(delta) > derivative_floor:
                derivative_signs.append(1 if delta > 0.0 else -1)
        bubble_radius_rebound_count = sum(
            left != right
            for left, right in zip(derivative_signs, derivative_signs[1:])
        )

    waveform_rms = math.sqrt(
        _mean([value * value for value in waveform_values])
    )
    derivative_max = max(state_derivatives, default=0.0)
    discontinuity_threshold = max(12.0, derivative_max * 0.75)
    discontinuity_count = sum(
        value >= discontinuity_threshold for value in state_derivatives
    )

    return _normalise(
        {
            "bar_mean": _mean(bar_means),
            "bar_peak": global_peak,
            "bar_flux": total_flux,
            "bar_centroid": _mean(centroids),
            "integrated_bar_energy": integrated_energy,
            "input_peak": input_peak,
            "response_frame": -1 if response_index is None else response_index,
            "response_latency_ms": response_latency_ms,
            "time_to_peak_ms": time_to_peak_ms,
            "attack_slope_per_s": attack_slope_per_s,
            "overshoot_ratio": global_peak / input_peak if input_peak > 0.0 else 0.0,
            "decay_to_half_frames": decay_frames,
            "decay_to_half_ms": decay_to_half_ms,
            "settling_time_ms": settling_time_ms,
            "state_derivative_max_per_s": derivative_max,
            "discontinuity_count": discontinuity_count,
            "waveform_rms": waveform_rms,
            "waveform_peak": max(
                (abs(value) for value in waveform_values),
                default=0.0,
            ),
            "waveform_zero_crossings": zero_crossings,
            "beat_count": beat_count,
            "onset_count": onset_count,
            "bubble_particle_peak": bubble_particle_peak,
            "bubble_speed_peak": bubble_speed_peak,
            "bubble_radius_peak": bubble_radius_peak,
            "bubble_centroid_speed_peak": bubble_centroid_speed_peak,
            "bubble_radius_change_peak_per_s": bubble_radius_change_peak_per_s,
            "bubble_count_change_peak": bubble_count_change_peak,
            "bubble_radius_excursion": bubble_radius_excursion,
            "bubble_radius_overshoot_ratio": bubble_radius_overshoot_ratio,
            "bubble_radius_settling_time_ms": bubble_radius_settling_time_ms,
            "bubble_radius_rebound_count": bubble_radius_rebound_count,
            "mode_summary": mode_summary,
        }
    )

def load_clips(input_dir: str | Path) -> list[FeatureClip]:
    """Load and hash-verify one versioned fixture directory."""
    root = Path(input_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing replay fixture manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("baseline_commit") != BASELINE_BEHAVIOR_COMMIT:
        raise ValueError("fixture manifest baseline commit does not match replay lock")
    if int(manifest.get("schema_version", -1)) != 1:
        raise ValueError("unsupported replay fixture schema version")

    entries = manifest.get("fixtures")
    if not isinstance(entries, list):
        raise ValueError("fixture manifest must contain a fixtures list")
    expected = {
        str(entry["name"]): entry
        for entry in entries
        if isinstance(entry, Mapping)
    }
    paths = sorted(root.glob("*.jsonl"))
    actual_names = {path.stem for path in paths}
    if actual_names != set(expected):
        raise ValueError("fixture manifest inventory does not match JSONL files")

    clips = []
    for path in paths:
        clip = FeatureClip.from_jsonl_bytes(path.stem, path.read_bytes())
        entry = expected[path.stem]
        if str(entry.get("file")) != path.name:
            raise ValueError(f"fixture filename mismatch for {path.stem}")
        if str(entry.get("sha256")) != clip.sha256():
            raise ValueError(f"fixture hash mismatch for {path.stem}")
        if int(entry.get("frames", -1)) != len(clip.frames):
            raise ValueError(f"fixture frame-count mismatch for {path.stem}")
        clips.append(clip)
    return clips


def _clip_for_mode(clip: FeatureClip, mode: str) -> FeatureClip:
    frames = tuple(
        replace(
            frame,
            mode=mode,
            control_event=(
                "visibility_toggle"
                if frame.control_event == "visibility_toggle"
                else "none"
            ),
        )
        for frame in clip.frames
    )
    return FeatureClip(f"{clip.name}__{mode}", frames)


def replay_directory(
    input_dir: str | Path,
    *,
    include_control_replays: bool = True,
    **kwargs,
) -> dict[str, dict[str, Any]]:
    """Replay every fixture through every supported mode plus control clips."""
    outputs: dict[str, dict[str, Any]] = {}
    for source_clip in load_clips(input_dir):
        source_hash = source_clip.sha256()
        for mode in MODE_ORDER:
            clip = _clip_for_mode(source_clip, mode)
            outputs[clip.name] = replay_clip(
                clip,
                source_clip_name=source_clip.name,
                source_input_sha256=source_hash,
                **kwargs,
            )

        if include_control_replays and any(
            frame.control_event != "none" for frame in source_clip.frames
        ):
            control_clip = FeatureClip(
                f"{source_clip.name}__control",
                source_clip.frames,
            )
            outputs[control_clip.name] = replay_clip(
                control_clip,
                source_clip_name=source_clip.name,
                source_input_sha256=source_hash,
                **kwargs,
            )
    return outputs

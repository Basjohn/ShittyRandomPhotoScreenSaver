"""Deterministic offline replay through current logical and Quick snapshot owners.

No window, audio capture, worker thread or production cadence is started. Synthetic
fixtures enter at the explicit post-DSP BeatEngine seam; the real authored tick,
mode runtimes, mailbox and presentation synchronization remain authoritative.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import random
import time
from unittest.mock import patch

from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from core.settings.visualizer_presets import resolve_visualizer_activation_payload
from widgets.spotify_visualizer.config_applier import (
    apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs,
)
from widgets.spotify_visualizer.feature_frame import FeatureClip, sha256_hex
from widgets.spotify_visualizer.logical_tick_state import install_default_logical_tick_state
from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
from widgets.spotify_visualizer.quick_technical_config import apply_controller_technical_config
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs
from widgets.spotify_visualizer.technical_config import build_technical_cache
from widgets.spotify_visualizer.tick_pipeline import logical_tick

from .engine import ReplayBeatEngine
from .metrics import calculate_metrics

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/visualizer_replay/v1"
MODES = ("spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve")


def mode_output(frame):
    """The actual immutable mode output, excluding time/style-only changes."""
    state = frame.mode_state
    if frame.mode_id == "bubble":
        return state.positions
    if frame.mode_id == "devcurve":
        return tuple(value for _name, curve in state.curves for value in curve)
    if frame.mode_id == "spectrum":
        return frame.common.bars + state.peaks
    if frame.mode_id == "sine_wave":
        return tuple(float(state.parameters[key]) for key in (
            "resolved_sensitivity", "resolved_width_reaction", "wave_effect_gate",
        ))
    sensitivity = float(state.parameters["resolved_sensitivity"])
    return tuple(value * sensitivity for value in frame.common.waveform)


def mode_metrics(series):
    vectors = [mode_output(frame) for frame in series]
    flux = sum(sum(abs(a - b) for a, b in zip(left, right))
               for left, right in zip(vectors, vectors[1:]))
    return {"output_flux": flux,
            "output_peak": max((abs(value) for vector in vectors for value in vector), default=0.0)}


def load_clips(directory: Path = FIXTURES) -> dict[str, FeatureClip]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    clips = {}
    for entry in manifest["fixtures"]:
        data = (directory / entry["file"]).read_bytes()
        if sha256_hex(data) != entry["sha256"]:
            raise ValueError(f"fixture integrity mismatch: {entry['file']}")
        clip = FeatureClip.from_jsonl_bytes(entry["name"], data)
        if len(clip.frames) != entry["frames"]:
            raise ValueError(f"fixture frame count mismatch: {entry['file']}")
        clips[clip.name] = clip
    return clips


@contextmanager
def deterministic_clock():
    now = [0.0]
    saved_random = random.getstate()
    random.seed(1729)
    try:
        with patch.object(time, "time", lambda: now[0]), patch.object(time, "monotonic", lambda: now[0]):
            yield now
    finally:
        random.setstate(saved_random)


def _configure(controller, mode):
    activation = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0})
    model = SpotifyVisualizerSettings.from_mapping(
        activation.resolved_config, apply_preset_overlay=False, resolve_preset_indices=False,
    )
    controller.set_mode(mode)
    controller.settings_model = model
    controller.record_resolved_activation(activation)
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=controller.bar_count)
    install_default_presentation_state(controller.presentation_state)
    values = asdict(model)
    apply_logical_vis_mode_kwargs(state, values)
    apply_presentation_vis_mode_kwargs(controller.presentation_state, values)
    apply_engine_vis_mode_kwargs(controller.engine, values)
    controller.technical_config_cache = build_technical_cache(None, model)
    apply_controller_technical_config(controller, controller.technical_config_cache[mode], reason="offline_replay")
    controller.enabled = True
    controller.playing = True
    controller.begin_render_activation(
        engine_generation=controller.engine.get_generation_id(),
        activation_id=controller.engine.get_activation_id(),
    )
    state._mode_teardown_block_until_ready = False
    state._mode_transition_ready = True
    state._waiting_for_fresh_engine_frame = False


def replay_clip(clip: FeatureClip, mode: str, *, present_every: int = 1):
    if mode not in (*MODES, "control") or present_every < 1:
        raise ValueError("invalid replay mode or presentation interval")
    frames = []
    logical_series = []
    presentation_trace = []
    travel_rates = []
    with deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(
            runtime_generation=0, initial_mode=clip.frames[0].mode if mode == "control" else mode,
            engine_factory=lambda _count: engine,
        )
        controller.engine = engine
        _configure(controller, controller.mode_id)
        sync = QuickVisualizerPresentationSync(
            controller,
            resolve_presentation=lambda: resolve_visualizer_presentation(
                policy=get_visualizer_presentation_policy(controller.mode_id),
                display_size=(1920.0, 1080.0), outer_origin=(0.0, 0.0),
                border_width=0.0, corner_radius=0.0, content_inset=0.0,
                background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0),
                shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
                shadow_offset=(0.0, 0.0), shadow_spread=0.0,
                shadow_extensions=(0.0, 0.0, 0.0, 0.0),
            ),
        )
        try:
            for index, feature in enumerate(clip.frames):
                clock[0] = feature.timestamp_us / 1_000_000.0
                if mode == "control" and feature.mode != controller.mode_id:
                    _configure(controller, feature.mode)
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                if not engine.accept_feature_frame(feature):
                    raise RuntimeError(f"rejected replay input {clip.name}:{index}")
                logical = logical_tick(controller.logical_tick_state)
                if logical is None:
                    raise RuntimeError(f"missing logical frame {clip.name}:{index}")
                logical_series.append(logical)
                row = {
                    "timestamp_us": feature.timestamp_us,
                    "display_bars": list(logical.common.bars),
                    "waveform": list(logical.common.waveform),
                    "energy_lanes": asdict(feature.energy),
                    "overlay": {"mode": controller.mode_id},
                }
                bubble = controller.peek_logical_mode_state("bubble")
                if controller.mode_id == "bubble" and bubble is not None:
                    row["bubble_simulation"] = {"particles": [
                        {name: getattr(p, name) for name in (
                            "x", "y", "vx", "vy", "impulse_vx", "impulse_vy", "radius", "display_radius",
                        )} for p in bubble.simulation._bubbles
                    ]}
                frames.append(row)
                if controller.mode_id == "devcurve":
                    runtime = controller.peek_logical_mode_state("devcurve")
                    travel_rates.append(runtime.solver_state.foreground_travel_rate)
                if feature.visible and index % present_every == 0:
                    if not sync.sync_latest():
                        raise RuntimeError(f"Quick snapshot rejected {clip.name}:{index}")
                    presentation_trace.append(index)
        finally:
            controller.close_render_admission()
            engine.deleteLater()
    return {
        "metrics": calculate_metrics(frames), "frames": frames,
        "mode_metrics": mode_metrics(logical_series),
        "travel_rates": travel_rates,
        "logical_series": logical_series, "presentation_trace": presentation_trace,
    }

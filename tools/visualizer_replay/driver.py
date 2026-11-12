"""Deterministic offline replay through current logical and Quick snapshot owners.

No window, audio capture, worker thread or production cadence is started. Synthetic
fixtures enter at the explicit post-DSP BeatEngine seam; the real authored tick,
mode runtimes, mailbox and presentation synchronization remain authoritative.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
import json
from pathlib import Path
import random
import time
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QThread

from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy, iter_all_visualizer_mode_descriptors
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
from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs, resolve_mode_source_config
from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config
from widgets.spotify_visualizer.tick_pipeline import logical_tick

from widgets.spotify_visualizer.feature_replay import (  # noqa: F401  (deterministic_clock: tool name)
    configure_offline_controller, deterministic_clock,
)

from .engine import ReplayBeatEngine
from .metrics import calculate_metrics

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/visualizer_replay/v1"
MODES = ("spectrum", "oscilloscope", "bubble", "devcurve")
# Modes that replay from schema 2 clips only (their inputs are the real-scale lanes).
REAL_SCALE_MODES = ("sphere", "shockwave_grid")


def sphere_output(state) -> tuple[float, ...]:
    """Sphere's behavioural outputs on one frame: section drives (fragmentation), then size,
    spin, tracer, incoming drive and density, then each live cohort's progress/strength/density."""
    cohorts = tuple(value for cohort in state.particle_cohorts
                    for value in (cohort.progress, cohort.strength, cohort.density))
    return (*state.section_drives, state.size_pulse, state.rotation_drive, state.tracer_drive,
            state.incoming_drive, state.incoming_density, *cohorts)


def mode_output(frame):
    """The actual immutable mode output, excluding time/style-only changes."""
    state = frame.mode_state
    if frame.mode_id == "bubble":
        return state.positions
    if frame.mode_id == "devcurve":
        return tuple(value for _name, curve in state.curves for value in curve)
    if frame.mode_id in {"spectrum", "extruded_spectrum"}:
        return frame.common.bars + state.peaks
    if frame.mode_id == "sphere":
        return sphere_output(state)
    if frame.mode_id == "shockwave_grid":
        # The live waves' strengths, newest last (the grid's reaction; its bars are Spectrum's).
        return tuple(float(event[3]) for event in state.events)
    if frame.mode_id == "extruded_bubble":
        # Its own simulation's bubble records (positions, radii, fades) and the scene scalars the GPU layers read.
        return (*state.bubbles, state.level, state.flash, state.drift, state.emission, state.stream_speed,
                state.rays)
    if frame.mode_id == 'waveform_ribbon':
        # Actual resolved range values and rate, excluding the independently flowing idle carrier.
        # Native packet/pixel comparisons remain the geometry proof.
        return (*(value for _key,value in state.realized),state.rotation_speed)
    if frame.mode_id == "oscilloscope":
        # The live trace's vertical swing (its points' y, the drawn audio), then the beam's
        # reactions: its drive and flare.
        import struct

        count = state.trace_points
        live = struct.unpack(f"<{2 * count}f", state.points[-8 * count:]) if count else ()
        return (*live[1::2], float(state.drive), float(state.flare))
    sensitivity = float(state.parameters["resolved_sensitivity"])
    drawn = frame.common.waveform[:frame.common.waveform_count]     # the samples the line draws
    return tuple(value * sensitivity for value in drawn)


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


# Offline controller configuration is production-owned (the Studio's recorded fixtures use it too).
_configure = configure_offline_controller


def _record_drift_step(logical, history: list[tuple[bytes, bytes]]) -> None:
    """Keep each Extruded Bubble drift step once (the newest record of the published history, with its chains'
    knot decisions)."""
    steps = getattr(logical.mode_state, "drift_steps", b"")
    if steps:
        from widgets.spotify_visualizer.extruded_bubble_drift_log import newest_knots
        newest = newest_knots(steps, logical.mode_state.drift_knots)
        if not history or history[-1][0] != newest[0]:
            history.append(newest)


def _with_drift_history(snapshot, history: list[tuple[bytes, bytes]]):
    """A sparse capture skips presentations, so its renderer never saw the steps in between: hand it every step
    since the previous returned snapshot (the live runtime presents each revision and needs no such help)."""
    state = snapshot.logical.mode_state
    if not getattr(state, "drift_families", ()) or not history:
        return snapshot
    steps, knots = (b"".join(part) for part in zip(*history))
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, drift_steps=steps,
                                                                                    drift_knots=knots)))


def replay_clip(clip: FeatureClip, mode: str, *, present_every: int = 1, preset: int = 0, overrides=None,
                snapshots_at=(), settings=None, viewport_extent=None):
    """Replay ``clip`` through ``mode`` (curated ``preset``, or ``settings``: frozen complete settings, a mapping
    or ``mode -> mapping``; with optional Settings-model ``overrides``). ``snapshots_at``: frame indices whose published Quick snapshot is returned
    (``result["snapshots"]``, index -> snapshot) for renderer captures. ``viewport_extent``: a committed CUSTOM
    world (width, height) hydrated exactly as a persisted card is, presented at uniform scale 1; ``None`` keeps
    the canonical baseline."""
    if mode not in (*(descriptor.mode_id for descriptor in iter_all_visualizer_mode_descriptors()), "control") or present_every < 1:
        raise ValueError("invalid replay mode or presentation interval")
    if mode in REAL_SCALE_MODES and any(frame.real is None for frame in clip.frames):
        raise ValueError("Sphere replays only from schema 2 (real-scale) clips")
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
        _configure(controller, controller.mode_id, preset, overrides, settings)
        extent = None if viewport_extent is None else (float(viewport_extent[0]), float(viewport_extent[1]))
        if extent is not None:
            controller.hydrate_committed_layout_metrics(extent, 0)
        # A display at least as large as the world keeps the uniform scale at 1, so replayed pixels are world units.
        display = (1920.0, 1080.0) if extent is None else (max(1920.0, extent[0]), max(1080.0, extent[1]))
        snapshots = {}
        wanted = frozenset(snapshots_at)
        drift_history: list[tuple[bytes, bytes]] = []   # EB drift steps (and knots) since the last returned snapshot
        def presentation():
            return resolve_visualizer_presentation(
                policy=get_visualizer_presentation_policy(controller.mode_id),
                display_size=display, outer_origin=(0.0, 0.0), viewport_extent=extent,
                border_width=0.0, corner_radius=0.0, content_inset=0.0,
                background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0),
                shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
                shadow_offset=(0.0, 0.0), shadow_spread=0.0,
                shadow_extensions=(0.0, 0.0, 0.0, 0.0),
            )

        sync = QuickVisualizerPresentationSync(controller, resolve_presentation=presentation)
        # The replayed card is the one a scene would draw: its framed view (N0.4) is what the scene would publish.
        from rendering.quick.visualizer.framed_view import resolve_framed_view

        controller.set_framed_view(resolve_framed_view(presentation()))
        try:
            for index, feature in enumerate(clip.frames):
                clock[0] = feature.timestamp_us / 1_000_000.0
                if mode == "control" and feature.mode != controller.mode_id:
                    _configure(controller, feature.mode, settings=settings)
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                if not engine.accept_feature_frame(feature):
                    raise RuntimeError(f"rejected replay input {clip.name}:{index}")
                logical = logical_tick(controller.logical_tick_state)
                if logical is None:
                    raise RuntimeError(f"missing logical frame {clip.name}:{index}")
                logical_series.append(logical)
                _record_drift_step(logical, drift_history)
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
                if controller.mode_id == "sphere":
                    state = logical.mode_state
                    row["sphere"] = {
                        "section_drives": list(state.section_drives), "size_pulse": state.size_pulse,
                        "rotation_drive": state.rotation_drive, "tracer_drive": state.tracer_drive,
                        "incoming_drive": state.incoming_drive, "incoming_density": state.incoming_density,
                        "cohorts": [asdict(cohort) for cohort in state.particle_cohorts],
                    }
                if controller.mode_id == "devcurve":
                    runtime = controller.peek_logical_mode_state("devcurve")
                    travel_rates.append(runtime.solver_state.foreground_travel_rate)
                if feature.visible and index % present_every == 0:
                    if not sync.sync_latest():
                        raise RuntimeError(f"Quick snapshot rejected {clip.name}:{index}")
                    presentation_trace.append(index)
                    if index in wanted:
                        snapshots[index] = _with_drift_history(controller.render_bridge.peek(), drift_history)
                        drift_history = []
        finally:
            controller.close_render_admission()
            # Offline replay owns this engine. Retire only its queued QObject
            # deletion, not unrelated scenes/windows left by other Qt tests.
            # A global DeferredDelete drain here can delete foreign QQuick
            # objects while their Python wrappers remain live in the process.
            engine.deleteLater()
            app = QCoreApplication.instance()
            if app is not None and engine.thread() == QThread.currentThread():
                QCoreApplication.sendPostedEvents(engine, QEvent.Type.DeferredDelete)
    return {
        "metrics": calculate_metrics(frames), "frames": frames,
        "mode_metrics": mode_metrics(logical_series),
        "travel_rates": travel_rates,
        "logical_series": logical_series, "presentation_trace": presentation_trace,
        "snapshots": snapshots,
    }

"""Recorded clip -> the exact ticks Bubble's production logical step is served, via the production replay.

Runs in a *separate process* (``python -m ui.studio.bubble_recorded_inputs``) through the shared event-driven
``ClipLoadJob``: the production offline replay (``widgets.spotify_visualizer.feature_replay``: ``ProductionLaneEngine``
+ ``configure_offline_controller`` + ``logical_tick`` under ``deterministic_clock``) pins the process clocks, so the
Studio never runs it inside the app. ``ProductionLaneEngine`` re-analyses every lane from the clip's PCM through the
production DSP under the settings' Audio Analysis values, so Sensitivity, the floors, Gain and Block Size move
Bubble's lanes and events as they do live (the recorded post-DSP lanes cannot move).

For every replay tick the worker records what the engine served Bubble's step (``get_bubble_energy_bands``,
``get_transient_energy_bands``, the typed events fed to the event scheduler, the authoritative source frame) and a
digest of the frame the production Bubble capture built after it, so the Studio's evaluator can be proven to
reproduce the live path frame for frame. The ticks depend on the Audio Analysis (technical) values only, never on Bubble's authored controls.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
MODE = "bubble"


def frame_digest(frame) -> str:
    """Every field of a ``BubbleFrame``; renderer parameters restricted to the mode's own keys."""
    from widgets.spotify_visualizer.render_state import BubbleFrame
    digest = hashlib.sha256()
    for field in fields(BubbleFrame):
        value = getattr(frame, field.name)
        if field.name == "parameters":
            value = sorted((k, repr(v)) for k, v in dict(value).items() if k.startswith(MODE + "_"))
        digest.update(field.name.encode())
        digest.update(repr(value).encode())
    return digest.hexdigest()


def extract(clip_path: str | Path, settings: Mapping[str, Any], *, seconds: float | None = None,
            frames_out: list | None = None, features=None) -> dict:
    """``features``: already-loaded feature frames instead of ``clip_path`` (tests). ``frames_out`` collects the
    production capture's frames (in-process callers only)."""
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer import logical_frame_capture
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.feature_replay import (
        configure_offline_controller, deterministic_clock, fed_events, lane_engine,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    from ui.studio import clip_loop
    from ui.studio.bubble_adapter import SEED, resolved_settings

    if QGuiApplication.instance() is None:
        raise RuntimeError("extract() needs an existing QGuiApplication (main() creates one)")
    if features is None:
        clip = load_feature_clip(clip_path)
        features = clip.frames
    origin_us = features[0].timestamp_us
    frames = [f for f in features if seconds is None or (f.timestamp_us - origin_us) / 1e6 <= seconds]
    frames, start = clip_loop.primed(features, frames, clip_path)       # a loop: its end replayed first
    capture = logical_frame_capture._BUILTIN_MODE_CAPTURE[MODE]
    records: list[dict] = []
    with deterministic_clock() as clock:
        engine = lane_engine(frames)
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=MODE,
                                                 engine_factory=lambda _: engine)
        controller.engine = engine
        configure_offline_controller(controller, MODE, settings=resolved_settings(settings))
        state = controller.logical_tick_state
        random.seed(SEED)                  # the Studio evaluator's seed at its first step
        carried: list = []                 # events fed on ticks that did not step Bubble (still in the scheduler)
        try:
            for feature in frames:
                clock[0] = feature.timestamp_us / 1e6
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                engine.accept_feature_frame(feature)
                bubble = engine.get_bubble_energy_bands()
                transient = engine.get_transient_energy_bands()
                ts, generation, activation = engine.get_latest_authoritative_frame()
                cadence = getattr(state, "_bubble_cadence_state", None)
                before = cadence.integrated_steps if cadence is not None else 0
                logical_tick(state)
                cadence = getattr(state, "_bubble_cadence_state", None)
                fed = fed_events(engine, feature)
                if cadence is None or cadence.integrated_steps == before:
                    carried.extend(fed)     # the production tick did not step Bubble: neither does the Studio
                    continue
                record = {
                    "now_ts": float(clock[0]), "playing": bool(feature.playing),
                    "bubble": [float(bubble.bass), float(bubble.mid), float(bubble.high), float(bubble.overall)],
                    "transient": [float(transient.bass_transient), float(transient.mid_transient),
                                  float(transient.high_transient), bool(transient.onset_detected),
                                  str(transient.onset_type), float(transient.onset_strength)],
                    "events": carried + fed,
                    "authoritative": float(ts),
                    "fresh": bool(generation == engine.get_generation_id()
                                  and activation == engine.get_activation_id()),
                    "scheduler": engine.get_event_scheduler() is not None,
                }
                result = capture(state, engine, None)
                if result is not None:
                    record["frame_sha256"] = frame_digest(result[0])
                    if frames_out is not None:
                        frames_out.append((record["now_ts"], result[0]))
                records.append(record)
                carried = []
        finally:
            engine.force_stop()
    if start is not None:                  # only the clip's own ticks are recorded; the lead-in just primed the engine
        records = [r for r in records if r["now_ts"] >= start - 1e-9]
        if frames_out is not None:
            frames_out[:] = [item for item in frames_out if item[0] >= start - 1e-9]
    if not records:
        raise RuntimeError("The clip never stepped Bubble")
    from ui.studio.clip_loop import mark_loop
    return mark_loop({"clip": str(clip_path), "origin": float(records[0]["now_ts"]),
                      "duration": float(records[-1]["now_ts"] - records[0]["now_ts"]), "steps": records},
                     clip_path, start)


def to_inputs(data: Mapping[str, Any], fixture):
    from ui.studio.bubble_adapter import RecordedInputs, TickInput
    steps = tuple(TickInput(now=float(s["now_ts"]), playing=bool(s["playing"]), bubble=tuple(s["bubble"]),
                            transient=tuple(s["transient"]), events=tuple(tuple(e) for e in s["events"]),
                            authoritative=float(s["authoritative"]), fresh=bool(s["fresh"]),
                            scheduler=bool(s["scheduler"]))
                  for s in data["steps"])
    from ui.studio.clip_loop import looped_fixture
    return RecordedInputs(looped_fixture(fixture, data), steps, float(data["origin"]),
                          float(data.get("loop_period", 0.0)))


def main(argv: list[str]) -> int:
    clip, settings_path, output_path, *rest = argv
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ui.studio.worker_lifetime import die_with_parent
    die_with_parent()                                            # never outlive the Studio (Linux)
    from ui.studio.waveform_recorded_inputs import CLIP_SECONDS
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    from PySide6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication([])     # this process is the analysis worker
    data = extract(clip, settings, seconds=float(rest[0]) if rest else CLIP_SECONDS)
    Path(output_path).write_text(json.dumps(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

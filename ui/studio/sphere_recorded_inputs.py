"""Recorded clip -> the exact engine answers Sphere's production capture is served, via the production replay.

Runs in a *separate process* (``python -m ui.studio.sphere_recorded_inputs``) through the shared event-driven
``ClipLoadJob``: the production offline replay (``feature_replay``: ``ReplayBeatEngine`` + ``configure_offline_controller``
+ ``logical_tick`` under ``deterministic_clock``) pins the process clocks, so the Studio never runs it inside the app.

Sphere's logical step is its capture (``sphere_capture.capture_sphere`` resolves the frame runtime). At every
production capture the worker records what the engine answered (``ui.studio.replay_engine.recorded_answers``: the
Bubble, shared and live lanes, musical level and intensity, the analysis spectrum, the transient lane, the typed
events fed since the previous capture, the authoritative source frame) and a digest of the Sphere frame the capture
built, so the Studio's evaluator can be proven to reproduce the live path frame for frame. The answers do not depend
on Sphere's authored controls.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
MODE = "sphere"


def frame_digest(frame) -> str:
    """Every field of a ``SphereFrame`` (renderer parameters included, the reflected backdrop by its identity)."""
    from widgets.spotify_visualizer.render_state import SphereFrame
    digest = hashlib.sha256()
    for field in fields(SphereFrame):
        value = getattr(frame, field.name)
        if field.name == "parameters":
            value = sorted((k, repr(None if v is None else dict(v).get("identity")) if k == "backdrop" else repr(v))
                           for k, v in dict(value).items())
        digest.update(field.name.encode())
        digest.update(repr(value).encode())
    return digest.hexdigest()


def extract(clip_path: str | Path, settings: Mapping[str, Any], *, seconds: float | None = None,
            frames_out: list | None = None, features=None, environment=None) -> dict:
    """``features``: already-loaded feature frames instead of ``clip_path`` (tests). ``frames_out`` collects the
    production capture's logical frames (in-process callers only). ``environment``: the photograph the production
    owner hands a reflecting mode (``PresentationImage``), applied by its reflection rule."""
    from unittest.mock import patch
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer import sphere_capture
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine, deterministic_clock
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    from ui.studio.replay_engine import offline_controller, recorded_answers
    from ui.studio.sphere_adapter import resolved_settings

    if QGuiApplication.instance() is None:
        raise RuntimeError("extract() needs an existing QGuiApplication (main() creates one)")
    if features is None:
        features = load_feature_clip(clip_path).frames
    origin_us = features[0].timestamp_us
    frames = [f for f in features if seconds is None or (f.timestamp_us - origin_us) / 1e6 <= seconds]
    records: list[dict] = []
    current = {"feature": None, "carried": []}
    original = sphere_capture.capture_sphere

    def recording(widget, engine, context):
        answers = recorded_answers(engine, current["feature"])
        answers["events"] = current["carried"] + answers["events"]
        current["carried"] = []
        current["fed"] = True
        result = original(widget, engine, context)
        answers["now_ts"] = float(context.now_ts)
        if result is not None:
            answers["frame_sha256"] = frame_digest(result[0])
        records.append(answers)
        return result

    with deterministic_clock() as clock, patch.object(sphere_capture, "capture_sphere", recording):
        engine = ReplayBeatEngine(32)
        controller = offline_controller(engine, MODE, resolved_settings(settings))
        if environment is not None:
            from ui.studio.environment import refresh_backdrop
            refresh_backdrop(controller.presentation_state, MODE, environment)
        state = controller.logical_tick_state
        try:
            for feature in frames:
                clock[0] = feature.timestamp_us / 1e6
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                engine.accept_feature_frame(feature)
                current["feature"] = feature
                current["fed"] = False
                before = len(records)
                payload = logical_tick(state)
                if len(records) == before:
                    # No capture this tick: its fed events stay in the scheduler for the next one.
                    real = feature.real
                    if real is not None:
                        current["carried"] += [[feature.timestamp_us / 1e6, e.kind, float(e.strength)]
                                               for e in real.events]
                elif frames_out is not None and payload is not None:
                    frames_out.append((records[-1]["now_ts"], payload))
        finally:
            engine.force_stop()
    if not records:
        raise RuntimeError("The clip never captured a Sphere frame")
    return {"clip": str(clip_path), "origin": float(records[0]["now_ts"]),
            "duration": float(records[-1]["now_ts"] - records[0]["now_ts"]), "steps": records}


def to_inputs(data: Mapping[str, Any], fixture):
    from ui.studio.replay_engine import EngineTick
    from ui.studio.sphere_adapter import RecordedInputs
    steps = tuple(EngineTick(now=float(s["now_ts"]), playing=bool(s["playing"]), bubble=tuple(s["bubble"]),
                             transient=tuple(s["transient"]), events=tuple(tuple(e) for e in s["events"]),
                             authoritative=float(s["authoritative"]), fresh=bool(s["fresh"]),
                             scheduler=bool(s["scheduler"]), energy=tuple(s["energy"]), live=tuple(s["live"]),
                             musical_level=tuple(s["musical_level"]), musical_intensity=float(s["musical_intensity"]),
                             spectrum=tuple(s["spectrum"]))
                  for s in data["steps"])
    return RecordedInputs(fixture, steps, float(data["origin"]))


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

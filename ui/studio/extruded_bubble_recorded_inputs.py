"""Recorded clip -> the exact Extruded Bubble frame-runtime inputs, via the production replay analysis.

Runs in a *separate process* (``python -m ui.studio.extruded_bubble_recorded_inputs``), like the Waveform worker
(``waveform_recorded_inputs``, whose event-driven ``ClipLoadJob`` launches this one): the production offline replay
(``widgets.spotify_visualizer.feature_replay``: ``ReplayBeatEngine`` + ``PcmReanalysis`` + ``logical_tick``) pins
the process clocks and builds its own runtime controller, so the Studio never runs it inside the app.

EB reads its own fixed-scale body feed (``get_extruded_bubble_body_bands``). Recordings carry no raw lanes, so the
replay engine serves EB the recorded shared feed unless the PCM is reanalysed; this worker reanalyses every frame's
native PCM and serves EB the production engine's own feed from it (what the EB recorded-reactivity gates do). Every
keyword input the production capture passes to ``ExtrudedBubbleFrameRuntime.advance`` is recorded with a digest of
the frame the production capture built from it, so the Studio's evaluator can be proven to reproduce it.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
MODE = "extruded_bubble"


def frame_digest(frame) -> str:
    """Every authored field of an ``ExtrudedBubbleFrame`` (renderer parameters: the mode's own keys and the 3D Detail
    tier, which are all the renderer reads). Drift-family revisions are process-unique counters, not content."""
    from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame
    digest = hashlib.sha256()
    for field in fields(ExtrudedBubbleFrame):
        value = getattr(frame, field.name)
        if field.name == "parameters":
            value = sorted((k, repr(v)) for k, v in dict(value).items()
                           if k.startswith(MODE + "_") or k == "scene3d_detail")
        elif field.name == "drift_families":
            value = [(f.family, f.first_serial, f.capacity, f.geometry, f.carry) for f in value]
        digest.update(field.name.encode())
        digest.update(value if isinstance(value, bytes) else repr(value).encode())
    return digest.hexdigest()


def extract(clip_path: str | Path, settings: Mapping[str, Any], *, seconds: float | None = None) -> dict:
    from unittest.mock import patch
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer import logical_frame_capture
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.feature_replay import (
        PcmReanalysis, ReplayBeatEngine, configure_offline_controller, deterministic_clock,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    if QGuiApplication.instance() is None:
        raise RuntimeError("extract() needs an existing QGuiApplication (main() creates one)")
    clip = load_feature_clip(clip_path)
    origin_us = clip.frames[0].timestamp_us
    frames = [f for f in clip.frames if seconds is None or (f.timestamp_us - origin_us) / 1e6 <= seconds]
    if any(f.capture_history is None for f in frames):
        raise RuntimeError("EB replay needs native PCM history on every frame; re-record the clip")
    records: list[dict] = []
    original = ExtrudedBubbleFrameRuntime.advance
    capture = logical_frame_capture._BUILTIN_MODE_CAPTURE[MODE]

    def recording(self, **kwargs):
        snapshot = original(self, **kwargs)
        if snapshot is not None:
            records.append({"now_ts": float(kwargs["now_ts"]), "playing": bool(kwargs["playing"]),
                            "play_ramping": bool(kwargs.get("play_ramping", False)),
                            "onsets": [asdict(onset) for onset in kwargs["onsets"]],
                            "body_bands": [float(v) for v in kwargs["body_bands"]],
                            "identity": [int(v) for v in kwargs["identity"]],
                            "source_identity": [int(v) for v in kwargs["source_identity"]]})
        return snapshot

    def capturing(widget, engine, context):
        result = capture(widget, engine, context)
        if result is not None and records:
            records[-1]["frame_sha256"] = frame_digest(result[0])
        return result

    resolved = dict(settings)
    resolved["mode"] = MODE
    reanalysis = PcmReanalysis()
    with patch.object(ExtrudedBubbleFrameRuntime, "advance", recording), \
            patch.dict(logical_frame_capture._BUILTIN_MODE_CAPTURE, {MODE: capturing}), \
            patch.object(ReplayBeatEngine, "get_extruded_bubble_body_bands",
                         _SpotifyBeatEngine.get_extruded_bubble_body_bands), \
            deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=MODE,
                                                 engine_factory=lambda _: engine)
        controller.engine = engine
        configure_offline_controller(controller, MODE, settings=resolved)
        try:
            for feature in frames:
                clock[0] = feature.timestamp_us / 1e6
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                engine.accept_feature_frame(feature)
                reanalysis.accept(engine, feature)
                logical_tick(controller.logical_tick_state)
        finally:
            engine.force_stop()
    steps = [r for r in records if "frame_sha256" in r]
    if not steps:
        raise RuntimeError("The clip never produced an Extruded Bubble frame")
    return {"clip": str(clip_path), "origin": float(steps[0]["now_ts"]),
            "duration": float(steps[-1]["now_ts"] - steps[0]["now_ts"]), "steps": records}


def to_inputs(data: Mapping[str, Any], fixture):
    from widgets.spotify_visualizer.transient_bus import MusicalOnset
    from ui.studio.extruded_bubble_adapter import AdvanceInput, RecordedInputs
    steps = tuple(AdvanceInput(now=float(s["now_ts"]), playing=bool(s["playing"]),
                               onsets=tuple(MusicalOnset(**o) for o in s["onsets"]),
                               body_bands=tuple(s["body_bands"]), play_ramping=bool(s["play_ramping"]),
                               identity=tuple(s["identity"]), source_identity=tuple(s["source_identity"]))
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

"""Which Audio Analysis controls change a mode's published frame: python -m tools.visualizer_replay.analysis_controls_audit

    python -m tools.visualizer_replay.analysis_controls_audit --modes devcurve oscilloscope --out logs/audio_analysis.json
    python -m tools.visualizer_replay.analysis_controls_audit --list

Ordinary replay serves the *recorded* post-DSP lanes (``feature_replay.ReplayBeatEngine``), so a technical control
that acts inside the engine cannot move them: it would read as inert everywhere. This audit instead recomputes every
lane a mode reads from the clip's native PCM through the production DSP (``ProductionLaneEngine``: each frame's
capture tail goes through ``compute_bars_from_samples`` with the replay worker's *configured* state, then the
production getters answer from that state: the control lanes, the live and bubble feeds, the fixed-scale body feeds,
the transient bus, the musical level, intensity and onsets, and the analysis spectrum). The mode's own production
``logical_tick`` then runs on those answers. Each owned technical control is moved from the mode's frozen baseline
and the published frame is compared with the baseline run, field by field (every signal field of the mode's frame,
plus the drawn bars where the mode draws them; configuration and the ticks' own clock are excluded).

A control is *inert* for a mode when every variation leaves the frame bit-identical (``difference == 0``).
The run is deterministic (pinned clock and RNG), so a repeat of the baseline is checked to differ by exactly zero.
Nothing starts audio capture, a window or a worker thread. Clips are the shipped Studio clips (``--clips``).

Scale caveat: this takes one analysis block per 11 ms tick (the newest ``block`` samples of each frame's capture
history), where the live worker analyses every capture callback, so absolute levels approximate the live engine's;
whether a control reaches a mode's frame at all is exact. Tests: ``tests/test_audio_analysis_controls.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402
CLIPS = ROOT / "assets" / "production" / "studio_clips"
MODES = ("spectrum", "extruded_spectrum", "oscilloscope", "bubble", "extruded_bubble", "sphere", "devcurve",
         "shockwave_grid", "waveform_ribbon")
# Frames (~90 Hz) replayed from the clip's start; the shipped clips open with a quiet lead-in and build to hot music.
DEFAULT_SECONDS = 9.0


def _production_lane_engine():
    """``feature_replay.ProductionLaneEngine``: every lane getter answers from production DSP on the clip's PCM."""
    from widgets.spotify_visualizer.feature_replay import ProductionLaneEngine
    return ProductionLaneEngine


def load_clip(name: str, seconds: float, start: float = 0.0):
    """The shipped Studio clip ``name`` from ``start`` s for ``seconds`` s (a window starts cold; replay is deterministic)."""
    from widgets.spotify_visualizer.compact_clip import load_compact
    from widgets.spotify_visualizer.feature_frame import FeatureClip

    clip = load_compact(CLIPS / f"{name}.srclip", name=name)
    first = clip.frames[0].timestamp_us
    frames = tuple(f for f in clip.frames if start <= (f.timestamp_us - first) / 1e6 <= start + seconds)
    return FeatureClip(name, frames)


def frozen(mode: str) -> dict:
    from tools.freeze_visualizer_settings import load_frozen

    return dict(load_frozen(mode))


def technical_keys(mode: str) -> dict:
    """suffix -> (storage key, spec control) for every technical control the mode owns (shown or not)."""
    from core.settings.visualizer_mode_settings import require_mode_settings

    return {control.key.removeprefix(f"{mode}_"): (control.key, control)
            for control in require_mode_settings(mode).technical_controls(offered=False)}


def baseline_values(mode: str, settings: dict) -> dict:
    """The resolved value of every owned technical key (what the baseline run uses)."""
    from core.settings.models import SpotifyVisualizerSettings

    model = SpotifyVisualizerSettings.from_mapping(settings, apply_preset_overlay=False, resolve_preset_indices=False)
    values = {}
    for suffix, (key, _defn) in technical_keys(mode).items():
        values[key] = getattr(model, key, None)
    return values


def variations(mode: str, base: dict) -> list[dict]:
    """[{control, label, base_overrides, overrides}]: each owned technical control moved to two other values.

    A control that acts only under another (Sensitivity under Use Recommended Sensitivity off, the manual floor
    under Dynamic Noise Floor off) is moved with that enabler forced, against a baseline forced the same way."""
    out = []
    keys = technical_keys(mode)

    def key(suffix):
        return keys[suffix][0] if suffix in keys else None

    def add(suffix, label, alternatives, forced=None):
        storage = key(suffix)
        if storage is None:
            return
        for alt in alternatives:
            out.append({"control": suffix, "label": f"{label} -> {alt}", "base_overrides": dict(forced or {}),
                        "overrides": {**(forced or {}), storage: alt}})

    def pick(storage, candidates, count=2):
        current = base.get(storage)
        chosen = [c for c in candidates if c != current]
        return chosen[:count]

    bar = key("bar_count")
    if bar:
        current = int(base.get(bar) or 32)
        add("bar_count", "Bar Count", [max(8, current // 2), min(96, current * 2)])
    block = key("audio_block_size")
    if block:
        add("audio_block_size", "Audio Block Size", pick(block, (128, 512, 1024, 256)))
    adaptive = key("adaptive_sensitivity")
    if adaptive:
        add("adaptive_sensitivity", "Use Recommended Sensitivity", [not bool(base.get(adaptive))])
    sens = key("sensitivity")
    if sens and adaptive:
        add("sensitivity", "Sensitivity (manual)", (0.5, 2.0), forced={adaptive: False})
    dyn = key("dynamic_floor")
    if dyn:
        add("dynamic_floor", "Dynamic Noise Floor", [not bool(base.get(dyn))])
    manual = key("manual_floor")
    if manual and dyn:
        add("manual_floor", "Noise Floor Baseline (fixed)", (0.1, 0.6), forced={dyn: False})
    for suffix, label, alts in (("input_gain", "Input Gain", (0.5, 1.6)), ("agc_strength", "AGC Strength", (0.1, 0.9)),
                                ("kick_lane_gain", "Kick Lane Gain", (0.2, 1.8)),
                                ("transient_pulse_gain", "Transient Pulse", (0.3, 2.5)),
                                ("transient_clamp", "Transient Clamp", (0.4, 2.8))):
        if key(suffix):
            add(suffix, label, pick(key(suffix), alts))
    if key("dynamic_range_enabled"):
        add("dynamic_range_enabled", "Output Lift", [not bool(base.get(key("dynamic_range_enabled")))])
    for suffix, (storage, control) in keys.items():
        if suffix in ("lane_transient_mix", "transient_mix_bass"):
            add(suffix, control.label.rstrip(":"), pick(storage, (0.1, 0.9)))
        elif suffix == "transient_mix_vocal":
            # Bubble's vocal mix reaches only the specular wobble (Rotation Amount) through its mid transient (Pulse gain).
            forced = {f"{mode}_rotation_amount": 1.0, f"{mode}_transient_pulse_gain": 3.0, f"{mode}_transient_clamp": 3.0}
            add(suffix, control.label.rstrip(":") + " (with Rotation Amount on)", pick(storage, (0.0, 1.0)), forced=forced)
    return out


def _digest(data) -> tuple[float, ...]:
    """Raw float32 bytes reduced to their sum, sum of squares and length (equal data, equal digest)."""
    import numpy as np

    raw = bytes(data)
    values = np.frombuffer(raw[: len(raw) // 4 * 4], dtype=np.float32).astype(np.float64)
    finite = values[np.isfinite(values)]
    return (float(finite.sum()), float((finite * finite).sum()), float(len(values)))


def _flat(value) -> tuple[float, ...]:
    """Every number in a frame field, in order; byte payloads (geometry, points) as a digest."""
    import dataclasses

    if isinstance(value, bool):
        return (float(value),)
    if isinstance(value, (int, float)):
        return (float(value),)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _digest(value)
    if isinstance(value, str) or value is None:
        return ()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(x for f in dataclasses.fields(value) for x in _flat(getattr(value, f.name)))
    try:
        return tuple(x for item in value for x in _flat(item))
    except TypeError:
        return ()


# Frame fields that are configuration (identical by construction) or only the ticks' own clock.
_NOT_SIGNALS = frozenset({"parameters", "animation_time", "time", "authored_time", "source_timestamp",
                          "simulation_timestamp", "geometry_diagnostics", "motion_phase"})
# Modes whose published bars are drawn (Spectrum's family and Neon Lake).
_DRAWS_BARS = ("spectrum", "extruded_spectrum", "shockwave_grid")


def _channels(frame, mode: str) -> dict[str, tuple[float, ...]]:
    """Every published signal of the mode's frame, by field name (everything it draws and drives the drawing with)."""
    import dataclasses
    import struct

    state, common = frame.mode_state, frame.common
    out: dict[str, tuple[float, ...]] = {}
    if mode in _DRAWS_BARS:
        out["bars"] = _flat(common.bars)
    for field in dataclasses.fields(state):
        if field.name not in _NOT_SIGNALS:
            out[field.name] = _flat(getattr(state, field.name))
    if mode == "oscilloscope":
        count = state.trace_points
        live = struct.unpack(f"<{2 * count}f", state.points[-8 * count:]) if count else ()
        out["live_trace"] = tuple(live[1::2])
    if mode == "shockwave_grid":
        out["events"] = tuple(float(e[3]) for e in state.events)
    return out


def replay(mode: str, clip, overrides: dict, *, prepare=None):
    """The mode's published frame vectors over ``clip`` with the settings overridden. ``prepare(engine)`` runs once the
    controller is configured, before the first frame (worker-level analysis state a mode does not own, a probe)."""
    from PySide6.QtCore import QCoreApplication, QEvent, QThread
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller, deterministic_clock
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    settings = frozen(mode)
    settings.update(overrides)
    series = []
    engine_class = _production_lane_engine()
    with deterministic_clock() as clock:
        engine = engine_class(32)
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        configure_offline_controller(controller, mode, 0, None, settings)
        if prepare is not None:
            prepare(engine)
        try:
            for index, feature in enumerate(clip.frames):
                clock[0] = feature.timestamp_us / 1_000_000.0
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                if not engine.accept_feature_frame(feature):
                    raise RuntimeError(f"rejected replay input {clip.name}:{index}")
                logical = logical_tick(controller.logical_tick_state)
                if logical is None:
                    raise RuntimeError(f"missing logical frame {clip.name}:{index}")
                series.append(_channels(logical, mode))
        finally:
            controller.close_render_admission()
            engine.deleteLater()
            app = QCoreApplication.instance()
            if app is not None and engine.thread() == QThread.currentThread():
                QCoreApplication.sendPostedEvents(engine, QEvent.Type.DeferredDelete)
    return series


def _channel_difference(base: list, other: list) -> dict:
    total = scale = 0.0
    changed = 0
    resized = False
    for left, right in zip(base, other):
        if len(left) != len(right):
            resized = True
            changed += 1
            continue
        delta = sum(abs(a - b) for a, b in zip(left, right))
        changed += delta > 0.0
        total += delta
        scale += (sum(abs(a) for a in left) + sum(abs(b) for b in right)) / 2.0
    return {"difference": total / scale if scale > 1e-12 else (0.0 if total == 0.0 else math.inf),
            "frames_changed": changed / max(1, len(base)), "resized": resized}


def difference(base: list, other: list) -> dict:
    """How far ``other`` is from ``base``, per published channel: relative mean absolute difference and the share of
    frames that differ. ``difference`` is the largest channel's; ``channels`` lists those that moved at all."""
    if len(base) != len(other):
        return {"difference": math.inf, "frames_changed": 1.0, "channels": {}, "moved": True,
                "note": "frame count differs"}
    channels = {}
    for name in base[0]:
        entry = _channel_difference([frame[name] for frame in base], [frame[name] for frame in other])
        if entry["difference"] > 0.0 or entry["frames_changed"] > 0.0:
            channels[name] = entry
    worst = max((e["difference"] for e in channels.values()), default=0.0)
    changed = max((e["frames_changed"] for e in channels.values()), default=0.0)
    result = {"difference": worst, "frames_changed": changed, "channels": channels, "moved": bool(channels)}
    if any(e["resized"] for e in channels.values()):
        result["note"] = "the drawn element count changed"
    return result


def audit_mode(mode: str, clip_names: list[str], seconds: float, only: set | None = None) -> dict:
    """Every owned technical control moved on each clip; a row's difference is the largest over the clips."""
    settings = frozen(mode)
    base_values = baseline_values(mode, settings)
    plan = variations(mode, base_values)
    rows: dict = {}
    frames = 0
    for clip_name in clip_names:
        clip = load_clip(clip_name, seconds)
        frames += len(clip.frames)
        baselines: dict = {}

        def baseline(forced, clip=clip, baselines=baselines):
            token = json.dumps(forced, sort_keys=True)
            if token not in baselines:
                baselines[token] = replay(mode, clip, forced)
            return baselines[token]

        entries = [("(determinism control)", "repeat of the baseline", {}, {}, replay(mode, clip, {}))]
        for item in plan:
            if only and item["control"] not in only:
                continue
            entries.append((item["control"], item["label"], item["base_overrides"], item["overrides"], None))
        for control, label, base_overrides, overrides, series in entries:
            if series is None:
                series = replay(mode, clip, overrides)
            result = difference(baseline(base_overrides), series)
            row = rows.setdefault((control, label), {"control": control, "label": label, "difference": 0.0,
                                                     "frames_changed": 0.0, "channels": {}, "clips": {}})
            row["clips"][clip_name] = result["difference"]
            row["difference"] = max(row["difference"], result["difference"])
            row["frames_changed"] = max(row["frames_changed"], result["frames_changed"])
            if result.get("note"):
                row["note"] = result["note"]
            for name, entry in result["channels"].items():
                kept = row["channels"].get(name)
                if kept is None or entry["difference"] > kept["difference"]:
                    row["channels"][name] = entry
    return {"mode": mode, "clips": clip_names, "frames": frames, "baseline": base_values, "rows": list(rows.values())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modes", nargs="*", default=list(MODES), choices=MODES)
    parser.add_argument("--clips", nargs="*", default=["growing_pains", "human"], help="shipped Studio clip ids")
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    parser.add_argument("--only", nargs="*", help="limit to these control suffixes (bar_count, input_gain, ...)")
    parser.add_argument("--out", type=artifact_paths.evidence_arg)
    parser.add_argument("--list", action="store_true", help="print each mode's variations without replaying")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.instance() or QCoreApplication([])
    results = []
    for mode in args.modes:
        if args.list:
            values = baseline_values(mode, frozen(mode))
            print(mode, {k: v for k, v in values.items()})
            for item in variations(mode, values):
                print("   ", item["label"], item["overrides"])
            continue
        result = audit_mode(mode, args.clips, args.seconds, set(args.only) if args.only else None)
        results.append(result)
        print(f"== {mode} ({result['frames']} frames, {', '.join(args.clips)})")
        for row in result["rows"]:
            moved = ", ".join(f"{name} {entry['difference']:.3g}" for name, entry in row["channels"].items())
            print(f"  {row['control']:24s} {row['label']:40s} max {row['difference']:.4g}"
                  f"  frames {row['frames_changed']:.0%}  [{moved}] {row.get('note', '')}")
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

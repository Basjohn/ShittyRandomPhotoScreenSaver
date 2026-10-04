"""Voxel Sphere promotion golden (S19): python -m tools.visualizer_replay.sphere_golden [--write]

The behavioural reference the shared-Scene3D promotion is measured against
(``Docs/Reference/Sphere_Visualizer.md`` "Promotion golden gate"): both original goldens (Glass
Current, Voxel Bloom) replayed through the production capture on one deterministic real-scale
clip (silence, flat/low qualified events, vocals, kicks and snares, a sustained loud bed, a big
hit, silence), recording every authored Sphere output per frame, the resolved hidden technical
profile and each preset's resolved parameters.

It is a reference, not a lock (operator 2026-10-04): a reaction change is allowed when it is
measured and intended. Without ``--write`` the tool replays and prints what differs from the
committed golden, per segment; ``--write`` re-records it (only for an intended, documented
change). ``tests/test_sphere_promotion_golden.py`` fails on any unreviewed difference.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
from pathlib import Path

GOLDEN = Path(__file__).resolve().parents[2] / "tests/goldens/visualizer_replay/sphere_promotion.json"
# Both original goldens as curated, and Voxel Bloom with Particle Outtake on so the outtake half of
# the vocabulary is covered whatever the curated snapshots currently choose.
PRESETS = ((0, "glass_current", None), (1, "voxel_bloom", None),
           (1, "voxel_bloom_outtake", {"sphere_particle_outtake_enabled": True}))
FRAME_US = 11_111                           # the logical cadence (90 Hz)
BANDS = 64
# (name, seconds, loudness, presence, spectrum emphasis (low, mid, high), events: (kind, strength,
# period s, phase s)). Loudness and presence are the transient bus's real units (3-17 in music).
# Quiet passages follow loud ones, so the passage ramp (intensity relative to the track's recent
# loud level) is exercised, not only absolute loudness.
SEGMENTS = (
    ("silence", 1.0, 0.0, 0.0, (0.0, 0.0, 0.0), ()),
    ("kicks", 2.0, 11.0, 1.3, (1.5, 1.0, 0.7), (("kick", 0.95, 1 / 3, 0.1), ("snare", 0.8, 2 / 3, 0.43))),
    ("flat_low", 2.0, 3.5, 0.5, (1.0, 0.8, 0.5), (("kick", 0.6, 0.5, 0.25),)),
    ("vocals", 2.0, 7.0, 1.0, (0.6, 1.4, 1.0), (("vocal_swell", 0.85, 0.6, 0.3),)),
    ("sustained", 2.0, 13.0, 1.1, (1.1, 1.1, 0.9), ()),
    ("big_hit", 1.0, 17.0, 1.8, (1.6, 1.2, 1.0), (("kick", 1.0, 0.5, 0.02),)),
    ("quiet_outro", 2.0, 4.0, 0.6, (0.8, 0.9, 0.6), (("kick", 0.7, 0.5, 0.2), ("vocal_swell", 0.6, 0.9, 0.5))),
    ("tail_silence", 1.0, 0.0, 0.0, (0.0, 0.0, 0.0), ()),
)
_FLUX_BANDS = {"kick": (0, 10, 2.6), "snare": (10, 32, 1.9), "vocal_swell": (18, 44, 1.8)}
_ONSET_KIND = {"kick": "kick", "snare": "snare", "vocal_swell": "vocal_swell"}


def _profile(k: int, emphasis) -> float:
    low, mid, high = emphasis
    x = k / (BANDS - 1)
    return low * max(0.0, 1.0 - x * 3.0) + mid * max(0.0, 1.0 - abs(x - 0.45) * 3.0) + high * max(0.0, x * 2.0 - 1.0)


def golden_clip():
    """The deterministic real-scale clip and its segment boundaries (first frame index of each)."""
    from widgets.spotify_visualizer.feature_frame import (
        REAL_SCALE_SCHEMA_VERSION, BandEnergy, EnergyLanes, FeatureClip, FeatureFrame, RealScaleLanes,
        RecordedOnset, TransientEnergy, TypedEvent,
    )

    frames, bounds, index = [], [], 0
    for name, seconds, loudness, presence, emphasis, events in SEGMENTS:
        bounds.append((name, index))
        count = int(round(seconds * 90))
        flux: dict[str, int] = {}
        for step in range(count):
            t = step / 90.0
            fired = []
            for kind, strength, period, phase in events:
                if t >= phase and int((t - phase) / period) != int((t - phase - 1 / 90.0) / period) or \
                        (step == int(round(phase * 90))):
                    fired.append((kind, strength))
                    flux[kind] = 4
            # A hit raises its band for a few frames (the spectral flux Sphere's capture reads).
            spectrum = []
            for k in range(BANDS):
                value = loudness * _profile(k, emphasis) * (1.0 + 0.03 * ((k * 7 + step) % 5))
                for kind, frames_left in flux.items():
                    lo, hi, gain = _FLUX_BANDS[kind]
                    if frames_left > 0 and lo <= k < hi:
                        value *= 1.0 + (gain - 1.0) * frames_left / 4.0
                spectrum.append(value)
            flux = {kind: left - 1 for kind, left in flux.items() if left > 1}
            peak = loudness * (1.6 if fired else 1.0)
            unit = min(1.0, peak / 17.0)
            band = BandEnergy(bass=unit * min(1.0, emphasis[0]), mid=unit * min(1.0, emphasis[1]),
                              high=unit * min(1.0, emphasis[2]), overall=unit)
            hit = max((s for _k, s in fired), default=0.0)
            transient = TransientEnergy(bass=hit if any(k == "kick" for k, _s in fired) else 0.0,
                                        mid=hit if any(k != "kick" for k, _s in fired) else 0.0, high=0.0,
                                        overall=hit, onset_detected=bool(fired),
                                        onset_type=("bass" if any(k == "kick" for k, _s in fired) else "mid")
                                        if fired else "", onset_strength=hit)
            live = tuple(min(2.5, peak * 0.3 * w) for w in (min(1.0, emphasis[0]), min(1.0, emphasis[1]),
                                                             min(1.0, emphasis[2]), 1.0))
            bars = tuple(min(1.0, spectrum[int(i * (BANDS - 1) / 31)] / 17.0) for i in range(32))
            frames.append(FeatureFrame(
                timestamp_us=1_000_000 + index * FRAME_US,
                energy=EnergyLanes(continuous=band, pre_agc=band, bubble=band, transient=transient),
                raw_bars=bars, waveform=tuple(0.2 * unit * ((i % 8) / 4.0 - 1.0) for i in range(64)),
                playing=True, visible=True, mode="sphere", schema_version=REAL_SCALE_SCHEMA_VERSION,
                real=RealScaleLanes(
                    live=live, musical_level=(peak, presence * (1.4 if fired else 1.0)),
                    analysis_spectrum=tuple(spectrum),
                    events=tuple(TypedEvent(kind, strength) for kind, strength in fired),
                    onsets=tuple(RecordedOnset(_ONSET_KIND[kind], strength, 2.5 * strength, peak,
                                               presence * 1.4) for kind, strength in fired)),
            ))
            index += 1
    return FeatureClip(name="sphere_promotion", frames=tuple(frames)), tuple(bounds)


def _round(value):
    if isinstance(value, float):
        return round(value, 7)
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    return value


def _frame_record(state) -> dict:
    record = {field.name: getattr(state, field.name) for field in dataclasses.fields(state)
              if field.name not in ("parameters", "particle_cohorts", "authored_time")}
    record["cohorts"] = [dataclasses.asdict(cohort) for cohort in state.particle_cohorts]
    return _round(record)


def capture() -> dict:
    """Replay both goldens and return the full reference document."""
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config

    from .driver import replay_clip

    clip, bounds = golden_clip()
    document = {"clip": {"frames": len(clip.frames), "segments": [list(b) for b in bounds]}, "presets": {}}
    for preset, name, overrides in PRESETS:
        activation = resolve_visualizer_activation_payload({"mode": "sphere", "preset_sphere": preset})
        model = SpotifyVisualizerSettings.from_mapping(activation.resolved_config, apply_preset_overlay=False,
                                                       resolve_preset_indices=False)
        technical = resolve_technical_config(build_technical_cache(None, model), "sphere")
        result = replay_clip(clip, "sphere", preset=preset, overrides=overrides)
        series = result["logical_series"]
        document["presets"][name] = {
            "preset_index": preset,
            "overrides": overrides or {},
            "technical_profile": _round(dict(technical)),
            # The 3D Detail tier is a hardware choice (the GPU's), not behaviour: left out.
            "parameters": _round({k: v for k, v in dict(series[0].mode_state.parameters).items()
                                  if isinstance(v, (int, float, str, bool, list, tuple))
                                  and k != "scene3d_detail"}),
            "frames": [_frame_record(logical.mode_state) for logical in series],
        }
    return document


def _compact(document: dict) -> dict:
    """Store a preset whose frames equal an earlier preset's by reference (the curated goldens
    differ only in presentation today)."""
    out = {"clip": document["clip"], "presets": {}}
    for name, entry in document["presets"].items():
        same = next((other for other, kept in out["presets"].items()
                     if "frames" in kept and kept["frames"] == entry["frames"]), None)
        out["presets"][name] = ({**{k: v for k, v in entry.items() if k != "frames"}, "frames_same_as": same}
                                if same else entry)
    return out


def load_golden() -> dict:
    """The committed golden with every preset's frames expanded."""
    document = json.loads(GOLDEN.read_text(encoding="utf-8"))
    presets = document["presets"]
    for entry in presets.values():
        if "frames_same_as" in entry:
            entry["frames"] = presets[entry.pop("frames_same_as")]["frames"]
    return document


def summarise(frames, bounds) -> dict:
    """Per segment: peak fragment drive, cohorts launched, mean tracer/rotation drive and size."""
    edges = [start for _name, start in bounds] + [len(frames)]
    out = {}
    for (name, start), stop in zip(bounds, edges[1:]):
        part = frames[start:stop]
        launches = sum(1 for prev, cur in zip(part, part[1:]) if len(cur["cohorts"]) > len(prev["cohorts"]))
        out[name] = {
            "fragment_peak": max((max(f["section_drives"] or [0.0]) for f in part), default=0.0),
            "cohort_launches": launches,
            "tracer": statistics.fmean(f["tracer_drive"] for f in part),
            "rotation": statistics.fmean(f["rotation_drive"] for f in part),
            "size": statistics.fmean(f["size_pulse"] for f in part),
        }
    return out


def differences(golden: dict, current: dict) -> list[str]:
    """Readable differences: technical profile and parameters exactly, frames by segment summary
    and the first differing frame."""
    lines = []
    bounds = [tuple(b) for b in golden["clip"]["segments"]]
    for name, reference in golden["presets"].items():
        now = current["presets"][name]
        for key in ("technical_profile", "parameters"):
            if reference[key] != now[key]:
                changed = sorted(k for k in set(reference[key]) | set(now[key])
                                 if reference[key].get(k) != now[key].get(k))
                lines.append(f"{name}: {key} differs: {changed}")
        if reference["frames"] != now["frames"]:
            first = next(i for i, (a, b) in enumerate(zip(reference["frames"], now["frames"])) if a != b) \
                if len(reference["frames"]) == len(now["frames"]) else 0
            lines.append(f"{name}: frames differ from frame {first}")
            before, after = summarise(reference["frames"], bounds), summarise(now["frames"], bounds)
            for segment in before:
                changes = {k: (round(before[segment][k], 3), round(after[segment][k], 3))
                           for k in before[segment] if before[segment][k] != after[segment][k]}
                if changes:
                    lines.append(f"  {segment}: " + ", ".join(f"{k} {a} -> {b}" for k, (a, b) in changes.items()))
    return lines


# Visual reference: renderer captures of replayed snapshots through the production render host,
# offscreen, the item in the middle of a window one item larger on every side (Sphere overflows).
# (name, golden preset, segment, frames into it, item width, height). Visual parity is a floor, not
# a ceiling: a deliberate upgrade is reviewed by eye on the before/after sheets (--visual) and then
# re-recorded (--write-visual).
VISUAL_DIR = GOLDEN.parent / "sphere_visual"
VISUAL_TIER = "High"                         # pinned: the reference must not depend on the GPU
VISUAL_REVIEW = Path(__file__).resolve().parents[2] / "logs" / "sphere_visual_review"
VISUAL_CASES = (
    ("glass_current_rest", "glass_current", "silence", 45, 480, 270),
    ("glass_current_kicks", "glass_current", "kicks", 60, 480, 270),
    ("glass_current_big_hit", "glass_current", "big_hit", 12, 480, 270),
    ("voxel_bloom_rest", "voxel_bloom", "silence", 45, 480, 270),
    ("voxel_bloom_kicks", "voxel_bloom", "kicks", 60, 480, 270),
    ("voxel_bloom_big_hit", "voxel_bloom", "big_hit", 12, 480, 270),
    ("glass_current_wide", "glass_current", "big_hit", 12, 960, 120),
    ("glass_current_tall", "glass_current", "big_hit", 12, 200, 600),
)


def _custom_presentation(width: float, height: float):
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy

    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("sphere"), display_size=(1920.0, 1080.0),
        viewport_extent=(float(width), float(height)), border_width=0.0, corner_radius=0.0, content_inset=0.0,
        background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0), shadow_enabled=False,
        shadow_color=(0, 0, 0, 0), shadow_blur=0.0, shadow_offset=(0.0, 0.0), shadow_spread=0.0,
        shadow_extensions=(0.0, 0.0, 0.0, 0.0),
    )


def render_visual_cases(cases=VISUAL_CASES) -> dict:
    """Render each case; returns name -> RGBA uint8 array (top row first). Needs a QApplication."""
    import numpy as np
    from OpenGL import GL as gl

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.transition_contact_sheet import TransitionCapture
    from widgets.spotify_visualizer.render_state import freeze_render_fields

    from .driver import replay_clip

    clip, bounds = golden_clip()
    starts = dict(bounds)
    presets = {name: (preset, overrides) for preset, name, overrides in PRESETS}
    snapshots = {}
    for preset_name in sorted({case[1] for case in cases}):
        wanted = {name: starts[segment] + offset for name, golden, segment, offset, *_ in cases if golden == preset_name}
        preset, overrides = presets[preset_name]
        result = replay_clip(clip, "sphere", preset=preset, overrides=overrides, snapshots_at=wanted.values())
        snapshots.update({name: result["snapshots"][index] for name, index in wanted.items()})
    images = {}
    for name, _golden, _segment, _offset, width, height in cases:
        # The replay presents the canonical item; resolve this case's CUSTOM extent through the
        # production presentation resolver (Sphere centres itself in the presentation's content).
        snapshot = snapshots[name]
        state = snapshot.logical.mode_state
        state = dataclasses.replace(state, parameters=freeze_render_fields(
            {**dict(state.parameters), "scene3d_detail": VISUAL_TIER}))
        snapshots[name] = dataclasses.replace(snapshot, presentation=_custom_presentation(width, height),
                                              logical=dataclasses.replace(snapshot.logical, mode_state=state))
        window_w, window_h = 3 * width, 3 * height
        matrix = (2 / window_w, 0, 0, 0, 0, -2 / window_h, 0, 0, 0, 0, 1, 0, -1 / 3, 1 / 3, 0, 1)
        capture = TransitionCapture(window_w, window_h)
        host = QuickVisualizerRenderHost()
        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glViewport(0, 0, window_w, window_h)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            host.render(snapshot=snapshots[name], viewport=(0, 0, window_w, window_h),
                        logical_size=(float(width), float(height)), matrix_values=matrix)
            pixels = gl.glReadPixels(0, 0, window_w, window_h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            images[name] = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(window_h, window_w, 4)[::-1].copy()
        finally:
            host.release_resources()
            capture.close()
    return images


def _save_png(path: Path, pixels) -> None:
    from PySide6.QtGui import QImage

    height, width = pixels.shape[:2]
    image = QImage(pixels.data, width, height, 4 * width, QImage.Format.Format_RGBA8888)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path)):
        raise OSError(f"could not write {path}")


def load_png(path: Path):
    import numpy as np
    from PySide6.QtGui import QImage

    image = QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull():
        raise FileNotFoundError(path)
    data = bytes(image.constBits())[: image.sizeInBytes()]
    return np.frombuffer(data, dtype=np.uint8).reshape(image.height(), image.bytesPerLine() // 4, 4)[:, :image.width()].copy()


def visual_difference(reference, current) -> dict:
    """Share of pixels whose largest channel difference exceeds 2/255 (driver noise is <=1-2),
    and the mean absolute difference."""
    import numpy as np

    if reference.shape != current.shape:
        return {"shape": (reference.shape, current.shape), "changed": 1.0, "mean": 255.0}
    delta = np.abs(reference.astype(np.int16) - current.astype(np.int16)).max(axis=2)
    return {"changed": float((delta > 2).mean()), "mean": float(delta.mean())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="re-record the golden (an intended, documented change)")
    parser.add_argument("--visual", action="store_true",
                        help="render the visual cases, compare and write before/after sheets for review")
    parser.add_argument("--write-visual", action="store_true", help="re-record the visual reference")
    args = parser.parse_args()
    if args.visual or args.write_visual:
        import numpy as np
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        images = render_visual_cases()
        for name, pixels in images.items():
            path = VISUAL_DIR / f"{name}.png"
            if args.write_visual:
                _save_png(path, pixels)
                print(f"wrote {path}")
                continue
            reference = load_png(path) if path.exists() else np.zeros_like(pixels)
            print(f"{name:24s} {visual_difference(reference, pixels)}")
            if reference.shape == pixels.shape:
                _save_png(VISUAL_REVIEW / f"{name}.png", np.concatenate([reference, pixels], axis=1))
        if args.visual:
            print(f"before | after sheets: {VISUAL_REVIEW}")
        return
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.instance() or QCoreApplication([])
    current = capture()
    bounds = [tuple(b) for b in current["clip"]["segments"]]
    for name, data in current["presets"].items():
        print(f"== {name}")
        for segment, values in summarise(data["frames"], bounds).items():
            print(f"  {segment:13s} " + "  ".join(f"{k} {v:.3f}" if isinstance(v, float) else f"{k} {v}"
                                                 for k, v in values.items()))
    if args.write:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(_compact(current), separators=(",", ":"), sort_keys=True) + "\n",
                          encoding="utf-8")
        print(f"wrote {GOLDEN}")
        return
    if GOLDEN.exists():
        lines = differences(load_golden(), current)
        print("\n".join(lines) if lines else "matches the golden")


if __name__ == "__main__":
    main()

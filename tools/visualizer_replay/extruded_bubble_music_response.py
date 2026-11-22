"""Music vs Extruded Bubble on-screen motion, by bubble age: does an old bubble answer the music as a newborn does?

Operator, 22 Nov: older regular bubbles are "not consistently accelerated by music". World-space speed along the stream
was exactly the stream speed for every free bubble (tests/test_extruded_bubble_stream_transport.py), which says
nothing about what the eye sees: projection, depth and position on screen. This trace measures the screen itself.

One recorded take is replayed through the checkout's ``ExtrudedBubbleFrameRuntime`` with a curated preset's controls
(no renderer, no window). Every drawn bubble (the snapshot's packed bubbles, alpha > 0.05) is projected through the
preset's own camera (``parameter_camera``: its pose, lens and eye offset, 16:9) and its on-screen speed in px/s at
1920x1080 taken tick to tick, then split by age: newborn (< 5 s), 5-15 s, older (> 15 s). Per band and tick: the
median px/s, and the median "relative speed": a bubble's px/s over the px/s the stream alone would give it there at
a fixed reference stream speed (its screen-space gain along the stream, taken at its own position), so depth,
foreshortening and screen position cancel and only how fast it is carried remains, music modulation included.

The report stacks the song's PCM envelope (rms dBFS and 30-150 Hz bass dB from the capture history, the shared
``waveform_music_response.pcm_envelope``) and the stream speed above each band's relative speed, and prints per band:
correlation of its 0.5 s means with the stream speed and with the bass, its modulation depth (p90 / p10 of the 0.5 s
means) and its lag to the stream speed. Older bands must rise and fall with the music as newborns do.

    python -m tools.visualizer_replay.extruded_bubble_music_response --clip ragdoll_quiet_intro_loud_end1
        --preset 9 --start 0 --seconds 120 --out <evidence dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECORDINGS = Path("F:/Programming/Apps/ShittyRandomPhotoScreenSaver/logs/visualizer_recordings")
BANDS = (("newborn <5 s", 0.0, 5.0), ("5-15 s", 5.0, 15.0), ("older >15 s", 15.0, 1e9))
WIDTH, HEIGHT = 1920, 1080
COLUMNS = ("t", "rms_db", "bass_db", "stream_speed", "count",
           *(f"{name}:{k}" for name, _lo, _hi in BANDS for k in ("n", "px", "rel")))


def preset_controls(preset: int):
    """The curated preset's resolved parameters and simulation controls (1-based preset number)."""
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import controls_from_parameters
    activation = resolve_visualizer_activation_payload(
        {"mode": "extruded_bubble", "preset_extruded_bubble": preset - 1}, mode="extruded_bubble")
    params = {k.split(".")[-1]: v for k, v in activation.resolved_config.items()}
    return controls_from_parameters(params), params


def trace(clip_name: str, preset: int, start: float, seconds: float, reference_speed: float = 1.0):
    """Rows of COLUMNS, one per tick, of ``seconds`` after ``start`` (the simulation runs from the take's start)."""
    import numpy as np
    from rendering.gl_programs.extruded_bubble_scene import parameter_camera
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from tools.visualizer_replay.waveform_music_response import pcm_envelope
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime
    from widgets.spotify_visualizer.extruded_bubble_simulation import BUBBLE_STRIDE
    from widgets.spotify_visualizer.feature_frame import FeatureClip

    controls, params = preset_controls(preset)
    _a, w2v, eye, tan, _p = parameter_camera(params, WIDTH / HEIGHT, 1.0)
    rotation = np.asarray(w2v, dtype=float).reshape(3, 3).T
    eye = np.asarray(eye, dtype=float)

    def project(points):
        d = (points - eye) @ rotation.T
        depth = -d[:, 2]
        ok = depth > 0.1
        safe = np.where(ok, depth, 1.0)
        x = d[:, 0] / (safe * tan[0]) * WIDTH / 2
        y = d[:, 1] / (safe * tan[1]) * HEIGHT / 2
        ok &= (np.abs(x) < WIDTH / 2) & (np.abs(y) < HEIGHT / 2)
        return np.stack((x, y), axis=1), ok

    clip = FeatureClip.from_jsonl_bytes(clip_name, (RECORDINGS / f"{clip_name}.jsonl").read_bytes())
    runtime = ExtrudedBubbleFrameRuntime(0x5EB0)
    engine = ReplayBeatEngine(32)
    t0 = clip.frames[0].timestamp_us / 1e6
    born, last = {}, {}
    rows, previous_spectrum = [], None
    for frame in clip.frames:
        now = frame.timestamp_us / 1e6 - t0
        if now > start + seconds:
            break
        engine.accept_feature_frame(frame)
        bands = engine.get_extruded_bubble_body_bands()
        snap = runtime.advance(onsets=engine.get_onset_events(runtime.onset_serial), now_ts=now,
                               playing=bool(frame.playing), identity=(1, 1, 1), source_identity=(1, 1),
                               body_bands=(bands.bass, bands.mid, bands.high) if bands else (0.0, 0.0, 0.0),
                               controls=controls)
        rms_db = bass_db = float("nan")
        if frame.capture_history is not None:
            rms_db, bass_db, _flux, previous_spectrum = pcm_envelope(frame.capture_history, previous_spectrum)
        packed = np.asarray(snap.bubbles, dtype=float).reshape(-1, BUBBLE_STRIDE)
        visible = packed[packed[:, 4] > 0.05]
        screen, ok = project(visible[:, :3]) if len(visible) else (np.zeros((0, 2)), np.zeros(0, bool))
        # Screen-space gain along the stream at each bubble: px per world unit carried (1 mm step).
        direction = np.asarray(snap.stream, dtype=float)
        ahead, _ok = project(visible[:, :3] + direction * 1e-3) if len(visible) else (screen, ok)
        gain = np.linalg.norm(ahead - screen, axis=1) / 1e-3
        per_band = {name: ([], []) for name, _lo, _hi in BANDS}
        seen = set()
        for row, point, on, g in zip(visible, screen, ok, gain):
            ident = int(row[6])
            seen.add(ident)
            born.setdefault(ident, now)
            if on and ident in last and now > last[ident][0]:
                speed = float(np.linalg.norm(point - last[ident][1])) / (now - last[ident][0])
                age = now - born[ident]
                for name, lo, hi in BANDS:
                    if lo <= age < hi:
                        per_band[name][0].append(speed)
                        if g > 1.0:            # end-on to the view: no screen motion to compare
                            per_band[name][1].append(speed / (g * reference_speed))
            last[ident] = (now, point)
        for ident in list(last):
            if ident not in seen:
                last.pop(ident)
        if now < start:
            continue
        values = [now, rms_db, bass_db, float(snap.stream_speed), float(len(visible))]
        for name, _lo, _hi in BANDS:
            px, rel = per_band[name]
            values += [len(px), float(np.median(px)) if px else float("nan"),
                       float(np.median(rel)) if rel else float("nan")]
        rows.append(values)
    return np.asarray(rows, dtype=float)


def _means(t, values, step=0.5):
    import numpy as np
    edges = np.arange(t[0], t[-1], step)
    out = []
    for a in edges:
        m = (t >= a) & (t < a + step) & np.isfinite(values)
        out.append(float(values[m].mean()) if m.any() else float("nan"))
    return np.asarray(out)


def report(rows, out: Path, label: str) -> list[str]:
    import numpy as np
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / f"{label}.npy", rows)
    col = {name: k for k, name in enumerate(COLUMNS)}
    t = rows[:, 0]
    stream = _means(t, rows[:, col["stream_speed"]])
    bass = _means(t, rows[:, col["bass_db"]])
    lines = [f"{label}: ticks {len(rows)}, {t[0]:.1f}-{t[-1]:.1f} s, drawn bubbles p50 "
             f"{np.median(rows[:, col['count']]):.0f}"]

    def corr(a, b):
        m = np.isfinite(a) & np.isfinite(b)
        return float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() > 4 and np.ptp(a[m]) and np.ptp(b[m]) else float("nan")

    def lag(a, b, most=6):
        best = (-2.0, 0)
        for shift in range(-most, most + 1):
            x, y = (a[shift:], b[:len(b) - shift]) if shift >= 0 else (a[:shift], b[-shift:])
            c = corr(x, y)
            if np.isfinite(c) and c > best[0]:
                best = (c, shift)
        return best[1] * 0.5
    for name, _lo, _hi in BANDS:
        rel = _means(t, rows[:, col[f"{name}:rel"]])
        px = _means(t, rows[:, col[f"{name}:px"]])
        n = rows[:, col[f"{name}:n"]]
        finite = rel[np.isfinite(rel)]
        depth = (float(np.percentile(finite, 90) / max(1e-6, np.percentile(finite, 10)))
                 if len(finite) > 4 else float("nan"))
        lines.append(f"  {name:13s} bubbles/tick p50 {np.median(n):4.0f}  px/s p50 {np.nanmedian(px):6.1f}  "
                     f"relative speed: corr(stream) {corr(rel, stream):+.2f} corr(bass) {corr(rel, bass):+.2f} "
                     f"p90/p10 {depth:.2f} lag to stream {lag(rel, stream):+.1f} s; "
                     f"px/s corr(stream) {corr(px, stream):+.2f}")
    # Stacked traces: the music on top, the stream speed, then each band's relative speed (0.5 s means).
    panels = [("rms dBFS", _means(t, rows[:, col["rms_db"]]), (235, 235, 235)),
              ("bass dB 30-150 Hz", bass, (235, 235, 235)), ("stream speed", stream, (255, 200, 90))]
    colours = ((110, 200, 255), (130, 230, 140), (255, 120, 200))
    for (name, _lo, _hi), colour in zip(BANDS, colours):
        panels.append((f"{name} relative on-screen speed", _means(t, rows[:, col[f"{name}:rel"]]), colour))
    width, left, row_h = 1900, 170, 110
    image = Image.new("RGB", (width, 30 + row_h * len(panels)), (14, 14, 20))
    draw = ImageDraw.Draw(image)
    draw.text((10, 8), lines[0], fill="white")
    span = max(1e-6, t[-1] - t[0])
    xs = np.arange(len(stream)) * 0.5 / span * (width - left - 10) + left
    for row, (label_text, values, colour) in enumerate(panels):
        top = 30 + row * row_h
        finite = values[np.isfinite(values)]
        low, high = (float(np.percentile(finite, 1)), float(np.percentile(finite, 99))) if len(finite) else (0, 1)
        high = high if high > low else low + 1.0
        draw.text((10, top + 4), label_text, fill="white")
        draw.text((10, top + 22), f"{high:.2f}", fill=(140, 140, 140))
        draw.text((10, top + row_h - 18), f"{low:.2f}", fill=(140, 140, 140))
        for second in range(0, int(span) + 1, 5):
            x = left + (width - left - 10) * second / span
            draw.line((x, top, x, top + row_h - 4), fill=(32, 32, 42))
        points = [(float(x), top + 4 + (row_h - 12) * (1 - (min(high, max(low, float(v))) - low) / (high - low)))
                  for x, v in zip(xs, values) if np.isfinite(v)]
        if len(points) > 1:
            draw.line(points, fill=colour, width=2)
    image.save(out / f"{label}_music_vs_onscreen_speed.png")
    (out / f"{label}.txt").write_text("\n".join(lines), encoding="utf-8")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--clip", required=True, help="a take in logs/visualizer_recordings (name without .jsonl)")
    parser.add_argument("--preset", type=int, action="append", required=True, help="curated preset number (1-based)")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for preset in args.preset:
        rows = trace(args.clip, preset, args.start, args.seconds)
        print("\n".join(report(rows, args.out, f"{args.clip}_p{preset}_{int(args.start)}s")))


if __name__ == "__main__":
    main()

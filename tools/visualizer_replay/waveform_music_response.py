"""Music vs Waveform response: the song's own envelope against what the ribbon visibly does, per song.

Operator, 6 Nov: "Can you not get similar traces of the raw song, see how the mode overlaps with that ... and see poor
behaviour much more starkly?" A response trace alone hides its failures. Put under the music's own envelope, they are
plain to see:
  * saturation: the response sits pinned while the music changes;
  * dead zone: the music changes and the response does not;
  * re-scaling: the same music level draws a different size later in a song or after a break (adaptive memory);
  * spurious motion: the response moves while the music holds.

Three steps (no renderer, no window):

  music     the INDEPENDENT music envelope straight from the recording's PCM (each feature frame's capture history:
            RMS dBFS over the newest 1024 samples, 30-150 Hz energy dB and positive spectral flux over 2048), with
            the pipeline's own real-music loudness (3-17 in music, guide "real music scales") beside it.
  response  replays continuous-play dynamics inputs (``waveform_ribbon_breathing_probe.record`` output: songs back to
            back without a reset) through a checkout's ``WaveformDynamics`` for curated presets; per tick: visible
            amplitude (|x| <= 16), largest visible swell, drives, effective roll, floor lift.
  report    joins them per song: stacked traces (music on top, every response file overlaid below), loudness ->
            response scatter coloured by time in song, and per-song metrics: correlation of 1 s means with the
            loudness, saturation and dead shares, and the response spread at equal loudness early vs late.

    python -m tools.visualizer_replay.waveform_music_response music --clips a.jsonl,b.jsonl --out music.npy
    python tools/visualizer_replay/waveform_ribbon_breathing_probe.py record ...   (or reuse a chain .npy)
    python -m tools.visualizer_replay.waveform_music_response response --root <checkout> --inputs chain.npy
        --presets 1,4,7 --out main.npy
    python -m tools.visualizer_replay.waveform_music_response report --music music.npy --response main=main_p4.npy
        --response branch=branch_p4.npy --out <dir>

Travelling and frozen reaction modes show only part of the ribbon changing at a time; ``live`` (largest visible swell)
is the first-cut measure of that part and ``born`` (``born_swell``) the mode-specific one: the swell where it enters
the view, or the unfrozen part of Frozen Past. ``response --mode/--direction/--breathing`` overrides the presets.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

MUSIC_COLUMNS = ("song", "t", "rms_db", "bass_db", "flux", "loudness", "presence")
RESPONSE_COLUMNS = ("t", "song", "song_time", "level", "view", "live", "height", "bend", "lift_drive", "roll",
                    "kick_sense", "floor_lift", "born")
BORN_WINDOW = 4.0   # scene units inside the view edge (or about the centre) where a travelling swell is new


def music(clips: list[Path], out: Path) -> None:
    import numpy as np
    from widgets.spotify_visualizer.feature_frame import load_jsonl
    rows = []
    for song, path in enumerate(clips):
        clip = load_jsonl(path)
        origin = clip.frames[0].timestamp_us
        previous = None
        for frame in clip.frames:
            history = frame.capture_history
            real = frame.real
            if history is None or real is None:
                continue
            pcm = np.frombuffer(history.pcm_f32le, "<f4").astype(np.float64)
            rate = history.sample_rate
            recent = pcm[-1024:]
            rms_db = 20.0 * np.log10(max(1e-6, float(np.sqrt(np.mean(recent * recent)))))
            window = pcm[-2048:] if pcm.size >= 2048 else np.pad(pcm, (2048 - pcm.size, 0))
            spectrum = np.abs(np.fft.rfft(window * np.hanning(window.size)))
            freqs = np.fft.rfftfreq(window.size, 1.0 / rate)
            bass = spectrum[(freqs >= 30) & (freqs <= 150)]
            bass_db = 10.0 * np.log10(max(1e-9, float(np.sum(bass * bass))))
            flux = 0.0 if previous is None else float(np.sum(np.maximum(0.0, spectrum - previous)))
            previous = spectrum
            loudness, presence = real.musical_level
            rows.append((song, (frame.timestamp_us - origin) / 1e6, rms_db, bass_db, flux, loudness, presence))
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(out, np.asarray(rows, np.float64))
    print("music rows", len(rows), "->", out)


def born_swell(model, controls, view=16.0):
    """The mode's newly born ("live") part, in the units of ``live`` (gain above 1 x height): Travelling Pulse and
    Group Wave, the swell where it enters the view (the view edge it travels in from, or about the centre for Centre
    Out); Frozen Past, the unfrozen travelling envelope over the view (never the held trail); Whole Swell, the whole
    field (every part is live)."""
    import numpy as np
    from core.waveform_ribbon_dynamics import PULSE_GRID
    pulse = controls.pulse
    strength, height = model._value("bend"), model._value("height")
    share = model._geom_share[0]
    if pulse.mode == "Frozen Past":
        frozen = getattr(model, "_frozen_swell", None)
        live = frozen[0] if frozen is not None else model._geom
        return float(share * .7 * strength * np.max(live[np.abs(PULSE_GRID) <= view])) * height
    if pulse.mode == "Whole Swell":
        window = np.abs(PULSE_GRID) <= view
    elif pulse.direction == "Centre Out":
        window = np.abs(PULSE_GRID) <= BORN_WINDOW / 2
    else:
        entering_high = (pulse.direction == "Head To Tail") == (getattr(model, "direction", 1.0) >= 0)
        window = ((PULSE_GRID <= view) & (PULSE_GRID >= view - BORN_WINDOW)) if entering_high else             ((PULSE_GRID >= -view) & (PULSE_GRID <= -view + BORN_WINDOW))
    return float(share * .7 * strength * np.max(model._geom[window])) * height


def response(root: Path, inputs_path: Path, presets: list[int], out: Path, mode: str | None = None,
             direction: str | None = None, breathing: float | None = None) -> None:
    sys.path.insert(0, str(root.resolve()))
    from dataclasses import replace
    import numpy as np
    import core.waveform_ribbon_dynamics as dyn
    from tools.visualizer_replay.waveform_ribbon_breathing_probe import preset_controls, swell_of, view_amplitude
    inputs = np.load(inputs_path)
    roll_key = getattr(dyn, "KICK_ROLL", 0.0)
    for preset in presets:
        controls = preset_controls(preset - 1)
        if mode or direction:
            controls = replace(controls, pulse=replace(controls.pulse, mode=mode or controls.pulse.mode,
                                                       direction=direction or controls.pulse.direction))
        if breathing is not None:
            controls = replace(controls, breathing=breathing)
        model = dyn.WaveformDynamics(controls)
        while not model.ready:
            model.advance(1 / 90, bands=(0.0, 0.0, 0.0), intensity=0.0, presence=0.0)
        rows, t = [], 0.0
        for row in inputs:
            dt, b, m, h, intensity, presence, hit, c0, c1, c2, accent, song, song_time = row[:13]
            snap = model.advance(float(dt), bands=(b, m, h), intensity=intensity, presence=presence, hit=hit,
                                 hit_components=(c0, c1, c2), accent=None if accent < 0 else accent,
                                 view_span=(-16.0, 16.0))
            t += dt
            drives = dict(snap.drives)
            target = model._value("rotation") if controls.rotation_enabled else 0.0
            sense = float(getattr(model, "kick_sense", 0.0))
            roll = model.angular_speed + (np.copysign(roll_key * sense, target) if controls.rotation_enabled else 0.0)
            rows.append((t, song, song_time, intensity * presence, view_amplitude(snap, 16.0), swell_of(model),
                         drives["height"], drives["bend"], drives["lift"], roll, sense,
                         float(np.max(model._trough_lift)), born_swell(model, controls)))
        target_path = out.with_name(f"{out.stem}_p{preset}.npy")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(target_path, np.asarray(rows, np.float64))
        print("response", preset, len(rows), "->", target_path)


def _smooth(values, width):
    import numpy as np
    if width <= 1:
        return values
    kernel = np.ones(width) / width
    return np.convolve(values, kernel, mode="same")


def report(music_path: Path, responses: dict[str, Path], out: Path) -> None:
    import numpy as np
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    m = np.load(music_path)
    loaded = {name: np.load(path) for name, path in responses.items()}
    colours = [(110, 160, 255), (255, 150, 60), (120, 220, 140), (230, 110, 200)]
    lines = []
    for song in sorted(set(m[:, 0].astype(int))):
        ms = m[m[:, 0] == song]
        width, left, row_h = 1900, 120, 120
        joined = {}
        for name, data in loaded.items():
            rs = data[data[:, 1] == song]
            if not len(rs):
                continue
            # Response sampled at each music frame (nearest tick in time).
            index = np.clip(np.searchsorted(rs[:, 2], ms[:, 1]), 0, len(rs) - 1)
            joined[name] = rs[index]
        white = (235, 235, 235)
        panels = [("loudness 3-17", [(ms[:, 5], white)]), ("rms dBFS", [(ms[:, 2], white)]),
                  ("bass dB", [(ms[:, 3], white)]), ("flux", [(_smooth(ms[:, 4], 9), white)])]
        for column, label in ((4, "view amplitude"), (5, "live swell"), (12, "born / unfrozen swell"),
                              (7, "Pulse Strength (bend)"), (9, "roll deg/s"), (11, "floor lift")):
            series = [(rs[:, column], colours[k]) for k, rs in enumerate(joined.values()) if rs.shape[1] > column]
            if series:
                panels.append((label, series))
        image = Image.new("RGB", (width, 30 + row_h * len(panels)), (14, 14, 20))
        draw = ImageDraw.Draw(image)
        draw.text((10, 8), f"song {song}: music (white) on top; response: " +
                  ", ".join(f"{n} {c}" for n, c in zip(joined, colours)), fill="white")
        t_max = float(ms[-1, 1]) or 1.0
        times = ms[:, 1]
        for row, (label, series) in enumerate(panels):
            low = float(min(np.min(values) for values, _c in series))
            high = float(max(np.max(values) for values, _c in series))
            high = high if high > low else low + 1.0
            top = 30 + row * row_h
            draw.text((10, top + 4), label, fill="white")
            draw.text((10, top + 20), f"{high:.2f}", fill=(140, 140, 140))
            draw.text((10, top + row_h - 18), f"{low:.2f}", fill=(140, 140, 140))
            for second in range(0, int(t_max) + 1, 5):
                x = left + (width - left - 10) * second / t_max
                draw.line((x, top, x, top + row_h - 4), fill=(32, 32, 42))
            for values, colour in series:
                points = [(left + (width - left - 10) * float(tt) / t_max,
                           top + 4 + (row_h - 12) * (1 - (float(v) - low) / (high - low)))
                          for tt, v in zip(times, values)]
                draw.line(points, fill=colour, width=1)
        image.save(out / f"song{song}_music_vs_response.png")
        # Scatter: loudness (x) -> view amplitude (y), colour = time in song (blue early, yellow late).
        scatter = Image.new("RGB", (620 * max(1, len(joined)), 520), (14, 14, 20))
        sd = ImageDraw.Draw(scatter)
        lo, hi = float(np.percentile(ms[:, 5], 1)), float(np.percentile(ms[:, 5], 99))
        for k, (name, rs) in enumerate(joined.items()):
            vmax = max(float(np.max(r[:, 4])) for r in joined.values()) or 1.0
            ox = 620 * k
            sd.text((ox + 10, 6), f"{name}: loudness -> view amplitude (colour: time)", fill="white")
            for (tt, loud), view in zip(ms[:, [1, 5]], rs[:, 4]):
                x = ox + 40 + 560 * (float(loud) - lo) / max(1e-6, hi - lo)
                y = 500 - 470 * float(view) / vmax
                f = float(tt) / t_max
                sd.point((x, y), fill=(int(60 + 195 * f), int(90 + 150 * f), int(255 - 200 * f)))
        scatter.save(out / f"song{song}_scatter.png")
        # Metrics on 1 s means.
        step = max(1, int(round(1.0 / max(1e-3, float(np.median(np.diff(ms[:, 1])))))))
        loud_1s = ms[: len(ms) // step * step, 5].reshape(-1, step).mean(axis=1)
        # The pipeline's loudness and the PCM's own envelope can disagree (6 Nov: a bass entry raised RMS and bass
        # by tens of dB while the 3-17 loudness barely moved), so correlate against all three.
        rms_1s = ms[: len(ms) // step * step, 2].reshape(-1, step).mean(axis=1)
        bass_1s = ms[: len(ms) // step * step, 3].reshape(-1, step).mean(axis=1)

        def correlation(a, b):
            return float(np.corrcoef(a, b)[0, 1]) if len(a) > 3 and np.ptp(a) and np.ptp(b) else float("nan")
        for (name, rs), column in [(item, column) for item in joined.items()
                                   for column in ((4, 12) if item[1].shape[1] > 12 else (4,))]:
            view_1s = rs[: len(rs) // step * step, column].reshape(-1, step).mean(axis=1)
            name = name if column == 4 else name + ":born"
            corr = correlation(loud_1s, view_1s)
            corr_rms, corr_bass = correlation(rms_1s, view_1s), correlation(bass_1s, view_1s)
            loud_range = np.ptp(loud_1s) or 1.0
            view_range = np.ptp(view_1s) or 1.0
            d_loud = np.abs(np.diff(loud_1s)) / loud_range
            d_view = np.abs(np.diff(view_1s)) / view_range
            saturated = float(np.mean(view_1s >= np.max(view_1s) - .05 * view_range))
            dead = float(np.mean((d_loud > .15) & (d_view < .03))) if len(d_loud) else 0.0
            spurious = float(np.mean((d_loud < .03) & (d_view > .15))) if len(d_loud) else 0.0
            half = len(loud_1s) // 2
            bins = np.linspace(loud_1s.min(), loud_1s.max(), 6)
            gaps = []
            for a, b in zip(bins[:-1], bins[1:]):
                early = view_1s[:half][(loud_1s[:half] >= a) & (loud_1s[:half] < b)]
                late = view_1s[half:][(loud_1s[half:] >= a) & (loud_1s[half:] < b)]
                if len(early) >= 2 and len(late) >= 2:
                    gaps.append(abs(float(late.mean() - early.mean())) / view_range)
            rescale = max(gaps) if gaps else float("nan")
            lines.append(f"song {song} {name:10s} corr(view; loudness {corr:+.2f} rms {corr_rms:+.2f} bass {corr_bass:+.2f})"
                         f" [music 1 s p5-p95: rms {np.subtract(*np.percentile(rms_1s, [95, 5])):.1f} dB,"
                         f" bass {np.subtract(*np.percentile(bass_1s, [95, 5])):.1f} dB; a flat song"
                         f" makes the correlations noise: judge its beats in the trace]"
                         f"  saturated {saturated:5.1%}"
                         f"  dead {dead:5.1%}  spurious {spurious:5.1%}  re-scale gap {rescale:.2f}"
                         f"  view range {np.ptp(view_1s):.2f}")
    (out / "music_vs_response.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("music")
    p.add_argument("--clips", required=True)
    p.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    p = sub.add_parser("response")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--presets", default="1,4,7")
    p.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    p.add_argument("--mode", help="override the presets' Reaction Mode")
    p.add_argument("--direction", help="override the presets' Pulse Direction")
    p.add_argument("--breathing", type=float, help="override the presets' Breathing")
    p = sub.add_parser("report")
    p.add_argument("--music", type=Path, required=True)
    p.add_argument("--response", action="append", required=True, help="name=path.npy")
    p.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    args = parser.parse_args()
    evidence_media.redirect_output(args, "out", "waveform_music_response")
    if args.command == "music":
        music([Path(c) for c in args.clips.split(",")], args.out)
    elif args.command == "response":
        response(args.root, args.inputs, [int(p) for p in args.presets.split(",")], args.out, args.mode, args.direction,
                 args.breathing)
    else:
        report(args.music, dict(item.split("=", 1) for item in args.response), args.out)


if __name__ == "__main__":
    main()
    evidence_media.finish(0)

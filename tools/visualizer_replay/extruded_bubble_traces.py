"""Extruded Bubble's reactivity on real music: drive its own simulation with recordings through the production
BeatEngine replay seam and plot every reactive signal over time (intensity, stream speed, drift, emission,
sustain, mid-bubble pulse, large-bubble swell, population; kicks as faint lines). For checking quick attack / slow decay, sustained loud
passages and stutter-free motion (Extruded_Bubble_Target.md section 8).

    python -m tools.visualizer_replay.extruded_bubble_traces OUT.png ragdoll_quiet_intro_loud_end1 1985_loud1

Clip names are recordings in logs/visualizer_recordings. It also prints the largest frame-to-frame stream-speed step.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from tools.visualizer_replay.engine import ReplayBeatEngine
from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime, passage_intensity_from_body_bands
from widgets.spotify_visualizer.extruded_bubble_simulation import BUBBLE_STRIDE, ExtrudedBubbleControls, WORLD_UNIT
from widgets.spotify_visualizer.feature_frame import FeatureClip

ROOT = Path(__file__).resolve().parents[2] / "logs" / "visualizer_recordings"
out, names = sys.argv[1], sys.argv[2:] or ['ragdoll_quiet_intro_loud_end1', 'cindarellaman_heavy2']
W, PANEL = 1600, 300
sheet = Image.new("RGB", (W, PANEL * len(names)), (18, 18, 20))
draw = ImageDraw.Draw(sheet)
controls = ExtrudedBubbleControls()
for row, name in enumerate(names):
    clip = FeatureClip.from_jsonl_bytes(name, (ROOT / f"{name}.jsonl").read_bytes())
    engine = ReplayBeatEngine(32)
    runtime = ExtrudedBubbleFrameRuntime(1)
    series = {k: [] for k in ("t", "intensity", "level", "sustain", "speed", "drift", "emission", "mids", "large", "count")}
    kicks = []
    t0 = None
    for frame in clip.frames:
        engine.accept_feature_frame(frame)
        now = frame.timestamp_us / 1e6
        t0 = now if t0 is None else t0
        onsets = engine.get_onset_events(runtime.onset_serial)
        kicks += [now - t0 for o in onsets if o.kind == "kick"]
        bands = engine.get_extruded_bubble_body_bands()
        body_bands = (bands.bass, bands.mid, bands.high)
        snap = runtime.advance(onsets=onsets, now_ts=now, playing=bool(frame.playing),
                               identity=(1, 1, 1), source_identity=(1, 1), body_bands=body_bands,
                               controls=controls)
        records = [snap.bubbles[i:i + BUBBLE_STRIDE] for i in range(0, len(snap.bubbles), BUBBLE_STRIDE)]
        kinds = {b.ident: b.large for b in runtime._simulation._bubbles}
        mids = [r[5] for r in records if not kinds[int(r[6])] and r[4] > 0.9]
        series["t"].append(now - t0)
        series["intensity"].append(passage_intensity_from_body_bands(body_bands))
        series["level"].append(snap.level)
        series["sustain"].append(snap.sustain)
        series["speed"].append(snap.stream_speed / (WORLD_UNIT * controls.stream_speed[1]))
        series["drift"].append(snap.drift)
        series["emission"].append(snap.emission)
        series["mids"].append(sum(mids) / len(mids) if mids else 0.0)
        large = [r[5] for r in records if kinds[int(r[6])] and r[4] > 0.9]
        series["large"].append(sum(large) / len(large) if large else 0.0)
        series["count"].append(snap.count / 70.0)
    t = series["t"]
    top = row * PANEL
    span = max(t) or 1.0
    def xy(ts, v):
        return 40 + (W - 60) * ts / span, top + PANEL - 25 - (PANEL - 50) * (max(-1.0, min(3.0, v)) + 1.0) / 4.0
    for k in kicks:
        x, _ = xy(k, 0)
        draw.line([(x, top + 20), (x, top + PANEL - 25)], fill=(30, 45, 70))
    colours = {"intensity": (150, 150, 150), "speed": (232, 85, 76), "drift": (76, 232, 122),
               "emission": (232, 193, 76), "sustain": (176, 76, 232), "mids": (76, 232, 224), "large": (255, 255, 255), "count": (110, 110, 110)}
    for key, colour in colours.items():
        draw.line([xy(a, b) for a, b in zip(t, series[key])], fill=colour, width=2 if key in ("speed", "sustain", "large") else 1)
    draw.text((45, top + 4), f"{name}  ({len(kicks)} kicks, {span:.0f} s)", fill=(220, 220, 220))
    for n, (key, colour) in enumerate(colours.items()):
        draw.text((600 + 100 * n, top + 4), key, fill=colour)
    steps = [abs(b - a) for a, b in zip(series["speed"], series["speed"][1:])]
    print(name, "max speed step (share of loud speed):", round(max(steps), 4),
          "mean sustain:", round(sum(series["sustain"]) / len(t), 3))
sheet.save(out)
print("saved", out)

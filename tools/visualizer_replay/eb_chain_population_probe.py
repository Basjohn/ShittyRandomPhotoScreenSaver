"""Extruded Bubble free-chain population per tick over a recorded clip: whole fades and blinks per chain.

    .venv/Scripts/python tools/visualizer_replay/eb_chain_population_probe.py anything_mixed2 1 40 out.json

Arguments: clip name under logs/visualizer_recordings, curated preset (1-based), seconds, trace output. Replays the
production logical tick (``replay_clip``) at High detail, sizes each chain's population opacity with the renderer's
``_procedural_fill`` / ``chain_drive`` and ``chain_opacity`` and reports the shortest 90%->10% fades and chains that
leave and return within 2 s (the 2026-10-31 blink). Offscreen, no window, no GL; presets are read, never written.
"""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dataclasses import replace


def bead_hash(x):
    x &= 0xffffffff
    x ^= x >> 16; x = (x * 0x7feb352d) & 0xffffffff; x ^= x >> 15; x = (x * 0x846ca68b) & 0xffffffff; x ^= x >> 16
    return x


def bead_random(index, salt):
    return float(bead_hash(((index * 0x9e3779b9) & 0xffffffff) ^ ((salt * 0x85ebca6b) & 0xffffffff)) & 0xffffff) / 16777215.0


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def main():
    clip_name = sys.argv[1] if len(sys.argv) > 1 else "anything_mixed2"
    preset = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools.visualizer_replay.driver import replay_clip
    from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    mode = "extruded_bubble"
    activation = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": preset - 1}, mode=mode)
    settings = dict(activation.resolved_config)
    frames = []
    with (ROOT / "logs/visualizer_recordings" / f"{clip_name}.jsonl").open(encoding="utf-8") as s:
        for line in s:
            f = FeatureFrame.from_dict(json.loads(line))
            if frames and (f.timestamp_us - frames[0].timestamp_us) / 1e6 > duration:
                break
            frames.append(f)
    result = replay_clip(FeatureClip("probe", tuple(frames)), mode, settings=settings)
    keys = ("extruded_bubble_bead_chains", "scene3d_detail", "extruded_bubble_emission_geometry",
            "extruded_bubble_bead_scatter")
    print(activation.preset_path, {k: settings.get(k) for k in keys})
    params = {**settings, "scene3d_detail": "High"}
    rows = []
    for frame, logical in zip(frames, result["logical_series"]):
        st = logical.mode_state
        t = (frame.timestamp_us - frames[0].timestamp_us) / 1e6
        fill, _, _ = eb._procedural_fill(params, eb.chain_drive(st), st.emission)
        travel = eb._BEAD_CLIMB * float(st.travel)
        rows.append((t, float(st.passage), float(st.level), float(st.chain_activity), fill, travel))
    out = []
    nchains = math.ceil(max(r[4] for r in rows))
    for t, passage, level, act, fill, travel in rows:
        per = []
        for c in range(nchains):
            try:
                from widgets.spotify_visualizer.extruded_bubble_material_paths import chain_opacity
                fillf = chain_opacity(fill, c)
            except ImportError:
                fillf = min(1.0, max(0.0, fill - c))
            life = (travel * 0.035 + bead_random(c, 24)) % 1.0
            lf = smooth(0.0, 0.18, life) * (1 - smooth(0.82, 1.0, life))
            per.append((fillf, lf))
        out.append({"t": t, "passage": passage, "level": level, "activity": act, "fill": fill, "travel": travel,
                    "fill_f": [p[0] for p in per], "life_f": [p[1] for p in per]})
    dest = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("chain_trace.json")
    dest.write_text(json.dumps(out))
    # summary
    fills = [r[4] for r in rows]
    trav = [r[5] for r in rows]
    print("ticks", len(rows), "fill min/max", min(fills), max(fills), "travel rate /s",
          (trav[-1] - trav[0]) / (rows[-1][0] - rows[0][0]), "chains", nchains)
    fades=[];blinks=[]
    for c in range(nchains):
        state=None;start=None;last_off=None
        for o in out:
            v=o["fill_f"][c]; tt=o["t"]
            s=1 if v>0.9 else (0 if v<0.1 else None)
            if s is None and start is None and state is not None: start=tt
            if s is not None:
                if state is not None and s!=state:
                    fades.append(round(tt-start,3))
                    if s==0: last_off=tt
                    elif last_off is not None and tt-last_off<2.0: blinks.append((c,round(last_off,2),round(tt,2)))
                start=None;state=s
    fades.sort()
    print("SUMMARY full fades", len(fades), "shortest", fades[:5], "blinks(off->on<2s)", len(blinks), blinks[:8])


main()

"""Build the Visualizer Studios' shipped audio clips (``assets/production/studio_clips``) from native recordings.

    .venv/Scripts/python tools/build_studio_clips.py [--recordings DIR] [--check]

Each clip is a short window of a 60 s native-PCM recording in ``logs/visualizer_recordings`` (which never
ships), written in the compact form (``widgets/spotify_visualizer/compact_clip.py``: de-duplicated int16
PCM + exact per-frame lanes, xz). Windows are seconds from the recording's first frame and include a
lead-in, so the Waveform replay is primed before the passage the clip is for. ``clips.json`` records
provenance: source file and its sha256, the window, the sha256 of the window's canonical JSONL frames
and of the written clip. ``--check`` rebuilds in memory and fails if a committed clip differs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "assets" / "production" / "studio_clips"
MANIFEST = "clips.json"

# (id, Studio label, recording, start s, end s, what the window is for). Chosen from each recording's
# 2 s musical-level profile: each window crosses a quiet-to-hot change, the span the Studio's
# Quiet / Mid / Peak references stand for, with ~2 s of lead-in before it.
CLIPS = (
    ("rag_doll", "Rag Doll", "ragdoll_quiet_intro_loud_end1.jsonl", 36.0, 48.0,
     "a mid verse dipping (38-40 s) before the loud end (42 s on)"),
    ("human", "Human", "human_heavy1.jsonl", 22.0, 34.0,
     "a heavy track's quiet break (22-26 s) into its hottest stretch (26-32 s)"),
    ("growing_pains", "Growing Pains", "growingpains_triplehitbeat.jsonl", 6.0, 18.0,
     "the soft intro (6-8 s) building through the triple-hit beat into the hot groove (14 s on)"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def window_frames(path: Path, start: float, end: float):
    """The recording's frames with ``start <= t <= end`` seconds after its first frame (parsed lazily)."""
    from widgets.spotify_visualizer.feature_frame import FeatureFrame
    frames, origin = [], None
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            # Keys are sorted, so the timestamp sits after the (large) capture history, near the line's end.
            found = re.search(r'"timestamp_us":(\d+)', line[-8192:])
            timestamp = int(found.group(1)) if found else json.loads(line)["timestamp_us"]
            if origin is None:
                origin = timestamp
            t = (timestamp - origin) / 1e6
            if t < start:
                continue
            if t > end:
                break
            frames.append(FeatureFrame.from_dict(json.loads(line)))
    if not frames:
        raise ValueError(f"{path.name}: no frames in {start}-{end} s")
    return tuple(frames)


def verify(source, decoded) -> dict:
    """Every lane equal; PCM within int16 quantisation; the preview is the only rebuilt field."""
    import numpy as np
    from widgets.spotify_visualizer.compact_clip import PCM_SCALE
    assert len(source) == len(decoded)
    worst = 0.0
    for a, b in zip(source, decoded):
        assert replace(a, waveform=b.waveform, capture_history=None) == replace(b, capture_history=None)
        ha, hb = a.capture_history, b.capture_history
        assert (ha.capture_serial, ha.sample_rate, ha.sample_count) == (hb.capture_serial, hb.sample_rate,
                                                                         hb.sample_count)
        error = np.max(np.abs(np.frombuffer(ha.pcm_f32le, "<f4").astype(np.float64)
                              - np.frombuffer(hb.pcm_f32le, "<f4").astype(np.float64)))
        worst = max(worst, float(error))
    assert worst <= .5 / PCM_SCALE + 1e-9, worst
    return {"max_pcm_error": worst}


def build(recordings: Path, *, check: bool = False) -> list[dict]:
    from widgets.spotify_visualizer.compact_clip import SUFFIX, decode, encode
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    entries = []
    for clip_id, label, source_name, start, end, purpose in CLIPS:
        source = recordings / source_name
        frames = window_frames(source, start, end)
        window_sha = FeatureClip(name=clip_id, frames=frames).sha256()
        provenance = {"source": source_name, "source_sha256": sha256_file(source), "window_s": [start, end],
                      "window_sha256": window_sha, "purpose": purpose,
                      "builder": "tools/build_studio_clips.py"}
        data = encode(frames, name=clip_id, provenance=provenance)
        stats = verify(frames, decode(data).frames)
        target = OUTPUT / (clip_id + SUFFIX)
        if check:
            if not target.is_file() or target.read_bytes() != data:
                raise SystemExit(f"{target.name} differs from a rebuild")
        else:
            OUTPUT.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        entries.append({"id": clip_id, "label": label, "file": target.name, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "frames": len(frames),
                        "seconds": round((frames[-1].timestamp_us - frames[0].timestamp_us) / 1e6, 3),
                        **provenance, **stats})
        print(f"{target.name}: {len(data) / 1e6:.3f} MB, {len(frames)} frames, {start}-{end} s of {source_name}")
    manifest = OUTPUT / MANIFEST
    text = json.dumps({"clips": entries}, indent=1) + "\n"
    if check:
        if not manifest.is_file() or manifest.read_text(encoding="utf-8") != text:
            raise SystemExit(f"{MANIFEST} differs from a rebuild")
    else:
        manifest.write_text(text, encoding="utf-8")
    return entries


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recordings", type=Path, default=ROOT / "logs" / "visualizer_recordings")
    parser.add_argument("--check", action="store_true", help="Rebuild in memory; fail if a committed clip differs")
    args = parser.parse_args(argv)
    build(args.recordings, check=args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

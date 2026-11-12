"""Native core N2.3: Spectrum's native frame schema on real frames, through a real native frame stream.

Replays a shipped Studio clip through the production owner on Spectrum (no window, no cadence thread), then publishes
every logical frame the owner handed its renderer through an in-process ``PacketMailbox(payload="native")`` loopback
(the worker's native encoder, the slot's ``payload_schema`` stamp, the reader's head check and the pure-Python
reference decoder) and compares each decoded record with the same fields taken from the tagged codec's decode, bit
for bit. Writes the record's layout table (the C++ reader's reference) and a summary to
``.artifacts/evidence/visualizers/spectrum/native_schema/<date>_<label>/``. Nothing in the product makes a native
stream; this harness and ``tests/test_visualizer_engine_native_schema.py`` are the encoder's only callers.

    python tools/native_schema_check.py [--seconds 1.5] [--clip growing_pains] [--label check]
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def run(seconds: float, clip_name: str) -> dict:
    from PySide6.QtWidgets import QApplication

    import tools.expanded_visualizer_evidence as evidence
    from core.visualizer_engine import frame_codec
    from core.visualizer_engine import spectrum_native_schema as spectrum
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge

    QApplication.instance() or QApplication([])
    frames = []
    publish = VisualizerSnapshotBridge.publish

    def recording(self, snapshot):
        frames.append(snapshot.logical)
        return publish(self, snapshot)

    VisualizerSnapshotBridge.publish = recording
    try:
        evidence.owner_replay(evidence.shipped_clip(seconds, clip_name), "spectrum")
    finally:
        VisualizerSnapshotBridge.publish = publish
    frames = [frame for frame in frames if frame.mode_id == "spectrum"]
    mailbox = PacketMailbox(slot_bytes=64 * 1024, payload="native")
    mismatches = []
    try:
        for index, frame in enumerate(frames):
            mailbox.publish(frame, generation=frame.runtime_generation, activation_id=frame.activation_id)
            taken = mailbox.take()
            tagged = frame_codec.decode(frame_codec.encode((1, 1, 0.0, frame)))[3]
            if taken is None or repr(taken.state) != repr(spectrum.project(tagged)):
                mismatches.append(index)
        refused = mailbox.refused_payloads
    finally:
        mailbox.close()
    return {
        "clip": clip_name, "seconds": seconds, "frames": len(frames), "mismatches": mismatches,
        "refused": refused, "schema_id": hex(spectrum.SCHEMA_ID), "version": spectrum.VERSION,
        "record_bytes": spectrum.LAYOUT.size, "fingerprint": spectrum.LAYOUT.fingerprint(),
        "layout_table": spectrum.LAYOUT.table(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--seconds", type=float, default=1.5, help="how much of the clip to replay")
    parser.add_argument("--clip", default="growing_pains", help="a shipped Studio clip's name")
    parser.add_argument("--label", default="check", help="the evidence folder's label")
    args = parser.parse_args(argv)
    sys.path.insert(0, os.path.abspath(args.repo))
    from tools.artifact_paths import evidence_dir, repository_root

    repository_root(args.repo)
    result = run(args.seconds, args.clip)
    out = evidence_dir("visualizers/spectrum", "native_schema", args.label)
    out.mkdir(parents=True, exist_ok=True)
    (out / "layout.md").write_text(f"# Spectrum native record, schema {result['schema_id']} (version "
                                   f"{result['version']}, {result['record_bytes']} bytes, fingerprint "
                                   f"{result['fingerprint']})\n\n{result['layout_table']}\n", encoding="utf-8")
    summary = {key: value for key, value in result.items() if key != "layout_table"}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"evidence: {out}")
    return 0 if result["frames"] and not result["mismatches"] and not result["refused"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

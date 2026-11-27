"""Guard output lean (operator, 22 Nov): the native guard keeps hashes per frame and images only for failing frames,
never a lossless full-take frame store (Bubble's guard wrote 26 GB). ``native_stream_player`` runs its two children
through ``subprocess.run`` here replaced by a stand-in that draws synthetic frames where the command says to."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from tests.test_native_stream_player import _base, _save


def _fake_children(tmp_path, monkeypatch, frames_for):
    """``subprocess.run`` replaced: the child's command names its frame folder (``--frames-dir``; the old command did
    not, and the stand-in then writes beside the index, as the old child did)."""
    def run(command, **_kwargs):
        def option(name):
            return command[command.index(name) + 1] if name in command else None
        api, out = option("--api"), Path(option("--out-dir"))
        frames = option("--frames-dir")
        frames_dir = None if frames is None else Path(frames)
        _save(out, api, frames_for[api], frames_dir)
        Path(option("--child-json")).write_text(json.dumps({"api": api, "drawn": 3, "seconds": 0.0}),
                                                        encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", run)


def _deliveries(folder):
    folder.mkdir(parents=True, exist_ok=True)
    lines = [{"mode": "bubble"}] + [{"input": i, "drawn": True} for i in range(4)]
    (folder / "deliveries.jsonl").write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")


def test_the_guard_keeps_hashes_and_only_failing_frames_images(tmp_path, monkeypatch):
    from tools import artifact_paths
    from tools.visualizer_replay import native_stream_player as player

    base = _base()
    block = base.copy()
    block[10:18, 10:18, 1] += 1                  # a compact one-level block: rule (b) fails this frame
    scattered = base.copy()
    scattered[5, 5, 0] += 1                      # a lone one-level pixel: rule (b) passes it
    frames = {"opengl": [base, base, base, base], "vulkan": [base, scattered, block, base]}
    _fake_children(tmp_path, monkeypatch, frames)
    _deliveries(tmp_path / "deliveries")
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        out = root / "scratch" / "guard_out"
        code = player.main(["--deliveries", str(tmp_path / "deliveries"), "--out", str(out), "--switch-input", "4"])
        assert code == 1                                         # the failing frame fails the run
        report = json.loads((out / player.REPORT_NAME).read_text(encoding="utf-8"))
        assert [len(h) for h in report["hashes"].values()] == [4, 4]            # a hash per frame, each API
        assert [f["input"] for f in report["rule_b"]["failed_frames"]] == [2]
        kept = sorted(path.relative_to(out).as_posix() for path in out.rglob("*.png"))
        assert kept and all(name.startswith("failing_frames/input2_") for name in kept)   # only input 2's images
        # No frame store anywhere: not in the evidence, and the scratch it was drawn in is gone.
        assert not list(out.rglob("frames_*.bin"))
        assert not (root / "scratch" / "native_stream_player").exists()


def test_a_passing_run_publishes_no_images_and_no_frames(tmp_path, monkeypatch):
    from tools import artifact_paths
    from tools.visualizer_replay import native_stream_player as player

    base = _base()
    _fake_children(tmp_path, monkeypatch, {"opengl": [base] * 4, "vulkan": [base] * 4})
    _deliveries(tmp_path / "deliveries")
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        out = root / "scratch" / "guard_out"
        assert player.main(["--deliveries", str(tmp_path / "deliveries"), "--out", str(out)]) == 0
        assert not list(out.rglob("*.png")) and not list(out.rglob("*.bin"))


def test_failing_images_are_capped_but_every_failure_is_recorded(tmp_path):
    from tools.visualizer_replay import native_stream_player as player

    base = _base()
    count = player.MAX_FAILING_IMAGES + 3
    blocks = []
    for _ in range(count):
        block = base.copy()
        block[10:18, 10:18, 1] += 1
        blocks.append(block)
    frames_dir = tmp_path / "scratch_frames"
    _save(tmp_path, "opengl", [base] * count, frames_dir)
    _save(tmp_path, "vulkan", blocks, frames_dir)
    result = player.rule_b(tmp_path, "bubble", switch_input=None, frames_dir=frames_dir,
                           images_dir=tmp_path / "images")
    assert len(result["failed_frames"]) == count
    assert len(list((tmp_path / "images").glob("*_difference_x64.png"))) == player.MAX_FAILING_IMAGES


def test_a_hash_only_run_stores_no_frames():
    from tools.visualizer_replay import owner_render_parity as parity

    store = parity._LastFrame()
    for index in range(5):
        store.append(((1,), bytes([index])))
    assert len(store) == 5 and store[4] == ((1,), bytes([4]))
    try:
        store[3]
    except IndexError:
        pass
    else:
        raise AssertionError("an earlier frame must not be kept")
    assert sys.getsizeof(store) < 1000

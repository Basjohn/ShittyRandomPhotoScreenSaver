"""The native-only player's judging (``tools/visualizer_replay/native_stream_player.py``, fast-proof part 2 step 4b), on
synthetic saved frames: rule (b) passes Bubble's scatter and fails a compact block (control) and a frame drawn on one API
only (control); the baseline compare lists every changed frame. Bounds come from the harness's own tolerance."""
from __future__ import annotations

import hashlib
import json
import zlib

import numpy as np


def _save(out, api, frames, frames_dir=None):
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    frames_dir = work if frames_dir is None else frames_dir
    frames_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with (frames_dir / f"frames_{api}.bin").open("wb") as stream:
        for index, frame in enumerate(frames):
            if frame is None:
                rows.append({"input": index, "drawn": False})
                continue
            data = zlib.compress(frame.tobytes(), 1)
            rows.append({"input": index, "drawn": True, "hash": hashlib.sha256(frame.tobytes()).hexdigest(),
                         "offset": stream.tell(), "size": len(data), "shape": list(frame.shape)})
            stream.write(data)
    (work / f"index_{api}.json").write_text(json.dumps(rows), encoding="utf-8")


def _base():
    frame = np.full((40, 60, 4), 80, np.uint8)
    frame[..., 3] = 255
    return frame


def test_rule_b_judges_every_frame_and_its_controls_fail(tmp_path):
    from tools.visualizer_replay import native_stream_player as player

    base = _base()
    scattered = base.copy()
    scattered[5, 5, 0] += 1
    scattered[20, 40, 1] += 1
    gl = [base, base, base, None]
    _save(tmp_path, "opengl", gl)
    _save(tmp_path, "vulkan", [base, scattered, base, None])
    result = player.rule_b(tmp_path, "bubble", switch_input=4)
    assert result["pass"] and result["compared"] == 3 and result["judged"] == 1 and result["hash_equal"] == 2
    # Controls: a compact one-level block; a frame drawn on one API only.
    block = base.copy()
    block[10:18, 10:18, 1] += 1
    _save(tmp_path, "vulkan", [base, block, base, None])
    failed = player.rule_b(tmp_path, "bubble", switch_input=4)
    assert not failed["pass"] and [f["input"] for f in failed["failed_frames"]] == [1]
    _save(tmp_path, "vulkan", [base, base, base, base])
    assert not player.rule_b(tmp_path, "bubble", switch_input=4)["pass"]


def test_the_oscilloscope_program_follows_the_glow_of_the_delivered_settings():
    # The player draws the program the route built: the Oscilloscope's Glow chooses it (Glow 0: the plain program and
    # translucency alone as rule (b)'s class), read from the take's first delivered settings.
    from tools.visualizer_replay import native_stream_player as player

    module, _base_module = player._harness("oscilloscope")
    saved = dict(module.GLOW_OFF)
    try:
        player._configure(module, [{"input": 0, "drawn": False}, {"input": 1, "drawn": True,
                                                                     "settings": {"uGlow": 1.0}}])
        assert module.GLOW_OFF["on"] and module.peer_frame_mask(_base()) is None
        player._configure(module, [{"input": 0, "drawn": True, "settings": {"uGlow": 1.0, "u_hdr_exposure": 0.0}}])
        assert not module.GLOW_OFF["on"] and module.peer_frame_mask(_base()).all()
    finally:
        module.GLOW_OFF.update(saved)


def test_against_lists_every_changed_frame(tmp_path):
    from tools.visualizer_replay import native_stream_player as player

    base = _base()
    other = base.copy()
    other[0, 0, 0] += 1
    _save(tmp_path, "opengl", [base, base, base])
    hashes = [hashlib.sha256(base.tobytes()).hexdigest()] * 3
    assert player.against(tmp_path, "opengl", {"hashes": {"opengl": hashes}})["identical"]
    _save(tmp_path, "opengl", [base, other, other])
    entry = player.against(tmp_path, "opengl", {"hashes": {"opengl": hashes}})
    assert entry["changed"] == [1, 2] and not entry["identical"]
    assert not player.against(tmp_path, "vulkan", {"hashes": {"opengl": hashes}})["compared"]

"""Evidence media: a KEPT frame sequence becomes one animated 24 fps WebP under 10 MB (a deliberate step);
tool output is published unchanged (PNG stills and frames alike: compare tools read them).

Operator, 7 Nov 2026: raw PNG frame folders filled ``.artifacts/evidence``, but "PNGs are not barred from the
project, only single frames when used to show full motion instead of a webp". A tool's scratch is deleted when it
succeeds and kept (for debugging) when it fails.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from tools import artifact_paths, evidence_media  # noqa: E402


@pytest.fixture
def scratch_root(tmp_path):
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        yield root / "scratch"


def _noisy_frame(index: int, size=(640, 360)) -> Image.Image:
    # Noise defeats compression, so the byte cap has to step the size down.
    return Image.effect_noise(size, 90 + index).convert("RGB")


def _durations(path):
    with Image.open(path) as encoded:
        assert encoded.format == "WEBP" and encoded.is_animated
        durations = []
        for frame in range(encoded.n_frames):
            encoded.seek(frame)
            encoded.load()
            durations.append(encoded.info["duration"])
        return durations, encoded.size


def test_a_frame_sequence_becomes_one_animated_24fps_webp_under_the_cap(tmp_path):
    frames = [_noisy_frame(index) for index in range(12)]
    out = tmp_path / "evidence.webp"
    cap = 150_000
    receipt = evidence_media.animated_webp(frames, out, max_bytes=cap)
    assert out.stat().st_size <= cap
    durations, size = _durations(out)
    assert len(durations) == 12
    assert sum(durations) / len(durations) == pytest.approx(1000 / 24, abs=0.6)
    assert max(size) < 640, "the evidence was not reduced in size"
    assert receipt["fps"] == 24 and receipt["bytes"] <= cap


def test_a_tool_run_publishes_every_output_unchanged_and_deletes_its_scratch(tmp_path, scratch_root):
    """Operator, 7 Nov: PNGs are not barred (compare tools read them); publishing never converts anything."""
    out = tmp_path / "evidence"
    args = SimpleNamespace(output=out)
    work = evidence_media.redirect_output(args, "output", "unit")
    assert args.output == work and artifact_paths.in_scratch(work)
    work.mkdir(parents=True)
    frames = []
    for index in range(14):
        frame = work / f"spin_{index:03d}.png"
        _noisy_frame(index, (48, 32)).save(frame)
        frames.append(frame.read_bytes())
    _noisy_frame(99, (96, 64)).save(work / "card.png")
    card = (work / "card.png").read_bytes()
    (work / "manifest.json").write_text(json.dumps({"still": str(work / "card.png"), "first": "spin_000.png"}))

    assert evidence_media.finish(0) == 0
    assert not any(scratch_root.rglob("*")), "scratch outlived a successful run"
    names = sorted(path.name for path in out.iterdir())
    assert names == sorted(["card.png", "manifest.json", *(f"spin_{index:03d}.png" for index in range(14))])
    assert (out / "card.png").read_bytes() == card, "a still was re-encoded"
    assert [(out / f"spin_{index:03d}.png").read_bytes() for index in range(14)] == frames
    assert json.loads((out / "manifest.json").read_text()) == {"still": str(out / "card.png"),
                                                               "first": "spin_000.png"}
    assert not list(out.rglob("*.webp")), "publishing converted output to WebP"


def test_a_failed_tool_run_keeps_its_scratch_for_debugging(tmp_path, scratch_root, capsys):
    args = SimpleNamespace(output=tmp_path / "evidence")
    work = evidence_media.redirect_output(args, "output", "unit")
    work.mkdir(parents=True)
    _noisy_frame(0, (32, 32)).save(work / "frame.png")
    assert evidence_media.finish(1) == 1
    assert (work / "frame.png").exists()
    assert str(work.parent) in capsys.readouterr().err
    assert not (tmp_path / "evidence").exists()


def test_animated_webp_refuses_a_non_webp_destination(tmp_path):
    with pytest.raises(ValueError):
        evidence_media.animated_webp([_noisy_frame(0, (32, 32)), _noisy_frame(1, (32, 32))], tmp_path / "out.png")

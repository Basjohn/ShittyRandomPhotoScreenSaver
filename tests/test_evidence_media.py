"""Durable visual evidence is one small animated WebP at 24 fps; its PNG frames never outlive the encode.

Operator, 7 Nov 2026: "agents have littered". Raw PNG frame folders filled ``.artifacts/evidence``; the rule
(Docs/Guardrails.md "Evidence and scratch hygiene") keeps PNGs only while frames are examined.
"""
from __future__ import annotations

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from tools import artifact_paths, evidence_media  # noqa: E402


@pytest.fixture
def scratch_root(tmp_path, monkeypatch):
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        yield root / "scratch"


def _noisy_frame(index: int, size=(640, 360)) -> Image.Image:
    # Noise defeats compression, so the byte cap has to step the size down.
    noise = Image.effect_noise(size, 90 + index).convert("RGB")
    return noise


def test_a_frame_sequence_becomes_one_animated_24fps_webp_under_the_cap_and_its_pngs_go(
    tmp_path, scratch_root,
):
    out = tmp_path / "evidence.webp"
    cap = 150_000
    with evidence_media.frame_sequence("unit", out, max_bytes=cap) as sequence:
        folder = sequence.folder
        for index in range(12):
            _noisy_frame(index).save(sequence.next_path())
        assert len(list(folder.glob("*.png"))) == 12

    assert not folder.exists(), "the temporary PNG frames outlived the encode"
    assert out.stat().st_size <= cap
    with Image.open(out) as encoded:
        assert encoded.format == "WEBP"
        assert encoded.is_animated and encoded.n_frames == 12
        durations = []
        for frame in range(encoded.n_frames):
            encoded.seek(frame)
            encoded.load()
            durations.append(encoded.info["duration"])
        assert max(encoded.size) < 640, "the evidence was not reduced in size"
    assert sum(durations) / len(durations) == pytest.approx(1000 / 24, abs=0.6)
    assert sequence.receipt["fps"] == 24 and sequence.receipt["bytes"] <= cap


def test_frames_are_deleted_when_the_capture_fails(tmp_path, scratch_root):
    out = tmp_path / "never.webp"
    with pytest.raises(RuntimeError):
        with evidence_media.frame_sequence("unit", out) as sequence:
            folder = sequence.folder
            _noisy_frame(0, (64, 64)).save(sequence.next_path())
            raise RuntimeError("capture failed")
    assert not folder.exists()
    assert not out.exists()


def test_a_still_becomes_a_reduced_still_webp_and_its_png_is_deleted(tmp_path):
    png = tmp_path / "still.png"
    _noisy_frame(0, (3000, 1000)).save(png)
    out = tmp_path / "still.webp"
    receipt = evidence_media.still_from_png(png, out)
    assert not png.exists()
    with Image.open(out) as encoded:
        assert encoded.format == "WEBP"
        assert not getattr(encoded, "is_animated", False)
        assert max(encoded.size) == evidence_media.STILL_MAX_SIDE
    assert receipt["bytes"] == out.stat().st_size


def test_evidence_media_refuses_png_destinations(tmp_path):
    with pytest.raises(ValueError):
        evidence_media.still_webp(_noisy_frame(0, (32, 32)), tmp_path / "out.png")

"""Durable visual evidence is small WebP: a sequence is one animated 24 fps WebP under 10 MB; PNGs are scratch.

Operator, 7 Nov 2026: "agents have littered". Raw PNG frame folders filled ``.artifacts/evidence``; the rule
(Docs/Guardrails.md "Evidence and scratch hygiene") keeps PNGs only while frames are examined. A tool's
scratch is deleted when it succeeds and kept (for debugging) when it fails.
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


def test_a_tool_run_publishes_webp_relinks_its_summary_and_deletes_its_pngs(tmp_path, scratch_root):
    out = tmp_path / "evidence"
    args = SimpleNamespace(output=out)
    work = evidence_media.redirect_output(args, "output", "unit")
    assert args.output == work and artifact_paths.in_scratch(work)
    work.mkdir(parents=True)
    for index in range(3):
        _noisy_frame(index, (96, 64)).save(work / f"spin_{index:03d}.png")
    _noisy_frame(9, (96, 64)).save(work / "card.png")
    (work / "manifest.json").write_text(json.dumps({"still": str(work / "card.png"), "first": "spin_000.png"}))

    assert evidence_media.finish(0) == 0
    assert not any(scratch_root.rglob("*.png")), "PNGs outlived a successful run"
    assert sorted(path.name for path in out.iterdir()) == ["card.webp", "manifest.json", "spin.webp"]
    durations, _size = _durations(out / "spin.webp")
    assert len(durations) == 3
    assert json.loads((out / "manifest.json").read_text()) == {"still": str(out / "card.webp"),
                                                               "first": "spin.webp"}


def test_inside_the_layout_webps_go_to_the_webp_root_and_the_summary_links_them(tmp_path, scratch_root):
    out = artifact_paths.evidence_dir("widgets", "clock_smoke", "run", date="20261107")
    args = SimpleNamespace(output=out)
    work = evidence_media.redirect_output(args, "output", "unit")
    work.mkdir(parents=True)
    _noisy_frame(1, (64, 48)).save(work / "card.png")
    (work / "manifest.json").write_text(json.dumps({"card": str(work / "card.png")}))
    evidence_media.finish(0)
    webp = artifact_paths.WEBP_ROOT / "widgets" / "clock_smoke" / "20261107_run_card.webp"
    assert webp.is_file()
    assert sorted(path.name for path in out.iterdir()) == ["manifest.json"]
    assert json.loads((out / "manifest.json").read_text()) == {"card": str(webp)}


def test_a_failed_tool_run_keeps_its_scratch_for_debugging(tmp_path, scratch_root, capsys):
    args = SimpleNamespace(output=tmp_path / "evidence")
    work = evidence_media.redirect_output(args, "output", "unit")
    work.mkdir(parents=True)
    _noisy_frame(0, (32, 32)).save(work / "frame.png")
    assert evidence_media.finish(1) == 1
    assert (work / "frame.png").exists()
    assert str(work.parent) in capsys.readouterr().err
    assert not (tmp_path / "evidence").exists()


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

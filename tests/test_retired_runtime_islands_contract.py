"""Removal gates for caller-proven pre-Quick runtime islands."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _production_python_files():
    for dirname in ("core", "engine", "rendering", "ui", "utils", "widgets"):
        yield from (ROOT / dirname).rglob("*.py")


def test_prequick_visualizer_renderer_island_is_removed() -> None:
    assert not (ROOT / "widgets" / "spotify_visualizer" / "renderers").exists()
    offenders = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "widgets.spotify_visualizer.renderers" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
    assert (ROOT / "rendering" / "quick" / "visualizer" / "implementations").is_dir()


def test_dead_sync_image_processor_is_removed() -> None:
    assert not (ROOT / "rendering" / "image_processor.py").exists()
    offenders = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "rendering.image_processor import" in text or "rendering.image_processor." in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
    assert (ROOT / "rendering" / "image_processor_async.py").is_file()

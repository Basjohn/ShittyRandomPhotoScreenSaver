"""Durable visual evidence as small WebP (Docs/Guardrails.md "Evidence and scratch hygiene").

* A frame sequence becomes ONE animated WebP at 24 fps, under 10 MB, at a reduced size (the longest side starts
  at ``DEFAULT_MAX_SIDE`` and steps down until the file fits the cap).
* A still (a frame, a contact sheet, a strip) becomes a still WebP.
* PNG frames are temporary: ``frame_sequence`` hands out frame paths inside an owner scratch folder
  (``tools/artifact_paths.scratch``), encodes them on success and deletes the folder on success and on
  exceptions. ``still_from_png`` deletes its source PNG once encoded.

Destinations come from ``tools/artifact_paths.py`` (``output_webp``/``webp_path``); this module only encodes.
Product showcase WebPs are ``tools/release_media.py``'s own business and do not use this helper.
"""
from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

EVIDENCE_FPS = 24
MAX_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_SIDE = 960
MIN_SIDE = 160
DEFAULT_QUALITY = 80
STILL_MAX_SIDE = 1920
STILL_QUALITY = 88


def _frame_durations(count: int, fps: int) -> list[int]:
    """Integer millisecond durations whose running total tracks ``count / fps`` exactly."""
    return [round((i + 1) * 1000 / fps) - round(i * 1000 / fps) for i in range(count)]


def _open_rgb(source: Any):
    from PIL import Image

    if isinstance(source, (str, Path)):
        with Image.open(source) as image:
            return image.convert("RGB")
    return source.convert("RGB")


def _fit(image, max_side: int):
    from PIL import Image

    width, height = image.size
    scale = min(1.0, max_side / max(width, height))
    if scale >= 1.0:
        return image
    return image.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS)


def animated_webp(
    frames: Sequence[Any],
    output: str | Path,
    *,
    fps: int = EVIDENCE_FPS,
    max_bytes: int = MAX_BYTES,
    max_side: int = DEFAULT_MAX_SIDE,
    quality: int = DEFAULT_QUALITY,
) -> dict:
    """Encode ``frames`` (PNG paths or PIL images) as one looping animated WebP under ``max_bytes``.

    The longest side starts at ``max_side`` and steps down (x0.75) until the file fits; raises when even
    ``MIN_SIDE`` does not. Returns the encoding receipt (size, frames, fps, bytes).
    """
    if len(frames) < 2:
        raise ValueError("an animated WebP needs at least two frames; use still_webp for one")
    if not 1 <= fps <= 60 or max_bytes <= 0:
        raise ValueError("invalid fps or byte cap")
    output = Path(output)
    if output.suffix.lower() != ".webp":
        raise ValueError(f"evidence media is WebP: {output}")
    sources = [_open_rgb(frame) for frame in frames]
    durations = _frame_durations(len(sources), fps)
    side = max(MIN_SIDE, min(max_side, max(sources[0].size)))
    attempts = []
    while True:
        images = [_fit(image, side) for image in sources]
        stream = io.BytesIO()
        images[0].save(stream, format="WEBP", save_all=True, append_images=images[1:], duration=durations,
                       loop=0, quality=quality, method=4)
        data = stream.getvalue()
        attempts.append({"max_side": side, "bytes": len(data)})
        if len(data) <= max_bytes:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            return {"path": str(output), "frames": len(images), "fps": fps, "size": list(images[0].size),
                    "bytes": len(data), "attempts": attempts}
        if side <= MIN_SIDE:
            raise ValueError(f"animation exceeds {max_bytes} bytes even at {MIN_SIDE}px: {attempts}")
        side = max(MIN_SIDE, round(side * 0.75))


def still_webp(
    source: Any, output: str | Path, *, max_side: int = STILL_MAX_SIDE, quality: int = STILL_QUALITY,
) -> dict:
    """One still (a PNG path or PIL image) as a WebP, reduced so its longest side is at most ``max_side``."""
    output = Path(output)
    if output.suffix.lower() != ".webp":
        raise ValueError(f"evidence media is WebP: {output}")
    image = _fit(_open_rgb(source), max_side)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="WEBP", quality=quality, method=4)
    return {"path": str(output), "size": list(image.size), "bytes": output.stat().st_size}


def still_from_png(png: str | Path, output: str | Path, **kwargs) -> dict:
    """``still_webp`` from a temporary PNG, which is deleted once encoded (also on failure)."""
    png = Path(png)
    try:
        return still_webp(png, output, **kwargs)
    finally:
        png.unlink(missing_ok=True)


def save_qimage_webp(image: Any, output: str | Path, **kwargs) -> dict:
    """A ``QImage`` (e.g. an offscreen ``grabWindow``) as a still WebP, through a scratch PNG."""
    from tools.artifact_paths import scratch

    with scratch("evidence_media") as folder:
        png = folder / "still.png"
        if not image.save(str(png)):
            raise OSError(f"could not save the grabbed image to {png}")
        return still_webp(png, output, **kwargs)


@dataclass
class FrameSequence:
    """Frame paths inside a scratch folder; ``frame_sequence`` encodes them on exit."""

    folder: Path
    paths: list[Path] = field(default_factory=list)
    receipt: dict | None = None

    def next_path(self, suffix: str = ".png") -> Path:
        path = self.folder / f"frame_{len(self.paths):05d}{suffix}"
        self.paths.append(path)
        return path

    def add(self, path: str | Path) -> None:
        """Register a frame the caller wrote itself (it must lie inside ``folder``)."""
        path = Path(path)
        if self.folder not in path.resolve().parents:
            raise ValueError(f"frames live in the scratch folder {self.folder}, not {path}")
        self.paths.append(path)


@contextlib.contextmanager
def frame_sequence(owner: str, output: str | Path, **encode: Any) -> Iterator[FrameSequence]:
    """Collect PNG frames in ``.artifacts/scratch/<owner>/``; on success encode ``output`` (animated WebP).

    The scratch folder, and every PNG in it, is deleted on success and on exceptions.
    """
    from tools.artifact_paths import scratch

    with scratch(owner) as folder:
        sequence = FrameSequence(folder)
        yield sequence
        written = [path for path in sequence.paths if path.exists()]
        if len(written) >= 2:
            sequence.receipt = animated_webp(written, output, **encode)
        elif written:
            sequence.receipt = still_webp(written[0], output)


__all__ = [
    "EVIDENCE_FPS",
    "FrameSequence",
    "MAX_BYTES",
    "animated_webp",
    "frame_sequence",
    "save_qimage_webp",
    "still_from_png",
    "still_webp",
]

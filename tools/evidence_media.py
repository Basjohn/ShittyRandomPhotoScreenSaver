"""Frame sequences as small animated WebP (Docs/Guardrails.md "Evidence and scratch hygiene").

Operator, 7 Nov 2026: PNGs are not barred. Only single frames used to show motion are replaced, by ONE animated
WebP at 24 fps, under 10 MB, at a reduced size (the longest side starts at ``DEFAULT_MAX_SIDE`` and steps down
until the file fits the cap). Stills (a screenshot, a contact sheet, a strip, a before/after) stay PNG, lossless.

A tool writes into an owner scratch folder (``tools/artifact_paths.py``). When the tool succeeds the folder is
published UNCHANGED (every file copied as the tool wrote it; tools and compare steps read PNG) and deleted. Turning a
kept frame sequence into one animated WebP is a deliberate ``animated_webp`` call, never automatic.
When it fails the folder stays, its path is printed for debugging, and ``python tools/artifact_paths.py
prune-scratch`` clears it later.

Destinations come from ``tools/artifact_paths.py``. Product showcase WebPs are ``tools/release_media.py``'s
own business and do not use this module.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator, Sequence

EVIDENCE_FPS = 24
MAX_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_SIDE = 960
MIN_SIDE = 160
DEFAULT_QUALITY = 80


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
        raise ValueError("an animated WebP needs at least two frames")
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


_TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".md", ".csv", ".html", ".log"}


def publish(work: Path, out_dir: Path) -> dict:
    """Publish a tool's scratch output folder unchanged.

    Every file (PNGs, stills and frames alike, data, logs) is copied to ``out_dir`` exactly as the tool wrote it:
    tools and their compare steps read PNG, so publishing never converts anything. In text files (json, txt, md,
    csv, html) the scratch folder's path is rewritten to ``out_dir``, so a summary's links stay valid. Replacing a
    kept frame sequence by one animated WebP is a deliberate step (``animated_webp``), never automatic.
    Returns ``{"files": [...]}``.
    """
    work, out_dir = Path(work), Path(out_dir)
    copied: list[str] = []
    if not work.exists():
        return {"files": copied}

    def forms(path: Path) -> tuple[str, ...]:
        native = str(path)
        return (native.replace("\\", "\\\\"), native, native.replace("\\", "/"))

    for path in sorted(work.rglob("*")):
        if not path.is_file():
            continue
        target = out_dir / path.relative_to(work)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in _TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
            for old, new in zip(forms(work), forms(out_dir)):
                text = text.replace(old, new)
            target.write_text(text, encoding="utf-8", errors="surrogateescape")
        else:
            shutil.copyfile(path, target)
        copied.append(str(target))
    return {"files": copied}


@contextlib.contextmanager
def evidence_workspace(owner: str, out_dir: str | Path) -> Iterator[Path]:
    """A scratch output folder for a tool that writes PNGs, published to ``out_dir`` when the block succeeds.

    Yields a not-yet-created path inside ``.artifacts/scratch/<owner>/``. On success it is published
    (``publish``) and deleted; on failure it is kept and its path printed (``artifact_paths.scratch``).
    """
    from tools.artifact_paths import scratch

    out_dir = Path(out_dir)
    with scratch(owner) as folder:
        work = folder / "out"
        yield work
        out_dir.mkdir(parents=True, exist_ok=True)
        receipt = publish(work, out_dir)
        print(f"evidence: {len(receipt['files'])} files in {out_dir}")


_PENDING: list[tuple[Path, Path, Path]] = []


def redirect_output(args: Any, attribute: str, owner: str) -> Path:
    """CLI tools: write ``args.<attribute>`` into owner scratch; ``finish`` publishes it on success.

    The destination (a folder, or a file such as ``out/sheet.png``) is remembered and ``args`` points into a
    scratch folder instead; the tool runs unchanged. The tool's ``__main__`` line becomes
    ``raise SystemExit(evidence_media.finish(main()))``. A destination already under ``.artifacts/scratch``
    is left alone (lossless frames a later compare step reads may live there while they are examined).
    """
    from tools import artifact_paths

    destination = Path(getattr(args, attribute))
    if artifact_paths.in_scratch(destination):
        return destination
    folder = artifact_paths.scratch_root(owner) / f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    work = folder / "out"
    file_mode = bool(destination.suffix) and not destination.is_dir()
    if file_mode:
        work.mkdir(parents=True)
    else:
        folder.mkdir(parents=True)
    _PENDING.append((folder, work, destination.parent if file_mode else destination))
    redirected = work / destination.name if file_mode else work
    setattr(args, attribute, redirected)
    return redirected


def finish(code: int | None = 0) -> int | None:
    """End of a CLI run: on success (``0``/``None``) publish every redirected output and delete its scratch;
    on failure keep the scratch and print where it is."""
    while _PENDING:
        folder, work, target = _PENDING.pop()
        if code not in (0, None):
            print(f"failed (exit {code}); scratch kept for debugging: {folder}", file=sys.stderr)
            continue
        target.mkdir(parents=True, exist_ok=True)
        receipt = publish(work, target)
        print(f"evidence: {len(receipt['files'])} files in {target}")
        shutil.rmtree(folder)
        with contextlib.suppress(OSError):
            folder.parent.rmdir()
    return code


__all__ = [
    "EVIDENCE_FPS",
    "MAX_BYTES",
    "animated_webp",
    "evidence_workspace",
    "finish",
    "publish",
    "redirect_output",
]

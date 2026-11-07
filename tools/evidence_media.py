"""Durable visual evidence as small WebP (Docs/Guardrails.md "Evidence and scratch hygiene").

* A frame sequence becomes ONE animated WebP at 24 fps, under 10 MB, at a reduced size (the longest side starts
  at ``DEFAULT_MAX_SIDE`` and steps down until the file fits the cap).
* A still (a frame, a contact sheet, a strip) becomes a still WebP.
* PNGs are temporary: a tool writes them into an owner scratch folder (``tools/artifact_paths.py``). When the
  tool succeeds the folder is published (PNGs as WebP, data copied and relinked) and deleted. When it fails
  the folder stays, its path is printed for debugging, and ``python tools/artifact_paths.py prune-scratch``
  clears it later.

Destinations come from ``tools/artifact_paths.py``. Product showcase WebPs are ``tools/release_media.py``'s
own business and do not use this module.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
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


_SEQUENCE = re.compile(r"^(?P<stem>.*?)(?P<index>\d{2,})$")
_TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".md", ".csv", ".html", ".log"}


def _webp_home(out_dir: Path) -> tuple[Path, str] | None:
    """For an evidence folder ``evidence/<area>/<topic>/<YYYYMMDD>_<label>[/sub]``: the WebP folder
    ``webp/<area>/<topic>`` and the name prefix ``<YYYYMMDD>_<label>[_sub]``; None outside the layout."""
    from tools import artifact_paths

    relative = artifact_paths._relative_to_root(out_dir.resolve(), artifact_paths.EVIDENCE_ROOT.resolve())
    if relative is None or not artifact_paths._layout_shaped(relative):
        return None
    depth = 2 if relative[0] in artifact_paths._NAMED_AREAS else 1
    return (artifact_paths.WEBP_ROOT.joinpath(*relative[: depth + 1]),
            "_".join(relative[depth + 1:]))


def _reference(path: Path) -> str:
    """How a summary names a published WebP: repository-relative under the layout, else absolute."""
    from tools import artifact_paths

    relative = artifact_paths._relative_to_root(path.resolve(), artifact_paths.ARTIFACTS_ROOT.resolve())
    if relative is None:
        return str(path)
    return "/".join((".artifacts", *relative))


def publish(work: Path, out_dir: Path) -> dict:
    """Publish a tool's scratch output folder as durable evidence.

    * PNGs whose names differ only by a trailing frame number (``frame_0001.png``...) in one folder become one
      animated 24 fps WebP named after their stem; every other PNG becomes a still WebP. When ``out_dir`` is
      an evidence folder the WebPs go to the matching ``.artifacts/webp/<area>/<topic>/`` as
      ``<YYYYMMDD>_<label>_<name>.webp``; elsewhere (tests) they sit beside the data.
    * Every other file is copied to ``out_dir``; in text files (json, txt, md, csv, html) each PNG path or name
      is rewritten to its WebP, so a summary links its WebPs by path.
    Returns ``{"webp": [...], "files": [...], "renamed": {png name: reference}}``. The PNGs stay in ``work``.
    """
    work, out_dir = Path(work), Path(out_dir)
    home = _webp_home(out_dir)
    renamed: dict[str, str] = {}
    absolute: dict[Path, Path] = {}
    written: list[str] = []
    copied: list[str] = []
    if not work.exists():
        return {"webp": written, "files": copied, "renamed": renamed}

    def destination(parent: Path, name: str) -> Path:
        sub = parent.relative_to(work).parts
        if home is None:
            return out_dir.joinpath(*sub, f"{name}.webp")
        folder, prefix = home
        return folder / ("_".join(part for part in (prefix, *sub, name) if part) + ".webp")

    pngs = sorted(path for path in work.rglob("*") if path.is_file() and path.suffix.lower() == ".png")
    groups: dict[tuple[Path, str], list[Path]] = {}
    for png in pngs:
        match = _SEQUENCE.match(png.stem)
        key = (png.parent, match.group("stem").rstrip("_-.") if match else "\0" + png.stem)
        groups.setdefault(key, []).append(png)
    for (parent, stem), members in groups.items():
        if len(members) >= 2 and not stem.startswith("\0"):
            members.sort(key=lambda path: int(_SEQUENCE.match(path.stem).group("index")))
            target = destination(parent, stem or "frames")
            animated_webp(members, target)
            outputs = [(member, target) for member in members]
        else:
            outputs = []
            for member in members:
                target = destination(parent, member.stem)
                still_webp(member, target)
                outputs.append((member, target))
                written.append(str(target))
        if len(members) >= 2 and not stem.startswith("\0"):
            written.append(str(target))
        for member, target in outputs:
            absolute[member] = target
            renamed[member.name] = target.name if home is None else _reference(target)

    def forms(path: Path) -> tuple[str, ...]:
        native = str(path)
        return (native.replace("\\", "\\\\"), native, native.replace("\\", "/"))

    for path in sorted(work.rglob("*")):
        if not path.is_file() or path.suffix.lower() == ".png":
            continue
        target = out_dir / path.relative_to(work)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in _TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
            for png, webp in absolute.items():                       # full paths first (JSON-escaped too)
                for old, new in zip(forms(png), forms(webp)):
                    text = text.replace(old, new)
            for old in sorted(renamed, key=len, reverse=True):         # then bare names
                text = text.replace(old, renamed[old])
            for old, new in zip(forms(work), forms(out_dir)):
                text = text.replace(old, new)
            target.write_text(text, encoding="utf-8", errors="surrogateescape")
        else:
            shutil.copyfile(path, target)
        copied.append(str(target))
    return {"webp": written, "files": copied, "renamed": renamed}


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
        print(f"evidence: {len(receipt['webp'])} WebP and {len(receipt['files'])} files in {out_dir}")


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
        print(f"evidence: {len(receipt['webp'])} WebP and {len(receipt['files'])} files in {target}")
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
    "still_from_png",
    "still_webp",
]

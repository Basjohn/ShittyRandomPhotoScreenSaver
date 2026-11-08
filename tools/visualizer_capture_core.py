"""Operator-facing orchestration of SRPSS's existing release_media.py renderer.

No renderer, replay model, or encoder is reimplemented here. All source frames,
release manifests and failures remain in a disposable, ignored logs workspace.
Only a verified WebP is published to the user's chosen output folder.
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RELEASE_MEDIA = ROOT / "tools" / "release_media.py"
RECORDINGS = ROOT / "logs" / "visualizer_recordings"
DEFAULT_OUTPUT = ROOT / "assets" / "temp"
_VALID_ID = re.compile(r"^[a-zA-Z0-9_]+$")


class CaptureError(Exception):
    """Invalid capture options, engine failure, or failed output verification."""


class CaptureCancelled(CaptureError):
    pass


def repo_python() -> Path:
    """Always run against this checkout's existing venv. Never install packages."""
    candidates = (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise CaptureError("SRPSS repository .venv Python is missing. Use the repository's normal environment setup.")


def _run_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def list_visualizer_cases() -> list[dict]:
    """Ask the existing release tool for the canonical current mode/preset catalogue."""
    if not RELEASE_MEDIA.is_file():
        raise CaptureError(f"Existing renderer is missing: {RELEASE_MEDIA}")
    try:
        result = subprocess.run(
            [str(repo_python()), str(RELEASE_MEDIA), "--list", "--kind", "visualizer"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=_run_flags(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CaptureError(f"Could not read the visualizer catalogue: {exc}") from exc
    if result.returncode:
        raise CaptureError("The release renderer could not enumerate visualizers:\n" + (result.stderr or result.stdout)[-4500:])
    try:
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise ValueError("catalogue is not a list")
        cases = [
            {"identity": case["identity"], "variant": case["variant"],
             "label": case["label"], "preset": case["preset"]}
            for case in data if case.get("kind") == "visualizer"
        ]
        if not cases or any(not _VALID_ID.fullmatch(c["identity"]) or
                            not _VALID_ID.fullmatch(c["variant"]) for c in cases):
            raise ValueError("missing or invalid visualizer identifiers")
        return cases
    except (ValueError, KeyError, TypeError) as exc:
        raise CaptureError(f"The existing renderer returned an invalid visualizer catalogue: {exc}") from exc


def available_recordings() -> list[Path]:
    """Nonrecursive canonical recordings only. Release Media validates actual content."""
    if not RECORDINGS.is_dir():
        return []
    return sorted(
        (p for p in RECORDINGS.glob("*.jsonl")
         if not re.search(r"_(noevents|v\d+)$", p.stem)),
        key=lambda p: (-(p.stat().st_mtime), p.name.casefold()),
    )


@dataclass(frozen=True)
class CaptureOptions:
    identity: str
    variant: str
    recording: Path
    start_seconds: float = 5.0
    duration_seconds: float = 4.0
    fps: int = 24
    capture_width: int = 1280
    output_width: int = 960
    max_bytes: int = 10_000_000
    destination: Path = DEFAULT_OUTPUT
    accept_reduced_fps: bool = False

    def validate(self) -> None:
        if not _VALID_ID.fullmatch(self.identity) or not _VALID_ID.fullmatch(self.variant):
            raise CaptureError("Invalid visualizer or preset identifier.")
        recording = self.recording.expanduser().resolve()
        if not recording.is_file() or recording.suffix.lower() != ".jsonl" or recording.parent != RECORDINGS.resolve():
            raise CaptureError("Select an existing canonical .jsonl recording in logs/visualizer_recordings.")
        if re.search(r"_(noevents|v\d+)$", recording.stem):
            raise CaptureError("Archived/diagnostic recordings are not accepted by the release renderer.")
        if not 0 <= self.start_seconds <= 36000:
            raise CaptureError("Start time must be nonnegative.")
        if not 0 < self.duration_seconds <= 30:
            raise CaptureError("Duration must be 0–30 seconds.")
        if not 160 <= self.output_width <= self.capture_width <= 3840:
            raise CaptureError("Output width must be 160–3840 and no larger than the capture width.")
        if not 10 <= self.fps <= 60:
            raise CaptureError("FPS must be 10–60.")
        if not 100_000 <= self.max_bytes <= 2 * 1024 ** 3 - 1:
            raise CaptureError("Invalid WebP byte limit.")
        if not self.destination:
            raise CaptureError("Select an output directory.")
        if not RELEASE_MEDIA.is_file():
            raise CaptureError("Missing SRPSS renderer: tools/release_media.py")


def _timeline_webp(data: bytes) -> tuple[list[int], int]:
    """Read WebP's actual ANMF timing and ANIM loop count; never infer fps."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise CaptureError("Rendered result is not a WebP container.")
    extent = int.from_bytes(data[4:8], "little") + 8
    if extent != len(data):
        raise CaptureError("Rendered WebP has an invalid RIFF length.")
    durations: list[int] = []
    loop = None
    offset = 12
    while offset < extent:
        if offset + 8 > extent:
            raise CaptureError("Rendered WebP has a truncated chunk header.")
        tag = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        start = offset + 8
        if start + size > extent:
            raise CaptureError("Rendered WebP has a truncated chunk.")
        if tag == b"ANMF":
            if size < 16:
                raise CaptureError("Invalid animated frame record.")
            durations.append(int.from_bytes(data[start + 12:start + 15], "little"))
        elif tag == b"ANIM":
            if size < 6:
                raise CaptureError("Invalid animated WebP header.")
            loop = int.from_bytes(data[start + 4:start + 6], "little")
        offset = start + size + (size % 2)
    if offset != extent or loop is None or not durations or any(d < 11 for d in durations):
        raise CaptureError("Rendered animation has invalid frame timing or looping.")
    return durations, loop


def _verify_animation(path: Path, options: CaptureOptions, receipt: dict) -> dict:
    data = path.read_bytes()
    if len(data) > options.max_bytes:
        raise CaptureError("The renderer exceeded the requested size cap.")
    durations, loop = _timeline_webp(data)
    if loop != 0:
        raise CaptureError("The renderer did not produce an infinite WebP loop.")
    intended_ms = round(options.duration_seconds * 1000)
    if sum(durations) != intended_ms:
        raise CaptureError(f"Animation duration changed: expected {intended_ms} ms, found {sum(durations)} ms.")
    actual_fps = receipt.get("fps")
    if not isinstance(actual_fps, (int, float)) or actual_fps <= 0:
        raise CaptureError("The renderer did not report a valid FPS.")
    if not options.accept_reduced_fps and actual_fps != options.fps:
        raise CaptureError(
            f"The renderer reduced {options.fps} fps to {actual_fps} fps to meet the size cap. "
            "Nothing published. Try a smaller width or higher size cap, or opt into FPS reduction."
        )
    if receipt.get("time_scale") != 1.0:
        raise CaptureError("The renderer changed playback speed; nothing published.")
    with Image.open(path) as image:
        if not image.is_animated or image.n_frames != len(durations):
            raise CaptureError("Rendered WebP failed decoded frame count verification.")
        dimensions = tuple(image.size)
    return {"frames": len(durations), "duration_ms": sum(durations), "loop": loop,
            "fps": actual_fps, "dimensions": dimensions, "bytes": len(data)}


def _new_output_name(destination: Path, base: str) -> Path:
    target = destination / base
    if not target.exists():
        return target
    for index in range(2, 10000):
        candidate = destination / f"{target.stem}_{index}{target.suffix}"
        if not candidate.exists():
            return candidate
    raise CaptureError("Too many outputs with the same filename.")


def _publish_without_overwrite(source: Path, destination: Path) -> Path:
    """Stage on destination volume, then publish without overwriting existing work."""
    destination.mkdir(parents=True, exist_ok=True)
    stage = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".capture_", suffix=".tmp", dir=destination, delete=False) as stream:
            stage = Path(stream.name)
            with source.open("rb") as opened:
                shutil.copyfileobj(opened, stream, 1024 * 1024)
        for index in range(1, 10000):
            name = source.name if index == 1 else f"{source.stem}_{index}{source.suffix}"
            candidate = destination / name
            try:
                # Same-volume link: exclusive and atomic on NTFS/ext4. Existing captures stay untouched.
                os.link(stage, candidate)
                return candidate
            except FileExistsError:
                continue
            except OSError as exc:
                # Hardlink-unavailable filesystems: copy exclusively, never overwrite.
                if candidate.exists():
                    continue
                created = False
                try:
                    with candidate.open("xb") as published:
                        created = True
                        with stage.open("rb") as incoming:
                            shutil.copyfileobj(incoming, published, 1024 * 1024)
                    return candidate
                except FileExistsError:
                    continue
                except Exception:
                    if created:
                        candidate.unlink(missing_ok=True)
                    raise CaptureError(f"Could not publish the verified WebP: {exc}") from exc
        raise CaptureError("Too many captures with the same output name.")
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


def capture_webp(options: CaptureOptions, *, notify: Callable[[str], None] | None = None,
                 cancelled: Callable[[], bool] | None = None) -> dict:
    """Drive the real release renderer in an isolated child and publish only its WebP."""
    options.validate()
    notify = notify or (lambda _message: None)
    cancelled = cancelled or (lambda: False)
    if cancelled():
        raise CaptureCancelled("Cancelled before capture started.")
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".viz_capture_", dir=ROOT / "logs") as scratch:
        scratch_path = Path(scratch)
        render_dir = scratch_path / "render"
        command = [
            str(repo_python()), str(RELEASE_MEDIA),
            "--kind", "visualizer", "--id", options.identity, "--variant", options.variant,
            "--clip", str(options.recording.expanduser().resolve()),
            "--start-seconds", str(options.start_seconds),
            "--duration-seconds", str(options.duration_seconds),
            "--capture-width", str(options.capture_width),
            "--width", str(options.output_width),
            "--fps", str(options.fps),
            "--max-bytes", str(options.max_bytes),
            "--output-dir", str(render_dir),
        ]
        notify(f"Rendering {options.identity} / {options.variant} from {options.recording.name}")
        notify("Scratch workspace and release manifests are temporary; only the final WebP is published.")
        try:
            proc = subprocess.Popen(
                command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=_run_flags(),
            )
        except OSError as exc:
            raise CaptureError(f"Could not start the production renderer: {exc}") from exc
        lines: queue.SimpleQueue[str] = queue.SimpleQueue()

        def reader() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.put(line.rstrip("\r\n"))
            proc.stdout.close()

        pump = threading.Thread(target=reader, name="srpss-render-output", daemon=True)
        pump.start()
        tail: list[str] = []
        try:
            while proc.poll() is None:
                if cancelled():
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    raise CaptureCancelled("Capture cancelled; no finished WebP published.")
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line:
                    notify(line)
                    tail.append(line)
                    tail = tail[-40:]
            pump.join(timeout=2)
            while not lines.empty():
                line = lines.get_nowait()
                if line:
                    notify(line)
                    tail.append(line)
                    tail = tail[-40:]
            if cancelled():
                raise CaptureCancelled("Capture cancelled; no finished WebP published.")
            if proc.returncode != 0:
                raise CaptureError("Production capture failed.\n" + "\n".join(tail[-14:]))
            source = render_dir / f"visualizer_{options.identity}_{options.variant}.webp"
            manifest_path = render_dir / "release_media.json"
            if not source.is_file() or not manifest_path.is_file():
                raise CaptureError("The release renderer reported success without the expected WebP and manifest.")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = manifest.get("entries", {}).get(f"visualizer/{options.identity}/{options.variant}")
            if not isinstance(entry, dict) or entry.get("file") != source.name:
                raise CaptureError("Capture manifest did not identify the requested output.")
            verified = _verify_animation(source, options, entry)
            if cancelled():
                raise CaptureCancelled("Capture cancelled; no finished WebP published.")
            target = _publish_without_overwrite(source, options.destination.expanduser().resolve())
            notify(f"Published {target.name} ({verified['bytes']:,} bytes, {verified['duration_ms']} ms).")
            return {"output_path": str(target), "visualizer": options.identity,
                    "preset": options.variant, "recording": str(options.recording), **verified}
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            pump.join(timeout=2)

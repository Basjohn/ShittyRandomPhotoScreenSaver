#!/usr/bin/env python3
"""
Standalone Spotify GSMTC live-thumbnail cadence probe.

Run this while a Spotify video is already playing. The probe does not control
Spotify and does not import or modify SRPSS.

Default:
    python gsm_tc_spotify_video_probe.py

It samples Spotify's GSMTC media properties for 15 seconds at up to 60 polls/s,
measuring:

1. How often the GSMTC thumbnail actually changes (raw and decoded-pixel hashes).
2. Whether MediaPropertiesChanged events fire while those frame changes occur.
3. Thumbnail dimensions, decode cost, and rough black-bar/content-AR evidence.

Output:
    <folder containing this script>/tmp/gsm_tc_video_probe_YYYYMMDD_HHMMSS/
        report.txt
        samples.csv
        events.csv
        probe.log
        frames/      # a few representative changed frames

Dependencies expected in the SRPSS venv:
    winrt-runtime
    winrt-Windows.Media.Control
    winrt-Windows.Storage.Streams
    Pillow (optional, but strongly recommended)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import io
import logging
import math
from pathlib import Path
import statistics
import sys
import threading
import time
from typing import Any, Callable


try:
    from winrt.windows.media.control import (  # type: ignore[import]
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    )
    from winrt.windows.storage.streams import DataReader  # type: ignore[import]
except Exception as exc:  # pragma: no cover - diagnostic environment only
    MediaManager = None
    DataReader = None
    WINRT_IMPORT_ERROR = exc
else:
    WINRT_IMPORT_ERROR = None

try:
    from PIL import Image  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    Image = None


MAX_THUMBNAIL_BYTES = 8 * 1024 * 1024


@dataclass
class Sample:
    index: int
    t_ms: float
    request_ms: float
    analysis_ms: float
    thumbnail_bytes: int
    raw_sha256: str
    pixel_sha256: str
    raw_changed: bool
    frame_changed: bool
    width: int
    height: int
    image_format: str
    top_black_pct: float
    bottom_black_pct: float
    left_black_pct: float
    right_black_pct: float
    content_aspect_ratio: float
    media_event_count: int
    title: str
    artist: str
    error: str


@dataclass
class EventRecord:
    index: int
    t_ms: float
    event: str


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    frac = pos - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def _fmt(value: float, digits: int = 2) -> str:
    if not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _session_source_id(session: Any) -> str:
    try:
        value = getattr(session, "source_app_user_model_id", "")
        return str(value or "")
    except Exception:
        return ""


def _sessions(manager: Any) -> list[Any]:
    try:
        return list(manager.get_sessions())
    except Exception:
        return []


def _is_playing(session: Any) -> bool:
    try:
        status = session.get_playback_info().playback_status
        name = getattr(status, "name", None)
        if name:
            return str(name).lower() == "playing"
        text = str(status).lower()
        return "playing" in text or text.endswith(".4")
    except Exception:
        return False


def _choose_session(manager: Any) -> tuple[Any, str, bool, list[str]]:
    sessions = _sessions(manager)
    session_ids = [_session_source_id(item) for item in sessions]

    spotify = [
        item
        for item in sessions
        if "spotify" in _session_source_id(item).lower()
    ]

    if spotify:
        playing = [item for item in spotify if _is_playing(item)]
        if playing:
            selected = playing[0]
        else:
            try:
                current = manager.get_current_session()
            except Exception:
                current = None
            if current is not None and any(current is item for item in spotify):
                selected = current
            else:
                selected = spotify[0]
        return selected, _session_source_id(selected), True, session_ids

    try:
        current = manager.get_current_session()
    except Exception:
        current = None

    if current is not None:
        return current, _session_source_id(current), False, session_ids

    raise RuntimeError("No GSMTC media session was found. Start Spotify playback first.")


async def _read_thumbnail(media_properties: Any) -> bytes:
    if DataReader is None:
        return b""

    thumb_ref = getattr(media_properties, "thumbnail", None)
    if thumb_ref is None:
        return b""

    stream = await thumb_ref.open_read_async()
    if stream is None:
        return b""

    try:
        size = int(getattr(stream, "size", 0))
    except Exception:
        size = 0

    if size <= 0:
        return b""

    requested = min(size, MAX_THUMBNAIL_BYTES)
    reader = DataReader(stream)
    try:
        loaded = await reader.load_async(requested)
        actual = int(loaded) if loaded is not None else 0
        if actual <= 0:
            try:
                actual = int(getattr(reader, "unconsumed_buffer_length", 0))
            except Exception:
                actual = 0

        if actual <= 0:
            return b""

        buf = bytearray(actual)
        reader.read_bytes(buf)
        return bytes(buf)
    finally:
        try:
            reader.close()
        except Exception:
            pass


def _row_black_fraction(rgb: Any, y: int, threshold: int = 18) -> float:
    px = rgb.load()
    width, _height = rgb.size
    black = 0
    for x in range(width):
        r, g, b = px[x, y]
        if max(r, g, b) <= threshold:
            black += 1
    return black / max(1, width)


def _column_black_fraction(rgb: Any, x: int, threshold: int = 18) -> float:
    px = rgb.load()
    _width, height = rgb.size
    black = 0
    for y in range(height):
        r, g, b = px[x, y]
        if max(r, g, b) <= threshold:
            black += 1
    return black / max(1, height)


def _estimate_black_bars(rgb: Any) -> tuple[float, float, float, float, float]:
    """
    Roughly estimate contiguous nearly-black borders.

    This is intentionally evidence, not a definitive video detector: naturally
    dark artwork can look like letterboxing. Temporal pixel changes are the
    stronger signal.
    """
    probe = rgb.copy()
    probe.thumbnail((240, 240))
    width, height = probe.size
    if width < 2 or height < 2:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    required_black_fraction = 0.94

    top = 0
    for y in range(height):
        if _row_black_fraction(probe, y) >= required_black_fraction:
            top += 1
        else:
            break

    bottom = 0
    for y in range(height - 1, -1, -1):
        if _row_black_fraction(probe, y) >= required_black_fraction:
            bottom += 1
        else:
            break

    left = 0
    for x in range(width):
        if _column_black_fraction(probe, x) >= required_black_fraction:
            left += 1
        else:
            break

    right = 0
    for x in range(width - 1, -1, -1):
        if _column_black_fraction(probe, x) >= required_black_fraction:
            right += 1
        else:
            break

    # A nearly-black actual frame should not be classified as "all bars".
    if top + bottom >= int(height * 0.80):
        top = bottom = 0
    if left + right >= int(width * 0.80):
        left = right = 0

    inner_width = max(1, width - left - right)
    inner_height = max(1, height - top - bottom)
    content_ar = inner_width / inner_height

    return (
        100.0 * top / height,
        100.0 * bottom / height,
        100.0 * left / width,
        100.0 * right / width,
        content_ar,
    )


def _analyze_image(
    data: bytes,
) -> tuple[str, int, int, str, float, float, float, float, float]:
    if not data or Image is None:
        return "", 0, 0, "", 0.0, 0.0, 0.0, 0.0, 0.0

    with Image.open(io.BytesIO(data)) as image:
        image_format = str(getattr(image, "format", "") or "")
        rgb = image.convert("RGB")
        width, height = rgb.size
        pixel_hash = hashlib.sha256(rgb.tobytes()).hexdigest()
        top, bottom, left, right, content_ar = _estimate_black_bars(rgb)
        return (
            pixel_hash,
            width,
            height,
            image_format,
            top,
            bottom,
            left,
            right,
            content_ar,
        )


def _image_extension(data: bytes, image_format: str) -> str:
    fmt = (image_format or "").lower()
    if fmt in {"jpg", "jpeg"}:
        return ".jpg"
    if fmt == "png":
        return ".png"
    if fmt == "webp":
        return ".webp"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return ".webp"
    return ".bin"


def _subscribe_media_properties_changed(
    session: Any,
    callback: Callable[[Any, Any], None],
) -> tuple[bool, Callable[[], None]]:
    add = getattr(session, "add_media_properties_changed", None)
    remove = getattr(session, "remove_media_properties_changed", None)
    if callable(add):
        token = add(callback)

        def unsubscribe() -> None:
            if callable(remove):
                try:
                    remove(token)
                except Exception:
                    pass

        return True, unsubscribe

    # Defensive fallback for alternate generated event surfaces.
    try:
        event = getattr(session, "media_properties_changed")
        event += callback

        def unsubscribe_descriptor() -> None:
            try:
                current = getattr(session, "media_properties_changed")
                current -= callback
            except Exception:
                pass

        return True, unsubscribe_descriptor
    except Exception:
        return False, (lambda: None)


def _write_csv(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _build_report(
    *,
    args: argparse.Namespace,
    source_id: str,
    spotify_matched: bool,
    session_ids: list[str],
    samples: list[Sample],
    events: list[EventRecord],
    event_subscription_supported: bool,
    actual_elapsed: float,
    representative_count: int,
) -> str:
    successful = [s for s in samples if not s.error and s.thumbnail_bytes > 0]
    request_ms = [s.request_ms for s in successful]
    analysis_ms = [s.analysis_ms for s in successful if s.analysis_ms > 0.0]
    raw_changes = [s for s in successful if s.raw_changed]
    frame_changes = [s for s in successful if s.frame_changed]

    fingerprints = [
        (s.pixel_sha256 or s.raw_sha256)
        for s in successful
        if (s.pixel_sha256 or s.raw_sha256)
    ]
    distinct_frames = len(set(fingerprints))

    poll_rate = len(samples) / actual_elapsed if actual_elapsed > 0 else 0.0
    success_rate = len(successful) / actual_elapsed if actual_elapsed > 0 else 0.0

    frame_change_rate = (
        max(0, len(frame_changes) - 1) / actual_elapsed
        if actual_elapsed > 0 and frame_changes
        else 0.0
    )

    frame_times = [s.t_ms for s in frame_changes]
    frame_intervals = [
        frame_times[i] - frame_times[i - 1]
        for i in range(1, len(frame_times))
        if frame_times[i] > frame_times[i - 1]
    ]

    event_times = [e.t_ms for e in events]
    event_intervals = [
        event_times[i] - event_times[i - 1]
        for i in range(1, len(event_times))
        if event_times[i] > event_times[i - 1]
    ]
    event_rate = len(events) / actual_elapsed if actual_elapsed > 0 else 0.0

    dimensions: dict[tuple[int, int], int] = {}
    for s in successful:
        if s.width and s.height:
            dimensions[(s.width, s.height)] = dimensions.get((s.width, s.height), 0) + 1

    changed_with_image_info = [
        s for s in frame_changes if s.width > 0 and s.height > 0
    ]
    bar_samples = [
        s
        for s in changed_with_image_info
        if max(
            s.top_black_pct,
            s.bottom_black_pct,
            s.left_black_pct,
            s.right_black_pct,
        )
        >= 1.0
    ]

    content_ars = [
        s.content_aspect_ratio
        for s in changed_with_image_info
        if s.content_aspect_ratio > 0
    ]

    if frame_change_rate >= 20.0:
        interpretation = (
            "STRONG: GSMTC is exposing changing pixels at a genuinely video-like cadence. "
            "A latest-frame-wins presentation path is technically plausible."
        )
    elif frame_change_rate >= 10.0:
        interpretation = (
            "PROMISING: the thumbnail behaves like low-frame-rate video, although it is "
            "below a clean 24 fps target."
        )
    elif frame_change_rate >= 3.0:
        interpretation = (
            "LIMITED: animated-frame behavior is real, but cadence is closer to a coarse "
            "preview than conventional video."
        )
    elif frame_change_rate > 0.0:
        interpretation = (
            "WEAK: the thumbnail changes, but only at slideshow-like cadence."
        )
    else:
        interpretation = (
            "STATIC: no changing decoded thumbnail pixels were observed during this run."
        )

    lines = [
        "Spotify GSMTC live-thumbnail probe",
        "=" * 38,
        "",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Python: {sys.version.split()[0]}",
        f"Pillow available: {'yes' if Image is not None else 'NO (raw-byte hashing only)'}",
        f"Requested duration: {args.seconds:.2f} s",
        f"Actual duration: {actual_elapsed:.3f} s",
        f"Requested poll ceiling: {args.poll_hz:.2f} Hz",
        "",
        "Session",
        "-------",
        f"Selected source_app_user_model_id: {source_id or '<blank>'}",
        f"Matched Spotify by source id: {'yes' if spotify_matched else 'NO - current GSMTC session fallback'}",
        f"Enumerated GSMTC sessions: {session_ids or ['<none>']}",
        "",
        "Polling / WinRT cost",
        "--------------------",
        f"Poll attempts: {len(samples)}",
        f"Successful thumbnail reads: {len(successful)}",
        f"Achieved poll rate: {_fmt(poll_rate)} Hz",
        f"Successful thumbnail-read rate: {_fmt(success_rate)} Hz",
        f"TryGetMediaProperties + thumbnail read latency p50: {_fmt(statistics.median(request_ms) if request_ms else math.nan)} ms",
        f"TryGetMediaProperties + thumbnail read latency p95: {_fmt(_percentile(request_ms, 0.95))} ms",
        f"TryGetMediaProperties + thumbnail read latency max: {_fmt(max(request_ms) if request_ms else math.nan)} ms",
    ]

    if Image is not None:
        lines.extend(
            [
                f"Pillow analysis latency p50: {_fmt(statistics.median(analysis_ms) if analysis_ms else math.nan)} ms",
                f"Pillow analysis latency p95: {_fmt(_percentile(analysis_ms, 0.95))} ms",
            ]
        )

    lines.extend(
        [
            "",
            "Changing-thumbnail evidence",
            "---------------------------",
            f"Raw encoded-byte changes observed: {len(raw_changes)}",
            f"Decoded-pixel frame changes observed: {len(frame_changes) if Image is not None else 'n/a (Pillow unavailable)'}",
            f"Distinct observed frame fingerprints: {distinct_frames}",
            f"Observed changing-frame rate: {_fmt(frame_change_rate)} fps",
            f"Inter-frame-change interval median: {_fmt(statistics.median(frame_intervals) if frame_intervals else math.nan)} ms",
            f"Inter-frame-change interval p95: {_fmt(_percentile(frame_intervals, 0.95))} ms",
            f"Representative changed frames saved: {representative_count}",
            "",
            "MediaPropertiesChanged evidence",
            "------------------------------",
            f"Event subscription supported: {'yes' if event_subscription_supported else 'NO'}",
            f"MediaPropertiesChanged events: {len(events)}",
            f"Event rate: {_fmt(event_rate)} Hz",
            f"Event interval median: {_fmt(statistics.median(event_intervals) if event_intervals else math.nan)} ms",
            f"Event interval p95: {_fmt(_percentile(event_intervals, 0.95))} ms",
        ]
    )

    if frame_change_rate > 0:
        lines.append(
            f"Events per observed frame change: {_fmt(len(events) / max(1, len(frame_changes)))}"
        )

    lines.extend(
        [
            "",
            "Image geometry / black-bar evidence",
            "-----------------------------------",
            f"Observed decoded dimensions: {dimensions if dimensions else 'n/a'}",
        ]
    )

    if changed_with_image_info:
        lines.extend(
            [
                f"Changed frames with >=1% estimated black border on an edge: "
                f"{len(bar_samples)}/{len(changed_with_image_info)}",
                f"Median estimated top bar: {_fmt(statistics.median([s.top_black_pct for s in changed_with_image_info]))}%",
                f"Median estimated bottom bar: {_fmt(statistics.median([s.bottom_black_pct for s in changed_with_image_info]))}%",
                f"Median estimated left bar: {_fmt(statistics.median([s.left_black_pct for s in changed_with_image_info]))}%",
                f"Median estimated right bar: {_fmt(statistics.median([s.right_black_pct for s in changed_with_image_info]))}%",
                f"Median estimated content aspect ratio after border removal: "
                f"{_fmt(statistics.median(content_ars) if content_ars else math.nan, 3)}",
            ]
        )
    else:
        lines.append("No decoded changed-frame geometry was available.")

    errors = [s.error for s in samples if s.error]
    lines.extend(
        [
            "",
            "Interpretation",
            "--------------",
            interpretation,
        ]
    )

    if event_subscription_supported:
        if frame_change_rate >= 3.0 and event_rate >= frame_change_rate * 0.7:
            lines.append(
                "MediaPropertiesChanged fires at a rate comparable to frame changes; an "
                "event-assisted path may be worth testing."
            )
        elif frame_change_rate >= 3.0:
            lines.append(
                "MediaPropertiesChanged is materially slower than thumbnail changes; "
                "polling would likely still be required to discover most frames."
            )

    if Image is None:
        lines.append(
            "Install/use Pillow before drawing conclusions about actual pixel-frame cadence: "
            "raw encoded bytes can theoretically change without decoded pixels changing."
        )

    if errors:
        lines.extend(
            [
                "",
                f"Errors: {len(errors)} sample(s) failed.",
                "First five:",
                *[f"  - {message}" for message in errors[:5]],
            ]
        )

    lines.extend(
        [
            "",
            "Important limitation",
            "--------------------",
            "GSMTC does not promise that Thumbnail is a video stream. This probe only measures "
            "Spotify/Windows behavior observed on this machine during this run.",
            "",
        ]
    )

    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    if sys.platform != "win32":
        print("ERROR: This probe only works on Windows.")
        return 2

    if MediaManager is None or DataReader is None:
        print("ERROR: pywinrt GSMTC support could not be imported.")
        print(f"Import error: {WINRT_IMPORT_ERROR!r}")
        print(
            "Expected packages: winrt-runtime, winrt-Windows.Media.Control, "
            "winrt-Windows.Storage.Streams"
        )
        return 2

    script_dir = Path(__file__).resolve().parent
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = script_dir / "tmp" / f"gsm_tc_video_probe_{stamp}"
    frames_dir = out_dir / "frames"
    out_dir.mkdir(parents=True, exist_ok=False)
    frames_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "probe.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("gsm_tc_probe")

    log.info(
        "Starting GSMTC probe duration=%.2fs poll_ceiling=%.2fHz Pillow=%s",
        args.seconds,
        args.poll_hz,
        Image is not None,
    )

    manager = await MediaManager.request_async()
    if manager is None:
        raise RuntimeError("GSMTC SessionManager.request_async() returned None")

    session, source_id, spotify_matched, session_ids = _choose_session(manager)
    log.info("Enumerated sessions: %s", session_ids)
    log.info(
        "Selected session source=%r spotify_match=%s playing=%s",
        source_id,
        spotify_matched,
        _is_playing(session),
    )

    if not spotify_matched:
        log.warning(
            "No Spotify-labelled GSMTC session found; probing the current session instead."
        )

    event_records: list[EventRecord] = []
    event_lock = threading.Lock()
    start_mono = time.perf_counter()

    def on_media_properties_changed(_sender: Any, _args: Any) -> None:
        now_ms = (time.perf_counter() - start_mono) * 1000.0
        with event_lock:
            event_records.append(
                EventRecord(
                    index=len(event_records),
                    t_ms=now_ms,
                    event="MediaPropertiesChanged",
                )
            )

    event_supported, unsubscribe = _subscribe_media_properties_changed(
        session,
        on_media_properties_changed,
    )
    log.info("MediaPropertiesChanged subscription supported=%s", event_supported)

    samples: list[Sample] = []
    representative_frames: list[tuple[float, bytes, str, str]] = []

    last_raw_hash = ""
    last_fingerprint = ""
    last_analysis = ("", 0, 0, "", 0.0, 0.0, 0.0, 0.0, 0.0)

    interval = 1.0 / args.poll_hz
    next_deadline = start_mono
    stop_at = start_mono + args.seconds

    save_spacing = (
        args.seconds / max(1, args.save_frames - 1)
        if args.save_frames > 1
        else args.seconds
    )
    next_save_at = 0.0

    try:
        index = 0
        while True:
            now = time.perf_counter()
            if now >= stop_at:
                break

            if now < next_deadline:
                await asyncio.sleep(next_deadline - now)

            sample_start = time.perf_counter()
            t_ms = (sample_start - start_mono) * 1000.0
            error = ""
            title = ""
            artist = ""
            data = b""

            try:
                props = await session.try_get_media_properties_async()
                if props is None:
                    raise RuntimeError("TryGetMediaPropertiesAsync returned None")
                title = str(getattr(props, "title", "") or "")
                artist = str(getattr(props, "artist", "") or "")
                data = await _read_thumbnail(props)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"

            request_done = time.perf_counter()
            request_ms = (request_done - sample_start) * 1000.0

            raw_hash = hashlib.sha256(data).hexdigest() if data else ""
            raw_changed = bool(raw_hash and raw_hash != last_raw_hash)
            analysis_ms = 0.0

            if raw_hash and raw_hash == last_raw_hash:
                analysis = last_analysis
            elif data and Image is not None:
                analyze_start = time.perf_counter()
                try:
                    analysis = _analyze_image(data)
                except Exception as exc:
                    log.warning("Image analysis failed at sample=%d: %s", index, exc)
                    analysis = ("", 0, 0, "", 0.0, 0.0, 0.0, 0.0, 0.0)
                analysis_ms = (time.perf_counter() - analyze_start) * 1000.0
                last_analysis = analysis
            else:
                analysis = ("", 0, 0, "", 0.0, 0.0, 0.0, 0.0, 0.0)
                last_analysis = analysis

            (
                pixel_hash,
                width,
                height,
                image_format,
                top_black,
                bottom_black,
                left_black,
                right_black,
                content_ar,
            ) = analysis

            fingerprint = pixel_hash or raw_hash
            frame_changed = bool(fingerprint and fingerprint != last_fingerprint)

            with event_lock:
                event_count = len(event_records)

            samples.append(
                Sample(
                    index=index,
                    t_ms=t_ms,
                    request_ms=request_ms,
                    analysis_ms=analysis_ms,
                    thumbnail_bytes=len(data),
                    raw_sha256=raw_hash,
                    pixel_sha256=pixel_hash,
                    raw_changed=raw_changed,
                    frame_changed=frame_changed,
                    width=width,
                    height=height,
                    image_format=image_format,
                    top_black_pct=top_black,
                    bottom_black_pct=bottom_black,
                    left_black_pct=left_black,
                    right_black_pct=right_black,
                    content_aspect_ratio=content_ar,
                    media_event_count=event_count,
                    title=title,
                    artist=artist,
                    error=error,
                )
            )

            if (
                frame_changed
                and data
                and len(representative_frames) < args.save_frames
                and (t_ms / 1000.0) + 1e-9 >= next_save_at
            ):
                representative_frames.append(
                    (t_ms, data, image_format, fingerprint)
                )
                next_save_at += save_spacing

            if raw_hash:
                last_raw_hash = raw_hash
            if fingerprint:
                last_fingerprint = fingerprint

            index += 1
            next_deadline += interval

            # If a WinRT call itself was slower than the requested cadence, do
            # not queue a catch-up burst. Resume from "now" and measure the
            # sustainable sequential rate.
            now_after = time.perf_counter()
            if next_deadline < now_after - interval:
                next_deadline = now_after

    finally:
        unsubscribe()

    actual_elapsed = time.perf_counter() - start_mono

    with event_lock:
        events = list(event_records)

    # Save only a handful of evidence frames, after timing-sensitive sampling.
    for i, (t_ms, data, image_format, fingerprint) in enumerate(representative_frames):
        ext = _image_extension(data, image_format)
        frame_path = frames_dir / (
            f"frame_{i:02d}_{t_ms:09.1f}ms_{fingerprint[:12]}{ext}"
        )
        frame_path.write_bytes(data)

    _write_csv(
        out_dir / "samples.csv",
        samples,
        list(Sample.__dataclass_fields__.keys()),
    )
    _write_csv(
        out_dir / "events.csv",
        events,
        list(EventRecord.__dataclass_fields__.keys()),
    )

    report = _build_report(
        args=args,
        source_id=source_id,
        spotify_matched=spotify_matched,
        session_ids=session_ids,
        samples=samples,
        events=events,
        event_subscription_supported=event_supported,
        actual_elapsed=actual_elapsed,
        representative_count=len(representative_frames),
    )
    (out_dir / "report.txt").write_text(report, encoding="utf-8")

    print()
    print(report)
    print(f"Output folder: {out_dir}")
    print()

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure Spotify GSMTC thumbnail/frame cadence for a short video session."
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=15.0,
        help="Probe duration in seconds (default: 15).",
    )
    parser.add_argument(
        "--poll-hz",
        type=float,
        default=60.0,
        help="Maximum sequential GSMTC poll rate (default: 60 Hz).",
    )
    parser.add_argument(
        "--save-frames",
        type=int,
        default=8,
        help="Maximum representative changed frames to save (default: 8).",
    )
    args = parser.parse_args()

    if not (1.0 <= args.seconds <= 120.0):
        parser.error("--seconds must be between 1 and 120")
    if not (1.0 <= args.poll_hz <= 240.0):
        parser.error("--poll-hz must be between 1 and 240")
    if not (0 <= args.save_frames <= 50):
        parser.error("--save-frames must be between 0 and 50")

    return args


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nProbe interrupted.")
        return 130
    except Exception as exc:
        print(f"\nFATAL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

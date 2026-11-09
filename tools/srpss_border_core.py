"""SRPSS Border Studio core: frame-preserving animated WebP conversion.

Requires Pillow >= 11. No GUI imports. Uses WebP's ANMF millisecond timestamps
rather than relying on Pillow's often-zero per-frame .info['duration'].
"""

from __future__ import annotations

import io
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageStat, ImageChops, features

SUPPORTED_SUFFIXES = {".webp", ".png", ".gif", ".jpg", ".jpeg"}
BORDER_PADDING = 2
BORDER_WIDTH = 2
BORDER_RADIUS = 3
MAX_SOURCE_BYTES = 350_000_000
MAX_ESTIMATED_RGBA_BYTES = 1_500_000_000


class AssetError(Exception):
    """Raised for unsafe, invalid, or unpreservable input/output."""


class Cancelled(AssetError):
    pass


@dataclass(frozen=True)
class Settings:
    scale_percent: int = 90
    min_scale_percent: int = 60
    scale_step_percent: int = 5
    preferred_quality: int = 96
    minimum_quality: int = 90
    max_bytes: int = 10_000_000   # GitHub decimal MB
    replace_existing_border: bool = True
    prefer_quality_over_pixels: bool = True
    strict_visual_check: bool = True
    make_zip: bool = True
    # If set, preserve this format only for single still inputs. Animation => WebP.
    still_format: str = "PNG"

    def validate(self):
        if not (10 <= self.min_scale_percent <= self.scale_percent <= 100):
            raise AssetError("Scale settings must satisfy 10 <= minimum <= starting <= 100.")
        if not (1 <= self.scale_step_percent <= 25):
            raise AssetError("Scale step must be between 1% and 25%.")
        if not (50 <= self.minimum_quality <= self.preferred_quality <= 100):
            raise AssetError("Quality settings must satisfy 50 <= minimum <= preferred <= 100.")
        if not (100_000 <= self.max_bytes <= 500_000_000):
            raise AssetError("Size cap outside supported range.")
        if self.still_format not in ("PNG", "WEBP"):
            raise AssetError("Still format must be PNG or WEBP.")


@dataclass(frozen=True)
class SlideshowSettings:
    enabled: bool = False
    hold_ms: int = 2000
    fade_ms: int = 400
    fps: int = 24
    loop_back_to_first: bool = True

    def validate(self):
        if not (0 <= self.hold_ms <= 120_000):
            raise AssetError("Slideshow hold duration must be between 0 and 120000 ms.")
        if not (0 <= self.fade_ms <= 60_000):
            raise AssetError("Slideshow crossfade duration must be between 0 and 60000 ms.")
        if not (1 <= self.fps <= 60):
            raise AssetError("Slideshow FPS must be between 1 and 60.")
        if self.enabled and self.hold_ms == 0 and self.fade_ms == 0:
            raise AssetError("Slideshow mode needs a non-zero hold or fade duration.")


@dataclass(frozen=True)
class SourceInfo:
    name: str
    width: int
    height: int
    frame_count: int
    durations_ms: tuple[int, ...]
    loop: int
    bytes_size: int
    source_format: str
    border_present: bool
    icc_profile: bytes | None = None
    payload: bytes = b""  # internal only; not included in JSON report

    @property
    def duration_ms(self):
        return sum(self.durations_ms)

    def summary(self):
        return {
            "name": self.name,
            "source_size_bytes": self.bytes_size,
            "source_format": self.source_format,
            "size": [self.width, self.height],
            "frame_count": self.frame_count,
            "duration_ms": self.duration_ms,
            "frame_durations_ms": list(self.durations_ms),
            "loop": self.loop,
            "existing_srpss_border_detected": self.border_present,
            "icc_profile_preserved": bool(self.icc_profile),
        }


def _u24(buf: bytes) -> int:
    return int.from_bytes(buf, "little")


def _riff_chunks(data: bytes):
    """Yield (4-char chunk id, payload start, payload length), with bounds checks."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise AssetError("This isn't a RIFF WebP file.")
    declared = int.from_bytes(data[4:8], "little") + 8
    if declared > len(data):
        raise AssetError("Truncated WebP RIFF container.")
    end = declared
    offset = 12
    while offset < end:
        if offset + 8 > end:
            raise AssetError("Truncated WebP chunk header.")
        tag = data[offset:offset + 4]
        length = int.from_bytes(data[offset + 4:offset + 8], "little")
        begin = offset + 8
        if begin + length > end:
            raise AssetError("Truncated WebP chunk payload.")
        yield tag, begin, length
        offset = begin + length + (length & 1)
    if offset != end:
        raise AssetError("Malformed WebP chunk padding.")


def webp_timeline(data: bytes) -> tuple[list[int], int]:
    """Parse exact WebP animation durations and loop, per WebP RIFF ANMF spec."""
    durations: list[int] = []
    loop = 0
    found_anim = False
    for tag, pos, size in _riff_chunks(data):
        if tag == b"ANIM":
            if size < 6:
                raise AssetError("Malformed ANIM chunk.")
            found_anim = True
            loop = int.from_bytes(data[pos + 4: pos + 6], "little")
        elif tag == b"ANMF":
            if size < 16:
                raise AssetError("Malformed ANMF chunk.")
            durations.append(_u24(data[pos + 12:pos + 15]))
    if bool(durations) != found_anim:
        raise AssetError("Animated WebP is missing ANIM/ANMF information.")
    return durations, loop


def patch_webp_timeline(data: bytes, durations: list[int], loop: int) -> bytes:
    """Repair metadata only, leaving every encoded image payload untouched."""
    positions = []
    loop_pos = None
    for tag, pos, size in _riff_chunks(data):
        if tag == b"ANMF":
            positions.append(pos + 12)
        elif tag == b"ANIM":
            loop_pos = pos + 4
    if len(positions) != len(durations) or loop_pos is None:
        raise AssetError("Cannot repair animation metadata: frame count mismatch.")
    if any(d < 0 or d > 0xFFFFFF for d in durations):
        raise AssetError("Frame duration exceeds WebP 24-bit range.")
    if not 0 <= loop <= 0xFFFF:
        raise AssetError("Loop count exceeds WebP range.")
    result = bytearray(data)
    for pos, duration in zip(positions, durations):
        result[pos:pos + 3] = duration.to_bytes(3, "little")
    result[loop_pos:loop_pos + 2] = loop.to_bytes(2, "little")
    return bytes(result)


def _load_input(path: Path) -> tuple[str, bytes]:
    if not path.is_file():
        raise AssetError(f"File doesn't exist: {path}")
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            candidates = [member for member in archive.infolist()
                          if not member.is_dir() and Path(member.filename).suffix.lower() in SUPPORTED_SUFFIXES]
            if len(candidates) != 1:
                raise AssetError(f"ZIP needs exactly one supported image, found {len(candidates)}.")
            member = candidates[0]
            if member.file_size > MAX_SOURCE_BYTES:
                raise AssetError("Image inside ZIP is larger than safety limit (350 MB).")
            with archive.open(member) as stream:
                data = stream.read(MAX_SOURCE_BYTES + 1)
            if len(data) > MAX_SOURCE_BYTES:
                raise AssetError("ZIP image decompressed beyond safety limit.")
            return Path(member.filename).name, data
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise AssetError("Supported: WebP, PNG, GIF, JPEG, or ZIP holding one of those.")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise AssetError("Input file is larger than 350 MB safety limit.")
    return path.name, path.read_bytes()


def _has_srpss_border(image: Image.Image) -> bool:
    """Recognize default 2 transparent + 2 black on a few sampled edges."""
    rgba = image.convert("RGBA")
    w, h = rgba.size
    if w < 24 or h < 24:
        return False
    p = rgba.load()
    probes_x = (w // 4, w // 2, w * 3 // 4)
    probes_y = (h // 4, h // 2, h * 3 // 4)
    for x in probes_x:
        for y in (0, 1, h - 2, h - 1):
            if p[x, y][3] != 0:
                return False
        for y in (2, 3, h - 4, h - 3):
            rgb = p[x, y]
            if rgb[3] < 245 or max(rgb[:3]) > 35:
                return False
    for y in probes_y:
        for x in (0, 1, w - 2, w - 1):
            if p[x, y][3] != 0:
                return False
        for x in (2, 3, w - 4, w - 3):
            rgb = p[x, y]
            if rgb[3] < 245 or max(rgb[:3]) > 35:
                return False
    return True



def inspect_source(path: str | Path) -> SourceInfo:
    path = Path(path)
    name, data = _load_input(path)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()  # decode first frame now to fail early on corrupt input
        count = getattr(image, "n_frames", 1)
        fmt = image.format or "UNKNOWN"
        if count < 1:
            raise AssetError("Image contains no frames.")
        if fmt == "WEBP" and count > 1:
            durations, loop = webp_timeline(data)
            if len(durations) != count:
                raise AssetError(f"WebP RIFF frame count {len(durations)} != decoder count {count}.")
        elif count > 1 and fmt == "GIF":
            durations = []
            for index in range(count):
                image.seek(index)
                durations.append(int(image.info.get("duration", 0)))
            # Netscape GIF loop count means *additional repeats* (1 => 2 plays),
            # whereas WebP ANIM loop count means *total plays* (1 => 1 play).
            gif_repeats = image.info.get("loop", None)
            loop = 1 if gif_repeats is None else (0 if gif_repeats == 0 else int(gif_repeats) + 1)
            if loop > 0xFFFF:
                raise AssetError("GIF repeat count exceeds WebP's 16-bit loop field.")
        elif count > 1:
            raise AssetError(f"Animated {fmt} not supported for strict frame preservation; use animated WebP/GIF.")
        else:
            durations, loop = [], 0
        if any(d < 11 or d > 0xFFFFFF for d in durations):
            raise AssetError("Animation has zero, very short (<11ms), or invalid frame durations. "
                             "Playback differs across browsers; refusing an untrustworthy conversion.")
        # a 10,000 frame image is almost certainly not a sane GitHub showcase
        if count > 10_000:
            raise AssetError("More than 10,000 frames is outside the tool's safety limit.")
        image.seek(0)
        bordered = _has_srpss_border(image)
        profile = image.info.get("icc_profile")
        return SourceInfo(name, image.width, image.height, count, tuple(durations), loop,
                          len(data), fmt, bordered, profile, data)
    except (OSError, SyntaxError, ValueError) as exc:
        raise AssetError(f"Could not decode image: {exc}") from exc


def _new_border(content: Image.Image) -> Image.Image:
    content = content.convert("RGBA")
    w, h = content.size
    padding, stroke, radius = BORDER_PADDING, BORDER_WIDTH, BORDER_RADIUS
    result = Image.new("RGBA", (w + 2*(padding+stroke), h + 2*(padding+stroke)), (0,0,0,0))
    draw = ImageDraw.Draw(result)
    draw.rounded_rectangle((padding,padding,result.width-padding-1,result.height-padding-1),
                           radius=radius, fill=(0,0,0,255))
    clip_mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(clip_mask).rounded_rectangle((0,0,w-1,h-1), radius=max(0, radius-stroke), fill=255)
    # Multiplying existing alpha by corner mask preserves transparent content.
    alpha = content.getchannel("A")
    from PIL import ImageChops as Chops
    content.putalpha(Chops.multiply(alpha, clip_mask))
    result.alpha_composite(content, (padding+stroke,padding+stroke))
    return result


def _iter_qualities(pref: int, floor: int):
    qualities = [pref]
    quality = pref - 2
    while quality >= floor:
        qualities.append(quality)
        quality -= 2
    if qualities[-1] != floor:
        qualities.append(floor)
    return qualities


def _check_border_alpha(fr: Image.Image, *, max_outline_rgb: int = 38):
    """Validate full perimeter, not just the four corner pixels."""
    w, h = fr.size
    a = fr.getchannel("A")
    for rect in ((0,0,w,2), (0,h-2,w,h), (0,0,2,h), (w-2,0,w,h)):
        if a.crop(rect).getextrema() != (0,0):
            raise AssetError("Border verification failed: outer 2px margin contains nontransparent pixels.")
    rgb = fr.convert("RGBA")
    for x,y in ((w//2,2),(w//2,3),(w//2,h-3),(w//2,h-4),
                (2,h//2),(3,h//2),(w-3,h//2),(w-4,h//2)):
        r,g,b,alpha = rgb.getpixel((x,y))
        if alpha < 245 or max(r,g,b) > max_outline_rgb:
            raise AssetError("Border verification failed: black outline damaged after encoding.")


def _unique_path(base: Path) -> Path:
    if not base.exists():
        return base
    for number in range(2,1000):
        candidate = base.with_name(f"{base.stem}_v{number}{base.suffix}")
        if not candidate.exists():
            return candidate
    raise AssetError("Too many similarly named outputs in destination folder.")


def _safe_name(source_name: str) -> str:
    base = Path(source_name).stem
    return re.sub(r"[^\w .()-]+", "_", base).strip(" .")[:90] or "SRPSS_Image"


def _prepare_content_frame(info: SourceInfo, target_size: tuple[int, int], replace_existing_border: bool) -> Image.Image:
    trim = 4 if info.border_present and replace_existing_border else 0
    with Image.open(io.BytesIO(info.payload)) as image:
        image.seek(0)
        frame = image.convert("RGBA")
    if trim:
        if frame.width <= trim * 2 or frame.height <= trim * 2:
            raise AssetError(f"{info.name}: source too small after removing an existing border.")
        frame = frame.crop((trim, trim, frame.width - trim, frame.height - trim))
    target_w, target_h = target_size
    if target_w < 4 or target_h < 4:
        raise AssetError("Normalization target became too small.")
    if frame.size != target_size:
        # Preserve aspect ratio. Normalize every input into the first source's trimmed canvas.
        scale = min(target_w / frame.width, target_h / frame.height)
        resized_w = max(1, round(frame.width * scale))
        resized_h = max(1, round(frame.height * scale))
        resized = frame.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
        normalized = Image.new("RGBA", target_size, (0, 0, 0, 0))
        offset = ((target_w - resized_w) // 2, (target_h - resized_h) // 2)
        normalized.alpha_composite(resized, offset)
        frame = normalized
    return frame


def _duration_sequence(total_ms: int, fps: int) -> list[int]:
    if total_ms <= 0:
        return []
    frame_count = max(1, round(total_ms * fps / 1000))
    base = total_ms // frame_count
    remainder = total_ms % frame_count
    durations = [base] * frame_count
    for i in range(remainder):
        durations[i] += 1
    return durations


def _sample_indices(total: int) -> set[int]:
    if total <= 0:
        return set()
    return {0, total // 4, total // 2, (total * 3) // 4, total - 1}


def _stream_slideshow_webp(
    infos: list[SourceInfo],
    target_size: tuple[int, int],
    slide_cfg: SlideshowSettings,
    quality: int,
    output_path: Path,
    notify: Callable[[str], None],
    cancelled: Callable[[], bool],
) -> tuple[int, int]:
    """Encode frames as they are produced, never retaining a frame-sequence in RAM.

    Pillow's public save_all API expands append_images into a list before encoding.
    Pillow 12's own WebP encoder is incremental; use its low-level animation entry
    point to preserve bounded memory, with a deliberately small compatibility seam.
    A held still is ONE frame with a long timestamp, not FPS * hold seconds copies.
    """
    try:
        from PIL import _webp
    except ImportError as exc:
        raise AssetError("Pillow's animated WebP encoder is unavailable.") from exc
    if not hasattr(_webp, "WebPAnimEncoder"):
        raise AssetError("This Pillow version lacks the incremental WebP encoder; use the SRPSS-pinned Pillow 12.0.0.")

    hold_ms = slide_cfg.hold_ms
    fade_durations = _duration_sequence(slide_cfg.fade_ms, slide_cfg.fps)
    transitions = len(infos) if slide_cfg.loop_back_to_first else len(infos) - 1
    expected_frame_count = len(infos) * int(hold_ms > 0) + transitions * len(fade_durations)
    if expected_frame_count < 2:
        raise AssetError("Slideshow requires at least two displayed frames; increase hold/crossfade duration.")
    if expected_frame_count > 10_000:
        raise AssetError("Slideshow exceeds 10,000 encoded frames. Reduce FPS or fade duration.")
    if fade_durations and min(fade_durations) < 11:
        raise AssetError("Fade FPS/duration produces frames shorter than 11 ms; lower FPS or increase fade duration.")

    loop_count = 0 if slide_cfg.loop_back_to_first else 1
    encoder = _webp.WebPAnimEncoder(
        (target_size[0] + 8, target_size[1] + 8),
        0, loop_count, False, 3, 5, False, False,
    )
    timestamp = 0
    submitted = 0
    current = None
    next_frame = None
    try:
        current = _new_border(_prepare_content_frame(infos[0], target_size, replace_existing_border=True))
        for index, info in enumerate(infos):
            if cancelled():
                raise Cancelled("Slideshow cancelled; no output published.")
            if hold_ms > 0:
                encoder.add(current.getim(), timestamp, False, quality, 100, 2)
                timestamp += hold_ms
                submitted += 1
            has_next = index + 1 < len(infos) or slide_cfg.loop_back_to_first
            if has_next:
                next_index = (index + 1) % len(infos)
                next_frame = _new_border(
                    _prepare_content_frame(infos[next_index], target_size, replace_existing_border=True)
                )
                for j, duration in enumerate(fade_durations, 1):
                    if cancelled():
                        raise Cancelled("Slideshow cancelled; no output published.")
                    # Intermediate transition colors only, not fake duplicate hold frames.
                    frame = Image.blend(current, next_frame, j / (len(fade_durations) + 1))
                    try:
                        encoder.add(frame.getim(), timestamp, False, quality, 100, 2)
                    finally:
                        frame.close()
                    timestamp += duration
                    submitted += 1
                current.close()
                current, next_frame = next_frame, None
            notify(f"  Encoded image {index + 1}/{len(infos)} ({submitted} source frames, {timestamp / 1000:.2f}s)")
        if cancelled():
            raise Cancelled("Slideshow cancelled; no output published.")
        # Pillow's public WebP writer uses the same libwebp flush/assemble sequence.
        encoder.add(None, timestamp, False, quality, 100, 0)
        data = encoder.assemble(infos[0].icc_profile or b"", b"", b"")
        if not data:
            raise AssetError("Incremental WebP encoder returned no animation.")
        output_path.write_bytes(data)
        return timestamp, submitted
    finally:
        if current is not None:
            current.close()
        if next_frame is not None:
            next_frame.close()


def _validate_slideshow(
    output_path: Path,
    infos: list[SourceInfo],
    content_size: tuple[int, int],
    slide_cfg: SlideshowSettings,
    intended_ms: int,
    strict_visual_check: bool,
    cancelled: Callable[[], bool],
) -> tuple[list[int], int, list[float]]:
    """Validate timeline, every frame's border and selected real still/fade images."""
    from bisect import bisect_right

    durations, loop = webp_timeline(output_path.read_bytes())
    expected_loop = 0 if slide_cfg.loop_back_to_first else 1
    if len(durations) < 2:
        raise AssetError("WebP animation collapsed to a single frame; the selected stills show no distinct motion.")
    if sum(durations) != intended_ms:
        raise AssetError(f"WebP duration mismatch: expected {intended_ms} ms, got {sum(durations)} ms.")
    if loop != expected_loop:
        raise AssetError(f"WebP loop mismatch: expected {expected_loop}, got {loop}.")
    if any(d < 11 or d > 0xFFFFFF for d in durations):
        raise AssetError("Encoded WebP contains an invalid or too-short frame duration.")

    checkpoints: list[tuple[int, int, int | None, float]] = []
    elapsed = 0
    transitions = len(infos) if slide_cfg.loop_back_to_first else len(infos) - 1
    fade_durations = _duration_sequence(slide_cfg.fade_ms, slide_cfg.fps)
    for index in range(len(infos)):
        if slide_cfg.hold_ms:
            checkpoints.append((elapsed + slide_cfg.hold_ms // 2, index, None, 0.0))
            elapsed += slide_cfg.hold_ms
        if index < transitions and fade_durations:
            middle = len(fade_durations) // 2
            checkpoints.append((elapsed + sum(fade_durations[:middle]) + fade_durations[middle] // 2,
                                index, (index + 1) % len(infos), (middle + 1) / (len(fade_durations) + 1)))
            elapsed += sum(fade_durations)
    if elapsed != intended_ms:
        raise AssetError("Internal slideshow timeline calculation mismatch.")

    ends = []
    cursor = 0
    for duration in durations:
        cursor += duration
        ends.append(cursor)
    selected: dict[int, list[tuple[int, int | None, float]]] = {}
    if strict_visual_check:
        for at_ms, first, second, alpha in checkpoints:
            frame_index = bisect_right(ends, at_ms)
            if frame_index >= len(durations):
                frame_index = len(durations) - 1
            selected.setdefault(frame_index, []).append((first, second, alpha))

    visual_diffs: list[float] = []
    with Image.open(output_path) as verify:
        expected_size = (content_size[0] + 8, content_size[1] + 8)
        if verify.size != expected_size:
            raise AssetError(f"WebP dimensions changed unexpectedly: {verify.size} vs {expected_size}.")
        if getattr(verify, "n_frames", 1) != len(durations):
            raise AssetError("WebP decoder and RIFF frame counts disagree.")
        if infos[0].icc_profile and verify.info.get("icc_profile") != infos[0].icc_profile:
            raise AssetError("WebP encoding discarded the first source's ICC profile.")
        for index in range(len(durations)):
            if cancelled():
                raise Cancelled("Slideshow validation cancelled; no output published.")
            verify.seek(index)
            frame = verify.convert("RGBA")
            _check_border_alpha(frame, max_outline_rgb=64)
            for first_index, second_index, alpha in selected.get(index, ()):
                ref_a = _new_border(_prepare_content_frame(infos[first_index], content_size, True))
                if second_index is None:
                    ref = ref_a
                else:
                    ref_b = _new_border(_prepare_content_frame(infos[second_index], content_size, True))
                    ref = Image.blend(ref_a, ref_b, alpha)
                    ref_a.close()
                    ref_b.close()
                try:
                    region = (4, 4, content_size[0] + 4, content_size[1] + 4)
                    black = Image.new("RGBA", (content_size[0], content_size[1]), (0, 0, 0, 255))
                    expected = Image.alpha_composite(black, ref.crop(region)).convert("RGB")
                    actual = Image.alpha_composite(black, frame.crop(region)).convert("RGB")
                    mean = sum(ImageStat.Stat(ImageChops.difference(expected, actual)).mean) / 3
                    visual_diffs.append(round(mean, 3))
                    if mean > 15:
                        raise AssetError(f"Slideshow source/fade visual check failed at encoded frame {index}: "
                                         f"mean RGB difference {mean:.1f}.")
                finally:
                    ref.close()
                    black.close()
                    expected.close()
                    actual.close()
            frame.close()
    return durations, loop, visual_diffs


def process_asset(source_path: str | Path, destination: str | Path,
                  settings: Settings | None = None,
                  notify: Callable[[str], None] | None = None,
                  cancelled: Callable[[], bool] | None = None) -> dict:
    """Create only validated final files, using atomic temporary candidates.

    Animation fidelity has strict priority over size: never drop frames,
    alter timings, change loop count, or return an unchecked artifact.
    """
    cfg = settings or Settings()
    cfg.validate()
    notify = notify or (lambda msg: None)
    cancelled = cancelled or (lambda: False)
    def check_cancel():
        if cancelled():
            raise Cancelled("Processing cancelled; no final output was published.")

    source = inspect_source(source_path)
    animated = source.frame_count > 1
    if (animated or cfg.still_format == "WEBP") and not features.check("webp"):
        raise AssetError("This Pillow build lacks libwebp support.")
    if animated and source.source_format == "GIF" and source.loop != 0:
        notify("Source GIF does not loop forever: preserving original finite loop count.")
    if source.border_present and cfg.replace_existing_border:
        notify("Existing SRPSS border detected: stripping it BEFORE resizing.")
    name_root = _safe_name(source.name)
    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    extension = ".webp" if animated or cfg.still_format == "WEBP" else ".png"
    final_file = _unique_path(dest / f"{name_root}_SRPSS_Bordered{extension}")
    final_zip = final_file.with_suffix(".zip")
    # Need no collisions with previous ZIPs either.
    while final_zip.exists():
        final_file = _unique_path(final_file.with_name(final_file.stem + "_v2" + extension))
        final_zip = final_file.with_suffix(".zip")

    trim = 4 if source.border_present and cfg.replace_existing_border else 0
    content_w = source.width - 2*trim
    content_h = source.height - 2*trim
    if content_w < 4 or content_h < 4:
        raise AssetError("Source too small after removing an existing border.")
    logs = []
    # Use lower res on the encoded file, but NEVER resize a previously drawn border.
    preferred_scales = list(range(cfg.scale_percent, cfg.min_scale_percent - 1, -cfg.scale_step_percent))
    if preferred_scales[-1] != cfg.min_scale_percent:
        preferred_scales.append(cfg.min_scale_percent)

    with tempfile.TemporaryDirectory(prefix="srpss_border_") as td:
        candidate = Path(td) / ("candidate" + extension)
        skip_scales_above = cfg.scale_percent
        for scale in preferred_scales:
            check_cancel()
            if scale > skip_scales_above:
                notify(f"Skipping {scale}% after file-size projection (image quality priority).")
                continue
            width = max(4, round(content_w * scale / 100))
            height = max(4, round(content_h * scale / 100))
            predicted = (width+8)*(height+8)*4*source.frame_count
            if predicted > MAX_ESTIMATED_RGBA_BYTES:
                notify(f"Skipping {scale}%: estimated decoded frames exceed 1.5 GB safety cap.")
                logs.append({"scale_percent":scale,"skipped":"memory safety"})
                continue
            notify(f"Preparing {source.frame_count} frames at {width}×{height} content ({scale}%).")
            image = Image.open(io.BytesIO(source.payload))
            frames = []
            first_frame_before_encode = None
            for idx in range(source.frame_count):
                check_cancel()
                image.seek(idx)
                fr = image.convert("RGBA")
                if trim:
                    fr = fr.crop((trim,trim,fr.width-trim,fr.height-trim))
                if (fr.width,fr.height) != (width,height):
                    fr = fr.resize((width,height), Image.Resampling.LANCZOS)
                result = _new_border(fr)
                if idx == 0:
                    first_frame_before_encode = result.copy()
                frames.append(result)
                if idx and idx % 80 == 0:
                    notify(f"  Rendered {idx}/{source.frame_count} frames...")
            image.close()
            check_cancel()
            if not animated and cfg.still_format == "PNG":
                png_kwargs = {"format":"PNG", "optimize":True}
                if source.icc_profile:
                    png_kwargs["icc_profile"] = source.icc_profile
                frames[0].save(candidate, **png_kwargs)
                candidate_size = candidate.stat().st_size
                notify(f"Lossless PNG: {candidate_size:,} bytes.")
                if candidate_size > cfg.max_bytes:
                    logs.append({"scale_percent": scale, "quality": "lossless PNG", "bytes": candidate_size})
                    continue
                selected_quality = "lossless PNG"
                break

            # Try highest-quality settings first; only lower quality inside the supplied floor.
            selected_quality = None
            if cfg.prefer_quality_over_pixels and scale > cfg.min_scale_percent:
                candidates = [cfg.preferred_quality]
            else:
                candidates = _iter_qualities(cfg.preferred_quality, cfg.minimum_quality)
            most_recent_encoded_size = None
            for quality in candidates:
                check_cancel()
                notify(f"  Encoding quality {quality}, scale {scale}%...")
                args = {"format":"WEBP", "quality":quality, "method":3, "exact":True}
                if source.icc_profile:
                    args["icc_profile"] = source.icc_profile
                if animated:
                    args.update(save_all=True, append_images=frames[1:], duration=list(source.durations_ms),
                                loop=source.loop, minimize_size=False)
                frames[0].save(candidate, **args)
                length = candidate.stat().st_size
                most_recent_encoded_size = length
                notify(f"  q{quality}: {length:,} bytes")
                logs.append({"scale_percent": scale, "quality": quality, "bytes": length})
                if length <= cfg.max_bytes:
                    selected_quality = quality
                    break
            if selected_quality is not None:
                # Files that fit must also pass checks. A timing/frame failure is not a reason
                # to silently try a different resolution, so validation happens AFTER selection.
                break
            if cfg.prefer_quality_over_pixels and most_recent_encoded_size and scale > cfg.min_scale_percent:
                # Coarse projection saves dozens of expensive animated encodes. It may
                # slightly undershoot optimal resolution, but it never lowers quality.
                projected = int(scale * (cfg.max_bytes / most_recent_encoded_size) ** 0.5 * 0.98)
                projected = max(cfg.min_scale_percent, min(scale - cfg.scale_step_percent, projected))
                # Snap projection upward to the nearest available step so we can
                # refine toward the highest feasible dimensions.
                permitted = [s for s in preferred_scales if s <= projected]
                skip_scales_above = max(permitted) if permitted else cfg.min_scale_percent
                notify(f"  Too large at q{cfg.preferred_quality}; next projected scale: {skip_scales_above}%.")
            del frames
        else:
            raise AssetError("No result fits within the byte cap above your minimum scale/quality. "
                             "Lower minimum scale, adjust quality floor, or shorten the animation. "
                             "Source file unchanged.")

        check_cancel()
        encoded_bytes = candidate.read_bytes()
        if animated:
            durations, loop = webp_timeline(encoded_bytes)
            if len(durations) != source.frame_count:
                raise AssetError(f"Encoder changed frame count: {source.frame_count} → {len(durations)}. "
                                 "Output rejected. Some encoders merge identical frames; this tool does not silently permit it.")
            if durations != list(source.durations_ms) or loop != source.loop:
                notify("  Encoder changed timestamp metadata: repairing timestamps WITHOUT re-encoding frames.")
                encoded_bytes = patch_webp_timeline(encoded_bytes, list(source.durations_ms), source.loop)
                candidate.write_bytes(encoded_bytes)
            confirm_durations, confirm_loop = webp_timeline(candidate.read_bytes())
            if confirm_durations != list(source.durations_ms) or confirm_loop != source.loop:
                raise AssetError("Frame timing repair failed; output rejected.")

        if candidate.stat().st_size > cfg.max_bytes:
            raise AssetError("Validated output crossed the size limit; output rejected.")
        verify = Image.open(candidate)
        if verify.size != (width + 8, height + 8):
            raise AssetError("Output resolution changed unexpectedly.")
        if getattr(verify,"n_frames",1) != source.frame_count:
            raise AssetError("Decoder frame count mismatch in final result.")
        if source.icc_profile and verify.info.get("icc_profile") != source.icc_profile:
            raise AssetError("ICC color profile could not be retained; output rejected.")
        # Sample RGB is deliberately validated in the FIRST frame and across representative
        # later frames. Border alpha is verified in EVERY frame.
        sampled_indices = {0, source.frame_count//2, source.frame_count-1}
        visual_diffs = []
        for idx in range(source.frame_count):
            check_cancel()
            verify.seek(idx)
            decoded = verify.convert("RGBA")
            _check_border_alpha(decoded)
            if idx in sampled_indices and cfg.strict_visual_check:
                if idx == 0:
                    reference = first_frame_before_encode
                else:
                    original = Image.open(io.BytesIO(source.payload))
                    original.seek(idx)
                    reference_content = original.convert("RGBA")
                    if trim:
                        reference_content = reference_content.crop((trim,trim,reference_content.width-trim,reference_content.height-trim))
                    if reference_content.size != (width,height):
                        reference_content = reference_content.resize((width,height), Image.Resampling.LANCZOS)
                    reference = _new_border(reference_content)
                    original.close()
                region = (4,4, width+4,height+4)
                # Composite transparent pixels over black before comparing RGB;
                # otherwise invisible RGB values can give false visual failures.
                reference_region = reference.crop(region)
                actual_region = decoded.crop(region)
                black = Image.new("RGBA", reference_region.size, (0,0,0,255))
                reference_rgb = Image.alpha_composite(black, reference_region).convert("RGB")
                actual_rgb = Image.alpha_composite(black, actual_region).convert("RGB")
                stats = ImageStat.Stat(ImageChops.difference(reference_rgb, actual_rgb))
                mean_abs = sum(stats.mean)/3
                visual_diffs.append(round(mean_abs,3))
                if mean_abs > 15:
                    raise AssetError(f"Visible image-difference check failed (frame {idx}, mean error {mean_abs:.1f}). "
                                     "Output rejected; try a higher quality or smaller dimensions.")
        verify.close()
        check_cancel()
        # Commit validated artifact in destination, not partial or failed intermediate.
        # exclusive creation avoids accidentally replacing existing user files.
        with final_file.open("xb") as stream:
            stream.write(candidate.read_bytes())
        report = {
            "tool": "SRPSS Border Studio",
            "source": {k:v for k,v in source.summary().items() if k != "frame_durations_ms"},
            "output_file": final_file.name,
            "output_size_bytes": final_file.stat().st_size,
            "content_size": [width,height],
            "final_size": [width+8,height+8],
            "scale_percent": scale,
            "quality": selected_quality,
            "frame_count": source.frame_count,
            "duration_ms": source.duration_ms,
            "loop": source.loop,
            "border": {"padding_px":2,"black_outline_px":2,"radius_px":3},
            "mean_absolute_rgb_diffs": visual_diffs,
            "attempts": logs,
            "validation": "PASS: strict count, timings, loop, transparent perimeter and black outline",
        }
        if cfg.make_zip:
            try:
                with zipfile.ZipFile(final_zip,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
                    archive.write(final_file,arcname=final_file.name)
                    archive.writestr("PROCESSING_REPORT.json",json.dumps(report,indent=2))
                with zipfile.ZipFile(final_zip) as archive:
                    if archive.testzip() is not None:
                        raise AssetError("Output ZIP CRC verification failed.")
            except Exception:
                final_zip.unlink(missing_ok=True)
                final_file.unlink(missing_ok=True)
                raise
            report["zip_path"] = str(final_zip)
        report["output_path"] = str(final_file)
        notify("PASS: frame count, timing, looping, border and ZIP verified.")
        return report


def process_slideshow(source_paths: list[str | Path], destination: str | Path,
                      settings: Settings | None = None,
                      slideshow: SlideshowSettings | None = None,
                      notify: Callable[[str], None] | None = None,
                      cancelled: Callable[[], bool] | None = None) -> dict:
    """Create one bounded-memory crossfade WebP from an ordered queue of stills."""
    cfg = settings or Settings()
    slide_cfg = slideshow or SlideshowSettings(enabled=True)
    cfg.validate()
    slide_cfg.validate()
    if not slide_cfg.enabled:
        raise AssetError("Slideshow settings must be enabled for slideshow processing.")
    if not features.check("webp"):
        raise AssetError("This Pillow build lacks libwebp support.")
    notify = notify or (lambda _message: None)
    cancelled = cancelled or (lambda: False)

    def check_cancel():
        if cancelled():
            raise Cancelled("Slideshow cancelled; no final output was published.")

    if len(source_paths) < 2:
        raise AssetError("Slideshow mode requires at least two still images.")
    infos = []
    for path in source_paths:
        check_cancel()
        info = inspect_source(path)
        if info.frame_count != 1:
            raise AssetError(f"{info.name}: slideshow mode accepts still images only.")
        infos.append(info)
    notify(f"Queue slideshow: {len(infos)} still images → one streaming animated WebP.")

    trim = 4 if infos[0].border_present else 0
    base_size = (infos[0].width - trim * 2, infos[0].height - trim * 2)
    if min(base_size) < 4:
        raise AssetError("First image is too small after border removal.")
    fade_durations = _duration_sequence(slide_cfg.fade_ms, slide_cfg.fps)
    transition_count = len(infos) if slide_cfg.loop_back_to_first else len(infos) - 1
    intended_ms = slide_cfg.hold_ms * len(infos) + slide_cfg.fade_ms * transition_count
    logical_frames = len(infos) * int(slide_cfg.hold_ms > 0) + len(fade_durations) * transition_count
    notify(f"  Timeline: {intended_ms / 1000:.3f}s, {logical_frames} generated frames "
           f"({len(infos)} holds use one frame each).")

    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    name_root = _safe_name(f"{Path(infos[0].name).stem}_Queue_Crossfade")
    final_file = _unique_path(dest / f"{name_root}_SRPSS_Bordered.webp")
    final_zip = final_file.with_suffix(".zip")
    while final_zip.exists():
        final_file = _unique_path(final_file.with_name(final_file.stem + "_v2" + final_file.suffix))
        final_zip = final_file.with_suffix(".zip")

    scales = list(range(cfg.min_scale_percent, cfg.scale_percent + 1, cfg.scale_step_percent))
    if scales[-1] != cfg.scale_percent:
        scales.append(cfg.scale_percent)
    scales = sorted(set(scales))
    attempts: list[dict] = []
    selected_quality: int | None = None
    selected_scale: int | None = None
    content_size: tuple[int, int] | None = None
    durations: list[int] = []
    loop_count = 0
    visual_diffs: list[float] = []

    with tempfile.TemporaryDirectory(prefix="srpss_slideshow_") as td:
        candidate = Path(td) / "candidate.webp"
        chosen = Path(td) / "chosen.webp"
        chosen_size: tuple[int, int] | None = None

        def encode_attempt(scale: int, quality: int) -> bool:
            nonlocal selected_scale, selected_quality, chosen_size
            check_cancel()
            size = tuple(max(4, round(length * scale / 100)) for length in base_size)
            # Allow a handful of large working surfaces, not FPS * hold seconds
            # independent buffers. The encoder streams compressed frames.
            working_bytes = (size[0] + 8) * (size[1] + 8) * 4 * 12
            if working_bytes > MAX_ESTIMATED_RGBA_BYTES:
                notify(f"Skipping {scale}%: single working-set estimate exceeds 1.5 GB.")
                attempts.append({"scale_percent": scale, "skipped": "working set safety"})
                return False
            notify(f"Streaming {size[0]}×{size[1]} slideshow ({scale}%, q{quality})...")
            actual_ms, submitted = _stream_slideshow_webp(
                infos, size, slide_cfg, quality, candidate, notify, cancelled
            )
            actual_bytes = candidate.stat().st_size
            attempts.append({"scale_percent": scale, "quality": quality, "bytes": actual_bytes,
                             "submitted_frames": submitted})
            notify(f"  q{quality}: {actual_bytes:,} bytes (budget {cfg.max_bytes:,})")
            if actual_ms != intended_ms:
                raise AssetError("Slideshow generator changed the intended timeline.")
            if actual_bytes > cfg.max_bytes:
                return False
            # Keep the best fitting candidate while subsequent attempts probe.
            # Don't publish or expose anything until all verification completes.
            import shutil
            shutil.copyfile(candidate, chosen)
            selected_quality, selected_scale, chosen_size = quality, scale, size
            return True

        if cfg.prefer_quality_over_pixels:
            # A large batch of 4K stills can take minutes to encode at 90%, only
            # to discover it cannot possibly meet a 10 MB cap. Probe the minimum
            # permitted size first, then binary-search UP for the largest fitting
            # dimensions at the preferred quality. Decrease quality only if even
            # the permitted minimum cannot fit at that quality.
            smallest = scales[0]
            if encode_attempt(smallest, cfg.preferred_quality):
                low, high = 1, len(scales) - 1
                while low <= high:
                    middle = (low + high) // 2
                    if encode_attempt(scales[middle], cfg.preferred_quality):
                        low = middle + 1
                    else:
                        high = middle - 1
            else:
                for quality in _iter_qualities(cfg.preferred_quality, cfg.minimum_quality)[1:]:
                    if encode_attempt(smallest, quality):
                        break
        else:
            # For users who prefer pixels over quality, try largest to smallest;
            # each permitted resolution receives quality attempts before shrinking.
            for scale in reversed(scales):
                for quality in _iter_qualities(cfg.preferred_quality, cfg.minimum_quality):
                    if encode_attempt(scale, quality):
                        break
                if selected_quality is not None:
                    break

        if selected_quality is None or chosen_size is None or selected_scale is None:
            raise AssetError("The animation exceeds your size cap at the minimum allowed scale/quality. "
                             "Lower Minimum size or Minimum WebP quality, or increase Max file size. "
                             "All frames were encoded incrementally; this was a file-size limit, not RAM exhaustion.")
        check_cancel()
        durations, loop_count, visual_diffs = _validate_slideshow(
            chosen, infos, chosen_size, slide_cfg, intended_ms, cfg.strict_visual_check, cancelled
        )
        content_size = chosen_size
        with final_file.open("xb") as out:
            out.write(chosen.read_bytes())

    report = {
        "tool": "SRPSS Border Studio", "mode": "queue_slideshow",
        "sources": [{"name": info.name, "source_size_bytes": info.bytes_size,
                     "source_format": info.source_format, "size": [info.width, info.height],
                     "existing_srpss_border_detected": info.border_present}
                    for info in infos],
        "normalization": {
            "strategy": "aspect-ratio preserving centered fit into the first image's trimmed content size",
            "source_order": [info.name for info in infos],
        },
        "output_file": final_file.name, "output_size_bytes": final_file.stat().st_size,
        "content_size": list(content_size), "final_size": [content_size[0] + 8, content_size[1] + 8],
        "scale_percent": selected_scale, "quality": selected_quality,
        "logical_generated_frame_count": logical_frames, "frame_count": len(durations),
        "duration_ms": sum(durations), "frame_durations_ms": durations, "loop": loop_count,
        "slideshow": {"hold_ms_per_image": slide_cfg.hold_ms, "crossfade_ms": slide_cfg.fade_ms,
                      "fps": slide_cfg.fps, "loop_back_to_first": slide_cfg.loop_back_to_first},
        "border": {"padding_px": 2, "black_outline_px": 2, "radius_px": 3},
        "mean_absolute_rgb_diffs": visual_diffs, "attempts": attempts,
        "validation": "PASS: total timing, loop, ordered still/fade samples, every frame border, size",
    }
    if cfg.make_zip:
        try:
            with zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
                archive.write(final_file, arcname=final_file.name)
                archive.writestr("PROCESSING_REPORT.json", json.dumps(report, indent=2))
            with zipfile.ZipFile(final_zip) as archive:
                if archive.testzip() is not None:
                    raise AssetError("Output ZIP CRC verification failed.")
        except Exception:
            final_zip.unlink(missing_ok=True)
            final_file.unlink(missing_ok=True)
            raise
        report["zip_path"] = str(final_zip)
    report["output_path"] = str(final_file)
    notify("PASS: streaming slideshow, ordered frames, timing, border and ZIP verified.")
    return report

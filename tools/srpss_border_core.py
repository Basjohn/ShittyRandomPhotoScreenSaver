"""SRPSS Border Studio core: frame-preserving animated WebP conversion.

Requires Pillow >= 11. No GUI imports. Uses WebP's ANMF millisecond timestamps
rather than relying on Pillow's often-zero per-frame .info['duration'].
"""

from __future__ import annotations

import io
import json
import math
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


def _check_border_alpha(fr: Image.Image):
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
        if alpha < 245 or max(r,g,b) > 38:
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


def _collapse_identical_frames(frames: list[Image.Image], durations: list[int]) -> tuple[list[Image.Image], list[int]]:
    if len(frames) != len(durations):
        raise AssetError("Internal frame/duration mismatch while collapsing slideshow frames.")
    if not frames:
        return [], []
    collapsed_frames = [frames[0].copy()]
    collapsed_durations = [durations[0]]
    previous_bytes = frames[0].tobytes()
    previous_size = frames[0].size
    for frame, duration in zip(frames[1:], durations[1:]):
        current_bytes = frame.tobytes()
        if frame.size == previous_size and current_bytes == previous_bytes:
            collapsed_durations[-1] += duration
        else:
            collapsed_frames.append(frame.copy())
            collapsed_durations.append(duration)
            previous_bytes = current_bytes
            previous_size = frame.size
    return collapsed_frames, collapsed_durations


def _compose_slideshow_bordered_frames(
    infos: list[SourceInfo],
    slideshow: SlideshowSettings,
    notify: Callable[[str], None],
    cancelled: Callable[[], bool],
) -> tuple[list[Image.Image], list[int], tuple[int, int], list[dict], bytes | None]:
    if len(infos) < 2:
        raise AssetError("Slideshow mode requires at least two still images.")
    for info in infos:
        if info.frame_count != 1:
            raise AssetError(f"{info.name}: slideshow mode accepts still images only.")

    trim0 = 4 if infos[0].border_present else 0
    target_size = (infos[0].width - 2 * trim0, infos[0].height - 2 * trim0)
    if target_size[0] < 4 or target_size[1] < 4:
        raise AssetError("First slideshow image becomes too small after border removal.")
    notify(f"Slideshow normalization target: {target_size[0]}×{target_size[1]} content from first source.")

    normalized_contents: list[Image.Image] = []
    normalization_report: list[dict] = []
    icc_profile = infos[0].icc_profile
    for idx, info in enumerate(infos, 1):
        if cancelled():
            raise Cancelled("Processing cancelled; no final output was published.")
        content = _prepare_content_frame(info, target_size, replace_existing_border=True)
        normalized_contents.append(content)
        normalization_report.append({
            "source": info.name,
            "input_size": [info.width, info.height],
            "trimmed_border": bool(info.border_present),
            "normalized_content_size": [content.width, content.height],
        })
        notify(f"  Normalized {idx}/{len(infos)}: {info.name}")

    bordered_stills = [_new_border(content) for content in normalized_contents]
    hold_durations = _duration_sequence(slideshow.hold_ms, slideshow.fps)
    fade_durations = _duration_sequence(slideshow.fade_ms, slideshow.fps)
    if not hold_durations and not fade_durations:
        raise AssetError("Slideshow mode needs a non-zero hold or fade duration.")

    frames: list[Image.Image] = []
    durations: list[int] = []
    total_transitions = len(bordered_stills) if slideshow.loop_back_to_first else len(bordered_stills) - 1

    for i, base_frame in enumerate(bordered_stills):
        if cancelled():
            raise Cancelled("Processing cancelled; no final output was published.")
        for duration in hold_durations:
            frames.append(base_frame.copy())
            durations.append(duration)
        if total_transitions <= 0:
            continue
        if i == len(bordered_stills) - 1 and not slideshow.loop_back_to_first:
            continue
        next_frame = bordered_stills[(i + 1) % len(bordered_stills)]
        fade_count = len(fade_durations)
        if fade_count:
            for fade_index, duration in enumerate(fade_durations, 1):
                blend = fade_index / (fade_count + 1)
                frames.append(Image.blend(base_frame, next_frame, blend))
                durations.append(duration)

    if not frames:
        raise AssetError("Slideshow assembly produced zero frames.")
    if len(frames) > 10_000:
        raise AssetError("Slideshow assembly would exceed the 10,000 frame safety limit.")
    return frames, durations, target_size, normalization_report, icc_profile


def _verify_visual_samples(reference_frames: list[Image.Image], encoded_path: Path, strict_visual_check: bool):
    verify = Image.open(encoded_path)
    sampled_indices = _sample_indices(len(reference_frames))
    visual_diffs: list[float] = []
    for idx, reference in enumerate(reference_frames):
        verify.seek(idx)
        decoded = verify.convert("RGBA")
        _check_border_alpha(decoded)
        if strict_visual_check and idx in sampled_indices:
            region = (4, 4, reference.width - 4, reference.height - 4)
            reference_region = reference.crop(region)
            actual_region = decoded.crop(region)
            black = Image.new("RGBA", reference_region.size, (0, 0, 0, 255))
            reference_rgb = Image.alpha_composite(black, reference_region).convert("RGB")
            actual_rgb = Image.alpha_composite(black, actual_region).convert("RGB")
            stats = ImageStat.Stat(ImageChops.difference(reference_rgb, actual_rgb))
            mean_abs = sum(stats.mean) / 3
            visual_diffs.append(round(mean_abs, 3))
            if mean_abs > 15:
                verify.close()
                raise AssetError(f"Visible image-difference check failed (frame {idx}, mean error {mean_abs:.1f}). "
                                 "Output rejected; try a higher quality or smaller dimensions.")
    verify.close()
    return visual_diffs


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
    """Build one bordered animated WebP from a queue of still images."""
    cfg = settings or Settings()
    slide_cfg = slideshow or SlideshowSettings(enabled=True)
    cfg.validate()
    slide_cfg.validate()
    if not slide_cfg.enabled:
        raise AssetError("Slideshow settings must be enabled for slideshow processing.")
    if not features.check("webp"):
        raise AssetError("This Pillow build lacks libwebp support.")
    notify = notify or (lambda msg: None)
    cancelled = cancelled or (lambda: False)

    def check_cancel():
        if cancelled():
            raise Cancelled("Processing cancelled; no final output was published.")

    if len(source_paths) < 2:
        raise AssetError("Slideshow mode requires at least two sources.")

    infos = [inspect_source(path) for path in source_paths]
    for info in infos:
        if info.frame_count != 1:
            raise AssetError(f"{info.name}: slideshow mode only accepts still images.")
    notify(f"Queue slideshow mode: {len(infos)} still images → one animated WebP.")

    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    name_root = _safe_name(f"{Path(infos[0].name).stem}_Queue_Crossfade")
    final_file = _unique_path(dest / f"{name_root}_SRPSS_Bordered.webp")
    final_zip = final_file.with_suffix(".zip")
    while final_zip.exists():
        final_file = _unique_path(final_file.with_name(final_file.stem + "_v2" + final_file.suffix))
        final_zip = final_file.with_suffix(".zip")

    preferred_scales = list(range(cfg.scale_percent, cfg.min_scale_percent - 1, -cfg.scale_step_percent))
    if preferred_scales[-1] != cfg.min_scale_percent:
        preferred_scales.append(cfg.min_scale_percent)

    with tempfile.TemporaryDirectory(prefix="srpss_border_slideshow_") as td:
        candidate = Path(td) / "candidate.webp"
        logs = []
        selected_quality = None
        selected_scale = None
        skip_scales_above = cfg.scale_percent
        final_reference_frames: list[Image.Image] | None = None
        final_durations: list[int] | None = None
        final_content_size: tuple[int, int] | None = None
        normalization_report: list[dict] | None = None
        icc_profile: bytes | None = None

        for scale in preferred_scales:
            check_cancel()
            if scale > skip_scales_above:
                notify(f"Skipping {scale}% after file-size projection (image quality priority).")
                continue

            if scale != 100:
                # Temporarily rescale the first source dimensions by wrapping the slideshow assembly.
                # We scale AFTER normalization target selection to preserve queue layout.
                base_trim = 4 if infos[0].border_present else 0
                base_target = (infos[0].width - 2 * base_trim, infos[0].height - 2 * base_trim)
                scaled_target = (max(4, round(base_target[0] * scale / 100)), max(4, round(base_target[1] * scale / 100)))
            else:
                base_trim = 4 if infos[0].border_present else 0
                scaled_target = (infos[0].width - 2 * base_trim, infos[0].height - 2 * base_trim)
            if scaled_target[0] < 4 or scaled_target[1] < 4:
                continue

            predicted_frames = len(_duration_sequence(slide_cfg.hold_ms, slide_cfg.fps)) * len(infos)
            predicted_frames += len(_duration_sequence(slide_cfg.fade_ms, slide_cfg.fps)) * (len(infos) if slide_cfg.loop_back_to_first else len(infos) - 1)
            predicted = (scaled_target[0] + 8) * (scaled_target[1] + 8) * 4 * max(1, predicted_frames)
            if predicted > MAX_ESTIMATED_RGBA_BYTES:
                notify(f"Skipping {scale}%: estimated decoded frames exceed 1.5 GB safety cap.")
                logs.append({"scale_percent": scale, "skipped": "memory safety"})
                continue

            # Build a scaled clone of the info set by temporarily overriding the first-target logic.
            patched_infos: list[SourceInfo] = []
            for idx, info in enumerate(infos):
                if idx == 0:
                    patched_infos.append(SourceInfo(
                        info.name,
                        scaled_target[0] + (4 if info.border_present else 0) * 2,
                        scaled_target[1] + (4 if info.border_present else 0) * 2,
                        info.frame_count,
                        info.durations_ms,
                        info.loop,
                        info.bytes_size,
                        info.source_format,
                        info.border_present,
                        info.icc_profile,
                        info.payload,
                    ))
                else:
                    patched_infos.append(info)

            notify(f"Preparing slideshow at {scaled_target[0]}×{scaled_target[1]} content ({scale}%).")
            frames, durations, content_size, norm_report, icc_profile = _compose_slideshow_bordered_frames(
                patched_infos, slide_cfg, notify, cancelled
            )
            final_frame_size = (content_size[0] + 8, content_size[1] + 8)
            check_cancel()
            if len(frames) != len(durations):
                raise AssetError("Internal slideshow frame/duration mismatch.")

            selected_quality = None
            if cfg.prefer_quality_over_pixels and scale > cfg.min_scale_percent:
                candidates = [cfg.preferred_quality]
            else:
                candidates = _iter_qualities(cfg.preferred_quality, cfg.minimum_quality)
            most_recent_encoded_size = None
            for quality in candidates:
                check_cancel()
                notify(f"  Encoding slideshow quality {quality}, scale {scale}%...")
                args = {
                    "format": "WEBP",
                    "quality": quality,
                    "method": 3,
                    "exact": True,
                    "save_all": True,
                    "append_images": frames[1:],
                    "duration": durations,
                    "loop": 0 if slide_cfg.loop_back_to_first else 1,
                    "minimize_size": False,
                }
                if icc_profile:
                    args["icc_profile"] = icc_profile
                frames[0].save(candidate, **args)
                length = candidate.stat().st_size
                most_recent_encoded_size = length
                notify(f"  q{quality}: {length:,} bytes")
                logs.append({"scale_percent": scale, "quality": quality, "bytes": length})
                if length <= cfg.max_bytes:
                    selected_quality = quality
                    selected_scale = scale
                    final_reference_frames = frames
                    final_durations = durations
                    final_content_size = content_size
                    normalization_report = norm_report
                    break
            if selected_quality is not None:
                break
            if cfg.prefer_quality_over_pixels and most_recent_encoded_size and scale > cfg.min_scale_percent:
                projected = int(scale * (cfg.max_bytes / most_recent_encoded_size) ** 0.5 * 0.98)
                projected = max(cfg.min_scale_percent, min(scale - cfg.scale_step_percent, projected))
                permitted = [s for s in preferred_scales if s <= projected]
                skip_scales_above = max(permitted) if permitted else cfg.min_scale_percent
                notify(f"  Too large at q{cfg.preferred_quality}; next projected scale: {skip_scales_above}%.")
        else:
            raise AssetError("No slideshow result fits within the byte cap above your minimum scale/quality. "
                             "Lower minimum scale, adjust quality floor, or shorten the slideshow.")

        if not final_reference_frames or not final_durations or not final_content_size or normalization_report is None:
            raise AssetError("Slideshow assembly did not produce a publishable candidate.")
        check_cancel()
        collapsed_reference_frames, collapsed_durations = _collapse_identical_frames(final_reference_frames, final_durations)
        encoded_bytes = candidate.read_bytes()
        actual_durations, actual_loop = webp_timeline(encoded_bytes)
        if len(actual_durations) != len(collapsed_durations):
            raise AssetError(f"Encoder changed slideshow frame structure unexpectedly: {len(collapsed_durations)} expected encoded frames, got {len(actual_durations)}. Output rejected.")
        expected_loop = 0 if slide_cfg.loop_back_to_first else 1
        if actual_durations != list(collapsed_durations) or actual_loop != expected_loop:
            notify("  Encoder changed slideshow timestamp metadata: repairing timestamps WITHOUT re-encoding frames.")
            encoded_bytes = patch_webp_timeline(encoded_bytes, list(collapsed_durations), expected_loop)
            candidate.write_bytes(encoded_bytes)
            confirm_durations, confirm_loop = webp_timeline(candidate.read_bytes())
            if confirm_durations != list(collapsed_durations) or confirm_loop != expected_loop:
                raise AssetError("Slideshow frame timing repair failed; output rejected.")
        if candidate.stat().st_size > cfg.max_bytes:
            raise AssetError("Validated slideshow output crossed the size limit; output rejected.")

        verify = Image.open(candidate)
        if verify.size != (final_content_size[0] + 8, final_content_size[1] + 8):
            raise AssetError("Slideshow output resolution changed unexpectedly.")
        if getattr(verify, "n_frames", 1) != len(collapsed_durations):
            raise AssetError("Slideshow decoder frame count mismatch in final result.")
        if icc_profile and verify.info.get("icc_profile") != icc_profile:
            raise AssetError("ICC color profile could not be retained in slideshow output; output rejected.")
        verify.close()
        visual_diffs = _verify_visual_samples(collapsed_reference_frames, candidate, cfg.strict_visual_check)
        check_cancel()

        with final_file.open("xb") as stream:
            stream.write(candidate.read_bytes())
        report = {
            "tool": "SRPSS Border Studio",
            "mode": "queue_slideshow",
            "sources": [
                {
                    "name": info.name,
                    "source_size_bytes": info.bytes_size,
                    "source_format": info.source_format,
                    "size": [info.width, info.height],
                    "existing_srpss_border_detected": info.border_present,
                }
                for info in infos
            ],
            "normalization": {
                "strategy": "normalize every source into the first source's trimmed content size using aspect-ratio-preserving fit",
                "per_source": normalization_report,
            },
            "output_file": final_file.name,
            "output_size_bytes": final_file.stat().st_size,
            "content_size": [final_content_size[0], final_content_size[1]],
            "final_size": [final_content_size[0] + 8, final_content_size[1] + 8],
            "scale_percent": selected_scale,
            "quality": selected_quality,
            "logical_generated_frame_count": len(final_durations),
            "frame_count": len(collapsed_durations),
            "duration_ms": sum(collapsed_durations),
            "frame_durations_ms": list(collapsed_durations),
            "loop": expected_loop,
            "slideshow": {
                "hold_ms_per_image": slide_cfg.hold_ms,
                "crossfade_ms": slide_cfg.fade_ms,
                "fps": slide_cfg.fps,
                "loop_back_to_first": slide_cfg.loop_back_to_first,
            },
            "border": {"padding_px": 2, "black_outline_px": 2, "radius_px": 3},
            "mean_absolute_rgb_diffs": visual_diffs,
            "attempts": logs,
            "validation": "PASS: strict count, timings, loop, transparent perimeter and black outline",
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
        notify("PASS: slideshow frame count, timing, looping, border and ZIP verified.")
        return report

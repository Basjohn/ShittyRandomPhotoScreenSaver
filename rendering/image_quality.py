"""Pure-Pillow wallpaper decoding and quality-resampling mechanics.

This module has no settings, worker, Qt, cache, or process ownership.  Callers
pass the already-resolved filter and display mode so foreground and speculative
workers can use the same opaque-pixel contract without a second implementation.
"""
from __future__ import annotations

from typing import Any


RESAMPLE_FILTERS = frozenset(("smooth", "hamming", "lanczos"))
SHARPEN_THRESHOLD = 0.5


def opaque_rgb(image: Any) -> Any:
    """Remove alpha work once, compositing authored transparency over black."""
    from PIL import Image

    if image.has_transparency_data:
        rgba = image.convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", rgba.size, (0, 0, 0, 255)), rgba).convert("RGB")
    return image if image.mode == "RGB" else image.convert("RGB")


def decode_image(path: str) -> Any:
    """Decode one wallpaper into an owned opaque RGB Pillow image.

    Wallpaper presentation is opaque.  Transparency is composited over black
    before resampling so both workers produce the same pixels for FILL crops
    and FIT/SHRINK bars, while ordinary opaque sources never pay for an RGBA
    resize.
    """
    from PIL import Image

    with Image.open(path) as opened:
        opened.load()
        image = opaque_rgb(opened)
        # load() owns the pixels; the context closes the file, not that storage.
        # Copying a fully decoded RGB image here would duplicate the whole source.
        return image


def process_image(
    image: Any,
    target: tuple[int, int],
    mode: str,
    resample_filter: str,
    sharpen: bool,
) -> Any:
    """Return the exact opaque RGB canvas for one resolved display request."""
    from PIL import Image, ImageFilter

    if resample_filter not in RESAMPLE_FILTERS:
        raise ValueError(f"Unknown resolved resample filter: {resample_filter!r}")
    target_width, target_height = target
    if target_width <= 0 or target_height <= 0:
        raise ValueError(f"Invalid target size: {target_width}x{target_height}")
    if mode not in {"fill", "fit", "shrink"}:
        raise ValueError(f"Unknown resolved display mode: {mode!r}")

    original_size = image.size
    scaled_size = calculate_scale_size(original_size, target, mode)
    result = image
    crop = None
    if scaled_size != original_size:
        resample = {
            "smooth": Image.Resampling.BILINEAR,
            "hamming": Image.Resampling.HAMMING,
            "lanczos": Image.Resampling.LANCZOS,
        }[resample_filter]
        output_size = scaled_size
        box = None
        if mode == "fill" and scaled_size != target:
            # Sample only the visible destination, using the original virtual
            # scale and integer centre crop. Keep a filter halo for sharpening;
            # a tall portrait must not allocate an enormous offscreen resize.
            halo = 8 if sharpen else 0
            left = (scaled_size[0] - target_width) // 2
            top = (scaled_size[1] - target_height) // 2
            x0, y0 = max(0, left - halo), max(0, top - halo)
            x1, y1 = min(scaled_size[0], left + target_width + halo), min(scaled_size[1], top + target_height + halo)
            output_size = (x1 - x0, y1 - y0)
            sx, sy = original_size[0] / scaled_size[0], original_size[1] / scaled_size[1]
            box = (x0 * sx, y0 * sy, min(original_size[0], x1 * sx), min(original_size[1], y1 * sy))
            crop = (left - x0, top - y0, left - x0 + target_width, top - y0 + target_height)
        # Pillow's integer reduction stage avoids filtering the entire large
        # source at severe downscale ratios. 3.0 retains fine resampling quality.
        result = image.resize(output_size, resample, box=box, reducing_gap=3.0)
        if sharpen:
            scale_factor = min(
                scaled_size[0] / original_size[0],
                scaled_size[1] / original_size[1],
            )
            if scale_factor < SHARPEN_THRESHOLD:
                result = result.filter(
                    ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)
                )
            elif scale_factor < 1.0:
                result = result.filter(ImageFilter.SHARPEN)
    if crop is not None:
        return result.crop(crop)
    return apply_display_mode(result, target, mode)


def calculate_scale_size(
    source: tuple[int, int],
    target: tuple[int, int],
    mode: str,
) -> tuple[int, int]:
    """Preserve worker scale/crop geometry, including one-pixel extreme aspects."""
    src_w, src_h = source
    target_width, target_height = target
    if src_w == 0 or src_h == 0:
        return target

    src_ratio = src_w / src_h
    target_ratio = target_width / target_height
    if mode == "fill":
        if src_ratio > target_ratio:
            new_height = target_height
            new_width = int(new_height * src_ratio)
        else:
            new_width = target_width
            new_height = int(new_width / src_ratio)
        return max(new_width, target_width), max(new_height, target_height)
    if mode == "fit":
        if src_ratio > target_ratio:
            new_width = target_width
            new_height = int(new_width / src_ratio)
        else:
            new_height = target_height
            new_width = int(new_height * src_ratio)
        return max(1, new_width), max(1, new_height)
    if mode == "shrink":
        if src_w <= target_width and src_h <= target_height:
            return source
        if src_ratio > target_ratio:
            new_width = target_width
            new_height = int(new_width / src_ratio)
        else:
            new_height = target_height
            new_width = int(new_height * src_ratio)
        return max(1, new_width), max(1, new_height)
    return source


def apply_display_mode(image: Any, target: tuple[int, int], mode: str) -> Any:
    """Centre-crop FILL or black-pad FIT/SHRINK into an exact RGB canvas."""
    from PIL import Image

    target_width, target_height = target
    image_width, image_height = image.size
    if mode == "fill":
        if image_width > target_width or image_height > target_height:
            left = (image_width - target_width) // 2
            top = (image_height - target_height) // 2
            return image.crop((left, top, left + target_width, top + target_height))
        return image
    if mode in {"fit", "shrink"}:
        if (image_width, image_height) == target:
            return image
        result = Image.new("RGB", target, (0, 0, 0))
        result.paste(
            image,
            ((target_width - image_width) // 2, (target_height - image_height) // 2),
        )
        return result
    return image

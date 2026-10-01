"""Image-quality work bounds and pixel oracles independent of worker transport."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageFilter

from rendering.image_quality import decode_image, process_image


def _pattern(size):
    width, height = size
    y, x = np.indices((height, width))
    return Image.fromarray(np.stack(((x * 13 + y * 7) % 256, (x * 3 + y * 11) % 256,
                                     ((x // 5 + y // 7) % 2) * 255), axis=2).astype(np.uint8))


@pytest.mark.parametrize("filter_name", ("smooth", "hamming", "lanczos"))
@pytest.mark.parametrize("sharpen", (False, True))
@pytest.mark.parametrize("source_size", ((120, 400), (800, 200)))
def test_fill_visible_sampling_matches_full_resize_and_crop(filter_name, sharpen, source_size):
    source = _pattern(source_size)
    target = (192, 108)
    scale = max(target[0] / source.width, target[1] / source.height)
    scaled_size = (max(target[0], int(source.width * scale)), max(target[1], int(source.height * scale)))
    kernel = {"smooth": Image.Resampling.BILINEAR, "hamming": Image.Resampling.HAMMING,
              "lanczos": Image.Resampling.LANCZOS}[filter_name]
    reference = source.resize(scaled_size, kernel)
    if sharpen and scale < 1:
        reference = reference.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)
                                     if scale < .5 else ImageFilter.SHARPEN)
    left, top = (scaled_size[0] - target[0]) // 2, (scaled_size[1] - target[1]) // 2
    reference = reference.crop((left, top, left + target[0], top + target[1]))
    actual = process_image(source, target, "fill", filter_name, sharpen)
    delta = np.abs(np.asarray(actual).astype(int) - np.asarray(reference).astype(int))
    # Fractional ROI coordinates can move the two separable rounding stages (amplified by
    # sharpening), but never move the crop or manufacture a dark boundary.
    assert delta.max() <= (4 if sharpen else 2)
    assert delta.mean() < .1


def test_tall_fill_never_resizes_the_discarded_offscreen_canvas(monkeypatch):
    source = _pattern((20, 2000))
    actual_resize = Image.Image.resize
    sizes = []

    def observe(image, size, *args, **kwargs):
        sizes.append(size)
        return actual_resize(image, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", observe)
    actual = process_image(source, (320, 180), "fill", "lanczos", True)
    assert actual.size == (320, 180)
    # Formerly 320x32000, despite only 180 output rows being visible.
    assert sizes and all(w <= 336 and h <= 196 for w, h in sizes)


def test_large_reduction_retains_full_lanczos_detail():
    source = _pattern((1600, 960))
    expected = source.resize((160, 96), Image.Resampling.LANCZOS)
    actual = process_image(source, (160, 96), "fit", "lanczos", False)
    delta = np.asarray(actual).astype(float) - np.asarray(expected).astype(float)
    assert np.mean(np.abs(delta)) < 1.0
    assert np.sqrt(np.mean(delta ** 2)) < 1.5


@pytest.mark.parametrize("alpha", (False, True))
def test_decode_owns_rgb_pixels_and_black_composites_alpha(tmp_path, alpha):
    path = tmp_path / "source.png"
    Image.new("RGBA" if alpha else "RGB", (31, 17), (100, 60, 20, 128) if alpha else (100, 60, 20)).save(path)
    source = decode_image(str(path))
    path.unlink()  # The decoded image retains no file handle or lazy file reads.
    assert source.mode == "RGB"
    assert source.getpixel((0, 0)) == ((50, 30, 10) if alpha else (100, 60, 20))


@pytest.mark.parametrize("mode", ("fit", "shrink", "fill"))
def test_extreme_aspects_never_request_zero_dimension(mode):
    assert process_image(Image.new("RGB", (1, 400)), (80, 2), mode, "hamming", False).size == (80, 2)


def test_filter_choice_is_visible_and_invalid_filter_is_not_substituted():
    source = _pattern((320, 180))
    outputs = [process_image(source, (97, 59), "fit", name, False).tobytes()
               for name in ("smooth", "hamming", "lanczos")]
    assert len(set(outputs)) == 3
    with pytest.raises(ValueError, match="Unknown resolved resample filter"):
        process_image(source, (97, 59), "fit", "hq2x", False)

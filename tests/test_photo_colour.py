"""Shared photo colours: the dominant colour is the majority (first-seen bin on a tie), the accent
is the vivid colour even where grey dominates, and a glow colour is luminous."""
from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from rendering.gl_programs.photo_colour import photo_accent_colour, photo_dominant_colour, photo_glow_colour


def _rgba(image: Image.Image) -> tuple[bytes, tuple[int, int], int]:
    return image.convert("RGBA").tobytes(), image.size, image.size[0] * 4


def test_the_dominant_colour_is_the_majority_and_a_tie_goes_to_the_first_bin_seen():
    image = Image.new("RGB", (128, 72), (0, 0, 255))
    ImageDraw.Draw(image).rectangle((0, 0, 63, 71), fill=(255, 0, 0))     # left half red, right half blue
    assert photo_dominant_colour(*_rgba(image)) == pytest.approx((1.0, 0.0, 0.0))
    ImageDraw.Draw(image).rectangle((0, 0, 95, 71), fill=(0, 255, 0))
    assert photo_dominant_colour(*_rgba(image)) == pytest.approx((0.0, 1.0, 0.0))


def test_the_accent_is_the_vivid_colour_even_when_grey_dominates():
    image = Image.new("RGB", (320, 180), (110, 110, 110))
    ImageDraw.Draw(image).rectangle((0, 0, 80, 180), fill=(200, 40, 30))
    dominant, accent = photo_dominant_colour(*_rgba(image)), photo_accent_colour(*_rgba(image))
    assert max(dominant) - min(dominant) < 0.05
    assert accent[0] > 0.6 and accent[1] < 0.3 and accent[2] < 0.3
    assert photo_accent_colour(*_rgba(Image.new("RGB", (64, 36), (90, 90, 90)))) == pytest.approx((90 / 255,) * 3)


def test_a_glow_colour_is_luminous_and_grey_glows_cool_white():
    glow = photo_glow_colour((0.6, 0.15, 0.1))
    assert max(glow) == pytest.approx(1.0) and glow[0] > glow[1] and glow[0] > glow[2]
    assert photo_glow_colour((0.5, 0.5, 0.5)) == pytest.approx((0.9, 0.94, 1.0))

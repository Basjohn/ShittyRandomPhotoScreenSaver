"""Pure pixel analysis only: native DWM acceptance remains a separate desktop gate."""
import numpy as np
import pytest

from tools.settings_native_corners import analyze_pixels, cover_transform, matching_wallpaper_reference


def test_corner_analysis_tracks_all_four_physical_origins_and_fractional_radius():
    width, height, pad = 83, 47, 7
    delta = np.zeros((height + pad*2, width + pad*2), dtype=np.int16)
    for x, y in ((pad, pad), (pad+width-1, pad), (pad, pad+height-1),
                 (pad+width-1, pad+height-1)):
        delta[y, x] = 71
    # A changed interior pixel must not be reported as corner residue.
    delta[pad+4, pad+4] = 200
    result = analyze_pixels(delta, width, height, pad, 5.25)
    assert set(result["corners"]) == {"top_left", "top_right", "bottom_left", "bottom_right"}
    for corner in result["corners"].values():
        assert corner == {"outside_rounded_pixels_changed_gt3": 1, "maximum_outside_delta": 71}
    assert result["changed_pixels_outside_hwnd_gt3"] == 0
    assert result["capture_perimeter_delta"] == 0


def test_native_shadow_and_capture_perimeter_are_separate_from_corner_residue():
    width, height, pad = 61, 39, 9
    delta = np.zeros((height + pad*2, width + pad*2), dtype=np.int16)
    delta[pad-1, pad+width//2] = 18
    delta[0, pad+width//2] = 6
    # The threshold ignores at most three channel levels, but preserves the raw maximum.
    delta[pad, pad] = 3
    result = analyze_pixels(delta, width, height, pad, 4.75)
    assert result["changed_pixels_outside_hwnd_gt3"] == 2
    assert result["capture_perimeter_delta"] == 6
    assert result["corners"]["top_left"] == {
        "outside_rounded_pixels_changed_gt3": 0, "maximum_outside_delta": 3}
    assert all(corner["outside_rounded_pixels_changed_gt3"] == 0 for corner in result["corners"].values())


def test_wallpaper_cover_keeps_aspect_and_crops_equally_on_both_sides():
    for source, target in (((320, 180), (240, 240)), ((180, 320), (400, 200)), ((384, 216), (256, 144))):
        result = cover_transform(source, target)
        x, y, width, height = result["source_crop"]
        assert width/height == pytest.approx(target[0]/target[1])
        assert x*2+width == pytest.approx(source[0])
        assert y*2+height == pytest.approx(source[1])
        assert width <= source[0] and height <= source[1]
        assert width*result["scale"] == pytest.approx(target[0])
        assert height*result["scale"] == pytest.approx(target[1])


def test_matching_wallpaper_pixels_use_physical_desktop_origin_for_texture_oracle():
    from PIL import Image

    yy, xx = np.indices((55, 91))
    texture = np.stack(((xx*19+yy*7)%256, (xx*11+yy*23)%256, (xx*3+yy*17)%256), axis=-1).astype(np.uint8)
    desktop = Image.fromarray(texture)
    reference = matching_wallpaper_reference(desktop, (-1188, 89, -1127, 128), (-1200, 80, -1109, 135))
    assert np.array_equal(np.asarray(reference), texture[9:48, 12:73])
    image = np.asarray(reference, dtype=np.int16).copy()
    image[5, 5] += 13
    delta = np.abs(image - np.asarray(reference, dtype=np.int16)).max(2)
    result = analyze_pixels(delta, 51, 29, 5, 4.25)
    assert result["corners"]["top_left"]["outside_rounded_pixels_changed_gt3"] == 1
    assert sum(c["outside_rounded_pixels_changed_gt3"] for c in result["corners"].values()) == 1
    assert result["changed_pixels_outside_hwnd_gt3"] == 0
    with pytest.raises(ValueError):
        matching_wallpaper_reference(desktop, (-1201, 89, -1127, 128), (-1200, 80, -1109, 135))

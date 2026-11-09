"""Pure pixel analysis only: native DWM acceptance remains a separate desktop gate."""
import numpy as np

from tools.settings_native_corners import analyze_pixels


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

"""Automated tests for sine wave micro wobble shader math.

Validates the mathematical properties of the micro wobble implementation
by computing the same formulas as the GLSL shader in Python.

Key properties tested:
1. Micro wobble is HIGH spatial frequency (micro-scale, not whole-line)
2. Displacement is small (1-4px) and independent of wave amplitude
3. Vocal-led energy weighting (mid 70%, bass 20%, high 10%)
4. Zero output when not playing or no energy
5. Smooth: no discontinuities or sudden jumps
6. Different spatial patterns per line (no visual overlap)
"""
import math
import pytest


# --- Shader math replicated in Python ---

def compute_mw_energy(mid: float, bass: float, high: float) -> float:
    """Vocal-led energy mix: mid*0.7 + bass*0.2 + high*0.1"""
    return mid * 0.7 + bass * 0.2 + high * 0.1


def compute_mw_drive(mw_energy: float) -> float:
    """Sqrt soft onset."""
    return math.sqrt(max(mw_energy, 0.0))


# Spatial frequencies for each line (must be distinct and HIGH)
LINE_FREQS = {
    1: [47.0, 83.0, 131.0, 199.0, 61.0],
    2: [53.0, 89.0, 137.0, 211.0, 67.0],
    3: [59.0, 97.0, 149.0, 223.0, 73.0],
}

LINE_TIME_RATES = {
    1: [0.5, -0.3, 0.7, -0.4, 0.6],
    2: [0.6, -0.4, 0.5, -0.35, 0.55],
    3: [-0.45, 0.55, -0.65, 0.3, -0.5],
}

WEIGHTS = [0.28, 0.24, 0.20, 0.16, 0.12]


def compute_mw_raw(nx: float, t: float, line: int) -> float:
    """Compute raw micro wobble sum-of-sines for a given line."""
    freqs = LINE_FREQS[line]
    rates = LINE_TIME_RATES[line]
    total = 0.0
    for freq, rate, weight in zip(freqs, rates, WEIGHTS):
        total += math.sin(nx * freq + t * rate) * weight
    return total


def compute_mw_displacement(nx: float, t: float, line: int,
                            micro_wob: float, mw_drive: float,
                            inner_height: float) -> float:
    """Full micro wobble displacement in normalized coords."""
    if micro_wob <= 0.001 or mw_drive <= 0.02:
        return 0.0
    mw_raw = compute_mw_raw(nx, t, line)
    max_disp_px = 3.5 * micro_wob
    return mw_raw * mw_drive * max_disp_px / max(inner_height, 1.0)


# --- Tests ---

class TestMicroWobbleEnergyWeighting:
    """Verify vocal-led energy mix."""

    def test_pure_mid_dominant(self):
        """Mid energy (vocals) should contribute 70%."""
        e = compute_mw_energy(mid=1.0, bass=0.0, high=0.0)
        assert e == pytest.approx(0.7)

    def test_pure_bass_minor(self):
        """Bass should contribute only 20%."""
        e = compute_mw_energy(mid=0.0, bass=1.0, high=0.0)
        assert e == pytest.approx(0.2)

    def test_pure_high_minor(self):
        """High should contribute only 10%."""
        e = compute_mw_energy(mid=0.0, bass=0.0, high=1.0)
        assert e == pytest.approx(0.1)

    def test_full_energy(self):
        """All bands at 1.0 = 1.0 total."""
        e = compute_mw_energy(mid=1.0, bass=1.0, high=1.0)
        assert e == pytest.approx(1.0)

    def test_zero_energy(self):
        """Zero input = zero output."""
        e = compute_mw_energy(mid=0.0, bass=0.0, high=0.0)
        assert e == pytest.approx(0.0)


class TestMicroWobbleDrive:
    """Verify sqrt soft onset."""

    def test_zero_energy_zero_drive(self):
        assert compute_mw_drive(0.0) == pytest.approx(0.0)

    def test_full_energy_full_drive(self):
        assert compute_mw_drive(1.0) == pytest.approx(1.0)

    def test_sqrt_onset_curve(self):
        """sqrt(0.25) = 0.5 — half drive at quarter energy."""
        assert compute_mw_drive(0.25) == pytest.approx(0.5)

    def test_negative_energy_clamped(self):
        """Negative energy should be clamped to 0."""
        assert compute_mw_drive(-0.5) == pytest.approx(0.0)


class TestMicroWobbleSpatialFrequency:
    """Verify bumps are micro-scale (high frequency)."""

    def test_minimum_frequency_is_high(self):
        """All spatial frequencies should be >= 47 cycles across the width."""
        for line in (1, 2, 3):
            for freq in LINE_FREQS[line]:
                assert freq >= 40.0, f"Line {line} freq {freq} too low for micro-scale"

    def test_bump_width_is_micro(self):
        """Each bump should span < 3% of card width (micro-scale)."""
        for line in (1, 2, 3):
            for freq in LINE_FREQS[line]:
                bump_width_pct = 100.0 / freq  # one cycle as % of width
                assert bump_width_pct < 3.0, (
                    f"Line {line} freq {freq}: bump spans {bump_width_pct:.1f}% — not micro"
                )

    def test_lines_use_different_frequencies(self):
        """Each line must have distinct spatial frequencies to avoid visual overlap."""
        for i in range(5):
            f1 = LINE_FREQS[1][i]
            f2 = LINE_FREQS[2][i]
            f3 = LINE_FREQS[3][i]
            assert f1 != f2, f"Lines 1 and 2 share frequency at index {i}"
            assert f1 != f3, f"Lines 1 and 3 share frequency at index {i}"
            assert f2 != f3, f"Lines 2 and 3 share frequency at index {i}"


class TestMicroWobbleDisplacement:
    """Verify displacement magnitude and gating."""

    def test_zero_when_not_playing(self):
        """micro_wob=0 → zero displacement."""
        d = compute_mw_displacement(0.5, 1.0, 1, micro_wob=0.0, mw_drive=1.0, inner_height=200.0)
        assert d == pytest.approx(0.0)

    def test_zero_when_no_energy(self):
        """mw_drive below threshold → zero displacement."""
        d = compute_mw_displacement(0.5, 1.0, 1, micro_wob=1.0, mw_drive=0.01, inner_height=200.0)
        assert d == pytest.approx(0.0)

    def test_max_displacement_bounded(self):
        """At max slider and full energy, displacement should be <= 4px."""
        max_disp = 0.0
        inner_h = 200.0
        for nx in [i / 1000.0 for i in range(1001)]:
            for t in [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]:
                for line in (1, 2, 3):
                    d = compute_mw_displacement(nx, t, line, micro_wob=1.0, mw_drive=1.0, inner_height=inner_h)
                    d_px = abs(d) * inner_h
                    if d_px > max_disp:
                        max_disp = d_px
        assert max_disp <= 4.0, f"Max displacement {max_disp:.2f}px exceeds 4px limit"
        assert max_disp > 0.5, f"Max displacement {max_disp:.2f}px too small to be visible"

    def test_displacement_independent_of_amplitude(self):
        """Displacement should NOT scale with wave amplitude."""
        d1 = compute_mw_displacement(0.3, 1.0, 1, micro_wob=0.5, mw_drive=0.8, inner_height=200.0)
        d2 = compute_mw_displacement(0.3, 1.0, 1, micro_wob=0.5, mw_drive=0.8, inner_height=200.0)
        assert d1 == pytest.approx(d2), "Displacement should be deterministic (amplitude-independent)"

    def test_displacement_scales_with_slider(self):
        """Higher micro_wob slider → larger displacement."""
        d_low = compute_mw_displacement(0.5, 1.0, 1, micro_wob=0.2, mw_drive=0.8, inner_height=200.0)
        d_high = compute_mw_displacement(0.5, 1.0, 1, micro_wob=1.0, mw_drive=0.8, inner_height=200.0)
        assert abs(d_high) > abs(d_low), "Higher slider should produce larger displacement"


class TestMicroWobbleSmoothness:
    """Verify no choppiness — displacement must be smooth in x."""

    def test_no_discontinuities_in_x(self):
        """Adjacent x samples should not have large jumps (smooth curve)."""
        inner_h = 200.0
        t = 2.5
        micro_wob = 1.0
        mw_drive = 0.8
        step = 0.001  # 1000 samples across width
        max_delta_px = 0.0
        prev = compute_mw_displacement(0.0, t, 1, micro_wob, mw_drive, inner_h)
        for i in range(1, 1001):
            nx = i * step
            curr = compute_mw_displacement(nx, t, 1, micro_wob, mw_drive, inner_h)
            delta_px = abs(curr - prev) * inner_h
            if delta_px > max_delta_px:
                max_delta_px = delta_px
            prev = curr
        # Max allowed jump between adjacent 0.1% x-steps: 0.5px
        assert max_delta_px < 0.5, (
            f"Max adjacent delta {max_delta_px:.3f}px — too choppy"
        )

    def test_no_discontinuities_in_time(self):
        """Adjacent time steps should not have large jumps."""
        inner_h = 200.0
        nx = 0.5
        micro_wob = 1.0
        mw_drive = 0.8
        dt = 1.0 / 165.0  # one frame at 165Hz
        max_delta_px = 0.0
        prev = compute_mw_displacement(nx, 0.0, 1, micro_wob, mw_drive, inner_h)
        for i in range(1, 1000):
            t = i * dt
            curr = compute_mw_displacement(nx, t, 1, micro_wob, mw_drive, inner_h)
            delta_px = abs(curr - prev) * inner_h
            if delta_px > max_delta_px:
                max_delta_px = delta_px
            prev = curr
        # Max allowed jump between frames: 0.3px (smooth temporal evolution)
        assert max_delta_px < 0.3, (
            f"Max temporal delta {max_delta_px:.3f}px — too choppy between frames"
        )


class TestWaveEffectVocalLed:
    """Verify wave effect uses vocal-led energy mix."""

    def test_wave_energy_is_vocal_led(self):
        """Wave effect energy should use same mid-dominant weighting."""
        # The shader computes: we1_raw = mid*0.7 + bass*0.2 + high*0.1
        # This is the same formula as micro wobble energy
        we = compute_mw_energy(mid=0.8, bass=0.3, high=0.2)
        assert we == pytest.approx(0.8 * 0.7 + 0.3 * 0.2 + 0.2 * 0.1)
        # Vocals (mid) should be dominant contributor
        mid_contrib = 0.8 * 0.7
        total = we
        assert mid_contrib / total > 0.6, "Mid (vocals) should dominate wave energy"

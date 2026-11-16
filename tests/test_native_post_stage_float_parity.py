"""Float texture comparison must reject nonfinite evidence before quantization."""
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native" / "core" / "python"))
import post_stage_check as tool


def test_nan_cannot_pass_the_real_comparison():
    a = np.zeros((2, 2, 4))
    b = a.copy()
    a[0, 0, 0] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = tool.judge_texture({"array": a, "format": "rgba16f"}, {"array": b, "format": "rgba16f"},
                                    tool.pt.Tolerance("finite"))
    assert not result["pass"]


@pytest.mark.parametrize("value", (np.nan, np.inf, -np.inf))
@pytest.mark.parametrize("side", ("candidate", "reference"))
def test_nonfinite_texture_fails_without_warnings(side, value):
    a = np.zeros((2, 2, 4), dtype=np.float64)
    b = a.copy()
    (a if side == "candidate" else b)[0, 0, 0] = value
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = tool.judge_texture({"array": a, "format": "rgba16f"}, {"array": b, "format": "rgba16f"},
                                    tool.pt.Tolerance("finite"))
    assert not result["pass"]
    assert result["invalid_counts"][side] == 1
    assert result["max_abs"] is None and result["max_ulps"] is None


@pytest.mark.parametrize("equal", (True, False))
def test_large_finite_inputs_do_not_overflow(equal):
    a = np.full((2, 2, 4), np.finfo(np.float64).max)
    b = a.copy() if equal else -a
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = tool.judge_texture({"array": a, "format": "rgba16f"}, {"array": b, "format": "rgba16f"},
                                    tool.pt.Tolerance("finite"))
    assert result["pass"] is equal
    assert np.isfinite(result["max_abs"]) and np.isfinite(result["max_ulps"])


def test_nonfinite_delta_fails_before_conversion():
    a = np.ones((2, 2, 4))
    b = np.zeros_like(a)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = tool.judge_texture({"array": a, "format": "rgba16f"}, {"array": b, "format": "rgba16f"},
                                    tool.pt.Tolerance("finite"), unit=0.)
    assert not result["pass"] and result["invalid_counts"]["delta"] == 4


def test_finite_ulp_tolerance_still_controls_verdict():
    a = np.ones((2, 2, 4), dtype=np.float16)
    b = np.nextafter(a, np.float16(2))
    candidate, reference = {"array": a, "format": "rgba16f"}, {"array": b, "format": "rgba16f"}
    assert tool.judge_texture(candidate, reference, tool.pt.Tolerance("one", masked_level=1))["pass"]
    assert not tool.judge_texture(candidate, reference, tool.pt.Tolerance("zero", masked_level=0))["pass"]

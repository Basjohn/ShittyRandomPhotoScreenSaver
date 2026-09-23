"""VZ-04: only waveform-sample consumers carry the 256 samples.

`mode_capabilities.consumes_waveform_samples` is the one declaration of which
modes read `common.waveform`. Every other mode carries an empty sample payload,
while the waveform count and generation stay live for every mode (line-mode
readiness keys on the generation, R-87 CHK12).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from widgets.spotify_visualizer import logical_frame_capture, mode_capabilities

ROOT = Path(__file__).resolve().parents[1]
_ALL_MODES = ("spectrum", "bubble", "sine_wave", "oscilloscope", "devcurve", "sphere")


class _Engine:
    def __init__(self, *, with_count: bool = True) -> None:
        self.waveform_reads = 0
        self._samples = [0.001 * (i % 97) for i in range(256)]
        if not with_count:
            self.get_waveform_count = None  # type: ignore[assignment]

    def get_waveform(self):
        self.waveform_reads += 1
        return list(self._samples)

    def get_waveform_count(self) -> int:
        return 200

    def get_latest_generation_with_waveform(self) -> int:
        return 41


def _state():
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.presentation_state import (
        install_default_presentation_state,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    controller = VisualizerRuntimeController(
        runtime_generation=0, bar_count=32, initial_mode="spectrum"
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=32)
    install_default_presentation_state(controller.presentation_state)
    return state


def test_only_oscilloscope_is_declared_a_waveform_sample_consumer() -> None:
    consumers = {mode for mode in _ALL_MODES if mode_capabilities.consumes_waveform_samples(mode)}
    assert consumers == {"oscilloscope"}


def test_only_declared_consumers_read_common_waveform_in_their_renderer() -> None:
    """A future renderer may not silently read the payload other modes omit."""

    implementations = ROOT / "rendering" / "quick" / "visualizer" / "implementations"
    readers = {
        path.stem
        for path in implementations.glob("*.py")
        if "common.waveform" in path.read_text(encoding="utf-8").replace(
            "common.waveform_count", ""
        )
    }
    assert readers, "the Oscilloscope renderer must still read the samples"
    for stem in readers:
        assert mode_capabilities.consumes_waveform_samples(stem), (
            f"{stem} reads common.waveform but is not declared in "
            "mode_capabilities._WAVEFORM_SAMPLE_CONSUMERS"
        )


@pytest.mark.parametrize("mode", _ALL_MODES)
def test_capture_carries_samples_only_for_consumers(mode) -> None:
    engine = _Engine()
    extra = logical_frame_capture._base_extras(_state(), mode, engine)

    # Count and generation authority are unchanged for every mode.
    assert extra["waveform_count"] == 200
    assert extra["latest_waveform_generation"] == 41
    if mode == "oscilloscope":
        assert list(extra["waveform"]) == engine._samples
        assert engine.waveform_reads == 1
    else:
        assert extra["waveform"] == ()
        assert engine.waveform_reads == 0


@pytest.mark.parametrize("mode", _ALL_MODES)
def test_count_less_engine_still_derives_the_count_from_the_samples(mode) -> None:
    engine = _Engine(with_count=False)
    extra = logical_frame_capture._base_extras(_state(), mode, engine)

    assert extra["waveform_count"] == 256
    assert (extra["waveform"] == ()) is (mode != "oscilloscope")

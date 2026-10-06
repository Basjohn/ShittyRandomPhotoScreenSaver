"""VZ-04: only waveform-sample consumers carry the 256 samples.

`mode_capabilities.consumes_waveform_samples` is the one declaration of which
modes read `common.waveform`. Every other mode carries an empty sample payload,
while the waveform count and generation stay live for every mode (line-mode
readiness keys on the generation, R-87 CHK12).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_visualizer_mode_descriptor,
)
from widgets.spotify_visualizer import logical_frame_capture, mode_capabilities

ROOT = Path(__file__).resolve().parents[1]
_ALL_MODES = VISUALIZER_MODE_IDS


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


def test_declared_waveform_sample_consumers_are_real_renderer_consumers() -> None:
    consumers = {
        mode for mode in _ALL_MODES if mode_capabilities.consumes_waveform_samples(mode)
    }
    # Oscilloscope's identity is waveform rendering, so losing its declaration
    # is a semantic regression. Future waveform-driven modes may join without
    # requiring this test to be rewritten.
    assert "oscilloscope" in consumers
    for mode in consumers:
        descriptor = get_visualizer_mode_descriptor(mode)
        renderer_path = ROOT / (descriptor.renderer_module.replace(".", "/") + ".py")
        source = renderer_path.read_text(encoding="utf-8").replace(
            "common.waveform_count", ""
        )
        assert "common.waveform" in source, (
            f"{mode} declares waveform-sample consumption but its renderer does not read it"
        )


def test_only_declared_consumers_read_common_waveform_in_their_renderer() -> None:
    """A future renderer may not silently read the payload other modes omit."""

    readers: set[str] = set()
    for mode in _ALL_MODES:
        descriptor = get_visualizer_mode_descriptor(mode)
        renderer_path = ROOT / (descriptor.renderer_module.replace(".", "/") + ".py")
        source = renderer_path.read_text(encoding="utf-8").replace(
            "common.waveform_count", ""
        )
        if "common.waveform" in source:
            readers.add(mode)
            assert mode_capabilities.consumes_waveform_samples(mode), (
                f"{mode} renderer reads common.waveform but the mode is not declared "
                "as a waveform-sample consumer"
            )
    assert "oscilloscope" in readers


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

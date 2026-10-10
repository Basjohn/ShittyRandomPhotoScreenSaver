"""The offline preview snapshot (onboarding previews, the Visualizer cost probe and the overhead
baseline) builds every registered Visualizer mode, applying the mode's resolved technical config as
the display owner does, while the fixture bars, not a silent engine, still drive Spectrum's peaks."""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

_MODES = tuple(descriptor.mode_id for descriptor in iter_visualizer_mode_descriptors())


@pytest.mark.parametrize("mode", _MODES)
def test_every_mode_builds_a_preview_snapshot(qt_app, mode):
    snapshot = _build_spectrum_preview_snapshot(width=320, height=180, mode=mode)
    assert snapshot.logical.mode_state is not None
    if mode == "devcurve":
        # Its frame runtime advanced as on a production tick: the renderer's parameters are there.
        assert "devcurve_sample_count" in snapshot.logical.mode_state.parameters


def test_spectrum_peaks_follow_the_fixture_bars(qt_app):
    peaks = list(_build_spectrum_preview_snapshot(width=320, height=180, mode="spectrum").logical.mode_state.peaks)
    assert len(peaks) > 8
    # The fixture is a jagged pattern; a silent engine would leave a smooth floor profile.
    steps = [b - a for a, b in zip(peaks, peaks[1:]) if b != a]
    turns = sum(1 for a, b in zip(steps, steps[1:]) if (a > 0) != (b > 0))
    assert turns > len(peaks) // 4

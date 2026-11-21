"""Waveform's bloom strength crossing 0 fades; it never switches the composite path (N5.4, fade never vanish).

The HDR scene and its tone map stay in place at strength 0, where the glow's contribution is 0, so a recorded run
whose strength reaches 0 shows no frame-to-frame jump at the crossing beyond its neighbours' motion. The control
replays the old rule (no HDR, no tone map once the strength is 0) and pops.
"""
from dataclasses import replace

import numpy as np
import pytest

from tests.test_waveform_ribbon_mode import frame_for

# A recorded run's strength, in equal steps down to 0 and back (one frame each).
RUN = (.30, .20, .10, 0., .10, .20, .30)
CROSSING = (2, 3, 4, 5)           # the steps touching the frame at 0 (indices into the step list below)


def _record(old_switch, monkeypatch):
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    from rendering.quick.scene3d.target import SceneTarget
    target = OffscreenRenderTarget(320, 200)
    renderer = QuickWaveformRibbonRenderer()
    if old_switch:
        original = SceneTarget.scope

        def switched(self, frame, samples, resources, *args, **kwargs):
            if kwargs.get('bloom', 0.) <= 0.:          # the old rule: no strength, no HDR and no tone map
                kwargs.update(hdr=None, bloom_stage=False)
            return original(self, frame, samples, resources, *args, **kwargs)
        monkeypatch.setattr(SceneTarget, 'scope', switched)
    frames = []
    try:
        frame = frame_for(target)
        state = frame.snapshot.logical.mode_state
        for strength in RUN:
            frame.snapshot.logical.mode_state = replace(state, scene=replace(state.scene, bloom=strength))
            target.bind(); renderer.render(frame)
            frames.append(target.read_rgba()[:, :, :3].astype(float))
    finally:
        renderer.release_resources(); target.close()
    return frames


def _steps(frames):
    return [float(np.abs(b - a).mean()) for a, b in zip(frames, frames[1:])]


@pytest.mark.qt
def test_bloom_strength_crossing_zero_does_not_pop(qt_app, monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    steps = _steps(_record(False, monkeypatch))
    here = [steps[i] for i in (2, 3)]                       # into 0 and out of 0
    around = [steps[i] for i in (0, 1, 4, 5)]               # the neighbouring frames' motion
    assert max(here) <= 1.5 * max(around) + 1e-6, (steps, here, around)


@pytest.mark.qt
def test_the_old_switch_pops_at_the_crossing(qt_app, monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    steps = _steps(_record(True, monkeypatch))
    here = [steps[i] for i in (2, 3)]
    around = [steps[i] for i in (0, 1, 4, 5)]
    assert max(here) > 1.5 * max(around), (steps, here, around)

"""First use of a 3D Visualizer lands behind its reveal (H1).

A ``prepared_reveal`` renderer compiles and allocates on hidden frames (content fade 0), one unit
per frame at least ``PREPARE_SPACING_S`` apart, through the production render host on an
offscreen context (no window); its first visible frame then compiles and allocates nothing.
The owner keeps a waiting target hidden until the render thread reports the activation
prepared, and reveals anyway at the deadline so nothing can strand."""
from __future__ import annotations

import dataclasses
import importlib
from types import SimpleNamespace

import numpy as np
import pytest

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_visualizer_mode_descriptor

pytestmark = pytest.mark.qt

_CASES = {
    "extruded_spectrum": {"extruded_spectrum_smooth_edges": True, "extruded_spectrum_face_mirror": 0.6},
    "shockwave_grid": {"shockwave_grid_glow": 0.8},
    "sphere": {},
}


def test_the_descriptor_flag_matches_the_renderers_that_prepare():
    for mode in VISUALIZER_MODE_IDS:
        descriptor = get_visualizer_mode_descriptor(mode)
        module = importlib.import_module(descriptor.renderer_module)
        renderer = getattr(module, descriptor.renderer_factory)()
        assert descriptor.prepared_reveal == hasattr(renderer, "prepare_step"), mode
    assert {"extruded_spectrum", "shockwave_grid", "sphere"} <= {
        mode for mode in VISUALIZER_MODE_IDS if get_visualizer_mode_descriptor(mode).prepared_reveal}


def _snapshot(mode, fade, activation=1, **parameters):
    from tests.test_qtquick_extruded_spectrum import H, W
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode=mode)
    state = snapshot.logical.mode_state
    state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
    logical = dataclasses.replace(snapshot.logical, mode_state=state, activation_id=activation)
    presentation = dataclasses.replace(snapshot.presentation, content_fade=fade)
    return dataclasses.replace(snapshot, logical=logical, presentation=presentation)


@pytest.fixture
def rig(qt_app, monkeypatch):
    from rendering.quick.scene3d import resources
    from rendering.quick.visualizer import render_host
    from tests.test_qtquick_extruded_spectrum import _Target

    clock = SimpleNamespace(now=100.0)
    compiles = []
    real_compile = resources.compile_program

    def counting_compile(*args, **kwargs):
        compiles.append(clock.now)
        return real_compile(*args, **kwargs)

    monkeypatch.setattr(render_host.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(resources, "compile_program", counting_compile)
    target = _Target()
    host = render_host.QuickVisualizerRenderHost()
    yield target, host, clock, compiles
    host.release_resources()
    target.close()


@pytest.mark.parametrize("mode", sorted(_CASES))
def test_hidden_frames_prepare_spaced_and_the_first_visible_frame_creates_nothing(rig, mode):
    from rendering.quick.visualizer.render_host import PREPARE_SPACING_S

    target, host, clock, compiles = rig
    parameters = _CASES[mode]
    backdrop = (0.1, 0.2, 0.3, 1.0)
    for _ in range(60):
        frame_compiles = len(compiles)
        pixels = target.render(host, _snapshot(mode, 0.0, **parameters), backdrop=backdrop)
        assert len(compiles) - frame_compiles <= 1                       # at most one compile a frame
        assert (np.abs(pixels - pixels[0, 0]).max() == 0)                # hidden: nothing drawn
        if host.prepared_activation == (mode, 1):
            break
        clock.now += PREPARE_SPACING_S / 3                              # three frames per step
    assert host.prepared_activation == (mode, 1)
    assert len(compiles) >= 2 and np.diff(compiles).min() >= PREPARE_SPACING_S - 1e-9
    renderer = host._implementations[mode]
    scene_target = getattr(renderer, "_target", None)
    allocation = scene_target.allocation if scene_target is not None else None
    before = len(compiles)
    pixels = target.render(host, _snapshot(mode, 1.0, **parameters), backdrop=backdrop)
    assert len(compiles) == before
    assert scene_target is None or scene_target.allocation == allocation
    assert np.abs(pixels - pixels[0, 0]).max() > 0                       # and it draws


@pytest.mark.parametrize("mode", sorted(_CASES))
def test_without_hidden_frames_the_first_visible_frame_compiles(rig, mode):
    target, host, _clock, compiles = rig
    target.render(host, _snapshot(mode, 1.0, **_CASES[mode]))
    assert len(compiles) >= 2                                            # the cost this moves
    assert host.prepared_activation == (mode, 1)


def test_a_new_activation_prepares_what_its_parameters_add(rig):
    from rendering.quick.visualizer.render_host import PREPARE_SPACING_S

    target, host, clock, compiles = rig
    target.render(host, _snapshot("shockwave_grid", 1.0, shockwave_grid_glow=0.0))
    plain = len(compiles)
    for _ in range(60):
        target.render(host, _snapshot("shockwave_grid", 0.0, activation=2, shockwave_grid_glow=0.8))
        if host.prepared_activation == ("shockwave_grid", 2):
            break
        clock.now += PREPARE_SPACING_S
    assert host.prepared_activation == ("shockwave_grid", 2) and len(compiles) > plain   # the glow's programs
    before = len(compiles)
    target.render(host, _snapshot("shockwave_grid", 1.0, activation=2, shockwave_grid_glow=0.8))
    assert len(compiles) == before
    host.release_resources()
    assert host.prepared_activation is None


class _Item:
    def __init__(self) -> None:
        self.prepared = False
        self.asked = []

    def renderer_prepared(self, mode, activation):
        self.asked.append((mode, activation))
        return self.prepared


def _owner(clock, item):
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._retired = False
    owner._sync = SimpleNamespace(sync_latest=lambda: True)
    owner._transition_clock = lambda: clock.now
    owner._transition_half_duration_s = 0.25
    owner._controller = SimpleNamespace(
        playing=True, mode_id="shockwave_grid",
        logical_tick_state=SimpleNamespace(_waiting_for_fresh_engine_frame=False))
    owner._presentation_runtime = SimpleNamespace(scene_controller=SimpleNamespace(visualizer_item=item))
    owner._mode_transition_phase = "waiting_target"
    owner._mode_transition_started_at = 0.0
    owner._mode_transition_fade = 0.0
    owner._preparing_activation = ("shockwave_grid", 7)
    owner._waiting_target_since = clock.now
    owner._pending_mode_activation = None
    return owner


def test_the_reveal_waits_for_the_prepared_renderer():
    clock, item = SimpleNamespace(now=5.0), _Item()
    owner = _owner(clock, item)
    for _ in range(5):
        clock.now += 0.05
        owner.sync_present()
        assert owner._mode_transition_phase == "waiting_target" and owner._mode_transition_fade == 0.0
    assert item.asked[-1] == ("shockwave_grid", 7)
    item.prepared = True
    clock.now += 0.05
    owner.sync_present()
    assert owner._mode_transition_phase == "fading_in" and owner._preparing_activation is None


def test_the_reveal_proceeds_at_the_deadline():
    from widgets.spotify_visualizer.quick_display_visualizer_owner import _PREPARED_REVEAL_DEADLINE_S

    clock, item = SimpleNamespace(now=5.0), _Item()
    owner = _owner(clock, item)
    clock.now += _PREPARED_REVEAL_DEADLINE_S - 0.01
    owner.sync_present()
    assert owner._mode_transition_phase == "waiting_target"
    clock.now += 0.02
    owner.sync_present()
    assert owner._mode_transition_phase == "fading_in"


def test_a_target_that_does_not_prepare_reveals_at_once():
    clock, item = SimpleNamespace(now=5.0), _Item()
    owner = _owner(clock, item)
    owner._preparing_activation = None
    owner.sync_present()
    assert owner._mode_transition_phase == "fading_in" and not item.asked


def test_the_item_reads_the_current_nodes_preparation():
    from rendering.quick.visualizer.item import _RenderNodeRetirement
    from rendering.quick.visualizer.telemetry import VisualizerRenderNodeTelemetry

    retirement = _RenderNodeRetirement(VisualizerRenderNodeTelemetry())
    assert retirement.renderer_prepared("shockwave_grid", 3) is False         # no node yet
    host = SimpleNamespace(prepared_activation=("shockwave_grid", 3))
    retirement.set_node(SimpleNamespace(render_host=host), active_mode_id="shockwave_grid")
    assert retirement.renderer_prepared("shockwave_grid", 3) is True
    assert retirement.renderer_prepared("shockwave_grid", 4) is False         # another activation

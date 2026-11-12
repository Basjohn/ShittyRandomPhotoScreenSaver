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
from tests._visualizer_frozen_settings import frozen_visualizer_settings

pytestmark = pytest.mark.qt

_CASES = {
    "extruded_bubble": {},
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

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode=mode, settings=frozen_visualizer_settings(mode))
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
    for _ in range(150):                                                 # three frames a step
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


def test_extruded_bubbles_first_visible_frame_asks_gl_for_no_uniform_location(rig):
    """1C.2: the preparation resolves each drawing program's uniform locations, so the first visible frame asks GL for
    none (before: 864 lookups over 11 programs, 480 of them names a program does not have; on the real 4K display
    that frame took 120 ms beside a second render thread). Every location the renderer then holds equals GL's own
    answer, inactive names included. Control: on the pre-fix renderer the first visible frame made every lookup."""
    import rendering.quick.visualizer.implementations.extruded_bubble as eb
    from rendering.quick.visualizer.render_host import PREPARE_SPACING_S

    target, host, clock, _compiles = rig
    for _ in range(300):
        target.render(host, _snapshot("extruded_bubble", 0.0))
        if host.prepared_activation == ("extruded_bubble", 1):
            break
        clock.now += PREPARE_SPACING_S
    assert host.prepared_activation == ("extruded_bubble", 1)
    real_set, real_lookup = eb._Uniforms.set, eb.gl.glGetUniformLocation
    inside, asked = [False], []

    def watched_set(self, program, values):
        inside[0] = True
        try:
            return real_set(self, program, values)
        finally:
            inside[0] = False

    def watched_lookup(program, name):
        if inside[0]:
            asked.append(name)
        return real_lookup(program, name)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(eb._Uniforms, "set", watched_set)
        patch.setattr(eb.gl, "glGetUniformLocation", watched_lookup)
        pixels = target.render(host, _snapshot("extruded_bubble", 1.0), backdrop=(0.1, 0.2, 0.3, 1.0))
    assert np.abs(pixels - pixels[0, 0]).max() > 0                       # it drew
    assert asked == []
    held = host._implementations["extruded_bubble"]._uniforms._locations
    assert any(location < 0 for location in held.values()) and any(location >= 0 for location in held.values())
    assert {key: location for key, location in held.items()} == {
        (program, name): int(real_lookup(program, name)) for program, name in held}


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
    for _ in range(150):                                                 # three frames a step
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


def test_each_preparation_unit_and_the_first_draw_are_counted_for_their_activation(rig):
    # R-180's liveness signal: one count per preparation unit the render thread completes (a unit can be a
    # multi-second cold driver link), one for an activation's first draw, none on later frames or for others.
    from rendering.quick.visualizer.render_host import PREPARE_SPACING_S

    target, host, clock, _compiles = rig
    assert host.preparation_progress("shockwave_grid", 1) == 0
    units = 0
    for _ in range(150):
        before = host.preparation_progress("shockwave_grid", 1)
        target.render(host, _snapshot("shockwave_grid", 0.0))
        units += 1
        assert host.preparation_progress("shockwave_grid", 1) == before + 1          # one unit a spaced frame
        target.render(host, _snapshot("shockwave_grid", 0.0))                        # inside the spacing: none
        assert host.preparation_progress("shockwave_grid", 1) == before + 1
        if host.prepared_activation == ("shockwave_grid", 1):
            break
        clock.now += PREPARE_SPACING_S
    assert host.prepared_activation == ("shockwave_grid", 1) and units >= 2
    target.render(host, _snapshot("shockwave_grid", 1.0))
    assert host.preparation_progress("shockwave_grid", 1) == units                   # prepared: no further count
    assert host.preparation_progress("shockwave_grid", 2) == 0
    target.render(host, _snapshot("shockwave_grid", 1.0, activation=2))
    assert host.preparation_progress("shockwave_grid", 2) == 1                       # a first draw is progress
    assert host.preparation_progress("shockwave_grid", 1) == 0
    host.release_resources()
    assert host.preparation_progress("shockwave_grid", 2) == 0


class _Item:
    def __init__(self) -> None:
        self.prepared = False
        self.progress = 0
        self.asked = []

    def renderer_prepared(self, mode, activation):
        self.asked.append((mode, activation))
        return self.prepared

    def renderer_preparation_progress(self, mode, activation):
        return self.progress if (mode, activation) == ("shockwave_grid", 7) else 0


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


def test_a_long_preparation_unit_does_not_reveal_the_target_into_its_remaining_compiles():
    # R-180: Neon Lake's basin link took ~6 s with a cold driver shader cache, holding the GUI thread in Qt's sync.
    # When the GUI resumed, the commit-based bound had long passed and the target was revealed with every other
    # program still to compile on visible frames. The bound runs from the last completed unit: while units keep
    # completing the target stays hidden; only a window with no progress reveals it anyway.
    from widgets.spotify_visualizer.quick_display_visualizer_owner import _PREPARED_REVEAL_DEADLINE_S

    clock, item = SimpleNamespace(now=5.0), _Item()
    owner = _owner(clock, item)
    clock.now += 6.9                                       # the GUI was held for the whole link
    item.progress = 1                                      # which the render thread then completed
    owner.sync_present()
    assert owner._mode_transition_phase == "waiting_target"
    for _ in range(5):                                     # the rest of the units, spaced frames apart
        clock.now += 0.1
        item.progress += 1
        owner.sync_present()
        assert owner._mode_transition_phase == "waiting_target"
    clock.now += _PREPARED_REVEAL_DEADLINE_S + 0.01        # then silence for the whole bound: reveal anyway
    owner.sync_present()
    assert owner._mode_transition_phase == "fading_in"


def _deadline_owner(item, failures):
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    clock = SimpleNamespace(now=5.0)
    owner = _owner(clock, item)
    owner._transition_request_serial = 3
    owner._transition_recovery_issued = False
    owner._transition_failure_callback = failures.append
    owner._render_identity = SimpleNamespace(mode_id="shockwave_grid", activation_id=7)
    owner._worker = None
    assert isinstance(owner, QuickDisplayVisualizerOwner)
    return owner


@pytest.mark.parametrize("fixed", (True, False))
def test_a_slow_but_alive_target_extends_the_activation_deadline_instead_of_reloading(monkeypatch, fixed):
    # R-180, the frozen run of 2026-11-08: the switch to Neon Lake committed, its first preparation unit (the basin
    # program's cold link, ~6 s) held the GUI thread, and the overdue 6 s deadline fired the moment the link
    # returned: "deadline:waiting_target", a full display reload for a target that was alive. A deadline whose window
    # saw the target's render progress is extended (bounded); one with none still fails. Negative control
    # (fixed=False, the progress read removed): the same live target is failed and reloaded.
    from core.threading.manager import ThreadManager
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    rearmed: list = []
    monkeypatch.setattr(ThreadManager, "single_shot",
                        staticmethod(lambda ms, func, *args: rearmed.append((ms, func, args))))
    if not fixed:
        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_slow_target_alive",
                            lambda self, serial: False, raising=False)
    failures: list = []
    item = _Item()
    owner = _deadline_owner(item, failures)
    item.progress = 1                                      # the long link returned just before the deadline ran
    owner._on_transition_deadline(3)
    if not fixed:
        assert failures == ["deadline:waiting_target"]     # the defect: a live target reloaded
        return
    assert failures == [] and owner._mode_transition_phase == "waiting_target"
    (ms, func, args), = rearmed
    assert ms == owner_module._ACTIVATION_TRANSACTION_DEADLINE_MS and args == (3,)
    assert func.__func__ is owner_module.QuickDisplayVisualizerOwner._on_transition_deadline
    owner._on_transition_deadline(2)                       # a superseded request's deadline stays inert
    assert failures == [] and len(rearmed) == 1
    owner._on_transition_deadline(3)                       # no progress in the whole next window: silent, fail
    assert failures == ["deadline:waiting_target"] and owner._mode_transition_phase == "failed"


def test_slow_target_extensions_are_bounded(monkeypatch):
    from core.threading.manager import ThreadManager
    from widgets.spotify_visualizer.quick_display_visualizer_owner import _SLOW_TARGET_DEADLINE_EXTENSIONS

    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda ms, func, *args: None))
    failures: list = []
    item = _Item()
    owner = _deadline_owner(item, failures)
    for _ in range(_SLOW_TARGET_DEADLINE_EXTENSIONS):
        item.progress += 1
        owner._on_transition_deadline(3)
        assert failures == []
    item.progress += 1                                     # still progressing, but out of extensions
    owner._on_transition_deadline(3)
    assert failures == ["deadline:waiting_target"]


def test_an_uncommitted_worker_target_is_never_counted_alive(monkeypatch):
    # Before the engine worker's commit reply binds the target, the render identity is still the outgoing one: its
    # frames are not the target's progress, so a silent worker still fails at the deadline.
    from core.threading.manager import ThreadManager

    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda ms, func, *args: None))
    failures: list = []
    item = _Item()
    owner = _deadline_owner(item, failures)
    owner._worker = object()
    owner._worker_commit = {"target": "shockwave_grid"}
    item.progress = 5
    owner._on_transition_deadline(3)
    assert failures == ["deadline:waiting_target"]


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
    host.preparation_progress = lambda mode, activation: 2 if (mode, activation) == ("shockwave_grid", 3) else 0
    assert retirement.renderer_preparation_progress("shockwave_grid", 3) == 2
    assert retirement.renderer_preparation_progress("shockwave_grid", 4) == 0

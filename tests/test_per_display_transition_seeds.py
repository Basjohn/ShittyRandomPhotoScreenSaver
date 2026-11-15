"""Plan 1D.15: a batch's seeded transition runs its own seed on each display (two hidden display units, no window).

One batch keeps one transition type and its Settings; each display's run re-draws its run seeds from the batch seed
and that display's stable identity (its ``screen_key``, never its index). Idle preparation builds each display's own
geometry, one display per spaced warm step.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QColor, QImage

from engine.display_manager import DisplayManager
from rendering.quick.display_image_route import presentation_image_from_processed_qimage
from rendering.quick.transitions.parameter_resolution import RUN_SEED_FIELDS
from rendering.quick.transitions.request_resolution import RandomTransitionSelection, ResolvedQuickTransitionSpec
from rendering.transition_registry import get_transition_descriptor
from tests._display_manager_doubles import display_runtime_double, display_unit_double, quick_display_identity

pytestmark = pytest.mark.qt

_SIZE = (2560, 1440)                     # both displays alike: equal aspects must still get different runs


def _image(name: str):
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor("#334455"))
    return presentation_image_from_processed_qimage(image, image_path=name)


class _Settings:
    def __init__(self, transition_id: str) -> None:
        self.name = get_transition_descriptor(transition_id).setting_name

    def get(self, key, default=None):
        if key == "transitions":
            return {"type": "Crossfade", "random_always": True, "pool": {self.name: True},
                    "activation": {self.name: True}}
        return True if key == "display.hw_accel" else default

    def get_bool(self, key, default=False):
        return bool(self.get(key, default))


class _Host:
    """A real DisplayManager over hidden display units; COMPUTE and the warm spacing are recorded, not run."""

    def __init__(self, transition_id: str, keys=("monitor-a", "monitor-b")) -> None:
        self.submitted, self.deferred, self.warmed, self.started = [], [], [], []
        host = self

        class _Threads:
            def submit_compute_task(self, func, *args, **kwargs):
                host.submitted.append((func, args))
                return "task"

            def single_shot(self, delay, callback, *args):
                host.deferred.append(lambda: callback(*args))
                return SimpleNamespace(active=True)

        self.source = _image("source")
        self.units = [self._unit(index, key) for index, key in enumerate(keys)]
        self.manager = DisplayManager(settings_manager=_Settings(transition_id), thread_manager=_Threads(),
                                      runtime_generation=1015)
        self.manager.displays = list(self.units)
        self.manager._authoritative_first_frame_emitted = True
        self.selection = RandomTransitionSelection(get_transition_descriptor(transition_id).setting_name)
        self.manager.set_random_transition_selection(self.selection)

    def _unit(self, index: int, key: str):
        width, height = _SIZE
        identity = quick_display_identity(index, key, (index * width, 0, width, height))
        return display_unit_double(
            display_runtime_double(display_identity=identity),
            screen_index=index,
            current_image=lambda: self.source,
            present_captured_image=lambda image: None,
            start_transition=lambda request: self.started.append((key, request)),
            has_running_transition=lambda: False,
            transition_logical_size=lambda: (float(width), float(height)),
            schedule_transition_warm_step=lambda tid, params, reporter, ticket:
                (self.warmed.append((key, dict(params), ticket)) or True),
            cancel_transition_warm_up=lambda: None,
        )

    def batch(self, seed: int | None = None) -> dict[str, dict]:
        """Admit one image batch on every display; each display's request parameters by its identity key."""
        if seed is not None:
            self.manager._next_batch_seed = seed
        self.started.clear()
        self.manager._begin_quick_transition_batch({unit.screen_index for unit in self.units})
        for unit in self.units:
            self.manager._present_quick_captured_image(unit, _image(f"new-{unit.screen_index}"), "new")
        requests = {key: request for key, request in self.started}
        self.manager._quick_transition_paths.clear()
        self.manager._transition_work_pending = False
        self.manager._reset_quick_transition_batch()
        return requests

    def close(self) -> None:
        self.manager._cancel_idle_transition_warmup()
        self.manager.displays = []


@pytest.fixture
def host_for(qt_app):
    hosts = []

    def make(transition_id: str, keys=("monitor-a", "monitor-b")) -> _Host:
        hosts.append(_Host(transition_id, keys))
        return hosts[-1]

    yield make
    for host in hosts:
        host.close()


def _seeds(parameters) -> dict:
    return {name: value for name, value in dict(parameters).items() if name in RUN_SEED_FIELDS}


def _lens_plan(request):
    from rendering.gl_programs.liquid_lens_program import lens_plan

    params = request.parameter_dict()
    return lens_plan(int(params["stops"]), int(params["seed"]), _SIZE[0] / _SIZE[1])


def test_two_displays_in_one_batch_run_their_own_seed_and_liquid_lens_plan(host_for):
    host = host_for("liquid_lens")
    for seed in range(1, 9):
        requests = host.batch(seed)
        a, b = requests["monitor-a"], requests["monitor-b"]
        assert a.transition_id == b.transition_id == "liquid_lens"
        assert _seeds(a.parameters) and _seeds(a.parameters) != _seeds(b.parameters)
        assert _lens_plan(a) != _lens_plan(b)


@pytest.mark.parametrize("transition_id", ("glass_shatter", "crumble", "jigsaw", "particle", "ripple"))
def test_every_seeded_transition_differs_per_display_and_shares_the_rest(host_for, transition_id):
    host = host_for(transition_id)
    for seed in range(1, 6):
        requests = host.batch(seed)
        a, b = requests["monitor-a"], requests["monitor-b"]
        assert _seeds(a.parameters) and _seeds(a.parameters) != _seeds(b.parameters)
        # The batch keeps one type, direction and Settings: only the run seeds differ (the later display's duration
        # carries the stagger, tests/test_multi_display_transition_desync.py).
        assert (a.transition_id, a.direction) == (b.transition_id, b.direction)
        rest = lambda request: {k: v for k, v in request.parameter_dict().items() if k not in RUN_SEED_FIELDS}
        assert rest(a) == rest(b)


def test_a_display_keeps_its_seed_for_the_same_batch_seed_whatever_its_index(host_for):
    first = host_for("glass_shatter", keys=("monitor-a", "monitor-b"))
    # The same monitors after a display move: the other order, so each one has the other's index.
    moved = host_for("glass_shatter", keys=("monitor-b", "monitor-a"))
    for seed in (5, 77, 2**63 + 11):
        once, again, reordered = first.batch(seed), first.batch(seed), moved.batch(seed)
        for key in ("monitor-a", "monitor-b"):
            assert _seeds(once[key].parameters) == _seeds(again[key].parameters)       # reproducible
            assert _seeds(once[key].parameters) == _seeds(reordered[key].parameters)   # identity, not index
    assert _seeds(first.batch(5)["monitor-a"].parameters) != _seeds(first.batch(6)["monitor-a"].parameters)


def test_idle_preparation_builds_one_displays_own_geometry_per_spaced_step(host_for):
    from rendering.quick.transitions.run_geometry import PREPARED_GEOMETRY, glass_geometry_key

    host = host_for("glass_shatter")
    manager = host.manager
    manager.prepare_next_transition(host.selection)
    # Only the first display's set is built in the idle edge itself.
    assert [len(args[1]) for _func, args in host.submitted] == [1]
    first_job = host.submitted[-1][1][1][0]
    steps = 0
    while host.deferred:
        host.deferred.pop(0)()
        key, params, ticket = host.warmed[-1]
        # Each display warms its own run: the parameters its own geometry upload keys on.
        assert params == dict(manager._display_transition_spec(
            next(unit for unit in host.units if unit.runtime.display_identity.screen_key == key),
            manager._idle_warm_spec, manager._idle_warm_seed).parameters)
        manager._on_idle_warm_step_finished(ticket, True)
        steps += 1
        # The next display's set is submitted only when the spaced chain reaches it, one set per submission.
        assert [len(args[1]) for _func, args in host.submitted] == [1] * min(steps + 1, len(host.units))
    assert [key for key, _params, _ticket in host.warmed] == ["monitor-a", "monitor-b"]
    jobs = [args[1][0] for _func, args in host.submitted]
    assert jobs[0] == first_job and jobs[0][0]["seed"] != jobs[1][0]["seed"]
    PREPARED_GEOMETRY.clear()
    for func, args in host.submitted:
        func(*args)
    # The batch that follows meets each display's own prepared set.
    for request in host.batch().values():
        key = glass_geometry_key(request.parameter_dict(), _SIZE[0] / _SIZE[1], request.direction)
        assert PREPARED_GEOMETRY.get(key) is not None
    PREPARED_GEOMETRY.clear()


def test_the_native_route_reads_each_displays_seed_from_its_request(host_for):
    from rendering.quick.render import native_background as nb
    from rendering.quick.transitions.state import TransitionRun

    renderer = nb.native_transition_renderer("liquid_lens")
    assert renderer is not None
    requests = host_for("liquid_lens").batch(31)
    settings = []
    for request in requests.values():
        # One duration for both (the later display's stagger is not under test), so only the request's own
        # parameters can tell the two frames apart.
        request = replace(request, duration_ms=1000)
        run = TransitionRun.start(run_id=1, request=request, start_ns=1_000)
        sample = run.sample(run.start_ns + (run.end_ns - run.start_ns) // 3)
        settings.append(nb.transition_settings(renderer, run, sample, (float(_SIZE[0]), float(_SIZE[1])), 1.0))
    assert settings[0] != settings[1]


def test_negative_control_the_shared_batch_seed_mirrors_both_displays(host_for, monkeypatch):
    """Today's shared seed (one spec for every display) is exactly what the checks above refuse."""
    monkeypatch.setattr(ResolvedQuickTransitionSpec, "for_display", lambda self, batch_seed, display_key: self)
    requests = host_for("liquid_lens").batch(3)
    a, b = requests["monitor-a"], requests["monitor-b"]
    assert _seeds(a.parameters) == _seeds(b.parameters) and _lens_plan(a) == _lens_plan(b)

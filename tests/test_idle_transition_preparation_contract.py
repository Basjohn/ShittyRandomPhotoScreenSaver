"""Qt-free execution of the exact display-owner idle GL admission methods.

This protects against a future reintroduction of repaint-driven warm-up or
parallel display preparation even where Windows Qt is not available.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / 'engine' / 'display_manager.py'
ITEM = ROOT / 'rendering' / 'quick' / 'render' / 'background_item.py'
METHODS = (
    '_cancel_idle_transition_warmup', '_idle_warm_valid',
    '_arm_next_idle_warm_step', '_admit_idle_warm_step', '_on_idle_warm_step_finished',
)


def _harness():
    tree = ast.parse(MANAGER.read_text(encoding='utf-8'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DisplayManager')
    implementations = []
    for method in owner.body:
        if isinstance(method, ast.FunctionDef) and method.name in METHODS:
            method.decorator_list = []
            implementations.append(method)
    assert len(implementations) == len(METHODS)
    namespace = {
        'IDLE_TRANSITION_WARM_STEP_SPACING_MS': 200,
        'IDLE_TRANSITION_WARM_MAX_STEPS_PER_DISPLAY': 96,
        'logger': SimpleNamespace(debug=lambda *a, **k: None),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=implementations, type_ignores=[])),
                 str(MANAGER), 'exec'), namespace)

    class Owner:
        pass

    for name in METHODS:
        setattr(Owner, name, namespace[name])
    owner = Owner()
    owner._retired = False
    owner._idle_warm_serial = 0
    owner._idle_warm_ticket = -1
    owner._idle_warm_shot = None
    owner._idle_warm_seed = 17
    owner._next_batch_seed = 17
    owner._idle_warm_generation = 3
    owner._runtime_generation = 3
    owner._idle_warm_index = 0
    owner._idle_warm_steps = 0
    owner._idle_warm_transition_id = 'crumble'
    owner._idle_warm_parameters = {'test_owned': True}
    # The per-display spec and geometry (plan 1D.15) are DisplayManager collaborators outside this Qt-free cut.
    owner._idle_warm_spec = None
    owner._display_transition_spec = lambda display, spec, seed: spec
    owner._prepare_transition_run_geometry = lambda spec, seed, displays: None
    owner._idle_warm_reporter = SimpleNamespace(finished=SimpleNamespace())
    owner._transition_work_pending = False
    owner.has_transition_work_pending = lambda: owner._transition_work_pending
    requested, deferred, cancelled = [], [], []
    owner._thread_manager = SimpleNamespace(
        single_shot=lambda ms, fn, *args: (deferred.append((ms, lambda: fn(*args))) or SimpleNamespace(active=True)))

    def unit(label):
        return SimpleNamespace(
            schedule_transition_warm_step=lambda name, params, reporter, ticket:
                (requested.append((label, name, ticket)) or True),
            cancel_transition_warm_up=lambda: cancelled.append(label),
        )
    owner.displays = [unit('D0'), unit('D1')]
    owner._idle_warm_order = tuple(owner.displays)
    return owner, requested, deferred, cancelled


def test_idle_gl_preparation_serializes_displays_and_steps():
    owner, requested, deferred, _ = _harness()
    owner._arm_next_idle_warm_step()
    assert len(deferred) == 1 and deferred[0][0] == 200
    assert not requested
    deferred.pop(0)[1]()
    assert [r[0] for r in requested] == ['D0']
    owner._on_idle_warm_step_finished(requested[-1][2], False)
    deferred.pop(0)[1]()
    assert [r[0] for r in requested] == ['D0', 'D0']
    owner._on_idle_warm_step_finished(requested[-1][2], True)
    deferred.pop(0)[1]()
    assert [r[0] for r in requested] == ['D0', 'D0', 'D1']
    owner._on_idle_warm_step_finished(requested[-1][2], True)
    assert not deferred and owner._idle_warm_seed is None


def test_busy_transition_new_generation_and_reservation_cancel_deferred_jobs():
    for mutation in ('busy', 'generation', 'seed', 'retirement'):
        owner, requested, deferred, cancelled = _harness()
        owner._arm_next_idle_warm_step()
        if mutation == 'busy': owner._transition_work_pending = True
        if mutation == 'generation': owner._runtime_generation = 4
        if mutation == 'seed': owner._next_batch_seed = 18
        if mutation == 'retirement': owner._retired = True
        deferred.pop(0)[1]()
        assert not requested, mutation
        owner._cancel_idle_transition_warmup()
        assert len(cancelled) == 2


def test_retired_result_cannot_start_another_display():
    owner, requested, deferred, _ = _harness()
    owner._arm_next_idle_warm_step()
    deferred.pop(0)[1]()
    ticket = requested[-1][2]
    owner._cancel_idle_transition_warmup()
    owner._on_idle_warm_step_finished(ticket, True)
    assert not deferred and len(requested) == 1


def test_preparation_waits_for_a_frame_the_window_renders_anyway_through_the_one_window_edge():
    """The GUI warm unit asks for no frame: it rides the window's own ``afterRendering`` through ``_WindowEdge`` (the
    one queued, one-shot edge owner), and the item has no render-thread job, no ``beforeRendering`` and no repaint."""
    source = ITEM.read_text(encoding='utf-8')
    assert '_WindowEdge("afterRendering", self._run_gui_warm)' in source
    assert 'beforeRendering' not in source and 'scheduleRenderJob' not in source
    assert '_FrameEdgeReceiver' not in source
    method = source.split('def schedule_warm_step(', 1)[1].split('def _cancel_warm_up(', 1)[0]
    assert '.update(' not in method


def test_cancel_releases_existing_delayed_one_shot():
    owner, requested, deferred, cancelled = _harness()
    released = []
    class Handle:
        active = True
        def cancel(self): released.append(True)
    owner._thread_manager.single_shot = lambda ms, fn, *args: (deferred.append((ms, lambda: fn(*args))) or Handle())
    owner._arm_next_idle_warm_step()
    assert owner._idle_warm_shot is not None
    owner._cancel_idle_transition_warmup()
    assert released == [True] and owner._idle_warm_shot is None
    # A closure already delivered to an event queue still fails its generation fence.
    deferred.pop()[1]()
    assert not requested


def test_idle_continuations_are_bound_to_generation_owned_manager():
    """R138 guard: no anonymous callback may escape the timer-generation registry."""
    owner, requested, deferred, _ = _harness()
    calls = []
    def shot(ms, fn, *args):
        calls.append((ms, fn, args))
        return SimpleNamespace(active=True)
    owner._thread_manager.single_shot = shot
    owner._arm_next_idle_warm_step()
    assert len(calls) == 1
    delay, callback, args = calls[0]
    assert delay == 200
    assert getattr(callback, '__self__', None) is owner
    assert callback.__name__ == '_admit_idle_warm_step'
    assert args == (owner._idle_warm_serial,)
    assert not requested


def test_prefetch_stagger_continuation_is_generation_owned():
    """R136 deferred source batches must participate in ThreadManager retirement."""
    pipeline = (ROOT / 'engine' / 'image_pipeline.py').read_text(encoding='utf-8')
    method = pipeline.split('def _defer_next_source_batch(', 1)[1].split('\n    if max_concurrent is None:', 1)[0]
    assert '_run_if_current._srpss_runtime_generation = generation' in method
    assert 'scheduler.single_shot(int(delay_ms), _run_if_current)' in method
    assert 'threading.Timer(' not in method


def test_idle_preparation_uses_no_unowned_timer_closures():
    manager = MANAGER.read_text(encoding='utf-8')
    method = manager.split('def _arm_next_idle_warm_step(', 1)[1].split('def _on_idle_warm_step_finished(', 1)[0]
    assert 'self._admit_idle_warm_step' in method
    assert 'def _admit(' not in method
    assert 'threading.Timer(' not in method
    assert 'QTimer.singleShot(' not in method

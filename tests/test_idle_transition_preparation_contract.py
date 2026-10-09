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


def test_preparation_does_not_schedule_repaint_or_rely_on_frame_signals():
    source = ITEM.read_text(encoding='utf-8')
    assert 'QQuickWindow.RenderStage.NoStage' in source
    assert 'window.scheduleRenderJob(job,' in source
    # PySide-defined QRunnable subclasses must not be handed to Qt to destroy
    # on the render thread. Qt owns a callable runnable with a weak-only payload.
    assert 'QRunnable.create(payload.run)' in source
    tree = ast.parse(source)
    job_class = next(node for node in tree.body
                     if isinstance(node, ast.ClassDef) and node.name == '_TransitionWarmStepJob')
    assert not job_class.bases
    job_source = ast.get_source_segment(source, job_class)
    assert 'weakref.ref(window)' in job_source
    assert 'weakref.ref(reporter)' in job_source
    assert 'self._window = window' not in job_source
    assert 'self._reporter = reporter' not in job_source
    assert 'beforeRendering.connect' not in source
    method = source.split('def schedule_warm_step(', 1)[1].split('def _cancel_warm_up(', 1)[0]
    assert '.update(' not in method
    assert 'window.update(' not in job_source


def test_render_item_imports_direct_signal_connection_authority():
    """Scene graph invalidation still binds with DirectConnection at window attach."""
    tree = ast.parse(ITEM.read_text(encoding='utf-8'))
    qt_imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                  and node.module == 'PySide6.QtCore']
    assert len(qt_imports) == 1
    assert 'Qt' in {name.name for name in qt_imports[0].names}
    source = ITEM.read_text(encoding='utf-8')
    assert 'Qt.ConnectionType.DirectConnection' in source


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


def _qt_free_render_job_class():
    """Execute the *production* QRunnable implementation with Qt-free adapters."""
    import threading
    import weakref

    tree = ast.parse(ITEM.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == '_TransitionWarmStepJob')
    class QRunnable:
        def __init__(self):
            pass
    class QOpenGLContext:
        @staticmethod
        def currentContext():
            return object()
    env = {'QRunnable': QRunnable, 'QOpenGLContext': QOpenGLContext,
           'weakref': weakref}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 str(ITEM), 'exec'), env)
    return env['_TransitionWarmStepJob']


def test_idle_render_job_does_not_own_gui_qobjects_at_render_thread_deletion():
    """Regression for the paired QBasicTimer wrong-thread warnings and abort."""
    import gc
    import threading
    import weakref

    Job = _qt_free_render_job_class()
    class Window:
        def __init__(self): self.calls = []
        def beginExternalCommands(self): self.calls.append('begin')
        def endExternalCommands(self): self.calls.append('end')
    class Reporter:
        def __init__(self):
            self.results = []
            self.finished = SimpleNamespace(emit=lambda *args: self.results.append(args))
    class Retirement:
        def warm_step(self, *args):
            assert args == ('block_spins', {'seed': 123})
            return True

    window, reporter = Window(), Reporter()
    job = Job(window, Retirement(), ('block_spins', {'seed': 123}),
              threading.Event(), reporter, 7)
    assert job._window_ref() is window and job._reporter_ref() is reporter
    assert all(obj is not window and obj is not reporter for obj in vars(job).values())
    job.run()
    assert window.calls == ['begin', 'end']
    assert reporter.results == [(7, True)]
    window_ref, reporter_ref = weakref.ref(window), weakref.ref(reporter)
    del window, reporter
    gc.collect()
    assert window_ref() is None and reporter_ref() is None
    job.run()  # stale window: no crash, no new work


def test_idle_render_job_cancelled_before_execution_touches_no_qt_wrappers():
    import threading
    Job = _qt_free_render_job_class()
    class GuiWrapper:
        pass
    window = GuiWrapper()
    reporter = GuiWrapper()
    token = threading.Event()
    token.set()
    job = Job(window, object(), ('not_started', {}), token, reporter, 12)
    job.run()  # no GL, no Qt calls, no signal
    assert job._window_ref() is window

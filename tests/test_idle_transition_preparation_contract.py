"""Qt-free execution of the exact display-owner idle GL admission methods.

This protects against a future reintroduction of repaint-driven warm-up, a timer-paced
warm-up, or parallel display preparation even where Windows Qt is not available.
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
    '_arm_next_idle_warm_step', '_request_idle_warm_frame', '_on_idle_warm_frame',
    '_admit_idle_warm_step', '_on_idle_warm_step_finished',
)


def _harness(min_spacing_s=0.2):
    tree = ast.parse(MANAGER.read_text(encoding='utf-8'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DisplayManager')
    implementations = []
    for method in owner.body:
        if isinstance(method, ast.FunctionDef) and method.name in METHODS:
            method.decorator_list = []
            implementations.append(method)
    assert len(implementations) == len(METHODS)
    clock = [100.0]
    namespace = {
        'IDLE_TRANSITION_WARM_MIN_SPACING_S': min_spacing_s,
        'IDLE_TRANSITION_WARM_MAX_STEPS_PER_DISPLAY': 96,
        'logger': SimpleNamespace(debug=lambda *a, **k: None),
        'time': SimpleNamespace(monotonic=lambda: clock[0]),
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
    owner._idle_warm_not_before = 0.0
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
    requested, frames, cancelled = [], [], []

    def no_timer(*args, **kwargs):
        raise AssertionError('idle warm-up must not schedule a timer')
    owner._thread_manager = SimpleNamespace(single_shot=no_timer)

    def unit(label, renders=True):
        return SimpleNamespace(
            schedule_transition_warm_step=lambda name, params, reporter, ticket:
                (requested.append((label, name, ticket)) or True),
            request_transition_warm_frame=lambda callback, *args:
                (frames.append((label, callback, args)) or True) if renders else False,
            cancel_transition_warm_up=lambda: cancelled.append(label),
        )
    owner.displays = [unit('D0'), unit('D1')]
    owner._idle_warm_order = tuple(owner.displays)
    owner._unit = unit
    owner._clock = clock
    return owner, requested, frames, cancelled


def _frame(frames, clock, advance=0.0):
    """Deliver the display's next swapped frame to the pending one-shot request."""
    clock[0] += advance
    _label, callback, args = frames.pop(0)
    callback(*args)


def test_idle_gl_preparation_serializes_displays_and_steps_on_rendered_frames():
    owner, requested, frames, _ = _harness()
    owner._arm_next_idle_warm_step()
    assert [f[0] for f in frames] == ['D0'] and not requested   # nothing runs without a frame
    _frame(frames, owner._clock, 0.05)                           # a frame inside the spacing window
    assert not requested and [f[0] for f in frames] == ['D0']    # ...only waits for the next one
    _frame(frames, owner._clock, 0.2)
    assert [r[0] for r in requested] == ['D0'] and not frames    # exactly one step per frame edge
    owner._on_idle_warm_step_finished(requested[-1][2], False)
    assert len(frames) == 1 and len(requested) == 1              # the next step waits for another frame
    _frame(frames, owner._clock, 0.01)
    assert len(requested) == 1                                   # too soon after the last step
    _frame(frames, owner._clock, 0.25)
    assert [r[0] for r in requested] == ['D0', 'D0']
    owner._on_idle_warm_step_finished(requested[-1][2], True)
    _frame(frames, owner._clock, 0.25)
    assert [r[0] for r in requested] == ['D0', 'D0', 'D1']       # display order, never overlapping
    owner._on_idle_warm_step_finished(requested[-1][2], True)
    assert not frames and owner._idle_warm_seed is None


def test_negative_control_without_spacing_the_first_frame_would_admit_a_step():
    """The spacing assertion above discriminates: a zero spacing admits on the first frame."""
    owner, requested, frames, _ = _harness(min_spacing_s=0.0)
    owner._arm_next_idle_warm_step()
    _frame(frames, owner._clock, 0.0)
    assert [r[0] for r in requested] == ['D0']


def test_a_display_that_renders_no_frames_is_skipped_not_waited_for():
    owner, requested, frames, _ = _harness()
    owner.displays = [owner._unit('D0', renders=False), owner._unit('D1')]
    owner._idle_warm_order = tuple(owner.displays)
    owner._arm_next_idle_warm_step()
    assert [f[0] for f in frames] == ['D1'] and owner._idle_warm_index == 1
    _frame(frames, owner._clock, 0.25)
    assert [r[0] for r in requested] == ['D1']


def test_busy_transition_new_generation_and_reservation_cancel_pending_frames():
    for mutation in ('busy', 'generation', 'seed', 'retirement'):
        owner, requested, frames, cancelled = _harness()
        owner._arm_next_idle_warm_step()
        if mutation == 'busy': owner._transition_work_pending = True
        if mutation == 'generation': owner._runtime_generation = 4
        if mutation == 'seed': owner._next_batch_seed = 18
        if mutation == 'retirement': owner._retired = True
        _frame(frames, owner._clock, 0.5)
        assert not requested and not frames, mutation
        owner._cancel_idle_transition_warmup()
        assert len(cancelled) == 2


def test_retired_result_cannot_start_another_display():
    owner, requested, frames, _ = _harness()
    owner._arm_next_idle_warm_step()
    _frame(frames, owner._clock, 0.25)
    ticket = requested[-1][2]
    owner._cancel_idle_transition_warmup()
    owner._on_idle_warm_step_finished(ticket, True)
    assert not frames and len(requested) == 1


def test_a_stale_frame_request_fails_its_serial_fence():
    owner, requested, frames, _ = _harness()
    owner._arm_next_idle_warm_step()
    stale = frames.pop(0)
    owner._cancel_idle_transition_warmup()
    stale[1](*stale[2])
    assert not requested and not frames


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


def test_idle_continuation_is_the_bound_manager_method_and_owns_no_timer():
    owner, requested, frames, _ = _harness()
    owner._arm_next_idle_warm_step()   # the harness's scheduler raises if anything asks for a timer
    callback, args = frames[0][1], frames[0][2]
    assert getattr(callback, '__self__', None) is owner
    assert callback.__name__ == '_on_idle_warm_frame'
    assert args == (owner._idle_warm_serial,)
    assert not requested


def test_prefetch_stagger_continuation_is_generation_owned():
    """R136 deferred source batches must participate in ThreadManager retirement."""
    pipeline = (ROOT / 'engine' / 'image_pipeline.py').read_text(encoding='utf-8')
    method = pipeline.split('def _defer_next_source_batch(', 1)[1].split('\n    if max_concurrent is None:', 1)[0]
    assert '_run_if_current._srpss_runtime_generation = generation' in method
    assert 'scheduler.single_shot(int(delay_ms), _run_if_current)' in method
    assert 'threading.Timer(' not in method


_TIMER_MARKERS = ('single_shot', 'QTimer', 'threading.Timer', 'startTimer', 'schedule_recurring')


def _timer_markers_in(source):
    return [marker for marker in _TIMER_MARKERS if marker in source]


def _warm_up_owner_source(manager_source):
    start = manager_source.index('def _arm_next_idle_warm_step(')
    end = manager_source.index('def _prepare_transition_run_geometry(')
    return manager_source[start:end]


def test_idle_preparation_owns_no_timer():
    assert _timer_markers_in(_warm_up_owner_source(MANAGER.read_text(encoding='utf-8'))) == []


def test_negative_control_the_timer_scan_flags_the_retired_design():
    retired = (
        "def _arm_next_idle_warm_step(self):\n"
        "    handle = self._thread_manager.single_shot(200, self._admit_idle_warm_step, 1)\n"
        "def _prepare_transition_run_geometry(self):\n    pass\n"
    )
    assert _timer_markers_in(_warm_up_owner_source(retired)) == ['single_shot']


def test_scene_controller_owns_only_a_one_shot_frame_continuation():
    controller = (ROOT / 'rendering' / 'quick' / 'scene_controller.py').read_text(encoding='utf-8')
    method = controller.split('def request_transition_warm_frame(', 1)[1].split('def cancel_transition_warm_up(', 1)[0]
    assert '.update(' not in method and 'QTimer' not in method and 'single_shot' not in method
    swapped = controller.split('def _on_frame_swapped(', 1)[1].split('def _on_scene_graph_invalidated(', 1)[0]
    assert 'self._run_warm_frame_request()' in swapped


def test_warm_frame_request_runs_once_on_the_next_swap_and_can_be_cancelled():
    from rendering.quick.scene_controller import QuickSceneController
    calls = []
    controller = QuickSceneController.__new__(QuickSceneController)
    controller._warm_frame_request = None
    controller._readiness = SimpleNamespace(admission_open=True)
    window = SimpleNamespace(isExposed=lambda: True)
    controller._background_item = SimpleNamespace(window=lambda: window, cancel_warm_up=lambda: None)
    assert controller.request_transition_warm_frame(lambda *a: calls.append(a), 7)
    assert calls == []
    controller._run_warm_frame_request()
    controller._run_warm_frame_request()
    assert calls == [(7,)]
    assert controller.request_transition_warm_frame(lambda *a: calls.append(a), 8)
    controller.cancel_transition_warm_up()
    controller._run_warm_frame_request()
    assert calls == [(7,)]
    window.isExposed = lambda: False
    assert controller.request_transition_warm_frame(lambda *a: calls.append(a), 9) is False
    controller._readiness = SimpleNamespace(admission_open=False)
    window.isExposed = lambda: True
    assert controller.request_transition_warm_frame(lambda *a: calls.append(a), 9) is False


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

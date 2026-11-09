"""H2: explicit child logging admission and report ownership after GUI retirement."""
from __future__ import annotations

import functools
import logging
import multiprocessing
import queue
import subprocess
import sys

import pytest


def _stop_id(label):
    from core.process.types import VISUALIZER_STOP_REPORT_PREFIX
    return VISUALIZER_STOP_REPORT_PREFIX + label


@pytest.mark.parametrize('flags,enabled', [(('--perf', '--viz'), True), ((), True), ((), False)])
def test_spawned_worker_inherits_admission_and_persists_module_exception(tmp_path, flags, enabled):
    from core.logging.logger import WorkerLoggingBootstrap, resolve_logging_bootstrap_profile
    from core.process.types import MessageType, WorkerMessage, WorkerResponse
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    bootstrap = WorkerLoggingBootstrap(resolve_logging_bootstrap_profile(flags),
                                       str(tmp_path) if enabled else None, enabled)
    ctx = multiprocessing.get_context('spawn')
    requests, responses = ctx.Queue(), ctx.Queue()
    child = ctx.Process(target=functools.partial(visualizer_worker_main, diagnostics=bootstrap),
                        args=(requests, responses))
    child.start()
    try:
        ready = WorkerResponse.from_dict(responses.get(timeout=10))
        assert ready.msg_type == MessageType.WORKER_READY
        # The production handler catches this invalid configure; its module logger must retain the traceback.
        requests.put(WorkerMessage(MessageType.VIS_CONFIGURE, 1, 'bad-config', payload={}).to_dict())
        error = WorkerResponse.from_dict(responses.get(timeout=5))
        assert not error.success and 'TypeError' in error.error
        requests.put(WorkerMessage(MessageType.SHUTDOWN, 2, 'shutdown').to_dict())
        assert WorkerResponse.from_dict(responses.get(timeout=5)).msg_type == MessageType.SHUTDOWN
        child.join(8)
        assert child.exitcode == 0
        path = tmp_path/'worker_visualizer.log'
        if enabled:
            text = path.read_text(encoding='utf-8')
            assert f'perf={"--perf" in flags}' in text and f'viz={"--viz" in flags}' in text
            assert 'Traceback (most recent call last)' in text and 'EngineSession._construct' in text
            assert (tmp_path/'worker_visualizer'/'native_faults.log').is_file()
            assert not (tmp_path/'screensaver.log').exists()
        else:
            assert not list(tmp_path.iterdir())
    finally:
        if child.is_alive():
            child.terminate()
            child.join(5)
        child.close()
        for channel in (requests, responses):
            channel.close()
            channel.join_thread()


def test_stop_callback_survives_listener_handoff_and_is_delivered_once(caplog):
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import MessageType, WorkerResponse, WorkerType

    supervisor = ProcessSupervisor()
    role = WorkerType.VISUALIZER
    responses = queue.Queue()
    supervisor._response_queues[role] = responses
    seen, ordinary = [], []
    try:
        assert supervisor.register_response_callback(role, _stop_id('stop'), seen.append, retain_until_stopped=True)
        assert supervisor.register_response_callback(role, 'ordinary', ordinary.append)
        supervisor._stop_response_listener(role, reason='worker_stopping')
        assert ordinary == [None] and seen == []
        report = WorkerResponse(MessageType.VIS_STOP, 1, _stop_id('stop'), True,
                                payload={'report': {'failed': 'tick sentinel'}})
        responses.put(report.to_dict())
        supervisor._drain_worker_response_queue(role, dispose_application=True, reason='worker_stopping')
        assert len(seen) == 1 and seen[0].payload['report']['failed'] == 'tick sentinel'
        with supervisor._lock:
            supervisor._cleanup_worker(role)
        assert len(seen) == 1 and not supervisor._response_callbacks[role]
    finally:
        supervisor.shutdown()


def test_missing_stop_callback_cancels_at_final_cleanup_without_leaking():
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType

    supervisor = ProcessSupervisor()
    role = WorkerType.VISUALIZER
    supervisor._response_queues[role] = queue.Queue()
    seen = []
    try:
        assert supervisor.register_response_callback(role, _stop_id('stop'), seen.append, retain_until_stopped=True)
        supervisor._stop_response_listener(role, reason='worker_stopping')
        assert seen == []
        with supervisor._lock:
            supervisor._cleanup_worker(role)
        assert seen == [None] and not supervisor._response_callbacks[role]
    finally:
        supervisor.shutdown()


def test_reused_worker_keeps_at_most_one_unanswered_stop_report():
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType

    supervisor = ProcessSupervisor()
    role = WorkerType.VISUALIZER
    supervisor._response_queues[role] = queue.Queue()
    seen = []
    try:
        for index in range(5):
            assert supervisor.register_response_callback(
                role, _stop_id(str(index)), lambda response, n=index: seen.append((n, response)), retain_until_stopped=True)
        assert seen == [(n, None) for n in range(4)]
        assert list(supervisor._response_callbacks[role]) == [_stop_id('4')]
        assert supervisor._stop_report_correlations == {(role, _stop_id('4'))}
        supervisor._stop_response_listener(role, reason='worker_stopping')
        with supervisor._lock:
            supervisor._cleanup_worker(role)
        assert seen == [(n, None) for n in range(5)]
        assert not supervisor._stop_report_correlations
    finally:
        supervisor.shutdown()


def test_superseded_stop_reply_never_enters_or_evicts_ordinary_response_buffer():
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import MessageType, WorkerResponse, WorkerType

    supervisor = ProcessSupervisor()
    role = WorkerType.VISUALIZER
    supervisor._response_queues[role] = queue.Queue()
    try:
        assert supervisor.register_response_callback(role, _stop_id('old'), lambda response: None,
                                                     retain_until_stopped=True)
        assert supervisor.register_response_callback(role, _stop_id('new'), lambda response: None,
                                                     retain_until_stopped=True)
        ordinary = WorkerResponse(MessageType.VIS_SET_VIEW, 1, 'ordinary', True)
        supervisor._buffer_response(role, ordinary)
        supervisor._buffer_response(role, WorkerResponse(MessageType.VIS_STOP, 2, _stop_id('old'), True))
        assert supervisor._buffered_responses[role] == {'ordinary': [ordinary]}
        assert not supervisor._abandoned_correlations[role]
    finally:
        supervisor._stop_response_listener(role, reason='worker_stopping')
        with supervisor._lock:
            supervisor._cleanup_worker(role)
        supervisor.shutdown()


def test_real_worker_stop_drain_delivers_report_before_cleanup(tmp_path):
    from core.logging.logger import WorkerLoggingBootstrap, resolve_logging_bootstrap_profile
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import MessageType, WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    supervisor = ProcessSupervisor()
    role = WorkerType.VISUALIZER
    bootstrap = WorkerLoggingBootstrap(resolve_logging_bootstrap_profile(()), str(tmp_path))
    supervisor.register_worker_factory(role, functools.partial(visualizer_worker_main, diagnostics=bootstrap))
    seen = []
    try:
        assert supervisor.start(role)
        assert supervisor.register_response_callback(role, _stop_id('stop'), seen.append, retain_until_stopped=True)
        assert supervisor.send_message(role, MessageType.VIS_STOP, {}, correlation_id=_stop_id('stop')) is not None
        assert supervisor.stop(role, timeout=5)
        assert len(seen) == 1 and seen[0] is not None and seen[0].msg_type == MessageType.VIS_STOP
        assert not supervisor._stop_report_correlations and not supervisor._response_callbacks[role]
    finally:
        supervisor.shutdown()


def test_parent_enabled_to_disabled_reentry_clears_child_directory_and_flags(tmp_path):
    script = f'''
from pathlib import Path
import core.logging.logger as log
log.set_forced_log_dir(Path({str(tmp_path)!r}))
log.setup_logging(perf=True, viz=True, lifecycle=True)
enabled = log.worker_logging_bootstrap()
assert enabled.log_directory == {str(tmp_path)!r}
assert enabled.profile.perf and enabled.profile.viz
from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink
class Supervisor:
    def register_worker_factory(self, role, factory):
        pass
    def is_running(self, role):
        return True
link = EngineWorkerLink.__new__(EngineWorkerLink)
link._supervisor = Supervisor()
assert link._ensure_worker()
log.flush_logging()
assert 'Child diagnostics: log=' in (Path({str(tmp_path)!r})/'screensaver.log').read_text(encoding='utf-8')
log._determine_logging_disabled = lambda _path: True
log.setup_logging()
disabled = log.worker_logging_bootstrap()
assert disabled.log_directory is None
assert not disabled.profile.perf and not disabled.profile.viz
log.flush_and_close_logging()
'''
    subprocess.run([sys.executable, '-c', script], check=True, timeout=15, capture_output=True, text=True)


def test_production_factory_snapshots_canonical_profile_without_child_imports(monkeypatch):
    import core.logging.logger as log
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    expected = log.WorkerLoggingBootstrap(log.resolve_logging_bootstrap_profile(('--perf', '--viz')), 'test-logs')
    monkeypatch.setattr(log, 'worker_logging_bootstrap', lambda: expected)
    class Supervisor:
        def register_worker_factory(self, role, factory):
            self.factory = factory

        def is_running(self, role):
            return True

    link = EngineWorkerLink.__new__(EngineWorkerLink)
    link._supervisor = Supervisor()
    assert link._ensure_worker()
    assert link._supervisor.factory.func is visualizer_worker_main
    assert link._supervisor.factory.keywords['diagnostics'] is expected


def test_retired_link_consumes_delayed_stop_without_retaining_link_or_qt(qt_app, caplog):
    import gc
    import weakref
    from core.process.types import MessageType
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link
    from tools.visualizer_replay.live_engine_gate import paced_pcm

    class DelayedStop(_InProcessSupervisor):
        def register_response_callback(self, role, correlation_id, callback, **kwargs):
            return super().register_response_callback(role, correlation_id, callback)

        def send_message(self, role, kind, payload, correlation_id=None):
            if kind == MessageType.VIS_STOP:
                self.stopped = (correlation_id, self.send_request_and_await_response(role, kind, payload))
                return correlation_id
            return super().send_message(role, kind, payload, correlation_id)

    supervisor = DelayedStop()
    rig = gate.OwnerRig('spectrum', worker=True, supervisor=supervisor, cadence='thread')
    try:
        pcm, rate = paced_pcm(.1)
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate):
            owner = rig.build()
        _pump(rig, .05)
        link = owner._worker
        mapping = link.mapping_name
        link._capacity_candidates = (mapping, 'candidate-not-yet-committed')
        reference = weakref.ref(link)
        link.retire()
        owner._worker = None
        del link
        gc.collect()
        assert reference() is None
        corr, response = supervisor.stopped
        response.payload['report']['failed'] = 'delayed tick sentinel'
        callback = supervisor.callbacks.pop(corr)
        assert callback.args == ((mapping, 'candidate-not-yet-committed'),)
        with caplog.at_level(logging.INFO):
            callback(response)
        assert 'delayed tick sentinel' in caplog.text and 'Stop report' in caplog.text and mapping in caplog.text
    finally:
        rig.close()
        supervisor.close()
        engine_worker_link.reset_run_state_for_testing()

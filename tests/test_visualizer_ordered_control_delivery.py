"""L1: ordered controls cannot lose an earlier edge or fail in the Queue feeder."""
from __future__ import annotations

import multiprocessing
import pickle
import queue
import os
from types import SimpleNamespace

import pytest

from core.process.types import MessageType, WorkerType


def _windows_handles():
    import ctypes
    from ctypes import wintypes
    native = ctypes.WinDLL('kernel32', use_last_error=True)
    native.GetCurrentProcess.restype = wintypes.HANDLE
    native.GetProcessHandleCount.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    count = wintypes.DWORD()
    assert native.GetProcessHandleCount(native.GetCurrentProcess(), ctypes.byref(count))
    return count.value


def _supervisor(channel, process=None):
    from core.process.supervisor import ProcessSupervisor
    supervisor = ProcessSupervisor()
    if process is None:
        native_handle = __import__('_winapi').GetCurrentProcess() if os.name == 'nt' else None
        process = SimpleNamespace(is_alive=lambda: True, pid=os.getpid(), sentinel=native_handle)
    supervisor._workers[WorkerType.VISUALIZER] = process
    supervisor._request_queues[WorkerType.VISUALIZER] = channel
    return supervisor


def _close(supervisor):
    supervisor._workers.pop(WorkerType.VISUALIZER, None)
    supervisor.shutdown()


def test_full_ordered_channel_refuses_new_edge_and_preserves_oldest():
    channel = queue.Queue(maxsize=1)
    oldest = {'ordered': 'first'}
    channel.put_nowait(oldest)
    supervisor = _supervisor(channel)
    try:
        assert supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, {}) is None
        assert channel.get_nowait() is oldest
        assert channel.empty()
    finally:
        _close(supervisor)


def test_unpickleable_ordered_payload_fails_before_queue_admission():
    channel = queue.Queue()
    supervisor = _supervisor(channel)
    try:
        with pytest.raises((pickle.PicklingError, AttributeError, TypeError)):
            supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, {'bad': lambda: None})
        assert channel.empty()
    finally:
        _close(supervisor)


class _CountedValue:
    reductions = 0

    def __reduce__(self):
        type(self).reductions += 1
        return str, ('snapshot',)


def test_queue_feeder_only_serializes_inert_bytes_after_single_payload_reduction():
    from core.process.control_messages import decode_control
    channel = multiprocessing.get_context('spawn').Queue(maxsize=1)
    supervisor = _supervisor(channel)
    _CountedValue.reductions = 0
    try:
        assert supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, {'value': _CountedValue()})
        snapshot = channel.get(timeout=5)
        assert isinstance(snapshot, bytes)
        assert decode_control(snapshot)['payload'] == {'value': 'snapshot'}
        assert _CountedValue.reductions == 1
    finally:
        _close(supervisor)
        channel.close()
        channel.join_thread()


@pytest.mark.parametrize('refusal', ('full', 'serialize'))
def test_refused_control_reaches_existing_link_failure_event(qapp, refusal):
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink
    channel = queue.Queue(maxsize=1)
    if refusal == 'full':
        channel.put_nowait({'earlier': True})
    supervisor = _supervisor(channel)
    supervisor._response_queues[WorkerType.VISUALIZER] = queue.Queue()
    link = EngineWorkerLink(supervisor, on_lost=lambda *_: None)
    failed = []
    try:
        payload = {'bad': lambda: None} if refusal == 'serialize' else {}
        link._send(MessageType.VIS_SET_PLAYING, payload, on_failed=failed.append)
        assert failed == []  # failure must not re-enter the edge's caller
        qapp.processEvents()
        assert len(failed) == 1 and 'could not be sent' in str(failed[0])
        assert not link.busy
        assert not supervisor._response_callbacks[WorkerType.VISUALIZER]
    finally:
        link.close()
        _close(supervisor)


def test_other_roles_keep_dictionary_consumer_and_existing_queue_policy():
    from core.process.supervisor import ProcessSupervisor
    supervisor = ProcessSupervisor()
    channel = queue.Queue(maxsize=1)
    channel.put_nowait({'speculative': 'older'})
    role = WorkerType.IMAGE_PREFETCH
    supervisor._workers[role] = SimpleNamespace(is_alive=lambda: True)
    supervisor._request_queues[role] = channel
    try:
        correlation = supervisor.send_message(role, MessageType.IMAGE_DECODE, {'path': 'sample'})
        delivered = channel.get_nowait()
        assert isinstance(delivered, dict) and delivered['correlation_id'] == correlation
        assert delivered['payload'] == {'path': 'sample'}
    finally:
        supervisor._workers.pop(role)
        supervisor.shutdown()


def _echo_worker(requests, responses):
    from core.process.workers.base import BaseWorker
    from core.process.types import WorkerResponse
    class Echo(BaseWorker):
        @property
        def worker_type(self):
            return WorkerType.VISUALIZER

        def handle_message(self, message):
            wake = message.payload['wake']
            try:
                wake.send_bytes(b'accepted')
            finally:
                wake.close()
            return WorkerResponse(message.msg_type, message.seq_no, message.correlation_id, True,
                                  payload={'value': message.payload['value']})
    Echo(requests, responses).run()


def test_accepted_control_bytes_cross_real_worker_loop_with_live_wake_transfer():
    from core.process.supervisor import ProcessSupervisor
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, _echo_worker)
    receiver, sender = multiprocessing.Pipe(duplex=False)
    try:
        assert supervisor.start(WorkerType.VISUALIZER)
        correlation = supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW,
                                             {'value': 'once', 'wake': sender})
        assert correlation is not None
        # The submitted snapshot owns its transfer even after the caller closes its original.
        sender.close()
        assert receiver.poll(5) and receiver.recv_bytes() == b'accepted'
        reply = supervisor.await_response(WorkerType.VISUALIZER, correlation, timeout_ms=5000)
        assert reply is not None and reply.success and reply.payload == {'value': 'once'}
    finally:
        sender.close()
        receiver.close()
        supervisor.shutdown()


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='Windows handle ownership regression')
@pytest.mark.parametrize('refusal', ('serialize', 'enqueue'))
def test_unsubmitted_connection_transfers_release_duplicates(refusal):
    receiver, sender = multiprocessing.Pipe(duplex=False)
    class Refused(queue.Queue):
        def put_nowait(self, value):
            raise queue.Full
    channel = Refused() if refusal == 'enqueue' else queue.Queue()
    supervisor = _supervisor(channel)
    try:
        before = _windows_handles()
        for _ in range(8):
            payload = {'wake': sender}
            if refusal == 'serialize':
                payload['bad'] = lambda: None
                with pytest.raises((pickle.PicklingError, AttributeError, TypeError)):
                    supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, payload)
            else:
                assert supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, payload) is None
        assert _windows_handles() == before
        sender.send_bytes(b'original still owned')
        assert receiver.recv_bytes() == b'original still owned'
    finally:
        sender.close()
        receiver.close()
        _close(supervisor)


def _unread_worker(channel, ready, release):
    ready.set()
    release.wait(15)


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='Windows target-process handle ownership')
@pytest.mark.parametrize('_generation', range(3))
def test_accepted_unread_pipe_transfer_dies_with_its_target_not_the_parent(_generation):
    context = multiprocessing.get_context('spawn')
    channel = context.Queue(maxsize=4)
    ready, release = context.Event(), context.Event()
    child = context.Process(target=_unread_worker, args=(channel, ready, release))
    receiver, sender = context.Pipe(duplex=False)
    child.start()
    supervisor = _supervisor(channel, child)
    try:
        assert ready.wait(5)
        channel.put_nowait(b'warm feeder')
        assert channel._reader.poll(5)
        before = _windows_handles()
        assert supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE, {'wake': sender})
        child.terminate()
        child.join(5)
        assert not child.is_alive()
        # Keep the process/queue/original pipe handles open across the reading,
        # so their normal teardown cannot disguise a leaked sender-side duplicate.
        assert _windows_handles() == before
    finally:
        if child.is_alive():
            child.terminate()
            child.join(5)
        _close(supervisor)
        child.close()
        sender.close()
        receiver.close()


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='Windows exact process-handle rollback')
def test_target_death_between_duplication_and_enqueue_refusal_needs_no_pid_lookup():
    context = multiprocessing.get_context('spawn')
    ready, release = context.Event(), context.Event()
    child = context.Process(target=_unread_worker, args=(None, ready, release))
    receiver, sender = context.Pipe(duplex=False)
    class DiesBeforeAdmission(queue.Queue):
        def put_nowait(self, value):
            child.terminate()
            child.join(5)
            assert not child.is_alive()
            raise queue.Full
    child.start()
    supervisor = _supervisor(DiesBeforeAdmission(), child)
    try:
        assert ready.wait(5)
        before = _windows_handles()
        assert supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE, {'wake': sender}) is None
        assert _windows_handles() == before
    finally:
        if child.is_alive():
            child.terminate()
            child.join(5)
        _close(supervisor)
        child.close()
        sender.close()
        receiver.close()


@pytest.mark.parametrize('refusal', ('serialize', 'enqueue'))
def test_never_submitted_sharer_registration_is_locally_reclaimed(refusal):
    """Exercise the stdlib registration path on Windows sockets and POSIX FDs."""
    import socket
    from multiprocessing import connection, resource_sharer
    from core.process.control_messages import _registration_service
    first, second = socket.socketpair()
    sender, receiver = connection.Connection(first.detach()), connection.Connection(second.detach())
    service = _registration_service()
    # This unrelated, unpublished registration must remain entirely untouched.
    closed = []
    unrelated = service.register(lambda *_: None, lambda: closed.append(True))
    class Refused(queue.Queue):
        def put_nowait(self, value):
            raise queue.Full
    supervisor = _supervisor(Refused() if refusal == 'enqueue' else queue.Queue())
    try:
        before = set(service._cache)
        for _ in range(8):
            payload = {'wake': sender}
            if refusal == 'serialize':
                payload['bad'] = lambda: None
                with pytest.raises((pickle.PicklingError, AttributeError, TypeError)):
                    supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, payload)
            else:
                assert supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, payload) is None
            assert set(service._cache) == before and closed == []
        sender.send_bytes(b'original remains usable')
        assert receiver.recv_bytes() == b'original remains usable'
    finally:
        with service._lock:
            _send, close = service._cache.pop(unrelated[1])
        close()
        sender.close()
        receiver.close()
        _close(supervisor)


def test_unsupported_sharer_shape_fails_before_registration(monkeypatch):
    import socket
    from multiprocessing import connection
    from core.process import control_messages
    first, second = socket.socketpair()
    sender = connection.Connection(first.detach())
    channel = queue.Queue()
    supervisor = _supervisor(channel)
    monkeypatch.setattr(control_messages.resource_sharer, '_resource_sharer', SimpleNamespace(_cache=None))
    try:
        with pytest.raises(RuntimeError, match='audited CPython 3.14'):
            supervisor.send_message(WorkerType.VISUALIZER, MessageType.VIS_SET_VIEW, {'wake': sender})
        assert channel.empty()
    finally:
        sender.close()
        second.close()
        _close(supervisor)


def test_unpublished_posix_adapter_claims_only_its_own_registration_once():
    """Pure adapter proof; Windows execution does not establish Linux IPC."""
    import threading
    from core.process.control_messages import _UnsubmittedRegistration
    closed = []
    service = SimpleNamespace(_lock=threading.Lock(), _address='service', _cache={
        7: (lambda *_: None, lambda: closed.append('ours')),
        8: (lambda *_: None, lambda: closed.append('unrelated')),
    })
    rollback = _UnsubmittedRegistration(service, ('service', 7))
    rollback.cancel()
    rollback.cancel()
    assert closed == ['ours'] and set(service._cache) == {8}
    _UnsubmittedRegistration(service, ('another-service', 8)).cancel()
    assert closed == ['ours'] and set(service._cache) == {8}

"""Focused ownership regressions for ImageWorker shared-memory transfers."""
from __future__ import annotations

import uuid
from queue import Empty as QueueEmpty
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QColor

from core.process.shared_memory_transport import (
    SHARED_MEMORY_ACK_ATTACHED,
    SharedMemoryAccounting,
    SharedMemoryDescriptor,
    close_producer_shared_memory,
    create_image_shared_memory,
)
from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerResponse, WorkerState, WorkerType
from core.process.workers.image_worker import ImageWorker
from engine.image_pipeline import load_image_via_worker


def _new_transfer(
    rgba_data: bytes,
    *,
    correlation_id: str = "image-transfer",
    width: int = 2,
    height: int = 1,
) -> tuple[object, SharedMemoryDescriptor, WorkerResponse]:
    name = f"srpss_img_{uuid.uuid4().hex[:12]}"
    producer, descriptor = create_image_shared_memory(rgba_data, name=name)
    response = WorkerResponse(
        msg_type=MessageType.IMAGE_RESULT,
        seq_no=1,
        correlation_id=correlation_id,
        success=True,
        payload={
            "width": width,
            "height": height,
            "format": "RGBA",
            **descriptor.payload_fields(),
        },
    )
    return producer, descriptor, response


def _assert_mapping_gone(name: str) -> None:
    from multiprocessing.shared_memory import SharedMemory

    with pytest.raises(FileNotFoundError):
        SharedMemory(name=name, create=False)


def test_parent_consumes_once_and_returns_live_accounting_to_zero() -> None:
    rgba = bytes((255, 0, 0, 255, 0, 255, 0, 255))
    producer, descriptor, raw_response = _new_transfer(rgba)
    supervisor = ProcessSupervisor()
    try:
        response = supervisor._response_from_data(raw_response.to_dict())
        copied = supervisor.consume_shared_memory_response(
            response,
            lambda view, _descriptor: bytes(view),
        )

        assert copied == rgba
        assert producer.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED
        assert supervisor.get_shared_memory_accounting_snapshot() == {
            "segments_created": 1,
            "segments_live": 0,
            "live_bytes": 0,
            "segments_consumed": 1,
            "segments_reclaimed_late": 0,
            "unlink_failures": 0,
        }
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    _assert_mapping_gone(descriptor.name)


def test_accounting_does_not_retain_completed_transfer_names() -> None:
    accounting = SharedMemoryAccounting()

    for index in range(1000):
        descriptor = SharedMemoryDescriptor(
            name=f"srpss_img_{index:012x}",
            data_size=32,
        )
        accounting.register(descriptor)
        accounting.finalize(descriptor, consumed=True)

    assert accounting._live == {}
    assert not hasattr(accounting, "_known_names")
    assert accounting.snapshot() == {
        "segments_created": 1000,
        "segments_live": 0,
        "live_bytes": 0,
        "segments_consumed": 1000,
        "segments_reclaimed_late": 0,
        "unlink_failures": 0,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("shared_memory_data_size", 0),
        ("shared_memory_handoff_version", 99),
        ("shared_memory_payload_offset", 2),
    ),
)
def test_malformed_descriptor_is_reclaimed_and_accounted(
    field: str,
    value: int,
) -> None:
    rgba = bytes((61, 62, 63, 255, 64, 65, 66, 255))
    producer, descriptor, raw_response = _new_transfer(rgba)
    raw_response.payload[field] = value
    supervisor = ProcessSupervisor()
    try:
        response = supervisor._response_from_data(raw_response.to_dict())
        assert supervisor.dispose_response(
            response,
            reason="malformed_test",
        )
        assert "shared_memory_name" not in response.payload
        assert producer.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED
        assert supervisor.get_shared_memory_accounting_snapshot() == {
            "segments_created": 1,
            "segments_live": 0,
            "live_bytes": 0,
            "segments_consumed": 0,
            "segments_reclaimed_late": 1,
            "unlink_failures": 0,
        }
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    _assert_mapping_gone(descriptor.name)


def test_image_pipeline_copies_directly_from_mapping_into_qt_owned_image() -> None:
    rgba = bytes((255, 0, 0, 255, 0, 255, 0, 255))
    producer, descriptor, raw_response = _new_transfer(rgba)
    supervisor = ProcessSupervisor()
    display_manager = object()
    engine = SimpleNamespace(
        _process_supervisor=supervisor,
        _runtime_generation=7,
        _shutting_down=False,
        display_manager=display_manager,
        settings_manager=None,
    )
    supervisor.is_running = lambda _worker_type: True
    supervisor.send_request_and_await_response = (
        lambda *_args, **_kwargs: supervisor._response_from_data(
            raw_response.to_dict()
        )
    )

    try:
        qimage = load_image_via_worker(
            engine,
            "synthetic.png",
            2,
            1,
        )
        assert qimage is not None
        assert qimage.width() == 2
        assert qimage.height() == 1
        assert qimage.pixelColor(0, 0) == QColor(255, 0, 0, 255)
        assert qimage.pixelColor(1, 0) == QColor(0, 255, 0, 255)
        assert producer.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED
        assert supervisor.get_shared_memory_accounting_snapshot()["live_bytes"] == 0
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    _assert_mapping_gone(descriptor.name)


def test_runtime_generation_rejection_reclaims_before_qimage_copy() -> None:
    rgba = bytes((1, 2, 3, 255, 4, 5, 6, 255))
    producer, descriptor, raw_response = _new_transfer(rgba)
    supervisor = ProcessSupervisor()
    display_manager = object()
    engine = SimpleNamespace(
        _process_supervisor=supervisor,
        _runtime_generation=3,
        _shutting_down=False,
        display_manager=display_manager,
        settings_manager=None,
    )
    supervisor.is_running = lambda _worker_type: True

    def _return_after_generation_change(*_args, **_kwargs):
        engine._runtime_generation = 4
        return supervisor._response_from_data(raw_response.to_dict())

    supervisor.send_request_and_await_response = _return_after_generation_change
    try:
        assert load_image_via_worker(engine, "synthetic.png", 2, 1) is None
        accounting = supervisor.get_shared_memory_accounting_snapshot()
        assert accounting["segments_live"] == 0
        assert accounting["live_bytes"] == 0
        assert accounting["segments_reclaimed_late"] == 1
        assert producer.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    _assert_mapping_gone(descriptor.name)


class _ResponseQueue:
    def __init__(self, items=()) -> None:
        self.items = list(items)
        self.cancelled = False
        self.closed = False
        self.joined = False

    def get(self, timeout=None):
        if not self.items:
            raise QueueEmpty
        return self.items.pop(0)

    def get_nowait(self):
        if not self.items:
            raise QueueEmpty
        return self.items.pop(0)

    def cancel_join_thread(self) -> None:
        self.cancelled = True

    def close(self) -> None:
        self.closed = True

    def join_thread(self) -> None:
        self.joined = True


def test_timeout_then_late_response_is_reclaimed_not_buffered() -> None:
    rgba = bytes((7, 8, 9, 255, 10, 11, 12, 255))
    producer, descriptor, response = _new_transfer(
        rgba,
        correlation_id="late-timeout",
    )
    supervisor = ProcessSupervisor()
    response_queue = _ResponseQueue()
    supervisor._response_queues[WorkerType.IMAGE] = response_queue
    try:
        assert supervisor.await_response(
            WorkerType.IMAGE,
            "late-timeout",
            timeout_ms=1,
            poll_slice_ms=1,
        ) is None

        response_queue.items.append(response.to_dict())
        assert supervisor._drain_worker_response_queue(
            WorkerType.IMAGE,
            dispose_application=False,
            reason="test_heartbeat",
        ) == 1
        assert supervisor._buffered_responses[WorkerType.IMAGE] == {}
        accounting = supervisor.get_shared_memory_accounting_snapshot()
        assert accounting["segments_live"] == 0
        assert accounting["live_bytes"] == 0
        assert accounting["segments_reclaimed_late"] == 1
        assert producer.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    _assert_mapping_gone(descriptor.name)


def test_cancellation_reclaims_already_buffered_response() -> None:
    rgba = bytes((13, 14, 15, 255, 16, 17, 18, 255))
    producer, descriptor, raw_response = _new_transfer(
        rgba,
        correlation_id="cancelled",
    )
    supervisor = ProcessSupervisor()
    try:
        response = supervisor._response_from_data(raw_response.to_dict())
        supervisor._buffer_response(WorkerType.IMAGE, response)

        assert supervisor.abandon_response(
            WorkerType.IMAGE,
            "cancelled",
            reason="cancelled",
        ) == 1
        assert supervisor._buffered_responses[WorkerType.IMAGE] == {}
        accounting = supervisor.get_shared_memory_accounting_snapshot()
        assert accounting["segments_live"] == 0
        assert accounting["segments_reclaimed_late"] == 1
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    _assert_mapping_gone(descriptor.name)


def test_supervisor_shutdown_disposes_buffered_shared_memory() -> None:
    rgba = bytes((19, 20, 21, 255, 22, 23, 24, 255))
    producer, descriptor, raw_response = _new_transfer(
        rgba,
        correlation_id="shutdown-buffer",
    )
    supervisor = ProcessSupervisor()
    response = supervisor._response_from_data(raw_response.to_dict())
    supervisor._buffer_response(WorkerType.IMAGE, response)

    supervisor.shutdown()
    try:
        accounting = supervisor.get_shared_memory_accounting_snapshot()
        assert accounting["segments_live"] == 0
        assert accounting["live_bytes"] == 0
        assert accounting["segments_reclaimed_late"] == 1
        assert producer.buf[descriptor.ack_offset] == SHARED_MEMORY_ACK_ATTACHED
    finally:
        close_producer_shared_memory(producer, attached=True)
    _assert_mapping_gone(descriptor.name)


def test_response_buffer_overflow_disposes_dropped_shared_memory() -> None:
    first_producer, first_descriptor, first_raw = _new_transfer(
        bytes((49, 50, 51, 255, 52, 53, 54, 255)),
        correlation_id="overflow-first",
    )
    second_producer, second_descriptor, second_raw = _new_transfer(
        bytes((55, 56, 57, 255, 58, 59, 60, 255)),
        correlation_id="overflow-second",
    )
    supervisor = ProcessSupervisor()
    supervisor.MAX_BUFFERED_RESPONSES = 1
    try:
        supervisor._buffer_response(
            WorkerType.IMAGE,
            supervisor._response_from_data(first_raw.to_dict()),
        )
        supervisor._buffer_response(
            WorkerType.IMAGE,
            supervisor._response_from_data(second_raw.to_dict()),
        )

        assert first_producer.buf[
            first_descriptor.ack_offset
        ] == SHARED_MEMORY_ACK_ATTACHED
        accounting = supervisor.get_shared_memory_accounting_snapshot()
        assert accounting["segments_created"] == 2
        assert accounting["segments_live"] == 1
        assert accounting["live_bytes"] == second_descriptor.data_size
        assert accounting["segments_reclaimed_late"] == 1
        assert list(supervisor._buffered_responses[WorkerType.IMAGE]) == [
            "overflow-second"
        ]
    finally:
        supervisor.shutdown()
        close_producer_shared_memory(first_producer, attached=True)
        close_producer_shared_memory(second_producer, attached=True)
    _assert_mapping_gone(first_descriptor.name)
    _assert_mapping_gone(second_descriptor.name)


def test_worker_publish_failure_reclaims_creator_mapping() -> None:
    rgba = bytes((25, 26, 27, 255, 28, 29, 30, 255))
    producer, descriptor, response = _new_transfer(
        rgba,
        correlation_id="publish-failed",
    )

    class _FailingQueue:
        def put_nowait(self, _item):
            raise RuntimeError("queue full")

    worker = ImageWorker(_ResponseQueue(), _FailingQueue())
    worker._pending_shared_transfers[response.correlation_id] = (
        producer,
        descriptor,
    )

    assert worker._send_response(response) is False
    assert worker._pending_shared_transfers == {}
    _assert_mapping_gone(descriptor.name)


def test_worker_closes_after_parent_attachment_without_lifetime_retention() -> None:
    from multiprocessing.shared_memory import SharedMemory

    rgba = bytes((31, 32, 33, 255, 34, 35, 36, 255))
    producer, descriptor, response = _new_transfer(
        rgba,
        correlation_id="attached",
    )
    parent_mapping = SharedMemory(name=descriptor.name, create=False)
    parent_mapping.buf[descriptor.ack_offset] = SHARED_MEMORY_ACK_ATTACHED

    class _AcceptingQueue:
        def put_nowait(self, _item):
            return None

    worker = ImageWorker(_ResponseQueue(), _AcceptingQueue())
    worker._pending_shared_transfers[response.correlation_id] = (
        producer,
        descriptor,
    )
    assert worker._send_response(response) is True
    assert worker._pending_shared_transfers == {}
    assert bytes(
        parent_mapping.buf[
            descriptor.payload_offset:descriptor.required_size
        ]
    ) == rgba

    parent_mapping.close()
    parent_mapping.unlink()
    _assert_mapping_gone(descriptor.name)


def test_worker_cleanup_during_unpublished_transfer_leaves_no_orphan() -> None:
    rgba = bytes((37, 38, 39, 255, 40, 41, 42, 255))
    producer, descriptor, response = _new_transfer(
        rgba,
        correlation_id="worker-shutdown",
    )
    worker = ImageWorker(_ResponseQueue(), _ResponseQueue())
    worker._pending_shared_transfers[response.correlation_id] = (
        producer,
        descriptor,
    )

    worker._cleanup()

    assert worker._pending_shared_transfers == {}
    _assert_mapping_gone(descriptor.name)


def test_cleanup_worker_drains_queue_before_closing_it() -> None:
    rgba = bytes((43, 44, 45, 255, 46, 47, 48, 255))
    producer, descriptor, response = _new_transfer(
        rgba,
        correlation_id="cleanup-queue",
    )
    supervisor = ProcessSupervisor()
    response_queue = _ResponseQueue([response.to_dict()])

    class _Process:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    process = _Process()
    supervisor._workers[WorkerType.IMAGE] = process
    supervisor._request_queues[WorkerType.IMAGE] = _ResponseQueue()
    supervisor._response_queues[WorkerType.IMAGE] = response_queue
    supervisor._health[WorkerType.IMAGE].state = WorkerState.RUNNING
    try:
        supervisor._cleanup_worker(WorkerType.IMAGE)
        accounting = supervisor.get_shared_memory_accounting_snapshot()
        assert accounting["segments_live"] == 0
        assert accounting["segments_reclaimed_late"] == 1
        assert response_queue.closed is True
        assert process.closed is True
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    _assert_mapping_gone(descriptor.name)

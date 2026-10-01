"""Spawned-process contract for bounded ImageWorker prefetch batches.

The batch deliberately uses QImage only: no QApplication fixture is supplied or
created here.  That catches accidental GUI dependencies in the worker path.
"""
from __future__ import annotations

import multiprocessing
import os
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication, QImage

import core.process.workers.image_worker as image_worker_module
from core.process.shared_memory_transport import SharedMemoryDescriptor, SharedMemoryReadLease
from core.process.types import MessageType, WorkerMessage, WorkerResponse, WorkerType
from core.process.workers.image_worker import ImageWorker, image_worker_main
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor


def _image_worker_without_gui(request_queue: Any, response_queue: Any) -> None:
    """Assert the spawned worker owns no QApplication before handling QImages."""
    assert QGuiApplication.instance() is None
    image_worker_main(request_queue, response_queue)


def _packed_rgba8888(qimage: QImage) -> bytes:
    rgba = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = int(rgba.width()), int(rgba.height())
    packed_stride = width * 4
    stride = int(rgba.bytesPerLine())
    data = rgba.constBits().tobytes()
    if stride == packed_stride:
        return data[: packed_stride * height]
    return b"".join(
        data[row * stride: row * stride + packed_stride]
        for row in range(height)
    )


def _expected_derivative(path: str, width: int, height: int, mode: str) -> bytes:
    source = QImage(path)
    assert not source.isNull()
    processed = AsyncImageProcessor.process_qimage(
        source,
        QSize(width, height),
        DisplayMode.from_string(mode),
        resample_filter="smooth",
        sharpen=False,
    )
    return _packed_rgba8888(processed)


def _write_gradient_source(
    path: Path,
    size: tuple[int, int],
    *,
    transparent: bool,
) -> None:
    """Write a nonuniform source so one derivative cannot stand in for another."""
    width, height = size
    pixels = [
        (
            (x * 47 + y * 13) % 256,
            (x * 19 + y * 71) % 256,
            (x * 89 + y * 23) % 256,
            ((x * 31 + y * 17) % 255) if transparent else 255,
        )
        for y in range(height)
        for x in range(width)
    ]
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    if not transparent:
        image = image.convert("RGB")
    image.save(path)


def _resolved_derivatives(
    derivatives: list[dict[str, object]],
    *,
    resample_filter: str = "smooth",
    sharpen: bool = False,
) -> list[dict[str, object]]:
    return [
        {
            "resample_filter": resample_filter,
            "sharpen": sharpen,
            **derivative,
        }
        for derivative in derivatives
    ]


def _await_response(response_queue: Any, correlation_id: str) -> WorkerResponse:
    while True:
        response = WorkerResponse.from_dict(response_queue.get(timeout=15.0))
        if response.correlation_id == correlation_id and response.msg_type in {
            MessageType.IMAGE_RESULT,
            MessageType.ERROR,
        }:
            return response


def _stop_worker(
    process: multiprocessing.Process,
    request_queue: Any,
    response_queue: Any,
) -> None:
    if process.is_alive():
        request_queue.put(
            WorkerMessage(
                msg_type=MessageType.SHUTDOWN,
                seq_no=99,
                correlation_id="batch-test-shutdown",
                worker_type=WorkerType.IMAGE,
            ).to_dict()
        )
    process.join(timeout=10.0)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5.0)
    request_queue.close()
    response_queue.close()


def _run_batch(
    path: str,
    derivatives: list[dict[str, object]],
) -> tuple[WorkerResponse, bytes, SharedMemoryDescriptor | None]:
    context = multiprocessing.get_context("spawn")
    request_queue = context.Queue()
    response_queue = context.Queue()
    process = context.Process(
        target=_image_worker_without_gui,
        args=(request_queue, response_queue),
    )
    process.start()
    try:
        ready = WorkerResponse.from_dict(response_queue.get(timeout=15.0))
        assert ready.msg_type == MessageType.WORKER_READY
        assert ready.success
        request_queue.put(
            WorkerMessage(
                msg_type=MessageType.IMAGE_PREFETCH_BATCH,
                seq_no=1,
                correlation_id="prefetch-batch",
                worker_type=WorkerType.IMAGE,
                payload={
                    "path": path,
                    "generation": 37,
                    "derivatives": _resolved_derivatives(derivatives),
                },
            ).to_dict()
        )
        response = _await_response(response_queue, "prefetch-batch")
        if not response.success:
            return response, b"", None
        transferred, descriptor = _consume_batch_payload(response.payload)
        return response, transferred, descriptor
    finally:
        _stop_worker(process, request_queue, response_queue)


def _consume_batch_payload(payload: dict[str, object]) -> tuple[bytes, SharedMemoryDescriptor]:
    descriptor = SharedMemoryDescriptor.from_payload(payload)
    assert descriptor is not None
    lease = SharedMemoryReadLease(descriptor)
    try:
        return bytes(lease.open()), descriptor
    finally:
        lease.close()


@pytest.mark.parametrize(
    ("source_size", "transparent", "derivatives"),
    [
        (
            (91, 37),
            False,
            [
                {"cache_key": "wide-fill", "width": 48, "height": 48, "mode": "fill"},
                {"cache_key": "wide-fit", "width": 48, "height": 48, "mode": "fit"},
                {"cache_key": "wide-perfect", "width": 91, "height": 37, "mode": "shrink"},
            ],
        ),
        (
            (37, 91),
            True,
            [
                {"cache_key": "tall-fill", "width": 48, "height": 48, "mode": "fill"},
                {"cache_key": "tall-fit", "width": 48, "height": 48, "mode": "fit"},
                {"cache_key": "tall-shrink", "width": 71, "height": 43, "mode": "shrink"},
            ],
        ),
        (
            (23, 13),
            False,
            [
                {"cache_key": "rounding-fill", "width": 16, "height": 9, "mode": "fill"},
                {"cache_key": "rounding-fit", "width": 16, "height": 9, "mode": "fit"},
                {"cache_key": "rounding-portrait", "width": 9, "height": 16, "mode": "fill"},
            ],
        ),
    ],
)
def test_spawned_batch_matches_qimage_derivatives_and_reclaims_one_transfer(
    tmp_path: Path,
    source_size: tuple[int, int],
    transparent: bool,
    derivatives: list[dict[str, object]],
) -> None:
    source_path = tmp_path / "source.png"
    _write_gradient_source(source_path, source_size, transparent=transparent)

    response, transferred, descriptor = _run_batch(str(source_path), derivatives)

    assert response.success
    assert response.msg_type == MessageType.IMAGE_RESULT
    payload = response.payload
    assert payload["path"] == str(source_path)
    assert payload["generation"] == 37
    assert payload["decode_count"] == 1
    assert payload["worker_pid"] != os.getpid()
    assert "rgba_data" not in payload
    assert payload["decode_started_ns"] <= payload["decode_finished_ns"]
    assert payload["decode_finished_ns"] <= payload["scale_started_ns"]
    assert payload["scale_started_ns"] <= payload["scale_finished_ns"]

    assert descriptor is not None
    response_derivatives = payload["derivatives"]
    assert isinstance(response_derivatives, list)
    assert len(response_derivatives) == len(derivatives)
    assert len(transferred) == descriptor.data_size

    cursor = 0
    for request, metadata in zip(derivatives, response_derivatives, strict=True):
        assert isinstance(metadata, dict)
        width = request["width"]
        height = request["height"]
        mode = request["mode"]
        assert isinstance(width, int)
        assert isinstance(height, int)
        assert isinstance(mode, str)
        expected = _expected_derivative(str(source_path), width, height, mode)
        assert metadata == {
            "cache_key": request["cache_key"],
            "width": width,
            "height": height,
            "mode": mode,
            "resample_filter": "smooth",
            "sharpen": False,
            "offset": cursor,
            "size": len(expected),
        }
        actual = transferred[cursor:cursor + len(expected)]
        assert actual == expected
        assert actual[3::4] == b"\xff" * (width * height)
        cursor += len(expected)
    assert cursor == len(transferred)

    with pytest.raises(FileNotFoundError):
        SharedMemory(name=descriptor.name, create=False)


@pytest.mark.parametrize(
    ("derivatives", "error_text"),
    [
        (
            [
                {
                    "cache_key": "too-large",
                    "width": 8192,
                    "height": 8192,
                    "mode": "fill",
                }
            ],
            "128 MiB",
        ),
        (
            [
                {
                    "cache_key": f"derivative-{index}",
                    "width": 1,
                    "height": 1,
                    "mode": "fill",
                }
                for index in range(17)
            ],
            "at most 16",
        ),
    ],
)
def test_batch_rejects_bounded_request_before_decode(
    derivatives: list[dict[str, object]],
    error_text: str,
) -> None:
    context = multiprocessing.get_context("spawn")
    request_queue = context.Queue()
    response_queue = context.Queue()
    process = context.Process(
        target=_image_worker_without_gui,
        args=(request_queue, response_queue),
    )
    process.start()
    try:
        ready = WorkerResponse.from_dict(response_queue.get(timeout=15.0))
        assert ready.msg_type == MessageType.WORKER_READY
        request_queue.put(
            WorkerMessage(
                msg_type=MessageType.IMAGE_PREFETCH_BATCH,
                seq_no=1,
                correlation_id="oversized-batch",
                worker_type=WorkerType.IMAGE,
                payload={
                    "path": "does-not-need-to-exist.png",
                    "generation": 1,
                    "derivatives": _resolved_derivatives(derivatives),
                },
            ).to_dict()
        )
        response = _await_response(response_queue, "oversized-batch")
        assert not response.success
        assert response.msg_type == MessageType.ERROR
        assert error_text in (response.error or "")
    finally:
        _stop_worker(process, request_queue, response_queue)


class _MemoryQueue:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    def put_nowait(self, item: dict[str, object]) -> None:
        self.items.append(item)


def test_batch_decodes_the_source_once_for_all_derivatives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "source.png"
    _write_gradient_source(source_path, (64, 41), transparent=True)
    worker = ImageWorker(_MemoryQueue(), _MemoryQueue())
    decoded_paths: list[str] = []
    original_decode = worker._decode_qimage

    def _spy_decode(path: str) -> QImage:
        decoded_paths.append(path)
        return original_decode(path)

    monkeypatch.setattr(worker, "_decode_qimage", _spy_decode)
    try:
        response = worker.handle_message(
            WorkerMessage(
                msg_type=MessageType.IMAGE_PREFETCH_BATCH,
                seq_no=1,
                correlation_id="decode-once",
                worker_type=WorkerType.IMAGE,
                payload={
                    "path": str(source_path),
                    "generation": 1,
                    "derivatives": _resolved_derivatives([
                        {"cache_key": "fill", "width": 32, "height": 32, "mode": "fill"},
                        {"cache_key": "fit", "width": 32, "height": 32, "mode": "fit"},
                        {"cache_key": "shrink", "width": 48, "height": 30, "mode": "shrink"},
                    ]),
                },
            )
        )
        assert response is not None
        assert response.success
        assert decoded_paths == [str(source_path)]
        assert response.payload["decode_count"] == 1
        assert response.payload["scale_started_ns"] <= response.payload["scale_finished_ns"]
    finally:
        worker._cleanup()


@pytest.mark.parametrize(
    ("resample_filter", "sharpen"),
    [(name, sharpen) for name in ("smooth", "hamming", "lanczos") for sharpen in (False, True)],
)
def test_spawned_batch_is_byte_identical_to_foreground_derivative(
    tmp_path: Path,
    resample_filter: str,
    sharpen: bool,
) -> None:
    """Speculation must return the exact selected foreground quality pixels."""
    source_path = tmp_path / "quality-gradient.png"
    _write_gradient_source(source_path, (91, 37), transparent=True)
    derivatives = [
        {"cache_key": "fill", "width": 48, "height": 48, "mode": "fill"},
        {"cache_key": "fit", "width": 48, "height": 48, "mode": "fit"},
    ]
    response, transferred, _descriptor = _run_batch(
        str(source_path),
        _resolved_derivatives(
            derivatives,
            resample_filter=resample_filter,
            sharpen=sharpen,
        ),
    )
    assert response.success

    foreground = ImageWorker(_MemoryQueue(), _MemoryQueue())
    try:
        cursor = 0
        metadata = response.payload["derivatives"]
        assert isinstance(metadata, list)
        for request, entry in zip(derivatives, metadata, strict=True):
            assert isinstance(entry, dict)
            assert entry["resample_filter"] == resample_filter
            assert entry["sharpen"] is sharpen
            expected, width, height, _original = foreground._prescale_rgba(
                str(source_path),
                int(request["width"]),
                int(request["height"]),
                str(request["mode"]),
                resample_filter,
                sharpen,
            )
            assert (width, height) == (request["width"], request["height"])
            size = int(entry["size"])
            assert transferred[cursor:cursor + size] == expected
            cursor += size
        assert cursor == len(transferred)
    finally:
        foreground._cleanup()


def test_quality_batch_decodes_one_pillow_source_for_all_derivatives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "quality-source.png"
    _write_gradient_source(source_path, (64, 41), transparent=False)
    worker = ImageWorker(_MemoryQueue(), _MemoryQueue())
    decoded_paths: list[str] = []
    original_decode = image_worker_module.decode_image

    def _spy_decode(path: str):
        decoded_paths.append(path)
        return original_decode(path)

    monkeypatch.setattr(image_worker_module, "decode_image", _spy_decode)
    try:
        response = worker.handle_message(
            WorkerMessage(
                msg_type=MessageType.IMAGE_PREFETCH_BATCH,
                seq_no=1,
                correlation_id="quality-decode-once",
                worker_type=WorkerType.IMAGE,
                payload={
                    "path": str(source_path),
                    "generation": 1,
                    "derivatives": _resolved_derivatives(
                        [
                            {"cache_key": "fill", "width": 32, "height": 32, "mode": "fill"},
                            {"cache_key": "fit", "width": 32, "height": 32, "mode": "fit"},
                        ],
                        resample_filter="hamming",
                    ),
                },
            )
        )
        assert response is not None and response.success
        assert decoded_paths == [str(source_path)]
        assert response.payload["decode_count"] == 1
    finally:
        worker._cleanup()


def test_worker_rejects_mixed_quality_batch_before_source_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = ImageWorker(_MemoryQueue(), _MemoryQueue())
    decoded_paths: list[str] = []

    def _unexpected_decode(path: str) -> QImage:
        decoded_paths.append(path)
        raise AssertionError("mixed quality must be rejected before a source decode")

    monkeypatch.setattr(worker, "_decode_qimage", _unexpected_decode)
    try:
        response = worker.handle_message(
            WorkerMessage(
                msg_type=MessageType.IMAGE_PREFETCH_BATCH,
                seq_no=1,
                correlation_id="mixed-quality",
                worker_type=WorkerType.IMAGE,
                payload={
                    "path": "does-not-need-to-exist.png",
                    "generation": 1,
                    "derivatives": [
                        *_resolved_derivatives([
                            {"cache_key": "smooth", "width": 8, "height": 8, "mode": "fill"},
                        ]),
                        *_resolved_derivatives([
                            {"cache_key": "lanczos", "width": 8, "height": 8, "mode": "fill"},
                        ], resample_filter="lanczos"),
                    ],
                },
            )
        )
        assert response is not None and not response.success
        assert response.msg_type is MessageType.ERROR
        assert "share one resolved resample filter" in (response.error or "")
        assert decoded_paths == []
    finally:
        worker._cleanup()


def test_batch_shared_memory_failure_is_an_error_not_an_inline_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.png"
    Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(source_path)
    worker = ImageWorker(_MemoryQueue(), _MemoryQueue())

    def _fail_shared_memory(*_args: object, **_kwargs: object) -> object:
        raise OSError("synthetic shared-memory failure")

    monkeypatch.setattr(image_worker_module, "create_image_shared_memory", _fail_shared_memory)
    response = worker.handle_message(
        WorkerMessage(
            msg_type=MessageType.IMAGE_PREFETCH_BATCH,
            seq_no=1,
            correlation_id="shared-memory-failure",
            worker_type=WorkerType.IMAGE,
            payload={
                "path": str(source_path),
                "generation": 1,
                "derivatives": _resolved_derivatives([
                    {
                        "cache_key": "only",
                        "width": 8,
                        "height": 8,
                        "mode": "fill",
                    }
                ]),
            },
        )
    )

    assert response is not None
    assert not response.success
    assert response.msg_type == MessageType.ERROR
    assert "shared-memory publication failed" in (response.error or "")
    assert "rgba_data" not in response.payload

"""Production constructor and packed-response ownership bars for prefetch."""
from __future__ import annotations

import ast
import gc
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import uuid
import weakref

import pytest

from core.process.shared_memory_transport import close_producer_shared_memory, create_image_shared_memory
from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerResponse, WorkerType
from engine.image_pipeline import (
    ImageProcessingInfrastructureError,
    ImageProcessingStaleRuntimeError,
    build_image_prefetcher,
    derive_prefetch_via_worker,
)
from rendering.display_modes import DisplayMode

ROOT = Path(__file__).resolve().parents[1]


class _DeliverySupervisor(ProcessSupervisor):
    def __init__(self):
        super().__init__()
        self.sent = []
        self.callback = None
        self.abandoned = []

    def is_running(self, role):
        return role is WorkerType.IMAGE_PREFETCH

    def send_message(self, role, kind, payload, correlation_id=None):
        self.sent.append((role, kind, payload))
        return "test-prefetch"

    def register_response_callback(self, role, correlation, callback):
        assert role is WorkerType.IMAGE_PREFETCH
        assert correlation == "test-prefetch"
        self.callback = callback
        return True

    def abandon_response(self, role, correlation, *, reason):
        self.abandoned.append((role, correlation, reason))


def _request(key, width):
    return {"cache_key": key, "width": width, "height": 1, "display_mode": DisplayMode.FILL, "resample_filter": "smooth", "sharpen": False}


def _response(supervisor, *, mutate=None):
    rgba = bytes((255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255))
    producer, descriptor = create_image_shared_memory(rgba, name=f"srpss_img_{uuid.uuid4().hex[:12]}")
    payload = {
        "path": "photo.png", "generation": 7, "decode_count": 1,
        "worker_pid": os.getpid() + 100, "format": "RGBA",
        "derivatives": [
            {"cache_key": "large", "width": 2, "height": 1, "mode": "fill", "resample_filter": "smooth", "sharpen": False, "offset": 0, "size": 8},
            {"cache_key": "small", "width": 1, "height": 1, "mode": "fill", "resample_filter": "smooth", "sharpen": False, "offset": 8, "size": 4},
        ],
        **descriptor.payload_fields(),
    }
    if mutate:
        mutate(payload)
    response = supervisor._response_from_data(WorkerResponse(
        msg_type=MessageType.IMAGE_RESULT, seq_no=1, correlation_id="test-prefetch",
        success=True, payload=payload,
    ).to_dict())
    return producer, response


def _engine(supervisor):
    return SimpleNamespace(_process_supervisor=supervisor, _runtime_generation=0,
                           display_manager=object(), _shutting_down=False)


def test_production_has_one_prefetch_constructor_and_both_routes_use_it():
    calls = []
    for directory in ("core", "engine", "rendering", "utils", "ui"):
        for path in (ROOT / directory).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ImagePrefetcher":
                    calls.append(path.relative_to(ROOT).as_posix())
    assert calls == ["engine/image_pipeline.py"]
    for filename in ("engine/screensaver_engine.py", "engine/engine_handlers.py"):
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8-sig"))
        assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "build_image_prefetcher" for node in ast.walk(tree))


def test_constructor_uses_canonical_budget_without_retaining_engine():
    class Engine:
        pass

    engine = Engine()
    engine._image_cache = SimpleNamespace(max_memory_bytes=256 * 1024 * 1024)
    engine.settings_manager = SimpleNamespace(get=lambda key: 4 if key == "cache.max_concurrent" else None)
    prefetcher = build_image_prefetcher(engine)
    assert prefetcher.snapshot_budget_state()["max_pending_requests"] == 16
    reference = weakref.ref(engine)
    del engine
    gc.collect()
    assert reference() is None
    delivered = []
    cancel = prefetcher._derive("photo.png", [], 0, lambda images, error: delivered.append((images, error)))
    assert delivered[0][0] == {}
    assert isinstance(delivered[0][1], ImageProcessingStaleRuntimeError)
    cancel()


@pytest.mark.parametrize("ahead,resample_filter,sharpen,limit,enabled,expected", [
    (4, "smooth", False, 2, True, [WorkerType.IMAGE, WorkerType.IMAGE_PREFETCH]),
    (0, "smooth", False, 2, True, [WorkerType.IMAGE]),
    (4, "lanczos", False, 2, True, [WorkerType.IMAGE, WorkerType.IMAGE_PREFETCH]),
    (4, "hamming", True, 2, True, [WorkerType.IMAGE, WorkerType.IMAGE_PREFETCH]),
    (4, "smooth", False, 1, True, [WorkerType.IMAGE]),
    (4, "smooth", False, 2, False, []),
])
def test_worker_startup_admits_speculation_only_for_selected_quality_and_budget(ahead, resample_filter, sharpen, limit, enabled, expected):
    from engine.screensaver_engine import ScreensaverEngine

    values = {"workers.max_workers": limit, "workers.image.enabled": enabled,
              "display.resample_filter": resample_filter, "display.sharpen_downscale": sharpen}
    started = []
    engine = SimpleNamespace(
        _process_supervisor=SimpleNamespace(start=lambda role: started.append(role) or True),
        _prefetch_ahead=ahead,
        settings_manager=SimpleNamespace(get=values.__getitem__, get_bool=values.__getitem__,
                                         get_application_name=lambda: "Screensaver"),
    )
    ScreensaverEngine._start_workers(engine)
    assert started == expected


def test_async_transport_detaches_all_derivatives_and_finalizes_once():
    supervisor = _DeliverySupervisor()
    delivered = []
    producer, response = _response(supervisor)
    try:
        cancel = derive_prefetch_via_worker(_engine(supervisor), "photo.png", [_request("large", 2), _request("small", 1)], 7,
                                          lambda images, error: delivered.append((images, error)))
        assert supervisor.sent[0][0] is WorkerType.IMAGE_PREFETCH
        assert supervisor.sent[0][1] is MessageType.IMAGE_PREFETCH_BATCH
        supervisor.callback(response)
        images, error = delivered[0]
        assert error is None
        assert images["large"].pixelColor(1, 0).green() == 255
        assert images["small"].pixelColor(0, 0).blue() == 255
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_consumed"] == 1
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_live"] == 0
        cancel()
        assert supervisor.abandoned == []
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()
    # Detached QImages remain usable after both mapping owners are gone.
    assert images["large"].pixelColor(0, 0).red() == 255


@pytest.mark.parametrize("mutate", [
    lambda payload: payload.update(generation=8),
    lambda payload: payload.update(worker_pid=os.getpid()),
    lambda payload: payload["derivatives"][1].update(offset=4),
    lambda payload: payload.update(shared_memory_data_size=8),
    lambda payload: payload.update(decode_count=2),
    lambda payload: payload["derivatives"][0].update(resample_filter="hamming"),
    lambda payload: payload["derivatives"][0].update(sharpen=True),
])
def test_bad_response_reclaims_shared_memory_and_never_publishes(mutate):
    supervisor = _DeliverySupervisor()
    delivered = []
    producer, response = _response(supervisor, mutate=mutate)
    try:
        derive_prefetch_via_worker(_engine(supervisor), "photo.png", [_request("large", 2), _request("small", 1)], 7,
                                   lambda images, error: delivered.append((images, error)))
        supervisor.callback(response)
        assert delivered[0][0] == {}
        assert isinstance(delivered[0][1], ImageProcessingInfrastructureError)
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_live"] == 0
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()


def test_manifest_rejection_reports_expected_and_actual_geometry(caplog):
    from core.logging.logger import ColoredFormatter

    supervisor = _DeliverySupervisor()
    delivered = []
    image_path = r"C:\wall papers\photo.png"

    def malformed(payload):
        payload["path"] = image_path
        payload["derivatives"][0]["width"] = 1

    producer, response = _response(supervisor, mutate=malformed)
    try:
        derive_prefetch_via_worker(
            _engine(supervisor), image_path, [_request("large", 2), _request("small", 1)], 7,
            lambda images, error: delivered.append((images, error)),
        )
        supervisor.callback(response)
        images, error = delivered[0]
        assert images == {} and isinstance(error, ImageProcessingInfrastructureError)
        expected, actual = str(error).split("actual=", 1)
        assert "RGBA manifest contract failed derivative=0 expected=" in expected
        assert "'width': 2" in expected and "'height': 1" in expected
        assert "'width': 1" in actual and "'height': 1" in actual
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_live"] == 0
        record = next(record for record in caplog.records if "Worker batch aborted" in record.getMessage())
        formatted = ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", use_color=False,
        ).format(record)
        assert image_path in formatted  # Spaces must not split the path into unrelated table/prose fields.
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()


def test_rounding_source_crosses_spawned_worker_and_real_parent_consumer(tmp_path):
    from PIL import Image
    from core.process.workers.image_worker import speculative_image_worker_main

    source = tmp_path / "near aspect source.png"
    Image.new("RGB", (23, 13), (31, 97, 173)).save(source)
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.IMAGE_PREFETCH, speculative_image_worker_main)
    completed = threading.Event()
    delivered = []

    def complete(images, error):
        delivered.append((images, error))
        completed.set()

    requests = [
        {"cache_key": "wide", "width": 16, "height": 9, "display_mode": DisplayMode.FILL, "resample_filter": "smooth", "sharpen": False},
        {"cache_key": "tall", "width": 9, "height": 16, "display_mode": DisplayMode.FILL, "resample_filter": "smooth", "sharpen": False},
    ]
    try:
        assert supervisor.start(WorkerType.IMAGE_PREFETCH)
        cancel = derive_prefetch_via_worker(_engine(supervisor), str(source), requests, 7, complete)
        assert completed.wait(15), "Worker callback did not complete"
        images, error = delivered[0]
        assert error is None
        assert set(images) == {"wide", "tall"}
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_consumed"] == 1
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_live"] == 0
        cancel()
    finally:
        supervisor.shutdown()
    # The strict consumer admitted exact canvases, and Qt owns their pixels
    # after both worker and mappings retire. A padded underfill cannot pass.
    for request in requests:
        image = images[request["cache_key"]]
        assert (image.width(), image.height()) == (request["width"], request["height"])
        for x in (0, image.width() - 1):
            for y in (0, image.height() - 1):
                assert image.pixelColor(x, y).getRgb() == (31, 97, 173, 255)


def test_cancelled_or_retired_response_is_reclaimed_before_publication():
    supervisor = _DeliverySupervisor()
    delivered = []
    producer, response = _response(supervisor)
    try:
        cancel = derive_prefetch_via_worker(_engine(supervisor), "photo.png", [_request("large", 2), _request("small", 1)], 7,
                                          lambda images, error: delivered.append((images, error)))
        cancel()
        cancel()
        assert len(supervisor.abandoned) == 1
        supervisor.callback(response)
        assert delivered == []
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_live"] == 0
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()


def test_runtime_generation_zero_is_valid_and_replacement_rejects_response():
    supervisor = _DeliverySupervisor()
    delivered = []
    producer, response = _response(supervisor)
    engine = _engine(supervisor)
    try:
        derive_prefetch_via_worker(engine, "photo.png", [_request("large", 2), _request("small", 1)], 7,
                                   lambda images, error: delivered.append((images, error)))
        engine._runtime_generation = 1
        supervisor.callback(response)
        assert delivered[0][0] == {}
        assert isinstance(delivered[0][1], ImageProcessingStaleRuntimeError)
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_live"] == 0
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()


def test_completion_exception_surfaces_once_after_mapping_finalization():
    supervisor = _DeliverySupervisor()
    producer, response = _response(supervisor)
    completion_count = 0

    def _raising_complete(_images, _error):
        nonlocal completion_count
        completion_count += 1
        raise RuntimeError("synthetic cache completion failure")

    try:
        derive_prefetch_via_worker(
            _engine(supervisor),
            "photo.png",
            [_request("large", 2), _request("small", 1)],
            7,
            _raising_complete,
        )
        with pytest.raises(RuntimeError, match="synthetic cache completion failure"):
            supervisor.callback(response)
        assert completion_count == 1
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_consumed"] == 1
        assert supervisor.get_shared_memory_accounting_snapshot()["segments_live"] == 0
    finally:
        close_producer_shared_memory(producer, attached=True)
        supervisor.shutdown()

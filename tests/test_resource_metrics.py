from __future__ import annotations

import json
import logging
from types import MappingProxyType, SimpleNamespace

from core.performance import resource_metrics


class _Owner:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def get_accounting_snapshot(self):
        return self._snapshot


def _engine():
    cache = _Owner(
        MappingProxyType(
            {
                "resources": (
                    MappingProxyType(
                        {
                            "owner": "decode-cache",
                            "generation": 4,
                            "dimensions": (20, 10),
                            "format": "Format_ARGB32",
                            "tracked_bytes": 800,
                            "lease_count": None,
                        }
                    ),
                ),
            }
        )
    )
    manager = _Owner(
        MappingProxyType(
            {
                "resources": (
                    MappingProxyType(
                        {
                            "resource_id": "texture-1",
                            "resource_type": "NATIVE_HANDLE",
                            "gl_handle_type": "texture",
                            "owner": "compositor:1",
                            "generation": 9,
                            "dimensions": (4, 8),
                            "format": "RGBA8",
                            "tracked_bytes": 128,
                            "lease_count": None,
                        }
                    ),
                    MappingProxyType(
                        {
                            "resource_id": "pbo-1",
                            "resource_type": "NATIVE_HANDLE",
                            "gl_handle_type": "vbo",
                            "owner": "compositor:1",
                            "generation": 9,
                            "dimensions": None,
                            "format": "PIXEL_UNPACK_BUFFER",
                            "tracked_bytes": 256,
                            "lease_count": None,
                        }
                    ),
                    MappingProxyType(
                        {
                            "resource_id": "program-1",
                            "resource_type": "NATIVE_HANDLE",
                            "gl_handle_type": "program",
                            "owner": "compositor:1",
                            "generation": 9,
                            "dimensions": None,
                            "format": "GL_PROGRAM",
                            "tracked_bytes": None,
                            "lease_count": None,
                        }
                    ),
                    MappingProxyType(
                        {
                            "resource_id": "query-1",
                            "resource_type": "NATIVE_HANDLE",
                            "gl_handle_type": "query",
                            "owner": "visualizer:1",
                            "generation": 9,
                            "dimensions": None,
                            "format": "GL_TIME_ELAPSED",
                            "tracked_bytes": None,
                            "lease_count": None,
                        }
                    ),
                ),
            }
        )
    )
    return SimpleNamespace(_image_cache=cache, resource_manager=manager)


def test_collect_resource_accounting_keeps_exact_known_bytes_and_unknowns():
    snapshot = resource_metrics.collect_resource_accounting(_engine())

    assert snapshot.cpu_cache_bytes == 800
    assert snapshot.registry_known_bytes == 384
    assert snapshot.gl_known_bytes == 384
    assert snapshot.gl_unknown_resources == 2
    assert snapshot.gl_texture_bytes == 128
    assert snapshot.gl_pbo_bytes == 256
    assert snapshot.gl_framebuffer_resources == 0
    assert snapshot.gl_framebuffer_bytes == 0
    assert snapshot.known_tracked_bytes == 1184
    assert snapshot.aggregate_fields()["qt_default_fbo"] == "qt_owned_untracked"


def test_collect_resource_accounting_uses_detached_display_aggregate_only():
    class _LiveDisplayTrap:
        def get_image_accounting_snapshot(self):
            raise AssertionError("background accounting touched a live DisplayWidget")

    engine = _engine()
    engine.display_manager = SimpleNamespace(displays=(_LiveDisplayTrap(),))
    engine._display_image_accounting_snapshot = MappingProxyType(
        {
            "resources": (
                MappingProxyType(
                    {
                        "resource_id": "qt-pixmap:detached",
                        "owner": "display:0",
                        "generation": 3,
                        "dimensions": (10, 10),
                        "format": "QPixmap(depth=32)",
                        "tracked_bytes": 400,
                        "lease_count": None,
                    }
                ),
            )
        }
    )

    snapshot = resource_metrics.collect_resource_accounting(engine)

    assert snapshot.cpu_display_resources == 1
    assert snapshot.cpu_display_bytes == 400


def test_worker_safe_accounting_uses_only_passive_registry_snapshot():
    class _Registry:
        def get_usage_accounting_snapshot(self):
            return MappingProxyType(
                {
                    "resources": (
                        MappingProxyType(
                            {
                                "resource_id": "texture-safe",
                                "resource_type": "NATIVE_HANDLE",
                                "gl_handle_type": "texture",
                                "owner": "compositor:worker-safe",
                                "generation": 12,
                                "dimensions": (2, 2),
                                "format": "RGBA8",
                                "tracked_bytes": 16,
                                "qobject_valid": None,
                            }
                        ),
                    )
                }
            )

        def get_accounting_snapshot(self):
            raise AssertionError("usage worker selected the live diagnostic snapshot")

    engine = _engine()
    engine.resource_manager = _Registry()

    snapshot = resource_metrics.collect_resource_accounting(
        engine,
        worker_safe=True,
    )

    assert snapshot.gl_texture_bytes == 16


def test_resource_details_are_machine_readable_and_include_owner_contract():
    snapshot = resource_metrics.collect_resource_accounting(_engine())
    details = json.loads(snapshot.resources_json())

    assert details[0]["source"] == "cpu_image_cache"
    assert details[1]["owner"] == "compositor:1"
    assert details[1]["generation"] == 9
    assert details[1]["dimensions"] == [4, 8]
    assert details[1]["format"] == "RGBA8"
    assert details[1]["lease_count"] is None


def test_lifecycle_resource_snapshot_is_inert_without_perf(monkeypatch, caplog):
    monkeypatch.setattr(resource_metrics, "is_perf_metrics_enabled", lambda: False)

    assert (
        resource_metrics.log_lifecycle_resource_snapshot(
            _engine(),
            event="settings",
            stage="before_stop",
        )
        is None
    )
    assert "[RESOURCE]" not in caplog.text


def test_lifecycle_resource_snapshot_emits_one_aggregate_with_details(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(resource_metrics, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(resource_metrics, "is_lifecycle_logging_enabled", lambda: False)

    with caplog.at_level(logging.INFO, logger="core.performance.resource_metrics"):
        snapshot = resource_metrics.log_lifecycle_resource_snapshot(
            _engine(),
            event="settings",
            stage="after_restart",
        )

    assert snapshot is not None
    assert "[RESOURCE] snapshot event=settings stage=after_restart" in caplog.text
    assert "tracked_known_bytes=1184" in caplog.text
    assert "resources_json=[" not in caplog.text


def test_lifecycle_detail_is_sidecar_gated_and_summarizes_ownership(
    monkeypatch,
    caplog,
):
    resource_manager = _Owner(
        MappingProxyType(
            {
                "resources": (
                    MappingProxyType(
                        {
                            "resource_id": "active-timer",
                            "resource_type": "TIMER",
                            "owner": "display:1",
                            "generation": 7,
                            "runtime_generation": 7,
                            "lifetime_scope": "runtime",
                            "qobject_valid": True,
                            "cleanup_callback_retains_owner": False,
                            "tracked_bytes": 64,
                        }
                    ),
                    MappingProxyType(
                        {
                            "resource_id": "process-cache",
                            "resource_type": "IMAGE_CACHE",
                            "owner": "shared",
                            "generation": None,
                            "runtime_generation": 6,
                            "lifetime_scope": "process",
                            "qobject_valid": False,
                            "cleanup_callback_retains_owner": True,
                            "tracked_bytes": None,
                        }
                    ),
                ),
            }
        )
    )
    thread_manager = SimpleNamespace(
        get_lifecycle_ownership_snapshot=lambda: {
            "active_tasks": (
                {"runtime_generation": 7},
                {"runtime_generation": 6},
            ),
            "ui": {
                "queue_depth": 2,
                "queued_by_generation": {"7": 1, "6": 1},
                "scheduled_single_shots": 1,
                "scheduled_single_shots_by_generation": {"7": 1},
            },
        }
    )
    fade = SimpleNamespace(
        _state=SimpleNamespace(name="READY"),
        _compositor_ready=True,
        _startup_holds={"critical_gl_startup"},
    )
    widget_manager = SimpleNamespace(
        _widgets={"clock": object(), "spotify_visualizer": object()},
        _fade_coordinator=fade,
    )
    display = SimpleNamespace(
        _runtime_generation=7,
        _has_rendered_first_frame=True,
        _gl_compositor=SimpleNamespace(context=lambda: object()),
        spotify_visualizer_widget=object(),
        _widget_manager=widget_manager,
    )
    engine = SimpleNamespace(
        _image_cache=None,
        _runtime_generation=7,
        _pending_runtime_destruction_barrier=SimpleNamespace(retiring_generation=6),
        display_manager=SimpleNamespace(displays=(display,)),
        resource_manager=resource_manager,
        thread_manager=thread_manager,
        _process_supervisor=None,
        _usage_telemetry=SimpleNamespace(
            get_latest_lifecycle_snapshot=lambda: {
                "sequence": 11,
                "sample_age_ms": 250.0,
                "rss_app_mb": 900.0,
                "private_app_mb": 3100.0,
                "private_main_mb": 3000.0,
                "private_children_mb": 100.0,
                "uss_app_mb": 720.0,
                "uss_main_mb": 650.0,
                "uss_children_mb": 70.0,
                "threads_app": 23,
                "handles_app": 712,
                "vram_dedicated_mb": 775.0,
                "vram_shared_mb": 80.0,
            }
        ),
    )
    monkeypatch.setattr(resource_metrics, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(resource_metrics, "is_lifecycle_logging_enabled", lambda: True)

    ownership = resource_metrics.collect_lifecycle_ownership_summary(engine)
    assert ownership["current_runtime_generation"] == 7
    assert ownership["retiring_runtime_generation"] == 6
    assert ownership["resource_manager"]["by_resource_type"] == {
        "IMAGE_CACHE": 1,
        "TIMER": 1,
    }
    assert ownership["resource_manager"]["lifetime_buckets"] == {
        "process": 1,
        "active": 1,
        "retiring": 0,
        "stale": 0,
        "unassigned": 0,
    }
    assert ownership["resource_manager"]["invalid_qobjects"] == 1
    assert ownership["resource_manager"]["cleanup_callbacks_retaining_owner"] == 1
    assert ownership["thread_manager"]["active_tasks_by_generation"] == {"7": 1, "6": 1}
    assert ownership["tracked_bytes"]["tracked_known_bytes"] == 64
    assert ownership["display"]["by_generation"]["7"]["first_frames_ready"] == 1
    assert ownership["display"]["by_generation"]["7"]["contexts"] == 1
    assert ownership["display"]["by_generation"]["7"]["fade_states"] == {"READY": 1}
    assert ownership["process"]["total_rss_mb"] == 900.0
    assert ownership["process"]["total_private_commit_mb"] == 3100.0
    assert ownership["process"]["main_private_commit_mb"] == 3000.0
    assert ownership["process"]["children_private_commit_mb"] == 100.0
    assert ownership["process"]["total_uss_mb"] == 720.0
    assert ownership["process"]["main_uss_mb"] == 650.0
    assert ownership["process"]["children_uss_mb"] == 70.0
    assert ownership["process"]["dedicated_vram_mb"] == 775.0
    detail_records = json.loads(resource_metrics.collect_resource_accounting(engine).resources_json())
    timer_record = next(record for record in detail_records if record["resource_id"] == "active-timer")
    assert timer_record["runtime_generation"] == 7
    assert timer_record["lifetime_scope"] == "runtime"
    assert timer_record["cleanup_callback_retains_owner"] is False

    with caplog.at_level(logging.INFO, logger="core.performance.resource_metrics"):
        snapshot = resource_metrics.log_lifecycle_resource_snapshot(
            engine,
            event="settings",
            stage="after_restart",
        )

    assert snapshot is not None
    assert "[PERF] [RESOURCE] snapshot event=settings stage=after_restart" in caplog.text
    assert "[LIFECYCLE] [RESOURCE_DETAIL] event=settings stage=after_restart" in caplog.text
    assert "ownership_json=" in caplog.text
    assert "resources_json=[" in caplog.text


def test_lifecycle_ownership_summary_tolerates_deleted_qt_like_wrappers():
    class InvalidDisplay:
        @property
        def _runtime_generation(self):
            raise RuntimeError("Internal C++ object already deleted")

        @property
        def _gl_compositor(self):
            raise RuntimeError("Internal C++ object already deleted")

        @property
        def _widget_manager(self):
            raise RuntimeError("Internal C++ object already deleted")

    engine = _engine()
    engine._runtime_generation = 9
    engine.display_manager = SimpleNamespace(displays=(InvalidDisplay(),))

    ownership = resource_metrics.collect_lifecycle_ownership_summary(engine)

    assert ownership["display"]["by_generation"]["9"]["displays"] == 1
    assert ownership["display"]["by_generation"]["9"]["compositors"] == 0

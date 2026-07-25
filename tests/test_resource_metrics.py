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
    assert snapshot.gl_unknown_resources == 1
    assert snapshot.gl_texture_bytes == 128
    assert snapshot.gl_pbo_bytes == 256
    assert snapshot.gl_framebuffer_resources == 0
    assert snapshot.gl_framebuffer_bytes == 0
    assert snapshot.known_tracked_bytes == 1184
    assert snapshot.aggregate_fields()["qt_default_fbo"] == "qt_owned_untracked"


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

    with caplog.at_level(logging.INFO, logger="core.performance.resource_metrics"):
        snapshot = resource_metrics.log_lifecycle_resource_snapshot(
            _engine(),
            event="settings",
            stage="after_restart",
        )

    assert snapshot is not None
    assert "[RESOURCE] snapshot event=settings stage=after_restart" in caplog.text
    assert "tracked_known_bytes=1184" in caplog.text
    assert "resources_json=[" in caplog.text

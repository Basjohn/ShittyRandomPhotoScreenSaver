"""Passive resource-accounting snapshots for recovery diagnostics.

This module reads existing owner-maintained accounting sidecars.  It never
creates, deletes, leases, or otherwise participates in resource control flow.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from core.logging.logger import (
    get_logger,
    is_lifecycle_logging_enabled,
    is_perf_metrics_enabled,
)


logger = get_logger(__name__)

_GENERATION_SUMMARY_LIMIT = 16
_RESOURCE_DETAIL_LIMIT = 256


def _json_safe(value: Any) -> Any:
    """Return a detached JSON-safe representation of snapshot metadata."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict) or hasattr(value, "items"):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return repr(value)


@dataclass(frozen=True)
class ResourceAccountingRecord:
    source: str
    resource_id: str
    resource_kind: str
    owner: Any
    generation: Any
    dimensions: tuple[int, ...] | None
    format: str | None
    tracked_bytes: int | None
    lease_count: int | None
    runtime_generation: Any = None
    generation_source: str | None = None
    lifetime_scope: str | None = None
    owner_class: str | None = None
    owner_id: int | None = None
    creation_site: str | None = None
    creation_site_kind: str | None = None
    weak_live: bool | None = None
    qobject_valid: bool | None = None
    cleanup_handler_kind: str | None = None
    cleanup_handler_owner_class: str | None = None
    cleanup_handler_owner_id: int | None = None
    cleanup_callback_retains_owner: bool | None = None


@dataclass(frozen=True)
class ResourceAccountingSnapshot:
    cpu_cache_resources: int
    cpu_cache_bytes: int
    cpu_display_resources: int
    cpu_display_bytes: int
    registry_resources: int
    registry_known_bytes: int
    registry_unknown_resources: int
    gl_resources: int
    gl_known_bytes: int
    gl_unknown_resources: int
    gl_texture_resources: int
    gl_texture_bytes: int
    gl_framebuffer_resources: int
    gl_framebuffer_bytes: int
    gl_renderbuffer_resources: int
    gl_renderbuffer_bytes: int
    gl_pbo_resources: int
    gl_pbo_bytes: int
    resources: tuple[ResourceAccountingRecord, ...]

    @property
    def known_tracked_bytes(self) -> int:
        return self.cpu_cache_bytes + self.cpu_display_bytes + self.registry_known_bytes

    @property
    def total_resources(self) -> int:
        return self.cpu_cache_resources + self.cpu_display_resources + self.registry_resources

    def aggregate_fields(self) -> dict[str, int | str]:
        """Return stable flat fields used by periodic and lifecycle logs."""
        return {
            "tracked_resources": self.total_resources,
            "tracked_known_bytes": self.known_tracked_bytes,
            "cpu_cache_resources": self.cpu_cache_resources,
            "cpu_cache_bytes": self.cpu_cache_bytes,
            "cpu_display_resources": self.cpu_display_resources,
            "cpu_display_bytes": self.cpu_display_bytes,
            "rm_resources": self.registry_resources,
            "rm_known_bytes": self.registry_known_bytes,
            "rm_unknown_resources": self.registry_unknown_resources,
            "gl_resources": self.gl_resources,
            "gl_known_bytes": self.gl_known_bytes,
            "gl_unknown_resources": self.gl_unknown_resources,
            "gl_texture_resources": self.gl_texture_resources,
            "gl_texture_bytes": self.gl_texture_bytes,
            "gl_framebuffer_resources": self.gl_framebuffer_resources,
            "gl_framebuffer_bytes": self.gl_framebuffer_bytes,
            "gl_renderbuffer_resources": self.gl_renderbuffer_resources,
            "gl_renderbuffer_bytes": self.gl_renderbuffer_bytes,
            "gl_pbo_resources": self.gl_pbo_resources,
            "gl_pbo_bytes": self.gl_pbo_bytes,
            # QOpenGLWidget's default FBO is Qt-owned.  The baseline has no
            # application-owned FBO allocation seam, so it is intentionally
            # outside the application byte total rather than guessed.
            "qt_default_fbo": "qt_owned_untracked",
        }

    def resources_json(self, *, limit: int | None = None) -> str:
        resources = self.resources
        if limit is not None:
            resources = resources[: max(0, int(limit))]
        return json.dumps(
            [_json_safe(asdict(record)) for record in resources],
            separators=(",", ":"),
            sort_keys=True,
        )


def _record_from_mapping(
    *,
    source: str,
    resource_id: str,
    resource_kind: str,
    values: Any,
) -> ResourceAccountingRecord:
    dimensions = values.get("dimensions")
    return ResourceAccountingRecord(
        source=source,
        resource_id=str(resource_id),
        resource_kind=str(resource_kind),
        owner=_json_safe(values.get("owner")),
        generation=_json_safe(values.get("generation")),
        dimensions=(
            tuple(int(value) for value in dimensions)
            if dimensions is not None
            else None
        ),
        format=(
            str(values.get("format"))
            if values.get("format") is not None
            else None
        ),
        tracked_bytes=(
            int(values.get("tracked_bytes"))
            if isinstance(values.get("tracked_bytes"), int)
            and not isinstance(values.get("tracked_bytes"), bool)
            and int(values.get("tracked_bytes")) >= 0
            else None
        ),
        lease_count=(
            int(values.get("lease_count"))
            if isinstance(values.get("lease_count"), int)
            and not isinstance(values.get("lease_count"), bool)
            else None
        ),
        runtime_generation=_json_safe(values.get("runtime_generation")),
        generation_source=(
            str(values.get("generation_source"))
            if values.get("generation_source") is not None
            else None
        ),
        lifetime_scope=(
            str(values.get("lifetime_scope"))
            if values.get("lifetime_scope") is not None
            else None
        ),
        owner_class=(
            str(values.get("owner_class"))
            if values.get("owner_class") is not None
            else None
        ),
        owner_id=(
            int(values.get("owner_id"))
            if isinstance(values.get("owner_id"), int)
            and not isinstance(values.get("owner_id"), bool)
            else None
        ),
        creation_site=(
            str(values.get("creation_site"))
            if values.get("creation_site") is not None
            else None
        ),
        creation_site_kind=(
            str(values.get("creation_site_kind"))
            if values.get("creation_site_kind") is not None
            else None
        ),
        weak_live=(
            bool(values.get("weak_live"))
            if values.get("weak_live") is not None
            else None
        ),
        qobject_valid=(
            bool(values.get("qobject_valid"))
            if values.get("qobject_valid") is not None
            else None
        ),
        cleanup_handler_kind=(
            str(values.get("cleanup_handler_kind"))
            if values.get("cleanup_handler_kind") is not None
            else None
        ),
        cleanup_handler_owner_class=(
            str(values.get("cleanup_handler_owner_class"))
            if values.get("cleanup_handler_owner_class") is not None
            else None
        ),
        cleanup_handler_owner_id=(
            int(values.get("cleanup_handler_owner_id"))
            if isinstance(values.get("cleanup_handler_owner_id"), int)
            and not isinstance(values.get("cleanup_handler_owner_id"), bool)
            else None
        ),
        cleanup_callback_retains_owner=(
            bool(values.get("cleanup_callback_retains_owner"))
            if values.get("cleanup_callback_retains_owner") is not None
            else None
        ),
    )


def _safe_getattr(owner: Any, name: str, default: Any = None) -> Any:
    """Read diagnostic state without allowing a deleted Qt wrapper to escape."""
    try:
        return getattr(owner, name, default)
    except (AttributeError, ReferenceError, RuntimeError):
        return default


def _safe_items(value: Any) -> tuple[tuple[Any, Any], ...]:
    try:
        return tuple(value.items()) if hasattr(value, "items") else ()
    except (AttributeError, ReferenceError, RuntimeError):
        return ()


def _safe_call(callable_value: Any, default: Any = None) -> Any:
    try:
        return callable_value() if callable(callable_value) else default
    except (ReferenceError, RuntimeError, TypeError):
        return default


def _bounded_generation_counts(
    values: list[Any],
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> dict[str, int]:
    """Return a capped generation map while retaining current/retiring buckets."""
    counts: dict[str, int] = {}
    for value in values:
        key = "unassigned" if value is None else str(value)
        counts[key] = counts.get(key, 0) + 1

    return _cap_generation_counts(
        counts,
        current_generation=current_generation,
        retiring_generation=retiring_generation,
    )


def _cap_generation_counts(
    counts: dict[str, int],
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> dict[str, int]:
    """Keep a pre-aggregated generation map bounded without losing key owners."""

    preferred = [
        str(value)
        for value in (current_generation, retiring_generation)
        if value is not None and str(value) in counts
    ]
    selected = list(dict.fromkeys(preferred))
    for key in sorted(counts):
        if key not in selected and len(selected) < _GENERATION_SUMMARY_LIMIT:
            selected.append(key)
    result = {key: counts[key] for key in selected}
    omitted = sum(value for key, value in counts.items() if key not in result)
    if omitted:
        result["other_generations"] = omitted
    return result


def _bounded_generation_count_mapping(
    counts: Any,
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> dict[str, int]:
    """Cap an existing generation-to-count mapping without expanding its counts."""
    values: dict[str, int] = {}
    for key, count in _safe_items(counts):
        try:
            normalized_count = max(0, int(count or 0))
        except (TypeError, ValueError):
            continue
        if normalized_count:
            normalized_key = "unassigned" if key is None else str(key)
            values[normalized_key] = values.get(normalized_key, 0) + normalized_count
    return _cap_generation_counts(
        values,
        current_generation=current_generation,
        retiring_generation=retiring_generation,
    )


def _generation_bucket(
    generation: Any,
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> str:
    if generation is None:
        return "unassigned"
    if current_generation is not None and generation == current_generation:
        return "active"
    if retiring_generation is not None and generation == retiring_generation:
        return "retiring"
    return "stale"


def _resource_manager_ownership_summary(
    engine: Any,
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> dict[str, Any]:
    manager = _safe_getattr(engine, "resource_manager")
    getter = _safe_getattr(manager, "get_accounting_snapshot")
    if not callable(getter):
        return {"available": False}
    try:
        entries = tuple(getter().get("resources", ()))
    except Exception:
        logger.debug("[LIFECYCLE] ResourceManager ownership snapshot failed", exc_info=True)
        return {"available": False}

    by_type: dict[str, int] = {}
    generations: list[Any] = []
    lifecycle_buckets = {
        "process": 0,
        "active": 0,
        "retiring": 0,
        "stale": 0,
        "unassigned": 0,
    }
    invalid_qobjects = 0
    retained_cleanup_callbacks = 0
    for entry in entries:
        resource_type = str(entry.get("resource_type", "unknown"))
        by_type[resource_type] = by_type.get(resource_type, 0) + 1
        generation = entry.get("runtime_generation", entry.get("generation"))
        generations.append(generation)
        if entry.get("qobject_valid") is False:
            invalid_qobjects += 1
        if bool(entry.get("cleanup_callback_retains_owner", False)):
            retained_cleanup_callbacks += 1
        if entry.get("lifetime_scope") == "process":
            lifecycle_buckets["process"] += 1
        else:
            lifecycle_buckets[
                _generation_bucket(
                    generation,
                    current_generation=current_generation,
                    retiring_generation=retiring_generation,
                )
            ] += 1
    return {
        "available": True,
        "total": len(entries),
        "by_resource_type": dict(sorted(by_type.items())),
        "by_runtime_generation": _bounded_generation_counts(
            generations,
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
        "lifetime_buckets": lifecycle_buckets,
        "invalid_qobjects": invalid_qobjects,
        "cleanup_callbacks_retaining_owner": retained_cleanup_callbacks,
    }


def _thread_ownership_summary(
    engine: Any,
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> dict[str, Any]:
    manager = _safe_getattr(engine, "thread_manager")
    getter = _safe_getattr(manager, "get_lifecycle_ownership_snapshot")
    if not callable(getter):
        return {"available": False}
    try:
        snapshot = getter()
    except Exception:
        logger.debug("[LIFECYCLE] ThreadManager ownership snapshot failed", exc_info=True)
        return {"available": False}

    tasks = tuple(snapshot.get("active_tasks", ()))
    task_generations = [task.get("runtime_generation") for task in tasks]
    ui = snapshot.get("ui", {})
    return {
        "available": True,
        "active_tasks": len(tasks),
        "active_tasks_by_generation": _bounded_generation_counts(
            task_generations,
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
        "ui_queue_depth": int(ui.get("queue_depth", 0) or 0),
        "ui_queued_by_generation": _bounded_generation_count_mapping(
            ui.get("queued_by_generation", {}),
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
        "ui_scheduled_single_shots": int(ui.get("scheduled_single_shots", 0) or 0),
        "ui_scheduled_by_generation": _bounded_generation_count_mapping(
            ui.get("scheduled_single_shots_by_generation", {}),
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
    }


def _display_ownership_summary(
    display_manager: Any,
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> dict[str, Any]:
    """Consume the display orchestrator's bounded Quick ownership contract."""

    if display_manager is None:
        # Teardown snapshots can legitimately run after engine.display_manager
        # has been detached while the destruction barrier still owns retiring
        # roots.  That is not a missing semantic contract and should not produce
        # a misleading warning during every healthy replacement/exit.
        logger.debug(
            "[LIFECYCLE] Display ownership snapshot unavailable: "
            "no live DisplayManager (already detached)"
        )
        return {
            "available": False,
            "display_manager_id": None,
            "by_generation": {},
        }

    getter = _safe_getattr(display_manager, "describe_resource_ownership")
    if not callable(getter):
        logger.warning(
            "[LIFECYCLE] Display ownership snapshot unavailable: semantic contract missing"
        )
        return {
            "available": False,
            "display_manager_id": id(display_manager),
            "by_generation": {},
        }
    try:
        snapshot = getter()
    except Exception:
        logger.warning(
            "[LIFECYCLE] Display ownership snapshot failed",
            exc_info=True,
        )
        return {
            "available": False,
            "display_manager_id": id(display_manager),
            "by_generation": {},
        }
    if not isinstance(snapshot, Mapping):
        logger.warning(
            "[LIFECYCLE] Display ownership snapshot rejected: expected mapping"
        )
        return {
            "available": False,
            "display_manager_id": id(display_manager),
            "by_generation": {},
        }

    raw_by_generation = snapshot.get("by_generation", {})
    by_generation = (
        {str(key): value for key, value in raw_by_generation.items()}
        if isinstance(raw_by_generation, Mapping)
        else {}
    )

    generation_keys = _bounded_generation_count_mapping(
        {
            str(key): int(counts.get("display_units", 0) or 0)
            for key, counts in by_generation.items()
            if isinstance(counts, Mapping)
        },
        current_generation=current_generation,
        retiring_generation=retiring_generation,
    )
    selected = set(generation_keys) - {"other_generations"}
    omitted_displays = sum(
        int(counts.get("display_units", 0) or 0)
        for key, counts in by_generation.items()
        if key not in selected and isinstance(counts, Mapping)
    )
    selected_details = {
        key: by_generation[key]
        for key in sorted(selected)
        if key in by_generation
    }
    if omitted_displays:
        selected_details["other_generations"] = {
            "display_units": omitted_displays
        }
    return {
        "available": True,
        "display_manager_id": snapshot.get("display_manager_id", id(display_manager)),
        "by_generation": selected_details,
    }


def _process_ownership_summary(engine: Any) -> dict[str, Any]:
    """Take only non-blocking main-process facts; worker RSS uses its existing seam."""
    process_summary: dict[str, Any] = {"main_pid": os.getpid()}
    try:
        import psutil

        process = psutil.Process(os.getpid())
        memory = process.memory_info()
        process_summary.update(
            {
                "main_rss_bytes": int(getattr(memory, "rss", 0) or 0),
                "main_private_bytes": getattr(memory, "private", None),
                "main_threads": int(process.num_threads()),
                "main_handles": getattr(process, "num_handles", lambda: None)(),
            }
        )
    except Exception:
        process_summary["main_metrics_available"] = False

    supervisor = _safe_getattr(engine, "_process_supervisor")
    worker_getter = _safe_getattr(supervisor, "get_image_worker_usage_snapshot")
    if callable(worker_getter):
        try:
            worker = worker_getter()
            process_summary["image_worker"] = {
                "pid": worker.get("image_worker_pid"),
                "rss_mb": worker.get("image_worker_rss_mb"),
            }
        except Exception:
            process_summary["image_worker"] = {"available": False}

    usage_service = _safe_getattr(engine, "_usage_telemetry")
    latest_usage_getter = _safe_getattr(
        usage_service,
        "get_latest_lifecycle_snapshot",
    )
    if callable(latest_usage_getter):
        try:
            latest_usage = dict(latest_usage_getter())
        except Exception:
            latest_usage = {}
        if latest_usage:
            process_summary.update(
                {
                    "usage_sample_sequence": latest_usage.get("sequence"),
                    "usage_sample_age_ms": latest_usage.get("sample_age_ms"),
                    "total_rss_mb": latest_usage.get("rss_app_mb"),
                    "total_private_commit_mb": latest_usage.get("private_app_mb"),
                    "main_private_commit_mb": latest_usage.get("private_main_mb"),
                    "children_private_commit_mb": latest_usage.get(
                        "private_children_mb"
                    ),
                    "total_uss_mb": latest_usage.get("uss_app_mb"),
                    "main_uss_mb": latest_usage.get("uss_main_mb"),
                    "children_uss_mb": latest_usage.get("uss_children_mb"),
                    "total_threads": latest_usage.get("threads_app"),
                    "total_handles": latest_usage.get("handles_app"),
                    "dedicated_vram_mb": latest_usage.get("vram_dedicated_mb"),
                    "shared_vram_mb": latest_usage.get("vram_shared_mb"),
                }
            )
    return process_summary


def _global_subscription_summary(
    engine: Any,
    *,
    current_generation: Any,
    retiring_generation: Any,
) -> dict[str, Any]:
    event_system = _safe_getattr(engine, "event_system")
    event_count = _safe_call(
        _safe_getattr(event_system, "get_subscription_count"),
        0,
    )
    ticker_snapshot: dict[str, Any] = {"total": 0, "subscribers": ()}
    try:
        from widgets.clock_ticker import GlobalClockTicker

        ticker = GlobalClockTicker._instance
        if ticker is not None:
            ticker_snapshot = ticker.get_lifecycle_ownership_snapshot()
    except Exception:
        logger.debug(
            "[LIFECYCLE] Clock ticker ownership snapshot failed",
            exc_info=True,
        )
    return {
        "process_event_system": int(event_count or 0),
        "clock_ticker_total": int(ticker_snapshot.get("total", 0) or 0),
        "clock_ticker_timer_active": bool(
            ticker_snapshot.get("timer_active", False)
        ),
        "clock_ticker_by_generation": _bounded_generation_count_mapping(
            ticker_snapshot.get("subscribers_by_generation", {}),
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
    }


def collect_lifecycle_ownership_summary(
    engine: Any,
    *,
    accounting_snapshot: ResourceAccountingSnapshot | None = None,
) -> dict[str, Any]:
    """Collect a bounded passive ownership summary for lifecycle-sidecar logs."""
    if accounting_snapshot is None:
        accounting_snapshot = collect_resource_accounting(engine)
    current_generation = _safe_getattr(engine, "_runtime_generation")
    barrier = _safe_getattr(engine, "_pending_runtime_destruction_barrier")
    retiring_generation = _safe_getattr(barrier, "retiring_generation")
    display_manager = _safe_getattr(engine, "display_manager")
    return {
        "current_runtime_generation": current_generation,
        "retiring_runtime_generation": retiring_generation,
        "destruction_barrier": (
            _safe_call(_safe_getattr(barrier, "describe"))
        ),
        "tracked_bytes": accounting_snapshot.aggregate_fields(),
        "display": _display_ownership_summary(
            display_manager,
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
        "resource_manager": _resource_manager_ownership_summary(
            engine,
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
        "thread_manager": _thread_ownership_summary(
            engine,
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
        "global_subscriptions": _global_subscription_summary(
            engine,
            current_generation=current_generation,
            retiring_generation=retiring_generation,
        ),
        "process": _process_ownership_summary(engine),
    }


def collect_resource_accounting(
    engine: Any,
    *,
    worker_safe: bool = False,
) -> ResourceAccountingSnapshot:
    """Collect one detached snapshot from the engine's existing owners.

    ``worker_safe`` is required for the periodic usage sampler.  In that mode
    ResourceManager contributes only its immutable registration metadata and
    byte counts; live resources and QObject validity are never inspected.
    """
    records: list[ResourceAccountingRecord] = []
    image_cache = _safe_getattr(engine, "_image_cache")
    if image_cache is not None:
        getter = _safe_getattr(image_cache, "get_accounting_snapshot")
        if callable(getter):
            try:
                cache_snapshot = getter()
                for index, item in enumerate(cache_snapshot.get("resources", ())):
                    records.append(
                        _record_from_mapping(
                            source="cpu_image_cache",
                            resource_id=f"cache:{index}",
                            resource_kind="cpu_image",
                            values=item,
                        )
                    )
            except Exception:
                logger.debug("[LIFECYCLE] CPU cache accounting snapshot failed", exc_info=True)

    display_manager = _safe_getattr(engine, "display_manager")
    display_snapshot = _safe_getattr(
        engine,
        "_display_image_accounting_snapshot",
    )
    if not isinstance(display_snapshot, Mapping):
        getter = _safe_getattr(display_manager, "get_image_accounting_snapshot")
        try:
            display_snapshot = getter() if callable(getter) else {}
        except Exception:
            logger.debug("[LIFECYCLE] Display accounting snapshot failed", exc_info=True)
            display_snapshot = {}
    for index, item in enumerate(display_snapshot.get("resources", ())):
        resource_id = str(item.get("resource_id") or f"display:{index}")
        records.append(
            _record_from_mapping(
                source="cpu_display",
                resource_id=resource_id,
                resource_kind="cpu_pixmap",
                values=item,
            )
        )

    resource_manager = _safe_getattr(engine, "resource_manager")
    if resource_manager is not None:
        getter_name = (
            "get_usage_accounting_snapshot"
            if worker_safe
            else "get_accounting_snapshot"
        )
        getter = _safe_getattr(resource_manager, getter_name)
        if callable(getter):
            try:
                manager_snapshot = getter()
                for item in manager_snapshot.get("resources", ()):
                    records.append(
                        _record_from_mapping(
                            source="resource_manager",
                            resource_id=str(item.get("resource_id", "")),
                            resource_kind=str(
                                item.get("gl_handle_type")
                                or item.get("resource_type")
                                or "unknown"
                            ),
                            values=item,
                        ),
                    )
            except Exception:
                logger.debug("[LIFECYCLE] ResourceManager accounting snapshot failed", exc_info=True)
        elif worker_safe:
            logger.debug(
                "[USAGE] ResourceManager has no worker-safe accounting snapshot; "
                "omitting registry resources"
            )

    cpu_records = [record for record in records if record.source == "cpu_image_cache"]
    display_records = [record for record in records if record.source == "cpu_display"]
    manager_records = [record for record in records if record.source == "resource_manager"]
    gl_records = [
        record
        for record in manager_records
        if record.resource_kind.lower()
        in {
            "vao",
            "vbo",
            "texture",
            "program",
            "shader",
            "framebuffer",
            "fbo",
            "renderbuffer",
            "rbo",
            "query",
        }
    ]
    texture_records = [
        record for record in gl_records if record.resource_kind.lower() == "texture"
    ]
    framebuffer_records = [
        record
        for record in gl_records
        if record.resource_kind.lower() in {"framebuffer", "fbo"}
    ]
    renderbuffer_records = [
        record
        for record in gl_records
        if record.resource_kind.lower() in {"renderbuffer", "rbo"}
    ]
    pbo_records = [
        record
        for record in gl_records
        if record.format == "PIXEL_UNPACK_BUFFER"
    ]

    def known_bytes(items: list[ResourceAccountingRecord]) -> int:
        return sum(
            record.tracked_bytes
            for record in items
            if record.tracked_bytes is not None
        )

    return ResourceAccountingSnapshot(
        cpu_cache_resources=len(cpu_records),
        cpu_cache_bytes=known_bytes(cpu_records),
        cpu_display_resources=len(display_records),
        cpu_display_bytes=known_bytes(display_records),
        registry_resources=len(manager_records),
        registry_known_bytes=known_bytes(manager_records),
        registry_unknown_resources=sum(
            record.tracked_bytes is None for record in manager_records
        ),
        gl_resources=len(gl_records),
        gl_known_bytes=known_bytes(gl_records),
        gl_unknown_resources=sum(record.tracked_bytes is None for record in gl_records),
        gl_texture_resources=len(texture_records),
        gl_texture_bytes=known_bytes(texture_records),
        gl_framebuffer_resources=len(framebuffer_records),
        gl_framebuffer_bytes=known_bytes(framebuffer_records),
        gl_renderbuffer_resources=len(renderbuffer_records),
        gl_renderbuffer_bytes=known_bytes(renderbuffer_records),
        gl_pbo_resources=len(pbo_records),
        gl_pbo_bytes=known_bytes(pbo_records),
        resources=tuple(records),
    )


def log_lifecycle_resource_snapshot(
    engine: Any,
    *,
    event: str,
    stage: str,
) -> ResourceAccountingSnapshot | None:
    """Emit one low-frequency snapshot at an owning lifecycle boundary."""
    perf_enabled = is_perf_metrics_enabled()
    lifecycle_enabled = is_lifecycle_logging_enabled()
    if not perf_enabled and not lifecycle_enabled:
        return None
    try:
        snapshot = collect_resource_accounting(engine)
        fields = snapshot.aggregate_fields()
        if perf_enabled:
            logger.info(
                "[PERF] [RESOURCE] snapshot event=%s stage=%s "
                "tracked_resources=%d tracked_known_bytes=%d "
                "cpu_cache_resources=%d cpu_cache_bytes=%d "
                "cpu_display_resources=%d cpu_display_bytes=%d "
                "rm_resources=%d rm_known_bytes=%d rm_unknown_resources=%d "
                "gl_resources=%d gl_known_bytes=%d gl_unknown_resources=%d "
                "gl_texture_resources=%d gl_texture_bytes=%d "
                "gl_framebuffer_resources=%d gl_framebuffer_bytes=%d "
                "gl_renderbuffer_resources=%d gl_renderbuffer_bytes=%d "
                "gl_pbo_resources=%d gl_pbo_bytes=%d qt_default_fbo=%s",
                event,
                stage,
                fields["tracked_resources"],
                fields["tracked_known_bytes"],
                fields["cpu_cache_resources"],
                fields["cpu_cache_bytes"],
                fields["cpu_display_resources"],
                fields["cpu_display_bytes"],
                fields["rm_resources"],
                fields["rm_known_bytes"],
                fields["rm_unknown_resources"],
                fields["gl_resources"],
                fields["gl_known_bytes"],
                fields["gl_unknown_resources"],
                fields["gl_texture_resources"],
                fields["gl_texture_bytes"],
                fields["gl_framebuffer_resources"],
                fields["gl_framebuffer_bytes"],
                fields["gl_renderbuffer_resources"],
                fields["gl_renderbuffer_bytes"],
                fields["gl_pbo_resources"],
                fields["gl_pbo_bytes"],
                fields["qt_default_fbo"],
            )
        if lifecycle_enabled:
            ownership = collect_lifecycle_ownership_summary(
                engine,
                accounting_snapshot=snapshot,
            )
            logger.info(
                "[LIFECYCLE] [RESOURCE_DETAIL] event=%s stage=%s "
                "resources_total=%d resources_omitted=%d "
                "ownership_json=%s resources_json=%s",
                event,
                stage,
                len(snapshot.resources),
                max(0, len(snapshot.resources) - _RESOURCE_DETAIL_LIMIT),
                json.dumps(_json_safe(ownership), separators=(",", ":"), sort_keys=True),
                snapshot.resources_json(limit=_RESOURCE_DETAIL_LIMIT),
            )
        return snapshot
    except Exception:
        logger.exception(
            "[PERF] [RESOURCE] snapshot_failed event=%s stage=%s",
            event,
            stage,
        )
        return None

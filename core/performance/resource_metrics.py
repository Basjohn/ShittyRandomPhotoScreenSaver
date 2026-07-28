"""Passive resource-accounting snapshots for recovery diagnostics.

This module reads existing owner-maintained accounting sidecars.  It never
creates, deletes, leases, or otherwise participates in resource control flow.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from core.logging.logger import get_logger, is_perf_metrics_enabled


logger = get_logger(__name__)


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

    def resources_json(self) -> str:
        return json.dumps(
            [_json_safe(asdict(record)) for record in self.resources],
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
    )


def collect_resource_accounting(engine: Any) -> ResourceAccountingSnapshot:
    """Collect one detached snapshot from the engine's existing owners."""
    records: list[ResourceAccountingRecord] = []
    image_cache = getattr(engine, "_image_cache", None)
    if image_cache is not None:
        getter = getattr(image_cache, "get_accounting_snapshot", None)
        if callable(getter):
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

    display_manager = getattr(engine, "display_manager", None)
    seen_display_resources: set[str] = set()
    for display in list(getattr(display_manager, "displays", ()) or ()):
        getter = getattr(display, "get_image_accounting_snapshot", None)
        if not callable(getter):
            continue
        display_snapshot = getter()
        for index, item in enumerate(display_snapshot.get("resources", ())):
            resource_id = str(item.get("resource_id") or f"display:{id(display)}:{index}")
            if resource_id in seen_display_resources:
                continue
            seen_display_resources.add(resource_id)
            records.append(
                _record_from_mapping(
                    source="cpu_display",
                    resource_id=resource_id,
                    resource_kind="cpu_pixmap",
                    values=item,
                )
            )

    resource_manager = getattr(engine, "resource_manager", None)
    if resource_manager is not None:
        getter = getattr(resource_manager, "get_accounting_snapshot", None)
        if callable(getter):
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
                    )
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
    if not is_perf_metrics_enabled():
        return None
    try:
        snapshot = collect_resource_accounting(engine)
        fields = snapshot.aggregate_fields()
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
            "gl_pbo_resources=%d gl_pbo_bytes=%d qt_default_fbo=%s "
            "resources_json=%s",
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
            snapshot.resources_json(),
        )
        return snapshot
    except Exception:
        logger.exception(
            "[PERF] [RESOURCE] snapshot_failed event=%s stage=%s",
            event,
            stage,
        )
        return None

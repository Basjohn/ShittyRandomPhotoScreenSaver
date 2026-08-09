"""Bounded diagnostic attribution for surviving plain-Python runtime owners.

This module is imported only by the dedicated diagnostic product, and only
samples references after the destruction barrier has already timed out.  It
never collects garbage, mutates the reference graph, or changes barrier
completion policy.
"""
from __future__ import annotations

import functools
import gc
import json
import logging
import time
from types import CellType, FrameType, FunctionType, MethodType
from typing import Any, Mapping, Sequence


_DEFAULT_DIRECT_LIMIT = 32
_DEFAULT_MAPPING_OWNER_LIMIT = 12
_DEFAULT_MATCH_LIMIT = 16
_DEFAULT_PAYLOAD_CHARS = 24_000
_DEFAULT_INSPECTION_LIMIT = 4096
_DEFAULT_ELAPSED_MS = 75.0
_DEFAULT_GC_QUERY_LIMIT = 9
_DEFAULT_BATCH_OWNER_LIMIT = 8
_DEFAULT_BATCH_INSPECTION_LIMIT = 8192
_DEFAULT_BATCH_ELAPSED_MS = 200.0
_DEFAULT_BATCH_GC_QUERY_LIMIT = 17
_INTERNAL_FRAME_MODULES = {
    __name__,
    "engine.runtime_destruction",
}
_INTERNAL_FRAME_NAMES = {
    "capture_owner_referrers",
    "encode_owner_referrer_snapshot",
    "_capture_diagnostic_python_owner_referrers",
    "_describe_referrer",
    "_describe_mapping_owners",
    "_on_timeout",
}
_MISSING = object()


class _InspectionBudget:
    """Shared processing/query budget for one timeout-only snapshot."""

    def __init__(
        self,
        *,
        max_items: int,
        max_elapsed_ms: float,
        max_gc_queries: int,
    ) -> None:
        self.max_items = max(64, min(65_536, int(max_items)))
        self.max_elapsed_ms = max(5.0, min(500.0, float(max_elapsed_ms)))
        self.max_gc_queries = max(1, min(32, int(max_gc_queries)))
        self.started = time.perf_counter()
        self.items_inspected = 0
        self.gc_queries = 0
        self.exhausted_reason: str | None = None

    def _within_limits(self) -> bool:
        if self.exhausted_reason is not None:
            return False
        if (time.perf_counter() - self.started) * 1000.0 >= self.max_elapsed_ms:
            self.exhausted_reason = "elapsed_limit"
            return False
        return True

    def consume(self) -> bool:
        if not self._within_limits():
            return False
        if self.items_inspected >= self.max_items:
            self.exhausted_reason = "inspection_limit"
            return False
        self.items_inspected += 1
        return True

    def begin_gc_query(self) -> bool:
        """Bound query count; an individual CPython query is not pre-emptible."""

        if not self._within_limits():
            return False
        if self.gc_queries >= self.max_gc_queries:
            self.exhausted_reason = "gc_query_limit"
            return False
        self.gc_queries += 1
        return True

    def can_continue(self) -> bool:
        """Return whether more Python-side inspection may begin."""

        return self._within_limits()

    def describe(self) -> dict[str, object]:
        return {
            "items_inspected": self.items_inspected,
            "max_items": self.max_items,
            "gc_queries": self.gc_queries,
            "max_gc_queries": self.max_gc_queries,
            "elapsed_ms": round(
                max(0.0, (time.perf_counter() - self.started) * 1000.0),
                3,
            ),
            "max_elapsed_ms": self.max_elapsed_ms,
            "exhausted_reason": self.exhausted_reason,
        }


def _type_name(value: object) -> str:
    try:
        value_type = type(value)
        module = str(getattr(value_type, "__module__", "") or "")
        name = str(getattr(value_type, "__qualname__", "") or "unknown")
        return f"{module}.{name}" if module else name
    except Exception:
        return "unknown"


def _safe_len(value: object) -> int | None:
    try:
        return int(len(value))  # type: ignore[arg-type]
    except Exception:
        return None


def _matching_mapping_keys(
    mapping: Mapping[object, object],
    target: object,
    *,
    limit: int,
    expose_identifiers: bool,
    budget: _InspectionBudget,
) -> tuple[list[str], bool]:
    matches: list[str] = []
    truncated = False
    try:
        items = mapping.items()
    except Exception:
        return matches, truncated
    try:
        for key, value in items:
            if not budget.consume():
                truncated = True
                break
            if value is not target:
                continue
            if (
                expose_identifiers
                and isinstance(key, str)
                and key.isidentifier()
            ):
                matches.append(key[:128])
            else:
                matches.append(f"<{_type_name(key)}>")
            if len(matches) >= limit:
                truncated = True
                break
    except (RuntimeError, TypeError):
        pass
    return matches, truncated


def _matching_sequence_indexes(
    sequence: Sequence[object],
    target: object,
    *,
    limit: int,
    budget: _InspectionBudget,
) -> tuple[list[int], bool]:
    matches: list[int] = []
    truncated = False
    try:
        for index, value in enumerate(sequence):
            if not budget.consume():
                truncated = True
                break
            if value is target:
                matches.append(index)
                if len(matches) >= limit:
                    truncated = True
                    break
    except (RuntimeError, TypeError):
        pass
    return matches, truncated


def _is_internal_frame(frame: FrameType) -> bool:
    try:
        module = str(frame.f_globals.get("__name__", ""))
        return (
            module in _INTERNAL_FRAME_MODULES
            and frame.f_code.co_name in _INTERNAL_FRAME_NAMES
        )
    except Exception:
        return True


def _describe_mapping_owners(
    mapping: Mapping[object, object],
    *,
    limit: int,
    excluded_ids: set[int],
    budget: _InspectionBudget,
) -> tuple[list[dict[str, object]], bool]:
    """Describe immediate owners of an instance/function ``__dict__``."""

    owners: list[dict[str, object]] = []
    truncated = False
    if not budget.begin_gc_query():
        return owners, True
    try:
        referrers = gc.get_referrers(mapping)
    except Exception:
        return owners, truncated
    excluded_ids.add(id(referrers))
    try:
        for candidate in referrers:
            if not budget.consume():
                truncated = True
                break
            if id(candidate) in excluded_ids:
                continue
            if isinstance(candidate, FrameType):
                if _is_internal_frame(candidate):
                    continue
                owners.append(
                    {
                        "kind": "frame",
                        "id": id(candidate),
                        "module": str(candidate.f_globals.get("__name__", ""))[:160],
                        "function": str(candidate.f_code.co_name)[:160],
                        "line": int(candidate.f_lineno),
                    }
                )
            else:
                try:
                    candidate_dict = getattr(candidate, "__dict__", None)
                except Exception:
                    candidate_dict = None
                if candidate_dict is not mapping:
                    continue
                descriptor: dict[str, object] = {
                    "kind": "object_dict_owner",
                    "id": id(candidate),
                    "type": _type_name(candidate),
                }
                if isinstance(candidate, FunctionType) or (
                    callable(candidate)
                    and getattr(candidate, "__qualname__", None) is not None
                ):
                    descriptor["qualname"] = str(
                        getattr(candidate, "__qualname__", "")
                    )[:200]
                elif isinstance(candidate, logging.LogRecord):
                    descriptor.update(
                        {
                            "logger": str(candidate.name)[:160],
                            "source_module": str(candidate.module)[:160],
                            "function": str(candidate.funcName)[:160],
                            "line": int(candidate.lineno),
                        }
                    )
                owners.append(descriptor)
            if len(owners) >= limit:
                truncated = True
                break
    finally:
        excluded_ids.discard(id(referrers))
    return owners, truncated


def _describe_referrer(
    referrer: object,
    target: object,
    *,
    match_limit: int,
    owner_limit: int,
    excluded_ids: set[int],
    budget: _InspectionBudget,
) -> dict[str, object] | None:
    if id(referrer) in excluded_ids:
        return None
    if isinstance(referrer, FrameType) and _is_internal_frame(referrer):
        return None

    descriptor: dict[str, object] = {
        "id": id(referrer),
        "type": _type_name(referrer),
    }
    size = _safe_len(referrer)
    if size is not None:
        descriptor["size"] = size

    if isinstance(referrer, dict):
        descriptor["kind"] = "mapping"
        owners, owners_truncated = _describe_mapping_owners(
            referrer,
            limit=owner_limit,
            excluded_ids=excluded_ids,
            budget=budget,
        )
        matching_keys, keys_truncated = _matching_mapping_keys(
            referrer,
            target,
            limit=match_limit,
            expose_identifiers=any(
                owner.get("kind") == "object_dict_owner"
                for owner in owners
            ),
            budget=budget,
        )
        descriptor["matching_keys"] = matching_keys
        if keys_truncated:
            descriptor["key_scan_truncated"] = True
        if owners:
            descriptor["owners"] = owners
        if owners_truncated:
            descriptor["owners_truncated"] = True
        # A locals mapping owned solely by this diagnostic call is attribution
        # noise rather than a pre-existing retaining edge.
        if not owners and set(descriptor["matching_keys"]).issubset(
            {"target", "owner", "candidate", "referrer"}
        ):
            return None
        return descriptor

    if isinstance(referrer, (list, tuple)):
        descriptor["kind"] = "sequence"
        matching_indexes, indexes_truncated = _matching_sequence_indexes(
            referrer,
            target,
            limit=match_limit,
            budget=budget,
        )
        descriptor["matching_indexes"] = matching_indexes
        if indexes_truncated:
            descriptor["sequence_scan_truncated"] = True
        return descriptor

    if isinstance(referrer, (set, frozenset)):
        descriptor["kind"] = "set"
        if not budget.consume():
            descriptor["contains_target"] = None
            descriptor["scan_truncated"] = True
            return descriptor
        try:
            descriptor["contains_target"] = target in referrer
        except Exception:
            descriptor["contains_target"] = None
        return descriptor

    bound_self = getattr(referrer, "__self__", _MISSING)
    if isinstance(referrer, MethodType) or (
        bound_self is not _MISSING and bound_self is not None
    ):
        descriptor.update(
            {
                "kind": "bound_method",
                "qualname": str(getattr(referrer, "__qualname__", ""))[:200],
                "self_is_target": bound_self is target,
            }
        )
        return descriptor

    if isinstance(referrer, FunctionType) or (
        callable(referrer)
        and getattr(referrer, "__qualname__", None) is not None
    ):
        matching_cells: list[int] = []
        for index, cell in enumerate(getattr(referrer, "__closure__", ()) or ()):
            if not budget.consume():
                descriptor["closure_scan_truncated"] = True
                break
            try:
                if cell.cell_contents is target:
                    matching_cells.append(index)
            except ValueError:
                continue
        descriptor.update(
            {
                "kind": "function",
                "module": str(getattr(referrer, "__module__", ""))[:160],
                "qualname": str(getattr(referrer, "__qualname__", ""))[:200],
                "matching_closure_cells": matching_cells[:match_limit],
                "owner_attribute_is_target": getattr(
                    referrer,
                    "_srpss_timer_owner",
                    None,
                )
                is target,
            }
        )
        return descriptor

    if isinstance(referrer, CellType):
        try:
            contains_target = referrer.cell_contents is target
        except ValueError:
            contains_target = False
        descriptor.update(
            {
                "kind": "closure_cell",
                "contains_target": contains_target,
            }
        )
        return descriptor

    if isinstance(referrer, functools.partial):
        descriptor.update(
            {
                "kind": "partial",
                "function_type": _type_name(referrer.func),
                "argument_types": [
                    _type_name(value) for value in referrer.args[:match_limit]
                ],
                "matching_argument_indexes": _matching_sequence_indexes(
                    referrer.args,
                    target,
                    limit=match_limit,
                    budget=budget,
                )[0],
            }
        )
        return descriptor

    if isinstance(referrer, logging.LogRecord):
        descriptor.update(
            {
                "kind": "log_record",
                "logger": str(referrer.name)[:160],
                "source_module": str(referrer.module)[:160],
                "function": str(referrer.funcName)[:160],
                "line": int(referrer.lineno),
                "argument_types": [
                    _type_name(value)
                    for value in (
                        referrer.args
                        if isinstance(referrer.args, tuple)
                        else (referrer.args,)
                    )[:match_limit]
                ],
            }
        )
        return descriptor

    if isinstance(referrer, FrameType):
        matching_locals, locals_truncated = _matching_mapping_keys(
            referrer.f_locals,
            target,
            limit=match_limit,
            # Frame-local names can originate outside SRPSS.  Their identity
            # is useful; their spelling is not required for attribution.
            expose_identifiers=False,
            budget=budget,
        )
        descriptor.update(
            {
                "kind": "frame",
                "module": str(referrer.f_globals.get("__name__", ""))[:160],
                "function": str(referrer.f_code.co_name)[:160],
                "line": int(referrer.f_lineno),
                "matching_locals": matching_locals,
            }
        )
        if locals_truncated:
            descriptor["locals_scan_truncated"] = True
        return descriptor

    try:
        attributes = getattr(referrer, "__dict__", None)
    except Exception:
        attributes = None
    if isinstance(attributes, dict):
        matching_attributes, attributes_truncated = _matching_mapping_keys(
            attributes,
            target,
            limit=match_limit,
            expose_identifiers=True,
            budget=budget,
        )
        if matching_attributes:
            descriptor.update(
                {
                    "kind": "object",
                    "matching_attributes": matching_attributes,
                }
            )
            if attributes_truncated:
                descriptor["attribute_scan_truncated"] = True
            return descriptor

    descriptor["kind"] = "opaque"
    return descriptor


def capture_owner_referrers(
    owner: object,
    *,
    direct_limit: int = _DEFAULT_DIRECT_LIMIT,
    mapping_owner_limit: int = _DEFAULT_MAPPING_OWNER_LIMIT,
    match_limit: int = _DEFAULT_MATCH_LIMIT,
    inspection_limit: int = _DEFAULT_INSPECTION_LIMIT,
    max_elapsed_ms: float = _DEFAULT_ELAPSED_MS,
    max_gc_queries: int = _DEFAULT_GC_QUERY_LIMIT,
    _shared_budget: _InspectionBudget | None = None,
) -> dict[str, object]:
    """Return a query-count/processing/output-bounded direct snapshot.

    ``gc.get_referrers`` is a CPython diagnostic primitive whose individual
    call cannot be pre-empted.  The query count is therefore bounded, while
    the elapsed budget bounds only work that begins between those calls.
    """

    direct_limit = max(1, min(128, int(direct_limit)))
    mapping_owner_limit = max(0, min(32, int(mapping_owner_limit)))
    match_limit = max(1, min(64, int(match_limit)))
    budget = _shared_budget or _InspectionBudget(
        max_items=inspection_limit,
        max_elapsed_ms=max_elapsed_ms,
        max_gc_queries=max_gc_queries,
    )
    snapshot: dict[str, object] = {
        "owner_id": id(owner),
        "owner_type": _type_name(owner),
        "referrers": [],
        "direct_truncated": False,
    }
    excluded_ids = {id(snapshot), id(snapshot["referrers"])}
    if not budget.begin_gc_query():
        snapshot["direct_truncated"] = True
        snapshot["budget"] = budget.describe()
        return snapshot
    try:
        direct_referrers = gc.get_referrers(owner)
    except Exception as exc:
        snapshot["error_type"] = _type_name(exc)
        snapshot["budget"] = budget.describe()
        return snapshot
    excluded_ids.add(id(direct_referrers))

    output = snapshot["referrers"]
    assert isinstance(output, list)
    try:
        for referrer in direct_referrers:
            if not budget.consume():
                snapshot["direct_truncated"] = True
                break
            descriptor = _describe_referrer(
                referrer,
                owner,
                match_limit=match_limit,
                owner_limit=mapping_owner_limit,
                excluded_ids=excluded_ids,
                budget=budget,
            )
            if descriptor is None:
                continue

            output.append(descriptor)
            if len(output) >= direct_limit:
                snapshot["direct_truncated"] = True
                break
    finally:
        excluded_ids.discard(id(direct_referrers))
    snapshot["direct_count"] = len(output)
    snapshot["budget"] = budget.describe()
    return snapshot


def capture_weak_owner_referrer_snapshots(
    pending_owners: Sequence[tuple[int, str, object]],
    *,
    max_owners: int = _DEFAULT_BATCH_OWNER_LIMIT,
    direct_limit: int = _DEFAULT_DIRECT_LIMIT,
    mapping_owner_limit: int = _DEFAULT_MAPPING_OWNER_LIMIT,
    match_limit: int = _DEFAULT_MATCH_LIMIT,
    inspection_limit: int = _DEFAULT_BATCH_INSPECTION_LIMIT,
    max_elapsed_ms: float = _DEFAULT_BATCH_ELAPSED_MS,
    max_gc_queries: int = _DEFAULT_BATCH_GC_QUERY_LIMIT,
) -> tuple[tuple[tuple[int, str, str], ...], dict[str, object]]:
    """Capture an aggregate-bounded timeout batch from weak owner accessors.

    Each third tuple item is expected to be a weak-reference-like callable.
    The helper resolves one owner at a time and never returns a live owner.
    """

    max_owners = max(1, min(32, int(max_owners)))
    budget = _InspectionBudget(
        max_items=inspection_limit,
        max_elapsed_ms=max_elapsed_ms,
        max_gc_queries=max_gc_queries,
    )
    records: list[tuple[int, str, str]] = []
    considered = 0
    released = 0
    for token, label, owner_ref in tuple(pending_owners)[:max_owners]:
        if not budget.can_continue():
            break
        considered += 1
        owner = None
        try:
            owner = owner_ref() if callable(owner_ref) else None
            if owner is None:
                released += 1
                continue
            snapshot = capture_owner_referrers(
                owner,
                direct_limit=direct_limit,
                mapping_owner_limit=mapping_owner_limit,
                match_limit=match_limit,
                _shared_budget=budget,
            )
            records.append(
                (
                    int(token),
                    str(label)[:160],
                    encode_owner_referrer_snapshot(snapshot),
                )
            )
        except Exception as exc:
            records.append(
                (
                    int(token),
                    str(label)[:160],
                    '{"capture_error_type":"%s"}' % _type_name(exc),
                )
            )
        finally:
            owner = None

    total_pending = len(pending_owners)
    metadata: dict[str, object] = {
        "pending": total_pending,
        "owner_limit": max_owners,
        "considered": considered,
        "captured": len(records),
        "released_before_capture": released,
        "owners_omitted": max(0, total_pending - considered),
        "budget": budget.describe(),
    }
    return tuple(records), metadata


def encode_owner_referrer_snapshot(
    snapshot: Mapping[str, Any],
    *,
    max_chars: int = _DEFAULT_PAYLOAD_CHARS,
) -> str:
    """Encode one snapshot while keeping each emitted log record bounded."""

    max_chars = max(1024, min(128_000, int(max_chars)))
    payload = dict(snapshot)
    referrers = list(payload.get("referrers", ()) or ())
    payload["referrers"] = referrers
    removed = 0
    while True:
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded) <= max_chars or not referrers:
            return encoded
        referrers.pop()
        removed += 1
        payload["payload_referrers_omitted"] = removed

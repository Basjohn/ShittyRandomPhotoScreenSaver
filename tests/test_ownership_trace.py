"""Diagnostic-only plain-Python owner attribution regressions."""
from __future__ import annotations

import inspect
import json
import logging
import weakref

from core import build_profile
from core.logging import ownership_trace
from engine import runtime_destruction
from engine.runtime_destruction import RuntimeDestructionBarrier


class _Owner:
    def __repr__(self) -> str:  # pragma: no cover - must never be called
        raise AssertionError("ownership tracing must not repr live runtime owners")


class _AttributeRetainer:
    pass


class _CompiledMethodLike:
    __slots__ = ("__self__",)
    __qualname__ = "WidgetManager._compiled_slot"

    def __init__(self, owner) -> None:
        self.__self__ = owner

    def __call__(self) -> None:
        return None


def _walk_descriptors(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_descriptors(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_descriptors(child)


def test_owner_referrer_snapshot_names_attribute_closure_and_log_record() -> None:
    owner = _Owner()
    retainer = _AttributeRetainer()
    retainer.widget_manager = owner

    def callback() -> object:
        return owner

    callback._srpss_timer_owner = owner
    compiled_method = _CompiledMethodLike(owner)
    record = logging.LogRecord(
        "tests.owner",
        logging.INFO,
        __file__,
        42,
        "owner=%s",
        (owner,),
        None,
    )
    # A retained LogRecord is discovered as the positive owner of its own
    # __dict__; no broad parent-graph walk is needed.
    record.widget_manager = owner

    snapshot = ownership_trace.capture_owner_referrers(owner)
    descriptors = list(_walk_descriptors(snapshot))

    assert any(
        descriptor.get("type", "").endswith("._AttributeRetainer")
        and "widget_manager" in descriptor.get("matching_attributes", ())
        for descriptor in descriptors
    )
    assert any(
        descriptor.get("kind") == "closure_cell"
        and descriptor.get("contains_target") is True
        for descriptor in descriptors
    )
    assert any(
        descriptor.get("type") == "logging.LogRecord"
        for descriptor in descriptors
    )
    assert any(
        descriptor.get("kind") == "bound_method"
        and descriptor.get("self_is_target") is True
        for descriptor in descriptors
    )

    # Keep the synthetic retainers live through the snapshot assertion.
    assert callback() is owner
    assert compiled_method.__self__ is owner
    assert record.args[0] is owner


def test_owner_referrer_snapshot_redacts_arbitrary_mapping_keys_and_limits_work() -> None:
    owner = _Owner()
    secret_key = "person@example.com/C:/private/token-value"
    retained_mapping = {secret_key: owner}
    identifier_secret = "PrivateCustomerName"
    identifier_mapping = {identifier_secret: owner}
    long_sequence = [None] * 5000 + [owner]

    snapshot = ownership_trace.capture_owner_referrers(
        owner,
        inspection_limit=64,
        max_elapsed_ms=50.0,
    )
    encoded = ownership_trace.encode_owner_referrer_snapshot(snapshot)

    assert secret_key not in encoded
    assert identifier_secret not in encoded
    assert snapshot["budget"]["items_inspected"] <= 64
    assert snapshot["budget"]["exhausted_reason"] in {
        "inspection_limit",
        "elapsed_limit",
    }
    assert retained_mapping[secret_key] is owner
    assert identifier_mapping[identifier_secret] is owner
    assert long_sequence[-1] is owner


def test_owner_referrer_encoding_is_valid_json_and_bounded() -> None:
    snapshot = {
        "owner_id": 7,
        "owner_type": "WidgetManager",
        "referrers": [
            {"kind": "mapping", "matching_keys": ["x" * 2000]}
            for _ in range(40)
        ],
    }

    encoded = ownership_trace.encode_owner_referrer_snapshot(
        snapshot,
        max_chars=2048,
    )

    assert len(encoded) <= 2048
    decoded = json.loads(encoded)
    assert decoded["payload_referrers_omitted"] > 0


def test_owner_referrer_snapshot_does_not_retain_owner() -> None:
    owner = _Owner()
    owner_ref = weakref.ref(owner)
    retainer = _AttributeRetainer()
    retainer.widget_manager = owner

    snapshot = ownership_trace.capture_owner_referrers(owner)
    retainer.widget_manager = None
    owner = None

    assert owner_ref() is None
    assert snapshot["owner_type"].endswith("._Owner")


def test_barrier_owner_trace_is_diagnostic_only(qt_app, monkeypatch) -> None:
    engine = type(
        "_Engine",
        (),
        {"_terminal_shutdown_requested": False},
    )()
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=8,
    )
    owner = _Owner()
    barrier.watch_python_owner(owner, label="WidgetManager")

    calls = []

    def _capture_batch(pending):
        records = []
        for token, label, owner_ref in pending:
            candidate = owner_ref()
            calls.append(candidate)
            records.append(
                (
                    token,
                    label,
                    json.dumps(
                        {"owner_id": id(candidate), "referrers": []}
                    ),
                )
            )
        return tuple(records), {"captured": len(records)}

    monkeypatch.setattr(
        ownership_trace,
        "capture_weak_owner_referrer_snapshots",
        _capture_batch,
    )
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", False)
    assert barrier._capture_diagnostic_python_owner_referrers() == ((), {})
    assert calls == []

    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", True)
    snapshots, metadata = barrier._capture_diagnostic_python_owner_referrers()
    assert calls == [owner]
    assert len(snapshots) == 1
    assert snapshots[0][1] == "WidgetManager"
    assert json.loads(snapshots[0][2])["owner_id"] == id(owner)
    assert metadata == {"captured": 1}

    barrier.cancel_for_terminal_shutdown()


def test_diagnostic_timeout_fail_closes_before_tracing_all_survivors(
    qt_app,
    monkeypatch,
) -> None:
    engine = type(
        "_Engine",
        (),
        {"_terminal_shutdown_requested": False},
    )()
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=9,
    )
    owners = [_Owner(), _Owner()]
    for owner in owners:
        barrier.watch_python_owner(owner, label="WidgetManager")

    captured_owner_ids = []

    def _capture_batch(pending):
        events.append(("capture", len(pending)))
        records = []
        for token, label, owner_ref in pending:
            candidate = owner_ref()
            captured_owner_ids.append(id(candidate))
            records.append(
                (
                    token,
                    label,
                    json.dumps(
                        {"owner_id": id(candidate), "referrers": []}
                    ),
                )
            )
        return tuple(records), {"captured": len(records)}

    events = []
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", True)
    monkeypatch.setattr(
        ownership_trace,
        "capture_weak_owner_referrer_snapshots",
        _capture_batch,
    )
    monkeypatch.setattr(
        runtime_destruction.logger,
        "critical",
        lambda message, *args, **_kwargs: events.append(
            ("critical", message, args)
        ),
    )
    monkeypatch.setattr(
        runtime_destruction.QApplication,
        "exit",
        lambda code: events.append(("exit", code)),
    )

    barrier._on_timeout()

    owner_records = [
        event
        for event in events
        if event[0] == "critical" and "[PYTHON_OWNER_REFS] " in event[1]
    ]
    assert set(captured_owner_ids) == {id(owner) for owner in owners}
    assert len(owner_records) == 2
    assert events.index(("exit", 1)) < events.index(("capture", 2))
    assert barrier.is_complete is True


def test_owner_referrer_batch_bounds_owner_and_gc_query_count(monkeypatch) -> None:
    owners = [_Owner() for _index in range(20)]
    retainers = [_AttributeRetainer() for _index in owners]
    pending = []
    for owner, retainer in zip(owners, retainers):
        retainer.widget_manager = owner
        pending.append((id(owner), "WidgetManager", weakref.ref(owner)))

    real_get_referrers = ownership_trace.gc.get_referrers
    calls = []

    def _counting_get_referrers(candidate):
        calls.append(type(candidate).__name__)
        return real_get_referrers(candidate)

    monkeypatch.setattr(
        ownership_trace.gc,
        "get_referrers",
        _counting_get_referrers,
    )
    records, metadata = ownership_trace.capture_weak_owner_referrer_snapshots(
        pending,
        max_owners=2,
        max_gc_queries=3,
    )

    assert len(calls) <= 3
    assert len(records) <= 2
    assert metadata["owners_omitted"] == 18
    assert metadata["budget"]["gc_queries"] <= 3
    assert all(
        retainer.widget_manager is owner
        for owner, retainer in zip(owners, retainers)
    )


def test_owner_trace_never_collects_garbage() -> None:
    source = inspect.getsource(ownership_trace)
    assert "gc.collect" not in source

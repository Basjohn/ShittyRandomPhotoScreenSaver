"""Healthy teardown detachment must not masquerade as a missing lifecycle contract."""
from __future__ import annotations

from core.performance import resource_metrics


def test_detached_display_manager_is_debug_not_missing_contract_warning(monkeypatch) -> None:
    warnings: list[str] = []
    debug: list[str] = []
    monkeypatch.setattr(
        resource_metrics.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )
    monkeypatch.setattr(
        resource_metrics.logger,
        "debug",
        lambda message, *args, **kwargs: debug.append(str(message)),
    )

    summary = resource_metrics._display_ownership_summary(
        None,
        current_generation=2,
        retiring_generation=1,
    )

    assert summary == {
        "available": False,
        "display_manager_id": None,
        "by_generation": {},
    }
    assert warnings == []
    assert any("already detached" in message for message in debug)


def test_live_manager_without_semantic_contract_still_warns(monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        resource_metrics.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    manager = object()
    summary = resource_metrics._display_ownership_summary(
        manager,
        current_generation=2,
        retiring_generation=1,
    )

    assert summary["available"] is False
    assert summary["display_manager_id"] == id(manager)
    assert len(warnings) == 1
    assert "semantic contract missing" in warnings[0]

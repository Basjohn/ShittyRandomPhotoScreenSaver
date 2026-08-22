"""Presentation-neutral widget family capability catalog (Phase E foundation).

The catalog is the single source of truth mapping a stable ``family_id`` to the
runtime widget ids it owns. Settings (E2) lists one activation row per family and
the runtime (E1 ``WidgetRuntimeManager``) resolves families generically, so both
depend on this metadata being cheap, consistent with dev gating, and free of any
QWidget/Quick/provider import.
"""
from __future__ import annotations

from core import dev_gates
from rendering.widget_descriptors import (
    get_active_member_widget_ids,
    get_family_id_for_widget,
    get_widget_family_descriptor,
    get_widget_family_descriptors,
    get_widget_runtime_descriptors,
)


def _active_widget_ids() -> set[str]:
    return {d.widget_id for d in get_widget_runtime_descriptors()}


def test_every_family_member_is_a_real_runtime_widget_id():
    active = _active_widget_ids()
    for family in get_widget_family_descriptors():
        assert family.member_widget_ids, family.family_id
        # At least one member is active (that is why the family is listed), and
        # every listed member must be a canonical runtime widget id.
        assert any(wid in active for wid in family.member_widget_ids), family.family_id
        for wid in family.member_widget_ids:
            assert isinstance(wid, str) and wid


def test_each_family_has_a_label_and_unique_id():
    families = get_widget_family_descriptors()
    ids = [f.family_id for f in families]
    assert len(ids) == len(set(ids))
    for family in families:
        assert family.label
        assert family.family_id


def test_no_widget_belongs_to_two_families():
    seen: dict[str, str] = {}
    for family in get_widget_family_descriptors():
        for wid in family.member_widget_ids:
            assert wid not in seen, (wid, seen[wid], family.family_id)
            seen[wid] = family.family_id


def test_reverse_lookup_round_trips():
    for family in get_widget_family_descriptors():
        for wid in get_active_member_widget_ids(family.family_id):
            assert get_family_id_for_widget(wid) == family.family_id


def test_visualizer_is_not_a_widget_family_capability():
    # The visualizer's settings live in WidgetsTab but it is deliberately not a
    # widget-family capability (docs 04/07). It must not appear in any family.
    for family in get_widget_family_descriptors():
        assert "spotify_visualizer" not in family.member_widget_ids
    assert get_family_id_for_widget("spotify_visualizer") is None


def test_unknown_ids_resolve_to_none():
    assert get_family_id_for_widget("does_not_exist") is None
    assert get_family_id_for_widget("") is None
    assert get_widget_family_descriptor("does_not_exist") is None
    assert get_widget_family_descriptor("") is None
    assert get_active_member_widget_ids("does_not_exist") == ()


def test_expected_core_families_present():
    ids = {f.family_id for f in get_widget_family_descriptors()}
    # These families own ungated members and must always be available.
    for expected in ("clocks", "weather", "media", "reddit", "gmail"):
        assert expected in ids


def test_clocks_family_owns_all_three_clocks():
    family = get_widget_family_descriptor("clocks")
    assert family is not None
    assert family.member_widget_ids == ("clock", "clock2", "clock3")


def test_imgur_family_follows_dev_env_gating(monkeypatch):
    # Imgur is deprecated/dev-gated: absent without SRPSS_ENABLE_DEV, present with.
    # The neutral catalog caches are keyed on an environment signature, so a
    # monkeypatched env is reflected without reloading modules.
    from core.settings import widget_family_catalog as wfc

    monkeypatch.delenv("SRPSS_ENABLE_DEV", raising=False)
    assert wfc.get_widget_family_descriptor("imgur") is None
    assert wfc.get_family_id_for_widget("imgur") is None

    monkeypatch.setenv("SRPSS_ENABLE_DEV", "true")
    assert wfc.get_widget_family_descriptor("imgur") is not None
    assert wfc.get_family_id_for_widget("imgur") == "imgur"


def test_steam_family_gating_matches_active_members():
    # Steam owns ungated members (achievement_pulse, abandonment_issues) so the
    # family is always available; --devsteam only adds the gated members. The
    # neutral catalog and runtime-descriptor caches are env-signature keyed, so
    # toggling the gate is reflected without clearing caches.
    import rendering.widget_descriptors as wd

    dev_gates.force_gate(steam=False)
    try:
        family = wd.get_widget_family_descriptor("steam")
        assert family is not None
        active = set(wd.get_active_member_widget_ids("steam"))
        assert "achievement_pulse" in active
        assert "abandonment_issues" in active
        # Gated members are absent from the active set without --devsteam.
        assert "steam_progress" not in active
        assert "friend_pulse" not in active

        dev_gates.force_gate(steam=True)
        active_dev = set(wd.get_active_member_widget_ids("steam"))
        assert "steam_progress" in active_dev
        assert "friend_pulse" in active_dev
    finally:
        dev_gates.force_gate(steam=False)

"""Remote CUSTOM visualizer capability admission, incl. delayed callback (E2 §2).

These cross the ACTUAL remote reconcile / delayed fallback-recheck / final-create
seams (not only ``_setup_spotify_visualizer``) and prove a stale/delayed callback
cannot create or reuse a Visualizer after Media or Visualizers was deactivated,
because current canonical capability state is re-read at execution/final-create
time and fails closed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import rendering.widget_setup_all as wsa


class _StubSettings:
    """Live settings authority stand-in; ``get('widgets')`` is re-read each call."""

    def __init__(self, widgets: dict):
        self.widgets = widgets

    def get(self, key, default=None):
        return self.widgets if key == "widgets" else default


class _StubTargetManager:
    def __init__(self, settings):
        self._settings_manager = settings
        self.create_calls = 0

    def create_spotify_visualizer_widget(self, *a, **k):
        self.create_calls += 1
        return SimpleNamespace()

    def _register_spotify_secondary_fade(self, w):
        pass


class _StubTarget:
    def __init__(self, manager):
        self.spotify_visualizer_widget = None
        self._widget_manager = manager
        self.media_widget = SimpleNamespace(alive=True)  # stale/live Media object

    def _apply_saved_custom_layouts(self):
        pass


class _StubMgr:
    def __init__(self, settings, token: int = 1):
        self._settings_manager = settings
        self._parent = SimpleNamespace(_exiting=False)
        self._remote_custom_visualizer_reconcile_token = token


ACTIVE = {"family_activation": {"media": True, "visualizers": True}}
VIS_OFF = {"family_activation": {"media": True, "visualizers": False}}
MEDIA_OFF = {"family_activation": {"media": False, "visualizers": True}}


@pytest.fixture(autouse=True)
def _neutralize_startup(monkeypatch):
    # The final-create helper touches startup/layout helpers that need real
    # widgets; neutralize them so the test isolates the capability admission.
    from rendering.multi_monitor_coordinator import get_coordinator
    get_coordinator().clear_visualizer_failover()
    monkeypatch.setattr(wsa, "_start_secondary_widget", lambda *a, **k: None)
    monkeypatch.setattr(wsa, "_reapply_saved_custom_layouts_after_startup", lambda *a, **k: None)
    yield
    get_coordinator().clear_visualizer_failover()


def _fake_resolution_to(target):
    def _resolve(target_screen_index, current_display=None):
        return SimpleNamespace(
            requested_display=target,
            requested_is_participating=True,
            requested_has_runtime_presence=True,
            chosen_display=target,
            fallback_display=None,
        )

    return _resolve


# --- Final creation boundary ------------------------------------------------


def test_final_create_blocked_when_visualizers_deactivated():
    mgr = _StubTargetManager(_StubSettings(VIS_OFF))
    target = _StubTarget(mgr)
    wsa._create_remote_custom_visualizer_on_target(target, {}, {}, 1, None)
    assert mgr.create_calls == 0


def test_final_create_blocked_when_media_deactivated_stale_media_present():
    # A stale/live Media QWidget is present on the target, but Media capability is
    # off: the final boundary must still fail closed.
    mgr = _StubTargetManager(_StubSettings(MEDIA_OFF))
    target = _StubTarget(mgr)
    wsa._create_remote_custom_visualizer_on_target(target, {}, {}, 1, None)
    assert mgr.create_calls == 0


def test_final_create_blocked_when_settings_manager_missing():
    # Cannot resolve current capability state -> fail closed.
    mgr = _StubTargetManager(None)
    target = _StubTarget(mgr)
    wsa._create_remote_custom_visualizer_on_target(target, {}, {}, 1, None)
    assert mgr.create_calls == 0


def test_final_create_allowed_when_active():
    mgr = _StubTargetManager(_StubSettings(ACTIVE))
    target = _StubTarget(mgr)
    wsa._create_remote_custom_visualizer_on_target(target, {}, {}, 1, None)
    assert mgr.create_calls == 1


# --- Delayed fallback recheck (the formerly broken path) --------------------


def _run_delayed(monkeypatch, mgr_settings, target):
    from rendering.multi_monitor_coordinator import get_coordinator
    monkeypatch.setattr(wsa, "describe_visualizer_spawn_display", _fake_resolution_to(target))
    # The recheck re-reads live CUSTOM routing from Settings; keep it CUSTOM-routed
    # to monitor 2 so the capability outcome is what these tests isolate.
    monkeypatch.setattr(wsa, "is_custom_position_selected_for_widget", lambda *a, **k: True)
    monkeypatch.setattr(wsa, "get_effective_monitor_value_for_widget", lambda *a, **k: "2")
    mgr = _StubMgr(mgr_settings)
    # Arm a grace so the recheck's global generation check is satisfied; the
    # capability outcome is what these tests isolate.
    generation = get_coordinator().arm_visualizer_grace(intended_index=1, origin_manager=mgr)
    mgr._remote_custom_visualizer_reconcile_token = 1
    # widgets_config here is the STALE copy captured at schedule time (active),
    # deliberately different from the live mgr settings.
    stale_active_copy = {"family_activation": {"media": True, "visualizers": True}}
    wsa._run_remote_custom_visualizer_fallback_recheck(
        mgr, stale_active_copy, {}, 0, None, SimpleNamespace(alive=True),
        target_screen_index=1, token=1, generation=generation,
    )


def test_delayed_recheck_no_create_when_visualizers_deactivated(monkeypatch):
    # B: scheduled while active, Visualizers deactivated before the callback runs.
    target_mgr = _StubTargetManager(_StubSettings(VIS_OFF))
    target = _StubTarget(target_mgr)
    _run_delayed(monkeypatch, _StubSettings(VIS_OFF), target)
    assert target_mgr.create_calls == 0


def test_delayed_recheck_no_create_when_media_deactivated(monkeypatch):
    # C: scheduled while active, Media deactivated before the callback runs.
    target_mgr = _StubTargetManager(_StubSettings(MEDIA_OFF))
    target = _StubTarget(target_mgr)
    _run_delayed(monkeypatch, _StubSettings(MEDIA_OFF), target)
    assert target_mgr.create_calls == 0


def test_delayed_recheck_creates_when_still_active(monkeypatch):
    # D: still active at execution -> the correct remote path still creates.
    target_mgr = _StubTargetManager(_StubSettings(ACTIVE))
    target = _StubTarget(target_mgr)
    _run_delayed(monkeypatch, _StubSettings(ACTIVE), target)
    assert target_mgr.create_calls == 1


# --- Immediate reconcile ----------------------------------------------------


def test_immediate_reconcile_no_create_or_schedule_when_capability_inactive(monkeypatch):
    # A: immediate remote reconcile with capability inactive -> neither creates
    # nor schedules a delayed recheck.
    created = []
    scheduled = []
    monkeypatch.setattr(
        wsa, "_create_remote_custom_visualizer_on_target",
        lambda *a, **k: created.append(1),
    )
    monkeypatch.setattr(
        wsa, "_schedule_remote_custom_visualizer_fallback_recheck",
        lambda *a, **k: scheduled.append(1),
    )
    mgr = _StubMgr(_StubSettings(VIS_OFF))
    wsa._reconcile_remote_custom_visualizer(
        mgr, VIS_OFF, {}, 0, None, SimpleNamespace(alive=True),
    )
    assert created == []
    assert scheduled == []

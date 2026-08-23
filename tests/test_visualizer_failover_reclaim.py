"""E2.7 — Visualizer CUSTOM display failover/reclaim lifecycle regression bar.

Covers the contract in Current_Plan.md E2.7.7 against the real reconcile /
delayed-recheck / reclaim seams in ``rendering.widget_setup_all`` plus the
runtime-only fallback record on the coordinator:

- 30s one-shot grace (no premature fallback);
- target returns inside grace -> zero fallback creation;
- target unavailable through deadline -> exactly one temporary fallback;
- target returns after fallback -> fallback retired, configured sole owner;
- configured monitor/geometry never persisted by failover (temporary only);
- repeated return events idempotent;
- return-event/deadline race -> exactly one owner;
- capability deactivated during grace / while reclaiming -> no (stale) creation;
- target disappears again after reclaim -> fresh token, no stale-token reuse;
- no participating fallback target -> fail closed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import rendering.widget_setup_all as wsa
from rendering.multi_monitor_coordinator import get_coordinator


ACTIVE = {"family_activation": {"media": True, "visualizers": True}}
VIS_OFF = {"family_activation": {"media": True, "visualizers": False}}


class _Settings:
    def __init__(self, widgets: dict):
        self.widgets = widgets
        self.set_calls: list = []
        self.save_calls = 0

    def get(self, key, default=None):
        return self.widgets if key == "widgets" else default

    def set(self, key, value):
        self.set_calls.append((key, value))

    def save(self):
        self.save_calls += 1


class _Mgr:
    def __init__(self, settings=None):
        self._settings_manager = settings
        self.create_calls = 0
        self.cleanup_calls: list = []
        self.unregister_calls: list = []
        self._parent = None
        self._remote_custom_visualizer_reconcile_token = 0

    def create_spotify_visualizer_widget(self, *a, **k):
        self.create_calls += 1
        vis = SimpleNamespace()
        if self._parent is not None:
            self._parent.spotify_visualizer_widget = vis
        return vis

    def _register_spotify_secondary_fade(self, w):
        pass

    def cleanup_widget(self, name):
        self.cleanup_calls.append(name)
        return True

    def unregister_widget(self, name):
        self.unregister_calls.append(name)

    def _bind_parent_attribute(self, attr, w):
        if self._parent is not None:
            setattr(self._parent, attr, w)


class _Display:
    """Weakref-able display stand-in (a real DisplayWidget is weakref-able)."""

    def __init__(self, screen_index, mgr, media=True, has_vis=False):
        self.screen_index = screen_index
        self._widget_manager = mgr
        self.media_widget = SimpleNamespace() if media else None
        self.spotify_visualizer_widget = SimpleNamespace() if has_vis else None
        self._thread_manager = None
        self._exiting = False

    def _apply_saved_custom_layouts(self):
        pass


def _make_display(screen_index, settings=None, media=True, has_vis=False):
    mgr = _Mgr(settings)
    display = _Display(screen_index, mgr, media=media, has_vis=has_vis)
    mgr._parent = display
    return display, mgr


def _resolution(*, requested_display, requested_is_participating, chosen_display, fallback_display):
    return SimpleNamespace(
        requested_display=requested_display,
        requested_is_participating=requested_is_participating,
        requested_has_runtime_presence=requested_display is not None,
        chosen_display=chosen_display,
        fallback_display=fallback_display,
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    # Isolate only our own runtime fallback record; do NOT reset the coordinator
    # singleton, which would disturb real DisplayWidget state in other suites.
    get_coordinator().clear_visualizer_fallback()
    monkeypatch.setattr(wsa, "_start_secondary_widget", lambda *a, **k: None)
    monkeypatch.setattr(wsa, "_reapply_saved_custom_layouts_after_startup", lambda *a, **k: None)
    yield
    get_coordinator().clear_visualizer_fallback()


# --- Grace: 30 seconds, one-shot -------------------------------------------


def test_fallback_grace_is_thirty_seconds():
    assert wsa.REMOTE_CUSTOM_VISUALIZER_FALLBACK_GRACE_MS == 30000


def test_reconcile_defers_fallback_when_target_known_but_not_participating(monkeypatch):
    # Grace: a runtime-known-but-not-participating configured target must NOT
    # birth an immediate fallback; it schedules one deferred recheck instead.
    scheduled = []
    created = []
    monkeypatch.setattr(wsa, "_schedule_remote_custom_visualizer_fallback_recheck",
                        lambda *a, **k: scheduled.append(k.get("target_screen_index")))
    monkeypatch.setattr(wsa, "_create_remote_custom_visualizer_on_target",
                        lambda *a, **k: created.append(1))
    monkeypatch.setattr(wsa, "is_custom_position_selected_for_widget", lambda *a, **k: True)
    monkeypatch.setattr(wsa, "get_effective_monitor_value_for_widget", lambda *a, **k: "2")
    requested, _ = _make_display(1)  # configured monitor (index 1) not participating
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=requested, requested_is_participating=False,
            chosen_display=requested, fallback_display=SimpleNamespace(screen_index=0),
        ),
    )
    local, local_mgr = _make_display(0, settings=_Settings(ACTIVE))
    wsa._reconcile_remote_custom_visualizer(local_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    assert scheduled == [1]
    assert created == []


# --- Deadline: exactly one temporary fallback ------------------------------


def _run_recheck(monkeypatch, *, requested, requested_participating, fallback, origin_settings=ACTIVE):
    origin, origin_mgr = _make_display(0, settings=_Settings(origin_settings))
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=requested, requested_is_participating=requested_participating,
            chosen_display=(requested if requested_participating else fallback),
            fallback_display=fallback,
        ),
    )
    wsa._run_remote_custom_visualizer_fallback_recheck(
        origin_mgr, dict(origin_settings), {}, 0, None, SimpleNamespace(),
        target_screen_index=1, token=0,
    )
    return origin_mgr


def test_deadline_creates_exactly_one_temporary_fallback(monkeypatch):
    fallback, fallback_mgr = _make_display(0, settings=_Settings(ACTIVE))
    requested, _ = _make_display(1)  # still not participating
    _run_recheck(monkeypatch, requested=requested, requested_participating=False, fallback=fallback)
    assert fallback_mgr.create_calls == 1
    intended, host = get_coordinator().get_visualizer_fallback()
    assert intended == 1
    assert host is fallback  # temporary owner on the non-configured display


def test_target_returns_inside_grace_creates_no_fallback(monkeypatch):
    # Configured target participating by the time the recheck runs -> the
    # visualizer is created on the CONFIGURED display, and no fallback is recorded.
    requested, requested_mgr = _make_display(1, settings=_Settings(ACTIVE))
    _run_recheck(monkeypatch, requested=requested, requested_participating=True, fallback=None)
    assert requested_mgr.create_calls == 1
    assert get_coordinator().get_visualizer_fallback() == (None, None)


def test_no_participating_fallback_target_fails_closed(monkeypatch):
    requested, _ = _make_display(1)
    origin_mgr = _run_recheck(monkeypatch, requested=requested, requested_participating=False, fallback=None)
    assert get_coordinator().get_visualizer_fallback() == (None, None)


def test_capability_off_during_grace_creates_no_fallback(monkeypatch):
    fallback, fallback_mgr = _make_display(0, settings=_Settings(VIS_OFF))
    requested, _ = _make_display(1)
    _run_recheck(monkeypatch, requested=requested, requested_participating=False,
                 fallback=fallback, origin_settings=VIS_OFF)
    assert fallback_mgr.create_calls == 0
    assert get_coordinator().get_visualizer_fallback() == (None, None)


# --- Reclaim: configured returns after fallback ----------------------------


def _arm_fallback_record(intended_index, host):
    get_coordinator().set_visualizer_fallback(intended_index, host)


def test_reclaim_retires_fallback_and_restores_configured(monkeypatch):
    host, host_mgr = _make_display(0, has_vis=True)  # temporary fallback owner
    configured, configured_mgr = _make_display(1, settings=_Settings(ACTIVE))
    _arm_fallback_record(1, host)
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=configured, requested_is_participating=True,
            chosen_display=configured, fallback_display=None,
        ),
    )
    wsa.reclaim_remote_custom_visualizer_owner()
    # Temporary owner retired, configured display is now the sole owner.
    assert "spotify_visualizer" in host_mgr.cleanup_calls
    assert host.spotify_visualizer_widget is None
    assert configured_mgr.create_calls == 1
    assert get_coordinator().get_visualizer_fallback() == (None, None)


def test_reclaim_does_not_persist_monitor_or_geometry(monkeypatch):
    host, host_mgr = _make_display(0, has_vis=True)
    settings = _Settings(ACTIVE)
    configured, configured_mgr = _make_display(1, settings=settings)
    _arm_fallback_record(1, host)
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=configured, requested_is_participating=True,
            chosen_display=configured, fallback_display=None,
        ),
    )
    wsa.reclaim_remote_custom_visualizer_owner()
    # Failover/reclaim is temporary runtime ownership only: it must never write
    # the configured monitor, position, size, viewport, or clamped geometry.
    assert settings.set_calls == []
    assert settings.save_calls == 0


def test_reclaim_is_idempotent_across_repeated_events(monkeypatch):
    host, host_mgr = _make_display(0, has_vis=True)
    configured, configured_mgr = _make_display(1, settings=_Settings(ACTIVE))
    _arm_fallback_record(1, host)
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=configured, requested_is_participating=True,
            chosen_display=configured, fallback_display=None,
        ),
    )
    wsa.reclaim_remote_custom_visualizer_owner()
    wsa.reclaim_remote_custom_visualizer_owner()  # repeated topology event
    assert configured_mgr.create_calls == 1  # not re-created
    assert get_coordinator().get_visualizer_fallback() == (None, None)


def test_reclaim_noop_when_no_fallback_recorded(monkeypatch):
    # Return-event/deadline race: configured returns before any fallback was
    # created (no record) -> reclaim is a no-op; the pending recheck later creates
    # exactly one owner on the configured display.
    configured, configured_mgr = _make_display(1, settings=_Settings(ACTIVE))
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=configured, requested_is_participating=True,
            chosen_display=configured, fallback_display=None,
        ),
    )
    wsa.reclaim_remote_custom_visualizer_owner()
    assert configured_mgr.create_calls == 0  # nothing to reclaim


def test_reclaim_blocked_when_configured_still_unavailable(monkeypatch):
    host, host_mgr = _make_display(0, has_vis=True)
    configured, configured_mgr = _make_display(1, settings=_Settings(ACTIVE))
    _arm_fallback_record(1, host)
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=configured, requested_is_participating=False,
            chosen_display=host, fallback_display=host,
        ),
    )
    wsa.reclaim_remote_custom_visualizer_owner()
    assert configured_mgr.create_calls == 0
    assert host_mgr.cleanup_calls == []  # temporary fallback left in place
    assert get_coordinator().get_visualizer_fallback() == (1, host)


def test_reclaim_blocked_when_capability_deactivated(monkeypatch):
    host, host_mgr = _make_display(0, has_vis=True)
    configured, configured_mgr = _make_display(1, settings=_Settings(VIS_OFF))
    _arm_fallback_record(1, host)
    monkeypatch.setattr(
        wsa, "describe_visualizer_spawn_display",
        lambda idx, current_display=None: _resolution(
            requested_display=configured, requested_is_participating=True,
            chosen_display=configured, fallback_display=None,
        ),
    )
    wsa.reclaim_remote_custom_visualizer_owner()
    # Capability off -> no stale recreation, temporary owner untouched.
    assert configured_mgr.create_calls == 0
    assert host_mgr.cleanup_calls == []
    assert get_coordinator().get_visualizer_fallback() == (1, host)


# --- Token fencing: fresh grace after re-loss ------------------------------


def test_retire_bumps_host_token_to_fence_stale_callbacks():
    host, host_mgr = _make_display(0, has_vis=True)
    host_mgr._remote_custom_visualizer_reconcile_token = 5
    wsa._retire_visualizer_owner(host)
    assert host_mgr._remote_custom_visualizer_reconcile_token == 6
    assert "spotify_visualizer" in host_mgr.cleanup_calls
    assert host.spotify_visualizer_widget is None


def test_stale_token_recheck_aborts(monkeypatch):
    # A delayed recheck carrying an out-of-date token must not act (fresh grace
    # after re-loss uses a new token; stale-token work is fenced).
    _, mgr = _make_display(0, settings=_Settings(ACTIVE))
    mgr._remote_custom_visualizer_reconcile_token = 9
    created = []
    monkeypatch.setattr(wsa, "_create_remote_custom_visualizer_on_target",
                        lambda *a, **k: created.append(1))
    wsa._run_remote_custom_visualizer_fallback_recheck(
        mgr, dict(ACTIVE), {}, 0, None, SimpleNamespace(), target_screen_index=1, token=8,
    )
    assert created == []


# --- Creation boundary records/clears fallback state -----------------------


def test_create_on_non_configured_display_records_fallback(monkeypatch):
    host, host_mgr = _make_display(0, settings=_Settings(ACTIVE))
    wsa._create_remote_custom_visualizer_on_target(host, ACTIVE, {}, 1, None)
    intended, recorded_host = get_coordinator().get_visualizer_fallback()
    assert intended == 1
    assert recorded_host is host


def test_create_on_configured_display_clears_fallback(monkeypatch):
    # Pre-existing stale record; creating on the configured display clears it.
    prior, _ = _make_display(0)
    get_coordinator().set_visualizer_fallback(1, prior)
    configured, configured_mgr = _make_display(1, settings=_Settings(ACTIVE))
    wsa._create_remote_custom_visualizer_on_target(configured, ACTIVE, {}, 1, None)
    assert configured_mgr.create_calls == 1
    assert get_coordinator().get_visualizer_fallback() == (None, None)

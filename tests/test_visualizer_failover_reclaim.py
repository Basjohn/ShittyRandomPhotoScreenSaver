"""E2.7 — Visualizer CUSTOM display failover/reclaim lifecycle regression bar.

Exercises the real reconcile / delayed-recheck / reclaim seams in
``rendering.widget_setup_all`` against the audit-corrected contract:

- absent configured target gets the SAME 30 s grace (no immediate fallback);
- a pending grace is visible to topology reconciliation: a target returning
  before the deadline is restored immediately and the stale callback is fenced;
- delayed/reclaim work re-resolves the CURRENT CUSTOM monitor from live Settings,
  so changing the configured monitor supersedes an old pending/fallback target;
- reclaim creates the configured owner only after retirement of the temporary
  owner is confirmed (retire-before-create is a hard guarantee);
- exactly one owner across the event/deadline race; capability re-checked; the
  configured monitor + saved geometry are never persisted by failover.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import rendering.widget_setup_all as wsa
from rendering.multi_monitor_coordinator import get_coordinator


ACTIVE = {"family_activation": {"media": True, "visualizers": True}}
VIS_OFF = {"family_activation": {"media": True, "visualizers": False}}
MEDIA_OFF = {"family_activation": {"media": False, "visualizers": True}}


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
    def __init__(self, settings=None, *, cleanup_ok=True):
        self._settings_manager = settings
        self.create_calls = 0
        self.cleanup_calls: list = []
        self.unregister_calls: list = []
        self._parent = None
        self._remote_custom_visualizer_reconcile_token = 0
        self._cleanup_ok = cleanup_ok

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
        return bool(self._cleanup_ok)

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


def _make_display(screen_index, settings=None, media=True, has_vis=False, cleanup_ok=True):
    mgr = _Mgr(settings, cleanup_ok=cleanup_ok)
    display = _Display(screen_index, mgr, media=media, has_vis=has_vis)
    mgr._parent = display
    return display, mgr


class _World:
    """Controllable display topology for describe_visualizer_spawn_display."""

    def __init__(self):
        self.participants: dict = {}   # index -> display (participating)
        self.known: dict = {}          # index -> display (runtime-known, not participating)
        self.configured_index = 1      # current CUSTOM monitor (0-based)
        self.custom = True

    def resolve(self, idx, current_display=None):
        participating = idx in self.participants
        req = self.participants.get(idx) or self.known.get(idx)
        parts = [self.participants[k] for k in sorted(self.participants)]
        fb = parts[0] if parts else None
        return SimpleNamespace(
            requested_display=req,
            requested_is_participating=participating,
            requested_has_runtime_presence=req is not None,
            chosen_display=(req if participating else fb),
            fallback_display=fb,
        )


@pytest.fixture
def world(monkeypatch):
    w = _World()
    monkeypatch.setattr(wsa, "describe_visualizer_spawn_display", w.resolve)
    monkeypatch.setattr(wsa, "is_custom_position_selected_for_widget", lambda *a, **k: w.custom)
    monkeypatch.setattr(
        wsa, "get_effective_monitor_value_for_widget",
        lambda *a, **k: str(w.configured_index + 1),
    )
    return w


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    get_coordinator().clear_visualizer_failover()
    monkeypatch.setattr(wsa, "_start_secondary_widget", lambda *a, **k: None)
    monkeypatch.setattr(wsa, "_reapply_saved_custom_layouts_after_startup", lambda *a, **k: None)
    yield
    get_coordinator().clear_visualizer_failover()


@pytest.fixture
def scheduler(monkeypatch):
    """Capture scheduled grace deadlines so tests can fire them deterministically."""
    captured: list = []

    def _capture(delay_ms, owner, callback, *args, **kwargs):
        captured.append((callback, owner, args))

    monkeypatch.setattr(wsa, "_schedule_weak_runtime_callback", _capture)

    def fire_all():
        for callback, owner, args in list(captured):
            callback(owner, *args)

    return SimpleNamespace(captured=captured, fire_all=fire_all)


# --- Grace: 30 seconds, one-shot -------------------------------------------


def test_fallback_grace_is_thirty_seconds():
    assert wsa.REMOTE_CUSTOM_VISUALIZER_FALLBACK_GRACE_MS == 30000


def test_absent_target_gets_grace_not_immediate_fallback(world, scheduler):
    # gap-1: configured monitor 1 is COMPLETELY ABSENT from runtime (no runtime
    # object). It must get the 30 s grace, not an immediate fallback onto the
    # participating display 0.
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}          # display 1 absent entirely
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(ACTIVE))
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    # No immediate fallback owner was created on display 0.
    assert m0.create_calls == 0
    # A pending grace is armed and recorded (visible to topology reconciliation).
    assert len(scheduler.captured) == 1
    record = get_coordinator().get_visualizer_failover()
    assert record is not None and record["pending"] is True and record["host"] is None
    assert record["intended_index"] == 1


def test_runtime_known_target_also_gets_grace(world, scheduler):
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    d1, m1 = _make_display(1)  # runtime-known but not participating
    world.participants = {0: d0}
    world.known = {1: d1}
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(ACTIVE))
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    assert m0.create_calls == 0
    assert len(scheduler.captured) == 1
    assert get_coordinator().get_visualizer_failover()["pending"] is True


def test_configured_target_participating_creates_immediately(world, scheduler):
    d1, m1 = _make_display(1, settings=_Settings(ACTIVE))
    world.participants = {1: d1}
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(ACTIVE))
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    assert m1.create_calls == 1
    assert scheduler.captured == []  # no grace needed
    assert get_coordinator().get_visualizer_failover() is None


# --- Deadline behaviour ----------------------------------------------------


def test_deadline_creates_one_temporary_fallback_when_still_absent(world, scheduler):
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(ACTIVE))
    # origin needs live settings the recheck can read.
    origin_mgr._settings_manager = _Settings(ACTIVE)
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    scheduler.fire_all()  # 30 s deadline, display 1 still absent
    assert m0.create_calls == 1
    record = get_coordinator().get_visualizer_failover()
    assert record["pending"] is False and record["host"] is d0 and record["intended_index"] == 1


def test_no_participating_display_at_deadline_fails_closed(world, scheduler):
    world.participants = {}  # nothing participating at all
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(ACTIVE))
    origin_mgr._settings_manager = _Settings(ACTIVE)
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    scheduler.fire_all()
    # Fail closed: nothing invented; pending grace retained for a later event.
    record = get_coordinator().get_visualizer_failover()
    assert record is not None and record["pending"] is True


def test_capability_off_at_deadline_creates_nothing(world, scheduler):
    d0, m0 = _make_display(0, settings=_Settings(VIS_OFF))
    world.participants = {0: d0}
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(VIS_OFF))
    origin_mgr._settings_manager = _Settings(VIS_OFF)
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    # reconcile used ACTIVE (capability effective) to arm grace; deadline re-reads
    # live VIS_OFF settings and must create nothing.
    scheduler.fire_all()
    assert m0.create_calls == 0


# --- Event before deadline: immediate restore + stale-callback fence -------


def test_return_during_grace_restores_immediately_and_fences_stale_callback(world, scheduler):
    # gap-2: display 1 returns 5 s into the grace via a topology event. Reclaim
    # must restore it immediately (not wait for the deadline) and fence the
    # still-pending deadline callback so it cannot create a second owner.
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(ACTIVE))
    origin_mgr._settings_manager = _Settings(ACTIVE)
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    assert get_coordinator().get_visualizer_failover()["pending"] is True

    # Display 1 comes back; WM_DISPLAYCHANGE -> reclaim.
    d1, m1 = _make_display(1, settings=_Settings(ACTIVE))
    world.participants = {0: d0, 1: d1}
    wsa.reclaim_remote_custom_visualizer_owner()
    assert m1.create_calls == 1                 # restored immediately on configured
    assert m0.create_calls == 0                 # no temporary fallback ever made
    assert get_coordinator().get_visualizer_failover() is None

    # The still-pending deadline now fires: it must be fenced (no second owner).
    scheduler.fire_all()
    assert m1.create_calls == 1
    assert m0.create_calls == 0


# --- Current configured monitor change wins (gap-3) ------------------------


def test_settings_monitor_change_during_grace_supersedes_target(world, scheduler):
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=_Settings(ACTIVE))
    origin_mgr._settings_manager = _Settings(ACTIVE)
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())

    # User changes the configured CUSTOM monitor to display 2, which is present.
    d2, m2 = _make_display(2, settings=_Settings(ACTIVE))
    world.participants = {0: d0, 2: d2}
    world.configured_index = 2
    scheduler.fire_all()  # deadline re-resolves live monitor -> 2
    assert m2.create_calls == 1     # created on the NEW configured monitor
    assert m0.create_calls == 0


def test_settings_monitor_change_during_fallback_reclaims_new_target(world, scheduler):
    # A temporary fallback is live on display 0 for old monitor 1; the user then
    # reconfigures to monitor 2 which is participating. Reclaim must hand off to 2.
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True)
    get_coordinator().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=m0,
    )
    d2, m2 = _make_display(2, settings=_Settings(ACTIVE))
    world.participants = {0: d0, 2: d2}
    world.configured_index = 2
    wsa.reclaim_remote_custom_visualizer_owner()
    assert d0.spotify_visualizer_widget is None   # temporary owner retired
    assert m2.create_calls == 1                    # restored on the NEW monitor 2
    assert get_coordinator().get_visualizer_failover() is None


def test_reclaim_superseded_to_non_custom_clears_and_retires(world):
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True)
    get_coordinator().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=m0,
    )
    world.participants = {0: d0}
    world.custom = False  # visualizer no longer CUSTOM-routed
    wsa.reclaim_remote_custom_visualizer_owner()
    assert d0.spotify_visualizer_widget is None
    assert get_coordinator().get_visualizer_failover() is None


# --- Retire-before-create is a hard guarantee (gap-4) ----------------------


def test_reclaim_fails_closed_when_retirement_fails(world):
    # cleanup_widget returns False and the widget stays bound -> retirement is not
    # confirmed. Reclaim must NOT create a second owner; it defers.
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True, cleanup_ok=False)
    d1, m1 = _make_display(1, settings=_Settings(ACTIVE))
    get_coordinator().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=m0,
    )
    world.participants = {0: d0, 1: d1}
    world.configured_index = 1
    wsa.reclaim_remote_custom_visualizer_owner()
    assert m1.create_calls == 0                    # no second owner created
    assert d0.spotify_visualizer_widget is not None  # temporary owner still alive
    # Record retained so a later event can retry.
    assert get_coordinator().get_visualizer_failover() is not None


def test_retire_confirms_and_reclaims_when_cleanup_ok(world):
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True, cleanup_ok=True)
    d1, m1 = _make_display(1, settings=_Settings(ACTIVE))
    get_coordinator().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=m0,
    )
    world.participants = {0: d0, 1: d1}
    world.configured_index = 1
    wsa.reclaim_remote_custom_visualizer_owner()
    assert "spotify_visualizer" in m0.cleanup_calls
    assert d0.spotify_visualizer_widget is None
    assert m1.create_calls == 1
    assert get_coordinator().get_visualizer_failover() is None


def test_retire_owner_returns_false_on_cleanup_failure():
    d0, m0 = _make_display(0, has_vis=True, cleanup_ok=False)
    assert wsa._retire_visualizer_owner(d0) is False
    assert d0.spotify_visualizer_widget is not None  # not orphaned/unbound
    assert m0._remote_custom_visualizer_reconcile_token == 1  # still fenced


def test_retire_owner_returns_true_and_bumps_token_on_success():
    d0, m0 = _make_display(0, has_vis=True, cleanup_ok=True)
    m0._remote_custom_visualizer_reconcile_token = 5
    assert wsa._retire_visualizer_owner(d0) is True
    assert d0.spotify_visualizer_widget is None
    assert m0._remote_custom_visualizer_reconcile_token == 6


# --- Reclaim guards --------------------------------------------------------


def test_reclaim_noop_without_record(world):
    d1, m1 = _make_display(1, settings=_Settings(ACTIVE))
    world.participants = {1: d1}
    wsa.reclaim_remote_custom_visualizer_owner()
    assert m1.create_calls == 0


def test_reclaim_keeps_record_when_configured_still_absent(world):
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True)
    get_coordinator().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=m0,
    )
    world.participants = {0: d0}  # configured (1) still absent
    world.configured_index = 1
    wsa.reclaim_remote_custom_visualizer_owner()
    assert m0.cleanup_calls == []
    assert get_coordinator().get_visualizer_failover() is not None


def test_reclaim_blocked_when_capability_deactivated(world):
    d0, m0 = _make_display(0, settings=_Settings(VIS_OFF), has_vis=True)
    d1, m1 = _make_display(1, settings=_Settings(VIS_OFF))
    get_coordinator().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=m0,
    )
    world.participants = {0: d0, 1: d1}
    world.configured_index = 1
    wsa.reclaim_remote_custom_visualizer_owner()
    assert m1.create_calls == 0
    assert d0.spotify_visualizer_widget is not None
    assert get_coordinator().get_visualizer_failover() is not None


def test_reclaim_idempotent_across_repeated_events(world):
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True)
    d1, m1 = _make_display(1, settings=_Settings(ACTIVE))
    get_coordinator().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=m0,
    )
    world.participants = {0: d0, 1: d1}
    world.configured_index = 1
    wsa.reclaim_remote_custom_visualizer_owner()
    wsa.reclaim_remote_custom_visualizer_owner()
    assert m1.create_calls == 1
    assert get_coordinator().get_visualizer_failover() is None


# --- Global grace generation authority (blocker-1) -------------------------


def test_repeated_reconcile_from_other_displays_arms_only_one_grace(world, scheduler):
    # Multiple DisplayWidgets run setup/reconcile during ONE outage for the single
    # Visualizer. Only the first arms a grace; the others must not start/reset a
    # second 30 s deadline.
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}          # configured monitor 1 absent
    world.configured_index = 1
    _, om0 = _make_display(0, settings=_Settings(ACTIVE))
    _, om2 = _make_display(2, settings=_Settings(ACTIVE))
    wsa._reconcile_remote_custom_visualizer(om0, ACTIVE, {}, 0, None, SimpleNamespace())
    wsa._reconcile_remote_custom_visualizer(om2, ACTIVE, {}, 2, None, SimpleNamespace())
    assert len(scheduler.captured) == 1  # exactly one grace across both origins


def test_old_generation_callback_from_other_display_is_fenced(world):
    # A delayed callback from ANOTHER DisplayWidget still carrying an OLD outage
    # generation must not act after reclaim / a new outage, even if that display's
    # LOCAL token happens to match. Generation is the global authority.
    coord = get_coordinator()
    gen1 = coord.arm_visualizer_grace(intended_index=1, origin_manager=None)  # outage 1
    coord.clear_visualizer_failover()                                          # reclaim/return
    coord.arm_visualizer_grace(intended_index=1, origin_manager=None)         # new outage (gen2)

    other, other_mgr = _make_display(3, settings=_Settings(ACTIVE))
    other_mgr._settings_manager = _Settings(ACTIVE)
    other_mgr._remote_custom_visualizer_reconcile_token = 7  # local token DOES match below
    world.participants = {3: other}
    world.configured_index = 1
    wsa._run_remote_custom_visualizer_fallback_recheck(
        other_mgr, dict(ACTIVE), {}, 3, None, SimpleNamespace(),
        target_screen_index=1, token=7, generation=gen1,
    )
    assert other_mgr.create_calls == 0  # fenced by stale generation, not by token


def test_current_generation_callback_acts(world):
    coord = get_coordinator()
    gen = coord.arm_visualizer_grace(intended_index=1, origin_manager=None)
    d1, m1 = _make_display(1, settings=_Settings(ACTIVE))
    m1._settings_manager = _Settings(ACTIVE)
    m1._remote_custom_visualizer_reconcile_token = 1
    world.participants = {1: d1}
    world.configured_index = 1
    wsa._run_remote_custom_visualizer_fallback_recheck(
        m1, dict(ACTIVE), {}, 1, None, SimpleNamespace(),
        target_screen_index=1, token=1, generation=gen,
    )
    assert m1.create_calls == 1


def test_new_outage_after_reclaim_gets_fresh_generation(world, scheduler):
    # After a handback, the target disappearing again is a genuinely NEW outage
    # with its own fresh grace/generation (strictly greater than the old one).
    coord = get_coordinator()
    gen1 = coord.arm_visualizer_grace(intended_index=1, origin_manager=None)
    coord.clear_visualizer_failover()  # reclaim/handback ends outage 1
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}       # monitor 1 absent again
    world.configured_index = 1
    _, om0 = _make_display(0, settings=_Settings(ACTIVE))
    wsa._reconcile_remote_custom_visualizer(om0, ACTIVE, {}, 0, None, SimpleNamespace())
    record = coord.get_visualizer_failover()
    assert record is not None and record["generation"] > gen1
    assert not coord.is_visualizer_failover_generation_current(gen1)


# --- Retirement failure must never be discarded (blocker-2) -----------------


def test_non_custom_branch_retains_record_when_retire_fails(world):
    # "No longer CUSTOM" branch: if the stray owner's retirement is not confirmed,
    # the failover record must be retained (never normalized while it may be live).
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True, cleanup_ok=False)
    get_coordinator().set_visualizer_fallback_owner(intended_index=1, host=d0, origin_manager=m0)
    world.participants = {0: d0}
    world.custom = False  # visualizer no longer CUSTOM-routed
    wsa.reclaim_remote_custom_visualizer_owner()
    assert d0.spotify_visualizer_widget is not None          # still alive
    assert get_coordinator().get_visualizer_failover() is not None  # record retained


def test_already_owns_branch_retains_record_when_stray_retire_fails(world):
    # "Configured already owns" branch: a stray temporary owner whose retirement
    # fails must not be discarded; retain the record for a later retry.
    stray, sm = _make_display(0, settings=_Settings(ACTIVE), has_vis=True, cleanup_ok=False)
    configured, cm = _make_display(1, settings=_Settings(ACTIVE), has_vis=True)  # already owns
    get_coordinator().set_visualizer_fallback_owner(intended_index=1, host=stray, origin_manager=sm)
    world.participants = {0: stray, 1: configured}
    world.configured_index = 1
    wsa.reclaim_remote_custom_visualizer_owner()
    assert stray.spotify_visualizer_widget is not None       # stray still alive
    assert get_coordinator().get_visualizer_failover() is not None  # record retained


# --- Capability deactivation retires the failover lifecycle ----------------


def test_deactivation_retires_pending_grace_then_fresh_grace_after_reactivation(world, scheduler):
    # 1. pending grace -> capability off (Visualizers) -> state/generation retired
    #    -> stale callback no-op -> capability on -> fresh grace/generation.
    coord = get_coordinator()
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}          # configured monitor 1 absent
    world.configured_index = 1
    _, om0 = _make_display(0, settings=_Settings(ACTIVE))
    om0._settings_manager = _Settings(ACTIVE)
    wsa._reconcile_remote_custom_visualizer(om0, ACTIVE, {}, 0, None, SimpleNamespace())
    rec = coord.get_visualizer_failover()
    assert rec is not None and rec["pending"] is True
    gen1 = rec["generation"]

    # Capability off -> failover lifecycle retired (record + generation).
    wsa.retire_visualizer_failover_on_capability_change(_Settings(VIS_OFF))
    assert coord.get_visualizer_failover() is None
    assert not coord.is_visualizer_failover_generation_current(gen1)

    # The stale pending deadline now fires -> fenced by the retired generation.
    scheduler.fire_all()
    assert m0.create_calls == 0

    # Explicit reactivation, target still absent -> a genuinely fresh grace.
    _, om0b = _make_display(0, settings=_Settings(ACTIVE))
    om0b._settings_manager = _Settings(ACTIVE)
    wsa._reconcile_remote_custom_visualizer(om0b, ACTIVE, {}, 0, None, SimpleNamespace())
    rec2 = coord.get_visualizer_failover()
    assert rec2 is not None and rec2["pending"] is True
    assert rec2["generation"] > gen1


def test_deactivation_media_off_retires_pending_grace(world, scheduler):
    # Media-off effective deactivation also retires the pending grace lifecycle.
    coord = get_coordinator()
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE))
    world.participants = {0: d0}
    world.configured_index = 1
    _, om0 = _make_display(0, settings=_Settings(ACTIVE))
    om0._settings_manager = _Settings(ACTIVE)
    wsa._reconcile_remote_custom_visualizer(om0, ACTIVE, {}, 0, None, SimpleNamespace())
    assert coord.get_visualizer_failover() is not None
    wsa.retire_visualizer_failover_on_capability_change(_Settings(MEDIA_OFF))
    assert coord.get_visualizer_failover() is None


def test_deactivation_retires_active_fallback_owner_and_state(world):
    # 2. active fallback -> capability off (Media) -> owner retired + state retired.
    coord = get_coordinator()
    d0, m0 = _make_display(0, settings=_Settings(MEDIA_OFF), has_vis=True, cleanup_ok=True)
    coord.set_visualizer_fallback_owner(intended_index=1, host=d0, origin_manager=m0)
    wsa.retire_visualizer_failover_on_capability_change(_Settings(MEDIA_OFF))
    assert "spotify_visualizer" in m0.cleanup_calls
    assert d0.spotify_visualizer_widget is None      # temporary owner retired
    assert coord.get_visualizer_failover() is None    # failover state retired


def test_deactivation_failed_retirement_retains_live_owner_record(world):
    # 3. failed fallback retirement on deactivation must NOT lose the live-owner
    #    record (retire is unconfirmed -> retain for a later retry).
    coord = get_coordinator()
    d0, m0 = _make_display(0, settings=_Settings(VIS_OFF), has_vis=True, cleanup_ok=False)
    coord.set_visualizer_fallback_owner(intended_index=1, host=d0, origin_manager=m0)
    wsa.retire_visualizer_failover_on_capability_change(_Settings(VIS_OFF))
    assert d0.spotify_visualizer_widget is not None   # still alive (not orphaned)
    assert coord.get_visualizer_failover() is not None  # record retained


def test_deactivation_noop_when_capability_effective(world):
    coord = get_coordinator()
    d0, m0 = _make_display(0, settings=_Settings(ACTIVE), has_vis=True)
    coord.set_visualizer_fallback_owner(intended_index=1, host=d0, origin_manager=m0)
    wsa.retire_visualizer_failover_on_capability_change(_Settings(ACTIVE))
    assert coord.get_visualizer_failover() is not None  # still effective -> untouched
    assert d0.spotify_visualizer_widget is not None
    assert m0.cleanup_calls == []


# --- Never persists monitor/geometry ---------------------------------------


def test_failover_and_reclaim_never_persist_settings(world, scheduler):
    settings = _Settings(ACTIVE)
    d0, m0 = _make_display(0, settings=settings)
    world.participants = {0: d0}
    world.configured_index = 1
    origin, origin_mgr = _make_display(0, settings=settings)
    origin_mgr._settings_manager = settings
    wsa._reconcile_remote_custom_visualizer(origin_mgr, ACTIVE, {}, 0, None, SimpleNamespace())
    scheduler.fire_all()  # temporary fallback created on display 0
    d1, m1 = _make_display(1, settings=settings)
    world.participants = {0: d0, 1: d1}
    wsa.reclaim_remote_custom_visualizer_owner()  # reclaim to display 1
    assert settings.set_calls == []
    assert settings.save_calls == 0

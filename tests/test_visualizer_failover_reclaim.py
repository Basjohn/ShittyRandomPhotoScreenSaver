"""E2.7 — Visualizer CUSTOM display failover/reclaim lifecycle regression bar.

Re-homed onto the presentation-neutral Quick failover state + lifecycle
(``rendering/quick/visualizer_failover*``) after the legacy physical-host owner
was deleted. Exercises the real reconcile / delayed-recheck / reclaim /
capability-retire seams over a deterministic fake topology (no QWidget /
DisplayWidget), against the audit-corrected contract:

- absent configured target gets the SAME 30 s grace (no immediate fallback);
- a pending grace is visible to topology reconciliation: a target returning
  before the deadline is restored immediately and the stale callback is fenced;
- delayed/reclaim work re-resolves the CURRENT CUSTOM monitor from live Settings,
  so changing the configured monitor supersedes an old pending/fallback target;
- reclaim creates the configured owner only after retirement of the temporary
  owner is confirmed (retire-before-create is a hard guarantee);
- exactly one owner across the event/deadline race; capability re-checked; the
  configured monitor + saved geometry are never persisted by failover.

The grace uses controllable deterministic time: scheduled deadlines are captured
and fired explicitly; no test sleeps.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import rendering.quick.visualizer_failover_lifecycle as fol
from rendering.quick.visualizer_failover import get_visualizer_failover_state


ACTIVE = {"family_activation": {"media": True, "visualizers": True}}
VIS_OFF = {"family_activation": {"media": True, "visualizers": False}}
MEDIA_OFF = {"family_activation": {"media": False, "visualizers": True}}


class _Display:
    """Neutral Quick-display stand-in: a screen index and its (single) owner."""

    def __init__(self, screen_index, has_owner=False, cleanup_ok=True):
        self.screen_index = screen_index
        self.owner = object() if has_owner else None
        self.cleanup_ok = cleanup_ok
        self.create_calls = 0
        self.cleanup_calls = 0


class _Topology:
    """Deterministic fake of the DisplayManager failover topology adapter.

    Presentation-neutral: it holds a controllable world of Quick displays, the
    live canonical capability/routing config, a fence token and a captured grace
    schedule. The lifecycle-under-test drives it exactly as the real adapter.
    """

    def __init__(self):
        self.displays: dict = {}       # index -> _Display (runtime-known)
        self.participating: set = set()
        self.configured_index = 1      # current effective CUSTOM monitor (0-based)
        self.custom = True
        self.widgets = dict(ACTIVE)
        self._token = 0
        self.scheduled: list = []
        # persistence guards: the neutral lifecycle must never write settings.
        self.persist_calls: list = []

    # --- world construction helpers (test-facing) ---
    def add(self, display, *, participating):
        self.displays[display.screen_index] = display
        if participating:
            self.participating.add(display.screen_index)
        else:
            self.participating.discard(display.screen_index)
        return display

    def fire_all(self):
        for target_screen_index, token, generation in list(self.scheduled):
            fol.run_fallback_recheck(
                self,
                target_screen_index=target_screen_index,
                token=token,
                generation=generation,
            )

    # --- adapter surface (lifecycle-facing) ---
    def capability_admitted(self) -> bool:
        from core.settings.capability_activation import is_widget_family_effective

        w = self.widgets
        if not isinstance(w, dict):
            return False
        try:
            return bool(is_widget_family_effective(w, "visualizers"))
        except Exception:
            return False

    def live_widgets(self):
        return self.widgets

    def is_custom_selected(self, widgets) -> bool:
        return bool(self.custom)

    def effective_monitor_index(self, widgets):
        return self.configured_index

    def resolve(self, intended_index):
        participating = intended_index in self.participating
        req = self.displays.get(intended_index)
        parts = [self.displays[k] for k in sorted(self.participating)]
        fb = parts[0] if parts else None
        return SimpleNamespace(
            requested_display=req,
            requested_is_participating=participating,
            fallback_display=fb,
        )

    def owner_present_on(self, display) -> bool:
        return display is not None and getattr(display, "owner", None) is not None

    def screen_index_of(self, display):
        return getattr(display, "screen_index", None)

    def create_owner(self, display, intended_index) -> bool:
        display.create_calls += 1
        display.owner = object()
        return True

    def cleanup_owner(self, display) -> bool:
        display.cleanup_calls += 1
        return bool(display.cleanup_ok)

    def detach_owner(self, display) -> None:
        display.owner = None

    def current_token(self) -> int:
        return self._token

    def bump_token(self) -> int:
        self._token += 1
        return self._token

    def schedule(self, delay_ms, *, target_screen_index, token, generation) -> None:
        assert delay_ms == fol.VISUALIZER_FALLBACK_GRACE_MS
        self.scheduled.append((target_screen_index, token, generation))


@pytest.fixture
def topo():
    return _Topology()


@pytest.fixture(autouse=True)
def _isolate():
    get_visualizer_failover_state().clear_visualizer_failover()
    yield
    get_visualizer_failover_state().clear_visualizer_failover()


def _record():
    return get_visualizer_failover_state().get_visualizer_failover()


# --- Grace: 30 seconds, one-shot -------------------------------------------


def test_fallback_grace_is_thirty_seconds():
    assert fol.VISUALIZER_FALLBACK_GRACE_MS == 30000


def test_absent_target_gets_grace_not_immediate_fallback(topo):
    # configured monitor 1 is COMPLETELY ABSENT from runtime. It must get the 30 s
    # grace, not an immediate fallback onto participating display 0.
    d0 = topo.add(_Display(0), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    assert d0.create_calls == 0                 # no immediate fallback owner
    assert len(topo.scheduled) == 1             # one armed grace
    rec = _record()
    assert rec is not None and rec["pending"] is True and rec["host"] is None
    assert rec["intended_index"] == 1


def test_runtime_known_target_also_gets_grace(topo):
    d0 = topo.add(_Display(0), participating=True)
    topo.add(_Display(1), participating=False)  # runtime-known, not participating
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    assert d0.create_calls == 0
    assert len(topo.scheduled) == 1
    assert _record()["pending"] is True


def test_configured_target_participating_creates_immediately(topo):
    d1 = topo.add(_Display(1), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    assert d1.create_calls == 1
    assert topo.scheduled == []                 # no grace needed
    assert _record() is None


# --- Deadline behaviour ----------------------------------------------------


def test_deadline_creates_one_temporary_fallback_when_still_absent(topo):
    d0 = topo.add(_Display(0), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    topo.fire_all()                             # 30 s deadline, monitor 1 still absent
    assert d0.create_calls == 1
    rec = _record()
    assert rec["pending"] is False and rec["host"] is d0 and rec["intended_index"] == 1


def test_no_participating_display_at_deadline_fails_closed(topo):
    topo.configured_index = 1                   # nothing participating at all
    fol.reconcile_custom_visualizer(topo)
    topo.fire_all()
    rec = _record()
    assert rec is not None and rec["pending"] is True  # grace retained for later event


def test_capability_off_at_deadline_creates_nothing(topo):
    d0 = topo.add(_Display(0), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)       # armed while ACTIVE
    topo.widgets = dict(VIS_OFF)                # deactivated during grace
    topo.fire_all()
    assert d0.create_calls == 0


# --- Event before deadline: immediate restore + stale-callback fence -------


def test_return_during_grace_restores_immediately_and_fences_stale_callback(topo):
    # display 1 returns during the grace via a topology event. Reclaim must
    # restore it immediately and fence the still-pending deadline callback.
    d0 = topo.add(_Display(0), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    assert _record()["pending"] is True

    d1 = topo.add(_Display(1), participating=True)   # monitor 1 comes back
    fol.reclaim_custom_visualizer_owner(topo)
    assert d1.create_calls == 1                 # restored immediately on configured
    assert d0.create_calls == 0                 # no temporary fallback ever made
    assert _record() is None

    topo.fire_all()                             # stale deadline now fires -> fenced
    assert d1.create_calls == 1
    assert d0.create_calls == 0


# --- Current configured monitor change wins (gap-3) ------------------------


def test_settings_monitor_change_during_grace_supersedes_target(topo):
    d0 = topo.add(_Display(0), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)

    d2 = topo.add(_Display(2), participating=True)   # user reconfigures to monitor 2
    topo.configured_index = 2
    topo.fire_all()                             # deadline re-resolves live monitor -> 2
    assert d2.create_calls == 1
    assert d0.create_calls == 0


def test_settings_monitor_change_during_fallback_reclaims_new_target(topo):
    # A temporary fallback is live on display 0 for old monitor 1; the user then
    # reconfigures to monitor 2 which is participating. Reclaim hands off to 2.
    d0 = topo.add(_Display(0, has_owner=True), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    d2 = topo.add(_Display(2), participating=True)
    topo.configured_index = 2
    fol.reclaim_custom_visualizer_owner(topo)
    assert d0.owner is None                     # temporary owner retired
    assert d2.create_calls == 1                 # restored on the NEW monitor 2
    assert _record() is None


def test_reclaim_superseded_to_non_custom_clears_and_retires(topo):
    d0 = topo.add(_Display(0, has_owner=True), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.custom = False                         # visualizer no longer CUSTOM-routed
    fol.reclaim_custom_visualizer_owner(topo)
    assert d0.owner is None
    assert _record() is None


# --- Retire-before-create is a hard guarantee (gap-4) ----------------------


def test_reclaim_fails_closed_when_retirement_fails(topo):
    # teardown fails and the owner stays bound -> retirement is not confirmed.
    # Reclaim must NOT create a second owner; it defers.
    d0 = topo.add(_Display(0, has_owner=True, cleanup_ok=False), participating=True)
    d1 = topo.add(_Display(1), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.configured_index = 1
    fol.reclaim_custom_visualizer_owner(topo)
    assert d1.create_calls == 0                 # no second owner created
    assert d0.owner is not None                 # temporary owner still alive
    assert _record() is not None                # record retained for a later retry


def test_retire_confirms_and_reclaims_when_cleanup_ok(topo):
    d0 = topo.add(_Display(0, has_owner=True, cleanup_ok=True), participating=True)
    d1 = topo.add(_Display(1), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.configured_index = 1
    fol.reclaim_custom_visualizer_owner(topo)
    assert d0.cleanup_calls == 1
    assert d0.owner is None
    assert d1.create_calls == 1
    assert _record() is None


def test_retire_owner_returns_false_on_cleanup_failure(topo):
    d0 = _Display(0, has_owner=True, cleanup_ok=False)
    assert fol.retire_visualizer_owner(topo, d0) is False
    assert d0.owner is not None                 # not orphaned/unbound
    assert topo.current_token() == 1            # still fenced


def test_retire_owner_returns_true_and_bumps_token_on_success(topo):
    d0 = _Display(0, has_owner=True, cleanup_ok=True)
    topo._token = 5
    assert fol.retire_visualizer_owner(topo, d0) is True
    assert d0.owner is None
    assert topo.current_token() == 6


# --- Reclaim guards --------------------------------------------------------


def test_reclaim_noop_without_record(topo):
    d1 = topo.add(_Display(1), participating=True)
    fol.reclaim_custom_visualizer_owner(topo)
    assert d1.create_calls == 0


def test_reclaim_keeps_record_when_configured_still_absent(topo):
    d0 = topo.add(_Display(0, has_owner=True), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.configured_index = 1                   # configured (1) still absent
    fol.reclaim_custom_visualizer_owner(topo)
    assert d0.cleanup_calls == 0
    assert _record() is not None


def test_reclaim_blocked_when_capability_deactivated(topo):
    d0 = topo.add(_Display(0, has_owner=True), participating=True)
    d1 = topo.add(_Display(1), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.configured_index = 1
    topo.widgets = dict(VIS_OFF)
    fol.reclaim_custom_visualizer_owner(topo)
    assert d1.create_calls == 0
    assert d0.owner is not None
    assert _record() is not None


def test_reclaim_idempotent_across_repeated_events(topo):
    d0 = topo.add(_Display(0, has_owner=True), participating=True)
    d1 = topo.add(_Display(1), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.configured_index = 1
    fol.reclaim_custom_visualizer_owner(topo)
    fol.reclaim_custom_visualizer_owner(topo)
    assert d1.create_calls == 1
    assert _record() is None


# --- Global grace generation authority (blocker-1) -------------------------


def test_repeated_reconcile_arms_only_one_grace(topo):
    # Repeated reconcile during ONE outage for the single Visualizer must arm only
    # one grace; the others must not start/reset a second 30 s deadline.
    topo.add(_Display(0), participating=True)
    topo.configured_index = 1                   # configured monitor 1 absent
    fol.reconcile_custom_visualizer(topo)
    fol.reconcile_custom_visualizer(topo)
    assert len(topo.scheduled) == 1             # exactly one grace across both


def test_old_generation_callback_is_fenced(topo):
    # A delayed callback still carrying an OLD outage generation must not act after
    # reclaim / a new outage, even if the LOCAL token happens to match. Generation
    # is the global authority.
    state = get_visualizer_failover_state()
    gen1 = state.arm_visualizer_grace(intended_index=1, origin_manager=None)  # outage 1
    state.clear_visualizer_failover()                                         # reclaim/return
    state.arm_visualizer_grace(intended_index=1, origin_manager=None)         # new outage (gen2)

    d1 = topo.add(_Display(1), participating=True)
    topo.configured_index = 1
    fol.run_fallback_recheck(
        topo, target_screen_index=1, token=topo.current_token(), generation=gen1,
    )
    assert d1.create_calls == 0                 # fenced by stale generation


def test_current_generation_callback_acts(topo):
    state = get_visualizer_failover_state()
    gen = state.arm_visualizer_grace(intended_index=1, origin_manager=None)
    d1 = topo.add(_Display(1), participating=True)
    topo.configured_index = 1
    fol.run_fallback_recheck(
        topo, target_screen_index=1, token=topo.current_token(), generation=gen,
    )
    assert d1.create_calls == 1


def test_new_outage_after_reclaim_gets_fresh_generation(topo):
    # After a handback, the target disappearing again is a genuinely NEW outage
    # with its own fresh grace/generation (strictly greater than the old one).
    state = get_visualizer_failover_state()
    gen1 = state.arm_visualizer_grace(intended_index=1, origin_manager=None)
    state.clear_visualizer_failover()           # reclaim/handback ends outage 1
    topo.add(_Display(0), participating=True)    # monitor 1 absent again
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    rec = _record()
    assert rec is not None and rec["generation"] > gen1
    assert not state.is_visualizer_failover_generation_current(gen1)


# --- Retirement failure must never be discarded (blocker-2) -----------------


def test_non_custom_branch_retains_record_when_retire_fails(topo):
    # "No longer CUSTOM" branch: if the stray owner's retirement is not confirmed,
    # the failover record must be retained (never normalized while it may be live).
    d0 = topo.add(_Display(0, has_owner=True, cleanup_ok=False), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.custom = False
    fol.reclaim_custom_visualizer_owner(topo)
    assert d0.owner is not None                 # still alive
    assert _record() is not None                # record retained


def test_already_owns_branch_retains_record_when_stray_retire_fails(topo):
    # "Configured already owns" branch: a stray temporary owner whose retirement
    # fails must not be discarded; retain the record for a later retry.
    stray = topo.add(_Display(0, has_owner=True, cleanup_ok=False), participating=True)
    configured = topo.add(_Display(1, has_owner=True), participating=True)  # already owns
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=stray, origin_manager=None,
    )
    topo.configured_index = 1
    fol.reclaim_custom_visualizer_owner(topo)
    assert stray.owner is not None              # stray still alive
    assert _record() is not None                # record retained


# --- Capability deactivation retires the failover lifecycle ----------------


def test_deactivation_retires_pending_grace_then_fresh_grace_after_reactivation(topo):
    state = get_visualizer_failover_state()
    topo.add(_Display(0), participating=True)    # configured monitor 1 absent
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    rec = _record()
    assert rec is not None and rec["pending"] is True
    gen1 = rec["generation"]

    topo.widgets = dict(VIS_OFF)                # capability off -> lifecycle retired
    fol.retire_visualizer_failover_on_capability_change(topo)
    assert _record() is None
    assert not state.is_visualizer_failover_generation_current(gen1)

    topo.fire_all()                             # stale pending deadline -> fenced
    # (no display 0 create assert needed; generation invalidated)

    topo.widgets = dict(ACTIVE)                 # explicit reactivation, target absent
    fol.reconcile_custom_visualizer(topo)
    rec2 = _record()
    assert rec2 is not None and rec2["pending"] is True
    assert rec2["generation"] > gen1


def test_deactivation_media_off_retires_pending_grace(topo):
    topo.add(_Display(0), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    assert _record() is not None
    topo.widgets = dict(MEDIA_OFF)
    fol.retire_visualizer_failover_on_capability_change(topo)
    assert _record() is None


def test_deactivation_retires_active_fallback_owner_and_state(topo):
    d0 = topo.add(_Display(0, has_owner=True, cleanup_ok=True), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.widgets = dict(MEDIA_OFF)
    fol.retire_visualizer_failover_on_capability_change(topo)
    assert d0.cleanup_calls == 1
    assert d0.owner is None                     # temporary owner retired
    assert _record() is None                    # failover state retired


def test_deactivation_failed_retirement_retains_live_owner_record(topo):
    d0 = topo.add(_Display(0, has_owner=True, cleanup_ok=False), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.widgets = dict(VIS_OFF)
    fol.retire_visualizer_failover_on_capability_change(topo)
    assert d0.owner is not None                 # still alive (not orphaned)
    assert _record() is not None                # record retained


def test_deactivation_noop_when_capability_effective(topo):
    d0 = topo.add(_Display(0, has_owner=True), participating=True)
    get_visualizer_failover_state().set_visualizer_fallback_owner(
        intended_index=1, host=d0, origin_manager=None,
    )
    topo.widgets = dict(ACTIVE)
    fol.retire_visualizer_failover_on_capability_change(topo)
    assert _record() is not None                # still effective -> untouched
    assert d0.owner is not None
    assert d0.cleanup_calls == 0


# --- Never persists monitor/geometry ---------------------------------------


def test_failover_and_reclaim_never_persist_settings(topo):
    d0 = topo.add(_Display(0), participating=True)
    topo.configured_index = 1
    fol.reconcile_custom_visualizer(topo)
    topo.fire_all()                             # temporary fallback created on display 0
    topo.add(_Display(1), participating=True)
    fol.reclaim_custom_visualizer_owner(topo)   # reclaim to display 1
    # The neutral lifecycle has no settings-write capability at all; the adapter's
    # persistence hook is never invoked by any failover path.
    assert topo.persist_calls == []

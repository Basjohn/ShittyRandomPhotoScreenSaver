"""Presentation-neutral Visualizer CUSTOM failover/reclaim lifecycle (E2.7).

Policy layer over the process-scoped failover state
(``rendering/quick/visualizer_failover.py``). It owns the durable contract and
drives an injected ``topology`` adapter that supplies the mechanism — resolving
the configured CUSTOM route from live canonical Settings, resolving which Quick
display participates, and creating/retiring the SINGLE Quick visualizer owner.
It constructs and retires nothing itself, so it is free of any QWidget /
DisplayWidget / physical-host coupling and free of any second presenter.

Durable contract preserved (audit ``Docs/QtQuick_Migration/
07_Settings_Capability_Activation.md`` §"Visualizer CUSTOM failover/reclaim"):

- configured CUSTOM target unavailable -> ONE global outage generation;
- full 30 s one-shot grace (never a poll), not an immediate fallback;
- target returns during grace -> immediate restore, no fallback;
- still unavailable after grace -> AT MOST one temporary fallback owner;
- configured target returns later -> retire/fence the temporary owner BEFORE
  reclaim (retire-confirmed create is a hard guarantee);
- repeated topology events are idempotent;
- a new outage after successful reclaim gets a fresh grace generation;
- capability OFF invalidates the pending grace and retires the temporary owner;
- a failed retirement preserves the truthful recoverable ownership record.

The topology adapter (duck-typed) must provide:

    capability_admitted() -> bool            # live, FAIL CLOSED
    live_widgets() -> dict | None            # current canonical widgets config
    is_custom_selected(widgets) -> bool
    effective_monitor_index(widgets) -> int | None   # 0-based, None if unresolved
    resolve(intended_index) -> Resolution    # .requested_display,
                                             # .requested_is_participating,
                                             # .fallback_display
    owner_present_on(display) -> bool
    screen_index_of(display) -> int | None
    create_owner(display, intended_index) -> bool   # mechanical create/reuse
    cleanup_owner(display) -> bool           # mechanical teardown; True == torn down
    detach_owner(display) -> None            # drop the owner reference after teardown
    current_token() -> int
    bump_token() -> int                      # fence pending deadlines after a retire
    schedule(delay_ms, *, target_screen_index, token, generation) -> None

Retirement confirmation policy (token fence + fail-closed) is owned HERE by
``retire_visualizer_owner`` rather than the adapter, so the durable contract is
provable neutrally.
"""

from __future__ import annotations

from typing import Optional

from core.logging.logger import get_logger

from rendering.quick.visualizer_failover import get_visualizer_failover_state

logger = get_logger(__name__)

# One-shot grace before a configured CUSTOM monitor that is momentarily
# unavailable is allowed a temporary fallback owner. Event-driven reclaim (see
# reclaim_custom_visualizer_owner) returns ownership to the configured monitor
# whenever it comes back, even long after this grace has elapsed. A single
# token/generation-fenced deadline, NEVER a recurring poll.
VISUALIZER_FALLBACK_GRACE_MS = 30000


def create_visualizer_owner_on_target(
    topology,
    target,
    intended_index: int,
    *,
    origin: object = None,
) -> bool:
    """Create/reuse the single visualizer owner on ``target``; return success.

    Single creation boundary for the immediate reconcile, the delayed fallback
    recheck, and reclaim. Re-reads CURRENT canonical capability here so a
    stale/delayed callback can never create a Visualizer after Media or
    Visualizers was deactivated (FAILS CLOSED). Records/clears the failover state:
    a host that is NOT the configured monitor is a temporary fallback (recorded);
    the configured monitor owning the visualizer clears the record (outage over).
    """
    if target is None:
        return False
    if topology.owner_present_on(target):
        return False
    # Final capability admission: re-read CURRENT canonical capability state so a
    # stale/delayed callback scheduled while active cannot create after
    # deactivation. Fails closed.
    if not topology.capability_admitted():
        logger.debug(
            "[VIS_FAILOVER] create skipped: visualizer capability no longer admitted"
        )
        return False
    if not topology.create_owner(target, intended_index):
        return False
    state = get_visualizer_failover_state()
    try:
        host_index = topology.screen_index_of(target)
        if host_index is not None and int(host_index) != int(intended_index):
            state.set_visualizer_fallback_owner(
                intended_index=intended_index,
                host=target,
                origin_manager=origin,
            )
        else:
            # Configured monitor now owns the visualizer -> outage over; clearing
            # invalidates the failover generation, retiring any old grace callback.
            state.clear_visualizer_failover()
    except Exception:
        logger.debug("[VIS_FAILOVER] failed to update failover record", exc_info=True)
    return True


def retire_visualizer_owner(topology, host) -> bool:
    """Retire a temporary fallback owner on ``host``; return True only if confirmed.

    Fences any pending delayed fallback work (token bump) so a stale callback
    cannot resurrect the retired owner, then tears the owner down. Honours the
    teardown's explicit success/failure: if teardown of a live owner fails, DO
    NOT drop the reference (that would orphan a live owner and mask the failure) —
    fail closed so reclaim does not create a second owner. Best-effort and
    idempotent.
    """
    if host is None:
        return True
    # Fence any pending delayed fallback work owned by the orchestrator so a stale
    # callback cannot resurrect the retired fallback owner.
    try:
        topology.bump_token()
    except Exception:
        logger.debug("[VIS_FAILOVER] failed to bump fence token during retire", exc_info=True)
    if not topology.owner_present_on(host):
        return True
    try:
        torn_down = bool(topology.cleanup_owner(host))
    except Exception:
        logger.debug("[VIS_FAILOVER] failed to tear down temporary fallback owner", exc_info=True)
        torn_down = False
    if not torn_down:
        logger.warning(
            "[VIS_FAILOVER] temporary fallback owner teardown failed on screen_index=%s; "
            "retirement NOT confirmed (failing closed)",
            topology.screen_index_of(host),
        )
        return False
    try:
        topology.detach_owner(host)
    except Exception:
        logger.debug("[VIS_FAILOVER] failed to detach temporary fallback owner", exc_info=True)
    confirmed = not topology.owner_present_on(host)
    if not confirmed:
        logger.warning(
            "[VIS_FAILOVER] temporary fallback owner retirement NOT confirmed on screen_index=%s",
            topology.screen_index_of(host),
        )
    return confirmed


def schedule_fallback_recheck(
    topology,
    *,
    target_screen_index: int,
    origin: object = None,
) -> None:
    """Arm ONE global grace for the single Visualizer outage and schedule it.

    If a grace/fallback is already active (armed earlier during this same
    outage), arm returns None and we do NOT start or reset a second 30 s
    deadline. The returned generation is the global authority every delayed
    callback validates.
    """
    state = get_visualizer_failover_state()
    generation = state.arm_visualizer_grace(
        intended_index=target_screen_index,
        origin_manager=origin,
    )
    if generation is None:
        logger.debug(
            "[VIS_FAILOVER] grace already active for this outage; not arming another"
        )
        return
    token = topology.current_token()
    logger.warning(
        "[VIS_FAILOVER] Requested CUSTOM monitor %s not participating; arming "
        "%sms one-shot grace (gen=%s) before any temporary fallback",
        target_screen_index,
        VISUALIZER_FALLBACK_GRACE_MS,
        generation,
    )
    topology.schedule(
        VISUALIZER_FALLBACK_GRACE_MS,
        target_screen_index=target_screen_index,
        token=token,
        generation=generation,
    )


def reconcile_custom_visualizer(topology) -> None:
    """Admit the single CUSTOM visualizer, or arm ONE grace if its target is absent.

    Immediate create when the configured CUSTOM display is participating now;
    otherwise arm the SAME 30 s one-shot grace whether the target is
    runtime-known-but-not-participating or completely absent (startup/wake). No
    immediate fallback — a temporary owner is only created at the deadline if it
    is still unavailable, and an event-driven reclaim restores it sooner.
    """
    if not topology.capability_admitted():
        return
    widgets = topology.live_widgets()
    if not isinstance(widgets, dict):
        return
    if not topology.is_custom_selected(widgets):
        return
    target_index = topology.effective_monitor_index(widgets)
    if target_index is None:
        return
    resolution = topology.resolve(target_index)
    if resolution.requested_is_participating and resolution.requested_display is not None:
        create_visualizer_owner_on_target(
            topology, resolution.requested_display, target_index, origin=topology
        )
        return
    schedule_fallback_recheck(topology, target_screen_index=target_index, origin=topology)


def run_fallback_recheck(
    topology,
    *,
    target_screen_index: int,
    token: int,
    generation: int,
) -> None:
    """Grace-deadline body: create at most one temporary fallback if still absent.

    Global authority: valid only while ``generation`` is the currently-active
    outage generation. Reclaim, a target return, or a new outage all invalidate
    the old generation, so a straggler aborts here regardless of its local token.
    """
    state = get_visualizer_failover_state()
    if not state.is_visualizer_failover_generation_current(generation):
        return
    if token != topology.current_token():
        return  # secondary fence: local token superseded by a retire
    if not topology.capability_admitted():
        logger.debug(
            "[VIS_FAILOVER] delayed recheck skipped: capability no longer admitted"
        )
        return
    # gap-3: re-resolve the CURRENT canonical CUSTOM monitor/config from live
    # Settings rather than trusting the copy captured when the grace was armed, so
    # a Settings change during the grace supersedes the old pending target.
    widgets = topology.live_widgets()
    if not isinstance(widgets, dict):
        return
    if not topology.is_custom_selected(widgets):
        # Visualizer no longer CUSTOM-routed -> pending grace superseded.
        state.clear_visualizer_failover()
        return
    current_index = topology.effective_monitor_index(widgets)
    if current_index is None:
        return
    state.update_visualizer_failover_intended(current_index)

    resolution = topology.resolve(current_index)
    requested_display = resolution.requested_display
    if requested_display is not None and topology.owner_present_on(requested_display):
        return
    if resolution.requested_is_participating and requested_display is not None:
        target = requested_display
    else:
        target = resolution.fallback_display
        if target is None:
            # No participating display at the deadline -> fail closed; do not
            # invent one. Leave the pending grace so a later topology event can
            # still reclaim without any polling timer.
            logger.info(
                "[VIS_FAILOVER] deadline for CUSTOM monitor %s: no participating "
                "display; failing closed (grace retained for event-driven reclaim)",
                current_index,
            )
            return
        logger.warning(
            "[VIS_FAILOVER] CUSTOM monitor %s still not participating after %sms; "
            "creating temporary fallback on participating display screen_index=%s",
            current_index,
            VISUALIZER_FALLBACK_GRACE_MS,
            topology.screen_index_of(target),
        )
    create_visualizer_owner_on_target(topology, target, current_index, origin=topology)


def reclaim_custom_visualizer_owner(topology) -> None:
    """Event-driven reclaim of the configured CUSTOM visualizer display (E2.7).

    Invoked from the existing display/topology event machinery (a monitor
    returning triggers a Quick rebuild whose admission reclaims), never a
    recurring poll. Handles BOTH a pending grace (no temporary owner yet) and a
    live temporary fallback: when the CURRENT configured CUSTOM display
    (re-resolved from live Settings) is participating again, hand ownership back
    to it as one reconciliation transaction.

    - Idempotent: no failover record -> no-op; safe under repeated events.
    - Pending grace visible: a target returning before the deadline is restored
      immediately and the stale pending callback is fenced by the retire token /
      cleared generation.
    - Current config wins (gap-3): the configured monitor is re-resolved live.
    - Retire-confirmed create (gap-4): the configured owner is created only after
      the temporary owner's retirement is confirmed; otherwise it defers.
    """
    state = get_visualizer_failover_state()
    record = state.get_visualizer_failover()
    if record is None:
        return  # no pending grace or fallback -> nothing to reclaim (idempotent)

    host = record["host"]

    if not topology.capability_admitted():
        # Capability deactivated: a topology event must not recreate/reclaim.
        logger.debug("[VIS_FAILOVER][RECLAIM] capability not admitted; not reclaiming")
        return

    widgets = topology.live_widgets()
    if not isinstance(widgets, dict):
        return

    # gap-3: re-resolve the CURRENT configured CUSTOM monitor from live Settings.
    if not topology.is_custom_selected(widgets):
        # No longer CUSTOM-routed -> failover superseded. Retire any stray owner
        # first; only declare normalized if retirement is CONFIRMED (blocker-2).
        if host is not None and not retire_visualizer_owner(topology, host):
            logger.warning(
                "[VIS_FAILOVER][RECLAIM] not clearing failover: stray owner "
                "retirement unconfirmed (no-longer-CUSTOM branch)"
            )
            return
        state.clear_visualizer_failover()
        return
    current_index = topology.effective_monitor_index(widgets)
    if current_index is None:
        return
    state.update_visualizer_failover_intended(current_index)

    resolution = topology.resolve(current_index)
    configured = resolution.requested_display
    if configured is None or not resolution.requested_is_participating:
        return  # configured display still not back -> keep the grace/fallback

    if topology.owner_present_on(configured):
        # Configured display already owns the visualizer; retire any stray
        # temporary owner and normalize the record. Only clear if the stray
        # owner's retirement is CONFIRMED (blocker-2).
        if host is not None and host is not configured:
            if not retire_visualizer_owner(topology, host):
                logger.warning(
                    "[VIS_FAILOVER][RECLAIM] not clearing failover: stray owner "
                    "retirement unconfirmed (configured-already-owns branch)"
                )
                return
        state.clear_visualizer_failover()
        return

    # gap-4: only create the configured owner once the temporary owner's
    # retirement is CONFIRMED; otherwise defer (never two live owners).
    if host is not None and host is not configured:
        if not retire_visualizer_owner(topology, host):
            logger.warning(
                "[VIS_FAILOVER][RECLAIM] deferring reclaim: temporary owner not retired"
            )
            return

    logger.info(
        "[VIS_FAILOVER][RECLAIM] CUSTOM monitor %s available; restoring visualizer to it",
        current_index,
    )
    # A successful create on the configured display clears the failover, which
    # invalidates the whole outage generation -> any still-pending delayed
    # callback aborts its generation check.
    created = create_visualizer_owner_on_target(
        topology, configured, current_index, origin=None
    )
    if not created:
        # Creation failed (e.g. capability dropped mid-transaction). The temporary
        # owner is already retired, so leave a PENDING grace (never a dangling
        # fallback host), preserving the generation so a later event can retry.
        state.repend_visualizer_failover(
            intended_index=current_index,
            origin_manager=None,
        )


def retire_visualizer_failover_on_capability_change(topology) -> None:
    """Retire the GLOBAL Visualizer failover lifecycle when capability is off.

    Canonical capability-deactivation reaction (E2.7): when Media or Visualizers
    becomes ineffective, an in-flight failover (pending grace or live temporary
    fallback) must be RETIRED — not merely blocked from creating — so it cannot
    stay stuck:

    - capability still effective -> no-op (this only retires on deactivation);
    - a live temporary fallback owner is retired, and its record is discarded only
      when retirement is CONFIRMED (a failed retirement retains the record so a
      later event retries — never lose a live-owner record);
    - a pending grace (no owner) has its record + global generation invalidated,
      so stale delayed callbacks from the retired generation remain fenced;
    - a later explicit reactivation therefore arms a genuinely fresh generation
      and a full new 30 s grace.
    """
    state = get_visualizer_failover_state()
    record = state.get_visualizer_failover()
    if record is None:
        return  # no in-flight failover -> nothing to retire (idempotent)
    if topology.capability_admitted():
        return  # still effective -> not a deactivation; leave the failover intact
    host = record.get("host")
    if host is not None:
        # Live temporary fallback owner: retire it and only discard the record
        # when retirement is CONFIRMED (never lose a live-owner record).
        if not retire_visualizer_owner(topology, host):
            logger.warning(
                "[VIS_FAILOVER][DEACTIVATE] not clearing failover: temporary owner "
                "retirement unconfirmed; retaining record for retry"
            )
            return
    state.clear_visualizer_failover()
    logger.info(
        "[VIS_FAILOVER][DEACTIVATE] visualizer failover lifecycle retired "
        "(capability off); generation invalidated"
    )


__all__ = [
    "VISUALIZER_FALLBACK_GRACE_MS",
    "create_visualizer_owner_on_target",
    "schedule_fallback_recheck",
    "reconcile_custom_visualizer",
    "run_fallback_recheck",
    "reclaim_custom_visualizer_owner",
    "retire_visualizer_failover_on_capability_change",
]

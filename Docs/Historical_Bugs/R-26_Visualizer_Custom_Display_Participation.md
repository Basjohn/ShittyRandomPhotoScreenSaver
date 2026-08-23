# R-26 — 2026-06-18 — Visualizer CUSTOM Display-Participation Fallback / Duplicate Owner From Startup And Sleep-Wake Participation Churn (Partial / Awaiting Validation)

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Current status — 2026-08-23

**Implementation is independently audited GREEN. Physical dual-display acceptance remains outstanding.**

The E2.7 implementation was independently audited GREEN at:

```text
5b3cbaef4d443c79941e5ac780252f82a4e77bc4
```

Therefore this incident is no longer an active implementation blocker and `Current_Plan.md` must not
send an agent back to “finish E2.7” without new contradictory source/runtime evidence.

It remains `PARTIAL / AWAITING VALIDATION` because the full human hardware sequence has not yet been
independently demonstrated on the operator's physical dual-display system, especially monitor
sleep/wake/late-return timing that `--s` and unit tests cannot reproduce.

### Final landed E2.7 contract

The configured CUSTOM monitor is always canonical. A fallback host is temporary runtime state only.

```text
configured target unavailable
    -> one GLOBAL Visualizer outage generation
    -> full 30-second one-shot grace

returns during grace
    -> no fallback
    -> configured target remains/gets owner

still unavailable at deadline
    -> at most one temporary participating fallback
    -> no persisted monitor/position/size/viewport rewrite

configured target returns later
    -> event-driven reclaim
    -> retire/fence fallback first
    -> only after confirmed retirement restore configured owner
    -> restore configured target's saved CUSTOM geometry
```

Key audited invariants:

- the 30-second grace applies whether the configured target is runtime-known/non-participating or
  completely absent;
- grace authority is global per the single Visualizer, not per `WidgetManager`;
- repeated reconcile from another display cannot restart/extend the same outage;
- delayed callbacks validate the coordinator/global generation, so old callbacks from another display
  cannot act after return/reclaim/new outage;
- a later new outage receives a fresh strictly-new generation and full 30-second grace;
- current live Settings are re-read at delayed fallback and reclaim boundaries;
- configured-monitor changes supersede captured/stale targets;
- retirement is retire-before-create and must be confirmed;
- failed retirement retains recoverable failover/live-owner state rather than declaring normalization;
- capability deactivation via Media OFF or Visualizers OFF retires pending failover state and invalidates
  its generation;
- a live fallback on capability deactivation is retired and its record is discarded only after
  confirmed retirement;
- failed fallback retirement on capability deactivation retains the live-owner record;
- later explicit reactivation with target still absent starts a fresh full 30-second grace;
- no recurring monitor polling timer is used;
- `screenAdded -> full topology rebuild` remains the authority for a physically absent display
  appearing.

### Remaining acceptance

On the physical dual-display installation, still validate as practical:

- configured target off/asleep at runtime/startup;
- target returns inside 30 seconds -> zero fallback creation;
- target remains unavailable through deadline -> one temporary fallback only;
- target returns after fallback, including much later -> configured target becomes sole owner;
- target disappears again after successful reclaim -> new full grace;
- repeated display churn does not create duplicate owners;
- persisted CUSTOM monitor/geometry remains unchanged by fallback;
- Media/Visualizers capability changes during grace/fallback remain correct in real runtime.

A physical failure reopens the **smallest demonstrated ownership/topology defect**, not E2/Phase E as a
whole.

## 2026-08-23 reopening/audit chronology

The June 2026 correction remained valid for the narrower failure it addressed: ordinary startup no
longer made CUSTOM owner selection from a partial registered display set, and a runtime-known display
that was still waking no longer caused an immediate duplicate-owner fallback.

The broader sleep/wake ownership contract was reopened during the Phase-E2 audit because the older
1500 ms recheck was not a useful human-scale grace and late configured-target reclaim had not been
proved.

The correction series then established:

1. **Human-scale grace + current-state reclaim.** Absent and runtime-known unavailable targets receive
   the same 30-second grace; pending grace became visible to reconciliation; delayed/reclaim paths
   re-read current Settings; retire-before-create became a hard success/failure boundary.
2. **Global outage authority.** One coordinator generation owns the singleton Visualizer outage; old
   callbacks from other managers are globally fenced; retirement failure is never discarded.
3. **Capability lifecycle closure.** Media/Visualizers deactivation retires the global failover
   lifecycle; reactivation can start a genuinely new 30-second outage; relevant stale E2/E2.7 tests
   were repaired to the landed contract rather than deferred as “pre-existing red.”

Independent audit of the third correction closed E2.7 implementation.

Do not erase the June chronology below: it records a real correction that remains part of the final
solution. Its former `SOLVED` classification was simply broader than the available evidence justified.

## Original 2026-06-18 resolved scope

- **Resolved state at the time:** ordinary multi-display startup no longer asks visualizer CUSTOM owner
  selection to decide from a partial display set, and runtime sleep/wake churn no longer immediately
  duplicates the visualizer onto another participating display just because the requested display is
  still waking. All allowed `DisplayWidget` instances are constructed and registered before the first
  display begins widget setup, and remote CUSTOM reconcile treats fallback as a delayed last-resort
  recheck when the requested display still exists in runtime but is temporarily non-participating.
- **Observed failure pattern:**
  - logs could emit `Requested CUSTOM monitor 1 is not participating` during ordinary startup even
    though the requested display would appear moments later;
  - screen 0 could then birth a fallback visualizer, and screen 1 would later create the real requested-
    display visualizer, recreating duplicate ownership;
  - real-world display sleep/wake could hit the same family: screen 0 wakes first, fallback appears
    while screen 1 is still waking, then screen 1 resumes with its own visualizer.
- **Root cause family:**
  1. The participation helper already knew how to defer to a live-but-not-ready requested display.
  2. `DisplayManager.initialize_displays()` still created and fully showed screen 0 before constructing
     screen 1.
  3. During screen 0 startup, the coordinator therefore contained only the first display, so the
     requested monitor looked truly absent and fallback fired against a partial world view.
  4. Later runtime reconcile still treated a runtime-known-but-temporarily-non-participating requested
     display as an immediate fallback case, which was too aggressive for monitor wake churn.
- **What worked in the June correction:**
  - changed `DisplayManager.initialize_displays()` into a two-phase startup:
    - instantiate/register every allowed `DisplayWidget`;
    - then show them with the existing stagger;
  - kept `rendering.spotify_display_participation` explicit about the difference between:
    - a truly absent requested display;
    - a runtime-known requested display that is not participating yet;
  - changed remote CUSTOM reconcile so the second case did not immediately fallback:
    - schedule a cautious delayed recheck through `ThreadManager.single_shot`;
    - if the requested display participates by then, let it keep ownership;
    - only if still unavailable, restore one visible owner on a participating display;
  - kept staggered show behavior so GL/compositor startup avoided simultaneous heavy work;
  - added focused regressions proving:
    - first `show_on_screen()` runs only after all allowed displays already exist;
    - remote reconcile delays fallback while a requested runtime display is temporarily unavailable;
    - delayed recheck falls back if the target stays unavailable.
- **Why it worked:**
  - it fixed the real ownership lies instead of silencing the warning;
  - it preserved loud fallback diagnostics while removing false-positive startup/wake cases;
  - it kept local spawn and remote reconcile on the same participating-display contract.
- **Takeaways:**
  - if owner selection depends on the active display set, construct/register that set before the first
    per-display startup path consumes it;
  - do not “fix” this family by silencing fallback warnings;
  - monitor-wake fallback is a self-heal seam, not a race-to-restore seam;
  - exactly-one-owner and persistence authority matter more than whichever display becomes ready first.

## Migration-epoch note

The June chronology names `DisplayWidget`, old compositor startup and other pre-cutover owners because
those were real/current implementation seams. They are **CURRENT-LEGACY — WILL BE OBSOLETE at H/I**.
The ownership lesson and the E2.7 singleton/failover contract survive the presenter migration.

## Record Provenance

This standalone file preserves the former inline `R-26` record from `Docs/Historical_Bugs.md` and the
2026-08-23 E2.7 audit chronology. Current implementation sequencing remains in `Current_Plan.md`.

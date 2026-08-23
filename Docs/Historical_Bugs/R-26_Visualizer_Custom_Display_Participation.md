# R-26 — 2026-06-18 — Visualizer CUSTOM Display-Participation Fallback / Duplicate Owner From Startup And Sleep-Wake Participation Churn (Partial / Reopened)

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

## 2026-08-23 reopening note

The June 2026 correction remains valid for the failure it actually addressed: ordinary startup no
longer makes CUSTOM owner selection from a partial registered display set, and a runtime-known display
that is still waking no longer causes an immediate duplicate-owner fallback.

The broader sleep/wake ownership contract is **not fully solved** and is now owned by
`Current_Plan.md` **E2.7 — Visualizer CUSTOM display failover/reclaim lifecycle**.

Current gaps identified during the Phase-E2 independent audit:

- the existing fallback recheck waits only 1500 ms, which is not a useful human-scale grace for a
  person turning on additional displays or for slower HDMI/DisplayPort wake/renegotiation;
- if the grace expires and a fallback Visualizer is created on another display, current source has no
  independently proven event-driven hand-back that returns ownership to the configured CUSTOM display
  when it becomes available later;
- a fallback display must be treated as **temporary runtime ownership only**. It must never overwrite
  the persisted configured monitor, the configured target's saved CUSTOM position/size/viewport, or
  make fallback/clamped geometry authoritative;
- the configured target remains canonical indefinitely. If it returns seconds, minutes or hours after
  fallback creation, display/topology events must reconcile the Visualizer back to it and retire/fence
  the temporary owner;
- E2.7 sets a 30-second one-shot grace and requires event-driven reclaim, exactly-one-owner fencing,
  current capability re-admission, and no recurring monitor polling timer.

Do not erase the June chronology below: it records a real correction that remains part of the final
solution. Its former `SOLVED` classification was simply broader than the evidence justified.

## Original 2026-06-18 resolved scope

- **Resolved state at the time:** ordinary multi-display startup no longer asks visualizer CUSTOM owner selection to decide from a partial display set, and runtime sleep/wake churn no longer immediately duplicates the visualizer onto another participating display just because the requested display is still waking. All allowed `DisplayWidget` instances are now constructed and registered before the first display begins widget setup, and remote CUSTOM reconcile now treats fallback as a delayed last-resort recheck when the requested display still exists in runtime but is temporarily non-participating.
- **Observed failure pattern:**
  - logs could emit `Requested CUSTOM monitor 1 is not participating` during an ordinary startup even though the requested display would appear moments later
  - screen 0 could then birth a fallback visualizer, and screen 1 would later create the real requested-display visualizer, recreating the duplicate-owner family in a newer form
  - real-world display sleep/wake could hit a second version of the same lie: screen 0 would wake first, remote reconcile would immediately fallback onto screen 0 while screen 1 was still waking, and screen 1 would then resume with its own visualizer so two owners stayed alive
- **Root cause family:**
  1. The participation helper itself already knew how to defer to a live-but-not-ready requested display.
  2. `DisplayManager.initialize_displays()` still created and fully showed screen 0 before constructing screen 1.
  3. During screen 0 startup, the coordinator therefore contained only the first display, so the requested monitor looked truly absent and the fallback path fired loudly but incorrectly.
  4. Later runtime reconcile still treated a runtime-known-but-temporarily-non-participating requested display as an immediate fallback case, which was too aggressive for ordinary monitor sleep/wake churn.
- **What finally worked:**
  - changed `DisplayManager.initialize_displays()` into a two-phase startup:
    - instantiate/register every allowed `DisplayWidget`
    - then show them with the existing stagger
  - kept `rendering.spotify_display_participation` explicit about the difference between:
    - a truly absent requested display
    - a runtime-known requested display that is not participating yet
  - changed remote CUSTOM reconcile so the second case does not immediately fallback:
    - schedule one cautious delayed recheck through `ThreadManager.single_shot`
    - if the requested display is participating by then, let it keep ownership
    - only if it is still unavailable after the recheck, log the fallback loudly and restore one visible owner on a participating display
  - kept the staggered show behavior so GL/compositor startup still avoids simultaneous heavy work
  - added focused regression bars proving:
    - the first `show_on_screen()` runs only after all allowed displays already exist
    - remote reconcile delays fallback while a requested runtime display is temporarily unavailable
    - the delayed recheck still falls back if the target stays unavailable
- **Why this worked:**
  - it fixed the real ownership lies instead of weakening the participation helper or silently muting fallbacks
  - it preserved the loud fallback for truly absent or still-missing monitors while removing the false-positive startup and sleep/wake cases
  - it keeps local spawn and remote reconcile on the same participating-display contract
- **Takeaways:**
  - if owner selection depends on the active display set, construct/register that set before the first per-display startup path consumes it
  - do not “fix” this family by silencing the fallback warning; the warning was accurate about the code's partial world view, not noisy by itself
  - for sleep/wake churn, fallback is a self-heal seam, not a race-to-restore seam; a cautious grace is safer than birthing a second owner while the requested display is still returning

## Record Provenance

This standalone file preserves the former inline `R-26` record from `Docs/Historical_Bugs.md`. The
2026-08-23 note reclassifies the current state based on later audit evidence while retaining the June
root-cause chronology and correction.

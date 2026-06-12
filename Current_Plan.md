# Current Plan

Last updated: 2026-06-12

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

The current top-priority blocker is CUSTOM geometry / edit-mode parity. `audits/GeoAudit/` is the working map for that task.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `audits/GeoAudit/`.
- Prune validated work aggressively. This is not a changelog.
- Keep harnesses/probes that materially improve diagnosis quality.
- Use relevant CLI families for new logging. Geometry logging belongs behind `--geo`.
- Prefer automation bars over repeated runtime-verification asks.
- Do not close visual/runtime bugs from polite unit doubles alone.
- Treat `presets/visualizer_modes/` as authored content; validate schema/index/repair behavior without forcing creative payload values.
- CUSTOM widgets are outside authored stacking for that runtime/layout pass.
- Gmail/Reddit may adjust height for visible count/cache/dead-space QoL, but no widget gets width authority from that path.

## Active References

- [`audits/GeoAudit/00_README_INDEX.md`](audits/GeoAudit/00_README_INDEX.md)
- [`audits/GeoAudit/01_Problem_Model_And_Invariants.md`](audits/GeoAudit/01_Problem_Model_And_Invariants.md)
- [`audits/GeoAudit/02_Edit_Mode_Trace.md`](audits/GeoAudit/02_Edit_Mode_Trace.md)
- [`audits/GeoAudit/03_Save_And_Runtime_Replay_Trace.md`](audits/GeoAudit/03_Save_And_Runtime_Replay_Trace.md)
- [`audits/GeoAudit/04_Widget_Scaling_And_Content_Loss_Audit.md`](audits/GeoAudit/04_Widget_Scaling_And_Content_Loss_Audit.md)
- [`audits/GeoAudit/05_Diagnostics_Instrumentation_And_Fix_Order.md`](audits/GeoAudit/05_Diagnostics_Instrumentation_And_Fix_Order.md)
- [`audits/GeoAudit/06_Codex_Execution_Prompt.md`](audits/GeoAudit/06_Codex_Execution_Prompt.md)

## Active Tasks

### 1. Re-close CUSTOM geometry / edit parity / shrink behavior

- [ ] Keep the problem statement anchored to the real geometry contract:
  - saving edit mode writes one authoritative CUSTOM snapshot for every editable widget in the scene
  - every saved widget is promoted to `Custom`
  - width is locked by the committed CUSTOM rect
  - Gmail/Reddit may change height only for visible-count/cache/dead-space QoL
  - edit resize remains uniform, top-center anchored, and non-freeform
  - min scale is `0.5`; max is bounded by the relevant display edge
  - authored/default placement and CUSTOM placement stay isolated after edit entry
  - text/icons/padding must not clip inside the committed card

- [ ] Re-audit Reddit/Gmail height behavior through the `4.0 .. HEAD` history before changing those runtime seams again.
  - Preserve the useful old behavior:
    - Reddit may start at the currently available cached/post count and grow vertically toward the configured visible count
    - Gmail may still clean up/neaten height from the visible row state
  - Do not restore width growth as part of that recovery.

- [ ] Keep two edit-shell concepts explicit where needed:
  - primary shell = authoritative saved rect
  - QoL envelope = unsaved preview of max vertical growth for the current configured visible count
  - the envelope is informational only and must not become saved geometry truth
  - Gmail/Reddit resize preview must stay live-content driven rather than a stretched cached snapshot

- [ ] Use the new `--geo` scene/replay probes to find the first Reddit/Gmail divergence before changing widget-local growth rules again.
  - `save_scene` must stay whole-scene and authoritative.
  - `replay_start` / `replay_after_payload` / `replay_after_update_position` / `replay_final` are now the required divergence checkpoints.
  - If `spotify_visualizer` reopens in edit mode again, treat committed-rect-vs-shell-envelope authority as the first suspect before reopening generic runtime replay theory.

- [ ] Replace any compounding resize model with a stable authored/reference baseline.
  - Re-entering edit after shrink must not lower future control range.
  - Use the current top-center / `0.5` / display-edge bars to prove or disprove edit-entry rebasing instead of reworking the live resize math again.
  - Keep resize growth able to push back into still-valid on-screen territory instead of stalling as soon as the current anchor nears an edge.
  - Corner-drag resize must not jump on first movement when the pointer begins inside the resize gutter.

- [ ] Re-close runtime replay parity.
  - saved authoritative rect == replayed rect
  - no authored stacking may touch CUSTOM widgets
  - no widget-local startup or refresh path may widen/narrow/move a committed CUSTOM widget
  - if Gmail/Reddit grow after replay, prove that the change is height-only and count-authorized

- [ ] Keep the current diagnosis table grounded in the actual post-revert tree before new geometry edits land.
  - `gmail`: failure layer currently inner content fit; latest logs keep `save_scene == replay_final`
  - `reddit` / `reddit2`: failure layer currently inner content fit plus blocked-fetch survivability; latest logs keep `save_scene == replay_final`
  - `spotify_visualizer`: outer replay, live-overlay rect, GPU rect authority, and edit-shell re-entry bars are green; only reopen shell/replay authority if fresh `--geo` logs contradict the committed-width + vertical-only-envelope contract

- [ ] Close the known runtime drift still visible in current `--geo` evidence.
  - Visualizer:
    - keep the now-green runtime outer replay locked: fresh `--geo` runs must keep `replay_after_payload` / `replay_after_update_position` / `replay_final` equal to the committed CUSTOM rect
    - keep edit-shell re-entry locked after save/swap/re-enter churn:
      - committed CUSTOM width remains authoritative
      - QoL envelope may grow height only
      - stale live geometry or anchor-media width drift must not narrow the shell
    - keep overlay/GPU rect authority locked during recreate/monitor churn:
      - prewarm and live overlay pushes must prefer the committed CUSTOM rect over stale square live geometry
      - GPU geometry-change detection must compare against the same authoritative rect, not raw `widget.geometry()` alone
    - if a future live screenshot still contradicts the rect logs and the re-entry bar stays green, route the next pass to card/overlay content fit or monitor-transfer state rather than reopening replay authority blindly
  - Spotify Volume:
    - keep outer CUSTOM replay green
    - keep pre-replay authored placement from leaking into first reveal
    - keep shrink payload slightly more aggressive for smaller media cards
    - keep secondary-stage reveal reliable when the anchor becomes visible late

- [ ] Treat Gmail/Reddit outer replay as currently proven and focus the next pass on their allowed vertical-only QoL seams.
  - Re-audit `4.0 .. HEAD` height-management history before changing those runtime seams again.
  - Reddit:
    - align staged growth / cache fill / `_effective_visible_capacity`
    - allow height growth toward configured visible count
    - keep width fixed
  - Gmail:
    - preserve height cleanup/neatening from visible rows
    - keep width fixed

- [ ] Re-close content-fit for the known shrink failures.
  - Weather must not lose location letters.
  - Weather condition icon must stay visually centered with the primary text block under shrink.
  - Gmail must not lose subject letters.
  - Reddit must not lose title/body letters.
  - SpotifyVolume live edit distortion must be isolated cleanly.
  - Spotify visualizer rect must remain locked by the committed CUSTOM replay even when preset height logic varies.
  - Spotify visualizer live GL overlay/prewarm must prefer the committed CUSTOM rect over stale square live geometry.

- [ ] Add/strengthen automation bars before calling the geometry family closed.
  - corner-drag cleanup bar: resize state must clear cleanly on pointer ungrab/release
  - no-width-growth Gmail/Reddit bar
  - allowed-height-only Gmail/Reddit growth bar
  - Gmail shrink-budget bar: smaller resize/font payloads must shrink action/time utility lanes and increase subject budget, not reduce it
  - Reddit shrink-budget bar: smaller resize/font payloads must compact the age lane and increase title budget, not reduce it
  - no-compounding edit baseline bar
  - committed-card no-clipping bars for the remaining shrink-risk widgets
  - visualizer monitor-churn bar: save/swap/re-enter must preserve committed width while allowing height-only QoL shell growth
  - visualizer GPU rect authority bar: stale square live geometry must not suppress the next committed-rect overlay push
  - Weather icon alignment bar: shrink must keep the condition icon centered against the primary text block
  - extend the now-green media metadata/controls/mute pattern to Weather and any other widget that still clips under shrink

- [ ] Keep the diagnosis table current while fixes land:

  ```md
  | Widget | Failure layer | First divergent phase | Width changed? | Height change allowed? | Content clips? | Baseline rebasing? | Suspected fix layer |
  |---|---|---|---|---|---|---|---|
  | gmail | inner content fit | post-replay live layout | no in latest `--geo` | yes, row/dead-space cleanup only | yes, subject loss in live | still under audit | sender/time/action lane budgeting |
  | reddit | inner content fit + fetch survivability | post-replay live layout | no in latest `--geo` | yes, staged cache/count growth only | yes, title loss in live | still under audit | title/age lane budgeting + growth path |
  | reddit2 | inner content fit + fetch survivability | post-replay live layout | no in latest `--geo` | yes, staged cache/count growth only | yes, title loss in live | still under audit | title/age lane budgeting + growth path |
  | spotify_visualizer | runtime card/overlay contradiction unless logs re-open shell or replay authority | live runtime/content after replay, unless fresh logs beat the committed-width re-entry and GPU-rect-authority bars | no in latest `--geo` | no | yes in screenshots when runtime contradicts shell | still under audit | card/overlay content fit or monitor-transfer state if committed-width shell + GPU rect bars stay green |
  ```

### 2. Remove the accidental 60 fps cap on Display 0 transitions

- [ ] Re-close the regression where Display 0 is capped to 60 fps despite being 165 Hz.
- [ ] Keep cadence decisions display-local; Display 1 may remain 60 Hz without dragging Display 0 down.
- [ ] Validate with a dual-display transition run and per-display cadence logging.

### 3. Re-close Bubble from the restored `510520e` baseline

- [ ] Keep the restored runtime baseline protected while rebuilding the loud-path oracle honestly.
- [ ] Tighten the oracle toward the real runtime complaint instead of weakening it to fit current code.
- [ ] Add interpolation/motion-blur only after the signal path and oracle are stable.

### 4. Re-close visualizer paused/idle startup behavior

- [ ] Re-validate paused/idle reveal without weakening first-frame guards for startup, reset, rebuild, and settings-exit rebuild.
- [ ] Keep watchdog logging diagnostic-only.

### 5. Re-validate recent visualizer/widget runtime safety checks

- [ ] Confirm same-track media churn still does not trigger visible metadata refit.
- [ ] Keep single-display MC focused-input readiness validated; multi-display focused-key ownership remains explicitly open.
- [ ] Re-check remaining latency warnings during ordinary mode/preset churn.

### 6. Make startup-update policy observable enough to trust

- [ ] Re-run the normal-mode fresh-cache startup-skip path with `--cache` visibility.
- [ ] Confirm the branch now clearly distinguishes fresh-cache skip, stale-cache refresh, blocked-cooldown cache skip, and `--noupdates`.
- [ ] Re-close Reddit startup hardening as two separate contracts:
  - blocked/403 responses must freshen both the widget cache timestamp and the shared Reddit startup gate before the next automatic startup fetch decision runs
  - in-flight widget refreshes must serialize request-slot acquisition so one blocked response can prevent the second widget from reaching Reddit on the same startup wave
- [ ] Replace plain browser-UA roulette with stable Reddit request personas.
  - rotate between distinct client/application appearances with stable bundled headers
  - choose persona by widget/cache/session window instead of randomizing every request
  - keep the current cooldown/cache hardening in front of live retries
  - blocked cooldown skips must not fall through to empty-listing/update-failure reporting
- [ ] After the cooldown window, verify whether the refreshed Reddit User-Agent/header set is enough to regain successful cache creation.
  - If Reddit still returns 403 after cooldown expiry, treat that as a fetch-identity/auth contract issue, not a startup-rate-limit issue.
  - While blocked cooldown is active, Reddit must not also misreport the skip as an empty-listing/update-failure path.

### 7. Restore image-cache / prescale performance after the interactive blockers

- [ ] Defer this until CUSTOM geometry and Bubble stop blocking day-to-day validation.
- [ ] Then re-run `--perf --cache`, confirm real reuse in shutdown summaries, and confirm `ImageWorker prescale` spikes materially drop.

## Watchlist

- CUSTOM geometry stays active until:
  - save/replay parity is stable
  - Gmail/Reddit height-only QoL behavior is restored without width drift
  - shrink does not clip content
  - re-entering edit does not compound

- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.

- `--noupdates` looks correct in logs, but the fresh-cache startup-skip branch still needs a normal-mode validation pass.

- If transition watchdog/compositor-complete failures reappear under `--perf`, inspect `rendering/gl_profiler.py` and `rendering/gl_compositor.py` before treating it as a generic transition regression.

## Deferred / Not Active

- Multi-display compositor/desync/startup-order validation stays deferred unless directly needed for the active Display 0 cadence regression.
- Secure-desktop long-runtime exit reliability stays deferred until the current interactive blockers stop dominating validation time.
- Future authored runtime oracles for Spectrum `Preset 1 (Organs)` and Spline Curve `Preset 1` should follow the stronger Bubble bar pattern.
- Rain Drops / Blinds cleanup stays deferred unless current runtime evidence shows active user harm.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- CUSTOM geometry active audit: `audits/GeoAudit/00_README_INDEX.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks currently remain in this box.
----
######

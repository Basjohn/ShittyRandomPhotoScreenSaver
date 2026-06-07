# Current Plan

Last updated: 2026-06-06

This file tracks active work only. Ongoing architecture truth belongs in the reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

The current top-priority blocker is CUSTOM widget geometry / resize replay. The detailed diagnostic audit for that work now lives in `audits/GeoAudit/` and should be treated as the working map for the next implementation pass.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and the active audit documents in `audits/GeoAudit/`.
- Prune validated work aggressively. Do not let this become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact creative values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Prefer stronger runtime-shaped automation over helper/proxy checks when live behavior is the complaint.
- Do not paper over visual correctness bugs by blocking legitimate runtime layout behavior. If a widget is supposed to grow/shrink because its content count changes, preserve that behavior explicitly instead of globally suppressing resize paths.
- Do not fix CUSTOM geometry by randomly adding more clamps. First identify which authority owns the outer rect, which authority owns inner content scaling, and which path is mutating either one after save/replay.
- Multi-display assumptions must stay explicit. Display 0 is high-refresh, Display 1 is 60 Hz; do not reintroduce a shared 60 fps cap or single-display geometry assumptions.

## GeoAudit Reference Documents

Use these files as the active diagnostic map for the CUSTOM geometry work:

- [`audits/GeoAudit/00_README_INDEX.md`](audits/GeoAudit/00_README_INDEX.md)
  - Audit index and recommended reading order.
- [`audits/GeoAudit/01_Problem_Model_And_Invariants.md`](audits/GeoAudit/01_Problem_Model_And_Invariants.md)
  - Failure model, invariants, symptoms, and non-negotiable CUSTOM contracts.
- [`audits/GeoAudit/02_Edit_Mode_Trace.md`](audits/GeoAudit/02_Edit_Mode_Trace.md)
  - Edit session lifecycle, shell creation, resize baseline, save/cancel/revert semantics.
- [`audits/GeoAudit/03_Save_And_Runtime_Replay_Trace.md`](audits/GeoAudit/03_Save_And_Runtime_Replay_Trace.md)
  - Save path, settings path, runtime rebuild, display recreation, replay timing.
- [`audits/GeoAudit/04_Widget_Scaling_And_Content_Loss_Audit.md`](audits/GeoAudit/04_Widget_Scaling_And_Content_Loss_Audit.md)
  - Widget-specific shrink/text loss audit for Weather, Gmail, Reddit, Media, SpotifyVolume, and visualizer-related scaling.
- [`audits/GeoAudit/05_Diagnostics_Instrumentation_And_Fix_Order.md`](audits/GeoAudit/05_Diagnostics_Instrumentation_And_Fix_Order.md)
  - Required probes, logging plan, validation matrix, and recommended fix order.
- [`audits/GeoAudit/06_Codex_Execution_Prompt.md`](audits/GeoAudit/06_Codex_Execution_Prompt.md)
  - Codex-ready execution prompt for the next implementation pass.

## Active Tasks

### 1. Re-close CUSTOM widget geometry and shrink scaling using the GeoAudit path

- [ ] Treat the CUSTOM geometry bug as the primary blocker until the following are all true:
  - edit preview geometry and saved runtime geometry match after resize/save/reload
  - placement remains correct when no resize is done
  - shrinking is as valid as enlarging
  - shrinking does not lose letters, subjects, location text, post text, image/artwork content, or visualizer content
  - repeated edit sessions do not compound shrink or lower future maximum size
  - multi-display geometry remains stable across different resolutions and refresh rates
  - authored/default min/max constraints do not silently override committed CUSTOM rects
  - widget-local content refresh does not widen, narrow, stretch, shrink, or restack the outer card after CUSTOM replay

- [ ] Start from the audit problem model before editing code:
  - read [`audits/GeoAudit/01_Problem_Model_And_Invariants.md`](audits/GeoAudit/01_Problem_Model_And_Invariants.md)
  - use its invariants as acceptance criteria, not optional commentary
  - keep the known symptom split explicit:
    - enlarging mostly works
    - no-resize placement mostly works
    - resizing introduces unreliability
    - shrinking is the most failure-prone path
    - edit mode can look perfect while runtime is wrong
    - shrink failures include both outer-rect drift and inner content loss

- [ ] Preserve the core CUSTOM contract while debugging and validating:
  - edit preview and saved runtime geometry must match
  - CUSTOM outer width must never silently widen or narrow on save/rebuild for any current widget family
  - CUSTOM outer height must never silently grow/shrink except through an explicitly allowed CUSTOM-aware content-count resize path
  - authored stacking is strictly outside CUSTOM; if any widget family is in `Custom`, stacking must fully stand down for that runtime/layout pass
  - internal artwork/font/track/icon/text scaling may update internals, but committed CUSTOM outer geometry must still be reasserted afterward
  - visualizer height-envelope behavior may still vary internally, but width is still locked by the committed CUSTOM rect
  - shrinking a widget below its authored/default size must be valid
  - pre-existing minimum/maximum constraints must not override the committed CUSTOM outer rect during runtime replay
  - display-local normalized geometry must remain display-local and must not be converted through the wrong monitor/work-area basis

- [ ] Trace edit mode A-to-Z before applying more fixes:
  - use [`audits/GeoAudit/02_Edit_Mode_Trace.md`](audits/GeoAudit/02_Edit_Mode_Trace.md)
  - confirm how edit sessions capture live widget state
  - confirm how shell snapshots are made
  - confirm how resize baselines are chosen
  - confirm how save, cancel, revert, and edit-exit paths differ
  - confirm whether re-entering edit after a shrink captures an already-shrunk widget as the new authored/baseline size
  - specifically test the suspected compounding path:
    - enter edit
    - shrink a widget
    - save
    - re-enter edit
    - inspect whether the maximum size range is now lower than before
    - repeat once and confirm whether shrink compounds again

- [ ] Trace save and runtime replay before widget-local surgery:
  - use [`audits/GeoAudit/03_Save_And_Runtime_Replay_Trace.md`](audits/GeoAudit/03_Save_And_Runtime_Replay_Trace.md)
  - verify `save_session()` writes the intended normalized local rects
  - verify affected widget position keys are forced to `Custom`
  - verify `settings_v2.json` is correct immediately after save
  - verify runtime rebuild refreshes settings from disk before display recreation
  - verify runtime rebuild uses `SettingsManager.get_widgets_map()` instead of stale ad hoc widget snapshots
  - verify CUSTOM layouts are reasserted:
    - before widget startup
    - immediately after widget startup
    - once more on the next event-loop turn
  - verify no later mutator changes the rect after the final replay pass
  - verify `_reload_widgets_across_instances()` teardown/recreate does not apply authored/default geometry after CUSTOM replay

- [ ] Add the diagnostic probes before attempting another fix pass:
  - use [`audits/GeoAudit/05_Diagnostics_Instrumentation_And_Fix_Order.md`](audits/GeoAudit/05_Diagnostics_Instrumentation_And_Fix_Order.md)
  - add geometry-owner logs around:
    - edit shell creation
    - edit resize start
    - edit resize commit
    - save payload creation
    - settings write
    - settings reload
    - widget creation
    - descriptor payload apply
    - widget-local `_update_position()` / `adjustSize()` / `setGeometry()` / `resize()` / `move()`
    - stacking planner entry/exit
    - final runtime replay
    - post-refresh repaint/layout passes
  - each probe should report:
    - widget key
    - display/screen id
    - authority name
    - before rect
    - after rect
    - saved rect
    - mode / position key
    - whether CUSTOM is active
    - whether the write is outer geometry, inner layout, or pure repaint
  - do not replace the bug with silent clamps until the logs show which authority is wrong.

- [ ] Validate the shared stacking exclusion against the exact 2026-06-05 `--geo` failure shape:
  - this run showed correct edit preview followed by post-save runtime stacking on screen 1 for `weather/reddit/reddit2/gmail`
  - geometry logs recorded authored stack planning such as:
    - `reddit2_widget:base=378:desired=311:h=683:off=-67`
    - `gmail_widget:base=512:desired=1004:h=415:off=492`
  - this is concrete evidence that stacking was still touching CUSTOM-replayed widgets after save
  - confirm the next `--geo` run no longer emits shared stacking offsets once a widget family is in `Custom`
  - confirm the saved runtime layout matches the edit shell after resize/save/reload

- [ ] Validate the broadened committed-rect reassertion against the exact families that previously slipped through tests:
  - `reddit_font`
  - `gmail_font`
  - `weather_scale`
  - `media_scale`
  - `volume_scale`
  - descriptor-owned CUSTOM resize modes generally
  - payload application must not be able to widen, narrow, vertically stretch, or restack the saved outer card after runtime replay
  - keep hostile tests that deliberately mutate geometry during payload apply
  - future fixes should extend the hostile-test pattern instead of relying on “well-behaved widget” doubles

- [ ] Finish the widget-local shrink/content-loss audit in priority order:
  - use [`audits/GeoAudit/04_Widget_Scaling_And_Content_Loss_Audit.md`](audits/GeoAudit/04_Widget_Scaling_And_Content_Loss_Audit.md)
  - Weather:
    - location text currently loses letters when shrunk instead of scaling uniformly
    - confirm whether any fit calculation still uses authored/default width such as 600 px while the live CUSTOM rect is smaller
    - ensure location/temp/condition/details scale from the committed rect, not from a stale authored minimum
  - Gmail:
    - subject text currently loses letters despite some font resizing
    - confirm subject/sender/snippet font calculations use the actual committed CUSTOM width/height
    - preserve intentional vertical growth/shrink when the configured email count changes
    - do not globally block post-startup resizing if the resize is content-count-authorized and CUSTOM-aware
  - Reddit:
    - post/title text currently loses letters under shrink
    - inspect setup-time off-screen move and progressive cached-start positioning
    - preserve intentional vertical growth/shrink when the configured post count changes
    - do not globally block post-startup resizing if the resize is content-count-authorized and CUSTOM-aware
  - Media:
    - still appeared wider/different than edit preview after save in at least one recent run
    - verify artwork sizing cannot own outer card width/height under active CUSTOM
    - verify metadata refit does not mutate outer geometry
  - SpotifyVolume:
    - still reported live edit-shell distortion even though post-save runtime replay is supposedly locked to saved rect
    - inspect live edit preview and shell snapshot assumptions separately from post-save replay
  - Spotify visualizer:
    - looked sane in the most recent run, but keep on watch until another `--geo` pass confirms it does not narrow under a different sequence
    - verify visualizer width is locked by the committed CUSTOM rect even if internal height envelope varies

- [ ] Re-open the “post-startup resizing” mistake as a required design correction:
  - removing/blocking all post-startup resizing from Gmail/Reddit was wrong
  - if the user changes the post count or email count, Reddit/Gmail should shrink or grow vertically for that setting
  - the correct rule is not “no post-startup resizing”
  - the correct rule is:
    - content-count-authorized resize may change height when the configured item count changes
    - CUSTOM geometry replay still owns the committed outer rect for user-resized widgets
    - if a widget is in CUSTOM and the count changes, the resize must be deterministic, logged, and based on a clear policy
    - content-count resize must never masquerade as an authored/default stack correction
    - content-count resize must not corrupt x/y, width, display id, or user placement
  - add a specific test case:
    - Reddit/Gmail in authored/default mode: count change may resize vertically as designed
    - Reddit/Gmail in CUSTOM mode: count change must follow the chosen CUSTOM-aware policy and must not corrupt placement/width
    - edit preview after the count change must match runtime

- [ ] Keep the stale-snapshot failure mode explicit while re-testing:
  - the saved `settings_v2.json` can already be correct while runtime still behaves as if widgets are authored/default-sized
  - geometry-critical runtime seams must read the canonical widgets snapshot through `SettingsManager.get_widgets_map()` (Ensure you are using/checking main.py's designated settings json if the logs are running main.py)
  - avoid ad hoc `get('widgets', ...)` calls in geometry-critical paths
  - CUSTOM runtime reload must refresh the in-memory settings snapshot before display recreation
  - post-save rebuilds must not keep consulting stale widget-route data
  - active committed custom rects must suppress parent restack churn even after replay, instead of relying on a later stacking no-op

- [ ] Retain the previous audit facts as known history, but do not assume they are sufficient:
  - save path previously looked logically correct: `save_session()` writes normalized local rects and forces the affected widget position keys to `Custom`
  - first confirmed shared bug was runtime startup finalization:
    - saved CUSTOM layouts were reapplying before widget startup
    - they were not reasserted after startup logic ran
  - shared startup finalization was changed to reassert CUSTOM layouts three times:
    - before widget startup
    - immediately after widget startup
    - once more on the next event-loop turn
  - CUSTOM save now marks runtime reload pending while `settings_manager.save()` emits
  - `WidgetManager` suppresses live `widgets.*` refresh handlers during that pending window
  - `_reload_widgets_across_instances()` still tears down widgets and runs a full `instance._setup_widgets()` recreate path
  - any remaining drift after this stabilization contract must be traced as a later mutator rather than blamed on edit mode by default

- [ ] Retain the previous widget-local geometry closure list, but re-verify under shrink:
  - `GmailWidget._apply_width()` was changed so it should no longer resize/reposition the outer card when a saved CUSTOM rect is active
  - `MediaWidget.set_artwork_size()` was changed so it should lock minimum height to the active CUSTOM rect and reassert geometry instead of letting artwork sizing own the outer card
  - `SpotifyVolumeWidget.apply_scale_contract()` was changed so it should lock runtime replay to the saved CUSTOM rect instead of letting scale payloads narrow or shorten the outer card after save
  - `WeatherWidget` runtime content/error refresh was changed so it should no longer use `adjustSize()` / authored repositioning to overwrite an active CUSTOM rect
  - committed rect replay was broadened beyond `media_scale` / `volume_scale`; all descriptor-owned CUSTOM resize modes should reassert the saved outer rect after payload apply
  - `BaseOverlayWidget` was changed so it should lock min/max width/height to the committed CUSTOM rect during runtime replay and restore authored constraints when CUSTOM authority clears
  - geometry-critical runtime seams were changed to use the canonical widgets snapshot and reload settings from disk before recreating displays
  - active committed custom rects were changed so they should no longer schedule shared parent stacking recalculation requests through `BaseOverlayWidget`
  - `RedditWidget` still performs an off-screen `move(10000, 10000)` during setup; keep this on watch even if stacking is outside CUSTOM

- [ ] Keep the current diagnostic posture:
  - because edit placement without resizing is mostly correct, remaining drift should not be treated as a generic edit-shell bug
  - because edit resize preview can be a scaled pixmap snapshot, “looks right in edit” does not prove live widget internals scale correctly
  - remaining drift should be classified as one of:
    - save payload corruption
    - stale settings snapshot
    - runtime replay order
    - widget-local outer geometry mutation
    - widget-local inner content scaling failure
    - stacking/parent layout authority leakage
    - multi-display normalization error
    - edit-baseline rebasing / compounding shrink
  - do not rewrite CUSTOM edit behavior unless logs prove the shell itself is wrong

- [ ] Execute the next pass using the Codex prompt:
  - use [`audits/GeoAudit/06_Codex_Execution_Prompt.md`](audits/GeoAudit/06_Codex_Execution_Prompt.md)
  - first add probes
  - then run the smallest reproductions
  - then fix the first proven mutator
  - then re-run the same logs
  - only then proceed to the next mutator
  - do not stack speculative fixes.

### 2. Remove the accidental 60 fps cap on Display 0 transitions

- [ ] Investigate the regression where Display 0 transitions are capped at 60 fps again.
  - Known user evidence:
    - reference/baseline `510520e` did not have this cap
    - current behavior forces Display 0 to 60 fps
    - Display 0 is 165 Hz
    - Display 1 is 60 Hz
    - likely causes include poor display refresh detection, using the wrong display as global cadence authority, or incorrectly applying the lowest refresh rate across all displays
  - Acceptance criteria:
    - Display 0 transition cadence should respect its own refresh capability
    - Display 1 may remain 60 Hz
    - no global 60 fps clamp should be applied to all displays unless explicitly requested by settings
    - multi-display compositor timing must not regress first-frame reveal behavior
  - Validation:
    - run a dual-display transition test
    - log per-display refresh/cadence decision
    - confirm Display 0 is not capped to Display 1’s refresh
    - confirm no reintroduced transition watchdog or compositor-complete failure

### 3. Re-close Bubble from the restored `510520e` baseline without reintroducing complexity

- [ ] Validate the current single small-lane support/source changes against live runtime.
  - Keep them only if they materially improve small-bubble participation without harming the restored big-bubble life.
  - Do not let oracle work drag Bubble backward again.

- [ ] Use the current runtime logs as the Bubble oracle target before adding more signal-path work.
  - Latest live evidence still says the small lane is the blocker:
    - loud windows with strong source energy such as `raw_bass=1.902` / `2.015`
    - still publishing weak bars around `~0.08` / `~0.15` max
  - Restored big lane now at least keeps obvious life.
  - Treat restored `510520e` + Dynamic Noise Floor behavior as the minimum baseline to protect.

- [ ] Tighten the Deep Sea oracle upward from the current floor guard.
  - It should match present runtime behavior as closely as possible under synthetic/runtime-shaped replay.
  - Focus especially on:
    - small-lane soft/loud participation
    - vocal/snare lift
    - restored big-bubble life
  - In the 2026-06-05 run, `Preset 1 (Deep Sea)` only held for a few seconds (`17:31:18-17:31:21`), so the useful baseline from that window is startup/reset behavior rather than a full phrase:
    - dynamic floor on
    - manual floor `0.10`
    - `input_gain=0.350`
    - `sensitivity=0.400`
    - `block=128`
    - first fresh-frame render after reset reached `display_max=0.177`, `display_avg=0.114`
    - dynamic floor ramped from `applied=0.184` to `0.626` within roughly two seconds
    - transient bus stayed quiet with `onset=False`
    - suggest methods of making dynamic floor more reliable regardless of song or track
  - Use that as the minimum “alive under restored baseline” floor.
  - Do not pretend this short run is enough to model a sustained Deep Sea loud section.
  - A longer single-preset capture is still needed before tightening beyond that.

- [ ] Add the deferred Bubble interpolation / motion-blur option cleanly if runtime still wants it after the signal path is stable.
  - If interpolation lands, keep all propagation complete:
    - UI buckets
    - settings model
    - serializer
    - defaults
    - preset payloads
    - `/tools` support
  - Keep changes one visible seam at a time.
  - After each significant Bubble change, compare runtime and oracle before stacking another.

### 4. Re-close visualizer paused/idle startup behavior without poisoning first-frame guards

- [ ] Re-validate that the paused/idle reveal path does not weaken first-frame guardrails for:
  - playing startup
  - mode reset
  - preset reset
  - display rebuild
  - settings exit rebuild

- [ ] Keep watchdog logging diagnostic-only.
  - It must never become reveal authority again.

- [ ] Keep current dual-display startup/cadence evidence attached:
  - latest run had clean first-frame commits on both screens at startup and rebuild
  - both `screen=0` and `screen=1` were represented
  - no `FIRST_FRAME_GUARD` appeared
  - no reveal-watchdog expiry appeared
  - routine preset/mode churn still emitted repeated `MODE_RESET_ASSERT` plus `FIRST_FRAME_PRIMER` lines
  - re-check whether that reset logging volume is expected diagnostic noise or an unresolved reset-order issue

### 5. Re-validate still-open runtime safety checks around recent visualizer/widget work

- [ ] Confirm same-track media metadata still does not refit/reformat title or artist due to non-visible churn.

- [ ] Confirm single-display MC focused-input readiness is still good.
  - Leave multi-display focused-key ownership explicitly open until real multi-display validation is available.

- [ ] Re-check low-grade visualizer latency warnings during routine mode/preset churn.
  - Latest run still logged `lag_ms≈94-95` for `sine_wave` and `bubble` with `pending=<none>`.
  - Keep paused-idle spam fixed.
  - Verify these remaining warnings correlate to real churn rather than stale lag state.

### 6. Make the shared startup-update policy observable enough to trust during heavy runtime testing

- [ ] Validate the normal-mode fresh-cache `<15 min` startup-skip path now that branch logging moved into the `--cache` stream for Gmail/Reddit/Weather.

- [ ] The earlier normal-mode run only proved cache loads plus immediate Reddit rate-limit waits.
  - Because the skip branch previously logged only at debug, that run could not tell whether startup fetch was truly allowed or merely unobservable.

- [ ] The next cache-enabled normal run should now clearly say one of:
  - startup refresh skipped because cache is fresh
  - startup refresh allowed because cache is stale/missing
  - automatic updates disabled via `--noupdates`

- [ ] If a known-fresh normal-mode run still reports startup refresh allowed:
  - inspect whether the preceding `--fresh` validation run actually had time to rewrite service cache timestamps before exit

### 7. Restore image-cache / prescale performance to a healthy runtime contract after the interactive blockers

- [ ] Defer this until CUSTOM geometry and Bubble are no longer blocking day-to-day validation.

- [ ] Validate:
  - cold-start scaled-hit behavior
  - early manual-next worker fallthrough
  - whether cache-side work still correlates with shared cadence stalls in `--perf`

- [ ] Re-run clean `--perf --cache` validation after the next cache-side fix.

- [ ] Confirm shutdown summaries show real scaled/raw reuse.

- [ ] Confirm `ImageWorker prescale` spikes materially drop.

- [ ] Treat any renewed startup flicker, wrong backing/shadow behavior, or first-frame mismatch as an automatic rollback condition for cache work.

## Watchlist

- CUSTOM geometry remains on the watchlist until the GeoAudit validation matrix is green:
  - repeated shrink/save/re-enter edit must not compound
  - Weather must not lose location letters under shrink
  - Gmail must not lose subject letters under shrink
  - Reddit must not lose post/title letters under shrink
  - Media must not widen/narrow relative to edit preview after save
  - SpotifyVolume live edit distortion must be isolated and fixed
  - Spotify visualizer must survive at least one more `--geo` resize/save/reload pass without narrowing
  - no shared stacking offsets may be emitted for CUSTOM widgets
  - no widget-local startup move may survive final CUSTOM replay

- `RedditWidget` still has a setup-time off-screen move plus progressive cached-start positioning path.
  - After the shared replay and save-time suppression fixes there may no longer be a known slot-collision or stacking-based cause left in code.
  - Keep it on watch for the next `--geo` verification.

- `--noupdates` is behaving correctly in logs.
  - The fresh-cache startup-skip branch still needs one normal-mode validation run with better branch logging before it can leave the watchlist.

- Non-`Custom` authored stacking remains explicit opt-in.
  - It must stay default-off until a future re-audit proves the planner respects real authored screenshots plus `--geo` traces.

- If `--perf` is enabled and a transition watchdog or compositor-complete failure reappears:
  - check `rendering/gl_profiler.py`
  - check `rendering/gl_compositor.py`
  - do this before treating it as a transition-runtime regression.

- Keep visualizer preset/settings drift in view during later audits:
  - preserve CLEAR-then-APPLY semantics
  - do not reintroduce a second post-overlay merge phase
  - do not reintroduce entry-point-specific fallback behavior for visualizer settings

## Deferred / Not Active

- Multi-display compositor/desync/startup-order validation stays open but deferred until real multi-display runtime is available again.
  - Exception: the Display 0 165 Hz / Display 1 60 Hz transition cap regression is active now because it is a current visible regression.

- Secure-desktop long-runtime exit reliability stays deferred until the current interactive visualizer/widget regressions stop blocking day-to-day validation.

- Future authored runtime oracles for Spectrum `Preset 1 (Organs)` and Spline Curve `Preset 1` should follow the stronger Bubble bar pattern rather than weak generic guards.

- Rain Drops / Blinds cleanup stays deferred unless current runtime evidence shows fallback or dead-path behavior is actively harming users.

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

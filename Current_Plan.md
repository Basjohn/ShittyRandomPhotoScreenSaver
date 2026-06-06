# Current Plan

Last updated: 2026-06-05

This file tracks active work only. Ongoing architecture truth belongs in the reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Do not let this become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact creative values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Prefer stronger runtime-shaped automation over helper/proxy checks when live behavior is the complaint.

## Active Tasks

- [ ] Re-close the shared CUSTOM geometry replay contract around settings-exit rebuilds before touching more widget-specific sizing logic.
  - [ ] Keep the rollback decision explicit: do not wholesale-revert geometry to `510520e` for this seam, because that revision still resolves CUSTOM visualizer width from `media_width` and therefore preserves the wrong outer-width contract.
  - [ ] Keep the actual CUSTOM contract explicit while debugging and validating:
    - edit preview and saved runtime geometry must match
    - CUSTOM outer width must never silently widen or narrow on save/rebuild for any current widget family
    - authored stacking is strictly outside CUSTOM; if any widget family is in `Custom`, stacking must fully stand down for that runtime/layout pass
    - internal artwork/font/track scaling may update internals, but committed CUSTOM outer geometry must still be reasserted afterward
    - visualizer height-envelope behavior may still vary internally, but width is still locked by the committed CUSTOM rect
    - shrinking a widget below its authored/default size must be just as valid as enlarging it; pre-existing minimum/maximum constraints must not override the committed CUSTOM outer rect during runtime replay
  - [ ] Validate the shared stacking exclusion against the exact 2026-06-05 `--geo` failure shape:
    - this run showed correct edit preview followed by post-save runtime stacking on screen 1 (`weather/reddit/reddit2/gmail`)
    - geometry logs recorded authored stack planning such as `reddit2_widget:base=378:desired=311:h=683:off=-67` and `gmail_widget:base=512:desired=1004:h=415:off=492`, which is the concrete evidence that stacking was still touching CUSTOM-replayed widgets after save
    - confirm the next `--geo` run no longer emits any shared stacking offsets once a widget family is in `Custom`, and that the saved runtime layout matches the edit shell
  - [ ] Validate the broadened committed-rect reassertion against the exact failure families that were previously slipping through tests:
    - `reddit_font`, `gmail_font`, and `weather_scale` payload application must not be able to widen, narrow, or vertically stretch the saved outer card after runtime replay
    - keep the new hostile tests that deliberately mutate geometry during payload apply; future fixes should extend that pattern instead of relying on “well-behaved widget” doubles
  - [ ] Re-test the remaining post-save/edit mismatches after stacking is removed from CUSTOM and committed-rect replay is universal:
    - `media` still appears wider/different than edit preview after save in at least one recent run
    - `spotify_volume` still distorts during live edit before save
    - `reddit` / `reddit2` were correctly placed in edit mode but resolved into overlap after save
    - `spotify_visualizer` looked sane in the most recent run, but keep it on the watchlist until at least one more `--geo` pass confirms it
  - [ ] If any of the above still drift after stacking is excluded, trace the next shared post-save mutator before editing widget-local geometry again:
    - saved custom rect application in `CustomLayoutManager`
    - widget-local `_update_position()` / scale hooks
    - post-settings runtime reload order
    - compositor/lifecycle reveal order only if geometry is already proven correct before reveal
  - [ ] Keep the stale-snapshot failure mode explicit while re-testing:
    - the saved `settings_v2.json` can already be correct while runtime still behaves as if widgets are authored/default-sized
    - geometry-critical runtime seams must read the canonical widgets snapshot through `SettingsManager.get_widgets_map()` rather than ad hoc `get('widgets', ...)` calls
    - CUSTOM runtime reload must refresh the in-memory settings snapshot before display recreation so post-save rebuilds cannot keep consulting stale widget-route data
    - active committed custom rects must suppress parent restack churn even after replay, instead of relying on a later stacking no-op
  - [ ] Keep the full CUSTOM-path audit attached to this task so future fixes stay clean and shared:
    - save path currently looks logically correct: `save_session()` writes normalized local rects and forces the affected widget position keys to `Custom`
    - runtime rebuild order was the first confirmed shared bug: widget startup finalization was reapplying saved CUSTOM layouts before widget startup, but not again after startup logic ran
    - shared startup finalization now reasserts CUSTOM layouts three times by contract:
      - before widget startup
      - immediately after widget startup
      - once more on the next event-loop turn as a stabilization pass
    - closed: CUSTOM save now marks runtime reload pending while `settings_manager.save()` emits, and `WidgetManager` suppresses live `widgets.*` refresh handlers during that window instead of letting authored refresh churn fight the committed rebuild
    - `_reload_widgets_across_instances()` still tears down widgets and runs a full `instance._setup_widgets()` recreate path, so any remaining drift after this stabilization contract must be traced as a later mutator rather than blamed on edit mode
    - concrete widget-local geometry writes discovered during the audit:
      - closed: `GmailWidget._apply_width()` no longer resizes/repositions the outer card when a saved CUSTOM rect is active
      - closed: `MediaWidget.set_artwork_size()` now locks its minimum height to the active CUSTOM rect and reasserts geometry instead of letting artwork sizing own the outer card
      - closed: `SpotifyVolumeWidget.apply_scale_contract()` now locks runtime replay to the saved CUSTOM rect instead of letting scale payloads narrow or shorten the outer card after save
      - closed: `WeatherWidget` runtime content/error refresh no longer uses `adjustSize()` / authored repositioning to overwrite an active CUSTOM rect
      - closed: committed rect replay is no longer special-cased to `media_scale` / `volume_scale`; all descriptor-owned CUSTOM resize modes now reassert the saved outer rect after payload apply
      - closed: BaseOverlayWidget now locks min/max width/height to the committed CUSTOM rect during runtime replay and restores authored constraints when CUSTOM authority clears, so shrinked layouts are not silently expanded back toward authored defaults
      - closed: geometry-critical runtime seams now use the canonical widgets snapshot (`get_widgets_map()`) and custom reloads refresh settings from disk before recreating displays, so a correct saved file cannot be silently undermined by stale in-memory route data
      - closed: active committed custom rects no longer schedule shared parent stacking recalculation requests through `BaseOverlayWidget`
      - watch closely: `RedditWidget` still performs an off-screen `move(10000, 10000)` during setup, even though stacking is now explicitly outside CUSTOM and committed replay is universal
    - because edit mode is already correct, any remaining drift should be treated as save/apply/runtime-reload corruption, not as an edit-shell problem
    - do not let future fixes rewrite CUSTOM edit behavior unless logs prove the shell itself is wrong
  - [ ] If geometry is still unhealthy after the shared replay fixes, finish the widget-local audit in this order instead of guessing:
    - `SpotifyVolumeWidget` live edit-shell distortion seam, which is still reported even though post-save runtime replay is now locked to the saved rect
    - `MediaWidget` post-settings width/height replay if it still widens or narrows relative to the correct edit preview after the shared replay clamps
    - `RedditWidget` setup/startup moves and any post-refresh authored repositioning that can survive CUSTOM replay

- [ ] Re-close Bubble from the restored `510520e` baseline without reintroducing complexity.
  - [ ] Validate the current single small-lane support/source changes against live runtime and keep them only if they materially improve small-bubble participation without harming the restored big-bubble life.
  - [ ] Use the current runtime logs as the Bubble oracle target before adding more signal-path work.
    - Latest live evidence still says the small lane is the blocker: loud windows with strong source energy such as `raw_bass=1.902` / `2.015` are still publishing weak bars (`~0.08` / `~0.15` max), while the restored big lane now at least keeps obvious life.
    - Treat the restored `510520e` + Dynamic Noise Floor behavior as the minimum baseline to protect while tightening the oracle; do not let the oracle drag Bubble backward again.
  - [ ] Tighten the Deep Sea oracle upward from the current floor guard so it matches present runtime behavior as closely as possible under synthetic/runtime-shaped replay, especially small-lane soft/loud participation and vocal/snare lift.
    - In the 2026-06-05 run, `Preset 1 (Deep Sea)` only held for a few seconds (`17:31:18-17:31:21`), so the useful baseline from that window is startup/reset behavior rather than a full phrase:
      - dynamic floor on, manual floor `0.10`, `input_gain=0.350`, `sensitivity=0.400`, `block=128`
      - first fresh-frame render after reset reached `display_max=0.177`, `display_avg=0.114`
      - dynamic floor ramped from `applied=0.184` to `0.626` within roughly two seconds while the transient bus stayed quiet (`onset=False`)
    - Use that as the minimum “alive under restored baseline” floor, but do not pretend this run alone is enough to model a sustained Deep Sea loud section; a longer single-preset capture is still needed before tightening beyond that.
  - [ ] Add the deferred Bubble interpolation / motion-blur option cleanly if runtime still wants it after the signal path is stable.
  - [ ] Keep Bubble options/settings propagation complete if interpolation lands: UI buckets, settings model, serializer, defaults, preset payloads, and `/tools` support must all stay in sync.
  - [ ] Keep changes one visible seam at a time: after each significant Bubble change, compare runtime and oracle before stacking another.

- [ ] Re-close visualizer paused/idle startup behavior so reveal authority stays correct without poisoning first-frame guards.
  - [ ] Re-validate that the paused/idle reveal path does not weaken the first-frame guardrails for playing startup or mode/preset reset paths.
  - [ ] Keep watchdog logging diagnostic-only; it must never become reveal authority again.
  - [ ] Keep the current dual-display startup/cadence evidence attached to this task:
    - latest run had clean first-frame commits on both screens at startup and rebuild (`screen=0` and `screen=1`)
    - no `FIRST_FRAME_GUARD` or reveal-watchdog expiry appeared in this run
    - but routine preset/mode churn still emits repeated `MODE_RESET_ASSERT` plus `FIRST_FRAME_PRIMER` lines, so re-check whether that volume of reset logging is still expected diagnostic noise or an unresolved reset-order issue

- [ ] Re-validate the small set of still-open runtime safety checks around recent visualizer/widget work.
  - [ ] Confirm same-track media metadata still does not refit/reformat title or artist due to non-visible churn.
  - [ ] Confirm single-display MC focused-input readiness is still good, while leaving multi-display focused-key ownership explicitly open until real multi-display validation is available.
  - [ ] Re-check the low-grade visualizer latency warnings during routine mode/preset churn:
    - latest run still logged `lag_ms≈94-95` for `sine_wave` and `bubble` with `pending=<none>`
    - keep paused-idle spam fixed, but verify these remaining warnings still correlate to real churn rather than stale lag state

- [ ] Make the shared startup-update policy observable enough to trust during heavy runtime testing.
  - [ ] Validate the normal-mode fresh-cache (<15 min) startup-skip path explicitly now that branch logging has moved into the `--cache` stream for Gmail/Reddit/Weather.
    - the earlier normal-mode run only proved cache loads plus immediate Reddit rate-limit waits
    - because the skip branch previously logged only at debug, that run could not tell us whether startup fetch was truly allowed or merely unobservable
    - the next cache-enabled normal run should now say one of:
      - startup refresh skipped because cache is fresh
      - startup refresh allowed because cache is stale/missing
      - automatic updates disabled via `--noupdates`
  - [ ] If a known-fresh normal-mode run still reports startup refresh allowed, inspect whether the preceding `--fresh` validation run actually had time to rewrite the service cache timestamps before exit.

- [ ] Restore image-cache / prescale performance to a healthy runtime contract when Bubble is no longer the blocking interactive problem.
  - [ ] Validate cold-start scaled-hit behavior, early manual-next worker fallthrough, and whether cache-side work still correlates with shared cadence stalls in `--perf`.
  - [ ] Re-run clean `--perf --cache` validation after the next cache-side fix and confirm shutdown summaries show real scaled/raw reuse while `ImageWorker prescale` spikes materially drop.
  - [ ] Treat any renewed startup flicker, wrong backing/shadow behavior, or first-frame mismatch as an automatic rollback condition for cache work.

## Watchlist
- Better repro still needed for current CUSTOM-layout regressions that are not yet visible enough in logs alone:
  - `spotify_visualizer` looked sane in one recent resize/save pass after the replay fixes, but keep it on watch until another `--geo` run confirms it is not still narrowing under a different sequence.
  - `RedditWidget` still has a setup-time off-screen move plus progressive cached-start positioning path, but after the shared replay and save-time suppression fixes there is no longer a known slot-collision or stacking-based cause left in code; keep it on watch for the next `--geo` verification.
- `--noupdates` is behaving correctly in logs, but the fresh-cache startup-skip branch still needs one normal-mode validation run with better branch logging before it can leave the watchlist.
- Non-`Custom` authored stacking remains explicit opt-in and must stay default-off until a future re-audit proves the planner respects real authored screenshots plus `--geo` traces.
- If `--perf` is enabled and a transition watchdog or compositor-complete failure reappears, check `rendering/gl_profiler.py` / `rendering/gl_compositor.py` before treating it as a transition-runtime regression.
- Keep visualizer preset/settings drift in view during later audits:
  - preserve CLEAR-then-APPLY semantics
  - do not reintroduce a second post-overlay merge phase
  - do not reintroduce entry-point-specific fallback behavior for visualizer settings

## Deferred / Not Active
- Multi-display compositor/desync/startup-order validation stays open but deferred until real multi-display runtime is available again.
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

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
1. At some point you also introduced a 60fps cap on Display 0's transitions again as well. 510520e did not have this, somewhere between now and then it was accidentally introduced. Reference display 0 is 165hz and Display 1 is 60hz but it is forcing 60fps on Display 0, either poor detection or incorrect capping.
2. Removing/Blocking all post startup resizing from Gmail/Reddit was the wrong move. If a user changes the post count of Reddit or Gmail then the widget shrinks or grows vertically for that, this was intentional and good behaviour, it is now dead.
----
######

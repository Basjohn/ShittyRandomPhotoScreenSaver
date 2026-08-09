# U-09 — 2026-06-13 / 2026-06-29 — Visualizer CUSTOM Runtime Shape Poison / Post-Replay Geometry Authority Split (Watchlist With Stale-Bucket Repair)

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Current state:** ordinary CUSTOM edit/save/replay geometry remains watchlist-clean, but the 2026-06-29 settings-return run reopened a narrower stale-bucket creation seam. This is not broad permission to relax foreign rect replay; it is a one-rect, concrete-monitor bucket repair problem.
- **Observed failure pattern:**
  - the user did not edit preset card sizes or any non-uniform width contract
  - `rendering.custom_layout_manager` can still log a correct `replay_final` rect while runtime visually disagrees
  - the issue remains visualizer-specific; other widgets do not show the same bizarre shape corruption class
  - a fresh 2026-06-19 settings-close rebuild could still leave the visualizer misplaced into the top-left corner after returning from settings even though the newer duplicate-owner startup/sleep-wake fallback work looked clean in the latest logs
- **Key evidence that re-opened the family:**
  - `logs/screensaver_geometry.log` repeatedly shows startup replay beginning from poisoned live geometry such as:
    - `05:18:16` `widget=spotify_visualizer phase=replay_start local=(696,840,840,560) global=(0,0,100,400)`
    - `05:18:16` `phase=replay_after_payload local=(0,0,840,560)`
    - `05:18:16` `phase=replay_final local=(696,840,840,560)`
  - the same startup pattern appears again at `05:33:53` and `05:34:30`
  - `logs/screensaver_spotify_vis.log` still shows staged startup/first-frame ownership churn around the same family:
    - `Card height set: 88 -> 400 (mode=spectrum)`
    - `startup_create`
    - `settings_refresh`
    - `FIRST_FRAME_PRIMER problems=overlay_generation_stale,overlay_activation_stale`
  - `logs/screensaver_geometry.log` from `2026-06-19 01:44:37 .. 01:44:38` shows the settings-close rebuild replaying other CUSTOM widgets from obviously poisoned `replay_start` globals before they recover, while the visualizer is recreated on `screen=1` with `custom_routing=True` but does not emit the same `GEO_AUDIT` replay trail in that rebuild window
  - the same `2026-06-19 01:44:38` rebuild window does **not** show the newer `[SPOTIFY_VIS][FALLBACK]` duplicate-owner/reconcile path firing, which weakens the theory that R-26 is the direct cause of this top-left failure
  - `2026-06-27 16:17:10` added a concrete route/bucket contradiction: `spotify_visualizer` saved `global=(372,348,844,562)` on display 0 while persisting `monitor=2`, then startup correctly rejected the missing exact display-2 bucket and suppressed creation
  - the same run showed the media recovery button inheriting a bad recovery aspect/placement when no exact saved display bucket was found, leaving a blank editable shell that was usable but not visualizer-shaped or discoverable enough
  - `2026-06-29 04:14:18` and `04:14:59` added the current narrow failure in `.tmp/perf_collapse_evidence_20260628_164113/20260629_0417_settings_return_collapse`: after settings return, creation logged `[SPOTIFY_VIS][FALLBACK] No saved CUSTOM visualizer rect matched live screen bucket=...; foreign-bucket geometry priming rejected` and then suppressed the visualizer entirely
  - `2026-06-29 04:15:17` proved the rect data still existed under a foreign bucket because the edit recovery button found `source=saved_foreign_visualizer_centered`; after recovery/save, later settings return recreated the visualizer on screen `1`
- **Why U-08 was not enough:**
  1. U-08 genuinely fixed shrink replay/min-constraint drift and improved replay parity.
  2. It did not prove that replay was the final geometry authority through every later visualizer-owned seam.
  3. The reopened family shows that startup, overlay, or post-replay runtime writers can still reintroduce impossible shapes after a correct replay.
- **Current suspected root-cause family:**
  1. The visualizer still has multiple geometry authorities after CUSTOM replay.
  2. The widget outer rect and GL overlay rect can still resolve from different state snapshots.
  3. Startup create, settings refresh, secondary-stage activation, preferred-height application, or generic overlay helpers may still mutate geometry after committed CUSTOM authority should have won.
  4. Save-time monitor authority can drift from the shell's actual global rect owner, causing later strict startup replay to reject an otherwise valid saved visualizer rect.
  5. Existing automation still proves local replay truths better than end-to-end runtime shape truth.
- **Validated containment and closure state:**
  - `rendering.custom_layout_manager` now repairs `spotify_visualizer` CUSTOM save ownership from the shell's actual global rect before persisting monitor/bucket authority, with a loud warning when this poisoned route is corrected
  - the edit-mode media recovery button now uses an exact saved visualizer rect when available, otherwise a centered visualizer-aspect rescue rect; a single foreign saved visualizer rect is used only as a recovery size/aspect hint, not as normal startup replay authority
  - bars cover the stale-route save shape and the foreign-saved recovery shape in `tests/test_custom_layout_manager.py`
  - the 2026-06-27 long `--geo` run validated the recovery behavior: the visualizer survived edit saves, replayed a valid corrected rect after save-route repair, and the recovery button behaved as an editable rescue path rather than removing the visualizer from all displays
  - the same run still emitted `[CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route...` at `16:48:38` and `16:50:09`, so normal edit-mode saves can still enter the repair path
  - the 2026-06-28 preserved `--geo` run superseded the open 2026-06-27 save-route concern for now: visualizer replay/save cycles stayed healthy and did not require route repair
  - the 2026-06-29 code path now promotes a single stale foreign visualizer rect into the live display bucket only when `spotify_visualizer.position=Custom`, the route points at the current concrete monitor, the parent display index matches that monitor, and exactly one saved visualizer rect exists; absent target, wrong-monitor, and ambiguous foreign buckets remain rejected
  - the 2026-06-30 route-authority pass added a stricter live-display guard: if a sole saved visualizer rect belongs to another active display, creator-time repair refuses to move it and instead recovers a stale/missing CUSTOM monitor route from live saved-rect evidence before owner selection; stale inactive signature drift can still repair onto the same monitor
  - the 2026-07-01 display-wake pass narrowed that recovery again: during reduced live topology, an explicit positive CUSTOM monitor route is preserved instead of being rewritten to the sole temporary display, and `DisplayManager` now reconciles full screen signatures after screen add/remove bursts so same-count wake swaps still rebuild
  - the follow-up `14:48..14:49` display-wake run exposed the missing second half: replacement `DisplayManager` instances detected returning displays but were no longer connected to `ScreensaverEngine._on_monitors_changed`; monitor signal wiring now lives in the display-manager creation/rebuild lifecycle, while `_subscribe_to_events()` avoids duplicate monitor subscriptions
  - the later wake run exposed a separate readiness-ordering flaw: `ScreensaverEngine._on_monitors_changed()` could replay the current image as soon as the replacement manager returned, even though staggered later displays had not completed show/render-surface/compositor setup; display startup now emits a generation-scoped `displays_ready` signal before the engine replays the current image
  - first-frame startup readiness no longer uses `QTimer.singleShot(0)` plus forced `repaint()`; readiness publication now uses the injected `ThreadManager` handoff and the normal paint schedule
  - `tools/transition_perf_health_parser.py` now names both visualizer CUSTOM creation suppression and bucket repair as timeline markers so this seam is not lost inside generic fallback noise
  - a related 2026-06-29 startup authority split was fixed separately from geometry repair: visualizer self-registration now prefers the manager-owned Spotify secondary-stage wrapper, and manager runtime-pause/fade-reset generation changes invalidate stale queued starters so a widget cannot remain "registered" against a cleared queue and wait forever for a secondary stage that no longer exists
- **Reopen criteria:**
  - ordinary visualizer CUSTOM edit saves emit `[CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route...`
  - `[SPOTIFY_VIS][FALLBACK]` duplicate-owner or requested-monitor participation fallback appears during a normal healthy multi-display run
  - logs show replay-green/runtime-wrong geometry, unauthorized width/aspect drift, top-left/square deformation, or recovery becoming the primary correctness path again
  - the new single-foreign-bucket repair repeats after it should have persisted the canonical display bucket

## Record Provenance

This standalone file preserves the complete former inline `U-09` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

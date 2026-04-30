# Current Plan

Last updated: 2026-04-30

This file tracks active work and near-term validation.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as the authored preset source tree.
- Do not add tests that require authored visualizer presets to keep specific names, slots, or numeric creative values beyond schema/index/repair contracts.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.

## Active Priorities
- Keep settings/dialog stability and startup behavior regression-free while preserving custom styling.
- **U-05 RESOLVED (2026-04-25)**: MC Keyboard Focus / Ctrl Halo Runtime Input Family fixed via wiring dead code `_restore_mc_input_focus`.
- **GMAIL WIDGET**: Plan v5.0 active in `Docs/Gmail_Widget_Plan.md` (2026-04-29).
  - [x] Foundation/settings/UI/sound implemented; Gmail dev gate removed and Gmail is now ordinary feature plumbing.
  - [x] Phase A structural polish implemented: nine-position enum, single `gmail.width`, Media-style content margins, measured header frame.
  - [x] Phase B deep-link foundation implemented: `core/gmail/gmail_deeplinks.py`, IMAP `open_url`, Gmail account slot, decimal `X-GM-THRID` to lowercase hex, focused tests.
  - [x] Phase B Inbox-order regression corrected: removed the over-fetch/date-sort mitigation and restored newest-UID mailbox order because runtime evidence showed the mitigation caused a worse Gmail Inbox mismatch.
  - [x] Phase C first safety pass implemented: widget async fetch generation/cancel guard, stale results ignored after cleanup/settings changes, `gmail_imap.py` hot-path `re` import removed.
  - [x] Phase B/D screenshot polish slice implemented: row clicks prefer `email.open_url`, action menu click has priority in widget tests, vertical ellipsis indicator, contraction-safe subject title case, sender cleanup/casing, max sender words, adjustable sender column width, fixed sender/subject columns, max subject words/chars, defaults/UI controls, focused tests.
  - [x] Gmail MC URL-routing patch implemented: row/header clicks now expose URLs to central input routing so MC can use direct `QDesktopServices` opening instead of the Reddit helper bridge.
  - [x] Gmail settings Layout cleanup implemented: Display now sits above Position; min/max width and custom padding controls removed; new saves write only `width`.
  - [x] Phase B interaction patch implemented: normal/main Gmail URL queueing now refreshes the helper session ticket and explicitly wakes the Reddit helper runtime/task-scheduler path after a successful ProgramData enqueue.
  - [x] Phase B IMAP action slice implemented: widget dispatches IMAP menu actions using `imap_uid`; IMAP mark-read/archive/spam/trash now use UID STORE/Gmail label operations with focused tests.
  - [x] Phase B action-menu follow-up implemented: Mark as Unread added for REST/IMAP, Archive now has fallback icon coverage, and failed menu actions log sanitized warnings.
  - [x] Phase B action isolation confirmed by runtime: normal/MC link opening works; Mark as Unread, Spam, and Delete work in both builds; Archive alone fails.
  - [~] Phase B Archive follow-up: current Gmail IMAP source research supports removing `\Inbox` via `-X-GM-LABELS` before any hard-named All Mail MOVE fallback; code now follows that order and needs runtime validation.
  - [x] Phase C settings flicker mitigation implemented: Gmail load uses a canonical comprehensive signal-block list, parent Widgets-tab load imports the same list, and Gmail panel/button visibility updates now skip redundant `setVisible(...)` calls.
  - [x] Phase C IMAP Save & Test non-blocking slice implemented: supplied credentials are tested on an IO task, saved only after success, and UI labels/buttons/popups are updated via the UI-thread helper.
  - [x] Phase C backend-specific auth UI fixed: OAuth testing text/Authorize controls are explicitly hidden for IMAP even when settings opens fresh with a hidden parent page.
  - [x] Phase C backend-visibility hardening: when backend service is temporarily unavailable during settings open, Gmail panel visibility now falls back to the backend-combo selection so IMAP/OAuth controls do not both appear.
  - [x] Gmail plan cleanup completed: `Docs/Gmail_Widget_Plan.md` v5.0 now keeps completed history compact and active tasks detailed.
  - [x] Phase D defaults audit first pass implemented: Gmail settings UI now uses a canonical default accessor for user-facing fallback values and save fallbacks.
  - [x] Phase D defaults regression fixed: settings-dialog cached widget defaults are merged with fresh canonical defaults and invalidated when `default_settings.py` changes, preventing stale cache data from hiding new Gmail defaults.
  - [x] Phase C bucket flicker mitigation: shared bucket toggles skip no-op visibility work; Gmail bucket-state writes are skipped when unchanged.
  - [x] Phase C bucket flicker audit: removed the failed Gmail hidden-bucket pre-polish/deferred-persistence attempt because it temporarily showed hidden bodies during settings construction, matching the R-18 flicker hazard pattern.
  - [x] Phase C Gmail construction hardening: Gmail backend/auth refresh is queued until after settings construction, styled combo popup-view creation is deferred until popup open, Gmail bucket final visibility is applied after controls are built, and Text Limits controls are split across two aligned rows.
  - [x] Phase C settings dialog creation flicker fixed in live use; extra Backend bucket resolved the Gmail-only bucket-open oddness.
  - [x] Phase C bucket organisation follow-up: Backend content moved into a default-open Backend bucket.
  - [x] Phase D refresh affordance slice implemented: top-right flat refresh icon now uses a more curved arrowless spiral glyph, bounded spinner timer during fetch, click-to-refresh, blank-space double-click refresh parity with Reddit, and hit-rect tests.
  - [x] Phase B/C cache-order follow-up corrected: fetched and cached email lists now preserve backend order instead of unread-first/date-desc sorting.
  - [x] Phase B grouping guard added: `gmail.group_threads` defaults to `False` and grouping remains off until the PayPal/thread behavior can be fixed safely.
  - [x] Phase B/D date display modes implemented: Relative, Numerical, and Words date styles, shown beside the date visibility control and applied to row width measurement.
  - [x] Phase D header parity implementation: Gmail header font/logo now follow Media's sizing relationship, header border uses Media-style inner thickness, and `gmail.header_logo_px_adjust` exists for final px nudging.
  - [ ] Phase D next: runtime-validate spiral glyph/spinner idleness, date display modes, restored IMAP Inbox ordering after manual refresh, Gmail header parity against Media/Spotify/Reddit, Reddit logo adjustment feasibility, and whether the Gmail refresh spiral needs its own px adjustment; run defaults audit; per-element fonts/colours.
  - [x] Phase E first build-script asset audit implemented: required Gmail image assets are manifest-tested, the missing Archive icon asset exists, and normal/MC Nuitka scripts are guarded for `images=images` inclusion.
  - [x] Phase C/D asset and repaint pass implemented: Gmail envelope/read PNG sources are clean 64px transparent black-and-white assets, unread rows select the unread envelope, text-limit word counting ignores punctuation-only separators, Text Limits uses a two-row grid, and Gmail widget same-value setters now skip no-op repaints.
  - [x] Phase E notification sound packaging guardrails implemented: default sound resolver prefers ProgramData with script fallback, normal/MC builds include only `resources/tutuogg.ogg` plus Qt multimedia support, installers ship `tutuogg.ogg` to ProgramData, and build runner preflight fails if the source OGG is missing.
  - [x] Phase E defaults/security audit: Reddit refresh spiral is default-on through canonical defaults/SST exports, Gmail defaults are present for normal and MC, tracked files were checked for Gmail credentials, and Gmail no-auth/no-cache activation no longer requests fade-in.
  - [~] Phase E packaged asset follow-up: standard build Gmail logo was missing at runtime because asset lookup could depend on cwd; Gmail image/action assets now resolve via cwd, executable parent, then module/repo root. Rebuild/runtime validation still required for the normal artifact.
  - [ ] Phase E later: online research for Gmail grouping/sender-swapping; final packaged-build runtime validation for Gmail assets.
  - [~] Phase E resource-use audit: source/log pass confirms transition frames are already spike-prone, so Gmail now defers refresh start and result apply while the parent display is pending/starting/running a transition, skips unchanged-result cache writes/repaints, sends cache writes to IO when ThreadManager is available, keeps refresh timers idle unless refreshing, avoids no-op setter repaints, precomputes header desaturation outside paint, renders stable Gmail content through a DPR-aware content pixmap cache without touching Qt shadow/effect paths, and emits `perf_widgets.log` metrics for Gmail paint/refresh/apply/cache buckets. Remaining target is runtime review of those Gmail buckets with 10 rows and idle-time sound cost.
  - [x] Phase B/D interaction patch implemented: Gmail action-menu clicks keep a live QMenu reference, use a topmost popup, and defer immediate MC focus restoration so the popup can receive clicks.
  - [x] Phase B/D interaction validation: runtime testing confirms Gmail link clicking works in normal and MC, and dot-menu opening/clicking works except Archive effect.
  - [ ] Phase E next: Archive runtime diagnosis, paint/resource profiling, and archive diagnostic harness only if label-removal still fails.
- **REDDIT WIDGET**
  - [x] Refresh spiral click classification fixed: non-link Reddit controls can consume clicks without setting `reddit_handled`, so the main build no longer exits as though a URL was clicked.
  - [x] Refresh spiral now queues a guarded Reddit refresh through the existing fetch path, respects fetch-in-progress, defers refresh start/result apply while parent transitions are pending/starting/running, and defers paint-cache regeneration during transitions when an old cache can be blitted.
  - [ ] Runtime-validate Reddit spiral refresh in normal and MC builds: no link-exit unless a real URL is clicked, one queued refresh after transition idle, spinner stops cleanly.
- Investigate MuteButtonWidget fade-in race with `invalidate_overlay_effects` (~1/10 failure).
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.

## Open Validation
- U-05 MC focus/input matrix: **RESOLVED**, awaiting long-term stability confirmation.
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform (needs log analysis over 50+ rotations).
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Settings destructive-flow checks (reset/import) when touching settings architecture.



### General Risk Assessment — Latent Focus Architecture Issues
These are ticking bombs even if not the U-05 root cause. Fix after U-05 is resolved. Weigh potential shadow corruption causing and breakage from changing these against changes planned. Current architecture works for MC mode.
- [ ] Assess & fix general focus policies on all overlay widgets (Issue 7 — HIGH risk).
- [ ] Assess GL compositor focus policy (Issue 6 — HIGH risk).
- [ ] Assess focus-restore reason consistency (`MouseFocusReason` vs `ActiveWindowFocusReason`) (Issue 2).
- [ ] Assess global Raw Input registration vs per-window (Issue 5).
- [ ] Assess halo focus interactions (Issue 3).
- [ ] Assess activation-refresh contract (does it need explicit focus restore?) (Issue 8).
- [ ] Audit all `setWindowFlag()` calls for post-show safety (Issue 1).

### Exit Criteria
- [x] Harness reproduces the user-reported MC failure: **manual click into SRPSS on secondary display causes keys to be "eaten"**; programmatic focus does not.
- [x] Identify exact Qt widget or focus state that "eats" keys after manual mouse click. **Found**: focus is never restored to `DisplayWidget` after click because `_restore_mc_input_focus()` is dead code.
- [x] Wire `_restore_mc_input_focus()` into `handle_mousePressEvent` after widget click routing (implemented 2026-04-25).
  - Added at 3 return points within `hard_exit/ctrl_mode` branches: context menu click, handled widget click, unhandled interaction click.
  - NOT added to fall-through exit path (app is exiting there, no point).
  - **User manually tested: WORKS** — media keys, `C`, `S` all work after manual click in MC mode.
- [x] Cursor halo side-effect fixed: `widget.raise_()` in `_restore_mc_input_focus` pushed halo behind DisplayWidget. Added `hint.raise_()` at end to re-raise halo after focus restoration. Safe because halo has `WindowDoesNotAcceptFocus`.
- [x] MC focused/unfocused behavior is consistent for media keys and normal control keys.
- [x] Final MC fix preserves: no taskbar entry, no Alt-Tab entry, and topmost/no-fall-behind behavior.
- [ ] Winlogon `S`-works clue is promoted only after MC is solved or the MC root cause clearly requires Winlogon comparison.
- [x] `Docs/Historical_Bugs.md` and `Docs/MEDIAKEYDEBUG.md` updated with final fix documentation.

## Runtime Watchlist
- Settings dialog startup/show/focus regressions.
- Visualizer mode-switch state bleed across shared seams.
- Preset repair/reindex drift from authored payload intent.
- Settings cache stale-read behavior after section/root writes.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`

## Post-U-05 Analysis — Anomalies (2026-04-25)

### Anomaly 1 — Mute Button Fade-In ~1/10 Failure [Still Occurs]

**Symptom**: Global audio mute button (MuteButtonWidget) occasionally fails to fade in during secondary startup stage.

**Root cause identified**: Race condition between `MuteButtonWidget._start_widget_fade_in()` and `invalidate_overlay_effects()`.

**Mechanism**:
1. Mute button used its own bespoke `QGraphicsOpacityEffect` + `QVariantAnimation` fade, NOT `ShadowFadeProfile`.
2. The bespoke animation used `_fade_anim` as its attribute name, but `_invalidate_widget_effect()` only checked for `_shadowfade_anim` / `_shadowfade_shadow_anim` before recreating effects.
3. During the ~1700ms fade window, `invalidate_overlay_effects()` could fire. Since the animation guard didn't recognize `_fade_anim`, `_recreate_effect()` was called mid-animation.
4. `_recreate_effect()` replaced the `QGraphicsOpacityEffect` while the animation was still updating the old (now destroyed) effect via its closure. The new effect was never updated.

**Fix applied (2026-04-25)**: Replaced bespoke fade implementation with `ShadowFadeProfile.start_fade_in(..., apply_shadow_on_finish=False, on_finished=...)`. This gives the mute button the same protections all other overlay widgets have:
- Stops existing animations before starting new ones
- Uses `_shadowfade_anim` which `_invalidate_widget_effect()` recognizes and protects
- Includes `Shiboken.isValid()` guard in `valueChanged` to gracefully handle destroyed effects
- No drop shadow is applied (preserving the original design constraint)

**File**: `widgets/mute_button_widget.py` `_start_widget_fade_in()`


## Idea Box
1. Add a lightweight “doc drift” check that flags stale references between `Spec.md`, `Index.md`, and `Current_Plan.md`.
2. Add a tiny harness smoke command list to this file so recurring investigations are one-command repeatable.
3. Deferred Winlogon-targeted automation pass: compare `S` path vs media path evidence only after MC focused behavior is understood.
4. Add a transition-distribution logger that counts transition types over a session and reports skew at shutdown.
5. Asses what use "card_height.py" is and why we do not simply have a logical centralized sizing system for all visualizer modes while preventing bleed or complex interactions? Basing it on multipliers is bizarre.
6. [x] For Spline Curve/DevCurve, specular now fades out while idle/paused and fades back in when playback resumes using the runtime specular alpha multiplier rather than shader reshaping or preset value enforcement.

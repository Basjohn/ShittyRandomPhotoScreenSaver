# Current Plan

Last updated: 2026-04-29

This file tracks active work and near-term validation.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as the authored preset source tree.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.

## Active Priorities
- Keep settings/dialog stability and startup behavior regression-free while preserving custom styling.
- **U-05 RESOLVED (2026-04-25)**: MC Keyboard Focus / Ctrl Halo Runtime Input Family fixed via wiring dead code `_restore_mc_input_focus`.
- **GMAIL WIDGET**: Plan v3.5 active in `Docs/Gmail_Widget_Plan.md` (2026-04-29).
  - [x] Foundation/dev gate/settings/UI/sound implemented.
  - [x] Phase A structural polish implemented: nine-position enum, single `gmail.width`, Media-style content margins, measured header frame.
  - [x] Phase B deep-link foundation implemented: `core/gmail/gmail_deeplinks.py`, IMAP `open_url`, Gmail account slot, decimal `X-GM-THRID` to lowercase hex, focused tests.
  - [x] Phase C first safety pass implemented: widget async fetch generation/cancel guard, stale results ignored after cleanup/settings changes, `gmail_imap.py` hot-path `re` import removed.
  - [x] Phase B/D screenshot polish slice implemented: row clicks prefer `email.open_url`, action menu click has priority in widget tests, vertical ellipsis indicator, contraction-safe subject title case, sender cleanup/casing, max sender words, adjustable sender column width, fixed sender/subject columns, max subject words/chars, defaults/UI controls, focused tests.
  - [x] Gmail MC URL-routing patch implemented: row/header clicks now expose URLs to central input routing so MC can use direct `QDesktopServices` opening instead of the Reddit helper bridge.
  - [x] Gmail settings Layout cleanup implemented: Display now sits above Position; min/max width and custom padding controls removed; new saves write only `width`.
  - [ ] Phase B interaction next: normal/main Gmail URLs are queued to the ProgramData helper bridge but do not reliably open after exit; inspect helper/task-scheduler/queue consumption using the Reddit path as the reference.
  - [x] Phase B IMAP action slice implemented: widget dispatches IMAP menu actions using `imap_uid`; IMAP mark-read/archive/spam/trash now use UID STORE/Gmail label operations with focused tests.
  - [ ] Phase B actions next: runtime-validate IMAP actions against real Gmail and harden folder/label discovery if Gmail rejects the current label operations.
  - [ ] Phase C next: fix Gmail settings flicker regression using `Docs/Historical_Bugs.md` R-18 and flicker harnesses; make Gmail IMAP Save & Test non-blocking; add backend helper to test supplied credentials before saving; harden OAuth callback server cleanup.
  - [ ] Phase D next: finish header parity visual/manual validation against Media/Spotify/Reddit; replace jagged Gmail envelope assets with clean black-and-white PNGs; add refresh button/blank-space double-click refresh; add date display mode; plan/implement thread collapse; run defaults audit; per-element fonts/colours; finish settings bucket organisation without duplicate controls.
  - [ ] Phase E later: resource-use audit for over-painting/over-updating/per-tick waste; stretch investigation for opening Gmail/Reddit links on the browser window/process on lowest-index monitor with safe fallback.
  - [ ] Phase B/D interaction next: MC subject links work, but vertical action menus do not open and briefly freeze cursor input; diagnose popup/focus separately using `/logs`.
  - [ ] Phase E next: secure-desktop/manual URL validation, paint/resource profiling, repo credential hygiene, archive deprecation note.
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

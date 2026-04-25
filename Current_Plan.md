# Current Plan

Last updated: 2026-04-26

This file tracks active work and near-term validation.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as the authored preset source tree.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.

## Active Priorities
- Keep settings/dialog stability and startup behavior regression-free while preserving custom styling.
- **U-05 RESOLVED (2026-04-25)**: MC Keyboard Focus / Ctrl Halo Runtime Input Family fixed via wiring dead code `_restore_mc_input_focus`.
- **GMAIL WIDGET**: See `Docs/Gmail_Widget_Plan.md` for full scoped implementation plan (8 phases + 4 appendices). Adapt archive code to production as dev-gated overlay widget with secure-desktop URL launching, DPAPI token encryption, settings UI, and OGG notification sound. Plan covers credential hygiene, paint performance guardrails, transition deferral, and AV false-positive avoidance.
- Investigate MuteButtonWidget fade-in race with `invalidate_overlay_effects` (~1/10 failure).
- Investigate transition random mode distribution skew report (Diffuse 60-70% observed).
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.

## Open Validation
- U-05 MC focus/input matrix: **RESOLVED**, awaiting long-term stability confirmation.
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform (needs log analysis over 50+ rotations).
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Settings destructive-flow checks (reset/import) when touching settings architecture.

## Focused Active Plan — Media Key / Input Matrix (U-05)
- Objective: make MC runtime key behavior perfect and reliable first, then use that understanding to approach Winlogon separately.
- Constraint: no runtime/input behavior edits until matrix evidence + code-path analysis converge on one primary resolution candidate.
- Current truth: **hardware ingress validator reproduces the real-world MC failure**. Manual mouse click into SRPSS on a secondary display causes keys to be "eaten"; programmatic `SetForegroundWindow` and `SendInput` clicks do NOT.
- **Speculative hypothesis**: the bug may be in Qt-side focus/activation/mouse side effects, not Windows focus routing. Requires validation by isolating specific widgets/event filters that capture input after manual click.
- Priority order: MC real-world repro fidelity first; Winlogon investigation is deferred until MC behavior is understood and reliable.
- Non-negotiable MC window guardrails: never appear in the normal taskbar, never appear in Alt-Tab, and never fall behind other windows.
- Normal-window or normal-build comparisons are not candidate fixes. They are already known to handle keys, but they do not satisfy MC requirements.

### Runtime Matrix To Lock
- MC runtime focused after **manual** in-window click on Display 1: media keys "eaten", control keys fail. Defocusing to Display 0 restores keys.
- MC runtime focused after **programmatic** focus (`SetForegroundWindow`): keys work. This does NOT reproduce the bug.
- Normal Windows Preview runtime: all keys work.
- Normal Winlogon runtime: media keys fail, most keys fail, `S` works. This is tracked as a later phase, not the next active target.

### Phase 1 — Evidence Freeze (No-Edit)
- [x] Capture a faithful MC-only reproduction: manual click into SRPSS on Display 1 causes media keys and hotkeys to be "eaten". Defocusing to Display 0 restores keys.
- [x] Capture two-phase MC evidence: unfocused keys work, manual click into SRPSS causes failure, programmatic focus does NOT cause failure.
- [x] Capture logs (`--debug`) for MC key batches via `hardware_ingress_validator.py`.
- [x] Record focus owner transitions at each MC step (before manual click, after manual click, after programmatic focus).
- [x] Archive MC evidence bundles in `logs/hardware_ingress/` with timestamps.

### Phase 2 — Harness Build Plan (Automation-First)
- [x] Add a media-key matrix runner harness (sequence-driven, repeatable).
- [x] Add a paired native-message probe harness (HWND + message route observer).
- [x] Ensure harness supports deterministic focused-state transitions:
  - focus SRPSS window
  - click SRPSS content
  - replay key batches after each transition
- [x] Emit machine-readable matrix output (`json`) plus readable summary (`md`).
- [x] Split probe paths so results are not conflated:
  - Qt synthetic key path (`SendInput`)
  - injected native `WM_APPCOMMAND` path
  - transition hotkey path (`C`)
- [x] Ingest both `screensaver.log` and `screensaver_verbose.log` for native debug signals (`[WIN_APPCOMMAND]`, `[RAW_INPUT]`).
- [x] Add MC runtime contract guard (window/flag/display/compositor checks) so harness fails when MC surface is not actually built.
- [x] Add live-profile parity mode (elevated execution path) and explicit profile mode reporting.
- [x] Block invalid `focused_clicked` samples when focus is stolen during click setup (mark as blocked with explicit reason instead of scoring false failures).
- [x] Add hardware-ingress validation layer (`tools/hardware_ingress_validator.py`) — correlates real physical key events with SRPSS log responses, separate from synthetic injection.
- [x] Add one-command compare runner for focus-policy A/B (`tools/media_key_matrix_compare.py`).
- [x] Add deterministic click-safe targeting so `focused_clicked` can be exercised without browser/overlay focus diversion.
- [x] Add mirrored-profile safety guard to disable Reddit click surfaces in harness-owned profiles during click scenarios.
- [x] Add an MC reality mode that does not rely on synthetic success as proof: `tools/hardware_ingress_validator.py` targets real focused window, captures OS-level hardware ingress via WH_KEYBOARD_LL, and correlates against SRPSS internal logs.
- [x] Add two-phase MC reality mode (`focus_transition`) for unfocused-working vs focused-failing capture.
- [x] Add a guarded splash-window flag experiment for harness diagnosis.
- [x] Treat splash-window mode as ruled out for product behavior unless repeated focus-change stability is proven.
- [x] Add native HWND style/ex-style reporting to the MC reality harness.

### Phase 3 — Code Analysis Pass (Still No Behavior Edits)
- [x] Trace media-key ingress path in `rendering/display_native_events.py`.
- [x] Trace Raw Input lifecycle in `core/windows/media_key_rawinput.py`.
- [x] Trace focus/interaction gating in `rendering/display_input.py` and `rendering/input_handler.py`.
- [x] Diff launch/runtime surface assumptions between `main.py` and `main_mc.py`.
- [x] Build an MC-only flow map: focus state -> message ingress -> dispatch -> handler outcome.
- [x] Explain why the real-world focused MC state fails when synthetic/injected focused MC samples pass: **manual mouse click into SRPSS causes the failure; programmatic focus does not.** The bug is in the manual click/activation path, not focus ownership itself.
- [ ] Map the native activation/focus behavior of MC `Qt.Tool` windows while preserving `WS_EX_TOOLWINDOW`/topmost/no-taskbar/no-Alt-Tab guardrails.
- [x] Investigate why clicking MC changes physical key routing even when the native guardrail style remains tool/topmost: **manual click alters Qt input handling state (likely widget focus or mouse-grab side effects) while programmatic SetForegroundWindow does not.**
- [ ] Verify any candidate fix keeps `WS_EX_TOOLWINDOW`/topmost semantics and does not introduce `WS_EX_APPWINDOW` or normal taskbar/Alt-Tab behavior.
- [x] Re-run divergence analysis only on valid `focused_clicked` samples (no focus theft); previous failing rows were contaminated by external foreground takeover.
- [x] Extend analysis to physical hardware ingress parity vs synthetic/injected paths using `hardware_ingress_validator.py`.
  - Finding: PowerToys remaps PgUp/PgDn to Volume Up/Down, causing media keys to appear as `injected=true` in `WH_KEYBOARD_LL`. Validator now accounts for this.
  - Finding: **Manual click focus reproduces the bug** (C fails). Programmatic focus does NOT reproduce it (C works).
  - Implication: fix must target the manual click/activation side effects, not focus routing.
- [x] Validate mirrored-safe strict/realistic A/B parity after focus-steal fix and click safety guard.

### Phase 4 — Resolution Gate (Edit Permission Boundary)
- [x] Propose exactly one primary fix direction and one fallback direction.
  - **Primary**: Wire existing `_restore_mc_input_focus()` into `handle_mousePressEvent` after widget click routing (MC mode, non-exit clicks). This function already implements `raise_()`, `activateWindow()`, `requestActivate()`, and `setFocus()` — it was just never called.
  - **Fallback**: If wiring `_restore_mc_input_focus` causes shadow flicker or other side effects, replace it with a more targeted `QApplication.setActiveWindow(widget)` + `widget.setFocus(Qt.ActiveWindowFocusReason)` call.
- [x] Expected matrix change: `focused_clicked` row should flip from FAIL to PASS for media keys, `C`, and `S`.
- [ ] Do not implement until user explicitly approves after risk review.

### H1 Test — Disable Child Widget Focus (FAILED — Reverted)
- [x] Implement `_h1_disable_child_widget_focus()` in `rendering/display_setup.py`.
- [x] Call it at end of `setup_widgets()` so all descendant QWidget instances get `Qt.NoFocus`.
- [x] **User manually tested**: media keys still fail after manual click.
- [x] **Reverted**: removed function and call from `display_setup.py`.
- **Finding**: H1 hypothesis (child widget focus theft) is **incorrect**.
- **Side effect**: shadow corruption on media/Reddit widgets became frequent (was occasional). Root cause: H1 destabilized Qt's focus tree, causing more `focusInEvent`/`focusOutEvent` cycles, which triggered more `invalidate_overlay_effects` calls and corrupted `QPixmapCache`.

### Critical Discovery — Dead Code `_restore_mc_input_focus`
- [x] Grepped entire codebase: `_restore_mc_input_focus()` is **defined** in `rendering/display_input.py` but **NEVER CALLED** in the main application.
- **Implication**: The function added as part of a previous "final fix" was never wired into `handle_mousePressEvent`. After ANY widget click in MC mode, focus is **never restored** to `DisplayWidget`.
- **This is the root cause**: Manual click leaves focus on the clicked child widget (or its native window). Media keys are delivered to the child widget, which does not handle them. `SetForegroundWindow` bypasses this by resetting the top-level window focus.
- **Next step**: Wire `_restore_mc_input_focus()` into `handle_mousePressEvent` after widget click routing, NOT modify child focus policies.

### Focus-State Logging (Proposed Diagnostic)
- [ ] Log `QApplication.focusWidget()`, `QApplication.activeWindow()`, native `GetFocus()`/`GetForegroundWindow()` after every mouse click in MC mode.
- [ ] Log focus widget class name and object name to confirm which widget "eats" keys.
- [ ] Add to verbose log only; no behavior change.

### General Risk Assessment — Latent Focus Architecture Issues
These are ticking bombs even if not the U-05 root cause. Fix after U-05 is resolved.
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

## Post-U-05 Analysis — Two Anomalies (2026-04-25)

### Anomaly 1 — Mute Button Fade-In ~1/10 Failure

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

### Anomaly 2 — Diffuse Transition Over-Represented at 60-70%

**Code audit result**: The random transition selection uses `random.choice(candidates)` from a uniformly populated list. Mathematically impossible to produce 60-70% for any single item with the intended pool size.

**Selection paths checked**:
- Engine `_prepare_random_transition_if_needed()` → `random.choice(candidates)` from `available` list
- Factory `_pick_random_transition()` → `random.choice(candidates)` from `available` list
- Both use Python stdlib `random` with no seeding manipulation

**Default pool state discrepancy**:
- `core/settings/default_settings.py` canonical defaults: `transitions.type='Slide'`, `random_always=False`, pool has `Blinds=False`, `Crossfade=False`
- `core/settings/presets.py` preset defaults: pool has ALL items `True`
- This means fresh installs vs preset-restored installs have different default pools.

**Likely explanations**:
1. **Perception bias**: Diffuse is visually distinctive (block-grid dissolve). Human memory overweight distinctive events.
2. **Small actual pool**: User's `settings_v2.json` may have fewer pool entries enabled than expected. `to_bool()` converts malformed values to `True`, but missing keys default to `True`. Unlikely to shrink pool accidentally.
3. **Non-random mode active**: Default `transitions.type='Slide'` with `random_always=False` means NO random selection at all — it always uses Slide. User must have explicitly enabled random mode.
4. **Insufficient sample size**: 10-20 observations is not statistically significant for an 11-item uniform distribution.

**Debug message assessment — "Requested X but instantiating Y"**:
- The `INFO` log message from `TransitionFactory._log_selection()` is **purely informational, safe, and performant**.
- When `random_mode=True`, `requested` = `transitions.type` (user's last manual selection, e.g. 'Block Puzzle Flip'), `actual` = `transitions.random_choice` (the resolved random pick).
- The factory always reads `transitions.random_choice` before instantiation. The `requested` string is only used for logging, never for caching or transition creation.
- **No "incorrect caching" risk**: `SettingsManager.set('transitions.random_choice')` is synchronous in-memory; the factory reads the current value. There is no stale cache.
- **Minor inefficiency**: `_prepare_random_transition_if_needed()` is called twice per timer rotation (once in `_on_rotation_timer`, once inside `_show_next_image`), causing one wasted RNG call. Harmless but could be cleaned up.
- **Minor UX note**: The log wording "Requested X but instantiating Y" sounds like a mismatch/bug. Rewording to "Random mode: resolved 'X' → 'Y'" would be clearer.

**Recommendation**: Check `screensaver.log` for the line `Random transition choice for this rotation: {choice}` over 50+ rotations to confirm actual distribution. If Diffuse is genuinely >30%, the pool is smaller than expected or there's a non-code factor (e.g. transition instantiation failing and falling back to a default — but fallback is Crossfade, not Diffuse).

## Idea Box
1. Add a lightweight “doc drift” check that flags stale references between `Spec.md`, `Index.md`, and `Current_Plan.md`.
2. Add a tiny harness smoke command list to this file so recurring investigations are one-command repeatable.
3. Deferred Winlogon-targeted automation pass: compare `S` path vs media path evidence only after MC focused behavior is understood.
4. Add a transition-distribution logger that counts transition types over a session and reports skew at shutdown.

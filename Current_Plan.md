# Current Plan

Last updated: 2026-04-25

This file tracks active work and near-term validation.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as the authored preset source tree.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.

## Active Priorities
- Keep settings/dialog stability and startup behavior regression-free while preserving custom styling.
- Resolve U-05 (MC Keyboard Focus / Ctrl Halo Runtime Input Family).
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.

## Open Validation
- Runtime confirmation for U-05 MC focus/input matrix.
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Settings destructive-flow checks (reset/import) when touching settings architecture.

## Focused Active Plan — Media Key / Input Matrix (U-05)
- Objective: make MC runtime key behavior perfect and reliable first, then use that understanding to approach Winlogon separately.
- Constraint: no runtime/input behavior edits until matrix evidence + code-path analysis converge on one primary resolution candidate.
- Current truth: the harness has not fully reproduced the user's real-world MC failure yet. It has proven that synthetic/injected paths can work when setup is controlled, and that the remaining gap is the real MC focus/physical-input transition under the guardrail window style.
- Priority order: MC real-world repro fidelity first; Winlogon investigation is deferred until MC behavior is understood and reliable.
- Non-negotiable MC window guardrails: never appear in the normal taskbar, never appear in Alt-Tab, and never fall behind other windows.
- Normal-window or normal-build comparisons are not candidate fixes. They are already known to handle keys, but they do not satisfy MC requirements.

### Runtime Matrix To Lock
- MC runtime focused after in-window click: media keys fail, control keys fail.
- Normal Windows Preview runtime: all keys work.
- Normal Winlogon runtime: media keys fail, most keys fail, `S` works. This is tracked as a later phase, not the next active target.

### Phase 1 — Evidence Freeze (No-Edit)
- [ ] Capture a faithful MC-only reproduction that matches the user's failure: focused SRPSS, physical media key fails, normal control keys fail, focus-loss recovers media keys.
- [ ] Capture two-phase MC evidence: physical keys while MC is unfocused and working, then the same physical keys after MC is brought into focus and failing.
- [ ] Capture logs (`--debug`) for the exact MC key batches only after the harness can represent the real failure state.
- [ ] Record focus owner transitions at each MC step (before click, after click, after focus-loss, after alt-tab).
- [ ] Archive one MC evidence bundle in `/logs` with timestamp, profile mode, focus state, and whether the sample used physical or synthetic keys.

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
- [ ] Add hardware-ingress validation layer (separate from synthetic injection).
- [x] Add one-command compare runner for focus-policy A/B (`tools/media_key_matrix_compare.py`).
- [x] Add deterministic click-safe targeting so `focused_clicked` can be exercised without browser/overlay focus diversion.
- [x] Add mirrored-profile safety guard to disable Reddit click surfaces in harness-owned profiles during click scenarios.
- [ ] Add an MC reality mode that does not rely on synthetic success as proof: target real focused window, wait for user/hardware media key input or capture OS-level hardware ingress, and compare against internal logs.
- [x] Add two-phase MC reality mode (`focus_transition`) for unfocused-working vs focused-failing capture.
- [x] Add a guarded splash-window flag experiment for harness diagnosis.
- [x] Treat splash-window mode as ruled out for product behavior unless repeated focus-change stability is proven.
- [x] Add native HWND style/ex-style reporting to the MC reality harness.

### Phase 3 — Code Analysis Pass (Still No Behavior Edits)
- [x] Trace media-key ingress path in `rendering/display_native_events.py`.
- [x] Trace Raw Input lifecycle in `core/windows/media_key_rawinput.py`.
- [x] Trace focus/interaction gating in `rendering/display_input.py` and `rendering/input_handler.py`.
- [x] Diff launch/runtime surface assumptions between `main.py` and `main_mc.py`.
- [ ] Build an MC-only flow map: focus state -> message ingress -> dispatch -> handler outcome.
- [ ] Explain why the real-world focused MC state fails when synthetic/injected focused MC samples pass.
- [ ] Map the native activation/focus behavior of MC `Qt.Tool` windows while preserving `WS_EX_TOOLWINDOW`/topmost/no-taskbar/no-Alt-Tab guardrails.
- [ ] Investigate why clicking MC changes physical key routing even when the native guardrail style remains tool/topmost.
- [ ] Verify any candidate fix keeps `WS_EX_TOOLWINDOW`/topmost semantics and does not introduce `WS_EX_APPWINDOW` or normal taskbar/Alt-Tab behavior.
- [x] Re-run divergence analysis only on valid `focused_clicked` samples (no focus theft); previous failing rows were contaminated by external foreground takeover.
- [ ] Extend analysis to physical hardware ingress parity vs synthetic/injected paths.
- [x] Validate mirrored-safe strict/realistic A/B parity after focus-steal fix and click safety guard.

### Phase 4 — Resolution Gate (Edit Permission Boundary)
- [ ] Propose exactly one primary fix direction and one fallback direction.
- [ ] Show which matrix cells each fix is expected to change.
- [ ] Do not implement until expected outcomes are explicitly mapped and risk-reviewed.

### Exit Criteria
- [ ] Harness reproduces the user-reported MC failure, not just synthetic-path passes.
- [ ] MC focused/unfocused behavior is consistent for media keys and normal control keys.
- [ ] Final MC fix preserves: no taskbar entry, no Alt-Tab entry, and topmost/no-fall-behind behavior.
- [ ] Winlogon `S`-works clue is promoted only after MC is solved or the MC root cause clearly requires Winlogon comparison.
- [ ] `Docs/Historical_Bugs.md` and `Docs/MEDIAKEYDEBUG.md` updated with final before/after matrix.

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

## Idea Box
1. Add a lightweight “doc drift” check that flags stale references between `Spec.md`, `Index.md`, and `Current_Plan.md`.
2. Add a tiny harness smoke command list to this file so recurring investigations are one-command repeatable.
3. Deferred Winlogon-targeted automation pass: compare `S` path vs media path evidence only after MC focused behavior is understood.

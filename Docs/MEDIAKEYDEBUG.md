# Media Key Debug Notes

Last updated: 2026-04-24

Operational playbook for media-key and keyboard-routing regressions.

## 0. Current Framing (2026-04-24)

MC comes first. MC must remain a screensaver-style surface: no normal taskbar entry, no Alt-Tab entry, and no falling behind other windows. Normal-window tests are not useful fix candidates because normal preview/exe behavior is already known to handle keys and does not satisfy the MC contract.

The harness has not fully reproduced the user's real-world MC failure yet; it has shown that synthetic/injected probes can pass in controlled focused-MC samples and that the live failure is tied to the real focus/physical-input transition.

What the harness currently proves:

1. `SendInput`/Qt key path works while focused (`C` + synthetic media VK route through `InputHandler`).
2. Injected `WM_APPCOMMAND` path also reaches `display_native_events` in focused MC runs.
3. Valid focused-click samples can pass when the click target is controlled and Reddit/browser focus diversion is removed.

What this does not prove:

1. It does not reproduce the physical-key MC failure the user sees.
2. It does not prove media-key hardware ingress is reliable while SRPSS owns focus.
3. It does not justify changing MC to a normal/taskbar/Alt-Tab window style.
4. It does not justify moving to Winlogon before MC behavior is understood.

What is still unresolved:

1. Real hardware media-key ingress behavior under the user repro (focused MC click path, real desktop state).
2. Why normal control keys fail in the same focused MC state.
3. Why the MC `Qt.Tool`/topmost guardrail window changes key routing after click/focus interaction.
4. Winlogon asymmetry where `S` works while media keys fail. This is deferred until MC is stable or the MC investigation needs it.

Newest MC observation (2026-04-24):

1. When MC starts unfocused, physical keys can work.
2. Bringing the MC window into focus is the transition that makes keys fail.
3. The useful capture is therefore two-phase: unfocused physical keys first, click/focus SRPSS, then the same physical keys again.
4. Splash-window experiment is ruled out as a fix: it shows the same issue and adds worse focus instability after focus changes.

## 1. Current Repro Matrix (Source of Truth)

Validated user matrix (2026-04-23):

1. **MC runtime (`main_mc.py`) after clicking into SRPSS window**
   - Media keys fail while SRPSS is focused.
   - Media keys work again when focus shifts to another app.
   - Normal control keys do not work in this mode.
2. **Normal mode, Windows Preview runtime**
   - All keys work, including media keys.
3. **Normal mode, Winlogon runtime**
   - Media keys fail.
   - Most non-media keys fail.
   - `S` still works and opens Settings.

This is a runtime/focus split problem, not a single-key bug.

Active priority: solve MC focused behavior first. Winlogon is a separate runtime surface and should not steer the next code edit until MC behavior is perfect and reproducible.

## 2. Hard Constraints (Do Not Violate)

- Do not apply routing edits until the MC failure is reproducible under harness/probe evidence.
- Do not collapse MC/Preview/Winlogon into one assumed behavior model.
- Do not ship a "works in preview" fix as proof for Winlogon or focused-MC behavior.
- Do not use normal-window/taskbar/Alt-Tab behavior as an MC fix path.
- Preserve MC window guardrails: no taskbar entry, no Alt-Tab entry, topmost/no-fall-behind.
- Do not treat synthetic or injected probe success as a reproduction of physical-key success.
- Preserve existing archived sub-fixes unless replacement behavior is proven across the full matrix.

## 3. Primary Investigation Questions

1. Which event ingress paths are active per runtime (`WM_APPCOMMAND`, `WM_KEYDOWN/UP`, Raw Input)?
2. What focus/foreground transitions change media-key behavior in MC?
3. Why do physical media/control keys fail in user MC while synthetic/injected harness probes pass?
4. Is focus-loss recovery in MC a focus ownership change, a message-route change, or both?
5. Why does `S` survive in Winlogon while media keys fail? Deferred until MC is understood.

## 4. No-Edit Investigation Checklist (Live)

- [ ] Capture baseline MC logs for the exact user sequence: focus SRPSS, physical media key, physical control key, external focus recovery.
- [ ] Trace focused vs unfocused MC transitions (before click, after click, after focus-loss, after alt-tab).
- [ ] Confirm which window receives native messages in each MC state.
- [ ] Verify whether Raw Input registration is live and still dispatching in each MC state.
- [ ] Confirm native style/ex-style remains guardrail-compliant (`WS_EX_TOOLWINDOW`, topmost, no taskbar/Alt-Tab) for every candidate path.
- [ ] Produce one MC side-by-side matrix artifact (state x key family x ingress path x observed result).
- [ ] Freeze root-cause hypothesis only after matrix + probe agreement (no code edits before this step).

## 5. Automation Harness Status + Next Up

Completed:

- [x] Repeatable matrix runner (`tools/media_key_matrix_harness.py`).
- [x] Focused-state scenarios for primary path (`focused_idle`, `focused_clicked`).
- [x] Separate probes for:
  - Qt synthetic key route (`SendInput`)
  - injected `WM_APPCOMMAND` route
  - transition key route (`C`)
- [x] Dual log ingestion (`screensaver.log` + `screensaver_verbose.log`) with JSON + Markdown reports.
- [x] MC runtime contract validation (window class/flag + display creation + GL compositor creation + show_on_screen).
- [x] Live-profile parity execution path (requires elevated run outside sandbox).
- [x] Safe-click harness guard for mirrored/isolated profiles:
  - disables `widgets.reddit.enabled`, `widgets.reddit.exit_on_click`, and `widgets.reddit2.enabled`
  - keeps focused-click automation from triggering Reddit interaction during tests.

Latest live-parity finding (2026-04-23):

- `focused_idle`: Qt media pass, AppCommand pass, `C` pass.
- `focused_clicked`: initially showed Qt media fail, AppCommand pass, `C` fail.
- Follow-up evidence review: these failing `focused_clicked` rows were contaminated by focus theft during click prep (external browser foreground), so they are not valid focused-MC samples.
- Harness now blocks/labels such rows as invalid (`focused_clicked_unstable_focus_or_overlay_focus_steal`) instead of treating them as real key-route failures.
- With edge-first click targeting and invalid-row blocking in place, repeated live-profile runs now produce valid `focused_clicked` samples that pass all probes (Qt media, native appcommand, native key-message `C`, transition `C`) in both strict and realistic focus policies.
- Conclusion update: the earlier `focused_clicked` fail signature was a harness contamination artifact, not yet proof of a persistent focused-MC app-path failure.
- Mirrored safe A/B run (`2026-04-23 22:31`) also passed all focused scenarios under both strict and realistic policies, with scenario validity preserved.

Latest probe extension (2026-04-23):

- Added native key-message probe (`WM_KEYDOWN/UP` for `C`).
- In live parity `focused_clicked`: native key-message `C` probe passes while synthetic `SendInput` `C` path fails.
- Interpretation update: post-click failure appears tied to synthetic/foreground input ingress path, not the downstream `C` handler itself.

Next harness upgrades (required for MC diagnosis):

- [ ] Add a Windows message observer companion harness to capture:
  - active HWND, foreground window,
  - native message IDs (`WM_APPCOMMAND`, `WM_INPUT`, `WM_KEYDOWN/UP`),
  - dispatch outcomes.
- [x] Add deterministic click-safe targeting for focused MC runs so `focused_clicked` stays on SRPSS and does not trigger browser foreground diversion.
- [ ] Add MC hardware-path validation mode (do not rely only on synthetic injection) and compare against injected-native probes.
- [x] Add two-phase MC reality mode (`focus_transition`) to capture unfocused-working vs focused-failing behavior in one report.
- [x] Test the existing splash-window flag path as a diagnostic only; do not treat it as a fix.
- [x] Add native HWND style/ex-style dumps to the reality harness.
- [ ] Add a focused-MC external-focus recovery scenario for contrast.
- [ ] Research and map the native Win32/Qt activation contract for MC `Qt.Tool` windows while preserving the existing no-taskbar/no-Alt-Tab/topmost contract.
- [ ] Defer Winlogon-oriented probe capture until MC behavior is reliable.
- [ ] Add post-click native key-message correlation probe (`WM_KEYDOWN`/`WM_SYSKEYDOWN` path evidence) to explain why `C` fails after click while AppCommand still passes.

Quick automation commands:

1. Single run (focused MC):
   - `python tools/media_key_matrix_harness.py --launch mc --profile-mode live --focus-policy realistic --scenarios focused_idle,focused_clicked`
2. Safer mirrored run (recommended when click scenarios are included):
   - `python tools/media_key_matrix_harness.py --launch mc --profile-mode mirrored --focus-policy realistic --scenarios focused_idle,focused_clicked`
3. A/B compare (strict vs realistic):
   - `python tools/media_key_matrix_compare.py --launch mc --profile-mode mirrored --policies strict,realistic --scenarios focused_idle,focused_clicked`
4. Two-phase MC reality capture:
   - `python tools/media_key_reality_harness.py --profile-mode mirrored --scenario focus_transition --manual-focus-seconds 8 --observe-seconds 12`

## 6. Code Surfaces To Analyze First

- `rendering/display_native_events.py`
- `core/windows/media_key_rawinput.py`
- `rendering/display_input.py`
- `rendering/input_handler.py`
- Runtime entry/launch-path differences in `main.py` and `main_mc.py`

## 7. Resolution Acceptance Criteria

- MC-focused failure is reproduced by the harness or by an automated observer-backed workflow using physical/hardware ingress evidence.
- MC focused/unfocused transitions no longer change media-key or normal-control-key reliability.
- Fix does not switch MC to splash semantics unless repeated focus-change behavior is proven stable.
- Winlogon runtime media-key behavior is handled as a separate follow-up once MC is stable.
- Historical bug entry (`U-05`) updated with before/after matrix and retained guardrails.

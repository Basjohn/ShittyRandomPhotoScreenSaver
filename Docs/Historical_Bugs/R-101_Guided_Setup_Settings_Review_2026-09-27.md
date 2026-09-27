# R-101 — Guided Setup / Settings Review 2026-09-27: Mechanisms Behind the Defects

**Status:** SOLVED IN CODE (2026-09-27). The Guided Setup implementation plan closed on the same day; current
behaviour is in `Docs/Reference/Guided_Setup.md`, open physical acceptance at the end of that file. This record keeps
the mechanisms so they are not reintroduced.

## Defects and their mechanisms

| Symptom | Mechanism | Fix / bar |
| --- | --- | --- |
| The wizard saved as you clicked; entering the last page "saved" | `SettingsManager.set` persists and publishes on every call; wizard pages wrote the store directly | `ui/onboarding/draft.py:SettingsDraft`; only Finish (or Keep Changes) commits. `tests/test_onboarding_flow.py::test_wizard_never_saves_until_finish` |
| Arrange Apply undid changes made on other pages | Apply replaced the whole `widgets` map with the editor's stale snapshot (lost update) | merge onto the current base; arrange model merge test |
| The Transitions list crawled while merely hovered | a focusable `QCheckBox` item widget took focus on hover inside Settings; the view made the row current and scrolled to it | row checkboxes are `NoFocus`; offscreen subprocess bar that fails without the fix |
| Seams at rounded corners on buttons, buckets, lists, the content area and popups | Qt style sheets draw rounded borders as separate edge/corner segments whose antialiased ends composite twice; themes use translucent border colours | borders painted as one `QPainterPath` (`ui/widgets/outlined_button.py`, `ui/widgets/continuous_border.py`); zoom-check on a translucent theme |
| The whole Settings stylesheet failed to build | a bare `%` inside a `%`-formatted QSS template (in a comment) | no `%` in those templates |
| Popups looked unthemed (dark text on dark, generic buttons) | a popup is its own top-level window and never inherits the Settings stylesheet | `StyledPopup` applies the Settings root stylesheet and `PopupSurface`; test in `tests/test_continuous_border.py` |
| Circle checkboxes nearly invisible on light themes | the indicators were fixed white SVGs | theme builder recolours them for dark-text themes |
| Previews blurry at 2x DPR | sheet cut-outs were downscaled, then Settings upscaled small previews to fill the box | native-size cut-outs, 2x renders, `ImagePanel(upscale=False)` |
| An edit made just before closing Settings could be lost | the Widgets tab had no `flush_pending_changes` for its 200 ms save batching | flush on close; one live coalescing timer |
| Every default change regenerated three files and blocked builds until done | checked-in "derived" copies of the defaults (`defaults_snapshot.json`, two `.sst`) that nothing at runtime read | copies retired; readers use the SSOT; the authority audit rejects revived copies |
| Redundant timers | `singleShot(0)` second scroll resets (a synchronous `setValue(0)` already survives the layout pass) and resize/move geometry save timers (close already saves) | removed with behavioural tests; geometry saved first on every close attempt |

## Negative controls

- Never let a wizard or preview surface write the store directly; stage in a draft.
- Never replace a whole settings root from a snapshot taken earlier; merge onto the current value.
- Never give item widgets inside a scrolling list focus they can take on hover.
- Never trust a QSS rounded border with a translucent colour; paint the border.
- Tests must not pin operator-editable values (presets, defaults, copy) and must never show a window on screen
  (`tests/_invisible_windows.keep_off_screen`).

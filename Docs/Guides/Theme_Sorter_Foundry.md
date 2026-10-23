# Theme Sorter Foundry

Standalone theme triage/organizing tool, deliberately separate from the main Settings UI. It **never** changes `ui.settings_theme_selection`, the active Widget theme, or operator-authored colour roles. **This is optional subjective side work and is NOT a task in `Current_Plan.md` or a dependency of EB, Neon Lake, Games You Follow or the core test-repair queue.**

Launch in the repository root on the installed Windows PySide6 environment:

```powershell
& '.\.venv\Scripts\python.exe' tools\theme_sorter_foundry.py
```

Optional `--repo <root>` or `--themes-dir <root>` selects the catalogue root without changing product Settings. Source/dev roots use `themes/*.srtheme` and `themes/widgets/*.srwtheme`; installed deployments use the resolution policy in [Settings Theme Architecture](../Architecture/Settings_Theme_Architecture.md), not guessed paths.

- Select a theme: the Sorter repaints **its own QWidget UI** with the actual selected Settings-theme semantic palette and material. Live input, slider and checkbox controls provide a quick preview. No product theme selection change is sent.
- **Copy Theme Name:** copies the selected theme's authored display name to the clipboard.
- **Rename Theme Pair:** rename Settings file/name and linked Widget file/name; rewrite the Widget stable Settings link. Existing Widget colour roles survive byte-for-byte at the semantic value level; an absent linked counterpart is generated from the renamed Settings theme using the existing mirror authority. Old file-backed IDs necessarily change with filename; an already persisted product theme ID referring to the old name may fall back until the operator reselects it.
- **Delete Theme Combo:** explicit confirmation then remove the selected file and **only its ID-linked Widget** counterpart. This is permanent file deletion. No default/theme-replacement is performed in the product Settings store.
- The actual compiled `Default Dark.srtheme` mirror is not a deletable authored theme, unlike other freely editable themes with similar names.

Both file operations preflight invalid filename/conflicts/ambiguous Widget links, stage outputs, and attempt rollback on errors. Unexpected restore failure retains a hidden `.theme-sorter-transaction-*` recovery directory with original files. Do not casually delete recovery data. Both operations are synchronous, human-initiated; no background catalogue scanning or timers.

## Tests and acceptance

Qt-free functional tests: `tests/test_theme_sorter_model.py`, all with temporary test-authored files and no golden assumptions about repository themes. No preset/theme visual contents are protected or frozen.

**Still needs native agent validation:** actual Windows Qt widget paint, accent modes across Glass/Acrylic/Off, clipboard copying, rename/delete confirmation, name-collision warnings, paired Widget name/link in the real Settings theme picker, and refresh after operations. Test on throwaway copies, not the operator's actual authored pack. The tool's appearance can be visually inspected by the agent; only subjective artistic preferences need operator input.


## 2026-10-23 native preview/material repair candidate

The first generated set of 60 themes was schema-valid but painted opaque Qt
`window.dialog_glass` surfaces (alpha 210 or 243/255), obscuring the Windows
Glass/Acrylic effect. Acrylic tint alpha was also excessive. Those values have
been reduced for the **60 new freely mutable themes only**, without altering
older authored themes or their Widget counterparts. The earlier Foundry was a
plain decorated QMainWindow using unthemed QCheckBox/QComboBox controls; it was
**not** a faithful Settings preview, regardless of its label.

The replacement candidate uses the shared frameless Foundry title-bar,
`StyledComboBox` with tool-local semantic popup colours, the same shared circle
checkbox indicator renderer supplied with the previewed theme, a native
backdrop, and live controls/surfaces plus linked Widget-card swatches. All
product theme selection and authored Settings remain untouched. This is
**source-only** verification: agent must compare Glass/Acrylic transparency
and actual Windows Desktop visibility against pre-existing working themes,
using dark and light examples at different DPI, including first show, theme
switch, reopen, popup indicators and click targets. Preserve working authored
patterns; do not replace objective UI checks with subjective theme goldens.
The new experimental palettes are mutable and disposable; do not protect
specific colours, names, counts, or artistic appearance in automated tests.

## Shared-control fidelity correction (tool only)

The initial preview mixed `StyledComboBox` with a generic Foundry QComboBox
skin. Qt therefore laid out the actual circular knob against an incompatible
rectangle. The preview also used a stock `QSlider` and generic QDoubleSpinBox
up/down buttons, resulting in mismatched groove/handle geometry and oversized,
visually dead right-hand stepper panels. Those visuals were **not** an accurate
representation of a Settings theme.

The Sorter now opts out of generic Foundry input, combobox, checkbox, spinbox
and slider rules. It uses `StyledComboBox` and `NoWheelSlider` alongside the
real shared Settings stylesheet templates for combo closed state/popup,
spinbox circular stepper, slider groove/fill/handle and circle checkbox.
`render_settings_preview_control_styles(theme)` accepts a tool-local theme,
rendering the same semantic definitions without altering product Settings or
mutating the shared process-global theme. Other Foundries keep their existing
stylesheet unless they explicitly opt in.

Agent verification (tooling only, **not** a `Current_Plan.md` task): use a
throwaway theme catalogue, record Windows screenshots of the whole preview at
100%/150%/mixed DPI and compare actual Settings controls at the same DPI.
Check that both combo dots are centered on their visible pills; popup options
and selections are usable; the slider has the shared groove/fill/handle and
moves on click/drag/keyboard; spinner circles increment/decrement without
hidden hit targets; circular checkbox toggles; and background material remains
visible. Include dark and light Glass/Acrylic themes. Fix any native discrepancy
in shared theme rendering, not with another hand-authored approximation. No
operator sign-off is required for objective alignment and hit-target issues.

# Settings `dark.qss` Retirement

Last updated: 2026-09-14

## Purpose

This is the **execution authority** for retiring `themes/dark.qss` without changing the accepted Settings GUI appearance or behavior.

The permanent theme/backdrop architecture remains `Docs/Architecture/Settings_Theme_Architecture.md`. `Future_Cleanup.md` owns admission/priority. This document owns the actual migration/deletion method once that cleanup item is admitted.

The objective is deliberately strict:

> **Retire every production dependency on `themes/dark.qss` with zero intended pixel or interaction change, then remove any remaining packaged/source asset.**

`dark.qss` is legacy debris, but the current product looks correct. Its removal is a dependency/ownership cleanup, not an opportunity to redesign controls, tweak spacing, “improve” colours, change native materials, or simplify fragile geometry by eye.

**2026-09-14 implementation status:** the checkpoint worktree remains the code authority; the current repository `themes/dark.qss` was read only as the missing reference oracle because GODZIP Foundry intentionally excludes `themes/`. Caller/precedence audit is complete enough to sever production dependencies without transplanting the monolith. `ui/settings_theme.py` and `ui/system_tray.py` no longer load/reference the file, the color-picker wrapper explicitly owns the only live legacy subsettings chrome found by caller proof, and a Qt-free retirement contract is **6/6 PASS**. The final repository/build asset deletion remains **Needs run** behind the physical Windows/PySide absence matrix. Never recreate or restore the legacy file as a fallback.

---

## Hard invariants — do not cross these boundaries

The retirement must preserve all of the following:

- schema-v6 `SettingsThemeSpec` remains sole Settings palette/opacity/shadow/gradient authority;
- compiled Default Dark remains the unconditional no-file/failure theme fallback;
- Glass remains untinted AccentPolicy state 3; semantic Qt RGBA surfaces own visible Glass tint/opacity;
- Acrylic remains AccentPolicy state 4 with real native theme tint/strength;
- `WA_TranslucentBackground`, the layered Settings HWND contract, native transition ownership and `core/windows/dwm_blur.py` are **out of scope**;
- forged outer-edge/corner geometry in `ui/settings_dialog.py` is **out of scope**;
- no post-show retry, timer, stylesheet replay, event-loop pump or repeated native call may be introduced;
- visual literals found in `dark.qss` are evidence of old behavior, **not values to copy back into Python**;
- a selector is migrated only if current caller proof shows that its structural/behavioral effect is still required;
- a rule already superseded by semantic/component styling is deleted rather than re-homed “just in case.”

If a proposed change alters the current appearance to make the cleanup easier, it is not this cleanup.

---

## Current dependency surface — 2026-09-14

Production runtime dependency is now **zero** in this checkpoint candidate:

1. `ui/settings_theme.py` no longer has `_load_base_stylesheet()` or a missing-file fail path. `_apply_theme_to_widget()` applies one complete root string from `_build_settings_root_stylesheet(theme)`, composed from a tiny palette-free structural base plus semantic ThemeSpec QSS.
2. `ui/system_tray.py` no longer reads a stylesheet file. `ui/settings_menu_style.py` renders only the tray `QMenu`/item/separator family from existing `context.menu.*` ThemeSpec roles while preserving the accepted legacy menu geometry.
3. `_ColorPickerDialog` in `ui/styled_popup.py` owns its frameless wrapper/title/close chrome explicitly. Its body was already semantic/palette-owned; it no longer inherits those rules accidentally from a global Settings stylesheet.
4. `tools/flicker_test.py` consumes the current semantic Settings-root renderer rather than a legacy file path. Foundry source also has no product dependency/reference.

The physical `themes/dark.qss` repository/build asset is **not** part of GODZIP payloads. Therefore code dependency retirement and physical asset deletion are deliberately separate evidence: the former is landed here; the latter must be done in the real repo only after the file-absent acceptance matrix passes.

---

## Current measured surface and resolved caller audit (2026-09-14)

Reference oracle: current public repository `themes/dark.qss`, blob SHA `42ea38a0a299f4950a27a74506971bea41a2be03`, **989 lines**. This file was inspected as reference only; the checkpoint ZIP remains the working tree.

The older ~989-line/~98-selector estimate substantially overstated the live migration burden because it counted historical selectors as though they were current callers. Exact object-name/source search plus current semantic-renderer inspection reduced the required migration to a bounded set:

| Legacy family | Current caller/precedence finding | 2026-09-14 disposition |
| --- | --- | --- |
| global `*` font | still useful as Settings fallback typography | retained as palette-free structure in `_build_base_structural_styles()` |
| generic `QCheckBox` typography/background | plain Settings checkboxes still inherit these structural details; semantic renderer owns colours/indicator | retained as palette-free structure; no legacy colour copied |
| generic `QLabel:disabled` | legacy pseudo-state still beat the current generic semantic `QLabel` rule; deleting the file would otherwise lose disabled-text contrast | moved to current root renderer with existing `text.disabled` role; no new token |
| `QToolButton[autoRaise="true"]` buckets | current `_build_custom_styles()` already owns geometry **and** semantic palette | legacy rule is redundant; no migration needed |
| `QToolTip` | current semantic root renderer already owns border/radius/padding/palette | legacy rule is redundant; no migration needed |
| `QGroupBox` + title | current semantic root renderer owns accepted structure/palette; missing old inherited font-weight/family was made explicit in that owner | permanent current owner confirmed |
| `QMenu` | Settings "More Options" menus already have local semantic QSS; tray alone depended on the global family | tray moved to narrow `settings_menu_style.py`; no generic monolith |
| `#subsettingsDialog` / `#titleFrame` / `#titleLabel` / `#closeButton` | live only in `_ColorPickerDialog`; its content body already had its own semantic owner | wrapper/title/close structure moved beside the picker using existing semantic roles |
| generic `QDialogButtonBox` | can affect Qt-owned/non-native dialog button ordering/margin even without an explicit app-side constructor | preserve its palette-free `button-layout: 1` + 10 px margin in the tiny root structural base; color picker locally overrides margin/padding while retaining button order |
| `QMainWindow`, overlay/main-frame/title-bar/resize-indicator families | no matching current caller in the Settings/tray path | dead architecture; do not transplant |
| `QKeySequenceEdit#SettingsKeySequenceEdit`, `SubSettingsSectionLabel`, `QComboArrow`, `QBasicBitchButton`, `QSmolselect*`, action/select/start/settings/about named buttons, loading/opacity-control families | no matching live object-name caller in current source | dead rules; preserve only in history/git |
| old subsettings scroll-area/corner/scrollbar family | no live caller in the current color-picker wrapper; current main Settings scrolling is owned elsewhere | do not migrate; R-09 remains the guardrail against recreating broad descendants |

### Why no ThemeSpec schema expansion was required

The earlier plan proposed roughly two dozen new semantic tokens because it assumed most legacy colours still had live callers. Caller proof disproved that premise. Adding those roles would have bloated strict schema-v6 `.srtheme` identity and could invalidate existing theme files for values that no current renderer needs. The landed approach therefore:

- reuses existing semantically correct roles for the narrow surviving callers;
- derives the color-picker close-hover inversion from its current semantic text role instead of minting a dead legacy token;
- keeps `_build_base_structural_styles()` free of colour literals;
- does **not** copy the old stylesheet into Python or a replacement `.qss`;
- leaves strict theme IO/schema shape unchanged.

### Automated dependency guard

`tests/test_settings_dark_qss_retirement_contract.py` runs without PySide package initialization and currently passes **5/5**. It proves:

- selected production Settings/tray/tool sources contain no legacy path reference and `_load_base_stylesheet` is gone;
- the tiny permanent base structural owner contains no palette literal;
- the complete Default Dark root stylesheet renders without unresolved placeholders or legacy file input;
- tray QMenu structure renders from ThemeSpec context-menu semantics;
- the color-picker wrapper owns the legacy subsettings chrome semantically;
- installer/build tooling has no filename-specific dependency on the obsolete stylesheet (`.iss` copies themes generically; build layout admits `.srtheme`/`.srwtheme` assets by extension).

`tests/test_settings_theme_lifetime_contract.py` was reconciled from the retired `BASE + CUSTOM` seam to `_build_settings_root_stylesheet(theme)`. Direct stubbed execution is **2/2 PASS**; ordinary pytest collection is still **Needs run** here because the repository `conftest.py` imports PySide6.

---

## Why this is dangerous despite the new theme system

The file mixes at least four very different kinds of material:

1. **obsolete visual palette** — old hard-coded dark colours that ThemeSpec now owns;
2. **still-useful structure/geometry** — margins, radius, dimensions, scrollbar/corner behavior, subcontrol geometry and similar non-palette rules;
3. **specificity/Qt behavior fixes** — rules whose exact selector shape matters even when the visual value looks trivial;
4. **unrelated/legacy callers** — old `QMainWindow`, overlay and control selectors that may no longer belong to current Settings at all.

Never migrate a whole block because one declaration inside it is live.

### Known specificity landmine: R-09

`Docs/Historical_Bugs/R-09_Settings_Input_Fill_QSS_Specificity.md` is required reading before touching scroll-area rules.

A broad descendant rule once made every Settings `QSpinBox`/`QLineEdit` transparent because:

```css
QScrollArea QWidget { background: transparent; }
```

out-ranked the intended input fill. The accepted repair deliberately narrowed the remaining SubSettings rule to:

```css
#subsettingsDialog QScrollArea > QWidget > QWidget
```

Do not “simplify” direct-child selectors back into broad descendants during retirement.

---

## Resolved risk map

The initial risk-map questions are now answered by the 2026-09-14 caller audit above. Durable lessons:

- global/named rules are not migrated merely because they exist in the old file;
- Settings-root typography and plain-checkbox structure are the only generic structural residue retained centrally;
- buckets, tooltips, group boxes, Settings menus and current inputs already have current owners;
- tray menu and color-picker wrapper were the only bounded secondary consumers requiring new/narrow ownership;
- old `QMainWindow`/overlay/title-bar/named-button/scroll-area families are dead for current Settings/tray and must not reappear as compatibility debris.

---

## Selector-audit method (completed 2026-09-14)

The implementation used one working row per surviving selector/rule family:

| Selector | Live caller(s) | Current precedence | Classification | Destination owner | Action | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| example | source path/object name | base-only / later-overridden / mixed | palette / structure / behavior / dead | exact module/component | delete / migrate structure / replace semantic owner | named visual/control check |

Rules:

- search both selector strings and matching `setObjectName()`/dynamic-property callers;
- distinguish “selector exists in source” from “this declaration still wins after later QSS”;
- for mixed rules, classify declarations individually;
- if later component/semantic QSS already owns the accepted result, delete the old declaration rather than duplicating it;
- if a legacy colour currently leaks through because no semantic role owns it, resolve that ownership explicitly. Prefer an existing semantically correct ThemeSpec role; add a narrowly justified semantic role only if no correct role exists. Do **not** create a hidden hard-coded replacement palette;
- do not preserve dead rules for historical appearance. Git history/historical bugs already preserve evidence.

The durable outcome of that table is recorded in the resolved caller audit above; Git/history retain the discarded legacy details. Re-run exact caller/source search immediately before final physical deletion in case later commits introduced a new dependency.

---

## Migration sequence / live status

### Stage 0 — reference oracle and asset provenance — **PARTIAL / NEEDS RUN**

Landed:

- current repository file recorded as 989 lines, SHA `42ea38a0a299f4950a27a74506971bea41a2be03`;
- GODZIP exclusion of `themes/` confirmed, so workspace absence is not treated as product absence;
- current source callers/precedence audited.

**Needs run:** capture/compare representative Settings output on the operator's Windows/PySide environment before/after the real file is renamed/removed. Include Default Dark, one materially different theme, Acrylic, Glass, dense/scroll-heavy pages, picker and tray.

### Stage 1 — caller/precedence inventory — **LANDED**

Resolved in the 2026-09-14 caller table above. Dead selectors were not migrated. Re-run exact source/object-name search immediately before final physical deletion to catch later changes.

### Stage 2 — sever tray from monolith — **LANDED / VISUAL NEEDS RUN**

`ui/system_tray.py` now uses `ui/settings_menu_style.py`. The renderer owns only `QMenu`/item/separator structure and consumes existing semantic `context.menu.*` roles. Static/Qt-free contract is green; physical tray appearance/interaction remains **Needs run**.

### Stage 3 — migrate only live Settings structure — **LANDED / VISUAL NEEDS RUN**

The migration is intentionally much smaller than the old estimate:

- root fallback font + plain-checkbox typography/background + generic dialog-button-box ordering/margin live in `_build_base_structural_styles()` and contain no palette literals;
- group-box inherited typography was made explicit in the current semantic owner;
- the live generic disabled-label pseudo-state is now explicitly semantic via existing `text.disabled`;
- bucket/toolbutton and tooltip structure was already current-owner QSS and was not duplicated;
- `_ColorPickerDialog` now owns its old subsettings wrapper/title/close structure beside the component;
- dead overlay/main-window/named-button/scrollbar families were not re-homed.

No new ThemeSpec role was added solely for the cleanup and strict schema-v6 theme identity remains unchanged.

### Stage 4 — replace Settings root base-file contract — **LANDED**

`_load_base_stylesheet()` is gone. The root applies:

```text
_build_base_structural_styles()
        +
_build_custom_styles(theme)
        -> widget.setStyleSheet(...)
```

There is no `missing legacy file => return False => apply nothing` path. Theme persistence/runtime notification/native backdrop ownership is unchanged.

### Stage 5 — real file-absent Windows/PySide gate — **NEEDS RUN**

In the actual repository/install tree, temporarily rename/remove `themes/dark.qss` and execute the matrix below. This is the decisive evidence that the code-dependency cleanup preserved the accepted product, because GODZIPs cannot represent this physical asset.

If any visual/lifecycle regression appears, inspect the exact missing structural owner. **Do not restore the whole stylesheet as fallback.**

### Stage 6 — final repository/build asset deletion — **PENDING STAGE 5**

After the file-absent matrix is green:

- permanently delete `themes/dark.qss` from the real repository;
- installer/build audit is already green for filename independence; re-check it after physical deletion and confirm the generic theme copy contains only intended assets;
- repository-search production code again for the path/name; historical bug/docs references may remain as history;
- remove any temporary visual/audit probes;
- update `Current_Plan.md` / `Future_Cleanup.md` / this document from candidate to complete.

The production loader deletion has already landed in the checkpoint because the working GODZIP cannot carry the physical asset. This is an intentional two-evidence boundary, not a supported half-state: runtime code must never regain a dependency while the physical cleanup waits for operator validation.

---

## Physical acceptance matrix

The final file-absent run must cover at least:

### Theme/material lifecycle

- compiled Default Dark/fallback;
- representative Acrylic theme on fresh Settings start;
- representative Glass theme on fresh Settings start;
- Acrylic -> Acrylic tint change;
- Glass -> Glass semantic theme change;
- Acrylic <-> Glass live switch;
- material -> Off and Off -> material if an Off theme remains supported;
- persisted selected theme reopened in a new Settings process.

Any first-start Glass regression is an immediate stop. `dark.qss` cleanup is not allowed to reopen the solved native-material bug.

### Main Settings surface

- forged outer edge/corners at rest and while resizing;
- title bar text/buttons/close states;
- sidebar, selected/hovered tabs and content area;
- group boxes and collapsible buckets open/closed/hovered;
- labels, informational text and disabled text;
- lists and selected/hovered items;
- ordinary buttons, named compact buttons and disabled/pressed/hovered states;
- checkboxes/radios and indicator resources;
- line edits, spin boxes, key sequence edits and focus states;
- combo boxes including popup/drop-down geometry;
- sliders and any custom-painted control states;
- tooltips;
- long/scroll-heavy pages including bottom-right scrollbar corners.

### Secondary/dialog consumers

- SubSettings dialog including rounded title/content/scroll area corners;
- About dialog;
- StyledPopup/info-warning-error path where applicable;
- colour picker/swatch path used by Settings themes;
- tray menu including selected/disabled/separator states;
- any other caller discovered by the preflight selector audit.

### DPI/geometry

At minimum, test the operator's normal display/DPI configuration. If practical before closure, also test one non-100% scale because fixed QSS dimensions and icon/button boxes are common residue in the old file.

---

## Focused automated/static checks

Automation cannot replace the physical visual oracle, but the cleanup should add or retain cheap proof for:

- no production source reference to `themes/dark.qss` after completion;
- no `_load_base_stylesheet` / `_load_tray_menu_stylesheet` dependency after completion;
- strict `.srtheme` load/round-trip remains unchanged;
- semantic theme renderers contain no unresolved placeholders;
- R-09 input-fill behavior is not reintroduced by broad descendant scroll-area selectors;
- any structural helper introduced has a focused ownership test rather than a full-style snapshot that ossifies obsolete palette text.

Do not create a giant golden-QSS string test as the replacement architecture.

---

## Stop / rollback conditions

Stop the current slice and return to the last known-good state if any of these occur:

- Glass or Acrylic fresh-start behavior changes;
- a corner/edge becomes square, clipped, black, haloed or otherwise materially different;
- an input fill becomes transparent/wrong again;
- scroll-area corners or scrollbars paint square filler/background;
- geometry shifts, controls resize or typography metrics change unexpectedly;
- a migrated rule requires copying old palette literals into a new hidden styling owner;
- the proposed fix needs retries/timers/order tricks rather than clear ownership;
- the implementing agent cannot explain which old declaration was live and which new owner replaces it.

The correct response to a failed slice is to inspect ownership/specificity, not to re-add the whole legacy stylesheet as a fallback.

---

## Definition of done

`dark.qss` retirement is complete only when all are true:

- `themes/dark.qss` is absent;
- neither Settings nor tray/runtime production code reads or references it;
- every surviving structural/behavior rule has a narrow current owner;
- ThemeSpec remains sole Settings visual authority;
- no legacy visual literals were copied into a new hidden palette;
- Default Dark, Acrylic and Glass all pass fresh-start/live-switch physical checks;
- secondary dialogs, tooltips, inputs, buckets, scroll areas and tray menu match the accepted pre-cleanup behavior;
- forged edge/corner/native AccentPolicy architecture is unchanged;
- temporary audit/probe machinery is removed;
- `Future_Cleanup.md` can remove the item rather than carrying a compatibility fallback.

If the file is gone but the GUI changed, the cleanup is not done.

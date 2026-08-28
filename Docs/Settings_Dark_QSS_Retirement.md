# Settings `dark.qss` Retirement

Last updated: 2026-08-28

## Purpose

This is the **execution authority** for retiring `themes/dark.qss` without changing the accepted Settings GUI appearance or behavior.

The permanent theme/backdrop architecture remains `Docs/Settings_Theme_Architecture.md`. `Future_Cleanup.md` owns admission/priority. This document owns the actual migration/deletion method once that cleanup item is admitted.

The objective is deliberately strict:

> **Delete `themes/dark.qss` with zero intended pixel or interaction change.**

`dark.qss` is legacy debris, but the current product looks correct. Its removal is a dependency/ownership cleanup, not an opportunity to redesign controls, tweak spacing, “improve” colours, change native materials, or simplify fragile geometry by eye.

---

## Hard invariants — do not cross these boundaries

The retirement must preserve all of the following:

- schema-v5 `SettingsThemeSpec` remains sole Settings palette/opacity/shadow/gradient authority;
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

## Current dependency surface

At the reviewed 2026-08-28 source state, there are two production loaders that matter:

1. `ui/settings_theme.py::_load_base_stylesheet()` reads the whole `themes/dark.qss`. `_apply_theme_to_widget()` currently aborts if that load returns `None`, then applies:

   ```text
   dark.qss + semantic _build_custom_styles(theme)
   ```

   Therefore simply removing/renaming the file **currently prevents the normal semantic Settings stylesheet from being applied at all**. The file-absent acceptance test is only meaningful after this loader dependency has been replaced.

2. `ui/system_tray.py::_load_tray_menu_stylesheet()` independently reads the same whole file and applies it to a single `QMenu`.

Repository-wide search must be repeated immediately before implementation. Historical documents and diagnostic tools that mention the file are not production runtime dependencies, but no agent may assume the loader inventory above remains complete after later commits.

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

## Initial risk map — starting evidence, not final caller proof

The current `dark.qss` contains several rule families that deserve explicit classification before deletion.

| Rule family / examples | Why it is risky | Expected destination decision |
| --- | --- | --- |
| global `*` font family | can silently affect every descendant and fallback metric | prove whether current explicit/shared typography already owns it; otherwise move only the required typography default to the narrow Settings owner |
| `QMainWindow`, `#main_frame`, `#borderOverlay`, `#overlayBackdrop`, old title-bar rules | visibly old application/overlay architecture mixed into the file | caller-proof; delete if no current live Settings/tray caller rather than transplanting |
| `QDialog#settingsDialog`, `#subsettingsDialog`, `#aboutDialog`, border/content/title frames | contains transparency, radius, margins and clip/corner assumptions as well as old colours | split structural declarations from palette; move structure to owning dialog/component only if still live |
| SubSettings `QScrollArea` / viewport / corner / scrollbar rules | historically specificity-sensitive and tied to rounded-corner cleanup | preserve exact required structural semantics; no broad descendant selectors |
| close/title label/button rules | mix fixed dimensions, symbol font, margins and old palette | retain only live geometry/behavior in the owning dialog; ThemeSpec/component renderer owns colour |
| `QKeySequenceEdit#SettingsKeySequenceEdit` | specialized control geometry/focus styling may not be fully duplicated elsewhere | inspect caller and semantic renderer before moving anything |
| `QDialogButtonBox` | `button-layout` and margin affect behavior/layout rather than palette | preserve only if current dialogs still depend on it |
| `QToolButton[autoRaise="true"]` | current semantic theme renderer overrides its palette, while `dark.qss` has historically supplied base bucket geometry | migrate only the structural bucket geometry into the bucket/shared-style owner; do not restore old colours |
| `QToolTip` | semantic theme currently overrides colours but base geometry may still be inherited | make one narrow tooltip renderer own required geometry + semantic tokens |
| `QMenu` and subcontrols | the tray currently loads the entire file solely to obtain this family | create a narrow tray-menu style owner; do not keep a general stylesheet dependency for one menu |
| generic `QGroupBox`, buttons, inputs, combo boxes, scrollbars, sliders, lists | later semantic/shared/component QSS may override some but not all declarations | compare final effective responsibility declaration-by-declaration; delete redundant rules, migrate only surviving structure |
| named legacy buttons such as `QComboArrow`, `QBasicBitchButton`, `QSmolselect`, `QSmolselectMini` | object-name rules can remain live even when generic styling moved | search current object-name callers; move required geometry to their component/shared owner or delete after caller proof |

This table is deliberately not permission to migrate those rules. It tells the implementing agent where to look first.

---

## Required selector audit

Before modifying code, build a temporary working table with one row per surviving selector/rule family:

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

The completed working table need not become a permanent document unless it exposes a durable new contract, but it should be retained with the implementation/audit evidence until physical acceptance.

---

## Migration sequence

### Stage 0 — freeze the visual oracle

Before the first stylesheet edit:

- inspect exact current main;
- record the current `dark.qss` SHA and both production loaders;
- capture representative Settings screenshots/notes for Default Dark, one Acrylic theme and one Glass theme;
- include at least the Themes tab, a dense form/input tab, a scroll-heavy tab and one subdialog/menu state;
- record current window size/DPI and any known corner/edge behavior;
- treat the accepted current output as the visual oracle. This cleanup has no planned restyle.

### Stage 1 — caller/precedence inventory

Complete the selector audit above before broad removal.

Do not begin by copying `dark.qss` into a Python string or a new `.qss` file. That merely moves the albatross.

### Stage 2 — sever the tray from the monolith

`ui/system_tray.py` should stop loading the whole file before Settings loses its base dependency.

Destination:

```text
ScreensaverTrayIcon
    -> narrow QMenu structural/style renderer
    -> only the semantic visual authority actually required by that menu
```

Requirements:

- only `QMenu`/item/separator behavior used by the tray belongs here;
- no unrelated Settings selectors;
- no copied dark palette literals as a new private theme;
- preserve current padding, separator and disabled/selected behavior unless a semantic owner intentionally already defines the accepted equivalent;
- physically inspect the tray menu before continuing.

### Stage 3 — migrate Settings structural behavior in bounded families

Recommended order:

1. root/default typography behavior;
2. Settings/subsettings/about dialog structure and fixed geometry;
3. scroll-area/viewport/corner/scrollbar structural rules;
4. specialized input/control geometry and resources;
5. bucket/toolbutton and tooltip base geometry;
6. any remaining proven named-control rules.

For each family:

```text
identify live winning declarations
-> move only structural/behavior declarations to the narrow permanent owner
-> use ThemeSpec/component renderer for visuals
-> remove the corresponding legacy declarations from the working base
-> focused test + eyes-on comparison
-> continue
```

Do not accumulate a second giant “structural qss” monolith. Structural QSS is acceptable where QSS is genuinely the correct renderer, but ownership should sit beside the component/dialog/shared-style code that owns those selectors.

### Stage 4 — replace `settings_theme.py` base-file contract

Before testing with `dark.qss` absent, change the root renderer so semantic theme application no longer depends on `_load_base_stylesheet()` succeeding.

The final shape should be conceptually:

```text
owned structural Settings QSS/renderers
        +
semantic ThemeSpec QSS
        -> widget.setStyleSheet(...)
```

There must be no “missing dark.qss => return False => apply nothing” path.

Do not change theme persistence/runtime notification/native backdrop behavior while doing this.

### Stage 5 — physical file-absent gate

With all known live structure owned elsewhere, physically remove/rename `themes/dark.qss` in the test worktree and run the complete matrix below.

The absence gate must happen **before** final deletion is committed. A green run means the product no longer depends on the file, not merely that no importer mentions it.

### Stage 6 — final deletion boundary

Only after the absence gate is green:

- delete `_load_base_stylesheet()` and any now-dead path/import/logging from `ui/settings_theme.py`;
- delete `_load_tray_menu_stylesheet()` and any now-dead path/import/logging from `ui/system_tray.py`;
- delete `themes/dark.qss`;
- delete stale comments claiming `dark.qss` supplies geometry;
- run repository search proving no production runtime code references the file;
- remove temporary audit/probe code created for the migration;
- keep historical references as history unless they falsely claim current authority.

The loader/file deletion belongs in one bounded final cleanup boundary so there is no supported half-state where a required file has been deleted but code still depends on it.

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

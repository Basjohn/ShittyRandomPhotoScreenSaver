# Custom Style Implementation

Last updated: 2026-09-02

## Settings UI

Settings remains QWidget-based. Settings-window shadows under `ui/widgets/control_shadow.py` are Settings
styling, separate from runtime widget shadow authority.

Settings visual values are owned by schema-v5 `SettingsThemeSpec`; permanent architecture is
`Docs/Settings_Theme_Architecture.md`. The frameless translucent Settings top-level is a layered HWND on Windows.
Acrylic and Glass deliberately stay on the same AccentPolicy composition family: Acrylic uses state 4 with native theme
tint; Glass uses untinted state 3 and semantic Qt RGBA surfaces supply its visible palette/opacity. Do not move native
material behavior into QSS or use native backdrop changes to compensate for semantic stylesheet defects.

`themes/dark.qss` is temporary legacy base-QSS residue, not palette authority. Its safe structural-selector retirement
is recorded in `Future_Cleanup.md`; do not remove it by recreating its old colour literals in component code.

## Settings theme selection and sectional navigation

The landed Themes tab owns live `.srtheme` selection for the Settings GUI and reserves a separate **Widget Themes** pill
for future `.srwtheme` work. Settings-theme selection must continue through the schema-v5 catalog/runtime path above;
individual Settings tabs do not own private palettes.

Future Widget Theme UX has **two orthogonal appearance axes**, not one overloaded theme selector. `Keep Synced` (default
ON) links Settings-theme identity to an explicitly mirrored Widget Theme. The Widget Theme owns the semantic runtime
palette/visual bundle and a `default_card_material_mode` recommendation. `Settings -> Widgets -> General -> Appearance`
owns one separate **Surface Style** preference: `Theme Default / Normal / Glass / Acrylic`. `Theme Default` follows the
selected Widget Theme recommendation; an explicit material overrides only the surface while retaining the same Widget
Theme colours. Keep Synced never clears an explicit surface override. Do not solve this by hiding colour swatches, by
manufacturing a fake `Custom` theme solely to unlock them, or by adding a second `Override Theme Background` checkbox—the
`Theme Default` Surface Style entry is the inheritance/no-override state.

Widget Theme card roles are fallback/global defaults underneath existing explicit per-widget card controls. Resolve an ordinary family card role as `explicit widgets.<family>.card.* value -> Widget Theme baseline`. This preserves mature family customisation when switching themes. The Context Menu is direct/global because it has no family card override. Per-family edits remain family-specific and do not trigger the Widget Theme Custom/unsync transition.

Manual edits to a **Widget Theme-owned** swatch/border/shadow/other visual value use one explicit ownership transition:
snapshot the complete currently resolved named Widget Theme into user-owned `Custom`, apply the edit to that snapshot,
switch the Widget Theme selector to `Custom`, and automatically turn `Keep Synced` OFF. This should be near-silent (no
confirmation dialog for the edit itself); the shipped `.srwtheme` is never mutated and all unedited theme values are
preserved in the Custom snapshot. `Custom` is persisted inside normal SRPSS Settings data, **not** written as
`themes/widgets/Custom.srwtheme`; runtime customization therefore requires no write permission to the installed theme
directory. A real `.srwtheme` is created only by an explicit save/export/authoring action. Do not implement hidden
per-property override inheritance on top of named themes.

Changing only Surface Style does **not** create Custom, modify the selected `.srwtheme`, or unsync the themes. If the user
later re-enables Keep Synced while Custom is active, the UI may switch back to the linked named Widget Theme, but the Custom
snapshot should remain available rather than being destroyed. Pack generation may pair matching `.srtheme`/`.srwtheme`
names as an authoring convenience, but runtime linkage should use explicit stable theme IDs/metadata rather than
display-name heuristics.

Sectional pill navigation is renderer/layout structure, not a new theme semantic. The Display tab now uses the same
sectional pill language as other large Settings tabs and consumes the existing `navigation.subtab.*` colour roles. Future
sectional rearrangements should reuse those semantic roles unless a genuinely distinct visual concept appears. Different
geometry/padding may have a narrow component style owner without expanding every `.srtheme`.

Theme-file layout is one shared root with a Widget subfolder, not one flat catalogue:

```text
installed/frozen: %ProgramData%\SRPSS\themes\*.srtheme
                  %ProgramData%\SRPSS\themes\widgets\*.srwtheme

source/dev:       <repo>\themes\*.srtheme
                  <repo>\themes\widgets\*.srwtheme
```

The Settings/Widget theme catalogues consume directories injected/resolved by startup/build authority. Do not duplicate
path policy inside renderers or merge ProgramData and repository catalogues simultaneously. The repository/bundled tree is
a development/bootstrap source; the installed stable root is ProgramData. Those installed theme files are read-mostly
catalogue assets; the automatic Widget Theme `Custom` state lives in Settings persistence rather than the filesystem.

## Canonical runtime shadow controls — F0.5 CLOSED / independently GREEN

Widgets → General → Appearance owns:

```text
Widget/Card: enabled, frame_opacity, blur_radius, frame_extra_offset
Text:        text_enabled, text_opacity, text_extra_offset
Header:      header_enabled
All:         direction = NW/N/NE/W/E/SW/S/SE
```

Direction picker is compact 3×3, center inert, default/fallback SE. No Text Blur, Intense mode or old
`widgets.shadows.offset`.

General save merges edits onto the existing `widgets.shadows` mapping so unrelated/future keys survive.

## Retired tuning authority

`shadowtuning.json` / `core.settings.shadow_tuning` is retired and must not return by relocation. Do not
reconstruct hidden card/text/text_large/header/icon/control/volume_slider profiles.

A visual rule is family-authored only if the family independently owns it. Clock analogue ring/marker/
numeral/hand relationships qualify; retired sidecar values do not become family-authored because they were
copied into a family file.

## Quick destination

Ordinary card: `OverlayCard -> cached RectangularShadow`.
Ordinary text: duplicate shadow glyph at signed offset + visible glyph.
No ordinary text blur/MultiEffect/layer capture. Whole-widget fade is ancestor/root opacity; no staged
shadow/effect carriers.

Current deliberate ordinary base magnitudes live in the retained widget host. Card/frame **Extra Offset is directional growth**, not whole-shadow translation: the base signed offset stays authored and only the selected far edge(s) extend. Text Extra Offset remains signed glyph displacement. Direction still resolves in Python.

Retained Context Menu is a runtime Quick overlay and consumes the same global **Card** shadow direction/opacity/blur/Extra Offset contract once per runtime generation. Its cached shadow is composed in the menu overlay plane so it can cast over runtime widgets/Visualizer/edit chrome while remaining behind the menu itself. Future Context Menu palette/material comes from **Widget Theme** semantic roles, not directly from the Settings QWidget theme. `Keep Synced` (future, default ON) links each Settings theme to its mirrored Widget Theme, while the separate Surface Style resolver determines the effective runtime material. Thus a user can keep a synced Glass-theme palette but explicitly render widget/menu surfaces as Normal or Acrylic. Glass/Acrylic menu pixels must reuse the same scene-local material authority as widget cards and never the Settings HWND AccentPolicy path.

## Header styling

`header_enabled` gates destination header-shadow semantic where applicable. Family header frames/logo
geometry remain family content. Do not substitute an unrelated style value because it is convenient: a
header border derives from proper card/header border authority, not a low-alpha row separator colour.

## Clock analogue

`Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md` is permanent landed contract. Global direction
applies to directional special analogue shadows. Do not flatten them into generic card/text recipes.

## Change process

Identify current product/style contract -> reject obsolete QWidget/shared-tuning mechanics -> update retained
destination owner -> focused tests -> eyes-on where subjective -> reconcile test/docs ownership -> commit.
No fidelity downgrade as performance shortcut.

# Custom Style Implementation

This document owns the durable relationship between Settings styling, runtime Widget Theme semantics, explicit family overrides and user-owned `Custom` state. Live sequencing remains in `Current_Plan.md`.

## Settings UI

Settings remains QWidget-based. Settings-window shadows under `ui/widgets/control_shadow.py` are Settings styling and are separate from runtime widget shadow authority.

Settings visual values are owned by schema-v6 `SettingsThemeSpec`; the permanent native/theme architecture is `Docs/Architecture/Settings_Theme_Architecture.md`. The frameless translucent Settings top-level is a layered HWND on Windows. Acrylic and Glass remain accepted **Settings-window** backdrop modes: Acrylic uses the native tinted composition path, while Glass uses the untinted composition family and semantic Qt RGBA surfaces provide the visible palette/opacity.

Do not use native backdrop changes to compensate for QSS/semantic palette defects. `themes/dark.qss` is retired legacy structural stylesheet residue, not palette authority, and is **physically absent**. Settings/tray structure has narrow permanent owners and `SettingsThemeSpec` owns semantic visuals. Do not restore the file, add a fallback stylesheet loader, or introduce a replacement monolithic Settings QSS — even when the asset is absent.

## Settings and Widget theme selection

The Themes tab has two current catalogues:

- **Settings Themes** — `.srtheme`, Settings QWidget/native-window appearance;
- **Widget Themes** — `.srwtheme`, runtime retained-widget/overlay semantic colours.

The two catalogues use explicit stable IDs and a bidirectional **Linked / Independent** control. While Linked, selecting either side transactionally selects and persists the exact counterpart on the other side. Selection does not silently unlink. A theme with no valid counterpart requires Independent mode before it can be selected independently.

Widget themes are **schema-v3 colour bundles that may name one card surface material** (optional `surface_material`, 6 Nov 2026; this supersedes the earlier colour-only rule, see `Docs/Architecture/Card_Surface_Materials.md` section 4). Style Overrides' Surface Material defaults to Theme (the theme's material, Normal when it names none); an explicit material there or per widget beats it. The Sep 2026 material keys (`default_card_material_mode`, `card_material_override`) stay retired. Settings theme names may legitimately retain `[Glass]`/`[Acrylic]` because those tags describe the Settings HWND; Widget counterpart names/files intentionally omit those material suffixes while `linked_settings_theme_id` still points to the exact Settings-theme identity.

## Widget Theme precedence and semantic inheritance

Widget Theme card roles are global/default baselines underneath intentional family overrides:

```text
explicit widgets.<family>.card.* value
    -> Widget Theme semantic baseline
    -> preserved local/default fallback
```

The Context Menu is direct/global because it has no family card override. Specialized visuals use the same sparse-role model:

```text
intentional family override
    -> exact Widget Theme role
    -> shared semantic parent
    -> local/current semantic value
    -> preserved fallback
```

`local.*` is runtime context and is never serialized. A default-valued stored family swatch is the implicit **Inherit** state; a genuinely changed surviving family value remains an explicit family override. Related controls belong in semantic buckets rather than one giant Appearance section. **Branded header colour controls are deliberately not family overrides anymore**: Media/Gmail/Reddit/Steam consume shared `header.*` semantics, while Media keeps only genuinely family-specific authoring such as `Seek Bar` and `Volume Control`.

Do not add one permanent Settings swatch for every separator, panel, icon, gradient or outline merely because the resolver knows the role.

## Named Widget Theme -> Custom ownership transition

Manual edits to a **Widget Theme-owned** palette value use one explicit ownership transition:

1. snapshot the complete currently resolved named Widget Theme;
2. apply the edit to that snapshot;
3. select user-owned `Custom`;
4. turn Linked/Keep Synced OFF.

The shipped `.srwtheme` is never mutated and all unedited values are preserved in the Custom snapshot. `Custom` lives in normal SRPSS Settings persistence, not as `themes/widgets/Custom.srwtheme`; ordinary customization therefore requires no write permission to the installed theme directory. A reusable `.srwtheme` is created only by an explicit save/export/authoring action such as Theme Foundry's Widget counterpart export.

Do not implement hidden per-property named-theme override inheritance on top of this state machine.

## Widgets -> General -> Style Overrides

`Style Overrides` groups the card controls whose interactions users need to see together:

- **Card Surface** — theme-owned colour edit; editing a named Widget Theme forks to `Custom`;
- **Card Border** — theme-owned colour edit; editing a named Widget Theme forks to `Custom`;
- **Header Fill** — theme-owned shared branded-header fill; editing a named Widget Theme forks to `Custom`;
- **Reset All Colours to Theme** — explicit operator action that normalizes ordinary family colour/card-alpha compatibility overrides to canonical Inherit values; never runs at startup and never touches Visualizer-authored colours;
- **Card Border Width** — global card geometry style, outside Widget Theme schema;
- **Surface Material** — global card and Context Menu surface (Normal default, Acrylic, Glass, Frosted, Mica, Smoked), outside Widget Theme schema; an explicit `widgets.<id>.surface_material` wins.

Superseded decision (6 Nov 2026): this guide used to say there is no runtime surface material control because the Sep 2026 card-backdrop experiments were physically rejected. Those mechanisms stay rejected; materials returned through `Docs/Architecture/Card_Surface_Materials.md`.

## Theme-file layout

Theme files use one root with a Widget subfolder:

```text
installed/frozen: %ProgramData%\SRPSS\themes\*.srtheme
                  %ProgramData%\SRPSS\themes\widgets\*.srwtheme

source/dev:       <repo>\themes\*.srtheme
                  <repo>\themes\widgets\*.srwtheme
```

The Settings/Widget catalogues consume directories injected/resolved by startup/build authority. Do not duplicate path policy inside renderers or merge ProgramData and repository catalogues simultaneously. The repository/bundled tree is the development/bootstrap source; ProgramData is the installed stable root. Installed theme files are read-mostly catalogue assets; automatic Widget `Custom` state lives in Settings persistence.

## Runtime card and shadow ownership

Ordinary runtime cards use the retained Qt Quick path only:

```text
OverlayCard RGBA surface/border
-> cached RectangularShadow
```

Ordinary text uses the authored duplicate shadow glyph at signed offset plus the visible glyph. There is no ordinary text blur/layer capture. Whole-widget fade is ancestor/root opacity; no staged effect carrier owns presentation.

Canonical runtime shadow controls remain:

```text
Widget/Card: enabled, frame_opacity, blur_radius, frame_extra_offset
Text:        text_enabled, text_opacity, text_extra_offset
Header:      header_enabled
All:         direction = NW/N/NE/W/E/SW/S/SE
```

Card/frame **Extra Offset is directional growth**, not whole-shadow translation: the base signed offset remains authored and only selected far edges extend. Text Extra Offset remains signed glyph displacement. Direction resolves in Python.

`shadowtuning.json` / `core.settings.shadow_tuning` is retired and must not return by relocation. Do not reconstruct hidden card/text/header/icon/control/volume profiles from old sidecar data.

## Runtime Context Menu

The retained Context Menu is a Quick overlay. It consumes the global Card shadow direction/opacity/blur/Extra Offset contract and Widget Theme semantic palette once per runtime generation. Its shadow is composed in the menu overlay plane so it may cast over runtime widgets/Visualizer/edit chrome while remaining behind the menu itself.

No menu-open/per-frame Settings read is allowed. The menu uses the same semantic-surface architecture as runtime cards, including the Surface Material baseline (`Docs/Architecture/Card_Surface_Materials.md`); Settings HWND Glass/Acrylic is never reused for it.

## Header styling

`header_enabled` gates current header-shadow semantics where applicable. Branded Media/Gmail/Reddit/Achievement Pulse/Abandonment Issues headers consume `BrandedHeader.qml`; accepted geometry/casing/intrinsic-width behavior, logo/text shadows and extension-shadow treatment are shared presentation contracts rather than family-local reinventions.

Branded Header Fill/Border/Text are shared Widget Theme semantics, not Media/Gmail/Reddit/Steam swatches. `Header Fill` is the one ordinary GUI authoring control in Style Overrides; Header Border/Text normally resolve from `header.border` / `header.text` (and their semantic parents) and may be authored in Widget Theme files/Foundry when a theme genuinely needs them. Old persisted family header fields remain compatibility-read plumbing only until the explicit deletion horizon and must never become invisible permanent precedence.

The small retained `MultiEffect` use in branded headers/artwork is local image treatment/masking only. It is not permission to restore full-card or full-display backdrop capture; surface materials use only the shared backdrop of `Docs/Architecture/Card_Surface_Materials.md`.

## Specialized local fallback guard

A specialized role may share a semantic parent without sharing the same accepted default pixel. Callers must supply the specialized current/default value at the relevant `local.*` terminal. For example, `media.volume.fill` and `media.progress.fill` can both inherit a theme-authored accent, while Default Dark may preserve distinct family-local fallback pixels when no theme/override owns them.

## Sectional navigation

Sectional pill navigation is renderer/layout structure, not a new theme semantic. Settings tabs should reuse the existing `navigation.subtab.*` roles unless a genuinely distinct visual concept appears. Geometry/padding may have a narrow component style owner without expanding every `.srtheme`.

## Clock analogue

`tests/test_qtquick_clock_presentation.py` is the executable permanent analogue-shadow contract; the ordinary-widget guide owns current authoring policy. Global direction applies to directional analogue shadows; do not flatten analogue ring/marker/numeral/hand relationships into generic card/text recipes.

## Change process

```text
identify current product/style contract
-> reject obsolete/duplicate owners
-> update the retained current owner
-> focused source tests
-> physical review where subjective
-> reconcile docs/test ownership
```

No fidelity downgrade is admitted as a performance shortcut. Settings native materials and runtime Widget semantic colours are separate architectures and remain separate; runtime card materials are scene-local (`Docs/Architecture/Card_Surface_Materials.md`) and never touch the Settings native stack.

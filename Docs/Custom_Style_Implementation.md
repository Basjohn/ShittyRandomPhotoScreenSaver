# Custom Style Implementation

Last updated: 2026-09-03

This document owns the durable relationship between Settings styling, runtime Widget Theme semantics, explicit family overrides and user-owned `Custom` state. Live sequencing remains in `Current_Plan.md`.

## Settings UI

Settings remains QWidget-based. Settings-window shadows under `ui/widgets/control_shadow.py` are Settings styling and are separate from runtime widget shadow authority.

Settings visual values are owned by schema-v5 `SettingsThemeSpec`; the permanent native/theme architecture is `Docs/Settings_Theme_Architecture.md`. The frameless translucent Settings top-level is a layered HWND on Windows. Acrylic and Glass remain accepted **Settings-window** backdrop modes: Acrylic uses the native tinted composition path, while Glass uses the untinted composition family and semantic Qt RGBA surfaces provide the visible palette/opacity.

Do not use native backdrop changes to compensate for QSS/semantic palette defects. `themes/dark.qss` remains legacy structural stylesheet residue, not palette authority; its guarded retirement is tracked in `Future_Cleanup.md`.

## Settings and Widget theme selection

The Themes tab has two landed catalogues:

- **Settings Themes** — `.srtheme`, Settings QWidget/native-window appearance;
- **Widget Themes** — `.srwtheme`, runtime retained-widget/overlay semantic colours.

The two catalogues use explicit stable IDs and a bidirectional **Linked / Independent** control. While Linked, selecting either side transactionally selects and persists the exact counterpart on the other side. Selection does not silently unlink. A theme with no valid counterpart requires Independent mode before it can be selected independently.

Widget themes are **colour-only schema-v3 bundles**. They do not own a backdrop/material recommendation and there is no runtime Surface Style preference. Settings theme names may legitimately retain `[Glass]`/`[Acrylic]` because those tags describe the Settings HWND; Widget counterpart names/files intentionally omit those material suffixes while `linked_settings_theme_id` still points to the exact Settings-theme identity.

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

`local.*` is runtime context and is never serialized. A default-valued stored family swatch is the implicit **Inherit** state; a genuinely changed family value remains an explicit family override. Related controls belong in semantic buckets rather than one giant Appearance section. Media is the reference: `Header Appearance`, `Seek Bar` and `Volume Control` expose meaningful family-facing roles while lower-level transport/mute/panel/icon roles remain theme-inherited.

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
- **Card Border Width** — global card geometry style, outside Widget Theme schema.

There is **no Surface Style / Theme Default / Normal / Glass / Acrylic runtime control**. Runtime card backdrop materials were physically rejected and removed; see `Docs/Historical_Bugs/Runtime_Card_Backdrop_Materials_Rejected_2026-09-02.md` and the detailed failed-method ledger in `Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md`.

## Theme-file layout

Theme files use one root with a Widget subfolder:

```text
installed/frozen: %ProgramData%\SRPSS\themes\*.srtheme
                  %ProgramData%\SRPSS\themes\widgets\*.srwtheme

source/dev:       <repo>\themes\*.srtheme
                  <repo>\themes\widgets\*.srwtheme
```

The Settings/Widget catalogues consume directories injected/resolved by startup/build authority. Do not duplicate path policy inside renderers or merge ProgramData and repository catalogues simultaneously. The repository/bundled tree is the development/bootstrap source; ProgramData is the installed stable root. Installed theme files are read-mostly catalogue assets; automatic Widget `Custom` state lives in Settings persistence.

## Runtime card and shadow destination

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

No menu-open/per-frame Settings read is allowed. The menu uses the same ordinary RGBA semantic-surface architecture as runtime cards; Settings HWND Glass/Acrylic does not authorize a runtime menu/card material path.

## Header styling

`header_enabled` gates destination header-shadow semantics where applicable. Branded Media/Gmail/Reddit/Achievement Pulse/Abandonment Issues headers consume `BrandedHeader.qml`; accepted geometry/casing/intrinsic-width behavior, logo/text shadows and extension-shadow treatment are shared J/J+ presentation contracts rather than family-local reinventions.

Header Fill/Border/Text remain family swatches where exposed, with canonical/default values inheriting through Widget Theme roles. Do not substitute unrelated semantic values because they are convenient: a header border derives from header/border authority, not a low-alpha row separator.

The small retained `MultiEffect` use in branded headers/artwork is local image treatment/masking only. It is not permission to restore full-card or full-display backdrop capture.

## Specialized local fallback guard

A specialized role may share a semantic parent without sharing the same accepted default pixel. Callers must supply the specialized current/default value at the relevant `local.*` terminal. For example, `media.volume.fill` and `media.progress.fill` can both inherit a theme-authored accent, while Default Dark may preserve distinct family-local fallback pixels when no theme/override owns them.

## Sectional navigation

Sectional pill navigation is renderer/layout structure, not a new theme semantic. Settings tabs should reuse the existing `navigation.subtab.*` roles unless a genuinely distinct visual concept appears. Geometry/padding may have a narrow component style owner without expanding every `.srtheme`.

## Clock analogue

`Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md` remains the permanent special-shadow contract. Global direction applies to directional analogue shadows; do not flatten analogue ring/marker/numeral/hand relationships into generic card/text recipes.

## Change process

```text
identify current product/style contract
-> reject obsolete/duplicate owners
-> update the retained destination owner
-> focused source tests
-> physical review where subjective
-> reconcile docs/test ownership
```

No fidelity downgrade is admitted as a performance shortcut. Settings native materials and runtime Widget semantic colours are separate architectures and must remain separate unless a future independently justified renderer redesign explicitly proves otherwise.

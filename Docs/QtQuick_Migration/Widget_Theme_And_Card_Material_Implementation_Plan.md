# Widget Theme + Card Material — Implementation Plan

Date: 2026-09-02

Consolidated, source-grounded execution plan for the committed J+ Widget Theme /
Glass / Acrylic work. This document sequences the build; it does **not** override
the durable design. Design authority remains, in order:

- `Docs/Contracts.md`;
- `Docs/Settings_Theme_Architecture.md`;
- `Docs/Custom_Style_Implementation.md`;
- `Future_Work.md` §10;
- `Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md` §10.

If this plan and those docs disagree, correct this plan.

## 0. Non-negotiable invariant — Dark is the guaranteed default

Exactly like Settings' compiled `DEFAULT_DARK_SETTINGS_THEME`, Widget Themes have a
compiled `DEFAULT_DARK_WIDGET_THEME` fallback. No files, invalid files, an unknown
selection, or a corrupt `Custom` snapshot must still resolve to a coherent theme and
`normal` material. Persistence must resolve the saved selection before first runtime
composition rather than deliberately flashing Default Dark first.

The optional `themes/widgets/Default Dark.srwtheme` is only a canonical mirror /
authoring convenience. The compiled object remains fallback authority.

## 1. Current implementation frontier

### Phase 1a — implemented at Claude checkpoint `f0564449`

The semantic/state-machine foundation is present and merged into the R-76 authority:

- `ui/widget_theme_spec.py` — schema, stable IDs, semantic palette, material default,
  compiled Default Dark and `effective_card_material_mode` resolver;
- `ui/widget_theme_io.py` — strict whole-or-reject `.srwtheme` IO and safe fallback;
- `ui/widget_theme_catalog.py` — built-in-first catalogue and injected-directory
  discovery;
- `ui/widget_theme_runtime.py` — Keep Synced identity rule, Custom snapshot and
  material resolution;
- `tests/test_widget_theme.py` — focused resolver/IO/catalogue/Custom contract.

Claude's focused Phase-1a gate was 24/24 green. This reconciliation environment can
run the pure tests but cannot claim PySide/Quick runtime acceptance.

### Existing source to reuse, not fork

- Settings theme stack (`settings_theme_spec/io/catalog/runtime`);
- reserved Widget Themes page in `ui/tabs/themes_tab.py`;
- `Settings -> Widgets -> General -> Appearance` in `ui/tabs/widgets_tab.py`;
- per-generation retained appearance snapshots in `DisplayManager`;
- ordinary family `OverlayCardStyle` projections and retained Context Menu;
- the existing per-widget card settings under `widgets.<family>.card.*`.

The current `ui/settings_theme_paths.py` packaged-path placeholder is temporary.
The durable shared root is:

```text
installed/frozen: %ProgramData%\SRPSS\themes
                  %ProgramData%\SRPSS\themes\widgets
source/dev:       <repo>\themes
                  <repo>\themes\widgets
```

One active root only; no ProgramData+repo merged catalogue.

## 2. The model — two orthogonal axes

### Theme identity / Keep Synced

`Keep Synced` defaults ON and links Settings-theme identity to a mirrored Widget
Theme using explicit stable IDs. Name matching is authoring convenience only.
Turning sync off permits arbitrary Settings + Widget Theme pairing.

### Surface Style

One preference:

```text
Theme Default | Normal | Glass | Acrylic
```

persisted as:

```text
card_material_override = theme | normal | glass | acrylic
```

and one resolver:

```text
effective_card_material_mode =
    widget_theme.default_card_material_mode if override == theme
    else override
```

Surface Style never creates Custom, dirties a theme, or changes Keep Synced.

### Custom

Editing a **Widget-Theme-owned global/default value** snapshots the full resolved
named Widget Theme into Settings-persisted `Custom`, applies the edit there, selects
Custom and silently turns Keep Synced OFF. The source `.srwtheme` is immutable.
Custom is not a file and is preserved when temporarily switching/relinking themes.
A real `.srwtheme` exists only after explicit save/export/authoring.

## 3. Palette precedence — resolved 2026-09-02

Existing per-widget swatches are real authored user settings and are **not** silently
reclassified as Widget Theme state.

For ordinary widget families, Widget Theme card roles are global defaults/baseline:

```text
effective family card value =
    explicit widgets.<family>.card.* value, when authored/present
    otherwise Widget Theme baseline role
```

Therefore:

- selecting a Widget Theme must not stomp existing family-specific card choices;
- a family swatch edit remains family-specific and does **not** create Widget Theme
  `Custom`;
- editing a Widget Theme-owned swatch in the Widget Themes UI does create Custom;
- the Context Menu has no family override layer, so its palette comes directly from
  the active Widget Theme;
- material resolution remains global/orthogonal; per-widget colour precedence does
  not create per-widget Glass/Acrylic material owners.

This resolves Claude's pre-1c design question in favour of **theme defaults with
explicit per-widget overrides winning**. Do not ship a temporary 1c that globally
stomps those values and promises later reconciliation.

## 4. Phase 1b — persistence + UI

Land the Settings model/keys:

```text
widget_theme.selected_id
widget_theme.keep_synced = true
widget_theme.card_material_override = theme
widget_theme.custom
```

Then populate:

- Themes tab -> Widget Themes selector + Keep Synced;
- Widgets -> General -> Appearance -> Surface Style;
- Theme Default/Normal usable on the current Normal renderer;
- Glass/Acrylic visible but disabled until the material path is admitted.

Do not hide colour swatches merely because a named Widget Theme is selected.

## 5. Phase 1c — retained runtime palette/material snapshot

At generation/configuration authority:

1. resolve active Widget Theme once;
2. resolve `effective_card_material_mode` once;
3. retain the global Widget Theme palette as the family fallback;
4. resolve each family card style with explicit family values above that baseline;
5. feed the Context Menu directly from Widget Theme palette;
6. keep effective material `normal` in this phase.

No per-tick Settings reads, theme catalogue reads, timers, capture or blur work.

Acceptance includes explicit tests for:

- Default Dark with zero files;
- invalid file / corrupt Custom whole fallback;
- Keep Synced identity behavior and explicit material-override survival;
- named theme -> Custom + auto-unsync for theme-owned edits;
- family swatch override winning over theme baseline without creating Custom;
- family with no explicit override inheriting the active Widget Theme role;
- Context Menu direct global Widget Theme inheritance;
- Surface Style change not creating Custom;
- zero new steady-state cadence/render work.

## 6. Phases 2–7 — scene-local material, after Phase 1 acceptance

2. Prototype one per-display reduced-resolution background-only Quick source + one
   shared bounded blur, consumed by one test card.
3. Prove transition/CUSTOM geometry and temporal correctness from the same frame
   state before widening coverage.
4. Add the Glass card-local recipe and measure.
5. Add Acrylic through the same shared backdrop with stronger cheap local treatment;
   then enable Glass/Acrylic through the existing resolver.
6. Only if measured Quick capture/effect cost is unacceptable, consider producing
   the shared backdrop beside `BackgroundRenderNode` from the same frame state.
7. Retire shared resources when the last Glass/Acrylic consumer disappears so Normal
   returns to current cost.

Hard rules: one lazy shared per-display backdrop/blur (or tiny measured tier set), no
per-card capture/FBO/blur, no Python readback/CPU blur, no second QQuickWindow, no
Settings HWND AccentPolicy on runtime Quick cards, and Context Menu reuses the same
scene-local material authority.

## 7. Settled design questions

1. **Default Dark provenance:** compiled fallback authority; optional on-disk canonical
   mirror only.
2. **Palette precedence:** Widget Theme is global baseline; explicit per-widget card
   swatches win; Context Menu is direct/global.
3. **Link metadata:** explicit stable IDs; pack tooling may pair by name but runtime
   never depends on display names.

These are no longer blockers for Phase 1b/1c.

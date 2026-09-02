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

Claude's focused Phase-1a gate was 24/24 green.

### Slice 8 semantic-role foundation — implemented, runtime/UI adoption still partial

The palette vocabulary is now schema-v2 and supports **sparse optional visual roles**
without making every new decorative role mandatory in every `.srwtheme`. The strict
whole-or-reject core card/context role set is now named separately from compiled
Default Dark, allowing Default Dark to materialize optional roles needed to preserve
accepted current pixels while old schema-v1 core-only themes still migrate in memory.

One Qt-free resolver owns the cascade:

```text
intentional per-widget override
    -> exact family/widget theme role
    -> shared semantic parent role
    -> local/current semantic role (`local.*`, never serialized)
    -> preserved current fallback
```

The first retained consumers are wired at construction/generation boundaries: shared
branded headers; Media transport/mute/volume/progress; Gmail/Reddit/Weather/Clock
separators and Gmail action popup; Steam info/tooltip/artwork/gradient/metric surfaces;
and the retained Context Menu palette. Context Menu Default Dark was reconciled to the
accepted current QML pixels **before** replacing those literals with one per-generation
projection, so semantic ownership does not itself recolour the shipped default.

Shared fades are also centralized: `ArtworkFadeImage.qml` uses gentler event-driven
`200 ms` out / `340 ms` in timing, and `MediaMetadataColumn.qml` performs a presentation-
only old->new metadata crossfade while model/provider truth updates immediately.

Focused semantic-role tests are green `13/13` when run through the Qt-free package shim
required by this environment. PySide6 is not installed here, so no Quick physical
acceptance is claimed. **Phase 1b still owns persistence/UI and setting the selected
active Widget Theme before retained presentation construction; Phase 1c still owns the
complete generation snapshot/card-material adoption.**

### Slice 9 bounded override UI + Media accessory — implemented, physical validation pending

Media now exercises the intended selective-override model rather than adding role-generated Settings clutter. Its controls are decomposed into collapsed `Header Appearance`, `Seek Bar`, and `Volume Control` buckets. Volume exposes Track/Fill/Outline; Seek exposes Track/Fill/Shadow/Glow; Header retains Fill/Border/Text. These persisted family swatches remain alpha-aware and become explicit semantic overrides only when they differ from canonical defaults.

The app-volume presentation is now an external scene-local right accessory lane using shared `OverlayWidget.rightAccessoryExtent/rightAccessoryContent`. The Media card retains/reclaims its accepted ordinary content width, the accessory remains inside the same retained root/lifecycle/uniform CUSTOM transform, and the global ordinary-card shadow excludes the accessory width. No second card/model/provider/service/poller or independent geometry authority is introduced. The Slice-8 white volume-fill regression is corrected by restoring the volume role's own local default instead of borrowing the seek/progress accent.

Steam header-size parity was also corrected at the asset boundary: both Steam families consume a tightly alpha-cropped derivative of the supplied padded Steam logo while retaining the same shared 25 px `BrandedHeader` logo box. There is no Steam-only header scale exception.

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

### 3A. Sparse semantic roles / GUI inheritance contract

Do not turn the expanded role vocabulary into dozens of permanent top-level swatches.
Specialized roles are optional and inherit. The normal/default state is effectively
**Inherit**. Existing family swatches participate as explicit overrides only when their
stored value differs from the canonical family default; default-valued persisted fields
therefore do not block a Widget Theme from styling that role.

`local.*` roles are presentation context only. They supply the accepted current widget
text/surface/border/accent/gradient value to the resolver when neither the selected theme
nor a semantic parent specifies something more precise. They must never be serialized
into `.srwtheme`, Custom snapshots, or Settings.

Sparse override UI should be exposed selectively and collapsed, not generated mechanically from the role graph. A named theme may define only broad roles (`widget.panel`, `widget.separator`, `widget.accent`) or exact roles (`media.transport.surface`, `steam.artwork.gradient.start`). Slice 9 is the first concrete family-override UX: Media keeps its high-value `Header Appearance`, `Seek Bar`, and `Volume Control` swatches as explicit family controls, while lower-level transport/mute/panel/icon roles remain inherited. These default-valued swatches are the implicit `Inherit` state; changing one intentionally promotes only that family role to the explicit override layer and does not create Widget Theme `Custom`. New widgets should consume the same resolver rather than inventing a family-local fallback/theme stack.

The resolver must also preserve **distinct local defaults under a shared parent**. Example: both `media.volume.fill` and `media.progress.fill` may inherit a theme-authored `widget.accent`, but when the selected theme does not author that parent the default volume fill remains its own muted gray/alpha and the seek/progress fill remains its own white/alpha. Do not populate a specialized role's `local.*` terminal from a sibling role merely because they share a semantic parent. Focused tests cover this regression.

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

1. resolve/set the selected active Widget Theme once before retained presentation construction;
2. resolve `effective_card_material_mode` once;
3. retain the global Widget Theme palette as the family fallback;
4. resolve each family card style with explicit family values above that baseline;
5. retain the Slice-8 semantic visual-role cascade for specialized surfaces rather than rebuilding family-local fallbacks;
6. keep the already-wired Context Menu direct palette projection generation-scoped and refresh it only through the admitted theme-generation path;
7. keep effective material `normal` in this phase.

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

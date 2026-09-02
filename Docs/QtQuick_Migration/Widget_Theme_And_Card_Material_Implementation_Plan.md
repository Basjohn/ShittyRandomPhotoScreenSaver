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

### Slice 8+ semantic-role foundation — usable wave implemented, physical review still open

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

The semantic wave is now broad enough for named Widget themes to be useful without pretending every decorative pixel is theme-owned: card surface/border/text, branded headers, Media controls/progress/volume, Gmail sender/read/timestamp hierarchy, Reddit age metadata, Steam secondary surfaces/metrics/artwork, and Context Menu are semantic consumers. Remaining editor/debug/legibility/shadow/fallback literals stay local until physical theme review proves they deserve public semantic vocabulary. PySide6 is not installed in the checkpoint environment, so Quick physical acceptance is still not claimed.

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

The packaged-path placeholder is retired. `ui/settings_theme_paths.py` now owns the durable shared root:

```text
installed/frozen: %ProgramData%\SRPSS\themes
                  %ProgramData%\SRPSS\themes\widgets
source/dev:       <repo>\themes
                  <repo>\themes\widgets
```

The normal and Media Center ISS scripts seed/clean-replace the ProgramData theme tree just like curated visualizer presets; both Nuitka builds already bundle `themes=themes`. Frozen runtime reads the ProgramData catalogue only rather than merging it with onefile/app-local copies. One active root only.

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

## 4. Phase 1b — persistence + UI — source-complete, validation pending

The Settings model now persists:

```text
widget_theme.selected_id
widget_theme.keep_synced = true
widget_theme.card_material_override = theme
widget_theme.custom
```

The Themes tab exposes a themed checkable `Linked to Settings Theme` / `Independent Widget Theme` control and Widget Theme selector. `Widgets -> General -> Appearance` owns Card Surface, Card Border and Surface Style **once for all widget families**. Surface Style is `Theme Default | Normal | Glass | Acrylic` through the Settings-themed `StyledComboBox`; changing it never creates Custom. Editing Widget-Theme-owned Card Surface/Border freezes the full resolved named palette into Settings-owned Custom and disables linking. Lazy Settings tabs refresh through event/navigation boundaries, not polling.

The curated mirror generator now produces one deterministic `.srwtheme` for every Settings `.srtheme` (50/50 at the 2026-09-02 checkpoint) with explicit stable `linked_settings_theme_id` metadata. Runtime linking never depends on display-name matching.

## 5. Phase 1c — retained runtime palette/material snapshot — source-complete, validation pending

At generation/configuration authority the selected Widget Theme and effective material are resolved before retained presentation construction. The active semantic palette is process-local construction state, not a per-frame/settings poller. Ordinary family card values follow:

```text
intentional family override -> Widget Theme baseline -> preserved local/default pixel
```

Visualizer consumes the shared card-shell baseline without changing DSP/viewport/reactivity authority. Context Menu consumes the generation-scoped Widget Theme palette directly. Default Dark's shared card values were reconciled to the accepted ordinary-family pixels before default-valued family settings became implicit Inherit, preventing the migration itself from recolouring shipped cards.

Current automated/source acceptance covers fallback/catalogue/link/Custom/material precedence and family inheritance. Real Qt/QML pixels still require the user-environment destination gate and physical review.

## 6. Phases 2–7 — shared scene-local Glass/Acrylic — source-complete, performance acceptance open

The current implementation is deliberately one **display-scoped** material facility:

```text
0 Glass/Acrylic consumers
    -> Loader inactive; no material ShaderEffectSource/MultiEffect

>=1 material consumer on a display
    -> one background-only ShaderEffectSource
       - live only while material is visible
       - recursive = false
       - 0.25 texture-size scale
    -> one shared MultiEffect blur + display-wide material mask
    -> ordinary cards / Visualizer / Context Menu contribute cheap masks + local tint only
```

Glass and Acrylic share the blurred backdrop and differ primarily in cheap local tint/material strength. No card owns a capture/FBO/blur, no second QQuickWindow exists, Settings HWND AccentPolicy is not reused, and no timer/poller/worker was added.

This is **bounded architecture, not proof of zero cost**. Qt documents blur as one of `MultiEffect`'s heavier effects and `ShaderEffectSource` as an extra FBO/memory cost. Acceptance therefore requires Normal-vs-Glass-vs-Acrylic measurement on 1/2/N displays and relevant DPRs: full-scene GPU/frame tails, offscreen/capture cost, texture memory, batching/overdraw impact, transition coherence and resource plateau. If the shared pass misses the envelope, optimize its resolution/bounds/shader strategy before considering any structural widening. Never solve it by creating per-card effects or reducing authored widget/Visualizer cadence.

## 6A. Deployment/resource contract

Runtime themes and runtime branding use filesystem assets, while Settings GUI micro-assets remain QRC resources:

- `ui/resources/assets.qrc` + generated `assets_rc.py`: embedded Settings fonts/icons (`:/ui/assets/...`);
- raw `images/`: runtime branded/widget imagery such as the cropped Steam logo;
- `%ProgramData%\SRPSS\themes`: installed Settings themes plus `widgets/*.srwtheme`;
- `%ProgramData%\SRPSS\presets`: installed curated visualizer presets.

Both QRC and raw asset lanes remain intentional. A missing `Steam_Logo_Cropped.png` cannot be repaired by regenerating QRC; the raw `images/` directory must be present in source/build packaging. When `assets.qrc` changes, regenerate `assets_rc.py` through `tools/regen_qrc.py`.

## 7. Settled design questions

1. **Default Dark provenance:** compiled fallback authority; optional on-disk canonical
   mirror only.
2. **Palette precedence:** Widget Theme is global baseline; explicit per-widget card
   swatches win; Context Menu is direct/global.
3. **Link metadata:** explicit stable IDs; pack tooling may pair by name but runtime
   never depends on display names.

These are no longer blockers for Phase 1b/1c.

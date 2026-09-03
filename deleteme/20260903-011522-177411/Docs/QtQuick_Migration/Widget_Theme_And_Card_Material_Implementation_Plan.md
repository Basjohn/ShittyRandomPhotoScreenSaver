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
- `Settings -> Widgets -> General -> Style Overrides` in `ui/tabs/widgets_tab_defaults.py`;
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

### 3B. Theme-system fragility / edge-contract audit — deliberately deferred

Do **not** reopen a broad semantic-theme coverage audit in this slice. After the material/parity/Foundry/submenu checkpoint, the next conversation should inspect only fragile ownership/transaction boundaries:

- stale Qt wrappers / QObject lifetime;
- lazy Settings-page state;
- bidirectional linked-theme transaction edges;
- retained-runtime recreation;
- material-mode propagation/admission/retirement;
- theme catalogue/path/build/install boundaries;
- swallowed live renderer failures;
- hidden polling/fallback/background owners.

This is not a literal-colour inventory, diagnostic-theme exercise or screenshot-diff campaign. Those broader semantic-audit mechanics are intentionally removed from the live plan.

## 4. Phase 1b — persistence + UI — source-complete, validation pending

The Settings model now persists:

```text
widget_theme.selected_id
widget_theme.keep_synced = true
widget_theme.card_material_override = theme
widget_theme.custom
```

The Themes tab exposes the same compact lock/unlock relationship control on **both** Settings Themes and Widget Themes pages. Locked means genuinely bidirectional identity: choosing a Settings theme selects its explicit Widget counterpart, and choosing a Widget theme selects its explicit Settings counterpart. A catalogue selection must never silently unlock the pair. If one side has no available counterpart (for example Settings-owned Widget `Custom`), the operator must switch to Independent first. The control is deliberately smaller than a general mode toggle and uses a small vector-style lock/unlock glyph; both copies reflect one persisted `widget_theme.keep_synced` state.

`Widgets -> General -> Style Overrides` owns Card Surface, Card Border, Surface Style and Card Border Width **once for all widget families**, immediately above Layout. Surface Style is `Theme Default | Normal | Glass | Acrylic` through the Settings-themed `StyledComboBox`; explicit modes are a material-only override and changing them never creates Custom. Editing Widget-Theme-owned Card Surface/Border freezes the full resolved named palette into Settings-owned Custom and disables linking because Custom has no paired Settings-theme identity. Card Border Width is global styling rather than Widget Theme schema. Lazy Settings tabs refresh through event/navigation boundaries, not polling.

The curated mirror generator now produces one deterministic `.srwtheme` for every Settings `.srtheme` (**58/58** at the 2026-09-02 follow-up checkpoint) with explicit stable `linked_settings_theme_id` metadata. The eight-theme expansion adds four genuinely light/white-adjacent themes and four silver/metal themes; regenerating the pack leaves the previous 50 Widget mirrors byte-identical. Runtime linking is resolved in **both directions from stable IDs** and never depends on display-name matching.
Theme Foundry now exposes `Save Widget Counterpart…` and calls the same `widget_counterpart_for_settings_theme()` authority as pack generation before strict-reloading the written `.srwtheme`. A file-authored draft first needs a real catalogue identity; compiled Default Dark can use its builtin stable ID directly and keeps its Widget-Normal exception. Foundry does not maintain a second converter.

### Live Settings QObject lifetime rule

Theme publication remains transactional, but a deleted Qt object is not a renderer failure. Python weak references are insufficient for PySide lifetime because a Python wrapper may temporarily survive after its C++ `SettingsDialog` has been deleted. Every live Settings-theme registry must therefore validate the underlying QObject (the root-QSS registry uses `Shiboken.isValid`) and prune stale wrappers before applying styles. A `RuntimeError` from a still-valid QWidget remains fatal and must still roll the theme transaction back. This rule prevents a dead prior Settings generation from blocking Glass/Acrylic/theme refresh on the current dialog without introducing polling or weakening failure visibility.

## 5. Phase 1c — retained runtime palette/material snapshot — source-complete, validation pending

At generation/configuration authority the selected Widget Theme and effective material are resolved before retained presentation construction. The active semantic palette is process-local construction state, not a per-frame/settings poller. Ordinary family card values follow:

```text
intentional family override -> Widget Theme baseline -> preserved local/default pixel
```

Visualizer consumes the shared card-shell baseline without changing DSP/viewport/reactivity authority. Context Menu consumes the generation-scoped Widget Theme palette directly. Default Dark's shared card values were reconciled to the accepted ordinary-family pixels before default-valued family settings became implicit Inherit, preventing the migration itself from recolouring shipped cards.

Clock is not an exception to Widget Theme text semantics: canonical/default Clock text resolves through shared `card.text`, while a genuinely authored Clock colour remains an explicit family override. The curated mirrors intentionally keep `card.text` close to white for legibility on wallpaper, so Clock may look much less dramatically recoloured than accent-heavy widgets. Do not force accent colours onto clock numerals/hands merely to make a theme visibly louder.

Current automated/source acceptance covers fallback/catalogue/link/Custom/material precedence and family inheritance. Real Qt/QML pixels still require the user-environment destination gate and physical review.

## 6. Phases 2–7 — shared scene-local Glass/Acrylic — v3.1 invalidation repair awaiting physical proof

The implementation remains one **display-scoped** material facility. The first layered-source physical run finally produced a slight visible Glass/Acrylic change, proving the shared `MultiEffect` composition route can work. That run also exposed a severe but narrow invalidation mismatch: the custom background rendered only once while transition lifecycle/perf counters continued and the Visualizer rendered normally. The material problem is therefore no longer "can Qt Quick render any special backdrop pixels?"; it is "keep the layered custom source live under SRPSS's existing transition cadence without adding a second cadence owner."

### Failed-attempt / evidence ledger

Preserve this history so later work does not circle back through already-falsified fixes:

- **v0, failed:** shared material Loader admission depended on `ordinaryCardMaterialMaskHost.children.length`. Dynamic Python-created mask reparenting made that an implicit change-notification contract.
- **v1, failed physically:** explicit retained `materialConsumerCount` fixed admission, but Glass/Acrylic still looked equivalent to Normal.
- **v2, failed physically:** Loader inputs became lexical QML bindings and the display-wide source/mask captures were explicit. Runtime diagnostics then proved mode/consumer/Loader/source/mask/captures/blur visibility all active, yet material pixels still did not become convincing. This moved the defect past admission/binding.
- **Retracted evidence rule:** custom-background render-count doubling is **not** a valid requirement for a working texture path. Qt can redirect a layered ancestor subtree into an offscreen target instead of drawing the custom node once to the window and again to the texture.
- **v3, failed as originally paced:** layer the actual displayed `backgroundPresentationHost` once and feed that texture directly to `MultiEffect`; retain only the one display-wide mask `ShaderEffectSource`. This finally produced a slight material effect, but Qt's layer cache froze the custom background because SRPSS transition progress lives inside `QSGRenderNode.render()` and only `QQuickWindow.update()` was requested each frame. Logs showed `BackgroundRenderNode.render_count=1` while transitions completed invisibly.
- **v3.1, current:** keep the v3 shared layer/effect/mask topology, explicitly keep `layer.live: true`, and reuse the EXISTING transition pacer to call `BackgroundRenderItem.update()` only while Glass/Acrylic is active. This gives the layer the source-item dirty edge Qt requires without a new timer, worker, polling loop or independent frame cadence. Normal unregisters the callback entirely.

The revised contract removes a redundant full-display texture stage:

```text
0 Glass/Acrylic consumers
    -> cardMaterialBackdropNeeded = false
    -> backgroundPresentationHost.layer.enabled = false
    -> material Loader inactive
    -> no material ShaderEffectSource / MultiEffect

>=1 material consumer on a display
    -> explicit retained materialConsumerCount / declarative mask visibility
    -> cardMaterialBackdropNeeded = true
    -> the ACTUAL displayed backgroundPresentationHost becomes layer-backed once
       (single shared background texture authority for that display)
    -> while a transition is active, the EXISTING transition pacer also dirties
       BackgroundRenderItem once per already-authored presentation opportunity
       so the layer cache receives the source-item update edge it requires
    -> lazy Loader creates one display-wide combined-mask ShaderEffectSource
       - mask source remains logically visible
       - hideSource suppresses the mask geometry from ordinary scene composition
    -> one shared MultiEffect consumes backgroundPresentationHost directly
       - no second background ShaderEffectSource/FBO
       - hasProxySource should be false while the source layer is active
    -> ordinary cards / Visualizer / Context Menu contribute cheap masks + local tint only
```

The custom background is a `QSGRenderNode`. Qt explicitly permits a render node's effective render target to change when an item/ancestor is dynamically layer-backed, so the renderer must remain render-target aware. SRPSS's background node already derives its viewport from `renderTarget().pixelSize()` rather than assuming the window backbuffer. Making the displayed background host itself the layer source therefore gives the material pass the same pixels the user actually sees, instead of asking a separate `ShaderEffectSource` to recapture the custom render-node subtree.

The lifecycle diagnostic is updated accordingly. For an admitted material run it reports `source_layer`, `source_layer_live`, mask-tree visibility/capture, blur source binding and `blur_proxy`. The desired structural state is `source_layer=True`, `source_layer_live=True`, `mask_tree_visible=True`, `mask_capture_live=True`, `blur_visible=True`, `blur_source_bound=True`, and `blur_proxy=False`. In addition, the background render count must now advance during special-material transitions rather than remaining at one. Normal must keep source layer and Loader dormant. These logs remain samples at existing lifecycle edges only; they are not a timer, frame probe or second material authority.

Glass and Acrylic share the blurred backdrop and differ primarily in cheap local tint/material strength. Because v3 finally proved visible effect pixels but they were roughly half the desired strength, v3.1 raises the shared blur from 24px/0.72 to 32px/0.90 for physical acceptance. No card owns a capture/FBO/blur, no second QQuickWindow exists, Settings HWND AccentPolicy is not reused, and no material timer/poller/worker is permitted.

This architecture is still **bounded architecture, not proof of acceptable cost**. A layer-backed full-display background is intentionally one fewer explicit texture stage than the failed background-capture design, but blur remains expensive. The zero-cost baseline is structural: when the resolved mode is Normal, `backgroundPresentationHost.layer.enabled` is false, the material Loader is inactive, no material `ShaderEffectSource`/`MultiEffect` exists, and the optional layered-background transition-sync callback is `None`. There is no material timer/frame/polling owner. Visualizer and ordinary-widget presentation are siblings above/outside the layered background source, so this material path cannot become their cadence authority. Glass/Acrylic may add only one display-wide background layer, one shared `MultiEffect`, one shared mask capture, and one source-item dirty call on each transition opportunity that already exists. Once pixels are correct, acceptance must measure Normal-vs-Glass-vs-Acrylic on 1/2/N displays and relevant DPRs: full-scene GPU/frame tails, texture memory, overdraw/batching impact, transition coherence and resource plateau. Optimize the shared pass only after those measurements; never create per-card effects or reduce authored widget/Visualizer cadence/reactivity to pay for material.

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

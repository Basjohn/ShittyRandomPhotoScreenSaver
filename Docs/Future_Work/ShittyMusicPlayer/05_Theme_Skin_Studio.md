# 05 | Unified Theme, Optional ZIP Skins and Theme & Skin Studio

**Approved planning direction, 16 November 2026; scheduling clarified 23 Nov.** This is a bounded two-layer
appearance architecture, not a universal third-party skin engine or a change to the current runtime. **Current
M3 material work, M4 unified Appearance Theme and the Theme Studio are independently valuable Standard/Dashboard
work that stays active** in Current Plan 1B.8. The scoped ZIP-skin runtime, SMP-specific panes/previews
and the skin-authoring expansion at M10 remain deferred with SMP plan 02 §8.2B until **after Melt Pool,
Concrete Rain, a substantial QoL phase and explicit operator readmission** (Future_Work §2.5).

## 1. Two layers and deliberately small skin scope

**Theme (always):** one versioned Appearance Theme with one selected ID/styles every Settings window, ordinary widget, Context Menu, Media and SMP presentation. Semantic roles own common and optional `settings.*`, `widgets.*` and `smp.*` values for colours, fonts, surfaces/materials, face transparency bias, border-surface material, border transparency bias, border thickness and curve/corner geometry. Different scopes can deliberately use different values within the one theme. Native Settings HWND and Qt Quick render through separate adapters with honest material fallbacks.

**Skin (optional):** a bounded, explicit overlay of supported roles, state-dependent glyph/button artwork, custom PNG/SVG shells/masks, shapes and motion for an admitted presentation. It can override almost any supported semantic for that target, but cannot introduce new commands, arbitrary executable QML/JS/Python, shaders, audio/Visualizer ownership or saved layout mutations. Every component without skin support remains fully themeable. Removing a skin restores the resolved theme and user family settings.

**Initial supported targets:** `smp_full`, `smp_compact`, and separately admitted `ordinary_media` using the SAME existing Media component. A skin advertises its targets; the user enables each supported target. Only their intersection activates a skin. Ordinary Media defaults OFF on Standard and Dashboard even when SMP is playing. Do not turn every Gmail, Clock, Reddit, Steam or Settings component into an arbitrary image/mask skin surface in advance. Adding such a target later requires a genuine consumer and a measured bounded implementation, not a new generic renderer.

## 2. Timing and ownership

- **Current Plan 1B.8 M3 / 1.7b:** measured material-aware border ring with unchanged shared backdrop, Flat/Normal pixel fallback, DPR and corner proof.
- **Current Plan 1B.8 M4, pre-SMP:** unify Settings and Widget catalogue/theme selection into one authored semantic authority. Theme-authored face/border transparency bias (-1..1 with neutral 0), face/border material, border thickness and four-corner curvature including concentric inner contour are first-class and independently scoped. Existing user Style Overrides apply *relative* to authored baselines; a neutral user override inherits them. No double material density or faux glass.
- **SMP M0/M1:** consume the already unified theme; build the minimal `.srskin` format, safe loader, appearance-context lookup and one demonstration on actual pane/Media QML. Do NOT build a giant skin framework or the whole Studio.
- **SMP M7:** prove full/compact styling in Standard/Dashboard compositor and standalone player, the optional user-enabled ordinary Media target, unchanged unrelated widgets and Settings, accessibility, mixed DPI, lifecycle and no playback/Visualizer restart.
- **Theme Studio, current-product scope (operator, 21/23 Nov):** after the native core, the flip and M4, independently of SMP M0: the visual editor of the unified theme over the production renderer (Current Plan 1B.8, "Theme Studio"). No SMP skin or pane implementation is necessary.
- **SMP M10, after M9 release:** the same Studio gains skin authoring and the SMP Full/Compact previews over the production skin loader. It is an authoring milestone, NOT a second runtime theme migration, a second Studio or a player-release prerequisite.

## 3. One Themes tab and scoped opt-in

The post-M4 Themes tab has one **Appearance Themes** page (one global selected theme) and a **Skins** page (skin preview/selection, optional Inherit/Coordinated/Independent colour/material mapping and `Apply To` targets). The target list is derived from a small explicit supported-target registry intersected with the skin's manifest, not from an independently maintained catalogue of every widget. Show unsupported targets greyed out with an explanation if helpful. Never add permanent skin-toggle glyph buttons to every live widget; the existing Edit/hover controls have separate purposes.

Skin application is an explicit appearance context, NOT the name of the current music provider. `smp_compact` and `ordinary_media` are distinct eligible contexts even though both reuse `MediaPresentation.qml`. The ordinary card always follows the base theme unless the manifest explicitly supports `ordinary_media` AND the user turns it on for that profile. Profile-specific choices cannot mutate the user's selected global theme or another profile's skin settings.

## 4. `.srskin` is a safe, self-contained ZIP

**Decision:** an `.srskin` file is a standard ZIP with a versioned `skin.json` manifest and optional `assets/` directory. ZIP is a better *distribution and installation* unit than a live loose folder: atomic import, integrity, removal and sharing. Studio edits a working project directory and exports a validated, reproducible ZIP. Production uses installed immutable validated bundles, never arbitrary working directories as a second source of truth.

Manifest: stable namespaced ID, format/revision, supported target IDs, common + Full/Compact variants, sparse semantic override roles, per-role normal/hover/pressed/focused/disabled/playing assets, hashes, intrinsic dimensions, stretch/nine-slice/vector rules and declared optional features. Missing optional art reverts to built-in vector icons. Asset mappings cannot change the semantic action, hitbox, keyboard focus, accessible name, tooltip or playback command.

Validation: reject absolute or traversal paths, symlinks, case-insensitive name collisions, unexpected file types, corrupt hashes, unsupported manifest, excessive members/unpacked bytes/ratio, high decoded pixel counts and malformed SVG. Only static SVG and transparent PNG assets, with no scripts, external URL/resource references, executable content or runtime custom QML/JS/Python/shaders. Decode at activation/asset edges, cache within measured bounds, never per frame or on the audio thread. SMP disabled means no skin scan/decode/render work. Curated read-only skins and imported per-user skins have explicitly separate directories and stable-ID collision rules; their loader does not introduce a second *global-theme* catalogue.

## 5. Visual Theme & Skin Studio

The theme half comes first, pre-SMP (section 2); M10 adds the skin half (SMP previews, glyph/state mapping, shells and masks). Together they supply direct visual editing at the quality of the existing Visualizer Studios: live native Settings + Qt Quick widgets + Media + SMP Full/Compact preview; light/dark backdrops; real DPR and clipping; independently scoped surface/border materials, transparency bias, thickness and curvature; SVG/PNG drop and glyph/state mapping; unique shells, curved masks, scalable/nine-slice assets; hover/press/selection motion, reduced-motion previews and responsive layouts. Include source/inheritance inspector, one-click revert, gesture undo/redo, Save/Cancel, strict export/import roundtrip through production loaders and legibility/interaction diagnostics.

Studio edits **appearance**, not the Full section tree or user layout slots, and never starts another media/Visualizer backend. Existing Qt Quick components remain action/lifecycle owners. Skin authors can make a visually radical Full player and a completely different Compact shell, but only inside those components' admitted layout/hitbox constraints.

## 6. Migration and acceptance

Curated old linked `.srtheme`/`.srwtheme` pairs can be regenerated semantically into one M4 schema; preserving curated pair bytes or running two selectors forever is unnecessary. User-authored files/Custom settings should be migrated once where possible, or safely backed up and diagnosed without destructive silent loss. Retire old sync/mirror machinery only after M4 real rendering and Settings persistence prove correct.

Release/Studio proof: changing global theme affects all standard surfaces coherently; enabling a skin changes only opted-in declared targets; disabling returns them to the theme; ordinary Media and all unrelated widgets remain unchanged by SMP-only skin selection. No duplicate renderer/audio/Visualizer, no extra material capture, no per-frame skin parsing, no surprise geometry or linked-theme writes. An author can package and re-import a distinct Full/Compact skin without touching code. **Do not widen target coverage merely because the manifest makes adding names easy.**

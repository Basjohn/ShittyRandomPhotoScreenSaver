# Card Surface Materials (Acrylic, Glass, Frosted, Mica, Smoked)

Status: implemented 6 Nov 2026 (operator item "Widget card surfaces"), awaiting the lead's live check under game load
and the operator's eyes. Captures, cadence and cost: `.artifacts/evidence/widgets/surfaces/20261106_surfaces/` (local
evidence); code: `rendering/quick/render/surface_backdrop.py`, `rendering/quick/surface_backdrop_owner.py`,
`rendering/quick/widgets/surface_material.py`, `rendering/quick/qml/MaterialSurface.qml` and its shaders. This decision **supersedes** the 2 Sep 2026 rejection of runtime card
materials (`Docs/Contracts.md` "Runtime card surfaces", `Spec.md` Widget Themes, `Docs/Guides/10_WIDGET_GUIDELINES.md`,
`Docs/Guides/Custom_Style_Implementation.md`). The rejection record stays in git history
(`a36fd32d:Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md`) and is summarised in section 1
because its lessons bind this design.

Operator priorities, in order: (1) never risk damaging the compositor, (2) be as performance-neutral as possible,
(3) prove every result with captures, including during transitions.

## 1. Why the earlier attempts failed

The Sep 2026 J+ experiment ran four versions. Each failure has a distinct cause:

| Version | Mechanism | Result | Cause |
| --- | --- | --- | --- |
| v0 | A shared material `Loader` admitted when a QML mask host had children | Normal, Glass and Acrylic looked identical | Admission depended on an implicit scene-graph side effect (Python-reparented mask children) |
| v1 | Explicit consumer count | Still identical | Admission was never the rendering failure |
| v2 | Lexical source/mask bindings, a background `ShaderEffectSource`, `MultiEffect` blur | Every stage "active" in diagnostics, pixels unconvincing | The capture **re-rendered** `BackgroundRenderItem` into a Qt-owned offscreen target; its custom `QSGRenderNode` is written for the window target (it reads `renderTarget()` size, sets its own viewport) and the redirected copy was not the displayed frame. A "render count doubles" proof was invalid: Qt may redirect a subtree instead of drawing it twice |
| v3 | The displayed background host itself made `layer.enabled` and fed to `MultiEffect` | A small visible effect; **wallpaper and transitions froze** while counters advanced | A layer caches its subtree and re-renders it only when an item in it is dirtied. The transition node samples wall time inside `render()` and is not re-synchronised per frame, so the cached layer kept showing a stale frame |
| v3.1 | The transition pacer dirtied the layered background every frame | Card effect stronger, background still dead | Same root cause; the layer also put an offscreen pass between the transition renderer and the window (the "custom compositor" the operator rejected) |

Common thread: **every version tried to re-render, cache or redirect the wallpaper/transition renderer to obtain a
backdrop**. The renderer has one correct output: the window's own render target. Anything that moves it elsewhere
changes the compositor.

Related records that bind the design:

- **R-61** (Settings Glass): native composition families are not interchangeable, and successful API readback is not
  proof of a composed visual. Runtime cards must not borrow the Settings HWND/AccentPolicy stack at all.
- **R-63** (black flash): the window is deliberately 1-2 px larger than the monitor (one exterior overscan edge) to
  avoid fullscreen-flip promotion. Nothing may change window geometry, surface format, swap interval, present mode or
  the window clear behaviour.
- **R-95**: work prepared off the renderer must key on the renderer's own inputs; the backdrop therefore sizes itself
  from the render target the node is drawing, never from `display_bounds()` or the monitor rectangle.
- **R-74** (shadow overpaint) and R-108 (card chrome parity): card shadows sit beneath every card surface in their own
  lane; a material must not move shadows or re-stack cards.
- Compositor_Architecture §6-7: one `QQuickWindow`, `QSGRenderNode` direct GL is the only custom primitive, the
  Visualizer clip host is render-node-local and protected (CHK26 optimisations, commits ce07b991/07486d83/985b9d53).

## 2. Invariants a material must never touch

1. **Presentation timing.** No timer, no `FrameAnimation`, no change to the transition frame gate in
   `DisplayScene.qml`, no frame requests of its own during a transition. The swap interval, render loop and surface
   format are untouched.
2. **The transition/background render path.** `BackgroundRenderItem` stays directly parented to the scene root at
   z 0; no layer, no `ShaderEffectSource`, no reparenting, no redirect, no extra update. Its code is not edited.
3. **First frame and reveal.** Cards before the first refresh look exactly like Normal; the material never holds,
   delays or gates readiness or the coordinated reveal.
4. **Mixed DPR and multi-display.** One owner per display scene, sized from that display's own render target; no
   cross-display sharing.
5. **Secure desktop / helper / MC.** Same scene code; no native window calls, no DWM, no AccentPolicy.
6. **Visualizer freshness.** The Visualizer's GL content is never read back; nothing runs per Visualizer frame.
7. **Dormancy.** With every card Normal for the whole generation, the owner, its item, its render node and every
   card-side material item do not exist. Once some surface used a material in a generation and the last one goes
   Normal again, the item is parked: no GL objects, never traversed, no Python call (section 3.2).

## 3. Design: read the frame that was already drawn

```text
DisplayScene root
  z0  BackgroundRenderItem          (unchanged: wallpaper / transitions into the window target)
  z1  backgroundDimming             (unchanged)
  z2  SurfaceBackdropSource         (NEW, only while some surface is non-Normal)
        render(): blit the window target -> 1/2 res, dual-filter blur pyramid,
                  write a 2-level mip texture (level 0 light blur 1/4 res, level 1 heavy blur 1/8 res)
  z5  pixelShiftLayer -> cards: MaterialSurface ShaderEffect samples that texture through each card's rounded mask
  z300 ContextMenu -> the same MaterialSurface under its surfaces
```

The backdrop source is **downstream** of the compositor: it reads the pixels the background renderer has already
written into the window target this frame (render order is z order: render nodes without depth awareness put the
scene in the in-order alpha pass), and draws nothing into the window. The background renderer never knows it exists.

- **Blur once, share it.** One blit and one pyramid per display, at most once per refreshed frame. Cards and the
  Context Menu sample it; there is no per-card capture, blur or owner.
- **Screen-space sampling.** Each `MaterialSurface` derives its backdrop coordinate in the vertex shader from
  `qt_Matrix * vertex` (normalised device coordinates of the actual render target). It follows pixel shift, Edit
  drags, uniform CUSTOM scale and any ancestor transform with no binding, and samples the same window space the blit
  copied. No `mapToItem` binding, no per-move update.
- **Fail closed to Normal.** The backdrop texture starts transparent; every refresh writes alpha 1. A card shader
  mixes `Normal surface -> material` by the sampled alpha, so before the first refresh, after a resize before the
  next refresh, or when a refresh is refused (multisampled target, GL failure) the card is exactly its Normal colour.
- **Wallpaper layer only.** The backdrop is the wallpaper/transition layer plus dimming, not other cards and not the
  Visualizer. A card overlapping another card, or the Context Menu over a card, shows the wallpaper beneath. That is
  the price of never resampling the Visualizer or any card content; with the materials' tint it reads as a frosted
  panel, not a hole.

### 3.1 Cadence

The source node sits under an opacity node that is 0 (not traversed, no Python call) except while armed:

- **One-shot** on edges the scene controller already owns: presentation image published (new wallpaper, startup
  desktop capture, adoption after a transition), transition run cleared, root/window size or DPR changed, dimming
  changed, owner created. The node refreshes on the next rendered frame and reports back once (queued signal); the
  item then disarms at the next sync.
- **Continuous** while a transition run is set: the node is traversed on every frame the display renders anyway
  (the transition's own gated frames or the Visualizer frames that ride it) and refreshes when at least the
  measured minimum interval has passed since its last refresh (render-thread monotonic time; no timer). Frames in
  between reuse the last backdrop.
- Nothing else re-arms it: card moves, fades, hover, text and Visualizer frames never refresh the backdrop.

### 3.2 Dormancy and ownership

`SurfaceBackdropOwner` (Python, GUI thread, at most one per `QuickSceneController`) is created on the first
non-Normal surface of a generation. Demand is computed at style-application edges: the ordinary widget host knows
the materials of its live cards (`surface_materials`, maintained on create, restyle, retire, transfer and unexpected
Qt death), and the Context Menu adds its baseline material. The owner creates the source item (z 2), hands it to the
host (which sets it on every card) and to the Context Menu, and receives the controller's edges.

When demand returns to zero the controller unbinds every consumer and **parks** the owner: at the next sync the
render node frees every GL object (the consumers' shader nodes were cleaned up at the start of that sync) and the
opacity node stays 0, so the node is never traversed. A later material in the same generation wakes it. The item is
never deleted mid-generation; it dies with the scene root. (Deleting the Python item mid-generation through its
queued render-thread signal corrupted later QML objects in the hidden render-control harness; parking avoids the
deletion entirely.) GL is also released on `sceneGraphInvalidated` (direct connection, render thread); without a
current context the names are dropped without GL calls. Python keeps its paint nodes referenced for the item's life
and always returns the same root, so Qt never deletes a node Python still owns.

On the card side, `OverlayCard` gains one inactive `Loader` (the only Normal-path change, an inert QML object per
card, no scene-graph node); it loads `MaterialSurface` only when the card's material is not Normal and a source is
bound. While loaded, the card's `Rectangle` keeps its border and drops its fill (the material paints the fill).

### 3.3 Legibility

**One panel per card (acceptance pass, 7 Nov; supersedes the per-line rows and per-run plates of 6 Nov).** The
operator, on a Glass desktop: Media's darker section "should go up and slightly above the header and slightly below
the seek track", "that glass misplacement applies to every single widget", and the panels "shouldn't be sharp
corners ... inherit the roundness of our widget ... rather be slightly larger than slightly smaller ... 2-3 px from
the widget border". The 6 Nov rows (a rounded box behind each list line, Media's track text, Weather's boxes) read
as boxes hugging the text at arbitrary heights; the per-run plates as chips.

Inside the card the material draws the card's one legibility panel (`surfaceAt` in the shaders' shared `SURFACE`
block):

- it covers the whole interior 2.5 px inside the border (border width + 2.5 px from the card edge), so it runs from
  above the header to below the last element on every card, with the same inset everywhere; its edge is a 2 px soft
  step, so it reads as a deliberate panel with a thin rim of the bare material;
- its corners are concentric with the card: the card's own configured corner radius (the Widget Settings value the
  card uses) minus that inset, never under 2 px, so a square or small-radius card still gets a rounded panel;
- it applies a slight constant shift away from the text colour (darker under light text, which is every dark theme;
  lighter under dark text on light themes), then a contrast floor that pushes further only where the blurred backdrop
  would leave the theme's card text below **7:1** (`MaterialSurface.panelContrastFloor`; it was 3:1 while rows and
  plates carried small text). 7:1 for the full text colour is what keeps the faint runs at 4.5:1 (below). The
  backdrop is heavily blurred, so the adjustment is smooth, and it acts only where the backdrop is bright; the
  direction follows the text so a dark-text light theme is never darkened under its own text.

Nothing else darkens the card itself: no `LegibilityRow` sits on a card (Media, Reddit, Gmail, Feed list lines,
Weather, the Abandonment and Achievement shelves lost theirs), and `ShadowedText` loads no plate of its own (the
`surfacePlateEnabled` opt-out is gone with it). A `LegibilityRow` remains only where text sits on a control's own
further fill (Feed grid tiles, Friend Pulse rows and tiles, Games You Follow story tiles, System Stats metric panels,
Achievement capsules): it passes that fill as `underlayColor` (the floor is measured against what the text sits on),
sits 2 px inside that panel's border and takes the panel's radius minus that inset (never under 2 px), so it follows
the same rounded, concentric rule. It evaluates the identical surface, so where the card's panel already meets the
floor for its colours it draws nothing: no double darkening. Bars: `tests/test_surface_material_style.py`,
`tests/test_card_surface_panels.py`.

**Faint runs (lead review, 7 Nov).** Runs drawn at 55-76 % of their colour (Gmail's dates and menu glyph,
Media's PLAYING, Feed sources and ages, System Stats' notes) have no plate of their own, so the panel's floor must
carry them. Measured on Glass (Default Dark [Single], PERSONALSET 859804, 656207 and 670483; the run's colour
composited at its effective opacity over the glyph-hidden frame, WCAG, 5th percentile over the glyph pixels; worst
small faint run across Media, Gmail, Reddit, World News, Weather and System Stats):

| Design | Worst faint small run | Where |
| --- | ---: | --- |
| main (per-line rows and per-run plates) | 4.67 | World News source/age |
| one panel, floor 5:1 | 3.88 | Gmail date |
| one panel, floor 5.7:1 | 4.25 | Gmail date |
| one panel, floor 6.5:1 | 4.57 | Gmail date |
| **one panel, floor 7:1 (shipped)** | **4.70** | Gmail date |

Full-colour small runs are 5.6:1 or better at 7:1. The one run below (a Feed's refresh glyph at 32 %, 2.8:1) is an
idle icon, not text. Bar: `test_card_panel_holds_faint_small_runs_at_4_5` (Gmail and Media over a seeded busy
backdrop; Gmail fails at 5:1).

**Child controls.** Media's transport bar, mute button (`mute_button`) and volume track (`spotify_volume`, the external
rail) are material too (`ChildMaterialSurface.qml`, operator 7 Nov: "the volume child widgets inside layer should be
material surfaced", "the media controls would have the material on them"): each loads a `MaterialSurface` through its
own rounded shape, tinted by its own fill, while the card's material is active; the control drops its own fill (the
mute button its gradient) meanwhile. On Normal it is an inactive `Loader` and the control is unchanged.

- No inner rim ("the mute button shouldn't have an extra inside border"): a child passes a negative border width, so
  the shaders' panel covers its whole face (`plateInset` is -1 there); its own outline is its only border.
- The volume track carries no text: its tint takes 40 % of its fill's alpha and it has no darker panel
  (`legibilityPanel: false`), so the backdrop reads through ("deserves more transparency"); the level fill and
  outline sit on top unchanged.
- The transport glyphs are vectors (`MediaTransportGlyph.qml`): previous, next, play and pause share one stroke
  weight (at least 2 px) and one ink height and sit centred in their segments at every DPR. They were font characters
  ("←", "||", "▶", "→") in the card's font since the Quick port (ace52dcb, Phase F4; the QWidget painter had set
  pause in Segoe UI Bold), whose fallback arrows are hairline and sit on the text baseline; adee7b90 routed them
  through `ThemedText`. This changes Media's Normal pixels on purpose.

On a material the light-theme soft text halo (a blurred `MultiEffect` silhouette) is not drawn: over a colourful blur it
reads as haze around the glyphs, and the plate now carries the contrast. Hard (dark-theme) shadows are unchanged.

**Edges (light themes).** Inside the border the surface draws a dark hairline and, below it, a soft highlight, so the
pale light-theme border reads as an edge over busy wallpaper. It scales with the tint's luminance and is exactly zero
on dark tints. The outer card shadow (the shared shadow lane, R-74) is unchanged.

**Style sweep fixes outside the materials (6 Nov evening; they change Normal pixels on purpose, nowhere else):**

- Media's content column clipped at the padded content edge, cutting the transport bar's small offset shadow (and
  the artwork's) square at the bar's right and bottom edges: the "square bottom-right corner" on light themes. The
  column no longer clips; the card's own `contentPaintBoundary` still bounds every child at the card edge.
- The mute button sat 4 px from the bar's rounded end and read as part of the end cap. It now keeps the same gap on
  the right as above and below (never under 8 px; about 5 px further left at the default size), and the transport
  arrows' lane shrinks by the same amount.
- Friend Pulse's grid/row secondary texts and quiet-state texts did not pass `shadowSoft`, so light themes drew the
  hard dark-theme shadow glyph (doubled names). Every shadowed run now follows the light-palette soft shadow
  (`tests/test_surface_material_style.py` checks every `ShadowedText` in the scene QML).

### 3.4 The Visualizer card (included 7 Nov) and the System Volume OSD (excluded)

**Superseded decision.** The 6 Nov version excluded the Visualizer card ("a material quad beneath the most
timing-sensitive item for little visible gain"); the operator then saw Spectrum's opaque fill beside Glass cards
("Spectrum doesn't have the glass but an ugly opaque"). This is the acceptance pass the exclusion asked for.

- **What it is.** `VisualizerPresentation.qml` has one inactive `Loader` (`visualizerCardSurfaceMaterial`) at the card
  background's z, under the content host; it loads the same `MaterialSurface` while the card shell is on, the
  material is not Normal and the backdrop is bound, and the authored background `Rectangle` hides meanwhile. The
  border, the clip host and the render node are untouched (the protected CHK26 path, commits
  ce07b991/07486d83/985b9d53, is not edited). The material is a static quad: nothing runs per Visualizer frame; it
  samples the shared backdrop, which is captured below z 20, so the Visualizer's own pixels are never read.
- **Which material.** The Widget Theme baseline (`resolve_global_surface_material`, the same value the Context Menu
  takes; `engine/display_manager.py` projects it through `QuickSceneController.apply_visualizer_surface_material` once
  per display generation). There is no per-Visualizer Surface Material row. The controller counts it as backdrop
  demand only while the Visualizer's presentation root exists on that display, and binds the backdrop to it with the
  other consumers.
- **Fill and material.** The Visualizer-authored Fill is the material's tint, exactly as a card's surface colour is
  for every other card: its alpha moves the tint opacity inside the material's own range (Glass 0.05-0.28), which
  caps it so the glass always reads. Candidates rendered side by side (`visualizer_<mode>__glass*.png` in the
  evidence below): the authored Fill as tint (chosen), the authored Fill with its alpha capped at 25 %, and the
  Widget Theme's card colour ignoring the Fill. With the default Fills they are within a few levels of each other,
  because the legibility panel's floor dominates on a busy backdrop; the chosen one keeps the user's Fill meaningful
  (a strong Fill gives a more tinted glass) with no second colour path.
- **Which modes show it.** Spectrum, Spline Curve and Oscilloscope leave most of the card visible (opaque coverage
  of the interior 8 %, 9 % and 1 % in the canonical renders). Bubble, Extruded Bubble and Waveform Ribbon cover it
  completely (no visible change; Bubble differs only on about 60 edge pixels). Neon Lake covers 65 % opaquely and
  its translucent sky picks up a slight shift (at most about 50 levels on dark pixels, not visible at a glance).
  Voxel Sphere and Extruded Spectrum are frameless: no card, no material.
- **Normal.** The `Loader` is inactive: no item, no node; the scene is pixel-identical to before (renderer jitter
  of at most 1-2 levels, the same as two runs of identical code).

Evidence: `.artifacts/evidence/widgets/card_surfaces/20261107_before/`, `20261107_after/` and the per-widget
before | after sheets in `20261107_sheets/` (`tools/card_surface_capture.py`; every card alone on PERSONALSET
859804 under `Default Dark [Single]`, Normal and Glass, the Visualizer also Acrylic).

The System Volume OSD is a transient indicator in the foreground lane whose card style comes from its own config;
it stays Normal.

### 3.5 Materials

All materials share one shader, one texture and one sampling path; they differ only in uniforms. The tint is the
theme's resolved card surface colour; its alpha moves the tint opacity within each material's range.

| Material | Backdrop | Look | Extra cost over Normal |
| --- | --- | --- | --- |
| Normal | none | today's RGBA fill | none (no backdrop, no shader) |
| Acrylic | heavy blur | blur, saturation lift, luminosity layer, theme tint, fine static grain | backdrop refresh + one textured quad per card |
| Glass | light blur | clear, faint tint, bright edge highlight, slight refraction near the rim | same |
| Frosted | heavy blur | milky haze toward white, stronger grain | same |
| Mica | heaviest (level 1) | wallpaper-tinted, near-solid theme surface; refreshes at a lower rate | same quad; backdrop refresh only |
| Smoked | light-heavy mix | dark, desaturated tinted translucent | same |

## 4. Settings model and themes

**Superseded decision (6 Nov 2026, evening).** The first version kept `.srwtheme` files colour-only: "themes still
carry colours only; the old 'theme recommends a material' field stays rejected". The operator then asked for themes
to carry a material once the cost proved low ("we should if cost is low"; it is, section 6), so a Widget Theme may
now name one. What stays rejected is the Sep 2026 mechanism (the `default_card_material_mode` /
`card_material_override` keys, still stripped by `core/settings/widget_theme_input_compat.py`, and every capture,
layer and per-card Loader of that design), not the idea of a theme designed for a material.

```text
<theme>.srwtheme  "surface_material"    optional: normal | acrylic | glass | frosted | mica | smoked (absent = none)
widgets.global.surface_material        Theme (default) | Normal | Acrylic | Glass | Frosted | Mica | Smoked
widgets.<family>.surface_material       Inherit (default) | Normal | the five materials
```

- **Theme files.** `WidgetThemeSpec.surface_material` (`ui/widget_theme_spec.py`) is optional within schema v3:
  the strict loader (`ui/widget_theme_io.py`) accepts the key or its absence and rejects anything but a real
  material; the writer emits it only when set, so every older theme round-trips byte for byte. The Foundry editor
  (`tools/widget_theme_foundry.py`) shows and saves it; the Custom theme (a `replace` of the active spec) keeps it.
- **A pair's material has one owner: the mirror (AC-17, operator 7 Nov 2026: "[Glass]" and "[Acrylic]" themes give
  Glass and Acrylic cards).** A linked Widget mirror carries its Settings theme's backdrop material:
  `widget_counterpart_for_settings_theme` (`tools/generate_widget_theme_mirrors.py`, the one authority pack
  generation, the Theme Foundry and the Theme Sorter call) projects `backdrop.mode` once (each material to the
  same card material, `off` -> none; since 8 Nov 2026 the Settings window also takes Frosted, Mica and Smoked, so a
  pair keeps one material for the window and the cards) through `surface_material_for_settings_theme`. The runtime resolver never
  reads the Settings theme; under Keep Synced the selected mirror simply names the material, and
  `resolve_global_surface_material` / `theme_surface_material` read it as for any theme. So the canonical default
  pair (`Default Dark [Single] [Glass]`, Keep Synced) draws Glass cards on a fresh profile (accepted), and Style
  Overrides set to anything but Theme still win. The shipped mirrors got the key by a **one-key fill**
  (`python tools/generate_widget_theme_mirrors.py --fill-materials`, like the preset repair fill), never by
  regeneration: ten mirrors carry hand-authored colour roles (for example `media.volume.fill`) that the wholesale
  generator would erase, and it would also delete every unlinked theme in the folder (so it now refuses both unless
  a flag names each intent; with no arguments the script changes nothing). The fill refuses a file the canonical
  writer would not reproduce byte for byte. Two pairs name none: `Matte Graphite [Single]` (backdrop
  `off`) and the built-in Default Dark, whose Widget half is the compiled `DEFAULT_DARK_WIDGET_THEME`: the
  unconditional fallback and the process's initial active theme, kept Normal so the error path and an un-themed
  start stay dormant (its Settings half draws an Acrylic window, but its name carries no tag). The Themes tab tags
  a Widget theme's list label with its material (`Name [Glass]`); file names and stored ids are unchanged.
  Regression bar: `tests/test_theme_pair_surface_material.py`.
- **Material themes.** Fifteen material themes (6 Nov, three per material,
  unlinked, `theme_id` `widget:material:*`) cover the hues the first 100 rarely use (chartreuse, green, yellow,
  violet, blue and magenta borders/accents; light cards; green/magenta, yellow/blue, violet/gold, blue/lime
  pairings). They are unlinked, so Keep Synced (the default) refuses them; they are reached with Independent. Themes
  are authored content: tests check structure and that each of these unlinked material themes' own text roles reads
  at 4.5:1 on its own surface, never its values. The linked mirrors are not held to that authoring bar (their
  colours are their Settings theme's projection); 18 of the 98 material mirrors sit under it, mostly
  `widget.accent` on `widget.panel` (`Current_Plan.md` §4).
- **Baseline.** `Widgets -> General -> Style Overrides -> Surface Material` sets the baseline beside Card Border
  Width; its first option, **Theme** (the new default), follows the active Widget Theme's material and is Normal when
  the theme names none (`resolve_global_surface_material` / `theme_surface_material` in
  `rendering/quick/widgets/surface_material.py`). The explicit materials override the theme. Every ordinary card
  and the Context Menu inherit the baseline; an explicit per-widget value beats it.
- **Stored values.** The feature had not shipped when the default changed, but a stored `widgets.global.surface_material:
  "normal"` cannot be told apart from a choice: page saves write the whole `global` section, defaults included. So
  there is **no bridge**: a stored `normal` stays an explicit Normal override (`theme` and an absent value follow the
  theme), recorded in `Docs/Architecture/Persisted_Input_Compatibility.md`. A profile saved today with the old
  default needs one switch to Theme. The projection is one
seam: `family_binder` passes every ordinary family's style through `with_surface_material` (and Games You Follow's
visual style), which also resolves the active Widget Theme's `card.text` as the legibility reference.

Every card family declares `surface_material: inherit` in canonical defaults (Clock, Weather, Media, Reddit, Gmail,
System Stats, every Feed, and the four Steam cards), so a page save keeps it (`_widget_save_base` preserves canonical
keys a page does not expose). Each family page shows a **Surface Material** row beside its background controls
(`ui/tabs/widget_surface_material_row.py`: Inherit plus the six materials), loaded and saved through the existing
descriptor load and save edges. Clock 2/3 and Reddit 2 follow their first card's appearance, so they resolve through
`clock` and `reddit`. The System Volume OSD stays Normal. The retired
Sep 2026 keys (`card_material_override`, `default_card_material_mode`) remain stripped by
`core/settings/widget_theme_input_compat.py`; they are not revived or mapped.

## 5. Acceptance plan

- **Captures** (`tools/surface_material_capture.py`, hidden `QQuickRenderControl`, no window): the production
  `DisplayScene`, real `BackgroundRenderItem`, real family presentations, on the operator's wallpapers. Each material
  beside Normal, a dark and a light Widget Theme, a still frame, and mid-transition frames across several
  transitions including 3D ones; cards over busy and flat regions.
- **Cadence measurement:** per transition, the mean/max error between the backdrop refreshed every frame and at
  candidate intervals, to pick the smallest refresh rate that looks right.
- **Cost:** backdrop refresh (GPU `GL_TIME_ELAPSED`, render-thread CPU, GL call count) relative to the Crossfade
  control in `tools/overhead_baseline.py`; whole-frame GPU per material against Normal in the capture scene.
- **Dormancy:** `tools/overhead_baseline.py --compare` against the newest baseline, unchanged GL/Python call counts,
  and source/runtime tests that nothing material-related exists while everything is Normal.
- **Compositor safety:** the existing compositor, lifecycle, transition and render-node suites unchanged; a test
  that `BackgroundRenderItem` stays at z 0 directly under the root with no layer.
- **Live:** the lead's live check under game load, then the operator's eyes. Until then the plan item stays
  `[~] AWAITING VALIDATION`.

## 6. Measurements (6 Nov 2026, RTX 4090)

**Cadence.** Worst case: a card drawn over a backdrop one full refresh interval old. Six transitions (Wipe, Slide,
Block Spins, Glass Shatter, Cube Turn, Page Curl), five points each. The figure is the p99 of the per-pixel 8-bit
difference inside the cards (`tools/surface_material_capture.py --cadence`):

| Material | 165 Hz | 120 Hz | 60 Hz | 30 Hz | 20 Hz | Chosen |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Glass | 7-11 | 9-15 | 17-28 | 33-52 | 45-67 | every rendered frame (never stale) |
| Acrylic | 1-3 | 2-4 | 3-8 | 6-17 | 9-23 | 60 Hz |
| Frosted | 1-4 | 1-6 | 2-12 | 4-24 | 6-29 | 60 Hz |
| Smoked | 2-4 | 3-5 | 5-10 | 10-18 | 14-25 | 60 Hz |
| Mica | 1-2 | 1-2 | 1-3 | 2-6 | 3-9 | 20 Hz |

Criterion: at most about 12 levels. Refresh runs only while a transition runs, on frames the display renders anyway;
at rest the node is not traversed.

**Backdrop refresh** (`tools/overhead_baseline.py`, `surface backdrop/refresh`, control-relative):

| Target | GPU | in Crossfade frames | render-thread CPU | GL calls | Python calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2560x1440 | 0.058 ms | 3.2 | 0.154 ms | 67 | 176 |
| 3840x2160 | 0.045 ms | 2.0 | 0.111 ms | 67 | 176 |

**Card quads**, steady, still wallpaper, five cards on a 1600x900 scene: Normal frame 0.055 ms GPU. Each material
adds 0.006-0.008 ms (Acrylic +0.006, Glass +0.007, Frosted +0.008, Mica +0.006, Smoked +0.008), with no per-frame
Python.

**Full cost with rows (6 Nov evening, RTX 4090; the lead reports it to the operator).** Steady frame: the hidden
production scene on a still wallpaper (no backdrop refresh), each material against Normal measured alternately beside
it, median of best-of-4 frames; GPU is `GL_TIME_ELAPSED` around the scene render, CPU the render thread's wall time
for sync + render. "5 cards" is Weather, Media, Reddit, System Stats and a Clock; "4 list cards" is Gmail, a news
Feed, Friend Pulse and System Stats (about 45 legibility rows). 1440p and 4K are the 1600x900 layout at DPR 1.6 and
2.4 (`tools/surface_material_capture.py --cost --dpr D --card-set main|lists`). Backdrop refresh:
`tools/overhead_baseline.py --only surfaces --size WxH` (control-relative; refresh happens only on image edges and
during transitions, see 3.1).

| Cost over Normal | Acrylic | Glass | Frosted | Mica | Smoked |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1440p, 5 cards: GPU / CPU ms | 0.030 / 0.047 | 0.032 / 0.048 | 0.033 / 0.047 | 0.024 / 0.049 | 0.046 / 0.048 |
| 1440p, 4 list cards | 0.075 / 0.069 | 0.064 / 0.063 | 0.092 / 0.064 | 0.075 / 0.065 | 0.090 / 0.061 |
| 4K, 5 cards | 0.055 / 0.050 | 0.058 / 0.046 | 0.059 / 0.048 | 0.046 / 0.046 | 0.057 / 0.048 |
| 4K, 4 list cards | 0.091 / 0.070 | 0.103 / 0.071 | 0.095 / 0.066 | 0.093 / 0.065 | 0.117 / 0.082 |

| Backdrop refresh | GPU | Crossfade frames | render-thread CPU | GL calls | Python calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2560x1440 | 0.080 ms | 8.2 | 0.103 ms | 67 | 176 |
| 3840x2160 | 0.042 ms | 1.8 | 0.102 ms | 67 | 176 |

All Normal: zero. Normal measured against itself reads 0.000 ms GPU and 0.00 ms CPU (within ±0.006 ms noise), and with
every card Normal no backdrop item, material or row exists (`tests/test_surface_materials.py`,
`tests/test_surface_material_style.py`). Nothing runs in Python per frame. The full overhead benchmark against
`2026-11-06_90f65ee9` is unchanged in GL and Python calls for every transition and Visualizer except Extruded Bubble
and Shockwave Grid, the same two main changed before this work (above). Rows first computed their tone per pixel
(+0.14-0.16 ms GPU at 1440p); the tone is now computed once per row in the vertex stage (18 surface samples, 4
vertices) and each pixel only checks its own surface, which also made rows cheaper on the CPU than the per-run chips
they replace (chips: +0.11-0.19 ms render-thread CPU at 1440p, one unbatched node per run).

**Legibility, per text run** (`tools/surface_material_capture.py --legibility` and `--compare-legibility`): the
WCAG contrast of each run's own colour against the pixels under its glyphs (the frame re-rendered with all glyphs and
shadows hidden), 5th percentile over the glyph pixels, worst run over three wallpapers including the busiest:

| Material | Light theme small text, before → after | Dark theme small text, before → after |
| --- | --- | --- |
| Normal | 4.27 → 4.27 (the theme's own muted label) | 5.24 → 5.24 |
| Acrylic | 3.89 → 4.89 | 4.64 → 4.93 |
| Glass | 2.11 → 4.58 | 3.37 → 4.93 |
| Frosted | 2.64 → 4.91 | 3.67 → 4.92 |
| Mica | 4.47 → 4.90 | 5.02 → 5.19 |
| Smoked | 2.70 → 4.90 | 4.71 → 5.01 |

Large text stays at 4.0 or better everywhere (floor 3:1).

**Rows (style pass, 6 Nov evening; superseded 7 Nov by the one card panel, 3.3).** Same measurement, now over nine cards (Weather, Media, Reddit, System Stats,
Clock; then Gmail, World News feed, Friend Pulse, System Stats) and three wallpapers (busy 859804, mixed 670483, light
656207); worst run per cell, before (per-run chips) → after (rows):

| Theme, text | Normal | Acrylic | Glass | Frosted | Mica | Smoked |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Light, small | 4.27 → 4.27 | 4.88 → 4.76 | 4.58 → 4.93 | 4.90 → 4.72 | 4.87 → 4.94 | 4.57 → 4.90 |
| Light, large | 5.97 → 5.97 | 5.08 → 5.19 | 3.28 → 4.01 | 3.45 → 4.44 | 6.46 → 6.46 | 3.28 → 4.39 |
| Dark, small | 5.24 → 5.24 | 4.68 → 4.86 | 4.91 → 4.92 | 4.60 → 4.83 | 5.19 → 5.02 | 4.91 → 4.93 |
| Dark, large | 6.64 → 6.64 | 3.77 → 6.84 | 3.31 → 5.73 | 3.73 → 6.83 | 5.94 → 7.08 | 4.43 → 6.98 |

(The Normal 4.27 is the light theme's own muted System Stats label on its panel; Normal is not touched.) Crops at 1x
and 3x, busy/flat/mid-transition, dark and light: `.artifacts/evidence/widgets/surfaces_style/20261106_surfaces_style/`. Normal frames differ from before only by the renderer's
run-to-run jitter (at most 2 levels on about 1,200 pixels, the same signature as two runs of identical code); dark
material frames are unchanged outside the text runs.

**Dormancy.** The full overhead benchmark against `2026-11-06_90f65ee9` (baseline `2026-11-06_e61647f5.json`) shows
every transition and Visualizer case unchanged in GL and Python calls except Shockwave Grid and Extruded Bubble. Their
deltas (+1 GL, about +50 Python calls) come from main's own changes to those modes since that baseline; this branch has
no diff against main in any Visualizer path. With every card Normal, the scene contains no backdrop item and no
material shader (`tests/test_surface_materials.py`).

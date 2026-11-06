# Card Surface Materials (Acrylic, Glass, Frosted, Mica, Smoked)

Status: implemented 6 Nov 2026 (operator item "Widget card surfaces"), awaiting the lead's live check under game load
and the operator's eyes. Captures, cadence and cost: `.artifacts/evidence/widget_surfaces_20261106/` (local
evidence); code: `rendering/quick/render/surface_backdrop.py`, `rendering/quick/surface_backdrop_owner.py`,
`rendering/quick/widgets/surface_material.py`, `rendering/quick/qml/MaterialSurface.qml` and its shaders. This decision **supersedes** the 2 Sep 2026 rejection of runtime card
materials (`Docs/Contracts.md` "Runtime card surfaces", `Spec.md` Widget Themes, `Docs/Guides/10_WIDGET_GUIDELINES.md`,
`Docs/Guides/Custom_Style_Implementation.md`). The rejection record stays in git history
(`f8567436:Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md`) and is summarised in section 1
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
  Visualizer clip host is render-node-local and protected (CHK26 optimisations, commits 0abc479c/78ab96a5/a0bf7093).

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

Inside the card's padded content area the material adds a legibility layer: a slight constant shift away from the
text colour (darker under light text, which is every dark theme; lighter under dark text on light themes), then a
contrast floor that pushes further only where the blurred backdrop would leave the theme's text below a 3:1
luminance contrast. The backdrop is heavily blurred, so the adjustment is smooth. This follows the Studio rule (a
layer slightly darker than the base behind controls); the direction follows the text so a dark-text light theme is
never darkened under its own text.

### 3.4 The Visualizer card and the System Volume OSD are excluded

The Visualizer card keeps its Visualizer-authored Fill/Border/Opacity (outside the Widget Theme and its reset), its
shell is part of the protected render-node-local clip path (Compositor_Architecture §7.2, CHK26), and its interior is
mostly live GL content. Including it would add a material quad beneath the most timing-sensitive item for little
visible gain. The architecture does not prevent a later inclusion (the backdrop is captured below z 20, so the
Visualizer's own pixels would still never be read), but it needs its own acceptance pass.

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

## 4. Settings model

Materials join the Widget Theme model without changing the colour-only `.srwtheme` schema (themes still carry
colours only; the old "theme recommends a material" field stays rejected):

```text
widgets.global.surface_material        Normal (default) | Acrylic | Glass | Frosted | Mica | Smoked
widgets.<family>.surface_material       Inherit (default) | the six above
```

`Widgets -> General -> Style Overrides -> Surface Material` sets the baseline beside Card Border Width. Every
ordinary card and the Context Menu inherit it; an explicit per-widget value beats the baseline. The projection is one
seam: `family_binder` passes every ordinary family's style through `with_surface_material` (and Games You Follow's
visual style), which also resolves the active Widget Theme's `card.text` as the legibility reference.

Not yet built: the per-family **Surface Material** row on each family page. The resolver already honours
`widgets.<id>.surface_material`, but no family declares the key in canonical defaults, so a family page save would not
keep it. Tracked in `Current_Plan.md`. The retired
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

**Dormancy.** The full overhead benchmark against `2026-11-06_90f65ee9` (baseline `2026-11-06_e61647f5.json`) shows
every transition and Visualizer case unchanged in GL and Python calls except Shockwave Grid and Extruded Bubble. Their
deltas (+1 GL, about +50 Python calls) come from main's own changes to those modes since that baseline; this branch has
no diff against main in any Visualizer path. With every card Normal, the scene contains no backdrop item and no
material shader (`tests/test_surface_materials.py`).

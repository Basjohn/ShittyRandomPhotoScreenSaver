# Card Surface Materials (Acrylic, Glass, Frosted, Mica, Smoked)

Status: design accepted for implementation 6 Nov 2026 (operator item "Widget card surfaces"); runtime proof in
`.artifacts/evidence/widget_surfaces_20261106/`. This decision **supersedes** the 2 Sep 2026 rejection of runtime card
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
7. **Dormancy.** With every card Normal the owner, its item, its render node and every card-side material item do
   not exist.

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

`SurfaceBackdropOwner` (Python, GUI thread, one per `QuickSceneController`) exists only while the display's demand
count is non-zero. Demand is counted at style-application edges: the ordinary widget host counts cards whose
resolved material is not Normal; the Context Menu counts one when its resolved material is not Normal. The owner
creates the source item (z 2), hands it to the host (which sets it on material cards) and to the Context Menu,
receives the controller's edges, and retires the item when demand returns to zero or the scene retires. GL resources
are released on `sceneGraphInvalidated` (direct connection, render thread) and when the node is destroyed, as the
background node does.

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

### 3.4 The Visualizer card is excluded

The Visualizer card keeps its Visualizer-authored Fill/Border/Opacity (outside the Widget Theme and its reset), its
shell is part of the protected render-node-local clip path (Compositor_Architecture §7.2, CHK26), and its interior is
mostly live GL content. Including it would add a material quad beneath the most timing-sensitive item for little
visible gain. The architecture does not prevent a later inclusion (the backdrop is captured below z 20, so the
Visualizer's own pixels would still never be read), but it needs its own acceptance pass.

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
ordinary card and the Context Menu inherit it; an explicit per-family value beats the baseline. The retired
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

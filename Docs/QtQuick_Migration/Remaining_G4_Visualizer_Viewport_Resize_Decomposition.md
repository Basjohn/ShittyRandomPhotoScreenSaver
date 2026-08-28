# Remaining G4 — Visualizer Viewport-Extent Resize Technical Decomposition

Status: **deterministic implementation COMPLETE; only the deferred all-five-mode installed/eyes-on gate remains (after H)**  
Landed and test-gated for all five modes: geometry projection (§2/§5/§6), session scale/extent working state (§3),
overlay + QML edge handles (§4), scene-controller preview projection (§6), the manager viewport-edge adapter (§5),
the persistence round-trip incl. canonical-reset (§9), the live `presentation_viewport_extent` config route from a
CUSTOM edge drag into the next authored Bubble step, and Bubble's baseline-relative logical-domain reflow (§7) with
`viewport_resize_capable=True` flipped on. Canonical `(420,280)` stays a strict byte-identical no-op. Do not reopen
the deterministic work; the remaining eyes-on gate is correctly blocked on H.  
Checkpoint basis: `59f4a3c98235215a9ff89fc09e4cc979d1831e89`  
Work admission: `Current_Plan.md`

This is an implementation decomposition, not a changelog and not permission to redesign CUSTOM or the Visualizer.
Exact later source outranks owner names below; the state/ownership contracts do not change casually.

## 1. Required result

Visualizer CUSTOM geometry has two independent operations:

```text
wheel / corner handles
    -> uniform whole-size scale
    -> viewport extent unchanged

left / right edge
    -> viewport width only
    -> uniform scale unchanged

top / bottom edge
    -> viewport height only
    -> uniform scale unchanged
```

The destination geometry state is conceptually:

```text
origin
uniform_visual_scale
viewport_extent = (world_width, world_height)
```

Visible outer size is derived from the latter two. Do not create an independent persisted `width`/`height` authority that
can disagree with them.

All five current modes participate: Spectrum, Oscilloscope, Sine, Bubble and DevCurve. Bubble is not exempt.

## 2. Extend the landed seams; do not build a second resize path

Current legal flow is already almost correct:

```text
CustomLayoutOverlay.qml
    semantic pointer/handle input only
        -> CustomLayoutOverlayModel
            local -> global pointer conversion
                -> CustomLayoutManager retained resize adapter
                    -> CustomLayoutSessionItem working state
                        -> session change publication
                            -> QuickSceneController
                                -> canonical visualizer presentation geometry
                                    -> retained VisualizerPresentation / render node
```

Relevant current owners:

- `rendering/quick/qml/CustomLayoutOverlay.qml`
- `rendering/quick/custom_layout_overlay.py`
- `rendering/custom_layout_manager.py`
- `rendering/custom_layout_session.py`
- `rendering/quick/scene_controller.py`
- `widgets/spotify_visualizer/presentation_geometry.py`
- `core/settings/visualizer_mode_registry.py`
- existing visualizer logical/runtime mode owners

**Do not** create a visualizer-specific QML persistence owner, second edit overlay, second session, separate top-level resize
window, or another geometry map.

## 3. Working-state representation

`CustomLayoutSessionItem.current_size_payload` is the existing family-specific working payload carrier. Use that seam (or a
small explicit typed equivalent immediately beneath it) for canonical visualizer resize state.

The current G4 implementation largely reconstructs visualizer size from baseline geometry plus `resize_scale`. That is
sufficient for uniform scaling but cannot represent the required scale/extent distinction by itself.

For the visualizer, working state must carry enough information to resolve both independently:

```text
uniform_visual_scale
viewport_extent_width
viewport_extent_height
```

or an equivalent canonical `viewport_extent` pair.

Rules:

- `resize_scale` may remain a transient/session-relative helper for the already-landed uniform operation; it must never be
  repurposed as viewport extent.
- admission initializes the working payload from the current committed/resolved visualizer presentation, not from an
  arbitrary QML item size;
- uniform resize changes only effective uniform scale;
- edge resize changes only the selected extent axis;
- Cancel restores both baseline values exactly;
- Save commits both values exactly;
- geometry variant and display identity remain the existing `CustomLayoutKey` authority;
- layout slots replay the committed payload; they do not invent a second visualizer-size snapshot.

If compatibility `width`/`height` fields are temporarily required to read an old CUSTOM entry, normalize them once into the
canonical scale+extent representation. Do not keep both representations writable.

## 4. Overlay affordance

Do not make every ordinary resizable widget gain viewport edges.

The overlay model needs a distinct semantic capability for viewport resize, e.g. `viewportResizeCapable`, separate from the
existing whole-size `resizable` role.

For the current product:

```text
spotify_visualizer -> viewportResizeCapable = true
ordinary widgets   -> false
```

All five visualizer modes are destination-capable. Remove/replace the temporary Bubble false gate; do not use it to hide the
edge controls.

Add four retained same-scene edge hit regions:

```text
left
right
top
bottom
```

They emit only semantic handle id + pointer position through the existing model/manager resize seam. QML does no min-size,
DPR, persistence, mode geometry or Bubble math.

Keep the existing corner and wheel behavior unchanged.

## 5. Edge geometry math

Python/session geometry remains authoritative.

At resize start capture the same kind of immutable origin facts used by the existing corner path:

```text
origin outer rect
origin uniform scale
origin viewport extent
pointer origin
selected edge
```

For an effective current uniform scale `S`:

```text
right:  outer_width  = pointer_x - fixed_left
left:   outer_width  = fixed_right - pointer_x; update left
bottom: outer_height = pointer_y - fixed_top
top:    outer_height = fixed_bottom - pointer_y; update top

viewport_width  = outer_width  / S
viewport_height = outer_height / S
```

Only the selected extent axis changes. The opposite axis and `S` remain bit-for-bit/epsilon-equivalent to their working
values.

Use the existing Python-owned screen/minimum/clamp/transfer rules. Do not independently clamp in QML and then clamp again
in Python. A cross-display threshold remains G5 ownership; an edge drag is not permission to create a second display-transfer
algorithm.

Minimums must be expressed coherently with scale: a minimum visible outer width/height implies a minimum extent at the
current scale. Do not silently increase/decrease uniform scale just to satisfy an edge minimum.

## 6. Canonical presentation resolution

`QuickSceneController._sync_custom_layout_visualizer()` currently has a uniform-only projection shape: baseline
presentation + session `resize_scale` -> `resize_visualizer_presentation_uniformly(...)`.

Extend that projection so it consumes the **current effective scale and current viewport extent** from the session payload.
Do not infer viewport extent from the QML edit frame after the fact.

Keep geometry math in `widgets/spotify_visualizer/presentation_geometry.py`. Preferred shape:

```text
baseline/current authored presentation style
+ target uniform scale
+ target viewport extent
+ target origin/display bounds
    -> one ResolvedVisualizerPresentation
```

A small pure helper may be added if it avoids duplicating the baseline-style de-scaling/re-scaling already present in
`resize_visualizer_presentation_uniformly()`. Do not duplicate border/radius/shadow/content-inset scaling logic in
`QuickSceneController`.

The resulting single `ResolvedVisualizerPresentation` continues to feed shell, clip and custom GL. There is no alternate
render geometry.

## 7. Bubble spatial reflow

Bubble benefits from the viewport operation and must implement it.

Viewport changes are **latest spatial configuration**, not authored-time events:

```text
CUSTOM drag sample
    -> latest viewport bounds/configuration

VisualizerLogicalRuntime
    -> continues advancing on its existing authored cadence
    -> consumes current bounds when performing logical work
```

Do not tick Bubble from pointer events. Do not add a geometry timer. Do not discard authored logical steps because a resize
is in progress.

Spatial rules:

- circles remain circles;
- radius units remain coherent;
- velocity units/collision response are not multiplied independently by X/Y aspect ratios;
- widening/tallening expands the available logical domain rather than stretching existing bubble positions like a texture;
- shrinking uses the existing/canonical bounds reconciliation behavior for objects now outside the domain; do not globally
  normalize every position to percentages as an anisotropic pseudo-reflow;
- trails, ghosts, pops/transients and protected renderer-visible consequences remain BTF-bound;
- the operation must not become an excuse to retune Bubble speed/collision/elasticity/personality.

If there is no current presentation-neutral viewport configuration record on the logical side, introduce the smallest
immutable/source-equivalent record required at the runtime-controller boundary. Never pass `QQuickItem`, `QScreen`, QML
objects or render-thread state into Bubble simulation.

## 8. Other mode reflow expectations

At constant uniform scale:

- Spectrum recomputes bar distribution/layout from the current viewport;
- Oscilloscope recomputes waveform domain/placement without changing authored stroke scale;
- Sine recomputes its domain/placement without a second clock or stretched raster;
- DevCurve recomputes layer/domain placement while preserving authored stroke/specular/tuning semantics;
- Bubble follows section 7.

The existing Phase-D baseline/wide/tall renderer geometry proofs are the foundation. The missing work is exposing,
persisting and live-projecting the operation through CUSTOM for every mode.

## 9. Persistence and replay

The following must preserve scale and extent as separate state:

```text
live CUSTOM edit
Save
Cancel
geometry variants
layout slots Shift+1..0 / 1..0
cross-display transfer
DPR/display projection
runtime recreation from committed settings
```

Specific invariants:

- edge resize never rewrites ordinary ON/OFF, capability activation, provider/account/source settings or inactive geometry
  variants;
- corner/wheel never reset a previously committed non-baseline viewport extent;
- layout-slot replay restores both extent and scale from that slot;
- cross-display transfer changes display/rect projection only; it does not reset the visualizer back to 1.5 aspect;
- Cancel after arbitrary uniform+edge operations returns exactly to the admitted baseline payload and rect.

## 10. Focused implementation order

Use this order unless exact source proves a smaller equivalent slice:

1. Add explicit visualizer scale+extent working/persistence semantics and tests without new QML affordance.
2. Add pure presentation-geometry projection for arbitrary extent + scale.
3. Update `QuickSceneController` retained preview projection to consume that state.
4. Add overlay/model edge semantic capability and four edge handles.
5. Route edge begin/live/final through the existing manager/session owner.
6. Make all five mode policies destination-capable; remove the Bubble temporary gate.
7. Wire Bubble logical viewport configuration without changing its authored clock.
8. Close Save/Cancel/layout-slot/variant/cross-display round-trip.
9. Run deterministic all-mode + BTF gates, then eyes-on wide/tall behavior.

Do not start with Bubble retuning or QML geometry hacks.

## 11. Required tests

Extend existing permanent tests rather than creating a parallel framework:

- `tests/test_qtquick_custom_layout_overlay.py`
  - distinct edge handles only for viewport-capable visualizer;
  - semantic edge ids; no QML persistence/math authority.
- `tests/test_custom_layout_session.py`
  - independent working scale/extent; exact Cancel restoration.
- `tests/test_custom_layout_manager.py`
  - left/right/top/bottom anchor math, minimums, active variant only, no scale mutation.
- `tests/test_qtquick_visualizer_geometry.py`
  - arbitrary target extent + scale; baseline identity retained; no X/Y stretch.
- `tests/test_layout_slots.py`
  - scale+extent slot round-trip and ordinary ON/OFF/capability separation.
- current all-mode Quick renderer tests
  - baseline/wide/tall for all five.
- Bubble deterministic/BTF tests
  - same authored cadence and consequences before/through/after viewport changes.

Also prove retained scene/item/model/render identity does not recreate merely because an edge moves.

## 12. Rejected shortcuts

Do not:

- treat Bubble's current false capability flag as product intent;
- turn edge drag into X/Y scaling of final GL pixels;
- derive and persist only outer `width`/`height` with no scale/extent distinction;
- add a second visualizer size settings authority;
- update QML properties and call that persistence;
- recreate the visualizer item/render node on every drag sample;
- feed pointer cadence into Bubble logical cadence;
- normalize/retune Bubble behavior to hide bad geometry;
- create a visualizer-only edit overlay or accelerated window;
- reset viewport extent when corner/wheel scaling occurs.

## 13. GREEN definition

G4 correction is GREEN only when all five modes can be edge-resized live, Save/Cancel/slot/variant replay is exact,
uniform scale remains independent, Bubble remains BTF-clean, and the one-window/one-retained-owner architecture survives.

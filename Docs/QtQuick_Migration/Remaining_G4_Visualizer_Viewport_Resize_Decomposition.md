# Remaining G4 — Visualizer Viewport-Extent Resize Technical Decomposition

Status: **core implementation LANDED; bounded post-checkpoint audit corrections are PRIORITY before G7**  
Work admission: `Current_Plan.md`  
Correction playbook: `Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md`

The original G4 scale/extent architecture is landed and remains binding. An independent post-checkpoint audit found bounded
lifecycle/spatial omissions; do not interpret those corrections as a reason to redesign CUSTOM, change Bubble personality or
reopen accepted geometry architecture.

Exact later source outranks historical owner wording below.

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

Canonical geometry state:

```text
origin
uniform_visual_scale
viewport_extent = (world_width, world_height)
```

Visible outer size is derived from scale + extent. Do not create an independently writable persisted width/height authority
that can disagree with them.

All five current modes participate: Spectrum, Oscilloscope, Sine, Bubble and DevCurve. Bubble is not exempt.

## 2. Landed owner path

The retained destination path is:

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

Relevant owners include:

- `rendering/quick/qml/CustomLayoutOverlay.qml`
- `rendering/quick/custom_layout_overlay.py`
- `rendering/custom_layout_manager.py`
- `rendering/custom_layout_session.py`
- `rendering/quick/scene_controller.py`
- `widgets/spotify_visualizer/presentation_geometry.py`
- `widgets/spotify_visualizer/runtime_controller.py`
- `widgets/spotify_visualizer/bubble_frame_runtime.py`
- `widgets/spotify_visualizer/bubble_simulation.py`
- `core/settings/visualizer_mode_registry.py`

Do not create a visualizer-specific QML persistence owner, second edit overlay, second session, separate top-level resize
window or another geometry map.

## 3. Working-state and persistence contract

The landed session carries uniform and viewport operations independently. The contract is:

- admission initializes from current committed/resolved presentation, not arbitrary QML pixels;
- uniform resize changes only effective uniform scale;
- edge resize changes only the selected extent axis;
- Cancel restores both admitted baseline values exactly;
- Save commits both exactly;
- geometry variant and display identity remain the existing `CustomLayoutKey` authority;
- layout slots replay the committed payload rather than inventing a second size snapshot;
- canonical `(420,280)` does not require a redundant persisted `viewport_extent` key;
- returning a previously non-baseline committed extent to canonical must remove the stale persisted key.

Compatibility width/height fields, if read at all, must normalize once into the canonical scale+extent representation and
must not remain a second writable truth.

## 4. Overlay affordance

The retained overlay has a distinct viewport-resize capability separate from ordinary whole-size resize.

Destination policy:

```text
spotify_visualizer -> viewportResizeCapable = true
ordinary widgets   -> false
```

All five visualizer modes are destination-capable.

Four retained same-scene edge hit regions own only semantic pointer input:

```text
left
right
top
bottom
```

QML owns no minimum-size, DPR, persistence, mode geometry or Bubble math. Existing corner/wheel behavior remains uniform
scale.

## 5. Edge geometry math

Python/session geometry remains authoritative.

At resize start the owner captures immutable origin facts equivalent to:

```text
origin outer rect
origin uniform scale
origin viewport extent
pointer origin
selected edge
```

For effective uniform scale `S`:

```text
right:  outer_width  = pointer_x - fixed_left
left:   outer_width  = fixed_right - pointer_x; update left
bottom: outer_height = pointer_y - fixed_top
top:    outer_height = fixed_bottom - pointer_y; update top

viewport_width  = outer_width  / S
viewport_height = outer_height / S
```

Only the selected extent axis changes. The opposite axis and uniform scale remain unchanged. Minimum visible outer size maps
back to a minimum extent at the current scale; minimum enforcement never mutates scale.

Edge drag is not a second cross-display transfer algorithm.

## 6. Canonical presentation resolution

Quick presentation resolves from one canonical source shape:

```text
baseline/current authored presentation style
+ target uniform scale
+ target viewport extent
+ target origin/display bounds
    -> one ResolvedVisualizerPresentation
```

Do not infer viewport extent back from QML frame pixels. Keep border/radius/shadow/content-inset scaling in the shared
presentation-geometry owner rather than duplicating it in `QuickSceneController`.

The resulting one `ResolvedVisualizerPresentation` continues to feed shell, clip and custom GL. There is no alternate render
geometry.

## 7. Logical viewport configuration and precedence

Viewport extent is latest **spatial configuration**, not authored-time input:

```text
CUSTOM working change / ordinary committed presentation
    -> latest effective viewport configuration

Visualizer authored cadence
    -> next normal authored step consumes current configuration
```

No pointer event ticks Bubble. No geometry timer exists.

The core live route is landed, but post-checkpoint audit found that **committed presentation extent and temporary CUSTOM
working extent need explicit precedence/lifecycle ownership**. The correction is mandatory and is decomposed in:

`G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` §1.

Binding outcome:

```text
CUSTOM active  -> working extent temporarily wins
CUSTOM Save    -> new committed extent wins after override retirement
CUSTOM Cancel  -> pre-edit committed extent wins after override retirement
ordinary mode  -> current committed extent wins
```

“No active CUSTOM session” must never be treated as synonymous with canonical `(420,280)`.

## 8. Bubble spatial reflow

Bubble uses a baseline-relative logical world. Canonical `(420,280)` corresponds to the exact accepted unit-square path.
Wide/tall extents expand one or both logical axes; renderer-facing positions/trails/radius are projected back into the
existing normalized Quick render contract so circles and apparent scale remain coherent.

Spatial rules:

- circles remain circles;
- radius units remain coherent;
- stream/drift deltas project once onto each expanded domain axis so their normalized content-space travel remains stable;
- diagnostics and nonbaseline trail smear use renderer-content coordinates, avoiding the old `1 / domain_axis` visible-motion loss and wide/tall trail anisotropy;
- collision response remains separate from that stream/drift projection and is not retuned as a viewport workaround;
- widening/tallening expands available logical domain rather than stretching finished pixels;
- authored big/small counts and `MAX_BUBBLES` do not scale with viewport area;
- shrinking reconciles state through existing lifecycle semantics rather than percentage-rescaling positions;
- trails and protected renderer-visible consequences remain BTF-bound;
- Bubble speed controls, event envelopes, collision/elasticity personality, cadence and gain are not retuned for geometry.

The phrase **“baseline density” is incorrect and must not be used**. At fixed authored counts, a larger viewport is naturally
less dense.

Post-checkpoint audit found three Bubble-specific items still requiring deterministic closure:

1. overlap-retry clamp still contains the old `[-0.25,1.25]` unit-square bound;
2. contraction behavior for newly off-domain `reaches_surface=False` bubbles needs explicit bounded retirement/tests;
3. `spec_ox`/`spec_oy` coordinate semantics must be traced through the shader and corrected only if they are positional
   viewport-space values.

See the correction playbook §§2–4.

## 9. Other mode reflow expectations

At constant uniform scale:

- Spectrum recomputes distribution/layout from current viewport;
- Oscilloscope recomputes waveform domain/placement without changing authored stroke scale;
- Sine recomputes domain/placement without a second clock or stretched raster;
- DevCurve recomputes layer/domain placement while preserving authored stroke/specular/tuning semantics;
- Bubble follows §8.

The core operation is landed for all five. Final physical baseline/wide/tall acceptance remains deferred until after H.

## 10. Save/Cancel/replay invariants

The following preserve scale and extent as separate state:

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

- edge resize never rewrites ordinary ON/OFF, capability activation, provider/account/source settings or inactive variants;
- corner/wheel never reset a committed non-baseline viewport extent;
- slot replay restores both extent and scale from that slot;
- cross-display transfer changes display/rect projection only and does not force 1.5 aspect;
- Cancel after arbitrary uniform+edge operations returns exactly to the admitted baseline payload and rect;
- Save of a canonical reset removes stale persisted non-baseline extent;
- end-CUSTOM logical configuration resolves to the correct committed extent rather than unconditional canonical baseline.

## 11. Current correction implementation order

The original G4 implementation sequence is complete. The remaining deterministic order is now:

1. committed-vs-CUSTOM viewport configuration ownership/precedence;
2. Bubble overlap-retry domain clamp;
3. contraction retirement for non-surface off-domain bubbles;
4. specular offset coordinate-space audit/correction if required;
5. remove “baseline density” wording;
6. focused G4/Bubble regression bars;
7. full established BTF/cadence/replay/reactivity/transport regression sweep;
8. post-push self-audit and G4 deterministic-close status update;
9. continue directly into G7.

Do not stop for independent audit after G4 alone. `Current_Plan.md` owns the single audit gate after all of G is GREEN and
checkpointed.

## 12. Required permanent tests

Keep/extend destination tests rather than creating a parallel framework:

- `tests/test_qtquick_custom_layout_overlay.py`
  - semantic edge capability and live extent sink publication;
  - CUSTOM clear/save/cancel route as applicable.
- `tests/test_custom_layout_session.py`
  - independent working scale/extent and exact Cancel restoration.
- `tests/test_custom_layout_manager.py`
  - edge anchors/minimums/no-scale mutation;
  - non-baseline persistence and reverse round-trip to canonical.
- visualizer runtime-controller tests
  - committed extent vs temporary CUSTOM override precedence;
  - latest-state coalescing with no new clock.
- `tests/test_bubble_viewport_config_route.py`
  - latest extent enters each authored Bubble step; no geometry-driven step.
- `tests/test_bubble_viewport_reflow.py`
  - exact baseline/no-op;
  - wide/tall/shrink;
  - authored-count invariance;
  - overlap-retry extended-domain bounds;
  - non-surface contraction retirement;
  - canonical/wide/tall consume-once transient head/trail motion projection with identical radius sequence;
  - trail/radius projection;
  - specular coordinate contract if applicable.
- existing Bubble BTF/cadence/replay/reactivity/transport goldens
  - unchanged baseline behavior and protected consequences.

Also prove retained scene/item/model/render identity does not recreate merely because an edge moves.

## 13. Rejected shortcuts

Do not:

- turn edge drag into X/Y scaling of final GL pixels;
- derive/persist only outer width/height with no scale/extent distinction;
- add a second visualizer size settings authority;
- update QML properties and call that persistence;
- recreate the visualizer item/render node on drag samples;
- feed pointer cadence into Bubble logical cadence;
- normalize/retune Bubble behavior to hide bad geometry;
- scale particle counts with viewport area;
- keep `[-0.25,1.25]` as a non-baseline world clamp;
- treat end-CUSTOM as automatic canonical viewport;
- allow ordinary presentation publication and CUSTOM working publication to race as equal viewport truths;
- change specular offsets without first proving their coordinate space;
- create a visualizer-only edit overlay or accelerated window;
- reset viewport extent when corner/wheel scaling occurs;
- regenerate/loosen BTF goldens to bless baseline drift.

## 14. GREEN definition

Deterministic G4 is finally GREEN when:

- all five modes retain independent live edge extent and uniform scale;
- Save/Cancel/slot/variant/cross-display replay remains exact;
- committed vs temporary CUSTOM extent precedence is deterministic through edit/save/cancel/clear;
- no-session runtime resolves the actual committed extent;
- Bubble canonical path remains accepted/BTF-clean;
- Bubble non-baseline spawn retry, contraction lifecycle and specular coordinate semantics are correct/tested;
- authored counts/personality/cadence remain unchanged by extent;
- one-window/one-retained-owner architecture survives;
- no golden/threshold retuning was needed to preserve baseline.

The remaining all-five-mode installed/eyes-on viewport matrix is deliberately deferred until after H and remains J/physical
acceptance debt. Deterministic GREEN is not a claim that the final visuals have been physically accepted.

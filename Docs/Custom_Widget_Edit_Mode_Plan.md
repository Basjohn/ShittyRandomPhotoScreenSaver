# Custom Widget Edit Mode Plan

Last updated: 2026-05-18

This document is the detailed implementation plan for the future CUSTOM widget layout/edit mode.

It is intentionally more detailed than `Current_Plan.md`. The plan file should point here, not duplicate this content.

## 1. Purpose

Introduce an optional CUSTOM widget layout mode that lets users:
- reposition supported widgets per display,
- optionally resize supported widgets safely,
- commit those changes into a reusable `CUSTOM` slot,
- return to authored/default positioning whenever they want.

The goal is to give users meaningful control without destabilizing the runtime, breaking multi-monitor/DPR behavior, or forcing every widget into a one-size-fits-all layout contract.

## 2. Core Design Decision

The best long-term model is:
- use the existing descriptor/registry system as the ownership base,
- use a temporary edit-shell layer rather than manipulating live widgets directly by default,
- store committed CUSTOM layouts as display-local normalized rectangles,
- treat snapping as an editor affordance, not the persistence format,
- allow resize only where the widget has a safe authored size contract.

This is intentionally not a freeform raw-pixel editor.

## 3. High-Level UX Contract

### 3.1 Entry and Exit

- Edit mode is entered from the context menu.
- Edit mode is exited with:
  - `Esc` = cancel changes and leave edit mode.
  - `Enter` = apply changes and leave edit mode.
- Normal screensaver exit paths must be suppressed while edit mode is active.
- Mouse movement or clicks must not accidentally exit the screensaver while edit mode is active.
- Context menu should expose:
  - `Enter Edit Mode`
  - `Save Edits`
  - `Cancel Edits`
  - eventually `Reset CUSTOM Layout`

### 3.2 What the User Sees

- Each participating widget becomes a temporary edit shell.
- The shell should visually echo the real widget:
  - same overall size and shape,
  - same card/background family,
  - similar color/opacity treatment,
  - clearly marked as an editable shell rather than a live widget.
- The shell should display:
  - widget title/name,
  - current display identity if useful,
  - current position/size hints only if they help rather than clutter.
- The shell should not continue expensive live animation by default.

### 3.3 Reset Size Control

- If the widget supports resize, the edit shell should expose a size reset affordance.
- Best placement:
  - bottom-right inside the shell,
  - visually consistent across widgets,
  - always reachable,
  - disabled or absent for non-resizable widgets.
- Reset should restore that widget’s authored/default size contract for the current display context, not some arbitrary last-known dimensions.

### 3.4 Dragging Between Displays

- A widget may be dragged across display boundaries while the drag is active.
- When the user releases the drag:
  - the widget lands on the display containing the largest area of its visible bounds,
  - if there is an exact tie, prefer the display under the pointer at release,
  - if that still fails, prefer the source display.
- Users cannot commit a widget in a state where its committed bounds belong to two displays at once.

### 3.5 Edge Rules

- CUSTOM layout must ignore the normal widget margin system.
- Users may place widgets as tightly to the display edge as they want.
- The committed visible bounds must remain fully inside the destination display.
- “Inside the display” means the visible widget/card bounds do not breach the display rectangle.
- This clamp should use the same visible-boundary contract the runtime uses for positioning, not a misleading raw transparent QWidget/effect rect.

## 4. Non-Goals for First Implementation

The first implementation should not try to do all of these:
- no arbitrary per-pixel live manipulation of full runtime widgets if an edit shell can own the interaction,
- no forced resize support for every widget,
- no immediate horizontal-only or vertical-only resize for all widgets,
- no requirement that CUSTOM layouts preserve exact authored stack/margin semantics,
- no attempt to make every widget reflow perfectly under every resize shape from day one.

The right first goal is safe, comprehensible, reversible control.

## 5. Persistence Contract

### 5.1 Recommended Storage Model

Persist CUSTOM layout data as display-local normalized rectangles, not raw pixels.

Each committed widget instance should eventually store something shaped like:

```json
{
  "position_mode": "custom",
  "display_binding": {
    "selection_mode": "logical_display",
    "display_key": "screen-1"
  },
  "rect": {
    "x": 0.125,
    "y": 0.310,
    "w": 0.280,
    "h": 0.145
  },
  "size_mode": "default|scaled|custom_axes",
  "scale": 1.10,
  "custom_size": null
}
```

This should be understood as:
- `rect` is normalized within the chosen display’s usable layout plane,
- not a raw device pixel rectangle,
- and not tied to the old margin-based anchor system.

### 5.2 Why Normalized Rectangles Are Better

- safer across DPR,
- safer across resolution changes,
- safer across multi-monitor setups,
- compatible with future resize,
- flexible enough to support tight edge placement,
- does not force the persistence contract to match the editor’s snap grid.

### 5.3 Snap Grid Decision

Best decision:
- use a snap grid in the editor,
- do not store the grid itself as the canonical committed layout.

Reason:
- the user wants tight placement freedom,
- future resize needs rectangles anyway,
- normalized rectangles are the better long-term contract,
- snap granularity can evolve without schema churn.

### 5.4 CUSTOM Slot Behavior

- `CUSTOM` remains unavailable/greyed out until at least one valid committed layout exists.
- Users can switch back to authored/default positions at any time.
- CUSTOM is a first-class saved layout mode, not a transient override layer hidden somewhere else.

## 6. Descriptor Ownership Requirements

This work must extend `rendering/widget_descriptors.py`, not bypass it.

Descriptor-owned edit metadata should eventually cover:
- `supports_custom_move`
- `supports_custom_resize`
- `resize_mode`
  - `none`
  - `uniform_scale`
  - `axis_vetted`
- `resize_axes`
  - `uniform`
  - `horizontal`
  - `vertical`
  - `both`
- `size_reset_strategy`
- `edit_shell_style_family`
- `custom_layout_participation_phase`

The descriptor layer should remain the single place where we answer:
- can this widget move?
- can this widget resize?
- how can it resize?
- how is reset handled?
- should it be phase-one safe or deferred?

## 7. Runtime Architecture Recommendation

### 7.1 New Layers

The feature should be built with explicit seams, not by growing `WidgetManager` into a god object.

Recommended new modules:
- `rendering/custom_layout_contract.py`
  - schema helpers,
  - normalized rect conversions,
  - display-binding helpers,
  - clamp helpers.
- `rendering/custom_layout_manager.py`
  - owns active edit session,
  - shell creation/destruction,
  - commit/cancel,
  - mapping between runtime widgets and shells.
- `widgets/edit_shell_widget.py`
  - the temporary editable shell.
- `rendering/custom_layout_snap.py`
  - optional snap grid helpers and nearest-slot logic.
- `rendering/custom_layout_validation.py`
  - pre-commit bounds checks,
  - resize capability checks,
  - cross-display resolution.

These names are suggestions, but the seam split matters more than the exact filenames.

### 7.2 Interaction Ownership

Edit-mode interaction should be centralized, likely through:
- `rendering/input_handler.py` for mode-aware routing,
- `widgets/context_menu.py` / display context-menu seams for entry/exit,
- a dedicated manager for drag/resize lifecycle.

Do not bury CUSTOM layout logic inside each widget.

### 7.3 Live Widgets vs Edit Shells

Best default:
- use edit shells for most widgets,
- pause or freeze expensive live runtime paths,
- allow live-widget editing only when a widget is proven safe and materially benefits from it.

Why:
- protects timers/network/render paths,
- reduces focus and effect corruption risk,
- makes drag/resize math easier to reason about,
- gives us a clean UX surface for handles and reset affordances.

### 7.4 Visualizer Special Handling

The visualizer should use the new outer-card geometry contract as its CUSTOM-edit basis.

That means:
- do not resize the visualizer by bypassing `widgets/spotify_visualizer/card_geometry.py`,
- do not treat the stencil shell as the editable geometry owner,
- keep outer geometry, stencil, and per-mode inner adaptation separate.

For the first implementation, the safest options are:
- move-only, or
- move plus uniform scale routed through visualizer-owned outer geometry,
- not arbitrary axis resize.

## 8. Resizing Strategy Recommendation

### 8.1 Best First Resize Model

The safest first resize model is:
- uniform scale only,
- per widget family,
- only for widgets whose content and authored layout survive that scaling cleanly.

This should be triggered by:
- `Ctrl + mouse wheel`,
- and optionally later by corner handles for the same uniform-scale contract.

### 8.2 Why Uniform Scale First

Uniform scale:
- is easier to explain,
- is easier to reset,
- is easier to store,
- is friendlier to future proportional font/content behavior,
- avoids immediate reflow complexity,
- avoids ugly partial support where some widgets distort under horizontal-only resize.

### 8.3 Directional Resize

Directional resize should be phase-two-or-later only.

Only enable it for vetted widgets where:
- width can reveal more content naturally,
- height can reveal more content naturally,
- layout rules stay predictable,
- reset remains simple,
- the widget does not visually break when constrained.

This likely applies later to:
- Gmail
- Reddit
- possibly Media

It is not the correct first move for:
- visualizer
- analogue/digital clock
- shell-style narrow controls

### 8.4 Font and Content Scaling

Best rule:
- keep first-phase uniform scale tied to widget-owned size controls,
- let fonts/content follow the widget’s authored size logic where available,
- avoid blind multiplying every font in the app.

In practice:
- some widgets will scale naturally because their layout is size-driven,
- some may need explicit scale-aware font helpers later,
- and some may be move-only until that contract exists.

## 9. Display, Bounds, and Clamp Rules

### 9.1 Display Resolution Rule

A committed widget belongs to one display only.

On release:
- compute visible-bounds intersection area against each display,
- choose the display with the largest overlap,
- clamp the rect fully inside that display’s bounds,
- write the normalized rect relative to that display.

### 9.2 Margin Rule

CUSTOM layout does not apply the ordinary margin/anchor padding contract.

That means:
- top-left can really mean near the literal display edge,
- the user can place widgets closer than normal presets allow,
- but the widget must still remain inside the display.

### 9.3 Visible Bounds Rule

All drag, snap, and clamp logic should operate on visible widget bounds, not arbitrary extra transparent space.

This is especially important for:
- painted shadow widgets,
- widgets with visual padding,
- direct QWidget implementations like the visualizer.

## 10. Edit Session Lifecycle

### 10.1 Entering Edit Mode

Checklist:
- freeze transitions,
- pause visualizer activity,
- suppress ordinary exit-on-input behavior,
- capture current runtime widget geometry,
- build edit shells,
- hide or freeze the live widgets as appropriate,
- display editor affordances,
- enter edit-session state.

### 10.2 During Edit Mode

Checklist:
- dragging updates shell geometry only,
- resize updates shell geometry and candidate size state only,
- snapping is visible and predictable,
- display reassignment remains previewable but not committed until release,
- live runtime widgets should not continue disruptive motion or refresh churn,
- no ordinary screensaver exit path should fire.

### 10.3 Saving

Checklist:
- validate each shell against descriptor capability rules,
- resolve destination display for each shell,
- clamp to visible display bounds,
- translate to normalized rect,
- persist CUSTOM layout payload,
- exit edit mode,
- rebuild live widgets from committed CUSTOM state,
- fade them back in.

### 10.4 Cancel

Checklist:
- discard uncommitted shell changes,
- destroy edit shells,
- restore live widgets to pre-edit geometry/state,
- resume paused systems cleanly.

## 11. Phased Delivery Plan

## Phase 0: Contract and Safety Foundations

Goal:
- no visible feature yet,
- but all enabling contracts become explicit.

Checklist:
- [ ] Add the detailed CUSTOM edit-mode reference doc.
- [ ] Add descriptor-owned edit capability metadata.
- [ ] Add normalized CUSTOM layout schema helpers.
- [ ] Add display-binding helpers and visible-bounds clamp helpers.
- [ ] Decide and document the commit/display tie-break rules.
- [ ] Decide and document resize participation strategy by family.

Success criteria:
- no feature UI yet,
- but no remaining ambiguity about ownership, persistence, bounds rules, or safety gates.

Validation:
- schema/unit tests only,
- descriptor metadata tests,
- display clamp math tests,
- normalized rect round-trip tests.

## Phase 1: Move-Only CUSTOM Layout

Goal:
- users can enter edit mode and reposition safe widgets,
- save into CUSTOM,
- and restore from CUSTOM on the next run.

Checklist:
- [ ] Build edit session manager.
- [ ] Build temporary shell widget.
- [ ] Add context-menu entry/exit flow.
- [ ] Suppress normal exit behavior while editing.
- [ ] Add drag handling and snap preview.
- [ ] Add majority-display resolution on release.
- [ ] Add CUSTOM persistence and rehydrate path.
- [ ] Keep CUSTOM greyed out until real saved data exists.

Success criteria:
- move-only works well,
- no resize yet required,
- CUSTOM restore is deterministic across runs and displays.

Validation:
- focused input/session tests,
- persistence round-trip tests,
- multi-display placement tests,
- runtime manual validation across at least two displays.

## Phase 2: Safe Uniform Resize

Goal:
- add `Ctrl + mouse wheel` resize for vetted widgets only.

Checklist:
- [ ] Add descriptor-owned uniform-scale participation flags.
- [ ] Add shell-side scale state.
- [ ] Add bottom-right reset-size control for resizable widgets.
- [ ] Add scale reset behavior and persistence.
- [ ] Rehydrate scale into real widget-owned size controls on apply.
- [ ] Confirm non-participating widgets stay move-only.

Success criteria:
- resize feels consistent,
- reset is obvious and reliable,
- widgets that should not resize simply do not expose it.

Validation:
- scale contract tests,
- reset-size tests,
- cross-DPR restore tests,
- manual validation on widgets from multiple families.

## Phase 3: Directional Resize for Vetted Widgets

Goal:
- only if phase 2 is solid,
- add horizontal/vertical resize where it genuinely improves content experience.

Checklist:
- [ ] Audit Gmail/Reddit/Media for real directional-resize viability.
- [ ] Add per-axis descriptor metadata.
- [ ] Add directional handles only for approved widgets.
- [ ] Add widget-specific content reflow/scaling rules where needed.
- [ ] Add reset behavior that restores authored width/height contracts cleanly.

Success criteria:
- no widget gets directional resize “because maybe.”
- only widgets with strong reflow behavior receive it.

Validation:
- widget-family-specific resize tests,
- content visibility assertions,
- manual UX validation for readability and recovery.

## Phase 4: Visualizer Participation Decision

Goal:
- decide whether the visualizer should stay move-only, become move-plus-scale, or remain deferred longer.

Checklist:
- [ ] Reuse `card_geometry.py` as the only outer-card geometry owner.
- [ ] Keep stencil-shell behavior untouched by CUSTOM geometry edits.
- [ ] Validate preset-owned growth still behaves sensibly under CUSTOM placement/scale.
- [ ] Decide whether visualizer scale should map to base height, growth factor, or a separate CUSTOM scale layer.

Recommended likely outcome:
- phase-one visualizer participation should be move-only or move-plus-uniform-scale,
- not directional resize.

## 12. Candidate Widget Phasing

### 12.1 Safest First-Phase Move Candidates

Most likely safe:
- Clock
- Weather
- Media
- Gmail
- Reddit
- Imgur
- Spotify volume
- Mute button

These still need audit, but they are plausible move-only candidates.

### 12.2 Safest First-Phase Resize Candidates

Best early bets:
- Clock: uniform scale only
- Weather: likely uniform scale only first
- Imgur: likely uniform scale only first
- Media: maybe uniform scale first, directional only later if audited

### 12.3 Likely Phase-Later Directional Candidates

Potentially worth it later:
- Gmail
- Reddit
- Media

Only if content-flow behavior is actually strong enough.

### 12.4 Likely Deferred or Restricted

Most likely restricted initially:
- Spotify visualizer: move-only or move-plus-uniform-scale only
- widgets with fragile anchor-dependent or specialized geometry behavior

## 13. Testing Plan

### 13.1 Unit/Contract Tests

- normalized rect conversion
- display-local persistence round-trip
- display majority selection
- tie-break rule on release
- visible-bounds clamping
- descriptor capability participation
- reset-size persistence contract

### 13.2 Integration Tests

- enter edit mode / cancel / save
- CUSTOM slot enable/disable behavior
- program restart restore from CUSTOM
- multi-display rehydrate with changed resolution/DPR
- non-resizable widget ignoring resize input
- resizable widget reset button restoring authored size

### 13.3 Visualizer-Specific Tests

- outer geometry still owned by `card_geometry.py`
- preset-owned growth still respected
- blob width reduction still centered correctly
- `tests/test_stencil_mask_alignment.py` stays green
- first-frame/preset-drift guard family remains green

### 13.4 Manual Validation

Required before rollout:
- two-display drag across boundary
- tight-to-edge placement with no margin enforcement
- save/apply/cancel feel
- resize feel for first-phase widgets
- reset-size discoverability
- no accidental screensaver exit during edit mode

## 14. Guardrails and Anti-Patterns

Do not:
- store raw pixels as the only truth,
- invent a second widget-position registry outside descriptors,
- let edit mode manipulate every live widget directly by default,
- enable resize on widgets before their authored size contract is understood,
- couple visualizer stencil logic to CUSTOM layout persistence,
- hide failed geometry decisions behind extra margins or silent clamps,
- turn `Current_Plan.md` into the detailed design doc for this feature.

## 15. Recommended Immediate Next Steps

If this feature becomes active, the best next implementation order is:

1. Add descriptor-owned edit-mode capability metadata.
2. Add the normalized CUSTOM layout schema/helpers.
3. Add the edit-session manager and shell widget.
4. Land move-only CUSTOM layout first.
5. Add uniform resize second.
6. Only then audit directional resize widget by widget.

That is the safest route to a polished experience without turning the feature into a brittle geometry experiment.

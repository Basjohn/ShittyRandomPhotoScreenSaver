# 05 — CUSTOM Layout, Input, Interaction and Auxiliary Runtime Pixels

Status: **Phase-G technical decomposition; Clock multi-geometry contract predeclared by Phase F**  
Last updated: 2026-08-24

Phase E is independently GREEN/CLOSED through `3a562632`; this remains the waiting Phase-G authority.

Cross-links:

- `Current_Plan.md`
- `rendering/custom_layout_contract.py`
- `Docs/10_WIDGET_GUIDELINES.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- `Docs/Guardrails/Visualizer_Presentation.md`

`Current_Plan.md` owns work admission. This file defines the Phase-G destination so Phase F does not
build presentation interfaces that G cannot preserve.

---

## 1. Preserve useful CUSTOM data contracts

Do not rewrite existing presentation-neutral CUSTOM math without evidence.

Preserve or deliberately rehome:

- screen signatures/aliases;
- normalize/denormalize;
- clamp;
- snap;
- gutters/grid;
- display ownership;
- restore maps;
- Save/Cancel;
- slot persistence;
- family-specific size payload semantics.

Change presentation/session ownership away from QWidget edit shells.

---

## 2. Destination `CustomLayoutSession`

Presentation-neutral session state per edited item:

```text
widget_id
model/presentation identity
source display
current display
geometry variant
baseline global rect
current global rect
baseline size payload
current size payload
resize scale
removed flag
```

The session does not require QWidget.

For a widget with multiple presentation geometry variants, the active session names the variant it is
editing. An inactive variant is not collateral mutable state.

---

## 3. Geometry-variant contract — REQUIRED

The migration must not assume every widget has exactly one durable CUSTOM rect.

A family may define stable geometry variants when modes have materially different shapes.

Canonical operations conceptually become:

```text
read committed geometry(widget_id, display_identity, variant)
write committed geometry(widget_id, display_identity, variant, rect, size_payload)
```

A missing/empty variant may fall back through documented default initialization. A present variant must
be restored exactly subject only to current-screen validity/clamping rules.

Do not repeatedly derive one saved variant from another during ordinary mode switches.

---

## 4. Clock digital/analogue geometry

Clock is the first required multi-geometry family:

```text
Clock instance + display
    ├── digital -> committed rect A
    └── analog  -> committed rect B
```

### First use of a target variant

If the target mode has never had a committed rect:

1. take the current visual center as the intent;
2. obtain the target mode's natural initial size from the presentation/geometry owner;
3. center that size on the current center;
4. clamp to the target display;
5. establish the result as the target variant's baseline.

This is an initialization event, not the permanent switch algorithm.

### Later mode switches

Once both exist:

```text
digital A
-> analog B
-> digital A
-> analog B
```

No accumulating center/size drift is allowed.

### Editing

- moving/resizing digital updates digital only;
- moving/resizing analogue updates analogue only;
- changing font/style may reflow content inside the committed rect but must not silently rewrite the
  inactive variant's committed rect;
- an explicit reset-size/reset-layout action may deliberately recompute the active variant according to
  its own contract.

### Persistence

Recreate/restart must restore both variants.

Display identity scopes the variant set. Cross-display transfer and topology changes must resolve the
target display's variant state deliberately rather than aliasing unrelated monitor geometry.

### Testing

At minimum:

- 50+ digital↔analogue round trips preserve exact A/B rects;
- manual digital resize does not change B;
- manual analogue resize does not change A;
- save/recreate restores A/B;
- Cancel restores the active variant baseline and leaves inactive variant untouched;
- two displays retain independent A/B pairs;
- clamping due to a changed display bounds is deterministic and does not create cumulative drift on
  subsequent switches.

The current legacy Clock `_rebuild_custom_rect_for_mode()` center-derived behavior is migration source
only, not destination authority.

---

## 5. Edit the real Quick presentation

Preferred behavior:

- live retained Quick widget stays visible;
- edit overlay/handles live above it in the same Quick window;
- session geometry temporarily overrides normal placement;
- model/provider may keep publishing current state;
- persistence is unchanged until Save.

Benefits:

- WYSIWYG;
- no screenshot shell;
- no duplicate visual owner;
- exact shadows/fade/content;
- Cancel does not rebuild untouched runtime/provider state.

The Visualizer follows the same one-live-pixel-owner rule despite using a `QSGRenderNode`.

---

## 6. Save

Save:

1. identify the active widget + geometry variant;
2. resolve final display from current global rect;
3. compute canonical local rect/size payload;
4. write only the active variant's committed state;
5. update canonical monitor/position settings through the existing route where product semantics require
   it;
6. remove session override;
7. let normal runtime geometry resolve to the just-committed variant.

For visualizer viewport work, scale and viewport extent remain separate values.

Do not recreate a whole runtime merely to adopt geometry already displayed unless current product
semantics require recreation.

---

## 7. Cancel

Cancel:

- discard session-only active-variant changes;
- restore that variant's baseline;
- do not mutate inactive variants;
- restore visualizer scale + viewport together where applicable;
- do not replay destructive config setters for state never committed;
- do not recreate provider/model state.

---

## 8. Resize

Quick edit handles emit deltas; Python session/geometry math owns persistence semantics.

Resolve:

- min size;
- aspect constraints;
- anchor semantics;
- family-specific size payload;
- active geometry variant;
- display/DPR projection.

Do not invent QML-only persisted geometry.

### Visualizer remains special

Keep the established distinction:

```text
uniform_visual_scale
content_viewport_size
```

Corner/wheel may change uniform scale; edge-only resize may change viewport extent where the mode
supports it. Never anisotropically stretch finished pixels.

---

## 9. Cross-monitor transfer

One live pixel owner at a time.

1. session chooses target display using existing global-rect contract;
2. source presentation is detached/retired;
3. target display scene creates/reparents presentation;
4. Python runtime/model owner survives unless product semantics say otherwise;
5. target-local active-variant rect is applied;
6. session updates current display identity.

Do not leave simultaneous source/target copies.

For multi-variant families, transfer must define whether an existing target-display variant is restored
or whether the incoming active rect initializes/replaces that target variant. The choice must be
deterministic and tested; never silently overwrite every variant on the target display.

---

## 10. Edit overlays

Port to retained Quick:

- grid;
- snap guides;
- selection outline;
- corner handles;
- edge handles where supported;
- widget label/control chrome.

Use one shared edit-overlay layer per display.

---

## 11. Input/action ownership

Refactor old DisplayWidget/QWidget-probing input seams toward a runtime-neutral input controller.

Quick may own hit regions/pointer handlers. It emits semantic actions.

Python owns:

- mode changes;
- provider actions;
- persistence;
- CUSTOM session commands;
- context/global shortcuts.

Enter=Save and Esc=Cancel remain.

Clock double-click/toggle becomes a semantic mode action; QML does not write geometry or Settings.

---

## 12. Context menu

A QWidget context menu may remain temporarily as a control surface if it does not become a second
runtime presenter or lifecycle blocker.

Decouple it from `DisplayWidget` API. Pass runtime/display identity and action/state owners explicitly.

If QWidget popup focus is proven to be a blocker, migrate the menu once. Do not maintain permanent dual
menu implementations.

---

## 13. Halo, dimming, pixel shift

These are runtime pixels and belong in the Quick scene.

- halo follows the correct display pointer and uses retained animation;
- dimming is a retained scene layer at the correct z;
- pixel shift is a transform/offset of intended presentation items, not a moved window or rebuilt
  texture.

No extra translucent top-level windows.

---

## 14. Media Center / focus gates

Stress:

- two displays;
- focus A -> B -> A;
- Ctrl interaction;
- context menu;
- Clock live mode switching;
- media controls/volume;
- halo;
- shadows;
- repeated activation/deactivation;
- Settings/CUSTOM transition;
- cross-monitor transfers.

Do not reintroduce the old focus-driven shadow corruption class.

---

## 15. Checkpoints

Suggested Phase-G audit boundaries:

```text
G1 CustomLayoutSession + multi-variant data contract
G2 Quick edit overlays + ordinary geometry
G3 Save/Cancel + exact variant persistence
G4 resize semantics
G5 cross-monitor transfer
G6 runtime-neutral input/action routing
G7 context/halo/dimming/pixel-shift
G8 MC/focus closure
```

Visualizer viewport-resize QoL remains separately scoped if it proves expensive; ordinary safe scale
resize must still work.

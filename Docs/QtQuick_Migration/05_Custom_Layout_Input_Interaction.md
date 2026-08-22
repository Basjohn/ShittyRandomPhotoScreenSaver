# 05 — CUSTOM Layout, Input, Interaction and Auxiliary Runtime Pixels

Status: technical decomposition only  
Last updated: 2026-08-22

Cross-links:

- `Current_Plan.md`
- `rendering/custom_layout_contract.py`
- `Docs/10_WIDGET_GUIDELINES.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Future_Cleanup.md`

## 1. Preserve CUSTOM data contracts

Do **not** rewrite the existing custom-layout persistence/math unless a focused bug proves it
necessary.

Keep:

- screen signatures/aliases;
- normalize/denormalize;
- clamp;
- snap;
- gutters/grid;
- monitor ownership;
- restore maps;
- Save/Cancel semantics;
- slot persistence.

Change presentation/session ownership.

The H0 Quick settings epoch means old QWidget geometry does not need heroic translation into the new
visualizer scale/viewport schema.

## 2. Current CUSTOM problem seam

`CustomLayoutManager` currently owns:

- QWidget live widgets;
- `EditShellWidget`;
- `EditGridOverlayWidget`;
- QPixmap previews;
- global key filter;
- widget hide/restore;
- special visualizer suspension;
- multi-display shell transfer.

Quick gives a cleaner final shape.

## 3. Destination session

Refactor to a presentation-neutral `CustomLayoutSession`.

Plain session state per widget:

```text
widget_id
model identity
source display
current display
baseline global rect
current global rect
baseline size payload
current size payload
resize scale
removed flag
```

For the visualizer, the final size payload may additionally carry the new-schema distinction between:

```text
uniform_visual_scale
content_viewport_size
```

The session does not require QWidget.

## 4. Edit the real Quick presentation

Preferred behavior:

- the live retained Quick widget remains visible content;
- edit mode adds outline/handles above it;
- session geometry overrides normal placement temporarily;
- provider/model content may continue updating;
- persistence is untouched until Save.

Benefits:

- WYSIWYG;
- no stale screenshot shell;
- no duplicate visual;
- no Cancel rebuild of untouched content;
- shadows/opacity/content remain exact.

The visualizer follows the same one-live-pixel-owner rule even though its content is a custom
QSGRenderNode.

## 5. Save

Save:

1. resolve current screen ownership from final rect;
2. compute canonical local/custom payload using existing contract;
3. write canonical custom layout;
4. update monitor/position keys only through existing canonical route;
5. remove temporary session override;
6. let normal runtime geometry resolve to the just-committed layout.

For visualizer viewport-resize support, commit scale and viewport extent together so a recreated
runtime cannot confuse "make content bigger" with "show more content."

No full runtime recreate merely to make the item adopt what it already displays unless current product
semantics require it.

## 6. Cancel

Cancel:

- discard session-only geometry/size;
- restore baseline presentation geometry;
- restore baseline visualizer scale + viewport extent together;
- do not replay destructive config setters for state that never changed;
- resume any explicitly suspended visualizer behavior;
- no provider/model recreation.

## 7. Resize

Retain current family-specific resize payload rules.

The Quick edit shell/handles emit deltas.

Python session math resolves:

- min size;
- aspect constraints;
- top-center or other anchor semantics;
- family-specific font/artwork/visualizer size payload.

Do not invent QML-only persisted geometry.

### 7.1 Visualizer: whole-size scale and viewport resize are different operations

Phase D establishes:

```text
canonical_baseline_viewport
uniform_visual_scale
viewport_extent
```

The baseline aspect is shared by all current modes. The retired per-mode `*_growth` settings do not
participate.

Preferred interactions:

```text
mouse wheel over resize/edit target
    -> uniform whole-visualizer scale
    -> baseline aspect preserved

corner handles
    -> uniform whole-visualizer scale
    -> baseline aspect preserved

left/right edge handles
    -> viewport width only
    -> visual scale unchanged

top/bottom edge handles
    -> viewport height only
    -> visual scale unchanged
```

This keeps the successful current CUSTOM behavior for ordinary resizing while giving edge-only drag a
new, explicit meaning: more/less playroom rather than stretching the visualizer.

At constant visual scale:

- Spectrum recomputes bar distribution/layout across the viewport;
- Bubble changes spatial bounds/aspect while preserving isotropic circles, radii, velocity units and
  BTF behavior;
- Oscilloscope/Sine/DevCurve recompute usable domain/placement while preserving line/stroke scale;
- future frameless 3D modes use aspect-correct projection.

The card shell, when present, follows the viewport geometry. A frameless mode retains the same edit
rect/handles with no card chrome.

`Reset Size` restores uniform scale and viewport extent to canonical baseline geometry unless a later
UX decision deliberately splits those reset actions.

Persist scale and viewport extent separately. Never map them back onto legacy `spectrum_growth`,
`osc_growth`, `sine_wave_growth`, `bubble_growth`, or `devcurve_growth`.

### 7.2 Spatial logical modes

If Bubble or another logical mode needs viewport bounds, route committed geometry changes through the
presentation-neutral viewport-metrics seam established in Phase D.

Do not let mouse-move frequency, edit repaint frequency, or physical refresh become the logical
simulation clock.

During drag, coalesce geometry application as needed for responsiveness, but final committed geometry
must be exact and deterministic.

### 7.3 Non-blocking migration rule

Freeform visualizer viewport resizing is a preferred QoL, not a cutover blocker.

If focused evidence shows one current mode would require major retuning or violate BTF/fidelity:

- keep ordinary uniform-scale resize;
- hide/disable viewport-edge resize handles for that mode;
- preserve the underlying scale/viewport-capable geometry contract;
- record the mode-specific deferred work;
- do not fake compatibility by stretching rendered pixels.

This exception is mode-specific. It is not permission to collapse scale and viewport geometry
globally.

## 8. Cross-monitor transfer

One live pixel owner at a time.

When an edited widget transfers screens:

1. session chooses target using existing global-rect contract;
2. detach/destroy source scene presentation item;
3. create/reparent the presentation into target display scene;
4. keep the same Python runtime model/provider owner;
5. apply target-local rect;
6. update session current display identity.

Never leave simultaneous source and target visual copies after transfer.

Do not transfer GL numeric resources between windows; visualizer render resources recreate/retarget
through normal scene ownership if needed.

Preserve visualizer scale/viewport semantics across the transfer and recompute DPR from the target
QQuickWindow/QScreen.

## 9. Edit overlays

Port to retained Quick:

- grid;
- snap guides;
- selection outline;
- corner resize handles;
- edge resize handles where the widget/mode supports them;
- widget label/control chrome if currently present.

These are runtime edit pixels and belong inside Quick windows.

Use one shared edit overlay layer per display.

## 10. Global keys

Keep Enter=Save, Esc=Cancel semantics.

A global QObject/event-filter owner may remain Python.

It targets the active `CustomLayoutSession`, not a QWidget manager list.

## 11. Input controller refactor

Current `InputHandler` is conceptually separated but takes `DisplayWidget` and probes QWidget
instances.

Refactor it into a runtime-neutral `RuntimeInputController`.

Inputs:

- SettingsManager;
- screen/runtime identity;
- command callbacks/signals;
- widget action router;
- MultiMonitorCoordinator state.

It should not need to import `DisplayWidget`.

`QuickDisplayWindow` forwards:

- key press/release;
- mouse press/release/move;
- wheel;
- focus/activation;
- relevant native Windows messages.

## 12. Widget hit testing / actions

Retained Quick items own visual hit regions.

Use Quick pointer/tap handlers or QQuickItem containment to emit semantic actions:

```text
open link
refresh
media previous/play/next
volume
mute
widget-specific action
```

Python provider/business owners execute the action.

Do not put provider logic in QML event handlers.

## 13. Context menu

The existing QWidget context menu may remain a transient control surface.

It is not an accelerated runtime presenter.

Refactor it so it does not require a `DisplayWidget` parent API.

Pass:

- runtime/display identity;
- action owner;
- current settings/model state;
- global popup position.

Gate focus/activation carefully, especially MC and the old shadow-corruption trigger.

If retaining QWidget popup becomes an actual focus/lifecycle blocker, migrate the menu once as a Quick
control. Do not maintain both.

## 14. Cursor halo

Port visual halo pixels to Quick.

Keep global Ctrl/focus ownership in `MultiMonitorCoordinator` or an explicit replacement.

The halo item:

- follows pointer in the correct display;
- uses retained animation;
- respects interaction mode;
- disappears deterministically on release/focus loss.

No separate translucent top-level halo window.

## 15. Dimming

Use a Quick scene rectangle/layer at the correct z.

Properties:

- enabled;
- opacity;
- synchronized across displays through current product action;
- no per-frame rebuild.

Ensure dimming does not unintentionally dim control UI if current semantics exclude it.

## 16. Pixel shift

Apply pixel shift as a presentation transform/offset to the intended widget group/items.

Do not move the QQuickWindow.

Do not rebuild textures/content for a small positional offset.

Preserve bleed/visualizer historical regression coverage.

## 17. Media Center / focus gate

Required stress:

- two displays;
- focus click A -> B -> A;
- Ctrl interaction;
- context menu;
- media controls;
- volume;
- taskbar/Alt+Tab behavior;
- halo;
- shadows;
- repeated activation/deactivation;
- Settings/CUSTOM transition.

No return of the old focus-driven shadow corruption class.

## 18. Visualizer resize gates

If viewport-resize QoL is implemented, prove:

- scroll-wheel resize changes uniform scale and preserves canonical baseline aspect;
- corner resize changes uniform scale and preserves canonical baseline aspect;
- horizontal edge resize changes width without changing visual scale;
- vertical edge resize changes height without changing visual scale;
- no anisotropic final-pixel stretch;
- current five carded modes preserve inner clipping/frame alignment;
- frameless-policy test object remains frameless while resizing;
- Bubble circles remain circular and BTF timing/trajectory invariants hold;
- Save/recreate preserves scale and viewport extent;
- Cancel restores both exactly;
- cross-monitor transfer preserves intent across DPR changes.

A mode marked viewport-resize-incapable must still retain correct ordinary scale resize.

## 19. Checkpoints

Push separately after:

- session data refactor;
- Quick edit overlays;
- Save/Cancel;
- ordinary resize;
- visualizer viewport-resize QoL if implemented;
- cross-monitor transfer;
- input controller;
- context menu decoupling;
- halo/dimming/pixel shift;
- MC/focus closure.

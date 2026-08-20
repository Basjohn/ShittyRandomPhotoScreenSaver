# 05 — CUSTOM Layout, Input, Interaction and Auxiliary Runtime Pixels

Status: technical decomposition only
Last updated: 2026-08-20

Cross-links:

- `Current_Plan.md`
- `rendering/custom_layout_contract.py`
- `Docs/10_WIDGET_GUIDELINES.md`
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

Quick gives us a cleaner final shape.

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

The session does not require QWidget.

## 4. Edit the real Quick presentation

Preferred behaviour:

- the live retained Quick widget remains the visible content;
- edit mode adds an outline/handles above it;
- session geometry overrides normal placement temporarily;
- provider/model content may continue updating;
- persistence is untouched until Save.

Benefits:

- WYSIWYG;
- no stale screenshot shell;
- no duplicate visual;
- no Cancel rebuild of untouched content;
- shadows/opacity/content remain exact.

## 5. Save

Save:

1. resolve current screen ownership from final rect;
2. compute canonical local/custom payload using existing contract;
3. write canonical custom layout;
4. update monitor/position keys only through existing canonical route;
5. remove temporary session override;
6. let normal runtime geometry resolve to the just-committed layout.

No full runtime recreate merely to make the item adopt what it already displays unless current product
semantics require it.

## 6. Cancel

Cancel:

- discard session-only geometry/size;
- restore baseline presentation geometry;
- do not replay destructive config setters for state that never changed;
- resume any explicitly suspended visualizer behaviour;
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
through its normal scene owner if needed.

## 9. Edit overlays

Port to retained Quick:

- grid;
- snap guides;
- selection outline;
- resize handles;
- widget label/control chrome if currently present.

These are runtime edit pixels and belong inside the Quick windows.

Use one shared edit overlay layer per display.

## 10. Global keys

Keep Enter=Save, Esc=Cancel semantics.

A global QObject/event-filter owner may remain Python.

It should target the active `CustomLayoutSession`, not a QWidget manager list.

## 11. Input controller refactor

Current `InputHandler` is already conceptually separated but takes `DisplayWidget` and probes QWidget
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

If retaining QWidget popup becomes an actual focus/lifecycle blocker, then migrate the menu once as a
Quick control. Do not maintain both.

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
- taskbar/Alt+Tab behaviour;
- halo;
- shadows;
- repeated activation/deactivation;
- Settings/CUSTOM transition.

No return of the old focus-driven shadow corruption class.

## 18. Checkpoints

Push separately after:

- session data refactor;
- Quick edit overlays;
- Save/Cancel;
- resize;
- cross-monitor transfer;
- input controller;
- context menu decoupling;
- halo/dimming/pixel shift;
- MC/focus closure.

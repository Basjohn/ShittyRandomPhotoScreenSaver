# Transition Change Checklist

Last updated: 2026-08-20

Use when adding/removing/renaming/retuning a transition or while executing the Qt Quick transition
migration.

Active migration sequencing is in `Current_Plan.md`.

Technical migration detail:

`Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`

## 1. Registry / identity

- canonical id/name stays in `rendering/transition_registry.py`;
- legacy settings aliases remain registry/settings concerns;
- random/cycle eligibility remains registry-owned;
- defaults reference valid canonical ids.

## 2. Presentation owner

Destination production owner:

```text
Quick transition run
-> display QSGRenderNode
-> display QQuickWindow
```

During migration old `gl_compositor_*` classes may still be current production reference code.

Do not add new dependencies from Quick code back to `GLCompositorWidget`.

Do not add a fallback that sends an unsupported Quick transition to the old compositor.

## 3. Timing

Preserve:

- duration;
- easing;
- direction;
- authored random parameters;
- exactly-once completion;
- interruption semantics.

Physical frame pacing is display presentation only.

No catch-up, paint acknowledgement, or transition-specific cadence hacks.

## 4. Renderer

Reuse existing shader/math when valid.

Render-thread state is immutable/synchronized.

No live QWidget/QPixmap access on render thread.

Resource create/use/delete follows the Quick render-node owner.

## 5. UI/settings

Settings UI remains unchanged unless transition controls/identity genuinely change.

Do not rewrite settings tab because the runtime renderer changed.

## 6. Tests

Cover:

- registry;
- factory/request mapping;
- transition run parameters;
- start/mid/end rendering;
- direction/easing;
- interruption;
- generation fencing;
- resource cleanup;
- high-refresh installed motion.

## 7. Migration closure

After all active transitions use Quick and production cutover is green, remove old compositor-only
transition classes through `Future_Cleanup.md`.

Commit and push each landed transition batch.

# H5c Performance Cursor-Halo Checkpoint — R6 (Outside Codex)

Date: 2026-08-31
Status: **SUPERSEDED CHECKPOINT / provenance only. The later native-`QCursor` Halo path was physically accepted; use current contracts/`Current_Plan.md` for any new cursor regression.**

This checkpoint supersedes only the R5 Cursor-Halo implementation. R5 Bubble complete-wake scaling and replacement-runtime prefetch reseeding remain accepted and must not be reverted.

## Physical/log evidence that forced R6

The R5 physical run reproduced the same severe presentation collapse during Cursor Halo movement. The retained context menu intentionally suppresses Halo; moving the ordinary cursor in that state did not reproduce the collapse. MC mode on the single 60 Hz display also did not reproduce the same failure, while the normal two-display/high-refresh path did.

Source audit found two surviving R5 hot paths:

1. every passive `QQuickWindow.mouseMoveEvent()` still entered `QuickInputController -> RuntimeInputOwner` and queried live interaction/Ctrl providers; normal interaction-mode resolution could reach Settings under locks/cache lookup;
2. the visible Halo remained a retained QML item (`HoverHandler.point.position -> CursorHalo.x/y`) and restarted its inactivity timer on coordinate changes, so physical cursor movement still dirtied the same composited scene as the Visualizer.

R5 therefore removed only the old auxiliary-state coordinate publication path. It did not remove cursor movement from the composited scene or remove all passive provider work.

## R6 ownership

```text
Settings / MC construction fact
    -> QuickInputController.interaction_mode_enabled (event-cached)

Ctrl key change on one display
    -> SharedCtrlCoordinator
    -> push global held truth to every live generation-scoped QuickInputController

QuickInputState
    -> QuickAuxiliaryController
        -> low-rate halo admission / suppression / shape

QuickAuxiliaryController.state_changed
    -> QuickCursorController
        -> cached native QCursor pixmap
        -> QQuickWindow.setCursor(...)

physical pointer movement while Halo admitted
    -> QuickDisplayWindow.mouseMoveEvent
        -> QuickCursorController.note_pointer_motion()
            -> update last_motion_ns only
            -> no Settings/provider read
            -> no auxiliary-state publication
            -> no QML position binding
            -> no scene-root property write
```

The classic non-interaction screensaver exit gesture remains separately routed through `RuntimeInputOwner` only when it can actually fire. Interaction mode, Ctrl mode and retained-context-menu motion bypass that route.

## Native cursor presentation

`QuickCursorController` renders the existing seven configured shapes (`circle`, `ring`, `crosshair`, `diamond`, `dot`, `cursor_light`, `cursor_dark`) into transparent `QPixmap`/`QCursor` assets. The window system owns physical pointer movement.

One-cursor semantics are explicit:

- Halo admitted + active motion -> window cursor is the Halo;
- retained context menu / semantic native-cursor admission -> one ordinary arrow cursor;
- normal non-interaction screensaver mode -> blank cursor;
- there is no retained fake pointer underneath or above the native cursor.

The old `CursorHalo.qml` file and `DisplayScene.qml` `HoverHandler`/Halo item are removed from the destination scene.

## Inactivity contract

The historical two-second inactivity behavior is preserved without a mouse-poll-rate timer restart:

- pointer motion updates `last_motion_ns`;
- the inactivity timer is armed only when not already active;
- on timeout it compares the deadline and re-arms only for the remaining quiet interval if motion continued;
- after true inactivity, a bounded six-step native-cursor alpha fade runs for 1200 ms;
- fade cursor pixmaps are cached;
- no recurring position poll, second cadence owner or Quick-scene animation is introduced.

An event-driven Halo admission may query `QCursor.pos()` once to preserve immediate appearance when the pointer is already stationary over that display. This is not recurring polling.

## Cached semantic input

`QuickInputController` no longer retains live interaction-mode or global-Ctrl providers. Interaction mode is initialized once when the generation is constructed and is pushed when the retained context-menu action changes Settings.

`SharedCtrlCoordinator` now broadcasts global Ctrl truth to subscribed live input controllers instead of requiring mouse events to poll it. Contribution/listener keys are `(runtime_generation, screen_index)` so overlapping replacement generations cannot delete a newer generation's Ctrl contribution by retiring an older same-screen unit.

## Focused source validation

The outside-Codex source-only profile is GREEN:

- `tests/test_visualizer_viewport_scaling_contracts.py`: **16/16**
- `tests/test_runtime_perf_policy_contracts.py`: **7/7**
- combined: **23/23**

The R6 contracts specifically prove:

- `DisplayScene.qml` contains no `CursorHalo` or pointer `HoverHandler`;
- `QuickSceneController` no longer writes Halo/native-cursor/shape properties into the scene root;
- the destination cursor owner uses native `QCursor` and has no `QQuickItem`/scene-update API;
- pointer motion uses a deadline timestamp and does not restart the timer per event;
- admitted Halo movement bypasses `RuntimeInputOwner`;
- `QuickInputController` retains no live interaction/global-Ctrl provider;
- cross-display Ctrl truth is event-broadcast and unchanged truth is not republished.

Changed Python files also pass `py_compile` in this source-only environment. PySide6 is not installed here, so this does **not** replace the maintained project test profile or physical runtime validation.

## Mandatory physical gate

On the same high-refresh display used to reproduce the failure:

1. run with `--perf` and sustained Cursor Halo movement over the Visualizer;
2. compare against sustained ordinary-cursor movement while the retained context menu is open;
3. presentation FPS/pacer skip behavior should no longer collapse simply because the Halo cursor moves;
4. verify exactly one cursor in interaction mode and Ctrl mode;
5. verify context-menu open immediately changes to the ordinary arrow and dismissal restores Halo semantics;
6. verify two-second inactivity plus fade and immediate restoration on motion;
7. verify Ctrl press/release across displays, including focus moving between displays;
8. verify normal non-interaction movement still performs the intended >10 px screensaver exit gesture.

If the movement collapse remains after this architecture, do not resurrect retained QML cursor motion or live Settings polling. Use the new logs to isolate the next presentation/input boundary.

## Still open after R6

- GC deep pauses/allocation pressure: re-measure only after the R6 physical gate so the evidence no longer includes the two known Halo hot paths.
- residual warm-cache natural-vs-manual transition FPS difference.
- H9 ordinary-widget uniform resize contract (currently delegated as a bounded concurrent slice).
- Bubble Ghost/Decay historical contract.
- Media polling -> event-driven migration and all other existing H/J rows in `Current_Plan.md`.

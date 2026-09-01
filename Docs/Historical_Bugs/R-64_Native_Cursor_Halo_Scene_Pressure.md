# R-64 — Retained Cursor Halo Turned Passive Pointer Motion Into Scene Pressure

Date: 2026-09-01
Status: Solved (performance architecture); visual cursor/Halo parity carried separately

## Symptom

With the retained Qt Quick Cursor Halo active, ordinary continuous mouse motion could collapse Visualizer presentation performance. Opening the retained context menu suppressed that Halo path and ordinary cursor motion immediately became harmless. The failure could therefore look like general Visualizer/GPU overload even though the authored Visualizer cadence itself was healthy.

## Root Cause

The first hot-path cleanup was incomplete. Passive motion still crossed two expensive boundaries on every mouse event:

1. `QuickDisplayWindow.mouseMoveEvent()` routed through `QuickInputController -> RuntimeInputOwner`, which could query live interaction/Ctrl/Settings state.
2. `HoverHandler.point.position` moved a visible retained QML `CursorHalo` and restarted its inactivity timer on pointer-coordinate changes, dirtying the same QQuickWindow scene that presented the Visualizer.

Removing only auxiliary pointer property publication did not remove either surviving owner. Physical A/B evidence was decisive: motion with the retained Halo active was bad; the same motion with the Halo suppressed by the context menu was clean.

## Fix

Cursor-following presentation moved out of the retained scene:

- `QuickCursorController` renders/caches the configured shape into the window's native `QCursor`.
- Qt/the window system owns cursor-coordinate motion; pointer coordinates no longer move a retained QML item or publish mouse-rate scene state.
- interaction-mode and Ctrl truth are event-updated facts rather than mouse-move provider reads.
- admitted Halo motion only updates a timestamp; the neutral mouse-move route remains solely for the classic non-interaction exit gesture.
- inactivity uses one armed deadline plus a bounded native-cursor fade, never a mouse-rate timer restart.

## Physical Acceptance

After the R6 cut, sustained pointer motion no longer produced the catastrophic Visualizer FPS collapse. The high-refresh display could remain near its normal presentation behavior under the same interaction.

The visual appearance of the native cursor/Halo remains a separate parity target. **Do not fix visual parity by restoring a moving QML cursor or mouse-rate retained-scene publication.**

## Binding Lesson

A tiny retained item can become a whole-scene performance owner if it changes at pointer rate. For cursor-following effects, preserve the native-cursor boundary unless future evidence proves an equally cheap presentation mechanism. When diagnosing Visualizer stalls, distinguish authored logical cadence from unrelated scene invalidation before tuning Visualizer rates.

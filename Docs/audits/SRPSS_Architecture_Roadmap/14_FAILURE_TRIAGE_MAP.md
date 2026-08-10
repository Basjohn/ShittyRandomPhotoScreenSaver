# 14 — Failure Triage Map

Last reconciled: 2026-08-10

Use this map to find owners, not symptom patches.

## Frame gap / visualizer microgap

First compare request age, event-loop lateness and paint duration. If request age dwarfs
paint, inspect synchronous GUI commits, logging/persistence, cold cache construction,
image warm/upload and callback bursts before touching visualizer cadence.

## `generic_pair_warm` / transition-start stall

Check retained-current key versus next-old lookup, `old_cached_before`, upload/allocation
counts and context/generation/size identity. Do not raise cache budgets or retain
historical textures to hide an identity mismatch.

## High GPU busy

Collect process GPU busy + sample age, transition family, non-blocking GL timer samples,
texture uploads, visualizer overlay update/paint rates and display refresh. Split upload,
transition shader/draw, visualizer overlay/context and presentation/overdraw. Do not cap
visualizer logic or call `glFinish()` as the first reaction.

## Visualizer paint/update rate exceeds display refresh

Determine separately:

- logical source/state publication rate;
- overlay state commit rate;
- update request rate;
- paint rate;
- actual display refresh/vsync/context route;
- source/state age at paint.

This may be presentation waste, but only Phase 7 may coalesce immutable render snapshots
after stronger temporal goldens. Logical/source cadence is not reduced merely because
the panel is 60 Hz.

## Main log is flooded by sidecar-family INFO

Check family classification/routing before lowering log level or deleting evidence. All
WARNING+ remain in main. Routine family INFO/DEBUG should route to sidecar when enabled.
Known example: `[GL CACHE]` currently misses cache-family suppression because routing
expects `[CACHE]`.

## Settings mutation causes UI hitch

Inspect synchronous JSON serialization/temp write/replace. In-memory setting should be
immediately authoritative; durable writes belong to ordered persistence with explicit
flush points. Do not use unordered pool writes where an old revision can win.

## Reddit/Weather/Gmail cold or callback hitch

Look for filesystem/JSON/filter/sort/cache construction inside GUI result callbacks or
`paintEvent()`. Move preparation/I/O away from GUI; keep Qt metrics/layout/QPixmap commit
on GUI.

## Bubble looks delayed/flat

Check shared GUI/event-loop/source-age pressure first. Do not change physics, cadence,
source sampling or executor ownership unless direct mode-owned evidence proves the
problem. `666624d4` is the negative control.

## Spectrum less smooth

Look for a second clock, paint-local state, self-requested paints or source/presentation
cadence divergence. `ebfec397` is the negative control.

## Temporary compatibility/fallback surface encountered

Ask what current contract it preserves. If only tests/docs/rejected architecture depend
on it, prove no production/dynamic/frozen consumer and delete it in a separate
checkpoint. Do not preserve an alternate scheduler/state machine “just in case.”

## Historical Settings/Edit deleted-wrapper/retired-owner failures

These are solved reference incidents. If the same shape reappears, consult R-53/R-56/
R-59 and verify later-turn admission, wrapper liveness and stable weak callback ownership.
Do not proactively reopen them during unrelated performance work.

## Memory flat but excessive

Separate RSS, private commit, mappings/stacks, child process, tracked CPU/GL bytes,
VRAM and driver state. Flat is not automatically acceptable; do not trim/recycle/GC to
make a graph look better.

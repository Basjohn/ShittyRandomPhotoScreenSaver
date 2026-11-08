# R-176 | Every worker process loaded the whole application before its own target (~1.3 s and ~80 MB per worker)

**STRONG RETENTION VALUE DOCUMENT.**

**Status:** fixed 8 Nov 2026 (merge `32bd6c3f`, commit `22af1f00`): `core/spawn_child.py`
(`importing_parents_main`) and the guarded application imports in `main.py` / `main_mc.py`. Regression bar:
`tests/test_visualizer_engine_frozen_spawn.py` (a spawn from a `main.py` parent loads no Qt GUI stack; the
negative control re-runs the old module level and fails 5 tests). Operator check still open: the same on a frozen build.
Found by checkpoint audit 10 (`Docs/Future_Work/Native_Core_P2_Audit.md`, A10-M1) while the native core's engine worker
was being made dormant; it was never a native-core bug: every worker role had it.

## Symptom

None visible. Each spawned worker (the image workers, the image prefetch worker, the Visualizer's engine worker) took
about 1.3 s longer to become ready than its own target needs and held about 80 MB more memory, with the Qt GUI, Quick,
Widgets, QML, Network and OpenGL modules loaded in a process that draws nothing. It only became visible as a cost once
5.7 retired and respawned the engine worker on every Settings round trip, and its first configure has a 6 s bound.

## Measured (spawn from a `main.py` parent, medians of 3)

| Worker | Ready | RSS | USS | Qt in the child |
| --- | --- | --- | --- | --- |
| Engine worker, before | 1.62 s | 112.4 MB | 83.1 MB | 7 PySide6 modules, 10 Qt6 DLLs |
| Engine worker, after | 0.29 s | 32.3 MB | 18.8 MB | none |
| Image worker, before | 1.56 s | 112.2 MB | 82.9 MB | 10 Qt6 DLLs |
| Image worker, after | 0.29 s | 32.0 MB | 18.5 MB | none |

Evidence: `.artifacts/evidence/architecture/native_core_p2/20261108_audit10_spawn_cost/` (`spawn_cost.json`, probes).

## Cause

Windows has only the `spawn` start method: a child process re-executes the parent's main module before it runs its
target. From source multiprocessing runs it as `__mp_main__`; a Nuitka build runs the same executable with
`--multiprocessing-fork` and compiles the root module a second time as `__parents_main__`. `main.py` did all its
application work at module level (the GL error policy, the Quick environment, PySide6 QtWidgets/QtGui/QtCore, logging,
Settings, the engine), so every worker paid for the whole application before its own small target. Nothing failed:
the work was simply wasted, in every worker, since spawn workers existed, growing with every import added to
`main.py`'s top.

## Fix

`main.py` asks `core.spawn_child.importing_parents_main(__name__)` (standard library only) before its application
imports and skips them in a worker; the imports stay at module level behind that check, so the parent runs the same
statements in the same order and tests that patch `main.QTimer` / `main.ScreensaverEngine` still work. A worker
inherits its environment (thread-pool sizes, the Quick render-loop variables) from the parent that set it. `main_mc.py`
does the same.

## Why it hid

- No worker failed, and no test measured a spawned worker's imports: the worker tests built their targets in process.
- The cost was paid once per worker at startup, inside "startup is slow by design" (lifecycle spikes are not counted).
- The native core's QtCore-only proof (slice 5.4) checked what the engine worker's *own* code imports, not what its
  process had loaded before the target ran (5.7 found it; audit 10 measured it).

## Lessons

1. A spawned worker's real import set is the parent's main module plus its target. Measure it from a real spawn of the
   production entry, never from importing the target in a test.
2. Keep an entry module's top level to what every process needs; application work goes behind
   `importing_parents_main` or into `main()`.
3. A new worker role inherits this automatically now; `tests/test_visualizer_engine_frozen_spawn.py` fails if an
   import that loads the Qt GUI stack moves above the check.

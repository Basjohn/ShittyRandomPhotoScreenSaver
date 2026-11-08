# R-176 | Every worker process loaded the whole application before its own target (~1.3 s and ~80 MB per idle worker)

**STRONG RETENTION VALUE DOCUMENT.**

**Status:** fixed 8 Nov 2026 (merge `32bd6c3f`, commit `22af1f00`): `core/spawn_child.py`
(`importing_parents_main`) and the guarded application imports in `main.py` / `main_mc.py`. Regression bar:
`tests/test_visualizer_engine_frozen_spawn.py` (a spawn from a `main.py` parent loads no Qt GUI stack; the
negative control re-runs the old module level and fails 5 tests). Operator check still open: the same on a frozen build.
Found by checkpoint audit 10 (`Docs/Future_Work/Native_Core_P2_Audit.md`, A10-M1) while the native core's engine worker
was being made dormant; it was never a native-core bug: every worker role had it.

## Symptom

None visible. Each spawned worker (the image workers, the image prefetch worker, the Visualizer's engine worker) took
about 1.3 s longer to become ready than its own target needs and held about 80 MB more memory while idle, with the Qt
GUI, Quick, Widgets, QML, Network and OpenGL modules loaded in a process that draws nothing (a configured engine worker
saves less: about 0.7 s to its first configure and about 40 MB in a session; see Measured). It only became visible as a cost once
5.7 retired and respawned the engine worker on every Settings round trip, and its first configure has a 6 s bound.

## Measured (spawn from a `main.py` parent, medians of 3)

These are an **idle, unconfigured** worker: `Process.start()` to its ready message, and memory 1 s after ready, before
any request (checkpoint audit 11, A11-L1).

| Worker | Ready | RSS | USS | Qt in the child |
| --- | --- | --- | --- | --- |
| Engine worker, before | 1.62 s | 112.4 MB | 83.1 MB | 7 PySide6 modules, 10 Qt6 DLLs |
| Engine worker, after | 0.29 s | 32.3 MB | 18.8 MB | none |
| Image worker, before | 1.56 s | 112.2 MB | 82.9 MB | 10 Qt6 DLLs |
| Image worker, after | 0.29 s | 32.0 MB | 18.5 MB | none |

Evidence: `.artifacts/evidence/architecture/native_core_p2/20261108_audit10_spawn_cost/` (`spawn_cost.json`, probes).

What a worker in use saves is smaller, because part of what the old preload loaded is the worker's own work, which
it now imports when it first needs it (audit 11):

- **Engine worker:** its first configure imports the session's graph (runtime controller, beat engine, tick pipeline,
  logical edges, technical config, `ThreadManager`): 1.69-1.72 s from a bare start, against 1.03-1.16 s when the old
  preload had already loaded part of it (audit 11 probe, 3 runs, source tree). About 0.6 s of the 1.33 s saving moved
  into that first configure (inside the worker's message loop and the first configure's 6 s bound), so ready plus
  first configure is about 0.7 s faster, not 1.3 s. A configured worker in a session holds about 71 MB (audit 10,
  bare entry), so its in-session saving is about 40 MB, not 80. The liveness rig's 1.25 s test heartbeat started
  retiring healthy workers mid-configure (0d32b308) because of this shift.
- **Image workers** keep nearly all of it. Their target (`core/process/workers/image_worker.py`) imports at module
  level only the standard library, `core.process.*`, `core.logging.logger` and `rendering.image_quality` (Pillow).
  The first decode on the default Qt path (`smooth`, no sharpen) imports `PySide6.QtCore`, `PySide6.QtGui` (`QImage`),
  `rendering.display_modes` and `rendering.image_processor_async`: about 0.1 s and about 12 MB in a bare
  interpreter (audit 11 resolution, 3 runs). The Pillow path imports nothing more. Neither loads QtWidgets, QtQuick,
  QtQml, QtNetwork, QtOpenGL, the engine or Settings.

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
4. Measure the configured worker, not only spawn-ready. A worker's ready message comes before its own imports: a
   saving measured at ready can be partly a cost moved into the first request (here ~0.6 s of 1.3 s moved into the
   engine worker's first configure), and idle memory is not in-session memory (~40 MB saved, not 80). Time ready plus
   the first request, and read memory inside a session, from the production entry.

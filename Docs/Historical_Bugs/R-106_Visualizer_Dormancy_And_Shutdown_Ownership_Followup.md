# R-106 | Visualizer Dormancy and Shutdown Ownership Follow-up

Status: **OPEN / FOLLOW-UP**  
Opened: 2026-10-05  
Working source: GODZIP `ad96bb78a3`  
Binding contracts: `Docs/Guardrails/Performance_Optimization_Contract.md` P5 and
`Docs/Guardrails/Visualizer_Presentation.md` 1A.

## Why this exists

The mode registry, render host and Scene3D consumers are broadly lazy and retire correctly, so the architecture is not carrying
one full runtime per installed Visualizer. Two remaining logical hot-path smells violate the stronger count-invariance contract,
and the supplied shutdown log exposes a separate late-Python-owner retirement problem.

## Dormancy smell 1 | Sine heartbeat can run while Sine is inactive

`widgets/spotify_visualizer/tick_pipeline.py::logical_tick()` calls `process_heartbeat(widget, now_ts)` unconditionally.
`process_heartbeat()` currently exits only when:

```text
_sine_heartbeat <= 0.001
or engine is None
```

It does **not** require the active mode to be `sine_wave`.

A Custom Sine heartbeat value therefore survives mode switches through normal resolved configuration and can continue doing
mode-specific work while Bubble, Sphere, Extruded Spectrum, etc. is active. That work includes energy-band reads, heartbeat EMA
state and transient/event-scheduler checks.

The shipped/default Sine presets use heartbeat zero, so this is usually dormant in ordinary defaults. That makes it easy to
miss, but it still violates the product contract for user-authored settings.

Required correction: heartbeat ownership resolves with the active Sine logical hook; inactive Sine performs zero heartbeat
queries/updates.

## Dormancy smell 2 | common tick grows one early-return dispatch per mode

The same common tick currently calls:

```text
dispatch_bubble_simulation(widget, now_ts)
dispatch_devcurve_field(widget, now_ts)
```

Both helpers return quickly when another mode is active. The present cost is tiny, but copying that pattern for every future
mode would make inactive-mode cost scale linearly with registry size.

Required correction: mode activation resolves one optional mode-specific logical-step hook. The common tick invokes that one
callable (or `None`). Adding mode N+1 must add no branch/call to mode N's steady-state path.

## Required regression shape

Dormancy tests must derive from the canonical Visualizer registry rather than a hand-written mode subset and prove:

- registry/common-owner import does not import every mode runtime/renderer;
- only the requested mode runtime/renderer is constructed;
- inactive modes with deliberately expensive/non-default settings are not advanced, queried or allocated;
- repeated switches retire previous consumer resources and logical state;
- adding many synthetic registered modes does not increase recurring common-tick work for the one active mode.

The useful mental test is: **100 registered modes + one active mode ~= one mode of runtime work.**

## Supplied shutdown evidence | Python owners outlive the terminal barrier

At 2026-10-05 12:37:36 the lifecycle barrier timed out after the Quick/QML destruction stream had largely drained:

```text
reason=application_exit
retiring_generation=0
qobjects={}
python_owners={'QuickDisplayUnit': 1, 'QuickDisplayPresenter': 1, 'QuickDisplayVisualizerOwner': 1}
resources=[]
thread_work=[]
global_subscriptions=[]
```

This is not evidence of surviving GL resources, registered QObjects or thread work. Those categories were already empty. It is
evidence that one Python ownership chain for the display/presenter/visualizer trio remains strongly reachable past the terminal
retirement boundary.

Investigation should start from the consumer-owner references and shutdown ordering, not by increasing the barrier timeout.
Useful questions:

- which object still strongly owns `QuickDisplayUnit` after its QML/Quick objects are destroyed;
- whether `QuickDisplayPresenter` and `QuickDisplayVisualizerOwner` retain each other or remain reachable from a retiring
  runtime/unit container;
- whether a callback/listener slot is already logically detached but still stored in a Python object that the barrier counts;
- whether the barrier samples Python owners before the final container reference is cleared.

Acceptance: normal stop/recreation reaches zero for those owners before the existing barrier expires, with no forced GC and no
new polling/timer.

## Intermittent exported-memoryview startup failure | first containment landed, root acceptance open

After the tiny-radius Bubble presentation candidate was applied, two consecutive startups aborted while printing:

```text
Exception ignored in tp_clear of: <class 'memoryview'>
Traceback (most recent call last):
  File ".../OpenGL/arrays/lists.py", line 179, in asArray
    return arrayType(value)
BufferError: memoryview has 1 exported buffer
IMAGE Worker: Exiting normally
IMAGE_PREFETCH Worker: Exiting normally
```

A later startup succeeded, so this is intermittent and must not be treated as an ordinary deterministic PyOpenGL call failure.
The Bubble candidate itself still changes no GL renderer, upload transport or worker lifetime. More importantly, CPython issue
#110408 documents this same `memoryview.tp_clear` unraisable with traceback frames that move between unrelated Python code under
debugger/multiprocessing timing. The shown `OpenGL/arrays/lists.py` frame is therefore evidence of where Python happened to be
executing, not proof that PyOpenGL owns the exported buffer.

### Concrete evidence from the supplied run

The attached 2026-10-05 run was launched with `--frame-trace` and closed with 2,245,565 records written. The trace writer used:

```text
view = memoryview(data)
...
_file.write(view[:take])
...
view = view[take:]
```

`data` is already a private `bytes` batch copied out of the ring. Carrying a memoryview and exporting it into buffered file I/O
is unnecessary diagnostic-side buffer ownership, so the first containment removes memoryview from this writer entirely and
uses byte offsets/slices instead. The rolling format, record alignment, segment retention and writer ownership do not change.
This path exists only for explicit `--frame-trace`; ordinary product runtime pays no new cost.

The same supplied run ended image shared-memory accounting at:

```text
segments_live=0
live_bytes=0
close_failures=0
unlink_failures=0
```

That does not prove the image transport can never participate in a future failure, but it is positive evidence against an
unreleased image mapping in this captured run. Do not rewrite that transport merely because `memoryview` appears in its API.

### Acceptance / branch rule

1. Re-run the same startup/soak command with `--frame-trace` repeatedly. The exported-buffer unraisable/startup abort must not
   recur. `tests/test_frame_trace.py` also pins the writer to owned bytes and forces several segment boundaries.
2. If the exception appears with **no** `--frame-trace`, treat it as a separate branch. Record whether `sys.gettrace()` is active
   (PyCharm/other debugger) and whether the lazy FEEDS `ProcessPoolExecutor` had been admitted. CPython #110408 specifically
   ties the same random-frame unraisable to debugger + process-pool timing, and SRPSS has such a lane.
3. Do not suppress `sys.unraisablehook`, force GC, lengthen shutdown waits, or globally disable workers as a "fix". The next
   branch must remove a concrete ownership hazard or isolate a confirmed interpreter/debugger defect.

Status: **CONTAINMENT LANDED / PHYSICAL REPRO ACCEPTANCE OPEN**.

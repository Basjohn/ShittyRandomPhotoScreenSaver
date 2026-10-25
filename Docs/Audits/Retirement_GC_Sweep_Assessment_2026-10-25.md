# Retirement GC sweep: assessment (2026-10-25)

**Status:** assessment only. **Cause found (R-169):** the opt-in GUI stall sampler's frame-map cycle, fixed
without any sweep (option A); this stays as the record of why a sweep was not adopted. The per-retirement sweep (commit `c8a00d08`) was reverted in `635587c3`; nothing here is
implemented. Live task: `Current_Plan.md` §2A "Settings-open lifecycle barrier timeout". First find the actual cycle
(referrer snapshot now on in source runs, `ec2f0920`), then decide whether any sweep mechanism is wanted.

## The failure being solved

`[LIFECYCLE_BARRIER] timeout` with every QObject gone and `QuickDisplayUnit` + `QuickDisplayVisualizerOwner` alive.
A non-terminal timeout calls `QCoreApplication.exit(1)`: **the saver closes instead of opening Settings** (preserved run
2026-10-24 16:35: timeout at :19, `Exiting (code=1)` at :23).

## Facts established

- **They are cyclic garbage, not held.** Preserved run: retirement 0 completed only through the thaw sweep
  (`collected=13207`); retirement 1 had no sweep and timed out. Whole-session GC counts were `(132, 5, 1)`; the one gen2
  was that sweep.
- **The collector will practically never free them on its own.** Python 3.14.8 (non-incremental here: gen2 counts
  advance). Measured: an old-generation cycle is reclaimed after ~267k tracked allocations at interpreter defaults
  `(2000, 10, 10)`, but ~2.26M (1,071 young collections) at the RUN policy's `(2000, 20, 50)`. The preserved session made
  132 young collections in total, so a retired generation's cycles stay for the session: an 8 s barrier cannot wait
  them out.
- **Today's behaviour is inconsistent.** The startup freeze runs once, 45 s into RUN, and only while RUNNING. Only the
  first retirement after it gets a thaw sweep (`thaw_for_runtime_retirement` → `collect_thawed_retirement_cycles_once`).
  A cycle is therefore swept or fatal depending on uptime (Settings before 45 s: no freeze, no sweep) and on which
  retirement it is. That makes the defect look random.
- **Every barrier retirement is a full teardown.** The barrier is armed only in `teardown_display_runtime` (reasons
  `settings`, `custom_edit`, `monitor_topology`, `application_exit`, `cli_exit_after`; plus the separate
  `settings_dialog_close` dialog barrier). No display renders while it waits, so a sweep there cannot hitch another
  display (an earlier worry, unfounded).

## Historical records against a sweep

- **R-53** (runtime recreation): "The barrier proves release; it never forces release with `gc.collect()`"; "no
  production/periodic `gc.collect()`". **R-56** and **R-59** repeat it for the Settings paths.
- **R-154**: the same class (`QuickDisplayUnit`) was held through a signal-retained bound method; the fix made it
  "reclaimable by reference counting alone", proven by a test that freezes GC. That is the established standard.
- **R-90**: a ctypes/COM cycle whose finalizer ran "at an arbitrary later GC" double-released a COM pointer (native
  fault). A sweep runs *every* pending cycle's finalizer at that moment, not just the retiring generation's.
- **R-99**: frozen objects are invisible to `gc.get_referrers`; attribution needs the freeze lifted (it is, after the
  first retirement's thaw).
- **Performance contract**: gen2 pauses of 41–146 ms each coincided with a visible Visualizer hitch; "do not … move
  forced collections merely because aggregate counters look cleaner". Startup/teardown windows are not stall points.
- **EB Target note**: "Never relax the barrier, add a timeout retry, call `gc.collect()` routinely …".

## Where a sweep would cause unwanted behaviour

1. **It hides the detector.** The barrier is the project's cycle detector for runtime owners (R-53/R-154). Sweeping
   turns every new cycle into silent memory churn; regressions stop being visible unless something else reports them.
2. **It can wake crashes that are dormant today.** A sweep collects *every* unreachable cycle in the process, so it runs
   their finalizers: R-90-class native releases, parentless PySide QObjects/timers owned by another thread, worker-side
   objects. Because the RUN policy makes deep collections so rare (one per session observed), a latent finalizer bug
   in such a cycle very likely never runs today. A sweep at every Settings / custom-edit / monitor teardown would run it
   regularly, during teardown itself. A sweep does not create the defect, but it can turn a dormant one into a crash
   users see. This is the strongest argument against B and C.
3. **A pause at every full teardown.** After the first thaw nothing is frozen, so each sweep scans the whole heap:
   expect the historical 50–150 ms (the thaw sweep measured 86.9 ms). It is inside the lifecycle window (not counted as a
   stall) but adds to Settings-open, custom-edit and monitor-wake latency.
4. **It holds the GIL for that pause.** Audio capture, feeds, COM volume callbacks and the logging thread wait. Harmless
   while displays are down, but nothing visual depends on it either.
5. **It contradicts recorded decisions** (R-53/R-56/R-59, the EB note). Any sweep needs an explicit supersession.

## Where a sweep would help

1. **No more "Settings closes the saver".** A cyclic, unheld owner no longer fails closed; only genuinely held owners
   do.
2. **Consistency.** The first and later retirements, before or after the 45 s freeze, would behave the same.
3. **Memory.** Each retirement's cyclic Python graph (13k objects on the first; controller/simulation state included)
   is reclaimed instead of accumulating for the session.

## Options

| | Behaviour on a cycle | Detection kept? | User impact |
| --- | --- | --- | --- |
| **A. Strict, find every cycle** (current) | fails closed; saver exits | yes (timeout + snapshot) | exits until each cycle is fixed |
| **B. Always sweep** (reverted) | silently reclaimed | no | none, but regressions hidden |
| **C. Snapshot, then recover** | snapshot the referrers loudly, then one sweep; still-held owners still fail closed | yes (logged with referrers every time; R-154-style refcount-only tests stay the gate) | none |
| **D. Make the existing exception consistent, no new sweep** | fails closed every time, even the first | yes | exits more often |

**Assessment:** A is right for development, but leaves users exposed whenever a new cycle appears. C keeps detection
(the referrer snapshot is taken *before* the sweep and logged as a warning on every occurrence, and refcount-only tests
remain the real gate), stops the user-facing exit, and makes behaviour consistent. It still carries harms 2–5 (harm 2 above all: it can
surface dormant finalizer crashes) and must
supersede R-53/R-56/R-59 explicitly. Decide after the actual cycle is found: if it is a single new edge on the framed
path, fixing it (A) may be enough and C becomes a separate product-robustness question.

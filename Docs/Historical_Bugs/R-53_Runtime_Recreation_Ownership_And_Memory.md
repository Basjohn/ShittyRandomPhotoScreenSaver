# R-53 — Retired Runtime Generations Survived Full Edit/Settings Recreation

Date opened: 2026-08-01  
Latest evidence: 2026-08-08  
Status: Pointer-width admission correction implemented after failed installed validation; lifecycle and plateau proof pending

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Original Failure

Equivalent-state runtime samples climbed from about 832.5 to 911.5 to 1,000.6 to 1,146.8 MiB main RSS across repeated Edit/CUSTOM Save-and-Continue and Settings restart cycles. Dedicated VRAM climbed from about 554.8 to 600.8 to 722.9 to 806.7 MiB while tracked known bytes changed only from about 456.9 to 455.9 to 471.7 to 489.1 MB. Generation-owned unknown `ResourceManager` entries accumulated from 35 to 52 to 74.

Explicit display/GL cleanup remained authoritative and successful: tracked textures, PBOs, display pixmaps, and total tracked GL bytes reached zero during Settings teardown and driver VRAM dropped substantially. This is a session-lifetime retired-owner problem under P5.4, not a reason to weaken teardown, enlarge caches, or reopen Phase 4.

## Implemented Barrier Correction

Recreation now has a non-reentrant destruction barrier after generation invalidation and explicit owner-context GL cleanup. It generation-rejects queued/delayed UI work, waits for watched QObject destruction plus zero retiring-generation resources/tasks/timers/subscriptions, and only then admits replacement construction. Settings uses a second barrier for its dialog tree. Registrations and lifecycle snapshots carry generation, owner identity/class, QObject validity, bounded creation-site, and callback-retention details. Display-pixmap accounting is captured on the GUI thread and published as a detached immutable sidecar so the background usage sampler never inspects live Qt pixmaps.

The correct destruction barrier also created a deliberate interval with no top-level window after Settings closed. Qt's default last-window policy could queue application quit before the dialog barrier constructed the replacement. Successful RUN startup therefore uses explicit-exit lifetime ownership with `setQuitOnLastWindowClosed(False)`; startup-failure/config-only paths remain unchanged.

## Earlier Follow-Up Evidence

The 2026-08-01 installed run completed Settings → generation 1, CUSTOM → generation 2, and Settings → generation 3 recreation. Equivalent settled main RSS was about 900.9, 901.2, and 895.2 MiB; dedicated VRAM about 539.2, 554.9, and 540.0 MiB; and ResourceManager totals/unknowns 58/47, 58/47, and 56/45. That eliminated the former approximately 80–90 MiB main-RSS, large VRAM, and 35 → 52 → 74 ResourceManager staircase across those replacements.

It did not close P5.4: equivalent private commit rose about 2,911.4 → 2,944.7 → 3,000.2 MiB, handles rose 2,130 → 2,146 → 2,189, and barriers still weak-observed manager wrappers after recreation.

## 2026-08-02 Evidence

Temporary evidence identity:

```text
logs/evidence_chest/08_02_3877b2c7_20_27/
```

The supplied archive was `logseditfailure.zip` and corresponds to `main` at `3877b2c7` plus the documentation-only migration commits made afterward.

### Settings recreation now passes the known ownership barrier

Two consecutive Settings cycles completed full runtime teardown, dialog teardown, replacement construction, authoritative first frame, and coordinated reveal.

First Settings cycle:

```text
retiring generation: 0
barrier armed:       176 QObjects, 2 PixelShiftManager owners
barrier complete:    219 ms
settings dialog:     constructed only after completion
dialog barrier:      2 QObjects, 0 Python owners, complete in 16 ms
replacement:         generation 1 revealed from its own authoritative frame
```

Second Settings cycle:

```text
retiring generation: 1
barrier armed:       166 QObjects, 2 PixelShiftManager owners
barrier complete:    203 ms
settings dialog:     constructed only after completion
dialog barrier:      2 QObjects, 0 Python owners, complete immediately
replacement:         generation 2 revealed from its own authoritative frame
```

No persistent visualizer compute lane was registered. Bubble diagnostics reported `lane_registrations=0` and a `1.000` offered/submitted/published ratio through the tested interval.

### The old linear Settings memory staircase did not reproduce

Lifecycle `replacement_settled` snapshots were:

```text
state                    main RSS   main private   handles   threads   tracked known   RM total/unknown
cold generation 0         848.4       2093.2        1790       61        424.7 MiB         61 / 50
Settings generation 1     949.5       2188.4        1838       67        424.6 MiB         56 / 45
Settings generation 2     946.6       2179.1        1823       62        413.4 MiB         54 / 43
```

The first post-Settings runtime sat about 101.1 MiB higher in main RSS and 95.2 MiB higher in main private bytes than the early cold-settled snapshot. The second Settings cycle did not add another step: main RSS fell 2.9 MiB, main private fell 9.3 MiB, handles fell 15, threads fell 5, tracked known bytes fell 11.2 MiB, and ResourceManager total/unknown counts both fell.

The cold snapshot was earlier in runtime warm-up and used Spectrum, while both post-Settings snapshots used Bubble. The one-time uplift therefore does not yet have a cause above 90% confidence and is not proof of a retained generation. The former approximately linear per-cycle Settings accumulation is not present in this batch.

Dedicated-VRAM fields in lifecycle snapshots inherit the latest asynchronous usage sample and were sometimes 13–14 seconds old during dialog gaps. They are valid for broad teardown/recovery shape, not exact same-instant comparison. Tracked GL bytes nevertheless reached zero during each teardown, and usage telemetry observed driver dedicated VRAM near 8 MiB while no display runtime existed.

### CUSTOM/Edit remains fail-closed and now proves the re-entrant cause

The user entered a dual-display CUSTOM session, resized widgets, and selected Save-and-Continue. All eleven edited scene entries were written before teardown began.

The current synchronous path then performed full runtime teardown from inside `CustomLayoutManager.commit_session_without_reload()`:

```text
Edit action
→ CustomLayoutManager.save_session()
→ persist scene and finish shells
→ synchronous custom_layout_reload_requested relay
→ engine.stop(reason=custom_edit)
→ display/GL teardown and manager cleanup
→ return into the still-running CustomLayoutManager save/finally frame
```

The barrier armed with:

```text
224 QObjects
2 CustomLayoutManager owners
2 PixelShiftManager owners
0 thread-work blockers after producer stop
```

Every watched QObject, tracked resource, thread task, and global subscription reached zero. Both PixelShift owners released. Exactly two `CustomLayoutManager` Python owners—one per display—remained for the entire eight-second timeout. The application then exited deliberately with code 1; this was the fail-closed lifecycle policy, not an unhandled process crash.

The log contains direct re-entrancy proof. Display cleanup called `CustomLayoutManager.cleanup()`, which cleared `manager._display`. Control then returned to the original save function's `finally` block, which tried to clear `_custom_layout_runtime_reload_pending` through those already-cleaned managers and produced two suppressed:

```text
AttributeError: 'NoneType' object has no attribute '_custom_layout_runtime_reload_pending'
```

Confidence that full recreation is admitted from inside the retiring Edit graph: **greater than 99%**.

Confidence in the exact final eight-second strong-reference edge: **below 90%**. Shell resolver/applier closures, manager-bound signal callback records, the action/key-filter dispatch frame, or a combination may retain the manager wrappers after the immediate save frame unwinds. A live `gc.get_referrers` capture is still absent. The exact edge does not change the required architecture: explicit shell callback retirement and later engine-owned reload admission are both required.

## Required Correction

1. Persist the complete CUSTOM scene without weakening graph-based placement authority.
2. Explicitly retire shell callbacks, signal connections, pointer grabs, snapshots, grid overlays, class-level active-manager/key-filter/restack state, and manager-owned temporary data.
3. Return from every manager/action/key-filter save frame.
4. Queue one engine-owned immutable reload intent on a later GUI turn.
5. Validate runtime generation and exact DisplayManager identity, coalesce duplicates, then run the same full runtime stop, destruction barrier, reconstruction, graph replay, and authoritative-first-frame reveal.
6. Never capture a manager, display, shell, edited widget, pixmap, bound manager method, or shell state in the queued continuation.
7. Keep `CustomLayoutManager` observed by the destruction barrier; do not hide it from accounting.

The full runtime reinitialization and graph-based placement/replay systems remain mandatory. This correction changes only the admission boundary.

## 2026-08-08 Mechanical Repair

The production path now persists the same complete scene graph, explicitly retires each temporary Edit shell, and returns through the manager-owned save/reset/slot frame before teardown is eligible to begin. Shell retirement is idempotent and releases pointer grabs, manager-bound signals, resolver/applier closures, temporary event filters, snapshots, guides, and transfer state. Save/reset/slot replacement paths discard deferred image payloads owned by the retiring runtime; cancel still restores the deferred image into the unchanged runtime.

`custom_layout_reload_requested` now carries request kind, runtime generation, and exact `DisplayManager` identity. The engine converts that data into a frozen primitive-only intent, coalesces duplicates, and admits it through a zero-delay `ThreadManager` GUI callback. The admission callback revalidates generation, exact manager identity, Settings/barrier ownership, terminal state, and current runtime availability before invoking the unchanged full stop → destruction barrier → reconstruction path. The callback captures the process-lifetime engine and immutable intent only; it does not capture a manager, display, shell, widget, pixmap, shell state, or bound manager method.

Focused production-shaped regressions prove:

- complete two-display positions, sizes, routes, and graph replay;
- both temporary shells die without `gc.collect()` after committed retirement;
- both barrier-observed `CustomLayoutManager` owners die without `gc.collect()` before replacement continuation;
- stale generation and manager identity are rejected;
- duplicate requests produce one queued admission and exactly one replacement;
- committed reload discards deferred image state while cancel restores it;
- `CustomLayoutManager` remains part of runtime-root observation.

The focused CUSTOM/lifecycle set passed 161 tests, and the adjacent display/widget lifecycle set passed 104 tests with four environment skips. This is mechanical evidence only. No installed dual-display Save-and-Continue or memory-plateau evidence has yet been collected for this repair.

## 2026-08-08 Installed Admission Failure And Correction

The first installed dual-display Save-and-Continue attempt persisted all eleven graph entries and retired the Edit session, but emitted no `CUSTOM layout reload queued` event and began no runtime teardown. The next teardown in the run was an unrelated Settings action fourteen seconds later.

The exact defect was signal width. Both `DisplayWidget.custom_layout_reload_requested` and `DisplayManager.custom_layout_reload_requested` declared the exact manager identity as Qt `int`. On 64-bit Python the observed object identities are pointer-width values (for example, approximately `1.866e12` in this run), while Qt's registered `int` is signed 32-bit. A project-venv reproduction produced Shiboken's overflow warning and delivered a truncated negative identity. The engine's exact-identity guard then correctly rejected the request as stale.

The test double had used identity `0`, so the production-shaped relay tests did not exercise the platform boundary. Both production signals and the real-signal test double now carry the identity as a Python object, and regressions require an identity above `2**32` to arrive unchanged at both signal layers.

The manager's old exception-only fallback to `_reload_widgets_across_instances()` was also removed. A committed Save/Reset that cannot request mandatory full recreation now logs the failure and exits with code 1. A widget-only teardown/setup is not a valid substitute for engine-owned full reconstruction.

Mechanical validation proves pointer-width identity survives the relay and a request failure performs no local widget rebuild. The later 17:07 installed capture completed one dual-display CUSTOM Save-and-Continue, admitted exactly one full replacement, crossed the retired-runtime barrier, and revealed only after the replacement generation's authoritative first frame. This closes the admission defect, not the five-cycle memory/resource gate.

## Settings Dialog Sibling Defect

Both successful Settings cycles emitted three caught `RuntimeError` traces after `dialog.exec()` returned because the close path touched a `SettingsDialog` wrapper whose C++ object had already been deleted by `WA_DeleteOnClose`. This is tracked separately as R-56. It did not block Settings recreation, but it is not acceptable lifecycle bookkeeping.

## Image Prefetch Sibling Defect

The same run emitted one `ImagePrefetcher._pump_scaled_prefetch()` `IndexError: pop index out of range`. This is independent of recreation ownership and is tracked separately as R-57.

## Signal-Bookkeeping Resolution

`WidgetManager` now tracks explicit ownership of its one-shot `image_displayed` connection. The ownership bit is cleared before touching Qt, so first readiness and terminal cleanup cannot attempt the same disconnect twice; disposed-sender cleanup remains fail-safe. A real PySide signal regression proves exactly one disconnect, and the 17:07 installed capture contains no repeat warning. This changes signal bookkeeping only and does not weaken authoritative first-frame readiness.

## Presentation Guardrail

The destruction barrier is separate from the authoritative-first-frame barrier. A replacement stays hidden until its own runtime generation, visualizer engine generation, and activation identity produce valid presentation state. `FadeCoordinator` remains the sole reveal coordinator. First-frame poison and Bubble → Spectrum → Bubble protections may not be weakened.

## Forbidden Substitutes

- no nested `processEvents()` teardown loop;
- no periodic or production `gc.collect()`;
- no working-set/allocator trimming;
- no process or worker recycling to conceal ownership;
- no cache enlargement;
- no warm standby or retired-tree reuse;
- no reduced GL teardown;
- no ignored manager owner or longer timeout.

## Validation Still Required

- Completed once: installed dual-display Save-and-Continue produced exactly one replacement runtime with no manager-owner timeout. Repeat it inside the mandatory alternating-cycle matrix below.
- Run at least five alternating installed Edit and Settings cycles with image work, Bubble/Spectrum/mode switches, transition overlap, media/artwork, and pending callbacks.
- Require every retired generation to reach zero roots, timers, animations, subscriptions, ThreadManager work, and generation-scoped ResourceManager entries.
- Require equivalent-state RSS, private commit, VRAM, handles, and threads to plateau.
- Require exactly one current-generation authoritative first-frame event before coordinated reveal.

## Evidence

- `logs/evidence_chest/08_02_3877b2c7_20_27/` — temporary installed evidence identity
- `Docs/phase_reports/P05_CPU_TASK_REDUCTION.md`
- `Current_Plan.md`
- `engine/runtime_destruction.py`
- `rendering/custom_layout_manager.py`
- `engine/engine_handlers.py`
- `tests/test_runtime_destruction.py`
- `tests/test_custom_layout_manager.py`

## Migration Record

This is the current standalone detailed record. The older embedded R-53 entry in `Docs/Historical_Bugs.md` remains untouched during the copy-first historical-document migration and should be treated as an earlier evidence snapshot until the final index cutover.

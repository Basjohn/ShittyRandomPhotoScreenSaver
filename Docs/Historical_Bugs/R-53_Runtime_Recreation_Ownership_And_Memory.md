# R-53 — Retired Runtime Generations Survived Full Edit/Settings Recreation

Date opened: 2026-08-01  
Last updated: 2026-08-10  
Status: **SOLVED — recreation ownership/admission and frozen retired-owner retention closed; remaining absolute resource work is separate Phase 5 architecture work**

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Original Failure

Repeated Settings and committed CUSTOM/Edit recreation originally produced an
approximately linear equivalent-state memory/resource staircase. Later evidence showed
that the broad symptom contained several distinct ownership failures rather than one
mysterious allocator problem:

1. full teardown could be admitted from inside the retiring Edit manager/action frame;
2. Settings could retouch a `WA_DeleteOnClose` dialog wrapper after the C++ object was already gone (split to R-56);
3. a 64-bit exact manager identity was temporarily carried through a Qt signed-32-bit `int` signal and therefore rejected after truncation;
4. frozen Nuitka/PySide signal callback wrappers could retain plain-Python `WidgetManager` and `CustomLayoutManager` owners after QObject teardown (root-caused and closed under R-59).

Tracked GL deletion itself could reach zero during the old failures. The incident was
therefore about **retired runtime ownership/admission**, not permission to weaken GL
teardown, enlarge caches, force GC or recycle the process.

## Runtime Destruction Barrier

The correction established a non-reentrant fail-closed destruction barrier after
runtime generation invalidation and explicit owner-context GL cleanup. It observes:

- retiring QObjects and weak-observed Python roots;
- generation resources;
- tasks/timers/animations/subscriptions/callbacks;
- visualizer/display owners;
- first-frame/reveal as a separate post-construction authority.

The barrier proves release; it never forces release with `gc.collect()`, event pumping,
timeout extension or ignored owners.

## Settings Path

Settings recreation moved to process/runtime-owned admission and retained full
stop–destroy–recreate. R-56 separately corrected the modal deleted-wrapper lifetime
mistake by observing the dialog graph while valid and checking Shiboken validity after
`exec()` returns.

## CUSTOM/Edit Admission Root Cause

The decisive failing path was:

```text
Edit action
-> CustomLayoutManager save/commit
-> persist scene + retire shells
-> synchronous custom_layout_reload_requested relay
-> engine.stop(reason=custom_edit)
-> display/GL teardown + manager cleanup
-> return into still-running retiring manager frame
```

That violates ownership regardless of how quickly Qt objects delete. The correct shape
is:

1. persist the complete graph;
2. explicitly retire temporary shell/session ownership;
3. return from manager/action/key-filter frames;
4. queue one primitive/immutable engine-owned reload intent on a later GUI turn;
5. revalidate runtime generation and exact manager identity;
6. run the unchanged full stop → barrier → reconstruction → graph replay → fresh-frame reveal.

No manager, display, shell, widget, pixmap, bound retiring method or shell state crosses
the later-turn handoff.

## Shell Retirement

Committed Edit retirement became explicit and idempotent: pointer grabs, manager-bound
signals, resolver/applier closures, temporary filters, snapshots/guides, transfer state,
grid overlays, class-level active-manager/key-filter/restack state and deferred old
runtime image state are retired before full reconstruction can begin.

## Pointer-Width Identity Correction

The first installed version of the later-turn admission carried Python object identity
through Qt `int`; a 64-bit identity overflowed/truncated and the exact-identity guard
correctly rejected it as stale. Production signals and tests were changed to carry the
pointer-width identity without truncation. The local/widget-only fallback was removed:
a committed Save/Reset that cannot request mandatory full recreation fails loudly rather
than silently substituting partial rebuild.

## Frozen Retired-Owner Follow-Up

A dedicated Diagnostic Runtime later reproduced frozen-only failures even after the
admission sequence was correct. The destruction barrier reached zero QObject/resource/
thread/subscription ownership but retained exactly two `WidgetManager` owners for
Settings; after that was fixed, committed Edit retained exactly two
`CustomLayoutManager` owners.

Failure-only direct-referrer diagnostics identified `builtins.compiled_method` wrappers
for lifetime-critical Qt signal callbacks. The fix, detailed under R-59, replaced those
strong bound-method edges with stable forwarding callables holding weak manager
references and used the exact stored callable for disconnect.

This closed the last frozen retired-owner manifestation without weakening the barrier.

## Final Validation And Closure

The 2026-08-09 compiled Diagnostic Runtime completed both runtime Settings and committed
CUSTOM/Edit Save & Continue after the stable weak-callback corrections. The subsequent
`logs/evidence_chest/08_09_ca830d7_14_59/` mixed-load/current-main evidence completed
four Settings retirements and one committed Edit retirement with destruction barriers
clearing normally and no retired `WidgetManager`/`CustomLayoutManager` timeout.

The user has now declared the Settings/Edit/Diagnostic build issue fully solved. The
remaining Phase 5 questions—absolute RSS/private commit/VRAM, GPU busy, cache efficiency,
UI-thread starvation and longer soak/plateau quality—are **not validation debt for
R-53**. They are general architecture/performance work and must not keep this incident in
Active/Pending status.

## What R-53 Does Not Authorize

- no partial Settings/Edit reinitialization;
- no nested `processEvents()` teardown loop;
- no production/periodic `gc.collect()`;
- no working-set/allocator trimming or process recycling;
- no ignored manager owner or longer destruction timeout;
- no widget-only fallback for committed Edit;
- no reveal before current-generation authoritative state.

## Related Records

- R-56 — Settings deleted-wrapper retouch, solved.
- R-59 — frozen Settings/Edit compiled bound-method owner retention, solved.
- R-57 — independent scaled-prefetch positional-removal defect, solved.

## Evidence

- `logs/evidence_chest/08_02_3877b2c7_20_27/`
- `logs/evidence_chest/08_09_diagnostic_widgetmanager_timeout_02_38/`
- compiled Diagnostic Settings/Edit success on 2026-08-09
- `logs/evidence_chest/08_09_ca830d7_14_59/`
- `engine/runtime_destruction.py`
- `engine/engine_handlers.py`
- `rendering/custom_layout_manager.py`
- `rendering/widget_manager.py`
- `widgets/edit_shell_widget.py`
- focused runtime-destruction/custom-layout/Settings tests

## Guardrail

Never enter full teardown synchronously from a frame owned by the graph being retired.
Return to a process-lifetime GUI turn with primitive identity, reject stale/duplicate
intent, keep destruction fail-closed, and construct/reveal only after the retired graph
is truly gone and fresh authoritative state exists.

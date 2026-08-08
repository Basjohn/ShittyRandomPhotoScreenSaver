# R-56 — Settings Close Path Retouched An Already-Deleted Dialog Wrapper

Date: 2026-08-02  
Last updated: 2026-08-08
Status: Solved after mechanical and installed validation

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Both Settings cycles in the installed `3877b2c7` evidence completed teardown, opened the dialog, closed it, rebuilt the display runtime, and revealed successfully. However, each close emitted three caught Python tracebacks:

```text
RuntimeError: Internal C++ object (SettingsDialog) already deleted.
```

The invalid calls were:

1. `dialog.findChildren(QObject)` while constructing the dialog destruction barrier;
2. `dialog.close()`;
3. `dialog.deleteLater()`.

Temporary evidence identity:

```text
logs/evidence_chest/08_02_3877b2c7_20_27/
```

## Root Cause

`engine/engine_handlers.py` sets:

```python
dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
```

It then calls `dialog.exec()`. When the user closes the modal dialog, Qt deletes the underlying C++ object before `exec()` returns. The Python wrapper may still exist, so:

```python
isinstance(dialog, QObject)
```

remains true even though the wrapped QObject is invalid.

The code constructs the dialog destruction barrier only after `exec()` returns and then treats Python type identity as QObject liveness. It subsequently calls methods on the dead wrapper. The broad exception handlers prevent a fatal failure, but they do not make the ownership sequence correct.

Confidence in this cause: **100%**. The source contract and repeated installed traces match exactly.

## Why Settings Still Returned Successfully

The invalid dialog calls were caught at DEBUG level. The separately owned `SettingsAnimationManager` and its timer were still valid, watched by the dialog barrier, cleaned, and destroyed. The barrier therefore reached zero and admitted one replacement runtime.

This means the main Settings entry/exit path currently works, but its dialog-root observation is partly accidental: the root was already gone before the barrier tried to register it.

## Required Correction

1. Create the Settings dialog destruction barrier before `dialog.exec()` can close and delete the dialog.
2. Register the dialog root, animation manager, animation timer, and any required stable child roots while they are valid.
3. After `exec()` returns, use a real wrapper-validity check such as `shiboken6.isValid()` or a `QPointer`-style contract before any QObject method call.
4. Do not call `close()` or `deleteLater()` again when `WA_DeleteOnClose` has already destroyed the dialog.
5. Clean the animation owner, cancel generation-scoped scheduled callbacks, seal the pre-registered barrier, and admit replacement only after it completes.
6. Keep fail-closed behavior if the dialog or animation graph does not reach zero.

The fix must not remove `WA_DeleteOnClose`, bypass the dialog destruction barrier, add nested event pumping, or merely suppress the RuntimeErrors.

## Implemented Correction

The Settings handler now creates and populates the dialog destruction barrier while the `SettingsDialog`, its child QObjects, the Settings `AnimationManager`, and its timer are valid and before modal execution begins. After `dialog.exec()` returns, every possible QObject touch is guarded by `shiboken6.isValid()` through one narrow wrapper-liveness helper.

If `WA_DeleteOnClose` has already destroyed the dialog, the handler does not enumerate children, close it again, or call `deleteLater()` on the invalid wrapper. If the dialog remains valid, close and deletion retain the existing explicit cleanup path, with validity checked again between those operations. Terminal/stale shutdown cancels the pre-registered barrier and constructs no replacement. Normal completion still seals the barrier and admits exactly one replacement only after the animation/dialog ownership reaches zero.

`WA_DeleteOnClose`, fail-closed barrier behavior, full runtime reconstruction, and the current first-frame/reveal path are unchanged.

## Required Tests

- Open and close a real `SettingsDialog` with `WA_DeleteOnClose` under the production handler shape.
- Prove the barrier watches the valid dialog before modal execution.
- Prove no code touches the dialog wrapper after Shiboken reports it invalid.
- Prove animation manager/timer ownership reaches zero.
- Prove exactly one replacement runtime is admitted after the barrier.
- Prove cancellation/stale-generation paths do not construct a replacement.
- Fail the test on any `Internal C++ object ... already deleted` warning or traceback.

Mechanical validation on 2026-08-08 now covers:

- a real Qt modal delete-on-close signal firing before `exec()` returns;
- a real `SettingsDialog` registered with the destruction barrier before modal execution;
- no invalid-wrapper warning, traceback, close, or deletion retouch;
- dialog and animation weakref release without `gc.collect()` in the production handler shape;
- animation-manager/timer barrier completion;
- exactly one normal replacement;
- terminal/stale close cancellation with zero replacements.

```text
engine lifecycle + SettingsDialog + destruction barrier + RUN lifetime: 82 passed
```

The 2026-08-08 installed run completed two Settings entry/exit/replacement cycles without an invalid-wrapper warning, traceback, or deleted `SettingsDialog` retouch. Both full runtime barriers and both dialog barriers completed before replacement construction, and both replacements reached current-generation authoritative first-frame reveal. R-56 is therefore solved; broader process-memory growth remains a separate active P5.4 issue.

## Current Runtime Result

The two Settings runtime barriers completed in approximately 219 ms and 203 ms, and both dialog barriers completed before replacement construction. This issue therefore does not reopen the removed persistent-lane blocker or the full runtime teardown architecture. It is a specific dialog-close lifetime defect within the otherwise functioning Settings flow.

## Evidence

- `logs/evidence_chest/08_02_3877b2c7_20_27/screensaver_verbose.log`
- `logs/evidence_chest/08_02_3877b2c7_20_27/screensaver.log`
- `engine/engine_handlers.py`
- `engine/runtime_destruction.py`

## Guardrail

A live Python wrapper is not proof of a live Qt object. Whenever QObject ownership can cross modal execution, queued deletion, `WA_DeleteOnClose`, or `deleteLater()`, register destruction observation before the deletion boundary and validate the C++ wrapper before every later touch.

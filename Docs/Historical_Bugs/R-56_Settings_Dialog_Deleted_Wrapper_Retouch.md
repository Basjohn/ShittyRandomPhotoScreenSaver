# R-56 — Settings Close Path Retouched An Already-Deleted Dialog Wrapper

Date: 2026-08-02  
Status: Unresolved; Settings recreation succeeds but lifecycle bookkeeping is invalid

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

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

## Required Tests

- Open and close a real `SettingsDialog` with `WA_DeleteOnClose` under the production handler shape.
- Prove the barrier watches the valid dialog before modal execution.
- Prove no code touches the dialog wrapper after Shiboken reports it invalid.
- Prove animation manager/timer ownership reaches zero.
- Prove exactly one replacement runtime is admitted after the barrier.
- Prove cancellation/stale-generation paths do not construct a replacement.
- Fail the test on any `Internal C++ object ... already deleted` warning or traceback.

## Current Runtime Result

The two Settings runtime barriers completed in approximately 219 ms and 203 ms, and both dialog barriers completed before replacement construction. This issue therefore does not reopen the removed persistent-lane blocker or the full runtime teardown architecture. It is a specific dialog-close lifetime defect within the otherwise functioning Settings flow.

## Evidence

- `logs/evidence_chest/08_02_3877b2c7_20_27/screensaver_verbose.log`
- `logs/evidence_chest/08_02_3877b2c7_20_27/screensaver.log`
- `engine/engine_handlers.py`
- `engine/runtime_destruction.py`

## Guardrail

A live Python wrapper is not proof of a live Qt object. Whenever QObject ownership can cross modal execution, queued deletion, `WA_DeleteOnClose`, or `deleteLater()`, register destruction observation before the deletion boundary and validate the C++ wrapper before every later touch.
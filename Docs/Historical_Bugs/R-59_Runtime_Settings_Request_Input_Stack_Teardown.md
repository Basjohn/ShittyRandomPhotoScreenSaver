# R-59 — Frozen Settings/Edit Recreation Retained Compiled Bound Methods

Date: 2026-08-08
Last updated: 2026-08-09
Status: Resolved in compiled Diagnostic Runtime; standard/Media Center delivery validation remains a Phase 5 release gate

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Opening Settings through the standalone `--s` route worked, while requesting
Settings from a running packaged screensaver or Media Center build terminated
the application. Script-mode runtime recreation also appeared healthy. The first
failure mode was a lifecycle sequencing error: the runtime key/signal route could
enter full display teardown from the same Qt input/signal call stack owned by a
display being retired.

After that sequencing defect was corrected, fresh frozen builds still failed.
The separate Diagnostic Runtime showed that Settings admission was occurring,
full runtime stop completed, all watched QObjects were destroyed, generation
resources/thread work/global subscriptions reached zero, yet exactly two
retired `WidgetManager` Python owners remained alive until the existing
8-second destruction barrier intentionally exited fail-closed.

Once the `WidgetManager` retention was corrected, Settings completed correctly
in the compiled Diagnostic Runtime. Committed CUSTOM/Edit then exposed the same
underlying frozen ownership defect one layer lower: Save & Continue completed
QObject teardown but retained exactly two `CustomLayoutManager` Python owners
until the barrier failed.

The defect therefore had two sequential manifestations in the same family:

1. Settings retained one `WidgetManager` per display through compiled signal
   callback wrappers.
2. Edit retained one `CustomLayoutManager` per display through compiled
   `EditShellWidget` signal callback wrappers.

Neither failure justified weakening the destruction barrier. The barrier was
correctly detecting retired Python owners that source-mode tests did not expose.

## Stage 1 — Input-Stack Teardown Sequencing

The Settings request path was changed to an engine-owned primitive-only handoff:

1. capture the current runtime generation and exact pointer-width
   `DisplayManager` identity;
2. coalesce duplicate requests;
3. queue a zero-delay process-lifetime callback so the emitting Qt input/signal
   frame returns before teardown begins;
4. revalidate terminal state, dialog/recreation state, runtime generation, and
   exact manager identity;
5. admit the existing fail-closed Settings teardown/reconstruction path only
   when every identity still matches.

No dialog, manager, display, widget, shell, pixmap, or bound retiring-runtime
method crosses that handoff.

Source validation then completed repeated Settings and CUSTOM/Edit recreation,
but a fresh frozen runtime still failed, proving that the sequencing repair was
necessary but not sufficient.

## Stage 2 — Diagnostic Localization Of The Frozen Retainer

The Diagnostic Runtime preserved the ordinary runtime/Settings/Edit paths while
adding bounded failure-only ownership tracing after a destruction timeout.
This produced decisive evidence:

- Settings teardown reached `qobjects={}`, `resources=[]`, `thread_work=[]`, and
  `global_subscriptions=[]` while retaining exactly two `WidgetManager` Python
  owners.
- Each surviving `WidgetManager` had direct referrers of type
  `builtins.compiled_method` for `_handle_settings_changed` and
  `_on_compositor_ready`.
- The authoritative display cleanup already called `WidgetManager.cleanup()`
  and cleared `DisplayWidget._widget_manager`; that former forward edge was not
  the remaining owner.
- The compiled-only referrer type directly explained why ordinary script-mode
  ownership tests could pass while Nuitka/PySide builds failed.

The relevant signal code had connected and disconnected freshly materialized
bound method objects, for example conceptually:

```python
signal.connect(self._on_compositor_ready)
...
signal.disconnect(self._on_compositor_ready)
```

That relies on the signal layer treating two separately materialized bound
methods as the same connection identity. Ordinary Python/PySide behavior can
make that appear safe; the frozen diagnostic evidence showed retained Nuitka
`compiled_method` wrappers still strongly owning the manager.

## WidgetManager Correction

Lifecycle-sensitive manager signal connections were changed to stable callback
objects that do not strongly own the manager:

- one exact callback object is created and retained for each connection;
- the callback reaches the manager through `weakref` rather than a bound-method
  strong reference;
- disconnect uses the exact same callable object that was originally connected;
- terminal cleanup clears the stored callback handles after disconnect.

This changes the ownership graph from:

```text
Qt/PySide signal
    -> compiled bound method
    -> WidgetManager
```

to:

```text
Qt/PySide signal
    -> stable forwarding callable
    -> weakref(WidgetManager)
```

Even if the Qt/PySide layer retains the forwarding callable beyond QObject
retirement, it can no longer keep the retired manager alive.

A fresh compiled Diagnostic Runtime then opened and returned from Settings
successfully, proving the frozen Settings ownership path was repaired rather
than hidden by a timeout or GC workaround.

## Stage 3 — CUSTOM/Edit Exposed The Same Defect

After Settings was fixed, committed CUSTOM/Edit still failed on Save & Continue.
The lifecycle barrier again proved that teardown itself was healthy:

- all watched QObjects were destroyed;
- `PixelShiftManager` owners released;
- resources, thread work, and global subscriptions reached zero;
- only two `CustomLayoutManager` Python owners remained.

Direct referrer capture identified the retained methods as the eleven shell
signal handlers:

- `_on_shell_geometry_live_changed`
- `_on_shell_drag_finished`
- `_on_shell_resize_wheel_requested`
- `_on_shell_resize_drag_started`
- `_on_shell_resize_drag_live_changed`
- `_on_shell_resize_drag_finished`
- `_on_shell_reset_size_requested`
- `_on_shell_reset_position_requested`
- `_on_shell_reset_visualizer_requested`
- `_on_shell_remove_requested`
- `_on_shell_context_menu_requested`

Every captured referrer was again `builtins.compiled_method` with the manager as
its bound `self`.

The referrer count also matched the live shell topology exactly. One display had
two edit shells and reported 22 direct compiled-method referrers:

```text
2 shells x 11 signal handlers = 22 retained compiled methods
```

The second display had nine shells; diagnostic capture hit its bounded referrer
cap before enumerating the expected larger set. This exact correspondence tied
the failure to shell signal ownership rather than generic Qt deletion delay.

## CustomLayoutManager Correction

The eleven direct shell-to-manager bound-method connections were replaced with
stable weak forwarding callbacks. The shell retains the exact callback handles
used for its signal connections so retirement can disconnect the identical
objects deterministically. The callbacks themselves hold only a weak reference
to `CustomLayoutManager`.

The resulting contract is:

```text
EditShellWidget signal
    -> stable forwarding callable
    -> weakref(CustomLayoutManager)
```

instead of:

```text
EditShellWidget signal
    -> compiled bound method
    -> CustomLayoutManager
```

`EditShellWidget.retire_session()` remains authoritative for releasing its
session-local callbacks, resolver/applier closures, pointer state, snapshots,
and signals. The manager-side weak connection contract is an additional
ownership guarantee, not a substitute for shell retirement.

A fresh compiled Diagnostic Runtime then completed committed Edit/Save &
Continue successfully. The destruction barrier no longer retained
`CustomLayoutManager`, and runtime reconstruction continued normally.

## Why This Is Not A Bandaid

The correction does not:

- add `gc.collect()`;
- extend the 8-second barrier timeout;
- ignore `WidgetManager` or `CustomLayoutManager` owners;
- add sleeps or nested event pumping;
- special-case the barrier for Nuitka;
- suppress a failed teardown and continue anyway.

It removes the strong ownership edge that the diagnostic runtime directly
identified. Exact callable identity also makes connect/disconnect semantics
explicit instead of depending on bound-method equivalence across the
Python/PySide/Nuitka boundary.

## Validation

The final compiled Diagnostic Runtime validated both branches of the incident:

- runtime Settings opens, closes, clears the retired runtime barrier, rebuilds,
  reaches a fresh authoritative frame, and continues running;
- committed CUSTOM/Edit Save & Continue clears the retired manager barrier,
  rebuilds, and continues running;
- no forced collection, ignored owners, timeout extension, or weakened
  lifecycle accounting is required.

Standard SCR and Media Center still require the ordinary Phase 5 rebuilt-artifact
smoke checks before release. Those are delivery/parity gates; the frozen
root-cause ownership defect itself is closed by the successful compiled
Diagnostic Runtime reproductions.

## Related Follow-Up, Not Part Of This Root Cause

The `CustomLayoutManager` audit found two shell geometry resolver/applier lambdas
that still strongly capture the manager. `EditShellWidget.retire_session()`
explicitly clears them and they did not appear in the surviving-referrer
capture, so they were not this incident's retainer. They should nevertheless be
weakified in later lifecycle hardening so a temporary shell has no strong path
back to its manager even if a future alternate teardown path forgets explicit
retirement.

Dead/legacy helper teardown code and broader `CustomLayoutManager` decomposition
also remain cleanup work, not reasons to broaden this repair.

## Evidence

- `logs/evidence_chest/08_08_94798add_main_settings3_custom_spectrum_23_05/`
- `logs/evidence_chest/08_08_e6f24ca5_main_settings3_perf_23_49/`
- `logs/evidence_chest/08_09_diagnostic_widgetmanager_timeout_02_38/`
- 2026-08-09 compiled Diagnostic Runtime Settings success after the
  `WidgetManager` weak-callback correction
- 2026-08-09 compiled Diagnostic Runtime Edit/Save & Continue success after the
  `CustomLayoutManager` weak shell-callback correction
- `engine/engine_handlers.py`
- `engine/runtime_destruction.py`
- `core/logging/ownership_trace.py`
- `rendering/display_cleanup.py`
- `rendering/widget_manager.py`
- `rendering/custom_layout_manager.py`
- `widgets/edit_shell_widget.py`
- `ui/settings_dialog.py`
- `tests/test_s_hotkey_workflow.py`
- `tests/test_settings_dialog.py`
- `tests/test_runtime_destruction.py`
- `tests/test_custom_layout_manager.py`

## Guardrails

Never destroy a Qt owner graph synchronously from an input, signal, paint,
timer, or callback frame owned by that graph. Return to a process-lifetime GUI
turn, carry primitive identity only, and reject stale/duplicate intent before
teardown.

For lifecycle-sensitive Qt/PySide signal connections whose receiver is a plain
Python runtime owner, do not rely on repeatedly materialized bound-method
identity across frozen builds. Use an explicitly owned stable callable, use the
same object for connect/disconnect, and ensure the callback does not strongly
retain an owner that must be provably dead before reconstruction.

Keep destruction barriers fail-closed. A surviving Python owner is evidence to
localize and remove the retaining edge, never permission to extend the timeout,
force GC, ignore the owner, or construct the replacement over the retired graph.

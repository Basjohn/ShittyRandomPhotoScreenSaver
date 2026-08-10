# R-59 — Frozen Settings/Edit Recreation Retained Compiled Bound Methods

Date: 2026-08-08  
Last updated: 2026-08-10  
Status: **SOLVED — compiled and ordinary runtime ownership path closed; no remaining Diagnostic/package incident gate**

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Failure Family

After the earlier input-stack sequencing correction, script/source recreation could pass
while fresh frozen builds still failed. The fail-closed destruction barrier showed two
sequential manifestations of the same compiled ownership defect:

1. Settings destroyed every watched QObject/resource/task/subscription but retained one `WidgetManager` per display.
2. After WidgetManager was fixed, committed Edit destroyed its Qt graph but retained one `CustomLayoutManager` per display.

The barrier was correct to fail; no timeout/GC/ignored-owner workaround was acceptable.

## Stage 1 — Later-Turn Admission

Runtime Settings/Edit requests carry primitive runtime generation and exact pointer-width
manager identity to a process-owned later GUI turn. The emitting Qt input/signal/action
frame returns before teardown can begin. The continuation captures no retiring manager,
display, shell, widget, pixmap or bound method and rejects stale/duplicate identity.

This sequencing correction was necessary but did not explain the remaining frozen-only
owner retention.

## Diagnostic Localization

The dedicated Diagnostic Runtime added bounded failure-only direct-referrer capture
after fail-closed timeout was already committed.

For Settings, each surviving `WidgetManager` was directly retained by
`builtins.compiled_method` wrappers for lifetime-critical callbacks such as
`_handle_settings_changed` and `_on_compositor_ready`.

For committed Edit, each surviving `CustomLayoutManager` was retained by compiled bound
wrappers for the eleven `EditShellWidget` signal handlers. Referrer counts matched shell
topology (for example two shells × eleven handlers = twenty-two direct method refs).

This explained why normal Python/PySide source tests could pass while Nuitka/PySide
frozen ownership failed.

## Root Cause

Lifecycle-sensitive signal connections relied on repeatedly materialized bound method
objects for connect/disconnect:

```python
signal.connect(self._handler)
...
signal.disconnect(self._handler)
```

The frozen runtime demonstrated that compiled bound-method wrappers could remain strongly
owned by the Qt/PySide signal layer and therefore keep the plain-Python manager alive.
QObject destruction/disconnect was not sufficient proof of Python-owner release.

## WidgetManager Correction

Each lifecycle-sensitive connection now owns one stable forwarding callable. The
forwarder holds only `weakref(manager)`, and disconnect uses the exact stored callable.

```text
Qt/PySide signal
 -> stable forwarding callable
 -> weakref(WidgetManager)
```

rather than:

```text
Qt/PySide signal
 -> compiled bound method
 -> WidgetManager
```

Compiled Diagnostic Settings then cleared its destruction barrier and rebuilt normally.

## CustomLayoutManager Correction

The eleven direct shell→manager bound connections were replaced by stable weak forwarding
callbacks stored with the shell for exact disconnect. `EditShellWidget.retire_session()`
remains authoritative for session-local signal/callback/resolver/pointer/snapshot cleanup;
the weak connection contract prevents retained Qt wrappers from owning the manager even
if they outlive expected shell teardown.

Compiled Diagnostic Edit/Save & Continue then cleared the manager barrier and rebuilt
normally.

## Why The Fix Is Architectural

It does not:

- call `gc.collect()`;
- extend the destruction timeout;
- ignore manager owners;
- add sleeps/nested event pumping;
- special-case a passing barrier for frozen builds;
- suppress a failed teardown and continue.

It removes the exact strong owner edges named by the frozen direct-referrer evidence and
makes connect/disconnect callable identity explicit.

## Final Validation And Closure

- compiled Diagnostic runtime Settings passes;
- compiled Diagnostic committed CUSTOM/Edit passes;
- `08_09_ca830d7_14_59` subsequently completes four Settings retirements and one committed Edit retirement without the former manager-owner timeout;
- ordinary current-main lifecycle continues rendering after recreation;
- no forced collection, ignored owner or timeout extension is required.

The user has declared the Settings/Edit/Diagnostic build issue fully solved. Standard/
Media Center packaging is therefore no longer an incident-validation item in
`Current_Plan.md`; any future package smoke is ordinary release delivery work, not R-59
root-cause debt.

## Follow-Up That Is Not R-59

Two shell live-geometry resolver/applier lambdas may still be weakified as lifecycle
hardening because explicit `retire_session()` currently clears them. They did not appear
in the failing referrer capture and do not keep this incident open. Broader
`CustomLayoutManager` decomposition/dead-helper cleanup is likewise separate cleanup.

## Evidence

- `logs/evidence_chest/08_09_diagnostic_widgetmanager_timeout_02_38/`
- compiled Diagnostic Settings success after WidgetManager stable weak callbacks
- compiled Diagnostic Edit success after CustomLayoutManager stable weak callbacks
- `logs/evidence_chest/08_09_ca830d7_14_59/`
- `engine/runtime_destruction.py`
- `rendering/widget_manager.py`
- `rendering/custom_layout_manager.py`
- `widgets/edit_shell_widget.py`
- focused Settings/custom-layout/destruction regressions

## Guardrails

Never destroy a Qt owner graph synchronously from an input/signal/paint/timer/callback
frame owned by that graph. For lifecycle-sensitive Qt→plain-Python callbacks, use an
explicit stable callable ownership contract, exact callable identity for disconnect, and
no strong path that can keep an owner alive past the barrier. A surviving Python owner
is evidence to localize, never permission to weaken the fail-closed barrier.

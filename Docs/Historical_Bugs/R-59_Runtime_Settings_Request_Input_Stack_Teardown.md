# R-59 — Runtime Settings Request Tore Down The Emitting Qt Input Stack

Date: 2026-08-08
Last updated: 2026-08-09
Status: Current source validated; installed standard artifact proven stale and awaiting rebuild validation

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

Opening Settings through the standalone `--s` route worked, while requesting
Settings from a running packaged screensaver or Media Center build terminated
the application. The runtime key/signal route synchronously entered full
display teardown from the same Qt input/signal call stack that belonged to a
display object being retired. Script runs could appear to tolerate that native
ownership sequence; frozen PySide builds did not reliably do so.

## Correction

The display request now enters a primitive-only engine-owned handoff:

1. capture the current runtime generation and exact pointer-width
   `DisplayManager` identity;
2. coalesce duplicate requests;
3. queue a zero-delay process-lifetime callback so the emitting input/signal
   frame returns before teardown begins;
4. revalidate terminal state, dialog/recreation state, runtime generation, and
   exact manager identity;
5. admit the existing fail-closed Settings teardown/reconstruction path only
   when every identity still matches.

No dialog, manager, display, widget, shell, pixmap, or bound retiring-runtime
method crosses the handoff.

## Live Source Result

Commit `94798add` completed three consecutive runtime Settings cycles in the
`23:02:19–23:05:20` source run. Every request was queued once and admitted once,
the runtime and dialog barriers completed, replacement construction reached a
fresh authoritative first frame, rendering continued, and the process exited
with code 0. No traceback, invalid-wrapper access, GL failure, or lifecycle
timeout occurred.

The same run exposed a separate nonfatal diagnostic defect: `showEvent`
scheduled a bound method through a helper that attached lifecycle metadata
directly to the bound-method object. The helper now wraps all callbacks in an
owned plain function in `1621e564`, and a focused regression proves the owner/generation
metadata and callback invocation. That defect did not cause the three runtime
cycles to fail, but it must be absent from the next capture.

The later canonical `e6f24ca5` `23:44:52–23:49:13` main run confirms that
follow-up. It completed two more Settings replacements plus one CUSTOM/Edit
replacement, continued transitions/visualizer delivery, and exited with code
0. The bound-method metadata exception is absent, as are lifecycle timeouts,
invalid-wrapper access, tracebacks, and native/critical Qt messages.

## Installed Artifact Drift

The currently installed standard `C:\Windows\System32\SRPSS.scr` is
`62,540,800` bytes with timestamp `2026-08-08 21:53:56`. It predates both the
later-turn Settings admission fix (`94798add`) and the bound-callback wrapper
fix (`1621e564`). The standard release SCR is also stale: its `23:23:29`
timestamp precedes `1621e564` by roughly eleven seconds. An installer built
afterward therefore still packages the stale SCR; rebuilding the installer
alone cannot validate or repair this failure.

This is direct evidence that the reported installed standard crash is not a
failure of the current source path. The installed binary still owns the exact
synchronous teardown shape this record prohibits. It must be rebuilt from
current source before another source change is considered.

## Remaining Validation

- Rebuild the standard SCR from current source, then rebuild/reinstall its
  installer and open/close Settings while the runtime is active.
- Keep Media Center to a minimal shared packaged-route parity smoke check. It
  never receives an independent capture, baseline, golden, matrix, or soak.
- Require one queued/admitted request, clean runtime and dialog barriers, one
  replacement, fresh first-frame reveal, continued rendering, and no native
  termination or bound-method metadata exception.

Until those package-only checks pass, this record remains awaiting validation;
the source-run evidence closes the shared runtime sequencing question but does
not claim frozen-binary closure.

## Evidence

- `logs/evidence_chest/08_08_94798add_main_settings3_custom_spectrum_23_05/`
- `logs/evidence_chest/08_08_e6f24ca5_main_settings3_perf_23_49/`
- `engine/engine_handlers.py`
- `ui/settings_dialog.py`
- `tests/test_s_hotkey_workflow.py`
- `tests/test_settings_dialog.py`

## Guardrail

Never destroy a Qt owner graph synchronously from an input, signal, paint,
timer, or callback frame owned by that graph. Return to a process-lifetime GUI
turn, carry primitive identity only, reject stale/duplicate intent, and keep the
existing fail-closed destruction and first-frame barriers intact.

# R-79 — 2026-09-12 — Quick Display Sleep/Wake Topology Authority Split Could Leave A Window Straddling Displays

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Evidence

The overnight diagnostic run began at `05:43:59` while Qt exposed one screen. Startup logged `Monitor detection enabled (1 screens)` and built one Quick display generation. No `screenAdded`, `screenRemoved`, `Monitor topology reconciled`, or later `QUICK_GEOMETRY` event appears before the logs stop at `09:16:28`. The operator did **not** kill the process then: it remained present until a forced close at `13:47`, when the visible Quick surface was stuck across two displays. Both displays had remained powered off during the unattended period. Therefore the logs do not prove a second display returned before 13:47, and 09:16 must not be described as the shutdown time.

## Root cause / current architectural gap

`QuickDisplayWindow` already subscribed to bound-`QScreen` geometry/DPI changes and could resize/re-anchor its own live native window. `DisplayManager`, however, treated only `QGuiApplication.screenAdded` / `screenRemoved` as whole-topology evidence. A sleep/wake or display-power transition can retain a `QScreen` wrapper while its geometry/virtual-desktop facts change, or resume to the same final Qt signature after Windows displaced the borderless native window. That allowed local window mutation/recovery to exist without the manager-level generation/topology authority seeing the same event.

## Fix

- `DisplayManager` subscribes to current Qt `QScreen` geometry/available/virtual-geometry/DPI edges, `primaryScreenChanged`, and the `applicationStateChanged -> ApplicationActive` resume edge.
- All events enter the existing 250 ms one-shot topology reconciler; there is no recurring poller and no restored Win32 `WM_DISPLAYCHANGE` path. Resume-revalidation intent is latched independently of the first scheduling reason, so a metric edge followed by `ApplicationActive` in the same coalesced burst cannot lose the same-signature repair.
- A changed signature emits the existing `monitors_changed` path and therefore uses the existing full generation teardown/rebuild authority.
- An application-state/resume edge with an unchanged final signature performs one bounded reapplication of each live Quick window's existing bound-screen geometry plus retained-content re-anchor. It does not rebind the window or create a second topology owner.
- Manager retirement disconnects the new signal set and stale queued callbacks are fenced.

## Regression coverage

`tests/test_qtquick_monitor_wake_reconcile.py` pins same-count metric-change reconciliation, same-signature resume geometry repair, metric-first/resume-second intent preservation, inactive-state no-op, primary-screen signature visibility, burst coalescing and retirement disconnect/fencing. `tests/test_qtquick_window.py` pins the public bound-screen revalidation seam. Physical dual-display sleep/wake remains required because Qt/native resume ordering cannot be proved by a synthetic unit test.

## Closure bar

Run the focused Windows/PySide suites and one installed dual-display off/sleep -> wake soak. The incident closes only if every admitted display returns to one correctly bound full-screen Quick surface with no straddled/stale geometry and no duplicate owner/rebuild loop.

# Qt / QML Observability Contract

Last updated: 2026-08-30

## Purpose

SRPSS has more than one diagnostic plane. Python logging alone is not sufficient evidence for a Qt Quick application.

Qt/QML binding failures, component warnings, signal/slot complaints, scene-graph diagnostics and other Qt messages travel through Qt's own message-handler path. During the Quick migration this blind spot hid a real Clock retirement failure even while the Python logs looked clean.

The capture is now **permanent always-on product infrastructure**.

## Diagnostic planes

| Plane | Primary artifact | Scope |
| --- | --- | --- |
| Python/runtime | `screensaver.log` + enabled family sidecars | Python owners, runtime sequence, provider/service/perf/lifecycle telemetry |
| Qt/QML | `screensaver_qml.log` | Qt message handler, QML bindings/components, Qt signal/slot/scene diagnostics |
| Diagnostic fatal | `diagnostic_crash.log` | Diagnostic-build `faulthandler` + uncaught Python/fatal breadcrumbs |
| Raw non-Qt stderr | console / process stderr | Native/library writes that bypass both Python logging and Qt message handler |

Do not silently treat these as interchangeable.

## Always-on Qt/QML capture

Implementation: `core/logging/qt_message_capture.py`.

Required lifecycle:

```text
ordinary logging path resolved
-> install Qt message capture
-> configure Quick graphics
-> create QApplication
-> create QQmlEngine / QQuickWindows
-> run application
-> retire all Quick/QML objects
-> return from main / destroy QApplication
-> atexit closes Qt capture
```

The handler must be installed **before `QApplication` and any `QQmlEngine` are created** and remain active through final Qt destruction.

## Sidecar existence is itself evidence

A successful install must eagerly create `screensaver_qml.log` and write a `session_start` marker.

This removes the former ambiguity caused by `RotatingFileHandler(delay=True)`:

```text
old clean run:
main log says capture active
+ Qt emits zero messages
+ sidecar file never opens
=> missing file could mean either "clean" or "capture unavailable"
```

New contract:

```text
file exists + session_start + zero messages
=> capture was alive and Qt/QML plane was clean

file does not exist
=> capture/setup/path/packaging problem; do not claim Qt/QML evidence

file exists + messages
=> inspect and classify every migration-relevant warning/error
```

The 2026-08-30 17:37–17:40 physical source-mode sidecar is a concrete clean example: `session_start` and `session_end` are present, with `messages=0`, empty category/level maps and `write_errors=0`. An almost-empty file is therefore a successful clean capture, not missing evidence.

## Record schema

Each Qt/QML message preserves, when available:

```text
timestamp with milliseconds
severity
process id
thread name + Python thread id
monotonic sidecar sequence
Qt category
source file + line + function
message payload
```

The sidecar also writes session markers and final counts by severity/category.

The exact human format may evolve. Do not remove those fields without replacing their diagnostic value.

## Persistence / failure behavior

The Qt/QML sidecar is deliberately direct and synchronous rather than routed through the ordinary queued logger.

Reasons:

- QML/Qt errors can occur while the ordinary logging queue is saturated or closing;
- Qt fatal/error evidence may be immediately followed by native termination;
- message-handler recursion must remain bounded and simple.

The file is rotated and size-bounded. It must not become a frame telemetry stream.

A Qt message callback may **never raise into Qt**.

## Console / previous-handler preservation

Installing SRPSS capture must not silently steal another Qt handler.

If a pre-existing Qt message handler exists, capture first and then delegate to it. If Qt had no custom handler, preserve useful script/debug console behavior by echoing a compact equivalent to the original stderr route.

Uninstall must restore the prior handler rather than blindly installing `None`.

## Runtime gate rule

For any H/J source-mode or installed physical claim involving Quick/QML:

1. read `screensaver.log` for the main runtime sequence;
2. read `screensaver_qml.log` for Qt/QML evidence over the same timestamp range;
3. follow owning family sidecars when needed;
4. do not call the gate GREEN while unexplained migration-relevant Qt/QML warnings/errors remain.

This does **not** mean every third-party informational Qt line is automatically a product failure. It means the diagnostic plane must be intentionally classified rather than ignored.

## Examples of first-class Qt/QML evidence

- `Cannot read property ... of null` during retained model teardown;
- `QML Image: Failed to get image from provider: image://mediaartwork/...`;
- required property/component creation errors;
- invalid signal/slot connection diagnostics;
- shader/component load failures;
- scene-graph warnings tied to the current runtime transition.

These messages may identify an H functional/lifecycle seam even when Python owners report normal completion.

## Correlation

Use timestamp + source/category + main-log runtime generation/activity to correlate Qt/QML records.

Do not add per-frame generation queries inside the Qt message handler merely to decorate logs. The capture path must remain passive and cheap.

If future investigations repeatedly need exact runtime-generation identity inside Qt/QML messages, add one process-owned, read-only correlation provider with a focused performance/lifetime review rather than coupling the handler to display owners.

## Raw stderr / `os.dup2` decision

Current production capture does **not** install an OS-level stderr tee.

That boundary is intentional. A true fd-2 tee is materially different from `qInstallMessageHandler`:

- native/C libraries can write to fd 2 without Qt;
- redirecting fd 2 changes subprocess/standard-handle inheritance;
- a background pipe-based tee can lose the final bytes if the process dies before the reader drains;
- direct fd-to-file redirection is more crash-resilient but sacrifices normal console parity unless another route mirrors it;
- frozen Windows behavior must be tested separately from script mode.

Therefore add permanent fd-2 capture only after a demonstrated non-Qt stderr gap and with an explicit design answering:

```text
console preservation?
subprocess inheritance?
rotation/bounds?
hard-crash persistence?
shutdown order?
frozen/script differences?
```

Do not use `os.dup2` merely because it sounds more comprehensive.

## Tests

Permanent coverage should prove:

- successful install eagerly creates the sidecar;
- clean session writes start/end markers with zero-message summary;
- warning/error callback records category + source context;
- previous Qt message handler is delegated/restored;
- log-dir relocation does not install a second Qt callback;
- sidecar metrics count messages/severities/categories;
- callback exceptions never escape into Qt;
- capture remains independent of ordinary logger queue state;
- a real `QQmlEngine` warning reaches the sidecar through Qt's actual message-handler path (`tests/test_qt_message_capture_qml_runtime.py`).

The fake-handler contract tests are GREEN in the handoff environment. The real-QML probe requires PySide6 and is **AWAITING TEST VALIDATION** in the Windows/runtime environment. Physical/frozen acceptance still matters because even a real local `QQmlEngine` probe cannot prove every scene-graph/driver path.

## Native presentation-mode diagnosis (PresentMon / ETW) — ephemeral only

Some defects live *below* the retained Quick scene: the scene, image identity,
scene-graph state and frame swaps stay healthy while the native/DWM presentation
misbehaves (e.g. R-63, the Display-1 black flash from fullscreen-flip PresentMode
transitions). `[QUICK_SURFACE]` telemetry proves the scene is exonerated but
cannot see the present path. Diagnose that with PresentMon **ephemerally, outside
the repository** — do not add a presentation-mode logger, tool, or env var to the
product.

Reusable method (installed at `C:\tools\PresentMon\PresentMon.exe`):

```text
capture-all (works unelevated):
  PresentMon.exe --timed N --qpc_time --output_file f.csv --stop_existing_session --no_console_stats
  -> per present: Application, ProcessID, PresentMode, AllowsTearing, TimeInQPC
  -> unelevated caveat: SwapChainAddress reports 0x0 (cannot split multiple windows apart)

correlate with a composed-desktop detector:
  dxcam (DXGI Desktop Duplication) captures the actual composed output of one monitor;
  classify near-black and stale (old-frame-resurface) frames; timestamp each via
  QueryPerformanceCounter (same QPC clock as PresentMon --qpc_time).
  For each detected frame, inspect PresentMode within +/-250 ms: did it transition
  (e.g. "Composed: Copy with GPU GDI" <-> "Hardware: Legacy Flip"), or stay stable?

drive interaction without exiting the screensaver:
  Win32 SetForegroundWindow (+ AttachThreadInput) changes activation with NO cursor
  motion, so the mouse-move exit gesture never fires. Never automate real mouse moves.

interpretation:
  run >=3 launches per condition — launch-to-launch present behavior is variable.
  flash AT a PresentMode transition -> the transition/promotion is the seam (fix by
    keeping the window in a stable mode, e.g. the 1px overscan of R-63);
  flash while PresentMode stays stable -> the transition is NOT the cause; look elsewhere.
```

Do not treat tearing as proof of presentation mode; prove it from the PresentMon
`PresentMode` column. Independent/hardware flip is an optimization, not a
correctness requirement — the product must stay correct under ordinary composition.

## Native Media event observation (GSMTC / WinRT) — durable facts

The shared Media runtime (`_SharedMediaRuntimeOwner` + `WindowsGlobalMediaController`)
is event-driven rather than polled: native GSMTC dirty edges feed the existing
accepted-snapshot pipeline, with one ~30s reconcile/liveness watchdog. Facts
proven on the installed projection (re-verify with an ephemeral harness — never
commit a polling harness, and never add a Media diagnostic env var to the
product):

```text
package: pywinrt `winrt` (snake_case projection); event token = EventRegistrationToken
Manager (GlobalSystemMediaTransportControlsSessionManager, retained after request_async):
  add/remove_current_session_changed, add/remove_sessions_changed
Session (GlobalSystemMediaTransportControlsSession, the observed session retained):
  add/remove_playback_info_changed, add/remove_media_properties_changed,
  add/remove_timeline_properties_changed
remove_*(token) cleanly stops delivery.
callbacks arrive on a NON-main WinRT thread-pool thread ("Dummy-N") -> hop to the UI
  thread (ThreadManager.run_on_ui_thread) and coalesce; never query/await/decode or
  touch Qt from the callback.
the manager AND the observed session must be RETAINED or their subscriptions die
  (the retired poll path requested a fresh manager per query and discarded it).
steady Spotify playback: timeline_properties_changed ~0.24 Hz; zero playback/
  media-properties events while unchanged; zero events when paused/idle.
```

Coalescing contract: at most one refresh in flight + one pending dirty edge
(unified with command confirmation; command wins). A timeline coalescing floor
bounds a chatty provider without a recurring cadence. Observation failure logs a
loud `[MEDIA_EVENT][DEGRADED]` and relies on the watchdog — the old 1–2.5s active
poll is never reactivated. The watchdog logs `[MEDIA_EVENT][MISSED_EVENT]` when it
finds a non-position change no native event delivered. Progress position is not
interpolated locally, so timeline edges (~4s for Spotify) are the progress-bar
freshness source — acceptable and comparable to the retired ~2.5s poll.

## Guardrails

- always-on does not mean high-volume;
- no per-frame QML debug chatter;
- no control flow driven by whether logging succeeded;
- no swallowing fatal/error evidence to keep a test green;
- no duplicated Quick owner just to expose diagnostics;
- no migration gate based solely on the console;
- no raw stderr redirection without an explicit subprocess/crash design.

# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-30 after source-mode run at `1849f2a44154132d6df45e327165b1cd79103bfa` and direct source/log reconciliation.

## Current checkpoint

G remains accepted. The H production-authority cutover and caller-proven deletion of the old physical host remain accepted architecture. **H is still OPEN. I is NOT admitted.**

H1 is now closed and H2 is now closed:

```text
H1a  repeated dual-display Settings/CUSTOM recreation hang     CLOSED
H1b  terminal Quick retirement / Clock model lifetime          CLOSED
H2   Media artwork provider identity                            CLOSED
H3   Reddit retained URL opener                                 CURRENT
H3b  Clock runtime mode-toggle persistence                      PENDING
H4   Media Play/Pause + seek command semantics                  PENDING
H5a  CUSTOM Visualizer independent display admission            PENDING
H5b  Spectrum data saturation + wrong topology                  PENDING
H6   CUSTOM Settings size-lock scope                            PENDING
H7   Exit visible-response/perf classification                  PENDING / likely J after measurement
```

The maintained H destination profile must remain GREEN after each bounded source change. H is not closed by unit tests alone: every H/H-J row in the operator ledger must be reconciled and the final dual-display source-mode smoke must remain physically clean.

Detailed evidence: `Docs/QtQuick_Migration/H_Post_Cutover_Runtime_Reality_Corrections.md`  
Operator backlog: `Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`

## Permanent Qt/QML observability baseline

Qt/QML has a diagnostic plane separate from Python logging. `core/logging/qt_message_capture.py` is therefore permanent always-on infrastructure, not temporary H instrumentation.

Normal source/runtime acceptance now reads **both**:

```text
screensaver.log       Python/runtime narrative + WARNING+
screensaver_qml.log   direct Qt/QML message-handler evidence
```

The Qt/QML capture must be installed before `QApplication` / `QQmlEngine` creation and remain active through final Qt teardown. A clean run still creates `screensaver_qml.log` and records capture session markers; the previous `delay=True` behavior, where a clean run produced no file at all, is retired because “file missing” was ambiguous with “capture failed.”

The sidecar records timestamp, severity, PID, thread identity, Qt category, source file/line/function when available, sequence, and message. It is direct/synchronous and independently rotated so Qt/QML failures are not dependent on the ordinary asynchronous log queue.

Unexpected Qt/QML warnings/errors that correlate with the current migration surface are first-class evidence. Do not call a physical H/J gate GREEN merely because `screensaver.log` is clean.

This is **not** an OS-level fd-2 tee. Raw non-Qt native stderr remains a separate diagnostic plane. Do not add `os.dup2` redirection casually: a true tee changes crash persistence, subprocess inheritance and shutdown semantics. See `Docs/Qt_QML_Observability.md`.

## Production architecture — binding

```text
selected physical display
-> DisplayManager semantic orchestration
-> one QuickDisplayUnit
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> one display-owned WidgetRuntimeManager
-> canonical capability + per-instance monitor admission
-> retained ordinary/CUSTOM/input/context/auxiliary/transition owners
-> zero-or-one admitted visualizer edge per display
-> exactly one product-level visualizer owner across participating displays
```

Do not restore `DisplayWidget`, QRhiWidget/GLCompositor presentation, `QQuickWidget`, a QWidget compatibility facade, a hidden QWidget presenter, a second accelerated surface, a second visualizer owner/pacer, or a software/QRhi fallback.

Other binding invariants:

- Python owns semantic/settings/provider/runtime truth; QML consumes bounded presentation state and emits semantic actions.
- `QuickSceneController` owns Quick item creation/retirement.
- One `WidgetRuntimeManager` per display generation.
- No duplicate provider/service manager, BeatEngine/source owner, logical visualizer runtime, mailbox/bridge, CUSTOM owner or cadence owner.
- Old-generation admission closes and authored/logical work joins before scene/window retirement; generation `0` is valid.
- Fallbacks are product-authorized, destination-owned and fail-loud.
- QML reports preferred content size only; Python owns anchor + margin + clamp + x/y + final outer rect.
- CUSTOM committed geometry outranks family/default geometry.
- Outside CUSTOM, Visualizer effective position/monitor routing follows Media.
- In committed CUSTOM, Visualizer owns its own persisted monitor/geometry, may overlap and may live on another selected display from Media.
- Bubble authored cadence remains presentation-independent; the display Quick frame pacer is the sole GUI presentation opportunity.
- Bubble Temporal Fidelity remains binding. Do not reduce cadence or retune physics merely to hide a presentation problem.

## Closed H1 — preserve, do not reopen without regression evidence

### H1a reconstruction

`2220782d` changed ordinary-family assembly to build all admitted retained family QML first and activate successfully built families afterward. The operator then completed 3 Settings recreation cycles + 5 CUSTOM Save/Continue cycles in one dual-display process without a watchdog dump.

### H1b terminal retirement

Terminal shutdown now has a terminal-purpose destruction barrier, staged finalization, safe Settings helper event filters and retained-model lifetime long enough for QML item retirement. Later physical runs prove:

```text
application_exit barrier arms
-> Quick roots retire
-> barrier completes (~200–250 ms)
-> ThreadManager/process finalization
-> clean code=0 exit
```

No `BackgroundRenderItem::` slot error, Windows access violation, Clock null-model retirement storm or Settings event-filter exception remains in the accepted physical gate.

The former failure is historical evidence only; do not keep its old “required next work” in active plan text.

## Closed H2 — Media artwork provider identity

Current production `MediaFamilyAdapter` obtains the `MediaArtworkImageProvider` already registered on the scene factory's `QQmlEngine` via the host and injects that exact provider into `MediaPresentationModel`. The old private-per-card provider split is gone.

The operator's latest source-mode run physically confirms Media artwork now displays.

**Preserve as permanent cross-layer contract:** decoded artwork must publish into the exact engine-registered provider that resolves `image://mediaartwork/<identity>`.

Historical artwork fade/presentation quality is **not H2**. Artwork currently appears but lacks the nicer historical transition/fade; that is a named J Parity+ row.

## Active H work — execute in order

### H3 — retained Reddit URL click has no production opener

**Status: source-proven composition defect; CURRENT.**

`RetainedRedditPresentation` already owns URL admission and an `on_open_requested` seam. Production `RedditFamilyAdapter` still constructs it without that callback.

Reconnect the retained semantic action to the existing product-level secure URL authority. Preserve product distinction:

```text
MC / diagnostic interactive build -> direct desktop URL route
SCR                           -> existing secure helper/queue route + normal saver exit
```

Prefer the established `core.windows.secure_url_launcher` product authority rather than reproducing helper policy in QML/model/family code. Helper readiness must not block teardown.

Add a production-family composition regression: an admitted Reddit row reaches the product opener exactly once; rejected/untrusted/interaction-disabled actions do not.

### H3b — Clock runtime mode toggle must persist across recreation

**Status: source-proven persistence wiring defect.**

`RetainedClockPresentation` already accepts `on_mode_toggle`. Production `ClockFamilyAdapter` currently omits it, so runtime analog/digital toggle changes only the live model. Settings/Edit recreation rebuilds from the old persisted mode and appears to “revert” the user's toggle.

Wire the existing semantic callback to the current Settings authority without moving persistence into QML. Preserve per-display/per-clock mode semantics already defined by the Clock contract. Add a production composition + recreation persistence regression.

### H4 — Media Play/Pause and seek do not execute; Previous/Next do

**Status: operator-reproducible; generic retained-card input is not the first suspect.**

Trace the real command boundary:

```text
semantic request
-> worker submission
-> real WinRT method result / bool / exception
-> state reconciliation refresh
```

Do not treat queue submission as success. Do not block the GUI waiting for WinRT. Preserve Previous/Next, which already work through the same card.

Verify Spotify's actual toggle behavior and the seek units/result of `try_change_playback_position_async()`.

### H5a — CUSTOM Visualizer must remain independent of Media's display route

**Status: operator-reproducible functional regression against an existing contract.**

Non-CUSTOM Visualizer follows Media's effective monitor. CUSTOM Visualizer owns its own persisted monitor/geometry and may live on another selected display. `QuickDisplayUnit.is_visualizer_participant()` does not require Media on that display.

Trace once per generation:

```text
spotify_visualizer.position / monitor
media.monitor
custom decision
effective monitor
requested screen
participant set
CUSTOM failover state
chosen unit
construct result / reject reason
```

Do not redesign routing or re-couple Visualizer ownership to a same-screen Media card.

Technical route: `Docs/QtQuick_Migration/H5_Visualizer_Routing_And_Spectrum_Decomposition_2026-08-30.md`.

### H5b — Spectrum saturation + wrong functional presentation topology

**Status: operator-reproducible; two branches must be localized independently.**

Current evidence:

1. Spectrum authored/computed payload repeatedly saturates near/all `1.00` before shader presentation.
2. Physical Organ/Spectrum presentation is the wrong representation family: a dense full-height matrix of tiny segmented blocks instead of the intended bottom-aligned continuous frequency columns.

Saturation may explain pinned energy; it does not explain the topology substitution.

Trace:

```text
data: FFT/bands -> Spectrum shaping -> floor/gain/expansion/normalization -> clamp -> final vector
presentation: mode/preset -> render snapshot -> renderer -> primitive/topology -> retained draw
```

H stops when live Spectrum data is non-degenerate and the correct functional continuous-column representation survives switch/recreation. Exact spacing/glow/gradient/line-thickness polish belongs to J Parity+.

Do not alter Bubble/shared cadence while fixing Spectrum.

### H6 — CUSTOM Settings may lock only size-authoring controls

**Status: operator-reproducible Settings ownership defect.**

For Media, canonical CUSTOM size-lock metadata is only:

```text
media_font_size
media_artwork_size
```

CUSTOM itself must not disable progress/seek/glow/volume/mute feature controls. Normal feature/provider dependency gates still apply.

Find the secondary disable owner (parent container, stale second lock path, dependency refresh ordering, etc.) and remove only the CUSTOM-derived over-lock. Do not force-enable controls that are legitimately disabled by their own semantics.

Technical route: `Docs/QtQuick_Migration/H6_Custom_Settings_Lock_Scope_Decomposition_2026-08-30.md`.

### H7 — Exit visible-response/performance classification

The current clean run routes Exit immediately and completes the terminal Quick barrier in ~250 ms. Script-mode recursive `__pycache__` cleanup then consumes additional terminal time.

Remeasure **visible window dismissal** separately from legal retirement and developer housekeeping. If visible dismissal is prompt, carry remaining tail/pycache policy into J/performance or cleanup rather than reopening lifecycle ownership.

## H observations intentionally carried to J unless a deterministic seam appears

### Bubble response

Bubble remains physically weak/delayed despite healthy authored ~90 Hz cadence/integration. Do not tune sensitivity/physics during unrelated H work. J must correlate playback edge -> source freshness -> logical Bubble state -> retained publication -> visible consequence. Promote only a proven stale/delayed owner seam.

Preserve the currently good Bubble partial/CUSTOM resizing.

### Black/test-frame/focus/context flashes

Black flashes, apparent startup diagnostic/test colour bands, focus flicker and context-menu flash remain high-priority J physical presentation defects unless tracing proves an actual semantic reset/test frame is admitted.

## H re-closure gate

H closes only when:

1. H1 reconstruction + terminal-retirement regressions remain GREEN;
2. H2 artwork provider identity remains GREEN and real artwork remains visible;
3. Reddit URL actions reach the correct product opener;
4. Clock runtime mode toggle survives Settings/Edit recreation;
5. Media Play/Pause + seek work on the real provider while Previous/Next remain working;
6. CUSTOM Visualizer can own a different selected display from Media while non-CUSTOM still follows Media;
7. Spectrum has non-degenerate data and the correct functional continuous-column representation after switch/recreation;
8. CUSTOM Settings locks only size-authoring controls;
9. Exit visible response is measured/understood with clean natural termination;
10. unexpected `screensaver_qml.log` warnings/errors relevant to these paths are reconciled;
11. maintained `h-destination` is GREEN after the bounded fixes;
12. every unresolved ledger row whose phase includes H is closed or explicitly carried to J with evidence;
13. a short dual-display source-mode smoke is GREEN.

Only then may I start.

## I — blocked residue reconciliation

I remains source/test/tool residue cleanup only. Do not use it to absorb current runtime failures and do not restore legacy presentation to satisfy stale tests.

## J — Parity+ destination

J is **Parity+**: proven historical user-visible quality/behavior is the floor where it was better, not the ceiling. Preserve genuine Quick improvements and fix historical shortcomings rather than reproducing bugs.

Read together:

```text
Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md
Docs/QtQuick_Migration/J_Visual_Parity_Runtime_Acceptance_Addendum_2026-08-30.md
Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md
Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md
Docs/Qt_QML_Observability.md
```

Primary visual references are the 4.7.2/4.7.0 release screenshots. `15099d3` is the cleaner historical behavior-code reference; `3fe5df6` is a later mixed reference with migration work. Historical code is never implementation authority.

Named J cells include:

- startup/focus/context-menu/transition black flash and apparent test-colour-band flash;
- actual gentle reveal/fade;
- Media Parity+: proportions, artwork sizing/chrome, **artwork change fade**, header/control-strip balance, optional metadata;
- preserve the newer transport strip where it is better;
- adjacent/outside adjustable Media app-volume accessory as the canonical established toggle outcome;
- Gmail clipping/refresh/header alignment;
- Achievement Pulse packing/icon/count allocation;
- one coherent visible pointer treatment (no OS cursor + halo duplication);
- ordinary non-CUSTOM free-space composition, especially Media + Visualizer, without dog-piling;
- CUSTOM overlap/cross-display authority untouched by ordinary collision avoidance;
- coherent context-submenu hover-leave lifetime;
- all-five visualizer eyes-on fidelity after H restores Spectrum data/topology;
- Bubble visible response/latency without sacrificing BTF or its currently good partial resizing;
- mixed refresh/DPR, off/wake, A->B->A focus/topology, installed performance tails and clean exit;
- **Qt/QML sidecar review as part of physical acceptance**, not console-only inspection.

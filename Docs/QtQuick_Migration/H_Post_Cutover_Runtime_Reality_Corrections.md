# H Post-Cutover Runtime-Reality Corrections — Current Record

Date: 2026-08-30  
Latest physically reviewed source-mode run: `1849f2a44154132d6df45e327165b1cd79103bfa`

This is the durable evidence/decomposition companion to `Current_Plan.md`. It records what H runtime reality actually disproved or repaired after the Quick production cutover. It is not a second sequence authority.

## 1. Accepted architecture remains unchanged

```text
physical display
-> DisplayManager
-> QuickDisplayUnit
-> QuickDisplayRuntime
-> standalone threaded QQuickWindow
-> retained scene
-> per-display WidgetRuntimeManager
```

One product-level Visualizer owner exists across participating displays. The deleted QWidget/QRhi/GL physical presenter is not a fallback and historical code is never current implementation authority.

## 2. H1a — dual-display reconstruction hang CLOSED

### Failure evidence

Before the repair, both Settings and CUSTOM replacement could wedge while screen-1 retained family QML was being built. Watchdog captures put MainThread inside retained Gmail `QQmlComponent.createWithInitialProperties()` while an earlier Media family had already begun provider/artwork work on a worker thread.

The evidence invalidated the earlier assumption that the final Media native breadcrumb necessarily named the root cause.

### Repair

`OrdinaryFamilyPresentationBinder.bind()` was changed from interleaved:

```text
build A -> activate A -> build B -> activate B
```

to:

```text
build every admitted retained family
-> activate every successful family in the same stable order
```

Admission, monitor routing, geometry, owner count and retirement were not broadened.

### Physical close

One dual-display source process completed:

```text
3 Settings recreate cycles
5 CUSTOM Save/Continue recreate cycles
0 watchdog dumps
```

Keep the two-phase binder and its focused tests. Do not re-open old Gmail/Media construction theories without a new hang.

## 3. H1b — terminal Quick retirement + Clock model lifetime CLOSED

### Initial failure

Ordinary Exit used to show this shape:

```text
Exit accepted
-> displays quiesced/cleared
-> asynchronous Quick retirement begins
-> Python/process shutdown continues
-> normal code=0 exit logged
-> BackgroundRenderItem slot complaint
-> Windows access violation during GC
```

Retiring Clock QML also emitted a large null-model property storm. That was never a missing-font failure; many unrelated properties failed because the same `clockModel` reference became null while its QQuickItem was still alive.

### Root ownership gaps

Two separate lifecycle seams were repaired:

1. replacement already used a destruction barrier, while terminal `application_exit` did not wait for the same asynchronous Quick/QObject retirement;
2. a parentless Clock model could be dropped before deferred QML item deletion had completed.

Settings helper event filters also assumed `_widget` / `_host` still existed during late Qt teardown events.

### Repair shape

- terminal-purpose destruction barrier observes the same retired roots/resources but can never admit replacement;
- terminal stop is staged so final process/thread/Qt quit occurs after legal Quick retirement proof;
- retained parentless model lifetime is bound to its retained item where required;
- late Settings helper event filters tolerate an already-retired target.

No `processEvents()` loop, arbitrary sleep, forced `gc.collect()`, force-kill, leaked window or per-property QML null plaster was introduced.

### Physical close

Later dual-display runs show:

```text
application_exit barrier armed
-> barrier complete (~200–250 ms)
-> ThreadManager/process finalization
-> natural code=0 process exit
```

No fatal access violation, dangling `BackgroundRenderItem::` slot error, Clock null-model retirement storm or Settings event-filter exception remains in the accepted gate.

## 4. Permanent observability correction — Qt/QML is a separate diagnostic plane

H1b exposed a migration-process failure as important as the runtime bug: Python logs were not sufficient to see Qt/QML diagnostics.

`qInstallMessageHandler` capture is now permanent always-on infrastructure. Read:

`Docs/Qt_QML_Observability.md`

### Required runtime evidence

```text
screensaver.log       ordinary Python/runtime spine
screensaver_qml.log   direct Qt/QML diagnostic sidecar
```

The Qt/QML capture is installed before `QApplication` / `QQmlEngine` creation and remains alive through final Qt teardown.

The earlier implementation used `RotatingFileHandler(delay=True)`. A perfectly clean run could therefore produce **no sidecar file at all**, even though capture was installed. That implementation-level ambiguity is retired; do not infer it from a bundle when the sidecar is actually present.

The 2026-08-30 17:37–17:40 operator sidecar is the intended clean shape: it contains `session_start`, then `session_end` with `messages=0`, `categories={}`, `levels={}` and `write_errors=0`. A successful install now eagerly creates the sidecar and writes session markers, so clean and broken runs are distinguishable:

```text
file exists + session_start + 0 Qt messages  -> capture alive, clean Qt/QML plane
file missing                                 -> capture/setup/packaging problem
file exists + messages                       -> inspect/reconcile those messages
```

Capture records severity, PID, Python thread identity, Qt category, file/line/function where available, sequence and message, and writes a final session summary.

### OS-level stderr boundary

No permanent `os.dup2` fd-2 tee has been added. That is intentional.

A true process stderr tee is not “more of the same logging”: it changes standard-handle/subprocess inheritance and typically needs a reader/forwarder path; using a pipe can lose the tail on a hard process crash, while direct redirection sacrifices console parity. Add it only for a demonstrated non-Qt native stderr gap with an explicit crash/subprocess design. Diagnostic `faulthandler` remains a separate direct crash plane.

## 5. H2 — Media artwork provider identity CLOSED

### Former defect

Old production composition created two different artwork providers:

```text
QQmlEngine registered provider A
MediaPresentationModel published decoded QImage into provider B
QML resolved image://mediaartwork/... through A
```

Decode was real but pixels could never resolve.

### Current source

`QuickSceneFactory` owns/registers the process scene's `MediaArtworkImageProvider`.

`MediaFamilyAdapter.build()` now obtains that exact provider through the ordinary host's registered-image-provider seam and injects it into `MediaPresentationModel`. A missing engine provider fails the card closed instead of silently creating an unresolvable card.

### Physical close

The operator confirms Media artwork is visibly loading in the latest source-mode run.

Keep a permanent cross-layer regression for exact provider identity. The fact that artwork **appears** closes H2.

The nicer historical artwork change fade does not currently match the old presentation. That is a J Parity+ quality row, not a reason to reopen provider wiring.

## 6. H3 — Reddit production opener IMPLEMENTED / AWAITING TEST VALIDATION

The production composition omission was source-proven and has a bounded prepared repair in this replacement pack.

Current prepared route:

```text
RetainedRedditPresentation.on_open_requested
-> RedditFamilyAdapter
-> weak generation-fenced DisplayManager callback
-> core.windows.secure_url_launcher.open_url(...)
-> interactive MC/diagnostic: direct route, no saver exit
-> ordinary saver: secure handoff, then normal exit only on successful open/handoff
```

This keeps URL admission in the retained model/presentation and product opening policy at the existing product authority. It does not make QML aware of helper/task policy and it does not wait for helper readiness during teardown.

Pure product-action coverage in `tests/test_qtquick_family_product_actions.py` is GREEN in the handoff environment. Real PySide production-family composition plus MC/SCR Windows behavior are **AWAITING TEST VALIDATION** before H3 may be called closed.
## 7. Clock runtime mode + geometry variants — IMPLEMENTED / AWAITING TEST VALIDATION

The physical report was more specific than a missing mode-setting write: after recreation the Clock could keep the requested analogue/digital **mode** but fall back to the wrong outer geometry. Source audit found several parts of the same R-45/R-48 contract had been split during the Quick migration:

1. production composition omitted the retained Clock's semantic mode-toggle persistence callback;
2. pre-bind CUSTOM hydration selected the Clock geometry variant from shared `display_mode` instead of the effective per-display override;
3. the live Clock changed its retained item rect directly while the display-owned `OverlayGeometryBinding` still held the previous committed rect, so a later preferred-size publication could replay stale geometry;
4. the retained variant store remembered only rects, was not seeded with both committed analogue/digital variants, and therefore could lose each variant's independent CUSTOM `font_size`;
5. a partially-authored layout with only the opposite Clock variant had no deterministic target-mode replay path.

The prepared repair keeps the existing ownership model:

```text
Clock double-click semantic action
-> RetainedClockPresentation switches mode
-> mode-specific retained variant state (rect + font_size)
-> display-owned OverlayGeometryBinding receives the new committed rect
-> weak generation-fenced DisplayManager product callback
-> display_mode_overrides[screen_signature]
-> when position=Custom and no edit transaction is active:
   canonical custom_layout[screen][clock][analog|digital]
      rect + font_size only; never display_mode
```

At admission, both committed Clock variants are now seeded into the retained variant store. The effective per-display mode selects the active variant. If the requested variant is missing but the opposite CUSTOM variant exists, hydration deterministically derives the target shape around the saved centre using the saved font scale; it does not mutate Settings during hydration. A later live toggle/save can canonicalize that variant through the normal Python persistence owner.

The shared `display_mode` remains the authored baseline, QML owns no settings or geometry persistence, and an active CUSTOM edit transaction is never bypassed by a behind-the-session geometry write.

Deterministic coverage now includes `tests/test_qtquick_family_product_actions.py` plus `tests/test_qtquick_clock_custom_variant_geometry.py`. The pure product-action tests are GREEN in the handoff environment; the PySide Clock geometry/composition tests and physical Settings/CUSTOM recreation are **AWAITING TEST VALIDATION**.

## 8. H4 — Media Play/Pause and seek

Previous/Next work through the same retained card, so generic card input is not the first suspect.

Instrument real provider command outcome:

```text
request
-> submitted
-> WinRT result / bool / exception
-> refresh/reconciliation
```

Queue submission is not success. Do not block GUI waiting for WinRT.

## 9. H5a — CUSTOM Visualizer independent monitor

Current source already defines:

```text
non-CUSTOM Visualizer -> effective route from Media
CUSTOM Visualizer     -> own spotify_visualizer route
```

The operator reports the committed CUSTOM Visualizer does not activate when its display differs from Media's. This is an H functional regression against current architecture, not a J layout preference.

Trace persisted route -> custom decision -> effective monitor -> participant set -> failover state -> chosen unit -> construct result. Do not re-couple Visualizer ownership to same-screen Media.

## 10. H5b — Spectrum has two distinct functional failures

### Data branch

Latest sidecar evidence shows repeated Spectrum bar payloads saturated near/all `1.00` before shader presentation.

Trace:

```text
FFT/bin magnitudes
-> band aggregation
-> resolved Spectrum preset/technical inputs
-> pre-floor/expansion bars
-> post-gain/floor/expansion values
-> upper clamp count
-> final vector
```

### Presentation branch

Physical comparison shows the current Quick output is a dense matrix of tiny repeated segments, while intended Organ/Spectrum is a modest set of bottom-aligned continuous frequency columns.

All-1.00 data can flatten height variation. It cannot explain the primitive/topology substitution.

Trace:

```text
mode/preset identity
-> render snapshot
-> renderer implementation
-> primitive/topology parameters
-> geometry/uniforms
-> retained drawn mode/preset
```

H closes this item after non-degenerate data + correct functional continuous-column representation survive mode switch/recreation. J Parity+ then owns exact column gap/width, line thickness, glow, gradient and elegance.

## 11. H6 — CUSTOM Settings lock scope

Canonical Media CUSTOM resize-lock metadata contains only:

```text
media_font_size
media_artwork_size
```

If seek/progress/glow/volume/mute feature controls are disabled merely because CUSTOM is active, another owner is applying a stale/broad lock.

Inspect parent enabled state, normal feature dependencies and refresh ordering. Remove only the CUSTOM-derived over-lock; do not force-enable controls whose own semantics legitimately disable them.

## 12. H8 — Visualizer middle-click preset hotswap

Historical bug records and pre-Quick source prove a distinct runtime gesture that the current Quick migration contracts did not carry forward:

```text
middle-click retained Visualizer
-> next preset in current mode
-> same-mode activation
-> wraparound including Custom
```

This is H because the product interaction is absent, not because its animation needs polish. Historical R-12 additionally proves `Custom` is a user-owned snapshot: runtime cycling must snapshot it on departure and restore it on re-entry. U-10 records that runtime preset writes were deliberately narrowed to `widgets.spotify_visualizer` after broad refreshes could blank Media metadata.

Current Quick source has no middle-button semantic admission for the visualizer and its `request_mode_change()` path intentionally rejects a target equal to the current mode. Restore the behavior through a distinct retained middle-click hit/action seam and same-mode preset activation transaction under the existing visualizer owner/controller/BeatEngine. Do not revive the historical QWidget `WidgetManager`; old source is behavior evidence only.

Detailed route: `Docs/QtQuick_Migration/H8_Visualizer_Middle_Click_Preset_Cycle_Decomposition_2026-08-30.md`.

## 13. H7 — Exit responsiveness classification

Latest clean run shows:

```text
16:48:10 Exit accepted
16:48:10 displays quiesced/cleared
16:48:10 terminal barrier complete (~250 ms)
16:48:10 ThreadManager done
16:48:10 pycache cleanup starts
16:48:11 code=0 exit logged
```

The action/lifecycle route is no longer a multi-second H blocker in this evidence. Script-only recursive `__pycache__` cleanup consumes visible terminal tail in development. Remeasure window disappearance separately; carry purely developer-housekeeping/performance tail into J/cleanup if windows already dismiss promptly.

## 14. Bubble — J-first unless a deterministic delay seam is proved

Authored cadence/integration remains healthy while physical response is weak/delayed. Do not tune Bubble during Spectrum or unrelated H fixes. J should correlate playback edge -> source freshness -> logical state -> retained publication -> visible result first.

Preserve good Bubble partial/CUSTOM resizing.

## 15. Close discipline

- H source tests are necessary, not sufficient.
- Every physical H run must inspect `screensaver.log` **and** `screensaver_qml.log`.
- Unexpected Qt/QML diagnostics cannot be ignored merely because Python logs are GREEN.
- `Current_Plan.md` owns sequence.
- Historical pre-Quick presentation is an outcome oracle only; current Quick architecture owns implementation.

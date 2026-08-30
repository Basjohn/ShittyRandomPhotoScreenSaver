# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-30 after source-mode run at `1849f2a44154132d6df45e327165b1cd79103bfa` and direct source/log reconciliation.

## Current checkpoint

G remains accepted. The H production-authority cutover and caller-proven deletion of the old physical host remain accepted architecture. **H is still OPEN. I is NOT admitted.**

H1 is now closed and H2 is now closed:

```text
H1a  repeated dual-display Settings/CUSTOM recreation hang     CLOSED
H1b  terminal Quick retirement / Clock model lifetime          CLOSED
H2   Media artwork provider identity                            CLOSED
H3   Reddit retained URL opener                                 IMPLEMENTED / DETERMINISTIC TESTS GREEN — PHYSICAL GATE PENDING
H3b  Clock runtime mode-toggle persistence                      IMPLEMENTED / DETERMINISTIC TESTS GREEN — PHYSICAL GATE PENDING
H4   Media Play/Pause + seek command semantics                  PENDING
H5a  CUSTOM Visualizer independent display admission            PENDING
H5b  Spectrum data saturation + wrong topology                  PENDING
H6   CUSTOM Settings size-lock scope                            PENDING
H8   Visualizer middle-click preset hotswap                     PENDING / SOURCE-PROVEN CONTRACT OMISSION
H7   Exit visible-response/perf classification                  PENDING / likely J after measurement
```

The maintained H destination profile is 76/76 GREEN at agent audit `1c2f4d75` and must remain GREEN after each bounded source change. H is not closed by unit tests alone: every H/H-J row in the operator ledger must be reconciled and the final dual-display source-mode smoke must remain physically clean.

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

### H3 — retained Reddit URL opener

**Status: implemented; deterministic tests GREEN in the real development environment; physical MC/SCR gate pending.**

The source-proven composition hole was real: `RetainedRedditPresentation` already owned URL admission and the `on_open_requested` seam, but production `RedditFamilyAdapter` omitted the callback.

Agent audit at `1c2f4d75` verified the repaired production route end-to-end: `DisplayManager._open_reddit` (weak, generation-fenced) -> `default_ordinary_family_adapters(reddit_open_requested=...)` -> `RedditFamilyAdapter` -> `RetainedRedditPresentation` -> URL admission/action. The earlier RED bare-adapter test was corrected to exercise this real composition seam.

The prepared repair keeps product consequences outside QML/model/presentation:

```text
Retained Reddit semantic URL action
-> RedditFamilyAdapter injected callback
-> weak generation-fenced DisplayManager route
-> existing core.windows.secure_url_launcher authority
-> MC / diagnostic: interactive/direct route
-> ordinary saver: secure handoff, then normal saver exit only after successful handoff
```

The adapter callback does not strongly retain `DisplayManager`, does not create another helper/poller/owner, and helper readiness does not gate teardown.

Prepared deterministic coverage:

```text
tests/test_qtquick_family_product_actions.py
```

It proves saver handoff opens exactly once then requests normal exit exactly once, interactive builds do not exit, and failed/empty opens do not trigger exit. The pure product-action subset is GREEN in this environment; the real PySide production-family composition and Windows MC/SCR physical behavior remain operator/agent validation.

**Validation gate before H3 closes:**

```text
1. run tests/test_qtquick_family_product_actions.py
2. run the relevant retained Reddit / h-destination tests on the real environment
3. MC: admitted Reddit click opens the URL and keeps MC alive
4. SCR/source-saver path: admitted click hands off once and exits normally
5. rejected/untrusted/interaction-disabled URL still does not open
6. inspect screensaver.log + screensaver_qml.log for unexplained action/QML errors
```

If those are GREEN, mark H3 CLOSED and continue without redesigning the helper/opening authority.
### H3b — Clock runtime mode + per-variant CUSTOM geometry

**Status: expanded source-proven repair implemented; deterministic tests GREEN in the real development environment; physical dual-display gate pending.**

The latest physical run narrowed the symptom: Clock can retain the requested analogue/digital state yet recreate at the wrong geometry. The migration had split the old R-45/R-48 contract across several seams:

```text
mode persistence:
retained Clock action -> production callback -> per-display override

recreation geometry:
effective per-display mode -> matching CUSTOM geometry variant

live toggle geometry:
mode-specific rect + font scale -> same display-owned OverlayGeometryBinding

CUSTOM persistence:
custom_layout[screen][clock][analog|digital] -> rect + font_size only
```

Prepared repair:

- production Clock callback persists only the target instance's `display_mode_overrides[screen_signature]`;
- pre-bind hydration uses that same identity-aware effective mode rather than the shared baseline;
- both committed analogue/digital variant states are seeded into the retained Clock (rect **and** variant-specific CUSTOM `font_size`);
- live CUSTOM mode switching replaces the display-owned geometry binding's committed rect, preventing later preferred-size publication from replaying the stale prior-mode rect;
- when an explicit target variant is absent but the opposite CUSTOM variant exists, replay derives a centered/clamped target shape using the saved font scale rather than falling to unrelated authored placement;
- outside an active edit transaction, a runtime mode toggle canonicalizes the target CUSTOM variant through Python Settings/custom-layout authority; active CUSTOM Save/Cancel is never bypassed;
- geometry payloads never regain `display_mode` behavior authority.

Prepared deterministic coverage:

```text
tests/test_qtquick_family_product_actions.py
tests/test_qtquick_clock_custom_variant_geometry.py
```

Both are GREEN in the real development environment. The H3b callback arity and maintained Clock presentation fakes were reconciled there; the remaining proof is the operator-only dual-display geometry/scale gate.

**Validation gate before H3b closes:**

```text
1. run both focused Clock/product-action tests plus relevant retained Clock / h-destination tests
2. dual display: put Clock in CUSTOM at an unmistakable non-default position/scale
3. give analogue and digital visibly different saved rect/scale variants
4. double-click only one display and verify the other display/Clock is unchanged
5. toggle analog -> digital -> analog and require each mode to restore its own rect + scale
6. Settings recreation preserves effective mode and matching geometry
7. CUSTOM Save/Continue recreation preserves effective mode and matching geometry
8. restart/reload preserves the same result
9. inspect custom_layout: variants contain rect/font_size, never display_mode
10. inspect screensaver.log + screensaver_qml.log for unexplained Clock/QML errors
```

If GREEN, mark H3b CLOSED and continue to H4.

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

### H8 — Visualizer middle-click preset hotswap

**Status: deterministic missing product interaction; historical contract exists, current Quick migration contract omitted it.**

Historical runtime behavior and bug records prove that middle-click on the live Visualizer stepped to the next preset in the **current mode**, including the special user-owned Custom slot. The current Quick input/visualizer contract carried double-click mode cycling but not this separate middle-click preset action. Current `RuntimeInputController.handle_mouse_press()` has only right/left-button product handling, and the retained Quick visualizer admission path has a double-click mode-cycle seam only.

Required product contract:

```text
middle-click inside active retained Visualizer
-> advance exactly one preset in the current mode, with wraparound
-> mode identity does not change
-> leaving Custom snapshots its exact user-owned payload
-> returning to Custom restores that payload
-> no next-image / exit / context-menu side effect
```

Do not fake this through `request_mode_change()`: the current Quick owner correctly rejects a target equal to the current mode. Add a distinct bounded same-mode preset activation transaction through the existing visualizer owner/controller/BeatEngine and retained presentation path. It must preserve one source/logical runtime/pacer, stale-generation fencing, fresh-frame admission and the existing transition/reveal semantics.

Preset persistence must remain narrow: mutate/persist `widgets.spotify_visualizer` only. Do not trigger a whole-`widgets` refresh; historical evidence already records that broad runtime preset writes could blank Media metadata. Curated preset application uses replace semantics so stale keys from the prior preset cannot bleed into the target.

Work this after H5/H6 source changes to avoid overlapping visualizer-activation churn, but close it before H re-closes.

Technical route: `Docs/QtQuick_Migration/H8_Visualizer_Middle_Click_Preset_Cycle_Decomposition_2026-08-30.md`.

### H7 — Exit visible-response/performance classification

The current clean run routes Exit immediately and completes the terminal Quick barrier in ~250 ms. Script-mode recursive `__pycache__` cleanup then consumes additional terminal time.

Remeasure **visible window dismissal** separately from legal retirement and developer housekeeping. If visible dismissal is prompt, carry remaining tail/pycache policy into J/performance or cleanup rather than reopening lifecycle ownership.

## Interleaved black-flash / first-visible-frame reality slice

**Status: proof-frame leak repaired; physical trace localized startup ordering and native/same-scene continuity; second bounded repair IMPLEMENTED / AWAITING TEST VALIDATION.**

This operator-approved No Quota interleave still does **not** reorder H4-H8. It is now evidence-driven rather than generic J polish.

Physical `[QUICK_SURFACE]` evidence after the first repair split the symptom:

```text
startup:
window can become visible with no real PresentationImage -> native black clear exposed

A -> B -> A focus:
window_active_changed coincides with flash while visible/exposed/scene graph/image identity stay stable

first context-menu open on each display:
two rapid flashes possible; retained image + scene graph stay stable; later same-display open is clean
```

An old wallpaper/image was physically glimpsed during a first-menu flash, but there was no matching image-publication event. Treat this as stale/native/back-buffer exposure, not image-selection state.

Current bounded repair:

- `QuickDisplayWindow` now separates exact-screen/geometry preparation from native show commit;
- `QuickDisplayRuntime.show_on_screen()` arms visible intent but keeps an image-less scene hidden;
- first real `PresentationImage` publication commits that prepared show; an already-primed retained scene re-shows immediately;
- activation changes and context-menu visible/hidden boundaries request exactly one `BackgroundRenderItem` refresh plus one `QQuickWindow.update()`, reasserting the same retained image without changing semantic state or adding a cadence owner;
- `[QUICK_SURFACE] background_surface_refresh_requested` records those bounded redraw requests.

Focused regression:

```text
tests/test_qtquick_black_flash_contract.py
```

It now pins proof opt-in, real-image first-frame readiness, first-show image gating, first-image show commit and single event-driven background continuity refresh. It is **AWAITING TEST VALIDATION** under real PySide6.

Technical route:
`Docs/QtQuick_Migration/J_Black_Flash_Surface_Continuity_Decomposition_2026-08-30.md`.

Next physical decision: if startup clears and focus/menu flashes improve, preserve these contracts. If focus still flashes while `background_surface_refresh_requested` is present and image/scene remain stable, investigate native `QQuickWindow` activation/composition policy next. If only first-menu flash remains, inspect/prewarm the retained menu's first-visible QSG resources rather than altering the base image.

## H observations intentionally carried to J unless a deterministic seam appears

### Bubble response

Bubble remains physically weak/delayed despite healthy authored ~90 Hz cadence/integration. Do not tune sensitivity/physics during unrelated H work. J must correlate playback edge -> source freshness -> logical Bubble state -> retained publication -> visible consequence. Promote only a proven stale/delayed owner seam.

Preserve the currently good Bubble partial/CUSTOM resizing.

### Black/test-frame/focus/context flashes

Black flashes remain high-priority J/H-conditional work. Trace now proves startup had an early-exposure seam, while focus and first-menu flashes occur with stable image identity and scene graph. Preserve the current bounded repairs and classify the next physical result before changing native window policy or menu resource lifetime.

## H re-closure gate

H closes only when:

1. H1 reconstruction + terminal-retirement regressions remain GREEN;
2. H2 artwork provider identity remains GREEN and real artwork remains visible;
3. Reddit URL actions reach the correct product opener;
4. Clock runtime mode toggle and its matching per-mode CUSTOM rect/scale survive Settings/Edit recreation;
5. Media Play/Pause + seek work on the real provider while Previous/Next remain working;
6. CUSTOM Visualizer can own a different selected display from Media while non-CUSTOM still follows Media;
7. Spectrum has non-degenerate data and the correct functional continuous-column representation after switch/recreation;
8. CUSTOM Settings locks only size-authoring controls;
9. middle-click inside the retained Visualizer hotswaps exactly one preset in-place, including a lossless Custom round-trip, without changing mode or disturbing Media;
10. Exit visible response is measured/understood with clean natural termination;
11. unexpected `screensaver_qml.log` warnings/errors relevant to these paths are reconciled;
12. maintained `h-destination` is GREEN after the bounded fixes;
13. every unresolved ledger row whose phase includes H is closed or explicitly carried to J with evidence;
14. a short dual-display source-mode smoke is GREEN.

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
- low-priority CUSTOM/Edit guide visibility: existing grid/guide presentation must actually publish useful snap/alignment guides during editing; do not invent a second layout owner;
- low-priority Quick-native performance/debug overlay parity if the product affordance is still desired; it must consume read-only current metrics and must not resurrect legacy GL presenter/profiler ownership;
- **Qt/QML sidecar review as part of physical acceptance**, not console-only inspection.

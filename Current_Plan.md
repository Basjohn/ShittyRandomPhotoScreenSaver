# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-31 after MEASURING the black-flash root cause with PresentMon (fullscreen-flip-promotion PresentMode transitions on the LG/Display-1 output) and landing the coverage-preserving 1px overscan fix; maintained h-destination GREEN.

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

**Status: IMPLEMENTED / deterministic focused gates GREEN; physical Spotify validation pending.**

Trace the real command boundary:

```text
semantic request
-> worker submission
-> real WinRT method result / bool / exception
-> state reconciliation refresh
```

Do not treat queue submission as success. Do not block the GUI waiting for WinRT. Preserve Previous/Next, which already work through the same card.

Verify Spotify's actual toggle behavior and the seek units/result of `try_change_playback_position_async()`.

Live closure checklist:

- [x] Project canonical GSMTC `is_play_enabled`, `is_pause_enabled`, and
  `is_play_pause_toggle_enabled`; the retired/nonexistent `is_play_pause_enabled`
  spelling no longer greys the retained glyph.
- [x] Choose state-specific Play/Pause when supported and Toggle only when that
  is the provider capability; preserve working Previous/Next.
- [x] Keep GUI submission non-blocking while separately carrying the real WinRT
  Boolean/exception outcome to the one shared Media runtime owner.
- [x] Reconcile only after command completion; if a poll is already in flight,
  coalesce exactly one completion-driven follow-up refresh.
- [x] Preserve seek as absolute GSMTC 100 ns ticks and treat `False` as provider
  rejection rather than queue success.
- [ ] Physical current-source Spotify gate: with Ctrl held, glyph is enabled;
  Play -> Pause -> Play changes Spotify; seek near 25% and 75% lands correctly;
  Previous/Next remain working; inspect both runtime logs for command outcome.

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

**Status: SOLVED (recurring flash). Root cause MEASURED with PresentMon: the exact-cover borderless window is non-deterministically promoted to a hardware fullscreen-flip presentation, and the composition <-> `Hardware: Legacy Flip` PresentMode transitions present the black/stale frames on the LG/Display-1 output (4K 60 Hz secondary TV). Fix: a 1px coverage-preserving overscan (`_fullscreen_compat_geometry`) keeps the window non-exact-cover, so it stays in stable `Composed: Copy with GPU GDI` and never transitions. 6/6 flashing-prone launches -> black=0, operator-confirmed no flashes. Two earlier repairs (deferred first-show, event-driven surface-refresh) physically FAILED and were removed.**

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

An old wallpaper/image was physically glimpsed during a flash, but with no matching image-publication event. Treat this as stale/native/back-buffer exposure, not image-selection state.

**New binding evidence (single-window MC A/B):** running one continuous MC process and switching the sole SRPSS window between outputs gave: LG/Display-1 only -> black flashes; MSI/Display-0 only -> completely clean; LG/Display-1 again -> black flashes. The defect **follows the LG output (a 60 Hz TV, DPR 1.5, physical 3840x2160) even when it is the ONLY SRPSS window.** This kills the earlier "secondary window / two-window activation" framing.

**Removed as physically failed (do not reintroduce):**

- deferred first-show (`prepare_on_screen()` / `commit_prepared_show()` gating the native show on first `PresentationImage`) — it made startup visibly WORSE (image -> black -> image); reverted to the immediate `show_on_screen()`;
- event-driven surface-refresh (`_request_background_surface_continuity()` -> `BackgroundRenderItem.request_surface_refresh()` + `QQuickWindow.update()` on activation/menu) — it did not improve the focus/menu flash; removed.

**Kept:** production proof-colour-band removal (opt-in only); `[QUICK_SURFACE]` telemetry (passive); real-image readiness semantics (`intentional_base_frame_ready`) independent of the removed show gate. Focused regression `tests/test_qtquick_black_flash_contract.py` now pins only proof opt-in + readiness.

**Failed approaches (physically disproven — do NOT retry):**

- [x] Persistent scene graph + graphics (`setPersistentGraphics/SceneGraph(True)`) — operator saw no change; telemetry: SG is never invalidated mid-flash, so persistence cannot matter.
- [x] Event-driven surface-refresh redraw on activation/menu (`BackgroundRenderItem` refresh + `QQuickWindow.update()`) — did not improve focus/menu flash. Removed.
- [x] Deferred first-show (gate native show on first image) — made startup visibly worse (image -> black -> image). Removed.
- [x] VSync ON (`swapInterval=1`) alone — no reliable reduction; single-run counts are inside a large launch-to-launch variance band.
- [x] Drop `SplashScreen` role — non-deterministic: identical code gave 0 flashes one launch, 15 the next (both operator-corroborated). Not a reliable fix.
- [x] `WS_EX_NOACTIVATE` / `WindowDoesNotAcceptFocus` / DWM-transition-disable / Ctrl-poll replacement — PROHIBITED (feature loss); never a valid endpoint.

**Solution (measured + operator-confirmed):**

- [x] Coverage-preserving 1px overscan (`QuickDisplayWindow._fullscreen_compat_geometry`, `x-1,y-1,w+2,h+2`). PresentMon proof: exact-cover baseline showed `Hardware: Legacy Flip` present rows with black/stale events clustered at the composition<->flip transitions; height-1 (3/3) and overscan (3/3) launches stayed 100% `Composed: Copy with GPU GDI` with black=0. Overscan chosen over height-1 because it loses no visible row. This recovers the historical `_FULLSCREEN_COMPAT_WORKAROUND` principle. Regression: `tests/test_qtquick_window.py::test_fullscreen_compat_geometry_overscans_without_losing_coverage`.

Remaining (minor, separate seam): operator still saw at most ~1 flash on startup — the show-before-first-frame interval, distinct from the resolved recurring/activation flash. Carry to J unless it recurs.

Diagnostic method for future presentation issues (ephemeral, NOT committed to the repo): run `C:\tools\PresentMon\PresentMon.exe` capture-all (`--timed N --qpc_time --output_file …`, works unelevated; process rows resolve, `SwapChainAddress` is `0x0` without elevation) alongside a DXGI Desktop-Duplication (`dxcam`) near-black/stale detector timestamped in QPC, then compare `PresentMode`/`AllowsTearing` in a +/-250 ms window around each detected frame. Drive activation with Win32 `SetForegroundWindow` (no cursor motion, so the mouse-move exit gesture never fires). See `Docs/Qt_QML_Observability.md`.

Constraints honored: no feature loss; no `WS_EX_NOACTIVATE`/`WindowDoesNotAcceptFocus`; no DWM transition disabling; no Ctrl-poll replacement; no permanent diagnostic env var/tool; no second surface. Independent/hardware flip is an optimization, not a correctness requirement — SRPSS stays correct in ordinary composition.

Technical route:
`Docs/QtQuick_Migration/J_Black_Flash_Surface_Continuity_Decomposition_2026-08-30.md`.

## H observations intentionally carried to J unless a deterministic seam appears

### Bubble response

Bubble remains physically weak/delayed despite healthy authored ~90 Hz cadence/integration. Do not tune sensitivity/physics during unrelated H work. J must correlate playback edge -> source freshness -> logical Bubble state -> retained publication -> visible consequence. Promote only a proven stale/delayed owner seam.

Preserve the currently good Bubble partial/CUSTOM resizing.

### Black/test-frame/focus/context flashes

The recurring/activation black flash on the LG/Display-1 output is SOLVED (fullscreen-flip-promotion PresentMode transitions; fixed by the coverage-preserving overscan — see the black-flash slice above). A minor startup-only flash may remain (show-before-first-frame) and is carried to J unless it recurs. The two prior bounded repairs failed and were removed; do not reintroduce them.

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

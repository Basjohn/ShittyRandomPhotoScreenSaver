# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-30 physical H1 verification and clean-exit reconciliation at pushed `af8896b52fbee153fe1cd0b627a55455c14625d1`.

## Current checkpoint

G remains independently audited and accepted. The H production-authority cutover and caller-proven deletion of the old physical host remain accepted architecture. **H itself is still OPEN. I is NOT admitted.**

The earlier post-cutover runtime-reality corrections remain accepted:

```text
da3dafab  controller-owned tick diagnostic defaults
cad4e6d2  active transition replacement -> cancel to destination, then replace
adcfd96d  successive visualizer revisions request retained presentation
747e3140  context menu no longer self-dismisses on its opening right-click
```

H1's intermittent dual-display reconstruction hang is now materially improved by:

```text
6c7ef945  bounded replacement-construction hang watchdog
2220782d  build all admitted retained families before activating any
af8896b5  docs checkpoint awaiting repeated physical gate
```

The operator then ran one dual-display source process at `af8896b5` through **3 Settings recreation cycles and 5 CUSTOM Save/Continue recreation cycles with no watchdog dump and no recreation hang**. That is enough to close the reconstruction-hang subproblem. It does **not** close H1 as a whole because ordinary terminal Exit still tears down unsafely and ends in a Windows access violation after the application has already logged `Exiting (code=0)`.

Detailed current evidence and ownership analysis are in:

`Docs/QtQuick_Migration/H_Post_Cutover_Runtime_Reality_Corrections.md`

The complete physical observation backlog is in:

`Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`

Focused technical decompositions for the new evidence are:

```text
Docs/QtQuick_Migration/H1b_Terminal_Retirement_And_Settings_Teardown_Decomposition_2026-08-30.md
Docs/QtQuick_Migration/H5_Visualizer_Routing_And_Spectrum_Decomposition_2026-08-30.md
Docs/QtQuick_Migration/H6_Custom_Settings_Lock_Scope_Decomposition_2026-08-30.md
```

**Parity+ rule:** Phase J uses proven historical presentation as a **quality floor, not a ceiling**. Primary visual references are the 4.7.2/4.7.0 release screenshots; `15099d3` is the cleaner old-code behavior reference and `3fe5df6` is a later mixed reference that already contains some migration work. Recover good historical outcomes, preserve genuine Quick improvements, and improve weak legacy behavior rather than reproducing bugs. Historical implementation is never authority: do not restore, wrap, adapt or depend on the deleted QWidget/QRhi/GL presenter architecture.

Durable reference:
`Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md`

## Production architecture — still binding

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
- Old-generation admission closes and authored/logical work joins before scene/window retirement.
- Generation `0` is valid.
- Fallbacks are product-authorized, destination-owned and fail-loud.
- QML reports preferred content size only; Python owns anchor + margin + clamp + x/y + final outer rect.
- CUSTOM committed geometry outranks family/default geometry.
- Outside CUSTOM, Visualizer effective position/monitor routing follows Media.
- In committed CUSTOM, Visualizer owns its own persisted monitor/geometry, may overlap, and may live on a different selected display from Media.
- Bubble authored cadence remains presentation-independent; the display Quick frame pacer is the sole GUI presentation opportunity.
- Bubble Temporal Fidelity remains binding. Do not reduce cadence or retune its physics merely to hide a presentation problem.

## Active H work — execute in this order

### H1a — dual-display reconstruction hang

**Status: PHYSICAL GATE PASSED at `af8896b5`; preserve the repair.**

Landed repair `2220782d` makes `OrdinaryFamilyPresentationBinder.bind()` two-phase:

```text
phase A: resolve/build/own every admitted retained family
phase B: activate every successfully built family exactly once, in stable order
```

The operator's verification process produced watchdog arm records for:

```text
CUSTOM  14:41:01
Settings 14:42:22
CUSTOM  14:43:03
CUSTOM  14:43:20
Settings 14:44:51
CUSTOM  14:45:17
CUSTOM  14:45:30
Settings 14:46:27
```

No watchdog stack dump followed any of them. Both replacement displays returned repeatedly. Keep `tests/test_qtquick_family_binder_two_phase.py` and do not reopen the old Media-COM/Gmail-construction theories without a new hang.

### H1b — terminal Quick retirement and Settings teardown hygiene

**Status: repair LANDED (`dcf3ced9`, `f111db61`); awaiting the operator's dual-display terminal-Exit physical gate. H2 waits until that gate is GREEN.**

**Landed:**
- **Settings event-filter hygiene (`dcf3ced9`).** `_ControlShadowHelper.eventFilter` and `ComboKnobController.eventFilter` read the tracked target (`_widget` / `_host`) through a guarded local reference and return early when it is absent; on Destroy, removal tolerates an already-invalid target. `tests/test_settings_eventfilter_teardown_guards.py` proves a late Qt event after Python-side teardown cannot raise.
- **Terminal retirement drain (`f111db61`).** `RuntimeDestructionBarrier` gained a `purpose` (`replacement` | `terminal`). A terminal-purpose barrier no longer self-cancels when terminal shutdown is requested (`_maybe_complete` / `_run_continuation` skip the `qt_replacement_may_run` gate for terminal), so it observes the SAME Quick/QObject/Python/resource roots to completion and then runs a terminal finalization exactly once; it never admits a replacement. `teardown_display_runtime` arms a terminal-purpose barrier for `application_exit` (`engine_cleanup` stays barrier-free). Terminal `stop()` is staged: intent → quiesce/clear → begin Quick retirement → observe the barrier to completion → `_run_stop_finalization` (beat engine / usage telemetry / ProcessSupervisor / ThreadManager shutdown, housekeeping, `QApplication.quit()`). On terminal timeout the barrier fails loudly but still finalizes and terminates — no force-kill, no claimed success. Replacement-barrier and non-terminal-stop semantics are unchanged; no `processEvents`/sleeps/`gc.collect`/kill/leak. `tests/test_terminal_runtime_destruction.py` pins: terminal waits for roots, finalizes exactly once despite `qt_replacement_may_run()` being False, refuses a replacement continuation during terminal shutdown, and leaves replacement behaviour unchanged.
- h-destination 68/68 GREEN.

**Operator run (2026-08-30 15:49–15:51) — terminal drain confirmed, storm root-caused:**
- Both exits show `[LIFECYCLE_BARRIER] armed reason=application_exit` → `complete` (250 ms / 235 ms) → ThreadManager shutdown → `Exiting(code=0)`, with `BackgroundRenderItem` and `QQmlEngine` destroyed **through the barrier** before exit. The **Windows access violation and `BackgroundRenderItem::` slot error are GONE** (operator confirmed console clean). §G resolved by the terminal drain.
- The **Clock null-model storm persisted** — but it is **QML-engine `TypeError`s printed to stderr** (`ClockAnalogueFace.qml: Cannot read property '…' of null`), which never enter the Python logger, so log scans (mine included) showed zero. Root cause (per §F): the retained item is retired with deferred `deleteLater()` while the Clock model is a parentless Python-owned QObject destroyed synchronously when its owner drops — so the still-live item's bindings re-evaluate against a null model during retirement.

**Landed (`d4c46559`):** `OrdinaryWidgetPresentationHost.create_family_widget` parents any *parentless* QObject model passed as an initial property to its item, so the model outlives the item's binding teardown and dies with the item. Already-parented models (Media/Gmail/Steam, parented to a generation-scoped window whose generation their neutral service reads via `consumer.parent()`) are left untouched. No per-property QML null guards. New retirement bar `tests/test_qtquick_retained_model_lifetime.py`; h-destination 69/69.

For reference, the originally observed terminal failure this repair targets:

The same physical run ends this way:

```text
Exit requested
-> RUNNING -> SHUTTING_DOWN
-> displays quiesced/cleared
-> DisplayManager begins asynchronous retirement for 2 Quick units
-> ThreadManager shutdown
-> application logs normal Exiting(code=0)
-> AttributeError: Slot 'BackgroundRenderItem::' not found
-> Windows fatal exception: access violation
-> GC / no Python frame
```

Before that terminal crash, retiring Clock QML repeatedly evaluates against a `null` model (`fontFamily`, `timezoneText`, `textColor`, `showSeparator`, angles, shadow values, etc.). This is **not a missing-font diagnosis**; the common failure is that the QML model reference is null during retirement.

Current source also proves a lifecycle-order gap:

- replacement teardown creates a `RuntimeDestructionBarrier`;
- `application_exit` and `engine_cleanup` deliberately skip that barrier;
- `DisplayManager.cleanup()` only **begins asynchronous** Quick retirement;
- `QuickDisplayUnit.retire()` relies on `retirement_completed` / `deleteLater`;
- terminal `stop()` proceeds into process/thread shutdown and `QApplication.quit()` without waiting for those Quick roots to finish.

Repair the terminal retirement boundary using the existing lifecycle authority. Do **not** hide the problem with QML null-property fallbacks, missing-font work, forced `gc.collect()`, arbitrary sleeps, event-loop pumping, process kill, leaked windows, or a second shutdown manager.

Required sequence:

1. Make Settings helper event filters safe under late destruction:
   - `_ControlShadowHelper.eventFilter()` may not assume `_widget` still exists;
   - `ComboKnobController.eventFilter()` may not assume `_host` still exists;
   - late callbacks must return harmlessly rather than raise through Qt.
2. Separate **retirement completion proof** from **replacement admission** in the existing destruction machinery:
   - terminal shutdown must be allowed to observe old Quick/QObject roots to completion;
   - terminal shutdown must never execute a replacement continuation;
   - keep the Qt event loop alive long enough for legal `deleteLater` / render-safe retirement to complete;
   - only after the retirement drain is complete may terminal pool/process teardown and `QApplication.quit()` finish.
3. Preserve replacement barrier behavior exactly.
4. After the ordering repair, verify whether the Clock null-model storm disappears naturally. If it remains, inspect retained item/model retirement ordering; do not treat each QML property warning independently.
5. The `BackgroundRenderItem::` slot error and final access violation must be gone.
6. Keep visible Exit responsiveness measured separately: current action -> quiesce/clear happens in the same logged second; the current ~2 s tail includes pycache cleanup, but final latency is not accepted until clean shutdown is restored.

Focused tests supplied in the handoff:

```text
tests/test_settings_eventfilter_teardown_guards.py
```

Add/extend runtime-shaped lifecycle coverage for the terminal retirement drain once its exact API is chosen. Do not encode a second lifecycle architecture in the test.

H1b physical close condition:

```text
dual-display source mode
-> ordinary context-menu Exit
-> visible windows dismiss promptly
-> no Clock null-model error storm attributable to retirement
-> no BackgroundRenderItem slot error
-> no Windows fatal exception/access violation
-> process exits naturally
```

A second clean ordinary Exit is useful confidence if the first is GREEN.

### H2 — Media artwork decoded but cannot reach the QML engine provider

**Status: source-proven wiring defect; NEXT after H1b is GREEN.**

`QuickSceneFactory` registers one `MediaArtworkImageProvider` on the shared `QQmlEngine`. Production Media construction creates/injects another provider into `MediaPresentationModel`. Decoded artwork is therefore published into an object QML never resolves.

Required fix:

- inject the exact engine-registered artwork provider through the existing Quick family assembly;
- do not register a duplicate image provider or create one per card;
- add a production-composition cross-layer regression;
- physically verify real artwork after decode.

### H3 — retained Reddit URL click has no production opener

**Status: source-proven wiring defect.**

Production `RedditFamilyAdapter` does not provide `RetainedRedditPresentation`'s existing opener callback. Reconnect the semantic action to established product authority:

```text
MC  -> direct desktop URL open
SCR -> existing deferred/helper queue + normal saver exit
```

No helper policy belongs in QML/model and helper readiness must not block teardown.

### H4 — Media Play/Pause and seek do not execute; Previous/Next do

**Status: operator-reproducible; narrow command boundary.**

Preserve Previous/Next as the working control group. Instrument:

```text
request
-> worker submission
-> real WinRT result/exception
-> state reconciliation
```

Verify real Spotify toggle semantics and seek units/result. Queueing a worker task is not command success. Do not block the GUI.

### H5a — CUSTOM Visualizer must remain independent of Media's display route

**Status: operator-reproducible functional regression; existing source contract already says this should work.**

The operator reports that when Media lives on one display and the committed CUSTOM Visualizer belongs on another, the Visualizer does not even try to activate.

The intended routing contract is already explicit in current source:

```text
non-CUSTOM visualizer -> effective route comes from Media
CUSTOM visualizer     -> own spotify_visualizer position/monitor route is authoritative
```

`QuickDisplayUnit.is_visualizer_participant()` is also independent of Media presence. Therefore **do not redesign routing** and do not re-couple Visualizer construction to a Media card on the same screen.

Use the technical decomposition to trace one generation:

```text
visualizer persisted position
visualizer persisted monitor
Media monitor
custom=True/False
resolved effective monitor
requested zero-based screen
live participant set
chosen/failover owner
construct-owner result/rejection reason
```

Focused semantic test supplied:

```text
tests/test_visualizer_custom_route_contract.py
```

Add a production admission test once the failing seam is identified: Media route 1 + Visualizer CUSTOM route 2 must yield the one Visualizer owner on selected participant 2. The same configuration with a non-CUSTOM Visualizer must follow Media route 1.

### H5b — Spectrum data saturation + wrong functional presentation topology

**Status: operator-reproducible; H owns the broken functional representation, J owns later Parity+ polish.**

The latest visualizer sidecar proves one upstream defect: Spectrum activation uses `bar_count=35`, then repeatedly publishes authored/computed bars where essentially every value is clamped to `1.00`.

Physical comparison now proves a second, independent-looking symptom: the current Quick Spectrum/Organ output is a dense full-height matrix of tiny segmented blocks, while the intended Organ/Spectrum family is a modest set of bottom-aligned continuous vertical frequency columns with variable heights. Saturated data can explain pinned energy; it does **not** by itself explain the wholesale primitive/topology substitution.

Use the historical reference only as a user-visible oracle:
- release 4.7.2 / 4.7.0 screenshots;
- `15099d3` as cleaner old behavior code;
- `3fe5df6` only as a later mixed reference.

Do not copy old presenter code.

Required sequence:

1. reproduce with the operator's Organ preset 1/current Spectrum activation;
2. prove canonical mode + preset identity;
3. capture bounded data stages: raw FFT/bands -> Spectrum mapping -> pre-gain/floor bars -> post-normalization/expansion bars -> clamp count;
4. identify why the 35-bar payload saturates and repair the smallest Spectrum-specific owner;
5. independently trace presentation identity: render snapshot mode/preset -> renderer implementation -> primitive/segment topology -> retained draw;
6. identify why Organ/Spectrum resolves to the current dense segmented matrix instead of the intended continuous-column representation;
7. repair the smallest presentation-selection/topology owner without changing shared cadence or resurrecting legacy rendering;
8. verify non-degenerate live bars and recognizably correct Spectrum/Organ topology after both mode switch and recreation.

**H acceptance is intentionally bounded:** correct data + correct functional Spectrum representation family. Exact column spacing, glow, gradient/rainbow elegance, line thickness and screenshot-level polish belong to J Parity+ once the representation is correct.

Do not change Bubble/shared cadence to fix Spectrum.
### H6 — CUSTOM Settings may lock only size-authoring controls

**Status: operator-reproducible functional Settings defect.**

CUSTOM geometry owns size. It does not own ordinary feature/appearance semantics.

For Media, the canonical descriptor already says the CUSTOM resize lock is only:

```text
media_font_size
media_artwork_size
```

Yet physical Settings currently greys out seek/progress/glow and other non-size controls while CUSTOM is active.

Required fix:

- retain normal dependency gating (`show controls`, `show progress`, `glow enabled`, provider capability, etc.);
- CUSTOM itself may disable only true size-authoring controls;
- determine whether the observed extra lock comes from a parent container enable state, a second/stale lock owner, or dependency refresh order;
- fix the smallest secondary owner rather than broadening the descriptor.

Focused intent test supplied:

```text
tests/test_custom_resize_lock_scope.py
```

This test should already be GREEN on current source; that is useful evidence that the defect lies outside the canonical descriptor.

### H7 — Exit responsiveness after clean-exit repair

**Status: partially localized; defer final classification until H1b is clean.**

Current log shows:

```text
14:46:41 Exit accepted
14:46:41 SHUTTING_DOWN
14:46:41 displays quiesced/cleared
14:46:41 async retirement begins
14:46:41 ThreadManager shut down
14:46:41 pycache cleanup starts
14:46:43 pycache cleanup ends / Exiting logged
```

So the context action itself does not appear to be the multi-second owner in this run. Remeasure after H1b. If windows dismiss immediately and only optional housekeeping consumes tail time, carry that as J/performance/maintenance cleanup. If visible windows remain after action acceptance, repair the smallest visible-dismiss owner in H.

## H observations that remain J unless a deterministic owner defect is proved

### Bubble reactivity

Bubble still physically feels barely reactive: delayed visible start/stop and little contraction/expansion. Raw authored metrics remain healthy (~90 Hz and requested/integrated ratio 1.000), so **do not tune Bubble now**.

J must correlate:

```text
playback edge
-> audio/source freshness
-> logical Bubble state
-> retained publication
-> visible geometry/energy consequence
```

A stale/delayed deterministic owner is repaired at that seam. Otherwise authored visible-response tuning waits for J. Preserve the currently good Bubble partial/CUSTOM resize behavior.

### Black flashes, test-colour-band startup flash and focus flicker

These remain high-priority J physical-presentation defects unless bounded tracing proves semantic image/reveal state is reset or an actual diagnostic frame is admitted into production. Do not add black clears or repaint loops.

## H re-closure gate

H can re-close only when all of the following are true on exact current source:

1. the accepted runtime-reality regressions remain GREEN;
2. H1a two-phase family construction remains GREEN and the repeated dual-display recreation pass is preserved;
3. ordinary terminal Exit completes without QML retirement storms, dangling slot errors, Windows fatal exception or lingering process;
4. Settings helper teardown produces no Python event-filter AttributeErrors;
5. Media artwork visibly resolves from a real decoded snapshot through the engine-registered provider;
6. Reddit admitted URLs reach the correct MC/SCR opener;
7. Media Play/Pause and seek work while Previous/Next remain working;
8. CUSTOM Visualizer can own a different selected display from Media while non-CUSTOM still follows Media;
9. Spectrum produces non-degenerate live bars and the correct functional Organ/Spectrum representation family (continuous frequency columns rather than the current dense segmented matrix) after mode switch and recreation;
10. CUSTOM Settings locks only controls whose values author committed size; ordinary feature/appearance controls remain usable subject to their normal dependency gates;
11. Exit visible responsiveness is measured/understood after clean terminal retirement;
12. maintained `h-destination` is rerun once after the bounded fixes and remains GREEN;
13. every unresolved ledger row whose phase includes **H** is closed or explicitly carried into J with a recorded reason;
14. a short final dual-display source-mode smoke is GREEN.

Only then may I start.

## I residue reconciliation — blocked

I remains source/test/tool residue cleanup after H. Do not use I to absorb these runtime defects and do not restore legacy presentation to satisfy stale tests.

## J acceptance inputs — explicit Parity+ destination

Use:

```text
Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md
Docs/QtQuick_Migration/J_Visual_Parity_Runtime_Acceptance_Addendum_2026-08-30.md
Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md
Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md
```

Named J cells include:

- startup/focus/context-menu/transition black flash and whole-scene flicker;
- intermittent startup flash resembling diagnostic/test colour bands;
- actual gentle reveal/fade;
- Media proportions/artwork sizing/header/control-strip parity after H2 restores data;
- Gmail row clipping and refresh/header parity;
- Reddit/Gmail/Media logo/header consistency;
- Achievement Pulse icon placement, unlocked-count allocation and dead-space removal;
- consistent header border/chrome;
- optional Media `Junk` / `Paused` metadata;
- one coherent visible pointer treatment (no OS cursor + cursor halo double pointer);
- adjacent/outside Media app-volume accessory as the canonical existing toggle outcome;
- ordinary/non-CUSTOM widget placement without dog-piling, especially Media + Visualizer adjacent free-space placement;
- CUSTOM overlap/cross-display authority untouched by ordinary collision avoidance;
- context submenus that dismiss/switch coherently after hover leave;
- Bubble visible reactivity/latency while preserving BTF and good partial resizing;
- physical A->B->A focus, mixed refresh/DPR, off/wake, performance tails and clean installed exit.

Finishing the active coding slice never closes this list by implication.

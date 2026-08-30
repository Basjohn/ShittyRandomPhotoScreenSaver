# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-30 runtime-reality reconciliation at pushed `fe8e6dbe10ac0a98fe43f612dd228f3f8eb8f8f3`

## Current checkpoint

G remains independently audited and accepted. The H production-authority cutover and caller-proven deletion of the old physical host remain accepted architecture. **H itself is still OPEN. I is NOT admitted.**

The first post-cutover runtime-reality pass exposed four deterministic seams which have now been corrected and added to the maintained destination boundary:

```text
da3dafab  controller-owned tick diagnostic defaults
cad4e6d2  active transition replacement -> cancel to destination, then replace
adcfd96d  successive visualizer revisions request retained presentation
747e3140  context menu no longer self-dismisses on its opening right-click
e1d80f4d  runtime-reality file added to h-destination; reported 64/64 GREEN
```

Keep those fixes. Do not reopen them without exact regression evidence.

A second real dual-display smoke, including source `4f33981`, then exposed additional product failures. These are now the active H boundary. Visual parity remains explicitly separated into J.

Detailed evidence, ownership hypotheses and gates are in:

`Docs/QtQuick_Migration/H_Post_Cutover_Runtime_Reality_Corrections.md`

The complete operator-observation backlog, including positive preservation targets, is in:

`Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`

**Parity rule:** the pre-Quick implementation is a user-visible outcome/design-language reference only. It may be used to establish how sizing, spacing, clipping, artwork, controls, refresh treatment and interaction felt when those behaviors were better. It is never permission to restore, wrap, adapt or depend on the deleted QWidget/QRhi/GL presenter architecture. Reproduce good outcomes in the accepted Quick architecture; preserve genuine Quick improvements.

## Production architecture — still accepted

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

Do not restore `DisplayWidget`, QRhiWidget/GLCompositor presentation, a QWidget compatibility facade, a second presenter, a second visualizer owner/pacer, or a software fallback.

## Active H blockers — work in this order

### H1 — dual-display replacement intermittently hangs during screen-1 retained-family construction

**Status: two-phase binder repair LANDED (`2220782d`); awaiting the operator's repeated dual-display physical gate. Two independent watchdog captures localized both Settings and CUSTOM hangs to the same retained Gmail QML creation call racing an earlier family's deferred activation work; the earlier Media/native localization is superseded. Gmail-QML stage isolation remains the fallback diagnostic if the physical hang survives.**

**Landed (`2220782d`):** `OrdinaryFamilyPresentationBinder.bind()` is now two-phase — phase 1 resolves/builds/owns every admitted retained presentation in the stable adapter order without activating; phase 2 activates each successfully built presentation exactly once, in the same order, only after all construction has returned. Admission (effective-family + per-instance enabled + monitor route), geometry resolution, fail-closed build, ownership and `retire_all()` are unchanged; no new manager/provider/worker/timer/presenter/scene/fallback, no sleeps, activation stays synchronous. New deterministic bar `tests/test_qtquick_family_binder_two_phase.py` pins build-all-then-activate-all ordering, no-activation-during-a-later-build, at-most-once activation, skipped/failed builds never activate, admission order unchanged, and exact retirement. Existing Qt binder tests GREEN; `h-destination` 66/66. The hang watchdog (`6c7ef945`) is retained for the physical gate.

**Pending operator gate:** one dual-display source-mode process with ≥3 Settings recreation cycles and ≥3 CUSTOM Save/Continue recreation cycles, then ordinary Exit. No watchdog fire and a clean exit across all cycles is the pass; a single clean cycle is not proof (both paths showed intermittent success next to a hang). If `logs/hang_stacks.log` gains a new entry, send it — the fallback Gmail-QML stage split below applies.

Exact source for both captured hangs:

```text
fe8e6dbe10ac0a98fe43f612dd228f3f8eb8f8f3
```

The operator now has both lifecycle paths on the watchdog:

```text
13:53:26  CUSTOM replacement armed and completes
13:53:50  Settings replacement armed -> HANG
14:01:29  Settings replacement armed and completes
14:02:39  CUSTOM replacement armed -> HANG
```

In **both** timed-out hangs, the Python MainThread is in the same call chain:

```text
QQmlComponent.createWithInitialProperties(...)
-> QuickSceneFactory.create_ordinary_widget_family
-> OrdinaryWidgetPresentationHost.create_family_widget
-> RetainedGmailPresentation.__init__
-> GmailFamilyAdapter.build
-> FamilyPresentationBinder.bind
-> screen 1 replacement construction
```

Therefore the demonstrated blocked operation is **synchronous retained Gmail QML instantiation**, common to Settings and CUSTOM replacement. The former inference that the last `[MEDIA_NATIVE][H1]` line identified a Media COM/native blocker is no longer valid.

Both watchdog captures also sample the same two concurrent locations:

```text
io_pool worker -> media_runtime.decode_media_artwork -> QImageReader.read()
log writer     -> RotatingFileHandler.shouldRollover -> os.path.exists()
```

That repetition strengthens the case for an ordering/concurrency gate, but it still does **not** prove either concurrent stack is causal. Do not patch COM, QImageReader, logging, Gmail child effects, or filesystem policy from a stack coincidence alone.

The exact production binder currently interleaves presentation construction and runtime activation:

```text
build family presentation
-> activate that family/service
-> build next family presentation
```

Thus Media provider/artwork work can begin while later Gmail QML is synchronously being constructed. Both captured hangs show that overlap at watchdog time. The smallest coherent first repair is to stop service activation from racing the remainder of retained-family QML assembly.

**Required next work — bounded two-phase family assembly:**

1. Inspect exact current `FamilyPresentationBinder.bind()` and preserve its admission/build order, monitor routing, geometry resolution, failure-closed behavior, and one-presentation ownership.
2. Change only the construction/activation sequence for one display generation:
   - phase A: resolve/build/own all admitted retained family presentations without activating their runtime services;
   - phase B: after all admitted family QML construction has returned, activate each successfully built presentation exactly once in the same deterministic order.
3. Do not create a second runtime manager, provider, worker, poller, timer, presenter, scene, fallback, or compatibility architecture. Do not add sleeps or make activation asynchronous merely to hide the stall.
4. Add a focused deterministic regression proving no activation occurs while a later admitted family is still being built; every successful build activates at most once; failed/skipped builds do not activate; monitor/effective-family admission is unchanged; retirement remains exact.
5. Re-run the focused family/runtime tests and `h-destination`.
6. Stop for the operator-only physical gate: one dual-display source-mode process with at least three Settings recreation cycles and three CUSTOM Save/Continue recreation cycles, followed by ordinary Exit. A single successful cycle is not evidence because both lifecycle paths have now shown intermittent success immediately before/after a hang.

If that repeated physical gate is GREEN, keep the two-phase binder ordering as the H1 repair and remove/reconcile H1-only diagnostic noise that is no longer useful.

**If the hang survives the two-phase ordering change:** do not guess another owner. With runtime activation now deferred, use the existing watchdog plus a diagnostic-only split around Gmail component creation:

```text
beginCreate(context)
setInitialProperties(object, {gmailModel: model})
completeCreate()
```

Preserve required-property/error/cleanup semantics and add one-shot begin/complete markers. This distinguishes object-tree creation from later binding/component-completion work. If the MainThread still disappears into an opaque Qt C++ call, request a native process/thread dump rather than inventing another QML/COM fix.

H1 closes only when Settings and CUSTOM replacement repeatedly recreate both selected displays, no watchdog fires, the process stays responsive, and ordinary Exit terminates cleanly.

One-display MC recreation working remains useful contrast evidence; preserve it in the matrix.

After H1 is GREEN, continue naturally to H2 in this plan. There is no separate H2/H3/H4 execution prompt to treat as competing sequence authority.

### H2 — Media artwork decoded but cannot reach the QML engine provider

**Status: source-proven wiring defect.**

`QuickSceneFactory` registers one `MediaArtworkImageProvider` on the shared `QQmlEngine`. Production `MediaFamilyAdapter`, however, constructs a different `MediaArtworkImageProvider` and injects that private instance into `MediaPresentationModel`.

The model publishes decoded artwork into its private provider and emits an `image://mediaartwork/<identity>` URL. QML resolves that URL against the engine-registered provider, which does not own the image. Runtime logs independently prove source decode succeeds (`decode_ok=True`, real payload bytes), matching the operator's “artwork never loads.”

Required fix: the Media presentation for a Quick scene must publish into the **same provider instance registered on that scene factory's QQmlEngine**. Inject that provider through the existing presentation assembly; do not register duplicate providers or create one per Media card.

Add a cross-layer test that builds Media through the production Quick family assembly and asserts the model's publication is resolvable by the factory's registered provider.

### H3 — retained Reddit URL click has no production opener

**Status: source-proven wiring defect.**

`RedditPresentationModel.admit_url()` is present. `RetainedRedditPresentation` exposes the correct `on_open_requested` seam and its focused tests pass only because tests explicitly inject a callback. Production `RedditFamilyAdapter` constructs `RetainedRedditPresentation` without `on_open_requested`, so `_handle_open_requested()` necessarily returns false after URL admission.

This cleanly explains why Gmail links work but Reddit links do not, including MC where the direct-open mechanism is otherwise simple.

Required fix: connect the retained Reddit semantic action to the existing product-level Reddit opening authority. Preserve the established product distinction:

```text
MC -> direct user-desktop open
SCR -> existing deferred/helper queue authority and normal saver exit
```

Do not recreate helper policy in QML or the family model. Do not let helper readiness block saver teardown.

Add a production-family assembly regression: an admitted retained Reddit row click must reach the injected product opener exactly once; untrusted URL and disabled interaction must remain rejected.

### H4 — Media Play/Pause and seek do not execute; Previous/Next do

**Status: operator-reproducible; routing exists, final command semantics unproven.**

The retained QML signals and Python presentation handlers exist for all four actions. Since Previous/Next work through the same retained card and interaction admission, do not rewrite the QML control strip or generic input path first.

Investigate the narrower GSMTC action boundary:

- record bounded action result telemetry: requested -> submitted -> WinRT result/exception -> reconciliation refresh;
- do not block the GUI waiting for WinRT;
- do not report action success solely because a worker task was queued;
- verify Spotify's real toggle semantics; if `try_toggle_play_pause_async()` is unreliable, compare explicit play/pause operations against the current accepted playback state before choosing a repair;
- verify the timeline/seek units and the boolean result of `try_change_playback_position_async()`.

Previous/Next are the working control group. Preserve their behavior.

### H5 — Spectrum is visually broken when switched to; other modes render, Bubble responsiveness tracked separately

**Status: operator-reproducible; localize before editing.**

Current logs show the mode switch itself is admitted cleanly: old logical runtime joins, the BeatEngine activation generation changes, the logical runtime restarts, `spectrum.frag` loads and the mode is persisted. That does **not** prove Spectrum pixels are correct.

Create a focused mode-switch reality gate that starts from another known-good mode, switches to Spectrum, then proves:

- mode identity is Spectrum through logical -> render snapshot -> retained node;
- Spectrum receives current non-stale authored bar/state data;
- its presentation geometry/uniforms match the committed item;
- the retained node actually draws Spectrum after the switch.

Do not change shared visualizer cadence or Bubble to fix a Spectrum-only failure.

### H6 — context-menu exit responsiveness: instrument, then classify

**Status: operator-visible, cause unknown.**

Add only bounded lifecycle timestamps around:

```text
context action accepted
-> exit signal emitted
-> input admission closed
-> Quick windows hidden/closed for visible response
-> display producers retired
-> worker/process joins
-> QApplication quit
```

If action admission or visible dismissal is delayed, repair the smallest H owner. If visible exit is immediate and only terminal joining is slow, carry the measured tail into J lifecycle/performance acceptance. Do not add arbitrary sleeps or abandon clean joins.

## H runtime observations that are NOT blockers by themselves

### Bubble

Current source-mode evidence after `adcfd96d` is healthy on objective authored/runtime measures:

- retained visualizer `sync_count` reaches the thousands rather than freezing at 1;
- Bubble authored cadence stays about 89.8–89.9 FPS;
- Bubble requested/integrated ratio is `1.000` with zero integration failures.

The operator's later physical observation is stronger than the first run: Bubble can be **barely reactive**, with delayed visible start/stop and very little contraction/expansion. That is a real acceptance failure to preserve, but current authored-cadence/integration evidence still argues against blind tuning. Route it to J as a high-priority fidelity/latency cell with an H-sized conditional: if a bounded check exposes stale playback state, delayed logical/source admission, stale render publication, or another obvious deterministic owner defect, reopen/fix that smallest seam before aesthetic tuning. Do not retune authored Bubble parameters merely to make the symptom disappear.

**Positive physical observation:** Bubble partial/CUSTOM resizing currently works quite well. Preserve that as a provisional J pass/protection target while fixing Spectrum and other parity debt; it does not certify every mode or viewport shape.

### Focus/click flicker and other presentation ugliness

Whole-scene flicker when clicking/focusing a display, black flashes, transition visual flakiness and widget-shell parity are J presentation evidence **unless** instrumentation proves focus is resetting semantic base-image/reveal state. If that deterministic state reset is found, reopen only that owner in H.

## H re-closure gate

H can re-close only when all of the following are true on exact current source:

1. the existing four runtime-reality regressions remain GREEN;
2. dual-display Settings close/recreate succeeds and process remains alive;
3. dual-display CUSTOM Save/Continue close/recreate succeeds and process remains alive;
4. Media artwork visibly resolves from a real decoded runtime snapshot through the engine-registered provider;
5. Reddit admitted URLs reach the correct MC/SCR product opener;
6. Media Play/Pause and seek work on the real provider while Previous/Next remain working;
7. Spectrum survives a real mode switch and visibly renders correctly;
8. context-menu Exit has measured/understood responsiveness with no action-routing failure;
9. process termination leaves no orphaned worker process attributable to an abnormal replacement crash;
10. maintained `h-destination` is rerun once after the bounded fixes and remains GREEN;
11. every unresolved ledger row whose phase includes **H** is either closed with evidence or explicitly carried into J with a recorded reason.

Then run a short source-mode two-display smoke. Only after that smoke is GREEN may I start.

## I residue reconciliation — blocked

I remains intentionally boring source/test/tool residue cleanup after H. Do not use I to absorb these runtime defects and do not restore legacy presentation to satisfy old tests.

When admitted:

- derive exact residue from callers/imports and broad collection;
- preserve/re-home surviving neutral/Quick contracts only;
- delete pure retired-presenter assertions and caller-dead adapters/tools/comments;
- restore meaningful broad-suite authority;
- reconcile `Docs/TestSuite.md`, `Future_Cleanup.md`, `Index.md` and `Spec.md` as needed.

## J acceptance inputs — explicit, not vague parity debt

Follow the existing J decomposition plus:

`Docs/QtQuick_Migration/J_Visual_Parity_Runtime_Acceptance_Addendum_2026-08-30.md`

Mandatory observation ledger:

`Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`

Finishing the current coding prompts does **not** close this ledger. J closure must account for every unresolved physical/visual row.

Named cells now include:

- startup/focus/transition black flash and whole-scene flicker;
- intermittent startup flash that resembles diagnostic/test colour bands; first identify whether real diagnostic pixels are entering the production readiness path or whether this is a lower-level transient;
- actual gentle reveal/fade;
- Media shell/proportions/artwork/header/control-strip parity;
- Gmail row clipping and header/refresh parity;
- Reddit/Gmail/Media logo/header alignment consistency;
- Achievement Pulse icon placement, unlocked-count space and wasted-area removal;
- consistent header border thickness/chrome;
- optional Media `Junk` and `Paused` metadata lines;
- all-five visualizer eyes-on fidelity, with Spectrum switching explicit and Bubble's now-reproducible weak/delayed reactivity tracked separately from raw ~90 Hz cadence; preserve the currently good Bubble partial-resize behavior and do not tune Bubble without owner evidence;
- one visible pointer treatment: retained cursor halo/cursor-shape presentation must not visibly duplicate the OS cursor;
- Media app-volume presentation: preserve the established optional **adjacent/outside** slider behavior; an integrated in-card form may exist only as an explicit optional variant, not as a silent replacement;
- ordinary/non-CUSTOM Media + Visualizer free-space placement: prefer a usable adjacent region when both share a display and space exists; CUSTOM committed geometry wins and may overlap or cross displays;
- retained context submenus must dismiss/switch coherently when the pointer leaves their parent/submenu path; no submenu may remain open indefinitely merely because it was hovered once;
- physical A->B->A focus, mixed refresh/DPR, off/wake, performance tails and clean exit.

## Binding invariants

- One selected physical display owns one standalone `QQuickWindow`, one retained scene and one display runtime/service chain.
- No `QQuickWidget`, second accelerated presenter, hidden QWidget presenter, QRhi/software fallback or screenshot facade.
- Python owns semantic/settings/provider/runtime truth; QML consumes bounded presentation state and emits semantic actions.
- Ordinary family admission resolves capability, instance `enabled` and canonical effective monitor route before construction.
- Visualizer authored cadence remains presentation-independent; the existing display Quick frame pacer is the sole GUI presentation opportunity.
- Transition interruption/replacement remains exactly-once and never uses a black clear as an ownership shortcut.
- Old generation admission closes and logical work joins before scene/window retirement; generation `0` is valid.
- Fallbacks are product-authorized, destination-owned and fail-loud. Deleted legacy presentation is not a fallback.

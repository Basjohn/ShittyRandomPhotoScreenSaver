# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-30 post-cutover audit at pushed `4f33981ef374301d6a66e1651917eb23a2686f8c`

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

### H1 — dual-display Settings/CUSTOM replacement generation dies while screen 1 Media is activating

**Status: characterized as an intermittent main-thread HANG (not a crash); stack-dump watchdog landed; awaiting a captured hang stack. No native owner has been changed.**

Landed at `ae3eda9a`, `6c7ef945`:

- **Source audit result.** The generation lifecycle is clean. `_runtime_generation` increments per replacement (`engine._runtime_generation + 1`), a whole new `DisplayManager` is built on the one app-scoped `ThreadManager`, the three shared Media owners are keyed `("runtime", generation)`, and the destruction barrier retires the old generation's owners before the replacement builds. There is **no cross-generation Python owner reuse**. The failure is native/runtime, not a Python cardinality bug.
- **Instrumentation.** Bounded one-shot `[MEDIA_NATIVE][H1]` breadcrumbs (generation + thread id) at every native boundary (`core/media/media_native_trace.py`): Media family `model_construct`, each lease `lease_attach` + owner `owner_activate`, `retained_item_construct`, GSMTC `winrt_init`, pycaw `core_audio_enumerate` thread, system-mute `mute_endpoint` acquire thread. De-duplicated per `(generation, screen, component, stage)`.
- **Deterministic bar.** `tests/test_media_generation_recreation.py` proves the same-process gen→gen owner lifecycle is clean (old retire, new fresh/distinct, registries return to zero). In `h-destination` (65/65 GREEN).

**Operator run 1 evidence (2026-08-30 13:36, source `4f33981`+instrumentation).** Several Settings/Edit recreations succeeded (gen 0→4 each rebuilt Media fully through `core_audio_enumerate`), then the final `custom_edit` replacement (gen=5) **hung** during screen-1 (LG TV) Media build. Findings:

- It is a **hang, not a crash**: the process lingered and was killed manually (ledger O-004).
- Last breadcrumb: `gen=5 ... component=spotify_volume stage=lease_attach_complete thread=MainThread`. The very next step (`mute_button lease_attach_begin`) never emitted.
- This truncation is **real, not a dropped-log artifact**: the same run wrote the entire 498-object teardown intact; the async log queue (`_LOG_QUEUE_CAPACITY=4096`, `put_nowait` drop-on-full) never saturated; and **no COM call was in flight at the freeze** — the last Core Audio session enumeration fully released ~10 s earlier (13:36:39).
- `mute` is disabled, so `mute_button` never activating its owner is expected (not a defect).
- So the main thread stops between two non-blocking breadcrumbs with **no emitting call to name it** — past what INFO/DEBUG staging can resolve.

**Landed response (`6c7ef945`): stack-dump watchdog.** `core/diagnostics/hang_watchdog.py` arms a `faulthandler` all-thread dump around the single recreation choke point (`_construct_and_start_replacement_runtime`, both `settings` and `custom_edit`), disarmed on success. A healthy replacement finishes in << 1 s; if construction does not return in 20 s it dumps every thread's Python stack to `logs/hang_stacks.log` (and `faulthandler.enable()` prints a native stack if the variant is a crash). Verified silent on success, dumping on stall.

**Operator step (required before any native fix): capture the hang stack.**

1. Run source mode, two displays, and repeat Settings / Edit-save / Edit-cancel / Reset-layout recreations until one **hangs** (it is intermittent — it took several last time).
2. When it wedges, wait ~20 s, then read `logs/hang_stacks.log`: the `MainThread` frame names the exact blocking call, and the io_pool/render frames show any counterpart. Send that dump here.
3. Only then fix that one owner at its boundary (preserve one shared owner per generation and the existing ThreadManager; no new worker/poller/presenter), add the native runtime-shaped smoke, and re-run `h-destination`.

The earlier runs had this shape:

```text
old two-display generation teardown
-> destruction barrier completes normally
-> replacement display initialization starts
-> screen 0 Quick unit completes
-> screen 1 starts family binding
-> Windows GSMTC controller initialized
-> Media shared poll owner/timer created
-> comtypes/Core Audio releases begin
-> process/log ends before screen 1 unit completion
```

CUSTOM evidence: source `747e314`, 04:34:14.  
Settings evidence: source `4f33981`, 04:47:07.

The old generation is not hanging: its destruction barrier completes. Do not redesign Quick retirement from this evidence. The strongest current suspect is replacement-generation Media/native service activation — especially the app-volume/Core Audio lease — because the termination sits on that exact boundary in both runs. This is still a hypothesis, not permission to add arbitrary `CoInitialize` calls.

Required next work:

1. add bounded stage breadcrumbs around Media model construction, each of its three service builds/injections (`media`, `spotify_volume`, `mute_button`), retained-item construction, and each service activation;
2. reproduce dual-display replacement;
3. perform a minimal capability/lease bisect (primary Media vs app-volume vs mute) to identify the actual native owner;
4. fix that owner only;
5. add a repeat-recreation regression/harness that reuses the real process/runtime-generation boundary rather than only constructing a fresh first generation;
6. prove Settings **and** CUSTOM Save/Continue recreate both selected displays and the process remains alive.

One-display MC recreation working is useful contrast evidence; preserve it in the matrix.

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

### H5 — Spectrum is visually broken when switched to; other modes are good

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

The operator is unsure whether Bubble feels slightly less reactive. Preserve that as a J eyes-on comparison; do not retune Bubble without stronger evidence.

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
- actual gentle reveal/fade;
- Media shell/proportions/artwork/header/control-strip parity;
- Gmail row clipping and header/refresh parity;
- Reddit/Gmail/Media logo/header alignment consistency;
- Achievement Pulse icon placement, unlocked-count space and wasted-area removal;
- consistent header border thickness/chrome;
- optional Media `Junk` and `Paused` metadata lines;
- all-five visualizer eyes-on fidelity, with Bubble feel and Spectrum switching explicit; preserve the currently good Bubble partial-resize behavior;
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

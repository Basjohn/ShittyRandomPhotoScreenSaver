# Current Plan — Post-Cutover J+

Last updated: 2026-09-04
Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

## PRE-V5 SETTINGS MIGRATION boundary

`81019d5dd196cc5522ca9041d8773c8f2fa62df3` is the **immediate pre-V5 rollback / comparison boundary**: the last commit before any Visualizer Settings migration began. It is the reference point for before-vs-after Settings self-audits and for rolling back V5-V8 without disturbing the pre-V5/V6 gate fixes. Keep this reference distinct; do not fold it into later V5 work.

## Current checkpoint

The Qt Quick production cutover is complete. This file is now a **live post-cutover plan**, not a migration diary. Completed H/I mechanism history belongs in closure/historical records and must not be recopied here.

Current source truth at this checkpoint:

- The deterministic Visualizer hitch owners already attributed in P0 are closed: diagnostics usage sampling, stable-set Gen2 rescans, first-publish cold import, and analysis/handoff tails. `gc.freeze()` remains the accepted stable-generation policy; post-freeze recreated generations collect normally and the pre-freeze cyclic pin is bounded until shutdown.
- V0-V4 Visualizer authority/dormancy work is complete. The 2026-09-03 audit hole where `logical_frame_capture` eagerly imported all five frame runtimes is fixed through the canonical descriptor seam; warming the common capture chain imports no disabled mode runtime.
- Achievement Pulse core parity is physically accepted; the new bounded recent-badge rail polish awaits eyes-on confirmation. Abandonment Issues is physically accepted. Reddit's remaining time-column tweak is bounded and awaiting eyes-on confirmation.
- Spectrum's explicit pause-to-idle descent and gentle left-to-right idle energy are physically accepted; preserve the mode-owned logical-clock implementation without timers/pollers or generic idle-self-animation.
- Runtime Widget Themes are colour-only schema-v3. Runtime card Glass/Acrylic is rejected/removed and must not return. Settings-window Glass/Acrylic remains valid and separate.
- Settings Theme Foundry and Widget Theme Foundry are current authoring tools. Ordinary Widget Settings now defaults to shared semantic/theme authority for branded headers instead of family-local header palettes; family-specific swatches remain only where a real family-level colour contract still exists.
- Widgets -> General -> **Style Overrides** is the shared ordinary-widget override surface: Card Surface, Card Border, Header Fill, Card Border Width, plus an explicit **Reset All Colours to Theme** action. Family-specific header colour swatches are retired. Media's lone `Show Header Pill` toggle belongs in its normal Appearance bucket, not a special Header Appearance bucket.
- Old per-family colour fields remain readable only as a bounded compatibility bridge until the explicit reset/upgrade horizon is complete. Retired header-button descriptors/load/finalize expectations are removed; only persisted colour-value compatibility remains part of that bridge, not permission for new hidden override authority.

Durable references when mechanism detail is needed:

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`
- `Docs/QtQuick_Migration/Resource_Plateau_Soak_Closure_2026-09-04.md`
- `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md`
- `Docs/Tooling_Audit_2026-09-01.md`
- `Docs/TestSuite.md`
- `Future_Cleanup.md`

## Immediate sequence

1. [SUSPECTED DONE - CHECK] **Finish shared Widget colour-authority cleanup and physical check.** Apply the Style Overrides/header cleanup, run **Reset All Colours to Theme** once on the current profile when desired, and verify Media/Reddit/Gmail/Steam branded headers resolve cohesively from the selected Widget Theme/shared override. No hidden family colour should survive merely because its GUI swatch was removed.
2. **Visualizer recreation-specific delivery quality.** Deterministic steady-state hitch owners are closed and owned-resource plateau is proven (2026-09-04 soak); remaining performance work is generation replacement/re-admission freshness/latency, plus the bounded Windows handle-drift attribution (AWAITING NEW SOAK). Bubble and extreme-tall Spectrum remain co-equal physical oracles. Do not lower cadence, accept stale frames, or damp authored response.
3. **V5-V8 Visualizer Settings rehost.** All four pre-V5/V6 gate items are resolved with tests as of 2026-09-04, including item 4 (Settings-body dormancy): all five modes are lazy in-place via `VisualizerModeBodyHost`, and V6a extracted the shared appearance controls out of Spectrum so Spectrum is lazy too. Remaining: the V7 top-level `Visualizers` tab presentation move (reusing the same host, preserving dormancy).
4. **Theme-switch slowdown + narrow theme fragility audit.** Attribute duplicate QWidget refresh/repolish work first, then audit only real edge contracts: stale wrappers, lazy Settings pages, linked-theme transactions, catalogue/install roots, retained recreation, live failure propagation, and hidden lifetime owners.
5. **J cleanup/optimization/acceptance.** Reconcile stale tests/tools, restore broad-suite signal, finish remaining bounded parity/snap polish, run resource/CPU/GPU ownership passes, then compiled/frozen/installed acceptance.

## User-environment validation gate

Run the maintained destination profile after meaningful current slices:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

Before final J closure also run:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Rules:

- [ ] Classify every red against **current ownership**. Museum/deleted-owner failures are cleanup evidence, not permission to resurrect retired QWidget/GL/polling/fallback architecture.
- [ ] Keep automated green separate from physical acceptance. QML pixels, CUSTOM transitions, frozen paths, topology and real Qt lifetime behavior still require the user environment.
- [ ] Do not weaken the destination profile to make the broad suite prettier.

## Current physical / product validation queue

Status: `[ ]` open, `[~]` implemented/source-proven but awaiting real-app validation, `[x]` physically/conclusively accepted.

- [~] **Shared Widget Style Overrides / reset.** Card Surface, Card Border and Header Fill must apply coherently through Widget Theme `Custom`; `Reset All Colours to Theme` must remove ordinary family colour/alpha overrides only, without touching Visualizer-authored colours, geometry, fonts, shadows, providers or feature toggles. Media `Show Header Pill` sits in Media -> Appearance. No family Header Appearance colour bucket remains.
- [~] **Reddit time rail parity.** `AGO` is a rigid aligned column shifted **14 authored px left from the original position** while the age-value column and title start remain fixed. Validate short/long ages and title spacing physically.
- [~] **Global CUSTOM dormancy.** Stacking and Media<->Visualizer adjacency stay off for persisted/effective CUSTOM, live Edit Layout, and number-key saved-layout load/rebuild.
- [~] **Media<->Visualizer ordinary adjacency + wheel routing.** Only outside global CUSTOM. Whole Media and ordinary Visualizer may forward discrete volume steps through the existing app-volume owner; CUSTOM resize-wheel ownership wins absolutely.
- [~] **Media external app-volume side selection.** When the app-volume rail is external, keep it on the side of Media with more display space: Media on the right half -> rail on the left; Media on the left half -> rail on the right. The retained position drives this automatically in CUSTOM too; keep one accessory lane/lifecycle owner and no polling/timer/persisted side authority.
- [~] **CUSTOM alignment-guide restoration.** During Edit Layout, peer-edge snaps publish gentle-blue transient guides above retained widgets; display/peer centering publishes gentle-purple guides below retained widgets; the absolute display-centre cross is stronger than the ordinary grid but remains below widgets. Transient guides clear on release/cancel/new drag and reuse the existing snap-resolution metadata (no second geometry authority/cadence).
- [~] **Context Menu interaction edges.** Settings click-through suppression and submenu crossing use event/deadline ownership only; no sticky lifetime, timer or poller.
- [~] **Gmail action-menu click-through guard.** Three-dot action activation and pointer-dismissal arm the existing shared monotonic pointer guard before the retained popup disappears, so a passive-grab release cannot also open the Gmail row underneath. No timer, poller or new pointer cadence; physically validate action-over-row and outside-dismiss-over-row.
- [ ] **MusicBee Home play/pause double-toggle — evidence first.** Operator sees a rapid play-then-pause only with MusicBee when Home is also remapped to Play/Pause by PowerToys; Spotify does not reproduce. Do not alter shared Media transport yet. A later short repro should distinguish duplicate Home/autorepeat from the external PowerToys/system-media injection path using existing runtime/media-command logs, then apply only a proven narrow fix.
- [~] **Settings Theme live recreation.** Repeated Settings recreation and Glass/Acrylic switching must not reintroduce stale `SettingsDialog` wrapper failures; live renderer failures must still propagate transactionally.
- [~] **Bidirectional linked-theme UX.** Locked Settings/Widget theme selection uses stable IDs in both directions and never implicitly unlocks. Widget `Custom` remains Independent-only.
- [~] **Theme authoring tools physical smoke.** Theme Foundry's simplified Everyday/All Roles workflow and Widget Theme Foundry's sparse semantic editor must open/save/strict-reload correctly in the real PySide6 environment.
- [~] **Media artwork/header alignment.** Preserve the accepted narrow artwork width/crop while extending its height upward so the artwork border aligns with the branded-header top; lower boundary remains unchanged.
- [~] **Visualizer frame visible-stroke scaling.** CUSTOM resize/screen-fit/cross-display reprojection must retain bounded scale-aware card-border thickness and must not compound a previously reduced border toward subpixel invisibility.
- [x] **Non-CUSTOM smart stacking collision solver.** Pathological overlap case physically accepted; preserve deterministic spill and zero steady-state cadence cost.
- [~] **Achievement Pulse badge rail polish.** Core parity remains accepted; the recent-achievement badge now starts closer to the smaller unlock text and moves right only when rendered text needs clearance. Recheck this bounded rail tweak physically.
- [x] **Steam Abandonment Issues presentation.** Source-audited and physically accepted; preserve unless a shared semantic fix genuinely applies.
- [x] **Windows GSMTC teardown / native fault capture.** Latest both-display evidence shows same-affinity GSMTC teardown, no `0x8001010e`, bounded clean native-fault capture and clean QML shutdown.
- [~] **Media runtime-provider failover must retarget the app-volume owner.** 2026-09-04 follow-up logs proved Firefox browser GSMTC acquisition works once `media.hardwaremediakeys.enabled = true` (opaque Firefox AUMID `308046B0AF4A39CB` selected successfully). The remaining volume-rail hole was internal: Media runtime failover changed transport/artwork provider but did not retarget the already-attached app-volume owner, so a `spotify_browser` owner could remain unsupported after failover to desktop Spotify (and the reverse could retain the wrong Core Audio target). The retained Media model now forwards every accepted runtime provider change to the existing volume service before the subsequent exact browser-source callback. Await one physical browser<->desktop failover check; no polling/process scraping/fuzzy fallback added.

## Visualizer delivery-quality tranche

The accepted authored chain remains:

```text
one shared BeatEngine
-> one persistent serial visualizer.audio_analysis lane
-> one sole VisualizerLogicalRuntime authored cadence
-> one active mode-owned frame runtime
-> immutable latest publication
-> retained Quick synchronization
-> one lazy active mode renderer inside the display QQuickWindow
```

Closed evidence does not need re-investigation without a new symptom:

- [x] diagnostics usage sampler attribution/partitioning;
- [x] stable-set Gen2 GC attribution and `gc.freeze()` lifecycle validation;
- [x] first-publish cold-import relocation, with V4 dormancy hole corrected at the canonical descriptor seam;
- [x] analysis/handoff tails closed as not a visible steady-state owner.
- [x] resource plateau for owned resources — the 2026-09-04 ~7h53m soak (`logs/evidence_chest/09_04_soak`) proves non-accumulation across RSS/USS/private commit/VRAM/threads/tracked+GL resources/shm/task lanes/logging, with clean topology retire+restore and large downward RAM reclamation. Only a bounded Windows handle drift remains open (below). See `Docs/QtQuick_Migration/Resource_Plateau_Soak_Closure_2026-09-04.md`.

Still live:

- [ ] **Recreation/re-admission latency and freshness.** Reduce replacement gaps without weakening generation/activation fencing or serving stale state.
  - E1 (freshness admission) **physically green** (2026-09-03 eyes-on): commit-seq watermark on the existing fence, armed on warm re-entry only (cold start unchanged). No stale-energy flash / no black screen; ~single-digit-ms continuity cost. Do not revisit without new evidence. Commit 5fd2fbde; tests/test_visualizer_recreation_freshness.py.
  - E2 (fresh source -> retained presentation) **attributed via instrumented run (2026-09-04); presentation path exonerated.** `kind=recreation`/`playback` T3..T6 split (commit 615833cf) shows: T3==T5 always (logical path instant); **recreation T3->T6 med ~4 ms (max 16)** — the O(1) bridge + ~90 Hz pacer are healthy, NOT the ~70-75 ms owner. The earlier "~70-75 ms recreation" was **warm-resume**, dominated by **capture wake** (edge->T3 med ~66 ms — audio pipeline first fresh frame after `engine.wake()`), which is upstream of fresh-source availability. Run carried `cpu_main_pct ~80-108 %` (main-thread saturated) with only 1 startup dt spike, so resume maxima (edge->T3 162 / T3->T6 63) are load/`--usage` contention, not architecture. **No presentation-path fix warranted.** Capture-wake lane **audited -> attributed-not-reducible**: `wake()` no-ops on a warm resume (restarts only when stale), the analysis lane keeps up inline (`rejected_busy=0`, `completed==published`), so the ~66 ms is inherent OS audio-capture latency (WASAPI shared-mode block + stream latency) delivering the first *post-edge* frame, plus this run's `cpu_main ~80-108 %` contention. Not safely reducible without a user-facing `audio_block_size` latency/CPU tradeoff or re-opening first-frame-poison risk (forbidden); E1 already makes the window quiet-not-stale. Minor ~29 ms resume sync + unmeasured T6->T7 paint are load/optional-only. See attribution doc lead E2 + capture-wake audit.
- [x] **Gen2 GC pre-freeze race (lead B follow-up) — physically validated (2026-09-04).** First expensive gen2 (~124 ms) could land just before the fixed 45 s freeze under realistic load. Fixed by deferring only the gen2 trigger during warmup (×10) and restoring active thresholds at freeze — contract-neutral (freeze pins the same set). Run evidence: warmup applied at start, `Froze 133802` at ~45 s with "restored active", and the **only** gen2 all run was **post-freeze** (10.85 ms) — no pre-freeze gen2 raced the freeze. Commit 258e0a23; tests/test_runtime_perf_policy_contracts.py.
- [ ] **Pacer/UI/logging attribution only if the physical oracle still shows gaps.** Async writer lag is not automatically caller/presentation latency.
- [ ] **[AWAITING NEW SOAK] Windows handle drift.** Owned-resource plateau is proven (moved to closed evidence above). The single residual is `handles_app` drifting ~+9/hour across the stable single-display window while every owned resource stays flat — bounded, not attributed. Source-first pass exonerated the psutil path (handles are cached on long-lived `Process` objects) and found the PDH GPU/VRAM rebuild cadence only loosely correlated (~0.68 handle/rebuild, 80 rebuilds); no owner was guessed and no lifetime architecture changed. Next soak discriminators (no new runtime cadence): the new `handles_main` split localizes main vs image-worker; a `--usage`-off run tests PDH/perflib self-attribution; existing `gpu_status=warming` samples give the rebuild timeline. No new soak expected today. See closure doc.
- [ ] **Physical Bubble + extreme-tall Spectrum acceptance after remaining latency work.** Preserve R-69/R-76 authored response. (Soak ran Bubble healthily for hours with no delivery degradation; final verdict still requires eyes-on.)

Never solve any of these by reducing logical cadence, adding per-mode clocks/QML timers/catch-up FIFOs/paint acknowledgements, increasing source age, or globally compressing Bubble/Spectrum authored response.

## HARD pre-V5/V6 Visualizer Settings gate

Resolve these **immediately before** moving the Settings presentation. Do not start the rehost and promise to fix them afterward.

1. [x] **Startup substitution ordering.** Fixed 2026-09-04: `_construct_quick_visualizer_owner_on` now substitutes a disabled/stale persisted mode on the section via the pure `resolve_effective_visualizer_section` **before** activation/model resolution; the old `model.mode` field-patch (mode-A state on mode B) is removed. Behaviour-neutral today (all modes enabled). Tests: `tests/test_visualizer_mode_enable_resolver.py`.
2. [x] **Deepest request admission.** Fixed 2026-09-04: `_request_quick_visualizer_mode()` itself rejects a canonical, dev-active but disabled mode for runtime/UI requests (before any activation build) — no silent route/re-enable, no second enable authority. Startup substitution stays at the startup resolver (item 1). Tests: `tests/test_visualizer_request_admission.py`.
3. [x] **Durable no-settings-lost coverage.** Locked 2026-09-04: a partial `enabled_modes` set and a disabled mode's local state both survive `from_mapping -> to_dict -> from_settings`; `enabled_modes` round-trips canonically ordered and additive (never reset). Test: `tests/test_visualizer_settings_plumbing.py::TestSettingsModelPlumbing::test_enabled_modes_and_disabled_mode_state_survive_round_trip`. Re-verify Settings/app *recreation* survival with eyes-on at rehost time.
4. [x] **Settings-body dormancy — SATISFIED in-place (V6a, 2026-09-04).** Runtime dormancy was already proven; the lazy Settings-body ownership contract (`core/settings/visualizer_mode_body_host.py::VisualizerModeBodyHost`) is proven and now drives the live Widgets-hosted Visualizers UI for **all five modes**. No mode Settings body is constructed when Settings opens; only the active/selected mode constructs; each hydrates once on fresh construction; a cached reselect never rebuilds/re-hydrates (unsaved edits survive); a full reload re-hydrates built bodies; missing-body construction fails loud + uncached. Spectrum is no longer an exception (V6a below extracted the shared controls out of it). The remaining V7 top-level-tab presentation move will reuse the same mechanism and must preserve this dormancy. Tests: `tests/test_visualizer_settings_body_dormancy.py`, `tests/test_visualizer_settings_lazy_bodies.py`.

Then perform V5-V8:

- [~] **V5 opening slice landed (2026-09-04):** canonical lazy Settings-body host + descriptor Settings-builder seam + pill model + dormancy proof (10 tests). Qt-free mechanism only — the live dialog is NOT yet rewired. Do not fold the mechanical rehost into that slice.
- [x] **V5b live-in-place lazy integration (construction flip DONE, 2026-09-04).** The live Widgets-hosted Visualizers UI now runs through `VisualizerModeBodyHost` with real per-mode laziness, no top-level tab / pixel move. **Decision (user):** Spectrum stays **eagerly built** as an explicit *temporary V5b Settings-only exception* — the genuinely shared Bar Fill/Border colour + Border Opacity controls are physically nested inside Spectrum's Appearance bucket (`spectrum_builder.py`), so extracting them is a V6 pixel move; no reclassification / proxy ownership. Oscilloscope / Sine / Bubble / DevCurve are constructed on first selection and hydrated ONCE at construction (`_hydrate_visualizer_mode_body`, from `_vis_loaded_config`); reselecting a cached body never rebuilds or re-hydrates it, so unsaved edits survive. Building a new mode hydrates only that mode's technical controls (`load_per_mode_technical_controls(only_mode=...)`), never clobbering another built mode's edits. Landed hazards 2/6/7/8 earlier; host gained `ensure`/`adopt`; the combo remains the single selection authority (`ensure` never sets selection). Proof: `tests/test_visualizer_settings_lazy_bodies.py` (A/B/F/G bar + no-rebuild/no-rehydrate + technical-edit + save-with-unbuilt) plus reconciled `test_widgets_tab.py` / `test_visualizer_presets.py` (select-then-assert for lazy bodies). No timers/pollers/workers; no top-level tab yet. **Gate 4 remains PARTIAL** — it may not close while Spectrum is eagerly constructed.
- [x] **V6a shared-control extraction + Spectrum lazy (DONE, 2026-09-04).** The genuinely shared Bar Fill/Border colour + Border Opacity controls are now owned by `ui/tabs/media/shared_appearance_controls.py`, built eagerly and independent of every mode body; Spectrum places (does not recreate) the exact same row widgets in its Appearance bucket, so presentation/order/defaults/keys/semantics/pixels are unchanged. Spectrum is now lazy under the identical `VisualizerModeBodyHost` construct/cache/hydrate contract as the other four modes (no eager build, no `adopt`, its loader moved to the hydrate dispatch). Save gates the Spectrum-owned ghost keys and the per-mode collect on the body being built (no fallback synthesis, no crash when unbuilt); the mode combo builds-before-saves. New regressions in `tests/test_visualizer_settings_lazy_bodies.py`: Spectrum-lazy, shared-controls-survive-Spectrum-unbuilt, unsaved-Spectrum-edit-survives-switch, save-while-Spectrum-unbuilt. This closes gate item 4 in-place.
- [ ] **V7 top-level `Visualizers` tab (pixel move):** rehost the shared SETUP controls + per-mode builders/preset sliders/Custom UI into a top-level `Visualizers` tab with `SETUP` plus enabled-mode pills, driven by `VisualizerModeBodyHost`; retire the Widgets-hosted `build_visualizers_ui`. Extract the WidgetsTab-free builder context first; do not rewrite behavior, do not duplicate controls; preserve the V6a dormancy.
- [ ] If Media is disabled at the Widgets capability/setup level, disable the Visualizers tab with tooltip **`Enable Media In Widgets`**. Do not create a second Media activation owner.
- [ ] Prove future-mode addition needs one canonical descriptor plus isolated runtime/renderer/Settings modules and focused tests, not unrelated five-way switch edits.
- [ ] Perform a before-vs-after Settings self-audit: controls, curated presets, Custom transitions, disabled-mode persistence, re-enable restore, selected/effective mode coherence, lazy page saving, Media-disabled state preservation, and no new timers/pollers/workers/fallback owners.

## Theme-system edge audit

Keep this narrow. Do **not** restart a semantic-literal inventory or another material experiment.

- [ ] stale Qt wrappers / QObject lifetime edges;
- [ ] lazy Settings-page construction/recreation;
- [ ] linked-theme transaction edges in both directions;
- [ ] retained-runtime recreation/generation handoff;
- [ ] theme catalogue/path/build/install boundaries;
- [ ] live renderer failures are not swallowed;
- [ ] no hidden polling, fallback or background lifetime owners.

## Residual cleanup / test truth

Exact deletion/test ledgers belong in `Future_Cleanup.md`, `Docs/TestSuite.md` and the tooling audit. Current Plan keeps only the live outcomes:

- [ ] Reconcile skipped/stale tests against current Quick ownership; migrate surviving behavioral assertions and delete fossils rather than resurrecting dead presenters.
- [ ] Reconcile remaining old Media Center physical-window tests against current Quick role/policy ownership.
- [ ] Re-run caller/import searches before each deletion batch; no compatibility fallback may silently recreate a second presenter/analysis/polling owner.
- [ ] Restore the broad whole-tree gate to useful signal without weakening destination authority.
- [ ] Retire migration-only benchmark/spike tools after final J physical/installed acceptance proves they have no remaining evidence job.

## Required optimization tranche before J closure

H/P0 proved architecture and removed known deterministic stalls; J still requires profiling the actual migrated product.

- [ ] **CPU/GPU/QML pass.** Frame tails, overdraw/offscreen work, binding churn, hidden animations, unnecessary invalidation and duplicate work.
- [ ] **Ownership/contention pass.** Remaining timers/pollers, worker/thread cardinality, locks/queues and duplicate event ownership. Prefer event-driven ownership and fewer owners over reduced authored rates.
- [ ] **Allocation/lifetime pass.** Measure current allocation churn and GC/lifetime tails before touching `RuntimeGCPolicy`; preserve the proven stable-generation freeze contract unless new evidence requires change. The caller-dead pre-Quick `GCController` facade is cleanup residue, not runtime authority.
- [x] **Resource plateau (owned resources).** Proven by the 2026-09-04 ~7h53m soak across RSS/USS/private commit/VRAM/threads/caches/workers/retained resources with clean topology recreation. Only the bounded Windows handle drift remains open under the delivery-quality tranche (AWAITING NEW SOAK). See `Docs/QtQuick_Migration/Resource_Plateau_Soak_Closure_2026-09-04.md`.
- [ ] **Quality recheck.** Modest and representative-heavy runs must preserve cadence, freshness, authored amplitude/motion and visible fidelity.

## Final J acceptance obligations

- [ ] Finish any remaining bounded family visual-parity work against the pre/post migration oracle where useful.
- [ ] Physically validate the restored CUSTOM alignment/snap-guide lines and complete remaining bounded presentation polish.
- [ ] Complete compiled/frozen/installed 1/2/N-display, DPR, topology and Media Center/screensaver acceptance.
- [ ] Reconcile historical-bug/migration records worth preserving after the three live planning authorities are clean.
- [ ] Run final maintained destination + broad-suite gates and reconcile source/docs/tests before J closes.

## Golden guardrails

### Visualizer fidelity / scaling

R-69 remains binding. Bubble's restored scaling/reactivity contract is the golden reference; extreme CUSTOM geometry must never be fixed by globally reducing head radius, authored reaction amplitude, motion, Ghost/history displacement or adding a second viewport/domain compensation. R-76 tall-Spectrum response is likewise protected.

### CUSTOM is global layout mode

The first widget entering global CUSTOM disables authored stacking/adjacency globally, including number-key saved-layout loading. Visualizer preset `Custom` is a separate concept.

### Media ownership

Do not restore fast Media polling or process-probe fallbacks. GSMTC/event ownership is primary; slow reconciliation/watchdog remains bounded degraded-path coverage. Visualizer consumes Media admission but never acquires a second Media owner.

### Performance admission

Freshness/reactivity and latency-tail quality outrank prettier aggregate counters. No performance change may silently lower authored quality. Use `Docs/Guardrails/Performance_Optimization_Contract.md`.

## Authority order

```text
exact source / exact test tree
-> Current_Plan.md
-> Spec.md
-> Docs/Contracts.md
-> focused guardrail / decomposition docs
-> Docs/TestSuite.md / Future_Cleanup.md
-> physical/log evidence
-> historical records for mechanism/failed-method lessons
```

Historical documents preserve what happened; they do not override current owner maps. Current source must also not erase a binding historical lesson merely because a shortcut looks locally cleaner.

# Current Plan — Post-Cutover J+

Last updated: 2026-09-03
Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

## Current checkpoint

The Qt Quick production cutover is complete. This file is now a **live post-cutover plan**, not a migration diary. Completed H/I mechanism history belongs in closure/historical records and must not be recopied here.

Current source truth at this checkpoint:

- The deterministic Visualizer hitch owners already attributed in P0 are closed: diagnostics usage sampling, stable-set Gen2 rescans, first-publish cold import, and analysis/handoff tails. `gc.freeze()` remains the accepted stable-generation policy; post-freeze recreated generations collect normally and the pre-freeze cyclic pin is bounded until shutdown.
- V0-V4 Visualizer authority/dormancy work is complete. The 2026-09-03 audit hole where `logical_frame_capture` eagerly imported all five frame runtimes is fixed through the canonical descriptor seam; warming the common capture chain imports no disabled mode runtime.
- Achievement Pulse core parity is physically accepted; the new bounded recent-badge rail polish awaits eyes-on confirmation. Abandonment Issues remains visually accepted/pristine. Reddit's remaining time-column tweak is bounded and awaiting eyes-on confirmation.
- Runtime Widget Themes are colour-only schema-v3. Runtime card Glass/Acrylic is rejected/removed and must not return. Settings-window Glass/Acrylic remains valid and separate.
- Settings Theme Foundry and Widget Theme Foundry are current authoring tools. Ordinary Widget Settings now defaults to shared semantic/theme authority for branded headers instead of family-local header palettes; family-specific swatches remain only where a real family-level colour contract still exists.
- Widgets -> General -> **Style Overrides** is the shared ordinary-widget override surface: Card Surface, Card Border, Header Fill, Card Border Width, plus an explicit **Reset All Colours to Theme** action. Family-specific header colour swatches are retired. Media's lone `Show Header Pill` toggle belongs in its normal Appearance bucket, not a special Header Appearance bucket.
- Old per-family colour fields remain readable only as a bounded compatibility bridge until the explicit reset/upgrade horizon is complete. Retired header-button descriptors/load/finalize expectations are removed; only persisted colour-value compatibility remains part of that bridge, not permission for new hidden override authority.

Durable references when mechanism detail is needed:

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`
- `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md`
- `Docs/Tooling_Audit_2026-09-01.md`
- `Docs/TestSuite.md`
- `Future_Cleanup.md`

## Immediate sequence

1. **Finish shared Widget colour-authority cleanup and physical check.** Apply the Style Overrides/header cleanup, run **Reset All Colours to Theme** once on the current profile when desired, and verify Media/Reddit/Gmail/Steam branded headers resolve cohesively from the selected Widget Theme/shared override. No hidden family colour should survive merely because its GUI swatch was removed.
2. **Weather parity.** Weather is the next substantial widget visual target. Use current Quick source and the pre-migration visual oracle; do not compensate for theme defects with family-local styling hacks.
3. **Visualizer recreation-specific delivery quality.** Deterministic steady-state hitch owners are closed; remaining performance work is generation replacement/re-admission freshness/latency, then resource plateau. Bubble and extreme-tall Spectrum remain co-equal physical oracles. Do not lower cadence, accept stale frames, or damp authored response.
4. **V5-V8 Visualizer Settings rehost.** Only after the hard pre-V5/V6 gate below is satisfied: deepest enabled-mode admission, correct startup substitution ordering, durable no-settings-lost coverage, and Settings-body dormancy.
5. **Theme-switch slowdown + narrow theme fragility audit.** Attribute duplicate QWidget refresh/repolish work first, then audit only real edge contracts: stale wrappers, lazy Settings pages, linked-theme transactions, catalogue/install roots, retained recreation, live failure propagation, and hidden lifetime owners.
6. **J cleanup/optimization/acceptance.** Reconcile stale tests/tools, restore broad-suite signal, finish remaining bounded parity/snap polish, run resource/CPU/GPU ownership passes, then compiled/frozen/installed acceptance.

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
- [ ] **Weather parity.** Current presentation is not accepted; perform a source-first visual pass rather than theme compensation.
- [~] **Global CUSTOM dormancy.** Stacking and Media<->Visualizer adjacency stay off for persisted/effective CUSTOM, live Edit Layout, and number-key saved-layout load/rebuild.
- [~] **Media<->Visualizer ordinary adjacency + wheel routing.** Only outside global CUSTOM. Whole Media and ordinary Visualizer may forward discrete volume steps through the existing app-volume owner; CUSTOM resize-wheel ownership wins absolutely.
- [~] **Context Menu interaction edges.** Settings click-through suppression and submenu crossing use event/deadline ownership only; no sticky lifetime, timer or poller.
- [~] **Settings Theme live recreation.** Repeated Settings recreation and Glass/Acrylic switching must not reintroduce stale `SettingsDialog` wrapper failures; live renderer failures must still propagate transactionally.
- [~] **Bidirectional linked-theme UX.** Locked Settings/Widget theme selection uses stable IDs in both directions and never implicitly unlocks. Widget `Custom` remains Independent-only.
- [~] **Theme authoring tools physical smoke.** Theme Foundry's simplified Everyday/All Roles workflow and Widget Theme Foundry's sparse semantic editor must open/save/strict-reload correctly in the real PySide6 environment.
- [~] **Media artwork/metadata fades.** Shared artwork fade and retained metadata old->new crossfade are event-driven and source-owned; physically validate rapid track skipping plus optional Album visibility without provider-delay, polling or duplicate cadence.
- [~] **Media artwork/header alignment.** Preserve the accepted narrow artwork width/crop while extending its height upward so the artwork border aligns with the branded-header top; lower boundary remains unchanged.
- [~] **Visualizer frame visible-stroke scaling.** CUSTOM resize/screen-fit/cross-display reprojection must retain bounded scale-aware card-border thickness and must not compound a previously reduced border toward subpixel invisibility.
- [x] **Non-CUSTOM smart stacking collision solver.** Pathological overlap case physically accepted; preserve deterministic spill and zero steady-state cadence cost.
- [~] **Achievement Pulse badge rail polish.** Core parity remains accepted; the recent-achievement badge now starts closer to the smaller unlock text and moves right only when rendered text needs clearance. Recheck this bounded rail tweak physically.
- [x] **Steam Abandonment Issues presentation.** Source-audited and physically accepted; preserve unless a shared semantic fix genuinely applies.
- [x] **Windows GSMTC teardown / native fault capture.** Latest both-display evidence shows same-affinity GSMTC teardown, no `0x8001010e`, bounded clean native-fault capture and clean QML shutdown.

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

Still live:

- [ ] **Recreation/re-admission latency and freshness.** Reduce replacement gaps without weakening generation/activation fencing or serving stale state.
  - E1 (freshness admission) **physically green** (2026-09-03 eyes-on): commit-seq watermark on the existing fence, armed on warm re-entry only (cold start unchanged). No stale-energy flash / no black screen; ~single-digit-ms continuity cost. Do not revisit without new evidence. Commit 5fd2fbde; tests/test_visualizer_recreation_freshness.py.
  - E2 (fresh source -> retained presentation, ~70-75 ms typ. on recreation) **attributed + instrumented, owner not yet pinned**: source path mapped (logical->mailbox->pacer sync_present->bridge publish[T6]->window.update->updatePaintNode[T7]); pacer is prompt, bridge is O(1), the activation fade is opacity-only (does not gate T6) — no avoidable wait found in source. Added diagnostics-only `kind=recreation` T3..T6 markers (commit 615833cf) so a --viz run splits the gap into fence/logical/sync-bridge and pins the owner (identity-alignment vs presentation-resolve vs first-publish). Fades stay protected (gentler/longer ok, shorter not).
- [x] **Gen2 GC pre-freeze race (lead B follow-up).** First expensive gen2 (~124 ms) could land just before the fixed 45 s freeze under realistic load. Fixed by deferring only the gen2 trigger during warmup (×10) and restoring active thresholds at freeze — contract-neutral (freeze pins the same set). Commit 258e0a23; tests/test_runtime_perf_policy_contracts.py. **Physical acceptance owed** (no >100 ms pre-freeze gen2; post-freeze cadence/memory match prior good runs).
- [ ] **Pacer/UI/logging attribution only if the physical oracle still shows gaps.** Async writer lag is not automatically caller/presentation latency.
- [ ] **Resource plateau.** Soak recreation/topology changes and track RSS/USS, VRAM, threads, handles, caches/workers and retained resources.
- [ ] **Physical Bubble + extreme-tall Spectrum acceptance after remaining latency work.** Preserve R-69/R-76 authored response.

Never solve any of these by reducing logical cadence, adding per-mode clocks/QML timers/catch-up FIFOs/paint acknowledgements, increasing source age, or globally compressing Bubble/Spectrum authored response.

## HARD pre-V5/V6 Visualizer Settings gate

Resolve these **immediately before** moving the Settings presentation. Do not start the rehost and promise to fix them afterward.

1. **Startup substitution ordering.** Resolve the effective enabled target mode before final activation/model payload resolution; re-enter the canonical resolver for the substitute rather than field-patching mode A state onto mode B.
2. **Deepest request admission.** `_request_quick_visualizer_mode()` must itself reject an explicitly requested disabled mode. Startup/stale persisted selection may deterministically substitute an enabled mode with an explicit log; normal runtime/UI requests may not silently route to or re-enable a disabled mode.
3. **Durable no-settings-lost coverage.** All existing Visualizer fields, mode presets, preset indices, mode-local Custom state and disabled-mode state survive load/model/save and Settings/app recreation. `enabled_modes` remains additive only.
4. **Settings-body dormancy.** Runtime dormancy is already proven; the future top-level Visualizers tab must also avoid constructing disabled mode Settings bodies while preserving their persisted state.

Then perform V5-V8:

- [ ] Rehost existing Visualizer builders/preset sliders/Custom UI into a top-level `Visualizers` tab with `SETUP` plus enabled-mode pills. Rehost; do not rewrite behavior.
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
- [ ] **Resource plateau.** Soak recreation/topology changes and prove non-accumulation across RSS/USS, VRAM, threads, handles, caches/workers and retained resources.
- [ ] **Quality recheck.** Modest and representative-heavy runs must preserve cadence, freshness, authored amplitude/motion and visible fidelity.

## Final J acceptance obligations

- [ ] Finish Weather and any remaining bounded family visual-parity work against the pre/post migration oracle where useful.
- [ ] Complete remaining alignment/snap-guide and bounded presentation polish.
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

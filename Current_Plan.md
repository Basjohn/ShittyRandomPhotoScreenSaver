# Current Plan — Post-Cutover J+

Last updated: 2026-09-05
Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

## PRE-V5 SETTINGS MIGRATION boundary

`81019d5dd196cc5522ca9041d8773c8f2fa62df3` is the **immediate pre-V5 rollback / comparison boundary**: the last commit before any Visualizer Settings migration began. It is the reference point for before-vs-after Settings self-audits and for rolling back V5-V8 without disturbing the pre-V5/V6 gate fixes. Keep this reference distinct; do not fold it into later V5 work.

## Current checkpoint

The Qt Quick production cutover is complete. This file is now a **live post-cutover plan**, not a migration diary. Completed H/I mechanism history belongs in closure/historical records and must not be recopied here.

Current source truth at this checkpoint:

- **Current supplied/pushed authority for this work slice:** `ed1cd8a18d94d6ded95907d1eb17fa300ce21047` (`main`). The attached clean GODZIP at this head is the source boundary; the present assistant slice is uncommitted on top of it.
- The deterministic Visualizer hitch owners already attributed in P0 are closed: diagnostics usage sampling, stable-set Gen2 rescans, first-publish cold import, and analysis/handoff tails. `gc.freeze()` remains the accepted stable-generation policy; post-freeze recreated generations collect normally and the pre-freeze cyclic pin is bounded until shutdown. The 2026-09-05 post-V7 Bubble run re-confirmed that the optimized code is still active: the usage sampler retains the every-8th heavy-enumeration partition and the run recorded **zero Gen2 collections** after the one-shot freeze path. Do not reopen GC or the light `--usage` path without contradictory evidence; the known diagnostics-only heavy `--usage` sample remains a separate bounded perturbation.
- The supplied 2026-09-05 operator logs do **not** show a broad performance/native regression: native-fault capture closed cleanly, both hang watchdogs armed without firing, logging reported no drops/writer errors, and GC remained free of the old Gen2-rescan pathology. The two crashes are lifecycle-local: slot load timed out with only `QuickDisplayVisualizerOwner` retained after earlier cross-display churn, and Save after a successful display hop failed because target teardown encountered `Quick frame pacer is closed`. Both trace to the same split display-owner defect rather than slot-schema/legacy geometry corruption.
- The focused V7/Visualizer acceptance cluster is now **277 passed, 1 skipped, 0 failed** on the user system after test-only reconciliation. Three retired `vis_mode_combo` fossils were deleted; fourteen stale tests were rewritten against current ownership; five genuinely unique pre-V7 invariants were migrated into `test_visualizer_settings_lazy_bodies.py`; thirty-five orphaned WidgetsTab visualizer tests and the obsolete `test_sine_line4_builder_integration.py` module were removed. No production code was changed to obtain that green.
- V0-V4 Visualizer authority/dormancy work is complete. The 2026-09-03 audit hole where `logical_frame_capture` eagerly imported all five frame runtimes is fixed through the canonical descriptor seam; warming the common capture chain imports no disabled mode runtime.
- Achievement Pulse core parity is physically accepted; the new bounded recent-badge rail polish awaits eyes-on confirmation. Abandonment Issues is physically accepted. Reddit's remaining time-column tweak is bounded and awaiting eyes-on confirmation.
- Spectrum's explicit pause-to-idle descent and gentle left-to-right idle energy are physically accepted; preserve the mode-owned logical-clock implementation without timers/pollers or generic idle-self-animation.
- Runtime Widget Themes are colour-only schema-v3. Runtime card Glass/Acrylic is rejected/removed and must not return. Settings-window Glass/Acrylic remains valid and separate.
- Settings Theme Foundry and Widget Theme Foundry are current authoring tools. Ordinary Widget Settings now defaults to shared semantic/theme authority for branded headers instead of family-local header palettes; family-specific swatches remain only where a real family-level colour contract still exists.
- Widgets -> General -> **Style Overrides** is the shared ordinary-widget override surface: Card Surface, Card Border, Header Fill, Card Border Width, plus an explicit **Reset All Colours to Theme** action. Family-specific header colour swatches are retired. Media's lone `Show Header Pill` toggle belongs in its normal Appearance bucket, not a special Header Appearance bucket.
- Old per-family colour fields remain readable only as a bounded compatibility bridge until the explicit reset/upgrade horizon is complete. Retired header-button descriptors/load/finalize expectations are removed; only persisted colour-value compatibility remains part of that bridge, not permission for new hidden override authority.
- Repository text normalization is now explicit through `.gitattributes`: authored source/config/docs use LF, Windows command/installer entry points use CRLF, and compiled/media/font/archive/database assets are `-text`. This checkpoint accepts the newline normalization already present in this interrupted slice rather than reconstructing mixed historical endings; do not perform unrelated whole-tree rewrites merely to normalize existing files.

Durable references when mechanism detail is needed:

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`
- `Docs/QtQuick_Migration/Resource_Plateau_Soak_Closure_2026-09-04.md`
- `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md`
- `Docs/Tooling_Audit_2026-09-01.md`
- `Docs/TestSuite.md`
- `Future_Cleanup.md`

## Immediate sequence

Operator-activated `Future_Work.md` implementation is sequenced separately in `FWPlan.md`; preserve the unrelated
work and physical/log validation below.

- [x] **Visualizer live Edit/transfer continuity — physically accepted on current supplied tree:** the operator reports
  cross-display live Edit followed by Save now preserves the running Visualizer without teardown/reinit. Preserve that
  contract. Numbered geometry/layout-slot reload remains a separate topology/hot-swap operation and is not part of this
  checkpoint. Do not reintroduce Save reconciliation merely because the committed monitor route changed after a successful
  live Visualizer ownership transfer.
- [~] **Checkpoint 1 — Bubble extreme-shape presentation tail — SOURCE IMPLEMENTED / PHYSICAL VALIDATION OPEN:** the
  adjustment logs show healthy ~90 Hz logical cadence through the measured ~1174x187 (6.28:1) viewport, so the reported
  slow/sparse extreme-wide feel is presentation density/travel rather than dropped simulation ticks. The main-head outline
  no longer subtracts extra thickness from the large/extreme viewport ramp. Ordinary wide/tall cards remain unchanged; an
  extreme-wide-only eased tail reaches **+1 big bubble, +3 small bubbles, +20% stream baseline and +20% stream cap** by
  the measured shape. No radius/reactivity/Ghost compression, drift rewrite, timer or new cadence owner is introduced.
  Physical validation must compare first post-transfer vertical outline weight and canonical/moderate/extreme-wide density.
- [~] **Checkpoint 1 — Widget Glow distance/softness — SOURCE IMPLEMENTED / PHYSICAL VALIDATION OPEN:** Intensity remains
  opacity-only. New `input.widget_glow_distance` is a persisted 6-48 px control (default 14 px versus the former fixed 12 px)
  projected through the immutable Quick input snapshot to ordinary widgets and Visualizer. The retained analytical QSB is
  stretched in coordinate space rather than rebaked, giving roughly 17% broader/softer default falloff with no texture/FBO
  or recurring work. Settings hides Intensity/Distance/Color unless Hover or Click glow is enabled. Validate long-distance
  clipping, mixed-DPR/CUSTOM scale and whether 14 px default / 48 px maximum feel useful.
- [~] **Checkpoint 2 — Sphere + layout-slot mode persistence — SOURCE IMPLEMENTED / PHYSICAL+QT/GL VALIDATION OPEN:**
  Sphere Deformation now exposes **0.0-4.5** (50% above the prior 3.0 ceiling) and Size Response **0.0-3.0** with a
  **+0.90 radius pulse ceiling** (50% above the former +0.60 maximum response); defaults are unchanged and the new
  deformation tail softens only additional negative displacement so extreme positive crests remain fully authored.
  Water/Magma now share the body's actual rotating/deforming surface anchors: the body grows a timed lower-hemisphere
  precursor bulge, the liquid neck is oriented back into that same anchor for a substantial attached phase, then the fixed
  instanced mesh pinches off and falls under gravity. Magma's six outlets participate in the same fissure field and major
  fissures are real vertex-radius depressions; fine branching remains filtered bump/emissive detail. Optional local AA and
  a persisted optional dark cast shadow are added; shadow direction is derived opposite the existing Sphere light direction,
  strength is preset/custom adjustable, and the shadow is one analytical quad (no FBO/texture/timer). Geometry slots now
  capture/restore `spotify_visualizer.mode` alongside visible layout state while deliberately excluding per-mode tuning.
  Slot **load** keeps the established fenced rebuild so the newly applied mode becomes runtime truth; ordinary live Edit Save
  and successful cross-display Visualizer Save remain no-teardown contracts. A pre-existing deterministic 1px discrete
  display-hop drift was also fixed at its projection seam by replacing integer `QRect.center()` with the true geometric centre;
  pointer/drag transfer is unchanged.
  **Checkpoint static validation completed here:** all 450 Python files AST-parse/compile, all 33 authored JSON files parse,
  all five Sphere presets carry AA/shadow controls, composed Sphere body/effect/shadow GLSL literals have balanced structure,
  and source contracts prove shared `surface(anchor)`, no `waterLane`, macro fissure geometry, negative-tail radius safety and
  local-AA/shadow uniforms. Test collection in this container is **environment-blocked** by missing `PySide6` (not red).
  **Required checkpoint validation:** run `tests/test_layout_slots.py`, `tests/test_sphere_mode_integration.py`,
  `tests/test_qtquick_sphere_rendering.py`, `tests/test_qtquick_visualizer_reactivity_config_parity.py`, and the existing
  `tests/test_qtquick_custom_layout_owner.py::test_visualizer_display_hop_uses_nearest_direction_and_preserves_shape` on a
  PySide6/OpenGL-capable environment. Physically verify Water/Magma attachment before detach, Magma fissure depth, AA toggle,
  shadow on/off + light-direction tracking/strength, 4.5 deformation/3.0 Size Response, slot mode restoration, and no
  regression to live cross-display Edit Save.
  **Checkpoint package:** `GODZIP_Sphere_Attached_Liquids_Slot_Mode_Checkpoint2_2026-09-05.zip`; archive CRC, duplicate-member,
  manifest path/size/SHA-256 and selective-scope checks pass. The cumulative ChatGPT-session package carries exactly 9
  touched tests and 4 touched Docs files; unchanged Claude-reconciled tests/docs/tools are omitted with
  `omission_means_delete: false`.

1. [SUSPECTED DONE - CHECK] **Finish shared Widget colour-authority cleanup and physical check.** Apply the Style Overrides/header cleanup, run **Reset All Colours to Theme** once on the current profile when desired, and verify Media/Reddit/Gmail/Steam branded headers resolve cohesively from the selected Widget Theme/shared override. No hidden family colour should survive merely because its GUI swatch was removed.
2. **Close V7 Visualizer Settings acceptance.** Automated reconciliation is green (277 passed / 1 skipped) and physical testing has already proved Custom snapshotting plus disabled-active Sine -> Bubble substitution. The remaining top-level navigation mirror is now source-fixed: the Visualizers button mirrors Media/Visualizers capability state immediately, rejects admission without constructing bodies, and has an explicit semantic disabled/grey presentation including its custom child label. Physical re-run remains open for both dependency cases plus state-preserving re-enable, then Rainbow/Custom, retirement/re-enable, Settings recreation and theme/glass inheritance. Future-mode descriptor/module closure remains a separate final V8 proof.
3. **Post-V7 Bubble presentation/delivery attribution.** A poor-feeling Bubble run occurred on the **60 Hz display** after the V7/Rainbow/native-crash fixes even though logical cadence remained healthy. The old GC/light-usage optimizations are still active, so do not reopen them. First reproduce without `--usage`, then attribute immutable logical revision/age -> retained Quick sync -> render-thread entry -> Bubble payload preparation -> persistent float32 transport copy -> uniform upload -> draw using bounded aggregate evidence. Compare 60 Hz and 165 Hz only after the 60 Hz owner is understood. Do not add revision suppression, mutable cross-thread buffers, lower authored cadence, or any change that reduces Bubble reaction, motion, trails, freshness or amplitude.
4. **Test-truth / debris audit.** Audit the supplied current test tree against current production ownership before touching unrelated failures. Whole-file dead suites become explicit GODZIP DEBRIS (`move_to_deleteme`) only after caller/coverage audit; stale functions inside mixed-use files are rewritten/deleted in place. Preserve the now-green V7 suite and do not resurrect WidgetsTab/GL-overlay fossils.
5. [THEME SWITCH SPEED FINE - FRAGILITY UNKNOWN] **Theme-switch slowdown + narrow theme fragility audit.** Attribute duplicate QWidget refresh/repolish work first, then audit only real edge contracts: stale wrappers, lazy Settings pages, linked-theme transactions, catalogue/install roots, retained recreation, live failure propagation, and hidden lifetime owners.
6. **J cleanup/optimization/acceptance.** Restore broad-suite signal, finish remaining bounded parity/snap polish, run resource/CPU/GPU ownership passes, then compiled/frozen/installed acceptance.

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
- [~] **Visualizers capability -> top-level navigation state — SOURCE FIXED / AWAITING PHYSICAL.** The button already mirrored canonical capability admission via `setEnabled`; the remaining visible defect was the custom-painted child label/QSS never rendering a disabled semantic state. `TabButton` now refreshes on `EnabledChange`, uses Settings `text.disabled` for its child label, and the Settings-theme adapter derives a muted disabled tab surface/border from the existing navigation/panel semantics. Media-off remains the stronger dependency with tooltip exactly `Enable Media In Widgets`; Visualizers-family-off uses `Enable Visualizers In Widgets`. No second capability authority, body construction, timer or polling owner was added. Physically verify both disable paths and state-preserving re-enable.

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

- [x] diagnostics usage sampler attribution/partitioning. Current source still refreshes the GIL-held Windows topology/thread enumerations only on the heavy sub-cadence (every eighth sample by default). The 2026-09-05 run still shows the expected heavy-sample pattern; ordinary light samples are not evidence of a returned 15-second GIL stall.
- [x] stable-set Gen2 GC attribution and `gc.freeze()` lifecycle validation. The same 2026-09-05 run reached the one-shot freeze and recorded **zero Gen2 collections** across the run, directly disproving a resurrection of the old recurring Gen2 hitch.
- [x] first-publish cold-import relocation, with V4 dormancy hole corrected at the canonical descriptor seam;
- [x] analysis/handoff tails closed as not a visible steady-state owner.
- [x] resource plateau for owned resources — the 2026-09-04 ~7h53m soak (`logs/evidence_chest/09_04_soak`) proves non-accumulation across RSS/USS/private commit/VRAM/threads/tracked+GL resources/shm/task lanes/logging, with clean topology retire+restore and large downward RAM reclamation. Only a bounded Windows handle drift remains open (below). See `Docs/QtQuick_Migration/Resource_Plateau_Soak_Closure_2026-09-04.md`.

Still live:

- [ ] **Post-V7 Bubble presentation-tail attribution / safety-transport A/B.** The poor-feeling acceptance run was on the **60 Hz** display, so same-revision over-render at 165 Hz is not the lead hypothesis. Logical Bubble cadence remained healthy and the float32 safety transport regression tests are green, but scene/presentation tails still deserve direct attribution because the long pre-V7 Bubble soak was smooth. Run a short representative Bubble baseline with `--perf --viz` and **without `--usage`** first. If tails remain, measure bounded aggregates for published revision/age -> Quick synchronization -> render-thread entry -> payload preparation -> persistent contiguous `numpy.float32` copies -> `glUniform*` upload -> draw. Only after measurement may redundant same-revision work be considered; do **not** implement revision-based suppression pre-emptively, and do not replace immutable publication with mutable cross-thread NumPy state. Any optimization must preserve or improve Bubble freshness/reactivity and must not reduce authored cadence, head radius, reaction amplitude, motion, Ghost/history displacement, trail behavior or burst response. Compare the 165 Hz display after the 60 Hz path is understood.
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
4. [x] **Settings-body dormancy — SATISFIED (V6a, preserved through V7 source rehost).** Runtime dormancy was already proven; the lazy Settings-body ownership contract (`core/settings/visualizer_mode_body_host.py::VisualizerModeBodyHost`) covers all five modes. V6a first proved it in-place under Widgets; V7 now reuses that same host under the top-level Visualizers tab. Opening the V7 tab on SETUP constructs no mode body; a selected mode constructs once; cached reselect never rebuilds/re-hydrates unsaved edits; full reload re-hydrates only built bodies; missing-body construction fails loud + uncached; disabling a built mode now also exercises the real Qt retirement callback. Tests: `tests/test_visualizer_settings_body_dormancy.py`, `tests/test_visualizer_settings_lazy_bodies.py`.

Then perform V5-V8:

- [~] **V5 opening slice landed (2026-09-04):** canonical lazy Settings-body host + descriptor Settings-builder seam + pill model + dormancy proof (10 tests). Qt-free mechanism only — the live dialog is NOT yet rewired. Do not fold the mechanical rehost into that slice.
- [x] **V5b live-in-place lazy integration (construction flip DONE, 2026-09-04).** The live Widgets-hosted Visualizers UI now runs through `VisualizerModeBodyHost` with real per-mode laziness, no top-level tab / pixel move. **Decision (user):** Spectrum stays **eagerly built** as an explicit *temporary V5b Settings-only exception* — the genuinely shared Bar Fill/Border colour + Border Opacity controls are physically nested inside Spectrum's Appearance bucket (`spectrum_builder.py`), so extracting them is a V6 pixel move; no reclassification / proxy ownership. Oscilloscope / Sine / Bubble / DevCurve are constructed on first selection and hydrated ONCE at construction (`_hydrate_visualizer_mode_body`, from `_vis_loaded_config`); reselecting a cached body never rebuilds or re-hydrates it, so unsaved edits survive. Building a new mode hydrates only that mode's technical controls (`load_per_mode_technical_controls(only_mode=...)`), never clobbering another built mode's edits. Landed hazards 2/6/7/8 earlier; host gained `ensure`/`adopt`; the combo remains the single selection authority (`ensure` never sets selection). Proof: `tests/test_visualizer_settings_lazy_bodies.py` (A/B/F/G bar + no-rebuild/no-rehydrate + technical-edit + save-with-unbuilt) plus reconciled `test_widgets_tab.py` / `test_visualizer_presets.py` (select-then-assert for lazy bodies). No timers/pollers/workers; no top-level tab yet. **Gate 4 remains PARTIAL** — it may not close while Spectrum is eagerly constructed.
- [x] **V6a shared-control extraction + Spectrum lazy (DONE, 2026-09-04).** The genuinely shared Bar Fill/Border colour + Border Opacity controls are now owned by `ui/tabs/media/shared_appearance_controls.py`, built eagerly and independent of every mode body; Spectrum places (does not recreate) the exact same row widgets in its Appearance bucket, so presentation/order/defaults/keys/semantics/pixels are unchanged. Spectrum is now lazy under the identical `VisualizerModeBodyHost` construct/cache/hydrate contract as the other four modes (no eager build, no `adopt`, its loader moved to the hydrate dispatch). Save gates the Spectrum-owned ghost keys and the per-mode collect on the body being built (no fallback synthesis, no crash when unbuilt); the mode combo builds-before-saves. New regressions in `tests/test_visualizer_settings_lazy_bodies.py`: Spectrum-lazy, shared-controls-survive-Spectrum-unbuilt, unsaved-Spectrum-edit-survives-switch, save-while-Spectrum-unbuilt. This closes gate item 4 in-place.
- [~] **V7 top-level `Visualizers` tab — SOURCE IMPLEMENTED / PHYSICAL ACCEPTANCE PARTIAL (2026-09-04):** the visualizer presentation is rehosted out of Widgets into a lazy top-level `VisualizersTab`. Widgets' physical section registry no longer includes Visualizers and there is no active `build_visualizers_ui` or `vis_mode_combo` path. Opening Visualizers lands on SETUP and constructs zero mode bodies; enabled-mode pills are the only mode-selection presentation. Per-mode bodies still construct on first pill selection through `VisualizerModeBodyHost`; normal reselect returns the cached body without rehydrating unsaved edits. Disabling a constructed mode performs real Qt retirement: remove/hide from the host layout, remove that mode's technical-control registry entry, clear stale context attributes that point into the body, then `deleteLater()` while retaining the existing Qt parent until deferred destruction. Re-enable + select reconstructs from persisted state. The obsolete V5b `adopt()` seam is deleted. First physical passes confirm Custom snapshotting works and disabling the currently-used Sine mode persisted Bubble as the replacement and excluded Sine; restart/runtime logs agree. Acceptance follow-up restores the complete canonical Settings control style bundle (`SPINBOX_STYLE`, `COMBOBOX_STYLE`, `SLIDER_STYLE`, circular checkboxes/tooltips), moves preset action buttons onto a semantic Settings button style, and restores tick marks to Rainbow Speed. **Custom presentation is now literal rather than an ownership leak:** Rainbow + Speed are physically moved inside the selected mode's normal/Custom layout; Spectrum Bar Appearance is likewise physically inside Spectrum Custom. Their tab-owned widget references are evacuated to the stable mode page before mode switch/SETUP/retirement, then reinserted on selection, so user-facing placement is correct without allowing Qt body destruction to take stable controls. No new polling/worker/fallback owner; the existing 200 ms user-input save coalescer moved with the controls.
  - [~] **V7a context extraction — superseded by this V7 checkpoint:** `ui/tabs/visualizer_settings_context.py` owns the reusable Visualizer Settings UI/preset/bucket/default-config context and the special Visualizer save merge/Custom-snapshot transaction. The five mode builders/shared helpers no longer type-couple to `WidgetsTab`. The first V7a outbound ZIP accidentally omitted the newly-created context file from its manifest and is **NOT a valid standalone checkpoint**; the V7 superseding GODZIP includes it and replaces that archive.
- [~] **Visualizer capability gate wired / navigation mirror source-fixed, physical acceptance open.** The top-level tab internally mirrors both canonical Widgets capability authorities instead of inventing activation state. If Media is off it disables admission with exact tooltip **`Enable Media In Widgets`**; if the Visualizers family itself is off it disables admission with **`Enable Visualizers In Widgets`**. The top-level navigation button now visibly greys through the same canonical `setEnabled` mirror, including its custom-painted child text, and re-enables without constructing the tab/mode bodies. If the top-level tab already exists when capability closes, it flushes pending edits, retires every constructed mode body and returns its internal page to SETUP; persisted state remains. Visualizers background hydration remains excluded. Re-run both dependency cases physically before closing V7.
- [ ] **Future-mode descriptor/module closure.** Prove addition of a new mode needs one canonical descriptor plus isolated runtime/renderer/Settings modules and focused tests, not unrelated five-way switch edits. This is intentionally not claimed by the V7 presentation rehost.
- [~] **V7 before/after self-audit — automated reconciliation green; physical re-run still open.** User physically confirmed Move To Custom snapshotting and disabled-active-mode substitution. Earlier tail logs confirm the save committed `mode=bubble`, removed Sine from `enabled_modes`, and subsequent runtime admitted Bubble; that run had no Qt capture warning/error/critical and logical runtime stop paths reported `joined=True`/zero failures. The next physical pass exposed two shared-path Rainbow defects and one native Quick-Bubble crash; the acceptance fixes moved Rainbow state to presentation ownership, added persistent contiguous `numpy.float32` transport buffers for Bubble positions/extras/trails, made discrete Rainbow save durable, and flush built tabs on Settings close without waking dormant tabs. **User-system focused acceptance is now 277 passed, 1 skipped, 0 failed**, including the new Bubble transport-buffer/`glUniform3fv` regressions. Test reconciliation deleted three extinct combo fossils, rewrote fourteen stale tests against current ownership, migrated five genuinely unique pre-V7 invariants into `test_visualizer_settings_lazy_bodies.py`, removed thirty-five orphaned WidgetsTab visualizer tests, and deleted the obsolete `test_sine_line4_builder_integration.py`; **no production code changed during that reconciliation.** Broader physical acceptance is still required for Rainbow animation, Bubble crash non-recurrence, the source-fixed top-level capability-button grey/re-enable state, curated presets/Custom transitions, Settings theme/glass inheritance, mode retirement/reconstruction and full Settings/app recreation.

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

- [x] **V7 Visualizer test reconciliation.** Focused cluster is 277 passed / 1 skipped / 0 failed. Retired combo tests and orphaned WidgetsTab/sine-line4 Visualizer fossils were removed only after current coverage was verified; five unique invariants were migrated to the maintained `VisualizersTab` suite. No production code was changed to satisfy stale tests.
- [ ] **Audit the supplied whole test tree and generate real GODZIP DEBRIS for whole-file corpses.** Use current source/ownership as authority, verify maintained coverage/callers first, then mark only wholly obsolete modules `move_to_deleteme`. Mixed-use files are edited in place. The removed `test_sine_line4_builder_integration.py` is already gone at source HEAD and must not be resurrected merely to delete it again.
- [ ] **Known non-Visualizer red: Media progress transport gate.** `test_widgets_tab.py::...media_progress...transport_gate` currently expects `media_playback_progress_enabled.isEnabled() == False` but sees True. Inspect the current Media capability/transport contract before deciding production bug vs stale assertion; do not lump it into Visualizer fossils.
- [ ] **Known non-Visualizer red: Media bucket-state roundtrip.** `test_widget_bucket_state_roundtrip` expects a `Transport & Volume` bucket that no longer appears under that name. Verify the current builder organization and persistence identity before rewriting/deleting the assertion.
- [ ] **Known stale/maintenance reds:** reconcile `test_visualizer_doc_references.py` old Phase-I phrase against current docs; audit `test_settings_defaults_parity.py` snapshot drift before any regeneration; reconcile `test_settings_theme_system.py` use of removed `THEMES_DIRECTORY_BUILD_REPLACE_BLANK` against the current theme-directory contract. Defaults artifacts must never be casually regenerated merely to green the suite.
- [ ] **Known whole-file GL-overlay fossil candidate:** `test_oscilloscope_display_contract.py` imports removed `widgets.spotify_bars_gl_overlay`. Confirm maintained Quick Oscilloscope coverage and zero live callers, then retire the whole module through GODZIP DEBRIS rather than resurrecting the deleted overlay.
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

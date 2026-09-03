# Current Plan — Qt Quick Production Migration

Last updated: 2026-09-03

## Current checkpoint

The production Qt Quick cutover is complete. Current work is now **post-cutover product completion, validation, modularity and cleanup** rather than presenter migration.

Detailed H/I history is intentionally not repeated here. Use the closure/historical records when mechanism evidence is needed:

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/Historical_Bugs/README.md`
- `Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`
- `Docs/Tooling_Audit_2026-09-01.md`
- `Future_Cleanup.md`

Do **not** repopulate this plan with completed migration sub-slices. The live plan should contain only current work, current validation gates, and durable guardrails needed to enter the next task safely.

## Immediate sequence

1. **P0 — Visualizer hitch attribution/baseline.** Bubble and extreme-tall Spectrum are co-equal sensitive oracles. Attribute recurring >33 ms delivery holes before changing smoothing or authored response. The logical cadence is a pure-Python thread, so a spike means a single GIL-held C call (or stop-the-world GC) stalled it. The `--usage` sampler lead is **resolved** (a diagnostics-perturbation artifact: two GIL-held system-wide psutil enumerations, now partitioned), and the always-on **Gen2 GC hitch is resolved** (stable long-lived survivors frozen out of gen2 scans via `gc.freeze()`, validated in-situ on both displays). The still-open owners are first-frame publication and analysis/presentation tails. See `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`.
2. **[DONE] P0 — Visualizer V0-V4 behavior-floor + authority/dormancy.** Behavior floor pinned green (V0), canonical mode wiring centralized into the descriptor (V1), per-mode enable state persisted additively with no settings lost (V2), every runtime caller routed through the effective enabled set (V3), and disabled-mode dormancy proven (V4). The Settings UI was intentionally **not** moved. Performance work now has the final active owner graph.
3. **P0 — remove deterministic hitch owners from the surviving active path.** First-frame publication, analysis/handoff tails, GUI/pacer delivery and diagnostic/logging overhead remain explicit targets until Bubble + tall Spectrum are physically smooth. (Done: usage-telemetry contention — partitioned; Gen2 GC — stable set frozen out of gen2 scans, validated in-situ.) Never solve them by lowering cadence, accepting stale state or damping authored amplitude/motion.
4. **Then complete V5-V8 Visualizers Settings extraction/rehosting, Media dependency UX and future-mode proof.** Settings presentation moves only after mode authority/dormancy and the main hitch owners are stable.
5. **Measure/repair the theme-switch slowdown.** Existing `[PERF][SETTINGS_THEME]` and `[PERF][THEME_SELECT]` timings point to overlapping QWidget refresh/repolish listeners; optimize only after confirming overlap. Do not weaken bidirectional stable-ID linking or transactional rollback.
6. **Run the narrow theme-system fragility / edge-contract audit.** Stale Qt wrappers/QObject lifetime, lazy Settings-page state, linked-theme transaction edges, retained-runtime recreation, theme catalogue/path/build/install boundaries, live renderer failure propagation and hidden polling/fallback owners.
7. **Resume bounded J visual parity + cleanup, then the broader optimization/resource plateau tranche.** Remaining widget parity, snap guides and polish matter, but recurring Visualizer hitches are a product-quality blocker and should not be buried under cosmetic work.

### Retired runtime card-material work

The Quick-runtime Glass/Acrylic backdrop-card experiment is **rejected and removed**, not merely disabled. Do not reintroduce its schema/state/UI or renderer machinery during ordinary theme work. The failed methods and reasons are preserved in `Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md`; they do not belong in this live checklist. Settings-window Glass/Acrylic remains a separate accepted QWidget/HWND theme feature.

### Retained theme/UI completion

- [~] **Abandonment/BACKLOG semantic + readability.** `abandonment_issues.accent -> widget.accent` owns the archive/BACKLOG block; the label uses ordinary resolved text colour. Existing explicit family accent override remains higher precedence.
- [~] **58 colour-only Widget counterparts.** Shipped `.srwtheme` files are schema-v3 semantic-colour bundles with no material recommendation and no `[Glass]`/`[Acrylic]` Widget display/file suffix. Stable `linked_settings_theme_id` still points to the actual Settings-theme identity, whose name/file may legitimately retain Settings-window material tags. All 58 mirrors materialize mature Media/Volume/Seek/Backlog roles. Light/dark-text counterparts now enforce a high-opacity light runtime card floor and opaque secondary metadata so arbitrary wallpaper cannot collapse contrast.
- [~] **Reddit parity.** Age value and `AGO` use fixed subcolumns so the first value digit and `AGO` column align while the title gap remains tight; the aligned `AGO` column is shifted 3 px left from the prior parity pass.
- [~] **Context Menu submenu crossing.** Transparent pointer corridor + one-event-turn defer; no timer/poller/sticky owner.
- [~] **Theme Foundry Widget export.** One deterministic Settings->Widget converter, stable link identity, strict reload, and colour-only v3 output.
- [~] **Widgets -> General `Style Overrides`.** Card Surface + Card Border edits fork the full resolved named Widget palette into persisted `Custom`; Card Border Width remains a global geometry style. There is no Surface Style/material control.
- [~] **Overlay-install debris cleanup.** `tools/material_rollback_cleanup_gui.py` moves known rejected material files, stale material-named Widget mirrors and failed root experiment artifacts into `/deleteme/<timestamp>` with manifest-backed Undo. It never touches Settings theme files merely because they legitimately contain `[Glass]`/`[Acrylic]`.

## User-environment automated validation gate

The 2026-09-01 `98/98` destination result is historical evidence only. The current tree includes stacking, global-CUSTOM dormancy, volume-wheel routing, Widget Theme/link/semantic work and new regression bars. Run:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [ ] **Run the refreshed `destination` profile in the normal user environment with PySide6/OpenGL available.** The maintained profile includes stacking/CUSTOM, volume, Widget Theme mirror/semantic/link, Settings-theme deleted-wrapper lifetime safety, and retained Context Menu Settings-click regressions.
- [ ] **Classify every red against current ownership.** A red is not permission to restore QWidget/GL presentation, a retired fallback, polling, or a second runtime owner.
- [ ] **Keep automated green separate from physical acceptance.** QML pixels, CUSTOM transitions, frozen paths and display topology still require real-app validation.

Before final J closure also run the broad gate:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

The destination profile remains production authority; broad-suite museum/deleted-owner failures are cleanup evidence, not product-authority evidence.

## Current physical / product validation queue

Status: `[ ]` open, `[~]` implemented/source-proven but awaiting real-app validation, `[x]` physically or conclusively accepted.

- [x] **Non-CUSTOM smart stacking collision solver.** Operator physically exercised the pathological all-widgets-on-one-slot case and reported exceptional behavior. Preserve deterministic whole-display spill and zero steady-state cadence cost.
- [~] **Global CUSTOM dormancy across all three entry paths.** Authored stacking and Media↔Visualizer adjacency must be completely off when: (1) persisted/effective CUSTOM exists, (2) live Edit Layout begins, or (3) a number-key saved layout begins its fenced load/rebuild. Number-key load is a first-class entry path, not an edge case.
- [~] **Media↔Visualizer ordinary adjacency.** Only while global CUSTOM is inactive: Media remains at its authored ordinary location and Visualizer occupies the useful adjacent side; disabled Media still supplies the authored route. This contract must never leak into CUSTOM.
- [~] **Whole-Media + Visualizer app-volume wheel routing.** Entire Media root and ordinary Visualizer may forward discrete wheel steps through the existing Media app-volume owner; CUSTOM resize-wheel ownership wins absolutely.
- [~] **Context Menu -> Settings click-through suppression.** Source uses an event/deadline guard rather than a timer/poller; run the maintained Qt regressions and physical click-through check.
- [~] **Settings Theme live-recreation regression.** Reopen/recreate Settings, then switch repeatedly across Glass/Acrylic/Glass themes. No `Internal C++ object (SettingsDialog) already deleted` error may occur; a stale PySide wrapper must be pruned from the root-QSS registry without weakening transactional rollback for genuinely live renderer failures. `test_settings_theme_qobject_lifetime.py` is an explicit PySide6 user-environment regression for the real Shiboken edge.
- [~] **Bidirectional linked-theme UX.** The compact lock/unlock control appears on both Settings Themes and Widget Themes pages. While locked, choosing either catalogue selects/persists the explicit matching stable-ID pair in the other catalogue; selection must never implicitly unlock. Themes with no counterpart (including Widget Custom) require Independent mode first.
- [~] **Widget Theme selection/semantic inheritance.** Verify named Widget themes, Independent state, Custom creation, Card Surface/Card Border inheritance and family override precedence. Clock is already semantic through shared `card.text` when its family swatch is canonical. Dark-theme mirrors may keep primary text near-neutral/near-white; light-theme mirrors deliberately use dark text over a stronger light runtime card floor. Subtle movement is not evidence that Clock bypasses theming.
- [x] **Windows GSMTC teardown / `0x8001010e` wrong-thread fault.** The latest 2026-09-03 operator log again shows native GSMTC observation establish/teardown staying on the same affinity owner thread (`72164`) through recreation with no `0x8001010e` or native-fault dump. Preserve the explicit owner lane and callback fencing.
- [x] **Native fault logging gap.** Latest source/debug run produced a bounded `native_faults.log` from capture-open through capture-close with no native dump; `screensaver_qml.log` also closed at 0 messages / 0 warnings / 0 errors / 0 criticals. Source/developer and explicit debug/verbose runs keep native capture; ordinary compiled non-diagnostic runs remain free of the extra file unless debug/verbose is requested. The hang watchdog must never retarget global faulthandler output.

- [~] **Theme selection responsiveness regression — owner now identified, optimization queued.** Latest timings show total Settings-theme publication around 152-298ms, dominated by `ui.tabs.shared_styles._refresh_live_shared_widgets` (~74-165ms) and `ui.settings_theme._refresh_registered_widgets` (~68-112ms); bidirectional linked selection adds only about 10ms beyond that publication. Audit duplicate/redundant QWidget repolish/refresh coverage between those two listeners before weakening transaction/link correctness.
- [~] **Abandonment Issues / BACKLOG accent inheritance.** `abandonment_issues.accent -> widget.accent`; the existing explicit family `accent_color` override remains higher precedence. No new global Settings swatch.
- [~] **Reddit parity.** Split the time field into two fixed sub-columns: value (`03D`/`02HR`) uses a fixed left edge so its first digit vertically aligns; constant `AGO` is right-aligned so its O/right edge aligns. The complete aligned `AGO` column is now 3 px further left. Keep the title gap tight. Validate short/long ages and elision physically.
- [~] **Context Menu submenu crossing.** A narrow transparent hover corridor plus one-event-turn defer keeps ownership while crossing parent -> submenu without adding a timer/poller or sticky lifetime. Validate both left- and right-opening submenus.
- [~] **Theme Foundry Widget counterpart export.** `Save Widget Counterpart…` uses the same deterministic Settings->Widget counterpart authority as the curated mirror generator and strict-reloads the saved `.srwtheme`. File-authored drafts must acquire a real Settings-theme identity; compiled Default Dark may use its existing builtin stable ID directly. Validate both paths.
- [~] **Widgets -> General `Style Overrides` grouping.** Card Surface, Card Border and Card Border Width sit together immediately above Layout. Editing Card Surface/Border forks the full named Widget palette into persisted `Custom`; Border Width remains global styling rather than Widget Theme schema. There is no runtime Surface Style/material control.
- [~] **Curated light/metal theme expansion.** The pack is now 58 Settings themes + 58 deterministic Widget counterparts. New light/white-adjacent themes: Porcelain Sky, Linen Sage, Pearl Blush, Alabaster Citrus. New silver/metal themes: Polished Chrome, Brushed Nickel, Titanium Cobalt, Tungsten Blues. Preserve stable mirror IDs/link identities and readable contrast. The six dark-text light/light-metal Widget mirrors now establish a wallpaper-independent light card floor and keep muted/metadata text opaque enough for runtime contrast. Widget mirrors are colour-only v3.
- [~] **Installed/frozen theme + asset roots.** Source/dev uses `<repo>/themes`; installed/frozen uses `%ProgramData%\SRPSS\themes` with `widgets\` beneath it. QRC remains the embedded Settings-UI lane; raw `images/` remains the runtime branding lane.
- [~] **Visualizer card shadow / Clock separator / Edit-mode X alignment / remaining bounded J parity items.** Keep these in the operator observation ledger or focused J decomposition; do not expand them into another migration phase here.

## P0 Visualizer hitch / delivery-quality tranche — active

Detailed owner/evidence checklist: `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`.

Latest operator log establishes that the current tall-Spectrum flicker cannot safely be treated as a smoothing-only regression. R-76 remains valid, but missed delivery windows are large enough to recreate visible tall-card jumps. Bubble is equally sensitive and is a co-primary physical oracle.

- [x] **Periodic usage sampler attribution.** Resolved: the `--usage` sampler's `children(recursive=True)` + `num_threads()` are GIL-held system-wide enumerations that stalled the pure-Python logical thread (proven headless). Partitioned to a slow sub-cadence; a `--usage`-only diagnostics-perturbation artifact, not a shipping owner. Record in the attribution doc.
- [x] **Gen2 GC owner.** Resolved. Attributed (headless): gen2 scan cost is O(retained tracked objects); the retained set is stable, long-lived survivors gen2 rescans (~28-142 ms) while freeing ~0. The Bubble tick is not the driver. Fix: `RuntimeGCPolicy.freeze_stable_generation()` (one-shot ~45 s after start; `gc.unfreeze()` on stop) moves that set to the permanent generation (O(1), free) so future gen2 scans skip it — not disabling GC. **Validated in-situ on both displays**: `Froze 132666 stable objects`, then no gen2 stall for the rest of the run; RSS stable, QML messages=0, no native fault, clean shutdown. Lifecycle audit (`tests/test_gc_freeze_lifetime.py`): generations recreated after the freeze retire normally (no accumulation); the one generation live at freeze time is a bounded pin until stop (resources release by explicit teardown regardless). Real-recreation in-situ confirmation of the Qt-side generation graph is still pending. See the attribution doc.
- [ ] **First-frame publication.** Initial Bubble tick spent ~361 ms in publish (`~414 ms` total). Treat activation cost separately from steady-state cadence and remove the one-shot owner without moving recurring copies into every frame.
- [ ] **Analysis/handoff tails.** Persistent audio-analysis lane averages remain low, but max execution reached ~58.75 ms and max handoff ~37.54 ms. Correlate these tails with visible gaps after periodic telemetry/GC are isolated.
- [ ] **Recreation-specific latency.** A ~117 ms Bubble gap during replacement construction and ~3.19 s Spectrum age warning during later re-admission are separate from steady-state hitch metrics. Preserve fresh-generation fencing while reducing replacement latency.
- [ ] **Pacer/UI/logging attribution.** Track skipped presentation deadlines, long UI deliveries and scene invalidation after producer stalls are controlled. Log writer lag reached ~440 ms but caller max was ~4.93 ms with zero dropped records; do not misattribute asynchronous file lag without evidence.
- [ ] **Resource plateau remains open.** Short-run RSS/private/cache/thread/handle values moved with recreation/cache activity but did not prove a monotonic leak. Soak/topology/resource-plateau work remains required before J closes.
- [ ] **No symptom damping.** Bubble motion/radius/Ghost and Spectrum amplitude/R-76 vertical response stay authored. No cadence reduction, stale snapshots, catch-up FIFO, extra timer or per-mode clock.
- [ ] **Order:** attribution baseline -> V0-V4 behavior-floor/authority/dormancy -> deterministic hitch owners -> active-path tails -> recreation freshness -> Bubble+tall-Spectrum physical acceptance -> V5-V8 Settings rehost/dependency/future-mode proof.

## Theme-system fragility / edge-contract audit — future task, not started

Run this **after** the rollback/parity/Foundry checkpoint is physically accepted. Keep it narrow and contract-oriented rather than reopening semantic-theme coverage.

- [ ] stale Qt wrappers / QObject lifetime edges;
- [ ] lazy Settings-page state and recreation;
- [ ] linked-theme transaction edges in both directions;
- [ ] retained-runtime recreation and generation handoff;
- [ ] theme catalogue/path/build/install boundaries;
- [ ] no swallowed live renderer failures;
- [ ] no hidden polling, fallback or background lifetime owners.

This audit is explicitly **not** a request to inventory every visual literal, create another diagnostic theme, or perform a three-part semantic coverage exercise.

## Golden guardrails

### Visualizer fidelity / freshness / scaling

Visualizer authored response is protected above refactor neatness, allocation counters and Settings organization. Read these before any mode modularization work:

- `Docs/Visualizer_Change_Checklist.md`
- `Docs/Visualizer_Reference.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Guardrails/Performance_Optimization_Contract.md`
- `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md`

Never solve modularity, performance or extreme viewport behavior by:

- reducing the authored/logical Visualizer cadence;
- adding per-mode clocks, QML timers, catch-up FIFOs or paint acknowledgements;
- increasing source/snapshot staleness;
- globally compressing Bubble head radius, reaction amplitude, motion or Ghost/history displacement as viewport extent grows;
- adding a second viewport/domain compensation to state already normalized once;
- retuning DSP/gain/cold-play response to hide a presentation or activation defect;
- changing mode presets, CUSTOM scale/extent semantics or renderer transfer merely to make registry work easier.

**R-69 remains binding.** Bubble's restored scaling/reactivity contract is the golden reference for all mode-modularity work. A registry/settings refactor must be behaviorally transparent to canonical, wide and tall viewports.

### One authored Visualizer runtime

Keep the accepted chain:

```text
one shared BeatEngine
-> one persistent serial visualizer.audio_analysis lane
-> one sole VisualizerLogicalRuntime authored cadence
-> one active mode-owned frame runtime
-> immutable latest publication
-> retained Quick synchronization
-> one lazy active mode renderer inside the display QQuickWindow
```

Mode enable/disable architecture may decide **which mode is eligible**; it may not create a second engine, logical clock, presentation surface or analysis lane.

### CUSTOM is a global layout mode

The first widget entering CUSTOM disables authored stacking/adjacency globally. This includes number-key saved-layout loading. Ordinary layout may become eligible again only after the effective persisted/live layout is globally non-CUSTOM.

Visualizer mode preset `Custom` and global display-layout CUSTOM are separate concepts. A future mode Settings reorganization must not conflate them.

### Media event ownership

Do not restore fast Media polling or process-probe fallbacks. GSMTC/event ownership is primary; slow reconciliation/watchdog is deliberate degraded-path coverage. Visualizer depends on Media product admission but does not acquire a second Media owner.

### Performance admission

Freshness/reactivity and latency-tail quality outrank prettier aggregate counters. No performance change may silently lower authored quality. Use `Docs/Guardrails/Performance_Optimization_Contract.md`.

## Next architecture tranche — Visualizer mode modularization

**Assessment: feasible and worthwhile, but only if mode activation is made real before the Settings UI is moved.** The whole Visualizer family is already capability-gated; individual modes are only partially modular today.

Target product UX:

```text
Visualizers tab
    SETUP
        family enabled/dependency state
        active mode toggles
        shared Visualizer position / common controls
    Spectrum        [pill only if active]
    Oscilloscope    [pill only if active]
    Sine Waves      [pill only if active]
    Bubble          [pill only if active]
    Spline Curve    [pill only if active]
```

- [x] **Phase V0 — baseline/fencing tests before refactor.** Visualizer test floor reconciled to green (646+); pins active-mode cycling, preset/Custom behavior, renderer/runtime laziness, viewport scale/extent, Bubble/BTF and source freshness. (Non-visualizer/heavy stale modules deferred to J+ exit via `tests/conftest.py collect_ignore`.)
- [x] **Phase V1 — consolidate neutral mode metadata/activation authority without moving UI.** Done: the `VisualizerModeDescriptor` is the single source of per-mode frame-runtime + renderer wiring (lazy import-path strings); `_mode_runtime_factory` and the renderer `implementation_registry` derive from it. `iter_all_visualizer_mode_descriptors` (all registered) vs `iter_visualizer_mode_descriptors` (active) distinction preserved. Behavior-transparent; lazy imports intact.
- [x] **Phase V2 — persisted per-mode activation.** Done: additive `enabled_modes` on `SpotifyVisualizerSettings` (default all; migration = absent -> all) + pure `resolve_effective_enabled_modes`/`resolve_effective_mode` (family ON -> >=1; disabled-current -> deterministic enabled substitute, logged, never re-enables). **Self-audited: no settings lost** (312 fields round-trip; to_dict gains only `enabled_modes`). Disabling a mode preserves its settings/presets.
- [x] **Phase V3 — route callers through the effective enabled set.** Done: cycling (double-click/context-menu), context-menu mode list, and initial/stale persisted-mode resolution all consult the enabled set so a disabled mode is unreachable; schema/serialization still knows all modes. Behavior-transparent today (all enabled). Renderer/frame-runtime/capture implicitly covered (active-mode only). Settings mode-selector UI restriction deferred to V5-V8.
- [x] **Phase V4 — prove true dormancy.** Done (`tests/test_visualizer_mode_dormancy.py`): fresh-interpreter proof that a disabled mode imports/constructs no renderer/frame-runtime, each mode can be the sole enabled mode, and enable-state owns no timer/thread/poller.

#### HARD pre-V5/V6 corrective gate — resolve immediately before V5/V6, do NOT start V5/V6 first

An independent audit found V2-V4 broadly sound but flagged two real admission/config gaps and two proof requirements. They are **dormant today** (every mode is enabled, so substitution/rejection never fire) but **must be fixed before any per-mode enable/disable UI or Settings rehosting**. Do not reopen V2-V4 for these mid-perf-work unless the code being changed directly intersects one; then fix only the intersecting item at its ownership boundary. No Visualizer behavior tuning, no generic mega-class, no retired QWidget/GL plumbing, no fallback activation paths.

1. **Disabled-current startup substitution ordering.** Today `_construct_quick_visualizer_owner_on` resolves the activation payload/model for the persisted mode, then patches `model.mode = substitute` afterward — leaving the disabled mode's preset/active-alias state on a model whose runtime mode is the substitute. Fix: resolve the effective enabled target mode **before** the final activation payload/model is resolved, and re-enter the existing canonical activation resolver for that target (do not field-patch after the fact). Regression: deliberately conflicting preset/settings between disabled-persisted mode A and enabled substitute B; prove the constructed model/resolved-activation carry B's own preset/Custom/technical state, not A's aliases. Preserve all disabled-mode settings/presets/Custom/preset-indices; never silently re-enable A.

2. **Deepest request-admission boundary.** `_request_quick_visualizer_mode()` still accepts any canonical/dev-active mode without consulting `enabled_modes`; UI/menu/cycle callers currently sanitize, but the canonical boundary must enforce the invariant itself. Semantics: startup/stale persisted selection -> deterministic enabled substitution + explicit log; explicit normal runtime/UI request for a disabled mode -> **reject explicitly** (do not silently enable or route to it). Schema/migration stays aware of all registered modes; this is runtime admission only. Tests: a disabled mode cannot be reached through direct normal activation even when a caller supplies its canonical id.

3. **Durable no-settings-lost regression.** Convert the V2 one-off self-audit into permanent coverage against current settings/preset authorities (not resurrected pre-Quick tests): every existing Visualizer field survives load->model->save; all five modes' mode-specific settings intact while modes are disabled; each mode's preset index; curated preset selection; mode-level Custom snapshot/cache; switching into Custom after an advanced edit; disabled-mode state surviving while another mode is active; `enabled_modes` additive (never replacing/deleting old state).

4. **Settings-body dormancy is NOT closed.** V4 proved runtime dormancy (lazy renderer/frame-runtime, resolver/cycling, no new timer/thread), but the Widgets-hosted Visualizer Settings still builds all five mode bodies. Carry into V5/V6: new top-level `Visualizers` tab + `SETUP` pill + a pill only for enabled modes; rehost existing builders/preset sliders/Custom UI (do not rewrite); a disabled mode's Settings body is not constructed (preferably built only when its enabled pill needs it); disabled-mode settings/presets remain persisted despite no UI construction. Keep V4/V5 wording from conflating runtime vs Settings-body dormancy.

**V5/V6 Settings-migration self-audit (before declaring V5/V6 done):** a deliberate before-vs-after audit against the pre-migration checkpoint (we previously lost and had to recover Visualizer preset/settings behavior, so do not infer fidelity from the UI rendering). Prove: all five builders preserve controls/semantics; curated preset selection works; preset sliders select the same authored slots; advanced changes still move to Custom; Custom snapshot/save/restore stays mode-local; settings survive Settings close/reopen and app recreation; disabled modes retain settings/presets; re-enabling restores prior config; selected/effective runtime mode stays coherent with `enabled_modes`; no save serializes only currently-built/lazy pages and drops unbuilt mode state; Media-disabled Visualizers-tab state does not erase Visualizer state; no new timers/pollers/workers/fallback owners/second runtime authorities appear. Keep every unchanged persistence key unchanged — a UI rehost is not a reason to migrate the schema.

- [ ] **Phases V5-V8 — move Settings presentation only after V0-V4 are green and hitch owners are stable.** Extract the narrow Visualizer Settings host first, then create a top-level Visualizers tab with a `SETUP` pill plus one pill for each enabled mode, preserve the Media dependency UX, and prove a bounded future-mode addition path. Reuse existing mode builders, preset sliders and mode Custom system; rehost them rather than rewriting visualizer behavior.
- [ ] **Media dependency UX.** If Media is disabled at the Widgets capability/setup level, grey/disable the Visualizers tab and expose tooltip text **`Enable Media In Widgets`**. Do not create a second way to activate Media from Visualizers. Re-enable normal Visualizers tab behavior when Media becomes available.
- [ ] **Phase V5 — future-mode authoring proof.** Adding a new mode should require one canonical descriptor plus its isolated runtime/renderer/Settings modules and focused tests, not edits to multiple unrelated five-way switch tables.
- [ ] **Physical acceptance after modularization.** Exercise every enabled/disabled combination that matters, one-mode-only operation for each mode, mode cycling, preset/custom round-trip, canonical/wide/tall viewport behavior, pause/play freshness, multi-display admission and Bubble/BTF eyes-on behavior.

The detailed decomposition and known hard-coded mode seams are in `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md`.

## Residual migration truth cleanup — non-blocking unless a red proves otherwise

Detailed deletion/test ledgers live in `Future_Cleanup.md`, `Docs/TestSuite.md` and the tooling audit. Keep only these live obligations here:

- [~] Reconcile stale tests that still import deleted GL/compositor/physical-owner code. **Visualizer floor is done and green** (646 pass; retired ~28 pre-cutover P2 presenter tests + monolith/overlay/creator/mode_transition tests, migrated the current-architecture ones, fixed a `sys.modules` isolation leak). **Deferred to J+ exit:** the remaining stale modules are skipped via `tests/conftest.py collect_ignore` (visualizer-unrelated infra: widget_manager/refresh/setup, widget_import_dormancy, display_context_menu/image_ops/integration, custom_layout_manager, logging_routing, f0_5_shadow_controls, p3_set_state_attribution, compositor_gpu_queries, startup_shader_warmup; plus visualizer-adjacent ghost_isolation, line4_6_pipeline_trace, oscilloscope_display_contract) and one headless-GL pixel test in `test_qtquick_visualizer_clip_smoke.py`. At J+ exit, reconcile each biasing to the current Quick architecture (fix where a current contract survives, delete when in doubt) and remove it from `collect_ignore`.
- [ ] Reconcile remaining old MC physical-window tests against current Quick role/policy ownership.
- [ ] Preserve neutral transition math/registry/shaders and neutral Visualizer DSP/logical algorithms that current Quick source actually uses.
- [ ] Re-run exact caller/import searches before each residue deletion batch; no compatibility fallback may silently recreate a second presenter/analysis/polling owner.
- [ ] Bring the broad whole-tree gate back to useful signal without weakening the destination production profile.
- [ ] Retire migration-only benchmark/spike tools only after final J physical acceptance proves they are no longer needed.

## Required post-migration optimization tranche — before J closure

H proved the retained Qt Quick architecture can meet its accepted heavy-load boundary. It was **not** a general optimization pass. J cannot close without profiling the real migrated product and removing measured useless work.

- [ ] **CPU/GPU/QML pass.** Measure frame tails, overdraw/offscreen work, binding churn, hidden animations, unnecessary scene invalidation and duplicate work.
- [ ] **Ownership/contention pass.** Audit remaining timers/pollers, worker/thread cardinality, locks/queues and event ownership. Prefer event-driven ownership and fewer owners over reduced authored update rates.
- [ ] **Allocation/GC pass.** Attribute Bubble's documented Gen2-correlated wall-clock stalls and remaining non-GC stalls using allocation/lifetime evidence before changing `RuntimeGCPolicy`. Current policy is conservative evidence-led behavior, not a finished optimization. The caller-dead pre-Quick `GCController` facade is cleanup residue, not runtime authority.

- [ ] **Resource plateau.** Soak recreation/topology changes and track RSS/USS, VRAM, threads, handles, caches/workers and retained resources.
- [ ] **Quality recheck after optimization.** Modest and representative-heavy runs must preserve cadence, source freshness, authored amplitude/motion and visible fidelity.

## Final J acceptance obligations

- [ ] Family visual-parity pass against the pre/post migration image oracle where useful.
- [ ] Complete remaining alignment/snap-guide and bounded presentation polish.
- [ ] Complete compiled/frozen/installed 1/2/N-display, DPR, topology and Media Center/screensaver acceptance.
- [ ] Reconcile remaining historical-bug records/failed methods worth preserving.
- [ ] Run final maintained destination + broad-suite gates and reconcile source/docs/tests before J closes.

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

Historical documents preserve what happened; they do not override current owner maps. Current source also must not erase a binding historical lesson merely because a shortcut looks locally cleaner.

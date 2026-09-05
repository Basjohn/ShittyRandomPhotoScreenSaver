# Current Plan — Migration Closeout Authority

Last updated: 2026-09-05
Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

## PRE-V5 SETTINGS MIGRATION boundary

`81019d5dd196cc5522ca9041d8773c8f2fa62df3` is the immediate pre-V5 rollback/comparison boundary. Keep it distinct for Settings before/after audits and do not rewrite it into later migration history.

## Purpose — READ THIS FIRST

The Qt Quick cutover is complete. **This file now answers only one question: what still blocks declaring the migration closed?**
It is intentionally not a diary of H/I/J/V5-V8. Historical mechanism detail belongs in the durable docs listed below; future features belong in `FWPlan.md`; cleanup/test archaeology belongs in `Future_Cleanup.md` and `Docs/TestSuite.md`.

The migration is being closed using **Bubble as the visualizer reference mode** because it exercises viewport geometry, logical ~90 Hz freshness, trails/history, collisions, response amplitude, persistent GL delivery and extreme CUSTOM shapes. Sphere is dormant-by-default and explicitly **not** a migration-close visual-fidelity gate.

Current supplied source authority for this work slice remains the user's current GODZIP/tree; this assistant slice is uncommitted on top of it. Repository line-ending policy is explicit through `.gitattributes`; do not create unrelated whole-tree normalization churn.

## Migration-close sequence

### M0 — ACTIVE: Visualizer CUSTOM geometry + cross-display lifecycle integrity

**Goal:** every live Edit operation must leave one coherent geometry/lifecycle truth. **Do not undo live Edit Save.**

Operator-accepted hard contracts:

- ordinary Visualizer Edit -> Save is a live working-state -> committed-state promotion with **no teardown/reinit**;
- a successful cross-display Visualizer Edit -> Save is also **no teardown/reinit**;
- numbered layout-slot **load** is the explicit fenced rebuild/hot-swap boundary because it may change ordinary widget enabled/layout state and the active Visualizer mode;
- side handles resize viewport extent on one axis; scroll wheel uniformly scales the whole Visualizer;
- no new timer, poller, delayed geometry commit, second QML geometry authority or new render cadence.

**2026-09-05 intermittent failure reconstructed from logs:**

1. successive viewport gestures were allowed to learn different retained presentation scales, producing an impossible working pair around `649x960` pixels versus `649x1406` logical extent;
2. subsequent button and drag transfer attempts reached a target display holding a retained Visualizer admission from an **older activation** while manager-level lifecycle ownership remained on the source;
3. the scene-level target check treated that orphan shell as a legitimate second owner, permanently rejecting transfers;
4. Save then persisted split-looking placement and the following numbered slot load inherited the already-corrupt ownership state and could not recover cleanly.

**Source repair in this checkpoint:**

- [~] One Edit session owns one stable Visualizer **pixels-per-world** scalar. Side/corner viewport gestures consume it; ordinary retained presentation publications cannot silently replace it.
- [~] Visualizer **corner handles are true X/Y viewport extent handles**: both axes move independently, the opposite corner stays anchored, and `resize_scale` remains untouched. Ordinary widget corners remain uniform resize. Visualizer corner squares use a deeper blue than side handles.
- [~] Only explicit wheel uniform scaling or unavoidable cross-display target-fit projection may change pixels-per-world. Button and drag paths commit final target display/rectangle before synchronous session notification; the transfer transaction refreshes the scalar only after the manager/unit move succeeds.
- [~] A target retained Visualizer admission may be discarded **only when `DisplayManager`/the target `QuickDisplayUnit` proves it owns no Visualizer lifecycle owner**. In that case the retained identity is an orphan scene shell and only scene-local render/input admission is cleared before adopting the one live source. Any target lifecycle owner is a hard conflict and transfer rolls back.
- [x] The pre-existing discrete button-hop 1 px drift remains fixed by using a true floating geometric centre rather than integer `QRect.center()`.
- [x] Media Volume visual polish folded in without lifecycle scope: internal and external volume borders are +1 authored px (1.5 -> 2.5); neighbouring control borders are unchanged.

**Focused target-environment tests required before M0 closes:**

- [ ] `tests/test_qtquick_visualizer_custom_geometry_regressions.py` — new focused regressions for two-axis corners, stable session scale, orphan-target reconciliation, and true target-owner refusal;
- [ ] `tests/test_qtquick_custom_layout_owner.py::test_visualizer_display_hop_uses_nearest_direction_and_preserves_shape` — deterministic 1 px hop regression;
- [ ] current reconciled `tests/test_qtquick_custom_layout_owner.py` live Save / transfer / Cancel cells;
- [ ] `tests/test_qtquick_custom_layout_overlay.py` — Visualizer corner semantics/styling and ordinary-widget negative controls;
- [ ] `tests/test_layout_slots.py` — slot load remains the fenced boundary and restores active Visualizer mode;
- [ ] `tests/test_qtquick_media_presentation.py` — Media Volume border presentation contract if current suite owns that pixel/style seam.

This container has no `PySide6`/OpenGL, so Qt-bearing pytest collection remains **AWAITING TARGET ENVIRONMENT**, not failed.

**Physical M0 acceptance sequence:**

- [ ] D1 -> D0 button hop -> continue reacting -> side resize -> corner X/Y resize -> wheel resize -> Save: no restart, no empty frame, no stale source Visualizer;
- [ ] D0 -> D1 and back repeatedly, including a target-fit case: one retained Visualizer, one lifecycle owner, coherent outline/viewport geometry;
- [ ] drag across the native seam in both directions, then Save; releasing and starting a new drag permits a fresh transfer attempt;
- [ ] Cancel after a cross-display hop restores source geometry/ownership cleanly;
- [ ] after several successful live edits/transfers, load two numbered layout slots including a slot with a different Visualizer mode; rebuild completes and the selected mode becomes runtime truth;
- [ ] no `Incoherent visualizer working geometry`, `target already has a retained scene admission`, closed-pacer retirement, duplicate admission or destruction-barrier residue.

### M1 — Bubble migration-reference visual parity

**Goal:** freeze one accepted visual/scaling contract before measuring the migration gain. No more broad visualizer tuning unless evidence reopens it.

Current Bubble geometry profile is event/cached, not hot-loop classification:

- [~] canonical main-head outline floor ~**1.6 px total**; gentle area/shape firmness begins early; hard ceiling ~**4.7 px total**;
- [~] wide tail eases from ~2.5:1 to ~5.0:1 physical aspect, reaching at most **+1 big / +3 small / +20% stream baseline + cap**;
- [~] authored `bubble_big_count=0` is legitimate and ultrawide never manufactures a hero bubble from zero;
- [~] extreme vertical tail eases from ~1.5:1 to ~3.0:1 height:width, reaching at most **-1 big / -1 small / -30% stream cap**; baseline stream speed is unchanged;
- [x] viewport profile classification is recomputed only when committed geometry/domain changes and cached on simulation/Quick seams; no steady-state aspect classifier was added;
- [x] Glow is physically accepted/closed.

Operator feedback on the current curve is **very good / much more cohesive**; the only requested tail adjustment in this run is the additional 10% extreme-vertical cap reduction above.

**M1 gates:**

- [ ] `tests/test_bubble_viewport_reflow.py` — full extreme tall cap now 0.70, wide zero-big safety, bounded population modifiers;
- [ ] `tests/test_qtquick_visualizer_bubble.py` and current Bubble pixel/reaction contracts;
- [ ] eyes-on canonical, moderate wide/tall, ~6:1 ultrawide and most-extreme vertical; outline may firm gradually but must not become thin because shape is extreme or balloon at the largest area;
- [ ] preserve R-69: no global radius/reaction/Ghost/history/drift/cadence compression to make an extreme viewport fit.

### M2 — Delivery/performance + soak proof

**Goal:** measure the migrated product after M0/M1 are stable; do not optimize around corrupted geometry or diagnostics overhead.

- [ ] First representative run: `--perf --viz` **without `--usage`** on the 60 Hz display, then compare 165 Hz under the same Bubble preset/geometry.
- [ ] Bubble logical cadence remains ~90 Hz with requested/integrated revisions tracking 1:1 apart from bounded shutdown/rebuild edges; no sustained integration failures, stale-age growth or cadence collapse.
- [ ] Attribute any visible hitch from immutable logical revision/age -> Quick sync -> render-thread entry -> Bubble payload prep/transport -> uniforms/draw before changing rates or ownership.
- [ ] Use `--usage` only as a separate diagnostic run; the known heavy enumeration sample must not be confused with product steady-state performance.
- [ ] Confirm steady-state CPU/GPU/QML work, no hidden animation/polling owners, no repeated area/aspect classification, and no resource growth beyond existing bounded caches.
- [ ] Run a long normal-runtime soak after M0 is clean. Record RSS/USS/private commit, VRAM/shared GPU memory, thread/work/subscription counts, handle trend, pacer/logical cadence and retirement/barrier outcomes.

Existing evidence remains useful: prior long resource soak proved owned-resource plateau and the failed-adjustment log showed healthy ~90 Hz Bubble delivery/zero integration failures **before** geometry ownership became incoherent. Do not reopen GC/freeze or media polling without contradictory evidence.

### M3 — Destination suite + installed/product closure

**Goal:** prove the destination architecture, not museum compatibility.

- [ ] Run maintained destination profile:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [ ] Resolve every red against current Quick/event ownership. Stale QWidget/old GL overlay/native-event/polling tests are cleanup evidence, not permission to resurrect retired production seams.
- [ ] Then run the broad tree:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

- [ ] Reconcile remaining real current-owner reds; keep unrelated cleanup ledger in `Future_Cleanup.md`/`Docs/TestSuite.md`.
- [ ] Compiled/frozen/installed acceptance: 1/2/N display, mixed DPR, topology changes, Settings recreation, Media Center/screensaver entry/exit and normal shutdown.
- [ ] Complete the remaining V7 Visualizer Settings physical acceptance only where it exercises current product behavior: Media dependency disable/re-enable, Visualizers-family disable/re-enable, preserved settings, Rainbow/Custom, mode dormancy/retirement/re-enable, Settings recreation/theme inheritance.
- [ ] Final source/docs/tests reconciliation and one superseding GODZIP/checkpoint.

## Definition of migration closed

All of the following must be true at once:

- [ ] live Visualizer Edit including cross-display Save remains continuous and never needs teardown as a recovery crutch;
- [ ] no split scene/runtime/pacer/unit ownership and no incoherent rect/viewport extent can be produced by side/corner/wheel/transfer gestures;
- [ ] numbered slot load rebuilds cleanly and restores active Visualizer mode after arbitrary prior live edits;
- [ ] Bubble canonical/extreme geometry is physically accepted and preserves authored freshness/reactivity/trails;
- [ ] representative 60/165 Hz performance and long-run resource behavior show no new deterministic hitch/leak owner;
- [ ] maintained destination suite is current-owner green/useful signal and broad reds are classified/reconciled;
- [ ] compiled/frozen/installed multi-display/DPR/topology/shutdown validation is complete.

When these are green, **close the migration. Do not keep J open merely because unrelated future polish exists.**

## Closed / explicitly non-blocking for migration

- [x] Widget Glow: physically accepted/closed.
- [x] Sphere: migration checkpoint closed; current visual fidelity is rejected/deferred. `FWPlan.md` owns the exact future status: **Requires Much Higher Fidelity Assessment/Rework, keep 3D architecture work if ever retired unless it is completely superceeded - Consider Voxels?** Dormancy means disabling it has no ongoing runtime cost.
- [x] Deterministic GC/Gen2-rescan/usage-sampler owners previously attributed in P0 remain closed unless new evidence contradicts them.
- [x] Resource plateau for owned resources was proven by the 2026-09-04 ~7h53m soak; only new evidence from the current architecture may reopen it.
- [ ] Shared Widget-theme/style physical polish, narrow theme fragility, transition experiments and other Future Work are **not migration blockers** unless they expose a concrete current regression in an M0-M3 gate.
- [ ] Test/debris archaeology remains necessary maintenance but does not extend migration once maintained current-owner destination/broad gates are reconciled.

## Durable references

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`
- `Docs/QtQuick_Migration/Resource_Plateau_Soak_Closure_2026-09-04.md`
- `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md`
- `Docs/Historical_Bugs/Visualizer_Cross_Display_Split_Ownership_2026-09-05.md`
- `Docs/Future_Work/Visualizer_Edit_Geometry_And_Sphere_Materials.md`
- `Docs/TestSuite.md`
- `Future_Cleanup.md`
- `FWPlan.md`

## Golden guardrails

### Visualizer fidelity / scaling

R-69 remains binding. Bubble is the golden reference: extreme CUSTOM geometry must never be solved by globally reducing head radius, authored reaction amplitude, motion, Ghost/history displacement, or adding a second viewport/domain compensation that makes wide/tall modes less reactive. Tall-Spectrum response protection remains binding as well.

### Live CUSTOM ownership

CUSTOM outer geometry is Python/session-owned. QML reports gesture intent only. One operation must publish one coherent rectangle/extent/scale truth. Visualizer sides = one-axis viewport extent; Visualizer corners = independent X/Y viewport extent; wheel = uniform whole-Visualizer scale. Cross-display scene admission + runtime/pacer + manager unit + retirement attachment is one transaction. **Save is not a teardown boundary.**

### CUSTOM is global layout mode

The first widget entering global CUSTOM disables authored stacking/adjacency globally, including number-key saved-layout loading. Visualizer preset `Custom` is a separate concept.

### Media ownership

Do not restore fast Media polling or process-probe fallbacks. GSMTC/event ownership is primary; slow reconciliation/watchdog remains bounded degraded-path coverage. Visualizer consumes Media admission but never acquires a second Media owner.

### Performance admission

Freshness/reactivity and latency-tail quality outrank prettier aggregate counters. No optimization may silently lower authored quality. Prefer fewer/event-owned mechanisms over lower rates. See `Docs/Guardrails/Performance_Optimization_Contract.md`.

## Authority order

```text
exact current source + current reconciled test tree
-> Current_Plan.md (M0-M3 migration-close authority)
-> Spec.md
-> FWPlan.md (future/non-blocking implementation)
-> Future_Cleanup.md / Docs/TestSuite.md (cleanup + test truth)
-> historical/decomposition docs
```

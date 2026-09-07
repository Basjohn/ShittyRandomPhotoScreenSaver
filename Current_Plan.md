# Current Plan — Migration Closeout Authority

Last updated: 2026-09-08
Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

## Active planned work (linked)

- **dark.qss retirement → ThemeSpec sole authority:**
  [Docs/Settings_Dark_QSS_Retirement.md](Docs/Settings_Dark_QSS_Retirement.md).
  Execution authority for migrating the Settings dialog's colour **and** structure
  out of `themes/dark.qss` (a competing style authority: ~89 dark-only selectors,
  ~47 colours) into `SettingsThemeSpec`, so themes fully apply and the file can be
  deleted with zero dark-theme regression (byte-identity guarded). Not started.
- **SST 9/10 settings closeout reference:**
  [Docs/Future_Work/SST_9of10_Settings.md](Docs/Future_Work/SST_9of10_Settings.md)
  (settings-migration closeout evidence; defaults/plumbing working and protected).
- **Ordinary widget resize normalization → one uniform-transform seam:**
  [Docs/Future_Work/Ordinary_Widget_Resize_Normalization.md](Docs/Future_Work/Ordinary_Widget_Resize_Normalization.md).
  Move Abandonment/Achievement/Weather off per-value CUSTOM resize payloads onto the
  shared `uniformScaleTransform` seam so CUSTOM resize is geometry-only for every
  ordinary widget — and make that seam the default path so new widgets are cheap to
  add (C4 + new-widget checklist). Not started; C0 evidence harness first.
  - [ ] **Weather `preferredContentHeight` binding loop:** the physical torture run
    produced repeated QML binding-loop warnings at `WeatherPresentation.qml`'s
    `preferredContentHeight` binding during aggressive CUSTOM resize/reposition and
    multi-display geometry churn. Treat this as a small sizing-correctness/polish bug,
    not performance degradation. Repair it in the same normalization slice by making
    the Weather preferred-height path one-directional: content/scale may determine the
    preferred height, but host/parent geometry must not feed back into the same binding.
    Do not add a timer, poller, debounce, fallback size authority or second geometry
    owner. Regression bar: repeated CUSTOM resize/reposition, cross-display movement and
    runtime recreation must emit zero Weather binding-loop warnings while preserving the
    current Weather visual size, uniform scaling and stacking behaviour.
- **Visualizer replay reactivity floor (recreate for this environment):**
  [Docs/Future_Work/Visualizer_Replay_Reactivity_Floor.md](Docs/Future_Work/Visualizer_Replay_Reactivity_Floor.md).
  Rebuild the deleted replay harness headlessly and arm the 67 existing goldens'
  quantitative metrics as a **minimum bar** (thresholds below current healthy
  reactivity, which per operator experience passes today). Floors only — it never
  constrains or re-blesses current behaviour, only catches a genuine reactivity
  regression or recovers from a mistake; no exact-pixel goldens, no runtime
  coupling. Not started.
- **Gmail `_SharedGmailRuntimeOwner` timer lifecycle leak (bug):** every
  Settings/runtime reconstruction leaves **another** `_SharedGmailRuntimeOwner`
  and its poll timer registered — the shared-owner registry
  (`_SHARED_GMAIL_OWNERS` in `widgets/gmail_runtime.py`) and its
  `create_overlay_timer`/`OverlayTimerHandle` accumulate across generations
  instead of the prior owner retiring. Fix at the owning boundary: reconstruction
  must retire the previous shared owner (stop `_stop_poll_timer` and drop it from
  `_SHARED_GMAIL_OWNERS` / the overlay-timer registry) so timers do not stack —
  runtime-owned async work retires with its generation. See existing coverage
  `tests/test_gmail_retiring_runtime.py`; add a bar that fails when a
  reconstruction leaves a second live owner/timer. Not started.

## Defaults sanitization continuation — RECOVERY CHECKPOINT

After CHECKPOINT5, the working container lost the uncheckpointed source edits. The sanitization continuation is being reconstructed from the authoritative CHECKPOINT5 tree and this checkpoint is the first physical recovery boundary. Completed/reverified here: ancient Visualizer `*_growth` card-height authority retired end-to-end from live schema/UI/runtime while authored preset JSON remains untouched; Custom visualizer snapshots are user-authored state rather than canonical defaults and survive Reset/SST omission; fresh `custom_layout_restore` metadata is empty instead of duplicating widget routing defaults; the unused transition-precompute worker and obsolete QWidget Visualizer renderer package are deleted with build-tool references removed. Focused defaults/theme authority suite is 21/21 and all changed Python compiles; all 30 curated preset files remain byte-identical to CHECKPOINT5. Continue the remaining runtime/UI shadow-default scan and final tooling/Reset/SST/preset guards from this boundary.

## Defaults sanitization continuation — CHECKPOINT7

CHECKPOINT7 extends the recovered defaults sanitization boundary through strict Visualizer DSP/Quick technical admission, canonical logical-state initialization, canonical per-mode preset-index repair, removal of synthesized authored preset placeholders, and Bubble collision/reactivity parameters routed through the resolved logical contract instead of ancient local fallbacks. Focused defaults/theme authority tests remain green (21/21), all changed Python compiles, and all 30 curated preset JSONs remain byte-identical to CHECKPOINT6/5. Continue with immutable frame/render consumers, transition/image/UI shadow defaults, broader repo/default-tooling scan, then final fresh/reset/SST/preset guards.

## Migration reconciliation — build/runtime/test repair (2026-09-06, Claude)

The CHECKPOINT5 recovery reverted the earlier build audit and the settings
sanitation broke test collection + startup. Status:

**Build (done, pushed):** gl_compositor_pkg removed from the 4 Nuitka scripts,
SRPSS.ico bundled as data, PEP-503 requirement normalization + requirements_helper.txt
restored (and un-ignored), closeout/installer/defaults-audit tests reconciled.
Preflight 0 errors; 35 build tests green.

**Runtime crash fixes (done):**
- `rendering/quick/display_presenter.py` `bind_families`: the per-widget geometry
  binding was registered *after* `connect_overlay_preferred_size`, which on a
  retained-runtime **recreation** (QML items already sized) synchronously ran
  `_reflow_non_custom_layout` before the binding existed -> `RuntimeError: stack
  participant lacks resolved geometry policy: clock` -> 0 displays -> app quit.
  Fixed by registering the binding before connecting (final single reflow still
  runs). This was the fatal that killed startup on both logged runs.
- `widgets/spotify_visualizer/audio_worker.py`: `_pre_agc_bass/_mid/_treble` are in
  `_COMPUTE_SNAPSHOT_ATTRS` and assigned only lazily per-frame but were not seeded
  in `__init__` (siblings `_pre_agc_live_*` were) -> `make_compute_snapshot`
  `AttributeError` before the first frame. Seeded them in `__init__` (transient DSP
  state, not a settings default).
- `rendering/widget_descriptors.py`: `WIDGET_DEFAULT_INIT_DESCRIPTORS` requested
  unprefixed `spotify_visualizer.bar_fill_color` / `bar_border_color`, but those are
  per-mode keys (`<mode>_bar_fill_color`); the KeyError crashed `WidgetsTab.__init__`
  and thus the whole settings dialog. Removed the two descriptors -- the attrs are
  owned/seeded by `ui/tabs/media/shared_appearance_controls.py` from
  `spectrum_bar_*`. Runtime data mistaken for a plain schema default.
- `core/settings/models/_spotify_visualizer.py`: `_active_visualizer_default`
  resolved `f"{active_mode}_{key}"` unconditionally, so selecting Sphere raised 15
  KeyErrors (Sphere is deliberately excluded from `PER_MODE_TECHNICAL_MODES`).
  Fixed the resolver to mirror these fields from the reference technical mode for
  non-technical active modes (matching `_normalize_mode_name`); no canonical/snapshot
  change, schema parity intact.

**Defaults sweep results (2026-09-06):** canonical defaults audit clean (0 issues);
153 literal `_widget_default`/`_color_from_default`/`require_canonical_default`
call-sites all resolve; 34 default descriptors -> 2 stale (fixed above); per-mode x
per-key cross-check -> only Sphere (fixed above via resolver, correctly, not by
inventing `sphere_<technical>` canonical keys); all 7 settings tabs build under
fresh defaults. So the statically discoverable "runtime data mistaken for schema"
set is closed; any remaining runtime reset tracebacks need reproduction from the
app (not reproducible headless here).

**Still to investigate (repair plans):**
- Lane-aware spectrum energy computes 0.0 (tests TestLaneAwareSpectrumEnergy
  missing-bass/missing-mid). Likely the same DSP-state/defaults gap family as
  `_pre_agc_*`; verify whether the `_pre_agc` seed resolves it or a lane profile
  default was dropped. Recover the correct value from git (settings >=1.5 days ago)
  and route it through canonical Settings, not a reintroduced local fallback.
- "Reset to defaults -> missing-defaults tracebacks": the canonical defaults audit
  is clean (0 issues), so the gaps are runtime *state/attribute* inits dropped by
  the sanitation (like `_pre_agc_*`), not schema. Plan: reproduce the reset path,
  collect each AttributeError/KeyError, and for each recover the intended default
  from git history and re-home it to the correct owner (canonical Settings for
  product defaults; `__init__`/logical-state seed for transient runtime state).
- One-time large-migration reset: gate a single automatic reset-to-defaults on a
  stored schema/migration version so it fires exactly once per large migration and
  never re-wipes user state on subsequent launches. Design with the settings
  architecture (a migration-version stamp in settings_v2), not a blanket reset.

**Remaining stale tests from the migration (wind-down list, not yet repaired):**
- `tests/test_spectrum_shaping.py::TestLaneAwareSpectrumEnergy` (2) — 0.0 lane
  energy; treat as runtime/DSP, above.
- `tests/test_qtquick_ordinary_widget_host.py::test_host_module_is_presentation_only`
  — source-scan now trips on a legitimate `shiboken6` import (widget-glow work);
  allow shiboken6 like PySide6.
- `tests/test_qtquick_ordinary_widget_host.py::test_scene_controller_owns_and_retires_ordinary_widget_host`
  — same two-phase deferred-retirement offscreen behavior already reconciled for
  the overlay test; branch on `window.isSceneGraphInitialized()`.
- A full `pytest tests/` inventory is still pending (collection was unblocked this
  pass); expect more widget-glow/two-phase-retirement/defaults casualties to triage.
- Add a narrow regression bar for the `bind_families` recreation ordering fix
  (bind with a retained item reporting a synchronous size must not raise).

## PRE-V5 SETTINGS MIGRATION boundary

`81019d5dd196cc5522ca9041d8773c8f2fa62df3` is the immediate pre-V5 rollback/comparison boundary. Keep it distinct for Settings before/after audits and do not rewrite it into later migration history.

## Purpose — READ THIS FIRST

The Qt Quick cutover is complete. **This file now answers only one question: what still blocks declaring the migration closed?**
It is intentionally not a diary of H/I/J/V5-V8. Historical mechanism detail belongs in the durable docs listed below; future features belong in `FWPlan.md`; cleanup/test archaeology belongs in `Future_Cleanup.md` and `Docs/TestSuite.md`.

The migration is being closed using **Bubble as the visualizer reference mode** because it exercises viewport geometry, logical ~90 Hz freshness, trails/history, collisions, response amplitude, persistent GL delivery and extreme CUSTOM shapes. Sphere is dormant-by-default and explicitly **not** a migration-close visual-fidelity gate.

Current supplied source authority for this work slice remains the user's current GODZIP/tree; this assistant slice is uncommitted on top of it. Repository line-ending policy is explicit through `.gitattributes`; do not create unrelated whole-tree normalization churn.

## Migration-close sequence

### M0 — CLOSED: Visualizer CUSTOM geometry + cross-display lifecycle integrity

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

**2026-09-05 aggressive-edit terminalization regression (latest log):**

A later torture run proved another M0 lifecycle hole after many successful resize/display operations. The first failure was not the final `s` hang: at ~18:27:44 the first Save persisted/promoted live geometry and then `_finish()` dereferenced an ordinary retained presentation whose C++ `QQuickItem` had already died. Cleanup threw halfway through the per-display loop, leaving one display out of Edit and the other still bound to the shared session. Later context-menu actions and Cancel hit the same poisoned retained graph, and terminal diagnostics finally dereferenced an already-deleted `DisplayScene` root and aborted teardown.

Repair contract in this checkpoint:

- [~] retained ordinary presentation wrappers subscribe to their own Qt `destroyed` edge; an unexpected C++ death removes the Python wrapper immediately and records its model identity for lifecycle repair. This is event-driven and adds no polling/render cadence;
- [~] `_finish()` retires the shared coordinator and attempts cleanup on **every display** even if one scene is corrupt, then clears shared session/binding/resize ownership in `finally`. One dead display can no longer leave another half-stuck in Edit;
- [~] Cancel catches baseline-projection failure, still terminalizes the whole shared session, then requests one reconstruction from committed truth;
- [~] Save still performs **no reload at all when healthy**. Only proven live-promotion/retained-object corruption after persistence requests `save_corrupt_retained_runtime`; this is invariant repair, not a replacement for live Save;
- [~] scene/overlay/Visualizer retirement paths guard already-deleted Shiboken wrappers. `describe_scene_state()` is observational only and must never prevent destruction;
- [~] unexpected `DisplayScene` root destruction while admission remains open is now logged at the destruction edge with screen/generation and carried into CUSTOM cleanup as corruption, so a future recurrence exposes the upstream death timing instead of surfacing much later through a menu/widget dereference.

The exact upstream reason the retained root died is **not yet proven** by the old log; do not speculate it into a transfer teardown. The new destruction-edge instrumentation is intended to identify that owner if it recurs while the recovery contract prevents a half-Edit/hung application.

**Focused target-environment tests required before M0 closes:**

- [x] `tests/test_qtquick_visualizer_custom_geometry_regressions.py` — new focused regressions for two-axis corners, stable session scale, orphan-target reconciliation, and true target-owner refusal;
- [x] `tests/test_qtquick_custom_layout_terminalization.py` — all-display `_finish()` despite one failed scene cleanup, healthy live Save never requesting reload, corruption-only Save/Cancel reconstruction, and event-driven stale-wrapper ledger;
- [x] `tests/test_qtquick_retained_lifecycle_integrity.py` — detailed current-owner lifecycle matrix: coordinator + per-display cleanup failure terminalization, healthy geometry and coherent cross-display Save remaining live, slot-save deferral boundary, promotion/Cancel corruption ordering, unexpected-vs-intentional Qt-root death, admission-scoped `DisplayScene` loss, and diagnostic failure isolation;
- [x] `tests/test_qtquick_custom_layout_owner.py::test_visualizer_display_hop_uses_nearest_direction_and_preserves_shape` — deterministic 1 px hop regression;
- [x] current reconciled `tests/test_qtquick_custom_layout_owner.py` live Save / transfer / Cancel cells;
- [x] `tests/test_qtquick_custom_layout_overlay.py` — Visualizer corner semantics/styling and ordinary-widget negative controls;
- [x] `tests/test_layout_slots.py` — slot load remains the fenced boundary and restores active Visualizer mode;
- [ ] `tests/test_qtquick_media_presentation.py` — Media Volume border presentation contract if current suite owns that pixel/style seam.

This container has no `PySide6`/OpenGL, so Qt-bearing pytest collection remains **AWAITING TARGET ENVIRONMENT**, not failed.

**Physical M0 acceptance sequence:**

- [x] D1 -> D0 button hop -> continue reacting -> side resize -> corner X/Y resize -> wheel resize -> Save: no restart, no empty frame, no stale source Visualizer;
- [x] D0 -> D1 and back repeatedly, including a target-fit case: one retained Visualizer, one lifecycle owner, coherent outline/viewport geometry;
- [x] drag across the native seam in both directions, then Save; releasing and starting a new drag permits a fresh transfer attempt;
- [x] Cancel after a cross-display hop restores source geometry/ownership cleanly;
- [x] after several successful live edits/transfers, load two numbered layout slots including a slot with a different Visualizer mode; rebuild completes and the selected mode becomes runtime truth;
- [x] after an intentionally aggressive resize/display torture pass, Save/Cancel leaves **both displays** out of Edit, context-menu actions remain clickable, Esc/Settings/exit remain admitted, and there is no deleted-`QQuickItem` warning;
- [x] no `Incoherent visualizer working geometry`, `target already has a retained scene admission`, half-CUSTOM state, unexpected `DisplayScene` destruction, closed-pacer retirement, duplicate admission or destruction-barrier residue.

### M1 — CLOSED: Bubble migration-reference visual parity

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

- [x] `tests/test_bubble_viewport_reflow.py` — full extreme tall cap now 0.70, wide zero-big safety, bounded population modifiers;
- [x] `tests/test_qtquick_visualizer_bubble.py` and current Bubble pixel/reaction contracts;
- [x] eyes-on canonical, moderate wide/tall, ~6:1 ultrawide and most-extreme vertical; outline may firm gradually but must not become thin because shape is extreme or balloon at the largest area;
- [x] preserve R-69: no global radius/reaction/Ghost/history/drift/cadence compression to make an extreme viewport fit.


**Closure evidence:** Claude's focused M0 + Bubble gate is green offscreen and on real monitors; the deterministic 1 px hop regression is green. The operator then completed an aggressive multi-display Edit/Save/Cancel/slot-load torture run without the prior split-CUSTOM or stale-root failure. Bubble is visually accepted and its logical/audio lane remained healthy. Reopen M0/M1 only on contradictory new evidence.

### M2 — ACTIVE: destination suite + build/install/product readiness

**Goal:** make the actual frozen product authoritative before spending the final overnight soak on it. Build/tool/install defects are migration blockers; future visual polish is not.

- [x] M0 focused gate is green on real hardware; M1 Bubble is operator-accepted.
- [~] Reconcile the maintained destination profile. Current remaining reds are outside closed M0/M1 and must be classified against intentional current product changes rather than resurrecting retired owners.
- [~] Audit both normal/global-Python and repo-venv Nuitka families so lazy Qt Quick/Visualizer/GL/audio imports are explicitly packaged rather than left to discovery.
- [~] Build preflight/post-build validation must require QML, baked QSBs, Visualizer shaders, shipped themes, Widget Themes, visualizer presets, notification/Jedi sounds and pinned Qt Quick/QML/QtMultimedia dependencies.
- [~] Diagnostic onefile must be self-contained: bundled themes/presets are its authority because its lowest-privilege installer intentionally does not seed ProgramData. Standard SCR and Media Center keep the shared ProgramData theme/preset authority.
- [ ] Add the real `resources/jedimodeyall.mp3`; Jedi Mode build preflight intentionally fails until the authored asset exists.
- [ ] Build Diagnostic EXE, standard SCR/onefile and MC onedir with current scripts; verify source preflight and post-build payload checks.
- [ ] Validate installers/upgrades carry current presets/themes/sounds without stale renamed files, and that Settings/Widget Theme paths resolve correctly per product profile.
- [ ] Run the destination profile from the resulting product tree where applicable, then broad-tree classification; no legacy architecture may be restored for museum tests.
- [ ] Compiled/frozen acceptance: 1/2/N display, mixed DPR/topology, Settings recreation, Media Center/screensaver entry/exit, mode dormancy, and clean shutdown.

**Small non-blocking polish folded into this build slice:** DevCurve travel now integrates a smoothed cruise phase with only ±10% audio speed breathing instead of a ~12x reactive throttle/re-phase; its lines gain +1 px total at canonical and ease to +3 px total at the largest viewport. Jedi Mode is a default-OFF easter egg using existing hover/click edges + EventSystem and a hard two-player QtMultimedia pool; no timer/poller/queue/frame owner.

**Defaults authority repair folded into this build slice:** `ui.settings_theme_selection` is now present in canonical Normal defaults/snapshot and missing Settings/Widget theme state resolves from that authority. The follow-up full defaults audit removed nested+dotted duplicate representations, live Settings/session captures, transition runtime-history fields and retired global preset payloads; added the real missing cache/history defaults; moved MC-only `mc.always_on_top` to the MC profile override; and made fresh-install seeding, Reset, SST/default projection and flattened-shape repair follow the shared structured-root contract. Defaults Foundry is now the product-default authority rather than one of several competing sources. The deeper sanitization also fixed explicit-`None` persistence (missing and JSON null are no longer conflated), removed dead Visualizer default leaves that normalization already discarded, added the genuinely persisted Sphere per-mode Rainbow defaults, and is removing UI save-side fallback literals. **Curated Visualizer preset JSON remains a separate highly-authored overlay authority and must stay byte-identical through this pass; Custom snapshots remain user-authored state and partial-profile repair must never deep-merge defaults into an existing Custom cache.** Fresh-profile Settings buckets are now explicitly collapsed by canonical `ui.*_bucket_states`; persisted expansion state still overlays normally. Steam/Achievement/Abandonment retained model defaults now project canonical Widget defaults instead of maintaining stale local copies; presentation-only geometry constraints remain local. Capability activation/pool, Display and Transitions defensive reads now resolve missing/invalid product state through canonical defaults rather than local literals, and the retained Phase-C parameter resolver no longer carries a duplicate table of Transition defaults.

### M3 — frozen-product performance + overnight soak proof

**Goal:** measure the actual end product after M2 proves the package is complete. Python/dev-run soak is supporting evidence only; the frozen diagnostic/SCR product is final authority.

- [ ] Representative clean run: `--perf --viz` without `--usage` on 60 Hz, then 165 Hz under the same accepted Bubble preset/geometry.
- [ ] Bubble logical cadence remains ~90 Hz with requested/integrated revisions tracking 1:1 apart from bounded shutdown/rebuild edges; no sustained stale-age growth, integration failures or cadence collapse.
- [ ] Attribute any visible hitch from immutable logical revision/age -> Quick sync -> render-thread entry -> Bubble payload prep/transport -> uniforms/draw before changing rates or ownership.
- [ ] Use `--usage` only as a separate diagnostic run; heavy process/resource enumeration must not be confused with product steady-state performance.
- [ ] Run the valuable overnight soak on the frozen Diagnostic EXE renamed/used as the `.scr` product path, with ordinary runtime behavior rather than torture Edit. Record RSS/USS/private commit, VRAM/shared GPU memory, thread/work/subscription/handle trend, pacer/logical cadence, stale-frame tails and retirement/barrier outcomes.
- [ ] Confirm process exits cleanly without log-autozip. If lingering reproduces only with autozip, classify/fix the logzip terminal owner separately; if it reproduces without autozip, reopen lifecycle closure immediately.

Existing evidence remains useful: the prior ~7h53m resource soak proved owned-resource plateau; subsequent torture runs show healthy ~90 Hz logical delivery and zero integration failures through aggressive geometry/display changes. M3 is confirmation on the actual frozen product, not a license to reopen already-closed architecture without contrary evidence.

## Definition of migration closed

All of the following must be true at once:

- [ ] live Visualizer Edit including cross-display Save remains continuous and never needs teardown as a recovery crutch;
- [ ] no split scene/runtime/pacer/unit ownership and no incoherent rect/viewport extent can be produced by side/corner/wheel/transfer gestures;
- [ ] numbered slot load rebuilds cleanly and restores active Visualizer mode after arbitrary prior live edits;
- [ ] Bubble canonical/extreme geometry is physically accepted and preserves authored freshness/reactivity/trails;
- [ ] maintained destination/build/install path is current-owner complete, including Qt Quick/QML/Multimedia assets, themes/presets and installers;
- [ ] compiled/frozen/installed multi-display/DPR/topology/shutdown validation is complete;
- [ ] representative 60/165 Hz performance and frozen-product overnight resource behavior show no new deterministic hitch/leak/stale-frame owner.

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
## Defaults sanitization checkpoint status — 2026-09-06

- [x] CHECKPOINT8: strict Visualizer immutable frame/render contract. Logical + presentation configuration is canonical-seeded then resolved-overlayed; active render consumers no longer own fallback tuning tables.
- [x] Structural guard proves removed shadow defaults do not leave live Visualizer settings barren; retired glow/growth keys have no active consumers.
- [x] Focused authority/theme suite: 22 passed; changed Python compiles; all 30 curated preset JSONs hash-identical to CHECKPOINT7/6/5.
- [ ] Remaining: transition/image/UI shadow-default scan, broader repo/default-tooling compatibility audit, fresh/reset/SST/Custom/preset final guards, final superseding GODZIP.


## Defaults sanitization checkpoint status — CHECKPOINT9

- [x] Transition requests resolve type/random/hardware/duration/per-type fields through canonical transition authority; renderer/request code no longer substitutes Crossfade/1300 product defaults.
- [x] Image prescale/prefetch workers require resolved display mode/Lanczos/sharpen inputs; dead QPixmap ImageProcessor duplicate authority removed.
- [x] Visualizer card Settings/theme fields are resolved before Quick admission and shell resize/render consumers are strict; presentation-only shell shape constants remain explicit presentation constants.
- [x] DevCurve logical/frame solver requires canonical-seeded layer parameters and authored shape nodes instead of emergency local baselines.
- [x] Focused authority/theme suite: 23 passed; changed Python compiles; all 30 curated Visualizer preset JSONs hash-identical to CHECKPOINT8/7/6/5.
- [ ] Remaining: Settings/model/runtime secondary-default scan, default-related tooling compatibility audit, final fresh/reset/SST/Custom/preset gates, final GODZIP.

## Defaults sanitization CHECKPOINT10 — strict shadow/runtime routing boundary (2026-09-06)

- [x] Global Widget shadow persisted repair is owned once by `ShadowSettings.from_settings()` using canonical defaults.
- [x] Retained Quick Context Menu / Reddit / Gmail / Media / Clock / Weather / Steam / Visualizer shell consume one complete strict generation shadow snapshot; removed downstream `SE` / `18` / `.77` / `.33` / black / `True` product fallbacks.
- [x] Gmail runtime persisted cadence/filter/sound settings seed and repair from canonical `widgets.gmail`; stale 50% sound-volume authority removed (canonical is 25%).
- [x] `get_default_settings()` no longer redundantly seeds Visualizer `enabled=True` / `monitor=ALL` before normalization.
- [x] Display monitor topology repair resolves malformed/unavailable persisted routing through canonical `display.show_on_monitors` rather than an inline `ALL` product default.
- [x] CUSTOM ordinary-item admission repairs missing enabled state from the widget's canonical section; incomplete restore metadata no longer invents monitor `ALL`.
- [x] Effective widget monitor routing derives missing state from each widget's canonical routing section.
- [x] Verification: 20/20 focused authority tests pass; 16 changed Python files compile; 30/30 curated Visualizer preset JSONs remain hash-identical to CHECKPOINT5.
- [x] CHECKPOINT10 packaging must use the original supplied GODZIP manifest schema exactly; archive/manifest integrity is mechanically validated before delivery.
- [ ] Continue broader Settings/model/runtime shadow-default scan.
- [ ] Run broader fresh-profile / Reset / SST / Custom preservation guards.
- [ ] Audit/migrate all repo tooling that reads/writes defaults/schema, without reintroducing shadow authority.
- [ ] Final full compile/test/preset guards and superseding sanitized GODZIP.
- [ ] After defaults sweep only: investigate/remove `dark.qss` lifecycle dependency without destabilizing theme semantics.

## Defaults sanitization CHECKPOINT11 — Settings preview / headless tooling boundary (2026-09-06)

- [x] Settings constructor/save enum repair routes Gmail date mode, Clock format/timezones/calendar layout, Accessibility values, Display glow/interaction values, Bubble/DevCurve UI values, and shadow toggles through canonical active-profile defaults rather than stale UI literals.
- [x] WidgetsTab stack-preview descriptors no longer copy per-widget enabled/position/monitor/font/limit defaults; missing controls project from each widget's canonical section.
- [x] CUSTOM position-option descriptors carry identity only; recovery position resolves from the effective canonical widget section.
- [x] `core.settings` package import is headless-safe via lazy `SettingsManager` export, so defaults/schema tooling does not require PySide6 merely to import canonical builders.
- [x] `defaults_snapshot_builder` now provides deterministic `--check` / explicit `--write`; stored `defaults_snapshot.json` exactly matches the canonical derivative.
- [x] Stale references to an absent `tools/default_settings_editor.py` were removed from canonical data-module docs; generated artifacts are explicitly derivative, never authority.
- [x] Verification: 22/22 focused authority tests pass; 17 Python files changed since CHECKPOINT10 compile; 30/30 curated Visualizer presets remain byte-identical to CHECKPOINT5.
- [ ] Continue final broader Settings/model/runtime scan and fresh-profile / Reset / SST / Custom integration guards.
- [ ] Final audit of any defaults-aware repo tooling actually present in the supplied tree; do not overwrite omitted/external tooling by inventing replacements.
- [ ] Final full compile/test/preset/manifest gate and sanitized superseding GODZIP.
- [ ] After defaults sweep only: investigate/remove `dark.qss` lifecycle dependency.


## Defaults sanitization CHECKPOINT12 — profile / SST / Custom authority boundary (2026-09-06)

- [x] MC profile overrides now contain only genuine behavioral differences; representation-only Gmail/Media monitor `"2"` overrides are removed.
- [x] Canonical widget-position enums parse strictly from canonical schema; only persisted/migration input may repair to that parsed canonical value.
- [x] SST replace begins from the same `get_flat_defaults(profile)` projection as fresh/reset, preserves user-authored Custom snapshots when omitted, and replaces them only when explicitly supplied.
- [x] SST export consumes the manager-owned resolved profile identity; there is no transport-level fallback to `Screensaver`.
- [x] Derived snapshot construction requires its canonical structured sections instead of manufacturing missing empty maps.
- [x] Verification: 25/25 focused authority tests pass; all Python changed since CHECKPOINT11 compiles; defaults snapshot check passes; 30/30 curated Visualizer presets remain byte-identical to CHECKPOINT5.
- [ ] Final repo-wide secondary product-default authority scan and cleanup.
- [ ] Final audit of defaults-aware repo tooling actually present in the supplied authoritative tree.
- [ ] Final full fresh/reset/SST/preset/compile/manifest gate and sanitized superseding GODZIP.
- [ ] After defaults sweep only: investigate/remove `dark.qss` lifecycle dependency.

## Defaults sanitization CHECKPOINT13 — permanent authority guard boundary (2026-09-06)

- [x] Added headless `core/settings/defaults_authority_audit.py` and `tools/check_defaults_authority.py`; current authority audit passes with zero violations and without exemption tables.
- [x] Normal product-build preflight paths invoke the defaults-authority audit so stale snapshots, revived defaults mirrors, direct authority bypasses, or default-constructible resolved presentation configs can fail builds.
- [x] Deleted unused `core/settings/defaults_generated.py` and `core/settings/defaults_snapshot.py`; the deterministic JSON snapshot builder is the sole generated defaults derivative.
- [x] Retained Quick widget presentation configs are no longer default-constructible product-default tables; persisted fields arrive through canonical-aware projection, semantic-only colours remain semantic/theme-owned.
- [x] Remaining Settings/runtime literal repair cleaned across Reddit/Weather/Gmail/Clock/Media/Steam/Accessibility/Transitions/Visualizer paths; strict canonical roots replace empty-map fallback construction.
- [x] Independent scan removed residual Sphere/Slide/Spectrum shadow defaults; current Spectrum repair table retains only historical migration signature data.
- [x] Verification: authority audit clean; 25/25 focused authority tests pass; all Python changed since CHECKPOINT12 compiles; defaults snapshot check passes; 30/30 curated Visualizer presets remain byte-identical to CHECKPOINT5.
- [ ] Finish independent repo-wide ownership/literal scan and classify remaining algorithm/session/presentation constants.
- [ ] Run final fresh-profile / Reset / SST / Custom / runtime integration guards plus full Python compile.
- [ ] Final defaults-aware tooling/build audit and final sanitized superseding GODZIP.
- [ ] After defaults sweep only: investigate/remove `dark.qss` lifecycle dependency.

## CHECKPOINT14 — final sweep boundary (2026-09-06)
- [x] Canonical bool missing-key repair fixed in SettingsManager.get_bool.
- [x] Early GL startup preferences derive from canonical display defaults.
- [x] Quick Visualizer renderer parameters/colours are strict immutable-frame inputs.
- [x] Defaults authority audit expanded for direct editable-default imports, raw QSettings product literals, bool coercion bypasses, and renderer fallbacks.
- [x] 28 focused authority tests pass; snapshot parity passes; full active Python compile passes; 30/30 curated presets byte-identical.
- [ ] Final independent secondary-authority classification scan.
- [ ] Final fresh/Reset/SST/Custom integration gate and superseding sanitized GODZIP.
- [ ] Separate post-sweep theming lifecycle cleanup (`dark.qss`) only after defaults work is closed.

## CHECKPOINT15 — defaults authority sanitization CLOSED (2026-09-06)

- [x] Post-CHECKPOINT14 authority audit clean after the final registry/descriptor/CUSTOM cleanup.
- [x] Focused defaults-authority suite passes **29/29**.
- [x] `defaults_snapshot.json` exactly matches the canonical deterministic builder.
- [x] Full first-party Python syntax compile passes **434/434** files.
- [x] All **30/30** curated Visualizer preset payloads are directly byte-identical to the actual CHECKPOINT5 archive.
- [x] Final repo-wide literal/ownership classification found no remaining secondary product-default table. Remaining literals are explicit algorithm/presentation constraints, migration signatures, recovery/session sentinels, platform constants, or separate compiled theme authority.
- [x] Permanent defaults-authority audit now scans all first-party Python, including `tools/`, helpers/providers and root entrypoints; only tests, caches, virtual environments and deletion staging are excluded.
- [x] `Docs/Guardrails.md` now carries the concise canonical-default prohibitions; defaults-aware tooling may not become a second authority or narrow the audit to hide violations.
- [x] Historical record added: `Docs/Historical_Bugs/2026-09-06_Canonical_Defaults_Authority_Fragmentation.md`.
- [x] Retired Python mirrors remain deleted: `core/settings/defaults_generated.py` and `core/settings/defaults_snapshot.py`; final GODZIP records them as explicit reversible debris moves rather than relying on omission.
- [x] Final superseding GODZIP rebuilt with the last known-good `srpss-godzip` manifest schema; full ordinary payload preservation, manifest size/SHA parity, member inventory and ZIP CRC are mechanically verified.
- [ ] **NEXT SEPARATE SLICE ONLY:** investigate/remove the `dark.qss` lifecycle dependency without reopening canonical-default sanitization unless one of the permanent gates proves a real regression.


## CHECKPOINT16 — defaults documentation / dormancy authoring closeout (2026-09-06)

- [x] `Docs/Defaults_Guide.md` now describes the post-sanitization single-authority contract, canonical missing-key resolution, structured-root/Foundry boundaries, and safe add/remove rules for widget-family and transition capabilities.
- [x] `Docs/10_WIDGET_GUIDELINES.md` now makes family activation, ordinary enabled state, catalog/descriptor ownership and provider/import dormancy explicit so families can be added or retired without parallel registries or hidden runtime owners.
- [x] `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md` and `Docs/Transition_Change_Checklist.md` now make registry/default/implementation ownership, lazy import dormancy, packaging visibility and coherent add/remove retirement explicit.
- [x] `Docs/TestSuite.md` records the permanent 29-test `tests/test_defaults_schema_authority.py` gate and its whole-first-party-Python audit coverage.
- [x] Packaging self-audit caught and repaired a CP15 over-broad virtual-environment exclusion: project-owned `scripts/venv/*.ps1` build scripts are ordinary payload and must never be excluded merely because a path component is named `venv`.
- [x] Final documentation gate: defaults authority **29/29**, authority audit clean, deterministic defaults snapshot exact; no product-default values changed in this documentation slice.
- [ ] Product decision only: review the new-user default recommendations from this checkpoint before intentionally changing canonical values and regenerating snapshot/SST artifacts.
- [ ] **NEXT SEPARATE SLICE ONLY:** investigate/remove the `dark.qss` lifecycle dependency without reopening canonical-default sanitization unless one of the permanent gates proves a real regression.

## CHECKPOINT17 — approved new-user defaults baseline (2026-09-06)

- [x] Standard/Screensaver widget routing baseline moved to **Display 1** for every widget/Visualizer section that owns a monitor route; no ordinary `enabled` values were changed by this tranche.
- [x] MC preserves its established routing through genuine profile overrides: existing Display-2 and `ALL` widget routes remain MC-specific rather than inheriting the new standard Display-1 baseline.
- [x] Spotify Visualizer remains **ON** by default and its default mode changed from DevCurve to **Bubble** through canonical settings; existing Media/now-playing admission keeps it dormant when there is nothing to visualize. Experimental Sphere remains excluded from canonical `enabled_modes`, so Sphere stays dormant until explicitly enabled.
- [x] Weather remains **ON** with blank location and Display 1; location remains user-specific/preserved rather than baked into defaults.
- [x] Gmail remains **ON** and moves to Display 1 in the standard profile; MC Gmail remains Display 2.
- [x] Default Settings theme remains `Default Dark [Single] [Glass]`; Widget Theme stays linked to `default_dark`; all canonical UI bucket-state maps remain collapsed.
- [x] Transitions remain in canonical Random mode via `transitions.random_always=True`; the remembered manual `type` is not rewritten to the retired `"Random"` sentinel and saved Random-pool membership was not opportunistically changed.
- [x] `core.settings.defaults_snapshot_builder` now regenerates/checks the JSON snapshot plus both checked-in Normal/MC SST defaults documents (`--write-all` / `--check-all`) directly from canonical source; no absent legacy generator is required.
- [x] `Docs/Defaults_Guide.md` and `Docs/TestSuite.md` record the approved baseline and deterministic regeneration path.
- [x] Focused defaults-authority gate expanded to **30 tests** and passes 30/30.
- [x] Final CHECKPOINT17 packaging gate: authority audit clean; `--check-all` exact; **434/434** Python compile; direct **30/30** CP5 preset byte parity; **534** manifested payload files with exact member/SHA/size verification and clean ZIP CRC; all four project-owned `scripts/venv/*.ps1` files retained.
- [ ] **NEXT SEPARATE SLICE ONLY:** `dark.qss` lifecycle/theming cleanup.

## CHECKPOINT18 — 5.0.0 installer migration-reset safety (2026-09-06)

- [x] Standard and MC installer `resetsettings` tasks default checked for **5.0.0 only**, with inline source comments requiring the default-on policy to be reconsidered after the migration release.
- [x] A selected reset is now complete: it deletes the profile's `settings_v2.json` **and** matching pre-JSON Qt `QSettings` registry tree, preventing first v5 launch from immediately re-importing the state the installer intended to discard.
- [x] Diagnostic intentionally remains reset-OFF by default because it consumes the ordinary SRPSS profile, but an explicitly selected Diagnostic reset now also clears both JSON and legacy QSettings.
- [x] `Docs/Defaults_Guide.md` records the real error/migration behavior: malformed JSON/invalid snapshot regenerates canonical defaults; valid historical state is migrated/repaired conservatively and unknown-but-valid semantics may survive unless reset.
- [x] Historical bug record added: `Docs/Historical_Bugs/Installer_Reset_Reimported_Legacy_QSettings_2026-09-06.md`.
- [x] New permanent installer policy guard `tests/test_installer_v5_reset_policy.py`; focused defaults + installer gate passes **32/32**.
- [x] Defaults authority audit clean; deterministic defaults snapshot exact; first-party Python compile **435/435**.
- [ ] Separate architectural follow-up candidate: normalize Weather/Steam CUSTOM sizing away from legacy per-value payload routes before allowing the non-CUSTOM stacker to apply transient automatic shrink broadly.
- [ ] `dark.qss` lifecycle/theming cleanup remains a separate task.

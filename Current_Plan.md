# Current Plan — Qt Quick Production Migration

Last updated: 2026-09-01

## Current checkpoint

**PHASE H CLOSED. PHASE I ACTIVE.**

The production Qt Quick authority cutover, post-cutover functional/runtime correction work, and heavy-load H performance acceptance are complete at the current source checkpoint. The detailed H acceptance record is preserved in:

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/Historical_Bugs/README.md`
- `Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`
- `Docs/Guardrails/Performance_Optimization_Contract.md` — canonical post-H performance admission/acceptance rules and modest/heavy reference envelopes.
- the superseded H5c/R6/R7 checkpoint documents retained for provenance.

Do **not** repopulate the active work queue with hundreds of stale completed H sub-items. Preserve H as a compact **completed checklist** here and keep the detailed evidence in its closure/historical records. If later evidence falsifies an accepted H contract, reopen the smallest demonstrated owner/incident and repair it; do not revive H wholesale.

**Checklist discipline is mandatory:** every phase in this plan has an explicit checkbox list. Completed phases keep a compact checked closure list; the active phase owns detailed actionable checkboxes; queued phases keep enough unchecked acceptance/work items that the next agent can enter them without reconstructing intent.

### Test-run qualification at H closure

The complete test tree was reconciled against current production/source authority. The closure environment has `pytest` and NumPy but does **not** have PySide6 or PyOpenGL, and `tests/conftest.py` imports PySide6 unconditionally. Therefore no new Qt aggregate pass count is claimed here.

The canonical maintained destination profile is now:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

`h-destination` remains a temporary compatibility alias only. The **first Phase-I gate** is to run `destination` in the normal project environment with PySide6/OpenGL available. A red is evidence to classify; it is never permission to restore a deleted QWidget/GL owner or a retired fallback.

## H closure summary

### H completed checklist

- [x] One selected physical display -> one standalone `QQuickWindow` -> one threaded Quick scene graph/runtime scene.
- [x] Old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical presentation authority remains deleted.
- [x] H1a/H1b lifecycle/recreation/terminal retirement accepted.
- [x] H2/H3/H3b/H4 family/product runtime semantics accepted.
- [x] H5a/H5b visualizer routing/topology accepted physically.
- [x] H5c visualizer reactivity/performance accepted at the heavy-load H boundary; residual optimization debt moved to J.
- [x] H6 Media CUSTOM Settings lock semantics accepted.
- [x] H7 visible Exit response accepted.
- [x] H8 middle-click same-mode preset cycling/Custom round-trip accepted physically.
- [x] H9 ordinary-family uniform resize accepted, including absolute persisted 40% floor and Gmail whole-card scaling.
- [x] R6 native-`QCursor` Halo architecture accepted and protected.
- [x] R7 transactional image admission/prefetch wake accepted; timer/manual transitions are the same performance class.
- [x] R-63 black-flash prevention accepted with `black=0`; bounded mixed-DPR shared-edge pixel overshoot tolerated rather than risking exact-cover fullscreen promotion.
- [x] Media fast polling retired in favor of event ownership plus slow reconciliation/watchdog.
- [x] Final heavy-load Visualizer audio lane/state work materially reduced GC frequency without sacrificing logical cadence/reactivity.
- [x] H closure docs/tests reconciled enough to hand authority to the phase-neutral `destination` profile and Phase I cleanup.

The final heavy-load performance evidence is intentionally **not** an invitation to chase counters further inside H. Representative accepted evidence:

```text
Visualizer logical publication: ~89-90 Hz when active
Typical snapshot age:           ~18-22 ms
Audio analysis mean compute:    ~1.86 ms
Audio callback work:            ~0.067 ms
Generic per-frame Future path:  0
Final heavy-load gen-0 rate:    ~9.8 collections/s
Final heavy-load gen-2 rate:    ~0.39/min
Residual deep gen-2 pauses:     ~130-146 ms in that run
```

Those residual deep pauses are real J/end-performance debt. They are **not** permission to reduce authored work, cadence, freshness, response amplitude, motion, viewport scaling, newest-state semantics, or visible fidelity.

## Golden guardrails carried into I/J

Performance work in I/J must also follow `Docs/Guardrails/Performance_Optimization_Contract.md`. That document owns the permanent rule that **freshness/reactivity and latency-tail quality outrank prettier aggregate counters**, plus the 2026-09-01 heavy/modest reference envelopes.

### 1. Visualizer reactivity/freshness is sacred

Priority order remains binding: authored fidelity/reactivity outranks lifecycle counters, frame-pacing averages, task-count elegance and FPS cosmetics.

Never “fix” performance or extreme geometry by:

- lowering the authored/logical Visualizer cadence;
- adding a debounce/catch-up FIFO/backlog between current source and newest-state presentation;
- allowing stale source/snapshot age to rise while pixels continue;
- globally compressing Bubble head radius, pulse amplitude, motion, Ghost/history displacement or another mode's authored reaction as viewport extent grows;
- applying a second `baseline/current` or `1 / viewport_extent` compensation to state already normalized into renderer-content coordinates;
- retuning DSP/gain/cold-play response to hide a presentation/geometry defect;
- restoring per-frame generic `Future`/task submission for audio analysis;
- removing the stable previous-bars packet snapshot merely to improve allocation counters without a replacement correctness proof.

**R-69 is the golden Bubble scaling lesson.** Canonical, wide and tall CUSTOM geometry must preserve the same authored response character. Bubble's renderer-facing head radius stays the authored fraction of actual card height. Ghost consumes already-normalized history exactly once. The accepted compact ripple-wake projection is a separate effect and must not be generalized to head/Ghost state. If an extreme full-expansion head is visually too large, fix only a proven upper visual tail without flattening the full response curve.

Apply the same reasoning to Spectrum/Oscilloscope/Sine/DevCurve: geometry adaptation may reframe/reflow/smooth presentation, but may not quietly weaken musical response.

### 2. Visualizer audio compute ownership

Current accepted path:

```text
one shared BeatEngine
-> one persistent serial visualizer.audio_analysis compute lane
-> one in flight + newest pending source replacement
-> retained detached DSP state across ordinary frames
-> rebuild only at real config/activation/reset epoch boundaries
-> immutable newest logical/render publication
```

No generic Future fallback. Lane creation failure must be loud. Config/reset crossing an in-flight computation fences the stale result. Keep the small stable previous-bars tuple because the live silence path may mutate the backing list in place.

Further GC work belongs near the end of J and must start from allocation/lifetime evidence. Do not tune collector thresholds simply to make counters prettier, and do not trade response latency/reactivity for fewer collections.

Historical performance record: `Docs/Historical_Bugs/R-71_Visualizer_Audio_Per_Frame_Task_And_DSP_State_Allocation.md`.

### 3. R-63 seam / black-flash priority

The no-black-flash contract outranks exact shared-edge pixel perfection.

Current native evidence on the operator's mixed-DPR pair showed Display 0's intended exterior/top overscan rounding to a `2561`-device-pixel window over a `2560`-pixel monitor, overlapping Display 1 by one device pixel. That explains the intermittent seam pixel.

A **bounded 1px overshoot is acceptable** while `black=0` remains true. Any later refinement must derive device-space coverage from actual monitor rectangles/DPR and remain valid across different resolutions, coordinates, monitor ordering and DPR combinations (including 1.0/1.25/1.5/1.75/2.0 and mixed-DPR). Never hard-code the current monitor pair, force exact cover, or remove R-63 overscan generically.

### 4. CUSTOM resize authority

Ordinary CUSTOM scale is absolute against stable authored/preferred size, persisted across sessions, with shared **40% floor**. A new session must not treat an already-scaled committed rectangle as a fresh 100% baseline.

Reddit/Reddit2, Media and Gmail use whole-card retained `uniformScaleTransform`; fixed chrome/text/rows/spacing scale with the card. Gmail's model width is already outer width; only row-derived preferred height receives the shell inset. Visualizer remains on its independent `uniform_visual_scale` + `viewport_extent` contract.

### 5. Media event ownership

Do not restore fast Media polling or process-probe fallback. Native GSMTC event/session observation is primary. The slow reconciliation/watchdog is deliberate safety coverage and degraded observation must be conspicuous in logs.

### 6. Native Cursor Halo

Passive pointer motion must not become QML scene invalidation again. Halo position/visibility is native cursor presentation through `QuickCursorController`/`QCursor`; QML retains only semantic interaction/Ctrl state where needed. The orphan `rendering/quick/qml/CursorHalo.qml` is I deletion residue, not a dormant fallback.

## Phase I — ACTIVE: caller-proven residue reconciliation

I is intentionally source-driven cleanup. It must make the tree tell the truth about the already-accepted destination; it must not redesign production behavior.

### I0 — deterministic destination gate

- [ ] Apply the H-closure test/doc patch.
- [ ] Manually delete only the tests explicitly listed under **Immediate manual deletions** below.
- [ ] In the normal PySide6/OpenGL project environment run:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [ ] Inspect both Python and Qt/QML diagnostics for any runtime-shaped targets that emit them.
- [ ] Classify every red as current-source defect, stale residue, environment-specific physical gate, or brittle assertion. Never restore a retired owner to satisfy a stale test.
- [ ] Resolve/rehome every `destination` red or explicitly mark a genuinely operator-only validation gate before moving deeper into I.

### Immediate manual deletions

These are already caller/contract-proven enough that preserving them adds fake authority:

- [ ] Delete `tests/test_settings_sync.py` — tombstone only; no executable tests.
- [ ] Delete `tests/test_phase_e_effect_corruption.py` — historical `QGraphicsEffect` corruption investigation; current focus/native-event coverage lives elsewhere.
- [ ] Delete `tests/test_visualizer_preset_cycling_runtime.py` — imports deleted QWidget `InputHandler`/`WidgetManager`/`SpotifyVisualizerWidget`; surviving same-mode preset, Custom round-trip and mode-owned audio-setting contracts are already covered by current Quick/logical tests.

Generated test cache (`tests/.pytest_cache/`, `tests/**/__pycache__/`, `*.pyc`) is never source authority and can be removed locally at any time.

### I1 — exact stale-owner test/tool reconciliation

Use `Docs/TestSuite.md` as the live inventory. Highest-confidence residue already identified:

- [ ] Reconcile old GL/compositor transition and rendering tests.
- [ ] Reconcile old compositor metrics/GPU-query/fallback tests.
- [ ] Reconcile old visualizer physical-host/card geometry tests.
- [ ] Reconcile `tests/test_spotify_visualizer_widget.py` importing deleted overlay/host code.
- [ ] Reconcile `tests/test_visualizer_replay.py` + `tools/visualizer_replay.py` referring to deleted replay-runtime ownership.
- [ ] Reconcile old MC physical-window implementation tests where current Quick role/policy tests own the surviving contract.
- [ ] For every candidate deletion/rehome: identify the exact surviving product-neutral contract and prove its current owner/test first.
- [ ] Do not mass-delete by filename/phase prefix; record each resolved owner/removal in `Docs/TestSuite.md` / cleanup ledger.

### I2 — source/tool residue

After exact caller search:

- [ ] Delete orphan `rendering/quick/qml/CursorHalo.qml` if still unreferenced.
- [ ] Remove caller-dead Media process-probe helpers retired by event ownership.
- [ ] Remove old physical-presenter/compositor aliases/adapters/comments/spikes that no longer have a production caller.
- [ ] Reconcile regeneration/default tools against current Settings/Quick schema before using them.
- [ ] Preserve neutral transition registry/settings/math/shaders and neutral visualizer DSP/logical algorithms used by Quick.
- [ ] Re-run exact caller/import searches after each residue batch so deletion does not create hidden compatibility fallback pressure.

`Future_Cleanup.md` owns the detailed deletion ledger.

### I3 — whole-tree truth restoration

After bounded residue batches:

- [ ] Run the maintained destination authority:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [ ] Run the broad whole-tree gate:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

- [ ] Confirm the first command remains GREEN production authority.
- [ ] Drive the second away from deleted-owner/museum failures until it is a useful broad gate again.
- [ ] Sweep current docs/test inventory after the final residue batch so source, tests and authority documents agree before I closes.

### I exit checklist

- [ ] Canonical `destination` profile GREEN in the real project environment.
- [ ] No current tests import deleted physical owners merely to preserve migration history.
- [ ] Whole-tree collection has no caller-dead-owner import failures.
- [ ] Source/tool residue has exact caller proof before deletion.
- [ ] No compatibility alias/fallback can silently recreate a second presenter/analysis/polling authority.
- [ ] `Docs/TestSuite.md`, `Future_Cleanup.md`, migration docs and source agree on owner map.
- [ ] No change violates the golden Visualizer/R-63/Media/CUSTOM guardrails above.
- [ ] Historical-bug records exist for any newly resolved or instructively failed I incidents before the phase is closed.
- [ ] `Current_Plan.md` is compactly rolled forward to J with the completed I checklist retained as closure evidence.

## Phase J — queued after I

J is final visual/fidelity/installed/physical acceptance and intentional polish. The detailed matrix lives in `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`.

Front-load the mandatory image-oracle parity work (`images/migration/Ideal (PreMigration)/` vs `Current (PostMigration)/`) when vision-capable tooling is available.

### J queued checklist

- [ ] Perform family visual-parity pass against the pre/post migration image oracle.
- [ ] Restore/verify alignment and snap guides.
- [ ] Verify/fix context-menu and theme correctness.
- [ ] Complete remaining Visualizer presentation polish, including any proven extreme Bubble full-expansion tail, **without weakening R-69 reactivity**.
- [ ] Consider device-space R-63 seam refinement only if it preserves `black=0` generically across DPR/resolution combinations; bounded overshoot remains preferable to black flash risk.
- [ ] Fix latency/telemetry accounting so recreation boundaries cannot report stale pre-recreation timestamps as multi-second live latency.
- [ ] Run late-J performance work under `Docs/Guardrails/Performance_Optimization_Contract.md`: target rare active latency tails and proven useless allocation/lifetime work before average counters.
- [ ] Revisit GC only from a clear allocation/lifetime mechanism; preserve ~90 Hz authored Visualizer cadence/newest-state freshness/R-69 and do not tune collection counts in isolation.
- [ ] Verify resource plateau across recreation/soak (RSS/USS, VRAM, threads, handles, workers/caches) without destroying useful bounded caches merely to reduce Task Manager numbers.
- [ ] Recheck both modest-load quality and representative-heavy graceful degradation after any performance change.
- [ ] Complete compiled/frozen/installed 1/2/N-display/DPR/topology acceptance.
- [ ] Complete final family-specific parity/polish acceptance from `Remaining_J_Final_Installed_Acceptance_Decomposition.md`.
- [ ] Reconcile remaining historical-bug records, including failed methods worth preserving.
- [ ] Remove migration-only harness/planning debris only after acceptance evidence exists.
- [ ] Run final maintained destination + broad suite gates and reconcile docs before J closes.

## Authority order

For current work:

```text
exact source / exact test tree
-> Current_Plan.md
-> Spec.md
-> Docs/Contracts.md
-> Docs/Guardrails.md + focused subsystem references
-> Docs/TestSuite.md / Future_Cleanup.md
-> physical/log evidence
-> historical records for mechanism/failed-method lessons
```

Historical documents preserve what happened; they do not override current owner maps. Conversely, current source must not erase a binding historical lesson merely because a tempting shortcut looks locally cleaner.

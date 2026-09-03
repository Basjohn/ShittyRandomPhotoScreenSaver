# Visualizer Hitch Attribution + Optimization Plan — 2026-09-03

Status: **P0 ACTIVE / evidence-led**  
Scope: recurring and activation/recreation delivery stalls that are visible in retained Qt Quick Visualizer presentation.  
Primary physical oracles: **Bubble** and **extreme-tall Spectrum**.

## Product invariant

A performance fix is successful only if it removes the owner of the hitch while preserving authored Visualizer behavior.

Do **not** hide hitches by:

- lowering authored logical cadence;
- increasing smoothing merely to conceal missed delivery opportunities;
- compressing Bubble reaction amplitude/radius/motion/Ghost displacement;
- reducing Spectrum amplitude or its vertical viewport response;
- adding a second timer, cadence, catch-up FIFO, paint acknowledgement or polling owner;
- accepting older source/snapshot state;
- weakening R-69, Bubble Temporal Fidelity, pause/play identity, or mode/preset semantics.

Bubble and tall Spectrum are **symptom oracles**, not owners. Bubble exposes discontinuities through motion/radius/event integration; a tall Spectrum card turns the same missed delivery interval into a larger visible vertical jump.

## Current evidence — operator run 2026-09-03 01:31:35–01:36:00

The native/lifecycle side of this run is clean enough to treat the remaining problem as a delivery/performance incident rather than a COM/QML crash incident:

- `native_faults.log`: capture opened and closed with **no native fault dump**;
- `screensaver_qml.log`: **0 messages / 0 warnings / 0 errors / 0 criticals**;
- GSMTC observation establish/teardown remained on its affinity owner thread through recreation;
- logging queue dropped **0** records; writer lag exists, but caller-side max logging cost was only ~4.93 ms in this run.

### P0 lead A — periodic usage telemetry correlates strongly with steady-state Visualizer gaps

The run emitted 13 `Tick dt spike_ms` warnings across Bubble, DevCurve and Spectrum. **10 of 13 occurred in the exact same wall-clock second as the 15-second usage sample.**

Post-warm-up usage collection cost was roughly **87–128 ms** per sample; the first sample cost ~551 ms. Representative exact-second pairs:

```text
01:32:55 usage ~97 ms   <-> Bubble dt spike 44.44 ms
01:33:25 usage ~111 ms  <-> Bubble dt spike 47.41 ms
01:33:40 usage ~103 ms  <-> Bubble dt spike 48.08 ms
01:34:25 usage ~97 ms   <-> Bubble dt spike 65.01 ms
01:34:40 usage ~91 ms   <-> Bubble dt spike 44.49 ms
01:34:55 usage ~120 ms  <-> DevCurve dt spike 48.92 ms
01:35:10 usage ~91 ms   <-> Spectrum dt spike 61.54 ms
01:35:40 usage ~92 ms   <-> Spectrum dt spike 50.44 ms
01:35:55 usage ~87 ms   <-> Spectrum dt spike 48.09 ms + ~86 ms frame latency
```

This is **strong correlation, not yet sole-causality proof**. The sampler runs outside the GUI owner, so attribution must distinguish CPU/GIL/process-enumeration/log-serialization contention from UI callback work before changing it.

#### Resolution 2026-09-03 — sole causality proven headless, sampler partitioned

`tools/viz_logical_gil_contention_harness.py` reproduces the mechanism deterministically without a display, running the **real** `VisualizerLogicalRuntime`:

- CPython preempts the GIL every ~5 ms (`sys.getswitchinterval`). A pure-Python 100 ms busy loop and a real GIL-releasing `collect()` both produced **0** `dt` spikes — so pure-Python work and psutil syscalls that release the GIL are *not* the owner.
- `Process.children(recursive=True)` (~16-25 ms) and `Process.num_threads()` (~15-87 ms) are Windows **system-wide** `NtQuerySystemInformation` enumerations that hold the GIL for the whole call. Hammered back-to-back against the real logical thread they produce **10-13 spikes of 42-118 ms, 100 % coincident** — the operator's exact signature, load-scaled by total system process/thread count.

Because the logical cadence is a pure-Python thread, any uninterruptible GIL hold on any thread stalls it by that hold's duration. Lead A is therefore a **diagnostics-perturbation artifact**: it only exists under `--usage`, i.e. the instrument was stalling the thread it measures (10/13 spikes were the instrument).

Fix (landed): `ProcessUsageCollector` now refreshes those two GIL-held system-wide enumerations together on a slow sub-cadence (`heavy_refresh_samples`, default 8 ≈ 2 min) while every sample still reports fresh RSS/USS/CPU/handles/IO for the cached process set. Light samples fell from ~30-120 ms to **~1-3 ms** with no system-wide enumeration; the thread count carries forward between refreshes. `tests/test_usage_sampler.py` pins the partition. This did **not** lower the authored cadence, the 42 ms threshold, or any diagnostic field.

Lead B (Gen2 GC) is the same stop-the-world class but is active in **every** RUN-lifetime run and remains the real production owner; its cause (allocation churn) is a separate attribution task and must precede any `RuntimeGCPolicy` change.

##### In-situ confirmation — `main_mc.py --usage --viz --perf`, 2026-09-03 03:07:46-03:09:46 (music playing)

A real 120 s capture confirmed the fix and cleaned up attribution:

- Usage samples seq 2-8 (the light samples) cost 21-44 ms wall-time but produced **zero** `Tick dt spike`s — down from the pre-fix *10 of 13 spikes coincident every 15 s*. `threads_app` correctly held at 93 across the light samples and re-measured to 95 at the next heavy sample (seq 9), proving the partition and carry-forward live.
- In the real (loaded) process, `memory_full_info()`/USS dominates light-sample wall-time (~20-40 ms) — much larger than the ~2 ms seen against a tiny headless process — but it **releases the GIL** during `QueryWorkingSetEx`, so it does not stall the logical thread (seq 4's 44 ms collect caused no spike). USS therefore stays per-sample; memory/leak fidelity is unchanged.
- Only the every-8th **heavy** sample still coincides with a spike (seq 9, 137 ms collect -> 44 ms spike, ~once per 2 min, `--usage` only). Acceptable residual; could be split/rarefied later if it ever muddies an attribution run.
- The one **steady-state** spike in the window was `03:09:03 bubble 60.13 ms`, coincident with `GC generation=2 duration_ms=56.62 collected=34` — clean lead B evidence, now no longer buried under usage-sampler noise. Three more spikes were the startup cluster (03:07:51-54, lead C).

### P0 lead B — Gen2 GC is a proven independent hitch owner

At `01:34:48`:

```text
GC generation=2 duration_ms=142.05
Bubble Tick dt spike_ms=120.87
scene dt_max_ms=171.16
```

This is direct same-window evidence. The existing conservative `RuntimeGCPolicy` therefore remains an unfinished performance owner, not a closed subject. Fix the allocation/lifetime cause or safe collection scheduling/ownership; do not merely push collection indefinitely or suppress evidence.

#### Attribution 2026-09-03 (headless, `tools/gc_gen2_attribution_harness.py`)

- **Gen2 cost is O(retained tracked container objects), linear** (~61 ms per 1M tracked objects on this box: 35K -> 2.8 ms, 1.6M -> 100 ms). So the operator's 142 ms scan implies ~2.3M tracked objects and the in-situ 56 ms scan ~0.9M. **The retained set is the cost driver, not per-frame churn.**
- **The Bubble tick is not the driver.** Driving the real `BubbleFrameRuntime.advance()` for 900 ticks nets only ~+1.5 *retained* tracked objects/tick (~+53 transient/tick, collected at gen0). The tick's allocations are modest and short-lived; they only affect gen2 *trigger frequency* (~every ~100 s at the runtime thresholds), not its cost.
- **`gc.freeze()` is the lever and is essentially free.** It splices the current generation lists into a permanent generation in O(1) (~0.01 ms for 2M objects) that future collections never scan. Post-freeze, a gen2 scan traverses only post-freeze objects (0.00-0.28 ms in the harness). It does not disable GC and does not hide leaks: objects allocated after the freeze are collected normally, so a post-freeze leak stays visible; only a bounded startup/steady-state snapshot is pinned (freed at `gc.unfreeze()` on RUN stop).
- **It must be called from a normal (non-collection) context.** Freezing from inside a gc `stop` callback captured only a partial set (5,431 of 200K), so the freeze must run once from a normal call site after warmup, not from the gc callback.

**Fix (implemented + validated in-situ):** `RuntimeGCPolicy.freeze_stable_generation()` runs once from a one-shot ~45 s after `start()` (a one-shot, not a poller), moving the stable long-lived set to the permanent generation; `gc.unfreeze()` runs on stop (and `stop()` reports/returns failure loudly rather than claiming a false restore).

Precise lifetime scope (not "cannot hide leaks" — narrowed after a lifecycle audit, proven in `tests/test_gc_freeze_lifetime.py`): objects allocated *after* the freeze — including every runtime/display/Settings generation recreated after it — stay under normal generational GC and are reclaimed; refcount-zero destruction still frees frozen objects; only *cyclic* collection of the frozen set is deferred to `gc.unfreeze()`. The single runtime generation live at freeze time has a cyclic Python graph, so if it later retires it is a **bounded one-generation pin** until stop (its OS resources — threads/GL/handles — release by explicit teardown regardless), **not** unbounded accumulation across recreations.

**Real-recreation confirmation (both-display `main.py --usage --perf --viz --life`, freeze at 15:02:26, then ~6-8+ aggressive Settings open/close generation recreations over ~2 min):** RSS/private oscillated in a band and **dropped repeatedly on recreation** (retired generations freeing memory — no accumulation); threads plateaued (95->98); handles held ~2150 (a ~50 oscillating drift, within noise). Zero errors/criticals, QML messages=0/write_errors=0, no native fault, clean shutdown, and `stop()` logged `freeze_restored=True`. Post-freeze gen2 under recreation ran 33-44 ms — the frozen startup set stays skipped while *recreated* generations remain collectible (correct: recreation churn is scanned+collected, not pinned). This satisfies audit check #2; the Qt-side generation graph retires cleanly under freeze.

Two real runs validated it:

1. **Stability run** (`main_mc --perf --viz --usage`, ~6.5 min, Bubble, music): 5 gen2 collections at 31/36/32/33/28 ms — flat, no upward trend — with `collected=0` on all but one. RSS oscillated in a stable ~750-830 MB band (no monotonic growth). So the retained set is stable, long-lived survivors gen2 never frees. First gen2 at ~66 s; RSS stable by ~30 s -> a 45 s freeze lands after the set is built, before the first gen2.
2. **Both-display confirmation** (`main.py --perf --viz --usage`, ~6 min, typical load): `[GC_POLICY] Froze 132666 stable objects` at 14:31:52. The **only** gen2 warning was 14:31:43 (56 ms, pre-freeze) with a coincident 65 ms Bubble spike; **no gen2 appears anywhere after the freeze** for the remaining ~5 min. QML capture: messages=0, write_errors=0; native_faults: no dump; RSS stable ~728-832 MB (freeze pins already-live objects, so it does not raise RSS); clean orderly shutdown across both displays. One leftover 55 ms Bubble spike (14:35:06) is not gen2-coincident — a one-off (image change / usage heavy sample), not a recurring pattern; it belongs to the first-frame/analysis-tail leads, not GC.

Lead B is resolved: the recurring Gen2 stop-the-world stall on the pure-Python cadence thread is eliminated with no cadence/amplitude/motion change and no GC disablement.

### P0 lead C — first-frame publication has a separate one-shot stall

The initial Bubble tick recorded:

```text
total_ms=414.46
bubble_step_ms=46.21
publish_ms=361.25
```

This is not the same class as recurring 15-second hitches. Attribute immutable-frame construction/copying/publication and first-render handoff separately. Avoid moving this cost into every frame merely to improve activation.

#### Resolution — cold import warmed off the first tick (+ dormancy correction)

Attributed: the publish phase pays a one-shot **cold import** of `logical_frame_capture` and its chain (~62 ms headless; larger cold). `capture` itself is a per-tick data copy with no first-call cost. Fix: `QuickDisplayVisualizerOwner._start_logical_runtime` warms `import logical_frame_capture` during activation, before the cadence thread starts, so the first tick no longer pays it. Pure import placement — no per-frame work, cadence unchanged, and every freshness/generation/activation/mode-id fence (bridge-snapshot clear on new activation, mismatch rejection, reactive-first-frame source identity, no stale/previous-mode frame across activation, no increased source age, no paint ACK, newest-state publication) is untouched.

Audit follow-up: warming that module **exposed a pre-existing dormancy hole** — `logical_frame_capture` imported all five mode frame-runtime classes at module scope, so the warm loaded every mode's runtime, violating V4 for disabled modes. Fixed by resolving each mode's frame runtime lazily through the canonical descriptor seam (`_mode_frame_runtime_type`, the same `frame_runtime_module`/`class` wiring `_mode_runtime_factory` uses) rather than a second hard-coded table. Now warming imports no frame runtime, and a real sole-enabled `logical_tick` imports only the active mode's runtime — proven in `tests/test_visualizer_mode_dormancy.py` (per-mode real-runtime + capture-import tests). The Lead-C prewarm strategy itself was sound; the hole was pre-existing and indirect.

### P0 lead D — analysis/presentation tails remain measurable

The persistent serial `visualizer.audio_analysis` lane is healthy on average but recorded approximately:

```text
execution_ms_max ~58.75
handoff_ms_max   ~37.54
callback_ms_max  ~0.52
```

Do not infer that these maxima are Visualizer-visible without timestamp correlation. They remain candidates for tail attribution after periodic telemetry/GC are isolated.

### P0 lead E — recreation is a separate acceptance lane

Runtime replacement produced a ~117 ms Bubble gap during display reconstruction and a later ~3.19 s Spectrum age warning during another replacement/re-admission window. These are **not steady-state evidence** and must not be mixed into the periodic-hitch metric. They still require a recreation/startup freshness acceptance lane after steady-state owners are removed.

### Resource observation — not yet leak evidence

Across this short multi-recreation run, RSS/USS/private bytes and tracked cache bytes moved materially with image/cache/recreation activity but did not show a simple monotonic leak signature. Thread/handle counts also settled rather than rising every sample. A four-minute run cannot prove plateau safety; retain the dedicated soak/resource-plateau task.

## Execution order

### P0-A — pin attribution before optimization

- [ ] Add/retain timestamp-correlatable markers for Visualizer logical tick, analysis completion/handoff, Quick sync/presentation, usage collection, GC start/end, image/cache callbacks and UI queue delivery.
- [ ] Make sure diagnostics themselves can be disabled or sampled and are not the hitch owner being measured.
- [ ] Capture a steady-state run with Bubble and one with extreme-tall Spectrum without opening Settings/CUSTOM during the measurement window.
- [ ] Quantify `dt`/source-age/presentation-age tails and map every >33 ms event to a known owner or mark it unattributed.
- [x] Run an A/B with periodic usage telemetry disabled or reduced **for diagnosis only**. If the 15-second spike signature disappears, redesign the sampler rather than leaving diagnostics permanently blind. *(Done headless via `tools/viz_logical_gil_contention_harness.py`: proved the two system-wide psutil enumerations are the GIL-held owner; sampler redesigned, not blinded — see lead A resolution above.)*
- [ ] Correlate Gen2 collections with Visualizer and scene-frame tails; capture allocation/lifetime evidence around the collection interval.
- [ ] Separate startup/recreation spikes from steady-state statistics.

### P0-B — V0–V4 behavior-floor / mode authority / dormancy before deep active-path tuning

Do the behavior-preserving ownership/dormancy part of the planned Visualizer modularization before optimizing internals:

- [ ] V0: pin all five current modes, cycling/preset semantics, source freshness, R-69/BTF/viewport behavior, one-cadence ownership, lazy renderer construction and global CUSTOM behavior before structural edits.
- [ ] V1: centralize duplicated identity/wiring while preserving lazy imports and legitimate mode-specific behavior.
- [ ] V2: persist per-mode enable state; at least one enabled mode while the family is enabled; deterministic current-mode substitution.
- [ ] V3: route every product caller through effective enabled modes while schema/default persistence still knows all registered modes.
- [ ] V4: prove a disabled mode imports/constructs no renderer, frame runtime, Settings body, recurring work or GPU resources; prove each mode can operate as the sole enabled mode.
- [ ] Do **not** move the Settings UI yet; V5-V8 rehosting/dependency/future-mode work waits until dormancy and hitch work are stable.

Reason: performance work should target the final active owner graph, not optimize work that V4 will correctly remove.

### P0-C — remove deterministic app-owned hitch sources

- [x] **Usage telemetry:** remove/partition the 15-second collection contention while preserving useful diagnostics. Candidates must be measured; do not simply lengthen the interval and call the hitch fixed. *(Done: `ProcessUsageCollector` partitions the two proven GIL-held system-wide enumerations to a slow sub-cadence; every sample still logs fresh RSS/USS/CPU/handles/IO. Light-sample cost ~1-3 ms.)*
- [ ] **Allocation/GC:** attribute high-churn allocations and remove useless churn first; then reassess collection policy. Do not globally disable GC or hide unbounded retention.
- [ ] **First-frame publish:** attribute the 361 ms publication cost and make activation cheap without adding recurring copies/owners.
- [ ] **Analysis lane tails:** correlate max execution/handoff events; optimize only if they survive as visible owners after the two deterministic periodic sources are removed.
- [ ] **GUI/pacer delivery:** inspect skipped deadlines, long UI callbacks and scene invalidation only after producer-side stalls are controlled.
- [ ] **Logging/diagnostics:** keep zero-drop observability, but ensure verbose serialization/output does not hold the GIL or main owner long enough to perturb the product being measured.

### P0-D — recreation/startup freshness

- [ ] Attribute replacement-generation first-frame age separately from steady state.
- [ ] Preserve immediate fresh-frame/generation fencing; never solve recreation latency by accepting stale prior-generation Visualizer state.
- [ ] Recheck coordinated startup reveal and desktop->wallpaper transition while Visualizer is enabled.

### P0-E — physical acceptance with sensitive oracles

Bubble and extreme-tall Spectrum both have to pass; neither may be tuned down to make the other look good.

- [ ] Bubble: no perceptible periodic freeze/jump in radius, drift, event motion or Ghost/history behavior during ordinary playback.
- [ ] Tall Spectrum: no periodic large vertical jump/flicker attributable to missed delivery; R-76 height-aware temporal scaling remains intact.
- [ ] Canonical/wide Spectrum remains arithmetically/visually unchanged by any tall-specific follow-up.
- [ ] DevCurve/Sine/Oscilloscope remain smooth enough that removing global hitch owners did not introduce a mode-specific regression.
- [ ] Pause/play and mode/preset changes remain fresh with no backlog/catch-up burst.
- [ ] Multi-display and transitions do not materially worsen Visualizer tails.
- [ ] Re-run representative-heavy and modest-load profiles before declaring the hitch tranche closed.

## Spectrum-specific decision after P0

R-76 already corrected the wrong-axis/stranded smoothing owner and canonicalized the invisible solid-bar hysteresis domain. This run demonstrates a delivery-hitch class capable of recreating a visible tall-card jump despite that correction.

Therefore:

1. remove deterministic hitches first;
2. physically retest tall Spectrum;
3. **only if tall Spectrum still flickers with healthy delivery**, inspect actual segmented/solid renderer pixel pitch, quantization, peak/ghost presentation and source-to-visible trace;
4. do not increase global smoothing or reduce amplitude as the first response.

## Closure condition

This tranche is not closed by average FPS. It closes only when recurring application-owned latency tails are either removed or explicitly bounded/justified, Bubble and tall Spectrum are physically smooth, mode dormancy is real, and no optimization weakened authored cadence/reactivity/freshness.

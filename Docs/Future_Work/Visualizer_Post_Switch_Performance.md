# Visualizer Post-Switch Presentation-Tail Investigation

Status: ACTIVE INVESTIGATION
Authority: `Current_Plan.md` item 1
Guardrail: `Docs/Guardrails/Performance_Optimization_Contract.md`
Preserved evidence: `logs/evidence_chest/logsb11575b976.zip`

## Question this work must answer

Does repeated Visualizer mode switching leave presentation/render ownership in a progressively worse state, or was the 2026-09-12 slowdown only external CPU contention/noise?

The observed run is suggestive but not causal proof: Sphere -> Spectrum -> Oscilloscope -> Sine -> extreme-vertical Bubble remained logically healthy while GUI/presentation tails worsened, then a saved-layout Quick-runtime recreation subjectively restored smoothness without changing Bubble engine generation/activation. Do not assume a leak from that observation alone.

This investigation must produce evidence that can **falsify** the switch-accumulation hypothesis. It is not permission to lower Visualizer cadence, audio freshness, reaction amplitude, authored motion, Bubble radius/tails, CUSTOM scaling, or the 60 Hz presentation target.

## Existing current owners to use

Do not create a parallel performance/render system.

- `rendering/quick/visualizer/render_host.py`
  - `QuickVisualizerRenderHost.render()` observes mode changes on the legal render thread.
  - `release_inactive_implementations()` is the canonical inactive-renderer retirement seam.
  - `resolved_mode_ids` and each renderer's `has_resources` are the current ownership facts.
  - the shared quad VAO/VBO is host-owned and must remain one bounded pair per live host.
- `rendering/quick/visualizer/telemetry.py`
  - current thread-safe node telemetry; extend this rather than adding a second telemetry cadence.
  - hot-path counters must become cheaper, not more expensive.
- `rendering/quick/visualizer/item.py` / `node.py`
  - existing render-thread retirement/event boundary. Do not release GL resources from GUI/logical threads.
- `widgets/spotify_visualizer/quick_display_visualizer_owner.py`
  - `request_mode_change()` / the retained activation transaction are the canonical product mode-switch path.
- `tests/test_qtquick_visualizer_mode_retirement.py`
  - current focused one-switch/retry/context tests; extend with repeated-switch ownership invariants.
- `tools/qtquick_visualizer_clip_smoke.py`
  - existing production-shaped real-GL Visualizer node harness; extend or factor a sibling switch probe rather than inventing a fake compositor.
- `core/performance/event_loop_recorder.py`, Quick frame-pacer telemetry and existing performance logs
  - use existing measurements for event-loop and frame-tail attribution.

## Hypotheses

Keep these separate. A run that disproves one does not prove another.

- **H0 — external contention only:** a settled Bubble-only control degrades similarly to a switch-exposed Bubble under matched load; mode-switch exposure has no repeatable residual effect.
- **H1 — stale renderer/resource ownership:** inactive Visualizer renderers/resources survive completed switches, accumulate with switch count, and/or disappear only when the Quick runtime is recreated.
- **H2 — presentation invalidation amplification:** resource ownership remains bounded, but update/invalidation/render requests per unit time increase after repeated switches while logical cadence/source freshness remain stable.
- **H3 — fixed per-frame render cost exposed by contention:** switching is innocent; a cost such as `_InheritedGlState.capture()/restore()` becomes visible only under CPU/driver contention and runtime recreation merely changes scheduling/driver state.
- **H4 — other Quick/runtime-generation state:** neither Visualizer renderer resources nor Visualizer invalidations grow, but a Quick-generation-owned scene/presentation resource does. Escalate only after H1/H2 are explicitly clean.

## Phase P0 — preserve and parse the original evidence

Before changing runtime code:

1. unpack/read `logs/evidence_chest/logsb11575b976.zip` with existing log-analysis tooling;
2. record the exact observed mode sequence, Bubble residency, saved-layout recreation boundary, Quick runtime generation before/after, engine generation/activation before/after, event-loop tails, pacer skips, Visualizer revision Hz/snapshot age, process CPU/GPU and resource snapshots;
3. save a compact investigation baseline in the work log/decomposition notes. Do not replace the raw evidence.

The original run is the motivation and comparison sample, not the regression oracle by itself.

## Phase P1 — lifecycle telemetry: boundary-only, not per-frame GL probing

Extend the existing `VisualizerRenderNodeTelemetry`/render-host boundary so a snapshot can answer, after every completed mode switch or teardown:

- active/drawn mode ID;
- mode-boundary sequence number;
- renderer resolve count, total and by mode if cheap;
- inactive release attempts / successes / failures;
- resolved mode IDs after cleanup;
- each resolved implementation's already-owned `has_resources` boolean;
- shared quad ownership (`vao_owned`, `vbo_owned` booleans; not raw GL state queries);
- full-host release count and last release error;
- runtime/display generation identity already available at the caller snapshot boundary.

Rules:

- update these facts only at existing mode-resolve/release/teardown events;
- do **not** call `glGet*` to collect diagnostics;
- do not log every frame;
- reading the snapshot must not mutate/render/release anything;
- a failed release remains visible as a failure and retained renderer; never silently delete it from accounting.

### Hard ownership invariant

After a target mode has rendered and its inactive cleanup has completed, a live host must converge to:

```text
resolved_mode_ids == {active_mode_id}
```

and no retired implementation may report `has_resources=True` outside an explicit failed-release/retry state.

The shared quad may remain owned by the live host; it must not multiply with mode switches. Full host/runtime teardown must release it.

## Phase P2 — deterministic repeated-switch tests

Extend `tests/test_qtquick_visualizer_mode_retirement.py` (or one narrowly named sibling) with tests that use the current fake-renderer/context seam to run **at least 100 completed mode changes** across the permanent modes plus experimental Sphere when activated for the test.

Required assertions:

1. every successful switch retires the previous inactive renderer before/while resolving the target;
2. after every completed switch, `resolved_mode_ids` contains exactly the active mode;
3. successfully retired fake renderers have `has_resources == False` and are no longer cached;
4. release counts grow with actual retirements, not rendered frames;
5. the shared host quad is not re-created/multiplied merely because the mode changed;
6. one injected release failure remains accounted/cached, then a later legal render retries it and returns to the one-active-renderer invariant;
7. switching to a mode before its first source snapshot still requests cleanup through the existing retirement event path;
8. full host release after the loop leaves no implementations and no host quad resources.

These tests prove lifecycle boundedness. They **cannot** prove the physical performance bug and must not be presented as doing so.

## Phase P3 — real-GL repeated-switch smoke

Extend `tools/qtquick_visualizer_clip_smoke.py` or create a small sibling `tools/qtquick_visualizer_switch_smoke.py` reusing its real `QQuickWindow`, `VisualizerRenderItem`, `VisualizerSnapshotBridge`, snapshot factories and telemetry.

Drive a deterministic sequence such as:

```text
sphere -> spectrum -> oscilloscope -> sine_wave -> bubble
```

for 5 cycles, then hold Bubble. A switch only counts after the target has produced/drawn an accepted snapshot; do not advance on a blind wall-clock toggle.

The real-GL smoke must report one JSON result containing:

- requested/completed switch count;
- active mode after every completion;
- boundary telemetry from P1;
- render/sync/draw/invalidation deltas per switch and during the final Bubble hold;
- GL error status only at existing bounded capture/check points, not every frame;
- final teardown resource state and legal render/release thread identity.

Acceptance: ownership stays bounded through the repeated real-GL sequence and final teardown is clean. Any accumulation is a concrete H1 lead before touching performance code.

## Phase P4 — causal installed-runtime A/B/C experiment

The physical slowdown must be tested in the real product path because synthetic GL tests cannot prove scheduler/QML/whole-scene behavior.

Use the same build, settings/presets, audio/source, extreme-vertical CUSTOM Bubble geometry, display topology, diagnostic options and deliberate external CPU contention for each matched run. Prefer the same repeatable CPU load/build workload rather than an uncontrolled game when establishing the oracle; the UE5 + 4-job scenario remains a useful hostile follow-up.

Run **three matched repetitions** of each condition. Exclude the first 15 seconds after the final activation/recreation from steady-state scoring.

**Corrected event-loop oracle (R-80):** the recorder's ordinary rolling percentile
is not a valid named-window metric because it retains 2,048 x 50 ms ~= 102.4 s of
history. At each scored-window start the opt-in driver must reset the recorder's
scoring history immediately before the marker. The recorder emits independent,
non-overlapping `period_*` summaries tagged with that window label; the harness
scores only those local periods and fails old rolling-only logs closed. The 15 s
exclusion remains an authored transition-settle interval, not a substitute for
flushing the old rolling deque.

### A — control, no switch exposure

- start/recreate into Bubble;
- do not visit other Visualizer modes;
- hold settled extreme-vertical Bubble for at least 120 seconds under the chosen contention.

This measures ordinary contention drift.

### B — switch exposure

- from the same starting state, perform 5 complete cycles of:
  `Sphere -> Spectrum -> Oscilloscope -> Sine -> Bubble`;
- require each transition to complete before requesting the next;
- after the final Bubble activation, hold the same Bubble geometry for at least 120 seconds;
- **do not** recreate the Quick runtime.

This measures residual state after repeated mode switching.

### C — intervention / recreation

- perform the same B switch exposure;
- hold Bubble long enough to establish the post-switch tail sample;
- load the same saved layout to force the already-existing Quick runtime recreation boundary;
- verify Quick runtime generation changes while the intended Bubble configuration is restored;
- after the same 15-second exclusion window, hold Bubble for at least 120 seconds.

This tests whether recreation reverses a B-only degradation. Recreation is an experiment/intervention, **not** an allowed production self-healing fix.

### Optional D — no-contention discriminator

Repeat A and B without deliberate external CPU contention. If B only diverges under contention, the bug may be a latent amplification rather than an unconditional leak.

## Measurements and causal classification

For every scored steady-state window collect the same existing metrics:

- window-local event-loop period p95 / p99 / max (never the pre-window rolling view);
- frame-pacer late/skip counts and ratio;
- render/sync/draw/invalidation rates;
- Visualizer logical revision Hz;
- logical/snapshot source age;
- Bubble integration requested/integrated/failure counts;
- process/system CPU and GPU from existing diagnostics;
- passive RSS/VRAM/thread/handle/resource snapshots where already available;
- P1 renderer/resource ownership facts;
- Quick runtime generation + Visualizer engine generation/activation;
- eyes-on physical smoothness as supporting evidence, never the only oracle.

### Working regression threshold

Call the result **swap-sensitive** only when at least 2 of 3 matched B repetitions show, relative to their paired A controls:

- event-loop p99 worsens by both **>= 2 ms absolute and >= 35%**, **or** frame-pacer skip ratio worsens by **>= 5 percentage points**;
- the difference persists through at least 60 seconds of the settled Bubble window rather than being only the transition burst;
- Visualizer revision Hz and source freshness remain materially healthy (no explanation from logical/audio starvation);
- and the paired C recreation removes **at least 70% of the B-vs-A introduced tail delta** without changing authored Bubble quality/cadence.

These are investigation thresholds, not permanent product performance specifications. Preserve the raw measurements so the threshold can be challenged.

### Interpretation table

```text
A ~= B, C ~= B
    -> switching hypothesis not reproduced; investigate contention/fixed cost (H0/H3)

B worse than A + ownership grows with switch count + C clears it
    -> H1 strongly supported; repair render-thread retirement/ownership seam

B worse than A + ownership bounded + invalidation/update rate grows + C clears it
    -> H2 strongly supported; trace request origins and remove only proven duplicate/no-op invalidations

B worse than A + ownership/invalidation bounded + C clears it
    -> investigate other Quick-generation-owned state (H4); do not guess a GL leak

A degrades similarly to B
    -> external contention/fixed per-frame cost is primary; mode swapping is not demonstrated causal
```

## Evidence status — 2026-09-12 oracle correction

The first full P4 matrix produced a `swap_sensitive` classification, but that
classification is **invalid causal evidence**. The event-loop summaries being
scored were the recorder's 2,048-sample rolling view (~102.4 s at 50 ms/sample), so
the 15 s post-switch exclusion did not isolate the named steady windows. The same
switch-period stalls were repeatedly re-observed until they aged out of the deque.

Condition C proves the mistake directly: in every preserved C run the
`steady_C_pre` rolling p99 returned to roughly 4–5 ms before the saved-layout
recreation happened. Therefore the old claim that recreation removed >=97% of a
persistent tail is withdrawn; the pre-recreation state had already recovered.

Useful non-causal stress facts remain valid and should not be discarded:

- the exact 25-switch path, including Sphere, converged to one active Bubble render
  implementation with 25/25 successful inactive releases and no renderer/quad
  accumulation;
- publication/request/render/swap counts stayed bounded and approximately 1:1;
- the mandatory `_InheritedGlState.capture()/restore()` isolation fence did not
  become more expensive across the stress path and remains unchanged;
- `sync_present()` timing, Python-thread census, process age (A-long), aggregate
  image-cache size and observed native-thread count do not explain the apparent
  rolling-tail result.

These facts reject several simple leak/amplification stories for the stress path;
they do **not** prove the original long-residency user-visible hitch is solved.

The next executable gate is deliberately small: one corrected A and one corrected
B using window-local `period_*` event-loop evidence. Only if B still shows a real
post-boundary persistent regression should C or deeper attribution resume. If B is
clean, close the automated 25-switch poison hypothesis for this build/load and
return to the original long-residency reproduction with the corrected oracle.

## Phase P5 — repairs only after attribution

### If H1

Repair the existing render-thread retirement seam. Do not add another resource manager, delayed cleanup timer, or layout-reload fallback. Add the smallest regression test that fails before the fix and passes after it, then rerun P2/P3/P4.

### If H2

Attribute request origins (frame pacer, mode-switch retirement, retained item/QML invalidation). Deduplicate only requests proven to be redundant/no-op. Never reduce the 60 Hz presentation target or logical cadence to hide the counter.

### If H3

Measure `_InheritedGlState.capture()/restore()` separately. Any optimization needs state-contamination coverage across Visualizers, ordinary widgets and transitions. Do not remove the render fence because synchronous state queries look expensive.

### Known safe anti-waste work

Independently of the causal result, the already-identified diagnostic hot-path waste may be removed if tests prove unchanged semantics:

- compute bars/energy/waveform maxima only when a diagnostic record consuming them is due;
- make `VisualizerRenderNodeTelemetry.note_sync/note_render/note_draw` mutate cheap protected counters/fields rather than allocating a replacement frozen dataclass every call; `snapshot()` remains immutable/thread-safe.

Do not claim either change fixes the post-switch degradation unless P4 demonstrates that.

## Closure

This item closes only when:

1. P2 deterministic repeated-switch lifecycle tests are green;
2. P3 real-GL repeated-switch smoke is green and resources plateau;
3. the corrected window-local P4 oracle has first established whether a post-switch regression exists at all; expand to matched A/B/C repetitions only when a causal recovery claim actually needs them;
4. any owner demonstrated by the corrected oracle has been repaired and the same trustworthy experiment rerun;
5. no fix lowers Bubble/permanent-mode temporal fidelity, audio/source freshness, reaction amplitude, motion/tails/radius, CUSTOM scaling or presentation target;
6. no automatic runtime/layout recreation has been introduced as a self-healing mechanism.

A clean result is valuable: if corrected A/B reject the swap hypothesis, mark it rejected for the tested build/load and stop carrying an unproven leak theory forward.

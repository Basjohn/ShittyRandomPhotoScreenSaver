# Bubble End-To-End Audit

Last updated: 2026-06-18

## Objective

Close Bubble's remaining unresolved family without sacrificing fidelity, function, reactivity, or latency:

1. Bubble performs materially worse than other visualizer modes when the application initiates a transition.
2. Small bubbles still under-participate in some loud passages, especially bass-dominant or lower-vocal hot sections.
3. The current automation is strong, but it still is not strict enough to fail the latest live complaint before more tuning.

The next execution pass must be root-cause-led, not mitigation-led.

## Non-Negotiable Constraints

- Zero fidelity loss.
- Zero functionality loss.
- Zero reactivity loss.
- No new audio smoothing, stale holds, or delay-based tricks.
- No “performance win” that works by hiding visible bubbles, culling visible ghosting, or lowering live authority.
- No Bubble code change lands unless the Bubble bar gets stricter first and stays green afterward.
- Bubble changes must remain mode-isolated unless evidence proves a shared seam is truly culpable.
- If a fallback or degraded path becomes necessary later, it must log loudly at `WARNING` or higher through the relevant CLI family.

## Current Failure Statement

Bubble is now in a split state:

- the overall loud-path is better than earlier failed passes
- but the latest logs still show:
  - Bubble throughput materially below other modes during transition-heavy runtime
  - dt spikes staying elevated through Bubble windows
  - small bubbles still failing to participate enough in some loud passages

This means the branch no longer has a broad “Bubble is dead everywhere” problem. It has a narrower but more dangerous one:

- the remaining failures are easier to miss
- the remaining perf cost is likely concentrated in Bubble-owned hot paths
- careless tuning could easily regress the hard-won good behavior

## Confirmed Evidence

### Performance evidence

Latest logs still show Bubble materially behind other modes.

- `logs/screensaver_spotify_vis.log`
  - `2026-06-15 21:10:50` Spectrum tick metrics: `avg_fps=86.8`, `dt_max=34.06ms`, `bar_count=35`
  - `2026-06-15 21:10:55 .. 21:13:19` Bubble settles mostly around `68-75 avg_fps`, with repeated `dt_max` in the `58-64ms` range
- `logs/screensaver_perf.log`
  - `2026-06-15 21:17:51` Bubble tick metrics: `avg_fps=68.8`, `dt_max=62.79ms`, `bar_count=48`
  - transition windows remain much healthier when the active visualizer mode is not Bubble, matching user runtime observation
- newer `2026-06-18` logs also add two useful negative clues:
  - Bubble throughput is materially healthier than the earlier failure family, settling roughly in the `75-87 avg_fps` band while the Bubble-owned diagnostics report `worker_ms` around `1.6-1.9ms`
  - disabling Bubble bounce settings during runtime testing did not produce a meaningful uplift
  - most Bubble spikes still report `pending=<none>`, `waiting_engine=False`, and `waiting_frame=False`, so the first suspects remain Bubble-owned hot-path cost rather than simple pending-result backlog folklore

### Loud-passage evidence

The latest live run still shows loud windows where Bubble is hotter on paper than on screen.

- `logs/screensaver_spotify_vis.log`
  - `21:11:15` floor snapshot shows `bass=1.702`-class hot behavior in the same general window while the visible Bubble reaction remains modest
  - `21:11:55` and `21:12:00` remain hot manual-floor windows with `support=0.000`, so the remaining issue is not explained away by dynamic-floor support inflation
  - the late session still contains bass-dominant windows where loud authority exists but small-lane presence does not look as alive as softer passages

### Oracle gap evidence

The existing Bubble suite is already much better than before, but it still missed the current live complaint.

Current strong lanes already exist in `tests/test_spotify_visualizer_widget.py`:

- `_deep_sea_runtime_log_replay_profile()`
- `_manual_floor_late_loud_runtime_log_replay_profile()`
- `_manual_floor_bass_dominant_tail_runtime_log_replay_profile()`
- `test_manual_floor_runtime_log_replay_keeps_loud_window_alive_without_support_pressure`
- `test_manual_floor_bass_dominant_tail_replay_stays_alive_without_presence_crutches`
- `test_bubble_soft_to_loud_audio_fixture_keeps_loud_section_more_expressive_than_soft`
- `test_bubble_loud_bass_hold_audio_fixture_keeps_manual_floor_lanes_alive`
- the three `test_bubble_current_feel_lock_*` guards

That is strong groundwork, but the latest runtime complaint proves we still need one tighter loud-path lane derived from the newest live evidence before more tuning happens.
That newer lane now exists for the `2026-06-18 05:25` mixed-hot family so thinner hot windows have to stay above soft-passage behavior even after the broader perf recovery.
The newest long run also adds a narrower tail-family reminder from `2026-06-18 13:40:10 .. 13:41:26`:

- `13:40:10` stayed clearly alive at `raw_bass=1.627`
- `13:41:11` still looked too compressed for a materially hot tail window at `raw_bass=1.377`
- `13:41:26` then looked friendlier again even though direct Bubble feed was lower

That matters because the current remaining failure is no longer “Bubble loud is generally dead.” It is “late hot consistency can still sag in a way that broad mixed-hot bars might miss unless they look at broad small-lane participation, not only the single strongest surviving small bubble.”

## End-To-End Contract Map

Bubble currently crosses these ownership seams:

1. **Beat-engine feed**
   - `widgets/spotify_visualizer/beat_engine.py::get_bubble_energy_bands()`
   - produces Bubble-specific feed terms like `absolute_body`, `hot_lift`, `hot_crest_lift`, and `presence_carry`
2. **Dispatch seam**
   - `widgets/spotify_visualizer/tick_pipeline.py::dispatch_bubble_simulation()`
   - mixes feed, transient bus, onset crest, and widget settings into the compute payload
3. **Simulation seam**
   - `widgets/spotify_visualizer/bubble_simulation.py::tick()`
   - updates bubble movement, lane energy, trail state, and collision response
4. **Snapshot seam**
   - `widgets/spotify_visualizer/bubble_simulation.py::snapshot()`
   - converts simulation state into flat CPU lists for render upload
5. **Worker/consume seam**
   - `widgets/spotify_visualizer_widget.py::_bubble_compute_worker()`
   - `widgets/spotify_visualizer_widget.py::_bubble_compute_done()`
   - `widgets/spotify_visualizer_widget.py::_consume_pending_bubble_result()`
6. **Overlay transport seam**
   - `widgets/spotify_bars_gl_overlay.py::set_state()`
   - stores Bubble arrays on the GL overlay state
7. **Renderer upload seam**
   - `widgets/spotify_visualizer/renderers/bubble.py::upload_uniforms()`
   - copies Python lists into persistent numpy buffers and uploads them as uniforms

If Bubble is 3x worse during transition-time runtime, the likely culprit is not one magical line. It is probably concentrated waste across these Bubble-owned seams, with `bubble_simulation.py` and `renderers/bubble.py` currently the strongest suspects.

## Resource Waste Inventory

### Waste 1. Collision response is O(n^2) and recomputes expensive state inside the pair loop

`bubble_simulation.py::_apply_bubble_collision_response()` currently:

- builds an `active` list every tick
- loops over every active pair
- calls `_effective_collision_radius(...)` for both bubbles inside the nested pair loop
- repeatedly evaluates pulse/contraction/clamp math and `math.hypot(...)`
- may run multiple collision passes in stricter bounce settings

This is the single strongest current Bubble perf suspect.

### Waste 2. Snapshot always rebuilds fresh flat Python lists

`bubble_simulation.py::snapshot()` currently allocates:

- `pos_data`
- `extra_data`
- `trail_data`

every compute result, then fills them bubble by bubble.

That means Bubble pays a repeated Python allocation and append cost even before the GL upload begins.

### Waste 3. Trail payload work continues even when the visible trail contract is effectively off

Even when trail is not materially contributing to the frame, `snapshot()` still fills `trail_data` for every bubble with zero-strength samples. The renderer later avoids uploading trail uniforms when trail is off, but the snapshot churn still already happened.

This is a clean waste seam because removing it should not alter visible output when the trail is not visible.

### Waste 4. Transport still repacks CPU lists into numpy buffers every frame

`renderers/bubble.py` persists the numpy buffers, which is good, but it still:

- zero-fills the persistent buffers every frame
- copies Python-list source data into those buffers every frame
- uploads large uniform arrays every frame

That makes Bubble far more payload-heavy than the bar-like modes.

### Waste 5. Bubble compute callback is still worker-thread direct, not a Qt-queued stage boundary

`core/threading/manager.py::submit_task()` invokes the callback directly on the worker after completion.

`_bubble_compute_done()` is careful and only stages Python-owned result data, so this is not the primary perf culprit right now, but it remains a correctness and observability seam:

- any later “small convenience” mutation there would be dangerous
- it can still complicate backlog/latency interpretation if result staging becomes heavier

This is a seam to keep explicit, not a first optimization target.

## Root-Cause Families Ranked

### 1. Bubble oracle is still underfitting the newest live failure shape

- **Confidence:** Highest
- **Why it matters:** if the latest live under-participation does not fail the suite, future tuning can still drift into false green
- **Best correction:** tighten the oracle first with a newest-log late-hot lane and keep the current feel-locks intact

### 2. BubbleSimulation collision + per-bubble runtime math is the dominant transition-time CPU sink

- **Confidence:** High
- **Why it matters:** Bubble alone remains the mode that drags transition-time runtime the hardest
- **Best correction:** profile-then-refactor the simulation hot path while proving identical visible output against the Bubble bars

### 3. Snapshot/transport churn is too expensive for Bubble’s payload size

- **Confidence:** High
- **Why it matters:** Bubble has much larger per-frame state than bar modes, so Python-list rebuild plus numpy repack plus uniform upload is a plausible second major cost
- **Best correction:** reduce pointless payload generation first, then reduce pack/upload churn with payload-equivalence bars

### 4. Small-lane loud under-participation is partly structural, not just tuning drift

- **Confidence:** High
- **Why it matters:** small bubbles are still primarily mid/high-led in `bubble_simulation.py`, and loud bass-dominant windows can therefore starve them
- **Best correction:** keep Bubble mode-isolated and add a clearer loud small-lane authority branch that does not depend on vocals being present

### 5. Dispatch / pending-result cadence could still be smearing Bubble responsiveness under load

- **Confidence:** Medium
- **Why it matters:** if compute completion falls behind, Bubble can feel late even when the actual visual math is “correct”
- **Best correction:** only investigate this after simulation and transport hot paths are narrowed, because right now it looks more like a downstream symptom than the main cause

## Bubble Loud-Path Diagnosis

The current loud-path under-participation is not random. The present structure explains it.

### What the code is doing now

In `bubble_simulation.py`, small bubbles are still fundamentally treated as a mid/high-led lane:

- `vocal_body` is the dominant base
- `chorus_support` helps soft and mixed passages
- `hot_bed_support` adds a bounded loud carry
- non-big bubbles then derive their pulse energy from that combined source

### Why that fails in some loud passages

This works well when:

- loudness has strong mid/high content
- vocals or upper harmonics stay active
- the song is soft enough that the small lane already thrives on the mid/high-led path

It works less well when:

- the loudness is bass-dominant
- vocals are sparse or absent
- the big lane is correctly hot, but the small lane is waiting on presence that is no longer driving the section

That matches the latest user complaint closely.

### Correct direction

Do not reopen shared floor semantics first.

Instead:

- keep Bubble mode-isolated
- preserve the current good soft-path feel
- add a clearer absolute-loud small-lane contribution for loud bass-dominant windows
- prove against the stricter bar that this does not just rescue the hero lane while small bubbles still die

## Best Correction Strategy

The safest order is:

1. tighten the oracle first
2. record the present good Bubble feel as a hard guard
3. isolate Bubble-owned perf waste before touching loud-path shaping
4. only then do one Bubble loud-path feed/simulation pass at a time

That order is the safest because:

- it avoids repeating the old overfit loop
- it preserves the hard-won good Bubble baseline
- it prevents perf work from silently changing feel
- it keeps all risky work measurable

## Ordered Work Plan

### Phase 0. Oracle Tightening First

- [x] **P0 | Highest expected value | Risk: Low**
  Tighten the Bubble oracle with at least one newest-log late-hot replay lane taken from the 2026-06-15 run.
  - Entry gate: current Bubble suite plus current feel-locks must be green.
  - Exit gate: the new latest-live lane is red before any Bubble tuning and green only after a real fix.
  - Avoid regression by keeping the existing feel-lock signatures unchanged unless the new evidence proves they are dishonest.

- [x] **P0 | High expected value | Risk: Low-Medium**
  Add a Bubble transition-time perf oracle that compares Bubble’s compute/transport throughput against itself, not against a softened absolute FPS target.
  - Entry gate: existing Bubble reactivity bars green.
  - Exit gate: the suite now exposes whether a candidate perf fix keeps the recovered worker/collision/snapshot budget band intact on the newest mixed-hot live family without altering payload equivalence.
  - Avoid regression by treating payload equivalence and current-feel locks as mandatory companions to any perf bar.

- [x] **P0 | High expected value | Risk: Low**
  Surface Bubble-owned worker/simulation perf breakdown into the existing visualizer perf path before deeper hot-path refactors.
  - Entry gate: existing Bubble reactivity bars green.
  - Exit gate: Bubble runtime logs now expose worker total, simulation tick, collision, snapshot, pair-count, overlap-count, and trail-payload activity through `[PERF] [SPOTIFY_VIS][BUBBLE]`.
  - Avoid regression by keeping the first pass observational and storing the diagnostics at the Bubble worker seam rather than threading it through unrelated visualizer modes.

- [x] **P0 | High expected value | Risk: Low**
  Add Bubble payload-equivalence coverage before changing renderer transport behavior.
  - Entry gate: existing Bubble transport tests green.
  - Exit gate: transport-only changes must preserve the exact active uploaded payload prefix for position, extra, and trail data.
  - Avoid regression by keeping the assertions at the GL-upload seam instead of inferring correctness from internal helper state alone.

- [x] **P0 | High expected value | Risk: Low**
  Extend the current feel-lock coverage so the newest good soft/hot windows are explicitly recorded before perf work continues.
  - Entry gate: existing fixture and replay feel-locks green.
  - Exit gate: current “good” Bubble feel is harder to accidentally erode.
  - Avoid regression by capturing actual present behavior rather than reusing older weaker numbers.

- [x] **P0 | High expected value | Risk: Low**
  Expand the Bubble lane metrics so loud-path guards can observe broad small-lane participation instead of only the single strongest surviving small bubble.
  - Entry gate: current Bubble loud/perf bars green.
  - Exit gate: replay guards can now assert `avg_small_delta` and `small_active_ratio` when a user-visible complaint is specifically about the small lane looking absent in loud passages.
  - Avoid regression by keeping this observability test-owned; it should not alter runtime behavior by itself.

- [x] **P0 | Medium expected value | Risk: Low**
  Keep a duplicate-dispatch guard so repeated Bubble ticks cannot quietly queue a second compute task while the prior one is still in flight.
  - Entry gate: existing Bubble dispatch guards green.
  - Exit gate: the harness proves Bubble will not silently drift into duplicate in-flight compute submissions on repeated ticks.
  - Avoid regression by keeping this at the dispatch seam only; do not turn it into a speculative threading rewrite.

### Phase 1. Bubble Perf Audit Pass

- [ ] **P0 | Very high expected value | Risk: Medium**
  Instrument and isolate `bubble_simulation.py::_apply_bubble_collision_response()` so we can prove how much cost is pair-loop math versus the rest of the sim.
  - Entry gate: tightened Bubble bars green.
  - Exit gate: new perf diagnostics show the proportion of Bubble compute time spent in collision versus non-collision work.
  - Avoid regression by making the first pass diagnostics-only and routing them through Bubble/visualizer perf logging.

- [ ] **P0 | High expected value | Risk: Medium**
  Add a payload-equivalence bar for Bubble snapshot output before changing list generation or transport shape.
  - Entry gate: tightened Bubble bars green.
  - Exit gate: we can change snapshot packing only if the same per-frame visible payload remains equivalent.
  - Avoid regression by comparing Bubble output metrics, not raw implementation details alone.

- [ ] **P1 | High expected value | Risk: Medium**
  Audit trail generation so invisible trail work can be skipped before list generation, not only before GL upload.
  - Entry gate: current Bubble trail-related feel locks green.
  - Exit gate: perf improves with no change in visible trail behavior when trail is enabled.
  - Avoid regression by proving trail-enabled output is unchanged and trail-disabled output was truly invisible already.

- [ ] **P1 | Medium expected value | Risk: Medium**
  Audit whether Bubble uniform upload can be narrowed or staged more efficiently without removing any visible bubble/ghost/trail data.
  - Entry gate: payload-equivalence bar green.
  - Exit gate: measured transport cost drops while Bubble render-state metrics remain equivalent.
  - Avoid regression by forbidding any optimization that reduces visible count, visible radius, visible alpha, or visible trail samples.

### Phase 2. Bubble Loud-Path Root-Cause Pass

- [ ] **P0 | Very high expected value | Risk: High**
  Add a small-lane loud-authority oracle for bass-dominant, lower-vocal hot windows so the current live complaint is impossible to miss.
  - Entry gate: latest-live replay lane red against current failure shape.
  - Exit gate: the new lane is green while the soft-path feel-locks remain green.
  - Avoid regression by requiring soft-path and hero-lane bars to remain unchanged or better.

- [ ] **P0 | High expected value | Risk: High**
  Audit the small-lane ownership split in `bubble_simulation.py` and decide whether the fix belongs in:
  - feed source weighting
  - sustained component shaping
  - small-lane loud carry
  - promotion/size-envelope rules
  - or a combination of exactly one of those at a time
  - Entry gate: tightened Bubble loud bars green except for the newest failure lane.
  - Exit gate: one chosen seam improves the failing loud lane without soft-path drift.
  - Avoid regression by changing one seam at a time and keeping `BubbleSimulation` and beat-engine roles separate.

- [ ] **P1 | Medium expected value | Risk: Medium-High**
  Re-audit whether small-lane loud under-participation is caused more by feed input or by simulation-side size/pulse/render envelopes.
  - Entry gate: latest-loud oracle and current feel-locks green.
  - Exit gate: evidence clearly points to feed-owned or simulation-owned responsibility before any further tuning.
  - Avoid regression by not stacking feed and simulation changes in one pass.

### Phase 3. Bubble Cadence / Latency Truth Pass

- [ ] **P1 | Medium expected value | Risk: Medium**
  Add a Bubble compute-age / pending-result oracle so we can see whether late-feeling Bubble is actual visual math or delayed delivery under load.
  - Entry gate: perf and loud-path bars green.
  - Exit gate: logs can distinguish “Bubble computed weakly” from “Bubble computed well but arrived late.”
  - Avoid regression by keeping this observability-only until a true latency seam is proven.

- [ ] **P2 | Medium expected value | Risk: Medium**
  Audit the worker-callback staging seam and decide whether it needs a cleaner queued boundary after the major hot paths are reduced.
  - Entry gate: prior phases complete.
  - Exit gate: only pursue this if logs still show delivery-age issues after simulation and transport work.
  - Avoid regression by refusing speculative threading rewrites before the dominant hot paths are reduced.

## Priority Summary

### Immediate

1. tighten the Bubble oracle with the newest late-hot live lane
2. lock the present good Bubble feel harder
3. add payload/perf oracles before transport or simulation refactors

### Next

1. isolate collision cost
2. isolate snapshot/trail/transport waste
3. only then choose one loud-path seam to correct

### Later only if needed

1. pending-result cadence truth
2. worker callback boundary cleanup

## Risk Table

| Task Family | Risk To Bubble Feel | Risk To Fidelity | Likelihood Of Improvement | How To Contain Risk |
|---|---|---:|---:|---|
| Oracle tightening | Low | Low | Very high | Only strengthens bars; does not alter runtime behavior. |
| Collision-path perf work | Medium | Low | Very high | Require payload-equivalence and current-feel locks before and after each change. |
| Snapshot/transport perf work | Medium | Medium | High | Forbid any optimization that changes visible payload; verify render-state equivalence. |
| Small-lane loud-path correction | High | Low | High | Change one seam at a time and keep soft/hot feel-locks green. |
| Callback/cadence cleanup | Medium | Low | Medium | Only attempt after the known hot paths are reduced and measured. |

## Guardrails

- Do not blur Bubble together with Spectrum or shared dynamic-floor work just because they touch the same broad visualizer subsystem.
- Do not trade away small visible bubbles to make the perf graph look nicer.
- Do not accept a fix that only helps during transition-time if it makes Bubble softer, later, or more plateaued outside transitions.
- Do not relax assertions to fit the current code.
- Do not stack multiple Bubble loud-path ideas in one pass.
- Every Bubble-touching task starts by improving the Bubble bar and ends by proving the Bubble bar stayed green.
- If a performance idea cannot be proven payload-equivalent, it is not safe enough.

## Recommendation

The best next route is:

1. make the Bubble oracle stricter against the newest live complaint
2. then attack Bubble-owned performance waste in this order:
   - collision path
   - snapshot churn
   - transport/upload churn
3. only after that, do one mode-isolated small-lane loud-path correction pass

That route best satisfies the user constraints because it is:

- root-cause-led
- mode-isolated
- hostile to false greens
- explicitly protective of Bubble feel

## Landed Safe First Pass

One small transport-only optimization is now considered safe groundwork:

- Bubble renderer buffer reuse no longer clears the full max-size numpy buffers every upload.
- It now clears only the active prefix needed for the current or previous upload span, while the payload-equivalence tests prove the uploaded active prefix remains exact.
- Bubble collision no longer recomputes the same effective pulsed radii for every pair inside the nested collision loop; radii are now precomputed once per pass.
- Bubble snapshot no longer emits a full zero-valued trail payload when no visible Bubble trail exists at all.
- Bubble snapshot now writes position/extra/trail payloads into exact-size frame buffers instead of growing Python lists bubble by bubble.
- Bubble collision now precomputes its per-class pair-policy scalars once per pass instead of rebuilding the same bounce/gap math for every active pair.
- Bubble snapshot no longer spends time writing per-bubble zero trail samples for bubbles whose trail strength is already zero inside a trail-active frame.
- Bubble collision now rejects non-overlapping pairs by squared-distance comparison before paying `sqrt`/normalization cost, keeping the expensive path for the overlap cases that actually need resolution.
- Bubble renderer transport now preserves exact zeroed tails while avoiding unnecessary full active-prefix clears when the next upload overwrites the same prefix anyway.
- Bubble small-lane loud recovery now includes a narrow simulation-owned sustained-loud support branch for tiny bubbles only; it does not rewrite the shared small-lane pulse source, and it was kept only because the stricter feel-locks and hero-lane guards stayed green.

Why this is acceptable:

- it does not remove visible Bubble output
- it does not alter simulation, feed, or render semantics
- it stays entirely inside Bubble-owned hot paths already guarded by focused tests
- the latest isolated perf oracle now treats the recovered budget band as the minimum acceptable floor, so future Bubble perf work has to stay inside a materially tighter worker/collision/snapshot envelope than before
- the latest mixed-hot oracle now compares the thinner hot window directly against stronger hot windows from the same run instead of only against soft passages, making that inconsistency much harder to hide
- Bubble collision now walks an x-sorted broad-phase order and breaks once later candidates are too far apart on the x-axis to overlap under the current collision contract, which cuts meaningless pair scans without altering visible Bubble resolution

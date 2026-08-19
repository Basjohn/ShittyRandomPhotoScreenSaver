# Current Plan — P2 Visualizer Recovery After Installed Acceptance Failure

Last updated: 2026-08-19 after the first installed run on the repaired logical runtime  
Branch: `main`  
Current source anchor at review: `80c8ed35f2f027522b00dcbe9795eb95b42076f4`  
Named accepted rollback/fidelity baseline: **4.7.2 / `42033c84eabbdf25ccd34bb0e83f9e553f2f8f11`**  
Architecture epoch: **single-surface OpenGL QRhi compositor + compositor-owned visualizer presentation + dedicated mode-general logical runtime**

This file owns unfinished active P2 work.

For architecture orientation, use the handoff reorientation supplied with this documentation refresh. It is doctrine only and does not override this plan.

Current installed evidence checkpoint: `Docs/P2_Installed_Acceptance_Findings_2026-08-19.md`.

Exact installed behaviour and exact current source override commit messages, test counts, comments, and claims that a slice is “done.”

The previous recovery plan successfully forced a real architectural correction. It is now stale because Slices A–E landed and the required installed run exposed the next failures.

---

# 0. Executive truth

## 0.1 P2 is NOT complete

The repaired logical runtime is a real improvement and must be retained. It does not make the installed product acceptable.

The installed run still has three user-visible failures:

1. **Pause/Play hitching remains essentially unchanged.**
2. **Paused Spectrum reveals its card but its intended idle bars are not perceptibly visible.**
3. **Overall presentation performance remains materially below the accepted class, including on the 165 Hz display that does not own the visualizer.**

Bubble is no longer showing the old catastrophic logical-cadence collapse, but it still fails the full Bubble Temporal Fidelity contract because long-tail logical and presentation gaps remain visible-risk territory.

## 0.2 The installed run DID include `--viz`

The operator ran:

```text
.\main.py --debug --perf --gpu-timing --viz --usage --viz --life --set --geo --fresh
```

The duplicate `--viz` is harmless.

Do not claim the installed run lacked visualizer diagnostics.

There are no `[SPOTIFY_VIS][LATENCY]` warning records in this run. That means no latency warning was emitted by the existing thresholded logger; it does **not** mean `--viz` was absent, and it does not authorize inventing a source-latency number.

## 0.3 Keep the architecture gains from Slices B–D

Do not broadly revert the latest round.

The following are now accepted unless new evidence directly disproves them:

- logical cadence is no longer owned by the GUI recurring timer;
- `VisualizerLogicalRuntime` is the one authoritative logical cadence owner;
- the worker scheduler now uses a high-resolution deadline clock and a non-quantized sleep path;
- logical mode-reveal readiness is separated from GUI reveal side effects;
- GUI-only reveal work stays GUI-owned;
- required logical/presentation handoffs are explicit rather than silently optional;
- mode switching works across all five modes on the worker-owned cadence;
- no second logical clock should be reintroduced;
- no 700 ms playback debounce should be reintroduced.

Slice E is accepted only for the narrow identity/lifecycle claim. It did **not** solve the perceptual Pause/Play hitch and must not be described as having done so.

## 0.4 Current source anchor

At review, `main` is:

```text
80c8ed35f2f027522b00dcbe9795eb95b42076f4
Slice E - Pause/Play identity on the qualified logical runtime
```

If `main` advances before work begins, re-read the changed files and update this anchor before making claims.

---

# 1. What the installed run actually proved

## 1.1 The old ~64 Hz scheduler collapse is fixed

The long installed runtime reported:

```text
generation                 -1   <-- invalid generation mapping defect; see §4
steps                   22636
skipped deadlines           38
slow steps                   4
failures                     0
joined                    True
```

Over the installed interval this is approximately the **89.8–89.9 Hz class**, with skipped deadlines around **0.17%**.

After Settings/recreation the replacement runtime reported:

```text
generation                  1
steps                     1621
skipped deadlines            1
slow steps                   0
failures                     0
joined                    True
```

This is a real production win. The previous stable ~63.9–64.0 Hz / ~29% skipped-deadline failure is gone.

Do not revert the scheduler merely because other performance problems remain.

## 1.2 The scheduler average is healthy; the tails are not yet BTF-green

During Bubble the logical metrics reached the expected ~89.8 Hz average, but the installed run still logged ordinary Bubble logical gaps including:

```text
49.83 ms
42.27 ms
```

The long runtime also counted four steps above the current 25 ms slow-step diagnostic threshold.

Per BTF:

- healthy average alone is insufficient;
- recurring or unexplained >33 ms logical holes are RED alarms;
- a timing repair must preserve continuous positional evolution, not merely restore an average.

The next work must therefore retain the new scheduler while tracing/removing the remaining long-tail stalls.

## 1.3 Bubble simulation admission/publication is no longer the obvious bottleneck

The final long Bubble cadence snapshot reported:

```text
offered                 11328
submitted tasks         11324
publish ratio           1.000
worker busy deferrals       4
result waiting deferrals    0
submission failures         0
stale results               0
```

This strongly exonerates the current Bubble compute lane as the cause of the remaining system-wide performance regression.

Do not tune Bubble equations, reduce its cadence, increase smoothing, or add Bubble-specific throttling to compensate for shared delivery problems.

Bubble remains the strongest perceptual canary.

## 1.4 Bubble presentation still carries unhealthy tails

Across the long Bubble interval, `state_to_paint_p95_ms` was repeatedly roughly 9–12 ms.

Measured Bubble windows:

```text
median p95        ~9.737 ms
worst p95         11.727 ms
worst max         71.797 ms
```

This is materially worse than the historical healthy ~5–9 ms p95 comparison class and repeatedly approaches the known rejected presentation-delivery class.

Do not call Bubble temporally healthy until these tails are understood and reduced.

## 1.5 The 165 Hz display proves the remaining problem is shared/system-level

The 165 Hz display does not own the visualizer, yet its completed compositor transition paint windows ranged approximately:

```text
103.8 FPS  ..  152.2 FPS
median            131.6 FPS
```

Representative accepted/poor examples:

```text
Particle     152.2 FPS
Blockspin    147.3 FPS
Wipe         131.6 FPS
Warp         103.8 FPS
later Blockspin windows ~121–143 FPS
```

This is decisive evidence against “Bubble itself is consuming the missing presentation budget.”

The remaining performance work must continue at shared GUI / compositor-delivery / runtime scheduling boundaries unless evidence isolates a narrower owner.

Do not optimize transitions individually merely because particular transition windows expose the starvation more strongly.

## 1.6 Event-loop tails remain bad

During the ordinary long run, event-loop summaries commonly showed approximately:

```text
p95             ~14–19 ms
p99             ~30–38 ms
```

After Settings/recreation, summaries degraded into approximately:

```text
p95             ~20–22 ms
p99             ~50–54 ms
```

There were larger outliers as well, including lifecycle/settings periods.

This is consistent with the user-visible report that the product remains unimpressive even though the logical worker average is now healthy.

The worker removes GUI stalls from the simulation clock; it does not make the GUI/compositor immune to the same stalls.

---

# 2. Spectrum: exact current failure

## 2.1 Slice A fixed the old first-frame blocker

The prior defect was real:

- paused Spectrum had a presentation-owned idle scene;
- missing live source generation/activation was incorrectly treated as a presentation blocker;
- first-frame primer problems forced `effective_fade = 0`;
- the card stayed hidden until Play.

That source/presentation readiness conflation has been corrected.

Retain that separation.

## 2.2 The new installed failure is visual magnitude, not reachability

The installed Spectrum shader debug snapshot proves the actual renderer received idle values:

```text
count=35
min=0.0100
max=0.0300
```

Therefore:

- the idle baseline generator ran;
- the frame reached the real renderer;
- the card/reveal path is no longer blocked by missing source identity.

But the operator sees **zero idle bars**.

Current `spectrum_presentation_smoothing.py` defines the idle baseline as only 1–3% of full scale:

```text
_IDLE_BASELINE_MIN = 0.010
_IDLE_BASELINE_MAX = 0.030
```

Current Spectrum uniform upload then multiplies bar values by `0.55` before the shader receives them.

The effective values entering shader height math are therefore roughly:

```text
0.0055 .. 0.0165
```

That can be mathematically non-zero while being perceptually absent in the installed card.

## 2.3 Gate 1 was not a true visible-pixel gate

The current Gate 1 parent is a recording QWidget stub whose `push_spotify_visualizer_frame()` only stores keyword arguments and returns `True`.

Its key content assertion is effectively:

```text
max(frame["bars"]) > 0
```

That proves data is non-zero. It does not prove the real GL Spectrum shader produces perceptible bar pixels.

Therefore Gate 1 is structurally incapable of catching the installed failure.

### Required correction

Keep:

- presentation-owned idle scene;
- source-authority separation;
- source generation/activation unset while paused;
- fresh-source wait retained for reactive Play;
- in-place replacement on Play.

Change only the idle presentation magnitude/renderer contract necessary to make the intended resting bars actually visible.

Do not feed fake audio into BeatEngine.

### Required replacement gate

A Spectrum idle gate must prove a **real visual result**, not just non-zero floats.

Preferred order:

1. real offscreen/current GL render readback or image comparison if the existing compositor test infrastructure can do it reliably;
2. otherwise a renderer-aware deterministic geometry/pixel-height contract that proves the tallest idle bars occupy a deliberately visible minimum height on representative card sizes and DPRs.

The gate must exercise the real renderer math, including the 0.55 upload scale and height-scale/profile math.

It must cover at least:

- standard Spectrum card;
- current installed enlarged Spectrum card;
- DPR 1.0 and 1.5 if practical;
- segmented and single-piece if the idle scene supports both.

The new test must fail on the current 0.010–0.030 visual result if that result is below the approved visible minimum.

Do not choose the minimum merely to make the current numbers pass. Choose it from an intentional resting-scene visual contract.

---

# 3. Pause/Play: current failure and strongest bounded suspect

## 3.1 What Slice E actually proved

Slice E proved:

- runtime identity survives Pause/Play;
- runtime generation does not intentionally churn on the edge;
- warm BeatEngine capture policy remains independent;
- cold visualizer/card/GL recreation is not intentionally invoked;
- the removed ~700 ms visualizer playback debounce remains removed.

Retain those properties.

It did **not** prove:

- no visible hitch;
- no GUI starvation;
- no presentation gap;
- no expensive edge-owned UI feedback.

The installed run says the perceptual hitch is still there.

## 3.2 Do not reopen the old debounce

No new pause-confirm timer.

No “stability delay.”

No smoothing the visualizer source to hide the edge.

No fade extension to mask the freeze.

The user reports the Pause/Play hitch is essentially unchanged. Treat that as a hard product failure.

## 3.3 MediaWidget control feedback is now the strongest bounded first target

Every Play/Pause control action starts MediaWidget feedback.

Current source:

- runs an animated feedback path when no image transition is active;
- uses `AnimationManager`;
- every animation update calls `_request_feedback_paint()`;
- `_request_feedback_paint()` calls `widget._safe_update()`.

The source itself already contains a special **static** feedback mode during compositor transitions because a normal feedback fade repaints the complete Media card repeatedly and can starve presentation delivery.

The fresh installed run gives the same mechanism direct relevance to ordinary Pause/Play:

For completed `command=play` events:

```text
paint requests per event:     35 .. 66
mean:                         ~43.7
configured duration:          1350 ms
```

Feedback animations themselves frequently ran only around:

```text
~24.8 .. 46.8 FPS
max animation gap up to ~77.23 ms
```

MediaWidget paint telemetry during those periods commonly shows:

```text
full media-card area          170400 px
average paint                 roughly 4–5 ms
max paint                     often ~7–9 ms
```

This is not yet proof that Media feedback is the sole hitch owner.

It **is** enough evidence to make it the first bounded edge-specific optimization target before speculative wake/source-handoff changes.

It also explains why ordinary visualizer mode switching can feel better than Play/Pause: mode switching does not inherently launch this 1.35-second full MediaWidget repaint stream.

## 3.4 Required Pause/Play correction shape

Preserve the feedback visual meaning.

Remove the technical waste of repainting the complete MediaWidget card dozens of times for one small control acknowledgement.

Allowed implementation shapes include, depending on current architecture:

- a lightweight child/overlay that owns only the feedback pixels;
- a cached feedback layer;
- dirty-region-only feedback painting;
- compositor-owned small feedback presentation;
- a static immediate acknowledgement if that is an explicitly accepted visual change.

Do not simply lower the animation FPS to hide cost. That keeps the same ownership mistake at a lower frequency and risks making the feedback itself visibly bad.

Do not remove feedback entirely without explicit product approval.

## 3.5 Required Pause/Play behavioral gate

The gate must cover both functional identity **and** delivery cost.

For one ordinary Pause/Play feedback event:

- visual feedback is still produced;
- visualizer runtime identity is retained;
- no cold startup/recreate occurs;
- no playback debounce exists;
- the MediaWidget parent is not repainted as a full card once per animation frame;
- full-card paint requests caused by feedback are bounded to start/end or another explicitly small count;
- the lightweight feedback owner may animate independently if cheap;
- no second logical clock is introduced.

A test that only checks runtime identity is no longer sufficient to call Gate 7 green.

---

# 4. Generation fencing defect: valid generation 0 becomes -1

This is a real current-source bug and must be fixed before generation fencing is considered trustworthy.

The initial runtime/lifecycle generation is validly `0`.

Current worker creation uses the common pattern:

```python
int(getattr(widget, "_runtime_generation", -1) or -1)
```

For valid `0`:

```text
0 or -1  ->  -1
```

The fresh installed log directly shows:

```text
initial runtime started generation=-1
post-Settings runtime started generation=1
```

Current presentation-side generation checks also use the same style of coercion and conditionally skip fencing when the resolved generation is negative.

Therefore the initial generation can silently fall outside the guard the tests claim to prove.

## Required fix

Treat `None` / missing as invalid.

Treat integer `0` as a valid generation.

Audit this exact coercion pattern across:

- logical runtime construction;
- logical publication;
- GUI presentation generation comparison;
- any compositor publication/reveal generation fence;
- tests that construct generation 0.

Do not globally replace every `or -1` in the repository. Fix only identity fields for which zero is valid.

## Required gate

Generation-fencing tests must explicitly exercise:

```text
generation 0  -> valid
generation 1  -> valid
missing/None  -> invalid sentinel
retired 0 cannot reveal/publish into replacement 1
retired 1 cannot reveal/publish into replacement 2
```

A Gate 9 suite that never uses generation 0 is incomplete.

---

# 5. Minor logical-runtime contract defect: `wake()` does not wake `_wait_until()`

Current runtime exposes:

```text
wake()
```

and documents that it nudges the logical loop out of its wait.

Current `_wait_until()` sleeps in bounded `time.sleep()` slices while checking only `_stop_event`. It does not test `_wake_event`.

Because the maximum sleep slice is currently 4 ms, this is unlikely to explain the large Pause/Play hitch.

It is still a contract/code mismatch.

## Required treatment

Do not redesign the scheduler around `Event.wait()` again; that would risk reintroducing the measured Windows quantization failure.

Either:

- make `wake()` truthfully influence the bounded sleep loop without using the old quantized timed wait; or
- remove/rename the claimed wake semantics if the runtime intentionally only guarantees <=4 ms response.

Keep scheduler cadence gates green.

This correction is lower priority than generation 0, Spectrum idle visibility, and Pause/Play full-card feedback cost.

---

# 6. Shared presentation/delivery remains unfinished P2 work

Fixing the logical clock exposed rather than solved the broader GUI/presentation starvation.

The 165 Hz non-visualizer display is the strongest proof.

## 6.1 Do not blame the visualizer merely because visualizer work is present

Frame-gap ownership records often show:

- visualizer logical presentation callbacks are individually sub-millisecond;
- compositor paint itself is often only low-single-digit milliseconds;
- nevertheless request age / dispatch pending can climb into tens or >100 ms;
- high-refresh transition delivery collapses despite no visualizer on that display.

Treat this as a shared scheduling/admission/delivery problem until evidence names a narrower owner.

## 6.2 Next shared-system questions after Pause/Play feedback

Once the edge-specific Media feedback stream is corrected, re-evaluate current logs/tests around:

- GUI dispatch-pending suppression;
- adaptive timer request acceptance;
- UI callback bursts;
- IO/compute callbacks that marshal to GUI;
- expensive ordinary widgets repainting during high-refresh compositor windows;
- settings/recreation lifecycle bursts;
- cursor/stacking/overlay callbacks if frame-gap ownership repeatedly names them;
- whether unchanged-scene/request suppression is behaving as intended.

Do not optimize Warp, Wipe, Blockspin, Particle, etc. individually unless source attribution proves transition-owned work.

The fact that different transitions expose different severity does not make them separate root causes.

## 6.3 Presentation acceptance target

Do not invent a new universal percentage merely to close the plan.

Use the accepted baseline/historical class already documented for this architecture:

- the 165 Hz display should return to the previous **low/mid-150 FPS completed-paint class** for ordinary transition windows where it previously achieved that;
- repeated ~104–132 FPS windows are a regression;
- repeated 80–100+ ms frame gaps are unacceptable;
- 60 Hz display should not show repeated missed-frame classes that visibly hitch Bubble/visualizer motion.

The exact final numeric gate should be anchored to existing accepted baseline runs, not arbitrary round numbers.

---

# 7. Execute next work in this exact order

Previous Slices A–E are historical landed work. Slices F, G, H and the
section 5 `wake()` correction are landed this round (see "Landed this round"
below). Slice I is audited; Slice J (the single installed acceptance) is the
only remaining active step before P2 can be evaluated.

## Landed this round

```text
F   db86e742  valid generation 0 survives as 0, not the -1 sentinel
G   0205579b  paused Spectrum idle bars render as visible pixels (real-GL gate)
H   838ee340  Pause/Play feedback repaints only the controls row, not the card
§5  be81f303  wake() truthfully interrupts the bounded wait (no Event.wait)
```

Each landed as its own commit with a production-shaped gate and a proven
negative control. The full combined suite shows zero regressions from these
slices; the only failures are the pre-existing contamination already recorded
in `Future_Cleanup.md` (sine_line4, visualizer_doc_references,
recovery_evidence_parser RecursionError, combined-run harness ordering).

## Slice I — shared GUI/compositor presentation starvation (audited)

Goal (unchanged, installed-run measured):

- restore high-refresh completed-paint delivery toward accepted low/mid-150 class;
- reduce request-age / dispatch-pending long tails;
- reduce 60 Hz visualizer state-to-paint tails;
- retain one compositor surface, one logical clock, latest-state publication.

Audit outcome:

- the shared admission path (`rendering/adaptive_timer.py`) is already minimal
  and contract-compliant: one dispatch-pending guard, no paint-ack backpressure,
  unchanged-scene suppression only for visualizer-only operation, GIL-friendly
  deadline wait. There is no speculative change to make there;
- the one **evidence-named** shared-GUI cost was the per-frame full-card
  MediaWidget feedback repaint, which ran on the shared GUI thread during
  exactly the Pause/Play windows where the 165 Hz collapse and event-loop tails
  appeared. That is removed in Slice H;
- attributing any **residual** 165 Hz shortfall requires the fresh installed
  run's `[PERF][DELIVERY_STAGE]` telemetry. Per the plan's own rule (shared
  problem until evidence names a narrower owner) and its anti-speculation
  directive, no further shared-scheduler change is made without that attribution.
  Gates 11/12 are inherently installed-run gates.

## Slice J — final P2 installed acceptance

ONE installed run now that F–H and the section 5 correction are landed and all
production-shaped gates are green. If the run shows Slice H closed the shared
starvation, P2 proceeds; if a residual owner remains, the DELIVERY_STAGE
telemetry names it for a bounded follow-up.

Do not ask the operator for repeated intermediate installed runs unless a
failure is literally impossible to reproduce or bound in the production-shaped
test/harness environment.

---

# 8. Updated behavioral gates

`Docs/P2_Behavioral_Gates.md` is binding and the repository replacement accompanying this plan is already revised for the post-installed-run failures.

It contains at minimum:

1. paused Spectrum **real visible pixels/height**, not `max(bars) > 0`;
2. all-five-mode production-shaped reveal;
3. scheduler cadence gate;
4. logical worker cannot touch GUI;
5. required handoffs fail loudly;
6. exactly one logical clock;
7. Pause/Play identity **plus separate delivery-cost gate**;
8. BTF;
9. generation 0 fencing;
10. known-bad historical validation where practical;
11. Media feedback does not repaint the full card per animation frame;
12. shared high-refresh presentation regression bar.

A green unit count is not a product result.

A bar is valid only if it would have failed on the installed defect it claims to prevent.

---

# 9. Bubble Temporal Fidelity remains binding

Read:

```text
Docs/Guardrails/Bubble_Temporal_Fidelity.md
```

before changing anything that can affect Bubble timing.

The current installed outcome is:

```text
logical average cadence       GREEN
skipped-deadline fraction     GREEN
Bubble worker admission       GREEN
logical >33 ms tails          RED
state->paint long tails       RED / warning-to-fail class
perceptual smoothness         user reports still unimpressive
```

Do not retune Bubble to fit technical starvation.

Do not add audio smoothing to hide timing holes.

Do not reduce logical/source cadence.

Do not use physical FPS as a substitute for source/logical/presentation timing.

---

# 10. Commit and revert discipline

## 10.1 One semantic slice per commit

Expected next sequence:

```text
F  generation-zero identity/fencing
G  Spectrum idle visual magnitude + real gate
H  Media feedback repaint isolation
I  shared GUI/compositor delivery closure
J  docs/status closure after installed acceptance
```

Do not combine unrelated “while I am here” refactors.

## 10.2 Before reverting anything

State:

- exact commit(s);
- exact files;
- exact semantic behavior lost;
- exact retained prerequisite work;
- why bounded forward-fix is less safe.

No broad “revert the worker changes.”

The repaired logical runtime is currently a demonstrated improvement.

## 10.3 Installed behavior overrides tests

If a gate says visible Spectrum and the operator sees no bars, the gate is wrong.

If a gate says Pause/Play and the operator sees the same hitch, the gate did not cover the hitch.

Fix the gate.

Do not argue with the installed product.

---

# 11. Documentation discipline

No helper scripts for moving or applying documentation.

When documentation changes are needed:

- edit the actual repository files directly;
- keep canonical files at their intended paths;
- do not add root clutter;
- do not generate `apply_docs.py`, PowerShell movers, patch scripts, or similar document-install machinery.

The repository itself is the workspace.

---

# 12. Final installed acceptance

After F–I and relevant suites are green, run with the operator’s normal diagnostic set, including `--viz`.

Acceptance exercise:

1. both-display startup;
2. Bubble long enough to judge continuous motion and reactivity;
3. all five mode switches;
4. rapid Pause/Play toggles;
5. paused Spectrum with clearly visible idle bars;
6. Settings/recreate while paused Spectrum remains visibly correct;
7. Play replaces idle bars in place;
8. populated Media CUSTOM Cancel;
9. ordinary transitions;
10. high-refresh display observed during multiple transitions;
11. clean shutdown.

Hard failures:

- Pause/Play visible hitch remains;
- Bubble shows stepping/flicker/freeze/jump;
- recurring >33 ms ordinary logical gaps remain unexplained;
- BTF source/logical/presentation alarms enter rejected class;
- paused Spectrum bars are visually absent;
- high-refresh presentation remains in persistent ~104–132 FPS class;
- mode switch hides target;
- stale generation reveals;
- generation 0 maps to invalid identity;
- second logical clock appears;
- lifecycle/GL cleanup fails.

Only after that run is acceptable may P2 be declared complete and work proceed to P5 monitor-topology/lifecycle closure.

---

# 13. Explicit non-goals for the next round

Do not:

- reopen single-surface compositor migration;
- rewrite the mode switch state machine;
- create per-mode schedulers;
- create per-transition optimizations without attribution;
- retune Bubble physics;
- reduce authored 90 Hz class;
- reintroduce pause debounce;
- smooth audio/source to hide scheduling;
- add paint acknowledgement/backpressure;
- add FIFO/catch-up;
- add a second visualizer surface;
- add QPainter visualizer fallback;
- request an installed run after every slice;
- treat raw test count as acceptance;
- generate documentation install/move scripts.

The current job is narrower:

> **preserve the repaired logical owner, make the remaining visual contracts real, remove the edge-owned full-card feedback waste, then finish the shared GUI/presentation starvation that the 165 Hz non-visualizer display proves still exists.**

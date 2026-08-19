# P2 Behavioral Gates — Post-Installed-Run Revision

Last updated: 2026-08-19  
Reviewed source anchor: `80c8ed35f2f027522b00dcbe9795eb95b42076f4`

Status: **binding P2 regression contract**

These gates exist because several previous tests asserted internal calls while the installed product remained visibly broken.

A gate is valid only if it proves the user-visible or architecture-visible end condition it claims to guard.

Where practical, prove the gate would fail against the known-bad historical revision that exhibited the defect.

---

# Gate 1 — Paused Spectrum must produce a perceptibly visible idle scene

## Defect class

The old gate proved:

```text
resolver called
bars > 0
fade > 0
```

while the installed result still looked like **zero bars**.

The current real renderer received values only in the 0.010–0.030 range, then Spectrum upload scaled them by 0.55. A recording-parent stub cannot prove those numbers create visible pixels.

## Required behavior

Paused Spectrum:

- card is visible;
- idle bars are visibly present;
- idle scene remains presentation-owned, not fake audio;
- `_waiting_for_fresh_engine_frame` remains true;
- source generation and source activation remain unset/invalid;
- no source identity is fabricated;
- on Play, fresh real current-generation data replaces idle bars in place.

## Required test shape

Preferred:

- render real Spectrum through the actual renderer/compositor path into an offscreen/current GL target;
- read back or compare a bounded image/pixel result;
- assert the idle bar region contains non-background pixels with an intentional minimum visible height.

Fallback only if reliable GL readback is impractical:

- exercise the real Spectrum renderer math in a deterministic geometry contract;
- include upload scale, card height, bar height scale, profile/power curve and segment/single-piece math;
- assert tallest resting bar maps to a deliberately visible minimum pixel height.

Cover representative:

```text
normal Spectrum card
expanded Spectrum card
DPR 1.0
DPR 1.5
segmented
single-piece where applicable
```

The test must fail on a resting scene that is technically non-zero but visually negligible.

`max(bars) > 0` is forbidden as the sole visibility assertion.

---

# Gate 2 — All five modes must actually reveal after switch

Modes:

```text
Bubble
Spectrum
Sine
Oscilloscope
DevCurve
```

For playing and paused where supported:

- switch request accepted;
- old mode teardown completes;
- target mode logical state publishes;
- target mode frame reaches presentation;
- effective target fade becomes non-zero;
- target mode becomes the scene actually presented;
- no worker-thread GUI mutation occurs;
- no thread-affinity exception is swallowed.

Use a real widget and live Qt loop.

Do not monkeypatch the fade method into “append a string” and call that visibility.

---

# Gate 3 — Logical scheduler must deliver the authored cadence

At approximately 11.11 ms authored interval for a meaningful scheduler-only window:

```text
achieved cadence            >= 88 Hz
skipped deadlines           <= 2%
recurring >33 ms gaps       none
catch-up bursts             none
step failures               0
join                         succeeds
```

Collect p50/p95/p99/max interval statistics.

This gate must reject independently:

- coarse deadline clock;
- coarse timed wait mechanism;
- any regression to the old ~64 Hz / ~29% skipped class.

Do not use “10 callbacks happened in two seconds.”

---

# Gate 4 — Worker-callable logical code cannot perform GUI/GL work

`logical_tick()` and every transitively worker-callable function must not:

- show/hide/update QWidget;
- read/write QWidget geometry for presentation;
- construct/use QPixmap/QPainter;
- mutate compositor/GL state;
- start GUI fades;
- invalidate GUI shadow/layout caches.

GUI-only functions must assert thread affinity in tests/debug.

A real worker-thread test must run enough logical steps to cross mode/readiness paths, not only the simplest steady-state tick.

---

# Gate 5 — Required handoffs are required

The logical-to-presentation mailbox and presentation request seam are required interfaces.

Missing required handoff:

- must fail loudly in tests/development;
- must not silently become “do nothing” through `getattr(..., None)`.

This gate must catch deletion/renaming of the handoff while logical work continues.

---

# Gate 6 — Exactly one logical clock

While enabled:

```text
VisualizerLogicalRuntime    active
visualizer GUI recurring timer    absent/inert as logical owner
AnimationManager listener         absent/inert as logical owner
per-mode logical timers           absent
hidden fallback logical clock     absent
```

Pause/Play and mode switching reuse the same logical runtime.

Cleanup joins it.

No architecture change may create a source/display cadence split where a second clock advances simulation.

---

# Gate 7A — Pause/Play preserves visualizer identity and warm ownership

Across rapid Pause -> Play -> Pause -> Play:

- same logical runtime object;
- same valid runtime generation;
- same mode/card identity;
- no GL/card recreation solely due to playback edge;
- no cold startup staging on warm resume;
- no 700 ms visible playback debounce;
- BeatEngine capture keepalive remains separate policy.

This is the narrow identity gate.

Passing Gate 7A does **not** mean Pause/Play is perceptually smooth.

---

# Gate 7B — Pause/Play feedback must not repaint the whole Media card per animation frame

## Defect class

Fresh installed behavior showed ordinary Play feedback producing roughly:

```text
35 .. 66 paint requests per event
~43.7 mean
1350 ms feedback duration
```

and MediaWidget full-card paint telemetry around the 4–5 ms average class over a ~170400 px card.

Current source requests `widget._safe_update()` from every feedback animation update.

## Required behavior

Keep the visual feedback.

But ordinary Pause/Play feedback must not use full MediaWidget repaint as its per-frame animation vehicle.

A production-shaped gate must prove:

- feedback appears;
- its progression/completion still works;
- full MediaWidget paint/update requests attributable to one feedback event are bounded to a very small number;
- per-frame animation work, if retained, belongs to a small/lightweight feedback owner or dirty region;
- visualizer logical runtime is unaffected;
- no second timer/clock is introduced to hide the problem.

Do not “pass” this gate by reducing feedback FPS while retaining full-card repaint ownership.

---

# Gate 8 — Bubble Temporal Fidelity (BTF)

Canonical contract:

```text
Docs/Guardrails/Bubble_Temporal_Fidelity.md
```

Required mechanically:

```text
logical cadence                   >= 88 Hz sustained
skipped authored deadlines        <= 2%
recurring ordinary >33 ms holes   none
Bubble cadence publication        no suppression class regression
protected replay/goldens          unchanged unless explicitly authorized
source freshness                  separately measured
state->paint                      must not enter known rejected class
```

Required behaviorally:

- continuous positional evolution;
- no freeze/jump cadence;
- no flicker between stale/current states;
- immediate audio reaction preserved;
- no added source smoothing;
- no flattened hot-passage elasticity;
- no lowered authored cadence.

The installed operator report remains a hard fail if the gate says green but Bubble visibly stutters.

---

# Gate 9 — Generation fencing, including valid generation 0

This gate must explicitly treat:

```text
0        valid generation
1        valid generation
None     invalid/unassigned
missing  invalid/unassigned
```

Required:

- runtime constructed for generation 0 reports generation 0;
- logical publication generated under 0 carries 0;
- GUI presentation compares 0 as a real identity;
- retired generation 0 cannot publish/reveal into replacement 1;
- retired generation 1 cannot publish/reveal into replacement 2;
- stale delayed worker publication is rejected;
- no `value or -1` coercion may map a valid 0 to -1.

A suite that begins at generation 1 is insufficient.

---

# Gate 10 — Known-bad historical validation

Where practical, run the relevant new gates against isolated known-bad revisions.

At minimum preserve evidence that:

- worker-thread reveal ownership gate fails against `a6a423bc10c44b392ef83151896039d16e38dd9a`;
- scheduler gate rejects the old coarse clock/wait behavior;
- current Spectrum visible-pixel gate fails if the idle scene is returned to the installed-invisible magnitude;
- generation-0 gate fails when `int(value or -1)` coercion is reintroduced.

Do not contort production code merely to make historical worktrees runnable.

The point is to prove the gate is capable of catching its named defect.

---

# Gate 11 — Shared high-refresh presentation must remain in accepted class

The 165 Hz display is especially useful because it does not own the visualizer.

The fresh installed run produced completed transition paint windows from roughly:

```text
103.8 FPS .. 152.2 FPS
median 131.6 FPS
```

This proves shared presentation can degrade independently of Bubble.

The final P2 bar must compare against the accepted historical single-surface class already documented for the project.

Required:

- ordinary high-refresh transition windows return to the previous low/mid-150 FPS completed-paint class where the baseline achieved it;
- repeated ~104–132 FPS windows are not accepted;
- large request-age / dispatch-pending tails must be bounded;
- no per-transition special-case optimization unless attribution names transition-owned work.

Do not replace this with average process CPU or average GPU utilization.

---

# Gate 12 — 60 Hz visualizer presentation tails

On the visualizer-owning 60 Hz display:

- compositor should make essentially every useful display opportunity under ordinary load;
- repeated 33/50+ ms visualizer-frame holes are failures;
- Bubble state-to-paint must remain outside the historical rejected ~13–15 ms p95 / ~50+ ms peak class;
- logical cadence must remain independent of display refresh.

This gate is about physical presentation continuity, not forcing one physical frame per logical step.

---

# Gate 13 — Required Pause/Play perceptual end condition

The final product gate is simple:

```text
Pause does not visibly hitch the visualizer.
Play does not visibly hitch the visualizer.
```

The automated evidence underneath it must include:

- Gate 7A identity;
- Gate 7B feedback ownership;
- BTF logical tails;
- state-to-paint tails;
- event-loop/GUI dispatch tails.

If those all claim green and the installed product still visibly hitches, the automated gates are incomplete.

Do not argue that stable identity makes the hitch acceptable.

---

# Gate 14 — Stale source/activation cannot gain visible authority

For modes requiring fresh reactive source:

- stale generation bars cannot reveal;
- stale activation bars cannot replace current presentation;
- paused presentation-owned idle state does not fabricate authority;
- Play must wait for fresh current-generation/current-activation real source before reactive authority transfers.

Spectrum idle visibility must not weaken this gate.

---

# Gate 15 — Shutdown/recreation lifecycle

After Settings/recreation and normal shutdown:

- old logical runtime quiesces and joins;
- replacement owns a new valid generation;
- stale mailbox content is fenced;
- compositor/visualizer GL resources clean up through existing ownership contract;
- no retired thread publishes after destruction;
- no duplicate logical runtime survives.

Generation 0 must be tested before the first recreation.

---

# Final acceptance rule

No single gate substitutes for the installed run.

The installed run occurs once after the active P2 slices are complete.

P2 cannot close while any of these remain:

- Pause/Play visible hitch;
- Spectrum idle bars visually absent;
- Bubble BTF tails in rejected class;
- generation 0 mapped to invalid identity;
- persistent high-refresh presentation collapse;
- stale generation/source authority;
- second logical clock;
- lifecycle/GL failure.

Test count is informational.

Behavior is the contract.

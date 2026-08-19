# Bubble Temporal Fidelity Contract

Last updated: 2026-08-19

Status: **durable focused guardrail / behavioural contract**

Canonical path: `Docs/Guardrails/Bubble_Temporal_Fidelity.md`

Short reference name: **BTF**

---

## 0. Routing shorthand

**BTF** means this entire contract.

Treat the following user phrases as explicit routing aliases to this document:

- `BTF`;
- `Bubble Temporal Fidelity`;
- `Bubble feel`;
- `Bubble feels worse`;
- `Bubble smoothness`;
- `Bubble stutter` / `stuttery`;
- `Bubble flicker` / `flickery`;
- `Bubble reactivity`;
- `Bubble elasticity`;
- Bubble being described as `late`, `flat`, `stale`, `jerky`, or `over-smoothed`.

When one of those phrases is used during SRPSS work, read this file before proposing,
implementing, validating, reverting, or accepting a change that can affect Bubble timing,
source freshness, simulation, publication, or presentation.

Do not require the operator to translate the visual complaint into technical language first.
This contract exists to perform that translation.

BTF is a behavioural contract, not a Bubble-specific architecture mandate. Bubble is often the
best canary for shared runtime starvation because continuous positional motion makes timing holes
obvious.

---

## 1. Purpose

Bubble is unusually sensitive to timing defects because its authored result combines:

- continuous positional motion;
- continuous size / elasticity evolution;
- low-energy drift and settling;
- short-lived transient and discrete-event responses;
- fast changes that must remain visually connected to the audio that caused them.

A system can preserve Bubble's equations, final state, average FPS, or worker cost and still make
Bubble visibly wrong if logical state is serviced or presented at an irregular or insufficient
cadence.

Therefore Bubble fidelity has two independent requirements:

1. **Behavioural shape** — the approved Bubble simulation, trajectories, attack, decay, overshoot,
   elasticity, settling, spatial distribution, event meaning and authored settings remain intact.
2. **Temporal fidelity** — those states are integrated and become presentation-eligible with
   sufficiently continuous timing and sufficiently low latency that the authored behaviour is
   actually visible.

Passing one does not excuse failing the other.

The operator remains final visual acceptance authority, but a report such as “Bubble feels worse”
must be treated as evidence that maps onto measurable alarm conditions below, not as an
unstructured subjective complaint.

---

## 2. Scope

Read and apply this contract whenever work can affect any of the following:

- visualizer logical cadence;
- source / analysis cadence or freshness;
- Bubble simulation scheduling;
- task/Future admission or execution;
- latest-state publication;
- GUI dispatch;
- compositor presentation;
- state-to-paint latency;
- transition-time visualizer delivery;
- Play / Pause / Resume;
- mode switching;
- Settings / CUSTOM recreation;
- shared runtime work that can starve visualizer servicing;
- any optimization that changes how often Bubble integrates, publishes, or reaches the screen.

A failure may be shared-runtime rather than Bubble-owned. Bubble is often the best canary because
continuous motion makes timing holes obvious.

Do not relabel a shared cadence or presentation failure as a Bubble algorithm problem unless
mode-owned evidence actually names Bubble work.

---

## 3. Core product definition

A healthy Bubble should look continuously alive while remaining tightly connected to the audio.

That means:

- travel/drift motion advances without visible stepping, freezes or positional flicker;
- size changes breathe and settle rather than jumping between snapshots;
- discrete hits and transients remain sharp and prompt;
- loud passages remain elastic and variable rather than flattening into a ceiling;
- quiet passages retain authored low-energy motion rather than appearing dead;
- overshoot and settling remain visible where authored;
- visual smoothing may make motion continuous, but must not smear or delay the underlying audio
  reaction;
- no architecture may obtain smooth-looking motion by reducing source/logical cadence, hiding
  transients, averaging away edges, or reducing authored reactivity.

“Smooth” here means **temporally continuous visual evolution**.

It does **not** mean additional audio smoothing.

“Reactive” means **low latency and preserved attack/transient amplitude**.

Both are required at the same time.

---

## 4. Protected behavioural shape

The Phase 2 visualizer fidelity lock established deterministic Bubble replay and quantitative
trajectory/elasticity metrics. Infrastructure work must preserve the approved replay/golden
behaviour unless an intentional Bubble behaviour change is explicitly authorized.

Representative protected isolated-impulse evidence from the established Phase 2 baseline includes:

```text
logical response latency        0 ms
attack                          21.764095 / s
bar half-decay                  120 ms
particle peak                   49
centroid speed peak             0.3353575 normalized units / s
mean-radius change peak         0.33431 / s
mean-radius excursion           0.0067272
radius overshoot ratio          0.3583855
radius settling                 260 ms
```

These numbers are reference evidence for the approved baseline, not permission to tune individual
constants until the numbers happen to match.

The protected behavioural dimensions are:

- input-to-logical response;
- attack;
- amplitude;
- decay;
- overshoot;
- elasticity;
- settling;
- trajectory;
- centroid motion;
- radius variation;
- low-energy response;
- spatial distribution;
- transient/event meaning;
- hot-passage variation;
- no artificial plateau/max-size pinning;
- no stale-event replay.

Use the protected replay/goldens and Bubble parity/reactivity harnesses to validate this layer.

---

## 5. Temporal fidelity contract

### 5.1 Authored cadence

The ordinary high-refresh Bubble logical target is approximately the **90 Hz authored service
class** unless current approved source explicitly changes that target.

At 90 Hz the nominal interval is approximately:

```text
11.11 ms
```

The important requirement is not exact metronomic 11.11 ms timing on every step. The requirement is
that ordinary runtime servicing remains near the authored class without sustained collapse or large
recurring holes.

For the current P2 recovery class, use these hard alarm thresholds:

```text
sustained logical cadence       >= 88 Hz
skipped authored deadlines      <= 2%
ordinary >33 ms logical holes   none recurring
```

These are recovery gates against the observed cadence-collapse class. If a future accepted baseline
formally changes them, this contract must be updated deliberately.

A runtime delivering approximately 64 Hz from a requested approximately 90 Hz while dropping
approximately 29% of authored deadlines is a **mechanical RED failure** even if:

- worker steps are cheap;
- `slow_steps == 0`;
- average compositor FPS is healthy;
- every unit test passes;
- final Bubble arrays are mathematically valid.

No installed visual review should be required to discover that failure.

### 5.2 Gap distribution matters more than average alone

Always inspect:

- logical Hz;
- logical interval p50;
- p95;
- p99;
- max;
- count of intervals above 25 ms;
- count above 33 ms;
- count above 50 ms;
- count above 100 ms;
- skipped/deferred logical-step count and percentage.

A healthy average with repeated 40–80 ms holes is not healthy Bubble timing.

### 5.3 No cadence substitution

Do not “fix” a scheduling problem by:

- lowering the authored Bubble cadence;
- adding a 60 Hz token clock;
- batching multiple Bubble logical steps and exposing only the terminal result;
- source/event decimation;
- display-rate division;
- paint-driven admission;
- catch-up bursts;
- smoothing across missing logical states.

The cadence owner may change. The authored behaviour may not silently change with it.

---

## 6. Logical-step visibility contract

Historical R-54 proved that high paint FPS does not protect Bubble if authored logical states are
discarded or hidden before first visibility.

The rejected mechanism:

- offered roughly 2,566 Bubble logical steps;
- submitted roughly 1,723;
- cadence-deferred roughly 842;
- kept Bubble painting around 89–93 FPS;
- kept worker cost around 1–2 ms;

yet Bubble became visibly late, stale and less elastic.

The accepted correction restored a 1.000 lane-free publication ratio in the measured path.

Therefore:

> Every integrated protected Bubble logical edge must have a valid path to become the freshest
> presentation state before that edge is semantically erased by later logical evolution.

This does not require every logical state to be physically scanned out on every display.

It does require that the architecture must not knowingly integrate a protected transient or
positional edge and then make it impossible for presentation to observe that state.

A test that only proves “the transient trigger fired” is insufficient.

The test must prove that the resulting **Bubble positional/render-state change** survived to the
publication/presentation boundary on the tick where it actually became visible.

---

## 7. State-to-screen latency contract

Historical R-62 proved the opposite failure class: Bubble can integrate and publish essentially every
logical state and still feel bad if integrated state reaches the screen too late or irregularly.

Known evidence:

```text
accepted / healthy state->paint p95 class:
~4.9 ms median across measured windows
worst measured healthy p95 around ~8.65 ms

rejected deferred candidate:
~13.2–15.4 ms p95
~52.7–56.5 ms peaks
```

The rejected candidate kept logical publication around 99.7–100%, yet Bubble became later, flatter
and less elastic.

Therefore logical publication success is not final Bubble delivery success.

Track separately:

```text
source / analysis age
    ↓
logical integration age
    ↓
render-state publication age
    ↓
GUI dispatch age
    ↓
state -> paint age
```

Do not collapse these into one average FPS number.

For current work, movement into the historical 13–15 ms p95 class with repeated approximately
50 ms peaks is a strong RED alarm and requires explanation before acceptance.

The historical approximately 5–9 ms p95 class is useful comparison evidence, not a universal
hard-coded rendering law.

---

## 8. Source freshness and reactivity

Smooth motion over stale source is not healthy Bubble behaviour.

Measure source/analysis freshness independently from logical cadence and independently from
state-to-paint.

When playback is active:

- source data must remain fresh enough for current-generation Bubble reactions;
- transient/onset events must be consumed with their intended one-shot semantics;
- a stale source must not be concealed by continuing deterministic positional motion;
- a timing repair must not trade lower visual jitter for greater audio-to-visible latency.

If Bubble movement is smooth but reactions feel late, inspect source age and event handoff before
changing Bubble damping, smoothing or shader math.

---

## 9. Continuous-motion contract

Bubble exposes cadence defects because positional state evolves continuously.

For steady authored movement:

- successive logical/render-state positions should progress continuously;
- repeated identical positional snapshots caused by technical cadence suppression are suspect;
- large unexpected position deltas after a servicing hole are suspect;
- discontinuity introduced by catch-up or an oversized dt is suspect;
- animation should not alternate between freeze and jump;
- visual state should not flicker between current and stale activation/generation snapshots.

Where a temporal harness can compare the approved trajectory under a stable cadence with the
candidate runtime schedule, it should report:

- positional delta distribution;
- centroid delta/speed distribution;
- radius delta distribution;
- repeated/stale revision count;
- large-discontinuity count.

Do not invent arbitrary tolerances solely to make a candidate pass. Anchor tolerances to the
approved replay/golden or a named accepted installed baseline.

---

## 10. Discrete-edge contract

Bubble has reactions that may exist for only a small number of logical publications.

Protected examples include:

- kick/snare-driven accents;
- size/elasticity impulses;
- overdrive/burst transitions;
- positional consequences of an event authored one tick earlier.

Rules:

- consume-once events stay consume-once;
- an event must not be replayed across many frames as a level signal;
- an event must not be integrated and then hidden by batching/coalescing before its positional result
  becomes visible;
- event protection must follow the actual resulting Bubble state, not merely the event flag.

A bypass/protection test that proves only “the edge trigger executed” is not sufficient.

It must prove the approved resulting render/positional edge survives.

---

## 11. Loud-passage elasticity

Bubble must remain active and variable under sustained loud input.

Known historical failure families include:

- living near maximum bubble size;
- constant overdrive hold;
- flattened variation;
- insufficient contraction between hits;
- stale events repeatedly re-authorizing hot state;
- raw-energy blowout;
- support/overdrive lanes remaining hot after the phrase has cooled.

Validate hot passages with behaviour metrics such as:

- big-bubble render-radius spread;
- clamp-hit frequency;
- pulse variation;
- contraction depth;
- hot-versus-soft response;
- number of distinct radius states;
- overdrive hold duration;
- event-consumption count.

A candidate that is “very reactive” only because Bubble lives continuously at maximum response
fails BTF.

---

## 12. Low-energy and idle behaviour

Quiet or paused Bubble should retain its authored personality.

Do not create apparent smoothness by forcing Bubble static unless the approved mode behaviour is
actually static.

Protect:

- low-amplitude drift;
- gentle radius evolution;
- authored paused/idle timing;
- absence of sudden cold restart on ordinary warm resume;
- continuity through Play/Pause where the runtime contract says state/resources remain warm.

A Play/Pause edge that creates large logical holes is a BTF failure even if the media state itself
changes promptly.

---

## 13. Mode switch, Play/Pause and lifecycle edges

Measure Bubble temporal fidelity across:

- cold startup;
- ordinary playback;
- Play -> Pause;
- Pause -> Play warm resume;
- Bubble -> another mode;
- another mode -> Bubble;
- Settings reconstruction;
- CUSTOM suspend/resume;
- display transition overlap;
- high-refresh and 60 Hz displays.

Do not assume a mode switch and a playback edge exercise the same ownership path.

If ordinary mode switching is smooth while Play/Pause hitches, treat that difference as useful
causal evidence rather than averaging the scenarios together.

No lifecycle correction may declare success while Bubble resumes with:

- a large visible freeze;
- stale-generation state;
- an avoidable cold ramp;
- repeated 33+ ms logical holes;
- a new cadence owner that has not reached the authored service class.

---

## 14. Shared-runtime attribution

Bubble is a canary, not automatically the culprit.

Before changing Bubble-specific math, compare:

```text
Bubble-owned compute cost
Bubble-owned render/GPU cost
source age
logical cadence/gaps
GUI event-loop availability
state->paint latency
shared cache/reconstruction/provider work
transition/startup work
```

If Bubble worker/render cost is cheap while logical holes are large, fix the shared owner first.

Do not:

- reduce Bubble fidelity because GUI work is starving the visualizer;
- create a Bubble-only cadence lane when the defect is mode-general;
- tune individual Bubble presets to hide scheduling defects;
- change shader motion to compensate for stale logical state.

---

## 15. Mechanical BTF alarm panel

When the user reports Bubble as stuttery, flickery, jerky, late, flat, stale, less elastic, less
reactive, or worse after a scheduler/presentation change, check this panel before requesting
another subjective run:

```text
A. LOGICAL SERVICE
   requested logical Hz
   achieved logical Hz
   skipped/deferred deadline count + %
   logical dt p50/p95/p99/max
   >25 / >33 / >50 / >100 ms hole counts

B. SOURCE
   current-generation source age
   transient/event age
   stale-generation rejection
   consume-once event count

C. LOGICAL FIDELITY
   protected replay/golden exactness
   impulse response / attack / decay / overshoot / settling
   trajectory / centroid / radius metrics
   hot-passage variation and clamp/plateau metrics

D. PUBLICATION
   logical step -> render-state publication ratio
   repeated/stale revision count
   protected visible-edge survival

E. PRESENTATION
   state -> GUI dispatch age
   state -> paint p50/p95/p99/max
   >25 / >33 / >50 ms age counts
   current activation/generation identity at paint

F. EDGE SCENARIOS
   ordinary playback
   transition overlap
   Play -> Pause
   Pause -> Play
   mode switch into/out of Bubble
   Settings/CUSTOM resume
```

Any obviously disqualifying mechanical result stops acceptance before asking the operator whether
Bubble “feels okay.”

---

## 16. Current hard RED examples

The following are known disqualifying shapes unless a later explicitly accepted contract supersedes
them:

```text
~90 Hz requested -> ~64 Hz achieved
~29% authored deadlines skipped
recurring ~40–80 ms logical holes
```

These mechanically explain visible stepping/poor positional continuity.

Also known rejected:

```text
~99.7–100% logical publication
but state->paint p95 ~13–15 ms
with ~52–56 ms peaks
```

This mechanically explains late/flatter/less-elastic Bubble despite correct logical publication.

Also known rejected:

```text
~89–93 paint FPS
cheap ~1–2 ms worker
but ~1/3 authored Bubble steps cadence-deferred
```

This mechanically explains stale/flattened visible reactions despite apparently good paint FPS.

These examples exist specifically to prevent future agents from calling such runs “green.”

---

## 17. What is not enough to pass BTF

None of the following alone establishes Bubble temporal fidelity:

- average FPS;
- paint FPS;
- worker duration;
- `slow_steps == 0`;
- final-state equality;
- unit tests of the scheduler mechanism;
- a mailbox publishing successfully;
- exact deterministic simulation under synthetic perfect timing;
- proof that a transient trigger fired;
- proof that `update()` was requested;
- proof that a mode became logically active;
- zero GPU bottleneck;
- subjective “looks smoother” after adding more audio smoothing.

A pass requires the relevant chain from source through authored logical evolution to screen-eligible
state to remain healthy.

---

## 18. Validation layers

Use the minimum relevant combination of:

### Layer 1 — deterministic behavioural lock

Protected visualizer replay/goldens and Bubble behaviour tests.

Purpose:

- equations;
- response;
- amplitude;
- attack/decay;
- elasticity;
- trajectory;
- event semantics.

### Layer 2 — runtime-shaped temporal lock

Use the real cadence/scheduler ownership shape.

Purpose:

- achieved cadence;
- deadline skipping;
- dt gaps;
- one-in-flight semantics;
- protected-edge survival;
- publication ratio.

A scheduler test that merely proves “N callbacks eventually happened” is insufficient.

### Layer 3 — presentation delivery

Purpose:

- revision freshness;
- GUI dispatch;
- state-to-paint latency;
- generation/activation identity;
- 60 Hz + high-refresh behaviour;
- transition overlap.

### Layer 4 — installed operator review

Purpose:

- final perceptual confirmation;
- driver/runtime effects not represented in synthetic tests.

Layer 4 remains required for relevant visual/timing changes, but Layers 1–3 should catch
mechanically obvious BTF violations before operator time is spent.

---

## 19. Golden and baseline policy

Infrastructure work must verify existing behavioural goldens.

Do not regenerate Bubble goldens merely because a scheduler/presentation architecture changed.

Changing the timing owner is not permission to redefine Bubble feel.

If an intentional product decision changes Bubble behaviour:

1. state exactly which BTF dimension changes;
2. provide old/new quantitative comparison;
3. obtain explicit approval for behavioural change;
4. update protected goldens deliberately;
5. update this contract if the durable behavioural definition changed.

---

## 20. Evidence sources / negative controls

Important existing evidence:

### Phase 2 Visualizer Fidelity Lock

`Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md`

Use for:

- deterministic baseline;
- trajectory/elasticity metrics;
- replay/golden policy.

### R-54 Bubble Cadence Gate

`Docs/Historical_Bugs/R-54_Bubble_Cadence_Gate.md`

Use as negative control for:

- artificial cadence token;
- batched logical steps;
- good paint FPS hiding poor visible reactivity;
- one-third logical deferral destroying feel.

### R-62 Transition-Scoped Presentation Deferral Bubble Regression

`Docs/Historical_Bugs/R-62_Transition_Scoped_Presentation_Deferral_Bubble_Regression.md`

Use as negative control for:

- logically correct Bubble reaching screen too late;
- healthy publication ratio failing because presentation age worsened;
- testing a trigger rather than its resulting visible Bubble edge.

### Bubble parity / reactivity harnesses

Current relevant tests/tools include Bubble reactivity, cadence/temporal fixtures, replay goldens and:

`tools/bubble_parity_harness.py`

Use them for behaviour-shape comparison, not as a substitute for live scheduler/delivery evidence.

---

## 21. Decision rule

When a Bubble-affecting candidate is evaluated:

```text
behavioural shape preserved?
        |
        +-- NO -> reject / rollback or explicitly authorize behaviour change
        |
        YES
        |
authored logical service healthy?
        |
        +-- NO -> reject; fix cadence/owner
        |
        YES
        |
source freshness / edge survival healthy?
        |
        +-- NO -> reject; fix source/event handoff
        |
        YES
        |
state delivery healthy?
        |
        +-- NO -> reject; fix dispatch/presentation
        |
        YES
        |
installed visual review healthy?
        |
        +-- NO -> reject and use the measured chain to localize missing fidelity
        |
        YES -> BTF passes for the exercised scenario
```

Do not collapse these stages into one score.

---

## 22. Durable shorthand

**BTF** means:

> preserve Bubble's approved behavioural shape **and** deliver it with authored-rate logical
> continuity, low source-to-visible latency, protected transient/positional edges, and healthy
> state-to-screen timing.

If the user says **“BTF failure”**, **“check BTF”**, or **“this violates BTF”**, evaluate the
affected change against this entire contract, especially the mechanical alarm panel in Section 15.

Do not require the user to restate the metrics or explain what “Bubble feel” means.

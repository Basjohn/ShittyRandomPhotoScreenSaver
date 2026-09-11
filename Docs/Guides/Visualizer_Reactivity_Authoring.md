# Visualizer Reactivity Authoring Guide

Last updated: 2026-09-10

Status: **binding authoring guidance for new/reactivity-changing Visualizer work**.

This guide collects the signal-selection and response-shaping lessons that SRPSS modes repeatedly had to rediscover independently. It does **not** replace a mode's accepted goldens, Bubble Temporal Fidelity (BTF), the Visualizer Presentation guardrail, or an explicitly authored mode-specific contract. Those remain stronger when they are more specific.

The purpose is to stop a new mode from spending days repeating already-proven failure patterns: dead post-AGC response, raw-energy blowout, hot-chorus flatlining, stale event replay, absolute-loudness particle spam, viewport-dependent reaction loss, and smoothing that hides delivery defects instead of fixing them.

---

## 1. Start by separating response jobs

Do not ask one scalar to mean all of these things:

1. **presence / silence permission** — is there enough current acoustic support to author new reactive state at all?
2. **event admission** — did a kick, vocal, snare, onset, rise or other discrete event actually happen?
3. **event magnitude / motion intensity** — once admitted, how strong/fast/large should the response be?
4. **sustained passage weight** — how heavy/full/active should the visual feel across a phrase or chorus?
5. **continuous articulation** — how should shape, contour, rotation or secondary motion follow ongoing energy?
6. **presentation smoothing** — how should already-authored state reach the screen without visual stepping?
7. **idle motion** — what remains alive without pretending silence is music?

A source that is excellent for one job may be actively harmful for another. Sphere became healthy only after admission, particle velocity, particle population, sustained fullness and visual interpolation stopped sharing false authority. Bubble/Blob repeatedly hit the same class of error through support/overdrive/event coupling.

---

## 2. Signal choice: use the freshest signal that matches the job

| Signal family | Good uses | Bad uses / proven traps |
| --- | --- | --- |
| **Raw pre-shape / pre-AGC analysis spectrum** | onset/flux, local spectral change, fast contrast, peak-picking | directly driving every continuous visual dimension; using raw magnitude without local normalization/headroom |
| **Live pre-AGC band energy** | current acoustic presence, silence gating, sustained passage weight, slow adaptive floor/peak, local positive-jump evidence | absolute event magnitude, particle count, or any response whose full range would become normal in loud passages |
| **Control-normalized/support-aware energy** | continuous articulation, contour, broad routing, bounded mode-local pressure | treating a hard-clamped control value as proof that every hot-passage event is maximum strength |
| **Smoothed/post-AGC/display bars** | stable displayed bars/curves, deliberately sustained envelopes, visual settling | local onset/event detection when attack/freshness matters; feeding one mode from another mode's presentation-shaped signal |
| **Typed transient/event bus** | semantic kick/vocal/snare/onset admission and consume-once accents | polling/reusing one event as a level signal; using clamped event confidence as maximum presentation velocity/power |

Sphere's rejected spectral-flux implementation is the cleanest negative example: `get_smoothed_bars()` had already passed through Spectrum-oriented shaping, temporal bar smoothing and AGC/play-ramp behavior. That made a Sphere-local onset detector depend on another mode's display signal. The accepted path uses the already-computed, temporally unsmoothed, pre-shape/pre-AGC analysis spectrum instead.

Conversely, raw/pre-AGC is **not** automatically better everywhere. Bubble/Blob proved that pushing hotter raw pressure through downstream math tuned for a cooler smoothed signal simply changes “dead” into “blown out.” Source choice and response math must be calibrated together.

---

## 3. Loud passages: preserve contrast instead of penalizing loudness

A new mode must be explicitly tested on a hot chorus or dense wall of sound. Quiet-song reactivity is not enough.

### Proven failure

Early clamping such as:

```text
raw energy -> min(1.0, energy * gain) -> response
```

throws away the remaining contrast exactly where loud music needs it most. Bubble historically showed `bass=1.000 mid=1.000` with near-zero useful variation through hot sections. Sphere later showed the related population failure: absolute pre-AGC passage energy around `2.0-2.5` fed a density curve already saturated at `1.5`, so practically every admitted event became full-density.

### Proven direction

Keep loud-passage eligibility and recover **local contrast**:

```text
current live energy
    + slower local baseline
    -> positive jump above baseline

raw analysis spectrum
    + adaptive local threshold
    -> flux / threshold contrast
```

Typed events remain valid evidence over a loud bed. Do **not** reduce a kick/vocal because the surrounding passage is loud. Instead, separate the question “did the event happen?” from “how much presentation reward did this event earn?”

Sphere's current detached-flow contract is the concrete example:

- typed/onset evidence remains admission authority;
- live pre-AGC presence prevents silence from authoring new cohorts;
- local positive energy jump + raw spectral flux provide granular motion evidence;
- absolute passage loudness does not own cohort population;
- maximum population requires exceptional event + motion evidence rather than merely a loud song.

---

## 4. Preserve headroom; clamp late

The most repeated mathematical failure is **premature saturation**.

If the source naturally occupies `0..2.5`, a response that reaches full at `1.0` or `1.5` is likely to spend ordinary loud passages pinned. Once a signal is hard-clamped, downstream math cannot recover lost variation.

Prefer this shape:

```text
raw/current source with useful headroom
-> local normalization against observed low/high or floor/peak
-> response shaping
-> final bounded presentation value
```

A simple normalized lane is often enough:

```text
x = clamp((signal - low) / (high - low), 0, 1)
```

Then choose the curve for the visual meaning:

- `pow(x, gamma)` with `gamma > 1` makes maximum response harder to reach and preserves more room in the middle/high range;
- `gamma < 1` makes weak signals more visible, but can easily make everything feel permanently hot;
- `smoothstep` is useful when a soft entrance/exit is desired without inventing a new time-domain smoother;
- separate attack/release envelopes are preferable when the visual should rise promptly but relax more slowly.

Do not tune by the mathematical elegance of the curve. Inspect **occupancy**: how often real music sits below 10%, in the middle, above 90%, and exactly at the ceiling. A curve that spends half a song at `1.0` has failed even if its equation is tidy.

---

## 5. Different timescales deserve different math

SRPSS has repeatedly succeeded when short-lived events and sustained motion are solved independently.

### Fast/discrete

Use typed events, peak-picked flux, Schmitt/rise edges or another explicit event mechanism. Add a refractory/debounce only to prevent one physical event from authoring repeated discrete rewards. Consume one-shot scheduler events once; do not poll `peek_latest(...)` every frame when the semantic is an edge.

### Medium continuous response

For things such as shape articulation or rotation speed, use short asymmetric attack/release smoothing. Fast attack + slower release can preserve punch without jittering back to zero immediately.

### Slow sustained response

Whole-object fullness/growth should use a much slower envelope and/or slow adaptive floor/peak. Sphere's sustained body weight is deliberately slow so a loud passage reads heavier without becoming a giant beat pulse.

### Presentation-only interpolation

When event timing is already correct but geometry looks discontinuous, interpolate **after** the event has been authored. Sphere Fragment Interpolation is the pattern: the packet exists on the exact event frame; only rendered displacement follows through a short position/velocity-continuous response.

Do not fix missed logical/presentation frames by adding more audio smoothing. BTF and the Spectrum tall-viewport history both show that delivery holes can masquerade as bad mode smoothing. Fix cadence/freshness first.

---

## 6. Admission and reward are different authorities

Binary admission is appropriate for genuinely discrete state: spawn a cohort, pop a bubble, author a fragment packet, queue tracer travel.

The *reward* after admission should usually remain continuous:

```text
qualifying event -> admitted
admitted event + continuous evidence -> magnitude / speed / population / distance
```

This avoids two opposite failures:

- threshold barely crossed -> full-power visual explosion;
- threshold not crossed -> nothing at all even though a continuous response would have been appropriate.

Do not multiply independent evidence blindly before admission; that can erase legitimate events. Multiplication/convex shaping is safer **after** admission when it is being used to make a full presentation endpoint deliberately rare.

---

## 7. Presence and playback state are not the same thing

`playing=True` means the source is active. It does **not** mean the current frame contains sound.

A mode that authors new discrete particles/packets must have a current acoustic-presence rule if silence would otherwise create visible activity. Sphere's intake gate is the proven pattern:

- hysteresis prevents gate chatter around the boundary;
- a stricter current-authoring floor prevents stale/latched event evidence from creating a new cohort in near-silence;
- existing in-flight cohorts may finish naturally;
- the silence gate does not raise the shared transient thresholds or weaken legitimate events.

Idle motion remains a separate authored visual choice. Never use fake music energy merely to keep a mode visually alive when an explicit idle lane can own that behavior honestly.

---

## 8. Avoid stale-event replay

One-shot events must remain one-shot.

Bubble/Blob historically reused recent scheduler events with `peek_latest(...)` every frame. One valid event then behaved like a sustained level for its entire max-age window, repeatedly re-authorizing burst/overdrive/stage lanes. The result looked “reactive” in logs but was actually a fake permanently-hot state.

Rule:

```text
discrete event -> consume once at the mode handoff / logical owner
continuous level -> sample continuously
```

Do not convert one into the other accidentally.

---

## 9. Geometry must not become a hidden gain control

Reactivity is not only audio math. A correct logical response can become visibly weak if viewport/domain projection applies a second compensation.

R-69/Bubble is binding:

- solve authored motion/radius/history in its proper content domain;
- project into expanded viewport space once;
- do not divide reaction amplitude again because the viewport became wide/tall;
- do not globally compress the full mode merely to keep an extreme tail inside bounds;
- if one tail/overshoot is excessive, target that proven tail only.

Spectrum's tall-viewport history adds the timing equivalent: a presentation delivery gap becomes a larger physical-pixel jump on a tall viewport. Do not lower amplitude or source energy to hide a cadence problem.

---

## 10. Source configuration is part of reactivity

A renderer can be perfectly implemented and still receive the wrong musical lanes.

Historical H5c work proved that losing configured Spectrum notch/shaping boundaries changed the bass/mid source lanes before mode logic even ran. Therefore preset -> canonical Settings -> technical/source application -> BeatEngine/audio lane -> mode capture must be treated as one reactivity chain.

A green renderer/replay test that begins *after* feature state already exists does not prove that a live preset actually reaches the source owner.

When a mode looks globally too weak/hot, trace the first bad stage. Do not immediately add mode gain.

---

## 11. Response math anti-patterns

Treat these as warning signs:

- early `min(1.0, ...)` / hard clamp before contrast has been extracted;
- raw/pre-AGC source swapped in while downstream gains/holds remain tuned for a smoothed source;
- smoothed display bars reused as an onset detector;
- absolute passage loudness used as event strength or particle population;
- generic “crest” or held high level used as repeated discrete packet authority;
- one event object replayed across many frames;
- one scalar independently multiplied by several “reactivity” controls until the useful range collapses;
- very permissive overdrive/hold gates that ordinary phrases occupy continuously;
- giant global gain added to fix one quiet song;
- visual smoothing added to hide scheduler/presentation holes;
- viewport/domain scaling applied twice;
- `playing` used as acoustic admission;
- a new timer/poller/FFT/audio worker created because the mode wants a different response signal.

---

## 12. Minimum new-mode reactivity workflow

Before polishing a new mode, define its reaction vocabulary in plain language:

```text
idle:
sustained quiet passage:
sustained loud passage:
kick:
snare:
vocal rise/swell:
generic onset:
release back toward calm:
```

Then:

1. choose an existing audio/analysis authority for each semantic; do not create a second FFT or audio owner;
2. keep presence, event admission, event magnitude and sustained support separate unless evidence proves they can share;
3. preserve source headroom through the mode's local normalization;
4. choose attack/release/refractory times from the visual meaning, not from one global smoothing constant;
5. establish neutral, weak, medium, strong and maximum synthetic cases and assert monotonic ordering;
6. explicitly test **silence**, a quiet song, ordinary material, a hot chorus/dense passage, and isolated strong kick/vocal events over a loud bed;
7. inspect output occupancy/distribution, not only averages;
8. test preset/runtime source configuration reachability, not only already-built feature frames;
9. test canonical/wide/tall geometry without changing authored response amplitude;
10. run installed eyes-on validation; synthetic tests do not prove musical feel.

If the mode is dead, find whether the failure is source, normalization, event semantics, logical evolution, delivery, geometry or presentation **before changing gain**.

---

## 13. Diagnostics that have paid for themselves

Useful low-noise diagnostics expose the chain, not giant arrays:

- source/raw/pre-AGC support;
- local baseline/floor/peak where relevant;
- event type and confidence;
- local contrast / flux ratio;
- resolved continuous motion/intensity;
- final bounded response/population;
- logical revision/activation identity;
- source age and state-to-screen/delivery gaps where presentation is suspect.

Look for patterns such as:

- too many exact zeros;
- too many exact ones;
- high average with no variance;
- gate/event activity during true silence;
- healthy logical variation but stale presentation;
- correct canonical behavior that shrinks/blows out only at extreme geometry.

Bounded diagnostics must use existing cadence/owners. Do not add a diagnostic timer or poller.

---

## 14. Evidence / negative-control map

Read these for the cases behind this guide rather than copying their old implementation literally:

- `Docs/Guardrails/Bubble_Temporal_Fidelity.md` — behavioral shape + temporal fidelity; loud-passage variation; cadence/delivery negative controls.
- `Docs/Historical_Bugs.md` **U-02 Bubble / Blob Signal-Contract Trap** — dead smoothed/post-AGC hold vs raw-energy blowout, stale-event replay, hot-chorus hard-ceiling failure.
- `Docs/Historical_Bugs/Voxel_Sphere_Clamped_Event_Strength_Was_Not_Particle_Velocity_2026-09-10.md` — event admission confidence is not continuous particle velocity authority.
- `Docs/Historical_Bugs/Voxel_Sphere_Absolute_Loudness_Pinned_Particle_Density_2026-09-10.md` — absolute passage loudness is not event population authority.
- `Docs/Historical_Bugs/Voxel_Sphere_Playback_State_Is_Not_Ingress_Authority_2026-09-10.md` — playback state is not acoustic presence.
- `Docs/Historical_Bugs/Voxel_Sphere_Global_Intake_Decay_Was_Not_Velocity_2026-09-10.md` — one global decay is not a real per-cohort motion/arrival contract.
- R-69 / Bubble viewport evidence — viewport adaptation may not globally damp authored reaction.
- R-76 / tall Spectrum evidence — physical-pixel flicker caused by delivery/temporal scaling must not be “fixed” by reducing response.

Historical files are evidence and negative controls. Current source + `Spec.md` + current guardrails remain implementation authority.

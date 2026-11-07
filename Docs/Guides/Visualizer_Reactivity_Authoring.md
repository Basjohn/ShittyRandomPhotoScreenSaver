# Visualizer Reactivity Authoring Guide

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
| **Live pre-AGC band energy** | current acoustic presence, silence gating, sustained passage weight on a fixed scale, local positive-jump evidence | absolute event magnitude, particle count, or any response whose full range would become normal in loud passages |
| **Control-normalized/support-aware energy** | continuous articulation, contour, broad routing, bounded mode-local pressure | treating a hard-clamped control value as proof that every hot-passage event is maximum strength |
| **Smoothed/post-AGC/display bars** | stable displayed bars/curves, deliberately sustained envelopes, visual settling | local onset/event detection when attack/freshness matters; feeding one mode from another mode's presentation-shaped signal |
| **Typed transient/event bus** | semantic kick/vocal/snare/onset admission and consume-once accents | polling/reusing one event as a level signal; using clamped event confidence as maximum presentation velocity/power |

### 2A. Measured signal scales: real music is far louder than "1"

Agents (and earlier SRPSS work) repeatedly calibrated against an imagined `0..1` world. Real playback is nowhere near
it. Measured on the operator's machine (Spotify via WASAPI loopback, 2026-10-03, technical profile sensitivity 0.97,
energy boost 1.18, input gain 0.98; `[SPHERE_AUDIO]` diagnostics):

| Signal (accessor) | Silence | Quiet moments / fade-ins | Ordinary to loud music |
| --- | --- | --- | --- |
| live pre-AGC bands (`get_live_pre_agc_energy_bands`, clamped at 2.5) | 0 | 0.1-1.9 | **pinned**: bass 2.5 almost always, mid 1.3-2.5, high 0-2.5 |
| transient-bus loudness (`get_musical_level()[0]`, peak band, unclamped) | 0 | 0.2-2 | **3-17**, typically 5-12 |
| presence (`get_musical_level()[1]`, loudness / its 6 s running level) | 0 | 0.03-0.6 | **0.35-2.0, about 1** at the track's own level |
| control / support lanes (`get_pre_agc_energy_bands`, `get_bubble_energy_bands`) | 0 | low | 0..1, normalised (bounded by design) |

Consequences, all learned the hard way:

- **Absolute thresholds in `0..1` units mean "is it silent?" and nothing more.** A gate at 0.09 or a slider floor in
  `0..1` on the live or loudness lanes never closes during music (Sphere's intake gate and energy floors did exactly
  that until 2026-10-03). The absolute numbers also move with the technical profile and the source's own volume.
- **Read loudness on the fixed real-music scale; never learn a level from the track** (operator 2026-10-04). How loud
  a passage is (`PassageIntensity`) and how far a hit stands out (`musical_emphasis`) are fixed functions of the real
  loudness around `MUSICAL_USUAL_LOUDNESS` (8.5: the median onset and eased passage loudness of four recorded songs).
  Every learned level tried (a slowly falling peak, a 20 s usual level, a learned usual onset presence) flattened a
  sustained loud chorus as it learned it, so reactions faded inside the same chorus, and resets re-seeded it so modes
  overreacted after a preset hotswap. A fixed scale follows playback volume instead: quieter listening reacts less,
  consistently. Near-silence is gated on the absolute scale only (`transient_bus.audible`). `musical_weight`'s second
  factor, presence against a 6 s running level, is itself a learned level: a quieter passage after a loud one reads
  less until the running level catches up, then more. Waveform Ribbon dropped it (7 Nov); the other modes still use it
  and are on the plan to follow.
- **Memoryless means the same music draws the same response (operator, 7 Nov 2026: "Adaptivity is the enemy").** The
  rule, what counts as adaptive and what replaces it are in §2B; every response path obeys it.
- **A clamp is not a normaliser.** The 2.5 clamp on the live lane is a safety bound; ordinary music saturates it, so
  no contrast survives there.
- **Silence must not teach a running level.** A running reference that decays through a pause makes the music's
  return look tens of times louder than usual (presence 46 was measured); the bus holds its level through
  near-silence.

Sphere's rejected spectral-flux implementation is the cleanest negative example: `get_smoothed_bars()` had already passed through Spectrum-oriented shaping, temporal bar smoothing and AGC/play-ramp behavior. That made a Sphere-local onset detector depend on another mode's display signal. The accepted path uses the already-computed, temporally unsmoothed, pre-shape/pre-AGC analysis spectrum instead.

Conversely, raw/pre-AGC is **not** automatically better everywhere. Bubble/Blob proved that pushing hotter raw pressure through downstream math tuned for a cooler smoothed signal simply changes “dead” into “blown out.” Source choice and response math must be calibrated together.

### 2B. No adaptivity: the same music draws the same response (binding)

Operator, 7 Nov 2026: "Adaptivity is the enemy"; "A soft start with vocals peaking should read the same as a chorus
dropping to soft and vocals peaking there if they match"; "Dynamics are fucking awful ... You cannot reliably do this
for music you cannot analyse ahead of [time]."

- **The rule.** Anything that sizes, gates or scales what the viewer sees is a function of the CURRENT music only.
  Music cannot be analysed ahead of time, so any memory in a response path makes the same moment look different
  depending on what came before: a loud passage starts big and shrinks, the same step draws a different rise, a song
  reads "better later" or flatlines in a hot chorus. Smoothing the current level (attack/release followers, cascaded
  stages) is allowed and needed; comparing it against a level learned from the track is not.
- **What counts as adaptive (each was in production; never re-add one under another name):**
  - **phrase-mean widening:** swings widened about a learned ~3 s mean of the drive itself (Waveform `PHRASE_DIP` /
    `PHRASE_RISE`): the widened swell sank back over 3 s as the mean caught up, so a loud passage started big and
    shrank;
  - **a learn gate:** a learn rate that pauses a memory at dips (Waveform's fell to 0 at every presence dip and sat
    below .5 on 39% of music ticks): the same soft->loud step drew x1.0 to x3.4 the memoryless rise depending on it
    (Anything: none for 30 s; Growing Pains, 1985: x2.7-3.4);
  - **a remembered or decaying peak** used as a divisor or gain (Waveform's retired Adaptive Response, Spline Curve's
    body peak, a "slowly falling peak", a learned usual level, Dynamic Floor's learned average, §13A): a spliced 5 s
    break sized the following 10 s 5-9% up, and a quieter passage was re-normalised back up to loud reach within a
    verse;
  - **a presence ratio** (loudness over its own running level: the bus `presence`, `musical_weight`'s second factor)
    used as a gain or gate: it gated Waveform's body, so a quieter passage after a loud one read less until the
    running level caught up, then more;
  - **a per-block peak input normaliser** (each PCM block scaled to a target peak): it turns a louder, peakier
    passage down against a softer one, and stepped near-silence by 2.8x at a .05 peak;
  - **contrast about a running mean** (old Breathing widened each drive about the phrase mean; an "accent" sized by
    its weight above the recent mean, §13C);
  - **per-kind running-mean contrast on kicks:** an onset already measured against the bus's adaptive threshold,
    judged again against a running mean of its own kind, zeroed 2/3 of kicks and faded a steady beat to <1% of its
    first kick, so songs looked reactive at the start and muted in the middle (§13D).
- **What replaces it:**
  - **a fixed response on the real-music scale:** drive = gain x target^curve, eased above a knee toward a ceiling
    below 1 (Waveform `fixed_response`: height/lift 1.2 x t^.75/.82, every other drive 1.12 x t^.86, knee .8,
    ceiling .92), the same for every song, calibrated once on long recordings to what the replaced path VISIBLY did,
    not hotter (§13D "no adaptive response gain");
  - **absolute audibility gates:** a smoothstep on loudness on the fixed scale (`transient_bus.audible`), never a
    ratio against recent loudness;
  - **a fixed pre-FFT input gain** (Waveform `bar_computation.RAW_SIGNAL_INPUT_GAIN` 2.8: the gain the normaliser
    always landed on in real playback, block peaks .14-.30 on eight recordings, so every calibrated anchor stayed
    put);
  - **release cascades within the authored Decay:** phrase-scale swings come from a release that actually lets go
    (each stage of a two-stage cascade takes a share of Attack/Decay, Waveform `CASCADE_SHARE`, so the visible release
    is about the authored Decay), and Breathing only shortens that release in a soft passage, a function of the current
    passage;
  - **travelling and event channels for beats**, and channels that do not fight the shape for kicks the geometry
    cannot show (Waveform's Kick Accent, §13D).
- **The one legitimate adaptive threshold is event ADMISSION.** "Did an onset happen?" may compare flux against a
  short local threshold (about a second, §3). It decides admission only, never size: the same kick right after a dense
  passage scores .22 against .61. Size every reward on the fixed scale (`musical_emphasis`, `passage_ramp`).
- **Prove it in continuous play.** Replay songs back to back without a reset and splice a 2-5 s break into recorded
  music (§13D "A break is a test of every running reference"); score the response against the song's own PCM
  (`tools/visualizer_replay/waveform_music_response.py`, which flags re-scaling at equal loudness early vs late).
  Anything that still differs once its followers settle is a running reference to remove.
- **Known remaining violations** are on the plan (`Current_Plan.md` §3 "Learned levels still in other modes"):
  `musical_weight`'s presence ratio in Spline Curve, Extruded Bubble, Neon Lake, Oscilloscope and Sphere, and Spline
  Curve's remembered body peak; Waveform's onset reward is still sized by the bus's adaptive flux threshold
  (`Current_Plan.md` §1 item 2). Remove them; never copy them into a new mode.

### 2C. Vocals lead; bass must not drown them (Waveform Ribbon, 7 Nov 2026)

Operator: "Vocals ARE more important than bass, secondary to vocals are changes (like kicks or vocals) during sustained
bass"; "Bass is tricky it cannot be completely ignored but it easily drowns out everything else"; "Vocals are key to
always keep an eye on though as well as of course the waveform reaction trace tool."

- **Order of authority:** vocals first; then changes (kicks, vocal entries) inside sustained bass; bass kept, but
  never the only or leading route of a main drive. Bass is loud and sustained in most mixes (the live bass lane is
  pinned almost always, §2A), so a bass-led drive sits on the bass and cannot show the voice.
- **Measured on Waveform:** every preset's Pulse Strength (the bend drive) was bass-only. Routed mid-led (Bass gain
  1.0 -> .5, Mids gain 0 -> .8, both curve 1.3; commit d5623bdc), on eight recordings back to back: Pulse Strength vs
  the PCM vocal band +.50 -> +.66 (Don't You See, a vocal song with little bass, -.58 -> +.18; Rag Doll, bass-led,
  +.71 -> +.57), loudness tracking on Preset 1 +.45 -> +.48, Frozen Past born swell +.50 -> +.56. The cost: a kick
  inside sustained bass raises the swell 21% less (median .058 -> .046), and those kicks now reach Kick Accent (roll,
  twist, sparks, strands) instead.
- **Rejected on measurement:** a dedicated 2048-sample 30-150 Hz bass lane (it drowned the vocals: Human +.55 ->
  +.15); rebalancing the phrase-energy weights toward mids (+.03 only).
- **Method for every candidate routing:** score a vocal band taken from the recording's own PCM (the lead audit used
  300-3400 Hz energy over the newest 2048 samples of each feature frame's capture history, correlated in 1 s means
  over music seconds) beside the song's own music trace (`tools/visualizer_replay/waveform_music_response.py`, the
  waveform reaction trace tool: loudness tracking, saturation, dead and spurious shares), and kick-lock the swell rise
  on kicks inside sustained bass (PCM bass in the song's top third). Judge whole songs in continuous play on several
  recordings, including a vocal song with little bass and a bass-led one.
- **Author routing in the canonical routing matrix** (the Studio's response tuner, then Save To Preset), never as a
  hidden code lane: the change above is three routing values per curated preset, set through the Studio, nothing in
  code. Routing is preset content the operator owns and retunes.

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

The adaptive threshold and the slower local baseline answer only "did an event happen?" (a short local context, about
a second; §2B: the one legitimate adaptive threshold). Never size a reaction from that ratio or that jump alone: the
same kick just after a dense passage scores far lower (lead audit 7 Nov, synthetic: reward .22 against .61 at 50 ms
after the drop, equal after ~2 s). Size rewards on the fixed scale (`musical_emphasis`, `passage_ramp`).

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
-> normalization against a FIXED low/high placed on real music
-> response shaping
-> final bounded presentation value
```

Place `low`/`high` once from pooled percentiles over several full songs (§13A), never from a floor or peak observed in
the playing track (§2B).

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

**Everything ramps (operator 2026-10-03).** Every reactive element follows the music's weight with a fast rise and a
gentle fall, and each one ramps on its own: particle population and power, fragmentation power *and how often it
fires*, tracer speed, spin velocity, glow. Scaling only the size of a reward while its admission frequency stays
constant reads as "reacts to everything the same" (Sphere's 2026-10-03 log: ~2 packets per 0.5 s at every level).

The shared ramp is `transient_bus.passage_ramp(intensity, quiet)`: `quiet` for a quiet passage, 1 for a loud one,
on the FIXED real-music scale (`PassageIntensity`), convex. Multiply by an absolute near-silence gate
(`transient_bus.audible`) so near-silence earns nothing. Any lane that is
**self-relative** (the bus's `bass/mid/high_transient` is flux over its own adaptive threshold) needs this ramp at
its consumer: on its own, a kick in a quiet passage reads as large as one in a loud passage, and near-silence fires
hardest. DevCurve's transients layer was inverted this way (Human's quiet passages swung it twice as hard as its loud
ones) until it took the ramp (2026-10-04). Bubble reads the same lane but keeps its golden; do not gate it in the bus.

**Slow passage drive (DevCurve, operator 2026-10-04).** Travel speed, undulation speed and slope must follow the music
without ever lurching. DevCurve once kept one speed and slope whatever the music did: the undulation drifted on
the wall clock, and travel was capped at cruise ±10%, a guard against a historic energy throttle that swung it ~12×.
The pattern that works: ease passage intensity through two even stages of ~1.2 s (per frame it flickers 0..1 with
the beat; eased, it follows the passage a viewer hears, ~0.25 quietest / ~0.65 usual / ~0.95 loudest on real music;
two stages make every change an S-curve with no kink where it starts or ends), map it through those points to a 0..1
drive where 0.5 is the historical look, and scale travel (0.5–1.6×), phase speed and swing from it. Integrate phase
and position from rate × dt so a speed change never jumps the picture. A loud passage is then faster and steeper.
Nothing per-beat touches speed: a ±10% transient nudge on travel still made it breathe with the beat, and the
operator read it as fast/slow/fast/slow (2026-10-04). Classify passages by 2 s windows when measuring, not by single
frames.

**The pulse is height, and it settles gently (DevCurve, operator 2026-10-04).** Each layer's reaction rises with a
hit within ~45 ms and settles over ~0.65 s, timed in seconds. A per-frame blend (0.30) fell as fast as it rose
(~50 ms), so every beat pumped the swing 14–29% and the curves read fast/slow/fast/slow. Measured on the recordings,
the asymmetric envelope halves the beat-scale pumping and makes the steepest falls ~3× gentler, at ~15–25% more
mean swing (the height lingers between hits). Never convert a per-frame blend factor into "smoothing" without dt:
it changes with frame rate. (Superseded in part 2026-11-05: the heights now pass two cascaded stages — see
§13D "DevCurve" — because that envelope's input was pinned and its single fast attack jumped the velocity.)

### Slow sustained response

Whole-object fullness/growth should use a slower envelope of the current level on a fixed scale (never a learned
floor or peak: §2A). Sphere's sustained body weight is deliberately slow so a loud passage reads heavier without becoming a giant beat pulse.

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
- a new timer/poller/FFT/audio worker created because the mode wants a different response signal;
- normalising by `_raw_bass_avg` or any level that only adapts while Dynamic Floor is ON: with the floor OFF it
  is the manual-floor setting, so the lane pins at its ceiling (§13A);
- relying on Dynamic Floor for good reactions: it learns a level from the track and degrades as the song continues (§13A);
- any memory in a response path: a running mean, a remembered peak, a learn gate, a presence ratio used as a gain or
  gate, a per-block peak normaliser, contrast about a running mean (§2B);
- a main drive routed from bass alone, or a routing lane hidden in code instead of the canonical routing matrix (§2C).

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
3. preserve source headroom through a fixed-scale normalization with no memory (§2B), and route main drives vocals
   first (§2C);
4. choose attack/release/refractory times from the visual meaning, not from one global smoothing constant;
5. establish neutral, weak, medium, strong and maximum synthetic cases and assert monotonic ordering;
6. explicitly test **silence**, a quiet song, ordinary material, a hot chorus/dense passage, and isolated strong kick/vocal events over a loud bed;
7. inspect output occupancy/distribution, not only averages, including the **share of frames at each lane's ceiling** with the mode's floor OFF (§13A);
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

## 13A. Reacting well without Dynamic Floor (Extruded Bubble, 2026-10-24)

The operator's standard: a mode must react at least as well as accepted **2D Bubble with Dynamic Floor ON**
(*Parity+*: never worse; better where genuinely smooth and accurate) **with its own floor OFF**. Dynamic Floor
produces good reactions early in a song and then degrades as the song continues, so no mode may depend on it.
Extruded Bubble (EB) was brought to that standard by the method below; reuse the method, not EB's constants.

### What Dynamic Floor actually does (read the code before blaming the music)

`beat_engine.get_bubble_energy_bands()` shapes Bubble's body bands by dividing raw lanes (mid, high and part
of bass) by `worker._raw_bass_avg`. `bar_computation` updates that average **only while Dynamic Floor is ON**,
where it tracks the music: a level *learned from the track*, which is exactly why it drifts and degrades. With
the floor OFF it is reset to, and stays at, the **manual-floor setting** (`audio_worker.set_floor_config`). The
floor-OFF bands are then "raw level ÷ a configuration knob": at ordinary gain they sit on their soft ceilings.
Measured on native PCM of four full songs at EB's authored gain: band mid at ≥ 0.96 for **52–78%** of playing
frames, band bass at ≥ 0.76 for **30–73%**, while the raw lanes underneath had healthy contrast (raw bass
p10/p50/p90 ≈ 1.3/2.8/3.7). The floor "makes reactivity good" only because its learned average restores that
contrast. Do not copy that mechanism; it is the unreliable part.

### Rule: read raw lanes on a fixed real scale, per mode

- Give the mode its **own body feed** that reads the same raw lanes (`_last_raw_bass/_mid/_treble`, after the
  gate floor) against **fixed references**: EB uses `get_extruded_bubble_body_bands()` with references
  (bass, mid, treble) = (5.0, 3.0, 1.2), linear below 0.8 and an exponential approach to 1 above it, times the
  play ramp. Pick references from pooled raw percentiles over several full songs so about **p90 maps near
  0.75** and loud crests keep soft headroom (§4). No learned level, no dependence on the floor mode or the
  manual floor. Sensitivity acts *after* the raw lanes (gate floor/expansion), so it does not move them; input
  gain scales the PCM before the FFT and does.
- **Fixed references need a fixed FFT length.** Raw lanes are ~`log1p(|FFT|)^1.2` of an unnormalised `rfft`,
  and `|FFT|` grows with block length, so a longer block adds an *offset*, not a factor: at 512 samples the same
  music sat ~30% higher with less contrast and pinned EB again (large range 0.24–0.58 on three songs; 256 gave
  0.73–0.84). A per-block multiplier cannot restore contrast. EB records the FFT bin count
  (`_last_raw_fft_bins`), undoes the compression, rescales the magnitude to the 256-sample reference with
  per-lane exponents (bass 1.0 ~tonal, mid 0.9, treble 0.6 ~noise-like; fitted at 128/441/512/1024 on four
  songs), and re-compresses. Auto blocks are covered because the bin count is the actual FFT. Residual: band
  splits move with block length (128/1024 ~15–20%, 441/512 ~5–10%). Measure every mode at each block size a
  preset uses.
- Do **not** change a shared feed that an accepted mode depends on (accepted 2D presets run floor OFF on
  `get_bubble_energy_bands`); add the mode-owned getter beside it. Replay engines must serve the new getter too
  (`ReplayBeatEngine` returns the recorded shared feed in ordinary replay; PCM reanalysis runs production).
- **Unpinning the input changes every downstream consumer.** EB's population, stream speed, drift, emission
  and rays read the same bands; with pinned input they sat near their loud ends (bubble count 47–52 throughout
  a song). After the fix they follow passages (count median 34, speed p10 1.03 → 0.22). Expect it, measure it,
  and report the visible density change instead of discovering it later.

### Shape the sustained (large/body) lane after unpinning

- A linear held term (`k × body`) compresses phrase contrast. Accepted 2D uses a **knee** (sustained support is
  zero below it). EB's held body is `soft_top(smooth_above(body_sum, knee=0.55, softness=0.08) / span=0.52)`:
  knee ≈ pooled **p25** and knee + span ≈ pooled **p95** of `bass + .28 mid + .10 high`. A p10 knee held large
  bubbles open through nearly all music (p95/p05 ~1.8×); a p40 knee collapsed a quieter-captured song (median
  0.57 vs 2D 1.58). With fixed anchors, quieter captures honestly breathe smaller — choose the knee so they
  still breathe.
- **Gate the change term by the held level** (`change × (0.15 + 0.85 × held)`): otherwise every kick in a soft
  passage refills the envelope and p05 stays near mid-size. Full passages then crest further.
- Apply the knee to the **unsquashed** sum. EB's old `soft_top(sum)` already compressed the upper half of all
  samples into 0.8–1.0, so a knee on top of it bought almost nothing (measured).
- Use a **smooth** knee (softplus) anchored to **exactly 0 at silence**, so steady quiet music sits a little
  above silence (synthetic "moderate" no longer equals silence) and silence still returns to the authored rest
  exactly. A small linear base instead raised every level and cost ~15% of breathing range (measured).
- Timing follows the passage role (operator: large = phrase body; small/flow/rays = changes inside loud
  passages). EB large: release ~**0.30 s** in music (2D's large decay 2.85–3.85/s; 0.10 s produced beat-rate
  wobble near the top), attack **0.12 s** (inside 2D's 0.09–0.125 s; 0.06 s followed per-frame band noise),
  change-term weight 3.0 *with* the held-level gate (2.2 ungated; 3.0 ungated pumped). Small keeps its faster
  release.
- **Cap at the authored maximum.** Per-identity amplitudes above 1 must not pass the loud handle: EB eases the
  excursion with `soft_top` toward the class maximum (Breathing's loud handle), never a hard clip.
- Measured and rejected: an even ease of the held body (τ 0.4 s) lowered range and did **not** reduce swings —
  the swings came from the change term and the attack, not the held term. Measure before keeping a smoother.

### Per-identity response (granularity)

A single class envelope makes every bubble breathe in lockstep. Accepted 2D varies sensitivity and timing by each
bubble's own size. EB now scales each identity's **excursion above the authored rest** by its normalized size
within its class (large 1.12 → 0.88, small 1.18 → 0.82) and its display-follower time constants by
0.75–1.25. Never move the **rest** itself: idle/rest tests caught the first attempt, which scaled the deviation
from 1.0 and changed resting shells.

### How to measure Parity+ (all tools are sidecars; production never imports them)

```powershell
# Floor-ON 2D reference vs the mode's own floor-OFF feed, both recomputed from recorded PCM:
.\.venv\Scripts\python.exe -m tools.visualizer_replay.bubble_response_comparison --clip logs/visualizer_recordings/<song>.jsonl --output <new dir> --duration 60 --window 0,60 --reanalyze-pcm --set bubble.bubble_dynamic_floor=true
.\.venv\Scripts\python.exe -m tools.visualizer_replay.bubble_breathing_continuity <dir> --report <dir>/continuity.json
.\.venv\Scripts\python.exe -m tools.visualizer_replay.bubble_breathing_overlay <dir> --window 10,20 --output <dir>/overlay.png
```

- Use **≥ 4 full songs** with native PCM (soft acoustic, quiet→loud, heavy, mixed); one song overfits.
  Schema-1 short clips without capture history cannot be reanalysed.
- Plain replay feeds recorded *post-DSP* bands, so floor/Sensitivity changes cannot show; `--reanalyze-pcm`
  recomputes body DSP from the recorded PCM (hybrid: recorded onsets/cadence). Check the per-mode input
  actually differs (`actual_body_input_mismatch_count`).
- Read several metrics together: per-segment `range` ((max−min)/median), `swings_per_s` (prominent turns;
  beat pumping vs phrase breathing), `reversals`/`top_reversals` (judder, especially at maximum), `flat`
  (sitting between states). `range` divides by the median, so lifting the median shrinks it even when the
  absolute swing is unchanged — also compare **absolute p05/median/p95** of radius/nominal.
- Plot curves before trusting medians: the first EB overlay showed the *input* was pinned, which no
  simulation metric revealed. Then render native pixels (`extruded_bubble_forensics --capture --reanalyze-pcm`)
  for the same window before and after.
- Compare against the previous revision from a temporary `git worktree` with the current sidecar tools copied in.
- Tests should state Parity as a **relative** oracle (mode vs 2D on the same clip and window, e.g.
  `test_active_recorded_phrase_breathes_at_least_like_accepted_2d_in_each_class`), with a negative control on
  the old code. An absolute threshold tuned on a non-production feed (EB's old `> 1.8`) exceeded what accepted
  2D itself reaches (1.22) and only passed against the pinned feed.

- **The quiet handle sets the floor of contraction.** Breathing's quiet handle 0.05 puts large rest at 0.71 of
  nominal, so no envelope change can contract further; measure presets at their own handles and report it.

State (2026-10-24, after block normalisation and the knee/gate change): at block 512 large p95/p05 is
2.5–4.6× (2D 2.6–9×), range 0.62–1.93 vs 2D 0.73–1.01, top reversals 0. anything_mixed2 stays below 2D range
(0.62 vs 0.88) because its median sits high. Evidence: `Docs/Reference/Extruded_Bubble/Investigation.md` §65–66.

---

## 13B. General lessons for any new visualizer (Extruded Bubble loop, 2026-10-24)

These held across EB's input, breathing, flow, collision and drift work. Each cost real time when missed.

**Input**
- **Check every derived driver for saturation, not only the input bands.** EB's input was fixed and its large
  bubbles breathed, yet stream speed still sat at its loud handle: `soft_top(0.6 level + 0.6 small + …)` adds two
  terms that are each ~0.5–0.7 in ordinary music. For every driver that feeds an authored Range, print p05/p50/p95
  over several songs *as a fraction of that Range*; anything living in the top 15% is pinned.
- **Fixed anchors need a fixed analysis geometry.** Raw FFT lanes change with block size (offset in the log
  domain), so references measured at one block re-pin at another. Record what the analysis actually used (EB:
  `_last_raw_fft_bins`, which also covers Auto) and normalise to the reference geometry. Measure presets at the
  block size they ship with, not the one you calibrated on.
- **Know which controls act before your lanes.** Input gain scales PCM before the FFT; Sensitivity and the floor act
  after the raw lanes. A docstring claiming otherwise survived one round — read the code path.
- **Check the recording before judging section response.** The bundled recordings are 60 s each; per-window PCM RMS
  shows how much contrast a clip actually holds (ragdoll's capture varies ~±2.5 dB, so its loud end is not in it).
  Long-form section changes need a full-song capture or native observation.

**Response shape**
- **One passage signal, many consumers.** EB's large breathing and its flow now both read one held passage level
  (fixed-scale knee). Deriving each consumer's "loudness" separately is how one stays pinned while another moves.
- **A knee belongs at a real musical level, chosen across songs.** Too low holds the effect open through all music;
  too high collapses quieter masters. Pick it from pooled percentiles (EB: ~p25) and check the quietest capture.
- **Gate transient pumps by the passage level.** An ungated change/onset term refills a sustained envelope on every
  kick in a soft passage, so soft passages never contract.
- **The authored loud handle is the maximum.** Onset lifts, sustain lifts and per-identity amplitudes go *inside* a
  soft top toward the handle, never added after it. Users clamp behaviour with that handle; respect it.
- **The quiet handle sets how far things can contract.** Report preset results at their own handles; a raised rest
  caps contraction no matter how good the envelope is.

**Physics on kinematic motion**
- **Kinematic motion has no momentum, so collisions need their own separation velocity.** A positional nudge slower
  than flow/breathing growth leaves pairs grinding ("rubbing"). Give the pair a decaying separating velocity along the
  normal plus a fast overlap correction, and apply it to fused groups as bodies.
- **Anything still visible still occupies space.** EB removed popping bubbles from collisions while they faded for
  2.4 s, so survivors slid through them. Fading/retiring objects stay obstacles (separation only, no new events).
- **Measure interpenetration by cause.** A per-frame census (pairs overlapping > 25% of the smaller radius, labelled
  bounce/pop-fade/not-admitted/leaving, plus episodes > 0.3 s) found both causes at once; screenshots did not.
- **Measure a reported cohort effect before fixing it.** "Old bubbles stay slow" measured equal for young and old
  identities on current source; the cause had been the pinned input upstream.

**Controls in 3D**
- **Translate 2D controls into the 3D frame, not literally.** EB's Drift Direction works in the stream's own frame
  (across/depth), so 2D's horizontal/vertical swish became Across/Depth, and spirals orbit the stream axis and widen,
  so births at the source spiral out. Keep the existing behaviour as the default choice so presets do not change.

**Tests**
- **An absolute threshold can encode the bug.** EB's startup test demanded a > 1.8 peak ratio (the higher held level
  made the same swell 1.66); the bounce test demanded < 0.01 units per step (the slow nudge that rubbed). State the
  intent relatively — step vs play ramp, < 10% of the overlap per step — and run the old code as a negative control.
- **Test behaviour with test-owned inputs**, never preset values: synthetic signals through the production FFT
  (`fft_to_bars`) for block invariance; test-owned ranges for "inside the authored range".

## 13C. Passage-driven Ranges and beat motion (Extruded Bubble, 2026-10-25)

- **Ranges ramp on the passage, beats swing them.** Band-driven drivers sit mid-range in nearly all music, and
  additive beat terms floor every passage there: EB's quiet and loud passages landed close together on every
  Range. The engine's eased passage intensity places each Range (`passage x (base + beats)`); beats modulate it
  multiplicatively, never as an added floor. Seed the passage follower on the first fill (activation can join music
  already playing).
- **A passage follower smooths beats away; beat motion needs its own path.** Speed and drift spanned ~2x across
  passages but moved 2-4% with the beats. A separate surge (onsets that stand out from the recent ones, eased in
  over ~0.1 s, released over ~0.3 s) pushes toward the loud handle; leave headroom under the handle for it.
- **Music sends ~10 onsets a second.** A response to every onset with a half-second release is a constant offset,
  not pulses: respond to accents (weight above the recent mean). **Superseded 7 Nov for sizing (§2B):** standing
  out from the recent onsets may ADMIT an accent; its size is read on the fixed scale, never from its weight above
  the recent mean (per-kind running-mean contrast muted mid-song kicks, §13D).
- **Rank quiet/loud by the passage, not the instantaneous value** (it snaps to 0 between beats, so its "quietest
  fifth" is beat gaps inside loud music).
- **Handles that cannot cross must hold one ordered quantity.** A rest depth and a crest on one Range forced the
  crest to its maximum whenever the rest was deepest.

## 13D. Motion, reach, texture and cost lessons (Waveform Ribbon, 2026-11-05)

Mode-neutral lessons from making Waveform Ribbon's reaction and look acceptable. The Waveform-specific mechanism,
constants and gates are in `Docs/Reference/Waveform_Ribbon_Migration_Plan.md` → Current reaction model; the owner is
`core/waveform_ribbon_dynamics.py`.

**Judge motion in time, not in stills**
- **Capture at a rate that divides the logical clock** (for example 45 fps on a 90 Hz logical clock) so every frame is
  the same number of ticks apart; a non-dividing rate adds aliasing judder that is not in the product. Review
  consecutive frames and time strips (`tools/visualizer_replay/capture_time_strip.py`), plus space-time maps of the
  reacting quantity along the object. Stills hid every defect below.
- **Probe per logical tick, on the same material points:** second differences (acceleration) and their change (jerk)
  of identical cloth points, split into bands along the object (centre, edges), under strong synthetic beats with the
  production constants. Exclude ring/history slots that were reused for a new point between ticks, or the probe
  measures recycling instead of motion. Run the old code as a negative control: the probe must fail on it.

**No twitch**
- **Geometry drives pass through two cascaded followers** (each with a minimum attack), so velocity is continuous. A
  single fast first-order attack makes position continuous but velocity jump on every transient. Light, colour and
  sparkle may keep a fast attack: a flash of light is not a twitch of the body.
- **Spread impulses over a short window** (same momentum, normalised peak) instead of one-tick velocity kicks.
- **A bound that lets go must relax at a limited rate.** A constraint may tighten at once, but when it releases (a
  share, a compression limit, a clamp) the whole field otherwise jumps in one tick. Rate-limit the release.
- **Fixed-length tapers, not drift- or data-sized ones.** An end taper sized by the current drift or head spacing
  jitters the edge every time that size changes.
- **Rim/hit light swells like the body** (quick rise, gentle settle); a raw hit decay was the strongest beat-rate
  flicker even though the geometry was smooth.
- **Whole-body size follows the passage, beats belong to the travelling feature.** When height/width/lift pump on
  every beat, the whole view pulses in unison and drowns the local reaction.

**Energy moves with the shape; it does not invent bumps**
- **Swell the object's own features.** Multiply the existing displacement by a positive gain envelope instead of
  adding a new wave: an added wavelet or height field brings its own crests and troughs, i.e. motion against the
  shape.
- **Flow rule:** for `y = c(x)·g(x)`, bound the envelope's slope and curvature relative to the carrier's own
  wavenumber (and make the envelope span at least a carrier wavelength) so a swell can deepen curvature but never
  reverse it, add an inflection or dent a curve inward. Size the envelope from the carrier (flow speed, wave rate),
  never from a constant.
- **Move material along the curve, never across it.** A sideways/axial scaling about the centre read as horizontal
  bursts; sliding points along their own curve (exact resampling of the unswollen body, bounded compression, rate
  limited) carries the energy without changing the curve. Horizontal position otherwise moves only with the steady
  flow.
- **Born outside the view, but just outside it, and fading only once seen.** Inject travelling energy just beyond the
  visible edge so it slides in already formed (energy born inside the view pops into existence), and measure that edge
  from the camera the card really uses: Waveform assumed +-30 and launched at 44, while the card shows +-16 (+-5 at the
  canonical size), so a Head To Tail swell arrived ~2 s late with 5% of its strength (in-view swell p50 .13 against
  Centre Out's 1.39). The capture now passes the camera's visible span as configuration; edge swells are born a few
  envelope widths beyond it and their fade starts at the edge, as a Centre Out swell's starts at its birth (p50 .99).
  A visible swell lifts the pre-kick baseline, so judge kicks by their peak as well as their rise.
- **A shared light reference is per unit of energy, not per mode.** Pulse Rim's reference had been set on swells that
  each carry half the injection (Centre Out splits it); a full-strength edge swell then sat at the ceiling over 43% of
  the view. Normalise what is published to the energy one swell carries, and check the share of rim pixels at 255 and
  the response's swell-to-elsewhere contrast per preset, not only the peak. Size every view-dependent quantity (birth,
  floor lift, its lookahead) from the same visible span, in units of the mode's own envelope.
- **Clear an obstacle with placement, never by shrinking the reaction.** When swells reached the view at strength,
  their troughs hit the floor; bounding the swell's gain kept them clear but cut peak kicks by up to a third. Raising
  the whole-object lift's limit cleared the same troughs with kicks identical per kick (the lift is a pure offset).
  Classify residual contact by cause (limit reached vs follower still easing) before changing the follower.
  **Measure every edge the placement moves toward:** that higher limit pushed crests out of the card's top (lead review
  6 Nov: clipped frames 9% -> 66%), which no floor measure showed. A whole-frame "bright pixels in the top rows" count
  also counts sparks drifting up; separate crest clipping (a wide bright run) from spark density before tuning the
  ribbon against it.
  **Superseded 7 Nov: floor first, the top takes back a bounded share.** The 6 Nov rule (top edge first, floor second:
  keep the limit the top allows, accept brief floor contact) left the visible lower edge through the floor on 7-72% of
  music ticks, and the operator ranks that worse: "We'd rather it goes a bit higher when it has to than clips." The
  rule now: the lift may rise as far as the floor needs (Waveform: `TROUGH_LIFT_MAX` 3), and the card's real top edge
  may take back at most a fixed share of that lift (`TOP_GIVE_BACK` 1.5), chosen by sweeping it on recorded continuous
  play at the smallest card you support while measuring **both** edges per preset (floor contact, and crests above the
  top in the model and on rendered frames). When a preset's body is taller than the card holds, no placement fixes
  both edges: report it as authoring, never shrink the reaction to fit. A floor meant to yield (Waveform's Floor Give)
  keeps its former limit.
- **Keep the travelling feature legible.** Geometry and look should follow the *fresh* energy (a short-fade copy of
  the field), or overlapping old energy piles into a uniform inflation or a glow parked at the emitter. Check the
  feature's median/max over the visible span on dense real music, and that successive beats stay separate bands.
- **Selectable reaction styles must be measurably distinct.** Review each style on long strips; a variant that looks
  the same as another is machinery without a gain. Every style still obeys the flow rule and the no-twitch probes.
- **A fix to one style is a check on every style.** The fresh-field fix reached Travelling Pulse only; Group Wave kept
  building its wide set envelope from the long-fade field with a peak-keeping blur (x7.4 on Preset 7), so on dense
  music its swell sat at the soft bound over two thirds of the view (median/max .98). The whole body then inflated at
  once with the strength drive: no decay in soft passages, flat sustained passages, and a full-size swell whenever that
  drive's band rose (Preset 7 on Rag Doll, 5 Nov). For every style, measure on recorded continuous play: median/max of the swell over the
  visible span, the share of it at the soft bound, and its rise and fall within 3 s windows.
- **A pulse is a band, and a freeze holds everything that moves.** (Waveform, operator 7 Nov: "The pulse is a
  relatively small horizontal width and the full vertical width"; Frozen Past: "each part stays frozen until the pulse
  reaches it, then it moves to match the current values low or high and freezes again when the pulse leaves.") A
  travelling field that sums every hit covers the whole view on dense music, so "where the pulse is" means everywhere:
  launch discrete bands on onsets (spaced at least two widths apart, later energy strengthening the newest), combine
  them by maximum (never summed), cap how many are in view (Pulse Count 1-3; a Centre Out pair is one) and gate a
  freeze on each band's window (a full core and a Pulse Falloff at each side). A frozen region must hold every quantity that moves it, not just the body drives: the
  swell, the final bounded gain (one shared bound rescales every held swell), vertical offsets (a whole-ribbon lift
  moves frozen cloth), the surge displacement (a scene-fixed drift field moves cloth flowing through it, and so does
  scaling it by a live strength), shape springs, roll and twist phase, idle motion and the clock. Hold it on cells
  FIXED TO THE CLOTH: re-interpolating held state onto a scene grid every tick is numerical diffusion, and the held
  shape slowly melts. Never low-pass the shown held state with a wide kernel either: it carries each band's update into
  the gaps; soften the band's own edges instead. Prove it on a space-time map of each cloth point's vertical motion
  (cloth coordinate keyed on the history's absolute coordinate, never the packet-relative one that re-bases) on a REAL
  preset (a synthetic test with narrow bands and wide gaps passed while Preset 5's 6-unit bands moved everywhere) and on
  rendered frames: motion outside the bands must be noise (Frozen Past, 7 Nov night: median .002 vs .46 world units/s).
- **Measure over what the camera actually shows.** The visible span is the production aperture times the authored
  lens (Waveform: about +-14 scene units at the capture aperture, not the lens' +-4 nor the +-30 the constants assume).
  Metrics over a wider span hide a pinned field; metrics over a narrower one miss swells arriving from the edge.

**The full reaction range**
- **Measure drive distributions, not one song:** p05/p50/p95 and time above 0.9 of every geometry drive, as a
  fraction of its authored Range, on several real recordings including sustained loud and soft passages. A drive
  that never leaves the middle of its Range wastes the authoring.
- **Superseded 6 Nov: no adaptive response gain.** Dividing a geometry drive by a remembered recent peak is the
  "slowly falling peak" §2A rejects: on recorded music with a spliced 5 s break it sized the following 10 s 5-9% up,
  and it re-normalises a long quieter passage. Map the routed target with a FIXED function on the real-music scale and
  let each target's Range be the authored reactivity. Calibrate it to what the replaced path VISIBLY did, not hotter:
  fit gain x target^curve to the paired output/target quantiles on long recordings played back to back, ease the top
  toward where it landed sustained loud passages (Waveform: .92). **Superseded 7 Nov:** the phrase-scale swings were
  then "restored" by widening each drive about a learned 3 s mean of itself, behind a learn-rate gate that collapsed
  at every presence dip (below .5 on 39% of music ticks): the same soft->loud step drew x1.0 to x3.4 depending on that
  gate, and a loud passage started big and shrank as the mean caught up. Removed; swings come from a release that lets
  go (below) and fixed placement, never from a mean. A hotter curve (lead review
  6 Nov) pinned Pulse Strength (3 s contrast -34..-39%), flattened passages and pushed crests out of the card; a drive
  parked in the easing knee loses contrast even when it never pins, so check each drive's own 3 s contrast, not only the
  visible size. Gate the result per preset against main: visible size p10/p50/p90, 3 s contrast, time near the top,
  kicks per time bin, the card's top edge. Waveform's remembered-peak path and its opt-in Adaptive Response control
  were retired 7 Nov (`visualizer_retired_modes`); add no adaptive path (§2B).
- **A break is a test of every running reference.** Splice 2-5 s of near-silence into recorded music (scale the PCM,
  re-analyse it through the production chain) and compare what follows against the unbroken clip per layer: engine
  adaptive sensitivity (Waveform's raw lanes and bus loudness are before it: no effect), the bus (its passage level
  climbs back over about a second), the response gain, Breathing. A memoryless response passes trivially once its
  followers settle; anything that still differs is a running reference to remove.
- **A sustained kick with no geometry headroom still needs a sense.** When the drive that sizes the swell sits near the
  top of its Range, send the share of the kick the geometry cannot show to channels that do not fight the shape (an
  eased roll-speed impulse, spark births on the swell), on the fixed reward scale, never a clamped confidence. Bound
  any continuous channel per kick against its own base (Waveform: at most 15% of the roll's speed): unbounded, dense
  kicks overlapped into a sustained ~2x spin. Measure the mean and the acceleration tail in loud songs, not one kick.
- **Historical (the opt-in Adaptive Response this applied to was retired 7 Nov; there is no gain memory to hold, §2B).**
  Kept as the record of why holding a memory does not rescue an adaptive gain. It held the gain's memory through a
  quieter PASSAGE, never through beat gaps. A 30 s relaxation re-normalises a
  quieter passage back up to loud reach within one verse (a passage at 70% of the loud input reached Pulse Strength .88
  against the loud passage's .87 after 25 s): "it swelled up to full power when the song went quieter". Keying a
  longer memory to the drive being below its peak is wrong: a drive sits below its peak between almost every pair of
  beats, so that held ALL music (a global retune; Preset 1's late kicks fell .58 -> .45). Key it to a slow level that
  never dips between beats (Waveform: the published passage held over seconds, against the loud level the peaks were
  set at; held only below .8 of it, fully at .7). On five recorded songs back to back it engaged on 15% of music ticks,
  sustained-loud kicks stayed identical to no hold at every time in song, and quieter-section kicks moved 1-4%. The 60 s
  clips hold little long-form contrast (the memory sat near its floor on them): prove the benefit with a long synthetic
  quieter passage after loud phrases, with a negative control, and the no-mute side on the recorded clips. Also keep
  the gain itself honest: with it off (fixed calibrated targets) every kick on the same clips was 30-50% smaller.
- **Judge reactivity in continuous play, not in a song's first seconds.** Replay whole songs back to back without a
  reset and tabulate each onset's response by time in song and by passage. Two stacked adaptations (an onset already
  measured against an adaptive threshold, then judged again against a running mean of its own kind) muted every
  routine kick of a sustained passage while the start of each song looked fine.
- **Soft passages must breathe.** A cascaded release adds up: Waveform's passage, phrase energy, bus intensity and
  two drive stages each released over .65-1.5 s, so a dip shorter than ~3 s never showed and the next loud moment had
  nothing to rise from (7 Nov lead audit). Measure the music's own steps (PCM RMS changes of 3 dB or more) against the
  drive's change over the next 1.5 s, and shorten the cascade so the visible release is about the authored Decay
  (§13A: Extruded Bubble's large body releases over ~0.3 s in music). Never widen swings about a running mean.
- **History ends move continuously.** Anything anchored to the oldest/newest stored sample (a continuation, an end
  taper) steps at every admission; anchor it at a point that advances with the admission phase on a smooth curve.

**DevCurve (2026-11-05, the same lessons applied).** Operator: "its smoothness is great but it has almost no
reactivity". Measured (`tools/visualizer_replay/devcurve_reactivity_audit.py`, three 60 s recordings, presets 1 and
6): the layer drives read the shared pre-AGC *control* lanes, which divide each band by a fast-adapting norm of the
loudest band — a band **share**, not a level — so bass/mids sat above 0.9 of their Range on 95–98% of playing
ticks (bass input p05 = p50 = p95 = 1.0 on two songs), beat modulation of the displacement was 2–5%, quiet and loud
windows differed by ≤ 1.4×, and the smoothness slope limiter held the bass curve on 72–98% of ticks. Fix, owner
`widgets/spotify_visualizer/devcurve_runtime.py`: each layer's level = its share × the bus loudness (fixed real
scale); the height is a slow **body** plus fast **accents**: only the body (two slow stages) is divided by the
remembered peak (floor in loudness units, landing at 1.0 of the drive; **a learned level that breaks §2B**: on the
plan to remove, 7 Nov), while accents — the body layers' flux lane above its
own recent mean, the transients layer's flux spike above its body, captured and held 0.06 s — are read on fixed
scales into the reserved room above it, then eased by two stages of (0.025, 0.15) s (each second stage follows its
first as it stood at the start of the tick, so a hit's first tick never jumps the velocity). A first cut normalised
the whole height, beats included: a sustained-chorus kick then lifted the visible reaction by ~2% of its level;
**normalise the passage, never the beats**, and measure kicks in continuous play (`devcurve_continuous_kicks.py`;
same recording twice, so identical kicks compare early vs late). A per-layer travelling swell born just beyond the
right edge, travelling left with the material and multiplying the layer's own undulation under the flow rule
(closed-form share, rate-limited relaxation). Lesson: **a self-normalised lane (band over the loudest band) is a
ratio, never a level**; and **check the geometric ceiling** (slope limiter, clamps) as you would a drive's Range — a
reaction that lands where the geometry is already limited is invisible.

*Kick headroom and loud size (lead reviews, 6 Nov).* (1) **Kick-lock the measurement:** average the traces around
every kick first and take the peak of the mean; a per-kick "max after minus mean before" is positive on any noisy
trace, kick or not (`locked_*` in the tool). (2) **Check that an accent source rises on the kick, per passage.** In
loud passages the body layers' "fast level above the body" *fell* on kicks (+0.38 → −0.32 loudness units within
150 ms: the bus loudness dips after onsets) and its noise held the accent half-saturated, so loud kicks ride the flux
lanes; in quiet passages the flux lanes are passage-ramped to ~20%, and the band **share**'s rise is the kick (bass
0.67 → 1.0 kick-locked), so quiet passages take the eased share rise, weighted by quietness, on its own linear path
(through the flux accent's saturating response it never matched pre-work main). (3) **Keep the reserved headroom
through the geometry, and keep the loud body big.** Capping body + accent together let the steady accent fill the cap
(kicks invisible); a hard half-share for the body halved the loud look ("far less alive"). The body now owns 0.85 of
the drawn ceiling (soft knee), the accent stays **linear** in its share, only overflow eases past the ceiling, the
swell multiplies the body inside the body's share (never the accent, or a full passage's swell pushes kicks into the
overflow), and troughs ease into a soft floor. (4) **Size is the slope budget, triangles are the limiter.** A big
smooth wave needs a gentle carrier: a body the mixed carrier cannot draw blends it slowly toward its broad 1.35-cycle
component, and the ceiling subtracts the slope the contour and the idle wave already use. A smooth wave reaches ~0.8 of
a slope-limited triangle's RMS at the same slope, so the strongest preset (Deep Blue bass) stays ~18% below the old
triangle peaks while others are within ~10%; time at the limiter goes from 76–100% to ~0. (5) **Separate onset from
muting in continuous play:** a kick's swell share drops in the first ~5 s of a passage while the swell fills, then
stays flat to 55 s; gate per layer "settled vs late", not only "first seconds vs late". (6) **Vectorise before
tuning:** the curve build vectorised byte-identically (16.8 M samples) took the tick from +25% over pre-work main to
below it, which paid for the new reactivity. Evidence: `.artifacts/evidence/visualizers/devcurve/reactivity/20261105_reactivity/`
(`continuous_v5/`, `strips_v3/`, `tick_cost_v2.jsonl`); gates `tests/test_devcurve_reactivity.py`,
`tests/test_devcurve_continuous_play.py`, `tests/test_devcurve_kick_headroom.py`.

*Replay floors (6 Nov).* The synthetic replay floors' `output_flux` for DevCurve fell to 15-31% of the pre-rework value
(five cases) when the rework merged. Measured (`.artifacts/evidence/visualizers/devcurve/floors/20261106_floors/`), it is the **cold start of the slow
body**, not lost motion: the shipped fixtures last 0.5-2 s and carry a constant schema-1 loudness, while the body's two
stages (0.45 s, 0.8 s) take ~3 s to settle, so a 1 s clip sees a quarter of the settled motion. Held to 8 s the same
inputs settle at 62-95% of the pre-rework flux and ~75% of its bass amplitude (the smooth wave against the slope-limited
triangle, above), and on four recordings (150 s each) flux is 89-104% of the pre-rework value, the quiet-to-loud
contrast is kept or larger (growingpains 2.0x -> 2.5x) and the kick-locked rise of the field is 2-9x the old one. A real
loudness step still lifts the field within ~1.5 s. Only DevCurve's entries of `reactivity_floor.json` were recalibrated
(`floors.calibrate`); `test_devcurve_held_input_keeps_moving_the_field_after_its_slow_body_settles` (with its frozen-field
control) guards the settled response the 1 s floors cannot see. Lesson: **a floor measured on a clip shorter than the
mode's slowest stage guards its cold start only; add a held-input check when a mode gets a slow body.**

**Collisions with the world**
- **Preserve the shape: lift the whole object.** Per-point clamps against a floor produce boxy, flat-bottomed troughs;
  proportional trough scaling still changes the curve. A whole-object offset, sized from the visible part only and
  eased in two cascaded stages (quick up, slow down), keeps the shape exact and the motion velocity-continuous.

**Texture and colour**
- **Detail lives in the object's own coordinates.** A lattice or weave defined in the sheet's own (warped) coordinates
  travels and twists with it; fade it to an even glow when cells go sub-pixel (no crawl or moiré), and combine line
  crossings so nodes never form white knots.
- **A swell deepens saturation, not whiteness.** Raise saturation toward full with hue and value unchanged and let
  colour carry the swell; additive light boosts wash crossings white. Never invent a hue on neutral colours.
- **Smeared colour beats crisp streaks.** Reflection taps weighted by a steep luminance power make the winning tap
  jump as objects move (column popping). Use gentler weights over overlapping taps, keep the hue, and ease reflected
  light toward a ceiling so a bright source cannot flood the ground with one colour.
- **Dark wet ground, bounded medium.** A grey floor came from the far surface level, not the reflections; surface light falls
  off from the lit objects toward a dark far level, so wide views still read as dark wet ground. Atmosphere takes a saturating, capped share of the objects' light and hue
  over its own tone, so strong local light cannot wash the frame. Check consecutive frames for flicker after any
  floor or medium change.
- **Particles:** at least a one-pixel core, a soft halo in the emitter's colour, fade in and out (never vanish);
  swell-carried births fill only the headroom the authored count leaves.

**Cost without changing a byte**
- **Vectorise per-object loops as rows** and prove the result byte-identical (values and dtypes) on every call of
  real-music replays across presets and modes before keeping it. Python scalars become columns in exactly the dtype
  NumPy would have cast them to; helpers that replace library calls reproduce their arithmetic, branches included.
- **Closed forms over iterative searches.** When the bounded quantity is linear in the parameter being searched
  (here an envelope `1 + share·swell`), the admissible maximum is a per-point closed form; pin it with a test against
  a fine search of the bound itself.
- Report paired timings on the same machine and conditions; never trade reaction strength for cost.

## 14. Evidence / negative-control map

Read these for the cases behind this guide rather than copying their old implementation literally:

- `Docs/Guardrails/Bubble_Temporal_Fidelity.md` — behavioral shape + temporal fidelity; loud-passage variation; cadence/delivery negative controls.
- `Docs/Historical_Bugs.md` **U-02 Bubble / Blob Signal-Contract Trap** — dead smoothed/post-AGC hold vs raw-energy blowout, stale-event replay, hot-chorus hard-ceiling failure.
- `Docs/Historical_Bugs/Sphere_2026-09-10_Acoustic_Admission_And_Cohort_Motion_Investigation.md` — consolidated acoustic intake and detached-cohort mistakes: playing state, loudness, saturated event confidence, and one global decay are **not** interchangeable admission/population/velocity authorities.
- R-69 / Bubble viewport evidence — viewport adaptation may not globally damp authored reaction.
- R-76 / tall Spectrum evidence — physical-pixel flicker caused by delivery/temporal scaling must not be “fixed” by reducing response.
- `Docs/Reference/Extruded_Bubble/Investigation.md` §65 — floor-independent fixed-scale body feed, sustained-lane knee/timing and per-identity breathing measured against 2D with Dynamic Floor ON (§13A).
- `Docs/Reference/Waveform_Ribbon_Migration_Plan.md` → Current reaction model and `Docs/Audits/Waveform_Studio_and_Reactivity_Audit_2026-11-05.md` — travelling pulse, flow rule, adaptive gain, floor lift and no-twitch evidence (§13D); negative-control tests `tests/test_waveform_no_twitch.py`, `tests/test_waveform_reaction_modes.py`, `tests/test_waveform_trough_clearance.py`.
- `.artifacts/evidence/visualizers/waveform_ribbon/memoryless_reactivity/` (`20261107_lead/README.md`, `20261107_bands/`) and `Current_Plan.md` §1 item 2 — the adaptive stages removed and what replaced them (§2B), pulse bands and the cloth-fixed freeze (§13D), and the vocals-first routing (§2C, commit d5623bdc); tests `tests/test_waveform_memoryless_response.py`, `tests/test_waveform_fixed_response_and_kick_accent.py`, `tests/test_waveform_pulse_count_and_falloff.py`.

Historical files are evidence and negative controls. Current source + `Spec.md` + current guardrails remain implementation authority.

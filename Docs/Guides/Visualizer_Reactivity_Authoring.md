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
| **Live pre-AGC band energy** | current acoustic presence, silence gating, sustained passage weight, slow adaptive floor/peak, local positive-jump evidence | absolute event magnitude, particle count, or any response whose full range would become normal in loud passages |
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
  consistently. `musical_weight` still gates near-silence (absolute) and a passage far quieter than the last few
  seconds (presence against the 6 s running level, which saturates at 0.8 so a sustained chorus is never gated). This
  is the one definition; Shockwave Grid, Voxel Sphere and DevCurve use it.
- **A clamp is not a normaliser.** The 2.5 clamp on the live lane is a safety bound; ordinary music saturates it, so
  no contrast survives there.
- **Silence must not teach a running level.** A running reference that decays through a pause makes the music's
  return look tens of times louder than usual (presence 46 was measured); the bus holds its level through
  near-silence.

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

**Everything ramps (operator 2026-10-03).** Every reactive element follows the music's weight with a fast rise and a
gentle fall, and each one ramps on its own: particle population and power, fragmentation power *and how often it
fires*, tracer speed, spin velocity, glow. Scaling only the size of a reward while its admission frequency stays
constant reads as "reacts to everything the same" (Sphere's 2026-10-03 log: ~2 packets per 0.5 s at every level).

The shared ramp is `transient_bus.passage_ramp(intensity, quiet)`: `quiet` in the track's quietest passage, 1 in
its loudest, convex. Multiply by `musical_weight(loudness, presence)` so near-silence earns nothing. Any lane that is
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
it changes with frame rate.

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
- a new timer/poller/FFT/audio worker created because the mode wants a different response signal;
- normalising by `_raw_bass_avg` or any level that only adapts while Dynamic Floor is ON: with the floor OFF it
  is the manual-floor setting, so the lane pins at its ceiling (§13A);
- relying on Dynamic Floor for good reactions: it learns a level from the track and degrades as the song continues (§13A).

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

## 14. Evidence / negative-control map

Read these for the cases behind this guide rather than copying their old implementation literally:

- `Docs/Guardrails/Bubble_Temporal_Fidelity.md` — behavioral shape + temporal fidelity; loud-passage variation; cadence/delivery negative controls.
- `Docs/Historical_Bugs.md` **U-02 Bubble / Blob Signal-Contract Trap** — dead smoothed/post-AGC hold vs raw-energy blowout, stale-event replay, hot-chorus hard-ceiling failure.
- `Docs/Historical_Bugs/Sphere_2026-09-10_Acoustic_Admission_And_Cohort_Motion_Investigation.md` — consolidated acoustic intake and detached-cohort mistakes: playing state, loudness, saturated event confidence, and one global decay are **not** interchangeable admission/population/velocity authorities.
- R-69 / Bubble viewport evidence — viewport adaptation may not globally damp authored reaction.
- R-76 / tall Spectrum evidence — physical-pixel flicker caused by delivery/temporal scaling must not be “fixed” by reducing response.
- `Docs/Reference/Extruded_Bubble/Investigation.md` §65 — floor-independent fixed-scale body feed, sustained-lane knee/timing and per-identity breathing measured against 2D with Dynamic Floor ON (§13A).

Historical files are evidence and negative controls. Current source + `Spec.md` + current guardrails remain implementation authority.

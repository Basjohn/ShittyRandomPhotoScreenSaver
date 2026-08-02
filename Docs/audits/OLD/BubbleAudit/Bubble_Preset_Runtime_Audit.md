# Bubble Preset Runtime Audit

Last updated: 2026-06-18

## Purpose

This is a document-only audit of the authored Bubble settings that touch live runtime behavior, with special focus on `Preset 1 (Deep Sea)`.

Use this before any more Bubble runtime-code tuning. The recent failure family proved that repeated code-side retunes can move around soft hero behavior while leaving the same loud-passage collapse alive. The preset combination itself therefore has to be treated as a first-class suspect.

## Scope

- Bubble mode only
- Authored preset/runtime settings only
- No code changes implied by this audit
- New user-facing display-only control included:
  - `bubble_big_visual_smoothing`

## Bubble Runtime-Touching Setting Map

### Core technical drive

- `bubble_dynamic_floor`
  - Owner: shared visualizer technical config / beat engine floor context
  - Runtime effect: whether Bubble inherits dynamic floor uplift/support behavior
  - Risk: changing this can alter noise-floor behavior, not just loudness feel

- `bubble_manual_floor`
  - Owner: shared visualizer technical config / beat engine floor context
  - Runtime effect: hard authored floor baseline before Bubble sees band energy
  - Risk: lowering blindly can increase jitter/noise; raising can suppress small-lane life

- `bubble_dynamic_range_enabled`
  - Owner: shared visualizer technical config
  - Runtime effect: controls broader energy normalization behavior before Bubble consumes it
  - Risk: can change overall feel beyond Bubble

- `bubble_agc_strength`
  - Owner: shared visualizer technical config
  - Runtime effect: affects how aggressively incoming energy is normalized
  - Risk: too much can flatten contrast; too little can starve quieter passages

- `bubble_input_gain`
  - Owner: shared visualizer technical config
  - Runtime effect: first-stage drive into Bubble’s visible authority
  - Risk: most useful authored “volume into Bubble” knob, but can overheat everything if pushed too far

- `bubble_kick_lane_gain`
  - Owner: shared visualizer technical config
  - Runtime effect: shared kick/transient expressiveness feeding Bubble’s event accent path
  - Risk: can make Bubble feel spikier without solving sustained body authority

- `bubble_transient_pulse_gain`
  - Owner: shared visualizer technical config
  - Runtime effect: accent/transient amplification for Bubble
  - Risk: too much can produce more spikes without improving loud sustained openness

- `bubble_transient_clamp`
  - Owner: shared visualizer technical config
  - Runtime effect: caps transient contribution
  - Risk: lowering can deaden kick accents; raising can make loud passages flashy but not fuller

- `bubble_adaptive_sensitivity`
  - Owner: shared visualizer technical config
  - Runtime effect: dynamic sensitivity behavior before Bubble sees final drive
  - Risk: broad contract change, not a surgical loud-collapse fix

- `bubble_sensitivity`
  - Owner: shared visualizer technical config
  - Runtime effect: authored sensitivity scalar for Bubble’s input path
  - Risk: high leverage; changes quiet and loud together

- `bubble_audio_block_size`
  - Owner: shared visualizer technical config
  - Runtime effect: capture/update cadence tradeoff
  - Risk: can affect responsiveness and stability, not just Bubble size

- `bubble_bar_count`
  - Owner: shared visualizer technical config
  - Runtime effect: beat-engine lane density and runtime payload size
  - Risk: not the first authored suspect for loud collapse

### Bubble lane and body shaping

- `bubble_big_bass_pulse`
  - Owner: Bubble simulation / render-radius pulse multiplier
  - Runtime effect: big/hero pulse gain
  - Risk: stronger hero spikes without necessarily helping the broad small field

- `bubble_small_freq_pulse`
  - Owner: Bubble simulation / render-radius pulse multiplier
  - Runtime effect: small-lane visible pulse gain
  - Risk: higher values can help lively quiet passages faster than loud sustained ones

- `bubble_big_size_max`
  - Owner: Bubble simulation
  - Runtime effect: base hero bubble size
  - Risk: higher values lift the hero lane but do not guarantee broad field survival

- `bubble_small_size_max`
  - Owner: Bubble simulation
  - Runtime effect: base small-bubble size
  - Risk: one of the clearest authored levers for field visibility in louder passages

- `bubble_big_contraction_bias`
  - Owner: Bubble simulation
  - Runtime effect: how much hero bubbles shrink away outside stronger authority
  - Risk: too low makes the hero look impressively “breathy” in soft passages while feeling weak in louder passages

- `bubble_big_size_clamp`
  - Owner: Bubble simulation
  - Runtime effect: hero growth ceiling
  - Risk: too low can stop loud sections from ever looking meaningfully more open than soft ones

- `bubble_big_specular_max_size`
  - Owner: Bubble render styling
  - Runtime effect: highlight scale cap, not core loudness authority
  - Risk: visual polish only; low value can make hero look less grand without changing actual body size

- `bubble_big_visual_smoothing`
  - Owner: Bubble display-only render-radius seam
  - Runtime effect: visual settling for the big/hero radius only
  - Risk: if pushed too high it can make hero size feel late or syrupy; if too low it can flicker in soft passages
  - Guardrail: this must remain visual-only and must not become a surrogate loud-collapse fix

### Field density and motion

- `bubble_big_count`
  - Owner: Bubble simulation population
  - Runtime effect: hero population count
  - Risk: more heroes can clutter rather than clarify loud authority

- `bubble_small_count`
  - Owner: Bubble simulation population
  - Runtime effect: field density
  - Risk: can help “alive” perception, but also raises perf cost and can hide weak per-bubble authority

- `bubble_surface_reach`
  - Owner: Bubble lifecycle
  - Runtime effect: how many bubbles persist to the surface vs cycling out earlier
  - Risk: affects occupancy and overall fullness

- `bubble_stream_constant_speed`
  - Owner: Bubble motion
  - Runtime effect: base travel speed
  - Risk: louder sections can feel “busier” rather than “larger” if this is leaned on too hard

- `bubble_stream_speed_cap`
  - Owner: Bubble motion
  - Runtime effect: loud-passage travel ceiling
  - Risk: high cap can overexpress motion without fixing visible body

- `bubble_stream_reactivity`
  - Owner: Bubble motion
  - Runtime effect: how much motion responds to audio
  - Risk: one of the clearest ways a preset can turn loud sections into speed instead of size

- `bubble_rotation_amount`
  - Owner: Bubble motion
  - Runtime effect: rotational animation amount
  - Risk: visual flavor only unless extremely high

- `bubble_drift_amount`
- `bubble_drift_speed`
- `bubble_drift_frequency`
- `bubble_drift_direction`
  - Owner: Bubble motion
  - Runtime effect: broad field motion character
  - Risk: can enrich quiet passages visually and thereby exaggerate loud-vs-soft contrast if body authority is weak

### Collision / secondary behavior

- `bubble_bounce_big_pct`
- `bubble_bounce_small_pct`
- `bubble_bounce_big_speed`
- `bubble_bounce_small_speed`
- `bubble_bounce_same_only`
- `bubble_collision_pop_mode`
  - Owner: Bubble collision path
  - Runtime effect: secondary movement and collision character
  - Risk: not primary loud-collapse suspects for Deep Sea because that preset already keeps these conservative

### Trail / ghost persistence

- `bubble_trail_strength`
- `bubble_tail_opacity`
- `bubble_ghosting_enabled`
- `bubble_ghost_alpha`
- `bubble_ghost_decay`
  - Owner: Bubble visual persistence / style
  - Runtime effect: visual fullness and afterimage richness
  - Risk: these can make soft passages look more luxurious than their actual authority, which in turn makes loud under-reaction easier to notice

## Deep Sea Preset 1 — Current Authored Combination

Key authored values in `preset_1_deep_sea.json`:

- `bubble_manual_floor=0.20`
- `bubble_dynamic_floor=false`
- `bubble_input_gain=0.35`
- `bubble_sensitivity=0.95`
- `bubble_big_bass_pulse=0.85`
- `bubble_small_freq_pulse=0.65`
- `bubble_big_size_max=0.036`
- `bubble_small_size_max=0.012`
- `bubble_big_contraction_bias=0.65`
- `bubble_big_size_clamp=3.48`
- `bubble_big_visual_smoothing=0.5`
- `bubble_big_count=6`
- `bubble_small_count=45`
- `bubble_stream_constant_speed=0.15`
- `bubble_stream_speed_cap=1.9`
- `bubble_stream_reactivity=1.1`
- `bubble_transient_pulse_gain=0.9`
- `bubble_transient_mix_bass=0.6`
- `bubble_transient_mix_vocal=0.15`
- `bubble_trail_strength=0.8`
- `bubble_tail_opacity=0.8`
- `bubble_ghosting_enabled=true`
- `bubble_ghost_alpha=0.15`
- `bubble_ghost_decay=0.5`

## Ranked Hypotheses

### 1. Lowest-risk, highest-likelihood authored culprit

- `bubble_input_gain=0.35` is probably too conservative for a manual-floor `0.20` preset that is expected to stay visibly alive in louder sustained passages.
- Why this matters:
  - the preset is already opting out of dynamic floor uplift
  - the floor is not especially low
  - loud passages therefore need enough absolute authored drive before Bubble’s own shaping can help
- Likelihood of improvement: High
- Risk to feel/perf: Low to Medium
- Best mitigation of risk:
  - raise this first before changing counts or weakening the floor

### 2. Hero openness is probably being undercut by the authored body envelope

- `bubble_big_contraction_bias=0.65` and `bubble_big_size_clamp=3.48` together are a plausible reason soft passages can look aesthetically strong while louder sections still fail to open up enough.
- Why this matters:
  - contraction bias makes the hero breathe down more aggressively
  - the clamp limits how much true loud authority can recover that
- Likelihood of improvement: High
- Risk to feel/perf: Low
- Best mitigation of risk:
  - raise contraction bias and clamp before touching counts

### 3. Small-lane visibility may simply be authored too small for hot sections

- `bubble_small_size_max=0.012` with `bubble_small_count=45` creates a dense field of relatively tiny bodies.
- Why this matters:
  - in soft passages, trail/ghost motion can make this feel rich
  - in hotter passages, if the field does not widen enough, it can look inactive even when many particles are still present
- Likelihood of improvement: Medium to High
- Risk to feel/perf: Low
- Best mitigation of risk:
  - increase small size before increasing count

### 4. Motion may be winning over size in louder passages

- `bubble_stream_reactivity=1.1` and `bubble_stream_speed_cap=1.9` encourage louder sections to express more as movement energy.
- Why this matters:
  - if visible body authority is conservative, the preset can read as “faster but not larger”
- Likelihood of improvement: Medium
- Risk to feel/perf: Low
- Best mitigation of risk:
  - only revisit this after the size-authority changes above

### 5. Soft passages are visually enriched enough to make loud under-reaction harsher by comparison

- `bubble_trail_strength=0.8`, `bubble_tail_opacity=0.8`, and active ghosting materially enrich soft passages.
- Why this matters:
  - this probably is not the root cause
  - but it does make the contrast with weak loud sections more obvious
- Likelihood of improvement: Low as a root fix
- Risk to feel/perf: High relative to user constraints
- Best mitigation of risk:
  - do not use trail/ghost reductions as a fake fix

## Recommended Authored Experiment Order

### Pass 1 — safest first

- [ ] Raise `bubble_input_gain` from `0.35` to the `0.48 .. 0.55` range.
- [ ] Raise `bubble_big_contraction_bias` from `0.65` to the `0.78 .. 0.88` range.
- [ ] Raise `bubble_big_size_clamp` from `3.48` to the `4.0 .. 4.4` range.
- [ ] Raise `bubble_small_size_max` from `0.012` to the `0.0135 .. 0.015` range.
- Priority: P0
- Likelihood of improvement: High
- Risk: Low to Medium
- Guardrail:
  - do these before changing counts or floor contracts

### Pass 2 — only if Pass 1 still leaves the field visually dead

- [ ] Consider a modest `bubble_small_count` increase from `45` to the `52 .. 58` range.
- [ ] Consider a modest `bubble_big_bass_pulse` raise from `0.85` to the `0.92 .. 1.00` range only if hero size still feels too restrained after Pass 1.
- Priority: P1
- Likelihood of improvement: Medium
- Risk: Medium
- Guardrail:
  - do not use count growth as the first fix; it can hide weak size authority and costs more runtime

### Pass 3 — visual polish only

- [ ] Validate `bubble_big_visual_smoothing` at:
  - `0.35` for rawer hero movement
  - `0.50` as the middle/default restored authored feel
  - `0.65` for softer settling
- Priority: P1
- Likelihood of improvement: Medium for soft-pass hero UX, Low for loud collapse itself
- Risk: Low
- Guardrail:
  - this is not a loud-collapse fix; it only shapes hero soft-passage visual settling

## What Should Not Be The First Move

- [ ] Do not lower `bubble_manual_floor` first just because loud sections look weak.
  - Risk: reopens jitter/noise and changes the authored baseline too broadly.

- [ ] Do not push `bubble_transient_pulse_gain` or `bubble_transient_mix_bass` aggressively as the main answer.
  - Risk: louder sections become spikier/faster without becoming fuller.

- [ ] Do not reduce trail/ghost richness to make loud under-reaction look less bad.
  - Risk: violates the zero-fidelity-loss rule and hides the real issue.

- [ ] Do not increase counts before lifting existing body authority.
  - Risk: more particles can mask the diagnosis and cost performance.

## Suggested Runtime Validation Order

- [ ] Validate Deep Sea with only `bubble_big_visual_smoothing` changed.
  - Purpose: isolate the visual-only control.

- [ ] Validate Deep Sea with only Pass-1 size-authority changes.
  - Purpose: determine whether the preset itself was the main co-owner.

- [ ] If Pass 1 helps, compare against the current loud-vs-soft Bubble oracle before any more code tuning.
  - Purpose: stop the next code pass from solving the wrong thing again.

- [ ] Only reopen Bubble code if the adjusted preset still reproduces loud collapse under the stronger runtime-shaped oracles.
  - Purpose: keep authored tuning and runtime tuning from getting mixed into another loop.

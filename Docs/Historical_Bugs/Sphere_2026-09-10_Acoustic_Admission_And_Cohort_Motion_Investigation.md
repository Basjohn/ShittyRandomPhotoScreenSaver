# Sphere audio admission and detached-cohort motion: consolidated September 2026 investigation

**STRONG RETENTION VALUE DOCUMENT**

**Status:** Historical investigation; architectural constraints retained in the current Sphere reference and tests. Five connected incident accounts are consolidated here without turning their provisional numeric tuning into immutable preset goldens. This is not a second Sphere settings authority.

## Why these were one difficult problem

The shared transient bus, playback state, passage loudness, and the motion state of individual detached cohorts answer *different* questions. Several successive fixes failed when one was used as a substitute for another. The following five contemporary case reports retain their original symptoms, causes, measured observations, and negative controls. The present contract belongs to `Docs/Reference/Sphere_Visualizer.md` and `Docs/Guardrails/Visualizer_Presentation.md`.

## Original case: Voxel Sphere — Absolute Loudness Pinned Particle Density — 2026-09-10

### Symptom

Detached voxel motion had become granular, but particle **quantity** still looked too binary. Hardware logs showed normal loud passages with pre-AGC intake around `2.0–2.5` while the density response reached full population at `1.50`, so sampled active events were repeatedly `density=1.000`. A separate near-silence case could also leave the hysteretic gate open long enough for residual signal / latched typed evidence to author another small cohort.

### Root cause

Cohort population was driven by absolute passage energy. That is the wrong authority: loudness says how heavy the surrounding passage is, not how many detached voxels one qualified transient deserves. The hysteretic gate also lacked a stricter current-authoring floor once it had recently opened.

### Binding fix

- Keep typed/onset admission and loud-passage kick/vocal eligibility intact.
- Never use absolute passage loudness as detached-cohort population authority.
- After admission, derive population from event confidence + Sphere-local granular motion evidence, retaining a visible minimum and making full population exceptional.
- Keep the hysteretic presence gate, but require a current near-silence authoring floor before any **new** cohort can be created. Existing cohorts may finish naturally through silence.
- Do not solve this by raising shared transient thresholds, suppressing loud-bed events, reducing motion/velocity, or changing permanent visualizer audio paths.

## Original case: Voxel Sphere — Clamped Event Strength Was Not Particle Velocity (2026-09-10)

### Symptom

Qualified low/flat transients and obvious kick/vocal/drum peaks could launch detached voxel cohorts at nearly the same apparent speed. Hardware described the result as effectively **0 or 1.0 power/velocity** even after real cohort transport existed.

### Cause

The shared transient bus intentionally normalises event confidence and clamps sufficiently strong events to `1.0`. That is valid admission evidence but destroys the amplitude granularity needed for particle presentation. Sphere incorrectly reused the clamped event strength as its velocity accent.

### Binding fix

- Shared typed/spectral events remain **admission authority** so reactivity is not reduced.
- Particle travel intensity is Sphere-local presentation state derived from positive **live pre-AGC loudness jump** plus **raw analysis-spectrum flux relative to its adaptive threshold**.
- Clamped event confidence supplies only a modest motion floor; it can never by itself mean maximum particle speed.
- Intake keeps a slower ordinary return than outtake, while genuine high-contrast attacks may still reach a fast endpoint.
- Intake fade-in follows cohort progress and remains gentle at low motion intensity.
- Vocal recoil remains fully reactive. If it pushes beyond the normal launch radius, fade only the over-launch tail instead of clipping or reducing recoil amplitude.
- Do not solve this by lowering event admission frequency, fragmentation, tracer activity, or the stable four-corner participation contract.

### Regression signal

If two admitted events with radically different local acoustic contrast receive the same maximum `velocity_accent` merely because their shared event strengths are both `1.0`, this bug has returned.

## Original case: Voxel Sphere — Global Intake Decay Was Not Velocity (2026-09-10)

### Failure

The early Sphere **Intake Velocity** control changed the release time of one global
`incoming_drive` scalar. New audio events could raise that scalar again while earlier
voxels were still returning. Physically this looked persistently fast and could reset a
large detached population; it was not particle/cohort velocity.

### Fix / binding contract

- Detached flow is a bounded **four-slot Sphere-only cohort ring** on the existing logical
  frame cadence.
- Each cohort captures stable voxel lane/quadrant, density, strength, travel progress,
  transient velocity accent, vocal-bounce ownership and intake/outtake direction at launch.
- New events do **not** globally change the progress or speed of cohorts already in flight.
  If all four slots are materially occupied, this secondary reward may coalesce rather than
  teleport active voxels.
- Particle Velocity changes real cohort travel duration/curve only. It must never become a
  global audio-chasing velocity multiplier.
- Intake voxels return to their own canonical shell slot. Optional Particle Outtake moves
  the selected source outward/fading while a replacement fades into the same canonical slot.
  Direction is captured at launch and cannot reverse an existing cohort.
- Outtake's extra source is an optional second instanced draw of the **same static Sphere
  voxel buffer**. Do not introduce a second geometry owner, private timer/poller/worker,
  per-voxel Python object graph, or accepted-visualizer behavior.
- Playing/source-active remains lifecycle state only; live pre-AGC energy + qualified events
  remain the admission authority. Preserve the physically accepted four-corner distribution
  and vocal-linked intake bounce.

### Regression signal

If a future implementation can make every visible detached voxel change speed/position when
one new event arrives, or describes one exponential global envelope as "particle velocity",
this bug has returned.

## Original case: Voxel Sphere Ingress Population Continuity — 2026-09-10

### Symptom

After raw pre-AGC onset work finally made Sphere feel broadly reactive, four-corner intake became visually exhausting: changing the dominant corner could make a large fraction of the shell appear to change at once.

### Cause

`incomingField()` included the **current dominant quadrant** in the deterministic voxel-selection hash. A dominance change therefore re-ranked particles in every quadrant instead of merely changing the intended 46% -> 70% fringe. Audio timing was good; visual population identity was not stable.

### Fix / guardrail

- Ingress rank depends only on stable voxel seed + visible quadrant.
- Every quadrant retains the same ~46% base population.
- Dominance crossfades only the extra ~24% fringe over ~110 ms.
- A narrow rank feather interpolates individual fringe participation.
- Do not solve this with whole-frame temporal blending, motion blur, slower audio detection, fewer packets, or reduced reaction amplitude.

Fragment visual interpolation is a separate optional Sphere setting; it smooths geometry only and is enabled in Reactive Voxel / Preset 6 for validation.

## Original case: Voxel Sphere — Playback State Is Not Ingress Authority (2026-09-10)

### Symptom

While the source remained in the playing state, incoming voxels could continue to appear through acoustically silent passages. Hardware logs included `active=True` frames with live pre-AGC bass/mid/high all at zero while an incoming envelope was still visible. Some residual envelope is legitimate landing from the preceding event; **authoring a new cohort from playback state or stale event evidence is not.**

### Cause / architectural trap

`playing` proves source ownership/lifecycle only. It says nothing about current acoustic energy. Incoming particles are visually expensive enough that treating source-active state as implicit admission makes quiet scenes feel permanently busy and increases perceptual jerk.

### Binding fix

- New incoming cohorts require a hysteretic **live pre-AGC** energy gate.
- A typed event may bypass the normal open threshold only when the same frame has non-silent live pre-AGC support; true silence always rejects new intake.
- Existing cohorts may finish their landing after the gate closes; do not hard-cut them.
- Optional energy-scaled cohort density and transient velocity are presentation modifiers only. They must not become event detectors, polling loops, or new audio workers.
- The four-corner stable-rank distribution remains independent of event/dominant identity; density changes threshold membership, never the hash.

### Do not regress

Do not "fix" quiet overactivity by reducing Sphere onset frequency, fragmentation strength, raw pre-AGC freshness, tracer travel, or the accepted vocal-linked bounce. The intake gate controls **permission to admit a new cohort**, not the primary musical reactivity contract.

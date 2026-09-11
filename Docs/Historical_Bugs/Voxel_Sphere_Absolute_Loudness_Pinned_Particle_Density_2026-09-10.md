# Voxel Sphere — Absolute Loudness Pinned Particle Density — 2026-09-10

## Symptom

Detached voxel motion had become granular, but particle **quantity** still looked too binary. Hardware logs showed normal loud passages with pre-AGC intake around `2.0–2.5` while the density response reached full population at `1.50`, so sampled active events were repeatedly `density=1.000`. A separate near-silence case could also leave the hysteretic gate open long enough for residual signal / latched typed evidence to author another small cohort.

## Root cause

Cohort population was driven by absolute passage energy. That is the wrong authority: loudness says how heavy the surrounding passage is, not how many detached voxels one qualified transient deserves. The hysteretic gate also lacked a stricter current-authoring floor once it had recently opened.

## Binding fix

- Keep typed/onset admission and loud-passage kick/vocal eligibility intact.
- Never use absolute passage loudness as detached-cohort population authority.
- After admission, derive population from event confidence + Sphere-local granular motion evidence, retaining a visible minimum and making full population exceptional.
- Keep the hysteretic presence gate, but require a current near-silence authoring floor before any **new** cohort can be created. Existing cohorts may finish naturally through silence.
- Do not solve this by raising shared transient thresholds, suppressing loud-bed events, reducing motion/velocity, or changing permanent visualizer audio paths.

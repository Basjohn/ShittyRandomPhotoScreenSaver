# Voxel Sphere — Clamped Event Strength Was Not Particle Velocity (2026-09-10)

## Symptom

Qualified low/flat transients and obvious kick/vocal/drum peaks could launch detached voxel cohorts at nearly the same apparent speed. Hardware described the result as effectively **0 or 1.0 power/velocity** even after real cohort transport existed.

## Cause

The shared transient bus intentionally normalises event confidence and clamps sufficiently strong events to `1.0`. That is valid admission evidence but destroys the amplitude granularity needed for particle presentation. Sphere incorrectly reused the clamped event strength as its velocity accent.

## Binding fix

- Shared typed/spectral events remain **admission authority** so reactivity is not reduced.
- Particle travel intensity is Sphere-local presentation state derived from positive **live pre-AGC loudness jump** plus **raw analysis-spectrum flux relative to its adaptive threshold**.
- Clamped event confidence supplies only a modest motion floor; it can never by itself mean maximum particle speed.
- Intake keeps a slower ordinary return than outtake, while genuine high-contrast attacks may still reach a fast endpoint.
- Intake fade-in follows cohort progress and remains gentle at low motion intensity.
- Vocal recoil remains fully reactive. If it pushes beyond the normal launch radius, fade only the over-launch tail instead of clipping or reducing recoil amplitude.
- Do not solve this by lowering event admission frequency, fragmentation, tracer activity, or the stable four-corner participation contract.

## Regression signal

If two admitted events with radically different local acoustic contrast receive the same maximum `velocity_accent` merely because their shared event strengths are both `1.0`, this bug has returned.

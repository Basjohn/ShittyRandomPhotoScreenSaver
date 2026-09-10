# Voxel Sphere Ingress Population Continuity — 2026-09-10

## Symptom

After raw pre-AGC onset work finally made Sphere feel broadly reactive, four-corner intake became visually exhausting: changing the dominant corner could make a large fraction of the shell appear to change at once.

## Cause

`incomingField()` included the **current dominant quadrant** in the deterministic voxel-selection hash. A dominance change therefore re-ranked particles in every quadrant instead of merely changing the intended 46% -> 70% fringe. Audio timing was good; visual population identity was not stable.

## Fix / guardrail

- Ingress rank depends only on stable voxel seed + visible quadrant.
- Every quadrant retains the same ~46% base population.
- Dominance crossfades only the extra ~24% fringe over ~110 ms.
- A narrow rank feather interpolates individual fringe participation.
- Do not solve this with whole-frame temporal blending, motion blur, slower audio detection, fewer packets, or reduced reaction amplitude.

Fragment visual interpolation is a separate optional Sphere setting; it smooths geometry only and is enabled in Reactive Voxel / Preset 6 for validation.

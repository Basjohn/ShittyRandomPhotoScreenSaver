# R-94 — Melt's Float Noise Hash Cut The Photograph Into Rectangles

Date: 2026-09-23  
Status: SOLVED IN CODE — `0dea3418`; Melt's overall look awaits operator acceptance

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

The operator saw "straight lines throughout the melting image": hard vertical (and horizontal) seams where
blocks of the photo sagged by different amounts.

## Root Cause

Melt's melt-time field used value noise over a chaotic float hash
(`fract(p*vec2(123.34,456.21)+…)`, then `fract(p.x*p.y)`) with large seed-offset coordinates. Neighbouring
noise cells evaluate the same lattice corner through differently inlined expressions; the GPU compiler rounds
them differently, and the chaotic hash turns a one-ulp difference into an unrelated value. Each noise cell
therefore melted at its own time — a hard-edged rectangle grid in the melt field.

## Why It Was Hard To Find

It depends on the GPU compiler's rounding, not on the maths (on paper the noise is continuous). The drip
columns looked like a plausible cause and were blamed first. Rendering the melt-time field itself as a debug
image showed the rectangles immediately.

## Fix

An exact integer lattice hash (`uvec3` mix of the integer corner and the seed): every cell gets bit-identical
corner values.

## Regression Coverage

`tests/test_qtquick_melt_surface.py::test_melt_field_has_no_seams` renders the production field and bounds
neighbour differences; it fails on the old hash.

## Guardrail

Value noise that drives geometry or displacement must hash integer lattice coordinates exactly. Other shaders
still use `fract(sin(dot(...)))` hashes; audit them with the same field render before trusting them for
displacement.

## Audit Of The Other Shaders (2026-09-26)

Only three other transitions build interpolated value noise; the rest hash a whole cell index (Diffuse,
Exploding Tiles, Directional Pixel Accretion, Raindrops, Block Flip, Crumble's chunk hash), where every cell
is meant to differ and one cell is always hashed through the same expression, so R-94's mechanism does not
apply.

- **Burn** (`warped_fbm` of `vnoise`, a sine-free chaotic float hash) shapes the burn front, and **Ink Bloom**
  (`noise2`, a `fract(sin(dot()))` hash) shapes the pigment veins. Both fields were rendered from inside the
  production shaders (output patched at the call site, seeds 713/4242/999, 640×360, NVIDIA RTX 4090): smooth,
  no rectangles or straight lines, largest neighbour step 18/255 with no isolated jump above 10/255.
- **Crumble**'s `stone()` noise is chunk-local (`vRock`) and only shades broken rock faces; it drives no
  geometry, so it is outside this rule.

No shader was changed. No regression bar was added either: R-94's failure did not reproduce on this GPU even
with the reconstructed chaotic hash placed in Burn's production shader or in a standalone field, so a new bar
could not be shown to fail when the defect returns. If a seam is ever reported, render that field as above
and move its hash to the exact integer lattice hash Melt uses.

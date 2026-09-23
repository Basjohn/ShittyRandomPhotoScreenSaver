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

# R-249 | Extruded Bubble's wake beads teleported a fraction of their parent's radius (worse for big parents)

**Status:** fixed 22 Nov 2026 (operator report 19 Nov; N5.6's first step, before the port's references), commit
ff7a86d14. Regression bar: `tests/test_extruded_bubble_wake_bead_continuity_gpu.py` runs the production `beadInstance`
on native GL on real `WakeField` records from a bubble turning through every direction: largest step per tick under
0.08 of the radius (pre-change shader 0.208; each half of the fix alone 0.209 and 0.133, both run as negative controls).

## Symptom

With wakes on, idle parent bubbles occasionally jumped their wake bubbles sideways; small parents barely showed it,
large ones clearly.

## Cause

Two discontinuities in the fizz/wake code (`rendering/gl_programs/extruded_bubble_program.py`), both proportional to
the parent's radius:

1. The trail curve's head segment used a mirrored phantom neighbour (`2 p1 - p2`). Every new wake point the bubble laid
   reshaped the curve through the same water, so every bead on it jumped about 0.22 of the radius; at idle a new point
   comes every few seconds.
2. Each bead's offset across its veil was `cross(tangent, a fixed z blended toward x)`. On a cone of trail directions
   that axis ran parallel to the trail and the cross product flipped, moving every bead across the veil in one frame
   (up to 0.78 of the radius).

## Why it stayed hidden

Both are rare per bead and small on small parents; the beads are tiny at 1080p and a single-frame jump reads as
sparkle. Nothing measured bead continuity: the wake's own records were continuous, only the shader's placement was not.

## Fix

The head neighbour is the bubble itself (`p0 = p1`), and the offset is a stable random 3D scatter with the trail
direction projected out (continuous in every direction; a 0.863 factor keeps the old mean spread). Traces on Preset 9
with music then idle: typical (p99) step 0.17 to 0.066 of the radius, largest 0.78 to 0.12 (the remainder is the
bubble's own motion in loud passages). Evidence: `.artifacts/evidence/visualizers/extruded_bubble/n56_wake_teleport/`.

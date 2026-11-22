# R-250 | Extruded Bubble's "emission starfish": a flickering star of beads at the emission face (Preset 9, orbiting)

**Status:** fixed 22 Nov 2026 (operator report: "the strange emission starfish in preset 9", seen orbiting with music;
confirmed fixed live by the operator the same day), commit 15be417dc. Regression bar:
`tests/test_extruded_bubble_scene_cycle.py`: no tiny-particle stream may wrap within a frame (control: the raw in-tank
path lengths do wrap).

## Symptom

With music on Preset 9, orbiting the camera brought a rapidly flickering star-shaped burst into view at the stream's
emission face, plus clumps of tiny bubbles that looked pinned there. The authored default camera keeps that face just
off screen, so the default view never showed it.

## Cause

The free bead chains (gathered into lanes by Stream Lanes), marine snow and specks each cycle their particles along
their path through the tank, inlet to exit. A chain whose inlet sat near the exit corner had an in-tank path of only
0.055 units, and it is drawn only when the music lifts the chain count past 73 of 120. On that path its 160 beads
wrapped faster than a frame, so each frame every bead landed somewhere new along its own spray ray at the emission
face: a flickering star. Chains with short paths (down to about 1.5 units) packed their beads into dense clumps that
read as pinned bubbles.

## Why it stayed hidden

Only an orbit shows the emission face; the chain that caused it appears only in loud passages; and the first search
(a lead's brief that paraphrased the report as a "bubble-star at the default camera") looked from the default camera.

## Fix

Each tiny-particle stream cycles over its in-tank path or 12 units, whichever is longer; the fade where it leaves the
tank stays at the real exit. The shader and the CPU twin used for drift share the value. Orbit capture (turn 0.6,
60 fps, recorded music): frame-to-frame flicker peak at the source 23,763 to 6,686 (ordinary crowd churn). Evidence:
`.artifacts/evidence/visualizers/extruded_bubble/n56_flicker/`.

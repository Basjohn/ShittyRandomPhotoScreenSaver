# R-225 | Bubble drew a ghost ring frozen where an earlier frame's trail samples left it

**Status:** fixed 15 Nov 2026 (found reading the renderer for the N5.1 Bubble port, step 1e). Present since the Quick
Bubble renderer kept its uniform values between frames (N1.6). Owner:
`rendering/quick/visualizer/implementations/bubble.py` (`QuickBubbleRenderer.render`, the trail branch). Regression bar:
`tests/test_bubble_stale_trail_ghost.py::test_a_frame_without_trails_draws_no_ghost_kept_from_an_earlier_frame` (a
frame without trail samples drawn after one with them equals the same frame drawn first). Its negative control is the
same test on the code before the fix: 174 pixels of a ghost ring differ on the 420 x 280 card.

## Symptom

None reported. With Ghost on, once every bubble's smear went quiet (the simulation then publishes no trail samples),
each bubble kept a faint afterimage ring at the place its history held on the last frame that had trails, until the
trails came back.

## Cause

`BubbleSimulation.snapshot` publishes an empty trail payload when no bubble's trail is active. The renderer then set the
wake's strength to 0 but left `u_bubbles_trail` as the last frame with trails wrote it (the block's values persist
between frames, as the old uniforms did). `bubble.frag`'s ghost pass reads each bubble's oldest sample whatever the
wake's strength, so it drew a ghost from those samples.

## Fix

On the frame where the trails stop, the renderer clears the trail samples once (`_trail_samples_held`); nothing is
written again while they stay off. The native record (N5.1) carries zeros on such a frame, so both renderers draw the
same.

## Why it hid

- The ring is faint (Ghost's alpha times the ghost's own fade) and sits near the bubble.
- Trails are active most of the time in music, so the frozen state rarely lasted long.

## Lessons

1. A value a pass keeps between frames must be written by every frame that changes what it means, including a frame
   that has none of it; "the shader skips it" holds only for the readers that check the same gate.
2. A port that moves values into a record (every field written every frame) surfaces exactly these stale-value paths:
   read the renderer's "kept from an earlier frame" comments as a list of suspects.

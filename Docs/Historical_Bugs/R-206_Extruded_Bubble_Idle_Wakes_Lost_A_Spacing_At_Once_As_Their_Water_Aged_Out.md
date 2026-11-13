# R-206 | Extruded Bubble's idle wakes lost a whole spacing at once each time their oldest water aged out

**Status:** fixed 14 Nov 2026 (Current_Plan 1D.8). Present since the wakes became the water the bubble passed through
(60e51c10, 25 Oct 2026), before and after 480b398b. Owner: `widgets/spotify_visualizer/extruded_bubble_wake.py`
(`WakeField.flow`, `record`), with the GPU path's end point in `rendering/gl_programs/extruded_bubble_program.py`
(`trailWater`). Regression bars in `tests/test_extruded_bubble_wake_contract.py`:
`test_a_slow_trail_ends_where_its_water_ages_out_never_a_spacing_at_once` (failed before the fix: a 0.447 world-unit
step against a 0.0056 bound) and `test_an_idle_wake_never_jumps_in_length` (the idle detector through the
simulation: failed with 1.29 bubble radii against 0.2). Evidence: `.artifacts/evidence/visualizers/extruded_bubble/
idle_wake_teleport/20261114_detector/` (detector summaries and events) and `.../20261114_frames/` (old and fixed
consecutive idle frames at detected jumps).

## Symptom

Operator, 13 Nov: at idle a wake occasionally jumps (its contents, its length or where it hangs). During playback
it does not.

## Cause

1. A wake keeps up to 12 points of the water its bubble passed through, laid one spacing apart. `WakeField.flow`
   dropped every point older than `HISTORY_SECONDS` (8 s) by cutting the whole-number point count.
2. The GPU draws the trail out to `trailReach = lead + count - 1` spacings and lays out everything along it by its
   share `s` of that reach: the sheet's narrowing, its tail fade and the beads' end fade. A count one lower cut the
   trail short by a whole spacing (0.7 to 1.5 bubble radii) in one frame and rescaled the width and fade along the
   rest of it, so the whole veil changed shape at once.
3. Playing, bubbles rise fast enough that their 12 points span less than 8 s and the reach is capped at 11 spacings,
   so points rarely age out (162 jumps in a 60 s replay). At idle they rise slowly: every trail keeps losing its
   oldest point as it ages (3,127 jumps of more than 0.6 radii in the same 60 s, 3,097 of them a count cut by age;
   median 1.03 radii, worst 1.50).
4. 480b398b had nothing to do with it: it changed only the shader (the sheet and beads sized by the steady radius,
   not the beat swell). Box 1D.11's background unit did not either: unit 0 was empty in every frame, idle or playing.

## Fix

The trail ends where its water reaches `HISTORY_SECONDS` of age, interpolated by age between the last young point
and the first aged one, which stays as the endpoint; once every point has aged the end lies between the bubble
(fresh water) and its newest point. The record's count carries that end as a fraction (below 1 in the last case);
`trailWater` holds `ceil(count)` points (it rounded before, the same for whole counts). After the fix, on the same
60 s replay, the largest per-frame change of a visible wake's drawn length is 0.02 radii idle (was 1.50) and 0.36
playing (was 1.50; the 0.36 is one bubble's own head step). Consecutive idle frames at tick 728, where the old code
dropped a point: the old pair changes 27,700 pixels (the left bubble's wake disappears from one frame to the next: its shortened length falls under the strength ramp), the fixed pair 3,189.

## Why it hid

- Playback, where the wakes were tuned and judged, rarely ages a point out; idle does it constantly.
- Every drawn quantity was continuous in the water index, which earlier fixes (881446a9, 480b398b) made the rule,
  but the count was an integer by construction and nothing checked the drawn length frame to frame.

## Lessons

1. Anything a shader normalises by (here the trail's reach) must itself be continuous; a whole-number count that
   can fall by one is a jump in everything laid out along it.
2. Judge a reactive effect at rest as well as in music: the idle path runs the same code with different rates, and
   rates decide which discontinuities show.

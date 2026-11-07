# R-55 — Spectrum Visual Smoothing: A Paint-Local Second Cadence (Aug) And Dead Smoothing After A Cleanup (Nov)

**STRONG RETENTION VALUE DOCUMENT. REPEAT BUG: Spectrum smoothing has broken twice, in opposite directions.**

Date: 2026-08-02 (first incident); 2026-11-06 (recurrence)
Status: Fixed. The accepted method has stood since August. The November fix restored it, and the operator accepted
it on 7 Nov 2026 ("very successful").

## If Spectrum smoothing looks wrong again: check these first

| Symptom | Likely cause | First check |
| --- | --- | --- |
| Smoothing On/strength changes nothing; bars look raw and jittery at every strength | The reset edge is stuck: `first_frame` stays true, so `SpectrumFrameRuntime.resolve` snaps to source on every tick (Nov 2026) | Replay one clip at off / 0.3 / 0.7 / 1.0. Byte-identical drawn bars mean the reset branch runs every tick. Then find who sets `_has_pushed_first_frame` (`widgets/spotify_visualizer/logical_frame_capture.py`, `capture_visualizer_logical_frame`) |
| Smoothing makes motion *less* smooth or stepped; paints exceed state publications | A second presentation cadence: smoothing moved into paint/render, or it requests its own repaints (Aug 2026) | Compare paint and update counts with `set_state`/publication counts per 10 s; paint must not exceed publication |
| Regular jerk every few ticks whatever the smoothing | Not smoothing: missing fresh audio (R-171, capture TripleBuffer) | `[AUDIO_LANE]` published/s against the tick rate, before touching any filter |

The accepted shape (do not redesign it):
- one symmetric, time-compensated one-pole filter;
- mode-owned presentation state, advanced only on the existing authoritative logical tick;
- the `2–14 ms` strength mapping;
- snap to source at the first-frame, activation, generation, mode, pause/disable and teardown boundaries, and after
  stalls of 100 ms or more;
- it covers Spectrum, Extruded Spectrum, Shockwave Grid and the Spectrum Studio step.

Regression bar: `tests/test_spectrum_visual_smoothing_seam.py` runs the production tick seam and compares strengths
with each other, never with authored values. Its negative control re-creates the never-cleared flag.

**Lessons for both incidents:**
1. When a cleanup retires a writer, check every reader of the state it wrote. A reset-edge flag with no writer left
   silently turns a filter into a pass-through.
2. Stub hosts must not set state that production never sets. The November tests stayed green only because their
   stubs set `_has_pushed_first_frame=True` by hand.
3. More paints are never evidence of smoother motion.

## Commits

```text
accepted executor restoration: 4bde89e8e39177dc4dd7b5e64b9ac99256ab9486
rejected smoothing experiment:  ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
exact revert on main:          ff93461685476bd0657aa88312fc2e35e9037880
```

`ff934616` has no file differences from `4bde89e`; it preserves the commit-level rollback point without moving `main` backwards.

## Observed Failure

After the executor-path restoration had made Spectrum significantly better, a Spectrum-only presentation smoothing experiment made it **significantly less smooth** in the installed runtime.

The experiment attempted to preserve zero-latency attack by snapping rises immediately while exponentially smoothing only falling values. It ran inside the GL overlay frame shell and requested another paint while decay remained unfinished.

## Evidence

The supplied installed logs showed the existing authoritative Spectrum state cadence already publishing approximately:

```text
set_state:       977–1000 per 10 seconds
```

With the smoothing experiment active, the overlay additionally reached approximately:

```text
paint:           1417–1544 per 10 seconds
update_requests: 1489–1551 per 10 seconds
```

Stable intervals commonly showed 1000 authoritative state updates but roughly 1479–1544 paints per 10 seconds. The smoothing path therefore introduced about 48–54 extra self-requested paints per second instead of merely improving the existing presentation.

No large CPU error was required for the visual regression. The failure was cadence and behaviour, not simple throughput exhaustion.

## Root Cause

The experiment accidentally created a second presentation cadence:

1. the normal visualizer tick published authoritative Spectrum bars;
2. the GL overlay independently mutated those bars during paint;
3. unfinished decay requested another paint;
4. those local paints ran between and out of phase with authoritative publications.

The asymmetric rule also produced an undesirable motion shape under rapidly changing music:

- falls were repeatedly held/interpolated;
- a later rise snapped immediately;
- the result could feel more stepped despite a higher paint count.

`paintGL()` had become presentation-state authority rather than a consumer of already-authored state.

## Why Tests Missed It

The deterministic tests proved only that:

- first presentation snapped to source;
- rises were numerically immediate;
- falls converged;
- generation changes reset state;
- another update was requested during decay.

Those tests did not reproduce the installed relationship between:

- the existing approximately 100 Hz authoritative `set_state` cadence;
- the additional approximately 50 Hz self-requested paint cadence;
- real Qt/GL paint scheduling;
- fast alternating musical rises and falls;
- operator perception of continuity.

The test that approved continuation paints was therefore authorizing the defect rather than detecting it.

## Correction

The smoothing implementation and its authorizing tests were removed completely in `ff934616`.

The accepted state is the executor-restored, unsmoothed presentation path. Bubble was not changed by either the experiment or the revert.

## 2026-08-08 Follow-Up Candidate — Positive Main-Runtime Result, Stronger Golden Still Open

After later installed evidence confirmed that ordinary Spectrum bars had no
presentation-only filter, the user authorized a new optional adjustable experiment.
This candidate deliberately does **not** revive the rejected mechanism:

- state advances only on the existing authoritative UI visualizer tick before the GPU
  frame push;
- rise and fall use one symmetric time-compensated filter rather than immediate-rise/
  paint-local-fall authorities;
- no timer, scheduler, queue, overlay self-update, repaint loop, paint mutation,
  source decimation, Bubble change, or shared-analysis change exists;
- disabled/default/stronger settings are available, with `true`/`0.50` as the candidate
  default;
- first-frame/identity/pause/disable/teardown boundaries and UI stalls of at least
  `100 ms` snap or reset to authoritative source.

Versioned temporal fixtures now cover rise, residual settling on existing ticks, drop,
stall snap, generation reset, and zero independent presentation cadence. These tests
make the implementation structurally safer.

The later canonical main runs add a positive operator and runtime result. Under
modest load the user judged adjustable smoothing around `0.50–0.60` visually
successful. In the `23:44–23:49` checkpoint Spectrum retained the configured
strength through Settings, published only on the authoritative tick, recorded
no geometry/reset failure, and kept overlay paint at or below state publication
rather than recreating the rejected extra-paint cadence. Ten-second steady
windows reached roughly `89–95 FPS` for both state and paint. This is meaningful
acceptance evidence for the implementation shape.

It is not yet the final stronger golden: exact real-source attacks, drops,
alternation, playback offsets, paused/reset cases, and source-to-paint receipt
still need the explicit temporal package. `ff934616` therefore remains the
earlier behavioural authority and `3b6082dd` remains the hard checkpoint if the
candidate later shows visible delay, transient flattening, pumping, extra UI
churn, or any Bubble/Spectrum regression.

### Method blacklist and whitelist

Blacklisted for this problem:

- interpolation or decay mutation in `paintGL()`/render callbacks;
- unfinished smoothing that requests its own repaint;
- asymmetric snap-rise/smooth-fall tuning that can hold drops then jump on rises;
- a new timer, cadence cap, scheduler lane, source decimation, or paint acknowledgement;
- accepting increased paint/update counts as proof of smoothness.

The only currently admissible method shape is mode-owned presentation state on the
existing authoritative tick, bounded reset identities, no independent GUI work, exact
temporal negative controls, and operator approval. The `0.50` default now has positive
main-runtime evidence, but it remains guarded by the incomplete stronger golden rather
than becoming permission for shared or paint-local smoothing.

## Durable Prevention

Future Spectrum smoothing or interpolation must:

- run only on the existing authoritative visualizer presentation tick;
- add no timer, scheduler, paint-derived clock, or self-requested repaint loop;
- never mutate Spectrum bars inside `paintGL()` or a render callback;
- preserve immediate attack unless the user explicitly approves otherwise;
- reset on activation, generation, mode, teardown, and first-frame boundaries;
- remain isolated from Bubble and shared source scheduling;
- compare update, publication, and paint cadence against the approved baseline;
- require stronger goldens first and explicit installed user approval afterward.

More paints are not evidence of smoother motion.

## 2026-11-06 Follow-Up — The Accepted Smoothing Was Dead Since The R77 Cleanup

Operator (6 Nov): "Spectrum still has broken visual only smoothing" (live: Spectrum smoothing on at `0.7`).

**Cause.** `SpectrumFrameRuntime.resolve` snaps to source while `first_frame` holds (a correct reset boundary). The
capture derives `first_frame = not widget._has_pushed_first_frame`, and the only writer that set the flag True was the
legacy GL overlay push deleted in `2cd939a0` (2 Sep, R77 debris cleanup). From then on every tick was a "first
frame", the reset branch ran every tick and every strength drew exactly the unsmoothed bars: Spectrum, Extruded
Spectrum and Shockwave Grid alike, and the Spectrum Studio's step too. The tests missed it because their stub hosts
set `_has_pushed_first_frame=True` by hand, which production never did.

**Measured** (production replay, preset index 0, 30 s each of anything_mixed2 / 1985_loud1 / growingpains / ragdoll):
before the fix, off, 0.3, 0.5, 0.7 and 1.0 were byte-identical. After: mean drawn-vs-source difference and jerk
reduction grow monotonically with strength (anything_mixed2 jerk −9% / −17% / −23% / −30% at 0.3 / 0.5 / 0.7 / 1.0;
added velocity lag ≈ +1.1 / +2.3 / +3.4 / +5.1 ms; kick peak retention 99 / 98 / 98 / 97%).
Evidence: `.artifacts/evidence/visualizers/spectrum/smoothing/20261106_smoothing/` in the main checkout (local and git-ignored; copied from
the fix agent's worktree on 7 Nov). It holds:
- before/after measurement JSON and text;
- `summary_anything_mixed2.json` (before the fix, 0.7 was identical to off);
- 0.5 s trace and kick strip PNGs;
- realtime and quarter-speed before/after WebPs.

Commits: `bb826a84` (fix), `c66c3278` (merge). The cleanup that removed the flag's only writer was `2cd939a0`.

**Fix.** `capture_visualizer_logical_frame` ends the first-frame edge with the first captured frame (one attribute
write per capture; no timer, thread or new state). The filter itself, its symmetric one-pole shape, its `2–14 ms`
mapping and its reset boundaries are unchanged: this restores the August-accepted behaviour. Regression:
`tests/test_spectrum_visual_smoothing_seam.py` (production tick seam, with a negative control re-creating the
never-cleared flag).

**Physical check.** The restored effect is subtle at ~90 Hz (≤ half a tick of lag at 1.0). Whether the authored
range is strong enough is the operator's call in a real session; widening it is a product choice, not part of this fix.

**Accepted (operator, 7 Nov 2026):** "Spectrum's visual smoothing fix … was very successful." This fixed state is
the reference if smoothing regresses again. Restore this behaviour rather than inventing a new filter.

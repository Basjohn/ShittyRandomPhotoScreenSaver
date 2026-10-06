# R-105 | Bubble Remaining Small-Radius Judder Investigation

Status: **CANDIDATE IMPLEMENTED / REPLAY + PHYSICAL ACCEPTANCE OPEN**  
Opened: 2026-10-05  
Working source: GODZIP `ad96bb78a3`  
Binding guardrail: `Docs/Guardrails/Bubble_Temporal_Fidelity.md`

## Symptom

After the first render-side judder correction, Bubble is materially better but the operator can still see small bubbles
caught between breathing states: the radius appears to move only one or two physical pixels and then vibrate rather than
completing a clean breath.

This is **not permission to smooth Bubble generally**. A cure that lowers attack, amplitude, elasticity, hot-passage variation,
settling quality or perceived reactivity is a regression even if it reduces a numerical judder counter.

## The previous fix is confirmed landed

The fix was not lost with the previous agent. Git history contains:

- `cf91835498` — pre-judder paranoia checkpoint.
- `800bf70f18` — `Bubble: the drawn radius no longer vibrates between breathing states`.
- `ad96bb78a3` — later manual judder/guardrail update and the supplied GODZIP head.

`800bf70f18` is present in the supplied tree. The current code:

- keeps `_sustained_loud_energy` and `_render_body_energy` raw for Bubble simulation authority;
- creates `_drawn_loud_energy` and `_drawn_body_energy` copies that rise immediately and release over
  `RENDER_SIZE_RELEASE_S` (0.10 s);
- applies the same release to `BubbleState.size_gate_energy` on downward movement;
- deliberately rejected feeding the envelope into `pulse_energy` because that changed Bubble excursion/feel;
- carries `tests/test_bubble_render_judder.py` with the old instant-release behaviour as a negative control.

That fix reduced recorded radius judder by roughly 73-82% while preserving the clean fixture/golden bars, but it did not claim
to remove every small-bubble oscillation.

## Pre-candidate remaining code path

The surviving path identified before the B2 candidate was narrower:

1. `bubble.pulse_energy` still integrates raw `gated_energy` in `BubbleSimulation.tick()`.
2. `_small_render_pulse_factor()` reads that raw-derived pulse along with the render-only `_drawn_body_energy`.
3. Non-big bubbles bypassed `_apply_big_display_radius_smoothing()` completely: their `display_radius` was set directly to
   the current target radius. The B2 candidate now inserts only the bounded tiny presentation seam at this point.
4. The fragment shader has a representation boundary at roughly **4 physical pixels radius**. Below it a bubble is a simple
   filled dot; above it the normal outline/specular path is used.

Therefore the remaining investigation must identify whether visible alternation is:

- primarily raw small-bubble pulse sign flips;
- concentrated near the 4 px dot/outline boundary;
- concentrated in another tiny-radius band where a 1 px delta is a large fraction of the whole bubble;
- or a combination of those effects.

## Latest runtime evidence

The supplied 2026-10-05 combined frame trace covers roughly 434 seconds on screen 1:

- steady non-transition Visualizer draw rate: ~90.5/s;
- repeat draws: ~1.3/s;
- logical dt median: 11.09 ms;
- logical dt p99: 11.63 ms;
- 47 swap gaps >25 ms, classified as 35 GUI-starved, 4 render, 8 unattributed;
- largest swap gap: 249.4 ms.

The stalls are real shared-runtime defects and remain separately actionable, but the ordinary logical cadence/repeat profile is
healthy enough that it does not explain the persistent tiny 1-2 px radius vibration. Do not retune Bubble cadence to attack
this symptom.

## Operator physical-pixel idea

The operator proposed forcing a tiny grow/shrink of one or two pixels an additional pixel in the same direction, only for
bubbles that need it and never at min/max. The intent is useful: a tiny bubble should read as committing to a breath, not
hovering indecisively in the middle.

The **literal** rule must not be implemented first. The known failure can alternate sign frame-to-frame. Blindly adding another
pixel to both `+1 px` and `-1 px` changes would amplify the vibration.

The safe experiment is a render-only **directional micro-breath assist** after evidence identifies the affected radius band:

- non-big bubbles only;
- physical-pixel thresholds derived from the already cached committed Bubble viewport height (`_viewport_profile.height`),
  not a baseline-only constant;
- establish a direction before assistance;
- suppress/reject a one-frame small reversal caused by chatter instead of magnifying it;
- optionally add at most a bounded ~1 physical px in an already established monotonic direction when the natural visible
  step is sub-perceptual;
- never assist at a local min/max/clamp, pop/exit, or a strong edge that should immediately take raw authority;
- no new audio smoothing, timer, worker, poll, simulation state authority or per-mode scheduler.

Because the snapshot already loops over the active Bubble population and viewport geometry is cached, the intended implementation
can remain O(1) arithmetic/comparisons per affected bubble and zero cost while Bubble is inactive. Measure rather than assume.

## Candidate now in the working slice

`BubbleSimulation._apply_tiny_breath_assist()` implements the narrow render-only experiment rather than altering Bubble's
audio or simulation lanes. It uses the cached committed viewport height, affects only non-big/non-promoted bubbles whose
displayed radius is <=8 physical px, and has these hard exits:

- pulse <=0.08 or >=0.92: raw render target;
- >=2.5 physical px target edge: raw render target;
- pop / exit / promotion: raw render target;
- `TINY_BREATH_ASSIST_PX <= 0`: exact raw negative-control path.

Within that band, the first <=2 px reversal of an established target direction is suppressed/attenuated for one sample.
If the reversal persists, the second sample is admitted as the real reversal. The displayed radius is never allowed to sit
more than one physical pixel from the current authored target. The assist is clamped to the authored target's side of the
shader's 4 px dot/outline boundary, so it cannot create a representation crossing on its own. A monotonic 0.35-2 px step
may receive at most one extra physical pixel per half-breath. A paused raw target immediately restores raw authority, so the
assist cannot remain parked beyond a completed breath. No timer, audio smoother, worker or second clock was added. Collision and movement remain on the authored
raw render-radius approximation so this experiment cannot feed back into Bubble physics.

Focused synthetic negative control in `tests/test_bubble_render_judder.py`:

- OFF target/output: `[4, 5, 6, 5.4, 6.4, 7.4]` px;
- ON output: `[4, 5, 7, 6.4, 6.4, 7.4]` px.

The replay analyser now also counts tiny-radius alternating runs and dot/outline-boundary runs, and can run an exact OFF/ON
comparison in one process. Run the committed broadband fixture first, then the operator's four canonical local recordings:
`balanced.jsonl`, `heavy1.jsonl`, `quiet_intro.jsonl` and `quiet_intro2.jsonl` in `logs/visualizer_recordings/`. Archived/derived
`*_vN` and `*_noevents` takes remain useful forensic references but are excluded by `recorded_clips()` and are not extra
acceptance-corpus members. The candidate is not accepted merely because the synthetic contract changes output; the real replay
numbers and physical feel still decide it.

Commands from repo root:

```text
python -m pytest tests/test_bubble_render_judder.py -q
python -m tools.visualizer_replay.bubble_judder --fixtures --clip broadband_noise --frozen --compare-tiny-assist --px-per-unit 300 --min-px 0.5
python -m tools.visualizer_replay.bubble_judder --compare-tiny-assist --px-per-unit 300 --min-px 0.5
```

## Acceptance bar

A candidate must:

- reduce the surviving noisy radius runs beyond `800bf70f18`;
- keep the existing Bubble golden/reactivity tests green without rewriting goldens;
- preserve clean impulse, beat-rate, ramp, step and silence metrics within the existing tolerance;
- not reduce attack, excursion, elasticity or loud-passage variation;
- introduce no visible hold band, delayed reversal, threshold pop or new dot/outline chatter;
- cost effectively nothing outside active Bubble and negligible work inside it;
- pass physical comparison on both displays with the operator's real songs.

If physical feel is worse, reject the candidate even if the numerical judder counter improves.

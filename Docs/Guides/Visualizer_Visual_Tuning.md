# Visualizer Visual Tuning: previewing, measuring and authoring toward a target

How to see what a visualizer actually draws while you build or tune it, and how to move it toward a target image
with measurements instead of guesses. Written from the Extruded Bubble (EB) fidelity work of October 2026; the tools
are EB's, the methods apply to any mode. Reactivity has its own guide
([Visualizer_Reactivity_Authoring.md](Visualizer_Reactivity_Authoring.md)); this one is about the picture.

## 1. Render the real thing, offscreen

Never judge a look from code, a lab, or a single mental model. Render production through the production host on
real recorded music, with no window and no settings writes:

```
.venv/Scripts/python tools/extruded_bubble_capture.py --output <dir> --clip logs/visualizer_recordings/<clip>.jsonl \
    --preset 4 --size 1672x941 --start 30 --duration 1 --fps 1 [--set extruded_bubble_<key>=<json> ...]
```

- `--preset N` renders a preset file as shipped; `--set` overrides any key for a trial without touching the file.
  Iterate on `--set` and write the preset only when the render is right.
- `--size 1672x941` matches the mocks, so crops line up. One frame at a loud moment (`--start 30` on ragdoll) is
  enough for composition and colour; use `--fps 24 --duration 10` for motion, encoded as WebP (quality 96 for
  sharing; frames are PNG in the output directory).
- `capture.json` records every frame's simulation scalars (count, rays, speed, emission...) and its GPU time.
- **GPU time:** the first frame of a run includes shader compiles and warm-up (hundreds of ms). Measure steady
  cost with `--duration 3 --fps 4`, twice, and read the median; compare against a control on the same machine
  state (absolute ms swing with clocks).
- Real windows are never opened by probes or tests (they freeze a blank screen).

## 2. Compare side by side, always against the target

Build a sheet per iteration: **mock | lab | ours**, one row per preset, at the same size. A scratch script that
renders presets (plus `--set` overrides) and pastes the three panels is worth writing first; read the sheet image,
then zoom: crop the same region of the mock and the render, and enlarge crops 3x (nearest-neighbour) when the
question is pixel-level (edges, aliasing, a bead's shading).

- **The lab is a waypoint, not the goal.** `tools/labs/extruded_bubble_lab.py` composes each scene by hand and came
  closest to the mocks first; reach it, then keep going toward the mock. Where the lab and the mock disagree, the
  mock wins.
- **When a transcription of a good recipe still looks bad, the gap is the world, not the values.** EB's presets
  were already the lab's recipes yet rendered far worse; the lab rendered at 62 degrees (presets 45), composed by
  on-screen size (production showed nothing under 18 px), drew deep-light rays with coverage off and kept its lights
  just outside the frame. Diff the lab's effective knobs against production's (`scene_knobs`) key by key.

## 3. Measure instead of eyeballing

- **Composition by on-screen size:** `python -m tools.visualizer_replay.eb_screen_stats --preset 3 4 --at 30 45
  [--set key=json]` replays the production simulation to those moments, projects every bubble through the
  production camera and counts bubbles per on-screen radius band (2-7, 7-18, 18-40, 40-85, 85+ px) and the fused
  share, beside the lab's composition. Author counts, sizes and emission until the bands match.
- **Water colour per region:** take a 3x3 grid of the mock and the render and compare each cell's 35th-percentile
  colour (bubbles and highlights excluded). It turned "too dark" into numbers: P3 was 5x too dark everywhere, P4/P6
  3-8x too dark below. Water colour drives the image non-linearly; halve the step after an overshoot.
- **Range behaviour on music:** `python -m tools.visualizer_replay.eb_control_audit --realized --preset 1 2` prints
  every preset's quiet / middle / loud values for each reactive control from one replay per song. Rank passages by
  a centred multi-second mean of intensity, never the instantaneous value (it snaps to 0 between beats).
- **Shimmer / stability:** draw the element at 16 sub-pixel offsets and compare its total light (a coefficient of
  variation; EB's tiny shells went from 20% to 1% by computing the antialiasing width analytically instead of
  `fwidth`, which fails on discs a few pixels across).

## 4. Prove what must not change

- **Accepted looks are pixel-identical, not "similar".** Render accepted presets at HEAD (`git stash`, render,
  `git stash pop`) and with the change, and require a zero max difference. New options default to the value that
  reproduces the previous look exactly (Bead Scatter 0, Light Tint at the former fixed share, Band Gathering 0,
  Doublets 0, Wake Trails 0, Floor 0); an option that is 0 must not even draw from a random stream.
- Simulation changes move every later frame, so pixel identity only holds for render-only changes; for simulation
  changes, assert behaviour with test-owned inputs instead.

## 5. Debugging a render

- **Nothing changed at all?** Diff the two renders numerically before reasoning about looks. A zero diff means the
  value never reached the shader (EB: trails had no camera uniforms; dust was hard-wired to 0 in the uniform map).
- **Black pixels or dashes:** look for NaN sources first: `pow` of a negative (interpolated strip coordinates
  overshoot their ends by a hair; clamp them), division by a derivative, `normalize` of zero.
- **A shader compile error** surfaces in the capture's stderr; run the capture directly to read it.
- **Heredocs mangle backslashes** (`\n`, line continuations). Write Python edit scripts with the Write tool.

## 6. Authoring rules learned

- **Accepted presets are not re-authored** (EB P1/P2, and P7 once accepted). New capability arrives as options;
  presets that want more opt in.
- **Range handles that cannot cross must not hold unrelated quantities** (a rest depth and a crest): give the quiet
  quantity its full effect by half way, so any rest pairs with any crest.
- **Lights read best just outside the frame**, their glow and fan sweeping in; an emitter disc in view rarely
  matches a mock.
- **Shared paths for related layers:** a wake's veil and its bead stream follow one path function, so the beads
  stream inside their veil. Two independent approximations of one thing never line up.
- **Attached elements follow their owner, not the music.** A wake steered by a global uniform (the live stream
  direction) swings with every musical turn while its bubble only drifts, and reads as detached; easing a per-trail
  direction is not enough either (its tail still moves on its own). Model the physics: a wake is the water the
  bubble passed through (EB `extruded_bubble_wake.WakePath`: sampled path history, dragged after the bubble a moment,
  then drifting with the water and smoothing out with age). Root it at the owner's own size (the bubble's lower sides).
- **Look at the goal at full resolution before choosing a technique.** EB's wakes were first drawn as soft blurred
  veils; the goal's are clear sheets with crisp glassy rims and fine lengthwise strands (caustic light drawn out
  along the flow). A blur cannot become that; edges and inner structure must be modelled. Shared optics apply to
  attachments too: a defocused bubble's wake takes the bubble's own near-defocus circle.
- **Every new control is authored into every preset** (`tools/visualizer_preset_repair.py --repair-all --mode
  <mode>` fills the default; then author the presets that use it). Tests never pin preset values.
- Record what was tried and rejected in the mode's Investigation log, with the measurement that decided it.

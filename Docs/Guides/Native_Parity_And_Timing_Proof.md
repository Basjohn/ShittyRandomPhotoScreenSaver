# Native parity and timing proof (Visualizer mode ports and optimisations; transitions: section 3's own list)

The method for proving that a native port, or an optimisation of one, loses nothing: no fidelity, reactivity,
smoothness or timing. It is also the long-term control. The stored references are rerun after a driver, Qt, compiler or
core change, and any drift shows up as a hash or timing change instead of an operator report.

Sources: the port rules and standard proof are in `Native_Port_Playbook.md` sections 1 and 2. The tolerance is D12
"The pixel tolerance" in `Docs/Future_Work/Native_Core_P3_Decisions.md`, through `tools/pixel_tolerance.py`. Bubble's
worked example is `Native_Bubble_Diagnostics.md`, "Optimisation gate". Bubble's temporal layers are in
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`. The open build work is `Current_Plan.md`, "Fast long-clip proof".
Decided with the operator on 17 Nov 2026, after Bubble's parity had been resting on a 5.5 s clip.

## 1. Four layers, each answering one question

| Layer | Question | How | Runs on |
|---|---|---|---|
| **L, logic and reactivity** | Does the native path receive exactly what the Python renderer uses? | Per frame, the packed record and settings must be byte-identical between the two paths. No rendering. | CPU only, every frame of every take and reaction mode |
| **P, pixels** | Is anything drawn differently? | Every frame is drawn and its readback hashed. Images are kept only for failing frames. Rule (a) is native OpenGL vs Python; rule (b) is Vulkan vs native OpenGL. | Hidden host, both backends |
| **T, timing and smoothness** | Is anything drawn later or less evenly? | Live cadence and presentation in the real process (section 4). | Invisible saver on Display 1, never Display 0 |
| **C, cost** | What does it cost? | GPU time per pass, median and p90 of 240 frames, with the GPU state and display state recorded. | Hidden host plus the invisible saver |

A hash cannot see timing, and a timing trace cannot see a wrong pixel. Every Visualizer mode port and every optimisation
needs all four layers, scaled as in section 3. A transition is not a mode: it needs fidelity and performance only
(section 3, "A transition port"); none of the mode material (recorded takes, reaction modes, coverage windows, layer
L, response tools, timing parity) applies to it.

## 2. Material: recorded music, never short synthetic clips

- **Takes:** three 60 s recorded takes chosen for distinct regimes: quiet intro to loud end
  (`ragdoll_quiet_intro_loud_end1`), sustained heavy (`human_heavy1`) and soft acoustic (`nightsolong_acousticsoft1`).
  `anything_mixed2` is the fourth when a port wants more. Bubble's port used all four. The takes are the operator's
  recordings in `logs/visualizer_recordings` (read only) and are driven through
  `tools/visualizer_replay/owner_render_parity.py --recording <take> --seconds 60`.
- **Frozen settings, exactly as set.** Adaptive ones stay on where a setting has them (Dynamic Floor, Adaptive
  Sensitivity, AGC). Each take runs continuously from a cold start, and its first and second halves are reported
  separately (`rule_a_halves`), because adaptive state drifts late.
- **Every reaction mode, separately.** A mode with several reaction modes (Waveform has four) runs each one over the
  takes; one reaction mode's pass says nothing about another's.
- **The 5.5 s Studio replay is a smoke check during development only, never a proof.**

## 3. How much to run

**A port.**
- **L:** every frame of every take and reaction mode.
- **P:** the Python reference hashes are rendered once per take, reaction mode and placement, then cached. The Python
  renderers are frozen until N5.2h deletes them, so the references never need re-rendering, except after a
  checklist-16 conversion (a port's decided change to the Python renderer): its references redraw once through the
  cache key, with stills before and after and the port's showcase WebP. Each native run renders
  only the native path against the cache.
- **Rendering defects found during a port:** reproduce the failure and fix it at the rendering boundary. Record
  the expected visual change and a control that distinguishes the correction from the defect. Use the corrected
  output as the reference and check unaffected paths for drift. After the Vulkan-default flip (NF), Vulkan is the
  primary acceptance target. Document OpenGL fallback limitations without carrying them into Vulkan output.
- **Coverage:** per reaction mode, one full 60 s take, plus coverage-selected windows from the other takes. L's
  records choose the windows: the extremes of each record field, the cold start, mode switches and fades, the loudest
  and quietest seconds, and reaction-mode changes. **Late-song windows are required:** every take contributes at
  least one window from its last 15 s, because adaptive state (Dynamic Floor, Adaptive Sensitivity, AGC) drifts
  most late in a song. Report each window's figures with its position in the take.
- **Adaptive state is never restarted inside a take.** A window is cut from one continuous run of the take from its
  cold start. The simulation, with all its adaptive state, ticks every frame from the take's first input, on the
  CPU and cheaply. Only the GPU drawing starts late, at the window's warm-up. A window whose simulation restarted at
  the window would see a cold floor and could pass where the real late song fails. A test proves the window's
  records are byte-identical to the same frames of the full continuous run, and a control that restarts the
  simulation at the window start must fail it.
- **Warm-up:** each window's drawing starts with a warm-up as long as the mode's GPU history (ribbons, rings, compute
  state, temporal buffers), stated per mode in section 5.
- **Proof of coverage:** a coverage report showing that every record field's observed range is covered gates
  acceptance.
- **Positional members are P's, not L's:** the members that place a draw in its window or target (the quad matrix,
  fragPixel's target, Spectrum's window maps) are outside L. Rule (a)'s pixels prove them on OpenGL at the display and
  overscan placements (and Spectrum's mapping control its maps); the stream player's rule (b) proves Vulkan at the
  harness's one placement only, so a Vulkan-only error at a fractional product placement is covered by no layer
  (checkpoint audit 9 L4).
- **Response:** the mode's own response tool (section 4's list; Waveform `waveform_music_response.py`, Neon Lake
  `neon_lake_music_response.py`) for every reaction mode separately, before against after, on the recorded
  continuous-play chain; also for any later change that touches the mode's simulation or its visible response
  (operator, 21 Nov: part of the fast proof for every mode). It is CPU only: run it in parallel with L, not after it.
- **T:** section 4, once at acceptance.
- **C:** per pass at 2560 x 1440 and 4K, on both backends.

**A transition port** needs fidelity and performance, nothing else (operator, 21 Nov).
- **Fidelity:** rule (a) and rule (b) through `transition_route_check.py` over the full canonical duration and
  several image pairs; no separate logic layer (the pixels prove it), no response tool, no reaction modes. The lead's
  transition rules (21 Nov, N5.2c; each constant in the harness carries its reason):
  - A 3D scene single-sampled (`N52C_RULE_A`): at most 1,750 one-level pixels a frame in groups of at most 28, nothing
    past one level: the translated packs and Python's compiler round a face's UVs and lighting within float error of a
    half level differently (measured worst 1,152 a frame and a group of 19, times 1.5).
  - A 3D scene multisampled is judged by rule (b) only (D8 point 1), and its rule (a) by its single-sampled form (the
    same geometry): the core draws its targets top row first and Python bottom row first, so the driver's 4x sample
    pattern, not symmetric under a vertical flip, lands mirrored and a slanted edge's pixel covers a different sample.
    The core's row order is not changed for it.
  - Jigsaw's single-sampled scenes also admit one flip a frame on a piece's outline (`JIGSAW_RULE_A`, as Surface
    Tension's): the two compilers put the outline either side of a pixel centre (measured one pixel, 12 levels).
  - Blinds' flat style is a fragment pass with its own scatter bound (`BLINDS_FLAT_RULE_A`: 192, measured 128 times 1.5).
  - A pose that is degenerate in Python itself is checked off it, never excused and never given a wider bound: Blinds'
    slats at 0.49 and 0.51 instead of 0.5 (a slat's side edge-on covers a row only by float error, and Python draws that
    row differently 1e-4 either side; at 0.4999 and 0.5001 the faces near edge-on still put 3,036 pixels a frame one
    level off at dpr 1.5).
  - Rule (b) admits the rasterisers' flips on geometry edges by name (`N52C_RULE_B`: at most 3 a frame, each isolated
    on an edge: Cube Turn's slanted silhouette, a Jigsaw piece's outline, a Cascade card's edge), as `BEAM_RULE_B`.
  - The lead's N5.2d rule (21 Nov; the operator: a transition need not match Python 1:1, closer is better for the 3D
    structure, so exactness past the guarded bounds is not chased): the piece-edge flip class, for the scenes of many
    small moving pieces with motion blur or trails (`N52D_EDGE_FLIPS_A` and `_B`, per transition and variant, 1.5 times
    the measured worst). Its cause is proved, not assumed: the core draws its targets top row first (F1), so a piece's
    edge within a rasteriser's sub-pixel snap of a pixel centre covers it in one frame and not the other, a whole edge
    row of a small piece at once; Python drawn upside down differs from itself by exactly the native frame's flips, and
    the native frame equals Python drawn in the core's frame. Vulkan and OpenGL snap differently too (rule b). The
    gather then smears each flip along the piece's motion. Guards: every pixel past one level lies on a moving piece edge
    of the reference (a 3 x 3 span of 4 levels or more where the reference differs from its frame a progress step either
    side; within 3 px: a trail outline's rim) or on its gather streak along the native velocity (at most 2K long); no
    compact group of differing pixels (one holding a full 7 x 7 square: wider than a 4 px tile's diagonal streak) past
    `N52C_SCATTER_GROUP`; at most `N52C_SCATTER_PIXELS` one-level pixels (their spread is the gather's); rule (b) also
    admits N52C's two-level ties off the edges (a trail's fade over a flat picture). A shifted piece, a patch, a colour
    shift or a streak across the motion fails (the harness tests' planted defects).
  - The gather-free forms (motion blur and trails off) are judged against Python drawn in the core's frame (`core_frame`;
    Python's own frame differs from it by the F1 flips alone, and Pixel Accretion's plain form then matches exactly). The
    lead's guard kept N52C's bounds for them; measured, they hold a few driver flips on moving piece edges that N52C
    admits none of (rule a: Crumble 1 tie, Glass Shatter 3; rule b, the 4x defaults: Crumble up to 16, Glass Shatter 7,
    Pixel Accretion 10), so they take the same class with their own counts (for the lead's confirmation, 22 Nov).
  - A vertex stage that writes its own clip depth after `uMatrix` (and every `sceneProject*` stage) ends with
    `native_clip_depth`'s line: Vulkan's clip depth is 0..w, OpenGL's -w..w (found on the ABI 37 build: half of every
    slab clipped). N5.2c's stages took it too; Depth Card Cascade with options then holds one frame of 4 card-edge flips,
    two touching, so its rule (b) is the piece-edge class (a card is a moving piece; `N52D_EDGE_FLIPS_B`, 6).
- **Performance:** C per pass at 2560 x 1440 and 4K on both backends (`transition_route_check.py --cost`, Crossfade
  the control). A scene transition's C is per record, not per pass: the core's GPU timer times the layer's whole record
  of the run (its photo environment's copy and chain at the run's first record, the scene's passes, the composite), so
  a scene's figure is the sum of its passes. Then one native Vulkan run for hitches and stalls (`preflip_pack.py --rows "transition/<id>/*" --name
  <post> --backend native-vulkan --app-arg=--graphics-backend=vulkan`, with `--per-row` for a one-transition session
  each). Read the row's hitch figures, never its fps or late %: the render thread's frame gaps inside each run (median,
  p90, max, the count over 33 ms; the startup reveal and the destination's handover lie outside the run's window, and its
  first frame is measured from the run's start), cut from the frame trace by the run's records (the native layer's tick
  and end records on Vulkan). The verdict is no gap over 33 ms inside a run, which includes no first-run compile stall.
  No pre-port baseline and no timing parity.
- Registration (offering it on Vulkan) waits for both.

**An optimisation of a landed port.**
- **No coverage sampling:** P hashes every frame of all three takes.
- **Native before against native after, per backend.** There is no Python render and no tolerance: any hash change
  fails, and byte identity is the acceptance.
- **L** reruns if the change touches the simulation, settings or packing. A logic change also needs Bubble's BTF
  section 24 lock, or the mode's equivalent, plus its response tools.
- **T** reruns whenever the change touches the render thread, uploads, synchronisation, threads or scheduling.
- **C** shows the gain.
- **A change that cannot hold byte identity** (reordered float math, half floats, merged passes) is tier 2: the shared
  tolerance plus the operator's sign-off, with the difference measured and shown.

**Which layers an optimisation needs, by what it touches:**

| Change touches | Required | Not sufficient alone |
|---|---|---|
| Shaders, passes, targets, buffers, culling (render only) | P on every frame, native before vs after, per backend; C; T when uploads or synchronisation change | coverage sampling |
| Simulation, settings, record packing (logic) | L, plus the mode's logic lock (Bubble: BTF section 24); P; the mode's response tools as support | music-response traces alone |
| Scheduling, threads, pacing | T; L and P unchanged | any offline replay |

**Every run states what it judged:** the number of frames or inputs judged against the number the material holds,
per half. A run that judged fewer than expected is a failed proof, not a pass: Bubble's first long run judged 337 of
5,503 inputs because the replay switched modes at 4.2 s. **A bound is measured on the acceptance material**, never on
the smoke clip: Bubble's scatter bound, measured as 34 on the 5.5 s clip, reached 45 on the long takes.

**After acceptance, proofs are regression guards, not confetti** (operator, 21 Nov). A change to the shared core
(C++, the route, the packet ABI) re-proves only the modes it is likely to touch: name them, with the reason, before
the run. A mode the change cannot reach is not re-run. An all-mode run happens only after major work (a whole port, a
3D mode) or a change with a likely knock-on effect on every mode (a shared pass, target or blend change), never after
every C++ change. Parity is not re-measured on accepted modes; a guard checks they did not move (native before
against native after, hashes, `--accepted`).

**The backstop for guards-only** (lead, 21 Nov): because a change judged unable to reach a mode may still reach
it, one full gate over every accepted mode and transition runs once before the flip (NF), unattended by the lead:
one full take per mode per backend with `--accepted`, every transition's pack row. Not before, not per change.

**Gates in general.** The lead runs batch gates unattended in the background, with references and native runs in
separate processes and several takes at once. An agent runs its gate in the foreground (agents run nothing in the
background), one process per take, at most the number its brief states at once, each under its timeout. A full gate runs at acceptance and once per batch of optimisations, never once per
candidate.

## 4. Timing and smoothness (layer T)

An offline replay steps at a fixed dt, so it never shows a stall, a sync point, a late upload or a cadence change. T
measures the real process:

- **The live run:** `tools/visualizer_live_check.py --mode <id> --preset <n> --seconds 90 --load none` drives the
  invisible Dashboard saver on recorded music, on Display 1. It gives frame-time median and p90, late frames, and Tick dt
  gaps. It is compared against the pre-flip baseline with `tools/preflip_pack.py --compare`
  (`tools/baselines/preflip/`). The `--usage` sampler's cost is part of the live shape (compare its collect_ms against
  the stored baselines).
- **Frame traces:**
  - `tools/frame_trace_report.py` gives the steady and post-lifecycle lines. Startup and teardown spikes are by design
    and are not counted.
  - `tools/frame_trace_cadence.py` gives presentation cadence per second and screen: publications, draws, and repeated
    draws of a revision already drawn, where a stall shows as repeats. It also shows the repeat rate while a
    transition renders.
- **Cadence:** `tools/visualizer_replay/cadence_parity.py` checks reaction, smoothness and elasticity at other
  logical cadences, when a change touches the logical clock.
- **Per-mode smoothness tools, where a mode has one:**
  - Bubble: `bubble_judder.py` and `bubble_breathing_continuity.py`.
  - Waveform: `waveform_music_response.py`.
  - Neon Lake: `neon_lake_music_response.py`.
  - Extruded Bubble: `extruded_bubble_music_response.py` (on-screen speed by bubble age through the preset's camera,
    under the take's PCM envelope).
  - A mode without one gets one only when its port finds a smoothness question. The music-response traces are evidence
    of reactivity shape, never the only proof.
- **Load:** game60 is the operator's yes each time, at most 10 minutes, lead only, and the rare end-of-chain
  worst-case proof. Display 0 is never used.

**Load during layer T.** The operator's modest load (a game, normal use) is fine and recorded with the figures. Other
agents' parity or judge runs are not: eight parallel owner replays took the machine to 93-97 % CPU on 21 Nov and
made a Bubble A/B unreadable. Check the whole-machine CPU before a T run (`Get-CimInstance Win32_Processor`), and
rerun any T run that ran above about 40 %. The lead staggers agents' heavy runs and T runs, and briefs say how many
parallel replay processes an agent may start.

The acceptance figures:
- Frame-time p90 no worse than the pre-flip baseline beyond its run-to-run spread (stated with the figure).
- No new late frames in steady state.
- No dt gap above the mode's cadence budget after the reveal.
- The mode's own smoothness tool unchanged.

## 5. The remaining ports

| Port | Reaction modes or variants | GPU history to warm | Its own T tool | Notes |
|---|---|---|---|---|
| Oscilloscope (N5.1) | its variants | glow history (bloom per frame) | the live run | First consumer of N3.4 bloom; the glow strength is per frame. |
| Waveform Ribbon (N5.4) | four reaction modes, each run separately | ribbon history buffer, rings, five compute passes | `waveform_music_response.py` | The heaviest coverage case; the reason for the fast proof. |
| Extruded Bubble (N5.6) | its emission modes (SCENE: variants a and b; BEAM), Sunlit and lighting BEAM | the drift state, integrated from the cold start (a gap past 128 steps restarts it): compute every input, draw from the window | `extruded_bubble_music_response.py` | Heavy render; less variance, so coverage windows are fewer. |
| Neon Lake (N5.5) | its variants | reaction and growth arrays, terrain | `neon_lake_music_response.py` | Persisted id `shockwave_grid`. |
| Extruded Spectrum, Sphere (N5.3) | their variants | none beyond the frame | the live run | Meshes, lighting, silhouette shadows. |
| Transitions (N5.2) | not a mode: fidelity and performance only (section 3) | none | none (one Vulkan hitch run) | Full canonical duration over several image pairs; no music, no layers. |

A mode port's brief names this guide plus the playbook. Its plan box lists its four layers' commands and states its
warm-up length before dispatch.

## 6. The long-term control

Each accepted port keeps:
- its Python reference hashes and its native hashes per backend (in evidence, beside the owner reports);
- its T figures;
- its C figures.

Spectrum, Spline Curve and Bubble are accepted (operator, 17 Nov). Their four-take hashes are their reference. Rerun
the gate after:
- a GPU driver, Qt or shader-compiler upgrade: one full take per accepted mode per backend with `--accepted`; every
  take only for a mode whose hashes moved;
- a native core ABI change that touches drawing: only the modes section 3's regression-guard rule names;
- an optimisation: the mode it optimises.

An unexplained hash change after an upgrade is investigated, never re-baselined silently. A re-baseline is a lead
decision, recorded with its reason.

## 7. What exists and what is still to build

- **Exists:**
  - `owner_render_parity.py --references-only`: a mode's cached Python references drawn before it has a native route
    (port preparation; the same key, so the port's first native run reads them);
  - `owner_render_parity.py`: `--recording`, frames spilled to disk, the switch moved to the end of a clip,
    `rule_a_halves`, `failed_frames` (only the first eight are listed in detail);
  - the per-mode `*_check.py` harnesses (rule (b));
  - `pixel_tolerance.py`;
  - `engine_worker_gate.py` (layer L's precedent: the worker against the in-process tick, frame by frame through the
    packet ABI, on the recordings);
  - `preflip_pack.py`, `visualizer_live_check.py`, `frame_trace_report.py`, `frame_trace_cadence.py`,
    `cadence_parity.py`;
  - the per-mode response tools and the Bubble diagnostics;
  - native Visualizer cadence in `visualizer_live_check.py` uses actual native content draws and their Qt swaps.
    `--frame-trace` observes the draw counter around Qt's native frame driver. It pairs only a draw and swap in the
    same display, generation and render cycle. The summary counts both, uses correlated swaps for FPS and
    within-window gaps, and reserves logical publication-to-swap age for evidence that carries logical revisions.
    A requested Visualizer measurement over a nonempty steady window fails if no correlated swaps occurred.
    The failed report still writes its summary and keeps its trace.
- **To build** (`Current_Plan.md`, "Fast long-clip proof" and "Bubble optimisation proof gap"):
  - a profile of the replay's time;
  - layer L for the native record;
  - cached Python references;
  - a native-only, hash-only compare with `--api opengl|vulkan`;
  - coverage selection with its report;
  - all failing frames recorded, not the first eight;
  - layer T's native per-pass GPU time from `--gpu-pass-timing`;
  - progress output during a run, so a killed run keeps what it had.
- **Method proof** (Bubble, 21 Nov): the coverage windows caught input 22, the offer fade frame 337 and the one-level
  shift, every window frame hash-identical to the continuous run's, but missed the one-ulp shader change
  (`ulp_ring` flips 3 frames per full take, none in a window). A one-ulp change flips only pixels on a rounding
  boundary, and no record predicts those frames. Evidence: `.artifacts/evidence/native_core/fast_proof/20261121_method_*`.
- **The split this sets (lead, 21 Nov):** what changed decides the material.
  - A mode's own shader or optimisation change, and every port's acceptance: a native-only run over each full take
    of that mode. A shared core change on accepted modes is a regression guard (section 3): one full take per mode it
    is likely to touch, with `--accepted`, never every take of every mode. Either way every frame is judged against
    the cached Python references (a frame hash-identical to the accepted native baseline needs
    no rejudge). Coverage windows never stand in for this. The run: `owner_render_parity.py --native --recording TAKE
    --seconds 60 --references --accepted ACCEPTED.json`. Confirmed 21 Nov on Bubble, nightsolong, variant a: the
    accepted run is the full replay (399.2 s, Python drawn and stored); with `--accepted`, 57.6 s (all 5,266 judged
    frames hash-identical, kept); every frame judged against the cached reference, 208.2 s. Its controls are caught:
    `--shader-control ulp_ring` changes 2 frames on this route (2026, 2499), exactly the 2 rejudged; `--native-control
    shift` rejudges and fails all 5,313 Bubble frames with the switch and digests intact (R-243). Evidence:
    `.artifacts/evidence/native_core/fast_proof/20261121_split_*`.
  - Python references: drawn once per take on the full continuous run and cached; redrawn only when their cache key
    changes. The slow full-path replay (Python drawn alongside) exists only to draw or redraw them.
  - Coverage windows: for record- and settings-driven classes (settings sweeps, offers, partner and switch frames),
    where a full take per setting is unaffordable; the late-song window stays required.
  - Take length (operator, 22 Nov, after N5.4's runs): the per-reaction-mode, per-placement and control runs of a
    mode use 30 s of each recorded take (`--seconds 30`), not 60; the late-song window stays required and is taken
    from the take's end, so adaptive drift is still covered. Full 60 s takes remain only where this guide names an
    acceptance or regression-guard take.
- **Once proven, it is the default** (operator, 20 Nov). After the fast tools pass their identical-verdict check and
  the method proof above, every port and every optimisation uses them: the cheaper judge, cached Python references,
  native-only hash runs and coverage windows, each for what the split above gives it. The slow full-path replay
  stays only to draw references. The tools are kept long term as the optimisation parity aid and the control in section 6, and
  are never retired as "temporary".

### Compact fast-proof and mode evidence (23 Nov 2026)

The portable archive compresses 442 MB of receipts to 131 MB. It retains the fast-proof method and controls, Waveform
logic and parity results with raw timing traces, and Spectrum and Spline long-take comparisons. It includes per-frame
hashes, verdicts, selected failure crops, applied settings and available resource samples. Original paths distinguish the
historical and native Waveform runs. The Extruded Bubble entries are reference-preparation receipts.
[Proof archive](../../.artifacts/evidence/native_core/fast_proof_compact/20261123_method_and_mode_proofs/fast-proof-method-and-modes.zip)

The verified manifest hashes all 1,218 source files plus the README and omission index. `omissions.json` records exact
paths and sizes for the large frame buffers, cached frame and mask files, and full copied profiles that remain in place.
The cache keys and `reference.json` indexes are in the archive. The cache data stays under `D:/Temp/Scratch/SRPSS/fast_proof/references/`.
[Archive SHA-256](../../.artifacts/evidence/native_core/fast_proof_compact/20261123_method_and_mode_proofs/fast-proof-method-and-modes.zip.sha256)

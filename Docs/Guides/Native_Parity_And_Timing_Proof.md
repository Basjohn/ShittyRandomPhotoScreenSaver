# Native parity and timing proof (every port, every optimisation)

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

A hash cannot see timing, and a timing trace cannot see a wrong pixel. Every port and every optimisation needs all
four layers, scaled as in section 3.

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
  renderers are frozen until N5.2h deletes them, so the references never need re-rendering. Each native run renders
  only the native path against the cache.
- **Coverage:** per reaction mode, one full 60 s take, plus coverage-selected windows from the other takes. L's
  records choose the windows: the extremes of each record field, the cold start, mode switches and fades, the loudest
  and quietest seconds, and reaction-mode changes.
- **Warm-up:** each window starts with a warm-up as long as the mode's GPU history (ribbons, rings, compute state,
  temporal buffers), stated per mode in section 5.
- **Proof of coverage:** a coverage report showing that every record field's observed range is covered gates
  acceptance.
- **T:** section 4, once at acceptance.
- **C:** per pass at 2560 x 1440 and 4K, on both backends.

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

**Gates in general.** Gates run unattended in the background, with references and native runs in separate processes
and several takes at once. A full gate runs at acceptance and once per batch of optimisations, never once per
candidate.

## 4. Timing and smoothness (layer T)

An offline replay steps at a fixed dt, so it never shows a stall, a sync point, a late upload or a cadence change. T
measures the real process:

- **The live run:** `tools/visualizer_live_check.py --mode <id> --preset <n> --seconds 90 --load none` drives the
  invisible MC saver on recorded music, on Display 1. It gives frame-time median and p90, late frames, and Tick dt
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
| Extruded Bubble (N5.6) | its variants | drift compute, defocus, transparency (OIT) | its response comparison | Heavy render; less variance, so coverage windows are fewer. |
| Neon Lake (N5.5) | its variants | reaction and growth arrays, terrain | `neon_lake_music_response.py` | Persisted id `shockwave_grid`. |
| Extruded Spectrum, Sphere (N5.3) | their variants | none beyond the frame | the live run | Meshes, lighting, silhouette shadows. |
| Transitions (N5.2) | each transition | per transition | the session pack (`preflip_pack.py`) | Full canonical duration over several image pairs; no music. |

A port's brief names this guide plus the playbook. Its plan box lists its four layers' commands and states its
warm-up length before dispatch.

## 6. The long-term control

Each accepted port keeps:
- its Python reference hashes and its native hashes per backend (in evidence, beside the owner reports);
- its T figures;
- its C figures.

Spectrum, Spline Curve and Bubble are accepted (operator, 17 Nov). Their four-take hashes are their reference. Rerun
the gate after:
- a GPU driver, Qt or shader-compiler upgrade;
- a native core ABI change that touches drawing;
- any optimisation.

An unexplained hash change after an upgrade is investigated, never re-baselined silently. A re-baseline is a lead
decision, recorded with its reason.

## 7. What exists and what is still to build

- **Exists:**
  - `owner_render_parity.py`: `--recording`, frames spilled to disk, the switch moved to the end of a clip,
    `rule_a_halves`, `failed_frames` (only the first eight are listed in detail);
  - the per-mode `*_check.py` harnesses (rule (b));
  - `pixel_tolerance.py`;
  - `engine_worker_gate.py` (layer L's precedent: the worker against the in-process tick, frame by frame through the
    packet ABI, on the recordings);
  - `preflip_pack.py`, `visualizer_live_check.py`, `frame_trace_report.py`, `frame_trace_cadence.py`,
    `cadence_parity.py`;
  - the per-mode response tools and the Bubble diagnostics.
- **To build** (`Current_Plan.md`, "Fast long-clip proof" and "Bubble optimisation proof gap"):
  - a profile of the replay's time;
  - layer L for the native record;
  - cached Python references;
  - a native-only, hash-only compare with `--api opengl|vulkan`;
  - coverage selection with its report;
  - all failing frames recorded, not the first eight;
  - layer T on native paths: on Vulkan the native core draws inside Qt's frame and writes no Python draw or swap
    records, so `visualizer_live_check.py` reports `frames_per_s 0` and no render or swap figures (20 Nov, Bubble).
    It must derive presentation cadence from Qt Quick's frame-cycle events (`quick_before_frame_begin` intervals,
    lifecycle windows excluded), and per-pass GPU time from `--gpu-pass-timing`;
  - progress output during a run, so a killed run keeps what it had.
- **Method proof:** on Bubble, the coverage-selected set must catch every failure the full four-take run found
  (input 22, the two offer fade frames, a one-level shift control, a one-ulp shader change) before Waveform relies
  on it.
- **Once proven, it is the default** (operator, 20 Nov). After the fast tools pass their identical-verdict check and
  the method proof above, every port and every optimisation uses them: the cheaper judge, cached Python references,
  native-only hash runs and coverage windows. The slow full-path replay stays only as the fallback for a mode where the
  method proof fails. The tools are kept long term as the optimisation parity aid and the control in section 6, and
  are never retired as "temporary".

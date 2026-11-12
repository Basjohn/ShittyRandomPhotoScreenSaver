# Benchmarks and lifecycle checks

How to measure what a transition or Visualizer mode costs, how to tell a real change from a busy
machine, and what results to expect. Everything here runs headless: one offscreen OpenGL context,
no window, no runtime. Related: `Docs/Guardrails/Performance_Optimization_Contract.md` (when a
baseline is required), `Docs/Reference/Harness_Index.md` (all harnesses), `Docs/TestSuite.md`.

**Note (12 Nov 2026): baselines predate Qt 6.12.0 (12 Nov); re-baseline before comparing.**

| Tool | Answers | Typical run |
|---|---|---|
| `tools/overhead_baseline.py` | What every showcase transition and Visualizer mode costs, before and after a change | 4-8 min (all), seconds (`--match`) |
| `tools/visualizer_cost_probe.py` | What one Visualizer mode costs with given parameters | ~10 s |
| `tests/test_transition_lifecycle_contract.py` | Whether warm-up, park and release keep their contract (no timing) | ~6 s |
| `tools/gl_object_ledger.py` | Which GL objects are alive (used by the contract; usable in any harness) | n/a |

## Running

```
python tools/overhead_baseline.py --size 2560x1440                                   # full baseline
python tools/overhead_baseline.py --size 2560x1440 --compare tools/baselines/overhead/<older>.json
python tools/overhead_baseline.py --size 2560x1440 --match liquid_lens --compare <older>.json   # one effect
python tools/overhead_baseline.py --compare-only OLD.json NEW.json
python tools/visualizer_cost_probe.py shockwave_grid shockwave_grid_glow=0.8 --size 2560x1440 --calls
python -m pytest tests/test_transition_lifecycle_contract.py
```

- Use **2560x1440** (or the display you care about). At small sizes the control costs a few
  microseconds, timer granularity dominates and the relative GPU figures are meaningless.
- A full baseline writes `tools/baselines/overhead/<date>_<commit>.json`; commit it when it is the
  reference for later comparisons. A `--match` run writes `<date>_<commit>_<match>.json`, compares
  only the cases it measured, and is normally not committed.
- **When to record one** (the contract's rule): before and after any shared-primitive or render-host
  change. Record the "before" on the parent commit, the "after" on yours, and `--compare` them.
- Close games, video and other GPU work if you can, and check nothing is left over from earlier
  load tests before calling a run quiet. The run reports what else was running anyway.

## What is measured, and why it holds up on a busy machine

Each sampled frame is rendered three times, each time right after a **control**: one fixed
Crossfade frame drawn eight times. Only the fastest repeat of each counts, then the median over
frames (48 by default, spread over the run's progress). Cases run **round-robin** on one shared
context, so a burst of outside load spoils one pass of many cases rather than every pass of one.
A pass whose control GPU time ran more than 35% over the controls' lower quartile shared the GPU
with something else; it is rejected and the case is measured again in a later round (up to
`--max-rounds`). The machinery lives in `tools/bench_stability.py` (`PairedBench`, `BenchCase`,
`LoadGate`, `ThreadCpuClock`, `SystemSampler`).

Every case is recorded three ways:

- **Absolute** milliseconds: `gpu_median` (`GL_TIME_ELAPSED`), `cpu_median` (wall time of the render
  call) and `cpu_thread_median` (the render thread's own CPU time, `QueryThreadCycleTime`, which
  preemption by other processes does not inflate).
- **Relative**, in **Crossfade frames (cf)**: `gpu_rel` and `cpu_rel`, the case divided by the
  control measured beside it. GPU clock state, contention and a busy core's slowdown move case and
  control alike and cancel. **Compare runs on these.**
- **Deterministic counts**: `gl_calls` (every OpenGL call per frame) and `py_calls` (Python function
  calls per frame). They do not move with load at all: any rise is real added per-frame work.

System conditions are sampled after every pass (other processes' CPU, memory, GPU busy, graphics
clock, temperature; GPU figures need `nvidia-smi`) and recorded per case (`env`) and per run (`load`).

## Reading the output

```
  transition liquid_lens/default   gpu  0.042 ms =   5.13 cf  cpu  0.258 ms =  1.30 cf  noise   2%  admitted 3/3  gl    58  py  406.5
  load: 93/154 passes admitted; control GPU quiet 0.009 ms, range 0.008-0.035 ms, wall CPU 0.080-0.196 ms
  conditions: other processes' CPU median 3.3% (max 18.8%), memory 55.5%, GPU busy 21.0% (max 100.0%), GPU clock 1785.0 MHz, 41.5 C
```

- `gpu ... ms = ... cf`: absolute GPU median, then the same in Crossfade frames.
- `cpu ... ms = ... cf`: the render thread's CPU time, then relative.
- `noise`: the spread of the case's admitted pass medians (relative GPU). Below 10% is normal for
  anything costing 0.05 ms or more; cheap cases (under ~0.03 ms) show large noise because the
  timer, not the work, dominates.
- `admitted a/b`: admitted passes out of passes run. Needing more passes than `--passes` means the
  GPU was shared during some of them.
- `load` / `conditions`: the run's admission and what else the machine was doing.

A comparison prints both runs' conditions, warns when they differ enough to mislead (other
processes' CPU by 15 points, GPU busy by 15, GPU clock by 150 MHz, temperature by 10 C), warns
when the old baseline predates the relative method, and then flags only:

- a GPU rise beyond `max(20%, 0.05 ms, twice either run's noise)`, judged on relative figures;
- a CPU rise beyond `max(50%, 0.15 ms, twice the noise)`: a hint, not proof (see limits);
- **any** rise in `gl_calls` or `py_calls`: real added work, whatever the conditions.

## Expected results

Measured 2026-10-11 on an RTX 4090 at 2560x1440 (`tools/baselines/overhead/2026-10-11_fea39fd6.json`;
1 cf there was about 0.018 ms of GPU and 0.077 ms of thread CPU):

- **Same code, two runs: "no regressions".** Between a run under full CPU load at a 540 MHz GPU
  clock and a quiet one, relative GPU figures agreed within 8% for 90% of cases (absolute ones moved
  by up to half); between two quiet runs whose GPU clocks were 1410 and 1785 MHz, nothing was flagged.
  The latest reference, `2026-10-11_ffa71024.json`, was recorded with other processes using 42% of
  the CPU and the GPU 73% busy; compared with the quiet `2baf6568` run it flagged only the intended
  call-count changes (the shared one-program renderer's +2 Python calls, the Liquid Lens redesign) and
  no timing on any untouched transition or Visualizer mode.
- **Relative CPU** still moves up to about 30% between busy and quiet runs (CPU power states and
  SMT siblings slow the thread itself), so CPU flags are hints; call counts are the proof.
- **Admission**: 60-100% of passes on a working desktop; much lower means something was competing
  for the GPU the whole time (the relative figures still hold; the absolute ones do not).
- **Counts** are identical from run to run and from size to size.

Reference figures (relative GPU in cf, thread CPU in ms, counts per frame):

| Case | GPU (cf) | Thread CPU (ms) | GL calls | Python calls |
|---|---|---|---|---|
| Crossfade | 0.66 | 0.078 | 49 | 301 |
| Wipe | 1.07 | 0.150 | 50 | 306 |
| Liquid Lens (2026-10-11 pitstop design) | 5.13 | 0.10-0.26 | 58 | 406 |
| Jigsaw Piece Flip | 6.59 | 0.281 | 119 | 863 |
| Exploding Tiles | 10.85 | 0.444 | 170 | 1055 |
| Melt / Drip | 21.00 | 0.094 | 50 | 369 |
| Particle | 152.4 | 0.145 | 65 | 385 |
| Spectrum | 2.40 | 0.183 | 17 | 754 |
| Sphere | 6.86 | 0.394 | 78 | 1473 |
| Shockwave Grid (flat scene before Neon Lake) | 15.89 | 0.429 | 146 | 1883 |
| Oscilloscope | 144.0 | 0.325 | 17 | 1768 |

Every transition's own steady cost is recorded beside it in `Docs/Reference/Transitions.md`.

Neon Lake's foundation reference is `tools/baselines/overhead/2026-10-13_6a63dcda.json` at 960×540, compared
with `2026-10-13_000e222e.json`. All unchanged consumers retained their deterministic call counts. Neon alone added
its new scene work (146→180 GL calls, 1883→2256 Python calls); its control-relative GPU equivalent rose from 0.190 to
0.243 ms under different GPU clock conditions. These are foundation measurements; later optional point/celestial
features require their own focused measurements, not attribution to unchanged consumers.

## Lifecycle contract (no timing)

`tests/test_transition_lifecycle_contract.py` holds every showcase transition (new ones join through
the release-media catalogue) and every Visualizer mode to the lifecycle rules, counted by the GL
object ledger:

- once warmed (geometry prepared as COMPUTE does, warm steps run to completion) a run's frames
  create no GL object: no compile, texture, buffer or target on a visible frame;
- what `park()` keeps is the same whatever the run (three runs, three seeds);
- `release_resources()` deletes every GL object the renderer created;
- cycling every Visualizer mode holds only the current mode's objects, and release frees all;
- rounds of every transition retain no Python objects: no object type's count rises in every one of
  four rounds (a single leaked ctypes type per Crossfade run is caught).

Expected: all pass, in about six seconds, on any machine and under any load. A failure names the
transition and what it created or kept.

## Limits

- Offscreen timing is not presentation timing: compositor, vsync, the second display and the
  runtime's own work are absent. Physical acceptance stays a separate gate.
- GPU costs under ~0.03 ms are timer-bound; their GPU deltas sit under the 0.05 ms flag floor.
- CPU timings are hints (see above); a rise in `py_calls` or `gl_calls` is the evidence.
- The control is Crossfade: a change to Crossfade itself shifts every relative figure together;
  that shows as every row moving the same way.

## Recorded sessions (moved from `Current_Plan.md`, 11 Nov 2026)

**7 Nov quiet-machine session** (stopped early by the lead; receipts under
`.artifacts/evidence/performance/quiet_session/20261107_quiet_session/<task>/receipts.md`). Owed re-runs are on the
plan (§3, "Lead, the quiet machine").

- **Overhead baseline** (`tools/baselines/overhead/2026-11-07_4bb2b775.json`). Against 123e1209 every Visualizer
  gains +46 Python calls a frame, arriving exactly at efea1304 (AC-08's `rendering/quick/gl_query.py`): not a
  regression (Spectrum 757 -> 803, Extruded Spectrum 1179 -> 1225; AC-12 adds none; each wrapper call replaces a
  PyOpenGL checked getter, about 2.7 us against about 13 us a query; control-relative render CPU fell: Spectrum
  2.04 -> 1.26 cf, Extruded Spectrum 3.29 -> 2.12 cf). GL calls and control-relative CPU are flat. Burn's +14 Python
  calls a frame (AC-20's per-frame spec lookup) were fixed in 0b3048b6 (407 again).
- **M0 Extruded Bubble baseline** (`2_m0_eb_baseline/`): four views (canonical, wide, tall, display) x idle/game60 on
  one monitor, plus canonical and display on two monitors. Only the display-sized view moves: under game60 its render
  mode is 8.2 ms against 4.4 at the card (over the 8 ms budget of the Expanded Visualizer plan §0.7) and fps 64
  against 73. Tick (5.1 ms game60, 2.7 idle) and GIL do not depend on size.
- **Waveform tick cut under game60** (`3_waveform_tick_cut/`, one clean round): main against `946e14b3^` tick -5 to
  -10 %, fps +6-12 % on P1/P4/P7. Indicative only (confounded by the other 193 commits). Waveform stays far over
  budget under game60 (GIL > 0.7, render 16-21 ms).
- **Waveform follow-ups merged the same day:** the music-vs-response check found no mid-song kick muted (Group Wave
  shows single kicks least; Whole Swell plateaus on flat loud songs, which reads as sustained). Floor first: the lift
  limit went from 1.5 to 3 and the top takes back at most 1.5; floor contact at 1282x1005 fell from 7-49% to 0-2.2%
  with no crest above the top. Evidence:
  `.artifacts/evidence/visualizers/waveform_ribbon/followups/20261107_followups/`.
- **GC freeze steady check** (`4_gc_freeze_steady/`): Bubble P1, 600 s game60 clean: no steady gen1/gen2, heap 180,685
  objects frozen at reveal and 87 left.
- **11 Nov re-baseline** (`tools/baselines/overhead/2026-11-11_4658981b.json`, 1920x1080; other processes' CPU 16.4%
  median (max 47.8%), GPU clock 750 MHz, 114/114 passes admitted: only the counts are read). The Python-call rises
  since `4bb2b775` (same tree as `81959727` on the rewritten history), attributed by per-function call counts at
  chosen commits: Scene3D content rotation (`f6328336`: the target's output frame and its `getattr`s on every
  Scene3D transition and mode, +4 to +7), the framed horizontal cap (`0afc19cb`: Extruded Bubble's optical height
  re-imported `framed_camera` through PySide's import hook and re-solved the lens every frame, +26, ~2.7 us) and
  Waveform Preset 1's Left To Right travel (`50a43e0d`, authored content engaging the mirror path, +16). Fixed in
  `4658981b`: the target turns only a turned scene's frame, EB resolves its optical height on its edges, the travel
  mirror is a constant. Against 7 Nov the counts now read +2 in every Scene3D transition, Oscilloscope +3, Sphere +4,
  Extruded Spectrum +5, Extruded Bubble +3, Waveform Ribbon +15 (the authored mirror path). Neon Lake's 5684 -> 5313
  Python and 354 -> 361 GL calls (GPU relative 1.14 -> 1.44 ms) are `33912e5a`'s terrain growth and reaction tables,
  new mode work. Evidence: `.artifacts/evidence/native_core/20261111_attribution/`.
- **Load session, 11 Nov** (lead, game60, invisible saver, `anything_mixed2`, no agent running; other processes
  73-78 % CPU, GPU 61-66 % at 2760 MHz in every run; evidence under
  `.artifacts/evidence/visualizers/{waveform_ribbon,spectrum}/live_check/20261111_load_r*`):
  - Waveform Preset 4, engine worker: 59.4 fps, render mode 10.4 / 12.7 ms (median / p90), swap gap 15.9 / 20.2
    ms, 1.4 % late, 3.3 hitches a minute, frame take 0.76 ms, worker tick to publish 6.2 / 7.7 ms; first 2 s
    after startup 86 frames, 3.5 % late.
  - Waveform Preset 4, in process: 40.6 fps, render mode 14.0 / 17.4 ms, swap gap 24.0 / 29.0 ms, 37.7 % late,
    7.2 hitches a minute, logical tick 14.5 / 20.2 ms (7.1 ms CPU); first 2 s 69 frames, 75 % late.
  - One Settings round trip on the worker at 60 s: 7.8 s in all, stop 0.46 s, barriers complete, thawed and
    re-frozen, no failure; RSS 823 to 862 MB, private 1271 to 1171 MB.
  - Card materials, alternated second pair (Normal then Glass; Spectrum Preset 1; interval 8 s, 5 s random
    transitions; 90 s each): fps 89.5 / 89.6, late 0.2 % / 0.2 %, hitches 0.73 / 0.73 a minute, publish to swap
    10.8 / 11.6 ms median, saver tree 106.1 / 105.7 % of a core. No measurable Glass cost; the first pair's
    +16 % of a core (below) was one unalternated pair and did not repeat.
- **Card materials** (`5_card_materials/`, one Glass/Normal pair): Glass costs about +16 % of a core on the render
  thread (53.7 against 37.5), publish->swap +3 ms, hitches 2.46 against 2.05 a minute, at the same late %.

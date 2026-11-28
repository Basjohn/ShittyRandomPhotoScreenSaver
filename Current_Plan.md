# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). Remove completed work; retain only extremely brief, useful native-core reference boxes. Durable contracts live in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.
**Operator sequencing, 23 Nov 2026:** finish the Vulkan-native core/flip, Reactive Liquid / Audio Melt Pool,
Concrete Rain and a substantial operator-reviewed quality-of-life phase **before reconsidering SMP**. SMP is
deferred in `Future_Work.md` §2.5 and its complete plan 02; nothing starts merely because NF or a native primitive
lands. Independent current-product material/theme work, M4 Unified Appearance Theme and Theme Studio stay
active. **Cross-profile live Settings** is also an admitted **post-Theme-Studio, post-Concrete-Rain QoL**
milestone, not SMP work. Preserve SMP-compatible architecture without allocating SMP implementation work.

## 0. Scope and rules

**If you are the lead (orchestrator):** read `Docs/Guides/Orchestrator_Handbook.md` before anything else, and run `tools/agent_handover.py` to see every agent worktree, its journal and its unmerged work. Agents read `Docs/Guardrails/Agent_Worktree_Rules.md`, then their item here.

**Accepted baseline (not live work):** original Bubble, Extruded Bubble, Neon Lake (`shockwave_grid`),
Oscilloscope, Spectrum/Rainbow Ghost, Voxel Sphere (`sphere`), source routing, transitions and Foundry launch buttons. Reopen an accepted
area only for a concrete new defect; deferred or unadmitted work belongs in `Future_Work.md`. Historical recovery
IDs, completed gates and rejected mechanisms belong in source control or their focused historical/investigation docs,
not in this working plan.

**Rules:** one Settings/capability/CUSTOM/render/lifecycle owner and the sole Visualizer logical clock. No new
floor, capture/DSP, renderer-side simulation, timers/polling or camera-following replacement populations. Preserve
authored presets (mutable, never test-pinned), BTF, accepted timings, parallel work and strict retirement barriers.
CLI/sidecars, never environment-variable configuration. Smallest meaningful focused test per change; the
balanced, two-worker chunked suite only at milestones; file-isolated execution is opt-in diagnosis,
not a routine agent gate; no build/installer unless requested. Visual work is judged on rendered pixels against
its target (`Docs/Guides/Visualizer_Visual_Tuning.md`), and any claim of "fixed" needs the failure reproduced first.

**Linux compatibility** runs as a separate operator-requested plan, `Linux_Plan.md`; it does not reorder this plan.
New platform-facing work (power, display, input) still ships a basic Linux path or an explicit inert one alongside
the Windows path, so it never needs its own Linux audit later (operator, 5 Nov).

**Architecture checklist:** `Docs/Reference/Architecture_Checklist.md` (the 6 Nov audit, verified against source on
7 Nov: 16 items with severity, reward, effort, owning boundary, fix, regression bar). Its Tier 1 (AC-01 Settings tab
registry, AC-02 Visualizer host binding, AC-03 application-service tier) is the prerequisite work for step 7 below
(AC-01's contract: `Docs/Architecture/Settings_Bucket_Persistence_Contract.md`, "Tabs and pills: one registry"). The
items promoted to run soon are in §3. Nothing else in it is admitted until it appears here.

## 1. Order of work (strict)

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep `[~]`
validation steps and open side defects. **Load runs:** game60 at most 10 minutes in total, started by the lead only
after the operator's yes on a question card; agents never start load (invisible checks without load, at most 3 min); the operator's own running load is not a load run and is measured under (`Agent_Worktree_Rules.md`).

**State (17 Nov):** Spectrum, Spline Curve and Bubble are native and accepted (operator), and Bubble is offered on
Vulkan. ABI 25; N3.4 audited, its defocus investigation non-blocking. Every port and optimisation is proved by one
method, `Docs/Guides/Native_Parity_And_Timing_Proof.md` (layers L logic, P pixels, T timing, C cost); per-mode tools
are named in each mode's own guide (Bubble: `Docs/Guides/Native_Bubble_Diagnostics.md`).

**Operator priority (23 Nov):** take the Qt 6.12.1 patch when its four matching Python wheels are published
(checked 27 Nov: the 6.12.1 SDK is staged and verified; all four PyPI wheels still return 404, latest 6.12.0).
Continue the native sequence below with the repaired timing receipts. The reported EB response delay is in the Watchlist.

**Order (lead and operator, 17 Nov):**
1. Close Bubble (the N5.1 Bubble box, in its order): checkpoint audit 8's fixes; build the fast long-clip proof's layer L and
   layer P tools (the "Build the fast long-clip proof" box); then Bubble's layer L directly, layer T on both backends,
   rule (b) over the four takes, the 2560 x 1440 cost, and the D1 rehearsal.
2. Attribute Bubble's remaining switch-frame tie at input 337 under the current D12 rule (a). Use the post-fix
   Spectrum and Spline Curve long-take controls in the residuals section.
3. Bubble GPU optimisation under the guide (its box), alongside step 4.
4. Ports, each under the guide from its first brief: the Oscilloscope (N5.1), then Waveform (N5.4) under the fast
   proof's split (the guide's section 7: full-take native-only runs against cached references; windows only for
   record and settings classes), then Extruded Bubble (N5.6), Neon Lake (N5.5),
   Extruded Spectrum and Sphere (N5.3).

5. Everything else in this plan is backlog: operator defects (Item 1, sections 1B, 1C, 1D, 1A), hygiene, Studio and
   later mode work. A slot takes from it only when no native step above can use that slot (operator, 15 Nov:
   native core first in every slot). Within a backlog section, its own internal order holds. No other heading in
   this plan sets a global order.

**Resume here**
- [ ] Live agents and where their work is (keep current). 27 Nov:
  - **Opus High `a7a8666a093ef7d48`**: N5.6 "Native record and route", **ABI 46**. Worktree
    `.claude/worktrees/agent-a7a8666a093ef7d48`, branch `worktree-agent-a7a8666a093ef7d48`, journal
    `<worktree>/.artifacts/handover/JOURNAL.md`, evidence `<worktree>/.artifacts/evidence/native_core/n5_6/`. Stops at
    "ready for build". 28 Nov: sub-boxes 1 and 2 done on the branch (`e7c0764b3` ABI 46 hold, `8d635e313`
    arena, seqlock, drift-window stream); built from `8d635e31`, resumed. Second stop 28 Nov: `29cb8317c` (program,
    worker record, route settings), `950465ab3` (arena close), `3fd93cc3a` (ABI 46 hold round), `24893c036` (C++,
    **ABI 47 reserved for N5.6**: a glass pass may sample the owner's capture, live attachments still refused). The
    lead built `24893c03` (module in that worktree's `release/native_module/`); successor **Opus High
    `a29135bafeaab65bb`** (28 Nov), worktree `.claude/worktrees/agent-a29135bafeaab65bb`, branch
    `worktree-agent-a29135bafeaab65bb` (merges the first branch) retired from use at 213k; `14d763931` built on GitHub
    (module in its `release/native_module/`). Third **Opus High `ae9dbc46b60681ac3`** (28 Nov), worktree
    `.claude/worktrees/agent-ae9dbc46b60681ac3`, branch `worktree-agent-ae9dbc46b60681ac3` (merges the second), ABI 47,
    retired from use at 230k after L subset and coverage. Fourth **Opus High `ac0cda3c82727c8cd`** (28 Nov), worktree
    `.claude/worktrees/agent-ac0cda3c82727c8cd`, branch `worktree-agent-ac0cda3c82727c8cd` (merges the third), ABI 47:
    reference key, native player, P/T/C; signed-zero entry numbered R-254. Reference key `77ca27c7e`; defocus taps
    `89c3ceca8` (built); input-0 empty-geometry placeholder + mixed-blend refusal `29a844943` (C++), lens shift
    `5feae1bc0`, in-process drift arena `8bf270aa7`; tip `8bf270aa7` built 28 Nov. Retired from use at 244k.
    Fifth **Opus Medium `a45099502ac294d6b`** (28 Nov), worktree `.claude/worktrees/agent-a45099502ac294d6b`, branch
    `worktree-agent-a45099502ac294d6b` (merges the fourth), ABI 47: rule (a) on the build, R-258, rule (b) noise
    floor, deliveries and references, the rest of P/T/C, the two side defects below.
    Open side defects for the successor: `schema.DRIFT` is one per process (two EB displays reset each other's
    projector, worker path too); raw `threading.Thread` at `packet_mailbox.py:491` from this branch's `8d635e313`
    fails `test_policy_compliance`. Retire the earlier worktrees only after the merge.
    Fifth agent's result (28 Nov, retired at 218k; commits `9f08b7df8` listener thread, `e01f125b9` drift projector
    per stream, `4b5025f64` arena once per run, `212964995` R-258/R-256, journal `82064c643`, pushed; no C++).
    Evidence is under its `.artifacts/evidence/native_core/n5_6/`.
    Done:
    - input 0 draws on all four runs;
    - 7 deliveries regenerated (identical at L);
    - 30 references stored in `fast_proof/eb_n56_r251`;
    - scene depth kept (glass needs it);
    - lens shift adds no difference;
    - both side defects fixed.
    Failing, these are the three defects for the sixth agent, in this order:
    1. **Vulkan does not render the same EB frame twice.** FIXED by the sixth agent, `7a089950b` (no C++): the glass
       shader's marine-snow exit left `gl_FragDepth` undefined, so the depth test rejected snow at random. It now writes
       `sceneSphereDepth`; the `.qsb` files are rebaked, with an every-exit test. Two Vulkan runs are byte-identical on
       400 inputs. R-259.
       R-259 entry `c22cdaac2`. OpenGL after the fix: 324/400 frames still differ run to run (p50 254 px, mostly 1–7
       levels, two frames at 30/38) on speck glints. This is OpenGL-only and has a separate cause. Side defect for this agent after defect 3.
       Defect 2 FIXED `5396351bb` (C++, ABI stays 47): the cap is now the layer's whole chain less two (4K: 4→9), matching
       Python's full mip chain. The 15 Nov core-downsample line is superseded. Building 28 Nov.
       Built `85f1baf9`: forced level 5 and level 7 draw on Vulkan, where the old module drew black (no zoomed-in card
       or Python comparison yet). The sixth agent was retired at 197k (journal `582fc37fd`). References made before the snow
       fix carry the same random snow depth (Python draws the same shader), so **Sonnet `afdd41cbae2c31521`** is
       regenerating all 30 and rerunning P (human_heavy1 60 s, plus the smoke), measurement only. Then defect 3 proper
       and the OpenGL speck residual go to a fresh Opus Medium.
       Before the fix: On a 30 s delivery, 2,576 of 2,586 frames differ across two
       runs (median 68 px, up to 149 levels, isolated pixels on specks/snow). The OpenGL floor is median 0, max 3 px.
       Ruled out by reading: unzeroed compute storage and atomic append order. Untested: per-frame-slot Dynamic buffers
       in offscreen frames, and target padding read but never written. This breaks rule (b) and the proof guide's
       Vulkan byte-identity basis, so it comes first.
    2. **Read-level cap without margin.** At aperture 1 on the 4K expanded card (3840×2112, cap 4), the read level is
       exactly 4. A zoomed-in world reaches level 5 at about aperture ≤0.54, where native refuses and fades the mode out
       while Python keeps drawing (`20261128_scripts/aperture_cap.py`).
    3. **Rule (a) on the long take.** human_heavy1 60 s: 5,500/5,503 frames, max 168 levels, on bright speck glints
       and highlight discs; the smoke still shows 2–3 level ties in the near layer's blurred bubbles.
    Not done:
    - turned card (needs a card-rotation harness feature);
    - ABI 46 hold firing and the five approximations (coverage selections must be regenerated);
    - C (1440p/4K deliveries plus a cost round);
    - T (Display 1, the lead's, after the C++ settles);
    - the 15-run L set;
    - music response: human_heavy1 preset 1 youngest bubbles fell 0.91→0.73 against 22 Nov. Check after fix 3.
    N3.9 drift history was checked by reading only: nothing registers `on_state_lost` for EB.
    Sixth **Opus Medium `a5f086921473dd17e`** (28 Nov, own worktree, merges the fifth's branch): defects 1–3 above, then the not-done
    items in order.
  - **N5.2h Gate merged** 28 Nov (`f12427a2e`; Opus Medium audit, should-fixes done in `a49087e7c`, harness reds in
    `ce80c0eeb`); main built on GitHub at `421a16bd` (ABI 45). Its four worktrees retired; evidence in
    `.artifacts/evidence/native_core/n5_2h/`, journal `.artifacts/handover/n5_2h/JOURNAL.md`.
  - **Opus Medium `acd9164542fb33bfc`**: N5.2h "The switch" (28 Nov), worktree `.claude/worktrees/agent-acd9164542fb33bfc`,
    branch `worktree-agent-acd9164542fb33bfc`, ABI 45, journal `<worktree>/.artifacts/handover/JOURNAL.md`; caller
    list + production route `5c81280f4` (no C++), retired from use at 231k. Successor **Opus Medium
    `a5767acce80d30d07`** (28 Nov), worktree `.claude/worktrees/agent-a5767acce80d30d07`, branch
    `worktree-agent-a5767acce80d30d07` (merges the first): finish the route (9 red tests, window-free
    `test_quick_backend_owner`, degraded-display negative control, a failed live layer fades to the degraded display),
    then the backdrop against the blit. Done through the reference cache (`a7c321e82`: Python frames cached in
    `D:/Temp/Scratch/SRPSS/fast_proof/transition_references/`, cost baselines `tools/baselines/preflip/python_cost_*`,
    proof guide section 3 rule). Membrane/Volumetric Dissolve run-to-run difference traced to the NVIDIA GL driver's
    multisampled blending (≤1 level; raw-GL repro, Python too, 1-sample and Vulkan identical); lead decided the
    proof-guide rule (OpenGL MSAA frames judged against a two-run noise floor, byte identity on Vulkan/1-sample).
    Media tools capture natively (`e1dcbc83a`, `tools/native_transition_capture.py`; scratch strips match shipped,
    burn's shipped strip predates the current burn). Retired from use at 190k. Third **Opus Medium
    `ac5eb8a969947d272`** (28 Nov), worktree `.claude/worktrees/agent-ac5eb8a969947d272`, branch
    `worktree-agent-ac5eb8a969947d272` (merges a5767's and ac12d's): GL_INVALID_ENUM fix (C++), then the delete
    sub-box. N5.6's `89c3ceca8` built on GitHub 28 Nov (module in the ac0cda worktree). Done: GL_INVALID_ENUM
    (`e06691e3e`, C++: Qt 6.12.0 writes sampler state to multisampled textures on first bind; `gl_sampler_state.cpp`;
    building 28 Nov), delete slice 1 (presenter, bridge, blit backdrop, selectors; import guard
    `tests/test_python_route_deleted.py`); retired at 183k. **Sonnet Medium `a6b16aeef142dc895`** (28 Nov), worktree
    `.claude/worktrees/agent-a6b16aeef142dc895`, branch `worktree-agent-a6b16aeef142dc895` (merges ac5eb's): the
    remaining ~54 `TransitionCapture` callers → `NativeTransitionCapture`, delete `render_host.py` and the transitions'
    GL draw code, bench/overhead/conventions retargets, public bootstrap close, smoke tests, Docs/Reference, and the
    pre-existing red `afterRendering.connect` in `background_item.py`. Done 28 Nov (`90aea5034`, `e7cafe96b`,
    `0d7b757bc`, `30c44c194`, journal `48658e507`): all of the above. The four reference checks pass from the cache on
    both APIs, and the media, onboarding, overhead and conventions smokes ran. Lead merged ac5eb's sampler follow-up as
    `9caada852`. Side defects: `tests/test_native_scene_targets.py::test_the_admission_refuses_with_its_reasons` wording vs
    the f475358aa module (goes to the GL fix agent); `rendering/quick/scene3d` PhotoEnvironment/MotionTrails/trails may
    now be dead for transitions (the visualizers still use them; check before any deletion). Retired at 231k.
    **Opus Medium `ad3b55fdd7e2d3dcd`** (28 Nov, own worktree, merges a6b16's): GL_INVALID_ENUM fix (diagnosis in the switch box)
    and the admission wording red. Done, built `f9d4399e`, verified. **Sonnet Medium `aa7af460a1382fb30`** (28 Nov, own
    worktree, merges ad3b5's): the switch's Proof box minus D1 (only Display 0 on): route + `--cost` both APIs, hitch
    rows, isolated suite.
    Done 28 Nov (retired at 221k, branch pushed): route + cost PASS both APIs, hitch rows wait for Display 1, suite
    reds sorted (see the Proof box). **Opus Medium `aa3b364fd31f5d860`** (own worktree, merges aa7af's): the three
    switch-caused retargets + the exit-crash attribution. **Sonnet Medium `a47d806ed60c9ed51`** (own worktree from
    main): the 9 reds that predate the switch.
  - **Sonnet Medium `ac12d10542a75cc4a`** (28 Nov): switch point 4, `TransitionCapture` → `OffscreenRenderTarget`,
    worktree `.claude/worktrees/agent-ac12d10542a75cc4a`, branch `worktree-agent-ac12d10542a75cc4a` (merges a5767's).
    Done 28 Nov (`d2c26bcb6` tests + `OffscreenRenderTarget.upload_image`, `d84ee39ae` tools; 40 test files, 7 tools,
    outputs compared old vs new); stopped at 195k, merges with the switch. Left for the delete box: `bench_stability.
    crossfade_control` (used by `visualizer_cost_probe.py`, `bubble_particle_glow.py` perf) goes to a native crossfade
    control; `overhead_baseline.py`, `conventions_identity.py` and the transition-drawing `test_qtquick_*`/
    `test_transition_*`/mixed scene3d cases retarget to the native route or go. Side defects (pre-existing, both fail
    identically on old code), both fixed and merged 28 Nov (`e895f7680` stale assertion after `994beba7f`; `2472a342d` probe never fed `aLensRadius`): `tests/test_extruded_bubble_trails_background_gpu.py` (`eb._glass(...)` has no
    `uBackground`); `tools/visualizer_replay/extruded_bubble_coverage_probe.py:103` `min()` of an empty array.
  - Qt 6.12.1 wheels: all four still 404 on PyPI (checked 27 Nov, this session).

  All six retained worktrees are clean, detached and merged into main:
  - `C:/Users/Basjohn/.codex/worktrees/` `dashboard-naming`, `eb-compute-binding-limit` (N5.6 evidence, 1.5 MB),
    `eb-optical-reference`, `native-mat3-packing` and `native-viz-timing`;
  - `.claude/worktrees/agent-ac5f7832a73527151` (earlier N5.6 core and drift journal).

  Copy any cited evidence they hold into the main checkout's `.artifacts/` before removing them. The N5.6 Python
  references are in `D:/Temp/Scratch/SRPSS/fast_proof/eb_n56_r251/` (18 of 18 runs done).
- [ ] Working rules (operator, 21 Nov; handbook 7a and section 3-4, proof guide section 3): critical path only; related
  work to the agent that holds it, unrelated to a fresh one; regression guards only after acceptance; unattended runs
  at once; briefs name the owning checklists, merges check the report bullet by bullet against the cited evidence;
  ABI numbers reserved at dispatch; main built once per batch of C++ merges.
- [ ] Continue [N5.6 Extruded Bubble](#n5-6-extruded-bubble) from the first open box and its linked receipts.
  Start the next implementation branch from main. The retained worktree at
  `C:/Users/Basjohn/.codex/worktrees/eb-compute-binding-limit/ShittyRandomPhotoScreenSaver` holds evidence.
  Keep the previous Claude worktree and journal
  (`.claude/worktrees/agent-ac5f7832a73527151/.artifacts/handover/JOURNAL.md`) for the earlier core and drift
  evidence. Its scratch and evidence are under `D:/Temp/Scratch/SRPSS/worktrees/agent-ac5f7832a73527151/`.
- [ ] Waveform follow-ups:
  - [ ] Watch: one GL_INVALID_ENUM on the route's first 4x frame on OpenGL (none single-sampled; a debug context caught no
    message); not the Group Wave squares (numeric overflow, fixed). Attribute with the next OpenGL route work.
  - [ ] Watch: the quiet-GPU `stream_ring` recheck (`mesh_buffer_check.py --rounds stream_ring`, GPU state before and
    after, margins against 0.05 ms) with Waveform now drawing natively.
  - [ ] N5.4's deferred Display 1 timing proof (Layer T, `7b0663cf5`). The 23 Nov comparison measured 50.0 / 77.2 / 51.4
    draws per second across Vulkan/OpenGL/Vulkan with the same settings and recording. Vulkan began about 51 Qt cycles
    per second from about 90 GUI requests. Trace delivery of `QEvent.UpdateRequest` to the same `QQuickWindow` beside
    the native item's request, swap and next Qt frame-begin. Use the split to attribute the wait before any scheduling
    change. The port order and the post-port optimization sequence govern this follow-up. Evidence is indexed in
    `Docs/Reference/Benchmarks.md`.
- [ ] Background track: N5.2f landed 22 Nov (registered on Vulkan, 26 of 28 transitions native; agent retired). Its
  box keeps the D1 hitch rows (a game held the machine) and the non-indirect fallback form; then N5.2g.
- [ ] Performance, parked until every port has landed (operator, 21 Nov: no optimising before then unless a port
  performs so poorly it cannot be considered stable, i.e. gaps over 33 ms inside runs, stalls or growth). Found 21 Nov (Jigsaw's GUI tick also about 1.25 ms against 0.5, its piece table packed every frame): inside a run, the saver's CPU on native Vulkan transitions is
  28-36 % of a core (Beam 32.9 %, the four 3D scenes 28-36 %, Jigsaw highest), while GPU render time halves against
  Python OpenGL. The earlier whole-row figures (Beam 16.5 % against 9.9, Crossfade 19.9 %) included idle time between
  runs; the first step is the same inside-run figure for Python OpenGL, so the ratio is like for like.
  Not one transition's own: it is the Vulkan path. Root cause (the present path, the frame driver, the trace and sampler on
  that path) before NF; evidence `tools/baselines/preflip/beam_*` and `crossfade_native_vulkan*`.
- [ ] `--perf` overlay on Vulkan (operator, 21 Nov): the Visualizer's overlay shows no fps, rev or age when the saver
  runs on Vulkan (`--vulkan`). Root-cause where the native path stops feeding the overlay's figures; fix at the owner
  so both backends feed it the same way, with a test. Before NF.
- [ ] The Oscilloscope: registered and documented; left only its two side defects and its backlog line.

**Open work by slot**

Follow the operator's current roster and weekly cutoff. Call the visual judge only when the comparison leaves
an uncertain uplift or degradation.
- [ ] Resume [N5.6 Extruded Bubble](#n5-6-extruded-bubble) from its first open reference-conversion box.
- [ ] Bubble GPU optimisation step 3: the offline work is done (the hero and wake rejects halve the bubble pass at 4K);
  the lead's live Display 1 baseline remains.
- [ ] Audit (Opus Medium; Opus High only for core C++ with real risk): each merge (the Bubble landing is audit 8).
- [ ] Sonnet Medium: profile the owner replay (the fast proof's first box), then cheap audits and docs of open avenues,
  and hygiene (item 6).

### Item 0. Operator defects of 11 Nov: section 1B (backlog; its own internal order; see Order point 5)

### Item 1. Operator-reported defects first

- [ ] Foundry UX (operator, 14 Nov): `Docs/Future_Work/Foundry_UX_Audit_2026-11-14.md`; open from it, for the operator's
  pick: its remaining high and medium findings and the Build Foundry's port from Tkinter to PySide6.
- [~] Defect (operator, 14 Nov): a Studio window's taskbar icon in frozen builds is Windows' default box. The static
  cause is unproven (likely an icon Qt could not decode). Lead: check the next GitHub frozen build's `[ICON]` startup
  line, any no-icon warning for a shown Studio window, and the taskbar.
- [ ] Lean guard output landed 27 Nov (merge of `worktree-agent-a75a706dc286f6d1a`; unit tests only). Lead: confirm on
  the first real run of each after it: `native_stream_player.py` leaves only `work/index_<api>.json`, the report and
  `failing_frames/` in the evidence (no `frames_*.bin`), `owner_render_parity.py --native-only` completes with
  `_LastFrame`, and `bubble_display_wide_response.py` / `extruded_bubble_music_response.py` publish through
  `evidence_media`. The judged `--native` run still spills the whole take to owner scratch until it exits (transient).
- [ ] Bubble's fast-proof baseline and record check (found by the C guard, 22 Nov):
  - [ ] The accepted `native_render_parity.json` used by `--accepted` predates the card quad (ABI 31/32), so no frame
    keeps its verdict and every guard judges all frames; take a fresh accepted Bubble baseline on main (ABI 39), with
    input 22's tracked exception, and point the guide's Bubble guard command at it.
  - [ ] The native record identity check fails on `u_fade` at inputs 0-27 (native 0.86 rising to 1.0, Python 1.0):
    since d67d6aac3 the native route folds the scene fade into the content fade and the check's Python side does
    not; fold it there too, with a control.
- [ ] Defect (operator): in the Dashboard profile, clicking a link kills the cursor halo completely. Root-cause and fix at
  the halo's owner, with a test.
- [ ] Material density, composed-stack readability and Studio surfaces: section 1A, item 1.7 (with 1.7a, 1.7b).
- [ ] Native Settings corners: section 1A, item 1.9. Keep their acceptance and reversible checkpoints separate.
- [ ] Circle selector for direction controls (operator, 22 Nov; much later, with the Studio work): Bubble's gradient
  direction and the other direction controls use the circular visual control, `DirectionMapper` /
  `DirectionChoiceMapper` in `ui/widgets/visual_controls.py` (NOT Bubble's old gradient control, which it replaces),
  adapted for Qt Quick where the Studios need it. It allows custom positions, and where the
  element makes sense a two-node "pie" range: e.g. specular with two pie points creates speculars anywhere between
  them. Defaults stay exactly as now (presets untouched); Settings spec system owns the values.
- [ ] Studio stall, clip selection and sidecar log (contract: `Docs/Reference/Visualizer_Studio.md`; the control-hints
  test runs on a never-shown window), D1 run (1B.14 harness) with the lead's checks:
  - [ ] Edit Reaction Mode while Waveform plays (the Studio keeps responding; the sidecar log shows the replay).
  - [ ] Pick Human once (the clip selection lands once, with its sidecar log line).

### Item 2. §7.1 Waveform Ribbon reactivity (operator, 7 Nov night: "Adaptivity is the enemy")

Contract: `Docs/Guides/Visualizer_Reactivity_Authoring.md` (§2B, §2C, §13D). Evidence:
`.artifacts/evidence/visualizers/waveform_ribbon/memoryless_reactivity/` (`20261107_lead/`, `20261107_bands/`) and
`.artifacts/webp/visualizers/waveform_ribbon/memoryless_reactivity/`.

- [~] Lead review on a rendered showcase WebP on recorded music: Frozen Past (Preset 5), live.
- [~] Lead review on rendered Studio frames (D1 run, 1B.14 harness): Pulse Count, Pulse Falloff and Freeze Deflate in
  the Studio.
- [ ] Vocals first, remainder: a kick inside sustained bass raises the swell 21% less (median .058 -> .046; those
  kicks also reach Kick Accent now); check it on the operator's look before tuning Pulse Strength's mid-led routing
  further.
- [ ] Breathing as a swell and release with proper motion (operator: 2D Bubble's breathing is the reference; guide
  §13A). Breathing is now only a faster release in soft passages.
- [ ] The onset reward is still sized by the bus's adaptive flux threshold (about 1 s of context: the same kick right
  after a dense passage scores .22 against .61); size it on the fixed scale.
- [ ] Group Wave's separation from Travelling Pulse and the pulse bands' colour edges: their boxes are in section
  7.1, "Reaction: travelling energy pulse".

### Item 3. Expanded Visualizer M2 onward (plan 01; operator's M1 amendment: a mode switch never re-expands)

Contract and phase ladder: `Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`
(§0.6 capable modes, cycling and inset; §G overlays; M3c Fullscreen Edit). Next: M2b, then M3 and M3b/M3c follow-ups.

- [ ] M2b, Spectrum's width-scaled bar count (operator, 8 Nov: "20% more if fullscreen and horizontal"): the display
  rule is built (`widgets/spotify_visualizer/spectrum_display_bar_count.py`, round(1.2 x) bars, cap 64, resampled
  by the renderer); the width-ratio DSP recompute of plan 01 M2b stays open and needs the hidden activation
  transaction (an engine bar-count change bumps its generation). Spectrum's own edge fade is part of it.
- [ ] Expanded Visualizer on D1 (1B.14 harness), lead review of grabbed frames: the expanded card's inset (operator,
  7 Nov night: "Don't reach nearly close enough to the screen borders") and the ordinary widgets and their shadows
  fading out with it (operator: "Don't really hide/disable the widgets underneath"; 14 logical px at 2560 x 1440
  was 30). Complex transitions under the takeover are M4.
- [ ] Bright-area text switch (operator's long-term item, plan 01 §G): overlay text white with a soft shadow should
  switch to black over a bright Visualizer area; cheap means no per-frame CPU readback (a `ShaderEffect` on the text
  sampling the already-rendered frame, or a tiny luminance probe only while an overlay shows). Not built.
- [ ] Now Playing on D1 (1B.14 harness), drag and hover driven by messages, lead review of the frame trace and
  grabbed frames: Show On Hover (`now_playing.hover_reveal`, on main since 0eda39c4) and Now Playing's parts as the
  block's children in Fullscreen Edit (`now_playing.child_geometry`, 2100fdc2): the child lock, a part drag and the
  hover re-fade on the real display.
- [ ] Side defect (8 Nov): `tests/test_qtquick_system_audio_osd.py::test_osd_colour_inheritance_respects_active_widget_
  theme_and_authored_overrides` fails when run after `tests/test_visualizers_fullscreen_mode_pill.py` in one
  process (passes alone; reproduced on the base): Widget Theme state leaks between the files.
- [ ] M4 (plan 01 `02_E0_Covered_Display_Admission.md`): the GPU/render-thread measurement with photo changes on the
  other display.
- [ ] M4: the two-monitor look, as a D1 run (1B.14 harness, Expanded Visualizer on D1 with a hidden D0-side owner);
  what truly needs both displays visible is listed in that report, not assumed.

**Next (admitted, in this order):**

### Item 4. Settings round-trip native residual

- [ ] About 2.5-6 MB of native heap per open/close, and the Studio's about 1-2 MB per session (measurements and the
  next step: section 3, "Settings round-trip memory growth").

### Item 5. Card/theme legibility beyond item 1.7 (details at section 4)

- [ ] Rerun `tools/theme_legibility.py` against final composed surfaces.
- [ ] Re-author the raw linked Widget Theme roles that fail `tools/theme_legibility.py`, especially widget.accent on
  widget.panel and header surfaces, and keep the concrete failing roles listed in its report; runtime ink correction
  does not make a raw mirror export pass.
- [ ] Fix light-theme widget shadows, then inspect actual faint text over the resulting cards (analytic panel
  contrast alone does not account for the shadow's effect); 4x crops, lead review.

### Item 6. Hygiene

- [ ] `tools/media_key_matrix_harness.py` waits for an old `[DISPLAY_WIDGET]` window-flag message whose producer
  has been removed. Replace the oracle with the current window-policy evidence and exercise a failing control.
- [ ] Make Linux smoke GL diagnostics readable: `tools/linux_smoke_dist.py` prints only the last 800 characters of
  `glxinfo -B`, cutting off the renderer and sometimes the middle of a line. Both Xvfb builds on 23 Nov passed;
  their logs show implausible virtual VRAM figures (4294848057 MB and 914948 MB). Report the renderer and GL version
  directly, with the full probe retained on failure. Keep the render and settings admission checks.
- [ ] Make live-check monitor rejection actionable. In the 23 Nov Spectrum smoke `20261123_native_draw_swap_smoke_custom`,
  `[VIS_ROUTING]` prints `requested_screen=0` with participating screen 0 but rejects the physical binding as
  unavailable; the report then stops at missing worker publications. Include the resolved binding and its rejection
  reason in the receipt so a routing failure can be distinguished from an admitted Visualizer that stopped drawing.
- [ ] Reconcile the raw-thread policy check with the existing PacketMailbox wake thread and its lifecycle
  owner. `tests/unit/test_policy_compliance.py` flags `core/visualizer_engine/packet_mailbox.py:472`.

- [ ] Re-baseline after Qt 6.12.0 (admitted: doc sweep decision 9, 12 Nov; moved here from the 7 Nov "not yet
  admitted" list by the night audit's fix soon 6): `tools/overhead_baseline.py`'s stored baselines and the figures
  in `Docs/Reference/Benchmarks.md` predate the bump. Run it once on main (lead or Medium slot; no load), record
  new baselines with system usage before the next shared-path comparison. Today's merges (12 Nov: N2.3's changed
  Spectrum per-frame reads, N1.6's GL-call cuts) were measured on branches without a 6.12 baseline: compare
  Spectrum against the new one.
- [ ] **Replace legacy preset-dependent tests with synthetic fixtures (operator, 23 Nov; cross-suite
  cleanup, independent of the artistic work):** audit existing `tests/`, harnesses and CI for
  any test that reads `presets/visualizer_modes/`, invokes `--preset N`, imports an operator
  preset for schema/roundtrip/preservation or asserts a real preset's name, count, file,
  key/value, rendered pixel, screenshot or response. Convert to synthetic test-owned settings,
  isolated temporary preset-shaped files and controlled recorded/synthetic audio. **Do not
  delete tests merely to pass**: preserve their real schema/serialization/migration/response
  contracts with independent negative controls. The current `test_3d_curated_preset_ownership.py`
  and `test_foundry_nav_and_eb_postport_20261119.py` deserve inspection, not presumed guilt
  without reading. Protect the operator's mutable files; no auto-repair, no pinning or
  replacement of curated presets. New Studio integrations must not introduce any such test.
- [ ] Hidden cross-test dependency on an earlier test's `tmp_path` (lead, 7 Nov): with pytest's
  `tmp_path_retention_policy = failed`, `test_3d_curated_preset_ownership.py::...promotes_missing_owned_temporal_
  and_profile_keys...[shockwave_grid]` (0.7 vs 0.23) and two or three `test_settings_dialog.py` tab-restore tests
  fail; each passes with the default retention, so something process-scoped keeps a path into an earlier test's
  `tmp_path` (a cached preset tree or storage root). The setting was reverted. Find the cache and give each test its
  own root; this may also hide state leaking between tests.
- [ ] Hidden-host owner guard red (N5.2h agent, 28 Nov): `tests/test_quick_backend_owner.py::
  test_every_hidden_host_user_goes_through_the_owner` fails because `native/core/python/eb_core_check.py` and
  `native/core/python/waveform_check.py` create hidden hosts outside the owner. Route them through the owner.
- [ ] Order-dependent failure (lead, 28 Nov; Borderless merge run): `test_qtquick_child_lock_scene.py::
  test_child_lock_is_reset_adjacent_default_locked_and_does_not_retire_geometry` passes alone but fails after the 80
  files that name `themes_tab`/`widgets_tab_defaults`/`widget_descriptors` (twice): `customLayoutClose-clock` is
  visible but not enabled. Find the earlier test leaving process state (likely the same class as the `tmp_path` box
  above), fix it at that owner.
- [ ] The AC-13 remainder (`Docs/Reference/Architecture_Checklist.md`).
- [ ] AC-14, AC-15 and AC-16 (same checklist).
- [ ] The rest of the plan staleness audit of 12 Nov
  (`D:\Temp\Scratch\SRPSS\research\20261112\plan_staleness_audit.md`; its line numbers predate the edits), Sonnet
  drafts and the lead decides:
  - [ ] One owner for the border material (1.7b, 1B.8's M3 and M4, 1B.9's last box) and for 1.9 against 1B.9.
  - [ ] One root-cause box for the state that leaks between test files in one process (item 3's side defect,
    section 3's "Isolate active Widget Theme state", the M3c context-menu and gesture reds, 1C.3's crash).
  - [ ] Section 3's "Found while ... (record, not yet admitted)" blocks: admit each or move it to
    `Future_Work.md`.
  - [ ] Findings written as boxes (the R-175 block, 7.1's "Open:" lines, 1B.8's theme-authoring numbers): one
    step each, the figures to their evidence document.
  - [ ] "Learned levels still in other modes" (section 3): per mode, the root-cause, contract, fix, guard and
    evidence steps.
  - [ ] 1.7a's first two boxes against M1, M2 and M2b: delete what those landed (1.7b's `plateInset` box went
    12 Nov).

### Item 7. Load session of 11 Nov (run; figures in `Docs/Reference/Benchmarks.md`, "Load session, 11 Nov")

Receipts: `.artifacts/evidence/performance/load_session/20261111_load_session/driver_receipts.json`.

- [ ] Waveform Preset 4 is still over the 8 ms render budget under game60 on the worker (10.4 ms median,
  `reflection` 1.7 and `ribbons` 1.9 ms the largest stages): a P3 input (item 8b, N5.4), not a P2 fault.
- [ ] Side defect, `tools/visualizer_live_check.py`: on the worker run with a Settings round trip the age chain's
  medians are nonsense (`publish_to_swap_ms` and `consumed_age_at_sync_ms` medians about -48,500 ms, p90 sane):
  records from before and after the round trip (a new worker generation, a different clock origin) are mixed.
  Report ages per generation, or only for the steady window before the first round trip as the help text says.
- [ ] Review the uncovered cases in the Watchlist ("Load runs the 11 Nov session did not cover") when admitted.

### Item 8. §8 Accepted-mode follow-ups

- [ ] Complete the Bubble performance-parity check in section 8.

**Then:**

### Item 8b. The native core: one C++ core for everything we draw; Vulkan the default, OpenGL selectable

Decisions with their reasons: `Docs/Future_Work/Native_Core_P3_Decisions.md` (D1 to D11 decided)
and `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md` (its 12 Nov addendum says what is superseded).
Records: P1 `Native_Core_P1_Spike.md`; P2 `Native_Core_P2_Engine_Design.md`, `Native_Core_P2_Phase_Boundary_Audit.md`,
`Native_Core_P2_Closeout_and_P3_Entry_2026-11-09.md`; attribution baseline
`tools/baselines/overhead/2026-11-11_4658981b.json`; SMP seam
`Docs/Future_Work/ShittyMusicPlayer/03_PCM_Source_and_Native_Core_Seams_2026-11-09.md`. Research outside the
repository: `D:\Temp\Scratch\SRPSS\research\20261112\native_core_capability_matrix.md` (which mode uses what) and
`native_core_qrhi_gaps_and_conventions.md` (every OpenGL dependency with its routes; the conventions).

**Standing rules of this item (not boxes):**
- A port is done when it has (a) single-sampled pixel parity on OpenGL against the Python renderer it replaces
  (`tools/visualizer_replay/owner_render_parity.py`) at the widened run set (variants `a` and `b` and every Choice
  offer: `tools/conventions_identity.py` `mode_runs(mode, offers=True)`; never presets), (b) the same scene on Vulkan in the hidden host against the
  native OpenGL result, within a tolerance the port states, (c) the frame trace and render-thread figures beside
  the Python path's with zero calls holding a Python thread state, (d) Settings, Studio and engine-worker parity
  and the mode's own tests green, (e) GPU time per pass and nothing per frame at rest, (f) one bounded Vulkan
  rehearsal on Display 1 by the lead (D10), (g) no rebuild for Settings or Studio work (lead, 14 Nov, from the
  operator's question): the mode's fragment shaders load at runtime from the product's own `.qsb` (baked by
  `tools/regen_qrc.py --shaders`), every Settings-derived value is resolved in Python from the spec and packed by
  the core by reflected name (a settings block re-packed only on a Settings or card change), and C++ holds only
  per-frame and simulation arithmetic; a test adds a settings-only uniform and draws it with no module rebuild.
  N2.5 builds the shared piece (round 4); every later port uses it. Then the Python renderer and its shaders are
  deleted in the same change (a transition's at the background family's switch, N5.2h). Never two permanent
  renderers.
- Every primitive and service is proved on its own off-screen harness scene (GPU time median and p90, lazy
  creation, no work when dormant, clean retirement); none becomes a second renderer, clock or camera. Read the 3D
  foundation lessons (`Docs/Reference/Transitions.md`) before a 3D slice and append after it.
- A native route required for the original **existing-mode port** is a measured D5.3 service with its
  mandated OpenGL counterpart. Once the original mode is ported and accepted, a NEW optional fidelity
  feature may explicitly require Vulkan features, such as mesh shading, without duplicating that
  extra artwork on OpenGL (operator's D5.3 supersession of 23 Nov). Its absence must be accurately shown
  as feature-unavailable in the Studio while the mode's original OpenGL path stays unaffected.
  No experimental extras change the accepted original appearance or hold up the flip.
- No new 3D primitive is built in the Python OpenGL renderer unless an open defect needs it; new modes are built
  on the native core only (was N1.5), through its generic mode content (N2.9): a new mode is a Python simulation in
  the engine worker (off the render thread, publishing its frame record), its shaders loaded at runtime and its
  spec, with no C++ and no build round while it is iterated to its mock and reactivity goals. Hand-written C++
  for a mode is an optimisation admitted only after those goals are met and a measurement shows the hot path; a
  new GPU technique is a primitive, built and proved once in C++ and then used by every mode as data (lead,
  14 Nov, from the operator's question).
- High-potential primitives are built without an existing consumer; low-potential ones only with an admitted
  consumer (operator, 12 Nov). **Operator refinement, 23 Nov: their preferred artistic result is an
  optional, genuinely music-reactive feature in an existing accepted Visualizer, demonstrated by a NEW
  mutable authored preset, rather than a standalone showcase WebP.** This does not replace the primitive's
  standalone harness, median/p90 GPU timings, validation, dormancy or retirement proofs. All SIX integrations
  in the N6 demonstration box below are **approved implementation work** once their dependencies and modes
  are ready. They must not block native mode-port parity, N5.8 Studio migration, NF (the Vulkan flip), or
  existing accepted modes. Add the feature as an adjustable, real production Studio surface, with visual
  AND musical-response controls; no hard-coded showcase-only effect or on/off-only implementation.
  **ABSOLUTE PRESET TEST BAN:** NEVER use ANY shipped/operator-authored preset as a test input, fixture,
  schema oracle, screenshot golden, hash, saved-value expectation, parity baseline or regression pin.
  That includes all demonstration presets and their slot/file identities. Do not read them in automated
  tests, restore them to an older version, or make a test pass depend on their current contents. Tests
  construct synthetic TEST-OWNED configurations/audio/seeds/files and check the actual feature contracts.
  Presets are mutable demonstration ART, and a human may reauthor them freely without breaking tests.
  The catalogue's "what this makes possible" notes remain in `Docs/Reference/Primitives.md`, with
  underlying resource facts in `Docs/Reference/Scene3D_Resources.md`.
- The protected clip and background commits (ce07b991, 07486d83, 985b9d53) are not retuned while the Python path
  lives; the native background must measure no worse than them before it replaces them.
- The native module is compiled only by the GitHub workflow (operator, 12 Nov; handbook section 8; N0.9): an agent
  commits, the lead pushes its branch and runs the build, the agent never starts one. Frozen builds stay the
  lead's, on GitHub.
- The shared 3D architecture is inside this item, in order (operator, 12 Nov: "definitely put in the 3D work
  needed into the native work plan, in detail and order"): the port rewrites every renderer, so it is decided
  and built here, never afterwards and never twice. The old primitive ids: S3D-1 is N4.b, S3D-2 N4.c, S3D-3 N6.2
  (photo shells N6.4), S3D-4 N6.1, S3D-5 N4.d, S3D-6 N4.h, S3D-7 N4.f1 and N4.f2 with its smoke N6.3 and lightning N6.6.
  The old stage names: P3.1 and P3.2 are N2; P3.3 is N5.2; P3.4 is N5; P3.5 is NF; P4 is N4.f2 (N4.f1 is the fog volume port). What exists in
  the Python substrate and is therefore a port is listed in `Docs/Reference/Scene3D_Resources.md` ("Shared
  Scene3D capability inventory").

**Order.** N0 and N1 now. Then N2 (the substrate and Spectrum), N2b (the background layer and the first full
rehearsal), N3 (the 3D substrate). From there two ordered tracks, one High slot each: the **modes track** (N5.1,
N5.4, N5.6, N5.5, N5.3) and the **background track** (N5.2 a to h). Waveform Ribbon and Extruded Bubble go before
the modes with no measured need: they are the triggers, and Expanded Visualizer M6 waits on Extruded Bubble. The
**primitives track** (N4's unconsumed items, N6) runs whenever a High slot is free and never holds the flip. NF
(the flip) follows both tracks. After NF: the new-mode track, **Reactive Liquid / Audio Melt Pool first, then
Concrete Rain**, followed by substantial QoL work and operator review. SMP remains in `Future_Work.md`, not an
automatic successor to NF, item 9 or the first new Visualizer.

**P2 remainders (the worker is the default; none of these holds N0 to N2 open)**

- [ ] Make the framed-view negative control independent of presentation timing
  (`test_visualizer_owner_engine_worker.py::test_the_framed_view_the_worker_tick_reads_follows_the_owners_controller`).
- [ ] A target that never reveals: decide the bound (the existing loop can retry every six seconds), including
  stopping a failed owner's runtime on a refused reload.
  - [ ] Implement the bound at the owner.
  - [ ] Guard test with a negative control on today's loop.
- [ ] Bubble owner: define Random Group Drift's guarantee before retuning or asserting alignment
  (`test_bubble_reactivity.py::test_group_drift_aligns_non_swirl_bubble_motion[random-x]` depends on the draw).
- [ ] Neon Lake's driver memory at its first draw (`private_other`, about +280 MB committed, mostly not resident)
  is not attributed: read GPU allocations around the first draw before N5.5 sizes anything for it.
- [ ] P2-C1 remainder (closeout section 2): a failed high-water admission preserves the last good frame without
  silently changing the worker path; the load part only after the operator's yes.
- [ ] P2-C2 remainder: leases and holds release exactly once across Settings, mode switches, worker death, a
  failed reload and a Visualizer-off run; one worker and mapping at most, no worker cost while disabled.
- [ ] M5 remainder: measure the Studios and the post-failure fallback separately (the in-process and worker laps
  show a first-visit GPU high-water step, not growth).
- [ ] L3 remainder: `collect_ms` with the displays on and under load (the one live reading, 13.5-21 ms over four
  processes, was taken with the displays asleep and the Visualizer parked).
- [ ] L4 residual: a blocked cadence thread fails its session closed at the worker's heartbeat, but the thread
  itself stays in the worker until it returns.
- [~] D1 run (1B.14 harness), lead review of grabbed frames: a mode switch on the engine worker leaves no ghost
  of the outgoing mode after its fade-out (R-184: Sphere, Extruded Spectrum, Waveform Ribbon switches).
- [ ] **"Visualizer swaps are pretty bad into 3D modes (they fade back in long before they are ready to show frames)"**
  (operator, 22 Nov). Obey the fade: the incoming mode's fade-in starts on its first drawn frame (a completion edge from
  the renderer, Python and native alike), never on the swap; until then the outgoing mode holds (fade, never vanish).
  Proof on Display 1 under load: frame-by-frame captures of swaps into each 3D mode (Waveform, Extruded Bubble, Neon
  Lake, Extruded Spectrum, Sphere), no faded-in empty or partial frame; control: the old start-on-swap. Later helper:
  N5.2g's field-job machinery (off-frame preparation with a ready edge) to warm the incoming mode before the swap.

**N0. Decisions, contracts and proofs (design and harness only; can start now)**

- [ ] N0.4's remainder (D5.5 points 2 and 5), built with the first framed port (N5.4, then N5.6): the worker's tick
  calls `widgets/spotify_visualizer/framed_view_camera.py` (today only its test calls it) and publishes the
  finished camera in the mode's native schema; the renderer stops building one.
  - [ ] D5.5's test "one owner": no perspective or tangent construction in the native sources or schemas (negative
    control: `tan(fov / 2)` added to a core file).
  - [ ] D5.5's test "resize edge": the packet carries the extent its camera was built for; a frame whose stamp
    differs from the target holds the previous frame (negative control: ignore the stamp, a stretched frame).
  - [ ] Waveform's oracle in `tests/test_framed_view_camera.py` (`_renderer_waveform`) restates the renderer's
    expression: make the renderer and the test call one function, as Extruded Bubble's `parameter_camera` is.
- [ ] Offline Waveform hosts lost their pulse span with N0.4: a controller with no framed view gives `card_span`
  None and the fixed grid (`core/waveform_ribbon_dynamics.py:979,1057,1441`). The driver, the Studio and the foundry
  set one; these do not: `tools/visualizer_replay/waveform_ribbon_motion_audit.py`, `waveform_ribbon_signal_audit.py`,
  `waveform_ribbon_breathing_probe.py`, `tools/labs/waveform_ribbon_recorded_input.py`, `engine_worker_gate.py`,
  `live_engine_gate.py`, `live_engine_cost.py`. Before item 2's reactivity work uses them again:
  - [ ] One helper beside `configure_offline_controller` sets the framed view of the card a host models
    (`resolve_framed_view`); each host above calls it (the worker gates send it as `VIS_SET_VIEW`).
  - [ ] Guard: a Waveform tick in each of those hosts has a view span (negative control: today's hosts have none).
- [ ] N0.6 D6's proof (harness rounds 1 to 6 merged; the record is D6's "As proved" in the decisions document;
  - [~] The P1 desktop window's alpha, DPI and sleep/wake behaviour, validated by the lead on Display 1 (hidden-host
    results do not close it).
  evidence `.artifacts/evidence/native_core/n06/`). The validation layer (Khronos's Windows build in
  `D:/Temp/Scratch/SRPSS/native_spike/validation_layers/extracted/`) is given to the harness process alone with
  `--layer-path`: no registry entry, nothing persistent. Validation is clean apart from Qt 6.12.0's own defects, each
  excused only by its id, text and Qt caller (`native/core/python/vk_validation.py`; owners and sources in
  `Native_Core_N06_N07_Qt_Facts.md` section I): A (`QVkTexture::create` PREINITIALIZED with optimal tiling), B
  (`createOffscreenRenderPass` without an external dependency, only with non-preserving targets), D (Qt Quick's
  `grabWindow` on Vulkan, grab phases only). C (`toVkAccess(TexColorOutput)` write-only) is avoided by priming targets
  at creation and after every readback and is never excused. Owed:
  - [ ] **Qt 6.12.1 bump (lead; operator, 20 Nov: bump without asking).** Checked 23 Nov: Qt published the 6.12.1
    SDK and Windows MSVC 2022 repository metadata. PyPI version endpoints for PySide6, PySide6_Addons,
    PySide6_Essentials and shiboken6 still return 404 for 6.12.1. Keep runtime and SDK on 6.12.0 until all four
    matching Python wheels are on PyPI. The 6.12.1 SDK entry passed an isolated download, checksum, extraction
    and layout check (`.artifacts/evidence/native_core/n06/20261123_qt_6121_readiness/`). Once wheels publish:
    - [ ] Pick a stage boundary (decision D11): no agent mid-build on `native/core`; agents merged or checkpointed.
    - [ ] Change the four pins in `requirements.txt`, then `pip install -r requirements.txt` with no venv process
      running (locked PySide6 DLLs make pip fail; restore a mixed set at once if it does).
    - [ ] Rebuild the native module on GitHub: the workflow reads Qt's version from that pin
      (`tools/native_sdk_fetch.py --print-qt-version`). Regenerate the `.qsb` packs if `regen_qrc --shaders --check`
      reports drift.
    - [ ] Run focused native loader, host and composite tests and one Vulkan live check of a native mode on Display 1.
    - [ ] With A removed from `native/core/python/vk_validation.py`, run the current N0.6 proof owners
      `host_check.py` and `composite_check.py` on Vulkan with `--require-validation` and `--layer-path`. Save the loaded
      Qt version and validation receipts. The released source uses `UNDEFINED`; close A when these rounds pass.
  - [~] Awaiting Validation — lead, Display 1 visible and bounded, when two displays are connected: a real translucent window on the
    module's device: see-through to the desktop (D7 point 8's first route; the hidden runs cannot read the composed
    alpha), with the DWM system backdrop and the project's glass, then the swapchain under resize, DPI change and
    sleep and wake. If it is not see-through, D7's second route (DirectComposition) is tried next.
- [ ] **D6 / N6.7 mesh-shader readiness before the Vulkan flip (operator, 23 Nov; capability plumbing, not N6.7 admission):** in `native/core/src/vulkan_context.cpp`, probe `VK_EXT_mesh_shader` on the selected physical device, query `VkPhysicalDeviceMeshShaderFeaturesEXT` and `VkPhysicalDeviceMeshShaderPropertiesEXT`, and optionally enable the extension and supported `meshShader` / `taskShader` bits in the `vkCreateDevice` feature chain. The selected device must still start when the extension is absent. Report supported **and enabled** state, output vertex/primitive and workgroup limits, and why the path is unavailable in device facts; do not infer enablement from an advertised extension alone. Prove on the native harness with extension present and artificially absent (negative control), clean validation, both imported Qt Quick QRhi and raw-device identities unchanged, and device-loss/rebuild feature reprobe. No mesh-shader pipeline, work, or flip blocker is introduced here; N6.7 owns that later.
- [ ] N0.3: run the three scenes on Metal when a Metal machine is available (Watchlist).
- [ ] N0.7 remaining Qt 6.12 checks:
  - [ ] The handoff probe's inherited-state assertion was narrowed from Qt's whole sync to the item's
    `updatePaintNode` (`tests/test_qtquick_native_texture_handoff_gl.py:114-129`) on the statement that Qt 6.12's
    own sync resets the array-buffer binding; no control shows it. Add the control: a sync in which the adopting
    code does nothing, GL state read before and after. If the binding still changes, record it as Qt's; if not,
    restore the whole-sync assertion.
  - The rest of 6.12 is researched in `Docs/Future_Work/Qt_6_12_Gains.md` (merged 12 Nov; qtbase and qtdeclarative
    `changes-6.12.0` were unreachable, so the threaded render loop, layers, D3D12/DirectComposition and the Windows
    platform plugin are unread there). Placed: SMP's audio sink period and cover-art key in plan 02 section 4.1 and
    5.2; the SMP desktop window's backdrop call in N0.6. Checks on 6.12 (the venv moved on 12 Nov; Display 1 was
    off at the time, so the D1 part waits for it):
    - [ ] Text: DirectWrite now reads a font's GASP table to choose antialiasing. Compare text crops (a widget title
      and body text, the Settings dialog via the offscreen render route) before and after; a visible change in
      weight or crispness is recorded and judged by the lead.
    - [ ] QML required properties now fail instead of building silently: grep every run's log for "required
      property" and QML component errors after the bump (the next D1 run and the next hidden-window test run);
      each hit is fixed at its component.

**N1. Every shader portable, in the existing OpenGL renderer (no C++; can start now)**

- [ ] The beads at the near plane: D4.4's 1.4 px bound is geometric; check the bead shader's near culling and the
  near layer's defocus before the bound is quoted as visible error.
- [ ] Verify the drift programs through fxc/dxc and the Vulkan backend when the native core first runs them
  (D4.7's self-check reports a compiler that breaks the pairs). Other vendors are best effort, never tested.
- [ ] Side defect: `tools/gl_object_ledger.py:84` records only names a create call returns; objects created through
  out-parameters (`glCreateBuffers(1, arr)` in `scene3d/stream.py`, `population.py`, the defocus targets) are
  invisible to the lifecycle tests: record those too, with a test.
- [ ] Side defect: `waveform_ribbon.py:54` (`0.5*(clip.z/clip.w+1.0)`) and `scene3d_spheres.py:197` assume OpenGL's
  -1..1 depth: route both through `viewDepthFromDepthTexture`/the include before matrices are corrected at upload.
- [ ] Side defect (12 Nov evening audit, low): `tests/test_qrhi_texture_formats.py` scans `rendering/` only, by the
  enum's text, so a format QRhi lacks under `widgets/` (its shaders included) or reached through an alias passes.
  Scan `widgets/` too, with a control that plants an `rg16f` image layout there.
- N1.4's remainder: the eight scene composites in `scene3d/target.py:125-286` (and their oriented forms) keep raw
  `gl_FragCoord` and are never converted: D5.2 replaces them with a texture node.
- [ ] N1.6 Loose uniforms into blocks across the renderer (`qsb` needs blocks), each group pixel-identical in OpenGL
  before and after and with GL calls per frame recorded before and after (fewer calls is a gain today); `.qsb` baked
  for every backend, not `--glsl 460` only; each group leaves the readiness ratchet in the same change. A group whose
  conversion is not pixel-identical inside one dispatch is converted at its port instead. Order: by first consumer on
  the ladder, not N5's order. Remainder (ratchet 12; every other group is merged):
  - [ ] Prove new conversions and ports at the widened run set (variants `a` and `b` and, with `--offers`, every Choice
    offer: `tools/conventions_identity.py`, `tests/test_conventions_identity_runs.py`), first parent against merge.
  - [ ] Convert at its port, not here: Neon Lake's basin (`NEON_VERTEX_SOURCE`/`NEON_FRAGMENT_SOURCE`, one 8-bit level
    on 2-6 pixels with Glass on its block; `NEON_BLOCK` is kept as its layout) and Extruded Bubble's traced glass.
  - `rendering/gl_programs/lighting.py` belongs to N4.m: it is not a product shader (no `#version`; only its test
    draws it), and a program that includes it converts it (a 3088-byte block, about 3 KB of resources).
- [ ] D5.3's formats service, its one listed use: the scene target's multisampled velocity attachment
  (`scene3d/target.py`, RG16F kept; RGBA16F would add 127.5 MiB per 4K display at 4x, 255 MiB at 8x). Built with the
  substrate when the scene target ports (N3), or reconsidered if N1.8's resolve-first rule removes the multisampled
  velocity.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 14): QRhi has no RG16F, so "RG16F kept" cannot be built natively. The native
  velocity is two R16F attachments, the same bytes as RG16F; RGBA16F only if the measurement shows two
  attachments cost more. A biased RG16 is refused: the single MRT clear value cannot encode zero velocity in it.
  The velocity resolve differs by backend (Vulkan averages, OpenGL blits nearest), so velocity resolves through
  the core's own per-sample pass (D14 point 10), nearest, on both.
- [ ] D5.6 row 13's control was not run: fill the widened targets' unused channels with non-zero values in a test, so
  a consumer that reads them fails (the scan and source checks show only `.rg`/`.xy`/`.rgb` reads today).
- [ ] N1.8 Per-sample multisample reads (`sampler2DMS`, `gl_SampleID`): each use resolves first and reads the
  resolve, with stills before and after; a use that cannot is listed for D5.3's per-sample service with the
  reason. The uses (D5.6 rows 7 and 15), one step each:
  - [ ] The composites' shader average over samples (`scene3d/target.py`, `_RESOLVE_GLSL`).
  - [ ] The per-sample OIT composite (`_OIT_RESOLVE_SAMPLES_FRAGMENT`, `gl_SampleID`).
  - [ ] The shaft source (`scene3d/shafts.py`, `_DOWNSAMPLE_SAMPLES_FRAGMENT`).
  - [ ] The background capture's nearest depth over samples (`_BACKGROUND_SAMPLES_FRAGMENT`; Extruded Bubble's
    refraction: the A/B of D5.6 answer 3).
- [ ] Waveform Ribbon hard-codes 4 samples (`rendering/quick/scene3d/waveform.py:381`) and the Oscilloscope 1:
  route both through the scene's sampling owner (N3.1 ports one owner, not three sources).

**N2. The substrate's 2D half and Spectrum (C++; `native/spike_p1` stays evidence, never a shipped renderer)**

- [ ] N2.2 leftovers (proved; `native/core/python/host_check.py`): one open item, the hidden host's stale Qt Quick contents; see Backlog.
- [ ] N2.4 leftovers (proved; `native/core/python/composite_check.py`): the Glass material on the native composite; see Backlog.

Order inside N2 (the numbers stay stable for the documents that cite them): N2.1 to N2.4, N2.6, N2.7, N2.5, then
N2.8, whose rehearsal closes N2.5's rule (f) and releases the Python renderer's retirement.

- [ ] N2.5 leftovers (merged 14 Nov at ABI 8): Studio on Vulkan, the two-block split, audit lows L6 and L8, an activation-deadline side defect; see Backlog.
- [ ] N2.9 leftovers (landed 14 Nov at ABI 10, decision D12): the sampler primitive (N4.a) and the Oscilloscope's primitives; see Backlog.
- [ ] N2.8 leftovers (Spectrum rehearsal passed 14 Nov): an empty Visualizer card frame with no renderable mode; see Backlog.

**N2b. The background layer, natively, and the first full rehearsal**

- [ ] N3.8 leftovers (landed 14 Nov at ABI 14, D9 "As built (N3.8)"): D8 row 3's contention gate and the warm-up job class; see Backlog.
- [ ] N5.7b leftovers (landed 14 Nov at ABI 16, D7 "as built (N5.7b)"): the slower-device fallback and glass over the live Visualizer; see Backlog.
- [ ] N5.2a leftovers (landed 14 Nov at ABI 15): first-frame pipeline and 4K cost, and a C++ side defect (a refused still draws black silently); see Backlog.
- [ ] N5.7c leftovers (D1 rehearsal on Vulkan, 15 Nov): real monitor sleep and wake, and the `[STARTUP_REVEAL]` gate for the native wallpaper; see Backlog.

**N3. The 3D substrate core (C++; harness scenes, no mode yet)**

Numbering kept stable for the documents that cite it: N3.5 (per-pass GPU timing) moved to N2.6, and N3.8 (the job
service) is built in N2b, where its first job (a photo's upload) is needed.

- [ ] N3.1b The four-sample capture cost on Vulkan (D14 point 13; settled before N5.6, Extruded Bubble, the first
  consumer of a four-sample capture). At 4K Vulkan's 4x minus 1x is 0.58 ms against the Python path's 0.41 (OpenGL
  0.45 is within noise, accepted); `cost_parts` puts about 0.5 ms of it in the capture step at four samples against
  0.08 ms single-sampled, and cannot split it further. The load-op fast clear is rejected (D14 point 12): do not retry it.
  - [ ] Per-run GPU timing inside a content: the GPU timer's scopes around each run of passes on a scene target, each
    core resolve (nearest, and QRhi's resolve at a run's end) and each capture, opt-in with the timer (no queries and
    no work when it is off: `core/diagnostics` rule), reported per scope in the content's state and the frame trace;
    a GPU-free test of the scope list and a harness check that the scopes sum to the surface's time within 5%.
  - [ ] Locate the capture step's 4x cost on Vulkan at 4K on a quiet GPU (`nvidia-smi` recorded with the figures),
    by scope: the nearest pass reading the multisampled D32F, the depth's layout switch (shader read to attachment,
    rule C's prime) before the second run, the second run's load of the multisampled attachments, the second colour
    resolve. Each candidate gets a harness control that removes it (with its pixels judged) before any fix.
  - [ ] Fix what the scopes show, if it brings Vulkan's 4K 4x minus 1x to the Python path's or below with parity
    exact and validation clean; otherwise the figure and its cause go to the lead with the operator's look question
    (4K defaulting to fewer samples).
- [ ] N3.3 leftovers: checkpoint audit 5's findings that D16's "As built after checkpoint audit 5" leaves to the plan
  (their boxes were lost in the 15 Nov merge 36faada69; still open in source, 20 Nov). Before the first compute consumer
  (N5.4, N5.6):
  - [ ] L2, a trigger consumed by a record that dispatches nothing: `ModeContent::decideDispatches` advances
    `lastTrigger`, `dispatches` and the fresh key before `recordCompute` may skip the entry (no pipeline, a group count
    of 0, groups past the device's limit). Decide the groups and the pipeline in `decideDispatches` and advance only an
    entry that dispatches; proof: a field-triggered stateful entry whose named group count is 0 for one record keeps
    that record's step for the next, control on the pre-change module.
  - [ ] L3, dispatch totals: only each dimension is bounded; the product of three admitted group counts is not (three
    record counts under at_most 65535 admit 2.8e14 groups, a TDR from an owner bug). Bound the product at admission and
    per record, refused at its edge as the per-dimension limit is; GPU-free test and a harness case refused with its
    reason.
  - [ ] L4, an image's zeros: `compute_passes.cpp` zeroes a storage image from one host `QByteArray` of a whole slice on
    the render thread (up to 256 MiB under `kMaxStorageImageBytes`). Upload them in bands of rows from one bounded block
    of zeros, proved by the copy round's zero reads on a 2D and a 3D image larger than one band; and decide whether
    `UsedAsTransferSource` (only the harness's readback needs it) stays on every storage image.
  - [ ] L5, the harness readback reaching the product: `NativeMode.read_storage` and `storage_data`
    (`rendering/native/mode.py`) are the harness's only; a test that no module under `rendering/`, `widgets/`, `core/` or
    `ui/` calls them, with its control.
  - [ ] M3's draw-side form: one render pass reading a storage buffer two ways (as `storage` and as `instance_from` or
    `indirect`, in one draw or two draws of a run) is admitted, and QRhi keeps one access a resource a pass. Refuse it
    at admission with the reason (or split the run), proved under validation with shader accesses on.
- [ ] N3.4 Transparency and post-processing (D17): source/proof complete; remaining investigation is non-blocking
  (operator, 16 Nov). Consumers retain their own parity, lifecycle and measured-cost requirements.
  - [ ] At Qt upgrades, recheck the private QRhi outside-pass `beginExternal`/`endExternal` contract against Qt source.
  - [ ] Non-blocking, deeper investigation by another agent: use R-232's retained timings, source/trace controls,
    failed avenues and unresolved hypotheses; choose one discriminating gather/control-flow or native-submission
    falsifier before running. Keep detailed evidence and machine conditions. Hardware counters are optional;
    profiler repair is not a prerequisite. No production barrier or tracking exception without proof. If a cause
    is established, verify the repair with both-backend `defocus_cost` and parity; this task does not hold consumers.
  - [ ] Awaiting Validation before a Waveform consumer: repeat `mesh_buffer_check.py --rounds stream_ring` on a quiet
    GPU, record load/clocks before and after, and review median margins plus the D5.3 tail watch. The available-GPU
    proof validates the harness, not quiet-GPU performance admission.
- [ ] N3.6 Lifetime (Opus High agent ab5da4c3c451f82c5, 21 Nov; built ABI 30 at e21923f1c, all three boxes pass on
  the build, branch head ebfe0944a; checkpoint audit by Opus High agent af5a9a2f30c88158c before merge): lazy creation on first use, release at retirement and at a mode switch, device loss rebuilt
  from the last packet, every state combination a pipeline built ahead and warmed gradually (Qt's pipeline cache
  file on Qt's pipelines; the core's own cache for raw ones); the working-set and GPU-memory readings of the P2
  audit rerun on it. On a lost device the Vulkan backend's `VK_EXT_device_fault` detail (vendor fault codes and
  addresses, Qt 6.12) is logged once, so a lost device on a user's machine is diagnosable.
  Decided by the lead, 15 Nov, from the research doc's sections 10 to 12:
  - [ ] Pipeline cache: pipelines the core builds on Qt's QRhi share Qt Quick's cache file, so they need nothing of
    their own. The job thread's QRhi and any raw Vulkan pipelines get one core file beside Qt's
    (`<CacheLocation>/qtpipelinecache-<abi>/srpss_core_<backend>`) with the same header check (driver version,
    vendor, device, cache UUID). A mismatch is a silent recompile. It is loaded at creation and saved at orderly
    shutdown, written to a temporary file and renamed, so two windows or processes never leave a torn file. The last
    writer wins, as with Qt's.
  - [ ] Defect (lead, 22 Nov, operator asked "No Vulkan pipeline cache?"): Qt Quick's Vulkan cache file is never
    written for SRPSS (`%LOCALAPPDATA%/ShittyRandomPhotoScreenSaver/SRPSS/cache/qtpipelinecache-*/` holds `qqpc_opengl`
    and the core's job-thread `srpss_core_vulkan`, no `qqpc_vulkan`), so every pipeline the core builds on Qt's QRhi
    (nearly all mode and transition pipelines) compiles from scratch on each Vulkan launch, a likely share of first-use
    stalls. Find why (Qt's automatic cache off for an adopted device, `QQuickGraphicsConfiguration` settings, or the
    exit path skipping `finalizePipelineCache`) and fix at the owner: either Qt's file is written, or the core's file
    also carries Qt's QRhi's `pipelineCacheData()` (load at creation, save at orderly shutdown, same header check).
    Proof: a second Vulkan launch's pipeline creation times (first frame of each mode and transition) against the
    first, file present and absent; a control with the file deleted.
  - [ ] Device loss: the core owns the `VkDevice` Qt adopts, and Qt's recovery re-adopts the same device. So on
    `sceneGraphInvalidated` after a loss (`FrameOpDeviceLost` or `VK_ERROR_DEVICE_LOST`), the core destroys its dead
    device and hands the window a new one before Qt's next frame. Then it rebuilds every core object from the last
    packet. Settle the threading of `setGraphicsDevice` from that slot in the harness first. The proof is a
    harness-only module entry that forces the lost path (no env flag), on a hidden host, followed by a frame equal to
    one before the loss. On OpenGL the loss is detected only through a failed `makeCurrent`; the same rebuild
    applies.
  - [ ] Release timing: retirement calls `deleteLater` at once. The two-frame lag on Vulkan, and one frame on
    OpenGL, is accepted. Where no frame will follow (window retired, saver exit), the core calls `QRhi::finish()`
    at that edge, outside any frame; never mid-frame, which blanked Vulkan presentation in d1_run on 14 Nov.
    Raw Vulkan objects go to a deferred-delete queue keyed to their frame slot's fence, drained at device idle on
    teardown.
  Checkpoint audit 11 (21 Nov, `Docs/Future_Work/Checkpoint_Audits_Nov21.md`; N3.6 merged at ABI 30, b056a212c; M1-M3,
  L1-L4 with Opus High agent a8797a6d7c59d45af):
  - [ ] M1: a harness-only real loss: Qt's own QRhi must report `isDeviceLost()`. For example, the hidden host's
    device-function table answers `vkQueueSubmit` with `VK_ERROR_DEVICE_LOST` once, with no environment flag. Then rerun
    the rebuild round with `qrhi_lost` true and `faultReport` present. Or the lead records the window record's loss slots
    (Qt's threaded loop) as accepted unproven.
  - [ ] M2: a failed `vkCreateDevice` in `replaceDevice` is retried (for example, at the record's next frame edge or
    expose while `device_swapped` is false) instead of leaving the window black. Proof: M1's injection plus a forced
    create failure.
  - [ ] M3: the rebuild round also crosses a loss with a mode program that has storage, a scene target, bloom and
    meshes, with Spectrum, and with the background layer and a backdrop. Each frame after the loss equals the frame
    before it.
  - [ ] L1: `rhi_owned.h` states that a wrapper is retired before its QRhi, always: `deleteLater` on a never-created
    wrapper after its QRhi went is a use-after-free in Qt 6.12. `device_loss_check.py` proves that no core wrapper is
    live after `sceneGraphInvalidated`.
  - [ ] L2: a lost device's destruction tells its job service that the device was lost before `stop()`, so the job
    teardown never saves a lost device's cache (today it trusts the job thread's own observation).
  - [ ] L3: a failed cache-file commit is a reported skip, not red in `pipeline_cache_by_rule`, and the plan's "last
    writer wins" says "some writer wins". Run the real-blob round trip when the job QRhi's first pipeline, or the first
    raw `VkPipelineCache`, exists.
  - [ ] L4: `device_loss_check.py`'s release docstring drops the ABI 29 control it never ran; the OpenGL
    `no_wait_inside_the_frame` check is dropped or marked informational.
  - [ ] L5: at each Qt upgrade, recheck `QQuickRenderControlPrivate::resetRhi` against Qt source: its signature, and
    that `initialize()` reassigns `QQuickWindowPrivate::rhi`.
  - [ ] L6: the parent box's lazy creation, mode-switch release, pre-built and gradually warmed pipelines, and P2
    working-set/GPU-memory rerun are still open. They are not on the audited branch.
- [ ] N3.7 The orientation and quarter-turn contract (the scene frame's rotation in the composite) and the
  Expanded Visualizer's display-size targets at 4K (the M6 budget).
- [ ] N3.9 A display move keeps a mode's GPU-held history (1C.2, plan 01 M3c "Display moves retarget the live
  owner"): with one device per window (D6) nothing is shared, so the handoff is a copy through the job thread (D9)
  from the source device to the target's before the target integrates again; a test equal to an uninterrupted run
  (Extruded Bubble's drift first, N5.6).

**N4. Shared primitives, each against its Python harness, each ported just before its first consumer below
(the unconsumed ones on the primitives track)**

- [ ] N4.b Ribbon and strip (the bounded history buffer, centripetal placement by continuous index, the
  camera-facing width variant, multi-ribbon): Waveform Ribbon.
- [ ] N4.c Compacted populations (sprites and streaks, bounded lifetimes and emitters, compute-driven
  arrangement). Used today by the Disintegrate and Volumetric Dissolve transitions only. **High potential.**
  - [ ] The two transitions port 1:1 on QRhi's own indirect draw (Qt 6.12: `QRhiCommandBuffer::drawIndirect` for
    `scene3d/population.py`'s `glDrawArraysIndirect`; D5.3's indirect service is retired). "Draw the maximum, cull
    in the vertex shader" is built only as the path for a backend that does not report `QRhi::DrawIndirect`.
  - [ ] The port queries `DrawIndirect` and `DrawIndirectMulti` at runtime and records each backend's answer
    (`DrawIndirectMulti` is expected on Vulkan 1.1+, GL 4.3+ and D3D12 only; elsewhere Qt issues separate draws).
  - [ ] D8 plus 7, a QRhi-only build: the harness at one million sprites, the indirect draw against the cull path,
    same pixels, cost recorded.
- [ ] N4.d Planar reflections and rough receivers (Waveform's floor), the scene probe (Extruded Bubble),
  wet-surface masks (high potential). Neon Lake's water reflection is analytic in its own basin shader and needs
  none of this.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 15): a cube renders as six passes, one render target per face (`setLayer`);
  multiview cannot render into a cube. Rough-receiver prefiltering is the core's own shader, never `generateMips`
  (a linear blit chain). The harness reads every face back on both backends first: face orientation may be
  mirrored between OpenGL and Vulkan.
- [ ] N4.e Heightfields and refined terrain meshes (the authored heightfield resource; Neon Lake's tile-refined
  basin; the grid a dynamic surface field will share).
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 16): vertex-stage sampling uses the binding's `VertexStage` flag with
  `textureLod`/`texelFetch` (QRhi has no feature flag for it); the heightfield is R16F or R32F read with
  `texelFetch`, so 32-bit float filtering is never required.
- [ ] N4.f1 The fog volume port (Waveform draws it today, so N5.4 cannot reach parity without it): ported just
  before its first consumer, N5.4, like every N4 item. The fog detail march (written and tested, runs nowhere in
  production: too costly at full size in the Python path) is the base of N6.3 and stays with N4.f2's reduced path.
- [ ] N4.f2 (placed after N5.6 and before Expanded Visualizer M6, see below) Reduced-resolution volumes and P4's
  mixed-resolution soft layers (D8 plus 4): bloom, reflection blur and wide glows at reduced resolution with
  depth-aware upsampling; lines, dots, rims, particles and UI stay at full resolution.
- [ ] N4.g Edge and propagation fields (the Edge Bloom and Capillary Bloom transitions only); sphere impostors,
  shared optics and underwater light (Extruded Bubble).
- [ ] N4.h Shared shadows (one fitted directional depth map, bounded soft filtering, caster and receiver
  admission, measured tiers). **High potential: built without a consumer**, proved on a harness scene; not a
  revival of the rejected Extruded cast shadows, and no mode turns it on without its own review.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 13): comparison sampling through `QRhiSampler` compare ops on a depth-only
  pass (legal on both backends). The shader branches on `isClipDepthZeroToOne()`. Depth bias is tuned per backend
  and measured, never one shared number (the offset unit is implementation-defined, and Qt sets Vulkan's bias clamp
  to 0). Outside the light frustum is handled in the shader (no clamp-to-border in QRhi).
- [ ] N4.j Backdrop environment (`BackdropEnvironment`: Extruded Spectrum and Sphere's wallpaper reflection), with N5.3;
  the photo half landed with N5.2c (ABI 36).
- [ ] N4.k Light shafts: the shared owner (Neon Lake today) and Extruded Bubble's own second implementation
  merged onto it, one owner (high potential); ported with Extruded Bubble, then used by Neon Lake.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 17): volumes are written by compute (one pass, D16), never by per-slice
  rendering (one pass per slice, and Vulkan 1.1 instance API for slices).
- Topology rule for every N4 primitive (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 18): triangle lists or degenerate strips, never a restart
  index (OpenGL restarts every topology, Vulkan only strips); no wide lines (false on the OpenGL core profile);
  lines and points are instanced quads (D15).
- [ ] N4.l Silhouette shadows (Extruded Spectrum's directional silhouette and Sphere's own pass) as one shared
  primitive, distinct from N4.h; the bendable grid (Membrane, Page Curl); Exploding Tiles' planar shadows and
  particles.
- [ ] N4.m The soft-light array (up to 96 soft lights, `rendering/gl_programs/lighting.py`; written, tested, used
  by a lab only). **High potential: built without a consumer.**

**N5, modes track (one High slot; each box is one port under the port rule)**

Slots (lead, 12 Nov): the first port of each kind, and the heavy 3D ports (Waveform Ribbon, Extruded Bubble, Neon
Lake, Extruded Spectrum and Sphere), go to Opus High. Once Spectrum (N2.5) has proved the pattern, the simple modes
(Spline Curve, Oscilloscope, Bubble) go to Opus Medium, proved frame by frame against the Python renderer with the
identity harnesses. A difference that is not byte for byte goes back to the lead to judge. An audit reruns the port's
negative controls and one take per backend from the cited evidence; it never repeats the full parity sweep.

Rule for every port here (Qt 6.12): where a mode's small instanced batches (bars, specks, snow, sprite families)
are measured above a handful per frame, one pipeline and one indirect call with `QRhi::ShaderDrawParameters`
(`gl_DrawID`, `gl_BaseInstance`, `gl_BaseVertex`) replaces a draw per batch; the port records which backends report
the feature (D3D11 is not stated).

- [ ] N5.1 Spline Curve leftover: its Studio is not offered on Vulkan (`STUDIO_PREVIEW_BACKENDS`), the same open
  item as Spectrum's; both close with N5.8.
- [ ] N5.1 Oscilloscope (registered on the route and offered on Vulkan, 21 Nov; N3.4 bloom's first consumer). Python oracle:
  `rendering/quick/visualizer/implementations/oscilloscope.py`, `rendering/gl_programs/oscilloscope_program.py`; follow
  `Docs/Guides/Native_Port_Playbook.md`, proof under `Docs/Guides/Native_Parity_And_Timing_Proof.md` (section 7's split);
  harness `native/core/python/oscilloscope_check.py`. Built through ABI 29 (D12 "As built: Oscilloscope", "The pixel
  tolerance"); rule (a) passes all six 60 s takes and 14 of 15 offers, layer L identical, cost round passed
  (b8c6c3528). Evidence `n5_1_oscilloscope/` (`20261121_owner_offers_class/`, `20261121_n51_turned_abi29_band/`).
  Open parity and offer boxes: one line in the Backlog section (Oscilloscope parity and offers).
  - [ ] Side defect (found 20 Nov by the port): the legacy `widgets/spotify_visualizer/shaders/oscilloscope.frag` (and
    its `.qsb`) is drawn by no renderer (its own header says so; the beam files are the mode's shaders now), yet it is
    still the mode's registered fragment (`shaders._ALL_SHADER_FILES["oscilloscope"]`): `preload_fragment_shaders`
    composes it at startup, the route's `_ModeContent.load` reads its pack at every Oscilloscope bind (the program
    ignores it), and `generic_mode_check.py`'s product-pack round admits it as "the Oscilloscope's" pack. Retire it with
    its registry entry once the route no longer reads a mode's pack for a mode with its own program, and move the
    harness's admission check to the beam's packs.
  - [ ] Side defect (found 21 Nov by the turned-card agent): Python's `item_pixel_rect` (`rendering/quick/scene3d/
    frame.py`) gives the item one device pixel more than its size at some whole-pixel origins: a card 641 x 361 at
    (803, 517) in a 1920 x 1080 window at dpr 1 gets a SceneTarget rect 642 wide (at (801, 515) it is 641; at (800, 512)
    641 x 362), so its float32 snap misses an edge that is a whole pixel. It is the oracle the card's `scene_item` copies,
    so both renderers agree, but the SceneTarget is a pixel larger than the item. Reproduce: `_card` and
    `_pythons_scene_rect` of `tests/test_native_oscilloscope.py` with `viewport_extent=(641.0, 361.0)`,
    `outer_origin=(803.0, 517.0)`, dpr 1.
- [ ] N5.1 Bubble (registered on the route, offered on Vulkan; D12 "As built: Bubble"; statistics and eliminated
  suspicions `Docs/Future_Work/Native_Bubble_Parity_Investigation.md`; tools `Docs/Guides/Native_Bubble_Diagnostics.md`;
  follow the Native Port Playbook; no further tolerance widening). The long-take current-rule rechecks cleared the three
  steady failures. Layer T and the current-source replay of the tracked scene-fade inputs remain open.
  - [ ] Layer T on Vulkan (lead, Display 1): first runs 20 Nov match the Python OpenGL control in median and p90 and
    in tick-to-publish; the tail is heavier (frames over 16.7 ms 27, 39, 27 against 11, 16, 18), all of it after
    rendering ends, not sync or recording. Evidence `.artifacts/evidence/visualizers/{bubble,spectrum}/live_check/20261120_*`,
    `.../bubble/live_check/20261121_layer_t_root_cause/figures.txt` (agent aac773583ad93e2ab).
    - [ ] Attribute the residual Vulkan late frames at the Qt request and frame boundaries. The 23 Nov paired HUD
      suppression showed no consistent reduction. Compare the request-to-frame gap with recorded GPU clocks when
      the residual repeats. Measure GUI sync before considering changes there. See the timing receipt in
      `Docs/Future_Work/Native_Bubble_Parity_Investigation.md`.
    - [ ] Fix at the owner if it is ours, then three Vulkan runs and three OpenGL controls back to back; accept when
      Vulkan's late frames fall within the control's spread. If it is the driver's or Qt's, record it in D12 and ask
      the operator. Then Bubble's own T tools (its diagnostics guide).
  - [ ] Attribute the remaining non-isolated masked tie verdict at mode-switch input 337 for offer directions 2 and 6.
    It persists after R-242 at display and overscan. Check the fade values at the owner and the composite edge before
    changing either path. Use the proof in `Docs/Future_Work/Native_Bubble_Parity_Investigation.md` and retain the
    operator's intended fullscreen density and breathing improvements.
  - [ ] GPU median and p90 per pass at 2560 x 1440 against the Python renderer's (checklist 11); 4K is measured (D12).
  - [ ] Ambience-off reads higher than ambience-on at 4K: variant b differs from variant a in many settings, so measure
    one frame with only the ambience switched (`bubble_check.py` `COST_RUNS`).
  - [ ] Native OpenGL is about 5 % slower than the Python renderer at the full 4K frame: input to the optimisation gate.
  - [ ] Conditional optimisation gate (operator, 16 Nov; after accepted parity and the per-pass cost check, before
    N5.4 and NF): name the measured Bubble-owned cost and its baseline first; a no-change result closes it. Full
    text (baseline, music matrix, exact-fidelity and speed proofs) in the Backlog section.
  - [ ] The D1 rehearsal (lead, rule (f), D10): one bounded Vulkan run on Display 1 through `tools/d1_run.py`, the
    Usu wallpaper and a recorded clip, ambience on and off. Deferred 17 Nov: Display 1 was off (`--list-displays`
    showed Display 0 only); run it when Display 1 is on.
- [ ] Non-blocking (does not hold the Bubble port): prove Bubble's rule-(a) scatter is the two-compiler case directly.
  Render Python's Bubble with the GLSL the qsb pack emits (the pack's GLSL variants in place of the composed source)
  over the `replay` recipe and show the steady residual collapses (from 2,430 one-level pixels, worst 34 a frame).
- [ ] Bubble optimisation proof gap: needs the fast long-clip proof's layer P tool (the box below) before the
  first Bubble optimisation; the rules are the guide's.
- [ ] Audit the fast-proof merge 79a5d1fe7 (Opus Medium audit agent a8810319889f3a218, 21 Nov): `tools/pixel_tolerance.py`'s M1 groups
  and density, the cheaper judge's equal-verdict proof, the reference cache key, the native-only and stream-player
  paths, and layer L's coverage of positional members.
- [ ] Build the fast long-clip proof (Opus Medium agent a6257c36aeee45f10, 20 Nov; method and rules:
  `Docs/Guides/Native_Parity_And_Timing_Proof.md` section 7):
  - [ ] Layer L built (e0275205c): `tools/visualizer_replay/native_record_identity.py`, test
    `tests/test_native_record_identity.py`; evidence `.artifacts/evidence/native_core/fast_proof/20261120_l_*`.
  - [ ] Layer P built (ddb3dc8b2, ec0bf3feb, 12a688e57, d0b2e8095, 29fc590c0): cached references
    (`tools/visualizer_replay/python_references.py`), native-only `--against`, `native_stream_player.py` for Vulkan
    (generic modes only; Spectrum's own item is not played yet), `--judge-workers`. Evidence `fast_proof/20261120_*`.
  - [ ] Coverage selection built (b4cd47802): `tools/visualizer_replay/coverage_windows.py`, test
    `tests/test_coverage_windows.py`; evidence `fast_proof/20261121_coverage_bubble_<take>/`.
- [ ] Waveform travel-speed reactivity (operator; after N5.4's acceptance, additive to its native record): the mesh's
  travel has no reactivity control for its speed. Add ONE range slider (two handles): its low end is the minimum
  speed at the least energy, its high end the maximum speed at the highest energy, and the speed between follows
  the overall music energy (wired to real energy, calibrated on recorded music, never pinned at either end). Attack
  is faster than decay and the decay is gentle (both exposed as options with those defaults). Check for a missing
  base speed and idle speed; audit these controls so they complement rather than conflict. Every preset's default stays exactly what it is now (Settings spec system,
  `core/settings/visualizer_mode_settings.py`); reaction check with `waveform_music_response.py`.
<a id="n5-6-extruded-bubble"></a>

- [ ] **N5.6 Extruded Bubble native port**
  - Port D4 drift compute, transparency and HDR, background capture and depth, probe and defocus, N4.k light
    shafts, and N4.g impostors and optics.
  - The [native port playbook](Docs/Guides/Native_Port_Playbook.md) owns shader and pass contracts.
    The original source reading is in `git show 644c18cb3:Current_Plan.md` under N5.6 → Reading. It inventories
    per-frame and on-change fields, stream sizes, pass order, formats, clears and turn handling. Verify paths and
    limits against current source. Use Extruded Bubble's own references.
  - References (all 18 runs drawn and stored 27 Nov, frozen adaptive settings, single sampling and masks): root
    `D:/Temp/Scratch/SRPSS/fast_proof/eb_n56_r251`, receipts `.artifacts/evidence/native_core/n5_6/20261127_refs_<take>/`,
    earlier ones in the [compact reference indexes](.artifacts/evidence/native_core/n5_6/20261123_r251_reference_indexes.zip).
    Keep the reference producer at its verified rendering and logical revision for the native comparisons. The keys
    that get late coverage windows (drift direction, collision scope, audio block size) draw their whole-take
    references with the Coverage windows box.
  - [ ] **Native record and route.** Use the [drift metadata proof](.artifacts/evidence/native_core/n5_6/20261123_drift_projection/report.md)
    and the source reading for field and resource ownership. **ABI 46 reserved** for this box (27 Nov, Opus High;
    agent id under "Live agents"). Agents never build: when the C++ for the first three sub-boxes is written and
    committed (with its Python side and tests that run without the new module), stop and report "ready for build";
    the lead builds the branch on GitHub (`build_runner.py --mode github --run --select native_module`) and resumes
    the agent with the module for the L proof (or, if its context is past about 200k, a fresh successor from the
    branch and journal; handbook 7a). At most two replay or identity processes at once. Audit: Opus High
    at merge (core concurrency).
    - [ ] Give the main process ownership of the named D3 mapping. Pass the name and identity to the worker and
      core. Finish each bank's seqlock write before `PacketMailbox.publish` exposes its key. Reuse a bank only
      after `consumed_sequence` acknowledges a successor with a different key for that family. Preserve the
      predecessor on rebase. If all candidate banks are live, defer publication and keep the projected lineage
      at its last published revision. Verify that edge, resize, retirement and replacement. The
      [ABI 45 D3 fixture](.artifacts/evidence/native_core/n5_6/20261123_n56_geometry_projection_checked/report.md)
      proves the reader with the harness writer.
    - [ ] Pack the native compute step/knot streams. Exercise repeated records, short gaps and the restart edge.
    - [ ] Complete the worker record, the mode program, and its `native_record_identity.MODES` entry with passes,
      read spans, streams and positional members. Prove L frame by frame for each take and graphics key with
      `native_record_identity.py --mode extruded_bubble --recording <take> --seconds <30-or-60> --run <key>
      --deliveries D:/Temp/Scratch/SRPSS/n56_deliveries/l_<take>_<key>`.
      28 Nov (successor `a29135bafeaab65bb`, `3df2b64fd` MODES entry and identity tests, `14d763931` C++ ready for
      build, ABI 47): smoke IDENTICAL (359 frames). The only L difference over 15 runs is signed zero: Qt's JSON
      stores `-0.0` as integer 0, so the native settings path dropped the sign Python packs (`uLightEnd`, stream and
      speck source/end, light_type 0's travel/axis). Fixed in the transport (`settingNumber` reads `"-0"`;
      `settings_json` writes it), not in the frozen Python producer (`7f9f002d8` reverted in `853dbb0b3`). All 15
      runs redo on the rebuilt module (scripts in that worktree's `.artifacts/scratch/n56rr/`); then the R-NNN entry
      (silent since settings went through JSON).
    - [ ] Side defects (agent, 28 Nov; fix or rule on them before merge):
      - `consumed_sequence` shows the main process took a frame, not that the core read it; a missed frame can
        find its bank rewritten. ABI 46 holds the step (late geometry, never wrong bytes). Hold proved on the built
        module (`3fd93cc3a`, `20261128_abi46_hold/summary.json`); open: whether it ever fires on the long takes (L runs).
      - Done (`950465ab3`, test seen failing): the arena prepared for a pending mode change closes with the link.
      - Registering the mode needs `program["buffers"]` passed to the item in `rendering/quick/visualizer/native_route.py`.
        Edit it: the "hash" is only Bubble's evidence provenance (`_bubble_native_components.py` records its sha256),
        not a lock; Bubble's next component receipt simply carries the new hash.
      - Known approximations to rule on with L and P: a rebase's old steps run at the smaller capacity; the
        `drift_out` relayout edge; the probe cube has no depth; a held geometry key leaves draws reading stale
        `drift_out`; the near layer's edge with no shells.
        L never reaches them (it runs without a worker or arena, and every L frame had shells); they and the ABI 46
        hold's firing on long takes go to P and T.
      - The whole drift window per record is up to 384 KB (limit 2 MiB); E8 slot shrink still open.
  - [ ] **Coverage windows.** Use `coverage_windows.py --mode extruded_bubble` with late windows in each take's
    last 15 s. A gap over 128 drift steps (about 1.4 s) resets history. On the native player use the ABI 42 draw
    skip and dispatch drift from cold start; confirm continuity and the restart control in `WARMUP_INPUTS`.
    A Python reference with a late window needs the whole take for that key. Decide which 30 s alternates need
    that full draw before starting them. Drift direction 0 and 2–7, collision scope 0 and 2, and audio block
    sizes 0, 2 and 3 need coverage windows for their record/settings changes.
  - [ ] **P, T and C, then register.** Follow the [proof guide](Docs/Guides/Native_Parity_And_Timing_Proof.md).
    - Lead, 28 Nov: the rest of the rule (a) failure came from the harness comparing the 4x scene against Python's
      single-sampled one (`19d5525ea`), plus the defocus gather mirroring its taps for EB's bottom-up near layer
      (`89c3ceca8`, C++, building). Input 0's undrawn native first frame (252k px, max 211) is **not excluded**: find
      and fix the cause (a first frame must fade in, never be missing). Side defects to fix in this box: the
      in-process (no worker) drift arena gap; lens shift hardcoded to (0,0) (make it settable so the odd-target
      bullet can test it); the core's missing guard against a pass mixing blended and unblended attachments (C++,
      refuse with a named error).
    - [ ] First (lead, 28 Nov): the Python reference key. `python_references._source_files` hashes the whole
      `rendering/quick/visualizer` package, so a native-only edit (`native_route.py`, `8c0cbad9c`) re-keys every mode's
      references, and N5.6's 18 references sit at three producer revisions (12 `23f88094`, 5 `eb776f4d`, 1 `9d34c13b`).
      Decided: key each reference on the repo modules its drawing process actually imported (recorded with the entry;
      a lookup rehashes that recorded set; a new import arrives through an importer whose bytes changed), plus the
      composed shaders, QML and harness sources as now. Native-only files then never enter. Tests: a native-only edit
      keeps the key, an edit to an imported Python module changes it, each with its control. Re-key once; redraw
      only the references whose recorded sources really differ, at one revision (a pure run, Haiku/Sonnet if separate).
      Then the native player and its `owner_render_parity --native` entry (pattern: `native_record_identity.py`
      registration near line 436).
    - [ ] Verify shaft and backdrop placement through the complete route at nonzero lens shift and odd,
      padded targets. The [ABI 45 component proof](.artifacts/evidence/native_core/n5_6/20261123_abi45_matrix_and_targets/report.md)
      validates the writer, blur and sampling. Reuse the core's scene-item matrix for the backdrop vertex under
      the bucketed scene, and compare the final composed frame.
    - [ ] Check the largest framed aperture against `defocusReadLevelCap`, the turned-card composite and bloom,
      and the display-move drift-history contract in N3.9.
    - [ ] Decide whether to omit the scene depth and resolve in both renderers with equal-frame proof. The scene
      holds depth clear 1 and drops the captured depth. The depth-backed glass shaders still write fragment depth.
    - [ ] Repeat the [recorded stream-speed trace](tools/visualizer_replay/extruded_bubble_music_response.py) on the
      Python and native routes with the frozen takes and settings. The 22 Nov before-state is under
      [the archived 22 Nov response trace](.artifacts/evidence/visualizers/extruded_bubble/music_response/20261122_onscreen.zip).
- [ ] N4.f2 (the reduced-resolution layers; Waveform and Extruded Bubble are native), then Expanded Visualizer M6
  (4K acceptance, plan 01) may run.
- [ ] N5.5 Neon Lake (N4.e, N4.k, instanced quads for its marks, its own analytic water reflection; its reaction
  and growth are uniform arrays).
  - [ ] First, before any port reference is recorded (operator, 21 Nov): the terrain's sharp, block-like judder. On
    Preset 1, terrain near the camera jumps up or down suddenly instead of moving smoothly. Likely visual, not design.
    Root-cause on the Python side (where the height steps: the published field, its interpolation between frames, the
    grid sampling), then smooth the motion there without smoothing the audio or deadening reactivity: the same peaks
    and troughs, reached less sharply. Prove it with `neon_lake_music_response.py` before and after on a recorded take
    (peak and trough heights kept, frame-to-frame height steps reduced) and a focused test with a control on the old
    code; then the port's references are taken.
  - Reading (reference; Sonnet agent ac4e1a1c9d1ad93c4, 21 Nov, merged), as Waveform's and Extruded Bubble's readings: the
    record per frame and per Settings or card change, stream size rules, every pass with its targets and formats, how
    it turns, its clear; then what the port needs that the ABI 29 core lacks beyond the Waveform and Extruded Bubble
    boxes (one C++ box each, with what its proof must show) and which of theirs it shares. File:line for every claim.
    Neon Lake's persisted id is `shockwave_grid`.
    Reading (Sonnet, 21 Nov, no code touched; sizes measured with a probe over the real mesh builders). `ng.py` is
    `rendering/quick/visualizer/implementations/shockwave_grid.py`; `basin.py` is `rendering/gl_programs/neon_lake_basin_program.py`;
    `target.py` and `shafts.py` are in `rendering/quick/scene3d/`; `mc.h` is `native/core/src/mode_content.h`; `D15` etc. are in
    `Native_Core_P3_Decisions.md`. Neon Lake has no compute, no storage image, no reflection target (its water reflection is the
    basin mesh drawn again mirrored, `ng.py:609-621`, `basin.py:507-511,694-706`), no depth texture, no HDR, no OIT.
    - Per frame from the logical frame (`ShockwaveGridFrame`, `widgets/spotify_visualizer/render_state.py:405-430`, on Spectrum's
      payload): the bars (at most 64, scaled by 0.55 at upload, `ng.py:388-389`, `rendering/quick/visualizer/implementations/spectrum.py:127-155`),
      peaks, the onset ring (age, x, z, strength; at most 48, `rendering/gl_programs/shockwave_grid_program.py:27`), the five terrain lane
      drives, their phase and the Growth and Indents drives, the animation time, the content fade. The Settings parameters ride
      frozen in the same frame.
    - Per frame in the renderer today, so for the worker to publish (D5.5, the N0.4 box): the newest 16 live events as records
      (`ng.py:390`, `shockwave_grid_program.py:23,191-196`), the mid-band mean (`ng.py:392-394`), the beat pulse (`:397-398`), the music
      drive (`:402`, `shockwave_grid_program.py:148-174`), the camera with its terrain-floor eye (`ng.py:200-209`, `basin.py:89-113`: it
      reads the terrain's cells round the eye, so the worker needs the terrain it already holds as a parameter), the Sun or
      Moon placement at infinity and its orbit (`ng.py:303-333`), the beat-star cells (up to 24 vec4, tested against the terrain
      and the body, `:438-452`, `rendering/gl_programs/neon_celestial.py:115`), the shaft light (`:718-727`), the halo light (`:730-735`),
      the cloud and nebula time terms (`:325-332`), the scroll, the idle swell and the wave terms (`:272-274,466`), the
      reaction-off flag when nothing drives the land (`:282-285`). The record is a few hundred bytes (events 16 x 16 B, 64 bars):
      no slot pressure.
    - Per Settings or card change only: the tier's samples, glow and mesh cells (`ng.py:94-104`; High 4 samples and 192 cells
      clamped to 180 x 120, Balanced 2 and 128, below single-sampled, `rendering/gl_programs/scene3d.py:81-92`,
      `shockwave_grid_program.py:29,54-58`), which stages exist (marks `ng.py:677`, sky `:710`, rays `:738`, glow), the three programs'
      blocks (about 100 uniforms: 5,488 B basin, 4,576 B skyline, 5,232 B sky; arrays `uBars` float[64] `basin.py:172`, the reaction
      lanes, bias and bands float[160], [32], [5] `rendering/gl_programs/neon_terrain_reaction.py:165-169`, the baked shaper
      tables `ng.py:681-699`), the terrain's adoption (`:167-176`), the mark diameter in pixels from the item's matrix
      (`basin_pixel_scale`, `ng.py:608`, `basin.py:36-44`: a card-derived value).
    - Meshes and textures (no per-frame bytes): the basin is non-indexed triangles of vec2 (`neon_lake_basin_mesh.py:97-154`), 385,320
      vertices = 3.08 MB at 180 x 120, 168,264 = 1.35 MB at 90 x 60, 78,864 = 0.63 MB at 40 x 27, keyed by the tier, the origin's
      reach and the painted tiles (`ng.py:136-154,664-669`); the marks are its unique vertices, 51,939 = 415 KB at 180 x 120, ten
      percent more with Wire Display's vertices (`ng.py:98-103`); the sky is a one-cell grid (`:242`). The terrain is a float32
      heightfield of at most 257 x 257 (`rendering/gl_programs/heightfield.py:16`): the stored cells RGBA32F (R height, G bank
      distance, B and A unwritten: 1.06 MB, `rendering/quick/scene3d/heightfield.py:59-62`; N1.7: QRhi has no RG32F) and, for a grown
      grid only, the overlay R32F (264 KB, `ng.py:132,182-185`), each uploaded once per data and released when the overlay goes
      (`heightfield.py:45-49`). The events are one std430 storage block at binding 3 (`ng.py:51,516`).
    - Passes of a frame in order (`ng.py:413-593`; one scene target, overlay, multisampled): 1 sky background (`:520-529`,
      depth test off, mask off); 2 depth-only prepass of the basin mesh, only with a Sun or a sky (`:531-540`, depth less, write on,
      blend ZERO, ONE_MINUS_SRC_ALPHA on colour and on emission, `:743-764`, to subtract the covered sky); 3 the mirrored basin,
      lines only, and 4 the mirrored marks, only with Reflection above 0 and the eye above the water (`:544,609-621`, depth always
      after a prepass, write off); 5 the surface (`:622-630`, depth less-or-equal, write on) and 6 the marks as `GL_POINTS`
      (`:631-633,640-645`); 7 the skyline, the basin mesh again with a displaced vertex stage (`:549-567`, `basin.py:1077-1190`, less-or-equal,
      write off); 8 the Sun or Moon body (`:568-577`, skyPass 2, `gl_FragDepth` 0.999999, `basin.py:1335`); 9 the shaft source (`:578-593`,
      skyPass 3, only while the body is in front of the camera, `gl_FragDepth` 1.0, `basin.py:1222`, written alone into attachment 2:
      `target.py:595-614`). On leaving the scope (`target.py:937-1013`): the shafts, a half-allocation downsample resolving the samples
      and two 16-tap radial gathers (`shafts.py:116-153`, three draws on two R16F targets), the emission's bloom chain
      (`target.py:966-968`, strength 1.4 x Glow, `ng.py:413`), and one composite of the scene with glow and shafts added
      (`target.py:228-277,1057-1104`). 14 entries (9 draws, 3 shafts, bloom, composite) against `kMaxModePasses` 16 (`mc.h:192`),
      3 scene targets (the scene and two shaft levels) of `kMaxSceneTargets` 4 (`scene_targets.h:69`), 1 storage buffer, 3 meshes of 8
      (`mesh_buffers.h:54`), at most 2 samplers a pass of 8 (`basin.py:1350`, `mc.h:277`): every limit fits, no limits box.
    - Attachments and formats: the scene's colour is RGBA8 (no HDR, `target.py:1202`); the emission RGBA16F only with Glow above 0
      (`:1207-1208`); the shaft source R16F only with rays admitted (`:1209-1210`), all multisampled at the tier's count; depth a D24
      renderbuffer, never sampled (`:1213-1220`), where the core's target depth is D32F (`scene_targets.h:9,102`). The fragments
      write `FragColor`, `Emission` at 1 and the sky also `ShaftSource` at 2 unconditionally (`basin.py:546,1158,1201-1202`); Python's
      shafts attachment is slot 2 even without emission, slot 1 draw-buffer NONE (`target.py:1222-1229`), and the core refuses an
      output past the target's attachments or an attachment left unwritten (`mode_content.cpp:664-683`, from Extruded Bubble's reading):
      fragment variants by attachment set (a `#define`, one file for both renderers, `mc.h:3-4`). Blends are Quick's inherited
      premultiplied over on colour, additive ONE, ONE on the emission (`target.py:585-588`) and off on the shafts (`:606`): with Glow
      above 0 every pass writes attachments of differing state, so the program needs the core's per-attachment blending
      (`mc.h:86-90`, device-gated: refused and Python's to log where it is not real).
    - Turning: the frame is oriented before anything (`ng.py:222,375`, `rendering/quick/scene3d/frame.py:38-66`), the scene draws unturned at the
      oriented size and only the composite and the bloom's first samples are oriented (`target.py:937-941,980-1000`); the core refuses
      a turned bloom or composite unless the scene is in the window's frame (`mc.h:150-155,445-447`, ABI 29), so Neon Lake is the
      turned-card anchoring box's fourth consumer (after the Oscilloscope, Waveform, Extruded Bubble). Suspected Python defect, not
      run: under a quarter turn `end` replaces `frame` by the physical output frame (`target.py:940-941`) before `_apply_shafts`
      maps the light's item point through its matrix (`:1042-1055`), while the shaft source was drawn in the oriented scene frame, so
      the rays' centre may be taken in the wrong frame for quarters 1 to 3. Reproduce: rays on, content quarter 1, compare the
      rays' centre with the Sun's drawn position; settle in Python before the port.
    - Clear: all constants. One `glClear` of every attachment to 0 (overlay: transparent, `target.py:918-926`) and depth 1; the
      emission and shafts attachments clear with it. No port decision is open. With the content fade at 0 or an empty content
      rect Python draws nothing at all (`ng.py:382-385`).
    - Found while reading, shapes the port:
      - The terrain is read with a hardware-filtered `textureLod` on RGBA32F (`rendering/gl_programs/heightfield_glsl.py:4-12`,
        `basin.py:260`) and its G channel's filtered value is compared to a threshold (`:411,443,596,848`), while the plan's N4.e
        decision reads the heightfield with `texelFetch` so that 32-bit float filtering is never required (plan N4.e, research
        section 16). R16F cannot hold the authored float32 heights. The shared shader either does a four-tap bilinear from
        `texelFetch` in both renderers (Python's pixels move by the hardware's quantised weights; rule (a) of D12) or the device
        proves linear RGBA32F (Waveform's box on 32-bit float filtering, for a mode texture instead of an image).
      - The basin deliberately keeps loose uniforms: on its pass block the Glass surfaces drew a few pixels one 8-bit level apart on
        OpenGL in 19 to 215 of 549 recorded frames (`basin.py:1365-1368`, the 14 Nov identity record), left "to its port". The
        port has no loose form, so that difference must be found and removed first, in Python, with the block form shown
        byte-identical on the Glass frames.
      - `uPass`, `uMarks`, `uDepthOnly`, `uSkyPass` are uniforms the renderer flips between draws of one program
        (`basin.py:233-235,1207`; `ng.py:525-592`). One rule fills each member from exactly one source (`mc.h:55-65`) and there is no
        per-pass constant, so each becomes a compile-time variant (a `#define`): about eight bakes of the large basin fragment,
        each with its own 5.5 KB block copy and pipeline, built a step at a time. Python's frames must stay byte-identical across
        the shader change.
      - The marks are `GL_POINTS` with `gl_PointSize` and `gl_PointCoord` (`basin.py:507-519,707-716`); the core refuses points
        (`mc.h:102`). Instanced quads on the primitive N5.1 builds (D15; the plan's N4 topology rule), the corner supplying the
        coverage, from the mesh's instance stream; one shader for both renderers.
      - The basin writes its clip depth by hand in GL's range after the matrix (`basin.py:193-202`), and the sky's `gl_FragDepth`
        constants 0.999999 and 1.0 assume GL's window depth; QRhi's correction covers x and y and a zero-to-one z on Vulkan
        (`native/core/src/conventions.h` rule 1; Waveform's floor maps `0.5 * (z / w + 1)`, `rendering/gl_programs/waveform_ribbon.py:55`).
        The body is depth-tested at 0.999999 against far land near the horizon, where D24 (Python) and D32F (core) quantise
        differently: the horizon frames are the proof.
      - Both renderers skip work per frame that the core records every time: everything at fade 0, the mirrored passes while the
        eye is at or below the water (`ng.py:544`: it moves with the orbit and the terrain floor; the shader would otherwise draw
        reflections from below, so this is parity, not only cost), and the shaft chain while the body is behind the camera
        (`:721-722`; a zero source gives zero rays, cost only). The record u32 that skips an entry is Extruded Bubble's box below.
      - A mesh change (tier, painted tiles, origin reach) uploads up to 3.1 MB in the record that first draws it
        (`mesh_buffers.h:4-11`), where Python warms it over not-ready steps (`ng.py:229-231,236-239`): the old mesh kept drawn until the
        new is resident is Extruded Bubble's geometry box's rule.
      - Shaft targets are half the allocation (`shafts.py:155-161`, the 64 px bucket of the item), so they need the exact explicit size
        Waveform's first box answers; the allocation's slack carries Python's own content under ABI 28's anchoring (`scene_targets.h:12-17`).
      - Already in the plan: N4.k's merged shafts owner (Extruded Bubble's port, then Neon Lake) decides whether the shafts keep
        the source attachment, the two gathers and a composite term, or become ordinary additive passes.
  - [ ] C++: a 32-bit float mode texture for the heightfield (N4.e's primitive). Mode textures are RGBA8 pixels from the GUI
    thread (`mc.h:35-37,488-500`, `setTexture` `:578`; Waveform's half-float box adds RGBA16F with mips, this is RGBA32F and R32F,
    no mips, one `format` member serving both). Needed: a declared format on a texture (RGBA32F, R32F), float bytes uploaded once
    per data and replaced in place at the same size (another size recreates), both stages reading it by name (`PassSampler.stages`,
    `mc.h:296`), `texelFetch` and `textureLod` at the base level, byte counts in `modeTextureCounts` (1.06 MB and 0.26 MB at
    257 x 257), the overlay removed when the grid is not grown, and the job-service route (`mc.h:46-53`) or its in-frame fallback
    for float bytes. Proof, both backends, sizes 2 to 257 including odd: every texel of both channels read back equal to Python's
    float32 bits (row order as Python's: the RGBA8 form is top-first); a vertex-stage `texelFetch` and `textureLod` of it
    (QRhi has no feature flag for vertex sampling, N4.e) reproducing Python's displaced surface; a replacement at the same and at
    another size mid-run without a pipeline rebuild; nothing uploaded at rest; zero textures after teardown; if the filtered
    read stays, Python's bilinear against the core's on the water classification and the bank-distance threshold, inside rule (a)
    of D12 (else the four-tap form in both renderers, same bound). Negative controls: R16F storage (heights and the water
    classification leave the bound), a flipped row order, the overlay left bound after the grid shrinks.
  - [ ] C++: the composite with light shafts, unless N4.k's merged owner draws its rays as ordinary additive passes. Core
    composites are overlay, overlay_glow and opaque_glow (`mc.h:147-155`, `native/core/shaders/composite_overlay_glow.frag:57-85`) and
    nothing under `native/core` mentions shafts. Python adds the half-size shaft texture, times the rays' colour and times the
    scene's coverage ("never the empty card around it"), into the glow before the dither test, bound in the glow's place when
    Glow is 0 (`target.py:259-277,1057-1104`). Needed: a composite input naming a shaft level (`"<target>.<attachment>"`, read
    at the glow's uv) and a three-component colour the record fills (the shafts' colour times strength, per frame), over both
    forms with and without bloom. Proof, both backends, every sample count: the composite against Python's
    `scene_overlay_shafts(_samples)` frame for frame, with bloom on, bloom off (the shafts alone), rays off and each tier; the
    dither where shafts alone clear its floor; a quarter turn (the fourth consumer of the anchoring box). Negative controls: the
    coverage factor left out (rays over the empty card), the dither keyed on bloom only, the glow read at the content size
    instead of the allocation's.
  - Shared with Waveform's and Extruded Bubble's boxes (not repeated): the turned-card anchoring box (fourth consumer); the exact-size
    explicit target (Waveform's first box: the two shaft levels, no mips); the record u32 that skips an entry (Extruded Bubble's
    box: fade 0, the mirrored passes while the eye is under the water, the shaft chain, with a proof frame at each; if the lead
    drops that box for Extruded Bubble these three cases argue to keep it); the geometry residency rule for a mesh swap
    (Extruded Bubble's geometry box, only its old-key-kept half); per-attachment blending (N3.4's gate); the fragment-variant rule
    for outputs; instanced quads (N5.1); the merged shafts owner (N4.k); Waveform's 32-bit float filtering box, only if the
    filtered terrain read stays. Not needed here: the pass, target and storage limits (all within the ABI 29 values), anisotropy,
    the half-float texture, the scene probe, the drift and geometry arena, the readback check, defocus, bloom off per record
    (Glow is a setting: a program change), the backdrop clear (every clear is a constant).
- [ ] N5.3 Extruded Spectrum, then Sphere (meshes, lighting, N4.j's backdrop environment, N4.l's silhouette
  shadows; neither uses bloom; no compute).
  - Reading (reference; Sonnet agent a32125875bef33af0, 21 Nov, merged), one reading per mode as the Waveform,
    Extruded Bubble and Neon Lake readings: the record, meshes and streams, every pass with its targets and formats, how
    each turns, the clear; then what each port needs that the ABI 29 core lacks beyond the earlier boxes (one C++ box
    each, with its proof) and which earlier boxes they share. File:line for every claim; any suspected Python defect is
    reported, not fixed. Sphere's persisted id is `sphere`.
    Reading (Sonnet agent a32125875bef33af0, 21 Nov, no code touched; sizes measured with a probe over the real mesh builders
    and block layouts). `es.py` is `rendering/quick/visualizer/implementations/extruded_spectrum.py`; `esp.py` is
    `rendering/gl_programs/extruded_spectrum_program.py`; `sv.py` is `.../implementations/sphere_voxel.py`; `svg.py` is
    `.../implementations/sphere_voxel_geometry.py`; `s3d.py` is `rendering/gl_programs/scene3d.py`; `env.py`, `target.py`,
    `frame.py` are in `rendering/quick/scene3d/`; `mc.h` is `native/core/src/mode_content.h`; `D12` etc. are in
    `Native_Core_P3_Decisions.md`. Both modes are one overlay `SceneTarget` (multisampled RGBA8 colour, a D24 renderbuffer
    depth, `target.py:1205,1217-1223`), a frameless card that may overflow it (`core/settings/visualizer_mode_registry.py:349-355,
    302-310,328,369`), drawn instanced from one small unit-cube mesh, and composited by the overlay composite with no bloom,
    no emission, no shafts, no compute, no reflection target, no OIT, no HDR, no depth texture. Neither uses `PhotoEnvironment`
    (ten transitions): N4.j for them is `BackdropEnvironment` only (`es.py:37,89`, `sv.py:26,730`).
    - **Extruded Spectrum, per frame** from the logical frame (`ExtrudedSpectrumFrame`, `widgets/spotify_visualizer/render_state.py:392-401`,
      Spectrum's payload and frame runtime unchanged): the bars (at most 64, `rendering/gl_programs/spectrum_options.py:13`),
      the peaks, the bar count and the animation time (`es.py:202-205,215-218`). The renderer turns the bars into the upload
      form per frame (`x 0.55`, `rendering/quick/visualizer/implementations/spectrum.py:127-148`) and the hue phase
      `animation_time x 0.15 x drift mod 1` (`es.py:75-77`, rate `esp.py:77`): for the worker to publish (D5.5, the N0.4 box), in
      the form Python packs (a double product rounded once to float32; a shader multiply would differ by an ulp). The bar
      record is 3 floats a bar, 768 B at 64 (`es.py:66-72`); no native schema exists yet for this mode (Spectrum's, Oscilloscope's,
      Bubble's and Spline Curve's do: `core/visualizer_engine/`), and the schema may carry f32 arrays or f64 fields filling a
      block's float arrays (`program_blocks.h:19`). The Settings parameters ride frozen in the same frame, with the wallpaper
      put in at the main side (`widgets/spotify_visualizer/backdrop.py:74-147`: 0.6 MB, so the record leaves it out).
    - **Extruded Spectrum, per Settings, card or view change only** (the view's Turn and Tilt are Settings, edited by drag):
      Spectrum's layout (`es.py:120-128`), depth, tilt, turn (`:133-136`), the fit `extruded_fit` (`:139-144`, `esp.py:133-149`),
      the painter's draw order of the translucent passes (`es.py:237-239`, `esp.py:115-123`: a permutation of up to 64 bars from
      the eye's x, so it is Settings-and-card data, not music), the multisampling (`es.py:54-63`: 4 at High, doubled to 8 by
      Smooth Edges, 2 and 4 at Balanced, 0 below, `s3d.py:81-88,115-127`), the colours, gloss, edge width in pixels, floor span
      (`es.py:214-226,265-277`), which passes exist (`:337-353`), the reach and so the target's frame (`:147-166`, `esp.py:152-175`;
      `frame.py:155-169` grows it in quarters of the item's height, never past the window), and the wallpaper maps (`es.py:279-291`).
      The pass block is 288 B (probed).
    - **Meshes**: the box is 36 vertices of position and normal, 864 B (`s3d.py:620-621`), drawn instanced once per bar,
      at most 64; the bars come from the record, never a second mesh.
    - **Passes of a frame in order** (`es.py:254-353`; one scene target, overlay, multisampled; every gate below is Settings,
      so each is a program variant, not a per-record choice): (1) the cast shadow (`es.py:301-335`, pass 4, MAX blend
      union) is never admitted: `EXTRUDED_CAST_SHADOW_AVAILABLE = False` (`core/settings/visualizer_mode_registry.py:15-17`, R-128;
      its settings are marked unavailable, `core/settings/visualizer_mode_settings.py:1390-1395`), so N4.l's Extruded half
      draws nothing in production; (2) the bars, pass 0, when the fill is opaque (`es.py:337-340`: depth test and write on) or,
      with a translucent fill or visible edges, pass 3 (`:341-348`: no depth, far-to-near by the records; the vertex stage moves
      the box faces turned away off the clip volume, `esp.py:344-349`); (3) the floor reflection, pass 2 (`es.py:350-351`, the
      row mirrored under the floor, discarded below the field, `esp.py:315-318,430-435`); (4) the ghost columns, pass 1
      (`es.py:352-353`, `esp.py:303-310,429`). Passes 1 to 3 are alpha blends with the depth mask off; one rule gives
      `uPass` no home in a block (`mc.h:55-65`), so each becomes a `#define` variant of one shader file (three or four bakes, each
      with its own 288 B block). On leaving the scope one overlay composite at the content fade (`target.py:980-1003,294-300`,
      `es.py:254`): up to 4 entries of `kMaxModePasses` 16 (`mc.h:192`), 1 scene target of 4 (`scene_targets.h:69`), 1 mesh of 8,
      at most 1 stream of 8 (`mesh_buffers.h:54-55`), 2 samplers of 8 (`mc.h:277`; `uBackdrop`, `uBackdropPrevious`,
      `esp.py:362,365,446-448`): every limit fits, no limits box. The blend of every pass is the core's `alpha` preset
      (colour SrcAlpha, OneMinusSrcAlpha; alpha One, OneMinusSrcAlpha: `mode_content.cpp:781-787`), the state the Python host leaves (`rendering/quick/visualizer/render_host.py:303-310`).
    - **Wallpaper (Mirror Faces)**: the two-slot `BackdropEnvironment` (`env.py:210-335`): an RGBA8 copy, longer side 512
      (`s3d.py:157`, `backdrop.py:27-31`), rows bottom first (`backdrop.py:20,46`), a full mip chain, linear mipmap filter,
      clamped (`env.py:287-299`); the new wallpaper goes into the other slot and the reflection crossfades over the bringing
      transition's duration or 2 s on the logical clock (`env.py:226,252-278`), the first one fading in from no reflection by
      `mirror x blend` (`es.py:243-252`); Mirror off holds nothing (`es.py:251-252`). The shader reads both with `textureLod` at the
      mirrored uv (`esp.py:416-426`). Native: two mode textures with mips already exist (`mc.h:35-44`, a same-size image replaces in
      place, another size recreates it; GPU mips). Gaps that are Python: the owner uploads on the edge it already has
      (`widgets/spotify_visualizer/quick_display_visualizer_owner.py:516-546`) instead of the frame carrying the pixels; the blend
      is per frame, so the worker publishes `mirror x blend` and the slot weights from the logical clock and the owner's
      (identity, duration) edge; a program whose texture is missing is not drawn (`mc.h:70-71`), so a 1 x 1 placeholder stays in both
      slots until the first wallpaper; the uv maps the fragment through `fragPixel(uTargetSize)` and `uBackdropMap`
      (`esp.py:363-364,418`), the allocation and the window's GL pixel, where the core's fragment row is top-first on every backend
      (`conventions.cpp:44`) and `u_target_px` is the content (`mode_content.cpp:230`): the shader maps the target pixel to the
      window's through `u_window_from_target_x/y` (`mode_content.cpp:228-229`) and the backdrop's row order once, in the one shared
      file, with Python's frames unchanged. Gaps that are C++: the crossfade's start (the owner's edge precedes the texture
      commit, `mc.h:46-53`), and the mip chain per backend: see the boxes.
    - **Turning**: the frame is oriented before anything (`es.py:172,195`, `frame.py:38-66`), the scene draws unturned at the oriented
      size, the reach stays in the oriented frame and clips to the physical window (`Docs/Reference/Scene3D_Resources.md:12`), and
      only the composite is turned (`target.py:937-941,980-1003`). The core refuses a turned composite unless the scene is in the
      window's frame (`mc.h:150-155,461-465`, ABI 29), so Extruded Spectrum is the turned-card anchoring box's fifth consumer
      (Oscilloscope, Waveform, Extruded Bubble, Neon Lake before it), and the only one that also overflows: its composite
      rect is the reach rect (`rendering/native/composite.py:12-14,115-136`; only `native/core/python/composite_check.py:472-473`
      passes an `overflow_rect` today), so that box's proof includes a turned, overflowing card.
    - **Clear**: all constants. One clear of colour to transparent and depth to 1 at the scope's start (`target.py:918-926`).
      With the content fade at 0, or no bars, Python draws nothing (`es.py:203,207`).
    - **Found while reading, shapes the port**:
      - The hand-written clip depth is OpenGL's range: `clip.z = clamp(-screen.z / 6, -1, 1) x w` (`esp.py:284`). The view depth
        spans both signs (the row turns up to 180 degrees about its centre, `esp.py:56-57,252-260`), so on Vulkan, whose clip
        range is 0 to w, everything nearer than the pivot is clipped. The one shared shader maps it as Waveform's floor does
        (`rendering/gl_programs/waveform_ribbon.py:55`, `0.5 x (z / w + 1)`); Python's frames must stay byte-identical across
        the change (the order is monotone; only D24's quantisation moves). The proof frames are the extreme turns and tilts.
      - The target is the reach: up to the whole window, at 8 samples with Smooth Edges at High (8 x (RGBA8 + D32F) = 64 B a pixel,
        about 530 MB at 3840 x 2160 before the resolve; arithmetic, not measured): `SceneTargetCounts` at the largest reach goes
        in the port's record, and the sample clamp to the device (`kMaxSceneSamples` 8, `scene_targets.h:72`) is a proof size.
      - The composite's rect is Python's `item_pixel_rect` of the reach frame (`frame.py:92-136`) and the core's is a whole-device-pixel
        rect (`composite.py:115-136`); the card's `scene_item` carries Python's (ABI 28), and the two must agree at every reach step.
      - Scene opacity reaches Extruded Spectrum only as the content fade (`es.py:254`), which the core's composite reads as `u_fade`
        (`native/core/shaders/composite_overlay.frag:16,39`); `render_contract.scene_faded_snapshot` folds it in on both paths
        (`rendering/quick/visualizer/render_contract.py:70-86`), so nothing is added.
    - **Sphere, per frame** from the logical frame (`SphereFrame`, `render_state.py:473-` and the cohort at `:438-469`): the size
      pulse, the rotation phase, the tracer drive and phase, the eight section drives, the incoming drive, density, two sections
      and blend, and up to four particle cohorts (progress, strength, density, velocity accent, vocal bounce, section, lane,
      outtake) (`sv.py:813-864,779-811`); every value packed as Python packs it (clamps at `:910-916`, `:793-800`). Per frame in the
      renderer today, so for the worker to publish: the rainbow phase `fmod(logical time x speed, 1)` (`sv.py:959`), the shadow's
      offset `-light x radius x (0.34 + 0.55 x pulse) x distance` and alpha `colour alpha x (0.28 + min(0.16, 1.6 x pulse)) x
      opacity` (`:1079-1087`), whether any admitted cohort is an outtake (`:967`), and the fade `scene_fade x content_fade` (`:955`;
      see the defect below). 278 instances is what the shell builder makes (`svg.py:14-19,63-95`, probed): radius 5, thickness
      0.75, 5,560 B of centre, seed and polarity, one cube of 36 vertices (864 B, `svg.py:32-44`), 10,008 vertices a draw.
    - **Sphere, per Settings or card change only**: the geometry `(centre, radius = 0.215 x min(content))` (`sv.py:48,79-85`), the
      reach and so the target's frame (`:93-109,751-756`), the multisampling (`:121-123`: 4, 2, then 1 where the tier has none),
      Mirror Cubes' strength (`:112-118`), the light vector (`:873-879`), colours, gloss, edge weight, depth shading, toon,
      rainbow flags, spin mode, perspective, view pose, voxel variation, projection (`:813-866,940-966`), which layers exist (the
      shadow and its softness layer, `:1073-1088,1134-1145`), and the wallpaper as above (`:929-939`). The block is 1,024 B
      (probed; `:126-181`), one block for hero and shadow, patched per layer (`:1115-1121`).
    - **Passes of a frame in order** (`sv.py:976-1034`; one scene target, overlay 1.0, multisampled, depth LESS and write on):
      (1) with Soft Shadow above 0, the soft layer, the same vertex stage with the cubes grown by `1 + 0.12 x softness`, a flat
      fragment of the shadow colour, alpha x `0.32 x softness`, projected with the offset and scale of the shadow
      (`:1134-1141`; shader `:691-704`), then a depth clear (`:1142`); (2) the shadow's core silhouette, the same program at cube
      scale 1 (`:1144`); depth is used only as a mask so overlapping faces do not stack alpha (`:1062-1069`); (3) a depth clear
      before the hero (`:989-990`) so the shadow cannot occlude it; (4) the hero, the cubes lit and edged, culled back with the
      front face from the matrix's handedness and the backend (`:1002-1018`, `:62-65`, `rendering/gl_programs/conventions.py`
      `front_face_clockwise`); (5) with outtake cohorts, a second draw of each of the three layers with `uRenderPass = 1`, depth
      write off (`:1020-1032,1107,1128-1132`); then the overlay composite at fade 1.0 (`:976`) with the fade applied per
      fragment (`:684-687`). Up to 6 draws, 2 depth clears and the composite: 9 entries of `kMaxModePasses` 16, 1 scene target,
      1 mesh with its instance stream of 8 (`mesh_buffers.h:54`), no stream or storage (every value fills a block member
      from the record or the settings: `mc.h:55-65`), 2 samplers: every limit fits. `uRenderPass`, `uVoxelScale`, `uProjectionOffset`,
      `uProjectionScale`, `uLayerAlpha`, `uShadowColor` change between draws of one program (`:1115-1121,1025`) and the rule has no
      per-pass constant: one `#define` variant a draw, a block member name per variant (about six bakes of the vertex and
      fragment sources, `:184-704`; warm-up one build a step). All draws are `Alpha` blends.
    - **Sphere, how it turns**: it does not turn the content. Sphere is not content-rotation capable
      (`registry:302-310`, against Extruded Spectrum's `:354`), never orients its frame (no call in `sv.py`), and its turn and tilt
      are a view pose in the vertex stage (`:837,509`, `s3d.py:1266-1286`). The turned-card box does not touch it.
    - **Sphere, clear**: constants (colour transparent, depth 1, `target.py:918-926`) plus the two mid-frame depth clears above.
      With the fade at 0 Python still records every pass (alpha 0, `:684-687`); no early return but a zero target.
    - **Found while reading, shapes the port (Sphere)**:
      - The core clears a scene target's depth only with the target's clearing draw at its first run of a record
        (`mc.h:96-97`, `mode_content.cpp:5999`): nothing clears depth mid-frame. Sphere's silhouette mask depends on it twice
        (`sv.py:989-990,1142`). A data-only substitute exists: a full-target pass with colour writes off, depth test Always, write
        on and `gl_FragDepth = 1.0` (`mc.h:91-92`), at a full-target fragment cost twice a frame; the box below decides.
      - The overlay composite always multiplies by the card's content fade (`composite_overlay.frag:39`, `u_fade` a core member,
        `mode_content.cpp:223`), where Sphere composites at 1.0 and fades each fragment before blending (`sv.py:976,684-687`);
        fading after the blend instead is not the same pixels where fragments overlap (the shell's translucent fills and the
        shadow layers). The shader's own fade member (`uFade`) is a record or settings member, not the core's `u_fade`.
      - Culling and the front-face selector (`mc.h:107-108`, `mode_content.cpp:5360-5372`) are built (N3.2) and used by no ported
        mode yet: Sphere is the first consumer, so the proof includes each backend's winding and the negative control of the
        flipped one.
      - The depth is the Scene3D projection's own: `sceneProjectAt` writes `clip.z = sceneClipDepth(w)` after the matrix
        (`s3d.py:224-239`), about 0.93 to 0.96 over the shell: inside both backends' ranges, the compare monotone; D24 against D32F
        only moves ties between faces of one cube, the same class as Neon Lake's horizon note.
      - The wallpaper maps as Extruded Spectrum's (`sv.py:661,962-963`, `uTargetSize` `:1044-1045`).
    - **Suspected Python defect (Sphere), not run**: the scene fade may be applied twice. The node and the native route fold the
      authored scene opacity into the content fade (`rendering/quick/visualizer/node.py:264`,
      `rendering/quick/visualizer/native_route.py:626-657`, `render_contract.py:70-86`; the root's `sceneOpacity` is
      `presentation.scene_fade x reveal`, `scene_controller.py:2741`, `VisualizerPresentation.qml:256`), and Sphere then multiplies
      `presentation.scene_fade x presentation.content_fade` again (`sv.py:955`; the snapshot's `scene_fade` is untouched by the
      fold). At a scene fade of 0.5 the shader receives 0.25. Extruded Spectrum and every other renderer use the content fade
      alone, and `tests/test_qtquick_visualizer_fade_authority.py` names "test_visualizer_scene_fade_once" (`:77`) which
      does not exist in `tests/`. The term arrived with the voxel rework (49086dbf4), before the fold (d67d6aac3). Reproduce: take
      a Sphere snapshot whose presentation has `scene_fade = 0.5` and `content_fade = 1.0`, pass it through `scene_faded_snapshot(
      snapshot, 0.5)`, and read `values["uFade"]` at `sv.py:955` (0.25, where one application gives 0.5); then a hidden render at
      scene fade 0.5 against an Extruded Spectrum frame at the same fade shows Sphere's alpha squared. Settle in Python (one term,
      with the fade-in curve judged on the activation reveal) before the port, since the native route would copy it.
  - [ ] C++: a depth-only clear of a scene target between passes (Sphere's silhouette mask, two a frame with Soft Shadow, one
    without it, none with the shadow off). The core's only depth clear is the target's first-run clearing draw (`mc.h:96-97`).
    Needed: a pass entry that clears a named target's depth (the far value, the whole content viewport and every sample) with colour
    untouched, recorded in place between runs of draws on that target. If the lead prefers data only, the full-target
    frag-depth pass above is the alternative and its cost the proof. Proof, both backends, every sample count: Sphere's frames
    with the clears taken against Python's `glClear` frames (shadow on with and without Soft Shadow; the hero not occluded by
    shadow depth), the clear leaving colour and the other target alone, GPU time of the entry at 4K against the frag-depth
    pass. Negative controls: the clear left out (the hero loses the pixels the shadow's depth covers), the clear writing colour.
  - [ ] C++: the overlay composite at a declared fade. The composite step's fade is the card's `u_fade` only
    (`composite_overlay.frag:16,39`; `mc.h:147-155`). Needed: a composite option whose fade is a constant 1 (or a named member the
    record or settings fill), valid for the overlay and glow forms, leaving every existing program's frames unchanged. Proof, both
    backends, every sample count: Sphere's overlay composite at 1.0 against Python's `overlay=1.0` frames with the per-fragment fade
    at 1, 0.5 and 0 (a content fade that does not reach the composite), and an existing overlay program (Oscilloscope or Neon
    Lake) hash-identical before and after. Negative control: the card's `u_fade` at the composite and the shader fade both applied
    (the half-fade frames leave the bound).
  - [ ] C++: a mode texture's commit as something the record can read. The wallpaper crossfade starts when the new image is what the
    slot draws (Python: at its first `textures` call, `env.py:260-271`); here the owner's edge precedes the texture's commit,
    which is one record later in place on OpenGL and a job's completion on Vulkan (`mc.h:46-53`), and the state keeps only
    counts (`TextureReport`, `mc.h:514-530`). Needed: each texture's committed generation as a core member of the pass block
    (or an edge to the owner, as a lost texture is, `item_notifier.h`), so the worker's blend begins at the commit and the shader
    never mixes toward a slot still holding an older image. Proof, both backends: a wallpaper change at a known record, the blend's
    first frame and the weights across the change against `BackdropEnvironment.textures` frame for frame with the job route
    forced slow (the in_frame control) and not; mip levels 0 to 4 read back against `glGenerateTextureMipmap` for even sizes
    and for the odd sizes real wallpapers give (QRhi's Vulkan blit differs on odd levels, D17 G), the reflection inside rule (a)
    of D12 on the frames that read them (lod 0.4 to 3.6, `esp.py:420`; 1.8 to 3.6, `sv.py:664`). Negative controls: the blend
    started at the owner's edge (a few percent of a stale reflection in the first frames), the mips of the Vulkan blit on an odd
    size without the bound. If the measured commit lag is a frame or less on both routes the lead may judge this immaterial and
    drop the box; the evidence is the proof's first row.
  - Shared with the earlier boxes (not repeated): the turned-card anchoring box (Extruded Spectrum only, fifth consumer, with its
    overflow rect in the proof); the record u32 that skips an entry (Extruded Bubble's box, for Sphere's three outtake overlay
    draws, which otherwise run every frame with every fragment discarded, `sv.py:537,1020-1032`: cost only, so if the lead drops
    that box Sphere pays and records it); the fragment and vertex `#define` variant rule (Extruded Bubble's and Neon Lake's); N3.6's
    warm-up for the variants. The wallpaper environment, the silhouette pass and the depth are N4.j's and N4.l's whole content:
    N4.j is two mode textures plus the Python plumbing above and the commit box; N4.l's Extruded half is dead code
    (R-128) and its Sphere half is ordinary passes of one program (the depth clear above), not a shared primitive, so N4.l as
    written (one primitive for both) is not needed by either mode. Not needed here: the pass, target, stream and storage limits
    (every one within the ABI 29 values), per-attachment blending, anisotropy, half-float or 32-bit float textures, the exact-size
    or mipped target, the scene probe, drift and geometry arena, readback check, defocus, bloom or HDR, shafts, the backdrop
    clear (every clear is a constant), instanced quads (the cube is a mesh).
- [ ] Spectrum and Spline Curve long-take residuals (ACCEPTED by the operator, 17 Nov, with Bubble; non-blocking).
  Rerun 21 Nov after the scene-fade fix (R-242) on all four 60 s takes, both variants, display placement: full
  replays with the Python references drawn and cached (`D:\Temp\Scratch\SRPSS\fast_proof\references\`), every
  one of 5,313 shown frames judged a run, halves 0-2645 / 2645-5291, 620-800 s a take for both variants. Module ABI 28
  (1843914e8); Spectrum's nightsolong take and the probes ran on ABI 29 after main's merge, and every probe
  reproduces the ABI 28 run's native hash at each failing input. The cold start passes on every take and variant
  (R-242's class is gone from the long takes). Neither mode is retuned and no D12 bound is changed. Evidence:
  `native_core/longclip_recheck/20261121_<mode>_<take>_display_fix_rerun/` (report with both paths' frame hashes,
  the long-term reference of the guide's section 6; `classify_<run>/`: every pixel past its allowance at each
  failing input, with crops). Bubble variant b's four 60 s takes pass after the fix (0 failed frames each; first
  half scatter 55-62, groups 2, ties 2-4; second half scatter 9-12, ties 0; Bubble's own Python frames identical to
  the pre-fix run, native changed only at inputs 0-27; `fast_proof/20261121_rule_a_fix_rerun_60s_<take>/`).
  - [ ] Spline Curve (`devcurve`): steady and deterministic failures only (nightsolong variant a fails exactly 17
    Nov's seven steady inputs). Failed frames (first half / second half; worst ties per half):
    - ragdoll: a 1 (2570 / none; ties 10 / 9); b 1 (2460 / none; 11 / 10).
    - human_heavy1: a 1 (none / 3376; 10 / 9); b 4 (1176, 1394, 2495 / 4646; 11 / 10).
    - anything_mixed2: a 3 (643, 810 / 5091; 9 / 9); b 2 (2384 / 5015; 11 / 11).
    - nightsolong: a 7 (728, 829 / 2991, 3170, 3385, 3446, 4042; 10 / 9); b 4 (205 / 3174, 5088, 5204; 10 / 12).
    Two classes; scatter 0 and flips 0 everywhere. (A) "11-12 ties", variant b only (9 frames): 8-10 two-level
    pixels on the translucency mask at the curve's anti-aliased edges (3x3 reference range 30-208), each isolated,
    plus 1-3 one-level opaque pixels; the count is one or two over the bound of 10, the placement never fails.
    (B) "ties neither isolated nor on a content edge", both variants (14 frames: 12 of a, 2 of b): a touching pair
    of one-level pixels in the curve's bright core (mostly one channel at 255), the stray one's 3x3 range 10-31,
    under the edge contrast of 32; at 728 the pair is two-level and on the mask (range 11-13). Not proved: the
    source of each (candidates: the line raster's coverage rounding for A, the core colour's float path for B).
    Next: compare the uniforms and the per-fragment colour of one A and one B frame Python against native; fix at
    the owner; if either proves a D12 class, the bound is a lead decision with the measured worst stated (A: 12
    ties; B: a touching pair at range 10).
    - Fixed at the source by the card quad (ABI 32, merged 21 Nov): failed frames 23 -> 6, class A gone. The 6 left
      (class B, one-level touching pairs, also seen in Python against itself) are backlog: human_heavy1 a 2358, 4200;
      nightsolong a 941, 4194, b 4836; anything_mixed2 a 2151.
  - Tool gaps found (fix with or before this box): no Vulkan path in the owner replay (no rule (b) or Vulkan hashes);
    output only at the end of a run (a killed run loses everything); about 3 GB per run; 28 min per one-variant run.
- [ ] Bubble GPU optimisation (Opus Medium agent ae6c6e5974266bad5, 21 Nov; the live Display 1 baseline is the lead's)
  (operator, 17 Nov: Bubble about 50 % GPU at 4K and Extruded Bubble
  about 55 %, on a stale build; "all guarded gains are valuable"). Every candidate passes
  `Docs/Guides/Native_Parity_And_Timing_Proof.md` for what it touches (its change-type table).
  - [ ] Baseline in the operator's case first: Bubble fullscreen (expanded) at 4K on Display 1, where Python OpenGL
    reaches about 50 % of a 4090 for 2D vector work, and Extruded Bubble about 55 %. Use live runs on Python OpenGL
    and native Vulkan with `--app-arg=--gpu-pass-timing`, and record `nvidia-smi` utilisation and clocks with the
    figures. The card-sized cost measured at the port is not this case.
  - [ ] Measure per-pass GPU time at 4K on both backends first. The port's figures put nearly all the cost in the main
    `bubble` pass (about 3 ms at full 4K area; native OpenGL about 5 % slower than Python).
  - [ ] Measure with decoration off, representative decoration on, and high-density, high-glow decoration on, at the
    canonical card and at extreme wide, tall and expanded sizes. Include R-170's density growth: a larger card draws
    up to 72 live heroes (110 with draining trails), and the hero loops run per fragment. Confirm that decoration off
    really skips the ambient target's draws.
  - [ ] Byte-identical candidates first. Anything that cannot hold byte identity goes to the operator as tier 2.
  - [ ] Optimise only a measured offender. If no material cost is found, close the item without redesigning Bubble.
  - Built (Opus Medium agent abbcd68ea9219da70, 21 Nov): the wake loop's per-bubble reject (c8d1ea916), hash-identical
    on all four 60 s takes on both APIs, -22 % OpenGL and -21 % Vulkan for the expanded 4K bubble pass. The ghost loop
    has no candidate that pays after it (5ba190a5f keeps the three in `bubble_cost_matrix.py`). The pass's largest
    stages are now the wake (0.90 ms OpenGL, 0.66 Vulkan) and, on Vulkan, the ghost (0.66).
  - [ ] Extruded Bubble gets the same treatment after N5.6, with its own three-clip before-state.

**N5, background track (one High slot; transitions grouped by what they share; needs are in the matrix,
section 2)**

Slots (lead, 12 Nov): N5.2a, the first group on the shared fullscreen pass, goes to Opus High, and so does each group
whose primitive is ported with it (N4.c, N4.g, N4.i, N4.j, N4.l). After that, a group whose primitive is already
native goes to Opus Medium, under the same parity proof and audit as the modes track.

- [ ] N5.2f Disintegrate, Volumetric Dissolve (N4.c).
  Reading (agent, 22 Nov; both implementations and programs, `rendering/quick/scene3d/population.py`, the N3.3 harness's
  `population` scene in `native/core/python/compute_passes`, `mode_content.cpp`'s pass, storage and indirect admission):
  - Shared. Linear easing; each ends on the photographs (progress 0 the old, 1 the new; Python draws the effect between,
    though Disintegrate's grains are gone by 0.97 and Volumetric is exact after 0.93), so `eased_show(progress)`. Samples
    are the request's (`scene3d_request_samples`; 0 draws straight into Quick's framebuffer, the core's one-sample target
    copied exactly, as N5.2c). The grid is of the viewport's device pixels (`disintegrate_grid` / `volumetric_grid`: the
    grain or particle size grows until the cells fit 600,000 / 400,000; 4K at size 2 gives 960 x 540 = 518,400 grains),
    so `scene_pixels`. No depth, no bloom, motion or trails; no Python conversion (checklist 16) is needed.
  - The population (N4.c): three compute dispatches a frame over every member (`population_count_source(hooks)`: 256 a
    group, a shared count; `POPULATION_SCAN_SOURCE`: one group of 1,024, the offsets and the command (vertices, live
    count, 0, 0); `population_scatter_source(hooks)`: each live member's id and `vec4` state at its slot, in id order),
    then one `glDrawArraysIndirect` strip of 4 a live member (`populationIds` / `populationStates[gl_InstanceID]`,
    readonly std430 at 6 and 7). Five buffers at 3-7 (counts and offsets 4 a group, command 16, ids 4 and states 16 a
    member: 10.4 MB at 518,400). The hooks read the transition's frame block (binding 15); the dispatches also read
    `PopulationDispatch` (`uPopulation`, `uGroups`, `uVertices`) at 16: two blocks in count and scatter, one in scan.
  - Disintegrate: `intact` (item quad, `uOldTex`/`uNewTex`, the old picture before a cell's release and the new after;
    blocks `DisintegrateIntact` + `DisintegrateFrame`: `uGrid` uvec2, `uDirection`, `uFrameSize` (logical), `uProgress`,
    `uSeed` uint, `uWind`), replace; then the population `grains` (`DISINTEGRATE_HOOKS`), its draw `grains` (`uOldTex`;
    one block `DisintegrateGrains`: `uMatrix`, `uItemSize`, `uGrid`: it reads no frame block), blended colour add one /
    one_minus_src_alpha, alpha add zero / one (`blend_scope`: the alpha kept).
  - Volumetric Dissolve: two photo environments, the new picture's (`uNewCopy`, unit 2, `textureLod` 1-5) and the old
    one's (`uOldCopy`, unit 3, lod 3.5 and 3) (`PhotoEnvironment` roles destination and source); `backdrop` (item quad,
    `uOldTex`, `uNewTex`, `uNewCopy`, `uOldCopy`; blocks `VolumetricBackdrop` + `VolumetricFrame`: `uGrid`, `uDirection`,
    `uFrameSize`, `uProgress`, `uSeed`, `uDepth`, `uMist`, `uRadial`), replace; the population `particles`
    (`VOLUMETRIC_HOOKS`); its draw `particles` (`uOldTex`, `uOldCopy`; blocks `VolumetricParticles` (`uMatrix`,
    `uItemSize`) + `VolumetricFrame`, its vertex recomputing the particle from its id), blended as Disintegrate's.
  - What the core has: compute entries with storage buffers sized by a setting, groups by a setting, the "draw" trigger
    (the one a still admits, ABI 37), readonly vertex-stage storage from a compute-written buffer, an indirect draw from
    a storage buffer (`drawIndirect`, refused with its reason where QRhi lacks `DrawIndirect`), two environment steps
    (`kMaxEnvironmentStages`, "Python's two roles"), uint and uvec2 settings. The N3.3 harness already draws the product's
    own population texts (count, scan, scatter, indirect, all five bound read_write) and checks them against its direct
    draw (`population` / `population_direct`, `compute_pass_check.py`; not rerun here). What it lacks: a second block a pass (count, scatter, intact, backdrop, the particles' draw), taken as data with
    N5.2e's `native_one_block`; and any way for Python to read QRhi's `DrawIndirect` / `DrawIndirectMulti` answers
    (`computeDeviceFacts` has neither), which N4.c's runtime query and cull path need.
  Design (agent, 22 Nov):
  - Frame blocks as data (`native_one_block`, as N5.2e): the native packs of intact, backdrop and the particles' draw
    merge the frame block into the pass block; the count and scatter packs merge it into `PopulationDispatch` (a compute
    stage is a one-stage tuple); the scan pack is the product's text verbatim. The grains' draw takes its text as is.
  - `NativeScenePopulation` (`native_scene.py`): its name, its hooks, the transition's frame block and its draw pass's
    name; a renderer's `native_scene_populations()` lists them for the bake (`tools/regen_qrc.py --shaders`:
    `<transition>_<population>_count.comp.qsb` and `_scatter.comp.qsb`; one shared `scene3d_population_scan.comp.qsb`
    beside the motion posts; `native_transition_renderer`'s shipped check counts them). `scene_program` expands one into
    the five `StorageBuffer`s (`<pop>_counts`, `_offsets`, `_command` with `indirect`, `_ids`, `_states`, each sized by a
    setting), the three `ComputePass`es (trigger "draw", groups `(<pop>_groups, 1, 1)` and `(1, 1, 1)`, all five bound
    read_write as the harness: qsb reflects every declared block), placed after the environment steps and before the
    passes (the hooks read no draw; no run of passes on the scene target is split), and its draw pass's `PassGeometry`
    (`indirect=<pop>_command`, `draw_count=1`, `storage=(("PopulationIds", ids), ("PopulationStates", states))`, strip).
    `scene_program` also returns the buffers for `mode.program(..., buffers=)`.
  - Values, one owner: a `population_values(name, population, vertices)` helper beside `CompactedPopulation`'s
    `_DISPATCH_BLOCK` (`uPopulation`, `uGroups`, `uVertices`, the group count and the three byte sizes) that the
    renderers' `scene_values` add, from the same grid as Python's `render`.
  - Volumetric's second environment: `NativeScene.source_environment` and the sampler kind `"source_environment"`, an
    `EnvironmentStep` of the old slot (`environment_size` of the source's pixels), sampled linear with linear mips.
  - N4.c's open boxes (Opus High, with the port): ABI 41 (one small core change, reserved for this track) adds
    `draw_indirect` and `draw_indirect_multi` to `computeDeviceFacts` and a harness control that hides `DrawIndirect`
    (as `hideDrawParameters`), so the port reads and records each backend's answer and the cull path is proved on this
    machine; the cull path is data: the draw drawn with `instances=uPopulation` and a vertex text whose id is
    `srpssInstanceIndex`, evaluating `populationActive` / `populationState` itself (a dead member collapsed off-screen),
    no compute entries, chosen by Python from the fact. Live order is id order in both forms, so the pixels are equal.
  - Traps to check first: the compute-to-indirect and compute-to-vertex-storage barriers (QRhi derives them; NVIDIA hid
    a missing one before), so the route check runs Vulkan with synchronization validation; the scan's 1,024 invocations
    against `max_threads_per_thread_group` (Vulkan guarantees 128; refuse with the reason, never clamp); `firstInstance`
    stays 0 (the scan writes it).
  - Proof (proof guide section 3): row order first (checklist 17); rule (a) on the single-sampled forms (the grains and
    particles are small moving quads, so start from `N52C_RULE_A` and measure, the piece-edge class only if measured), rule
    (b) on every form, through the route check's N52F variants (each default; Disintegrate grain 2 at 4K (the grown
    size), wind 0.5 and 2, a diagonal, 4x; Volumetric center out, mist 0 and 1, depth 0 and 1, size 2, 4x), several image
    pairs, full canonical durations, both dprs; the cull form equal to the indirect one; N4.c's harness at one million
    sprites, indirect against cull, same pixels, cost; `--cost` at 1440p and 4K on both backends; one native Vulkan
    hitch session; registration last.
  - [ ] The hitch rows under a game (22 Nov): attributed by agent ac3072f8bea57441b for Disintegrate (trace
    `.artifacts/evidence/performance/preflip_pack/20261122_n52f_native_vulkan_session_2160p_idle`, probes
    `.artifacts/evidence/native_core/n5_2f/20261122_hitch_attribution/`): the GUI thread stalls at the process's FIRST
    run; `transition()` costs 47-58 ms then 9-13 ms in the first ticks (second run 24-27 + 4-5 ms): the lazy import of
    the transition's renderer module and its shader text build, then another import at the first scene frame; under the
    game's CPU load past 33 ms. Fix (not N5.2f-scoped): warm the next transition's module import and text build
    gradually ahead of its run (warm-up rule; audit low L6, N3.6), then retake the rows under the same running load,
    copying each per-row session folder out between runs. Volumetric Dissolve's 182.6 ms gap: trace lost, retake it.
    Dispatched 27 Nov (Opus Medium, agent id: see "Live agents"). 27 Nov report: root cause, gradual
    `afterRendering` units and off-screen proof on `6caceaa1b` (evidence `native_core/n5_2f/20261127_hitch_warm_units/`).
    Sent back: every figure so far, including the 22 Nov attribution, was compile-inclusive (`PYTHONDONTWRITEBYTECODE=1`
    in the Claude shells; proof guide, "Bytecode during timing runs"). Remeasure with bytecode cached, and split the
    first unit (about 34 ms with compile) until each unit is at most 8 ms on the GUI thread. Merged 27 Nov
    (`003b86fbe`, R-252): units at most 7.3 ms with bytecode cached; first run after the warm-up imports and builds
    nothing (7.4 / 8.0 ms); evidence `native_core/n5_2f/20261127_hitch_warm_units_split/`. Only the lead's rows remain.
    - [x] Root cause first, on the product path: show the first-run `transition()` cost split (module import, shader
      text build, first scene frame import) on a hidden host, with a negative control (a pre-warmed module removes
      that share).
    - [x] Fix at the owner, wherever it lives (the transition controller, the renderer registry, the native
      background, the prewarm owner): the next likely transition's module import and shader text build are warmed
      **gradually**: one bounded unit per spaced, already-rendered frame (piggybacked on frames the window renders
      anyway, spaced like S11's >= 0.2 s), next-likely transition first; never at startup, never in a burst, no new
      timers, threads, polling or forced frames; a run still prepares whatever is left. An image change resolves its
      transition only ~14 ms before its first frame, so the warm-up must not depend on that lead time. Guard test with
      a control seen failing on the old code (the first run's `transition()` pays the import).
    - [x] Agent: prove the fix off-screen first: on a hidden host, the first run's `transition()` after the warm-up
      pays no import or text build, and the warm-up units land one per spaced rendered frame (their per-frame cost
      recorded). Then stop and report "ready for the rows" with the commit.
    - Lead rows, 27-28 Nov (native Vulkan, 3840 x 2160 on Display 1, bytecode cached, one priming pass): both pass,
      no gap over 33 ms. Disintegrate max 14.65 ms (first 12.25), Volumetric Dissolve max 13.66 ms (first 13.66), render
      1.2-1.5 ms median, 0 % late. Measured under the operator's own running load (GPU 61-83 %, 10.5 GB in use;
      CPU 12-22 %). Baselines `tools/baselines/preflip/20261127_n52f_warm_units*.json`, traces in
      `.artifacts/evidence/performance/preflip_pack/20261127_20261127_n52f_warm_units*`. Side defect fixed on the way:
      `--per-row` wrote every row to one size-and-state folder, so a later row overwrote the earlier row's trace.
    - [ ] Side (N5.2f agent, 27 Nov): other scene transitions (Crumble, Glass Shatter, Exploding Tiles and others) still
      build their shader texts at import, so their first warm unit may exceed 8 ms. Measure each module's import with
      bytecode cached; split any over 8 ms into `WARM_PIECES` like Disintegrate's. Also measured: the native
      `mode.texture` copy costs 7-13 ms per run; attribute it before N5.2h (route cost, not general optimisation).
  - No cull fallback (lead, 22 Nov): indirect draw is core Vulkan 1.0 and OpenGL 4.0, and Python's population already
    draws with `glDrawArraysIndirect`, so no supported card lacks it; the core refuses with its reason if one ever does
    (ABI 41's facts record the answer). N4.c's one-million-sprite cost check runs on the indirect form only.
- [ ] N5.2g Edge Bloom, Capillary Bloom (N4.g); their fields are the first transition preparation run as an async
  job (D9, consumer class a).
  Reading (agent ac3072f8bea57441b, 22 Nov; `implementations/edge_bloom.py`, `capillary_bloom.py`, their `gl_programs`
  programs, `scene3d/edge_field.py`, `scene3d/propagation_field.py`, `native_background.py`, `job_service.h/.cpp`,
  `mode_content.h/.cpp` advanceTextures, `compute_passes.h`, `transitions/controller.py`, D9):
  - Both are one 2D fragment over the item quad (`item_quad_program`, as Liquid Lens: a `NativeFragmentPass`, no scene
    target), with `uv = (vUv.x, 1 - vUv.y)`, plus per-run fields sampled linear. Python draws the photo itself at
    progress 0 and from `EDGE_BLOOM_SETTLED` 0.97 / `CAPILLARY_SETTLE[1]` 0.94.
  - Edge Bloom: two edge fields (new picture, old picture), each built from its lent photo at `edge_field_size` (768
    on the longer side, the render's aspect): luma (16 linear taps of the photo, r16f), blur twice (r16f), edges (r16f
    strength, rgba32f seeds), jump flood (`edge_field_jumps`: 11 dispatches at 768, uJump per dispatch, rgba32f
    ping-pong), resolve (rgba16f field, sampled linear): 16 dispatches a field, one block `EdgeFieldDispatch` each. The
    glow colours are CPU (`photo_accent_colour` of each picture's rgba8, once per run). Thresholds from `detail`.
  - Capillary Bloom: one propagation field, photo-independent (seed, count, fibres, aspect) at `propagation_size` (256
    on the longer side): seed (cost + arrival, r32f; two blocks: `PropagationDispatch` and the consumer's
    `PropagationCost`, so `native_one_block`), 192 relax dispatches (two programs alternating over the same two
    images; after the even count the newest is the "arrival" texture), extent (one group of 256, a 1 x 1 r32f).
    The fragment samples arrival linear (r32f: the ABI 33 linear-filter fact) and the extent by `texelFetch`, and
    takes its front gradient from `dFdx` / `-dFdy`.
  - What the core lacks: (1) 192 + 4 dispatches exceed `kMaxModePasses` (48) as program entries; (2) a still admits only
    the "draw" trigger, so program entries would rebuild the fields every drawn frame; (3) the job service runs uploads
    only (`UploadJob`, `RhiUploadBackend::upload`); (4) no Python edge tells the layer that textures committed (only
    `on_textures_lost`); (5) mode textures are RGBA8 / RGBA16F / RGBA32F, no R32F.
  Design (agent, 22 Nov; ABI 43, written by no one yet, see the stop note below):
  - Fields are item textures made from a recipe, not program entries: `mode.field(name, recipe, packs, input=<item
    texture>, pixels=<the input's rgba8 or None>, deadline_ms)`. A recipe is plain data Python builds from the field
    owners' own texts and values: images ({name, format r16f/r32f/rgba16f/rgba32f, size}), a flat list of dispatches
    ({pack index, block bytes packed by Python's own `Scene3DBlockLayout`, checked against the reflected size, groups,
    bindings by shader name to an image with its access or to the input photo as a linear clamped sampler}) and the
    outputs (image -> item texture name). A flat list needs no repeat or per-dispatch scoping: the 192 relax dispatches
    are 192 entries over two packs, the 11 flood dispatches 11 blocks. Packs are baked by `tools/regen_qrc.py --shaders`
    from `EDGE_FIELD_PROGRAMS` and `propagation_programs("capillary", CAPILLARY_COST_GLSL)` (`native_one_block` for the
    seed), shipped beside the transitions' packs and counted by `native_transition_renderer`'s shipped check.
  - One recorder, two forms (D9 point 5): `FieldRecorder` (new, QRhi-agnostic: pipelines cached per pack, images,
    one uniform buffer of every dispatch's block at `ubufAligned` offsets uploaded once, SRBs cached per binding set,
    each dispatch its own QRhi compute pass) runs (a) on the job QRhi as a `FieldJob` (a ticket like `UploadJob`: it
    owns its pixels, uploads its input photo itself, waits on its fence, publishes each output's VkImage and layout),
    or (b) in the frame on Qt's QRhi at the commit, its input the item's resident texture (OpenGL, no service, a failed
    job, the deadline). Outputs import with `createFrom` like a job's upload and commit together with the item's other
    textures (D9 as built point 3: the destination photo and its fields switch in one record), retire through the
    window's list, cancel by compare-and-set, quiesce at teardown; the destruction barrier counts them.
  - The deadline is the core's: a field job not done by `deadline_ms` after its submit is cancelled at the next record
    and its in-frame form recorded there (the run ticks every frame, so a record follows). No Python timer.
  - The start edge: `mode.on_textures_ready(listener)`, queued to the GUI thread through the item notifier like
    `texturesLost`, once per commit with the names committed. The layer keeps the background's program on the old
    picture and pauses its own effect clock until the edge naming every field of the run, then samples the run at
    `now - (edge - run.start_ns)`. The controller is not touched: Python sets `deadline_ms` to half the run's settled
    margin (the duration times one minus the linear time at which the easing reaches the settled value), so the shifted
    run still reaches its settled frame before the controller ends it, and the end stays the exact new picture.
  - Inputs: the destination's pixels are the bytes the same `_start_run` hands `mode.texture` (one shared
    `TextureImage`, no second copy); the old picture's field needs its pixels again (one copy of the PresentationImage
    at the run's start, Edge Bloom only; recorded as a cost). Capillary's job has no input.
  - The drawing: each transition a `NativeFragmentPass` with extra samplers (`native_samplers(run)`: the field
    textures by name, linear clamped) that `transition_program` binds. Checklist 16 conversion first: Edge Bloom's and
    Capillary's fragments take `uShow` (old and new photos exactly, as Liquid Lens), and Capillary's native text
    corrects `dFdy`'s sign under `SRPSS_NATIVE_CORE` if the harness shows the core's rows reverse it (trap to read back
    first on both backends; `anisotropic.py` notes Vulkan's).
  - Formats: R32F joins `ModeTextureFormat` for the imported arrival and extent; RGBA16F fields exist.
  - Proof (proof guide section 3): the field textures read back against Python's on both backends (edge fields
    against `edge_field_reference` where small, propagation against `propagation_reference`), then rule (a) / (b)
    through `transition_route_check.py` variants (each default; Edge Bloom detail 0 and 1, every colour source, glow 0
    and 1; Capillary sources at both ends of `CAPILLARY_SOURCES_RANGE`, fibres 0 and 1), several image pairs, full
    durations, both dprs; the job form equal to the in-frame form (hashes), a deadline control (a job held past it runs
    in-frame, same pixels); `--cost` at 1440p and 4K both backends, the run's first effect record included; the D1
    hitch rows; registration last.
  - Open for the lead: the two statistical bounds `transition_route_check.py` proposes (`N52G_STATISTICS`: Capillary
    rules (a) and (b), Edge Bloom rule (b)), the reasons beside them. A run's first effect frame on a cold driver
    shader cache compiles its pipeline on the render thread (one 39-41 ms gap a row, then clean): N3.6's warm-up
    policy, not this box's.
- [ ] Pre-flip reference pack (operator, 15 Nov: "measure the gain instead of just telling ourselves it is good"):
  captured while the Python renderers are still the product, and **before N5.2h deletes them** (after that the
  "before" side cannot be measured). One script (extending `tools/visualizer_live_check.py` and
  `tools/overhead_baseline.py`, not a new system) runs the same matrix before and after the flip:
  - [ ] Every Visualizer mode (its default preset) and every transition, on Display 1 at 3840 x 2160 and on Display 0's
    size at 2560 x 1440, invisible saver, recorded music (`anything_mixed2`) over the Usu wallpaper: fps, render time
    median/p90, swap gap, late %, hitches a minute, saver CPU % of a core, GPU ms per frame, RSS and private memory,
    first-2-seconds frames.
  - [ ] Idle and loaded. game60 is only with the operator's yes on the day, 10 minutes at most, lead only.
  - The 15 Nov capture is done: every mode and the five-transition load set, idle and game60, on Display 1
    (`Benchmarks.md`, `tools/baselines/preflip/`); one size only (the saver takes its display's resolution).
  - [ ] Stored as a named baseline (`tools/baselines/preflip/`) and summarised in `Docs/Reference/Benchmarks.md`; the
    flip's acceptance reruns the same matrix on Vulkan and on native OpenGL and reports the gain per row.
- [ ] N5.2h The background family switches on OpenGL (D10 point 4): presenter, backdrop and all 28 transitions
  native in production; the native backdrop compared with the blit on the same frames; the Python presenter, the
  Python transitions, the blit backdrop and the wrapped-texture bridge deleted in that change.
  - [x] Gate (operator, 22 Nov: a start below Python OpenGL is a bad place to start; general optimisation stays its own
    phase after the flip): every transition's native OpenGL cost at or below Python's own on the same frames before the
    switch. Known: the native OpenGL route's fixed cost (Crossfade control 0.15 ms against Python's 0.04 at 4K,
    `n52f_cost`) puts N5.2f's native OpenGL (0.53-0.77 ms) above Python's (0.27-0.46); find that route overhead first.
    Behaviour under modest load (a game running) is a target, never an excuse: hitch rows run and must pass under it.
    Proof: the proof guide's section 3, "A transition port", Performance, every bullet. Binding (lead, 28 Nov):
    28 Nov report (evidence `20261128_route_cost_root_cause/`, before-table `20261128_n52h_cost_before_all/`):
    Crossfade on the same frames, Python 0.061 / native 0.104 ms at 4K (0.030 / 0.053 at 1440p). Named shares: the
    surface's full-triangle clearing draw (0.020 ms at 4K; `mode_content.cpp` `recordPasses`; fixed on OpenGL by the
    pass's own clear in `b483770bc`, Vulkan keeps it per rule B); the composite pass, Qt drawing the kept native
    surface into the window (0.030 ms at 4K; `composite.cpp`; open, below); the old cost round timed Python as a bare
    draw (fixed in `6e754c85d`: `python_product_frame_gpu` against `qrhi_frame_gpu`). CPU per frame is half Python's;
    `mode.texture` is a per-run copy (2.35 / 4.45 ms), below Python's first run frame (25-33 ms). Ruled out: per-frame
    sync, readback, resource or pipeline work, and a bridge copy. Fragment transitions sit about 0.047 ms above Python
    at 4K (the same two shares); scene transitions 0.06-0.15 ms at plain settings, up to about 0.9 ms with 4x motion
    blur and trails (`crumble_both_4x`, `glass_shatter_both_4x`).
    - [x] Root cause first, on the product route, off-screen (hidden host, 3840 x 2160 and 2560 x 1440): split
      Crossfade's native OpenGL frame cost against Python's on the same frames into GPU (timestamps around each
      pass) and CPU (submit, state, uniform upload, sync). Name each share over 0.02 ms with its owner. Candidates to
      prove or rule out: an extra pass, clear or copy on the native route (including the wrapped-texture bridge),
      a sync or readback, per-frame resource or pipeline work, and the native `mode.texture` copy measured at
      7-13 ms per run (N5.2f agent, 27 Nov: attribute whether it is per run or per frame and where it lands). Each
      named share gets a negative control (remove it, the share goes).
    - [x] Successor, after the build: `--cost` on both APIs with Crossfade's clear check passing (same pixels with and
      without the draw, clears counted by route, the draw's time back with `surface_clear_draw`), the route check's
      pixels unchanged, and the Vulkan figures not worse.
    - [x] Scene-target clears (28 Nov, `5025acb09` built, harness fix `613e82d58`; evidence `<N5.2h worktree>/.artifacts/
      evidence/native_core/n5_2h/20261128_n52h_cost_built_5025*`, `20261128_n52h_route_built_5025/`): OpenGL scene
      targets clear by their pass where measured cheaper; multisampled R16F targets keep the draw. `--cost` and the
      full route check (validation layers) pass on both APIs; Vulkan unchanged.
    - [x] The scene-pass gap (the real one; lead, 28 Nov). On the built module at 4K, `crumble_both_4x` native 1.495 ms
      against Python 0.929 (1440p 0.746 / 0.300); `crumble_plain` 0.204 / 0.146. Core record time is nearly all of
      the native frame, so the gap is inside the core's scene passes, not the route or the composite. Time each pass
      (GPU timestamps per pass: scene, motion-blur taps, trails, resolve, 4x) for `crumble_both_4x` and
      `glass_shatter_both_4x` against Python's same work on the same frames; name every share over 0.02 ms with its
      owner and a negative control; fix at the owner. Any C++ change: "ready for build".
      28 Nov (`ff29e64ee` per-pass timing built; `d5e9371ab` fix, Python; evidence `n5_2h/20261128_n52h_scene_passes_*`,
      `20261128_n52h_route_ghosts_first/`): share 1 named and fixed. The ghost passes split the 4x scene target into
      two runs, each paying the multisampled resolves (0.505 ms OpenGL / 0.230 Vulkan at 4K); owner the pass order in
      `scene_program`, now ghosts first, one run (`scene_target_runs` test with its control). `crumble_both_4x` 4K
      OpenGL 1.383 -> 1.109, Vulkan 1.058 -> 0.844; `glass_shatter_both_4x` 1.483 -> 1.204 / 1.143 -> 0.976.
      Open: about 0.42 ms at 4K OpenGL inside the single scene run (0.875 against about 0.45 for Python's stages,
      an estimate from the bare-FBO stamps). Suspects: QRhi's end-of-pass resolves and the kept clearing draws on the
      4x R16F attachments; split them with a C++ bracket ("ready for build"), and time Python's same span directly.
      Lead's Vulkan hitch row on Display 1 after the ghosts-first order (28 Nov, `d5e9371ab` on the `ff29e64e` module,
      primed, operator's load): Crumble and Glass Shatter pass, no gap over 33 ms, max 16.9 / 17.8 ms, first frame
      11.4 / 13.0 ms (`tools/baselines/preflip/20261128_n52h_ghosts_first_vulkan_hitch.md`).
    - [x] The composite pass: decided, not built (lead, 28 Nov). D5.2 stands: the core's output reaches the window as a
      texture, never as a draw inside Qt's pass (QRhi cannot record into the window before Qt's pass, which clears it,
      so a direct route would need an underlay or render node). The composite, Qt drawing the kept surface, is the
      architecture's fixed share: about 0.030 ms at 4K, owner `composite.cpp`. It is not removed; box 6 names it on
      each row. Kept on record if ever revisited: the five guards (no overwork on still repaints, no allocation or
      per-frame toggling on demand flips, both pass variants warmed gradually, no new threads/timers/polling, no
      flicker with per-frame readback across flips), plus the reader list in the N5.2h journal.
    - [x] Crossfade: native 0.088 / Python 0.054 ms at 4K (1440p 0.032 / 0.027); the remaining gap equals the
      composite's fixed share above, so it is named rather than fixed.
      Closed 28 Nov (fourth agent; `5359b9264` velocity one RGBA16F read as .xy, `121087442` OpenGL pass clear of
      multisampled RGBA16F, built; R-253): 4K `crumble_both_4x` OpenGL 0.717 against Python 0.923, Vulkan 0.711;
      `glass_shatter_both_4x` 0.848 / 1.040 / 0.820. Named, not fixed: the RGBA16F velocity moves twice RG16F's bytes
      (QRhi has no RG16F; RG16 would clamp an unbounded velocity; a packed R32 needs a packed-average resolve in C++),
      +0.039 ms pieces and +0.022 resolve at 1440p crumble.
    - [x] Then every transition: native OpenGL against Python OpenGL on the same frames (`--cost`, 1440p and 4K),
      one table, each row at or below Python's or named with its own share and owner (the composite's
      0.030 ms at 4K is named on every row). Done 28 Nov, 89 variants x 2 sizes (evidence
      `n5_2h/20261128_n52h_box6_a/`, `_b/` with `box6.py`, `_repeat/` overriding): 70 rows at or under Python, 94 over by
      at most the composite (0.0154 ms 1440p, 0.0297 4K; measured per pass on the two scene rows, the same full-screen
      pass on every other row), 13 by the composite plus under 0.013 ms (noise band), one named beyond: 1440p
      `crumble_both_4x` +0.043 (composite plus the RGBA16F share). Python's own figures swing up to 0.2 ms between runs.
      Lead's Vulkan hitch row passed (above). Gate closed: audited and merged 28 Nov (`f12427a2e`).
  - [ ] The switch (after the Gate merges; decompose here before dispatch). Order:
    - [x] Caller list (28 Nov, `acd9164542fb33bfc`): `<wt>/.artifacts/evidence/native_core/n5_2h/20261128_switch_caller_list/caller_list.txt`.
      Five callers rule out deleting in the same change as the route; lead decided each (28 Nov):
      1. Python transition references are drawn live by `transition_route_check.py` (rule (a) `:456-485`, `--cost`
         `:818-845`), `fullscreen_pass_check`, `background_layer_check`, `backdrop_pyramid_check`. **Cache them once
         before deleting**: frames per check case into the proof cache (keyed like the Visualizer references), Python
         cost figures as stored baselines under `tools/baselines/preflip/`. No frozen Python GL code is kept. The proof
         guide section 3 gains the transition rule in the same change (side defect found by the caller list).
      2. `release_media.py` and `onboarding_preview_foundry.py` capture only through `TransitionCapture` →
         `QuickTransitionRenderHost`. Operator 28 Nov: "Release media transitions do not need rerenders same with
         onboarding." Then: "The tools should still be updated for long term value, but re-rendering is a
         waste." The two tools move to native capture before the deletion, so they never break. That is N5.8's tool
         part, pulled forward; the Studio preview host stays in N5.8. Proof is a short capture of a few transitions
         into scratch, compared by eye against the shipped WebP or preview. Shipped WebPs and preview assets are never
         regenerated or committed.
      3. The Python transition classes stay as value owners (`block_values`, `scene_values`, `native_scene`,
         `regen_qrc.py:442-501` pack baking); only their GL draw code and `render_host.py` are deleted.
      4. `TransitionCapture` as the generic offscreen GL context (~45 tests, ~12 tools) moves to
         `tools/labs/render_target.py` `OffscreenRenderTarget`: mechanical, a Sonnet Medium slice.
      5. `start_quick_backend` (`bootstrap.py:652`) loads the core on OpenGL too. A failed Vulkan start falls back to
         native OpenGL as today's API fallback; a module that fails to load on both shows the photos through Qt's own
         `Image` with hard cuts and no transitions, logged as an error once (degraded display, not a second renderer),
         with a test.
    - [ ] Production route (built `5c81280f4`, finished `88f6bd2eb`/`39e01c6f4`; backdrop vs blit `9ef7ec49d`, OpenGL
      only so far). Lead D1 run 28 Nov on native OpenGL (wallpaper pair + recorded clip, 70 s, displays on): wallpaper
      and transitions drawn by the core, no faults, clean exit
      (`<a5767 wt>/.artifacts/evidence/display/d1_run/20261128_n52h_switch_gl_native/`). Side defects sent to the
      agent: stale reveal log wording (`display_manager.py:5375`), GL `v_uv`/`vUv` varying-name warning, five
      window-showing probes in `test_quick_backend_owner.py`, offscreen env leak into pixel wrappers, Cube Turn input
      53-59 levels vs Python. All done by `f475358aa` (vUv triangle `mode_up.vert`, C++), built on GitHub 28 Nov
      (module in the a5767 worktree). Pending: the D1 recheck that the warning is gone (displays off at 05:35; the
      agent confirms it offscreen meanwhile). OpenGL's background (presenter, backdrop, all 28 transitions) goes native, as Vulkan already
      does; one route per API, no Python fallback in the product (point 5's degraded display only). The product
      changes per the caller list.
      Side defect (found by N5.6, 28 Nov; product-relevant now that OpenGL is native): Qt's OpenGL backend sets
      sampler parameters on multisampled textures and logs GL_INVALID_ENUM every frame. Find which core texture or
      sampler pairing triggers it (a multisample texture bound through a sampler, or a QRhiSampler on a
      `QRhiTexture::sampleCount > 1`), fix it in the core (C++), and test that a validation-on OpenGL frame logs
      no GL errors.
      State 28 Nov: `e06691e3e` and `aab60aa9e` (marking each multisampled bind at record time, built as `163d41b8`)
      left the count unchanged: `eb_4x` 5, `eb_band_4x` 5, `tiles_4x` 1, all on frame 0. Advisor's diagnosis (Opus High,
      read-only; it had no Qt source on hand, so the Qt internals below are unverified). QRhi's GL backend writes sampler
      state at execute time, in `bindCombinedSampler` during `endFrame`. Each mismatch makes five calls (MIN, MAG, WRAP_S,
      WRAP_T, COMPARE_MODE), so each case of 5 is one mismatched bind. Record-time marking is undone by:
      (1) a `create()` after the mark in the same frame, which resets the cache. Frame 0 allocates the scene targets
      lazily and re-points the nearest-resolve bindings after a resize (`mode_content.cpp:6088`). This is the main
      candidate.
      (2) Two srbs binding the same multisampled texture with different `QRhiSampler`s, for example the capture's
      nearest sampler and the nearest resolve's `n.sampler`. The single error in `tiles_4x` may be this.
      Fix direction:
      - one shared sampler (nearest, clamp, no compare) for every multisampled binding;
      - one helper that `create()`s a multisampled texture and writes that sampler's state into its cache at once;
      - keep the record-time marking as a backstop;
      - a source test that no `sampleCount>1` texture is created outside the helper and no other sampler reaches a
        `sampler2DMS` binding.
      To name the exact call, use `SynchronousLogging` in the repro's `QOpenGLDebugLogger`. In the callback, read
      `GL_TEXTURE_BINDING_2D_MULTISAMPLE`, `GL_ACTIVE_TEXTURE` and `GL_CURRENT_PROGRAM`, and match the texture name against
      the core textures' `nativeTexture().object`. Check the Qt claims against the SDK's `qrhigles2.cpp` first.
      Result (`ad3b55fdd7e2d3dcd`, 28 Nov): the advisor was wrong. A synchronous debug-logger probe on `163d41b8` showed
      one error per multisampled texture at creation, not at bind. Qt's `QGles2Texture::create()` always sets
      `GL_TEXTURE_MIN_FILTER` after allocating, and that is invalid on a multisampled texture. The `eb_4x` case has five
      such scene targets and `tiles_4x` has one. Fix `158531ad9`: a `createTexture` helper in `gl_sampler_state.cpp`
      allocates the multisampled storage itself and hands it to Qt through `createFrom` (Qt owns and frees it). Both
      creates in `scene_targets.cpp` use it, and a source test plus negative control cover it. The admission test's
      wording is fixed in `123cf29d0`. The Waveform "first 4x frame" watch is likely the same cause. Built as `f9d4399e`;
      lead verified 28 Nov: gl_errors PASS (no errors), 52 tests pass in the module, scene-target and post-stage files.
      Verify: `post_stage_check.py --apis opengl --rounds gl_errors` and
      `tests/test_native_core_module.py::test_a_validation_on_opengl_frame_logs_no_gl_errors`.
    - [ ] The native backdrop against the blit on the same frames (the D7 pyramid's input): pixels or a named bound.
    - [ ] Cache the Python references (point 1) and retarget the four checks to the cache; native capture for the two
      media tools (point 2: scratch capture only, no asset rerender); the `TransitionCapture` → `OffscreenRenderTarget` move
      (point 4).
    - [ ] Delete: the Python presenter, Python transitions' GL draw code and `render_host.py`, the blit backdrop and the
      bridge. Tests that only pinned them go; tests of behaviour retarget to the native route. A test that nothing in
      the product or tools imports the deleted modules.
    - [ ] Proof: the route check and `--cost` on both APIs, a Display 1 run on native OpenGL (wallpaper folder +
      recorded clip), the hitch rows for the five-transition load set on both APIs, and the isolated suite at the
      milestone. Audit: Opus Medium, High if the deletion touches core lifetime.
      Proof run 28 Nov (Sonnet, module `f9d4399e`, the `ad3b55fd` line merged; evidence
      `<proof wt>/.artifacts/evidence/native_core/n5_2h/20261128_n52h_proof_route2/` and `..._proof_cost/`):
      - Route check, both APIs, validation on: PASS (`N52A VERDICT PASS`). `--cost` both APIs: PASS (opengl, vulkan).
      - Hitch rows: NOT RUN. `preflip_pack.py` rows are Display 1 only (`display 1 is not present (present: [0])`, 28 of
        28 skipped, nothing stored); they wait for Display 1 with the D1 run, on both APIs.
      - Isolated suite (`run_chunked.py --isolated`, 1213 files, 24 failed). Against the Gate merge `f12427a2e` the same
        24 files give 9 red already (so predating the switch, recorded, not fixed): `test_foundry_nav_and_eb_postport_20261119`
        (a plan heading it reads is gone), `test_qtquick_family_product_actions` (`core.mc` import),
        `test_qtquick_visualizer_custom_geometry_regressions` (`_Unit.screen_index`), `test_settings_input_foreground`
        (palette colours), `test_shader_derivatives` (`waveform_ribbon` unbound), `test_test_suite_durability`
        (two literals, `test_achievement_pulse_ring_surface_ownership.py:260`, `test_native_scene_transitions.py:529`),
        `test_visualizer_prepared_reveal` (`_Uniforms._locations`), `tests/unit/test_policy_compliance.py` (a raw
        `threading.Thread`, `packet_mailbox.py:472`), and `test_vulkan_shader_readiness`'s disintegrate bake.
        Switch-caused and fixed, a commit each: the four tests that read the deleted retained background node
        (`b106bfd42`), the scene orientation test's `capture.textures` (`OffscreenRenderTarget` has none),
        the slide test that drew the deleted renderer, the tooling inventory rows for `native_transition_capture.py` and
        `transition_references.py`, and `test_quick_exit_routes` (its negative control demanded a 0xC0000005 at exit that
        the switch's tree no longer produces; window and host counts stay the control, cause of the vanished crash
        unattributed).
        Switch-caused and NOT fixed (each needs a retarget, not an edit): (1) the card-material pixel tests,
        `test_achievement_pulse_ring_backdrop_fidelity`, `test_card_surface_panels`, `test_hidden_scene_retirement`,
        `test_surface_material_style`, `test_surface_opacity_adjust`, `test_visualizer_card_clip_contract` (38 tests):
        `tools/surface_material_capture.py`'s `MaterialScene` draws through `_HiddenQuickScene` (a QRenderControl GL
        texture), which has no native core, so `SurfaceBackdropOwner` raises "the surface backdrop needs the native core";
        it needs the hidden native host like `NativeTransitionCapture` (N5.8's tool part). (2) `test_qtquick_runtime`
        (2 tests): `tools/qtquick_render_node_smoke.py` asserts the Python render node's telemetry (GL initialised,
        image uploads, transition samples) and calls `BackgroundRenderItem.setProofProgress`, both deleted; the
        lifecycle half should be kept on the native layer's own evidence. (3) `test_vulkan_shader_readiness` (3 tests):
        the population and propagation composers' only resolved call sites were the deleted transitions' GL code, so
        discovery no longer evaluates them; it needs to read their native-pack call sites (`native_scene.py`).
- [ ] N5.9 True glass over the Visualizer (D7 point 7; D8 plus 5): after the Visualizer layer and the backdrop
  are both native; `Docs/Architecture/Card_Surface_Materials.md` section 2 invariant 6 amended for the native
  core in the same change.

**NF. The flip (P3.5): Vulkan the default, OpenGL selectable**

- [ ] One row-order convention again (lead, 22 Nov): N5.4 draws Waveform in Python's row order through the composite's
  `scene_rows: "up"` so its 4x edges match Python exactly; every other program draws top row first. Once the Python
  renderers are retired (N5.2h and the modes' flip), return Waveform to the core's row order, delete `scene_rows` and
  `u_scene_rows_up`, and re-baseline Waveform native-only (rule (b) and its reaction check); a test that no program
  declares another row order.
- [ ] N5.8 The Studio's preview host and window, and the release-media and capture tools, render through the
  same core; no Python OpenGL node is left in any Qt Quick surface of the process.
- [ ] The translucent-window question settled from N0.6 (the Studio's window: see-through if Vulkan can, else an
  opaque window with the system's rounded corners; the SMP build's window by D7 point 8's route, the artwork
  backdrop only where no route works).
- [ ] The flip gate of D10, item by item, as a record in the decisions document; then the backend setting in
  Settings (Vulkan by default; OpenGL the fallback, with the automatic start on OpenGL and its stated reason).
- [ ] A frozen GitHub build on Vulkan on Display 1; one load session after the operator's yes, Vulkan against
  OpenGL.

**N6. Primitives planned but never built: native only, on the primitives track**

- [ ] N6.1 Dynamic surface field. **High potential** (water, ripples, pools, melt, any reactive surface; Neon
  Lake's water and SMP surfaces could use it): a bounded GPU height and velocity grid with impulse injection and
  damping, a displaced mesh with true normals, reflection distortion driven by it (with N4.d).
- [ ] N6.2 Static scene geometry and materials. **High potential** (what turns a mode into a place: floors,
  walls, wells, simple skyline and tunnel slices, with roughness, bevel and contact shading, built once and
  kept). Operator, 28 Nov: a likely later help for modes like Extruded Bubble whose framing has very little room in
  which it renders correctly (surroundings that stay right at more poses). Not an EB defect and not scheduled:
  parity and the native core come first.
- [ ] N6.3 Advected smoke and haze on the volume primitive. **High potential** (atmosphere for every 3D scene;
  shares N4.f2's reduced-resolution path).
- [ ] N6.4 Photo-textured shells and planes with real depth. **Low potential until a consumer** (a transition
  or a mode built round the user's photos).
- [ ] N6.5 The opt-in deformable sheet. **Low potential until a consumer.**
- [ ] N6.6 Lightning: procedural bolt geometry and its light. **Low potential until a consumer** (one effect).

- [ ] N6.8 Frost and ice (operator, 20 Nov). **Consumer known:** Extruded Bubble's icy-water look, which reads nothing
  like ice today. A surface treatment: a rime or frost layer (a procedural frost normal and scatter, crystalline
  sparkle), refraction through ice (on N4.d's rough receivers and the scene probe), and an ice-to-water edge on N6.1's
  dynamic surface field. Research first: which parts are new and which are compositions of N4.d, N4.j and N6.1. Then
  its harness proof like the other primitives, then the consumer.
- [ ] N6.7 Dense procedural geometry route (operator, 13 and 23 Nov: `VK_EXT_mesh_shader` for fidelity, not
  merely speed). **Two distinct consumers, with different compatibility contracts:**
  - **Existing Visualizers during their original port:** preserve Python OpenGL -> native OpenGL ->
    native Vulkan parity and all accepted rendering. If mesh shaders subsequently **accelerate/rewrite
    that original accepted rendering**, its QRhi/indirect or compute-cull + indirect twin must
    preserve the same original picture on OpenGL and Vulkan without the feature. Candidates
    remain existing EB beads/bubbles, Neon Lake terrain/culling and Waveform ribbons.
    Proof: original-mode visual parity with the twin, N2.6 GPU median/p90, clean validation.
    A **new** optional artistic effect ADDED after native port acceptance (approved N6 Kelp
    Cathedral, for example) may instead be feature-gated Vulkan-only, with no OpenGL
    reproduction of its *new art*, and disabled without perturbing the base mode.
    Neither class changes existing presets or holds up the native Studio or NF flip.
    N6.2 scene geometry and N6.3 smoke remain shared primitive candidates; their
    new artistic consumers are in the N4/N6 approved integration box below.
  - **New modes authored only after the Vulkan-default flip:** may explicitly require Vulkan and
    `VK_EXT_mesh_shader` when it enables their intended geometry and fidelity; **no OpenGL or non-mesh twin and no
    pixel-parity obligation to an implementation that never existed.** Selectable OpenGL remains for existing modes,
    not as a mandated renderer for new Vulkan-only modes. Modes requiring unavailable capabilities are visibly
    unavailable with an accurate reason rather than silently substituted, degraded, or allowed to fail device creation.
    Consumers in order: **Reactive Liquid / Audio Melt Pool first, Concrete Rain second** (their contracts are in
    `Docs/Future_Work/`). Neither is obliged to use mesh shaders for every pass; admit where it helps the authored
    target. Higher fidelity is a valid admission reason without proving that traditional rendering was too slow.
  - **Optional early N6.7 proof route:** if a real mesh-shader consumer is needed *after N5.8/NF
    and EB native parity but before the new modes*, the approved Kelp Cathedral is the
    appropriate Extruded Bubble integration. Rooted curved stalks and attached leaves
    with delayed current-driven movement are fully specified in the N4/N6 artistic
    integrations below. Kelp Cathedral **is approved eventual work** even if a
    harness proves mesh shaders first; it must have real Studio visual/reactivity
    controls and a new editable demonstration preset at final admission.
    A harness alone can satisfy the early pipeline proof, avoiding any artificial
    Kelp-before-flip gate. No change to existing accepted EB, presets or OpenGL output.
  - **Native seam:** use the core-owned Vulkan device (D6), enabled feature bits and reported limits; a reusable
    raw-Vulkan graphics-pass service inside the frame driver's existing pass graph, with
    `QRhiCommandBuffer::ExternalContent` and `beginExternal()/endExternal()`, retrieving the current native command
    buffer *after* `beginExternal`. Own `VkPipeline`/`VkPipelineLayout`, descriptor bindings, render-pass
    compatibility, state transitions, resource hazards, deferred destruction and loss recovery through the core;
    create/warm pipelines outside visible `render` calls. Do not introduce a separate frame loop, window,
    compositor, resource owner or per-mode renderer.
  - **Shader admission:** add Vulkan-only `.mesh` and optional `.task` GLSL -> SPIR-V (`SPV_EXT_mesh_shader`)
    compilation and validation, embedded with the native packs; keep existing `qsb` cross-backend
    `.vert/.frag/.comp` checks intact. Never try to cross-compile mesh/task stages to GLSL 430, HLSL 5.0 or
    MSL 1.2. Proof includes compilation failure controls, feature-disabled refusal, live validation and
    synchronisation, bounds/workgroup/primitive limits, GPU timing, teardown, device loss, display changes and
    operator visual acceptance against the authored mock. No raw pipeline is created on devices without support.

**N4 / N6 approved primitive demonstration integrations (operator, 23 Nov; POST-FLIP ARTISTIC WORK)**

**Ordering is non-negotiable:** finish required original-mode primitives, port parity, **N5.8's native Studio
preview/host/capture migration, then NF's Vulkan-default flip** without waiting for any of the additional
artistic integrations. Unconsumed high-potential primitives continue on their independent, non-blocking
primitives track; an approved optional integration is scheduled only **after its host mode's native parity
and native Studio have been accepted**, when its underlying native service is ready. An earlier core harness
may be used to prove the primitive itself, but the new Studio integrations and new presets are NEVER
new NF, Studio-flip, Waveform/EB/Neon Lake parity or existing preset migration gates. Work may proceed in
parallel after those prerequisites if resources allow, without displacing Melt Pool then Concrete Rain's
post-flip order or generating a second renderer. Each **approved integration** requires independent
review of its Studio implementation and an authored demonstration preset.

**Common engineering, fidelity, Studio and reactivity admission contract (every integration):**
- Feature must be independently enabled/disabled, using canonical per-mode typed settings and the
  *production* renderer/logical owner, with inactive feature causing no simulation, native draw pass,
  extra analysis, recurring work or allocated effect-only GPU resources. Existing presets, Custom,
  user selection, Studio state and base-mode behaviour are unchanged; there is no global default-on
  surprise, hidden extra clock, second renderer or unsupervised photo/wallpaper replacement.
- **Studio implementation is part of 'done'.** Expose Enable plus adequate and meaningfully independent
  appearance/geometry/colour/material, placement/density, dynamics and music-response parameters
  in the mode's EXISTING Studio through canonical schema/adapter/property admission. Use appropriate
  typed shapes, directions, gradients, colour, quiet-to-peak ranges and intensity curves as supported.
  One toggle or a single overall strength slider is inadequate. Every setting must visibly affect
  the production picture within its admitted range (when enabled), round-trip through Studio preview,
  Save/Cancel, undo/redo, Custom, Settings, preset authoring and restart. No separate Studio renderer,
  bespoke settings source, raw frame-thread editing or inconsistent setting fallback. Give sufficient
  discoverable grouping and explanatory labels so an operator can art-direct the feature in detail.
- **Music response must be authored rather than generic noise**: reuse the existing mode's canonical
  production audio snapshot and sole logical clock. Distinguish sustained musical motion, transients,
  envelope/phrasing and silence recovery where useful, with independent mapping for each
  visually meaningful reaction. Avoid the assumption that all effects should follow bass, a
  lone shared scalar or identical peaks. Controls should provide quiet/peak response, modulation
  strength, sensitivity, attack/decay/recovery, speed or lag and event emphasis only as appropriate
  to that physical component; don't duplicate native DSP or mask the mode's existing musical output.
  Continuous motion should have inertia, no pops, strobe, clipping or reset on the next beat.
- **Visual fidelity bar:** no static substitute for a reactive element, geometry made of conspicuous
  camera-facing cards, identical repeated pattern, broken attachment/contact, depth/sort flicker,
  shimmery aliasing, disconnected reflection/shadow, foreground clipping, overly uniform noise,
  uncontrolled bloom or cheap fullscreen postprocessing passed off as 3D structure. Judge close
  and distant views, orbit/pan, stereo-free depth cues, quiet/medium/loud music, multiple aspect
  ratios, card/fullscreen, DPR, light/dark backgrounds and movements between two displays.
  Preserve readable original composition; never blanket-mask a visualizer with the new feature.
- **Test proof uses NO PRESETS, EVER.** Synthetic test-owned parameter sets (including off/default,
  extremes and unusual combinations), deterministic source/seed/input, fixture-owned audio traces,
  feature-independent base-mode parity, each control's visible or measurable effect, physical
  continuity, life-cycle/retirement/device-loss and performance (CPU/GPU p50/p90 and tail, card
  and 4K, feature off/on) form the automated acceptance. DO NOT test preset format using real
  preset files either: fabricate ephemeral test-owned preset-shaped files if exercising persistence.
  Rendered WebPs, native live sessions and the new editable demonstration preset are **human review
  and artistic evidence only**, never automated image or value goldens. A Studio Save To Preset
  explicitly creates a *new* editable demonstration, preserving all existing authored files.
- **Portability:** a new optional feature that truly requires mesh shaders may be exposed on
  Vulkan only, with specific capability reason and disabled/inapplicable controls on OpenGL;
  the existing base mode retains its original OpenGL/Vulkan parity. Do not fabricate a
  lower-quality OpenGL twin just for the new feature; where shared cross-backend primitives
  already suffice, use them. Versioned lifetime, warm-up, quality tier and bounded populations
  follow the established native core. A primitive may land first with its harness; it counts
  as a *finished approved visual integration* only with the Studio and new preset.

- [ ] **1. Extruded Bubble: Kelp Cathedral (N6.7 mesh shaders if valuable, N6.2 geometry, N4.h shadows,
  existing N4.k shafts).** Build a genuine small underwater kelp habitat in the same scene coordinate
  frame as the bubbles: individually rooted and tapered curved stalks with physically attached
  fronds, coherent variation in height, spacing, branching, shape, leaf size, curl, translucency,
  surface normals, light interception and real depth/occlusion. Spatial composition should
  leave clear routes for the bubbles instead of turning the entire view into a green curtain;
  near and distant kelp should separate naturally as the framed camera moves. Stalk bases
  resist displacement while tips sweep; fronds inherit host-stalk velocity and attachment,
  lag with their own bending/recoil and gradually settle. Water current varies continuously
  across the environment rather than all stalks performing an identical sine-wave dance.
  Reactivity: distinct mappings for slow background current, sustained phrase-driven bending
  and bounded phrase/onset flourishes in tip speed/leaf flutter; quiet scene remains alive,
  peaks have headroom and recovery retains inertia. Never detach leaves, tunnel stalks
  through bubbles without depth, billboard them to the camera, reset old stalks on a hit,
  or conflate their motion with newly spawned bubbles only. Studio: enable, habitat coverage,
  root zones, stalk count/spacing, height, thickness/taper, curvature/stiffness, frond
  density/size/curl, tint/material/transmission, optional shadow/shaft influence and
  orientation; current direction/base speed, sustained bend quiet-to-peak range, onset
  influence, leaf flutter/lag, response attack/relax, spatial coherence and turbulence
  limit. Segments, draw dispatch and shadow participation are bounded by quality.
  **Mesh-shader kelp is a genuine optional Vulkan-only feature if that fidelity warrants
  it; the existing accepted EB remains untouched on OpenGL.**

- [ ] **2. Waveform Ribbon: Smoke Signals (N6.3 advected smoke, N4.f2 reduced-res volumes).**
  Real volumetric smoke emerges from art-directable sources ON the moving ribbons
  (specified edges, points, ends or contact zones) and continues moving in world space
  after emission, inheriting ribbon velocity at birth. Long graceful wisps curl,
  stretch, roll, diffuse and dissipate; density, colour and soft light vary through
  3D depth; smoke properly occludes and mixes with the ribbons instead of behaving
  like flat scrolling texture or general fog. Avoid obvious sprite balls, repeated
  plumes, volume banding, hard depth intersections and a cloud that entirely obscures
  the original lattice. Reactivity: separate baseline ambient trail, sustained musical
  generation/turbulence/vertical drift and a bounded transient accent plume; lingering
  smoke retains history as a phrase ends, no instant reset/disappearance on silence.
  Studio: enable, emitter geometry/position, amount/rate, thickness, lifetime, colour
  gradient/opacity, buoyancy/direction, inherited motion, advection/curl/turbulence,
  diffusion, depth softness, occlusion and quality; independently controllable
  musical emission, curl force, ascent/spread, transient accents and decay/inertia
  mappings. A music-controlled recolour of existing fog **does not count**.

- [ ] **3. Neon Lake (`shockwave_grid`): Rainfall Echo (N6.1 surface field, N4.d wet/rough optics,
  N4.c bounded impacts where needed).** An optional physically coherent layer of
  droplets striking actual basin water coordinates, each creating locally
  propagating, perspective-correct wavelets. Different impacts interfere
  and decay in a bounded height/velocity field; displaced surface normals alter
  genuine nearby reflections with stable spatial correspondence. Near/far impact
  sizes, crests and light/shading must read as water rather than painted rings,
  glowing stickers or fullscreen distortion. Respect the original authored
  shoreline, heightfield brush, analytic baseline reflection and music response:
  no land-crossing rings, moving shoreline or replacement water renderer.
  Reactivity: map sustained musical energy to an evolving rain density/placement
  and wave texture; accents independently increase selected impact energy,
  ring/crown emphasis or local disturbance; preserve distinct quiet, sustained
  and busy looks without hitting a permanent high-water ceiling. Studio: enable,
  density, coverage/strike region, placement seed/distribution, drop scale,
  impulse energy, ring width/speed, damping/viscosity, interference strength,
  detail/crown/spray, wet reflectance/roughness and tint; quiet-to-peak mapping
  separately for strike rate, impact strength, surface propagation and reflection
  breakup, plus transient probability/weight, attack and relaxation. History
  continues across events, bounded for long takes; off is exactly original lake.

- [ ] **4. Waveform Ribbon: Shadow Theatre (N4.h shared directional shadow maps).**
  Moving 3D ribbons cast meaningful, physically attached world-space shadows
  onto the existing floor or a declared receiver. Shadows trace individual
  curved ribbon portions and overlapping silhouettes with convincing penumbrae,
  contact definition, changing distance falloff and plausible light direction.
  Stable across orbit, tilt, zoom, raster size and music-driven geometry:
  no projected grey blob, fake detached double-image, crawling texels,
  peter-panning, acne, or shadow remaining static when the ribbon moves.
  The floor's colour, lighting and existing reflections remain separately
  readable. Reactivity is primarily the *actual* music-driven ribbon
  deformation causing continuously evolving silhouettes; optional gently
  varied shadow intensity/penumbra can respond separately but must stay
  physically coherent with the caster and light. Studio: enable, caster/receiver
  participation and light selection/direction, shadow opacity/colour,
  filtering softness, contact falloff, projection reach, bias within safe
  limits, quality resolution and optional music-controlled shadow
  emphasis/softness with response curves/smoothing. Validate depth-sampling
  and backend bias via synthetic harness; never tie correctness to the
  demonstration preset's ribbon pose or camera.

- [ ] **5. Extruded Bubble: Abyssal Lanterns (N4.m shared soft-light array; optionally
  N4.c compacted populations).** Submerged bioluminescent organisms/clusters
  travel among the existing bubbles. They are real local light emitters:
  near bubbles show moving reflections, transmission/rim shading and
  sensible distance/angle falloff, distant bubbles show less. Light colour,
  size, spatial distribution, softness, grouping and travel speed vary
  enough to make recognisable colonies instead of a fixed array of bright
  dots. Brightness must be energy-bounded to avoid uniform exposure,
  neon fog or strobing; don't assign every particle a full shadow caster
  or duplicate the shared N4.m service. Reactivity: continuous drift
  carries light fields, sustained musical phrases make rolling
  illumination, distinct accents pulse selected clusters with delayed
  fade; genuine bubble lighting changes, not a glow overlay floating
  on top. Studio: enable, population size/cluster density/regions,
  emitter shape/size, colour/temperature/gradient, brightness,
  light radius/falloff/softness, affected geometry, motion direction,
  drift speed/coherence and quality cap; independently controllable
  quiet-to-peak brightness, pulse probability/strength, travel
  acceleration, phrase speed, transient accent and decay. Maintain
  stable identities across source updates and camera moves.

- [ ] **6. Waveform Ribbon: Rain-Slick Floor (N4.d wet masks, planar reflections and
  rough receivers).** Actual floor-space patches of damp and shallow pooled
  water, with irregular believable contours, roughness gradation,
  varied micro-normal relief and wet/dry transitions that retain
  visible floor material. Reflected ribbon silhouettes must originate
  from current world-space ribbon positions and respond to camera
  movement, floor normals and wetness: sharp in calmer deeper areas,
  blurred/broken over rough thin films. Light grazing across wet
  edges should show sensible specular variation, not solid black
  mirror plastic or random circles pasted over the frame.
  The *wet patch geography is fixed in the environment*, not a
  beat-synchronised flashing mask. Music: the moving source ribbon
  produces corresponding moving reflections; optional bounded
  micro-disturbance changes local ripples/roughness/reflection
  breakup with sustained phrasing and gentle transient emphasis
  while the wet coverage itself remains anchored. Studio: enable,
  coverage/seed/patch density/scale/irregularity, wet and dry
  tint/roughness, film-depth impression, micro-normal strength,
  glancing highlight and reflection strength/blur, distortion
  anisotropy and quality; separate response intensity, quiet/peak
  disturbance, transient detail, attack and smoothing/recovery.
  Reject spatially disconnected reflections, sliding/teleporting
  puddles, uniform polished mirror and postprocessing pretending
  to be surface physics.

- [ ] **7. Bubble: Ice Chunks.** Add a primitive with varied chunk shapes and slight
  translucency. Give the chunks an optional subtle chill glow and let them break
  into visible fragments that shed particles. Integrate these controls into Bubble
  Studio and prove the effect in the native renderer with a genuinely ice-like Bubble
  preset that shows the shape variation, translucency, fragmentation, glow and particles.

**Do not convert the above checkboxes into mere request fulfilment screenshots.** Their art targets
are concrete quality bars for the live, editable, reactive Studio/production-renderer behaviour; the
recorded demonstration preset is only one freely mutable example of what the canonical controls can do.
For new, genuinely post-flip Vulkan-exclusive modes Melt Pool then Concrete Rain, N6.7's distinct
no-OpenGL-twin policy continues to apply. This optional existing-mode work must not delay either the
port/Studio/native flip or the designated new-mode order.

### Item 9. After the native core: new visualizers, then QoL; SMP separately deferred

Existing-mode ports still obey every cross-backend parity/readiness rule. New post-flip Vulkan-only modes use the
N6.7 Vulkan capability and shader-admission rule instead of a manufactured OpenGL twin.
Operator, 27 Nov: from the next completely new mode on, no OpenGL version is made; on an OpenGL run (chosen or
fallback) the mode is skipped in rotation and greyed in Settings and the Studio with its reason. The next mode
(Reactive Liquid / Audio Melt Pool) is expected to generate its geometry, and texture effects where needed, with
mesh shaders (N6.7). Still some way off. Expanded Visualizer continues
meanwhile (item 3; plan 01, whose section 0 holds the phase ladder and the 4K budgets).

- [ ] Oscilloscope legibility (operator, 21 Nov; after the flip, with the other mode tweaks): a setting that slows
  the trace's apparent noise while it stays reactive and busy. Today every preset moves so fast the trace reads as
  static to the eye. Research first: which motion carries the speed (sample window, refresh of the trace, jitter
  from noise), and how to slow what the eye sees without lagging the reaction. For example, temporal smoothing of the
  displayed trace shape against the reaction envelope, or persistence. Judge it with the music-response traces and
  live rendered motion, never twitch.
- [ ] Before the first new mode's Studio (lead, 27 Nov): one shared spec-to-Studio translator. Every
  `ui/studio/*_adapter.py` copies the same loop over `spec.body_controls` (Slider/Toggle/Choice/Colour into
  `StudioProperty`, decimals from `display_multiplier`, label and tooltip fallbacks, bucket to workspace), and the
  copies have drifted: Oscilloscope raises on an unplaced control, the others skip it or default its workspace; label
  and tooltip fallbacks differ. Move it into `ui/studio/schema.py` with each mode passing only its bucket map, priorities,
  icons and its own extra rows (Custom rows, ScenePath inspectors); each adapter's schema identical before and after
  (compare `build_schema()` output per mode), drift resolved to one rule. Then a new mode's adapter is its bucket
  map, extras, evaluator and recorded inputs.
- [ ] Studio camera saving has two buttons (operator, 28 Nov, later work): "I think there is duplication in save
  camera. The save camera button works well but there is a second button that claims to be involved with saving a
  camera (And tick mark glyph I think?) which is either useless or poorly explained." The second is the toolbar's
  tick, `keepViewButton` ("Keep View", `StudioShell.qml` near line 2961, `controller.keep_view`). It commits the
  previewed lens (FOV) as an undoable edit, and the orbit only when the store's camera policy allows; dolly and pan
  stay previews. Save Camera (`saveCameraButton`, `controller.saveCamera`) writes the preset's starting camera.
  Decide one model: either fold Keep View into Save Camera, or give it a name and tooltip that say what it keeps and
  how that differs. Then check every orbiting mode's round trip (`test_framed_camera_home_round_trip.py`).
- [ ] New native-core modes in this order: **Reactive Liquid / Audio Melt Pool, then Concrete Rain** (section 7,
  lab and mock-fidelity proof first). Usu Moonscape remains a later, separately admitted long-horizon concept;
  it does not block SMP re-evaluation just because it is listed after Concrete Rain.
- [ ] Very low priority, after the native core and its new primitives (operator, 14 Nov): Extruded Bubble's arctic
  look is flat, with "nothing icey about it": no ice, frost or anything inventive. Rework it once the native
  primitives give it real material tools (frost and ice surfaces, refraction, a sparkle field), not with today's
  parameters alone. Presets are authored content: the work is new EB capabilities, plus authoring that preset with
  them. The lead judges it on showcase WebPs over bright and dark wallpapers.

**Post-Concrete-Rain sequencing (operator, 23 Nov):** undertake a substantial round of product QoL improvements
from the remaining current-plan defects and operator priorities. **This phase includes the
post-M4/Theme Studio cross-profile Live Settings milestone in 1B.8**, without advancing it ahead of
native/Studio NF, Melt Pool or Concrete Rain. The operator, not an automatically satisfied
date, phase counter, or a generic "native flip complete" gate, decides when that QoL phase is sufficient to
consider SMP. No SMP M0-M10, library, audio playback, ZIP skin or desktop-host implementation is active in this
plan. Its complete deferred implementation order and contracts live at `Future_Work.md` §2.5 and plan 02.
Do not accidentally design out future SMP: `Docs/Guardrails/Presentation_Change_Preflight.md` keeps the small,
host-agnostic architectural invariants binding on current work, without requiring speculative SMP features.

## 1B. Operator defects and requests (11 Nov; backlog under section 1's Order, in this internal order)

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep
`[~]` validation steps and open side defects. Order: the Edit/exit defects, the Studio work, the fullscreen
overlay contract, window material and corners, presets last. Every fix reproduces its failure first; the lead
judges visual items on rendered pixels and audits each branch against the pre-fix code before merging.
**Nothing in this section waits on the operator** (operator, 11 Nov: checks are the lead's work; a remaining
question without a simple test is a Watchlist item, never an open phase). What needs the real product on real
hardware is proven by the lead's harnesses in 1B.14.

### 1B.1 Edit edits the display it was entered on (contract: plan 01 M3c)

- [ ] Side defect (unreproduced): in an ordinary global Edit, closing the Visualizer and then switching mode makes
  `activate_edit_visualizer_profile` return False (`rendering/quick/custom_layout_owner.py`, the `visible is None`
  branch), which looks like a forced runtime reload. Reproduce in a test or rule out.

### 1B.2 Cursor keeps its changed shape after exit until a click (R-183; proof in 1B.14)

The harness reproduced the stuck shape only with Qt's pointer tracking cleared artificially: the real exit path is
unproven.

- [ ] Side defect: when a hovered QML item is destroyed or left, the saver window can keep the hand or arrow
  instead of the Halo until the Halo next re-applies it.

### 1B.4 Shape instrument for Spectrum and Neon Lake (contract: Visualizer_Studio.md)

- [~] `fft_to_bars` gained two helper calls per tick (`shape_bar_profile`, `lane_sample_positions`). The overhead
  baseline was re-recorded after 1B.4 merged (`tools/baselines/overhead/2026-11-11_4658981b.json`, with a Spectrum
  case): the lead confirms the two calls are in it, then deletes this box.
- [ ] Admitted later if wanted (operator's call): a pop-out larger canvas; Spline Curve's layer nodes and Voxel
  Sphere's zone boundaries on the same instrument; Shift axis lock, snapping, double-click reset.

### 1B.5 Neon Lake: all visible land is brush-editable

Contract: `Docs/Reference/Neon_Lake_Basin.md`.

- [ ] Distance-based mesh density was not built (the mesh does not know the eye, and a camera-dependent mesh
  would rebuild and pop): no render shows whether the smallest brush aliases on far land seen up close; render
  it once, and only then decide whether anything is owed.

### 1B.6 Neon Lake: smooth land reaction, Growth and Indents

Contract and measurements: `Docs/Reference/Neon_Lake_Basin.md`. The lead decides when the reactivity is good enough
(operator, 11 Nov).

- [~] Lead's reactivity verdict: watch `indents_p1_heavy1.webp` and one driven showcase per preset with Growth
  and Indents on, beside the music envelope (`tools/visualizer_replay/neon_lake_music_response.py --continuous`);
  write the verdict here (good enough, or the one thing that is still weak) before any further reaction work.
- [ ] Side defect: `tools/visualizer_replay/waveform_music_response.py:63` silently skips recordings without PCM
  (heavy1, quiet_intro*, balanced*) and the report drops those songs without saying so: name them in the report.
- [ ] Side defect: the cost probe does not count GL or Python calls inside modules loaded under alias names, so
  one-session comparisons against an old renderer have meaningless call counts: count by module object.

### 1B.7 Fullscreen Now Playing: one geometry contract with the Media widget (plan 01 M3c)

Contract: plan 01 M3c (what stays overlay-specific, with its reason); the old artwork-factor bridge is in
`Docs/Architecture/Persisted_Input_Compatibility.md`.

- [ ] The safe-area edge guides are no longer drawn in Fullscreen Edit (as in ordinary Edit); confirm that is
  wanted or restore them through the ordinary guide owner.
- [ ] Evidence gap: no side-by-side render of the Media widget's own Edit beside Fullscreen Edit (it needs an
  off-screen harness that drives ordinary Edit on a Media card); build it beside
  `tools/expanded_visualizer_evidence.py`.
- [ ] **Now Playing app-mixer volume child (operator, 18 Nov; new request supersedes only the old "no volume rail" HUD design, not the OSD):** add a separate, independently editable volume child inside fullscreen Now Playing using the Media widget's existing volume child presentation, application-mixer volume authority, semantic colours and material surface. **The Volume OSD controls system volume; this new rail controls application mixer volume.** Never substitute one value/endpoint for the other, add a second volume owner/poller, or display a fabricated app level when the existing Media model cannot provide one.
  - [ ] Default placement follows Now Playing's artwork side: just **left of the artwork** when artwork is on the left, and just **right of the artwork** when artwork is on the right; orientation changes and Now Playing movement/resize move the authored default together. The rail remains its own adjustable/movable child under the existing Fullscreen Edit child-geometry, containment, guides, Undo, Save/Cancel and profile persistence rules; respect explicit child offsets rather than re-snapping them on every layout change.
  - [ ] Inherit the working Media volume child's tint, opacity/material, border and shadow semantics; verify surface rendering on bright/dark fullscreen Visualizers without demanding continuous Visualizer captures. Keep system OSD priority and separate OSD geometry unchanged. Test both alignment sides, missing app-volume capability, edit round trips, multiple displays/DPR and ordinary Media parity. Detail belongs to plan 01 M3c's existing Now Playing child contract, not a second fullscreen editor or a new native-core workstream.

### 1B.8 Light themes are practically opaque in the saver (M1, M2 and M2b merged; M3 waits behind the native core)

**Material track (operator, 11 Nov: proper transparency on light themes, no inset while keeping the material on
all themes, border materials). One agent, one shader, in this order, each its own reviewed checkpoint.** Contract:
`Docs/Architecture/Card_Surface_Materials.md` ("M1 dark-ink rule"; it also holds M1, M2, M2b and the 12 Nov
follow-ups with their evidence folders).

- [ ] Watch: the "three failures in one long run" were not reproduced in any order of that run's 21 files; the
  long run's other two failures may have been the engine worker gate (red since 438790f7, fixed 4a805fe6).

- [ ] Accents whose corrected text ink collapses toward the card text: Royal Orchard most (#3e4f2c to #97a08d,
  48 % of its colour kept) and Smoke Quartz; Slate Lavender, Tungsten Blues, Lantern Grove and Riviera Dusk keep
  61-70 % (`.artifacts/evidence/materials/20261111_m2b/ink_rule/accent_collapse_candidates_3x.png`). A theme-authoring matter: these six accents are too dark for a
  dark card; note it for the theme files, no solver change.
- [ ] The accent as a graphic (bars, dividers, icons; not recoloured) is under 3:1 on eight dark themes: Royal
  Orchard 1.44, Tungsten Blues 2.27, Lantern Grove 2.32, Slate Lavender 2.35, Smoke Quartz 2.59, Riviera Dusk
  2.67, Forest Rose 2.89, Nordic Signal 2.89. The same theme-authoring note.
- [ ] Mid-transition frames and a real display for M1, M2 and M2b: a D1 run (1B.14 harness), lead review.
- [ ] M3. With the inner hairline gone, the border stays clearly distinct from the face on the three light
  themes over a busy bright wallpaper and over a dark one (3x edge zooms); no second line inside the card.
- [ ] **Context Menu backdrop correctness (operator, 16 Nov; close before SMP):** its current `MaterialSurface` samples the shared wallpaper/dimming pyramid, even when right-clicked over another card or the fullscreen Visualizer. This distorts an image which is not actually behind the menu. The menu and its submenu must either sample the *real visible underlay* or render as straightforward theme-coloured translucent surfaces; never advertise a false glass result.
  - [ ] **Investigate first, bounded to the existing material/native compositor:** assess native QRhi's retained layer textures and N5.9's proposed overlap-limited Visualizer glass (D7 point 7; ≤0.3 ms). That source alone omits ordinary cards. Check whether a colour-accurate, correctly ordered *local* composited-underlay texture for the menu's rectangle can be obtained without a new fullscreen capture, CPU/GPU readback, synchronous right-click frame fence, duplicate blur chain, Visualizer-frame work while no menu is shown, or compositor rearchitecture. Test both menu and submenu as they move and overlap other surfaces. No risky new capture owner just to simulate glass.
  - [ ] **Decide by evidence, not the material label:** adopt true blurred/translucent glass only if its sampled colours and spatial details reflect the actually visible wallpaper/cards/Visualizer, its local cost is within N5.9's overlap budget where relevant, and opening, submenu reveal and frame p90 show no meaningful hitch or regression. **Otherwise choose Normal with theme-derived RGBA opacity/tint** (including existing ink-contrast, border, shadow, hover and opacity-adjust authority): a naturally transparent coloured menu with no special wallpaper sampling, fabricated distortion, capture or extra material pass. No new theme switch required.
  - [ ] **Proof and ordering:** compare right-click over bright/dark wallpaper, opaque/translucent cards and active fullscreen Visualizer, including while a wallpaper transition runs; check submenus, clipping, colour/alpha, light/dark themes and mixed DPR on both native OpenGL and Vulkan where supported. Capture pixel evidence plus GPU cost, input-to-menu latency, frame p90 and dormancy, with the Visualizer uninterrupted. Place final material behaviour in `Docs/Architecture/Card_Surface_Materials.md`; use focused Context Menu regressions. This is pre-SMP surface work, shared across Screensaver, Dashboard and SMP, and must not create an SMP-only renderer.
  - [ ] **Fullscreen Now Playing vs Context Menu underlays (operator, 19 Nov):** the shared wallpaper/dimming material backdrop cannot represent the foreground of an active fullscreen Visualizer. The ordinary Media Control Bar's theme material is accepted and must not regress. **Now Playing is resolved independently:** its optional card and its shared transport bar use semantic **Normal** colour fills with alpha blending directly over the live Visualizer, never false material sampling. Visualizers → Fullscreen Mode → Now Playing has independent **Media Bar Fill Opacity** and **Card Fill Opacity** adjustments (-1..+1, zero = the currently resolved Normal widget-card alpha); those controls affect fills only, leaving outline, separators, glyphs, text, artwork, shadow and timing unchanged. Ordinary Media still uses its own independent material and opacity Style Overrides, including the volume-track-inspired treatment. Validate both fullscreen card on/off, bar/floating, bright/dark and fast-changing Visualizers, Custom positioning, mixed DPI, reset/reload, transitions and original OSD priority; no extra shader/capture or new Media controller.
  - [ ] **Context Menu retains its own evidence-based decision:** true composited-underlay material only if the preceding Context Menu gate proves correct pixels and its GPU/input budget; otherwise theme-semantic Normal RGBA transparency is the reliable fallback. It must not depend on Visualizer preset metadata, palette sampling, or Now Playing's local opacity adjustments. Keep the menu/submenu performance and appearance gates above unchanged.
  - [ ] **Seekbar track and progress-fill surface investigation (do not dismiss):** inspect the ordinary Media seekbar and fullscreen Now Playing seekbar separately for their semantic RGBA fill, alpha/composition and existing material-source availability. Compare a subtle inherited material where the true underlay is available with semantic Normal translucency where it is not; preserve separate track/fill roles, progress legibility, scrubbing hit targets and controls. Decide by screenshots and GPU timing rather than dismissing thin geometry or requiring a new blur pass.

- [ ] Each step: `.qsb` regenerated, the SURFACE block kept identical across its three shader files, one focused
  GPU before/after, lead pixel review on the operator's two wallpapers.

- [ ] **M4 Unified Appearance Theme (operator, 16 and 23 Nov):** independent current-product QoL, after 1B.8 M3 / 1.7b material-border rendering and its proof; also precedes any eventual SMP M0. Consolidate the separately selected Settings and Widget themes into ONE typed, versioned Appearance Theme, one chosen ID and one global selector. Keep separate actual native Settings-HWND and Qt Quick rendering projections. Current linked pairs and mirror generation are transitional, not the desired permanent architecture.
  - [ ] Shared semantic roles with independently authored Settings / Widget / optional SMP scopes: surface colour/material, **surface transparency bias** (neutral 0), border-surface colour/material, **border transparency bias** (neutral 0), **border thickness** and **four-corner curvature** (correct concentric inner edge), plus typography/contrast. The skinning system does not own these global renderers. Neutral user Style Overrides inherit the authored theme value; nonzero user biases are relative adjustments applied once.
  - [ ] Retire roles left unused by the 22 Nov tile unification (System Stats' `metric_surface_color` and its theme role;
    tiles now take `tile_wash`) when the themes are regenerated here.
  - [ ] **Semantic completeness audit alongside unification (operator, 18 Nov):** inventory presently hardcoded colours, alpha, tint and *reasonably independent* material surfaces across Settings, ordinary widgets and fullscreen overlays; give missing eligible elements typed roles **where the element genuinely has an authored surface/ink purpose**, especially the Media Control Bar (distinct from the Media card), volume child, branded headers, seekbar track/fill and overlay controls. Seed every new role with the **effective visual value the element renders today**, including existing style overrides, so the default unified theme is visually unchanged unless the operator explicitly requests a change. Preserve fullscreen Now Playing’s two fill-opacity biases as neutral-zero adjustments on the resolved Normal semantic alpha, not new standalone colour authority or preset metadata. Preserve shared renderer/semantic ownership and per-element inheritance/Normal overrides; avoid indiscriminate material passes for decorative lines, tiny fills or already-correct surfaces. Prove baseline parity with before/after pixels before re-authoring aesthetics.
  - [ ] **Media application-volume child border thickness becomes semantic at M4 (operator, 19 Nov):** introduce an authored, typed `media.volume.outline.width` thickness role shared by both the vertical track and its filled-level outline, and use the current **2.5 logical px** as the unified-theme baseline. The Widgets → Media → Volume Control **Outline Width** setting, added before M4, must then become an explicit override of that role; an untouched/default value must inherit the theme instead of freezing all users at 2.5 px. Preserve non-default user-authored widths across migration, including zero (intentional no outline). Keep the material-border 20% alpha adjustment and the single-stroke clipping behavior independent of thickness. Confirm round-trip, theme switch/reset, DPI scaling, both alignment sides, Normal/material states and no new renderer or capture.
  - [ ] **Hierarchical sub-semantics (operator, 20 Nov), if architecture and cost allow.** Each role (for example
    border: colour, thickness, surface) has an overarching semantic, and each element (a widget's border, the volume
    child's outline) may carry an optional sub-semantic that takes authority for that element when provided.
    - [ ] Design check first: resolve the hierarchy once, at theme load and on change, into flat per-element values,
      so drawing reads one value with no per-frame lookup chain. Record the cost (zero recurring work) and the
      precedence: element sub-semantic, then role semantic, then theme default, then user Style Override where exposed.
    - [ ] Defaults: no sub-semantic is authored where today's look comes from the role. Where an element differs today,
      its sub-semantic reproduces that, so the regenerated themes render as now (pixel comparison per theme).
  - [ ] **Theme-authored legibility guard per eligible surface:** evaluate a typed semantic on/off (and inheritance precedence) for the guard/legibility panel, resolving theme default -> user Style Override if that component exposes one -> material child, with no duplicate shader or capture. Defaults mirror **current effective per-component states**: the ordinary Media card keeps its guard; the volume child and Media Control Bar do not have theirs restored by accident. Do not apply a global switch that disables guards on unrelated cards or sacrifices necessary contrast; prove light/dark/bright-scene ink accessibility and independently configurable card/child guards.
  - [ ] Regenerate curated themes semantically into the new format; preserving old bundled .srtheme/.srwtheme pairs byte-for-byte is not required. Retire the duplicate catalogues/mirror sync after accepted projection. Convert user-authored themes and Custom values in a bounded one-time importer where possible; otherwise back up the originals and report a safe fallback. No silent deletion of personal files.
  - [ ] Prove dark/light/material themes, Settings, Context Menu, Media and ordinary widgets; neutral and non-neutral surface/border bias, border width/curves, flat/material fallback, DPR 100/125/150/200%, real bright/dark backgrounds, hot selection, legibility and no extra underlay capture. The M3 material-border pass and native corner constraints remain independent renderer contracts. See SMP document 05.
- [ ] **Theme Studio (operator, 21 and 23 Nov; supersedes "Studio only at SMP M10"):** independent current-product
  theme authoring, after the native core work, the flip (NF), its follow-ups and M4; do not bring forward SMP M0. One visual editor for the
  unified Appearance Theme at the quality of the Visualizer Studios: live rendered previews of real Settings, ordinary
  widgets, Media, the Context Menu and fullscreen overlays on light and dark backdrops at real DPR; edits of every
  semantic role and sub-semantic (colours, materials, face and border transparency bias, border thickness, curvature,
  typography, legibility guard) with an inheritance inspector, one-click revert, undo and redo, Save and Cancel, and
  export and import through the production theme loader. It renders through the production theme renderer (no second
  renderer, no per-frame theme parsing) and edits appearance only. SMP M10 later adds skin authoring and the SMP
  Full/Compact previews to this same Studio. Design: `Docs/Future_Work/ShittyMusicPlayer/05_Theme_Skin_Studio.md` §5.

- [ ] **L0-L7 Transactional Live Settings across ALL profiles (operator, 23 Nov; after M4 and Theme Studio,
  within the substantial post-Concrete-Rain QoL phase):** move from unconditional Settings-open display teardown
  to **unchanged runtime on open/close**, canonical SettingsManager-driven scoped live updates, correct
  capability-local retirement when enabling/disabling whole widget/Visualizer/provider features, and
  bounded re-admission. This is an **approved implementation task**, NOT already implemented and NOT
  a native-core/Studio/NF/Melt-Pool/Concrete-Rain gate. **One complete technical plan:**
  `Docs/Future_Work/Live_Settings_Transactional_Runtime_2026-11-23.md` (phases L0-L7,
  owner map, impact classification, security, test fixtures, proof and failed alternatives).
  - [ ] **Preserve all ownership/resource guarantees or improve them.** No R-49 hide-only half-stop,
    zombie QObject/GL/QRhi resource, unmanaged callback, leak, duplicate Visualizer/beat engine,
    orphaned provider/capture/COM subscriber, duplicated GUI owner, hidden timer or new Settings render
    engine. Keep strict lifecycle barriers, exact generation+manager identity, lazy capability admission,
    zero-work dormancy and documented close/release order. A disabled capability RETIRES; a temporary
    pause PARKS, with independently composing park reasons and fresh-frame/clock re-entry.
  - [ ] **Least-disruption hierarchy (hard contract):** (1) no interruption for read-only Settings and
    safe in-place edits; (2) stage and atomically apply a minimal affected-owner transaction with
    targeted release/re-admission; (3) only when an otherwise safe substantial visual change would
    jump, the existing compositor fades **OUT -> commits behind the fade -> validates the new
    authoritative frame -> fades IN** over the smallest affected region; (4) **last resort**
    complete engine-owned teardown/rebuild only for proven structural incompatibility, device/context
    failure or irrecoverable owner state, never as a shortcut. Process-global/backend changes may
    instead require an explicit application restart. No arbitrary "all Settings changes rebuild" rule.
  - [ ] **Profiles/desktop:** Screensaver RUN/CONFIG, Dashboard, Diagnostic and eventual SMP consume the
    SAME architecture, with their real input/security and source/visualizer policies. Windows
    **Winlogon/secure/unknown desktop retains EXACTLY the existing proved saver
    Settings request, exit and handoff behaviour**: do not invent either an
    automatic live Settings window or a blanket ban on a historically valid
    Settings action. No extra HWND, Studio/shield, browser/OAuth, new input
    capture or lock/login focus manipulation. Treat account/credential actions
    as fail-closed on noninteractive/unknown desktops; desktop identity and
    Settings-request authority are separate axes and need real Windows proof.
    Existing Screensaver and Dashboard runtime behaviour remains as-is until its specific gate passes.
  - [ ] **Settings conceal/restore for BOTH Studios (mandatory, not optional polish):**
    keep the existing QWidget Settings alive in the same SettingsSession but
    **visible only until the Studio presents its FIRST authoritative frame**;
    then fully CONCEAL Settings for the complete Visualizer Studio or
    Theme Studio session, with no interactive Settings controls, popups,
    taskbar minimization, duplicate Settings window or focus rivalry.
    Restore the SAME Settings QWidget afterward, preserving page/pill,
    scroll, selected mode/preset, Custom, undo and Settings session.
    Keep the proven beneath-Studio, non-activating reveal and Win32
    expose/WM_PAINT workaround; activate Settings only after the Studio
    disappears. No Settings flash between consecutive Studios/mode switch;
    handle early presentation failure, scene loss, close, Esc, Alt+F4,
    Save/Cancel, application shutdown and invalid wrappers. Replace the
    `QDialog.exec()`-dependent lifecycle with an explicitly owned async
    session; **nonmodal does NOT mean leaving Settings visible next to
    Studio**. The session owns real Preview/Apply/Cancel, not a fake
    rollback via the 30-step SettingsUndo. No QML Settings rewrite.
  - [ ] **Proof/acceptance:** impact-map every existing settings key/side effect; no-change identity
    preservation, repeated Settings+Edit+Studio+source/mode/capability/monitor cycles, healthy
    graphics backend and first visible frame, performance p50/p90/p99, CPU/GPU/VRAM, native heap,
    Python/QObject/QML wrappers, subscriptions/timers/threads/COM, same-profile no-run controls,
    correct remote/mixed-DPI and secure-desktop negative controls. Existing failure probes R-49,
    R-53/56/59, R-175, R-22/U-09 and R-80 are essential. Use **synthetic test-owned settings**;
    never test against mutable operator-authored presets. **AUTOMATED GATES FIRST:**
    implement the detailed document's A1-A8 executable tests, covering
    no-change identity, real Studio conceal/restore/first-paint/focus order,
    precise resource retirement, dormancy, no leaks, first-authoritative
    frames, minimal fade and profile/desktop negative controls. Publish
    machine-readable evidence; a mock or screenshot without a real GUI
    execution is not a pass. **No routine operator checks or sign-offs**
    for measurable behaviour. Reserve human judgement for inherently
    subjective visuals or physical protected-desktop interactions that
    cannot safely be automated; leave that route unchanged if unproven
    while independently green interactive profiles proceed. Existing
    permission for agent-started heavy game load remains binding.
    Do not delete existing R-175 memory-attribution work just because
    unnecessary teardown is later reduced.
  - [ ] **SMP handoff stays deferred:** when SMP is separately admitted its M8 adds player-specific
    output-device, decoder/queue/library/SMTC live-setting transactions on this shared base;
    SMP playback/Media survive Settings and its Visualizer parks/resumes to zero active work.
    This common QoL milestone does not start SMP or remove its existing M8 proofs.

### 1B.9 Settings and Studio window corners bleed (continues 1.9)

- [ ] Studio's outer corners to match the visible Settings improvement: UI-1 of `Docs/Future_Work/Studio_Corners_Card_Rim_and_Visualizer_Rotate_2026-11-09.md` (its live checklist;
  UI-2 landed in 7cbc1d5b). Do it with this section's corner work, as one owner.

Measurements, rejected alternatives and the residue no layered window can remove:
`Docs/Architecture/Settings_Theme_Architecture.md` (native corners).

- [ ] Side defect: the Studio window shows only blur (no title bar or content) in native captures by
  `tools/settings_native_corners.py --window studio`; find whether it is the capture setup or the Studio.
- [ ] Side defect (red on main before this work): `tests/test_waveform_studio_theme.py::
  test_every_theme_yields_readable_studio_chrome[Matte Graphite [Single]]`, accent-text contrast 2.12 against 4.5.
- [ ] `tools/settings_native_corners.py --qt-scale-factor` sets Qt's `QT_SCALE_FACTOR` inside the tool process to
  emulate 100% and 200%: decide whether that tool-only use stands under the no-environment-variables rule.
- [ ] Window border material: the border ring takes 1.7b's border-material treatment (one rule for cards and
  windows), inside the +2 px budget (unused: the border stays 4 px).

### 1B.10 Presets (Opus Medium, low priority, when nothing more significant waits; the lead judges the pixels)

Every preset must read as unique and visually impressive; the agent may ask the lead for a feature or
architecture a better look needs, if it is not wasteful. Order: Spectrum, then Extruded Bubble, then Neon Lake;
the agent reports after each mode for the lead's pixel review. Presets are authored, mutable and exchangeable:
this item describes looks, and nothing here or anywhere names, counts or pins them.

The operator's taste for Spectrum (11 Nov, on five of round 1: "are all ghastly ugly"): wide glossy, chrome,
capsule, grid-on-block and dark-fill looks fail; fine luminous gradients pass; fewer good presets beat a full slot
count. The Spectrum features and the Bar Gap control are in `Docs/Reference/Visualizer_Reference.md`.

Every 3D look (operator, 14 Nov): never a near-lens blob (a defocused shell or bubble in front of the camera);
the lead rejects any still or showcase frame that shows one.

- [ ] Defect: growing a painted Neon Lake grid shifts the picture 0.055-0.11 of a level on average (allowance
  0.02); `tests/test_neon_terrain_growth.py` holds it as an expected failure. Cause not found (tile alignment,
  edge clipping and mound position ruled out). Root-cause it, with the far-land Water trench below if related.
- [ ] Defect: a river painted with the Water brush in Neon Lake's far land draws as a straight-walled trench, not
  along its path (reproduction: `render_neon_evidence.py stills --preset 1 --look
  .artifacts/evidence/visualizers/shockwave_grid/presets/20261114_round1/side_defect_far_water_trench/look_river.json`).
- [ ] Side defect: Rim Glow measures distance to the square edge (`spectrum.frag:783-785`), so it facets at
  rounded tops.

### 1B.10a Extruded Bubble stream and particle response (after the native port)

- [ ] **Investigate the remaining weak speed swing after N5.6** (operator, 23 Nov). Isolate the visible
  population first. Compare the global stream and shell transport with bead chains, wake fizz, snow
  and ambient specks on the same recorded passage. Measure each active layer's velocity through quiet and
  loud input against its own transport owner, then repair the layer that misses the intended swing.
  - [Log bundle](logs/evidence_chest/logs8acd9d88e9.zip) records the 22:46 Studio edits and preset save.
    Its Studio and timing logs establish the control path. The visible layer and achieved velocity remain
    unmeasured. [R-251](Docs/Historical_Bugs/R-251_Extruded_Bubble_Stream_Speed_Range_Was_Attenuated.md) covers
    the narrower global-stream endpoint repair.
- [ ] **Finish the Studio motion controls after N5.6.**
  - [ ] Replace Studio's separate Stream Speed (Quiet) and Stream Speed (Peak) controls with one range
    slider on the existing range setting. Keep authored values, with no endpoint pinning.
  - [ ] Add the Motion section for Stream Speed, Drift and, if it belongs there, Path through the
    existing settings spec owner.
  - [ ] Add separate Particle Reactivity and Microbubble Reactivity range sliders to Motion, with
    quiet-to-loud endpoints for each layer. Bind them to the existing settings spec and each
    layer's transport owner. These controls are a separate post-port deliverable from the
    speed-swing investigation.
- [~] Themed list scrollbars merged 21 Nov (the product drew the platform's bar too); a real Windows 11 hover in
  1B.14's Settings and Studio box (every Settings tab's scroll area now takes the same owner). The Studio's QML bars
  are 1B.14's.

### 1B.12 Fullscreen glyphs relative to the Visualizer's display (contract: plan 01 M3c)

- [ ] A display arrangement changing while the saver runs is covered only by re-admission in tests; check it on
  the topology-replacement path.
- [ ] The Reset Camera glyph (a font character) shows coloured edge fringes in off-screen crops; confirm on a
  real display and paint it as a path like the arrows if it does there too.

### 1B.13 Hold right-click to pan the live Visualizer (contract: Spec.md / Contracts.md input)

- [~] Native pointer capture on a real foreground window (tests use a stand-in capture): 1B.14's held-right pan
  box.

### 1B.14 Lead verification runs (operator, 11 Nov: "why can you not make tests that exercise these?")

Tools: `--only-display <index>` (RUN only, fails closed) and `tools/d1_run.py` (the real saver on one display,
bounded, frames read back from the saver's own window and from the desktop, crops, logs; refuses the primary
display; `--help` holds the recipes); both in `Docs/Reference/Harness_Index.md`. Permissions (operator, 11 Nov):
bounded runs on Display 1 are the lead's; Display 0 is rare (the lead only, through `--allow-primary`, never in a test, recipe or automated run; agents never take it); builds run only through GitHub's workflows.
Agents build harnesses and prove them hidden; each visible run is short, bounded, fails closed and tears down.
Every `[~]` box in this plan that says "D1 run", "Studio run on D1" or "Frozen run" is run in these sessions.

- [~] Cursor after exit (R-183) on D1 with `tools/cursor_exit_observer.py`: key, click, mouse-move, link click
  (browser launch stubbed), Settings and Dashboard exits, the pointer placed over the saver on D1 for the
  run and put back after; a verdict per path. Then R-183 is accepted, or the failing path is fixed at the
  retire owner and re-run.
- [~] Held-right pan on D1: real pointer capture on a foreground window (press, drag, release; a click still
  opens the menu on release; focus loss mid-pan releases the capture).
- [~] Expanded Visualizer on D1: expand, collapse, the fullscreen arrows offered for the real arrangement, the
  move toward D1 from a hidden D0-side owner where that can be driven without showing anything on D0; frames
  grabbed and reviewed by the lead. What truly needs both displays visible is listed in the report, not assumed.
- [~] Settings and Studio windows on D1: corner drag and resize from each corner by messages (the alpha-1 corner
  pixels keep input); the Studio's corners captured natively; the scrollbars of the theme list, the theme
  filter's popup, the Sources list and autocomplete captured (theme them through `shared_styles` if they are
  native bars there; 1B.11, 1C.9).
- [ ] Frozen build: `tools/github_remote_build.py` on the pushed commit (the lead's standing permission).
  - [ ] From the artifact: the engine worker's import closure is QtCore only and the image worker's Qt
    dependencies are the expected ones (the oracle of `tests/test_visualizer_engine_import_weight.py`, run
    against the frozen manifest); icons unchanged.
  - [ ] The frozen product on D1 with diagnostic flags: worker memory flat across a Settings round trip; the
    first Neon Lake activation logs a cold link or a cache hit and never an activation-failure reload; the
    second run a cache hit.
  - [ ] In the same frozen run: saves work, and a Studio opens (the 6 Nov "QtQuick.Controls.Basic is not
    installed" fix; contract `Spec.md`, frozen QML package contract;
    `test_every_shipped_qml_import_survives_the_frozen_prune`).
- [ ] Real audio endpoints: a test that opens real WASAPI loopback in the engine worker and drives the product's
  own device-change path with real endpoint ids; it skips cleanly with a stated reason where the machine has no
  second endpoint.
  - [ ] Two or more active render endpoints: a default-device change to the other endpoint (the notification
    delivered with its real id; no system setting changed) and capture resuming on it.
  - [ ] One endpoint: invalidate and reopen on the same endpoint.
  - [ ] Endpoint removal by its notification.
  - [ ] The in-process path too.
- [ ] First reveal, worker against in process, without load on D1: the time from activation to the first drawn
  frame for each mode on both paths.
- [ ] `tools/d1_run.py` hands `screen.grabWindow(0)`, a `QPixmap`, to its writer thread (`_write_frame`; 12 Nov night
  audit, low 1). It works only because Windows' platform reports threaded pixmaps: convert with `.toImage()` on the
  GUI thread (one frame's copy) so the tool does not depend on it.
- [~] Carried from section 1A's former "Awaiting Validation" list, in the D1 sessions: the changed glyphs as
  zoomed crops; camera and child placement round trips; long fullscreen metadata and controls; material
  comparisons on native pixels.

### 1B.16 Tooling (Docs/Reference/Tooling.md, merged 12 Nov)

- [ ] Candidates to retire (Tooling.md's table; the operator keeps useful tools, so the lead judges each and deletes
  only what is dead and superseded, recording the reason): high confidence `verify_compile.py` (repo root) and
  `.github/tools/linux_smoke_dist.py` (a stale copy no workflow runs); the medium and low rows stay unless a caller
  check proves them dead.
- [ ] Workflow supply chain (12 Nov evening audit, low): `.github/workflows/native-module.yml` pins its actions by major
  tag (`actions/checkout@v4`, `setup-python@v5`, `cache@v4`, `upload-artifact@v4`); pin each by commit SHA with the tag
  in a comment. `tools/native_sdk_fetch.py` says Vulkan-Headers 1.4.341 is "the release it is built with" for Qt 6.12
  with no source: cite Qt's own build record, or say it is the loader's version on this machine.

### 1B.15 Housekeeping the lead decided (11 Nov; engineering choices, not operator decisions)

- [ ] Extruded Bubble evidence of 20 Oct: the references now point to
  `.artifacts/evidence/visualizers/extruded_bubble/20261020/` (`RELOCATED` in `tools/artifact_migration.py`),
  but neither that folder nor the old `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/` exists on disk any
  more: the media `Investigation.md` cites is gone. Say so in `Investigation.md` (one line under its evidence
  list) so nobody hunts for it; the 22 and 23 Oct folders are still referenced and still ignored by git.

## 1C. Operator's diagnostic run (11 Nov, evening; ahead of everything in 1B that is not already in flight)

The operator ran the product themselves and reported five defects ("do not rely on me for future runs"). Rule
for this section and from now on (operator, 11 Nov): the plan holds every task in detail before it is dispatched;
an agent's brief is its plan item, and its report is checked against the boxes, never taken on trust or kept only
in the lead's memory. Each item below starts with a root-cause box: the cause is established on the real product
path (an off-screen reproduction or a Display 1 run), with a negative control, before anything is changed.

### 1C.2 Display moves retarget the live Visualizer (R-194)

Operator: "we do not want teardowns and rebuilds unless absolutely needed. They are a last resort." A display move
attaches the session to both scenes and commits in place (decision: plan 01 M3c; rule:
`Docs/Guardrails/Presentation_Change_Preflight.md`, "Retarget before rebuild"). Teardown remains only for a display
arrangement change, a display added or removed, the owning display lost, Settings, and corrupted-object recovery.

- [ ] The 1.5 s preparation bound on a cold shader cache (34 units land at 1.22-1.28 s warm, close to the bound).
- [ ] PyOpenGL's `GL_TIMEOUT_IGNORED` has the wrong value (`glWaitSync` rejects it): the move uses the GL spec's
  value; record it where GL constants are shared so nothing else takes PyOpenGL's.

### 1C.3 Fullscreen Now Playing: one Edit contract with the Media widget (R-189)

Contract: plan 01 M3c; evidence `.artifacts/evidence/visualizers/shared/expanded_now_playing/20261112_1c3_after/`.

- [ ] Side defect (watch): `tests/test_visualizers_fullscreen_mode_pill.py` crashed once with an access violation
  when run after overlay_settings, fullscreen_edit and overlays in one process (not reproduced with two files).

### 1C.4 Spline Curve's white lines show about one pixel into the card border (R-191, R-192)

- [ ] The tests that open windows were not run on the merge (`test_qtquick_visualizer_clip_smoke.py`, Neon Lake's
  `actual_neon_qsg_pixels`): run them hidden at the next milestone run.

### 1C.5 Volume child control: its drop shadow was cut off sharply (R-187)

- [ ] The agent could not reproduce the cut at the operator's stored Media layout (no volume edits in their
  settings): a D1 run with a copy of the operator's profile (1B.14), a 4x crop of the volume bar, lead review.

### 1C.8 Neon Lake: the water's edge and face lines can be hidden completely

Contract and evidence: `Docs/Reference/Neon_Lake_Basin.md` "Water Lines".

- [ ] The showcase WebP at Water Lines 0 was lost when its worktree was retired (the retire step copied only evidence;
  it now copies WebPs too): re-render it with `tools/release_media.py` (Preset 3 at 0 on the heavy recording) and
  review it.

### 1C.10 Neon Lake round 3 (operator, 11 Nov evening; one Opus High agent when a slot is free, in this order)

One agent, one mode (`shockwave_grid`), four features and two repairs, each its own reviewed checkpoint. Every
new control is a canonical spec entry in `core/settings/visualizer_mode_settings.py`, off or neutral by default,
authored neutral into every Neon Lake preset by the repair fill, shown in Settings and the Studio through the
spec, identical pixels and zero cost when off (a skipped branch, not a multiply by zero), Settings/Studio and
engine-worker parity rerun, `Docs/Reference/Neon_Lake_Basin.md` and the Visualizer Reference updated. Everything
ramps and fades; nothing pins at its ceiling on loud music and nothing mutes mid-song kicks in continuous play
(judge on whole songs with `tools/visualizer_replay/neon_lake_music_response.py --continuous`).

**a. Repairs first (they change what the rest is measured against)**

- [ ] 1B.5's dormancy fault: an ungrown grid with React To Music off pays for the terrain-overlay path; skip it
  (identical pixels, the pre-1B.5 cost), re-measured alternated in one session; the five unattributed GL calls.
- [ ] 1B.6's paused Studio preview: a paused seek shows the reaction the fixture has at that time.

**b. Water lines can be hidden: plan 1C.8, as written there.**

**c. Spire glow on hits (operator: "spires should glow an editible colour on hits. Completely optional in the
Studio. If you want a test colour just pick one of the dominant colours.")**

- [ ] The hit part of the Growth drive exposed on its own (today it is mixed into the drive): a frame-field
  value and one uniform, memoryless on the fixed scale like the other drives; nothing per frame when off.
- [ ] Growth's share of a vertex's height passed to the fragment shader; emission added into the bloom target
  in proportion to that share and the hit value, so only what grew glows, tallest most; mounds glow less than
  spires by the same rule (Growth Shape decides), no separate switch.
- [ ] Two spec controls in the Studio's Reaction workspace beside Growth: "Spire Glow" (amount, 0 = off and
  identical to today) and "Spire Glow Colour" (an editable colour). No test colour is shipped in presets: the
  presets are authored at 0; for evidence use each preset's dominant accent (Preset 1 its magenta ridge colour,
  Preset 3 its gold).
- [ ] The glow rises with the hit and decays over a few hundred milliseconds (a ramp, never a flash that
  strobes); on sustained loud passages it settles below its ceiling so the next hit still reads.
- [ ] Evidence: a staged sheet (hit value 0, 0.5, 1 on Presets 1 and 3), one driven WebP on `heavy1`, the
  music-response trace with the glow term beside the song's envelope; lead pixel review.

**d. Vertex trace (operator: "would a vertex trace reaction also be viable? When on and a colour is chosen
vertexes react to music by changing colour to the chosen colour and you could select 'Random', 'Left to Right',
'Back To Front', 'Front To Back' and 'Center Out' as their starting points. Their speed and colour deepness
effected by intensity, making sure not to pin.")** Viable and cheap: the land's vertex points are already drawn
by a vertex shader that knows each point's position, and the mode already carries a small ring of travelling
wave fronts from the tick to the shader.

- [ ] Design note first (half a page in `Neon_Lake_Basin.md`, seen by the lead before code): each vertex gets an
  order key in 0..1 from its position by the chosen start: Left To Right (basin x), Back To Front and Front To
  Back (depth from the saved camera's forward axis, so it reads the same from the default view), Center Out
  (distance from the lake's centre), Random (a stable hash of the cell, so it never shimmers frame to frame). A
  trace is a front that travels along the key; a vertex's colour moves toward the chosen colour as the front
  passes and relaxes back behind it over a set tail length.
- [ ] Fronts are launched by the music in the tick (a hit above the passage's own level launches one), kept in
  a small fixed ring (as the wave ring is), advanced on the logical tick, sent as one uniform array; the vertex
  shader does a few operations per vertex per live front and nothing when the ring is empty.
- [ ] Intensity drives two things, both through soft knees so neither pins: the front's speed (faster on
  louder passages, bounded so a front is always seen to travel) and the colour's depth (how far a vertex moves
  toward the chosen colour; never fully replacing the land's own colour unless the control asks for it).
- [ ] Spec controls in the Reaction workspace: "Vertex Trace" (amount, 0 = off), "Trace Colour" (editable),
  "Trace Start" (Random, Left To Right, Back To Front, Front To Back, Center Out; Title Case as written here),
  "Trace Length" (the tail). Whether land vertices only or the water's vertices too: the agent renders both
  and the lead picks.
- [ ] It composes with Growth, Indents and Spire Glow without double-brightening (the trace recolours the
  vertex; glow adds emission; together they stay under the bloom ceiling on `heavy1`).
- [ ] Evidence: one WebP per Trace Start on Preset 1 with a test colour from its dominant accents, the
  music-response trace showing launches against the song, a continuous-play run over three songs (launch
  counts per third, no starvation after loud passages), cost per frame against the overhead baseline; lead
  pixel review.

**e. Islands (operator: "land can grow out of water but only in exceptional music circumstances"; optional,
last because it touches the water's edge)**

- [ ] The standing rule changes for this one feature only, and the docs say so: the authored shoreline never
  moves; islands are extra land that may rise inside the lake while the feature is on.
- [ ] "Exceptional" defined on the music's own scale and proved on whole songs: an island rises only when the
  passage level has stayed in the top few percent of the session's own recent loudness for some seconds *and*
  a strong hit lands; a cooldown follows; a quiet or even song raises none. Calibrate by presence on the
  recorded songs (0 on `quiet_intro` until its loud end; 1 to 3 across `heavy1`), never by absolute levels.
- [ ] A few fixed island sites per preset (seeded from the terrain record, in open water away from the shore and
  the celestial reflection path), each a smooth mound; an island rises over seconds and sinks over seconds
  (fade, never vanish), and never breaches the camera floor's clearance.
- [ ] The island gets a real water's edge without recomputing the precomputed bank distance: its shoreline
  distance is analytic (distance to the island's current waterline circle), and the shore glow, wet fringe,
  wave taper and reflections read the smaller of the bank distance and the island distance. With no island up
  the term is skipped and the frame is identical to today.
- [ ] The camera floor's ripple allowance and the water reaction account for an island that is up; Growth,
  Indents, Spire Glow and Vertex Trace treat island land as land.
- [ ] One spec control, "Islands" (off by default), with at most one more for how rare; in the Studio the
  Peak fixture can force one for authoring.
- [ ] Evidence: rise and sink WebP on Presets 1 and 3 with 4x crops of the island's waterline (glow and fringe
  wrap it, no hard ring), the whole-song launch table, GPU cost with an island up and with none, alternated in
  one session; lead pixel review. If the analytic edge cannot be made to look right, stop and report with the
  renders rather than shipping rocks without a shoreline.

### 1C.9 Sources: RSS Pools shows which pools are active and valid

Contract: `Docs/Architecture/Settings_Theme_Architecture.md` (the shared list style and the Sources pool rows).

- [ ] The marks seen with real stored health once (a D1 or frozen run of 1B.14 after a real fetch), lead review.
- [ ] Not rendered: a Mica theme; the onboarding lists keep their own style (decide whether they join the shared
  one when onboarding is next touched).
- [~] The Sources list's scrollbars (unthemed black native bars in off-screen renders; the Themes list too): 1B.14's
  Settings and Studio box.

## 1D. Operator requests (12 Nov, evening; after the current agents pass audit)

### 1D.13 Side defects found at its merge (15 Nov; Opus Medium when a slot is free of native work)

- [ ] Two tests fail only inside one long same-process pytest run (2,413 tests over 14 minutes), and pass alone:
  `tests/test_waveform_pulse_rim.py::test_pulse_rim_off_is_pixel_identical_to_the_light_pass_without_it` and
  `tests/test_qtquick_ordinary_widget_host.py::test_refresh_transition_clock_coalesces_arbitrary_simultaneous_consumers`.
  A third, `tests/test_qtquick_startup_reveal.py::test_startup_reveal_primes_zero_then_completes_at_one_once`,
  failed the same way in the 1D.12 merge run (4,407 tests over 33 minutes). Find the leaked state or ordering they depend on, and make each test own its preconditions.
  The N5.1 merge run (4,529 tests, 44 minutes, one process) added twelve more of this kind; they pass alone.
- [ ] Watch for recurrence of the Oscilloscope reflow clip-smoke red; retain captures and owner-resolved vertical
  geometry before judging the thresholded lit-row oracle. Protected QSG/clip implementation stays unchanged.
- [ ] Lead, Display 1: confirm R-221 in the product, Fullscreen Hide Borders with pixel shift stepping, and check
  whether the operator's lavender edge colour came from the shift.
- [ ] Checkpoint audit 1 M1 (15 Nov, 1D.12 C; open, found by the 20 Nov closed-report triage): a display move back to a
  display whose Visualizer shell already exists replays the 3D control hint. The transfer reuses the retained root
  (`scene_controller.py` `transfer_visualizer_to`, `_adopt_visualizer_transfer`), and neither the host binding's
  `transfer` nor `_transfer_quick_visualizer_unit` re-projects `controlHintShown`
  (`_configure_quick_visualizer_input_admission` runs at bind and mode edges only). Case: A's hint on D1, move to D2,
  switch to B, hover on D2 (B joins the set), move back: D1's retained root still reads B as not shown and plays it
  again. Fix at the transfer edge (the adopting scene projects the session set); test with two hidden production hosts
  and the real `transfer_visualizer_to` (the audit's probe printed "display 1 root reused = True controlHintShown =
  False"; it is no longer on disk), negative control today's code.
  - [ ] Its L2: `tests/test_visualizer_control_hint_once_per_mode.py::test_display_manager_hands_every_display_the_sessions_one_set`
    compiles `_configure_quick_visualizer_input_admission` out of `display_manager.py` and drives `SimpleNamespace`
    stubs; rebuild it on `tests/_display_manager_doubles.py`, and replace the `_admit()` stand-in for a display move
    (the test says a move rebuilds the root; it does not).

### 1D.10 Audit of 13 Nov: what is left after its merge (14 Nov)

- [ ] C++, with the next native build round: excuse `vulkan_context.cpp:205-207`'s two messages only when Qt6Gui
  is the caller; prune `surfaces.cpp`'s window registry (`:51-54`, `:295-305`). Then the lead runs host_check, which
  also proves the new `front_face_fixed_cw` control and the Qt-only cycle verdict on the GPU.
- [ ] `tools/build_runner.py` `_fit_initial_window`: on a work area shorter than the content, the
  fit clamps Tk's client height without counting the native frame, so the window's bottom passes the work area by
  about 25 px. This only affects short screens; the operator's 732 px stays. Count the frame in the clamp.
  `tests/test_build_foundry_window_layout.py -k keeps_the_whole_window` is a strict expected failure until then.
- [ ] Archive Foundry's close joins a read-only worker for up to 10 s on the GUI thread (audit low 5). Bound the join tighter,
  or detach the result safely.

### 1D.9 Linux credential encryption, port from the archived branch (Opus Medium, low priority; Linux is best effort)

- [ ] The Linux branch was deleted on 13 Nov and archived as tag `archive/linux-branch-2026-11-05`. Its one unported
  piece: Linux credentials through a per-user key in the Secret Service keyring (`core/secret_service_key.py`,
  the `core/windows/dpapi.py` rework, no plaintext fallback). Port it onto today's `dpapi.py` without changing
  Windows behaviour, with its tests and the `Linux_Plan.md` row updated.

### 1D.2 Fullscreen Visualizer display styles

- [ ] Watch R-192's enclosed axis. A monitor with no exterior edge on an axis whose extent is not whole at its
  DPR (the middle of three in a row; the centre of a 3 x 3 grid) keeps Qt Quick's stretch there, and Borders To
  Edge's frame shows it. `test_the_enclosed_axis_stretch_is_recorded_not_hidden` records it.

## 1A. Fullscreen, Rotate, material and corner items (1.0 to 1.9)

### 1.0 Rotate in ordinary and fullscreen Edit

- [~] Lead review of rendered frames (off-screen for ordinary Edit, D1 run of 1B.14 for fullscreen Edit): Rotate in
  every mode except Sphere, in ordinary and in fullscreen Edit.
- [~] Lead review of zoomed glyph crops: the rectangle/quarter-turn glyph against Reset Camera.

### 1.0b Studio Rotate control

Preview orientation is per-open state, separate from camera/artwork and desktop CUSTOM orientation; Copy Frame
captures it.

- [~] Studio run (D1, 1B.14 harness), lead review of grabbed frames: Studio's Rotate control in every mode except
  Sphere.
- [~] Same run: upright handle labels.
- [~] Same run, drags posted by messages: rotated brush/drag feel (the drag lands where the pointer is).

### 1.1 Mode switch with no direct cause (Awaiting Logs)

- [ ] No direct mode-switch cause in the supplied archive. On recurrence, correlate the reported time, prior/result
  mode, selected preset and runtime generation with the existing mode-transition owner and frame trace.
- [ ] Distinguish explicit selection, enabled-mode normalization and Settings restoration first.

### 1.4-1.5 Remaining fullscreen visual acceptance

- [~] Fullscreen run on D1 (1B.14 harness), lead review of grabbed frames: Media Bar and Floating Glyphs styles.
- [~] Same run: long metadata fitting.
- [~] Same run: multiline Edit boxes and optional album, including Save/Cancel.

### 1.6 Achievement Pulse child placement

- [~] D1 run (1B.14 harness) with `--geo`: check child placement after Settings/fullscreen return (replaying the
  saved payload on Edit entry must not change the canvas; disabled provider fields must not count as painted capsule
  rows).

### 1.7a Studio legibility follow-up

- [ ] Resolve the intended density once (the panel guard raises broad light surfaces nearly opaque to carry
  accent/focus marks).
- [ ] Minimally correct runtime semantic ink against its actual composed locations; retain authored/scene colours.
- [ ] Prove controls/traces on final off-screen wallpaper renders.

### 1.7 Material density (separate reversible slice)

Contracts and evidence: `Docs/Architecture/Card_Surface_Materials.md`,
`Docs/Architecture/Settings_Theme_Architecture.md`, `Docs/Reference/Visualizer_Studio.md`. Final native checks use both
operator wallpapers under `C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET`; Studio renders have no DWM proof.

- [~] Lead review of side-by-side renders (the supplied widget material screenshots beside current cards, both
  operator wallpapers): especially the good Glass/Frosted volume surfaces, Glass inset/distortion, and Studio
  panels/tabs/headers/wells.
- [~] D1 run (1B.14 harness), lead review of grabbed frames: exercise Settings Opacity Adjust and Widget Opacity
  Adjust in Style Overrides (-1..1, neutral 0).
- [~] Studio run on D1 (1B.14 harness): live Studio material switching, snap and resize, driven by messages.
- [ ] The remaining unsampled control/delegate inks.

### 1.7b Material-aware widget border (near-term, independent material slice; 10 Nov)

**Source implementation candidate (19 Nov, awaiting compiled shader and operator validation):**
The shared `OverlayCard`/`MaterialSurface` path now carries one separate material ring, a global
Border Surface choice (Normal / Theme / Acrylic / Glass / Frosted / Mica / Smoked), and an
independent Border Opacity slider (neutral 0). The ring uses the existing display backdrop,
adds no QML layer/extra capture, and never applies a border legibility panel. Do not mark the
feature complete on source checks alone: the committed `.qsb` is not regenerated by this
handoff and must be rebuilt with the pinned Windows Qt toolchain before runtime testing.
The following unchecked items are **mandatory acceptance gates**, not deleted work.

Contract: `Docs/Architecture/Card_Surface_Materials.md` §3.2.1.

- [ ] Extend the existing shared card `MaterialSurface` shader's rounded SDF to shade the **border ring** using the
  same display-local blurred backdrop already sampled by the fill; never create a second capture/blur, extra
  material pass, timer or per-frame Python owner.
- [ ] A material-enabled card inherits its surface material for the border **by default**. In
  `Widgets -> General -> Style Overrides` add **Border Material:** Inherit Surface (default) / Flat / Acrylic /
  Glass / Frosted / Mica / Smoked (explicit overrides). An explicit different border material still samples the same
  shared backdrop and draws through the same card shader (ring-local parameters only; no independent material item).
- [ ] Add **Border Opacity Adjust** (-1..+1, persisted neutral 0), following the existing
  `core/settings/surface_opacity.py` adjustment semantics and save/flush path. Zero is exactly the authored
  material/theme baseline, not an always-on override; nonzero adjusts border density independently of `Widget
  Opacity Adjust` and the existing family border-opacity controls.
- [ ] **No fixed minimum border-width rule (operator, 19 Nov):** admit material borders at every positive authored
  visible stroke width, including 1–2 logical px. Use proper continuous rounded-SDF coverage and device-pixel AA,
  not a 3 px eligibility gate that silently switches thin borders to Flat. At subpixel physical widths preserve
  sensible coverage and shape without inventing a thicker border. Verify 1/1.5/2/3/5 px at 100/125/150/200% DPR,
  with normal/material switching and all corner radii; let measured appearance decide future tuning.
- [ ] Retain the authored theme border colour/contrast as the ring's tint/edge authority and border width/radius as
  its geometric authority.
- [ ] On Normal or Flat, retain today's Rectangle border **pixel-identically**; on active material, remove overdraw
  by that Rectangle only for the ring.
- [ ] Must remain clear against the fill, including on Glass and bright wallpapers; validate stroke AA, translucent
  corners, 100/150/200% DPR, normal/material switching, card opacity/theme inheritance and Style Overrides reset.
- [ ] **Measure incremental material-border overhead, not accepted card-material cost (operator, 19 Nov):** take a
  comparable GPU/CPU/frame-time baseline with the *existing, accepted card materials* active, then enable the border
  ring alone. Compare one, several, and densely populated simultaneously visible ordinary widgets, plus existing
  material children/headers, over static wallpaper and during wallpaper transitions; include glass/acrylic/frosted/
  mica/smoked, normal/flat fallbacks, varied border widths and mixed DPR. Record GPU pass/sample counts where available,
  per-frame GPU cost, frame p90/p99, 90 Hz cadence impact, scene-graph item/node counts, memory changes and idle/dormant
  behaviour. The extra border must be in the SAME material shader/sampler invocation with no duplicate backdrop blur,
  capture, full-scene pass or per-border worker. Reject or optimise only a measured regression; do not re-open the
  already accepted card-material rendering or divert the native core work for cosmetic materials.
- [ ] Include the framed and expanded Visualizer frame using its own authored width, radius and colour, not the
  ordinary `OverlayCard` geometry. **Separate foreground path awaiting measurement (19 Nov):** the live Visualizer
  paints above its existing card-face shader, so the border-only material shader has to paint above those pixels;
  it cannot share the ordinary card's single face/border quad without covering the live content. Check 4K/90 Hz
  GPU/CPU frame-time impact of this *extra border-only draw*, static backdrop sampling, 1–2 px strokes and
  Native/Vulkan/OpenGL parity. Normal/zero-width/missing-backdrop must not instantiate a border shader, and no
  extra backdrop capture or work per frame beyond the existing conditional draw is permitted. If its measured cost
  is unacceptable, optimise/defer that Visualizer-specific material path, never the already accepted card surfaces.
  Material children/Context Menu keep their independent border semantics.
- [ ] **One-time cumulative material/UI/Steam audit (19 Nov):** use `Docs/Temporary_Material_Surface_Audit_2026-11-19.md` to audit the full handoff, run its focused and Qt/performance tests, fix confirmed issues in their existing owners, record outcomes, then delete the temporary document and remove this checklist line. Do not advance native-core scope for the audit.
- [ ] Preserve older themes and settings via neutral defaults.
- [ ] **Shader bake and binary admission (BLOCKING):** use the project's pinned `PySide6` toolchain to regenerate
  `surface_material.frag.qsb` from its changed GLSL source for the full shipped QRhi target matrix, and run
  `tools/regen_qrc.py --shaders --check`; test the generated pack on Windows Vulkan and OpenGL before shipping.
  Source-only shader changes paired with stale compiled `.qsb` files must not be treated as a working material-border release.
- [ ] **Disabled/compatibility proof:** Normal border and zero-width border must keep pixel-identical legacy
  outlines on both Normal and material card fills. Test Theme inheritance, explicit override while the parent
  card is Normal, older saved settings, switch on/off, opacity reset, backdrop first-frame fallback, missing
  backdrop and hot-switch failure modes; verify no leaks/scene-graph churn after multiple Settings edits.
- [ ] **Shader and visual proof:** confirm ring/face order and rounded-corner coverage at 1, 1.5, 2, 3 and 5 px
  across DPR 100/125/150/200%, Glass/Acrylic/Frosted/Mica/Smoked, light/dark themes, bright/dark wallpapers,
  shared-backdrop updates and transitions, multiple displays and scale-aware CUSTOM layouts. Confirm the border
  never inherits the card's legibility guard, and no flat outline overpaints active material borders.
- [ ] **Incremental cost and dormancy proof:** benchmark *border OFF vs border ON* with accepted card materials
  unchanged, single and crowded ordinary widgets, overlapping material headers/controls, and on both Vulkan and
  OpenGL where available. Capture per-pass GPU median/p90, frame p90/p99, 90 Hz missed cadence, CPU, resource and
  material node counts, GPU-memory delta and shared-backdrop dormancy. Regressions must be measured and resolved
  before marking complete; this cosmetic task must not displace native-core priorities.

### 1.8 Gmail and Reddit/Reddit2 column gestures

- [~] D1 run (1B.14 harness), gestures posted by messages: top grips reorder.
- [~] Same run: solid-span endpoints change start/width and truncation.

### 1.9 Settings native corner clipping (next step is 1B.9: the operator's +2 px border allowance)

Reproducer: `tools/settings_native_corners.py`; evidence and the rejected candidates (Qt and post-Accent regions, an
inset native-child blur): `Docs/Architecture/Settings_Theme_Architecture.md`. No candidate code ships.

- [ ] Find a composition treatment that actually clips Accent material at the rounded silhouette: a viable rounded
  composition host, with input, resize/DPI, activation and lifetime proof (material transparency alone cannot
  close it).
  - [ ] First candidate, if the operator still sees escape (from 1B.9): the Windows 11 DWM corner preference on a
    non-layered variant (Microsoft's guidance excludes layered windows and windows with a region from system
    rounding; cost check: shadow ownership, translucency, the layered-window repaint path of section 9's freeze
    fix), then a composition-host clip. Whichever clips needs input, resize, snap and maximise, DPI change,
    activation and Studio-over-Settings modality proven on the real `SettingsDialog` and Studio window.
- [ ] Keep it a separate reversible fix.
- [ ] Repeat the four-case corner/border/shadow gate before claiming improvement.

## 2. Awaiting the operator (decisions only; details stay at the item)

One line each; the detail and evidence live in the section named. Nothing here holds a phase open, and nothing here
is an operator look: looks, listens and feels are the lead's proofs (1B.14), and what has no simple test is a
Watchlist entry (operator, 11 Nov).

- [~] **Framed aperture on the saver card (8 Nov, decision):** the writer is fixed (R-181: the Visualizer's uniform-scale
  minimum is absolute, and settings load lifts stored cards to it). That alone does not restore the saver card's 45°
  look: the repaired 592x592 card holds a 1480x1480 world (0.4 px per world unit, aperture 5.29), still at the 90° x
  90° cap and visually the same as before (`.artifacts/evidence/architecture/framed_camera/20261108_scale_repair/`).
  45° on that card needs about 2.11 px per world unit (a 280-unit world). Decide: bound the framed aperture (or the
  vertical view) as well, or leave it to Edit (Restore Size, wheel up, side drag back to the wanted width).
- [~] **§1 8b P2:** decide whether to size the frame-age gain with a matched-GPU repeat game60 pair; gates 3/4 and their
  measurement limits are in the design record. The Windows default and H1/H2 repairs are already integrated.
- [~] **Decision, Waveform Preset 4 (the reference):** sign off the fixed-scale v7 trade-offs against main and the
  "floor first" lift (`TROUGH_LIFT_MAX` 1.5 -> 3: Preset 4's ribbon rides about .7 higher at p90 and stops dipping
  into the floor, operator: "rather it goes a bit higher when it has to than clips"), or ask for the tag's exact
  Preset 4 dynamics (numbers at 7.1, "Fixed-scale rework v7"; the lead accepted them on 6 Nov).
- [~] **Decision, Waveform on a small 640x560 card:** Presets 5 and 6 cannot fit it either way: crests now graze the top
  on 14-47% of frames, against floor contact before (an authoring choice; no reaction was shrunk). Sign off, or ask
  for taller-body authoring.
- [~] **Decision, expanded card's hover Edit lane (plan 01 M3c):** the lane (Restore Widget Size, the transfer arrows)
  stays withdrawn on the display-wide card outside Edit since M2, because each edits the ordinary card's layout,
  which that view does not draw (since 1D.7 its Rotate glyph turns the expanded card outside Edit and saves at
  once). Return it, and what should each do while expanded?
- [~] **Decision, overlays on pause:** a pause does nothing to them (by the spec, not built): Now Playing is event-only
  and has already faded after its window; with Always Show it stays up by definition. Add a fade-out on pause?
- [~] **Decision, Audio Analysis group in the Spline Curve and Oscilloscope Studios (section 9):** keep it or hide it?
  Every offered control moves the frame (Spline Curve's; Oscilloscope's Flare and Drive, and Tone for Bar Count, Block
  Size and Input Gain), though the Oscilloscope's trace itself is the raw capture.
- [~] **Decision, Studio clip loops (section 9):** the clips now start and end mid-song at the chosen loop points (Human
  and Growing Pains on their groove) for a seamless wrap, not at the earlier quiet-to-hot windows. Keep the seam, or
  restore the quiet-to-hot arc?

## 3. Lead and agents: active, paused and queued work

**Agents and slots:** `Docs/Guides/Orchestrator_Handbook.md` section 1 is the one source (roster, models, audits). The
plan holds every task in detail before dispatch: a brief is its plan item, and a report is checked against the item's
boxes (operator, 11 Nov evening). Closing before opening (operator, 12 Nov): a slot takes no new work while its last
report is unreviewed or unmerged, and a dispatch is sized to finish inside a usage window. The native core's state and
tracks are in item 8b ("Order").

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep `[~]`
validation steps and open side defects. Landed slices live in `Docs/Reference/Architecture_Checklist.md` (AC-01 to
AC-12, A-xx audit ids), `Docs/Audits/Settings_SSOT_Audit_2026-11-07.md` (AC-17 to AC-23), `Docs/Reference/Benchmarks.md`
("Recorded sessions") and the Historical Bugs records.

- [ ] **Learned levels still in other modes (lead audit, 7 Nov; operator: "Adaptivity is the enemy"):** move each to
  absolute audibility and fixed scales, mode by mode, with continuous-play evidence. The bus presence ratio
  (`musical_weight`, a 6 s running level) still gates:
  - [ ] Spline Curve (`devcurve_frame_runtime.py`); it also divides its body by a remembered peak
    (`devcurve_runtime.py`, 20 s memory, not opt-in), and its accents read a lane "above its own recent mean"
    (reactivity guide §13D, guide pass 8 Nov).
  - [ ] Extruded Bubble (`extruded_bubble_frame_runtime.py`).
  - [ ] Neon Lake (`logical_frame_capture.py`, `rendering/gl_programs/shockwave_grid_program.py`).
  - [ ] Oscilloscope.
  - [ ] Sphere.
  - [ ] `tools/labs/waveform_ribbon_recorded_input.py` still uses `musical_weight` and no longer matches production.
- [ ] **Vocal-band scorer into the music-response tool (8 Nov):** the PCM vocal-band (300-3400 Hz) series behind the
  mid-led routing evidence and guide §2C lives only in scratch (`lead_audit/vocal_band.py`); add it to
  `tools/visualizer_replay/waveform_music_response.py` as a lane so it survives scratch pruning.
- [ ] **Side findings of the Waveform second tick cut (7 Nov, not fixed there):**
  - [ ] `capture_visualizer_logical_frame` refreezes the common style (`freeze_render_fields(_common_style(widget))`,
    logical_frame_capture.py) on every tick of every mode, ~0.02-0.04 ms; a FrozenFieldsMemo would remove it.
  - [ ] The logical-tick capture reads every Waveform control (~150 getattr) and compares the whole configuration
    dict every tick (~0.07 ms together); a settings-change token would make the no-change tick free.
  - [~] overhead_baseline on main 4467759c counted gl 182 / py 7010 per Waveform preview frame against the
    81959727 baseline's 180 / 6987. The 11 Nov attribution (382ae139) found and fixed per-frame Python-call rises
    and re-recorded the baseline: the lead confirms the two GL calls are accounted for, then deletes this box.
  - [ ] 11 of the 19 recordings in `logs/visualizer_recordings` lack native capture history, so the Waveform tick
    (PCM reanalysis) cannot replay them; identity proofs cover the other 8.
  - [ ] The Studio's step-state copy refuses NumPy dtype objects ("uncopyable Float64DType"); a dtype-keyed cache in
    a logical owner fails every Waveform Studio. Caught by `tests/test_waveform_studio_evaluator.py` and avoided in
    the cut (keyed by `dtype.str`); worth a line in the Studio's step-state contract.

**Active or paused:**

- [ ] Repair the shared Achievement Pulse mock field IDs (`build_mock_steam_view_model`): it emits rarity/session,
  while the card accepts total/latest/playtime/previous/source/selected. Existing fixtures can test impossible rows.
- [ ] Isolate active Widget Theme state between scene/display tests: the combined 33-file run fails four tests that
  pass alone (Achievement Pulse config, Gmail actions, Media projection and baseline theme material).
- [~] **D1 run (1B.14 harness), lead review of grabbed frames:** live Style Overrides/theme changes must reach
  Visualizer and Context Menu material in the current display generation (`_configure_quick_auxiliary`), including
  the new global opacity override.
- [ ] Extend actual faint-run pixel checks to light widget themes beyond the sampled Gmail/Media cards. Keep
  authoring-mirror failures separate from runtime material guards; contract:
  `Docs/Architecture/Card_Surface_Materials.md`.
- [ ] **AC-02 remainder:** what stays in `DisplayManager` until a second host needs it: the request and gesture
  routing that acts on the owner (mode/preset requests, view orbit, camera reset, Edit move/scale gestures,
  transfer glyphs) and the committed-CUSTOM profile resolver `_resolve_quick_visualizer_layout_profile`. Move any of
  these only when a second host needs them.
- [ ] **Settings round-trip memory growth (R-175; record `Docs/Historical_Bugs/R-175_*`):** the main cause is fixed;
  about 2.5-6 MB per round trip of unattributed native heap remains (against no-round-trip controls of the same
  build: Waveform +1.8 MB RSS a minute, Spectrum +0.3; round trips every 60 s still add ~2.5-4.5 MB RSS each on
  Waveform and ~3.5-6 on Spectrum; main ~19-20). Evidence:
  `.artifacts/evidence/memory/settings_roundtrip/20261107_settings_roundtrip/`.
  - [ ] Next: a heap-block histogram per reveal, or an offscreen render-control loop (the Studio saw 1-2 MB a
    session). The memory map puts the residual in the default native heap (+5-6 MB a round trip on both modes); it is
    not Python, retired wrappers, the Settings dialog (+0.1-0.25 MB each in isolation), the QML engine and its
    components, GL accounting, threads, handles or the driver's `private_other`. Left: the Quick window, its GL
    context and scene graph, and the Visualizer's GL programs per generation.
  - [ ] Gate 4 (8 Nov, 20 round trips, Spectrum P1): the same residual with the engine worker on and off (main
    +4.2 / +3.2 MB RSS, +7.0 / +6.1 MB private a trip); each trip also leaves ~1,700-1,800 tuples and as many
    weakrefs tracked (census, on and off), and the main process's pagefile-backed section views rose by 2 over the
    20 trips on both paths (106 -> 108 off). Attribute these.
  - [ ] The invisible Waveform live check grows with no round trips at all: +7.2 MB private a minute over a 600 s run
    (`wf_p4_no_roundtrip_fix`; ~3.8 MB a minute on the steady stretch between image steps; main
    `wf_p4_no_roundtrip_main`: +2.6 MB RSS a minute, branch +1.8). tracemalloc puts the Python share at ~1 MB a
    minute, mostly the harness's own per-frame lists (`tools/eb_live_phases.py` `_frames`, `_waveform_signals`,
    unbounded for the run) and the probe; the rest is native heap, unattributed. It bounds any round-trip slope from
    a 60 s schedule. Next: overnight, R-97 method.
  - [ ] The Spectrum P1 control (`sp_p1_no_roundtrip_fix`) kept RSS flat (+0.3 MB a minute) but private bytes jumped
    +476 MB at ~7 min, non-resident, and fell by 216 MB two minutes later: committed-not-touched memory, R-97/R-99
    territory.
  - [ ] One `QWidget` wrapper of every Settings dialog outlives it: the initial tab's placeholder
    (`ui/settings_dialog.py` `_build_tab_by_key`: `removeWidget` + `deleteLater`). Its C++ object is destroyed, no
    Python object refers to it, a full collection leaves it: shiboken keeps the wrapper. One small wrapper a trip.
  - [ ] The Settings dialog barrier's `destroyed` callbacks outlive it in the live run: tracemalloc shows 459
    `functools.partial` objects from `RuntimeDestructionBarrier.watch_qobject` (`engine/runtime_destruction.py:250`)
    added and kept every round trip (~36 KB; the dialog barrier watches 467 objects). Not reproduced with a bare
    dialog (298 watched, all released).
  - [ ] `QuickSceneFactory` is per display generation, not process-level as its docstring says, and its
    `QQmlComponent`s have no QObject parent: Python owns them, so they outlive their engine for as long as their
    wrappers do (until R-175's collection). Fix the docstring or the ownership.
- [ ] **GC freeze per generation (merged 7 Nov): the live check is owed (lead, quiet machine).** Evidence:
  `.artifacts/evidence/memory/gc_gen2/20261107_gc_gen2/` (`live_roundtrip_wf_p4_{main,pregc}/`).
  - [ ] Waveform P4 and Bubble, 600 s, game60, with `--frame-trace`, alternating main and branch; then
    `tools/frame_trace_report.py` for gen1/gen2 pauses per hour and the heap census at the reveal.
  - [ ] One long run with a few Settings round trips (`tools/visualizer_live_check.py --settings-roundtrip AT[,AT]`):
    a re-freeze after each reveal, no barrier timeouts, flat memory, and the `[GC_POLICY]` lines.
  - [ ] The live 64-152 ms spikes at Waveform preset switches are not yet attributed; the live trace will show
    whether they are collections.
- [ ] **Lead, the quiet machine, 7 Nov session (stopped early by the lead; evidence
  `.artifacts/evidence/performance/quiet_session/20261107_quiet_session/<task>/receipts.md`):** owed runs and the
  baselines they are judged against (overhead baseline `tools/baselines/overhead/2026-11-07_4bb2b775.json`):
  - [ ] M0 EB baseline (`2_m0_eb_baseline/`) gaps, never measured: GPU `TIME_ELAPSED` (the live check has none),
    p95/p99, lease/pool counts beyond the media leases, audio-to-photo freshness, and the unexplained two-monitor
    canonical game60 outlier (48.6 fps, never repeated). Reference: only the display-sized view moves; under game60
    its render mode is 8.2 ms against 4.4 at the card (over §0.7's 8 ms) and fps 64 against 73; tick (5.1 ms game60,
    2.7 idle) and GIL do not depend on size.

**Found while landing AC-01 (7 Nov; record, not yet admitted):**

- [ ] `tools/flicker_test.py`'s Widgets-tab `setup_ui_only_*` modes patch `widgets_tab_media.build_visualizers_ui`,
  which no longer exists anywhere (the Visualizer left the Widgets tab at V7), so those modes fail at `getattr`
  before measuring (its mode-body stub now targets `spec_mode_builder.build_mode_body`).
- [ ] Gate note: `tests/test_release_media.py::test_source_change_during_capture_discards_media` fails in any agent
  worktree (and in a fresh one on main) because the operator's Usu scene originals (`assets/usu/scenes/UsuScene*.png`)
  are untracked and exist only in the main checkout; environmental, not a product defect.

**Found while landing AC-03 (7 Nov; record, not yet admitted):**

- [ ] Production never calls `engine_lifecycle.cleanup`: the terminal path is `stop(exit_app=True)` and its barrier
  finalization (and the post-loop `finalize_after_event_loop` backstop); `cleanup()` is reached only by tests. AC-03
  retires the tier on both paths (idempotent); a change to one terminal path must check the other.

**Found while centralizing tool output (7 Nov; record, not yet admitted):**

- [ ] Dead evidence references (the folders no longer exist; `tools/artifact_migration.py refs` lists them):
  `logs/evidence_chest/08_*` in Historical_Bugs R-53/56/57/58/59/60/62, `.artifacts/evidence/{ribbon_path,
  ribbon_frames,ribbon_strip,expanded_visualizer,oscilloscope}` and several `waveform_ribbon/wr*` folders in
  `Docs/Reference/Ribbon_Path.md`, `Waveform_Ribbon_Lab_Plan.md` and
  `Waveform_Ribbon_Mist_Failure_and_Replacement.md`. Left unchanged; prune or mark historical on review.

**Side defects (Studio stall / clip selection fix, 7 Nov):**

- [ ] Bubble, Sphere and Extruded Bubble replay a change in one GUI-thread evaluation (no frame budget). While
  playing, the pass restarts, so the replay is short. Paused, an edit 6 s into Human still costs one evaluation of
  about 1.5 s (Bubble), 0.3 s (Sphere) or 0.2 s (Extruded Bubble), measured 7 Nov without load. Give them the frame
  budget (`ExactReplay`) or accept the cost.
- [ ] A restart still replays the clip's 2 s analysis lead-in (`clip_loop.PREROLL_S`) under the 8 ms budget. That
  holds the preview for about 0.7 s (Waveform) or 1 s (DevCurve), shown as "Updating...". A larger budget for that
  one replay would shorten it.
- [ ] `tests/test_visualizer_control_hints.py::test_lazy_visualizer_root_retains_initial_hint_capability` still
  builds a `QuickDisplayWindow` (it is never shown), which the probe rule forbids. Move it to the render-control
  pattern.
- [ ] `tests/test_studio_exit_every_mode.py` still calls `shiboken6.delete(...)`. The plain-orbit file's two calls
  left Qt Quick's pointer state dangling, and the next Quick window's mouse event in the same process crashed (the
  control-hints access violation). Check whether this call is safe.

**Found while building Expanded Visualizer M2 (7 Nov; recorded, not yet admitted):**

- [ ] Extruded Bubble drift family revisions are process-global (`extruded_bubble_drift_log._REVISIONS`): two
  identical replays in one process publish different labels, so in-process digest comparisons of EB (and the
  Studio's packet-hash proofs, if they ever replay EB twice in one process) differ for no behavioural reason. The M2
  harness numbers each replay from 1 (`fresh_drift_revisions`). A per-runtime counter would remove the trap.
- [ ] A takeover fade completes on the publication edge only: like the activation fade it has no deadline, so with no
  logical publication (displays off, parked) an expand or collapse in flight waits and finishes when publications
  resume; the coordinator meanwhile refuses mode requests and transfers as busy. Watch for it at M5 (display power).
- [~] Lead review of a rendered expanded-card frame (hidden host, then D1 grab): the expanded card shows the theme's
  surface material (the Visualizer card's `visualizerCardSurfaceMaterial` exists since 0b4abe04, so it is no longer
  a plain rectangle).

**Found while building Expanded Visualizer M3 (7 Nov night; recorded, not yet admitted):**

- [ ] An ordinary root's initial fade runs its family's own fade from QML's default: the host writes `fadeOpacity`
  before parenting (`OrdinaryWidgetPresentationHost._adopt_item`), but a family `Behavior on fadeOpacity` (the
  OSD's, 1150 ms) is already live, so the root animates 1 -> 0 instead of starting at 0, and a
  `set_fade_opacity(1.0)` in the same turn reads the not-yet-ticked 1.0 and is skipped
  (`RetainedOverlayWidget.set_fade_opacity` compares first), so that reveal is lost. Harmless today (the startup
  gate is closed while generations build, and a real OSD reveal arrives later), but a mid-generation root with an
  authored fade would show a brief fade-out. The M3 test waits it out. Fix at the host (project the initial fade
  with the Behavior bypassed) when admitted.
- [ ] The overhead baseline cannot see the QML scene: `tools/overhead_baseline.py` renders render nodes on a bare
  host, never `DisplayScene.qml`, so scene-level dormancy (M3's cover) is proven by the QObject census and the
  no-per-frame-work structure instead.

**Found while building Expanded Visualizer M3b (8 Nov; recorded, not yet admitted):**

- [ ] A Card on a material shows the wallpaper, not the Visualizer: the shared backdrop is the wallpaper layer only
  (`Docs/Architecture/Card_Surface_Materials.md` §3), so on Glass over an opaque mode (Extruded Bubble) the card is a
  blurred wallpaper the Visualizer hides everywhere else. It reads as a tinted panel (evidence still
  `extruded_bubble_06_card_glass.png`). Lead review on rendered stills (Glass over Extruded Bubble, then other
  modes): whether that is acceptable. (For a surface that overlaps the Visualizer the native answer is decision
  D7 point 7, item 8b N5.9; the card's own material keeps the wallpaper.)
- [ ] Right-hand corners sit further in than left ones: they keep clear of the card's hover-revealed controls (about
  80 px from the top edge for the collapse glyph, its tip and the 3D hint; the bottom for Reset Camera, the preset
  steps and their tip). Fullscreen Edit (M3c) can move an overlay. Lead review on rendered expanded-card frames:
  revisit if the gap reads odd.
- [ ] Now Playing needs an admitted Media card somewhere: it reads the Media model the Visualizer already binds; with
  Media off on every display there is no source and nothing shows (by design: no second Media source).
- [ ] The hidden render host never waits for the GPU: `tools/expanded_visualizer_evidence.HiddenDisplayHost.render`
  queues unthrottled frames, so the next texture upload (a glyph, a layer) waits for the whole queue (40-390 ms
  measured on the M3b scene) and time-based QML animations jump past what a test samples. The M3b tests finish each
  frame (`glFinish`); other users sampling animations should too, or the host could finish its frames itself.

**Found while building Expanded Visualizer M3c (8 Nov; recorded, not yet admitted):**

- [ ] `tests/test_visualizer_preset_glyphs.py` opens a real window (offscreen QPA hangs it), so the glyph-row agent
  could not run its updated assertion (Edit's glyphs match the card's 26 px). Port it to the hidden production host
  (QQuickRenderControl, as `tests/test_visualizer_glyph_row.py` does) and run it.
- [ ] `tests/test_qtquick_context_menu.py` fails after `tests/test_qtquick_custom_layout_owner.py` in one process
  (the 1B.1 side defect); the same pairing also turns three `tests/test_visualizer_direct_gestures.py` tests red
  (Alt-wheel / Alt-drag gestures never begin; reproduced on e9bbd7a4 without the M3c single-axis/rotate changes,
  8 Nov), so it is the same leak.
- [ ] The overlays' Edit placeholders are fixed English words ("Preset Name", "Track Title", "Artist"), shown only in
  Fullscreen Edit when there is nothing to show yet.

## 4. Runtime side requests (operator, 5 Nov; run alongside the order above)

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep `[~]`
validation steps and open side defects.

**Slow startup (operator, 6 Nov 10:30; owners fixed, awaiting the lead's cold start)**

The held-lock rule is in `Docs/Guardrails/Performance_Optimization_Contract.md` section 5, the optional-worker start
in its appendix.

- [~] D1 run (1B.14 harness): cold start with `--usage`, then the lead reads the log:
  - [ ] No `UI_CALLBACK` / `FEED_GUI_DELIVERY` line exceeds a frame (the 166-240 ms lines of 6 Nov were not
    reproduced offline: 0.1-15 ms per source; treated as post-block backlog on a 97-100% CPU machine).
  - [ ] The first `collect_ms` is small.
- [ ] Side defect: a prefetch batch asked for before the optional image_prefetch child is ready fails as "not
  running" (a logged `[PREFETCH]` error); that batch is not retried.

**Spline Curve (`devcurve`) "more alive while keeping the flow" (second cut 6 Nov; awaiting lead review)**

Contract: guide section 13D -> DevCurve. Evidence: `.artifacts/evidence/visualizers/devcurve/reactivity/20261105_reactivity/`.

- [~] Lead review on the rendered before/after WebPs (loud end and a quiet passage, P1/P6): the second cut reads
  more alive while keeping the flow.
- [ ] Open: the strongest preset's bass stays ~18% below pre-work main's loud RMS (a smooth wave cannot
  match a slope-limited triangle at the same slope).
- [ ] Open: the quiet-passage evidence is one recording's cold start (9 kicks).
- [ ] Open: a capped layer shows the swell less (it lives inside the body's share).

**Waveform logical tick starves the render thread under game load (quiet-machine game60, 6 Nov)**

This is the Graphics Backend Decision's "optimise the logical tick first" step before trigger 2 can be judged.
Evidence `.artifacts/evidence/performance/live_check/20261106_quiet/`. Baseline to beat (main, game60): Waveform
P1/P4 tick median 8.5/8.3 ms (p90 14.4/14.0), GIL held 73-75%, render-mode 16-17 ms, 41-44 fps; same session
P1/P4/P7 43.5/42.7/37.6 fps, tick 8.5-8.7 ms (p90 14-16), GIL 0.75, P7 64% late frames; under the same load Neon
Lake runs 89 fps, Spectrum 90, Bubble 63, Extruded Bubble 5.9 ms / GIL 0.53 / 55 fps.

- [ ] Profile the LIVE logical tick (offline the Waveform dynamics are ~1.3 ms and the whole tick replays in ~1.5 ms;
  the live cost is elsewhere: capture, packet build, field/strand/spark work). Offline ticks above ~16 ms are gen2
  GC (86-161 ms, about one per 5,500 ticks), not Waveform work.
- [ ] Record the logical thread's own CPU time (`time.thread_time`) beside the tick's wall time in the live check,
  so the wait share is a number (a no-load P4 run measured a 7.49 ms tick median; about 6 ms of each live tick is
  likely spent waiting for the GIL held by the render/GUI threads). Switch-interval tuning stays banned by the
  Performance Optimization Contract.
- [ ] Cut what the profile names, with byte-identical output (Preset 4 bit-exact with tag
  `waveform-baseline-2026-11-05`).
- The game60 re-measure of the two tick cuts is superseded on the default path: the tick runs in the engine
  worker (P2), and the 11 Nov load session measured it there (item 7). The boxes above matter for
  `--viz-in-process` only; the lead decides whether they still pay.

**Widget/Settings material appearance: Awaiting Validation**

Active work: section 1A, items 1.7/1.9. Owners: `Docs/Architecture/Card_Surface_Materials.md`,
`Docs/Architecture/Settings_Theme_Architecture.md`.

- [~] D1 run (1B.14 harness), lead review of grabbed frames, in the running app:
  - [ ] The inner rim.
  - [ ] Transport, mute and volume.
  - [ ] Dark and light palettes.
  - [ ] Linked material choice.

**Widget theme legibility (open)**

- [ ] Theme the Weather detail asset icons: they remain white and become faint on pale cards.

**Extruded Bubble: a deep red ocean preset that truly matches the mock (operator 6 Nov, not urgent)**

The mock is `Docs/Reference/Extruded_Bubble/Targets/Originals/Preset7Goal.png`. One preset only; the shared
controls (Ember Grain, Ember Band, Lit Glass, Stream Lanes, Wake Tint) are each dormant at 0, so no other look
changes. Details: `Docs/Reference/Extruded_Bubble/Investigation.md` sections 72-73.

- [~] Lead review of side-by-side sheets (mock | ours, full resolution plus crops) of Preset 9 against the mock.
- [ ] Shells are paler and smoother inside than the mock's copper, busy-interior glass, and too many crowd together.
- [ ] Embers are partly along-stream strokes rather than torn debris.
- [ ] The lower right is far too busy (the mock's band fades out there).
- [ ] The shaft corner lacks its bright glittering core.
- [ ] Faint surface ripples at the top.
- [ ] Side defect: the near (defocus) layer stair-steps the rim of a large near shell on some frames (seen with Lit
  Glass off as well).
- [ ] Side defect: `tools/release_media.py` cannot render Waveform Ribbon showcases: the replay raises "Raw musical
  replay requires current PCM reanalysis" because `replay_clip` never drives
  `tools/visualizer_replay/pcm_reanalysis.py`.

## 5. Watchlist (observe during normal use; reopen only on evidence)

Live checklist: every box is an observation or a fix owed on evidence; delete an item when its evidence closes it.

**Extruded Bubble response during sustained playback (operator, 23 Nov)**

- [ ] Reopen if a failing take reproduces a persistent relative delay against a good take with the same profile.
  The supplied `logs/evidence_chest/logs077d6cc043.zip` has frame delivery but no independent audio-output clock.
  Matched recorded PCM, actual D1 worker snapshots, 4K shell pixels and the Realtek loopback comparison found no
  sustained fullscreen-start phase shift. The controls detected deliberate late PCM and late shell motion with fresh
  frame stamps. Keep the playback ramp and R-219 optics. Align independently timestamped audio output with callbacks,
  EB target and shell radii, and swaps before considering a change. Receipts are under
  `.artifacts/evidence/visualizers/extruded_bubble/fullscreen_start_latency/` and
  `.artifacts/evidence/visualizers/extruded_bubble/response_pixel_radius/20261123_live_d1_cold_124/REPORT.md`.

**Engine worker and platform (reopen only on evidence; no simple test exists)**

- [ ] Linux engine worker (best effort, never run): the named wake pipe (FIFO), the worker's spawn under
  forkserver, the shared mapping's tracker, Pulse capture in the worker, the listener thread ending when the
  worker's writer closes, and a broken worker showing as a logged in-process fallback. `--viz-in-process` is
  the escape if a Linux user reports the Visualizer missing.

**Neon Lake (`shockwave_grid`) camera step on real music (found 6 Nov, pass 7, pre-existing at 0776da08)**

Preset 1 on 1985_loud1 between 42.054 s and 42.075 s: the whole land shifts ~8 px down in one frame and stays (mean
step 8.5/255 against ~1.3; replay parameters and presentation identical across the two frames, Terrain Reaction
bands smooth).

- [ ] Find the owner (camera floor / reaction normalisation) with `tools/neon_lake_capture.py --clip ... --start 41.9
  --duration 0.3 --fps 90 --all-frames`.

**Neon render tests load-sensitive under parallel runs (5-6 Nov)**

`test_neon_lake_renderer.py` (once, pass-5 merge gate) and `test_neon_scene_materials.py` (once, pass-5 branch) failed
under parallel load and passed alone; the re-run overwrote each log, so the failing test is unknown (most likely a QSG
clip probe timing out).

- [ ] Next time it fails, read `logs/pytest_isolated/<file>.under_load.log` (the isolated runner now keeps the
  parallel-run failure) and fix the probe's timeout or synchronisation rather than rerunning.

**4x MSAA repeat-render noise (driver, 5 Nov)**

Mechanism and the shared comparison helper `tests/_msaa_render_noise.py`: `Docs/TestSuite.md` ("4x MSAA repeat-render
noise").

- [ ] Reopen if a driver update or another GPU shows the noise gone or larger.
- Parity gates judge single-sampled targets and report product sampling beside the path's own repeat; the noise
  is attributed only as far as "the mode's own passes" (11 Nov attribution).

**Display Settings capacity (physical hotplug)**

- [ ] On a real monitor disconnect/return or explicit reauthoring, Settings' current-screen rows and
  selections/bindings stay coherent.

**R38 hover display-transfer glyphs (physical topology)**

- [ ] Watch glyph hit/tooltip/fade and transfer on unequal-DPI screens and monitor unplug/return (equal-DPR pair
  passes).

**Steam Games You Follow images**

Many update entries lack images. A generic game cover existing is not proof an image is missing.

- [ ] On a report of missing images: audit URLs, redirects/statuses, cache keys, game IDs, fallbacks, dedupe and
  selection order (including artwork fetched but rejected downstream).
- [ ] Then prefer image-bearing updates without suppressing legitimate no-image entries.
- [ ] Instrument attrition and compare natively with Feeds (the lead's own comparison; no operator step).

**Steam artwork 404**

- [ ] Asset hash `9b4a68b51c5f` (23 Oct MC run, `logs/run_matrix/2026-10-23_idle_hint_shaft/`) and earlier
  `4b349d51e996` / `3f5b734df3c5`: decide stale metadata vs genuinely missing CDN asset before changing lookup.

**Monitor power/wake**

- [ ] Exercise: display off, > 30 s off, rapid off/on, reordered return, both selected displays absent; widgets keep
  physical assignments and CUSTOM geometry.
- [ ] On recurrence record timestamps, remaining screen, flavour, Interaction Mode and wake/exit input (history:
  R-79).

**Refresh contention**

- [ ] Correlate FEEDS/Gmail/Reddit queue/claim/publish/retire with transition delays in a natural dual-display trace
  (fairness, no post-transition stampede, retained last-good content).

**15 s usage-sample hitch (unexplained, not reproduced)**

31 Oct MC run: a 95-121 ms freeze of the GUI, render and logical threads at every `--usage` sample, because the
sampled tree held 7 processes / 233 threads (normal 3 / ~55); the four extra descendants used the GPU and are
unidentified. The next MC run and an invisible live check were normal.

- [ ] On recurrence read the sampler's `[USAGE] topology added ... name= parent= threads=` lines (one per process
  entering the tree), identify the extra processes, then decide whether the sampler must exclude/outsource them.
- [ ] Seen again 8 Nov with a normal tree (design doc step 6 "Gate 3 record"): every sample stalled the render
  thread 71-106 ms; `collect_ms` ~13 ms per process walked at 87% system CPU (23 ms for 4 on an idle machine).
  Main-side on both paths; the engine worker adds one process to the walk.

**Cross-display Media shortcuts**

- [ ] Delivered once on the other display, when exercised.

**Music recorder**

- [ ] 60-second clip, signal/history, cancel and mixed-DPR UI, when recording is needed.

**Helper breadcrumb diagnostics unavailable**

Current native MC evidence logs no access to `C:\ProgramData\SRPSS\logs\scr_helper.log`. Separate from Waveform
rendering.

- [ ] Inspect the helper/log-path authority before relying on that diagnostic route; do not hide it behind a silent
  local fallback.

**GitHub Remote builds (8 Nov, proven end to end; moved from section 2)**

`Docs/Guides/GitHub_Remote_Build.md`. Installing a remote-built product on an ordinary user account is the
"Installed builds" entry below; the frozen run of 1B.14 covers the artifact.

- [ ] Retire superseded native run43937313108 (`e15efeda1`, token20261116_211445_549725) when GitHub permits:
  REST reports queued/no jobs, while cancellation returns409 "not been queued yet" and token discovery cannot
  identify it. No local publisher is running. Do not redispatch that token or publish its older artifact over the
  validated c53e3fe27 module. This service-state cleanup is non-blocking.
- [ ] Since checkpoint audit 11 (8 Nov) the tab's Linux job runs beside the Windows runs on its own process owner
  (never holding their retrieval) and a stop cancels its run even before it was followed; tested with fakes only, so
  the next Remote run with Linux selected is its first real one: read its log and fix what it shows.

**Bubble / Extruded Bubble "terrible performance" reports (6 Nov log 10:32-10:35; moved from section 2)**

That log was our load (97-100% system CPU from game60 checks), not the product: on the quiet machine Bubble P1 ran
65.9 fps (tick 1.47 ms, GIL 0.13) and Extruded Bubble 45-69 fps. Heavy load runs are the lead's only.

- [ ] On a new report, read the log's system CPU first: a load-driven reading is not a product defect; otherwise
  reproduce on the quiet machine against those numbers.

**Displays off -> presentation pauses entirely, resumes clean (built 5 Nov; needs the machine's own screen timeout)**

Contract: `Docs/Architecture/Compositor_Architecture.md` -> Display power.

- [ ] When a heavy preset (Waveform Ribbon (`waveform_ribbon`) Preset 1 or Neon Lake (`shockwave_grid`)) is left
  overnight and Windows' screen timeout turns both displays off (not the panels' own buttons: an HDMI panel that
  stays enumerated gives no signal and the TV rejects DDC/CI queries; operator decision 6 Nov: no Screens Off
  command, the burden stays off the user; they enabled the power plan's display timeout), notice the saver's CPU/GPU
  in Task Manager while dark, whether wake input reaches the saver, and the first seconds after wake (a stale frame,
  a jump or a hitch). Run with `--frame-trace --usage`; when something shows, read that trace and reopen here.

**Load runs the 11 Nov session did not cover (reopen only on evidence)**

- [ ] The 600 s Waveform Preset 4 and Bubble GC runs with `--frame-trace` (gen1/gen2 pauses per hour) and a long
  run with several Settings round trips: one 85 s run with one round trip was clean (re-frozen, no barrier
  timeout); nothing has shown a steady collection since the GC freeze merged.
- [ ] The two-monitor canonical game60 outlier (48.6 fps once, 7 Nov, never repeated).
- The Waveform tick-cut A/B under load is superseded on the default path (the tick runs in the engine worker);
  it matters for `--viz-in-process` only.

**Installed builds as an ordinary Windows user (no such account or fresh install exists to test on; moved from 1.2-1.3)**

Durable behaviour: `Docs/Reference/Visualizer_Studio.md`; evidence:
`Docs/Audits/Studio_Camera_And_Fullscreen_Overlay_Self_Audit_2026-11-09.md` and
`Docs/Historical_Bugs/R-182_Installed_Preset_Files_Lacked_User_Modify_Permission.md`. Source-level file/Qt checks do
not establish installed ACLs; the frozen run of 1B.14 covers the artifact, not an installed ProgramData tree.

- [ ] On a freshly installed Screensaver or Dashboard build as an ordinary Windows user (when one is available): the
  installer grants Modify on the shared ProgramData Visualizer preset tree **and its existing files**; Save and Save
  Camera over a shipped preset work; Save As and reopen work; Save As New Preset's file dialog lands in the right
  folder in an installed build (ProgramData's shared preset tree). If one fails, fix the installer's ACL grant
  (R-182).

**Frozen release gate (operator scheduled)**

- [ ] Screensaver and Diagnostic from one compile.
- [ ] Dashboard and Reddit Helper installed startup/exit.
- [ ] Settings/widgets/cache/audio and installer behaviour.
- [ ] Installer logs and obsolete-file removal in both curated theme/preset trees. Both sources declare whole-tree
  replacement; verify Diagnostic now reads that installed theme tree too.

**Conditional evidence only**

- [ ] Original Bubble tiny-radius judder (R-105) needs a new reproduction.
- [ ] Dual-display reboot recovery (R-134–R-145) needs a new reproduction.
- [ ] The 90 Hz versus 60 Hz investigation stays off limits.

## 6. Shared 3D architecture: now inside section 1, item 8b

Kept as the target of the documents that cite "Current_Plan §6". The shared 3D primitives (S3D-1 to S3D-7) are
stages N3, N4 and N6 of item 8b, where the old ids are mapped; there is nothing else here.

## 7. Visualizer modes (backlog; when admitted, one at a time in this order)

### 7.0 Method: lab first, then production

Extruded Bubble's lab (`tools/labs/extruded_bubble_lab.py`) reached the mocks long before production did; production
then closed the gap by measuring against both. Do the same for every new mode:

- [ ] **Target first:** the mock/concept package and its low/high pair; write the mode's contract and hard gates (from
  its brief) into its focused doc before code.
- [ ] **Lab:** `tools/labs/<mode>_lab.py` composes the target scene by hand, offscreen, from the shared primitives,
  with free knobs and no Settings/preset plumbing. From the native core on, a lab composes from the core's
  harness primitives (item 8b): no new Python OpenGL scene code.
  - [ ] Reuse the context/target and ownership contract in `Docs/Guides/Visualizer_Labs.md`.
  - [ ] Iterate on rendered stills (mock | lab sheets) until it is close.
- [ ] **Production through the shared substrate:** typed Settings, presets, the logical clock and lifecycle.
  - [ ] Diff the lab's effective knobs against production's key by key.
  - [ ] Judge with **mock | lab | ours** sheets per preset, the per-mode capture tool (`tools/<mode>_capture.py` on
    recorded real music) and measurements (regional colour, on-screen size bands, Range audits), as in
    `Docs/Guides/Visualizer_Visual_Tuning.md`.
- [ ] **The lab is a waypoint, not the goal:** keep going toward the mock; keep the lab (it costs the product nothing).
- [ ] **Same-scene low/high proof, measured cost, dormancy and retirement** before calling any stage done, including
  the live-shape check under the calibrated game load (`tools/visualizer_live_check.py --load game60`, budgets in
  `Docs/Guides/Visualizer_Change_Checklist.md` 1C); the operator gives final sign-off.

### 7.1 Waveform Ribbon (next)

This is the single live list of reported failures, proposed corrections and required evidence (Awaiting native
validation/operator judgement, 2 Nov; updated 3 Nov). Tests establish mechanisms, not visual acceptance. Work first on
body/audio/accents, then grounded camera/viewport and replacement atmosphere. Binding references:
`Docs/Guides/Visualizer_Reactivity_Authoring.md` sections 13A-13C; control/design ownership
`Docs/Reference/Waveform_Ribbon_Migration_Plan.md` (recorded measurements: its section 8); motion targets and recorded
bake-off `Docs/Reference/Waveform_Ribbon_Lab_Plan.md` section 5.1. Keep C-primary elastic response and A's accumulated
twisting.

**Reactivity milestone baseline (operator, 5 Nov): tag `waveform-baseline-2026-11-05` (= `e598155d`)**

Pulse and Centre Out "like night and day"; logical cadence survives heavy game load; **Preset 4 is the reference**
("let us not lose this"). Preset 4 keeps Breathing 0 (exactly the baseline dynamics).

- [ ] Every later dynamics change shows, on the recorded clips, that Preset 4 is unchanged against this tag (or names
  the improvement for operator sign-off).

**Operator-selected recovery baseline (3 Nov)**

`Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.png` and its `.capture.json` preserve the exact
chosen image/settings/source; the baseline settings are applied to Preset 3.

- [ ] Use this material direction; do not darken the background or lower the floor's colour level. Retain this
  reference before further work.
- [ ] Floor brightness is provisionally approved, not the entire floor/atmosphere.
- [ ] Remaining lumps and reactive detail still need improvement.

**Fixed-scale rework v7 (accepted by the lead review 6 Nov, merged; operator sign-off on Preset 4 and the trade-offs)**

No adaptive memory (the Adaptive Response toggle is retired), Kick Accent bounded at 15% of the roll (Preset 4
ships 0), the floor lift bounded by the card's top edge. Lessons of the rejected v4:
`Docs/Guides/Visualizer_Reactivity_Authoring.md`; measurements: Migration Plan section 8.

Trade-offs against main, for the operator's sign-off or a request for the tag's exact Preset 4 dynamics (the decision
is in section 2; the lead accepted them on 6 Nov):

- Preset 4 visible amplitude p10/p50/p90 -4/+4/+5% and 3 s contrast +4.5% against the tag (inside the +-10% gate).
- Preset 7 roll 1.12x; P7 saturation higher on two songs (10.2% / 6.8% against 3.4%).
- Kick peaks 1.6-6.4% under main in 6 of 16 song-time bins (worst P7 0-15 s) and 6-11% over it in sustained loud
  bins.
- Quieter-after-loud kicks 8-27% under main by design (a quieter passage is no longer re-normalised up).
- Top-row spark density up to about 2x main.
- **Floor first (7 Nov, operator: "rather it goes a bit higher when it has to than clips"; supersedes top edge
  first): Preset 4 change for sign-off.** `TROUGH_LIFT_MAX` 1.5 -> 3, `TOP_GIVE_BACK` 1.5; Floor Give (P2) and Static
  Height keep 1.5. Preset 4's lift p50/p90 .75/1.48 -> 1.01/2.19 at 1282x1005 (the ribbon rides ~.7 world units higher
  at p90, at most 1.5 higher, in loud passages) and no longer dips into the floor (7.8% -> .1%).

- [~] Lead review on the music-vs-response traces (`waveform_music_response.py`; chain7, every preset and Reaction
  Mode; 7 Nov):
  - [ ] Group Wave registers single kicks least: P7 as authored born rise .03-.06 per kick, P7 forced to Travelling
    Pulse .16-.30, and 46% of P7's kicks raise its born swell by under 1% of its range (Travelling Pulse 25%).
  - [ ] Whole Swell plateaus in flat loud songs (P6 song 2 saturated 20%, ws_P1 15%): the music's RMS is flat there and
    beats ripple the plateau, so it reads as sustained, not pinned.
  - [ ] Song 1's sparse intro (big isolated kicks in the PCM) barely moves any preset while the carry-over from song 0
    decays (re-scale gap .37-.50 on most presets).
- [ ] At the 640x560 card: P4 Anything's crest-clipped share is 6.2% against main's .4% (crests graze the top edge)
  and P4 Rag Doll 2.1% (.4%); crests above the top on .2-1.1% of ticks (main 0-.1%).
- [ ] P5 and P6 do not fit a 640x560 card with any setting (floor 32-43% and crests above the top 16-36% of ticks;
  rendered crest clipping 14-47% against main's 2-16%): authoring, their bodies are taller than that card.

**Preset 7 and the other reaction modes (operator log `logse7a84d332e.zip`, Rag Doll, 5 Nov; awaiting the lead's
review)**

Complaints: no decay/breathing in soft passages, sustained passages with changes read almost flat, a swell to full
power as the song got QUIETER. Preset 7 is Group Wave (song 31-123 s in the log; the recorded clip is song 70-130 s).
Evidence `reactivity_preset7/20261107_reactivity_preset7/`.

- [~] Lead review on a rendered showcase WebP and the music-response trace of Preset 7 (bodies are smaller in loud
  passages now that the uniform inflation is gone: sustained-loud visible amplitude 6.4 -> 5.4).
- [~] Lead review on rendered Whole Swell (Preset 6) strips: it sits at its soft bound in all music by design (one
  global level; de-saturating it barely changed the visible body, so it was left).

**Breathing + anchored history ends (merged; awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/breathing/20261105_breathing/`.

- [~] Invisible run on recorded music and lead review of the animated WebP: soft passages let go between swells (0.7
  in every preset but 4) and a quieter passage after a loud one stays quieter.
- [~] Lead review on a rendered side-angle WebP: the tail no longer staggers at side angles.

**Four-ribbon maximum and Preset 3 (Awaiting Validation)**

The operator's maximum is four ribbons (it overrides the first board's decorative count label); Preset 3's paired
target uses four.

- [~] Lead review on mock | ours sheets (full resolution plus crops): validate Preset 3 against
  `references/Preset3Goal1.png` and `references/Preset3ReactivityGoalExample.png`:
  - [ ] Teal/orange contrast.
  - [ ] Readable lattice/twist/strands/particles.
  - [ ] Continuous wet textured floor.
  - [ ] The large quiet-to-peak geometric change shown.
- [ ] Native low/high/recorded captures must reach that range without pinning or swapping scene/camera identity.
- [ ] The recorded draft still needs visual correction: white/rope-like overlaps, repeated continuation, weak/dark
  atmosphere and a poor floor/contact strip remain rejected.
- [ ] Do not equate source tests, particle/root counts or larger amplitude with reference fidelity.

**Reaction: travelling energy pulse + four Reaction Modes (5 Nov; awaiting the lead's review)**

Design: Migration Plan "Current reaction model"; decision record in the audit doc, decisions 7+; evidence
`.artifacts/evidence/visualizers/waveform_ribbon/studio_20261105/modes/`.

- [~] Lead review on rendered strips and music-response traces: Travelling Pulse (default), Frozen Past, Whole Swell
  and Group Wave read right on recorded music (flow-rule and twitch tests exist for every mode).
- [ ] Group Wave still reads close to Travelling Pulse on rendered strips (it keeps the summed travelling field; its
  sets need their own pass), and its Pulse Width is not yet the band core the other two modes use (operator: "a
  relatively small horizontal width and the full vertical width").
- [ ] Pulse bands' colour edges read crisp at Pulse Falloff below ~1 on wide bands (Preset 5's vertical colour
  columns); judge on the operator's look whether the light's falloff should follow the geometry's broader envelope.

**Particles (5 Nov candidate)**

- [~] Lead review on rendered crops and a WebP: crest-weighted, distributed births in each ribbon's colour, visible
  >=1 px cores with soft halos, gentle fade; swells gather particles (Pulse Particles).
- [ ] Open: still sparser than the high-react reference (admission-limited).

**Strands: rare, 3-5 seconds TOTAL life**

The latest operator correction supersedes the proposed 30-second fade.

- [~] Lead review on a rendered strand WebP: preserve the approved non-flickering look and make appearances much
  rarer.
- [~] Same review: use most of a configurable 3-5 second lifetime for a gentle tip-first fade.
- [~] Same review: reactivation restores them smoothly, with glow and movement/growth (retain the approximate 20%
  repeat extension), without abrupt respawn or pulse reset.
- [ ] Prove quiet/peak lifetime handles, tip/root fade ordering, slow decay, partial-fade reactivation and
  direct/reflected appearance.
- [ ] Retain birth look during travel; finite history eviction must not cut off a visible unfinished fade.

**Colour, floor and mist (5 Nov candidates; awaiting the lead's review)**

Evidence `studio_20261105/floor4/`; measurements in Migration Plan section 8.

- [~] Lead review on rendered sheets: lattice sheets (V3).
- [~] Lead review on rendered strips: wet concrete with stable soft coloured reflection mass (no horizon line, no
  flicker-prone streaks; operator prefers smeared colour to streaks).
- [~] Lead review on rendered sheets: one bounded night medium with a slight local ribbon tint (strong Local Light
  can no longer wash the frame).
- [ ] Wide sheets (P2) still graze the floor on ~60% of ticks: optional Floor Give (below) lets the wet floor dent
  under them instead.

**Fixed response, break-proof Breathing, Kick Accent (operator, 6 Nov: "when it went suddenly quiet everything become
more reactive ... Adaptive is a very problematic approach"; "many sustained kicks ignored"; awaiting the lead's review)**

Geometry drives are a fixed function of the real-music scale (the Adaptive Response toggle is retired). Preset 4
differs from the tag only through it, Kick Accent and the floor lift: compare against the tag with Kick Accent 0.
Range audit: `.artifacts/evidence/visualizers/waveform_ribbon/reactivity_preset7/20261107_reactivity_preset7/rangeaudit_*.txt`.

- [~] Invisible run on recorded music and lead review of the music-response traces: the fixed response, Breathing
  and Kick Accent.
- [ ] Rotation's drive is never above .36 on any recording (its Peak handle is never reached).
- [ ] Light/Colour/Sparkle/Highlights, Width and Lift never reach .8 on three or four of five songs: those
  calibrations (not the response gain) are the remaining Range losses.
- [ ] The music's return after a break still dips for about a second while the shared passage level climbs back
  (return window 12-55% of the unbroken clip on every arm, main included).
- [ ] Preset 3's quieter-after-loud kicks are 4% under main's (every time bin is above).
- [ ] Soft passages swing less in absolute terms (3 s contrast .21 vs the adaptive gain's .30) and loud ones .11 vs
  .16.

**Floor Give (operator, 5 Nov: "the floor can deform inwards, allowing crests"; awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/floor_deform/20261107_floor_deform/`; design in the
Migration Plan's Floor bucket.

- [~] Lead review on rendered stills and a WebP: where a lower edge comes down onto the floor the wet floor yields in
  a soft dent, so troughs stay round and dip in instead of flattening: in the visible frame P2 reaches the floor
  only in the ragdoll loud end (about 49.5-52 s); P3 never does, so it is unchanged there.

**Pulse Rim (operator, 5 Nov: "where the pulse is that section of the ribbon's rim can be even brighter with
falloff"; awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/pulse_rim/20261107_pulse_rim/`; design in the Migration
Plan's Reaction bucket.

- [~] Lead review on rendered strips: the rims (line and rim glow) brighten on the pulse with the field's own smooth
  falloff, in every Reaction Mode and both Travel Directions.

**Swells reach the Preset camera already faded (Presets 1-3; awaiting the lead's review)**

Evidence `reactivity_preset7/20261107_reactivity_preset7/` (`visibility_tag_vs_final.txt`, `kicks4_table.txt`,
`sheets/*_p1..3_*`); design in the Migration Plan.

- [~] Lead review on the rendered sheets of Presets 1-3: edge swells arrive in view at strength.
- [ ] Open: on Presets 1/3 the rim's swell-to-elsewhere contrast (1.11/1.17) is still below Preset 4's (1.27).
- [ ] Open: the no-twitch probe's .02/.01 bounds only held because its swells never reached the cloth (in-view
  .028/.012).

**Travel Direction (operator, 5 Nov: "Travel Direction ... chosen in the studio ... an important basic need";
awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/travel_direction/20261107_travel_direction/`; design in the
Migration Plan's Flow bucket.

- [~] Lead review on a rendered WebP of a live change: it fades out, swaps while hidden and fades back (0.6 s each
  way).
- [~] Lead review on rendered strips: Left To Right mirrors history, pulses, held swells, Tilt Shift, sparks,
  strands and floor give.

**Dense highlights, moving colour and rim glow**

- [ ] Playback still lacks rewarded high-energy density and glow: verify local crest/high-power colour, bright
  tunable rim/glow and denser highlights against actual music, including quiet/loud differences.
- [ ] Consumer reachability does not establish visible strength. Keep both range handles effective.

**Idle and first-play blackout**

- [ ] Keep subtle low-energy body motion and the same ready scene on first play; no blackout, re-priming or scene
  reset.
- [ ] Test cold playing-before-start, silence, pause/resume and source changes.
- [ ] Idle must not emit fake musical hits or particles.

**Dynamic Floor independence**

The operator found floor ON more responsive. Controlled full PCM now proves identical body/birth packets and typed
events OFF/ON on four clips.

- [ ] Prove lively OFF response by ear/eye against the guide's standard; raw parity alone does not establish musical
  response.
- [ ] Preserve the existing FFT/bus raw-reference policy, mode-switch/reset and stale-compute fences, plus accepted
  Bubble/EB behavior.

**Grounded camera, near-flat tilt and infinite view**

Perspective is the only projection (Orthographic removed 5 Nov 2026) and retains its positive clip contract. Native
geometry and persistence tests alone cannot establish feel or beauty across moving audio, view and viewport extremes.

- [ ] Stable eye height above the floor, approach/retreat and bounded left/right orbit, waveform always in view and no
  escape into ugly areas.
- [ ] Admit a genuinely near-flat tilt with visible floor.
- [ ] Keep eye/basis, navigation, editor markers and saved pose under the shared owner; preserve continuous/infinite
  body with no exposed ends and complete Edit scaffolding.
- [ ] Reproduce the new cut-to-black at one end and staggered entry at the opposite end against recorded wide/angled
  playback.
- [ ] Current visual route (operator delegates the choice): a restrained long-lens Perspective primary view,
  calibrated with a farther physical eye and narrow lens together; preserve stable height, bounded orbit and actual
  camera movement; no camera-dependent actor density or audio compensation.
- [ ] Judge colours, restrained reactive twisting, floor material and full-scene mist together against the references
  before acceptance.

**Floor coverage, collision, reflection and viewport changes**

- [~] Lead review on rendered frames (D1 run, 1B.14 harness, for native pixels): the floor now intersects the same
  physical camera's pixel rays with the infinite world plane, covering foreground/far ground while actor clipping
  remains unchanged. Finish the unified atmosphere before visual judgment.
- [ ] After the strand slice, draw ground all the way through the foreground and beyond the waveform into heavy dark
  mist that GENTLY thickens until no horizon line is visible. A strip of reflections over black is rejected.
- [ ] Keep actors and physical floor contact correct, with smooth waveform collision rather than clipping.
- [ ] Compare identical snapshots at canonical/wide/tall/large sizes in Perspective; inspect reflection
  normalization/filtering separately.
- [ ] Preserve live reflectivity/tint/brightness and the shared resize contract; no audio-gain compensation. Columns
  remain secondary.
- [ ] Additional explicit rejection: material outside the core reflection is practically invisible. Validate readable
  dim texture across the foreground with reflection and atmosphere both OFF, then under the unified night medium;
  increasing reflection alone cannot satisfy this. The current candidate restores filtered concrete/roughness and
  ambient light.

**Unified atmosphere (5 Nov candidate)**

Replacement medium in place (old banks/fringe/floor haze removed); P3 density 0.06-0.09, P1/P2 0.055-0.075.

- [~] Lead review on rendered sheets: the darker bounded haze with capped local tint.
- [ ] Open: the retained moving-body wake needs measurement.
- [ ] Open: the loaded fog cost gate (P2/game60 render median was over budget) needs measurement.

**Waveform Studio (replaces the rejected builder UI)**

In-process, reusable (mode registry + switcher; Extruded Bubble is a second real adapter) Qt Quick Studio per the
operator's design pack; Settings > Custom opens it. Contract: `Docs/Reference/Visualizer_Studio.md`.

- [ ] Remaining mock parity.
- [ ] Real-window checks on hardware: visible window; native Settings hide/restore; exit timing via `[STUDIO] retire`
  logs; per-monitor DPI.

**Live performance and truthful evidence**

Offline GPU at the live card size: P2 7.2-7.6 ms with strands, 6.0-6.6 without (strands ~1.1 ms); logical tick budget
2.5 ms (measured history: Migration Plan section 8).

- [ ] Run all three presets under matched recorded PCM/game60 and admitted camera extremes.
- [ ] Verify the ACTUAL applied configuration, audible input and rendered features before interpreting timings
  (requested CLI settings can be overwritten by curated activation).
- [ ] Profile logical preparation, birth admission, render stages and whole-frame tails; do not reduce artistic
  reaction strength to conceal cost.
- [ ] Preset 2 with persistent strands currently exceeds the render budget (~14 ms median under game60): reduce
  repeated submission/preparation and prove tails without weakening the approved strands.
- [ ] GPU re-measure now that Floor Give has landed, then the game60 live check.

**Chosen first: the smallest contained scene and the first consumer of S3D-1/S3D-5** (it uses no population, S3D-2)

Brief and hard gates: `Docs/Future_Work/Waveform_Ribbon.md`. The detailed working checklist and visual target custody
live in `Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; reference packages under `references/` are local/operator-owned
and intentionally absent from ordinary source handoffs. The scene is world-first through the shared framed Perspective camera:
wet reflective concrete floor, waveform and full-scene night fog, with no visible horizon/sky/floor edge; the waveform
clears and softly lights the mist.

- [ ] Preset/control migration and recorded-audio calibration come only after the lab look is credible.

**WR-07/08 production candidate: finish admission**

Reaction design: Migration Plan "Current reaction model".

- [~] Lead review on rendered strips and a WebP: preserve constant history flow, no time-varying axial scaling,
  smooth curves, particles/free strands and fog clearance by the actual body.

**Full controls/editors, four-ribbon capacity and three presets: finish admission**

- [~] Lead review of rendered Studio frames: expose bend/torsion/stretch/twist/rotation and accent ranges,
  source/curve visual tuning, ribbon/gradient editors, and floor reflectivity/tint/brightness.
- [ ] Every reactive range needs actual quiet/peak consumer proof for both handles (the range audit, lead-run).
- [ ] Retain mutable authored presets and prove Save/Cancel/Restore and runtime source reachability (focused tests
  on the real SettingsDialog).

**Framing, timing and acceptance**

- [ ] Prove hidden ends/history bounds and body/head-to-visible delay across admitted sizes/camera poses.
- [ ] Replay real quiet/middle/hot/silence/hot-start windows with unshifted audio, inspect lab/production parity and
  audit range headroom.
- [ ] Close shared lifecycle/cost/dormancy gates and run `tools/visualizer_live_check.py --mode waveform_ribbon --load
  game60` before WR-09 acceptance.
- [ ] Lead visual/native judgement at WR-09 acceptance: rendered showcase WebPs and a D1 run (1B.14 harness); what
  neither can close, and has no simple test, becomes a Watchlist entry, never an open phase (operator, 11 Nov).
- [ ] The new unified atmosphere supersedes all old fog layers. Floor-column polish is secondary to continuous ground
  and response.

**Loaded render budget**

The prior run labelled fog-OFF rendered fog because preset activation overwrote its CLI values; it is a failed fog-ON
run, not an A/B.

- [ ] Repeat the corrected actual-config live check after current source/geometry changes.
- [ ] Verify packet lease/GPU envelope/culling retirement and finite-consumer parity.
- [ ] Measure current body/birth/floor cost with the rejected volume disabled. Keep CPU reduction as a test oracle; no
  readback or duplicate live preparation.
- [ ] The replacement atmosphere must earn its own measured budget.

### 7.2 Reactive Liquid / Audio Melt Pool

A heavy viscous molten body in a real concrete chamber; must never read as Neon Lake (`shockwave_grid`) water. Brief
and hard gates H01-H14: `Docs/Future_Work/Melt_Pool.md` (mock in
`references/Reactive_Liquid_Audio_Melt_Pool_Concept_and_Architecture.zip`). Uses S3D-3 (chamber), S3D-4 (surface
field), S3D-5 (reflections), S3D-2 (droplets).

**First new post-flip Vulkan-native Visualizer.** Its H01-H14 art, behaviour, camera, audio and acceptance contracts
remain binding, but the implementation need not reproduce a nonexistent OpenGL mode. N6.7 mesh shaders may produce
chamber, well, lip, floor or higher-fidelity dynamic geometry where useful, with shared native Vulkan/QRhi services;
the liquid solver can remain bounded compute/heightfield where that best meets the mock. A mesh-shader requirement
is explicitly capability-gated rather than automatically imposed on every part of the scene.

- [ ] Stages with stop points:
  - [ ] Static chamber + framed camera.
  - [ ] Connected viscous surface.
  - [ ] Musical pressure and peaks (decide whether a deformable peak mesh is needed).
  - [ ] Material/environment interplay.
  - [ ] Droplets, Settings, acceptance.

### 7.3 Concrete Rain

Rain on a night street: music changes the pavement's water, never the street. Contract:
`Docs/Future_Work/Concrete_Rain.md` (reference `references/Low and High Reactivity Concrete Rain Comparison.png`, left
low / right high). Reuses S3D-3 (street), S3D-4 (ripples), S3D-5 (wet surface, reflections), S3D-2 (impacts, crowns,
droplets).

**Second new post-flip Vulkan-native Visualizer, after Melt Pool.** Target a small, coherent, procedurally authored
wet street / crosswalk / intersection with real pavement slabs, curb and drainage geometry, asphalt relief and bounded
mid-distance architecture; N6.7 mesh/task generation where worthwhile, normal/material/reflection and compute paths
where they are better. The original comparison's camera and authored environment are identical between low/high
reactivity captures, but separately prove modest orbit freedom (up to a believable 360-degree view of the bounded
scene, not unrestricted street traversal), stable parallax and no missing geometry or reflections. Distant buildings
may use controlled bokeh/impostor treatment where the orbit remains believable. No Blender asset requirement and
no legacy OpenGL twin for Vulkan-only geometry; the existing visual/physics contracts still bind.

- [ ] Stages:
  - [ ] Wet surface and reflection.
  - [ ] Ripples and impact rings.
  - [ ] Splash crowns/droplets.
  - [ ] Music mapping (density, impact energy, ripple complexity, reflection disturbance).
  - [ ] Scene assembly and acceptance against the reference.

### 7.4 Usu Moonscape (eventual)

Long-horizon character/world vertical: `Docs/Future_Work/Usu_Moonscape.md` (Blender work:
`Docs/Future_Work/Usu_Blender_Work.md`). Not admitted until the foundations are proven; the static silhouette approval
stays a separate hard gate.

- [ ] Prove the character/world foundations S19-S27 listed there (asset bake, skinning, animation graph, secondary
  motion, felt/fuzz, world-view projection, sphere world/starscape) plus S3D-6.

## 8. Accepted Bubble: open reviews and side defect

- [ ] Side defect (agent aac773583ad93e2ab, 21 Nov, under the operator's game plus agents' runs, 77-96 % CPU): the
  live check's engine worker timed out on its first configure and the saver fell back to in-process. In the same
  conditions an OpenGL control drew 12 fps. Reproduce under a measured CPU load, then find the worker's configure
  deadline and why the in-process fallback runs so slowly. A slow but loaded machine must degrade gracefully, never
  fall to 12 fps.

- [ ] Side defect (lead, 20 Nov live control): Python OpenGL Bubble on Display 1 shows 1.44 hitches a minute (steady
  frames over 50 ms; `tools/frame_trace_cadence.py`: 6 gui_starved stalls, the worst a 88.5 ms swap-to-frame-begin
  gap with an 84.4 ms GUI wake gap). Native Vulkan Bubble's logical side shows the same worker gaps (10 over 16 ms,
  max 145.7 ms). Root cause first: attribute the GUI starvation and the worker's logical gaps (GIL-holding C calls,
  GC generation 2 at 36 ms, the usage sampler) on both paths, before any fix. Evidence:
  `.artifacts/evidence/visualizers/bubble/live_check/20261120_bubble_*`.

The operator accepted Bubble's drift, motion, ambient, direction and occlusion rules
(`Docs/Guardrails/Bubble_Temporal_Fidelity.md` section 23); do not reopen them. Bubble's performance work is the
native "Bubble GPU optimisation" box in item 8b (section 1's Order, step 3); the earlier Python-side gate here is
superseded, because the Python renderer is deleted at N5.2h.

**R-170 lead review**

Evidence: `Docs/Historical_Bugs/R-170_Bubble_Shape_Dependent_Speed_And_Aspect_Modifiers.md`.

- [~] Lead review on rendered WebPs at each card size: Bubble on a tall card, a wide card and the TV card moves and
  sizes like the canonical card, and is denser on large cards.

**Side defect (found during R-170, not fixed)**

- [ ] `_apply_bubble_collision_response` smooth mode multiplies `max_disp *= 0.72` inside the per-bubble loop, so the
  in-view correction cap compounds down the list (order-dependent). Fixing it changes canonical Bubble output, so it
  needs an explicit BTF behaviour-change decision first.

**Particle glow (merged; awaiting the lead's review)**

- [~] Lead review on the `before/` vs `after/` 4x crops and flicker strips of
  `.artifacts/evidence/visualizers/bubble/particle_glow/20261107_particle_glow/`: hot core, monotonic halo (no dark
  moat), no twinkle on drifting sub-pixel cores.

## 9. Studio for every visualizer (replaces the builders)

Operator (5 Nov): instead of a Bubble UX sweep, every visualizer (Sine retired 2026-11-05) gets a version of the
reusable Studio (`ui/studio`, mode registry + adapters) that replaces its builder. The Waveform Studio is the first
adapter and the framework bar; each mode contributes only an adapter (typed schema from the canonical registry,
truthful evaluator on its production logical/render path, fixtures, scene objects, workspaces and instruments), never
a copied shell. The former Bubble scalar-to-range idea is folded in: each adapter picks the right instrument per
control under the design pack's control policy (quiet/peak A/B, real ranges only where a true interval exists), with
unchanged serialized data unless a migration is justified. Accepted looks/behaviour (BTF, presets, timings) must not
change.

- [ ] Finish Waveform Studio acceptance first (section 7.1), then extract any remaining Waveform-shaped assumptions.
- [ ] Waveform's sensitivity (operator, 25 Nov: "does waveform have an equivalent to a sensitivity slider option?").
  Found 25 Nov: it does, as **Input Gain** (`waveform_ribbon_input_gain`, 5-200 %, default 1.0). It scales the PCM
  before every raw lane Waveform reads (`widgets/spotify_visualizer/bar_computation.py:1085-1089`). The shared
  Sensitivity, Use Recommended Sensitivity and noise-floor controls were retired for Waveform on 8 Nov because they
  sit after its fixed-scale lanes and never reached its frame (`core/settings/visualizer_mode_registry.py:479-484`).
  Input Gain is already offered in Settings' Technical group and in the Studio's Reactivity workspace, Technical
  group (`ui/studio/waveform_adapter.py:180-295`), and the presets carry their own values. Pulse Strength (`bend`)
  and Carrier Height size the response and the drawing, not what the mode hears. Left to do:
  - [ ] Lead, D1 Studio run (1B.14 harness): confirm Input Gain shows and acts live in Waveform's Studio. If it is
    buried (Technical is the last group), move it into the Reaction section's head through the spec owner
    (`core/settings/visualizer_mode_settings.py`) and label it "Sensitivity (Input Gain)". Keep the key and every
    preset's stored value. Never add a second gain stage.
- [ ] Adapters in order of authoring pain (Extruded Bubble, Bubble, Spectrum/Rainbow Ghost, Extruded Spectrum and Neon
  Lake (`shockwave_grid`) built, Spline Curve (`devcurve`) and Oscilloscope built below):
  - [ ] Neon Lake awaits the lead's acceptance review on its rendered Studio frames (evidence
    `.artifacts/evidence/visualizers/shockwave_grid/studio/20261107_studio/`, Presets 1 and 3): recorded engine
    answers like Spectrum, the shared framed camera, no wallpaper; its terrain is painted with the Studio's shared
    brush (evidence `.artifacts/evidence/studio/completion/20261106_completion/brush/`; the retired Settings editor's
    3/4 view Sun / Moon drag is now Position X / Y / Z only).
  - [ ] Extruded Spectrum awaits the lead's acceptance review on its rendered Studio frames (evidence
    `.artifacts/evidence/visualizers/extruded_spectrum/studio/20261107_studio/`); its cast-shadow rows stay out of the
    Studio while they are unavailable (`EXTRUDED_CAST_SHADOW_AVAILABLE`).
  - [ ] Spectrum awaits the lead's acceptance review on its rendered Studio frames (evidence
    `.artifacts/evidence/visualizers/spectrum/studio/20261105_studio/`).
  - [~] Lead review of the rendered Settings pages (the real SettingsDialog, off-screen), one sentence per mode:
    every mode's Settings body is now the preset row and the Studio launcher (operator 6 Nov: migrate fully once
    parity+ is proven; `tests/test_visualizer_studio_parity.py`).

**Spline Curve Studio built (6 Nov), awaiting the lead's acceptance review**

`ui/studio/devcurve_adapter.py`, registered; Spline Curve's preset row shows Open Studio and no Edit Preset. Evidence
`.artifacts/evidence/visualizers/devcurve/studio/20261107_studio/` (two presets, on Rag Doll and on Human: every
workspace with the live traces, plus the node rows).

- [~] Lead review on the rendered Studio frames: the per-layer Body / Accent / Swell traces as the way to read the
  reworked reactivity.
- [~] Lead review on the rendered Studio frames: the Layers workspace (one panel per layer).

Whether the Audio Analysis group earns its place is a decision in section 2: it is re-analysed from PCM through the
production DSP, every offered control moves Spline Curve's frame; AGC Strength and Output Lift read nothing and are
now hidden (`Docs/Reference/Visualizer_Reference.md` -> Audio Analysis controls per mode).

**Oscilloscope Studio built (6 Nov), awaiting the lead's acceptance review**

`ui/studio/oscilloscope_adapter.py`, registered. Evidence `.artifacts/evidence/oscilloscope/studio/` (two presets, on
Human and on Rag Doll: every workspace with the live traces). Recorded engine answers with the
capture history recorded by identity (binary sidecar; `Docs/Reference/Visualizer_Studio.md` section 3).

- [~] Lead review on the rendered Studio frames: Level / Afterglow / Ghosts / Flare / Drive / Tone as the way to
  read the beam.
- [~] Lead review on the rendered Studio frames: the three workspaces.

Whether the Audio Analysis group earns its place is a decision in section 2: it is re-analysed from PCM through the
production DSP, every offered control moves Flare and Drive, and Bar Count, Block Size and Input Gain also move Tone
(the trace itself is the raw capture, but the beam's reactions are not; `Docs/Reference/Visualizer_Reference.md` ->
Audio Analysis controls per mode).

**Edit Preset deleted (6 Nov)**

Contract: `Docs/Reference/Visualizer_Studio.md` section 4 (Open Studio and the confirmed Save To <Preset>).

- [~] Lead review on a render of the real SettingsDialog (off-screen): Open Studio's place in the preset row.
- [~] Lead review on a render of the real SettingsDialog with its popup patched: the Save To flow.

**Operator side requests (6 Nov, "important eventually"; queue after the running work)**

- [ ] **Waveform travel speed:** History Speed (`flow_speed`, 0.8-2.4, Flow bucket) and Pulse Speed exist but the
  operator did not find them, and there is no travel-speed reactivity (after the adaptive rework; same owner).
  - [ ] Make them findable (name / workspace / tooltip).
  - [ ] Consider a quiet -> peak History Speed under the flow rule: music pushes history faster, smoothly; knot spacing
    and the anchored ends stay continuous.
- [ ] **Studio clips are seamless loops (6 Nov), awaiting the lead's review of the wrap.** The Studio plays no
  sound: the clips are the capture stream the analysis reads, so the check is the music-reactive picture across the
  wrap. Contract `Docs/Reference/Visualizer_Studio.md` section 3 "Studio clips"; evidence
  `.artifacts/evidence/studio/clip_loop/20261106_clip_loop/`. Lead:
  - [~] Review a rendered loop WebP of each of the three clips across the wrap (end of the 13 s timeline): the
    preview should not jump, empty, or re-start its motion.
  - [ ] Rag Doll has no steady beat, so its seam is the least certain: judge it first.
  - [ ] The clips now start and end mid-song at the loop points chosen (Human and Growing Pains on their groove), not
    at the earlier quiet-to-hot windows. Whether the quiet-to-hot arc matters more than the seam is a decision in
    section 2.

**Studio chrome: Awaiting Validation**

Active material work is section 1A, item 1.7; rounded native corners remain open at item 1.9. Contract:
`Docs/Reference/Visualizer_Studio.md` (Chrome and theme). Off-screen Studio evidence cannot establish native DWM
composition; preview-overlay backing stays cheap and scene colours stay independent of chrome.

- [~] Studio run on D1 (1B.14 harness), lead review of grabbed frames: the shared semantic material on panels,
  workspace tabs, section headers, tools and instrument wells.
- [~] Same run, driven by messages: native snap/resize/maximise.
- [~] Same run on a light theme: light-theme shadows.

**Studio drag lag fixed (6 Nov), awaiting the lead's drag check**

Contract: `Docs/Reference/Visualizer_Studio.md` "Drags are batched" (per move 56 ms -> 0.07 ms on Waveform).

- [~] Studio run on D1 (1B.14 harness), drags posted by messages with `tools/studio_drag_profile.py`: the feel of
  drags (per move on the 0.07 ms scale of the evidence above).

**UI frozen after closing a Studio, recovered by itself (operator 6 Nov 21:56, Extruded Bubble, Wine Ice Acrylic):
owner found in source, awaiting a field log**

Not reproducible offscreen. The incident, its cause and the 7 Nov remedy are in `Docs/Reference/Visualizer_Studio.md`
section 4 ("Repaint at the reveal").

- [ ] Open until a field log shows a paint right after the reveal and `first Paint after the first input` within a
  frame or two (the `[STUDIO] after reveal` lines, `presence.RevealWatch`, one-shot, removed at the first input to
  Settings, name which window Windows sent the clicks to and the state at each step; "repaint since reveal: none" is
  the takes-input-but-never-repaints signature).
- [ ] Acceptance needs the operator's field log plus a fix proven on the real SettingsDialog path, never a stand-in
  only. If the lines show another owner, fix that owner from them.

**Camera reset on every edit and the exit double flicker fixed (operator 8 Nov), awaiting the lead's D1 run**

Contract: `Docs/Reference/Visualizer_Studio.md` section 4 ("One transition out" and the camera round trip).

- [~] Studio run on D1 (1B.14 harness), lead review of grabbed frames: orbit, then drag sliders (the view stays).
- [~] Same run: close the Studio by every path (one clean change to Settings, no swap).

**Per-session memory growth in the Studio (side defect, 6 Nov; the clip caches ruled out 7 Nov)**

Process memory grows about 1-3 MB per offscreen Extruded Bubble session after an ~85 MB warm-up over the first 4
sessions, but the series swings by +-70 MB run to run (main and branch alike); tracemalloc sees only ~55 kB of Python
growth per session, and the clip caches are ruled out and bounded. What grows is native (Qt Quick / GL driver heaps).

- [ ] A native heap comparison (UMDH or VMMap) across 30 sessions; bar: a trend, not run-to-run noise, before any
  fix.

**Slider drags no longer let go mid-motion (operator 6 Nov), awaiting the lead's drag check**

Contract: `Docs/Reference/Visualizer_Studio.md` "Drags are batched"; guard `tests/test_studio_drag_coalescing.py`.

- [~] Studio run on D1 (1B.14 harness), a drag with a vertical wobble posted by messages: a slider drag holds
  through a wobble on every mode.

**No automatic switch to Custom (operator 6 Nov), awaiting the lead's review**

Spec: `Docs/Reference/Visualizer_Studio.md` section 4 "Canonical save"; tests
`tests/test_studio_preset_row_and_save_to_preset.py`.

- [~] Lead review of a grabbed frame (D1 run, 1B.14 harness): the prompt's wording and buttons over a real Studio.

**Neon Lake: drag the Sun/Moon in the Studio preview**

- [ ] Retiring the Settings terrain section (6 Nov, Studio brush) removed its 3/4 view, where the Sun/Moon could be
  dragged; it is now placed with Position X/Y/Z only. Give the Studio preview a direct drag for it: the same pick
  through the production camera as the terrain brush, one undoable commit on release.

**Lead review: the Studio terrain brush**

Brush button or B in the viewport toolbar; Raise, Lower, Flatten, Water; left-drag paints, right/middle drag pans.
Evidence `.artifacts/evidence/studio/completion/20261106_completion/brush/`.

- [~] Studio run on D1 (1B.14 harness), strokes posted by messages, lead review of grabbed frames: the terrain brush
  in the Studio.

## Backlog (parked text moved out of section 1 on 21 Nov; agents are not briefed on this section; the lead promotes an item back by plan box)

### Bubble conditional optimisation gate (moved verbatim from N5.1 Bubble; the plan box keeps a pointer)

  - [ ] **N5.1 Bubble conditional optimisation gate (operator, 16 Nov; AFTER accepted native OpenGL/Vulkan parity
    and the per-pass cost check above, BEFORE N5.4 and NF):** recorded music now allows controlled, bounded
    performance-only optimisation without assuming that Bubble's calculations are the cause of any observed GPU
    utilisation. First name the measured Bubble-owned GPU pass, CPU/GIL, transfer or allocation problem and its
    baseline; if nothing significant is attributable to Bubble, record a no-change result and close the gate.
    Do NOT speculatively optimise the old Python/OpenGL renderer being retired, retune motion or response, or
    rewrite the 110-body shader on theoretical complexity alone. The relevant owner is the accepted native path,
    or the surviving Python logical simulation where that owner is independently shown to be costly.
    - [ ] **Baseline before editing:** freeze two *fully resolved* independent settings cases from the accepted
      curated **Preset 1 (Deep Sea Abyss)** and **Preset 2 (Going Down)**. Keep the existing
      `tests/fixtures/visualizer_frozen_settings/bubble.json` and its consumers intact; it has Preset 1-like
      values but must be checked against the entire current resolved profile before being called exact.
      Create an immutable versioned Preset 2 fixture, with SHA-256 for both frozen files and resolved models.
      Preserve the pre-change acceptance and commit/fixture provenance. Never resolve from the mutable Studio
      state on each run or regenerate baselines from the candidate implementation.
    - [ ] **Music/event matrix:** normally replay ALL FOUR existing ~60-second schema-2 operator takes with PCM
      histories, typed events and onsets: `nightsolong_acousticsoft1`,
      `ragdoll_quiet_intro_loud_end1`, `human_heavy1`, `anything_mixed2`, under EACH frozen preset
      (eight full replay cases, approximately 43,200 ticks at 90 Hz). THREE full, distinct recordings
      are the absolute minimum only if one is unavailable and the lead explicitly accepts a documented
      reason. Validate file SHA-256, actual span and event/onset completeness rather than assuming a filename
      proves 60 seconds. Do not use a short excerpt, older schema-1 clip or synthetic input as a substitute.
      Extend existing `tools/visualizer_replay/bubble_parity.py` narrowly for two immutable profiles while
      retaining its four default clips, per-frame hashes, first difference, and negative controls.
      Use configured Bubble-band PCM reanalysis for an audio-analysis/input optimisation, not merely the
      recorder's Sphere-profile post-DSP bands.
    - [ ] **Exact logical fidelity:** pin seed/timebase/inputs/event consumption and compare the complete
      canonical bytes at EVERY frame: published logical frame, identity-preserving physics, reactive event
      consequences, Quick snapshot and renderer payload. Zero differing frames, timestamps, values or event
      order; even a float last-bit change rejects an output-preserving optimisation. A deliberately perturbed
      float and a late/missing one-shot event must fail the gate. Byte-parity is about computed results,
      not proof of on-monitor latency. If the change affects shaders/passes, also retain N5.1's approved
      Python/native OpenGL and Vulkan/OpenGL pixel oracles; same-device raw RGBA equality where repeatable,
      otherwise the existing D12 pixel bounds without silently widening tolerance.
    - [ ] **Independent speed and reactivity proof:** paired measurements of the named CPU/GIL owner or native
      GPU pass at 2560x1440 and 4K, ambience on/off, GPU median/p90, frame latency p95/p99, resource
      lifetime/dormancy, source/snapshot age, authored ~90 Hz cadence, event-to-visible attack, loud/quiet
      elasticity and motion/ghost/tail feel on the installed system (including mixed-display load).
      Retain the 240-frame ambience-off empty-pass control below. No slowdown, timing regression or
      fidelity alteration may be excused by matching offline hashes. Lead/operator acceptance or revert;
      one bounded candidate at a time, then return to the native migration ladder. BTF §24 binds.

### Oscilloscope parity and offers (moved from N5.1 Oscilloscope; operator 21 Nov: the mode is reworked after the flip, no 1:1 polish)

- [ ] Rule (a) for the Choice offers passes 14 of 15 runs; the one miss is nightsolong `oscilloscope_audio_block_size=0`
  input 1388 (two diagonally touching 2-level pixels in the beam's edge; the lead decides whether it is a class).
  Rule (b) over the three 60 s takes fails `VULKAN_RULE_B` on isolated edge pixels of 2-6 levels (shape A: saturated
  core or glow fringe, the composite's dither over float16 bloom; shape B: one pixel held for hundreds of frames,
  human_heavy1 a (370, 251) and nightsolong b (264, 208); a root cause of B is the open question); no bound is widened.
  Rule (b) for the offers is not run: the stream player's windows do not reproduce its continuous frames for the
  Oscilloscope (a window with warm-up 299 never converges; the player or publish-history state is suspect;
  `coverage_windows.WARMUP_INPUTS["oscilloscope"]` is 0, unproved). Repro: `native_stream_player.py --deliveries
  D:/Temp/Scratch/SRPSS/fast_proof/deliveries/oscilloscope_human_heavy1_a --apis opengl --windows <one window [300, 310],
  warmup_inputs 299> --against n5_1_oscilloscope/20261121_rule_b_60s_human_heavy1_a/native_stream_player.json`.
  Evidence: `n5_1_oscilloscope/20261121_owner_offers_<take>/`, `20261121_offer_windows/`,
  `20261121_rule_b_60s_<take>_<a|b>/` (`classify_rule_b.json`, crop sheets), `20261121_layer_p_summary/summary.json`,
  `20261121_warmup_probe_*`, `20261121_windows_against_full_human_heavy1_a/`. Figures per take are in those folders.

### Native core leftovers (moved verbatim from N2.2 to N5.7c; the plan keeps one verdict line each)

- [ ] N2.2 leftovers (proved; `native/core/python/host_check.py`; lifecycle facts J1 to J4 in
  `Native_Core_N06_N07_Qt_Facts.md`):
  - [ ] The hidden host's Qt Quick target keeps its contents between frames (defect B). A hidden host with
    transparent content must clear what Qt Quick does not cover; decide that when the first such host exists.
- [ ] N2.4 leftovers (proved; `native/core/python/composite_check.py`):
  - [ ] The Glass card material on the native composite; its contract read once Glass's own native path exists.
    When the card material moves to the core, its grain takes an integer hash exact on every backend (today 2 frosted
    pixels sit 12 levels apart on Vulkan where the float hash's `fract` wraps near 1.0; accepted 14 Nov).
- [ ] N2.5 leftovers (merged 14 Nov at ABI 8; the Python renderer retires only after N2.8 passes, in the switch
  change):
  - [ ] Studio on Vulkan: Spectrum's Studio preview is the Python renderer in an OpenGL node, so `has_studio` is
    OpenGL-only (`STUDIO_PREVIEW_BACKENDS`). A native Studio preview (the same native item in the Studio's scene)
    before the flip (NF) or before Vulkan becomes a default, whichever is first.
  - [ ] The two-block split (port rule (g)'s preferred shape): a settings block packed on change and a frame block
    per frame, removing the 980 to 995 Python calls a frame on the OpenGL path; OpenGL bit-identical at the
    widened run set. With audit M3: `spectrum_settings_values` and `QuickSpectrumRenderer.render` share one
    settings owner (today the guard compares one frozen setup).
  - [ ] Audit lows: L6 the native pipeline joins the gradual warm-up (`renderer_prepared` is True at once on the
    native route, `item.py:316-323`); L8 the destruction barrier sees the native objects.
  - [ ] Side defect (R-214's sibling, low): the activation deadline's fading-out phase has no slow-but-alive
    extension (cancels the switch after 6 s; only reached at about 270 ms a frame). Same rule as R-214 when the
    owner is next touched.
  - Surface format: RGBA8 (RGBA16F gave rule (a) no gain at twice the memory; quad alignment fixed it).
    `surface_format` stays a harness-only switch.
- [ ] N2.9 leftovers (generic mode content landed 14 Nov at ABI 10: a mode is a Python simulation, its product shader
  and its spec, with no build; README "How a new mode is built", decision D12):
  - [ ] Samplers are a primitive (N4.a): Bubble's `u_ambient_texture` (binding 0, the water-decoration underlay)
    and `u_ambient_light` (binding 1, the particles' linear light), both from Bubble's offscreen ambient render.
  - [ ] The Oscilloscope's port: its Quick renderer draws an instanced beam from a storage buffer with its own scene
    target and bloom, not `oscilloscope.frag`, so its N5 port needs those primitives (or returns to the 2D shader).
- [ ] N2.8 leftovers (the first rehearsal on Display 1 passed 14 Nov for Spectrum, rule (f); the Python renderer
  retires in the switch change):
  - [ ] With no admitted mode renderable on the backend (before N2.5), the Visualizer card shows as a thin empty
    purple frame beside Spotify. Find its owner and decide: a card with nothing to draw fades out, never sits as an
    empty frame. OpenGL unchanged.
- [ ] N3.8 leftovers (the async job service landed 14 Nov at ABI 14, D9 "As built (N3.8)"; OpenGL stays in-frame by
  design):
  - [ ] D8 row 3's gate (the contention measurement under a heavy Visualizer frame, the one limit of N0.7's proof,
    D9 point 2): p99 frame time and late frames across image changes with a Visualizer running, async against
    in-frame (Vulkan only; OpenGL runs in-frame).
  - [ ] D9 point 2, consumer (b), the warm-up class: warm-up jobs run on this service, scheduled with N3.6's
    gradual warm-up (one unit per spaced frame). Transition preparation (consumer (a)) is N5.2g's.
- [ ] N5.7b leftovers (the native backdrop pyramid landed 14 Nov at ABI 16, D7 "as built (N5.7b)"):
  - [ ] The slower-device fallback (D7 point 3's minimum build interval) is not built; Vulkan follows every layer frame.
  - [ ] D7 point 7 (glass over the live Visualizer) is not built.
- [ ] N5.2a leftovers (the seven transitions landed 14 Nov at ABI 15, each drawn on Vulkan from its own product
  fragment over the background layer):
  - [ ] The first frame's pipeline build cost when a run switches program, and the 4K cost (not measured).
  - [ ] Side defect (C++): the core refusing a still for "no card" draws black silently and `content_status`
    reports no failure, so the layer's fade-out on failure would not trigger; report it and fail closed.
- [ ] N5.7c leftovers (the D1 rehearsal on Vulkan, 15 Nov, covered wallpaper, cards on all five materials, Spectrum,
  live Settings changes, a transition and a clean exit):
  - [ ] Sleep and wake through Windows' console display state (`[DISPLAY_POWER]` off, then on). The operator's power
    cycle of the TV during the run raised no display-power event and rendering carried on; a real monitor sleep
    remains unexercised.
  - [ ] `[STARTUP_REVEAL]` still says "the vulkan backend has no background renderer, so no wallpaper frame is awaited
    (D10)". Since N5.7a, Vulkan draws the native wallpaper, so the reveal should wait for its first wallpaper frame as
    OpenGL does. Fix the reveal gate, or show that the first presented frame already holds the wallpaper.

### Test-failure triage (19 Nov; folded in from Docs/testfailures20261119.md, deleted)

Investigate on real Qt before changing anything; none is proof of a production defect or licence to retune visuals,
relax thresholds or wake the dormant native worker. The runner now balances 32 historical-duration batches, two
child processes, one GPU/Qt Quick lane; read the last `batch_NN.log` node name before blaming a test. A Windows
timeout dump (`.dmp`) can hold process memory: inspect before sharing. GPU scheduling is not a cross-worktree lock.

- [ ] `tests/test_settings_input_foreground.py`: both `test_input_roles_follow_current_semantics_across_live_theme_changes`
  cases fail; an explicit `control.input.text` colour does not reach `QPalette.Text` (a Qt stylesheet precedence issue is
  plausible; one QLineEdit has its own background-only stylesheet). Prove the displayed colour for QLineEdit, QSpinBox
  and QComboBox before touching shared theme code.
- [ ] `tests/test_visualizer_card_clip_contract.py`: `glass` cases fail at 1.0x and 1.25x (Spline Curve, Neon Lake,
  Extruded Bubble); it also timed out at `extruded_bubble-glass-1.25`. Check stale QSB binaries first
  (`tools/regen_qrc.py --shaders --check`), then compare captured pixels and clip ancestry; no shader or bound change
  without that proof.
- [ ] `tests/test_neon_lake_studio.py` (timeout in `test_engine_owned_edits_change_the_engine_answers_negative_control`),
  `tests/test_studio_drag_io_churn.py` (the `shockwave_grid` case of
  `test_no_drag_instrument_writes_while_moving_and_each_release_commits_once`) and
  `tests/test_visualizer_owner_render_parity.py` (the `extruded_spectrum` worker-path case): 160 s isolated timeouts,
  not proven deadlocks; collect the last-test log, faulthandler output and a dump, isolate the parametrization, no
  broad worker rewrite, native worker stays dormant.
- [ ] `tests/unit/test_policy_compliance.py::TestThreadingPolicyCompliance::test_no_raw_threading_in_production_code`
  flags the named daemon wake-listener thread at `core/visualizer_engine/packet_mailbox.py:472`; the test file was
  absent from the transferred archive. Decide whether it is a permitted dormant mailbox mechanism or a real policy
  violation; do not exempt or refactor it from the missing test alone.

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################
Reactivity Issues:
General Issues:
###################

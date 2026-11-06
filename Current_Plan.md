# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). When an item lands, delete it: completed work lives in source control and its durable contract in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.

## 0. Order, scope and rules

**Work strictly in this order:**

1. **§7.1 Waveform Ribbon**: finish acceptance (already built; the only 3D mode in flight).
2. **§9 Studio for every visualizer** (operator, 5 Nov): replaces the deferred Bubble scalar-to-range/UX sweep.
3. **§8 Accepted-mode follow-ups**: the brief Bubble performance-parity check is operator-admitted now.
4. **SMP & Full Display (backend decision, 5 Nov: `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`):**
   Expanded Visualizer (plan 01) first, then ShittyMusicPlayer (plan 02). No Vulkan backend now: the eventual backend is
   a native render core on Qt Quick's Vulkan RHI, started only when a recorded trigger fires (full-display 4K GPU
   budget, render-thread GIL starvation, a needed capability, a platform blocker). Port-readiness rules bind all new
   GPU code from now.
5. **§6 Shared 3D architecture** and **§7 Visualizer modes** (Reactive Liquid / Melt Pool → Concrete Rain → Usu
   Moonscape, lab-first per §7.0) resume after Expanded Visualizer acceptance and its full-display measurements, under
   the port-readiness rules; if a trigger fires first, the native Vulkan core precedes them.

**Accepted baseline (not live work):** original Bubble, Extruded Bubble, Neon Lake, Oscilloscope,
Spectrum/Rainbow Ghost, Sphere, source routing, transitions and Foundry launch buttons. Reopen an accepted
area only for a concrete new defect; deferred or unadmitted work belongs in `Future_Work.md`. Historical recovery
IDs, completed gates and rejected mechanisms belong in source control or their focused historical/investigation docs,
not in this working plan.

**Rules:** one Settings/capability/CUSTOM/render/lifecycle owner and the sole Visualizer logical clock. No new
floor, capture/DSP, renderer-side simulation, timers/polling or camera-following replacement populations. Preserve
authored presets (mutable, never test-pinned), BTF, accepted timings, parallel work and strict retirement barriers.
CLI/sidecars, never environment-variable configuration. Smallest meaningful focused test per change; the isolated
chunked suite only at milestones; no build/installer unless requested. Visual work is judged on rendered pixels against
its target (`Docs/Guides/Visualizer_Visual_Tuning.md`), and any claim of "fixed" needs the failure reproduced first.

**Linux compatibility** runs as a separate operator-requested plan, `Linux_Plan.md`; it does not reorder this plan.
New platform-facing work (power, display, input) still ships a basic Linux path or an explicit inert one alongside
the Windows path, so it never needs its own Linux audit later (operator, 5 Nov).

**Agents (operator, 5-6 Nov):** at most three Opus subagents at once (two medium and one high, or three medium) plus
one additional Sonnet 5.5 high agent (6 Nov, workload), with the lead as reviewer/orchestrator.

## 4. Runtime side requests (operator, 5 Nov; run alongside the order above)

- [ ] **Slow startup (operator, 6 Nov 10:30; owners found and fixed, awaiting the operator's cold start):** the 7 s
  GUI "Feeds delivery" and the sampler's 7.2 s first sample were one `ProcessSupervisor` state lock held across a
  stuck optional child's stop/start; fixed (lock for dictionary work only, per-role lifecycle lock, a role mid-transition
  reports "not available"; `tests/test_process_supervisor_availability.py`). The engine init thread no longer waits up
  to 10 s for the OPTIONAL image_prefetch child's ready signal (10:30:10 to :20): `_start_optional_worker` queues that
  start on a ThreadManager IO worker (the required IMAGE worker keeps its inline ready wait; supervisor `shutdown()`
  aborts the wait and the engine stops the supervisor before the ThreadManager; `tests/test_optional_worker_startup.py`).
  Offline, Feeds cache delivery including the NEWS card model is 0.1-15 ms per source at 18 publishers x 40 stories, so
  the 166-240 ms `FEED_GUI_DELIVERY` lines at 10:30:40-42 are not reproduced (`_complete` excludes QML) and are treated
  as the post-block backlog on a 97-100% CPU machine. Open: confirm on the operator's next cold start with `--usage`
  that no `UI_CALLBACK` / `FEED_GUI_DELIVERY` line exceeds a frame and the first `collect_ms` is small; a prefetch
  batch asked for before the child is ready fails as "not running" (a logged `[PREFETCH]` error; no retry of that batch). Evidence
  `.artifacts/evidence/slow_startup_20261106/`.
- [x] **Bubble / Extruded Bubble "terrible performance" (operator log 10:32-10:35): our load, not the product.** That
  session ran at 97-100% system CPU from the agents' game60 checks. The lead re-ran them on the quiet machine at 6 Nov
  14:00 under game60 (`.artifacts/evidence/live_20261106/`):
  - Bubble P1: 65.9 fps, tick 1.47 ms, GIL 0.13, 3.9% late;
  - Extruded Bubble: 45-69 fps.

  Heavy load-generator runs are scheduled by the lead only. Delete this item once the operator has read it.

- [~] **Displays off -> presentation pauses entirely, resumes clean (built 5 Nov; awaiting the operator's physical
  overnight check):** `core.display_power` pauses rotation, transitions, the Visualizer (parked, capture released) and
  the clock while the console displays are off (`Docs/Architecture/Compositor_Architecture.md` → Display power).
  Injected through the real window procedure, a heavy preset went from ~142% of a core / ~10% GPU / 51 swaps/s to ~4% /
  ~0% / ~0.6 swaps/s while off, and resumed with no publish or swap hole (`.artifacts/evidence/display_power/`). Still
  needs real hardware: leave a heavy preset (Waveform Preset 1 or Neon Lake) overnight with both displays turned off
  by the power plan, then check Task Manager CPU/GPU for the saver while dark, that wake input reaches the saver, and
  the first seconds after wake (no stale frame, jump or hitch; run with `--frame-trace --usage`). Per-monitor power is
  not observable on Windows: an HDMI panel switched off at its own button that stays enumerated keeps running.
- [~] **DevCurve "more alive while keeping the flow" (second cut 6 Nov; awaiting lead review, then operator eyes):**
  loud body owns most of the drawn ceiling (big, smooth: carrier blends to its broad component instead of limiter
  triangles), kicks ride linear headroom, quiet passages take the band share's rise, swell inside the body's share,
  tick vectorised (guide §13D → DevCurve). Evidence and before/after WebPs (loud end and a quiet passage, P1/P6) in
  `.artifacts/evidence/devcurve/reactivity_20261105/` (`PROGRESS.md`). Open: the strongest preset's bass (Deep Blue)
  stays ~18% below pre-work main's loud RMS (a smooth wave cannot match a slope-limited triangle at the same slope);
  the quiet-passage evidence is one recording's cold start (9 kicks); a capped layer shows the swell less (it lives
  inside the body's share).
- [ ] **Waveform logical tick starves the render thread under game load (quiet-machine game60, 6 Nov):** Waveform
  P1/P4 logical tick median 8.5/8.3 ms (p90 14.4/14.0) holding the GIL 73-75% of the time, so render-mode time is
  16-17 ms and frames drop to 41-44 fps (Neon Lake 89 fps, Spectrum 90, Bubble 63 under the same load; Extruded Bubble
  5.9 ms / GIL 0.53 / 55 fps is the second case). Offline the Waveform dynamics alone are ~1.3 ms, so the live tick's
  cost is mostly elsewhere (capture, packet build, field/strand/spark work): profile the LIVE logical tick, then cut
  it with byte-identical output (Preset 4 bit-exact with the tag). This is the Graphics Backend Decision's "optimise
  the logical tick first" step before trigger 2 can be judged. Evidence `.artifacts/evidence/live_check_quiet_20261106/`.
  - **Extruded Bubble part (built 6 Nov; offline proven, live re-measure open):** byte-identical cuts at the owners.
    These are the contact discovery and far-pair skip, the cluster motion and layout, the cached phase terms, steer
    with no closure, the wake fast path, the snapshot records, controls re-resolved only on a read value's change,
    a strict-equality memo for the renderer parameters, struct-packed wake floats and presentation attrs resolved
    once per spec. Every published frame matches main on 4 recordings x 6 cases (24 replays, 130,926 frames, per-frame
    digests). `tests/test_extruded_bubble_logical_tick_exactness.py` compares the output against the straightforward
    forms. The offline P1 tick (`tools/eb_logical_cost_probe.py`, paired with main) went from 2.50 to 2.13 ms median
    (p90 3.25 to 2.78), about 15%. The tick is now spread thin: contacts 0.38, wakes 0.42 (NumPy flow 0.2), the
    rest of the simulation 0.62, capture 0.45. A NumPy contact sweep measured slower in situ and was dropped.
    **Live, confirmed (lead, quiet machine, game60, before/after alternated, 2 rounds, 6 Nov 14:00):**
    | Preset | fps (r1 / r2) | late frames (r1 / r2) |
    |---|---|---|
    | P1 | 44.9 -> 45.5 / 57.3 -> 63.8 | 32 -> 24.5% / 6.0 -> 2.0% |
    | P5 | 42.3 -> 52.9 / 62.9 -> 69.2 | 36 -> 8.2% / 2.3 -> 1.5% |

    Better in every pair. The live tick is only 2-4% lower (5.3-5.6 ms, GIL ~0.5): most of it lies outside the
    simulation. Evidence `.artifacts/evidence/live_20261106/` and `.artifacts/evidence/eb_logical_tick/`.
  - **Waveform, same session (main):** P1 / P4 / P7 run at 43.5 / 42.7 / 37.6 fps, tick 8.5-8.7 ms (p90 14-16), GIL
    0.75, P7 64% late frames. Waveform is now the slowest live mode. The tick cut waits for the fixed-scale rework
    (same files).
- [ ] **Frozen builds could not open a Studio (operator 6 Nov: "module QtQuick.Controls.Basic is not installed"): fixed
  in source (e5005ffa), confirm on the next build.** The QML prune removed QtQuick/Controls, Templates and Shapes, and
  the import allowlist scanned only the saver's QML, never `ui/studio/qml`. The build now keeps the Basic style's
  closure and prunes only the other Controls styles. `test_every_shipped_qml_import_survives_the_frozen_prune` walks
  every shipped import's module and DLL closure against the prune. Open: open a Studio from a fresh build.
- [ ] **Widget card surfaces: Acrylic, Glass and other materials (operator 6 Nov, near term; the lead or an Opus 5.5
  high agent, never a smaller model).** Operator: the old attempt failed with a weaker agent; done properly it is a
  lasting visual uplift. This **supersedes** the recorded rejection: `Docs/Contracts.md` (runtime cards are plain RGBA,
  "no ... card-material Loader/capture path"), `Spec.md` ("rejected runtime Glass/Acrylic card experiment"),
  `Docs/Guides/Custom_Style_Implementation.md` and `Docs/Guides/10_WIDGET_GUIDELINES.md`, which already names the way
  back: "a broader independently justified renderer architecture and a fresh acceptance plan rather than reviving the
  rejected card-only experiments". **Operator priorities, in order:** never risk damaging the compositor; stay as
  performance-neutral as possible; every result proved by captures, including during transitions. Before any code:
  1. **Read the failed-method record** in those docs and the historical bugs (R-61 Settings Glass layered-HWND
     backdrop mismatch, R-63 black flash, R-95, and grep Glass/Acrylic/backdrop/material). Write down why each
     earlier mechanism failed.
  2. **Design one scene-local Qt Quick material owner per display**, never routed through the Settings HWND or
     AccentPolicy stack. A blurred, tinted copy of the wallpaper/transition layer is made once per display and
     shared by every card through its mask: no per-card capture, blur or owner. Its update cadence is tied to the
     wallpaper/transition edges, not a timer. Cost is zero when every card is Normal (dormancy). Cards over a running
     transition stay correct. Light-theme legibility holds, with a darker legibility layer behind text, as in the
     Settings rule. The Visualizer card is included or explicitly excluded.
  3. **Materials to offer, each measured for cost:** Acrylic (blur, tint, luminosity, noise), Glass (lighter blur,
     edge highlight, slight refraction), Frosted, a Mica-like wallpaper-tinted solid (very cheap), Smoked/tinted
     translucent, and Normal (today's default).
  4. **Settings:** the Widget Theme model (memory: Normal first; Context Menu and cards inherit the Widget Theme;
     per-family overrides beat the theme baseline).
  5. **Acceptance plan:** offscreen sheets on real wallpapers per material and theme, transitions mid-flight, cost
     against the overhead baseline (control-relative), and a live check under the lead-scheduled game load. Then
     rewrite the Contracts/Spec/guide passages as a superseded decision, not an overwrite.
- [~] **Extruded Bubble: a deep red ocean preset that truly matches the mock (operator 6 Nov, not urgent) - awaiting
  operator eyes:** the mock is `Docs/Reference/Extruded_Bubble/Targets/Originals/Preset7Goal.png`. Preset 9 (Deep Red
  Ocean) is new; Preset 7 is untouched (pixel-identical, as are Presets 1-8). Shared work: **Ember Grain** (Water) breaks
  the dust clouds into burning grit, strands and sparks (0 = the previous look, verbatim). Water, shafts and ember
  colour now measure close to the mock region by region; still short: the mock's dense lit glass micro-bubbles and
  bright copper rims along the streams (ours read dimmer and sparser), embers also drift into the dark top-middle, and
  the bokeh giant appears only when the simulation brings a bubble near the lens. Details, numbers and cost:
  Extruded_Bubble/Investigation.md §72; evidence `.artifacts/evidence/extruded_bubble/deep_red_ocean_20261106/`.

## 5. Watchlist (observe during normal use; reopen only on evidence)

- [ ] **Neon Lake goal mocks (Presets 1-3, 6 Nov sixth pass, awaiting operator look):** darker mirror lake with a
  longer Moon/Sun column and no swell wash, Preset 3's mid-lake blob fixed (mirror counted swell troughs as land),
  navy Preset 1 sky with a shallower band and a soft blue stream upper left, even luminous Moon face, near ridges
  that swell and fade along their length, Preset 3 cooler sky with stronger wisps and motion 0.232/255
  (`Docs/Reference/Neon_Lake_Basin.md`, "Third" to "Sixth pass"). Still short of
  `references/NeonLakeGoalPreset1.png` / `NeonLakeGoalPreset3.png`: the high-react look (vivid line mesh over the
  lake, glowing island) is not reached on loud real music (1985_loud1: the lake barely changes; a squared
  spectrum-energy term on the ripple network was tried and did nothing visible, reverted); Preset 1's lake is still
  lighter than the mock's (p35 [28,30,65] vs [16,22,61]: bloom of the pink shore crest beside it) and its near dot
  field is coarser than the mock's; the far-shore sawtooth and the crest before the lake are mesh silhouette (a
  fine band to v 0.25 measured no gain); Preset 3 motion ideally toward 0.165. Side defect (pre-existing, found
  6 Nov): at Depth Scale 1 + Horizon Thickness 3 over dunes seen grazing, the skyline's lifted copy shows over the
  near land's own face as a broad translucent sheet (its 2% depth offset is less than the ground's recession over
  the lift); fix in the skyline vertex depth, then tighten `tests/test_neon_ridge_shape.py` to those settings. Evidence:
  `.artifacts/evidence/neon_lake/fidelity_20261105/pass6/` (triptych/, clips/*.webp, gpu_*.txt, overhead_*).

- [ ] **Neon render tests load-sensitive under parallel runs (5-6 Nov):** `test_neon_lake_renderer.py` (once, pass-5
  merge gate) and `test_neon_scene_materials.py` (once, pass-5 branch) failed under parallel load and passed alone; the
  re-run overwrote each log, so the failing test is unknown (most likely a QSG clip probe timing out). The isolated
  runner now keeps the parallel-run failure as `logs/pytest_isolated/<file>.under_load.log`; next time, read it and
  fix the probe's timeout or synchronisation rather than rerunning.
- [ ] **`test_studio_exit_every_mode.py` exited non-zero with every test passing (6 Nov, once):** "19 passed" in its
  log but a failing exit code under the 8-way gate, and that runner stopped before its summary; the immediate re-run
  passed 64/64. Looks like a native crash at interpreter teardown after the Studio tests. If it recurs, capture the
  exit code and any faulthandler output (run the file alone with `-X faulthandler`) and fix the teardown owner.
  Probably the same family as the leaked clip workers fixed in 90f65ee9 (a surviving worker held the runner's pipe).

- [ ] **4x MSAA repeat-render noise (driver, 5 Nov; was "Floor Give run-to-run noise"):** the same frame rendered
  again through a 4x scene target differs by 1 level (rarely 2-3) on a pixel or two in Waveform (more often with Floor
  Give and mist) and on ~0.7% of pixels in Neon Lake. Not renderer state: packet, uniforms, every vertex position,
  fields, fog volumes, reflection and all four depth samples are bit-identical, single-sample renders are exact
  (`test_floor_give_repeat_renders_are_renderer_deterministic`), and no barrier/finish/stream pinning changes it; the
  multisampled colour itself flips up to 3/255 per sample. Per-sample Waveform floor shading removes it there but costs
  +1.2 ms (give off) / +2.0 ms (give on) at 1080p, so it was not taken. Tests compare such renders with
  `tests/_msaa_render_noise.py`. Reopen if a driver update or another GPU shows it gone or larger.

- [ ] **Display Settings capacity (physical hotplug):** on a real monitor disconnect/return or explicit reauthoring,
  Settings' current-screen rows and selections/bindings stay coherent (focused checks pass; hidden form evidence
  `tmp/pytest_ux30_display/test_display_ui_rows_follow_to0/six_display_rows.png`).
- [ ] **R38 hover display-transfer glyphs (physical topology):** watch glyph hit/tooltip/fade and transfer on
  unequal-DPI screens and monitor unplug/return (equal-DPR pair passes; `tmp/ux30_actual_displays/receipt.json`).
- [~] **Steam Games You Follow images:** many update entries lack images. Audit URLs, redirects/statuses, cache keys,
  game IDs, fallbacks, dedupe and selection order (including artwork fetched but rejected downstream); prefer
  image-bearing updates without suppressing legitimate no-image entries; instrument attrition, compare natively with
  Feeds. A generic game cover existing is not proof an image is missing.
- [ ] **Steam artwork 404** for asset hash `9b4a68b51c5f` (23 Oct MC run, `logs/run_matrix/2026-10-23_idle_hint_shaft/`)
  and earlier `4b349d51e996` / `3f5b734df3c5`: stale metadata vs genuinely missing CDN asset, before changing lookup.
- [ ] **Monitor power/wake:** display off, > 30 s off, rapid off/on, reordered return, both selected displays absent:
  widgets keep physical assignments and CUSTOM geometry. On recurrence record timestamps, remaining screen, flavour,
  Interaction Mode and wake/exit input (history: R-79).
- [ ] **Refresh contention:** correlate FEEDS/Gmail/Reddit queue/claim/publish/retire with transition delays in a natural
  dual-display trace (fairness, no post-transition stampede, retained last-good content).
- [ ] **15 s usage-sample hitch (unexplained, not reproduced):** 31 Oct 19:28-19:33 MC run, a 95-121 ms freeze of the
  GUI, render and logical threads at every `--usage` sample (20 in 5 min, `gui_stall_stacks.log` and frame trace
  agree). Each sample took ~95 ms because the sampled tree held 7 processes / 233 threads (normal 3 / ~55, ~16-24 ms);
  the four extra descendants used the GPU (counters 17 → 70), existed from the first sample and are unidentified.
  The next MC run (19:47) and an invisible live check on current code were normal. On recurrence the sampler now
  logs `[USAGE] topology added ... name= parent= threads=` for every process entering the tree: identify them, then
  decide whether the sampler must exclude/outsource them. Not the Extruded Bubble chain fix (no processes, tick unchanged).
- [ ] **Cross-display Media shortcuts** delivered once on the other display, when exercised.
- [ ] **Music recorder** 60-second clip, signal/history, cancel and mixed-DPR UI, when recording is needed.
- [ ] **Helper breadcrumb diagnostics unavailable:** current native MC evidence logs no access to
  `C:\ProgramData\SRPSS\logs\scr_helper.log`. Inspect the helper/log-path authority before relying on that
  diagnostic route; do not hide it behind a silent local fallback. Separate from Waveform rendering.
- [ ] **Doc sweep leftovers (6 Nov, `Docs/Audits/Doc_Sweep_2026-11-06.md`):**
  1. **The guide's remembered-peak gain** (`Visualizer_Reactivity_Authoring.md` ~623 and the Waveform Migration Plan)
     is rewritten as superseded when the Waveform fixed-scale rework lands (that rework's owner does it), together with
     the "adaptive response gain" wording in `Spec.md` (~795) and `Index.md` (~100).
  2. **Stale Orthographic text** in the Waveform docs (`Waveform_Ribbon_Lab_Plan.md`, `Waveform_Ribbon_Migration_Plan.md`)
     and the Extruded Bubble docs (`Investigation.md` ~1325, `Motion_Reactivity_Viewport_Plan.md`) is fixed once their
     running agents finish.
- [ ] **Frozen release gate (operator scheduled):** Standard/Diagnostic from one compile, MC and Reddit Helper installed
  startup/exit, Settings/widgets/cache/audio and installer behaviour.
  Check installer logs and obsolete-file removal in both curated theme/preset trees. Both sources declare whole-tree
  replacement; verify Diagnostic now reads that installed theme tree too.
- [ ] **Conditional evidence only:** original Bubble tiny-radius judder (R-105) and dual-display reboot recovery
  (R-134–R-145) need new reproductions. The 90 Hz versus 60 Hz investigation stays off limits.

## 6. Shared 3D architecture (one step, before the next mode; after Expanded Visualizer, under port-readiness rules)

The architecture planned for the dropped concepts (volumetric music chamber, audio aurora/ribbon volume, photo
fracture portal, voxel morph field, holographic depth slices, procedural storm, reactive particle field,
terrain/skyline/tunnel, deformable blob sphere) is worth having; the modes were not. Build it here as shared primitives
on the existing Scene3D substrate (`Docs/Reference/Scene3D_Resources.md`): `MeshResources`, `SceneTarget`, depth-aware
OIT, probe, defocus, HDR intermediate, framed camera. Each primitive is proven on **its own offscreen harness** with
bounded, measured cost (TIME_ELAPSED, median/p90), lazy creation, zero dormant work and clean retirement; none waits for a
consumer, and none becomes a second renderer, clock or camera. Read the 3D foundation lessons in
`Docs/Reference/Transitions.md` before each slice. Order follows which mode needs them first.

- [ ] **S3D-1 Ribbon / strip primitive:** finish the reusable camera-facing width variant, shared defocus integration,
  lifecycle/admission proof and bounded cost around the existing history/ring/oriented-strip substrate. Preserve a bounded
  history SSBO, centripetal Catmull-Rom placement by continuous index, OIT translucency, multi-ribbon support and fixed
  maximum history. *Consumers: Waveform Ribbon; trails anywhere.*
- [ ] **S3D-2 Particle population extensions (G4):** inventory the existing compacted-population/sprite/streak
  helpers first; add bounded lifetimes, emitters, transient bursts, indirect draws and compute-driven arrangement
  (morphing a fixed population between shapes, from the voxel morph concept). Deterministic admission/retirement.
  *Consumers: ribbon sparks, rain droplets/crowns, melt droplets.*
- [ ] **S3D-3 Static scene geometry and materials:** authored static meshes (slabs, curbs, walls, recesses, wells,
  simple skyline/tunnel slices) with their own roughness/bevel/contact shading, built once and retained; photo-textured
  shells/planes with real depth (from the fracture portal and depth-slice concepts). *Consumers: Melt Pool chamber,
  Concrete Rain street.*
- [ ] **S3D-4 Dynamic surface field:** a bounded GPU height+velocity grid (compute or ping-pong), impulse injection,
  damping/return, a displaced mesh with normals from the actual surface, and an opt-in deformable sheet for shapes a
  heightfield cannot make (from the deformable blob sphere concept). *Consumers: Melt Pool body, Concrete Rain
  ripples/puddles.*
- [ ] **S3D-5 Reflections and wet surfaces:** a bounded planar/probe reflection for floors and pools, wet-surface and
  puddle masks over authored ground, and reflection-distortion sampling driven by a surface field. No screen-space trick
  that collapses under camera motion. *Consumers: Waveform Ribbon floor (next: §7.1), Melt Pool, Concrete Rain.*
- [ ] **S3D-6 Shared shadows (G2 / S25):** one fitted directional depth map, bounded soft PCF/bias, caster/receiver
  admission, resize/teardown/dormancy and tier cost on a real test scene (also Usu's S25; not a revival of the rejected
  Extruded cast shadows).
- [ ] **S3D-7 Reduced-resolution volumes, then lightning (G5):** prove the bounded static fog slice required by Waveform
  Ribbon first, with no audio reactivity. Then add bounded procedural bolt geometry/light and fog/smoke volumes with
  advection/reprojection and no permanent extra targets or separate cadence. *Consumers: chamber/street atmosphere.*

## 7. Visualizer modes (one at a time, in this order)

### 7.0 Method: lab first, then production

Extruded Bubble's lab (`tools/labs/extruded_bubble_lab.py`) reached the mocks long before production did; production
then closed the gap by measuring against both. Do the same for every new mode:

1. **Target first:** the mock/concept package and its low/high pair; write the mode's contract and hard gates (from its
   brief) into its focused doc before code.
2. **Lab:** `tools/labs/<mode>_lab.py` composes the target scene by hand, offscreen, from the shared primitives, with
   free knobs and no Settings/preset plumbing. Reuse the context/target and ownership contract in
   `Docs/Guides/Visualizer_Labs.md`. Iterate on rendered stills (mock | lab sheets) until it is close.
3. **Production through the shared substrate:** typed Settings, presets, the logical clock and lifecycle. Diff the lab's
   effective knobs against production's key by key; judge with **mock | lab | ours** sheets per preset, the per-mode
   capture tool (`tools/<mode>_capture.py` on recorded real music) and measurements (regional colour, on-screen size
   bands, Range audits), as in `Docs/Guides/Visualizer_Visual_Tuning.md`.
4. **The lab is a waypoint, not the goal:** keep going toward the mock; keep the lab (it costs the product nothing).
5. **Same-scene low/high proof, measured cost, dormancy and retirement** before calling any stage done, including the
   live-shape check under the calibrated game load (`tools/visualizer_live_check.py --load game60`, budgets in
   `Docs/Guides/Visualizer_Change_Checklist.md` 1C); the operator gives final sign-off.

### 7.1 Waveform Ribbon (next)

**Live rejection checklist - Awaiting native validation/operator judgement (2 Nov).** This is the single live
list of reported failures, proposed corrections and required evidence (updated 3 Nov). Tests establish mechanisms, not visual acceptance.
Work first on body/audio/accents, then grounded camera/viewport and replacement atmosphere. Binding references:
`Docs/Guides/Visualizer_Reactivity_Authoring.md` sections 13A-13C; control/design ownership in
`Docs/Reference/Waveform_Ribbon_Migration_Plan.md`; motion targets and recorded bake-off in
`Docs/Reference/Waveform_Ribbon_Lab_Plan.md` section 5.1. Keep C-primary elastic response and A's accumulated twisting.

**Reactivity milestone baseline (operator, 5 Nov): tag `waveform-baseline-2026-11-05` (= `e7a84d33`).** Pulse and
Centre Out "like night and day"; logical cadence survives heavy game load; **Preset 4 is the reference** ("let us not
lose this"). Every later dynamics change shows, on the recorded clips, that Preset 4 is unchanged against this tag
(or names the improvement for operator sign-off). Preset 4 keeps Breathing 0 (exactly the baseline dynamics).

- [ ] **Fixed-scale rework (branch `worktree-agent-ab2ce64aff1fa59c4`): REJECTED by the lead review 6 Nov, in rework.**
  Kept from it: no adaptive memory (a song replayed after ~7 min of other music responds the same: height within .01,
  roll .35 deg/s), breaks no longer re-scale what follows, an Adaptive Response toggle (off), Breathing's mean learns
  only from heard music, and the floor cleared with height. Rejected, measured on whole recordings against main
  (`tmp/waveform_review_20261106/`, gitignored: frame sheets, traces, `drift_*.txt`, the 7-song `chain7.npy`;
  scripts in `scripts/`):
  - crests clipped by the card's top edge on P4 Anything 9% -> 66%, P4 Rag Doll 2 -> 62%, P7 Anything 3 -> 66%, P7 Rag
    Doll 1 -> 54%, P1 0-3 -> 16-43% of frames: the hotter fixed calibration inflates the swells and the 3.0 lift
    pushes them out of the frame (only the floor had been measured);
  - Pulse Strength pinned near its ceiling through whole songs (3 s contrast -34..-39%); quiet stretches (Anything
    ~40-44 s) stay nearly full size; Preset 7 loud-song swing -24..-34%: the operator's "almost flat" complaint;
  - Kick Accent overlaps into a sustained ~2x spin in loud songs (16-18 against 8.5-9.5 deg/s, Preset 4 included);
  - sharper size jumps (visible-amplitude rate max 41-49 against 22-24).

  Acceptance for the rework:
  - Preset 4 visible amplitude p10/p50/p90 and its 3 s contrast are within +-10% of main (the tag).
  - Every other preset has contrast >= main, and Pulse Strength never pins.
  - Kick Accent adds at most 15% to mean roll speed (0 on Preset 4 unless proven).
  - Top clipping is no worse than main at 640x560 and 1282x1005, and the floor comes second.
  - **Operator, 6 Nov:** every reaction mode must be truly reactive (Travelling Pulse in each direction, Centre Out,
    Group Wave, Whole Swell, and the unfrozen parts of Frozen Past). See whether Breathing helps, keeping the goals.
  - **Judge with music-vs-response traces** (`tools/visualizer_replay/waveform_music_response.py`). The song's own PCM
    envelope sits above the response, with loudness -> response scatter and per-song saturation, dead, spurious and
    re-scaling measures. For travelling and frozen modes, measure only the part changing at the time (the newly
    born swell).
  - Build on the reactivity guide's real-music scale: loudness 3-17 in music, the live lane at 2.5, 0..1 absolutes
    mean only "silent", calibrate by presence on recorded music.
- [~] **Preset 7 and the other reaction modes (operator log `logse7a84d332e.zip`, Rag Doll, 5 Nov) - awaiting
  operator eyes:** no decay/breathing in soft passages, sustained passages with changes read almost flat, and a swell to
  full power as the song got QUIETER. Preset 7 is Group Wave (song 31-123 s in the log; the recorded clip is song
  70-130 s). Causes: Group Wave's set envelope was built from the long-fade field with a peak-keeping blur, so the swell
  sat at its soft bound over the visible span (median/max .98) and the whole body inflated with Pulse Strength (bass);
  and the adaptive gain's 30 s memory re-normalised a quieter passage to loud reach. Fixed: Group Wave follows the fresh
  field (as Travelling Pulse); Breathing holds the gain memory through a quieter passage only, keyed to the slow
  passage level, never beat gaps (Preset 4, Breathing 0, is bit-exact with the tag).
  Evidence and per-passage tables: `.artifacts/evidence/waveform_ribbon/reactivity_preset7/`. Open: operator review of
  Preset 7 (bodies are smaller in loud passages now that the uniform inflation is gone: sustained-loud visible
  amplitude 6.4 -> 5.4); Whole Swell (Preset 6) sits at its soft bound in all music by design (one global level;
  de-saturating it barely changed the visible body, so it was left). Pulse-visibility WIP (branch
  `worktree-agent-a470c20ffe5fe8b02`) stays parked: the operator accepted the pulse as is.
- [~] **Breathing + anchored history ends (merged b0ddc041) — awaiting operator ears/eyes:** soft passages let go
  between swells (0.7 in every preset but 4) and, since the Preset 7 fix, a quieter passage after a loud one stays
  quieter (gain memory held); the tail no longer staggers at side angles. Evidence
  `.artifacts/evidence/waveform_ribbon/breathing_20261105/`.

**Operator-selected recovery baseline (3 Nov):**
`Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.png` and its `.capture.json` preserve the exact
chosen image/settings/source. Use this material direction; do not darken the background or lower the floor's colour
level. Floor brightness is provisionally approved, not the entire floor/atmosphere. Remaining lumps and reactive
detail still need improvement. Baseline settings are applied to Preset 3; retain this reference before further work.

- [~] **Four-ribbon maximum and Preset 3 — Awaiting Validation:** the candidate now admits FOUR cards across
  authoring/runtime/clearance/accent/range paths, preserving Presets 1/2's three active identities. Validate Preset 3 against
  `references/Preset3Goal1.png` and `references/Preset3ReactivityGoalExample.png`: teal/orange contrast, readable
  lattice/twist/strands/particles, continuous wet textured floor, and the large quiet-to-peak geometric change shown.
  The explicit operator maximum overrides the first board's decorative count label; use four for Preset 3's paired
  target. Native low/high/recorded captures must reach that range without pinning or swapping scene/camera identity.
  Four-card forward migration and a first Teal/Ember Preset 3 are implemented; preserve original three-card values
  and count in old state. The recorded draft still needs visual correction: white/rope-like overlaps, repeated
  continuation, weak/dark atmosphere and a poor floor/contact strip remain rejected. Do not equate source tests,
  particle/root counts or larger amplitude with reference fidelity.
- [~] **Reaction: travelling energy pulse + four Reaction Modes (5 Nov) — awaiting operator eyes/ears:** the R1/R2
  elastic motion was rejected as fundamentally wrong (sideways bursts from the retired axial stretch; standing bends).
  Beats launch swells that travel along the waveform and amplify its OWN crests/troughs through a broad envelope
  whose slope is capped so a swell never bends a curve inward; points slide along their own curve (shape-preserving,
  rate-limited); a narrower travelling light/colour/saturation band and gathered particles show where the energy is.
  Modes: Travelling Pulse (default), Frozen Past, Whole Swell, Group Wave; flow-rule and twitch tests for every mode.
  Dense music (5 Nov probe, ragdoll loud end): the light reads as one coherent front travelling at the authored speed
  with no standing glow at the emitter; a packetised release was measured (emitter share .41 -> .40) and rejected as
  machinery without a visible gain. 8 s strips (5 Nov, `modes_long/`): Frozen Past is distinct (held crests stay
  raised when the passage quiets); Group Wave was indistinguishable, so a swell now arrives as a SET (envelope 3.5
  carrier wavelengths, light across the set, stronger forward lean) and reviewed frame by frame. Audit doc decisions 7+; evidence `.artifacts/evidence/waveform_ribbon/
  studio_20261105/modes/`.
- [~] **Particles (5 Nov candidate):** crest-weighted, distributed births in each ribbon's colour, visible
  >=1 px cores with soft halos, gentle fade; swells gather particles (Pulse Particles). Hot passages hold ~3.4x quiet.
  Pulse births only fill the cohort headroom left after the authored Spark Count, so they never mask it.
  Open: still sparser than the high-react reference (admission-limited).
- [~] **Strands: rare, 3-5 seconds TOTAL life.** Latest operator correction supersedes the proposed 30-second fade.
  Preserve the approved non-flickering look, make appearances much rarer, and use most of a configurable 3-5 second
  lifetime for a gentle tip-first fade. Reactivation restores them smoothly,
  with glow and movement/growth (retain the approximate 20% repeat extension), without abrupt respawn or pulse reset.
  Prove quiet/peak lifetime handles, tip/root fade ordering, slow decay, partial-fade reactivation and direct/reflected
  appearance. Retain birth look during travel; finite history eviction must not cut off a visible unfinished fade.
- [~] **Colour, floor and mist (5 Nov candidates):** lattice sheets (V3); wet concrete with stable soft coloured
  reflection mass (no horizon line, no flicker-prone streaks; operator prefers smeared colour to streaks); one bounded
  night medium with a slight local ribbon tint (strong Local Light can no longer wash the frame). 5 Nov vs `Preset3Goal1`:
  the grey base was the far concrete level and surface brightness, and Reflection Colour was not the hue drift (lower
  read pastel). All presets darker far surface (.2) and brightness (1.2); P3 stronger, wider-smeared reflection
  masses (lit saturation .60 vs reference .59, current .54). Consecutive frames smooth (flicker .0068 -> .0105, from
  brighter moving masses, no column popping); evidence `studio_20261105/floor4/`.
  Floor collision (operator, 5 Nov): a ribbon whose lower edge nears the floor lifts as a WHOLE (shape-exact, two-stage
  eased, up to 1.5 units); per-knot trough limits were rejected as boxy. Wide sheets (P2) still graze ~60% of ticks:
  optional Floor Give (below) lets the wet floor dent under them instead.
- [~] **Floor Give (operator, 5 Nov: "the floor can deform inwards, allowing crests") — awaiting operator eyes:**
  opt-in Floor slider (default 0 = the rigid floor, pixel-identical); P2 authored 1.0. Where a lower edge comes down
  onto the floor the wet floor yields in a soft dent (one surface for the floor's ray hit, its shading/reflection and
  the ribbons' contact), so troughs stay round and dip in instead of flattening. Perspective only. In the visible
  frame P2 reaches the floor only in the ragdoll loud end (about 49.5-52 s); P3 never does, so it is unchanged there.
  Evidence `.artifacts/evidence/waveform_ribbon/floor_deform/`; design in the Migration Plan's Floor bucket.
- [~] **Pulse Rim (operator, 5 Nov: "where the pulse is that section of the ribbon's rim can be even brighter with
  falloff") — awaiting operator eyes:** Reaction-bucket slider (0 = today's rims, pixel-identical). The rims (line and
  rim glow) brighten by the square of the published pulse field over a reference level, softly capped, sampled at
  each fragment's history x (direct and reflected light), so every Reaction Mode and both Travel Directions put it
  exactly on the pulse; the field's own smooth shape is the falloff. Evidence
  `.artifacts/evidence/waveform_ribbon/pulse_rim/`; design in the Migration Plan's Reaction bucket.
- [~] **Swells reach the Preset camera already faded (Presets 1-3) - awaiting operator eyes:** the card's camera shows
  about ±16 of the scene axis at 1282x1005 (±5 at the canonical card), but edge swells were born at `PULSE_ORIGIN` 44,
  so Head To Tail swells arrived ~2 s late at 5% strength (in-view swell p50 .13-.30 against Preset 4's 1.39). Now the
  capture and the Studio pass the camera's visible span; Travelling Pulse edge swells are born just beyond it and age
  only once seen (p50 .81-.99 at ±16; the peak visible swell after each kick is 1.7-5.6x main at every time in song).
  Preset 4 and Presets 5-7 are byte-identical. Evidence `.artifacts/evidence/waveform_ribbon/reactivity_preset7/`
  (`visibility_tag_vs_final.txt`, `kicks4_table.txt`, `sheets/*_p1..3_*`). Follow-ups (6 Nov): an edge swell now
  publishes half its level for Pulse Rim, as a Centre Out swell carries half the injection (rims at their ceiling over
  43% of the view -> 0-1%; rim pixels at 255 4.3% -> 3.6% P1, 3.2% -> 2.5% P3; Preset 4 pixel-identical); the floor
  lift reads the card's visible span plus 5 envelope sigmas within ±32 (identical at a 1282x1005 card, lower lift for
  unseen troughs at the canonical card with unchanged contact). Open: on Presets 1/3 the rim's swell-to-elsewhere
  contrast (1.11/1.17) is still below Preset 4's (1.27); the no-twitch probe's .02/.01 bounds only held because its
  swells never reached the cloth (in-view .028/.012).
- [~] **Travel Direction (operator, 5 Nov: "Travel Direction ... chosen in the studio ... an important basic need") —
  awaiting operator eyes:** Flow-bucket Choice, Right To Left (default, unchanged) or Left To Right (the mirror image:
  history enters at the left; pulses, held swells, Tilt Shift, sparks, strands and floor give follow; the world colour
  grade stays put). A live change fades out, swaps while hidden and fades back (0.6 s each way). Leads the Studio's
  Composition / Flow group. Evidence `.artifacts/evidence/waveform_ribbon/travel_direction/`; design in the Migration
  Plan's Flow bucket.
- [ ] **Dense highlights, moving colour and rim glow:** playback still lacks rewarded high-energy density and glow.
  Verify local crest/high-power colour, bright tunable rim/glow and denser highlights against actual music, including
  quiet/loud differences. Consumer reachability does not establish visible strength. Keep both range handles effective.
- [ ] **Idle and first-play blackout:** keep subtle low-energy body motion and the same ready scene on first play;
  no blackout, re-priming or scene reset. Test cold playing-before-start, silence, pause/resume and source changes.
  Idle must not emit fake musical hits or particles.
- [ ] **Dynamic Floor independence:** the operator found floor ON more responsive. Controlled full PCM now proves
  identical body/birth packets and typed events OFF/ON on four clips. Preserve the existing FFT/bus raw-reference
  policy, mode-switch/reset and stale-compute fences, plus accepted Bubble/EB behavior. Prove lively OFF response by
  ear/eye against the guide's standard; raw parity alone does not establish musical response.
- [ ] **Grounded camera, near-flat tilt and infinite view:** stable eye height above the floor, approach/retreat and
  bounded left/right orbit, waveform always in view and no escape into ugly areas. Admit a genuinely near-flat tilt
  with visible floor. Keep eye/basis, navigation, editor markers and saved pose under the shared
  owner; preserve continuous/infinite body with no exposed ends and complete Edit scaffolding. Native geometry and
  persistence tests alone cannot establish feel or beauty across moving audio, view and viewport extremes. Reproduce
  the new cut-to-black at one end and staggered entry at the opposite end against recorded wide/angled playback.
  Perspective (the only projection; Orthographic removed 5 Nov 2026) retains its positive clip contract.
  **Current visual route:** operator delegates the choice; use a restrained long-lens Perspective primary view,
  calibrated with a farther physical eye and narrow lens together. Preserve stable height,
  bounded orbit and actual camera movement; no camera-dependent actor density or audio compensation. Judge colours,
  restrained reactive twisting, floor material and full-scene mist together against the references before acceptance.
- [ ] **Floor coverage, collision, reflection and viewport changes:** after the strand slice, draw ground all the
  way through the foreground and beyond the waveform into heavy dark mist that GENTLY thickens until no horizon
  line is visible. A strip of reflections over black is rejected. **Awaiting native visual validation:** the floor now
  intersects the same physical camera's pixel rays with the infinite world plane, covering foreground/far ground
  while actor clipping remains unchanged. Focused native tests cover complete coverage,
  world coordinates, floor occlusion and capped reflection. Finish the unified atmosphere before visual judgment. Keep actors and
  physical floor contact correct, with smooth waveform collision rather than clipping. Compare identical snapshots at
  canonical/wide/tall/large sizes and both projections; inspect reflection normalization/filtering separately. Preserve
  live reflectivity/tint/brightness and the shared resize contract; no audio-gain compensation. Columns remain secondary.
  **Additional explicit rejection:** material outside the core reflection is practically invisible. Validate readable
  dim texture across the foreground with reflection and atmosphere both OFF, then under the unified night medium;
  increasing reflection alone cannot satisfy this. Current candidate restores filtered concrete/roughness and ambient light.
- [~] **Unified atmosphere (5 Nov candidate):** replacement medium in place (old banks/fringe/floor haze removed);
  darker bounded haze with capped local tint; P3 density 0.06-0.09, P1/P2 0.055-0.075. Open: retained moving-body
  wake and the loaded fog cost gate (P2/game60 render median was over budget) still need measurement.
- [ ] **Waveform Studio (replaces the rejected builder UI):** in-process, reusable (mode registry + switcher;
  Extruded Bubble is a second real adapter) Qt Quick Studio per the operator's design pack; Settings > Custom opens it; production
  framing on the real card; camera navigation; theme-token chrome; full registry coverage; Energy Pulse/Reaction Mode
  first in Reactivity; target-first response tuner. Opens on the live card's world (Fill framing; 1493e246) with the
  mock's viewport toolbar, ribbon arrows and curve tiles. Open: remaining mock parity; shipped audio (3 compact clips:
  Rag Doll, Human, Growing Pains in a lazily read assets folder, never the .rcc; agent branch in progress); real-window checks on hardware (visible window,
  native Settings hide/restore, exit timing via `[STUDIO] retire` logs, per-monitor DPI). The old builder buckets are
  already retired (Custom shows only the preset row and the Studio launcher); contract in
  `Docs/Reference/Visualizer_Studio.md`.
- [ ] **Live performance and truthful evidence:** run all three presets under matched recorded PCM/game60 and admitted
  camera extremes. Verify ACTUAL applied configuration, audible input and rendered features before interpreting
  timings. Profile logical preparation, birth admission, render stages and whole-frame tails; do not reduce artistic
  reaction strength to conceal cost. Preset 2 with persistent strands currently exceeds the render budget (~14 ms
  median under game60); reduce repeated submission/preparation and prove tails without weakening the approved strands.
  Requested CLI settings can be overwritten by curated activation.
  5 Nov: the logical tick (Waveform dynamics) was 2.2-3.2 ms median offline (live ~1.4x, budget 2.5 ms) after the
  reaction work; the along-curve surge and per-card colouring now run as rows (byte-identical packets proven per tick
  on real replays; paired -0.33 and -0.18 ms), quiet-machine median 1.32-1.35 ms all presets. Offline GPU at the
  live card size: P2 7.2-7.6 ms with strands, 6.0-6.6 without (strands ~1.1 ms). 5 Nov (late): the no-twitch/pulse
  work added no tick cost vs a21a2b0c (same machine, human_heavy: advance median 2.45 ms both) and the closed-form
  flow-rule share took it to 2.30 ms. Next: GPU re-measure once Floor Give lands, then the game60 live check.

Chosen first: the smallest contained scene and the first consumer of S3D-1/S3D-2/S3D-5. Brief and hard gates:
`Docs/Future_Work/Waveform_Ribbon.md`. The detailed working checklist and visual target custody live in
`Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; reference packages under `references/` are local/operator-owned and are
intentionally absent from normal GODZIPs.

The scene is world-first through the shared framed Perspective camera: wet reflective concrete floor,
waveform and full-scene night fog, with no visible horizon/sky/floor edge. The waveform clears and softly lights
the mist. Preset/control migration and recorded-audio calibration come only after the lab look is credible.

- [~] **WR-07/08 production candidate — finish admission:** the reaction is the travelling energy pulse with
  selectable modes (the C elastic body remains only for depth sway/torsion); A's accumulated twist and the reactive
  axial roll stay, with musical vertical response applied after the roll (roll-invariant). Preserve constant history
  flow, no time-varying axial scaling, smooth curves, particles/free strands and fog clearance by the actual body.
- [~] **Full controls/editors, four-ribbon capacity and three presets — finish admission:** primary/alternate examples now have
  candidate Preset 1/2 with the
  selected hybrid, shared framed 3D camera/navigation, technical profile, preset/Custom and Edit/Arrange feature set.
  Expose bend/torsion/stretch/twist/rotation and accent ranges, source/curve visual tuning, ribbon/gradient editors,
  and floor reflectivity/tint/brightness. Every reactive range needs actual quiet/peak consumer proof for both handles;
  retain mutable authored presets and prove Save/Cancel/Restore and runtime source reachability.
- [ ] **Framing, timing and acceptance:** prove hidden ends/history bounds and body/head-to-visible delay across admitted
  sizes/camera poses; replay real quiet/middle/hot/silence/hot-start windows with unshifted audio, inspect lab/production
  parity and audit range headroom. Close shared lifecycle/cost/dormancy gates and run
  `tools/visualizer_live_check.py --mode waveform_ribbon --load game60` before WR-09 acceptance. Operator visual/native
  judgement remains explicit where automation cannot close it. The new unified atmosphere supersedes all old fog
  layers. Floor-column polish is secondary to continuous ground and response.
- [ ] **Loaded render budget:** repeat the corrected actual-config live check after current source/geometry
  changes. The prior run labelled fog-OFF rendered fog because preset activation overwrote its CLI values; it is a
  failed fog-ON run, not an A/B. Verify packet lease/GPU envelope/culling retirement and finite-consumer parity, then
  measure current body/birth/floor cost with the rejected volume disabled. Keep CPU reduction as a test oracle; no
  readback or duplicate live preparation. Replacement atmosphere must earn its own measured budget.

### 7.2 Reactive Liquid / Audio Melt Pool

A heavy viscous molten body in a real concrete chamber; must never read as Neon Lake water. Brief and hard gates
H01–H14: `Docs/Future_Work/Melt_Pool.md` (mock in `references/Reactive_Liquid_Audio_Melt_Pool_Concept_and_Architecture.zip`).
Uses S3D-3 (chamber), S3D-4 (surface field), S3D-5 (reflections), S3D-2 (droplets).

- [ ] Stages with stop points: static chamber + framed camera → connected viscous surface → musical pressure and peaks
  (decide whether a deformable peak mesh is needed) → material/environment interplay → droplets, Settings, acceptance.

### 7.3 Concrete Rain

Rain on a night street: music changes the pavement's water, never the street. Contract: `Docs/Future_Work/Concrete_Rain.md`
(reference `references/Low and High Reactivity Concrete Rain Comparison.png`, left low / right high). Reuses S3D-3
(street), S3D-4 (ripples), S3D-5 (wet surface, reflections), S3D-2 (impacts, crowns, droplets).

- [ ] Stages: wet surface and reflection → ripples and impact rings → splash crowns/droplets → music mapping (density,
  impact energy, ripple complexity, reflection disturbance) → scene assembly and acceptance against the reference.

### 7.4 Usu Moonscape (eventual)

Long-horizon character/world vertical: `Docs/Future_Work/Usu_Moonscape.md` (Blender work:
`Docs/Future_Work/Usu_Blender_Work.md`). Needs the character/world foundations S19–S27 listed there (asset bake,
skinning, animation graph, secondary motion, felt/fuzz, world-view projection, sphere world/starscape) plus S3D-6.
Not admitted until those foundations are proven; the static silhouette approval stays a separate hard gate.

## 8. Accepted Bubble: bounded performance gate and deferred control audit

The operator has **accepted the improved original Bubble normal-drift musical authority**. That task is closed;
do not reopen it as unfinished work or restore the pre-experiment drift response. The durable approved motion,
ambient, direction and occlusion rules are in `Docs/Guardrails/Bubble_Temporal_Fidelity.md` §23. The following
performance gate is **explicitly admitted now** as a short exception to the §7 mode sequence. The separate
scalar-to-range audit remains deferred until explicitly reprioritized.

- [ ] **Bubble post-ambient performance / exact-output check (short and bounded):** inspect hidden costs from the
  shared hero big-over-small shader loop (including decoration OFF), opt-in 2048-capped ambient FBO, large glow
  sprite fill, and up-to-110-circle masking. Compare the **original handoff** to the **accepted Slice 13** under
  matched configuration for resource/performance attribution, then freeze **Slice 13 itself** as the behavioral and
  rendered-output oracle for any proposed optimization: original-vs-Slice-13 pixel bytes are *not* expected to match
  where the operator intentionally changed layering, motion or glow.
  - [ ] Measure decoration OFF, representative decoration ON, and high-density/high-glow decoration ON, using matched
    real-music replay and canonical plus extreme-wide/tall/expanded sizes, with multiple repetitions on the operator's
    native Qt Quick/OpenGL runtime. Report Bubble GPU/render p50/p95, CPU logical work, FPS/frame-pacing gaps,
    resource allocation/release and other-display contention. Check that OFF really avoids the extra FBO, sprite
    and mask draws; the modified shared hero shader still warrants timing even with decorations OFF.
  - [ ] For any **actual optimization**, compare deterministic logical packets/bit patterns exactly, and compare
    final captured RGBA bytes frame-by-frame on the **same GPU, driver, dimensions and fixed replay** when that
    capture path is deterministic. Where bit identity is unavailable, disclose why and use exact geometry/response
    checks plus recorded pixel-diff and temporal parity evidence. Do not claim byte-identical *performance*:
    throughput, GPU timing and latency require measurements.
  - [ ] If cost is material, optimize only the measured offender and repeat the parity + native performance gate;
    preserve visual quality, all approved sinking/reversed-flow presets, reactivity/latency, BTF and mutable presets.
    If no material cost is measured, **close the item without redesigning Bubble**. No generic "lean out" campaign.
  - [ ] Include the R-170 density growth: a card larger than the canonical one now draws up to 72 live heroes
    (up to 110 with draining trails) instead of its authored ~31-68, and the hero loops are per fragment.
- [ ] **R-170 operator eyes-on:** Bubble on a tall, a wide and the TV card should move and size like the canonical
  card, denser on large cards. Evidence: `Docs/Historical_Bugs/R-170_Bubble_Shape_Dependent_Speed_And_Aspect_Modifiers.md`.
- [ ] **Side defect (found during R-170, not fixed):** `_apply_bubble_collision_response` smooth mode multiplies
  `max_disp *= 0.72` inside the per-bubble loop, so the in-view correction cap compounds down the list (order-dependent).
  Fixing it changes canonical Bubble output, so it needs an explicit BTF behaviour-change decision first.
- [~] **Particle glow (merged f441bd99) — awaiting operator eyes:** emitted linear light with a hot core and a
  monotonic halo (no dark moat), no twinkle on drifting sub-pixel cores, cheaper ambient CPU pass. Evidence
  `.artifacts/evidence/bubble/particle_glow/` (`before/` vs `after/` 4x crops, flicker strips).

## 9. Studio for every visualizer (replaces the builders)

Operator (5 Nov): instead of a Bubble UX sweep, every visualizer (Sine retired 2026-11-05) gets a version of the reusable
Studio (`ui/studio`, mode registry + adapters) that replaces its builder. The Waveform Studio is the first adapter and
the framework bar; each mode contributes only an adapter (typed schema from the canonical registry, truthful evaluator
on its production logical/render path, fixtures, scene objects, workspaces and instruments), never a copied shell.
The former Bubble scalar-to-range idea is folded in: each adapter picks the right instrument per control under the
design pack's control policy (quiet/peak A/B, real ranges only where a true interval exists), with unchanged
serialized data unless a migration is justified. Accepted looks/behaviour (BTF, presets, timings) must not change.

- [ ] Finish Waveform Studio acceptance first (§7.1), then extract any remaining Waveform-shaped assumptions.
- [ ] Adapters in order of authoring pain (Extruded Bubble, Bubble, Spectrum/Rainbow Ghost, Extruded Spectrum and
  Neon Lake built, DevCurve and Oscilloscope built (below); Sphere in progress). Neon Lake (Shockwave Grid) awaits operator acceptance
  (evidence `.artifacts/evidence/neon_lake/studio/`, Presets 1 and 3): recorded engine answers like Spectrum, the
  shared framed camera, no wallpaper; its Settings body keeps the terrain brush (the one Settings control without a
  Studio home) unless a shared brush instrument is admitted. Extruded Spectrum awaits operator acceptance
  (evidence `.artifacts/evidence/extruded_spectrum/studio/`); its cast-shadow rows stay out of the Studio while
  they are unavailable (`EXTRUDED_CAST_SHADOW_AVAILABLE`). Spectrum awaits operator acceptance (evidence
  `.artifacts/evidence/spectrum/studio_20261105/`). Every mode's Settings body is now the preset row and the Studio
  launcher (operator 6 Nov: migrate fully once parity+ is proven; `tests/test_visualizer_studio_parity.py`). Operator
  look pending on the migrated Settings pages (one sentence per mode; Neon Lake's page keeps the terrain brush).
- [ ] **Neon Lake terrain brush in the Studio (the last step to "fully migrated", operator 6 Nov: "not be half in and
  half off"):** the Studio carries the heightfield, undo, Extend and Reset but has no brush instrument, so Neon Lake's
  Settings page keeps the brush section (`settings_sections=("terrain",)`). Build a shared Studio brush instrument
  that paints on the preview (raise, lower, flatten; radius, strength, falloff; the existing undo), then retire the
  Settings section with the parity test proving the brush round trip.
- [ ] **DevCurve Studio built (6 Nov), awaiting operator acceptance** (`ui/studio/devcurve_adapter.py`, registered;
  so DevCurve's preset row now shows Open Studio and no Edit Preset). Evidence `.artifacts/evidence/devcurve/studio/`
  (Deep Blue on Rag Doll, Neon Skyline on Human: every workspace with the live traces, plus the node rows). Operator
  to judge: the per-layer Body / Accent / Swell traces as the way to read the reworked reactivity, the Layers
  workspace (one panel per layer), and whether the Audio Analysis group earns its place (re-analysed from PCM through the
  production DSP, every offered control moves DevCurve's frame; AGC Strength and Output Lift read nothing and are now
  hidden: `Docs/Reference/Visualizer_Reference.md` → Audio Analysis controls per mode).
- [ ] **Oscilloscope Studio built (6 Nov), awaiting operator acceptance** (`ui/studio/oscilloscope_adapter.py`,
  registered). Evidence `.artifacts/evidence/oscilloscope/studio/` (Preset 1 Phosphor on Human, Preset 3 Lissajous on
  Rag Doll: every workspace with the live traces). Recorded engine answers with the capture history recorded by
  identity (binary sidecar; `Docs/Reference/Visualizer_Studio.md` §3). Operator to judge: Level / Afterglow / Ghosts /
  Flare / Drive / Tone as the way to read the beam, the three workspaces, and whether the Audio Analysis group earns
  its place (re-analysed from PCM through the production DSP, every offered control moves Flare and Drive, and Bar Count,
  Block Size and Input Gain also move Tone: the trace itself is the raw capture, but the beam's reactions are not;
  `Docs/Reference/Visualizer_Reference.md` → Audio Analysis controls per mode).
- [ ] **Studio replay understates Audio Analysis (found 6 Nov):** the engine-processed Studios serve the clip's *recorded*
  post-DSP lanes (`ReplayBeatEngine`; only the Spectrum family's bars are re-shaped from PCM), so editing Sensitivity,
  the floors, Gain or Block Size in the DevCurve, Oscilloscope, Bubble, Extruded Bubble or Sphere Studio (and Neon
  Lake's onset waves) changes little or nothing on screen while the live engine changes Flare, Drive, onsets and the
  curves. The audit's
  `ProductionLaneEngine` (`tools/visualizer_replay/analysis_controls_audit.py`: per-frame PCM through
  `compute_bars_from_samples`, production getters) is the candidate: promote it to `feature_replay`, use it in
  `engine_answers.extract` for modes with engine-owned analysis, and re-prove the parity tests. It takes one analysis
  block per 11 ms tick where live analyses every capture callback, so absolute levels approximate. Worker cost
  measured 6 Nov (`engine_answers.extract` with `ReplayBeatEngine` swapped for `ProductionLaneEngine`, the three
  shipped 12 s clips, frozen settings, best of two, machine at ~80% CPU from other work): DevCurve 3.8-3.9 s -> 4.2-4.3 s
  (+9-14%), Oscilloscope 2.0-2.2 s -> 2.5-2.6 s (+18-28%); the cost is no obstacle. Still to do: move the class into
  `widgets/spotify_visualizer/feature_replay.py` (the audit tool then imports it), pick it in `extract` for modes with
  engine-owned analysis (Bubble, Extruded Bubble and Sphere run their own recorded-input workers and need the same
  swap), and re-anchor the Studio parity tests, whose oracle is the production replay on recorded lanes.
- [ ] **Edit Preset deleted (6 Nov)**: every visualizer mode now has a Studio, so the preset row's Edit Preset button,
  `_open_preset_json` and its pop-up are gone (`ui/tabs/media/preset_slider.py`); curated presets are authored with
  Open Studio and the Studio's confirmed Save To <Preset> (`Docs/Reference/Visualizer_Studio.md` §4).
  `tools/flicker_test.py` keeps its own historical mock of the old row. Operator look pending: Open Studio's place in
  the preset row and the Save To flow.
- [ ] **Operator side requests (6 Nov, "important eventually"; queue after the running work):**
  - **Waveform travel speed:** History Speed (`flow_speed`, 0.8-2.4, Flow bucket) and Pulse Speed exist but the
    operator did not find them; there is no travel-speed reactivity. Make them findable (name / workspace / tooltip)
    and consider a quiet -> peak History Speed under the flow rule (music pushes history faster, smoothly; knot spacing
    and the anchored ends stay continuous). After the adaptive rework (same owner).
  - **Studio clips: 30 s small, or cleanly loopable.** Shipped clips are ~12 s, ~0.9 MB each (2.5 MB total); 30 s would
    be ~2.2 MB each but an engine-owned edit re-analyses the whole clip (~2.5x longer). A clean loop instead: loop
    points on matching musical positions with a short crossfade, and the Studio's evaluator continuing its simulation
    state across the loop (today the replay restarts at t = 0, which would jump). Choose with measurements. Operator
    (6 Nov): the clips are still 12 s; the loop must be seamless (no skip at the end).
- [ ] **Studio chrome matches Settings (6 Nov), awaiting the operator's look** (all Studios: one shell;
  `Docs/Reference/Visualizer_Studio.md` "Chrome and theme"). Frameless window with Settings' title bar and forged
  rounded edge, the theme's Glass/Acrylic material, 1.5 px one-path card borders, Settings' panel casts at half
  offset, viewport corners rounded over the scene. Hidden-render evidence `.artifacts/evidence/studio_chrome/`
  (before/after, Default Dark Acrylic, Matte Graphite Normal, Pearl Blush light Glass; 8x crops). Operator to check
  on screen: the live Glass/Acrylic composition of the Qt Quick window (first use of the AccentPolicy material on an
  alpha OpenGL window; the evidence only simulates the blur), snap/resize/maximise by hand, and the panel opacity
  floor (0.88) and shadow strength on light themes. Light-theme instrument wells (trace cards, response curve,
  transport bar) now sit on the theme's input surface (evidence `.artifacts/evidence/studio_followups/legibility/`,
  Pearl Blush and Default Dark, before/after): operator look pending. Operator (6 Nov, not urgent): the material is
  missing from most Studio areas (workspace tabs, the panels under the preview, their section headers). Apply the
  theme's Glass/Acrylic to them with a slightly darker layer behind every control so it stays legible. Controls laid
  over the preview (transport chips, aspect chips, the source notice) keep a translucent dark solid: blurring the live
  scene behind them would cost GPU time every frame and skew what the preview shows about performance.
- [ ] **Studio drag lag fixed (6 Nov), awaiting the operator's feel check.** Drags preview once per frame and
  re-show only the dragged key (Visualizer_Studio.md "Drags are batched"); evidence
  `.artifacts/evidence/studio_drag/` (per move 56 ms -> 0.07 ms on Waveform). Side defect (not measured): Bubble's,
  Extruded Bubble's and Sphere's evaluators still replay exactly in one evaluation from the fixture start, without the
  frame budget and checkpoints Waveform and the engine-answer modes now share (`ui/studio/exact_replay.py`); measure
  with `tools/studio_drag_profile.py` and move them onto `ExactReplay` where a release stalls.

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################
- When implementing SMP aim for quality, compatible and adjustable audio as on par or beyond with apps like Music Bee as possible. Do not shy away from custom work when it will improve quality/performance/ux. Gate SMP/Library/Playlist behind --smp until production ready and feature rich.
- When SMP is available (Library Widget ON) a new SMP Tab should exist in settings allowing for well organised adjustments to items related to SMP and audio processing. Use Pills and maintain high quality thematic UX. We should already have in the plans for what to hide when running an SMP only build and how to do it. 





###################
# SRPSS Documentation Index

## Start here

- **Settings editing-path persistence:** [durable ownership contract](Docs/Architecture/Settings_Bucket_Persistence_Contract.md).
  [Current Plan](Current_Plan.md) owns remaining work; accepted Settings-window, connector and Visualizer checks live in source control.

- **Names:** [Naming Reference](Docs/Reference/Naming.md) (generated, `tools/naming_reference.py --write`) maps every product name to its persisted id and every other spelling in code, with the grep hazards. Read it before searching for a mode, transition or widget by name: Neon Lake is `shockwave_grid`, Spline Curve is `devcurve`.

- **Test suite:** [Test Suite Guide](Docs/TestSuite.md) owns commands and gates (`tests/run_chunked.py --isolated [--changed]` at milestones, focused files per slice). The [23 October archived-failure triage](Docs/Audits/Archived_Test_Failure_Triage_2026-10-23.md) is historical; its stale-test reconciliation is closed.

```text
exact current source
-> Current_Plan.md
-> Spec.md / Docs/Contracts.md
-> relevant Architecture / Guardrail / Guide / Reference / Future Work document
-> tests + physical evidence for the claim
```

`Current_Plan.md` owns current work admission and sequence. `Spec.md` owns durable product/architecture. `Docs/Historical_Bugs.md` is the sole historical index; incident narratives live in `Docs/Historical_Bugs/` (older audit snapshots elsewhere are not current authority) (the legacy `Docs/Fossils/` described outdated architecture and is retired; source control keeps it). Ordinary chronology and retired decompositions belong in source control rather than the live docs tree.

## Current product and regression references

- `Current_Plan.md` contains the next actionable checklist; accepted Voxel Sphere (`sphere`) / Neon Lake (`shockwave_grid`) DSP and R151 cache/Settings work are not implementation queues.
- `Docs/Reference/Steam_Games_You_Follow.md` and `Docs/Reference/System_Volume_OSD.md` describe the current product contracts. `Future_Work.md` routes deferred feature ideas, not completed products.
- `Docs/Historical_Bugs/R-88_QtQuick_Custom_Edit_Paint_Role_Churn_And_False_Test_Oracles.md` records durable Edit paint/role and test-oracle failures; use the live source and targeted tests for any new defect.

Local-repo transition concept mock references currently used by the plan live under `tmp/mocks/` in the checked-out repository (for example `TBlockPuzzle.png`, `TVolu.png`, `TVHS.png`, `TLens.png`, `TMemb.png`, `TGroup.png`). They are visual review artifacts, not separate product authorities, and are intentionally not treated as normal GODZIP handoff payload.

## Directory roles

| Location | Role |
| --- | --- |
| `Docs/Architecture/` | durable architecture and subsystem ownership |
| `Docs/Guardrails/` | binding invariants and preflight contracts |
| `Docs/Guides/` | maintained authoring/change procedures |
| `Docs/Reference/` | current lookup/reference material and harness routing |
| `Docs/Historical_Bugs/` | permanent regression/root-cause/failed-method evidence |
| `Docs/Audits/` | dated audit/decision snapshots and design packs; evidence only, never current authority (durable rules move to their owner; a routing row may cite one as the evidence behind a rule, never as the rule) |
| `Docs/Future_Work/` | deferred concept briefs and packages routed from `Future_Work.md` |

Keep the small routing authorities at `Docs/` root: project overview, current owner map, guardrail router, Historical Bugs router and TestSuite.

For archive handoffs, `.godzip/workflow.md` defines extraction/packaging policy and `.godzip/manifest.json` inventories **only shipped files**. These are metadata, not architecture or source authority. Older optional `.godzip/CHECKPOINT_HANDOFF.md` / `.godzip/CHECKPOINT_LIVE_CHECKLIST.md` exist only if actually included; do not invent or expect them. The extracted GODZIP is the current working tree until superseded, and its source and `Current_Plan.md` outrank stale checkpoint notes. A v2 manifest is a closed inventory of the ordinary repository payload actually shipped: every shipped ordinary file has exactly one manifest record, while `.godzip/` contains metadata. Root `assets/`, `ui/assets/`, `themes/` and `references/` are intentionally hard-excluded from normal GODZIP transfer. Other Lab/Evidence material may also be intentionally omitted by scope. Absence never authorizes deletion, contract removal, recreation or fetching a different repository state; only an explicit manifest `debris` action authorizes the delete-like move into `.deleteme`.

## Current authority routing

| Need | Read |
| --- | --- |
| current work / next sequence | `Current_Plan.md` |
| Windows builds on GitHub runners (Build Runner's GitHub Remote tab): setup, process, validation, installers | `Docs/Guides/GitHub_Remote_Build.md`; `tools/github_remote_build.py`, `.github/workflows/windows-build.yml` |
| Linux: run/install/build/test how-to / live checklist and gaps / durable rules | `Docs/Guides/Linux_Guide.md` / `Linux_Plan.md` / `Docs/Guardrails/Linux_Compatibility.md`; `core/platform_paths.py` |
| R151 Steam cache publication and Settings UTC: focused Windows gate accepted, full rerun not requested | `Docs/Historical_Bugs/R-151_Steam_Cache_Windows_Publication_Race_And_Python314_Timestamps.md` |
| R149 Python 3.14 full-test failures, Steam cache WinError 32, NumPy BLAS introspection and 35-minute runtime review | `Docs/Contracts.md` |
| R134–R145 dual-display collapse, reboot-dependent recovery and pre/post performance/cache/handles investigation | `Docs/Historical_Bugs/R-134_to_R-145_Dual_Display_Reboot_Recovery.md` |
| Python 3.14 active MSVC/frozen-product gate (operator runs builds and returns logs) | `Current_Plan.md` §5; `Docs/Guides/Python314_Cutover.md` |
| durable product / architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| architecture checklist (SSOT, dormancy, lifecycle, 2D/3D consistency, performance; SMP / full-display prerequisites AC-01..03) | `Docs/Reference/Architecture_Checklist.md` (live; evidence: `Docs/Audits/Architecture_Audit_2026-11-06.md`) |
| project overview | `Docs/00_PROJECT_OVERVIEW.md` |
| runtime presentation architecture | `Docs/Architecture/Compositor_Architecture.md` |
| card surface materials (Acrylic, Glass, Frosted, Mica, Smoked; shared per-display backdrop) | `Docs/Architecture/Card_Surface_Materials.md` |
| Qt/OpenGL production floor | `Spec.md` → Accepted runtime presentation; `rendering/quick/bootstrap.py` |
| Settings theme / Acrylic / Glass / palette previews / favourites / Theme Foundry | `Docs/Architecture/Settings_Theme_Architecture.md` |
| Settings native outer-corner bleed/clipping evidence and four-case desktop gate | `Docs/Architecture/Settings_Theme_Architecture.md` → native Settings corner acceptance; `tools/settings_native_corners.py` |
| light-theme font/shadow ownership, native comparisons and accepted rendering cost | `Docs/Contracts.md` → Shadow authority; `Docs/Audits/Light_Theme_Legibility_2026-10-26.md` |
| Settings hierarchy connector rails and semantic annotations | `ui/widgets/bucket_tree.py`; `Docs/Architecture/Settings_Theme_Architecture.md` → bucket children |
| runtime Widget Theme / style override ownership | `Docs/Guides/Custom_Style_Implementation.md` |
| Settings/Widget Opacity Adjust, combined surface density and cached semantic ink | `core/settings/surface_opacity.py`; `ui/settings_surface_composition.py`; `Docs/Architecture/Settings_Theme_Architecture.md` |
| ordered visualizer controls, synchronous admission and transferred wake-handle ownership | `core/process/control_messages.py`; `Docs/Contracts.md` → Process path; `Docs/Future_Work/Native_Core_P2_Phase_Boundary_Audit.md` → L1 |
| engine worker wake pipe per platform (a handle on Windows, a name on POSIX), cadence liveness, worker-versus-in-process drawn parity | `core/visualizer_engine/wake_channel.py`; `core/visualizer_engine/engine_worker.py` → `watch_cadence_liveness`; `tools/visualizer_replay/owner_render_parity.py`; `Docs/Future_Work/Native_Core_P2_Phase_Boundary_Audit.md` → 11 Nov |
| safety / guardrail router | `Docs/Guardrails.md` |
| performance admission / reopen rules | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| wallpaper cache, speculative source batches and image-worker ownership | `Docs/Contracts.md` → Wallpaper image cache and prefetch |
| Just Make It Work pool selection, provider admission and legacy feed migration | `Docs/Reference/Wallpaper_Pool_Selection.md`; `sources/rss/pools.py` |
| Visualizer preset directory authority, repair/import/export and explicit replacement | `Docs/Reference/Visualizer_Preset_Repair.md`; `core/visualizer_preset_tree.py` |
| accepted Standard/MC Ban Image and matching-run frozen-build evidence | `Docs/Guides/Python314_Cutover.md` |
| persisted Ban Image identity, zero-ban cost and explicit Clear | `Spec.md` → Persistent Ban Image admission; `Docs/Contracts.md` → Actions / images |
| image filters, Lanczos cost, quality migration and measurements | `Docs/Reference/Image_Quality.md` |
| Build Runner cancellation and supported products | `Spec.md` → Build control and products |
| operator-only build execution / canonical Python 3.14 workers | `Current_Plan.md` §5; `Docs/Guides/Python314_Cutover.md` |
| immutable Qt resources, editable assets and automatic regeneration | `Spec.md` → Settings themes / native backdrop; `Docs/Guides/10_WIDGET_GUIDELINES.md` → asset ownership |
| presentation/cadence renderer preflight | `Docs/Guardrails/Presentation_Change_Preflight.md` |
| Visualizer presentation invariants | `Docs/Guardrails/Visualizer_Presentation.md` |
| Fullscreen controls, metadata fitting and overlay editing | `Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md` §G; `core/settings/fullscreen_overlays.py` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Bubble drawn-radius release and remaining judder evidence | `Current_Plan.md` §5; `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md`; `Docs/Reference/Harness_Index.md` |
| ordinary widget authoring | `Docs/Guides/10_WIDGET_GUIDELINES.md` |
| ordinary CUSTOM geometry, Gmail/Reddit column endpoints/reorder, Edit-only keyboard controls and reset | `Docs/Guides/Custom_Child_Geometry.md` and `Docs/Guides/Custom_Child_Placement_And_Headers.md` |
| R154 display-owner retirement callback; historical diagnostic preset collision, superseded by R155 unified runtime root | `Docs/Historical_Bugs/R-154_Quick_Display_Terminal_Callback_And_Sphere_Slot_Collision.md` |
| R156 missing Diagnostic frame-trace evidence; native Windows CLI admission and writer-failure receipts | `Docs/Guides/Qt_QML_Observability.md` |
| R155 cross-display Media shortcuts and compiled Diagnostic shared preset authority | `Docs/Guardrails/Visualizer_Presentation.md`; `Spec.md` → Media transport / Visualizer preset catalogue |
| current-screen Settings rows, physical saver/widget selection, absent-display lifecycle, monitor power/wake and saved CUSTOM replay | `Spec.md` → Visualizer display routing; `Docs/Contracts.md` → Saver display selection / Geometry / CUSTOM; `Docs/Architecture/Persisted_Input_Compatibility.md`; `Current_Plan.md` §5 |
| current source/Qt/physical proof for CUSTOM changes | `Docs/TestSuite.md` → Shared paint/Edit parity acceptance; `Current_Plan.md` for newly opened gates |
| Visualizer planar/freeform CUSTOM geometry split and hot-swap contract | `Docs/Contracts.md`; `Spec.md` → Visualizer geometry; `Docs/Guides/Visualizer_Change_Checklist.md` §7A |
| Visualizer content Rotate (every mode except Sphere), per-mode CUSTOM persistence and Scene3D output mapping | `Docs/Reference/Visualizer_Reference.md` → Scene3D content orientation; `Docs/Reference/Scene3D_Resources.md`; `widgets/spotify_visualizer/presentation_orientation.py` |
| Visualizer change preflight | `Docs/Guides/Visualizer_Change_Checklist.md` |
| Visualizer reactivity authoring | `Docs/Guides/Visualizer_Reactivity_Authoring.md` |
| Visualizer visual tuning: offscreen preview, side-by-side sheets, measurement, pixel-identity proof | `Docs/Guides/Visualizer_Visual_Tuning.md` |
| Shared lab context/target, production-host input experiments, bounded capture and retirement | `Docs/Guides/Visualizer_Labs.md`; `tools/labs/render_target.py` |
| Shared ribbon history/width frames, oriented GPU prototype and open admission gates | `Docs/Reference/Ribbon_Path.md`; `core/ribbon_geometry.py` |
| Shared planar reflection ownership, mirrored camera and rough receiver filtering | `Docs/Reference/Scene3D_Resources.md` → Planar reflections; `rendering/quick/scene3d/reflection.py` |
| Waveform Ribbon lab, current visual gaps (§0B), preferred checkpoint, mock custody and generated floor maps | `Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; `tools/labs/waveform_ribbon_targets.py`; `Docs/Future_Work/Waveform_Ribbon.md` |
| Waveform Ribbon rejected mist image, failure analysis and full-scene night-fog replacement proposals | `Docs/Reference/Waveform_Ribbon_Mist_Failure_and_Replacement.md` |
| Waveform Ribbon latest Preset 3/four-ribbon, paired peak range and unified mist/floor targets | `Docs/Reference/Waveform_Ribbon_Lab_Plan.md` section 1.1; `references/Preset3Goal1.png`; `references/Preset3ReactivityGoalExample.png`; `references/Mist Goal.png` |
| Waveform unified atmosphere and infinite floor coverage contracts | `Docs/Reference/Waveform_Ribbon_Migration_Plan.md` Mist / Floor / Camera; `rendering/gl_programs/waveform_atmosphere.py` |
| Waveform four-ribbon Teal/Ember candidate, long-lens primary view and gentle reactivatable strand EoL | `Docs/Reference/Waveform_Ribbon_Migration_Plan.md`; `presets/visualizer_modes/waveform_ribbon/preset_3_teal_and_ember.json`; `core/ribbon_strand_cohorts.py` |
| Waveform operator-selected recovery image, brightness constraints and reproducible material settings | `Docs/Reference/Waveform_Ribbon_Migration_Plan.md` §6; `Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.png`; companion `.capture.json` |
| Waveform Ribbon recorded-audio motion bake-off and full Visualizer controls/migration | `Docs/Reference/Waveform_Ribbon_Lab_Plan.md` §5.1; `tools/labs/waveform_ribbon_music_bakeoff.py`; `Docs/Reference/Waveform_Ribbon_Migration_Plan.md` |
| Shared retained Waveform scene, neutral appearance inputs and shaders | `rendering/quick/scene3d/waveform.py`; `core/waveform_ribbon_scene.py`; `core/ribbon_style.py`; `rendering/gl_programs/waveform_ribbon.py` |
| Waveform reaction model: travelling energy pulse, Reaction Modes, flow rule, fixed response (Adaptive Response opt-in), Kick Accent, whole-ribbon floor lift (floor first), no-twitch rules, Dynamic Zoom | `Docs/Reference/Waveform_Ribbon_Migration_Plan.md` → Current reaction model; `core/waveform_ribbon_dynamics.py`; `Docs/TestSuite.md` → Waveform reaction gates |
| Visualizer Studio: adapter contract, framings, preview Rotate, Save / Save Camera, canonical preset writes and restore guarantee | `Docs/Reference/Visualizer_Studio.md`; `ui/studio/registry.py`; `ui/studio/adapter.py` |
| Waveform production mode, canonical controls/editors, event sparks and recorded PCM capture | `core/waveform_ribbon_dynamics.py`; `core/ribbon_bursts.py`; `core/ribbon_strand_cohorts.py`; `widgets/spotify_visualizer/waveform_ribbon_parameters.py`; `ui/widgets/waveform_ribbon_editors.py`; `tools/waveform_ribbon_capture.py` |
| Visualizer current reference | `Docs/Reference/Visualizer_Reference.md` |
| Visualizer engine worker: the default on every platform (Linux source-level only, never run: `Linux_Plan.md` Phase 4), explicit process choices, frame capacity/ABI, child diagnostic log and final STOP reports | `Docs/Future_Work/Native_Core_P2_Engine_Design.md`; `Docs/Future_Work/Native_Core_P2_Phase_Boundary_Audit.md` → resolution; `Current_Plan.md` §1 |
| Visualizer Previous/Next preset glyphs and default selection | `Docs/Reference/Visualizer_Reference.md` → Preset navigation glyphs |
| Visualizer hover display transfer, native glyph admission and existing CUSTOM transaction | `Docs/Reference/Visualizer_Reference.md` → Preset navigation glyphs; `Current_Plan.md` → R38 |
| Visualizer Settings declarations, consumer/authoring boundaries, validation, availability and bespoke editors | `core/settings/visualizer_mode_settings.py`; `Docs/Reference/Visualizer_Reference.md` → Settings declarations; `Docs/Guides/Visualizer_Change_Checklist.md` |
| Expanded Visualizer (full display) implementation plan: phase ladder, gates, 4K budgets, backend triggers | `Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md` (live; prerequisites in `Docs/Reference/Architecture_Checklist.md`) |
| ShittyMusicPlayer implementation plan: `--smp` gate, prerequisite phases, SMP Settings tab with pills, audio quality bar, icon/artwork rules, full rearrangement | `Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md` (live); `Future_Work.md` §2.5 (only promoted work enters `Current_Plan.md`; the 5 Nov plans zip was never tracked and is superseded by these files) |
| Neon Lake (`shockwave_grid`) framing, terrain authoring, editable experiments, Custom selection migration and renderer | `Docs/Reference/Neon_Lake_Basin.md`; `Docs/Reference/Naming.md` (its `shockwave_grid_*`, `shockwave_*` and `neon_*` owners); concrete recurrences only enter `Current_Plan.md` §5 |
| Spline Curve (`devcurve`; classes are named `DevCurve*`): solver, frame runtime, renderer, Studio and Settings | `Docs/Reference/Visualizer_Reference.md`; `widgets/spotify_visualizer/devcurve_runtime.py`, `widgets/spotify_visualizer/devcurve_frame_runtime.py`, `ui/studio/devcurve_adapter.py`; owner map in `Docs/Reference/Naming.md` |
| Oscilloscope (`oscilloscope`; keys `osc_` and `oscilloscope_`): captured-PCM line, reaction, Studio and Settings | `Docs/Reference/Visualizer_Reference.md`; `widgets/spotify_visualizer/oscilloscope_frame_runtime.py`, `ui/studio/oscilloscope_adapter.py`; owner map in `Docs/Reference/Naming.md` |
| transitions and material surfaces (accepted work; new graphics decomposition) | `Docs/Reference/Transitions.md`; `Docs/Guides/Transition_Change_Checklist.md` |
| Accepted original Bubble Settings/replay and musical response reference | `Docs/Reference/Visualizer_Reference.md` → Settings declarations; `Docs/Reference/Harness_Index.md`; `Spec.md` |
| Original Bubble two-node gradient, named recipe compatibility and gesture undo | `Docs/Reference/Bubble_Gradient.md`; `core/gradient_geometry.py`; `ui/widgets/visual_controls.py` |
| EB accepted baseline, targets and historical recovery | `Docs/Reference/Extruded_Bubble/README.md`; `Current_Plan.md` §0 |
| EB drift/stream, framed viewport, Perspective camera, pause/resume and rays | `Docs/Reference/Extruded_Bubble/Motion_Reactivity_Viewport_Plan.md` (accepted reference; reopen only on a concrete defect) |
| EB R42 surface retirement, birth clustering and Bounce next repair; glyph native test audit | retired EB-R42 history; `Docs/Reference/R42_EB_Surface_Birth_Glyph_Test_Audit.md` |
| EB architectural work order and visual acceptance falsifiers | retired recovery sequence (see `git show 9f1f1434:Current_Plan.md`); [`Docs/Reference/Extruded_Bubble/Acceptance_Runbook.md`](Docs/Reference/Extruded_Bubble/Acceptance_Runbook.md) |
| EB viewport-sized near-shell blur/fade, off-axis continuity and native diagnostic evidence | historical G11 evidence; `rendering/gl_programs/extruded_bubble_program.py` → `EB_LENS_GLSL`; `Docs/TestSuite.md` → Extruded Bubble recovery gates |
| EB lighting physical authority, independent Lighting Coverage BEAM/SCENE, Beam Width and persistent SCENE emission clustering | [`Docs/Reference/Extruded_Bubble/Lighting_Authority_Repair.md`](Docs/Reference/Extruded_Bubble/Lighting_Authority_Repair.md); historical recovery evidence, not a live queue |
| EB **22 Oct additional source-level reproductions**, per-mode exit leakage, emission-mode transitions, slider-endpoint coupling, GPU visibility and disabled-ray cost hypothesis | [`Docs/Reference/Extruded_Bubble/Additional_Source_Audit_2026-10-22.md`](Docs/Reference/Extruded_Bubble/Additional_Source_Audit_2026-10-22.md); historical source findings, not a current task queue |
| Extruded Bubble recorded-audio forensics, paired 2D response, count/emission candidates and fixed-world geometry | `Docs/Reference/Extruded_Bubble/Investigation.md` §6–18; `Docs/Reference/Harness_Index.md` → Extruded Bubble forensic tools |
| EB idle visibility versus 2D, saved-pose rejection, class-rest transfer and native layer evidence | `Docs/Reference/Extruded_Bubble/Investigation.md` §41/§49/§52/§57; historical recovery evidence |
| EB BEAM restoration candidate, SCENE-only experiments and remaining parity/attenuation gaps | `Docs/Reference/Extruded_Bubble/Lighting_Authority_Repair.md`; `Docs/Reference/Extruded_Bubble/Investigation.md` §63; historical candidate, not current scope |
| EB finite-world camera bounds shared by flight, saved poses and all special 3D controls | `core/settings/extruded_bubble_camera.py`; `Docs/Reference/Extruded_Bubble/Investigation.md` §51; historical G03/G07 evidence |
| Reusable framed 3D internal camera, held-left orbit and per-mode view-pose contract | `Docs/Reference/Visualizer_Reference.md` → Live view pose; `Docs/Reference/Scene3D_Resources.md` → Shared framed-camera |
| Framed 3D control hints, hover visit, global glyph/hint preferences and RCC artwork | `Docs/Reference/Visualizer_Reference.md` → framed hints; `ui/assets/widgets/visualizer/control_hint.png` |
| Framed preset starting views, Save Preset As and camera validation | `Docs/Reference/Visualizer_Reference.md` → Framed preset starting views; `core/settings/visualizer_view_orbit.py` |
| Preset Repair control coverage, migrations, atomic replacement and safe Undo | `Docs/Reference/Visualizer_Preset_Repair.md`; `tools/visualizer_preset_repair.py` |
| Shared G1 attachments, G3A transparent layering, G2 shadow-map and selective G3B optics proof | `Docs/Reference/Scene3D_Resources.md`; `Current_Plan.md` §6 |
| Usu character authoring source and static review renders | local checkout `assets/usu/README.md` (excluded from normal Godzip) |
| shared 3D resource ownership, DSA, immutable storage and state restoration | `Docs/Reference/Scene3D_Resources.md` |
| runtime audit 2026-09-22 outcomes and rejected ideas (closed) | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| FEEDS architecture, terminal failure/queued settlement, bundle admission and open physical acceptance | `Docs/Reference/Feeds.md`; `Docs/TestSuite.md` → FEEDS |
| defaults | `Docs/Guides/Defaults_Guide.md` |
| Guided Setup / Quick Start / Settings Layout tab (Arrange, Layout Slots, Reset Widget Layouts) | `Docs/Reference/Guided_Setup.md` (open physical acceptance at its end) |
| logging / bounded MC CLI capture / Qt-QML observability | `Docs/Guides/Logging_Guide.md` + `Docs/Guides/Qt_QML_Observability.md` |
| documentation maintenance | `Docs/Guides/Documentation_Maintenance.md` |
| test inventory / acceptance authority | `Docs/TestSuite.md` |
| durable test authoring / mutable-authority hygiene | `Docs/Guides/Test_Durability.md` |
| harness commands | `Docs/Reference/Harness_Index.md` |
| release/README animated media (`tools/release_media.py`, ignored output) | `Docs/Reference/Release_Media.md` |
| ordinary widget resize/stack capture harness (maintained tooling, never imported by production) | `Docs/Guides/Ordinary_Widget_Resize_Capture.md` |
| Theme Sorter Foundry (optional standalone theme triage tool) | `Docs/Guides/Theme_Sorter_Foundry.md` |
| delegating work to Codex and auditing it | `Docs/Guides/Codex_Delegation.md` |
| GODZIP Foundry quick-launch Foundries / GUI tools | `Docs/Reference/Harness_Index.md` → GODZIP Foundry operator commands |
| friendly 60-second music capture / full waveform replay | `tools/music_recorder.py`; `Docs/Reference/Harness_Index.md` |
| benchmarks: cost baselines, the lifecycle contract, reading results, expected results | `Docs/Reference/Benchmarks.md` |
| bounded self-terminating RUN / repeated startup-teardown acceptance | `Docs/Reference/Harness_Index.md` → Bounded self-terminating RUN sessions (`main_mc.py`, `tools/run_matrix.py`, `--exit-after`) |
| Steam source/auth/privacy contract | `Docs/Reference/Steam_Source_Contracts.md` |
| Friend Pulse current contract | `Docs/Reference/Steam_Friend_Pulse.md` |
| System Stats current contract | `Docs/Reference/System_Stats_Widget.md` |
| Voxel Sphere (`sphere`) standard-mode contract, analysis-only DSP and accepted horizon shaped like Neon Lake's (`shockwave_grid`) | `Docs/Reference/Sphere_Visualizer.md`; `Docs/Historical_Bugs/R-150_Sphere_Analysis_Only_Shockwave_Shaper_Audit.md` |
| historical bug / rejected-method routing | `Docs/Historical_Bugs.md` (sole index) |
| compatibility / schema-migration bridges | `Docs/Architecture/Persisted_Input_Compatibility.md` |
| deferred features / long-horizon graphics and Visualizer ideas | `Future_Work.md` |
| graphics backend decision (Vulkan vs SMP & Full Display), triggers and port-readiness rules for new GPU code | `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md` |
| Usu Moonscape vertical: behaviour, reactivity, required 3D architecture (S19–S27), asset gates | `Docs/Future_Work/Usu_Moonscape.md` |
| Usu Blender work: previewing Usu, rig/clip fixes, missing clips, bake/export preparation | `Docs/Future_Work/Usu_Blender_Work.md` |
| Games You Follow product/source/CUSTOM | `Docs/Reference/Steam_Games_You_Follow.md` |
| system master-volume OSD | `Docs/Reference/System_Volume_OSD.md` |

## Performance/freshness baseline

CHK26 / repository commit `985b9d5306` is the current operator-accepted GOLDEN performance/freshness baseline. CHK23 is the immediately prior GOLDEN rollback/bisect landmark and CHK15 / `ce07b9919f` is the older pre-retained-background baseline.

The generic headroom campaign is closed. CHK27-CHK29 retained useful `--frame-trace` observability and proved that the largest remaining scheduler-shaped residuals are Qt frame/render-phase ownership or small distributed Bubble/driver costs rather than another obvious local hotspot. Reopen performance work only from a concrete reproduced symptom. The complete chronology and false trails live in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`.

## Visualizer read order

For a new mode or meaningful reactivity change, read:

1. `Docs/Reference/Naming.md` (which product name is which id, and every owner's spelling);
2. `Docs/Guides/Visualizer_Reactivity_Authoring.md`;
3. `Docs/Guides/Visualizer_Change_Checklist.md`;
4. `Docs/Guardrails/Visualizer_Presentation.md`;
5. `Docs/Guardrails/Bubble_Temporal_Fidelity.md` when Bubble/shared timing could be affected;
6. `Docs/Reference/Visualizer_Reference.md`;
7. relevant Historical Bug negative controls.

Any production change that touches Bubble reaction/timing requires active-music physical acceptance; idle-only evidence is not sufficient.

## Documentation hygiene

Do not add another inventory/changelog/history layer. Closed decompositions are consolidated into current contracts or Historical Bugs and then deleted from the live docs tree. Extensible catalogs are registry-owned: live docs and harnesses say "every registered mode" / "canonical transition registry" rather than freezing today's membership count into prose. Persisted-input compatibility bridges are documented as architecture in `Docs/Architecture/Persisted_Input_Compatibility.md` (user-data protection, horizon-gated — not a backlog); caller-dead residue is deleted outright, not tracked in a register. When paths move, update this router and all live cross-references in the same change.


- [2026-10-23 Test Oracle Repair: no authored preset/Settings value pins](Docs/Audits/Test_Oracle_Repair_2026-10-23.md) (cross-linked to [Test Durability](Docs/Guides/Test_Durability.md) and [Test Suite](Docs/TestSuite.md)); preserve all unresolved native and visual gates.

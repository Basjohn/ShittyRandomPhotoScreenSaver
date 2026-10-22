# SRPSS Documentation Index

## Start here

```text
exact current source
-> Current_Plan.md
-> Spec.md / Docs/Contracts.md
-> relevant Architecture / Guardrail / Guide / Reference / Future Work document
-> tests + physical evidence for the claim
```

`Current_Plan.md` owns current work admission and sequence. `Spec.md` owns durable product/architecture. `Docs/Historical_Bugs.md` is the sole historical index; incident narratives live in `Docs/Historical_Bugs/` (older audit snapshots elsewhere are not current authority) (the legacy `Docs/Fossils/` described outdated architecture and is retired; source control keeps it). Ordinary chronology and retired decompositions belong in source control rather than the live docs tree.

## Current product and regression references

- `Current_Plan.md` contains the next actionable checklist; accepted Sphere/Shockwave DSP and R151 cache/Settings work are not implementation queues.
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

Keep the small routing authorities at `Docs/` root: project overview, current owner map, guardrail router, Historical Bugs router and TestSuite.

For archive handoffs, `.godzip/workflow.md` defines extraction/packaging policy and `.godzip/manifest.json` inventories **only shipped files**. These are metadata, not architecture or source authority. Older optional `.godzip/CHECKPOINT_HANDOFF.md` / `.godzip/CHECKPOINT_LIVE_CHECKLIST.md` exist only if actually included; do not invent or expect them. The extracted GODZIP is the current working tree until superseded, and its source and `Current_Plan.md` outrank stale checkpoint notes. The archive may intentionally omit Lab/Evidence/assets; absence does not authorize removing their contracts, recreating them, or fetching a different repository state.

## Current authority routing

| Need | Read |
| --- | --- |
| current work / next sequence | `Current_Plan.md` |
| R151 Steam cache publication and Settings UTC: **106 focused Windows tests accepted**, full rerun not requested | `Docs/Historical_Bugs/R-151_Steam_Cache_Windows_Publication_Race_And_Python314_Timestamps.md` |
| R149 Python 3.14 full-test failures, Steam cache WinError 32, NumPy BLAS introspection and 35-minute runtime review | `Docs/Contracts.md` |
| R134–R145 dual-display collapse, reboot-dependent recovery and pre/post performance/cache/handles investigation | `Docs/Historical_Bugs/R-134_to_R-145_Dual_Display_Reboot_Recovery.md` |
| Python 3.14 active MSVC/frozen-product gate (operator runs builds and returns logs) | `Current_Plan.md` §5; `Docs/Guides/Python314_Cutover.md` |
| durable product / architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| project overview | `Docs/00_PROJECT_OVERVIEW.md` |
| runtime presentation architecture | `Docs/Architecture/Compositor_Architecture.md` |
| Qt/OpenGL production floor | `Spec.md` → Accepted runtime presentation; `rendering/quick/bootstrap.py` |
| Settings theme / Acrylic / Glass / Theme Foundry | `Docs/Architecture/Settings_Theme_Architecture.md` |
| Settings hierarchy connector rails and semantic annotations | `ui/widgets/bucket_tree.py`; `Docs/Architecture/Settings_Theme_Architecture.md` → bucket children |
| runtime Widget Theme / style override ownership | `Docs/Guides/Custom_Style_Implementation.md` |
| safety / guardrail router | `Docs/Guardrails.md` |
| performance admission / reopen rules | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| wallpaper cache, speculative source batches and image-worker ownership | `Docs/Contracts.md` → Wallpaper image cache and prefetch |
| accepted Standard/MC Ban Image and matching-run frozen-build evidence | `Docs/Guides/Python314_Cutover.md` |
| persisted Ban Image identity, zero-ban cost and explicit Clear | `Spec.md` → Persistent Ban Image admission; `Docs/Contracts.md` → Actions / images |
| image filters, Lanczos cost, quality migration and measurements | `Docs/Reference/Image_Quality.md` |
| Build Runner cancellation and supported products | `Spec.md` → Build control and products |
| operator-only build execution / canonical Python 3.14 workers | `Current_Plan.md` §5; `Docs/Guides/Python314_Cutover.md` |
| immutable Qt resources, editable assets and automatic regeneration | `Spec.md` → Settings themes / native backdrop; `Docs/Guides/10_WIDGET_GUIDELINES.md` → asset ownership |
| presentation/cadence renderer preflight | `Docs/Guardrails/Presentation_Change_Preflight.md` |
| Visualizer presentation invariants | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Bubble drawn-radius release and remaining judder evidence | `Current_Plan.md` §5; `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md`; `Docs/Reference/Harness_Index.md` |
| ordinary widget authoring | `Docs/Guides/10_WIDGET_GUIDELINES.md` |
| ordinary CUSTOM geometry, Edit-only keyboard controls and reset | `Docs/Guides/Custom_Child_Geometry.md` and `Docs/Guides/Custom_Child_Placement_And_Headers.md` |
| R154 display-owner retirement callback; historical diagnostic preset collision, superseded by R155 unified runtime root | `Docs/Historical_Bugs/R-154_Quick_Display_Terminal_Callback_And_Sphere_Slot_Collision.md` |
| R156 missing Diagnostic frame-trace evidence; native Windows CLI admission and writer-failure receipts | `Docs/Guides/Qt_QML_Observability.md`; `Current_Plan.md` §5 |
| R155 cross-display Media shortcuts and compiled Diagnostic shared preset authority | `Docs/Guardrails/Visualizer_Presentation.md`; `Spec.md` → Media transport / Visualizer preset catalogue |
| physical saver/widget selection, absent-display lifecycle, monitor power/wake and saved CUSTOM replay | `Spec.md` → Visualizer display routing; `Docs/Contracts.md` → Geometry / CUSTOM; `Docs/Architecture/Persisted_Input_Compatibility.md`; `Current_Plan.md` §5 |
| current source/Qt/physical proof for CUSTOM changes | `Docs/TestSuite.md` → Shared paint/Edit parity acceptance; `Current_Plan.md` for newly opened gates |
| Visualizer planar/freeform CUSTOM geometry split and hot-swap contract | `Docs/Contracts.md`; `Spec.md` → Visualizer geometry; `Docs/Guides/Visualizer_Change_Checklist.md` §7A |
| Visualizer change preflight | `Docs/Guides/Visualizer_Change_Checklist.md` |
| Visualizer reactivity authoring | `Docs/Guides/Visualizer_Reactivity_Authoring.md` |
| Visualizer current reference | `Docs/Reference/Visualizer_Reference.md` |
| Visualizer Settings declarations, consumer/authoring boundaries, validation, availability and bespoke editors | `core/settings/visualizer_mode_settings.py`; `Docs/Reference/Visualizer_Reference.md` → Settings declarations; `Docs/Guides/Visualizer_Change_Checklist.md` |
| Future Visualizer concepts, feasibility notes and low/high-react mocks | `Docs/Future_Work/Additional_Future_Transitions_Package.zip` (concept catalogue; only promoted work enters `Current_Plan.md`) |
| Neon Lake Basin framing, terrain authoring, editable experiments, Custom selection migration and renderer | `Docs/Reference/Neon_Lake_Basin.md`; `Current_Plan.md` §2A / §3 / §5 |
| transitions and material surfaces (accepted work; new graphics decomposition) | `Docs/Reference/Transitions.md`, `Docs/Guides/Transition_Change_Checklist.md` and `Current_Plan.md` §4 |
| Accepted original Bubble Settings/replay and musical response reference | `Docs/Reference/Visualizer_Reference.md` → Settings declarations; `Docs/Reference/Harness_Index.md`; `Spec.md` |
| Active Extruded Bubble investigation/recovery and genuine acceptance debt | `Current_Plan.md` §0 / §4B; `Docs/Reference/Extruded_Bubble/README.md` |
| EB R42 surface retirement, birth clustering and Bounce next repair; glyph native test audit | `Current_Plan.md` §4B EB-R42; `Docs/Reference/R42_EB_Surface_Birth_Glyph_Test_Audit.md` |
| EB architectural work order and visual acceptance falsifiers | `Current_Plan.md` §4B G00–G33; [`Docs/Reference/Extruded_Bubble/Acceptance_Runbook.md`](Docs/Reference/Extruded_Bubble/Acceptance_Runbook.md) |
| EB viewport-sized near-shell blur/fade, off-axis continuity and native diagnostic evidence | `Current_Plan.md` G11; `rendering/gl_programs/extruded_bubble_program.py` → `EB_LENS_GLSL`; `Docs/TestSuite.md` → Extruded Bubble recovery gates |
| EB **22 Oct lighting physical-authority consolidation**, finite world-space shafts, future Lighting Coverage BEAM/SCENE and persistent SCENE emission clustering | [`Docs/Reference/Extruded_Bubble/Lighting_Authority_Repair.md`](Docs/Reference/Extruded_Bubble/Lighting_Authority_Repair.md); statuses still in `Current_Plan.md` G05–G09/G27/G30/G32/G33 |
| EB **22 Oct additional source-level reproductions**, per-mode exit leakage, emission-mode transitions, slider-endpoint coupling, GPU visibility and disabled-ray cost hypothesis | [`Docs/Reference/Extruded_Bubble/Additional_Source_Audit_2026-10-22.md`](Docs/Reference/Extruded_Bubble/Additional_Source_Audit_2026-10-22.md); current G00–G33 queue unchanged; **not native visually verified** |
| Extruded Bubble recorded-audio forensics, paired 2D response, count/emission candidates and fixed-world geometry | `Docs/Reference/Extruded_Bubble/Investigation.md` §6–18; `Docs/Reference/Harness_Index.md` → Extruded Bubble forensic tools |
| EB idle visibility versus 2D, saved-pose rejection, class-rest transfer and native layer evidence | `Docs/Reference/Extruded_Bubble/Investigation.md` §41/§49/§52; active work in `Current_Plan.md` G07/G15 |
| EB finite-world camera bounds shared by flight, saved poses and all special 3D controls | `core/settings/extruded_bubble_camera.py`; `Docs/Reference/Extruded_Bubble/Investigation.md` §51; active G03/G07 |
| Reusable framed 3D internal camera and per-mode view-pose contract | `Docs/Reference/Visualizer_Reference.md` → Live view pose; `Docs/Reference/Scene3D_Resources.md` → Shared framed-camera |
| Framed 3D control hints, hover visit, global glyph/hint preferences and RCC artwork | `Docs/Reference/Visualizer_Reference.md` → framed hints; `ui/assets/widgets/visualizer/control_hint.png` |
| Framed preset starting views, Save Preset As and camera validation | `Docs/Reference/Visualizer_Reference.md` → Framed preset starting views; `core/settings/visualizer_view_orbit.py` |
| Shared G1 attachments, G3A transparent layering, G2 shadow-map and selective G3B optics proof | `Docs/Reference/Scene3D_Resources.md`; `Current_Plan.md` §4A |
| Usu character authoring source and static review renders | local checkout `assets/usu/README.md` (excluded from normal Godzip); media source guidance in `Current_Plan.md` §3 |
| shared 3D resource ownership, DSA, immutable storage and state restoration | `Docs/Reference/Scene3D_Resources.md` |
| runtime audit 2026-09-22 outcomes and rejected ideas (closed) | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| FEEDS architecture, terminal failure/queued settlement, bundle admission and open physical acceptance | `Docs/Reference/Feeds.md`; `Docs/TestSuite.md` → FEEDS |
| defaults | `Docs/Guides/Defaults_Guide.md` |
| Guided Setup / Quick Start / Settings Arrange | `Docs/Reference/Guided_Setup.md` (open physical acceptance at its end) |
| logging / bounded MC CLI capture / Qt-QML observability | `Docs/Guides/Logging_Guide.md` + `Docs/Guides/Qt_QML_Observability.md` |
| documentation maintenance | `Docs/Guides/Documentation_Maintenance.md` |
| test inventory / acceptance authority | `Docs/TestSuite.md` |
| durable test authoring / mutable-authority hygiene | `Docs/Guides/Test_Durability.md` |
| harness commands | `Docs/Reference/Harness_Index.md` |
| delegating work to Codex and auditing it | `Docs/Guides/Codex_Delegation.md` |
| GODZIP Foundry quick-launch Foundries / GUI tools | `Docs/Reference/Harness_Index.md` → GODZIP Foundry operator commands |
| friendly 60-second music capture / full waveform replay | `tools/music_recorder.py`; `Docs/Reference/Harness_Index.md` |
| benchmarks: cost baselines, the lifecycle contract, reading results, expected results | `Docs/Reference/Benchmarks.md` |
| bounded self-terminating RUN / repeated startup-teardown acceptance | `Docs/Reference/Harness_Index.md` → Bounded self-terminating RUN sessions (`main_mc.py`, `tools/run_matrix.py`, `--exit-after`) |
| Steam source/auth/privacy contract | `Docs/Reference/Steam_Source_Contracts.md` |
| Friend Pulse current contract | `Docs/Reference/Steam_Friend_Pulse.md` |
| System Stats current contract | `Docs/Reference/System_Stats_Widget.md` |
| Sphere standard-mode contract, analysis-only DSP and accepted Shockwave-shaped horizon | `Docs/Reference/Sphere_Visualizer.md`; `Docs/Historical_Bugs/R-150_Sphere_Analysis_Only_Shockwave_Shaper_Audit.md` |
| historical bug / rejected-method routing | `Docs/Historical_Bugs.md` (sole index) |
| compatibility / schema-migration bridges | `Docs/Architecture/Persisted_Input_Compatibility.md` |
| deferred features / long-horizon graphics and Visualizer ideas | `Future_Work.md` |
| Usu Moonscape vertical: behaviour, reactivity, required 3D architecture (S19–S27), asset gates | `Docs/Future_Work/Usu_Moonscape.md` |
| Usu Blender work: previewing Usu, rig/clip fixes, missing clips, bake/export preparation | `Docs/Future_Work/Usu_Blender_Work.md` |
| Games You Follow product/source/CUSTOM | `Docs/Reference/Steam_Games_You_Follow.md` |
| system master-volume OSD | `Docs/Reference/System_Volume_OSD.md` |

## Performance/freshness baseline

CHK26 / repository commit `a0bf70932c` is the current operator-accepted GOLDEN performance/freshness baseline. CHK23 is the immediately prior GOLDEN rollback/bisect landmark and CHK15 / `0abc479c52` is the older pre-retained-background baseline.

The generic headroom campaign is closed. CHK27-CHK29 retained useful `--frame-trace` observability and proved that the largest remaining scheduler-shaped residuals are Qt frame/render-phase ownership or small distributed Bubble/driver costs rather than another obvious local hotspot. Reopen performance work only from a concrete reproduced symptom. The complete chronology and false trails live in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`.

## Visualizer read order

For a new mode or meaningful reactivity change, read:

1. `Docs/Guides/Visualizer_Reactivity_Authoring.md`;
2. `Docs/Guides/Visualizer_Change_Checklist.md`;
3. `Docs/Guardrails/Visualizer_Presentation.md`;
4. `Docs/Guardrails/Bubble_Temporal_Fidelity.md` when Bubble/shared timing could be affected;
5. `Docs/Reference/Visualizer_Reference.md`;
6. relevant Historical Bug negative controls.

Any production change that touches Bubble reaction/timing requires active-music physical acceptance; idle-only evidence is not sufficient.

## Documentation hygiene

Do not add another inventory/changelog/history layer. Closed decompositions are consolidated into current contracts or Historical Bugs and then deleted from the live docs tree. Extensible catalogs are registry-owned: live docs and harnesses say "every registered mode" / "canonical transition registry" rather than freezing today's membership count into prose. Persisted-input compatibility bridges are documented as architecture in `Docs/Architecture/Persisted_Input_Compatibility.md` (user-data protection, horizon-gated — not a backlog); caller-dead residue is deleted outright, not tracked in a register. When paths move, update this router and all live cross-references in the same change.

R43 current candidate investigation: `Docs/Reference/R43_EB_Breach_Inlet_And_Glyph_Checkpoint.md` (R42 premature EOL, population burst, actual radius spacing; all unaccepted).

# SCENE and BEAM | One Extruded Bubble physical emission system

**Candidate, never visually accepted.** Active acceptance is owned by `Current_Plan.md` G07/G08/G09/G32 and the single acceptance runbook. This reference is architecture and evidence, **not** another checklist.

## Operator intent and one authority

- **BEAM** is canonical default for all existing presets: current physical Source→End patch, size/spread/columns/count and lifetime behavior remain. No preset is rewritten.
- **SCENE** uses the same `ExtrudedBubbleSimulation` and existing bubble IDs, collision logic, audio followers, count endpoints, camera, shader stages and draw batches. The normalized Source selects physically adjacent inlet faces; the normalized End sets motion direction, never attracts particles toward an arbitrary point. The scene is a bounded 36×16×36 world box, with Sunlit Surface physically rendered at Y=9.
- At a floor source pointing upward, the whole floor is an inlet. At an inward-facing corner, adjoining inlet faces are selected with face-area × inward-direction weighting. An interior/malformed facing-source falls back to physical upstream faces rather than spawning impossibly on the wrong wall. The oblique editor paints inlet/outlet faces without inventing a second geometry or FOV.
- A **deterministic pre-aged startup cohort** makes SCENE feel like an inhabited tank on entry. It is generated at activation only, using the actual inlet and per-track traveled distance, with collision spacing and a bounded number of attempts. Once activated, all further births come through the physical inlet; no camera-dependent generation or midstream population replenishment.
- All newborns use existing gentle alpha admission and per-ID lifetimes. Sunlit Surface still has its current separate real-water-plane retirement (unaccepted for big bubbles); Deep Light/SCENE uses each individual's world exit face instead of the authored End dot. World boundary retirement keeps the established fade.
- Same GPU bead/snow/speck shader programs, not a new particle pass, sample these exact faces using uniform source-face weights computed once on CPU. Bead chains, snow and specks move along **individual full-length tank tracks**; parent fizz/wakes stay tied to their actual bubble parents. No change to authored glow/music controls or presets.
- Columns applies to localized BEAM authoring only; it does not discretize a whole-face SCENE inlet into bands. Bubble Spread and Particle Spread retain BEAM behavior; SCENE's lateral extent is the full face rather than an arbitrarily widened patch.

## Implementation owners

- `core/settings/default_settings.py` and `core/settings/visualizer_mode_settings.py`: one choice `extruded_bubble_emission_geometry` with default `BEAM` and `SCENE` opt-in; typed Settings and lazy buckets persist it.
- `core/settings/visualizer_paths.py`, `core/constants/extruded_bubble_world.py`: existing direction, physical coordinates and world dimensions remain the only authority.
- `widgets/spotify_visualizer/extruded_bubble_geometry.py`: `scene_source_face_weights`, `upstream_source`, `scene_track_length`, independent of the camera.
- `widgets/spotify_visualizer/extruded_bubble_frame_runtime.py` and `_simulation.py`: existing logical capture, persistent identity, pre-age/entry/end lifecycle. No new thread/timer/worker.
- `rendering/quick/visualizer/implementations/extruded_bubble.py` and `rendering/gl_programs/extruded_bubble_program.py`: one small uniform `uSceneEmission` and shared `uSceneFaces` for existing procedural GPU programs. No simulation owned by the renderer.
- `ui/widgets/visual_controls.py`, `ui/tabs/media/spec_mode_builder.py`: oblique editor paints the selected faces; the existing choice controls it. No change to shared two-node editor's existence, no FOV manipulation.

## What remains unproven

1. **Native 4.6 scene and shader compatibility**: offscreen Mesa 4.5 links are syntax evidence only. Verify correct face selection, rendered opacity, per-cohort fades and no clips at corner/boundary.
2. **Quality/density**: the global 192-bubble cap is unchanged; a distributed physical world may look sparse without extra capacity. Do not adjust count ranges or silently spawn more bubbles without actual GPU/pixel cost measurements.
3. **Cost**: shader includes one extra uniform branch, face selection per instance and possible increased visible glass coverage. Measure real CPU/GPU frame p95/p99, DPR/dual-display memory, and dormant resource cost. Only consider render-only frustum/LOD afterward; simulation-cull by camera is prohibited.
4. **Surface/large EOL**: the shared R43 surface and world-boundary decisions have not been visually validated for large bubbles. SCENE does not repair them.
5. **Screen-space 3D**: the oblique editor is only an authored control, not a second camera. Verify physical paths from above/below/sides and that light-source/shaft world-coordinates remain coherent.
6. **Test infrastructure**: a preexisting BEAM zero-speed test expects a birth within 30 captures even though the R43 paced inlet admits only ~0.4/s at zero stream speed. Do not alter product admission cadence to satisfy an outdated expectation without design evidence.

## Targeted focused validation

For Qt-free geometry and simulation (from Python 3.14 repo-root virtual environment):

```powershell
& '.\.venv\Scripts\python.exe' -m pytest --noconftest -p tools.pytest_qt_noenv -q tests/test_extruded_bubble_scene_emission_candidate.py
```

Native Settings construction and hydration: `tests/test_extruded_bubble_lazy_bucket_ui.py::test_scene_emission_choice_and_volume_face_repaint_use_one_settings_owner`. Native Windows GL/rendering and the operator visual acceptance remain separate gates.


## R45 subsequent visual rejection and mode-handoff attribution (22 October; OPEN)

The operator subsequently supplied another SCENE screenshot (`Evidence/2026-10-22_SCENE_operator_rejected_clustering.png`) with visible
clusters/bright speck islands and wide lower-scene gaps. **This candidate is
not visually accepted**; source-code changes to independent inlet UVs and
speck admission did not prove correction in native output. Capture the exact
Windows build revision and mode/settings before identifying which failure
mechanism survived. A single image cannot prove whether the grouping is
physically concentrated entities, bright shader samples or bloom.

Distinguish four controls in the source-to-pixel experiment: **emission
geometry** (BEAM/SCENE), **Light Type** (Surface/Deep), proposed **Lighting
Coverage** (BEAM/SCENE, **not yet implemented**), and the actual population
count. None is a substitute for another. Low counts can make SCENE look sparse
but do not explain localized grouping of actually distributed coordinates.

The logical simulation retains existing bubble IDs and XYZ through ordinary
BEAM→SCENE control changes: only future births take SCENE inlet sampling.
Therefore compare cold-start SCENE with transitions from BEAM, tagging ID
provenance and natural retirement. This is a falsifier, not an explanation
proven from the screenshot. Don't delete, teleport, respawn or camera-relocate
old bubbles. Check procedural population seed masks, alpha, illumination and
HDR bloom separately. Preserve G04 bubble-surface exit as independently open.

See `Lighting_Authority_Repair.md` for the audited ray/light defects and
ordered native acceptance experiment; all work gates remain under
`Current_Plan.md` §4B.

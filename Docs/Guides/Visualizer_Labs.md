# Shared visualizer lab contract

Every future mode starts in `tools/labs/<mode>_lab.py`. A lab composes and authors inputs over the shared production
graphics substrate. Its recipe can precede Settings and mode registration; reusable GPU primitives stay in
`rendering/quick/scene3d/` and production shader modules. The target image and mode's focused contract own visual
requirements. See [visual tuning](Visualizer_Visual_Tuning.md) for mock/lab/production comparisons and music capture.

## Context, target and capture

`tools/labs/render_target.py:OffscreenRenderTarget` owns the GUI-thread Qt offscreen surface, validated OpenGL 4.6
context, RGBA8 colour/depth24 framebuffer and lazy diagnostic quad. Reuse it rather than copying setup or importing
`TransitionCapture` merely to obtain a context. Construction leaves its context current; `current()` scopes an entire
GL operation and restores the caller's previous context. `bind()` clears the target; `read_rgba()` returns an owned,
contiguous, top-left raw RGBA array. Alpha conversion belongs to the exporting caller. Additive glow needs an explicitly
chosen backdrop when an opaque reference is required.

`resize()` admits a complete replacement before deleting the previous target; failure retains the last admitted
dimensions/resources and raises. Callers own projection changes and scene-specific HDR/MSAA/OIT targets. The shared
target adds no scene resize policy, window, timer, polling or GL-state cache. It is a diagnostic output target, not a
runtime framebuffer authority.

Retire scene/host resources under `with target.current():` before `target.close()`, using `try/finally` or `ExitStack`
from first successful allocation. Close is idempotent; failed resource retirement restores a foreign caller's context
and remains retryable. Partial admission and failed resize propagate loudly. A render error invalidates the preview;
do not quietly retain a stale image and call that success.

## Scene and renderer composition

- Before registration, compose shared Scene3D primitives and shader modules directly, as the Extruded Bubble lab does.
  The lab owns its recipe, local programs/resources and explicit scene time. Do not invent registry entries or copy
  production lifecycle machinery merely to draw an experimental primitive.
- For an existing mode, use `QuickVisualizerRenderHost` with immutable snapshots. A scoped `renderer_factory` can
  customize an input projection in a renderer subclass; canonical admission, identity checking, lazy cache-miss
  construction, drawing, GL-state restoration and retirement remain with the production host/resolver. Never monkeypatch
  module globals or copy a renderer into the lab. The default runtime factory path is unchanged.

Time is explicit fixture/replay input. Production admission later uses the sole Visualizer logical clock. No lab
scheduler, DSP pipeline, Settings schema, palette, presets store or renderer-side simulation becomes a second authority.
There is no universal lab recipe schema: mode-specific scene inputs remain at their focused owner.

## Execution and proof

Use project Python and explicit CLI paths; no environment-variable configuration. Automated GPU/native probes need an
external deadline over their entire process tree. Reuse the Windows Job ownership in
`tools.build_runner.BuildProcessOwner` for a bounded launcher: it owns the probe process, not a product build. Legal
renderer retirement is still required before successful exit. See [Qt/QML observability](Qt_QML_Observability.md).

Prove driver capture, resize, interleaved context ownership, failure cleanup and idempotent retirement at the shared
boundary (`tests/test_lab_render_target.py`). Then prove the mode's same-scene low/high output and measured warm GPU
cost; a successful FBO read is not visual or musical acceptance. Native Settings/runtime rendering and operator
acceptance remain separate gates. Adopters include TransitionCapture (retaining its own transition fixtures/host),
Foundry's production visualizer captures and the Extruded Bubble composition lab.

## Bubble two-node gradient

`.venv\Scripts\python.exe tools/labs/bubble_gradient_mapper_lab.py` opens the interactive control. Add
`--capture tmp/bubble_gradient_mapper/prototype.png` for a finite control render plus wide/narrow/shifted fixtures.
The shared `GradientMapper` uses semantic slider styling, independent Dark/Light nodes, keyboard fine movement, one
gesture commit and the existing undo interface. Normalized top-left content endpoints project through the actual
content aspect: zero/one occur at Dark/Light and the physical blend normal matches their line. A minimum span prevents
undefined coincident endpoints. Geometry is Qt-free in `core/gradient_geometry.py`.

The lab uses the production Custom gradient settings/capture path, without a renderer-input override. Named
recipes retain their existing pixels; custom endpoint persistence and compound recipe/node Undo are implemented.
See `Docs/Reference/Bubble_Gradient.md` for the current contract.

## Waveform Ribbon entry point

`tools/labs/waveform_ribbon_preflight.py` performs reference/projection preparation only. The detailed live boundaries
and Orthographic-default requirements are in `Docs/Reference/Waveform_Ribbon_Lab_Plan.md`. No scene/ribbon renderer
exists yet. Use `.artifacts/evidence/` for explicit retained output and `.artifacts/scratch/` for disposable checks.

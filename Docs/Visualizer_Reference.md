# Visualizer Reference

Last updated: 2026-08-19

Current Spotify visualizer architecture/settings reference.

## 1. Modes

Canonical ids come from `core/settings/visualizer_mode_registry.py`:

- `spectrum`
- `oscilloscope`
- `sine_wave`
- `bubble`
- `devcurve` (user-facing Spline Curve)

Retired Blob identities remain migration/history only.

## 2. Canonical idle capability model

Use the canonical mode capability owner. Do not recreate hard-coded subsets in startup, mode switch,
tick, reveal or settings code.

| Mode | Idle reveal | Idle self-animation | Presentation-owned idle scene | Fresh real source required for reactive playback |
|---|---:|---:|---:|---:|
| Bubble | yes | yes | no | no |
| Spectrum | yes | no | yes | yes |
| Sine | yes | yes | no | no |
| Oscilloscope | yes | yes | no | no |
| DevCurve | yes | yes | no | no |

Paused Spectrum is intentionally mixed:

```text
presentation_ready = true
reactive_source_ready = false
waiting_for_fresh_engine_frame = true
source generation/activation = absent
```

Its idle bars are presentation state, not fake audio.

## 3. Settings / presets

Primary owners:

- model: `core/settings/models/_spotify_visualizer.py`
- mode identity: `core/settings/visualizer_mode_registry.py`
- preset resolution: `core/settings/visualizer_presets.py`
- activation/runtime/config helpers under `widgets/spotify_visualizer/`

One activation consumes one resolved target payload.

Curated preset selection, same-mode preset cycling and identical settings refresh are different
operations. Do not globally cache solely by mode id.

## 4. Logical cadence runtime

Primary owner:

`widgets/spotify_visualizer/logical_runtime.py::VisualizerLogicalRuntime`

Supporting owners include:

- `widgets/spotify_visualizer/tick_helpers.py`
- `widgets/spotify_visualizer/tick_pipeline.py`
- `widgets/spotify_visualizer/mode_transition.py`
- `widgets/spotify_visualizer/thread_affinity.py`
- `widgets/spotify_visualizer/beat_engine.py`
- `widgets/spotify_visualizer/audio_worker.py`

Current production shape:

```text
VisualizerLogicalRuntime
    -> worker-callable logical_tick()
    -> LatestStateMailbox
    -> GUI run_on_ui_thread handoff
    -> present_tick()
```

The old GUI visualizer recurring timer is not the logical clock.

`AnimationManager` is not the logical clock.

## 5. Logical / GUI ownership split

Logical worker owns plain-data decisions/state evolution.

GUI owns:

- QWidget visibility;
- presentation geometry mutation;
- layout/shadow/card raster work;
- fade/reveal execution;
- compositor publication;
- GL/QRhi mutation.

Required cross-boundary handoffs are explicit and test-covered.

## 6. Latest-state handoff

The mailbox is single-slot/latest-wins.

No FIFO.

No catch-up.

No one-GUI-callback-per-logical-tick contract.

Every authored event must integrate before later logical state may supersede it.

## 7. `SpotifyBarsGLOverlay` means resource/state host, not surface

The historical class/path remains for visualizer render state and GL-resource code used by the
compositor.

It is not an independently presented GL overlay.

Do not add:

- its own QOpenGLWidget/QRhiWidget presentation;
- swap/vsync ownership;
- self-driven repaint stream;
- framebuffer-grab assumptions.

Actual pixels are rendered through:

`rendering/gl_compositor_pkg/visualizer_layer.py`

inside the display's sole compositor.

## 8. Presentation geometry

One authoritative geometry snapshot feeds:

- card texture;
- viewport;
- scissor;
- shader resolution;
- framebuffer origin;
- stencil/mask;
- border.

Compositor/display DPR is presentation DPR authority.

## 9. Card visual

The QPainter-authored card source may be rasterized/cached on GUI at a known size/DPR/style revision.

Steady visualizer presentation reuses the uploaded GL texture.

Do not rebuild QPainter/card pixels every visualizer frame.

## 10. Spectrum idle presentation

The paused Spectrum idle scene is static presentation state.

It must:

- be perceptibly visible;
- remain low/resting rather than reactive;
- not create fake BeatEngine data;
- not fabricate source generation/activation;
- remain visible until real current-generation data is ready on Play;
- be replaced in place.

“bar float > 0” is not sufficient proof of perceptible visibility.

Use actual GL/pixel output or renderer-aware pixel-height geometry.

## 11. Bubble / BTF

Canonical contract:

`Docs/Guardrails/Bubble_Temporal_Fidelity.md`

BTF protects:

- trajectories;
- elasticity;
- attack/decay/overshoot/settling;
- source freshness;
- logical cadence/gaps;
- protected edge survival;
- state-to-screen timing;
- final perceptual continuity.

Bubble is a canary for shared timing; do not create Bubble-specific cadence fixes without Bubble-owned
evidence.

## 12. Playback

Pause/Play should preserve:

- logical runtime;
- mode identity;
- card/GL resources;
- warm capture ownership.

The visualizer-owned 700 ms pause debounce is retired.

Identity continuity does not prove no-hitch continuity.

Current Pause/Play work must also account for GUI/presentation cost such as Media control feedback.

## 13. Generation / activation

Generation and activation are ownership identities.

- `0` is a valid integer generation;
- None/missing is invalid/unassigned;
- do not use `value or -1` where zero is meaningful;
- stale retired identities cannot reveal/publish.

## 14. CUSTOM / Edit

Edit snapshot comes from compositor-owned visualizer scene, not
`SpotifyBarsGLOverlay.grabFramebuffer()`.

Drag/resize is preview-first.

Save publishes new authoritative geometry once.

Cancel restores/resumes the prior live owner rather than broadly replaying unrelated settings.

## 15. Validation

Use:

- deterministic replay/goldens for authored behaviour;
- current P2 behavioral gates for worker/readiness/generation/edge ownership;
- BTF for Bubble timing/feel;
- real GL tests for card/viewport/idle visibility;
- runtime-shaped 60 Hz + high-refresh delivery;
- lifecycle generation tests;
- installed manual review.

A test's name does not prove it exercises the real output path.

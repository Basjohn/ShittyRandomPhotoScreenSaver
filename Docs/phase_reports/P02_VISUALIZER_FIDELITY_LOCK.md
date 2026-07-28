# Phase Report — P02: Visualizer Fidelity Lock

## Metadata

- Branch: `main`
- Commit before: `5ad5781de8d8fdbbdc43c761d5b047d386d784db` (`4.6.9 Phase 1`)
- Commit after: checkpoint commit `4.6.9 Phase 2`
- Date: 2026-07-28
- Environment: Windows native PowerShell; repository `.venv`; Python 3.11.9; pytest 8.4.1; Qt tests run with `QT_QPA_PLATFORM=offscreen`
- Baseline behaviour commit: `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c`
- Donor: reference-only; no donor code copied or merged

## Phase objective

Protect baseline visualizer feel before lifecycle, memory, threading, or compositor work by replaying deterministic timestamped feature frames through the real baseline simulation/tick/overlay path, capturing versioned per-mode output, and making ordinary verification read-only.

## Invariants protected

- Visualizer: baseline equations, authored preset zero, mode personality, activation boundaries, visibility gating, input processing, and tick ownership remain unchanged.
- Lifecycle: no GL/context lifecycle or Settings/Edit behaviour changed in this phase.
- Frame pacing: presentation opportunities sample completed logical state and never drive simulation.
- Memory: no production cache or resource ownership changed; replay/golden files are development evidence only.
- Threading: live and replay analysis commit through the same beat-engine acceptance seam; replay makes external audio startup inert and uses an immediate deterministic compute test double only where the production callback contract requires it.

## Code and ownership inspected

- `widgets/spotify_visualizer/beat_engine.py`
- `widgets/spotify_visualizer/tick_pipeline.py`
- `widgets/spotify_visualizer/spotify_visualizer.py`
- `widgets/spotify_visualizer/overlay.py`
- mode-owned Spectrum, Bubble, Sine, Oscilloscope, and Dev Curve runtime state
- `core/settings/models/_spotify_visualizer.py`
- `rendering/spotify_widget_creators.py`
- Phase 2 roadmap fidelity and test contracts

The donor was not exhaustively analyzed. Its failed compositor/scheduler shapes were excluded by the roadmap; this phase stayed on the baseline runtime path.

## Changes made

- Added immutable, validated, canonical timestamped feature-frame and clip schemas.
- Added 13 versioned feature-only fixtures: silence, isolated impulse, 60/120/180 BPM beats, sustained bass, sustained treble, broadband noise, gradual ramp, sudden volume step, representative music features, irregular input cadence, and mode/visibility control.
- Added a synchronous beat-engine acceptance seam that shares smoothing and commit logic with live analysis frames.
- Added deterministic replay through the real `SpotifyVisualizerWidget`, production `tick_pipeline.on_tick`, and `SpotifyBarsGLOverlay.set_state` logical-state preparation. OpenGL presentation alone is suppressed.
- Added all-mode capture for Spectrum, Oscilloscope, Sine Wave, Bubble, and Dev Curve plus the mode/visibility control replay.
- Added independent 30/60/90/120 Hz, irregular cadence, and 100/250/500 ms presentation sampling without simulation feedback.
- Added response, peak, attack, decay, overshoot, settling, energy, derivative/discontinuity, waveform, onset, and Bubble trajectory/elasticity metrics.
- Added font-independent Spectrum/Bubble contact sheets and a labelled HTML review page.
- Added protected bootstrap/update/verify policy and versioned golden manifest hashes for fixtures and authored preset-zero settings.

## Changes explicitly not made

- No visualizer equation, damping, smoothing, normalization, amplitude mapping, shader, preset, mode cadence, or creative setting changed.
- No compositor scheduler, paint acknowledgement, catch-up update, compatibility façade, or donor lifecycle path was introduced.
- No driver-dependent shader pixels are claimed by the logical contact sheets.
- No Phase 3 Settings/Edit or GL teardown work and no Phase 4 memory/cache work was pulled forward.

## Tests and scenarios

- Final Phase 2 focused suite: `48 passed`.
- Established runtime-shaped visualizer gate: `186 passed, 20 skipped`.
- Full replay capture: 13 input fixtures, 66 outputs, 3,469 logical frames, 67 golden files including manifest.
- Full golden verification recomputed every output and preserved every golden hash and modification timestamp.
- Broad visualizer sweep: `681 passed, 23 skipped, 18 failed, 1 warning`. The failures are pre-existing baseline debt in Bubble legacy/physics expectations, stale Sine UI imports, one non-Qt settings test double, and one historical-Git subprocess missing the process-local safe-directory override. None touched Phase 2 files; the established runtime-shaped and Phase 2 gates passed.
- Python compilation passed for all changed Python modules.

## Golden and tolerance contract

- Golden comparison is exact canonical JSON after normalization to seven decimal places.
- All five supported modes use the same exact normalized tolerance because replay fixes time, random state, inputs, viewport, settings payload, and callback ordering.
- Infrastructure phases may run `verify` only. They may not bootstrap or update baseline output.
- Bootstrap requires an empty directory and `--acknowledge-baseline`.
- Update requires both `--acknowledge-behavior-change` and a declaration containing exact `approved: true` and `goldens: true` lines.
- Intentional visualizer behaviour changes require the roadmap visualizer change declaration and user approval before golden replacement.

## Representative quantitative evidence

The representative music fixture produces immediate logical response (`0 ms`), peak at `560 ms`, normalized bar peak `0.6934138`, attack `1.2382389/s`, overshoot ratio `1.3959136`, integrated bar energy `0.5096317`, and zero detected discontinuities across every mode's shared analysis bars. Mode-owned arrays and runtime state remain separately captured in each golden.

The isolated Bubble impulse records:

- response latency: `0 ms`;
- peak within the first authored sample; bounded attack: `21.764095/s`;
- bar half-decay: `120 ms`;
- particle peak: `49`;
- centroid speed peak: `0.3353575 normalized units/s`;
- mean-radius change peak: `0.33431/s`;
- mean-radius excursion: `0.0067272`;
- radius overshoot ratio: `0.3583855`;
- radius settling: `260 ms`.

## Visualizer fidelity result

- Deterministic replay: pass; repeat runs produce identical logical frames/digests and restore global random state.
- Production pathway: pass; automation spies the inherited production beat-engine `tick`, production tick pipeline, and production overlay state function.
- Spectrum manual logical review: pass; contact sheet retains band contour, attack, and progressive decay without flat-band collapse.
- Bubble manual logical review: pass; contact sheet retains immediate population, spatial movement, radius variation, and settling without an overdamped/static shape.
- Irregular presentation: pass; all tested presentation schedules preserve the exact logical series while selecting the latest completed state.
- Visibility/mode control: pass; hidden frames do not publish and fresh visible/mode frames use the production gates.

Artifacts:

- `Docs/phase_reports/artifacts/P02/spectrum_logical_contact_sheet.png`
- `Docs/phase_reports/artifacts/P02/bubble_logical_contact_sheet.png`
- `Docs/phase_reports/artifacts/P02/spectrum_bubble_review.html`

## Unexpected findings and rejected approaches

- The native offscreen Qt environment exposes zero font families. Initial labels rendered as boxes, so PNG evidence was made font-independent and descriptive text remains in HTML.
- Internal Bubble `vx/vy` is zero for much of authored preset-zero drift. Treating that lane alone as visible motion was rejected; aggregate centroid and radius trajectory metrics were added.
- A zero-time-to-peak impulse initially divided by a 1 microsecond placeholder. It now uses the adjacent authored input interval, avoiding a meaningless attack slope.
- The broad suite still contains unrelated baseline debt. It was recorded, not fixed or hidden inside Phase 2.

## Rollback instructions

Revert checkpoint commit `4.6.9 Phase 2`. No migration, user settings, production cache, or external state must be undone.

## Gate decision

- [x] Pass
- [ ] Fail
- [ ] Pass with explicit deferred issue

Gate 2 passes: baseline visualizer logical feel is protected by deterministic all-mode replay, protected goldens, cadence-separation tests, quantitative metrics, and manually inspected Spectrum/Bubble artifacts. Driver-level shader screenshots and live Spotify review remain later runtime/release evidence; they are not substituted by this logical lock.

## Live checklist updates

- Phase 2 roadmap checklist completed.
- `Current_Plan.md` advances to Phase 3 lifecycle safety.
- Harness, test-suite, visualizer-reference, specification, and index routes updated.
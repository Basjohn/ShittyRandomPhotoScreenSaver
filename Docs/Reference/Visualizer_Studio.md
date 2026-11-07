# Visualizer Studio

Current owner reference for the reusable in-process authoring Studio (`ui/studio/`). It records what is true in
source now; open acceptance work (mock parity, hardware window checks, further adapters) lives only in
`Current_Plan.md` §7.1 and §9. The design rationale and the viewport decision are recorded in
`Docs/Audits/Waveform_Studio_and_Reactivity_Audit_2026-11-05.md` §4; the operator's interface concept is
`Docs/Audits/SRPSS_Waveform_Studio_Design_Pack_2026-11-03.zip`.

## 1. What it is

A Studio is a top-level Qt Quick window (`ui/studio/qml/StudioShell.qml`) opened from a Visualizer mode's preset
row in Settings (Open Studio, on every preset slot). It shows a live preview drawn by the mode's **production** renderer from the mode's **production**
logical owner, plus an inspector that edits the mode's canonical settings and saves them through Settings' own
Custom save path. It is the only sanctioned Qt Quick window opened from Settings; Settings itself stays Qt Widgets.

The framework is mode-neutral: nothing outside an adapter module names a mode's geometry or sources. A mode joins by
registering an adapter; every other piece (shell, session, transport, viewport host, Settings link, theme) is shared
and must not be copied per mode.

## 2. Module ownership

| Module | Owns |
| --- | --- |
| `ui/studio/registry.py` | `mode_id -> "module:Factory"` registrations; `has_studio`, `studio_modes`, `create_adapter`. Adapters import lazily, so an unopened Studio loads no mode code. The registry is the membership authority: docs and tests say "every registered Studio adapter", never a count. |
| `ui/studio/adapter.py` | The adapter contract: `StudioModeAdapter`, `StudioEvaluator` / `StudioRenderer` protocols, `StudioCapabilities`, `StudioFixture` (kinds `REFERENCE`, `SYNTHETIC`, `RECORDED`), `StudioFraming` + `fill_extent`, `StudioNavigation` / `NavAxis`, `StudioPreview`, `RenderCard`, and `control_condition` (a registry control's `when` as Studio terms). |
| `ui/studio/technical.py` | A mode's technical (audio-analysis) controls as Studio properties with Settings' own keys, ranges, choices, labels and coercion; adapters call it instead of copying them. |
| `ui/studio/schema.py` | Typed, mode-supplied property schema: instruments (`SCALAR`, `COUNT`, `SWITCH`, `CHOICE`, `QUIET_PEAK`, `COLOUR`, `GRADIENT`), workspaces/columns, scene objects, response tuner, starting-point presets, lifecycle timelines and rendered cards. `admit` is the mode's canonical validator; the framework stores no defaults. |
| `ui/studio/session.py` | `StudioEditSession`: hydrate from the canonical store, preview vs committed values, one commit per gesture, undo/redo/dirty. The store answers each commit with its canonical post-save snapshot. No Qt, no mode knowledge. |
| `ui/studio/controller.py` | `StudioController` (single active instance, open → present → retire lifecycle) and `StudioBridge`, the only object QML sees. Bridge slots are plain methods (no `result=`), per the QML signal → result-slot crash rule. The bridge's `values` is a `StudioValueMap` (`QQmlPropertyMap`): each property id notifies on its own, so a changed value re-evaluates only the bindings that read it. |
| `ui/studio/viewport.py` | Inline `QSGRenderNode` that draws the adapter's renderer straight into the window framebuffer on the render thread (no readback, no per-frame texture copy). Before drawing it clears the scene's region (the slot's scissor) to `SCENE_BACKING`, the opaque backing snapshots also use, so nothing the chrome paints under the viewport composites into a mode's transparent background or translucent edges. It applies the viewport slot's scene-graph clip (scissor), so a frameless mode that overflows its card in production (Extruded Spectrum, Sphere: up to the window) reaches the slot's edge, never the Studio chrome. Renderer created lazily and released on the render thread on `sceneGraphInvalidated` / node release. Snapshots (tiles, rendered cards, Copy Frame) use a second renderer instance, at most one per frame and only on request. |
| `ui/studio/transport.py` | Play/pause/scrub/loop on the Studio's own time. No timer: it advances on the surface's `afterAnimating` frame start and requests another frame only while playing. |
| `ui/studio/surface.py` | `StudioWindowSurface` (visible window) and `OffscreenStudioSurface` (hidden `QQuickRenderControl` host used by tests and the capture tool). Same shell, same signals (`frameStarted`, `presented`, `closeRequested`, `lost`, `failed`). |
| `ui/studio/settings_link.py` | `open_mode_studio` and `VisualizerSettingsStore`, the canonical store over the Visualizers tab (see §4), including Save To <Preset>. |
| `core/settings/visualizer_preset_file.py` | Shape-preserving edits of an authored preset file (section merge, in-place patching, source-like formatting, `save_changes_to_preset`), shared by the preset repair tool and the Studio's Save To <Preset>. |
| `ui/studio/presence.py` | `WindowPresence`: conceal/reveal the *same* Settings dialog without ending its `QDialog.exec()` loop (native `SW_HIDE` on Windows; zero opacity plus off-screen move elsewhere). |
| `ui/studio/framed.py` | Shared pieces for 3D (and card-presented) adapters: production presentation resolver and uniform aperture scale, `card_framings` / `live_card_framings`, `camera_navigation` over the shared framed camera, `orbit_navigation` for a free-orbit mode (the descriptor's `view_orbit_settings` only), `QuickModeRenderer` wrapping a production Quick renderer and `ContractModeRenderer` handing it the production render-frame contract (pixel ratio from the item mapping, so a letterboxed live card presents at the true DPR). |
| `ui/studio/engine_answers.py` | The Spectrum family's recorded engine answers (Spectrum, Extruded Spectrum, Neon Lake, DevCurve, Oscilloscope), mode-neutral (`EngineAnswerMode(mode_id, conditional_reads)`): synthetic audio (with the analysis spectrum and onsets a recording carries), the out-of-process `extract`, recorded inputs, the per-mode answer cache, `start_clip_load` and `EngineAnswerEvaluator` (the production step in process on `ExactReplay`). |
| `ui/studio/clip_loop.py` | Seamless Studio clips: the loop period a compact clip names, `Anchor` (the transport's unrolled time -> the history an evaluator replays; a rewind re-anchors to the pass the instant is in), `Cycles` (the endless tick sequence of a looped input: later passes shifted whole periods, onset serials kept increasing), the per-family tick shifts and `primed` (an analysis worker replays the loop's last 2 s before the clip). See §3 "Studio clips". |
| `ui/studio/exact_replay.py` | `ExactReplay`, the shared exact-history mechanism of the replaying evaluators (the engine-answer modes and Waveform): checkpoints per values signature, rewinds, the frame budget (`converging`) and the live-gesture path. An evaluator supplies only its step, its state capture and its restyle. The engine-owned / mode-owned split follows from the production source projection (`source_config_applier`). |
| `ui/studio/brush.py` | The shared heightfield brush instrument: `BrushTarget` (the record's key, `pick` and `footprint` through the mode's production camera, from `adapter.brush_target()` when `capabilities().brush`) and `StudioBrush` (tool settings, held pointer points, the stroke; flushed at frame start). Strokes are painted by `rendering/gl_programs/heightfield_brush.py`. |
| `ui/studio/spectrum_shape.py` | The Spectrum family's shape editor as Studio rows, admission and structural edits (add / remove node, lane swap), by key prefix (`ShapeKeys`). |
| `ui/studio/theme.py`, `colour.py` | Chrome tokens derived from the active Settings theme with enforced contrast; display ↔ linear colour conversion for instruments. Scene colours never pass through the theme. |
| `ui/studio/chrome.py` | The painted chrome items (`StudioFrame`, `StudioWindowEdge`, QML module `SRPSS.StudioChrome`), painting with Settings' own owners (below). |

### Chrome and theme

The Studio's chrome follows the Settings theme; the scene never does: the viewport clears the scene's region to one
fixed backing (`viewport.SCENE_BACKING`) before the mode draws, so a transparent background or a translucent rim
composites onto it, never onto the themed surface under it (`tests/test_studio_scene_theme_independence.py` renders
every registered Studio under the darkest and the lightest shipped theme and compares the scene pixels). The chrome
reuses Settings' owners rather than restating them:

- **Window.** `StudioWindowSurface` is a frameless top-level (`Qt.FramelessWindowHint`). The shell draws Settings'
  custom title bar in QML (`studioTitleBar`: "SRPSS STUDIO", minimise, maximise/restore, close, on the theme's
  `window.titlebar.*` roles); the Studio header (mode picker, preset, undo/redo, help, Save Preset As…, Close) sits
  directly under it, as Settings keeps its title bar free of controls. A title-bar drag is the system move
  (`QWindow.startSystemMove`: Windows snap and Aero snap), double-click maximises to the work area (manual, as
  Settings), a drag from maximised restores under the pointer, the window sides and corners resize through
  `startSystemResize`, and Esc / Alt+F4 / the title bar's × close through the same close path as before.
- **Rounded edge.** `StudioWindowEdge` paints `ui/settings_window_edge.py:paint_forged_window_edge`, the function
  `SettingsDialog.paintEvent` calls: the same radius, outer border (`chrome.outer_border`), backing and opaque corner
  caps (`window.titlebar.surface`), square when maximised. There is one forged edge, not one per window.
- **Material.** Normal (`backdrop.mode` off) is an opaque window with no native call. Under a Glass or Acrylic theme
  the window gets an alpha surface and, on first show, the theme's material through
  `core/windows/dwm_blur.py:apply_backdrop`, the mode → AccentPolicy mapping Settings' own backdrop owner calls
  (Acrylic: state 4 with the theme tint; Glass: untinted state 3). One window-level material, no per-panel blur or
  capture. The window surface (`window.dialog_glass`) and title bar take the theme's translucent roles; the large
  panels let the material through at the theme's polarity with an opacity floor (`PANEL_MATERIAL_FLOOR`, 0.88) so
  dense instruments stay legible over any desktop; the viewport, toolbars and inputs stay opaque. The material is
  chosen when the window opens (Settings is concealed while a Studio is open).
- **Cards and sections.** Main panels, the response dock, the tab strip and the viewport frame are `StudioFrame`s:
  Settings' hard outside-only cast (`ui/widgets/control_shadow.py:cast_shadow_path`, the `panel.group` shadow role at
  half its offset, `SHADOW_SCALE`), the surface, and the border stroked once along one continuous path
  (`ui/widgets/continuous_border.py:rounded_border_path`), 1.5 px. Smaller cards (group headers, schematic and trace
  cards, starting-point tiles, toolbar backings) are Quick rectangles whose border is one ring, also 1.5 px. A painted
  frame repaints only when its size or a colour changes: nothing per frame, no frame requests.
- **Instrument wells.** Signal-trace cards, the response-curve box and the transport bar (with its time readout) sit
  on the `well` role: the viewport tone while the theme's own text reads on it at 4.5:1 (every dark theme, unchanged),
  else the theme's input surface (a light theme). Their inks (`wellText`, `wellDim`, `wellTrace1..3`) are the panel's
  text and trace colours checked on the well (`ui/studio/theme.py`).
- **Viewport corners.** The viewport frame reaches 2 px past its column so the slot keeps its exact place and size
  (the scene's pixels are unchanged) while every slot corner lies inside the frame's rounded outline; the frame's
  border is drawn over the scene (`viewportFrameBorder`), covering the slot's square corners. The render node, its
  scissor and the saver's clip path are untouched.
| `ui/studio/<mode>_adapter.py`, `<mode>_recorded_inputs.py` | One adapter per registered mode plus its recorded-clip extractor. |

## 3. Adapter contract

An adapter supplies `schema()`, `scene_objects(values)`, `create_evaluator()` and `create_renderer()`; everything else
is optional and defaults to "not offered":

- **Truthful evaluator.** `evaluate(time, values, exact=...)` returns an immutable frame from the mode's production
  logical owner (its own instance; never the desktop visualizer's runtime, history, engine or GL objects).
  Identical fixture, values and time give an identical frame; `exact=False` may approximate during a live gesture,
  and the gesture end replays exactly. Fixtures feed the exact keyword inputs the production capture passes to the
  mode's frame runtime. This is a sandbox timeline on the same code, not a second model or clock.
- **Fixtures.** Held Quiet/Mid/Peak references, synthetic inputs and recorded clips. Recorded clips are analysed in a
  separate process (`python -m ui.studio.<mode>_recorded_inputs`, via `QProcess`; a frozen build runs its own
  executable with `--studio-clip-worker`) through the production offline replay, so the running app's live
  visualizer is never disturbed; the finished job is released after its signal returns, never inside it. A worker
  never outlives its job or the Studio process (`ui/studio/worker_lifetime.py`): on Windows each worker and
  everything it starts (a venv `python.exe` is a launcher that starts the real interpreter suspended) runs in its
  own kill-on-close Job Object held only by the Studio, so a cancel ends the whole tree and the OS ends it when the
  Studio exits or crashes; on Linux the worker arms `PR_SET_PDEATHSIG` (and exits if its parent is already gone);
  elsewhere a cancel still ends it but a parent crash does not. Every worker exits non-zero at once on a missing or
  unreadable clip. The worker's temporary folder (`worker_tag`) names the starting process, so a leak is traceable. Every
  Studio lists the shipped clips (`assets/production/studio_clips`) first, then a checkout's own recordings.
  **The GUI thread never parses a worker's output:** `ClipLoadJob._on_finished` hands the JSON read and the mode's
  `convert` to an IO task on the app-shared ThreadManager and the inputs come back through `run_on_ui_thread`, dropped
  if the job was cancelled meanwhile (an Extruded Bubble clip is about 12 ms of parse; a tool with no app-shared
  manager parses in place). **Analysed clips live in one bounded store per mode** (`engine_answers.remember/analysed`,
  newest `ANALYSED_LIMIT` kept, keyed by the clip and its analysis values); no adapter keeps its own cache. Each Audio
  Analysis edit is a new key (about 0.66 MB per Extruded Bubble entry), so an unbounded cache grew for the process.
  `tests/test_studio_clip_cache_and_parse.py`.
- **Studio clips are seamless loops (6 Nov).** The three shipped clips are not 12 s windows that restart: each is a
  loop (12.6-13.2 s, 0.86-1.01 MB, 2.74 MB in all) whose first frame follows its last as the recording's own next
  moment, and the Studio plays on through the wrap instead of restarting. There is no audio playback in the Studio: a
  clip is the capture stream and lanes the analysis and every mode's logic are fed, so "the sound jumps" was the
  analysis input and the preview's simulation state jumping at `t = 0`. Three parts, each owned once.
  *Loop points* (`tools/studio_clip_loop.py`, run by `tools/build_studio_clips.py`): the start and the period are
  searched inside a span the clip is for (period 12-16 s) for the pair whose lead-ins match best (onset-envelope
  correlation, level, log-spectrum, and, where the recording has a reliable groove, the beat grid's phase, 15 ms at most); a
  steady groove gives a whole number of beats (Human 12.80 s = 32 beats of 0.400 s, Growing Pains 12.63 s = 20 of
  0.631 s). *Baked seam*: the last second is an equal-power crossfade (`cos`/`sin`, level-matched to the equal-power
  target so alike sources do not bump 3 dB) of the source just before the end into the source just before the start,
  so the loop's next sample is the source's own next sample; the capture stream is periodic and every frame's history
  (the first frames' too) is read from it; the lanes are mixed with the same weights and the discrete onsets follow the
  louder source. The loop (frames, period, crossfade, source times, what the bake measured) is in the clip's header
  and `clips.json` (`loop`). *Played on through the wrap* (`ui/studio/clip_loop.py`): the transport counts passes
  (`cycles`, `unrolled`); the controller hands a loop fixture (`StudioFixture.loop`) the unrolled time
  (`StudioTransport.evaluation_time`); every evaluator (Bubble, Sphere, Extruded Bubble, Waveform, the engine-answer
  modes) steps its production logic on over the clip's ticks again, shifted whole periods (`shifted` on each
  `RecordedInputs`: times, onset serials and, for recorded engine answers, the onset query's `after_serial`
  argument), so no state resets. A rewind to the start (an edit, a seek, new answers) re-anchors to the start of
  the pass the instant is in, so it replays what it always replayed, never every pass played; `ExactReplay` drops
  checkpoints older than two passes and returns the re-anchored time, so a budgeted replay converges across a wrap
  exactly as before. *Primed workers*: a worker replays the loop's last 2 s (`PREROLL_S`) before the clip and the
  record keeps those ticks before the clip's origin (`Cycles` plays them once, as the first pass's head), so the Studio's
  history at the clip's start is the production replay's and a running loop's, and the engine's lanes at the start are
  a running loop's, not a cold start (measured: without it the first second
  of Bubble's overall lane sat at 0.008-0.014 against 0.33-0.45 steady; with 1 s of lead-in the lanes equal the
  converged third pass of an unbroken run, 2 s is the margin, +0.4 s of worker time on ~3.3 s, about +12%). A native
  recording, or a clip cut short by `seconds`, is not a loop and behaves as before. Why not 30 s clips: the best
  seam a 22-30 s loop offers gains at most 0.05 of onset correlation over a 12-16 s one on the same recordings (Human
  .87 -> .92, Growing Pains .66 -> .68; Rag Doll gets worse, .47 -> .34), while size and a re-analysis grow with the
  length. Measured (`tools/studio_clip_length_cost.py`, 6 Nov, other agents' load on the machine, one run each): a 30 s
  window is 1.99-2.42 MB against the loops' 0.86-1.01 MB, and a worker takes 1.9-2.2x as long (the loops' time includes
  the 2 s lead-in): Bubble 6.5-9.1 s -> 12.9-13.8 s, Extruded Bubble 3.7-4.2 -> 8.0-8.8 s, Waveform 6.0-6.4 -> 11.8-12.7 s,
  Sphere 2.6-2.8 -> 5.3-5.7 s, Spectrum 2.9-3.1 -> 5.9-6.1 s.
  Seam, measured (`.artifacts/evidence/studio/clip_loop/20261106_clip_loop/`): the loop's last 5 ms are the source's own to -37 / -46 /
  -57 dB (Human / Growing Pains / Rag Doll), the sample step across the join equals the source's own step, the crossfade
  holds the equal-power level within 0.23 dB, the 20 ms RMS changes 0.1-0.23 dB across the seam (the music's own 95th
  percentile is 4-8 dB), no spectral-flux burst follows it, and the beat grid steps -25 / -47 / -85 ms against the
  loops' own 95th percentile of 65 / 302 / 94 ms (Rag Doll has no steady beat; Growing Pains' triple hit wanders). The
  two sources the crossfade blends sit 0.6 ms (Growing Pains), 12 ms (Rag Doll) and 33 ms (Human, a weak groove) apart on
  the beat grid. The picture: at the wrap the frame-to-frame step of each mode's state (Growing Pains) is 0.06-1.8 against
  ordinary 95th percentiles of 0.09-71, and the old restart at zero is 21-299 times larger for eight of the nine
  recorded-input modes (Bubble 29x, Sphere 73x, Extruded Bubble 299x, Waveform 48x, Spectrum 225x, Extruded Spectrum
  229x, DevCurve 21x, Neon Lake 167x). Oscilloscope's carried beam state (afterglow, ghosts, flare, drive, tone) settles
  inside the lead-in, so a restart no longer moves it (its jump was the trace, which the baked audio now keeps
  continuous); DevCurve's travelling highlights respawn when their own travel ends and are left out of the step.
  Evidence: `tools/studio_clip_loop_report.py` (audio seam), `tools/studio_clip_loop_wrap.py` (the picture at the
  wrap for all nine Studios with recorded inputs), `tests/test_studio_clip_loop.py`.
- **Recorded engine answers (engine-processed modes).** A mode whose step consumes the engine's *own processing*
  (the Spectrum family, Spectrum, Extruded Spectrum and Neon Lake: `consume_engine_bars` ticks the engine and reads its
  smoothed, shape-processed bars, all on the process clock; Neon Lake's capture also reads the transient bus's onsets,
  the musical level and intensity and the pre-AGC analysis spectrum) cannot be served authored lanes and must not pin
  the clock in process. All use `ui/studio/engine_answers.py`; their worker modules and adapters only name the mode. Its worker stands
  `replay_engine.EngineAnswerRecorder` in for the engine during each production `logical_tick` and records every
  answer the engine gave the step (JSON via `encode_answer`, exact for floats; a getter answering twice differently
  in one tick raises). Getters a mode reads only under some mode-owned setting are named as the mode's
  `conditional_reads` and recorded every tick (Neon Lake's Terrain Reaction reads the musical level and the analysis
  spectrum only while it is on), so switching that setting on stays a mode-owned edit served from the record. The
  Studio runs the mode's production step in process with `RecordedEngineAnswers` standing in
  for the engine (commands inert; a read the record lacks falls through and is counted, and the parity tests require
  zero). Settings split into **engine-owned** (they change the answers: a new key re-runs the worker, the previous
  answers and their own engine values staying on screen until it lands) and **mode-owned** (exact and instant). The
  split is proven in both directions on the production replay; it is derived, not listed: engine-owned are the
  mode's keys the production source projection hands the engine (the Spectrum source keys and the technical
  analysis), mode-owned everything else the mode stores (spec controls, Custom rows, shared bar and rainbow families).
  A mode whose step reads the engine's lanes beyond its shaped bars (`EngineAnswerMode.production_lanes`: DevCurve,
  Oscilloscope, Neon Lake) records on `feature_replay.ProductionLaneEngine`: every lane, the transient bus, its onsets
  and events, the musical level and intensity and the analysis spectrum re-analysed from the clip's PCM through the
  production DSP under the edited values, so Sensitivity, the floors, Gain and Block Size move these Studios as they
  move the live engine (the others' shaped bars were always re-shaped from the PCM). Recorded clips only: a synthetic
  fixture keeps its authored lanes, since its held Quiet / Mid / Peak levels and scripted hits are references the
  production DSP's own normalisation would flatten (measured 6 Nov: a quiet bed reads at full scale, and the
  transient fixture's isolated kick no longer reaches DevCurve's accents). Its frames equal the production
  replay on re-analysed lanes tick for tick (`tests/test_studio_audio_analysis_response.py`, with the old
  recorded-lanes path as the negative control). Scale caveat: one analysis block per 11 ms tick, where live analyses
  every capture callback, so absolute levels approximate. Worker cost (6 Nov, the three shipped 12 s clips, frozen
  settings, best of two, Ryzen 9 5900X at ~12% load; recorded lanes -> production lanes): DevCurve 9.9 -> 11.0 s
  (+11%), Oscilloscope 3.8 -> 5.1 s (+35%), Neon Lake 5.8 -> 8.2 s (+41%), Bubble 10.1 -> 12.3 s (+22%), Extruded
  Bubble 4.2 -> 5.2 s (+25%), Sphere 2.0 -> 3.9 s (+100%, about 1.3 s a clip). A re-analysis runs once per release.
  DevCurve normalises its body to the song, so Sensitivity / floor / Gain move its picture only subtly, as live
  (evidence `.artifacts/evidence/studio/completion/20261106_completion/audio_analysis/`).
  Synthetic fixtures of such a mode are generated *audio* through the same worker, so engine-owned edits stay
  truthful for them too; each synthetic frame carries what a recording carries: its audio's analysis spectrum (the
  live engine's band math), the score's hits as the transient bus's onsets, and the loudness on the real-music scale
  (`PassageIntensity`), with presence against its own 6 s running level. The store's 3D Detail tier (`scene3d_detail`) and, for a reflecting mode, the environment
  photograph reach the presentation as production hands them (both the worker's in-process replay and the Studio).
- **A mode with its own logical step (DevCurve).** DevCurve's tick runs its descriptor hook
  (`tick_pipeline.dispatch_devcurve_field`) on the engine's live answers (pre-AGC control lanes, transient lanes,
  musical level and intensity, the source frame), so it uses the same recorded engine answers: the worker records
  everything the engine answered the whole production `logical_tick`, and `EngineAnswerEvaluator._step` runs what
  `logical_tick` runs, the mode's hook included, between `consume_engine_bars` and the capture. Engine-owned are the
  technical (audio analysis) values, each re-analysed from the clip's PCM (production lanes, above), so every offered
  one moves DevCurve's frame here as live (`Docs/Reference/Visualizer_Reference.md` → Audio Analysis controls per
  mode); the split is proven both ways (`tests/test_devcurve_studio.py`). Its schema follows
  DevCurve's Settings buckets: Layers (Settings' Shaper: one group per layer with its Custom-row values, the
  shape-editor nodes, Add / Remove Node and Settings' stack re-ranking as `follow`), Motion & Swell (Core and the
  analysis) and Foreground & Ghost (with the rainbow). Each layer group traces that layer's **Body** (over its body
  top), **Accent** (over its reserved accent room) and **Swell**; Core traces Passage, Reaction and the strongest
  Swell; Audio Analysis the served band shares and loudness. All are reads of the evaluator's own runtime and served
  answers (`DevCurveStudioEvaluator.measurements`), never saver work. Instruments: no DevCurve value is a true
  interval, so none is a Quiet/Peak A/B; the stack order is a segmented count.
- **Arrays answered by identity (Oscilloscope).** Oscilloscope's capture reads the capture history (a read-only NumPy
  array the engine keeps as the *same object* while its capture serial holds), the 256-sample waveform, onsets after
  the runtime's serial, the musical level and intensity, the analysis spectrum and the history's rate; its frame
  runtime rebuilds the trace only for a new history object. The recorder therefore numbers every array an answer
  carries by identity (`replay_engine.RecordedArrays`: one number per distinct object for the whole recording, a
  reference held so an id is never reused) and the answer names the number; the worker writes the arrays' raw bytes
  to a binary sidecar beside its JSON (`<output>.arrays`, read before the job's folder is removed), and the Studio
  serves one read-only `np.frombuffer` view per number (`served_arrays`), so a held history is the same object tick to
  tick. `StepState` shares the recorded arrays instead of copying them, so a rewound step still holds the object the
  view serves. Without a pool an array answer is still refused, so a mode whose answers hold no arrays records
  exactly as before. A shipped clip: about 830 distinct 4096-sample histories (13.6 MB sidecar), 7.6 MB of answer
  JSON, about 0.1 s to load. Engine-owned are the technical values (re-analysed from the PCM: every offered one moves Flare
  and Drive, as live);
  every `osc_*` key is mode-owned. Workspaces follow the buckets: Trace (Display), Beam & Screen,
  Reaction (with the analysis). Traces, read from the frame on screen (`OscilloscopeStudioEvaluator.measurements`):
  **Level** (the live trace's swing in its display's own units), **Afterglow** (the newest afterglow trace's
  brightness against a fresh one) and **Ghosts** (held traces against the capacity), **Flare**, **Drive**, **Tone**;
  the transport overview is the recorded loudness (`EngineAnswerEvaluator.timeline_measure`). No value is a true
  interval: every slider is one scalar.
- **Recorded-input modes re-analyse a clip for the Audio Analysis values (Bubble, Extruded Bubble, Sphere).** Their
  clip workers replay on `ProductionLaneEngine` (the events they record are those the production scheduler accepted,
  `feature_replay.fed_events`) and their adapters name the values a clip's analysis depends on
  (`clip_analysis_keys`: the mode's offered technical keys; clip caches are keyed by them). After a commit, undo or
  redo that changes them, the controller analyses the clip on screen again in the background
  (`StudioController._refresh_clip_analysis`); the previous inputs stay on screen until the new ones land at the same
  instant, and those keys' sliders update on release. Synthetic and held fixtures are authored lanes in every mode
  and do not react to Audio Analysis (the engine-answer modes' note above says why).
- **Exact replay without a stall (`ui/studio/exact_replay.py`).** The engine-answer evaluators and Waveform's share
  one mechanism, `ExactReplay`. Such an evaluator never re-configures its controller for a mode-owned edit:
  `replay_engine.StepState` captures the production step state (controller, logical tick state, presentation state
  and the mode runtimes they hold; locks, QObjects and the engine view shared; Waveform: its frame runtime, the
  compiled configuration shared) right after configuration and at checkpoints (every 90 ticks, for the current values
  and the last two), and a rewind restores the pristine capture plus the production restyle (Waveform: the runtime's
  own `reset` and `configure`), or the latest checkpoint of the same values (undo, seek back). The rewound replay
  equals the production replay. The controller sets a frame budget (`set_frame_budget`,
  `StudioController.EVALUATION_BUDGET_S`); a replay that does not fit continues on the next frames (`converging`, the
  controller requests them) while the last frame shown stays on screen (the live-applied one after a click or a
  drag), and when a rewind alone used the frame's budget, stepping starts on the next frame. What remains per commit
  is one configuration build (an engine-answer mode's production settings model, Waveform's compiled settings) on the
  commit frame; a single production tick cannot be split.
- **A change while playing restarts the pass (7 Nov, `exact_replay.PassRestart`).** The replay of a change (an edit,
  undo/redo, new answers or inputs landing, a new extent) begins at the pass start or a checkpoint, while a playing
  transport moves on. Under the budget it chased a moving instant and the frame stayed frozen until the loop wrapped
  (operator, Waveform Ribbon). Measured on Human at 6 s with no rendering: Waveform 3.6 s, DevCurve through the
  wrap. The one-shot evaluators (Bubble, Sphere, Extruded Bubble) replayed it in one evaluation (Bubble 1.5 s). The
  history at the current instant under new values exists only by replaying from the start, so it cannot be
  recomputed in place. Instead, while playing (`set_playing`, no live gesture), a change whose replay would step more
  than `RESTART_BACKLOG_S` of history replays to the start of the pass. The controller takes the restart
  (`take_restart`) and puts the transport there (`StudioTransport.restart_pass`). While any exact replay converges,
  the transport holds (`StudioTransport.hold`) instead of running ahead. A seek back, a paused transport and a short
  replay behave as before. What remains is the clip's analysis lead-in (Waveform about 0.7 s), shown as
  "Updating…" (`previewBusy`; "Analysing…" while the clip on screen or the answers are analysed).
  `tests/test_studio_change_while_playing.py` covers every Studio-backed mode.
- **Source selection: latest wins (7 Nov).** Asking for a source retires every other clip analysis
  (`_retire_other_clip_jobs`), and the picker names an analysing clip at once (`pendingFixture`). A job that already
  finished inside its loader is never registered as running, which would otherwise block the clip for good.
- **Sidecar log (`logs/screensaver_studio.log`, 7 Nov).** One INFO line per event, written on the frame and job edges
  (no timer): each source selection (accepted, analysing first, or rejected), each clip analysis (started, finished
  and selected or superseded, failed, cancelled with its reason, all with durations), each replay after a change
  (trigger, duration, frames, restarted or resumed), and each preview gap longer than `PREVIEW_GAP_LOG_S` while the
  preview should move, with its cause.
- **Drags without a model build per frame (engine-answer modes).** A live gesture dragging one numeric key that the
  production build hands through verbatim takes the latest full build with that one entry replaced
  (`EngineAnswerEvaluator._mode_kwargs_for`). A key counts as such only after a full build in this Studio differed
  from the previous one in that key alone and produced exactly that key with exactly its value; anything else builds.
  The patched kwargs are never cached, so the release replays from a full build. Every Spectrum-owned slider passes
  (`tests/test_spectrum_studio_drag_model.py`).
- **Background analysis hooks.** An evaluator that analyses in the background exposes `set_invalidate(callback)`
  (the controller re-evaluates and refreshes the transport when a result lands), `analysing`, and
  `timeline_revision` (the transport overview is recomputed when it changes). A failure is reported through
  `analysis_failure` (the controller shows it once as a notice with **Retry**, `retry_analysis`; the previous
  answers stay on screen); a failed clip analysis offers Retry the same way. A background clip load that lands
  selects itself only while it is still the source last asked for (the user's choice, or the default before any).
  Its "Preview source" notice is withdrawn when the user picks another source (other notices stay).
- **Structural edits.** A schema `StudioAction` on a row (`StudioProperty.actions`) or under a group
  (`StudioSchema.group_actions`) is answered by the adapter's `structure_edit(action_id, values)` as one undoable,
  admitted change set, or None while not admissible (the button is disabled). `StudioSchema.row_label` titles a row
  from the current values (an element whose meaning moves with it). Spectrum: Add Node (widest gap, on the current
  silhouette), Remove Node per node row, and lane swaps per boundary row, under Settings' shape-editor rules; the
  Studio reaches every state Settings' shape editor saves (`tests/test_spectrum_studio_shape_editor.py`). Neon Lake:
  the same for its Frequency Response shape and for Terrain Reaction's shaper (one record: nodes two to five, the
  first lane boundary pinned at the shoreline by `normalize_terrain_shaper`), and the terrain editor's whole-record
  edits (Extend Toward Horizon, Reset Terrain) on the authored heightfield. The heightfield's cells are painted with
  the shared brush (below); the session carries the record (undo, save, Save To <Preset>) through an
  `instrument_only` schema marker.
- **Brush (`capabilities().brush`, Neon Lake's terrain).** The viewport toolbar's brush button (or B) turns the
  viewport into a brush: left-drag paints, right / middle drag still pans and the wheel zooms; a floating panel holds
  the mode (Raise, Lower, Flatten, Water), Radius, Strength, Falloff and Flatten Height (tool state, never saved), and
  the footprint (reach ring, dashed core) is drawn on the ground under the pointer. The adapter's `BrushTarget` names
  the record and picks a presented-frame point on the drawn ground through the frame's production camera (Neon Lake:
  `basin_view` at the card's content field, the ray met with `neon_terrain_surface`). Pointer points are held and
  painted at the next frame start, all of them in order (the path decides a stroke, not the event rate), with one
  preview per frame; release commits once (one save, one undo entry, "Paint Terrain (<mode>)"); Esc drops the stroke.
  During a stroke points are picked on the ground as it was when it began. `tests/test_visualizer_studio_parity.py`
  proves the pick against the production camera, the coalesced stroke, its save through Settings' owners, reload and
  Undo; `tools/waveform_studio_capture.py --brush` renders a stroke (evidence
  `.artifacts/evidence/studio/completion/20261106_completion/brush/`).
- **Conditions.** A property's `when` terms must all hold, its `when_any` terms at least one (Settings' former OR
  rules, e.g. Bubble's particle rows while any population is on); `ui/studio/schema.condition_hidden` is the one
  evaluation the bridge's `conditionHidden` uses.
- **Switch rows.** Every boolean control is the shell's one `SwitchRow` (an `Item`: a `Row` ignores the `x` of its
  children, which once pushed the click area past the label and made every switch unclickable, 6 Nov). A row whose
  `when` condition fails is hidden (`conditionHidden`). `tests/test_studio_switch_rows_click.py` clicks the rendered rows
  through real window events on the hidden offscreen surface and reads the canonical store.
- **Capabilities.** `StudioCapabilities(viewport, camera, handles, objects)`; the default is a plain 2D live preview
  with a scene-object list. A flat mode declares no camera and no handles and the shell then shows no navigation,
  view readout, Keep View/Reset or handle overlay and never calls `navigation()` / `scene_handles()`.
  `objects=False` drops the scene-object list (the viewport takes its width). `viewport=False` gives an
  inspector-only Studio with no renderer.
- **Presented extent.** An evaluator whose logical step reads the card's world extent (for example Bubble's domain)
  exposes `set_viewport_extent`; the controller passes the extent actually presented before each evaluation and
  re-evaluates when a filling framing's extent follows a viewport resize.
- **Framings.** `framings(card_extent, card_style)` lists presentation frames, first = default unless
  `default_framing()` names one. Framed modes use `ui/studio/framed.py:card_framings`: **Fill** (default; the live
  card's world at the live card's scale, grown to the viewport's shape by `fill_extent` so it never shows less world
  than the card), **Live Card** (the card exactly, letterboxed), and 16:9 / 21:9 cards containing the live card's
  world. An empty tuple fills the viewport with no letterbox.
- **Navigation and camera saving.** `navigation()` maps orbit/zoom/dolly/pan onto the mode's own camera values.
  `saved_with_camera_policy` keys persist only when the store's camera policy allows; `saved_on_keep` keys persist on
  Keep View; anything else is preview only.
- **Previews.** `preset_preview` (starting-point tiles) and `card_preview` (rendered cards at the Quiet or Peak
  endpoint) render once per commit while visible, never per frame.
- **Handles.** `scene_handles(...)` projects direct-manipulation handles through the mode's real camera (or item
  mapping for 2D); an `"xy"` handle is one undoable two-axis move.

Every adapter carries a registry-derived full-coverage test (every canonical control reachable), a production-parity
preview test and a Settings round-trip test, and is covered by the shared parity+ test
(`tests/test_visualizer_studio_parity.py`); see `Docs/TestSuite.md` → Visualizer Studio. A property whose path the
current values do not hold (an unused optional element, such as a curve-node slot) is hidden.

### Drags are batched

Every drag instrument (value sliders, Quiet/Peak lanes, lifecycle grips, response curves, XY handles, colour pickers,
gradient nodes) goes through `previewValue` / `previewColour` / `previewGradient`, which only hold the newest value
per target. The controller applies the held values at the next frame start (`on_frame`, the surface's existing
`afterAnimating` edge; no timer), latest wins, so the session previews at most once per rendered frame however fast
the pointer moves. An applied preview re-shows only the properties stored under the gesture's keys; the whole values
map, the starting-point state and the condition map are rebuilt when the gesture ends (or at once when a changed key
decides another property's visibility). The slider and its readout follow the pointer locally at once. Release
applies the last held value and commits once (one save, one undo entry); Escape drops the held value and restores;
keyboard steps and typed values commit per step. An evaluator can name keys whose preview follows only on release
(`release_only_keys`): the engine-answer modes' engine-owned keys, whose analysis runs once on release (a live
gesture evaluates with `exact=False`, which never starts one). Their sliders say "Updates On Release" while dragged.
`tools/studio_drag_profile.py` measures a drag (`Docs/Reference/Harness_Index.md`): Spectrum's mode-owned drag frames
no longer build the settings model (evaluation per frame 29.7 -> 7.3 ms median on a loaded machine), and Waveform's
release replay spreads over frames within the budget (one 222 ms evaluation -> about 8.4 ms per frame); evidence
`.artifacts/evidence/studio/followups/20261107_followups/drag_profile/`.

A drag holds until release. Drag instruments that sit in a scrolling panel set `preventStealing: true`: the value
slider, the colour picker's field and hue bar, gradient nodes, and the response curve in the sideways-scrolling
dock. Without it, a vertical wobble past the drag threshold handed the press to the panel's scroll view, and the
slider let go mid-drag (operator, 6 Nov: "sliders snap out of being dragged in mid motion"; it reproduced on every
mode at the first wobble). `tests/test_studio_drag_coalescing.py` drags every mode with a wobble, with a negative
control.

## 4. Settings link and the restore guarantee

- **Entry.** Every visualizer mode's Settings body is `build_studio_owned_mode_ui` (`ui/tabs/media/spec_mode_builder.py`,
  operator 6 Nov: migrate fully once each Studio has parity+): the preset row with its **OPEN STUDIO** button
  (`VisualizerPresetSlider.set_studio_launcher`, where Edit Preset was; offered on every curated preset and on Custom
  alike) and one sentence; no Settings control is kept beside them. Opened on a curated preset, the Studio shows that
  preset. The body's values (`body_keys`: the
  bucketed controls, each Custom row's keys and the bucketless controls a Custom row edits) live in the section-lazy
  cache `_<prefix>_lazy_values`, admitted as the model admits them, with nothing built; the technical (audio-analysis)
  controls and the page's shared Bar Appearance / Rainbow rows keep their canonical widgets as value owners in the
  body's never-shown holder, so load/collect/save, preset switching and Custom snapshots run through unchanged owners.
  Neon Lake's terrain, the last Settings-only control, is painted with the Studio's brush since 6 Nov; its Settings
  section and editor are retired.
- **Parity+ proof.** `tests/test_visualizer_studio_parity.py` derives every mode (each descriptor with a registered
  adapter) and every control from the registries: spec bucket entries and Custom-row keys, the offered technical
  controls, and the shared families (Rainbow wherever owned; Bar Appearance where the mode `draws_bars`), each a Studio
  property with the registry's range, choices and condition; every preset-row control has a Studio action; plain and
  Custom-row edits through the bridge save and reload through a never-shown `VisualizersTab`; conditional rows hide
  live; negative controls drop a property per category; every authored heightfield is the brush's target, and a brush
  stroke saves once, reloads and undoes exactly. Before the flip it also proved each Studio against the body
  users had (every row the body collected and every row its spec and hand-written conditions hid; commit `db7468ab`).
- **Canonical save.** `VisualizerSettingsStore.commit` loads the values into the mode body with signals blocked. On
  Custom it then runs the tab's own `_force_visualizer_preset_to_custom` and `_save_settings_now`. On a curated
  preset there is **no automatic switch to Custom** (operator, 6 Nov). The edit is held as a *draft*:
  - It lives in Settings' widgets only, with nothing saved and the preset still selected.
  - The session reads it back as the canonical save would store it (`_draft_config`: the tab's own collect and
    merge, read as Custom, never written).
  - It is settled when the user saves explicitly (Save To <Preset>) or when the session would leave that preset.
    The user's own closes (Close button, Esc, title-bar close, window X / Alt+F4), a preset switch and a mode
    switch show Settings' prompt **Unsaved Preset Changes**, with four choices:
    - **Overwrite <Preset>** writes the changed keys into its file, the same patch as Save To. It is left out when
      the file is read-only.
    - **Save As New Preset** runs Settings' own Save Preset As file dialog into the presets folder; the new preset
      is then selected.
    - **Place In Custom** does what every edit used to do.
    - **Discard** reloads the preset and writes nothing.
  - Closing the prompt without a choice keeps the Studio open.
  - Edits returned to the preset's own values are dropped without asking.
  - Exits nobody can answer (application quit, Settings destroyed, a lost window, a failure, a programmatic
    `close()`) place the draft in Custom, so nothing is lost.

  The mode's shared families that
  Settings keeps outside the mode body (bar Fill / Border / Border Opacity, the per-mode rainbow toggle and speed)
  are loaded into their owning Settings widgets first, so the tab's own save collects them. The Studio never writes
  the settings map directly. Camera turn/tilt go through the framed camera editor's pose authority.
- **Preset menu.** The header's preset picker offers Settings' own preset-row actions: Move To Custom (on a curated
  preset), Save Preset As… (on Custom, Settings' own file dialog) and, for authoring the curated presets themselves,
  **Save To <Preset>**. This replaced Settings' Edit Preset (the preset file opened in the OS editor), deleted on
  6 Nov 2026 once every visualizer mode had a Studio.
- **Save To <Preset>.** The store remembers the curated preset this session's edits came from: the preset the Studio
  opened on, the preset a held draft edits, or the preset Move To Custom was used from. Choosing another curated
  preset starts afresh; returning to Custom keeps it. The store also remembers the keys edited since. While a draft is
  held, or on Custom with such an origin, the menu offers Save To <that preset>. It writes only the edited keys whose value differs from
  what selecting that preset resolves (its own settings over the canonical defaults), plus the starting view when the
  view was edited and Include Camera View is on. It always asks first (Settings' `StyledPopup`; Cancel writes
  nothing), then patches the preset's own file through `core.settings.visualizer_preset_file.save_changes_to_preset`:
  the path comes from `get_preset_file_path`, every section the loader reads is patched in place (existing keys keep
  order and value, a new key goes in by the repair's ordering rule, inert keys and metadata stay), the file keeps its
  indentation, escaping, line endings and final newline, the result must load the written values, and
  `reload_presets` follows. A read-only location (an installed build) gives a clear message pointing to Save Preset
  As… and writes nothing. The slot that was selected stays selected (Custom with its values, or the preset, which
  now holds the edits and asks nothing more at close); the release mirror is not refreshed (an explicit
  release step). Opened on Custom, the origin is unknown and only Save Preset As… is offered.
- **Mode switcher.** Switching modes selects that mode's Settings page (as its pill would) and hands the Studio a new
  canonical store; only enabled modes with an adapter are offered.
- **Lifecycle.** One Studio at a time (`StudioController.active()`; a second open raises the first). Settings stays
  visible until the Studio has presented its first frame, then is concealed (never `QDialog.hide()`, which would end
  Settings' modal loop). The Studio window is application-modal.
- **Restore guarantee.** Every exit path (Close button, Esc, window X / Alt+F4, surface loss, open/present failure,
  application quit, Settings dialog destruction) reveals and refreshes the *same* Settings window (page, scroll and
  preset slider intact) right after the edit and playback stop, *before* clip jobs, the window and the models are
  retired, and again (idempotently) in a `finally`, so neither a failing nor a hanging teardown step can leave
  Settings concealed; a mode switch retires without revealing because the next session follows. Open failures show a
  "Studio Unavailable" popup over Settings.
- **Reveal re-exposes (layered window).** Settings is frameless and translucent, so Qt presents it as a layered window,
  which never receives `WM_PAINT`; Qt exposes it only from a show it initiated, and `WindowPresence` shows it natively.
  Without help the revealed window stays *not exposed* to Qt: it accepts input but never repaints (the 6 Nov "frozen and
  unclickable" stall: saves logged for 25 s after a clean reveal). `reveal` therefore follows the native show with
  `RedrawWindow(RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW)`, which makes Windows send the missing `WM_PAINT` so Qt
  exposes and repaints; the reveal log line carries `exposed=`. `tests/test_studio_exit_repaint.py` guards it.
- **Post-close input record (one-shot).** The 6 Nov 21:56 report was a UI frozen after closing a Studio that
  recovered by itself after ~18 s, with the process idle and Settings revealed `exposed=True`. Qt's own state
  cannot reproduce it: an offscreen-QPA probe with a real application-modal `StudioWindowSurface`, closed by a click
  on its Close button, leaves Settings active, unblocked and taking clicks. So each reveal arms
  `presence.RevealWatch`, which logs `[STUDIO] after reveal +N ms ...` lines:
  - Qt's and Windows' window state (modal, focus, active, mouse grab, foreground, capture, `WS_DISABLED`) at the
    reveal and when the Studio window is destroyed;
  - up to 12 native activation, button and key messages, with the window Windows sent each one to;
  - the first input Qt delivers to Settings, and how long after the reveal it arrived.

  It removes its filters at that first input, when Settings is destroyed, or 60 s after the reveal, so nothing runs
  at rest. Its Qt filter sits on Settings' own window, never the application. An application-wide Python filter is
  handed every Qt Quick item an event visits, and wrapping items PySide had not wrapped yet deleted a live Studio
  item in a later test (7 Nov).
- **Never hide the window from Python.** PySide holds the GIL through `QWindow.hide()`, and Qt's threaded render
  loop waits inside it for the render thread, which runs the viewport's Python (render-node release,
  `sceneGraphInvalidated`) when the non-persistent scene graph is invalidated: calling it from Python deadlocked the
  app with Settings concealed. `StudioWindowSurface.retire` queues the hide (and `deleteLater`) to the event loop,
  which runs them in C++ with the GIL released. The same rule holds for any other call that makes the GUI thread wait
  for the render thread.
- **Lifecycle record.** `[STUDIO]` INFO lines always reach the main log: open, shown, presented, Settings concealed,
  every commit / undo / redo, mode switch, failure, the close request with its path (flushed to disk before any
  teardown), each retirement step and the Settings reveal. `--studio` adds the `screensaver_studio.log` sidecar
  (`Docs/Guides/Logging_Guide.md`).

## 5. Tools

`tools/spectrum_studio_replay_budget.py` measures the Spectrum Studio's GUI-thread evaluation cost frame by frame
after mode-owned commits, undo, seeks and an engine-owned landing at the end of the longest shipped clip, checking
every landed frame against the production replay (`--budget 0` measures the former one-evaluation replay).
`tools/studio_clip_loop.py` searches, bakes and measures a clip's loop (`tools/build_studio_clips.py` builds the shipped
clips with it; `--check` verifies them); `tools/studio_clip_loop_report.py` measures the seam of the shipped clips (sample
step, RMS, spectral flux, beat grid, against a hard cut of the same loop and the former clips);
`tools/studio_clip_loop_wrap.py` drives every Studio's evaluator through a clip's wrap on a fake transport clock and
measures the frame-to-frame step of the mode's state across it against the steps around it and against the former
restart at zero (no window, no renderer); `tools/studio_clip_length_cost.py` measures what a longer clip costs (size and
each worker's time).
`tools/waveform_studio_capture.py` renders any registered Studio (`--mode`, Waveform by default) through the hidden
`OffscreenStudioSurface` against an in-memory store (nothing is saved), writing one PNG per workspace plus frame and
evaluation timings. It never shows a window. Command examples live in `Docs/Reference/Harness_Index.md`.

## 6. Adding an adapter

1. Read `Docs/Guides/Visualizer_Change_Checklist.md`; the canonical control registry
   (`core/settings/visualizer_mode_settings.py`) stays the value and range authority.
2. Implement the adapter in `ui/studio/<mode>_adapter.py` on the mode's production logical owner and renderer;
   framed 3D modes reuse `ui/studio/framed.py` and the shared framed camera (`core/settings/framed_camera.py`).
3. Register one line in `ui/studio/registry.py`.
4. Add the coverage, parity and Settings round-trip tests; render evidence with the capture tool.
5. The mode's builder is `build_studio_owned_mode_ui` with one plain sentence; `tests/test_visualizer_studio_parity.py`
   must pass for it (a control with no Studio home is a missing instrument to build, never a Settings section).

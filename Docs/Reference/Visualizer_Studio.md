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
| `ui/studio/controller.py` | `StudioController` (single active instance, open → present → retire lifecycle) and `StudioBridge`, the only object QML sees. Bridge slots are plain methods (no `result=`), per the QML signal → result-slot crash rule. |
| `ui/studio/viewport.py` | Inline `QSGRenderNode` that draws the adapter's renderer straight into the window framebuffer on the render thread (no readback, no per-frame texture copy). It applies the viewport slot's scene-graph clip (scissor), so a frameless mode that overflows its card in production (Extruded Spectrum, Sphere: up to the window) reaches the slot's edge, never the Studio chrome. Renderer created lazily and released on the render thread on `sceneGraphInvalidated` / node release. Snapshots (tiles, rendered cards, Copy Frame) use a second renderer instance, at most one per frame and only on request. |
| `ui/studio/transport.py` | Play/pause/scrub/loop on the Studio's own time. No timer: it advances on the surface's `afterAnimating` frame start and requests another frame only while playing. |
| `ui/studio/surface.py` | `StudioWindowSurface` (visible window) and `OffscreenStudioSurface` (hidden `QQuickRenderControl` host used by tests and the capture tool). Same shell, same signals (`frameStarted`, `presented`, `closeRequested`, `lost`, `failed`). |
| `ui/studio/settings_link.py` | `open_mode_studio` and `VisualizerSettingsStore`, the canonical store over the Visualizers tab (see §4), including Save To <Preset>. |
| `core/settings/visualizer_preset_file.py` | Shape-preserving edits of an authored preset file (section merge, in-place patching, source-like formatting, `save_changes_to_preset`), shared by the preset repair tool and the Studio's Save To <Preset>. |
| `ui/studio/presence.py` | `WindowPresence`: conceal/reveal the *same* Settings dialog without ending its `QDialog.exec()` loop (native `SW_HIDE` on Windows; zero opacity plus off-screen move elsewhere). |
| `ui/studio/framed.py` | Shared pieces for 3D (and card-presented) adapters: production presentation resolver and uniform aperture scale, `card_framings` / `live_card_framings`, `camera_navigation` over the shared framed camera, `orbit_navigation` for a free-orbit mode (the descriptor's `view_orbit_settings` only), `QuickModeRenderer` wrapping a production Quick renderer and `ContractModeRenderer` handing it the production render-frame contract (pixel ratio from the item mapping, so a letterboxed live card presents at the true DPR). |
| `ui/studio/engine_answers.py` | The Spectrum family's recorded engine answers, mode-neutral (`EngineAnswerMode(mode_id)`): synthetic audio, the out-of-process `extract`, recorded inputs, the per-mode answer cache, `start_clip_load` and `EngineAnswerEvaluator` (the production step in process, rewinds, checkpoints, frame budget). The engine-owned / mode-owned split follows from the production source projection (`source_config_applier`). |
| `ui/studio/spectrum_shape.py` | The Spectrum family's shape editor as Studio rows, admission and structural edits (add / remove node, lane swap), by key prefix (`ShapeKeys`). |
| `ui/studio/theme.py`, `colour.py` | Chrome tokens derived from the active Settings theme with enforced contrast; display ↔ linear colour conversion for instruments. Scene colours never pass through the theme. |
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
  visualizer is never disturbed; the finished job is released after its signal returns, never inside it. Every
  Studio lists the shipped clips (`assets/production/studio_clips`) first, then a checkout's own recordings.
- **Recorded engine answers (engine-processed modes).** A mode whose step consumes the engine's *own processing*
  (the Spectrum family, Spectrum and Extruded Spectrum: `consume_engine_bars` ticks the engine and reads its smoothed,
  shape-processed bars, all on the process clock) cannot be served authored lanes and must not pin the clock in
  process. Both use `ui/studio/engine_answers.py`; their worker modules and adapters only name the mode. Its worker stands
  `replay_engine.EngineAnswerRecorder` in for the engine during each production `logical_tick` and records every
  answer the engine gave the step (JSON via `encode_answer`, exact for floats; a getter answering twice differently
  in one tick raises). The Studio runs the mode's production step in process with `RecordedEngineAnswers` standing in
  for the engine (commands inert; a read the record lacks falls through and is counted, and the parity tests require
  zero). Settings split into **engine-owned** (they change the answers: a new key re-runs the worker, the previous
  answers and their own engine values staying on screen until it lands) and **mode-owned** (exact and instant). The
  split is proven in both directions on the production replay; it is derived, not listed: engine-owned are the
  mode's keys the production source projection hands the engine (the Spectrum source keys and the technical
  analysis), mode-owned everything else the mode stores (spec controls, Custom rows, shared bar and rainbow families).
  Synthetic fixtures of such a mode are generated *audio* through the same worker, so engine-owned edits stay
  truthful for them too. The store's 3D Detail tier (`scene3d_detail`) and, for a reflecting mode, the environment
  photograph reach the presentation as production hands them (both the worker's in-process replay and the Studio).
- **A mode with its own logical step (DevCurve).** DevCurve's tick runs its descriptor hook
  (`tick_pipeline.dispatch_devcurve_field`) on the engine's live answers (pre-AGC control lanes, transient lanes,
  musical level and intensity, the source frame), so it uses the same recorded engine answers: the worker records
  everything the engine answered the whole production `logical_tick`, and `EngineAnswerEvaluator._step` runs what
  `logical_tick` runs, the mode's hook included, between `consume_engine_bars` and the capture. Engine-owned are the
  technical (audio analysis) values; in the replay most of them leave DevCurve's lanes unchanged (the clip carries
  the pre-AGC lanes), and the split is still proven both ways (`tests/test_devcurve_studio.py`). Its schema follows
  DevCurve's Settings buckets: Layers (Settings' Shaper: one group per layer with its Custom-row values, the
  shape-editor nodes, Add / Remove Node and Settings' stack re-ranking as `follow`), Motion & Swell (Core and the
  analysis) and Foreground & Ghost (with the rainbow). Each layer group traces that layer's **Body** (over its body
  top), **Accent** (over its reserved accent room) and **Swell**; Core traces Passage, Reaction and the strongest
  Swell; Audio Analysis the served band shares and loudness. All are reads of the evaluator's own runtime and served
  answers (`DevCurveStudioEvaluator.measurements`), never saver work. Instruments: no DevCurve value is a true
  interval, so none is a Quiet/Peak A/B; the stack order is a segmented count.
- **Exact replay without a stall.** Such an evaluator never re-configures its controller for a mode-owned edit:
  `replay_engine.StepState` captures the production step state (controller, logical tick state, presentation state
  and the mode runtimes they hold; locks, QObjects and the engine view shared) right after configuration and at
  checkpoints (Spectrum: every 90 ticks, for the current values and the last two), and a rewind restores the
  pristine capture plus the production restyle, or the latest checkpoint of the same values (undo, seek back). The
  rewound replay equals the production replay for every mode-owned key. The controller sets a frame budget
  (`set_frame_budget`, `StudioController.EVALUATION_BUDGET_S`); a replay that does not fit continues on the next
  frames (`converging`, the controller requests them) while the live-applied frame stays on screen. What remains per
  frame is one production settings-model build per new set of values (on the commit frame) and the budget.
- **Background analysis hooks.** An evaluator that analyses in the background exposes `set_invalidate(callback)`
  (the controller re-evaluates and refreshes the transport when a result lands), `analysing`, and
  `timeline_revision` (the transport overview is recomputed when it changes). A failure is reported through
  `analysis_failure` (the controller shows it once as a notice with **Retry**, `retry_analysis`; the previous
  answers stay on screen); a failed clip analysis offers Retry the same way. A background clip load that lands
  selects itself only while it is still the source last asked for (the user's choice, or the default before any).
- **Structural edits.** A schema `StudioAction` on a row (`StudioProperty.actions`) or under a group
  (`StudioSchema.group_actions`) is answered by the adapter's `structure_edit(action_id, values)` as one undoable,
  admitted change set, or None while not admissible (the button is disabled). `StudioSchema.row_label` titles a row
  from the current values (an element whose meaning moves with it). Spectrum: Add Node (widest gap, on the current
  silhouette), Remove Node per node row, and lane swaps per boundary row, under Settings' shape-editor rules; the
  Studio reaches every state Settings' shape editor saves (`tests/test_spectrum_studio_shape_editor.py`).
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
preview test and a Settings round-trip test; see `Docs/TestSuite.md` → Visualizer Studio. A property whose path the
current values do not hold (an unused optional element, such as a curve-node slot) is hidden.

## 4. Settings link and the restore guarantee

- **Entry.** `ui/tabs/media/spec_mode_builder.py` gives any spec-built mode with a registered adapter an **Open Studio**
  button in its preset row (`VisualizerPresetSlider.set_studio_launcher`, where Edit Preset was), so it is offered on
  every curated preset and on Custom alike; there is no second launcher in the Custom body. Opened on a curated preset,
  the Studio shows that preset. A mode whose every control is Studio-edited uses `build_studio_owned_mode_ui`: its
  body is only the preset row and one sentence. Its values live in the section-lazy cache with nothing ever
  built, and the technical (audio-analysis) controls keep their canonical widgets as value owners in a never-shown
  holder, so load/collect/save, preset switching and Custom snapshots run through unchanged owners.
- **Canonical save.** `VisualizerSettingsStore.commit` loads the values into the mode body with signals blocked, then
  runs the tab's own `_force_visualizer_preset_to_custom` and `_save_settings_now`. The mode's shared families that
  Settings keeps outside the mode body (bar Fill / Border / Border Opacity, the per-mode rainbow toggle and speed)
  are loaded into their owning Settings widgets first, so the tab's own save collects them. The Studio never writes
  the settings map directly. Camera turn/tilt go through the framed camera editor's pose authority.
- **Preset menu.** The header's preset picker offers Settings' own preset-row actions: Move To Custom (on a curated
  preset), Save Preset As… (on Custom, Settings' own file dialog) and, for authoring the curated presets themselves,
  **Save To <Preset>**. This replaces Settings' retired Edit Preset (the preset file opened in the OS editor), which
  remains only for modes that have no Studio yet (`Current_Plan.md` §9).
- **Save To <Preset>.** The store remembers the curated preset this session's Custom values came from (the preset the
  Studio opened on, a Studio edit made on a curated preset, which moves it into Custom, or Move To Custom from it;
  choosing another curated preset starts afresh, returning to Custom keeps it) and the keys edited since. On Custom
  with such an origin the menu offers Save To <that preset>: it writes only the edited keys whose value differs from
  what selecting that preset resolves (its own settings over the canonical defaults), plus the starting view when the
  view was edited and Include Camera View is on. It always asks first (Settings' `StyledPopup`; Cancel writes
  nothing), then patches the preset's own file through `core.settings.visualizer_preset_file.save_changes_to_preset`:
  the path comes from `get_preset_file_path`, every section the loader reads is patched in place (existing keys keep
  order and value, a new key goes in by the repair's ordering rule, inert keys and metadata stay), the file keeps its
  indentation, escaping, line endings and final newline, the result must load the written values, and
  `reload_presets` follows. A read-only location (an installed build) gives a clear message pointing to Save Preset
  As… and writes nothing. Custom stays selected with its values; the release mirror is not refreshed (an explicit
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
5. Replace the mode's builder body with `build_studio_owned_mode_ui` only after operator acceptance of that Studio.

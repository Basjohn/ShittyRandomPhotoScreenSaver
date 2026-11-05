# Visualizer Studio

Current owner reference for the reusable in-process authoring Studio (`ui/studio/`). It records what is true in
source now; open acceptance work (mock parity, hardware window checks, further adapters) lives only in
`Current_Plan.md` §7.1 and §9. The design rationale and the viewport decision are recorded in
`Docs/Audits/Waveform_Studio_and_Reactivity_Audit_2026-11-05.md` §4; the operator's interface concept is
`Docs/Audits/SRPSS_Waveform_Studio_Design_Pack_2026-11-03.zip`.

## 1. What it is

A Studio is a top-level Qt Quick window (`ui/studio/qml/StudioShell.qml`) opened from a Visualizer mode's Custom
body in Settings. It shows a live preview drawn by the mode's **production** renderer from the mode's **production**
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
| `ui/studio/viewport.py` | Inline `QSGRenderNode` that draws the adapter's renderer straight into the window framebuffer on the render thread (no readback, no per-frame texture copy). Renderer created lazily and released on the render thread on `sceneGraphInvalidated` / node release. Snapshots (tiles, rendered cards, Copy Frame) use a second renderer instance, at most one per frame and only on request. |
| `ui/studio/transport.py` | Play/pause/scrub/loop on the Studio's own time. No timer: it advances on the surface's `afterAnimating` frame start and requests another frame only while playing. |
| `ui/studio/surface.py` | `StudioWindowSurface` (visible window) and `OffscreenStudioSurface` (hidden `QQuickRenderControl` host used by tests and the capture tool). Same shell, same signals (`frameStarted`, `presented`, `closeRequested`, `lost`, `failed`). |
| `ui/studio/settings_link.py` | `open_mode_studio` and `VisualizerSettingsStore`, the canonical store over the Visualizers tab (see §4). |
| `ui/studio/presence.py` | `WindowPresence`: conceal/reveal the *same* Settings dialog without ending its `QDialog.exec()` loop (native `SW_HIDE` on Windows; zero opacity plus off-screen move elsewhere). |
| `ui/studio/framed.py` | Shared pieces for framed 3D adapters: production presentation resolver and uniform aperture scale, `card_framings` / `live_card_framings`, `camera_navigation` over the shared framed camera, and `QuickModeRenderer` wrapping a production Quick renderer. |
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
  separate process (`python -m ui.studio.<mode>_recorded_inputs`, via `QProcess`) through the production offline
  replay, so the running app's live visualizer is never disturbed; the finished job is released after its signal
  returns, never inside it. Clips are offered only from a source tree with `logs/visualizer_recordings/` (frozen
  builds offer none until shipped clips land; see `Current_Plan.md` §7.1).
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
preview test and a Settings round-trip test; see `Docs/TestSuite.md` → Visualizer Studio.

## 4. Settings link and the restore guarantee

- **Entry.** `ui/tabs/media/spec_mode_builder.py` adds an "Open <title> Studio" launcher to any spec-built mode with a
  registered adapter. A mode whose every control is Studio-edited uses `build_studio_owned_mode_ui`: the Custom body
  is only the preset row, one sentence and the launcher. Its values live in the section-lazy cache with nothing ever
  built, and the technical (audio-analysis) controls keep their canonical widgets as value owners in a never-shown
  holder, so load/collect/save, preset switching and Custom snapshots run through unchanged owners.
- **Canonical save.** `VisualizerSettingsStore.commit` loads the values into the mode body with signals blocked, then
  runs the tab's own `_force_visualizer_preset_to_custom` and `_save_settings_now`. The Studio never writes preset
  JSON or the settings map directly. Camera turn/tilt go through the framed camera editor's pose authority.
- **Mode switcher.** Switching modes selects that mode's Settings page (as its pill would) and hands the Studio a new
  canonical store; only enabled modes with an adapter are offered.
- **Lifecycle.** One Studio at a time (`StudioController.active()`; a second open raises the first). Settings stays
  visible until the Studio has presented its first frame, then is concealed (never `QDialog.hide()`, which would end
  Settings' modal loop). The Studio window is application-modal.
- **Restore guarantee.** Every exit path (close button, Alt+F4, surface loss, open/present failure, application quit,
  Settings dialog destruction) retires playback, the evaluator, GL resources and the window, and reveals and refreshes
  the *same* Settings window (page, scroll and preset slider intact). The reveal runs in a `finally`, so no teardown
  failure can leave Settings concealed; a mode switch retires without revealing because the next session follows.
  Retirement is logged under `[STUDIO]`. Open failures show a "Studio Unavailable" popup over Settings.

## 5. Tools

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

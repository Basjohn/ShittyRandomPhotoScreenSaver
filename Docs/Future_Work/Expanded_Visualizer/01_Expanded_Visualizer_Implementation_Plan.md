# 01 | Expanded Visualizer: SRPSS / MC Implementation Plan

**Prepared:** 2026-11-05. **Live tracked document since 2026-11-07** (extracted from the plans zip, which was never  
tracked; this file is the one source of truth). Reviewed 7 Nov against `a295697c` with the  
[Architecture Checklist](../../Reference/Architecture_Checklist.md); §0 below holds the phase ladder, gates, owners,  
dormancy, lifecycle, 2D/3D consistency, budgets and risks the review added. Sections A-J are the original plan,  
corrected where the review found drift.  
**Status (10 Nov): PARTIALLY IMPLEMENTED / STILL UNDER PHYSICAL ACCEPTANCE.** The original future-entry
gate below was superseded when the operator admitted Expanded Visualizer work. The canonical live authority
is `Current_Plan.md` §1 step 3 and §1A, not historical unchecked implementation boxes in this detailed plan.
M1/M2, the overlay and Fullscreen Edit functionality, and the M4 covered-display admission implementation
have landed; M2b's full width-ratio DSP transaction, M4 GPU-load measurements, M5 lifecycle evidence and M6
4K acceptance are not thereby completed. The original milestones remain as design/evidence checklists.
Do not restart earlier implementation phases or claim that an untested later gate passed.
**Original entry-gate rationale (5–7 Nov, historical):** Waveform physical acceptance and P-A host
extraction preceded admission. Later 3D work still follows the active `Current_Plan.md` order.  
**Supported visualizers (operator, 7 Nov):** every mode except Voxel Sphere (`sphere`) and Extruded Spectrum
(`extruded_spectrum`): Extruded Bubble (the first, the gate mode), Spectrum, Oscilloscope, Spline Curve (`devcurve`),
Bubble, Neon Lake (`shockwave_grid`) and Waveform Ribbon, each by one descriptor flag. Waveform Ribbon is already over
budget under game load at the card (41-44 fps); its full-display figures are recorded at M6 against §0.7 (its
live-tick cut is in flight on another branch); the flag carries no perf gate.  
**Products:** existing Standard SRPSS and existing Media Center (MC) sharing the current Quick scene. No additional screensaver window, no product fork.  
**Companion:** `Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md` begins after this plan's acceptance and reuses its proven presentation **semantics**, not the screensaver's physical window manager.

## 0. Phase ladder, prerequisites, owners and budgets (7 Nov review)

### 0.1 Prerequisites from the architecture checklist

| Checklist item | Must land before | Why |
| --- | --- | --- |
| **AC-02** Visualizer host binding extracted from `DisplayManager`; Media docking a declared placement policy | **M2** (the takeover transaction binds to the owner); M1's pure reducer may start on today's owner | The takeover state machine (§D) must be a sibling of one host-neutral Visualizer owner, not a fourth concern inside the 6k-line `DisplayManager`. Doing it afterwards moves the new code twice. |
| **AC-11** one 3D camera control contract (operator decision; **landed 7 Nov**, `Docs/Reference/Visualizer_Reference.md` → Live view pose) | a second mode opts into expansion | At full display the card is large and orbiting likely; Sphere and Extruded Spectrum now reset to their home view. EB (the first mode) already has the framed camera. |
| **AC-04** inactive-renderer release failure no longer blacks out the active mode (**landed 7 Nov**) | M5 (mode requests while expanded) | Capable -> incapable collapses and switches mode; a stuck release would black out the whole display, not a card. |
| **AC-09** one card border width resolver | M2 (expanded card chrome) | The expanded presentation variant must not inherit `DisplayManager`'s private copy. |

**Does not need:** AC-03 (application-service tier). Expansion intent is a settings value that the next display
generation re-evaluates once at its readiness edge (§B.8); nothing outlives a generation.

### 0.2 Phase ladder with entry and exit gates

Each phase has an entry gate (what must be true to start), an exit gate (measurable evidence that closes it) and the
owner that signs it. The original milestones (§H) keep their checklists; this table binds them.

| Phase | Entry gate | Exit gate (evidence) | Signs |
| --- | --- | --- | --- |
| **P-A** AC-02 host binding | Waveform accepted; `Current_Plan.md` admits P-A | AC-02's regression bar green; Edit/Arrange parity maps byte-identical; `DisplayManager` no longer constructs the owner | lead |
| **M0** baseline | P-A merged; operator admits plan 01 | EB baseline receipts at canonical, wide/tall and display-sized views, one and two monitors, idle and game60: fps, tick median/p90, GIL share, frame age, lease counts; written to `.artifacts/evidence/expanded_visualizer/baseline/`; no Visualizer code changed | lead |
| **M1** capability + persistence + reducer | M0 receipts exist | all pure reducer tests green incl. stale generation, duplicate glyph, Edit cancel, topology loss; `replace_visualizer_runtime_preset_state` round-trips the intent; no dormant-mode import (import scan) | agent |
| **M2** full-display viewport | M1 green; AC-02, AC-09 merged | production-host renders at 16:9, 16:10, 21:9, portrait, mixed DPR show the Visualizer card near the display's visible extents (inset by only what the card's own chrome needs plus a 2 px gap, amended 7 Nov; never the R-63 overscanned window) with its chrome; reactivity packet digests identical to M0 on recorded clips for every capable mode; ordinary rect round-trips to the byte | lead + operator look |
| **M2b** Spectrum bar count at full display | M2 accepted | expanded bar count = card bar count x the width ratio (clamped to the DSP maximum), so bar width stays as authored; the DSP band layout is recomputed at the expand and collapse edges behind a fade (never a jump); Spectrum's digests differ at full display by design (per-band history re-mapped), every other mode's stay identical | lead + operator look |
| **M3** fades, HUD, widget suspension | M2 accepted | consumer counts equal before/after N cycles (Media, OSD, Gmail, Feeds, Steam leases); no QObject/subscription growth over 20 cycles; HUD visible only on events, fades within its bounded window | agent |
| **M3b** full-display overlays | M3 merged | §G spec incl. options and the Fullscreen Mode pill; event-only visibility, Always Show crossfade, every corner, media controls on the one Media controller; consumer counts unchanged | agent |
| **M3c** Fullscreen Edit | M3b merged | Edit entered while expanded stays expanded and edits only the overlays' geometry through the existing Edit session (draft, Save/Cancel); Edit/Arrange-style parity map for the overlays; ordinary layout untouched byte for byte | agent |
| **M4** wallpaper policy and GPU savings | E0 state diagram written and reviewed | batch traces: expected/published/covered identities, zero stalled batch, zero backlog on collapse; measured GPU and render-thread CPU delta on the covered display vs M0 (relative, load recorded) | lead |
| **M5** transactional lifecycle | M3, M4 green | deterministic event traces for capable->capable, capable->incapable, failed activation, transfer at mixed DPI, Settings open/close x10, Edit Save/Cancel, hotplug; resource counts flat | agent |
| **M6** performance, fidelity, admission | M5 green | §0.7 budgets met at 4K under game60 (or a trigger recorded); EB BTF/reattack/settle/stream/drift unchanged vs M0; docs updated for proven semantics only | operator physical acceptance |

### 0.3 SSOT owners (who owns what; nothing gets a second owner)

| Thing | Owner | Never |
| --- | --- | --- |
| mode capability `supports_expanded_display` | `core/settings/visualizer_mode_registry.py` descriptor (default False; every mode but Sphere and Extruded Spectrum declares True) | a Settings flag, a preset field |
| persisted intent `widgets.spotify_visualizer.expanded_display_requested` | canonical defaults + `SettingsManager` normaliser; excluded from mode/Custom payload | a sidecar file, a per-preset copy |
| effective state (DORMANT..RETIRING) | the takeover coordinator next to the Visualizer host binding (AC-02), one per process | QML state, `DisplayManager` ad hoc flags |
| expanded viewport geometry | `resolve_expanded_visualizer_presentation` (`widgets/spotify_visualizer/presentation_geometry.py`), a variant of the ordinary `ResolvedVisualizerPresentation`; its inset is `expanded_card_inset`: the card's own chrome (the AC-09 border width, the shadow's displaced body) plus `EXPANDED_CARD_EDGE_GAP` (amended 7 Nov) | a stretched texture, authored CUSTOM geometry, the overscanned window rect, the ordinary slot's edge margin |
| widget visibility while covered | one display-local transient visual policy on the retained host (§F) | `widgets.<id>.enabled`, family activation, layout slots |
| per-display wallpaper admission | one policy at the engine/manager batch seam (§E) | a second queue, dropped callbacks |
| HUD data | existing Media model / volume model (§G) | a second GSMTC query, decoder or art cache |
| the one Visualizer owner, controller, clock, DSP lane, renderer | unchanged (`Docs/Contracts.md` → Transition / visualizer) | anything new |

### 0.4 Dormancy: nothing costs anything while full display is off

Prove, not assert, each of these at M1 and again at M6:

- `tools/overhead_baseline.py` transition and Visualizer GL/Python call counts identical to the stored baseline
  with the capability present and the intent False (the glyph and HUD are `Loader`s that stay inactive unless the
  mode is capable and the pointer is over the card; the coordinator is a plain object with no timer).
- The AST import scan shows no new module reachable from the common Quick import or from an incapable mode.
- No new QObject, signal connection, timer or per-frame branch on the ordinary path: the reducer is called only on
  events (glyph, mode request, transfer, Settings, topology), never per frame.
- Zero new work while displays are off (`Spec.md` → Lifecycle → Displays off): an expanded display parks like an
  ordinary one; no fade animation runs while parked.

### 0.5 Lifecycle contracts the takeover must honour

- One display generation owns one effective state; every event carries runtime generation, visualizer activation
  and physical display identity; stale ones are rejected, never queued.
- Settings keeps today's teardown (`engine_handlers.py::on_settings_requested`): intent persists, state dies; the
  replacement generation re-evaluates once at the reveal coordinator's readiness edge, before any retained root is
  exposed (no ordinary-card flash, no double fade).
- Display power: an expanded display parks and resumes exactly as an ordinary one; the fresh-frame fence covers the
  first expanded frame after wake.
- Topology: loss of the owning display retires the generation under the existing barriers; the intent survives;
  a return re-evaluates. Transfer is one transaction on the existing `_transfer_quick_visualizer_unit` seam with
  rollback fences for both takeover scopes (§D4).
- Edit: entering Edit from the ordinary scene edits the ordinary layout as today. **Entering Edit while expanded
  (operator, 8 Nov; supersedes "entering Edit collapses") stays expanded and edits the full-display overlays' geometry**
  (M3c, built 8 Nov); an active draft is resolved by the session's own Save/Cancel path (§D5); the CUSTOM working
  override and the ordinary committed geometry are untouched by expansion. **Edit edits the display it was entered on
  (operator, 11 Nov; plan 1B.1):** entered on another display while expanded, it is an ordinary Edit of every display
  but the expanded one, which stays expanded and running outside the session (M3c "Edit beside the view").
- Terminal exit: HUD animations, leases and GL resources retire under the existing render-thread owner; no new
  release path.

### 0.6 2D/3D consistency at full display

Every registered mode must look and behave as the same mode at the card and at the display; expansion is a viewport,
not a different renderer.

- **Full display is not edge to edge (operator, 7 Nov):** "we have the overscan rule to stop opengl artifacting for a
  good reason. In my opinion a full screen visualizer would place the widget card of the visualizer near the display
  extents. You'd still see it's border colour and surface type if relevant." **Amended (operator, 7 Nov night, on
  Waveform Ribbon expanded at 2560 x 1440):** "for fullscreen visualizer we currently: 1. Don't reach nearly close
  enough to the screen borders." The expanded card is the display's logical rect (the monitor, never the R-63
  window) inset on every side by only what the card's own chrome needs, plus a 2 px gap (`expanded_card_inset`): its
  border width (the one AC-09 resolver) and, when it casts a shadow, the shadow's displaced body (base offset plus
  Extra Offset) on its furthest side; the blur falloff and the transient hover glow may meet the display edge
  (keeping them whole would put the card about 30 px in again). It keeps its chrome as the card draws it: border
  colour and width, corner radius, shadow (not magnified with the display-wide world) and surface material (the
  Visualizer card's material is its own open item in `Current_Plan.md`; the expanded card inherits whatever the card
  draws). Canonical chrome on 2560 x 1440 at 150 %: 4 + 8 + 2 = 14 logical px (21 device px), was 30 (45) with a
  shadow magnified about five times.
- **The world is contained, never cropped or stretched (M2):** the ordinary viewport extent grows on the inset card's
  long axis only (a wider card keeps the height and widens; a portrait one keeps the width and grows taller), and one
  uniform scale maps it onto the card. The logical runtime keeps the ordinary extent (the controller is never handed
  the display-wide record), so every mode's frames are those of its card.
- **Cycling while expanded (operator, 7 Nov):** a double-click to the next mode skips enabled modes that are not
  capable and goes to the next enabled capable mode, staying expanded; with no other enabled capable mode it stays
  on the current mode, still expanded. An explicit selection of an incapable mode (Settings, the context menu) still
  collapses and clears the intent (§D3).

- **Clip policy stays mode-owned.** `CARD_INTERIOR` modes (Bubble, Spectrum, Neon Lake, Extruded Bubble, Waveform)
  keep their card interior semantics scaled to the display rect; `VIEWPORT_RECT` modes (Sphere, Extruded Spectrum)
  keep theirs. The expanded variant is resolved per policy and proven per mode (§B2), never by flipping policies.
- **2D modes:** the line halo scales with the visible area's square root against 420x280 (`Docs/Contracts.md`), and
  Bubble sizes its radius unit from the canonical card times `world_scale` (R-170; a 4K card draws up to 72 live
  heroes / 110 with trails). Expansion must not add a second compressor (R-69). Measure Bubble's tick and GPU at
  4K before calling 2D "free".
- **3D modes:** the shared framed camera (`core/settings/framed_camera.py`) resolves its frustum from the expanded
  aspect; authored poses, preset starting views and saved camera values are unchanged; W/A/S/D, drag orbit, inertia
  and wrap behave exactly as at the card (AC-11 decides the contract for modes without a framed spec before they opt
  in). Control hints keep the upper-right corner; Reset Camera shares the bottom-right glyph row with the collapse
  glyph (§B1, "One bottom-right glyph row" under Milestone 2).
- **Input:** double-click cycles the mode, middle-click cycles the preset, the collapse glyph consumes its own presses
  (including the second press of a double-click, as the queued Reset Camera fix requires), for 2D and 3D alike.
- **Audio:** one engine, one tick, one cadence; expansion changes no DSP, floor, smoothing or ramp.

### 0.7 Performance budgets, including 4K, and the backend triggers

Budgets are the live-shape ones in `Docs/Guides/Visualizer_Change_Checklist.md` §1C, applied at the display size.
Measure with `tools/visualizer_live_check.py --mode <mode> --preset N --load game60` on the quiet machine, A/B
alternated against the card size, system conditions recorded (`Docs/Reference/Benchmarks.md`), median and p90.

| Budget | Card (today) | Full display, up to 3840x2160 | If exceeded |
| --- | --- | --- | --- |
| logical tick median | ≤ 2.5 ms | ≤ 2.5 ms (resolution-independent, except Bubble's density growth: measure) | optimise the tick first (Graphics decision step) |
| render-mode time (render thread, live) | ≤ 8 ms | ≤ 8 ms | mixed resolution for soft layers (mist, bloom, reflection blur) at their quality floor, lines/dots/particles native |
| GPU time per frame (`TIME_ELAPSED`, median / p90) | recorded per mode | ≤ 8 ms / ≤ 11 ms with soft layers at the quality floor | **Trigger 1** of the Graphics Backend Decision fires: record it in `Current_Plan.md`; the native Vulkan core precedes new 3D modes |
| publish -> swap median | ≤ 20 ms | ≤ 20 ms | frame age gone: find the owner (tick, GL call count, GIL share) before any knob |
| late frames under game60 | mode's accepted figure | not worse than at the card by more than the GPU delta explains | regression; not accepted |
| GPU memory | scene targets at card size | scene targets at display size: record bytes per target (an RGBA16F 4K target is ~66 MB; a 4x multisampled one ~265 MB plus depth); no permanent extra target | a quality floor that reduces MSAA at full display is an authored choice, recorded per mode |

- Record per-mode GPU time at 4K with and without the reduced-resolution soft layers; that table is the evidence the
  backend decision waits for (`Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md` → Meanwhile).
- **Trigger 2** (render-thread starvation) is judged only after the Waveform logical tick cut lands
  (`Current_Plan.md` §4); do not judge it on expanded Waveform before then.
- Port-readiness rules bind any new GPU code written here (there should be none: the variant is a viewport).

### 0.8 Full rearrangement

Expansion is not a layout. It writes no geometry, moves no widget, and collapses to the exact committed layout. The
Visualizer's resting place is decided by its placement policy (AC-02: `docked_to: media | none`), so a user who has
arranged the Visualizer away from Media gets it back there. Arrange never shows an expanded state. Edit entered from
the ordinary scene edits the ordinary layout; Edit entered on the expanded display edits only the full-display overlays
(M3c), whose geometry is its own, never the ordinary layout's; Edit entered on another display edits that display's
ordinary layout (with every other non-expanded display) while the view stays expanded (plan 1B.1).

### 0.9 Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| per-display wallpaper suppression wedges a global batch (§E) | medium | critical | pure state tests of the batch accounting first (E1.1); the fallback keeps the transaction contract and records one unresolved perf item |
| 4K GPU cost of EB/Waveform exceeds budget | medium | high (decides the backend) | mixed resolution for soft layers; otherwise trigger 1 recorded, not hidden by a knob |
| widget re-admission after fade creates duplicate owners or orphans shared backends | medium → closed at M3 | high | nothing is retired: the M3 cover is a visual policy only (no `admit_widget` built); the regression bar spies every lifecycle entry point over 20 cycles |
| expansion persisted on a now-incapable mode flashes or loops at startup | low | medium | one evaluation at the readiness edge; deterministic incapable rule (§D3) |
| HUD/OSD/control hit overlap | medium | low | one visibility lease with priority (§G); native QML hit tests |
| plan drift from the source by the time it starts | high | medium | M0 re-audits every seam in §A and records amendments |

---

## A. Source audit and interpretation

Repository `Basjohn/ShittyRandomPhotoScreenSaver`, default `main`, examined 2026-11-05. Revalidate sources before beginning; proposal input is `Docs/Future_Work/ShittyMusicPlayer/Proposal.md` in `SRPSS_ShittyMusicPlayer_Proposal_Expanded_2026-11-05(1).zip`. The audits cited below are **source inspection, not executed tests or physical validation**.

| Existing fact / seam | Actual source of authority | Consequence for implementation |
| --- | --- | --- |
| One accelerated retained `QQuickWindow` per participating display, Qt 6.11.2/OpenGL 4.6, `QSGRenderNode` | `Spec.md` Build/runtime presentation; `Docs/Contracts.md` Physical presentation; `rendering/quick/runtime.py`; `rendering/quick/qml/DisplayScene.qml` | Expansion enlarges the existing retained visualizer inside the **existing** display, not an extra window, `QQuickWidget` or second GL context. |
| One Visualizer owner/controller/logical clock/DSP lane and newest-state bridge | `Docs/Contracts.md` Transition / visualizer; `Docs/Reference/Visualizer_Reference.md`; `widgets/spotify_visualizer/quick_display_visualizer_owner.py`; `widgets/spotify_visualizer/quick_presentation_sync.py` | Expansion must not recreate simulation, analysis, mode, preset, camera or frame cadence. |
| `DisplayManager` admits exactly one visualizer to participating displays | `engine/display_manager.py::_admit_quick_visualizer`, `_construct_quick_visualizer_owner_on`; `rendering/quick/visualizer_admission.py` | Expansion attaches to that owner; `ALL` still selects first participating display; unavailable explicit monitor does **not** silently reroute. |
| Existing cross-display visualizer transfer is transactional | `engine/display_manager.py::_transfer_quick_visualizer_unit`; `rendering/quick/scene_controller.py::_release_visualizer_for_transfer/_adopt_visualizer_transfer` | Extend this seam for takeover handoff. Never use retire/recreate for a normal move. |
| Visualizer geometry is one `ResolvedVisualizerPresentation` | `rendering/quick/scene_controller.py::apply_visualizer_presentation`; `Docs/Guardrails/Visualizer_Presentation.md` | Resolve expanded viewport at a **presentation policy** layer. Do not overwrite saved CUSTOM bounds, preset geometry or authored camera pose. |
| Ordinary widgets have retained, display-local presentation and neutral services | `rendering/quick/widgets/host.py`; `rendering/quick/widgets/family_binder.py`; `rendering/widget_runtime_manager.py`; `rendering/quick/display_presenter.py` | Fade, display-local suspend and reactivation must be attached to existing owners. Binder has `retire_widget` today but no symmetric targeted re-admission contract; design and test one only if actual resource suspension is needed. |
| Media controller is shared per generation across display leases | `widgets/media_runtime.py::_SharedMediaRuntimeOwner` (generation key, active leases, media serial lane); `rendering/quick/widgets/media.py` | HUD must consume already-admitted playback metadata. **Hiding Media paint cannot discard the last required Media/Visualizer consumer.** |
| Visualizer playback truth already resolves a Media model from another display | `engine/display_manager.py::_resolve_quick_visualizer_media_model/_bind_quick_visualizer_media` | Preserve cross-display Media truth. A non-owning display's Media need not be duplicated on the expanded display. |
| OSD has a foreground scene lane and shared Core Audio endpoint | `rendering/quick/qml/DisplayScene.qml` OSD foreground (`z:30`); `Docs/Reference/System_Volume_OSD.md`; `Docs/Contracts.md` shared system audio dormancy | Preserve OSD independently, including with Media visually suppressed. Never add a second endpoint subscriber or volume poll. |
| Wallpaper image changes are whole, admitted batches; expected-screen accounting controls completion | `engine/screensaver_engine.py::_show_next_image/_try_begin_image_change_work`; `engine/display_manager.py::_begin_quick_transition_batch/_finish_quick_transition_batch_if_complete/_present_quick_captured_image` | There is **no currently proven display-local 'pause transitions' toggle**. Per-display suppression requires a new transaction with explicit completion/accounting semantics; simply hiding a background or ignoring a callback can deadlock a batch. |
| Current source→destination image contract rejects overwrite during active transition | `rendering/quick/runtime.py::set_presentation_image/start_transition`; `engine/display_manager.py::_present_quick_captured_image` | Do not cancel/snap a live run to enter expansion. Settle on a safe completion/admission edge. |
| QML scene order: wallpaper -> ordinary widgets -> visualizer -> OSD -> Edit -> context menu | `rendering/quick/qml/DisplayScene.qml` | HUD and expansion glyph must respect context menu, OSD, tooltip and Edit z/hit policy, not use an extra native overlay. |
| Settings fully stops and replaces SRPSS runtime | `engine/engine_handlers.py::on_settings_requested/_restart_after_settings_dialog_destroyed`; `engine/runtime_destruction.py` | Keep this exact lifecycle. Persist **intent**, never a retained Qt item, and reapply only after the replacement generation is ready. |
| Mode and preset changes have distinct semantic paths | `engine/display_manager.py::_request_quick_visualizer_mode/_request_quick_visualizer_preset_change`; `Docs/Reference/Visualizer_Reference.md` | Capability checks and expansion transfer must wrap canonical mode transitions, never replace them. |
| Universal glyph chrome and local visualizer glyphs already exist | `rendering/quick/qml/WidgetHoverEditGlyphs.qml`; `VisualizerPresentation.qml`; `OverlayWidget.qml` | Reuse the input admission/theme/hover/tooltip semantics and avoid overlapping reset/preset/transfer controls. The expand glyph is a distinct semantic action, **not** an Edit glyph. |
| Mode-owned preset change writes the whole normalized Visualizer child | `core/settings/settings_manager.py::replace_visualizer_runtime_preset_state` | New expanded intent MUST survive the normalization/atomic replacement; exclude it from mode/Custom payload and regression-test the exact transaction. |
| Profile settings are distinct but non-settings data root shared | `core/settings/json_store.py::determine_storage_path`; `core/settings/storage_paths.py`; `Docs/Contracts.md` | Standard and MC may have independent expansion preferences. No sidecar state file or new profile resolver. |

**Binding review first:** `Spec.md`, `Docs/Contracts.md`, `Docs/Guardrails/Performance_Optimization_Contract.md`, `Docs/Guardrails/Visualizer_Presentation.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md`, `Docs/Guides/Visualizer_Change_Checklist.md`, `Docs/Reference/Visualizer_Reference.md`, `Docs/Reference/Scene3D_Resources.md`, `Docs/Reference/Extruded_Bubble/*`, `Docs/TestSuite.md`, and exact historical bug lessons R-69 / R-71 / R-87 / native Qt retirement. Documentation is contract authority, but source may reveal an unimplemented contract; never silently weaken it to pass a test.

## B. Product behaviour / scoped definitions

1. **Expanded** means the *existing selected Quick display scene's logical display rectangle* inset by only what the card's own chrome needs (operator, 7 Nov: the card sits near the display's visible extents with its chrome, and much closer than the ordinary edge margin; §0.6), not exclusive OS fullscreen, a new window or altered screen/desktop shell. It covers all compositor space intended by the product, respecting actual selected display geometry and viewport/DPR, not an arbitrary 16:9 crop. Preserve current screen-window policy and monitor identity.
2. **Entering:** operator presses a contextual diagonal upper-right expansion glyph on a capable visualizer. Normal hover/interaction eligibility applies. User sees a short, gentle coordinated transition from ordinary visualizer rect to display-wide viewport; ordinary widgets on **that** display fade out. Other displays behave normally. OSD remains available. There is no extra mode activation.
3. **Exiting:** reverse glyph (diagonal lower-left), explicit collapse, Edit entry, loss of capability, or relocation. Return exact authored pre-expansion presentation rather than saving the temporary screen-sized rect. Collapse/restore is independent of preset and CUSTOM values.
4. **Mode selection:** ordinary double-click and context-menu mode switches retain current meaning, except that a double-click while expanded cycles only through capable modes (§0.6). Capable -> capable stays expanded through the canonical activation. Capable -> incapable collapses in a strictly ordered handoff, then changes mode. A rejected mode request leaves the current mode/expansion intact. Middle-click still cycles preset only.
5. **Other display:** no fades, audio change, transition suppression, image queue mutation or OSD change, except legitimate shared-source work already occurring. A shared provider survives while any real consumer still needs it.
6. **Overlays (operator, 8 Nov; supersedes the bottom-right HUD with a volume rail):** two gentle event-revealed overlays on the expanded display, nothing else. (a) **Preset name, top left**, in Title Case, fading in and out gently when the preset changes. (b) **Now playing, bottom left**: Artist, Song and Artwork fading in and out very gently when the track changes. The artwork carries the themed card border; the text has none. Text is white with a customizable font; long term, a cheap detection of bright areas under the text switches it to black where needed. No volume rail (the OSD owns volume), no pointer-hover reveal by default (Show On Hover, an option the operator asked for on 8 Nov, re-fades Now Playing where it sits; §G), no permanent timer/poller, no duplicate transport controller, and no overlap/hitbox conflict with OSD, camera, presets or the collapse glyph.
7. **Persistence:** expansion is a user intent, per existing settings profile. It is effective only if the currently resolved mode supports it, owner is live, monitor participates, and Edit/Settings/retirement aren't active. Losing eligibility must not rewrite user intent as a false 'off' unless the user explicitly toggles it off; a deliberately selected incapable mode can normalize effective state off without destroying the original authored layout. (Operator, 7 Nov: selecting an incapable mode also clears the intent, so a later capable mode starts ordinary; §D3.)
8. **Restore:** startup/Settings restart/topology replacement re-evaluates persisted intent **once at an already-defined readiness edge**; no unguarded early fade, first-wallpaper duplication or reentry loop. Missing explicit target remains unadmitted (no theft of another display), and later reconnection restores safely.
9. **DPR/size:** recompute physical frame/viewport from target display and its existing display identity, not from screen-1 cached values. Treat camera, frustum, stream volume, near field, lighting reach, translucency and particles as authored mode semantics, not as a stretched old texture.
10. **No accidental global style changes:** preserve selected themes, card chrome policy, opacity, OSD palette, default user content and existing settings. SMP later reuses the **semantic display takeover contract**, not this screensaver-only physical compositor.

### B1. Input and chrome priority

- [ ] Show an **expand ↗** control (vector drawn, not a platform-dependent font emoji) for eligible modes, initially EB only. On expanded view, replace with **collapse ↙**. Distinct from SMP's later square-with-diagonal-arrow **Pop Out**, which moves a window.
- [ ] Use the existing interaction/admission gate: no invisible clickable hits, no action under an active context menu, no conflicting visualizer double-click/preset middle-click, no edit pointer gesture leak.
- [ ] Reserve a safe zone for collapse glyph, camera-reset and preset-controls row; auto-relocate HUD within target display when OSD or controls are visible. Inspect the actual `VisualizerPresentation.qml` bottom-right controls (`cameraResetGlyph`, `presetControls`) before choosing anchors. Do not stack HUD on them.
- [ ] Context-menu and mouse actions are single semantic events. If a fullscreen glyph receives a click, consume it before image-next / visualizer-mode-cycle fallback; no duplicate action due to Qt TapHandler propagation.
- [ ] Keyboard path for collapse must be documented and not steal current exit/media/CUSTOM keys. Offer a visible control usable with mouse and keyboard focus; avoid an unadvertised global key override.

### B2. Mode policy vs authored state

**Recommended minimal source addition** (names illustrative; fit registry naming before implementation):

```text
VisualizerModeDescriptor / presentation capability:
  supports_expanded_display: bool = False

widgets.spotify_visualizer (product-level canonical persisted intent):
  expanded_display_requested: bool = False

Resolved display policy (runtime, never a preset):
  requested, effective, owning_display_identity, runtime_generation,
  visualizer_activation_id, expanded_viewport, exclusion_policy
```

- [ ] Define *registered*, *enabled*, *active*, *capable* and *expanded-effective* as five different predicates. A disabled/experimental/unavailable mode cannot be made active by expansion.
- [ ] Exactly one persisted intent; do not persist a second mirror of current mode/monitor/geometry. Existing mode/physical route keys are authoritative. If the Visualizer section normalization cannot retain the new non-preset key across `replace_visualizer_runtime_preset_state`, extend its canonical schema/normalizer and tests, or choose a deliberately documented sibling SSOT. **Never** solve by patching each preset or writing a separate JSON file.
- [ ] Keep `Custom` *preset* payload mode-owned. Keep global layout `CUSTOM` editor/slots separate. Expansion overwrites neither.
- [ ] Framed vs frameless renderer policy stays mode-owned. Capability alone does not change `CARD_INTERIOR` to `VIEWPORT_RECT` across unrelated modes; explicitly resolve an expanded presentation variant for eligible modes and prove its clip/shell behaviour.

## C. Hard invariants / fail-closed rules

- [ ] One existing Quick scene/window for each participating display, one visualizer controller, one logical clock, one audio worker lane, one renderer per current owning display; zero surprise second windows/context/visualizer sources.
- [ ] No per-frame GUI scans, Python timers, render-driven animation/physics clocks, `frameSwapped`-update feedback loops, synthetic source capture, additional BeatEngine or duplicated Media queries.
- [ ] No change to EB bubble counts, drift/stream speed, smoothing, sources, particle/microbubble inheritance, light/reflection material, collision physics, BTF/temporal fidelity, mode preset data or user-created Custom values in order to improve timing.
- [ ] No early resource retirement: existing visualizer logical runtime must satisfy stop/join barrier; Qt item release, queued callbacks, context-local GL resources and display transfers retain generation fences.
- [ ] Shared data/source/endpoint lifetime is consumer-based; per-display visibility does not infer global service dormancy. A widget still needed on another display remains fully functional there.
- [ ] OSD is an independently admitted foreground consumer (not implicitly disabled by suppressing other overlays). No attempt to use OSD Core Audio as a substitute for provider-specific app volume.
- [ ] Wallpaper images and transitions on **other** displays preserve source order, identity accounting, authored transition type/duration and stagger. No spurious Crossfade substitution.
- [ ] A pending or running display transition reaches its existing finalization contract before a policy change that would detach its resources. Never cancel/snap/destroy a transition solely to acquire expansion.
- [ ] No backlog of missed wallpaper transitions or deferred image tasks while expanded; exit must have a bounded, precisely defined rejoin rule, not 'replay every skipped slide'.
- [ ] Real user Settings still performs existing stop -> destruction barrier -> dialog -> replacement. A retained fullscreen viewport never leaks into the dialog.
- [ ] Native physical evidence is still required for final appearance and dual-display frame pacing; automated tests should cover virtually all correctness before operator review.

## D. State machine, authority and atomic transactions

**Proposed pure state vocabulary** (single display-manager-level semantic coordinator; do not create a global renderer):

```text
DORMANT            no visualizer owner or no current capability
ORDINARY           canonical visualizer rect, widgets and wallpaper normal
ENTER_PENDING      eligibility fenced; active wallpaper batch/EDIT resolving
ENTERING           precomputed scope + one-shot paint fade; old rect saved by owner
EXPANDED           full logical display viewport, HUD/OSD; scoped omissions active
EXITING            restore wallpaper/widget admission and ordinary geometry
TRANSFER_PENDING   source/target admission transaction, no duplicate owner
RETIRING           generation closing; never process late callbacks
```

The operator's intended *expanded* bool is separate from transient state. Only the current `DisplayManager`/canonical owner may commit a state transition; QML owns animation and hit-target visuals, **not** persisted state or Media/source work. Idempotent repeated clicks are coalesced by this owner. Cancellation/target loss rolls back to the last fully admitted coherent state, never a half-faded scene. Every event carries current runtime-generation, visualizer activation, and physical display identity where relevant.

### D1. Enter expanded (ordered)

1. Read current capability/enablement, display routing, scene readiness, `CUSTOM` status and existing accepted transition batch. Reject without writes if any is invalid.
2. Resolve active Edit transaction through its **existing** user-choice/Save/Cancel path. Preserve draft when the user cancels entry; do not silently Save or Cancel. This same requirement applies if the glyph is technically clicked while Edit chrome is present.
3. If a transition is active, wait for its accepted finalization edge or reject/defer **one latest intent** bounded by that existing edge. Do not steal its destination or start a timer to poll for completion.
4. Snapshot a small *transient* activation record (owning display identity, ordinary resolved rect, visible widget IDs/leases, visualizer activation/generation, current image/transition policy). Do **not** clone settings, scene objects or render payloads.
5. Resolve entire display logical viewport and mode camera/clip policy through the canonical presentation/config resolver; preflight render target size/DPR and resource budget before making overlay changes.
6. Fence/prepare per-display wallpaper policy (see E), then apply a display-local transient widget-visibility gate. Allow other displays and OSD to continue.
7. Apply one gently eased viewport transition and overlays through the retained Quick host. On completion, lazily retire **only those truly display-local service/presentation leases proven safe**; preserve a cheap re-admission snapshot for restoration.
8. Publish EXPANDED and persist requested intent with a narrow canonical Settings write *only after the action succeeds*. Failure restores ordinary layout and policy. Do not persist on each animation frame.

### D2. Exit expanded (ordered)

1. Fence current expanded generation/input and HUD animations; capture the latest intended restore target from canonical settings (not from a stale stored pixel rect).
2. Re-admit widgets and their required display leases **without starting a duplicate shared owner or blanking services still used elsewhere**. Honor original per-display routes and current Settings state.
3. Restore wallpaper eligibility with one coherent current source/image policy (E); if there is no ready wallpaper yet, preserve a non-black safe known frame and hand off at the existing readiness boundary. No replay backlog.
4. Apply short exit transition to ordinary visualizer geometry and restore its original clip/shell policy.
5. Commit ORDINARY; explicit user collapse persists `expanded_display_requested=False`. Automatic temporary collapse (e.g. Settings, edit start, monitor loss) does not necessarily erase intended future expansion.

### D3. Mode requests

- [ ] **Capable -> capable:** precompute new mode's expanded viewport and controller activation using existing request-completion edge; retain the takeover and wallpaper policy. Do not shrink to a card before a valid new frame. No controller duplication; failed activation keeps the previous mode and UI state.
- [ ] **Capable -> incapable:** hold mode activation until orderly collapse; use current `_request_quick_visualizer_mode` call and its existing `on_complete` after the collapse has committed. If target admission fails after that temporary collapse, **roll back by re-expanding the still-active capable source mode** (subject to its current eligibility), not by silently leaving the old mode miniaturized. Do not persist an inconsistent mode or lose user geometry.
- [x] **Incapable -> capable:** select mode normally; never re-enter expansion. **Decided by the operator (7 Nov):**
  "Fullscreen is a special explicitly asked for function for the visualizer so a preset should not have the power to
  decide it." A switch to an incapable mode clears the persisted intent once that mode is the Visualizer's and the
  collapse has committed (also when the intent was only held, e.g. under Edit, and when a generation becomes ready on
  an incapable mode chosen in Settings), so a later capable mode starts ordinary. A rejected incapable target leaves
  the capable mode and its intent, and re-expands it (above). Tested in `tests/test_visualizer_expansion_reducer.py`.
- [ ] Middle click/preset Previous/Next must not toggle expansion, destroy it, or reset playback; `replace_visualizer_runtime_preset_state` preserves the product-level intent and geometry.
- [ ] Request rejection vs preparation failure vs accepted completion has distinct outcomes; stale completion cannot resurrect an expanded state on another display.

### D4. Monitor transfer / loss

- [ ] Resolve true physical destination identity, participation, new DPR/size/refresh, display-local wallpaper status, OSD presence and whether the destination is already under any takeover.
- [ ] Perform a single **source collapse + target preparation + existing `transfer_visualizer_to`/manager transfer + target expand** transaction. No duplicate renderer or controller in the overlap. If target cannot be preflighted, preserve source intact rather than strand the visualizer.
- [ ] Existing `QuickDisplayUnit.attach_visualizer_owner/detach_visualizer_owner` and `DisplayManager._transfer_quick_visualizer_unit` retain exact retirement ownership; add rollback fences for *both* display takeover scopes.
- [ ] Source widgets/transition eligibility restore; target widgets/transition eligibility suppress. Other displays unaffected.
- [ ] New target viewport uses local real logical and physical geometry and camera reflow; no artificial scaling from the source display or writes to authored preset coordinates.
- [ ] Explicit route to an absent display stays absent until it returns. Topology loss retires the generation under existing barriers and re-evaluates intent after replacement; do not create invisible offscreen surfaces.

### D5. Startup / Settings / Edit / shutdown

- [ ] Initial scene admission resolves mode and monitor **first**, then expanded intent; reveal coordinator gates all new retained roots before exposure. A persisted expanded intent must never cause a cold ordinary-card flash.
- [ ] Settings opens using current `on_settings_requested`, complete teardown and destruction barrier. The *intent* persists in profile settings. On return, only the new generation may re-admit expanded state; no callbacks from prior QML objects.
- [ ] Edit entry from expanded stays expanded and opens Fullscreen Edit (M3c; operator 8 Nov, superseding the
  collapse-on-Edit rule M1 implemented) on the expanded display; Edit entered on another display edits that display
  while the view stays expanded (plan 1B.1, M3c "Edit beside the view"). **If Edit has an active unsaved draft when expansion is requested, prompt/resolve with the current session policy; no implicit discard.** Returning from Edit restores expanded intent only after editor exit and correct readiness, not during drag.
- [ ] Terminal exit releases HUD animations, every local lease, visualizer and GL resources with existing exact retirement; preserve settings but not runtime references.
- [ ] Restoration on startup/Settings and topology change is idempotent, bounded and has a documented safe state if eligible mode is no longer available.

## E. Per-display wallpaper/transition suppression: the critical architectural gate

**Problem proven by inspection:** `engine/screensaver_engine.py::_show_next_image` reserves the full image-change transaction before queue/history mutation; `DisplayManager` tracks an expected set of screens and completes only when every admitted destination is authoritative. `QuickDisplayRuntime.set_presentation_image` rejects replacing the image during an active transition. Therefore one display cannot simply ignore `start_transition`, drop completion, or unhook image events. Nor can a 'deferred' per-display FIFO grow behind a fullscreen view.

### E0. Required design proof **before** a suppression implementation

Written 8 Nov: [02_E0_Covered_Display_Admission.md](02_E0_Covered_Display_Admission.md) (decision: exclude a covered
display that already shows an image at batch admission; zero targets return before the queue moves; resume at the
next admitted edge). The checklist below stays as its review list.

- [ ] Trace `_show_next_image`, `_prepare_next_transition`, `_load_and_display_image_async`, `DisplayManager` expected/published screen sets, `_present_quick_captured_image`, `transition_batch_idle`, `current_images`, the image queue/peek/history, source-speculative workers, monitor wake/replay, startup reveal and image-cache ownership. Draw an explicit source/destination/accounting state diagram for (a) one covered screen of two, (b) ALL covered if possible, (c) last uncovered screen removed mid-batch.
- [ ] Define **one authoritative per-display presentation admission policy** at the existing engine/manager seam: `normal`, `covered_committed_without_effect`, `covered_excluded_from_processing` (labels illustrative). This is NOT a second transition engine or separate image queue.
- [ ] Choose the strongest state actually safe. Prefer suppressing GPU effect work and any unnecessary image preparation on the covered display. The *global* queue and other displays keep their canonical semantics, including same-image/independent-image configuration. Distinguish logical image progression from physical pixel upload.
- [ ] Decide and test whether a covered display must still **commit a cheap destination identity/accounting receipt** for a global batch, or can be removed from that batch's expected set at admission. If excluded, recompute expected membership **before** queue mutation, and the actual completion contract must remain satisfiable. Do not later add it to an already running batch.
- [ ] Never suspend a shared source/prefetch worker solely because a single display is covered; only suppress work provably exclusive to it. If both screens are covered or none selected, apply documented zero-target/no-consumer behavior rather than infinite defer.
- [ ] Define exactly what the uncovered display receives on resume: current authoritative wallpaper at the engine's next admitted edge vs a single explicit re-seed without transition. No replay of skipped frames, no old/stale destination, no black flash.
- [ ] Classify performance honestly: hiding a visualizer's background under opaque pixels may avoid visible work but **does not itself stop render/GPU work**; measuring that distinction is part of the gate.

### E1. Implementation order and fallbacks

1. Implement **batch/accounting-safe no-effect covered display** in pure state tests first. It must send a completed/omitted receipt at the right boundary; never replace a live source/destination image without the accepted transition completion.
2. Prove cross-display ongoing effects by real Quick smoke and synthetic two-display completion sequences with source/history assertions.
3. Only then remove covered display's decode/process/prefetch participation if evidence shows that its work is separately identifiable, and the source queue history remains correct. This deeper optimization is separately gated and optional.
4. Test exit rejoin at image-idle, mid-transition on the *other* display, and source refresh/invalidation. Ensure the visualizer never sees a stale wallpaper reflection when expanded; if a mode consumes wallpaper, document whether it retains the pre-cover snapshot or the current global source intentionally.
5. If true suppression cannot be proved without violating batch semantics, **do not weaken the image transaction contract**. Permit a narrowly documented per-display low-cost presentation fallback (including Crossfade only as last resort) and keep one explicitly unresolved performance item. Crossfade is not evidence of dormancy and must not change other displays' transitions.

**Release gate:** no screenshot-only proof. Require batch-state traces of expected/published/covered display identities, image queue/history before/after, active transition counts, foreground/background processing submissions, first-frame identity on resume and zero pending work after collapse. Tests must fail if an expected display has no terminal receipt.

## F. Widget fading and service dormancy: two different contracts

- [ ] Add a **temporary display-local visual policy** separate from family activation and `widgets.<id>.enabled`. Suppressing a widget must not persist `enabled=False`, remove a capability, or alter a global saved layout slot.
- [ ] Fade admitted ordinary widget roots through the existing retained host and family `fadeOpacity`/startup gate *without hijacking family-owned fades*. The startup reveal is independent; a new takeover scalar must compose cleanly with authored family fade rather than overwrite it. Avoid treating visual opacity `0` as a lifetime signal.
- [ ] Preserve Media **state** even when its card paint is suppressed. If no local Media presentation is needed for source truth but another display's already-admitted model supplies it, bind the HUD to that model. Otherwise establish a narrowly justified neutral consumer lease rather than leaving an invisible full Media card or creating a duplicate controller. Preserve exact `MediaRuntimeService` generation/lease accounting.
- [ ] For nonessential display-local widgets, after fade completion use `OrdinaryFamilyPresentationBinder`/`WidgetRuntimeManager` service ownership. Existing binder `retire_widget` has no matching mid-generation targeted `admit_widget`: implement a symmetric *single-family, idempotent, exact-generation re-admission* if demanded by this feature. This is a **justified** new contract, not a general rerender system. Rebuild the widget exactly once from current canonical config, not stale pre-hide QObjects, and activate only after construction as the existing two-phase binding rule requires.
- [ ] If a widget service owns a generation-shared backend (Gmail, Media, Feeds, Steam), retiring the *display lease* must not stop the backend while other displays use it. On re-entry the new lease gets the newest published snapshot and does not trigger a burst of missed polling/requests.
- [ ] Preserve OSD rendering and endpoint consumer count; when it overlaps HUD, the HUD moves/fades/limits its footprint, not the OSD. OSD is a named exception to widget hiding and must remain in its existing foreground host.
- [ ] Other display retains current widgets and geometry, hover, input, Media actions, default fades and update cadence.
- [ ] Prevent stale callbacks into retired QML controls on re-admission, including `shiboken6.isValid` and generation fences on queued/coalesced actions. Repeated expansion cycles must not grow QObject, subscription or worker counts.
- [ ] Decide once what happens to a widget that is enabled/disabled by Settings while covered. On collapse, reconcile current committed intent, not a frozen widget list. No forced resurrection of a user-disabled family.

## G. Now-playing HUD: single data source and deterministic event windows

**Operator spec, 8 Nov (binding; supersedes the bottom-right placement, the volume rail and pointer reveal below):**
- **Preset toast, top left:** the preset's name in Title Case (the preset owner's own display name, title-cased by the
  shared typography rule), fading in and out gently on a preset change (Settings, middle-click cycling, the preset
  slider, the Studio's preset switch); latest change wins.
- **Now playing, bottom left:** Artist, Song and Artwork, fading in and out very gently on a track change (the Media
  model's track identity, never a second GSMTC read). The artwork is drawn with the themed card border (the one card
  chrome owner: border colour, width, radius); the text has no card, border or plate.
- **Text:** white by default with a customizable font (a global Visualizer setting with a canonical default, offered
  in Settings; corrected 8 Nov at M3b: not a preset value, so it is not authored into presets and the Studio, which
  edits a mode's preset values, does not carry it). Readable on bright visualizer
  frames: a soft text shadow now; long term (separate item), a cheap luminance detection of the visualizer area under
  the text that switches the text to black where it is bright. Cheap means no per-frame CPU readback: e.g. a
  `ShaderEffect` on the text sampling the already-rendered visualizer texture, or a tiny downsampled luminance probe
  taken only while an overlay is visible.
- **Fades:** gentle, both ways (fade, never vanish); one-shot from the event, bounded visible window, latest event wins,
  no repeating timer or per-frame driver. Both overlays sit inside the expanded card's safe area, clear of the collapse
  glyph, camera/preset controls and the OSD (which keeps priority).
- **Options (operator, 8 Nov, later the same night; maximum customizability):**
  - **Corner:** each overlay picks any of the four corners. The defaults are the placements above: preset top left,
    now playing bottom left. Two overlays in one corner stack without overlapping, the newer one nearer the edge.
  - **Always Show:** an overlay can stay up permanently instead of fading out. A change still crossfades its content
    gently; it never pops. Off by default.
  - **Media Controls:** previous / play-pause / next shown with the now-playing overlay, off by default. They drive
    the existing Media controller (the Media card's own transport path); no second controller, no second GSMTC read.
    Their hit area joins the overlay's, outside the OSD, collapse glyph and camera/preset controls. They are the
    Media card's own control bar, small (operator, 8 Nov: "it should have the media control bar just a small
    version"), not separate buttons.
  - **Show On Hover (operator, 8 Nov, later: "the media section should optionally refade in if hovered over where it
    was positioned. Without timers or polling"):** Now Playing only, off by default (`now_playing.hover_reveal`).
    Built (M3c branch): the pointer arriving where Now Playing is placed fades it back in from where it is and holds
    it while the pointer rests; leaving runs the reveal's own hold and fade-out (the same window as after a track
    change). Driven by one `HoverHandler` (`blocking: false`) on an empty region item over the slot's rectangle
    (`ExpandedVisualizerOverlays.qml`, `nowPlayingHoverRegion`; its `hovered` edge drives `nowPlayingHoverActive` ->
    `ExpandedOverlaySlot.hoverEnter()` / `hoverExit()`). The fade machinery reused as is: the slot's one finite
    `SequentialAnimation` (fade in, `PauseAnimation` hold, fade out), never a Timer; `hoverHeld` joins Always Show and
    Edit as a reason to hold, and leaving restarts the same cycle (`_showAgain`, which `resume()` also uses). Nothing
    takes a press (clicks, wheel and gestures reach what lies under it; the Media Controls keep their own hover); the
    handler is disabled while the option is off and under Fullscreen Edit (Edit holds the overlays itself); without
    a track or under Always Show it does nothing; the preset toast is untouched. The region is exactly the shown
    block while faded out: the text layout no longer reads the controls' effective visibility (which fell with the
    slot's own fade and shrank the faded slot by the Media Controls row).
  - **Card:** an optional border and theme surface like the widget cards (the card chrome owner: border colour, width
    and radius, plus the active Widget Theme's surface material), wrapping the whole overlay; off by default, so the
    artwork alone keeps its themed border.
- **Settings home:** a new Visualizers pill, **Fullscreen Mode**, placed first after Setup (before the mode pills),
  holding every overlay option above plus the overlay font. Its values are one canonical Settings value with a
  canonical default (`widgets.spotify_visualizer.fullscreen_overlays`: one owner, persisted, reset to defaults), a
  global Visualizer setting like `expanded_display_requested`, never a preset value (corrected at M3b; see the Text
  bullet). Steam-style buckets, closed by default; one-sentence intros, the rest in tooltips; Title Case labels.
- Owner: its own slice (M3b) after M3's widget suspension merges, since both touch the expanded scene hierarchy.

- [ ] HUD is presentation-only. Authoritative fields derive from **existing Media model** (`MediaPresentationModel`/`MediaRuntimeSnapshot`) and the canonical volume/OSD model as applicable. Reuse semantic theme colours, font/stroke/shadow rules and artwork image provider; no second GSMTC query, network request, decoder or artwork cache.
- [ ] Construct HUD lazily only for an expanded owning display (not all scenes, not imported backends); use one small retained QML item in the scene's current visualizer/foreground presentation hierarchy. No extra top-level window, render node or QObject model with duplicate business data.
- [ ] Trigger events: track identity changed, playback state changed, optional volume changed, and pointer moved/hovered within the expanded visualizer. Pointer movement is *event*-driven with bounded coalescing; no permanent hover poll or frame-request loop.
- [ ] Apply one semantic priority/visibility lease: OSD (higher priority) > collapse/camera/preset controls > HUD > decorative content. HUD must shrink/move or defer when its safe rect is not available. Different DPRs, portrait displays and very small geometry are measured.
- [ ] Define one-shot fade lifecycle from event time (Qt finite animation or already-owned one-shot visibility deadline), with latest-event-wins and a hard maximum display interval. No repeating QTimer; do not introduce new per-frame update to drive opacity.
- [ ] Volume bar semantics must match the actual volume type (app-specific vs system); do not show a fabricated per-app level if `supports_app_volume=False`. Reading a system endpoint for OSD does not imply app-volume control.
- [ ] Track title/artist/cover changes are identity-fenced and published atomically; stale old album art must not flash under the next track. Missing cover falls back to theme geometry.
- [ ] HUD does not steal focus, suppress visualizer drag/camera wheel or intercept double/middle clicks beyond its explicitly visible supported controls.
- [ ] Honour user-selected settings to suppress HUD, reduce motion/animations and font readability where applicable; no duplicate theme colour hardcodes in the policy layer.

### Fullscreen presentation options

Now Playing's existing Media Controls switch enables one transport owner. Its persisted
`now_playing.media_controls_style` selects `bar` (the shared Media card bar) or `floating`
(the same glyphs and input owner with the bar's surface, border, separators and shadow withdrawn).
Fullscreen Mode edits this member in the existing `fullscreen_overlays` value; Edit preserves it.

Ordinary Media and fullscreen title, artist and album use `MediaMetadataText.qml`: horizontal fitting to the shared
minimum followed by elision, with wrapping inside an explicitly allotted multiline row. Fullscreen Edit's text height
allots additional lines to each metadata row; the album follows Media's Show Album option and has its own
ordinary child-edit role when visible. These are the latched track's
strings and retain the existing reveal/swap fence. Text layout adds no provider, timer or persistence owner.

## H. Milestones with live checklists and explicit completion gates

Entry and exit gates per milestone are bound in §0.2; the prerequisite phase P-A (AC-02) precedes M2.

**Milestone 0 | Pre-admission and baseline capture**

- [ ] Waveform Ribbon completed/accepted by operator; do not preempt current Waveform or other current work.
- [ ] Record active repository commit/heads and audit every source and guardrail above; note drift from this plan and deliberate contract amendments, not unreviewed legacy assumptions.
- [ ] Baseline EB idle/music dynamic traces and accepted presets on canonical, wide/tall, extreme screen-sized view, one/two monitors and representative GPU load. Capture CPU/GL/GUI, frame pacing p50/p95/p99, source age, visualizer audio-to-photo freshness, pool/lease counts, and startup/reflection behaviour.
- [ ] Identify all widget families on both real displays and their shared-owner leases; log baseline consumer counts without creating a polling diagnostic.
- [ ] **Gate 0:** written baseline receipts, unresolved risks labelled, no visualizer code changed yet.

**Milestone 1 | Capability + persistence + pure takeover state machine**

- [x] Add registry capability default false; EB true only. Disabled/unregistered mode cannot force expansion.
- [x] Add canonical default/model/normalization for persisted intent. Test preset and Custom replacement transaction preserving field/other widget subtree; reset/import/export/migration/MC profile isolation.
- [x] Implement pure event/action reducer for enter/exit/mode/monitor/Settings/Edit/topology with generation and idempotency rules; no GL or extra resource owners.
- [ ] **Gate 1:** all pure tests pass including stale/duplicate input and immediate accept/reject permutations; no modules eagerly imported from dormant modes.

**M1 amendments (7 Nov, implementing agent; the source is the authority where this plan was silent or stale):**

- *Entry order.* M1 was built ahead of the M0 receipts at the lead's direction; it changes no rendering or runtime
  behaviour, and its branch merges only after the lead has captured M0.
- *Reducer location.* The pure reducer is `core/expanded_visualizer_takeover.py`, not a file beside
  `widgets/spotify_visualizer/visualizer_host_binding.py`: that package's `__init__` eagerly imports the beat engine
  and audio worker, which a standard-library-only module must not pull in. The M2 coordinator (one per process, the
  §0.3 owner of effective state) sits beside the binding and imports the reducer. §D's "display-manager-level
  coordinator" means that coordinator, not `DisplayManager`.
- *Capability.* `VisualizerModeDescriptor.supports_expanded_display` (default False; Extruded Bubble True) is read
  only through `resolve_expanded_display_capable(mode_id, mode_activation)`: registered, active (not gated), enabled
  by `mode_activation` and opted in. The fifth §B2 predicate, expanded-effective, is the reducer's. Events carry the
  resolved `mode_capable` as a fact, so the reducer stays registry-free and tests can use a synthetic second capable
  mode (as M5 asks).
- *Intent.* `widgets.spotify_visualizer.expanded_display_requested`: canonical default (both profiles, no MC
  override), model field, and `normalize_expanded_display_requested` (bools, 0/1 and the usual spellings; anything
  else falls back to the canonical default, never `bool(value)`). It has no mode prefix, so preset payloads and the
  Custom snapshot exclude it by construction: no preset repair fill, and the completeness guard is unaffected. No
  visualizer schema bump: an older profile gains the key through the defaults merge. No UI at M1.
- *Write rules (§D1.8, §D2.5; amended by the operator 7 Nov).* True is written only by the user's glyph, once, when
  the user's enter commits on a capable mode. False is written when the user's collapse is accepted (collapse is
  always attainable, so a Settings visit during the exit cannot resurrect it), and when an incapable mode becomes the
  Visualizer's: at the activation if nothing is drawn expanded, otherwise at the edge where the collapse commits; and
  at a generation's readiness on an incapable mode. Edit, Settings, monitor loss and shutdown never write it, so the
  intent survives a Settings round trip and a restart while the capable mode stays selected. Presets and Custom
  never carry it.
- *Decision, §D3 incapable -> capable (operator, 7 Nov, superseding the agent's first choice that the intent
  re-applies):* a mode switch never re-expands; a capable mode reached from an incapable one starts ordinary.
  Capable -> incapable holds the request until the collapse commits, then forwards it; its rejection re-expands the
  still-active source mode (the mode never changed, so its intent stands). Capable -> capable keeps the takeover
  (or a held intent).
- *Decisions on busy phases:* a mode request or transfer arriving while an enter, exit or transfer is in flight is
  rejected (never queued); one latest opposite glyph press is held to the running transition's commit edge; a
  failed enter restores ordinary and does not retry until a new edge (Edit exit, mode activation, readiness, press).
- *Fences M2 must supply:* every event carries the engine generation; glyph presses and transfers carry the
  visualizer activation (`engine.get_activation_id()`, which the reducer requires to increase within a generation)
  and the physical display identity (the runtime's `display_identity`); completions carry the transaction id the
  reducer issued. Loss of the owning display retires the generation (§0.5); a lost transfer target rolls back.
- *Gate 1 evidence (7 Nov, agent; the lead signs at merge):* `tests/test_visualizer_expansion_reducer.py` (table
  traces, an invariant walk over every short event sequence from ten reachable states, accept/reject permutations
  through a scripted coordinator), `tests/test_visualizer_expansion_capability.py` (capability and the AST
  import-graph scan plus a fresh interpreter) and `tests/test_visualizer_expansion_persistence.py` all fail on main
  for their own reasons, and six reducer mutations (Settings writing the intent, an enter staying expanded under
  Edit, a repeated press id, no generation fence, a retried failure, persisting on press) each turn them red.
  `tools/overhead_baseline.py` call counts are identical to main's (all 38 transition, Visualizer, surface and
  node-path cases, GL and Python). The stored `2026-11-06_ed9cec6b` baseline is already behind main by +46 Python
  calls per Visualizer frame and +14 for Burn; M0 should re-record it on the quiet machine. The impacted-file gate
  (`tools/impacted_tests.py --base main`, 735 files, `tests/run_chunked.py --isolated` in four batches) passed
  734; `test_release_media.py::test_source_change_during_capture_discards_media` fails identically on a clean main
  worktree because the untracked operator originals `assets/usu/scenes/*.png` exist only in the main checkout.

**Milestone 2 | Full display viewport with intact 3D rendering**

- [x] Implement single resolved display-space presentation variant through scene controller/retained node. No new render path, no preset changes, no whole-widget final-pixel stretching.
- [x] Add contextually admitted vector ↗/↙ glyph with safe hitboxes and event-bound hover fade; preserve existing reset/preset and semantic double/middle clicks.
- [x] Prove viewport clips and camera on 16:9, 16:10, 21:9, portrait and mixed DPR, with screen/window-bound geometry and safe GL target resize/retirement.
- [ ] **Gate 2:** production-host geometry is the card near the display's visible extents (chrome inset, chrome kept), and reactivity/payload numerical identities remain untouched for every capable mode; ordinary view round-trips its geometry to the byte. Lead signs; operator looks.

**M2 as built (7 Nov, implementing agent; the source is the authority where this plan was silent):**

- *Geometry.* `resolve_expanded_visualizer_presentation(ordinary, display_size, dpr)`: outer rect = the display's
  logical rect inset on every side by `expanded_card_inset(ordinary)`, exactly (the inset rect is the stage
  authority, never re-derived from extent x scale), capped at a quarter of the shorter side; extent contained (§0.6);
  shell, clip, border, radius, colours, shadow and orientation from the ordinary record; DPR the target display's.
  **Amended 7 Nov (operator: "Don't reach nearly close enough to the screen borders"):** the inset was the card's
  ordinary edge margin (`resolve_overlay_geometry_policy("media")`, 30 px canonical) passed by the display manager;
  it is now derived inside the resolver from the card's own chrome (§0.6), so no caller passes a margin. The shadow
  is drawn as the card draws it (it had been magnified with the display-wide world: blur about 88 px on a 2560 x
  1440 display). The ordinary card is untouched.
- *Owner route.* `QuickDisplayVisualizerOwner.set_expanded_display(expanded, animate, on_complete)`
  swaps the publication sync's resolve/commit pair (`QuickVisualizerPresentationSync.set_presentation_route`) at the
  event edge, so the steady path carries no per-frame branch and a collapse restores the ordinary methods
  themselves. The display-wide commit hands the controller the ordinary record's metrics, never its own, so the
  logical world, CUSTOM, presets and Settings never see the display rect. `resolved_outer_size` (layout planning)
  stays ordinary. Animated changes fade the whole presentation out where it is, swap the viewport at the midpoint
  and fade in at the target (two smoothstep halves of the mode transition's 0.25 s), sampled on the existing
  publication edge on the owner's transition clock: one GL target reallocation at the swap, no geometry tween, no
  timer. The readiness restore and Edit's collapse are unanimated.
- *Coordinator.* `widgets/spotify_visualizer/expanded_display_coordinator.py`, a plain object the display manager
  creates lazily (only for a capable mode or a saved intent) beside the host binding; it feeds the reducer and
  performs its actions: the owner route, one narrow intent write (`settings.set` + `save`), the canonical mode path
  (held until a collapse commits for an incapable target), the glyph. Its takeover generation is its own admission
  serial: the engine's generation advances with every preset and mode activation, so it cannot fence a takeover.
  Glyph presses carry the activation the glyph was published for and the owning display's key.
- *Wiring.* Owner admission (`_construct_quick_visualizer_owner_on`, before reveal) -> readiness; the one place an
  admission ends (the binding's `record_admission(None, None)`) -> `OwnerRetired`; explicit mode requests ->
  `ModeRequested`; the double-click cycle -> `ModeCycleRequested`; mode and preset completions -> `ModeActivated`;
  Edit start -> `EditEntered` before capture (immediate collapse), Save/Cancel -> `EditExited`; an ordinary CUSTOM
  transfer -> one ordinary transfer transaction. While the view is (or is becoming) display-wide, direct Alt
  gestures, the Edit hover glyphs and display transfers are refused (expanded transfer is M5).
- *Glyph.* `VisualizerPresentation.qml` `visualizerExpandGlyph`: vector arrow (↗, turned to ↙ when expanded), at
  the far corner of the card's bottom-right glyph row (below), Reset Camera's admission and hover fade, a delayed
  "FULL DISPLAY" / "EXIT FULL DISPLAY" tip above the row, right-aligned on the glyph, consumes its own presses
  including a double-click's second; the Edit hover glyphs are withdrawn while expanded. The coordinator publishes it
  (`set_visualizer_expand_glyph`). (Until 8 Nov it sat in the upper-right corner with the control hint moved left of
  it; the hint now keeps that corner alone.)
- *One bottom-right glyph row (operator, 8 Nov: "The rotate glyph should be on the same line as the bottom right
  glyphs, heck let's put expansion there too to be neater and do the same thing for the normal visualizer";
  decided).* One `Row` (`glyphRow`, `visualizerGlyphRow`) anchored at the card's bottom-right inset
  (max(12, border + 6), the 3D hint's inset) places the corner's controls on the ordinary and the display-wide card
  alike. Order, left to right: the preset steps, Rotate Widget Content (Edit's, below), Reset Camera, expand /
  collapse at the far corner (the card's exit stays where the pointer finds it; rotate and Reset Camera, both
  camera/content turns, sit side by side; the steps stay leftmost as before). Each member sits in a layout slot
  that carries its availability (`volumeWheelEnabled` for the steps, `cameraResetAvailable`, `expandGlyphAvailable`);
  the glyph inside carries the shared admission (`widgetGlowAdmitted`, the card shown), so the row skips what is not
  offered (no gaps), admission never moves a member, and hover only fades (each glyph's fade, tip and press rules are
  unchanged). Admission is not on the row itself: a `Row` hears a member's visibility only through effective-
  visibility edges, which an invisible row never delivers, so its width went stale while not admitted. The card
  publishes the row's one geometry (`glyphSize`, `glyphSpacing`, `glyphRowInset`, `glyphRowScale`, `glyphRowRight`,
  `glyphRowBottom`, `glyphRowTop`, `glyphRowCardWidth`); a card too narrow or short for the widest row (five members)
  scales the whole row about its bottom-right corner instead of overflowing. In Edit, `CustomLayoutOverlay.qml`
  `editGlyphRow` (Edit's preset steps, then Rotate Widget Content) continues the row on a Visualizer frame (ordinary,
  and Fullscreen Edit's expanded card, whose frame is now the whole card): the card's inset, size, spacing and scale,
  ending one spacing left of the members the card offers (Reset Camera; the expand glyph is withdrawn under Edit);
  other frames keep their own lower-right slot. The rotate route, undo and Save/Cancel are Edit's, unchanged. Edit
  chrome (corner squares, side strips, close, display hops, the wedge, Restore Size, the child lock) stays clear of the
  row. Evidence: `tests/test_visualizer_glyph_row.py`; stills outside the repository
  (`D:\Temp\Scratch\SRPSS\evidence\visualizer\20261108_glyph_row\`: the ordinary card hovered, ordinary Edit
  with rotate, the expanded card hovered, Fullscreen Edit with rotate, a narrow card).
- *V key (operator, 8 Nov).* V while the saver runs is a press of this glyph: `RuntimeInputOwner` emits
  `visualizer_expand_toggle_requested` once per physical press (no repeat, nothing under the context menu, consumed
  and refused in Edit), and `DisplayManager._toggle_quick_visualizer_expansion_from_key` passes the generation gate,
  then calls `_route_quick_visualizer_expand_glyph` on the Visualizer's unit in the direction the glyph shows. Every
  glyph rule and the persisted intent therefore hold; where the glyph is not offered (an incapable mode, Edit, no
  coordinator) V does nothing, like the glyph.
- *Reducer additions.* `ModeCycleRequested` (the cycling rule, §0.6) and `OwnerRetired` (reload, Visualizer off,
  failed construction: the state dies, the intent persists).
- *Not M2:* fades of the other widgets (M3), wallpaper policy (M4), expanded transfer (M5), the Spectrum bar count
  (M2b). Until M2b Spectrum's bars widen with the card.
- *Gate 2 evidence:* `tools/expanded_visualizer_evidence.py` (digests through the production owner for every capable
  mode, a leak negative control, the ordinary round trip, hidden production-host renders); receipts in
  `.artifacts/evidence/visualizers/extruded_bubble/expanded_m2/20261107_gate2/`.

**Milestone 2b | Spectrum bar count at full display (operator, 7 Nov; after M2)**

> "Spectrum would need to add a percentage of bars though based on how much wider it is when it goes full screen."

Operator, 8 Nov: "20% more if fullscreen and horizontal." **Landed** as a presentation rule: the display-wide record
(`ResolvedVisualizerPresentation.expanded_display`) of a horizontal card draws round(1.2 x) the authored bars, capped
at 64 (`widgets/spotify_visualizer/spectrum_display_bar_count.py`, the one owner). The renderer resamples the same
logical bars and peaks, so logical frames and their digests stay identical ordinary and expanded, and the count
switches with the record at the fade-through's midpoint (card invisible). A quarter-turned card keeps the authored
count (`tests/test_spectrum_expanded_bar_count.py`). The DSP recompute below remains open.

- [ ] Expanded bar count = the card's bar count x (expanded content width / card content width), clamped to the
  DSP's maximum, so a bar keeps its authored width.
- [ ] The DSP band layout is recomputed at the expand and collapse edges behind a fade (never a jump), through the
  one controller-owned BeatEngine reconfiguration path (bar count, engine generation and the logical display-bar
  mirror stay coherent, `Docs/Guardrails/Visualizer_Presentation.md` §1).
- [ ] Spectrum's reactivity digests differ at full display by design (per-band history is re-mapped); every other
  mode's digests stay identical (the M2 harness keeps proving it).

**Milestone 3 | Display-local fading, HUD + safe widget suspension**

- [x] Add composed takeover opacity outside authored fade; no flashing at startup or immediate toggles.
- [x] Add exception/preservation for Media truth and OSD; implement consumer-accurate targeted retirement/re-admission (if safe), not global disable flags. (Retirement/re-admission decided against, below: the cover is visual only.)
- [ ] HUD: **not M3 any more.** The operator respecified it (7 Nov night); it is its own slice after M3 merges, per the amended §G (lead).
- [ ] **Gate 3:** no service/backend orphaning, no duplicate worker/endpoint source, UI equal on untouched display, no opacity/binding warnings. Widget part evidenced (below); lead signs; the operator's look on the real display is owed.

**M3 as built (7 Nov night, implementing agent; widget fade and suspension only):**

> Operator, on Waveform Ribbon expanded at 2560 x 1440: "Don't really hide/disable the widgets underneath as you can
> see a double border on the topleft from another widget."

- *Policy (§0.3, §F).* One display-local transient visual policy on the retained scene: `DisplayScene.qml`
  `ordinaryWidgetsCovered` drives `ordinaryWidgetsCoverOpacity`, applied as the opacity of the two ordinary lanes,
  the paint lane (`ordinaryWidgetHost`) and a new shadow lane (`ordinaryWidgetShadowLane`, inside the shadow host
  after the Visualizer card's shadow, so paint order is unchanged and every ordinary card shadow fades with its
  card). Fully covered, both lanes are invisible (no paint, hit or hover); input stops at the cover edge
  (`enabled`), not at the end of the fade. It composes as an ancestor's opacity with every family `fadeOpacity` and
  the startup gate and never writes them; a root created while covered joins covered. The Visualizer card, its
  shadow and the OSD foreground lane are outside it. `QuickSceneController.set_ordinary_widgets_covered(covered,
  fade_s)` is the one setter; QML owns only the fade (a `Behavior`, `Easing.InOutSine`, its `NumberAnimation`
  instantiated on first use; nothing runs at rest).
- *Driver.* The takeover coordinator, at its action edges only (no timer, no poll, no per-frame branch): `RunEnter`
  covers (D1.6, before the owner's route), `BeginExit` uncovers (D2.2), as do `CancelEnter` and `RetireTakeover`.
  The fade is the owner's own fade half (`expanded_display_fade_half_s`, 0.25 s): the widgets leave while the card
  fades out at its ordinary rect and return while the display-wide card fades out. The readiness restore and Edit's
  collapse snap (a restore happens before reveal, so nothing is ever seen fading; Edit edits the ordinary layout at
  once). Only the owning display is covered; covering another first uncovers the previous one. The display manager
  wires `_cover_ordinary_widgets` into the coordinator's services.
- *Suspension (decided).* Covered widgets are suspended as presentation: invisible items draw nothing and take no
  input. Family services are **not** retired and re-admitted: Media must keep feeding the Visualizer's playback
  truth and its volume wheel; Gmail, Feeds, Steam, System Stats and Friend Pulse backends are generation-shared and
  serve other displays; a per-collapse rebuild would re-run QML construction on the GUI thread and re-arm provider
  refreshes (the Reddit/Steam burst risk §F names), and could not return each widget "exactly as it was" (rotation,
  scroll and fade state). So the binder's targeted `admit_widget` is not built. Visibility-driven presentation work
  already pauses on its own (Friend Pulse reports an empty visible range, so avatar hydration for this display
  stops; Achievement Pulse's pulse stops). What still runs while covered: each family's provider cadence and model
  updates, exactly as before expansion. Reopen only on measured evidence that a covered display's exclusive provider
  work matters.
- *Suspension audit (8 Nov, operator: "widgets are still doing work when they are not visible").* Evidence: the
  last 05:06-05:45 session in `logs/` (the expanded intent stayed persisted the whole session, so every Settings
  generation started expanded; rotation edges logged the display covered at 05:08:43, 05:21:58, 05:29:39 and
  05:39:44). Generation 7, the newest, was covered from its 05:37:25 reveal to the end of the log at 05:45, the LG
  TV its only display, with Clock, three NEWS cards, Gmail, Media, Reddit and Weather on it. Every widget line
  logged while covered was provider work this section keeps: Media's event-driven GSMTC reads (about 16 a minute
  while Spotify sat paused, the coalesced
  timeline flush in `widgets/media_runtime.py`) and its 30 s reconcile watchdog (0.05 ms each, re-reading the 85 KB
  thumbnail, decoded once: the Visualizer's playback truth and the Now Playing overlay's art); the NEWS sources'
  startup refresh (12 fetches about 3 s apart, 05:37:37-05:38:12, each followed by an artwork warm on an io worker
  that only verified already-cached files with PIL: 0 downloads, 26-126 ms per source, nothing on the GUI thread,
  nothing more until the next due refresh); Gmail's 5 min poll (05:42:24, 10 ms dispatch, mail unchanged, no
  repaint). Exclusive to the covered display here (it was the only one) but not costly, so no open question. The
  source audit found two presentation-only cadences the cover did not stop, and they now pause at its edge:
  the Clock's 1 Hz publication (a covered Clock left subscribed, keeping the global ticker's timer alive when it is
  the only Clock; about 0.06 ms of GUI work a tick) and the display's refresh-edge clock (each Gmail/Reddit/Feeds
  BUSY edge ran a 240 ms `QVariantAnimation` with about 17 Python phase callbacks on glyphs nobody can see).
  `QuickSceneController.set_ordinary_widgets_covered` tells its `OrdinaryWidgetPresentationHost`, the one owner:
  it runs each ordinary widget's bound cover handler (`RetainedOverlayWidget.set_cover_handler`; a late root or a
  display move joins the host's state; the foreground OSD lane is outside) and stops refresh edges animating
  (`RefreshTransitionClock.set_covered`: an edge settles at once; one already running finishes inside the fade).
  The Clock binds `ClockPresentationModel.set_presentation_covered`: it leaves the ticker, and on uncover publishes
  the current time before the first fade-in frame, then rejoins the shared tick. Left as they are, by inspection:
  one-shot QML content fades (Feeds, artwork, Media metadata, System Stats bars), which run in C++ only when a
  provider update lands. Evidence: `tests/test_visualizer_expansion_covered_presentation.py`.
- *§F open points, decided.* A widget enabled or disabled by Settings while covered: Settings replaces the
  generation, and the readiness restore covers the new one before reveal. Edit collapses first (uncovered, snapped),
  so its live enable/disable commits happen on the ordinary layout. Nothing is frozen, so collapse reconciles
  nothing: the lanes reopen over whatever is live.
- *Gate 3 evidence (widget part).* `tests/test_visualizer_expansion_widget_cover.py` on the production
  `DisplayScene.qml` and `QuickSceneController` (hidden `QQuickRenderControl` scene, never shown): covered (snap and
  fade) the frame equals the same display with no ordinary widgets, the expanded Visualizer card with its shadow and
  a revealed OSD included; uncovering restores every pixel; mid-fade every card shadow fades with its card; family
  fades, startup gate and roots untouched; input stops at the edge; a late root joins covered. Twenty user
  expand/collapse cycles through the real coordinator and the display manager's cover service: 0 calls into any
  family, binder, runtime-manager, presenter or host lifecycle entry point (spied), so no Media, OSD, Gmail, Feeds or
  Steam consumer or lease can change; the same retained roots; QObject tree 206 before and after the 20 cycles (one
  warm-up cycle first adds the deferred `NumberAnimation` and two Canvas contexts painting late); no Qt warning.
  `tests/test_visualizer_expansion_coordinator.py` covers the edge order, snaps and retirements. Negative controls:
  no cover on the paint lane, the cover on the whole shadow host (fades the Visualizer's shadow), an unfaded shadow
  lane, ordinary shadows outside the lane, no uncover at `BeginExit`: each turns its bar red. No real Media / Gmail /
  Feeds / Steam lease was counted in a test (that needs a live generation); the bar instead proves the cover cannot
  reach their lifecycle. (§I proposed `test_visualizer_expansion_widget_leases.py` for a retire/re-admit design that
  was not built.)

**Milestone 3b | Full-display overlays (operator spec, §G, 8 Nov)**

- [x] Preset-name toast top left (Title Case), gentle fade in/out on preset change; latest wins.
- [x] Now-playing bottom left: Artist, Song, Artwork (themed border on the artwork only), very gentle fade in/out on
  track change; identity-fenced (no stale art flash), missing art falls back to theme geometry.
- [x] White text, customizable font (a global Visualizer setting with a canonical default, in Settings; corrected:
  not a preset value, so neither presets nor the Studio carry it), soft shadow for legibility; the bright-area
  black-text switch recorded as its own follow-up (`Current_Plan.md` §3).
- [x] Options: per-overlay corner (any of four; same-corner stacking), Always Show (crossfade on change), Media
  Controls with the now-playing overlay (default off; the existing Media transport path), optional card border +
  theme surface material (default off).
- [x] Settings: a **Fullscreen Mode** pill in Visualizers, first after Setup, holding the overlay options and font as
  one canonical value (defaults, persistence, reset).
- [x] Tests: event-only visibility, fade retirement, latest-wins, Always Show keeps the overlay up and crossfades,
  every corner placed inside the safe area with stacking, media controls reach the one Media controller, no hit/z
  conflict with OSD/glyph/controls, consumer counts unchanged (no second Media query), dormant when not expanded,
  the pill's position (structure only, never its wording).
- [ ] **Gate 3b:** the lead's audit; the operator's look at the overlays on the real display (fade feel, sizes,
  legibility over bright frames, the Card on Glass).

**M3b as built (8 Nov, implementing agent; the source is the authority where this plan was silent):**

- *Setting.* `widgets.spotify_visualizer.fullscreen_overlays` (owner `core/settings/fullscreen_overlays.py`): per
  overlay (`preset`, `now_playing`) `corner`, `always_show`, `card`, placement `offset_x`/`offset_y` (fractions of
  the expanded card's safe area, screen axes) and `scale`; `now_playing.media_controls`; one `font_family` and
  `font_size`. A global Visualizer setting with a canonical default, like `expanded_display_requested`: no mode
  prefix, so presets and the Custom snapshot never carry it (no repair fill; the completeness guard is unaffected).
  One normaliser (unknown members dropped, malformed members fall back to their default member by member, numbers
  clamped), a typed model field, defaults in both profiles. M3c edits the placement through Edit; the corner is the
  anchor the offset is relative to.
- *Where they live.* `ExpandedVisualizerOverlays.qml` (+ `ExpandedOverlaySlot.qml` per overlay), loaded by
  `VisualizerPresentation.qml` (z 6: above the content and frame, below every card control, the OSD lane and the
  menu) only while `expandedOverlaysDrawn`. The owner sets that at its route's edges only: a committed swap, the
  fade-through's midpoint (the card at zero opacity, so the overlays arrive and leave with it), display power (a
  parked display holds none; waking re-enters) and retirement. Inside the card they inherit its fade-through and
  the startup reveal; a restore before reveal waits for the gate to open.
- *Sources.* The preset's display name is the preset owner's (`get_preset_names`), title-cased by the one SRPSS rule
  (`utils.text_utils.title_case`, moved there Qt-free; Settings re-exports it), published by the display manager at
  the mode and preset completions (a mode change changes the active preset too) and without a reveal at admission.
  Now Playing reads the `MediaPresentationModel` the Visualizer's playback truth already binds
  (`_quick_visualizer_media_model`): its coherent snapshot (title, artist, artwork source, can-previous/next/play)
  and the one artwork image provider. Nothing else: no runtime call, lease or refresh.
- *Events and fades.* Entering (once the reveal is open), a preset announcement, a track identity change (artist +
  title). Each is one finite QML animation from the event (preset 0.7 s in, 2.6 s hold, 1.4 s out; Now Playing
  1.3 s, 5.2 s, 2.0 s); a newer event restarts it from where it is. A showing overlay swaps by fading only its
  content out, swapping while invisible and fading it in (the overlay, and its card, stay up); Always Show holds at
  full. A track change latches title, artist and the artwork source together at the swap, and the artwork shown is
  the model's only while the latched identity is the live one (never another track's art under the text). No track
  fades Now Playing out. When a fade ends nothing runs and the item is invisible.
- *Placement.* The safe area is the card inset by its border plus max(24, 2.5% of the shorter side). Right-hand
  corners also keep clear of the card's controls (top: the 3D hint; bottom: the glyph row (the preset steps, Rotate
  Widget Content, Reset Camera, the collapse glyph) and their tips; 8 Nov, the collapse glyph moved into the row).
  An overlay is at most 45% of the safe width (text elides), so a left one never reaches the right-hand controls. Two in one corner stack, the newer (by appearance, not by content swap)
  nearer the edge; an appearing overlay waits while a showing peer makes room, and the older glides back when the
  newer has gone. A showing OSD over an overlay keeps priority: the overlay fades aside (and takes no input) until
  the OSD hides.
- *Look.* Text white (on its own card: the theme's card text, so a light theme's card stays readable) with a soft
  shadow (`ShadowedText`'s soft profile). Artwork square (as tall as the text beside it), framed with the card's own
  chrome (border colour, the AC-09 width, the card radius) on a concentric mask; missing art shows the card surface
  with a quiet note glyph. Card wraps an overlay in `OverlayCard` (the widget cards' own card: theme border, surface,
  material via the shared backdrop, card shadow). Media Controls are the one Media transport bar,
  `MediaTransportBar.qml`, which the Media card (`MediaPresentation.qml`, at the card's size, its mute button a child)
  also draws: the rounded bar with its outline and shadow, previous | play-pause | next in three segments split by
  thin separators, `MediaTransportGlyph` (pause while playing), the card's dim, hover and press. Its look is the
  Media model's (`MediaPresentationModel.transportBarLook`: one JSON string of plain values, because a QColor or a
  map read through QML `var` stays a reference connected to the model until JS garbage collection, which an
  unloaded overlay must never leave behind); the overlay's own bar takes no card material (it sits over the
  Visualizer, not the wallpaper). Size, from the card's own bar-to-text ratio: the card's bar is 2.15 x its font
  size tall under a title of 1.12 x that size in points, so bar / title = 2.15 / 1.4933 = 1.44; Now Playing's bar
  keeps that ratio to its artist line (0.74 x the title), the line it sits under: height = 1.07 x the overlay's
  scaled font size (32 px at the 30 px default), width = six heights (segments twice as wide as tall, which keeps
  the card's glyph box of half the bar's height), outline 1.5 px, radius 12 and shadow scaled by the bar's height
  against the card's. It sits under the text on the anchor side, scales with the overlay's scale and fades with Now
  Playing. Each segment holds its own presses (double-click included, `consumesDoubleClick`) and emits
  `transportRequested` with the same keys; nothing else in the overlays takes input, so double-click, middle-click,
  wheel and orbit reach the card as before.
- *Media Controls route.* QML → `QuickSceneController.visualizer_overlay_transport_requested` → the display manager's
  `_route_expanded_overlay_transport` (owning unit, admission open, no context menu) → `_route_quick_media_transport`,
  the route the keyboard transport shortcuts take: the Media card's own transport owner, never fanned out.
  Interaction Mode (or Ctrl) admits them, as every widget control.
- *Settings.* `ui/tabs/visualizers_fullscreen_page.py`: buckets Preset Name, Now Playing and Text (`fullscreen:*` in
  `ui.visualizer_bucket_states`), one level (each overlay has three or four options; nothing needs a second level),
  closed by default, one open at a time, remembered as the page's editing path (`_visualizers_pill` returns
  `fullscreen`). The page writes the one value through the tab's save and keeps the placement it does not show.
- *Evidence.* `tests/test_visualizer_expansion_overlays.py` (hidden production scene and the production owner),
  `tests/test_visualizer_expansion_overlay_settings.py`, `tests/test_visualizers_fullscreen_mode_pill.py` (real
  Settings dialog); each bar was turned red by reintroducing its defect. Stills (Extruded Bubble and Spectrum on
  PERSONALSET 859804, 1600 x 900): preset + Now Playing, Card, Media Controls, two stacked in one corner with Card,
  missing art in the right-hand corners, Card on Glass, long names.

**Milestone 3c | Fullscreen Edit (operator, 8 Nov)**

Operator: "when we choose edit mode during a fullscreen visualizer we should be able to adjust the size/position/
placement of the toast and preset text elements and artwork instead of it going back to the full quick scene. Like we
can most geometry normally."

- [x] Entering Edit while expanded keeps the expanded view (no collapse) and makes the overlays the editable items:
  the preset toast, the now-playing text block, the artwork and (when shown) the media controls. The Visualizer itself
  stays full-display; ordinary widgets stay suspended.
- [x] Same gestures, chrome and snapping as ordinary widget geometry (the existing Edit owner, glyphs and guides); no
  second editor, no second commit path. Drag moves, handles resize (text scales its font, artwork its size), snapping
  to the display's safe area, corners and the other overlays.
- [x] Geometry is the overlays' own canonical setting (spec system, defaults, reset), stored relative to the expanded
  display's safe area so it reflows across displays of different size/DPR. The Fullscreen Mode corner choice is the
  anchor the Edit position is relative to; changing the corner in Settings keeps the offset sensible (or resets it,
  decided in the slice and documented).
- [x] Draft semantics: Edit edits a draft; Save commits, Cancel restores the pre-Edit overlay geometry exactly; an
  unsaved draft is never silently saved or discarded (the session's existing prompt).
- [x] While Fullscreen Edit is open the overlays are shown (as if Always Show) so they can be grabbed; on exit they
  return to their authored visibility with a fade.
- [x] Tests: a parity map in the spirit of the Edit/Arrange parity harness (the same gesture through the Edit owner
  on a copy, then cancel, compared with the committed result); the ordinary layout and CUSTOM slots byte-identical
  after a Fullscreen Edit Save and Cancel; entering Edit while expanded does not emit the collapse transaction; no
  hit/z conflict with the collapse glyph, OSD and camera/preset controls.
- [ ] **Gate 3c:** the lead's audit; the operator's look at Fullscreen Edit on the real display (the frames, the feel
  of a drag and a corner drag, Settings held by an unsaved draft).

**M3c as built (8 Nov, implementing agent; the source is the authority where this plan was silent):**

- *Reducer.* `EditEntered` on a resting EXPANDED view keeps it EXPANDED with `edit_fullscreen` (no `BeginExit`; the
  intent is untouched); `eligible` holds under it. Under Fullscreen Edit nothing ends Edit implicitly: a collapse
  press is held for the Edit session's resolution (`RequestEditResolution`; the coordinator declines it, so the draft
  and Edit stay, as an expand press under an ordinary Edit always did; a press still held when the user's own
  Save/Cancel ends Edit is the user's collapse then), an incapable mode request and a transfer are refused (a
  capable mode and the double-click cycle stay expanded), and the one forced end, an incapable activation (no user
  path reaches it), ends the session first (`EndFullscreenEdit`: Cancel, nothing saved) and collapses. Edit begun
  while an enter, exit or transfer runs is an ordinary Edit that collapses at its commit edge, as before. Stale
  generation, duplicate glyph, Edit Cancel and topology loss keep their scenarios
  (`tests/test_visualizer_expansion_reducer.py`; only the superseded collapse-on-Edit traces were replaced).
- *One session, one Save.* The display manager's Edit entry asks the coordinator first; Fullscreen Edit opens the
  `QuickCustomLayoutOwner`'s one session (`start_fullscreen`) on the expanded display's overlays only:
  `fullscreen_overlay.preset`, `.now_playing` (the text block, with its Media Controls when shown) and `.artwork` (since 8 Nov: `.now_playing` is the whole block and its parts are its children; see "Now Playing's parts" below). The
  same retained Edit layer, frames, corner handles, wheel, Restore Size, guides, Ctrl+Z, Enter/Esc, background
  double-click and context menu; the frames offer no close (the overlays have no enabled state). Save writes exactly
  the placement members into `widgets.spotify_visualizer.fullscreen_overlays`; no ordinary widget, Visualizer item or
  other display is in the session, so CUSTOM, the ordinary layout and the layout slots stay byte-identical. The
  context menu's Save now takes the one Save route (Enter's): it had bypassed the takeover's Edit exit.
- *Geometry* (`rendering/quick/fullscreen_overlay_edit.py`). Each item's payload is its draft placement; its frame is
  read back from the live QML after every projection (the scene controller's `expanded_overlay_edit_geometry`) and
  whenever the overlays report a geometry change while editing (a track, the stacking), so a frame is always what is
  drawn. Moves snap with the ordinary rule (`resolve_snap_local_rect_for_edit`) inside the safe area (its edges, so
  its corners, and its centre) and to the other overlay (edges, centre, the 30 px gutter); every guide is drawn on
  the Edit layer (the guide underlay lies under the expanded card). Stored offsets are the ones the overlay really
  took (clamps included). Corner drags scale by the dragged corner's distance from the opposite one and keep that
  corner; the wheel (5 % per notch) and Restore Size (the canonical scale) keep the frame's top centre.
- *Artwork (decided; superseded 8 Nov by "Now Playing's parts" below: the artwork is the block's child and has no
  Edit item of its own; `artwork_scale` / `artwork_width` / `artwork_height` still draw as stored and Restore Size
  returns them to canonical).* Now Playing's artwork has its own size factor, `now_playing.artwork_scale` (canonical default,
  clamped like `scale`), on top of the text-derived size; it stays beside its text, so dragging the artwork or the
  text moves Now Playing as one (its undo step is Now Playing's), and the artwork grows away from the overlay's anchor
  corner. Media Controls belong to the text block (they scale with the text).
- *Single-axis sizing (operator, 8 Nov: "Does the edit allow x only and y only changes like our proper edits do? It
  should."; decided).* Every part declares both content axes (`content_extent_axes`), so the one Edit layer draws
  ordinary Edit's side strips and, on the selected part, its two-axis diagonals; the owner routes them to
  `FullscreenOverlayEdit` like the corners. A side drag uses ordinary Edit's edge rule (`edge_resize_rect`, bounded
  by the safe area) and resize-edge snap (`resolve_resize_edge_snap`: the safe area's centre, the other overlay's
  edges and centre), changes one member and keeps the other exactly (ordinary `content_extent_resize_payload`):
  `text_width` / `text_height` for the toast and the Now Playing text block, `artwork_width` / `artwork_height` for
  the artwork, all new members of the one value (canonical default = today's look: text `0` = natural, artwork `1`
  = square; a value stored before them reads them so, no bridge). Mirrored semantics: the text box is ordinary
  Edit's content box (Media's card elides in a set width and reflows into a set height): a set width elides, a set
  height adds lines (the toast's name and Now Playing's title wrap, then elide; the toast's name is centred in its
  box; Now Playing's rows fill it, see the artist-line fix below), floored at one line (the toast) or the natural
  block (Now Playing), at least the Media Controls bar's width; extents
  are in ems of the overlay's font, so a uniform scale (corner, wheel) and the font size keep the box's shape, as
  ordinary Edit's uniform scale keeps `content_extent`; a set box may use the whole safe area (the 45 % cap is only
  the natural growth). The artwork mirrors ordinary Edit's freeform artwork frame
  (`freeform_artwork_child_role`: free X/Y, image `PreserveAspectCrop`), so it may go non-square; its size still
  follows the natural (one-line) text block, never a set text height. The text parts keep the opposite edge (and
  the untouched axis's position); the artwork grows from its place beside the text, as its corner drag does, which
  keeps each change one undo step of one item. The stored extent is the one drawn (floors and the safe area
  applied), as offsets are. Restore Size returns scale and extents to canonical (ordinary Restore Size drops
  `content_extent`). Shared chrome change: a side strip on a frame shorter than 56 px keeps a 16 px grabbable length
  clear of the corner squares (it had none on a one-line toast; ordinary frames of 56 px and more are unchanged).
  Evidence: `tests/test_visualizer_expansion_fullscreen_edit.py` (side strips, one axis per handle, reflow and crop,
  undo, Restore Size, uniform scale, the parity map with side drags) and `..._overlay_settings.py`; stills outside the
  repository (`D:\Temp\Scratch\SRPSS\evidence\expanded_visualizer\20261108_m3c_axes\`).
- *Live defects (operator, 8 Nov, live; fixed the same day).* (1) **The artist line follows the box.** A set Now
  Playing box height gives the title the lines that fit and spreads what is left between the rows (title to artist,
  artist to the Media Controls): the title sits at the box's top and the last row at its bottom, so the artist moves
  with the side handles as the title does (formerly the rows stayed bunched in the middle with a stale gap above and
  below); Media's own content extent likewise widens its metadata spacing with its height. Natural boxes are
  unchanged. (2) **Dragging the text.** Now Playing's text block dragged with real pointer events through the window
  is taken by its Edit frame and moves Now Playing as one (guides, one undo step, Save); this did not reproduce on
  the hidden production scene (DPR 1 and 1.5, with and without Media Controls, stacked corners, after side handles,
  with the expanded card's item) and is now a permanent bar; the operator's live recheck is owed. (3) **The Volume
  OSD is a Fullscreen Edit part (decided: it mirrors the overlays' model).** Its placement over the expanded card is
  `fullscreen_overlays.volume_osd` = `offset_x` / `offset_y` (fractions of the safe area) and `scale`, relative to
  where its ordinary layout puts it (canonical zero / one = exactly there; a value stored before it reads it so, no
  bridge). The scene controller maps the OSD's layout rectangle through it (`RetainedOverlayWidget.
  set_display_placement`, `core.settings.fullscreen_overlays.volume_osd_rect`: scaled about its centre, offset, kept
  inside the safe area) only while the display-wide card is drawn, at event edges (the config, the overlays' stage
  appearing or going, the stage's `volumeOsdPlacementChanged`: safe area or OSD lane). Its ordinary placement
  (ordinary Edit, CUSTOM) is never changed: the layout keeps assigning the ordinary rectangle (the authored one) and
  collapsing returns it exactly; writing the ordinary placement instead would have moved the collapsed OSD too and
  broken Fullscreen Edit's rule that its Save never reaches the ordinary layout. In the session it moves with the
  same snapping (the safe area, the overlays), one undo step, corner / wheel scale and Restore Size; it has no
  single-axis extents (no side strips; its ordinary content extent stays ordinary Edit's). No Settings options.
  Evidence: `tests/test_visualizer_expansion_fullscreen_edit.py` (artist rows with and without Media Controls, draft
  and after Save, red on the former centred column; the real-pointer text drag; the OSD part, Save, the ordinary
  rect kept and collapse, red without the part), `..._overlay_settings.py`; stills outside the repository
  (`D:\Temp\Scratch\SRPSS\evidence\expanded_visualizer\20261108_m3c_defects\`).
- *Rotate Widget Content on the expanded card (operator, 8 Nov: the fullscreen Visualizer is missing "THE ROTATE
  GLYPH"; decided).* Ordinary Edit's Visualizer frame offers Rotate Widget Content (`rotateContentControl`, a
  quarter-turn of the content, CUSTOM layout state per mode) for a mode that can turn its content (Spectrum,
  Oscilloscope, Bubble, Spline Curve; never a framed 3D mode). Fullscreen Edit now admits the expanded card as one
  more session item, `fullscreen_overlay.visualizer`, when the live mode can turn (first in the session, so its frame
  lies under the overlays'): the same frame glyph (revealed on hover in the card's bottom-right glyph row, the
  card's frame being the whole card; until 8 Nov it stopped above the card's controls), the same `rotateContent`
  route and owner method (`rotate_visualizer_content`, one undo step per turn). The card is never moved or sized (a viewport, not a layout):
  not resizable, no Restore Size, no content axes, and its QML frame draws no outline and takes no press, so the
  background stays Edit's (its double-click Saves). Preview: a turned card publishes the committed world with the
  draft map through the scene's one viewport/orientation seam (the controller's `set_custom_viewport_override`, as
  ordinary Edit's Visualizer item does); an unturned card publishes nothing, so Fullscreen Edit without a turn
  leaves the Visualizer untouched. The production owner resolves the ordinary record with it and derives the
  display-wide card (`resolve_expanded_visualizer_presentation` already carried the orientation), so the expanded
  card turns exactly as the ordinary one; the working-stage reuse never takes the display-wide record for the
  ordinary one. Save: orientation is CUSTOM layout state, so a turn is written where every Edit writes it, the
  Visualizer's CUSTOM entry (`_admit_visualizer_item` from the ordinary card's record, `ordinary_presentation`, then
  `commit_custom_session`, as the direct Visualizer gesture's Save; its rect is the ordinary card's, unchanged), and
  promoted live by `commit_live_custom_layout`, which validates against the ordinary record while the scene draws the
  display-wide one. This narrows the M3c byte-identity: without a turn a Fullscreen Save still writes only the
  overlays' value; with one, exactly the Visualizer's CUSTOM entry also changes (on an authored layout it becomes
  CUSTOM at its current rect, as an ordinary Edit or direct gesture Save makes it). Cancel and undo restore exactly.
  Hover lane (checked, unchanged): the ordinary Visualizer's hover glyphs outside Edit offer no rotate
  (`canRotate: false`; Restore Widget Size and the transfer arrows only), and the expanded card withdraws that lane
  (M2), so outside Edit both stay without a rotate glyph, mirroring ordinary. The card item's capability is the
  mode's at Edit entry and the owner re-checks the live mode at each turn (as ordinary Edit's admission snapshot);
  a mode change during Fullscreen Edit to a mode that cannot turn leaves the glyph inert until Edit ends.
  Evidence: `tests/test_visualizer_expansion_fullscreen_edit.py` (the Edit path on the hidden scene: glyph, preview,
  undo, Cancel, a turn-free Save byte-identical, Save's CUSTOM entry and promotion; a 3D mode has no glyph; the
  production owner end to end on an unshown runtime: preview draws the display-wide card turned in place without
  committing, Cancel exactly back, Save commits and the collapsed card shows it at its own rect); stills 07-09 in the
  same evidence folder.
- *Corner change in Settings (decided).* `rebase_offset_for_corner` (the one owner): per axis, the offset is kept when
  it still points into the display from the new corner (right of a left corner, left of a right one, below a top
  corner, above a bottom one), so the overlay stays in bounds the same distance in from the new anchor's edge; an axis
  that would push the overlay out past the new anchor's edge resets to zero. The Fullscreen Mode page uses it.
- *Other displays (decided).* They keep running as they are, without Edit chrome: Fullscreen Edit edits only the
  overlays (§0.8). One Save/Cancel therefore never touches them, which makes the byte-identity structural rather
  than a check. ~~Their ordinary layout is edited from an ordinary Edit after collapsing.~~ Superseded 11 Nov
  (operator, plan 1B.1, "D0 becomes impossible to edit"): Edit entered on another display edits it while the view
  stays expanded (next item).
- *Edit beside the view (operator, 11 Nov; plan 1B.1, decided).* **Edit edits the display it was entered on.** The
  operator's report: with two displays and the Visualizer expanded on D1, Edit entered on D0 or D1 opened only D1's
  Fullscreen Edit, so D0 could not be edited. Cause: the display manager's one Edit entry
  (`_start_quick_custom_layout_session`) took no entry display and asked the coordinator only whether a takeover was
  resting expanded (`EditEntered` on EXPANDED always set `edit_fullscreen`), so every entry (menu, double-right, hover
  glyph) went to the expanded display. Ordinary Edit (no expansion) is one global session: entered from any display
  it binds every display, and a second entry from another display is the same session. Semantics settled to match it:
  - Every entry names its display (the context menu's and the double-right shortcut's unit, the hover glyph's
    source; none named means the view's display). On the expanded display: Fullscreen Edit, unchanged. On any other
    display: an ordinary Edit of **every display but the expanded one** (the global Edit minus the display it cannot
    edit), through the same owner and session: `QuickCustomLayoutOwner.start(excluded_units=...)` binds no scene there
    (no Edit chrome, no item captured, no Visualizer item; transfers only between bound displays). The view stays
    expanded and running (no collapse transaction, the intent untouched); the reducer marks it `edit_elsewhere`
    (`EditEntered.on_view_display` False) with Fullscreen Edit's holds, because collapsing would put the view's
    display back into a layout the session does not hold: the glyph is withdrawn as under every Edit and a stale
    collapse press waits for the session's own Save/Cancel (declined), an incapable mode request and a transfer are
    refused, a capable mode switch stays expanded (the Edit has no Visualizer profile to stage). An incapable
    activation (no user path) collapses the view and the Edit goes on as an ordinary one (it never held the view).
    Edit begun while an enter, exit or transfer runs is still an ordinary global Edit that collapses at its commit
    edge. Save/Cancel/Undo/Enter/Esc and the authored-layout quiesce are the ordinary Edit's own (CUSTOM is global).
  - Shared widgets: the expanded display's copies of a widget on every display (`ALL`) are outside the session but
    counted (`CustomLayoutSession.hold_copies`, `commit_custom_session(..., held=...)`), so the X on the session copy
    removes only that copy and Save narrows the route to the held copy's display, exactly as the same edit in a
    global Edit; the held display's saved geometry is never written.
  - Menus are per display: Save/Cancel only where the open session edits; a display it does not edit offers Edit
    Layout. A request from a display the open session does not edit (Fullscreen Edit open and Edit asked on another
    display, or the reverse) moves Edit there through the session's own Cancel when it holds nothing to lose
    (`QuickCustomLayoutOwner.unsaved_changes`: Fullscreen Edit's draft, or any item changed since it started);
    otherwise it waits for that session's Save or Cancel (never discarded or saved implicitly). Settings keeps its
    rules: held by an unsaved Fullscreen draft from either display; an ordinary Edit is cancelled by it as always.
  - Reset To Saved Layout in an Edit beside the view resets the families in its session (not the Visualizer's) and
    rebuilds the generation as every reset does; the replacement re-applies the expansion intent at readiness.
  Evidence: `tests/test_visualizer_expansion_two_display_edit.py` (the real entry, Save, Cancel, Settings and menu
  routes, the real coordinator and owner, a real clock display beside the hidden production scene drawn expanded:
  entry from either display by menu and shortcut with the view on display 0 or 1, red on the pre-fix entry; ordinary
  Edit with no expansion binds both from either; Save/Cancel on each; a Fullscreen draft against a request from the
  other display, and the reverse; a shared widget's X; the view's holds), `tests/test_visualizer_expansion_reducer.py`
  (traces and the invariant walk with the new entry), `tests/test_custom_layout_session.py`,
  `tests/test_custom_layout_contract.py` (held copies against the global Edit's result). Owed: the operator's
  physical two-monitor check.
- *Exits (decided).* An unsaved draft is never discarded or saved implicitly; nothing ends it but the user's own Save
  or Cancel (there is no runtime prompt to reuse: the session's user-choice path is Enter/Esc, the background
  double-click and the menu). The collapse glyph is withdrawn under Edit, as in every Edit, and a stale press is
  declined (above). Settings is held while the draft is pending: the menu entry is disabled (the menus refresh when
  the draft's state flips) and the route refuses; with a clean draft it opens as before (ending Edit loses nothing).
  The user's monitor change (a Visualizer transfer) is refused while expanded and under Fullscreen Edit. A physical
  topology change replaces the generation under the existing barriers, which retires the Edit owner like every Edit
  (nothing written; the overlays keep their committed value). Layout slot save and load are refused under
  Fullscreen Edit (a slot holds the ordinary layout; its save would save the draft, its load would discard it).
- *Visibility.* While editing both overlays reveal and hold (as Always Show) with quiet placeholders where there is
  no preset name or track yet ("Preset Name", "Track Title", "Artist"); their size and stacking follow at once (no
  easing to lag a frame); the OSD does not push them aside. When Edit ends they return to their authored visibility:
  Always Show (with content) stays, anything else fades out with its own fade.
- *Clear of the card's controls.* An overlay reaching into the column of the card's right-hand controls, from any
  corner, keeps clear of them vertically (the 3D hint above; the glyph row, Rotate Widget Content included, and its
  tips below). The column is measured from the card's size, the widest row and the tips' text only (never hover,
  admission or Edit), so nothing moves at runtime or on entering Fullscreen Edit; at zero offset every placement is
  M3b's.
- *Evidence.* `tests/test_visualizer_expansion_fullscreen_edit.py` (hidden production scene, the real owner, model
  and gestures, a real `SettingsManager`): the parity map (one gesture script on a draft, Cancel exactly, the same
  script, Save commits what the draft showed), byte-identical store after a Fullscreen-only Save and Cancel, the
  display manager's real Edit entry (no collapse call, the ordinary layout never quiesced, the Visualizer kept drawn
  under publications), the menu's Save ending Edit for the takeover, Settings held by a draft, visibility and fades,
  frames following content, the control column, guides on the Edit layer; plus reducer, coordinator, settings and
  pill bars. Fourteen M3c mutations (and five reducer ones, four schema ones) each turned a bar red. Stills
  (Extruded Bubble, PERSONALSET 859804, 1600 x 900) were handed to the lead outside the repository: the chrome, a
  mid-drag guide, a resized Now Playing, stacked Cards, after Cancel.
- *Now Playing's parts are the block's children (operator, 8 Nov: "I meant separately when there is no block visible
  but what we could do is allow movement within the block that is not drawn like we already do for child elements in
  normal geometry. I should be able to move every element around in that block and change it. The existing child
  geometry logic is probably good for this."; built on an agent branch).* Now Playing's Edit item is its **block**
  (`fullscreen_overlay.now_playing`: the whole overlay, artwork, text and Media Controls; the separate artwork item
  is gone). It mirrors how an ordinary widget enters child edit: the item declares ordinary Edit's child roles
  (`core.settings.fullscreen_overlays.NOW_PLAYING_CHILD_ROLES`: `artwork` = the freeform artwork frame, `title` and
  `artist` = uniform text roles like the Media card's metadata and artist, `controls` = a two-axis role like the
  Media card's transport controls; all movable), and the scene's presentation resolver for Fullscreen Edit
  (`QuickSceneController._fullscreen_overlay_presentation_item`) gives the block's frame the Now Playing slot as its
  presentation, which declares `customEditableChildRoles` exactly as `OverlayWidget` roots do. So the one child editor
  in `CustomLayoutOverlay.qml` (select the block, open its child lock by its glyph or L; the parts' frames, move
  areas, corner handles, side strips, child guides, containment, the global collision preference) drives the
  owner's own `begin_child_move` / `update_child_move` / `begin_child_resize` / `update_child_resize` /
  `preview_child_resize` / `cancel_child_gesture` (`resolve_child_*_geometry`), bound into the Fullscreen session by
  `bind_fullscreen_overlay_edit_session`; no second editor. The records live in the one value,
  `now_playing.child_geometry` (ordinary Edit's CUSTOM `child_geometry` carrier, parsed by `normalize_child_geometry`
  against the roles; `{}` = today's layout, and a value stored before it reads so; no bridge): per part a size factor
  of its own drawn size and an offset in fractions of 10 ems of the block's font (`CHILD_NORMALIZATION_EMS`), so a
  part keeps its place under the block's scale and the font size and never moves with a track's text length. The QML
  draws each part at today's place plus its offset, growing from its top-left (the child editor's contract): the
  artwork frame and the bar resize (the image crops), the text parts scale whole through applied `Scale`/`Translate`
  transforms (published to the editor as `customEditMappingDependency`); the block's own size never follows its parts
  (every natural size is the authored one, as ordinary Edit never grows a parent for a child edit) and a part is
  always drawn inside the block, card padding included (whatever a record says). The text parts' frames are their
  lines (as wide as the text draws, up to the box), so they can move across the box. Save writes the records with
  the rest of the placement, Cancel and undo (one step per gesture) restore them exactly, a part's edit alone marks
  the draft (Settings held), and Restore Size on the block also restores the authored parts (ordinary Restore Size's
  `restore_authored_child_geometry`). The block keeps its own handles: move, corner / wheel scale (every part
  follows) and its side strips, which set the text box that makes the block that size (its artwork beside its text
  box). **Room (decided):** the parts move within the block, which is as large as its content (today's layout) until
  its own side handles make it larger; that is ordinary Edit's rule (a child is contained in its parent; the parent's
  content box is the outer handles' job). **With a block surface (Card; decided):** the parts stay editable inside
  it, mirroring a widget with a visible card (the Media card's children are edited inside the card); the card is
  then the block's visible extent. Evidence: `tests/test_visualizer_expansion_fullscreen_edit.py` (real pointer
  events: selection, the lock glyph, three part moves and the artwork's side strip, containment, undo, Cancel, Save;
  with and without Card; scale-follow; a record past the edge drawn at the edge; eight negative controls),
  `..._overlay_settings.py` (records, old values); stills outside the repository
  (`D:\Temp\Scratch\SRPSS\evidence\expanded_visualizer\20261108_np_children\`: the hover sequence, the block
  selected with its parts open, title / artist moved, artwork resized, bar moved, after Save, before and after
  Cancel, and the same with a Card).
- *Also on this branch (operator, 8 Nov):* playback resuming (the Media model's paused -> playing edge) reveals Now
  Playing like a track change, keeping its content; Always Show is untouched; a pause is no event. And a bar that the
  display-wide card keeps the framed camera's controls (Reset Camera, the preset steps, the 3D hint) under the card's
  admission; the hover Edit lane (Restore Widget Size, Close, the transfer arrows) stays withdrawn while expanded (M2;
  its return is the operator's call, §3). The rotate glyph itself is Edit's and now on the expanded card in Fullscreen
  Edit ("Rotate Widget Content" above).

**Milestone 4 | Wallpaper transition policy and GPU savings**

- [x] Complete E0 diagram ([02_E0](02_E0_Covered_Display_Admission.md)). - [x] Exclusion at admission built 8 Nov
  (02_E0 "Built"); measurement below still open. - [ ] Implement batch-safe covered-display receipt/omission policy; test both screens with staggered, asynchronous transitions and image queue/history.
- [ ] Only after baseline receipt, suppress admitted GPU effect work on covered display; deeper source/decode/prefetch suppression optional and separately proven.
- [ ] **Gate 4:** another display still uses authored transition; covered display has no backlog or stalled batch; collapse re-enters safely. Record true GPU/CPU improvement vs original; no unmeasured 'dormant' claim.

**Milestone 5 | Mode/monitor/Settings/Editor transactional lifecycle**

- [ ] Test capable->capable (synthetic second capable descriptor fixture until another real mode opts in), capable->incapable, failed mode activation, mode-cycle double-click, context-menu mode and preset middle-click.
- [ ] Cross-display transfer at different DPI/size/refresh retains **one** controller, DSP lane, mode, authored state and exact owner retirement; source restored, target expanded.
- [ ] Cold launch expanded, repeat Settings open/close, active CUSTOM draft Save/Cancel, monitor hotplug/unplug/restart and terminal shutdown.
- [ ] **Gate 5:** deterministic event trace and resource-count proofs after multiple cycles; zero stale observer actions or leaking Qt/GL resources.

**Milestone 6 | Performance/fidelity and documented product admission**

- [ ] Run focused suite, native retained-QML tests, production replay captures and EB `tools/visualizer_live_check.py` at representative preset(s)/load, including other-display photo changes and real active music.
- [ ] Compare accepted EB BTF/reattack/settle/stream/drift, bead/particle appearance and GL/CPU frame-age tails to baseline. No new performance knob hiding source/renderer cost.
- [ ] Record closed risks with source and evidence, then update `Spec.md`, `Docs/Contracts.md`, `Docs/Reference/Visualizer_Reference.md`, `Docs/TestSuite.md`, and any focused 3D contract **only for proven new semantics**. Add historical-bug records only for rejected/faulty mechanisms. Avoid restating all source implementations in every doc.
- [ ] **Gate 6:** operator's only mandatory intervention is visual/physical acceptance of actual expanded appearance/controls and any installed build gate they personally choose to run. No agent product/installer build. Mark implementation accepted only after that evidence.

## I. Automated verification matrix (new test filenames are PROPOSED)

Plan test assets under `tests/` / `tools/`, align with `Docs/TestSuite.md` and current harness conventions. Do not create docs/defaults existence assertions or brittle text snapshots in place of functional tests. Never pin mutable visualizer presets. All synthetic config remains test-local. For Qt tests, use the real retained QML item when geometry/click delivery matters; no second QQuickWidget.

| Proposed focused test/harness | What it must prove | Failure is blocking? |
| --- | --- | --- |
| `test_visualizer_expansion_capability.py` | Registry opt-in EB only; disabled/unregistered mode inert; mode change policy and no import of dormant modes | Yes |
| `test_visualizer_expansion_persistence.py` | Normal/MC isolation, defaults, SST import/export/reset, mode-presets and Custom normalization across runtime transaction, no layout-slot corruption | Yes |
| `test_visualizer_expansion_reducer.py` | Ordered state transitions, idempotence, stale generation/activation reject, duplicate glyph, Edit cancel, topology/target failure rollback | Yes |
| `test_visualizer_expansion_geometry.py` | Exact display logical viewport, DPR conversion, aspect/camera and original rect restoration, clip/shell correctness, no unrequested settings writes | Yes |
| `test_visualizer_expansion_qml_native.py` | Real retained glyph hit/tooltip/fade, no action under menu/Edit, double/middle clicks unchanged, no HUD/OSD overlap or binding warnings | Yes |
| `test_visualizer_expansion_widget_leases.py` | Other-display lease survival, targeted retire/re-admit, no Media/OSD loss, deactivated family stays off, no Qt stale callback | Yes |
| `test_visualizer_expansion_transition_batch.py` | Whole batch never wedges; two-screen target change/status receipts, other-display effect, queue/history, no missed backlog, safe resume | **Critical** |
| `test_visualizer_expansion_transfer.py` | Old->new display owner transaction and rollback, mixed DPR/hotplug/absent display, no duplicate controller/pacer | Yes |
| `test_visualizer_expansion_lifecycle.py` | Cold expanded launch, Settings barrier, Edit Save/Cancel, warm replacement, terminal retirement, no resource/subscription growth | Yes |
| `test_visualizer_expansion_hud.py` | Event-only visibility, source identity/artwork, per-app volume vs system OSD, fade retirement, input priority | Yes |
| `tools/visualizer_live_check.py` with EB and real-music replay | No logical/render starvation, no source age/regression, accepted EB feel under game-shaped load | Yes for final acceptance |

**Execution rule:** focus new pure tests first; run only affected existing tests at each milestone; run `tests/run_chunked.py` at milestones, not after every source edit. Run project interpreter from `.venv`, no global installs. If PowerShell commands are supplied, keep each on one line with semicolons and no environment-variable setup. No GitHub Actions, no agent Nuitka/installer builds. Tests proving Qt/GL presentation must exercise real Quick consumers rather than drain bridge snapshots directly.

## J. Rollback, explicit non-goals, acceptance report

**Rollback:** each milestone can disable new capability admission via one canonical metadata gate and leave ordinary runtime unaffected. The gate must not leave orphan persistent `expanded_display_requested` values silently rewriting other settings; inactive intent remains harmless and explicit. Aborting an in-flight expansion restores the last accepted semantic state at a current-generation edge; do not blanket-cancel wallpaper runs or orphan resource generations. Any failed milestone stays unaccepted and cannot be 'fixed' by weakening BTF, switching to software/QWidget fallback, or recreating a second GL window.

**Not in this project:** SMP playback engine, library DB, playlists, new visualizer modes, Vulkan/FSR/DLSS, window pop-out, reworking Settings into live player mode, retuning EB presets/physics or expanding every mode without merit.

**End-of-gate report expected from implementing agent:** changed **complete files**, source/contract rationale, tests run with pass/fail summary (never claim unrun tests), artifact/trace locations, GPU/CPU timings compared to baseline, open issues, and a short **operator-only physical validation** list. Update durable contracts only after accepted implementation. Keep `Current_Plan.md` untouched until the operator explicitly admits the work.

# 02 | ShittyMusicPlayer: MC-First Implementation Plan

**Prepared:** 2026-11-05. **Live tracked document since 2026-11-07** (extracted from the plans zip, which was never  
tracked; this file is the one source of truth). Reviewed 7 Nov against `a295697c` with the  
[Architecture Checklist](../../Reference/Architecture_Checklist.md): §0A holds the prerequisite phases, the `--smp`  
gate, the phase ladder with entry/exit gates, owners, dormancy, lifecycle, budgets and risks; §13-16 hold the  
operator's box items (audio quality, the SMP Settings tab with pills, the icon and artwork rules, full rearrangement)  
as live checklist targets. Sections 0-12 are the original plan, corrected where the review found drift.  
**Status (12 Nov 2026, lead's decision):** admitted in order by `Current_Plan.md` item 9: SMP's foundations come after the native core's flip; `Current_Plan.md` governs the order. Do not implement ahead of that item.  
**Entry gates (12 Nov 2026):** the native core's flip (`Current_Plan.md` item 8b, NF) comes first. Waveform Ribbon and the Expanded Visualizer are accepted and are no longer gates (its display-takeover and dormant-resource contracts are needed by M6, not by M1-M5); the prerequisite phases in §0A.1 still land before the milestone each precedes.
**First visible implementation:** **Library + Playlists**, two independently placeable/resizable/movable MC panes that are **ONE widget entry** and ONE feature/capability in Settings. **Not** a playback-only stub followed by the library later.  
**Pre-profile gate:** deliver **Expanded Media in MC**, reusing the earlier display-takeover semantics, before creating a standalone SMP build/profile.  
**Products:** existing SRPSS/MC repository, then a third SMP desktop launcher/profile; exactly one canonical visualizer implementation shared with both. No separate repository/fork.  
**Proposal basis:** the proposal `Proposal.md` and its recovered `MusicBee_SRPSS_Concept_2026-09-24.png` (not in the tree; they shipped in the proposal zip and are design references only). The operator restored the full-player mock on 11 Nov 2026 with added Library/Playlist notes: `references/ShittyMusicPlayer-Miami-Afterdark-Mock-DETAILS.png` and a material example (`references/` is ignored by git); every annotation is transcribed, mapped to this plan's sections and extended with the lead's UX proposals in `04_Full_Player_Mock_2026-11-11.md`, which is the design reference from now on. This plan supersedes its *implementation order* wherever the original proposed Playback before Library/Playlist and adds an MC Expanded Media gate before product separation. It does not overwrite the original visual concept, which remains a design reference.

## 0A. Prerequisites, the `--smp` gate, phase ladder, owners and budgets (7 Nov review)

### 0A.1 Prerequisite phases from the architecture checklist (mark: must land before SMP work starts)

| Phase | Checklist item | Must land before | Why |
| --- | --- | --- | --- |
| **P1** | **AC-01** Settings tabs and pills become one descriptor registry with `pill_of` and `available(profile)`; Studio-owned mode bodies lose their hidden value-owner widgets; CONFIG-mode Settings owns one helper ThreadManager | **M1** (the `Library & Playlists` Settings entry) and the SMP tab (§14) | The SMP tab with pills, profile-conditional tabs and the SMP-only build's hiding all need one declaration point; without it every tab is four edits and a forgotten branch drops the remembered pill. |
| **P2** | **AC-03** application-service tier above display generations (**landed 7 Nov**: `core/application_services.py`, contract in `Spec.md` → Lifecycle "Application services") | **M2** (`LibraryRepository`) and **M3** (`PlaybackService`) | Settings tears the runtime down (`engine_handlers.py:355-600`); playback, queue and library must be owned by the tier, leased by generations. A teardown failure retires live services, then exits. Still to build at M1/M2: hand each generation its leaser (`DisplayManager` and the Settings dialog do not receive `engine.application_services` yet), a `core/smp.py` gate as the descriptor's `available`, and a lease-count edge if the repository idles on "no pane leases". |
| **P3** | **AC-02** Visualizer host binding; Media docking a placement policy | **M7** (SMP dock / Pop Out hosts); already landed for plan 01 | The docked Visualizer and Pop Out are second hosts of the one owner. |
| **P4** | **AC-05** one beat-engine authority (no module global, no in-tick fallback; **landed 7 Nov**) | **M3** (the decoded-PCM source) | A second engine input must bind through the controller's factory and lease, never through a fail-open process lookup. |
| **P5** | **AC-07** unchanged settings writes do not publish | **M8** (live Settings) | Live Settings re-saves groups; publication must mean change. |

P1 and P2 **must land before SMP work starts** (M1). P3-P5 land before the milestone named.

### 0A.2 The `--smp` gate (operator: "Gate SMP/Library/Playlist behind --smp until production ready and feature rich")

- [ ] **Mechanism:** `main.py`'s known-flag list (`parse_screensaver_args`, `main.py:254` on 11 Nov 2026) gains `--smp`; a side-effect-free
  predicate `core/smp.py::is_smp_enabled()` (beside `core/mc.py::is_mc_build()`, same style: entry point, profile
  or flag, no `SettingsManager` construction) answers True when the flag is present or the process is the SMP
  profile/entry point (M7). No environment variable, no settings key: the gate is a launch decision.
- [ ] **What it gates:** the `music_workspace` family's availability in `core/settings/widget_family_catalog.py`
  (absent from the catalog's available set, so no Settings row, no capability activation, no CUSTOM slot, no
  import); the SMP Settings tab descriptor's `available()` (§14); the internal `smp` Media provider; the SMTC
  publisher; the SMP desktop host entry point. With the gate off, every one of these is unreachable and
  `test_smp_cross_product_dormancy.py` proves zero cost.
- [ ] **What it never gates:** existing Standard/MC behaviour, defaults, presets or layouts. A profile that saved
  `widgets.music_workspace.*` while gated-on keeps the values when gated-off (inert, not deleted).
- [ ] **Lifting it:** at **Gate M9** (usable standalone player, codecs measured, library migrations proven, no
  contract weakened) the gate flips to default-on for MC and the SMP profile; Standard SRPSS stays without SMP
  unless the operator decides otherwise. The flag remains as an explicit opt-in until then and is removed, not
  inverted, afterwards.

### 0A.3 Phase ladder with entry and exit gates

| Phase | Entry gate | Exit gate (evidence) | Signs |
| --- | --- | --- | --- |
| **P1** AC-01 | Waveform accepted; `Current_Plan.md` admits P1 | AC-01 regression bar green for every existing tab; CONFIG-mode helper manager single | lead |
| **P2** AC-03 | P1 merged | AC-03 regression bar green; Settings open/close keeps a stub service; `Spec.md` → Lifecycle records the teardown-failure rule | lead |
| **M0** audit and baseline | P1, P2 merged; operator admits plan 02 | source SHA and changed contracts inventoried; two-pane fake-family integration tests written; Standard+MC idle import/service/thread/widget counts recorded | lead |
| **M1** `music_workspace` family, two panes | M0; `--smp` gate built | two rectangles moved onto different monitors and restored; one Settings row; one family; `test_music_workspace_family.py`, `_qml_native.py` green; dormancy test green with the gate off | agent |
| **M2** offline library + playlists | M1; P2 | a real folder (≥ 5,000 tracks) indexed with the GUI responsive (no GUI stall > 16 ms in the stall sampler); every action survives restart and Settings; no audio file altered (hashes before/after) | lead |
| **M3** playback service, queue, PCM source | M2; P4 | codec matrix measured (§13); playback survives pane close, Settings teardown, mode switch; one DSP lane; PCM-to-audible latency calibrated (§13); `tools/music_backend_native_smoke.py` report | lead + operator listen |
| **M4** library UX, metadata, art, groups | M3 | three-membership limit under concurrent writes; favourites survive rescans; art cache bounded (bytes); tag-edit corpus undamaged | agent |
| **M5** internal Media provider + outbound SMTC | M4 | SMP plays while Media shows Spotify; exactly one media-key recipient; own session excluded from GSMTC reading | agent |
| **M6** Expanded Media in MC | M5; plan 01 accepted | cross-feature tests (EB expanded <-> Media expanded) green; two-display visual acceptance | operator |
| **M7** SMP profile and desktop host | M6; P3 | snapping, taskbar, focus, Alt+Tab, mixed DPI, hotplug; same audio/visualizer state across compact/full/immersive; no wallpaper engine constructed; §16 rearrangement bar | operator |
| **M8** live Settings policy | M7; P5 | repeated Settings/mode/Pop Out/SMTC/close cycles keep media state; Qt/COM/DB/GL counts bounded | agent |
| **M9** release | M8 | 4-run soaks; concurrent MC/SMP DB; build payload reachability; `--smp` lifted (§0A.2) | operator |

### 0A.4 SSOT owners

| Thing | Owner | Never |
| --- | --- | --- |
| product identity (Standard / MC / SMP; `--smp`) | `core/mc.py` + `core/smp.py` predicates, resolved from the entry point/profile/flag | a settings key, an env var, a second resolver |
| `music_workspace` family, two member ids | `core/settings/widget_family_catalog.py` + `rendering/widget_descriptors.py` | a second capability, a third pane identity without operator authorisation |
| `widgets.music_workspace.*` (enabled, per-pane visible/monitor/position, appearance) | canonical defaults + `SettingsManager`, profile-scoped | the library DB, a sidecar |
| library, playlists, favourites, groups, art cache index | `LibraryRepository` (SQLite in the shared non-settings data root), application-service tier (P2) | `settings_v2.json`, tags, QML |
| playback, queue, output device, state revision | `PlaybackService` + `QueueController` in the service tier; one per process that activates it | Media widget, playlist pane, SMTC, GSMTC |
| decoded-PCM analysis source | `AudioAnalysisSource` adapter into the one controller-owned BeatEngine source boundary (P4) | a second engine, a loopback of SMP's own output |
| Media provider kind (`external_gsmtc` / `internal_service`) | `core/media/provider_registry.py` typed descriptor | an AUMID spoof |
| SMP Settings tab and pills | the tab registry descriptor (P1), §14 | per-tab if/elif chains |
| icon and artwork precedence | §15 (`images/SMP.ico`; `core/media` artwork resolver) | per-widget copies |
| pane and panel arrangement | MC: the ordinary CUSTOM owner and layout slots; SMP host: one dock/split layout model with semantic slots (§16) | pixel rects alone |

### 0A.5 Dormancy: nothing costs anything when SMP is off

Prove at every milestone (`test_smp_cross_product_dormancy.py`) and record in the handoff:

- gate off (Standard, MC without `--smp`): zero new modules on the common Quick import and on Settings open (import
  scan); zero new QObjects, threads, COM objects, SQLite handles, audio devices, SMTC sessions; `overhead_baseline`
  counts identical; the family absent from the catalog's available set.
- gate on but family OFF: the catalog row exists; no `LibraryRepository`, no DB open, no scan thread, no
  `PlaybackService` until a real consumer leases it; opening Settings builds the SMP tab lazily like any tab.
- panes hidden, no playback: per-display views released; the repository idles and closes connections; no polling,
  no filesystem watcher (scans are user actions or one opt-in change worker).
- displays off: playback and analysis continue (audio is not presentation); SMP presentation parks like any
  display content; no toast, no HUD animation while parked.
- SMP-only build: image-saver workers, wallpaper transitions, screen capture, monitor stagger, Reddit/Gmail/Steam
  families are never imported (payload reachability report at M9).

### 0A.6 Lifecycle contracts

- Service lifetime (P2): created on the first lease, retired at terminal `cleanup`; display generations lease and
  release; a stale generation's lease cannot command the service; Settings teardown (MC) leaves it playing.
- Exactly one `PlaybackService`, one `QueueController`, one command queue (manual, media keys, SMTC inbound,
  Media widget are adapters); command completion is observed, never assumed.
- Decoded PCM is captured once at the media owner boundary with device-latency-calibrated timestamps and enters the
  existing one-in-flight + newest-pending analysis lane; source selection is explicit (§4.2); never both decoded PCM
  and WASAPI loopback of the same audible track.
- Pop Out / dock (M7): mutually exclusive render hosts of the one owner; context-local GL resources rebuild on the
  destination after the source root is fenced and destroyed; no interval with two live renderers.
- DB: worker-thread-owned connections, one writer policy, WAL, bounded busy timeout, backups before migrations,
  multi-process (MC + SMP) write policy tested before M7.
- Settings (M8): SRPSS/MC keep full teardown; SMP's live Settings is a separate application policy with reversible /
  controlled / deferred / restart classes per setting (§9); late callbacks from closed Settings fail closed.
- [ ] **Visualizer during live Settings (operator, 7 Nov, binding):** with SMP's live Settings the Media widget and
  playback stay visible and playing, and the Visualizer will usually have been on. While Settings is open the
  Visualizer **pauses into dormancy**: parked, its capture/analysis lease released or idle, no ticks, no GL work, zero
  cost by the overhead benchmark. When Settings closes it **resumes successfully**: same mode, preset and camera, a
  fade-in rather than a pop, no stale frame, the beat engine re-admitted. Exactly one Visualizer and one beat engine
  may exist at every instant, including across the open/close edges; never a second instance for a Settings
  preview. A setting changed in Settings that the Visualizer reads applies on resume through the normal reapply
  path. Acceptance:
  - repeated open/close cycles with music playing (Visualizer on, every mode family 2D and 3D) keep the media state;
  - a dormancy proof while Settings is open (overhead benchmark: Visualizer GL/Python calls 0);
  - a resume-parity capture (the first frames after close match an uninterrupted run, within the mode's own replay
    tolerance);
  - a negative control: the Visualizer left ticking while Settings is open fails the dormancy check.

  Lead's opinion on MC builds: MC would benefit from live Settings, because today every Settings visit tears down
  and rebuilds the whole runtime, which is slow and stops the Media widget. It is harder there than in SMP: MC's
  display runtime is the screensaver/media-centre presentation itself, so live Settings means the AC-03 service tier
  plus a per-setting reapply class for every display, widget and transition setting, not only for SMP's own groups.
  Recommend building it in SMP first (M8), then deciding on MC from SMP's measured reapply coverage, rather than
  making it an MC prerequisite.

### 0A.7 Performance budgets

| Budget | Target | Measurement |
| --- | --- | --- |
| audio underruns | 0 in a 30-minute soak at every supported sample rate, shared and exclusive mode | backend counters + recorded loopback null test (§13) |
| decoded-PCM to audible latency | measured per device and applied as the analysis timestamp offset; error ≤ 10 ms | loopback recording of a click track against the PCM timestamps |
| visualizer budgets | unchanged (`Visualizer_Change_Checklist.md` §1C); immersive at 4K uses plan 01 §0.7 | `tools/visualizer_live_check.py` with the SMP PCM source and with external WASAPI |
| GUI thread | no stall > 16 ms during scan, search, scroll, art decode (stall sampler); list delegates virtualised | `--gui-stall-stacks` sidecar |
| library scan | ≥ 200 files/s metadata-only on local SSD, cancellable within 100 ms | scanner benchmark on a fixture corpus |
| art cache | bounded by bytes (default 256 MB) and count; thumbnails decoded off-GUI | cache stats in the handoff |
| DB queries behind the panes | p95 ≤ 20 ms on a 50,000-track fixture on a worker thread | query benchmark |
| idle footprint with SMP on, nothing playing, panes visible | ≤ the ordinary widget set + the DB handle; no timer | `--usage` sampler |

### 0A.8 Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Qt Multimedia cannot deliver gapless / exclusive / bit-perfect output | high | high (audio quality is the operator's bar) | §13 measures first; the backend behind `PlaybackService` is private and replaceable; custom WASAPI output is admitted when the trial fails a measured criterion |
| two writers on the shared DB (MC + SMP) | medium | high | one write policy, WAL, lock tests before M7 |
| playback dies with Settings teardown | certain without P2 | high | P2 before M2 |
| SMP tab bloats Settings or copies the hidden-owner pattern | medium | medium | P1 registry; §14 pills; no hidden QWidgets |
| artwork writes into the user's music folders | medium | high (user data) | §15: opt-in, default off, never overwrite, provenance sidecar |
| third pane identity creeps in (queue, now-playing) | medium | medium | §3.2: queue is a view inside the playlists pane; a third top-level identity needs the operator |
| SMTC WinRT availability in the frozen build | medium | medium | probe before promising; playback never depends on it |

---

## 0. Repo audit: accepted contracts and gaps

Source inspected from `Basjohn/ShittyRandomPhotoScreenSaver` default `main` on 2026-11-05. **No proposed SMP feature exists yet; no code/test/build was executed for this plan.** Re-audit changed source at admission time and record exact commit.

| Existing authority | Observed behaviour | Allowed extension / risk |
| --- | --- | --- |
| `Spec.md`; `Docs/Contracts.md`; `rendering/quick/runtime.py` | Retained Qt Quick/GL presentation, no `QQuickWidget`, one accelerated display surface in SRPSS/MC | MC panes use existing Quick display; SMP native desktop host may own a separate top-level window, but never change screensaver physical rule. |
| `rendering/widget_runtime_manager.py`; `rendering/quick/widgets/family_binder.py`; `rendering/quick/display_presenter.py` | Family activation -> per-member admission -> presentation/neutral service; binder maps one `widget_id` to one retained presentation | One Settings *feature entry* may own two member IDs/geometry roots. Must extend descriptors/Settings navigation consistently; **do not** cram two independent desktop rectangles into one retained card. |
| `core/settings/widget_family_catalog.py`; `rendering/widget_descriptors.py` | Family membership/admission distinct from per-widget enabled | Register **one `music_workspace` family**, with exactly two presentation member identities. Independent pane visibility/rect/monitor is not a second capability. |
| `core/settings/settings_manager.py`; `core/settings/defaults.py`; `default_settings.py`; `default_profile_overrides.py` | One canonical SettingsManager; Normal + MC defaults; applied values and lazy settings construction | One `widgets.music_workspace` schema/Settings section; one canonical default for each field; store DB content *outside* settings. No copied `SMPSettingsManager`. |
| `core/settings/json_store.py::determine_storage_path`; `core/settings/storage_paths.py` | Normal/MC settings separate; canonical non-settings data root shared. Unknown profile names isolated. | SMP will require explicit canonical profile **and defaults resolver updates**; simply adding a third folder mapping is insufficient. Keep test `StorageRoot` isolation. |
| `main_mc.py`; `main.py`; `core/mc.py`; `core/build_profile.py` | MC delegates to shared main and forces Interaction; diagnostic identity is a separate build flavour | Initial workspace and playback live behind MC admission. Later define host/profile/flavour separately, without filename-sniff fallback or new environment variable. |
| `engine/engine_handlers.py::on_settings_requested` | MC/SRPSS Settings triggers complete engine stop, Qt destruction barrier, and display replacement | A long-lived music service **must be owned above** the MC display generation if playback should survive Settings. Do not weaken screensaver barriers. |
| `widgets/media_runtime.py`; `core/media/media_controller.py`; `core/media/provider_registry.py` | Shared generation-scoped Media/GSMTC **reader**, event-driven observation, serial command lane; provider registry represents **external** GSMTC sessions | Internal SMP provider must be a typed *in-process* adapter. Do not spoof GSMTC or make Media selection control player lifetime. |
| `widgets/spotify_visualizer/*`; `core/settings/visualizer_mode_registry.py` | Exactly one shared authored logical clock, DSP lane, immutable frame/snapshot bridge, mode-owned settings | SMP output PCM must adapt to the existing source boundary; no second BeatEngine or mode-specific copy. |
| `rendering/quick/qml/MediaPresentation.qml`; `rendering/quick/widgets/media.py` | Rich retained Media styling, external app-volume accessory, uniform whole-card transform | MC Expanded Media needs responsive **large-screen reflow**, not merely scaling the small card to monitor width. Small/expanded views share state and semantic style. |
| `rendering/quick/qml/DisplayScene.qml` | OSD, context menu, visualizer, ordinary families have explicit layering | MC expanded media uses the first plan's safe display takeover. No new native overlays inside MC. |
| `Docs/Guardrails/Visualizer_Presentation.md`; BTF; Performance Optimization Contract | Source freshness, authored reactivity, renderer/Qt retirement outrank FPS optimizations | Never change DSP/fidelity to compensate for player's decode or GUI load. |

**Must read on admission:** `Docs/00_PROJECT_OVERVIEW.md`, `Spec.md`, `Docs/Contracts.md`, `Docs/TestSuite.md`, `Current_Plan.md`, `Docs/Guardrails.md`, `Docs/Guardrails/Performance_Optimization_Contract.md`, `Docs/Guardrails/Visualizer_Presentation.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md`, `Docs/Guides/10_WIDGET_GUIDELINES.md`, `Docs/Guides/Visualizer_Change_Checklist.md`, `Docs/Architecture/Settings_Bucket_Persistence_Contract.md`, `Docs/Reference/Visualizer_Reference.md`, `Docs/Reference/Guided_Setup.md`, and the *accepted* Expanded Visualizer reference/contract created under Plan 01.

## 1. Product invariants (not negotiable)

- [ ] Same repository, same mode registry, same preset/catalogue, same controller/logical/FFT/source freshness semantics, same shared Quick implementation for compatible visualizers. No SMP-specific shader/mode fork, no second Qt theme engine, no parallel player-specific visualizer Settings builders.
- [ ] Standard SRPSS when the player feature is disabled has zero new decoder/DB/SMTC/PCM worker/device/session cost, zero imported SMP implementation tree on common Quick/module import, and no new QML scene object activation. MC without music-workspace/player admission is equally dormant.
- [ ] Shared library/playlist/database state is not ordinary widget lifetime. Hide or close either pane, enter Expanded Media, open Settings, switch visualizer modes or pop out a renderer without stopping playback, clearing queue, closing shared DB mid-write or losing metadata.
- [ ] One playback service and one queue authority per process that explicitly activates it. No dual command ownership via Media, playlist pane, SMTC or external GSMTC. These are control adapters to the service.
- [ ] Audio output and visualizer analysis are distinct: actual audio can play with no visualizer; external-provider Media can be selected while SMP keeps playing; source choice is explicit and never feeds an internal track both through decoded PCM and WASAPI simultaneously.
- [ ] Metadata scanning/editing is bounded, cancellable and off GUI/render/audio-critical lanes. No auto rewriting tags, modifying artwork inside sound files or auto deleting duplicates. User groups/favorites persist in the library database, not in genre/comment metadata or `settings_v2.json`.
- [ ] **One widget entry / two independent panes:** one family activation and one grouped Settings entry, two separate retained presentation identities/rectangles, separate optional visibility, independent route/position/size, one shared library state model. Moving one pane never drags/reanchors the other by hidden coupling.
- [ ] Existing Settings semantics and complete runtime teardown remain unchanged for SRPSS and initially MC. SMP's later live Settings is a **new application policy**, not a dismantling of SRPSS's lifetime contract.
- [ ] New optional Qt/WinRT/metadata/library imports are lazy. Registry/Settings metadata itself remains pure and side-effect-free; no COM, SQLite open, audio device or network at import time.
- [ ] Screensaver/MC one-QQuickWindow-per-display contract remains. SMP native host and optional Pop Out must own their own bounded windows, but never permit two active renderers for the one visualizer or two analysis clocks.
- [ ] Operator mutable presets are immutable only as **ownership boundaries**, not as data snapshots: never pin current preset values as test oracle. Tests use synthetic owned fixtures and BTF/replay performance oracles.
- [ ] No podcasts. Optional lyrics start local embedded/.lrc only. MusicBrainz/Cover Art Archive and optional matching are opt-in and rights-conscious; audio format support is measured and disclosed, not promised as universal.
- [ ] No product build/installer or GitHub Actions automatically run by an agent. Tests are local, focused and project-venv isolated. PowerShell examples remain one line, no environment-variable configuration; deliver source changes as full files and work artifacts as ZIPs.

## 2. Target ownership map (one application, many presentations)

```text
SRPSS Standard / MC / future SMP entry point (profile + host selection)
  |  canonical SettingsManager/defaults/schema/repair (profile-scoped)
  |  canonical capability catalog + lazy registry (no service startup)
  |
  +-- MusicWorkspace feature activation [MC, SMP only]
  |     +-- Application MusicLibraryOwner (shared DB/index/search/metadata/art)
  |     +-- MusicWorkspaceDisplayAdapter (display-local, no DB ownership)
  |            +-- music_library pane [its own rect/edit/route/visibility]
  |            +-- music_playlists pane [its own rect/edit/route/visibility]
  |     +-- one Settings entry 'Library & Playlists' (two internal geometry groups)
  |
  +-- Optional PlaybackService [one process owner, independent of panes]
  |     +-- QueueController and PlaybackState publication
  |     +-- QMediaPlayer backend candidate + output device
  |     +-- internal PCM -> existing Visualizer source selector
  |     +-- optional Windows SMTC publisher (outbound, not GSMTC reader)
  |     +-- internal Media provider adapter (existing Media widget can opt in)
  |
  +-- one canonical Visualizer controller -> one logical clock/DSP -> one current render host
  |     +-- MC selected display Quick scene (existing)
  |     +-- SMP docked Visualizer OR SMP popout native Quick host (never both active)
  |
  +-- ExpandedPresentation policy, reused semantics
        +-- EB Expanded Visualizer in SRPSS/MC (Plan 01)
        +-- MC Expanded Media (new milestone below)
        +-- SMP immersive music display (its own desktop host)
```

Names are illustrative: align with current descriptor/adapter conventions. **PlaybackService is not created by constructing the Library QML, nor is LibraryRepository a singleton in a shared import.** Application-owned service lifecycle uses explicit creation/retirement and real consumer/cardinality semantics; loose process-global singletons that survive shutdown are forbidden.

## 3. First visible deliverable: one Library & Playlists widget entry, TWO movable panes

### 3.1 Identity/schema decision (mandatory preflight)

Recommend `music_workspace` as one capability and one Settings navigation item. The *retained presentation members* need separate stable IDs (illustratively `music_library` and `music_playlists`) because `WidgetRuntimeManager` and `OrdinaryFamilyPresentationBinder` currently require one widget ID per display-visible, retired, movable presentation root. Store their layout in one coherent canonical `widgets.music_workspace` subtree with two named geometry branches or equivalent existing layout descriptor mechanism:

```text
widgets.music_workspace:
  enabled: bool                      # master ordinary ON/OFF (not capability activation)
  library:
    visible: bool                    # per-pane opt-in; not a second family activation
    monitor: route                   # preserve physical display identity
    position: placement              # current ordinary/CUSTOM layout vocabulary
    [content_extent, semantic child geometry only if actually consumed]
  playlists:
    visible: bool
    monitor: route
    position: placement
    [content_extent, semantic child geometry only if actually consumed]
  [shared appearance and browsing/selection settings, where legitimately profile-local]
```

**Critical integration audit:** `rendering.widget_descriptors`, `core.settings.widget_family_catalog`, `capability_activation`, `WidgetRuntimeManager`, display route filtering, Settings SETUP, CUSTOM three-slot load/save/undo, stored geometry normalization, pane-specific close/restore, Guided Setup and `Docs/Contracts.md` must agree. If this one-Settings-entry mapping is simpler with current canonical `widgets.music_library` / `widgets.music_playlists` children, that is acceptable **only if** the UI groups them as ONE feature and there is exactly one capability/master authoring authority; never silently create a second widget Settings entry. Define canonical mapping once and test it through both schema and retained Quick projection.

- [ ] One Settings row **Library & Playlists**, not two separate widget rows; page offers Library and Playlists subsections/toggles plus their shared controls. One family activation button and one master ordinary enable. Both pane toggles can be independently changed without toggling the family.
- [ ] One selected default arrangement can show both panes on MC or just one, but selection is operator editable and route-aware. Independent rectangles are real, not fake columns inside one unmovable card. Each pane can live on a different participating display if the operator places it there.
- [ ] Parent pane geometric intent uses existing anchor/margin and CUSTOM rect/slot semantics; child roles are declared stable across data updates. Library track rows and playlist items are **not** new draggable top-level widget identities.
- [ ] Each pane can be independently moved, resized, hidden/closed/restored. Dragging the library does not move playlist; resizing playlist does not reflow library except through intentionally selected global automatic stack policy. Preset/click/edit semantics remain coherent across separate displays.
- [ ] When a pane is hidden, release only its per-display view/adapters; retain one database/index owner when another pane or active playback needs it. Master family OFF retires both panes, but application-owned playback can continue if active.
- [ ] When both panes hidden and no playback/library background jobs are authorized, the library owner can close/idle connections; avoid persistent IO threads solely for a toolbar label.
- [ ] In SMP desktop host these same pane IDs are separate dockable/splittable regions, not SRPSS CUSTOM editor impersonations. MC uses current retained scene/edit mechanisms.
- [ ] Test display transfer, monitor off/return, mixed DPI, saved layout slot, theme, double click, selected Edit mapping, disabled family and Settings restart. No saved rect disappears because its pane is hidden.

### 3.2 Initial working UI with no music engine yet

The first *functional* milestone should produce a useful offline library and saved-playlist organiser **before** adding a durable playback backend. It may expose 'Play' disabled with an honest tooltip until later milestone. Do not build placeholder play buttons pretending playback exists.

**Library pane:** folder picker; incremental scan progress/status/cancel; live list of indexed tracks (track, title, artist, album, duration, optional genre), filter/search/sort, explicit refresh/rescan, track properties, safe missing/unknown file treatment. Do not require audio output to browse files. Search/selection must be keyboard accessible; large collections use bounded pagination/virtualization rather than thousands of simultaneous Quick delegates.
The search and filter entry points of this pane follow the full-player mock: a search glyph that opens a library
filter drop-down and a favourites heart that applies the favourites filter, both owned by one filter owner (§5.1; mock
R7, R8). The first milestone needs only the plain search; the glyph pair is the long-range shape.

**Playlist pane:** list of named playlists; create/rename/delete with confirmation; select list, order items by drag/move/keyboard, add/remove selected tracks, reorder persistently, explicit save, distinguish frozen playlist vs dynamic query. A separate *current queue* tab/view can be introduced **inside the playlists pane** when playback arrives; this is not a third separately placed widget unless operator later authorizes it. Support an empty playlist gracefully.
In the full-player mock the right column's "Playing Tracks" is this same Playlist pane shown as a compact
presentation (artwork, title, artist, duration and a menu per row, the playing row highlighted); it is one widget
entry with the pane, not a second widget (§4.1; mock R10).

**Interaction between panes:** selecting Library tracks and 'Add to playlist' should update Playlist pane through shared immutable library/playlist revision (not direct QML-to-QML references). Independent layout roots but one query/service owner. Deleting a playlist never deletes tracks. Duplicate named playlists require a clear policy. Missing-file entries remain visible/repairable rather than silently disappearing and reindexing the playlist order.

### 3.3 Persistence layout and initial DB

- [ ] `LibraryRepository` built above scene generations; SQLite candidate in shared `%APPDATA%/SRPSS/` non-settings root, with explicit `StorageRoot` isolation for tests/tools. Separate profile-local *pane geometry/preferences* from shared library/playlist content.
- [ ] Transactional schema/migration ledger with version, rollback/backup before destructive migrations, integrity checks, journaled scans, WAL where appropriate; SQLite connections are worker-thread-owned, not shared Qt/GUI objects. One writer policy with bounded busy timeout and retry; never indefinite GUI waits.
- [ ] `tracks`: durable identity, normalized path, stable metadata projection, file stat/signature and availability; `playlists`: stable ID; `playlist_entries`: ordered ID/position, referential constraints and missing-file retention. Search index optional FTS if supported by shipped SQLite.
- [ ] Track identity must survive safe rename/move where deterministically recognised; path alone is not the identity. Avoid false merges when same title/duration exists in two recordings. Rescan has conflict policy and only updates authoritative fields after a verified identity match.
- [ ] Select paths/root folders explicitly; avoid scanning entire drives, system directories, removable/network drives unexpectedly. Prevent symlink cycles, out-of-root traversal, duplicate roots and unbounded recursive directory work.
- [ ] Discovery/parsing/index work is cancellable and bounded; no UI thread blocking, no per-delegate file stat/decoder, no filesystem polling. Scans may be triggered by user action or an opt-in scheduled change worker with a single authority, not dozens of watch timers.
- [ ] Asset validation: path containment, media format detection, filename surrogate/Unicode, missing file, permission error, odd tags, corrupt/truncated audio and very large directories. No unexplained silent skip; record per-file errors compactly.
- [ ] Cross-process MC/SMP compatibility: DB shared; no two independent writers racing. Need an explicit multi-process test and backup/restore proof before separate SMP entry point is admitted. DB must not be a hidden settings JSON mirror.

## 4. Playback phase, only after Library/Playlist model acceptance

### 4.1 Service/queue contracts

*Qt 6.12 (the project's Qt since 12 Nov 2026; `Docs/Future_Work/Qt_6_12_Gains.md`):* if playback uses Qt
Multimedia's `QAudioSink`, its buffer period is settable since 6.12 (`setNativePeriodFrameCount()`, powers of two from
32 to 4096 frames, only while stopped; on Windows it maps to the audio client's buffer duration, default about 1024
frames). Choose the period once from the Visualizer's latency budget and the PCM source seam
(`03_PCM_Source_and_Native_Core_Seams_2026-11-09.md`), measured, not left at the default.

Define small interfaces first (illustrative, not new business superclasses): `PlaybackService` (output, commands, state and exactly-once retirement), `QueueController` (ordered track references, shuffle/repeat/history), `LibraryRepository` (read-only queries/transactions), `AudioAnalysisSource` (timestamped decoded PCM adapter), `PlaybackStateSnapshot` (immutable revision, track identity, provider, position, playing, audio generation). Clear player lifecycle is distinct from window and display lifetime.

- [ ] Begin with local file play/pause/stop/seek/volume, one player-owned stream, one queue and one persisted player state. If media missing/unsupported, fail action with visible reason while preserving queue and library.
- [ ] `QMediaPlayer` + `QAudioOutput` and FFmpeg-based `QAudioBufferOutput` under pinned Qt/PySide6 is a **candidate**, not guaranteed format/gapless/latency acceptance. Build a native Qt/Windows smoke using actual MP3, FLAC, Ogg/Vorbis, Opus, WAV and AAC fixtures available legally. Measure codec load, play, seek, rate, duration and repeat. Document unverified formats as unsupported until proven.
- [ ] Decoded PCM is captured **once** and timestamped at the media owner boundary, not by a second WASAPI loopback of SMP playback. Calibrate decoder buffer timestamps to audible output with device latency measurements; a PCM signal being emitted is not proof speaker sound played then.
- [ ] Feed the **existing** BeatEngine/analysis worker via a single selected source descriptor and its one-in-flight + newest-pending rule. Preserve floor/ramp, freshness, pauses, silence and all mode numerical reactivity. Avoid a new per-song FFT or visualizer-specific gain overlay.
- [ ] Stream/player device switching is an explicit, retryable service transaction. Preserve queue and intended playback position when possible, but do not promise sample-exact continuation if the backend cannot guarantee it.
- [ ] Define service lifetime above the MC display graph, with an app-level owner and explicit shutdown path. Opening MC Settings may retire all Quick display roots; player keeps playing if the operator has actually started it. Do not hold a retired QML model or generation-owned signal/worker as a surrogate player owner.
- [ ] Presentation adapters subscribe to latest revision; stale track/artwork/seek commands rejected by generation or item identity. The library/playlists UI may disappear/reappear without restarting audio or resending a duplicate command.
- [ ] Queue order is independent from library sort/filter and playlist order. A playback queue can be made from a playlist snapshot, then independently re-ordered without silently rewriting the saved playlist. Repeat one/all, shuffle with stable history, previous, seek and end-of-queue have exact tests.
- [ ] Manual user command and Windows media-key ingress share one command queue; command completion/error is observed, not assumed on worker submission. Replaying a click should not double-advance a track.
- [ ] **Playing Tracks is the Playlist widget, compact (full-player mock R10):** the queue view of the Playlist pane
  (§3.2) has a compact presentation for the full-player window's right column. It is the same widget and the same
  model as the pane, one widget entry; it never becomes a third top-level identity or a separate queue implementation.
- [ ] **Transport bar uses what exists (full-player mock R12 to R14):** the volume control is one of our existing
  sliders and the seek bar is the existing `MediaSeekBar.qml` (already one shared component), matched for length to
  the bar; no second slider or seek implementation is written for the player. Every control in the bar, both sliders
  included, sits on one horizontal alignment; correct alignment is a core requirement of the bar, checked by a
  geometry assertion in the native Quick test, not by eye.

### 4.2 Source and Media provider arbitration

Current `core/media/provider_registry.py` encodes explicit external Windows GSMTC identities. **Do not** shoehorn SMP into that dictionary as if an AUMID from the player were the controller for the in-process service. Introduce a typed neutral provider descriptor with `external_gsmtc` versus `internal_service` source kind at the same canonical dispatch boundary, leaving all existing external IDs/behaviour intact.

- [ ] `smp` is an explicit selectable **internal** Media source when service is available. It reads `PlaybackStateSnapshot` and calls service commands directly; it never queries its own SMTC through global GSMTC.
- [ ] Keep Spotify, MusicBee, browser, Apple Music and YouTube Music external sources selectable; keep their specific source identification and fallback rules. No implicit provider activation when SMP starts.
- [ ] SMP can play with the Media widget set to Spotify. The Library/Playlist pane controls SMP independent of current Media provider. The visualizer may be configured to follow the selected Media source or an explicitly selected active player source; specify a deterministic default and provide clear UI indication. Do not silently mix signals.
- [ ] When switching sources, retire source-specific subscriptions/generations cleanly, preserve playback/queue, avoid stale metadata/art flashes or dual decoded+loopback analysis of the same audible track. Changing Media selection cannot kill player or auto-restart system sources.
- [ ] Existing Media's app-volume vs system-volume availability and wheel behaviour remain truthful for internal and external providers. No synthetic provider capabilities.

## 5. Library maturity is a pre-profile acceptance gate, not future hand-waving

### 5.1 First-class favorites, groups and browse modes

- [ ] Favorites: durable boolean on canonical track ID, heart in Library/Playlist/Media details, cached filter; rescan/rename never erases it. No silent tag write.
- [ ] Named personal groups: unlimited **catalogue** entries, but at most **three distinct memberships per track**. Transaction/DB enforcement (not UI-only). Group rename/reorder/delete; right-click Add to group / Create group / Remove, bulk-add bounded transaction; clear error upon fourth membership. Group is a dynamic collection/query, not an ordered playlist.
- [ ] Explicit DB constraint (foreign keys + unique track/group; trigger or transaction-level enforced maximum with multi-writer tests). Concurrent MC/SMP attempts to add fourth membership cannot slip through.
- [ ] Browse **All / Artists / Genres / Favorites / Groups**, with dense list and cached artwork grid; selection and keyboard navigation stable across category switches. Display group mosaics, accurate counts, search, sorting and drill-down. No synchronous high-resolution art decode in GUI delegates.
- [ ] Build 'Play group', 'Queue group', and 'Save as playlist' as explicit snapshot/queue operations. A group's playlist export must not silently sever future dynamic membership semantics; label snapshot vs dynamic clearly.
- [ ] **One filter owner, two entry glyphs (full-player mock R7, R8):** the favourites filter above and the library
  filter drop-down are one filter owner over the same list. The favourites heart is the same control as the search
  glyph but applies the favourites filter; the search glyph opens the library filter drop-down. A filter stays
  applied until the user unselects it, and the glyph glows slightly while a filter is active. Neither glyph owns a
  second filtered copy of the list.
- [ ] **Audiobooks as a Library special group (full-player mock R2, long-term goal):** the full-player navigation
  shows AUDIOBOOKS where the concept image showed Podcasts, so §8.2's removal of Podcasts navigation stands and this
  replaces it. Audiobooks are a special group in the Library, not a separate product area: the user can add and
  remove audiobook items, save bookmarks at track points, and use chapter support and the like. Bookmarks and
  chapters are Library data under §3.3 persistence (database rows keyed by canonical track ID, never tags or
  `settings_v2.json`) and are bound by the same explicit-write and no-silent-tag-write rules as groups. This does not
  admit podcasts (§1, §12).

### 5.2 Artwork and metadata

*Qt 6.12:* where Qt Multimedia reads a file's metadata, cover art is `QMediaMetaData::CoverArtImage`;
`ThumbnailImage` is deprecated in 6.12 and is not used.

- [ ] Art precedence: the operator's order in §15 (embedded, `artist.*`, `album.*`, `folder.*`, other images in the folder, opt-in fetch); explicit user override outranks auto discovery.Original assets untouched. Cache bounded variants (row, album tile, mosaic, detail) keyed by stable source identity/version. Verify dimension/file/decoder caps and error handling; never permit remote art to be a mandatory paint dependency.
- [ ] Local tags: title, artist, album artist, album, track/disc numbers, year/date, genre, comments, composer, artwork and technical properties when format supports. Use a tested parser library candidate such as Mutagen only after source/build reachability is demonstrated. All reads off GUI/render.
- [ ] **Tag writes are explicit user transactions** with before/after validation, format capability matrix, backup/recovery and tested interruption behaviour, unknown-tag preservation, bulk-edit field review, read-only/missing/corrupt-file errors, and DB rescan after successful write. Never rewrite audio on scanning, changing a group or selecting artwork.
- [ ] Optional online metadata/art: user opt-in, MusicBrainz verified identity matching and Cover Art Archive art, at most one MusicBrainz API call per second with identifying User-Agent, finite retries/cache and source provenance. Present match confidence/alternatives and require confirmation before writing tags or replacing authoritative local art. Offline mode must work fully.
- [ ] Portable personal groups are DB-first. Optional explicit export/import via safe namespaced custom format tags/sidecar where supported; never reinterpret standard `GENRE`/`COMMENT`/`GROUPING` by default, and never rewrite thousands of files upon group rename. A comments fallback requires deliberate warning/choice.
- [ ] Optional duplicate discovery distinguishes identical bytes, probable recording matches/different encodes and similar names; background hashes/fingerprints bounded, no automatic delete, never conflate live/remaster versions. User can retain, ignore or explicitly remove after confirmation.
- [ ] Optional local embedded unsynchronised lyrics and `.lrc` sidecars can be added after core library acceptance. Online lyrics require legal/provider validation, and remain non-blocking. **No podcasts.**
- [ ] **Library track menu (full-player mock R9):** a row's three-dot menu is the library track menu: Properties,
  Metadata Edit, Quick Tagging, Delete and Add To Group. Each entry is a front for the explicit transactions already
  described here and in §5.1 (tag writes as user transactions with backup, delete only after confirmation and
  path revalidation, group membership under the three-membership limit); the menu adds no new write path. Quick
  Tagging is a short tagging flow over the same metadata transaction, not a second tag writer.
- [ ] **Track Information alignment is swappable (full-player mock R11):** the Track Information panel (large
  artwork, title, artist, album and the format line) can swap its alignment, header included, in the way Now Playing
  does (side flip with one text group, Current_Plan 1C.3); artwork comes from the §15 resolver and the format line
  from the technical properties read above.

### 5.3 Storage safety and partial failure

- [ ] Deterministic schema version upgrades, backups before changes, restore testing and explicit library export; concurrent readers/writers protected by SQLite transactions/WAL/locks. Lock contentions never block GUI or audio.
- [ ] Bounded artwork cache with LRU/byte ceiling, invalid-source negative caching, permission/source change invalidation, cancellation at scan retirement and no age-based deletion of user-authored group data.
- [ ] Protected paths: a library folder is not an instruction to rewrite or delete audio files. Tag writes and deletes require explicit action and source-path revalidation immediately before commit.
- [ ] Indexed but missing tracks show unavailable status, remain in playlists and keep favorites/groups until an explicit cleanup. A rescan never silently replaces the identity with a different recording of the same name.

## 6. Windows playback media session: outbound vs inbound

- [ ] SMP's Windows **SMTC publisher** is an output adapter to player service, independent of existing **GSMTC reader**. Explore `ISystemMediaTransportControlsInterop::GetForWindow` on the real MC/desktop HWND; test actual Python/WinRT availability and frozen dependencies before promising compatibility.
- [ ] Publish track/artist/album/artwork, playing/paused/stopped, position, duration, capabilities; receive Windows play/pause/skip/seek into the **single** service command owner. Generation-fence every callback, unsubscribe at shutdown.
- [ ] Mark the player's published AUMID/session as owned; exclude it from *external* source discovery while keeping internal `smp` Media adapter functional. No self-reading feedback or global blanket browser exclusion.
- [ ] Playback never depends on an SMTC consumer: if OS integration fails, local player/queue/visualizer keep working and report that optional integration unavailable.
- [ ] Test Media keys while selected external player remains active; no doubled global keys, no program hijacking another provider's session, no duplicate notification/OSD.

## 7. MC Expanded Media: **complete before SMP profile separation**

This is a **new hard milestone** added by the operator. It reuses Plan 01's display-local takeover, background admission, widget lease and OSD contracts, but renders media-first content rather than a display-wide EB simulation. It is **not the SMP desktop host** and does **not require the later visualizer Pop Out**.

### 7.1 UI modes and glyph semantics

- [ ] Mini/ordinary Media card gains **↗** diagonal-outward glyph. Expanded media view replaces it with **↙** inward-collapse glyph. Draw vectors in the existing semantic style, not Unicode glyphs with inconsistent baselines; separate hitbox, hover fade, tooltip and keyboard accessibility. Visualizer's future desktop **Pop Out** is **square + diagonal arrow** and represents a *different* action/window boundary.
- [ ] **Swapping arrow in the SMP title bar (full-player mock R1):** the full-player window's title bar carries the
  same swapping-arrow family: a down-left diagonal arrow that enters the Mini / Normal Media presentation (the compact
  player of §8.2), the reverse of the expand arrows. It is drawn in the same vector glyph family as the Visualizer
  card's fullscreen arrows and this section's glyphs (Current_Plan 1B.12, plan 01 M3c), not a separate icon set.
- [ ] A screen-wide adaptive Media experience uses existing Media track/artwork/transport/seek/volume/state truth, including correct source attribution. It **reflows** artwork, title, controls, playback details and optional canonical visualizer area instead of naïvely scaling the entire 420-ish mini card. Keep theme palette and round-trip to exact saved mini geometry.
- [ ] If Visualizers is not enabled, expanded Media still works as a media interface. If it is enabled, optional existing visualizer presentation may occupy a defined area, but it is still the **one** visualizer owner/render pipeline, not an independently running second visualizer. No product requirement to force Visualizers capability ON.
- [ ] Media and EB takeover on one display are mutually exclusive **presentation states**. Use one authoritative display takeover policy, not two flags that can both control background/widget admission; switching expansion types is an ordered exit/enter transaction with predictable persistence and safe restoration.
- [ ] Distinguish selected Media provider from the audio service. Expanded Media may show external Spotify while SMP continues playing invisibly; no implicit switch, queue reset or ownership transfer. The currently active source is labelled.
- [ ] Show OSD and genuine system-volume changes in existing lane; avoid overlay collisions with play/seek and album art; no extra volume poll. Existing Media double-click refresh semantics survive in mini and get a deliberately specified expanded action (not an accidental mode switch).

### 7.2 Technical and lifecycle gates

- [ ] Use the first plan's per-display wallpaper/transition admission receipt and widget fade/dormancy. Another display keeps unaffected transitions and widget services; one expanded Media doesn't globally deactivate visualizers or other providers.
- [ ] Preserve existing Media model/commands/service; switching mini↔expanded is retained presentation policy, not a new GSMTC controller or media query lane.
- [ ] Persist expanded-media intent in the canonical MC settings, **not inside a media provider selection or visualizer mode preset**; restore only on eligible startup/Settings/monitor readiness. Ordinary Media widget geometry remains untouched.
- [ ] Handle Edit Save/Cancel, media source changes, two-display swap/target hotplug, repeated Settings open/close, no-source/error state, actual mixed DPI/screen sizes, input menu overlays and terminal retirement.
- [ ] Run **cross-feature** tests: EB expanded -> Media expanded, Media expanded -> EB expanded, either -> ordinary; no double hidden-widget scope or missing service leases, preserved single visualizer owner and image-batch accounting.
- [ ] Compare GPU/CPU/GUI frame-age with mini and collapsed baseline; no second renderer, no hidden full-size card still painting behind. Use native Quick QML tests and real two-display review at the final acceptance gate.
- [ ] **Gate:** MC Expanded Media is accepted as independently useful, reversible and consistent with current themes/hit-testing. Only then begin third-profile separation.

## 8. Standalone SMP product: native host, not a renamed screensaver

### 8.1 Profile + settings/storage + packaging

- [ ] Introduce explicit SMP profile resolver/identity through existing side-effect-free startup policy. Update `core/settings/storage_paths.py` canonical data-root set, `core/settings/json_store.py::determine_storage_path` explicit settings directory mapping, **and** `core/settings/defaults.py::_resolve_profile` / `get_default_settings` plus canonical raw defaults/override lookup. Otherwise SMP silently receives Normal defaults or isolated test-profile storage.
- [ ] Settings profile, runtime host and frozen build flavour are three independent axes. New entrypoint calls shared core initialisation/service registration but **never** starts/screensaver engine just to paint a music library. No `--dev` env special case, no separate defaults file hardcoded by UI, no duplicate SettingsManager.
- [ ] Shared non-settings data root contains DB/artwork/theme/preset stores intentionally common to MC/SMP, with atomic multi-process writes; separate SMP settings directory holds player-window position, pane arrangement, source preference, output device, display target, playlist selection and app theme/layout choices as decided. Keep Standard and MC existing paths and defaults untouched.
- [ ] Profile-aware defaults/repair/reset/export/import are explicit; test unseen/inactive settings retain values through other profiles. Isolated `StorageRoot` tests cannot open real user DB or credentials.
- [ ] SMP runtime imports no image-saver source workers, wallpaper transitions, screen capture, monitor stagger, screensaver screens or subreddit/mail/Steam families merely for shared registry/Settings UI. Package reachability audits confirm excluded code only where truly absent; keep mandatory Qt Multimedia/QtOpenGL/Qt Quick substrate.
- [ ] Build Foundry/Runner/installer definitions are updated **only after** runtime tests pass. Operator alone runs Nuitka/Inno builds and supplies physical evidence; code editing agents must not invoke product builds.

### 8.2 Real desktop UI and pane geometry

- [ ] Normal Windows focusable, taskbar-capable, snappable, resizable/minimizable/maximizable desktop top-level host; choose an ordinary native `QQuickWindow`-based presentation boundary and audit platform/window flags. Not the existing screensaver's topmost multi-display compositor.
- [ ] Visual reference: recovered MusicBee-like charcoal/slate design with restrained accent, but **live canonical visualizer replaces the LEFT Artist Pictures pane**, artwork and details remain in lower-right Track Information, central music library and right queue/playlist; persistent transport, seek/volume. Remove Podcasts navigation.
- [ ] The two MC music-workspace pane identities become independent dock/split areas, still under **one logical Library & Playlists feature**. Desktop user manipulates normal resizable splitter/docking controls, not global SRPSS CUSTOM Edit, while preserving shared pane models/theme colours and profile-local placement.
- [ ] All pane arrangements are bounded and DPI-aware; restore by semantic slots and normalized geometric intent rather than only last pixel rectangle. Handle 125/150/200% DPR, maximized/compact modes, missing monitor and small window; clip safely instead of placing a child offscreen.
- [ ] **Compact player** is a normal desktop window using the existing Media widget semantic model/style; **Full desktop** is Library/Playlist/Visualizer composition; **Immersive** uses the admitted expanded visualizer/media concepts within SMP's own host. Compact↔full↔immersive must not reset audio, queue, SMTC or visualizer logical clock.
- [ ] Theme and preset controls reuse canonical sources, and Settings is reorganized by the later presentation descriptor without hiding important visualizer detail. No second renderer or separate mode preset implementation.
- [ ] **SMP Edit mode (full-player mock R3; operator's clarification of 11 Nov 2026, evening; contract route in
  `04_Full_Player_Mock_2026-11-11.md` sections 7 and 8, which settle the two statements that stood side by side
  here):** the mock's grid glyph enters SMP Edit, in which every section of Full mode except the title bar can be
  moved, resized (X, Y and XY) and swapped. SMP Edit is its own owner over its own record (the section tree of §16A),
  beside the existing Edit modes and never inside them: it is not the global SRPSS CUSTOM Edit (so the bullet above
  stands), and it is built from the same handles, guides, snapping, lock glyph and commit / cancel transaction (so
  the mock's "existing Edit handlers" stands too). Existing Edit modes must not break: in the screensaver and MC
  builds, which carry the compositor and full SMP functionality together, the two live side by side, one edit
  session per window, neither record touched by the other's session.
- [ ] **Small mode and Full mode (operator, 11 Nov 2026):** Small mode is the Media widget as it is now; on the
  SMP profile build it sits on the live desktop, with proper snapping, its outer geometry adjustable at all times
  and its children adjustable behind the lock glyph (the "Compact player" above). Its Up arrow switches to Full
  mode, the mock's layout (the "Full desktop" above). Full mode defaults to full screen but can be adjusted like a
  normal window, and its sections scale their spacing and sizing with it: §16A's section tree is the layout at
  every window size, not only in full screen. On the screensaver and MC builds neither mode needs to leave the
  compositor: Small mode is the Media widget where it is today and Full mode is a display-wide presentation on one
  display, as the fullscreen Visualizer is (document 04 sections 8.2, 8.3 and 8.7: one implementation, two hosts).
- [ ] **Arrange's SMP section (operator, 11 Nov 2026):** Arrange gains a section for SMP in which the Full mode
  section tree is rearranged with Arrange's precision; it is the main section of Arrange on the SMP profile build.
  It edits the same record through the same owner as SMP Edit, under the Edit / Arrange parity rule (document 04
  section 8.6); Arrange's existing sections are unchanged.
- [ ] **Three builds from profiles (operator, 11 Nov 2026):** the screensaver build, the MC build and the SMP build
  come from profiles as the first two do today. The screensaver and MC builds have full SMP functionality together
  with the compositor; only the SMP profile build has no compositor (no transitions, no image presenter, no widgets
  that are not the Visualizer or media related), as §8.1 already requires of its runtime imports.
- [ ] **Left pane edges (full-player mock R4):** the left pane's edges are adjustable in X, Y and XY (a corner moves
  both), within the per-content minimums of §16A.
- [ ] **Backgrounds and colours (full-player mock R15, R16):** every pane and bar background inherits the surface
  material and the theme colours (the widget material system, `Docs/Architecture/Card_Surface_Materials.md`), and
  every colour is a semantic theme colour. The mock's Miami Afterdark navy and pink is one example under one theme,
  not a palette to hard-code; the restrained charcoal and slate in the visual-reference bullet above is likewise only
  the concept image's example.

### 8.3 Visualizer Pop Out: SMP-only product feature

- [ ] **The left pane shows Visualizer, Lyrics or Artist Collage (full-player mock R5, R6, long-range):** the left
  pane of the full player presents one of the three. As Visualizer it is the real Visualizer card with its real glyph
  row (glyph parity, including the Pop Out glyph below), not a second renderer; Lyrics and Artist Collage are further
  presentations of the same pane. Lyrics stay bound by §5.2's local-first, later-milestone rule, and whether Lyrics and
  Artist Collage belong to the first full-player milestone is an open operator question
  (`04_Full_Player_Mock_2026-11-11.md` section 6).
- [ ] The glyph is a **square outline containing outward diagonal arrow** (not the ↗ Expand glyph), with tooltip `POP OUT VISUALIZER`. It moves the *one* visualizer into a separate **always-on-top** desktop window. MC does not need it for product acceptance; a focused MC test shell is allowed only if it proves a difficult window-transfer contract and is not shipped as a new feature.
- [ ] Exactly one live logical controller/DSP source and one currently active GL visualizer renderer. Desktop dock and popout are **mutually exclusive rendering hosts**. Rehosting between separate `QQuickWindow` GL contexts can require releasing/recreating *context-local GPU resources*; don't assume reparenting a QSGRenderNode or QQuickItem across contexts is free/safe. Fence old root destruction, then construct/attach destination with current immutable presentation/source state. No double active renderer interval.
- [ ] Preserve selected mode, preset, camera semantic view, wallpaper/scene environment policy where applicable, activation epoch/source freshness and authored state; renderer-only context objects may rebuild without restarting playback or analysis.
- [ ] Pop-out always-on-top is user-toggleable and must behave sanely when an unrelated game enters fullscreen, when Alt+Tab/taskbar focus changes and when target monitor is unplugged. Closing should re-dock to exactly the saved slot or safe fallback if parent layout was removed.
- [ ] Pop-out and immersive expansion are distinct. User can pop out from full library or collapse/re-dock; transition to/from immersive has one selected host at each instant. No second media HUD/SMTC/OSD instance.

### 8.4 SMP-only toasts

- [ ] Track/playback notifications from player events, not media polling. Only SMP desktop product admits them; SRPSS/MC inherit no new toast window.
- [ ] For exact *active display* placement, use one bounded monitor-aware non-activating application overlay with native Windows work-area/foreground resolution. OS toasts are not guaranteed display-selectable. Fallback/quiet-mode if foreground monitor unavailable. No permanent overlays over games, no focus theft, no more than one bounded toast generation.
- [ ] Theme/media semantics, event-driven show/hide, deduped events, click-through when hidden; suppress duplicate Windows SMTC notifications or immersive HUD when applicable.

## 9. Player-oriented Settings: preserve SRPSS dormancy, add safe live policy

**Do not rewrite SRPSS's `on_settings_requested` to keep windows alive.** MC can continue to use full stop/replacement while player service survives above display generations; native SMP may introduce a separate Settings window over its live player host.

- [ ] One `SettingsManager`/canonical schemas/preset and theme authorities. Three axes: application profile eligibility, Settings navigation/presentation descriptor, setting-specific live/recreate/defer policy. UI cannot declare a low-level unsafe change live.
- [ ] SMP Settings priority: Playback/Audio, Library/Playlists, Visualizers (same detailed mode builders), Appearance/themes, windows/immersive and integrations, Advanced. Screensaver/MC current tab order remains unchanged unless operator chooses otherwise.
- [ ] Lazy Settings body admission: disabled/inactive family tab does not import backend, create QObject or mutate settings by merely opening dialog. Use current lazy body invalidation/`shiboken6.isValid` contract on retirement.
- [ ] **Reversible live:** style, color, supported arrangement and volume; explicit source resolver and current model. **Controlled service transaction:** output device, active queue operations and folder indexing; commit/discard handling includes irreversible external side effects. **Deferred:** renderer backend/major Qt host rebuild requiring exact resource shutdown. **App restart:** packaging-level change only with clear notice.
- [ ] Do not confuse `SettingsUndo` 30-gesture memory list with a durable Save/Cancel transaction. Define a scoped preview buffer, original committed values, preview side-effects, Commit, Cancel and rollback for the specific controllable settings. Native file edits / external network calls / library scan cannot claim magical rollback of side effects.
- [ ] Opening/closing Settings with playback active must preserve decoder, audio device, queue, visualizer source and SMTC session unless user changed that exact resource. Qt presentation/GUI window is independent; late callbacks from closed Settings widgets must fail closed.
- [ ] Test combined cross-profile resets, SST imports, themed live settings and background hydration, no hidden-tab write or Visualizer Custom surprise modification.

## 10. Strict milestone ladder and completion criteria

**M0 | Admission audit, tests and stable baseline (no feature source yet)**

- [ ] Previous Waveform + Expanded Visualizer acceptance recorded. `Current_Plan.md` updated **only by operator authorisation**; source SHA and changed contracts inventoried.
- [ ] Diagram widget registry/member admission, Settings UI row/Custom geometry/slot and generation lifetime. Write representative two-pane fake-family integration tests first; confirm no hidden second capability.
- [ ] Design DB isolation/backup/identity/concurrency and player lifetime above MC display barrier. Baseline Standard+MC idle import/service/thread/widget counts and existing external Media/Visualizer replay.
- [ ] **Gate M0:** no undocumented changes to shared physical/lifecycle contract. Implementation sequence locked below.

**M1 | MusicWorkspace capability + independent Library/Playlist panes [FIRST FEATURE]**

- [ ] One `Library & Playlists` Settings entry, two independently routed/resized/movable QML panes; master capability and ordinary on/off, pane visibility, proper CUSTOM and MC profile persistence.
- [ ] No decoder/output/player backend yet. Empty-state pane UI and same-generation icon/theme/hitbox/native Quick geometry tests. No import startup of music backend from family registry alone.
- [ ] **Gate M1:** two distinct rectangles can be moved onto different monitors and restored; only one Settings row/family and one neutral library ownership authority. Other widgets/visualizer unchanged.

**M2 | Offline indexed Library + editable saved Playlists [FIRST USEFUL BEHAVIOUR]**

- [ ] Shared-root SQLite DB with isolated test root, transactional migrations/backups and safe scanner. Indexed list, search, sort, track status, playlist create/rename/reorder/add/remove; no playback dependency.
- [ ] Background bounded/cancellable scanning + immutable revisions; correct missing/renamed/unavailable track identity, dual-process lock tests, safe GUI virtualization.
- [ ] **Gate M2:** sizable real folder can be indexed and playlist edited with GUI responsive, and every action survives restart/Settings opening. No track file altered.

**M3 | Independent PlaybackService + Queue + decoded-PCM Visualizer adapter**

- [ ] `QMediaPlayer` trial, output service, ordered queue, seek/device/repeat/shuffle, latest-source freshness and one-player-owner shutdown. Library/playlist pane actions can now play/queue.
- [ ] Player continues through pane close, MC Settings full display teardown/recreation, EB mode switching and source/monitor routing. External WASAPI unaffected.
- [ ] **Gate M3:** real local codecs/seek and source timing measured; no double DSP, playback restart, orphan worker/device or stale callback.

**M4 | Full Library UX / metadata / art / favorites / three-group contract**

- [ ] All/Artists/Genres/Favorites/Groups, list and artwork grid; cached deterministic collages; manual tag edits; local covers; optional online lookup; portable group export; optional duplicate view.
- [ ] Three memberships enforced under concurrent DB writes, favorites preserved across safe rescans, playlist distinction, bounded art/scan/GUI performance, file backups/undo limitations explained.
- [ ] **Gate M4:** functional test corpus for MP3/FLAC/Ogg/Opus/MP4 metadata without damage; valid group and edit durability; large list/thumbnail benchmarks pass.

**M5 | Internal SMP Media adapter and outbound Windows SMTC**

- [ ] Add explicit in-process `smp` Media provider, external providers remain available, source selector chooses one analysis owner. Outbound SMTC on real HWND; own session filtered from external GSMTC reading.
- [ ] **Gate M5:** SMP plays while Media displays Spotify, library commands target SMP, Windows key handler has exactly one recipient, no feedback loops/stale sessions.

**M6 | Expanded Media in MC [MANDATORY PRE-PROFILE]**

- [ ] ↗/↙ glyph, responsive full-display media layout, artwork/controls/source truth, optional canonical visualizer, takeover transitions/widgets/OSD/HUD policy reused from accepted EB expansion.
- [ ] Mutual exclusion between visualizer expansion and media expansion, preserved saved mini layout, other-display operation and Settings/monitor/EDIT lifecycle.
- [ ] **Gate M6:** real installed MC two-display visual acceptance + native/focused tests; no second player or controller. **Do not create SMP profile until M6 accepted.**

**M7 | Explicit SMP settings profile and native desktop host**

- [ ] Update all canonical profile/default/storage selectors and build/startup identity, preserving existing Standard+MC. Construct native desktop `QQuickWindow`, independent Library+Playlist panes, left live visualizer, lower-right artwork and compact/full/immersive.
- [ ] Add SMP-only Pop Out as an independent **optional post-host** subgate; if renderer rehost cannot be proven, leave Pop Out disabled rather than fork renderer. Add safe active-display toasts only after host lifetime proven.
- [ ] **Gate M7:** snaps, taskbar, focus, Alt+Tab, mixed DPI/hotplug, same audio/visualizer state across desktop modes; no SRPSS wallpaper engine constructed and no extra rendered visualizer.

**M8 | Settings lifecycle adaptation and full cross-product regression**

- [ ] Presentation-descriptor Settings priorities and reversible live changes; service/device reconfigure and renderer deferred rebuild; full SRPSS/MC barriers untouched.
- [ ] **Gate M8:** repeated Settings/desktop mode/Pop Out/SMTC/window close cycles preserve media state and bounded Qt/COM/DB/GL resources; no hidden writes.

**M9 | Release/product acceptance**

- [ ] Standard and MC source tests, SMP native tests, 4-run cold/warm/Settings/stop soaks, library migrations/backups, real hardware codecs, GPU load and idle footprint; test isolated and shared MC/SMP concurrent DB.
- [ ] Source-proven build payload reachability report and explicit dependency pins. Operator alone runs frozen SMP/MC/Standard builds and Inno installers; review actual Nuitka reports for added Qt/FFmpeg/metadata payload.
- [ ] Update `Spec.md`, focused Docs/Reference and Docs/Contracts for actually accepted new owners, plus `Docs/TestSuite.md` and user-facing README. Do not keep stale parallel proposal assertions as destination authority.
- [ ] **Gate M9:** usable standalone player, no screensaver/MC contracts weakened, no two visualizer implementations, zero unverified performance/codec claims.

## 11. Automated test/verification matrix (names below are PLANNED)

New tests must assert behaviour, native retained paint and actual DB/lifetime transactions, not source text, default values or a mutable user preset snapshot. Build fixtures must use temporary `StorageRoot`, fake/offline music files where feasible, and native Windows integration for platform-only contract proof. Each milestone runs its *smallest useful subset* before the chunked suite; no huge suite after every code change.

| Proposed test/harness | Required assertions | Gate |
| --- | --- | --- |
| `test_music_workspace_family.py` | Exactly one family/one Settings entry/two pane descriptors, independent visible/size/route, disabled import dormant | M1 |
| `test_music_workspace_qml_native.py` | Two independent Quick rectangles and hit/Edit mapping, mixed DPR, drag/resize/slot/undo, hidden restoration, no binding warnings | M1 |
| `test_music_workspace_storage.py` | DB outside JSON settings, isolated root, migration/restore, WAL concurrent writes/readers, no GUI I/O | M2 |
| `test_music_library_scanner.py` | Bounded scan, duplicate roots/symlink/permissions, cancellation/generation, missing/rename identity, no song writes | M2 |
| `test_music_playlists.py` | Create/rename/reorder/delete, stable IDs and ordering, queue vs playlist independent, missing entries and restart | M2/M3 |
| `test_music_playback_service.py` | App ownership, exactly one service, play/pause/seek/device/shutdown, lifecycle and event revisions | M3 |
| `test_music_pcm_visualizer_source.py` | Single source/PCM timestamp/epoch, source switch, no double loopback, latest-state and inherited reactivity numerical parity | M3 |
| `tools/music_backend_native_smoke.py` | Supported Windows codec matrix, seeks/duration/output device, visual latency, audible continuity across UI destruction | M3 |
| `test_music_groups_and_favorites.py` | Track identity, three-group maximum incl simultaneous fourth, rename, bulk edit, favorite preservation | M4 |
| `test_music_artwork_cache.py` | Precedence, decode/cancel/caps/invalid art, thumbnails/mosaics, source rev replacement and bounded disk use | M4 |
| `test_music_metadata_edit.py` | Write opt-in only, backup/round-trip/unknown-tag preservation, safe failure, portable group explicit import/export | M4 |
| `test_music_online_lookup.py` | User opt-in, safe matching/confidence, MusicBrainz rate/UA, network cancellation and offline fallback | M4 |
| `test_music_provider_arbitration.py` | Internal vs GSMTC, current selection independent of audio service, no self-loop, ext source/volume correctness | M5 |
| `tools/music_smtc_windows_smoke.py` | Real HWND/SMTC publication/media keys/metadata/timeline, exactly one handler, proper unsubscribe | M5 |
| `test_mc_expanded_media_policy.py` | ↗/↙ semantics, screen reflow, `EB expanded` mutual exclusion, takeover account/lease/OSD & restore | M6 |
| `test_mc_expanded_media_qml_native.py` | Source labels, control hitboxes/OSD priority, large/portrait/DPR geometry, no stale QML | M6 |
| `test_smp_profile_defaults.py` | Explicit third-profile default/settings/data-root + test isolation, reset/import/export, no Normal/MC corruption | M7 |
| `test_smp_desktop_hosts.py` | Compact/full/immersive focus/snapping geometry model, separate panes, no screensaver engine; one GL visualizer host | M7 |
| `test_smp_popout_transfer.py` | Separate QQuickWindow lifetime, context-local resource recreation, never two current renderers, clean re-dock/Alt+Tab/hotplug | M7 optional |
| `test_smp_live_settings.py` | Preview/Cancel/Apply side-effects, no hidden tab instantiation, continued music, resource fence, scoped rollback | M8 |
| `test_smp_cross_product_dormancy.py` | Fresh Standard/MC import startup: zero SMP backend/DB/audio SMTC work; repeated generations/resources bounded | Every milestone |
| `tools/visualizer_live_check.py` + accepted replay/BTF | Active-gaming/source/render frame freshness and gold reactivity with SMP PCM and external WASAPI | M3/M6/M9 |

**Operator-only physical items, minimized:** a small number of *irreducible* Windows outcomes: visually approving real expanded Media and SMP desktop/Pop Out layout; verifying actual sound/seek across devices and codecs when an automated hardware probe is not sufficient; checking Windows snapping, native SMTC keys and foreground toast behaviour. Most geometry, integrity, background work, provider arbitration and restart/save/restore must already be automated. Operator only runs frozen product/installer builds upon explicit choice. Document measured failures instead of asking for repeated exploratory manual tests.

**Automation constraints:** local `.venv` only; one-line PowerShell with semicolons, no environment variable toggles; no GitHub Actions; execute focused tests that exist, then chunked suite at gates. Example after a planned test *exists*: `.\.venv\Scripts\python.exe -m pytest tests/test_music_workspace_family.py -q`. Don't claim success for unimplemented tests or unavailable native devices.

## 12. Change-acceptance discipline and deferred risks

### Required implementation handoff after each milestone

1. Full-file source change inventory with exact SSOT/schema/descriptor owners changed and rationale; no patches as delivery.
2. Repo commit/reference and focused tests **actually executed** with precise pass/fail; failed tests stay failed, do not mark `[x]` by inference.
3. Ownership account: per-profile services/imports, per-display panes/QML roots, controller/DSP/audio lanes, pending tasks, audio output, Windows listeners, DB connections and GPU resources, before/after acceptance.
4. Persistence account: which keys changed, which never change (other profile/visualizer presets/layout), write transaction vs live presentation, migration and rollback.
5. Quantitative performance: GUI frame delivery, audio underruns, latency/source age, widget dormant costs, background scanning, QML retained item counts, DB scan throughput, cache bytes, present/absent GPU load.
6. Open issues classified **blocking** vs **optional later**. Native operator test list only where physical evidence cannot be automatically supplied.

### Decisions that must stay evidence-gated

- **Audio backend choice:** Qt Multimedia is a trial; if it cannot deliver accepted precision/format/device behaviour, change only the private backend behind service interface after a proven failure. Do not create a new per-mode DSP engine.
- **Library identity:** decide rename/move fingerprint reconciliation on real file fixtures before migration. Don't guess from filename alone.
- **Wallpaper suspension:** if Plan 01 accepted only a narrower no-effect background contract, MC Expanded Media inherits that exact accepted behaviour. It cannot promise stronger suspension without an additional E0/E1 proof.
- **Database sharing:** isolated test roots and one multi-process write policy required before MC and SMP concurrent access. Shared root != uncontrolled shared mutable service object.
- **Expanded Media layouts:** should be responsive scene layout using existing Media data; naive uniform scale is explicitly insufficient for a large readable transport UI.
- **Pop Out:** context-bound visualizer resource migration is difficult and optional for initial SMP unless tested cleanly; it is **not** a reason to ship second active renderers.
- **Live Settings:** accept only operations with demonstrably reversible owner effects; keep other changes controlled/deferred. Existing SRPSS full-retire policy remains untouched.
- **Future Vulkan, temporal upscalers and frame generation:** separate shared rendering projects after evidence, not prerequisites or opportunities to weaken audio reactivity. No GL->Vulkan backend split inside SMP-only modes.

### Explicit non-goals

No podcasts, no auto-lyrics scraping, no mandatory online artwork, no built-in account sync, no Spotify/music streaming decoder, no global audio player autostart in Standard SRPSS, no duplicate visualizer implementation, no forced media-provider takeover when SMP plays, no general-purpose compositor rewrite, no provider-specific UI fork, no speculative universal codec support.

## 13. Audio quality: on par with or beyond MusicBee (operator box item, live target)

Operator: "aim for quality, compatible and adjustable audio as on par or beyond with apps like Music Bee as possible.
Do not shy away from custom work when it will improve quality/performance/ux." The bar is measured, not promised.
Qt Multimedia remains the first trial (§4.1); each criterion below is a gate the backend passes or the private
backend behind `PlaybackService` is replaced with custom work (FFmpeg decode through the pinned Qt build or a
dedicated decoder, plus our own WASAPI output; `utils/audio_capture.py` already owns the WASAPI capture side and its
device/format negotiation is the model). No second DSP engine for the Visualizer; the analysis source stays the one
decoded-PCM adapter.

- [ ] **Output modes:** WASAPI shared and **exclusive** (bit-perfect, event-driven), selectable output device with
  hot-unplug recovery, sample rate follows the source in exclusive mode (44.1 / 48 / 88.2 / 96 / 176.4 / 192 kHz)
  and the device's mix format in shared mode; 16/24/32-bit and float; a measured latency readout per device.
  **Evidence:** a loopback null test (digital capture of the output against the decoded file) is bit-identical in
  exclusive mode with DSP off.
- [ ] **Gapless playback** across tracks of the same stream format (0 ms gap, measured on a recorded loopback of a
  known gapless album), with LAME/iTunes encoder delay and padding honoured for MP3/AAC; **crossfade** (0-12 s,
  equal-power, optional auto-only-between-albums) as an alternative; pre-buffered next track.
- [ ] **Formats measured, not promised:** FLAC, MP3, AAC/M4A/ALAC, Ogg Vorbis, Opus, WAV/AIFF, WavPack, APE
  (optional), DSD (optional, PCM conversion). Each format's load, seek accuracy (≤ 1 frame), duration, sample rate,
  bit depth and gapless behaviour recorded in a matrix from legally available fixtures; unverified ones are shown as
  unsupported in the UI.
- [ ] **DSP chain, in this order, each bypassable and bit-transparent at neutral:** ReplayGain (track/album, pre-amp,
  clip prevention; tags read, never written on play), a parametric / 10- or 31-band graphic EQ with presets, a
  user-ordered insert slot, volume with a dither stage at the output bit depth, optional high-quality resampler
  (SoXR-class, VHQ) only when the device cannot follow the source. **Evidence:** at neutral settings the output is
  bit-identical to the decoder output; each stage's cost is ≤ 2% of a core at 192 kHz.
- [ ] **Upmixing and downmixing (operator, 11 Nov 2026: "everything from upmixing, downmixing to replay gain,
  device select and so on, audio crossfade too"):** explicit channel-layout handling as a stage of the DSP chain:
  stereo to multichannel and multichannel to stereo with stated coefficients, selectable per output device, and
  bit-transparent when the source and device layouts match. The equalizer above is a first-class feature with
  presets and per-device memory, not only a stage in a list.
- [ ] **Transport quality:** sample-accurate seek with a short fade to avoid clicks, play/pause fades (configurable
  0-500 ms), stop fades, no pops on device switch, resume-at-position after restart, A-B repeat optional.
- [ ] **Adjustability exposed in the SMP Settings tab (§14) Playback and Audio pills:** output device and mode,
  exclusive on/off, buffer size, sample-rate policy, bit depth, dither, resampler quality, ReplayGain mode, EQ, fades
  and crossfade, with tooltips carrying the explanations; every value a canonical default.
- [ ] **Beyond MusicBee where cheap:** per-device remembered settings; an audio-path readout ("FLAC 96 kHz 24-bit ->
  exclusive 96 kHz 24-bit, bit-perfect") in the Media card and the SMP transport; loudness-aware crossfade; a
  visualizer analysis tap after the DSP chain so the picture reacts to what is heard.
- [ ] **Gate:** M3 cannot close without the null test, the gapless measurement and the codec matrix; M9 cannot close
  without the 30-minute underrun soak at every mode.

## 14. The SMP Settings tab with pills (operator box item, live target)

Operator: "When SMP is available (Library Widget ON) a new SMP Tab should exist in settings allowing for well organised
adjustments to items related to SMP and audio processing. Use Pills and maintain high quality thematic UX. We should
already have in the plans for what to hide when running an SMP only build and how to do it."

- [ ] **Declaration:** one `SettingsTabDescriptor` (P1 / AC-01) with key `smp`, label `SMP`, a lazy builder,
  `pill_of(view_state)` returning the remembered pill, and
  `available(profile) = is_smp_enabled() and music_workspace family activated` (the "Library Widget ON" condition
  reads the family activation in `capability_activation`, not the pane's visibility). Position: after Widgets in
  MC; first in the SMP profile (§9 priority order). The tab is absent (not hidden) when unavailable, and the
  remembered tab index maps through keys, so its absence never shifts another tab.
- [ ] **Pills (one open editing path, Steam-style buckets inside each, closed by default, one open per level):**
  `Playback` (device, mode, buffers, fades, crossfade, resume), `Audio` (ReplayGain, EQ, dither, resampler, the
  audio-path readout), `Library` (roots, scan policy, identity/rescan rules, missing-file handling, duplicates),
  `Artwork` (precedence per §15, cache size, the opt-in fetch and the opt-in store-to-folder), `Integrations`
  (Media provider selection for SMP, outbound SMTC, media keys, toasts in the SMP profile only), `Advanced` (DB
  location/backup/restore/export, diagnostics). The pill persists through `project_settings_bucket_context` like the
  Widgets tab's `subtab_id`; the registry's single `pill_of` replaces any if/elif.
- [ ] **UX rules (existing patterns, `Docs/Architecture/Settings_Theme_Architecture.md`):** one-sentence intros and
  tooltips for the rest; Title Case controls, ALL CAPS short tags; the theme's material and connector rails; no
  hidden value-owner widgets (values in the section-lazy cache, AC-01); no backend, COM, SQLite or device touched by
  opening the tab (lazy body admission, §9); every control a canonical default and a Reset per bucket.
- [ ] **SMP-only build: what is hidden and how.** Hiding is declarative, by `available(profile)` on each descriptor
  and by family availability in the catalog, never `QWidget.hide()` or a build-time file prune:
  - tabs absent in the SMP profile: `Sources`, `Display` (saver display routing; the SMP host has its own window
    placement under `Playback`/`Advanced`), `Transitions`, `Layout` (Arrange, Layout Slots are saver layouts; SMP's
    arrangement lives in its host, §16), `Quick Start` (replaced by an SMP first-run inside `Library`);
  - tabs present: `SMP` (first), `Visualizers` (unchanged bodies and Studios), `Widgets` reduced by family
    availability to Media and the music workspace (Clocks/Weather/Reddit/Feeds/Gmail/Steam/System Stats/OSD families
    unavailable in the SMP profile; their settings keep their values, inert), `Scene3D`, `Accessibility`, `Themes`,
    `About`;
  - the Settings dialog in the SMP profile is the live-policy dialog of §9 over the running host, not the
    saver's full-teardown path;
  - **Regression bar:** AC-01's registry test with `profile=smp`: the hidden tabs are absent from the button row and
    the stack; the remembered tab survives; no saver module is imported by opening Settings in the SMP profile
    (import scan).
- [ ] **Gate:** built at M1 with the `Library` pill only (the first visible deliverable needs it), extended per
  milestone (`Playback`/`Audio` at M3, `Artwork` at M4, `Integrations` at M5); operator look at each extension.

## 15. SMP icon and artwork rules (operator box item, live target)

- [ ] **Icon:** `images/SMP.ico` is in the repo. It becomes `ShittyMusicPlayer.exe`'s icon in the build definition
  (M7; builds are the operator's locally or the lead's through GitHub workflows only) and the Media card's provider glyph when the selected source is `smp` (M5), in the
  existing glyph style and sizes, from the Qt resource pack like the other icons (regenerated by
  `tools/regen_qrc.py`; no runtime file read).
- [ ] **Artwork precedence (operator's order; replaces §5.2's first bullet):** 1. tagged / embedded cover in the
  file's metadata; 2. `artist.jpg|png` in the track's folder; 3. `album.jpg|png`; 4. `folder.jpg|png`; 5. any other
  image in the same folder (largest first, square preferred); 6. the fetching methods (§5.2, opt-in, MusicBrainz /
  Cover Art Archive with confirmation). An explicit user override outranks all. Case-insensitive names; `.jpeg`
  counts as `.jpg`. The resolver is one function in the media/artwork owner with a table-driven test.
- [ ] **Presentation:** the existing Media fade-in system is reused for artwork changes (identity-fenced, atomic
  publish, no stale art flash; plan 01 §G rules); row/tile/mosaic/detail variants come from the bounded cache (§5.3).
- [ ] **Store a fetched image in the artist's folder (operator: "consider"):** an **opt-in** setting in the
  `Artwork` pill, default off: when a library track has no artwork at any local level and the user's selected Media
  service is not SMP, a fetched and user-confirmed image is written as `artist.jpg` into that artist's folder, never
  overwriting an existing file, with a provenance sidecar (`artist.jpg.srpss.json`: source, date, match confidence)
  so it can be removed. Writes happen on the IO lane after path revalidation, respect read-only folders, and are
  logged. Nothing is written without the opt-in; nothing is written into the audio file.
- [ ] **Gate:** M4 for precedence and cache; M5 for the Media glyph; M7 for the exe icon.

## 16. Full visual rearrangement: every widget and panel, on par with our app and beyond MusicBee (operator)

The operator's bar: "full visual rearrange ability on par with our application/beyond music bee". MusicBee lets
the user show/hide, dock and resize its panels in a few fixed regions. SRPSS's CUSTOM lets the user move and resize
every widget anywhere on any display with saved slots. SMP gets both, with one layout model.

- [ ] **Inventory of movable things (each a named presentation identity with its own rect, visibility and slot
  membership):** `music_library` pane, `music_playlists` pane (with its queue view), the now-playing / track
  information panel, the artwork panel, the Visualizer (one owner, docked or popped out), the transport bar
  (play/seek/volume), the search/filter bar, the status/audio-path readout, toasts (placement only, SMP profile). The
  browse-mode sidebar (All / Artists / Genres / Favourites / Groups) is a region of the library pane, not a separate
  identity.
- [ ] **In MC:** the two workspace panes are ordinary CUSTOM widgets (M1): move, resize, per-display route, saved
  layout slots, Arrange, Edit-only keyboard controls, reset, exactly like every other family. Expanded Media (M6)
  collapses to the saved layout.
- [ ] **In the SMP host (M7):** one dock/split layout model with semantic slots (left/centre/right/bottom, nested
  splitters, tabbed stacks), drag-to-dock with a live preview, detach to a floating panel, hide/restore from a
  View menu, per-monitor placement, DPI-aware restore by semantic slot and normalised geometry (never last pixel
  rect alone), compact/full/immersive presets that are themselves saved layouts. Three user layout slots plus a
  default, like the saver's Layout Slots, with import/export.
- [ ] **Beyond MusicBee:** any panel can float on another monitor; the Visualizer can be docked into any slot or
  popped out always-on-top; panels remember a per-layout size and a per-monitor position; a layout can hide the
  transport and run from media keys; a layout switch never resets audio, queue, SMTC or the visualizer clock
  (§8.2); Edit-style keyboard nudging for floating panels; theme-aware chrome on every panel.
- [ ] **SMP Edit mode and the mock (full-player mock R3, R4, R11; settled 11 Nov 2026):** the operator left the
  contract route to the lead (`04_Full_Player_Mock_2026-11-11.md` section 8). Full mode's layout is §16A's section
  tree at every window size; SMP Edit is its own owner over that tree, built from the existing Edit modes' parts;
  §16A's four operations gain "move to an edge" (re-split at the top, bottom, left or right, which is how the
  controls go on top or at the side and the Visualizer becomes a thin wide strip along the bottom) and XY resize
  at a corner where two splits meet; each content declares its minimums, the orientations it supports and its fold
  priority in one registry, and presents itself from the rectangle it is given. The dock model in the "In the SMP
  host" box above (tabbed stacks, floating panels) is wider than the operator's description needs and stays
  unadmitted unless asked for; nothing floats in Full mode except the Visualizer's Pop Out (§8.3). The lead's
  remaining proposals for the mock are in document 04 section 4 and are not part of this plan until accepted.
- [ ] **One model, not two:** pane identities, visibility and rects are the same canonical values whether MC's
  CUSTOM or the SMP host edits them (profile-scoped geometry, shared identities); the dock model is a different
  editor over the same per-pane intent, not a second persistence authority.
- [ ] **Regression bar:** `test_smp_desktop_hosts.py` moves every identity in the inventory to every slot, floats
  and re-docks it, switches layouts and monitors, and asserts rects restore to the byte, no identity is lost, audio
  state is untouched and the one Visualizer renderer stays single; MC's parity harness covers the two panes.

### 16A. SMP fullscreen arrangement (operator, 7 Nov 2026; lead's design proposal)

Operator: "Freedom but no dead/empty sections and sections must connect, so smp would largely be choosing sections,
swapping them, resizing them and of course remembering all of this." Also: "SMP being in Fullscreen should be
remembered", and the Visualizer's own Expanded state is never decided by a preset or a mode switch (plan 01 §D3).

**Model: one tiling tree per fullscreen layout.**
- **Structure:** each layout is a guillotine split tree.
  - An internal node is a horizontal or vertical split with one normalised ratio.
  - A leaf is a section holding exactly one content identity from the §16 inventory: Library, Playlist/Queue, Track
    Information, Artwork, Visualizer, Transport (play/seek/volume), Search/Filter, Status/Audio path.
- **No holes or overlaps by construction:**
  - Leaves always tile the screen and share edges, so there are no gaps or overlaps.
  - Every leaf has content, so there are no empty sections.
  - Each content appears at most once; the Visualizer stays one owner.
- **Never pixel rects:** the layout is persisted as the small tree with ratios. It restores on any monitor, DPI or
  aspect ratio without reauthoring. Fullscreen has no floating panels; the §16 floating/detach behaviour belongs to
  the windowed host, and Pop Out (§8.3) is a separate window.

**The whole edit vocabulary (four operations; everything else is rejected):**
1. **Choose:** a section's picker sets its content. Choosing a content already shown elsewhere swaps the two, so no
   duplicates appear and nothing is lost.
2. **Swap:** drag one section onto another; the two contents exchange, with a live preview. Splits don't change.
3. **Resize:** drag a shared edge to change that one split's ratio.
   - Snap stops at 1/4, 1/3, 1/2, 2/3 and 3/4 of the split.
   - Snap to neighbouring parallel edges, so rows and columns line up across the screen; Shift drags freely.
   - Per-content minimums clamp the drag (e.g. Transport height, Library and Queue width, Artwork near its aspect);
     a split never yields a section below its minimum.
4. **Split / remove:** split a section to add a content (only contents not yet shown are offered). Removing a
   section gives its whole space to its sibling, so space never becomes dead.

**Fitting and alignment:**
- **Small screens:** when a screen is too small for the minimums, sections fold in a declared priority order
  (Status → Search → Artwork → Queue …; Transport and the current focus content last). They return when space allows.
  They never overlap or go off screen.
- **Styling:** one theme gutter between all sections, and every section uses the same card surface (Glass/Acrylic
  from the theme, the legibility layer the whole face up to the real border, never an inset panel: Card_Surface_Materials.md, M2 of 11 Nov 2026). This avoids today's mixed opaque and glass cards and
  partial inner panels.
- **Reflow:** each content reflows to its rect instead of scaling. Library switches between grid and list by width,
  Transport compresses to icons, Artwork fits its aspect, and the Visualizer fills its section through plan 01's
  viewport owner.

**Editing and persistence:**
- **Arrange:** SMP fullscreen gets its own Arrange: section outlines and labels, edge handles, drag-to-swap, and a
  per-section menu (change content, split horizontally/vertically, remove). Like MC Edit, it edits a draft; Save
  commits and Esc/Cancel restores the saved tree.
- **Built-in starts:** 3–4 layouts, e.g. Visualizer Stage (Visualizer large, Transport bottom, Queue right),
  Library, Now Playing (Artwork + Track Information + Visualizer), Minimal (Visualizer + Transport).
- **Slots:** three user slots plus the default, like the saver's Layout Slots, with import/export.
- **Persisted in the SMP profile:** whether SMP is fullscreen (restored at start), the active layout tree, and the
  slots. Per-aspect-class variants (16:9, 21:9, portrait) are optional later; normalised ratios cover most cases.

**Settings → Layout gets two pills: Widgets and SMP.**
- MC builds show both and auto-select the one that matters now: SMP when SMP is fullscreen or was last edited, else
  Widgets.
- SMP builds show only SMP's Arrange for its fullscreen elements.
- The pills follow the existing Settings bucket/pill patterns (one open at a time, short names).

**Regression bar (planned):** `test_smp_fullscreen_layout.py`.
- Random sequences of choose, swap, resize, split and remove never leave a hole, an overlap, an empty leaf or a
  duplicate content.
- Minimums hold.
- The tree round-trips to the byte through save and restore across resolutions and DPR.
- Folding at small sizes is deterministic and reversible.
- Swaps never restart audio, the queue or the visualizer clock.

**Final acceptance statement:**If MC offers two independently movable/resizable Library and Playlist panes under one widget entry, playback survives those views and Settings, Media/visualizer remain independently source-selectable, MC Expanded Media works before profile separation, and a later SMP native window reuses the shared library/player/visualizer state with intact dormancy and strict SRPSS contracts, the roadmap has achieved its goal without throwing away the existing architecture.

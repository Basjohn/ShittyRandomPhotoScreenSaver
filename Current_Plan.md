# SRPSS | Current Plan

This is the **live forward checklist**. It contains open work and acceptance debt only. Durable product truth belongs in
`Spec.md`, `Docs/Contracts.md`, Architecture/Guardrail/Guide/Reference documents, and useful failure history belongs in
`Docs/Historical_Bugs/`.

Work top-to-bottom unless the operator redirects a slice or a stated physical-evidence gate remains open.
Local checkouts make narrow validated checkpoints; archive handoffs return a superseding GODZIP under the handoff rules below.

---

## 0. Visual cohesion / Spectrum regression audit | CHECKPOINT 1 landed

The operator's physically-good comparison build is anchored at `f12137cf2f` (2026-10-06 00:42 UTC, about 02:42 local), before the current remedial/3D tranche. The forward diff to `8448717216` is 17 commits and contains **no direct edit to the Spectrum renderer, Spectrum fragment shader or `presentation_geometry.py`**. Therefore the current Spectrum top-line flicker/reactivity regression must not be papered over in that shader without first locating the changed source/presentation input seam. The attempted derivative-sized top-line floor did not fix the physical repro and is removed in this checkpoint.

- [x] **C1. COMPLETE: one visible card-border authority.** Root cause of the long-standing cross-widget thickness mismatch was twofold: most ordinary family adapters silently relied on their projector's hard-coded `4.0` default instead of threading `widgets.global.card_border_width_px`, while every H9 whole-card CUSTOM transform scaled that outer border with the content. Games You Follow was an accidental exception because it already read the global value itself. All ordinary adapters now resolve the global width explicitly, and `OverlayWidget` inverse-compensates only the outer card border under `presentationScale`. CP2 overlap testing also exposed stale `2.0` factory/smoke fallbacks in `OverlayWidget` and `OverlayCardStyle`; those are now synchronized to the canonical `4.0` default while production remains explicitly Settings-owned. No timer, guard, duplicate style owner or family-specific fudge is added.
- [x] **C2. COMPLETE: framed Visualizer radius/border + stencil parity.** The retained Visualizer geometry resolver treated card chrome as visual-world geometry: its border width changed with `uniform_visual_scale` and its 8 px corner radius was multiplied by that scale. Small/custom card poses could therefore approach square corners; the same collapsed value fed `inner_corner_radius`, so the stencil faithfully reproduced the wrong shape. Framed modes now keep the exact global visible border width and 8 px visible radius (geometry-capped only for impossibly tiny cards); the existing single resolver still derives the inner stencil radius. No second mask/stencil path was added.
- [x] **C3. PHYSICALLY ACCEPTED: Spectrum top-line flicker.** The width-based explanation was wrong. The real-GL failure proved the actual pixel defect: the moving horizontal cap used `authored_scale` as its raster coverage interval. When that scale was below one logical pixel, some fractional `active_height` values contained no fragment centre in the cap interval, so the moving endpoint became fill while the vertical sides remained. This is independent of bar width. The repair is one shader ownership correction, not a derivative/guard stack: the top cap keeps authored growth above 1 px but has a one-logical-pixel minimum coverage interval. The operator now confirms the weird bar flicker is gone. CP2 overlap then exposed a regression-test mistake: the real-GL test asserted both alpha-covered endpoints were border pixels even though `glReadPixels` makes `covered[0]` the moving cap and `covered[-1]` the stationary baseline, whose authored-scale bottom stroke was never part of this repair. The guard now checks the moving cap only. Broader C5 cross-display/card-chrome acceptance remains open. Durable incident record and permanent real-GL oracle: `Docs/Historical_Bugs/R-108_Card_Chrome_Parity_And_Spectrum_Regression_Audit.md`.
- [~] **C4. CHECKPOINT 2 IMPLEMENTED, AWAITING PHYSICAL: Spectrum reactivity parity.** Organs authored preset values and `bar_computation.py` are unchanged. The concrete post-anchor semantic change is `fd3a072985`: PyAudio capture stopped shaping the actual float32 payload and began rejecting any packet whose byte count did not equal callback `frame_count * channels`. The known-good path ignored that advisory count and reshaped the delivered payload by its actual channel-divisible length. Valid native packets can therefore be discarded while the stream still appears alive, reducing/jittering source updates without any preset change. Restore the known-good packet-shaping rule while retaining the new affinity owner, float32-only contract, malformed-channel rejection and exact authored block request. Physical Organs reaction still owns closure; do not compensate with gain/floor tuning. Durable incident record and permanent contradictory-`frame_count` PCM oracle: `Docs/Historical_Bugs/R-108_Card_Chrome_Parity_And_Spectrum_Regression_Audit.md`.
- [ ] **C5. Physical parity pass.** After the CP2 grouped gate, compare framed Visualizer corners/stencil (Bubble included), global border width on Media/News/Reddit/Gmail/Steam/Weather, Spectrum top edges and Organs reaction against the older screenshots/build on both displays. Include wide, ordinary and narrow Spectrum poses; the top-line test is about vertical raster coverage, not width.
- [x] **C6. ACCEPTED: 3D Settings visual-authoring parity audit.** Extruded now uses the shared alpha-capable **Bar Appearance** swatches as normal colour authority plus an explicit **Appearance** bucket with Rainbow enable + mutually-exclusive Faces/Edges participation and Hue Drift; the old `Spectral Faces / Spectral Edges / Bar Colours` enum survives only as persisted/runtime compatibility encoding. Mirrored Layout + Shape Editor remain in Shape. Material, Reflection, Shadow, Render and Ghost are separated advanced buckets, and Ghost explicitly inherits the rendered bar material because the renderer owns no independent ghost-rainbow participation path. Shockwave now owns line/crest alpha colour authoring in normal **Appearance**, with Waves + Bar Response normal and density/glow/floor/scroll/overflow in advanced **Render**. Shared Rainbow UI is no longer inserted as a hidden bucket for 3D modes that do not support that shared family. **R-109 follow-up:** the first C6 handoff crashed Settings construction because parked dynamic accessories queried `bubble:bar_appearance`, and the canonical bucket map still carried retired pre-C6 Extruded/Shockwave names. Stable accessories now bootstrap closed until compatible placement and the canonical bucket schema matches the C6 builders. No renderer, curated-preset or persisted visualizer-setting key semantics were changed. New Settings regression coverage proves shell construction across every persisted active mode, exact 3D bucket ownership and explicit Extruded controls round-trip back through the stable runtime enum. Operator acceptance received after the R-109 repair; C6 is closed. Durable incident: `Docs/Historical_Bugs/R-109_Visualizer_Settings_Bucket_Schema_Drift_Crashed_Settings_Open.md`.

Checkpoint-1 tests must include real retained-QML scale behavior plus Visualizer geometry/stencil contracts. Source-string checks alone are not closure.

### 0A. Bounded operator-flow / parity side quests | do not displace the existing roadmap

These are deliberately small quality-of-life repairs. They may reuse existing owners but must not introduce a parallel runtime, cadence owner or new background maintenance path.

- [x] **Q1. ACCEPTED: GODZIP Foundry `OPEN CP & DIFF`.** The first implementation used `cmd.exe /c start /wait` and immediately claimed the plan was opened when only the worker thread had started; on the operator machine the click registered but no editor was launched. The command-shell launcher is removed. Windows now opens the exact `Current_Plan.md` through native `ShellExecuteExW` / the file association, requesting a process handle with `SEE_MASK_NOCLOSEPROCESS`; `os.startfile()` is the association fallback if that native launch itself fails. The status remains **Opening...** until Windows actually accepts the launch. A distinct waitable editor still gets automatic close/save diff; single-instance/DDE handoff keeps the exact pre-open snapshot armed behind `CHECK CP DIFF`. Unchanged text stays silent and changed text opens the existing copy-ready unified-diff dialog. No filesystem watcher, polling loop or Git mutation is added.
- [~] **Q2. IMPLEMENTED, AWAITING PERF/PHYSICAL: one bounded IDLE ↔ BUSY refresh presentation across every refreshable retained card.** Feeds remains the visual baseline: bounded 30×30 target, 72% glyph, shared white hover frame/full-opacity hover contract; Reddit, Gmail and **Games You Follow** now use the same accessory. NEWS and every CUSTOM Feed slot already share `FeedPresentation.qml`, so any number of simultaneously-present feed cards consume the same path. The rejected `RotationAnimator` remains gone: no widget owns an animation tied to network lifetime. Instead each display's existing `OrdinaryWidgetPresentationHost` owns exactly one **240 ms `RefreshTransitionClock`** implemented with one bounded `QVariantAnimation`. Every accessory publishes only its existing IDLE/BUSY fact and joins that clock on a state edge; edges arriving while the clock is active coalesce into the same epoch rather than restarting or multiplying cadence. The shared `RefreshStateGlyph.qml` crossfades `↻` ↔ `◌` from that phase and becomes completely inert when the clock rests, regardless of how many providers remain busy or how long requests take. Steam Games You Follow now exposes its already-existing shared-owner `_in_flight` fact event-driven through the generation lease; it gains no new request/deadline owner. Regression coverage deliberately joins **32 simultaneous consumers** to one epoch so future refreshable widgets cannot accidentally turn instance count into scene cadence. Durable incident: `Docs/Historical_Bugs/R-110_Refresh_Animator_Unbounded_Quick_Render_Storm.md`.
- [x] **Q3. ACCEPTED: Double-right-click enters CUSTOM Edit.** Native Quick input gives right-button double-click first refusal before family double-click hit testing, **but only after the existing runtime-replacement pointer guard gets absolute first refusal**. The first shortcut handoff inspected `event.button()` before that neutral guard and broke the established opaque-event suppression regression. The guard now consumes replacement-window double-clicks without dereferencing them; admitted right-button double-clicks then route to the existing CUSTOM owner, dismiss the first right-click's retained context menu for that display, arm the existing short click-through guard for the second release, and start the normal global Edit session. No second editor/session owner is introduced; Alt+right Visualizer move remains separate and already-active Edit keeps its existing pointer ownership.
- [ ] **Q4. Later: lightweight `Ban Image` under Context Menu → Images.** Do not implement this as a growing Settings list scanned at startup or per rotation. Preferred design: canonical current-image identity hashed to a zero-byte persistent ban sentinel (or equivalently indexed on-disk key store) plus one persisted/default-false `has_banned_images` fast-path fact. When false, candidate admission executes **no ban lookup at all**. Once the first ban exists, candidate rejection performs one identity hash + direct indexed/existence lookup whose hot-path cost does not scale with the number of bans; no full list is loaded at startup. Ban action must immediately retire/advance the currently displayed banned image without rebuilding unrelated sources/prefetch and must define stable identity for local files and remote/feed image URLs before implementation. Add clear/unban maintenance only through an explicit user action, never background sweeping.

**R-110 operator evidence:** the grouped Windows tranche passed **578 tests in 48.42 s**. Runtime logs from the same build exposed the refresh-animation render storm described above; static/unit success did not cover that scenegraph-liveness failure. The next operator run must therefore pair the grouped gate with a cold-start + Settings-reinit PERF_HUD check. Prefer a deliberately busy configuration with Gmail, Reddit, Games You Follow and several NEWS/CUSTOM Feed cards enabled, then manually refresh several as close together as practical. One short transition burst is allowed at each IDLE/BUSY edge, but after the 240 ms display epoch rests, scene draw/swap rate must settle to the active logical demand even while one or many network refreshes remain in flight. Consumer count must not create sustained or multiplicative scene cadence.

**One grouped operator gate for the entire current C3/C4/C6 + side-quest tranche.** Do not split this into little batches unless a failure needs isolation. Run exactly from the repository root:

```powershell
$tests = @(
    "tests/test_settings_manager.py",
    "tests/test_settings_bucket_single_open_contract.py",
    "tests/test_visualizer_settings_body_transaction_contract.py",
    "tests/test_visualizer_settings_lazy_bodies_current.py",
    "tests/test_visualizer_settings_plumbing.py",
    "tests/test_visualizer_technical_profile_contract.py",
    "tests/test_visualizer_profile_lender_presets.py",
    "tests/test_3d_curated_preset_ownership.py",
    "tests/test_visualizer_preset_manifest.py",
    "tests/test_audio_capture_native_pcm.py",
    "tests/test_audio_capture_block_size.py",
    "tests/test_p2_audio_capture_lane.py",
    "tests/test_qtquick_extruded_spectrum.py",
    "tests/test_qtquick_visualizer_geometry.py",
    "tests/test_qtquick_visualizer_item.py",
    "tests/test_qtquick_visualizer_bubble.py",
    "tests/test_qtquick_visualizer_spectrum.py",
    "tests/test_qtquick_visualizer_devcurve.py",
    "tests/test_qtquick_h9_uniform_resize.py",
    "tests/test_qtquick_family_binder.py",
    "tests/test_qtquick_ordinary_widget_host.py",
    "tests/test_qtquick_feed_component_load.py",
    "tests/test_qtquick_games_you_follow_staging.py",
    "tests/test_steam_followed_shared_runtime.py",
    "tests/test_godzip_foundry_core.py",
    "tests/test_godzip_foundry_script_runner.py",
    "tests/test_click_affordance_parity.py",
    "tests/test_qtquick_input_controller.py",
    "tests/test_qtquick_context_menu.py",
    "tests/test_qtquick_gmail_presentation.py",
    "tests/test_qtquick_reddit_presentation.py",
    "tests/test_reddit_refresh_glyph_clearance.py",
    "tests/test_feed_header_parity_contract.py"
)
python -m pytest $tests -q
```

---

## 1. Bubble tiny-radius judder | protect feel first. DEFER AND SKIP UNTIL LOCAL AGENT CAN MEASURE PRECISELY.

The accepted render-release envelope remains the baseline. The tiny-breath experiment was rejected by recorded-music and
fixture A/B evidence and removed completely; R-105 owns the failure mechanism. Small drawn radii follow each authored
target directly. There is no disabled candidate or fallback implementation.

- [~] **B1. Awaiting Validation / Logs: localize the remaining physical defect on the restored baseline.** Match the affected
  song passage to the canonical recording, mode/preset, CUSTOM viewport/uniform scale and display DPR. Identity-preserving
  replay found no alternating runs in the <=8px band at the supplied 300px projection. Establish the actual affected radius
  band and distinguish radius reversal from dot/outline representation chatter or shared delivery stalls before another repair.
- [ ] **B2. Evidence-led presentation repair.** Only after B1 reproduces the defect, fix the owning seam without changing audio,
  simulation gain or cadence. Pixel eligibility/bounds must use the actual renderer response-height projection plus scale/DPR,
  not logical viewport height. Retain per-clip frame-aligned radius differences, boundary crossings and extrema/excursion;
  verify isolated first response, attack, peak/turn timing and authored amplitude with existing golden/reactivity bars.
  Input-window first radius movement on already moving music is not proof of causal audio latency. No golden rewrite.
- [~] **B3. Awaiting Validation: physical acceptance on both displays.** Check the restored baseline and any subsequently admitted
  repair at quiet breathing, strong hits, sustained loud sections, min/max size, pop/exit and CUSTOM extremes. Reject a repair
  that feels flatter/slower even when the judder metric improves.

Until physical localization is available, proceed with the shared-runtime/lifecycle work below. Do not invent another Bubble filter.

The canonical local real-music corpus for B1-B3 is under `logs/visualizer_recordings/`: `balanced.jsonl`, `heavy1.jsonl`,
`quiet_intro.jsonl` and `quiet_intro2.jsonl`. These are operator-authored schema-2 captures and are intentionally local/large;
`*_vN` and `*_noevents` files are retained archived/derived takes, not additional canonical corpus members. The production
`recorded_clips()` selector excludes those suffixed takes automatically. Synthetic fixtures and committed goldens remain separate
negative-control/regression evidence and must not be substituted for the real-music corpus when B1-B3 require recorded music.

Focused automation:

```powershell
python -m pytest tests/test_bubble_render_judder.py tests/test_bubble_fidelity_report.py -q
python -m tools.visualizer_replay.bubble_judder --fixtures --clip broadband_noise --frozen --compare-release --px-per-unit 300 --min-px 0.5 --report logs/bubble_judder_acceptance/release_fixture.json
```

Real recordings:

```powershell
python -m tools.visualizer_replay.bubble_judder --compare-release --px-per-unit 300 --min-px 0.5 --report logs/bubble_judder_acceptance/release_recordings.json
```

Durable mechanism/negative controls: `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md` and
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

---

## 2. Shared presentation stalls

Treat Bubble/DevCurve as canaries for shared delivery. Do not retune a Visualizer to hide GUI/runtime stalls.

- [ ] **P4. Re-trace after P1-P3.** Investigate native/swap/sync ownership only if unattributed presentation holes survive.
  Do not add a compositor timer or `frameSwapped -> requestUpdate()` loop.
- [ ] **P5. Physical bar.** Unattended two-display Bubble + DevCurve run with no Settings/mouse interaction; compare
  >25 / >33 / >50 ms gaps and owner classes before/after.


---

## 3. Visualizer dormancy and retirement

The binding invariant is count-independent: registry growth must not add recurring work to an unrelated active mode.

- [~] **L4. Awaiting Validation / Logs: replacement-generation terminal owner release.** Ordinary and traced MC stop beyond
  startup freeze now match actual child exit 0 with current-session Qt/QML clean. Exercise replacement generations after
  freeze and confirm Python-owner release through the destruction barrier, not just a logged application exit. If the earlier
  diagnostic actual-exit-1/logged-exit-0 discrepancy recurs, preserve and investigate it. Keep the focused weakref/replacement
  proof; do not extend deadlines or force GC.

Durable invariants: `Docs/Guardrails/Performance_Optimization_Contract.md` P5 and
`Docs/Guardrails/Visualizer_Presentation.md` 1A.

---

## 3A. Visualizer CUSTOM geometry profiles | planar ↔ freeform 3D hot-swap

Descriptor-owned `planar` / `freeform_3d` poses now use the existing CUSTOM variant axis, commit/hydration and transaction
owners. Cross-family activation restores the pose while hidden; Edit framing uses the renderer-derived read-only envelope.
Stable geometry, migration and gesture truth lives in `Docs/Contracts.md` and `Spec.md`; this section owns remaining acceptance.

Quota-stop orientation: the profile split, renderer-derived read-only 3D content envelope/pivot and Edit-time Alt orbit/move/scale routing are already in tree. The immediate finish slice is chrome/acceptance, not another geometry redesign. Edit framing, guides, resize affordances, transfer/HIDE chrome and freeform-3D Orbit use a neutral dark-grey/graphite family rather than cyan/blue theme accents. The parent wedge reads **HIDE / SHOW**. Freeform-3D Orbit is a compact arrows-only 22px glyph in the stable bottom-left parent-glyph row immediately beside Restore; it does **not** follow the moving projected 3D envelope.

- [x] **G14. ACCEPTED: Optional fit is explicit, glyph-first, never ambient.** If physical acceptance shows users still need a one-shot
  way to bring a wildly edge-on/oversized scene back into a useful stage, add an explicit Edit-only **Fit Scene** action that
  computes a proposed stage rect from the same projected-envelope authority and writes it only into the active working session.
  If admitted, expose it as its own compact **unique glyph button in Edit chrome**, with the same hover/visibility language as
  the other Edit affordances; do not bury it in a context menu. It must be undoable/cancellable and must never run merely
  because orbit, music or mode changed. Do not overload Restore Size unless its existing authored-baseline semantics remain
  exact.
- [x] **G15. ACCEPTED: repeat the failed operator Edit gestures.** Native window/QML/session proof covers signed
  wheel movement on either Qt axis, zero no-op, reversible scaling, Alt-right completion, clickable Orbit and overflow ingress.
  The actual accepted-frame footprint and an empty scene retain independent orbit admission with no continuing audio observer.
  Review `logs/edit_footprint_proof/selected_edit_contact_sheet.png`, then repeat Alt-wheel in both directions, Alt-right move
  (including releasing Alt first), glyph/Alt-left orbit and Save/Cancel on the shallow turned bars. Confirm the saved stage
  remains stable and the primary frame matches the item throughout orbit. Confirm the neutral graphite Edit palette, **HIDE / SHOW**
  copy and the arrows-only Orbit glyph fixed beside Restore remain legible/clickable without covering projected content.
  Production-render/QML proof does not close feel.
- [~] **G16. Awaiting Validation: physical acceptance.** On both displays, deliberately author a compact/off-widget planar pose and a substantially
  different freeform-3D pose. Repeatedly hot-swap Spectrum/Bubble ↔ Extruded/Shockwave (and Sphere after promotion), including
  preset changes and orbiting. Each family must return exactly to its own useful placement/size without covering the wrong
  widgets, inheriting the other family's proportions, visible one-frame jumps, lost orbit state or Edit/Arrange fluidity. In
  Edit, compare front-facing and near-edge-on 3D views: the primary content envelope must remain visually honest while the saved
  stage remains stable, and Alt orbit/move/scale must feel identical to their non-Edit counterparts except for Edit's deliberate
  Save/Cancel semantics.


---

## 4. 3D Visualizer authoring parity | Extruded and Shockwave

Each mode owns its complete technical, source-shaper,
bar/ghost families where consumed, smoothing and bar-height stabilization; shared UI/evaluation remains one implementation.
Curated snapshots are explicit and self-contained, and the before-default-fill migration preserves old borrowed values once.
Direct fill/body alpha and the optional canonical-direction shadow have real-GL proof. Current behavior belongs in
`Docs/Reference/Visualizer_Reference.md`; these are the remaining actions.

- [x] **E7. COMPLETE: full relevant checkpoint gate.** Windows accepted the complete grouped 3D Settings/runtime migration gate at **296/296 passed in 11.87 s** after the earlier 186/186 and 221/221 checkpoints. Lazy construction/reopen, per-mode Technical UI-state identity, Custom ↔ curated-preset isolation, mode-owned activation/capture, Reset authority and RAW-Spectrum-to-Sphere startup migration are now source/runtime accepted. Do not extend this closed migration with speculative compatibility scaffolding; physical visual acceptance remains E8.

- [~] **E8. Awaiting Validation: physical acceptance after historical-response repair.** The second physical pass exposed that
  the ownership migration had preserved Extruded's new private architecture but **not its former effective response**: before
  ownership, Extruded resolved Spectrum's selected preset at activation. On the default/Organs path that meant 35 bars, 128-sample
  audio blocks, Dynamic Floor ON with 0.42 baseline, Output Lift ON, AGC 0.34, Input Gain 0.98, fixed Sensitivity 0.97, Kick Lane
  Gain 1.70, Transient Clamp 1.85, Kick Lane Mix 0.90, plus Organs' shape/notches/lane strengths/wave/floor/falloff/ghost profile.
  The schema-10 ownership landing instead generated a generic 33-bar/512-sample profile, which explains the operator's Preset 1 →
  Custom mismatch and altered reaction. Canonical Extruded defaults and all four curated Extruded presets now freeze the complete
  default-Organs effective profile into `extruded_spectrum_*` ownership while retaining distinct 3D finish/material/orbit state.
  Historical opaque Extruded fill remains opaque (Organs RGB with alpha 255). Schema 11 narrowly repairs only the recognizable
  generated schema-10 bundle in live/Custom state, field-by-field, preserving deviations that are genuinely user-authored.
  Dynamic Floor is restored ON for historical fidelity even though the operator may deliberately retune it OFF later.

  The same pass attempted Extruded's independent directional-shadow defect by projecting the full cuboid silhouette onto the floor rather than
  translating only the top cap, with overlapping projected faces unioned once. Settings keeps Mirrored Layout + the shape/lane
  **Physical override:** the operator still reports no visible Extruded shadow after that source change. Treat the shadow as OPEN regardless of source/real-GL contracts; trace the complete pass admission, shadow colour/alpha, target reach/compositing and floor-space projection before another geometry tweak. No more shadow work may be declared fixed from source inspection alone.
  editor together in Shape. Recheck both displays: Spectrum top edges at small/wide CUSTOM scale during idle and music; Extruded
  Preset 1→Custom and all four curated finishes; historical Technical values; Dynamic Floor on/off comparison; shadow on/off and
  directions; overflow/orbit; reflective/non-reflective; opaque/translucent looks; ghosting; CUSTOM resize/reflow; wallpaper
  transition; and Mirror Faces on bright/dark photographs. Spectrum top-edge flicker and broader Organs reaction parity are now owned by the checkpointed C3/C4 regression audit above; the failed derivative-line experiment has been removed rather than stacked.

---

## 5. GitHub Release / README animated WebPs

The capture/encode/manifest tool and its focused smoke proof are implemented in the working tree, awaiting checkpoint and
full catalogue output. Release/readme media stays outside runtime QRCs and normal GODZIPs. `Docs/Reference/Release_Media.md`
owns the tool's registry, source-attribution, capture and encoding contract.

- [ ] **M1. Land the tool and generate transition media.** Review/checkpoint `tools/release_media.py` and its focused tests,
  then capture every admitted canonical registry identity plus meaningful curated appearance variants on a stable source tree.
- [ ] **M2. Generate Visualizer media.** After the authoring/geometry source checkpoints are stable, capture every registered
  mode's curated presets with the canonical schema-2 recorded-music clip through the production replay/capture/render path.
- [ ] **M3. Inspect the generated catalogue.** Confirm motion/endpoints, photograph-backed Visualizers, loop/metadata/dimensions
  and release size limits; reduce dimensions/fps before lowering quality when needed. Retain the real outputs and manifest.
- [ ] **M4. Verify incremental regeneration.** Re-run the stable catalogue to prove unchanged items stay current and changed
  source/preset/clip inputs regenerate only affected/stale media. The source guard must refuse mixed-revision captures.

---

## 6. Run-matrix acceptance harness

- [~] **Awaiting Validation / Logs: remaining configuration/replacement cases.** The short MC and ordinary/traced 55-second
  post-freeze cases passed actual process/current-session checks; evidence is under `logs/run_matrix/mc_rss_fixed_20261007/`
  and `logs/run_matrix/mc_after_freeze_20261007/`. Repeat the relevant cases after the final authoring/geometry checkpoints
  and operator-selected display/mode/effect configurations, including L4 replacement generations. The harness exercises saved
  settings; it cannot substitute interactive single-display evidence for P5's unattended two-display canary run.

The declarative input, evidence scoping and source attribution contract lives in
`Docs/Reference/Harness_Index.md` → Bounded self-terminating RUN sessions. Raw logs remain the evidence authority.

---

## 7. Voxel Sphere promotion | settings parity-plus

Sphere's move from experimental/private plumbing to a standard Visualizer is also its authoring-surface graduation. Do not
promote the renderer while leaving it dependent on hidden Spectrum settings or a thinner Settings contract than older modes.

The consumed analysis inventory, mode-owned technical profile, selected frequency splits, direct RGBA alpha and Rainbow
speed/extent have source, PCM and real-GL proof. Startup, legacy Custom-cache and SST promotion preserve RAW Spectrum values
once before defaults, while curated Sphere looks restore complete owned snapshots. `Docs/Reference/Sphere_Visualizer.md`
owns current controls and migration details. Remaining product admission and acceptance:

- [x] **S5. COMPLETE: standard promotion semantics.** Sphere presents as **Voxel Sphere** rather than an Experimental product, uses the registry's normal Guided Setup offer path, and retains the same canonical `mode_activation`, preset catalogue, Custom-cache and Reset owners proven by E7. The promotion gate ran in the subsequent Windows 203-test 3D/S5 cluster; its sole failure was the now-obsolete Extruded preset-shape inequality oracle after the operator deliberately requested one Organs-derived Extruded shape. All S5-specific activation/onboarding/dormancy coverage passed. Lazy Settings/capture/runtime/renderer imports, prepared reveal, independent disablement and inactive resource dormancy remain unchanged.
- [~] **S6. Awaiting Validation: loaded-desktop GPU tail.** The shared per-frame uniform block, ring/resource/lifecycle
  migration has focused driver, retirement and unchanged-golden proof. Investigate the measured whole-host GPU p90 increase
  under actual loaded display use before claiming performance neutrality; the lower CPU submit/GL-call count and near-neutral
  isolated draw time do not close that gate. `Docs/Reference/Sphere_Visualizer.md` owns the scoped measurements.
- [~] **S7. Awaiting Validation: physical/golden acceptance.** Behavioral vocabulary preserved or stronger; Mirror Ball / Mirror Cubes, tier AA,
  overflow, wallpaper reflection, opaque/translucent looks, Rainbow, particle/fragment extremes and distinct preset-owned
  reactions on bright/dark images and both displays. The promotion must not regress current Sphere goldens merely to satisfy a
  generic Settings layout.

---

## 8. Transition expansion tranche (immediately after Sphere)

These transition concepts are promoted into the active roadmap rather than left as distant-future backlog. The current
visual mocks are local-repo references only and should be preserved for implementation review:

- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TBlockPuzzle.png` — clean-room jigsaw/puzzle-piece
  flip replacement concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TVolu.png` — Volumetric Dissolve concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TVHS.png` — VHS Distortion concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TLens.png` — Liquid Lens concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TMemb.png` — Membrane Turnover concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TGroup.png` — grouped second-batch concepts in
  this fixed order: Surface Tension Merge, Edge Bloom Reveal, Chromatic Shear, Depth Card Cascade, Capillary Bloom.

The local mocks are design references, not fidelity prisons. They establish the intended visual family and order of attack.

- [ ] **T1. Jigsaw Piece Flip (clean-room Block Puzzle replacement).** Implement this as a **new** transition rather than
  mutating the existing Block Puzzle Flip implementation. The goal is the originally intended behavior: puzzle outlines draw or
  fade in, then one piece at a time flips from Top Left / Top Right / Bottom Left / Bottom Right / Random ordered starts /
  fully unordered piece order, each flipped piece carrying its own portion of the destination image and clearing its local puzzle
  outline once landed. Useful existing architecture: canonical transition registry, per-display transition gating, retained Quick
  presentation ownership, current transition timing/identity plumbing, and any reusable shared 3D card-flip mesh/math that does
  **not** drag in old Block Puzzle behavior. New useful architecture: a shared transition-piece layout generator plus bounded
  per-piece scheduling/order-planning helper so future tiled/card effects can reuse the same geometry/order substrate. Leave the
  legacy Block Puzzle Flip installed for now; remove it only after this clean-room successor is accepted and the operator chooses
  retirement timing.
- [ ] **T2. Volumetric Dissolve.** Use the mock as the target feeling: the outgoing image disintegrates into colored particles,
  mist and shallow volume while the incoming image resolves behind/through it. Useful existing architecture: Scene3D lifecycle,
  shared uniform/state ownership, retained presentation control, and any particle infrastructure admitted by the shared 3D
  primitives work. New useful architecture: bounded reduced-resolution smoke/fog volume support, color-carrying image emitters,
  depth-aware compositing/OIT where justified, and reusable transition-side particle emission masks.
- [ ] **T3. VHS Distortion.** Treat this as a deliberate stylized transition, not a joke/glitch throwaway: horizontal tearing,
  scanline interference, chroma drift, dropout bands and unstable tracking carrying the source toward the destination. Useful
  existing architecture: fullscreen material/post passes, transition registry/timing, retained Quick presentation authority and
  the current transition harness/capture path. New useful architecture: a reusable distortion/noise primitive set (scanline,
  dropout, luma wobble, chroma offset, line displacement) so VHS can ship cleanly without becoming a bespoke hard-coded pile.
- [ ] **T4. Edge Bloom Reveal.** Promote the grouped mock's second concept into the first-wave batch: strong edges from the
  destination image appear as luminous structural lines over the source, thicken, and fill into full image regions. Useful
  existing architecture: fullscreen shader passes, existing mask/reveal sequencing, transition registry and capture harness. New
  useful architecture: a shared edge/gradient-mask generation pass and controllable region-growth/fill helper that later reveal
  transitions can reuse.
- [ ] **T5. Liquid Lens.** The destination image is seen first through a moving/refractive lens that expands and distorts until
  it consumes the frame. Useful existing architecture: current transition timing/identity plumbing, fullscreen distortion passes,
  retained presentation authority. New useful architecture: shared restrained refraction/thickness/dispersion helpers from the
  3D primitives program, kept bounded and consumer-owned.
- [ ] **T6. Membrane Turnover.** A taut glossy sheet deforms, stretches and turns through itself to reveal the destination
  image. Useful existing architecture: any shared mesh deformation/card surface math admitted by Scene3D primitives plus current
  transition sequencing. New useful architecture: a reusable deformable-sheet or low-resolution transition mesh substrate rather
  than a one-off transition-only simulation.
- [ ] **T7. Surface Tension Merge.** Source and destination behave like two fluids separated by a moving meniscus boundary;
  rounded pools swell, merge and take territory. Useful existing architecture: fullscreen passes, mask/reveal sequencing,
  transition registry. New useful architecture: a shared organic-boundary/meniscus field helper that can also serve capillary or
  liquid-family effects.
- [ ] **T8. Chromatic Shear.** A clean prismatic transition where the source image splits into offset spectral layers and broad
  shear slices before reconverging as the destination. Useful existing architecture: fullscreen post/material passes and timing
  plumbing. New useful architecture: shared chromatic-channel displacement/spectral-slice helpers so the effect stays elegant
  rather than duplicating ad-hoc RGB math.
- [ ] **T9. Depth Card Cascade.** The outgoing image separates into a small number of large shallow-Z cards that tilt/slide past
  the viewer, exposing the destination behind them. Useful existing architecture: retained presentation authority, Scene3D
  lifecycle, per-display gating, and any shared flip/card primitive introduced by Jigsaw Piece Flip. New useful architecture: a
  reusable card/depth-layer primitive with stable ordering, shadows only where justified, and transition-owned parallax rather
  than bespoke transition-local geometry.
- [ ] **T10. Capillary Bloom.** The destination image spreads through the source like dye moving through wet fibres: branching
  tendrils, joins and bloom fronts, but the final destination image resolves cleanly. Useful existing architecture: fullscreen
  material passes, reveal/mask sequencing. New useful architecture: a shared organic propagation field / capillary-front helper,
  preferably compatible with Surface Tension Merge rather than an isolated solver.

Implementation order inside this tranche is deliberate: **Jigsaw Piece Flip, Volumetric Dissolve, VHS Distortion and Edge Bloom
Reveal first; then Liquid Lens, Membrane Turnover, Surface Tension Merge, Chromatic Shear, Depth Card Cascade and Capillary
Bloom.**

---

## 9. Shared 3D primitives and next consumers

Resume only after the immediate Bubble/shared-runtime/lifecycle work above is under control.

- [ ] **S17 remaining active-only scene facilities:** demand-created normal/material/depth/history attachments, reusable real
  3D shadows, GTAO only if justified, weighted blended OIT/depth-aware transparency, thickness/depth refraction, Fresnel,
  rough transmission and restrained dispersion.
- [ ] **S18 primitives:** sprite/streak/ribbon particles over `CompactedPopulation`, collision/OIT where justified, lightning,
  then bounded reduced-resolution smoke/fog/fire volumes with advection/vorticity/depth raymarch/temporal reprojection.
  Measure each primitive independently before combinations.
- [ ] **Visualizer vertical sequence:** Reactive Particle Field -> Spectrum Terrain/Skyline/Tunnel -> Waveform Ribbon ->
  Deformable Blob Sphere -> Bubble Depth Field under Bubble Temporal Fidelity.
- [ ] Only after primitives are accepted: electrical storm terrain, smoke-lit voxel fracture, ember/dust destruction,
  refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL combinations.

---

## 10. Queued side quest: canonical CPython 3.14 migration

**Not started.** Start only after the current remedial work is complete and committed, its full relevant test/chunky gate
is green, and a clean pre-migration checkpoint exists. Once admitted, this operator-directed migration takes precedence
over new feature expansion. Physical acceptance cannot be inferred from test results. Git owns rollback; an untenable
migration is reverted rather than retained as competing Python authorities or compatibility scaffolding.

- [ ] **PY1. Admission and baseline.** Close the prerequisite remedial gates; run the full relevant chunky/durability gate,
  commit/push a clean pre-migration checkpoint, and retain exact interpreter/dependency/tool versions, product artifact sizes
  and bounded startup/exit evidence for comparison.
- [ ] **PY2. Exact dependency audit.** Verify current stable standard-GIL CPython 3.14 x64 and the complete requirements/build
  dependency set against Windows cp314 wheels. Preserve PySide6/Qt 6.11.2 and compatible pins; change only incompatible
  dependencies and required coupled packages. Identify exact blockers before considering a workaround.
- [ ] **PY3. One build authority and immutable inputs.** Migrate every real bootstrap/venv/build/helper/prerequisite path to
  3.14; remove 3.11 fallback behavior. Detect and clearly rebuild/refuse an old-interpreter root `.venv`. Reuse a bounded local
  immutable wheel/input cache keyed by exact Python/ABI, Windows architecture and locked dependencies; keep large inputs out
  of normal Git. Checkpoint the coherent new authority early. End users still require no installed Python.
- [ ] **PY4. NumPy 2 and native-contract migration.** Audit removed APIs, dtype/ABI/buffer/contiguity/structured-layout assumptions
  in production and tests, especially audio, GL uploads, Scene3D packing and transition geometry. Preserve numerical/rendering
  behavior, goldens, cadence and lifecycle; fix at the owning boundary.
- [ ] **PY5. Complete acceptance.** Create a clean environment using canonical scripts; install the complete locked dependency
  set; pass the full test suite/chonky chunks, durability/policy, Visualizer/audio/NumPy and real-GL/Scene3D gates. Build and
  launch Standard, Diagnostic, Media Center and Reddit/helper frozen products without system-Python participation. Verify
  startup/exit/multiprocessing and compare sizes plus obvious startup/runtime regressions with PY1. Record useful checkpoints.
- [ ] **PY6. Accepted baseline and cleanup.** Record exact known-good Python/dependency/build-tool versions in the canonical
  build docs; leave 3.11 only as historical context. If fundamentally incompatible, revert the migration to PY1 and retain
  the exact blocker evidence instead of dead fallback code.

---

## Cross-cutting acceptance for every slice

- [ ] **Dormancy/count invariance:** inactive registry entries add no recurring runtime work; only admitted owners may prepare,
  with the documented single reserved-next-transition exception.
- [ ] **Performance:** measure CPU submit/GPU cost and Python GL-call pressure for new render passes.
- [ ] **Time:** no second simulation clock, catch-up queue or hidden recurring timer.
- [ ] **State:** touched GL state is fence-restored on success and failure.
- [ ] **Memory:** targets/buffers/volumes/history are bounded, consumer-owned and retired deterministically.
- [ ] **Settings:** canonical defaults/descriptor resolution happen before admission; renderers do not read Settings per frame.
- [ ] **3D authoring parity:** shared editor/schema/runtime helpers may be reused across modes, but authored values, Custom
  state and preset snapshots are per-mode. A 3D mode must not silently inherit another mode's currently selected preset merely
  because it shares analysis/render machinery. Expose only settings with a proven consumer; richer 3D modes may exceed 2D
  parity where their renderer has meaningful extra axes.
- [ ] **Test authority:** the blocking durability audit stays green for touched areas. Tests derive defaults, preset/catalog
  membership and other mutable authorities from their current canonical owner unless an exact literal is itself the contract.
  Advisory pin/source-copy queues are review aids, not automatic project debt.
- [ ] **Unattended evidence:** do not skip, xfail or deselect a test merely because it exposes a window. Preserve the evidence and
  move it offscreen/non-intrusive where the same native Qt/GL/input contract can be retained. Keep `Docs/TestSuite.md` aligned
  with material test-infrastructure changes.
- [ ] **Physical:** both displays, cold/warm use, switching, CUSTOM, Play/Pause/Resume, real photos and representative music.

## Handoff rules

For remote/archive handoffs, the supplied/latest GODZIP is the working-tree authority. Significant handed-off slices return a
full-file superseding GODZIP, never a partial patch. Do not include oversized generated media, recordings, frame traces, build
outputs or unchanged giant assets/tests. GODZIP manifests are produced/validated with `tools/godzip_foundry_core.py`; every
generated archive also carries `.godzip/workflow.md` with transfer rules for that archive-handoff workflow. Those transfer rules
do **not** govern Codex, Claude or another local-repository application that is already operating directly in the checked-out
repo; local repo agents follow the operator's workspace/repository instructions and should not switch themselves into GODZIP
mode merely because `.godzip/workflow.md` exists. `.godzip/*` is archive metadata, never a repository replacement target, and
`ui/assets/` is a hard normal-GODZIP exclusion rather than optional handoff payload. No environment-variable feature gates.
Rejected experiments are removed rather than retained as fallback architecture.

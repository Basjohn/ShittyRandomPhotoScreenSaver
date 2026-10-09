# R-113 | Independent 3D CUSTOM profiles exposed Edit stage / mesh / cage and mode-change regressions

**STRONG RETENTION VALUE DOCUMENT**

**Status:** Code repair staged, Windows grouped test and physical acceptance pending.

## Evidence

First G17–G21 grouped Windows gate: **731 passed, 20 failed, 71.99s**. The failures clustered around outdated preset/view-orbit expectations (no longer allowed to mutate view pose), exact 3D stage hydration, four retained-runtime Save incoherence errors, orbit click admission, a graphite guide oracle and missing test imports. Operator screenshots and `--geo` logs show an Extruded stage resizing without its mesh following until mode re-entry, missing projected 3D cages and cross-profile mode requests rejected during Edit.

## Causal contracts and repairs

- The 3D presentation resolver reconstructed saved height from width-derived uniform world scale. Stage size is now an explicit two-dimensional CUSTOM input, separate from the logical rendering extent; it is not re-inferred from the world aspect ratio.
- Normal Visualizer publications could restore committed presentation over the current Edit working stage. Retained session stage remains the source for frame composition while an admitted Edit override exists.
- Reusing previously multiplied `content_fade` could keep the visible mesh suppressed across a mode transition. Each presentation derives fade only from the owning transition state.
- Cross-profile switches were blocked to avoid corrupting the single-Edit transaction. They now occur only at the hidden mode-activation edge: park the outgoing working profile in the **same** session, admit the target, keep Save/Cancel atomic. Parked variants are **not** duplicate widgets or live snap obstacles. All existing variant commits still use the canonical writer.
- Extruded's cage was gated behind a visible audio-dependent footprint, so it disappeared during empty source/reveal. The structural projected cage has its own paint admission while the actual content footprint remains honestly absent. Its north marker remains projected onto the real cage face.
- Historical tests assuming presets owned tilt/turn, orbit mutated curated presets, outdated accent-blue Edit guides, and two missing `dataclasses` imports were corrected; the strict Save-coherence regression is **not** relaxed.

## Permanent gate

Retained Qt tests must prove independently sized 3D stages hydrate exactly, Save promotes the active profile without runtime reconciliation, parked siblings survive Edit switches and Save/Cancel, empty audio can display a cage without a fake content reach, and orbit works through the actual compact hit area. Operator verifies live mesh and cage, Edit mode switching, Arrange, Settings reinit, multi-display behavior and no sustained geometry mismatch counters.

The operator subsequently supplied `presets/visualizer_modes/spectrum/preset_1_organs.json`; R-114 embeds those exact received bytes. Do not regenerate that preset from defaults or from the frozen Extruded migration baseline.

## Second grouped operator regression (R-113 follow-up)

The R-113 Windows gate produced **738 passed, 16 failed, 62.74s**. Seven failures exposed a real authored-data conflict: curated Extruded and Shockwave JSON files still physically held camera tilt/turn despite the preset layer excluding those keys at runtime. The curated files have now been sanitized of view-pose fields without changing response/material/appearance values; future preset files must never regain view-pose ownership.

Four Edit Save/profile cases raised `CUSTOM visualizer geometry does not encode one pixels-per-world scale`. Freeform 3D stages deliberately allow a different aspect from their renderer world. The planar strict scaling guard remains, but freeform 3D computes a bounded interaction scalar without asserting aspect equality. Its X/Y side and corner resize preserves the authored world extent so stage growth actually enlarges the mesh; uniform resize multiplies the existing stage rectangle rather than reconstructing its shape from viewport extent. Arrange calls the same profile-aware helper.

The remaining regressions comprise an uninitialized Edit owner access in a display-transfer test, a structurally admitted cage whose tuple projection did not reliably marshal into a JS array, and stale test oracles that rejected the newly required empty-source cage or expected pre-graphite guide colours. The cage is normalized into Qt-compatible lists before the retained QML handoff; it remains read-only and no source cadence is introduced.

**Do not close this incident from source parsing alone.** One grouped Windows Qt gate and physical first-entry 3D Edit scaling/cage visibility, Save/Cancel, mode switching, Arrange and display transfer remain mandatory.

## Third grouped operator regression (R-114 follow-up)

The next Windows gate produced **744 passed, 11 failed, 59.22 s**. Failures covered (1) an obsolete Extruded-preset assertion that still demanded `turn` and `tilt` in curated files; (2) four N-profile Edit switching/Save scenarios; (3) four signed Alt-wheel geometry round-trip cases; (4) a first-frame/empty-audio Edit-envelope callback over-publication; and (5) an obsolete white crosshair expectation after graphite chrome was accepted.

The critical Edit-switch seam was selecting the new `CustomLayoutSessionItem` before the retained renderer's hidden mode activation. `QuickSceneController._sync_custom_layout_visualizer` then looked up mechanics from the *outgoing* render identity, applying planar pixels-per-world validation to a legitimate incoming `freeform_3d` stage. It now uses the **active Edit session item's** descriptor-derived `geometry_kind` during that transition, retaining one authority and no additional presentation state.

The Save regression test mutated `current_global_rect` directly without publishing that change via the session's existing `notify_item_changed`. That made the strict retained-runtime coherence check correctly reject an unrendered edit. Tests now deliver the same change notification as actual pointer gestures; the product's strict Save rejection remains unchanged.

Alt-wheel stored stage dimensions use integer `QRect` values. Its regression now asserts that the retained stage follows the session rectangle on both axes and that the uniform aspect differs only by the mathematically unavoidable per-axis half-pixel rounding envelope. No geometry or UI tolerance was weakened in the production renderer.

Audio-only `present_frame=False` wakes are not eligible Edit framing publications; they must not resolve geometry or disarm the pending first visible frame. Existing empty/first-frame and held-orbit regressions remain the authority. The accepted graphite guide colour and view-pose-outside-preset assertions were updated to match their settled product contracts.

**Physical acceptance and the grouped Windows/Qt suite remain mandatory.** Source/static checks alone cannot close the invisible-cage or intermittent mesh scaling reports.

## Fourth grouped operator gate (R-115 follow-up)

R-114 operator run: **749 passed / 6 failed in 68.24s**. The remaining planar-to-3D draft switch called `resize_visualizer_presentation` with `committed_outer_size` while the retained baseline still used the outgoing CARD shell, which rejected explicit 3D stage dimensions and could cascade into the Edit retirement/restore path. The current active session profile and the retained render identity must agree before projecting a working Edit stage; once the target's coherent presentation is published, the same retained session applies its geometry. Do not bypass the resolver's CARD/FRAMELESS contract.

Four signed Alt-wheel tests recorded a genuine 480x270 to 480x269 cumulative integer-rectangle drift across reversible uniform gestures. The 3D session item now keeps a **derived, transient, unscaled uniform-shape reference** while the gesture sequence is uniform, refreshing it only when an explicit side/shape edit or transfer establishes a new stage. Persistence remains exclusively the current `QRect` and its normal CUSTOM layout carrier; the reference does not enter settings, presets, renderer, or a second geometry store. A dedicated regression checks round-trip and explicit re-shaping. The existing three-entry Edit Undo snapshot also captures/restores that transient derived reference, so Ctrl+Z cannot silently change later uniform sizing.

The last orbit test observed non-present audio-only snapshots invoking the authored-view callback despite the manager guarding them afterward. The admission gate now lives at the GUI publication callback boundary as well, before any Edit footprint/cage computation. Pending first-visible source remains armed until a genuinely presentable frame.

Grouped Windows Qt tests and actual Edit/cage/Save/Cancel/hot-swap physical acceptance remain mandatory; this static-only environment cannot close R-113/G17–G21.

## Fifth grouped operator gate (R-116 follow-up)

R-115 Windows gate: **752 passed, 5 failed in 60.50s**. Its two new 3D wheel regressions showed a stale nonpersisted `uniform_stage_reference` surviving an explicitly authored stage size; a later wheel gesture used the old shape, shrinking a valid 480×270 stage to 360×200 or interpreting a directly replaced 610×180 shape through the previous 360×200 baseline. The working stage is sole authority. Reset the derived reference when the published QRect and reference×scale disagree beyond integer quantization; keep it stable for actual wheel round-trips.

Two historical retained Edit/transfer tests create planar Visualizer session entries with legacy `geometry_variant=default`, not modern `planar`. The cross-profile safety guard must admit that alias **only** for a planar target/planar session, while all named 3D profiles stay strict. Do not drop the mode/target-shell guard to make those tests green. The final orbit test counted the intentional authored activation-edge cage resolution without clearing its counter before a non-present frame. Separate structural-edge observation from audio-only callback observation; do not remove the genuine single-frame callback guard.

The full Qt grouped test and real first-entry 3D scaling, cage visibility, cross-mode Save/Cancel and display transfer checks remain pending.

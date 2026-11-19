# TEMPORARY: cumulative SRPSS material, UI, Steam and installer audit (18–19 November 2026)

**Scope:** inspect the *cumulative* handoff, not just the latest cosmetic edit. Baseline: `GODZIP_e53f4a6645_2026-11-18_1411.zip` at `e53f4a6645`; candidate: the full GODZIP containing this document. Source tree is intentionally cumulative and dirty; never reset to baseline or assume omission means deletion. The generated file inventory at the end is built from byte comparisons of those archives.

**Temporary working checklist, NOT a new specification, migration or native-core milestone.** This file is deliberately disposable. Complete its checks, repair verified defects, record any enduring decisions in their existing owning plan/spec/bug record, then **delete this temporary document** and check off/remove its single `Current_Plan.md` audit entry. No separate master plan, README or new authority is to survive.

## Audit outcome ledger (fill in on the actual Windows build)

| Gate | Evidence required | Result |
|---|---|---|
| Archive and install | GODZIP manifest hashes, Git diff, file ownership, original Steam paths present, installer options checked | Pending |
| Qt/QML load | All presentation QML compiled by actual scene factory with no `Property value set multiple times`; initial two-screen run | Pending |
| Appearance regression | Normal/Theme/explicit materials; opacity 0/negative/positive; saved override round trips; compare screenshots | Pending |
| Material lifetime | Active, inactive, missing backdrop, screen moves, transitions, hide border, rebuild/teardown | Pending |
| GPU and cadence | Old accepted card rendering vs borders and child layers, 90 Hz p90/p99, GPU pass counts at 4K | Pending |
| Steam persistence | Historical achievements, owned-game playtime, current refresh, malformed-success responses | Partially operator-validated; live refresh pending |
| Windows/Linux packages | ISS opt-out semantics and Linux switches on fresh/install-over-existing | Pending |
| Temporary cleanup | Fix issues, record durable findings in existing owners, delete this file and its plan entry | Pending |

**Local source checks in this handoff:** 135 focused tests passed and one wizard-artwork test was deliberately deselected because normal GODZIPs do not contain `ui/assets/installer/SRPSSWizard.png`. A separate broader attempt reached 101 passes before Qt-fixture/import blockers (PySide6 is absent here). This is **not** a substitute for the full Windows `.venv` suite. The seven files in the most recent R-240 Steam playtime repair archive are byte-identical in this candidate.

### Confirmed handoff regression: stale shader binaries, 19 Nov (high priority)

- **Source-confirmed root cause of the repeat-wide border/material failure:** The GODZIP delivered after the successful Windows shader bake contained `surface_material.vert`/`.frag` updated for the border-material ABI but also shipped the exact **pre-material-border** `surface_material.vert.qsb` and `.frag.qsb` bytes from the original 18 Nov archive. A full-file GODZIP apply replaced locally regenerated, compatible packs with those old binaries. This is independent of the newly added volume-outline-width or Achievement Pulse guard setting and does not implicate native Vulkan/C++ work.
- Shader rebuild success **before** a GODZIP is applied does not protect against **later stale shader-file replacement**. Prior manifest SHA-256 checks proved that the archived QSB bytes were intact, not that they belonged to the GLSL included in the same archive. Tests of the GLSL/vertex uniform layout similarly cannot validate stale compiled QSBs.
- **Prevent recurrence in transfer:** `tools/godzip_foundry_core.py` now hard-excludes generated `.qsb` binaries from GODZIP export, preselection and apply. This is deliberate: compiled packs are local build outputs that must be regenerated from the transferred GLSL with the receiving machine's pinned Qt compiler. An existing older GODZIP containing a QSB must not overwrite a local copy, even when it appears changed/dirty. Test `tests/test_godzip_foundry_core.py` for export prohibition, v2 import default safety and attempted-apply rejection. `omission_means_delete=false` ensures locally compiled packs are not removed.
- **Required physical gate:** After applying this handoff, run `& .\.venv\Scripts\python.exe tools\regen_qrc.py --shaders; if ($LASTEXITCODE -ne 0) { throw 'Shader bake failed' }; & .\.venv\Scripts\python.exe tools\regen_qrc.py --shaders --check; if ($LASTEXITCODE -ne 0) { throw 'Shader verification failed' }` from the Windows checkout **before launching**. Compare startup before/after reveal, all material widget/card borders, framed Visualizer and Normal fast paths. If still broken after this gate, collect the new logs and actual baked QSB hashes; do not automatically attribute a second defect to the volume control.

## 1. Review order and ownership

1. **Integrity first:** use this archive as the single source. Verify `.godzip/manifest.json` `files[].size` and `sha256` against extracted bytes, verify `.godzip/workflow.md`, note manifest `debris`, compare with the named baseline. Never merge an older partial archive on top of this one. Confirm both Steam R-240 repair layers survive intact. Keep operator-owned `themes/`, `assets/` and references excluded as the GODZIP workflow specifies.
2. **Mechanical safety:** compile changed Python files; run `tools/regen_qrc.py --shaders` and `--check` in `.venv`; compile every QML presentation in the real Qt scene factory before attempting the screensaver. Check for duplicate property assignments *and* actual runtime bindings. There were already startup-blocking duplicate QML properties during this work, so pure string checks are not sufficient.
3. **Visual acceptance:** compare screenshots with the same theme, wallpaper, DPI, card geometry, material and opacity. Explicit material selections must not silently fall back; `Normal` paths should preserve existing appearance and have no extra loader cost. Confirm `Theme` inheritance and saved per-widget overrides separately. Check child material vs outer card and header legibility separately.
4. **Performance and teardown:** inspect *incremental* changes over accepted card materials, not the cost of the already-shipped card surface system. Measure after Settings and during idle, full-screen Visualizer with and without border, material-header/child combinations, wallpaper transitions and two displays at different DPR. Border-only Visualizer must be dormant at zero width and skip expensive interior sampling when active. Check node count and resource lifetime as well as GPU busy %.
5. **No scope drift:** native C++/QRhi migration priorities, authored visualizer preset logic, external providers and established theme semantics are not an excuse to rewrite the subsystem. Fix only defects proven by these checks. Store deferred findings under the correct existing Settings/material/Steam owner instead of native-core work.

## 2. High-value code and behaviour contracts

### Steam R-240: historical achievement and playtime repair

- Review `core/steam/achievement_pulse.py`, `_cache.py`, new `_history.py`, `tests/test_steam_achievement_history_regression.py`, and `Docs/Historical_Bugs/R-240_*.md`. `GetRecentlyPlayedGames` can return empty without implying prior achievements were deleted. Existing per-game records must remain discoverable after the rolling list vanishes. A nominal HTTP 200 with unusable game data must not silently overwrite last-good records.
- Lifetime playtime falls back from recent games to the shared owned-games cache and remembered history. Preserve last-good values, bounded fetches and the 24 h owned-games cache policy; no full library sweep per update. Verify fresh acquisitions and old achievements on a real account after the successful historical/playtime recovery already reported. Redact API keys and personal data from any debug evidence.

### Widget header, card, child and transport materials

- Review `OverlayCard.qml`, `OverlayWidget.qml`, `MaterialSurface.qml`, `ChildMaterialSurface.qml`, `BrandedHeader.qml`, `MediaTransportBar.qml`, `ExpandedVisualizerOverlays.qml`, `rendering/quick/widgets/{host,surface_material,media}.py`, `core/settings/surface_opacity.py`, and the shared shader. Material/opacity choices are `Normal`, `Theme` (inherit), and Glass/Acrylic/Frosted/Mica/Smoked. The header legibility panel is intentionally enabled for material headers; Media Control Bar and material borders have it disabled, independent of the Media *card* guard.
- Verify all nine branded-header consumers and all ordinary widget families share the display-scoped backdrop without creating per-widget captures. Loading a material only when needed, preserving a Normal fast path and explicit material demand when parent cards are Normal are critical. Test absence/reappearance of backdrops during first frame and transitions.
- Ordinary and fullscreen Media Control Bars use one semantic outline colour for separators and border, consistent separator stroke width/geometry, and the same global material choice/opacity. Ordinary bar has been visually accepted; fullscreen bar cannot currently sample the foreground Visualizer with the shared wallpaper-underlay capture. This remains a distinct planned follow-up, not evidence that stronger tint alone fixes the underlay. Check screenshot vs physical-display differences under DPI/HDR and actual drawing order.
- Media and fullscreen Now Playing artwork borders share 3.25 logical px. Verify 100/125/150/200% DPR and both left/right artwork alignment, especially Edit/Save, without moving the outer Media widget.

### Volume child: dual outlines and compositing

- `MediaPresentation.qml` has TWO separate bordered elements: `mediaAppVolumeTrack` and `mediaAppVolumeFill`. At partial level, the fill's outline occupies some of the same left/right border pixels as the parent track. Simply multiplying *both* alphas by 0.8 would yield approximately 0.96 final alpha where an opaque pair overlaps (`1 - (1 - 0.8)^2`), masking the requested 20% reduction.
- The intended correction keeps the original two-rectangle layout for Normal and uses one conditional, dormant-when-unused clipped outline owner when *card border material is genuinely active*. In that mode the track draws only above/below the fill bounds, the fill draws its own border, and each visible vertical region is outlined once using `effectiveVolumeOutlineColor` with 0.8 of authored alpha. Check level 0%, 1%, middle, 99%, 100%; CUSTOM track scale, resize, wheel, hover and opacity; round caps and seams near the fill edge. Inspect whether the extra clip nodes are acceptable; prefer a simpler single-path solution if screenshots or performance disagree.
- **Confirmed runtime regression, fixed in this handoff:** Material-border activation evaluated an inline clipping `Loader` whose geometry referenced `appVolumeFill.y` and `.height`, but the fill Rectangle had only `objectName`, not a QML `id`. Qt logged `ReferenceError: appVolumeFill is not defined` at `MediaPresentation.qml` lines 1141 and 1155 despite passing source-only tests. The fix declares `id: appVolumeFill` on the existing fill and adds a dedicated source regression assertion. Windows audit must exercise the **active** border-material path at partial mixer volume and confirm zero QML ReferenceErrors, not merely scene compilation.
- **Media volume outline width added after the initial audit (19 Nov):** the persisted `spotify_volume_border_width_px` defaults to the prior **2.5 logical px**, shared by the track, level fill and both clipped track outlines. Audit 0, 0.5, 1, 2.5, 5 and 8 px under Normal/material borders, 0/50/100% mixer level, resize/DPR, settings reload and QML runtime warnings. Confirm the M4 plan migrates it to the `media.volume.outline.width` semantic without freezing untouched users at 2.5 px. No shader or audio-runtime work belongs to this control.
- **Achievement Pulse material disc legibility:** the opt-in `progressCircleMaterial` now enables the child shader's legibility panel; this must not alter the unchecked/Normal original fill, percentage/ring artwork, or the outer card's independent guard. Validate over both dark and bright wallpaper and confirm the material surface remains dormant when disabled. This is an existing material child, not a new pass or backdrop owner.
- Do **not** change `appVolumeBorderColor` semantics or its saved swatch. Check that a material-enabled *parent card fill* with **Normal border** leaves the volume outline identical to legacy; only an actually active *material border* triggers the reduction. Missing backdrop must follow Normal.

### Widget material borders and Visualizer frame

- **Confirmed common shader ABI fault (2026-11-19, awaiting Windows validation):** `rendering/quick/qml/shaders/surface_material.frag` acquired eight border-material uniform fields between `panelCeiling` and `srpssConventions`, but `surface_material.vert` retained the old uniform block. Both `qsb` packs compile independently, so shader regeneration/`--check` can succeed even with mismatched `layout(std140, binding=0) uniform buf` declarations. The renderer can then receive inconsistent reflected layouts, potentially corrupting all card/child/border materials at once. This is consistent with the operator observing the entire scene for roughly one second before a dark layer appears during reveal, while the logs show `STARTUP_REVEAL` 13:20:41–13:20:44 and no fatal QML error. The correction restores exact cross-stage member/type/order parity in the vertex shader. `tests/test_qtquick_material_shader_abi_parity.py` asserts parity for every paired Qt shader and validates all `MaterialSurface.qml` property types. **Regenerate both QSBs, then verify a real normal-to-material activation, multiple ordinary widget families and the framed Visualizer on Windows before closing; the fade itself has not been shown faulty.**
- Audit `surface_material.frag`'s rounded-SDF ring coverage, shader uniform binding/ABI, normal flat-outline suppression only while material is truly active, font/text legibility independence, alpha premultiplication and `MaterialSurface` QML uniform declarations. Border may be 1/1.5/2/3/5 logical px, any authored radius, and must neither grow nor gain a silent minimum-width threshold. Confirm 4K, mixed DPR, light/dark themes and translucent wallpapers.
- Ordinary cards use their existing material shader; Visualizer paints live content above its card and therefore needs a separate **foreground border-only shader draw**, restricted to bordered display modes. `Fullscreen (Hide Borders)` is the **new-install default**, and must instantiate neither material-border work nor border-associated backdrop demand. Previously saved display styles must remain respected. In framed or Borders To Edge mode measure real GPU time/p90/p99 and whether the transparent interior really avoids the backdrop/texture/grain work.
- Distinguish source shader from shipped `.qsb` pack. The pinned Windows Qt toolchain must regenerate and verify GLSL/HLSL/MSL/SPIR-V translations; source-only tests, or “packs current” in a different checkout, do not demonstrate the actual handoff's binaries are current. Test real OpenGL/Vulkan paths. No per-border extra backdrop capture, worker thread or per-frame Python polling.

### Achievement Pulse progress circle

- Audit `AchievementPulsePresentation.qml`, `rendering/quick/widgets/achievement_pulse.py`, Steam Settings' circular checkbox and the `steam.progress.disc` semantic. Material applies to the **disc interior** only when chosen and a backdrop is active; the percentage, outer progress stroke, and Normal fallback retain their own appearance. Previous changes repeatedly passed source checks without producing the intended visible difference. Require before/after pixel evidence and prove the shader receives a valid backdrop, not just that the Loader's `active` expression is true.

### General UI, Settings frame and movement

- Audit `ui/settings_dialog.py`, `ui/settings_window_edge.py`, `ui/settings_window_placement.py`, `ui/tabs/widgets_tab_defaults.py`, `widgets_tab_media.py`, `widgets_tab_steam.py`, and `core/settings/default_settings.py`. Check 5.25 px Settings-only outer border and 6.25 radius, four invisible resize grips with no scratch lines, and the extra 2 px right inset. Studio's shared edge owner must remain unchanged.
- Settings window snapping/containment must happen at end-of-gesture/restored geometry, not on a new timer or in a paint loop. Verify negative-coordinate second monitors, taskbar work areas, 100–200% mixed DPI, restoring/moving between displays, maximize and constraints smaller than the documented 1280×760 minimum.
- Ensure Header/Media Bar/Border surface dropdowns and opacity sliders use one canonical global Style Override source, slider zero exactly reproduces its pre-adjustment appearance, and legacy saved Media `flat`/`normal` choices still load. Confirm opacity controls do not accidentally modify the outer card, text or child geometry.
- The previously observed `[PERF][UI_CALLBACK]` Settings single-shot (64–86 ms) and widget save (141 ms), plus `QFont::setPointSize(-1)`, are **Settings UI observations**, not established native-thread faults. Profile with proper Qt traces if reproducible; defer broad fixes to Settings ownership rather than detouring the live native renderer.

### Windows and Linux installer options

- Windows: `scripts/SRPSS_Installer.iss`, `scripts/SRPSS_MediaCenter_Installer.iss`. Ensure separate default-checked replacement tasks for themes and visualizer presets control BOTH `InstallDelete` and `[Files]`. Deselecting an asset family must neither delete nor overwrite it. Verify repeat-install task defaults and upgrades, onefile extraction-cache cleanup independence, and no changes to shared profile-directory ownership.
- Linux: `tools/linux_build.py` generates `install.sh` for MC and Screensaver. Check ordinary install replaces both, `--keep-themes`, `--keep-presets`, combined options preserve independently, and a missing release payload fails before deleting anything. Validate the bundled tarball's executable bits, manifests, shared directories and one real Linux MC smoke run if available.

## 3. Tests, evidence and stop conditions

**Windows venv, repository root, one-line PowerShell (no environment variables):**

```powershell
& .\.venv\Scripts\python.exe tools\regen_qrc.py --shaders; if ($LASTEXITCODE -ne 0) { throw 'Shader bake failed' }; & .\.venv\Scripts\python.exe tools\regen_qrc.py --shaders --check; if ($LASTEXITCODE -ne 0) { throw 'Shader verification failed' }; & .\.venv\Scripts\python.exe -m pytest -q tests/test_media_volume_outline_width_contract.py tests/test_fullscreen_visualizer_default_and_volume_outline.py tests/test_widget_border_material_and_media_separators.py tests/test_visualizer_border_material_and_transport_ink.py tests/test_general_material_child_opacity.py tests/test_branded_header_material_override.py tests/test_media_controls_surface_and_installer_choices.py tests/test_qml_header_binding_uniqueness_and_opacity_group.py tests/test_qtquick_material_shader_abi_parity.py tests/test_qtquick_all_presentation_compile_smoke.py tests/test_qtquick_media_presentation.py tests/test_qtquick_achievement_pulse_presentation.py tests/test_achievement_ring_material_and_shared_backdrop.py tests/test_settings_frame_and_child_material_20261118.py tests/test_settings_window_placement_policy_20261118.py tests/test_settings_dialog.py tests/test_steam_cache.py tests/test_steam_backend.py tests/test_steam_request_policy.py tests/test_steam_achievement_pulse.py tests/test_steam_achievement_history_regression.py tests/test_installer_contract.py tests/test_linux_build.py tests/test_linux_mc_build_contract.py
```

Run any repository-mandated broader gates through its existing runner (with Qt available). **Test counts are not acceptance by themselves**. Save evidence for: all-QML scene compilation, screenshots for Normal/Theme/five materials and opacity, 0/50/100% volume level, one/two-display startup and shutdown, and 90 Hz p90/p99/GPU pass cost with borders disabled vs enabled. Use `Docs/Architecture/Card_Surface_Materials.md`, the live `Current_Plan.md` 1.7b checklist and the existing historical bug index as governing references, not this temporary checklist.

**Stop/repair if:** a QML presentation fails initialization; Normal renders different; an inactive material still captures or draws; a shared backdrop is acquired twice; the material border paints over live Visualizer content or fails to respect zero width; stale QSB binaries or unresolved shader ABI; installed presets/themes get overwritten on unchecked options; an input/resize regression appears; a sustained 4K/90 Hz cadence penalty is attributable to optional material work. Fix in the owning code and add a reproducing regression test; do not hide failures by skipping tests or weakening test assertions.

## 4. Exit and cleanup

- [ ] Re-run the actual Windows shader bake and real QML startup tests after final source edits; repeat baseline screenshots and failure-path tests.
- [ ] Confirm no active GPU/Qt regression, material owner leaks, persistent-setting migration bug or installer data-loss path; record measured p90/p99, CPU/GPU deltas and DPI notes.
- [ ] Close or defer genuine findings in the *existing* material/UI/Steam task or historical issue, preserving accepted native-core ordering.
- [ ] **Delete `Docs/Temporary_Material_Surface_Audit_2026-11-19.md` and remove its dedicated `Current_Plan.md` checklist line** as the final act once the audit is actually done. Do not leave a second persistent plan.

## Appendix: generated cumulative file inventory

The following list is computed from first-versus-candidate archive bytes, excluding GODZIP metadata. `M` = existing file changed; `+` = new file. It is a navigation aid, not proof of correctness.

**Counts:** 44 modified, 17 added (including this temporary audit), 0 retired since baseline.

- `M` `core/settings/default_settings.py`
- `M` `core/settings/surface_opacity.py`
- `M` `core/steam/achievement_pulse.py`
- `M` `core/steam/achievement_pulse_cache.py`
- `+` `core/steam/achievement_pulse_history.py`
- `M` `Current_Plan.md`
- `M` `Docs/Historical_Bugs.md`
- `+` `Docs/Historical_Bugs/R-240_Achievement_Pulse_Rolling_Recent_Play_Cache_Erased_History_Discovery.md`
- `M` `engine/display_manager.py`
- `M` `rendering/quick/qml/AbandonmentIssuesPresentation.qml`
- `M` `rendering/quick/qml/AchievementPulsePresentation.qml`
- `M` `rendering/quick/qml/BrandedHeader.qml`
- `M` `rendering/quick/qml/ChildMaterialSurface.qml`
- `M` `rendering/quick/qml/ExpandedVisualizerOverlays.qml`
- `M` `rendering/quick/qml/FeedPresentation.qml`
- `M` `rendering/quick/qml/FriendPulsePresentation.qml`
- `M` `rendering/quick/qml/GamesYouFollowPresentation.qml`
- `M` `rendering/quick/qml/GmailPresentation.qml`
- `M` `rendering/quick/qml/MaterialSurface.qml`
- `M` `rendering/quick/qml/MediaPresentation.qml`
- `M` `rendering/quick/qml/MediaTransportBar.qml`
- `M` `rendering/quick/qml/OverlayCard.qml`
- `M` `rendering/quick/qml/OverlayWidget.qml`
- `M` `rendering/quick/qml/RedditPresentation.qml`
- `M` `rendering/quick/qml/shaders/surface_material.frag`
- `M` `rendering/quick/qml/SystemStatsPresentation.qml`
- `M` `rendering/quick/qml/VisualizerPresentation.qml`
- `M` `rendering/quick/scene_controller.py`
- `M` `rendering/quick/widgets/achievement_pulse.py`
- `M` `rendering/quick/widgets/host.py`
- `M` `rendering/quick/widgets/media.py`
- `M` `rendering/quick/widgets/surface_material.py`
- `M` `scripts/SRPSS_Installer.iss`
- `M` `scripts/SRPSS_MediaCenter_Installer.iss`
- `+` `tests/__pycache__/test_fullscreen_visualizer_default_and_volume_outline.cpython-313.pyc`
- `+` `tests/test_achievement_ring_material_and_shared_backdrop.py`
- `+` `tests/test_branded_header_material_override.py`
- `+` `tests/test_fullscreen_visualizer_default_and_volume_outline.py`
- `+` `tests/test_general_material_child_opacity.py`
- `+` `tests/test_media_controls_surface_and_installer_choices.py`
- `+` `tests/test_qml_header_binding_uniqueness_and_opacity_group.py`
- `M` `tests/test_qtquick_achievement_pulse_presentation.py`
- `+` `tests/test_qtquick_all_presentation_compile_smoke.py`
- `M` `tests/test_qtquick_media_presentation.py`
- `M` `tests/test_settings_forged_edge_over_content.py`
- `+` `tests/test_settings_frame_and_child_material_20261118.py`
- `M` `tests/test_settings_list_style_real_dialog.py`
- `+` `tests/test_settings_window_placement_policy_20261118.py`
- `+` `tests/test_steam_achievement_history_regression.py`
- `M` `tests/test_steam_achievement_pulse.py`
- `+` `tests/test_visualizer_border_material_and_transport_ink.py`
- `+` `tests/test_widget_border_material_and_media_separators.py`
- `M` `tools/linux_build.py`
- `M` `ui/settings_dialog.py`
- `M` `ui/settings_window_edge.py`
- `+` `ui/settings_window_placement.py`
- `M` `ui/tabs/widgets_tab_defaults.py`
- `M` `ui/tabs/widgets_tab_media.py`
- `M` `ui/tabs/widgets_tab_steam.py`
- `M` `ui/widget_visual_roles.py`
- `+` `Docs/Temporary_Material_Surface_Audit_2026-11-19.md` (temporary; remove after audit)

# SRPSS Documentation Index

Last updated: 2026-09-11

## Start here

```text
exact current source
-> Current_Plan.md
-> Spec.md / Docs/Contracts.md
-> relevant focused guide, guardrail, reference or future-work document
-> tests + physical evidence for the claim
```

`Current_Plan.md` owns current work admission and sequence. `Spec.md` owns durable product/architecture. Historical Bugs, Fossils and audits are evidence/negative controls, not current implementation authority.

## Directory roles

| Location | Role |
| --- | --- |
| `Docs/Architecture/` | durable architecture and subsystem ownership |
| `Docs/Guardrails/` | binding invariants and preflight contracts |
| `Docs/Guides/` | how-to/change procedures and authoring practice |
| `Docs/Reference/` | current lookup/reference material and harness routing |
| `Docs/Future_Work/` | admitted/deferred implementation plans |
| `Docs/Historical_Bugs/` | permanent regression/failed-method evidence |
| `Docs/Fossils/` | superseded decompositions and performance evidence retained for archaeology |
| `Docs/audits/` | point-in-time reconciliations/audit evidence |

Keep the small routing authorities at `Docs/` root: project overview, owner map, guardrail router, historical-bug router and TestSuite. The two `.sst` files in `Docs/` are generated/default evidence artifacts rather than prose documentation.

## Current authority routing

| Need | Read |
| --- | --- |
| current work / next sequence | `Current_Plan.md` |
| durable product / architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| project overview | `Docs/00_PROJECT_OVERVIEW.md` |
| runtime presentation architecture | `Docs/Architecture/Compositor_Architecture.md` |
| Settings theme / Acrylic / Glass / Theme Foundry | `Docs/Architecture/Settings_Theme_Architecture.md` |
| safety / guardrail router | `Docs/Guardrails.md` |
| presentation/cadence preflight | `Docs/Guardrails/Presentation_Change_Preflight.md` |
| Visualizer presentation invariants | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| performance optimization admission | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| runtime efficiency | `Docs/Guardrails/Runtime_Efficiency.md` |
| ordinary widget authoring | `Docs/Guides/10_WIDGET_GUIDELINES.md` |
| Visualizer change preflight | `Docs/Guides/Visualizer_Change_Checklist.md` |
| Visualizer reactivity authoring / new modes | `Docs/Guides/Visualizer_Reactivity_Authoring.md` |
| Visualizer current reference | `Docs/Reference/Visualizer_Reference.md` |
| transitions | `Docs/Guides/Transition_Change_Checklist.md` |
| defaults | `Docs/Guides/Defaults_Guide.md` |
| logging / Qt-QML observability | `Docs/Guides/Logging_Guide.md` + `Docs/Guides/Qt_QML_Observability.md` |
| documentation maintenance | `Docs/Guides/Documentation_Maintenance.md` |
| test inventory / retirement | `Docs/TestSuite.md` |
| harness commands | `Docs/Reference/Harness_Index.md` |
| historical bug routing | `Docs/Historical_Bugs.md` then `Docs/Historical_Bugs/README.md` |
| deferred cleanup | `Future_Cleanup.md` |
| broad deferred features | `Future_Work.md` |
| operator-activated future checklists | `FWPlan.md` |

## Visualizer read order

For a new mode or any meaningful reactivity change, read `Docs/Guides/Visualizer_Reactivity_Authoring.md` before inventing source math. It consolidates the proven Bubble/Spectrum/Sphere lessons around raw vs smoothed signals, pre-AGC headroom, loud-passage contrast, admission vs reward, consume-once events, saturation/blow-out, geometry-vs-gain mistakes, cadence and validation. Then use `Docs/Guides/Visualizer_Change_Checklist.md`, the presentation guardrail, and mode-specific evidence as applicable.

## Settings themes

`Docs/Architecture/Settings_Theme_Architecture.md` owns SettingsThemeSpec schema v6. `about.art.liquid` recolours only the explicitly masked About liquid/background field; every shipped Settings theme seeds it from that theme's primary chrome accent (`chrome.outer_border` RGB at full alpha). Schema-v5 themes migrate that role from the same primary accent. Widget Theme schema/precedence remains separate.

## Complete documentation inventory

### Repository root

- `Current_Plan.md` — Current Plan — Active Work
- `Future_Cleanup.md` — Future Cleanup — Active Deletion / Compatibility Ledger
- `Future_Work.md` — Future Work
- `FWPlan.md` — Future Work implementation plan
- `Index.md` — SRPSS Documentation Index (this file)
- `README.md` — ShittyRandomPhotoScreenSaver (SRPSS)
- `Spec.md` — SRPSS Specification
- `SRPSS_SettingsAbout_DocOrganization_HANDOFF_2026-09-11.md` — SRPSS Settings/About + documentation organization handoff — 2026-09-11
- `SRPSS_VoxelSphere_AcceptedExperimental_Polish_HANDOFF_2026-09-10.md` — SRPSS Voxel Sphere — Accepted Experimental Polish Handoff — 2026-09-10

### Docs root routing authorities

- `Docs/00_PROJECT_OVERVIEW.md` — Project Overview
- `Docs/Contracts.md` — Contracts — Current Owner Map
- `Docs/Guardrails.md` — SRPSS Guardrails
- `Docs/Historical_Bugs.md` — Historical Bugs
- `Docs/TestSuite.md` — Test Suite Guide

### Architecture

- `Docs/Architecture/Compositor_Architecture.md` — Runtime Presentation Architecture
- `Docs/Architecture/Settings_Theme_Architecture.md` — Settings Theme Architecture

### Guardrails

- `Docs/Guardrails/Bubble_Temporal_Fidelity.md` — Bubble Temporal Fidelity Contract
- `Docs/Guardrails/Performance_Optimization_Contract.md` — Performance Optimization Contract
- `Docs/Guardrails/Presentation_Change_Preflight.md` — Presentation / Cadence Change Preflight
- `Docs/Guardrails/Runtime_Efficiency.md` — Runtime Efficiency / Change Safety Guardrails
- `Docs/Guardrails/Visualizer_Presentation.md` — Visualizer Presentation Guardrails

### Guides

- `Docs/Guides/10_WIDGET_GUIDELINES.md` — Ordinary Widget Authoring Guide
- `Docs/Guides/Custom_Style_Implementation.md` — Custom Style Implementation
- `Docs/Guides/Defaults_Guide.md` — Defaults Guide
- `Docs/Guides/Documentation_Maintenance.md` — Documentation Maintenance
- `Docs/Guides/Logging_Guide.md` — Logging Guide
- `Docs/Guides/Ordinary_Widget_Resize_Capture.md` — Ordinary widget resize capture harness
- `Docs/Guides/Qt_QML_Observability.md` — Qt / QML Observability Contract
- `Docs/Guides/Transition_Change_Checklist.md` — Transition Change Checklist
- `Docs/Guides/Visualizer_Change_Checklist.md` — Visualizer Change Checklist
- `Docs/Guides/Visualizer_Reactivity_Authoring.md` — Visualizer Reactivity Authoring Guide

### Reference

- `Docs/Reference/Harness_Index.md` — Harness Index
- `Docs/Reference/Steam_Data_Feasibility.md` — Steam Data Feasibility
- `Docs/Reference/Visualizer_Reference.md` — Visualizer Reference

### Future Work

- `Docs/Future_Work/Bubble_Aspect_And_Presentation_Decomposition.md` — Bubble aspect response and presentation cost
- `Docs/Future_Work/Edit_Layout_Live_Commit.md` — Live Edit commit (retired / historical reference)
- `Docs/Future_Work/Ordinary_Widget_Resize_Normalization.md` — Ordinary Widget Resize Normalization (retired / historical reference)
- `Docs/Future_Work/Settings_Dark_QSS_Retirement.md` — Settings `dark.qss` Retirement
- `Docs/Future_Work/Sphere_Visualizer_Decomposition.md` — Voxel Sphere — accepted experimental preservation and future migration gate
- `Docs/Future_Work/Steam_Friend_Pulse.md` — Steam Friend Pulse — definite current-plan widget proposal/decomposition
- `Docs/Future_Work/System_Stats_Widget.md` — System Stats — conditional current-plan widget proposal/decomposition
- `Docs/Future_Work/SST_9of10_Settings.md` — SST 9/10 Settings — closeout/reference checklist (Strategy B)
- `Docs/Future_Work/Visualizer_Replay_Reactivity_Floor.md` — Visualizer replay reactivity floor (landed regression reference)
- `Docs/Future_Work/Visualizer_Visual_Regression_Recovery.md` — Visualizer visual regression recovery (historical evidence)
- `Docs/Future_Work/Widget_Interaction_Glow_Decomposition.md` — Widget interaction glow (retired / historical reference)

### Fossils

- `Docs/Fossils/Performance_Evidence/Acceptance-08_19-15_17-WorkerQuantized-REJECTED.md` — Acceptance Evidence — 2026-08-19 15:15–15:17 — Quantized Dedicated Worker — REJECTED
- `Docs/Fossils/Performance_Evidence/Acceptance-08_19-17_10-RepairedWorker-FAILED.md` — Acceptance Evidence — 2026-08-19 17:05–17:10 — Repaired Dedicated Worker — FIRST INSTALLED FAILURE
- `Docs/Fossils/Performance_Evidence/Acceptance-08_19-19_08-ccb63542-FAILED.md` — Acceptance Evidence — 2026-08-19 19:04–19:08 — Second Installed Run — FAILED
- `Docs/Fossils/Performance_Evidence/Acceptance-08_19-20_02-8ac2421e-HARD_FAILED.md` — Acceptance Evidence — 2026-08-19 19:59–20:02 — Third Installed Run — HARD FAILURE
- `Docs/Fossils/Performance_Evidence/Acceptance-08_20-00_05-82a14b31-Heavy-REFERENCE.md` — Acceptance Evidence — 2026-08-20 00:03–00:05 — 82a14b31 Heavy Load — REFERENCE FAILURE CLASS
- `Docs/Fossils/Performance_Evidence/Acceptance-08_20-00_20-82a14b31-Light-REFERENCE.md` — Acceptance Evidence — 2026-08-20 00:15–00:20 — 82a14b31 Light Load — REFERENCE
- `Docs/Fossils/Performance_Evidence/Acceptance-08_20-13_03-Diagnostic-Long-Soak.md` — Acceptance Evidence — 2026-08-20 04:46–13:03 — Diagnostic Long Soak — LIFECYCLE PASS / PRESENTATION DIRECTION REINFORCED
- `Docs/Fossils/Performance_Evidence/Acceptance_Record_Template.md` — Acceptance Evidence — YYYY-MM-DD HH:MM — <short name> — PASS/FAILED
- `Docs/Fossils/Performance_Evidence/Architecture_Comparison-08_19-22_49.md` — Architecture Comparison — 2026-08-19 22:49 SAST
- `Docs/Fossils/Performance_Evidence/Baseline-42033c84-AcceptedReference.md` — Baseline — 42033c84 — Accepted Rollback / Fidelity Reference
- `Docs/Fossils/Performance_Evidence/Hypothesis-K-cba50b50-GSMTC-Wait.md` — Hypothesis Record — Slice K / cba50b50 — Synchronous GSMTC Wait
- `Docs/Fossils/Performance_Evidence/Hypothesis-L-10f1c3c4-Feedback-Paint.md` — Hypothesis Record — Slice L / 10f1c3c4 — Feedback-Only Parent Paint Fast Path
- `Docs/Fossils/Performance_Evidence/P2_Performance_Ledger.md` — P2 Performance Evidence Ledger
- `Docs/Fossils/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` — Qt Quick P0 common-workload comparison — 2026-08-20
- `Docs/Fossils/Performance_Evidence/Raw_Log_Manifest.md` — Raw Log Manifest — P2 Evidence
- `Docs/Fossils/Performance_Evidence/README.md` — SRPSS Performance Evidence — Rules and Usage
- `Docs/Fossils/Performance_Evidence/Reference-08_19-15_29-PreDedicatedRuntime.md` — Performance Reference — 2026-08-19 15:27–15:29 — Pre-Dedicated-Runtime Comparison
- `Docs/Fossils/Rejected_Card_Material_Experiments_2026-09-02.md` — Rejected Qt Quick Runtime Card-Material Experiments — 2026-09-02
- `Docs/Fossils/SRPSS_Steam_Widget_Family_Implementation_Plan.md` — SRPSS Steam Widget Family — Quick-Era Reference Index
- `Docs/Fossils/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md` — Visualizer Mode Modularization + Settings Tab — Decomposition
- `Docs/Fossils/Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md` — Visualizer Reactivity Audit — Historical vs Current Source Evidence Matrix

### Audits

- `Docs/audits/Post_Material_Rollback_Documentation_Reconciliation_2026-09-03.md` — Post-Material-Rollback Documentation Reconciliation — 2026-09-03

### Historical Bugs

- `Docs/Historical_Bugs/A-01_Settings_Dialog_Placeholder_Investigation.md` — A-01 — MAJOR VISUAL BUG: Settings Dialog Flicker / Placeholder Regression — Historical Investigation Archived
- `Docs/Historical_Bugs/A-02_Visualizer_Crossover_Persistence_Blob.md` — A-02 — 2026-02-24 — Spotify Visualizer "Crossover Persistence" (Blob muted after mode switch)
- `Docs/Historical_Bugs/A-03_Settings_Dialog_Flicker_Resolved_Archive.md` — A-03 — 2026-03-22 — Settings Dialog Flicker / Placeholder Regression (Resolved) - USER NOTE: UNRESOLVED BUT LOW PRIORITY NOW. SEE DUPLICATION OF THIS ISSUE IN THIS VERY DOCUMENT.
- `Docs/Historical_Bugs/A-04_MC_Keyboard_Focus_Ctrl_Halo_Archive.md` — A-04 — 2026-03-22 — MC Keyboard Focus / Ctrl Halo Interaction Regressions (Historical Partial Fixes Archived; superseded by [U-05](U-05_MC_Keyboard_Focus_Ctrl_Halo.md))
- `Docs/Historical_Bugs/A-05_Blob_Ghost_Pulse_Investigation.md` — A-05 — 2026-03-22 — Blob Ghost/Pulse Investigation (Resolved Subsystems Archived)
- `Docs/Historical_Bugs/A-06_Visualizer_Mode_Preset_Bleed_Investigation.md` — A-06 — 2026-05-06 — Visualizer Runtime Mode/Preset Bleed Survived Audio Resets (Archived Investigation; superseded by R-22)
- `Docs/Historical_Bugs/Defaults_Canonical_Schema_Dedup_2026-09-06.md` — Historical Bug — Canonical defaults schema drift and duplicate authority
- `Docs/Historical_Bugs/Installer_Reset_Reimported_Legacy_QSettings_2026-09-06.md` — Installer Reset Could Re-import Legacy QSettings — 2026-09-06
- `Docs/Historical_Bugs/R-01_Settings_Shell_Outer_Border_Radius.md` — R-01 — 2026-04-09 — Settings Shell Outer Border Radius / Corner Bleed (Resolved With Caveats)
- `Docs/Historical_Bugs/R-02_Reddit_Helper_Link_Handoff.md` — R-02 — 2026-04-08 / 2026-04-09 — Reddit Helper Link Handoff Fails In Real Screensaver Runtime (Resolved)
- `Docs/Historical_Bugs/R-03_Sine_Idle_Paused_Motion.md` — R-03 — 2026-04-18 — Sine Idle Motion Dead/Flat During Paused State (Resolved)
- `Docs/Historical_Bugs/R-04_Visualizer_Curated_Preset_Custom_Authority.md` — R-04 — 2026-04-18 — Visualizer Curated Preset Selection Reused Custom Runtime Values (Resolved)
- `Docs/Historical_Bugs/R-05_Visualizer_Preset_Slot_Label_Target.md` — R-05 — 2026-04-18 — Visualizer Preset Slot Label Mismatched Edit Target (Resolved)
- `Docs/Historical_Bugs/R-06_Visualizer_Preset_Merge_Pollution.md` — R-06 — 2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE) (Resolved)
- `Docs/Historical_Bugs/R-07_Startup_Fade_Visualizer_Secondary_Stage.md` — R-07 — 2026-03-28 — Startup Fade / Visualizer Secondary-Stage Ownership Split (Resolved)
- `Docs/Historical_Bugs/R-08_Pixel_Shift_Visualizer_Bleed_Through.md` — R-08 — 2026-02-26 / 2026-03-05 — Pixel Shift Visualizer Bleed-Through (Resolved)
- `Docs/Historical_Bugs/R-09_Settings_Input_Fill_QSS_Specificity.md` — R-09 — 2026-03-05 — Settings Spinbox/LineEdit Fill Regression (Resolved)
- `Docs/Historical_Bugs/R-10_Deleted_QObject_Provider_Switch_Callback.md` — R-10 — 2026-03-06 — Widget C++ Object Already Deleted on Provider Switch (Resolved)
- `Docs/Historical_Bugs/R-11_Visualizer_Preset_Tooling_Regression.md` — R-11 — 2026-03-14 — Visualizer Preset Tooling Regression (Resolved)
- `Docs/Historical_Bugs/R-12_Runtime_Custom_Preset_Cycling.md` — R-12 — 2026-04-09 — Runtime Custom Slot Replaced While Cycling Presets (Resolved)
- `Docs/Historical_Bugs/R-13_Sine_Oscilloscope_Lines_4_6_Persistence.md` — R-13 — 2026-04-13 — Visualizer Sine/Oscilloscope Lines 4-6 Settings Never Persisted (Resolved)
- `Docs/Historical_Bugs/R-14_Blob_Inward_Liquid_Overlay_Handoff.md` — R-14 — 2026-04-17 — Blob Inward-Liquid Runtime Handoff Broke GL Overlay Push (Resolved In Code, Visual Validation Pending)
- `Docs/Historical_Bugs/R-15_Frozen_Curated_Preset_Root.md` — R-15 — 2026-04-18 — Frozen Curated Presets Silently Fell Back to Onefile Tree (Resolved)
- `Docs/Historical_Bugs/R-16_One_Dir_Frozen_Detection_And_Slot_Drift.md` — R-16 — 2026-04-18 — One-Dir Runtime Misdetected As Script + Curated Slot Drift (Resolved)
- `Docs/Historical_Bugs/R-17_Goo_No_Gap_Artifact_Regression.md` — R-17 — 2026-04-18 — Goo No-Gap/Artifact Regression Family (Resolved In Dev-Gated Path)
- `Docs/Historical_Bugs/R-18_Settings_Dialog_Taskbar_Ghost.md` — R-18 — 2026-04-23 — Settings Dialog Flicker / Taskbar Ghost (`Qt691QWindowIcon`) (Resolved)
- `Docs/Historical_Bugs/R-21_Visualizer_Painted_Card_GL_Boundary.md` — R-21 — 2026-05-04 — Visualizer Painted-Card GL Content Escaping Card Boundary (Resolved)
- `Docs/Historical_Bugs/R-22_Visualizer_Runtime_State_Bleed.md` — R-22 — 2026-05-07 — Spotify Visualizer State Bleed: Runtime Bar Arrays Not Cleared During Mode Transitions (Resolved)
- `Docs/Historical_Bugs/R-23_Custom_Edit_Surface_Geometry_Regression.md` — R-23 — 2026-05-24 / 2026-05-25 — CUSTOM Edit Mode Global Shell/Grid/Z-Order/Geometry Regression Family (Resolved)
- `Docs/Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md` — R-24 — 2026-05-25 — Retired Overlay-Effect Cache-Busting Path Still Driving Menu/Focus/Display Churn (Resolved)
- `Docs/Historical_Bugs/R-25_Spectrum_Solid_Bar_Hysteresis.md` — R-25 — 2026-06-13 — Spectrum Solid-Bar Boundary Flicker / Robotic Snap Follow-Up (Resolved)
- `Docs/Historical_Bugs/R-26_Visualizer_Custom_Display_Participation.md` — R-26 — 2026-06-18 — Visualizer CUSTOM Display-Participation Fallback / Duplicate Owner From Startup And Sleep-Wake Participation Churn (Partial / Awaiting Validation)
- `Docs/Historical_Bugs/R-27_Pending_Paint_Requeue_UI_Pressure.md` — R-27 — 2026-06-27 — Pending-Paint Requeue Perf Regression / UI Pressure Trap (Resolved)
- `Docs/Historical_Bugs/R-28_Settings_Last_Moved_Deleted_QObject.md` — R-28 — 2026-06-30 — Settings Slider Last-Moved Weakref Touched Deleted Qt Wrapper (Resolved In Code, Runtime Validation Pending)
- `Docs/Historical_Bugs/R-29_Reddit_Refresh_Provider_Authority.md` — R-29 — 2026-06-30 — Reddit Refresh Cadence And Provider Fallback Authority (Resolved In Code, Runtime Validation Pending)
- `Docs/Historical_Bugs/R-30_Adaptive_Timer_Shutdown_Ownership.md` — R-30 — 2026-07-01 — Adaptive Timer Ownership Drop Left Python Process Alive After App Exit (Resolved In Code, Runtime Validation Pending)
- `Docs/Historical_Bugs/R-31_ImageWorker_Display_Replacement_On_Rejection.md` — R-31 — 2026-07-10 — Worker-Rejected Display Image Masqueraded As Multi-Monitor Compositor Loss (Resolved In Code, Runtime Validation Pending)
- `Docs/Historical_Bugs/R-32_WidgetsTab_Lazy_Save_Hydration_Guard.md` — R-32 — 2026-07-10 — Lazy WidgetsTab Save Treated Expected Unbuilt Sections As Guard Violations (Resolved In Code, Runtime Validation Pending)
- `Docs/Historical_Bugs/R-33_Defaults_SST_Regeneration_Safety.md` — R-33 — 2026-07-10 — Defaults SST Regeneration Reached Installed Profiles And Canonicalized Machine Layout Slots (Resolved In Code)
- `Docs/Historical_Bugs/R-34_Blank_Weather_Location_Lifecycle_Fallback.md` — R-34 — Blank Weather Location Entered Lifecycle Error/Fallback And Collapsed Its Card
- `Docs/Historical_Bugs/R-35_Steam_Family_Master_Runtime_Gate.md` — R-35 — Steam Family Master Hid Settings But Did Not Gate Runtime Cards
- `Docs/Historical_Bugs/R-36_Blob_Mighty_Shaped_Contour_Motion.md` — R-36 — Blob Mighty / Shaped Contours Reached Healthy Audio But Lost Visible Motion Inside Blob-Local Geometry
- `Docs/Historical_Bugs/R-37_Abandonment_Rotation_Expiry_And_Sequential_Selection.md` — R-37 — Abandonment Rotation Expiry Was Silently Dropped And Selection Walked Archive Order
- `Docs/Historical_Bugs/R-38_Achievement_Pulse_Unlock_Ranking_And_Count_Elision.md` — R-38 — Achievement Pulse Ranked Recent Play Instead Of Recent Unlock And Elided Unlocked Counts
- `Docs/Historical_Bugs/R-39_Abandonment_Automatic_Rotation_Artwork_Hydration.md` — R-39 — Abandonment Automatic Rotation Lost Uncached Selected Artwork
- `Docs/Historical_Bugs/R-40_Abandonment_Shared_Steam_Refresh_Authority.md` — R-40 — Abandonment Ignored The Shared Steam Refresh Interval
- `Docs/Historical_Bugs/R-41_Gmail_OAuth_Callback_Thread_Ownership.md` — R-41 — Gmail OAuth Callback Server Escaped ThreadManager Lifecycle Ownership
- `Docs/Historical_Bugs/R-42_Abandonment_Selected_Game_Achievement_Acquisition.md` — R-42 — Abandonment Achievement Shelves Had No Selected-Game Acquisition Path
- `Docs/Historical_Bugs/R-43_Foundry_Modal_Colour_Editor_Lifetime.md` — R-43 — Defaults Foundry Modal Colour Picker Destroyed Its Delegate Editor
- `Docs/Historical_Bugs/R-44_Gmail_Custom_Text_Balance_Authority.md` — R-44 — Gmail CUSTOM Resize Payload Overrode Live Text Balance
- `Docs/Historical_Bugs/R-45_Clock_Custom_Geometry_Authority.md` — R-45 — Clock CUSTOM Payload Overrode Settings Mode To Preserve Geometry
- `Docs/Historical_Bugs/R-46_Blob_Visualizer_Retirement.md` — R-46 — Failed Blob Visualizer Retired End To End
- `Docs/Historical_Bugs/R-47_Oscilloscope_Diagnostic_NameError.md` — R-47 — Oscilloscope Diagnostic Cleanup Broke Every Frame Push
- `Docs/Historical_Bugs/R-48_Clock_Per_Display_Mode_Override.md` — R-48 — Clock Double-Click Replaced Per-Display Mode With Shared Setting
- `Docs/Historical_Bugs/R-49_Settings_Edit_Hide_Only_Runtime_Retention.md` — R-49 — Settings/Edit Hide-Only Pause Retained Old GL Runtime And Shadowed Cleanup
- `Docs/Historical_Bugs/R-50_Count_Only_Resource_Retention.md` — R-50 — Count-Only Image/Texture Retention And Unbounded Prefetch Backlog
- `Docs/Historical_Bugs/R-51_Shared_Shader_Cache_Deletion_Ownership.md` — R-51 — Phase 3 Shared Shader Cache Gave Two Compositors One Deletion Identity
- `Docs/Historical_Bugs/R-52_ImageWorker_Shared_Memory_Retention.md` — R-52 — ImageWorker Retained Every Shared-Memory Frame Until Process Exit
- `Docs/Historical_Bugs/R-53_Runtime_Recreation_Ownership_And_Memory.md` — R-53 — Retired Runtime Generations Survived Full Edit/Settings Recreation
- `Docs/Historical_Bugs/R-54_Bubble_Cadence_Gate.md` — R-54 — Phase 5 Bubble Cadence Gate Delayed And Flattened Visible Reactions
- `Docs/Historical_Bugs/R-55_Spectrum_Presentation_Smoothing.md` — R-55 — Spectrum Paint-Local Smoothing Created A Second Cadence
- `Docs/Historical_Bugs/R-56_Settings_Dialog_Deleted_Wrapper_Retouch.md` — R-56 — Settings Close Path Retouched An Already-Deleted Dialog Wrapper
- `Docs/Historical_Bugs/R-57_Image_Prefetch_Selected_Index_Order.md` — R-57 — Scaled Prefetch Popped Selection Order Instead Of Descending Indices
- `Docs/Historical_Bugs/R-58_Visualizer_Move_To_Custom_Preset_Authority.md` — R-58 — Move To Custom Copied Stale Backing Values Instead Of The Curated Runtime State
- `Docs/Historical_Bugs/R-59_Runtime_Settings_Request_Input_Stack_Teardown.md` — R-59 — Frozen Settings/Edit Recreation Retained Compiled Bound Methods
- `Docs/Historical_Bugs/R-60_ImagePresenter_DPR_Texture_Identity.md` — R-60 — ImagePresenter DPR Split Rekeyed The Retained Current Texture
- `Docs/Historical_Bugs/R-61_Settings_Glass_Layered_HWND_Backdrop_Mismatch.md` — R-61 — Settings Glass Used The Wrong Composition Family For A Layered QWidget
- `Docs/Historical_Bugs/R-61_Visualizer_Presentation_Bound_To_Transition_Timer.md` — R-61 — Visualizer Presentation Bound To The Transition-Scoped Render Timer
- `Docs/Historical_Bugs/R-61B_Visualizer_Presentation_Bound_To_Transition_Timer.md` — R-61B — Visualizer Presentation Bound To The Transition-Scoped Render Timer
- `Docs/Historical_Bugs/R-62_Transition_Scoped_Presentation_Deferral_Bubble_Regression.md` — R-62 — Transition-Scoped Presentation Deferral Degraded Bubble
- `Docs/Historical_Bugs/R-63_Display1_Black_Flash_Fullscreen_Flip_Promotion.md` — R-63 — Display-1 Black Flash from Fullscreen-Flip PresentMode Transitions
- `Docs/Historical_Bugs/R-64_Native_Cursor_Halo_Scene_Pressure.md` — R-64 — Retained Cursor Halo Turned Passive Pointer Motion Into Scene Pressure
- `Docs/Historical_Bugs/R-65_Transactional_Image_Admission_And_Prefetch_Latch.md` — R-65 — Image Change Admission Could Bare-Snap And Prefetch Could Strand Across Recreation
- `Docs/Historical_Bugs/R-66_Media_Event_Ownership_Replaced_Fast_Polling.md` — R-66 — Media Runtime Fast Polling Replaced By Provider Event Ownership
- `Docs/Historical_Bugs/R-67_Custom_Resize_Reentry_Absolute_Scale.md` — R-67 — CUSTOM Resize Re-entry Rebased Persisted Geometry And Could Compound Shrink
- `Docs/Historical_Bugs/R-68_Visualizer_Custom_Presentation_Authority_Rebase.md` — R-68 — Visualizer CUSTOM Working Geometry Rejected Fresh Logical Snapshots
- `Docs/Historical_Bugs/R-69_Bubble_Extreme_Viewport_Global_Radius_Compression.md` — R-69 — Bubble Extreme-Viewport Global Radius Compression Suppressed Reactivity
- `Docs/Historical_Bugs/R-70_Gmail_Custom_Uniform_Scale_Preferred_Dimension_Split.md` — R-70 — Gmail CUSTOM Uniform Scale Needed Different Width And Height Shell Semantics
- `Docs/Historical_Bugs/R-71_Visualizer_Audio_Per_Frame_Task_And_DSP_State_Allocation.md` — R-71 — Visualizer Audio Per-Frame Task And DSP-State Allocation Drove GC Pressure
- `Docs/Historical_Bugs/R-72_Production_Shutdown_Imported_Dead_Perf_Parser.md` — R-72 — Production Shutdown Imported A Dead Performance Parser
- `Docs/Historical_Bugs/R-73_Quick_Card_Shadow_Extra_Offset_Translation_And_Visualizer_Omission.md` — R-73 — Quick card-shadow Extra Offset translated the whole shadow; Visualizer missed global shadow ownership
- `Docs/Historical_Bugs/R-74_Quick_Card_Shadow_Sibling_Subtree_Overpaint.md` — R-74 — Quick card shadows could overpaint sibling widget content
- `Docs/Historical_Bugs/R-75_Superseded_Compute_Callback_Released_Held_Serial_Lane_Slot.md` — R-75 — A superseded audio-analysis callback could release a serial-lane slot a newer owner held
- `Docs/Historical_Bugs/R-76_Spectrum_Viewport_Temporal_Scaling_Axis_And_Solid_Domain.md` — R-76 — Spectrum viewport temporal scaling used the wrong axis and the wrong owner
- `Docs/Historical_Bugs/R-77_Post_Phase_I_QWidget_Runtime_Residue_Required_Coordinated_Retirement.md` — R-77 — Post-Phase-I QWidget/runtime residue required coordinated retirement
- `Docs/Historical_Bugs/README.md` — Historical Bug Records
- `Docs/Historical_Bugs/Runtime_Card_Backdrop_Materials_Rejected_2026-09-02.md` — Runtime Card Backdrop Materials Rejected — 2026-09-02
- `Docs/Historical_Bugs/Theme_Defaults_Split_Authority_2026-09-06.md` — Historical Bug — Theme defaults split authority
- `Docs/Historical_Bugs/U-02_Bubble_Blob_Signal_Contract.md` — U-02 — 2026-04-10 / 2026-04-25 — Bubble / Blob Signal-Contract Trap: Dead Smoothed Hold vs Raw-Energy Blowout (Resolved)
- `Docs/Historical_Bugs/U-03_Spectrum_Vocal_Lane_Migration.md` — U-03 — 2026-04-08 / 2026-04-25 — Non-Mirrored Spectrum Vocal Lane Still Missing After Claimed Landing (Resolved)
- `Docs/Historical_Bugs/U-04_Settings_Dialog_Flicker_Investigation_Archive.md` — U-04 — 2026-04-21 — Settings Dialog Flicker / Taskbar Ghost (Investigation Archive; Superseded by [R-18](R-18_Settings_Dialog_Taskbar_Ghost.md))
- `Docs/Historical_Bugs/U-05_MC_Keyboard_Focus_Ctrl_Halo.md` — U-05 — 2026-04-08 — MC Keyboard Focus / Ctrl Halo Runtime Input Family Reopened (Unresolved)
- `Docs/Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md` — U-06 — 2026-04-30 — Multi-Monitor MC Shadow Cache Corruption On Focus Loss (Unresolved)
- `Docs/Historical_Bugs/U-07_Bubble_Loud_Path_Oracle_Drift.md` — U-07 — 2026-06-05 — Bubble Loud-Path Oracle Drift / Multi-Tweak Overfit Family (Resolved)
- `Docs/Historical_Bugs/U-08_Custom_Replay_Shrink_Minimum_Constraints.md` — U-08 — 2026-06-06 / 2026-06-12 — CUSTOM Runtime Replay Shrink Failure / Minimum-Constraint Reassertion Drift (Resolved)
- `Docs/Historical_Bugs/U-09_Visualizer_Custom_Runtime_Shape_Poison.md` — U-09 — 2026-06-13 / 2026-06-29 — Visualizer CUSTOM Runtime Shape Poison / Post-Replay Geometry Authority Split (Watchlist With Stale-Bucket Repair)
- `Docs/Historical_Bugs/U-10_Oscilloscope_Strobe_Waveform_Ghost_Contract.md` — U-10 — 2026-06-28 / 2026-06-29 — Oscilloscope Visual Strobe / Waveform-Ghost-Transient Contract Drift (Resolved)
- `Docs/Historical_Bugs/Visualizer_Builder_Bucket_State_Schema_Drift_2026-09-10.md` — Visualizer Builder Bucket-State Schema Drift — 2026-09-10
- `Docs/Historical_Bugs/Visualizer_Cross_Display_Split_Ownership_2026-09-05.md` — Historical bug — Visualizer cross-display split ownership (2026-09-05)
- `Docs/Historical_Bugs/Visualizer_Experimental_Mode_Settings_Family_Contract.md` — Historical Bug — Experimental Visualizer mode key-family contract escaped shared consumers
- `Docs/Historical_Bugs/Visualizer_Preset_Sparse_Catalog_And_Failed_Body_Leak_2026-09-10.md` — Visualizer Preset Sparse Catalog + Failed Settings Body Leak — 2026-09-10
- `Docs/Historical_Bugs/Voxel_Sphere_Absolute_Loudness_Pinned_Particle_Density_2026-09-10.md` — Voxel Sphere — Absolute Loudness Pinned Particle Density — 2026-09-10
- `Docs/Historical_Bugs/Voxel_Sphere_Clamped_Event_Strength_Was_Not_Particle_Velocity_2026-09-10.md` — Voxel Sphere — Clamped Event Strength Was Not Particle Velocity (2026-09-10)
- `Docs/Historical_Bugs/Voxel_Sphere_Global_Intake_Decay_Was_Not_Velocity_2026-09-10.md` — Voxel Sphere — Global Intake Decay Was Not Velocity (2026-09-10)
- `Docs/Historical_Bugs/Voxel_Sphere_Ingress_Continuity_2026-09-10.md` — Voxel Sphere Ingress Population Continuity — 2026-09-10
- `Docs/Historical_Bugs/Voxel_Sphere_Playback_State_Is_Not_Ingress_Authority_2026-09-10.md` — Voxel Sphere — Playback State Is Not Ingress Authority (2026-09-10)
- `Docs/Historical_Bugs/Voxel_Sphere_Pseudo_Material_Contamination_2026-09-09.md` — Voxel Sphere pseudo-material contamination — 2026-09-09

## Non-prose documentation artifacts

- `Docs/SRPSS_Settings_Screensaver.sst` — checked-in Settings/default artifact.
- `Docs/SRPSS_Settings_Screensaver_MC.sst` — checked-in MC Settings/default artifact.

Historical/fossil/audit documents may deliberately contain old paths or owner names because they record the state at the time. Do not rewrite those bodies merely to make history read like current architecture.

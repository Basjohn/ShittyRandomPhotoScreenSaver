# Historical Bugs

Last updated: 2026-09-01

Compact status/navigation index for significant SRPSS regressions. Full incident narratives live under
`Docs/Historical_Bugs/`.

Use [`Docs/Historical_Bugs/README.md`](Historical_Bugs/README.md) for the folder reading rule and
complete record set.

Historical incident bodies may name old owners. They are evidence for the failure/mechanism at the time,
not automatic current architecture instructions.

## Open / Watchlist Records

- [U-05 — MC Keyboard Focus / Ctrl Halo Runtime Input Family](Historical_Bugs/U-05_MC_Keyboard_Focus_Ctrl_Halo.md)
- [U-06 — Multi-Monitor MC Shadow Cache Corruption On Focus Loss](Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md)
- [U-09 — Visualizer CUSTOM Runtime Shape Poison / Post-Replay Geometry Authority Split](Historical_Bugs/U-09_Visualizer_Custom_Runtime_Shape_Poison.md)

## Active / Pending Acceptance Records

- [R-26 — Visualizer CUSTOM Display-Participation Fallback / Duplicate Owner From Startup And Sleep-Wake Participation Churn](Historical_Bugs/R-26_Visualizer_Custom_Display_Participation.md) — **PARTIAL / AWAITING VALIDATION**. E2.7 implementation is independently audited GREEN; physical dual-display wake/late-return acceptance remains.

No other R-series record is current implementation sequencing. Current migration work is owned by
`Current_Plan.md`; historical Phase/P-number status prose never admits current work.

- R-69 Bubble extreme-viewport scaling is **accepted as a golden contract**: never reintroduce global viewport compression of authored head/Ghost response. Any oversized extreme expansion tail is separate J visual debt.

## Standalone R Records

- [R-72 — Production Shutdown Imported A Dead Performance Parser](Historical_Bugs/R-72_Production_Shutdown_Imported_Dead_Perf_Parser.md)
- [R-71 — Visualizer Audio Per-Frame Task And DSP-State Allocation Drove GC Pressure](Historical_Bugs/R-71_Visualizer_Audio_Per_Frame_Task_And_DSP_State_Allocation.md)
- [R-70 — Gmail CUSTOM Uniform Scale Needed Different Width And Height Shell Semantics](Historical_Bugs/R-70_Gmail_Custom_Uniform_Scale_Preferred_Dimension_Split.md)
- [R-69 — Bubble Extreme-Viewport Global Radius Compression Suppressed Reactivity](Historical_Bugs/R-69_Bubble_Extreme_Viewport_Global_Radius_Compression.md)
- [R-68 — Visualizer CUSTOM Working Geometry Rejected Fresh Logical Snapshots](Historical_Bugs/R-68_Visualizer_Custom_Presentation_Authority_Rebase.md)
- [R-67 — CUSTOM Resize Re-entry Rebased Persisted Geometry And Could Compound Shrink](Historical_Bugs/R-67_Custom_Resize_Reentry_Absolute_Scale.md)
- [R-66 — Media Runtime Fast Polling Replaced By Provider Event Ownership](Historical_Bugs/R-66_Media_Event_Ownership_Replaced_Fast_Polling.md)
- [R-65 — Image Change Admission Could Bare-Snap And Prefetch Could Strand Across Recreation](Historical_Bugs/R-65_Transactional_Image_Admission_And_Prefetch_Latch.md)
- [R-64 — Retained Cursor Halo Turned Passive Pointer Motion Into Scene Pressure](Historical_Bugs/R-64_Native_Cursor_Halo_Scene_Pressure.md)
- [R-63 — Display-1 Black Flash From Fullscreen-Flip PresentMode Transitions](Historical_Bugs/R-63_Display1_Black_Flash_Fullscreen_Flip_Promotion.md)
- [R-62 — Transition-Scoped Presentation Deferral Degraded Bubble](Historical_Bugs/R-62_Transition_Scoped_Presentation_Deferral_Bubble_Regression.md)

- [R-61 — Settings Glass Used The Wrong Composition Family For A Layered QWidget](Historical_Bugs/R-61_Settings_Glass_Layered_HWND_Backdrop_Mismatch.md)
- [R-60 — ImagePresenter DPR Split Rekeyed The Retained Current Texture](Historical_Bugs/R-60_ImagePresenter_DPR_Texture_Identity.md)
- [R-59 — Frozen Settings/Edit Recreation Retained Compiled Bound Methods](Historical_Bugs/R-59_Runtime_Settings_Request_Input_Stack_Teardown.md)
- [R-58 — Move To Custom Copied Stale Backing Values Instead Of The Curated Runtime State](Historical_Bugs/R-58_Visualizer_Move_To_Custom_Preset_Authority.md)
- [R-57 — Scaled Prefetch Popped Selection Order Instead Of Descending Indices](Historical_Bugs/R-57_Image_Prefetch_Selected_Index_Order.md)
- [R-56 — Settings Close Path Retouched An Already-Deleted Dialog Wrapper](Historical_Bugs/R-56_Settings_Dialog_Deleted_Wrapper_Retouch.md)
- [R-55 — Spectrum Paint-Local Smoothing Created A Second Cadence](Historical_Bugs/R-55_Spectrum_Presentation_Smoothing.md)
- [R-54 — Phase 5 Bubble Cadence Gate Delayed And Flattened Visible Reactions](Historical_Bugs/R-54_Bubble_Cadence_Gate.md)
- [R-53 — Retired Runtime Generations Survived Full Edit/Settings Recreation](Historical_Bugs/R-53_Runtime_Recreation_Ownership_And_Memory.md)
- [R-52 — ImageWorker Retained Every Shared-Memory Frame Until Process Exit](Historical_Bugs/R-52_ImageWorker_Shared_Memory_Retention.md)
- [R-51 — Phase 3 Shared Shader Cache Gave Two Compositors One Deletion Identity](Historical_Bugs/R-51_Shared_Shader_Cache_Deletion_Ownership.md)
- [R-50 — Count-Only Image/Texture Retention And Unbounded Prefetch Backlog](Historical_Bugs/R-50_Count_Only_Resource_Retention.md)
- [R-49 — Settings/Edit Hide-Only Pause Retained Old GL Runtime And Shadowed Cleanup](Historical_Bugs/R-49_Settings_Edit_Hide_Only_Runtime_Retention.md)
- [R-48 — Clock Double-Click Replaced Per-Display Mode With Shared Setting](Historical_Bugs/R-48_Clock_Per_Display_Mode_Override.md)
- [R-47 — Oscilloscope Diagnostic Cleanup Broke Every Frame Push](Historical_Bugs/R-47_Oscilloscope_Diagnostic_NameError.md)
- [R-46 — Failed Blob Visualizer Retired End To End](Historical_Bugs/R-46_Blob_Visualizer_Retirement.md)
- [R-45 — Clock CUSTOM Payload Overrode Settings Mode To Preserve Geometry](Historical_Bugs/R-45_Clock_Custom_Geometry_Authority.md)
- [R-44 — Gmail CUSTOM Resize Payload Overrode Live Text Balance](Historical_Bugs/R-44_Gmail_Custom_Text_Balance_Authority.md)
- [R-43 — Defaults Foundry Modal Colour Picker Destroyed Its Delegate Editor](Historical_Bugs/R-43_Foundry_Modal_Colour_Editor_Lifetime.md)
- [R-42 — Abandonment Achievement Shelves Had No Selected-Game Acquisition Path](Historical_Bugs/R-42_Abandonment_Selected_Game_Achievement_Acquisition.md)
- [R-41 — Gmail OAuth Callback Server Escaped ThreadManager Lifecycle Ownership](Historical_Bugs/R-41_Gmail_OAuth_Callback_Thread_Ownership.md)
- [R-40 — Abandonment Ignored The Shared Steam Refresh Interval](Historical_Bugs/R-40_Abandonment_Shared_Steam_Refresh_Authority.md)
- [R-39 — Abandonment Automatic Rotation Lost Uncached Selected Artwork](Historical_Bugs/R-39_Abandonment_Automatic_Rotation_Artwork_Hydration.md)
- [R-38 — Achievement Pulse Ranked Recent Play Instead Of Recent Unlock And Elided Unlocked Counts](Historical_Bugs/R-38_Achievement_Pulse_Unlock_Ranking_And_Count_Elision.md)
- [R-37 — Abandonment Rotation Expiry Was Silently Dropped And Selection Walked Archive Order](Historical_Bugs/R-37_Abandonment_Rotation_Expiry_And_Sequential_Selection.md)
- [R-36 — Blob Mighty / Shaped Contours Reached Healthy Audio But Lost Visible Motion](Historical_Bugs/R-36_Blob_Mighty_Shaped_Contour_Motion.md)
- [R-35 — Steam Family Master Hid Settings But Did Not Gate Runtime Cards](Historical_Bugs/R-35_Steam_Family_Master_Runtime_Gate.md)
- [R-34 — Blank Weather Location Entered Lifecycle Error/Fallback And Collapsed Its Card](Historical_Bugs/R-34_Blank_Weather_Location_Lifecycle_Fallback.md)
- [R-33 — Defaults SST Regeneration Reached Installed Profiles And Canonicalized Machine Layout Slots](Historical_Bugs/R-33_Defaults_SST_Regeneration_Safety.md)
- [R-32 — Lazy WidgetsTab Save Treated Expected Unbuilt Sections As Guard Violations](Historical_Bugs/R-32_WidgetsTab_Lazy_Save_Hydration_Guard.md)
- [R-31 — Worker-Rejected Display Image Masqueraded As Multi-Monitor Compositor Loss](Historical_Bugs/R-31_ImageWorker_Display_Replacement_On_Rejection.md)
- [R-30 — Adaptive Timer Ownership Drop Left Python Process Alive After App Exit](Historical_Bugs/R-30_Adaptive_Timer_Shutdown_Ownership.md)
- [R-29 — Reddit Refresh Cadence And Provider Fallback Authority](Historical_Bugs/R-29_Reddit_Refresh_Provider_Authority.md)
- [R-28 — Settings Slider Last-Moved Weakref Touched Deleted Qt Wrapper](Historical_Bugs/R-28_Settings_Last_Moved_Deleted_QObject.md)
- [R-27 — Pending-Paint Requeue Perf Regression / UI Pressure Trap](Historical_Bugs/R-27_Pending_Paint_Requeue_UI_Pressure.md)
- [R-26 — Visualizer CUSTOM Display-Participation Fallback / Duplicate Owner From Startup And Sleep-Wake Participation Churn](Historical_Bugs/R-26_Visualizer_Custom_Display_Participation.md)
- [R-25 — Spectrum Solid-Bar Boundary Flicker / Robotic Snap Follow-Up](Historical_Bugs/R-25_Spectrum_Solid_Bar_Hysteresis.md)
- [R-24 — Retired Overlay-Effect Cache-Busting Path Still Driving Menu/Focus/Display Churn](Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md)
- [R-23 — CUSTOM Edit Mode Global Shell/Grid/Z-Order/Geometry Regression Family](Historical_Bugs/R-23_Custom_Edit_Surface_Geometry_Regression.md)
- [R-22 — Spotify Visualizer State Bleed: Runtime Bar Arrays Not Cleared During Mode Transitions](Historical_Bugs/R-22_Visualizer_Runtime_State_Bleed.md)
- [R-21 — Visualizer Painted-Card GL Content Escaping Card Boundary](Historical_Bugs/R-21_Visualizer_Painted_Card_GL_Boundary.md)
- [R-18 — Settings Dialog Flicker / Taskbar Ghost (`Qt691QWindowIcon`)](Historical_Bugs/R-18_Settings_Dialog_Taskbar_Ghost.md)
- [R-17 — Goo No-Gap/Artifact Regression Family](Historical_Bugs/R-17_Goo_No_Gap_Artifact_Regression.md)
- [R-16 — One-Dir Runtime Misdetected As Script + Curated Slot Drift](Historical_Bugs/R-16_One_Dir_Frozen_Detection_And_Slot_Drift.md)
- [R-15 — Frozen Curated Presets Silently Fell Back to Onefile Tree](Historical_Bugs/R-15_Frozen_Curated_Preset_Root.md)
- [R-14 — Blob Inward-Liquid Runtime Handoff Broke GL Overlay Push](Historical_Bugs/R-14_Blob_Inward_Liquid_Overlay_Handoff.md)
- [R-13 — Visualizer Sine/Oscilloscope Lines 4-6 Settings Never Persisted](Historical_Bugs/R-13_Sine_Oscilloscope_Lines_4_6_Persistence.md)
- [R-12 — Runtime Custom Slot Replaced While Cycling Presets](Historical_Bugs/R-12_Runtime_Custom_Preset_Cycling.md)
- [R-11 — Visualizer Preset Tooling Regression](Historical_Bugs/R-11_Visualizer_Preset_Tooling_Regression.md)
- [R-10 — Widget C++ Object Already Deleted on Provider Switch Callback](Historical_Bugs/R-10_Deleted_QObject_Provider_Switch_Callback.md)
- [R-09 — Settings Spinbox/LineEdit Fill Regression](Historical_Bugs/R-09_Settings_Input_Fill_QSS_Specificity.md)
- [R-08 — Pixel Shift Visualizer Bleed-Through](Historical_Bugs/R-08_Pixel_Shift_Visualizer_Bleed_Through.md)
- [R-07 — Startup Fade / Visualizer Secondary-Stage Ownership Split](Historical_Bugs/R-07_Startup_Fade_Visualizer_Secondary_Stage.md)
- [R-06 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE)](Historical_Bugs/R-06_Visualizer_Preset_Merge_Pollution.md)
- [R-05 — Visualizer Preset Slot Label Mismatched Edit Target](Historical_Bugs/R-05_Visualizer_Preset_Slot_Label_Target.md)
- [R-04 — Visualizer Curated Preset Selection Reused Custom Runtime Values](Historical_Bugs/R-04_Visualizer_Curated_Preset_Custom_Authority.md)
- [R-03 — Sine Idle Motion Dead/Flat During Paused State](Historical_Bugs/R-03_Sine_Idle_Paused_Motion.md)
- [R-02 — Reddit Helper Link Handoff Fails In Real Screensaver Runtime](Historical_Bugs/R-02_Reddit_Helper_Link_Handoff.md)
- [R-01 — Settings Shell Outer Border Radius / Corner Bleed](Historical_Bugs/R-01_Settings_Shell_Outer_Border_Radius.md)

### Historical numbering note

`R-19` and `R-20` were aliases for `U-02` and `U-03`; no independent source bodies existed, so no
duplicate records are manufactured.

## U Records

- [U-10 — Oscilloscope Visual Strobe / Waveform-Ghost-Transient Contract Drift](Historical_Bugs/U-10_Oscilloscope_Strobe_Waveform_Ghost_Contract.md)
- [U-09 — Visualizer CUSTOM Runtime Shape Poison / Post-Replay Geometry Authority Split](Historical_Bugs/U-09_Visualizer_Custom_Runtime_Shape_Poison.md)
- [U-08 — CUSTOM Runtime Replay Shrink Failure / Minimum-Constraint Reassertion Drift](Historical_Bugs/U-08_Custom_Replay_Shrink_Minimum_Constraints.md)
- [U-07 — Bubble Loud-Path Oracle Drift / Multi-Tweak Overfit Family](Historical_Bugs/U-07_Bubble_Loud_Path_Oracle_Drift.md)
- [U-06 — Multi-Monitor MC Shadow Cache Corruption On Focus Loss](Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md)
- [U-05 — MC Keyboard Focus / Ctrl Halo Runtime Input Family](Historical_Bugs/U-05_MC_Keyboard_Focus_Ctrl_Halo.md)
- [U-04 — Settings Dialog Flicker / Taskbar Ghost Investigation Archive](Historical_Bugs/U-04_Settings_Dialog_Flicker_Investigation_Archive.md)
- [U-03 — Non-Mirrored Spectrum Vocal Lane Still Missing After Claimed Landing](Historical_Bugs/U-03_Spectrum_Vocal_Lane_Migration.md)
- [U-02 — Bubble / Blob Signal-Contract Trap: Dead Smoothed Hold vs Raw-Energy Blowout](Historical_Bugs/U-02_Bubble_Blob_Signal_Contract.md)

## Archived Investigation Records

- [A-06 — Visualizer Runtime Mode/Preset Bleed Survived Audio Resets](Historical_Bugs/A-06_Visualizer_Mode_Preset_Bleed_Investigation.md)
- [A-05 — Blob Ghost/Pulse Investigation](Historical_Bugs/A-05_Blob_Ghost_Pulse_Investigation.md)
- [A-04 — MC Keyboard Focus / Ctrl Halo Interaction Regressions](Historical_Bugs/A-04_MC_Keyboard_Focus_Ctrl_Halo_Archive.md)
- [A-03 — Settings Dialog Flicker / Placeholder Regression](Historical_Bugs/A-03_Settings_Dialog_Flicker_Resolved_Archive.md)
- [A-02 — Spotify Visualizer Crossover Persistence (Blob muted after mode switch)](Historical_Bugs/A-02_Visualizer_Crossover_Persistence_Blob.md)
- [A-01 — Settings Dialog Flicker / Placeholder Regression — Historical Investigation](Historical_Bugs/A-01_Settings_Dialog_Placeholder_Investigation.md)

## Maintenance Rule

Do not add full incident bodies here. New substantial incidents receive one standalone record, then
links here and in the folder README.

When an incident changes from implementation-open to audit-green/acceptance-only/solved, update the
status navigation here and in `Docs/Historical_Bugs/README.md` without rewriting its historical
chronology.

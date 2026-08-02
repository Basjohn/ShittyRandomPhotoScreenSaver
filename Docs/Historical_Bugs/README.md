# Historical Bug Records

Standalone detailed incident records extracted from `Docs/Historical_Bugs.md`.

## Migration Safety Rule

The migration is copy-first and one incident per commit:

1. copy one complete source entry into a dedicated file;
2. preserve its date, status, evidence, failed approaches, correction, validation, and guardrails;
3. verify the dedicated-file commit independently;
4. leave the original monolithic entry untouched until the standalone set is complete;
5. only then replace `Docs/Historical_Bugs.md` with a compact status/index document linking these records.

During migration, `Docs/Historical_Bugs.md` remains the canonical fallback for entries not listed here. Do not delete or shorten an original entry merely because a partial or reconstructed standalone record exists.

For migrated active records, the standalone file is the current evidence record; the embedded monolithic entry remains an earlier snapshot until final cutover.

## Active / Pending Records

- [R-57 — Scaled Prefetch Popped Selection Order Instead Of Descending Indices](R-57_Image_Prefetch_Selected_Index_Order.md) — exact cause identified; code repair and validation pending.
- [R-56 — Settings Close Path Retouched An Already-Deleted Dialog Wrapper](R-56_Settings_Dialog_Deleted_Wrapper_Retouch.md) — Settings returns successfully, but dialog lifetime bookkeeping is invalid.
- [R-53 — Retired Runtime Generations Survived Full Edit/Settings Recreation](R-53_Runtime_Recreation_Ownership_And_Memory.md) — Settings barrier now passes and no linear two-cycle staircase reproduced; CUSTOM/Edit remains fail-closed on two managers.

## Standalone Records

### 2026-08

- [R-57 — Scaled Prefetch Popped Selection Order Instead Of Descending Indices](R-57_Image_Prefetch_Selected_Index_Order.md)
- [R-56 — Settings Close Path Retouched An Already-Deleted Dialog Wrapper](R-56_Settings_Dialog_Deleted_Wrapper_Retouch.md)
- [R-55 — Spectrum Paint-Local Smoothing Created A Second Cadence](R-55_Spectrum_Presentation_Smoothing.md)
- [R-54 — Phase 5 Bubble Cadence Gate Delayed And Flattened Visible Reactions](R-54_Bubble_Cadence_Gate.md)
- [R-53 — Retired Runtime Generations Survived Full Edit/Settings Recreation](R-53_Runtime_Recreation_Ownership_And_Memory.md)

### 2026-07

- [R-52 — ImageWorker Retained Every Shared-Memory Frame Until Process Exit](R-52_ImageWorker_Shared_Memory_Retention.md)
- [R-51 — Phase 3 Shared Shader Cache Gave Two Compositors One Deletion Identity](R-51_Shared_Shader_Cache_Deletion_Ownership.md)
- [R-50 — Count-Only Image/Texture Retention And Unbounded Prefetch Backlog](R-50_Count_Only_Resource_Retention.md)
- [R-49 — Settings/Edit Hide-Only Pause Retained Old GL Runtime And Shadowed Cleanup](R-49_Settings_Edit_Hide_Only_Runtime_Retention.md)
- [R-48 — Clock Double-Click Replaced Per-Display Mode With Shared Setting](R-48_Clock_Per_Display_Mode_Override.md)
- [R-47 — Oscilloscope Diagnostic Cleanup Broke Every Frame Push](R-47_Oscilloscope_Diagnostic_NameError.md)
- [R-46 — Failed Blob Visualizer Retired End To End](R-46_Blob_Visualizer_Retirement.md)
- [R-45 — Clock CUSTOM Payload Overrode Settings Mode To Preserve Geometry](R-45_Clock_Custom_Geometry_Authority.md)
- [R-44 — Gmail CUSTOM Resize Payload Overrode Live Text Balance](R-44_Gmail_Custom_Text_Balance_Authority.md)
- [R-43 — Defaults Foundry Modal Colour Picker Destroyed Its Delegate Editor](R-43_Foundry_Modal_Colour_Editor_Lifetime.md)
- [R-42 — Abandonment Achievement Shelves Had No Selected-Game Acquisition Path](R-42_Abandonment_Selected_Game_Achievement_Acquisition.md)
- [R-41 — Gmail OAuth Callback Server Escaped ThreadManager Lifecycle Ownership](R-41_Gmail_OAuth_Callback_Thread_Ownership.md)
- [R-40 — Abandonment Ignored The Shared Steam Refresh Interval](R-40_Abandonment_Shared_Steam_Refresh_Authority.md)
- [R-39 — Abandonment Automatic Rotation Lost Uncached Selected Artwork](R-39_Abandonment_Automatic_Rotation_Artwork_Hydration.md)
- [R-38 — Achievement Pulse Ranked Recent Play Instead Of Recent Unlock And Elided Unlocked Counts](R-38_Achievement_Pulse_Unlock_Ranking_And_Count_Elision.md)
- [R-37 — Abandonment Rotation Expiry Was Silently Dropped And Selection Walked Archive Order](R-37_Abandonment_Rotation_Expiry_And_Sequential_Selection.md)
- [R-36 — Blob Mighty / Shaped Contours Reached Healthy Audio But Lost Visible Motion](R-36_Blob_Mighty_Shaped_Contour_Motion.md)
- [R-35 — Steam Family Master Hid Settings But Did Not Gate Runtime Cards](R-35_Steam_Family_Master_Runtime_Gate.md)
- [R-34 — Blank Weather Location Entered Lifecycle Error/Fallback And Collapsed Its Card](R-34_Blank_Weather_Location_Lifecycle_Fallback.md)

## Final Cutover Requirements

Before replacing `Docs/Historical_Bugs.md` with the compact index:

- every original entry has exactly one standalone destination;
- every destination has been checked against the complete source entry, not a truncated excerpt;
- IDs, dates, statuses, cross-references, evidence paths, and unresolved validation requirements are preserved;
- unresolved and active records remain clearly separated from solved records;
- existing anchor references are either preserved in the compact index or updated deliberately;
- no historical detail exists only in an uncommitted working copy;
- the cutover is one dedicated commit with the pre-cutover monolith identified as the rollback point.

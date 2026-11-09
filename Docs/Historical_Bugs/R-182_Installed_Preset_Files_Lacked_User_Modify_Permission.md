# R-182: Installed presets were readable but could not be overwritten by an ordinary user

Discovered 9 November 2026 from the operator's frozen-build Studio save failures. Source repair is complete;
the next Standard and Media Center installations still require ordinary-user validation.

## Evidence and cause

The canonical frozen preset catalogue is `C:/ProgramData/SRPSS/presets/visualizer_modes`. Both elevated installers
copied presets there without granting ordinary users modification rights. On the inspected installation the root
was owned by Administrators; Users had Read/Execute and Write on the directory, while a shipped Bubble JSON file
granted Users only Read/Execute. Parent-directory Write did not make that existing preset writable or replaceable.

This distinction matters because the canonical preset writer validates a complete replacement, writes a sibling
temporary file, then atomically replaces the original. Permission to create the sibling is insufficient without
permission to modify/delete the existing destination. Source-run writable fixtures and elevated installations can
therefore hide the defect. Read-only-file tests prove error handling, not the installer-created ACL.

`git blame` shows the Standard installer's preset-directory declaration without a modification grant at
`feaa59f12` (28 July 2026); its 29 July ACL comment explicitly retained inherited ProgramData rights. This proves
the omission was present by July, not when an individual user first encountered it. The Media Center installer
likewise had no explicit mutable-preset directory declaration at discovery.

## Repair and regression boundary

Both installers now declare `users-modify` on the shared `visualizer_modes` data directory and its descendants.
The grant is restricted to authored JSON/data; application binaries, the helper and other shared directories
retain their existing ACL policy. Runtime saves keep the same catalogue, atomic writer and clear read-only errors.

`test_installed_preset_data_is_modifiable_without_granting_binary_write_access` failed before the repair and
checks both installer declarations and binary-tree exclusion. The focused installer selection passed three checks.
The Studio tests separately cover writable shared-root saves, read-only failure with draft retention and unchanged
bundled data. No installer was compiled or run and no installed ACL was changed during diagnosis.

The remaining field gate is a rebuilt Standard/MC installation followed by Save over a shipped preset and Save As
from a normal, non-elevated application. `Current_Plan.md` owns that Awaiting Validation item.

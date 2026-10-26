# Settings bucket persistence

Only the active pill's editor context (or active tab where no pills exist) retains its last-open editing path for
reopening Settings. Inactive pills and unrelated tabs present as closed, including after lazy reconstruction. Nested
ancestors remain open only to expose the selected leaf. Fresh profiles start closed. Preset choice, current mode and
stored Settings values remain independent of disclosure state.

Visualizer Technical is a child of Advanced. An open Technical leaf therefore retains both ancestors; an advanced
Custom leaf retains Advanced; a normal Custom leaf retires both. Legacy Technical-only state acquires its required
Advanced ancestor through the existing projection, without a new schema or persistence owner.

`core/settings/ui_bucket_state.py` owns canonical normalization and `project_settings_bucket_context` /
`retire_settings_bucket_context`. The Settings dialog and tab navigation apply that projection; shared bucket helpers
close unrelated live branches silently. Existing per-control maps remain the persistence schemas. Navigation does not
create a second context store, scheduler or polling owner. Connector rails derive from the visible hierarchy and do
not own persistence.

Focused regression coverage lives in `tests/test_settings_active_bucket_path.py`,
`tests/test_settings_bucket_single_open_contract.py` and `tests/test_settings_bucket_reopen_real_dialog.py`: selected
context, nested ancestors, tab/pill changes, lazy reopening, migration and real-dialog round trips. Operator acceptance
of the persistence and connector-rail work is recorded in source control; any new defect enters `Current_Plan.md`.

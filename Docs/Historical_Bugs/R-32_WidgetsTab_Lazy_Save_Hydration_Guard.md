# R-32 — 2026-07-10 — Lazy WidgetsTab Save Treated Expected Unbuilt Sections As Guard Violations (Resolved In Code, Runtime Validation Pending)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

- **Observed failure pattern:** an ordinary save after opening only a small subset of lazy widget sections emitted `blocked_save_from_unhydrated_section` for every other section, including Clock, Weather, Media, Visualizers, Reddit, Gmail, and Steam.
- **Evidence:** at `14:12:26`, the WidgetsTab log declared only `defaults` and `gmail` built/hydrated, then immediately warned that all intentionally unbuilt descriptors were blocked.
- **Root cause:** `_save_settings_now()` passed the full descriptor registry to `collect_widget_section_save_results()`. The collector correctly treated unhydrated sections as unsafe, preserved their existing values, and fired the guard, but expected lazy omission had already been misclassified as an attempted save. The caller then ran visualizer merge/normalization even when Visualizers was unhydrated, creating a second mutation seam outside the guard.
- **Fix:** normal save orchestration now passes only hydrated descriptors. The collector's direct unhydrated guard remains unchanged and tested. Visualizer merge, normalization, and Custom snapshot persistence run only when the Visualizers descriptor is hydrated; otherwise the persisted mapping is left untouched.
- **Bars:** `tests/test_widgets_tab.py` proves an ordinary Clock-only lazy save emits no blocked warning and preserves the exact pre-save visualizer payload. `tests/test_widget_descriptors.py` directly invokes an unhydrated descriptor and proves the warning/preservation guard still fires.
- **Runtime validation target:** ordinary saves after visiting one or two widget sections should not emit `blocked_save_from_unhydrated_section`. Any future occurrence should now represent a real orchestration bug rather than expected lazy omission.

## Record Provenance

This standalone file preserves the complete former inline `R-32` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

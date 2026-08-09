# R-28 — 2026-06-30 — Settings Slider Last-Moved Weakref Touched Deleted Qt Wrapper (Resolved In Code, Runtime Validation Pending)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

- **Observed failure pattern:** opening/closing Settings could emit repeated `RuntimeError: Internal C++ object (NoWheelSlider) already deleted` tracebacks from `ui/tabs/shared_styles.py::_mark_last_moved`, usually when the settings UI rebuilt or moved focus/slider state after a previous tab/widget tree had been torn down.
- **Root cause:** `NoWheelSlider` used a module-level Python `weakref` to track the last moved slider for QSS highlighting. A weakref only proves the Python wrapper still exists; it does not prove the underlying Qt C++ object is still live. When the old wrapper survived deletion, `_mark_last_moved()` called `setProperty()` / `style()` on a dead QObject.
- **Fix:** `NoWheelSlider` now validates wrappers through Shiboken before touching them, clears stale last-moved refs, and clears the ref from the slider `destroyed` signal when the highlighted slider dies.
- **Bars:** `tests/test_settings_shared_styles.py` simulates stale Shiboken-invalid wrappers and proves the settings highlight tracker does not touch or retain them.
- **Long-term prevention:** any UI helper that stores Qt widgets beyond immediate stack scope must distinguish Python wrapper liveness from C++ QObject liveness. Do not broad-catch `RuntimeError` as a substitute for validating ownership/lifetime at the seam.

## Record Provenance

This standalone file preserves the complete former inline `R-28` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

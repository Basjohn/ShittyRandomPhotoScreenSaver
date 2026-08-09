# R-18 — 2026-04-23 — Settings Dialog Flicker / Taskbar Ghost (`Qt691QWindowIcon`) (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final state:** the transient taskbar/titlebar ghost during settings startup was removed without disabling startup switches or custom styling.
- **Root cause:** a redundant `setVisible(True)` call for the visualizer preset slider edit button in `ui/tabs/media/preset_slider.py` was triggering transient helper windows (`Qt691QWindowIcon`) during construction.
- **What proved it:** automated harness isolation (`tools/flicker_test.py`) plus external HWND observer traces (`tools/winprobe_observer.py`) reproduced and then eliminated the ghost across targeted and full-dialog variants.
- **Final fix:** remove the redundant explicit visibility call and keep the existing widget default visibility behavior.
- **Why it worked:** the fix removed the actual constructor-time native-window trigger instead of masking behavior (no startup-flag restrictions, no style rollback).
- **Harness note:** keep the flicker harness + observer pair; they are now part of the regression toolbelt for this bug family.

## Record Provenance

This standalone file preserves the complete former inline `R-18` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

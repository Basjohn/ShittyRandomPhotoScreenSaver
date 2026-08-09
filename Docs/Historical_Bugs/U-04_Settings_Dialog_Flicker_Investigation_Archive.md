# U-04 — 2026-04-21 — Settings Dialog Flicker / Taskbar Ghost (Investigation Archive; Superseded by [R-18](R-18_Settings_Dialog_Taskbar_Ghost.md))

## Classification

- [ ] COMPLETELY FUCKED
- [X] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Status note:** this investigation thread is kept for timeline context; the resolved outcome is tracked in **R-18 (2026-04-23)**.

- **Symptom:** When the settings dialog is summoned, the taskbar flickers and a small window with the SRPSS app icon briefly appears (typically centered on Display 0) before the dialog renders. This affects title bars / taskbar of OTHER applications (e.g. the IDE on Display 0) even though the dialog targets Display 1. Present in both engine mode (via `dialog.exec()`) and config mode (`--s`, via `dialog.show()` + `app.exec()`).
- **Earlier partial fixes (kept, each individually valid):**
  - **Fix A:** Removed premature `raise_()` / `activateWindow()` in `engine_handlers.py` — these were redundant with `exec()` internals and could produce ghost frames.
  - **Fix B:** Changed window flags from `Window | FramelessWindowHint | WindowSystemMenuHint` to `Dialog | FramelessWindowHint` — the `Window` type created an unnecessary independent taskbar entry during HWND allocation.
  - **Fix C:** Added `WA_ShowWithoutActivating` during construction, cleared in `showEvent` — prevents incidental Win32 activation during `__init__`.
  - These fixes eliminated a separate "tiny ghost window" artifact from the old window type. The primary flicker (taskbar + Display 0 title bars + small icon window) **persists** after all three.
- **Systematic isolation via `tools/flicker_test.py` (13 variants tested):**
  - Variants 1-7: Basic QDialogs with every combination of flags/attributes (`FramelessWindowHint`, `WA_TranslucentBackground`, `Dialog`, `Window`, `Tool`, stylesheets). **None flickered.**
  - Variant 8: Font registration via `QFontDatabase.addApplicationFont`. **No flicker.**
  - Variant 9: Font registration + `QGuiApplication.setFont()` global font change. **No flicker.**
  - Variant 10: Full flags + real `dark.qss` stylesheet (256ms show). **No flicker.**
  - Variant 11: Full flags + 200 child widgets (QGroupBox/QLabel/QPushButton/QCheckBox/QComboBox). **No flicker.**
  - Variant 12: All combined — font reg + global font + large QSS + 200 widgets (670ms construction). **No flicker.**
  - Variant 13: Actual `SettingsDialog` construction (2260ms). **FLICKERED — tiny central window with app icon in title bar.**
  - Variants 14-16: Same as 1/5/12 but with main.py startup steps applied first (DPI policy, `AA_UseDesktopOpenGL`, `AA_ShareOpenGLContexts`, `QSurfaceFormat.setDefaultFormat`, `app.setWindowIcon`). **None flickered.**
  - Variant 17: Actual `SettingsDialog` + main.py setup (1960ms). **FLICKERED — same tiny window.**
- **What this proves:**
  - The flicker is NOT caused by window flags, attributes, `WA_TranslucentBackground`, font loading, global font changes, large stylesheets, many child widgets, construction time, or main.py OpenGL/DPI/icon setup.
  - The flicker IS caused by something specific inside `SettingsDialog.__init__` that no mock variant reproduces — something about the specific widget tree, signal wiring, effect composition, or native API calls during its construction.
- **Failed approaches to stop repeating:**
  - Off-screen HWND creation (`self.move(-32000, -32000)` + snap in `showEvent`) — flicker still occurred.
  - Focus gap theory (reordering `engine.stop()` vs `dialog.show()`) — user confirmed "not focus related AT ALL."
  - Multi-monitor compositor / placeholder theory (Approaches A-E in the historical entry) — proven wrong; flicker occurs in standalone `--s` config mode with no engine, no compositor, no multi-monitor windowing.
  - Acrylic blur — user confirmed "added acrylic after this issue first appeared."
- **Current investigation direction:** Binary search within `SettingsDialog.__init__` to find the exact operation that triggers the tiny HWND with title bar. The tiny window has a standard title bar with the app icon, suggesting somewhere during construction a native HWND is created with `WS_CAPTION` style before frameless flags take effect, or a secondary HWND (tooltip, popup, or internal Qt helper) is briefly shown.
- **2026-04-23 follow-up isolation (new):**
  - Added auto-close harness behavior in `tools/flicker_test.py` (default `10s`) plus new targeted variants `34-36`.
  - `v34` (`force_widgets_initial_no_hydration`): **~2271ms construct**, **45** `QComboBoxPrivateContainer` helper frames already present **before** `show()`.
  - `v35` (`force_sources_initial_no_hydration`): **~519ms construct**, **0** helper frames before/after show.
  - `v36` (`force_sources_hydrate_without_widgets`): **~519ms construct**, then **15** helper frames after show (non-widgets tabs only).
  - Interpretation: the strongest construction-time pressure/flicker candidate is the **Widgets tab build path**, especially when it is initial-tab or hydrated immediately.
- **2026-04-23 automation upgrade (new):**
  - Added external observer `tools/winprobe_observer.py` and wired it into `tools/flicker_test.py` per variant run (`SRPSS_FLICKER_EXTERNAL_WINPROBE=1`).
  - This captures transient native HWNDs + foreground changes across the **entire** variant lifecycle (constructor + show), not just post-show.
  - In failing paths (`v13`, `v34`), observer repeatedly reports transient tiny caption windows:
    - class `Qt691QWindowIcon`
    - size ~`105x59`
    - title `python` (harness process title)
    - each appearance briefly steals foreground before focus returns to Codex window.
  - In control paths (`v35`, `v36`, `v18`), these transient `Qt691QWindowIcon` windows/foreground steals are absent when Widgets build pressure is removed.
- **Important correction (why earlier env A/B could still fail):**
  - `SRPSS_SETTINGS_FORCE_INITIAL_TAB_SOURCES=1` was being undermined by `_restore_last_tab_selection()`, which could switch back to saved Widgets tab after init.
  - Fixed: when force-initial-sources is enabled, last-tab restore is now skipped so the A/B toggle behavior is actually deterministic.
- **2026-04-23 root-cause breakthrough (new):**
  - Isolated to `ui/tabs/media/preset_slider.py` inside `VisualizerPresetSlider._build_ui()`.
  - The explicit `self._edit_btn.setVisible(True)` call (redundant, default is already visible) consistently triggered the transient `Qt691QWindowIcon` helper HWND / foreground-steal signature in observer logs.
  - Removing that single call eliminated the startup taskbar/titlebar ghost in automated repro paths:
    - `tools/flicker_test.py v54` (plain dialog + six `VisualizerPresetSlider` instances): tiny caption windows removed.
    - `v48` (SettingsDialog visualizers-only): tiny caption windows removed.
    - `v13` (full real SettingsDialog): tiny caption windows removed.
- **Immediate next step (actionable):**
  - Run live user validation in the actual startup path (normal settings open and `--s`) to confirm the ghost is gone outside harness.
  - If validated, flip this issue from `PARTIAL` to `SOLVED` and archive older hydration-deferral workaround options as no longer needed for this bug family.

## Record Provenance

This standalone file preserves the complete former inline `U-04` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

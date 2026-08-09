# A-01 — MAJOR VISUAL BUG: Settings Dialog Flicker / Placeholder Regression — Historical Investigation Archived

## Classification

- [ ] COMPLETELY FUCKED
- [X] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **User later confirmed this issue is resolved in live use (Mar 22 2026).**
- The investigation record is retained below because several failed approaches are still useful anti-patterns. The final working state is summarized in the resolved entry dated **2026-03-22**.

- **Problem statement:** On MC builds we only render the fullscreen DisplayWidget on Display 1 while Display 0 remains a normal Windows desktop (winlogon is *not* involved). When we summon Settings (which still launches on Display 0), `engine.stop(exit_app=False)` tears down the MC window on Display 1 *and* leaves Display 0 unprotected for ~3 s while the dialog constructs. Windows fills that gap with a security-style popup that shows a lock icon and rapidly flickers. This is **not** historical behavior; the regression appeared after the March 13 settings work. **Update:** running `main.py` in script mode (non-winlogon screensaver) exhibits the exact same flicker, proving the bug is tied solely to the settings dialog invocation/creation path and is independent of build flags or MC-only windowing.
- **MC-specific observations supplied by user:**
  - Flicker occurs on whichever display is about to host the settings dialog even if that display never had SRPSS content (e.g., MC pinned to Display 1, dialog on Display 0).
  - Switching MC window flags between `Qt.SplashScreen` and `Qt.Tool` does **not** change the outcome; the secure popup still flashes.
  - Adding the `SettingsShieldManager` overlay not only failed to help, it added a second flicker on top of the MC display, so shields are now fully disabled.
  - The issue never repros in screensaver mode (every monitor has a DisplayWidget) which re-confirms this is an MC-only regression tied to mixed content across monitors, not Winlogon.
- **Observed deltas vs ≤ March 12 builds:** identical teardown order except for shields, but settings used to appear almost instantly, suggesting presentation timing/foreground activation hid the blanking earlier. Currently: log timestamps show ~3 s between “Settings requested” and “Settings dialog created,” during which Windows repeatedly presents the placeholder on the target monitor. 
- User note: Settings always opened slowly and there was no shitty ass flickering when it did.
- **Investigation Hypothesis (user):** MC builds need either (a) the dialog to become visible <200 ms so Windows never paints the placeholder, or (b) a masking strategy that works on *non*-MC monitors without introducing new artifacts. Shields are ruled out; we must find a different architectural fix.

**Approach A – Delay display teardown until dialog is visible** — **FAILED**
- Rationale: Even if teardown is delayed, the dialog often opens on monitor 0 while the compositor/render stack sits on monitor 1 (especially in MC builds where only one display is covered). The moment we finally pause/destroy the compositor, the monitor hosting the dialog will flash Windows’ placeholder, so this approach cannot eliminate flicker without additional masking.

**Approach B – Keep DisplayWidgets composited with a static frame during pause** — **FAILED**
- Rationale: `engine.stop()` always clears and hides every `DisplayWidget` within ~60 ms of the hotkey. Even if we froze the compositor first, the mandatory teardown would still destroy the HWNDs and Windows would drop in its placeholder for the remaining ~3.2 s while `SettingsDialog` builds. Avoiding teardown entirely would violate engine lifecycle contracts (widgets expect cleanup/start) and reintroduce the multi-monitor focus issues that Approach A already failed to solve.

**Approach C – Replace OS placeholder with compositor-controlled blackout** — **FAILED**
- Rationale: Blackout overlays only exist on monitors that currently host DisplayWidgets. MC builds (and script-mode runs) routinely summon Settings on a monitor that **never** had our compositor window, so there is no HWND on that screen to paint the blackout. Windows still shows its placeholder the moment the dialog begins constructing, so this approach cannot solve the regression without an entirely different masking primitive.
- (Historical steps retained for reference)

**Approach D – Cut SettingsDialog construction time to <200 ms without hurting UX** — **FAILED**
- [x] **Target-tab-first creation (no ugly placeholders):**
  [x] **Per-tab styling/shadow application:**
  [x] **Cache heavy-but-static data with freshness checks:**
- **Summary:** Target-tab-first hydration, per-tab styling deferral, and caching are live, but dialog construction still takes ~3 s on MC builds (see latest `screensaver.log`). The flicker persists even when only one monitor hosts SRPSS content, so raw construction speed is insufficient to mask the OS placeholder.
 Fade-in fallback remains unimplemented and is no longer expected to solve the problem; Approach D is marked failed pending a new direction.

**Approach E – External research before redesign (NEW)**
- [ ] Research and corroborate ROOT CAUSES from **≥5 recent sources** (2024+) focused on Windows multi-monitor Qt apps that mix fullscreen + desktop content. Emphasize findings about secure-desktop placeholders, HWND teardown ordering, and alternative masking primitives. Summarize pros/cons and cite each source before proposing a new architecture.
Mitigation last resort, but unacceptable as early builds of this project did not have this bug.

## Record Provenance

This standalone file preserves the complete former inline `A-01` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

# Media Key Debug Notes

Last updated: 2026-04-25

Operational playbook for media-key and keyboard-routing regressions.

## 0. Current Framing (2026-04-25)

MC comes first. MC must remain a screensaver-style surface: no normal taskbar entry, no Alt-Tab entry, and no falling behind other windows. Normal-window tests are not useful fix candidates because normal preview/exe behavior is already known to handle keys and does not satisfy the MC contract.

The harness now reproduces the user's real-world MC failure: **manual mouse click into the SRPSS MC window on a secondary display causes both media keys and control hotkeys to fail**. Keys are "eaten" -- they neither reach SRPSS handlers nor pass through to the system (Spotify/Windows). Defocusing SRPSS (focusing any app on the primary display) restores key functionality immediately.

Critical distinction: **programmatic focus** (`SetForegroundWindow` / `BringWindowToTop`) does **not** reproduce the failure. Only a **real user mouse click** into the SRPSS window triggers the bug.

**Speculative hypothesis**: this points to a Qt-side focus/activation or mouse-grab side effect, not a native Windows focus-routing issue. Requires validation by isolating which Qt widget or event filter captures input after manual click.

User setup detail: multi-display configuration. SRPSS MC runs on Display 1. User works on Display 0 (IDE, browsers). Clicking SRPSS on Display 1 to focus it is the repro step.

PowerToys note: user remaps PgUp/PgDn to global Volume Up/Down via PowerToys. This causes media keys to appear as `injected=true` in `WH_KEYBOARD_LL` hooks because PowerToys sends them via `SendInput`. This is expected and accounted for in the hardware ingress validator.

What the harness currently proves:

1. `SendInput`/Qt key path works while focused (`C` + synthetic media VK route through `InputHandler`).
2. Injected `WM_APPCOMMAND` path also reaches `display_native_events` in focused MC runs.
3. Valid focused-click samples can pass when the click target is controlled and Reddit/browser focus diversion is removed.
4. **Hardware ingress validator reproduces the real failure**: manual click into SRPSS on secondary display causes keys to be eaten.
5. **Programmatic focus does NOT reproduce the failure**: keys continue to work after `SetForegroundWindow`.

What this does not prove:

1. It does not yet identify the exact Qt-side mechanism that "eats" keys after manual click.
2. It does not justify changing MC to a normal/taskbar/Alt-Tab window style.
3. It does not justify moving to Winlogon before MC behavior is understood.

What is still unresolved:

1. Exact Qt widget or event filter that captures input after manual mouse click on secondary display.
2. Whether the issue is mouse-grab, widget focus theft, or a Qt event loop state change.
3. Why normal control keys fail in the same focused MC state after manual click.
4. Winlogon asymmetry where `S` works while media keys fail. Deferred until MC is solved.

Newest MC observation (2026-04-25):

1. **Multi-display repro confirmed**: SRPSS MC on Display 1, user works on Display 0. Clicking SRPSS on Display 1 triggers the bug.
2. **Keys are "eaten"**: after manual click into SRPSS, media keys and hotkeys do not reach SRPSS handlers AND do not pass through to Windows/Spotify. They simply disappear.
3. **Defocus recovery confirmed**: focusing any app on Display 0 immediately restores key functionality.
4. **Manual click vs programmatic focus distinction**: `SetForegroundWindow`/`BringWindowToTop` does NOT trigger the bug. Only a real mouse click into SRPSS does. This implicates Qt-side mouse/focus side effects, not Windows focus routing.
5. **Programmatic click also does NOT trigger the bug**: `SendInput` mouse click into SRPSS window does not reproduce the failure.
6. When MC starts unfocused, physical keys can work.
7. Splash-window experiment is ruled out as a fix: it shows the same issue and adds worse focus instability after focus changes.

## 1. Current Repro Matrix (Source of Truth)

Validated user matrix (2026-04-23):

1. **MC runtime (`main_mc.py`) after manual click into SRPSS window on Display 1**
   - Media keys fail while SRPSS is focused (keys are "eaten", do not pass through to system).
   - Hotkeys (`C`, `X`, `S`) also fail while SRPSS is focused.
   - Keys work again when focus shifts to any app on Display 0 or another app on Display 1.
   - **Programmatic focus** (`SetForegroundWindow`) does NOT trigger this failure.
   - **Programmatic click** (`SendInput` mouse) does NOT trigger this failure.
   - Only a **real user mouse click** into the SRPSS window reproduces the bug.
2. **Normal mode, Windows Preview runtime**
   - All keys work, including media keys.
3. **Normal mode, Winlogon runtime**
   - Media keys fail.
   - Most non-media keys fail.
   - `S` still works and opens Settings.

This is a runtime/focus split problem, not a single-key bug.

Active priority: solve MC focused behavior first. Winlogon is a separate runtime surface and should not steer the next code edit until MC behavior is perfect and reproducible.

## 2. Hard Constraints (Do Not Violate)

- Do not apply routing edits until the MC failure is reproducible under harness/probe evidence.
- Do not collapse MC/Preview/Winlogon into one assumed behavior model.
- Do not ship a "works in preview" fix as proof for Winlogon or focused-MC behavior.
- Do not use normal-window/taskbar/Alt-Tab behavior as an MC fix path.
- Preserve MC window guardrails: no taskbar entry, no Alt-Tab entry, topmost/no-fall-behind.
- Do not treat synthetic or injected probe success as a reproduction of physical-key success.
- Preserve existing archived sub-fixes unless replacement behavior is proven across the full matrix.

## 3. Primary Investigation Questions

1. Which event ingress paths are active per runtime (`WM_APPCOMMAND`, `WM_KEYDOWN/UP`, Raw Input)?
2. What focus/foreground transitions change media-key behavior in MC?
3. **Why does a real user mouse click into SRPSS on a secondary display trigger the key-eating bug, while programmatic `SetForegroundWindow`/`SendInput` click does not?**
4. Is focus-loss recovery in MC a focus ownership change, a message-route change, or both?
5. Why does `S` survive in Winlogon while media keys fail? Deferred until MC is understood.
6. Which Qt widget or focus state is "eating" keys after manual mouse click on Display 1?
7. Does multi-display geometry (Display 1 coordinates, monitor boundary crossing) play a role in the Qt focus/activation bug?

## 4. No-Edit Investigation Checklist (Live)

- [x] Capture baseline MC logs for the exact user sequence: focus SRPSS, physical media key, physical control key, external focus recovery.
- [x] Trace focused vs unfocused MC transitions (before click, after click, after focus-loss, after alt-tab).
- [ ] Confirm which window receives native messages in each MC state (esp. after manual click vs programmatic focus).
- [ ] Verify whether Raw Input registration is live and still dispatching in each MC state.
- [ ] Confirm native style/ex-style remains guardrail-compliant (`WS_EX_TOOLWINDOW`, topmost, no taskbar/Alt-Tab) for every candidate path.
- [x] Produce one MC side-by-side matrix artifact (state x key family x ingress path x observed result).
- [x] Freeze root-cause hypothesis: **manual mouse click into SRPSS on secondary display causes Qt-side key capture/eating. Programmatic focus does not.** Fix must target Qt focus/activation/mouse side effects, not Windows focus routing.
- [ ] Identify exact Qt widget or event filter that captures input after manual click.
- [ ] Test whether disabling specific widgets (e.g., GL compositor overlay, visualizer widget) prevents key-eating after manual click.
- [ ] Test whether `setFocusPolicy(Qt.NoFocus)` on all overlay widgets prevents the bug.

## 5. Automation Harness Status + Next Up

Completed:

- [x] Repeatable matrix runner (`tools/media_key_matrix_harness.py`).
- [x] Focused-state scenarios for primary path (`focused_idle`, `focused_clicked`).
- [x] Separate probes for:
  - Qt synthetic key route (`SendInput`)
  - injected `WM_APPCOMMAND` route
  - transition key route (`C`)
- [x] Dual log ingestion (`screensaver.log` + `screensaver_verbose.log`) with JSON + Markdown reports.
- [x] MC runtime contract validation (window class/flag + display creation + GL compositor creation + show_on_screen).
- [x] Live-profile parity execution path (requires elevated run outside sandbox).
- [x] Safe-click harness guard for mirrored/isolated profiles:
  - disables `widgets.reddit.enabled`, `widgets.reddit.exit_on_click`, and `widgets.reddit2.enabled`
  - keeps focused-click automation from triggering Reddit interaction during tests.

Latest live-parity finding (2026-04-23):

- `focused_idle`: Qt media pass, AppCommand pass, `C` pass.
- `focused_clicked`: initially showed Qt media fail, AppCommand pass, `C` fail.
- Follow-up evidence review: these failing `focused_clicked` rows were contaminated by focus theft during click prep (external browser foreground), so they are not valid focused-MC samples.
- Harness now blocks/labels such rows as invalid (`focused_clicked_unstable_focus_or_overlay_focus_steal`) instead of treating them as real key-route failures.
- With edge-first click targeting and invalid-row blocking in place, repeated live-profile runs now produce valid `focused_clicked` samples that pass all probes (Qt media, native appcommand, native key-message `C`, transition `C`) in both strict and realistic focus policies.
- Conclusion update: the earlier `focused_clicked` fail signature was a harness contamination artifact, not yet proof of a persistent focused-MC app-path failure.
- Mirrored safe A/B run (`2026-04-23 22:31`) also passed all focused scenarios under both strict and realistic policies, with scenario validity preserved.

Latest probe extension (2026-04-25):

- Hardware ingress validator (`tools/hardware_ingress_validator.py`) successfully reproduces the real-world MC failure.
- **Key finding**: manual mouse click into SRPSS on secondary display causes both media keys and control hotkeys to be "eaten". Programmatic `SetForegroundWindow` and `SendInput` mouse clicks do NOT reproduce the bug.
- PowerToys remaps PgUp/PgDn to Volume Up/Down, causing media keys to appear as `injected=true` in `WH_KEYBOARD_LL`.
- LL hooks (`WH_KEYBOARD_LL`, `WH_MOUSE_LL`) are used **only in diagnostic harness tools** (`tools/media_key_reality_harness.py`, `tools/hardware_ingress_validator.py`). They are **not** present in the main SRPSS build. The main build uses `core/windows/media_key_rawinput.py` (Raw Input API) for non-blocking media key detection.
- Next harness step: add display-index capture and manual-click coordinate logging to correlate exact click location with key-eating onset.

Next harness upgrades (required for MC diagnosis):

- [ ] Add a Windows message observer companion harness to capture:
  - active HWND, foreground window,
  - native message IDs (`WM_APPCOMMAND`, `WM_INPUT`, `WM_KEYDOWN/UP`),
  - dispatch outcomes.
- [x] Add deterministic click-safe targeting for focused MC runs so `focused_clicked` stays on SRPSS and does not trigger browser foreground diversion.
- [ ] Add MC hardware-path validation mode (do not rely only on synthetic injection) and compare against injected-native probes.
- [x] Add two-phase MC reality mode (`focus_transition`) to capture unfocused-working vs focused-failing behavior in one report.
- [x] Test the existing splash-window flag path as a diagnostic only; do not treat it as a fix.
- [x] Add native HWND style/ex-style dumps to the reality harness.
- [ ] Add a focused-MC external-focus recovery scenario for contrast.
- [ ] Research and map the native Win32/Qt activation contract for MC `Qt.Tool` windows while preserving the existing no-taskbar/no-Alt-Tab/topmost contract.
- [ ] Defer Winlogon-oriented probe capture until MC behavior is reliable.
- [ ] Add post-click native key-message correlation probe (`WM_KEYDOWN`/`WM_SYSKEYDOWN` path evidence) to explain why `C` fails after click while AppCommand still passes.

Quick automation commands:

1. Single run (focused MC):
   - `python tools/media_key_matrix_harness.py --launch mc --profile-mode live --focus-policy realistic --scenarios focused_idle,focused_clicked`
2. Safer mirrored run (recommended when click scenarios are included):
   - `python tools/media_key_matrix_harness.py --launch mc --profile-mode mirrored --focus-policy realistic --scenarios focused_idle,focused_clicked`
3. A/B compare (strict vs realistic):
   - `python tools/media_key_matrix_compare.py --launch mc --profile-mode mirrored --policies strict,realistic --scenarios focused_idle,focused_clicked`
4. Two-phase MC reality capture:
   - `python tools/media_key_reality_harness.py --profile-mode mirrored --scenario focus_transition --manual-focus-seconds 8 --observe-seconds 12`

## 6. Code Surfaces To Analyze First

- `rendering/display_native_events.py`
- `core/windows/media_key_rawinput.py`
- `rendering/display_input.py`
- `rendering/input_handler.py`
- Runtime entry/launch-path differences in `main.py` and `main_mc.py`

## 7. Research Findings & Code Analysis (2026-04-25)

### 7.1 Online Research — Multi-Display Qt.Tool Focus Issues

Multiple independent sources confirm `Qt::Tool` / `WS_EX_TOOLWINDOW` windows exhibit anomalous focus/keyboard behavior on Windows, especially in multi-monitor configurations and when the window must remain on top without taskbar/Alt-Tab presence.

**A. Qt::Tool sets WS_EX_TOOLWINDOW — undocumented Windows side effects**
- Source: `forum.qt.io/topic/141915` — Chris Kawa confirms `Qt::Tool` maps to `WS_EX_TOOLWINDOW`. This flag causes tool windows to appear on **all virtual desktops** and changes how the Windows window manager routes activation/focus messages.
- **Implication for SRPSS**: Our MC window uses `Qt::Tool` intentionally (for no-taskbar/no-Alt-Tab). The `WS_EX_TOOLWINDOW` style may be causing Windows to treat manual click activation differently than programmatic `SetForegroundWindow`.

**B. Qt's activateWindow() is unreliable when app is not already foreground**
- Source: `bugreports.qt.io/browse/QTBUG-14062` — `QWidget::activateWindow()` on Windows is blocked by Microsoft if the application is not currently the active one. The title bar flashes but the window does not become the true foreground window.
- **Implication for SRPSS**: Our `_restore_mc_input_focus()` calls `activateWindow()` + `requestActivate()` + `setFocus()`. If Windows blocks activation because the app was not foreground (user was on IDE on Display 0), these calls may silently fail. However, the harness's direct `SetForegroundWindow()` bypasses Qt and works, confirming the issue is in the Qt activation path, not Windows focus policy.

**C. Key events are LOST during focus transitions between Qt widgets**
- Source: `stackoverflow.com/questions/11047880` — When a Qt window loses focus and another gains it, key events pressed in the transition gap are **not delivered to either window's event filter**. The application may not have focus at all during the gap.
- **Implication for SRPSS**: Manual click into the MC window triggers a focus transition from Display 0 (IDE) to Display 1 (SRPSS). If Qt's focus routing takes time to settle, keys pressed immediately after the click may fall into this gap and be permanently lost. But the user reports keys are eaten **persistently** after click, not just during transition, so this alone is insufficient.

**D. WS_EX_TOOLWINDOW + manual click = "focus cursor present but no keyboard capture"**
- Source: `stackoverflow.com/questions/47453827` — A window with `WS_EX_TOOLWINDOW` + `WS_POPUP | WS_VISIBLE` shows the typing cursor (appears focused) but **does not capture actual keyboard input**. Solved by simulating a click, not by `SetFocus()`.
- **Implication for SRPSS**: This is a **direct match** to our symptoms. The window appears focused after manual click but keyboard input is not routed to it. Programmatic `SetForegroundWindow` does not exhibit this because it bypasses the `WM_MOUSEACTIVATE` → `SetFocus()` path that Windows uses for manual clicks.

**E. Tool windows can steal focus unexpectedly on showNormal() / activation**
- Source: `forum.qt.io/topic/83098` — `showNormal()` on a tool window causes keyboard focus to be stolen unexpectedly. Using `Qt::Tool` alone (without `WindowStaysOnTopHint`) can prevent focus theft but breaks always-on-top behavior.
- **Implication for SRPSS**: Our MC window combines `Qt::Tool | Qt::WindowStaysOnTopHint | Qt::FramelessWindowHint`. The `show_on_screen()` path calls `show()`, `raise_()`, and `activateWindow()`. If a subsequent manual click triggers an internal `showNormal()` or re-activation path inside Qt, it may corrupt the focus state.

**F. AutoKey Qt focus-loss issue — identical symptom pattern**
- Source: `github.com/autokey/autokey/issues/169` — After sending keys to a Qt app, the window loses focus, quickly regains it briefly, then loses it completely. The title bar indicates "not focused" but the window still accepts human input. `xdotool getwindowfocus` shows the focused window hasn't changed, but `getactivewindow` fails.
- **Implication for SRPSS**: This reveals a distinction between **focused window** (where keyboard messages go) and **active window** (title bar highlight). Our manual click may make SRPSS the "active" window (visible highlight) but not the "focused" window (keyboard target). Programmatic `SetForegroundWindow` sets both correctly.

**G. WS_EX_NOACTIVATE is the native Windows solution for non-activating windows**
- Source: `forum.qt.io/topic/140542`, `stackoverflow.com/questions/18662031` — `Qt::WindowDoesNotAcceptFocus` and `Qt::WA_ShowWithoutActivating` are **not sufficient** on Windows. The native `WS_EX_NOACTIVATE` extended style is required to truly prevent a window from taking focus on click.
- **Implication for SRPSS**: Our code sets `WindowDoesNotAcceptFocus=False` when claiming focus, and `_restore_mc_input_focus()` aggressively reclaims focus. But if a child widget (or the window itself) still has some `WS_EX_NOACTIVATE` flag set incorrectly, manual click may not activate it properly while programmatic focus does.

**H. Focus problems when clicking on embedded/native child content**
- Source: `forum.qt.io/topic/56536` — When a native HWND is embedded in a Qt widget, clicking on the embedded content causes focus to behave as if the click hit the parent QMainWindow instead. The embedded content's WindowProc never receives `WM_FOCUS` back.
- **Implication for SRPSS**: Our DisplayWidget contains a GL compositor (`QOpenGLWidget`) and multiple overlay widgets. If any of these child widgets has its own native window handle (e.g., `Qt.WA_NativeWindow`), clicking on it may cause Qt's focus system to route focus to an unexpected target.

### 7.2 Code Analysis — Compounding Issues Identified

**Issue 1: Focus policy and window flag toggling in DisplayWidget.__init__**
- `DisplayWidget.__init__` calls `claim_focus(self)` which sets `setFocusPolicy(StrongFocus)`, `setWindowFlag(WindowDoesNotAcceptFocus, False)`, and `setAttribute(WA_ShowWithoutActivating, False)`.
- **Problem**: `setWindowFlag()` on an already-created window **causes the window to be hidden and reshown** when the window is visible. During `__init__` the window is not yet visible, so this is safe. But if any code path calls `setWindowFlag()` after `show()`, it would cause a hide/show cycle that corrupts focus.
- **Finding**: No post-show `setWindowFlag()` calls were found in the main paths. `_restore_mc_input_focus()` does NOT call `setWindowFlag()`. This issue is **ruled out** as the primary cause.

**Issue 2: _restore_mc_input_focus() uses MouseFocusReason, not ActiveWindowFocusReason**
- `_restore_mc_input_focus()` calls `widget.setFocus(Qt.FocusReason.MouseFocusReason)`.
- `MouseFocusReason` tells Qt the focus change was caused by a mouse click. Qt's internal focus routing may behave differently than `ActiveWindowFocusReason` (used in `show_on_screen()`).
- **Problem**: If a child widget under the cursor has `ClickFocus` policy, `MouseFocusReason` may give focus to the child widget instead of the DisplayWidget. The child widget (e.g., a Reddit link label, a media widget button) may not handle key events, causing them to be "eaten".
- **Finding**: In hard_exit mode, left-clicks route to `route_widget_click()` which checks if a widget was clicked. But if no widget handles the click, `event.accept()` is called and the function returns. The focus may still be on a child widget that didn't handle the click.
- **Severity**: MODERATE. This could explain why manual click causes focus to land on a child widget, but doesn't explain why media keys (which bypass Qt entirely via Raw Input) are also eaten.

**Issue 3: CursorHaloWidget is a separate top-level Tool window**
- `CursorHaloWidget` is created with `Qt.Tool | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint` and `WA_ShowWithoutActivating=True`.
- It forwards mouse events to the parent DisplayWidget via `_forward_mouse_event()`.
- **Problem**: While `WindowDoesNotAcceptFocus` should prevent it from taking focus, if there's a bug in Qt's focus routing on `WS_EX_TOOLWINDOW` windows, the halo window might interfere with focus ownership.
- **Finding**: The halo is explicitly set to not accept focus. But on Windows, `WS_EX_TOOLWINDOW` windows have known edge cases. We should verify halo window does not appear as the foreground window.
- **Severity**: LOW-MODERATE. Need to test with halo disabled.

**Issue 4: Only ONE DisplayWidget can own focus via MultiMonitorCoordinator**
- `MultiMonitorCoordinator.claim_focus()` uses first-caller-wins policy. In MC mode, only one display is covered, so this should be fine.
- **Problem**: If the coordinator has stale state (e.g., a previous DisplayWidget instance from a prior run), the new instance might fail to claim focus. This would cause `setFocusPolicy(NoFocus)` and `WindowDoesNotAcceptFocus=True` to be set.
- **Finding**: `release_focus()` is called in `closeEvent()`. If the app crashes or is killed, focus ownership may not be released. But this is a process-level singleton and would reset on restart.
- **Severity**: LOW. Unlikely to be the primary cause in a fresh run.

**Issue 5: Raw Input registration is tied to a specific HWND**
- `handle_nativeEvent()` lazily registers Raw Input with `raw_input.register(hwnd, on_media_key)` where `hwnd` is the DisplayWidget's native window handle.
- **Problem**: If focus shifts to another window, Raw Input messages may still be delivered to the registered `hwnd`. But if the window is not the true foreground window, Windows may not deliver the messages.
- **Finding**: Raw Input can be registered per-thread (hwnd=NULL) or per-window. Our code registers per-window. If the window loses true focus but appears focused, Raw Input may stop delivering to it.
- **Severity**: LOW for the primary issue (keys don't work even when window IS focused after manual click). This is more relevant for Winlogon.

**Issue 6: QOpenGLWidget compositor may have its own native window**
- The GL compositor (`_gl_compositor`) is a `QOpenGLWidget`. On Windows, `QOpenGLWidget` creates an internal native window for rendering.
- **Problem**: If the user clicks on the compositor area, the click may hit the compositor's native child window. Qt's focus system might give focus to the compositor widget instead of the DisplayWidget. The compositor widget may not handle key events.
- **Finding**: `QOpenGLWidget` does not normally accept focus by default. But if it's the only child widget and the parent has `StrongFocus`, focus may still route correctly. This needs testing by disabling the compositor or giving it `NoFocus` explicitly.
- **Severity**: MODERATE-HIGH. This is a strong candidate for the "manual click only" bug because the click target matters.

**Issue 7: Overlay widgets may have default FocusPolicy**
- Overlay widgets (clock, weather, media, Reddit, etc.) are created in `_setup_widgets()`. Most Qt widgets default to `StrongFocus` or `ClickFocus`.
- **Problem**: If any overlay widget has `ClickFocus` and the user clicks near it (even if not directly on it, due to click slop or geometry overlap), the overlay widget may steal focus. Since overlay widgets don't handle key events, keys are "eaten".
- **Finding**: We need to check the focus policy of each overlay widget. `SpotifyVisualizerWidget`, `MediaWidget`, `RedditWidget`, etc. may have `StrongFocus` by default.
- **Severity**: HIGH. This is the **strongest candidate** for the manual-click-only bug. Programmatic focus (`SetForegroundWindow`) sets focus on the top-level window (DisplayWidget), bypassing child widget focus routing. Manual click goes through Qt's focus routing which may land on a child widget.

**Issue 8: perform_activation_refresh() does NOT restore focus**
- `perform_activation_refresh()` updates the compositor and all visible widgets but does NOT call `activateWindow()`, `raise_()`, or `setFocus()`.
- **Problem**: If a child widget steals focus during a manual click, `perform_activation_refresh()` will not reclaim it for the DisplayWidget.
- **Finding**: `_restore_mc_input_focus()` IS called after interactive clicks, which does try to reclaim focus. But if the child widget also runs its own activation logic, there may be a race.
- **Severity**: MODERATE. The `_restore_mc_input_focus()` should handle this, but if it's called after the child widget has already eaten the focus, it may be too late.

### 7.3 Synthesized Root-Cause Model (Speculative)

**Primary hypothesis**: When the user manually clicks into the SRPSS MC window, Qt's focus routing evaluates all child widgets under the cursor. If any overlay widget (GL compositor, media widget, visualizer, etc.) has a non-`NoFocus` policy, Qt gives focus to that child widget. The child widget does not handle key events, so:
- Qt key events (`QKeyEvent`) are delivered to the child widget and dropped (not forwarded to DisplayWidget).
- Native `WM_KEYDOWN` messages may still arrive at the window, but since Qt's focused widget is the child, the `nativeEvent()` handler on DisplayWidget may not be called.
- Media keys sent via Raw Input or `WM_APPCOMMAND` also fail because the window's keyboard input state is owned by a child widget that doesn't process them.

**Why programmatic focus works**: `SetForegroundWindow()` sets the foreground window at the Windows level. Qt's `activateWindow()` or `requestActivate()` then sets the Qt active window to the DisplayWidget top-level. This bypasses the child widget focus routing that happens during mouse click.

**Why defocusing to Display 0 restores keys**: When focus leaves SRPSS entirely, the next key press goes through Windows' normal routing. Since SRPSS is no longer the foreground window, the keys pass through to the system (Spotify/Windows volume). When the user clicks back into SRPSS, the focus routing bug reoccurs.

**Why this only affects MC builds**: Normal builds use `Qt.SplashScreen` instead of `Qt.Tool`. `Qt.SplashScreen` does not set `WS_EX_TOOLWINDOW`, so Windows treats it as a normal popup window with standard focus behavior. The tool window style is what exposes the edge case.

### 7.4 Testable Hypotheses (No-Edit Phase)

1. **H1 (Child Widget Focus Theft)**: Setting `setFocusPolicy(Qt.FocusPolicy.NoFocus)` on ALL child widgets of DisplayWidget prevents the key-eating bug after manual click.
2. **H2 (GL Compositor Focus Theft)**: Explicitly setting `NoFocus` on the GL compositor widget alone prevents the bug.
3. **H3 (Cursor Halo Interference)**: Disabling the cursor halo prevents the bug.
4. **H4 (Overlay Widget Specific)**: Only one specific overlay widget (media, visualizer, Reddit, etc.) causes focus theft. Binary search through disabling widgets will identify it.
5. **H5 (Native Window Handle Collision)**: The GL compositor's internal native window handle receives `WM_MOUSEACTIVATE` and returns a value that prevents proper keyboard focus transfer. Querying the compositor's native window focus state will show it has focus instead of DisplayWidget.
6. **H6 (Qt.Tool Focus Routing Bug)**: Switching MC window from `Qt.Tool` to `Qt.SplashScreen` (with `WS_EX_TOOLWINDOW` removed via `SetWindowLong`) prevents the bug while breaking no-taskbar/no-Alt-Tab behavior.
7. **H7 (_restore_mc_input_focus Race)**: Calling `_restore_mc_input_focus()` with a small delay (`QTimer.singleShot`) after mouse press allows the focus routing to settle and prevents the bug.

### 7.5 Resolution Acceptance Criteria

- MC-focused failure is reproduced by the harness or by an automated observer-backed workflow using physical/hardware ingress evidence.
- MC focused/unfocused transitions no longer change media-key or normal-control-key reliability.
- Fix does not switch MC to splash semantics unless repeated focus-change behavior is proven stable.
- Winlogon runtime media-key behavior is handled as a separate follow-up once MC is stable.
- Historical bug entry (`U-05`) updated with before/after matrix and retained guardrails.

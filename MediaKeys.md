# Media Key Handling

## Status: LL Hook Feature Removed (v1.2+)

The low-level keyboard hook (WH_KEYBOARD_LL) feature for media key passthrough has been **removed** from the codebase as of v1.2. This feature was determined to be more trouble than it was worth due to:

1. **Anti-virus/EDR flagging**: WH_KEYBOARD_LL is the primary mechanism used by keyloggers, causing false positives
2. **Anti-cheat concerns**: Even with low risk, any non-zero risk was unacceptable for some users
3. **Complexity**: Required dedicated thread, message pump, and careful cleanup
4. **Limited benefit**: Only affected naturally-summoned screensaver mode

## Current Media Key Behavior

### MC Builds (Manual Controller)
Media keys work correctly via `WM_APPCOMMAND` passthrough. The MC build uses `Qt.WindowType.SplashScreen` which allows the window to receive media key messages.

### Screensaver Mode
Media keys do NOT pass through to other applications when the screensaver is naturally summoned by Windows. This is due to Winlogon desktop isolation - a security feature of Windows that cannot be bypassed without the LL hook.

**Workaround**: Use the MC build if media key passthrough is required.

## Technical Background

### Why Screensaver Mode Is Different

When Windows launches a screensaver naturally (after idle timeout):
1. Windows switches to a separate desktop (`Winsta0\Winlogon`)
2. The screensaver runs in complete isolation from the interactive desktop
3. `WM_APPCOMMAND` messages cannot broadcast to apps on the default desktop

This is a Windows security feature, not a bug in the screensaver.

### Previous LL Hook Implementation (Removed)

The removed implementation:
- Used `WH_KEYBOARD_LL` to detect media keys at the driver level
- Ran on a dedicated ThreadManager-managed thread
- Always called `CallNextHookEx()` to pass keys through (anti-cheat safe)
- Was opt-in via `input.enable_media_key_hook` setting (default: False)
- Had zero performance impact when disabled

**Removal commits**:
- Deleted: `core/windows/media_key_ll_hook.py`
- Deleted: `tests/unit/core/windows/test_media_key_ll_hook.py`
- Removed: UI checkbox in Display tab
- Removed: Settings key `input.enable_media_key_hook`

## Remaining Media Key Code

The following media key handling remains:

1. **Raw Input** (`core/windows/media_key_rawinput.py`): Detects media keys for visual feedback within the screensaver
2. **WM_APPCOMMAND** (`rendering/display_widget.py`): Handles media keys for MC builds
3. **Visual Feedback**: Media key presses show on-screen feedback when the media widget is enabled

## Future Considerations

If media key passthrough in screensaver mode is needed in the future, alternatives to consider:

1. **User Education**: Document that MC build is required for passthrough
2. **Separate Helper Process**: A lightweight process running on default desktop (complex)
3. **Windows Service**: Requires admin privileges to install

None of these are currently planned. The MC build is the recommended solution.

---

*For historical reference, the original LL hook analysis and implementation details were preserved in git history. This document was rewritten after the feature removal in Feb 2026.*

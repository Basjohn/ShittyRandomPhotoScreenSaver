# Custom Style Implementation

Last updated: 2026-06-30

Guidance for SRPSS settings-dialog and runtime UI styling.

## 1. Goals
- Preserve SRPSS's deliberate custom chrome and dark settings language.
- Keep shared style decisions in shared modules instead of scattering large local QSS blocks.
- Fix focus, startup, visibility, and flicker bugs at their owner instead of removing styling to hide symptoms.

## 2. Current Sources Of Truth
- Dialog chrome and shared settings styling: `ui/settings_dialog.py`, `ui/settings_theme.py`, `ui/tabs/shared_styles.py`.
- Styled confirmations and action feedback: `ui/styled_popup.py`.
- Reusable custom controls: `ui/widgets/` and existing tab helper modules.
- Runtime overlay card/shadow behavior: shared widget/base paint paths, not ad hoc Qt effect churn.

## 3. Styling Rules
- Prefer shared style helpers for buttons, inputs, combo boxes, sliders, buckets, warnings, and popup chrome.
- Keep spacing, typography, border weight, and card language aligned across tabs.
- Do not create popup views, show hidden sections, or force focus changes during constructors just to apply style.
- Action warnings and confirmations should use the shared popup/chrome path.
- Temporary edit-mode controls should read as part of SRPSS but stay visually subordinate to the widget content.

## 4. Safety Rules
- Do not remove shadows, fades, acrylic/framed chrome, or custom controls as a workaround for runtime bugs.
- Avoid broad `setVisible(...)`, `setUpdatesEnabled(...)`, focus-policy recursion, or popup construction during settings load.
- If a styling change affects show/hide behavior, validate it against settings-open, tab-switch, and startup/focus paths.
- Keep live runtime shadows on painter-owned paths unless a future architecture change deliberately says otherwise.

## 5. Change Process
When changing shared styling:
- update the shared style source first,
- migrate local duplicates only where the behavior is the same,
- keep widget/tab-specific exceptions small and named,
- run relevant settings/UI tests,
- and keep runtime/manual validation open for flicker, focus, multi-window, or overlay behavior.

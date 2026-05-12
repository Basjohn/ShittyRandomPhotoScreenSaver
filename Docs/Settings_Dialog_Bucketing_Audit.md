# Settings Dialog Bucketing Audit

Last updated: 2026-05-13

## Purpose
- Track where the settings dialog already has good grouping.
- Identify regions that would benefit from stronger bucketing before more controls are added.
- Keep the title-case wording pass visible so label consistency does not drift again.

## Scope
- `ui/settings_dialog.py`
- `ui/settings_about_tab.py`
- `ui/tabs/display_tab.py`
- `ui/tabs/sources_tab.py`
- `ui/tabs/transitions_tab.py`
- `ui/tabs/widgets_tab.py`
- `ui/tabs/widgets_tab_clock.py`
- `ui/tabs/widgets_tab_media.py`
- `ui/tabs/widgets_tab_reddit.py`
- `ui/tabs/widgets_tab_gmail.py`
- `ui/tabs/widgets_tab_imgur.py`
- `ui/tabs/widgets_tab_weather.py`
- `ui/tabs/accessibility_tab.py`

## Current Top-Level Regions
- `Sources`: already split into `Folder Sources` and `RSS / JSON Feed Sources`.
- `Display`: currently grouped into `Monitor Configuration`, `Display Mode`, `Image Timing`, `Image Quality`, and `Interaction`.
- `Transitions`: already grouped well at the top level, but the advanced per-transition panels are dense.
- `Widgets`: strongest candidate for more bucketing because it hosts both shared widget defaults and multiple widget-specific control families.
- `Accessibility`: already reasonably bucketed into `Background Dimming` and `Widget Pixel Shift`.
- `About`: informational only, but the bottom destructive/import-export actions remain visually dense.

## Bucketing Opportunities
### 1. Widgets Tab
- Status: partially landed on 2026-05-13.
- What landed:
- `Clock`, `Weather`, `Media`, `Reddit`, and `Imgur` now use persisted collapsed buckets while keeping their enable circle checkbox unbucketed.
- Buckets default closed and persist through `ui.widget_bucket_states`.
- The implementation follows the Gmail anti-flicker pattern: defer initial bucket-body visibility and finalize it once after construction, rather than forcing bodies visible during setup.
- Intentionally skipped in this pass:
- `Gmail` (already bucketed and used as the model),
- `Defaults` (small shared section),
- `Visualizers` (already separately structured and intentionally out of scope for this pass).
- Bucket map now in code:
- Clock: `Time Content`, `Layout`, `Appearance`, `Additional Clocks`.
- Weather: `Location & Layout`, `Forecast Content`, `Appearance`.
- Media: `Provider & Layout`, `Appearance`, `Artwork & Header`, `Transport & Volume`.
- Reddit: `Feed & Interaction`, `Layout`, `Appearance`, `Reddit 2`.
- Imgur: `Source & Grid`, `Layout`, `Appearance`.

### 2. Visualizer Controls
- Status: needs a dedicated pass, not an opportunistic edit.
- Why: advanced controls under `ui/tabs/media/` mix presentation, motion, ghosting, glow, layering, and mode-specific shaping in long vertical flows.
- Suggested buckets:
- Shared visualizer regions: `Visibility`, `Color`, `Glow`, `Ghosting`, `Motion`, `Geometry`, `Advanced`.
- Devcurve/Blob/Sine/Oscilloscope/Spectrum builders should adopt a consistent bucket order so mode-switching does not reshuffle the user’s mental model.

### 3. Sources Tab
- Status: medium-value follow-up.
- Why: RSS feed setup, feed hygiene, and disk retention settings are in one long run.
- Suggested buckets:
- `Feed List`, `Autocorrect / Validation`, `Refresh & Staleness`, `Disk Caching`.

### 4. Transitions Tab
- Status: medium-value follow-up.
- Why: shared controls are fine, but transition-specific panels stack densely once advanced options are shown.
- Suggested buckets:
- `Selection`, `Timing`, `Direction / Easing`, `Transition-Specific Advanced`.

### 5. Dialog Footer Actions
- Status: small but worthwhile polish.
- Why: `Reset`, `Import`, and `Export` are important destructive or snapshot actions but live in a busy bottom row with little framing.
- Suggested bucket:
- a dedicated `Configuration Actions` footer treatment or card, visually separated from ordinary tab content.

## Title-Case Pass Status
- Completed in this pass:
- `Display` option labels now use title case for the main toggles and the new `Interaction Mode` label.
- `Reddit` and `Gmail` top-level option labels were normalized where they were still using sentence case.
- `About` hotkey wording now uses `Interaction Mode`.
- The advanced visualizer builders now use title case for the remaining visible option/helper labels that were still mixed-case in Oscilloscope, Sine Wave, Spectrum, and shared builder scaffolding.

- Remaining follow-up:
- review descriptive `QLabel` helper text separately from option labels so we do not over-title-case explanatory prose that reads better as sentences.

## Guidance For Future Passes
- Prefer bucketing by user intent, not by implementation source.
- Keep toggle-heavy rows together, but separate source/auth/refresh concerns from visual styling concerns.
- When adding a new control, decide its bucket first instead of appending it to the nearest existing section.
- Preserve existing tab order unless a reordering solves a real navigation problem.

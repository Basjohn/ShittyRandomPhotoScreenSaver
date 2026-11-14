# R-222 | A built Widgets page saved its stale position back over a Layout tab write

**Status:** fixed 15 Nov 2026 (plan item 1D.12 A, commit `1b8573bb0`). Present since Arrange and Reset Widget Layouts
moved onto Settings' Layout tab beside an already-built Widgets tab.

`LayoutPage.widgetsWritten` (`ui/onboarding/layout_page.py`) fires after the Layout tab writes widget positions or
display routes (Arrange Apply through `ArrangePage.applied`, Reset Widget Layouts), and
`SettingsDialog._reload_widgets_tab_after_layout_write` (`ui/settings_dialog.py`) reloads the Widgets tab when it is
already built (never constructing it). No timer, no `settings_changed` listener (other tabs write `widgets` too).

Regression bar: `tests/test_widget_position_follows_layout_writes.py` on the real SettingsDialog (popup `exec`
patched): a Media page built before an Arrange move reads Custom, an unrelated Media edit keeps Custom, a named
position afterwards keeps the saved geometry, Reset Widget Layouts leaves Custom. Negative control: with the reload
disconnected, 3 of those fail ("Top Left" shown; "Top Left" saved over "Custom"). A widget with no saved custom
layout never offers CUSTOM.

## Symptom

Silent: after moving a widget in Arrange (or resetting layouts) with that widget's Widgets page opened earlier in the
same Settings session, its Position dropdown kept the old named position with CUSTOM greyed out. Any later edit on
that page (font size, a checkbox) saved the whole page, writing the named position back over `"Custom"`: the widget
left its custom geometry without the operator choosing to. The reverse after Reset Widget Layouts: the page kept
showing Custom and could write it back. Every widget with a position dropdown, not only Now Playing.

## Cause

Widgets pages load their controls once, when built (lazy hydration), and save every control of the page on each
edit. The Layout tab writes the same `widgets` map directly through `SettingsManager.set`, and nothing told the built
Widgets tab to reload. The save path then treated its stale controls as the operator's intent. A dialog opened after
the move was always right, which hid it: the persisted data and the load path were correct.

## Lesson

A page that saves its whole section from its controls must be reloaded at every edge where another page writes that
section in the same dialog. When a fresh dialog shows the right value but the open one does not, look for a second
writer, not at the data.

# R40: Hover glyph first-click recovery / themed tooltip feasibility | UNACCEPTED

## Operator observations

- Clicking ordinary-mode Lock enters Edit but does **not** unlock child editing. The source routes `requestToggleChildEditLockForWidget` immediately after the new Edit owner starts, but its QML handler previously walked only delegates already instantiated by the Repeater. No delegate yet meant the request was silently dropped. This is a **credible failure mechanism**, not independently confirmed as the only native cause.
- Repeated `Attempting to set another interceptor ... parentGlyphControlsOpacity` warnings have a **confirmed source cause**: two `Behavior on parentGlyphControlsOpacity` declarations in each Edit delegate.
- Ordinary/Visualizer hover action rows were upper-right, not operator-requested bottom-left. Hover close X could be larger without expanding the click target.

## Source candidate

- Removed the duplicate `Behavior` on the Edit opacity property. Retained the 700 ms appearance / 1200 ms disappearance animation, no new timers.
- `CustomLayoutOverlay.qml` now retains **one pending semantic Lock request, scoped to the current `sessionModel`**. It tries the existing frame immediately; if it has not materialized, `Repeater.onItemAdded`, frame `Component.onCompleted` and availability of `presentationItem` retry **from events only**. The request is cleared before toggling, and is discarded at session/model retirement. No extra child-state bit, persistence owner, geometry authority, fake pointer click or second Edit session. Python owner admission/capability checking stays unchanged.
- `WidgetHoverEditGlyphs.qml` places the shared action row at bottom-left for ordinary and visualizer cards, with 8-pixel inset. The close X text changes from 15 to 18 pixels; the 24x24 button/hitbox and others stay unchanged.
- Edit-only glyphs retain their family-specific arrangement and the unique Hide Controls wedge. Moving **those** edit handles to a consolidated lane requires separate collision/hit-test analysis against resize, header, corner, rotate and transfer controls. Do not move them under the pretence that the common hover row governs those arrangements.

## Native validation needed

- New `tests/test_r40_lock_immediate_edit_native.py` uses a real retained CUSTOM model and actual QML frame, sends the lock signal before processing pending Qt events, verifies child unlock and repeat toggle, then rebinds a new session. This protects the precise first-click edge instead of asserting only a model method name.
- User should visually verify hover Lock when unselected → Edit → child handles appear, then click again → child handles disappear, including tiny cards and quick session Save/Cancel. Verify no interceptor warning, glyphs bottom-left on multiple families and visualizer, close X appears slightly larger but the button doesn't.
- Pending request must never replay after target removal, display/session change or Edit exit. Existing native R39 handoff checks remain unaccepted; there is no claim that passing these focused tests proves every multiscreen handoff safe.

## Themed compositor tooltip feasibility (assessment only; NOT implemented)

Feasible without introducing a thread or background poller, **provided it uses Qt Quick presentation items and existing hover signals**. Proposed design: one per-display retained, normally dormant tooltip presenter over the compositor scene, supplied with short semantic action text and one current anchor. An admitted `MouseArea`/`HoverHandler` updates the active tooltip on pointer enter/leave. A slow opacity transition runs only during an actual hover state change; otherwise there is no paint/update obligation or compositor refresh. Use on-demand Text/Rectangle or a single lazy Loader, not a `QtQuick.Controls.ToolTip` Popup per glyph or extra Window, and keep all glyphs using the same presenter. Avoid cross-thread Qt objects, Python callbacks per pointer move, repeated QML object allocation, polling, timers and new animation clocks. A passive tooltip must never intercept mouse/keyboard, enter the Edit owner or hold a stale widget reference through retirement.

- **GIL:** pure QML hover state and text paint do not create Python threads or new GIL competition. One discrete Python bridge on glyph-enter, if unavoidable, would be much less concerning than per-frame traffic, but existing QML-local text is preferable.
- **Memory:** one display-scoped presenter is small and bounded, not per-widget or per-glyph retained Popup trees; actual GPU/text atlas cost needs measurement. Qt Quick may cache text glyphs, but does not require a dedicated framebuffer per tooltip.
- **CPU/GPU:** hover animations incur bounded work during fade. No render-loop work while hidden; quantify incremental rendering/layout cost and check 120/165 Hz dual-display behavior before acceptance.
- **Placement:** position in display-local coordinates with border/DPR clipping, and flip sides near edges. Revalidation required if mouse moves between widgets, Edit starts, or runtime generation retires.
- **Timing:** start with a deliberately slow, gentle fade; avoid tooltip dwell `Timer`. If delay is desired later, prefer a single opt-in animation sequence strictly while hovered, and measure. Do not couple tooltip admission to Widget Glow and do not reveal it without Interaction Mode/Ctrl.

This is a *feasibility result*, not permission to implement before visual verification of R40 Lock and glyphs. Keep all previous EB musical, optical, camera and lifecycle checklists intact.

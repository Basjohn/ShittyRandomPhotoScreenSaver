# Guided Setup and Quick Start

Guided Setup is a lazy panel shown inside the Settings window (it replaces the sidebar and tabs while it runs, so it
shares Settings' theme and backdrop). With no folders or wallpaper feeds, Settings makes one deferred
decision after its shell is shown: open Guided Setup, or show the existing No Image Sources popup when
`sources.guided_setup_silenced` is true. Sources present means no automatic prompt. The Settings close guard still
requires an image source. QUICK START always allows a manual rerun, regardless of Silence; there is no completion flag.

## Owners and choices

`ui/onboarding/wizard.py` owns page navigation. Pages are built on first visit and edit the ordinary Settings keys
through `ui/onboarding/draft.py:SettingsDraft`, never the store itself: saving is explicit. Finish commits the draft
(and any unapplied Arrange edits). Skip sits in the header on every page (there is no separate Close); with anything
unsaved, Skip or closing Settings asks Keep Changes / Discard Changes / Stay In Setup, and dismissing that prompt
means Stay. A discard also restores the live theme the Theme page previewed. Explicit save buttons inside pages
(Save to Slot, account Save & Test, Import Settings) write straight through.
`core/sources/readiness.py` is the shared source-readiness rule; `sources/rss/curated.py` is the one Just Make It Work
operation used by Sources, the close popup and Guided Setup.

Copy follows one casing rule (`ui/onboarding/common.py:title_case`): Title Case with short joining words and
prepositions lowercase, short tags in ALL CAPS, user data (paths, URLs, addresses) never re-cased. The panel paints a
20% veil inside its border (black behind light text, white behind dark) so Glass stays readable on bright desktops.

- Welcome offers **Import Settings?** (`ui/settings_import.py`, shared with Settings → About): choose ALL SETTINGS or
  Display, Widget, Transition, Theme Choice, Custom Geometry Including Layouts and Misc. A partial import merges only
  those parts (`core/settings/sst_io.py:filter_snapshot_categories`); credentials never travel. Import writes the
  store directly (explicit), and success drops the wizard draft and finishes Guided Setup.
- Sources is two large buckets, Folders and Online Wallpaper Feeds (feeds need internet). Custom feed addresses are
  added there through the same autocorrect as the Sources tab (`ui/tabs/sources_tab.py:autocorrect_feed_url`).
- Displays: clicking a display in the diagram switches it on or off (filled when on); one display always stays on.
  Each is listed with the resolution Windows shows and its scale (`2560 × 1440 · 150%`), read from the monitor
  (`core/windows/monitor_resolution.py`), never Qt's rounded logical size. Leaving the page (and Finish) with exactly
  one display selected routes every widget the saver could not show onto it (`route_widgets_to_single_monitor`:
  numbered routes elsewhere move; `ALL` stays; authored restore routes follow).
- Interaction: Media Center builds keep interaction on, so the screensaver-only choice is greyed with a tooltip.
- Widget Setup (large buckets) includes Clocks: the shared analogue/digital face and a timezone per enabled clock.
  Choosing a face clears per-display face overrides so the choice shows everywhere.
- Large buckets are `build_bucket_toggle(..., large=True)`: the theme QSS keys a quarter-larger geometry on the
  `bucketSize` property.

Displays use the existing ALL or 1-based monitor selection. The theme page and full Themes tab share
`ui/settings_theme_selection.py`; the existing Keep Synced relationship alone controls Widget Theme changes.
Interaction writes `input.interaction_mode`; the practice card has no network or browser behavior.

Widget families and dependency admission come from the canonical family catalog and capability normalizer.
Member controls write their original settings sections, including Media-owned volume/mute controls. Setup sections
exist only for selected dependencies. Weather lookups begin only after typing, subreddit validation is local, and
FEEDS News selection preserves existing publishers. FEEDS Custom 1–4 card authoring stays in full Settings (custom
wallpaper feed addresses are added on the Sources page).

Visualizer mode choices use the mode registry and retain at least one mode. Sphere is offered only if already
admitted. Transition choices edit activation and pool through the existing normalizer, preserving Random behavior.
Advanced widget, mode and transition controls remain in their full Settings pages.

## Accounts and retirement

`core/windows/desktop_context.py` checks the calling thread's desktop through Win32. Steam and Gmail inputs and
browser actions are admitted only on the interactive Default desktop; unknown/noninteractive desktop is denied.
The secure URL handoff remains the browser authority. Accounts are optional and missing setup never blocks Finish.

`core/account_setup/controllers.py` is shared by Guided Setup and the full account pages. Guided Setup's Steam section
reuses the Settings Steam connection flow and popups (`ui/tabs/widgets_tab_steam.py`) on a small host object, so a
saved connection shows as Connected; closed Steam/Gmail buckets read "· CONNECTED" from non-secret storage status.
Steam validates before encrypted replacement; Gmail tests IMAP before the GUI thread commits through the existing
backend/storage owner. The Gmail bucket also offers the new-mail sound (play, file, Test, volume).
No account secret is a wizard setting, preview fixture or log field. Settings summaries inspect only non-secret
saved-connection metadata. Account workers start only on explicit actions and completion is fenced by page lifetime.
Leaving the conditional Setup page clears password inputs, closes its OpenID callback and retires its geocoder and
any locally owned helper manager.

## Arrange and saved layouts

`ui/onboarding/arrange_model.py` stages a `CustomLayoutSession`; `rendering/custom_layout_commit.py` is the shared
commit owner for Settings Arrange and Runtime Edit. The canvas is a projection of selected screens in Qt logical
coordinates. Merely opening, selecting or dragging does not persist. In Guided Setup, Apply/Next applies the
arrangement to the wizard draft, which Finish saves; Discard drops it. Quick Start reuses the same editor (created only
when its bucket opens), where Apply saves directly.

The canvas uses the saver's own geometry, so boxes land where they are drawn:

- **Sizes.** `rendering/quick/widgets/preferred_size_measurement.py` measures each widget's preferred size through
  its family's own QML: the family adapter's `presentation_model` (the same construction `build` uses) and card style,
  the registered component, `preferredContentWidth/Height`, then the item is deleted. Items never enter a window or
  scene and no service is attached, so fonts, DPR and text metrics are this machine's. One meter lives with the Arrange
  page, created when it opens; results are memoized per size-relevant draft fingerprint (placement fields, CUSTOM
  entries and slots excluded), so moves and resets reuse them and a real setting change re-measures once. The
  Visualizer is sized by its own `resolve_visualizer_presentation` (authored viewport fitted to the display).
- **Units.** Layout is Qt logical pixels in both the saver and Arrange (`QScreen.geometry()`); only text shown to
  people (display captions, box sizes) is device pixels, from each display's own resolution and scale.
- **Clock faces.** A Clock's geometry variant is the face the saver presents (`clock_geometry_variant`: Clock 2/3
  inherit the main Clock's face, per-display overrides by display signature).
- **Placement.** Uncommitted boxes are placed by `rendering/quick/widgets/authored_layout_projection.py`, which
  composes the display presenter's anchor policy, display-wide stacking/shrink and `DisplayManager`'s Media+Visualizer
  docking with the saver's inputs and build order. Under global CUSTOM they sit on plain anchors and an uncommitted
  Visualizer on Media's slot, exactly as the saver shows them.
- **Apply.** CUSTOM is global, so once the operator places anything Apply saves every box where the canvas shows it,
  as content-sized placements at their nearest anchor (Runtime Edit's Save also keeps the visible layout). Viewing or
  loading a slot alone commits nothing, and a box returned to its anchor with Reset stays authored; it is drawn where
  the saver will put it after Apply.

Placements persist an anchor and uniform scale in the existing CUSTOM payload, with `_size_from_content: true` and
`_placement_anchor`; runtime resolves the live content size at that anchor. Explicit saved entries retain explicit
sizing. Runtime Edit preserves content sizing for move-only saves and converts to explicit geometry when a measured
resize, extent or child edit requires it. Child geometry and content rotation remain Runtime Edit operations.

Width-only and height-only resize (side handles) use the same math as Runtime Edit
(`rendering/quick/custom_layout_size.py`: `edge_resize_rect`, `content_extent_resize_payload`, snapped by
`resolve_resize_edge_snap`). Settings offers them only when every input is already persisted
(`settings_content_extent_edges`): a logical box saved by Runtime Edit (a preferred size is not the live content box
a side drag reflows), a floor declared by the family descriptor (Achievement Pulse and Abandonment Issues use
a live authored-size floor) and no customized children (their room is reported only by the live family). Otherwise the
selection line says to resize once in the saver's Edit mode. Reset uses the session's authored-size restore, which
drops a saved box.

The Free placement checkbox derives from CUSTOM state. Reset removes the selected parent placement and restores
authored position/monitor routing; other displays' child customizations remain intact. The global Reset Widget Layouts
action uses the established reset owner and retains content settings, credentials and saved slots.

Slots use `core/settings/layout_slots.py`: Load into editor changes only a draft, Save requires a committed layout,
and occupied-slot replacement is confirmed. Existing runtime shortcuts remain 1–9/0 to load and Shift with those keys
to save. Slots include layout fields such as fonts, monitors and Clock face choices, not sources or credentials.

## Dormancy and preview maintenance

Quick Start is excluded from background Settings hydration. Closed onboarding has no timer, worker, provider, QML
root, audio consumer or preview cache; Arrange's size meter and its private QML engine exist only while an Arrange page
does. Static PNGs decode only on the visited page; artwork rescales only on geometry
or DPR changes using the same helper as About. Arrange never starts a screensaver runtime or data provider.

`python tools/onboarding_preview_foundry.py` authors the bundled `images/onboarding` PNGs. It is never imported or
run by onboarding.

- Widgets render through the production retained presenters with fictional local fixtures, each card enabled, via
  `QQuickRenderControl` into a hidden GL texture (operator-approved Windows-QPA `QOffscreenSurface`; no window is
  ever shown). The offscreen QPA has no GL and silently drops logos, shadows and effect layers, so it is not used.
- When the operator's unshipped screenshot sheet `tools/onboarding_sources/MEGASHEET.png` is present,
  `tools/onboarding_sheet_previews.py` replaces every widget preview except Clocks with cut-outs of the real cards
  (card rectangles are data in that tool; re-measure them if the sheet is replaced).
- Every widget preview is transparent around its card with a free-hanging SE shadow, so it sits on any theme.
- Visualizer mode previews (`visualizer_<mode>.png`) are cut from the operator's unshipped
  `tools/onboarding_sources/Visualizers.png`; Voxel Sphere has no card there, so it keeps its background inside a
  drawn frame. Without the sheet, a rebuild keeps the committed previews. The page shows a narrow mode list (sized
  to its longest name, never truncated) with the selected mode's preview beside it.
- Widget previews render at 2x device pixels (the sheet is a 2x screenshot and is cut at native size). Settings
  shows them at no more than one source pixel per physical pixel (`ImagePanel(..., upscale=False)`), so small cards
  stay sharp at their true size instead of being stretched.
- Transition strips sample 25%, 50% and 75% of the resolved effect (Block Spins samples off its edge-on midpoint)
  from the operator artworks `GonnadsBIIIGYProdBlue.jpg` -> `MassiveDS.jpg`, as three unlabelled 800x450 frames
  side by side. `TransitionStrip` paints the gaps and the percentage labels as live text, 90% of the page width.
- Captures wait for decoded logos, avatars and artwork and for artwork fades; a readiness failure is a capture
  failure, not permission to ship a blank placeholder. Lossless PNG only (never JPEG), 24 MB budget; a rebuild
  removes generated files the new set no longer contains.

The build asset check requires the preview directory and operator-provided `images/SRPSSWitch.png`. See
`Docs/Architecture/Persisted_Input_Compatibility.md` for content-sized CUSTOM downgrade behavior. The mechanisms behind
the 2026-09-27 review's defects are recorded in `Docs/Historical_Bugs/R-101_Guided_Setup_Settings_Review_2026-09-27.md`.

## Physical acceptance (open)

Implementation and automated coverage are complete; one operator pass on the real saver remains:

- fresh/no-source automatic Guided Setup; Witch artwork and exact welcome copy;
- source requirement;
- Just Make It Work → exact lazy prompt → both choices;
- Skip from the header with unsaved changes: Keep Changes, Discard Changes (theme reverts), Stay In Setup;
- nothing is saved before Finish (close Settings mid-way and reopen);
- Welcome → Import Settings? by category (an import finishes the wizard);
- Sources buckets, a custom feed address, clicking displays in the diagram, Interaction greyed on MC;
- Widget Setup: Clocks face/timezones, Steam shows a saved connection, Gmail notification sound + Test;
- Silence → old no-source popup;
- live Theme switch; monitor selection; Interaction demo;
- widget previews and selections;
- one Steam/Gmail/Weather/Reddit/FEEDS setup path, including the D1 message when started by Windows as the screensaver;
- transition and Visualizer mode previews (sharp at your DPR; the transition list does not scroll on hover);
- saver right-click → Images → Save Image (first save adds Pictures/SRPSS Collections to sources);
- Arrange geometry: after a full settings delete and the wizard, the boxes match the saver's cards on each display
  and DPR (sizes, Visualizer docked to Media, stacked cards apart); move one, Apply, and every widget lands where it
  was drawn;
- Arrange: free-place and scale a never-moved widget (it keeps its real size on the saver); move, scale and
  reassign the display of an already-customised widget; tick and untick Free placement; load a layout slot (Apply and
  Cancel); save to a slot, then load it on the saver with its number key;
- Runtime Edit sees Quick Start changes, and Quick Start sees a later Runtime Edit change;
- child edits survive parent manipulation;
- final runtime start;
- Settings → QUICK START lazy reopen;
- no network or provider work while Quick Start and Arrange are closed.


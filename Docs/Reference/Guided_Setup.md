# Guided Setup and Quick Start

Guided Setup is a lazy panel shown inside the Settings window (it replaces the sidebar and tabs while it runs, so it
shares Settings' theme and backdrop). With no folders or wallpaper feeds, Settings makes one deferred
decision after its shell is shown: open Guided Setup, or show the existing No Image Sources popup when
`sources.guided_setup_silenced` is true. Sources present means no automatic prompt. The Settings close guard still
requires an image source. QUICK START always allows a manual rerun, regardless of Hide This From Now On (Quick Start: Hide Guided Setup From Now On); there is no completion flag.

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
  the registered component, then Qt's own layout (polish) pass through a `QQuickRenderControl` window that is never
  shown, until `preferredContentWidth/Height` settle; then the item is deleted. The polish pass is required: Column/Row
  positioners size themselves only when polished (unpolished, Weather read 119 px against the saver's 250/374 px). A
  family whose size follows its data measures the state data brings (Weather's `present_measurement_sample`, only
  with a location). A content-sized entry measures as its payload presents it (Clock's saved font). No service is
  attached, so fonts, DPR and text metrics are this machine's. One meter lives with the Arrange page, created when it
  opens; results are memoized per size-relevant draft fingerprint (placement fields, CUSTOM entries and slots
  excluded). The Visualizer is sized by its own `resolve_visualizer_presentation` (authored viewport fitted to the
  display).
- **Units.** Layout is Qt logical pixels in both the saver and Arrange (`QScreen.geometry()`); only text shown to
  people (display captions, box sizes) is device pixels, from each display's own resolution and scale.
- **Clock faces.** A Clock's geometry variant is the face the saver presents (`clock_geometry_variant`: Clock 2/3
  inherit the main Clock's face, per-display overrides by display signature).
- **Committed boxes.** Explicit entries are their stored rectangle; content-sized entries are drawn where the saver
  resolves them, at their anchor with today's measured size (`resolve_overlay_geometry_policy`; the Visualizer through
  `resolve_committed_visualizer_rect`, the same rule `DisplayManager` uses).
- **One Visualizer.** The saver runs exactly one, on its requested display when shown, otherwise the first shown
  display (`resolve_quick_visualizer_owner_unit`). Arrange shows it only there, never once per display.
- **Displays.** The canvas follows the shown displays whenever the page is shown and when a screen is added or
  removed; a pending draft is carried onto the new display set (Discard still restores Settings).
- **Placement.** Uncommitted boxes are placed by `rendering/quick/widgets/authored_layout_projection.py`, which
  composes the display presenter's anchor policy, display-wide stacking/shrink and `DisplayManager`'s Media+Visualizer
  docking with the saver's inputs and build order. Under global CUSTOM they sit on plain anchors and an uncommitted
  Visualizer on Media's slot, exactly as the saver shows them.
- **Apply.** CUSTOM is global, so once the operator places anything Apply saves every box where the canvas shows it:
  moved or untouched boxes as content-sized placements at their nearest anchor, resized ones as explicit boxes, exactly
  as Runtime Edit's Save does. Viewing or
  loading a slot alone commits nothing, and a box returned to its anchor with Reset stays authored; it is drawn where
  the saver will put it after Apply.

Content-sized placements persist an anchor in the existing CUSTOM payload, with `_size_from_content: true` and
`_placement_anchor`; runtime resolves the live content size at that anchor. Explicit saved entries retain explicit
sizing. Both editors save a never-placed card as content-sized (a card still loading, such as Weather before its first
data, is never frozen at its loading size), preserve content sizing for moves and convert to explicit geometry on any
resize (uniform scale, width/height) and, in Runtime Edit, on child edits.

**Unapplied Arrange changes.** Arrange under Settings → Quick Start applies nothing until Apply. Closing Settings (close
button, Enter or Escape), switching to another Settings tab, or starting Guided Setup with a pending draft asks once,
in the shared styled popup: Apply Changes, Discard Changes or Stay In Arrange (closing the popup stays). Guided
Setup's Arrange step asks the same on Back and Next (Apply there applies to the wizard's draft, saved at Finish); Skip
or closing Settings keeps the wizard's own Keep/Discard/Stay prompt.

**Finish and Finish & Run.** The last step offers both; both save. Finish & Run then closes Settings asking to run
(`SettingsDialog.request_run_after_close`): a running saver, or a RUN launch waiting on Settings for image sources,
resumes on close with the saved settings; a Settings-only (CONFIG) launch continues into RUN in the same process
(`main.run_config_session`), as a RUN launch resumes after source onboarding. Staying at a close prompt cancels it. Child geometry and content rotation remain Runtime Edit operations.

Sizing is Runtime Edit's own, so the same gesture in either editor saves the same entry. Uniform scale (corner drag,
Ctrl+wheel, slider) uses `uniform_scale_geometry` in `rendering/quick/custom_layout_size.py`, which Runtime Edit calls
too: the top edge and horizontal centre stay put, limits and payload are Edit's, and a Visualizer with its own world
scales that world. A corner drag measures `uniform_corner_drag_scale` from its start and snaps one edge to a nearby
peer line; Ctrl+wheel steps 5% of scale (`uniform_wheel_scale`); the slider scales about the same point. The
Visualizer's corners change its width and height together with the opposite corner fixed, as Runtime Edit's do.

Width-only and height-only resize (side handles) exist for every axis a widget has (`settings_side_edges`): each
declared content-extent axis, and both axes of the Visualizer's viewport world. They use Runtime Edit's own math
(`rendering/quick/custom_layout_size.py`: `edge_resize_rect`, `resolve_resize_edge_snap`, `content_extent_resize_payload`
and, for the Visualizer, `viewport_extent_resize_payload`, which Runtime Edit calls too). A box with no saved extent
starts from its measured size, exactly as Runtime Edit's first side drag starts from the live one. Minimums are the
shared ones: the family's declared floor, raised to the measured natural size where a family floors there
(Achievement Pulse, Abandonment Issues), plus any room customized children report. Every declared floor is the box
the card really reflows into (`tests/test_content_extent_minimum_contract.py`), so a handle never leaves a card shrunk
inside empty space. Arrange is an outer-widget editor:
children are never shown or edited here, and their saved payload is carried unchanged through moves and resizes.
Clocks scale uniformly only, in both editors. A real resize makes the entry explicit, as in Runtime Edit. Reset uses
the session's authored-size restore, which drops a saved box.

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

`python tools/onboarding_preview_foundry.py` authors the bundled `ui/assets/onboarding/source` PNGs. It is never imported or
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

The build resource prerequisite checks the preview sources and operator-provided `ui/assets/onboarding/source/SRPSSWitch.png`,
then regenerates the binary `ui/resources/onboarding_assets.rcc` pack when stale. Runtime registers that pack through
`QResource` only when Guided Setup explicitly requests an asset; its existing `:/srpss/onboarding/...` identities do
not change. See
`Docs/Architecture/Persisted_Input_Compatibility.md` for content-sized CUSTOM downgrade behavior. The mechanisms behind
the 2026-09-27 review's defects are recorded in `Docs/Historical_Bugs/R-101_Guided_Setup_Settings_Review_2026-09-27.md`.

## Optional operator-triggered physical review

The implemented feature is operator-accepted. Use the following checklist only if reopening a specific Guided Setup/Quick Start concern or when requesting fresh installed proof:

- [ ] fresh/no-source automatic Guided Setup; Witch artwork and exact welcome copy;
- [ ] source requirement;
- [ ] Just Make It Work → exact lazy prompt → both choices;
- [ ] Skip from the header with unsaved changes: Keep Changes, Discard Changes (theme reverts), Stay In Setup;
- [ ] nothing is saved before Finish (close Settings mid-way and reopen);
- [ ] Welcome → Import Settings? by category (an import finishes the wizard);
- [ ] Sources buckets, a custom feed address, clicking displays in the diagram, Interaction greyed on MC;
- [ ] Widget Setup: Clocks face/timezones, Weather location and Show 5-Day Forecast, Steam shows a saved connection,
  Gmail notification sound + Test;
- [ ] Hide This From Now On (wizard) / Hide Guided Setup From Now On (Quick Start) → old no-source popup;
- [ ] live Theme switch; monitor selection; Interaction demo;
- [ ] widget previews and selections;
- [ ] one Steam/Gmail/Weather/Reddit/FEEDS setup path, including the D1 message when started by Windows as the screensaver;
- [ ] transition and Visualizer mode previews (sharp at your DPR; the transition list does not scroll on hover);
- [ ] saver right-click → Images → Save Image (first save adds Pictures/SRPSS Collections to sources);
- [ ] Arrange geometry: after a full settings delete and the wizard, the boxes match the saver's cards on each display
  and DPR (sizes, Visualizer docked to Media, stacked cards apart, Weather at its with-data height); move one, Apply,
  and every widget lands where it was drawn; width-only/height-only on a card and on the Visualizer land exactly;
  with two displays and Media on ALL there is one Visualizer; turning a display on while Arrange is open shows it;
- [ ] Arrange: free-place and scale a never-moved widget (it keeps its real size on the saver); move, scale and
  reassign the display of an already-customised widget; tick and untick Free placement; load a layout slot (Apply and
  Cancel); save to a slot, then load it on the saver with its number key;
- [ ] Arrange: move a widget and, without Apply, close Settings (and separately: switch tab, press Escape, start Guided
  Setup) — the Apply/Discard/Stay popup appears each time; Stay keeps the draft and Quick Start in view; Apply shows the
  move on the saver; Discard drops it. In Guided Setup's Arrange step the same popup appears on Back and on Next;
- [ ] Finish & Run from standalone Settings (Windows Screen Saver Settings → Settings, or the MC Settings launch), from
  Settings opened on the running saver, and from a saver launch that opened Settings for missing sources: each saves
  and starts (or resumes) the saver with the new settings; Finish only saves;
- [ ] Runtime Edit on first run or offline (Weather still loading): Save without touching Weather; once data arrives,
  Weather grows to its full card instead of shrinking inside a short box;
- [ ] Ready step: the Settings / Edit Widget Layout menu capture sits beside the summary, sharp at your DPR, with no
  scrollbar and the Controls block unmoved;
- [ ] Widget Setup → Gmail: labelled rows with Steam's spacing, green "Connected" when a connection is saved, the volume
  slider in the Settings style;
- [ ] Reddit narrower than its header plus refresh glyph (a long subreddit name, ~340 px): the ↻ glyph hides instead of
  overlapping, and comes back when widened;
- [ ] Arrange sizing matches Runtime Edit: scale a card up with Ctrl+wheel in Edit mode, Save, then one Ctrl+wheel notch
  down in Arrange returns it to the same place (top edge and centre fixed); a corner drag scales about the same point;
  the Visualizer's corner changes width and height together; width/height on Reddit, Gmail or Friend Pulse stops where
  the card still fills its box;
- [ ] Runtime Edit sees Quick Start changes, and Quick Start sees a later Runtime Edit change;
- [ ] child edits survive parent manipulation;
- [ ] final runtime start;
- [ ] Settings → QUICK START lazy reopen;
- [ ] no network or provider work while Quick Start and Arrange are closed.

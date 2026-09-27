# Guided Setup and Quick Start

Guided Setup is a lazy, Settings-owned dialog. With no folders or wallpaper feeds, Settings makes one deferred
decision after its shell is shown: open Guided Setup, or show the existing No Image Sources popup when
`sources.guided_setup_silenced` is true. Sources present means no automatic prompt. The Settings close guard still
requires an image source. QUICK START always allows a manual rerun, regardless of Silence; there is no completion flag.

## Owners and choices

`ui/onboarding/wizard.py` owns page navigation. Pages are built on first visit and edit the ordinary Settings keys
through `ui/onboarding/draft.py:SettingsDraft`, never the store itself: saving is explicit. Finish commits the draft;
Skip (or closing Settings) asks Save/Discard when anything is pending; a discard also restores the live theme the
Theme page previewed. Explicit save buttons inside pages (Save to Slot, account Save & Test) write straight through.
`core/sources/readiness.py` is the shared source-readiness rule; `sources/rss/curated.py` is the one Just Make It Work
operation used by Sources, the close popup and Guided Setup. Skip sits in the Guided Setup header (there is no
separate Close); it leaves at any step, offers an unapplied Arrange draft first and changes no other settings.

- Sources is two large buckets, Folders and Online Wallpaper Feeds (feeds need internet). Custom feed addresses are
  added there through the same autocorrect as the Sources tab (`ui/tabs/sources_tab.py:autocorrect_feed_url`).
- Displays: clicking a display in the diagram switches it on or off (filled when on); one display always stays on.
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
FEEDS News selection preserves existing publishers. Custom feed authoring stays in full Settings.

Visualizer mode choices use the mode registry and retain at least one mode. Sphere is offered only if already
admitted. Transition choices edit activation and pool through the existing normalizer, preserving Random behavior.
Advanced widget, mode and transition controls remain in their full Settings pages.

## Accounts and retirement

`core/windows/desktop_context.py` checks the calling thread's desktop through Win32. Steam and Gmail inputs and
browser actions are admitted only on the interactive Default desktop; unknown/noninteractive desktop is denied.
The secure URL handoff remains the browser authority. Accounts are optional and missing setup never blocks Finish.

`core/account_setup/controllers.py` is shared by Guided Setup and the full account pages. Steam validates before
encrypted replacement; Gmail tests IMAP before the GUI thread commits through the existing backend/storage owner.
No account secret is a wizard setting, preview fixture or log field. Settings summaries inspect only non-secret
saved-connection metadata. Account workers start only on explicit actions and completion is fenced by page lifetime.
Leaving the conditional Setup page clears password inputs, closes its OpenID callback and retires its geocoder and
any locally owned helper manager.

## Arrange and saved layouts

`ui/onboarding/arrange_model.py` stages a `CustomLayoutSession`; `rendering/custom_layout_commit.py` is the shared
commit owner for Settings Arrange and Runtime Edit. The canvas is a projection of selected screens in Qt logical
coordinates. Merely opening, selecting or dragging does not persist. Apply/Next commits; Discard or closing the
wizard drops the draft. Quick Start reuses the same editor, created only when its bucket opens.

Settings cannot measure live QML content. New free placements therefore persist an anchor and uniform scale in the
existing CUSTOM payload, with `_size_from_content: true` and `_placement_anchor`. Their displayed bounds are estimates;
runtime resolves the actual content size at that anchor. Explicit saved entries retain explicit sizing. Runtime Edit
preserves content sizing for move-only saves and converts to explicit geometry when a measured resize, extent or child
edit requires it. Width/height reflow, child geometry and content rotation remain Runtime Edit operations.

The Free placement checkbox derives from CUSTOM state. Reset removes the selected parent placement and restores
authored position/monitor routing; other displays' child customizations remain intact. The global Reset Widget Layouts
action uses the established reset owner and retains content settings, credentials and saved slots.

Slots use `core/settings/layout_slots.py`: Load into editor changes only a draft, Save requires a committed layout,
and occupied-slot replacement is confirmed. Existing runtime shortcuts remain 1–9/0 to load and Shift with those keys
to save. Slots include layout fields such as fonts, monitors and Clock face choices, not sources or credentials.

## Dormancy and preview maintenance

Quick Start is excluded from background Settings hydration. Closed onboarding has no timer, worker, provider, QML
root, audio consumer or preview cache. Static PNGs decode only on the visited page; artwork rescales only on geometry
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
`Docs/Future_Work/Guided_Setup.md` for remaining acceptance and `Docs/Architecture/Persisted_Input_Compatibility.md`
for content-sized CUSTOM downgrade behavior.

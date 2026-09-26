# Guided Setup / Quick Start | implementation plan (live checklist)

**Status:** ACTIVE, implementation in progress. This file owns execution of the feature. Tick items as they land and delete
nothing until the feature ships; then move the durable parts into `Docs/Reference/Guided_Setup.md` and
`Docs/Contracts.md` and retire this file. `Current_Plan.md` only points here.

**Goal:** a complete GUIDED SETUP wizard and a permanent QUICK START Settings page, taken through implementation,
automated tests, generated preview assets, docs/contracts and the agent's own visual inspection. The operator's only
role is one final physical acceptance pass (§ Final operator handoff). Do not stop for ordinary design questions that
the architecture and this plan answer. All design decisions below are settled (§2); stop only for a real blocker.

---

## 0. Read first (every session)

1. `Index.md`, `Spec.md`, `Docs/Contracts.md`, `Docs/Guardrails.md`, `Current_Plan.md`; load the `srpss-guardrails`
   skill if the agent has it.
2. Focused docs for what each slice touches:
   - Settings: `ui/settings_dialog.py` (tab keys, lazy placeholders, `_get_tab_instance`, `_has_image_sources`,
     `_show_no_sources_popup`, `_on_add_default_sources`), `ui/styled_popup.py`, `ui/settings_theme_runtime.py`,
     `ui/tabs/shared_styles.py` (`build_bucket_toggle`, accordion contract), Contracts § Settings collapsible-bucket
     contract, § Lazy Settings-section lifetime, § Runtime -> Settings round-trip.
   - Defaults: `core/settings/default_settings.py` (it is exact `pprint.pformat(width=100, sort_dicts=True)` output),
     `tools/regenerate_defaults_artifacts.py`, `tools/check_defaults_authority.py`,
     `Docs/Architecture/Persisted_Input_Compatibility.md`.
   - Widgets: `core/settings/widget_family_catalog.py`, `core/settings/capability_activation.py`
     (`is_widget_family_effective`), `rendering/widget_descriptors.py` (settings sections, runtime descriptors:
     `custom_layout_resize_mode`, `content_extent_axes`, `supports_custom_position_slot`, `supports_layout_resize_edit`),
     the Widgets **Setup** pill (`section_id="setup"`).
   - CUSTOM geometry: `rendering/custom_layout_contract.py`, `rendering/custom_layout_session.py`,
     `rendering/quick/custom_layout_owner.py` (`save`, `_write_item`), `rendering/quick/custom_layout_size.py`,
     `rendering/quick/custom_layout_hydration.py`, `core/settings/layout_slots.py`, `engine/display_manager.py`
     (`_save_layout_slot`, `_load_layout_slot`, `show_on_monitors` repair), `Docs/Guides/Custom_Child_Geometry.md`,
     `Docs/Guides/Custom_Child_Placement_And_Headers.md`, historical R-63.
   - Launch: `main.py` (`run_screensaver`, `_run_missing_sources_onboarding`, `run_config`, mode parsing).
   - Secure boundary: `core/windows/secure_url_launcher.py`, `core/windows/reddit_helper_bridge.py`, R-02.
   - Accounts: `ui/tabs/widgets_tab_steam.py` (connection bucket, `_on_steam_connect_id`, `_on_steam_connect_api_key`,
     `_on_steam_check_saved_connection`), `ui/tabs/widgets_tab_gmail.py` + `core/gmail/gmail_backend.py`,
     `ui/widgets/geocode_completer.py` + `weather/open_meteo_provider.py`, Reddit settings in `widgets_tab_reddit.py`.
   - Previews: `tools/transition_contact_sheet.py` (`TransitionCapture`, offscreen GL),
     `tools/ordinary_widget_resize_capture.py`, `tools/ordinary_widget_stack_capture.py`.
   - Build: `scripts/build_nuitka.ps1`, `scripts/build_nuitka_mc_onedir.ps1` (`--include-data-dir=images=images`),
     `tools/build_runner.py` (`required_assets`).
3. Standing operator rules that apply here:
   - No environment-variable feature flags or A/B toggles.
   - **No visible windows in probes, tools or tests.** The preview foundry and every capture use the offscreen QPA
     (`QT_QPA_PLATFORM=offscreen`, `QT_QPA_FONTDIR=C:/Windows/Fonts`, software Quick backend for QML, offscreen GL
     context for transitions). Never construct `QuickDisplayWindow` or call `show_on_screen` for a capture.
   - New Settings UI copies the existing UX (Steam-style nested buckets, closed by default, one open bucket per level,
     one-sentence intros, explanations in tooltips, short names such as "Layout").
   - No live Reddit calls in tests or tools (rate limits). No live network or credentials in the foundry.
   - Bubble is GOLDEN; do not touch Visualizer runtime to build onboarding.
   - Connecting a QML signal to a PySide `@Slot(..., result=...)` native-crashes; QML-signal handlers are plain methods.
   - Commit and push each slice to `main` with the `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` line.
     Never sweep the operator's own edits to defaults, `.sst`, themes or installer files into a commit.
   - Physical validation is not tracked in `Current_Plan.md`; it lives in § Final operator handoff here.

## 1. Verified facts that correct or sharpen the original brief (2026-09-26)

Each of these was checked in the tree. Re-verify before relying on one; the tree wins over this list.

1. **Three no-source edges, not two.**
   - `main.py` `run_screensaver`: with no sources it shows a plain `QMessageBox` ("No Sources Configured", auto-closes
     after 10 s), then `_run_missing_sources_onboarding` opens Settings modally inside the RUN launch and resumes the
     saver only if sources then exist.
   - `ui/settings_dialog.py` close guard: `_has_image_sources()` and `_show_no_sources_popup()` (`StyledPopup`
     "No Image Sources", buttons "Just Make It Work" / "Ehhhh"; "Ehhhh" calls `sys.exit(0)`).
   - `engine/screensaver_engine.py` logs `[FALLBACK] No image sources initialized` (a log, not a prompt).

   The readiness rule `bool(sources.folders) or bool(sources.rss_feeds)` is copied three times (main.py twice,
   settings_dialog once). The `QMessageBox` is exactly the "pre-Settings message followed by another wizard" to remove.
2. **"Just Make It Work" exists twice.** `SettingsDialog._on_add_default_sources` and the Sources tab action both
   read `sources.rss.constants.DEFAULT_RSS_FEEDS` and **replace** `sources.rss_feeds` with its values. The dialog
   version then calls `self.close()`. The wizard must not call either method; extract one function first.
3. **Monitor selection is index based.** `display.show_on_monitors` is `'ALL'` or a list of 1-based monitor
   indices (`Screensaver_MC` defaults to `[2]`), repaired by `DisplayManager` against the live topology. Widgets
   store `monitor: 'ALL' | '1' | '2' ...`. There is no safer identity for selection. Write exactly what the Display
   tab writes. Do not invent a display identity.
4. **CUSTOM geometry is keyed by screen signature, not index.** `custom_layout.displays` is keyed by
   `get_screen_signature(QScreen)` (with `get_screen_signature_aliases` and `canonicalize_screen_layout_bucket`).
   Entries hold a rect normalised against `QScreen.geometry()` (the runtime's `_DisplayBinding.geometry`), a
   `size_payload`, a `resize_mode` and a geometry variant (Clock digital/analog). Settings has the same
   `QScreen`s, so it can produce identical keys and rects.
5. **There is no separate shared CUSTOM commit path yet.** Persistence lives inside the 3,400-line runtime owner
   `rendering/quick/custom_layout_owner.py` (`save()` grouping, duplicate and removal handling, the Visualizer
   monitor-route rule, and `_write_item`: clamp, `normalize_local_rect`, payload scale key, clock/visualizer/content
   extent payload rules, `position: "Custom"` / `monitor` writes). The working state (`CustomLayoutSession`,
   `CustomLayoutSessionItem`) and the rect/snap/clamp/transfer helpers are already presentation-neutral. The brief's
   "shared mutation/normalization path" must be **extracted** before Arrange exists (§ 3, slice A).
6. **Authored widgets have no headless size.** A widget with no CUSTOM entry gets its size from its QML-reported
   preferred content size plus a Python anchor (`rendering/quick/widgets/geometry_resolver.py`). It is known only
   after QML layout. For six of eight resize modes (`UNIFORM_TRANSFORM_RESIZE_MODES`) the committed CUSTOM rect *is*
   the outer box and content scales to fill it, so promoting an authored widget to CUSTOM at an *estimated* size (the
   stack predictor's) visibly rescales it on the next run: `OverlayGeometryPolicy.resolve` returns a committed
   rect whole and ignores content size. What *is* exact in Settings is an authored widget's **anchor point**. For
   example, Top Right with margin m is the display's top-right corner inset by m, whatever the widget's size. Hence
   decision D2.
7. **Your X/Y point, concretely.** Each CUSTOM parent carries, besides its rect:
   - a uniform `resize_scale` (payload `_custom_resize_scale`);
   - an optional `content_extent` X/Y reflow box, declared by ten families (`content_extent_axes`);
   - an optional Visualizer `viewport_extent` X/Y world;
   - a content-rotation token in `size_payload`;
   - child size factors;
   - per-mode payloads (`clock_font` font size, `visualizer_rect` width and height).

   X/Y reflow and child minimums (`child_content_requirement`) are re-reported by the live presentation. Settings
   cannot know them, which rules out full X/Y parity outside Runtime Edit. Hence decision D3.
8. **Layout slots are the saved loadouts.** Ten slots (`1`-`9`, `0`) in `widgets.layout_slots`. `capture_layout_slot`
   stores the whole `custom_layout` + `custom_layout_restore` plus every widget's layout fields (enabled, position,
   monitor, margin, font family and size, clock display mode and per-display overrides, and so on).
   `apply_layout_slot` replays them onto a widgets map, and never re-enables a family the user has deactivated.
   Today they are saved and loaded only from the runtime (`DisplayManager._save_layout_slot` / `_load_layout_slot`),
   by key on the saver (`rendering/runtime_input.py`): **1**-**9** and **0** load, and **Shift** with the same key saves.
20. **The Position combo's "Custom" option is already the free-placement switch.** Settings enables it only when a
    CUSTOM entry exists (`WidgetsTab._refresh_custom_position_option_state` → `has_saved_custom_layout_for_widget`).
    Any "free arrange" control must be derived from that state, never a second stored flag.
9. **Theme.** `widget_theme = {custom, keep_synced (default True), selected_id}`; the Settings theme selection is
   `ui.settings_theme_selection`. Keep Synced is the only bridge.
10. **Interaction.** `input.interaction_mode` (default False). Holding Ctrl temporarily admits widget interaction
    (`rendering/quick/input_controller.py`). Before shipping the brief's framing, verify the "links are handed back and
    SRPSS exits" sentence against current R-02 behavior.
11. **Widgets.** Two levels: `widgets.family_activation.<family>` and each member's `enabled`, combined by
    `is_widget_family_effective`. The Widgets **Setup** pill already edits family activation. The catalogue has a
    `label` and `description` per family: that is the gallery unit (members inside it). FEEDS is shipped but its family
    activation defaults to False, which is a user choice, not "unadmitted".
12. **Visualizer.** `spotify_visualizer.enabled`, `mode`, `mode_activation` (bubble, devcurve, oscilloscope,
    sine_wave, spectrum, sphere) and `monitor`. Sphere is "accepted experimental, isolated": show it only as
    `mode_activation` admits it and never promote it.
13. **Transitions.** Two maps, `transitions.activation` and `transitions.pool`, plus `type` and `random_always`.
    Mirror the Transitions tab's save semantics exactly; never write one map without the other rule the tab applies.
14. **Settings nav.** `SettingsDialog._tab_keys` ends with `about`; pages are lazy placeholders created by
    `_create_<key>_tab`; nav icons are drawn by `_SettingsTabVectorIcon` (`_draw_<name>`).
15. **Responsive image.** `ui/settings_about_tab.py` already scales pixmaps for DPR (`devicePixelRatioF`,
    `setDevicePixelRatio`, smooth scaling). Extract and reuse it for the Witch rather than writing a second scaler.
16. **`images/SRPSSWitch.png` is untracked.** The build bundles `images/` whole (`--include-data-dir=images=images`),
    so a build from another checkout would ship without it. It stays operator-managed; see D6.
17. **WebP is not proven in the frozen build.** Preview assets are **PNG** unless both Nuitka builds are shown to ship
    `qwebp` and a frozen-build test loads one.
18. **The secure-desktop test today is a heuristic.** `secure_url_launcher` classifies Winlogon/Services by
    `SESSIONNAME` and notes it can read "Console" even on Winlogon's desktop; saver clicks therefore always hand off.
    See D1.
19. **Existing reds not to "fix" for this feature:** `test_sparse_crumble_uses_canonical_piece_count_and_complexity`,
    `test_pill_model_is_setup_plus_enabled_in_canonical_order`,
    `test_lazy_theme_pages_refresh_without_polling_or_cross_tab_theme_owner` (see `Current_Plan.md`).

## 2. Decisions

- **D1. Account steps follow the real desktop, not the launch mode.** Steam/Gmail setup (browser pages, OAuth,
  credential entry) works whenever the wizard's own thread is on the user's normal desktop: first run, `/c` from
  Windows Screen Saver Settings, MC, Settings opened directly or from the tray. It is disabled only when the thread
  desktop is not the interactive `Default` desktop (Winlogon, the screen-saver desktop) or cannot be determined
  (fail closed).
  - Add one small helper, e.g. `core/windows/desktop_context.py::is_interactive_user_desktop()`:
    `GetThreadDesktop(GetCurrentThreadId())` plus `GetUserObjectInformationW(UOI_NAME) == "Default"`, and not
    `SESSIONNAME` in {winlogon, services}.
  - Do **not** change `secure_url_launcher` (R-02 is an attended, operator-protected boundary).
  - When disabled, the step shows why and what to do instead. Suggested text, final wording at the agent's discretion:
    "For your protection, account setup is turned off while SRPSS runs as the screensaver. Open SRPSS from Windows
    Screen Saver Settings (Settings button) to connect Steam or Gmail." The step is then marked NEEDS SETUP on Ready
    and in Quick Start.
- **D2. Every widget is freely arrangeable: content-sized CUSTOM placement.** A widget placed or scaled from
  Settings gets an ordinary CUSTOM entry whose position is explicit but whose **size keeps following its content**,
  so nothing Settings cannot measure is ever frozen into the entry.
  - **Carrier.** Two keys in the entry's existing `size_payload` (no new schema, no new settings key):
    `_size_from_content: true` and `_placement_anchor: "<h>,<v>"` (h in left, center, right; v in top, center,
    bottom), plus the existing `_custom_resize_scale`. The stored rect records where the user put the box. The anchor
    says which point of it is authoritative on each axis (left edge, centre or right edge; top, centre or bottom).
  - **Runtime.** The committed-geometry path resolves a content-sized entry as the family's real size (preferred
    content size × `_custom_resize_scale` for the uniform modes; the scaled `font_size` payload for `clock_font`; the
    payload width/height for `visualizer_rect`), placed so its anchor point lands on the stored point, then the
    existing containment clamp. Every other entry resolves exactly as today.
  - **Exactness.** An authored widget's anchor point is exact in Settings (§1.6), so turning free placement on at the
    current spot reproduces the authored placement pixel for pixel, for any content size; a test asserts it for every
    anchor option and margin. Moving and uniform scaling are exact too, because size is never guessed, only
    displayed. Settings draws the box at the stack-predictor estimate × scale, labelled "size follows content".
  - **The anchor** is chosen deterministically from where the box ends up: the display third its centre falls in on
    each axis, or the edge it is snapped to. That keeps a widget pushed against the right edge flush right at its real
    width.
  - **Free placement control (operator's idea, made derived).** The Arrange side panel has a **Free placement**
    circle checkbox per widget per display. It is checked exactly when a CUSTOM entry exists, reading the same state
    as the Position combo's "Custom" gate; it is never stored.
    - Checking it creates a content-sized entry at the widget's current anchored spot (no visible change at runtime).
    - Dragging or scaling an authored widget checks it automatically.
    - Unchecking it is Reset: the entry is removed and `position` / `monitor` come back from `custom_layout_restore`.
    - Widgets without CUSTOM support show it disabled with the reason.
  - **Stacking edge case.** Authored widgets sharing an anchor get runtime stack offsets that CUSTOM widgets do not.
    When free placement is turned on for a stacked widget, start it at the stack predictor's offset and show it on the
    canvas so the user sees and fixes any overlap.
  - **Runtime Edit parity.**
    - Runtime Edit admits a content-sized entry at its live rect.
    - If that session resizes it, changes an extent or edits children, Save writes an ordinary explicit entry (today's
      behaviour, since Edit measures the live size).
    - A move-only edit keeps it content-sized, recomputing the anchor from the new spot, so later font or config
      changes in Settings still resize it.
  - **Compatibility.** An older build reads a content-sized entry as an explicit rect at the estimated size (visible
    only on downgrade). Record this in `Docs/Architecture/Persisted_Input_Compatibility.md`.
- **D3. Uniform scaling only in Quick Start.** Resize in Arrange is uniform scale, through the same helpers Runtime
  Edit uses (`scale_quick_size_payload`, `quick_custom_payload_minimum_scale`, `quick_custom_minimum_size`,
  `CUSTOM_LAYOUT_MIN_RESIZE_SCALE`). For content-sized entries it changes `_custom_resize_scale` (and the Clock
  `font_size` payload); for explicit entries it also scales the rect about its anchor point.
  - Existing `content_extent`, `viewport_extent`, content rotation and child sizes are carried through byte for byte,
    never created or edited.
  - Widgets with X/Y reflow show a one-line hint: "Width and height reflow: use Edit Mode on the saver."
- **D4. One commit path.** Arrange stages edits in a `CustomLayoutSession` (the same working-state class) and commits
  through a presentation-neutral function extracted from `custom_layout_owner.save/_write_item` (slice A). The
  runtime owner then calls the same function. Byte-identical persisted output for the same session is a test.
- **D5. Layout slots in Quick Start (operator addition).** A **Layout Slots** area lists the ten slots with a short
  summary (which widgets and displays each covers, or empty).
  - **Load into editor** applies `apply_layout_slot` to a deep copy of the widgets map and projects that draft into
    the Arrange canvas. It commits only on Apply, through the same persistence as `DisplayManager._load_layout_slot`;
    Cancel discards.
  - **Save to slot** has a slot picker (1-9, 0, showing which are occupied, and confirming before overwriting). It
    runs `save_layout_slot` on the committed widgets map, so an unsaved Arrange draft must be applied first; the
    button says so when a draft is pending.
  - The UI states plainly that a slot also stores and restores fonts, positions, monitors and clock modes, not only
    boxes.
  - A one-line hint in the same area: "On the saver, 1-9 and 0 load a slot; Shift with the same key saves to it."
- **D6. `images/SRPSSWitch.png` stays operator-managed.** It already exists in the operator's working tree, and the
  build bundles `images/` from it. Do not commit it (operator-owned). Add it to `tools/build_runner.py`
  `required_assets` so a build without it fails loudly instead of shipping a broken Welcome page.
- **D7. Silence! lives at `sources.guided_setup_silenced` (default False)** in canonical defaults, with artifacts
  regenerated. Reset to Defaults resets it like any preference.
- **D8. Shipped preview art is operator-owned or generated.** Transition source/destination images come from
  `D:\Artwork\Projects` (operator's own art) or are generated; never from downloaded wallpapers such as
  `PERSONALSET`, which are fine for internal checks but not for shipping. Widget fixtures use synthetic artwork, never
  real game capsules, real Reddit posts or real usernames.
- **D9. Interaction demo is a Settings-side mock**, a small `QWidget` card with an "Open story" target that only
  explains what would happen. No GIF or video: capturing the real runtime would need a visible window, and video would
  add QtMultimedia to Settings.

## 3. Slices (each ends with focused gate → diff/status review → commit → push)

At every slice, check durability, content/user adaptability, performance neutrality (dormant when closed: no timer,
poll, worker, network owner, QML runtime, capture process or extra monitor watcher) and collisions with historical
bugs.

### Slice A | Foundations extracted with parity (no user-visible change)

- [x] `core/sources/readiness.py::has_image_sources(settings)` (same rule as today); `main.py` (both sites) and
      `SettingsDialog._has_image_sources` call it.
- [x] One curated-sources function (e.g. `sources/rss/curated.py::apply_curated_wallpaper_feeds(settings)`, replacing
      `sources.rss_feeds` with `DEFAULT_RSS_FEEDS` values exactly as today); the dialog and the Sources tab call it.
      Dialog-specific follow-ups (reload tab, close) stay in the dialog.
- [ ] `is_interactive_user_desktop()` (D1) with a Windows test using a fake Win32 layer; unknown → False.
- [ ] Steam and Gmail connection controllers extracted from the `WidgetsTab`-bound handlers into small classes that
      take callbacks for status text; the Widgets tab keeps identical behaviour (existing Steam/Gmail settings tests
      stay green; add parity tests). Credentials stay in their DPAPI owners; nothing new is persisted.
- [ ] CUSTOM commit extracted: `rendering/custom_layout_commit.py::commit_custom_session(widgets, session,
      descriptors, displays)`, where `displays` maps identity → (screen signature aliases, `QRect` geometry, monitor
      route). `CustomLayoutOwner.save` calls it.
      Parity test: for recorded sessions (move, display transfer, duplicates on ALL, removal, clock variant,
      visualizer viewport, content extent, children), the persisted `widgets` map is byte-identical before and after
      the extraction.
- [x] Reusable DPR pixmap scaler extracted from `settings_about_tab.py`; About uses it unchanged.
- **Done when:** full Settings/CUSTOM/defaults/Steam/Gmail gates green with zero behaviour change.

### Slice A2 | Content-sized CUSTOM entries in the runtime (D2)

- [ ] `rendering/custom_layout_contract.py`: parse and write `_size_from_content` / `_placement_anchor`, and a pure
      `resolve_content_sized_rect(stored_rect, anchor, content_size, display_size)`, plus the anchor-choice rule
      (display thirds or snapped edge).
- [ ] Runtime committed-geometry path (`resolve_quick_committed_variant_state`, `OverlayGeometryPolicy` /
      `OverlayGeometryBinding`): content-sized entries resolve from the live content size, per resize mode, then the
      existing clamp; explicit entries are untouched.
- [ ] `custom_layout_owner` admission and Save (via `commit_custom_session` from slice A): move-only edits keep an
      item content-sized with a recomputed anchor; resize, extent or child edits write explicit entries.
- [ ] Tests:
  - for every anchor option and margin, a content-sized entry created at the anchor point resolves to exactly the
    rect `resolve_anchored_geometry` gives, for several content sizes;
  - explicit entries resolve byte-identically to before;
  - an Edit move keeps content-sizing, and an Edit resize converts to explicit;
  - layout slots carry the keys through save and load.
- **Done when:** the runtime, CUSTOM, slot and geometry suites are green; historical R-63 and R-88 checked.

### Slice B | No-source routing, Silence!, wizard shell, Welcome, Sources

- [ ] `sources.guided_setup_silenced` default added; artifacts regenerated; `check_defaults_authority` green.
- [ ] One no-source owner:
  - no sources + Silence OFF → Guided Setup;
  - no sources + Silence ON → the existing `StyledPopup` "No Image Sources";
  - sources present → nothing automatic.
- [ ] `main.py`: the plain `QMessageBox` is removed. The RUN-interrupted onboarding opens Settings, and Settings
      shows Guided Setup (or the popup, per Silence) once, right after its shell is shown (one deferred call, not a
      recurring timer).
- [ ] CONFIG / MC / tray Settings with no sources: same single decision after show; the close guard still refuses a
      source-less close exactly as today.
- [ ] Manual launch from Quick Start ignores Silence. Closing the wizard while source-less leaves the existing close
      guard in charge; no `onboarding_completed` flag exists anywhere.
- [ ] Wizard shell: a large themed dialog owned by Settings, Back/Next, pages created lazily, live Settings-theme
      subscription through the existing owner (no QSS monolith, hardcoded colours, parallel theme cache, emoji or
      stock Windows wizard look), correct at 100/125/150/200% DPR.
- [ ] Welcome: `images/SRPSSWitch.png` (present locally, D6; add it to `required_assets`), left-aligned, aspect kept, scaled with the shared DPR scaler
      only on size/DPR change, never per paint, never cropped or stretched. Copy **verbatim**:
  - Heading, bold and underlined: **You're Inside A Wizard Harry!**
  - Body: "Your first time inside someone is special and confusing.
    The Wizard can help pick the right settings for you while you squirm inside without consent."
  - Primary **Next**. **Silence!** is a circle checkbox, visually secondary and away from Next, with a tooltip or
    second line: "When SRPSS has no image sources, show the simple No Image Sources popup instead of opening Guided
    Setup automatically."
- [ ] Sources. Copy **verbatim**: "You put on your robe and wizard hat.
      Sources matter the most. Where do you want your wallpapers from?"
  - Folders add/remove and a basic Wallpaper Feeds on/off/list, through the existing Sources owners. No wizard-only
    lists and no advanced RSS/cache/ratio options.
  - Next is disabled while `has_image_sources` is False, with an inline reason (no modal chain).
  - **Just Make It Work** is secondary and physically apart from Back/Next. It calls the slice-A function, then shows a
    themed prompt, verbatim: "You're lazy and so am I! Skip the rest?" with buttons **No, I can do it!** (continue)
    and **Skip** (finish now; nothing else changes).
  - **Skip** is secondary, apart from Back/Next, Sources page only, enabled only once sources exist; it finishes with
    every other setting untouched.

### Slice C | Displays, Theme, Interaction

- [ ] Displays: plain-English intro. Lists the live `QScreen`s with name, resolution and a small relative diagram
      (from `QScreen.geometry()`). Selection reads and writes `display.show_on_monitors` exactly as the Display tab
      does (`'ALL'` or a 1-based list). At least one display stays selected. Mixed DPR stays in Qt logical
      coordinates; no new identity.
- [ ] Theme: installed Settings themes listed; a click applies immediately through the existing runtime and restyles
      the wizard. Widget Theme follows only through `widget_theme.keep_synced` (existing behaviour); a decoupled Widget
      Theme is never overwritten. No screenshots.
- [ ] Interaction: two large exclusive choices writing only `input.interaction_mode`, with a D9 mock card. The mock
      starts no network, launches no browser, touches no handoff and builds no feed widget. Verify the framing text
      (§1.10) before using it.

### Slice D | Preview foundry and Widgets page

- [ ] `tools/onboarding_preview_foundry.py`: offscreen only, fixtures only, no network (a socket guard fails the run
      on any connection attempt), no credentials imported.
  - Widgets: build each onboarding-visible family's real production presentation with deterministic representative
    data and a known shipped Widget Theme; let layout settle; capture; crop and pad to the asset contract. Prefer
    backgrounds that suit transparency; otherwise give each preview a neat semantic border on dark grey.
  - Transitions: `TransitionCapture` with a fixed D8 source/destination pair, rendered as a 25% | 50% | 75% triptych.
  - Visualizer (optional): stills from real render code with fixed fake spectrum state.
  - Writes PNG (§1.17) to `images/onboarding/` within a size budget (target ≤ 8 MB total); deterministic output.
    Onboarding never runs the foundry.
- [ ] The agent inspects every generated image and fixes clipping, settlement and framing itself.
- [ ] `tools/build_runner.py` checks the onboarding asset directory exists and is non-empty.
- [ ] Widgets page. Copy **verbatim**: "Widgets are what make the experience special, and messy.
      Pick the ones you might actually give a shit about."
  - Gallery on the left, one row per catalogue family (label from the catalogue). A persistent preview panel on the
    right shows the asset, name, description and a requirement marker (READY, NEEDS STEAM, NEEDS GMAIL, NEEDS
    LOCATION, NEEDS SETUP...), plus member toggles for multi-member families (Clocks 1-3, Reddit 1-2, Steam cards,
    FEEDS News categories).
  - Writes go through family activation and member `enabled`, the same authority as Widgets → Setup; dependencies
    are resolved by `is_widget_family_effective`, not re-coded. No tooltip previews, no handwritten widget list.

### Slice E | Widget Setup (conditional)

- [ ] Built from the selections; a page or section exists only if its dependency is selected.
- [ ] Weather: location through the existing `geocode_completer` / Open-Meteo owner (user-typed lookups only).
- [ ] Steam (D1 gating), copy **verbatim**: "SRPSS sends you to Steam's own sign-in and API-key pages. Your Steam
      password never enters SRPSS. Your Steam identity and API key are stored encrypted for your Windows account."
      Uses the slice-A controller: OpenID page, API-key page or paste and Save & Test, validation before durable
      replacement, DPAPI only, no plaintext fallback. The key lives only in the input field while being typed.
- [ ] Gmail (D1 gating), IMAP App Password path by default, copy **verbatim**: "Use a Google App Password, not your
      normal Google password. SRPSS tests the connection directly with Gmail and stores the credential encrypted for
      your Windows account." Uses the existing backend and storage with verified TLS; OAuth stays in full Settings.
- [ ] Reddit / Reddit 2: subreddit names only (examples `wallpapers`, `pcgaming`, `cats`; `r/` optional and
      stripped). Format validation only, no live check (rate limits).
- [ ] FEEDS: News category checkboxes (the category cards from `core/feeds/news.py`, default publishers kept), through
      the existing Feeds settings owner. Custom slots stay in full Settings.
- [ ] No secret enters a generic wizard object, a log, a preview asset or a fixture.

### Slice F | Visualizer and Transitions

- [ ] Visualizer: enable, admitted modes (`mode_activation`), its `monitor` if exposed, and optional preview stills.
      No tuning, AGC, energy floors, mode internals or presets.
- [ ] Transitions: admitted transitions with triptych previews and a one-line description; basic enable writes
      `activation` and `pool` exactly as the Transitions tab does, keeping `random_always` semantics. No per-effect
      parameters.

### Slice G | Arrange (restricted editor over canonical CUSTOM)

- [ ] Canvas: the selected displays, placed by their real relative `QScreen.geometry()` and aspect. It is a
      projection, not persisted geometry.
- [ ] Items (lightweight wireframe boxes, optionally with the preview asset):
  - one box per effective widget per display it appears on (`monitor: ALL` gives one per selected display, as the
    runtime does);
  - the Clock box uses the variant active on that display (`_clock_variant_from_widgets`);
  - boxes for widgets without CUSTOM support are shown but not draggable.
- [ ] Every CUSTOM-capable widget is freely arrangeable (D2, D3): free move, uniform scale with the shared
      minimums, drag to another display (monitor route plus rect translated into the target's normalised space, then
      clamp and `choose_best_screen_for_global_rect` / `should_transfer_rect_to_screen`), and Reset.
      - An authored widget becomes a content-sized entry on its first move or scale, or when its derived **Free
        placement** checkbox is ticked.
      - Merely selecting or viewing writes nothing.
      - Explicit entries keep explicit semantics.
- [ ] Snapping reuses only the existing neutral helpers in `custom_layout_contract.py`; no second snap system.
- [ ] Transaction: the draft is a `CustomLayoutSession`. Pointer moves never write settings; Apply/Next commits
      through `commit_custom_session` (D4); Cancel discards.
- [ ] Reset (per widget): the established reset. Remove that display's CUSTOM entry and restore `position` /
      `monitor` from `custom_layout_restore`. Child customisation elsewhere is untouched.
- [ ] Layout slots (D5): list, Load into editor, Save to slot (picker, overwrite confirm) and the hotkey hint.
- [ ] Opening Arrange starts no Weather, Steam, Gmail, FEEDS, audio, network or QML runtime root.

### Slice H | Quick Start page and Ready

- [ ] Nav entry **QUICK START**, anchored bottom-left under About with visual separation, with a new
      `_SettingsTabVectorIcon` drawing (compass or guide mark, no emoji). The page is lazy, and the Arrange editor
      inside it is lazy again.
- [ ] Contents, following the existing bucket UX:
  - a brief start-here line and a concise current-setup summary (cheap reads only);
  - **Run Guided Setup Again**, which starts from current settings and ignores Silence;
  - **Arrange Widgets**;
  - the Layout Slots area (D5: list, load into editor, save to slot, hotkey hint);
  - **Reset Widget Layouts**, which resets parent layouts only, with wording that says exactly that;
  - the **Silence!** circle checkbox with its explanation.
- [ ] Ready page: a summary such as displays, sources, interaction, widget count, account states (Steam connected /
      Gmail needs setup from the existing non-decrypting saved-connection checks), Visualizer modes and transition
      count. Unfinished optional accounts are marked, not blocking. Buttons **Back to Arrange** and **Finish**;
      Finish changes nothing that was not explicitly changed.

### Slice I | Tests, docs, visual self-check, cleanup

- [ ] Tests (§4), then the relevant existing suites: Settings, defaults, capability, CUSTOM geometry and slots,
      monitor/display, widget descriptors, credentials, lifecycle.
- [ ] Internal visual check through offscreen captures: Welcome at 100% and 200% DPR, Sources, Theme before and after
      a live switch, Widget gallery, one conditional setup page (enabled and D1-disabled), Transition gallery, Arrange
      with one and two monitors, Ready, Quick Start.
      Look for clipping, a blurry Witch, DPR errors, overflow, poor spacing, stale theme tokens, preview aspect errors,
      buttons below the viewport, Skip/JMIW reading as primary, monitor cards outside the canvas, boxes losing
      identity, and invisible hover/focus. Fix what is found.
- [ ] Docs: `Docs/Reference/Guided_Setup.md`, plus Contracts entries for the trigger, Silence, shared wizard/Quick
      Start authority, D1, the Arrange boundary (D2-D5), dormancy and preview-foundry maintenance. No changelog prose.
- [ ] Delete the `Current_Plan.md` pointer when the feature is accepted.

## 4. Tests (minimum)

1. no-source + Silence OFF → Guided Setup; 2. no-source + Silence ON → existing popup; 3. sources present → nothing
automatic; 4. manual launch ignores Silence; 5. exactly one no-source prompt across `main.py` and Settings (the
`QMessageBox` is gone); 6. Sources Next/Skip disabled while source-less; 7. Skip mutates nothing else (whole-settings
diff); 8. JMIW calls the single curated function (no copied feed list); 9. both follow-up buttons behave;
10. rerun hydrates current settings; 11. live theme apply respects Keep Synced/decoupled; 12. display selection
writes `show_on_monitors` exactly like the Display tab; 13. Interaction writes only `input.interaction_mode`;
14. widget selection follows `is_widget_family_effective`; 15. no credential in wizard state, logs or assets;
16. setup sections exist only for selected dependencies; 17-18. preview coverage matches onboarding-visible widgets
and transitions, and dimensions and format are correct; 19. foundry makes no network call and imports no credential
(socket guard); 20-21. Quick Start and Arrange are lazy; 22. opening Arrange creates no provider, runtime or network
owner; 23. authored widgets stay authored until moved, and an authored move writes only `position`/`monitor`;
24. a CUSTOM edit commits through `commit_custom_session`; 25. existing CUSTOM rects read back exactly; 26. child
payloads, `content_extent`, `viewport_extent` and rotation survive move and scale byte for byte; 27. display transfer
matches the runtime (monitor route, normalised rect, Visualizer rule, duplicates); 28. Cancel discards; 29. Apply
persists; 30. Reset equals the established reset; 31. mixed-DPR conversion stays in logical coordinates;
32. Settings close/reopen and runtime reconstruction stay clean.

Added by this plan: 33. commit extraction is byte-identical to the old owner; 34. a slot loads into the draft
without persisting, and Apply persists the same map `DisplayManager._load_layout_slot` would; 35. D1 disables
account steps on a non-Default or unknown desktop and shows the explanation; they are enabled on Default;
36. uniform scale in Arrange equals Runtime Edit's wheel scale for every resize mode (`clock_font` payload,
`visualizer_rect` payload, uniform modes); 37. the Steam and Gmail controller extraction preserves Widgets tab
behaviour; 38. D2 exactness: free placement turned on at the anchored spot resolves to the anchored rect for every
anchor, margin and content size; 39. a content-sized entry follows a later content change (for example a font
size); 40. the Free placement checkbox is derived (checked iff an entry exists, unchecking equals Reset, never
stored); 41. Save to slot writes exactly what `save_layout_slot` writes on the committed map, confirms before
overwriting, and refuses while a draft is pending; 42. explicit CUSTOM entries resolve byte-identically after slice
A2.

Do not fix the unrelated reds in §1.19 to make a gate green.

## 5. Final operator handoff (the only physical step)

One pass, after everything above is green and self-inspected:

- fresh/no-source automatic Guided Setup; Witch artwork and exact welcome copy;
- source requirement;
- Just Make It Work → exact lazy prompt → both choices;
- Sources Skip;
- Silence → old no-source popup;
- live Theme switch; monitor selection; Interaction demo;
- widget previews and selections;
- one Steam/Gmail/Weather/Reddit/FEEDS setup path, including the D1 message when started by Windows as the screensaver;
- transition previews;
- Arrange: free-place and scale a never-moved widget (it keeps its real size on the saver); move, scale and
  reassign the display of an already-customised widget; tick and untick Free placement; load a layout slot (Apply and
  Cancel); save to a slot, then load it on the saver with its number key;
- Runtime Edit sees Quick Start changes, and Quick Start sees a later Runtime Edit change;
- child edits survive parent manipulation;
- final runtime start;
- Settings → QUICK START lazy reopen;
- no network or provider work while Quick Start and Arrange are closed.

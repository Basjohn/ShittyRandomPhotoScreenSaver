# SMP full-player mock (operator, restored 11 Nov 2026)

**Status:** design reference for the full-size ShittyMusicPlayer window, the long-range goal ("far far ahead of
us"). It is a mock: one example of the layout, coloured by one theme. The lead may adjust it for better UX and
functionality, and adjust the plans with it. Nothing here is scheduled; the order of work is plan 02
(`02_ShittyMusicPlayer_Implementation_Plan.md`), whose phase ladder and `--smp` gate still bind. Sections 7 to 9
record the operator's clarification of the same evening: the product's shape, the contract route for SMP Edit
and the long-term audio and library goals. SMP comes after the native core, the open defects and the
fullscreen Visualizer.

**Files (in `references/`, which git ignores, so this document carries their content in words):**

- `references/ShittyMusicPlayer-Miami-Afterdark-Mock-DETAILS.png`: the annotated mock ("Miami Afterdark" colours:
  deep navy surfaces, pink accent). Every annotation is transcribed below.
- `references/SMP Material Surfaces And Vibrancy ONLY Example.png`: the same layout with translucent, blurred
  surfaces and a soft coloured glow behind them. It shows material and vibrancy only; the operator's note: "we can
  do better".

This replaces the earlier concept image (`MusicBee_SRPSS_Concept_2026-09-24.png`) that plan 02 cites as "not in
the tree".

## 1. Layout of the mock

A single window with a custom title bar, a navigation row, three columns and a transport bar.

| Region | Content in the mock |
|---|---|
| Title bar | Menu glyph, "ShittyMusicPlayer", minimise / maximise / close. |
| Navigation row | Back; tabs MUSIC (selected), NOW PLAYING, PLAYLISTS, MUSIC EXPLORER, PODCASTS; a "Search Playlist" field; a grid glyph at the far right. |
| Left column | A tall pane labelled VISUALIZER / LYRICS / ARTIST COLLAGE. |
| Centre column | "Tracks": a favourites heart, a search glyph, an All / A-Z index strip; a table with Artist, Title and Plays columns; the playing row is highlighted with a play mark, a heart and a three-dot menu. |
| Right column, top | "Playing Tracks": the queue as rows of artwork, title, artist, duration and a three-dot menu; the playing row highlighted. |
| Right column, bottom | "Track Information": large artwork, then title, artist, album, and a format line (MP3 320 kbps, 44.1 kHz, Stereo, 3:41). |
| Transport bar | Shuffle, previous, play/pause (large, ringed), next, repeat; volume glyph and slider; artwork thumbnail with "Artist - Title" and elapsed time; the seek bar with "elapsed / total"; then favourite, queue, visualizer, "CS" and settings glyphs. |

## 2. The operator's annotations, as requirements

Each line is the annotation's meaning; the quoted words are the operator's.

**Title bar**
- R1. The title bar "also needs swapping arrow glyphs": a down-left diagonal arrow that enters Mini / Normal Media
  (the reverse of the expand arrows the Visualizer card has; one glyph family, see plan 01 M3c and Current_Plan
  1B.12).

**Navigation row**
- R2. PODCASTS is replaced by AUDIOBOOKS: a Library special group with add/remove, saveable bookmarks at track
  points, chapter support and the like. Long-term goal.
- R3. The grid glyph is SMP Edit mode: "every element (except title bar) moveable, sizeable and swappable when
  space calculations can handle it".

**Left pane**
- R4. Its edges are fully adjustable in X, Y and XY.
- R5. It shows Visualizer, Lyrics or an Artist Collage.
- R6. As Visualizer it "has glyph parity" and "displays actual Visualizer widget": the real Visualizer card with
  its real glyph row, not a second renderer.

**Tracks pane**
- R7. The heart is "same as search but filters favourites".
- R8. The search glyph "opens drop down library filter"; the list "stays filtered until search unselected"; the
  glyph has a slight glow while a filter is active.
- R9. A row's three-dot menu is the library track menu: properties, metadata edit, quick tagging, delete, add to
  group.

**Right column**
- R10. "Playing Tracks" is the Playlist widget, integrated small (the same widget, a compact presentation).
- R11. "Track Information": its alignment is swappable, header included.

**Transport bar**
- R12. The volume control uses our existing sliders.
- R13. The seek bar is our existing seek bar, matched for length.
- R14. "Both bars and all controls should be properly horizontally aligned! Correct alignments are core to a good
  experience everywhere."

**Whole window**
- R15. All backgrounds inherit the surface material and theme colours.
- R16. Semantic theme colours throughout; the mock is one example only.

## 3. Where each requirement lands in plan 02

| Requirement | Plan 02 section | Note |
|---|---|---|
| R1 swapping arrow glyphs | 7.1 UI modes and glyph semantics | Same arrow family as the Visualizer's fullscreen glyphs; down-left returns to Mini / Normal Media. |
| R2 Audiobooks | 5.1 groups and browse modes | A special group, not a separate product area; bookmarks and chapters are Library data (3.3 persistence). |
| R3 SMP Edit mode | 16 Full visual rearrangement, 8.2 pane geometry | The existing Edit owner and its handlers, not a second layout system. |
| R4-R6 left pane | 8.3 Visualizer Pop Out, 16 | The one canonical Visualizer; Lyrics and Artist Collage are further presentations of the same pane. |
| R7-R9 Tracks pane | 3 first visible deliverable, 5.1 favourites, 5.2 metadata | The library filter and the favourites filter are one filter owner with two entry glyphs. |
| R10 Playing Tracks | 3 (the Playlists pane), 4.1 queue contracts | A compact presentation of the Playlist pane; one widget entry. |
| R11 Track Information | 5.2 artwork and metadata, 16 | Alignment swap as in Now Playing (Current_Plan 1C.3: side flip and one text group). |
| R12-R14 transport bar | 4 playback phase, 14 Settings tab with pills | `MediaSeekBar.qml` is already one shared component (Current_Plan 1B.7). |
| R15-R16 materials and colours | 8.2, 15 icon and artwork rules | The widget material system (Card_Surface_Materials.md) and semantic theme tokens. |

## 4. The lead's UX adjustments (proposals, kept apart from the operator's requirements)

Each is a proposal for the operator to accept or strike; none changes plan 02's order.

- A1. **One filter field.** The mock has a "Search Playlist" field in the navigation row and a search glyph in the
  Tracks header. Two search entry points with different scopes confuse. Proposal: the navigation-row field always
  searches the active tab's main list and says so in its placeholder; the Tracks header's glyph opens the library
  filter drop-down (R8) and shows the active filter as removable chips beside the index strip, so "stays filtered"
  is visible without relying on the glyph's glow alone.
- A2. **Index strip follows the sort column.** All / A-Z only makes sense for a text sort. When the list is sorted
  by Plays (as in the mock) the strip should dim, or switch to ranges for the sorted column, instead of jumping by
  artist under a Plays sort.
- A3. **Row actions appear on hover or selection for every row,** not only the playing one, and the heart shows
  filled for favourites in every row, so favourites can be seen and set without first playing the track.
- A4. **Transport alignment grid (R14).** One baseline for every control in the bar; the play/pause ring is the
  only element allowed to exceed the row height, centred on that baseline; the elapsed time sits at the seek bar's
  left end and the total at its right end (the mock repeats the duration under the title and again as
  "0:52 / 3:41"; one of them goes).
- A5. **"CS" needs a name.** The mock's "CS" glyph has no annotation. Until the operator says what it is, it is not
  designed.
- A6. **Queue header carries the count and a view menu** ("Playing Queue (12)" with a list-options glyph, as the
  material example shows); the mock's plain "Playing Tracks" loses both.
- A7. **Edit mode affordance (R3).** Entering SMP Edit shows each section's handles and a swap target on drag,
  with the same handle sizes and guides as ordinary Edit, and a "Reset Layout" in the Edit bar. The Transport is a
  section like any other and can go to the top or a side (operator, P4 in section 7); only the order of the
  buttons inside its transport cluster (previous, play/pause, next) stays fixed, since muscle memory matters more
  than freedom there. The contract route is section 8.
- A8. **Minimum sizes and collapse order.** When the window narrows, panes collapse in a stated order (Track
  Information first, then the left pane to a strip, then the queue to an overlay), never by clipping text.
- A9. **Keyboard and accessibility.** Every glyph-only control has a tooltip and a key; the Tracks table is fully
  keyboard-navigable (type-ahead jumps, Enter plays, Menu key opens the track menu).

## 5. Material direction (against the example image)

What the example does: translucent panes over a blurred, softly coloured backdrop, a brighter rim on each pane, a
pink glow under the selected tab and the playing row.

What ours should do better, using what the widget material track has built or is building (Current_Plan 1B.8):

- Real backdrop materials (Glass, Acrylic, Frosted, Mica, Smoked) chosen by the theme, the same shader and
  parameters as the widget cards; no painted fake blur.
- Legibility by the one ink rule: text that misses its ratio corrects its own ink; panes never go opaque to save
  text and never grow an inset panel.
- Borders shaded from the same backdrop as the face (the border material, M3/M4), with the window's rounded
  corners truly see-through (Current_Plan 1B.9).
- Vibrancy as a theme token, not baked colour: the accent glow under selected and playing items comes from the
  semantic accent, so every theme, light themes included, gets a correct one.
- The Visualizer pane is the live Visualizer on the same material, so the window's most vivid element is real.
- Cost: one backdrop capture shared by all panes of the window, no per-pane blur passes; dormant when the window
  is hidden or minimised.

## 6. Open questions for the operator (no action needed now)

- What "CS" in the transport bar stands for.
- Whether Lyrics and Artist Collage are in the first full-player milestone or later presentations of the pane.
- Whether the wider dock model of plan 02 section 16 (tabbed stacks, floating panels on other monitors) is
  wanted at all, now that Full mode is a tree of sections (section 8.5).

## 7. Product shape (operator, 11 Nov 2026, evening)

The operator's clarification, in their order. SMP stays long term: the native core, the existing defects and the
fullscreen Visualizer come first. It is written down now so that work done before then does not close doors.

- P1. **Three builds from profiles, as the saver and MC build today.** SMP functionality exists in all three: the
  screensaver build, the MC build and an SMP build. The screensaver and MC builds carry full SMP functionality
  *along with* the compositor (images, transitions, every widget). Only the SMP profile build comes without the
  compositor: no transitions, no image presenter, no widgets that are not the Visualizer or media related. At
  least two of its media widgets do not exist yet (the Library and the Playlist / Queue of plan 02 section 3).
- P2. **Small mode** is the Media widget as it is now, on the live user's desktop: proper snapping, its outer
  geometry adjustable at all times, and its children adjustable behind the lock glyph.
- P3. **The Up arrow switches Small mode to Full mode**, which is what the mock shows. (The mock's down-left arrow,
  R1, is the way back.)
- P4. **Full mode defaults to full screen but can be adjusted like a normal window**; the sections inside scale
  their spacing and sizing with it. Full mode's edit, SMP Edit, rearranges as much as possible, "especially with
  swaps and x/y adjustments": the controls on top or at the side, the Visualizer as a thin wide strip along the
  bottom, the artwork and artist information top left. "Every 'child' should be intelligently moveable as an
  adjustable 'section'."
- P5. **Existing Edit modes must not break**, and in the screensaver and MC builds SMP Edit lives side by side
  with them.
- P7. **SMP has its own section in Arrange**, "where this can be more easily carried out"; on SMP builds it is
  the main section of Arrange.
- P8. **On the screensaver and MC builds, Full mode and Small mode do not need to leave the compositor.** Only
  the SMP profile build puts them on the desktop as windows.
- P6. **Audio and library, eventually:** an equalizer; high-end audio support ("everything from upmixing,
  downmixing to replay gain, device select and so on, audio crossfade too"); "a well indexed growable library
  database"; "full modern music player parity without sacrificing our unique features".

## 8. SMP Edit: the contract route (the lead's design; the operator left the route to the lead)

Operator: "It's a lot like Fullscreen Visualizer Edit but you can figure out the best contract route yourself."

**8.1 Two presentations, one application state.** Small mode and Full mode are two presentations of the same
live services (playback, queue, library, the one Visualizer owner). Switching between them is a retarget of live
owners, never a teardown and rebuild: audio, queue position, the system media session and the Visualizer's clock
and history carry across (plan 02 section 8.2 already requires this; Current_Plan 1C.2 makes "retarget before
rebuild" a standing rule).

**8.2 Small mode is the Media widget's own contract; the host differs by build (P8).** On the screensaver and MC
builds Small mode *is* the Media widget on the compositor, exactly as today, and never leaves it. On the SMP
profile build the same component sits in a desktop window, where its outer geometry is always live (edge and
corner drags, snapping to screen edges, to the work area and to its own last positions) with no Edit mode to
enter. In both hosts its children (artwork, text group, transport, volume, seek bar) keep the Media widget's Edit
rules and are adjustable only while the lock glyph is open, so an ordinary drag can never disturb them.

**8.3 Full mode is one tree of sections at every window size.** Plan 02 section 16A's tiling tree (the operator's
"no dead/empty sections and sections must connect", 7 Nov) is the layout model for Full mode whether the window is
full screen, maximised or dragged to any size: an internal node is a horizontal or vertical split with a normalised
ratio; a leaf is a section holding one content. Because the tree stores ratios and never pixels, resizing the
window scales every section's size and spacing with no reauthoring (P4). Full screen is the default window state
and is remembered; it is a state of the window, not a different layout system. On the screensaver and MC builds
Full mode stays inside the compositor (P8): it is a display-wide presentation on one display, the same kind of
takeover the fullscreen Visualizer is (plan 01), and its rectangle is that display; the tree, the sections and
every rule below are the same. Only the host of the rectangle differs.

**8.4 A section is the unit, and it adapts to its shape.** Every "child" of Full mode is a section: Navigation,
Library (Tracks), Queue (Playing Tracks), Track Information, Artwork, Visualizer (or Lyrics or Artist Collage in
its place), Transport, Search / Filter, Status. Each content declares, as data and in one registry:

- its minimum width and height, and a preferred aspect where it has one (Artwork);
- the orientations it supports and how it presents in each: Transport as a horizontal bar (top or bottom) or a
  vertical rail (left or right); the Visualizer as a tall pane, a wide strip or any rectangle (it is the real
  Visualizer card, which already renders at any aspect); Track Information stacked or side by side, with its
  alignment swap (R11); Navigation as a row or a rail;
- its fold priority when the window is too small (plan 02 section 16A's order), and what it folds into.

A section chooses its presentation from the rectangle it is given, by rule, so "controls on top or the side" and
"the Visualizer thin and wide along the bottom" are ordinary results of moving a section, not special layouts.

**8.5 The edit vocabulary.** Section 16A's four operations stand (Choose, Swap, Resize, Split or Remove), and the
operator's P4 adds two that the tree supports without becoming free-form:

- **Move to an edge:** drag a section to the top, bottom, left or right edge of the window, or of another section,
  to re-split the tree there (a live preview shows the resulting split). This is how the Transport goes to the
  top or the side and how the Visualizer becomes a strip along the bottom.
- **X, Y and XY resize:** dragging a shared edge changes one split's ratio (X or Y); dragging a corner where two
  splits meet changes both (XY). Snap stops and per-content minimums are 16A's.

Nothing floats and nothing overlaps in Full mode; the only detached surface is the Visualizer's Pop Out (plan 02
section 8.3). Plan 02 section 16's wider dock model (tabbed stacks, floating panels on other monitors) is not
needed to meet P4 and stays unadmitted unless the operator asks for it.

**8.6 SMP Edit is its own owner beside the existing Edit modes, built from the same parts.** This is what keeps
P5 true.

- *Separate owner and record.* SMP Edit edits one thing: the section tree of a Full mode layout, stored in SMP's
  own layout record (profile scoped, with layout slots as the saver has). It never reads or writes the widget
  layout record that ordinary Edit, Arrange and Fullscreen Visualizer Edit own, and those never touch the tree.
  Neither owner knows the other exists; there is no mode flag inside the existing Edit owner.
- *Shared parts, not shared state.* The handles, guides, snap rules, lock glyph, keyboard nudging, the
  commit / cancel transaction and the "one undo per gesture" rule are the components and helpers the existing
  Edit modes already use (the route Fullscreen Visualizer Edit took: its own surface, ordinary Edit's handlers).
  So the three feel the same in the hand, and a fix to a handle fixes all three.
- *One edit session per surface.* A surface (a compositor display, or the SMP build's window) is in at most
  one edit mode at a time. On the screensaver and MC builds Full mode is a display-wide presentation inside the
  compositor, so SMP Edit stands to it exactly as Fullscreen Visualizer Edit stands to the expanded Visualizer:
  entered from that presentation, editing only that presentation's record, with ordinary Edit unavailable on
  that display until the presentation collapses and available as ever on the other displays. Entering either
  never changes the other's record.
- *Arrange has an SMP section (P7).* Arrange gains one section for SMP that shows the Full mode section tree
  (and Small mode's children) and offers the same operations with the precision Arrange gives the widget layout
  today. It edits the same record through the same owner as SMP Edit, never a copy: the Edit / Arrange parity
  rule applies, so the same gesture made in SMP Edit and in Arrange's SMP section leaves the same stored tree
  (the parity harness pattern, extended). Arrange's existing sections are unchanged. On the SMP profile build,
  where the compositor's sections have nothing to show, the SMP section is Arrange's main section.
- *Inside a section, the section's own rules.* The Visualizer section keeps its glyph row and its own view
  gestures; Track Information keeps its alignment swap. SMP Edit moves and sizes sections; it does not reach
  inside them.
- *Proof owed when built:* the existing Edit suites (ordinary Edit, Arrange parity, Fullscreen Edit) run unchanged
  and green with SMP present and with SMP Edit entered; the widget layout record is byte-identical before and
  after any SMP Edit or SMP Arrange session, the section tree is byte-identical after any ordinary Edit or
  Arrange session, and SMP Edit and Arrange's SMP section agree gesture for gesture.

**8.7 Profiles decide what is built in, by capability, and so which host SMP uses.** The SMP profile build has no
compositor capability: the image presenter, transitions, image sources and the non-media widget families are
absent, and the SMP runtime never imports them (plan 02 section 8.1 already has this; an import-closure test like
the engine worker's proves it); there Small and Full mode are desktop windows. The screensaver and MC builds have
the compositor capability and the SMP capability together; there Small and Full mode are presentations inside the
compositor and need no desktop window (P8). The section tree, the section registry, SMP Edit and Arrange's SMP
section are written once against a small host interface ("give me a rectangle, tell me when it changes, take
focus, leave"), with two hosts: a compositor display and a desktop window. SMP code never assumes which one it
has.

**What must not be closed off before SMP starts** (rules for work done now):

- Media widget, Now Playing and seek bar components stay host-agnostic (no reach into the display compositor).
- The Visualizer stays one owner that can be retargeted between hosts and rendered at any aspect, strips included
  (Current_Plan 1C.2, and the border contract of 1C.4).
- Edit handles, guides and snapping stay reusable components, not code welded to the widget layout owner.
- The native core (plan item 8b, P3) renders the Visualizer into whatever surface its host provides, with no
  dependency on the image compositor.

## 9. Long-term audio and library parity (P6)

Plan 02 section 13 already sets the audio bar (shared and exclusive output, device selection with hot-unplug
recovery, gapless, crossfade, ReplayGain, an equalizer in a bypassable DSP chain, a high-quality resampler) and
section 5 sets the library's. P6 adds or sharpens:

- **Upmixing and downmixing:** explicit channel-layout handling in the DSP chain (stereo to multichannel and
  multichannel to stereo with stated coefficients, bit-transparent when source and device layouts match).
- **The equalizer is a first-class feature** with presets and per-device memory, not only a stage in a list.
- **A well indexed, growable library database:** schema versioned with migrations, indexes for every browse and
  sort the UI offers, incremental scan, and measured behaviour at large sizes (plan 02 section 5 and its budgets).
- **Full modern music-player parity without giving up what is ours:** the live Visualizer as a section, the
  theme and material system, Edit-grade rearrangement. Parity is a checklist to be written against named players
  when SMP is scheduled, not before.

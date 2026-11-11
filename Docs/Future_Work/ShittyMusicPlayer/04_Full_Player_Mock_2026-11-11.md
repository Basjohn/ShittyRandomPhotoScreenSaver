# SMP full-player mock (operator, restored 11 Nov 2026)

**Status:** design reference for the full-size ShittyMusicPlayer window, the long-range goal ("far far ahead of
us"). It is a mock: one example of the layout, coloured by one theme. The lead may adjust it for better UX and
functionality, and adjust the plans with it. Nothing here is scheduled; the order of work is plan 02
(`02_ShittyMusicPlayer_Implementation_Plan.md`), whose phase ladder and `--smp` gate still bind.

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
- A7. **Edit mode affordance (R3).** Entering SMP Edit shows each pane's handles and a swap target on drag, with
  the same handle sizes and guides as ordinary Edit; panes snap to the column grid; a "Reset Layout" lives in the
  Edit bar. The title bar and the transport bar's left cluster (transport buttons) keep their order, since muscle
  memory for play/pause matters more than freedom there. This narrows R3 slightly ("except title bar") and is for
  the operator to accept or reject.
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
- Whether A7's narrowing of Edit mode (the transport cluster's order fixed) is acceptable.

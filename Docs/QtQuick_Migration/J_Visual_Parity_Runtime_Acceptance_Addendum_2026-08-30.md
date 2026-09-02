# J Addendum — Post-Cutover Visual / Runtime Acceptance Cells

Date: 2026-08-30  
Applies to: `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`

This addendum records concrete eyes-on/runtime acceptance observations from the first corrected Quick production smokes so they do not disappear into vague “visual parity” wording.

H is now closed. This addendum must not reopen deterministic H contracts through stale prose: lifecycle/reconstruction, Media artwork/actions/event ownership, Reddit opening, Clock mode/CUSTOM persistence, Visualizer routing/reactivity/topology, ordinary-family resize, R6 Halo and R7 transition admission are accepted source/physical baselines. This addendum owns J visual/interaction acceptance on top of those contracts.

## 1. Parity+ baseline rule

J is a **Parity+** phase.

Historical successful presentation is the quality/behavior floor where it was better; it is not a ceiling and it is not a bug-for-bug target. Preserve genuine Quick improvements and deliberately improve weak historical behavior.

Use the dedicated durable reference:

`Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md`

Reference hierarchy for user-visible outcomes:

1. **Binding family screenshot oracle:** compare the matching files under `images/migration/Ideal (PreMigration)/` and `images/migration/Current (PostMigration)/`. For every pixel/detail actually visible in the family-specific Ideal image, that image is the highest visual parity authority; Current is the explicit post-migration regression baseline. This currently covers Abandonment Issues, Achievement Pulse, Gmail, Media, Reddit and Weather. Clock is intentionally absent because its current Quick presentation is acceptable.
2. current explicit operator observations that intentionally preserve or improve a newer treatment (for example the current Media transport strip);
3. 4.7.2 release screenshot — secondary broad-composition baseline;
4. 4.7.0 release screenshot;
5. `15099d3` — cleaner historical behavior-code reference;
6. `3fe5df6` — **known-good pre-Qt-Quick behavioral oracle for visualizer reactivity**; for unrelated broad UI archaeology it is simply a later reference than `15099d3`.

Agents must inspect the relevant paired repository images before changing a covered family. Prose is explanatory; it does not overrule the pictured target for visible details unless the operator explicitly chooses a newer treatment.

**Sequencing:** when the acting agent/model has reliable image inspection, do the paired-oracle family pass near the **front of J**, not as leftover polish after easier text-only tasks. A weak-vision agent may briefly defer the implementation to a vision-capable pass, but the oracle cells remain mandatory and cannot be closed from prose, tests, or historical code alone.

For implementation, current accepted Quick architecture always wins.

This is an outcome reference only: **never restore, wrap, adapt, proxy through, or copy back the deleted QWidget/QRhi/GL physical presenter architecture to obtain parity.**

Parity+ explicitly permits improvements. Example: preserve the newer Media transport strip if it is better; make seek work even though the old 4.7.2 release notes say its seek bar did not yet seek; preserve an adjacent/outside volume accessory while optionally retaining the useful in-card form as a separate option.

The exhaustive per-observation checklist is `Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`; this addendum never silently closes ledger rows.
## 2. Global scene acceptance

Required eyes-on cells:

- cold start: no full-scene black flash before intentional first frame;
- no intermittent flash of diagnostic/test colour bands or other non-product placeholder pixels. The Phase-A Slide proof leak is now source-proven and repaired as opt-in-only; physical validation remains. Use `J_Black_Flash_Surface_Continuity_Decomposition_2026-08-30.md` and `[QUICK_SURFACE]` for any remaining black/focus/context flash classification;
- first reveal: a clearly visible gentle reveal/fade rather than telemetry-only completion;
- click/focus current display: no whole-scene flicker;
- A -> B -> A focus across physical displays: no scene clear, reveal restart, stale frame or opacity jump;
- ordinary image transition boundaries: no black/stale handoff;
- competing image request during an active transition: current transition remains visually coherent and completes normally; the newer request is deferred/rejected before image truth moves, with no cancel-to-destination snap or bare image flash;
- Settings/CUSTOM replacement after H fix: no replacement-generation black frame beyond intentional readiness policy.

If instrumentation proves a click/focus action resets semantic image/reveal state, classify the smallest owner as H rather than accepting it as cosmetic.

## 3. Media card

Preserve:

- the current post-migration transport/control strip styling. **This is the only current Media visual treatment presently judged superior to the old implementation; do not generalize that exception to the rest of the current Media card.**
- the established app-volume outcome is an adjustable slim slider **next to the Media card**. The current integrated-in-card form must not silently replace that contract; retain it only if it becomes a deliberately selectable optional variant.

Correct:

- artwork must remain functional under the closed H2 engine-provider contract;
- artwork region should be materially larger and better balanced against title/artist text;
- artwork changes should recover the historically nicer fade/transition treatment without delaying provider truth or recreating the card;
- artwork border should not dominate the image;
- Spotify/video artwork whose source bitmap contains baked-in top/bottom black bars must be conservatively content-cropped before the ordinary fill/crop presentation; do not mistake genuinely dark album art for letterboxing;
- artwork and text block alignment should resemble the tighter pre-Quick hierarchy;
- provider logo/text inside the header frame should align consistently with Gmail/Reddit **and scale with the card as one authored header relationship; current logo+name headers are effectively not scaling with widget size**;
- Spotify header border thickness should match the shared header language unless a deliberate setting says otherwise;
- optional `Junk`/album and `Paused` state lines should be configurable rather than permanently consuming vertical space;
- controls, progress and optional volume must not force excessive empty outer-card height;
- when app volume is enabled, the established product wording/behavior is a slim vertical slider **next to the Media card**. Preserve an externally adjustable/adjacent presentation as the canonical behavior; if the integrated in-card variant is retained because it looks useful, expose it deliberately rather than changing the meaning of the existing toggle.

### Media live parity checklist

- [~] Slice 1 source repair remains cumulative: seek track is 75% of its previous effective width; provider header uses the shared compact branded-frame language and logo/label vertical centres coincide; system mute is 75% of its prior size. **AWAITING PHYSICAL VALIDATION.**
- [~] Slice 2 geometry refinement remains cumulative for metadata/seek +2 px, system-mute 4 px total right-edge inset, and the exact 2 px artwork border. Its full header-top→seek-bottom artwork span is now only the Slice-3 reference envelope rather than the final frame size. **AWAITING PHYSICAL VALIDATION.**
- [~] Slice 3 artwork refinement: frame height is 85% of the Slice-2 reference span and centred within it; width is reduced by the same 15% and then narrowed a further 15% (72.25% of the Slice-2 authored width). `Image.PreserveAspectCrop` remains authoritative. The Quick image provider now strips only convincing symmetric baked-in near-black top/bottom bands once per new artwork identity, covering Spotify video-thumbnail letterboxing that `PreserveAspectCrop` alone cannot remove. Rounded clipping is owned by a retained `MultiEffect` mask matching the actual non-square frame rather than the old provider-side rounded-square pre-crop, preventing source black/transparent corners from escaping the border. **AWAITING PHYSICAL VALIDATION.**
- [~] Slice 4 metadata/settings/shadow refinement: retained Title/Artist/Album projection is always normalized to title case without mutating provider/runtime truth; Album and Playback State lines have independent default-ON Settings toggles (`show_album`, `show_playback_state`) and participate in layout-slot persistence; artwork frame, transport surface and app-volume track use one cheap retained duplicate rectangle each, with a Python-resolved signed 4 px vector from global shadow direction. The former hard-coded SE blurred artwork shadow is removed. **AWAITING PHYSICAL VALIDATION.**
- [~] Slice 5 metadata-fit/stroke-scaling refinement: Title/Artist/Album each use single-line `Text.HorizontalFit` with 6 pt minimum and right-elide only at the floor, restoring shrink-before-clip behavior. Artwork/header/transport/app-volume outer strokes compensate for the whole-card CUSTOM transform and target a visible baseline +/-1 px thickness, clamped to a 1 px minimum, so enlarged cards do not balloon the small framing lines and shrunk cards do not lose them. **AWAITING PHYSICAL VALIDATION.**
- [~] Slice 6 shadow/theme-role refinement: artwork/transport/app-volume hard duplicate shadows are superseded by small cached `RectangularShadow`s using the same Python-resolved global direction vector with `1.20x` / `1.15x` / `1.05x` displacement respectively. Their blur is intentionally bounded to `25%` of global blur, clamped `2..6 px`. App-volume outline now has an independent alpha-aware persisted swatch (`spotify_volume_border_color`); the existing volume-fill swatch is alpha-aware too. Media header Fill + Border are independent alpha-aware persisted swatches so the pill is ready for later Widget Theme role projection rather than being tied to the outer card border. **AWAITING PHYSICAL VALIDATION.**
- [~] Slice 7 header closure: Media now consumes the same `BrandedHeader.qml` primitive as the other branded families, including ALL-CAPS intrinsic-width text, independent alpha-aware Header Text, logo shadow, retained text shadow, scale-aware border and a cached direction-aware extension shadow using the Media transport-bar shadow profile. **AWAITING PHYSICAL VALIDATION.**
- [ ] Validate Slices 1–8 against the actual widget at ordinary scale plus enlarged and shrunk CUSTOM sizes: confirm the smaller/narrower artwork no longer crowds or clips the seek region, embedded Spotify video bars are gone, rounded corners contain all source pixels, ordinary album art is not falsely cropped, metadata/seek +2 px and mute inset remain correct, Title/Artist/Album casing looks natural on mixed/all-caps provider data, long metadata shrinks before clipping without wrapping, each optional line hides/reappears immediately and survives Settings reload/layout-slot use, artwork/transport/volume shadows all follow at least two non-SE global directions with the requested relative offsets and only slight blur, alpha in the header/volume swatches is honored, the header extension shadow keeps opposite-edge coverage, the four scale-aware framing strokes remain legible without exceeding the +/-1 px visible-thickness contract, and artwork/metadata fade timing remains gentle without delaying authoritative provider truth.
- [~] **Slice 9 external-volume closure / Media parity lock.** Media's canonical app-volume control is now the planned scene-local **external right accessory rail**, default ON whenever Media exposes app-volume capability. `OverlayWidget.rightAccessoryExtent/rightAccessoryContent` keeps that rail in the same retained root/lifecycle/CUSTOM transform while the ordinary card reclaims the accepted full content width; the display-level card shadow deliberately covers the card only, not the accessory lane. The rail's Track/Fill/Outline and the Seek Bar's Track/Fill/Shadow/Glow are alpha-aware persisted family swatches grouped in collapsed `Volume Control` / `Seek Bar` Settings buckets, with Header Fill/Border/Text grouped under `Header Appearance`. Default-valued swatches remain semantic Inherit; deliberate changes become family overrides. The Slice-8 white volume-fill regression is fixed by preserving the accepted gray volume fallback unless a real `media.volume.fill` / shared accent theme role overrides it. **AWAITING PHYSICAL VALIDATION.** If this validates, Media visual parity is complete. Later J/J+ work must not move volume back inside the card, steal the reclaimed width, reset accepted Media alignment/shadows/strokes/fades, or re-hardcode these semantic roles unless a specifically named Media regression is opened.

## 4. Gmail card

- no message row may draw outside the card/content clip;
- long sender/subject text must elide/clip inside its owned columns;
- refresh indicator appearance/placement should use the preferred Reddit treatment for consistency;
- Gmail logo/header baseline should align with the other branded cards and the logo+name header should scale coherently with the card;
- header frame border/radius should match the shared visual language.

## 5. Reddit cards

- header logo/text alignment should be consistent with Gmail/Media and scale coherently with the card;
- current refresh indicator is the preferred comparison point for Gmail;
- row density/spacing should remain close to the visually successful pre-Quick treatment;
- visual fixes must not regress the H URL action wiring or interaction-mode admission.

## 6. Achievement Pulse

- remove avoidable dead space;
- achievement icon belongs with the achievement/content hierarchy rather than floating awkwardly;
- unlocked count must not truncate when the card has available width;
- title/game/stat columns should use available space before eliding;
- preserve the semantic data and current Steam ownership while improving layout only.

## 6A. Ordinary placement versus CUSTOM

The ordinary and CUSTOM layout policies are deliberately different.

**Ordinary / non-CUSTOM:**

- do not allow enabled widgets at the same authored destination to collapse into an unreadable dog-pile;
- Media + Visualizer has a stronger existing product relationship: when they are routed to the same display and sufficient usable space exists, resolve the Visualizer into a sensible adjacent/free region relative to Media;
- preserve canonical anchor/margin/clamp rules and monitor routing;
- do not solve this by silently enabling the global optional `stacking_enabled` policy for all widget families.

**CUSTOM:**

- committed user geometry wins;
- overlap is legal;
- cross-display transfer is legal where the existing CUSTOM contract admits it;
- no automatic ordinary collision/free-space owner may move an explicitly committed CUSTOM item behind the user's back.

## 6B. Pointer and retained context interaction

- the operator must not see both the ordinary OS cursor and an additional cursor-shaped halo as two competing pointers; accept one coherent visible pointer treatment while retaining same-scene auxiliary ownership;
- a context submenu must not remain open indefinitely merely because its parent was hovered once; moving to another submenu replaces the current submenu, and leaving the parent/submenu interaction path dismisses it with only the intentional hover grace needed to cross into the submenu;
- implement submenu lifetime inside the retained same-scene menu. Do not add a popup/native window, polling loop, or reintroduce the opening-right-click self-dismiss fixed by `747e3140`.

### Context interaction live checklist

- [~] Event-driven submenu lifetime implemented: leaving both the parent row and submenu closes it after one event-loop handoff; crossing directly between the overlapping row/submenu remains admitted. No timer or polling owner. **AWAITING PHYSICAL VALIDATION.**
- [ ] Validate both Transitions and Visualizers submenus: parent -> submenu, submenu -> parent, submenu -> blank menu space, submenu -> outside menu, and submenu A -> submenu B.
- [ ] Keep the existing deferred opening-event dismiss protection intact while validating submenu lifetime.

## 7. Header / shell consistency matrix

### Edit chrome / header-row live checklist

- [~] Shared CUSTOM edit X alignment now projects the Python/session-owned absolute `resize_scale` into the retained overlay and centres the 22 px X on the common authored 32 px header/logo/refresh row; it no longer uses a fixed `y: 8`. The same row is deliberately used on widgets with no refresh glyph. **AWAITING PHYSICAL VALIDATION.**
- [~] Gmail + Reddit are the only retained refresh-glyph presentations found in the current QML tree; both glyphs use `opacity: 0.7`. **AWAITING PHYSICAL VALIDATION.**
- [~] Slice 7 shared branded-header normalization: Media, Gmail, Reddit, Achievement Pulse and Abandonment Issues consume one `BrandedHeader.qml` contract: 25 px logo / 8 px gap / 20 px total horizontal padding / 36 px minimum height / 9 px radius / family-invariant 16.4 pt bold ALL-CAPS label. Header text is never elided; the pill widens to the full logo + label width. Each header has independent alpha-aware Fill + Border + Text settings, retained text shadow, logo shadow, shared scale-aware stroke compensation and a cached direction-aware extension shadow using the accepted Media transport-bar blur/offset profile. Gmail/Reddit `header_logo_px_adjust` remains retired. **AWAITING PHYSICAL VALIDATION.**
- [~] Gmail + Reddit refresh positioning is part of the protected header-row contract: right-anchored, vertically centred on the common header area, 70% opacity. The edit-mode X uses the same authored row via session-owned `resize_scale`. **AWAITING PHYSICAL VALIDATION.**
- [ ] Validate the X at baseline, enlarged and shrunk CUSTOM scales on Reddit/Gmail first, then spot-check Media, Weather, Clock, Achievement Pulse, Abandonment Issues and Visualizer/non-refresh families. Confirm the X stays on the same horizontal header row without stealing resize/move input, and refresh glyphs remain readable at 70% opacity.
- [ ] Validate the five branded header pills side-by-side at baseline plus enlarged/shrunk sizes: logo/text vertical centre, logo-to-label gap, pill padding/height/radius, all-caps intrinsic-width expansion, alpha-aware fill/border/text, logo/text shadows, extension shadow direction/opposite-edge coverage, and visible border thickness must remain coherent. Visualizer is exempt from the shared stroke migration.
- [ ] **J/J+ protected authored baseline.** Family-specific parity work may correct each widget's outer padding, content spacing, row geometry and placement of the shared header as a whole, but it must not fork/rewrite the accepted `BrandedHeader` internals, restore Gmail/Reddit logo-size exceptions, reduce refresh opacity from 70%, move refresh/edit-X off the shared row, remove the accepted logo/text/header shadows, undo already-accepted Media geometry/shadow/stroke choices, re-hardcode Slice-8 semantic-role consumers, or replace the shared artwork/metadata fade primitives with family-local timers/effects unless the operator opens a specifically named regression. Parity is not authority to revert newer authored improvements merely because the pre-migration screenshot differed.
- [~] Slice 8 first line-width rollout: the shared visible baseline +/-1 px, minimum-1-px stroke helper now covers selected Gmail message/boundary separators, Reddit/Reddit2 separators, Weather separators and Steam info/artwork/metric decorative borders/separators in addition to the already-protected Media/header uses. **AWAITING PHYSICAL VALIDATION.** Continue incrementally only where thickness is decorative; do not blanket-convert semantic/content geometry, and do not regress already-migrated uses. Visualizer remains exempt.
- [~] Slice 8 Widget Theme semantic-role projection: one shared sparse resolver now owns Header Fill/Border/Text, Media transport/mute/volume/progress roles, Gmail action/separator roles, Reddit/Weather/Clock separators, Steam panels/tooltips/artwork/gradients/metrics, and the retained Context Menu palette. Default-valued family swatches remain implicit Inherit; genuinely changed family swatches stay explicit overrides. `local.*` semantic values are runtime context and never serialize. Context Menu Default Dark was first reconciled to its accepted retained QML pixels, then its palette literals were replaced by one generation-scoped theme projection. **AWAITING PHYSICAL VALIDATION / PHASE 1b LIVE THEME UI.** Do not re-hardcode migrated colours during parity work.
- [~] Slice 8 fade polish: shared `ArtworkFadeImage.qml` now uses gentler `200/340 ms` fade-through timing for Media/Achievement Pulse/Abandonment Issues, and Media Title/Artist/Album use an event-driven old->new text crossfade (`240/340 ms`) while authoritative metadata updates immediately. **AWAITING PHYSICAL VALIDATION.** No recurring animation timer, provider polling or data freshness delay may be introduced.
- [~] Slice 9 Steam-logo normalization: Achievement Pulse and Abandonment Issues keep the shared 25 px `BrandedHeader` logo box, but now consume a tightly alpha-cropped derivative of the supplied Steam asset because the original bitmap's large transparent margins made the visible mark materially smaller than Gmail/Reddit/Media at the same box size. **AWAITING PHYSICAL VALIDATION.** This is an asset-boundary correction, not a Steam-specific scale override; later parity work must not reintroduce transparent-padding-driven apparent-size drift.
- [~] Slice 9 Settings organization proves the intended semantic-override UX: Media is decomposed into `Provider & Layout`, `Appearance`, `Header Appearance`, `Artwork`, `Transport Controls`, `Seek Bar`, and `Volume Control` buckets. This organization is UI presentation only and does not become a second theme/state/geometry owner. Follow-up bucket cleanup for other overloaded widget sections should reuse semantic groupings without mechanically exposing every sparse theme role. **AWAITING SETTINGS GUI VALIDATION.**

Check Media, Gmail, Reddit, Achievement Pulse and Abandonment Issues side-by-side for:

```text
outer border width
outer corner radius
header-frame border width
header-frame radius
logo vertical centre
logo-to-label gap
label baseline
header horizontal padding
refresh/control icon vertical centre
shadow direction/blur/spread
```

Differences need to be either setting-driven/family-intentional or removed.


### Weather resize binding-loop gate

A pre-R7/H9 physical resize experiment emitted repeated Qt/QML warnings:

`WeatherPresentation.qml: Binding loop detected for property preferredContentHeight` (binding at line 24 in the observed build).

Treat this as **J geometry/parity correctness debt by default**, not harmless log cosmetics. H is already closed; reopen a smaller functional owner only if later evidence proves actual committed-geometry or lifecycle corruption. The current preferred-height expression reads `readyColumn.childrenRect.height + shellInset` while the content column is centred inside the Python-assigned outer rect; during resize/reflow the preferred-size notification can participate in the QML -> Python outer-rect -> QML layout feedback edge. Before Weather J parity is accepted, source-localize the smallest cycle and prove repeated wheel/corner resize plus Save/recreation yields stable preferred geometry with **zero binding-loop warnings** in `screensaver_qml.log`. Do not paper it over by suppressing Qt messages or by adding a second geometry owner.

## 8. Visualizer

With H Spectrum topology/data and CUSTOM cross-display admission accepted, physically inspect all five modes again for J Parity+.

Bubble: H closed with R-69 as a golden scaling/reactivity contract. Canonical, wide and tall CUSTOM geometry must preserve authored musical response; do not globally compress head radius, pulse/motion or already-normalized Ghost/history displacement to make extreme geometry tidier. J may polish an oversized extreme expansion tail only if it preserves the full response curve. Raw ~90 Hz cadence never licenses visible-reactivity loss.

Spectrum: H already restored/validated the correct functional representation family and live topology. J Parity+ owns exact spacing, outline/glow, gradient/rainbow treatment and motion polish while preserving the accepted large-viewport smoothing and musical response. Explicitly include “switch into Spectrum from another mode,” not only cold-start Spectrum.

All modes: verify canonical/wide/tall viewport behavior and shell/clip/shadow correctness already required by the main J decomposition.

## 9. One-shot diagnostic to support parity work

At initial family bind and each generation recreation, optionally emit one bounded record per ordinary widget:

```text
widget_id
effective_screen_index
preferred_content_width/height
final_outer_x/y/width/height
committed_custom_rect (or none)
DPR
anchor/clamp result
```

This is diagnostic evidence only. Do not turn it into a polling geometry owner or per-frame callback stream.

## 10. Acceptance principle

A prettier screenshot is not enough if interactions or lifecycle are broken, and a green model/unit test is not enough if the actual production pixels are visibly wrong. J closes only when the physical presentation is both correct and coherent with the deterministic owner contracts, **and every unresolved J row in the operator ledger has been explicitly reviewed.**


## 11. H/J boundary updates from the 14:40–14:46 physical run

These observations are deliberately *not* extra J work:

- terminal access violation / dangling `BackgroundRenderItem` slot: **closed H1b preservation target**;
- Clock QML null-model retirement storm: **closed H1b preservation target**;
- Visualizer refusing its own different CUSTOM display: H routing/admission contract;
- Spectrum's repeated all-1.00 35-bar payload **and** dense segmented-block topology replacing the intended continuous-column Spectrum/Organ representation: H functional defects until correct data + basic topology are restored;
- CUSTOM disabling non-size Media controls: H Settings ownership defect.
- missing Visualizer middle-click current-mode preset hotswap: H8 deterministic interaction restoration, including Custom snapshot semantics; J may later judge transition feel only after the action exists.

J should inherit only the remaining eyes-on/fidelity work after those owners are functionally correct.

Bubble remains J-first despite its poor visible response because objective authored cadence/integration remains healthy. Its partial/CUSTOM resizing is a preservation target.

The ~2 s explicit `__pycache__` cleanup observed after visible shutdown is a later performance/maintenance decision only after H restores a clean terminal lifecycle.


## 12. Qt/QML diagnostic acceptance

J physical acceptance reads `screensaver_qml.log` alongside `screensaver.log`. A visual run is not fully evidenced when the Qt/QML sidecar is missing or contains unexplained migration-relevant binding/component/provider/signal/slot/scene errors.

The sidecar itself must exist even on a zero-message clean run and contain session markers. This is capture-health evidence, not cosmetic logging.

See `Docs/Qt_QML_Observability.md`.

## 13. Retained operator affordances

### CUSTOM/Edit alignment guides — mandatory J parity

The operator currently sees **none of the useful visible alignment/snap guide lines that existed before migration**. Current Quick source already contains grid/safe-gutter/vertical/horizontal guide presentation and a Python `set_guides(...)` seam, but no production caller currently publishes guide sets into that seam. This is a visible interaction-parity regression and should be worked early in J alongside the family screenshot oracle when the acting agent can inspect the result reliably. Reuse the existing Python snap/layout authority; do not add QML geometry truth or a second layout owner.

Acceptance: while moving/resizing an item, useful centre/peer/edge/safe-gutter relationships visibly appear and clear with the same transaction, without changing Save/Cancel semantics or ordinary non-CUSTOM layout. A weak-vision agent may defer the eyes-on tuning to a vision-capable pass, but may not close or downgrade this cell.

### Performance/debug overlay — low priority

Any overlay/telemetry or optimization work in J follows `Docs/Guardrails/Performance_Optimization_Contract.md`. In particular, the overlay must distinguish active latency tails from demand-light no-swap `dt_max`, and must not present high-refresh pacer skip or raw GC counts as standalone quality verdicts.

The operator also reports that the prior performance/debug overlay affordance is absent. Preserve this as low-priority J/diagnostic work. A future overlay may consume bounded read-only metrics already owned by current performance/runtime instrumentation, but must be a retained Quick presentation under the accepted scene and must not resurrect the legacy `gl_profiler.py` rendering path, QWidget/QRhi/GL presenter ownership, another accelerated window, or a new cadence owner.

Acceptance: when explicitly enabled for diagnostics, one lightweight Quick-native overlay shows the agreed useful metrics and disappears cleanly; normal product mode pays no hidden polling/render-owner cost merely because the feature exists.


# J Addendum — Post-Cutover Visual / Runtime Acceptance Cells

Date: 2026-08-30  
Applies to: `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`

This addendum records concrete eyes-on/runtime acceptance observations from the first corrected Quick production smokes so they do not disappear into vague “visual parity” wording.

It does **not** move deterministic H failures into J. H1 reconstruction/terminal ownership and H2 Media artwork provider identity are now closed. Reddit URL opening and Clock runtime mode persistence now have prepared H repairs but remain H until real validation closes them. Media Play/Pause/seek, Spectrum data/topology, CUSTOM Visualizer cross-display admission and CUSTOM Settings over-locking also remain H.

## 1. Parity+ baseline rule

J is a **Parity+** phase.

Historical successful presentation is the quality/behavior floor where it was better; it is not a ceiling and it is not a bug-for-bug target. Preserve genuine Quick improvements and deliberately improve weak historical behavior.

Use the dedicated durable reference:

`Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md`

Reference hierarchy for user-visible outcomes:

1. current explicit operator observations/comparison screenshots;
2. 4.7.2 release screenshot — strongest broad visual baseline and explicitly the last Raw PySide6 architecture release;
3. 4.7.0 release screenshot;
4. `15099d3` — cleaner historical behavior-code reference;
5. `3fe5df6` — later mixed reference containing some migration work.

For implementation, current accepted Quick architecture always wins.

This is an outcome reference only: **never restore, wrap, adapt, proxy through, or copy back the deleted QWidget/QRhi/GL physical presenter architecture to obtain parity.**

Parity+ explicitly permits improvements. Example: preserve the newer Media transport strip if it is better; make seek work even though the old 4.7.2 release notes say its seek bar did not yet seek; preserve an adjacent/outside volume accessory while optionally retaining the useful in-card form as a separate option.

The exhaustive per-observation checklist is `Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`; this addendum never silently closes ledger rows.
## 2. Global scene acceptance

Required eyes-on cells:

- cold start: no full-scene black flash before intentional first frame;
- no intermittent flash of diagnostic/test colour bands or other non-product placeholder pixels. If a bounded startup trace proves an actual diagnostic/test frame is admitted as readiness content, repair that deterministic owner before treating the symptom as J polish;
- first reveal: a clearly visible gentle reveal/fade rather than telemetry-only completion;
- click/focus current display: no whole-scene flicker;
- A -> B -> A focus across physical displays: no scene clear, reveal restart, stale frame or opacity jump;
- ordinary image transition boundaries: no black/stale handoff;
- interrupted transition: still visually coherent after the deterministic cancel-to-destination contract fires;
- Settings/CUSTOM replacement after H fix: no replacement-generation black frame beyond intentional readiness policy.

If instrumentation proves a click/focus action resets semantic image/reveal state, classify the smallest owner as H rather than accepting it as cosmetic.

## 3. Media card

Preserve:

- the new transport/control strip styling, which is an improvement;
- the established app-volume outcome is an adjustable slim slider **next to the Media card**. The current integrated-in-card form must not silently replace that contract; retain it only if it becomes a deliberately selectable optional variant.

Correct:

- artwork must remain functional under the closed H2 engine-provider contract;
- artwork region should be materially larger and better balanced against title/artist text;
- artwork changes should recover the historically nicer fade/transition treatment without delaying provider truth or recreating the card;
- artwork border should not dominate the image;
- artwork and text block alignment should resemble the tighter pre-Quick hierarchy;
- provider logo/text inside the header frame should align consistently with Gmail/Reddit;
- Spotify header border thickness should match the shared header language unless a deliberate setting says otherwise;
- optional `Junk`/album and `Paused` state lines should be configurable rather than permanently consuming vertical space;
- controls, progress and optional volume must not force excessive empty outer-card height;
- when app volume is enabled, the established product wording/behavior is a slim vertical slider **next to the Media card**. Preserve an externally adjustable/adjacent presentation as the canonical behavior; if the integrated in-card variant is retained because it looks useful, expose it deliberately rather than changing the meaning of the existing toggle.

## 4. Gmail card

- no message row may draw outside the card/content clip;
- long sender/subject text must elide/clip inside its owned columns;
- refresh indicator appearance/placement should use the preferred Reddit treatment for consistency;
- Gmail logo/header baseline should align with the other branded cards;
- header frame border/radius should match the shared visual language.

## 5. Reddit cards

- header logo/text alignment should be consistent with Gmail/Media;
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

## 7. Header / shell consistency matrix

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

## 8. Visualizer

After H Spectrum repair and H CUSTOM cross-display admission repair, physically inspect all five modes again.

Bubble: the current complaint is now stronger than “slightly less reactive”: physical use can be **barely reactive**, with delayed visible start/stop and very little contraction/expansion. Do not answer this by arbitrary sensitivity/growth tuning. First correlate playback edge -> source/logical state -> retained publication -> visible response; an obvious stale/delayed owner defect is repaired at that seam, otherwise compare/tune authored visible response against the accepted baseline in J. Raw ~90 Hz cadence alone does not close this cell. **Partial/CUSTOM resizing is currently a provisional physical PASS and should be preserved.**

Spectrum: H must first restore the correct **functional** representation family. The operator's intended Organ/Spectrum comparison is continuous bottom-aligned frequency columns; the current dense matrix of tiny segmented blocks is not merely a styling difference. Once H restores correct data + topology, J Parity+ owns exact spacing, outline/glow, gradient/rainbow treatment and motion polish. Explicitly include “switch into Spectrum from another mode,” not only cold-start Spectrum.

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

J should inherit only the remaining eyes-on/fidelity work after those owners are functionally correct.

Bubble remains J-first despite its poor visible response because objective authored cadence/integration remains healthy. Its partial/CUSTOM resizing is a preservation target.

The ~2 s explicit `__pycache__` cleanup observed after visible shutdown is a later performance/maintenance decision only after H restores a clean terminal lifecycle.


## 12. Qt/QML diagnostic acceptance

J physical acceptance reads `screensaver_qml.log` alongside `screensaver.log`. A visual run is not fully evidenced when the Qt/QML sidecar is missing or contains unexplained migration-relevant binding/component/provider/signal/slot/scene errors.

The sidecar itself must exist even on a zero-message clean run and contain session markers. This is capture-health evidence, not cosmetic logging.

See `Docs/Qt_QML_Observability.md`.

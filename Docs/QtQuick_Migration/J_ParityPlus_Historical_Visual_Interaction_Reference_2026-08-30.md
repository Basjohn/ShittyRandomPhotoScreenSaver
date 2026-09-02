# J Parity+ — Historical Visual / Interaction Reference

Date: 2026-08-30  
Applies to: Phase J final physical/visual acceptance, using closed-H functional presentation contracts as the non-regression baseline.

## 1. Purpose

Phase J is **Parity+**, not a vague “make it look roughly like before” pass.

The target is:

> Recover at least the proven user-visible quality, density, geometry, clipping, feature availability, interaction behavior and design language of the successful pre-Quick application where those outcomes were better, **while preserving genuine Quick-era improvements and deliberately improving weak legacy outcomes where safe**.

Parity is the floor. The `+` matters.

This is **not** bug-for-bug compatibility and it is **not** implementation compatibility.

Examples:

- the newer Media transport strip may be kept because the operator prefers it;
- the old 4.7.2 seek bar is useful as a visual/interaction reference even though the release notes explicitly say clicking it did not seek yet — closed H4 made seeking functional, and J must not reproduce that limitation;
- the app-volume control remains a Media-dependent child widget; the historical separate adjacent accessory is the default outcome for the existing toggle, while an integrated in-card variant may survive only as an explicit additional option;
- old Spectrum/Organ presentation is a topology/design oracle; closed H already established correct functional topology/live data, and J now tunes glow/spacing/colour without weakening that response.

## 2. Reference hierarchy

Use references in this order for **user-visible outcomes**:

### 2.1 Repository paired migration screenshots — highest J visual authority

The strongest family-by-family parity oracle now lives in the repository itself:

- `images/migration/Ideal (PreMigration)/` — the achievable pre-migration visual target.
- `images/migration/Current (PostMigration)/` — the current Quick comparison/regression baseline.

For any J work on a covered family, inspect the corresponding image pair **before changing QML or layout constants**. When prose, release-wide screenshots, or historical-source inference disagree with a detail clearly shown by the pair, the `Ideal (PreMigration)` image wins for that visible detail. The paired images are outcome authority only; they grant no authority to resurrect the old presenter architecture.

The current paired set covers Abandonment Issues, Achievement Pulse, Gmail, Media, Reddit and Weather. Clock is intentionally absent because its current Quick presentation is already considered acceptable. Current filenames in the `Current (PostMigration)` directory are intentionally descriptive of visible defects and may be used as a compact visual checklist.

For a vision-capable agent this paired-image reconciliation is an **early mandatory J task**, not optional finishing polish. Weak-vision agents may briefly defer it to a vision-capable pass, but cannot downgrade or close it from prose.

| Family | Ideal oracle | Current comparison |
| --- | --- | --- |
| Abandonment Issues | `Ideal (PreMigration)/AbandonmentIssues.png` | `Current (PostMigration)/AbandonIsFineActually.png` |
| Achievement Pulse | `Ideal (PreMigration)/AchievementPulse.png` | `Current (PostMigration)/AchievPulseBigMiddlespaceTruncatedUnlockWrongAchievIconPosition.png` |
| Gmail | `Ideal (PreMigration)/Gmail.png` | `Current (PostMigration)/Gmailescapingtextlogoalignbad.png` |
| Media | `Ideal (PreMigration)/Media.png` | `Current (PostMigration)/MediaGoodControlBarBadRest.png` |
| Reddit | `Ideal (PreMigration)/Reddit.png` | `Current (PostMigration)/RedLogoAlignmentRefreshwrongUglyGapBetweenTimeAndPost.png` |
| Weather | `Ideal (PreMigration)/Weather.png` | `Current (PostMigration)/Weatherpoorpaddingandspacing.png` |

Explicit operator decisions may preserve a newer treatment that is preferred even when it differs from the old image. **Current explicit Media exception: the post-migration transport/control bar is the only current Media visual treatment presently judged superior to the old implementation. Preserve that strip; default the rest of Media back to the Ideal image unless a later operator decision names another exception.** Exceptions must be explicit; an implementation agent must not infer them from the Current screenshot or replace the pictured target with its own aesthetic judgement.

### 2.2 Current explicit operator observations

Current physical observations are the strongest clarification of behavior not completely captured by the paired stills, and they decide explicit exceptions where a newer Quick treatment is preferred. They do not downgrade the paired images into optional inspiration.

### 2.3 Release screenshots — broad composition oracle

The GitHub Releases screenshots remain useful whole-screen/widget-composition references, especially for relationships not visible in the isolated paired images.

Primary:

- Release 4.7.2: <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/releases/tag/4.7.2>
- Embedded release screenshot: <https://github.com/user-attachments/assets/76cb21ce-d228-49bb-a397-9a0a47a0ee06>

The 4.7.2 release explicitly identifies itself as the **last version on the Raw PySide6 architecture** before the major Qt Quick migration. It is therefore an especially useful broad visual baseline without granting its implementation any authority.

Secondary:

- Release 4.7.0: <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/releases/tag/4.7.0>
- Embedded release screenshot: <https://github.com/user-attachments/assets/82e1fd3e-99b7-4c96-8536-580f4cdef463>

### 2.4 Historical source snapshots — behavior/reference archaeology only

Cleaner old-code reference:

- `15099d389e5091942a0ce3d6e6311d33b6043d3d`
- <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/commit/15099d389e5091942a0ce3d6e6311d33b6043d3d>

Later reference:

- `3fe5df687387b6b6a121142372c43a7719442386`
- <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/commit/3fe5df687387b6b6a121142372c43a7719442386>

For broad UI/presentation archaeology, `15099d3` can still be the cleaner old architecture snapshot. **For visualizer reactivity, however, the user-supplied `3fe5df6` source tree is explicitly the known-good pre-Qt-Quick behavioral oracle** and should be compared line-by-line against current logical/configuration/presentation semantics. It remains a behavior oracle only, never an architecture to restore.

### 2.5 Current architecture and contracts

For **implementation**, current accepted Quick architecture always wins over every historical visual reference.

If historical code achieved the right outcome through a deleted owner, reproduce the outcome through the current owner instead.

## 3. Absolute anti-resurrection rule

Historical references may answer questions such as:

```text
How large was this card?
How did rows clip?
Where did the volume accessory sit?
How did Media and Visualizer share ordinary space?
How did Spectrum/Organ fundamentally draw?
What metadata was optional?
How did hover/menu interaction feel?
What visual hierarchy did the headers use?
```

They may **not** answer:

```text
Which presenter should own it now?
Should QWidget/QRhi/GLCompositor be restored?
Should a compatibility facade be added?
Should old timers/workers/providers be revived?
Should a second accelerated surface be created?
```

Never restore, wrap, adapt, copy back or proxy through the deleted QWidget/QRhi/GL physical presenter architecture merely because its pixels were better.

## 4. Closed H boundary versus J under Parity+

Parity+ does not reopen H functional contracts. H closed with Quick-only lifecycle/presentation ownership, functional family actions, Visualizer routing/topology/reactivity, CUSTOM ownership, R6 Halo and R7 transition admission accepted. J preserves those behaviors while improving physical quality. If later evidence falsifies one, reopen the smallest demonstrated owner/incident rather than treating J as permission to redesign the accepted contract.

For Spectrum specifically, H accepted the recognizable continuous-column representation family with non-degenerate live frequency data and large-viewport smoothing. J owns screenshot-level spacing/glow/colour/motion parity without changing that functional identity or weakening musical response.

### J owns Parity+ physical quality

Examples:

- card proportions/density;
- artwork size and chrome balance;
- clipping/elision;
- border/radius/header alignment;
- logo + header-name scaling with the card/widget (current ordinary-family headers are effectively fixed-size while cards scale);
- black flash/flicker;
- gentle reveal;
- submenu feel;
- pointer presentation;
- ordinary free-space composition;
- exact visualizer spacing, glow, gradients, line thickness and motion feel;
- Bubble visible responsiveness if no earlier deterministic stale/delay defect is found.

## 5. Spectrum / Organ reference boundary

The operator supplied a direct current-vs-intended comparison.

The intended Organ/Spectrum family is recognizably:

- a modest number of bottom-aligned vertical frequency columns;
- column height varies with frequency content;
- columns are continuous bar shapes rather than a screen-filling matrix of tiny repeated cells;
- the preset owns its established colour/outline/glow language.

The current Quick failure is fundamentally different:

- a dense, tall matrix of tiny segmented blocks;
- visual topology is wrong before considering exact colour/glow polish;
- runtime evidence also shows a 35-bar authored/computed payload repeatedly saturating at/near `1.00`.

Closed H5 investigated and accepted **both**:

```text
data correctness:
FFT/bands -> Spectrum shaping -> normalization/gain/floor/expansion -> final bar vector

presentation identity/topology:
mode/preset -> render snapshot -> renderer implementation -> primitive/segment topology -> retained draw
```

Saturation may explain uniform height/energy. It does **not** by itself explain why a continuous-column Spectrum became a dense segmented-cell matrix.

Accepted H Spectrum baseline:

- correct Spectrum mode/preset path;
- non-degenerate live frequency data;
- correct basic Organ/Spectrum representation family (continuous frequency columns, not the block matrix);
- correct behavior after mode switch and recreation.

J Parity+ then owns the exact:

```text
column width/gap
outline thickness
gradient/rainbow distribution
glow strength
baseline spacing
outer shell relationship
animation smoothness
visual elegance
```

## 6. Component Parity+ matrix

### Global scene

Floor:

- no black/stale/test frames;
- coherent focus and transition boundaries;
- gentle intentional reveal;
- no duplicate cursor treatment.

Plus:

- retain smoother/newer Quick interactions where they are genuinely better.

### Media

Floor:

- historical density/proportion/hierarchy;
- large useful artwork;
- coherent provider/header alignment;
- optional metadata;
- a separate adjacent/outside adjustable app-volume child item with its own geometry, dependent on Media and following Media's display route/lifecycle;
- feature controls remain usable;
- artwork fades where historically supported; the current visible artwork without the nicer transition is a J Parity+ gap, not an H provider failure.

Plus:

- retain the newer transport strip if it remains the better treatment;
- make seek actually work;
- default existing/unspecified volume presentation to the separate child item;
- allow an integrated volume form only as an explicit extra option rather than replacing the established toggle outcome;
- reuse the existing Media presentation model plus its one `MediaVolumeRuntimeService` lease/action seam in both forms; the retained child presentation may hide/retire with Media but must not own or duplicate that shared runtime, and must not recreate the historical QWidget.

### Gmail / Reddit

Floor:

- rows remain inside cards;
- compact readable density;
- coherent shared header language;
- refresh behavior/treatment consistent where semantics match;
- working URL actions.

Plus:

- preserve a current treatment over the Ideal oracle only when the operator explicitly identifies it as better. At present the named Media exception is the transport/control bar only.

### Steam cards / Achievement Pulse

Floor:

- no unnecessary dead area;
- artwork/icon belongs to content hierarchy;
- available width is used before truncation.

Plus:

- preserve newer semantic/features while improving packing.

### Visualizer

Floor:

- all five modes recognizably preserve their intended visual family and response;
- correct ordinary/CUSTOM routing;
- no geometry distortion;
- no gross topology substitutions.

Plus:

- use Quick's retained scene/pacing to improve smoothness and polish without retuning away authored behavior.

### Ordinary layout

Floor:

- no unreadable dog-pile;
- Media + Visualizer honor their established ordinary free-space relationship where room exists;
- CUSTOM user geometry wins and may intentionally overlap/cross displays;
- Edit mode restores the **missing visible alignment/snap guide lines** when relationships are available (centre/peer/edge/safe-gutter). This is mandatory J interaction parity, ideally worked early with the visual oracle. Current Quick already contains guide presentation seams; reconnect the existing Python snap/layout authority rather than restoring old layout code or inventing QML geometry truth.

Low-priority diagnostic parity:

- preserve the remembered performance/debug overlay affordance as later Quick-native read-only observability work; no legacy GL profiler/presenter resurrection.

Plus:

- improve placement determinism and mixed-DPR robustness without surprising the user.

### Observability

Parity+ is not pixel-only. A physically good-looking run with unexplained Qt/QML diagnostics is not a clean final acceptance. Inspect `screensaver_qml.log` beside the ordinary log for every relevant J run.

## 7. How to use historical source safely

When a J cell is unclear:

1. for a covered ordinary family, inspect the paired `Ideal (PreMigration)` / `Current (PostMigration)` image first;
2. use release screenshots only for broader composition/relationships the paired crop does not show;
3. inspect `15099d3` for the old behavior/value/layout rule if needed;
4. for visualizer reactivity, compare directly against the known-good `3fe5df6` tree; for unrelated UI archaeology, use whichever historical source best exposes the successful behavior;
5. write down the **user-visible invariant** in neutral language;
6. implement that invariant through current Quick owners;
7. compare physical output against the reference;
8. preserve any current treatment explicitly accepted as better.

Do not copy old classes wholesale and “port them later.”

## 8. Interaction-contract survival sweep

Before J closes, perform one bounded inventory of explicit historical user gestures/affordances against the retained Quick interaction surface: mouse buttons, wheel/resize semantics, double-click actions, context actions, edit guides and diagnostic affordances. This is a **detection guardrail**, not permission to turn every historical mechanism into current architecture. If a valuable deterministic product action is missing, promote it to the smallest owning correction (as H8 does for middle-click preset cycling); if only its presentation/feel is deficient, keep it in J. Obsolete presenter mechanisms remain obsolete.

## 9. J close condition

J is not complete when the program is merely functional or when each card has been independently prettified.

J closes when:

- every unresolved J ledger row has been physically reviewed;
- the application reaches at least the proven historical visual/interaction floor where that floor was better;
- intentional Quick improvements remain;
- no historical bug is restored merely for fidelity;
- multi-widget composition, mixed display conditions and interactions are coherent as one product;
- remaining differences from historical screenshots are either deliberate improvements or setting/data-driven differences, not migration accidents.

## 10. Committed non-blocking J+ work — ordinary-widget Glass / Acrylic cards

**Committed J+ work, non-blocking for J close.** This is not migration parity and is not required to close J, but it must remain tracked until implemented/accepted or explicitly superseded. Schedule it after the mandatory parity/fidelity/installed acceptance rows are under control, and keep the Normal card path untouched by default.

Canonical architecture/deeper design: `Future_Work.md`, section **10. Ordinary-widget card materials — committed Normal / Glass / Acrylic modes**. That section owns the shared/lazy backdrop design; J must not invent a second implementation.

### Product contract

- [ ] Add one mutually-exclusive `Settings -> Widgets -> General -> Appearance -> Surface Style` choice: **Theme Default / Normal / Glass / Acrylic**.
- [ ] `Theme Default` is the default/no-override state. It follows the selected Widget Theme's `default_card_material_mode`; the existing/Dark Widget Theme recommends **Normal**.
- [ ] Normal means the current cheap translucent `OverlayCard` path and creates **no** blur/capture/offscreen material resources.
- [ ] An explicit Normal/Glass/Acrylic selection overrides **material only** while preserving the selected Widget Theme's colours. Do not require a fake Custom theme, hide swatches, or add a second `Override Theme Background` checkbox.
- [ ] Never expose independent Glass/Acrylic booleans; simultaneous material states must be impossible.
- [ ] Widget Themes (`.srwtheme`) serialize a recommended/default material, not a competing final material owner. Persist the user override separately and resolve one `effective_card_material_mode` for runtime consumers.
- [ ] `Keep Synced` links Settings Theme <-> mirrored Widget Theme identity but never clears an explicit Surface Style override; sync OFF permits independent theme pairings under the same material-resolution rule.
- [ ] Manual edit of any Widget Theme-owned swatch/border/shadow/other visual value silently snapshots the full currently resolved named theme into user-owned **Custom**, applies the edit there, selects Custom, and turns Keep Synced OFF. The source `.srwtheme` stays immutable; unedited colours/settings remain exactly as resolved from the previous named theme.
- [ ] Persist `Custom` in normal SRPSS Settings data, not as `themes/widgets/Custom.srwtheme`; ordinary runtime customization must not require ProgramData write access. Creating a real reusable `.srwtheme` is an explicit save/export/authoring action.
- [ ] Do not build per-property theme override inheritance. `Custom` is the single user-owned working snapshot. Re-enabling Keep Synced may reselect the paired named Widget Theme but must not destroy the Custom snapshot.
- [ ] Surface Style is explicitly excluded from the Custom/unsync trigger: Theme Default/Normal/Glass/Acrylic changes material ownership only.
- [ ] Theme discovery uses one durable root: installed/frozen `.srtheme` files under `%ProgramData%\SRPSS\themes` and `.srwtheme` files under `%ProgramData%\SRPSS\themes\widgets`; source/dev mirrors this as `<repo>\themes` + `<repo>\themes\widgets`. Do not flatten both theme types into one directory or merge ProgramData/repo catalogues simultaneously. ProgramData files are read-mostly catalogue assets; automatic Custom persistence remains in Settings.
- [ ] Runtime Context Menu follows the selected Widget Theme palette + the same effective material resolution; do not create a second menu-only material owner by default.
- [ ] Widget activation, provider/account state, geometry, cadence and business logic remain completely outside material/theme ownership.

### Architecture admission checklist

- [ ] Reuse the single retained `QQuickWindow`; never create a native backdrop HWND or one accelerated window per card.
- [ ] Treat the accepted Settings Glass/Acrylic work as **semantic evidence only**. Do **not** port `SetWindowCompositionAttribute`, AccentPolicy or HWND backdrop mechanisms into Quick widget cards.
- [ ] Build at most **one lazy shared backdrop/blur source per display** (or a very small measured set of shared blur tiers), activated only while at least one Glass/Acrylic card is visible.
- [ ] Source the material from the scene below ordinary widgets only. Never recursively capture cards, Visualizer, CUSTOM overlay, Halo or context menus.
- [ ] Keep blur/capture/material work render-thread/GPU native. No Python pixel loops, screenshots, `QPixmap` bridges, CPU blur or per-tick Python material updates.
- [ ] Prefer a deliberately downsampled shared backdrop and cheap card-local crop/mask/tint. Never create one `ShaderEffectSource`, FBO, blur chain or scene capture per card.
- [ ] Card-local Glass/Acrylic differences should mostly be cheap parameters: tint/opacity/border plus, for Acrylic only, restrained noise/luminosity if it visibly earns its cost.
- [ ] When the last material consumer disappears, retire the shared backdrop resources and return fully to Normal-path cost.

### Temporal / geometry correctness checklist

- [ ] Material samples use the **same current background/transition frame state** as the display behind the card; no one-frame lag or independent transition clock.
- [ ] Resolve crop UVs from final display-space geometry, including current CUSTOM position/resize/pixel-shift transforms and mixed DPR.
- [ ] Rounded clipping/masking stays card-local; the shared per-display backdrop remains geometry-neutral.
- [ ] Background dimming and material sampling remain visually coherent without forcing a second full-scene capture.

### Performance acceptance checklist

- [ ] Follow `Docs/Guardrails/Performance_Optimization_Contract.md`; reactivity/freshness and R-69 remain sacred.
- [ ] Normal mode shows no measurable new steady-state capture/blur cadence, GPU owner or allocation stream when no material card is active.
- [ ] Glass/Acrylic do not introduce a Python timer, polling loop, per-frame settings propagation or per-card offscreen owner.
- [ ] Measure 1 / several / many material cards at representative 1440p/4K and mixed-DPR displays; adding another card should mostly add cheap crop/mask/tint work, not another full blur pipeline.
- [ ] Exercise image transitions while material cards are visible and reject any backdrop lag, swimming, seam, black flash or stale crop.
- [ ] Re-run modest-load and representative-heavy acceptance. A prettier material is rejected if it worsens Visualizer freshness/reactivity, transition continuity, R-63 `black=0`, or creates sustained resource pressure.

### Recommended implementation order

1. [ ] Land Widget Theme identity/linking plus the three-layer surface schema first: `.srwtheme.default_card_material_mode`, persisted `card_material_override`, and resolved `effective_card_material_mode`. Expose **Theme Default / Normal / Glass / Acrylic**, with only Theme Default->Normal/Normal effectively available until material rendering is admitted. Prove persistence, Keep Synced behavior, the named-theme -> Custom snapshot + automatic unsync transition for theme-owned manual edits, Custom preservation when switching/relinking, and Surface Style override survival across theme changes without adding render cost.
2. [ ] Prototype one shared per-display reduced-resolution Quick backdrop source + bounded blur, consumed by one test card.
3. [ ] Prove temporal/geometry correctness during transitions and CUSTOM movement/resize before widening family coverage.
4. [ ] Add Glass card-local recipe; measure.
5. [ ] Add Acrylic as the same shared backdrop plus stronger cheap local treatment; measure again.
6. [ ] Only if the simple Quick capture/effect route is demonstrably too expensive, consider producing the shared material backdrop beside `BackgroundRenderNode` from the same frame state. Do not lower-level-optimize pre-emptively.
7. [ ] After physical/performance acceptance, enable Glass/Acrylic as selectable explicit overrides and as valid Widget Theme defaults through the same resolver. Do not add a parallel theme-material path.

If this committed slice is scheduled after J close, leave the resolved runtime material effectively `normal` and the current card architecture alone until implementation begins. The live plan and Future Work retain the requirement; there is no reason to partially land blur ownership merely because the future schema/UI exists.


# J Parity+ — Historical Visual / Interaction Reference

Date: 2026-08-30  
Applies to: Phase J final physical/visual acceptance and any earlier H defect whose *functional presentation topology* must be identified before J polish.

## 1. Purpose

Phase J is **Parity+**, not a vague “make it look roughly like before” pass.

The target is:

> Recover at least the proven user-visible quality, density, geometry, clipping, feature availability, interaction behavior and design language of the successful pre-Quick application where those outcomes were better, **while preserving genuine Quick-era improvements and deliberately improving weak legacy outcomes where safe**.

Parity is the floor. The `+` matters.

This is **not** bug-for-bug compatibility and it is **not** implementation compatibility.

Examples:

- the newer Media transport strip may be kept because the operator prefers it;
- the old 4.7.2 seek bar is useful as a visual/interaction reference even though the release notes explicitly say clicking it did not seek yet — H4 should make seeking actually work rather than reproducing that limitation;
- the app-volume control remains a Media-dependent child widget; the historical separate adjacent accessory is the default outcome for the existing toggle, while an integrated in-card variant may survive only as an explicit additional option;
- old Spectrum/Organ presentation is a topology/design oracle, but current H must also provide correct dynamic data before J tunes glow/spacing/colour.

## 2. Reference hierarchy

Use references in this order for **user-visible outcomes**:

### 2.1 Current explicit operator observations

The operator's current physical observations and comparison screenshots outrank historical inference. If the operator explicitly says a newer Quick treatment is better, preserve it unless it conflicts with a surviving product contract.

### 2.2 Release screenshots — strongest broad visual oracle

The GitHub Releases screenshots are the preferred whole-screen/widget-composition visual reference.

Primary:

- Release 4.7.2: <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/releases/tag/4.7.2>
- Embedded release screenshot: <https://github.com/user-attachments/assets/76cb21ce-d228-49bb-a397-9a0a47a0ee06>

The 4.7.2 release explicitly identifies itself as the **last version on the Raw PySide6 architecture** before the major Qt Quick migration. It is therefore an especially useful visual baseline without granting its implementation any authority.

Secondary:

- Release 4.7.0: <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/releases/tag/4.7.0>
- Embedded release screenshot: <https://github.com/user-attachments/assets/82e1fd3e-99b7-4c96-8536-580f4cdef463>

The release screenshots are also useful because they show the application under heavy/many-widget presentation rather than one isolated card.

### 2.3 Historical source snapshots — behavior/reference archaeology only

Cleaner old-code reference:

- `15099d389e5091942a0ce3d6e6311d33b6043d3d`
- <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/commit/15099d389e5091942a0ce3d6e6311d33b6043d3d>

Later reference:

- `3fe5df687387b6b6a121142372c43a7719442386`
- <https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/commit/3fe5df687387b6b6a121142372c43a7719442386>

For broad UI/presentation archaeology, `15099d3` can still be the cleaner old architecture snapshot. **For visualizer reactivity, however, the user-supplied `3fe5df6` source tree is explicitly the known-good pre-Qt-Quick behavioral oracle** and should be compared line-by-line against current logical/configuration/presentation semantics. It remains a behavior oracle only, never an architecture to restore.

### 2.4 Current architecture and contracts

For **implementation**, current accepted Quick architecture always wins over every historical reference.

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

## 4. H versus J under Parity+

Parity+ does not make H a visual-polish phase.

### H owns broken functional presentation contracts

Examples:

- Media artwork provider identity is now functionally closed in H2; J must preserve that while restoring better artwork scale/chrome/fade;
- Reddit opener composition has a prepared H repair but remains awaiting MC/SCR validation;
- Media Play/Pause/seek do not execute;
- CUSTOM Visualizer refuses its own committed display;
- Spectrum receives saturated data and/or renders the **wrong fundamental presentation topology**;
- CUSTOM Settings disables controls it does not own;
- shutdown crashes.

For Spectrum specifically, H ends when the selected Spectrum preset is recognizably the correct functional representation and is driven by non-degenerate live frequency data. It does not need screenshot-perfect glow/spacing before H closes.

### J owns Parity+ physical quality

Examples:

- card proportions/density;
- artwork size and chrome balance;
- clipping/elision;
- border/radius/header alignment;
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

Therefore H5 must investigate **both**:

```text
data correctness:
FFT/bands -> Spectrum shaping -> normalization/gain/floor/expansion -> final bar vector

presentation identity/topology:
mode/preset -> render snapshot -> renderer implementation -> primitive/segment topology -> retained draw
```

Saturation may explain uniform height/energy. It does **not** by itself explain why a continuous-column Spectrum became a dense segmented-cell matrix.

H acceptance for Spectrum:

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

- choose the cleaner current treatment where one family demonstrably improved.

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
- Edit mode exposes useful alignment/snap guides when relationships are actually available. Current Quick already contains guide presentation seams; this is an outcome to reconnect, not a reason to restore old layout code.

Low-priority diagnostic parity:

- preserve the remembered performance/debug overlay affordance as later Quick-native read-only observability work; no legacy GL profiler/presenter resurrection.

Plus:

- improve placement determinism and mixed-DPR robustness without surprising the user.

### Observability

Parity+ is not pixel-only. A physically good-looking run with unexplained Qt/QML diagnostics is not a clean final acceptance. Inspect `screensaver_qml.log` beside the ordinary log for every relevant J run.

## 7. How to use historical source safely

When a J cell is unclear:

1. inspect the release screenshot first;
2. inspect `15099d3` for the old behavior/value/layout rule if needed;
3. for visualizer reactivity, compare directly against the known-good `3fe5df6` tree; for unrelated UI archaeology, use whichever historical source best exposes the successful behavior;
4. write down the **user-visible invariant** in neutral language;
5. implement that invariant through current Quick owners;
6. compare physical output against the reference;
7. preserve any current treatment explicitly accepted as better.

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

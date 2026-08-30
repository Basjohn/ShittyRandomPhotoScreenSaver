# Black Flash / First-Visible-Frame Surface Continuity Decomposition

Date: 2026-08-30 (superseded in part 2026-08-31)

> **STATUS 2026-08-31 (2) — RECURRING FLASH SOLVED.** PresentMon proved the
> root cause: the exact-cover borderless window is non-deterministically promoted
> to hardware fullscreen-flip, and the composition <-> `Hardware: Legacy Flip`
> PresentMode transitions present the black/stale frames on the LG/Display-1
> output. Fix: `QuickDisplayWindow._fullscreen_compat_geometry` applies a 1px
> coverage-preserving overscan so the window is non-exact-cover and stays in
> stable `Composed: Copy with GPU GDI` (6/6 launches black=0, operator-confirmed).
> The tearing/flip language below is a superseded hypothesis; the measured seam is
> the *mode transition*, not composed-vs-flip per se. A minor startup-only flash
> may remain (separate seam). See Current_Plan.md.
>
> **STATUS 2026-08-31 — two repairs in §4 FAILED and were REMOVED.**
> The §4.1 deferred first-show (`prepare_on_screen`/`commit_prepared_show`) made
> startup visibly worse (image -> black -> image); reverted to immediate
> `show_on_screen()`. The §4.2 event-driven surface-refresh redraw on
> activation/menu did not improve the flash; removed (with
> `request_surface_refresh` and `background_surface_refresh_requested`).
> **Kept:** §2 proof-band removal, `[QUICK_SURFACE]` passive telemetry, and the
> `intentional_base_frame_ready` readiness semantics.
> **New binding evidence:** a single-window MC A/B (LG-only -> flash, MSI-only ->
> clean, LG-only -> flash) shows the flash follows the **LG/Display-1 output**
> (60 Hz TV, DPR 1.5, 3840x2160) even as the sole window — so §3.2/§3.3's
> two-window/activation framing is not the root cause. Presentation mode is NOT
> proven (tearing alone is not proof); measure with PresentMon/ETW. The prior
> "independent flip vs DWM composition" language below is a hypothesis, not a
> verdict. See Current_Plan.md "Interleaved black-flash" for the live plan and
> the failed-approaches checklist.

This is a high-priority J / H-conditional decomposition. The physical trace has now separated the former generic “black flash” report into distinct owners instead of treating it as visual polish by default.

## 1. Product requirement

A selected display must not expose a migration proof frame, an unexplained black native clear, a stale desktop/wallpaper/back-buffer frame, or a whole-scene reset during normal startup/focus/context/transition operation.

The accepted Quick architecture remains one standalone `QQuickWindow` and one retained scene per selected display. Do not solve flashes by adding another cover window/surface or by restoring the deleted presenter.

## 2. First deterministic defect already repaired: migration proof fallback

`rendering/quick/render/background_node.py` contains the old deterministic Slide proof palette used during migration bring-up. Production previously instantiated that render node when no real image existed, so `uHasImage == false` could physically display the coloured proof bands.

`BackgroundRenderItem` now keeps proof rendering explicit-opt-in only. A no-image/no-transition product state produces no proof node, while harnesses can still call `setProofProgress()`.

Quick first-frame readiness also requires a rendered real active image identity; an empty/proof render cannot satisfy `intentional_base_frame_ready`.

## 3. Physical trace after the proof repair

The new `[QUICK_SURFACE]` telemetry gives three important results.

### 3.1 Startup black flash

A display window can become visible before its first real `PresentationImage` has published/rendered. The later display in staggered dual-display startup is especially exposed to this interval. With the colour proof gone, the QQuickWindow native black clear is visible instead.

This is deterministic startup ordering, not cosmetic J tuning.

### 3.2 A -> B -> A click/focus flash

The recurring display-switch flash aligns with `window_active_changed`. During those events the trace keeps:

```text
visible=True
exposed=True
scene graph initialized
active image identity unchanged
transition unchanged/absent
```

No image replacement, scene-graph invalidation, QML error or logical transition accompanies the flash. The semantic retained scene is therefore exonerated for this class. The current owner is native/window presentation continuity around activation.

### 3.3 First context-menu open on each display

The first menu open on a display can produce two rapid flashes; a second open on the same display is physically clean, while the first open on another display can reproduce the issue. The trace still shows the same retained image identity and initialized scene graph throughout.

An observed glimpse of an old wallpaper/image during this flash is especially important: there is no corresponding `presentation_image_published` event. Treat it as stale/native/back-buffer exposure, not as the image-selection engine choosing an old image.

The first-open-only shape may still indicate first-visible context-menu QSG resource/material preparation. Do not jump to menu prewarming until one retained-background continuity repair is physically tested.

## 4. Current bounded repair

### 4.1 Gate first native show on a real retained image

Window placement/intent and native exposure are now split:

```text
show_on_screen request
-> prepare exact QScreen + geometry
-> mark desired-visible
-> if retained PresentationImage already exists: show now
-> otherwise remain hidden
-> first real PresentationImage publication
-> commit prepared native show
```

This preserves the image pipeline's target geometry before processing but prevents an empty QQuickWindow clear from becoming the first physical frame.

Important: display-manager “startup ready” remains a setup/image-replay admission seam, not proof that the native window has already become visible. That avoids a startup deadlock: the engine may process/replay the image while the window is armed but hidden.

### 4.2 Reassert the retained background at native/same-scene boundaries

Activation changes and context-menu visibility changes now request exactly one retained background refresh:

```text
window activation/deactivation OR context-menu visible/hidden
-> BackgroundRenderItem.update()
-> QQuickWindow.update()
-> redraw the same retained PresentationImage in the next frame
```

This changes no semantic image state and owns no timer, queue, render surface or cadence. It is an event-driven attempt to stop native/first-composition frames from depending on stale back-buffer contents.

New telemetry event:

```text
[QUICK_SURFACE] ... event=background_surface_refresh_requested ... reason=...
```

## 5. Physical decision tree after this repair

Exercise:

```text
cold dual-display startup
A -> B -> A clicks several times
first context-menu open on A
second context-menu open on A
first context-menu open on B
Settings recreation
CUSTOM Save/Continue recreation
ordinary transition
```

### A. Startup black flash disappears

Keep the deferred-show contract permanently. It proves the empty-native-clear owner was correctly localized.

### B. Startup still flashes but first visible event has a real image

Inspect the exact order of `presentation_image_published`, `window_visible_changed`, `scene_graph_initialized`, and frame swaps. If the first real image is present before show but the first physical swap still clears black, the remaining startup issue moves to native first-frame continuity rather than image admission.

### C. Click/focus flash improves/disappears

Keep the event-driven background reassertion. Do not add periodic repainting.

### D. Click/focus flash remains with `background_surface_refresh_requested` and stable scene/image

The bounded redraw is insufficient. Investigate native `QQuickWindow`/Windows activation-buffer behavior next: window role/flags, persistence/exposure policy, and composition continuity. Do not modify image state to chase it.

### E. First-menu flash remains but focus improves

The first-visible menu resource path becomes the primary suspect. Investigate/prewarm only the retained menu's own first-visible QSG resources while keeping it same-scene.

### F. Old wallpaper/image is visible again with no image-publication event

Treat that as strong native/back-buffer evidence. The image pipeline remains exonerated.

## 6. Explicitly forbidden fixes

Do not use:

- an extra cover window;
- a second accelerated surface;
- QWidget/QRhi/GL presenter resurrection;
- black clears intended to hide black flashes;
- arbitrary startup/focus sleeps;
- `processEvents()` pumping;
- periodic repaint/update loops;
- destroying/recreating the retained scene for context-menu interaction;
- changing image identity on activation/menu events;
- lowering visualizer cadence as a workaround.

## 7. Focused regression

`tests/test_qtquick_black_flash_contract.py` now pins:

1. migration proof rendering is opt-in;
2. an empty/proof render is not a product first frame;
3. runtime show requests remain physically deferred while no real retained image exists;
4. first real image publication commits an armed hidden show;
5. a surface boundary requests one retained background refresh/window update rather than a recurring repaint owner.

The test requires PySide6 and remains **AWAITING TEST VALIDATION** in the real development environment.

## 8. Acceptance split

### Deterministic acceptance

- no migration proof frame;
- no native startup exposure before a real retained image is available;
- activation/menu continuity uses only event-driven retained redraw;
- no duplicate presentation owner/surface/cadence.

### J Parity+ acceptance

- no recurring black flash on focus/context-menu/transition edges;
- no stale wallpaper/back-buffer glimpse;
- first menu open is as stable as later opens;
- startup reveal remains intentional and coordinated;
- no visual workaround weakens Bubble/Visualizer cadence.

# Remaining G7 / G8 — Auxiliary, Input and Focus Closure Technical Decomposition

Status: **execute after the current bounded G4 audit-correction batch is GREEN; then close G7 + G8 continuously**  
Source basis: inspect exact current tree before each slice; owner names below are current routing, not a frozen commit snapshot.  
Work admission: `Current_Plan.md`

This document describes how to finish the already-selected architecture. It is not permission to redesign input, create a
new focus subsystem or port historical QWidget fixes mechanically into Quick.

## 0. Entry and audit boundary

Do not enter this decomposition until `G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` is GREEN. Once admitted, G7
and G8 are one continuous remaining-G closure sequence. Do **not** stop merely to request an independent audit after a
GREEN G7 slice or between bounded G8 fixes. Use focused tests + post-push self-audit and continue while the next task is
known and GREEN.

After G4 corrections + G7 + G8 are all GREEN, push/checkpoint the complete G state, reconcile immediate G status docs, then
**stop once for independent audit before H**. Real RED/unresolved YELLOW evidence, a missing product decision or a hard
destination-invariant conflict still stops early.

## 1. Current destination wiring

The important current path is:

```text
QuickDisplayWindow
    -> QuickInputController / RuntimeInputOwner
        -> generation-scoped QuickInputState
            -> QuickAuxiliaryController
                -> halo visibility / auxiliary state
            -> QuickSceneController / ordinary-widget host

QuickDisplayWindow.pointer_position_changed
    -> QuickAuxiliaryController.update_halo_pointer

QuickContextMenuModel.visibilityChanged
    -> QuickInputController.set_context_menu_active
        -> QuickInputState
            -> halo/input suppression

QuickAuxiliaryController.state_changed
    -> QuickSceneController.apply_auxiliary_state
        -> same DisplayScene root
            dimming
            pixel shift
            halo

QuickContextMenuModel
    -> same DisplayScene root ContextMenu.qml
    -> semantic action handler in Python
```

This is the architecture to close. Do not add a second menu window, top-level halo, QWidget auxiliary presenter or family
keyboard router.

## 2. G7 is closure, not another feature phase

Already landed:

- retained same-scene dimming;
- one shared retained pixel-shift transform/cadence owner;
- retained same-scene cursor halo with inactivity behavior;
- retained context-menu model/QML;
- context-menu visibility feeding generation-scoped input state;
- semantic action admission in Python.

G7 remaining work is caller proof and deletion/rerouting of old presentation owners.

Likely legacy surfaces to inspect include current callers of:

- `widgets/context_menu.py`;
- `rendering/display_context_menu.py`;
- `widgets/cursor_halo.py`;
- old pixel-shift manager/presenter code;
- `DisplayWidget` dimming/halo/context helper methods;
- old focus/Z-order helpers whose only purpose was separate QWidget auxiliary windows.

Do not delete by filename. Classify each live callable first:

```text
presentation pixel / QWidget-window ownership
    -> retire when caller-dead

semantic command / settings / neutral policy still required
    -> route into existing Quick controller/model seam, then retire old pixel owner

historical compatibility with no destination caller
    -> delete, do not port
```

## 3. G7 per-feature invariants

### Dimming

- one retained scene layer;
- opacity/enable state comes from Python-owned accepted settings/runtime state;
- no family-specific dimming windows;
- no fade/lifecycle authority hidden in QML;
- edit-mode temporary dimming must restore through the existing CUSTOM/session semantics, not a second setting.

### Pixel shift

- one shared scene transform, not per-family positional mutation;
- current bounded cadence remains owned by `QuickAuxiliaryController`;
- transition defer remains an explicit runtime fact; do not shift content mid-transition merely because a timer fired;
- disabling resets the offset coherently;
- no second timer in QML or individual family items.

### Cursor halo

- same retained scene, never a top-level translucent window;
- pointer position comes from the owning `QuickDisplayWindow`;
- visibility is derived from current generation input state + inactivity + suppression;
- context-menu active, exiting, closed admission or inactive interaction/Ctrl state hides it;
- a stale display/generation update is rejected rather than repainting a replacement runtime.

### Context menu

- `QuickContextMenuModel` owns display/generation-scoped menu presentation state;
- Python builds admitted entries from canonical current state;
- QML renders rows/submenus and emits semantic requests only;
- QML never writes Settings or invokes providers/controllers directly;
- menu visibility must set/clear `context_menu_active` exactly, including dismiss, hide, retirement and action-triggered close;
- opening/closing a menu must not recreate the display scene or any family presentation.

## 4. G7 deletion rule

Do not keep both old and retained implementations because normal startup still uses `DisplayWidget` before H. The project
explicitly does not require the half-migrated old product to remain functional.

Once a legacy auxiliary pixel owner has no required migration caller, remove it now. If deletion would remove a neutral
command/settings rule still needed by Quick, move/reuse that rule first; do not preserve the pixel object as a convenient
policy container.

G7 closes when destination presentation is sole admitted auxiliary/context pixel architecture and the remaining old source
is either required physical-host scaffolding for H or genuinely caller-dead deletion debt explicitly owned elsewhere.

## 5. G8 objective

G8 is not "make focus complicated." It proves that the retained single-window/input model behaves correctly across the
interaction combinations that historically broke SRPSS.

Core contract:

```text
one physical display
-> one QuickDisplayWindow keyboard/pointer ingress owner
-> one QuickInputController generation
-> retained QML hit regions emit semantic actions
-> no child/top-level auxiliary presentation becomes an alternate keyboard owner
```

Cross-display Ctrl/interaction state may be coordinated globally where product semantics require it, but there must not be
multiple independent truths that can become stuck after focus moves.

## 6. MC window contract

Preserve the product surface:

- no normal taskbar entry;
- no normal Alt-Tab entry;
- topmost / no falling behind according to the selected MC policy;
- retain the intended `QuickWindowRole`/native role semantics rather than changing to a normal window to make focus easy.

Historical MC focus bugs are evidence, not a recipe. In the QWidget era, broad focus-policy mutation caused rapid focus
churn and shadow corruption, and top-level halo/focus workarounds had their own failures. Do **not** port those mechanisms
into Quick unless current Quick evidence proves an equivalent need.

In particular, do not:

- recursively toggle focus policy on the retained item tree;
- add focusIn/focusOut shadow invalidation;
- add a top-level halo to recover click routing;
- convert MC to a normal taskbar/Alt-Tab window;
- scatter per-family key handlers to compensate for a window/input-owner defect;
- spam `requestActivate()`/`forceActiveFocus()` after every click without a demonstrated focus-loss condition.

## 7. Focus and event ownership

`QuickDisplayWindow` is the native event owner. Interactive QML regions should consume only the pointer gestures they own
and emit semantic requests. They should not become hidden keyboard/focus owners merely because they are clickable.

Required behavioral rules:

- unhandled ordinary key policy stays in `RuntimeInputOwner`;
- family-specific double-click is admitted by retained hit testing before the global next-image fallback;
- context menu suppresses exit/halo behavior through `context_menu_active`, then releases that suppression on every close
  path;
- Ctrl press/release must not remain stuck because focus moved from display A to B;
- interaction mode and Ctrl state must agree between the active display, any global coordinator and published
  `QuickInputState`;
- runtime retirement closes input admission before scene/window teardown, so late keys/pointer/menu callbacks cannot target
  the replacement generation.

A focus change is not permission to rebuild shadows, families, context models or the scene.

## 8. G8 two-display matrix

Exercise A -> B -> A with at least these states:

```text
idle
Ctrl held
interaction mode
context menu open/dismiss
halo active then inactivity hide
family single-click
family double-click
Clock mode toggle
Media transport / seek / volume / mute
Gmail / Reddit action hit regions
CUSTOM edit active
CUSTOM X + Cancel
CUSTOM X + Save
layout slot save/load
cross-display CUSTOM drag
visualizer corner/wheel scale
visualizer edge viewport resize
Settings open / runtime hide-or-recreate path
runtime generation replacement
```

For each relevant row verify:

- intended semantic action fires once;
- global fallback does not also fire;
- no unexpected exit;
- Ctrl/interaction state is not stuck on either display;
- menu active state clears;
- halo does not remain visible/suppressed incorrectly;
- no presentation/model duplication;
- no extra accelerated/native auxiliary window;
- old-generation action is rejected after replacement.

## 9. Media/hardware key caution

Historical U-05 showed that synthetic/injected probes could pass while physical focused input still differed. Therefore:

- deterministic tests may prove routing/state ownership;
- script/runtime eyes-on may prove focus transitions;
- do not claim a physical hardware-ingress result from `SendInput` or synthetic Qt events alone.

G8 should close the architectural/focus state machine with the strongest available runtime evidence. Comprehensive installed
Winlogon/MC/hardware matrices still belong to J. If a physical-only acceptance cell cannot be run during G8, record it as J
acceptance debt rather than fabricating a pass; do not leave an unresolved deterministic focus/cardinality defect for J.

## 10. Recommended implementation/closure order

1. Audit G7 legacy auxiliary/context callers and classify pixel vs neutral semantics.
2. Reroute any still-needed neutral semantics into existing Quick/Python owners.
3. Delete caller-dead QWidget/top-level auxiliary pixel owners.
4. Strengthen generation/menu/halo close-path tests.
5. Build a focused two-display Quick input/focus harness around the real `QuickDisplayWindow`/`QuickInputController` path.
6. Exercise A -> B -> A and Ctrl/context/interaction state transitions.
7. Exercise retained family hit regions and global fallback exclusivity.
8. Exercise CUSTOM + cross-display + both visualizer resize operations under focus changes.
9. Exercise MC window policy without changing the product window role.
10. Only fix concrete failures at their owning seam; do not introduce a generic focus manager because a matrix cell failed.

## 11. Permanent tests to extend

Prefer extending destination tests:

- `tests/test_qtquick_auxiliary.py`
  - generation mismatch, menu suppression, pause/close, halo timeout, pixel-shift defer.
- `tests/test_qtquick_context_menu.py`
  - semantic admission, visibility close paths, generation identity, no QML settings ownership.
- `tests/test_qtquick_input_controller.py`
  - Ctrl/global state, context active, closed admission, fallback behavior.
- `tests/test_qtquick_runtime.py`
  - signal wiring and close order: input/menu/auxiliary close before scene/window retirement.
- retained ordinary-widget/family presentation tests
  - semantic hit regions do not duplicate global fallbacks.
- existing MC/input historical regression tests
  - keep product behavior, but update assertions away from QWidget-only implementation once Quick owns the path.

Do not create tests that require the deleted QWidget focus machinery merely because that is how the old bug was fixed.

## 12. GREEN definitions

### G7 GREEN

- retained Quick scene is the sole destination context/dimming/pixel-shift/halo presentation;
- Python remains semantic/settings authority;
- old auxiliary/context pixel owners are caller-dead/retired rather than dual-run;
- generation/menu/halo lifecycle is deterministic.

### G8 GREEN

- two-display focus/interaction state does not drift;
- MC product window policy is preserved;
- retained family actions and global fallbacks are exclusive/correct;
- menu/halo/Ctrl state survives A -> B -> A, CUSTOM, Settings/recreate and runtime replacement;
- no focus-driven shadow corruption or auxiliary/native-window regression is introduced.


## 13. G completion gate

G7/G8 GREEN is not permission to start H immediately. The complete G checkpoint includes the corrected G4 viewport contract,
G7 caller-proof auxiliary/context closure and G8 focus/MC closure. Once that complete checkpoint is pushed, stop for the
single independent G audit required by `Current_Plan.md`. H begins only after that audit is accepted.

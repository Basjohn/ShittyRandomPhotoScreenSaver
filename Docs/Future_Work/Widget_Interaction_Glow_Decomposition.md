# Widget interaction glow

Status: implementation pending. Live sequencing: `FWPlan.md`.
Pre-implementation comparison/rollback HEAD: `0fd64b3d002834614131b46581e41fe497d5cbc5`.

## Existing foundation and owning boundaries

- `core/settings/default_settings.py`, `core/settings/models/_core.py`: canonical defaults and InputSettings.
- `ui/tabs/display_tab.py`: existing Display -> Interaction builder and load/save transaction.
- `engine/display_manager.py`: Settings -> generation-local input/auxiliary projection.
- `rendering/quick/input_controller.py`, `state.py`: event-cached input admission, Ctrl, context-menu and retirement.
- `rendering/quick/scene_controller.py`: matching display/generation admission before ordinary-host projection.
- `rendering/quick/widgets/host.py`: retained creation/adoption, transfer, cached input-state projection and retirement.
- `rendering/quick/qml/OverlayWidget.qml`: shared ordinary-family shell, visual card bounds and uniform scale.
- `OverlayCardShadow.qml`: retained `RectangularShadow` precedent; no second render surface is required.
- `tests/test_qtquick_ordinary_widget_host.py`, `test_qtquick_input_controller.py`, `test_display_tab.py`:
  production-shaped host/input and Settings seams to extend or complement.

## Contract and ownership

Two independent booleans, `input.widget_glow_on_hover` and `input.widget_glow_on_click`, default false.
`input.widget_glow_color` is one shared RGBA colour, default `[130, 205, 255, 255]`. Settings owns persistence;
QML receives primitive resolved state only. No runtime Settings reads on pointer motion.

The existing input snapshot carries presentation configuration and admits feedback only while interaction/Ctrl
is active, admission is open, and exit/context-menu suppression is absent. Existing scene generation checks remain
authoritative. The host projects the shared properties for every ordinary family, including new/adopted/transferred
items; per-family semantic action admission remains unchanged.

One reusable retained QML primitive owns transient hover/press/pulse pixels. It observes pointer events passively,
never substitutes for or consumes a family action. Finite Qt Quick property animations may run only in response
to an actual state edge and must stop at rest. No Timer, worker, poller, independent frame request or perpetual loop.
Disabled/retired/hidden items cannot keep pulse work alive. The item uses current card geometry/radius/scale and
inherits whole-widget/startup fades. No artwork capture, extra window or per-frame CPU/GPU resource creation.

The primitive is **justified reusable presentation infrastructure** because all ordinary families consume it.
Glow colours and input options are **feature-local**; generalized animation managers, per-family glow controllers,
new style-theme roles and a Visualizer glow policy are **speculative reuse deferred**.

## Resumable checkpoints

- [x] Inspect source/ownership and commit this decomposition with the live FW plan.
- [ ] Add canonical InputSettings/defaults, the two Interaction controls and shared swatch; prove roundtrip/reload.
- [ ] Project configuration through existing input state and retained host; prove cold adoption, updates, transfer,
  rejection of stale generation and retirement.
- [ ] Implement shared retained pixels and finite passive hover/click feedback; prove actions still receive events.
- [ ] Run focused tests, inspect diff and commit/push the coherent vertical feature; reconcile current docs.

## Acceptance bars

- **Deterministic:** independent toggles and shared colour survive Settings reload; loading does not save defaults
  over existing choices; production input projection gates all ordinary roots, including cached/late-created items.
- **Lifecycle/resource:** no new engine/window/timer/worker; disabling/closing/retiring stops transient activity;
  cross-display adoption uses target input policy and retires with the existing item.
- **Performance:** disabled loader has no glow renderer; enabled idle/settled hover has no running animation;
  pointer motion within unchanged hover state does not request recurring Python work. Bound effect geometry to card.
- **Visual/operator:** verify subtle colour/edge quality on opaque and translucent cards, click pulse, hover decay,
  action passthrough, CUSTOM scale/transfer, 1/2 displays and mixed DPR. Automated QML proof does not close this bar.

# Widget Creation and Runtime Presentation Guide

Last updated: 2026-08-20

Canonical guide for adding or deeply refactoring a non-visualizer widget during the Qt Quick runtime
presentation migration.

## 1. Split the widget into two concerns

Every runtime widget should be understood as:

```text
data / provider / model / settings / interaction logic
                    +
runtime pixel presentation
```

The Qt Quick migration primarily changes the second concern.

Do not rewrite provider, persistence, authentication, refresh, or business logic into QML merely
because runtime pixels are moving to Quick.

## 2. Settings remain separate

Settings/configuration UI may remain QWidget-based.

Opening Settings must not:

- start runtime providers merely to hydrate controls;
- build every widget section;
- recreate live runtime;
- perform network work;
- trigger expensive pixel preparation for widgets the user did not open.

Preserve lazy settings construction and canonical SettingsManager/defaults ownership.

## 3. Runtime presentation destination

Runtime widget pixels that coexist over the screensaver scene should ultimately be presented inside
the display's single `QQuickWindow`.

Preferred shape:

```text
Python widget/provider/model
        ↓ compact presentation state
Quick runtime item/layer
        ↓
display scene
```

No separate accelerated native window per widget.

No `QQuickWidget` runtime workaround.

## 4. Migration compatibility

Existing QWidget runtime widgets may remain temporarily while their Quick presentation equivalent is
being built and validated.

Do not create permanent dual-presentation ownership.

A migration slice should have a clear handoff/cutover point after which only one presentation owner
draws that widget.

## 5. Widget classification

Classify:

1. static/mostly-static information card;
2. service-backed card;
3. interactive control;
4. anchor-dependent item;
5. CUSTOM-editable item;
6. special high-frequency visual element.

Use ordinary retained Quick items for ordinary UI where practical.

Use custom rendering only when fidelity/performance requires it.

## 6. Provider/model contract

Keep canonical Python owners for:

- refresh policy;
- credentials;
- network access;
- caching;
- error/fallback policy;
- normalized state;
- settings persistence.

Publish a compact presentation model/state rather than letting render code reach into provider
internals.

## 7. Runtime update contract

Prefer state-driven invalidation.

Do not:

- rebuild stable pixels every frame;
- add private high-frequency timers when the scene can retain state;
- perform blocking provider/file/cache work in render callbacks;
- emit one GUI/Quick update per source event when state can coalesce;
- repaint/rebuild a large card for a tiny decoration without measured justification.

## 8. CUSTOM layout

Committed CUSTOM geometry and authored/default geometry remain separate authorities.

The presentation item must consume authoritative geometry rather than invent a second layout system.

Live content refresh must not overwrite committed outer geometry.

Save and Cancel remain distinct lifecycle actions.

## 9. Input

Keep shared input semantics and business actions in existing Python routing where practical.

Quick presentation items may expose hit geometry/events, but do not duplicate the actual command,
URL, provider, or persistence authority in QML.

## 10. Styling

Preserve the authored SRPSS visual language.

Shared style/chrome constants should remain canonical rather than being copied into every QML/item
implementation.

If a migration requires new Quick-side style tokens, bridge them from the existing canonical source
or define one new canonical presentation-style source.

## 11. Performance

A new/migrated widget must not:

- introduce a second accelerated surface;
- block Quick render synchronization on provider work;
- allocate unbounded textures/images;
- force whole-scene rebuilds for small content changes;
- reduce animation fidelity to hit counters.

Measure p95/p99/max and shared presentation effects, not just widget-local paint time.

## 12. Lifecycle

Widget presentation state is generation-owned.

On recreation:

- old widget presentation loses admission;
- delayed/stale provider results cannot publish into replacement presentation;
- render resources are retired legally;
- replacement geometry/state becomes authoritative;
- reveal occurs only when intentional content is ready.

## 13. Testing

Test separately:

- model/provider behaviour;
- settings/defaults;
- presentation-state mapping;
- Quick item/render output;
- CUSTOM geometry;
- input routing;
- lifecycle/recreation;
- multi-display/DPR;
- installed visual parity.

Do not call a migration complete because the Python model tests still pass.

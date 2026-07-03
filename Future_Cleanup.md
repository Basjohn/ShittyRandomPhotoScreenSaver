# Future Cleanup

Last updated: 2026-07-03

## Priority Guidance

- Promote only when the item blocks active runtime-health work or has fresh log evidence.
- Remaining direct `QTimer.singleShot` sites are mostly UI-local polish/debounce helpers; promote only if fresh evidence ties one to lifecycle, widget startup, settings return, or runtime churn.
- Stale exported settings examples are documentation hygiene, not runtime risk; batch with a defaults/doc refresh rather than interrupting active lifecycle/perf work.
- Compatibility-shell cleanup should remain low priority unless it causes import/runtime ambiguity.

Low-priority cleanup items discovered during unrelated work. These are not active tasks unless promoted into `Current_Plan.md`.

## Backlog

- [ ] Reconcile likely-stale Media/Visualizers descriptor tests in [tests/test_widget_descriptors.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_widget_descriptors.py). Three expectations still assume older Media/Visualizers coupling: `media.loader_guard_attrs == ("media_enabled", "vis_enabled_checkbox")`, mutual lazy dependencies between `media` and `visualizers`, and programmatic Visualizers hydration materializing Media first. Current [rendering/widget_descriptors.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/widget_descriptors.py) has Media and Visualizers split more cleanly (`media` only guards on `media_enabled`; Visualizers depends programmatically on Defaults only). High likelihood: stale tests after intentional settings-section split. Before deleting/changing assertions, verify Media/Visualizers settings persistence, bucket state, scroll state, and runtime visualizer enablement still work when opening either section lazily.
- [ ] Decide whether `Docs/SRPSS_Settings_Screensaver.sst` and `Docs/SRPSS_Settings_Screensaver_MC.sst` are meant to be canonical examples or historical exports; regenerate or relabel them so stale defaults do not mislead future work.
- [ ] Classify and either track or retire the `Imgur` overlay-raise TODO in [widgets/imgur/widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/imgur/widget.py).
- [ ] Revisit [rendering/gl_compositor_pkg/__init__.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/__init__.py) and decide whether it should remain a clearly quarantined compatibility shell or be folded into a cleaner package-facing contract.
- [ ] Retire or quarantine [rendering/render_strategy.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/render_strategy.py). Current `rg` shows no live imports/callers, but the file still contains an old busy-wait timer loop and a separate update-queue helper; remove it only with a caller grep/bar so dynamic import assumptions do not regress.
- [ ] Classify and migrate remaining direct `QTimer.singleShot` sites only when they stop being UI-local. Current lower-priority examples include message-box auto-close, settings scroll/notices/about-image refresh, settings save debounce, system-tray tooltip refresh, Gmail auth/status delay, and tool/test-only helpers.
- [ ] Investigate `ImagePrefetcher._submit_load.<locals>._on_done` callback `IndexError: pop index out of range` if it recurs. Latest rotated perf run showed it once in `core.threading.manager` after an image load callback; fix the source callback directly rather than adding retries or broad exception masking.

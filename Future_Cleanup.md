# Future Cleanup

Last updated: 2026-06-22

Low-priority cleanup items discovered during unrelated work. These are not active tasks unless promoted into `Current_Plan.md`.

## Backlog

- [ ] Decide whether `Docs/SRPSS_Settings_Screensaver.sst` and `Docs/SRPSS_Settings_Screensaver_MC.sst` are meant to be canonical examples or historical exports; regenerate or relabel them so stale defaults do not mislead future work.
- [ ] Classify and either track or retire the `Imgur` overlay-raise TODO in [widgets/imgur/widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/imgur/widget.py).
- [ ] Revisit [rendering/gl_compositor_pkg/__init__.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/__init__.py) and decide whether it should remain a clearly quarantined compatibility shell or be folded into a cleaner package-facing contract.
- [ ] Replace or retire the two remaining production `processEvents()` seams that were not part of the active settings/display-rebuild perf fix: the unused synchronized-transition wait loop in [engine/display_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/engine/display_manager.py) and the Reddit exit URL-dismissal safety path in [engine/display_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/engine/display_manager.py). Any removal needs targeted bars because UI pressure is forbidden, but exit/browser routing must not regress.

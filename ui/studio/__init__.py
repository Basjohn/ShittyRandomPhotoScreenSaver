"""Reusable in-process Qt Quick authoring Studio (mode-neutral framework).

The framework owns the window shell, a typed edit session, the viewport host, the
preview transport and the Settings hide/restore lifecycle. A visualizer mode
contributes a :class:`ui.studio.adapter.StudioModeAdapter` (property schema,
deterministic evaluator, fixtures, scene objects and a render-thread renderer);
nothing in this package names a particular mode's geometry or sources.
"""

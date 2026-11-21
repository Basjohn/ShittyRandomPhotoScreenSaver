"""Sphere draws the scene fade once: its ``uFade`` is the content fade alone (R-NEW).

The render owner folds the scene opacity into the content fade (``render_contract.scene_faded_snapshot``), so Sphere
multiplying the presentation's ``scene_fade`` in again squared the fade of every reveal.
"""
from __future__ import annotations

from dataclasses import replace

import pytest


@pytest.mark.qt
def test_sphere_ufade_is_the_scene_faded_content_fade_not_squared(qt_app, monkeypatch):
    from rendering.quick.visualizer.implementations import sphere_voxel
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from rendering.quick.visualizer.render_contract import scene_faded_snapshot
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture

    scene = 0.5
    context = TransitionCapture(160, 90)
    host = QuickVisualizerRenderHost()
    seen: list[float] = []
    original = sphere_voxel.QuickSphereVoxelRenderer._packed_frame

    def spy(self, values, *, bind):
        seen.append(float(values["uFade"]))
        return original(self, values, bind=bind)

    monkeypatch.setattr(sphere_voxel.QuickSphereVoxelRenderer, "_packed_frame", spy)
    try:
        snapshot = _build_spectrum_preview_snapshot(width=160, height=90, mode="sphere")
        # The product's state mid-reveal: the authored scene fade on the presentation, and the same opacity handed
        # to the render owner, which folds it into the content fade.
        snapshot = replace(snapshot, presentation=replace(snapshot.presentation, scene_fade=scene))
        faded = scene_faded_snapshot(snapshot, scene)
        matrix = (2/160, 0, 0, 0, 0, -2/90, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
        host.render(snapshot=faded, viewport=(0, 0, 160, 90), logical_size=(160., 90.), matrix_values=matrix)
        assert seen, "Sphere drew no frame"
        expected = snapshot.presentation.content_fade * scene
        assert expected != pytest.approx(expected * scene)          # the control is distinguishable from the square
        assert seen[-1] == pytest.approx(expected)
        assert seen[-1] == pytest.approx(faded.presentation.content_fade)
    finally:
        host.release_resources()
        context.close()

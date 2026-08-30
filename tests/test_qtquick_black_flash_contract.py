"""Pins the first-visible-frame contract used to eliminate migration proof flashes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from rendering.quick.render.background_item import BackgroundRenderItem
from rendering.quick.render.background_node import BackgroundRenderNode
from rendering.quick.scene_controller import _render_snapshot_has_intentional_base_frame


@pytest.fixture(scope="module")
def gui_app():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


def test_migration_proof_background_is_opt_in(gui_app):
    owner = QObject()
    item = BackgroundRenderItem()
    item.setParent(owner)

    # A production no-image state must not create the colour-band proof node.
    assert item._proof_enabled is False
    assert item.updatePaintNode(None, None) is None

    # Harnesses can still request the deterministic proof explicitly.
    item.setProofProgress(0.5)
    node = item.updatePaintNode(None, None)
    assert item._proof_enabled is True
    assert isinstance(node, BackgroundRenderNode)


def test_empty_or_proof_render_is_not_product_first_frame():
    assert not _render_snapshot_has_intentional_base_frame(
        SimpleNamespace(render_count=1, active_image_identity=None, error=None)
    )
    assert not _render_snapshot_has_intentional_base_frame(
        SimpleNamespace(render_count=1, active_image_identity="image:a", error="boom")
    )
    assert _render_snapshot_has_intentional_base_frame(
        SimpleNamespace(render_count=1, active_image_identity="image:a", error=None)
    )


def test_runtime_defers_native_show_until_real_image_exists():
    from types import SimpleNamespace

    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.state import QuickRuntimePhase

    class _Controller:
        def __init__(self):
            self.calls = 0

        def resume(self):
            self.calls += 1

        def reset_initial_position(self):
            self.calls += 1

    class _Window:
        desired_visible = False

        def __init__(self):
            self.prepared = 0
            self.committed = 0
            self.visible = False

        def prepare_on_screen(self):
            self.prepared += 1
            self.desired_visible = True

        def commit_prepared_show(self):
            self.committed += 1
            return True

        def isVisible(self):
            return self.visible

    window = _Window()
    scene = SimpleNamespace(presentation_image=None)
    fake = SimpleNamespace(
        _phase=QuickRuntimePhase.CONSTRUCTED,
        _binding_loss=None,
        auxiliary_controller=_Controller(),
        input_controller=_Controller(),
        window=window,
        scene_controller=scene,
    )

    QuickDisplayRuntime.show_on_screen(fake)
    assert window.prepared == 1
    assert window.committed == 0, "an empty native surface must remain hidden"

    scene.presentation_image = object()
    QuickDisplayRuntime.show_on_screen(fake)
    assert window.prepared == 2
    assert window.committed == 1, "an already-primed retained scene may show immediately"


def test_first_image_publication_commits_an_armed_hidden_show():
    from types import SimpleNamespace

    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.state import QuickRuntimePhase

    class _Scene:
        def __init__(self):
            self.images = []

        def set_presentation_image(self, image):
            self.images.append(image)

    class _Window:
        desired_visible = True

        def __init__(self):
            self.committed = 0

        def isVisible(self):
            return False

        def commit_prepared_show(self):
            self.committed += 1
            return True

    scene = _Scene()
    window = _Window()
    fake = SimpleNamespace(
        _phase=QuickRuntimePhase.CONSTRUCTED,
        transition_controller=SimpleNamespace(is_active=False),
        scene_controller=scene,
        window=window,
    )
    image = object()

    QuickDisplayRuntime.set_presentation_image(fake, image)

    assert scene.images == [image]
    assert window.committed == 1


def test_surface_boundaries_request_one_retained_background_refresh():
    from types import SimpleNamespace

    from rendering.quick.scene_controller import QuickSceneController

    class _Background:
        def __init__(self):
            self.refreshes = 0

        def request_surface_refresh(self):
            self.refreshes += 1
            return True

    class _Window:
        def __init__(self):
            self.updates = 0

        def update(self):
            self.updates += 1

    background = _Background()
    window = _Window()
    traces = []
    fake = SimpleNamespace(
        _background_item=background,
        _readiness=SimpleNamespace(admission_open=True),
        _window=window,
        _trace_surface_event=lambda event, **kwargs: traces.append((event, kwargs)),
    )

    assert QuickSceneController._request_background_surface_continuity(
        fake, "window_active_changed"
    )
    assert background.refreshes == 1
    assert window.updates == 1
    assert traces[0][0] == "background_surface_refresh_requested"
    assert "window_active_changed" in traces[0][1]["detail"]

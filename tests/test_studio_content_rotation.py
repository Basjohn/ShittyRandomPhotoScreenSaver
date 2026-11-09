"""Studio turns cross the real QML/viewport/frame seam; hidden GL checks physical texel orientation."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPointF, QCoreApplication, QEvent, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtQuick import QQuickItem

from ui.studio.registry import create_adapter, studio_modes
from tests.test_studio_header_layout import Store
from tests.test_studio_preset_row_and_save_to_preset import (
    real_dialog, offscreen_launch, preset_copy, popups,
)


@pytest.fixture
def studio(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioBridge, StudioController
    from ui.studio.session import StudioEditSession
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()
    built = []

    def build(mode, *, real_renderer=False, size=(960, 600), prepare_calls=None):
        adapter = create_adapter(mode)
        real_factory = adapter.create_renderer
        draws = []

        def factory():
            renderer = real_factory()
            # Keep the production Studio wrapper and its resolved canonical frame. Only GL implementation
            # work is replaced for all-mode admission; separate real-pixel cases below exercise actual GL.
            if not real_renderer:
                def prepare(card, frame):
                    if prepare_calls is None:
                        return True
                    prepare_calls.append(card.content_rotation_quarters)
                    return not (card.content_rotation_quarters == 1 and prepare_calls.count(1) == 1)
                renderer.prepare = prepare
                renderer.render = lambda card, frame: draws.append(renderer._frame(card, frame))
            return renderer

        adapter.create_renderer = factory
        store = Store(mode)
        store.saves = []
        store.save_current = lambda: store.saves.append(deepcopy(store.values))
        store.save_camera = lambda values: store.saves.append(deepcopy(values))
        controller = StudioController(adapter, store, SimpleNamespace(), lambda c: None)
        controller.session = StudioEditSession(adapter.schema(), store)
        controller.evaluator = adapter.create_evaluator()
        controller.bridge = StudioBridge(controller)
        surface = OffscreenStudioSurface(controller, size=size, present_on_show=False)
        controller.surface, controller.viewport = surface, surface.viewport
        controller.framings = adapter.framings((460., 280.), {})
        controller.select_framing("card")
        # No worker/source jobs or clock needed: use a sentinel frame for the wrapper-only gate.
        if not real_renderer:
            surface.viewport.set_frame(SimpleNamespace())
        surface.pump(2)
        built.append((controller, surface))
        return controller, surface, draws

    yield build
    for controller, surface in reversed(built):
        surface.retire()
        controller.evaluator.release()
    qt_app.processEvents()


def named(surface, name):
    return surface.host.root.findChild(QQuickItem, name)


def click(surface, item):
    centre = item.mapToScene(QPointF(item.width() / 2., item.height() / 2.))
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        QCoreApplication.sendEvent(surface.window, QMouseEvent(kind, centre, centre, Qt.MouseButton.LeftButton,
                                  Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    QCoreApplication.processEvents()
    surface.pump()


@pytest.mark.parametrize("mode", [entry.mode_id for entry in studio_modes()])
def test_rotate_click_reaches_production_frame_without_changing_authoring(studio, mode):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from rendering.quick.scene3d.frame import orient_visualizer_scene_frame
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    from widgets.spotify_visualizer.presentation_orientation import logical_uv_from_physical_uv
    controller, surface, draws = studio(mode)
    button = named(surface, "rotateContentButton")
    capable = get_visualizer_presentation_policy(mode).content_rotation_capable
    assert button.isVisible() == capable
    assert capable == (mode != "sphere")
    before = deepcopy(controller.session.values), deepcopy(controller._pose)
    assert draws and isinstance(draws[-1], QuickVisualizerRenderFrame)
    # The view toolbar moves below input controls when they cannot fit side by side at native minimum.
    source = named(surface, "fixtureBox")
    view = named(surface, "viewToolbar").parentItem()
    source_rect = source.mapRectToScene(source.boundingRect())
    view_rect = view.mapRectToScene(view.boundingRect())
    assert not source_rect.intersects(view_rect)
    assert view_rect.left() >= 0 and view_rect.right() <= surface.size[0]
    if not capable:
        controller.bridge.rotateContent()
        assert controller.content_rotation_quarters == 0
        return
    physical = surface.viewport.width(), surface.viewport.height()
    extent = surface.viewport.extent
    for q in (1, 2, 3, 0):
        click(surface, button)
        assert controller.content_rotation_quarters == q
        frame = draws[-1]
        assert frame.content_rotation_quarters == q
        assert frame.snapshot.presentation.viewport_extent == extent
        size = physical[::-1] if q % 2 else physical
        assert frame.oriented_logical_size == size
        assert controller.presented_geometry()[:2] == (size, extent[::-1] if q % 2 else extent)
        # Scene3D's production dataclass replacement path must work too (the old namespace carrier failed).
        oriented = orient_visualizer_scene_frame(frame)
        assert oriented.logical_size == size
        assert oriented.snapshot.presentation.logical_viewport_extent == (extent[::-1] if q % 2 else extent)
        # Actual QML inverse item mapping used by handle drags and terrain picks agrees with the shared oracle.
        logical_uv = logical_uv_from_physical_uv((.21, .37), q)
        for name in ("handleLayer", "brushLayer"):
            layer, slot = named(surface, name), surface.host.slot
            point = layer.mapFromItem(slot, QPointF(slot.property("frameX") + physical[0] * .21,
                                                   slot.property("frameY") + physical[1] * .37))
            assert (point.x(), point.y()) == pytest.approx((logical_uv[0] * size[0], logical_uv[1] * size[1]))
        assert (controller.session.values, controller._pose) == before
        assert controller.session.commit_count == 0 and not controller.store.saves
    controller.bridge.rotateContent()
    controller.bridge.saveCurrent()
    if controller.capabilities.camera:
        controller.bridge.saveCamera()
    assert controller.store.saves and all(values == before[0] for values in controller.store.saves)
    assert controller.content_rotation_quarters == 1
    controller.last_frame = SimpleNamespace()
    controller.copy_frame()
    assert controller.viewport._snapshot_jobs[-1][-1] == 1


def test_turn_reenters_bounded_preparation_before_a_visible_turned_draw(studio):
    calls = []
    controller, surface, draws = studio("waveform_ribbon", prepare_calls=calls)
    assert calls == [0]
    click(surface, named(surface, "rotateContentButton"))
    assert calls == [0, 1]
    assert draws[-1].content_rotation_quarters == 0       # first turned prepare has not finished
    surface.pump()
    assert calls == [0, 1, 1] and draws[-1].content_rotation_quarters == 1
    surface.pump()
    assert calls == [0, 1, 1]                            # no repeated preparation at rest


def test_snapshot_turn_reenters_preparation_on_its_existing_renderer(studio):
    calls = []
    controller, surface, _ = studio("waveform_ribbon", prepare_calls=calls)
    images = []
    surface.viewport.snapshotReady.connect(lambda key, *_: images.append(key))
    frame = SimpleNamespace()
    surface.viewport.request_snapshot("first", frame, (32, 20), (32., 20.), (448., 280.))
    surface.pump()
    assert images == ["first"] and calls == [0, 0]
    surface.viewport.request_snapshot("turned", frame, (32, 20), (32., 20.), (448., 280.),
                                     content_rotation_quarters=1)
    surface.pump()
    assert images == ["first"] and calls == [0, 0, 1]
    surface.pump()
    assert images == ["first", "turned"] and calls == [0, 0, 1, 1]


def test_actual_projected_handle_labels_stay_upright_in_the_turned_layer(studio):
    controller, surface, _ = studio("waveform_ribbon")
    evaluator = controller.evaluator
    evaluator.select(controller.adapter.default_fixture(evaluator))
    for _ in range(100):
        controller.last_frame = evaluator.evaluate(2., controller.evaluation_values())
        if controller.last_frame.ready:
            break
    assert controller.last_frame.ready
    def labels_under(item):
        return [child for parent in item.childItems()
                for child in ([parent] if parent.objectName() == "sceneHandleLabel" else labels_under(parent))]
    for _ in range(3):
        controller.bridge.rotateContent()
        surface.pump()
        labels = labels_under(surface.host.root)
        assert labels, controller.bridge.handles
        for label in labels:
            origin, unit = label.mapToScene(QPointF(0., 0.)), label.mapToScene(QPointF(1., 0.))
            assert (unit.x() - origin.x(), unit.y() - origin.y()) == pytest.approx((1., 0.))


@pytest.mark.parametrize("mode", ("spectrum", "waveform_ribbon"))
def test_rotated_snapshot_is_the_production_logical_render_turned_at_native_extent(studio, mode):
    """Actual planar and Scene3D GL: non-square output, no resize of the rendered pixels."""
    controller, surface, _ = studio(mode, real_renderer=True)
    evaluator = controller.evaluator
    fixture = next(f for f in evaluator.fixtures() if f.kind == "reference")
    evaluator.select(fixture.id)
    frame = evaluator.evaluate(.2, controller.evaluation_values())
    controller.last_frame = frame
    surface.viewport.set_frame(frame)
    images, failures = {}, []
    surface.viewport.snapshotReady.connect(lambda key, w, h, data:
        images.update({key: np.frombuffer(data, np.uint8).reshape(h, w, 4).copy()}))
    surface.viewport.snapshotFailed.connect(lambda *args: failures.append(args))
    for key, size, extent, q in (("logical", (80, 128), (280., 448.), 0),
                                 ("physical", (128, 80), (448., 280.), 1)):
        surface.viewport.request_snapshot(key, frame, size, size, extent, (), content_rotation_quarters=q)
    for _ in range(180):
        surface.pump()
        if len(images) == 2 or failures:
            break
    assert not failures
    assert set(images) == {"logical", "physical"}
    # Readback rows are bottom-up, so clockwise top-down is counterclockwise in the raw array.
    expected = np.rot90(images["logical"], 1)
    assert np.ptp(images["logical"][:, :, :3]) > 5, "a blank frame cannot prove orientation"
    assert np.max(np.abs(images["physical"].astype(int) - expected.astype(int))) <= 1


def test_odd_turn_evaluates_bubble_in_the_same_logical_domain_as_the_renderer(studio):
    controller, surface, draws = studio("bubble")
    controller.state = "presented"
    extent = controller.presented_extent()
    controller.bridge.rotateContent()
    controller.on_frame()
    assert controller.evaluator._extent == extent[::-1]
    surface.pump()
    assert draws[-1].snapshot.presentation.logical_viewport_extent == controller.evaluator._extent
    evaluations = controller.evaluations
    controller.on_frame()
    assert controller.evaluations == evaluations           # no extra logical work at rest


def test_rotation_survives_canonical_saves_but_reopening_starts_a_fresh_preview(
        real_dialog, offscreen_launch, preset_copy, popups):
    from core.settings import visualizer_presets as vp
    from core.settings.visualizer_mode_registry import get_visualizer_view_pose_keys
    from tests.test_studio_preset_row_and_save_to_preset import _edited_studio, _launcher, MODE
    tab, bridge, curated, path, key, target = _edited_studio(real_dialog, offscreen_launch)
    controller = offscreen_launch[-1]
    stored, file_bytes = deepcopy(tab._settings.get("widgets")), path.read_bytes()
    camera = {k: controller.evaluation_values()[k] for k in get_visualizer_view_pose_keys(MODE)}
    bridge.rotateContent()
    assert tab._settings.get("widgets") == stored and path.read_bytes() == file_bytes
    bridge.saveCamera()
    assert vp.get_presets(MODE)[curated].starting_view == camera
    bridge.saveCurrent()
    assert vp.get_preset_settings(MODE, curated)[key] == pytest.approx(target)
    assert bridge.contentRotationQuarters == 1 and not popups
    controller.close()
    _launcher(tab, MODE).click()
    assert offscreen_launch[-1].bridge.contentRotationQuarters == 0


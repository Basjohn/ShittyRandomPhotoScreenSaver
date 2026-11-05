"""Studio <-> Settings lifecycle on a real VisualizersTab inside a never-shown dialog.

Nothing here shows a window: the Studio shell renders through QQuickRenderControl
(OffscreenStudioSurface) and the Settings dialog is never shown, so concealment is
tracked by WindowPresence without native window calls.
"""
from __future__ import annotations

import threading

import pytest

from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_presets import get_custom_preset_index
from ui.studio.waveform_adapter import WaveformStudioAdapter

MODE = "waveform_ribbon"


@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="WaveformStudio",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


class CountingRenderer:
    created = 0
    released = 0
    threads: set = set()

    def __init__(self):
        type(self).created += 1

    def prepare(self, card, frame):
        type(self).threads.add(threading.get_ident())
        return True

    def render(self, card, frame):
        assert card.quad_vao > 0 and min(card.viewport[2:]) > 0

    def release(self):
        type(self).released += 1


class LightAdapter(WaveformStudioAdapter):
    """Real schema/evaluator; a counting renderer keeps the lifecycle tests GPU-light."""

    def create_renderer(self):
        return CountingRenderer()

    def recorded_clips(self):
        return ()          # no background clip analysis in lifecycle tests


@pytest.fixture(autouse=True)
def _reset_counts():
    CountingRenderer.created = CountingRenderer.released = 0
    CountingRenderer.threads = set()
    from ui.studio.controller import StudioController
    yield
    active = StudioController.active()
    if active is not None:
        active.close()
    assert StudioController.active() is None


@pytest.fixture
def dialog_tab(qt_app, settings_manager):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from ui.tabs.visualizers_tab import VisualizersTab

    def build(preset_index=None):
        settings_manager.set("widgets", {"spotify_visualizer": {
            "enabled": True, "visualizers_enabled": True, "mode": MODE,
            "mode_activation": build_visualizer_mode_activation([MODE]),
            f"preset_{MODE}": get_custom_preset_index(MODE) if preset_index is None else preset_index}})
        dialog = QDialog()
        layout = QVBoxLayout(dialog)
        tab = VisualizersTab(settings_manager)
        layout.addWidget(tab)
        tab._select_mode_page(MODE)
        built.append(dialog)
        return dialog, tab

    built = []
    yield build
    for dialog in built:
        dialog.deleteLater()
    qt_app.processEvents()


def _surfaces(store, **kwargs):
    from ui.studio.surface import OffscreenStudioSurface

    def factory(controller):
        surface = OffscreenStudioSurface(controller, size=kwargs.get("size", (960, 600)), present_on_show=False)
        store.append(surface)
        return surface
    return factory


def _count_saves(monkeypatch, settings_manager):
    saves = []
    original = settings_manager.set_widgets_map

    def counted(widgets, **kwargs):
        saves.append(widgets["spotify_visualizer"])
        return original(widgets, **kwargs)
    monkeypatch.setattr(settings_manager, "set_widgets_map", counted)
    return saves


def _stored(settings_manager):
    return settings_manager.get("widgets")["spotify_visualizer"]


def test_custom_body_offers_the_studio_and_keeps_the_camera_checkbox(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    dialog, tab = dialog_tab()
    button = getattr(tab, f"_{MODE}_studio_button")
    body = getattr(tab, f"_{MODE}_settings_container")
    assert body.isAncestorOf(button)
    from ui.widgets.waveform_ribbon_preview import WaveformPreview
    assert body.findChildren(WaveformPreview) == []
    slider = tab._get_visualizer_preset_slider(MODE)
    assert slider._include_starting_view is not None           # camera-save choice unchanged
    calls = []
    monkeypatch.setattr(settings_link, "open_mode_studio", lambda t, m: calls.append((t, m)))
    button.click()
    assert calls == [(tab, MODE)]


def test_open_hides_only_after_first_frame_edits_save_once_and_close_restores_same_settings(
        qt_app, dialog_tab, settings_manager, monkeypatch, no_gl_checks):
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    saves = _count_saves(monkeypatch, settings_manager)
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    presence = controller.presence
    assert presence.widget is dialog
    assert controller.state == "opening" and not presence.concealed     # nothing presented yet
    surface = surfaces[0]
    surface.pump()
    assert controller.state == "presented" and presence.concealed
    assert StudioController.active() is controller
    assert CountingRenderer.created == 1 and CountingRenderer.threads

    bridge = controller.bridge
    # Live gesture: previews render, nothing is saved until the gesture ends.
    bridge.beginEdit(f"{MODE}_ribbons[1].height", "Height")
    for value in (0.6, 0.9, 1.3):
        bridge.previewValue(f"{MODE}_ribbons[1].height", 0, value)
        surface.pump()
    assert saves == []
    bridge.endEdit()
    assert len(saves) == 1 and _stored(settings_manager)[f"{MODE}_ribbons"][1]["height"] == pytest.approx(1.3)
    # A quiet/peak endpoint, edited through the A/B endpoint path.
    peak = list(_stored(settings_manager)[f"{MODE}_height"])
    bridge.commitValue(f"{MODE}_height", 1, peak[0])
    assert len(saves) == 2 and _stored(settings_manager)[f"{MODE}_height"][1] == pytest.approx(peak[0])
    bridge.undo()
    assert len(saves) == 3 and _stored(settings_manager)[f"{MODE}_height"] == pytest.approx(peak)
    assert bridge.dirty and bridge.undoText == "Height"

    evaluations = controller.evaluations
    bridge.requestClose()
    assert controller.state == "closed" and StudioController.active() is None
    assert not presence.concealed and presence.reveal_count == 1 and presence.widget is dialog
    assert surface.retired and controller.transport.stopped
    assert CountingRenderer.released == CountingRenderer.created
    # Settings was refreshed from the new canonical state, not stale widgets.
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings
    assert collect_spec_mode_settings(tab, MODE)[f"{MODE}_ribbons"][1]["height"] == pytest.approx(1.3)
    # No hidden work after close: frame callbacks and pumps do nothing.
    controller.on_frame()
    surface.pump(3)
    assert controller.evaluations == evaluations and not controller.transport.on_frame()
    assert len(saves) == 3


def test_repeated_open_close_cycles_hydrate_latest_state_and_leave_nothing_running(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    path = f"{MODE}_ribbons[0].width"
    surfaces = []
    controllers = []
    for cycle in range(5):
        controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
        controllers.append(controller)
        surfaces[-1].pump(2)
        assert controller.presence.concealed
        expected = 0.4 + 0.2 * cycle
        if cycle:
            # Reopening hydrates what the previous session saved.
            assert controller.bridge.values[path] == pytest.approx(0.4 + 0.2 * (cycle - 1))
        controller.bridge.setLoop(True)
        controller.set_playing(True)
        surfaces[-1].pump(2)
        controller.bridge.commitValue(path, 0, expected)
        controller.close()
        assert not controller.presence.concealed and StudioController.active() is None
        assert surfaces[-1].retired and not controller.transport.wants_frames
    assert CountingRenderer.created == CountingRenderer.released == 5
    assert len({id(c.presence.widget) for c in controllers}) == 1          # always the same Settings
    qt_app.processEvents()
    assert _stored(settings_manager)[f"{MODE}_ribbons"][0]["width"] == pytest.approx(1.2)


def test_single_instance_reuses_the_open_studio(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    first = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump()
    second = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    assert second is first and len(surfaces) == 1
    first.close()


def test_failure_to_open_keeps_settings_visible_and_reports(qt_app, dialog_tab, monkeypatch):
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    from ui import styled_popup
    _dialog, tab = dialog_tab()
    shown = []
    monkeypatch.setattr(styled_popup.StyledPopup, "exec", lambda self: shown.append(self._message) or 0)

    def broken(_controller):
        raise RuntimeError("no GL for you")

    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=broken)
    assert controller.state == "closed" and not controller.presence.concealed
    assert controller.presence.reveal_count == 0 and StudioController.active() is None
    assert shown and "no GL for you" in shown[0]


def test_studio_window_lost_after_presentation_restores_settings(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump()
    assert controller.presence.concealed
    surfaces[0].lost.emit()                 # e.g. the native window was destroyed underneath us
    assert controller.state == "closed" and not controller.presence.concealed


def test_first_commit_on_a_curated_preset_moves_to_custom(qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab(preset_index=0)
    slider = tab._get_visualizer_preset_slider(MODE)
    assert slider.preset_index() == 0
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump()
    curated = controller.bridge.presetLabel
    controller.bridge.commitValue(f"{MODE}_ribbons[2].rate", 0, 0.75)
    custom = get_custom_preset_index(MODE)
    assert slider.preset_index() == custom and _stored(settings_manager)[f"preset_{MODE}"] == custom
    assert controller.bridge.presetLabel != curated
    assert _stored(settings_manager)[f"{MODE}_ribbons"][2]["rate"] == pytest.approx(0.75)
    controller.close()


def test_real_production_renderer_draws_into_the_studio_viewport(qt_app, dialog_tab, no_gl_checks):
    import numpy as np
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    class RealRendererNoClips(WaveformStudioAdapter):
        def recorded_clips(self):
            return ()
    controller = open_mode_studio(tab, MODE, adapter=RealRendererNoClips(),
                                  surface_factory=_surfaces(surfaces, size=(1100, 640)))
    surface = surfaces[0]
    for _ in range(200):
        surface.pump()
        if controller.bridge.viewportStatus != "preparing":
            break
    assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
    from PySide6.QtCore import QPointF
    slot = surface.host.slot
    origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
    x, y = int(origin.x()), int(origin.y())
    w, h = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
    pixels = surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3]
    assert pixels.std() > 4.0 and pixels.max() > 60          # a lit scene, not a flat placeholder
    controller.close()


def test_visible_window_surface_is_modal_and_retires_without_ever_being_shown(qt_app, dialog_tab):
    """The production surface is constructed and retired here but never shown (no visible windows)."""
    from PySide6.QtCore import QRect, Qt
    from ui.studio.controller import StudioController
    from ui.studio.surface import StudioWindowSurface, initial_geometry
    from ui.studio.presence import WindowPresence
    from ui.studio.settings_link import VisualizerSettingsStore
    dialog, tab = dialog_tab()
    controller = StudioController(LightAdapter(), VisualizerSettingsStore(tab, MODE), WindowPresence(dialog),
                                  lambda c: None)
    from ui.studio.session import StudioEditSession
    controller.session = StudioEditSession(controller.adapter.schema(), controller.store)
    controller.evaluator = controller.adapter.create_evaluator()
    from ui.studio.controller import StudioBridge
    controller.bridge = StudioBridge(controller)
    surface = StudioWindowSurface(controller, anchor=QRect(100, 100, 900, 700))
    assert surface.window.modality() == Qt.WindowModality.ApplicationModal
    assert not surface.window.isVisible() and surface.viewport.window() is surface.window
    geometry = initial_geometry(QRect(100, 100, 900, 700))
    assert geometry.width() >= 960 and geometry.height() >= 600
    lost, closes = [], []
    surface.lost.connect(lambda: lost.append(True))
    surface.closeRequested.connect(lambda: closes.append(True))
    from PySide6.QtCore import QCoreApplication as _App
    from PySide6.QtGui import QCloseEvent
    _App.sendEvent(surface.window, QCloseEvent())       # what Alt+F4 / the title-bar close delivers
    assert closes == [True]
    surface.retire()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    import shiboken6
    assert lost == []                              # our own retirement is not a "lost" window
    assert not shiboken6.isValid(surface.window)   # destroyed by deferred deletion, never shown
    controller.evaluator.release()



def test_viewport_presents_the_card_extent_letterboxed_and_framings_switch(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(),
                                  surface_factory=_surfaces(surfaces, size=(1400, 820)))
    surfaces[0].pump(2)
    viewport, slot = surfaces[0].viewport, surfaces[0].host.slot
    assert controller.bridge.framingId == (controller.adapter.default_framing() or controller.framings[0].id)
    card = next(f for f in controller.framings if f.id == "card").extent
    for framing in controller.framings:
        controller.select_framing(framing.id)
        surfaces[0].pump()
        assert viewport.width() <= slot.width() + 1e-6 and viewport.height() <= slot.height() + 1e-6
        # No framing ever shows less of the world than the live card does.
        assert viewport.extent[0] >= card[0] - 1e-6 and viewport.extent[1] >= card[1] - 1e-6
        if framing.fill:
            # Fills the slot: no letterbox on either axis, the card grown to the slot's shape.
            assert (viewport.width(), viewport.height()) == pytest.approx((slot.width(), slot.height()))
            assert min(viewport.extent[0] / card[0], viewport.extent[1] / card[1]) == pytest.approx(1.0)
        else:
            aspect = framing.extent[0] / framing.extent[1]
            assert viewport.width() / viewport.height() == pytest.approx(aspect, rel=1e-3)
            assert viewport.extent == framing.extent
    controller.close()


def test_view_pose_is_preview_only_unless_the_camera_checkbox_allows_the_orbit(
        qt_app, dialog_tab, settings_manager, monkeypatch, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    saves = _count_saves(monkeypatch, settings_manager)
    checkbox = tab._get_visualizer_preset_slider(MODE)._include_starting_view
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump()
    turn = f"{MODE}_turn"
    before = controller.session.committed_values[turn]
    checkbox.setChecked(False)
    controller.bridge.commitValue(turn, 0, 0.3)
    controller.bridge.commitValue(f"{MODE}_scene_scale", 0, 1.4)
    assert saves == [] and controller.bridge.values[turn] == pytest.approx(0.3)
    assert controller.evaluation_values()[f"{MODE}_scene_scale"] == pytest.approx(1.4)
    checkbox.setChecked(True)
    controller.bridge.orbitBy(40.0, 0.0)
    controller.bridge.endOrbit()
    assert len(saves) == 1 and controller.session.committed_values[turn] != pytest.approx(before)
    assert controller.evaluation_values()[f"{MODE}_scene_scale"] == pytest.approx(1.4)   # zoom stays preview
    controller.close()


def test_measured_signals_feed_traces_and_the_response_tuner(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    bridge = controller.bridge
    bridge.setWorkspace("reactivity")
    controller.set_playing(True)
    surfaces[0].pump(12)
    measured = bridge.measurements
    response = bridge.response
    assert set(measured["sources"]) == {s["id"] for s in response["sources"]}
    assert {t["id"] for t in response["targets"]} <= set(measured["targets"])
    assert bridge.traces and all(len(v) >= 2 for v in bridge.traces.values())
    target = response["targets"][0]
    cell = target["cells"][0]
    bridge.selectTarget(target["id"])
    bridge.commitValue(cell["gain"], 0, 1.25)
    assert controller.session.get((f"{MODE}_routing", target["id"], 0, 0)) == pytest.approx(1.25)
    controller.close()


@pytest.mark.parametrize("size", [(1100, 700), (1600, 900)])
def test_inspector_rows_never_overlap_at_any_inspector_width(qt_app, dialog_tab, no_gl_checks, size):
    """Offscreen layout check: every inspector row contains its own content and rows stack without overlap."""
    import shiboken6
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces, size=size))
    surface = surfaces[0]

    def scene_span(item):
        top = item.mapToScene(QPointF(0, 0)).y()
        return top, top + item.height()

    def visible_descendants(item):
        for child in item.childItems():
            if child.isVisible() and child.height() > 0:
                yield child
                yield from visible_descendants(child)

    checked = 0
    for workspace in ("composition", "reactivity", "appearance", "world"):
        controller.bridge.setWorkspace(workspace)
        surface.pump(3)
        def walk(item):
            for child in item.childItems():
                yield child
                yield from walk(child)
        rows = [r for r in walk(surface.host.root) if r.objectName() == "inspectorRow" and r.isVisible()
                and r.height() > 0]
        by_parent: dict = {}
        for row in rows:
            # Keyed by the C++ parent (Python wrapper ids can be reused across distinct parents).
            by_parent.setdefault(shiboken6.getCppPointer(row.parentItem())[0], []).append(row)
        for siblings in by_parent.values():
            spans = sorted(scene_span(r) for r in siblings)
            for (_top, bottom), (next_top, _b) in zip(spans, spans[1:]):
                assert bottom <= next_top + 0.5, (workspace, bottom, next_top)
        for row in rows:
            top, bottom = scene_span(row)
            for child in visible_descendants(row):
                if child.objectName() == "inspectorRow":
                    continue
                c_top, c_bottom = scene_span(child)
                assert c_top >= top - 1.0 and c_bottom <= bottom + 1.0, (workspace, row.property("rowData")["id"])
            checked += 1
    assert checked > 20
    controller.close()


def test_live_card_extent_resolves_on_the_visualizer_display_not_only_the_settings_screen(qt_app):
    """5 Nov regression: the card lives on another display than Settings; the Studio must still find it."""
    from types import SimpleNamespace
    from core.settings.visualizer_mode_registry import get_visualizer_layout_profile
    from ui.studio.settings_link import VisualizerSettingsStore
    profile = get_visualizer_layout_profile(MODE)
    widgets = {"spotify_visualizer": {"position": "Custom", "mode": MODE},
               "custom_layout": {"version": 2, "displays": {"serial:999|model:Test TV|name:Test TV": {
                   "spotify_visualizer": {profile: {"rect": {"x": .1, "y": .1, "width": .4, "height": .5},
                                                    "resize_mode": "visualizer_rect",
                                                    "size_payload": {"viewport_extent": [1282.5, 1005.0],
                                                                     "width": 1026, "height": 804}}}}}}}
    tab = SimpleNamespace(_settings=SimpleNamespace(get=lambda key: widgets if key == "widgets" else None),
                          window=lambda: SimpleNamespace(screen=lambda: None))
    store = VisualizerSettingsStore(tab, MODE)
    assert store.card_extent() == (1282.5, 1005.0)
    widgets["spotify_visualizer"]["position"] = "Top Left"        # not CUSTOM: production uses the baseline
    assert store.card_extent() is None


def test_navigation_zoom_dolly_pan_reset_and_keep_view(qt_app, dialog_tab, settings_manager, monkeypatch,
                                                       no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    saves = _count_saves(monkeypatch, settings_manager)
    tab._get_visualizer_preset_slider(MODE)._include_starting_view.setChecked(False)
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump()
    nav = controller.adapter.navigation()
    saved = controller.session.committed_values
    fov0, dolly0 = saved[nav.zoom.key], saved[nav.dolly.key]
    for _ in range(40):
        controller.bridge.zoomBy(-1.0, False)                    # wheel out: wider lens, bounded
    assert controller.evaluation_values()[nav.zoom.key] == pytest.approx(nav.zoom.bounds[1])
    controller.bridge.zoomBy(2.0, True)                         # Shift+wheel: dolly in
    assert controller.evaluation_values()[nav.dolly.key] > dolly0
    controller.bridge.panBy(100.0, -50.0, 800.0, 600.0)
    assert controller.evaluation_values()[nav.pan_x.key] != saved[nav.pan_x.key]
    readout = {r["label"]: r for r in controller.bridge.viewReadout}
    assert readout[nav.zoom.label]["changed"] and controller.bridge.viewModified
    assert saves == []                                         # navigation alone never saves
    controller.bridge.keepView()
    assert len(saves) == 1 and controller.session.committed_values[nav.zoom.key] == pytest.approx(nav.zoom.bounds[1])
    assert controller.evaluation_values()[nav.dolly.key] > dolly0     # dolly/pan stay preview views
    controller.bridge.resetCamera()                             # (double-click does the same)
    values = controller.evaluation_values()
    assert values[nav.dolly.key] == pytest.approx(dolly0) and not controller.bridge.viewModified
    assert fov0 != values[nav.zoom.key]                         # the kept lens is now the saved camera
    controller.close()


def test_close_records_step_timings_and_never_waits_on_background_jobs(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump()

    class SlowJob:
        cancelled = False

        def cancel(self):
            type(self).cancelled = True          # a real job kills its worker without waiting

    controller._clip_jobs["clip:x"] = SlowJob()
    controller.close()
    timings = controller.close_timings
    assert SlowJob.cancelled
    assert {"gesture", "transport", "jobs", "surface", "evaluator", "settings", "total"} <= set(timings)
    assert timings["jobs"] < 50.0


def test_clip_job_cancel_does_not_block(qt_app):
    import time
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.waveform_recorded_inputs import ClipLoadJob
    clip = StudioFixture("clip:none", "None", RECORDED, 0.0, "does-not-exist.jsonl")
    job = ClipLoadJob(clip, {}, lambda *_a: None)
    started = time.perf_counter()
    job.cancel()
    assert (time.perf_counter() - started) < 0.25


@pytest.mark.parametrize("size", [(960, 600), (1672, 941)])
def test_dashboard_panels_tile_under_the_viewport_without_overlap(qt_app, dialog_tab, no_gl_checks, size):
    """Dashboard (mock): ribbon list | wide viewport on top, the workspace's panels side by side underneath, at
    the window's minimum size and at full size: panels never overlap each other or the viewport, stay inside
    the window, and every shown group sits in exactly one panel."""
    from PySide6.QtCore import QPointF, QRectF
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces, size=size))
    surface = surfaces[0]

    def walk(item):
        for child in item.childItems():
            yield child
            yield from walk(child)

    def rect(item):
        top_left = item.mapToScene(QPointF(0, 0))
        return QRectF(top_left.x(), top_left.y(), item.width(), item.height())
    assert controller.bridge.framingId == controller.adapter.default_framing()
    root = surface.host.root
    window = QRectF(0, 0, size[0], size[1])
    for workspace in ("composition", "reactivity", "appearance", "world"):
        controller.bridge.setWorkspace(workspace)
        surface.pump(3)
        panels = [rect(i) for i in walk(root) if i.isVisible()
                  and i.objectName() in ("dashboardPanel", "responseDock")]
        viewport = rect(next(i for i in walk(root) if i.objectName() == "viewportSlot"))
        assert panels, workspace
        for index, panel in enumerate(panels):
            assert window.adjusted(-0.5, -0.5, 0.5, 0.5).contains(panel), (workspace, panel)
            assert panel.top() >= viewport.bottom(), (workspace, panel, viewport)
            assert panel.width() > 150 and panel.height() > 120, (workspace, panel)
            for other in panels[index + 1:]:
                assert not panel.adjusted(0.5, 0.5, -0.5, -0.5).intersects(other), (workspace, panel, other)
        shown = [g["group"] for g in controller.bridge.inspector]
        placed = [g["group"] for c in controller.bridge.inspectorColumns for g in c["groups"]]
        assert sorted(placed) == sorted(shown), workspace
    controller.close()


def test_switch_rows_are_checkboxes_that_commit(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces, size=(1400, 820)))
    surface = surfaces[0]
    controller.bridge.setWorkspace("appearance")
    surface.pump(3)

    def walk(item):
        for child in item.childItems():
            yield child
            yield from walk(child)
    boxes = [i for i in walk(surface.host.root) if i.objectName() == "checkBox" and i.isVisible()]
    assert boxes
    prop = next(p for p in controller.session.schema.properties
                if p.instrument == "switch" and p.workspace == "appearance")
    before = controller.session.get(prop.path)
    controller.bridge.commitValue(prop.id, 0, not before)
    assert controller.session.get(prop.path) is (not before)
    controller.close()


# ------------------------------------------------------------------ every exit path restores Settings
def _assert_settings_restored(controller, dialog):
    """Settings is back exactly once, usable, and the Studio is fully gone (no in-between state)."""
    from ui.studio.controller import StudioController
    presence = controller.presence
    assert not presence.concealed, "Settings is still concealed"
    assert presence.reveal_count == 1, f"revealed {presence.reveal_count} times"
    assert presence.widget is dialog and dialog.isEnabled()
    assert controller.state == "closed" and StudioController.active() is None
    assert controller.surface is None and controller.transport.stopped


def _open_presented(tab, **kwargs):
    from ui.studio.settings_link import open_mode_studio
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=kwargs.pop("adapter", LightAdapter()),
                                  surface_factory=_surfaces(surfaces), **kwargs)
    surfaces[0].pump()
    assert controller.state == "presented" and controller.presence.concealed
    return controller, surfaces[0]


def _press_escape(surface):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent, QCoreApplication
    root = surface.host.root
    root.forceActiveFocus()
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(surface.window, QKeyEvent(kind, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    QCoreApplication.processEvents()        # the shell defers the close out of its key handler


@pytest.mark.parametrize("path", ["close_button", "escape", "window_x", "window_lost", "app_quit"])
def test_every_exit_path_restores_settings(qt_app, dialog_tab, no_gl_checks, path):
    dialog, tab = dialog_tab()
    controller, surface = _open_presented(tab)
    if path == "close_button":
        controller.bridge.requestClose()
    elif path == "escape":
        _press_escape(surface)
    elif path == "window_x":
        surface.closeRequested.emit()            # the window's close event (X, Alt+F4) emits this
    elif path == "window_lost":
        surface.lost.emit()
    elif path == "app_quit":
        qt_app.aboutToQuit.emit()                # the saver/engine retiring the application
    _assert_settings_restored(controller, dialog)


@pytest.mark.parametrize("failing", ["evaluator", "surface", "adapter", "jobs", "gesture", "refresh"])
def test_teardown_failures_never_leave_settings_concealed(qt_app, dialog_tab, no_gl_checks, monkeypatch, failing):
    dialog, tab = dialog_tab()
    controller, surface = _open_presented(tab)

    def boom(*_args, **_kwargs):
        raise RuntimeError(f"{failing} exploded")
    if failing == "evaluator":
        monkeypatch.setattr(controller.evaluator, "release", boom)
    elif failing == "surface":
        monkeypatch.setattr(surface, "retire", boom)      # e.g. a failed or slow renderer release
    elif failing == "adapter":
        monkeypatch.setattr(controller.adapter, "release", boom)
    elif failing == "jobs":
        class Job:
            def cancel(self):
                raise RuntimeError("clip job cancel exploded")
        controller._clip_jobs["clip:x"] = Job()
    elif failing == "gesture":
        monkeypatch.setattr(controller.session, "cancel_gesture", boom)
    elif failing == "refresh":
        monkeypatch.setattr(controller.presence, "_refresh", boom)
    controller.close()
    _assert_settings_restored(controller, dialog)
    if failing != "refresh":
        assert controller.close_failures, "the failing step is reported"


def test_settings_going_away_closes_the_studio(qt_app, dialog_tab, no_gl_checks):
    """The saver retiring Settings (dialog destroyed) while the Studio is open ends the Studio too."""
    from ui.studio.controller import StudioController
    dialog, tab = dialog_tab()
    controller, _surface = _open_presented(tab)
    dialog.destroyed.emit()
    assert controller.state == "closed" and StudioController.active() is None


def test_restoration_check_detects_a_concealed_settings_negative_control(qt_app, dialog_tab, no_gl_checks):
    """Negative control: a retirement that skips the reveal (the mode-switch path) is caught by the check."""
    dialog, tab = dialog_tab()
    controller, _surface = _open_presented(tab)
    controller._retire(reveal=False)
    controller.state = "closed"
    with pytest.raises(AssertionError, match="still concealed"):
        _assert_settings_restored(controller, dialog)
    controller.presence.reveal()


# ------------------------------------------------------------------ header preset dropdown
def _click(surface, item):
    from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        QCoreApplication.sendEvent(surface.window, QMouseEvent(kind, centre, centre, Qt.MouseButton.LeftButton,
                                                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    QCoreApplication.processEvents()
    surface.pump()


def test_preset_dropdown_lists_presets_and_switches_only_on_an_explicit_pick(
        qt_app, dialog_tab, settings_manager, monkeypatch, no_gl_checks):
    from core.settings.visualizer_presets import get_custom_preset_index, get_preset_names
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces, size=(1400, 820)))
    surface = surfaces[0]
    surface.pump(2)
    bridge = controller.bridge
    names = get_preset_names(MODE)
    custom = get_custom_preset_index(MODE)
    presets = bridge.presets
    assert [p["label"] for p in presets] == list(names)
    assert [p["index"] for p in presets if p["current"]] == [custom]
    # A Custom edit that must survive switching away and back.
    path = f"{MODE}_ribbons[0].width"
    bridge.commitValue(path, 0, 0.77)
    saves = _count_saves(monkeypatch, settings_manager)

    def walk(item):
        for child in item.childItems():
            yield child
            yield from walk(child)
    root = surface.host.root
    pill = next(i for i in walk(root) if i.objectName() == "presetPill")
    menu_items = lambda: [i for i in walk(surface.window.contentItem()) if i.objectName() == "presetItem"]
    # Clicking the pill opens the list; it does not change the preset (the reported bug).
    _click(surface, pill)
    assert len(menu_items()) == len(names)
    assert [p["index"] for p in bridge.presets if p["current"]] == [custom] and saves == []
    # Escape closes it without a pick: nothing changes.
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(surface.window, QKeyEvent(kind, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    QCoreApplication.processEvents()
    surface.pump()
    assert not menu_items() and controller.state == "presented"      # Esc closed the list, not the Studio
    assert saves == [] and controller.store.preset_index() == custom
    # An explicit pick switches through Settings' own preset authority and re-opens the session on it.
    _click(surface, pill)
    _click(surface, menu_items()[0])
    assert controller.store.preset_index() == 0 and bridge.presetLabel == names[0]
    assert _stored(settings_manager)[f"preset_{MODE}"] == 0
    assert controller.session.values == controller.store.snapshot()
    assert not controller.session.dirty and not bridge.canUndo
    # Back to Custom: the Custom edit is restored, never lost.
    bridge.selectPreset(custom)
    assert controller.store.preset_index() == custom
    assert controller.session.get((f"{MODE}_ribbons", 0, "width")) == pytest.approx(0.77)
    controller.close()
    assert not controller.presence.concealed

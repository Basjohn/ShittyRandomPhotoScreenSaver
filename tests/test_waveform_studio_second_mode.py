"""The Studio framework without Waveform: a tiny test-only mode drives shell, session, transport and save.

Proves the reuse contract for every visualizer (framed 3D like Extruded Bubble and flat 2D like Spectrum,
Oscilloscope or Bubble): a mode supplies only a schema, evaluator, fixtures, scene objects and a renderer,
and declares what its viewport supports. The toy mode is a flat 2D, camera-less adapter: no navigation,
no scene handles, no inspector extras. Nothing in the shell is copied.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest

from ui.studio.adapter import (NavAxis, REFERENCE, SYNTHETIC, StudioCapabilities, StudioFixture, StudioFraming,
                               StudioModeAdapter, StudioNavigation)
from ui.studio.schema import (QUIET_PEAK, SCALAR, SWITCH, ResponseCell, ResponseSource, ResponseTarget,
                              SceneObject, StudioProperty, StudioResponse, StudioSchema, Workspace)


@dataclass(frozen=True)
class ToyFrame:
    time: float
    glow: float


class ToyEvaluator:
    def __init__(self):
        self._fixtures = (StudioFixture("calm", "Calm", REFERENCE, 4.0), StudioFixture("pulse", "Pulse", SYNTHETIC, 6.0))
        self._fixture = self._fixtures[0]
        self.released = False

    def fixtures(self):
        return self._fixtures

    def select(self, fixture_id):
        self._fixture = next(f for f in self._fixtures if f.id == fixture_id)
        return self._fixture

    @property
    def fixture(self):
        return self._fixture

    def evaluate(self, time, values, *, exact=True, revision=None):
        low, high = values["toy_glow"]
        return ToyFrame(round(time, 6), low + (high - low) * (time / self._fixture.duration) * values["toy_gain"])

    def measurements(self):
        return {"sources": {"in": .5}, "targets": {"glow": .25}, "signals": {"Glow": .25}}

    def release(self):
        self.released = True


class ToyRenderer:
    drawn: list = []
    released = 0

    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        type(self).drawn.append(frame)

    def release(self):
        type(self).released += 1


class ToyAdapter(StudioModeAdapter):
    """A flat 2D mode: a live preview, but no camera and no scene handles."""
    mode_id = "toy_mode"
    title = "Toy Studio"
    navigation_calls = 0
    handle_calls = 0

    def capabilities(self):
        return StudioCapabilities(viewport=True, camera=False, handles=False)

    # A careless 2D adapter that still answers these must never be consulted.
    def navigation(self):
        type(self).navigation_calls += 1
        return StudioNavigation(zoom=NavAxis("toy_gain", (0., 2.)))

    def scene_handles(self, *args, **kwargs):
        type(self).handle_calls += 1
        return {"outline": [[0, 0], [1, 1]], "handles": [{"id": "x"}]}

    def schema(self):
        def admit(key, candidate, previous):
            if key == "toy_glow":
                return sorted(max(0., min(1., float(v))) for v in candidate)
            if key == "toy_on":
                return bool(candidate)
            return max(0., min(2., float(candidate)))
        response = StudioResponse((ResponseSource("in", "Input"),),
                                  (ResponseTarget("glow", "Glow", "How bright it glows.",
                                                  (ResponseCell("in", "toy_gain", "toy_gain"),), "toy_glow"),),
                                  (0., 2.), (0., 2.))
        return StudioSchema("toy_mode", "Toy Studio", (Workspace("look", "Look", ("Glow",)),), (
            StudioProperty("toy_gain", ("toy_gain",), "Gain", "look", "Glow", SCALAR, 0., 2.),
            StudioProperty("toy_glow", ("toy_glow",), "Glow", "look", "Glow", QUIET_PEAK, 0., 1.),
            StudioProperty("toy_on", ("toy_on",), "Enabled", "look", "Glow", SWITCH),
        ), admit, response=response, group_traces=(("Glow", ("Glow",)),))

    def scene_objects(self, values):
        return (SceneObject("orb", "Orb", "#808080"),)

    def create_evaluator(self):
        return ToyEvaluator()

    def create_renderer(self):
        return ToyRenderer()

    def framings(self, card_extent, card_style=None):
        return (StudioFraming("square", "Square", (300., 300.)),)


class ToyStore:
    def __init__(self):
        self.values = {"toy_gain": 1.0, "toy_glow": [0.1, 0.9], "toy_on": True}
        self.commits = []

    def snapshot(self):
        return deepcopy(self.values)

    def commit(self, values, changed):
        self.commits.append(frozenset(changed))
        self.values = deepcopy(dict(values))
        return deepcopy(self.values)

    def preset_label(self):
        return "Toy Custom"


class Presence:
    def __init__(self):
        self.concealed = False
        self.reveals = 0

    def conceal(self):
        self.concealed = True

    def reveal(self):
        self.concealed = False
        self.reveals += 1


@pytest.fixture
def toy_studio(qt_app):
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    ToyRenderer.drawn, ToyRenderer.released = [], 0
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(900, 600), present_on_show=False))
        return surfaces[-1]
    store, presence = ToyStore(), Presence()
    controller = StudioController(ToyAdapter(), store, presence, factory)
    yield controller, store, presence, surfaces
    if StudioController.active() is controller:
        controller.close()


def test_a_non_waveform_mode_runs_the_whole_shell(toy_studio):
    controller, store, presence, surfaces = toy_studio
    assert controller.open()
    surfaces[0].pump(2)
    assert presence.concealed and controller.bridge.title == "Toy Studio"
    assert controller.bridge.modes == [{"id": "toy_mode", "title": "Toy Studio"}]
    assert surfaces[0].viewport.extent == (300., 300.)
    assert surfaces[0].viewport.width() == pytest.approx(surfaces[0].viewport.height())
    assert ToyRenderer.drawn and isinstance(ToyRenderer.drawn[-1], ToyFrame)
    bridge = controller.bridge
    assert [row["id"] for group in bridge.inspector for row in group["rows"]] == ["toy_gain", "toy_glow", "toy_on"]
    # Session + canonical save path: one save per gesture, named undo, A/B endpoint edits.
    bridge.beginEdit("toy_gain", "Gain")
    bridge.previewValue("toy_gain", 0, 1.5)
    surfaces[0].pump()
    assert store.commits == []
    bridge.endEdit()
    bridge.commitValue("toy_glow", 1, 0.5)
    bridge.commitValue("toy_on", 0, False)
    assert store.commits == [frozenset({"toy_gain"}), frozenset({"toy_glow"}), frozenset({"toy_on"})]
    assert store.values["toy_glow"] == [0.1, 0.5] and bridge.dirty
    bridge.undo()
    assert store.values["toy_on"] is True
    # Transport: deterministic scrub, playback driven only by frames.
    controller.seek(3.0)
    surfaces[0].pump()
    assert ToyRenderer.drawn[-1].time == 3.0
    controller.select_fixture("pulse")
    assert controller.transport.duration == 6.0 and bridge.fixtureId == "pulse"
    controller.set_playing(True)
    surfaces[0].pump(3)
    assert bridge.traces["Glow"]
    controller.close()
    assert not presence.concealed and presence.reveals == 1 and surfaces[0].retired
    assert ToyRenderer.released == 1 and controller.evaluator.released and controller.transport.stopped


def _walk(item):
    for child in item.childItems():
        yield child
        yield from _walk(child)


def test_a_flat_2d_mode_gets_no_camera_navigation_or_handles(toy_studio):
    controller, store, presence, surfaces = toy_studio
    ToyAdapter.navigation_calls = ToyAdapter.handle_calls = 0
    assert controller.open()
    surface = surfaces[0]
    surface.pump(3)
    bridge = controller.bridge
    assert bridge.capabilities == {"viewport": True, "camera": False, "handles": False, "objects": True,
                                   "brush": False}
    named = {i.objectName(): i for i in _walk(surface.host.root) if i.objectName()}
    for chrome in ("keepViewButton", "resetViewButton", "orbitArea", "handleLayer"):
        assert not named[chrome].isVisible(), chrome
    assert not named["noPreviewNote"].isVisible()
    # Gestures a 3D mode would map are inert: no pose, no saves, no readout.
    before = dict(store.values)
    bridge.orbitBy(40.0, 20.0)
    bridge.zoomBy(2.0, False)
    bridge.panBy(10.0, 10.0, 300.0, 300.0)
    bridge.keepView()
    bridge.endOrbit()
    surface.pump(2)
    assert store.values == before and store.commits == [] and not bridge.viewModified
    assert bridge.viewReadout == [] and bridge.handles["handles"] == []
    assert ToyAdapter.navigation_calls == 0 and ToyAdapter.handle_calls == 0
    # The 2D preview still renders through the mode's renderer, letterboxed by its framing.
    assert ToyRenderer.drawn and surfaces[0].viewport.extent == (300., 300.)
    # The help overlay lists only the gestures a 2D mode has (no camera or handle gestures).
    overlay = named["helpOverlay"]
    gestures = overlay.property("gestures").toVariant()
    assert gestures and not any(g[0] in ("view", "lens", "move") for g in gestures)
    # No inspector extras declared: none are offered.
    assert all(not g["presets"] and not g["lifecycle"] and not g["card"] for g in bridge.inspector)
    controller.close()


def test_an_inspector_only_mode_creates_no_renderer(qt_app):
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface

    class InspectorOnly(ToyAdapter):
        def capabilities(self):
            return StudioCapabilities(viewport=False)

        def create_renderer(self):
            raise AssertionError("no viewport declared: the renderer must never be created")

    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(800, 500), present_on_show=False))
        return surfaces[-1]
    store, presence = ToyStore(), Presence()
    controller = StudioController(InspectorOnly(), store, presence, factory)
    assert controller.open()
    surfaces[0].pump(4)
    bridge = controller.bridge
    assert bridge.capabilities == {"viewport": False, "camera": False, "handles": False, "objects": True,
                                   "brush": False}
    assert bridge.viewportStatus == "none" and not surfaces[0].viewport.isVisible()
    named = {i.objectName(): i for i in _walk(surfaces[0].host.root) if i.objectName()}
    assert named["noPreviewNote"].isVisible()
    bridge.commitValue("toy_gain", 0, 0.5)
    assert store.commits == [frozenset({"toy_gain"})]
    controller.close()
    assert presence.reveals == 1 and StudioController.active() is None


def test_the_registry_and_mode_switch_rebuild_the_session_without_revealing_settings(qt_app, monkeypatch):
    from ui.studio import registry
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    monkeypatch.setattr(registry, "_ENTRIES", dict(registry._ENTRIES))
    registry.register_studio_adapter("toy_mode", __name__ + ":ToyAdapter")
    assert {e.mode_id for e in registry.studio_modes()} >= {"waveform_ribbon", "toy_mode"}
    assert isinstance(registry.create_adapter("toy_mode"), ToyAdapter)

    class OtherToy(ToyAdapter):
        mode_id = "toy_other"
        title = "Other Toy"

    stores = {"toy_mode": ToyStore(), "toy_other": ToyStore()}
    surfaces = []
    presence = Presence()

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(800, 500), present_on_show=False))
        return surfaces[-1]
    controller = StudioController(ToyAdapter(), stores["toy_mode"], presence, factory,
                                  mode_switcher=lambda mode: (OtherToy(), stores[mode]),
                                  modes=lambda: (("toy_mode", "Toy"), ("toy_other", "Other Toy")))
    controller.open()
    surfaces[-1].pump()
    controller.bridge.switchMode("toy_other")
    assert controller.adapter.mode_id == "toy_mode"              # the picker only asks; the controller's edge switches
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    assert presence.concealed and presence.reveals == 0          # no Settings flash between modes
    surfaces[-1].pump()
    assert controller.adapter.mode_id == "toy_other" and controller.bridge.modeId == "toy_other"
    assert surfaces[0].retired and len(surfaces) == 2
    controller.bridge.commitValue("toy_gain", 0, 0.5)
    assert stores["toy_other"].commits and not stores["toy_mode"].commits     # saves go to the active mode
    controller.close()
    assert presence.reveals == 1 and StudioController.active() is None

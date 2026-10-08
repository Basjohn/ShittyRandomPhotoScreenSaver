"""Settings Arrange draws what the saver places: one size and one placement authority.

Sizes come from each family's own QML, measured through the adapter's own model
construction on detached items; uncommitted placement composes the display
presenter's own anchor/stacking functions. The oracle is the saver's real
presenter and retained host (constructed, never shown).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import re

import pytest
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QGuiApplication

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.models import ShadowSettings
from core.settings.visualizer_mode_registry import get_visualizer_layout_profile
from rendering.custom_layout_contract import (
    deserialize_custom_layout_entry,
    get_widget_layout_variant_payload,
    load_custom_layout_map,
    resolve_content_sized_rect,
)
from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.display_presenter import QuickDisplayPresenter
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.authored_layout_projection import project_authored_display_layout
from rendering.quick.widgets.family_binder import (
    ClockFamilyAdapter,
    SystemStatsFamilyAdapter,
    WeatherFamilyAdapter,
    default_ordinary_family_adapters,
)
from rendering.quick.widgets.geometry_resolver import resolve_overlay_geometry_policy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.widgets.preferred_size_measurement import (
    OrdinaryPreferredSizeMeter,
    ordinary_instance_order,
)
from rendering.quick.widgets.registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    ordinary_widget_family_component,
)
from rendering.visualizer_media_adjacency import VISUALIZER_MEDIA_GAP
from rendering.widget_descriptors import get_widget_runtime_descriptors
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel

pytestmark = pytest.mark.usefixtures("qt_app")


def _make_runtime(qt_app, generation: int):
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=generation,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    return runtime, factory


def _families(*active: str) -> dict:
    """TEST INPUT: every family explicit; an absent one would inherit its default."""

    return {family: family in active for family in DEFAULT_SETTINGS["widgets"]["family_activation"]}


def _intersects(a: QRect, b: QRect) -> bool:
    return a.intersects(b)


def test_every_ordinary_widget_has_one_family_component_and_model_property() -> None:
    adapters = default_ordinary_family_adapters()
    used = set()
    for descriptor in get_widget_runtime_descriptors():
        if descriptor.widget_id == "spotify_visualizer":
            continue
        owners = [c for c in (a.presentation_component(descriptor.widget_id) for a in adapters) if c]
        assert len(owners) == 1, descriptor.widget_id
        used.add(owners[0])
    assert used == {component.family_id for component in ORDINARY_WIDGET_FAMILY_COMPONENTS}
    for component in ORDINARY_WIDGET_FAMILY_COMPONENTS:
        source = (quick_qml_root() / component.qml_filename).read_text(encoding="utf-8")
        assert re.search(rf"required property \w+ {component.model_property}\b", source), component


class _NoServices:
    """The saver's build path with no provider/service lifetime at all."""

    def has_runtime_service(self, _widget_id: str) -> bool:
        return False

    def retire_widget_service(self, _widget_id: str) -> None:
        return None


@pytest.mark.qt
def test_meter_reads_the_saver_cards_preferred_size_for_every_family(qt_app) -> None:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    # TEST INPUT: an analogue face has no time-dependent text width.
    widgets["clock"]["display_mode"] = "analog"
    shadows = asdict(ShadowSettings.from_widgets_map(widgets))
    bounds = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)
    meter = OrdinaryPreferredSizeMeter()
    runtime, factory = _make_runtime(qt_app, 301)
    host = runtime.scene_controller.ordinary_widget_host
    measured = 0
    try:
        for descriptor in get_widget_runtime_descriptors():
            widget_id = descriptor.widget_id
            adapter = next((a for a in meter.adapters if a.presentation_component(widget_id)), None)
            if adapter is None:
                continue
            # The family's real retained card (its own style, shell and host adoption).
            retained = adapter.build(
                widget_id=widget_id, widgets_config=widgets, host=host,
                geometry=OverlayWidgetGeometry(0.0, 0.0, 100.0, 100.0), display_bounds=bounds,
                display_identity="screen:parity", shadow_values=shadows,
                runtime_manager=_NoServices(), runtime_generation=None,
            )
            assert retained is not None, widget_id
            try:
                saver = (
                    float(retained.item.property("preferredContentWidth")),
                    float(retained.item.property("preferredContentHeight")),
                )
            finally:
                retained.retire()
            assert meter.measure(widget_id, widgets) == pytest.approx(saver), widget_id
            measured += 1
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        meter.close()
        qt_app.processEvents()
    assert measured == sum(1 for d in get_widget_runtime_descriptors() if d.widget_id != "spotify_visualizer")


def test_meter_never_shows_a_window_and_remeasures_only_on_a_size_change(monkeypatch) -> None:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    meter = OrdinaryPreferredSizeMeter()
    visible = lambda: sum(1 for window in QGuiApplication.topLevelWindows() if window.isVisible())  # noqa: E731
    windows = visible()
    calls: list[str] = []
    measure = meter._measure
    monkeypatch.setattr(meter, "_measure", lambda *args: calls.append(args[0]) or measure(*args))

    first = meter.measure("weather", widgets)
    placed = deepcopy(widgets)
    placed["weather"].update(position="Bottom Left", monitor="2", margin=5)
    placed["custom_layout"] = {"version": 1, "displays": {}}
    assert meter.measure("weather", placed) == first
    assert calls == ["weather"]

    larger = deepcopy(widgets)
    larger["weather"]["font_size"] = int(widgets["weather"]["font_size"]) + 12
    assert meter.measure("weather", larger) != first
    assert calls == ["weather", "weather"]
    assert visible() == windows  # its layout window is bound to a render control, never shown
    meter.close()


@pytest.mark.qt
def test_arrange_projection_is_the_saver_presenters_stacked_placement(qt_app) -> None:
    widgets = {
        "family_activation": _families("clocks", "weather", "system_stats"),
        "global": {"stacking_enabled": True},
        # TEST INPUT: four cards on one corner of a small display must spill/shrink.
        "clock": {"enabled": True, "monitor": "ALL", "position": "Top Right", "display_mode": "analog"},
        "clock2": {"enabled": True, "monitor": "ALL", "position": "Top Right"},
        "weather": {"enabled": True, "monitor": "ALL", "position": "Top Right"},
        "system_stats": {"enabled": True, "monitor": "ALL", "position": "Top Right"},
    }
    adapters = (ClockFamilyAdapter(), WeatherFamilyAdapter(), SystemStatsFamilyAdapter())
    bounds = OverlayWidgetGeometry(0.0, 0.0, 1280.0, 720.0)
    runtime, factory = _make_runtime(qt_app, 302)
    presenter = QuickDisplayPresenter(runtime, adapters=adapters)
    meter = OrdinaryPreferredSizeMeter(adapters)
    try:
        built = presenter.bind_families(
            widgets_config=widgets,
            display_bounds=bounds,
            shadow_values=asdict(ShadowSettings.from_widgets_map(widgets)),
        )
        assert set(built) == {"clock", "clock2", "weather", "system_stats"}
        projected = project_authored_display_layout(
            widgets,
            display_size=(1280, 720),
            ordinary=[(wid, meter.measure(wid, widgets)) for wid in ordinary_instance_order(widgets, adapters)],
        )
        for widget_id in built:
            saver = presenter.geometry_for(widget_id)
            placed = projected[widget_id]
            assert (saver.x, saver.y, saver.width, saver.height) == pytest.approx(
                (placed.x, placed.y, placed.width, placed.height)
            ), widget_id
        # The oracle really exercised spill: the cards did not all keep the corner.
        assert len({(round(projected[w].x), round(projected[w].y)) for w in built}) == len(built)

        display = ArrangeDisplay("screen:parity", ("screen:parity",), QRect(0, 0, 1280, 720), "1")
        model = ArrangeModel(widgets, (display,), meter=meter)
        for item in model.session.items():
            saver = presenter.geometry_for(item.model_identity)
            shown = item.current_global_rect
            assert abs(shown.x() - saver.x) <= 0.5 and abs(shown.y() - saver.y) <= 0.5, item.model_identity
            assert abs(shown.width() - saver.width) <= 0.5 and abs(shown.height() - saver.height) <= 0.5
    finally:
        presenter.retire()
        runtime.close_runtime()
        factory.deleteLater()
        meter.close()
        qt_app.processEvents()


def test_visualizer_docks_under_media_and_global_custom_keeps_it_on_medias_slot() -> None:
    # TEST INPUT sizes/positions; the placement rules are the saver's.
    widgets = {
        "media": {"position": "Top Left", "margin": 20},
        "weather": {"position": "Top Left", "margin": 20},
    }
    ordinary = [("weather", (600.0, 107.0)), ("media", (600.0, 310.0))]
    placed = project_authored_display_layout(
        widgets, display_size=(1920, 1080), ordinary=ordinary, visualizer_size=(420.0, 280.0)
    )
    media, visualizer, weather = placed["media"], placed["spotify_visualizer"], placed["weather"]
    assert (media.x, media.y) == (20.0, 20.0)  # Media is held; others move around it
    assert (visualizer.x, visualizer.y) == (media.x, media.y + media.height + VISUALIZER_MEDIA_GAP)
    rects = [QRect(round(p.x), round(p.y), round(p.width), round(p.height)) for p in (media, visualizer, weather)]
    assert not any(_intersects(a, b) for i, a in enumerate(rects) for b in rects[i + 1:])

    # One effective Custom route makes CUSTOM global: no docking, Media's plain slot.
    widgets["weather"]["position"] = "Custom"
    placed = project_authored_display_layout(
        widgets, display_size=(1920, 1080), ordinary=ordinary, visualizer_size=(420.0, 280.0)
    )
    assert (placed["spotify_visualizer"].x, placed["spotify_visualizer"].y) == (
        placed["media"].x, placed["media"].y
    )


def _reported_layout() -> tuple[dict, ArrangeDisplay]:
    """TEST INPUT shaped like the reported wizard run: Media+Visualizer, two Reddit cards."""

    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = _families("media", "visualizers", "reddit")
    widgets["media"].update(enabled=True, position="Top Left", monitor="ALL")
    widgets["spotify_visualizer"]["enabled"] = True
    widgets["reddit"].update(enabled=True, position="Bottom Right", monitor="ALL")
    widgets["reddit2"].update(enabled=True, position="Bottom Right", monitor="ALL")
    return widgets, ArrangeDisplay("screen:tv", ("screen:tv",), QRect(0, 0, 2560, 1440), "1")


def _saver_rect(widget_id: str, committed: dict, display: ArrangeDisplay, meter) -> QRect:
    """Where the saver resolves one committed content-sized entry."""

    bucket = load_custom_layout_map(committed)["displays"][display.identity]
    profile = (
        get_visualizer_layout_profile(str(committed["spotify_visualizer"]["mode"]))
        if widget_id == "spotify_visualizer" else "default"
    )
    entry = deserialize_custom_layout_entry(
        widget_id, profile, get_widget_layout_variant_payload(bucket, widget_id, profile)
    )
    assert entry.size_payload["_size_from_content"] is True, widget_id
    size = QSize(display.geometry.width(), display.geometry.height())
    if widget_id == "spotify_visualizer":
        payload = entry.size_payload
        return resolve_content_sized_rect(
            entry.rect, payload["_placement_anchor"], (payload["width"], payload["height"]), size
        )
    bounds = OverlayWidgetGeometry(0.0, 0.0, float(size.width()), float(size.height()))
    geometry = resolve_overlay_geometry_policy(widget_id, committed, committed_entry=entry).resolve(
        meter.measure(widget_id, committed), bounds
    )
    return QRect(round(geometry.x), round(geometry.y), round(geometry.width), round(geometry.height))


def test_arrange_apply_lands_every_widget_where_the_canvas_showed_it() -> None:
    widgets, display = _reported_layout()
    model = ArrangeModel(widgets, (display,))
    shown = {item.model_identity: QRect(item.current_global_rect) for item in model.session.items()}
    assert set(shown) == {"media", "spotify_visualizer", "reddit", "reddit2"}
    # The canvas shows the saver's authored layout: docked, spilled, no overlap.
    assert shown["spotify_visualizer"].top() > shown["media"].bottom()
    assert not _intersects(shown["reddit"], shown["reddit2"])

    reddit2 = next(item for item in model.session.items() if item.model_identity == "reddit2")
    model.move(reddit2.source_key, shown["reddit2"].translated(0, -12), snap=False)
    shown["reddit2"] = QRect(reddit2.current_global_rect)
    committed = model.apply()

    # Apply saved the whole canvas (CUSTOM is global), so nothing falls back to
    # a plain anchor, and the saver resolves every box where it was shown.
    landed = {widget_id: _saver_rect(widget_id, committed, display, model._meter) for widget_id in shown}
    for widget_id, rect in landed.items():
        assert abs(rect.x() - shown[widget_id].x()) <= 1 and abs(rect.y() - shown[widget_id].y()) <= 1, widget_id
        assert abs(rect.width() - shown[widget_id].width()) <= 1, widget_id
        assert abs(rect.height() - shown[widget_id].height()) <= 1, widget_id
    boxes = list(landed.values())
    assert not any(_intersects(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])


def test_viewing_or_loading_an_authored_slot_commits_nothing() -> None:
    widgets, display = _reported_layout()
    from core.settings.layout_slots import save_layout_slot

    assert save_layout_slot(widgets, "3") is True
    model = ArrangeModel(widgets, (display,))
    assert model.load_slot("3") is True
    committed = model.apply()
    assert load_custom_layout_map(committed)["displays"] == {}


def test_a_reset_widget_stays_authored_and_shows_where_the_saver_puts_it() -> None:
    widgets, display = _reported_layout()
    authored_position = widgets["reddit"]["position"]
    model = ArrangeModel(widgets, (display,))
    items = {item.model_identity: item for item in model.session.items()}
    model.move(items["reddit2"].source_key, items["reddit2"].current_global_rect.translated(-40, 0), snap=False)
    model.reset(items["reddit"].source_key)

    # The rest of the canvas will be committed, so CUSTOM is global and the
    # saver keeps the reset card on its plain anchor.
    size = model._meter.measure("reddit", widgets)
    plain = resolve_overlay_geometry_policy("reddit", widgets).resolve(
        size, OverlayWidgetGeometry(0.0, 0.0, 2560.0, 1440.0)
    )
    assert items["reddit"].current_global_rect == QRect(round(plain.x), round(plain.y), round(plain.width), round(plain.height))

    committed = model.apply()
    bucket = load_custom_layout_map(committed)["displays"][display.identity]
    assert "reddit" not in bucket
    assert {"media", "spotify_visualizer", "reddit2"} <= set(bucket)
    assert committed["reddit"]["position"] == authored_position


def _clock_face_widgets() -> dict:
    """TEST INPUT: the base Clock's analogue face, a secondary clock that inherits it."""

    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = _families("clocks")
    widgets["clock"].update(enabled=True, display_mode="analog", position="Top Right", monitor="ALL")
    widgets["clock2"].update(enabled=True, display_mode="digital", position="Bottom Right", monitor="ALL")
    widgets["clock3"]["enabled"] = False
    return widgets


def test_arrange_uses_the_savers_clock_face_including_inheritance() -> None:
    from rendering.quick.custom_layout_hydration import clock_geometry_variant

    widgets = _clock_face_widgets()
    display = ArrangeDisplay("screen:clock", ("screen:clock",), QRect(0, 0, 1707, 960), "1")
    model = ArrangeModel(widgets, (display,))
    variants = {item.model_identity: item.source_key.geometry_variant for item in model.session.items()}
    # A secondary clock presents the base Clock's face, whatever its own field says.
    assert variants == {
        "clock": clock_geometry_variant(widgets, "clock", display.identity),
        "clock2": clock_geometry_variant(widgets, "clock2", display.identity),
    }
    assert variants["clock2"] == "analog"


class _NoServiceRuntime:
    """Presentation-only build: no provider/service lifetime is created."""

    def __init__(self, runtime):
        self._runtime = runtime

        class _Manager:
            def __init__(self, real):
                self._real = real

            def has_runtime_service(self, _widget_id):
                return False

            def retire_widget_service(self, _widget_id):
                return None

            def __getattr__(self, name):
                return getattr(self._real, name)

        self.widget_runtime_manager = _Manager(runtime.widget_runtime_manager)

    def __getattr__(self, name):
        return getattr(self._runtime, name)


@pytest.mark.qt
def test_a_moved_content_sized_clock_survives_a_saver_restart(qt_app) -> None:
    """Generation start must resolve a Clock entry in the face it presents.

    Resolving the ``default`` variant found nothing for a Clock, so a moved
    content-sized Clock (Arrange, or an Edit move-only Save) snapped back to its
    authored corner on the next start.
    """

    from rendering.quick.custom_layout_hydration import (
        resolve_quick_committed_entry,
        resolve_quick_committed_geometry,
        resolve_quick_custom_entry,
    )

    screen = qt_app.primaryScreen()
    from rendering.custom_layout_contract import get_screen_signature, get_screen_signature_aliases

    display = ArrangeDisplay(get_screen_signature(screen), get_screen_signature_aliases(screen),
                             QRect(screen.geometry()), "1")
    model = ArrangeModel(_clock_face_widgets(), (display,))
    clock2 = next(item for item in model.session.items() if item.model_identity == "clock2")
    moved = clock2.current_global_rect.translated(-400, -200)
    model.move(clock2.source_key, moved, snap=False)
    shown = QRect(clock2.current_global_rect)
    widgets = model.apply()

    assert resolve_quick_custom_entry(widgets, screen, "clock2") is None  # the old lookup
    assert resolve_quick_committed_entry(widgets, screen, "clock2") is not None

    runtime, factory = _make_runtime(qt_app, 303)
    presenter = QuickDisplayPresenter(_NoServiceRuntime(runtime), adapters=(ClockFamilyAdapter(),))
    geo = screen.geometry()
    try:
        presenter.bind_families(
            widgets_config=widgets,
            display_bounds=OverlayWidgetGeometry(0.0, 0.0, float(geo.width()), float(geo.height())),
            shadow_values=asdict(ShadowSettings.from_widgets_map(widgets)),
            committed_rect_resolver=lambda wid: resolve_quick_committed_geometry(widgets, screen, wid),
            committed_entry_resolver=lambda wid: resolve_quick_committed_entry(widgets, screen, wid),
        )
        saver = presenter.geometry_for("clock2")
        local = shown.translated(-geo.x(), -geo.y())
        assert (round(saver.x), round(saver.y)) == (local.x(), local.y())
        assert (round(saver.width), round(saver.height)) == (local.width(), local.height())
    finally:
        presenter.retire()
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


def _edit_unit(qt_app, widgets, generation, factory):
    """A display unit bound exactly as DisplayManager binds one (never shown)."""

    from core.settings.default_contract import require_canonical_default
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.custom_layout_hydration import (
        apply_quick_committed_payloads,
        resolve_quick_committed_entry,
        resolve_quick_committed_geometry,
        resolve_quick_committed_variant_state,
    )
    from rendering.quick.display_unit import create_quick_display_unit

    screen = qt_app.primaryScreen()
    unit = create_quick_display_unit(
        screen=screen, screen_index=0, runtime_generation=generation, scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(),
        adapters=(ClockFamilyAdapter(), WeatherFamilyAdapter(), SystemStatsFamilyAdapter()),
    )
    unit.bind_families(
        widgets_config=widgets,
        shadow_values=require_canonical_default("widgets.shadows"),
        committed_rect_resolver=lambda wid: resolve_quick_committed_geometry(widgets, screen, wid),
        committed_entry_resolver=lambda wid: resolve_quick_committed_entry(widgets, screen, wid),
        committed_variant_state_resolver=lambda wid, variant: (
            resolve_quick_committed_variant_state(widgets, screen, wid, geometry_variant=variant)
            if wid in {"clock", "clock2", "clock3"} else None),
    )
    apply_quick_committed_payloads(unit, widgets)
    return unit


def _unit_rects(unit, screen) -> dict:
    geo = screen.geometry()
    rects = {}
    for wid in unit.presenter.bound_widget_ids:
        g = unit.presenter.geometry_for(wid)
        rects[wid] = QRect(round(g.x + geo.x()), round(g.y + geo.y()), round(g.width), round(g.height))
    return rects


class _EditSettings:
    """The settings surface the Runtime Edit owner reads and saves through."""

    def __init__(self, values):
        self.widgets = deepcopy(values)

    def get_widgets_map(self):
        return deepcopy(self.widgets)

    def set_widgets_map(self, values, *, emit_change=True):
        self.widgets = deepcopy(values)

    def save(self):
        return None

    def get(self, key, default=None):
        return default


def _assert_same(a: dict, b: dict) -> None:
    assert set(a) == set(b)
    for wid in a:
        ra, rb = a[wid], b[wid]
        assert max(abs(ra.x() - rb.x()), abs(ra.y() - rb.y()), abs(ra.width() - rb.width()),
                   abs(ra.height() - rb.height())) <= 1, (wid, ra.getRect(), rb.getRect())


@pytest.mark.qt
def test_runtime_edit_and_arrange_agree_back_and_forth(qt_app, monkeypatch) -> None:
    import rendering.quick.widgets.family_binder as binder
    from rendering.custom_layout_contract import get_screen_signature, get_screen_signature_aliases
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner

    monkeypatch.setattr(binder, "_attach_runtime_service", lambda *_args, **_kwargs: True)  # no services
    widgets = _clock_face_widgets()
    widgets["family_activation"] = _families("clocks", "weather", "system_stats")
    widgets["weather"].update(enabled=True, position="Bottom Left", monitor="ALL")
    widgets["system_stats"].update(enabled=True, position="Middle Left", monitor="ALL")
    screen = qt_app.primaryScreen()
    display = ArrangeDisplay(get_screen_signature(screen), get_screen_signature_aliases(screen),
                             QRect(screen.geometry()), "1")
    factory = QuickSceneFactory()
    meter = OrdinaryPreferredSizeMeter()

    def arranged(config) -> dict:
        return {i.model_identity: QRect(i.current_global_rect) for i in ArrangeModel(config, (display,), meter=meter).session.items()}

    # Arrange commits the whole canvas; the saver presents exactly that.
    model = ArrangeModel(widgets, (display,), meter=meter)
    first = model.session.items()[0]
    model.move(first.source_key, first.current_global_rect.translated(-60, 40), snap=False)
    widgets = model.apply()
    unit = _edit_unit(qt_app, widgets, 610, factory)
    owner = None
    try:
        start = _unit_rects(unit, qt_app.primaryScreen())
        _assert_same(arranged(widgets), start)

        # Runtime Edit: wheel, side drag and a move through the owner's own seams.
        settings = _EditSettings(widgets)
        owner = QuickCustomLayoutOwner(settings_manager=settings, participants_provider=lambda: (unit,),
                                       visualizer_provider=lambda: (None, None), reload_request=lambda _k: None,
                                       live_config_commit=lambda _w: None)
        assert owner.start() is True
        items = {i.model_identity: i for i in owner.session.items()}
        owner.resize_wheel(items["weather"], 120)
        stats = items["system_stats"]
        cursor = QPoint(stats.current_global_rect.right(), stats.current_global_rect.center().y())
        width_before = stats.current_global_rect.width()
        assert owner.begin_resize(stats, "right", cursor)
        owner.update_resize(stats, "right", cursor + QPoint(30, 0), True)
        widened = stats.current_global_rect.width() - width_before
        clock2 = items["clock2"]
        proposed = clock2.current_global_rect.translated(-50, -30)
        clock2.set_geometry(owner.resolve_move(clock2, proposed, proposed.center()))
        owner.session.notify_item_changed(clock2)
        assert owner.save() is True
        owner.retire()
        owner = None
        widgets = deepcopy(settings.widgets)
        edited = _unit_rects(unit, qt_app.primaryScreen())
        _assert_same(arranged(widgets), edited)  # Arrange opens on exactly what Edit saved

        # Arrange takes the changes back with its own operations.
        model = ArrangeModel(widgets, (display,), meter=meter)
        keys = {i.model_identity: i.source_key for i in model.session.items()}
        model.move(keys["clock2"], QRect(start["clock2"].topLeft(), start["clock2"].size()), snap=False)
        model.wheel_scale(keys["weather"], -120)  # Edit's +1 notch, undone by Arrange's -1
        if widened and "right" in model.side_edges(keys["system_stats"]):
            rect = QRect(model.item(keys["system_stats"]).current_global_rect)
            model.resize_edge(keys["system_stats"], "right", rect, QPoint(-widened, 0))
        shown = {i.model_identity: QRect(i.current_global_rect) for i in model.session.items()}
        widgets = model.apply()
        unit.retire()
        qt_app.processEvents()
        unit = _edit_unit(qt_app, widgets, 611, factory)  # a fresh saver generation
        rebuilt = _unit_rects(unit, qt_app.primaryScreen())
        _assert_same(shown, rebuilt)
        assert rebuilt["clock2"] == start["clock2"]  # a move returns exactly
        # Both editors keep the top-centre when scaling, so the card comes back
        # to where it was, not just to its size (rounding: 1 px).
        _assert_same({"weather": rebuilt["weather"]}, {"weather": start["weather"]})
    finally:
        if owner is not None:
            owner.retire()
        unit.retire()
        factory.deleteLater()
        meter.close()
        qt_app.processEvents()


def _edit_gesture(owner, item, kind, arg, delta) -> None:
    if kind == "wheel":
        owner.resize_wheel(item, arg)
        return
    cursor = item.current_global_rect.center()
    assert owner.begin_resize(item, arg, cursor)
    owner.update_resize(item, arg, cursor + QPoint(*delta), True)


def _arrange_gesture(model, key, kind, arg, delta) -> None:
    if kind == "wheel":
        model.wheel_scale(key, arg)
    elif kind == "corner":
        model.corner_resize(key, arg, model.resize_origin(key), QPoint(*delta))
    else:
        model.resize_edge(key, arg, QRect(model.item(key).current_global_rect), QPoint(*delta))


@pytest.mark.qt
def test_the_same_size_gesture_saves_the_same_layout_in_runtime_edit_and_arrange(qt_app, monkeypatch) -> None:
    """Arrange sizes exactly as Runtime Edit: pivot, limits, payload and explicit box.

    Each gesture runs once through the Edit owner's own seams (committed with
    its Save's commit owner) and once through Arrange, from one saved layout.
    The saver reads nothing else, so identical maps mean identical cards.
    """

    import rendering.quick.widgets.family_binder as binder
    from rendering.custom_layout_commit import commit_custom_session
    from rendering.custom_layout_contract import get_screen_signature, get_screen_signature_aliases
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner

    monkeypatch.setattr(binder, "_attach_runtime_service", lambda *_args, **_kwargs: True)  # no services
    widgets = _clock_face_widgets()
    widgets["family_activation"] = _families("clocks", "weather", "system_stats")
    widgets["weather"].update(enabled=True, position="Bottom Left", monitor="ALL")
    widgets["system_stats"].update(enabled=True, position="Middle Left", monitor="ALL")
    screen = qt_app.primaryScreen()
    display = ArrangeDisplay(get_screen_signature(screen), get_screen_signature_aliases(screen),
                             QRect(screen.geometry()), "1")
    factory = QuickSceneFactory()
    meter = OrdinaryPreferredSizeMeter()
    model = ArrangeModel(widgets, (display,), meter=meter)
    first = model.session.items()[0]
    model.move(first.source_key, first.current_global_rect.translated(-60, 40), snap=False)
    saved = model.apply()
    unit = _edit_unit(qt_app, saved, 620, factory)
    gestures = {
        "wheel up": ("weather", [("wheel", 120, None)]),
        "wheel down": ("clock", [("wheel", -240, None)]),
        "corner": ("weather", [("corner", "bottom_right", (40, 25))]),
        "opposite corner": ("system_stats", [("corner", "top_left", (-30, -10))]),
        "width": ("system_stats", [("side", "right", (47, 0))]),
        "height": ("weather", [("side", "bottom", (0, -35))]),
        "width, then scale": ("system_stats", [("side", "right", (50, 0)), ("wheel", 120, None),
                                                ("corner", "top_right", (-20, 30))]),
    }
    try:
        for label, (widget_id, steps) in gestures.items():
            owner = QuickCustomLayoutOwner(settings_manager=_EditSettings(saved), participants_provider=lambda: (unit,),
                                           visualizer_provider=lambda: (None, None), reload_request=lambda _k: None,
                                           live_config_commit=lambda _w: None)
            assert owner.start() is True
            try:
                item = next(i for i in owner.session.items() if i.model_identity == widget_id)
                for kind, arg, delta in steps:
                    _edit_gesture(owner, item, kind, arg, delta)
                edited = deepcopy(saved)
                commit_custom_session(edited, owner.session, owner._descriptors, owner._bindings)
            finally:
                owner.cancel()
            arrange = ArrangeModel(saved, (display,), meter=meter)
            key = next(i.source_key for i in arrange.session.items() if i.model_identity == widget_id)
            for kind, arg, delta in steps:
                _arrange_gesture(arrange, key, kind, arg, delta)
            arranged = arrange.apply()
            assert load_custom_layout_map(arranged) == load_custom_layout_map(edited), label
    finally:
        unit.retire()
        factory.deleteLater()
        meter.close()
        qt_app.processEvents()


@pytest.mark.qt
def test_a_never_placed_layout_saves_the_same_in_runtime_edit_and_arrange(qt_app, monkeypatch) -> None:
    """Untouched cards keep following their content in both editors.

    Edit's Save writes every card; a fixed box taken while a card is still
    loading (Weather before its first data) would later shrink the card inside
    it. Both editors save a never-placed card as a content-sized placement.
    """

    import rendering.quick.widgets.family_binder as binder
    from rendering.custom_layout_commit import commit_custom_session
    from rendering.custom_layout_contract import get_screen_signature, get_screen_signature_aliases
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner

    monkeypatch.setattr(binder, "_attach_runtime_service", lambda *_args, **_kwargs: True)  # no services
    widgets = _clock_face_widgets()
    widgets["family_activation"] = _families("clocks", "weather", "system_stats")
    widgets["weather"].update(enabled=True, position="Bottom Left", monitor="ALL")
    widgets["system_stats"].update(enabled=True, position="Middle Left", monitor="ALL")
    screen = qt_app.primaryScreen()
    display = ArrangeDisplay(get_screen_signature(screen), get_screen_signature_aliases(screen),
                             QRect(screen.geometry()), "1")
    factory = QuickSceneFactory()
    meter = OrdinaryPreferredSizeMeter()
    unit = _edit_unit(qt_app, widgets, 630, factory)
    try:
        owner = QuickCustomLayoutOwner(settings_manager=_EditSettings(widgets), participants_provider=lambda: (unit,),
                                       visualizer_provider=lambda: (None, None), reload_request=lambda _k: None,
                                       live_config_commit=lambda _w: None)
        assert owner.start() is True
        try:
            edited = deepcopy(widgets)
            commit_custom_session(edited, owner.session, owner._descriptors, owner._bindings)
        finally:
            owner.cancel()
        model = ArrangeModel(widgets, (display,), meter=meter)
        first = model.session.items()[0]
        origin = QRect(first.current_global_rect)
        model.move(first.source_key, origin.translated(1, 0), snap=False)
        model.move(first.source_key, origin, snap=False)
        arranged = model.apply()
        assert load_custom_layout_map(arranged) == load_custom_layout_map(edited)
        for variants in load_custom_layout_map(edited)["displays"][display.identity].values():
            for entry in variants.values():
                assert entry["size_payload"].get("_size_from_content") is True
    finally:
        unit.retire()
        factory.deleteLater()
        meter.close()
        qt_app.processEvents()


_POLISH_TRUTH = r'''
import json, os, sys
from copy import deepcopy
from dataclasses import asdict
os.environ["QT_QPA_PLATFORM"] = "offscreen"          # a shown window is never visible here
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
os.environ["QT_QUICK_BACKEND"] = "software"
sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication
app = QApplication([])
from ui.font_registration import ensure_custom_fonts
ensure_custom_fonts()
from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.models import ShadowSettings
from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.widgets.host import apply_overlay_card_style
from rendering.quick.widgets.preferred_size_measurement import OrdinaryPreferredSizeMeter
from rendering.quick.widgets.registry import ordinary_widget_family_component
meter = OrdinaryPreferredSizeMeter()
engine = QQmlEngine(); engine.addImportPath(str(quick_qml_root()))
window = QQuickWindow(); window.resize(3840, 2160); window.show()
components = {}
def shown(widget_id, widgets):
    adapter = next(a for a in meter.adapters if a.presentation_component(widget_id))
    descriptor = ordinary_widget_family_component(adapter.presentation_component(widget_id))
    model = adapter.presentation_model(widget_id=widget_id, widgets_config=widgets,
                                       shadow_values=asdict(ShadowSettings.from_widgets_map(widgets)))
    prepare = getattr(adapter, "prepare_measurement", None)
    if callable(prepare):
        prepare(model)
    component = components.setdefault(descriptor.family_id, QQmlComponent(
        engine, QUrl.fromLocalFile(str(quick_qml_root() / descriptor.qml_filename))))
    item = component.createWithInitialProperties({descriptor.model_property: model})
    item.setParent(engine); model.setParent(item)
    apply_overlay_card_style(item, adapter.presentation_card_style(model))
    item.setParentItem(window.contentItem())
    for _ in range(6):
        item.setWidth(item.property("preferredContentWidth")); item.setHeight(item.property("preferredContentHeight"))
        app.processEvents()
    return [round(item.property("preferredContentWidth"), 1), round(item.property("preferredContentHeight"), 1)]
base = deepcopy(DEFAULT_SETTINGS["widgets"])
base["weather"]["location"] = "TEST INPUT"
cases = {"weather": deepcopy(base), "reddit": deepcopy(base)}
cases["weather_5day"] = deepcopy(base); cases["weather_5day"]["weather"]["show_five_day_forecast"] = True
cases["clock_digital"] = deepcopy(base); cases["clock_digital"]["clock"].update(display_mode="digital", show_date=True)
out = {}
for name, widgets in cases.items():
    widget_id = name.split("_")[0]
    out[name] = {"meter": [round(v, 1) for v in meter.measure(widget_id, widgets)], "shown": shown(widget_id, widgets)}
print(json.dumps(out)); sys.stdout.flush(); os._exit(0)
'''


def test_meter_matches_a_polished_shown_card_including_data_driven_sizes(tmp_path) -> None:
    """Positioners size themselves only when polished; the truth is a card in a shown window.

    Runs on the offscreen platform, where a shown window is never visible.
    Weather's rows (and its 5-day band) are laid out by a Column: unpolished,
    the card reads 119 px tall instead of the 250/374 px the saver shows.
    """

    import json
    import subprocess
    import sys
    from pathlib import Path

    script = tmp_path / "polish_truth.py"
    script.write_text(_POLISH_TRUTH, encoding="utf-8")
    root = str(Path(__file__).resolve().parents[1])
    result = subprocess.run([sys.executable, str(script), root], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=300)
    line = next(l for l in reversed(result.stdout.strip().splitlines()) if l.startswith("{"))
    measured = json.loads(line)
    for name, pair in measured.items():
        assert pair["meter"] == pytest.approx(pair["shown"], abs=0.5), (name, pair)
    # The case the unpolished meter got wrong: data-driven Weather rows.
    assert measured["weather"]["shown"][1] > 119.0
    assert measured["weather_5day"]["shown"][1] > measured["weather"]["shown"][1]


def test_arrange_shows_the_single_visualizer_where_the_saver_admits_it() -> None:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = _families("media", "visualizers")
    widgets["media"].update(enabled=True, position="Top Left", monitor="ALL")
    widgets["spotify_visualizer"]["enabled"] = True
    first = ArrangeDisplay("screen:one", ("screen:one",), QRect(0, 0, 1707, 960), "1")
    second = ArrangeDisplay("screen:two", ("screen:two",), QRect(2560, 0, 2560, 1440), "2")

    # ALL: one Visualizer, on the first shown display (the saver's first participant).
    model = ArrangeModel(widgets, (first, second))
    visualizers = [i for i in model.session.items() if i.model_identity == "spotify_visualizer"]
    assert [v.source_key.display_identity for v in visualizers] == ["screen:one"]
    # A specific route: that display. Adjusting it saves that route for the saver.
    widgets["media"]["monitor"] = "2"
    model = ArrangeModel(widgets, (first, second))
    (visualizer,) = [i for i in model.session.items() if i.model_identity == "spotify_visualizer"]
    assert visualizer.source_key.display_identity == "screen:two"
    model.move(visualizer.source_key, visualizer.current_global_rect.translated(300, 200), snap=False)
    saved = model.apply()
    assert saved["spotify_visualizer"]["position"] == "Custom"
    assert saved["spotify_visualizer"]["monitor"] == "2"


def test_a_display_added_while_arranging_keeps_the_pending_draft() -> None:
    widgets, one = _reported_layout()
    two = ArrangeDisplay("screen:two", ("screen:two",), QRect(2560, 0, 1707, 960), "2")
    for widget_id in ("media", "reddit", "reddit2"):
        widgets[widget_id]["monitor"] = "ALL"
    model = ArrangeModel(widgets, (one,))
    reddit = next(i for i in model.session.items() if i.model_identity == "reddit")
    moved = reddit.current_global_rect.translated(-120, -60)
    model.move(reddit.source_key, moved, snap=False)

    assert model.replace_displays((one, two)) is True
    assert model.pending
    on_one = {i.model_identity: i for i in model.session.items() if i.source_key.display_identity == one.identity}
    on_two = {i.model_identity for i in model.session.items() if i.source_key.display_identity == two.identity}
    assert on_one["reddit"].current_global_rect == moved  # the draft survived
    assert {"media", "reddit", "reddit2"} <= on_two  # the new display shows its widgets
    model.discard()
    assert model.widgets == ArrangeModel(widgets, (one, two)).widgets  # Discard still restores Settings

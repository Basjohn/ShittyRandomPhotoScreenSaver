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
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QGuiApplication

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.models import ShadowSettings
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


def test_meter_is_windowless_and_remeasures_only_on_a_size_change(monkeypatch) -> None:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    meter = OrdinaryPreferredSizeMeter()
    windows = len(QGuiApplication.topLevelWindows())
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
    assert len(QGuiApplication.topLevelWindows()) == windows
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
    entry = deserialize_custom_layout_entry(
        widget_id, "default", get_widget_layout_variant_payload(bucket, widget_id, "default")
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
    assert committed["reddit"]["position"] == "Bottom Right"

"""Capture fixed retained-card pixels and geometry before/after normalization.

Run as a module with --output NEW_DIRECTORY. Uses the real Quick scene/host,
deterministic presentation snapshots and local artwork; no provider is started.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
import subprocess

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer, QSize, QRect, QMetaObject, Qt, qInstallMessageHandler, qVersion
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtWidgets import QApplication

from core.settings.default_contract import require_canonical_default
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.window import QuickDisplayWindow
from rendering.quick.custom_layout_size import capture_quick_size_payload, scale_quick_size_payload
from rendering.widget_descriptors import get_widget_runtime_descriptor

SIZES = (("1.00", 1., 1.), ("0.75", .75, .75), ("0.50", .5, .5),
         ("1.40", 1.4, 1.4), ("2.00", 2., 2.), ("narrow", .75, 1.),
         ("short", 1., .75), ("wide-short", 1.25, .8))
FAMILIES = ("abandonment_issues", "achievement_pulse", "weather")
PROPERTIES = ("preferredContentWidth", "preferredContentHeight", "uniformScaleTransform",
              "presentationScale", "cardShadowVisualX", "cardShadowVisualY",
              "cardShadowVisualWidth", "cardShadowVisualHeight", "interactionGlowX",
              "interactionGlowY", "interactionGlowWidth", "interactionGlowHeight",
              "legacyHorizontalInset", "legacyVerticalInset", "legacyTextInset", "readyContentFitScale")


def settle(milliseconds):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def grab(root):
    result = root.grabToImage(QSize(int(root.width()), int(root.height())))
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    result.ready.connect(loop.quit)
    timeout.start(5000)
    loop.exec()
    timeout.stop()
    return result.image()


def ledger(item):
    records = []
    def visit(node):
        if node.objectName():
            record = {"name": node.objectName(), "x": node.x(), "y": node.y(),
                      "width": node.width(), "height": node.height(), "scale": node.scale(),
                      "visible": node.isVisible()}
            font = node.property("font")
            if font is not None and hasattr(font, "pointSizeF"):
                record["font_point_size"] = font.pointSizeF()
                record["font_pixel_size"] = font.pixelSize()
            records.append(record)
        for child in node.childItems():
            visit(child)
    visit(item)
    return {"properties": {key: item.property(key) for key in PROPERTIES}, "items": records}


def build_card(family, variant, host, artwork_path, image):
    shadows = require_canonical_default("widgets.shadows")
    bounds = OverlayWidgetGeometry(60., 60., 600., 400.)
    if family == "weather":
        from rendering.quick.widgets.weather import WeatherPresentationConfig, WeatherPresentationStyle, WeatherPresentationModel, RetainedWeatherPresentation
        config = WeatherPresentationConfig.from_mapping({"location": "Cape Town", "font_family": "Arial",
            "show_forecast": True, "show_details_row": True, "show_condition_icon": True})
        if variant == "missing":
            config = replace(config, location="")
        model = WeatherPresentationModel(config, WeatherPresentationStyle.project(config, shadows))
        # Snapshot fixture admission, deliberately no provider/runtime activation.
        model._active = True
        if variant not in ("missing", "loading", "error"):
            model.on_weather_state({"temperature": 22.4, "condition": "partly cloudy",
                "location": "Johannesburg, Gauteng Province" if variant == "long" else "Cape Town",
                "weather_code": 2, "is_day": 1, "precipitation_probability": 17,
                "humidity": 68, "windspeed": 12.6, "forecast": "Tomorrow: 19°C, light rain"}, from_cache=variant == "cached")
        if variant == "error":
            model.on_weather_error("Fixture weather unavailable")
        presentation = RetainedWeatherPresentation(host=host, model=model, geometry=bounds)
    else:
        changes = {"font_family": "Arial"}
        if variant == "no-art":
            changes["show_artwork"] = False
        elif variant == "portrait":
            changes["artwork_shape"] = "portrait"
        if family == "abandonment_issues":
            from rendering.quick.widgets.abandonment_issues import AbandonmentIssuesPresentationConfig, AbandonmentIssuesPresentationStyle, AbandonmentIssuesPresentationModel, RetainedAbandonmentIssuesPresentation
            from widgets.steam_abandonment_preparation import AbandonmentPreparedPresentation
            config = AbandonmentIssuesPresentationConfig.from_widgets_mapping({family: changes})
            model = AbandonmentIssuesPresentationModel(config, AbandonmentIssuesPresentationStyle.project(config, shadows))
            model.activate()
            from core.steam.abandonment_issues import AbandonmentResolved, LAST_PLAYED_VERIFIED
            from widgets.steam_abandonment_models import build_abandonment_view_model
            card = build_abandonment_view_model(AbandonmentResolved(
                status="ok", appid=753640, title="Outer Wilds", playtime_minutes=1080,
                last_played_at=1700000000., last_played_confidence=LAST_PLAYED_VERIFIED,
                inactivity_days=270, queue_position=1, queue_count=5,
                unlocked_achievement_count=5, total_achievement_count=20, latest_unlock_age_days=280,
            ), field_visibility=dict(config.field_visibility), connection_needs_attention=True)
            if variant == "long":
                card = replace(card, title="A very long archived adventure with descenders: gypsy fjords")
            model.on_abandonment_presentation(AbandonmentPreparedPresentation(model=card, artwork=image,
                artwork_identity=str(artwork_path), desaturation_bucket=40), animate=False)
            presentation = RetainedAbandonmentIssuesPresentation(host=host, model=model, geometry=bounds)
        else:
            from rendering.quick.widgets.achievement_pulse import AchievementPulsePresentationConfig, AchievementPulsePresentationStyle, AchievementPulsePresentationModel, RetainedAchievementPulsePresentation
            from widgets.steam_achievement_preparation import AchievementPulsePreparedPresentation
            config = AchievementPulsePresentationConfig.from_widgets_mapping({family: changes})
            model = AchievementPulsePresentationModel(config, AchievementPulsePresentationStyle.project(config, shadows))
            model.activate()
            from core.steam.achievement_pulse import AchievementPulseResolved
            from widgets.steam_card_models import build_achievement_pulse_view_model
            card = build_achievement_pulse_view_model(AchievementPulseResolved(
                status="ok", appid=753640, title="Outer Wilds", selection_label="Recently played",
                unlocked=5, total=20, percent=25., latest_achievement="Beginner's Luck",
                latest_achievements=("Beginner's Luck", "Deep Impact"), playtime_forever_minutes=1080,
            ), connection_needs_attention=True)
            if variant == "long":
                card = replace(card, title="A very long achievement adventure: gypsy fjords")
            model.on_achievement_presentation(AchievementPulsePreparedPresentation(model=card, artwork=image,
                artwork_identity=str(artwork_path), artwork_key="fixture",
                latest_artwork=image, latest_artwork_identity=str(artwork_path), latest_artwork_key="fixture-unlock"), animate=False)
            presentation = RetainedAchievementPulsePresentation(host=host, model=model, geometry=bounds)
    presentation.item.setProperty("fadeOpacity", 1.)
    return presentation


def capture(output, *, families):
    output.mkdir(parents=True, exist_ok=False)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    app = QApplication.instance() or QApplication([])
    artwork_path = output / "fixture.png"
    image = QImage(180, 240, QImage.Format.Format_ARGB32)
    image.fill(QColor("#3e6685"))
    painter = QPainter(image)
    painter.fillRect(20, 30, 140, 65, QColor("#dbb860"))
    painter.fillRect(40, 115, 100, 90, QColor("#669789"))
    painter.end()
    if not image.save(str(artwork_path)):
        raise RuntimeError("Could not save fixture artwork")
    messages = []
    prior_handler = qInstallMessageHandler(lambda kind, context, message: messages.append(str(message)))
    window = QuickDisplayWindow(screen_index=0, runtime_generation=0, screen=app.primaryScreen(),
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False, accepts_focus=False))
    window.setGeometry(80, 80, 1500, 1000)
    factory = QuickSceneFactory()
    scene = QuickSceneController(window=window, factory=factory)
    results = {}
    try:
        QMetaObject.invokeMethod(window, "show", Qt.ConnectionType.QueuedConnection)
        for family in families:
            variants = ("base", "no-art", "portrait", "long") if family != "weather" else ("base", "long", "missing", "loading", "error", "cached")
            for variant in variants:
                card = build_card(family, variant, scene.ordinary_widget_host, artwork_path, image)
                # Allow retained artwork's readiness-gated 340ms reveal to finish.
                settle(750)
                item = card.item
                width = float(item.property("preferredContentWidth"))
                height = float(item.property("preferredContentHeight"))
                if min(width, height) <= 0:
                    raise RuntimeError(f"invalid baseline {family}/{variant}")
                descriptor = get_widget_runtime_descriptor(family)
                payload = capture_quick_size_payload(descriptor, card, QRect(60, 60, int(width), int(height)))
                for label, sx, sy in SIZES:
                    card._retained.apply_custom_layout_size_payload(scale_quick_size_payload(
                        descriptor, payload, min(sx, sy)))
                    item.setWidth(width * sx)
                    item.setHeight(height * sy)
                    window.update()
                    settle(80)
                    pixels = grab(scene.scene_root)
                    if pixels.isNull():
                        raise RuntimeError("Quick capture returned no pixels")
                    case = f"{family}__{variant}__{label}"
                    if not pixels.save(str(output / f"{case}.png")):
                        raise RuntimeError(f"Could not save {case}")
                    results[case] = ledger(item)
                card.retire()
                app.processEvents()
    finally:
        scene.quiesce_for_retirement()
        window.queue_close()
        settle(100)
        factory.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qInstallMessageHandler(prior_handler)
    metadata = {"fixture_version": 1, "qt": qVersion(), "platform": platform.platform(),
        "logical_window": [1500, 1000], "font": "Arial", "graphics_api": "OpenGL"}
    revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1]).stdout.strip()
    (output / "ledger.json").write_text(json.dumps({"dpr": window.devicePixelRatio(),
        "environment": metadata, "revision": revision, "cases": results,
        "qml_messages": messages}, indent=2), encoding="utf-8")
    print(f"Captured {len(results)} cases at DPR {window.devicePixelRatio()}: {output}")
    print(f"Qt messages: {len(messages)}")
    if messages:
        raise RuntimeError("Qt emitted messages; inspect ledger.json before accepting captures")


def compare(before, after, output, *, max_channel_delta=0):
    """Write a pixel/geometry comparison; differences require inspection, never auto-blessing."""
    import numpy as np
    from PIL import Image, ImageChops

    ledgers = [json.loads((path / "ledger.json").read_text(encoding="utf-8"))
               for path in (before, after)]
    for key in ("environment", "dpr"):
        if key not in ledgers[0] or ledgers[0][key] != ledgers[1].get(key):
            raise ValueError(f"Capture {key} mismatch; recapture in the same environment")
    if ledgers[0]["cases"].keys() != ledgers[1]["cases"].keys():
        raise ValueError("Capture case sets differ")
    if any(ledger["qml_messages"] for ledger in ledgers):
        raise ValueError("Capture has Qt messages; resolve them before comparing")
    output.mkdir(parents=True, exist_ok=False)
    rows = {}
    for case in ledgers[0]["cases"]:
        with Image.open(before / f"{case}.png") as left, Image.open(after / f"{case}.png") as right:
            if left.size != right.size:
                raise ValueError(f"Image dimensions differ: {case}")
            difference = ImageChops.difference(left.convert("RGBA"), right.convert("RGBA"))
            delta = np.asarray(difference)
            mask = np.any(delta != 0, axis=2)
            changed = int(np.count_nonzero(mask))
            ys, xs = np.nonzero(mask)
            bounds = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if changed else None
            rows[case] = {"changed_pixels": changed, "difference_bounds": bounds,
                "max_channel_delta": int(delta.max()),
                "pixels_above_tolerance": int(np.count_nonzero(np.any(delta > max_channel_delta, axis=2))),
                "tolerance": max_channel_delta,
                "geometry_equal": ledgers[0]["cases"][case] == ledgers[1]["cases"][case]}
            if changed:
                # Opaque mask also exposes alpha-only drift when viewed on black.
                Image.fromarray((mask * 255).astype("uint8")).save(output / f"{case}__difference.png")
    (output / "comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    normal = [row for case, row in rows.items() if case.endswith("__1.00")]
    print(f"Identical pixels: {sum(row['changed_pixels'] == 0 for row in rows.values())}/{len(rows)}")
    print(f"Identical normal-size pixels: {sum(row['changed_pixels'] == 0 for row in normal)}/{len(normal)}")
    print(f"Normal-size cases exceeding explicit tolerance {max_channel_delta}: {sum(row['pixels_above_tolerance'] > 0 for row in normal)}/{len(normal)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--families", nargs="+", choices=FAMILIES, default=list(FAMILIES))
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--max-channel-delta", type=int, choices=range(256), default=0, metavar="0..255")
    args = parser.parse_args()
    if args.compare:
        compare(*[path.resolve() for path in args.compare], args.output.resolve(), max_channel_delta=args.max_channel_delta)
    else:
        capture(args.output.resolve(), families=args.families)

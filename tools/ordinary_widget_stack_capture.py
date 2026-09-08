"""Real-Quick fixed-snapshot packing review; reuse the maintained resize harness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, Qt, qInstallMessageHandler
from PySide6.QtGui import QImage, QColor
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtWidgets import QApplication

from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.window import QuickDisplayWindow
from rendering.widget_stacking import DisplayStackParticipant, build_display_stack_plan, build_display_auto_scale_plan
from tools.ordinary_widget_resize_capture import FAMILIES, build_card, settle, grab, ledger


def capture(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    app = QApplication.instance() or QApplication([])
    artwork = QImage(180, 240, QImage.Format.Format_ARGB32)
    artwork.fill(QColor("#3e6685"))
    path = output / "fixture.png"
    assert artwork.save(str(path))
    messages = []
    prior = qInstallMessageHandler(lambda _kind, _context, message: messages.append(str(message)))
    window = QuickDisplayWindow(screen_index=0, runtime_generation=91, screen=app.primaryScreen(),
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False, accepts_focus=False))
    window.setGeometry(80, 80, 1500, 1000)
    factory = QuickSceneFactory()
    scene = QuickSceneController(window=window, factory=factory)
    results = {}
    try:
        QMetaObject.invokeMethod(window, "show", Qt.ConnectionType.QueuedConnection)
        cards = {family: build_card(family, "base", scene.ordinary_widget_host, path, artwork)
                 for family in FAMILIES}
        settle(750)
        participants = [DisplayStackParticipant(family, "Top Left", 30, 30,
            round(card.item.property("preferredContentWidth")),
            round(card.item.property("preferredContentHeight")), order, 30)
            for order, (family, card) in enumerate(cards.items())]
        for label, width, height, auto in (
            ("full", 1500, 1000, True), ("crowded_before", 1100, 650, False),
            ("crowded_after", 1100, 650, True), ("restored", 1500, 1000, True),
        ):
            window.setGeometry(80, 80, width, height)
            if auto:
                plan, scales = build_display_auto_scale_plan(participants, eligible_keys=cards,
                    container_width=width, container_height=height)
            else:
                plan = build_display_stack_plan(participants, container_width=width, container_height=height)
                scales = dict.fromkeys(cards, 1.)
            for member in participants:
                placement, scale = plan.placements[member.key], scales[member.key]
                cards[member.key].set_geometry(OverlayWidgetGeometry(placement.desired_x,
                    placement.desired_y, round(member.width * scale), round(member.height * scale)))
            window.update()
            settle(160)
            assert grab(scene.scene_root).save(str(output / f"{label}.png"))
            results[label] = {"budget": [width, height], "all_fit": plan.all_fit,
                "unresolved": plan.unresolved, "scales": scales,
                "cards": {family: ledger(card.item) for family, card in cards.items()}}
    finally:
        scene.quiesce_for_retirement()
        window.queue_close()
        settle(100)
        factory.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qInstallMessageHandler(prior)
    (output / "ledger.json").write_text(json.dumps({"cases": results, "qt_messages": messages}, indent=2), encoding="utf-8")
    print({label: (row["all_fit"], row["scales"]) for label, row in results.items()})
    if messages:
        raise RuntimeError(f"Qt capture warnings: {messages}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    capture(parser.parse_args().output.resolve())

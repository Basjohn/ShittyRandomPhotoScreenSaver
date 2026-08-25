from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _run_fresh_process_probe(probe: str) -> object:
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(
        next(
            line
            for line in reversed(proc.stdout.strip().splitlines())
            if line.startswith(("[", "{"))
        )
    )


def test_widget_package_and_legacy_hosts_do_not_eagerly_import_families() -> None:
    probe = r"""
import json
import sys

import widgets  # noqa: F401
import rendering.widget_manager  # noqa: F401
import rendering.display_widget  # noqa: F401

forbidden = {
    "widgets.weather_widget",
    "widgets.media_widget",
    "widgets.reddit_widget",
    "widgets.spotify_visualizer_widget",
    "widgets.spotify_volume_widget",
    "widgets.mute_button_widget",
    "core.media.media_controller",
    "core.media.spotify_volume",
    "core.media.system_mute",
}
print(json.dumps(sorted(forbidden & set(sys.modules))))
"""

    assert _run_fresh_process_probe(probe) == []


def test_deactivated_media_setup_keeps_all_media_implementations_dormant() -> None:
    probe = r"""
import json
import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QWidget
from core.resources.manager import ResourceManager
from rendering.widget_manager import WidgetManager

class Settings:
    def get_widgets_map(self):
        return {
            "media": {
                "enabled": True,
                "monitor": "ALL",
                "spotify_volume_enabled": True,
                "mute_button_enabled": True,
            },
            "family_activation": {"media": False},
        }

app = QApplication.instance() or QApplication([])
parent = QWidget()
manager = WidgetManager(parent, ResourceManager())
created = manager.setup_all_widgets(Settings(), screen_index=0, thread_manager=None)
forbidden = {
    "rendering.spotify_widget_creators",
    "widgets.media_widget",
    "widgets.media_runtime",
    "widgets.media.display_update",
    "widgets.spotify_visualizer_widget",
    "widgets.spotify_volume_widget",
    "widgets.media_volume_runtime",
    "widgets.mute_button_widget",
    "widgets.system_mute_runtime",
    "core.media.media_controller",
    "core.media.spotify_volume",
    "core.media.system_mute",
}
print(json.dumps({
    "created": sorted(created),
    "forbidden": sorted(forbidden & set(sys.modules)),
}))
manager.cleanup()
parent.deleteLater()
"""

    assert _run_fresh_process_probe(probe) == {"created": [], "forbidden": []}

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


def test_widget_package_import_does_not_eagerly_import_families() -> None:
    probe = r"""
import json
import sys

import widgets  # noqa: F401

forbidden = {
    "widgets.media_widget",
    "widgets.spotify_visualizer_widget",
    "core.media.media_controller",
    "core.media.spotify_volume",
    "core.media.system_mute",
}
print(json.dumps(sorted(forbidden & set(sys.modules))))
"""

    assert _run_fresh_process_probe(probe) == []


def test_common_quick_scene_import_keeps_ordinary_families_dormant() -> None:
    probe = r"""
import json
import sys

import rendering.quick.scene_controller  # noqa: F401

forbidden = {
    "rendering.quick.widgets.clock",
    "rendering.quick.widgets.weather",
    "rendering.quick.widgets.media",
    "rendering.quick.widgets.reddit",
    "rendering.quick.widgets.gmail",
    "widgets.clock_ticker",
    "widgets.weather_runtime",
    "widgets.media_runtime",
    "widgets.media_volume_runtime",
    "widgets.system_mute_runtime",
    "widgets.reddit_runtime",
    "widgets.gmail_runtime",
    "widgets.weather_widget",
    "widgets.media_widget",
    "core.reddit_post_provider",
    "core.gmail.gmail_backend",
    "core.gmail.gmail_client",
    "core.gmail.gmail_imap",
    "core.gmail.gmail_oauth",
    "core.media.media_controller",
    "core.media.spotify_volume",
    "core.media.system_mute",
}
print(json.dumps(sorted(forbidden & set(sys.modules))))
"""

    assert _run_fresh_process_probe(probe) == []


def test_gmail_presentation_import_keeps_runtime_backend_dormant() -> None:
    probe = r"""
import json
import sys

import rendering.quick.widgets.gmail  # noqa: F401

forbidden = {
    "widgets.gmail_runtime",
    "core.gmail.gmail_backend",
    "core.gmail.gmail_imap",
    "core.gmail.gmail_oauth",
    "core.audio.notification_sound",
}
print(json.dumps(sorted(forbidden & set(sys.modules))))
"""

    assert _run_fresh_process_probe(probe) == []

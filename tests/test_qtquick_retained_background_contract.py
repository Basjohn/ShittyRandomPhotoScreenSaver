"""Source contracts for CHK21 steady retained-background ownership."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_native_reveal_readiness_remains_frame_swapped_gated():
    controller = _read("rendering/quick/scene_controller.py")
    telemetry = _read("rendering/quick/render/telemetry.py")
    assert "native_background_active" in controller
    assert "def note_native_background_visibility(" in telemetry
    assert "native_background_active=bool(visible and identity is not None)" in telemetry
    # Retained texture admission alone is not a new GUI show/update loop.
    assert "frameSwapped -> requestUpdate" not in controller
    assert "frameSwapped -> requestUpdate" not in telemetry



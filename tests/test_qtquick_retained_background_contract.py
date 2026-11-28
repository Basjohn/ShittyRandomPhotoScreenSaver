"""Source contracts for CHK21 steady retained-background ownership."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_native_reveal_readiness_remains_frame_swapped_gated():
    controller = _read("rendering/quick/scene_controller.py")
    # N5.2h audit item 1: the presented frame and the background's drawn photo (the native layer's or the degraded
    # node's own fact) are both published from the swap (the deleted Python node's telemetry no longer stands in).
    swapped = controller.split("def _on_frame_swapped", 1)[1].split("\n    def ", 1)[0]
    assert 'changes["frame_presented"] = True' in swapped
    assert 'changes["background_drawn"] = True' in swapped and "background.background_drawn" in swapped
    assert "self._publish_readiness(**changes)" in swapped
    # Retained texture admission alone is not a new GUI show/update loop.
    assert "frameSwapped -> requestUpdate" not in controller
    assert "requestUpdate" not in swapped



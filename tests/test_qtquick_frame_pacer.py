"""Contracts for Qt-owned retained-scene continuous frame demand."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal

from rendering.quick.frame_pacer import QuickFrameDemand, QuickFramePacer, QuickPacerState

ROOT = Path(__file__).resolve().parents[1]


class _Window(QObject):
    frameSwapped = Signal()

    def __init__(self, *, visible: bool = True) -> None:
        super().__init__()
        self.update_request_count = 0
        self._visible = bool(visible)

    def isVisible(self) -> bool:  # noqa: N802 - mirrors QWindow API
        return self._visible

    def requestUpdate(self) -> None:  # noqa: N802 - mirrors QWindow API
        self.update_request_count += 1


def _pacer(target_hz: float = 100.0):
    window = _Window()
    return QuickFramePacer(window, target_hz), window


@pytest.mark.parametrize("rate", (0.0, -1.0, math.inf, -math.inf, math.nan))
def test_target_rate_must_be_finite_and_positive(rate):
    with pytest.raises(ValueError):
        QuickPacerState(rate)


def test_pacer_has_no_python_timer_or_visualizer_demand() -> None:
    source = (ROOT / "rendering" / "quick" / "frame_pacer.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names: set[str] = set()
    referenced_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.Name):
            referenced_names.add(node.id)
    assert "QTimer" not in imported_names
    assert "QTimer" not in referenced_names
    assert "PreciseTimer" not in referenced_names
    for forbidden in ("set_visualizer_active", "set_visualizer_sync"):
        assert forbidden not in source
    assert not hasattr(QuickFrameDemand, "VISUALIZER")



def test_hidden_window_starts_paused_and_resume_seeds_first_real_update() -> None:
    window = _Window(visible=False)
    pacer = QuickFramePacer(window, 60.0)
    pacer.set_transition_active(True)

    assert pacer.describe()["paused"] is True
    assert pacer.describe()["update_pending"] is False
    assert window.update_request_count == 0

    window._visible = True
    assert pacer.resume() is True
    assert window.update_request_count == 1
    assert pacer.describe()["update_pending"] is True

def test_first_continuous_demand_seeds_one_coalesced_qt_update_and_is_idempotent() -> None:
    pacer, window = _pacer(165.0)
    assert pacer.is_active() is False
    pacer.set_transition_active(True)
    pacer.set_transition_active(True)
    assert pacer.is_active() is True
    assert window.update_request_count == 1
    assert pacer.describe()["update_pending"] is True


def test_frame_swap_chains_exactly_one_successor_while_demand_is_active() -> None:
    pacer, window = _pacer()
    pacer.set_transition_active(True)
    assert window.update_request_count == 1

    window.frameSwapped.emit()
    assert window.update_request_count == 2
    window.frameSwapped.emit()
    assert window.update_request_count == 3

    described = pacer.describe()
    assert described["driver"] == "qt_frame_swapped"
    assert described["frame_swaps"] == 2
    assert described["requested_opportunities"] == 3
    assert described["issued_update_requests"] == 3
    assert described["skipped_deadlines"] == 0


def test_removing_last_demand_stops_chain_after_any_already_queued_frame() -> None:
    pacer, window = _pacer()
    pacer.set_transition_active(True)
    pacer.set_transition_active(False)
    assert pacer.is_active() is False
    assert window.update_request_count == 1

    window.frameSwapped.emit()
    assert window.update_request_count == 1
    assert pacer.describe()["update_pending"] is False


def test_pause_clears_pending_admission_and_resume_seeds_fresh_update() -> None:
    pacer, window = _pacer(60.0)
    pacer.set_transition_active(True)
    assert window.update_request_count == 1
    assert pacer.pause() is True
    assert pacer.pause() is False
    assert pacer.describe()["update_pending"] is False
    assert pacer.demands == QuickFrameDemand.TRANSITION

    # A frameSwapped arriving while paused cannot restart the chain.
    window.frameSwapped.emit()
    assert window.update_request_count == 1

    assert pacer.resume() is True
    assert pacer.resume() is False
    assert window.update_request_count == 2
    assert pacer.describe()["update_pending"] is True


def test_stop_clears_pending_admission_and_allows_reuse() -> None:
    pacer, window = _pacer()
    pacer.set_transition_active(True)
    pacer.stop()
    assert pacer.is_active() is False
    assert pacer.describe()["update_pending"] is False
    pacer.set_transition_active(True)
    assert window.update_request_count == 2


def test_target_retarget_is_diagnostic_metadata_not_a_pacing_clock() -> None:
    pacer, window = _pacer(60.0)
    pacer.set_transition_active(True)
    pacer.set_target_hz(120.0)
    assert pacer.target_hz == 120.0
    assert window.update_request_count == 1
    assert pacer.describe()["interval_ns"] == pytest.approx(round(1_000_000_000 / 120), abs=1)


def test_close_disconnects_chain_and_rejects_new_admission() -> None:
    pacer, window = _pacer()
    pacer.set_transition_active(True)
    pacer.close()
    window.frameSwapped.emit()
    assert window.update_request_count == 1
    assert pacer.describe()["closed"] is True
    with pytest.raises(RuntimeError, match="closed"):
        pacer.set_transition_active(True)


def test_only_supported_nonzero_demand_bits_are_accepted() -> None:
    pacer, _window = _pacer()
    with pytest.raises(ValueError, match="unsupported"):
        pacer.set_demand(QuickFrameDemand.NONE, True)
    with pytest.raises(ValueError, match="unsupported"):
        pacer.set_demand(QuickFrameDemand(8), True)


def test_describe_names_only_actual_continuous_quick_demands() -> None:
    pacer, _window = _pacer()
    pacer.set_transition_active(True)
    assert pacer.describe()["demands"] == ["transition"]

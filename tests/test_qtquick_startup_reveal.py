"""Runtime-shaped contract tests for the coordinated ordinary Quick startup reveal."""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from rendering.quick.startup_reveal import QuickStartupRevealCoordinator


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def test_startup_reveal_primes_zero_then_completes_at_one_once() -> None:
    _app()
    values: list[float] = []
    completions: list[int] = []

    def sink(value: float) -> int:
        values.append(float(value))
        return 3

    reveal = QuickStartupRevealCoordinator(
        runtime_generation=7,
        opacity_sink=sink,
        duration_ms=12,
    )
    reveal.completed.connect(completions.append)

    assert reveal.prime() == 3
    assert values == [0.0]
    assert reveal.start() is True
    assert reveal.start() is False

    loop = QEventLoop()
    reveal.completed.connect(lambda _generation: loop.quit())
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    assert completions == [7]
    assert reveal.is_completed is True
    assert values[-1] == 1.0
    assert all(0.0 <= value <= 1.0 for value in values)


def test_startup_reveal_cancel_never_publishes_completion() -> None:
    _app()
    values: list[float] = []
    completions: list[int] = []

    reveal = QuickStartupRevealCoordinator(
        runtime_generation=9,
        opacity_sink=lambda value: values.append(float(value)) or 2,
        duration_ms=50,
    )
    reveal.completed.connect(completions.append)

    reveal.prime()
    assert reveal.start() is True
    assert reveal.cancel() is True
    assert reveal.cancel() is False

    loop = QEventLoop()
    QTimer.singleShot(80, loop.quit)
    loop.exec()

    assert values[0] == 0.0
    assert completions == []
    assert reveal.is_completed is False


def test_startup_reveal_with_no_ordinary_targets_completes_immediately() -> None:
    _app()
    values: list[float] = []
    completions: list[int] = []

    reveal = QuickStartupRevealCoordinator(
        runtime_generation=11,
        opacity_sink=lambda value: values.append(float(value)) or 0,
        duration_ms=1800,
    )
    reveal.completed.connect(completions.append)

    assert reveal.prime() == 0
    assert reveal.start() is True
    assert completions == [11]
    assert values == [0.0, 1.0]

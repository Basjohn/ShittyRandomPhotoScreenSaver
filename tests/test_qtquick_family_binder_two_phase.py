"""Two-phase display-family assembly ordering (H1 repair bar).

The watchdog stack dumps (H doc §3) showed screen-1 replacement construction
wedged on the GUI thread inside a *later* admitted family's QML component
construction (`QQmlComponent.createWithInitialProperties` via
`RetainedGmailPresentation.__init__`) while an I/O worker ran artwork decode work
for an *earlier*, already-activated family. The binder had interleaved each
family's build with its activation, so provider/native/artwork work started
before later retained-family QML finished constructing.

`OrdinaryFamilyPresentationBinder.bind()` now builds every admitted presentation
first, then activates them — this bar pins that ordering deterministically,
without Qt, and guards the admission/ownership/retirement contracts that must not
regress. It proves activation never overlaps a later family's construction,
activation happens at most once per successful build, skipped/failed builds never
activate, admission order is unchanged, and `retire_all()` still covers every
built presentation exactly once.
"""
from __future__ import annotations

from typing import Any

from rendering.quick.widgets.family_binder import OrdinaryFamilyPresentationBinder
from rendering.quick.widgets.host import OverlayWidgetGeometry


_BOUNDS = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)


class _RuntimeManager:
    def __init__(self, effective_families: set[str]) -> None:
        self._effective = set(effective_families)

    def is_family_effective(self, _config: Any, family_id: str) -> bool:
        return family_id in self._effective


class _Retained:
    def __init__(self, widget_id: str, log: list[tuple[str, str]]) -> None:
        self.widget_id = widget_id
        self._log = log
        self.activate_calls = 0
        self.retire_calls = 0

    def activate(self, _thread_manager: Any) -> None:
        self.activate_calls += 1
        self._log.append(("activate", self.widget_id))

    def retire(self) -> bool:
        self.retire_calls += 1
        self._log.append(("retire", self.widget_id))
        return True


class _Adapter:
    """One fake family adapter recording build/activate order into a shared log."""

    def __init__(
        self,
        family_id: str,
        instance_ids: tuple[str, ...],
        log: list[tuple[str, str]],
        *,
        behavior: dict[str, str] | None = None,
    ) -> None:
        self._family_id = family_id
        self._instance_ids = instance_ids
        self._log = log
        self._behavior = dict(behavior or {})
        self.built: dict[str, _Retained] = {}

    @property
    def family_id(self) -> str:
        return self._family_id

    def enabled_instance_ids(self, _config: Any) -> tuple[str, ...]:
        return self._instance_ids

    def build(self, *, widget_id: str, **_kwargs: Any) -> _Retained | None:
        # The core invariant: no presentation may activate while any family is
        # still being constructed.
        assert not any(event == "activate" for event, _ in self._log), (
            "activation ran during a later family's build: %r" % (self._log,)
        )
        self._log.append(("build", widget_id))
        behavior = self._behavior.get(widget_id)
        if behavior == "raise":
            raise RuntimeError("deliberate build failure for %s" % widget_id)
        if behavior == "none":
            return None
        retained = _Retained(widget_id, self._log)
        self.built[widget_id] = retained
        return retained


def _binder(
    adapters: tuple[_Adapter, ...],
    runtime_manager: _RuntimeManager,
    log: list[tuple[str, str]],
    *,
    screen_index: int = 0,
    thread_manager: Any = object(),
    no_geometry: frozenset[str] = frozenset(),
) -> OrdinaryFamilyPresentationBinder:
    def _geometry(widget_id: str) -> OverlayWidgetGeometry | None:
        if widget_id in no_geometry:
            return None
        return OverlayWidgetGeometry(120.0, 90.0, 300.0, 160.0)

    return OrdinaryFamilyPresentationBinder(
        host=object(),
        runtime_manager=runtime_manager,
        geometry_resolver=_geometry,
        display_bounds=_BOUNDS,
        display_identity="screen:a",
        screen_index=screen_index,
        shadow_values={},
        thread_manager=thread_manager,
        adapters=adapters,
    )


def test_all_admitted_families_build_before_any_activation() -> None:
    log: list[tuple[str, str]] = []
    adapters = (
        _Adapter("alpha", ("a",), log),
        _Adapter("beta", ("b",), log),
        _Adapter("gamma", ("c",), log),
    )
    rm = _RuntimeManager({"alpha", "beta", "gamma"})

    binder = _binder(adapters, rm, log)
    built = binder.bind({})

    assert built == ("a", "b", "c")
    # Every build precedes every activation, in stable order.
    assert log == [
        ("build", "a"),
        ("build", "b"),
        ("build", "c"),
        ("activate", "a"),
        ("activate", "b"),
        ("activate", "c"),
    ]
    # Each successful build activates exactly once.
    for adapter in adapters:
        for retained in adapter.built.values():
            assert retained.activate_calls == 1


def test_failed_and_skipped_builds_never_activate() -> None:
    log: list[tuple[str, str]] = []
    # "a" builds fine, "b" returns None (skipped), "c" raises (failed),
    # "d" builds fine. Only a and d may activate, and only after all builds.
    adapters = (
        _Adapter("fam", ("a", "b", "c", "d"), log, behavior={"b": "none", "c": "raise"}),
    )
    rm = _RuntimeManager({"fam"})

    binder = _binder(adapters, rm, log)
    built = binder.bind({})

    assert built == ("a", "d")
    assert log == [
        ("build", "a"),
        ("build", "b"),
        ("build", "c"),
        ("build", "d"),
        ("activate", "a"),
        ("activate", "d"),
    ]


def test_non_effective_family_and_excluded_route_are_not_built_or_activated() -> None:
    log: list[tuple[str, str]] = []
    adapters = (
        _Adapter("on", ("a",), log),
        _Adapter("off", ("x",), log),  # family not effective -> skipped entirely
        _Adapter("on2", ("b", "nogeo"), log),  # "nogeo" has no geometry -> skipped
    )
    rm = _RuntimeManager({"on", "on2"})

    binder = _binder(adapters, rm, log, no_geometry=frozenset({"nogeo"}))
    built = binder.bind({})

    assert built == ("a", "b")
    assert ("build", "x") not in log
    assert ("build", "nogeo") not in log
    assert log == [
        ("build", "a"),
        ("build", "b"),
        ("activate", "a"),
        ("activate", "b"),
    ]


def test_retire_all_retires_every_built_presentation_exactly_once() -> None:
    log: list[tuple[str, str]] = []
    adapters = (
        _Adapter("fam", ("a", "b", "c"), log, behavior={"b": "none"}),
    )
    rm = _RuntimeManager({"fam"})

    binder = _binder(adapters, rm, log)
    binder.bind({})
    log.clear()

    binder.retire_all()

    # Both successfully built presentations retire exactly once, in reverse order.
    assert log == [("retire", "c"), ("retire", "a")]
    assert binder.is_retired is True

    # Idempotent: a second retire_all does not re-retire.
    log.clear()
    binder.retire_all()
    assert log == []


def test_activation_is_skipped_without_a_thread_manager() -> None:
    log: list[tuple[str, str]] = []
    adapters = (_Adapter("fam", ("a", "b"), log),)
    rm = _RuntimeManager({"fam"})

    binder = _binder(adapters, rm, log, thread_manager=None)
    built = binder.bind({})

    assert built == ("a", "b")
    # Builds still happen and are owned; activation is simply not driven.
    assert log == [("build", "a"), ("build", "b")]

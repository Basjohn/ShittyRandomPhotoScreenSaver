"""Phase E1 — WidgetRuntimeManager owner regression bar.

Covers the responsibility extracted out of the WidgetManager god-object:

- capability *admission* authority (dependency-aware; the single shared-consumer
  accounting query), including compatibility defaults for missing keys;
- capability-*deactivation* reaction dispatch delegating to the E2.7 canonical
  Visualizer failover retirement (retire on ineffective, no-op while effective);
- presentation-neutral runtime *lifecycle routing* over the host registry,
  preserving the E2.7 confirmed-retirement contract (explicit ``cleanup_widget``
  bool) and failing closed once the host edge is released.

These cross the real production seam: ``WidgetRuntimeManager`` is the same owner
``WidgetManager`` constructs and ``_create_factory_widgets`` admits through.
"""
from __future__ import annotations

import pytest

from rendering.widget_runtime_manager import WidgetRuntimeManager
from rendering.multi_monitor_coordinator import get_coordinator


ACTIVE = {"family_activation": {"media": True, "visualizers": True}}
VIS_OFF = {"family_activation": {"media": True, "visualizers": False}}
MEDIA_OFF = {"family_activation": {"media": False, "visualizers": True}}


class _Host:
    """Minimal host exposing the widget registry the owner routes over."""

    def __init__(self, widgets=None):
        self._widgets = widgets or {}


class _Settings:
    def __init__(self, widgets):
        self._widgets = widgets

    def get(self, key, default=None):
        return self._widgets if key == "widgets" else default


class _LifecycleWidget:
    def __init__(self, state="ACTIVE"):
        self.calls: list[str] = []
        self._lifecycle_state = type("S", (), {"name": state})()

    def initialize(self):
        self.calls.append("initialize")

    def activate(self):
        self.calls.append("activate")

    def deactivate(self):
        self.calls.append("deactivate")

    def cleanup(self):
        self.calls.append("cleanup")


# --------------------------------------------------------------------------- #
# Capability admission authority                                              #
# --------------------------------------------------------------------------- #
def test_family_for_widget_resolves_members_and_unknown():
    owner = WidgetRuntimeManager(_Host())
    assert owner.family_for_widget("clock") == "clocks"
    assert owner.family_for_widget("media") == "media"
    assert owner.family_for_widget("spotify_visualizer") == "visualizers"
    assert owner.family_for_widget("reddit2") == "reddit"
    assert owner.family_for_widget("not_a_widget") is None


def test_is_family_activated_missing_keys_resolve_compatibly():
    owner = WidgetRuntimeManager(_Host())
    # Missing activation state -> activated (pre-Quick installs keep features).
    assert owner.is_family_activated({}, "clocks") is True
    assert owner.is_family_activated({"family_activation": {}}, "media") is True
    # Explicit deactivation is honored.
    assert owner.is_family_activated({"family_activation": {"clocks": False}}, "clocks") is False


def test_is_family_effective_honors_media_dependency():
    owner = WidgetRuntimeManager(_Host())
    assert owner.is_family_effective(ACTIVE, "visualizers") is True
    # Media off -> visualizers cannot be effective (shared-consumer accounting).
    assert owner.is_family_effective(MEDIA_OFF, "visualizers") is False
    assert owner.is_family_effective(VIS_OFF, "visualizers") is False
    # Media itself has no dependency and stays effective when activated.
    assert owner.is_family_effective(ACTIVE, "media") is True


def test_admits_widget_family_gate():
    owner = WidgetRuntimeManager(_Host())
    # Ungoverned widget is always admitted.
    assert owner.admits_widget_family("not_a_widget", {"family_activation": {}}) is True
    # Governed + activated -> admitted; governed + deactivated -> denied.
    assert owner.admits_widget_family("clock", {"family_activation": {"clocks": True}}) is True
    assert owner.admits_widget_family("clock", {"family_activation": {"clocks": False}}) is False
    # Admission is activation-only (not dependency-effective): visualizers stays
    # admitted-at-creation even with media off; the dependency cascade is enforced
    # by canonical normalization + the special visualizer subsystem, not this gate.
    assert owner.admits_widget_family("spotify_visualizer", MEDIA_OFF) is True


# --------------------------------------------------------------------------- #
# Capability-deactivation reaction dispatch                                   #
# --------------------------------------------------------------------------- #
@pytest.fixture
def _isolate_failover():
    get_coordinator().clear_visualizer_failover()
    yield
    get_coordinator().clear_visualizer_failover()


def test_handle_capability_change_retires_pending_grace_when_off(_isolate_failover):
    coord = get_coordinator()
    gen = coord.arm_visualizer_grace(intended_index=1, origin_manager=None)
    assert gen != 0
    assert coord.get_visualizer_failover() is not None

    owner = WidgetRuntimeManager(_Host())
    owner.handle_capability_change(_Settings(VIS_OFF))

    # Pending grace retired; generation invalidated so stale callbacks are fenced.
    assert coord.get_visualizer_failover() is None
    assert coord.is_visualizer_failover_generation_current(gen) is False


def test_handle_capability_change_noop_while_effective(_isolate_failover):
    coord = get_coordinator()
    coord.arm_visualizer_grace(intended_index=1, origin_manager=None)
    assert coord.get_visualizer_failover() is not None

    owner = WidgetRuntimeManager(_Host())
    owner.handle_capability_change(_Settings(ACTIVE))

    # Still effective -> not a deactivation -> failover left intact.
    assert coord.get_visualizer_failover() is not None


def test_handle_capability_change_retires_on_media_off(_isolate_failover):
    coord = get_coordinator()
    coord.arm_visualizer_grace(intended_index=1, origin_manager=None)

    owner = WidgetRuntimeManager(_Host())
    owner.handle_capability_change(_Settings(MEDIA_OFF))

    assert coord.get_visualizer_failover() is None


# --------------------------------------------------------------------------- #
# Runtime lifecycle routing                                                   #
# --------------------------------------------------------------------------- #
def test_lifecycle_routing_calls_widget_hooks():
    w = _LifecycleWidget()
    owner = WidgetRuntimeManager(_Host({"a": w}))

    assert owner.initialize_widget("a") is True
    assert owner.activate_widget("a") is True
    assert owner.deactivate_widget("a") is True
    assert owner.cleanup_widget("a") is True
    assert w.calls == ["initialize", "activate", "deactivate", "cleanup"]


def test_lifecycle_routing_missing_widget_returns_false():
    owner = WidgetRuntimeManager(_Host({}))
    assert owner.initialize_widget("missing") is False
    assert owner.cleanup_widget("missing") is False
    assert owner.get_widget_lifecycle_state("missing") is None


def test_cleanup_widget_returns_explicit_bool_for_e2_7():
    class _Explodes:
        def cleanup(self):
            raise RuntimeError("boom")

    owner = WidgetRuntimeManager(_Host({"a": _Explodes()}))
    # A failed cleanup must report False so the E2.7 confirmed-retirement contract
    # can retain the live-owner record rather than orphan it.
    assert owner.cleanup_widget("a") is False


def test_all_variants_count_and_states():
    a, b = _LifecycleWidget("A"), _LifecycleWidget("B")
    owner = WidgetRuntimeManager(_Host({"a": a, "b": b}))

    assert owner.initialize_all_widgets() == 2
    assert owner.deactivate_all_widgets() == 2
    assert owner.get_all_lifecycle_states() == {"a": "A", "b": "B"}


def test_cleanup_releases_host_and_fails_closed():
    owner = WidgetRuntimeManager(_Host({"a": _LifecycleWidget()}))
    owner.cleanup()
    # Host edge released -> registry empty -> routing fails closed, no crash.
    assert owner.initialize_widget("a") is False
    assert owner.initialize_all_widgets() == 0
    assert owner.get_all_lifecycle_states() == {}


# --------------------------------------------------------------------------- #
# Presentation-neutral runtime service (provider/model) ownership             #
# --------------------------------------------------------------------------- #
class _ProviderConsumer:
    """Stub runtime widget that records an injected provider (no QWidget)."""

    def __init__(self):
        self.injected = None

    def set_post_provider(self, provider):
        self.injected = provider


def test_ensure_widget_service_builds_owns_and_injects_reddit_provider():
    # The provider owner exists independently of any QWidget pixel ownership:
    # a plain consumer stub (not a QWidget) receives the built provider, and the
    # owner holds it for independent retirement.
    owner = WidgetRuntimeManager(_Host())
    consumer = _ProviderConsumer()
    service = owner.ensure_widget_service(
        "reddit", consumer, {"reddit": {"provider": "public_json"}}
    )
    assert service is not None
    assert getattr(service, "provider_id", None) == "public_json"
    assert consumer.injected is service
    assert owner.get_widget_service("reddit") is service


def test_ensure_widget_service_none_for_unregistered_widget():
    owner = WidgetRuntimeManager(_Host())
    assert owner.ensure_widget_service("clock", _ProviderConsumer(), {}) is None
    assert owner.get_widget_service("clock") is None


def _install_counting_spec(monkeypatch):
    """Register a spec with retire/build/inject counters for one widget id."""
    from rendering import widget_runtime_services as wrs

    calls = {"build": 0, "inject": 0, "retire": 0}

    def _build(widget_id, widgets_config):
        calls["build"] += 1
        return f"service-{calls['build']}"

    def _inject(widget, service):
        calls["inject"] += 1
        if widget is not None:
            widget.injected = service

    def _retire(service):
        calls["retire"] += 1

    spec = wrs.RuntimeServiceSpec(build=_build, inject=_inject, retire=_retire)
    monkeypatch.setattr(
        wrs, "get_runtime_service_spec", lambda wid: spec if wid == "svc" else None
    )
    return calls


def test_ensure_widget_service_idempotent_retires_prior_before_reowning(monkeypatch):
    calls = _install_counting_spec(monkeypatch)
    owner = WidgetRuntimeManager(_Host())

    first = owner.ensure_widget_service("svc", _ProviderConsumer(), {})
    second = owner.ensure_widget_service("svc", _ProviderConsumer(), {})

    # Re-owning retired the prior service exactly once and owns exactly one now.
    assert first != second
    assert calls["build"] == 2
    assert calls["retire"] == 1
    assert owner.get_widget_service("svc") == second


def test_retire_and_cleanup_release_service_exactly_once(monkeypatch):
    calls = _install_counting_spec(monkeypatch)
    owner = WidgetRuntimeManager(_Host())
    owner.ensure_widget_service("svc", _ProviderConsumer(), {})

    assert owner.retire_widget_service("svc") is True
    assert owner.retire_widget_service("svc") is False  # already gone, no double
    assert calls["retire"] == 1
    assert owner.get_widget_service("svc") is None

    # cleanup() retires any remaining owned services exactly once.
    owner.ensure_widget_service("svc", _ProviderConsumer(), {})
    owner.cleanup()
    assert calls["retire"] == 2
    assert owner.get_widget_service("svc") is None


def test_ensure_widget_service_build_failure_fails_closed(monkeypatch):
    from rendering import widget_runtime_services as wrs

    def _boom(widget_id, widgets_config):
        raise RuntimeError("build failed")

    spec = wrs.RuntimeServiceSpec(build=_boom, inject=lambda w, s: None)
    monkeypatch.setattr(
        wrs, "get_runtime_service_spec", lambda wid: spec if wid == "svc" else None
    )
    owner = WidgetRuntimeManager(_Host())
    assert owner.ensure_widget_service("svc", _ProviderConsumer(), {}) is None
    assert owner.get_widget_service("svc") is None

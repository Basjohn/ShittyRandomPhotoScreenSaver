"""Tests for rendering backend selection and registry."""

from __future__ import annotations

import pytest

from rendering.backends import (
    create_backend_from_settings,
    get_backend_diagnostics,
    get_registry,
    reset_backend_diagnostics,
)
from rendering.backends.opengl.backend import OpenGLRendererBackend
from rendering.backends.software.backend import SoftwareRendererBackend


class StubSettings:
    """Minimal settings provider for backend creation tests."""

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._values = values or {}

    def get(self, key: str, default=None):  # type: ignore[override]
        return self._values.get(key, default)


@pytest.fixture
def registry():
    return get_registry()
def test_opengl_backend_falls_back_to_software(monkeypatch, registry):
    def failing_init(self):
        raise RuntimeError("opengl-test")

    monkeypatch.setattr(OpenGLRendererBackend, "initialize", failing_init)

    settings = StubSettings({"display.render_backend_mode": "opengl"})

    selection = create_backend_from_settings(settings)

    assert isinstance(selection.backend, SoftwareRendererBackend)
    assert selection.fallback_performed is True
    assert selection.resolved_mode == "software"


def test_explicit_software_backend_selection(registry):
    settings = StubSettings({"display.render_backend_mode": "software"})

    selection = create_backend_from_settings(settings)

    assert isinstance(selection.backend, SoftwareRendererBackend)
    assert selection.requested_mode == "software"
    assert selection.fallback_performed is False


def test_backend_diagnostics_counters(monkeypatch, registry):
    reset_backend_diagnostics()

    # Successful OpenGL selection
    monkeypatch.setattr(OpenGLRendererBackend, "initialize", lambda self: None)
    selection = create_backend_from_settings(StubSettings({"display.render_backend_mode": "opengl"}))
    assert selection.resolved_mode == "opengl"

    # OpenGL fallback to software
    monkeypatch.setattr(OpenGLRendererBackend, "initialize", lambda self: (_ for _ in ()).throw(RuntimeError("gl fail")))
    selection = create_backend_from_settings(StubSettings({"display.render_backend_mode": "opengl"}))
    assert selection.resolved_mode == "software"
    assert selection.fallback_performed

    diag = get_backend_diagnostics()
    assert diag.selections["opengl"] >= 1
    assert diag.selections["software"] >= 1
    assert diag.fallbacks["opengl->software"] == 1


def test_unknown_backend_normalizes_to_opengl(registry):
    selection = create_backend_from_settings(StubSettings({"display.render_backend_mode": "bogus"}))

    assert isinstance(selection.backend, OpenGLRendererBackend)
    assert selection.requested_mode == "opengl"
    assert selection.resolved_mode == "opengl"
    assert selection.fallback_performed is False

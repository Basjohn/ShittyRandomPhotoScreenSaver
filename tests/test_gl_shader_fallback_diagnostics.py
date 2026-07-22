import logging
from types import SimpleNamespace

from rendering.gl_compositor_pkg import paint as paint_module
from rendering.gl_compositor_pkg import shader_dispatch


class _FakeCompositor:
    def __init__(self) -> None:
        self._last_shader_path_failure = ""
        self._last_shader_fallback_signature = None
        self._shader_fallback_suppressed_count = 0
        self._gl_disabled_for_session = False
        self._use_shaders = True
        self._current_transition_name = "GLCompositorRainDropsTransition"


def test_shader_path_records_capability_failure_reason():
    comp = _FakeCompositor()
    calls = []

    rendered = shader_dispatch.try_shader_path(
        comp,
        "raindrops",
        object(),
        lambda: False,
        lambda _target: calls.append("paint"),
        target=None,
    )

    assert rendered is False
    assert calls == []
    assert comp._last_shader_path_failure == "raindrops:capability_unavailable"


def test_shader_fallback_log_is_loud_but_bounded(caplog):
    comp = _FakeCompositor()
    comp._last_shader_path_failure = "raindrops:capability_unavailable"

    with caplog.at_level(logging.ERROR, logger=paint_module.logger.name):
        paint_module._log_shader_fallback_once(comp, ["raindrops"])
        paint_module._log_shader_fallback_once(comp, ["raindrops"])

    fallback_records = [
        record for record in caplog.records
        if "[GL PAINT][FALLBACK]" in record.getMessage()
    ]
    assert len(fallback_records) == 1
    assert "active=raindrops" in fallback_records[0].getMessage()
    assert "last_failure=raindrops:capability_unavailable" in fallback_records[0].getMessage()
    assert comp._shader_fallback_suppressed_count == 1


def test_shader_fallback_log_reports_suppressed_previous_on_new_signature(caplog):
    comp = _FakeCompositor()
    comp._last_shader_path_failure = "raindrops:capability_unavailable"

    with caplog.at_level(logging.ERROR, logger=paint_module.logger.name):
        paint_module._log_shader_fallback_once(comp, ["raindrops"])
        paint_module._log_shader_fallback_once(comp, ["raindrops"])
        comp._last_shader_path_failure = "diffuse:texture_prep_failed"
        comp._current_transition_name = "GLCompositorDiffuseTransition"
        paint_module._log_shader_fallback_once(comp, ["diffuse"])

    fallback_records = [
        record for record in caplog.records
        if "[GL PAINT][FALLBACK]" in record.getMessage()
    ]
    assert len(fallback_records) == 2
    assert "suppressed_previous=1" in fallback_records[1].getMessage()
    assert "last_failure=diffuse:texture_prep_failed" in fallback_records[1].getMessage()


def test_texture_prep_failure_does_not_poison_shader_session():
    comp = _FakeCompositor()
    comp._gl_pipeline = object()
    comp._texture_manager = type(
        "TextureManager",
        (),
        {
            "prepare_transition_textures": lambda self, old, new: False,
            "release_transition_textures": lambda self: None,
        },
    )()

    assert shader_dispatch.prepare_pair_textures(comp, object(), object()) is False
    assert comp._gl_disabled_for_session is False
    assert comp._use_shaders is True


def test_transient_shader_exception_retries_and_resets_failure_streak(monkeypatch):
    comp = _FakeCompositor()
    attempts = []

    def paint(_target):
        attempts.append("paint")
        if len(attempts) == 1:
            raise RuntimeError("transient")

    monkeypatch.setattr(shader_dispatch, "paint_qpainter_overlays_gl", lambda _comp: None)

    assert shader_dispatch.try_shader_path(
        comp,
        "wipe",
        object(),
        lambda: True,
        paint,
        target=None,
    ) is False
    assert comp._gl_disabled_for_session is False
    assert comp._use_shaders is True
    assert comp._shader_path_failure_streak == 1

    assert shader_dispatch.try_shader_path(
        comp,
        "wipe",
        object(),
        lambda: True,
        paint,
        target=None,
    ) is True
    assert comp._shader_path_failure_streak == 0


def test_idle_base_shader_uses_committed_texture_without_pixmap_lookup(monkeypatch):
    rendered = []

    class _Pixmap:
        def isNull(self):
            return False

        def width(self):
            return 1920

        def height(self):
            return 1080

    class _Manager:
        def get_committed_texture(self):
            return 77

        def get_cached_texture(self, _pixmap):
            raise AssertionError("idle paint must not rediscover residency by cacheKey")

    class _Helper:
        def render(self, **kwargs):
            rendered.append(kwargs)

    comp = SimpleNamespace(
        _gl_disabled_for_session=False,
        _gl_pipeline=SimpleNamespace(
            initialized=True,
            crossfade_program=5,
            crossfade_uniforms={},
            quad_vao=6,
        ),
        _texture_manager=_Manager(),
        _base_pixmap=_Pixmap(),
    )
    monkeypatch.setattr(shader_dispatch, "gl", object())
    monkeypatch.setattr(shader_dispatch, "get_viewport_size", lambda _comp: (1920, 1080))
    monkeypatch.setattr(
        "rendering.gl_programs.program_cache.get_program_cache",
        lambda: SimpleNamespace(get_program_instance=lambda _identity: _Helper()),
    )

    assert shader_dispatch.paint_idle_base_shader(comp) is True
    assert rendered[0]["old_tex"] == 77
    assert rendered[0]["new_tex"] == 77

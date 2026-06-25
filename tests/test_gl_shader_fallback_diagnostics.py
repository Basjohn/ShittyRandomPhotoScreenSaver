import logging

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

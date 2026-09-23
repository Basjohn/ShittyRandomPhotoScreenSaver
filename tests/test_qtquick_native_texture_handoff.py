"""PR-04 native texture handoff: one owner, lent textures, attributed routes.

When a transition ends, the retained native background adopts the transition's
resident destination GL texture instead of uploading the same pixels again. The
custom node's ``PresentationTextureHost`` stays the only owner and the only
deleter; the native branch holds only a non-owning Qt wrapper. These tests pin
the ownership state machine (mocked GL) and the route selection (fake window);
``test_qtquick_native_texture_handoff_gl.py`` proves pixels and lifetime on a
real threaded OpenGL window.
"""

from __future__ import annotations

import pytest

from rendering.quick.image_state import PresentationImage
from rendering.quick.render import background_image_node, image_textures
from rendering.quick.render.image_textures import PresentationTextureHost
from rendering.quick.render.native_texture_bridge import NativeTextureUnavailable
from rendering.quick.render.telemetry import RenderNodeTelemetry
from rendering.quick.transitions import TransitionRequest, TransitionRun

from tests.test_qtquick_image_textures import _FakeGl


def _image(identity: str, size=(2, 1), value: int = 9) -> PresentationImage:
    width, height = size
    return PresentationImage(
        identity=identity, source_path="synthetic", logical_size=(width, height),
        device_pixel_ratio=1, pixel_size=(width, height), row_stride=width * 4,
        rgba8=bytes((value, value, value, 255)) * (width * height),
    )


def _run(source: PresentationImage, destination: PresentationImage, run_id: int = 1) -> TransitionRun:
    request = TransitionRequest(
        runtime_generation=3, transition_id="crossfade", requested_name="Crossfade",
        selected_from_random=False, duration_ms=1000, direction=None, parameters={},
        source_image=source, destination_image=destination,
    )
    return TransitionRun.start(run_id=run_id, request=request, start_ns=10)


@pytest.fixture
def host(monkeypatch):
    fake_gl = _FakeGl()
    monkeypatch.setattr(image_textures, "gl", fake_gl)
    telemetry = RenderNodeTelemetry(gui_thread_id=1)
    return PresentationTextureHost(telemetry), fake_gl, telemetry


def test_lent_destination_survives_transition_end_and_is_the_next_source(host) -> None:
    owner, gl, telemetry = host
    a, b, c = _image("a", value=10), _image("b", value=20), _image("c", value=30)
    owner.synchronize(a, _run(a, b))               # transition A -> B uploads A(1) and B(2)
    assert owner.lend(b) == 2                      # the native branch adopts B
    owner.release(keep_lent=True)                  # transition branch retires
    assert gl.deleted == [1]                       # A deleted; the lent B is not
    assert owner.lent_identities == {"b"}

    uploads = len(gl.uploads)
    owner.synchronize(b, _run(b, c, run_id=2))     # next transition: B is the source
    assert len(gl.uploads) == uploads + 1          # only C is uploaded; B is reused
    assert owner.lend(c) == 3
    owner.reclaim("b")                             # native branch now shows C
    assert gl.deleted == [1]                       # B is still this run's source
    owner.release(keep_lent=True)
    assert gl.deleted == [1, 2]                    # B deleted once the run retires
    owner.reclaim("c")
    assert gl.deleted == [1, 2, 3]
    snapshot = telemetry.snapshot()
    assert snapshot.image_upload_bytes == snapshot.image_release_bytes
    assert not owner.has_resources


def test_teardown_deletes_lent_textures_exactly_once(host) -> None:
    owner, gl, _telemetry = host
    a, b = _image("a"), _image("b")
    owner.synchronize(a, _run(a, b))
    owner.lend(b)
    owner.release()                                # Settings replacement / exit / invalidation
    assert sorted(gl.deleted) == [1, 2]
    assert not owner.has_resources and not owner.lent_identities
    owner.reclaim("b")                             # a late reclaim is a no-op
    owner.release()
    assert sorted(gl.deleted) == [1, 2]            # never deleted twice


def test_lend_refuses_absent_or_differently_sized_images(host) -> None:
    owner, _gl, _telemetry = host
    a, b = _image("a"), _image("b", size=(2, 1))
    owner.synchronize(a, _run(a, b))
    assert owner.lend(_image("elsewhere")) == 0
    assert owner.lend(_image("b", size=(4, 2))) == 0   # same identity, other display size
    assert owner.lent_identities == frozenset()


def test_reclaim_of_an_unlent_identity_never_deletes(host) -> None:
    owner, gl, _telemetry = host
    a, b = _image("a"), _image("b")
    owner.synchronize(a, _run(a, b))
    owner.reclaim("b")
    owner.reclaim("a")
    assert gl.deleted == []


def test_an_interrupted_transition_leaves_no_texture_behind(host) -> None:
    owner, gl, _telemetry = host
    a, b, c = _image("a"), _image("b"), _image("c")
    owner.synchronize(a, _run(a, b))
    owner.synchronize(a, _run(a, c, run_id=2))     # replaced before it ended
    assert 2 in gl.deleted                         # B is gone
    owner.release()
    assert sorted(gl.deleted) == [1, 2, 3]


def test_many_transitions_keep_at_most_two_live_textures_and_no_backlog(host) -> None:
    owner, gl, telemetry = host
    current = _image("img-0", value=0)
    owner.synchronize(current, None)
    lent = None
    for index in range(1, 51):
        following = _image(f"img-{index}", value=index % 250)
        owner.synchronize(current, _run(current, following, run_id=index))
        assert owner.lend(following)
        if lent is not None:
            owner.reclaim(lent)
        owner.release(keep_lent=True)
        lent, current = following.identity, following
        assert len(owner._records) <= 2 and not owner._pending_deletions
    assert len(gl.uploads) == 51                   # each image uploaded exactly once
    owner.release()
    snapshot = telemetry.snapshot()
    assert snapshot.image_upload_bytes == snapshot.image_release_bytes


# --- Route selection in the retained native branch ---------------------------


class _Texture:
    def __init__(self, name: str) -> None:
        self.name = name


def _image_node_type():
    from PySide6.QtQuick import QSGNode

    class _ImageNode(QSGNode):
        events: list = []
        texture = None

        def setOwnsTexture(self, _owns) -> None:  # noqa: N802
            pass

        def setFiltering(self, _filtering) -> None:  # noqa: N802
            pass

        def setTexture(self, texture) -> None:  # noqa: N802
            self.events.append(("setTexture", texture.name))
            self.texture = texture

        def setSourceRect(self, _rect) -> None:  # noqa: N802
            pass

        def setRect(self, _rect) -> None:  # noqa: N802
            pass

    return _ImageNode


class _Window:
    def __init__(self, events: list) -> None:
        self.events = events
        self.uploads = 0

    def createImageNode(self):  # noqa: N802
        node = _image_node_type()()
        node.events = self.events
        return node

    def createTextureFromImage(self, _image, _options):  # noqa: N802
        self.uploads += 1
        self.events.append(("upload",))
        return _Texture(f"uploaded-{self.uploads}")


class _Custom:
    """Stands in for the custom node's texture host: which images are resident."""

    def __init__(self, events: list, resident: dict) -> None:
        self.events = events
        self.resident = resident

    def lend_presentation_texture(self, image) -> int:
        texture_id = self.resident.get(image.identity, 0)
        if texture_id:
            self.events.append(("lend", image.identity))
        return texture_id

    def reclaim_presentation_texture(self, identity) -> None:
        self.events.append(("reclaim", identity))

    def releaseResources(self) -> None:  # noqa: N802
        self.events.append(("release",))


@pytest.fixture
def retained(qt_app, monkeypatch):
    from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode

    events: list = []
    resident: dict = {}
    wrapped: list = []

    def fake_wrap(texture_id, _window, pixel_size):
        if texture_id == 666:
            raise NativeTextureUnavailable("synthetic: not OpenGL")
        wrapped.append((texture_id, tuple(pixel_size)))
        return _Texture(f"adopted-{texture_id}")

    monkeypatch.setattr(background_image_node, "wrap_gl_texture", fake_wrap)
    window = _Window(events)
    telemetry = RenderNodeTelemetry(gui_thread_id=1)
    node = RetainedBackgroundSceneNode(window=window, telemetry=telemetry, screen_index=0, frame_trace=None)
    node._custom_node = _Custom(events, resident)
    return node, window, telemetry, events, resident, wrapped


def _show(node, image) -> None:
    node._synchronize_native_image(image, logical_size=(2.0, 1.0))


def test_a_resident_destination_is_adopted_without_any_upload(retained) -> None:
    node, window, telemetry, events, resident, wrapped = retained
    _show(node, _image("first"))                     # startup: nothing resident yet
    resident["second"] = 42
    events.clear()
    _show(node, _image("second"))
    assert window.uploads == 1                       # only the startup image was uploaded
    assert wrapped == [(42, (2, 1))]
    assert events == [("lend", "second"), ("setTexture", "adopted-42")]
    snapshot = telemetry.snapshot()
    assert (snapshot.native_background_adopt_count, snapshot.native_background_upload_count) == (1, 1)
    assert snapshot.native_background_last_route == "adopted"


def test_the_previous_adopted_texture_is_reclaimed_only_after_its_wrapper_is_replaced(retained) -> None:
    node, _window, _telemetry, events, resident, _wrapped = retained
    resident.update({"first": 41, "second": 42})
    _show(node, _image("first"))
    events.clear()
    _show(node, _image("second"))
    assert events == [("lend", "second"), ("setTexture", "adopted-42"), ("reclaim", "first")]


def test_fallbacks_upload_and_are_attributed(retained) -> None:
    node, window, telemetry, events, resident, _wrapped = retained
    _show(node, _image("first"))
    snapshot = telemetry.snapshot()
    assert snapshot.native_background_fallback_reason == "not_resident"

    resident["second"] = 666                         # adoption fails on this backend
    events.clear()
    _show(node, _image("second"))
    assert window.uploads == 2
    assert ("reclaim", "second") in events           # the lend is handed back
    snapshot = telemetry.snapshot()
    assert snapshot.native_background_last_route == "uploaded"
    assert snapshot.native_background_fallback_reason == "synthetic: not OpenGL"


def test_adopted_textures_never_enter_the_upload_or_release_byte_ledger(retained) -> None:
    node, _window, telemetry, _events, resident, _wrapped = retained
    resident["only"] = 7
    _show(node, _image("only"))
    node.release_resources()
    snapshot = telemetry.snapshot()
    assert snapshot.image_upload_bytes == 0 and snapshot.image_release_bytes == 0

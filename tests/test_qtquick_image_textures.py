"""Render-owner gates for Phase C1 presentation image textures."""

from __future__ import annotations

import pytest

from rendering.quick.image_state import PresentationImage
from rendering.quick.render import image_textures
from rendering.quick.render.image_textures import ImageTextureOwner
from rendering.quick.render.telemetry import RenderNodeTelemetry


class _FakeGl:
    GL_ACTIVE_TEXTURE = 1
    GL_TEXTURE_BINDING_2D = 2
    GL_UNPACK_ALIGNMENT = 3
    GL_UNPACK_ROW_LENGTH = 4
    GL_UNPACK_SKIP_ROWS = 5
    GL_UNPACK_SKIP_PIXELS = 6
    GL_TEXTURE0 = 100
    GL_TEXTURE_2D = 101
    GL_TEXTURE_MIN_FILTER = 102
    GL_TEXTURE_MAG_FILTER = 103
    GL_TEXTURE_WRAP_S = 104
    GL_TEXTURE_WRAP_T = 105
    GL_LINEAR = 106
    GL_CLAMP_TO_EDGE = 107
    GL_RGBA8 = 108
    GL_RGBA = 109
    GL_UNSIGNED_BYTE = 110

    def __init__(self) -> None:
        self.state = {
            self.GL_ACTIVE_TEXTURE: self.GL_TEXTURE0 + 7,
            self.GL_TEXTURE_BINDING_2D: 77,
            self.GL_UNPACK_ALIGNMENT: 8,
            self.GL_UNPACK_ROW_LENGTH: 31,
            self.GL_UNPACK_SKIP_ROWS: 4,
            self.GL_UNPACK_SKIP_PIXELS: 5,
        }
        self.generated = 0
        self.deleted: list[int] = []
        self.uploads: list[tuple[object, ...]] = []
        self.fail_upload = False
        self.failed_delete_count = 0

    def glGetIntegerv(self, name: int) -> int:
        return self.state[name]

    def glActiveTexture(self, value: int) -> None:
        self.state[self.GL_ACTIVE_TEXTURE] = value

    def glGenTextures(self, _count: int) -> int:
        self.generated += 1
        return self.generated

    def glBindTexture(self, _target: int, texture_id: int) -> None:
        self.state[self.GL_TEXTURE_BINDING_2D] = texture_id

    def glTexParameteri(self, *_args: object) -> None:
        return

    def glPixelStorei(self, name: int, value: int) -> None:
        self.state[name] = value

    def glTexImage2D(self, *args: object) -> None:
        if self.fail_upload:
            raise RuntimeError("synthetic upload failure")
        self.uploads.append(args)

    def glDeleteTextures(self, _count: int, texture_ids: list[int]) -> None:
        if self.failed_delete_count:
            self.failed_delete_count -= 1
            raise RuntimeError("synthetic deletion failure")
        self.deleted.extend(int(texture_id) for texture_id in texture_ids)


def _image(identity: str, rgba8: bytes = b"\x01\x02\x03\xff") -> PresentationImage:
    return PresentationImage(
        identity=identity,
        source_path="synthetic",
        logical_size=(1, 1),
        device_pixel_ratio=1,
        pixel_size=(1, 1),
        row_stride=4,
        rgba8=rgba8,
    )


def test_texture_owner_uploads_by_identity_and_restores_all_unpack_state(monkeypatch):
    fake_gl = _FakeGl()
    monkeypatch.setattr(image_textures, "gl", fake_gl)
    telemetry = RenderNodeTelemetry(gui_thread_id=1)
    owner = ImageTextureOwner(telemetry)
    inherited_state = dict(fake_gl.state)

    assert owner.ensure_uploaded(_image("first")) == 1
    assert owner.ensure_uploaded(_image("first")) == 1
    assert fake_gl.generated == 1
    assert len(fake_gl.uploads) == 1
    assert fake_gl.uploads[0][-1] == b"\x01\x02\x03\xff"
    assert fake_gl.state == inherited_state

    assert owner.ensure_uploaded(_image("second", b"\x05\x06\x07\xff")) == 2
    assert fake_gl.generated == 2
    assert fake_gl.deleted == [1]
    owner.release()

    snapshot = telemetry.snapshot()
    assert fake_gl.deleted == [1, 2]
    assert not owner.has_resources
    assert snapshot.image_upload_count == 2
    assert snapshot.image_release_count == 2
    assert snapshot.image_upload_bytes == snapshot.image_release_bytes == 8
    assert snapshot.pending_image_release_count == 0
    assert snapshot.active_image_identity is None


def test_failed_upload_cleanup_remains_owned_when_deletion_also_fails(monkeypatch):
    fake_gl = _FakeGl()
    fake_gl.fail_upload = True
    fake_gl.failed_delete_count = 1
    inherited_state = dict(fake_gl.state)
    monkeypatch.setattr(image_textures, "gl", fake_gl)
    telemetry = RenderNodeTelemetry(gui_thread_id=1)
    owner = ImageTextureOwner(telemetry)

    with pytest.raises(RuntimeError, match="synthetic upload failure"):
        owner.ensure_uploaded(_image("failed"))

    failed = telemetry.snapshot()
    assert owner.has_resources
    assert failed.image_upload_count == 0
    assert failed.image_release_count == 0
    assert failed.pending_image_release_count == 1
    assert fake_gl.state == inherited_state

    owner.release()
    recovered = telemetry.snapshot()
    assert fake_gl.deleted == [1]
    assert not owner.has_resources
    assert recovered.image_upload_count == 0
    assert recovered.image_release_count == 0
    assert recovered.pending_image_release_count == 0

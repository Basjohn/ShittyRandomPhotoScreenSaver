from dataclasses import FrozenInstanceError

import pytest
from PySide6.QtGui import QImage

from rendering.image_upload_payload import (
    ImageUploadPayload,
    prepare_qimage_upload_payload,
)


def test_payload_owns_immutable_bytes_and_validates_layout():
    source = bytearray(range(16))
    payload = ImageUploadPayload.from_rgba8(2, 2, source)
    source[0] = 255

    assert payload.data == bytes(range(16))
    assert payload.byte_size == 16
    with pytest.raises(FrozenInstanceError):
        payload.width = 3
    with pytest.raises(ValueError, match="stride"):
        ImageUploadPayload.from_rgba8(2, 1, b"\0" * 7, stride=7)
    with pytest.raises(ValueError, match="data length"):
        ImageUploadPayload.from_rgba8(2, 2, b"\0" * 15)


def test_qimage_payload_repacks_odd_width_padded_rows():
    row_1 = bytes((1, 2, 3, 4) * 3)
    row_2 = bytes((5, 6, 7, 8) * 3)
    padded = row_1 + b"PAD!" + row_2 + b"skip"
    image = QImage(
        padded,
        3,
        2,
        16,
        QImage.Format.Format_RGBA8888,
    )

    payload = prepare_qimage_upload_payload(image)

    assert payload.width == 3
    assert payload.height == 2
    assert payload.stride == 12
    assert payload.data == row_1 + row_2


def test_content_identity_is_stable_and_change_sensitive():
    pixels = bytes(range(16))
    first = ImageUploadPayload.from_rgba8(2, 2, pixels, identity_seed="source-a")
    same = ImageUploadPayload.from_rgba8(2, 2, pixels, identity_seed="source-a")
    changed_pixel = ImageUploadPayload.from_rgba8(
        2, 2, pixels[:-1] + b"\xff", identity_seed="source-a"
    )
    changed_dimensions = ImageUploadPayload.from_rgba8(
        1, 4, pixels, identity_seed="source-a"
    )
    changed_seed = ImageUploadPayload.from_rgba8(2, 2, pixels, identity_seed="source-b")

    assert first.content_id == same.content_id
    assert changed_seed.content_id == first.content_id
    assert len(first.content_id) == 64
    assert len(
        {
            first.content_id,
            changed_pixel.content_id,
            changed_dimensions.content_id,
            changed_seed.content_id,
        }
    ) == 3


def test_image_cache_accounts_payload_bytes_without_qt_conversion():
    from utils.image_cache import ImageCache

    cache = ImageCache(max_items=2, max_memory_mb=1)
    payload = ImageUploadPayload.from_rgba8(3, 2, bytes(range(24)))

    cache.put("scaled", payload)

    assert cache.get("scaled") is payload
    assert cache.memory_usage() == payload.byte_size


class _FakeGL:
    GL_PIXEL_UNPACK_BUFFER = 1
    GL_STREAM_DRAW = 2
    GL_TEXTURE_2D = 3
    GL_UNPACK_ALIGNMENT = 4
    GL_TEXTURE_MIN_FILTER = 5
    GL_TEXTURE_MAG_FILTER = 6
    GL_LINEAR = 7
    GL_TEXTURE_WRAP_S = 8
    GL_TEXTURE_WRAP_T = 9
    GL_CLAMP_TO_EDGE = 10
    GL_RGBA8 = 11
    GL_RGBA = 12
    GL_UNSIGNED_BYTE = 13

    def __init__(self):
        self.buffer_data = []
        self.buffer_sub_data = []
        self.tex_images = []
        self.bound_buffers = []

    def glGenTextures(self, _count):
        return 71

    def glBindBuffer(self, target, handle):
        self.bound_buffers.append((target, handle))

    def glBufferData(self, *args):
        self.buffer_data.append(args)

    def glBufferSubData(self, *args):
        self.buffer_sub_data.append(args)

    def glBindTexture(self, *_args):
        pass

    def glPixelStorei(self, *_args):
        pass

    def glTexParameteri(self, *_args):
        pass

    def glTexImage2D(self, *args):
        self.tex_images.append(args)

    def glDeleteTextures(self, *_args):
        pass


def test_payload_upload_uses_rgba_contract_and_immutable_pbo_bytes(monkeypatch):
    import rendering.gl_programs.texture_manager as texture_module
    from core.resources.manager import ResourceManager

    class ResourceStub:
        def register_gl_texture(self, *_args, **_kwargs):
            return None

    fake_gl = _FakeGL()
    monkeypatch.setattr(texture_module, "gl", fake_gl)
    monkeypatch.setattr(
        ResourceManager,
        "get_or_create_app_shared",
        classmethod(lambda _cls: ResourceStub()),
    )
    manager = texture_module.GLTextureManager()
    monkeypatch.setattr(manager, "_get_or_create_pbo", lambda _size: 41)
    payload = ImageUploadPayload.from_rgba8(3, 1, bytes(range(12)))

    assert manager.upload_payload(payload) == 71
    assert fake_gl.buffer_sub_data == [(1, 0, 12, payload.data)]
    assert fake_gl.tex_images == [(3, 0, 11, 3, 1, 0, 12, 13, None)]
    assert manager._texture_sizes[71] == payload.byte_size
    assert not hasattr(fake_gl, "glFinish")
    assert not hasattr(fake_gl, "glClientWaitSync")


def test_payload_get_or_create_never_converts_qpixmap(monkeypatch):
    import rendering.gl_programs.texture_manager as texture_module

    class ConversionTrap:
        def isNull(self):
            return False

        def toImage(self):
            raise AssertionError("payload path must not convert QPixmap")

    monkeypatch.setattr(texture_module, "gl", object())
    manager = texture_module.GLTextureManager()
    monkeypatch.setattr(manager, "upload_payload", lambda _payload: 81)
    payload = ImageUploadPayload.from_rgba8(1, 1, b"\x01\x02\x03\x04")

    first = manager.get_or_create_texture(ConversionTrap(), payload=payload)
    second = manager.get_or_create_texture(ConversionTrap(), payload=payload)

    assert first == second == 81
    assert manager.get_cached_texture(payload) == 81
    assert manager.commit_cached_texture(payload, texture_id=81) == 81
    assert manager.get_stats()["misses"] == 1
    assert manager.get_stats()["hits"] == 2


def test_payload_texture_is_uploaded_once_per_share_group_with_gpu_ordering(
    monkeypatch,
):
    import rendering.gl_programs.texture_manager as texture_module
    from rendering.gl_programs.shared_texture_registry import SharedTextureRegistry

    class SharedGL:
        GL_SYNC_GPU_COMMANDS_COMPLETE = 1
        GL_TIMEOUT_IGNORED = -1

        def __init__(self):
            self.waits = []
            self.deleted = []
            self.deleted_syncs = []
            self.flushes = 0

        def glFenceSync(self, _condition, _flags):
            return "ready-91"

        def glFlush(self):
            self.flushes += 1

        def glIsTexture(self, texture_id):
            return int(texture_id) == 91

        def glWaitSync(self, sync, flags, timeout):
            self.waits.append((sync, flags, timeout))

        def glDeleteTextures(self, texture_id):
            self.deleted.append(int(texture_id))

        def glDeleteSync(self, sync):
            self.deleted_syncs.append(sync)

    wrapper = object()
    fake_gl = SharedGL()
    uploads = []
    registry = SharedTextureRegistry()
    monkeypatch.setattr(texture_module, "gl", fake_gl)
    monkeypatch.setattr(
        texture_module,
        "current_share_group_identity",
        lambda: (("share-group", 1), wrapper),
    )
    monkeypatch.setattr(texture_module, "qt_object_is_valid", lambda _obj: True)
    first = texture_module.GLTextureManager(shared_registry=registry)
    second = texture_module.GLTextureManager(shared_registry=registry)

    def upload(_payload):
        uploads.append(91)
        return 91

    monkeypatch.setattr(first, "upload_payload", upload)
    monkeypatch.setattr(
        second,
        "upload_payload",
        lambda _payload: (_ for _ in ()).throw(
            AssertionError("second compositor must reuse shared native storage")
        ),
    )
    payload = ImageUploadPayload.from_rgba8(1, 1, b"\x01\x02\x03\x04")

    assert first.get_or_create_texture(payload=payload) == 91
    assert second.get_or_create_texture(payload=payload) == 91
    assert uploads == [91]
    assert fake_gl.flushes == 1
    assert fake_gl.waits == [("ready-91", 0, -1)]
    assert registry.stats().creations == 1
    assert registry.stats().reuses == 1
    assert registry.stats().texture_bytes == 4
    assert first.get_stats()["texture_mb"] == 0.0
    assert first.get_stats()["shared_group_textures"] == 1

    first.cleanup_cache()
    assert fake_gl.deleted == []
    second.cleanup_cache()
    assert fake_gl.deleted == [91]
    assert fake_gl.deleted_syncs == ["ready-91"]


def test_shared_texture_abandon_keeps_other_compositor_lease_live(monkeypatch):
    import rendering.gl_programs.texture_manager as texture_module
    from rendering.gl_programs.shared_texture_registry import SharedTextureRegistry

    class SharedGL:
        GL_SYNC_GPU_COMMANDS_COMPLETE = 1
        GL_TIMEOUT_IGNORED = -1

        def __init__(self):
            self.deleted = []

        def glFenceSync(self, *_args):
            return "ready"

        def glFlush(self):
            pass

        def glIsTexture(self, _texture_id):
            return True

        def glWaitSync(self, *_args):
            pass

        def glDeleteTextures(self, texture_id):
            self.deleted.append(int(texture_id))

        def glDeleteSync(self, _sync):
            pass

    wrapper = object()
    fake_gl = SharedGL()
    registry = SharedTextureRegistry()
    monkeypatch.setattr(texture_module, "gl", fake_gl)
    monkeypatch.setattr(
        texture_module,
        "current_share_group_identity",
        lambda: (("share-group", 2), wrapper),
    )
    monkeypatch.setattr(texture_module, "qt_object_is_valid", lambda _obj: True)
    first = texture_module.GLTextureManager(shared_registry=registry)
    second = texture_module.GLTextureManager(shared_registry=registry)
    monkeypatch.setattr(first, "upload_payload", lambda _payload: 101)
    monkeypatch.setattr(second, "upload_payload", lambda _payload: 202)
    payload = ImageUploadPayload.from_rgba8(1, 1, b"\x05\x06\x07\x08")

    assert first.get_or_create_texture(payload=payload) == 101
    assert second.get_or_create_texture(payload=payload) == 101
    first.abandon()

    assert registry.stats().entries == registry.stats().leases == 1
    assert second.get_cached_texture(payload=payload) == 101
    second.cleanup_cache()
    assert fake_gl.deleted == [101]


def test_payload_pair_is_authoritative_cached_and_committable(monkeypatch):
    import rendering.gl_programs.texture_manager as texture_module

    class ConversionTrap:
        def isNull(self):
            return False

        def toImage(self):
            raise AssertionError("authoritative payload pair must not convert")

    monkeypatch.setattr(texture_module, "gl", object())
    manager = texture_module.GLTextureManager()
    next_texture = iter((91, 92))
    monkeypatch.setattr(manager, "upload_payload", lambda _payload: next(next_texture))
    old_payload = ImageUploadPayload.from_rgba8(1, 1, b"\x01\x02\x03\x04")
    new_payload = ImageUploadPayload.from_rgba8(1, 1, b"\x05\x06\x07\x08")

    assert manager.prepare_transition_textures(
        ConversionTrap(),
        ConversionTrap(),
        old_payload=old_payload,
        new_payload=new_payload,
    )
    assert (manager.old_tex_id, manager.new_tex_id) == (91, 92)
    assert manager.get_cached_texture(payload=new_payload) == 92
    assert manager.commit_cached_texture(payload=new_payload, texture_id=92) == 92
    assert manager.get_committed_texture() == 92

    manager.release_transition_textures()
    assert manager.prepare_transition_textures(
        ConversionTrap(),
        ConversionTrap(),
        old_payload=old_payload,
        new_payload=new_payload,
    )
    assert (manager.old_tex_id, manager.new_tex_id) == (91, 92)


def test_incomplete_payload_pair_does_not_fall_back_to_pixmaps(monkeypatch):
    import rendering.gl_programs.texture_manager as texture_module

    monkeypatch.setattr(texture_module, "gl", object())
    manager = texture_module.GLTextureManager()
    payload = ImageUploadPayload.from_rgba8(1, 1, b"\0\0\0\xff")
    monkeypatch.setattr(
        manager,
        "get_or_create_texture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("incomplete payload pair must fail before upload")
        ),
    )

    assert not manager.prepare_transition_textures(
        object(), object(), old_payload=payload, new_payload=None
    )


def test_shader_dispatch_forwards_state_payload_pair():
    from types import SimpleNamespace

    from rendering.gl_compositor_pkg.shader_dispatch import prepare_transition_textures

    old_payload = ImageUploadPayload.from_rgba8(1, 1, b"\x01\x02\x03\x04")
    new_payload = ImageUploadPayload.from_rgba8(1, 1, b"\x05\x06\x07\x08")

    class Manager:
        def __init__(self):
            self.received = None

        def has_transition_textures(self):
            return False

        def prepare_transition_textures(self, old_pixmap, new_pixmap, **kwargs):
            self.received = (old_pixmap, new_pixmap, kwargs)
            return True

    manager = Manager()
    state = SimpleNamespace(
        old_pixmap="old",
        new_pixmap="new",
        old_upload_payload=old_payload,
        new_upload_payload=new_payload,
    )
    comp = SimpleNamespace(
        _gl_pipeline=object(),
        _texture_manager=manager,
        _texture_prep_exception_logged=False,
    )

    assert prepare_transition_textures(comp, lambda: True, state)
    assert manager.received == (
        "old",
        "new",
        {"old_payload": old_payload, "new_payload": new_payload},
    )


def test_compositor_stages_one_complete_payload_pair_on_active_state():
    from types import SimpleNamespace

    from rendering.gl_compositor import GLCompositorWidget

    old_payload = ImageUploadPayload.from_rgba8(1, 1, b"\x01\x02\x03\x04")
    new_payload = ImageUploadPayload.from_rgba8(1, 1, b"\x05\x06\x07\x08")
    state = SimpleNamespace(old_upload_payload=None, new_upload_payload=None)
    comp = SimpleNamespace(
        _staged_old_upload_payload=None,
        _staged_new_upload_payload=None,
        _crossfade=None,
        _slide=None,
        _wipe=state,
        _warp=None,
        _blockflip=None,
        _blockspin=None,
        _blinds=None,
        _diffuse=None,
        _raindrops=None,
        _crumble=None,
        _particle=None,
        _burn=None,
    )

    assert GLCompositorWidget.stage_transition_upload_payloads(
        comp,
        old_payload,
        new_payload,
    )
    assert GLCompositorWidget._attach_staged_transition_upload_payloads(comp)
    assert state.old_upload_payload is old_payload
    assert state.new_upload_payload is new_payload
    assert comp._staged_old_upload_payload is None
    assert comp._staged_new_upload_payload is None

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from rendering.gl_programs.shared_texture_registry import (
    InvalidShareGroupError,
    ShareGroupIdentity,
    SharedTextureRegistry,
    TextureAllocation,
    TextureLifecycleCallbacks,
)
from rendering.image_upload_payload import ImageUploadPayload


@dataclass
class NativeHarness:
    next_texture_id: int = 100
    forced_texture_id: int | None = None
    creates: list[str] = field(default_factory=list)
    validates: list[int] = field(default_factory=list)
    deleted: list[int] = field(default_factory=list)
    unregistered: list[object | None] = field(default_factory=list)
    abandoned: list[object | None] = field(default_factory=list)
    valid_textures: set[int] = field(default_factory=set)

    def callbacks(self) -> TextureLifecycleCallbacks:
        return TextureLifecycleCallbacks(
            create_upload=self.create_upload,
            validate=self.validate,
            delete=self.delete,
            unregister=self.unregister,
            abandon_unregister=self.abandon_unregister,
        )

    def create_upload(self, payload: ImageUploadPayload) -> TextureAllocation:
        texture_id = self.forced_texture_id or self.next_texture_id
        self.next_texture_id += 1
        self.creates.append(payload.content_id)
        self.valid_textures.add(texture_id)
        return TextureAllocation(texture_id, f"resource-{len(self.creates)}")

    def validate(self, allocation: TextureAllocation) -> bool:
        self.validates.append(allocation.texture_id)
        return allocation.texture_id in self.valid_textures

    def delete(self, texture_id: int) -> None:
        self.deleted.append(texture_id)
        self.valid_textures.discard(texture_id)

    def unregister(self, registration_token: object | None) -> None:
        self.unregistered.append(registration_token)

    def abandon_unregister(self, registration_token: object | None) -> None:
        self.abandoned.append(registration_token)


def payload(marker: int, *, width: int = 2, height: int = 2) -> ImageUploadPayload:
    return ImageUploadPayload.from_rgba8(
        width,
        height,
        bytes([marker]) * (width * height * 4),
    )


def group(key: int, validity: dict[str, bool] | None = None) -> ShareGroupIdentity:
    wrapper = object()
    state = validity if validity is not None else {"valid": True}
    return ShareGroupIdentity(("share-group", key), wrapper, lambda _wrapper: state["valid"])


def test_exact_payload_reuses_valid_texture_and_callbacks_run_outside_lock() -> None:
    registry = SharedTextureRegistry()
    identity = group(1)
    native = NativeHarness()
    callbacks = native.callbacks()
    original_create = callbacks.create_upload
    original_validate = callbacks.validate
    callbacks = TextureLifecycleCallbacks(
        create_upload=lambda item: (registry.stats(), original_create(item))[1],
        validate=lambda allocation: (registry.stats(), original_validate(allocation))[1],
        delete=lambda texture_id: (registry.stats(), native.delete(texture_id))[1],
        unregister=lambda token: (registry.stats(), native.unregister(token))[1],
        abandon_unregister=lambda token: (
            registry.stats(),
            native.abandon_unregister(token),
        )[1],
    )
    item = payload(1)

    first = registry.acquire(identity, "manager-a", item, callbacks)
    second = registry.acquire(identity, "manager-b", item, callbacks)

    assert first.texture_id == second.texture_id == 100
    assert len(native.creates) == 1
    assert native.validates == [100]
    assert registry.stats().reuses == 1
    registry.release(first, identity)
    registry.release(second, identity)
    assert native.deleted == [100]
    assert native.unregistered == ["resource-1"]


def test_same_numeric_texture_id_is_independent_between_share_groups() -> None:
    registry = SharedTextureRegistry()
    first_native = NativeHarness(forced_texture_id=77)
    second_native = NativeHarness(forced_texture_id=77)
    first_group = group(1)
    second_group = group(2)
    item = payload(2)

    first = registry.acquire(first_group, "manager-a", item, first_native.callbacks())
    second = registry.acquire(second_group, "manager-b", item, second_native.callbacks())

    assert first.texture_id == second.texture_id == 77
    assert len(first_native.creates) == len(second_native.creates) == 1
    registry.release(first, first_group)
    assert first_native.deleted == [77]
    assert second_native.deleted == []
    registry.release(second, second_group)
    assert second_native.deleted == [77]


def test_content_identity_does_not_hide_dimension_or_format_mismatch() -> None:
    registry = SharedTextureRegistry()
    identity = group(3)
    native = NativeHarness()
    first_payload = payload(3, width=2, height=2)
    different_shape = payload(3, width=1, height=4)
    object.__setattr__(different_shape, "content_id", first_payload.content_id)

    first = registry.acquire(identity, "manager-a", first_payload, native.callbacks())
    second = registry.acquire(identity, "manager-a", different_shape, native.callbacks())

    assert first.texture_id != second.texture_id
    assert len(native.creates) == 2
    assert first.key.content_id == second.key.content_id
    assert (first.key.width, first.key.height) != (second.key.width, second.key.height)


def test_independent_manager_and_reentrant_leases_hold_storage() -> None:
    registry = SharedTextureRegistry()
    identity = group(4)
    native = NativeHarness()
    item = payload(4)

    first = registry.acquire(identity, "manager-a", item, native.callbacks())
    repeated = registry.acquire(identity, "manager-a", item, native.callbacks())
    other = registry.acquire(identity, "manager-b", item, native.callbacks())

    stats = registry.stats()
    assert stats.live_managers == 2
    assert stats.leases == 3
    assert registry.release(first, identity).deleted_textures == 0
    assert registry.release(other, identity).deleted_textures == 0
    assert native.deleted == []
    assert registry.release(repeated, identity).deleted_textures == 1
    assert native.deleted == [100]


def test_final_valid_release_deletes_and_unregisters_exactly_once() -> None:
    registry = SharedTextureRegistry()
    identity = group(5)
    native = NativeHarness()
    item = payload(5)
    first = registry.acquire(identity, object(), item, native.callbacks())
    second = registry.acquire(identity, object(), item, native.callbacks())

    registry.release(first, identity)
    result = registry.release(second, identity)
    duplicate = registry.release(second, identity)

    assert result.deleted_textures == result.unregistered_textures == 1
    assert duplicate == type(duplicate)()
    assert native.deleted == [100]
    assert native.unregistered == ["resource-1"]


def test_final_abandon_unregisters_without_invalid_context_gl_work() -> None:
    registry = SharedTextureRegistry()
    identity = group(6)
    native = NativeHarness()
    lease = registry.acquire(identity, "manager-a", payload(6), native.callbacks())

    result = registry.abandon(lease)

    assert result.released_leases == 1
    assert result.unregistered_textures == 1
    assert native.deleted == native.unregistered == []
    assert native.abandoned == ["resource-1"]
    assert registry.stats().pending_delete_entries == 0
    drained = registry.drain(identity)
    assert drained.deleted_textures == drained.unregistered_textures == 0
    assert native.deleted == []
    assert native.unregistered == []
    assert registry.drain(identity).deleted_textures == 0


def test_one_manager_abandon_keeps_texture_reusable_for_live_share_group() -> None:
    registry = SharedTextureRegistry()
    identity = group(61)
    native = NativeHarness()
    item = payload(61)
    first = registry.acquire(identity, "manager-a", item, native.callbacks())
    second = registry.acquire(identity, "manager-b", item, native.callbacks())

    registry.abandon(first)
    third = registry.acquire(identity, "manager-c", item, native.callbacks())

    assert third.texture_id == second.texture_id
    assert native.abandoned == []
    registry.release(second, identity)
    registry.release(third, identity)


def test_invalid_or_replaced_wrapper_cannot_reuse_stale_texture() -> None:
    registry = SharedTextureRegistry()
    state = {"valid": True}
    identity = group(7, state)
    native = NativeHarness()
    item = payload(7)
    lease = registry.acquire(identity, "manager-a", item, native.callbacks())
    state["valid"] = False

    with pytest.raises(InvalidShareGroupError):
        registry.acquire(identity, "manager-b", item, native.callbacks())
    replacement = ShareGroupIdentity(identity.stable_key, object(), lambda _wrapper: True)
    with pytest.raises(InvalidShareGroupError):
        registry.acquire(replacement, "manager-b", item, native.callbacks())

    same_wrapper_new_checker = ShareGroupIdentity(
        identity.stable_key,
        identity.wrapper,
        lambda _wrapper: True,
    )
    with pytest.raises(InvalidShareGroupError):
        registry.release(lease, same_wrapper_new_checker)

    assert len(native.creates) == 1
    assert native.validates == []
    assert native.deleted == native.unregistered == []


def test_lru_ceiling_never_evicts_leased_entries_and_abandon_retires_storage() -> None:
    registry = SharedTextureRegistry()
    identity = group(8)
    native = NativeHarness()
    leases = [
        registry.acquire(identity, "manager-a", payload(marker), native.callbacks())
        for marker in range(10, 15)
    ]

    stats = registry.stats()
    assert stats.lru_capacity == 4
    assert stats.entries == stats.leased_entries == 5
    assert stats.over_capacity_entries == 1
    assert stats.evictions == 0
    assert native.deleted == []

    for lease in leases[:3]:
        registry.abandon(lease)
    extra = registry.acquire(identity, "manager-a", payload(20), native.callbacks())

    stats = registry.stats()
    assert stats.entries == 3
    assert stats.evictions == 0
    assert native.deleted == []
    assert len(native.abandoned) == 3
    assert all(lease.texture_id not in native.deleted for lease in leases[3:])
    assert extra.texture_id not in native.deleted


def test_failed_validation_creates_new_generation_without_premature_delete() -> None:
    registry = SharedTextureRegistry()
    identity = group(9)
    native = NativeHarness()
    item = payload(9)
    first = registry.acquire(identity, "manager-a", item, native.callbacks())
    native.valid_textures.remove(first.texture_id)

    second = registry.acquire(identity, "manager-b", item, native.callbacks())

    assert second.texture_id != first.texture_id
    assert native.deleted == []
    registry.release(first, identity)
    assert native.deleted == [first.texture_id]
    registry.release(second, identity)
    assert native.deleted == [first.texture_id, second.texture_id]
    assert registry.stats().validation_failures == 1


def test_reset_for_tests_invalidates_old_lease_without_native_cleanup() -> None:
    registry = SharedTextureRegistry()
    identity = group(10)
    native = NativeHarness()
    lease = registry.acquire(identity, "manager-a", payload(10), native.callbacks())

    registry.reset_for_tests()

    assert registry.stats().entries == 0
    assert registry.release(lease, identity).released_leases == 0
    assert native.deleted == native.unregistered == []

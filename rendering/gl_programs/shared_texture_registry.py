"""Share-group-scoped leases for immutable OpenGL image textures.

This module owns metadata only. Callers must invoke it on their GL-affinity
thread with the intended share-group context current. It never imports OpenGL
or Qt, changes a context, waits for GPU work, or creates synchronization
objects. Every native/resource action is supplied by the caller and is invoked
outside the registry lock.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Hashable

if TYPE_CHECKING:
    from rendering.image_upload_payload import ImageUploadPayload


class SharedTextureRegistryError(RuntimeError):
    """Base error for shared texture registry contract violations."""


class InvalidShareGroupError(SharedTextureRegistryError):
    """Raised when a share-group wrapper is stale or does not match."""


class RegistryOperationInProgressError(SharedTextureRegistryError):
    """Raised instead of waiting when the same group/key is already active."""


@dataclass(frozen=True, slots=True)
class ShareGroupIdentity:
    """Stable native identity plus a retained wrapper and validity probe.

    ``stable_key`` should include the native share-group pointer/type rather
    than a transient context object. The registry also requires wrapper object
    identity to match so a recycled numeric pointer cannot reuse stale state.
    """

    stable_key: Hashable
    wrapper: object
    wrapper_is_valid: Callable[[object], bool] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        try:
            hash(self.stable_key)
        except TypeError as exc:
            raise TypeError("share-group stable_key must be hashable") from exc
        if self.wrapper is None:
            raise ValueError("share-group wrapper must not be None")
        if not callable(self.wrapper_is_valid):
            raise TypeError("wrapper_is_valid must be callable")

    def is_valid(self) -> bool:
        """Return wrapper validity without allowing probe failures to escape."""

        try:
            return bool(self.wrapper_is_valid(self.wrapper))
        except Exception:
            return False


@dataclass(frozen=True, slots=True)
class TextureKey:
    """Immutable upload identity; content hash alone is never authoritative."""

    content_id: str
    width: int
    height: int
    stride: int
    pixel_format: str

    @classmethod
    def from_payload(cls, payload: ImageUploadPayload) -> "TextureKey":
        try:
            content_id = str(payload.content_id)
            width = int(payload.width)
            height = int(payload.height)
            stride = int(payload.stride)
            pixel_format = str(payload.pixel_format)
        except (AttributeError, TypeError, ValueError) as exc:
            raise TypeError("payload must provide immutable upload metadata") from exc
        if not content_id or width <= 0 or height <= 0 or stride <= 0 or not pixel_format:
            raise ValueError("payload upload metadata is incomplete")
        return cls(content_id, width, height, stride, pixel_format)


@dataclass(frozen=True, slots=True)
class TextureAllocation:
    """Native texture id plus ownership and cross-context publication tokens."""

    texture_id: int
    registration_token: object | None = None
    publication_token: object | None = None

    def __post_init__(self) -> None:
        if int(self.texture_id) <= 0:
            raise ValueError("created texture id must be positive")
        object.__setattr__(self, "texture_id", int(self.texture_id))


@dataclass(frozen=True, slots=True)
class TextureLifecycleCallbacks:
    """Caller-owned native lifecycle actions, all run outside registry locks."""

    create_upload: Callable[[ImageUploadPayload], TextureAllocation | int]
    validate: Callable[[TextureAllocation], bool]
    delete: Callable[[int], None]
    unregister: Callable[[object | None], None]
    abandon_unregister: Callable[[object | None], None]

    def __post_init__(self) -> None:
        for name in (
            "create_upload",
            "validate",
            "delete",
            "unregister",
            "abandon_unregister",
        ):
            if not callable(getattr(self, name)):
                raise TypeError(f"{name} callback must be callable")


@dataclass(frozen=True, slots=True)
class TextureLease:
    """Opaque, one-shot lease owned by one texture manager."""

    lease_id: int
    texture_id: int
    key: TextureKey
    group_key: Hashable
    manager_token: Hashable = field(repr=False)
    _registry_generation: int = field(repr=False)
    _group_generation: int = field(repr=False)


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Outcome of a release or explicit drain."""

    released_leases: int = 0
    deleted_textures: int = 0
    unregistered_textures: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RegistryStats:
    """Coherent snapshot of registry occupancy and lifetime counters."""

    groups: int
    entries: int
    leased_entries: int
    pending_delete_entries: int
    live_managers: int
    leases: int
    texture_bytes: int
    lru_capacity: int
    over_capacity_entries: int
    acquisitions: int
    reuses: int
    creations: int
    validation_failures: int
    releases: int
    abandons: int
    drains: int
    evictions: int
    delete_calls: int
    unregister_calls: int
    abandon_unregister_calls: int
    callback_errors: int


@dataclass(slots=True)
class _Entry:
    entry_id: int
    key: TextureKey
    allocation: TextureAllocation
    callbacks: TextureLifecycleCallbacks
    leases: dict[int, Hashable] = field(default_factory=dict)
    pending_delete: bool = False
    cleanup_claimed: bool = False
    operations: int = 0
    last_used: int = 0


@dataclass(slots=True)
class _Group:
    identity: ShareGroupIdentity
    generation: int
    active: dict[TextureKey, _Entry] = field(default_factory=dict)
    entries: dict[int, _Entry] = field(default_factory=dict)
    manager_lease_counts: Counter[Hashable] = field(default_factory=Counter)
    busy_keys: set[TextureKey] = field(default_factory=set)


class SharedTextureRegistry:
    """Thread-safe metadata registry for immutable share-group textures.

    Native callbacks are never serialized by this object. The caller remains
    responsible for invoking acquire/release/drain on the correct GL-affinity
    thread with the matching context current.
    """

    TEXTURES_PER_LIVE_MANAGER = 4

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._registry_generation = 1
        self._next_group_generation = 1
        self._next_entry_id = 1
        self._next_lease_id = 1
        self._clock = 0
        self._groups: dict[Hashable, _Group] = {}
        self._leases: dict[int, tuple[_Group, _Entry]] = {}
        self._counters: Counter[str] = Counter()

    def acquire(
        self,
        group_identity: ShareGroupIdentity,
        manager_token: Hashable,
        payload: ImageUploadPayload,
        callbacks: TextureLifecycleCallbacks,
    ) -> TextureLease:
        """Acquire one manager lease, validating reuse or uploading once.

        The validate/create callbacks run with no registry lock held. Rather
        than block another caller while native work is active, a same-key
        concurrent acquisition raises ``RegistryOperationInProgressError``.
        """

        self._require_hashable_manager(manager_token)
        key = TextureKey.from_payload(payload)
        group = self._resolve_group(group_identity, create=True)
        entry: _Entry | None
        with self._lock:
            self._assert_current_group_locked(group_identity, group)
            if key in group.busy_keys:
                raise RegistryOperationInProgressError(
                    "texture acquisition already active for this share group and payload"
                )
            group.busy_keys.add(key)
            entry = group.active.get(key)
            if entry is not None:
                entry.operations += 1

        if entry is not None:
            try:
                reusable = bool(callbacks.validate(entry.allocation))
            except Exception:
                reusable = False
            cleanup: list[_Entry] = []
            with self._lock:
                group.busy_keys.discard(key)
                entry.operations = max(0, entry.operations - 1)
                still_active = group.active.get(key) is entry and not entry.pending_delete
                if reusable and still_active:
                    lease = self._grant_lease_locked(group, entry, manager_token, reused=True)
                    cleanup.extend(self._prune_lru_locked(group))
                else:
                    self._counters["validation_failures"] += 1
                    self._mark_pending_locked(group, entry)
                    claimed = self._claim_if_unleased_locked(group, entry)
                    if claimed is not None:
                        cleanup.append(claimed)
                    group.busy_keys.add(key)
                    lease = None
            self._cleanup_entries(cleanup)
            if lease is not None:
                return lease

        try:
            created = callbacks.create_upload(payload)
            allocation = (
                created
                if isinstance(created, TextureAllocation)
                else TextureAllocation(int(created))
            )
        except Exception:
            with self._lock:
                group.busy_keys.discard(key)
            raise

        cleanup = []
        post_create_error: Exception | None = None
        with self._lock:
            try:
                self._assert_current_group_locked(group_identity, group)
                if key in group.active:
                    raise RegistryOperationInProgressError(
                        "texture appeared while create/upload callback was active"
                    )
                entry = _Entry(
                    entry_id=self._take_entry_id_locked(),
                    key=key,
                    allocation=allocation,
                    callbacks=callbacks,
                    last_used=self._tick_locked(),
                )
                group.active[key] = entry
                group.entries[entry.entry_id] = entry
                self._counters["creations"] += 1
                lease = self._grant_lease_locked(group, entry, manager_token, reused=False)
                cleanup.extend(self._prune_lru_locked(group))
            except Exception as exc:
                post_create_error = exc
            finally:
                group.busy_keys.discard(key)
        if post_create_error is not None:
            cleanup.append(
                _Entry(
                    entry_id=0,
                    key=key,
                    allocation=allocation,
                    callbacks=callbacks,
                )
            )
            self._cleanup_entries(cleanup)
            raise post_create_error
        self._cleanup_entries(cleanup)
        return lease

    def release(
        self,
        lease: TextureLease,
        group_identity: ShareGroupIdentity,
    ) -> CleanupResult:
        """Release one lease and clean the final reference in a valid context."""

        resolved_group = self._resolve_group(group_identity, create=False)
        if resolved_group is None:
            return CleanupResult()
        cleanup: list[_Entry] = []
        with self._lock:
            located = self._locate_lease_locked(lease)
            if located is None:
                return CleanupResult()
            group, entry = located
            if group is not resolved_group:
                raise InvalidShareGroupError("lease belongs to another group generation")
            self._assert_current_group_locked(group_identity, group)
            self._drop_lease_locked(group, entry, lease.lease_id)
            self._counters["releases"] += 1
            if not entry.leases:
                self._mark_pending_locked(group, entry)
                claimed = self._claim_if_unleased_locked(group, entry)
                if claimed is not None:
                    cleanup.append(claimed)
            cleanup.extend(self._prune_lru_locked(group))
        result = self._cleanup_entries(cleanup)
        return CleanupResult(
            released_leases=1,
            deleted_textures=result.deleted_textures,
            unregistered_textures=result.unregistered_textures,
            errors=result.errors,
        )

    def abandon(self, lease: TextureLease) -> CleanupResult:
        """Drop one lease after context loss without issuing any GL calls."""

        abandoned: list[_Entry] = []
        with self._lock:
            located = self._locate_lease_locked(lease)
            if located is None:
                return CleanupResult()
            group, entry = located
            self._drop_lease_locked(group, entry, lease.lease_id)
            self._counters["abandons"] += 1
            if not entry.leases:
                self._mark_pending_locked(group, entry)
                claimed = self._claim_if_unleased_locked(group, entry)
                if claimed is not None:
                    abandoned.append(claimed)
        result = self._abandon_entries(abandoned)
        return CleanupResult(
            released_leases=1,
            unregistered_textures=result.unregistered_textures,
            errors=result.errors,
        )

    def drain(self, group_identity: ShareGroupIdentity) -> CleanupResult:
        """Clean unleased pending entries with the matching context current."""

        group = self._resolve_group(group_identity, create=False)
        if group is None:
            return CleanupResult()
        cleanup: list[_Entry] = []
        with self._lock:
            self._assert_current_group_locked(group_identity, group)
            for entry in sorted(group.entries.values(), key=lambda item: item.last_used):
                if entry.pending_delete and not entry.leases and entry.operations == 0:
                    claimed = self._claim_cleanup_locked(group, entry)
                    if claimed is not None:
                        cleanup.append(claimed)
            self._counters["drains"] += 1
        result = self._cleanup_entries(cleanup)
        return CleanupResult(
            deleted_textures=result.deleted_textures,
            unregistered_textures=result.unregistered_textures,
            errors=result.errors,
        )

    def stats(self, group_key: Hashable | None = None) -> RegistryStats:
        """Return a lock-consistent occupancy and lifetime counter snapshot."""

        with self._lock:
            groups = list(self._groups.values())
            if group_key is not None:
                groups = [group for group in groups if group.identity.stable_key == group_key]
            entries = [entry for group in groups for entry in group.entries.values()]
            managers = {
                (group.generation, manager)
                for group in groups
                for manager, count in group.manager_lease_counts.items()
                if count > 0
            }
            capacity = self.TEXTURES_PER_LIVE_MANAGER * len(managers)
            count = len(entries)
            counters = self._counters.copy()
            return RegistryStats(
                groups=len(groups),
                entries=count,
                leased_entries=sum(bool(entry.leases) for entry in entries),
                pending_delete_entries=sum(entry.pending_delete for entry in entries),
                live_managers=len(managers),
                leases=sum(len(entry.leases) for entry in entries),
                texture_bytes=sum(
                    entry.key.stride * entry.key.height for entry in entries
                ),
                lru_capacity=capacity,
                over_capacity_entries=max(0, count - capacity),
                acquisitions=counters["acquisitions"],
                reuses=counters["reuses"],
                creations=counters["creations"],
                validation_failures=counters["validation_failures"],
                releases=counters["releases"],
                abandons=counters["abandons"],
                drains=counters["drains"],
                evictions=counters["evictions"],
                delete_calls=counters["delete_calls"],
                unregister_calls=counters["unregister_calls"],
                abandon_unregister_calls=counters["abandon_unregister_calls"],
                callback_errors=counters["callback_errors"],
            )

    def reset_for_tests(self) -> None:
        """Forget all metadata without native callbacks; test isolation only."""

        with self._lock:
            self._groups.clear()
            self._leases.clear()
            self._counters.clear()
            self._registry_generation += 1
            self._next_group_generation = 1
            self._next_entry_id = 1
            self._next_lease_id = 1
            self._clock = 0

    def _resolve_group(
        self,
        identity: ShareGroupIdentity,
        *,
        create: bool,
    ) -> _Group | None:
        identity = self._require_valid_identity(identity)
        with self._lock:
            group = self._groups.get(identity.stable_key)
        if group is not None:
            stored_valid = group.identity.is_valid()
            with self._lock:
                if self._groups.get(identity.stable_key) is not group:
                    group = self._groups.get(identity.stable_key)
                elif not stored_valid:
                    if not group.entries and not group.busy_keys:
                        self._groups.pop(identity.stable_key, None)
                        group = None
                    else:
                        raise InvalidShareGroupError(
                            "stored share-group wrapper is stale; native entries cannot be reused"
                        )
        with self._lock:
            if group is not None:
                self._assert_current_group_locked(identity, group)
                return group
            if not create:
                return None
            group = _Group(
                identity=identity,
                generation=self._next_group_generation,
            )
            self._next_group_generation += 1
            self._groups[identity.stable_key] = group
            return group

    @staticmethod
    def _require_valid_identity(identity: ShareGroupIdentity) -> ShareGroupIdentity:
        if not isinstance(identity, ShareGroupIdentity):
            raise TypeError("group_identity must be ShareGroupIdentity")
        if not identity.is_valid():
            raise InvalidShareGroupError("share-group wrapper is not valid")
        return identity

    @staticmethod
    def _require_hashable_manager(manager_token: Hashable) -> None:
        try:
            hash(manager_token)
        except TypeError as exc:
            raise TypeError("manager_token must be hashable") from exc

    @staticmethod
    def _assert_current_group_locked(
        identity: ShareGroupIdentity,
        group: _Group,
    ) -> None:
        if identity.stable_key != group.identity.stable_key:
            raise InvalidShareGroupError("share-group stable identity does not match")
        if identity.wrapper is not group.identity.wrapper:
            raise InvalidShareGroupError(
                "share-group wrapper does not match retained verified wrapper"
            )

    def _grant_lease_locked(
        self,
        group: _Group,
        entry: _Entry,
        manager_token: Hashable,
        *,
        reused: bool,
    ) -> TextureLease:
        lease_id = self._next_lease_id
        self._next_lease_id += 1
        entry.leases[lease_id] = manager_token
        entry.last_used = self._tick_locked()
        group.manager_lease_counts[manager_token] += 1
        self._leases[lease_id] = (group, entry)
        self._counters["acquisitions"] += 1
        if reused:
            self._counters["reuses"] += 1
        return TextureLease(
            lease_id=lease_id,
            texture_id=entry.allocation.texture_id,
            key=entry.key,
            group_key=group.identity.stable_key,
            manager_token=manager_token,
            _registry_generation=self._registry_generation,
            _group_generation=group.generation,
        )

    def _locate_lease_locked(
        self,
        lease: TextureLease,
    ) -> tuple[_Group, _Entry] | None:
        if not isinstance(lease, TextureLease):
            raise TypeError("lease must be TextureLease")
        if lease._registry_generation != self._registry_generation:
            return None
        located = self._leases.get(lease.lease_id)
        if located is None:
            return None
        group, entry = located
        if lease._group_generation != group.generation:
            return None
        return group, entry

    def _drop_lease_locked(self, group: _Group, entry: _Entry, lease_id: int) -> None:
        manager_token = entry.leases.pop(lease_id)
        self._leases.pop(lease_id, None)
        remaining = group.manager_lease_counts[manager_token] - 1
        if remaining > 0:
            group.manager_lease_counts[manager_token] = remaining
        else:
            group.manager_lease_counts.pop(manager_token, None)

    @staticmethod
    def _mark_pending_locked(group: _Group, entry: _Entry) -> None:
        entry.pending_delete = True
        if group.active.get(entry.key) is entry:
            group.active.pop(entry.key, None)

    def _claim_if_unleased_locked(self, group: _Group, entry: _Entry) -> _Entry | None:
        if entry.leases or entry.operations:
            return None
        return self._claim_cleanup_locked(group, entry)

    @staticmethod
    def _claim_cleanup_locked(group: _Group, entry: _Entry) -> _Entry | None:
        if entry.cleanup_claimed or entry.leases or entry.operations:
            return None
        entry.cleanup_claimed = True
        if group.active.get(entry.key) is entry:
            group.active.pop(entry.key, None)
        group.entries.pop(entry.entry_id, None)
        return entry

    def _prune_lru_locked(self, group: _Group) -> list[_Entry]:
        capacity = self.TEXTURES_PER_LIVE_MANAGER * len(group.manager_lease_counts)
        cleanup: list[_Entry] = []
        while len(group.entries) > capacity:
            candidate = next(
                (
                    entry
                    for entry in sorted(
                        group.entries.values(), key=lambda item: item.last_used
                    )
                    if not entry.leases and entry.operations == 0
                ),
                None,
            )
            if candidate is None:
                break
            claimed = self._claim_cleanup_locked(group, candidate)
            if claimed is None:
                break
            cleanup.append(claimed)
            self._counters["evictions"] += 1
        return cleanup

    def _cleanup_entries(self, entries: list[_Entry]) -> CleanupResult:
        deleted = 0
        unregistered = 0
        errors: list[str] = []
        for entry in entries:
            try:
                entry.callbacks.delete(entry.allocation.texture_id)
            except Exception as exc:
                errors.append(f"delete texture {entry.allocation.texture_id}: {exc}")
            finally:
                deleted += 1
                with self._lock:
                    self._counters["delete_calls"] += 1
            try:
                entry.callbacks.unregister(entry.allocation.registration_token)
            except Exception as exc:
                errors.append(f"unregister texture {entry.allocation.texture_id}: {exc}")
            finally:
                unregistered += 1
                with self._lock:
                    self._counters["unregister_calls"] += 1
        if errors:
            with self._lock:
                self._counters["callback_errors"] += len(errors)
        return CleanupResult(
            deleted_textures=deleted,
            unregistered_textures=unregistered,
            errors=tuple(errors),
        )

    def _abandon_entries(self, entries: list[_Entry]) -> CleanupResult:
        """Forget ResourceManager ownership after native context destruction."""

        unregistered = 0
        errors: list[str] = []
        for entry in entries:
            try:
                entry.callbacks.abandon_unregister(
                    entry.allocation.registration_token
                )
            except Exception as exc:
                errors.append(
                    f"abandon texture {entry.allocation.texture_id}: {exc}"
                )
            finally:
                unregistered += 1
                with self._lock:
                    self._counters["abandon_unregister_calls"] += 1
        if errors:
            with self._lock:
                self._counters["callback_errors"] += len(errors)
        return CleanupResult(
            unregistered_textures=unregistered,
            errors=tuple(errors),
        )

    def _take_entry_id_locked(self) -> int:
        entry_id = self._next_entry_id
        self._next_entry_id += 1
        return entry_id

    def _tick_locked(self) -> int:
        self._clock += 1
        return self._clock


shared_texture_registry = SharedTextureRegistry()


def get_shared_texture_registry() -> SharedTextureRegistry:
    """Return the process-wide registry intended for texture-manager wiring."""

    return shared_texture_registry


__all__ = [
    "CleanupResult",
    "InvalidShareGroupError",
    "RegistryOperationInProgressError",
    "RegistryStats",
    "ShareGroupIdentity",
    "SharedTextureRegistry",
    "SharedTextureRegistryError",
    "TextureAllocation",
    "TextureKey",
    "TextureLease",
    "TextureLifecycleCallbacks",
    "get_shared_texture_registry",
    "shared_texture_registry",
]

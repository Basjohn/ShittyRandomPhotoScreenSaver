"""Ban Image indexes persistent hashes and uses eligible-only runtime queues."""
from pathlib import Path

from core.sources.image_bans import ImageBanStore, canonical_image_identity
from engine.image_queue import ImageQueue
from sources.base_provider import ImageMetadata, ImageSourceType


def _local(name):
    return ImageMetadata(ImageSourceType.FOLDER, 'folder', name, local_path=Path('C:/Art') / name)


def _remote(url, local='rss-cache-123.png'):
    return ImageMetadata(ImageSourceType.RSS, 'feed', url, url=url, local_path=Path(local))


def test_zero_ban_fast_path_never_hashes_candidates(tmp_path, monkeypatch):
    store = ImageBanStore(tmp_path / 'settings_v2.json')
    assert not store.has_banned_images
    monkeypatch.setattr(store, '_sentinel', lambda meta: (_ for _ in ()).throw(AssertionError('disk lookup on zero ban')))
    assert not store.is_banned(_local('a.png'))
    queue = ImageQueue(shuffle=False)
    queue.add_images([_local('a.png'), _local('b.png')])
    assert queue._image_ban_predicate is None
    assert queue.next().image_id == 'a.png'


def test_ban_is_persistent_and_loaded_once_as_an_index(tmp_path):
    settings = tmp_path / 'settings.json'
    store = ImageBanStore(settings)
    local = _local('one.png')
    assert store.ban(local)
    assert store.is_banned(local)
    assert store._sentinel(local).stat().st_size == 0
    restored = ImageBanStore(settings)
    assert restored.has_banned_images and restored.is_banned(local)
    assert not restored.is_banned(_local('two.png'))
    restored.clear_all()
    assert not ImageBanStore(settings).has_banned_images
    assert not restored.is_banned(local)


def test_url_identity_stable_across_cache_paths_tokens_and_fragment(tmp_path):
    first = _remote('https://EXAMPLE.com/a.jpg?size=large&X-Amz-Signature=abc&utm_source=foo#top', 'cache1')
    second = _remote('https://example.com/a.jpg?utm_source=bar&size=large&X-Amz-Signature=def', 'cache2')
    different = _remote('https://example.com/a.jpg?size=small', 'cache3')
    assert canonical_image_identity(first) == canonical_image_identity(second)
    assert canonical_image_identity(first) != canonical_image_identity(different)
    store = ImageBanStore(tmp_path / 'settings.json')
    store.ban(first)
    assert store.is_banned(second) and not store.is_banned(different)


def test_queue_skips_bans_across_selection_and_preview_after_reindex(tmp_path):
    images = [_local('one.png'), _local('two.png'), _local('three.png')]
    queue = ImageQueue(shuffle=False)
    queue.add_images(images)
    store = ImageBanStore(tmp_path / 'settings.json')
    store.ban(images[0])
    store.ban(images[2])
    queue.set_image_ban_predicate(store.is_banned)
    assert queue.peek().image_id == 'two.png'
    assert [meta.image_id for meta in queue.peek_many(3)] == ['two.png']
    assert queue.next().image_id == 'two.png'
    assert all(meta.image_id == 'two.png' for meta in queue.preview_upcoming(5))
    store.ban(images[1])
    queue.set_image_ban_predicate(store.is_banned)  # explicit ban action updates the queue
    assert queue.next() is None   # empty eligible pool exits immediately
    store.clear_all()
    queue.set_image_ban_predicate(None)
    assert queue.next() is not None


def test_active_ban_lookup_never_touches_filesystem(tmp_path, monkeypatch):
    from pathlib import Path
    store = ImageBanStore(tmp_path / 'settings.json')
    images = [_local(f'image-{i}.jpg') for i in range(500)]
    for item in images[:400]:
        store.ban(item)
    restored = ImageBanStore(tmp_path / 'settings.json')
    assert len(restored._digests) == 400
    monkeypatch.setattr(Path, 'is_file', lambda *_: (_ for _ in ()).throw(
        AssertionError('filesystem access during ban lookup')))
    assert all(restored.is_banned(item) for item in images[:400])
    assert all(not restored.is_banned(item) for item in images[400:])


def test_ban_heavy_library_has_no_selection_predicate_or_retry_cost(tmp_path):
    images = [_local(f'image-{i}.jpg') for i in range(301)]
    store = ImageBanStore(tmp_path / 'settings.json')
    for img in images[:-1]:
        store.ban(img)
    queue = ImageQueue(shuffle=False)
    queue.add_images(images)
    counted = [0]

    def reject(meta):
        counted[0] += 1
        return store.is_banned(meta)

    queue.set_image_ban_predicate(reject)
    assert counted[0] == len(images)  # indexing once on explicit installation
    counted[0] = 0
    assert queue.size() == 1
    assert queue.peek() is images[-1]
    assert queue.peek_many(3) == [images[-1]]
    assert [x.image_id for x in queue.preview_upcoming(5)] == [images[-1].image_id] * 5
    for _ in range(20):
        assert queue.next() is images[-1]
    assert counted[0] == 0  # no ban identity work during ordinary selection


def test_incremental_ban_keeps_existing_queue_and_clear_restores_without_source_reload(tmp_path):
    images = [_local(f'image-{i}.jpg') for i in range(12)]
    queue = ImageQueue(shuffle=False)
    queue.add_images(images)
    assert queue.next() is images[0]
    store = ImageBanStore(tmp_path / 'settings.json')
    store.ban(images[1])
    checked = []

    def reject(meta):
        checked.append(meta.image_id)
        return store.is_banned(meta)

    queue.set_image_ban_predicate(reject)
    assert queue.next() is images[2]
    checked.clear()
    store.ban(images[3])
    queue.set_image_ban_predicate(reject)
    assert len(checked) == 11  # only previously eligible items rechecked
    assert queue.next() is images[4]
    assert all(x not in queue.preview_upcoming(12) for x in (images[1], images[3]))
    queue.add_images([images[1], images[5]])  # rediscovery must not readmit banned identity
    assert all(x is not images[1] for x in queue.peek_many(20))
    store.clear_all()
    queue.set_image_ban_predicate(None)
    assert images[1] in queue.peek_many(100)
    assert images[3] in queue.peek_many(100)


def test_all_banned_zero_retry_even_after_source_add(tmp_path):
    store = ImageBanStore(tmp_path / 'settings.json')
    images = [_local(f'{i}.jpg') for i in range(100)]
    for img in images:
        store.ban(img)
    queue = ImageQueue(shuffle=True)
    queue.set_image_ban_predicate(store.is_banned)
    queue.add_images(images)
    assert queue.is_empty()
    assert queue.next() is None
    assert queue.preview_upcoming(4) == []
    assert len(queue._history) == 0
    new_image = _local('allowed.jpg')
    queue.add_images([new_image])
    assert queue.next() is new_image


def test_context_menu_ban_routes_per_display_and_explicit_clear():
    from rendering.quick.context_menu import build_quick_context_menu_entries
    menu = build_quick_context_menu_entries(
        transition_names=['Crossfade'], current_transition='Crossfade',
        random_enabled=False, random_selectable=True,
        visualizer_modes=[], current_visualizer='spectrum', visualizer_available=False,
        dimming_enabled=False, interaction_mode_enabled=True,
        interaction_mode_locked=False, edit_mode_active=False,
    )
    images = next(entry for entry in menu if entry.kind == 'submenu' and 'Images' in entry.label)
    assert {'ban_image', 'clear_image_bans'} <= {entry.action_id for entry in images.children}

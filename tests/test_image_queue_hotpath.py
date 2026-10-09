"""Image queue prefetch work must scale with the requested preview, not source count."""
from collections import deque
from pathlib import Path
from engine.image_queue import ImageQueue
from sources.base_provider import ImageMetadata, ImageSourceType


def _meta(n):
    return ImageMetadata(ImageSourceType.FOLDER, 'test', str(n), local_path=Path(f'/art/{n}.png'))


def test_small_peek_does_not_walk_full_pending_catalogue():
    class CountingDeque(deque):
        seen = 0
        def __iter__(self):
            for item in super().__iter__():
                self.seen += 1
                if self.seen > 5:
                    raise AssertionError('peek_many walked beyond the requested five images')
                yield item
    q = ImageQueue(shuffle=False)
    items = [_meta(i) for i in range(12000)]
    q.add_images(items)
    q._queue = CountingDeque(q._queue)
    assert q.peek_many(5) == items[:5]
    assert q._queue.seen == 5


def test_banned_preview_does_not_clone_rejected_source_catalogue():
    q = ImageQueue(shuffle=False)
    items = [_meta(i) for i in range(500)]
    q.add_images(items)
    q.set_image_ban_predicate(lambda meta: int(meta.image_id) != 42)
    class RejectedCatalogue(list):
        def __iter__(self):
            raise AssertionError('Preview traversed the rejected full catalogue')
    q._images = RejectedCatalogue(q._images)
    assert [item.image_id for item in q.preview_upcoming(3)] == ['42', '42', '42']

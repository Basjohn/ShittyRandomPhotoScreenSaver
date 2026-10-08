"""Persistent per-profile image bans with in-memory membership.

An empty `.active` marker skips even loading the index for ordinary users.
When bans exist, hash filenames are loaded once per runtime generation; no
image-selection path touches the filesystem or scans the ban directory.
"""
from __future__ import annotations

import hashlib
import ntpath
import os
import shutil
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sources.base_provider import ImageSourceType


# Authentication/tracking query arguments do not identify remote artwork.
_EPHEMERAL_KEYS = frozenset({
    'expires', 'expiry', 'signature', 'sig', 'token', 'auth', 'auth_key',
    'x-amz-algorithm', 'x-amz-credential', 'x-amz-date', 'x-amz-expires',
    'x-amz-signedheaders', 'x-amz-signature', 'fbclid', 'gclid',
})


def canonical_image_identity(meta) -> str:
    """Local original path or stable remote resource URL, not an RSS cache file.

    Normalization never stats the disk and does not hash an image's bytes.
    """
    source_type = getattr(meta, 'source_type', None)
    url = str(getattr(meta, 'url', '') or '').strip()
    local = getattr(meta, 'local_path', None)
    if source_type != ImageSourceType.FOLDER and url:
        parts = urlsplit(url)
        if parts.scheme.lower() in ('http', 'https') and parts.hostname:
            host = parts.hostname.lower()
            if ':' in host and not host.startswith('['):
                host = f'[{host}]'
            try:
                port = parts.port
            except ValueError:
                # Preserve a malformed-but-stable source identity rather than
                # crashing image rotation while a ban happens to exist.
                return 'url:' + url.split('#', 1)[0]
            if port:
                host += f':{port}'
            username = parts.username or ''
            if username:  # preserve distinct authenticated resources
                host = f'{username}@{host}'
            query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                                     if k.lower() not in _EPHEMERAL_KEYS
                                     and not k.lower().startswith('utm_')))
            return 'url:' + urlunsplit((parts.scheme.lower(), host, parts.path or '/', query, ''))
        return 'url:' + url.split('#', 1)[0]
    if local:
        raw = os.fspath(local)
        if ntpath.isabs(raw):
            return 'file:' + ntpath.normcase(ntpath.normpath(raw))
        return 'file:' + os.path.normcase(os.path.abspath(raw))
    if url:
        return 'url:' + url.split('#', 1)[0]
    raise ValueError('An image ban requires a source path or URL')


class ImageBanStore:
    """One O(1) candidate lookup regardless of ban count. No background owner."""

    def __init__(self, settings_path: Path):
        self._root = Path(settings_path).parent / 'banned_images' / 'v1'
        self._active_marker = self._root / '.active'
        # No directory enumeration for a profile with no bans. Otherwise the
        # sentinel filenames (not their contents) are our startup snapshot.
        self._digests: set[str] = set()
        if self._active_marker.is_file():
            for path in self._root.glob('[0-9a-f][0-9a-f]/*.ban'):
                digest = path.stem
                if (len(digest) == 64 and digest[:2] == path.parent.name
                        and all(c in '0123456789abcdef' for c in digest)):
                    self._digests.add(digest)
        self.has_banned_images = bool(self._digests)

    @staticmethod
    def _digest(meta) -> str:
        return hashlib.sha256(canonical_image_identity(meta).encode('utf-8')).hexdigest()

    def _sentinel(self, meta) -> Path:
        key = self._digest(meta)
        return self._root / key[:2] / (key + '.ban')

    def is_banned(self, meta) -> bool:
        if not self.has_banned_images:
            return False  # No identity computation, hash or disk lookup.
        return self._digest(meta) in self._digests

    def ban(self, meta) -> bool:
        digest = self._digest(meta)
        if digest in self._digests:
            return True  # An already-banned image never writes again.
        target = self._root / digest[:2] / (digest + '.ban')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)
        self._active_marker.touch(exist_ok=True)
        # Never publish a ban in memory until persistence has succeeded.
        self._digests.add(digest)
        self.has_banned_images = True
        return True

    def clear_all(self) -> None:
        """User-initiated only. Never run from startup, refresh or rotation."""
        if self._root.exists():
            shutil.rmtree(self._root)
        self._digests.clear()
        self.has_banned_images = False

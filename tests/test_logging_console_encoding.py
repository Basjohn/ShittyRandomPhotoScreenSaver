from __future__ import annotations

import io
import logging

import pytest

from core.logging.logger import SuppressingStreamHandler


def _build_logger_with_stream(stream: io.TextIOBase) -> tuple[logging.Logger, SuppressingStreamHandler]:
    """Create an isolated logger bound to a specific text stream.

    We keep this logger separate from the root so tests do not interfere with the
    application's global logging configuration.
    """

    handler = SuppressingStreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("test_console_encoding")
    logger.handlers = []  # type: ignore[assignment]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger, handler


@pytest.mark.parametrize("encoding", ["cp1252", "latin-1"])
def test_console_handler_replaces_unencodable_characters_narrow_encodings(encoding: str) -> None:
    """Narrow console encodings should not crash on arrows/emoji.

    When the console stream cannot encode certain Unicode characters (e.g.
    arrows/emoji on Windows cp1252), the handler should fall back to replacement
    characters rather than raising UnicodeEncodeError. File logs remain
    unaffected and are outside the scope of this unit test.
    """

    raw_buffer = io.BytesIO()
    stream = io.TextIOWrapper(raw_buffer, encoding=encoding, errors="strict")

    logger, handler = _build_logger_with_stream(stream)

    msg = "Arrows \u2192 and tick \u2705"
    logger.info(msg)

    # Flush both handler and underlying stream so bytes are visible.
    handler.flush()
    stream.flush()

    data = raw_buffer.getvalue()
    # Decoding with the same encoding should now succeed because the handler
    # has already applied replacement characters for unencodable glyphs.
    text = data.decode(encoding, errors="strict")

    assert "Arrows " in text
    assert " and tick " in text
    # At least one replacement character should be present where glyphs could
    # not be represented by the console encoding.
    assert "?" in text
    # The original arrow/emoji glyphs should not survive in the narrow-encoded
    # console output.
    assert "\u2192" not in text
    assert "\u2705" not in text


def test_console_handler_preserves_unicode_on_utf8_console() -> None:
    """UTF-8 consoles should preserve full Unicode glyphs without fallback."""

    raw_buffer = io.BytesIO()
    stream = io.TextIOWrapper(raw_buffer, encoding="utf-8", errors="strict")

    logger, handler = _build_logger_with_stream(stream)

    msg = "Arrows \u2192 and tick \u2705"
    logger.info(msg)

    handler.flush()
    stream.flush()

    data = raw_buffer.getvalue()
    text = data.decode("utf-8", errors="strict")

    # Full message should round-trip with original Unicode characters intact.
    assert msg in text
    assert "?" not in text

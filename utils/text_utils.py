"""Text utility functions for string formatting and manipulation."""

import re

def smart_title_case(text: str) -> str:
    """Apply title case while preserving apostrophes correctly.
    
    Python's built-in .title() incorrectly capitalizes after apostrophes,
    turning "don't tell me" into "Don'T Tell Me". This function fixes that
    by only capitalizing the first letter of each word (space-separated).
    
    Args:
        text: Input string to convert
        
    Returns:
        Title-cased string with correct apostrophe handling
        
    Examples:
        >>> smart_title_case("don't tell me")
        "Don't Tell Me"
        >>> smart_title_case("it's a beautiful day")
        "It's A Beautiful Day"
        >>> smart_title_case("rock 'n' roll")
        "Rock 'N' Roll"
    """
    if not text:
        return text
    
    # Split by spaces to get words
    words = text.split()
    
    # Capitalize first letter of each word, leave rest as-is
    titled_words = []
    for word in words:
        if word:
            # Capitalize only the first character, preserve the rest
            titled_word = word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper()
            titled_words.append(titled_word)
    
    return ' '.join(titled_words)


# The SRPSS Title Case rule (Settings copy, buttons, buckets, the Expanded Visualizer's preset toast). Qt-free,
# so the display runtime can use it without the Settings widget stack.
# Units and abbreviations that stay as written inside Title Case copy.
_KEEP_CASE = {"px", "ms", "e.g", "i.e", "vs"}
# User data and addresses are never re-cased: URLs, drive/UNC/absolute paths,
# e-mail addresses and bare domains.
_DATA_TOKEN = re.compile(
    r"^r/|://|^[A-Za-z]:[/\\]|\\|@|^/|^www\.|\.(?:com|org|net|io|rss|xml|png|jpg|ogg|wav|mp3)\b",
    re.IGNORECASE,
)


def _capitalise(segment: str) -> str:
    for index, char in enumerate(segment):
        if char.isalpha():
            return segment[:index] + char.upper() + segment[index + 1:]
        if char.isdigit():
            return segment
    return segment


# Short joining words stay lowercase inside Title Case, as established Settings
# copy does ("Widget Glow on Hover", "Reset All Colours to Theme").
_SMALL_WORDS = frozenset({
    "a", "an", "the", "and", "but", "or", "nor", "for",
    "as", "at", "by", "in", "of", "on", "to", "via", "per", "vs",
    # Prepositions stay lowercase too ("Share Style with Main Clock").
    "with", "from", "into", "onto", "over", "under", "about", "after", "before",
    "between", "through", "without", "within", "than",
})


def title_case(text: str) -> str:
    """SRPSS copy casing: Title Case, leaving data and units alone.

    Only a word's first letter changes, so acronyms (RSS, OSD) and mixed-case
    names keep their inner capitals.  Short joining words stay lowercase except
    at the start of a sentence.  Hyphen and slash compounds capitalise each
    part ("Right-Click", "Previous/Next").  Paths, URLs and e-mail addresses
    pass through untouched.
    """
    sentence_start = [True]

    def word(match):
        token = match.group(0)
        starts = sentence_start[0]
        sentence_start[0] = token.endswith((".", "!", "?", ":"))
        bare = token.lower().strip("().,;:!?\"'")
        if bare in _KEEP_CASE or _DATA_TOKEN.search(token):
            return token
        ends = token.endswith((".", "!", "?", ":", ")", ",")) or match.end() >= len(str(text).rstrip())
        if bare in _SMALL_WORDS and not starts and not ends and not token.startswith("("):
            return token[0].lower() + token[1:] if token[:1].isupper() and token[1:].islower() else token
        return re.sub(r"[^/-]+", lambda part: _capitalise(part.group(0)), token)
    return re.sub(r"\S+", word, str(text))

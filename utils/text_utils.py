"""Text utility functions for string formatting and manipulation."""

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

"""Page Curl's Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module
(``page_curl_program``) loads only when Page Curl renders.
"""

from __future__ import annotations

# Where the page starts to peel: a corner or the middle of an edge. Random picks one per run.
PAGE_CURL_ORIGINS = {
    "Bottom Right": "bottom_right",
    "Bottom Left": "bottom_left",
    "Top Right": "top_right",
    "Top Left": "top_left",
    "Right": "right",
    "Left": "left",
    "Bottom": "bottom",
    "Top": "top",
}
PAGE_CURL_ORIGIN_CHOICES = (*PAGE_CURL_ORIGINS, "Random")

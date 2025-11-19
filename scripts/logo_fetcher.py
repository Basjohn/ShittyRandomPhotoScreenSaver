"""Generic logo downloader for the /images folder.

Usage examples (PowerShell):

    python scripts/logo_fetcher.py --url "https://example.com/spotify_logo.png" --name spotify_logo
    python scripts/logo_fetcher.py --url "https://example.com/reddit_mark.svg" --name reddit_logo

The script is deliberately simple and generic so it can be reused for
future widget logos (Spotify, Reddit, MusicBee, etc.). It does not run
automatically; you invoke it manually when you want to refresh or add
an asset.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download a logo/icon into the project's /images folder "
            "for use by widgets and UI components."
        )
    )
    parser.add_argument(
        "--url",
        required=True,
        help="HTTP(S) URL of the logo/image to download (PNG/SVG/WebP/etc.)",
    )
    parser.add_argument(
        "--name",
        required=False,
        help=(
            "Base filename to save as, without extension. "
            "Defaults to the URL path basename without its extension."
        ),
    )
    parser.add_argument(
        "--ext",
        required=False,
        help=(
            "Optional file extension override (e.g. png, svg). "
            "If omitted, the extension is inferred from the URL path; "
            "falls back to 'png' when unknown."
        ),
    )
    return parser


def _infer_name_and_ext(url: str, name: str | None, ext: str | None) -> tuple[str, str]:
    parsed = urlparse(url)
    path = parsed.path or ""
    stem = "logo"
    suffix = ""

    if path:
        last = Path(path).name
        if "." in last:
            stem = last.rsplit(".", 1)[0] or stem
            suffix = last.rsplit(".", 1)[1].lower()
        else:
            stem = last or stem

    final_name = name or stem or "logo"

    if ext:
        final_ext = ext.lstrip(".").lower() or "png"
    elif suffix:
        final_ext = suffix
    else:
        final_ext = "png"

    return final_name, final_ext


def _download_bytes(url: str, timeout: float = 15.0) -> bytes:
    with urlopen(url, timeout=timeout) as resp:  # nosec: B310 (controlled URL via CLI)
        return resp.read()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    url: str = args.url
    base_name, ext = _infer_name_and_ext(url, args.name, args.ext)

    project_root = Path(__file__).resolve().parent.parent
    images_dir = project_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    target = images_dir / f"{base_name}.{ext}"

    print(f"Downloading logo from: {url}")
    print(f"Saving to           : {target}")

    try:
        data = _download_bytes(url)
    except Exception as exc:  # pragma: no cover - network/environment dependent
        print(f"ERROR: Failed to download logo: {exc}")
        return 1

    try:
        target.write_bytes(data)
    except OSError as exc:  # pragma: no cover - filesystem dependent
        print(f"ERROR: Failed to write logo to {target}: {exc}")
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual utility
    raise SystemExit(main())

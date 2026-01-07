import re
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

INDEX_URL = "https://basmilius.github.io/weather-icons/index-fill.html"


def fetch_html(url: str) -> str:
    with urllib.request.urlopen(url) as resp:  # nosec - developer-invoked helper
        charset = resp.headers.get_content_charset() or "utf-8"
        data = resp.read()
        return data.decode(charset, errors="replace")


def extract_svg_urls(html: str, base_url: str) -> list[str]:
    # Find all href/src attributes that end in .svg
    pattern = re.compile(r"(href|src)\s*=\s*['\"]([^'\"]+?\.svg)['\"]", re.IGNORECASE)
    urls: set[str] = set()
    for _attr, ref in pattern.findall(html):
        full = urljoin(base_url, ref)
        # Prefer the line set icons; filter out obvious non-icon SVGs if needed later.
        urls.add(full)
    # Deterministic ordering for reproducibility
    return sorted(urls)


def download_svgs(urls: list[str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(urls)
    print(f"Found {total} SVG URLs. Downloading into {out_dir}...")

    for idx, url in enumerate(urls, start=1):
        name = url.split("/")[-1]
        target = out_dir / name
        try:
            with urllib.request.urlopen(url) as resp:  # nosec - developer-invoked helper
                data = resp.read()
            target.write_bytes(data)
            print(f"[{idx}/{total}] wrote {name}")
        except Exception as e:  # pragma: no cover - best-effort helper
            print(f"[{idx}/{total}] FAILED {name}: {e}")


def main() -> int:
    try:
        print(f"Fetching index: {INDEX_URL}")
        html = fetch_html(INDEX_URL)
    except Exception as e:
        print(f"Failed to fetch index page: {e}")
        return 1

    urls = extract_svg_urls(html, INDEX_URL)
    if not urls:
        print("No SVG URLs found on index page; layout may have changed.")
        return 1

    # Assume this script lives in <project>/scripts/; place icons in <project>/images/weather
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    out_dir = project_root / "images" / "weather"

    download_svgs(urls, out_dir)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

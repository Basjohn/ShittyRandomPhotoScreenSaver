"""Native feed probation harness for CUSTOM and future NEWS sources.

This tool is reporting/orchestration only. Source viability is evaluated by the
exact same ``core.feeds.probe`` seam used by Settings TEST FEED, preventing a
second network/parser implementation from drifting away from production.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.feeds.news_candidates import NEWS_CANDIDATES
from core.feeds.normalization import redacted_url_for_log
from core.feeds.probe import probe_feed_url


def probe(label: str, url: str, *, max_items: int = 50) -> dict:
    result = probe_feed_url(url, max_items=max_items)
    payload = {
        "label": label,
        "url": redacted_url_for_log(url),
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "ok": bool(result.ok),
        "elapsed_ms": round(float(result.elapsed_ms), 1),
    }
    if not result.ok:
        payload["failure"] = result.failure
        if result.final_url:
            payload["final_url"] = redacted_url_for_log(result.final_url)
        return payload
    payload.update({
        "final_url": redacted_url_for_log(result.final_url or url),
        "format": result.format,
        "title": result.title,
        "items": result.item_count,
        "actionable": result.actionable_count,
        "actionable_coverage": round(result.actionable_coverage, 3),
        "imaged": result.image_count,
        "image_coverage": round(result.image_coverage, 3),
        "newest_unix": result.newest_unix,
        "etag": bool(result.etag_present),
        "last_modified": bool(result.last_modified_present),
        "bytes": result.response_bytes,
        "feed_url": redacted_url_for_log(result.feed_url or url),
        "via": result.via,
    })
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe RSS/Atom sources through SRPSS production feed transport")
    parser.add_argument("--url", action="append", default=[], help="custom feed URL; may be supplied more than once")
    parser.add_argument("--catalog", action="store_true", help="probe all inert NEWS research candidates")
    parser.add_argument("--category", choices=("world", "us", "politics", "gaming", "tech"))
    parser.add_argument("--json", dest="json_path", help="optional output JSON path")
    args = parser.parse_args(argv)

    targets: list[tuple[str, str]] = []
    for index, url in enumerate(args.url, start=1):
        targets.append((f"custom_{index}", url))
    if args.catalog:
        for candidate in NEWS_CANDIDATES:
            if args.category and candidate.category != args.category:
                continue
            targets.append((candidate.candidate_id, candidate.url))
    if not targets:
        parser.error("provide --url or --catalog")

    results = [probe(label, url) for label, url in targets]
    for result in results:
        state = "PASS" if result["ok"] else "FAIL"
        extras = (
            f" items={result.get('items')} images={result.get('imaged')} format={result.get('format')}"
            if result["ok"] else f" failure={result.get('failure')}"
        )
        print(f"{state:4} {result['label']:<24} {result['url']}{extras}")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all(result["ok"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

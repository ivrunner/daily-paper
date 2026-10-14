"""Check every feed in feeds.yaml.  Run: python -m paper.check_feeds"""
from __future__ import annotations

from pathlib import Path

from paper.clean import find_image
from paper.fetch import FeedResult, fetch_all, load_config

ROOT = Path(__file__).resolve().parent.parent


def report_lines(results: list[FeedResult]) -> list[str]:
    lines = []
    for r in results:
        label = f"{r.feed.section_slug:<14} {r.feed.name:<28}"
        if r.error:
            lines.append(f"FAIL  {label} {r.error}")
        else:
            photos = sum(1 for e in r.entries if find_image(e))
            lines.append(f"OK    {label} {len(r.entries):>3} entries, {photos:>3} with photos")
    return lines


def main() -> int:
    results = fetch_all(load_config(ROOT / "feeds.yaml"))
    print("\n".join(report_lines(results)))
    return 1 if any(r.error for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

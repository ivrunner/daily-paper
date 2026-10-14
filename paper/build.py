"""Build today's edition and the whole site.

Run:  python -m paper.build            (writes site/)
      python -m paper.build --out /tmp/preview
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from paper.clean import dedupe, entry_to_article
from paper.edition import ET, build_edition, parse_quotes
from paper.fetch import ConfigError, FeedResult, fetch_all, load_config
from paper.models import Article, Edition
from paper.render import render_site
from paper.weather import get_weather

ROOT = Path(__file__).resolve().parent.parent
KEEP_DAYS = 30
MIN_STORIES = 10
log = logging.getLogger("paper")


def collect_articles(results: list[FeedResult], fetched_at: datetime) -> list[Article]:
    articles = []
    for result in results:
        for entry in result.entries:
            article = entry_to_article(entry, source=result.feed.name, section_slug=result.feed.section_slug,
                                       fetched_at=fetched_at)
            if article:
                articles.append(article)
    return dedupe(articles)


def _edition_dates(editions_dir: Path) -> list[date]:
    dates = []
    for path in editions_dir.glob("*.json"):
        try:
            dates.append(date.fromisoformat(path.stem))
        except ValueError:
            continue
    return dates


def load_editions(editions_dir: Path) -> list[Edition]:
    editions = []
    for day in sorted(_edition_dates(editions_dir), reverse=True):
        path = editions_dir / f"{day.isoformat()}.json"
        try:
            editions.append(Edition.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("Skipping unreadable edition %s: %s", path.name, exc)
    return editions


def launch_date(editions: list[Edition], today: date) -> date:
    """Day of issue No. 1, worked out from saved issue numbers so it survives pruning."""
    return min([today] + [e.date - timedelta(days=e.issue - 1) for e in editions])


def prune_editions(editions_dir: Path, today: date, keep_days: int = KEEP_DAYS) -> None:
    cutoff = today - timedelta(days=keep_days - 1)
    for day in _edition_dates(editions_dir):
        if day < cutoff:
            (editions_dir / f"{day.isoformat()}.json").unlink()


def write_report(results: list[FeedResult], edition: Edition | None, problem: str | None) -> None:
    failed = [r for r in results if r.error]
    lines = ["## The Daily: build report", ""]
    if problem:
        lines += [f"**Not published:** {problem}", ""]
    if edition:
        lines += [f"Edition {edition.date.isoformat()}: {edition.story_count} stories from "
                  f"{edition.source_count} sources.", ""]
    lines += [f"Feeds OK: {len(results) - len(failed)} / {len(results)}"]
    if failed:
        lines += ["", "| Section | Feed | Problem |", "|---|---|---|"]
        lines += [f"| {r.feed.section_slug} | {r.feed.name} | {r.error} |" for r in failed]
    text = "\n".join(lines) + "\n"
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)


def run(*, out: Path, editions_dir: Path, config: Path, quotes_path: Path, now: datetime | None = None,
        fetcher=fetch_all, weather_fn=get_weather) -> int:
    now = now or datetime.now(timezone.utc)
    sections = load_config(config)
    results = fetcher(sections)
    if results and all(r.error for r in results):
        write_report(results, None, "every feed failed")
        return 1
    today = now.astimezone(ET).date()
    editions_dir.mkdir(parents=True, exist_ok=True)
    launch = launch_date(load_editions(editions_dir), today)
    quotes = parse_quotes(quotes_path.read_text(encoding="utf-8")) if quotes_path.exists() else []
    edition = build_edition(collect_articles(results, now), sections=sections, now=now, launch=launch,
                            quotes=quotes, weather=weather_fn())
    if edition.story_count < MIN_STORIES:
        write_report(results, edition, f"only {edition.story_count} stories (need {MIN_STORIES})")
        return 1
    path = editions_dir / f"{edition.date.isoformat()}.json"
    path.write_text(json.dumps(edition.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    prune_editions(editions_dir, edition.date)
    render_site(load_editions(editions_dir), out)
    write_report(results, edition, None)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build The Daily.")
    parser.add_argument("--out", type=Path, default=ROOT / "site")
    parser.add_argument("--editions", type=Path, default=ROOT / "editions")
    parser.add_argument("--config", type=Path, default=ROOT / "feeds.yaml")
    parser.add_argument("--quotes", type=Path, default=ROOT / "quotes.txt")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return run(out=args.out, editions_dir=args.editions, config=args.config, quotes_path=args.quotes)
    except ConfigError as exc:
        log.error("feeds.yaml problem: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

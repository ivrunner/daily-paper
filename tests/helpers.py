"""Shared builders for tests."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from paper.models import Article

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)  # 5:00 AM EDT


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def make_entry(title: str, link: str, *, hours_ago: float = 1.0, image: str | None = None,
               summary: str = "A short summary of the story.") -> dict:
    """A dict shaped like a feedparser entry."""
    entry = {
        "title": title,
        "link": link,
        "summary": summary,
        "published_parsed": (NOW - timedelta(hours=hours_ago)).utctimetuple(),
    }
    if image:
        entry["media_content"] = [{"url": image, "medium": "image"}]
    return entry


def make_article(title: str, *, source: str = "Source", section: str = "tech",
                 hours_ago: float = 1.0, image: str | None = None, link: str | None = None,
                 also: list[str] | None = None) -> Article:
    return Article(
        title=title,
        link=link or f"https://{_slug(source)}.example/{_slug(title)}",
        summary=f"Summary of {title}.",
        source=source,
        section_slug=section,
        published=NOW - timedelta(hours=hours_ago),
        image_url=image,
        also_covered_by=list(also or []),
    )

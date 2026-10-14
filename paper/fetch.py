"""Read feeds.yaml and download every feed in parallel."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import feedparser
import requests
import yaml

TIMEOUT = 15
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/17.0 Safari/605.1.15 TheDaily/1.0")
RESERVED_SLUGS = frozenset({"static", "archive", "editions"})


class ConfigError(ValueError):
    """feeds.yaml is malformed. The message says what to fix."""


@dataclass
class FeedSpec:
    name: str
    url: str
    section_slug: str


@dataclass
class SectionSpec:
    number: int
    name: str
    slug: str
    feeds: list[FeedSpec]


@dataclass
class FeedResult:
    feed: FeedSpec
    entries: list
    error: str | None


def load_config(path: Path) -> list[SectionSpec]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" near line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError(f"feeds.yaml isn't valid YAML{where} (check indentation; use spaces, not tabs)") from exc
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise ConfigError("feeds.yaml needs a top-level 'sections' list")
    sections: list[SectionSpec] = []
    seen: set[str] = set()
    for number, raw in enumerate(data["sections"], start=1):
        if not isinstance(raw, dict):
            raise ConfigError(f"Section {number} must be a block with name, slug and feeds")
        name = raw.get("name") or f"section {number}"
        slug = raw.get("slug")
        if not slug:
            raise ConfigError(f"Section '{name}' is missing 'slug'")
        slug = str(slug)
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            raise ConfigError(f"Section '{name}': slug '{slug}' may only use a-z, 0-9 and '-'")
        if slug in RESERVED_SLUGS:
            raise ConfigError(f"Section '{name}': slug '{slug}' is reserved")
        if slug in seen:
            raise ConfigError(f"Slug '{slug}' is used twice")
        seen.add(slug)
        feeds = []
        for feed in raw.get("feeds") or []:
            if not isinstance(feed, dict) or not feed.get("name") or not feed.get("url"):
                raise ConfigError(f"A feed in section '{name}' needs a name and url")
            feeds.append(FeedSpec(name=str(feed["name"]), url=str(feed["url"]), section_slug=slug))
        sections.append(SectionSpec(number=number, name=str(name), slug=slug, feeds=feeds))
    return sections


def fetch_feed(feed: FeedSpec) -> FeedResult:
    try:
        response = requests.get(feed.url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    except Exception as exc:  # any failure only skips this one feed
        return FeedResult(feed, [], f"{type(exc).__name__}: {exc}")
    if not parsed.entries:
        return FeedResult(feed, [], "no entries")
    return FeedResult(feed, list(parsed.entries), None)


def fetch_all(sections: list[SectionSpec], max_workers: int = 12) -> list[FeedResult]:
    feeds = [feed for section in sections for feed in section.feeds]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(fetch_feed, feeds))

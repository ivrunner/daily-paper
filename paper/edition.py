"""The editor's rules: what's in the paper today and where it goes."""
from __future__ import annotations

import dataclasses
from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from paper.clean import title_words
from paper.fetch import SectionSpec
from paper.models import Article, Edition, Quote, Section, Weather

ET = ZoneInfo("America/New_York")
MAX_PER_SECTION = 12
MAX_PER_SOURCE = 5
MIN_PER_SECTION = 4
GROUP_MIN_SHARED_WORDS = 3
FRONT_SLOTS = 6
TICKER_PER_SECTION = 2


def _cap(items: list[Article]) -> list[Article]:
    per_source: Counter[str] = Counter()
    kept: list[Article] = []
    for article in items:
        if per_source[article.source] >= MAX_PER_SOURCE:
            continue
        per_source[article.source] += 1
        kept.append(article)
        if len(kept) == MAX_PER_SECTION:
            break
    return kept


def select_window(articles: list[Article], slugs: list[str], now: datetime) -> dict[str, list[Article]]:
    by_section: dict[str, list[Article]] = {slug: [] for slug in slugs}
    for article in sorted(articles, key=lambda a: a.published, reverse=True):
        if article.section_slug in by_section:
            by_section[article.section_slug].append(article)
    window = {}
    for slug, items in by_section.items():
        recent = [a for a in items if a.published >= now - timedelta(hours=24)]
        if len(recent) < MIN_PER_SECTION:
            recent = [a for a in items if a.published >= now - timedelta(hours=48)]
        window[slug] = _cap(recent)
    return window


def _related(a: Article, b: Article) -> bool:
    return len(title_words(a.title) & title_words(b.title)) >= GROUP_MIN_SHARED_WORDS


def group_stories(articles: list[Article]) -> list[list[Article]]:
    groups: list[list[Article]] = []
    for article in articles:
        for members in groups:
            if any(_related(article, m) for m in members):
                members.append(article)
                break
        else:
            groups.append([article])
    return groups


def _coverage(group: list[Article]) -> list[str]:
    sources: list[str] = []
    for article in group:
        for name in [article.source, *article.also_covered_by]:
            if name not in sources:
                sources.append(name)
    return sources


def _newest(articles: list[Article]) -> Article:
    with_image = [a for a in articles if a.image_url]
    return max(with_image or articles, key=lambda a: a.published)


def pick_top(articles: list[Article]) -> Article | None:
    """The story most sources are covering, else the newest story with a photo."""
    if not articles:
        return None
    best = max(group_stories(articles), key=lambda g: (len(_coverage(g)), max(a.published for a in g)))
    sources = _coverage(best)
    if len(sources) >= 2:
        rep = _newest(best)
        return dataclasses.replace(rep, also_covered_by=[s for s in sources if s != rep.source])
    return _newest(articles)


def _order(articles: list[Article], top: Article | None) -> list[Article]:
    if top is None:
        return []
    return [top] + [a for a in articles if a.link != top.link]


def _front_slots(sections: list[Section], lead: Article | None) -> list[Article]:
    others = [s for s in sections if not (lead and s.slug == lead.section_slug)]
    front = [s.articles[0] for s in others if s.articles]
    for s in others:  # an empty section's slot goes to another section's next story
        if len(front) >= FRONT_SLOTS:
            break
        if len(s.articles) > 1:
            front.append(s.articles[1])
    return front[:FRONT_SLOTS]


def parse_quotes(text: str) -> list[Quote]:
    quotes = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or " — " not in line:
            continue
        body, author = line.rsplit(" — ", 1)
        quotes.append(Quote(text=body.strip().strip('"“”'), author=author.strip()))
    return quotes


def quote_for(day: date, quotes: list[Quote]) -> Quote | None:
    return quotes[day.timetuple().tm_yday % len(quotes)] if quotes else None


def volume_and_issue(day: date, launch: date) -> tuple[int, int]:
    years = day.year - launch.year - ((day.month, day.day) < (launch.month, launch.day))
    return years + 1, (day - launch).days + 1


def build_edition(articles: list[Article], *, sections: list[SectionSpec], now: datetime, launch: date,
                  quotes: list[Quote], weather: Weather | None) -> Edition:
    window = select_window(articles, [s.slug for s in sections], now)
    lead = pick_top([a for items in window.values() for a in items])
    built: list[Section] = []
    for spec in sections:
        items = window[spec.slug]
        if lead and spec.slug == lead.section_slug:
            top = lead
        else:
            candidates = [a for a in items if not (lead and _related(a, lead))] or items
            top = pick_top(candidates)
        built.append(Section(number=spec.number, name=spec.name, slug=spec.slug, articles=_order(items, top)))
    front = _front_slots(built, lead)
    used = {a.link for a in front} | ({lead.link} if lead else set())
    ticker = []
    for section in built:
        ticker += [a for a in section.articles if a.link not in used][:TICKER_PER_SECTION]
    local = now.astimezone(ET)
    volume, issue = volume_and_issue(local.date(), launch)
    return Edition(date=local.date(), built_at=local, volume=volume, issue=issue, lead=lead, front=front,
                   sections=built, ticker=ticker, quote=quote_for(local.date(), quotes), weather=weather)

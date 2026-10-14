"""Turn raw feed entries into clean Article objects, and remove duplicates."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from paper.models import Article

SUMMARY_WORDS = 60
DUPLICATE_SIMILARITY = 0.6
ET = ZoneInfo("America/New_York")
STOPWORDS = frozenset("""
a about after all an and are as at be been but by can could did do does for from get gets had has have
he her his how i if in into is it its just more new not now of off on or our out over says she so than
that the their them they this to up us was we were what when where which who why will with would you your
""".split())
TRACKING_KEYS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "cmpid", "ref", "guccounter", "src"})
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
NOT_PHOTOS = ("feedburner.com", "gravatar.com", "doubleclick.net", "stats.wp.com", "pixel")
FALLBACK_DATE_FORMATS = ("%b %d, %Y %I:%M%p",)  # "Oct 13, 2026 6:57pm" (Fierce Network, Eastern)
_IMG_SRC = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)


def strip_html(text: str | None) -> str:
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def truncate_words(text: str, limit: int = SUMMARY_WORDS) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(",;:.-") + "…"


def normalize_url(url: str) -> str:
    """Comparable form of a link: no scheme, no www, no tracking params, no trailing slash."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS]
    host = parts.netloc.lower().removeprefix("www.")
    return urlunsplit(("", host, parts.path.rstrip("/"), urlencode(query), "")).lstrip("/")


def title_words(title: str) -> set[str]:
    text = title.lower().replace("’", "'").replace("'s", "")
    return {w for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS and len(w) > 1}


def similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _looks_like_image(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(IMAGE_EXTENSIONS)


def find_image(entry) -> str | None:
    candidates: list[str] = []
    for media in entry.get("media_content") or []:
        url = media.get("url", "")
        if media.get("medium") == "image" or (media.get("type") or "").startswith("image/") or _looks_like_image(url):
            candidates.append(url)
    candidates += [t.get("url", "") for t in entry.get("media_thumbnail") or []]
    for link in [*(entry.get("enclosures") or []), *(entry.get("links") or [])]:
        if (link.get("type") or "").startswith("image/"):
            candidates.append(link.get("href", ""))
    for block in entry.get("content") or []:
        candidates += _IMG_SRC.findall(block.get("value", ""))
    candidates += _IMG_SRC.findall(entry.get("summary") or "")
    for url in candidates:
        url = html.unescape(url.strip())
        if url.startswith("//"):
            url = "https:" + url
        if url.startswith(("http://", "https://")) and not any(bad in url for bad in NOT_PHOTOS):
            return url
    return None


def parse_published(entry, fallback: datetime) -> datetime:
    """Publish time in UTC; never later than `fallback` (the fetch time)."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return min(datetime(*parsed[:6], tzinfo=timezone.utc), fallback)
    raw = (entry.get("published") or entry.get("updated") or "").strip()
    for fmt in FALLBACK_DATE_FORMATS:
        try:
            local = datetime.strptime(raw, fmt).replace(tzinfo=ET)
        except ValueError:
            continue
        return min(local.astimezone(timezone.utc), fallback)
    return fallback


def entry_to_article(entry, *, source: str, section_slug: str, fetched_at: datetime) -> Article | None:
    title = strip_html(entry.get("title"))
    link = (entry.get("link") or "").strip()
    if not title or not link.startswith(("http://", "https://")):
        return None
    summary_html = entry.get("summary") or ""
    if not summary_html and entry.get("content"):
        summary_html = entry["content"][0].get("value", "")
    summary = truncate_words(strip_html(summary_html))
    if summary.lower() == title.lower():
        summary = ""
    return Article(
        title=title, link=link, summary=summary, source=source, section_slug=section_slug,
        published=parse_published(entry, fallback=fetched_at), image_url=find_image(entry),
    )

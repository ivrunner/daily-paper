from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

from paper.clean import (entry_to_article, find_image, normalize_url, parse_published, similarity,
                         strip_html, title_words, truncate_words)
from tests.helpers import NOW

FIXTURE = Path(__file__).parent / "fixtures" / "sample_rss.xml"


def test_strip_html_removes_tags_scripts_and_entities():
    assert strip_html("<p>Hi <b>there</b> &amp; you</p><script>x()</script>") == "Hi there & you"
    assert strip_html(None) == ""


def test_truncate_words():
    text = " ".join(f"w{i}" for i in range(80))
    out = truncate_words(text, 60)
    assert out.endswith("…")
    assert len(out.split()) == 60
    assert truncate_words("short text", 60) == "short text"


def test_normalize_url_drops_tracking_scheme_www_and_trailing_slash():
    a = normalize_url("https://www.site.example/story/?utm_source=x&id=7&fbclid=abc")
    b = normalize_url("http://site.example/story?id=7")
    assert a == b == "site.example/story?id=7"


def test_title_words_and_similarity():
    a = title_words("Apple's new MacBook Pro is here")
    assert a == {"apple", "macbook", "pro", "here"}
    b = title_words("New MacBook Pro from Apple is here")
    assert similarity(a, b) == 1.0
    assert similarity(set(), b) == 0.0


def test_find_image_sources_in_priority_order():
    parsed = feedparser.parse(FIXTURE)
    images = [find_image(e) for e in parsed.entries]
    assert images[0] == "https://img.sample.example/media.jpg"
    assert images[1] == "https://img.sample.example/enclosure.png"
    assert images[2] == "https://img.sample.example/inline.webp"
    assert images[3] is None


def test_find_image_skips_trackers_and_avatars():
    entry = {"summary": '<img src="https://feeds.feedburner.com/~r/x/~4/abc" width="1" height="1">'
                        '<img src="https://0.gravatar.com/avatar/z">'}
    assert find_image(entry) is None


def test_find_image_handles_protocol_relative_urls():
    assert find_image({"summary": '<img src="//cdn.example/a.jpg">'}) == "https://cdn.example/a.jpg"


def test_parse_published_fallback_format_and_future_clamp():
    fetched = NOW
    # Fierce Network's nonstandard format, Eastern time
    fierce = parse_published({"published": "Oct 13, 2026 4:30am"}, fallback=fetched)
    assert fierce == datetime(2026, 10, 13, 8, 30, tzinfo=timezone.utc)
    # future dates are clamped to fetch time
    future = (NOW + timedelta(days=2)).utctimetuple()
    assert parse_published({"published_parsed": future}, fallback=fetched) == fetched
    # missing dates fall back to fetch time
    assert parse_published({}, fallback=fetched) == fetched


def test_entry_to_article_from_real_feed():
    parsed = feedparser.parse(FIXTURE)
    articles = [entry_to_article(e, source="Sample", section_slug="tech", fetched_at=NOW) for e in parsed.entries]
    first = articles[0]
    assert first.title == "Media content story"
    assert first.summary == "First bold paragraph & more."
    assert first.published == datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)
    assert first.source == "Sample" and first.section_slug == "tech"
    assert articles[3] is None  # no link


def test_entry_to_article_drops_summary_that_repeats_title():
    entry = {"title": "Same text", "link": "https://x.example/a", "summary": "<p>Same text</p>"}
    assert entry_to_article(entry, source="S", section_slug="tech", fetched_at=NOW).summary == ""


def test_entry_to_article_strips_wordpress_appeared_first_footer():
    entry = {"title": "Judge stops deal", "link": "https://x.example/a",
             "summary": "<p>A judge blocked the deal.</p><p>The post <a href='#'>Judge stops deal</a> "
                        "appeared first on <a href='#'>Broadband Communities</a>.</p>"}
    assert entry_to_article(entry, source="S", section_slug="t", fetched_at=NOW).summary == "A judge blocked the deal."

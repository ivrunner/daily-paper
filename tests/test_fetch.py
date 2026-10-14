from pathlib import Path

import pytest
import requests

from paper import fetch
from paper.fetch import ConfigError, FeedSpec, SectionSpec, fetch_all, fetch_feed, load_config

RSS = (Path(__file__).parent / "fixtures" / "sample_rss.xml").read_bytes()


class FakeResponse:
    def __init__(self, content=b"", status=200):
        self.content, self.status_code = content, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error")


def write(tmp_path, text):
    path = tmp_path / "feeds.yaml"
    path.write_text(text)
    return path


def test_load_config_numbers_sections_in_order(tmp_path):
    path = write(tmp_path, """
sections:
  - name: Technology
    slug: technology
    feeds:
      - {name: Verge, url: "https://verge.example/rss"}
  - name: Apple
    slug: apple
    feeds: []
""")
    sections = load_config(path)
    assert [(s.number, s.slug) for s in sections] == [(1, "technology"), (2, "apple")]
    assert sections[0].feeds == [FeedSpec("Verge", "https://verge.example/rss", "technology")]


@pytest.mark.parametrize("body, message", [
    ("sections:\n  - name: X\n    feeds: []\n", "missing 'slug'"),
    ("sections:\n  - {name: A, slug: Bad Slug}\n", "Bad Slug"),
    ("sections:\n  - {name: A, slug: static}\n", "reserved"),
    ("sections:\n  - {name: A, slug: a}\n  - {name: B, slug: a}\n", "used twice"),
    ("sections:\n  - name: A\n    slug: a\n    feeds:\n      - {name: X}\n", "needs a name and url"),
    ("nothing: here\n", "top-level 'sections'"),
])
def test_load_config_rejects_bad_slugs(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, body))


def test_fetch_feed_success(monkeypatch):
    monkeypatch.setattr(fetch.requests, "get", lambda url, **kw: FakeResponse(RSS))
    result = fetch_feed(FeedSpec("Sample", "https://s.example/rss", "tech"))
    assert result.error is None
    assert len(result.entries) == 4


def test_fetch_feed_reports_http_errors_and_empty_feeds(monkeypatch):
    monkeypatch.setattr(fetch.requests, "get", lambda url, **kw: FakeResponse(status=403))
    assert "403" in fetch_feed(FeedSpec("X", "https://x.example", "tech")).error
    monkeypatch.setattr(fetch.requests, "get", lambda url, **kw: FakeResponse(b"<html>not a feed</html>"))
    assert "no entries" in fetch_feed(FeedSpec("X", "https://x.example", "tech")).error


def test_one_timeout_does_not_stop_the_others(monkeypatch):
    def fake_get(url, **kw):
        assert kw["timeout"] == fetch.TIMEOUT and "User-Agent" in kw["headers"]
        if "slow" in url:
            raise requests.Timeout("timed out")
        return FakeResponse(RSS)

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    section = SectionSpec(1, "Tech", "tech", [
        FeedSpec("Slow", "https://slow.example", "tech"),
        FeedSpec("Fast", "https://fast.example", "tech"),
    ])
    results = fetch_all([section])
    assert [r.feed.name for r in results] == ["Slow", "Fast"]
    assert "Timeout" in results[0].error
    assert results[1].error is None and len(results[1].entries) == 4


@pytest.mark.parametrize("body, message", [
    ("sections:\n  - name: A\n\tslug: a\n", "line"),          # tab / bad indent → YAML syntax error
    ("sections:\n  - Apple\n", "Section 1"),                  # section written as a bare word
])
def test_load_config_explains_yaml_typos(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, body))

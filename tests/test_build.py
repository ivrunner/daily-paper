import json
from datetime import date, timedelta
from pathlib import Path

from paper.build import run
from paper.check_feeds import report_lines
from paper.fetch import FeedResult, FeedSpec
from tests.helpers import NOW, make_entry

FEEDS_YAML = """
sections:
  - name: Technology
    slug: technology
    feeds:
      - {name: Alpha, url: "https://alpha.example/rss"}
      - {name: Beta, url: "https://beta.example/rss"}
  - name: Apple
    slug: apple
    feeds:
      - {name: Gamma, url: "https://gamma.example/rss"}
"""


def fake_fetcher(sections):
    results = []
    for s in sections:
        for f in s.feeds:
            entries = [make_entry(f"Story x{f.name}{i} y{i}{f.name} z{f.name}{i}k", f"https://{f.name.lower()}.example/{i}",
                                  hours_ago=i + 1, image=f"https://img.example/{f.name}{i}.jpg" if i % 2 == 0 else None)
                       for i in range(6)]
            results.append(FeedResult(f, entries, None))
    return results


def failing_fetcher(sections):
    return [FeedResult(f, [], "ConnectionError: down") for s in sections for f in s.feeds]


def setup(tmp_path):
    config = tmp_path / "feeds.yaml"
    config.write_text(FEEDS_YAML)
    quotes = tmp_path / "quotes.txt"
    quotes.write_text("Be quick, but don't hurry. — John Wooden\n")
    return dict(out=tmp_path / "site", editions_dir=tmp_path / "editions", config=config, quotes_path=quotes)


def test_build_publishes_and_saves_edition(tmp_path):
    paths = setup(tmp_path)
    code = run(**paths, now=NOW, fetcher=fake_fetcher, weather_fn=lambda: None)
    assert code == 0
    saved = json.loads((paths["editions_dir"] / "2026-10-13.json").read_text())
    assert saved["issue"] == 1
    assert (paths["out"] / "index.html").exists()
    assert (paths["out"] / "editions/2026-10-13/apple/index.html").exists()


def test_build_refuses_when_every_feed_fails(tmp_path):
    paths = setup(tmp_path)
    assert run(**paths, now=NOW, fetcher=failing_fetcher, weather_fn=lambda: None) == 1
    assert not paths["out"].exists()
    assert not (paths["editions_dir"] / "2026-10-13.json").exists()


def test_build_refuses_thin_edition(tmp_path):
    paths = setup(tmp_path)

    def thin(sections):
        f = sections[0].feeds[0]
        return [FeedResult(f, [make_entry("Only one story here", "https://a.example/1")], None)]

    assert run(**paths, now=NOW, fetcher=thin, weather_fn=lambda: None) == 1


def test_prunes_to_30_days_and_counts_issue_from_first_edition(tmp_path):
    paths = setup(tmp_path)
    for days in (5, 29, 30, 45):
        run(**paths, now=NOW - timedelta(days=days), fetcher=fake_fetcher, weather_fn=lambda: None)
    run(**paths, now=NOW, fetcher=fake_fetcher, weather_fn=lambda: None)
    kept = sorted(p.stem for p in paths["editions_dir"].glob("*.json"))
    assert kept == ["2026-09-14", "2026-10-08", "2026-10-13"]  # 29 and 5 days ago + today
    today = json.loads((paths["editions_dir"] / "2026-10-13.json").read_text())
    assert today["issue"] == 46  # first edition was 45 days earlier


def test_corrupt_saved_edition_is_skipped(tmp_path):
    paths = setup(tmp_path)
    paths["editions_dir"].mkdir()
    (paths["editions_dir"] / "2026-10-12.json").write_text("{not json")
    assert run(**paths, now=NOW, fetcher=fake_fetcher, weather_fn=lambda: None) == 0


def test_report_lines():
    ok = FeedResult(FeedSpec("Alpha", "u", "technology"),
                    [make_entry("A", "https://a/1", image="https://i/a.jpg"), make_entry("B", "https://a/2")], None)
    bad = FeedResult(FeedSpec("Beta", "u", "technology"), [], "HTTPError: 403")
    lines = report_lines([ok, bad])
    assert lines[0].startswith("OK") and "2 entries" in lines[0] and "1 with photos" in lines[0]
    assert lines[1].startswith("FAIL") and "403" in lines[1]

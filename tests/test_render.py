import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from paper.edition import build_edition
from paper.fetch import SectionSpec
from paper.models import Quote, Weather
from paper.render import render_site
from tests.helpers import NOW, make_article

SPECS = [SectionSpec(1, "Technology", "technology", []), SectionSpec(2, "Apple", "apple", []),
         SectionSpec(3, "Video Games", "video-games", [])]


def _edition(day_offset=0, empty_games=False):
    arts = [make_article(f"Tech {i} item tok{i}", source=f"T{i}", section="technology", hours_ago=i + 1,
                         image="https://img.example/t.jpg" if i % 2 == 0 else None) for i in range(6)]
    arts += [make_article(f"Apple {i} thing ap{i}", source=f"A{i}", section="apple", hours_ago=i + 1) for i in range(5)]
    if not empty_games:
        arts += [make_article(f"Game {i} news g{i}", source=f"G{i}", section="video-games", hours_ago=i + 1)
                 for i in range(3)]
    now = NOW - timedelta(days=day_offset)
    arts = [a.__class__(**{**a.__dict__, "published": a.published - timedelta(days=day_offset)}) for a in arts]
    return build_edition(arts, sections=SPECS, now=now, launch=date(2026, 10, 1),
                         quotes=[Quote("Real artists ship.", "Steve Jobs")],
                         weather=Weather("Fort Wayne", 71, 52, "Partly cloudy", "partly"))


def _internal_links(page: Path):
    html = page.read_text()
    for url in re.findall(r'(?:href|src)="([^"]+)"', html):
        if not url.startswith(("http://", "https://", "#", "mailto:")):
            yield url


@pytest.fixture
def site(tmp_path):
    out = tmp_path / "site"
    render_site([_edition(0, empty_games=True), _edition(1)], out)
    return out


def test_expected_pages_exist(site):
    for rel in ["index.html", "technology/index.html", "apple/index.html", "video-games/index.html",
                "archive/index.html", "editions/2026-10-13/index.html", "editions/2026-10-12/apple/index.html",
                "static/the-daily.css", "static/manifest.webmanifest", "static/apple-touch-icon.png"]:
        assert (site / rel).exists(), rel


def test_every_internal_link_resolves(site):
    for page in site.rglob("*.html"):
        for url in _internal_links(page):
            assert not url.startswith("/"), f"{page}: absolute link {url}"
            target = (page.parent / url.split("#")[0]).resolve()
            assert target.exists(), f"{page.relative_to(site)} → {url}"


def test_front_page_content(site):
    html = (site / "index.html").read_text()
    assert "The Daily" in html and "Tech · Sport · Fiber · Play" in html
    assert "Tuesday, October 13, 2026" in html
    assert "Fort Wayne" in html and "71°" in html
    assert "Real artists ship." in html
    assert "Lead story" in html
    assert "{{" not in html and "{%" not in html


def test_empty_section_message(site):
    assert "No new stories in this section today." in (site / "video-games/index.html").read_text()


def test_photos_have_fallback_and_no_referrer(site):
    html = (site / "technology/index.html").read_text()
    imgs = re.findall(r"<img [^>]+>", html)
    assert imgs
    for tag in imgs:
        assert 'onerror="this.parentElement.remove()"' in tag
        assert 'referrerpolicy="no-referrer"' in tag
        assert 'loading="lazy"' in tag


def test_titles_are_escaped(tmp_path):
    ed = _edition()
    ed.sections[0].articles[0].title = "<script>alert(1)</script> & co"
    render_site([ed], tmp_path / "s")
    html = (tmp_path / "s/technology/index.html").read_text()
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html


def test_refuses_to_clear_a_non_site_folder(tmp_path):
    (tmp_path / "important.txt").write_text("keep me")
    with pytest.raises(ValueError):
        render_site([_edition()], tmp_path)
    assert (tmp_path / "important.txt").exists()


def test_rerender_replaces_old_site(tmp_path):
    out = tmp_path / "site"
    render_site([_edition()], out)
    (out / "stale.html").write_text("old")
    render_site([_edition()], out)
    assert not (out / "stale.html").exists()


def test_lead_uses_two_columns_only_for_long_summaries(tmp_path):
    ed = _edition()
    render_site([ed], tmp_path / "short")
    assert "two-col" not in (tmp_path / "short/index.html").read_text()
    ed.lead.summary = " ".join(["word"] * 50)
    render_site([ed], tmp_path / "long")
    assert 'class="lead-body two-col"' in (tmp_path / "long/index.html").read_text()

from datetime import date

from paper.edition import (build_edition, group_stories, parse_quotes, pick_top, quote_for, select_window,
                           volume_and_issue)
from paper.fetch import SectionSpec
from paper.models import Quote
from tests.helpers import NOW, make_article

SLUGS = ["tech", "apple", "sports", "endurance", "leadership", "fiber", "games"]
SPECS = [SectionSpec(i + 1, s.title(), s, []) for i, s in enumerate(SLUGS)]


def test_window_24h_then_48h_fallback_and_caps():
    busy = [make_article(f"Tech item {i} unique{i}", source=f"S{i % 3}", section="tech", hours_ago=i + 0.5)
            for i in range(20)]
    thin = [make_article("Apple one alpha", section="apple", hours_ago=30),
            make_article("Apple two beta", section="apple", hours_ago=40),
            make_article("Apple three gamma", section="apple", hours_ago=60)]
    window = select_window(busy + thin, ["tech", "apple", "games"], NOW)
    assert len(window["tech"]) == 12
    assert [a.title for a in window["apple"]] == ["Apple one alpha", "Apple two beta"]  # 48h, not 60h
    assert window["games"] == []


def test_window_caps_any_one_source_at_five():
    flood = [make_article(f"Flood story {i} word{i}", source="9to5Mac", section="apple", hours_ago=i * 0.1 + 0.1)
             for i in range(10)]
    other = [make_article("Other story zeta", source="MacRumors", section="apple", hours_ago=5)]
    window = select_window(flood + other, ["apple"], NOW)
    assert sum(a.source == "9to5Mac" for a in window["apple"]) == 5
    assert any(a.source == "MacRumors" for a in window["apple"])


def test_group_stories_needs_three_shared_words():
    a = make_article("Apple MacBook Pro M6 launch event")
    b = make_article("MacBook Pro M6 reviews are in")
    c = make_article("Apple Watch gets update")
    groups = group_stories([a, b, c])
    assert [len(g) for g in groups] == [2, 1]


def test_pick_top_prefers_widest_coverage():
    big = [make_article("MacBook Pro M6 launch details", source="A", hours_ago=3),
           make_article("MacBook Pro M6 launch hands-on", source="B", hours_ago=2, image="https://i/x.jpg"),
           make_article("MacBook Pro M6 launch pricing", source="C", hours_ago=4)]
    newest = make_article("Unrelated newest story", source="D", hours_ago=0.5, image="https://i/y.jpg")
    top = pick_top(big + [newest])
    assert top.source == "B"  # newest with image inside the biggest group
    assert top.also_covered_by == ["A", "C"]


def test_pick_top_falls_back_to_newest_with_image():
    a = make_article("Alpha story one", source="A", hours_ago=1)
    b = make_article("Beta story two", source="B", hours_ago=2, image="https://i/b.jpg")
    assert pick_top([a, b]).title == "Beta story two"
    assert pick_top([a]).title == "Alpha story one"
    assert pick_top([]) is None


def _full_day():
    arts = []
    for i, slug in enumerate(SLUGS):
        for j in range(4):
            arts.append(make_article(f"{slug} headline {j} token{i}x{j}", source=f"{slug}-src{j}",
                                     section=slug, hours_ago=j + 1 + i * 0.1, image=f"https://i/{slug}{j}.jpg"))
    return arts


def test_build_edition_front_page_slots_and_ticker():
    arts = _full_day()
    arts += [make_article("MacBook Pro M6 launch event recap", source="MacRumors", section="apple", hours_ago=2),
             make_article("MacBook Pro M6 launch event analysis", source="9to5Mac", section="apple", hours_ago=1.5)]
    ed = build_edition(arts, sections=SPECS, now=NOW, launch=date(2026, 10, 11), quotes=[Quote("Q", "A")],
                       weather=None)
    assert ed.lead.section_slug == "apple"
    assert ed.sections[1].articles[0].link == ed.lead.link  # lead tops its own section
    assert len(ed.front) == 6
    assert {a.section_slug for a in ed.front} == set(SLUGS) - {"apple"}
    front_links = {a.link for a in ed.front} | {ed.lead.link}
    assert not front_links & {a.link for a in ed.ticker}
    assert len(ed.ticker) == 14
    assert (ed.volume, ed.issue) == (1, 3)
    assert ed.date == date(2026, 10, 13)
    assert ed.built_at.utcoffset().total_seconds() == -4 * 3600


def test_lead_story_not_repeated_on_front_page():
    arts = _full_day()
    arts += [make_article("MacBook Pro M6 launch event recap", source="MacRumors", section="apple", hours_ago=2),
             make_article("MacBook Pro M6 launch event takeaways", source="9to5Mac", section="apple", hours_ago=1.5),
             make_article("MacBook Pro M6 launch event live", source="Verge", section="tech", hours_ago=0.2,
                          image="https://i/v.jpg")]
    ed = build_edition(arts, sections=SPECS, now=NOW, launch=date(2026, 10, 13), quotes=[], weather=None)
    # widest coverage (3 sources); Verge is the newest version with a photo, so the lead sits in tech
    assert ed.lead.source == "Verge" and ed.lead.also_covered_by == ["9to5Mac", "MacRumors"]
    apple_slot = next(a for a in ed.front if a.section_slug == "apple")
    assert "MacBook" not in apple_slot.title
    assert all("MacBook" not in a.title for a in ed.front)
    assert ed.quote is None


def test_empty_section_slot_is_filled_by_another_sections_second_story():
    arts = [a for a in _full_day() if a.section_slug != "games"]
    ed = build_edition(arts, sections=SPECS, now=NOW, launch=date(2026, 10, 13), quotes=[], weather=None)
    assert len(ed.front) == 6
    assert ed.sections[6].articles == []


def test_quotes_parse_and_rotate():
    quotes = parse_quotes("# comment\n\nBe quick, but don't hurry. — John Wooden\n“Real artists ship.” — Steve Jobs\nbad line\n")
    assert quotes == [Quote("Be quick, but don't hurry.", "John Wooden"), Quote("Real artists ship.", "Steve Jobs")]
    assert quote_for(date(2026, 1, 1), quotes) == quotes[1]  # day 1 % 2
    assert quote_for(date(2026, 1, 2), quotes) == quotes[0]
    assert quote_for(date(2026, 1, 2), []) is None


def test_volume_and_issue():
    launch = date(2026, 10, 13)
    assert volume_and_issue(launch, launch) == (1, 1)
    assert volume_and_issue(date(2027, 10, 12), launch) == (1, 365)
    assert volume_and_issue(date(2027, 10, 13), launch) == (2, 366)

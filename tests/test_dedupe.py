from paper.clean import dedupe
from tests.helpers import make_article


def test_same_link_with_tracking_is_merged():
    a = make_article("Story", source="A", link="https://site.example/x?utm_source=rss", hours_ago=1)
    b = make_article("Story (updated)", source="B", link="https://www.site.example/x/", hours_ago=2)
    out = dedupe([a, b])
    assert len(out) == 1
    assert out[0].source == "A" and out[0].also_covered_by == ["B"]


def test_near_identical_titles_merge_and_photo_version_wins():
    plain = make_article("Apple unveils new MacBook Pro with M6 chip", source="A", hours_ago=1)
    photo = make_article("Apple unveils MacBook Pro with new M6 chip", source="B", hours_ago=2,
                         image="https://img.example/p.jpg")
    out = dedupe([plain, photo])
    assert len(out) == 1
    assert out[0].source == "B"
    assert out[0].image_url == "https://img.example/p.jpg"
    assert out[0].also_covered_by == ["A"]


def test_different_stories_are_kept_newest_first():
    old = make_article("Fiber grants announced in Ohio", hours_ago=5)
    new = make_article("Playoff race tightens after weekend", hours_ago=1)
    assert [a.title for a in dedupe([old, new])] == [new.title, old.title]


def test_three_way_merge_lists_each_source_once():
    a = make_article("Big launch event today recap", source="A", hours_ago=1)
    b = make_article("Big launch event today recap", source="B", hours_ago=2)
    c = make_article("Big launch event today recap", source="A", hours_ago=3, link="https://other.example/c")
    out = dedupe([a, b, c])
    assert len(out) == 1
    assert out[0].also_covered_by == ["B"]

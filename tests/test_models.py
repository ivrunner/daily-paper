from datetime import date

from paper.models import Article, Edition, Quote, Section, Weather
from tests.helpers import NOW, make_article


def test_article_round_trip():
    a = make_article("Hello world", image="https://img.example/a.jpg", also=["Other"])
    assert Article.from_dict(a.to_dict()) == a


def test_section_top_and_sources():
    s = Section(number=1, name="Tech", slug="tech", articles=[
        make_article("One", source="B"), make_article("Two", source="A"), make_article("Three", source="B")])
    assert s.top.title == "One"
    assert s.sources == ["A", "B"]
    assert Section(number=2, name="X", slug="x", articles=[]).top is None


def test_edition_round_trip_and_counts():
    a1 = make_article("Lead", source="A", section="tech")
    a2 = make_article("Second", source="B", section="apple")
    edition = Edition(
        date=date(2026, 10, 13), built_at=NOW, volume=1, issue=3, lead=a1, front=[a2],
        sections=[Section(1, "Tech", "tech", [a1]), Section(2, "Apple", "apple", [a2])],
        ticker=[a2], quote=Quote("Be quick, but don't hurry.", "John Wooden"),
        weather=Weather(place="Fort Wayne", high_f=71, low_f=52, label="Partly cloudy", icon="partly"),
    )
    assert edition.story_count == 2
    assert edition.source_count == 2
    assert Edition.from_dict(edition.to_dict()) == edition


def test_edition_round_trip_without_optional_parts():
    edition = Edition(date=date(2026, 10, 13), built_at=NOW, volume=1, issue=1, lead=None, front=[],
                      sections=[], ticker=[], quote=None, weather=None)
    assert Edition.from_dict(edition.to_dict()) == edition

"""Data types shared by every step of the build."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime


@dataclass
class Article:
    title: str
    link: str
    summary: str
    source: str
    section_slug: str
    published: datetime  # timezone-aware, UTC
    image_url: str | None = None
    also_covered_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["published"] = self.published.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Article:
        return cls(**{**data, "published": datetime.fromisoformat(data["published"])})


@dataclass
class Weather:
    place: str
    high_f: int
    low_f: int
    label: str
    icon: str  # one of: sun, partly, cloud, fog, rain, snow, storm

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Weather:
        return cls(**data)


@dataclass
class Quote:
    text: str
    author: str


@dataclass
class Section:
    number: int
    name: str
    slug: str
    articles: list[Article]  # articles[0] is the section's top story

    @property
    def top(self) -> Article | None:
        return self.articles[0] if self.articles else None

    @property
    def sources(self) -> list[str]:
        return sorted({a.source for a in self.articles})


@dataclass
class Edition:
    date: date
    built_at: datetime  # timezone-aware, America/New_York
    volume: int
    issue: int
    lead: Article | None
    front: list[Article]
    sections: list[Section]
    ticker: list[Article]
    quote: Quote | None
    weather: Weather | None

    @property
    def story_count(self) -> int:
        return sum(len(s.articles) for s in self.sections)

    @property
    def source_count(self) -> int:
        return len({a.source for s in self.sections for a in s.articles})

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "built_at": self.built_at.isoformat(),
            "volume": self.volume,
            "issue": self.issue,
            "lead": self.lead.to_dict() if self.lead else None,
            "front": [a.to_dict() for a in self.front],
            "sections": [
                {"number": s.number, "name": s.name, "slug": s.slug,
                 "articles": [a.to_dict() for a in s.articles]}
                for s in self.sections
            ],
            "ticker": [a.to_dict() for a in self.ticker],
            "quote": asdict(self.quote) if self.quote else None,
            "weather": self.weather.to_dict() if self.weather else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Edition:
        return cls(
            date=date.fromisoformat(data["date"]),
            built_at=datetime.fromisoformat(data["built_at"]),
            volume=data["volume"],
            issue=data["issue"],
            lead=Article.from_dict(data["lead"]) if data["lead"] else None,
            front=[Article.from_dict(a) for a in data["front"]],
            sections=[
                Section(number=s["number"], name=s["name"], slug=s["slug"],
                        articles=[Article.from_dict(a) for a in s["articles"]])
                for s in data["sections"]
            ],
            ticker=[Article.from_dict(a) for a in data["ticker"]],
            quote=Quote(**data["quote"]) if data["quote"] else None,
            weather=Weather.from_dict(data["weather"]) if data["weather"] else None,
        )

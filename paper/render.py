"""Turn editions into the static website."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from paper.clean import truncate_words
from paper.models import Edition

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
MARKER = ".the-daily-site"


def make_env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]),
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    env.filters["longdate"] = lambda d: f"{d:%A}, {d:%B} {d.day}, {d.year}"
    env.filters["shortdate"] = lambda d: f"{d:%b} {d.day}"
    env.filters["clock"] = lambda dt: f"{dt:%I:%M %p}".lstrip("0") + " ET"
    env.filters["words"] = truncate_words
    return env


def _prefix(target: Path, page_dir: Path) -> str:
    """Relative path from page_dir to target, with a trailing slash ('' when they're the same)."""
    rel = os.path.relpath(target, page_dir)
    return "" if rel == "." else rel.replace(os.sep, "/") + "/"


def _write(env: Environment, template: str, page_dir: Path, site_dir: Path, home_dir: Path, **context) -> None:
    page_dir.mkdir(parents=True, exist_ok=True)
    html = env.get_template(template).render(root=_prefix(site_dir, page_dir), home=_prefix(home_dir, page_dir),
                                             **context)
    (page_dir / "index.html").write_text(html, encoding="utf-8")


def render_edition(env: Environment, edition: Edition, edition_dir: Path, site_dir: Path, *, is_today: bool) -> None:
    names = {s.slug: s.name for s in edition.sections}
    common = {"edition": edition, "names": names, "is_today": is_today}
    _write(env, "front.html", edition_dir, site_dir, edition_dir, **common)
    for i, section in enumerate(edition.sections):
        prev = edition.sections[i - 1] if i > 0 else None
        nxt = edition.sections[i + 1] if i + 1 < len(edition.sections) else None
        _write(env, "section.html", edition_dir / section.slug, site_dir, edition_dir,
               section=section, prev=prev, next=nxt, **common)


def _reset(site_dir: Path) -> None:
    if site_dir.exists():
        if any(site_dir.iterdir()) and not (site_dir / MARKER).exists():
            raise ValueError(f"Refusing to clear {site_dir}: it isn't a folder The Daily built")
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    (site_dir / MARKER).write_text("Built by paper.render; safe to delete.\n")


def render_site(editions: list[Edition], site_dir: Path) -> None:
    """editions are newest first. Today's goes at the root; every edition also lives under editions/<date>/."""
    site_dir = Path(site_dir)
    _reset(site_dir)
    shutil.copytree(STATIC, site_dir / "static")
    env = make_env()
    if editions:
        render_edition(env, editions[0], site_dir, site_dir, is_today=True)
    for edition in editions:
        render_edition(env, edition, site_dir / "editions" / edition.date.isoformat(), site_dir, is_today=False)
    _write(env, "archive.html", site_dir / "archive", site_dir, site_dir, editions=editions)

# The Daily — Design Spec

**Date:** 2026-10-13
**Status:** Draft for review

## 1. Purpose

A personal, automatically built daily newspaper called **The Daily**. It has a real newspaper look and feel and pulls headlines from free news sources on the owner's interests. It's read every morning in Safari, or as a Home Screen / Dock web app, on iPhone, iPad and Mac.

**Success criteria**
- A new edition is live by about 5:15 AM Eastern every day with no manual steps.
- It reads comfortably and looks like a newspaper on all three device sizes.
- Changing sources means editing one file (`feeds.yaml`), which can be done from github.com on any device.
- One broken source never stops the paper from being published.
- Running cost is $0.

**Out of scope for v1:** AI summaries and editing (planned as a later add-on), a native app, offline reading, dark mode, push notifications, full article text (every story links out to the source).

## 2. Decisions made

| Topic | Decision |
|---|---|
| Delivery | Static website, rebuilt daily by GitHub Actions, hosted on GitHub Pages from a **public** repo |
| Story selection | Rules only, no AI (option 1) |
| Schedule | 5:00 AM America/New_York, all year |
| Name | **The Daily** |
| Weather | Fort Wayne, IN 46845, via Open-Meteo (free, no key) |
| Visual style | Approved mockups: `docs/mockups/front-page.html` (draft 4, lighter newsprint) and `docs/mockups/section-page.html` |

## 3. Sections and sources

Each section maps to a page. Every feed URL below was tested on 2026-10-13. Telecompetitor and Fierce's own site block automated requests, First Round Review no longer publishes a feed, and HBR's feed is down, so those were replaced as shown. `feeds.yaml` records the final URLs.

| # | Section | Sources |
|---|---|---|
| 01 | Technology | The Verge, Ars Technica, TechCrunch |
| 02 | Apple | MacRumors, 9to5Mac, AppleInsider, Six Colors |
| 03 | Sports | ESPN, CBS Sports, Yahoo Sports |
| 04 | Endurance | iRunFar, DC Rainmaker, Triathlete, Canadian Running |
| 05 | Leadership | Fast Company (Leadership), MIT Sloan Management Review, Seth Godin |
| 06 | Fiber & Telecom | Broadband Breakfast, Light Reading, Fierce Network (via its FeedBurner feed), Broadband Communities |
| 07 | Video Games | Polygon, IGN, Eurogamer, Rock Paper Shotgun |

`feeds.yaml` shape:

```yaml
sections:
  - name: Apple
    slug: apple
    feeds:
      - name: MacRumors
        url: https://feeds.macrumors.com/MacRumors-All
```

The order of sections in the file sets the section numbers (01–07) and the order of pages.

## 4. Architecture

```
GitHub Actions (cron) ──► paper/build.py
                             │
   feeds.yaml ──► fetch ──► clean ──► edition ──► render ──► site/  ──► GitHub Pages
   Open-Meteo ──► weather ──────────────┘   │
   quotes.txt ──────────────────────────────┘
                                            └──► editions/YYYY-MM-DD.json (committed)
```

**Stack:** Python 3.12 in CI (3.11+ supported locally), `feedparser`, `requests`, `Jinja2`, `PyYAML`, `pytest`. Output is plain HTML and CSS: no JavaScript framework and no build tools.

### Units

| File | Job | Input → Output |
|---|---|---|
| `paper/fetch.py` | Download each feed in parallel with a 15s timeout and a browser-like User-Agent. Each failure is caught and logged. | `feeds.yaml` → list of raw entries + list of failed feeds |
| `paper/clean.py` | Normalize each entry into an `Article`. Remove HTML from summaries and cut them to about 60 words. Find the image (media:content, media:thumbnail, enclosure, or first `<img>` in content). Throw out entries with no title or link. Remove duplicates. | raw entries → `list[Article]` |
| `paper/edition.py` | Choose the time window, group stories, pick the lead story, fill each section, and choose the ticker headlines and the quote of the day | `list[Article]` + weather + quotes → `Edition` |
| `paper/weather.py` | Get today's forecast (high, low, conditions code) for lat 41.17, lon −85.10. Returns `None` on failure. | → `Weather \| None` |
| `paper/render.py` | Turn an `Edition` into pages using the Jinja templates. Copy the static files over. Build the archive index. | `Edition`(s) → `site/` |
| `paper/build.py` | Runs the steps in order. Saves `editions/<date>.json`, deletes edition files older than 30 days, and redraws every saved edition. | CLI entry point |
| `paper/models.py` | Data classes: `Article`, `Section`, `Edition`, `Weather` | — |

`Article` fields: `title, link, summary, image_url | None, source, section_slug, published (UTC datetime)`.

## 5. Edition rules

**Time window:** articles published in the last 24 hours before build time. If a section has fewer than 4, that section looks back 48 hours. Articles with no date count as published at fetch time, and dates in the future are clamped to fetch time. Fierce Network's FeedBurner feed uses a nonstandard date format (`Oct 13, 2026 6:57pm`, Eastern), which is parsed explicitly. Each section keeps at most 12 articles, newest first, and **at most 5 from any one source**, so high-volume sites like 9to5Mac can't crowd out the others.

**Removing duplicates:**
- Two articles are the same if their links match after stripping query strings, tracking parameters and the trailing `/`.
- Two articles are also the same if their titles share ≥ 60% of their meaningful words (lowercased, with common filler words removed; overlap measured as Jaccard similarity).
- When articles are merged, the version with an image wins. The other sources go into the `also_covered_by` list.

**Story groups (shared coverage):** across all sections, articles whose titles share at least 3 meaningful words go into the same group. A group's *coverage* is the number of different sources in it.

**Lead story:** the group with the most coverage, if it has ≥ 2 sources. Ties go to the newest. Its representative article is the newest one with an image, or the newest one if none has an image. If no group has ≥ 2 sources, the lead is the newest article with an image from any section. The lead story's page lists every source that covered it.

**Section top story:** chosen the same way as the lead, but only within the section. Articles about the same story as the lead are passed over when choosing other sections' top stories, so the lead never appears twice on the front page. On the front page, the lead stands in for its own section, so the 6 other sections fill the 6 remaining story slots.

**Front page slots** (matches the mockup):
- Lead: big photo, headline, italic summary line, two-column summary with a large first letter, sources.
- Right column: 2 section top stories (the first text-only, the second with a photo when one exists), then the quote of the day.
- Bottom row: the remaining 4 section top stories.
- Ticker: the next 2 headlines from each section, 14 total.

A front-page slot that calls for a photo falls back to a text-only layout when its article has none.

**Section page** (matches the mockup): the top story is featured, the next 3 get cards, and the rest go in an "In brief" two-column list. The top story's callout box shows the other sites that covered it, when there are any. If a section has no articles, its page says "No new stories in this section today." and the front page's slot for that section goes to the next section's second story.

**Quote of the day:** `quotes.txt` holds one `quote — author` per line, and the quote is picked by day-of-year mod line count. The project starts with about 70 well-attributed quotes on leadership, sport and endurance.

**Issue number:** "Vol. 1 · No. N", where N is the number of days since the first edition plus 1. The volume goes up by one each year on the launch anniversary.

**Masthead details:** the date, "Morning Edition", the issue number, the weather box (on the left), and today's counts on the right ("68 stories from 25 sources · Built 5:04 AM ET"). The tagline is "Tech · Sport · Fiber · Play".

## 6. Visual design

The approved mockups in `docs/mockups/` are the reference. Key details:

- **Paper:** `#f1ede4`, with a light fractal-noise grain (~0.28 opacity) and faint fiber layers drawn by inline SVG backgrounds. No image files are needed for the texture. The strength of the texture is controlled by one CSS variable so it can be adjusted later.
- **Ink:** `#1d1b18`, with a slight text-shadow for ink bleed. **Accent:** `#d9661b`, used for section labels, the sun icon and quote marks.
- **Type:** DM Serif Display (masthead and headlines), Source Serif 4 (body and italic summaries), Space Grotesk (labels, small print, ticker), Bodoni Moda (temperature and issue number). All come from Google Fonts.
- **Photos:** loaded directly from the source sites with `loading="lazy"`. CSS makes them grayscale, adds contrast and a hint of sepia, and lays a halftone dot pattern over them. An `onerror` handler switches a card to its text-only layout if the photo fails to load.
- **Rules:** a double line under the masthead, 1px lines around every column, and lighter 35% lines inside columns.
- **Ticker:** a CSS-only scrolling band. It stops scrolling and shows the headlines as a static list when the device's "reduce motion" setting is on.
- **Responsive layout:**
  - **≥ 1024px:** the full grid from the mockup.
  - **768–1023px (iPad portrait):** the sidebar becomes a row of section tabs, the lead spans the full width, and the right column moves below it.
  - **< 768px (iPhone):** single column, section tabs scroll sideways, and photos become thumbnails next to the headlines, as in the phone mockup. The masthead shrinks to about 52px, and the weather box and counts sit on one line below it.
- **Web app setup:** a `manifest.webmanifest`, an `apple-touch-icon` (the orange sun on paper), `apple-mobile-web-app-capable`, and a `theme-color` matching the paper.

## 7. Site structure

```
site/
  index.html                 ← today's front page
  <slug>/index.html          ← today's section pages (technology/, apple/, …)
  archive/index.html         ← list of the last 30 editions
  editions/YYYY-MM-DD/…      ← the same pages for each saved past edition
  static/…                   ← css, icons, manifest
```

The site lives at `https://<github-username>.github.io/daily-paper/`. All links are relative so the paper works under that subpath.

## 8. Automation and error handling

**Workflow** `.github/workflows/daily.yml`:
- **Triggers:** `schedule` runs at `0 9 * * *` and `0 10 * * *` UTC, plus `workflow_dispatch` (a "Run" button).
- **Time gate:** unless the run was started by hand, the job exits early when the hour in America/New_York isn't 05, or when `editions/<today>.json` already exists. This keeps the build at 5 AM through daylight-saving changes and prevents building twice.
- **Steps:** check out the repo → set up Python 3.12 (with pip cache) → `pip install -r requirements.txt` → `python -m paper.build` → commit `editions/` back to `main` as "Edition YYYY-MM-DD" → upload `site/` → deploy with `actions/deploy-pages`.
- The daily commit counts as repository activity, so GitHub won't turn off the schedule for inactivity.

**Failures:**
- A feed that fails or returns nothing is logged and skipped. A build summary listing broken feeds goes in the run's summary page.
- The build fails, and stops before deploying, only if **every** feed fails or the edition has fewer than 10 articles. GitHub then emails the owner, and yesterday's site stays up.
- If the weather lookup fails, the weather box is left out of the page.
- Bad markup in feeds is handled by feedparser, and summaries are cleaned before display.

**Commands for local use:**
- `python -m paper.build --out site` builds the paper locally. Opening `site/index.html` shows it.
- `python -m paper.check_feeds` checks every feed in `feeds.yaml` and prints OK or FAIL, how many entries it returned, and how many of them have photos.

## 9. Testing

- **Unit tests** (`pytest`) use saved feed snapshots in `tests/fixtures/`:
  - `clean`: removing HTML, finding the image in each feed format, cutting summaries, throwing out entries without a link.
  - Duplicate removal: matching links after stripping tracking parameters, matching near-identical titles, and the version with an image winning.
  - `edition`: picking the lead from a group with shared coverage, falling back to the newest story with an image, filling in a slot when a section is empty, the 48-hour look-back, quote rotation, and issue numbers.
  - `fetch`: one feed timing out doesn't affect the others (using mocked HTTP).
- **Render test:** build a sample edition from the fixtures and check that the pages have the expected slots, all links are relative, and none of the template markers are left unfilled.
- **Manual check before launch:** compare the live pages against the mockups at iPhone (390px), iPad (820px) and Mac (1440px) widths, and test adding the paper to the iPhone Home Screen.

## 10. One-time setup (owner)

1. Create the public repo `daily-paper` on GitHub and push.
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Actions → General → Workflow permissions: **Read and write** (needed to commit `editions/`).
4. Actions → "Daily edition" → **Run workflow** once to publish the first edition.
5. On iPhone/iPad: open the site in Safari → Share → **Add to Home Screen**. On Mac: Safari → File → **Add to Dock**.

## 11. Later (not v1)

- **Claude as editor:** an optional `paper/editor.py` step between `edition` and `render`, turned on when an `ANTHROPIC_API_KEY` secret is present. It would choose the lead, write summaries and add a "Today in brief" column.
- Offline reading through a service worker.
- Specific sports teams and endurance sub-topics.

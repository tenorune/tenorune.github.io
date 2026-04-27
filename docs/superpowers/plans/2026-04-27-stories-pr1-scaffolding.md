# Stories Compilation PR 1 — Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a working, deployable Jekyll scaffold for the stories compilation that coexists with the existing `lightseed.net` homepage without touching it. After this PR, the homepage continues to render byte-identical, and `/stories/` and `/stories/themes/` render as empty (zero-content) project pages.

**Architecture:** Jekyll on GitHub Pages classic build, single `stories` collection with `render_with_liquid: false`, six layouts, two `_data/*.json` files for state tracking (empty at scaffold), one `_data/themes.yml` (empty), per-theme directory pattern for `/themes/<slug>/{index,all}.md`. Pre-commit invariants enforced by `scripts/verify.py`; build check by `scripts/build-check.sh`.

**Tech Stack:** Jekyll 4.x, Ruby (system), Python 3.12 for verify script. Whitelisted plugins: `jekyll-feed`, `jekyll-sitemap`. No webfonts, no JavaScript.

**Spec source of truth:** `docs/superpowers/specs/2026-04-27-stories-design.md`. Read alongside this plan when implementing — every decision in this plan is grounded there.

**Branch:** `claude/review-bluesky-stories-plan-ItxMr` (current session branch).

---

## File map

Files this plan creates or modifies:

| Path | Action | Responsibility |
|---|---|---|
| `_config.yml` | create | Jekyll site config: collections, plugins, exclude list, defaults |
| `Gemfile` | create | Ruby gem deps for local dev |
| `Gemfile.lock` | create (via `bundle install`) | Pinned versions, committed |
| `.env.example` | create | Placeholder credentials for fetch script (committed) |
| `.gitignore` | modify | Add Jekyll/Python/dev artifacts |
| `_layouts/default.html` | create | Page shell shared by all project pages |
| `_layouts/story.html` | create | Single story page |
| `_layouts/stories_index.html` | create | Chronological list of all published stories |
| `_layouts/themes_index.html` | create | List of all themes |
| `_layouts/theme_list.html` | create | Single theme: titles + summaries |
| `_layouts/theme_compilation.html` | create | Single theme: full stories inline |
| `_includes/stories_header.html` | create | Project nav header |
| `_includes/stories_footer.html` | create | Project footer |
| `_includes/story_card.html` | create | List item partial used by index pages |
| `_data/saves_inventory.json` | create | Empty inventory shell |
| `_data/saves_state.json` | create | Empty state shell |
| `_data/themes.yml` | create | Empty themes list |
| `_stories/.gitkeep` | create | Hold the empty collection directory in git |
| `stories/index.md` | create | Front page → stories_index layout |
| `stories/themes/index.md` | create | Themes hub → themes_index layout |
| `assets/stories/stories.css` | create | Project CSS (scoped to project pages) |
| `scripts/verify.py` | create | Pre-commit invariant checks |
| `scripts/build-check.sh` | create | Local Jekyll build + homepage byte check |
| `scripts/requirements.txt` | create | Python deps (verify.py uses stdlib only, but reserved for fetch) |
| `tests/test_verify.py` | create | TDD tests for verify.py |
| `docs/stories-plan.md` | delete | Superseded by the new design spec |
| `CLAUDE.md` | modify | Update spec pointer to the new design path |

---

## Task 1 — Gemfile, .env.example, and .gitignore

**Files:**
- Create: `Gemfile`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1.1: Write `Gemfile`**

```ruby
source "https://rubygems.org"

# Pinned to GitHub Pages' supported version range.
# See https://pages.github.com/versions/ for the canonical list.
gem "github-pages", group: :jekyll_plugins
gem "jekyll-feed", group: :jekyll_plugins
gem "jekyll-sitemap", group: :jekyll_plugins

# Windows / JRuby compatibility
gem "tzinfo", ">= 1", "< 3"
gem "tzinfo-data", platforms: [:mingw, :x64_mingw, :mswin, :jruby]
gem "wdm", "~> 0.1.1", platforms: [:mingw, :x64_mingw, :mswin]

# Performance: faster file watching on Linux/macOS local dev
gem "http_parser.rb", "~> 0.6.0", platforms: [:jruby]
```

- [ ] **Step 1.2: Write `.env.example`**

```env
# BlueSky credentials for scripts/fetch_saves.py.
# Copy this file to .env and fill in real values.
# .env is gitignored; .env.example is committed.

BSKY_HANDLE=you.bsky.social
BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

- [ ] **Step 1.3: Update `.gitignore`**

Read current contents (only `.superpowers/`); append the new entries.

```
.superpowers/

# Jekyll
_site/
.jekyll-cache/
.jekyll-metadata
.bundle/
vendor/

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/

# Local credentials
.env
.bsky-session.json

# Editor / OS
.DS_Store
*.swp
```

- [ ] **Step 1.4: Commit**

```bash
git add Gemfile .env.example .gitignore
git commit -m "scaffold(stories): add Gemfile, .env.example, .gitignore entries"
```

---

## Task 2 — `_config.yml`

**Files:**
- Create: `_config.yml`

- [ ] **Step 2.1: Write `_config.yml`**

```yaml
# Site
title: lightseed stories
description: Long-form synopses of saved BlueSky posts.
url: https://lightseed.net
baseurl: ""

# Build
markdown: kramdown
kramdown:
  input: GFM
  hard_wrap: false
  syntax_highlighter: rouge

# No theme — we own the layouts.
theme: ~

# Plugins (only those on the GitHub Pages whitelist).
plugins:
  - jekyll-feed
  - jekyll-sitemap

# Stories collection.
collections:
  stories:
    output: true
    permalink: /stories/:slug/
    render_with_liquid: false

# Defaults: ensure stories use the right layout and that drafts (published: false)
# are not rendered. Jekyll respects `published: false` natively.
defaults:
  - scope:
      path: ""
      type: stories
    values:
      layout: story

# Exclude every homepage asset and every dev artifact so Jekyll passes them
# through untouched. The cohabitation discipline (Section 1 of spec) lives here.
exclude:
  # Homepage assets — DO NOT REMOVE without curator review.
  - index.html
  - style.css
  - CNAME
  - favicon.ico
  - media/
  - LICENSE

  # Project bookkeeping that should not be served as web pages.
  - CLAUDE.md
  - docs/
  - README.md

  # Build / dev artifacts.
  - Gemfile
  - Gemfile.lock
  - .env
  - .env.example
  - .gitignore
  - .bundle/
  - vendor/
  - .jekyll-cache/
  - .jekyll-metadata
  - .superpowers/
  - .venv/

  # Scripts and tests are not site content.
  - scripts/
  - tests/

# Feed and sitemap config.
feed:
  path: feed.xml
```

- [ ] **Step 2.2: Run `bundle install` to create `Gemfile.lock`**

Run: `bundle install`
Expected: gems installed, `Gemfile.lock` created.

- [ ] **Step 2.3: Commit**

```bash
git add _config.yml Gemfile.lock
git commit -m "scaffold(stories): add _config.yml and pin Gemfile.lock"
```

---

## Task 3 — Empty data files and collection skeleton

**Files:**
- Create: `_data/saves_inventory.json`
- Create: `_data/saves_state.json`
- Create: `_data/themes.yml`
- Create: `_stories/.gitkeep`
- Create: `stories/index.md`
- Create: `stories/themes/index.md`

- [ ] **Step 3.1: Write `_data/saves_inventory.json`**

```json
{
  "fetched_at": null,
  "saves": []
}
```

- [ ] **Step 3.2: Write `_data/saves_state.json`**

```json
{
  "updated_at": null,
  "states": {}
}
```

- [ ] **Step 3.3: Write `_data/themes.yml`**

```yaml
# Emergent themes will accumulate here as stories are drafted.
# Schema (per Section 4 of spec):
#   - slug: kebab-case-id
#     label: human-readable label
#     description: one-sentence emergent description
[]
```

- [ ] **Step 3.4: Create `_stories/.gitkeep`**

Empty file. Holds the directory in git so Jekyll registers the collection.

- [ ] **Step 3.5: Write `stories/index.md`**

```markdown
---
layout: stories_index
title: Stories
permalink: /stories/
---
```

- [ ] **Step 3.6: Write `stories/themes/index.md`**

```markdown
---
layout: themes_index
title: Themes
permalink: /stories/themes/
---
```

- [ ] **Step 3.7: Commit**

```bash
git add _data/ _stories/.gitkeep stories/
git commit -m "scaffold(stories): add empty data files and collection skeleton"
```

---

## Task 4 — Page shell layout and includes

**Files:**
- Create: `_layouts/default.html`
- Create: `_includes/stories_header.html`
- Create: `_includes/stories_footer.html`

- [ ] **Step 4.1: Write `_includes/stories_header.html`**

```html
<header class="stories-header">
  <a class="wordmark" href="/stories/">STORIES</a>
  <nav><a href="/stories/themes/">themes</a></nav>
</header>
```

- [ ] **Step 4.2: Write `_includes/stories_footer.html`**

```html
<footer class="stories-footer">
  <span class="meta">Compiled from saved BlueSky posts.</span>
  <a href="/feed.xml">RSS</a>
</footer>
```

- [ ] **Step 4.3: Write `_layouts/default.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page.title | default: site.title }}</title>
  <link rel="stylesheet" href="/assets/stories/stories.css">
  {% feed_meta %}
</head>
<body>
  {% include stories_header.html %}
  <main>
    {{ content }}
  </main>
  {% include stories_footer.html %}
</body>
</html>
```

- [ ] **Step 4.4: Commit**

```bash
git add _layouts/default.html _includes/stories_header.html _includes/stories_footer.html
git commit -m "scaffold(stories): add page shell layout and header/footer includes"
```

---

## Task 5 — Story-related layouts

**Files:**
- Create: `_layouts/story.html`
- Create: `_layouts/stories_index.html`
- Create: `_includes/story_card.html`

- [ ] **Step 5.1: Write `_layouts/story.html`**

Story page: title, hero, summary, theme chips, meta line, body, source link.

```html
---
layout: default
---
<article class="story">
  <h1 class="story-title">{{ page.title }}</h1>

  {% if page.hero_image %}
  <figure class="hero">
    <img src="{{ page.hero_image }}" alt="{{ page.hero_image_alt }}">
    {% if page.hero_image_credit %}
    <figcaption class="meta">{{ page.hero_image_credit }}</figcaption>
    {% endif %}
  </figure>
  {% endif %}

  <p class="summary">{{ page.summary }}</p>

  <p class="themes">
    {% for slug in page.themes %}
      {% assign theme = site.data.themes | where: "slug", slug | first %}
      {% if theme %}
        <a class="chip" href="/stories/themes/{{ theme.slug }}/">#{{ theme.label }}</a>
      {% endif %}
    {% endfor %}
  </p>

  <p class="meta meta-line">
    Saved {{ page.bluesky_saved_at | date: "%b %-d, %Y" }} ·
    Source: {{ page.source_publication }}{% if page.source_author %}, {{ page.source_author }}{% endif %}{% if page.source_published_at %} ({{ page.source_published_at | date: "%b %-d, %Y" }}){% endif %}
  </p>

  <hr class="rule">

  <div class="body">
    {{ content }}
  </div>

  <hr class="rule">

  <p class="source-link">
    <a href="{{ page.source_url }}">Read original →</a>
    <span class="meta">{{ page.source_url | replace: "https://", "" | replace: "http://", "" | split: "/" | first }}</span>
  </p>
</article>
```

- [ ] **Step 5.2: Write `_includes/story_card.html`**

Used by `stories_index.html` and `theme_list.html`. Expects `story` to be set in scope.

```html
<li class="card">
  <span class="card-date meta">{{ story.date | date: "%b %-d" }}</span>
  <a class="card-title" href="{{ story.url }}">{{ story.title }}</a>
  <p class="card-summary">{{ story.summary }}</p>
  <p class="card-themes meta">
    {% for slug in story.themes %}{{ slug }}{% unless forloop.last %} · {% endunless %}{% endfor %}
  </p>
</li>
```

- [ ] **Step 5.3: Write `_layouts/stories_index.html`**

```html
---
layout: default
---
<h1 class="page-title">Stories</h1>
<p class="intro">Compiled from saved BlueSky posts.</p>

{% assign published = site.stories | where: "published", true | sort: "date" | reverse %}
{% assign current_year = "" %}

<ul class="stories-list">
{% for story in published %}
  {% assign year = story.date | date: "%Y" %}
  {% if year != current_year %}
    {% unless forloop.first %}</ul><h2 class="year">{{ year }}</h2><ul class="stories-list">{% endunless %}
    {% if forloop.first %}<h2 class="year">{{ year }}</h2>{% endif %}
    {% assign current_year = year %}
  {% endif %}
  {% include story_card.html story=story %}
{% endfor %}
</ul>

{% if published.size == 0 %}
<p class="empty">No published stories yet.</p>
{% endif %}
```

- [ ] **Step 5.4: Commit**

```bash
git add _layouts/story.html _layouts/stories_index.html _includes/story_card.html
git commit -m "scaffold(stories): add single-story and stories-index layouts"
```

---

## Task 6 — Theme-related layouts

**Files:**
- Create: `_layouts/themes_index.html`
- Create: `_layouts/theme_list.html`
- Create: `_layouts/theme_compilation.html`

- [ ] **Step 6.1: Write `_layouts/themes_index.html`**

```html
---
layout: default
---
<h1 class="page-title">Themes</h1>

{% assign themes = site.data.themes | sort: "label" %}
{% assign published = site.stories | where: "published", true %}

{% if themes.size == 0 %}
<p class="empty">No themes yet.</p>
{% else %}
<ul class="themes-list">
  {% for theme in themes %}
    {% assign count = 0 %}
    {% for story in published %}
      {% if story.themes contains theme.slug %}{% assign count = count | plus: 1 %}{% endif %}
    {% endfor %}
    <li class="theme-row">
      <a class="theme-label" href="/stories/themes/{{ theme.slug }}/">{{ theme.label }}</a>
      <span class="theme-count meta">{{ count }} {% if count == 1 %}story{% else %}stories{% endif %}</span>
      <p class="theme-description">{{ theme.description }}</p>
    </li>
  {% endfor %}
</ul>
{% endif %}
```

- [ ] **Step 6.2: Write `_layouts/theme_list.html`**

Reads the theme's slug from `page.theme_slug` (set in the per-theme stub frontmatter).

```html
---
layout: default
---
{% assign theme = site.data.themes | where: "slug", page.theme_slug | first %}
{% assign published = site.stories | where: "published", true | sort: "date" | reverse %}
{% assign matching = "" | split: "" %}
{% for story in published %}
  {% if story.themes contains page.theme_slug %}
    {% assign matching = matching | push: story %}
  {% endif %}
{% endfor %}

<h1 class="page-title">Theme: {{ theme.label }}</h1>
<p class="theme-description">{{ theme.description }}</p>
<p><a class="read-all" href="/stories/themes/{{ theme.slug }}/all/">Read all stories in this theme →</a></p>

<hr class="rule">

{% if matching.size == 0 %}
<p class="empty">No published stories in this theme yet.</p>
{% else %}
{% assign current_year = "" %}
<ul class="stories-list">
{% for story in matching %}
  {% assign year = story.date | date: "%Y" %}
  {% if year != current_year %}
    {% unless forloop.first %}</ul><h2 class="year">{{ year }}</h2><ul class="stories-list">{% endunless %}
    {% if forloop.first %}<h2 class="year">{{ year }}</h2>{% endif %}
    {% assign current_year = year %}
  {% endif %}
  {% include story_card.html story=story %}
{% endfor %}
</ul>
{% endif %}
```

- [ ] **Step 6.3: Write `_layouts/theme_compilation.html`**

```html
---
layout: default
---
{% assign theme = site.data.themes | where: "slug", page.theme_slug | first %}
{% assign published = site.stories | where: "published", true | sort: "date" %}
{% assign matching = "" | split: "" %}
{% for story in published %}
  {% if story.themes contains page.theme_slug %}
    {% assign matching = matching | push: story %}
  {% endif %}
{% endfor %}

<h1 class="page-title">Theme: {{ theme.label }} — full compilation</h1>
<p class="theme-description">{{ theme.description }}</p>
<p><a class="view-list" href="/stories/themes/{{ theme.slug }}/">View as list →</a></p>

{% if matching.size == 0 %}
<p class="empty">No published stories in this theme yet.</p>
{% else %}
{% for story in matching %}
<hr class="strong-rule">

<article class="compiled-story">
  <h2 class="story-title">{{ story.title }}</h2>

  <p class="meta meta-line">
    {{ story.date | date: "%b %-d, %Y" }} ·
    {{ story.source_publication }}{% if story.source_author %}, {{ story.source_author }}{% endif %}
  </p>

  {% if story.hero_image %}
  <figure class="hero">
    <img src="{{ story.hero_image }}" alt="{{ story.hero_image_alt }}">
    {% if story.hero_image_credit %}
    <figcaption class="meta">{{ story.hero_image_credit }}</figcaption>
    {% endif %}
  </figure>
  {% endif %}

  <p class="summary">{{ story.summary }}</p>

  <div class="body">
    {{ story.content }}
  </div>

  <p class="source-link"><a href="{{ story.source_url }}">Read original →</a></p>
</article>
{% endfor %}
{% endif %}
```

- [ ] **Step 6.4: Commit**

```bash
git add _layouts/themes_index.html _layouts/theme_list.html _layouts/theme_compilation.html
git commit -m "scaffold(stories): add theme index and per-theme layouts"
```

---

## Task 7 — Stylesheet

**Files:**
- Create: `assets/stories/stories.css`

- [ ] **Step 7.1: Write `assets/stories/stories.css`**

Long-form serif aesthetic per Section 5 of spec. System fonts only.

```css
:root {
  --serif: "Iowan Old Style", "Apple Garamond", Baskerville,
           "Times New Roman", "Droid Serif", Times, serif;
  --sans:  -apple-system, BlinkMacSystemFont, "Segoe UI",
           Roboto, "Helvetica Neue", sans-serif;
  --measure: 38rem;
  --leading: 1.65;
  --ink: #1a1a1a;
  --paper: #fafaf8;
  --muted: #6b6b6b;
  --rule: #d8d8d4;
  --accent: #6b3a1a;
}

* { box-sizing: border-box; }

html, body { margin: 0; padding: 0; }

body {
  font-family: var(--serif);
  font-size: 1.0625rem;
  line-height: var(--leading);
  color: var(--ink);
  background: var(--paper);
  -webkit-font-smoothing: antialiased;
}

main {
  max-width: var(--measure);
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
}

a { color: var(--accent); }
a:hover { text-decoration-thickness: 2px; }

/* Sans for UI / metadata */
.meta, nav, footer, .label, .stories-header, .stories-footer,
.themes, .card-themes, .year, .empty, .intro, .read-all, .view-list {
  font-family: var(--sans);
}

/* Header */
.stories-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  max-width: var(--measure);
  margin: 0 auto;
  padding: 1.25rem 1.25rem 0.5rem;
  border-bottom: 1px solid var(--rule);
}
.stories-header .wordmark {
  font-weight: 700;
  letter-spacing: 0.08em;
  font-size: 0.85rem;
  color: var(--ink);
  text-decoration: none;
}
.stories-header nav a {
  font-size: 0.85rem;
  text-decoration: none;
}

/* Footer */
.stories-footer {
  max-width: var(--measure);
  margin: 4rem auto 2rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--rule);
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: var(--muted);
}
.stories-footer a { color: var(--muted); }

/* Page titles */
.page-title {
  font-size: 2rem;
  line-height: 1.2;
  margin: 1rem 0 0.5rem;
}
.intro { color: var(--muted); margin: 0 0 2rem; font-style: italic; }
.empty { color: var(--muted); font-style: italic; }

/* Year heading */
.year {
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin-top: 2rem;
  margin-bottom: 0.5rem;
}

/* Stories list */
.stories-list { list-style: none; padding: 0; margin: 0; }
.card { margin: 1.25rem 0; }
.card-date { font-size: 0.85rem; color: var(--muted); margin-right: 0.5rem; }
.card-title { font-family: var(--serif); font-size: 1.15rem; text-decoration: none; color: var(--ink); }
.card-summary { font-style: italic; margin: 0.25rem 0; }
.card-themes { font-size: 0.85rem; color: var(--muted); }

/* Themes index */
.themes-list { list-style: none; padding: 0; margin: 0; }
.theme-row { margin: 1.5rem 0; }
.theme-label { font-family: var(--serif); font-size: 1.15rem; text-decoration: none; color: var(--ink); }
.theme-count { font-size: 0.85rem; color: var(--muted); margin-left: 0.5rem; }
.theme-description { font-style: italic; color: var(--muted); margin: 0.25rem 0 0; }

/* Single story */
.story-title { font-size: 1.75rem; line-height: 1.25; margin: 1rem 0 1rem; }
.summary { font-style: italic; font-size: 1.1rem; color: var(--ink); margin: 0.5rem 0 0.75rem; }
.themes .chip {
  display: inline-block;
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  text-decoration: none;
  margin-right: 0.5rem;
}
.meta-line { font-size: 0.85rem; color: var(--muted); margin: 0.25rem 0 1rem; }

.body p { margin: 1em 0; }
.body img { display: block; max-width: 100%; height: auto; margin: 1.5rem 0; }

.hero { margin: 1rem 0 0.5rem; }
.hero img { width: 100%; height: auto; display: block; }
.hero figcaption { font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }

.rule { border: 0; border-top: 1px solid var(--rule); margin: 2rem 0; }
.strong-rule { border: 0; border-top: 3px double var(--rule); margin: 3rem 0; }

.source-link { font-family: var(--sans); margin-top: 1.5rem; }
.source-link a { font-weight: 600; }

/* Theme list extras */
.read-all, .view-list { display: inline-block; margin: 1rem 0; }

/* Compilation view */
.compiled-story { margin-top: 2rem; }
.compiled-story .story-title { font-size: 1.5rem; }
```

- [ ] **Step 7.2: Commit**

```bash
git add assets/stories/stories.css
git commit -m "scaffold(stories): add project stylesheet"
```

---

## Task 8 — First Jekyll build & homepage byte-identity check

**Files:** none created. Verifies the scaffold compiles and homepage assets pass through untouched.

- [ ] **Step 8.1: Run a clean Jekyll build**

```bash
bundle exec jekyll build --trace
```

Expected: succeeds with no errors. `_site/` directory created.

- [ ] **Step 8.2: Verify homepage byte-identity**

```bash
diff -q index.html _site/index.html
diff -q style.css _site/style.css
diff -q CNAME _site/CNAME
diff -q favicon.ico _site/favicon.ico
diff -rq media/ _site/media/
```

Expected: all `diff` calls produce no output (files match byte-for-byte). If any diff produces output, the `exclude:` list in `_config.yml` is wrong — fix and re-run.

- [ ] **Step 8.3: Verify empty project pages render**

```bash
test -f _site/stories/index.html && echo "stories index OK"
test -f _site/stories/themes/index.html && echo "themes index OK"
test -f _site/feed.xml && echo "feed OK"
test -f _site/sitemap.xml && echo "sitemap OK"
```

Expected: all four lines print. If `feed.xml` or `sitemap.xml` are missing, `jekyll-feed`/`jekyll-sitemap` aren't activating — re-check the `plugins:` section in `_config.yml`.

- [ ] **Step 8.4: No accidental commit of `_site/`**

`_site/` should be in `.gitignore` (added in Task 1). Verify:

```bash
git status --short | grep -E "^\?\? _site/" && echo "BUG: _site is tracked" || echo "OK: _site ignored"
```

Expected: `OK: _site ignored`.

- [ ] **Step 8.5: No commit needed for this task** — it's verification only. Move on.

---

## Task 9 — Python tooling setup

**Files:**
- Create: `scripts/requirements.txt`

- [ ] **Step 9.1: Write `scripts/requirements.txt`**

`verify.py` uses only stdlib + `PyYAML` for parsing `themes.yml`. Reserved entries for the future fetch script are also listed but commented to keep scaffold-only deps minimal.

```
# Used by scripts/verify.py
PyYAML>=6.0
pytest>=8.0

# Used by scripts/fetch_saves.py (added in PR 2; uncomment when introduced)
# httpx>=0.27
# python-dateutil>=2.9
# python-dotenv>=1.0
```

- [ ] **Step 9.2: Create local virtualenv and install deps**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

Expected: venv created, deps install cleanly.

- [ ] **Step 9.3: Commit**

```bash
git add scripts/requirements.txt
git commit -m "scaffold(stories): add Python requirements for verify script"
```

---

## Task 10 — `scripts/verify.py` test suite (TDD, part 1: write failing tests)

**Files:**
- Create: `tests/__init__.py` (empty file, makes the directory a package)
- Create: `tests/conftest.py` — pytest fixtures for a minimal repo
- Create: `tests/test_verify.py` — one test per check from Section 9 of spec

- [ ] **Step 10.1: Write `tests/__init__.py`**

Empty file. Just a `touch` equivalent.

- [ ] **Step 10.2: Write `tests/conftest.py`**

A pytest fixture that builds a minimal valid stories repo in a tmpdir for each test.

```python
"""Shared pytest fixtures for verify.py tests.

Each test gets a fresh, valid scaffold in a tmpdir and mutates it to
trigger the failure mode under test.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _git_init_with_homepage(repo: Path) -> None:
    """Initialise git in the tmpdir and commit homepage assets so the
    homepage_untouched check has a HEAD to compare against."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo, check=True
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture: initial commit"],
        cwd=repo,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Build a minimal valid stories scaffold in tmp_path and return the path."""
    r = tmp_path

    # Homepage assets that verify.py compares against HEAD.
    (r / "index.html").write_text("<html>homepage</html>\n")
    (r / "style.css").write_text("body { color: black; }\n")
    (r / "CNAME").write_text("example.com\n")
    (r / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    (r / "media").mkdir()
    (r / "media" / "logo.gif").write_bytes(b"GIF89a")

    # Minimal _config.yml with the homepage assets in `exclude:`.
    (r / "_config.yml").write_text(
        "exclude:\n"
        "  - index.html\n"
        "  - style.css\n"
        "  - CNAME\n"
        "  - favicon.ico\n"
        "  - media/\n"
        "  - LICENSE\n"
        "  - CLAUDE.md\n"
        "  - docs/\n"
    )

    # Empty data files.
    (r / "_data").mkdir()
    (r / "_data" / "saves_inventory.json").write_text(
        json.dumps({"fetched_at": None, "saves": []}, indent=2) + "\n"
    )
    (r / "_data" / "saves_state.json").write_text(
        json.dumps({"updated_at": None, "states": {}}, indent=2) + "\n"
    )
    (r / "_data" / "themes.yml").write_text("[]\n")

    # Empty stories collection and theme stub directory.
    (r / "_stories").mkdir()
    (r / "_stories" / ".gitkeep").write_text("")
    (r / "stories").mkdir()
    (r / "stories" / "themes").mkdir()

    _git_init_with_homepage(r)
    return r


def add_theme(repo: Path, slug: str, label: str, description: str) -> None:
    """Append a theme to themes.yml and create both stub files."""
    themes_yaml = repo / "_data" / "themes.yml"
    existing = themes_yaml.read_text()
    entry = (
        f"- slug: {slug}\n"
        f"  label: {label}\n"
        f"  description: \"{description}\"\n"
    )
    # Replace the empty `[]\n` placeholder on first add; otherwise append.
    new = (entry if existing.strip() == "[]" else existing + entry)
    themes_yaml.write_text(new)
    theme_dir = repo / "stories" / "themes" / slug
    theme_dir.mkdir(parents=True, exist_ok=True)
    (theme_dir / "index.md").write_text(
        f"---\nlayout: theme_list\npermalink: /stories/themes/{slug}/\n"
        f"theme_slug: {slug}\n---\n"
    )
    (theme_dir / "all.md").write_text(
        f"---\nlayout: theme_compilation\n"
        f"permalink: /stories/themes/{slug}/all/\ntheme_slug: {slug}\n---\n"
    )


def add_story(
    repo: Path,
    *,
    slug: str = "fixture-story",
    saved_at: str = "2026-04-12T18:31:00Z",
    themes: list[str] | None = None,
    published: bool = True,
    hero: bool = False,
    body: str = "Synopsis paragraph.\n",
) -> Path:
    """Write a minimal valid story file and return its path."""
    themes = themes or []
    fname = f"{saved_at[:10]}-{slug}.md"
    path = repo / "_stories" / fname

    fm: list[str] = [
        "---",
        f'title: "Fixture {slug}"',
        f"slug: {slug}",
        'summary: "One-sentence summary."',
        f"date: {saved_at[:10]}",
        f"themes: [{', '.join(themes)}]",
        'source_url: "https://example.org/article"',
        'source_title: "Original article"',
        'source_publication: "Example Publication"',
        'bluesky_uri: "at://did:plc:abc.../app.bsky.feed.post/abc"',
        f"bluesky_saved_at: {saved_at}",
    ]
    if hero:
        fm.append(f"hero_image: /assets/stories/{slug}/hero.jpg")
        fm.append('hero_image_alt: "Alt text"')
    fm.append(f"published: {'true' if published else 'false'}")
    fm.append("---")
    fm.append("")
    fm.append(body)

    path.write_text("\n".join(fm))
    return path


def set_state(repo: Path, uri: str, status: str, story_slug: str | None) -> None:
    """Write an entry into saves_state.json."""
    state_path = repo / "_data" / "saves_state.json"
    state = json.loads(state_path.read_text())
    state["states"][uri] = {
        "status": status,
        "story_slug": story_slug,
        "first_processed_at": "2026-04-15T20:00:00Z",
        "last_action_at": "2026-04-15T20:00:00Z",
    }
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def add_inventory_entry(repo: Path, uri: str) -> None:
    """Append a minimal entry to saves_inventory.json."""
    inv_path = repo / "_data" / "saves_inventory.json"
    inv = json.loads(inv_path.read_text())
    inv["saves"].append(
        {
            "uri": uri,
            "saved_at": "2026-04-12T18:31:00Z",
            "post_text": "post text",
            "embed": {
                "type": "external",
                "url": "https://example.org/article",
                "title": "title",
                "description": "desc",
            },
            "author": {
                "handle": "h.bsky.social",
                "display_name": "name",
                "did": "did:plc:abc",
            },
        }
    )
    inv_path.write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 10.3: Write `tests/test_verify.py`**

One test per check. Each test starts from the `repo` fixture (a minimal valid scaffold) and either leaves it valid (passing case) or breaks one invariant (failing case).

```python
"""Tests for scripts/verify.py — one test per check (Section 9 of spec)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/ importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import verify  # noqa: E402

from conftest import add_inventory_entry, add_state, add_story, add_theme  # noqa: E402


# ---------- baseline: a valid scaffold passes ----------

def test_baseline_valid_scaffold_passes(repo):
    ok, msg = verify.run_all(repo)
    assert ok, f"valid scaffold should pass; got: {msg}"


# ---------- homepage_untouched ----------

def test_homepage_untouched_passes_when_unchanged(repo):
    ok, _ = verify.check_homepage_untouched(repo)
    assert ok


def test_homepage_untouched_fails_when_modified(repo):
    (repo / "index.html").write_text("<html>tampered</html>\n")
    ok, msg = verify.check_homepage_untouched(repo)
    assert not ok
    assert "index.html" in msg


# ---------- exclude_completeness ----------

def test_exclude_completeness_passes_for_full_list(repo):
    ok, _ = verify.check_exclude_completeness(repo)
    assert ok


def test_exclude_completeness_fails_when_homepage_missing_from_exclude(repo):
    (repo / "_config.yml").write_text("exclude:\n  - LICENSE\n")
    ok, msg = verify.check_exclude_completeness(repo)
    assert not ok
    assert "index.html" in msg or "style.css" in msg


# ---------- theme_references_resolve ----------

def test_theme_references_resolve_passes(repo):
    add_theme(repo, "climate", "climate", "Test description.")
    add_story(repo, slug="s1", themes=["climate"])
    ok, _ = verify.check_theme_references_resolve(repo)
    assert ok


def test_theme_references_resolve_fails_on_unknown_theme(repo):
    add_story(repo, slug="s1", themes=["typo-theme"])
    ok, msg = verify.check_theme_references_resolve(repo)
    assert not ok
    assert "typo-theme" in msg


# ---------- theme_stubs_exist ----------

def test_theme_stubs_exist_passes_when_both_present(repo):
    add_theme(repo, "climate", "climate", "desc")
    ok, _ = verify.check_theme_stubs_exist(repo)
    assert ok


def test_theme_stubs_exist_fails_when_index_missing(repo):
    add_theme(repo, "climate", "climate", "desc")
    (repo / "stories" / "themes" / "climate" / "index.md").unlink()
    ok, msg = verify.check_theme_stubs_exist(repo)
    assert not ok
    assert "climate" in msg


def test_theme_stubs_exist_fails_when_all_missing(repo):
    add_theme(repo, "climate", "climate", "desc")
    (repo / "stories" / "themes" / "climate" / "all.md").unlink()
    ok, msg = verify.check_theme_stubs_exist(repo)
    assert not ok


# ---------- hero_alt_required ----------

def test_hero_alt_required_passes_with_alt(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"], hero=True)
    ok, _ = verify.check_hero_alt_required(repo)
    assert ok


def test_hero_alt_required_fails_when_alt_missing(repo):
    add_theme(repo, "x", "x", "d")
    p = add_story(repo, slug="s1", themes=["x"], hero=True)
    # Strip the alt line.
    text = p.read_text()
    text = text.replace('hero_image_alt: "Alt text"\n', "")
    p.write_text(text)
    ok, msg = verify.check_hero_alt_required(repo)
    assert not ok
    assert "s1" in msg


# ---------- inline_image_alt ----------

def test_inline_image_alt_warns_on_empty(repo, capsys):
    add_theme(repo, "x", "x", "d")
    add_story(
        repo,
        slug="s1",
        themes=["x"],
        body="Body.\n\n![](/assets/stories/s1/figure-1.jpg)\n",
    )
    ok, msg = verify.check_inline_image_alt(repo)
    # Soft warning — should still pass, but the message reports it.
    assert ok
    assert "empty alt" in msg.lower() or "warn" in msg.lower()


# ---------- state_consistency ----------

def test_state_consistency_passes_when_story_exists(repo):
    add_theme(repo, "x", "x", "d")
    add_inventory_entry(repo, "at://uri/1")
    add_story(repo, slug="s1", themes=["x"])
    add_state(repo, "at://uri/1", "drafted", "s1")
    ok, _ = verify.check_state_consistency(repo)
    assert ok


def test_state_consistency_fails_when_story_missing(repo):
    add_inventory_entry(repo, "at://uri/1")
    add_state(repo, "at://uri/1", "drafted", "ghost-slug")
    ok, msg = verify.check_state_consistency(repo)
    assert not ok
    assert "ghost-slug" in msg


# ---------- state_inventory_cross_reference ----------

def test_state_inventory_cross_reference_passes(repo):
    add_inventory_entry(repo, "at://uri/1")
    add_state(repo, "at://uri/1", "skipped", None)
    ok, _ = verify.check_state_inventory_cross_reference(repo)
    assert ok


def test_state_inventory_cross_reference_fails_on_orphan_state(repo):
    add_state(repo, "at://uri/orphan", "skipped", None)
    ok, msg = verify.check_state_inventory_cross_reference(repo)
    assert not ok
    assert "at://uri/orphan" in msg


# ---------- frontmatter_contract ----------

def test_frontmatter_contract_passes_for_complete_story(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"])
    ok, _ = verify.check_frontmatter_contract(repo)
    assert ok


def test_frontmatter_contract_fails_when_required_field_missing(repo):
    add_theme(repo, "x", "x", "d")
    p = add_story(repo, slug="s1", themes=["x"])
    p.write_text(p.read_text().replace('source_publication: "Example Publication"\n', ""))
    ok, msg = verify.check_frontmatter_contract(repo)
    assert not ok
    assert "source_publication" in msg


# ---------- slug_filename_match ----------

def test_slug_filename_match_passes(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="matching-slug", themes=["x"])
    ok, _ = verify.check_slug_filename_match(repo)
    assert ok


def test_slug_filename_match_fails_on_mismatch(repo):
    add_theme(repo, "x", "x", "d")
    p = add_story(repo, slug="real-slug", themes=["x"])
    # Rename file but leave slug field unchanged.
    new_path = p.parent / "2026-04-12-different-slug.md"
    p.rename(new_path)
    ok, msg = verify.check_slug_filename_match(repo)
    assert not ok
    assert "different-slug" in msg or "real-slug" in msg


# ---------- pandoc_clean ----------

def test_pandoc_clean_passes_for_plain_markdown(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"], body="Plain paragraph.\n")
    ok, _ = verify.check_pandoc_clean(repo)
    assert ok


def test_pandoc_clean_fails_on_liquid_braces(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"], body="Body with {{ liquid }}.\n")
    ok, msg = verify.check_pandoc_clean(repo)
    assert not ok
    assert "s1" in msg
```

- [ ] **Step 10.4: Run tests to verify they all fail**

```bash
source .venv/bin/activate
pytest tests/test_verify.py -v
```

Expected: every test fails with `ModuleNotFoundError: No module named 'verify'` (since we haven't written it yet). This is correct red-bar TDD state.

- [ ] **Step 10.5: Commit failing tests**

```bash
git add tests/__init__.py tests/conftest.py tests/test_verify.py
git commit -m "scaffold(stories): add failing test suite for verify.py (TDD red bar)"
```

---

## Task 11 — `scripts/verify.py` implementation (TDD green bar)

**Files:**
- Create: `scripts/verify.py`

- [ ] **Step 11.1: Write `scripts/verify.py`**

```python
"""Pre-commit invariant checks for the stories compilation project.

Each check is an independent function that takes the repo root path and
returns a (ok: bool, msg: str) tuple. The CLI runs all checks and exits
non-zero on any failure. Tests in tests/test_verify.py exercise each
check in isolation.

Section 9 of docs/superpowers/specs/2026-04-27-stories-design.md is
the spec source of truth.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

import yaml

HOMEPAGE_FILES = ["index.html", "style.css", "CNAME", "favicon.ico"]
HOMEPAGE_DIRS = ["media"]

REQUIRED_FRONTMATTER = [
    "title",
    "slug",
    "summary",
    "date",
    "themes",
    "source_url",
    "source_title",
    "source_publication",
    "bluesky_uri",
    "bluesky_saved_at",
    "published",
]

REQUIRED_EXCLUDE_ENTRIES = ["index.html", "style.css", "CNAME", "favicon.ico", "media/"]


# ----- helpers -----

def _git_show_head(repo: Path, rel_path: str) -> bytes | None:
    """Return the bytes of `rel_path` at git HEAD, or None if not tracked."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=repo,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _load_yaml_frontmatter(path: Path) -> tuple[dict, str]:
    """Split a Markdown file with YAML frontmatter into (dict, body_str)."""
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}, text
    _, fm_text, body = text.split("---\n", 2)
    return yaml.safe_load(fm_text) or {}, body


def _iter_stories(repo: Path):
    """Yield (path, frontmatter_dict, body_str) for every _stories/*.md file."""
    stories_dir = repo / "_stories"
    if not stories_dir.exists():
        return
    for p in sorted(stories_dir.glob("*.md")):
        fm, body = _load_yaml_frontmatter(p)
        yield p, fm, body


def _load_themes(repo: Path) -> list[dict]:
    yml_path = repo / "_data" / "themes.yml"
    if not yml_path.exists():
        return []
    data = yaml.safe_load(yml_path.read_text())
    return data or []


# ----- checks -----

def check_homepage_untouched(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for f in HOMEPAGE_FILES:
        head = _git_show_head(repo, f)
        if head is None:
            continue  # not tracked yet (e.g., scaffolding before first commit)
        actual = (repo / f).read_bytes() if (repo / f).exists() else b""
        if head != actual:
            failures.append(f"{f} differs from HEAD")
    for d in HOMEPAGE_DIRS:
        dpath = repo / d
        if not dpath.exists():
            continue
        for child in sorted(dpath.rglob("*")):
            if not child.is_file():
                continue
            rel = child.relative_to(repo).as_posix()
            head = _git_show_head(repo, rel)
            if head is None:
                continue
            if head != child.read_bytes():
                failures.append(f"{rel} differs from HEAD")
    if failures:
        return False, "homepage_untouched: " + "; ".join(failures)
    return True, "homepage_untouched: OK"


def check_exclude_completeness(repo: Path) -> tuple[bool, str]:
    cfg = repo / "_config.yml"
    if not cfg.exists():
        return False, "exclude_completeness: _config.yml missing"
    raw = yaml.safe_load(cfg.read_text()) or {}
    excludes = set(raw.get("exclude", []) or [])
    missing = [e for e in REQUIRED_EXCLUDE_ENTRIES if e not in excludes]
    if missing:
        return False, "exclude_completeness: missing entries: " + ", ".join(missing)
    return True, "exclude_completeness: OK"


def check_theme_references_resolve(repo: Path) -> tuple[bool, str]:
    theme_slugs = {t.get("slug") for t in _load_themes(repo)}
    failures: list[str] = []
    for path, fm, _ in _iter_stories(repo):
        for slug in fm.get("themes", []) or []:
            if slug not in theme_slugs:
                failures.append(f"{path.name} references unknown theme '{slug}'")
    if failures:
        return False, "theme_references_resolve: " + "; ".join(failures)
    return True, "theme_references_resolve: OK"


def check_theme_stubs_exist(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for theme in _load_themes(repo):
        slug = theme.get("slug")
        if not slug:
            continue
        idx = repo / "stories" / "themes" / slug / "index.md"
        all_md = repo / "stories" / "themes" / slug / "all.md"
        if not idx.exists():
            failures.append(f"missing stub: stories/themes/{slug}/index.md")
        if not all_md.exists():
            failures.append(f"missing stub: stories/themes/{slug}/all.md")
    if failures:
        return False, "theme_stubs_exist: " + "; ".join(failures)
    return True, "theme_stubs_exist: OK"


def check_hero_alt_required(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for path, fm, _ in _iter_stories(repo):
        if fm.get("hero_image") and not fm.get("hero_image_alt"):
            slug = fm.get("slug", path.stem)
            failures.append(f"{slug}: hero_image set but hero_image_alt missing")
    if failures:
        return False, "hero_alt_required: " + "; ".join(failures)
    return True, "hero_alt_required: OK"


def check_inline_image_alt(repo: Path) -> tuple[bool, str]:
    """Soft warning: empty alt text in inline images. Returns ok=True even on
    findings, with a non-empty message describing them."""
    findings: list[str] = []
    pattern = re.compile(r"!\[\]\(")
    for path, _, body in _iter_stories(repo):
        if pattern.search(body):
            findings.append(f"{path.name} contains image with empty alt")
    if findings:
        return True, "inline_image_alt: WARN empty alt in: " + "; ".join(findings)
    return True, "inline_image_alt: OK"


def check_state_consistency(repo: Path) -> tuple[bool, str]:
    state_path = repo / "_data" / "saves_state.json"
    if not state_path.exists():
        return True, "state_consistency: OK (no state file)"
    state = json.loads(state_path.read_text()).get("states", {})
    story_slugs = {fm.get("slug") for _, fm, _ in _iter_stories(repo)}
    failures: list[str] = []
    for uri, entry in state.items():
        if entry.get("status") in {"drafted", "polished", "published"}:
            slug = entry.get("story_slug")
            if slug not in story_slugs:
                failures.append(f"{uri[:40]}... refs missing slug '{slug}'")
    if failures:
        return False, "state_consistency: " + "; ".join(failures)
    return True, "state_consistency: OK"


def check_state_inventory_cross_reference(repo: Path) -> tuple[bool, str]:
    state_path = repo / "_data" / "saves_state.json"
    inv_path = repo / "_data" / "saves_inventory.json"
    if not state_path.exists() or not inv_path.exists():
        return True, "state_inventory_cross_reference: OK (file(s) missing)"
    state_uris = set(json.loads(state_path.read_text()).get("states", {}).keys())
    inv_uris = {s.get("uri") for s in json.loads(inv_path.read_text()).get("saves", [])}
    orphans = state_uris - inv_uris
    if orphans:
        return False, "state_inventory_cross_reference: orphan URIs in state: " + ", ".join(sorted(orphans))
    return True, "state_inventory_cross_reference: OK"


def check_frontmatter_contract(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for path, fm, _ in _iter_stories(repo):
        for field in REQUIRED_FRONTMATTER:
            if field not in fm or fm.get(field) in (None, ""):
                failures.append(f"{path.name}: missing required field '{field}'")
    if failures:
        return False, "frontmatter_contract: " + "; ".join(failures)
    return True, "frontmatter_contract: OK"


def check_slug_filename_match(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    name_re = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$")
    for path, fm, _ in _iter_stories(repo):
        m = name_re.match(path.name)
        if not m:
            failures.append(f"{path.name}: filename does not match YYYY-MM-DD-<slug>.md pattern")
            continue
        file_slug = m.group(1)
        fm_slug = fm.get("slug")
        if fm_slug != file_slug:
            failures.append(f"{path.name}: filename slug '{file_slug}' != frontmatter slug '{fm_slug}'")
    if failures:
        return False, "slug_filename_match: " + "; ".join(failures)
    return True, "slug_filename_match: OK"


def check_pandoc_clean(repo: Path) -> tuple[bool, str]:
    """Body Markdown should not contain Liquid tokens — even though
    render_with_liquid: false makes Jekyll skip Liquid in bodies, the
    Pandoc export pipeline (deferred) prefers truly Liquid-free input."""
    failures: list[str] = []
    for path, fm, body in _iter_stories(repo):
        slug = fm.get("slug", path.stem)
        if "{{" in body or "{%" in body:
            failures.append(f"{slug}: body contains Liquid braces")
    if failures:
        return False, "pandoc_clean: " + "; ".join(failures)
    return True, "pandoc_clean: OK"


# ----- runner -----

CHECKS: list[Callable[[Path], tuple[bool, str]]] = [
    check_homepage_untouched,
    check_exclude_completeness,
    check_theme_references_resolve,
    check_theme_stubs_exist,
    check_hero_alt_required,
    check_inline_image_alt,
    check_state_consistency,
    check_state_inventory_cross_reference,
    check_frontmatter_contract,
    check_slug_filename_match,
    check_pandoc_clean,
]


def run_all(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    warnings: list[str] = []
    for check in CHECKS:
        ok, msg = check(repo)
        if not ok:
            failures.append(msg)
        elif "WARN" in msg:
            warnings.append(msg)
    if failures:
        return False, "\n".join(failures + warnings)
    return True, "\n".join(warnings) if warnings else "OK"


def _summary(repo: Path) -> str:
    n_stories = sum(1 for _ in _iter_stories(repo))
    n_themes = len(_load_themes(repo))
    inv_path = repo / "_data" / "saves_inventory.json"
    n_inv = 0
    if inv_path.exists():
        n_inv = len(json.loads(inv_path.read_text()).get("saves", []))
    return f"verify: OK ({n_stories} stories, {n_themes} themes, {n_inv} inventory entries)"


def main() -> int:
    repo = Path.cwd()
    ok, msg = run_all(repo)
    if not ok:
        print(msg, file=sys.stderr)
        return 1
    if msg and msg != "OK":
        print(msg)  # warnings
    print(_summary(repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 11.2: Run tests to verify they pass**

```bash
source .venv/bin/activate
pytest tests/test_verify.py -v
```

Expected: every test passes (green bar). If any fail, fix `verify.py` until they pass; do not modify the tests unless a test itself is wrong.

- [ ] **Step 11.3: Run verify.py against the real repo**

```bash
python scripts/verify.py
```

Expected output:

```
verify: OK (0 stories, 0 themes, 0 inventory entries)
```

If failures appear, the scaffolding is missing something — fix and re-run.

- [ ] **Step 11.4: Commit verify.py**

```bash
git add scripts/verify.py
git commit -m "scaffold(stories): implement verify.py (TDD green bar)"
```

---

## Task 12 — `scripts/build-check.sh`

**Files:**
- Create: `scripts/build-check.sh`

- [ ] **Step 12.1: Write `scripts/build-check.sh`**

```bash
#!/usr/bin/env bash
# Local Jekyll build wrapper that asserts the homepage passed through
# byte-identically. Run before pushing layout or config changes.
set -euo pipefail

bundle exec jekyll build

# Verify homepage assets passed through verbatim.
diff -q index.html _site/index.html
diff -q style.css _site/style.css
diff -q CNAME _site/CNAME
diff -q favicon.ico _site/favicon.ico
diff -rq media/ _site/media/

echo "build-check: OK"
```

- [ ] **Step 12.2: Make it executable**

```bash
chmod +x scripts/build-check.sh
```

- [ ] **Step 12.3: Run it end-to-end**

```bash
bash scripts/build-check.sh
```

Expected: ends with `build-check: OK`. If any `diff` produces output, the homepage was modified — investigate.

- [ ] **Step 12.4: Commit**

```bash
git add scripts/build-check.sh
git commit -m "scaffold(stories): add build-check.sh (jekyll build + homepage diff)"
```

---

## Task 13 — Cleanup: delete old plan, update CLAUDE.md

**Files:**
- Delete: `docs/stories-plan.md`
- Modify: `CLAUDE.md`

- [ ] **Step 13.1: Delete old plan**

```bash
git rm docs/stories-plan.md
```

- [ ] **Step 13.2: Update `CLAUDE.md`**

Read the current file. Replace the reference to `docs/stories-plan.md` with `docs/superpowers/specs/2026-04-27-stories-design.md`. Also update the "What's NOT in the repo yet" section to reflect that scaffolding is now done.

The exact replacements (other content stays as-is):

- Replace `Authoritative plan: [\`docs/stories-plan.md\`](docs/stories-plan.md). **Read that file first** before starting any stories-related work.` with: `Authoritative spec: [\`docs/superpowers/specs/2026-04-27-stories-design.md\`](docs/superpowers/specs/2026-04-27-stories-design.md). **Read that file first** before starting any stories-related work.`

- Replace the entire "What's NOT in the repo yet" section content with:

  ```
  ## What's been scaffolded vs. still pending

  Scaffolding is complete (PR 1): `_config.yml`, six layouts, three includes, three empty `_data/*` files, `_stories/`, `stories/index.md`, `stories/themes/index.md`, `assets/stories/stories.css`, `scripts/verify.py`, `scripts/build-check.sh`, `Gemfile`/`Gemfile.lock`, `.env.example`. Homepage cohabitation verified.

  Still pending:
  - PR 2: `scripts/fetch_saves.py` ingestion script. Needs your `.env` populated with `BSKY_HANDLE` and `BSKY_APP_PASSWORD` first.
  - PR 3: First bulk-draft of stories from real saves.
  - PR 4: First cull + polish + publish pass.
  ```

- Replace `## Things to read before acting on this project` list:

  ```
  ## Things to read before acting on this project
  1. This file.
  2. `docs/superpowers/specs/2026-04-27-stories-design.md` — full design spec.
  3. `docs/superpowers/plans/2026-04-27-stories-pr1-scaffolding.md` — PR 1 plan (now executed).
  4. The existing homepage (`index.html`, `style.css`, `media/`) to confirm it is untouched.
  ```

- [ ] **Step 13.3: Commit**

```bash
git add CLAUDE.md docs/stories-plan.md
git commit -m "docs(stories): remove superseded plan, point CLAUDE.md to new spec"
```

---

## Task 14 — Final verification, push, summary

- [ ] **Step 14.1: Run the full pre-push pipeline**

```bash
source .venv/bin/activate
python scripts/verify.py
bash scripts/build-check.sh
pytest tests/test_verify.py -v
```

Expected: all three exit 0, last command shows green bar for every test.

- [ ] **Step 14.2: Confirm working tree is clean**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 14.3: Push**

```bash
git push -u origin claude/review-bluesky-stories-plan-ItxMr
```

Expected: push succeeds. Retry up to 4 times with exponential backoff on transient network failures (per session rules).

- [ ] **Step 14.4: Write a brief handoff summary**

Append to a new section in CLAUDE.md *or* leave a comment in the next session — does not require its own commit. The summary should cover:

- What scaffolding landed (link the PR 1 plan).
- The exact commands for the curator to run locally on first checkout (`bundle install`, `python -m venv .venv`, etc.).
- The clear next step: populate `.env` and request PR 2 (fetch script).

---

## Self-review

After all tasks are executed, verify:

**Spec coverage** — every requirement in `docs/superpowers/specs/2026-04-27-stories-design.md`:

| Spec section | Implemented in |
|---|---|
| §1 Repo layout & cohabitation | Tasks 1, 2, 3, 4, 5, 6 |
| §2 Data model | Task 3 (empty data files); the schemas are exercised by Task 10 fixtures |
| §3 Stories collection & frontmatter | Task 2 (`render_with_liquid: false`), Task 5 (story layout), Task 11 (frontmatter contract check) |
| §4 Themes (yml + per-theme stubs) | Task 3, Task 6, Task 11 (stub-existence check) |
| §5 Layouts, CSS, aesthetic | Tasks 4, 5, 6, 7 |
| §6 Images (alt rules, hero credit) | Task 5 (hero rendering), Task 11 (`hero_alt_required`, `inline_image_alt`) |
| §7 Ingestion script | Deferred to PR 2 (intentional) |
| §8 Authoring workflow | Deferred to PR 2/3/4 (intentional) |
| §9 Verification | Tasks 10, 11, 12 |
| §10 Out-of-scope, relocation, open questions | Reflected in CLAUDE.md update (Task 13) |

**Placeholder scan** — none of "TBD", "TODO", "implement later" should appear in the saved plan. (Verified empty before commit.)

**Type consistency** — function names used in `tests/test_verify.py` (`check_homepage_untouched`, `check_exclude_completeness`, `run_all`, etc.) match the definitions in `scripts/verify.py`.

---

## Execution handoff

**Recommended approach:** **Inline execution** via `superpowers:executing-plans`. The user is unavailable overnight, so subagent-per-task review checkpoints would idle. Inline is a single continuous session with self-checkpoints at the natural commit boundaries already in the plan.



# Stories Compilation — Design Specification

> **Status**: design approved 2026-04-27. Implementation plan pending.
> **Supersedes**: `docs/stories-plan.md` (delete in the same commit as scaffolding PR 1).
> **Working branch for scaffolding**: `claude/bluesky-stories-compilation-milg9` (per CLAUDE.md).

---

## Context

The user keeps news and other posts on BlueSky via the Saved/Bookmarks feature. These saved posts cluster around recurring themes and deserve a longer-form home than an ephemeral social feed. This project turns that collection into a durable, curated, thematically organized, chronologically ordered archive — a public reading site that doubles as a Pandoc-clean corpus for a future book export.

It will be built and hosted inside the `tenorune.github.io` repo, but has **no relationship or linkage to the existing `lightseed.net` homepage**. The homepage stays completely untouched; the stories project is a self-contained, independent piece of work that happens to share the repo as its build host.

Each story entry contains:

- A one-sentence summary
- A 2–3 paragraph synopsis (drafted by Claude after reading the source article)
- A source citation and link
- Optional images (curator-managed)
- One or more emergent themes

### Locked decisions

| Area | Decision |
|---|---|
| Purpose | Hybrid: public reading site + book-export-ready (Pandoc) |
| Build | Jekyll, GitHub Pages classic build (whitelist plugins only) |
| Homepage relationship | Truly independent — no shared CSS, no nav crosslinks |
| Scale target | ~100–300 stories, ~5–15/month, modest archive |
| Ingestion | Local Python script in `scripts/`, run by curator; full inventory artifact |
| Authoring | Hybrid: Claude bulk-drafts as `published: false` → curator culls → curator polishes (Claude does ad-hoc revisions on request) |
| URL structure | Flat `/stories/:slug/` |
| Themes | Emergent; themes index page + per-theme pages (list view + full-compilation view) |
| Aesthetic | Long-form serif, ~38rem column, generous leading; system-font stack (no webfonts) |

---

## Section 1 — Repository layout & cohabitation

The project shares a repo with the existing `lightseed.net` homepage but must remain truly independent. Cohabitation works because Jekyll passes through any root file with no YAML front matter automatically — and the homepage assets (`index.html`, `style.css`, `CNAME`, `favicon.ico`, `media/`) have no front matter, so they end up in `_site/` byte-identical to their source. The `_config.yml` `exclude:` list covers only files that should NOT appear in `_site/` at all: project bookkeeping (`CLAUDE.md`, `docs/`, `README.md`) and dev artifacts (`Gemfile`, `.env`, `.bundle/`, `.superpowers/`, `scripts/`, `tests/`, etc.).

> **Errata note (2026-04-27 implementation):** The original draft of this section asserted "Jekyll, once activated, processes the whole repo by default — so cohabitation is enforced by an explicit `exclude:` list including the homepage files." That was factually wrong. Listing homepage files in `exclude:` *removes* them from `_site/` entirely (the deployed site would have no homepage at all). The corrected approach above is what's actually shipped. The `homepage_untouched` check in Section 9 + `scripts/build-check.sh` provides the cohabitation safety guarantee.

Project-owned files use a recognizable namespace (`stories_*` includes, `assets/stories/`, `*saves*` scripts) so a future relocation to a subdomain is a clean copy of an obvious set.

```
/                                       (repo root)
├── _config.yml                  [P]    Jekyll config + explicit exclude:
├── Gemfile                      [P]    local dev only
├── Gemfile.lock                 [P]    committed for dev reproducibility
├── _layouts/
│   ├── default.html             [P]    project page shell
│   ├── story.html               [P]
│   ├── stories_index.html       [P]
│   ├── themes_index.html        [P]
│   ├── theme_list.html          [P]    single theme: titles + summaries
│   └── theme_compilation.html   [P]    single theme: full stories inline
├── _includes/
│   ├── stories_header.html      [P]
│   ├── stories_footer.html      [P]
│   └── story_card.html          [P]
├── _data/
│   ├── saves_inventory.json     [P]    raw saves; fetch-script-owned
│   ├── saves_state.json         [P]    per-URI editorial state
│   └── themes.yml               [P]    emergent themes
├── _stories/                    [P]    one .md per story (drafts + published)
├── stories/
│   ├── index.md                 [P]    → stories_index layout
│   └── themes/
│       ├── index.md             [P]    → themes_index layout
│       └── <slug>/              [P]    one directory per theme (machine-generated)
│           ├── index.md         [P]    → theme_list layout
│           └── all.md           [P]    → theme_compilation layout
├── assets/stories/
│   ├── stories.css              [P]    scoped to project pages only
│   └── <slug>/                  [P]    per-story image folder, on demand
├── scripts/
│   ├── fetch_saves.py           [P]    AT Protocol ingestion (run locally)
│   ├── verify.py                [P]    pre-commit invariant checks
│   ├── build-check.sh           [P]    Jekyll build + homepage byte check
│   └── requirements.txt         [P]
├── docs/
│   └── superpowers/specs/
│       └── 2026-04-27-stories-design.md   [P] this design doc
├── .env.example                 [P]    placeholder credentials, committed
├── .gitignore                   [P]    .superpowers/, .env, _site/, .bundle/, vendor/
│
├── index.html                          UNCHANGED (in exclude:)
├── style.css                           UNCHANGED (in exclude:)
├── CNAME, favicon.ico, media/          UNCHANGED (in exclude:)
├── LICENSE                             UNCHANGED
├── CLAUDE.md                           UNCHANGED structurally; updated for new spec
└── docs/stories-plan.md                DELETED in scaffolding PR 1
```

`[P]` marks project-owned files — the move list for relocation. Notable changes from the prior plan:

- The original `processed_manifest.json` is replaced by `saves_state.json` (broader scope: also tracks `culled` and `skipped` URIs, which the cull workflow needs).
- The original `.github/workflows/fetch-bluesky.yml` is gone — ingestion is local-only.
- Per-theme directory under `stories/themes/<slug>/` holds two stub files (one for the list view, one for the full compilation).
- New `scripts/verify.py` and `scripts/build-check.sh` enforce build invariants pre-commit.

---

## Section 2 — Data model & state tracking

Two `_data/` files with strict ownership boundaries plus the themes file. The fetch script never touches editorial state; editorial operations never touch raw inventory. This separation is the safety guarantee — a botched fetch can't corrupt your decisions, and a botched cull can't lose inventory.

### `_data/saves_inventory.json` — raw saves, fetch-owned

Append-only from the fetch script's perspective. Existing entries are never mutated; new saves are added.

```json
{
  "fetched_at": "2026-04-27T10:14:00Z",
  "saves": [
    {
      "uri": "at://did:plc:abc.../app.bsky.feed.post/3kxyz...",
      "saved_at": "2026-04-12T18:31:00Z",
      "post_text": "First 300 chars of the BlueSky post body...",
      "embed": {
        "type": "external",
        "url": "https://example.org/article",
        "title": "Original article title",
        "description": "Article description from the embed card"
      },
      "author": {
        "handle": "someone.bsky.social",
        "display_name": "Someone Realname",
        "did": "did:plc:..."
      }
    }
  ]
}
```

Keyed by `uri`. Ordering: `saved_at` desc. The `post_text` and `embed` fields are what the bulk-draft pass uses to pre-fill `source_url`, `source_title`, `source_publication`, `source_author`.

### `_data/saves_state.json` — editorial state, agent/curator-owned

Exactly one entry per URI that has been touched by an editorial decision. URIs not present are implicitly `pending`.

```json
{
  "updated_at": "2026-04-27T10:14:00Z",
  "states": {
    "at://did:plc:abc.../app.bsky.feed.post/3kxyz...": {
      "status": "drafted",
      "story_slug": "climate-grief-in-the-pnw",
      "first_processed_at": "2026-04-15T20:00:00Z",
      "last_action_at": "2026-04-15T20:00:00Z",
      "notes": "optional curator note"
    }
  }
}
```

**Status values:**

| Value | Meaning |
|---|---|
| (absent) | Not yet processed (implicitly pending). |
| `drafted` | Bulk-draft created `_stories/<slug>.md` with `published: false`. Claude's prose, untouched by curator. |
| `polished` | Curator has edited the prose; still `published: false`. Decision to ship is pending. |
| `published` | `published: true` in frontmatter; live on the site. |
| `culled` | Story file deleted. Do not redraft. |
| `skipped` | Marked "don't draft this" before any draft was written. |

`story_slug` is null for `culled`/`skipped`, present for `drafted`/`polished`/`published`.

**State transitions:**

```
                ┌─→ drafted ─→ polished ─→ published
pending ─→ ─────┤      │           │           │
                │      ├─→ culled ←┤           │
                └─→ skipped         (or back to drafted/polished
                                     on "unpublish")
```

`published: true` in story frontmatter remains the source of truth for site visibility. The state field is editorial workflow tracking — useful for queries like "show me stories I've polished but haven't shipped".

### `_data/themes.yml` — emergent themes (detail in Section 4)

List of theme objects with `slug`, `label`, `description`. Updated by the bulk-draft pass (appends new themes) and by the cull pass (merges, prunes, edits descriptions).

### Ownership rules

| File | Fetch script | Bulk-draft pass (Claude) | Cull/polish (curator + Claude) |
|---|---|---|---|
| `saves_inventory.json` | **read + append new** | read only | read only |
| `saves_state.json` | never touches | **append/update entries** | **update entries** |
| `themes.yml` | never touches | **append new themes** | **edit/merge/prune** |
| `_stories/*.md` | never touches | **create as drafts** | **promote / edit / delete** |

### Atomicity / safety

- All writes are full-file rewrites (no streaming append). JSON parse → mutate in memory → write atomically (`<file>.tmp` + `os.rename`). Prevents partial-write corruption.
- Both data files pretty-printed (`indent=2`, sorted keys) so diffs are reviewable.
- `saves_state.json` is the single source of truth for "is this URI done?" — derived from neither inventory nor `_stories/` contents.

---

## Section 3 — Stories collection & frontmatter contract

### Collection configuration (`_config.yml`)

```yaml
collections:
  stories:
    output: true
    permalink: /stories/:slug/
    render_with_liquid: false
```

`render_with_liquid: false` is the load-bearing line. It tells Jekyll: do not run story body Markdown through Liquid before processing. Three benefits:

1. Eliminates the entire class of "an article title or quote contains `{{` and breaks the build" bugs.
2. Bodies become true plain Markdown — what Jekyll renders is exactly what Pandoc reads.
3. No `{% raw %}` escaping rules to remember.

Frontmatter is still parsed normally; only the body skips Liquid.

### File naming

`_stories/YYYY-MM-DD-<slug>.md` where the date is derived from `bluesky_saved_at`. The date prefix is purely filesystem-chronological ordering — it does **not** appear in URLs (permalinks are `/stories/:slug/`). Keeping it makes `ls _stories/` and `git log` readable.

### Frontmatter contract

```yaml
---
# Required identification
title: "Climate Grief in the Pacific Northwest"
slug: climate-grief-in-the-pnw
summary: "One-sentence summary of the story."
date: 2026-04-12              # YYYY-MM-DD only; derived from bluesky_saved_at
themes: [climate-grief, infrastructure]

# Required source citation
source_url: "https://example.org/article"
source_title: "Original article title"
source_publication: "The New York Times"

# Required BlueSky provenance
bluesky_uri: "at://did:plc:abc.../app.bsky.feed.post/3kxyz..."
bluesky_saved_at: 2026-04-12T18:31:00Z

# Optional
source_author: "Jane Doe"           # byline; many pieces are unsigned
source_published_at: 2026-04-10     # when the article was originally published
hero_image: /assets/stories/climate-grief-in-the-pnw/hero.jpg
hero_image_alt: "Smoke over a mountain ridge."   # REQUIRED if hero_image present
hero_image_credit: "Photo: Jane Photographer / Reuters"

# Publishing
published: false              # default for fresh drafts; flip to true to publish
---

Synopsis paragraph one. Plain Markdown only — no Liquid tags, no raw HTML.

Synopsis paragraph two.

![Inline image alt text](/assets/stories/climate-grief-in-the-pnw/figure-1.jpg)

Synopsis paragraph three (optional).
```

### Field rules

| Field | Required? | Notes |
|---|---|---|
| `title`, `slug`, `summary` | Yes | `slug` must match the slug portion of the filename. |
| `date` | Yes | YYYY-MM-DD; derived from `bluesky_saved_at`. Required by Jekyll for collection items. |
| `themes` | Yes | List of slugs; every value must exist in `_data/themes.yml`. |
| `source_url`, `source_title`, `source_publication` | Yes | Use `"Unknown"` for `source_publication` when truly unknown. |
| `bluesky_uri`, `bluesky_saved_at` | Yes | The provenance link. |
| `source_author` | No | Many pieces are unsigned. |
| `source_published_at` | No | Often unknown. |
| `hero_image` | No | If set, `hero_image_alt` becomes required. |
| `hero_image_alt` | Conditional | Required iff `hero_image` is set. Build verification fails otherwise. |
| `hero_image_credit` | No | Encouraged when applicable. |
| `published` | Yes | Defaults to `false` for new drafts; flip to `true` to publish. |

### Body rules

- **Plain Markdown only.** No Liquid (now enforced by `render_with_liquid: false`). No raw HTML — Pandoc handles HTML poorly when converting to print formats.
- **Image references use root-relative paths** under `/assets/stories/<slug>/`. Same paths work on both `lightseed.net/stories/` and a future `stories.lightseed.net/`.
- **Length target:** 2–3 paragraphs. Soft guideline, not enforced.
- **No inline metadata.** All citation/source info lives in frontmatter, not in body prose. The story layout renders citation from frontmatter; this keeps Pandoc export clean.

### Drafts

`published: false` is the only mechanism. Drafts:

- Do **not** render to HTML.
- Do **not** appear in `/stories/` index, theme pages, sitemap, or RSS.
- **Are still committed to git** — drafts are first-class content, just not site-visible.

To publish: change one frontmatter line to `published: true`, commit. Update the corresponding URI's status in `saves_state.json` to `published` in the same commit.

### Theme reference rule

Any theme listed in a story's `themes:` field must exist in `_data/themes.yml`. The bulk-draft pass appends new themes there in the same commit. A typo'd theme would silently render no chip and not appear on any theme page — `scripts/verify.py` (Section 9) catches this at pre-commit time.

---

## Section 4 — Themes

### `_data/themes.yml` schema

```yaml
- slug: climate-grief
  label: climate grief
  description: "Personal and collective reckoning with ecological loss."

- slug: infrastructure
  label: infrastructure
  description: "Roads, grids, water — the physical scaffolding of civic life."
```

Three fields per theme: `slug` (URL-safe, matches what stories reference), `label` (display text, can have spaces and casing), `description` (one sentence; appears on the themes index and at the top of each theme page).

Slugs are stable identifiers — once stories reference a slug, renaming it requires updating every story's frontmatter. The `label` is freely editable.

### Themes index — `/stories/themes/`

A single page rendered by `_layouts/themes_index.html`. Iterates `site.data.themes`, sorts alphabetically by `label`, shows for each theme:

- The label as a link to `/stories/themes/<slug>/`
- The description
- A count of published stories using that theme (computed from `site.collections.stories.documents` filtered by `themes contains theme.slug` and `published`)

### Per-theme pages — two URLs per theme

Each theme has **two** URLs, both rendered from machine-generated stub files in a directory:

```
stories/themes/<slug>/
├── index.md         permalink: /stories/themes/<slug>/      layout: theme_list
└── all.md           permalink: /stories/themes/<slug>/all/  layout: theme_compilation
```

| URL | Layout | Content |
|---|---|---|
| `/stories/themes/<slug>/` | `theme_list.html` | Header (label, description) + chronological list of stories (date · title · summary), newest-first. Includes a "Read all stories in this theme →" link to `/all/`. |
| `/stories/themes/<slug>/all/` | `theme_compilation.html` | Header + every story rendered inline, oldest-first (chapter-like reading order). Each story shows title, meta, hero, synopsis, source link, separated by strong dividers. Theme chips on individual stories are omitted (redundant in this view). |

The `/all/` view maps cleanly onto a Pandoc chapter export — each theme is effectively a chapter in the future book pipeline.

Each stub file is ~5 lines of frontmatter, machine-generated. The directory grouping keeps each theme's bookkeeping co-located, so deleting/merging a theme is `rm -r stories/themes/<slug>/` plus the `themes.yml` edit plus the story-frontmatter sweep.

### Theme operations

| Operation | What happens |
|---|---|
| **Append (bulk-draft pass)** | Claude adds a new entry to `themes.yml` and creates the `<slug>/index.md` and `<slug>/all.md` stubs. Both committed with the story batch. |
| **Edit description / label** | One-line edit to `themes.yml`. Slug unchanged → no other files touched. |
| **Rename slug** | Edit `themes.yml` slug + rename stub directory + update every story's `themes:` field. Multi-file commit; Claude handles. Rare. |
| **Merge two themes** | Pick a winning slug; update every story referencing the loser to use the winner; delete the loser's `themes.yml` entry and stub directory. Single commit. |
| **Prune (delete) a theme** | Same as merge but with no winner — every story using it has the theme removed from its `themes:` field. If any story ends up with empty `themes:`, it's flagged for curator decision before commit. |

### Validation

Every value in a story's `themes:` field must be a slug present in `themes.yml`. Every theme in `themes.yml` must have both stub files at `stories/themes/<slug>/index.md` and `stories/themes/<slug>/all.md`. `scripts/verify.py` enforces both invariants pre-commit.

### Theme display in stories

On a single story page, themes render as small chips in the metadata area (label as link to `/stories/themes/<slug>/`). Visual treatment is in Section 5.

---

## Section 5 — Layouts, CSS, aesthetic

### Layout files

Six small templates, each with one job:

```
_layouts/default.html              page shell (header, footer, css link)
_layouts/story.html                single story page
_layouts/stories_index.html        chronological list of all published stories
_layouts/themes_index.html         list of all themes
_layouts/theme_list.html           single theme: titles + summaries
_layouts/theme_compilation.html    single theme: full stories inline
```

`default.html` is the only one that includes `_includes/stories_header.html` and `_includes/stories_footer.html`; the five content layouts extend it.

### Typography & CSS strategy

System-font stack — no web fonts, no external requests, fast first paint. Print version uses identical-feeling type:

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

body {
  font-family: var(--serif);
  font-size: 1.0625rem;
  line-height: var(--leading);
  color: var(--ink);
  background: var(--paper);
}

main { max-width: var(--measure); margin: 0 auto; padding: 2rem 1.25rem; }
.meta, nav, footer, .label { font-family: var(--sans); }
```

CSS lives at `assets/stories/stories.css` and is loaded **only by project layouts**. The homepage's `style.css` is untouched and never references the project (verified in Section 9).

### Wireframe — single story (`/stories/<slug>/`)

```
┌─────────────────── /stories/<slug>/ ───────────────────┐
│   STORIES                                       themes │  ← sans, small
│  ─────────────────────────────────────────────────────  │
│   Climate Grief in the Pacific Northwest                │  ← serif, h1
│   ┌───────────────────────────────────────────────┐     │
│   │           [hero image, full column width]      │     │
│   └───────────────────────────────────────────────┘     │
│   Photo: Jane Photographer / Reuters                    │  ← muted sans
│                                                         │
│   Personal and collective reckoning with ecological     │  ← summary, italic
│   loss reshapes how a generation reads weather reports. │
│                                                         │
│   #climate-grief   #infrastructure                      │  ← theme chips, sans
│   Saved Apr 12, 2026 · Source: The New York Times,      │  ← meta line
│   Jane Doe (Apr 10, 2026)                               │
│   ─────────────                                         │
│   Synopsis paragraph one in serif body. Generous        │
│   line-height. Comfortable measure.                     │
│   Synopsis paragraph two...                             │
│   [inline figure, full column]                          │
│   Synopsis paragraph three...                           │
│   ─────────────                                         │
│   Read original →  example.org/article                  │  ← prominent, sans
└─────────────────────────────────────────────────────────┘
```

### Wireframe — stories index (`/stories/`)

```
┌──────────────────── /stories/ ─────────────────────────┐
│   STORIES                                       themes │
│  ─────────────────────────────────────────────────────  │
│   Compiled from saved BlueSky posts.                    │  ← optional intro
│   2026                                                  │  ← year heading, sans
│   Apr 12  Climate Grief in the Pacific Northwest        │  ← serif title
│           One-sentence summary in italic.               │
│           climate-grief · infrastructure                │  ← muted theme list
│   Apr 09  Another Story Title                           │
│   ...                                                   │
│   2025                                                  │
│   Dec 20  ...                                           │
└─────────────────────────────────────────────────────────┘
```

### Wireframe — themes index (`/stories/themes/`)

```
┌──────────────── /stories/themes/ ──────────────────────┐
│   STORIES                                       themes │
│  ─────────────────────────────────────────────────────  │
│   THEMES                                                │
│   climate grief                              14 stories │  ← serif label
│   Personal and collective reckoning with                │  ← italic serif
│   ecological loss.                                      │
│   infrastructure                              7 stories │
│   Roads, grids, water — the physical                    │
│   scaffolding of civic life.                            │
└─────────────────────────────────────────────────────────┘
```

### Wireframe — theme list view (`/stories/themes/<slug>/`)

```
┌────── /stories/themes/climate-grief/ ──────────────────┐
│   STORIES                                       themes │
│  ─────────────────────────────────────────────────────  │
│   Theme: climate grief                                  │
│   Personal and collective reckoning with ecological     │
│   loss.                                                 │
│   Read all stories in this theme →                      │  ← link to /all/
│   ─────────────                                         │
│   2026                                                  │
│   Apr 12  Climate Grief in the Pacific Northwest        │
│           One-sentence summary.                         │
│   Mar 03  Another Story In This Theme                   │
│   ...                                                   │
└─────────────────────────────────────────────────────────┘
```

### Wireframe — theme compilation view (`/stories/themes/<slug>/all/`)

```
┌────── /stories/themes/climate-grief/all/ ──────────────┐
│   STORIES                                       themes │
│  ─────────────────────────────────────────────────────  │
│   Theme: climate grief — full compilation               │
│   Personal and collective reckoning with ecological     │
│   loss.                                                 │
│   View as list →                                        │  ← back to list view
│   ═══════════════════════════════════                   │  ← strong divider
│   Climate Grief in the Pacific Northwest                │  ← story 1 (oldest first)
│   Apr 12, 2026 · The New York Times, Jane Doe           │
│   [hero image]                                          │
│   Photo: Jane Photographer / Reuters                    │
│   Personal and collective reckoning... (summary)        │
│   Synopsis paragraph one...                             │
│   Synopsis paragraph two...                             │
│   Synopsis paragraph three...                           │
│   Read original at example.org →                        │
│   ═══════════════════════════════════                   │
│   Another Story In This Theme                           │  ← story 2
│   Mar 03, 2026 · The Atlantic                           │
│   ...                                                   │
└─────────────────────────────────────────────────────────┘
```

### Header / footer

`_includes/stories_header.html` is just the wordmark "STORIES" linked to `/stories/` and a single nav link "themes" → `/stories/themes/`. No homepage link, no other navigation.

`_includes/stories_footer.html` is a single sans line: copyright/license notice + a small "RSS" link (since `jekyll-feed` is on). No social links, no analytics.

### Visual rules

- Theme chips: small caps, sans, accent color, no background fill.
- Hero image: full content width, no rounded corners, no shadow.
- Inline figures: same width as the text column.
- Source link at the bottom of each story is intentionally prominent — the project exists to honor sources.
- Compilation view: strong horizontal rule between stories; theme chips omitted (every story shares the theme).
- No JavaScript anywhere in the default scaffold.

---

## Section 6 — Images

### Storage convention

One folder per story at `assets/stories/<slug>/`. Folder is created on demand (no images = no folder). Inside:

- `hero.<ext>` — optional featured image (referenced by `hero_image` in frontmatter)
- arbitrary inline images named for what they are (e.g. `figure-1.jpg`, `protest-march.jpg`)

Slug folder name matches the story's `slug` exactly. Renaming a story's slug (rare) is a multi-file operation: rename folder + rename story file + update internal references.

### Formats and sizes

| Aspect | Rule |
|---|---|
| Allowed formats | `.jpg`, `.png`, `.webp` preferred. `.gif` only for genuinely animated content. Avoid `.tiff`, `.heic`, raw camera formats. |
| Soft size cap | 500 KB per image. Larger files trigger a "let me resize this" prompt during conversational add. |
| Hard size cap | 2 MB. Above this the image is rejected — curator must resize before re-attempting. |
| Animated GIFs | Cap at 2 MB regardless. Above that, convert to looping `.webp` or rejected. |
| Repo-wide budget | Soft target: total `assets/stories/` under 100 MB. At modest scale (~300 stories × ~3 images × 300 KB) we're well inside this. |

No automatic image processing (resize, compression, format conversion) at scaffolding. Curator does it before pasting.

### Alt text rules

- **Hero images: `hero_image_alt` is required when `hero_image` is set.** Build verification fails the build if violated.
- **Inline images: alt text is required.** Pure decoration is not a use case — every image either describes something or shouldn't be there. Standard Markdown syntax: `![alt text](/path/to/file.jpg)`. Empty alt (`![]`) is a build-time warning.
- Alt text describes the image's content/meaning, not "image of …". Follows web accessibility best practices.

### Hero image credit

`hero_image_credit` is optional but encouraged. Renders below the image as muted sans (`Photo: Jane Photographer / Reuters`). Inline images don't have a structured credit field — if attribution is needed, work it into surrounding body prose.

### Provenance — where do images come from?

Three sources, in order of preference:

1. **Source article asset.** The original article's hero/figure image. Curator pastes the URL or downloads it locally first; Claude doesn't fetch it autonomously (avoid surprise downloads).
2. **BlueSky embedded media.** If the saved post itself includes images, those are *not* automatically downloaded by the fetch script. The inventory JSON records their URLs, but pulling them into the repo is a deliberate curator action.
3. **Curator-supplied.** Anything else — your own photos, public-domain stock, screenshots.

### Conversational add/remove flow

| You say | What happens |
|---|---|
| "Add this image to story X as hero" + URL or path | Claude downloads (URL) or copies (path) into `assets/stories/<slug>/hero.<ext>`, sets `hero_image`, prompts for `hero_image_alt`. Single commit. |
| "Add this as figure 1" + image | Claude places it as `assets/stories/<slug>/figure-1.<ext>`, inserts the Markdown reference at the appropriate place in the body (asks where if ambiguous), prompts for alt text. Single commit. |
| "Remove the second inline image from story X" | Claude deletes the file and strips the Markdown reference. Single commit. |
| "Remove the hero from story X" | Claude deletes the file, removes `hero_image`/`hero_image_alt`/`hero_image_credit` from frontmatter. Single commit. |
| "Replace the hero on X with this new one" | Delete + add as a single commit; new alt text required. |

Every image operation lands as **one commit per change** so `git revert` works as the rollback mechanism.

### Build-time considerations

- No image fingerprinting / cache-busting at scaffolding. If you replace an image with a same-named file, browsers may show stale versions briefly. Acceptable at this scale.
- `_site/assets/stories/` is git-ignored along with the rest of `_site/`. Originals in `assets/stories/` are committed; Jekyll copies them into the build output verbatim.

### Pandoc / book export implications

Markdown image references using root-relative `/assets/stories/<slug>/<file>` paths won't resolve directly under Pandoc — Pandoc expects paths relative to the source `.md` file or the working directory. The book pipeline (deferred) will need a small pre-processing step that rewrites `/assets/...` to `../assets/...` or similar. Flagged here so we don't forget.

---

## Section 7 — Ingestion script

A small Python program that pulls BlueSky saves into `_data/saves_inventory.json`. **Runs locally on the curator's laptop only — never in CI.**

### `scripts/fetch_saves.py`

**Runtime:** Python 3.12. No SDK — direct XRPC over HTTP via `httpx`. Single file, target ≤200 lines.

**Authentication:** loads from a local `.env` file (gitignored) at the repo root:

```env
BSKY_HANDLE=you.bsky.social
BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

The app-password risk is now de-risked because the fetch is local — failures are loud and fast. The script tries the bookmarks endpoint first; if it returns 401/403 indicating insufficient scope, it falls back to a full-session OAuth-style flow that the curator authorizes interactively (one-time browser/device flow), persisting refresh tokens in a separate gitignored file.

**Endpoints, in fallback order:**

1. `app.bsky.bookmark.getBookmarks` (or whatever the current bookmarks lexicon is at runtime — script probes for the actual method name on first run and caches the result locally).
2. `com.atproto.repo.listRecords` for the curator's own `app.bsky.feed.bookmark` collection (alternate access path if the above is namespaced differently).
3. `app.bsky.feed.getActorLikes` as a degraded fallback — explicitly tagged `source: "likes"` in the recorded entries so you can see which items came from this path.
4. **Manual JSON drop.** If all three fail, the script accepts a `--from-file <path>` argument that ingests a hand-prepared JSON in the inventory schema. Documented escape hatch.

The script writes a single line at the top of stderr indicating which path succeeded.

### Idempotency

- Keys all entries by `uri`. New saves are appended; existing entries are **never modified**.
- Sorts by `saved_at` desc on each write so the file diff is stable and the newest items are at the top.
- Updates the file's top-level `fetched_at` timestamp on every run.
- Re-running with no new saves is a no-op for the file's content section (only `fetched_at` changes).

### What it never does

- Never touches `_data/saves_state.json`, `_data/themes.yml`, `_stories/`, or anything else.
- Never downloads images. Inventory records embed URLs; pulling images is a deliberate curator action (Section 6).
- Never commits, pushes, or runs git operations. Output is just the file write.
- Never makes network calls beyond BlueSky XRPC. No analytics, no telemetry.

### Output JSON shape

Already defined in Section 2's `saves_inventory.json` schema. The script appends entries matching that exact shape; the schema is the contract between fetch and bulk-draft.

### `scripts/requirements.txt`

```
httpx>=0.27
python-dateutil>=2.9
python-dotenv>=1.0
```

Three dependencies. The dotenv loader is the only addition over the original plan.

### Local invocation

```bash
# one-time setup
python -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
cp .env.example .env  # then fill in credentials

# regular use
python scripts/fetch_saves.py
git diff _data/saves_inventory.json   # review what's new
git add _data/saves_inventory.json && git commit -m "data: refresh saves inventory"
```

`.env.example` is committed (with placeholder values) so the variable names are discoverable; `.env` itself is in `.gitignore`.

### Risks & mitigations

| Risk | Mitigation |
|---|---|
| BlueSky bookmark lexicon name changes or moves namespace | Probe-and-cache strategy + multiple fallback endpoints + manual `--from-file` escape hatch |
| App password lacks scope for bookmarks | Detect 401/403, fall through to full-session OAuth flow (one-time interactive auth, refresh tokens persisted) |
| Rate limits on first run with a large bookmark history | Pagination respected; backoff on 429 with exponential delay |
| `.env` accidentally committed | `.gitignore` includes `.env`; `.env.example` committed instead |

### Notable changes from the original plan

- **No GitHub Action.** No `.github/workflows/fetch-bluesky.yml`, no repo secrets named `STORIES_BSKY_*`, no daily cron. The auto-commit-via-`GITHUB_TOKEN` concerns (Pages-rebuild semantics, workflow recursion) are now moot.
- Full-session OAuth fallback baked in from the start.
- Manual JSON `--from-file` escape hatch as the last-resort path.

> **Errata note (2026-04-27 morning, after PR 1 shipped):** The "no local execution at all" constraint was clarified by the curator after PR 1 landed. As a result, the "local-only script" approach above was **reversed**. PR 2 now ships:
>
> - `scripts/fetch_saves.py` — same Python script, but designed to run inside GitHub Actions rather than on the curator's laptop.
> - `.github/workflows/fetch.yml` — scheduled daily fetch (07:17 UTC) + `workflow_dispatch`. Auto-commits `_data/saves_inventory.json` when the saves array changes.
> - Secrets in repo Settings → Secrets and variables → Actions: `BSKY_HANDLE`, `BSKY_APP_PASSWORD`.
>
> The OAuth fallback path is **NOT** in PR 2 because OAuth requires browser interaction which a non-interactive Action cannot perform. If the app password lacks the bookmark scope (likely), the workflow goes red with a `NoBookmarkEndpointError` listing every probed endpoint and its status code; the curator then decides between Option B (manual paste in chat) or Option D (one-time OAuth in chat → persisted refresh token in repo Secrets) as a follow-up.
>
> The original Section 7 design (local script, OAuth fallback, manual `--from-file` hatch) is preserved here for historical context. The implementation in `scripts/fetch_saves.py` is closer to the original *plan*'s approach (`docs/stories-plan.md` before it was deleted) than to this spec's Section 7 as originally written.

---

## Section 8 — Authoring workflow

Five passes, each one Claude-assisted but scoped differently. Status transitions in `saves_state.json` track progress through them.

### Pass 1 — Bulk draft (Claude-driven, no per-story approval)

Curator says: *"Draft the next N saves"* (or *"draft everything pending older than 2026-03-01"*, etc.)

Claude does the following for each selected save in one batch operation:

1. Reads `_data/saves_inventory.json`, filters to URIs whose status is `(absent)` (i.e., pending) — never touches `skipped`, `culled`, or already-drafted URIs.
2. For each pending save:
   - `WebFetch` the embed's external URL (the source article).
   - Draft `title`, one-sentence `summary`, 2–3 paragraph synopsis from the article content.
   - Consult `_data/themes.yml`. Reuse existing themes where they fit; append new themes with one-line descriptions when nothing fits.
   - For each new theme created, also create the two stub files (`stories/themes/<slug>/index.md` and `all.md`) per Section 4.
   - Compute slug from title (URL-safe kebab-case, max ~60 chars, deduped against existing stories).
   - Write `_stories/<saved_at>-<slug>.md` with frontmatter and body per Section 3's contract, **`published: false`**.
   - Update `_data/saves_state.json`: add an entry for this URI with `status: drafted`, `story_slug`, `first_processed_at`, `last_action_at`.
3. **Commits the entire batch as a single commit.** Message: `drafts: bulk-draft N stories from saves`.
4. Reports a brief summary to curator: *"Drafted N stories. Created K new themes: …. Used existing themes: …. Sources that wouldn't fetch: …."*

**No per-story approval gate.** Quality bar must be high enough that culling-rather-than-rewriting is the typical action. If a source URL fails to fetch, that URI's status stays `(absent)` and it's noted in the summary so curator can intervene manually.

### Pass 2 — Cull (curator-driven, Claude-assisted)

Some time after a bulk draft, curator reviews. Operations expressed conversationally:

| Curator says | What happens |
|---|---|
| "Cull stories X, Y, Z" | Claude deletes the story files, removes their image folders if any, sets the URIs' status to `culled` in `saves_state.json`. Single commit per cull batch. |
| "Show me drafts that mention [topic]" | Claude greps `_stories/*.md` filtered by `published: false`, reports paths + summaries. |
| "Merge themes X and Y, keeping X" | Claude updates every story referencing Y to use X instead, deletes Y from `themes.yml` and Y's stub directory. Single commit. |
| "Prune theme X" | Claude removes X from every story's `themes:` field; if any story ends up with empty `themes:`, it's flagged for curator decision; X deleted from `themes.yml` and stubs. |
| "Edit theme X's description to: …" | One-line edit to `themes.yml`. |

Cull is destructive and intentional — `git revert` if curator changes their mind.

### Pass 3 — Polish (curator-driven, in editor)

Curator opens keepers in their editor and edits. Status doesn't auto-update — when curator finishes a polish pass, they tell Claude *"mark stories X, Y, Z as polished"* and Claude updates `saves_state.json` accordingly. Single commit, message like `state: mark 3 stories polished`.

Curator can also ask Claude for ad-hoc help during polish (Pass 4 operations interleaved).

### Pass 4 — Ad-hoc revisions (Claude-assisted, anytime)

| Curator says | What happens |
|---|---|
| "Tighten paragraph 2 of story X" | Claude edits the body, shows diff, commits on approval. |
| "Regenerate the synopsis in a more somber tone" | Claude re-reads `source_url` via WebFetch, drafts fresh text, shows for approval, commits. |
| "Swap the summary sentence for X" | Single-line edit, commit. |
| "Add theme Y to story X" | Verifies/appends to `themes.yml`, edits frontmatter, commit. |
| "Unpublish story X" | Sets `published: false` in frontmatter; updates state to `polished` (or `drafted` if it was never edited). |
| "Delete story X" | Removes file + image folder; sets state to `culled`. |

Unlike Pass 1, these *do* show diffs before committing — curator has decided this story matters enough to polish, so changes get a second look.

### Pass 5 — Publish (curator-driven, mostly mechanical)

| Curator says | What happens |
|---|---|
| "Publish stories X, Y, Z" | Claude sets `published: true` on each file's frontmatter, updates state to `published` in `saves_state.json`. Single commit message `publish: 3 stories`. |
| "Publish all polished stories" | Same as above for every URI with state `polished`. |
| "Publish everything ready" | Equivalent — explicit alias for the common bulk operation. |

### Skipping URIs you never want drafted

Two ways to mark a save as `skipped` before any draft:

| Curator says | What happens |
|---|---|
| "Skip URIs A, B, C" (with explicit URIs or inventory entries) | Updates `saves_state.json` directly; single commit. |
| "Skip all saves from author @handle" | Filters inventory, updates state for each match. |

`skipped` is the right status for accidental saves, duplicates of saves processed under another URI, or saves that don't fit the project's spirit.

### What's excluded from this workflow

- **No automatic re-drafting.** Once a URI has any non-`(absent)` status, the bulk-draft pass skips it forever unless curator explicitly says *"redraft URI X"*, which resets it to pending.
- **No silent commits.** Every state-changing operation produces a git commit with an auditable message. There is no "background" agent activity.
- **No multi-curator concurrency.** This is a single-curator project; locking and merge conflicts on `saves_state.json` aren't designed for.

---

## Section 9 — Verification

Two layers: **local pre-commit checks** (catch errors before push) and **post-deploy spot checks** (catch errors that only manifest on GitHub Pages). The classic build can't run custom plugins, so most validation lives in a local script — fine since authoring is local anyway.

### `scripts/verify.py` — the local check

A single script that runs all build-time invariants. Curator runs it before committing edits or pushing. Exits non-zero on any failure with a clear message. Target ≤150 lines.

**Checks performed:**

| Check | Failure mode | Why it matters |
|---|---|---|
| **Homepage untouched** | Compares `index.html`, `style.css`, `CNAME`, `favicon.ico`, `media/*` against their git HEAD versions. Fails if any byte differs. | Catches accidental edits to homepage files. |
| **Theme references resolve** | Iterates every `_stories/*.md`; for each `themes:` entry, asserts the slug exists in `_data/themes.yml`. | Catches typos that would render no theme chip and no listing. |
| **Theme stubs exist** | For every theme in `_data/themes.yml`, asserts `stories/themes/<slug>/index.md` and `stories/themes/<slug>/all.md` both exist. | Catches "I added a theme but forgot the stubs" — would 404 the theme URL. |
| **Hero alt required** | Any story with `hero_image:` set must also have non-empty `hero_image_alt:`. | Accessibility + author-discipline. |
| **Inline image alt non-empty** | Greps story bodies for `![](...)` (empty alt) and warns. | Soft warning, not a hard fail. |
| **State consistency** | For every URI in `_data/saves_state.json` with `status` ∈ {`drafted`, `polished`, `published`}, asserts the referenced `story_slug` exists at `_stories/*-<slug>.md`. | Catches state drift if a story file was deleted without updating state. |
| **State / inventory cross-reference** | Every URI in `saves_state.json` must exist in `saves_inventory.json`. (Reverse is not required — pending URIs aren't in state.) | Catches malformed state file. |
| **Frontmatter contract** | Every `_stories/*.md` has all required fields per Section 3. | Catches incomplete drafts. |
| **Slug ↔ filename match** | The `slug:` field in each story's frontmatter must match the slug portion of the filename. | Catches rename bugs that would break permalinks silently. |
| **Body Markdown is Pandoc-clean** | No `<` followed by a tag-shaped token; no `{%` or `{{`. | Maintains book-export readiness. |

A successful run prints `verify: OK (N stories, M themes, P inventory entries)` and exits 0.

### `scripts/build-check.sh` — local Jekyll build

Wraps the Jekyll build with a homepage byte-identity assertion:

```bash
#!/usr/bin/env bash
set -euo pipefail

bundle exec jekyll build

# Verify homepage assets passed through verbatim
diff -q index.html _site/index.html
diff -q style.css _site/style.css
diff -q CNAME _site/CNAME
diff -q favicon.ico _site/favicon.ico
diff -rq media/ _site/media/

echo "build-check: OK"
```

Catches Jekyll touching homepage files — impossible if `exclude:` is right, but worth verifying. Draft-rendering correctness is checked separately via the fixture flow in step 12 below.

### Verification at scaffold time (PR 1)

Before merging the scaffolding PR:

1. `bundle install && bundle exec jekyll serve`
2. `python scripts/verify.py` → exits 0
3. `bash scripts/build-check.sh` → exits 0
4. Browser-visit `localhost:4000/` — should render the existing homepage byte-identical.
5. Browser-visit `localhost:4000/style.css` — same byte-identity check.
6. Browser-visit `localhost:4000/stories/` — empty stories index renders cleanly.
7. Browser-visit `localhost:4000/stories/themes/` — empty themes page renders cleanly.

### Verification with seeded fixtures (still PR 1, optional)

Optional fixture story + fixture theme committed temporarily to verify rendering end-to-end:

8. Add `_stories/2026-01-01-fixture.md` (one story, two themes, one hero image, `published: true`).
9. Add corresponding entries to `_data/themes.yml` and stubs.
10. Re-run `verify.py` and `build-check.sh`.
11. Visit `/stories/`, `/stories/themes/`, `/stories/themes/<slug>/`, `/stories/themes/<slug>/all/`, `/stories/<slug>/`.
12. Set fixture's `published: false`, re-build, confirm it disappears from index/themes/feed/sitemap.
13. Remove the fixture before merging.

### Post-deploy verification (after PR merges)

| Check | How |
|---|---|
| `https://lightseed.net/` shows the existing homepage | Browser. Compare to pre-merge screenshot if uncertain. |
| `https://lightseed.net/style.css` is byte-identical to source | `curl -s https://lightseed.net/style.css \| diff - style.css` |
| `https://lightseed.net/stories/` renders | Browser. |
| `https://lightseed.net/feed.xml` exists (jekyll-feed) | Browser / curl. |
| `https://lightseed.net/sitemap.xml` exists (jekyll-sitemap) | Browser / curl. |
| Pages build status is green for the PR | GitHub UI / Pages settings. |

### Verification cadence post-scaffold

- `scripts/verify.py` runs **before every commit** that touches `_stories/`, `_data/`, or `assets/stories/`. Curator may wire it into a local `pre-commit` git hook.
- `scripts/build-check.sh` runs before any push that includes layout or config changes.
- Post-deploy spot checks happen after merging anything non-trivial.

The big change from the original plan is moving from "verify by manual diff after build" to "verify by `scripts/verify.py` before commit" — invariants are checked early and consistently rather than caught by build failures or rendering errors.

---

## Section 10 — Out of scope, relocation plan, open questions

### Explicitly out of scope (YAGNI)

Things not in this design and not added unless explicitly revisited:

| Deferred | Trigger to revisit |
|---|---|
| Pagination on `/stories/` | When published count exceeds ~75 stories. |
| Site search | When Cmd-F isn't enough. Likely Pagefind (whitelist-incompatible; would require moving to GitHub Pages + Actions — separate project). |
| Related-stories sidebar on a single story | Probably never; the themes index already serves this. |
| Multi-language support | Never planned. |
| Pandoc book export pipeline | Its own project once content is mature. The current design keeps Markdown bodies Pandoc-clean. |
| Automatic image processing (resize, optimize, format convert) | Add `scripts/optimize_images.py` if the manual cap-and-trigger flow becomes painful. |
| Image fingerprinting / cache busting | If browsers stale-cache becomes a recurring complaint. |
| Comments, reactions, social embeds | Out of scope; the project is a reading archive, not a discussion site. |
| Analytics / telemetry | Out of scope. |
| Newsletter delivery / RSS-to-email | RSS feed exists via `jekyll-feed`; piping to email is a third-party concern. |
| Scheduled publishing (auto-flip `published` at a future date) | Manual flip is the intended workflow. |
| Multi-curator concurrency | Single-curator project; conflict resolution on `saves_state.json` not designed for. |
| Private / auth-gated stories | All published content is public. Private staging happens via `published: false`. |
| Automated tests for the fetch script | Manual smoke-test on first run is enough at this scale. |
| `_stories/` cross-linking conventions | If a story should reference another story, just use a normal Markdown link. No special syntax. |

### Relocation plan

Two relocation futures are anticipated: (a) move to a subdomain like `stories.lightseed.net` while staying on GitHub Pages; (b) move off GitHub entirely. The design supports both.

**The move list** is the `[P]`-marked files in Section 1. Specifically:

```
_config.yml          (edit url and permalinks during move)
Gemfile, Gemfile.lock
_layouts/*           (all six layouts)
_includes/stories_*  (three includes)
_data/*              (three data files)
_stories/*           (all stories)
stories/             (index pages, theme stub directories)
assets/stories/      (CSS + per-story image folders)
scripts/             (fetch_saves.py, verify.py, build-check.sh, requirements.txt)
docs/superpowers/specs/2026-04-27-stories-design.md
.gitignore           (Jekyll/Python lines for the new repo)
.env.example         (committed; .env stays per-machine)
CLAUDE.md            (rewrite scope to the new home)
```

**Move steps for `stories.lightseed.net` (subdomain on GitHub Pages):**

1. Create a fresh repo (e.g., `lightseed-stories`).
2. Copy the move list verbatim. Drop the `lightseed.net` homepage files.
3. In `_config.yml`: change `url:` to `https://stories.lightseed.net`; change `permalink: /stories/:slug/` to `permalink: /:slug/`; rename `stories/` directory to root-level URLs (`stories/index.md` → `index.md`, `stories/themes/...` → `themes/...`); update the Jekyll `exclude:` list.
4. Image paths inside `_stories/*.md` (`/assets/stories/<slug>/...`) need a sweep: `/assets/stories/` becomes `/assets/` (or stays the same if you keep the directory structure). One `find` + `sed` pass handles it.
5. DNS: add a `CNAME` file at the new repo root with `stories.lightseed.net`; configure CNAME record at the DNS provider.
6. After verifying the new site, optionally delete the `[P]` files from `tenorune.github.io` to leave only the homepage.

**Move steps off GitHub (Netlify / Cloudflare Pages / self-hosted):**

Same as above through step 4. Then: (5b) push the new repo to the new host; configure build (`bundle exec jekyll build`, publish `_site/`); (6b) DNS + SSL configuration on the new host.

Nothing in the design references the lightseed.net homepage, so cleanup is a single deletion of the move-list files from this repo when the time comes.

### Open questions remaining (none blocking)

| Question | Stance |
|---|---|
| Exact BlueSky bookmark lexicon name at runtime | Probe-and-cache strategy in fetch script handles it; not a design-time decision. |
| OAuth flow specifics if app password fails | Implementation detail, documented in the fetch script's docstring rather than this spec. |
| What to do with the existing `docs/stories-plan.md` after this design lands | Delete it in scaffolding PR 1 with a commit message that points to this new spec path. |
| `Gemfile.lock` committed? | Yes — already in the layout. |
| `.env.example` committed? | Yes — covered in Section 7. |

### What's deliberately *not* deferred (i.e., done at scaffold)

A few things from the original plan's "still open" list are now explicit decisions:

- **`jekyll-feed` and `jekyll-sitemap`**: included at scaffolding (PR 1).
- **Per-theme pages**: included at scaffolding (Section 4 / Section 5).
- **`Gemfile.lock` committed**: yes.
- **State tracking via `saves_state.json`** (replacing `processed_manifest.json`): included.
- **Bulk-draft + cull workflow** (replacing per-story approval): included.

---

## Critical files (post-scaffold)

- `/home/user/tenorune.github.io/_config.yml`
- `/home/user/tenorune.github.io/_layouts/story.html`
- `/home/user/tenorune.github.io/_layouts/theme_list.html`
- `/home/user/tenorune.github.io/_layouts/theme_compilation.html`
- `/home/user/tenorune.github.io/_data/themes.yml`
- `/home/user/tenorune.github.io/_data/saves_state.json`
- `/home/user/tenorune.github.io/scripts/fetch_saves.py`
- `/home/user/tenorune.github.io/scripts/verify.py`

---

## Execution phases

1. **Scaffolding (PR 1)** — `_config.yml` (with explicit `exclude:`), `Gemfile`, `Gemfile.lock`, `.gitignore`, `.env.example`, all six `_layouts/*`, three `_includes/stories_*`, `assets/stories/stories.css`, three empty `_data/*` files, `stories/index.md`, `stories/themes/index.md`, `scripts/verify.py`, `scripts/build-check.sh`, delete `docs/stories-plan.md`. Verify homepage unchanged on fresh build per Section 9.

2. **Ingestion (PR 2)** — `scripts/fetch_saves.py`, `scripts/requirements.txt`. Run once locally; confirm data lands in `_data/saves_inventory.json` and re-run is a no-op.

3. **First stories (PR 3)** — bulk-draft 5–10 saves into `_stories/`, seeding `_data/themes.yml` with real emergent themes. Stage any requested images. All as drafts (`published: false`).

4. **First cull + polish + publish (PR 4)** — curator culls the batch, polishes keepers, flips `published: true` on a small first cohort. Site goes live with real content.

5. **Polish iteration** — iterate on CSS once real content exposes spacing/typography needs.

Branch convention for subsequent curator sessions: `stories/YYYYMMDD-<slug-or-topic>` per PR.


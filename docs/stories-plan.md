# Stories Compilation — Project Plan

> **Status**: planning complete, scaffolding not yet started.
> **Branch for all work**: `claude/bluesky-stories-compilation-milg9`.
> **This document** is the authoritative plan for the project. If a new Claude session is opened, read this file first to load full context.

---

## Context

The user keeps news and other posts on BlueSky via the Saved/Bookmarks feature. These saved posts cluster around recurring themes and deserve a longer-form home than an ephemeral social feed. This project turns that collection into a durable compilation — a curated, thematically organized, chronologically ordered archive.

It will be built and hosted inside the `tenorune.github.io` repo, but has **no relationship or linkage to the current `lightseed.net` homepage**. The homepage stays completely untouched; the stories project is a self-contained, independent piece of work that happens to share the repo as its build host. Over time it may move to `subdomain.lightseed.net` or off GitHub entirely — so the project is organized for easy relocation.

Each story entry contains:
- A one-sentence summary
- A 2–3 paragraph synopsis (drafted by the agent after reading the source article)
- A source citation and link
- Optional images (curator-managed)

A book-form output is a stated second target but is deferred; content is authored as plain Markdown so Pandoc can consume it later.

### User decisions (locked in)
- **Ingestion**: AT Protocol API fetch (script authenticates to BlueSky and pulls saves)
- **Build**: Jekyll (native to GitHub Pages; no build-step complications)
- **Book output**: Deferred; author Markdown in a Pandoc-compatible shape
- **Themes**: Discovered organically from content (no pre-defined list)
- **Relationship to homepage**: None. No nav link, no shared CSS, no aesthetic constraint.
- **Curator workflow**: Conversational through Claude — no CMS, no admin UI. Git is the revision log.

---

## Approach

A minimal Jekyll scaffold added alongside the untouched homepage. The project's files live under predictable paths so a future move to a subdomain or external host is a clean copy. A Python ingestion script (runnable locally and on a scheduled GitHub Action) pulls BlueSky saves into a JSON data file. A manual, agent-assisted authoring loop turns each unprocessed save into a story Markdown file after reading its source. Themes accumulate in `_data/themes.yml` as they emerge. No custom Jekyll plugins initially (stays within the GitHub Pages whitelist); `jekyll-feed` and `jekyll-sitemap` may be added since both are on the whitelist.

### Portability-first file organization

Jekyll has hard conventions for where collections (`_stories/`), layouts, includes, and data files must live (all at repo root), so perfect isolation inside a subfolder isn't possible without a GitHub Actions build step. Instead:

- Every project asset lives under a **recognizable project namespace** so it can be identified and moved as a group.
- All *URL-visible* content lives under `/stories/` while on `lightseed.net`. On a future subdomain, change permalinks to `/` in one config edit.
- The "move list" when relocating is explicit and short (see *Relocation* section).

### Key design choices

| Area | Choice | Why |
|---|---|---|
| Homepage | Not touched. Explicit Jekyll `exclude:` list. | User has stated the two are unrelated. |
| Jekyll theme | None (`theme:` unset) | Avoid Pages default injecting Minima |
| Collection | `_stories`, `output: true` | One URL per story |
| Theme pages | Liquid-filtered page backed by `_data/themes.yml` | No custom plugins needed; emergent themes supported |
| Story URLs | `/stories/:year/:month/:slug/` | Chronological + readable; easy to remap on subdomain |
| Story authoring | Manual, agent-assisted | Synopses are the whole point — never auto-commit |
| Fetch automation | Daily GitHub Action, commits only `_data/bluesky_saves.json` | Keeps raw saves fresh; never touches story files |
| Story body format | Plain Markdown only (no Liquid/HTML in body) | Pandoc-ready for future book export |
| Drafts | `published: false` in frontmatter | Native Jekyll feature; no infra cost |
| Aesthetic | Independent of homepage; project defines its own identity | User clarified no aesthetic inheritance |

---

## File layout

Project-owned files (the "move list") are marked with `[P]`. Everything else is either untouched or shared Jekyll convention.

```
/
├── _config.yml                         [P] Jekyll config (explicit exclude list for homepage)
├── Gemfile                             [P] local dev only
├── _layouts/
│   ├── default.html                    [P] doc shell for project pages
│   ├── story.html                      [P] single story page
│   ├── stories_index.html              [P] chronological list
│   └── themes_index.html               [P] themes grouped view
├── _includes/
│   ├── stories_header.html             [P] header used by project pages
│   ├── stories_footer.html             [P]
│   └── story_card.html                 [P] list item partial
├── _data/
│   ├── themes.yml                      [P] emergent; appended by agent
│   ├── bluesky_saves.json              [P] raw saves (fetched)
│   └── processed_manifest.json         [P] URIs already turned into stories
├── _stories/                           [P] YYYY-MM-DD-slug.md
├── stories/
│   ├── index.md                        [P] -> stories_index layout
│   └── themes/index.md                 [P] -> themes_index layout
├── assets/stories/
│   ├── stories.css                     [P] scoped to project pages only
│   └── <slug>/                         [P] per-story image folder (created on demand)
├── scripts/
│   ├── fetch_bluesky.py                [P] AT Protocol ingestion
│   └── requirements.txt                [P]
├── .github/workflows/
│   └── fetch-bluesky.yml               [P] scheduled fetch
├── docs/
│   └── stories-plan.md                 [P] THIS file
├── CLAUDE.md                           [P] session context pointer for Claude
├── .gitignore                          [P] updated with Jekyll/Python exclusions
├── index.html                          UNCHANGED (in Jekyll exclude:)
├── style.css                           UNCHANGED (in Jekyll exclude:)
├── CNAME, favicon.ico, media/          UNCHANGED (in Jekyll exclude:)
└── LICENSE                             UNCHANGED
```

Naming notes that support portability:
- Includes prefixed `stories_` so they can be moved without colliding if the repo later grows other sections.
- CSS under `assets/stories/` (not generic `assets/css/`) for the same reason.
- Scripts and workflow named `*bluesky*` / `*stories*` — obvious what belongs to the project.

---

## Frontmatter contract (`_stories/*.md`)

```yaml
---
title: "Short human title"
summary: "One-sentence summary."
date: 2026-04-14                      # from bluesky_saved_at date
source_published_at: 2026-04-10       # optional; when the article was published
themes: [climate-grief, infrastructure]
source_url: "https://example.org/article"
source_title: "Original article title"
source_publication: "The New York Times"   # the outlet
source_author: "Jane Doe"                  # byline, optional
bluesky_uri: "at://did:plc:.../app.bsky.feed.post/..."
bluesky_saved_at: 2026-04-12T18:31:00Z
slug: short-slug
hero_image: /assets/stories/short-slug/hero.jpg   # optional
hero_image_alt: "Alt text for hero image"         # required if hero_image set
hero_image_credit: "Photo: Jane Photographer / Reuters"   # optional
published: true                        # omit or false for drafts
---

Synopsis paragraph one...

Synopsis paragraph two...

![Inline image alt text](/assets/stories/short-slug/figure-1.jpg)

Synopsis paragraph three (optional).
```

Rules:
- Body is plain Markdown — no Liquid, no HTML.
- Any theme in `themes:` must exist in `_data/themes.yml`. New themes get appended there in the same commit.
- Filename prefix is ISO date from `bluesky_saved_at`.
- All image references use root-relative paths under `/assets/stories/<slug>/`.
- If an article title contains `{{` or `{%`, wrap the title field value in quotes; body-level braces require `{% raw %}...{% endraw %}` escaping.

`_data/themes.yml` entry shape:
```yaml
- slug: climate-grief
  label: climate grief
  description: one-line emergent description
```

---

## Images — storage and lifecycle

- **Storage**: one folder per story at `assets/stories/<slug>/`. Files inside: `hero.jpg` (optional featured image), plus any inline images used in the synopsis body.
- **Formats**: jpg, png, webp preferred. Avoid GIFs > 2MB. Avoid raw/tiff.
- **Size**: soft cap at 500KB per image; if a source image is larger, curator requests a resize during conversational authoring.
- **Alt text**: required for any image that renders on the page (both hero and inline).
- **Credit**: optional but encouraged for hero images.
- **Adding/removing images**: conversational — "add this image to story X" → I place the file under `assets/stories/<slug>/` and update the Markdown reference or `hero_image` frontmatter in one commit. "Remove the second image from story X" → I delete the file and strip the reference in one commit.
- **Provenance**: the fetch script does NOT automatically download BlueSky embedded media. The curator pastes image paths or URLs during authoring, and I stage them.

---

## Curator editing workflow (conversational)

All editing is agent-mediated in chat. No CMS, no admin UI. Git history is the revision log.

**Supported operations** (curator phrases → what I do):
- "Tighten paragraph 2 of story X" → I edit the body, show diff, commit on approval.
- "Regenerate the synopsis in a more somber tone" → I re-read `source_url` via WebFetch, draft fresh text, show for approval, commit.
- "Swap the summary sentence for story X" → single-line edit, commit.
- "Add theme Y to story X" → check `themes.yml`, append if new, edit frontmatter, commit.
- "Unpublish story X" → add `published: false` to frontmatter, commit.
- "Delete story X" → remove file and its image folder, optionally remove from `processed_manifest.json`, commit.

**Rollback**: `git revert <sha>` on the commit that made the change. No custom revisions folder.

---

## BlueSky ingestion script

**`scripts/fetch_bluesky.py`** (Python 3.12, direct XRPC calls, no SDK)
- Auth: env `STORIES_BSKY_HANDLE` + `STORIES_BSKY_APP_PASSWORD` → `com.atproto.server.createSession`.
- Preferred endpoint: `app.bsky.bookmark.getBookmarks` (native bookmarks).
- Fallback order if unavailable: `app.bsky.feed.getActorLikes` (tagged `source: "likes"` in the record), then documented manual JSON export on the same schema.
- For each record, resolves the embedded `app.bsky.embed.external` facet to pre-fill `source_url`, `source_title`, `source_author` when possible.
- Idempotent: keys by `bluesky_uri`, never overwrites existing entries, re-sorts by `saved_at` desc.
- Writes only `_data/bluesky_saves.json`. Never mutates `_stories/`, `themes.yml`, or `processed_manifest.json`.

**`scripts/requirements.txt`**: `httpx>=0.27`, `python-dateutil>=2.9`.

---

## Agent-driven authoring workflow (per session, manual)

1. Read `_data/bluesky_saves.json`, filter out URIs already in `_data/processed_manifest.json`.
2. Pick N oldest unprocessed (user says how many).
3. For each: `WebFetch` `source_url`, read the article.
4. Draft title + one-sentence summary + 2–3 paragraph synopsis.
5. Consult `_data/themes.yml`; reuse an existing theme or append a new one with a one-line description.
6. Write `_stories/<saved_at-date>-<slug>.md` following the frontmatter contract.
7. Append the `bluesky_uri` to `processed_manifest.json`.
8. Report drafts to the user before committing.

---

## Automation (`.github/workflows/fetch-bluesky.yml`)

- Trigger: `schedule: cron '17 7 * * *'` (off the top-of-hour to avoid runner contention) + `workflow_dispatch`.
- Steps: checkout → setup-python 3.12 → `pip install -r scripts/requirements.txt` → run fetch script with secrets `STORIES_BSKY_HANDLE`, `STORIES_BSKY_APP_PASSWORD` → if `_data/bluesky_saves.json` changed, commit `chore(stories): refresh bluesky saves` and push.
- `contents: write` via default `GITHUB_TOKEN`. Direct commit (no PR — this is data, not code).
- Must not touch `_stories/`, `_data/themes.yml`, or `_data/processed_manifest.json`.
- Rebuilds of the Pages site on each data commit are **expected and acceptable** — the data file is a real input to the rendered site.

---

## Aesthetic

The project defines its own visual identity — no inheritance from the homepage. Starting defaults (tunable once real content exists):
- Readable content width (~38rem), generous line-height.
- Serif body / sans meta — typical long-form-reading typography.
- Theme "chips" as unobtrusive text links.
- No JavaScript, no analytics (default; user can add if desired).
- CSS lives at `assets/stories/stories.css`; the homepage never loads it.

---

## Relocation plan (for later, when moving to a subdomain or off GitHub)

1. Copy everything marked `[P]` in the *File layout* section to the new location.
2. In `_config.yml`, change `url:` and permalinks. If moving to `stories.lightseed.net`, change story permalinks from `/stories/:year/:month/:slug/` to `/:year/:month/:slug/`.
3. Update any root-relative image paths inside `_stories/*.md` if the mount changes.
4. Set up DNS CNAME for the subdomain and a new GitHub Pages site OR configure the external host.
5. Delete the `[P]` files from `tenorune.github.io` once the move is verified.

Nothing in the project references the homepage, so there is no cleanup beyond file removal.

---

## Execution phases

1. **Scaffolding (PR 1)** — `_config.yml` (with explicit `exclude:`), `Gemfile`, `.gitignore`, all `_layouts/*`, `_includes/stories_*`, `assets/stories/stories.css`, empty `_data/*` files, `stories/index.md`, `stories/themes/index.md`. Verify homepage unchanged on fresh build.
2. **Ingestion (PR 2)** — `scripts/fetch_bluesky.py`, `scripts/requirements.txt`, `.github/workflows/fetch-bluesky.yml`. Configure repo secrets. Run once manually; confirm data lands and re-run is a no-op.
3. **First stories (PR 3)** — agent drafts 3–5 stories from populated saves, seeds `_data/themes.yml` with real themes, stages any requested images.
4. **Polish** — iterate on CSS once real content exposes spacing/typography needs. Consider adding `jekyll-feed` for RSS once the archive is non-empty.

Development branch for scaffolding: `claude/bluesky-stories-compilation-milg9`.
Branch convention for subsequent curator sessions: `stories/YYYYMMDD-<slug-or-topic>` per PR.

---

## Critical files (post-scaffold)
- `/home/user/tenorune.github.io/_config.yml`
- `/home/user/tenorune.github.io/_layouts/story.html`
- `/home/user/tenorune.github.io/_layouts/themes_index.html`
- `/home/user/tenorune.github.io/_data/themes.yml`
- `/home/user/tenorune.github.io/scripts/fetch_bluesky.py`
- `/home/user/tenorune.github.io/.github/workflows/fetch-bluesky.yml`

---

## Risks / unknowns

1. **BlueSky bookmark lexicon name** may differ from `app.bsky.bookmark.getBookmarks`. Script probes and degrades to likes; manual export on same schema is the final fallback.
2. **App password scope** for bookmarks unverified — if app passwords can't read them, document the trade-off and consider a session-token strategy.
3. **Body/Liquid collisions**: article titles containing `{{` break Jekyll. Guideline in `story.html` comment: wrap body braces in `{% raw %}...{% endraw %}` if needed.
4. **Jekyll activating for the whole repo**: adding `_config.yml` activates Jekyll sitewide. Mitigation is an explicit `exclude:` list in the config listing `index.html`, `style.css`, `CNAME`, `favicon.ico`, `media/`, `LICENSE`, `CLAUDE.md`, `docs/`. Verify on first build that the homepage is truly untouched.

---

## Verification

**Local**
1. `bundle install && bundle exec jekyll serve`.
2. `curl -s localhost:4000/ | diff - index.html` → byte-identical (or verify via the `exclude:` list that Jekyll copied it verbatim).
3. `curl -s localhost:4000/style.css | diff - style.css` → byte-identical.
4. Seed one theme in `_data/themes.yml` + one fixture story. Visit `/stories/`, `/stories/themes/`, and the story permalink. Confirm layout, summary, theme chip, source citation.
5. Author a second story with two themes and a hero image; confirm it appears under both themes on the themes page and image renders.
6. Run `python scripts/fetch_bluesky.py` with a real app password; confirm JSON populates and re-run is a no-op.
7. Mark one story `published: false`; confirm it disappears from `/stories/` and its permalink 404s.

**Remote**
8. Push branch `claude/bluesky-stories-compilation-milg9`, open PR, confirm GitHub Pages preview build succeeds.
9. Post-merge: `https://lightseed.net/` shows seeds.gif unchanged; `https://lightseed.net/stories/` renders independently.
10. `workflow_dispatch` the fetch workflow; confirm it only commits when saves changed.

---

## Session log — what's been decided vs. still open

### Decided in planning sessions so far
- All items listed in *User decisions (locked in)* above.
- Image storage convention: `assets/stories/<slug>/`.
- Hero image frontmatter: `hero_image`, `hero_image_alt`, `hero_image_credit`.
- Source citation split: `source_publication` + `source_author`.
- Drafts via `published: false`.
- Secret naming: `STORIES_BSKY_*` prefix.
- Cron minute: `17 * * *` to avoid contention.
- Explicit Jekyll `exclude:` for homepage protection (replaces earlier "byte-identical diff" approach as primary mitigation — the diff is still used as a verification check).
- Conversational curator workflow for all edits, regeneration, image management; git history is the revision log.

### Still open (decide at scaffolding time or later)
- Whether to add `jekyll-feed` at scaffolding time or wait until first stories exist.
- Whether to generate per-theme pages (`/stories/themes/<slug>/`) at scaffolding or defer.
- Whether to commit `Gemfile.lock` (leaning yes for dev reproducibility).
- Whether the daily data commit should use `[skip ci]` — probably no, since data changes genuinely affect the site.
- Where/whether to document theme descriptions publicly on the themes page.

### Deferred
- Pagination strategy for `/stories/` (revisit at ~50 stories).
- Related-stories sidebar on single-story page.
- Multi-language support.
- Automated tests for the fetch script.
- Book (Pandoc) export pipeline.

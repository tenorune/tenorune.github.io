# Claude session context

This repo hosts two unrelated things that share a GitHub Pages build:

1. **`lightseed.net` homepage** — static, hand-authored. Lives at the repo root: `index.html`, `style.css`, `CNAME`, `favicon.ico`, `media/`. **Do not modify any of these** unless the user explicitly asks about the homepage.

2. **Stories compilation** (PR 1 scaffolded, awaiting ingestion) — a Jekyll-based long-form archive of BlueSky saves. Authoritative spec: [`docs/superpowers/specs/2026-04-27-stories-design.md`](docs/superpowers/specs/2026-04-27-stories-design.md). **Read that file first** before starting any stories-related work.

## Active development branch
- `claude/review-bluesky-stories-plan-ItxMr` for the current scaffolding work.
- Subsequent curator sessions (authoring stories, editing, adding images): `stories/YYYYMMDD-<slug-or-topic>` per PR.

## Key rules
- The two projects are **isolated**: no shared CSS, no nav link, no front-matter changes to the homepage.
- Jekyll passes through the homepage automatically because the homepage files have no YAML front matter; they are NOT in `_config.yml` `exclude:` (putting them there would delete them from `_site/`). The cohabitation guarantee is verified by `scripts/verify.py` (homepage byte-identity vs. git HEAD) and `scripts/build-check.sh` (homepage diff after build).
- Story authoring is **hybrid**: Claude bulk-drafts stories as `published: false`, the curator culls and polishes, Claude does ad-hoc revisions on request. See the spec's authoring workflow section.
- Git history is the revision log for stories. Use `git revert` to roll back an edit.
- Frontmatter contract, file layout, and image storage conventions are in the spec — follow exactly.

## What's been scaffolded vs. still pending

Scaffolding complete (PR 1):
- `_config.yml` with `stories` collection (`render_with_liquid: false`), `jekyll-feed`, `jekyll-sitemap`.
- Six layouts: `default`, `story`, `stories_index`, `themes_index`, `theme_list`, `theme_compilation`.
- Three includes: `stories_header`, `stories_footer`, `story_card`.
- Three empty `_data/` files: `saves_inventory.json`, `saves_state.json`, `themes.yml`.
- `_stories/` collection (empty), `stories/index.md`, `stories/themes/index.md`.
- `assets/stories/stories.css` (long-form serif aesthetic, system-font stack).
- `scripts/verify.py` (10 invariant checks, 21 passing pytest tests in `tests/test_verify.py`).
- `scripts/build-check.sh` (jekyll build + homepage byte-identity assertion).
- `Gemfile`, `Gemfile.lock`, `.env.example`, `.gitignore`.
- Verified: homepage byte-identical pre/post build; `/stories/`, `/stories/themes/`, `/feed.xml`, `/sitemap.xml` all render.

Still pending:
- **PR 2: Ingestion script.** `scripts/fetch_saves.py` (AT Protocol via XRPC). Requires curator's `.env` populated with `BSKY_HANDLE` and `BSKY_APP_PASSWORD`. App passwords likely cannot read bookmarks; the script will fall back to OAuth/session flow on 401/403.
- **PR 3: First bulk-draft.** Once inventory has data, Claude bulk-drafts stories from real saves, seeding `_data/themes.yml` with emergent themes.
- **PR 4: First cull + polish + publish.** Curator decides what to keep, polishes prose, flips `published: true`.
- **PR 5: CSS iteration** once real content exposes spacing/typography needs.

## First-time local setup (curator)

```bash
# Ruby gems
bundle install

# Python tooling for verify.py
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt

# Local credentials (for PR 2 fetch script)
cp .env.example .env
# edit .env, fill in BSKY_HANDLE and BSKY_APP_PASSWORD
```

Then:
```bash
# Verify invariants
python scripts/verify.py

# Build with homepage byte-identity check
bash scripts/build-check.sh

# Local preview
bundle exec jekyll serve
```

## Things to read before acting on this project
1. This file.
2. `docs/superpowers/specs/2026-04-27-stories-design.md` — full design spec (with errata noted in Section 1 / Section 9).
3. `docs/superpowers/plans/2026-04-27-stories-pr1-scaffolding.md` — PR 1 plan (now executed).
4. The existing homepage (`index.html`, `style.css`, `media/`) to confirm it is untouched.

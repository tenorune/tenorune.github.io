# Claude session context

This repo hosts two unrelated things that share a GitHub Pages build:

1. **`lightseed.net` homepage** — static, hand-authored. Lives at the repo root: `index.html`, `style.css`, `CNAME`, `favicon.ico`, `media/`. **Do not modify any of these** unless the user explicitly asks about the homepage.

2. **Stories compilation** (PR 1 scaffolded, awaiting ingestion) — a Jekyll-based long-form archive of BlueSky saves. Authoritative spec: [`docs/superpowers/specs/2026-04-27-stories-design.md`](docs/superpowers/specs/2026-04-27-stories-design.md). **Read that file first** before starting any stories-related work.

## Operating model

The curator does not run dev or build commands locally. Everything happens through one of two channels:

- **This chat session** (Claude on Web). All authoring, editing, image management, and one-off commands run by Claude (e.g., resolving a BlueSky URL, drafting a story, committing a change).
- **GitHub Actions**. CI runs verify checks + Jekyll build on every push and PR (`.github/workflows/verify.yml`). PR 2's ingestion will also run in a GitHub Action.

The curator only needs a browser. No `bundle install`, no `pip install`, no local Ruby or Python.

## Active development branch
- `claude/review-bluesky-stories-plan-ItxMr` for the current scaffolding work.
- Subsequent curator sessions (authoring stories, editing, adding images): `stories/YYYYMMDD-<slug-or-topic>` per PR.

## Key rules
- The two projects are **isolated**: no shared CSS, no nav link, no front-matter changes to the homepage.
- Jekyll passes through the homepage automatically because the homepage files have no YAML front matter; they are NOT in `_config.yml` `exclude:` (putting them there would delete them from `_site/`). The cohabitation guarantee is enforced by the `verify` workflow on every push.
- Story authoring is **hybrid**: Claude bulk-drafts stories as `published: false`, the curator culls and polishes (in chat — Claude makes the edits), Claude does ad-hoc revisions on request.
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
- `scripts/build-check.sh` (jekyll build + homepage byte-identity assertion; mainly useful when Claude runs it in-chat before pushing).
- `.github/workflows/verify.yml` — CI workflow that runs all of the above on every push and PR.
- `Gemfile`, `Gemfile.lock`, `.env.example`, `.gitignore`.

### Ingestion (status: pivoted to manual paste; automated paths preserved as dormant)

The plan tried two automated paths against BlueSky's bookmark API — both hit walls for accounts on third-party PDSes (the curator's account is on `eurosky.social`):

1. **App-password + service auth** (in `scripts/fetch_saves.py`). Works for `bsky.social`-hosted accounts; fails for third-party PDSes because the AppView at `bsky.social` won't verify session JWTs from foreign servers.
2. **OAuth + DPoP** (in `scripts/oauth_init.py`, `scripts/atproto_dpop.py`, the `oauth init`/`oauth complete` workflows). The auth flow itself works; the resulting access token is rejected by `bsky.social`'s AppView with the explicit message `"OAuth tokens are meant for PDS access only"`. This is BlueSky policy, not a fix-able bug.

See spec Section 7's "Errata round 2" for the full debugging story.

**Status of the automated infrastructure:**
- `scripts/fetch_saves.py`, `scripts/oauth_init.py`, `scripts/atproto_dpop.py`, `oauth/*` and the three workflows (`fetch.yml`, `oauth-init.yml`, `oauth-complete.yml`) are all **preserved in the repo but dormant**.
- `fetch.yml` cron has been disabled; the workflow is `workflow_dispatch`-only.
- All `BSKY_*` secrets and the `BSKY_PDS` Variable can be deleted; nothing in active CI uses them.
- If the curator ever adds a `bsky.social`-hosted secondary account, the app-password path is ready to use.

**Active ingestion path:**

- **Save inventory:** `fetch saves` workflow (manual or scheduled) pulls bookmarks via the AT Protocol bookmark endpoint into `_data/saves_inventory.json`. The PDS-direct path (`pds:app.bsky.bookmark.getBookmarks`) succeeds for the curator's third-party-PDS account. Currently 675 saves committed.
- **Article hydration:** `fetch articles` workflow (manual) iterates inventory entries with external article links, downloads each article via trafilatura, and writes `article_text` back into the entry. Idempotent. Lets bulk-drafting in chat read article content directly from inventory.
- **Thread hydration:** `fetch threads` workflow (manual) walks each save's thread via the public AppView and stores same-author descendant posts (with their images) as `thread_replies` on the entry. Idempotent and schema-versioned: schema bumps trigger re-fetch on next run.
- **Image localization:** `fetch images` workflow (manual) scans `_stories/*.md` for inline image references pointing at `cdn.bsky.app`, downloads each into `assets/stories/<slug>/` using a deterministic hash-named filename, and rewrites the story body to use the local root-relative path. Idempotent. Run after a draft batch to make image references durable against CDN drift.
- **Bulk drafting:** Claude reads inventory + article_text in chat, drafts batches of stories as `published: false`, commits with theme stubs and saves_state updates. Curator culls and polishes later.
- **Ongoing incremental adds:** the curator can also paste a BlueSky URL or AT-URI directly into chat for one-off additions when needed.
- **PR 3: First bulk-draft.** Once inventory has data (from the bulk import), Claude bulk-drafts stories from real saves, seeding `_data/themes.yml` with emergent themes.
- **PR 4: First cull + polish + publish.** Curator decides what to keep (in chat); Claude flips `published: true`.
- **PR 5: CSS iteration** once real content exposes spacing/typography needs.

## How verification works (no local commands)

The `verify` GitHub Actions workflow runs on every push and PR. It:

1. Installs Ruby + Python deps.
2. Runs `pytest tests/` — 21 unit tests for `verify.py`'s checks.
3. Runs `python scripts/verify.py` — 10 invariants on the actual repo.
4. Runs `bundle exec jekyll build`.
5. Verifies the built site's homepage is byte-identical to the source.

If any step fails, the workflow goes red and the PR cannot merge cleanly. The curator never has to run anything to know if a change is broken — GitHub tells them.

## Things to read before acting on this project
1. This file.
2. `docs/superpowers/specs/2026-04-27-stories-design.md` — full design spec (with errata noted in Section 1 / Section 9).
3. `docs/superpowers/plans/2026-04-27-stories-pr1-scaffolding.md` — PR 1 plan (now executed).
4. The existing homepage (`index.html`, `style.css`, `media/`) to confirm it is untouched.

# Claude session context

This repo hosts two unrelated things that share a GitHub Pages build:

1. **`lightseed.net` homepage** — static, hand-authored. Lives at the repo root: `index.html`, `style.css`, `CNAME`, `favicon.ico`, `media/`. **Do not modify any of these** unless the user explicitly asks about the homepage.

2. **Stories compilation** — a Jekyll-based long-form archive of BlueSky saves. ~63 stories drafted, ~43 published; 675 saves in inventory; curator dashboards live at `/stories/curator/` and `/stories/curator/pending/`. Authoritative spec: [`docs/superpowers/specs/2026-04-27-stories-design.md`](docs/superpowers/specs/2026-04-27-stories-design.md). **Read that file first** before starting any stories-related work.

## Operating model

The curator does not run dev or build commands locally. Everything happens through one of two channels:

- **This chat session** (Claude on Web). All authoring, editing, image management, and one-off commands run by Claude (e.g., resolving a BlueSky URL, drafting a story, committing a change).
- **GitHub Actions**. CI runs verify checks + Jekyll build on every push and PR (`.github/workflows/verify.yml`). PR 2's ingestion will also run in a GitHub Action.

The curator only needs a browser. No `bundle install`, no `pip install`, no local Ruby or Python.

## Active development branch
- **Trunk-only: commits go directly to `main`.** The earlier scaffolding branch (`claude/review-bluesky-stories-plan-ItxMr`) and the older planning branch (`claude/bluesky-stories-compilation-milg9`) have been deleted; main is the only active branch. The deferred-drain curator workflow handles concurrent-write races so direct-to-main is safe in practice.

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

### Ingestion (status: automated via the published `bsky-saves` PyPI package)

The four ingestion workflows (`fetch.yml`, `fetch-articles.yml`, `fetch-threads.yml`, `fetch-images.yml`) install [`bsky-saves`](https://pypi.org/project/bsky-saves/) from PyPI and call its CLI. The package is maintained in a separate repo ([`tenorune/bsky-saves`](https://github.com/tenorune/bsky-saves)) and was extracted from this repo's `scripts/` on 2026-04-30 (see `docs/extraction-draft/README.md` for the cutover procedure and full extraction map).

The active path uses **app-password + PDS-direct bookmark fetch**, which works for accounts on third-party PDSes (the curator is on `eurosky.social`) because the call goes to the PDS that issued the session JWT, not to bsky.social's AppView. AppView-targeted endpoints are still in the package as fallbacks for bsky.social-hosted accounts.

The OAuth + DPoP scaffolding that used to live in this repo (`scripts/oauth_init.py`, `scripts/atproto_dpop.py`, `oauth/*`, the `oauth-init`/`oauth-complete` workflows) was extracted into [`atproto-oauth-py`](https://pypi.org/project/atproto-oauth-py/) ([`tenorune/atproto-oauth-py`](https://github.com/tenorune/atproto-oauth-py)). It's not in active use here — BlueSky's AppView rejects OAuth tokens from third-party PDSes with `"OAuth tokens are meant for PDS access only"` — but it's preserved as a published library if the use case ever changes.

See spec Section 7's "Errata round 2" for the full debugging story.

**Required secrets / variables for the active path** (curator's `eurosky.social` account):
- Secrets: `BSKY_HANDLE`, `BSKY_APP_PASSWORD` — used by `createSession` against the curator's PDS to mint a session JWT.
- Variable: `BSKY_PDS=https://eurosky.social` — without this, the script defaults to `https://bsky.social` and both `createSession` and the PDS-direct bookmark call go to the wrong server.

If the curator ever adds a `bsky.social`-hosted secondary account, leave `BSKY_PDS` unset (or set it to `https://bsky.social`) and the AppView-targeted endpoints take over.

**Active ingestion path:**

- **One-button refresh:** the `refresh saves + hydrate + rebuild` workflow runs `bsky-saves fetch`, `bsky-saves hydrate articles`, `bsky-saves hydrate threads`, `bsky-saves enrich`, then `build_curator_data.py` + `build_pending_data.py`, and commits the result as a single commit. This is the default routine ingestion run; use it whenever the curator is doing a normal "what's new since last time" pull.
- **Save inventory:** `fetch saves` workflow runs `bsky-saves fetch --inventory _data/saves_inventory.json`. Currently 675 saves committed. Run this standalone only when you want a quick inventory-only pull without waiting for hydration.
- **Article hydration:** `fetch articles` workflow runs `bsky-saves hydrate articles --inventory _data/saves_inventory.json`. Iterates entries with external article links, downloads each via trafilatura, writes `article_text` back. Idempotent. Standalone form is mainly useful with `--refresh-dates` (exposed as a workflow input) to re-extract `article_published_at` after a metadata change.
- **Thread hydration:** `fetch threads` workflow runs `bsky-saves hydrate threads --inventory _data/saves_inventory.json`. Walks each save's thread via the public AppView and stores same-author descendant posts (with their images) as `thread_replies`. Idempotent and schema-versioned: schema bumps in the `bsky-saves` package trigger re-fetch on the next run, which is when standalone form is most useful.
- **Enrichment:** `enrich inventory` workflow runs `bsky-saves enrich --inventory _data/saves_inventory.json`. Offline post-processing — TID-decodes `post_created_at` for any save missing it and drops bogus `article_published_at` values that fall within ±1 day of `article_fetched_at` (a common trafilatura fallback on metadata-poor hosts like YouTube). Idempotent. The `refresh` orchestrator already runs this; the standalone is for re-enriching after a heuristic bump in the `bsky-saves` package, with the optional `refresh` input forcing re-decode of `post_created_at` across all entries.
- **Image localization:** `fetch images` workflow runs `bsky-saves hydrate images --stories _stories --assets assets/stories --assets-url-prefix /assets/stories`. Scans `_stories/*.md` for inline `cdn.bsky.app` image refs, downloads each into `assets/stories/<slug>/` with a deterministic hash filename, rewrites refs to local paths. Idempotent. Operates on stories, not the inventory, so it's deliberately *not* part of the `refresh` orchestrator — run it after a draft batch.
- **Bulk drafting:** Claude reads inventory + article_text in chat, drafts batches of stories as `published: false`, commits with theme stubs and saves_state updates. Curator culls and polishes later.
- **Curator dashboards:** `/stories/curator/` (drafted stories) and `/stories/curator/pending/` (theme-aligned saves not yet drafted). Each row carries action buttons that open pre-filled GitHub issues (`curator: <action> <slug-or-rkey>`).
- **Curator queue (deferred drain):** the `curate` workflow now *appends* each submitted action to `_data/curator_queue.yml` and acknowledges the issue, leaving it open. Nothing is mutated until you trigger a drain — either via the `drain curator queue` workflow on the Actions tab, or by asking Claude in chat. The drain applies every queued action in order, regenerates `_data/curator.yml` and `_data/pending.yml`, clears the queue, and closes processed issues — all in a single commit. This avoids the 1-commit-per-curator-click noise and the push-race fragility of immediate processing.
- **Ongoing incremental adds:** the curator can also paste a BlueSky URL or AT-URI directly into chat for one-off additions when needed.

## Status (as of 2026-04-30)

- **Inventory:** 675 saves; ~210 with external article URLs; ~166 with hydrated article text; ~362 with self-thread context; quote-post embeds also captured (via `quoted_post` field) with their own thread context.
- **Stories:** 63 total — ~43 published, ~19 drafted, 1 culled (per `_data/saves_state.json`).
- **Themes:** 8, with story counts ranging from 10 (predatory-capital) to 21 (civilian-harm).
- **Saves_state:** ~29 skipped, ~3 queued (curator-flagged for next bulk-draft), the rest pending.
- **Dates captured:** every save has `post_created_at` (TID-decoded); 164 have `article_published_at` (trafilatura metadata). Curator pages flag rows where post-vs-publication gap exceeds 7 days, suppressing noisy hosts.
- **CSS:** has been incrementally tuned alongside content; no discrete CSS-iteration pass scheduled — minor adjustments happen on demand.

## How verification works (no local commands)

The `verify` GitHub Actions workflow runs on every push to main. It:

1. Installs Ruby + Python deps.
2. Runs `pytest tests/` — unit tests for `verify.py` (the bookmark-schema tests now live in the `bsky-saves` repo).
3. Runs `python scripts/verify.py` — invariant checks on the actual repo (frontmatter contract, theme references, homepage byte-identity, article-pending flag, etc.).
4. Runs `bundle exec jekyll build`.
5. Verifies the built site's homepage is byte-identical to the source.

If any step fails, the workflow goes red on `main` itself. Since we're trunk-only, breakage is visible immediately rather than blocked at merge — the convention is to push fixes promptly rather than rely on a merge gate.

## Things to read before acting on this project
1. This file.
2. `docs/superpowers/specs/2026-04-27-stories-design.md` — full design spec (with errata noted in Section 1 / Section 9).
3. `docs/superpowers/plans/2026-04-27-stories-pr1-scaffolding.md` — PR 1 plan (now executed).
4. The existing homepage (`index.html`, `style.css`, `media/`) to confirm it is untouched.

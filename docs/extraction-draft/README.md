# Extraction drafts

Scratch directory for the two packages being extracted from this repo:

- **`bsky-saves/`** — BlueSky bookmarks toolkit (PyPI: `bsky-saves`).
- **`atproto-oauth-py/`** — AT Protocol OAuth 2.1 + DPoP library and CLI
  (PyPI: `atproto-oauth-py`).

Nothing in this directory is shipped or imported by the Stories of 47 site.
This is a review surface for the curator. Once approved, each subtree gets
copied into its respective fresh GitHub repo and tagged `v0.1.0` to trigger
its release workflow.

## How to use these drafts

For each package (`bsky-saves`, then `atproto-oauth-py`):

1. Open a new Claude Code on Web session pointed at the empty target repo
   (`tenorune/bsky-saves` or `tenorune/atproto-oauth-py`).
2. Hand Claude the corresponding subtree from this directory. Two ways:
   - Tar it up and paste, or
   - Walk Claude through the file list and paste each file's contents.
3. Commit + push to `main`. CI (`verify.yml`) runs; PyPI is untouched.
4. Once `main` is green, push the release tag:

   ```
   git tag v0.1.0
   git push origin v0.1.0
   ```

5. Watch the Actions tab. `release.yml` runs in the `pypi` environment, the
   OIDC handshake authenticates to PyPI, and the package goes live.
6. Verify with `pip install bsky-saves` (or `pip install atproto-oauth-py`).

## Pre-conditions you've already done

- Both repos exist on GitHub (empty).
- A `pypi` GitHub Environment is configured in each repo's settings.
- A pending publisher is configured on PyPI for each project, pointing at the
  matching repo + workflow filename `release.yml` + environment `pypi`.

## Pre-conditions still to do (one-time)

- In each repo's *Settings → Environments → pypi → Deployment branches and
  tags*, restrict to tag pattern `v*`. (Optional but recommended; the workflow
  itself already filters on `v*`, so this is belt-and-suspenders.)
- Add a `LICENSE` file. Drafts include MIT placeholders — change if you want
  Apache 2.0 or similar.

## Extraction map

| New package | Source files in this repo |
|---|---|
| `bsky-saves` | `scripts/_tid.py`, `scripts/fetch_saves.py` (app-password path; OAuth path stripped — see below), `scripts/fetch_articles.py`, `scripts/fetch_threads.py`, `scripts/fetch_images.py`, `scripts/enrich_inventory.py`, the four fetch workflows, parts of `tests/test_fetch_saves.py` |
| `atproto-oauth-py` | `scripts/atproto_dpop.py`, `scripts/oauth_init.py`, `oauth/client-metadata.json`, `oauth/callback/index.html`, `.github/workflows/oauth-init.yml`, `.github/workflows/oauth-complete.yml` |

The OAuth runtime path that's currently entangled in `fetch_saves.py`
(`oauth_main()` and `discover_token_endpoint`) is dropped from `bsky-saves`
v0.1.0. Rationale:

- The active path (and the only one that actually works for the curator's
  third-party PDS) is the PDS-direct app-password path. The OAuth fallback
  was never reachable in production because BlueSky's AppView rejects OAuth
  tokens (see `CLAUDE.md` Section "Ingestion").
- The OAuth machinery is preserved, untouched, in `atproto-oauth-py` for any
  user who wants to implement an OAuth-authenticated AppView client.
- If a future need surfaces, `bsky-saves` v0.2 can declare
  `atproto-oauth-py` as an optional dependency and re-add the OAuth path
  behind a `--oauth` flag.

## Phase C — cutting Stories of 47 over

After both packages publish, this repo gets its turn:

1. Add `bsky-saves` to `scripts/requirements.txt`.
2. Replace `python scripts/fetch_saves.py` etc. in the four `fetch-*.yml`
   workflows with `bsky-saves fetch ...` etc.
3. Delete the now-duplicated scripts:
   `scripts/_tid.py`, `scripts/fetch_saves.py`, `scripts/fetch_articles.py`,
   `scripts/fetch_threads.py`, `scripts/fetch_images.py`,
   `scripts/enrich_inventory.py`, `scripts/atproto_dpop.py`,
   `scripts/oauth_init.py`, `oauth/`, `.github/workflows/oauth-*.yml`.
4. Move the bookmark-schema tests to the `bsky-saves` repo (already in the
   draft); leave the stories-specific tests
   (`tests/test_verify.py`) here.
5. Push, watch verify go green.

That's a separate session's work — don't start it until both packages are
live on PyPI.

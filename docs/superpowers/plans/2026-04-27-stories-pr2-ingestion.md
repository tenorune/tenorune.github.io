# Stories Compilation PR 2 — Ingestion Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate BlueSky save ingestion via a scheduled GitHub Action. Authenticate with the curator's app password, fetch bookmarks via the AT Protocol, append new entries to `_data/saves_inventory.json`, commit if changed.

**Architecture:** Python script (`scripts/fetch_saves.py`) wrapped by a GitHub Actions workflow (`.github/workflows/fetch.yml`). Secrets stored in repo Settings → Secrets and variables → Actions. Auto-commits via `GITHUB_TOKEN`. The script probes multiple bookmark-related endpoints in fallback order; if all fail (likely if app passwords lack bookmark scope), it exits non-zero with a clear diagnostic and the workflow goes red — the curator then decides the next move (Option D: OAuth-via-chat, or Option B: manual paste).

**Tech Stack:** Python 3.12, `httpx`, `python-dateutil`. No Anthropic SDK or other heavy deps.

**Spec source of truth:** `docs/superpowers/specs/2026-04-27-stories-design.md` (Section 7). This plan re-introduces the GitHub Action approach that the spec moved away from; Section 7 will be updated in Task 5 of this plan to reflect the pivot.

**Branch:** `claude/review-bluesky-stories-plan-ItxMr` (same branch as PR 1 — the user can split into separate PRs at merge time if desired).

---

## File map

| Path | Action | Responsibility |
|---|---|---|
| `scripts/fetch_saves.py` | create | Authenticate, probe bookmark endpoints, fetch & merge inventory |
| `scripts/requirements.txt` | modify | Uncomment fetch deps (`httpx`, `python-dateutil`) |
| `tests/test_fetch_saves.py` | create | Unit tests with mocked HTTP responses |
| `.github/workflows/fetch.yml` | create | Daily scheduled fetch + commit |
| `docs/superpowers/specs/2026-04-27-stories-design.md` | modify | Section 7 errata documenting the pivot |
| `CLAUDE.md` | modify | Reflect that ingestion is now a scheduled Action |

---

## Task 1 — Update `scripts/requirements.txt`

- [ ] **Step 1.1:** Uncomment fetch-related lines.

```
# Used by scripts/verify.py
PyYAML>=6.0
pytest>=8.0

# Used by scripts/fetch_saves.py
httpx>=0.27
python-dateutil>=2.9
respx>=0.21       # HTTP mocking for tests
```

- [ ] **Step 1.2:** Install in venv (Claude does this in chat; user does nothing).

```bash
.venv/bin/pip install -r scripts/requirements.txt
```

- [ ] **Step 1.3:** Commit.

---

## Task 2 — Write `tests/test_fetch_saves.py` (TDD red bar)

**Files:**
- Create: `tests/test_fetch_saves.py`

Test scenarios (each one its own test function; mocks via `respx`):

- [ ] `test_create_session_returns_access_jwt` — POST to `com.atproto.server.createSession` with handle+app-password, mock response shape `{accessJwt, refreshJwt, did}`, assert returned token.
- [ ] `test_create_session_raises_on_401` — auth failure returns clear exception message.
- [ ] `test_probe_bookmark_endpoints_succeeds_on_first` — first endpoint returns 200, function returns its response without trying others.
- [ ] `test_probe_bookmark_endpoints_falls_through_on_404` — first returns 404, second returns 200, function uses the second.
- [ ] `test_probe_bookmark_endpoints_raises_when_all_fail` — all endpoints return 4xx, function raises `NoBookmarkEndpointError` listing what was tried.
- [ ] `test_pagination_collects_all_pages` — first page has `cursor`, second page has none; function collects both pages' bookmarks.
- [ ] `test_merge_preserves_existing_entries` — given inventory with URI X and a fetch result with URIs X and Y, merge keeps the original X and adds Y (no overwrites).
- [ ] `test_merge_sorts_by_saved_at_desc` — newest first in output regardless of fetch order.
- [ ] `test_merge_idempotent_when_no_new_saves` — re-running with the same fetch result produces no diff in `saves` array (`fetched_at` may differ).
- [ ] `test_extract_embed_external_pulls_url_title_description` — given a post with `app.bsky.embed.external`, function extracts `url`, `title`, `description` into the inventory entry.
- [ ] `test_extract_handles_missing_embed` — post with no embed produces an entry with `embed: null` (no crash).

- [ ] **Step 2.1:** Write all tests above. Each ~10–20 lines using `respx.mock` for HTTP and a small `make_inventory(...)` helper.

- [ ] **Step 2.2:** Run `pytest tests/test_fetch_saves.py -v`. Expected: all fail with `ModuleNotFoundError: No module named 'fetch_saves'`. Red bar achieved.

- [ ] **Step 2.3:** Commit failing tests.

---

## Task 3 — Implement `scripts/fetch_saves.py` (TDD green bar)

**Files:**
- Create: `scripts/fetch_saves.py`

**Module structure** (~150 lines):

```python
"""Fetch the curator's BlueSky saves into _data/saves_inventory.json."""

# Constants
BSKY_BASE = "https://bsky.social/xrpc"
BOOKMARK_ENDPOINTS = [
    # In probe order. Each is a (method_name, params_factory) pair where
    # params_factory(cursor) returns the query params for one page.
    ("app.bsky.bookmark.getBookmarks", lambda c: {"limit": 100, "cursor": c} if c else {"limit": 100}),
    ("app.bsky.feed.getActorBookmarks", lambda c: {"actor": "$DID", "limit": 100, "cursor": c} if c else {"actor": "$DID", "limit": 100}),
    # Last-resort: list raw repo records in the bookmark collection.
    ("com.atproto.repo.listRecords", lambda c: {"repo": "$DID", "collection": "app.bsky.bookmark", "limit": 100, "cursor": c} if c else {"repo": "$DID", "collection": "app.bsky.bookmark", "limit": 100}),
]

# Public API
class NoBookmarkEndpointError(Exception): ...
def create_session(handle, app_password) -> dict
def probe_bookmark_endpoints(session) -> tuple[str, list[dict]]   # (endpoint_used, raw_records)
def normalise_record(raw) -> dict                                  # map AT-protocol record → inventory entry shape
def merge_into_inventory(existing: dict, new_entries: list[dict]) -> dict
def main() -> int                                                  # CLI entry point
```

**Auth flow:**

```python
def create_session(handle, app_password):
    r = httpx.post(
        f"{BSKY_BASE}/com.atproto.server.createSession",
        json={"identifier": handle, "password": app_password},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()  # contains accessJwt, refreshJwt, did
```

**Probe logic:**

```python
def probe_bookmark_endpoints(session):
    headers = {"Authorization": f"Bearer {session['accessJwt']}"}
    did = session["did"]
    tried = []
    for method, params_factory in BOOKMARK_ENDPOINTS:
        try:
            records = []
            cursor = None
            while True:
                params = params_factory(cursor)
                # Substitute $DID placeholder.
                params = {k: (did if v == "$DID" else v) for k, v in params.items()}
                r = httpx.get(f"{BSKY_BASE}/{method}", params=params, headers=headers, timeout=30.0)
                if r.status_code in (401, 403, 404, 400):
                    tried.append(f"{method} -> {r.status_code}")
                    break
                r.raise_for_status()
                data = r.json()
                page_records = data.get("bookmarks") or data.get("records") or data.get("feed") or []
                records.extend(page_records)
                cursor = data.get("cursor")
                if not cursor or not page_records:
                    return method, records
            else:
                # Inner loop exited without a return — try next endpoint.
                continue
        except httpx.HTTPStatusError as e:
            tried.append(f"{method} -> {e.response.status_code}")
            continue
    raise NoBookmarkEndpointError("All bookmark endpoints failed: " + "; ".join(tried))
```

**Normalisation:** map raw AT-protocol records (which vary by endpoint) into the inventory schema from spec Section 2.

**Merge:** read existing `_data/saves_inventory.json`, add new URIs, preserve existing entries verbatim, sort by `saved_at` desc, update `fetched_at`, write atomically.

**Main:**
```python
def main() -> int:
    handle = os.environ["BSKY_HANDLE"]
    app_password = os.environ["BSKY_APP_PASSWORD"]
    session = create_session(handle, app_password)
    endpoint, raw = probe_bookmark_endpoints(session)
    print(f"fetch_saves: used endpoint {endpoint}, got {len(raw)} records", file=sys.stderr)
    new_entries = [normalise_record(r) for r in raw]
    inv_path = Path("_data/saves_inventory.json")
    existing = json.loads(inv_path.read_text())
    merged = merge_into_inventory(existing, new_entries)
    inv_path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    print(f"fetch_saves: inventory now has {len(merged['saves'])} total entries", file=sys.stderr)
    return 0
```

- [ ] **Step 3.1:** Write `scripts/fetch_saves.py` per the structure above.

- [ ] **Step 3.2:** Run `pytest tests/test_fetch_saves.py -v`. Iterate until green bar.

- [ ] **Step 3.3:** Commit.

---

## Task 4 — `.github/workflows/fetch.yml`

**Files:**
- Create: `.github/workflows/fetch.yml`

Schedule: daily at 07:17 UTC (off-peak, avoids runner contention) + `workflow_dispatch` for manual triggers.

```yaml
name: fetch saves

on:
  schedule:
    - cron: "17 7 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Python deps
        run: pip install -r scripts/requirements.txt

      - name: Fetch saves
        env:
          BSKY_HANDLE: ${{ secrets.BSKY_HANDLE }}
          BSKY_APP_PASSWORD: ${{ secrets.BSKY_APP_PASSWORD }}
        run: python scripts/fetch_saves.py

      - name: Commit if changed
        run: |
          git config user.name "fetch-saves[bot]"
          git config user.email "fetch-saves@users.noreply.github.com"
          if [ -n "$(git status --porcelain _data/saves_inventory.json)" ]; then
            git add _data/saves_inventory.json
            git commit -m "data: refresh saves inventory"
            git push
          else
            echo "no changes"
          fi
```

- [ ] **Step 4.1:** Write `.github/workflows/fetch.yml`.

- [ ] **Step 4.2:** Commit (workflow doesn't run yet — secrets aren't set).

---

## Task 5 — Update spec Section 7 with the pivot

**Files:**
- Modify: `docs/superpowers/specs/2026-04-27-stories-design.md`

Add an errata note to Section 7 explaining that the "local-only script, no GitHub Action" decision was reversed under the no-local-execution constraint (decided 2026-04-27 morning).

- [ ] **Step 5.1:** Append errata to Section 7 noting the design pivot.

- [ ] **Step 5.2:** Commit alongside Task 6.

---

## Task 6 — Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 6.1:** Replace the "PR 2: Ingestion. Strategy is open under the no-local-execution constraint" line with concrete description: scheduled GitHub Action, secrets needed.

- [ ] **Step 6.2:** Add a "Repo secrets to set" section telling the curator (in plain language) to set `BSKY_HANDLE` and `BSKY_APP_PASSWORD` via repo Settings before the workflow can run.

- [ ] **Step 6.3:** Commit.

---

## Task 7 — Push and document next steps for curator

- [ ] **Step 7.1:** Push branch.

- [ ] **Step 7.2:** Verify CI workflow goes green (running tests should pass; the fetch workflow won't run since no schedule trigger fires immediately and no secrets are set yet).

- [ ] **Step 7.3:** Tell curator: set `BSKY_HANDLE` and `BSKY_APP_PASSWORD` as repo secrets, then trigger the `fetch saves` workflow manually (Actions tab → fetch saves → Run workflow). Watch logs.

- [ ] **Step 7.4:** If workflow goes green, inventory is now flowing → ready for PR 3 (bulk-draft). If 401/403 on all endpoints (`NoBookmarkEndpointError`), pivot to Option D (OAuth-via-chat) or Option B (manual paste) — write the appropriate plan in a follow-up session.

---

## Self-review

**Spec coverage:** Section 7 of the spec describes ingestion. This plan implements it (with a pivot noted in Task 5).

**Type consistency:** `create_session` returns dict with `accessJwt` / `did` keys, used by `probe_bookmark_endpoints`. `normalise_record` produces dicts matching the inventory schema in spec Section 2. `merge_into_inventory` returns the full inventory dict (with `fetched_at` and `saves` array).

**Error paths:** `NoBookmarkEndpointError` is the documented failure for "app password can't read bookmarks". The workflow will fail loudly so the curator knows to pivot.

**Placeholders:** none.

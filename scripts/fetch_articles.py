"""Hydrate inventory entries with article_text for saves with external embeds.

Iterates `_data/saves_inventory.json` for entries whose embed.url has not yet
been fetched, downloads the article HTML, extracts the main text via
trafilatura, and writes the result back into the entry's `article_text` field.

Idempotent: entries with `article_text` already populated are skipped.
Entries that fail are marked with `article_fetch_error` so subsequent runs
don't pointlessly re-hit them — but the next run *will* retry on demand if
the curator deletes that error field.

Designed to run in GitHub Actions (where outbound to news sites is allowed).
The fetch_articles.yml workflow runs this on workflow_dispatch and commits
the resulting inventory diff.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import trafilatura

USER_AGENT = (
    "lightseed-stories/0.1 (+https://lightseed.net/stories/; "
    "personal archive of saved BlueSky posts)"
)
RATE_LIMIT_SEC = 1.0
TIMEOUT = 30.0
MIN_EXTRACT_CHARS = 100  # below this, treat extraction as failed


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_article_text(url: str) -> tuple[str | None, str | None]:
    """Return (text, error). Exactly one of the two is non-None."""
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
            follow_redirects=True,
            timeout=TIMEOUT,
        )
    except Exception as e:
        return None, f"fetch_error:{type(e).__name__}:{str(e)[:120]}"

    if r.status_code >= 400:
        return None, f"http_{r.status_code}"

    text = trafilatura.extract(
        r.text,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
    )
    if not text or len(text.strip()) < MIN_EXTRACT_CHARS:
        return None, "extraction_too_short_or_empty"
    return text.strip(), None


def main() -> int:
    inv_path = Path("_data/saves_inventory.json")
    inv = json.loads(inv_path.read_text())
    saves = inv["saves"]

    pending = []
    for s in saves:
        embed = s.get("embed") or {}
        if embed.get("type") != "external":
            continue
        url = embed.get("url")
        if not url:
            continue
        if s.get("article_text"):
            continue  # already hydrated
        if s.get("article_fetch_error"):
            # Skip permanent failures unless the curator clears the error.
            continue
        pending.append(s)

    if not pending:
        print("fetch_articles: nothing to hydrate", file=sys.stderr)
        return 0

    print(
        f"fetch_articles: {len(pending)} entries to hydrate",
        file=sys.stderr,
    )

    success = 0
    failed = 0
    for i, s in enumerate(pending, 1):
        url = s["embed"]["url"]
        print(f"  [{i}/{len(pending)}] {url[:100]}", file=sys.stderr)
        text, error = fetch_article_text(url)
        s["article_fetched_at"] = now_iso()
        if text:
            s["article_text"] = text
            s.pop("article_fetch_error", None)
            success += 1
            print(f"    ok ({len(text)} chars)", file=sys.stderr)
        else:
            s["article_fetch_error"] = error
            s.pop("article_text", None)
            failed += 1
            print(f"    FAIL: {error}", file=sys.stderr)
        time.sleep(RATE_LIMIT_SEC)

    inv["fetched_at"] = now_iso()
    inv_path.write_text(json.dumps(inv, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    print(
        f"fetch_articles: hydrated {success}, failed {failed}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

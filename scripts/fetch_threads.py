"""Hydrate inventory entries with thread_replies — same-author posts in
the thread descending from the bookmarked post.

For each save in `_data/saves_inventory.json`, calls
`app.bsky.feed.getPostThread` on the public AT Protocol AppView (no auth
needed) and collects descendant posts whose author DID matches the
bookmarked post's author. Stored as `thread_replies` in the entry.

This addresses the case where a saved post is the start of a self-thread
("🧵") that continues with substantive content the bookmark alone doesn't
capture. Drafting in chat can then read the full self-thread from the
inventory.

Idempotent: skips entries already hydrated (thread_replies present, even
if empty list) or marked with thread_fetch_error.

Designed to run in GitHub Actions (workflow_dispatch). The Claude
sandbox's outbound to public.api.bsky.app is blocked.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from fetch_saves import _extract_media

# Bump this when the thread_replies schema changes; entries whose stored
# thread_schema_version is below the current value are re-fetched on the
# next run.
THREAD_SCHEMA_VERSION = 2

APPVIEW = "https://public.api.bsky.app"
USER_AGENT = (
    "lightseed-stories/0.1 (+https://lightseed.net/stories/; "
    "personal archive of saved BlueSky posts)"
)
RATE_LIMIT_SEC = 0.5
TIMEOUT = 30.0


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_thread(uri: str) -> tuple[dict | None, str | None]:
    """Returns (thread_root, error). Exactly one is non-None."""
    try:
        r = httpx.get(
            f"{APPVIEW}/xrpc/app.bsky.feed.getPostThread",
            params={"uri": uri},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
    except Exception as e:
        return None, f"fetch_error:{type(e).__name__}:{str(e)[:120]}"
    if r.status_code >= 400:
        return None, f"http_{r.status_code}"
    body = r.json()
    return body.get("thread"), None


def collect_same_author_replies(thread: dict, author_did: str) -> list[dict]:
    """Walk the thread tree depth-first, returning posts whose author DID
    matches `author_did`. We recurse into all nodes (not just same-author
    ones) so a self-thread interrupted by other replies is still captured.
    Each reply also has its embedded media extracted."""
    out: list[dict] = []
    seen_uris: set[str] = set()

    def visit(node):
        if not isinstance(node, dict):
            return
        for reply in node.get("replies", []) or []:
            post = (reply or {}).get("post") or {}
            author = post.get("author", {})
            uri = post.get("uri", "")
            if author.get("did") == author_did and uri and uri not in seen_uris:
                record = post.get("record", {}) or {}
                embed_view = post.get("embed") or {}
                out.append(
                    {
                        "uri": uri,
                        "indexedAt": post.get("indexedAt", ""),
                        "text": record.get("text", ""),
                        "images": _extract_media(embed_view),
                    }
                )
                seen_uris.add(uri)
            visit(reply)

    visit(thread)
    return out


def main() -> int:
    inv_path = Path("_data/saves_inventory.json")
    inv = json.loads(inv_path.read_text())
    saves = inv["saves"]

    pending = []
    for s in saves:
        # Re-fetch if the entry was hydrated under an older schema version
        # (initial v1 schema captured only {uri, indexedAt, text} per reply,
        # without images).
        if (
            "thread_replies" in s
            and s.get("thread_schema_version") == THREAD_SCHEMA_VERSION
        ):
            continue
        if s.get("thread_fetch_error"):
            # Honour stored fetch errors (curator can clear the error field
            # to retry). Bumping the schema version does NOT auto-retry
            # failed entries — they remain in the failure state.
            continue
        pending.append(s)

    if not pending:
        print("fetch_threads: nothing to hydrate", file=sys.stderr)
        return 0

    print(
        f"fetch_threads: {len(pending)} entries to hydrate",
        file=sys.stderr,
    )

    success = 0
    failed = 0
    found_any = 0
    for i, s in enumerate(pending, 1):
        uri = s["uri"]
        author_did = s["author"]["did"]
        print(f"  [{i}/{len(pending)}] {uri[:80]}", file=sys.stderr)
        thread, error = fetch_thread(uri)
        s["thread_fetched_at"] = now_iso()
        if thread is not None:
            replies = collect_same_author_replies(thread, author_did)
            s["thread_replies"] = replies
            s["thread_schema_version"] = THREAD_SCHEMA_VERSION
            s.pop("thread_fetch_error", None)
            success += 1
            if replies:
                found_any += 1
            print(f"    ok ({len(replies)} self-replies)", file=sys.stderr)
        else:
            s["thread_fetch_error"] = error
            s.pop("thread_replies", None)
            failed += 1
            print(f"    FAIL: {error}", file=sys.stderr)
        time.sleep(RATE_LIMIT_SEC)

    inv["fetched_at"] = now_iso()
    inv_path.write_text(json.dumps(inv, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    print(
        f"fetch_threads: {success} hydrated ({found_any} had self-replies), {failed} failed",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

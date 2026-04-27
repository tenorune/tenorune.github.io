"""Fetch the curator's BlueSky saves into _data/saves_inventory.json.

Designed to run inside .github/workflows/fetch.yml on a daily schedule.
Authenticates via app password (BSKY_HANDLE / BSKY_APP_PASSWORD env vars,
provided by repo Secrets), probes several bookmark-related XRPC endpoints
in fallback order, and merges new entries into the inventory.

Spec source: docs/superpowers/specs/2026-04-27-stories-design.md Section 7
(with the 2026-04-27 errata that pivoted from local-only to GitHub Action).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable

import httpx

BSKY_BASE = "https://bsky.social/xrpc"

# Endpoints tried in order. Each entry is (xrpc_method, params_factory).
# params_factory(cursor, did) returns the GET params dict for that page; the
# function uses None for cursor on the first call.
EndpointParams = Callable[[str | None, str], dict]

BOOKMARK_ENDPOINTS: list[tuple[str, EndpointParams]] = [
    (
        "app.bsky.bookmark.getBookmarks",
        lambda cursor, did: {"limit": 100, **({"cursor": cursor} if cursor else {})},
    ),
    (
        "app.bsky.feed.getActorBookmarks",
        lambda cursor, did: {"actor": did, "limit": 100, **({"cursor": cursor} if cursor else {})},
    ),
    (
        "com.atproto.repo.listRecords",
        lambda cursor, did: {
            "repo": did,
            "collection": "app.bsky.bookmark",
            "limit": 100,
            **({"cursor": cursor} if cursor else {}),
        },
    ),
]

# Status codes treated as "this endpoint isn't available, try the next one".
ENDPOINT_FAILURE_CODES = {400, 401, 403, 404}


class NoBookmarkEndpointError(Exception):
    """All probed bookmark endpoints failed."""


# ----- auth -----

def create_session(handle: str, app_password: str) -> dict:
    """Authenticate via com.atproto.server.createSession.

    Returns the session dict (accessJwt, refreshJwt, did, handle).
    Raises httpx.HTTPStatusError on non-2xx.
    """
    r = httpx.post(
        f"{BSKY_BASE}/com.atproto.server.createSession",
        json={"identifier": handle, "password": app_password},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


# ----- bookmark probing -----

def _records_from_response(data: dict) -> list[dict]:
    """The bookmark endpoints don't all return the same key. Check the common
    candidates in priority order."""
    for key in ("bookmarks", "records", "feed"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return []


def probe_bookmark_endpoints(session: dict) -> tuple[str, list[dict]]:
    """Try each endpoint in BOOKMARK_ENDPOINTS until one returns 200.

    Returns (endpoint_name, list_of_raw_records). Records are accumulated
    across all pages of the chosen endpoint.

    Raises NoBookmarkEndpointError listing each (endpoint, status_code)
    that was tried and failed.
    """
    headers = {"Authorization": f"Bearer {session['accessJwt']}"}
    did = session["did"]
    tried: list[str] = []

    for method, params_factory in BOOKMARK_ENDPOINTS:
        records: list[dict] = []
        cursor: str | None = None
        endpoint_failed = False

        while True:
            params = params_factory(cursor, did)
            r = httpx.get(
                f"{BSKY_BASE}/{method}",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            if r.status_code in ENDPOINT_FAILURE_CODES:
                tried.append(f"{method} -> {r.status_code}")
                endpoint_failed = True
                break
            r.raise_for_status()
            data = r.json()
            page = _records_from_response(data)
            records.extend(page)
            cursor = data.get("cursor")
            if not cursor or not page:
                break

        if not endpoint_failed:
            return method, records

    raise NoBookmarkEndpointError(
        "All bookmark endpoints failed: " + "; ".join(tried)
    )


# ----- normalisation -----

def normalise_record(raw: dict) -> dict:
    """Map a raw AT-protocol record to the inventory schema (spec Section 2).

    The shape varies between endpoints, but at minimum we need:
    - uri: the saved post's URI
    - saved_at: when the user saved it
    - post_text: the post's text content
    - embed: {type, url, title, description} if external embed, else None
    - author: {handle, display_name, did}
    """
    saved_at = raw.get("indexedAt") or raw.get("createdAt") or ""

    # Records may wrap the bookmarked post in `value.subject` or `subject` directly.
    value = raw.get("value", raw)
    subject = value.get("subject", value)
    post_uri = subject.get("uri") or raw.get("uri", "")
    post_value = subject.get("value", subject)

    post_text = post_value.get("text", "")

    embed = None
    embed_raw = post_value.get("embed") or {}
    if embed_raw.get("$type") == "app.bsky.embed.external":
        ext = embed_raw.get("external", {})
        embed = {
            "type": "external",
            "url": ext.get("uri", ""),
            "title": ext.get("title", ""),
            "description": ext.get("description", ""),
        }

    author_raw = subject.get("author", {})
    author = {
        "handle": author_raw.get("handle", ""),
        "display_name": author_raw.get("displayName", ""),
        "did": author_raw.get("did", ""),
    }

    return {
        "uri": post_uri,
        "saved_at": saved_at,
        "post_text": post_text,
        "embed": embed,
        "author": author,
    }


# ----- merge -----

def merge_into_inventory(existing: dict, new_entries: list[dict]) -> dict:
    """Merge new_entries into existing inventory.

    Rules (spec Section 7):
    - Keyed by `uri`. Existing entries are NEVER modified.
    - New URIs are appended.
    - Result sorted by `saved_at` desc (newest first).
    - `fetched_at` updated to current run; the script's caller fills this in.
    """
    by_uri = {s["uri"]: s for s in existing.get("saves", [])}
    for entry in new_entries:
        uri = entry.get("uri", "")
        if not uri:
            continue
        if uri not in by_uri:
            by_uri[uri] = entry
    saves = sorted(by_uri.values(), key=lambda s: s.get("saved_at", ""), reverse=True)
    return {
        "fetched_at": existing.get("fetched_at"),
        "saves": saves,
    }


# ----- main -----

def main() -> int:
    handle = os.environ.get("BSKY_HANDLE")
    app_password = os.environ.get("BSKY_APP_PASSWORD")
    if not handle or not app_password:
        print(
            "fetch_saves: BSKY_HANDLE and BSKY_APP_PASSWORD must be set",
            file=sys.stderr,
        )
        return 2

    print(f"fetch_saves: authenticating as {handle}", file=sys.stderr)
    session = create_session(handle, app_password)

    print("fetch_saves: probing bookmark endpoints", file=sys.stderr)
    endpoint, raw = probe_bookmark_endpoints(session)
    print(
        f"fetch_saves: used {endpoint} ({len(raw)} raw records)",
        file=sys.stderr,
    )

    new_entries = [normalise_record(r) for r in raw]

    inv_path = Path("_data/saves_inventory.json")
    existing = json.loads(inv_path.read_text()) if inv_path.exists() else {
        "fetched_at": None,
        "saves": [],
    }
    merged = merge_into_inventory(existing, new_entries)

    # Stamp current fetched_at.
    from datetime import datetime, timezone
    merged["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    inv_path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    print(
        f"fetch_saves: inventory now has {len(merged['saves'])} total entries",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests for scripts/fetch_saves.py with mocked HTTP via respx."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

# Module path is set up by tests/conftest.py.
import fetch_saves  # noqa: E402


BSKY_BASE = "https://bsky.social/xrpc"


def _mock_session(handle="user.bsky.social", did="did:plc:abc"):
    """Return a fake session dict like createSession response."""
    return {
        "accessJwt": "fake-access-token",
        "refreshJwt": "fake-refresh-token",
        "did": did,
        "handle": handle,
    }


# ---------- create_session ----------

@respx.mock
def test_create_session_returns_access_jwt():
    respx.post(f"{BSKY_BASE}/com.atproto.server.createSession").mock(
        return_value=httpx.Response(
            200,
            json={
                "accessJwt": "abc",
                "refreshJwt": "def",
                "did": "did:plc:xyz",
                "handle": "user.bsky.social",
            },
        )
    )
    session = fetch_saves.create_session("user.bsky.social", "app-password")
    assert session["accessJwt"] == "abc"
    assert session["did"] == "did:plc:xyz"


@respx.mock
def test_create_session_raises_on_401():
    respx.post(f"{BSKY_BASE}/com.atproto.server.createSession").mock(
        return_value=httpx.Response(401, json={"error": "AuthenticationRequired"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        fetch_saves.create_session("user.bsky.social", "wrong-password")


# ---------- probe_bookmark_endpoints ----------

@respx.mock
def test_probe_bookmark_endpoints_succeeds_on_first():
    session = _mock_session()
    respx.get(f"{BSKY_BASE}/app.bsky.bookmark.getBookmarks").mock(
        return_value=httpx.Response(
            200,
            json={"bookmarks": [{"uri": "at://x/1", "indexedAt": "2026-04-12T00:00:00Z"}]},
        )
    )
    endpoint, records = fetch_saves.probe_bookmark_endpoints(session)
    assert endpoint == "app.bsky.bookmark.getBookmarks"
    assert len(records) == 1
    assert records[0]["uri"] == "at://x/1"


@respx.mock
def test_probe_bookmark_endpoints_falls_through_on_404():
    session = _mock_session()
    respx.get(f"{BSKY_BASE}/app.bsky.bookmark.getBookmarks").mock(
        return_value=httpx.Response(404, json={"error": "MethodNotImplemented"})
    )
    respx.get(f"{BSKY_BASE}/app.bsky.feed.getActorBookmarks").mock(
        return_value=httpx.Response(
            200, json={"bookmarks": [{"uri": "at://y/1", "indexedAt": "2026-04-12T00:00:00Z"}]}
        )
    )
    endpoint, records = fetch_saves.probe_bookmark_endpoints(session)
    assert endpoint == "app.bsky.feed.getActorBookmarks"
    assert records[0]["uri"] == "at://y/1"


@respx.mock
def test_probe_bookmark_endpoints_raises_when_all_fail():
    session = _mock_session()
    respx.get(f"{BSKY_BASE}/app.bsky.bookmark.getBookmarks").mock(
        return_value=httpx.Response(401, json={"error": "AuthenticationRequired"})
    )
    respx.get(f"{BSKY_BASE}/app.bsky.feed.getActorBookmarks").mock(
        return_value=httpx.Response(404, json={"error": "MethodNotImplemented"})
    )
    respx.get(f"{BSKY_BASE}/com.atproto.repo.listRecords").mock(
        return_value=httpx.Response(403, json={"error": "Forbidden"})
    )
    with pytest.raises(fetch_saves.NoBookmarkEndpointError) as exc_info:
        fetch_saves.probe_bookmark_endpoints(session)
    msg = str(exc_info.value)
    assert "401" in msg
    assert "404" in msg
    assert "403" in msg


@respx.mock
def test_pagination_collects_all_pages():
    session = _mock_session()
    respx.get(f"{BSKY_BASE}/app.bsky.bookmark.getBookmarks").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "bookmarks": [{"uri": "at://x/1", "indexedAt": "2026-04-12T00:00:00Z"}],
                    "cursor": "page2",
                },
            ),
            httpx.Response(
                200,
                json={
                    "bookmarks": [{"uri": "at://x/2", "indexedAt": "2026-04-11T00:00:00Z"}],
                },
            ),
        ]
    )
    endpoint, records = fetch_saves.probe_bookmark_endpoints(session)
    uris = [r["uri"] for r in records]
    assert uris == ["at://x/1", "at://x/2"]


# ---------- merge_into_inventory ----------

def _empty_inventory():
    return {"fetched_at": None, "saves": []}


def test_merge_preserves_existing_entries():
    existing = {
        "fetched_at": "2026-04-01T00:00:00Z",
        "saves": [
            {
                "uri": "at://x/1",
                "saved_at": "2026-04-01T12:00:00Z",
                "post_text": "original",
                "embed": None,
                "author": {"handle": "a", "display_name": "A", "did": "did:plc:a"},
            }
        ],
    }
    new_entries = [
        {
            "uri": "at://x/1",
            "saved_at": "2026-04-12T00:00:00Z",
            "post_text": "REPLACED — must not appear",
            "embed": None,
            "author": {"handle": "a", "display_name": "A", "did": "did:plc:a"},
        },
        {
            "uri": "at://x/2",
            "saved_at": "2026-04-12T00:00:00Z",
            "post_text": "new",
            "embed": None,
            "author": {"handle": "b", "display_name": "B", "did": "did:plc:b"},
        },
    ]
    merged = fetch_saves.merge_into_inventory(existing, new_entries)
    by_uri = {s["uri"]: s for s in merged["saves"]}
    assert by_uri["at://x/1"]["post_text"] == "original"  # preserved
    assert by_uri["at://x/2"]["post_text"] == "new"  # added


def test_merge_sorts_by_saved_at_desc():
    existing = _empty_inventory()
    new_entries = [
        {"uri": "at://x/A", "saved_at": "2026-04-10T00:00:00Z", "post_text": "", "embed": None, "author": {}},
        {"uri": "at://x/B", "saved_at": "2026-04-12T00:00:00Z", "post_text": "", "embed": None, "author": {}},
        {"uri": "at://x/C", "saved_at": "2026-04-11T00:00:00Z", "post_text": "", "embed": None, "author": {}},
    ]
    merged = fetch_saves.merge_into_inventory(existing, new_entries)
    saved_ats = [s["saved_at"] for s in merged["saves"]]
    assert saved_ats == sorted(saved_ats, reverse=True)


def test_merge_idempotent_when_no_new_saves():
    seed = {
        "fetched_at": "2026-04-01T00:00:00Z",
        "saves": [
            {
                "uri": "at://x/1",
                "saved_at": "2026-04-01T12:00:00Z",
                "post_text": "p",
                "embed": None,
                "author": {"handle": "a", "display_name": "A", "did": "did:plc:a"},
            }
        ],
    }
    new_entries = [seed["saves"][0].copy()]  # exact same URI
    merged = fetch_saves.merge_into_inventory(seed, new_entries)
    # Saves array should be identical (modulo order).
    assert sorted(json.dumps(s, sort_keys=True) for s in merged["saves"]) == sorted(
        json.dumps(s, sort_keys=True) for s in seed["saves"]
    )


# ---------- normalise_record ----------

def test_extract_embed_external_pulls_url_title_description():
    raw = {
        "uri": "at://x/1",
        "indexedAt": "2026-04-12T00:00:00Z",
        "value": {
            "createdAt": "2026-04-12T00:00:00Z",
            "subject": {
                "uri": "at://author/post1",
                "value": {
                    "text": "post text here",
                    "embed": {
                        "$type": "app.bsky.embed.external",
                        "external": {
                            "uri": "https://example.org/article",
                            "title": "Article title",
                            "description": "Article description",
                        },
                    },
                },
                "author": {
                    "handle": "author.bsky.social",
                    "displayName": "Author Name",
                    "did": "did:plc:author",
                },
            },
        },
    }
    entry = fetch_saves.normalise_record(raw)
    assert entry["uri"] == "at://author/post1"
    assert entry["embed"]["url"] == "https://example.org/article"
    assert entry["embed"]["title"] == "Article title"
    assert entry["embed"]["description"] == "Article description"
    assert entry["embed"]["type"] == "external"


def test_extract_handles_missing_embed():
    raw = {
        "uri": "at://x/2",
        "indexedAt": "2026-04-12T00:00:00Z",
        "value": {
            "createdAt": "2026-04-12T00:00:00Z",
            "subject": {
                "uri": "at://author/post2",
                "value": {"text": "no embed"},
                "author": {
                    "handle": "h",
                    "displayName": "H",
                    "did": "did:plc:h",
                },
            },
        },
    }
    entry = fetch_saves.normalise_record(raw)
    assert entry["uri"] == "at://author/post2"
    assert entry["embed"] is None

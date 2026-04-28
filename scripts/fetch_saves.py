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

# Two distinct base URLs in AT Protocol:
#  - PDS hosts the user's account, records, and authentication. For users on
#    bsky.social this is bsky.social; for users on a third-party PDS
#    (self-hosted or any non-bsky.social ATproto host) it is that PDS.
#  - AppView hosts hydrated cross-PDS views like getBookmarks. This is bsky's
#    public AppView, regardless of which PDS the user lives on.
PDS_BASE = os.environ.get("BSKY_PDS", "https://bsky.social").rstrip("/")
# bsky.social serves the *authenticated* AppView for app.bsky.* user-data
# endpoints (getBookmarks, getActorBookmarks, etc.). public.api.bsky.app is
# the unauthenticated public read AppView (profile lookups, post threads) and
# does NOT implement the authenticated bookmark endpoints — calls there
# return 501.
APPVIEW_BASE = os.environ.get("BSKY_APPVIEW", "https://bsky.social").rstrip("/")
# Candidate DIDs to try as the `aud` (audience) when requesting service-auth
# tokens from the user's PDS. The AppView verifies the `aud` claim against
# its own DID; if there's a mismatch it returns InvalidToken even for a
# correctly-signed token. Different BlueSky deployments have used different
# DIDs, so we try a list. Set BSKY_APPVIEW_DID to pin to one specific value.
_pinned_did = os.environ.get("BSKY_APPVIEW_DID")
if _pinned_did:
    APPVIEW_DID_CANDIDATES = [_pinned_did]
else:
    APPVIEW_DID_CANDIDATES = [
        "did:web:api.bsky.app",   # most documented
        "did:web:bsky.app",       # alternate
        "did:web:bsky.social",    # AppView-on-PDS variant
    ]

# Endpoints tried in order. Each entry is (host, xrpc_method, params_factory).
# host is "pds" (the user's PDS) or "appview" (the cross-PDS aggregator).
# params_factory(cursor, did) returns the GET params dict for that page; the
# function uses None for cursor on the first call.
EndpointParams = Callable[[str | None, str], dict]

BOOKMARK_ENDPOINTS: list[tuple[str, str, EndpointParams]] = [
    # AppView: hydrated bookmarks, but only works if the AppView trusts the
    # accessJwt issued by the user's PDS. For users on bsky.social this works
    # natively; for third-party PDS users, behaviour depends on the AppView.
    (
        "appview",
        "app.bsky.bookmark.getBookmarks",
        lambda cursor, did: {"limit": 100, **({"cursor": cursor} if cursor else {})},
    ),
    (
        "appview",
        "app.bsky.feed.getActorBookmarks",
        lambda cursor, did: {"actor": did, "limit": 100, **({"cursor": cursor} if cursor else {})},
    ),
    # PDS: raw bookmark records from the user's own repo. Always available
    # if bookmarks live in the standard collection. Returns URI references
    # (no hydrated post content).
    (
        "pds",
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
# Includes both 4xx (auth/availability) and 5xx (server-side not implemented or
# transient) — we have fallback endpoints, so broad permissiveness is correct.
# Only after every endpoint fails do we raise NoBookmarkEndpointError with the
# full diagnostic.
ENDPOINT_FAILURE_CODES = {400, 401, 403, 404, 500, 501, 502, 503, 504}


class NoBookmarkEndpointError(Exception):
    """All probed bookmark endpoints failed."""


class ServiceAuthError(Exception):
    """The PDS refused to issue a service-auth token (likely scope-restricted
    app password)."""


# ----- auth -----

def create_session(handle: str, app_password: str) -> dict:
    """Authenticate via com.atproto.server.createSession.

    Returns the session dict (accessJwt, refreshJwt, did, handle).
    Raises httpx.HTTPStatusError on non-2xx, with the response body included
    in stderr for diagnosis (BlueSky returns useful JSON like
    {"error": "AuthenticationRequired", "message": "Invalid identifier or password"}).
    """
    # Strip whitespace/newlines that often leak through GitHub Secrets UI.
    handle = (handle or "").strip()
    app_password = (app_password or "").strip()

    r = httpx.post(
        f"{PDS_BASE}/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": app_password},
        timeout=30.0,
    )
    if r.status_code >= 400:
        # Surface the actual BlueSky error body before raising.
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:500]}
        print(
            f"fetch_saves: createSession returned {r.status_code}: {body}",
            file=sys.stderr,
        )
    r.raise_for_status()
    return r.json()


# ----- service auth (cross-server) -----

def get_service_auth(session: dict, aud: str, lxm: str) -> str:
    """Request a service-auth token from the user's PDS.

    Used to call AppView endpoints (e.g., bsky.social) for a user whose
    account lives on a third-party PDS. The PDS signs a short-lived JWT with
    the user's account key, scoped to the AppView audience and a single
    lexicon method. The AppView verifies the signature against the user's
    DID document.

    Raises ServiceAuthError on 4xx with the response body for diagnosis.
    """
    headers = {"Authorization": f"Bearer {session['accessJwt']}"}
    r = httpx.get(
        f"{PDS_BASE}/xrpc/com.atproto.server.getServiceAuth",
        params={"aud": aud, "lxm": lxm},
        headers=headers,
        timeout=30.0,
    )
    if r.status_code >= 400:
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:500]}
        raise ServiceAuthError(
            f"getServiceAuth({aud}, lxm={lxm}) returned {r.status_code}: {body}"
        )
    payload = r.json()
    token = payload.get("token", "")
    print(
        f"fetch_saves:     service-auth ok aud={aud} lxm={lxm} token_len={len(token)}",
        file=sys.stderr,
    )
    return token


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

    For AppView (cross-server) endpoints, also try each APPVIEW_DID_CANDIDATES
    `aud` value — the AppView rejects tokens whose `aud` doesn't match its
    own DID with `InvalidToken`, even when the token is correctly signed.

    Returns (endpoint_name, list_of_raw_records). Records are accumulated
    across all pages of the chosen endpoint+aud.

    Raises NoBookmarkEndpointError listing each (endpoint, aud, status_code)
    that was tried and failed.
    """
    pds_headers = {"Authorization": f"Bearer {session['accessJwt']}"}
    did = session["did"]
    tried: list[str] = []

    # When the user's PDS *is* the AppView (e.g., bsky.social-hosted account
    # calling bsky.social/xrpc), service auth is unnecessary — the session
    # JWT is already valid for both sides. Skip the service-auth step in
    # that case.
    same_server = PDS_BASE == APPVIEW_BASE

    for host, method, params_factory in BOOKMARK_ENDPOINTS:
        base = PDS_BASE if host == "pds" else APPVIEW_BASE
        if host == "pds" or same_server:
            candidate_auds: list[str | None] = [None]
        else:
            candidate_auds = list(APPVIEW_DID_CANDIDATES)

        # Tracks whether this endpoint should be abandoned (status code that
        # means "this endpoint isn't going to work, try next") vs. retried
        # with a different aud (InvalidToken from AppView).
        give_up_on_endpoint = False

        for candidate_aud in candidate_auds:
            if give_up_on_endpoint:
                break

            # Set up headers for this attempt.
            if host == "pds" or candidate_aud is None:
                # PDS call, or AppView call where PDS == AppView (no service
                # auth needed; session JWT is valid for both sides).
                headers = pds_headers
            else:
                try:
                    svc_token = get_service_auth(session, candidate_aud, method)
                    headers = {"Authorization": f"Bearer {svc_token}"}
                except ServiceAuthError as e:
                    print(
                        f"fetch_saves:   {host}:{method} aud={candidate_aud} -> "
                        f"service-auth failed: {e}",
                        file=sys.stderr,
                    )
                    tried.append(f"{host}:{method} aud={candidate_aud} -> svc-auth-fail")
                    continue  # try next aud

            # Page through this endpoint+aud. Outcomes:
            # - success on every page → return
            # - InvalidToken (aud mismatch) → try next aud
            # - other failure → mark endpoint dead, break to next endpoint
            records: list[dict] = []
            cursor: str | None = None
            invalid_token = False
            request_failed = False

            while True:
                params = params_factory(cursor, did)
                r = httpx.get(
                    f"{base}/xrpc/{method}",
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )
                aud_tag = "" if host == "pds" else f" aud={candidate_aud}"
                status_msg = f"fetch_saves:   {host}:{method}{aud_tag} -> {r.status_code}"
                body: object = None
                if r.status_code >= 400:
                    try:
                        body = r.json()
                    except ValueError:
                        body = {"raw": r.text[:500]}
                    status_msg += f"  body={body}"
                print(status_msg, file=sys.stderr)

                # InvalidToken with a 400 from the AppView = try next aud.
                if (
                    host != "pds"
                    and r.status_code == 400
                    and isinstance(body, dict)
                    and body.get("error") == "InvalidToken"
                ):
                    invalid_token = True
                    break

                if r.status_code in ENDPOINT_FAILURE_CODES:
                    tried.append(f"{host}:{method}{aud_tag} -> {r.status_code}")
                    request_failed = True
                    break

                r.raise_for_status()
                data = r.json()
                page = _records_from_response(data)
                records.extend(page)
                cursor = data.get("cursor")
                if not cursor or not page:
                    break  # exhausted; success

            if invalid_token:
                continue  # try next aud
            if request_failed:
                give_up_on_endpoint = True
                break  # try next endpoint
            return method, records  # got a clean success

        # Fell out of aud loop without returning — try next endpoint.

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

def list_repo_collections(session: dict) -> list[str]:
    """Return the list of collection names in the user's PDS repo.

    Diagnostic helper: when probe_bookmark_endpoints returns 0 records, this
    tells us which collections do exist (e.g., bookmarks may be stored under
    a non-standard name on a third-party PDS).
    """
    headers = {"Authorization": f"Bearer {session['accessJwt']}"}
    r = httpx.get(
        f"{PDS_BASE}/xrpc/com.atproto.repo.describeRepo",
        params={"repo": session["did"]},
        headers=headers,
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    return list(data.get("collections", []))


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

    if not raw:
        # Diagnostic: tell us where bookmarks might actually live.
        try:
            collections = list_repo_collections(session)
            print(
                f"fetch_saves: 0 records — collections in your PDS repo: {collections}",
                file=sys.stderr,
            )
        except Exception as e:
            print(
                f"fetch_saves: 0 records, and describeRepo also failed: {e}",
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

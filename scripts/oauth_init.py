"""One-time OAuth initialization for the stories fetch workflow.

Two-phase interactive flow:

  python scripts/oauth_init.py init <handle>
      Resolves handle, contacts the auth server, prints an authorization
      URL for the curator to open. Persists transient state to a local
      gitignored file (.oauth-init-state.json).

  python scripts/oauth_init.py complete '<full-redirect-url>'
      Reads the persisted state, exchanges the auth code for tokens
      (DPoP-signed), prints the credentials the curator should add as
      repo Secrets.

Spec source: docs/superpowers/plans/2026-04-27-stories-pr2.5-oauth.md.

Designed to run in this Claude session's sandbox; the curator never
runs Python locally. Claude executes both phases with the curator's
input pasted in chat between them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import urllib.parse
from pathlib import Path

import httpx

from atproto_dpop import (
    b64url_encode,
    dpop_post_form,
    generate_dpop_key,
    jwk_to_key,
    key_to_jwk,
    public_jwk,
)

CLIENT_ID = "https://lightseed.net/oauth/client-metadata.json"
REDIRECT_URI = "https://lightseed.net/oauth/callback/"
SCOPE = "atproto transition:generic"

STATE_PATH = Path(".oauth-init-state.json")
PUBLIC_API = "https://public.api.bsky.app"


# ----- handle / DID / auth server resolution -----

def resolve_handle_to_did(handle: str) -> str:
    """Resolve a handle to its DID, trying multiple AT Protocol-standard paths.

    Order:
      1. https://<handle>/.well-known/atproto-did (HTTPS-based handle proof)
      2. https://bsky.social/xrpc/com.atproto.identity.resolveHandle (PDS)
      3. https://public.api.bsky.app/... (public AppView, often 403/rate-limited)
    """
    errors: list[str] = []

    # Path 1: HTTPS well-known
    try:
        r = httpx.get(f"https://{handle}/.well-known/atproto-did", timeout=15.0)
        if r.status_code == 200:
            did = r.text.strip()
            if did.startswith("did:"):
                return did
        errors.append(f"well-known/atproto-did -> {r.status_code}")
    except Exception as e:
        errors.append(f"well-known/atproto-did -> {type(e).__name__}: {e}")

    # Path 2: bsky.social PDS
    for base in ("https://bsky.social", PUBLIC_API):
        try:
            r = httpx.get(
                f"{base}/xrpc/com.atproto.identity.resolveHandle",
                params={"handle": handle},
                timeout=15.0,
            )
            if r.status_code == 200:
                return r.json()["did"]
            errors.append(f"{base} -> {r.status_code}")
        except Exception as e:
            errors.append(f"{base} -> {type(e).__name__}: {e}")

    raise RuntimeError(f"Failed to resolve handle '{handle}'. Tried: " + "; ".join(errors))


def resolve_did_to_pds(did: str) -> str:
    """Return the PDS endpoint URL from the DID document."""
    if did.startswith("did:plc:"):
        r = httpx.get(f"https://plc.directory/{did}", timeout=30.0)
    elif did.startswith("did:web:"):
        host = did.removeprefix("did:web:")
        r = httpx.get(f"https://{host}/.well-known/did.json", timeout=30.0)
    else:
        raise ValueError(f"Unsupported DID method: {did}")
    r.raise_for_status()
    doc = r.json()
    for svc in doc.get("service", []):
        if svc.get("id", "").endswith("#atproto_pds") or svc.get("type") == "AtprotoPersonalDataServer":
            return svc["serviceEndpoint"].rstrip("/")
    raise RuntimeError(f"No atproto_pds service entry in DID document for {did}")


def resolve_authorization_server(pds: str) -> str:
    """Find the authorization server URL from the PDS's protected-resource
    metadata."""
    r = httpx.get(f"{pds}/.well-known/oauth-protected-resource", timeout=30.0)
    r.raise_for_status()
    servers = r.json().get("authorization_servers", [])
    if not servers:
        raise RuntimeError(f"PDS {pds} declared no authorization_servers")
    return servers[0].rstrip("/")


def fetch_authorization_server_metadata(auth_server: str) -> dict:
    r = httpx.get(f"{auth_server}/.well-known/oauth-authorization-server", timeout=30.0)
    r.raise_for_status()
    return r.json()


# ----- PKCE -----

def make_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256."""
    verifier = b64url_encode(secrets.token_bytes(32))
    challenge = b64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


# ----- phase 1: init -----

def phase_init(handle: str) -> None:
    print(f"oauth_init: resolving handle '{handle}'...", file=sys.stderr)
    did = resolve_handle_to_did(handle)
    print(f"oauth_init: did = {did}", file=sys.stderr)

    pds = resolve_did_to_pds(did)
    print(f"oauth_init: pds = {pds}", file=sys.stderr)

    auth_server = resolve_authorization_server(pds)
    print(f"oauth_init: auth_server = {auth_server}", file=sys.stderr)

    meta = fetch_authorization_server_metadata(auth_server)
    par_endpoint = meta["pushed_authorization_request_endpoint"]
    auth_endpoint = meta["authorization_endpoint"]
    token_endpoint = meta["token_endpoint"]
    print(f"oauth_init: par = {par_endpoint}", file=sys.stderr)
    print(f"oauth_init: authorization_endpoint = {auth_endpoint}", file=sys.stderr)
    print(f"oauth_init: token_endpoint = {token_endpoint}", file=sys.stderr)

    private_key = generate_dpop_key()
    private_jwk = key_to_jwk(private_key)
    public_jwk = public_jwk(private_jwk)

    code_verifier, code_challenge = make_pkce()
    state = secrets.token_urlsafe(16)

    par_form = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "login_hint": handle,
    }
    print("oauth_init: sending PAR...", file=sys.stderr)
    par_resp = dpop_post_form(par_endpoint, par_form, private_key, public_jwk)
    request_uri = par_resp["request_uri"]
    print(f"oauth_init: request_uri = {request_uri}", file=sys.stderr)

    auth_url = (
        auth_endpoint
        + "?"
        + urllib.parse.urlencode({"client_id": CLIENT_ID, "request_uri": request_uri})
    )

    STATE_PATH.write_text(
        json.dumps(
            {
                "handle": handle,
                "did": did,
                "pds": pds,
                "auth_server": auth_server,
                "token_endpoint": token_endpoint,
                "code_verifier": code_verifier,
                "state": state,
                "private_jwk": private_jwk,
            },
            indent=2,
        )
    )
    print(f"oauth_init: state saved to {STATE_PATH}", file=sys.stderr)
    print()
    print("=== OPEN THIS URL IN YOUR BROWSER ===")
    print(auth_url)
    print()
    print("After authorising, you'll land on https://lightseed.net/oauth/callback/")
    print("with a long URL displayed. Copy that full URL and paste it back to")
    print("Claude, then run: python scripts/oauth_init.py complete '<that-url>'")


# ----- phase 2: complete -----

def phase_complete(redirect_url: str) -> None:
    if not STATE_PATH.exists():
        print(f"oauth_init: missing state file {STATE_PATH}; run init first", file=sys.stderr)
        sys.exit(2)
    state_data = json.loads(STATE_PATH.read_text())

    parsed = urllib.parse.urlparse(redirect_url)
    qs = urllib.parse.parse_qs(parsed.query)
    if qs.get("error"):
        raise RuntimeError(f"Auth server returned error: {qs}")
    if qs.get("state", [None])[0] != state_data["state"]:
        raise RuntimeError("OAuth state mismatch — possible CSRF, refusing")
    code = qs["code"][0]
    iss = qs.get("iss", [None])[0]
    print(f"oauth_init: received code (len={len(code)}), iss={iss}", file=sys.stderr)

    private_key = jwk_to_key(state_data["private_jwk"])
    public_jwk = public_jwk(state_data["private_jwk"])

    token_form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": state_data["code_verifier"],
    }
    print("oauth_init: exchanging code for tokens...", file=sys.stderr)
    tokens = dpop_post_form(state_data["token_endpoint"], token_form, private_key, public_jwk)

    print()
    print("=== ADD THESE AS REPO SECRETS ===")
    print()
    print(f"BSKY_OAUTH_REFRESH_TOKEN={tokens['refresh_token']}")
    print()
    print(f"BSKY_OAUTH_DPOP_PRIVATE_JWK={json.dumps(state_data['private_jwk'])}")
    print()
    print(f"BSKY_OAUTH_PDS_ISSUER={state_data['pds']}")
    print()
    print(f"BSKY_OAUTH_DID={state_data['did']}")
    print()
    print("=== ADD AS REPO VARIABLE (or leave default) ===")
    print()
    print(f"BSKY_OAUTH_TOKEN_ENDPOINT={state_data['token_endpoint']}")
    print()
    print("Once added, the fetch workflow can use the OAuth path.")

    # Show access token as a sanity check (its value is not stored — it's
    # short-lived, the workflow refreshes on each run).
    print(f"\n(access_token len={len(tokens.get('access_token', ''))}, "
          f"expires_in={tokens.get('expires_in')}, "
          f"scope={tokens.get('scope')})", file=sys.stderr)


# ----- CLI -----

def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init", help="Phase 1: build authorization URL")
    pi.add_argument("handle", help="e.g., alice.bsky.social")
    pc = sub.add_parser("complete", help="Phase 2: exchange code for tokens")
    pc.add_argument("redirect_url", help="Full URL the callback page displayed")
    args = p.parse_args()

    if args.cmd == "init":
        phase_init(args.handle)
    elif args.cmd == "complete":
        phase_complete(args.redirect_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Two-phase interactive OAuth flow + runtime token-endpoint discovery.

Phase 1 (``phase_init``): resolve handle → DID → PDS → auth server, generate
DPoP keypair + PKCE, send PAR (Pushed Authorization Request), persist
transient state, return the authorization URL the user opens in a browser.

Phase 2 (``phase_complete``): parse the redirect URL the user pasted back,
verify state, exchange the auth code for tokens (DPoP-signed token request),
print the credentials to persist.

These are designed for a single-user, console-driven flow. For a server-side
multi-user flow you'd want a different state-store and to call the helpers
directly (``make_pkce``, ``make_dpop_proof``, ``dpop_post_form``) instead.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
import urllib.parse
from pathlib import Path

import httpx

from .dpop import (
    b64url_encode,
    dpop_post_form,
    generate_dpop_key,
    jwk_to_key,
    key_to_jwk,
    public_jwk,
)
from .resolve import (
    fetch_authorization_server_metadata,
    resolve_authorization_server,
    resolve_did_to_pds,
    resolve_handle_to_did,
)

DEFAULT_SCOPE = "atproto transition:generic"
DEFAULT_STATE_PATH = Path(".atproto-oauth-state.json")


def make_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256."""
    verifier = b64url_encode(secrets.token_bytes(32))
    challenge = b64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def discover_token_endpoint(pds: str) -> str:
    """Resolve PDS → authorization server → token endpoint."""
    pds = pds.rstrip("/")
    r = httpx.get(f"{pds}/.well-known/oauth-protected-resource", timeout=30.0)
    r.raise_for_status()
    auth_servers = r.json().get("authorization_servers", [])
    if not auth_servers:
        raise RuntimeError(f"PDS {pds} declared no authorization_servers")
    auth_server = auth_servers[0].rstrip("/")
    r = httpx.get(
        f"{auth_server}/.well-known/oauth-authorization-server", timeout=30.0
    )
    r.raise_for_status()
    return r.json()["token_endpoint"]


def phase_init(
    handle: str,
    *,
    client_id: str,
    redirect_uri: str,
    scope: str = DEFAULT_SCOPE,
    state_path: Path = DEFAULT_STATE_PATH,
) -> str:
    """Run phase 1. Returns the authorization URL to open in a browser."""
    print(f"atproto-oauth: resolving handle '{handle}'...", file=sys.stderr)
    did = resolve_handle_to_did(handle)
    print(f"atproto-oauth: did = {did}", file=sys.stderr)

    pds = resolve_did_to_pds(did)
    print(f"atproto-oauth: pds = {pds}", file=sys.stderr)

    auth_server = resolve_authorization_server(pds)
    print(f"atproto-oauth: auth_server = {auth_server}", file=sys.stderr)

    meta = fetch_authorization_server_metadata(auth_server)
    par_endpoint = meta["pushed_authorization_request_endpoint"]
    auth_endpoint = meta["authorization_endpoint"]
    token_endpoint = meta["token_endpoint"]
    print(f"atproto-oauth: par = {par_endpoint}", file=sys.stderr)
    print(f"atproto-oauth: authorization_endpoint = {auth_endpoint}", file=sys.stderr)
    print(f"atproto-oauth: token_endpoint = {token_endpoint}", file=sys.stderr)

    private_key = generate_dpop_key()
    private_jwk = key_to_jwk(private_key)
    pub_jwk = public_jwk(private_jwk)

    code_verifier, code_challenge = make_pkce()
    state = secrets.token_urlsafe(16)

    par_form = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "login_hint": handle,
    }
    print("atproto-oauth: sending PAR...", file=sys.stderr)
    par_resp = dpop_post_form(par_endpoint, par_form, private_key, pub_jwk)
    request_uri = par_resp["request_uri"]
    print(f"atproto-oauth: request_uri = {request_uri}", file=sys.stderr)

    auth_url = (
        auth_endpoint
        + "?"
        + urllib.parse.urlencode({"client_id": client_id, "request_uri": request_uri})
    )

    state_path.write_text(
        json.dumps(
            {
                "handle": handle,
                "did": did,
                "pds": pds,
                "auth_server": auth_server,
                "token_endpoint": token_endpoint,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
                "state": state,
                "private_jwk": private_jwk,
            },
            indent=2,
        )
    )
    print(f"atproto-oauth: state saved to {state_path}", file=sys.stderr)
    return auth_url


def phase_complete(
    redirect_url: str,
    *,
    state_path: Path = DEFAULT_STATE_PATH,
) -> dict:
    """Run phase 2. Returns the credentials dict.

    Keys: ``refresh_token``, ``private_jwk``, ``pds``, ``did``, ``token_endpoint``,
    plus ``access_token``, ``expires_in``, ``scope`` for the just-minted access
    token (which the caller can either use immediately or discard, depending on
    whether the workflow refreshes per-call).
    """
    if not state_path.exists():
        raise FileNotFoundError(
            f"missing state file {state_path}; run phase_init first"
        )
    state_data = json.loads(state_path.read_text())

    parsed = urllib.parse.urlparse(redirect_url)
    qs = urllib.parse.parse_qs(parsed.query)
    if qs.get("error"):
        raise RuntimeError(f"Auth server returned error: {qs}")
    if qs.get("state", [None])[0] != state_data["state"]:
        raise RuntimeError("OAuth state mismatch — possible CSRF, refusing")
    code = qs["code"][0]
    iss = qs.get("iss", [None])[0]
    print(f"atproto-oauth: received code (len={len(code)}), iss={iss}", file=sys.stderr)

    private_key = jwk_to_key(state_data["private_jwk"])
    pub_jwk = public_jwk(state_data["private_jwk"])

    token_form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": state_data["redirect_uri"],
        "client_id": state_data["client_id"],
        "code_verifier": state_data["code_verifier"],
    }
    print("atproto-oauth: exchanging code for tokens...", file=sys.stderr)
    tokens = dpop_post_form(state_data["token_endpoint"], token_form, private_key, pub_jwk)

    return {
        "refresh_token": tokens["refresh_token"],
        "access_token": tokens.get("access_token"),
        "expires_in": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
        "private_jwk": state_data["private_jwk"],
        "pds": state_data["pds"],
        "did": state_data["did"],
        "token_endpoint": state_data["token_endpoint"],
    }

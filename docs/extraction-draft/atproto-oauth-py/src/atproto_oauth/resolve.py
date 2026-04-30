"""Handle / DID / PDS / authorization-server resolution helpers."""
from __future__ import annotations

import httpx

PUBLIC_API = "https://public.api.bsky.app"


def resolve_handle_to_did(handle: str) -> str:
    """Resolve a handle to its DID, trying multiple AT Protocol-standard paths.

    Order:
      1. ``https://<handle>/.well-known/atproto-did`` (HTTPS-based handle proof)
      2. ``https://bsky.social/xrpc/com.atproto.identity.resolveHandle`` (PDS)
      3. ``https://public.api.bsky.app/...`` (public AppView, often 403/rate-limited)
    """
    errors: list[str] = []

    try:
        r = httpx.get(f"https://{handle}/.well-known/atproto-did", timeout=15.0)
        if r.status_code == 200:
            did = r.text.strip()
            if did.startswith("did:"):
                return did
        errors.append(f"well-known/atproto-did -> {r.status_code}")
    except Exception as e:
        errors.append(f"well-known/atproto-did -> {type(e).__name__}: {e}")

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
    """Find the authorization server URL from the PDS's protected-resource metadata."""
    r = httpx.get(f"{pds.rstrip('/')}/.well-known/oauth-protected-resource", timeout=30.0)
    r.raise_for_status()
    servers = r.json().get("authorization_servers", [])
    if not servers:
        raise RuntimeError(f"PDS {pds} declared no authorization_servers")
    return servers[0].rstrip("/")


def fetch_authorization_server_metadata(auth_server: str) -> dict:
    r = httpx.get(
        f"{auth_server.rstrip('/')}/.well-known/oauth-authorization-server",
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()

"""atproto-oauth-py — AT Protocol OAuth 2.1 + DPoP."""
from __future__ import annotations

__version__ = "0.1.0"

from .dpop import (
    b64url_decode,
    b64url_encode,
    dpop_get,
    dpop_post_form,
    generate_dpop_key,
    jwk_to_key,
    key_to_jwk,
    make_dpop_proof,
    public_jwk,
)
from .resolve import (
    fetch_authorization_server_metadata,
    resolve_authorization_server,
    resolve_did_to_pds,
    resolve_handle_to_did,
)
from .flow import discover_token_endpoint, make_pkce, phase_complete, phase_init

__all__ = [
    "__version__",
    "b64url_decode",
    "b64url_encode",
    "discover_token_endpoint",
    "dpop_get",
    "dpop_post_form",
    "fetch_authorization_server_metadata",
    "generate_dpop_key",
    "jwk_to_key",
    "key_to_jwk",
    "make_dpop_proof",
    "make_pkce",
    "phase_complete",
    "phase_init",
    "public_jwk",
    "resolve_authorization_server",
    "resolve_did_to_pds",
    "resolve_handle_to_did",
]

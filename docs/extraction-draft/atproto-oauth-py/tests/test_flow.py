"""Smoke tests for the OAuth flow helpers (PKCE)."""
from __future__ import annotations

import base64
import hashlib

from atproto_oauth.flow import make_pkce


def test_make_pkce_returns_verifier_and_s256_challenge():
    verifier, challenge = make_pkce()

    # Verifier is a base64url-encoded 32-byte random value (43 chars after
    # padding stripped).
    assert 43 <= len(verifier) <= 44

    # Challenge should equal urlsafe-base64 of sha256(verifier), no padding.
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert challenge == expected

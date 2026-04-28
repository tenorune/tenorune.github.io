"""Shared DPoP + JWK helpers for AT Protocol OAuth.

Used by scripts/oauth_init.py (one-time auth dance) and
scripts/fetch_saves.py (daily refresh + AppView calls).
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def generate_dpop_key():
    """Generate an EC P-256 keypair."""
    return ec.generate_private_key(ec.SECP256R1())


def key_to_jwk(private_key) -> dict:
    """Serialise an EC P-256 private key as a JWK dict (with d for private)."""
    nums = private_key.private_numbers()
    pub = nums.public_numbers
    x = pub.x.to_bytes(32, "big")
    y = pub.y.to_bytes(32, "big")
    d = nums.private_value.to_bytes(32, "big")
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": b64url_encode(x),
        "y": b64url_encode(y),
        "d": b64url_encode(d),
    }


def public_jwk(private_jwk: dict) -> dict:
    return {k: v for k, v in private_jwk.items() if k != "d"}


def jwk_to_key(jwk: dict):
    """Reverse of key_to_jwk: rebuild the EC private key from a JWK dict."""
    x = int.from_bytes(b64url_decode(jwk["x"]), "big")
    y = int.from_bytes(b64url_decode(jwk["y"]), "big")
    d = int.from_bytes(b64url_decode(jwk["d"]), "big")
    pub_nums = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1())
    priv_nums = ec.EllipticCurvePrivateNumbers(d, pub_nums)
    return priv_nums.private_key()


def make_dpop_proof(
    private_key,
    pub_jwk: dict,
    htm: str,
    htu: str,
    nonce: str | None = None,
    access_token: str | None = None,
) -> str:
    """Build a DPoP proof JWT for one HTTP request.

    htm = HTTP method, htu = full URL. nonce is set if the server previously
    issued a DPoP-Nonce. access_token is set when calling a resource server,
    binding the proof to the token via the `ath` claim.
    """
    payload = {
        "jti": str(uuid.uuid4()),
        "htm": htm,
        "htu": htu,
        "iat": int(time.time()),
    }
    if nonce:
        payload["nonce"] = nonce
    if access_token:
        payload["ath"] = b64url_encode(
            hashlib.sha256(access_token.encode("ascii")).digest()
        )
    headers = {"typ": "dpop+jwt", "alg": "ES256", "jwk": pub_jwk}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def dpop_post_form(url: str, form: dict, private_key, pub_jwk: dict) -> dict:
    """POST form-encoded data to `url` with a DPoP proof. Retries once with
    a DPoP-Nonce if the server returns `use_dpop_nonce`."""
    nonce: str | None = None
    for _ in range(2):
        proof = make_dpop_proof(private_key, pub_jwk, "POST", url, nonce=nonce)
        r = httpx.post(
            url,
            data=form,
            headers={
                "DPoP": proof,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30.0,
        )
        if r.status_code == 400:
            try:
                err = r.json().get("error")
            except ValueError:
                err = None
            if err == "use_dpop_nonce":
                nonce = r.headers.get("DPoP-Nonce")
                if not nonce:
                    raise RuntimeError("Server requested DPoP nonce but didn't provide one")
                continue
        if r.status_code >= 400:
            raise RuntimeError(f"POST {url} -> {r.status_code}: {r.text[:500]}")
        return r.json()
    raise RuntimeError("DPoP nonce loop did not converge")


def dpop_get(
    url: str,
    access_token: str,
    private_key,
    pub_jwk: dict,
    params: dict | None = None,
) -> httpx.Response:
    """GET a protected resource with a DPoP-bound access token. Retries once
    on use_dpop_nonce. Returns the final Response (caller decides what to do
    with status codes)."""
    nonce: str | None = None
    for _ in range(2):
        proof = make_dpop_proof(
            private_key,
            pub_jwk,
            "GET",
            url,
            nonce=nonce,
            access_token=access_token,
        )
        r = httpx.get(
            url,
            params=params,
            headers={
                "Authorization": f"DPoP {access_token}",
                "DPoP": proof,
            },
            timeout=30.0,
        )
        if r.status_code in (400, 401):
            try:
                err = r.json().get("error")
            except ValueError:
                err = None
            if err == "use_dpop_nonce":
                new_nonce = r.headers.get("DPoP-Nonce")
                if new_nonce and new_nonce != nonce:
                    nonce = new_nonce
                    continue
        return r
    return r

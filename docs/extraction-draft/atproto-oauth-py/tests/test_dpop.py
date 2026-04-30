"""Smoke tests for the DPoP / JWK helpers."""
from __future__ import annotations

import base64
import json

import jwt

from atproto_oauth.dpop import (
    b64url_decode,
    b64url_encode,
    generate_dpop_key,
    jwk_to_key,
    key_to_jwk,
    make_dpop_proof,
    public_jwk,
)


def test_b64url_roundtrip():
    data = b"hello \x00\x01\xff world"
    assert b64url_decode(b64url_encode(data)) == data


def test_b64url_no_padding():
    # urlsafe_b64encode on 1 byte normally returns 4 chars with `=` padding.
    assert "=" not in b64url_encode(b"x")


def test_key_jwk_roundtrip_yields_same_public_numbers():
    key = generate_dpop_key()
    jwk = key_to_jwk(key)
    assert jwk["kty"] == "EC"
    assert jwk["crv"] == "P-256"
    assert "d" in jwk

    rebuilt = jwk_to_key(jwk)
    n1 = key.private_numbers()
    n2 = rebuilt.private_numbers()
    assert n1.private_value == n2.private_value
    assert n1.public_numbers.x == n2.public_numbers.x
    assert n1.public_numbers.y == n2.public_numbers.y


def test_public_jwk_strips_d():
    key = generate_dpop_key()
    jwk = key_to_jwk(key)
    pub = public_jwk(jwk)
    assert "d" not in pub
    assert pub["x"] == jwk["x"]
    assert pub["y"] == jwk["y"]


def test_make_dpop_proof_includes_required_claims():
    key = generate_dpop_key()
    jwk = key_to_jwk(key)
    pub = public_jwk(jwk)
    proof = make_dpop_proof(key, pub, "POST", "https://example.com/token")

    # Header should declare typ=dpop+jwt and embed the public JWK.
    header = jwt.get_unverified_header(proof)
    assert header["typ"] == "dpop+jwt"
    assert header["alg"] == "ES256"
    assert header["jwk"] == pub

    # Payload should include htm, htu, jti, iat. Decoding without verification
    # is fine for this assertion — the signature is checked by the server,
    # not by us.
    payload_b64 = proof.split(".")[1]
    payload = json.loads(b64url_decode(payload_b64).decode("ascii"))
    assert payload["htm"] == "POST"
    assert payload["htu"] == "https://example.com/token"
    assert "jti" in payload
    assert "iat" in payload
    assert "ath" not in payload  # access_token wasn't passed


def test_make_dpop_proof_includes_ath_when_access_token_passed():
    key = generate_dpop_key()
    pub = public_jwk(key_to_jwk(key))
    proof = make_dpop_proof(
        key, pub, "GET", "https://example.com/api", access_token="some-access-token",
    )
    payload_b64 = proof.split(".")[1]
    payload = json.loads(b64url_decode(payload_b64).decode("ascii"))
    assert "ath" in payload

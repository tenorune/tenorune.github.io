# atproto-oauth-py

AT Protocol OAuth 2.1 + DPoP library and CLI for Python. Handles handle/DID/PDS
resolution, PAR (Pushed Authorization Requests), PKCE, refresh-token rotation,
and DPoP-bound HTTP calls.

## Status

Works end-to-end against the OAuth flow: `init` resolves a handle through to a
PDS-issued authorization URL, `complete` exchanges an authorization code for a
refresh token + DPoP private key. The library also exposes runtime DPoP helpers
for making authenticated calls.

There is one important caveat for the BlueSky use case (see [Limitations](#limitations)
below): BlueSky's AppView at `bsky.social` rejects OAuth tokens minted by
third-party PDSes with `"OAuth tokens are meant for PDS access only"`. OAuth is
fine for talking to your own PDS; cross-PDS AppView calls require service-auth
or app-password authentication instead.

## Install

```
pip install atproto-oauth-py
```

## CLI: one-time auth

The CLI is two-phase. Between the phases, you open a browser, authorize, and
paste back the redirect URL.

You also need a publicly-hosted **client metadata** JSON document and a
**callback page** at the redirect URI. Templates are included under
`oauth-templates/` — copy them to your hosting and edit the URLs to match your
domain.

```
# Phase 1: build the authorization URL.
export ATPROTO_OAUTH_CLIENT_ID=https://example.com/oauth/client-metadata.json
export ATPROTO_OAUTH_REDIRECT_URI=https://example.com/oauth/callback/
atproto-oauth init alice.bsky.social
```

This prints an authorization URL. Open it in a browser, sign in to your PDS,
authorize the request. You'll land on the callback page, which displays the
full URL it received. Copy that URL.

```
# Phase 2: exchange the auth code for tokens.
atproto-oauth complete 'https://example.com/oauth/callback/?code=...&state=...&iss=...'
```

This prints four credentials to add to your secrets store:

```
ATPROTO_OAUTH_REFRESH_TOKEN=...
ATPROTO_OAUTH_DPOP_PRIVATE_JWK={"kty":"EC","crv":"P-256",...}
ATPROTO_OAUTH_PDS_ISSUER=https://your-pds
ATPROTO_OAUTH_DID=did:plc:...
```

Phase 1 persists transient state to `.atproto-oauth-state.json` (gitignored);
phase 2 reads and consumes it.

## Library: runtime DPoP-bound calls

Once you have the four credentials above, you can call your PDS:

```python
import json, os
from atproto_oauth.dpop import dpop_post_form, dpop_get, jwk_to_key, public_jwk
from atproto_oauth.flow import discover_token_endpoint

private_jwk = json.loads(os.environ["ATPROTO_OAUTH_DPOP_PRIVATE_JWK"])
private_key = jwk_to_key(private_jwk)
pub_jwk = public_jwk(private_jwk)

# Refresh access token.
token_endpoint = discover_token_endpoint(os.environ["ATPROTO_OAUTH_PDS_ISSUER"])
tokens = dpop_post_form(
    token_endpoint,
    {
        "grant_type": "refresh_token",
        "refresh_token": os.environ["ATPROTO_OAUTH_REFRESH_TOKEN"],
        "client_id": os.environ["ATPROTO_OAUTH_CLIENT_ID"],
    },
    private_key, pub_jwk,
)
access_token = tokens["access_token"]

# Watch for refresh_token rotation; if tokens["refresh_token"] != the one you
# sent, persist the new one before the next call.

# Now make a DPoP-bound call.
r = dpop_get(
    f"{os.environ['ATPROTO_OAUTH_PDS_ISSUER']}/xrpc/com.atproto.repo.describeRepo",
    access_token, private_key, pub_jwk,
    params={"repo": os.environ["ATPROTO_OAUTH_DID"]},
)
print(r.json())
```

## Hosting the client metadata

OAuth 2.1 for AT Protocol uses a publicly-hosted JSON document as the
`client_id`. Copy `oauth-templates/client-metadata.json` to your web host
(GitHub Pages, Netlify, S3, etc.), edit the URLs, and serve it at a stable URL
that becomes your `ATPROTO_OAUTH_CLIENT_ID`.

`oauth-templates/callback/index.html` is the page that receives the
authorization redirect — it just displays the URL it was loaded with so you
can copy it back to phase 2.

Both files have no server-side logic; static hosting is fine.

## Limitations

- **Tested against**: bsky.social and eurosky.social PDSes. Other AT Protocol
  PDSes that expose `/.well-known/oauth-protected-resource` and
  `/.well-known/oauth-authorization-server` should work but haven't been
  verified.
- **AppView interop**: BlueSky's AppView (`bsky.social`'s `app.bsky.*`
  endpoints) explicitly rejects OAuth-minted access tokens with
  `"OAuth tokens are meant for PDS access only"`. This is a BlueSky policy,
  not a fix-able bug. OAuth tokens work for talking to *your own PDS*; for
  AppView calls you need service-auth (which only works for bsky.social-hosted
  accounts in practice) or an app password.
- **Single-user**: there is no token store, no multi-account support, and no
  encrypted-at-rest persistence. The library returns the credentials and you
  decide where to put them (env vars, secret manager, etc.).

## License

MIT. See `LICENSE`.

## Provenance

Extracted from <https://github.com/tenorune/tenorune.github.io>'s `scripts/`
directory, where it powered the OAuth scaffolding for the [Stories of 47]
archive's BlueSky save ingestion. The runtime ingestion lives in
[`bsky-saves`].

[Stories of 47]: https://lightseed.net/stories/
[`bsky-saves`]: https://pypi.org/project/bsky-saves/

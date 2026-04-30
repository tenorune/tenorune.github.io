"""Command-line entry point for ``atproto-oauth``.

  atproto-oauth init <handle>
      Phase 1: build authorization URL. Requires ATPROTO_OAUTH_CLIENT_ID and
      ATPROTO_OAUTH_REDIRECT_URI env vars (or --client-id / --redirect-uri).

  atproto-oauth complete '<full-redirect-url>'
      Phase 2: exchange code for tokens. Prints the credentials to add to
      your secret store.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .flow import DEFAULT_SCOPE, DEFAULT_STATE_PATH, phase_complete, phase_init


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atproto-oauth")
    p.add_argument(
        "--state-path",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help=f"Where to persist phase-1 state (default: {DEFAULT_STATE_PATH}).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="Phase 1: build authorization URL")
    pi.add_argument("handle", help="e.g. alice.bsky.social")
    pi.add_argument(
        "--client-id",
        default=os.environ.get("ATPROTO_OAUTH_CLIENT_ID"),
        help="Public URL of your client_metadata.json (or $ATPROTO_OAUTH_CLIENT_ID).",
    )
    pi.add_argument(
        "--redirect-uri",
        default=os.environ.get("ATPROTO_OAUTH_REDIRECT_URI"),
        help="Public URL of your callback page (or $ATPROTO_OAUTH_REDIRECT_URI).",
    )
    pi.add_argument(
        "--scope",
        default=os.environ.get("ATPROTO_OAUTH_SCOPE", DEFAULT_SCOPE),
        help=f"OAuth scope string (default: {DEFAULT_SCOPE!r}).",
    )

    pc = sub.add_parser("complete", help="Phase 2: exchange code for tokens")
    pc.add_argument("redirect_url", help="Full URL the callback page displayed")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "init":
        if not args.client_id or not args.redirect_uri:
            print(
                "atproto-oauth: --client-id and --redirect-uri (or env vars) required",
                file=sys.stderr,
            )
            return 2
        auth_url = phase_init(
            args.handle,
            client_id=args.client_id,
            redirect_uri=args.redirect_uri,
            scope=args.scope,
            state_path=args.state_path,
        )
        print()
        print("=== OPEN THIS URL IN YOUR BROWSER ===")
        print(auth_url)
        print()
        print(f"After authorising, copy the full URL the callback page shows and run:")
        print(f"  atproto-oauth complete '<that-url>'")
        return 0

    if args.cmd == "complete":
        creds = phase_complete(args.redirect_url, state_path=args.state_path)
        print()
        print("=== ADD THESE AS SECRETS ===")
        print()
        print(f"ATPROTO_OAUTH_REFRESH_TOKEN={creds['refresh_token']}")
        print()
        print(f"ATPROTO_OAUTH_DPOP_PRIVATE_JWK={json.dumps(creds['private_jwk'])}")
        print()
        print(f"ATPROTO_OAUTH_PDS_ISSUER={creds['pds']}")
        print()
        print(f"ATPROTO_OAUTH_DID={creds['did']}")
        print()
        print("=== USEFUL VARIABLE ===")
        print()
        print(f"ATPROTO_OAUTH_TOKEN_ENDPOINT={creds['token_endpoint']}")
        print()
        access = creds.get("access_token") or ""
        print(
            f"(access_token len={len(access)}, "
            f"expires_in={creds.get('expires_in')}, "
            f"scope={creds.get('scope')})",
            file=sys.stderr,
        )
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())

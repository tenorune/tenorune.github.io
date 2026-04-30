#!/usr/bin/env python3
"""Backfill post_created_at on every inventory save (offline, from rkey).

The TID embedded in the post's rkey is decoded to a UTC timestamp. This is
the moment the BlueSky post was authored — distinct from saved_at (when
the curator bookmarked it) and from any source-article publication date.

Idempotent: skips entries that already have post_created_at unless
--refresh is passed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _tid import decode_tid_to_iso, rkey_of

REPO = Path(__file__).resolve().parent.parent
INVENTORY = REPO / "_data" / "saves_inventory.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="Recompute post_created_at even if it's already set")
    args = ap.parse_args()

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    saves = inv["saves"]
    added = 0
    skipped = 0
    failed = 0

    for s in saves:
        if s.get("post_created_at") and not args.refresh:
            skipped += 1
            continue
        try:
            s["post_created_at"] = decode_tid_to_iso(rkey_of(s["uri"]))
            added += 1
        except Exception as e:
            print(f"  failed: {s.get('uri')!r}: {e}", file=sys.stderr)
            failed += 1

    INVENTORY.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"enriched: added={added} skipped={skipped} failed={failed} total={len(saves)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

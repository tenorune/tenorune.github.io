#!/usr/bin/env python3
"""Backfill post_created_at on every inventory save (offline, from rkey).

The TID embedded in the post's rkey is decoded to a UTC timestamp. This is
the moment the BlueSky post was authored — distinct from saved_at (when
the curator bookmarked it) and from any source-article publication date.

Also cleans up bogus article_published_at values:
  - if it's within ±1 day of article_fetched_at, the extractor almost
    certainly defaulted to "today" (common on YouTube and a few other
    metadata-poor hosts), so drop it.

Idempotent: skips entries that already have post_created_at unless
--refresh is passed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from _tid import decode_tid_to_iso, rkey_of

REPO = Path(__file__).resolve().parent.parent
INVENTORY = REPO / "_data" / "saves_inventory.json"


def parse_iso(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.fromisoformat(s + "T00:00:00+00:00")
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


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
    pub_dropped = 0

    for s in saves:
        if not s.get("post_created_at") or args.refresh:
            try:
                s["post_created_at"] = decode_tid_to_iso(rkey_of(s["uri"]))
                added += 1
            except Exception as e:
                print(f"  failed: {s.get('uri')!r}: {e}", file=sys.stderr)
                failed += 1
        else:
            skipped += 1

        # Clean bogus article_published_at:
        #   (a) pub date is after the post date — the article can't have
        #       been published after the BlueSky post that links it, so
        #       trafilatura got the metadata wrong (common on YouTube,
        #       which often returns the fetch date as the upload date);
        #   (b) pub date equals the fetch date (within 36h) — same
        #       fall-back behaviour, caught here for entries where the
        #       post date wasn't yet known.
        pub = parse_iso(s.get("article_published_at"))
        post = parse_iso(s.get("post_created_at"))
        fetched = parse_iso(s.get("article_fetched_at"))
        bogus = False
        if pub and post and pub > post:
            bogus = True
        elif pub and fetched and abs((pub - fetched).total_seconds()) < 86400 * 1.5:
            bogus = True
        if bogus:
            s.pop("article_published_at", None)
            pub_dropped += 1

    INVENTORY.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"enriched: added={added} skipped={skipped} failed={failed} "
          f"pub_dropped={pub_dropped} total={len(saves)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

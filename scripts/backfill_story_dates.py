#!/usr/bin/env python3
"""Backfill post_created_at on every _stories/*.md.

For each story file:
  1. Read its bluesky_uri from frontmatter.
  2. Look up the matching inventory entry's post_created_at.
  3. If the story is missing post_created_at, insert it after bluesky_saved_at.
  4. Also rewrite the `date:` field to the post date (YYYY-MM-DD) so Jekyll
     orders stories by when the BlueSky post was authored, not when the
     curator bookmarked it.

Idempotent: a story already pointing date: at its post date and carrying
post_created_at won't be touched.

This script is meant to run once after `bsky-saves enrich`; new drafts I
create directly in chat will include both fields from the start.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STORIES = REPO / "_stories"
INVENTORY = REPO / "_data" / "saves_inventory.json"

FRONTMATTER_RE = re.compile(r"\A(---\n)(.*?)(\n---\n)(.*)", re.S)
URI_RE = re.compile(r'^bluesky_uri:\s*"?(at://[^"\s]+)"?\s*$', re.M)
DATE_RE = re.compile(r'^date:\s*[^\n]+$', re.M)
POST_AT_RE = re.compile(r'^post_created_at:\s*[^\n]+$', re.M)
SAVED_AT_RE = re.compile(r'^bluesky_saved_at:\s*[^\n]+$', re.M)


def main() -> int:
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    by_uri = {s["uri"]: s for s in inv["saves"]}
    updated = 0
    skipped = 0

    for md in sorted(STORIES.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        fm = m.group(2)

        uri_m = URI_RE.search(fm)
        if not uri_m:
            print(f"  {md.name}: no bluesky_uri", file=sys.stderr)
            continue
        uri = uri_m.group(1)
        save = by_uri.get(uri)
        if not save:
            print(f"  {md.name}: uri not in inventory", file=sys.stderr)
            continue
        post_created_at = save.get("post_created_at")
        if not post_created_at:
            print(f"  {md.name}: inventory entry missing post_created_at", file=sys.stderr)
            continue
        post_date = post_created_at[:10]

        new_fm = fm

        # Update `date:` to post_date.
        new_fm = DATE_RE.sub(f"date: {post_date}", new_fm)

        # Insert or update `post_created_at:` right after `bluesky_saved_at:`.
        if POST_AT_RE.search(new_fm):
            new_fm = POST_AT_RE.sub(f'post_created_at: "{post_created_at}"', new_fm)
        else:
            saved_m = SAVED_AT_RE.search(new_fm)
            if saved_m:
                end = saved_m.end()
                new_fm = new_fm[:end] + f'\npost_created_at: "{post_created_at}"' + new_fm[end:]
            else:
                new_fm = new_fm.rstrip() + f'\npost_created_at: "{post_created_at}"\n'

        if new_fm == fm:
            skipped += 1
            continue
        new_text = f"{m.group(1)}{new_fm}{m.group(3)}{m.group(4)}"
        md.write_text(new_text, encoding="utf-8")
        updated += 1

    print(f"backfilled: updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

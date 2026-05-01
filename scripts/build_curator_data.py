#!/usr/bin/env python3
"""Emit _data/curator.yml from _stories/*.md.

Jekyll filters published: false out of site.stories iteration, so the
curator dashboard can't list drafts via Liquid. This script reads every
story file directly (regardless of published state), extracts the
metadata the dashboard needs, and writes a YAML data file that the
curator layout iterates instead.

Includes a gap_flag (True iff |post_created_at - source_published_at| > 7
days) so the curator can spot saves that reference articles older than
their post by more than a week.

Sorted by post_created_at descending. Idempotent.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

# Hosts whose date metadata trafilatura tends to extract poorly. Mirror of
# build_pending_data.NOISY_DATE_HOSTS — kept in sync by hand for the moment.
NOISY_DATE_HOSTS = {
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "docs.google.com",
    "github.com",
    "en.wikipedia.org",
    "wikipedia.org",
}


def host_of(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().removeprefix("www.")

REPO = Path(__file__).resolve().parent.parent
STORIES = REPO / "_stories"
OUT = REPO / "_data" / "curator.yml"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)", re.S)


def state(fm: dict) -> str:
    if fm.get("culled"):
        return "rejected"
    if fm.get("published") is False:
        return "draft"
    return "published"


def parse_iso(s) -> datetime | None:
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
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


def gap_days(post_at, pub_at) -> int | None:
    p = parse_iso(post_at)
    q = parse_iso(pub_at)
    if p is None or q is None:
        return None
    return abs((p - q).days)


def main() -> int:
    rows = []
    for md in sorted(STORIES.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            print(f"warn: {md.name} has no frontmatter; skipping", file=sys.stderr)
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        slug = fm.get("slug") or md.stem.split("-", 3)[-1]
        post_at = fm.get("post_created_at") or ""
        pub_at = fm.get("source_published_at") or ""
        gap = gap_days(post_at, pub_at)
        is_noisy = host_of(fm.get("source_url", "")) in NOISY_DATE_HOSTS
        rows.append(
            {
                "slug": slug,
                "title": fm.get("title", "(untitled)"),
                "date": str(fm.get("date", "")),
                "post_created_at": str(post_at) if post_at else "",
                "source_published_at": str(pub_at) if pub_at else "",
                "gap_days": gap,
                "gap_flag": gap is not None and gap > 7 and not is_noisy,
                "summary": fm.get("summary", ""),
                "themes": fm.get("themes") or [],
                "state": state(fm),
                "source_url": fm.get("source_url", ""),
                "source_publication": fm.get("source_publication", ""),
                "bluesky_uri": fm.get("bluesky_uri", ""),
                # Repo-relative path of the underlying story file, so the
                # curator dashboard can link drafts/rejected items straight
                # to their GitHub source for editing.
                "path": f"_stories/{md.name}",
            }
        )

    rows.sort(key=lambda r: r["post_created_at"] or r["date"], reverse=True)
    flagged = sum(1 for r in rows if r["gap_flag"])
    OUT.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(rows)} stories, {flagged} gap-flagged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

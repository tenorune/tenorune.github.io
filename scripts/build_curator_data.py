#!/usr/bin/env python3
"""Emit _data/curator.yml from _stories/*.md.

Jekyll filters published: false out of site.stories iteration, so the
curator dashboard can't list drafts via Liquid. This script reads every
story file directly (regardless of published state), extracts the
metadata the dashboard needs, and writes a YAML data file that the
curator layout iterates instead.

Sorted by date descending. Idempotent.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

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
        rows.append(
            {
                "slug": slug,
                "title": fm.get("title", "(untitled)"),
                "date": str(fm.get("date", "")),
                "summary": fm.get("summary", ""),
                "themes": fm.get("themes") or [],
                "state": state(fm),
                "source_url": fm.get("source_url", ""),
                "source_publication": fm.get("source_publication", ""),
                "bluesky_uri": fm.get("bluesky_uri", ""),
            }
        )

    rows.sort(key=lambda r: r["date"], reverse=True)
    OUT.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(rows)} stories)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

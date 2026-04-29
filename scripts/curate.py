#!/usr/bin/env python3
"""Apply a curator action to a story's frontmatter.

Actions:
  publish  →  published: true,  remove culled
  draft    →  published: false, remove culled
  reject   →  published: false, culled: true

Idempotent. Exits non-zero on bad inputs (unknown action, slug not
found). Writes the file in-place, preserving frontmatter ordering and
the body unchanged.

Usage:
  scripts/curate.py <action> <slug>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STORIES = REPO / "_stories"

VALID_ACTIONS = {"publish", "draft", "reject"}
FRONTMATTER_RE = re.compile(r"\A(---\n)(.*?)(\n---\n)(.*)", re.S)


def find_story(slug: str) -> Path | None:
    for md in STORIES.glob("*.md"):
        m = FRONTMATTER_RE.match(md.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = m.group(2)
        if re.search(rf"^slug:\s*{re.escape(slug)}\s*$", fm, re.M):
            return md
    return None


def apply_action(fm: str, action: str) -> str:
    # Strip any existing published / culled lines.
    lines = [ln for ln in fm.splitlines() if not re.match(r"^(published|culled):\s", ln)]
    if action == "publish":
        lines.append("published: true")
    elif action == "draft":
        lines.append("published: false")
    elif action == "reject":
        lines.append("published: false")
        lines.append("culled: true")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: curate.py <action> <slug>", file=sys.stderr)
        return 2
    _, action, slug = argv
    if action not in VALID_ACTIONS:
        print(f"unknown action: {action!r} (expected: {sorted(VALID_ACTIONS)})", file=sys.stderr)
        return 2

    path = find_story(slug)
    if path is None:
        print(f"no story with slug={slug!r} in {STORIES}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        print(f"{path.name}: no frontmatter", file=sys.stderr)
        return 1

    new_fm = apply_action(m.group(2), action)
    new_text = f"{m.group(1)}{new_fm}{m.group(3)}{m.group(4)}"
    if new_text == text:
        print(f"{path.name}: no change ({action})")
        return 0

    path.write_text(new_text, encoding="utf-8")
    print(f"{path.name}: applied {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

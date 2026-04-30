#!/usr/bin/env python3
"""Apply a curator action.

Story actions (target = story slug):
  publish  →  published: true,  remove culled
  draft    →  published: false, remove culled
  reject   →  published: false, culled: true

Pending-save actions (target = bluesky rkey, the last segment of the AT-URI):
  skip     →  saves_state.json status=skipped
  queue    →  saves_state.json status=queued
  unqueue  →  remove the saves_state.json entry (revert queued → no-state)

Idempotent. Exits non-zero on bad inputs (unknown action, slug/rkey not
found).

Usage:
  scripts/curate.py <action> <slug-or-rkey>
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STORIES = REPO / "_stories"
INVENTORY = REPO / "_data" / "saves_inventory.json"
STATE = REPO / "_data" / "saves_state.json"

STORY_ACTIONS = {"publish", "draft", "reject"}
PENDING_ACTIONS = {"skip", "queue", "unqueue"}
VALID_ACTIONS = STORY_ACTIONS | PENDING_ACTIONS

FRONTMATTER_RE = re.compile(r"\A(---\n)(.*?)(\n---\n)(.*)", re.S)


# ---------- story actions ----------

def find_story(slug: str) -> Path | None:
    for md in STORIES.glob("*.md"):
        m = FRONTMATTER_RE.match(md.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = m.group(2)
        if re.search(rf"^slug:\s*{re.escape(slug)}\s*$", fm, re.M):
            return md
    return None


def apply_story_action(fm: str, action: str) -> str:
    lines = [ln for ln in fm.splitlines() if not re.match(r"^(published|culled):\s", ln)]
    if action == "publish":
        lines.append("published: true")
    elif action == "draft":
        lines.append("published: false")
    elif action == "reject":
        lines.append("published: false")
        lines.append("culled: true")
    return "\n".join(lines)


STORY_ACTION_TO_STATUS = {
    "publish": "published",
    "draft":   "drafted",
    "reject":  "culled",
}


def _update_state_for_story(slug: str, status: str) -> None:
    """Mirror a story-action status onto the matching saves_state entry.

    Looks up the saves_state entry whose `story_slug` matches `slug` and
    sets its `status` to the new value (and bumps `last_action_at`). If
    no matching entry exists (e.g., the story was authored without a
    bluesky_uri) this is a silent no-op — the story file remains the
    source of truth for site visibility either way.
    """
    if not STATE.exists():
        return
    doc = json.loads(STATE.read_text(encoding="utf-8"))
    states = doc.get("states") or {}
    changed = False
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for uri, entry in states.items():
        if entry.get("story_slug") == slug:
            if entry.get("status") != status:
                entry["status"] = status
                entry["last_action_at"] = now
                changed = True
    if changed:
        doc["states"] = dict(sorted(states.items()))
        STATE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_story_action(action: str, slug: str) -> int:
    path = find_story(slug)
    if path is None:
        print(f"no story with slug={slug!r}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        print(f"{path.name}: no frontmatter", file=sys.stderr)
        return 1
    new_fm = apply_story_action(m.group(2), action)
    new_text = f"{m.group(1)}{new_fm}{m.group(3)}{m.group(4)}"
    fm_changed = new_text != text
    if fm_changed:
        path.write_text(new_text, encoding="utf-8")

    # Mirror onto saves_state regardless of frontmatter-changed (the state
    # file may have drifted from frontmatter and this is the moment to
    # reconcile).
    _update_state_for_story(slug, STORY_ACTION_TO_STATUS[action])

    if fm_changed:
        print(f"{path.name}: applied {action}")
    else:
        print(f"{path.name}: no change ({action})")
    return 0


# ---------- pending-save actions ----------

def find_uri_by_rkey(rkey: str) -> str | None:
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    for s in inv.get("saves", []):
        uri = s.get("uri", "")
        if uri.endswith(f"/{rkey}"):
            return uri
    return None


def run_pending_action(action: str, rkey: str) -> int:
    uri = find_uri_by_rkey(rkey)
    if uri is None:
        print(f"no inventory save with rkey={rkey!r}", file=sys.stderr)
        return 1

    state_doc = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"states": {}}
    states = state_doc.setdefault("states", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = states.get(uri)

    if action == "unqueue":
        if existing and existing.get("status") == "queued":
            states.pop(uri)
            changed = True
        else:
            changed = False
    else:
        target_status = action  # "skip" → "skipped" handled below
        target_status = {"skip": "skipped", "queue": "queued"}[action]
        if existing and existing.get("status") == target_status:
            changed = False
        else:
            states[uri] = {
                "first_processed_at": (existing or {}).get("first_processed_at", now),
                "last_action_at": now,
                "notes": (existing or {}).get("notes"),
                "status": target_status,
                "story_slug": (existing or {}).get("story_slug"),
            }
            changed = True

    if not changed:
        print(f"{rkey}: no change ({action})")
        return 0

    states_sorted = dict(sorted(states.items()))
    state_doc["states"] = states_sorted
    STATE.write_text(json.dumps(state_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{rkey}: applied {action}")
    return 0


# ---------- entrypoint ----------

def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: curate.py <action> <slug-or-rkey>", file=sys.stderr)
        return 2
    _, action, target = argv
    if action not in VALID_ACTIONS:
        print(f"unknown action: {action!r} (expected: {sorted(VALID_ACTIONS)})", file=sys.stderr)
        return 2

    if action in STORY_ACTIONS:
        return run_story_action(action, target)
    return run_pending_action(action, target)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

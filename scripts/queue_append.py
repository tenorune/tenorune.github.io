#!/usr/bin/env python3
"""Append one entry to _data/curator_queue.yml.

Reads action / target / issue from environment (ACTION, TARGET, ISSUE).
Used by the curate workflow so each issue submission is one append-only
write, leaving actual state mutations to the drain workflow.

Idempotent? No — duplicate clicks add duplicate entries. The drain pass
applies them in order; curate.py is itself idempotent so a duplicate is a
no-op against the new state.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

QUEUE = Path("_data/curator_queue.yml")


def main() -> int:
    action = os.environ.get("ACTION", "")
    target = os.environ.get("TARGET", "")
    issue = os.environ.get("ISSUE", "")
    if not action or not target or not issue:
        print("missing ACTION / TARGET / ISSUE in environment", file=sys.stderr)
        return 2

    queue = yaml.safe_load(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []
    queue = queue or []
    queue.append(
        {
            "action": action,
            "target": target,
            "issue": int(issue),
            "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"appended: {action} {target} (issue #{issue})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

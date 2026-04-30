#!/usr/bin/env python3
"""Drain _data/curator_queue.yml by applying every queued action in order.

The curate workflow appends pending actions to the queue file rather than
mutating state directly. This script processes the queue in a single pass:
applies each action via curate.py's logic, regenerates the curator + pending
data files, clears the queue, and prints a list of issue numbers that were
processed (consumed by the drain workflow to close them with confirmations).

Idempotent: re-running on an empty queue is a no-op. Safe to interrupt — any
applied action persists in saves_state.json / story files; the queue retains
only the actions that haven't been applied yet (we rewrite the queue at the
end, so a mid-run crash leaves the queue intact for retry).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / "_data" / "curator_queue.yml"

sys.path.insert(0, str(REPO / "scripts"))

# Import the action-router from curate.py.
from curate import run_story_action, run_pending_action, STORY_ACTIONS, PENDING_ACTIONS  # type: ignore  # noqa: E402


def apply(action: str, target: str) -> int:
    if action in STORY_ACTIONS:
        return run_story_action(action, target)
    if action in PENDING_ACTIONS:
        return run_pending_action(action, target)
    print(f"  unknown action: {action!r} (skipping)", file=sys.stderr)
    return 2


def main() -> int:
    if not QUEUE.exists():
        print("queue file missing; nothing to drain")
        return 0
    queue = yaml.safe_load(QUEUE.read_text(encoding="utf-8")) or []
    if not queue:
        print("queue empty; nothing to drain")
        return 0

    processed: list[int] = []
    failed: list[tuple[int, str]] = []
    for entry in queue:
        action = entry.get("action")
        target = entry.get("target")
        issue  = entry.get("issue")
        print(f"  applying: {action} {target} (issue #{issue})")
        rc = apply(action, target)
        if rc == 0:
            processed.append(int(issue))
        else:
            failed.append((int(issue), f"{action} {target}: rc={rc}"))

    # Regenerate data files so the curator UI reflects the new state.
    import subprocess
    subprocess.run([sys.executable, "scripts/build_curator_data.py"], cwd=REPO, check=True)
    subprocess.run([sys.executable, "scripts/build_pending_data.py"], cwd=REPO, check=True)

    # Clear the queue. (If failed entries should be retained for retry, we
    # could keep them — but failures are usually unknown rkeys / slugs that
    # won't succeed on a retry either, so clearing is the safer default.)
    QUEUE.write_text("[]\n", encoding="utf-8")

    summary = {
        "processed_issues": processed,
        "failed": failed,
        "drained_count": len(queue),
    }
    Path(REPO / ".drain_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"drained {len(queue)} actions; processed {len(processed)} issues; {len(failed)} failures")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

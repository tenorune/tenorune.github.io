"""Pytest fixtures for verify.py tests.

Each test gets a fresh, valid scaffold in a tmpdir and mutates it to
trigger the failure mode under test. Helper functions for constructing
test data live in tests/_helpers.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Make scripts/ importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
# Make tests/ importable so test files can `from _helpers import ...`.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _git_init_with_homepage(repo: Path) -> None:
    """Initialise git in the tmpdir and commit homepage assets so the
    homepage_untouched check has a HEAD to compare against."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo, check=True
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture: initial commit"],
        cwd=repo,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Build a minimal valid stories scaffold in tmp_path and return the path."""
    r = tmp_path

    # Homepage assets that verify.py compares against HEAD.
    (r / "index.html").write_text("<html>homepage</html>\n")
    (r / "style.css").write_text("body { color: black; }\n")
    (r / "CNAME").write_text("example.com\n")
    (r / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    (r / "media").mkdir()
    (r / "media" / "logo.gif").write_bytes(b"GIF89a")

    # Minimal _config.yml. With the corrected mental model, homepage files
    # are NOT in `exclude:` (they pass through verbatim because they have no
    # front matter). Only dev artifacts are excluded.
    (r / "_config.yml").write_text(
        "exclude:\n"
        "  - CLAUDE.md\n"
        "  - docs/\n"
    )

    # Empty data files.
    (r / "_data").mkdir()
    (r / "_data" / "saves_inventory.json").write_text(
        json.dumps({"fetched_at": None, "saves": []}, indent=2) + "\n"
    )
    (r / "_data" / "saves_state.json").write_text(
        json.dumps({"updated_at": None, "states": {}}, indent=2) + "\n"
    )
    (r / "_data" / "themes.yml").write_text("[]\n")

    # Empty stories collection and theme stub directory.
    (r / "_stories").mkdir()
    (r / "_stories" / ".gitkeep").write_text("")
    (r / "stories").mkdir()
    (r / "stories" / "themes").mkdir()

    _git_init_with_homepage(r)
    return r

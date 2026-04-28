"""Pre-commit invariant checks for the stories compilation project.

Each check is an independent function that takes the repo root path and
returns a (ok: bool, msg: str) tuple. The CLI runs all checks and exits
non-zero on any failure. Tests in tests/test_verify.py exercise each
check in isolation.

Section 9 of docs/superpowers/specs/2026-04-27-stories-design.md is
the spec source of truth.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

import yaml

HOMEPAGE_FILES = ["index.html", "style.css", "CNAME", "favicon.ico"]
HOMEPAGE_DIRS = ["media"]

REQUIRED_FRONTMATTER = [
    "title",
    "slug",
    "summary",
    "date",
    "themes",
    "source_url",
    "source_title",
    "source_publication",
    "bluesky_uri",
    "bluesky_saved_at",
    "published",
]


# ----- helpers -----

def _git_show_head(repo: Path, rel_path: str) -> bytes | None:
    """Return the bytes of `rel_path` at git HEAD, or None if not tracked."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=repo,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _load_yaml_frontmatter(path: Path) -> tuple[dict, str]:
    """Split a Markdown file with YAML frontmatter into (dict, body_str)."""
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    fm_text, body = parts[1], parts[2]
    return yaml.safe_load(fm_text) or {}, body


def _iter_stories(repo: Path):
    """Yield (path, frontmatter_dict, body_str) for every _stories/*.md file."""
    stories_dir = repo / "_stories"
    if not stories_dir.exists():
        return
    for p in sorted(stories_dir.glob("*.md")):
        fm, body = _load_yaml_frontmatter(p)
        yield p, fm, body


def _load_themes(repo: Path) -> list[dict]:
    yml_path = repo / "_data" / "themes.yml"
    if not yml_path.exists():
        return []
    data = yaml.safe_load(yml_path.read_text())
    return data or []


# ----- checks -----

def check_homepage_untouched(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for f in HOMEPAGE_FILES:
        head = _git_show_head(repo, f)
        if head is None:
            continue  # not tracked yet
        actual = (repo / f).read_bytes() if (repo / f).exists() else b""
        if head != actual:
            failures.append(f"{f} differs from HEAD")
    for d in HOMEPAGE_DIRS:
        dpath = repo / d
        if not dpath.exists():
            continue
        for child in sorted(dpath.rglob("*")):
            if not child.is_file():
                continue
            rel = child.relative_to(repo).as_posix()
            head = _git_show_head(repo, rel)
            if head is None:
                continue
            if head != child.read_bytes():
                failures.append(f"{rel} differs from HEAD")
    if failures:
        return False, "homepage_untouched: " + "; ".join(failures)
    return True, "homepage_untouched: OK"


def check_theme_references_resolve(repo: Path) -> tuple[bool, str]:
    theme_slugs = {t.get("slug") for t in _load_themes(repo)}
    failures: list[str] = []
    for path, fm, _ in _iter_stories(repo):
        for slug in fm.get("themes", []) or []:
            if slug not in theme_slugs:
                failures.append(f"{path.name} references unknown theme '{slug}'")
    if failures:
        return False, "theme_references_resolve: " + "; ".join(failures)
    return True, "theme_references_resolve: OK"


def check_theme_stubs_exist(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for theme in _load_themes(repo):
        slug = theme.get("slug")
        if not slug:
            continue
        idx = repo / "stories" / "themes" / slug / "index.md"
        all_md = repo / "stories" / "themes" / slug / "all.md"
        if not idx.exists():
            failures.append(f"missing stub: stories/themes/{slug}/index.md")
        if not all_md.exists():
            failures.append(f"missing stub: stories/themes/{slug}/all.md")
    if failures:
        return False, "theme_stubs_exist: " + "; ".join(failures)
    return True, "theme_stubs_exist: OK"


def check_hero_alt_required(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for path, fm, _ in _iter_stories(repo):
        if fm.get("hero_image") and not fm.get("hero_image_alt"):
            slug = fm.get("slug", path.stem)
            failures.append(f"{slug}: hero_image set but hero_image_alt missing")
    if failures:
        return False, "hero_alt_required: " + "; ".join(failures)
    return True, "hero_alt_required: OK"


def check_inline_image_alt(repo: Path) -> tuple[bool, str]:
    """Soft warning: empty alt text in inline images. Returns ok=True even on
    findings, with a non-empty message describing them."""
    findings: list[str] = []
    pattern = re.compile(r"!\[\]\(")
    for path, _, body in _iter_stories(repo):
        if pattern.search(body):
            findings.append(f"{path.name} contains image with empty alt")
    if findings:
        return True, "inline_image_alt: WARN empty alt in: " + "; ".join(findings)
    return True, "inline_image_alt: OK"


def check_state_consistency(repo: Path) -> tuple[bool, str]:
    state_path = repo / "_data" / "saves_state.json"
    if not state_path.exists():
        return True, "state_consistency: OK (no state file)"
    state = json.loads(state_path.read_text()).get("states", {})
    story_slugs = {fm.get("slug") for _, fm, _ in _iter_stories(repo)}
    failures: list[str] = []
    for uri, entry in state.items():
        if entry.get("status") in {"drafted", "polished", "published"}:
            slug = entry.get("story_slug")
            if slug not in story_slugs:
                failures.append(f"{uri[:40]}... refs missing slug '{slug}'")
    if failures:
        return False, "state_consistency: " + "; ".join(failures)
    return True, "state_consistency: OK"


def check_state_inventory_cross_reference(repo: Path) -> tuple[bool, str]:
    state_path = repo / "_data" / "saves_state.json"
    inv_path = repo / "_data" / "saves_inventory.json"
    if not state_path.exists() or not inv_path.exists():
        return True, "state_inventory_cross_reference: OK (file(s) missing)"
    state_uris = set(json.loads(state_path.read_text()).get("states", {}).keys())
    inv_uris = {s.get("uri") for s in json.loads(inv_path.read_text()).get("saves", [])}
    orphans = state_uris - inv_uris
    if orphans:
        return False, "state_inventory_cross_reference: orphan URIs in state: " + ", ".join(sorted(orphans))
    return True, "state_inventory_cross_reference: OK"


def check_frontmatter_contract(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    for path, fm, _ in _iter_stories(repo):
        for field in REQUIRED_FRONTMATTER:
            if field not in fm or fm.get(field) in (None, ""):
                failures.append(f"{path.name}: missing required field '{field}'")
    if failures:
        return False, "frontmatter_contract: " + "; ".join(failures)
    return True, "frontmatter_contract: OK"


def check_slug_filename_match(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    name_re = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$")
    for path, fm, _ in _iter_stories(repo):
        m = name_re.match(path.name)
        if not m:
            failures.append(f"{path.name}: filename does not match YYYY-MM-DD-<slug>.md pattern")
            continue
        file_slug = m.group(1)
        fm_slug = fm.get("slug")
        if fm_slug != file_slug:
            failures.append(f"{path.name}: filename slug '{file_slug}' != frontmatter slug '{fm_slug}'")
    if failures:
        return False, "slug_filename_match: " + "; ".join(failures)
    return True, "slug_filename_match: OK"


def check_pandoc_clean(repo: Path) -> tuple[bool, str]:
    """Body Markdown should not contain Liquid tokens — even though
    render_with_liquid: false makes Jekyll skip Liquid in bodies, the
    Pandoc export pipeline (deferred) prefers truly Liquid-free input."""
    failures: list[str] = []
    for path, fm, body in _iter_stories(repo):
        slug = fm.get("slug", path.stem)
        if "{{" in body or "{%" in body:
            failures.append(f"{slug}: body contains Liquid braces")
    if failures:
        return False, "pandoc_clean: " + "; ".join(failures)
    return True, "pandoc_clean: OK"


def check_article_pending_flag(repo: Path) -> tuple[bool, str]:
    """If a story's source_url is the same as an inventory entry's external
    embed URL AND that entry has article_fetch_error set, the story should
    declare `source_article_pending: true` in its frontmatter so the
    curator can find stories awaiting manual hydration."""
    inv_path = repo / "_data" / "saves_inventory.json"
    if not inv_path.exists():
        return True, "article_pending_flag: OK (no inventory)"
    inv = json.loads(inv_path.read_text())
    failed_urls = set()
    for s in inv.get("saves", []):
        if not s.get("article_fetch_error"):
            continue
        url = (s.get("embed") or {}).get("url")
        if url:
            failed_urls.add(url)
    failures: list[str] = []
    for path, fm, _ in _iter_stories(repo):
        url = fm.get("source_url")
        if url and url in failed_urls and not fm.get("source_article_pending"):
            failures.append(
                f"{path.name}: source_url is in inventory.article_fetch_error "
                f"but story lacks source_article_pending: true"
            )
    if failures:
        return False, "article_pending_flag: " + "; ".join(failures)
    return True, "article_pending_flag: OK"


# ----- runner -----

CHECKS: list[Callable[[Path], tuple[bool, str]]] = [
    check_homepage_untouched,
    check_theme_references_resolve,
    check_theme_stubs_exist,
    check_hero_alt_required,
    check_inline_image_alt,
    check_state_consistency,
    check_state_inventory_cross_reference,
    check_frontmatter_contract,
    check_slug_filename_match,
    check_pandoc_clean,
    check_article_pending_flag,
]


def run_all(repo: Path) -> tuple[bool, str]:
    failures: list[str] = []
    warnings: list[str] = []
    for check in CHECKS:
        ok, msg = check(repo)
        if not ok:
            failures.append(msg)
        elif "WARN" in msg:
            warnings.append(msg)
    if failures:
        return False, "\n".join(failures + warnings)
    return True, "\n".join(warnings) if warnings else "OK"


def _summary(repo: Path) -> str:
    n_stories = sum(1 for _ in _iter_stories(repo))
    n_themes = len(_load_themes(repo))
    inv_path = repo / "_data" / "saves_inventory.json"
    n_inv = 0
    if inv_path.exists():
        n_inv = len(json.loads(inv_path.read_text()).get("saves", []))
    return f"verify: OK ({n_stories} stories, {n_themes} themes, {n_inv} inventory entries)"


def main() -> int:
    repo = Path.cwd()
    ok, msg = run_all(repo)
    if not ok:
        print(msg, file=sys.stderr)
        return 1
    if msg and msg != "OK":
        print(msg)  # warnings
    print(_summary(repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests for scripts/verify.py — one test per check (Section 9 of spec)."""
from __future__ import annotations

# sys.path is set up by conftest.py so verify and _helpers are importable.
import verify  # noqa: E402

from _helpers import (  # noqa: E402
    add_inventory_entry,
    add_story,
    add_theme,
    set_state,
)


# ---------- baseline: a valid scaffold passes ----------

def test_baseline_valid_scaffold_passes(repo):
    ok, msg = verify.run_all(repo)
    assert ok, f"valid scaffold should pass; got: {msg}"


# ---------- homepage_untouched ----------

def test_homepage_untouched_passes_when_unchanged(repo):
    ok, _ = verify.check_homepage_untouched(repo)
    assert ok


def test_homepage_untouched_fails_when_modified(repo):
    (repo / "index.html").write_text("<html>tampered</html>\n")
    ok, msg = verify.check_homepage_untouched(repo)
    assert not ok
    assert "index.html" in msg


# ---------- theme_references_resolve ----------

def test_theme_references_resolve_passes(repo):
    add_theme(repo, "climate", "climate", "Test description.")
    add_story(repo, slug="s1", themes=["climate"])
    ok, _ = verify.check_theme_references_resolve(repo)
    assert ok


def test_theme_references_resolve_fails_on_unknown_theme(repo):
    add_story(repo, slug="s1", themes=["typo-theme"])
    ok, msg = verify.check_theme_references_resolve(repo)
    assert not ok
    assert "typo-theme" in msg


# ---------- theme_stubs_exist ----------

def test_theme_stubs_exist_passes_when_both_present(repo):
    add_theme(repo, "climate", "climate", "desc")
    ok, _ = verify.check_theme_stubs_exist(repo)
    assert ok


def test_theme_stubs_exist_fails_when_index_missing(repo):
    add_theme(repo, "climate", "climate", "desc")
    (repo / "stories" / "themes" / "climate" / "index.md").unlink()
    ok, msg = verify.check_theme_stubs_exist(repo)
    assert not ok
    assert "climate" in msg


def test_theme_stubs_exist_fails_when_all_missing(repo):
    add_theme(repo, "climate", "climate", "desc")
    (repo / "stories" / "themes" / "climate" / "all.md").unlink()
    ok, msg = verify.check_theme_stubs_exist(repo)
    assert not ok


# ---------- hero_alt_required ----------

def test_hero_alt_required_passes_with_alt(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"], hero=True)
    ok, _ = verify.check_hero_alt_required(repo)
    assert ok


def test_hero_alt_required_fails_when_alt_missing(repo):
    add_theme(repo, "x", "x", "d")
    p = add_story(repo, slug="s1", themes=["x"], hero=True)
    text = p.read_text()
    text = text.replace('hero_image_alt: "Alt text"\n', "")
    p.write_text(text)
    ok, msg = verify.check_hero_alt_required(repo)
    assert not ok
    assert "s1" in msg


# ---------- inline_image_alt ----------

def test_inline_image_alt_warns_on_empty(repo):
    add_theme(repo, "x", "x", "d")
    add_story(
        repo,
        slug="s1",
        themes=["x"],
        body="Body.\n\n![](/assets/stories/s1/figure-1.jpg)\n",
    )
    ok, msg = verify.check_inline_image_alt(repo)
    # Soft warning — should still pass, but the message reports it.
    assert ok
    assert "empty alt" in msg.lower() or "warn" in msg.lower()


# ---------- state_consistency ----------

def test_state_consistency_passes_when_story_exists(repo):
    add_theme(repo, "x", "x", "d")
    add_inventory_entry(repo, "at://uri/1")
    add_story(repo, slug="s1", themes=["x"])
    set_state(repo, "at://uri/1", "drafted", "s1")
    ok, _ = verify.check_state_consistency(repo)
    assert ok


def test_state_consistency_fails_when_story_missing(repo):
    add_inventory_entry(repo, "at://uri/1")
    set_state(repo, "at://uri/1", "drafted", "ghost-slug")
    ok, msg = verify.check_state_consistency(repo)
    assert not ok
    assert "ghost-slug" in msg


# ---------- state_inventory_cross_reference ----------

def test_state_inventory_cross_reference_passes(repo):
    add_inventory_entry(repo, "at://uri/1")
    set_state(repo, "at://uri/1", "skipped", None)
    ok, _ = verify.check_state_inventory_cross_reference(repo)
    assert ok


def test_state_inventory_cross_reference_fails_on_orphan_state(repo):
    set_state(repo, "at://uri/orphan", "skipped", None)
    ok, msg = verify.check_state_inventory_cross_reference(repo)
    assert not ok
    assert "at://uri/orphan" in msg


# ---------- frontmatter_contract ----------

def test_frontmatter_contract_passes_for_complete_story(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"])
    ok, _ = verify.check_frontmatter_contract(repo)
    assert ok


def test_frontmatter_contract_fails_when_required_field_missing(repo):
    add_theme(repo, "x", "x", "d")
    p = add_story(repo, slug="s1", themes=["x"])
    p.write_text(p.read_text().replace('source_publication: "Example Publication"\n', ""))
    ok, msg = verify.check_frontmatter_contract(repo)
    assert not ok
    assert "source_publication" in msg


# ---------- slug_filename_match ----------

def test_slug_filename_match_passes(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="matching-slug", themes=["x"])
    ok, _ = verify.check_slug_filename_match(repo)
    assert ok


def test_slug_filename_match_fails_on_mismatch(repo):
    add_theme(repo, "x", "x", "d")
    p = add_story(repo, slug="real-slug", themes=["x"])
    new_path = p.parent / "2026-04-12-different-slug.md"
    p.rename(new_path)
    ok, msg = verify.check_slug_filename_match(repo)
    assert not ok
    assert "different-slug" in msg or "real-slug" in msg


# ---------- pandoc_clean ----------

def test_pandoc_clean_passes_for_plain_markdown(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"], body="Plain paragraph.\n")
    ok, _ = verify.check_pandoc_clean(repo)
    assert ok


def test_pandoc_clean_fails_on_liquid_braces(repo):
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"], body="Body with {{ liquid }}.\n")
    ok, msg = verify.check_pandoc_clean(repo)
    assert not ok
    assert "s1" in msg


# ---------- article_pending_flag ----------

def _add_failed_inventory_entry(repo, url: str):
    """Inject one inventory entry whose article fetch failed."""
    import json
    inv_path = repo / "_data" / "saves_inventory.json"
    inv = json.loads(inv_path.read_text())
    inv["saves"].append({
        "uri": "at://did:plc:fake/app.bsky.feed.post/abc",
        "saved_at": "2026-04-12T18:31:00Z",
        "post_text": "p",
        "embed": {"type": "external", "url": url, "title": "t", "description": "d"},
        "author": {"handle": "h", "display_name": "H", "did": "did:plc:fake"},
        "article_fetch_error": "http_403",
    })
    inv_path.write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")


def test_article_pending_flag_passes_when_flag_set(repo):
    add_theme(repo, "x", "x", "d")
    url = "https://example.com/article"
    _add_failed_inventory_entry(repo, url)
    p = add_story(repo, slug="s1", themes=["x"])
    text = p.read_text()
    text = text.replace(
        'source_url: "https://example.org/article"',
        f'source_url: "{url}"\nsource_article_pending: true',
    )
    p.write_text(text)
    ok, _ = verify.check_article_pending_flag(repo)
    assert ok


def test_article_pending_flag_fails_when_flag_missing(repo):
    add_theme(repo, "x", "x", "d")
    url = "https://example.com/article"
    _add_failed_inventory_entry(repo, url)
    p = add_story(repo, slug="s1", themes=["x"])
    text = p.read_text()
    text = text.replace(
        'source_url: "https://example.org/article"',
        f'source_url: "{url}"',
    )
    p.write_text(text)
    ok, msg = verify.check_article_pending_flag(repo)
    assert not ok
    assert "source_article_pending" in msg


def test_article_pending_flag_passes_when_url_succeeded(repo):
    """A story pointing at an inventory URL with NO fetch error doesn't
    need the flag (and shouldn't be expected to have it)."""
    add_theme(repo, "x", "x", "d")
    add_story(repo, slug="s1", themes=["x"])
    ok, _ = verify.check_article_pending_flag(repo)
    assert ok

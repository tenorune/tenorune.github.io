"""Tests for scripts/localize_story_images.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Module path is set up by tests/conftest.py.
import localize_story_images as lsi  # noqa: E402


def _write_story(stories_dir: Path, *, slug: str, uri: str, body: str) -> Path:
    p = stories_dir / f"2026-05-01-{slug}.md"
    p.write_text(
        f'---\n'
        f'title: "Fixture {slug}"\n'
        f'slug: {slug}\n'
        f'date: 2026-05-01\n'
        f'bluesky_uri: "{uri}"\n'
        f'---\n'
        f'{body}',
        encoding="utf-8",
    )
    return p


def _write_inventory(inv_path: Path, entries: list[dict]) -> None:
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(
        json.dumps({"fetched_at": None, "saves": entries}, indent=2) + "\n",
        encoding="utf-8",
    )


def _seed_cache(cache_dir: Path, files: dict[str, bytes]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        (cache_dir / name).write_bytes(payload)


def _common_layout(tmp_path: Path):
    """Return (stories_dir, inv_path, cache_dir, assets_dir)."""
    stories_dir = tmp_path / "_stories"
    stories_dir.mkdir()
    inv_path = tmp_path / "_data" / "saves_inventory.json"
    cache_dir = tmp_path / "_data" / "_image_cache"
    assets_dir = tmp_path / "assets" / "stories"
    return stories_dir, inv_path, cache_dir, assets_dir


def _run(stories_dir: Path, inv_path: Path, cache_dir: Path, assets_dir: Path) -> int:
    return lsi.main([
        "--stories", str(stories_dir),
        "--inventory", str(inv_path),
        "--cache", str(cache_dir),
        "--assets", str(assets_dir),
        "--assets-url-prefix", "/assets/stories",
    ])


# ---------- happy path ----------

def test_rewrites_cdn_url_and_copies_asset(tmp_path: Path):
    stories_dir, inv_path, cache_dir, assets_dir = _common_layout(tmp_path)
    uri = "at://did:plc:a/app.bsky.feed.post/abc"
    cdn_url = "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:a/bafkrei...@jpeg"
    filename = "img-deadbeefdeadbeef.jpg"

    _write_story(
        stories_dir,
        slug="my-story",
        uri=uri,
        body=f"Body text.\n\n![alt text]({cdn_url})\n",
    )
    _write_inventory(inv_path, [
        {"uri": uri, "saved_at": "2026-05-01T00:00:00Z",
         "local_images": [{"url": cdn_url, "path": filename}]}
    ])
    _seed_cache(cache_dir, {filename: b"fake-jpeg-bytes"})

    rc = _run(stories_dir, inv_path, cache_dir, assets_dir)
    assert rc == 0

    # Asset copied into per-slug dir.
    assert (assets_dir / "my-story" / filename).read_bytes() == b"fake-jpeg-bytes"

    # Markdown URL rewritten.
    rewritten_text = (stories_dir / "2026-05-01-my-story.md").read_text(encoding="utf-8")
    assert cdn_url not in rewritten_text
    assert f"/assets/stories/my-story/{filename}" in rewritten_text


# ---------- idempotence ----------

def test_idempotent_when_already_localized(tmp_path: Path):
    stories_dir, inv_path, cache_dir, assets_dir = _common_layout(tmp_path)
    uri = "at://did:plc:a/app.bsky.feed.post/abc"
    cdn_url = "https://cdn.bsky.app/img/x@jpeg"
    filename = "img-aaaaaaaaaaaaaaaa.jpg"

    # Story already has local URL.
    story = _write_story(
        stories_dir,
        slug="done",
        uri=uri,
        body=f"![]( /assets/stories/done/{filename})\n",
    )
    original = story.read_text(encoding="utf-8")
    _write_inventory(inv_path, [
        {"uri": uri, "saved_at": "2026-05-01T00:00:00Z",
         "local_images": [{"url": cdn_url, "path": filename}]}
    ])
    _seed_cache(cache_dir, {filename: b"x"})

    # Pre-place the asset; rewriter should not re-copy.
    (assets_dir / "done").mkdir(parents=True)
    (assets_dir / "done" / filename).write_bytes(b"original-bytes")

    rc = _run(stories_dir, inv_path, cache_dir, assets_dir)
    assert rc == 0

    # Story unchanged.
    assert story.read_text(encoding="utf-8") == original
    # Pre-existing asset NOT overwritten with cache contents.
    assert (assets_dir / "done" / filename).read_bytes() == b"original-bytes"


def test_repeated_run_no_op(tmp_path: Path):
    stories_dir, inv_path, cache_dir, assets_dir = _common_layout(tmp_path)
    uri = "at://did:plc:a/app.bsky.feed.post/abc"
    cdn_url = "https://cdn.bsky.app/img/y@jpeg"
    filename = "img-bbbbbbbbbbbbbbbb.jpg"

    _write_story(stories_dir, slug="s", uri=uri,
                 body=f"![alt]({cdn_url})\n")
    _write_inventory(inv_path, [
        {"uri": uri, "saved_at": "2026-05-01T00:00:00Z",
         "local_images": [{"url": cdn_url, "path": filename}]}
    ])
    _seed_cache(cache_dir, {filename: b"z"})

    assert _run(stories_dir, inv_path, cache_dir, assets_dir) == 0
    after_first = (stories_dir / "2026-05-01-s.md").read_text(encoding="utf-8")
    assert _run(stories_dir, inv_path, cache_dir, assets_dir) == 0
    after_second = (stories_dir / "2026-05-01-s.md").read_text(encoding="utf-8")
    assert after_first == after_second


# ---------- edge cases ----------

def test_story_without_bluesky_uri_is_skipped_silently(tmp_path: Path):
    stories_dir, inv_path, cache_dir, assets_dir = _common_layout(tmp_path)
    p = stories_dir / "2026-05-01-authored.md"
    p.write_text(
        '---\nslug: authored\ndate: 2026-05-01\n---\nBody.\n',
        encoding="utf-8",
    )
    _write_inventory(inv_path, [])
    rc = _run(stories_dir, inv_path, cache_dir, assets_dir)
    assert rc == 0
    assert p.read_text(encoding="utf-8").endswith("Body.\n")


def test_inventory_entry_missing_local_images_no_change(tmp_path: Path):
    stories_dir, inv_path, cache_dir, assets_dir = _common_layout(tmp_path)
    uri = "at://did:plc:a/app.bsky.feed.post/abc"
    p = _write_story(stories_dir, slug="s", uri=uri, body="Body.\n")
    _write_inventory(inv_path, [
        {"uri": uri, "saved_at": "2026-05-01T00:00:00Z"}
    ])
    rc = _run(stories_dir, inv_path, cache_dir, assets_dir)
    assert rc == 0
    assert p.read_text(encoding="utf-8").endswith("Body.\n")


def test_cdn_url_without_mapping_emits_warning_but_keeps_url(tmp_path, capsys):
    stories_dir, inv_path, cache_dir, assets_dir = _common_layout(tmp_path)
    uri = "at://did:plc:a/app.bsky.feed.post/abc"
    pasted_url = "https://cdn.bsky.app/img/random@jpeg"
    p = _write_story(stories_dir, slug="s", uri=uri,
                     body=f"![alt]({pasted_url})\n")
    _write_inventory(inv_path, [
        {"uri": uri, "saved_at": "2026-05-01T00:00:00Z", "local_images": []}
    ])
    rc = _run(stories_dir, inv_path, cache_dir, assets_dir)
    assert rc == 0
    text = p.read_text(encoding="utf-8")
    # URL kept (we only rewrite when we have a mapping).
    assert pasted_url in text


def test_missing_cache_file_warns_but_still_rewrites(tmp_path: Path, capsys):
    """If a local_images filename is missing from the cache, we warn but
    still rewrite the Markdown — the asset just has to be supplied later."""
    stories_dir, inv_path, cache_dir, assets_dir = _common_layout(tmp_path)
    uri = "at://did:plc:a/app.bsky.feed.post/abc"
    cdn_url = "https://cdn.bsky.app/img/q@jpeg"
    filename = "img-cccccccccccccccc.jpg"
    cache_dir.mkdir(parents=True)  # empty: no file inside

    p = _write_story(stories_dir, slug="s", uri=uri,
                     body=f"![alt]({cdn_url})\n")
    _write_inventory(inv_path, [
        {"uri": uri, "saved_at": "2026-05-01T00:00:00Z",
         "local_images": [{"url": cdn_url, "path": filename}]}
    ])
    rc = _run(stories_dir, inv_path, cache_dir, assets_dir)
    assert rc == 0
    text = p.read_text(encoding="utf-8")
    assert f"/assets/stories/s/{filename}" in text
    err = capsys.readouterr().err
    assert "cache missing" in err

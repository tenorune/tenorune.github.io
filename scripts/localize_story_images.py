#!/usr/bin/env python3
"""Localize CDN image references in `_stories/*.md` using the `local_images`
field added to inventory entries by `bsky-saves hydrate images` (v0.2+).

This script picks up where bsky-saves' v0.2 ingestion leaves off:

  bsky-saves v0.2 (in fetch-images.yml):
    - Downloads images into a flat cache (e.g. `_data/_image_cache/`).
    - Records each downloaded image as `local_images: [{url, path}, ...]`
      on the matching inventory entry.

  This script (after that):
    - For each `_stories/*.md`, looks up the matching inventory entry by
      `bluesky_uri` and reads its `local_images`.
    - Copies each cached image into `assets/stories/<slug>/<filename>`
      (per-slug subdir is the Jekyll-side layout convention).
    - Rewrites every `![alt](https://cdn.bsky.app/...)` Markdown reference
      whose URL has a matching `local_images.url` to
      `/assets/stories/<slug>/<filename>`.

Idempotent. Safe to re-run. Markdown URLs that have already been
localised are left alone; cached files that are already present at the
slug-scoped destination aren't re-copied.

The `bsky-saves` package is intentionally format-agnostic in v0.2 — it
captures images and records the URL→path mapping but does not write
into Markdown. That format-specific layer is here, in this script.

CLI:
  scripts/localize_story_images.py
      [--stories DIR]    default: _stories/
      [--inventory PATH] default: _data/saves_inventory.json
      [--cache DIR]      default: _data/_image_cache/
      [--assets DIR]     default: assets/stories/
      [--assets-url-prefix PREFIX]
                         default: /assets/stories
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DEFAULT_STORIES = REPO / "_stories"
DEFAULT_INVENTORY = REPO / "_data" / "saves_inventory.json"
DEFAULT_CACHE = REPO / "_data" / "_image_cache"
DEFAULT_ASSETS = REPO / "assets" / "stories"
DEFAULT_ASSETS_URL_PREFIX = "/assets/stories"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)", re.S)
SLUG_RE = re.compile(r'^slug:\s*(\S+)\s*$', re.M)
URI_RE = re.compile(r'^bluesky_uri:\s*"?(at://[^"\s]+)"?\s*$', re.M)

# Markdown image syntax: ![alt](url). Matches only cdn.bsky.app URLs so
# already-localised refs (which point at /assets/...) are left untouched.
CDN_IMG_RE = re.compile(
    r'(?P<head>!\[[^\]]*\]\()'
    r'(?P<url>https://cdn\.bsky\.app/[^)\s]+)'
    r'(?P<tail>\))'
)


def parse_frontmatter(text: str) -> tuple[str, str] | None:
    """Return (frontmatter_text, body_text) or None if no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    return m.group(1), m.group(2)


def index_inventory_by_uri(inventory_path: Path) -> dict[str, dict]:
    inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    return {s["uri"]: s for s in inv.get("saves", [])}


def url_to_path_map(entry: dict) -> dict[str, str]:
    """Return {cdn_url: local_filename} from an entry's local_images."""
    out: dict[str, str] = {}
    for img in entry.get("local_images") or []:
        url = img.get("url")
        path = img.get("path")
        if url and path:
            out[url] = path
    return out


def copy_cached_assets(
    filenames: set[str],
    cache_dir: Path,
    slug_assets_dir: Path,
) -> tuple[int, list[str]]:
    """Copy each cached image into the slug-scoped assets directory.

    Returns (copied, missing_filenames). `copied` counts only files that
    were actually copied this run; pre-existing destinations are skipped.
    """
    copied = 0
    missing: list[str] = []
    for filename in filenames:
        src = cache_dir / filename
        if not src.exists():
            missing.append(filename)
            continue
        dst = slug_assets_dir / filename
        if dst.exists():
            continue
        slug_assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied, missing


def rewrite_markdown_body(
    body: str,
    url_to_filename: dict[str, str],
    slug: str,
    assets_url_prefix: str,
) -> tuple[str, int, list[str]]:
    """Rewrite ![alt](https://cdn.bsky.app/...) refs whose URL is mapped.

    Returns (new_body, rewritten_count, unmapped_urls).
    """
    rewritten = 0
    unmapped: list[str] = []

    def replace(match: re.Match) -> str:
        nonlocal rewritten
        url = match.group("url")
        filename = url_to_filename.get(url)
        if filename is None:
            unmapped.append(url)
            return match.group(0)
        local_url = f"{assets_url_prefix.rstrip('/')}/{slug}/{filename}"
        rewritten += 1
        return match.group("head") + local_url + match.group("tail")

    new_body = CDN_IMG_RE.sub(replace, body)
    return new_body, rewritten, unmapped


def localize_story(
    story_path: Path,
    *,
    inventory_by_uri: dict[str, dict],
    cache_dir: Path,
    assets_dir: Path,
    assets_url_prefix: str,
) -> tuple[int, int, list[str]]:
    """Process one story file. Returns (copied, rewritten, warnings)."""
    text = story_path.read_text(encoding="utf-8")
    parsed = parse_frontmatter(text)
    if not parsed:
        return 0, 0, [f"{story_path.name}: no frontmatter"]
    fm, body = parsed

    slug_m = SLUG_RE.search(fm)
    uri_m = URI_RE.search(fm)
    if not slug_m:
        return 0, 0, [f"{story_path.name}: no slug in frontmatter"]
    if not uri_m:
        # Not all stories have a bluesky_uri (e.g. authored from scratch).
        # Without a URI we can't look up local_images; nothing to do.
        return 0, 0, []
    slug = slug_m.group(1)
    uri = uri_m.group(1)

    entry = inventory_by_uri.get(uri)
    if entry is None:
        return 0, 0, [f"{story_path.name}: uri {uri} not in inventory"]

    url_to_filename = url_to_path_map(entry)

    # bsky-saves v0.2 enumerates every image URL the inventory entry
    # references — including embed thumbs, thread-reply images, and
    # quoted-post images. Most of those aren't referenced in the
    # rendered story body. We only localize what the body actually
    # uses, matching v0.1's behavior. The rest stay in the cache.
    referenced_urls: list[str] = [m.group("url") for m in CDN_IMG_RE.finditer(body)]
    needed: dict[str, str] = {}
    unmapped: list[str] = []
    for url in referenced_urls:
        fn = url_to_filename.get(url)
        if fn is None:
            unmapped.append(url)
        else:
            needed[url] = fn

    warnings: list[str] = []
    for url in unmapped:
        warnings.append(
            f"{story_path.name}: body has cdn.bsky.app URL with no local_images mapping: {url[:80]}"
        )

    if not needed:
        # Body already-localized (no cdn URLs) or no matching inventory
        # data — nothing to do here. Don't touch the slug assets dir.
        return 0, 0, warnings

    slug_assets_dir = assets_dir / slug
    copied, missing = copy_cached_assets(set(needed.values()), cache_dir, slug_assets_dir)
    for filename in missing:
        warnings.append(f"{story_path.name}: cache missing {filename}")

    new_body, rewritten, _unmapped_in_rewrite = rewrite_markdown_body(
        body, needed, slug, assets_url_prefix
    )

    if new_body != body:
        new_text = f"---\n{fm}\n---\n{new_body}"
        story_path.write_text(new_text, encoding="utf-8")

    return copied, rewritten, warnings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--stories", type=Path, default=DEFAULT_STORIES)
    p.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    p.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    p.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    p.add_argument(
        "--assets-url-prefix",
        default=DEFAULT_ASSETS_URL_PREFIX,
        help="Root-relative URL prefix that replaces cdn.bsky.app URLs.",
    )
    args = p.parse_args(argv)

    if not args.stories.exists():
        print(f"localize: no {args.stories} directory; nothing to do", file=sys.stderr)
        return 0

    inventory_by_uri = index_inventory_by_uri(args.inventory)

    total_copied = 0
    total_rewritten = 0
    total_warnings = 0
    for story_path in sorted(args.stories.glob("*.md")):
        copied, rewritten, warnings = localize_story(
            story_path,
            inventory_by_uri=inventory_by_uri,
            cache_dir=args.cache,
            assets_dir=args.assets,
            assets_url_prefix=args.assets_url_prefix,
        )
        total_copied += copied
        total_rewritten += rewritten
        for w in warnings:
            print(f"  WARN {w}", file=sys.stderr)
            total_warnings += 1

    print(
        f"localize: copied {total_copied} assets, "
        f"rewrote {total_rewritten} refs, {total_warnings} warnings",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

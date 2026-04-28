"""Test helpers for constructing fixture stories, themes, state."""
from __future__ import annotations

import json
from pathlib import Path


def add_theme(repo: Path, slug: str, label: str, description: str) -> None:
    """Append a theme to themes.yml and create both stub files."""
    themes_yaml = repo / "_data" / "themes.yml"
    existing = themes_yaml.read_text()
    entry = (
        f"- slug: {slug}\n"
        f"  label: {label}\n"
        f"  description: \"{description}\"\n"
    )
    new = (entry if existing.strip() == "[]" else existing + entry)
    themes_yaml.write_text(new)
    theme_dir = repo / "stories" / "themes" / slug
    theme_dir.mkdir(parents=True, exist_ok=True)
    (theme_dir / "index.md").write_text(
        f"---\nlayout: theme_list\npermalink: /stories/themes/{slug}/\n"
        f"theme_slug: {slug}\n---\n"
    )
    (theme_dir / "all.md").write_text(
        f"---\nlayout: theme_compilation\n"
        f"permalink: /stories/themes/{slug}/all/\ntheme_slug: {slug}\n---\n"
    )


def add_story(
    repo: Path,
    *,
    slug: str = "fixture-story",
    saved_at: str = "2026-04-12T18:31:00Z",
    themes: list[str] | None = None,
    published: bool = True,
    hero: bool = False,
    body: str = "Synopsis paragraph.\n",
) -> Path:
    """Write a minimal valid story file and return its path."""
    themes = themes or []
    fname = f"{saved_at[:10]}-{slug}.md"
    path = repo / "_stories" / fname

    fm: list[str] = [
        "---",
        f'title: "Fixture {slug}"',
        f"slug: {slug}",
        'summary: "One-sentence summary."',
        f"date: {saved_at[:10]}",
        f"themes: [{', '.join(themes)}]",
        'source_url: "https://example.org/article"',
        'source_title: "Original article"',
        'source_publication: "Example Publication"',
        'bluesky_uri: "at://did:plc:abc.../app.bsky.feed.post/abc"',
        f"bluesky_saved_at: {saved_at}",
    ]
    if hero:
        fm.append(f"hero_image: /assets/stories/{slug}/hero.jpg")
        fm.append('hero_image_alt: "Alt text"')
    fm.append(f"published: {'true' if published else 'false'}")
    fm.append("---")
    fm.append("")
    fm.append(body)

    path.write_text("\n".join(fm))
    return path


def set_state(repo: Path, uri: str, status: str, story_slug: str | None) -> None:
    """Write an entry into saves_state.json."""
    state_path = repo / "_data" / "saves_state.json"
    state = json.loads(state_path.read_text())
    state["states"][uri] = {
        "status": status,
        "story_slug": story_slug,
        "first_processed_at": "2026-04-15T20:00:00Z",
        "last_action_at": "2026-04-15T20:00:00Z",
    }
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def add_inventory_entry(repo: Path, uri: str) -> None:
    """Append a minimal entry to saves_inventory.json."""
    inv_path = repo / "_data" / "saves_inventory.json"
    inv = json.loads(inv_path.read_text())
    inv["saves"].append(
        {
            "uri": uri,
            "saved_at": "2026-04-12T18:31:00Z",
            "post_text": "post text",
            "embed": {
                "type": "external",
                "url": "https://example.org/article",
                "title": "title",
                "description": "desc",
            },
            "author": {
                "handle": "h.bsky.social",
                "display_name": "name",
                "did": "did:plc:abc",
            },
        }
    )
    inv_path.write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")

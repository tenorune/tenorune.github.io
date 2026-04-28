"""Localize CDN image references in story files.

Scans every `_stories/*.md` file for inline image references whose URL
points at `cdn.bsky.app`, downloads each image into
`assets/stories/<slug>/` using a deterministic hash-based filename, and
rewrites the story body to use the local root-relative path. Idempotent:
if a target file already exists locally, the URL is just rewritten
(no redundant download).

Designed to run in GitHub Actions (workflow_dispatch only) where outbound
to cdn.bsky.app is allowed. The Claude sandbox cannot reach BlueSky CDN
directly, so drafts initially commit CDN URLs and this workflow localizes
them in a follow-up commit.

Per spec Section 6: image references should use root-relative paths
under `/assets/stories/<slug>/`.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import httpx

USER_AGENT = (
    "lightseed-stories/0.1 (+https://lightseed.net/stories/; "
    "personal archive of saved BlueSky posts)"
)
TIMEOUT = 30.0

# Markdown image syntax: ![alt](url). Captures the leading "![alt](" and
# trailing ")" so we can replace just the URL.
IMG_PATTERN = re.compile(
    r'(?P<head>!\[[^\]]*\]\()'
    r'(?P<url>https://cdn\.bsky\.app/[^)\s]+)'
    r'(?P<tail>\))'
)


def filename_for_url(url: str) -> str:
    """Deterministic filename: 16-hex-char SHA256 prefix + .jpg.

    Stable across runs as long as the URL is unchanged. CDN-served
    BlueSky images are JPEGs by default; we use .jpg without sniffing.
    """
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"img-{h}.jpg"


def slug_from_frontmatter(text: str) -> str | None:
    m = re.search(r"^slug:\s*(\S+)", text, re.MULTILINE)
    return m.group(1) if m else None


def download_to(url: str, dest: Path) -> None:
    """Download the URL to dest. Caller checks existence before invoking."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "image/*"},
        follow_redirects=True,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    dest.write_bytes(r.content)


def main() -> int:
    repo = Path.cwd()
    stories_dir = repo / "_stories"
    if not stories_dir.exists():
        print("fetch_images: no _stories directory; nothing to do", file=sys.stderr)
        return 0

    total_downloaded = 0
    total_rewritten = 0
    total_failed = 0

    for story_path in sorted(stories_dir.glob("*.md")):
        text = story_path.read_text()
        slug = slug_from_frontmatter(text)
        if not slug:
            continue

        new_parts: list[str] = []
        last_end = 0
        modified = False
        for match in IMG_PATTERN.finditer(text):
            url = match.group("url")
            fname = filename_for_url(url)
            local_path = repo / "assets" / "stories" / slug / fname
            local_url = f"/assets/stories/{slug}/{fname}"

            if not local_path.exists():
                try:
                    download_to(url, local_path)
                    total_downloaded += 1
                    print(
                        f"  downloaded {url[:80]} -> {local_path.relative_to(repo)}",
                        file=sys.stderr,
                    )
                except Exception as e:
                    total_failed += 1
                    print(
                        f"  FAIL {url[:80]}: {type(e).__name__}: {e}",
                        file=sys.stderr,
                    )
                    # Leave the original URL in place; we'll retry on a
                    # later run.
                    continue

            # Rewrite this match to the local path.
            new_parts.append(text[last_end : match.start()])
            new_parts.append(match.group("head") + local_url + match.group("tail"))
            last_end = match.end()
            total_rewritten += 1
            modified = True

        if modified:
            new_parts.append(text[last_end:])
            story_path.write_text("".join(new_parts))
            print(f"rewrote {story_path.name}", file=sys.stderr)

    print(
        f"fetch_images: downloaded {total_downloaded}, "
        f"rewrote {total_rewritten} refs, {total_failed} failed",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

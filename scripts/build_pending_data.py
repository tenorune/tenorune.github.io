#!/usr/bin/env python3
"""Emit _data/pending.yml from inventory + state + drafted-stories.

A "pending" save is one that:
  - is in _data/saves_inventory.json
  - is NOT drafted (no _stories/*.md with matching bluesky_uri)
  - is NOT skipped (no entry in saves_state.json with status=skipped)

The curator's pending view shows only saves with at least one theme-keyword
match. Saves that match no theme are counted but excluded from the entry list
(the meta block reports the excluded count).

Output structure:
  meta:
    total_inventory, drafted, skipped, queued, pending_total,
    pending_aligned, pending_unaligned
  entries:
    - one per aligned pending save
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

REPO = Path(__file__).resolve().parent.parent
INVENTORY = REPO / "_data" / "saves_inventory.json"
STATE = REPO / "_data" / "saves_state.json"
STORIES = REPO / "_stories"
OUT = REPO / "_data" / "pending.yml"

# Theme keywords. Generous on purpose (the user said it is OK to include
# obviously off-topic ones, so we err toward including).
THEME_KEYWORDS = {
    "bureaucratic-cruelty": [
        "detention", "detained", "detain", "asylum", "visa", "green card",
        "green-card", "paperwork", "denied", "refus", "interview", "naturali",
        "citiz", "medication", "insulin", "diabetes", "pregnant", "pregnancy",
        "separated", "family separation", "no contact", "ICE",
    ],
    "civilian-harm": [
        "shot", "shoot", "killed", "death", "died", "tear gas", "pepper",
        "rubber bullet", "bystander", "civilian", "child", "children",
        "pregnan", "beat", "injur", "wound", "struck", "mother", "father",
    ],
    "deportation-machinery": [
        "deport", "removal", "removed", "ICE", "CBP", "border patrol", "DHS",
        "homeland security", "el salvador", "cecot", "rendition", "expel",
        "third country",
    ],
    "rule-of-law": [
        "judge", "court", "ruling", "lawsuit", "attorney", "due process",
        "warrant", "constitution", "supreme court", "unconstitutional",
        "illegal", "unlawful", "contempt", "defy", "defied", "injunction",
        "DOJ", "FBI",
    ],
    "state-violence": [
        "agent", "officer", "mask", "masked", "tactical", "violence",
        "assault", "raid", "tear gas", "pepper", "rubber bullet", "shot",
        "kill", "gun", "rifle", "military", "troop", "national guard",
        "guardsman", "marines",
    ],
    "official-narrative": [
        "statement", "press release", "spokesperson", "official said",
        "claim", "lie", "lied", "false", "misled", "misinform", "propaganda",
        "narrative", "McLaughlin", "Noem", "Homan", "denied", "spokesman",
    ],
    "predatory-capital": [
        "private prison", "CoreCivic", "GEO Group", "Palantir", "Anduril",
        "billion", "million-dollar", "no-bid", "sole-source", "kickback",
        "donor", "shareholder", "billionaire", "private equity", "lobbyist",
        "lobbying", "campaign donation", "contract", "bounty", "reward",
        "Koch", "Thiel", "Musk",
    ],
    "resistance-and-witness": [
        "protest", "protester", "activist", "organiz", "rally", "march",
        "witness", "recorded", "documented", "journalist", "reporter",
        "press", "community", "neighbor", "mutual aid", "volunteer",
        "lawyer", "attorney", "filed",
    ],
}

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def load_drafted_uris() -> set[str]:
    uris = set()
    for md in STORIES.glob("*.md"):
        m = FRONTMATTER_RE.match(md.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        u = fm.get("bluesky_uri")
        if u:
            uris.add(u)
    return uris


def load_state() -> dict:
    if not STATE.exists():
        return {"states": {}}
    return json.loads(STATE.read_text(encoding="utf-8"))


def blob(s: dict) -> str:
    parts = [s.get("post_text") or ""]
    e = s.get("embed") or {}
    if isinstance(e, dict):
        parts.append(e.get("title") or "")
        parts.append(e.get("description") or "")
    parts.append((s.get("article_text") or "")[:3000])
    for r in s.get("thread_replies") or []:
        parts.append(r.get("post_text") or "")
    return " ".join(parts).lower()


def classify(text: str) -> list[str]:
    matched = []
    for theme, kws in THEME_KEYWORDS.items():
        if any(kw.lower() in text for kw in kws):
            matched.append(theme)
    return matched


def rkey_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def bluesky_url_of(uri: str, handle: str) -> str:
    rkey = rkey_of(uri)
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def parse_iso(s: str | None) -> datetime | None:
    """Parse a variety of ISO-ish timestamps to a tz-naive UTC datetime."""
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    # Normalise trailing Z and fractional seconds for fromisoformat compatibility.
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Date-only: "2025-11-04"
        try:
            dt = datetime.fromisoformat(s + "T00:00:00+00:00")
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def gap_days(post_at: str | None, pub_at: str | None) -> int | None:
    p = parse_iso(post_at)
    q = parse_iso(pub_at)
    if p is None or q is None:
        return None
    return abs((p - q).days)


def excerpt(text: str, n: int = 280) -> str:
    text = (text or "").strip().replace("\r", "")
    if len(text) <= n:
        return text
    return text[:n].rstrip() + "…"


def host_of(url: str) -> str:
    if not url:
        return ""
    h = urlparse(url).netloc.lower()
    return h.removeprefix("www.")


def main() -> int:
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    saves = inv.get("saves", [])
    drafted = load_drafted_uris()
    state = load_state().get("states", {})

    skipped_uris = {u for u, e in state.items() if e.get("status") == "skipped"}
    queued_uris = {u for u, e in state.items() if e.get("status") == "queued"}

    pending = [
        s for s in saves
        if s["uri"] not in drafted and s["uri"] not in skipped_uris
    ]

    aligned: list[dict] = []
    unaligned_count = 0
    for s in pending:
        themes = classify(blob(s))
        if not themes:
            unaligned_count += 1
            continue

        e = s.get("embed") or {}
        author = s.get("author") or {}
        handle = author.get("handle") or ""
        uri = s["uri"]

        badges = []
        if s.get("article_text"):
            badges.append("article")
        if s.get("thread_replies"):
            badges.append("thread")
        if s.get("images"):
            badges.append("image")

        post_at = s.get("post_created_at", "")
        pub_at = s.get("article_published_at", "")
        gap = gap_days(post_at, pub_at)
        aligned.append({
            "rkey": rkey_of(uri),
            "uri": uri,
            "author": handle,
            "author_display": author.get("display_name") or handle,
            "saved_at": s.get("saved_at", ""),
            "post_created_at": post_at,
            "article_published_at": pub_at,
            "gap_days": gap,
            "gap_flag": gap is not None and gap > 7,
            "post_text": excerpt(s.get("post_text") or "", 280),
            "embed_title": (e.get("title") or "").strip() if isinstance(e, dict) else "",
            "embed_host": host_of(e.get("url") if isinstance(e, dict) else None),
            "embed_url": (e.get("url") or "") if isinstance(e, dict) else "",
            "bluesky_url": bluesky_url_of(uri, handle) if handle else "",
            "themes": themes,
            "badges": badges,
            "queued": uri in queued_uris,
        })

    aligned.sort(key=lambda r: r["post_created_at"] or r["saved_at"], reverse=True)

    flagged = sum(1 for a in aligned if a["gap_flag"])
    meta = {
        "total_inventory": len(saves),
        "drafted": len(drafted),
        "skipped": len(skipped_uris),
        "queued": len(queued_uris),
        "pending_total": len(pending),
        "pending_aligned": len(aligned),
        "pending_unaligned": unaligned_count,
        "pending_gap_flagged": flagged,
    }

    out = {"meta": meta, "entries": aligned}
    OUT.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(REPO)} "
        f"({meta['pending_aligned']} aligned, {meta['pending_unaligned']} unaligned excluded)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

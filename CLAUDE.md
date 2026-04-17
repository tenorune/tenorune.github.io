# Claude session context

This repo hosts two unrelated things that share a GitHub Pages build:

1. **`lightseed.net` homepage** — static, hand-authored. Lives at the repo root: `index.html`, `style.css`, `CNAME`, `favicon.ico`, `media/`. **Do not modify any of these** unless the user explicitly asks about the homepage.

2. **Stories compilation** (planning complete, scaffolding not yet started) — a Jekyll-based long-form archive of BlueSky saves. Authoritative plan: [`docs/stories-plan.md`](docs/stories-plan.md). **Read that file first** before starting any stories-related work.

## Active development branch
- `claude/bluesky-stories-compilation-milg9` for the initial scaffold.
- Subsequent curator sessions (authoring stories, editing, adding images): `stories/YYYYMMDD-<slug-or-topic>` per PR.

## Key rules
- The two projects are **isolated**: no shared CSS, no nav link, no front-matter changes to the homepage.
- When Jekyll is added, the homepage files must be in the `_config.yml` `exclude:` list so Jekyll passes them through unchanged. See the *Risks / unknowns* and *Verification* sections of the plan for details.
- Story authoring is **conversational** through Claude — no CMS. All edits, image add/remove, and text regeneration happen via chat and commits.
- Git history is the revision log for stories. Use `git revert` to roll back an edit.
- Frontmatter contract, file layout, and image storage conventions are in the plan document — follow exactly.

## What's NOT in the repo yet
Everything in the stories plan is planned but unbuilt: no `_config.yml`, no `_layouts/`, no `_stories/`, no fetch script, no workflow. The next step is PR 1 (Scaffolding) per the plan's *Execution phases* section.

## Things to read before acting on this project
1. This file.
2. `docs/stories-plan.md` — full plan.
3. The existing homepage (`index.html`, `style.css`, `media/`) to confirm it is untouched.

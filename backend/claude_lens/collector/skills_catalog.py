"""Skill catalog: locate SKILL.md files and map slugs to file sizes.

Ported from `token_dashboard/skills.py`. A skill on disk lives at one of:
  ~/.claude/skills/<name>/SKILL.md                     -> slug "<name>"
  ~/.claude/scheduled-tasks/<name>/SKILL.md            -> slug "<name>"
  ~/.claude/plugins/marketplaces/*/plugins/<plugin>/skills/<name>/SKILL.md
      -> registers TWO slugs: "<plugin>:<name>" and "<name>"
      (Claude Code accepts either form in the Skill tool.)

Sizes are in chars; token estimate is chars // 4 (the same approximation
`parse._extract_results` uses for tool-result tokens).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

_DEFAULT_ROOTS = [
    Path.home() / ".claude" / "skills",
    Path.home() / ".claude" / "scheduled-tasks",
    Path.home() / ".claude" / "plugins",
]

_VERSION_RE = re.compile(r"^\d+\.\d+")
_STRUCTURE_NAMES = {"skills", "plugins", "marketplaces", "cache", ".claude"}


def _slugs_for(skill_md: Path) -> list[str]:
    """Return the slug(s) a Skill tool invocation could use to load this file.

    Paths vary by install source:
      marketplaces/<m>/plugins/<plugin>/skills/<skill>/SKILL.md
      cache/<m>/<plugin>/<version>/skills/<skill>/SKILL.md
      cache/temp_git_*/skills/<skill>/SKILL.md         (no plugin)
      skills/<skill>/SKILL.md                          (no plugin)
      scheduled-tasks/<skill>/SKILL.md                 (no plugin)

    Strategy: always register the bare skill name. Additionally, walk up from
    `skills/` and register `<ancestor>:<skill>` for every ancestor segment
    that plausibly names a plugin (not a structural/version/temp-dir token).
    Unused slugs are harmless; the user only invokes real ones.
    """
    parts = skill_md.parts
    if "SKILL.md" not in parts or skill_md.name != "SKILL.md":
        return []
    skill_name = skill_md.parent.name
    slugs = {skill_name}
    # Locate the `skills` folder that contains this skill.
    try:
        skills_idx = len(parts) - 1 - parts[::-1].index("skills")
    except ValueError:
        return list(slugs)
    for seg in parts[:skills_idx]:
        if not seg or seg in _STRUCTURE_NAMES:
            continue
        if _VERSION_RE.match(seg):
            continue
        if seg.startswith("temp_git_"):
            continue
        if seg.endswith(":") or ":" in seg:  # drive letters like "C:"
            continue
        slugs.add(f"{seg}:{skill_name}")
    return sorted(slugs)


def scan_catalog(roots=None) -> Dict[str, dict]:
    """Return {slug: {path, chars, tokens}} for every SKILL.md found.

    When a slug resolves to multiple files (nested `skills/skills/`), keep the
    entry with the shallowest path; that's the canonical install.
    """
    roots = roots or _DEFAULT_ROOTS
    catalog: Dict[str, dict] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for md in root.rglob("SKILL.md"):
            try:
                chars = md.stat().st_size
            except OSError:
                continue
            entry = {"path": str(md), "chars": chars, "tokens": chars // 4}
            for slug in _slugs_for(md):
                prev = catalog.get(slug)
                if prev is None or len(md.parts) < len(Path(prev["path"]).parts):
                    catalog[slug] = entry
    return catalog


def upload_catalog(conn, machine: str, catalog: Optional[Dict[str, dict]] = None) -> int:
    """Replace this machine's `skill_catalog` rows with `catalog` (default: scan disk).

    The API runs on the VPS and can't see this PC's skill files, so each
    collector run uploads them. Other machines' rows are left alone. `conn`
    must have `search_path` set to the Claude Lens schema and be idle.
    Returns the number of slugs written.
    """
    if catalog is None:
        catalog = scan_catalog()
    with conn.transaction():
        conn.execute("DELETE FROM skill_catalog WHERE machine = %s", (machine,))
        if catalog:
            with conn.cursor() as cur:
                with cur.copy(
                    "COPY skill_catalog (machine, slug, path, chars, tokens) FROM STDIN"
                ) as cp:
                    for slug in sorted(catalog):
                        e = catalog[slug]
                        cp.write_row((machine, slug, e["path"], e["chars"], e["tokens"]))
    return len(catalog)

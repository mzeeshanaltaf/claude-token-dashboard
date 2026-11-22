from pathlib import Path

from claude_lens.collector import skills_catalog
from claude_lens.collector.skills_catalog import _slugs_for, scan_catalog


def _write(p: Path, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_user_skill(tmp_path):
    _write(tmp_path / "skills" / "frontend-design" / "SKILL.md", "x" * 400)
    cat = scan_catalog([tmp_path / "skills"])
    assert cat["frontend-design"]["chars"] == 400
    assert cat["frontend-design"]["tokens"] == 100


def test_plugin_skill_registers_both_slugs(tmp_path):
    p = tmp_path / "plugins" / "marketplaces" / "official" / "plugins" / "superpowers" / "skills" / "brainstorming" / "SKILL.md"
    _write(p, "y" * 800)
    cat = scan_catalog([tmp_path / "plugins"])
    assert cat["brainstorming"]["tokens"] == 200
    assert cat["superpowers:brainstorming"]["tokens"] == 200


def test_scheduled_task_skill(tmp_path):
    _write(tmp_path / "scheduled-tasks" / "morning-coffee" / "SKILL.md", "z" * 100)
    cat = scan_catalog([tmp_path / "scheduled-tasks"])
    assert "morning-coffee" in cat


def test_nested_skills_skills_dedup_prefers_shallow(tmp_path):
    _write(tmp_path / "skills" / "foo" / "SKILL.md", "s" * 100)
    _write(tmp_path / "skills" / "skills" / "foo" / "SKILL.md", "d" * 999)
    cat = scan_catalog([tmp_path / "skills"])
    assert cat["foo"]["chars"] == 100


def test_slugs_for_plugin_path():
    slugs = set(_slugs_for(Path("plugins/marketplaces/x/plugins/superpowers/skills/brainstorming/SKILL.md")))
    # Both forms must be present; extra ancestor aliases (e.g. marketplace name) are harmless.
    assert "brainstorming" in slugs
    assert "superpowers:brainstorming" in slugs


def test_slugs_for_cache_versioned_path():
    slugs = set(_slugs_for(Path("plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/brainstorming/SKILL.md")))
    assert "brainstorming" in slugs
    assert "superpowers:brainstorming" in slugs
    # version segment must NOT become a slug prefix
    assert "5.0.7:brainstorming" not in slugs


def test_slugs_for_user_skill():
    assert _slugs_for(Path(".claude/skills/frontend-design/SKILL.md")) == ["frontend-design"]


def test_slugs_for_non_skill_file():
    assert _slugs_for(Path("skills/foo/README.md")) == []


def test_missing_skill_not_in_catalog(tmp_path):
    cat = scan_catalog([tmp_path / "skills"])
    assert "never-installed" not in cat


def test_default_roots_unchanged():
    home = Path.home() / ".claude"
    assert skills_catalog._DEFAULT_ROOTS == [home / "skills", home / "scheduled-tasks", home / "plugins"]

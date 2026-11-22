from claude_lens.collector import skills_catalog
from claude_lens.collector.skills_catalog import upload_catalog
from helpers import q


def _cat(**sizes):
    return {slug: {"path": f"/skills/{slug}/SKILL.md", "chars": n, "tokens": n // 4}
            for slug, n in sizes.items()}


def test_upload_replaces_only_this_machines_rows(db):
    assert upload_catalog(db, "pc-a", _cat(alpha=400, beta=80)) == 2
    upload_catalog(db, "pc-b", _cat(gamma=40))
    assert upload_catalog(db, "pc-a", _cat(alpha=800)) == 1
    rows = q(db, "SELECT machine, slug, chars, tokens FROM skill_catalog ORDER BY machine, slug")
    assert rows == [("pc-a", "alpha", 800, 200), ("pc-b", "gamma", 40, 10)]


def test_upload_empty_catalog_clears_rows(db):
    upload_catalog(db, "pc-a", _cat(alpha=4))
    assert upload_catalog(db, "pc-a", {}) == 0
    assert q(db, "SELECT count(*) FROM skill_catalog") == [(0,)]


def test_upload_defaults_to_scanning_disk(db, tmp_path, monkeypatch):
    skill = tmp_path / "skills" / "my-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("x" * 100)
    monkeypatch.setattr(skills_catalog, "_DEFAULT_ROOTS", [tmp_path / "skills"])
    n = upload_catalog(db, "pc-a")
    rows = q(db, "SELECT slug, chars, tokens FROM skill_catalog")
    # Besides the bare name, the catalog registers "<ancestor>:my-skill" for the temp path's folders.
    assert n == len(rows)
    assert ("my-skill", 100, 25) in rows

from claude_lens.core.names import _encode_slug, best_project_name, project_name_for


def test_basename_of_posix_cwd():
    assert project_name_for("/Users/x/foo", "slug") == "foo"


def test_basename_of_windows_cwd():
    assert project_name_for(r"C:\Users\alice\projects\Token Dashboard", "anything") == "Token Dashboard"


def test_trailing_slash_stripped():
    assert project_name_for("/a/b/c/", "slug") == "c"


def test_fallback_uses_last_dash_segment():
    assert project_name_for(None, "C--Users-x-Foo-Bar") == "Bar"


def test_fallback_single_segment():
    assert project_name_for(None, "projA") == "projA"


def test_empty():
    assert project_name_for(None, "") == ""


def test_walks_up_cwd_to_project_root():
    # cwd is a subfolder; slug matches the parent -> return the parent's basename
    assert project_name_for(
        r"C:\Users\alice\projects\MyProject\subdir",
        "C--Users-alice-projects-MyProject",
    ) == "MyProject"


def test_walks_up_preserves_spaces():
    assert project_name_for(
        r"C:\Users\alice\projects\Token Dashboard\src\subdir",
        "C--Users-alice-projects-Token-Dashboard",
    ) == "Token Dashboard"


def test_encode_slug_matches_claude_code():
    assert _encode_slug(r"E:\Projects\Claude Code\app") == "E--Projects-Claude-Code-app"
    assert _encode_slug("/home/u/my app") == "-home-u-my-app"


def test_best_project_name_prefers_matching_cwd():
    slug = "C--work-Real-Project"
    cwds = [r"C:\elsewhere\other", r"C:\work\Real Project\src"]
    assert best_project_name(cwds, slug) == "Real Project"


def test_best_project_name_falls_back_to_first_cwd_then_slug():
    assert best_project_name([None, "/x/first", "/y/second"], "nomatch") == "first"
    assert best_project_name([], "C--Users-x-Foo-Bar") == "Bar"
    assert best_project_name(None, "") == ""

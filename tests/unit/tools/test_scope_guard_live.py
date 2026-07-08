"""Unit tests for live-host scope matching (Phase 2), plus repo back-compat."""
from tools import scope_guard


def test_extract_host_from_url_and_bare_host():
    assert scope_guard.extract_host("https://Example.com:8443/api") == "example.com"
    assert scope_guard.extract_host("example.com") == "example.com"
    assert scope_guard.extract_host("example.com:9000") == "example.com"
    assert scope_guard.extract_host("") == ""


def test_check_live_allows_matching_host():
    allow = ["https://target.example.com"]
    assert scope_guard.check_live("https://target.example.com/admin", allow) is True
    # Port + path are irrelevant; host must match.
    assert scope_guard.check_live("http://target.example.com:8080/", allow) is True


def test_check_live_refuses_other_host():
    allow = ["https://target.example.com"]
    assert scope_guard.check_live("https://evil.example.net/", allow) is False
    # A subdomain is NOT the same host.
    assert scope_guard.check_live("https://api.target.example.com/", allow) is False


def test_check_live_refuses_empty_allowlist():
    assert scope_guard.check_live("https://target.example.com/", []) is False


def test_check_target_dispatches_by_type(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    # Repo path uses containment (Phase 1 behaviour, unchanged).
    assert scope_guard.check_target(str(repo), [str(tmp_path)], "repo") is True
    assert scope_guard.check_target("/etc/passwd", [str(tmp_path)], "repo") is False
    # live_app uses host allowlist.
    assert scope_guard.check_target(
        "https://target.example.com/x", ["target.example.com"], "live_app"
    ) is True
    assert scope_guard.check_target(
        "https://evil.example.net/", ["target.example.com"], "live_app"
    ) is False


def test_repo_check_unchanged(tmp_path):
    # Phase-1 path containment must still hold.
    repo = tmp_path / "repo"
    repo.mkdir()
    assert scope_guard.check(str(repo / "sub"), [str(repo)]) is True
    assert scope_guard.check(str(tmp_path / "other"), [str(repo)]) is False

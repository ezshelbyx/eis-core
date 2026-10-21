import pytest

from redkit.scope import EmptyScope, OutOfScope, Scope, ScopeError, default_home


def test_empty_scope_refuses_everything():
    scope = Scope([])
    assert scope.is_empty()
    with pytest.raises(OutOfScope):
        scope.require("192.168.1.1")
    with pytest.raises(OutOfScope):
        scope.require("https://example.com/")


def test_cidr_membership():
    scope = Scope(["192.168.1.0/24"])
    assert scope.allows("192.168.1.77")
    assert not scope.allows("192.168.2.77")


def test_single_ip():
    scope = Scope(["10.0.0.5"])
    assert scope.allows("10.0.0.5")
    assert not scope.allows("10.0.0.6")


def test_domain_and_subdomain():
    scope = Scope(["example.com"])
    assert scope.allows("example.com")
    assert scope.allows("app.example.com")
    assert scope.allows("https://deep.app.example.com/path?q=1")
    assert not scope.allows("notexample.com")
    assert not scope.allows("example.com.evil.net")


def test_wildcard_entry():
    scope = Scope(["*.example.com"])
    assert scope.allows("api.example.com")
    assert scope.allows("example.com")


def test_invalid_entry_rejected():
    with pytest.raises(ScopeError):
        Scope(["not a host!"])
    with pytest.raises(ScopeError):
        Scope([""])


def test_add_remove_roundtrip(tmp_path):
    scope = Scope([])
    assert scope.add("10.0.0.0/24")
    assert not scope.add("10.0.0.0/24")  # duplicate returns False
    scope.add("example.com")
    path = tmp_path / "scope"
    scope.save(path)

    loaded = Scope.load(path)
    assert loaded.entries() == ["10.0.0.0/24", "example.com"]
    assert loaded.remove("10.0.0.0/24")
    assert not loaded.remove("10.0.0.0/24")
    assert loaded.entries() == ["example.com"]


def test_load_tolerates_comments(tmp_path):
    path = tmp_path / "scope"
    path.write_text("# my lab\n192.168.56.0/24\n\nexample.com  # staging\n")
    scope = Scope.load(path)
    assert scope.entries() == ["192.168.56.0/24", "example.com"]


def test_load_missing_file_is_empty(tmp_path):
    assert Scope.load(tmp_path / "nope").is_empty()


def test_url_forms_normalize():
    scope = Scope(["example.com"])
    assert scope.allows("HTTPS://Example.COM:8443/x")
    assert scope.allows("http://sub.example.com")


def test_default_home_env(monkeypatch, tmp_path):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    assert default_home() == tmp_path

import json

import pytest

from redkit import cli
from redkit.scope import Scope, load_scope
from redkit.store import Finding, clear, findings_path, load, record


# --- store ------------------------------------------------------------------

def test_record_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    record(Finding(module="scan", target="10.0.0.1:22", title="Open port 22/tcp",
                   severity="info", detail="SSH-2.0-OpenSSH"))
    record(Finding(module="web", target="https://x", title="Missing header",
                   severity="medium"))
    items = load()
    assert len(items) == 2
    assert items[0].title == "Open port 22/tcp"
    assert items[1].severity == "medium"
    assert findings_path(tmp_path).exists()


def test_record_bad_severity_rejected():
    with pytest.raises(ValueError):
        Finding(module="m", target="t", title="x", severity="extreme")


def test_load_tolerates_corrupt_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    path = findings_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    good = Finding(module="m", target="t", title="ok")
    from dataclasses import asdict
    path.write_text(json.dumps(asdict(good)) + "\n{broken json\n\n")
    assert len(load()) == 1


def test_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    record(Finding(module="m", target="t", title="x"))
    assert clear() is True
    assert load() == []
    assert clear() is False


# --- CLI --------------------------------------------------------------------

def test_cli_no_command_prints_help(capsys):
    rc = cli.main([])
    assert rc == 2
    assert "scope" in capsys.readouterr().out


def test_cli_scope_add_list_remove(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    assert cli.main(["scope", "add", "192.168.7.0/24", "example.com"]) == 0
    out = capsys.readouterr().out
    assert "192.168.7.0/24" in out and "example.com" in out

    assert cli.main(["scope", "list"]) == 0
    out = capsys.readouterr().out
    assert "192.168.7.0/24" in out

    assert cli.main(["scope", "remove", "example.com"]) == 0
    capsys.readouterr()  # flush remove output before checking list output
    assert cli.main(["scope", "list"]) == 0
    out = capsys.readouterr().out
    assert "example.com" not in out
    assert load_scope().entries() == ["192.168.7.0/24"]


def test_cli_scope_show_prints_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    assert cli.main(["scope", "show"]) == 0
    assert str(tmp_path / "scope") in capsys.readouterr().out


def test_scan_refused_when_scope_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    rc = cli.main(["scan", "127.0.0.1", "-p", "1-10"])
    err = capsys.readouterr().err
    assert rc == 3
    assert "scope is empty" in err


def test_scan_refused_out_of_scope(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    cli.main(["scope", "add", "10.0.0.0/8"])
    capsys.readouterr()
    rc = cli.main(["scan", "8.8.8.8", "-p", "53"])
    err = capsys.readouterr().err
    assert rc == 3
    assert "refused" in err
    assert "written permission" in err


def test_scan_localhost_records_finding(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    cli.main(["scope", "add", "127.0.0.1"])
    capsys.readouterr()
    # Port 1 is almost always closed -> exit 1, but probes must have run.
    rc = cli.main(["scan", "127.0.0.1", "-p", "1", "-t", "0.3"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "0 open port(s)" in out


def test_web_refused_out_of_scope(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    cli.main(["scope", "add", "example.com"])
    capsys.readouterr()
    rc = cli.main(["web", "https://not-in-scope.org/"])
    err = capsys.readouterr().err
    assert rc == 3
    assert "refused" in err


def test_report_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    assert cli.main(["report"]) == 0
    assert "no findings" in capsys.readouterr().out


def test_report_with_findings_and_clear(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    record(Finding(module="scan", target="10.0.0.1:445", title="Open port 445/tcp",
                   severity="info"))
    record(Finding(module="web", target="https://x", title="Exposed path: /.env",
                   severity="high", detail="HTTP 200"))
    assert cli.main(["report"]) == 0
    out = capsys.readouterr().out
    assert "2 finding(s)" in out
    assert "high=1" in out
    assert "Exposed path: /.env" in out

    assert cli.main(["report", "--clear"]) == 0
    assert load() == []


def test_selftest_passes(capsys):
    rc = cli.main(["selftest"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "all checks passed" in out


def test_scan_bad_port_spec(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REDKIT_HOME", str(tmp_path))
    cli.main(["scope", "add", "127.0.0.1"])
    capsys.readouterr()
    rc = cli.main(["scan", "127.0.0.1", "-p", "bogus"])
    assert rc == 2
    assert "error" in capsys.readouterr().err

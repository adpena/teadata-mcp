from __future__ import annotations

from types import SimpleNamespace

import pytest

from teadata_mcp import server


def test_diagnose_environment_reports_missing_dependency(monkeypatch, capsys):
    monkeypatch.setattr(server.importlib.util, "find_spec", lambda name: None)

    ok = server.diagnose_environment()

    captured = capsys.readouterr().out
    assert not ok
    assert "Could not locate 'modelcontextprotocol'" in captured


def test_diagnose_environment_reports_success(monkeypatch, capsys):
    def fake_find_spec(name: str):
        if name == "modelcontextprotocol":
            return SimpleNamespace(origin="/tmp/modelcontextprotocol/__init__.py", loader=None)
        if name == "modelcontextprotocol.adapters.stdio":
            return SimpleNamespace(origin="/tmp/stdio.py", loader=None)
        raise AssertionError(f"Unexpected module lookup: {name}")

    monkeypatch.setattr(server.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(server.importlib.metadata, "version", lambda name: "1.0.0")

    ok = server.diagnose_environment()

    captured = capsys.readouterr().out
    assert ok
    assert "Found 'modelcontextprotocol' (version 1.0.0)" in captured
    assert "Found 'modelcontextprotocol.adapters.stdio'" in captured


def test_diagnose_environment_checks_snapshot(monkeypatch, capsys, tmp_path):
    def fake_find_spec(name: str):
        return SimpleNamespace(origin="/tmp/module.py", loader=None)

    monkeypatch.setattr(server.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(server.importlib.metadata, "version", lambda name: "1.0.0")

    monkeypatch.setenv("TEADATA_SNAPSHOT", str(tmp_path / "missing.snapshot"))

    ok = server.diagnose_environment()

    captured = capsys.readouterr().out
    assert not ok
    assert "TEADATA_SNAPSHOT points to missing path" in captured

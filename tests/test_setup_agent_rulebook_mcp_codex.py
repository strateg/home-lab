"""Tests for the ADR0096 Codex MCP setup helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "orchestration" / "mcp" / "setup-agent-rulebook-mcp-codex.py"
    spec = importlib.util.spec_from_file_location("setup_agent_rulebook_mcp_codex", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load setup-agent-rulebook-mcp-codex module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_server_spec_prefers_repo_venv_python() -> None:
    module = _load_module()

    spec = module.build_server_spec()

    expected_python = str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python")
    assert spec["command"] == expected_python
    assert spec["args"] == [
        str(Path(__file__).resolve().parents[1] / "scripts" / "orchestration" / "mcp" / "agent_rulebook_mcp_server.py")
    ]


def test_main_print_config_emits_mcp_json_snippet(capsys) -> None:
    module = _load_module()

    exit_code = module.main(["--print-config"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["mcpServers"][module.MCP_SERVER_NAME]["type"] == "stdio"


def test_check_status_reports_matching_config(monkeypatch, capsys) -> None:
    module = _load_module()
    spec = module.build_server_spec()
    monkeypatch.setattr(module, "codex_mcp_get", lambda _: {"command": spec["command"], "args": list(spec["args"])})

    exit_code = module.main(["--check"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["configured"] is True
    assert payload["matches_expected"] is True


def test_register_mcp_server_replaces_existing_entry(monkeypatch, capsys) -> None:
    module = _load_module()
    calls: list[list[str]] = []

    def _fake_run_command(args: list[str], *, check: bool = True):
        calls.append(args)
        return SimpleNamespace(stdout="{}", stderr="", returncode=0)

    monkeypatch.setattr(module, "codex_mcp_get", lambda _: {"command": "python3", "args": ["old.py"]})
    monkeypatch.setattr(module, "run_command", _fake_run_command)

    ok = module.register_mcp_server()

    captured = capsys.readouterr()
    assert ok is True
    assert any(args[:4] == ["codex", "mcp", "remove", module.MCP_SERVER_NAME] for args in calls)
    assert any(args[:4] == ["codex", "mcp", "add", module.MCP_SERVER_NAME] for args in calls)
    assert "Registered" in captured.out

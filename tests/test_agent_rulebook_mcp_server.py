#!/usr/bin/env python3
"""Tests for ADR0096 MCP stdio resource server."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "orchestration" / "mcp" / "agent_rulebook_mcp_server.py"
    spec = importlib.util.spec_from_file_location("agent_rulebook_mcp_server", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load agent_rulebook_mcp_server module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_rulebook_mcp_server_lists_exported_resources() -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    export_catalog = mod.build_resource_catalog(repo_root)
    server = mod.build_server(repo_root)

    resources = asyncio.run(server.list_resources())
    listed_uris = {str(resource.uri) for resource in resources}
    exported_uris = {entry["uri"] for entry in export_catalog["resources"]}

    assert listed_uris == exported_uris


def test_agent_rulebook_mcp_server_reads_rulebook_and_rule_map() -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    server = mod.build_server(repo_root)

    rulebook = asyncio.run(server.read_resource("home-lab://ai/rulebook"))
    rule_map = asyncio.run(server.read_resource("home-lab://ai/rule-map"))

    assert rulebook[0].content.startswith("# Universal AI Agent Rulebook")
    assert 'generated_from_adr: "0096"' in rule_map[0].content


def test_agent_rulebook_mcp_server_check_mode_reports_summary() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "orchestration" / "mcp" / "agent_rulebook_mcp_server.py"

    run = subprocess.run(
        [sys.executable, str(script), "--check"],
        text=True,
        capture_output=True,
        check=False,
        cwd=repo_root,
    )

    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    payload = json.loads(run.stdout)
    assert payload["server_name"] == "home-lab-ai-rulebook"
    assert payload["resource_prefix"] == "home-lab://ai"
    assert payload["resource_count"] >= 14

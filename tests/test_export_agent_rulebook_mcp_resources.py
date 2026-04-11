#!/usr/bin/env python3
"""Tests for ADR0096 MCP-style resource catalog export."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "validation" / "export_agent_rulebook_mcp_resources.py"
    spec = importlib.util.spec_from_file_location("export_agent_rulebook_mcp_resources", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load export_agent_rulebook_mcp_resources module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repository_agent_rulebook_mcp_export_builds() -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    rule_map = yaml.safe_load((repo_root / "docs" / "ai" / "ADR-RULE-MAP.yaml").read_text(encoding="utf-8"))

    export = mod._build_export(repo_root=repo_root, rule_map=rule_map)

    assert export["catalog_kind"] == "mcp_resource_catalog"
    assert export["resource_prefix"] == "home-lab://ai"
    assert export["boot_resources"] == ["home-lab://ai/rulebook", "home-lab://ai/rule-map"]
    assert export["resource_count"] == len(export["resources"])

    by_uri = {entry["uri"]: entry for entry in export["resources"]}
    assert "home-lab://ai/rulebook" in by_uri
    assert "home-lab://ai/rule-map" in by_uri
    assert "home-lab://ai/adr/0096/schema-policy" in by_uri
    assert "home-lab://ai/adr/0096/status-report" in by_uri
    assert "home-lab://ai/adr/0096/swot-analysis" in by_uri

    for entry in export["resources"]:
        assert (repo_root / entry["path"]).exists()


def test_export_includes_rule_pack_resource_for_each_registered_pack() -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    rule_map = yaml.safe_load((repo_root / "docs" / "ai" / "ADR-RULE-MAP.yaml").read_text(encoding="utf-8"))

    export = mod._build_export(repo_root=repo_root, rule_map=rule_map)
    exported_rule_packs = {
        entry["uri"].removeprefix("home-lab://ai/rules/"): entry
        for entry in export["resources"]
        if entry["kind"] == "rule-pack"
    }

    assert set(exported_rule_packs) == set(rule_map["rule_packs"])
    for pack_name, pack in rule_map["rule_packs"].items():
        assert exported_rule_packs[pack_name]["path"] == pack["path"]
        assert exported_rule_packs[pack_name]["source_adr"] == pack["source_adr"]


def test_cli_writes_output_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "agent-rule-mcp-resources.json"
    script = repo_root / "scripts" / "validation" / "export_agent_rulebook_mcp_resources.py"

    run = subprocess.run(
        [sys.executable, str(script), "--output-json", str(output_path)],
        text=True,
        capture_output=True,
        check=False,
        cwd=repo_root,
    )

    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["catalog_kind"] == "mcp_resource_catalog"
    assert payload["resource_count"] == len(payload["resources"])

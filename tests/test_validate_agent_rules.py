#!/usr/bin/env python3
"""Tests for ADR0096 agent rule validation."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "validation" / "validate_agent_rules.py"
    spec = importlib.util.spec_from_file_location("validate_agent_rules", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load validate_agent_rules module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repository_agent_rule_validation_passes() -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    result = mod.validate_agent_rules(
        repo_root=repo_root,
        rule_map_path=repo_root / "docs" / "ai" / "ADR-RULE-MAP.yaml",
        schema_path=repo_root / "schemas" / "adr-rule-map.schema.json",
        register_path=repo_root / "adr" / "REGISTER.md",
    )
    assert result.errors == []


def test_validator_uses_adapter_registry_from_rule_map(tmp_path: Path) -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]

    (tmp_path / "adr").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ai" / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "schemas").mkdir(parents=True, exist_ok=True)

    shutil.copy2(repo_root / "schemas" / "adr-rule-map.schema.json", tmp_path / "schemas" / "adr-rule-map.schema.json")
    (tmp_path / "adr" / "REGISTER.md").write_text(
        "| [0096] | Test ADR | Implemented | 2026-04-10 | - | - |\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "ai" / "rules" / "testing-ci.md").write_text("# test pack\n", encoding="utf-8")

    rule_map = {
        "schema_version": 1,
        "generated_from_adr": "0096",
        "purpose": "Temporary rule map for validator coverage.",
        "adapters": {
            "files": ["CUSTOM-AGENT.md"],
            "required_refs": ["docs/ai/AGENT-RULEBOOK.md", "docs/ai/ADR-RULE-MAP.yaml"],
        },
        "rule_packs": {
            "testing-ci": {
                "path": "docs/ai/rules/testing-ci.md",
                "source_adr": ["0096"],
                "files_glob": ["tests/**"],
            }
        },
        "rules": [
            {
                "id": "TST-001",
                "scope": "testing-ci",
                "trigger": "Any validator coverage change",
                "must": ["Keep validation behavior source-linked."],
                "never": ["Do not hide adapter registry in validator-only constants."],
                "validate": ["pytest tests/test_validate_agent_rules.py -q"],
                "source_adr": ["0096"],
            }
        ],
    }
    (tmp_path / "docs" / "ai" / "ADR-RULE-MAP.yaml").write_text(
        yaml.safe_dump(rule_map, sort_keys=False),
        encoding="utf-8",
    )
    (tmp_path / "CUSTOM-AGENT.md").write_text("custom adapter without required refs\n", encoding="utf-8")

    result = mod.validate_agent_rules(
        repo_root=tmp_path,
        rule_map_path=tmp_path / "docs" / "ai" / "ADR-RULE-MAP.yaml",
        schema_path=tmp_path / "schemas" / "adr-rule-map.schema.json",
        register_path=tmp_path / "adr" / "REGISTER.md",
    )

    assert any(
        error == "Adapter CUSTOM-AGENT.md does not reference docs/ai/AGENT-RULEBOOK.md" for error in result.errors
    )
    assert any(
        error == "Adapter CUSTOM-AGENT.md does not reference docs/ai/ADR-RULE-MAP.yaml" for error in result.errors
    )

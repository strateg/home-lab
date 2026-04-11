#!/usr/bin/env python3
"""Contract checks for ADR0096 rule-map schema evolution policy."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_adr0096_schema_policy_documents_current_epoch_and_change_process() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    policy_path = repo_root / "adr" / "0096-analysis" / "SCHEMA-VERSION-POLICY.md"
    content = policy_path.read_text(encoding="utf-8")

    assert "Writer baseline: `schema_version: 1`" in content
    assert "Reader compatibility epoch: `1`" in content
    assert "compatibility epoch" in content
    assert "Breaking changes require `schema_version` bump" in content
    assert "1. Update this policy." in content
    assert "3. Update `schemas/adr-rule-map.schema.json`." in content


def test_adr_rule_map_schema_version_matches_documented_policy_epoch() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rule_map = yaml.safe_load((repo_root / "docs" / "ai" / "ADR-RULE-MAP.yaml").read_text(encoding="utf-8"))
    policy = (repo_root / "adr" / "0096-analysis" / "SCHEMA-VERSION-POLICY.md").read_text(encoding="utf-8")

    assert rule_map["schema_version"] == 1
    assert "Writer baseline: `schema_version: 1`" in policy

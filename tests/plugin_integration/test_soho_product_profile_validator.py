#!/usr/bin/env python3
"""Integration checks for SOHO product profile validator."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.validators.soho_product_profile_validator import SohoProductProfileValidator


def _ctx(tmp_path: Path, project_payload: dict) -> PluginContext:
    project_manifest = tmp_path / "project.yaml"
    project_manifest.write_text(yaml.safe_dump(project_payload, sort_keys=False), encoding="utf-8")
    policy_path = tmp_path / "soho-migration-state-policy.yaml"
    policy_path.write_text(
        """
schema_version: 1
states: [legacy, migrated-soft, migrated-hard]
allowed_transitions:
  legacy: [legacy, migrated-soft]
  migrated-soft: [migrated-soft, migrated-hard]
  migrated-hard: [migrated-hard]
blocking_on_invalid_transition: true
""".strip() + "\n",
        encoding="utf-8",
    )
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        output_dir=str(tmp_path / "build"),
        config={
            "repo_root": str(tmp_path),
            "project_id": "home-lab",
            "project_manifest_path": str(project_manifest),
            "soho_migration_policy_path": str(policy_path),
        },
    )


def test_soho_validator_warns_when_product_profile_is_missing(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(tmp_path, {"project": "home-lab"})

    result = validator.execute(ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7941" for diag in result.diagnostics)
    report_path = tmp_path / "build" / "diagnostics" / "product-profile-state.json"
    assert report_path.exists()


def test_soho_validator_fails_for_migrated_hard_missing_bundles(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(
        tmp_path,
        {
            "project": "home-lab",
            "product_profile": {
                "profile_id": "soho.standard.v1",
                "deployment_class": "managed-soho",
                "site_class": "single-site",
                "user_band": "1-25",
                "operator_mode": "single-operator",
                "release_channel": "stable",
                "migration_state": "migrated-hard",
            },
            "product_bundles": ["bundle.edge-routing", "bundle.network-segmentation"],
        },
    )

    result = validator.execute(ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7942" for diag in result.diagnostics)


def test_soho_validator_fails_on_invalid_state_transition(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(
        tmp_path,
        {
            "project": "home-lab",
            "product_profile": {
                "profile_id": "soho.standard.v1",
                "deployment_class": "starter",
                "site_class": "single-site",
                "user_band": "1-25",
                "operator_mode": "single-operator",
                "release_channel": "stable",
                "migration_state": "migrated-soft",
                "previous_migration_state": "migrated-hard",
            },
            "product_bundles": [
                "bundle.edge-routing",
                "bundle.network-segmentation",
                "bundle.secrets-governance",
                "bundle.remote-access",
                "bundle.operator-workflows",
            ],
        },
    )

    result = validator.execute(ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7947" for diag in result.diagnostics)

#!/usr/bin/env python3
"""Integration checks for SOHO profile resolver compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.compilers.soho_profile_resolver_compiler import SohoProfileResolverCompiler


def _write_bundle(path: Path, bundle_id: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "bundle_id": bundle_id,
                "title": bundle_id,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _ctx(tmp_path: Path, project_payload: dict, profile_payload: dict | None = None) -> PluginContext:
    project_manifest = tmp_path / "project.yaml"
    project_manifest.write_text(yaml.safe_dump(project_payload, sort_keys=False), encoding="utf-8")

    profiles_root = tmp_path / "product-profiles"
    bundles_root = tmp_path / "product-bundles"
    profiles_root.mkdir(parents=True, exist_ok=True)
    bundles_root.mkdir(parents=True, exist_ok=True)

    _write_bundle(bundles_root / "bundle.edge-routing.yaml", "bundle.edge-routing")
    _write_bundle(bundles_root / "bundle.network-segmentation.yaml", "bundle.network-segmentation")
    _write_bundle(bundles_root / "bundle.secrets-governance.yaml", "bundle.secrets-governance")
    _write_bundle(bundles_root / "bundle.remote-access.yaml", "bundle.remote-access")

    if profile_payload is not None:
        (profiles_root / "soho.standard.v1.yaml").write_text(
            yaml.safe_dump(profile_payload, sort_keys=False),
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
            "project_manifest_path": str(project_manifest),
            "product_profiles_root": str(profiles_root),
            "product_bundles_root": str(bundles_root),
        },
    )


def test_resolver_reports_legacy_when_product_profile_is_missing(tmp_path: Path) -> None:
    compiler = SohoProfileResolverCompiler("base.compiler.soho_profile_resolver")
    ctx = _ctx(tmp_path, {"project": "home-lab"})

    result = compiler.execute(ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert result.output_data["profile_present"] is False
    assert result.output_data["required_bundles"] == []


def test_resolver_computes_required_bundles_from_canonical_profile(tmp_path: Path) -> None:
    compiler = SohoProfileResolverCompiler("base.compiler.soho_profile_resolver")
    ctx = _ctx(
        tmp_path,
        {
            "project": "home-lab",
            "product_profile": {
                "profile_id": "soho.standard.v1",
                "deployment_class": "starter",
                "migration_state": "migrated-soft",
            },
        },
        profile_payload={
            "schema_version": 1,
            "profile_id": "soho.standard.v1",
            "core_required_bundles": [
                "bundle.edge-routing",
                "bundle.network-segmentation",
                "bundle.secrets-governance",
            ],
            "deployment_classes": {
                "starter": {
                    "required_bundles": ["bundle.remote-access"],
                }
            },
        },
    )

    result = compiler.execute(ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert result.output_data["profile_present"] is True
    assert set(result.output_data["required_bundles"]) == {
        "bundle.edge-routing",
        "bundle.network-segmentation",
        "bundle.secrets-governance",
        "bundle.remote-access",
    }
    assert result.output_data["missing_bundle_definitions"] == []

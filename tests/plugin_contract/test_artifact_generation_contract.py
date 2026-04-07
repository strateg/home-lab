#!/usr/bin/env python3
"""Contract checks for ADR0093 artifact planning/report schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.artifact_contract import (  # noqa: E402
    build_artifact_plan,
    build_generation_report,
    build_planned_output,
    compute_obsolete_entries,
    save_current_plan,
)
from kernel.plugin_base import PluginContext  # noqa: E402


def _load_schema(name: str) -> dict:
    schema_path = REPO_ROOT / "schemas" / name
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_artifact_plan_schema_accepts_helper_payload() -> None:
    schema = _load_schema("artifact-plan.schema.json")
    plan = build_artifact_plan(
        plugin_id="base.generator.ansible_inventory",
        artifact_family="ansible.inventory",
        planned_outputs=[
            build_planned_output(
                path="generated/home-lab/ansible/inventory/production/hosts.yml",
                template="ansible/inventory/hosts.yml.j2",
                reason="base-family",
            )
        ],
        capabilities=["has_inventory"],
        validation_profiles=["production"],
    )
    jsonschema.validate(plan, schema)


def test_artifact_generation_report_schema_accepts_helper_payload() -> None:
    schema = _load_schema("artifact-generation-report.schema.json")
    planned = [
        build_planned_output(
            path="generated/home-lab/terraform/proxmox/provider.tf",
            template="terraform/provider.tf.j2",
            reason="base-family",
        )
    ]
    report = build_generation_report(
        plugin_id="object.proxmox.generator.terraform",
        artifact_family="terraform.proxmox",
        planned_outputs=planned,
        generated=["generated/home-lab/terraform/proxmox/provider.tf"],
    )
    jsonschema.validate(report, schema)


def test_artifact_plan_schema_rejects_missing_planned_outputs() -> None:
    schema = _load_schema("artifact-plan.schema.json")
    invalid_payload = {
        "schema_version": "1.0",
        "plugin_id": "object.proxmox.generator.terraform",
        "artifact_family": "terraform.proxmox",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_payload, schema)


def _ctx(tmp_path: Path, **config: str) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        output_dir=str(tmp_path / "build"),
        config=config,
    )


def test_compute_obsolete_entries_defaults_to_warn_and_proves_by_prefix(tmp_path: Path) -> None:
    output_root = tmp_path / "generated" / "terraform" / "proxmox"
    output_root.mkdir(parents=True, exist_ok=True)
    stale_file = output_root / "stale.tf"
    stale_file.write_text("# old file\n", encoding="utf-8")

    planned = [
        build_planned_output(
            path=str(output_root / "provider.tf"),
            template="terraform/provider.tf.j2",
            reason="base-family",
        )
    ]

    entries, errors = compute_obsolete_entries(
        ctx=_ctx(tmp_path),
        plugin_id="object.proxmox.generator.terraform",
        output_root=output_root,
        planned_outputs=planned,
    )
    assert errors == []
    assert len(entries) == 1
    assert entries[0]["path"] == str(stale_file.resolve())
    assert entries[0]["action"] == "warn"
    assert entries[0]["ownership_proven"] is True
    assert entries[0]["ownership_method"] == "output_prefix_match"


def test_compute_obsolete_entries_blocks_delete_without_ownership_proof(tmp_path: Path) -> None:
    output_root = tmp_path / "generated" / "terraform" / "proxmox"
    output_root.mkdir(parents=True, exist_ok=True)
    stale_file = output_root / "stale.tf"
    stale_file.write_text("# old file\n", encoding="utf-8")

    planned = [
        build_planned_output(
            path=str(output_root / "provider.tf"),
            template="terraform/provider.tf.j2",
            reason="base-family",
        )
    ]
    ctx = _ctx(tmp_path, artifact_obsolete_action="delete")

    entries, errors = compute_obsolete_entries(
        ctx=ctx,
        plugin_id="object.proxmox.generator.terraform",
        output_root=output_root,
        planned_outputs=planned,
        ownership_prefix=str(tmp_path / "some-other-prefix"),
    )
    assert len(entries) == 1
    assert entries[0]["action"] == "warn"
    assert entries[0]["ownership_proven"] is False
    assert entries[0]["ownership_method"] == "none"
    assert len(errors) == 1
    assert "without ownership proof" in errors[0]


def test_compute_obsolete_entries_uses_previous_plan_proof(tmp_path: Path) -> None:
    output_root = tmp_path / "generated" / "ansible" / "inventory" / "production"
    output_root.mkdir(parents=True, exist_ok=True)
    stale_file = output_root / "hosts.yml"
    stale_file.write_text("# old file\n", encoding="utf-8")

    plugin_id = "base.generator.ansible_inventory"
    ctx = _ctx(tmp_path, artifact_obsolete_action="delete")
    previous_plan = build_artifact_plan(
        plugin_id=plugin_id,
        artifact_family="ansible.inventory",
        planned_outputs=[build_planned_output(path=str(stale_file))],
    )
    save_current_plan(ctx=ctx, plugin_id=plugin_id, artifact_plan=previous_plan)

    entries, errors = compute_obsolete_entries(
        ctx=ctx,
        plugin_id=plugin_id,
        output_root=output_root,
        planned_outputs=[
            build_planned_output(path=str(output_root / "group_vars" / "all.yml")),
        ],
        ownership_prefix=str(tmp_path / "unrelated-prefix"),
    )

    assert errors == []
    assert len(entries) == 1
    assert entries[0]["action"] == "delete"
    assert entries[0]["ownership_proven"] is True
    assert entries[0]["ownership_method"] == "previous_plan_match"

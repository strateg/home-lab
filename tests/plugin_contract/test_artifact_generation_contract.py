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
)


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

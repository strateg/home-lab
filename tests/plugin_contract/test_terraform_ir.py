#!/usr/bin/env python3
"""Contract checks for ADR0092 Terraform typed IR helpers."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.terraform_ir import build_terraform_module_family_ir  # noqa: E402


def test_build_terraform_ir_is_order_independent_for_templates() -> None:
    first = {
        "provider.tf": "terraform/provider.tf.j2",
        "backend.tf": "terraform/backend.tf.j2",
        "qos.tf": "terraform/qos.tf.j2",
    }
    second = {
        "qos.tf": "terraform/qos.tf.j2",
        "provider.tf": "terraform/provider.tf.j2",
        "backend.tf": "terraform/backend.tf.j2",
    }
    capability_templates = {"qos.tf": "terraform/qos.tf.j2"}

    ir_a = build_terraform_module_family_ir(
        artifact_family="terraform.mikrotik",
        templates=first,
        capability_templates=capability_templates,
        remote_state_enabled=True,
        capability_flags=["has_qos", "has_wireguard"],
    )
    ir_b = build_terraform_module_family_ir(
        artifact_family="terraform.mikrotik",
        templates=second,
        capability_templates=capability_templates,
        remote_state_enabled=True,
        capability_flags=["has_wireguard", "has_qos"],
    )

    assert ir_a.to_dict() == ir_b.to_dict()
    reasons = {item.filename: item.reason for item in ir_a.planned_files}
    assert reasons["provider.tf"] == "base-family"
    assert reasons["backend.tf"] == "dependency-enabled"
    assert reasons["qos.tf"] == "capability-enabled"

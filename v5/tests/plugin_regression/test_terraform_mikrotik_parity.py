#!/usr/bin/env python3
"""Parity checks for v5 MikroTik Terraform artifacts vs v4 baseline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_MIKROTIK = REPO_ROOT / "v4-generated" / "terraform" / "mikrotik"


def _file_set(path: Path) -> set[str]:
    return {item.name for item in path.iterdir() if item.is_file()}


def test_terraform_mikrotik_file_set_matches_v4_baseline(generated_artifacts_root: Path) -> None:
    v5_mikrotik = generated_artifacts_root / "terraform" / "mikrotik"
    assert v5_mikrotik.exists(), "v5 mikrotik terraform directory missing"
    assert V4_MIKROTIK.exists(), "v4 mikrotik terraform baseline missing"
    actual = _file_set(v5_mikrotik)
    baseline = _file_set(V4_MIKROTIK)
    optional = {"qos.tf", "vpn.tf", "containers.tf"}
    assert actual - optional == baseline - optional


def test_terraform_mikrotik_semantic_contract(generated_artifacts_root: Path) -> None:
    v5_mikrotik = generated_artifacts_root / "terraform" / "mikrotik"
    provider_tf = (v5_mikrotik / "provider.tf").read_text(encoding="utf-8")
    variables_tf = (v5_mikrotik / "variables.tf").read_text(encoding="utf-8")
    tfvars_example = (v5_mikrotik / "terraform.tfvars.example").read_text(encoding="utf-8")

    assert 'provider "routeros"' in provider_tf
    assert "required_providers" in provider_tf
    assert 'source  = "terraform-routeros/routeros"' in provider_tf
    assert 'variable "mikrotik_password"' in variables_tf
    assert "<TODO_MIKROTIK_PASSWORD>" in tfvars_example


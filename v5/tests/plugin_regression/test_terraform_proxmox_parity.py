#!/usr/bin/env python3
"""Parity checks for v5 Proxmox Terraform artifacts vs v4 baseline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_PROXMOX = REPO_ROOT / "v4-generated" / "terraform" / "proxmox"


def _file_set(path: Path) -> set[str]:
    return {item.name for item in path.iterdir() if item.is_file()}


def test_terraform_proxmox_file_set_matches_v4_baseline(generated_artifacts_root: Path) -> None:
    v5_proxmox = generated_artifacts_root / "terraform" / "proxmox"
    assert v5_proxmox.exists(), "v5 proxmox terraform directory missing"
    assert V4_PROXMOX.exists(), "v4 proxmox terraform baseline missing"
    assert _file_set(v5_proxmox) == _file_set(V4_PROXMOX)


def test_terraform_proxmox_semantic_contract(generated_artifacts_root: Path) -> None:
    v5_proxmox = generated_artifacts_root / "terraform" / "proxmox"
    provider_tf = (v5_proxmox / "provider.tf").read_text(encoding="utf-8")
    versions_tf = (v5_proxmox / "versions.tf").read_text(encoding="utf-8")
    tfvars_example = (v5_proxmox / "terraform.tfvars.example").read_text(encoding="utf-8")

    assert 'provider "proxmox"' in provider_tf
    assert "endpoint  = var.proxmox_api_url" in provider_tf
    assert "required_providers" in versions_tf
    assert "source  = \"bpg/proxmox\"" in versions_tf
    assert "<TODO_PROXMOX_API_TOKEN>" in tfvars_example


#!/usr/bin/env python3
"""Integration checks for TUC-0003 MikroTik live parity drift gate."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "MIKROTIK-TERRAFORM-DRIFT-CHECK.md"


def _run_compile(workdir: Path) -> tuple[int, str]:
    workdir = workdir.resolve()
    generated_root = workdir / "generated"
    output_json = workdir / "effective.json"
    diagnostics_json = workdir / "diagnostics.json"
    diagnostics_txt = workdir / "diagnostics.txt"
    cmd = [
        "python3",
        str(COMPILER),
        "--topology",
        str(TOPOLOGY.relative_to(REPO_ROOT).as_posix()),
        "--secrets-mode",
        "passthrough",
        "--artifacts-root",
        str(generated_root.relative_to(REPO_ROOT).as_posix()),
        "--output-json",
        str(output_json.relative_to(REPO_ROOT).as_posix()),
        "--diagnostics-json",
        str(diagnostics_json.relative_to(REPO_ROOT).as_posix()),
        "--diagnostics-txt",
        str(diagnostics_txt.relative_to(REPO_ROOT).as_posix()),
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return completed.returncode, completed.stdout + "\n" + completed.stderr


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_tuc0003_runbook_exists() -> None:
    assert RUNBOOK.exists(), f"missing runbook: {RUNBOOK}"
    content = _read(RUNBOOK)
    assert "MikroTik Terraform Drift Check" in content
    assert "generator-gap" in content


def test_tuc0003_compile_emits_mikrotik_domain_files(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-tuc0003" / f"{tmp_path.name}-compile"
    workdir.mkdir(parents=True, exist_ok=True)

    code, output = _run_compile(workdir)
    assert code == 0, output

    mikrotik_dir = workdir / "generated" / "home-lab" / "terraform" / "mikrotik"
    assert mikrotik_dir.exists()

    expected = {
        "interfaces.tf",
        "addresses.tf",
        "dhcp.tf",
        "dns.tf",
        "firewall.tf",
        "provider.tf",
        "variables.tf",
        "outputs.tf",
    }
    actual = {path.name for path in mikrotik_dir.glob("*.tf")}
    assert expected.issubset(actual)


def test_tuc0003_compile_contains_topology_and_runtime_markers(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-tuc0003" / f"{tmp_path.name}-markers"
    workdir.mkdir(parents=True, exist_ok=True)

    code, output = _run_compile(workdir)
    assert code == 0, output

    mikrotik_dir = workdir / "generated" / "home-lab" / "terraform" / "mikrotik"
    interfaces = _read(mikrotik_dir / "interfaces.tf")
    addresses = _read(mikrotik_dir / "addresses.tf")
    dhcp = _read(mikrotik_dir / "dhcp.tf")
    dns = _read(mikrotik_dir / "dns.tf")
    firewall = _read(mikrotik_dir / "firewall.tf")

    assert 'resource "routeros_interface_bridge"' in interfaces
    assert 'resource "routeros_interface_vlan" "guest"' in interfaces
    assert 'resource "routeros_interface_vlan" "iot"' in interfaces

    assert 'resource "routeros_ip_address"' in addresses
    assert "192.168.88.1/24" in addresses

    assert 'resource "routeros_ip_dhcp_server" "lan_dhcp"' in dhcp
    assert 'resource "routeros_ip_dhcp_server_network" "lan_network"' in dhcp

    assert 'resource "routeros_ip_dns" "settings"' in dns

    assert 'resource "routeros_ip_firewall_filter"' in firewall
    assert 'resource "routeros_ip_firewall_nat" "runtime_nat_1"' in firewall


def test_tuc0003_effective_payload_keeps_mikrotik_observed_runtime(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-tuc0003" / f"{tmp_path.name}-effective"
    workdir.mkdir(parents=True, exist_ok=True)

    code, output = _run_compile(workdir)
    assert code == 0, output

    effective = json.loads((workdir / "effective.json").read_text(encoding="utf-8"))
    rows = effective.get("instances", {}).get("devices", [])
    assert isinstance(rows, list)

    row = next((item for item in rows if item.get("instance_id") == "rtr-mikrotik-chateau"), None)
    assert isinstance(row, dict)
    instance_data = row.get("instance_data", {})
    assert isinstance(instance_data, dict)
    observed_runtime = instance_data.get("observed_runtime", {})
    assert isinstance(observed_runtime, dict)
    assert "nat" in observed_runtime
    assert "dns" in observed_runtime

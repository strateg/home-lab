#!/usr/bin/env python3
"""Integration checks for TUC-0002 Terraform generator onboarding."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"

EXPECTED_TERRAFORM_PLUGIN_IDS = {
    "object.mikrotik.generator.terraform",
    "object.proxmox.generator.terraform",
}
EXPECTED_TERRAFORM_CORE_FILES = {
    "object.mikrotik.generator.terraform": {
        "provider.tf",
        "interfaces.tf",
        "firewall.tf",
        "dhcp.tf",
        "dns.tf",
        "addresses.tf",
        "variables.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    },
    "object.proxmox.generator.terraform": {
        "versions.tf",
        "provider.tf",
        "variables.tf",
        "bridges.tf",
        "lxc.tf",
        "vms.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    },
}


def _list_plugin_ids(manifest_path: Path) -> set[str]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return set()
    out: set[str] = set()
    for row in plugins:
        if not isinstance(row, dict):
            continue
        plugin_id = row.get("id")
        if isinstance(plugin_id, str) and plugin_id.strip():
            out.add(plugin_id.strip())
    return out


def test_tuc0002_expected_terraform_generators_exist_in_manifests() -> None:
    manifest_paths = [
        REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml",
        *sorted((REPO_ROOT / "topology" / "object-modules").glob("*/plugins.yaml")),
    ]
    discovered: set[str] = set()
    for manifest in manifest_paths:
        if manifest.exists():
            discovered.update(_list_plugin_ids(manifest))

    missing = sorted(EXPECTED_TERRAFORM_PLUGIN_IDS - discovered)
    assert not missing, f"missing expected terraform plugin ids: {missing}"


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
        "--strict-model-lock",
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


def _hash_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[rel] = digest
    return out


def test_tuc0002_compile_publishes_terraform_artifact_contracts(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-tuc0002" / f"{tmp_path.name}-contracts"
    workdir.mkdir(parents=True, exist_ok=True)
    code, output = _run_compile(workdir)
    assert code == 0, output

    contracts_root = workdir / "artifact-contracts"
    for plugin_id in sorted(EXPECTED_TERRAFORM_PLUGIN_IDS):
        plugin_dir = contracts_root / plugin_id.replace(".", "__")
        plan_path = plugin_dir / "artifact-plan.json"
        report_path = plugin_dir / "artifact-generation-report.json"
        assert plan_path.exists(), f"missing plan file for {plugin_id}"
        assert report_path.exists(), f"missing report file for {plugin_id}"

        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert plan.get("plugin_id") == plugin_id
        assert report.get("plugin_id") == plugin_id
        assert str(plan.get("artifact_family", "")).startswith("terraform.")
        assert str(report.get("artifact_family", "")).startswith("terraform.")
        assert int(report.get("summary", {}).get("generated_count", 0)) > 0


def test_tuc0002_terraform_outputs_are_deterministic(tmp_path: Path) -> None:
    run1 = REPO_ROOT / "build" / "test-tuc0002" / f"{tmp_path.name}-run1"
    run2 = REPO_ROOT / "build" / "test-tuc0002" / f"{tmp_path.name}-run2"
    run1.mkdir(parents=True, exist_ok=True)
    run2.mkdir(parents=True, exist_ok=True)

    code1, output1 = _run_compile(run1)
    code2, output2 = _run_compile(run2)
    assert code1 == 0, output1
    assert code2 == 0, output2

    tree1 = _hash_tree(run1 / "generated" / "terraform")
    tree2 = _hash_tree(run2 / "generated" / "terraform")
    assert tree1 == tree2


def test_tuc0002_terraform_semantic_file_contract_and_renderers(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-tuc0002" / f"{tmp_path.name}-semantic"
    workdir.mkdir(parents=True, exist_ok=True)
    code, output = _run_compile(workdir)
    assert code == 0, output

    contracts_root = workdir / "artifact-contracts"
    generated_root = workdir / "generated" / "home-lab" / "terraform"

    for plugin_id in sorted(EXPECTED_TERRAFORM_PLUGIN_IDS):
        plugin_dir = contracts_root / plugin_id.replace(".", "__")
        plan = json.loads((plugin_dir / "artifact-plan.json").read_text(encoding="utf-8"))

        planned = plan.get("planned_outputs", [])
        assert isinstance(planned, list) and planned
        renderers = {str(item.get("renderer", "")) for item in planned if isinstance(item, dict)}
        assert renderers.issubset({"jinja2", "programmatic"})

        backend_rows = [
            item
            for item in planned
            if isinstance(item, dict) and str(item.get("path", "")).endswith("/backend.tf")
        ]
        for row in backend_rows:
            assert row.get("renderer") == "programmatic"

        family_dir = "mikrotik" if "mikrotik" in plugin_id else "proxmox"
        actual_files = {path.name for path in (generated_root / family_dir).glob("*.tf*")}
        assert EXPECTED_TERRAFORM_CORE_FILES[plugin_id].issubset(actual_files)

#!/usr/bin/env python3
"""Integration checks for TUC-0002 Terraform generator onboarding."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import yaml
from tests.helpers.plugin_execution import run_plugin_for_test

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"
V5_TOOLS = REPO_ROOT / "topology-tools"

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


def _load_generator_class(module_rel: str, class_name: str):
    module_path = REPO_ROOT / module_rel
    spec = importlib.util.spec_from_file_location(f"tuc0002_{class_name}", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def _semanticize(compiled_json: dict) -> dict:
    payload = copy.deepcopy(compiled_json)
    instances = payload.get("instances")
    if not isinstance(instances, dict):
        return payload
    for rows in instances.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            object_ref = row.pop("object_ref", None)
            class_ref = row.pop("class_ref", None)
            if not isinstance(object_ref, str) and not isinstance(class_ref, str):
                continue
            instance_block = row.get("instance")
            if not isinstance(instance_block, dict):
                instance_block = {}
                row["instance"] = instance_block
            if isinstance(object_ref, str) and object_ref:
                instance_block.setdefault("materializes_object", object_ref)
            if isinstance(class_ref, str) and class_ref:
                instance_block.setdefault("materializes_class", class_ref)
    return payload


def _plugin_ctx(tmp_path: Path, compiled_json: dict, extra_config: dict) -> object:
    import sys

    sys.path.insert(0, str(V5_TOOLS))
    from kernel.plugin_base import PluginContext  # noqa: WPS433

    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_semanticize(compiled_json),
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated"), **extra_config},
    )


def _run_generator(generator, ctx) -> object:
    import sys

    sys.path.insert(0, str(V5_TOOLS))
    from kernel.plugin_base import Stage  # noqa: WPS433

    return run_plugin_for_test(generator, ctx, Stage.GENERATE)


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
        # TUC-0002 validates generator artifact contracts and determinism.
        # Keep compile independent from unrelated model-lock governance drift.
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
            item for item in planned if isinstance(item, dict) and str(item.get("path", "")).endswith("/backend.tf")
        ]
        for row in backend_rows:
            assert row.get("renderer") == "programmatic"

        family_dir = "mikrotik" if "mikrotik" in plugin_id else "proxmox"
        actual_files = {path.name for path in (generated_root / family_dir).glob("*.tf*")}
        assert EXPECTED_TERRAFORM_CORE_FILES[plugin_id].issubset(actual_files)


def test_tuc0002_mikrotik_remote_state_backend_uses_programmatic_renderer(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(V5_TOOLS))
    from kernel.plugin_base import PluginStatus, Stage  # noqa: WPS433

    generator_class = _load_generator_class(
        "topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py",
        "TerraformMikroTikGenerator",
    )
    compiled = {
        "instances": {
            "devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}],
            "network": [],
            "services": [],
        }
    }
    ctx = _plugin_ctx(
        tmp_path,
        compiled,
        {
            "terraform_remote_state": {
                "enabled": True,
                "backend": "pg",
                "config": {"schema_name": "mikrotik", "conn_str": "postgres://terraform@db.internal/terraform_state"},
            }
        },
    )
    generator = generator_class("object.mikrotik.generator.terraform")
    result = _run_generator(generator, ctx)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data is not None
    plan_rows = result.output_data["artifact_plan"]["planned_outputs"]
    backend_entry = next(item for item in plan_rows if str(item.get("path", "")).endswith("/backend.tf"))
    assert backend_entry["renderer"] == "programmatic"
    backend_tf = (tmp_path / "generated" / "terraform" / "mikrotik" / "backend.tf").read_text(encoding="utf-8")
    assert 'backend "pg"' in backend_tf


def test_tuc0002_proxmox_remote_state_backend_uses_programmatic_renderer(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(V5_TOOLS))
    from kernel.plugin_base import PluginStatus, Stage  # noqa: WPS433

    generator_class = _load_generator_class(
        "topology/object-modules/proxmox/plugins/generators/terraform_proxmox_generator.py",
        "TerraformProxmoxGenerator",
    )
    compiled = {
        "instances": {
            "devices": [{"instance_id": "srv-gamayun", "object_ref": "obj.proxmox.ve"}],
            "lxc": [],
            "services": [],
        }
    }
    ctx = _plugin_ctx(
        tmp_path,
        compiled,
        {
            "terraform_remote_state": {
                "enabled": True,
                "backend": "s3",
                "config": {"bucket": "tf-state-home-lab", "key": "proxmox/terraform.tfstate", "encrypt": True},
            }
        },
    )
    generator = generator_class("object.proxmox.generator.terraform")
    result = _run_generator(generator, ctx)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data is not None
    plan_rows = result.output_data["artifact_plan"]["planned_outputs"]
    backend_entry = next(item for item in plan_rows if str(item.get("path", "")).endswith("/backend.tf"))
    assert backend_entry["renderer"] == "programmatic"
    backend_tf = (tmp_path / "generated" / "terraform" / "proxmox" / "backend.tf").read_text(encoding="utf-8")
    assert 'backend "s3"' in backend_tf

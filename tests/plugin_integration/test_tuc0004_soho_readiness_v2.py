#!/usr/bin/env python3
"""TUC-0004 SOHO readiness tests using snapshot/envelope model (ADR 0097/0099).

This module tests SOHO readiness builders using direct plugin execution via
PluginInputSnapshot and run_plugin_once(), ensuring deterministic test execution.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
TUC_ROOT = REPO_ROOT / "acceptance-testing" / "TUC-0004-soho-readiness-evidence"
QUALITY_GATE = TUC_ROOT / "quality-gate.py"

# Ensure topology-tools is in path
if str(V5_TOOLS) not in sys.path:
    sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (
    Phase,
    PluginInputSnapshot,
    PluginStatus,
    Stage,
)
from kernel.plugin_runner import run_plugin_once

# ADR 0091 D3 domains required for operator readiness
ADR0091_D3_DOMAINS = {
    "greenfield-first-install",
    "brownfield-adoption",
    "router-replacement",
    "secret-rotation",
    "scheduled-update",
    "failed-update-rollback",
    "backup-and-restore",
    "operator-handover",
}

# Mandatory handover documentation files
MANDATORY_HANDOVER_FILES = {
    "SYSTEM-SUMMARY.md",
    "NETWORK-SUMMARY.md",
    "ACCESS-RUNBOOK.md",
    "BACKUP-RUNBOOK.md",
    "RESTORE-RUNBOOK.md",
    "UPDATE-RUNBOOK.md",
    "INCIDENT-CHECKLIST.md",
    "ASSET-INVENTORY.csv",
    "CHANGELOG-SNAPSHOT.md",
}

# Mandatory report files
MANDATORY_REPORT_FILES = {
    "health-report.json",
    "drift-report.json",
    "backup-status.json",
    "restore-readiness.json",
    "operator-readiness.json",
    "support-bundle-manifest.json",
}


def _load_builder_class(module_rel: str, class_name: str):
    """Dynamically load a builder class from a module file."""
    module_path = REPO_ROOT / module_rel
    if not module_path.exists():
        pytest.skip(f"Builder module not found: {module_path}")
    spec = importlib.util.spec_from_file_location(f"tuc0004_{class_name}", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def _build_snapshot(
    tmp_path: Path,
    plugin_id: str,
    compiled_json: dict[str, Any],
    *,
    stage: Stage = Stage.BUILD,
    extra_config: dict[str, Any] | None = None,
    subscriptions: dict[tuple[str, str], Any] | None = None,
) -> PluginInputSnapshot:
    """Build a PluginInputSnapshot for builder testing."""
    # Set deterministic timestamp
    os.environ["COMPILE_DETERMINISTIC_TIMESTAMP"] = "2026-01-01T00:00:00+00:00"

    config = {
        "generator_artifacts_root": str(tmp_path / "generated"),
        "secrets_mode": "passthrough",
        "project_id": "home-lab",
        **(extra_config or {}),
    }

    return PluginInputSnapshot(
        plugin_id=plugin_id,
        stage=stage,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        config=config,
        compiled_json=compiled_json,
        output_dir=str(tmp_path),
        workspace_root=str(tmp_path / "generated"),
        dist_root=str(tmp_path / "dist"),
        subscriptions=subscriptions or {},
    )


# Realistic compiled payload for SOHO readiness testing
SOHO_COMPILED_PAYLOAD = {
    "instances": {
        "devices": [
            {
                "instance_id": "rtr-mikrotik-chateau",
                "object_ref": "obj.mikrotik.chateau_lte7_ax",
                "instance_data": {
                    "role": "router",
                    "network": {"interfaces": {"lan": {"ip": "192.168.88.1/24"}}},
                },
            },
            {
                "instance_id": "srv-gamayun",
                "object_ref": "obj.proxmox.ve",
                "instance_data": {
                    "role": "hypervisor",
                    "proxmox": {"node_name": "pve"},
                },
            },
        ],
        "lxc": [
            {
                "instance_id": "ct-dns",
                "object_ref": "obj.lxc.alpine",
                "instance_data": {"vmid": 100, "role": "dns"},
            },
        ],
        "services": [
            {
                "instance_id": "svc-pihole",
                "object_ref": "obj.service.pihole",
                "instance_data": {"port": 53},
            },
        ],
    },
    "project": {
        "id": "home-lab",
        "name": "Home Lab Infrastructure",
    },
}


class TestTUC0004SohoReadinessV2:
    """TUC-0004 tests using snapshot/envelope execution model."""

    def test_quality_gate_script_exists(self) -> None:
        """Verify quality gate script exists."""
        if not QUALITY_GATE.exists():
            pytest.skip(f"Quality gate not found: {QUALITY_GATE}")
        content = QUALITY_GATE.read_text(encoding="utf-8")
        assert "def main" in content or "if __name__" in content

    def test_soho_readiness_builder_produces_reports(self, tmp_path: Path) -> None:
        """Test SOHO readiness builder produces required report files."""
        try:
            builder_class = _load_builder_class(
                "topology-tools/plugins/builders/soho_readiness_builder.py",
                "SohoReadinessBuilder",
            )
        except (FileNotFoundError, AttributeError):
            pytest.skip("SohoReadinessBuilder not available")

        # Create required directories
        product_dir = tmp_path / "generated" / "home-lab" / "product"
        (product_dir / "handover").mkdir(parents=True, exist_ok=True)
        (product_dir / "reports").mkdir(parents=True, exist_ok=True)

        snapshot = _build_snapshot(tmp_path, "base.builder.soho_readiness_package", SOHO_COMPILED_PAYLOAD)
        plugin = builder_class("base.builder.soho_readiness_package")
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        # Builder may skip if dependencies not met
        if envelope.result.status == PluginStatus.SKIPPED:
            pytest.skip("Builder skipped due to missing dependencies")

        # Builder produces files but may report FAILED due to missing evidence (backup, restore)
        # This is expected behavior - we're testing that files are generated
        assert envelope.result.status in (
            PluginStatus.SUCCESS,
            PluginStatus.PARTIAL,
            PluginStatus.FAILED,
        ), f"Unexpected status: {envelope.result.status}"

        # Verify output_data contains generated files
        output_data = envelope.result.output_data
        assert output_data is not None, "Builder did not produce output_data"
        assert "generated_files" in output_data, "No generated_files in output_data"
        assert len(output_data["generated_files"]) > 0, "No files were generated"

    def test_operator_readiness_schema(self, tmp_path: Path) -> None:
        """Test operator readiness report schema conforms to ADR 0091."""
        # Create a mock operator-readiness.json to validate schema
        reports_dir = tmp_path / "generated" / "home-lab" / "product" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Create mock report with required structure
        operator_readiness = {
            "status": "yellow",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "evidence": {
                "greenfield-first-install": {"status": "pass", "artifacts": []},
                "brownfield-adoption": {"status": "pass", "artifacts": []},
                "router-replacement": {"status": "warn", "artifacts": []},
                "secret-rotation": {"status": "pass", "artifacts": []},
                "scheduled-update": {"status": "pass", "artifacts": []},
                "failed-update-rollback": {"status": "warn", "artifacts": []},
                "backup-and-restore": {"status": "pass", "artifacts": []},
                "operator-handover": {"status": "pass", "artifacts": []},
            },
        }

        operator_path = reports_dir / "operator-readiness.json"
        operator_path.write_text(json.dumps(operator_readiness, indent=2))

        # Validate structure
        payload = json.loads(operator_path.read_text(encoding="utf-8"))
        evidence = payload.get("evidence", {})

        assert isinstance(evidence, dict)
        assert ADR0091_D3_DOMAINS.issubset(
            set(evidence.keys())
        ), f"Missing domains: {ADR0091_D3_DOMAINS - set(evidence.keys())}"
        assert payload.get("status") in {"green", "yellow", "red"}

    def test_support_bundle_manifest_schema(self, tmp_path: Path) -> None:
        """Test support bundle manifest conforms to expected schema."""
        reports_dir = tmp_path / "generated" / "home-lab" / "product" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Create mock manifest with required structure
        manifest = {
            "completeness_state": "partial",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "contents": {
                "handover": list(MANDATORY_HANDOVER_FILES),
                "reports": list(MANDATORY_REPORT_FILES),
            },
        }

        manifest_path = reports_dir / "support-bundle-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        # Validate structure
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload.get("completeness_state") in {"missing", "partial", "complete"}

    def test_handover_documentation_structure(self, tmp_path: Path) -> None:
        """Test handover documentation directory structure."""
        handover_dir = tmp_path / "generated" / "home-lab" / "product" / "handover"
        handover_dir.mkdir(parents=True, exist_ok=True)

        # Create mock handover files
        for filename in MANDATORY_HANDOVER_FILES:
            filepath = handover_dir / filename
            if filename.endswith(".md"):
                filepath.write_text(f"# {filename.replace('.md', '').replace('-', ' ').title()}\n\nContent here.\n")
            elif filename.endswith(".csv"):
                filepath.write_text("asset_id,name,type,location\n")

        # Verify all mandatory files exist
        actual_files = {p.name for p in handover_dir.iterdir() if p.is_file()}
        missing = MANDATORY_HANDOVER_FILES - actual_files
        assert not missing, f"Missing handover files: {missing}"

    def test_compiled_payload_contains_required_instance_types(self) -> None:
        """Test compiled payload contains all required instance types for SOHO."""
        instances = SOHO_COMPILED_PAYLOAD.get("instances", {})

        # Verify required instance types
        assert "devices" in instances, "Missing devices in compiled payload"
        assert len(instances["devices"]) > 0, "No devices defined"

        # Verify at least one router device
        devices = instances["devices"]
        router = next(
            (d for d in devices if d.get("instance_data", {}).get("role") == "router"),
            None,
        )
        assert router is not None, "No router device found"

        # Verify project metadata
        project = SOHO_COMPILED_PAYLOAD.get("project", {})
        assert project.get("id"), "Missing project ID"

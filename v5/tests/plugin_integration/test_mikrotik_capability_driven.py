#!/usr/bin/env python3
"""Tests for capability-driven MikroTik Terraform generation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage  # noqa: E402
from plugins.generators.projections import (  # noqa: E402
    _derive_mikrotik_capability_flags,
    _extract_capabilities,
    build_mikrotik_projection,
)

def _load_generator_class():
    module_path = V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "terraform_mikrotik_generator.py"
    spec = importlib.util.spec_from_file_location("test_object_mikrotik_terraform_generator", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerraformMikroTikGenerator


TerraformMikroTikGenerator = _load_generator_class()


class TestCapabilityExtraction:
    """Tests for capability extraction helpers."""

    def test_extract_capabilities_from_list(self) -> None:
        row = {
            "instance_id": "rtr-test",
            "capabilities": [
                "cap.net.overlay.vpn.wireguard.server",
                "cap.net.platform.containers",
            ],
        }
        caps = _extract_capabilities(row)
        assert "cap.net.overlay.vpn.wireguard.server" in caps
        assert "cap.net.platform.containers" in caps

    def test_extract_capabilities_from_derived(self) -> None:
        row = {
            "instance_id": "rtr-test",
            "derived_capabilities": ["cap.os.routeros", "cap.arch.arm64"],
        }
        caps = _extract_capabilities(row)
        assert "cap.os.routeros" in caps
        assert "cap.arch.arm64" in caps

    def test_extract_capabilities_empty(self) -> None:
        row = {"instance_id": "rtr-test"}
        caps = _extract_capabilities(row)
        assert caps == set()

    def test_extract_capabilities_mixed(self) -> None:
        row = {
            "instance_id": "rtr-test",
            "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
            "derived_capabilities": ["cap.os.routeros"],
        }
        caps = _extract_capabilities(row)
        assert len(caps) == 2


class TestMikroTikCapabilityFlags:
    """Tests for capability flag derivation."""

    def test_wireguard_capability_flag(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
                "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_wireguard"] is True
        assert flags["has_containers"] is False

    def test_containers_capability_flag(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
                "capabilities": ["cap.net.platform.containers"],
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_containers"] is True
        assert flags["has_wireguard"] is False

    def test_chateau_implicit_capabilities(self) -> None:
        """Chateau models have implicit LTE and containers support."""
        routers = [
            {
                "instance_id": "rtr-mikrotik-chateau",
                "object_ref": "obj.mikrotik.chateau_lte7_ax",
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_containers"] is True
        assert flags["has_lte"] is True

    def test_qos_capability_flags(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
                "capabilities": ["cap.net.l3.qos.advanced"],
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_qos_advanced"] is True
        assert flags["has_qos_basic"] is False

    def test_no_capabilities(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_wireguard"] is False
        assert flags["has_containers"] is False
        assert flags["has_qos_basic"] is False


class TestMikroTikProjectionCapabilities:
    """Tests for capability flags in MikroTik projection."""

    def test_projection_includes_capabilities(self) -> None:
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        projection = build_mikrotik_projection(compiled_json)
        assert "capabilities" in projection
        assert projection["capabilities"]["has_wireguard"] is True

    def test_projection_does_not_use_legacy_group_names(self) -> None:
        compiled_json = {
            "instances": {
                "l1_devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
                    }
                ],
                "l2_network": [],
                "l5_services": [],
            }
        }
        projection = build_mikrotik_projection(compiled_json)
        assert projection["counts"]["routers"] == 0
        assert projection["capabilities"]["has_wireguard"] is False


class TestMikroTikGeneratorCapabilityDriven:
    """Tests for capability-driven file generation."""

    def _ctx(self, tmp_path: Path, compiled_json: dict) -> PluginContext:
        return PluginContext(
            topology_path="v5/topology/topology.yaml",
            profile="test",
            model_lock={},
            compiled_json=compiled_json,
            output_dir=str(tmp_path / "build"),
            config={"generator_artifacts_root": str(tmp_path / "generated")},
        )

    def test_generates_vpn_tf_when_wireguard_capability(
        self, tmp_path: Path
    ) -> None:
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = generator.execute(ctx, Stage.GENERATE)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        assert "vpn.tf" in generated_files

    def test_skips_vpn_tf_without_wireguard_capability(
        self, tmp_path: Path
    ) -> None:
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        # No wireguard capability
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = generator.execute(ctx, Stage.GENERATE)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        assert "vpn.tf" not in generated_files

    def test_generates_containers_tf_for_chateau(self, tmp_path: Path) -> None:
        """Chateau models should generate containers.tf (implicit capability)."""
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-mikrotik-chateau",
                        "object_ref": "obj.mikrotik.chateau_lte7_ax",
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = generator.execute(ctx, Stage.GENERATE)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        assert "containers.tf" in generated_files

    def test_core_files_always_generated(self, tmp_path: Path) -> None:
        """Core Terraform files should always be generated."""
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = generator.execute(ctx, Stage.GENERATE)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        # Core files should always exist
        assert "provider.tf" in generated_files
        assert "interfaces.tf" in generated_files
        assert "firewall.tf" in generated_files
        assert "variables.tf" in generated_files
        assert "outputs.tf" in generated_files

#!/usr/bin/env python3
# ADR: 0106
"""Tests for capability-driven MikroTik Terraform generation."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage  # noqa: E402
from plugins.generators.object_projection_loader import load_object_projection_module  # noqa: E402

_MIKROTIK_PROJECTIONS = load_object_projection_module("mikrotik")
_raw_build_mikrotik_projection = _MIKROTIK_PROJECTIONS.build_mikrotik_projection


def _load_capability_flags_module():
    # W07 migration order item 1: capability-flag derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin. Unit
    # tests of the derivation logic itself now load it from there.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "capability_flags_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_capability_flags_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CAPABILITY_FLAGS_MODULE = _load_capability_flags_module()
_derive_mikrotik_capability_flags = _CAPABILITY_FLAGS_MODULE._derive_capability_flags
_extract_capabilities = _CAPABILITY_FLAGS_MODULE._extract_capabilities
_resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref


def _load_wireguard_tunnels_module():
    # W07 migration order item 4a: WireGuard tunnel derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "wireguard_tunnels_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_wireguard_tunnels_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_WIREGUARD_TUNNELS_MODULE = _load_wireguard_tunnels_module()
_extract_wireguard_tunnels = _WIREGUARD_TUNNELS_MODULE._extract_wireguard_tunnels

# The producer the manifest lets this generator subscribe to. Both of its keys -
# `security_matrices` and `vlan_cidr_map` - are declared `required: true`, because
# the projection derives no substitute for either.
_SECURITY_MATRIX_COMPILER = "base.compiler.security_matrix"
_CAPABILITY_FLAGS_COMPILER = "object.mikrotik.compiler.capability_flags"
_WIREGUARD_TUNNELS_COMPILER = "object.mikrotik.compiler.wireguard_tunnels"
_CONSUMED_KEYS = (_SECURITY_MATRIX_COMPILER, _CAPABILITY_FLAGS_COMPILER, _WIREGUARD_TUNNELS_COMPILER)


def _mikrotik_routers_and_network(compiled_json: dict) -> tuple[set[str], list[dict]]:
    semantic = _semanticize(compiled_json)
    instances = semantic.get("instances")
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    network_rows = instances.get("network", []) if isinstance(instances, dict) else []
    router_ids = {
        row.get("instance_id")
        for row in devices
        if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
    }
    return {r for r in router_ids if isinstance(r, str) and r}, [r for r in network_rows if isinstance(r, dict)]


def _derive_flags_for_fixture(compiled_json: dict) -> dict:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 1)."""
    semantic = _semanticize(compiled_json)
    instances = semantic.get("instances")
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    routers = [
        row for row in devices if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    return _derive_mikrotik_capability_flags(routers)


def _derive_wireguard_tunnels_for_fixture(compiled_json: dict) -> dict:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4a)."""
    router_ids, network_rows = _mikrotik_routers_and_network(compiled_json)
    return _extract_wireguard_tunnels(network_rows, router_ids, {})


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


def build_mikrotik_projection(compiled_json: dict, **kwargs) -> dict:
    """Channels stated empty: these fixtures declare no matrices and no domains.

    They are required arguments now - the projection derives no substitute for
    `base.compiler.security_matrix` - so omission is an error and `{}` is a claim.

    `capability_flags` (W07 migration order item 1) and `wireguard_tunnels`
    (W07 migration order item 4a) are likewise required and are auto-derived
    here from the same devices/network rows the real compile-stage compiler
    plugins read, unless a test passes its own value to exercise a specific case.
    """
    semantic = _semanticize(compiled_json)
    kwargs.setdefault("composed_matrices_by_enforcer", {})
    kwargs.setdefault("vlan_cidr_map", {})
    if "capability_flags" not in kwargs:
        instances = semantic.get("instances")
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        routers = [
            row for row in devices if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
        ]
        kwargs["capability_flags"] = _derive_mikrotik_capability_flags(routers)
    if "wireguard_tunnels" not in kwargs:
        router_ids, network_rows = _mikrotik_routers_and_network(compiled_json)
        kwargs["wireguard_tunnels"] = _extract_wireguard_tunnels(network_rows, router_ids, {})
    return _raw_build_mikrotik_projection(semantic, **kwargs)


def _load_generator_class():
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "generators"
        / "terraform_mikrotik_generator.py"
    )
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
        """Chateau models have LTE and containers capabilities from object definition."""
        # ADR0078: Capabilities come from object definitions, resolved during compilation
        routers = [
            {
                "instance_id": "rtr-mikrotik-chateau",
                "object_ref": "obj.mikrotik.chateau_lte7_ax",
                # These capabilities are defined in obj.mikrotik.chateau_lte7_ax.yaml
                # and would be resolved during compilation
                "enabled_capabilities": [
                    "cap.net.platform.containers",
                    "cap.net.interface.lte",
                ],
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

    def _ctx(self, tmp_path: Path, compiled_json: dict, *, publish_channels: bool = True) -> PluginContext:
        capability_templates = {
            "qos": {"enabled_by": "capabilities.has_qos", "template": "terraform/qos.tf.j2", "output": "qos.tf"},
            "wireguard": {
                "enabled_by": "capabilities.has_wireguard",
                "template": "terraform/vpn.tf.j2",
                "output": "vpn.tf",
            },
            "containers": {
                "enabled_by": "capabilities.has_containers",
                "template": "terraform/containers.tf.j2",
                "output": "containers.tf",
            },
        }
        ctx = PluginContext(
            topology_path="topology/topology.yaml",
            profile="test",
            model_lock={},
            compiled_json=_semanticize(compiled_json),
            output_dir=str(tmp_path / "build"),
            config={
                "generator_artifacts_root": str(tmp_path / "generated"),
                "capability_templates": capability_templates,
            },
        )
        # The generator consumes these from `base.compiler.security_matrix` and
        # derives no substitute. These fixtures are about capability-driven
        # template selection, so they publish the channels empty rather than
        # leave them absent - absence is a blocked generation, which
        # `test_the_generator_blocks_when_the_compiler_published_nothing` covers.
        if publish_channels:
            for key in ("composed_matrices_by_enforcer", "vlan_cidr_map"):
                publish_for_test(ctx, _SECURITY_MATRIX_COMPILER, key, {})
            # capability_flags and wireguard_tunnels are likewise required
            # (W07 migration order items 1 and 4a). These fixtures test
            # capability-driven template selection itself, so the published
            # values must reflect the fixture's own capabilities/tunnels,
            # not an empty stand-in.
            publish_for_test(
                ctx, _CAPABILITY_FLAGS_COMPILER, "capability_flags", _derive_flags_for_fixture(compiled_json)
            )
            publish_for_test(
                ctx,
                _WIREGUARD_TUNNELS_COMPILER,
                "wireguard_tunnels",
                _derive_wireguard_tunnels_for_fixture(compiled_json),
            )
        return ctx

    def test_generates_vpn_tf_when_wireguard_capability(self, tmp_path: Path) -> None:
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

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        assert "vpn.tf" in generated_files

    def test_vpn_tf_has_no_resources_without_wireguard_capability(self, tmp_path: Path) -> None:
        """vpn.tf is always generated but contains no resources when WireGuard is disabled."""
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

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        # vpn.tf is now a core template, always generated
        assert "vpn.tf" in generated_files
        # But it should NOT contain WireGuard resources when capability is disabled
        vpn_tf = (tmp_path / "generated" / "terraform" / "mikrotik" / "vpn.tf").read_text(encoding="utf-8")
        assert "routeros_interface_wireguard" not in vpn_tf
        assert "WireGuard capability not enabled" in vpn_tf

    def test_generates_containers_tf_for_chateau(self, tmp_path: Path) -> None:
        """Chateau models should generate containers.tf when capability is present."""
        # ADR0078: Capabilities come from object definitions, resolved during compilation
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-mikrotik-chateau",
                        "object_ref": "obj.mikrotik.chateau_lte7_ax",
                        # These capabilities are defined in obj.mikrotik.chateau_lte7_ax.yaml
                        "enabled_capabilities": [
                            "cap.net.platform.containers",
                        ],
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

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

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        # Core files should always exist
        assert "provider.tf" in generated_files
        assert "interfaces.tf" in generated_files
        assert "firewall.tf" in generated_files
        assert "variables.tf" in generated_files
        assert "outputs.tf" in generated_files

    def test_the_generator_blocks_when_the_compiler_published_nothing(self, tmp_path: Path) -> None:
        """No channel, no artifacts - and no quiet success.

        The projection used to carry its own derivation of zone membership and
        address-domain CIDRs, so a missing compiler channel rendered an empty
        address list and an empty tunnel route set while the plugin reported
        SUCCESS. Both derivations are gone. This pins the replacement behaviour:
        the run fails, and it names the producer that should have published.

        In the pipeline the kernel refuses to dispatch at all, because the
        manifest declares both keys `required: true` (E8003). This test exercises
        the second guard, the one that holds for any direct caller.
        """
        compiled_json = {
            "instances": {
                "devices": [{"instance_id": "rtr-test", "object_ref": "obj.mikrotik.test"}],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json, publish_channels=False)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.FAILED
        messages = [diagnostic.message for diagnostic in result.diagnostics]
        assert any("base.compiler.security_matrix" in message for message in messages), messages
        assert not list((tmp_path / "generated").rglob("*.tf")), "artifacts were written despite the failure"

    def test_the_manifest_declares_all_four_channels_required(self) -> None:
        """`required: false` is what let the absence pass as an empty result."""
        import sys as _sys

        _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "topology-tools"))
        from yaml_loader import load_yaml_file

        manifest_path = Path(__file__).resolve().parents[2] / "topology/object-modules/mikrotik/plugins.yaml"
        manifest = load_yaml_file(manifest_path) or {}
        spec = next(item for item in manifest["plugins"] if item["id"] == "object.mikrotik.generator.terraform")
        consumes = {item["key"]: item for item in spec.get("consumes", [])}

        for key in ("composed_matrices_by_enforcer", "vlan_cidr_map"):
            assert consumes[key]["from_plugin"] == _SECURITY_MATRIX_COMPILER
            assert consumes[key]["required"] is True, f"{key} must block generation when absent"
        # W07 migration order item 1: capability_flags is required the same way.
        assert consumes["capability_flags"]["from_plugin"] == _CAPABILITY_FLAGS_COMPILER
        assert consumes["capability_flags"]["required"] is True
        # W07 migration order item 4a: wireguard_tunnels is required the same way.
        assert consumes["wireguard_tunnels"]["from_plugin"] == _WIREGUARD_TUNNELS_COMPILER
        assert consumes["wireguard_tunnels"]["required"] is True

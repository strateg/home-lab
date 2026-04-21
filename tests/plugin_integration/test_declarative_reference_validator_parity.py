#!/usr/bin/env python3
"""Parity tests between legacy refs validators and declarative validator."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext
from kernel.plugin_base import PluginDiagnostic, Stage
from plugins.validators.backup_refs_validator import BackupRefsValidator
from plugins.validators.certificate_refs_validator import CertificateRefsValidator
from plugins.validators.declarative_reference_validator import DeclarativeReferenceValidator
from plugins.validators.dns_refs_validator import DnsRefsValidator
from plugins.validators.network_core_refs_validator import NetworkCoreRefsValidator
from plugins.validators.power_source_refs_validator import PowerSourceRefsValidator
from plugins.validators.service_dependency_refs_validator import ServiceDependencyRefsValidator

from tests.helpers.plugin_execution import publish_for_test


def _context(*, config: dict[str, Any] | None = None, objects: dict[str, Any] | None = None) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config=config or {},
        classes={},
        objects=objects or {},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict[str, Any]]) -> None:
    # Test helper: simulate publish from dependency plugin
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _run(plugin: Any, ctx: PluginContext, *, plugin_id: str) -> list[PluginDiagnostic]:
    from tests.helpers.plugin_execution import run_plugin_for_test

    return run_plugin_for_test(plugin, ctx, Stage.VALIDATE, consumes_keys={"base.compiler.instance_rows"}).diagnostics


def _triple(diags: list[PluginDiagnostic]) -> set[tuple[str, str, str]]:
    return {(diag.code, diag.severity, diag.path) for diag in diags}


@pytest.mark.parametrize(
    ("legacy_cls", "rule", "missing_code", "missing_path", "rows"),
    [
        (
            DnsRefsValidator,
            "dns",
            "E7856",
            "pipeline:validate",
            [
                {"group": "services", "instance": "svc-a", "class_ref": "class.service.web_ui", "layer": "L5"},
                {
                    "group": "services",
                    "instance": "svc-dns",
                    "class_ref": "class.service.dns",
                    "layer": "L5",
                    "extensions": {"records": [{"service_ref": "svc-missing"}]},
                },
            ],
        ),
        (
            CertificateRefsValidator,
            "certificate",
            "E7857",
            "pipeline:validate",
            [
                {"group": "services", "instance": "svc-a", "class_ref": "class.service.web_ui", "layer": "L5"},
                {
                    "group": "certificates",
                    "instance": "cert-main",
                    "class_ref": "class.security.certificate",
                    "layer": "L5",
                    "extensions": {"service_ref": "svc-a", "used_by": {"service_ref": "svc-a"}},
                },
            ],
        ),
        (
            BackupRefsValidator,
            "backup",
            "E7858",
            "pipeline:validate",
            [
                {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
                {"group": "pools", "instance": "pool-a", "class_ref": "class.storage.pool", "layer": "L3"},
                {
                    "group": "operations",
                    "instance": "backup-nightly",
                    "class_ref": "class.operations.backup",
                    "layer": "L7",
                    "extensions": {"destination_ref": "pool-a", "targets": {"device_ref": "srv-a"}},
                },
            ],
        ),
        (
            ServiceDependencyRefsValidator,
            "service_dependency",
            "E7848",
            "pipeline:validate",
            [
                {"group": "data-assets", "instance": "asset-a", "class_ref": "class.storage.data_asset"},
                {
                    "group": "services",
                    "instance": "svc-a",
                    "class_ref": "class.service.web_ui",
                    "extensions": {"data_asset_refs": ["asset-missing"]},
                },
            ],
        ),
        (
            NetworkCoreRefsValidator,
            "network_core",
            "E7837",
            "pipeline:validate",
            [
                {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
                {"group": "network", "instance": "inst.zone.a", "class_ref": "class.network.trust_zone", "layer": "L2"},
                {
                    "group": "network",
                    "instance": "inst.vlan.a",
                    "class_ref": "class.network.vlan",
                    "layer": "L2",
                    "extensions": {
                        "bridge_ref": "inst.bridge.missing",
                        "trust_zone_ref": "inst.zone.a",
                        "managed_by_ref": "rtr-a",
                    },
                },
            ],
        ),
        (
            PowerSourceRefsValidator,
            "power_source",
            "E6901",
            "pipeline:mode",
            [
                {
                    "group": "devices",
                    "instance": "pdu-rack",
                    "class_ref": "class.power.pdu",
                    "layer": "L1",
                    "extensions": {},
                },
                {
                    "group": "devices",
                    "instance": "rtr-a",
                    "class_ref": "class.router",
                    "layer": "L1",
                    "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
                },
                {
                    "group": "devices",
                    "instance": "rtr-b",
                    "class_ref": "class.router",
                    "layer": "L1",
                    "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
                },
            ],
        ),
    ],
)
def test_declarative_reference_validator_matches_legacy_diagnostics(
    legacy_cls: type,
    rule: str,
    missing_code: str,
    missing_path: str,
    rows: list[dict[str, Any]],
):
    legacy_ctx = _context()
    declarative_ctx = _context(
        config={
            "enabled_rules": [rule],
            "missing_rows_code": missing_code,
            "missing_rows_path": missing_path,
        }
    )
    _publish_rows(legacy_ctx, rows)
    _publish_rows(declarative_ctx, rows)

    legacy = legacy_cls(f"legacy.{rule}", "1.x")
    declarative = DeclarativeReferenceValidator(f"declarative.{rule}", "1.x")

    legacy_diags = _run(legacy, legacy_ctx, plugin_id=f"legacy.{rule}")
    declarative_diags = _run(declarative, declarative_ctx, plugin_id=f"declarative.{rule}")

    assert _triple(declarative_diags) == _triple(legacy_diags)


@pytest.mark.parametrize(
    ("legacy_cls", "rule", "missing_code", "missing_path"),
    [
        (DnsRefsValidator, "dns", "E7856", "pipeline:validate"),
        (CertificateRefsValidator, "certificate", "E7857", "pipeline:validate"),
        (BackupRefsValidator, "backup", "E7858", "pipeline:validate"),
        (ServiceDependencyRefsValidator, "service_dependency", "E7848", "pipeline:validate"),
        (NetworkCoreRefsValidator, "network_core", "E7837", "pipeline:validate"),
        (PowerSourceRefsValidator, "power_source", "E6901", "pipeline:mode"),
    ],
)
def test_declarative_reference_validator_matches_legacy_missing_rows_diagnostics(
    legacy_cls: type,
    rule: str,
    missing_code: str,
    missing_path: str,
):
    legacy_ctx = _context()
    declarative_ctx = _context(
        config={
            "enabled_rules": [rule],
            "missing_rows_code": missing_code,
            "missing_rows_path": missing_path,
        }
    )

    legacy = legacy_cls(f"legacy.{rule}", "1.x")
    declarative = DeclarativeReferenceValidator(f"declarative.{rule}", "1.x")

    legacy_diags = _run(legacy, legacy_ctx, plugin_id=f"legacy.{rule}")
    declarative_diags = _run(declarative, declarative_ctx, plugin_id=f"declarative.{rule}")

    assert _triple(declarative_diags) == _triple(legacy_diags)

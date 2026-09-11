#!/usr/bin/env python3
"""Contract checks for the MikroTik runtime_baseline projection boundary.

W01 of the ADR 0118/0119 implementation plan requires the producer, the fixture
and the consumer to agree on which projection keys are required and which have a
defined empty value, and requires missing required data to fail clearly rather
than as a template error.

Templates render under StrictUndefined, so a key a template reads must exist.
Optional keys are filled with their defined empty value here; absence and
emptiness mean the same thing and neither grants anything. The dhcp block is
conditionally required: once enabled, its fields must be present.

End-to-end coverage of the missing-key case lives in
`test_generator_projection_contract.py`, whose minimal projection carries no
runtime_baseline at all. The enabled-but-incomplete case cannot currently be
produced by `build_mikrotik_projection`, which only sets `enabled` when pool,
CIDR and gateway are all present; the check guards the consumer boundary against
a future producer change or a hand-built projection.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V5_ROOT / "topology-tools"))

from kernel.plugin_base import Stage


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
    spec = importlib.util.spec_from_file_location("test_mikrotik_runtime_baseline", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerraformMikroTikGenerator


TerraformMikroTikGenerator = _load_generator_class()

# Every key a template reads from runtime_baseline, with its defined empty value.
OPTIONAL_LIST_KEYS = ("nat", "dns_servers", "addresses", "firewall_baseline_rules")


def _normalize(raw):
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    return generator._normalize_runtime_baseline(raw, stage=Stage.GENERATE)


def test_absent_runtime_baseline_yields_defined_empty_values() -> None:
    baseline, diagnostics = _normalize(None)

    assert diagnostics == []
    for key in OPTIONAL_LIST_KEYS:
        assert baseline[key] == [], f"{key} must default to its defined empty value"
    assert baseline["dhcp"] == {"enabled": False}


def test_partial_runtime_baseline_keeps_supplied_values() -> None:
    supplied = {"nat": [{"chain": "dstnat"}]}

    baseline, diagnostics = _normalize(supplied)

    assert diagnostics == []
    assert baseline["nat"] == [{"chain": "dstnat"}]
    assert baseline["firewall_baseline_rules"] == []
    assert supplied == {"nat": [{"chain": "dstnat"}]}, "input must not be mutated"


def test_wrong_typed_collection_falls_back_to_empty() -> None:
    baseline, diagnostics = _normalize({"nat": "not-a-list", "dhcp": "not-a-mapping"})

    assert diagnostics == []
    assert baseline["nat"] == []
    assert baseline["dhcp"] == {"enabled": False}


def test_disabled_dhcp_requires_no_further_fields() -> None:
    baseline, diagnostics = _normalize({"dhcp": {"enabled": False}})

    assert diagnostics == []
    assert baseline["dhcp"]["enabled"] is False


def test_enabled_dhcp_with_complete_fields_passes() -> None:
    dhcp = {
        "enabled": True,
        "pool_range": "192.0.2.10-192.0.2.200",
        "server_name": "defconf",
        "lease_time": "30m",
        "network_cidr": "192.0.2.0/24",
        "gateway": "192.0.2.1",
        "interface": "bridge",
    }

    baseline, diagnostics = _normalize({"dhcp": dhcp})

    assert diagnostics == []
    assert baseline["dhcp"] == dhcp


def test_enabled_dhcp_missing_required_fields_fails_with_named_diagnostic() -> None:
    baseline, diagnostics = _normalize(
        {"dhcp": {"enabled": True, "pool_range": "192.0.2.10-192.0.2.200", "gateway": "   "}}
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.code == "E9211"
    assert diagnostic.severity == "error"
    # The message must name what is missing, so the fix is locatable in the source.
    for field in ("server_name", "lease_time", "network_cidr", "gateway", "interface"):
        assert field in diagnostic.message
    assert "pool_range" not in diagnostic.message
    # A blocked candidate still normalizes; it is the diagnostic that stops rendering.
    assert baseline["firewall_baseline_rules"] == []

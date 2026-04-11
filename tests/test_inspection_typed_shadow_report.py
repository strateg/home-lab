#!/usr/bin/env python3
"""Unit-level contract checks for typed-shadow diagnostics helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSPECTION_DIR = REPO_ROOT / "scripts" / "inspection"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fixture_instances() -> list[dict[str, object]]:
    return [
        {
            "instance_id": "inst.router",
            "source_id": "rtr-main",
            "instance_data": {
                "network_gateway_ref": "gw-main",
                "peer_refs": ["svc-api"],
            },
            "instance": {},
        },
        {
            "instance_id": "inst.gateway",
            "source_id": "gw-main",
            "instance_data": {},
            "instance": {},
        },
        {
            "instance_id": "inst.service.api",
            "source_id": "svc-api",
            "instance_data": {
                "runtime_host_ref": "inst.gateway",
                "storage_volume_ref": "vol-main",
            },
            "instance": {},
        },
        {
            "instance_id": "inst.volume",
            "source_id": "vol-main",
            "instance_data": {},
            "instance": {},
        },
    ]


def test_build_typed_shadow_report_default_thresholds_pass() -> None:
    module = _load_module(
        INSPECTION_DIR / "inspection_typed_shadow_report.py",
        "inspection_typed_shadow_report_contract_default",
    )

    report = module.build_typed_shadow_report(_fixture_instances())

    assert report["schema_version"] == module.TYPED_SHADOW_REPORT_SCHEMA_VERSION
    assert report["edge_counts"]["total"] == 4
    assert report["edge_counts"]["classified_non_empty"] == 4
    assert report["edge_counts"]["coverage_percent"] == 100.0
    assert report["label_classifications_total"] == 4
    assert report["label_type_counts"].get("generic_ref", 0) == 0
    assert report["label_type_counts"]["network"] == 2
    assert report["label_type_counts"]["runtime"] == 1
    assert report["label_type_counts"]["storage"] == 1
    assert report["generic_ref_share_percent"] == 0.0
    assert report["gates"]["g2_coverage_pass"] is True
    assert report["gates"]["g2_generic_share_pass"] is True
    assert report["gates"]["g2_pass"] is True


def test_build_typed_shadow_report_can_fail_generic_share_threshold() -> None:
    module = _load_module(
        INSPECTION_DIR / "inspection_typed_shadow_report.py",
        "inspection_typed_shadow_report_contract_threshold",
    )

    report = module.build_typed_shadow_report(_fixture_instances(), min_coverage_percent=101.0)

    assert report["gates"]["g2_coverage_pass"] is False
    assert report["gates"]["g2_generic_share_pass"] is True
    assert report["gates"]["g2_pass"] is False


def test_typed_shadow_report_text_includes_gate_status() -> None:
    module = _load_module(
        INSPECTION_DIR / "inspection_typed_shadow_report.py",
        "inspection_typed_shadow_report_text_contract",
    )

    report = module.build_typed_shadow_report(_fixture_instances(), min_coverage_percent=101.0)
    text = module.typed_shadow_report_text(report)

    assert "ADR0095 Typed Shadow Coverage Report" in text
    assert "status: FAIL" in text
    assert "Gate Failure Details" in text
    assert "coverage percent" in text

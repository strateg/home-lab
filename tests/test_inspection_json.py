#!/usr/bin/env python3
"""Unit-level contract checks for inspection JSON payload builders."""

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


def _instances_fixture() -> list[dict[str, object]]:
    return [
        {
            "instance_id": "inst.router",
            "source_id": "rtr-main",
            "instance_data": {"service_ref": "svc-api"},
            "instance": {},
        },
        {
            "instance_id": "inst.service.api",
            "source_id": "svc-api",
            "instance_data": {"peer_ref": "gw-main"},
            "instance": {},
        },
        {
            "instance_id": "inst.gateway",
            "source_id": "gw-main",
            "instance_data": {"broken_ref": "missing.ref"},
            "instance": {},
        },
    ]


def test_summary_payload_contract_shape() -> None:
    module = _load_module(INSPECTION_DIR / "inspection_json.py", "inspection_json_summary_contract")
    payload = {
        "classes": {"class.router": {}, "class.service": {}},
        "objects": {"obj.router": {}, "obj.service": {}},
        "instances": {"network": [{"instance_id": "inst.router"}], "services": [{"instance_id": "inst.service"}]},
    }
    body = module.summary_payload(payload, [{"instance_id": "inst.router"}, {"instance_id": "inst.service"}])

    assert body["schema_version"] == module.SUMMARY_SCHEMA_VERSION
    assert body["command"] == "summary"
    assert body["counts"]["classes"] == 2
    assert body["counts"]["objects"] == 2
    assert body["counts"]["instances"] == 2
    assert body["counts"]["instance_groups"] == 2
    assert body["instance_group_counts"]["network"] == 1
    assert body["instance_group_counts"]["services"] == 1


def test_deps_payload_returns_resolved_dependency_view() -> None:
    module = _load_module(INSPECTION_DIR / "inspection_json.py", "inspection_json_deps_contract")
    code, body = module.deps_payload(_instances_fixture(), instance_ref="rtr-main", max_depth=3)

    assert code == 0
    assert body["schema_version"] == module.DEPS_SCHEMA_VERSION
    assert body["resolved_instance_id"] == "inst.router"
    assert body["instance_ref"] == "rtr-main"
    assert body["max_depth"] == 3
    assert body["direct_outgoing"][0]["instance_id"] == "inst.service.api"
    assert body["transitive_outgoing"][0]["instance_id"] == "inst.service.api"
    assert body["transitive_outgoing"][1]["instance_id"] == "inst.gateway"


def test_deps_payload_returns_structured_error_for_unknown_instance() -> None:
    module = _load_module(INSPECTION_DIR / "inspection_json.py", "inspection_json_deps_error")
    code, body = module.deps_payload(_instances_fixture(), instance_ref="unknown", max_depth=3)

    assert code == 2
    assert body["schema_version"] == module.DEPS_SCHEMA_VERSION
    assert body["error"]["code"] == "unknown_instance_reference"
    assert body["error"]["instance_ref"] == "unknown"

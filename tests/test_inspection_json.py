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
    body = module.summary_payload(
        payload,
        [
            {"instance_id": "inst.router", "_group": "network"},
            {"instance_id": "inst.service", "_group": "services"},
        ],
    )

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
    code, body = module.deps_payload(
        _instances_fixture(), instance_ref="rtr-main", max_depth=3, include_typed_shadow=True
    )

    assert code == 0
    assert body["schema_version"] == module.DEPS_SCHEMA_VERSION
    assert body["resolved_instance_id"] == "inst.router"
    assert body["instance_ref"] == "rtr-main"
    assert body["max_depth"] == 3
    assert body["direct_outgoing"][0]["instance_id"] == "inst.service.api"
    assert body["direct_outgoing"][0]["relation_types"] == ["runtime"]
    assert body["transitive_outgoing"][0]["instance_id"] == "inst.service.api"
    assert body["transitive_outgoing"][1]["instance_id"] == "inst.gateway"
    assert body["semantic_relations"]["schema_version"] == "adr0095.inspect.deps.semantic-relations.v1"
    assert body["semantic_relations"]["mode"] == "authoritative"
    assert body["typed_shadow"]["schema_version"] == "adr0095.inspect.deps.typed-shadow.v1"
    assert body["typed_shadow"]["mode"] == "compat_alias"
    assert body["typed_shadow"]["direct_outgoing"][0]["edge"] == "inst.router->inst.service.api"


def test_deps_payload_typed_shadow_preserves_baseline_edge_contract() -> None:
    module = _load_module(INSPECTION_DIR / "inspection_json.py", "inspection_json_deps_shadow_parity")

    base_code, base_body = module.deps_payload(
        _instances_fixture(),
        instance_ref="rtr-main",
        max_depth=3,
        include_typed_shadow=False,
    )
    shadow_code, shadow_body = module.deps_payload(
        _instances_fixture(),
        instance_ref="rtr-main",
        max_depth=3,
        include_typed_shadow=True,
    )

    assert base_code == 0
    assert shadow_code == 0
    assert "typed_shadow" not in base_body
    assert "typed_shadow" in shadow_body

    for key in (
        "schema_version",
        "command",
        "resolved_instance_id",
        "instance_ref",
        "max_depth",
        "semantic_relations",
        "direct_outgoing",
        "direct_incoming",
        "transitive_outgoing",
        "unresolved_refs",
    ):
        assert shadow_body[key] == base_body[key]


def test_deps_payload_returns_structured_error_for_unknown_instance() -> None:
    module = _load_module(INSPECTION_DIR / "inspection_json.py", "inspection_json_deps_error")
    code, body = module.deps_payload(_instances_fixture(), instance_ref="unknown", max_depth=3)

    assert code == 2
    assert body["schema_version"] == module.DEPS_SCHEMA_VERSION
    assert body["error"]["code"] == "unknown_instance_reference"
    assert body["error"]["instance_ref"] == "unknown"


def test_inheritance_payload_summary_and_focused_contracts() -> None:
    module = _load_module(INSPECTION_DIR / "inspection_json.py", "inspection_json_inheritance_contract")
    payload = {
        "classes": {
            "class.router": {},
            "class.router.edge": {"parent_class": "class.router"},
        }
    }
    summary_code, summary = module.inheritance_payload(payload)
    focused_code, focused = module.inheritance_payload(payload, class_ref="class.router")

    assert summary_code == 0
    assert summary["schema_version"] == module.INHERITANCE_SCHEMA_VERSION
    assert summary["counts"]["classes_total"] == 2
    assert summary["counts"]["root_classes"] == 1
    assert focused_code == 0
    assert focused["class_ref"] == "class.router"
    assert focused["direct_children"] == ["class.router.edge"]


def test_capabilities_payload_summary_and_error_contracts(tmp_path: Path, monkeypatch) -> None:
    module = _load_module(INSPECTION_DIR / "inspection_json.py", "inspection_json_capabilities_contract")
    topology_dir = tmp_path / "topology" / "class-modules" / "router"
    topology_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "topology" / "topology.yaml").write_text(
        "\n".join(
            [
                "version: 5.0.0",
                "framework:",
                "  capability_packs: topology/class-modules/L1-foundation/router/capability-packs.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (topology_dir / "capability-packs.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "packs:",
                "  - id: pack.router.home_gateway",
                "    class_ref: class.router",
                "    capabilities:",
                "      - cap.net.routing",
                "",
            ]
        ),
        encoding="utf-8",
    )
    effective_path = tmp_path / "build" / "effective-topology.json"
    effective_path.parent.mkdir(parents=True, exist_ok=True)
    effective_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    payload = {
        "topology_manifest": "topology/topology.yaml",
        "classes": {"class.router": {"required_capabilities": ["cap.net.routing"]}},
        "objects": {"obj.router": {"materializes_class": "class.router", "enabled_capabilities": ["cap.net.routing"]}},
    }

    ok_code, summary = module.capabilities_payload(payload, effective_path=effective_path)
    err_code, err = module.capabilities_payload(payload, effective_path=effective_path, object_id="obj.unknown")

    assert ok_code == 0
    assert summary["schema_version"] == module.CAPABILITIES_SCHEMA_VERSION
    assert summary["scope"] == "summary"
    assert summary["counts"]["classes_total"] == 1
    assert summary["counts"]["objects_total"] == 1
    assert err_code == 2
    assert err["error"]["code"] == "unknown_object_reference"

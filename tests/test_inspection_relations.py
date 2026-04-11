#!/usr/bin/env python3
"""Unit-level contract checks for inspection relation helpers."""

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
                "service_ref": "svc-api",
                "peer_refs": ["inst.gateway", "missing.ref"],
            },
            "instance": {
                "self_ref": "rtr-main",
            },
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
                "router_ref": "router",
            },
            "instance": {
                "host_ref": "inst.gateway",
            },
        },
    ]


def test_iter_refs_discovers_ref_suffixes_recursively() -> None:
    relations = _load_module(INSPECTION_DIR / "inspection_relations.py", "inspection_relations_iter_refs")
    data = {
        "service_ref": "svc-api",
        "nested": {
            "peer_refs": ["a", "b"],
            "not_ref_key": "skip",
        },
    }

    refs = relations.iter_refs(data)

    assert ("service_ref", "svc-api") in refs
    assert ("nested.peer_refs", ["a", "b"]) in refs
    assert all(path != "nested.not_ref_key" for path, _ in refs)


def test_normalize_ref_values_supports_string_and_list_only() -> None:
    relations = _load_module(INSPECTION_DIR / "inspection_relations.py", "inspection_relations_normalize")

    assert relations.normalize_ref_values("inst.router") == ["inst.router"]
    assert relations.normalize_ref_values(["a", 1, "b"]) == ["a", "b"]
    assert relations.normalize_ref_values({"bad": "type"}) == []


def test_build_dependency_graph_maps_aliases_labels_and_unresolved() -> None:
    relations = _load_module(INSPECTION_DIR / "inspection_relations.py", "inspection_relations_build_graph")
    edges, unresolved, labels = relations.build_dependency_graph(_fixture_instances())

    assert edges["inst.router"] == {"inst.service.api", "inst.gateway"}
    assert edges["inst.service.api"] == {"inst.router", "inst.gateway"}
    assert unresolved["inst.router"] == ["missing.ref"]
    assert labels["inst.router->inst.service.api"] == ["service_ref"]
    assert labels["inst.router->inst.gateway"] == ["peer_refs"]


def test_resolve_instance_id_supports_instance_source_and_short_alias() -> None:
    relations = _load_module(INSPECTION_DIR / "inspection_relations.py", "inspection_relations_resolve")
    instances = _fixture_instances()

    assert relations.resolve_instance_id(instances, "inst.router") == "inst.router"
    assert relations.resolve_instance_id(instances, "rtr-main") == "inst.router"
    assert relations.resolve_instance_id(instances, "router") == "inst.router"
    assert relations.resolve_instance_id(instances, "unknown") is None


def test_infer_relation_type_classifies_common_domains() -> None:
    relations = _load_module(INSPECTION_DIR / "inspection_relations.py", "inspection_relations_infer_type")

    assert relations.infer_relation_type("network.gateway_ref") == "network"
    assert relations.infer_relation_type("storage.volume_ref") == "storage"
    assert relations.infer_relation_type("runtime.host_ref") == "runtime"
    assert relations.infer_relation_type("capability_pack_ref") == "capability"
    assert relations.infer_relation_type("service_ref") == "runtime"
    assert relations.infer_relation_type("target_ref") == "binding"
    assert relations.infer_relation_type("endpoint_a.device_ref") == "network"
    assert relations.infer_relation_type("trust_zone_ref") == "network"
    assert relations.infer_relation_type("os_refs") == "runtime"
    assert relations.infer_relation_type("managed_by_ref") == "binding"
    assert relations.infer_relation_type("unknown_relation_ref") == "generic_ref"


def test_typed_relation_shadow_builds_edge_type_map() -> None:
    relations = _load_module(INSPECTION_DIR / "inspection_relations.py", "inspection_relations_shadow")
    labels = {
        "inst.router->inst.api": ["network.gateway_ref", "service_ref"],
        "inst.api->inst.storage": ["storage.volume_ref"],
    }

    shadow = relations.typed_relation_shadow(labels)

    assert shadow["inst.router->inst.api"] == ["network", "runtime"]
    assert shadow["inst.api->inst.storage"] == ["storage"]

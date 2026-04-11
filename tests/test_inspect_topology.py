"""Contract tests for topology inspection CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspection" / "inspect_topology.py"


def _write_fixture_repo(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    topology_dir = tmp_path / "topology" / "class-modules" / "router"
    build_dir.mkdir(parents=True, exist_ok=True)
    topology_dir.mkdir(parents=True, exist_ok=True)

    (tmp_path / "topology" / "topology.yaml").write_text(
        "\n".join(
            [
                "version: 5.0.0",
                "framework:",
                "  capability_packs: topology/class-modules/router/capability-packs.yaml",
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
                "      - cap.net.interface.ethernet",
                "      - cap.net.l3.routing.static",
                "",
            ]
        ),
        encoding="utf-8",
    )

    effective_payload = {
        "topology_manifest": "topology/topology.yaml",
        "classes": {
            "class.infrastructure": {},
            "class.router": {
                "required_capabilities": ["cap.net.routing"],
                "optional_capabilities": ["cap.net.vpn"],
                "capability_packs": ["pack.router.home_gateway"],
            },
            "class.router.edge": {
                "parent_class": "class.router",
            },
            "class.service": {
                "required_capabilities": ["cap.svc.runtime"],
            },
            "class.service.api": {
                "parent_class": "class.service",
            },
        },
        "objects": {
            "obj.router.ok": {
                "materializes_class": "class.router",
                "enabled_capabilities": ["cap.net.routing"],
                "enabled_packs": ["pack.router.home_gateway"],
            },
            "obj.router.bad": {
                "materializes_class": "class.router",
                "enabled_packs": ["pack.router.missing"],
            },
            "obj.router.gateway": {
                "materializes_class": "class.router.edge",
            },
            "obj.service.api": {
                "materializes_class": "class.service.api",
                "enabled_capabilities": ["cap.svc.runtime", "cap.svc.api"],
            },
            "obj.service.worker": {
                "extends_class": "class.service",
            },
        },
        "instances": {
            "network": [
                {
                    "instance_id": "inst.router.ok",
                    "source_id": "rtr-ok",
                    "layer": "L3",
                    "instance": {
                        "materializes_object": "obj.router.ok",
                        "materializes_class": "class.router",
                    },
                    "instance_data": {
                        "service_ref": "svc-api",
                        "nested": {"self_ref": "rtr-ok"},
                    },
                },
                {
                    "instance_id": "inst.gateway",
                    "source_id": "gw-main",
                    "layer": "L3",
                    "instance": {
                        "materializes_object": "obj.router.gateway",
                        "materializes_class": "class.router.edge",
                    },
                    "instance_data": {},
                },
            ],
            "services": [
                {
                    "instance_id": "inst.service.api",
                    "source_id": "svc-api",
                    "layer": "L5",
                    "instance": {
                        "materializes_object": "obj.service.api",
                        "materializes_class": "class.service.api",
                    },
                    "instance_data": {
                        "upstream_ref": "gw-main",
                        "broken_ref": "missing.ref",
                    },
                },
                {
                    "instance_id": "inst.service.worker",
                    "source_id": "svc-worker",
                    "layer": "L5",
                    "instance": {
                        "materializes_object": "obj.service.worker",
                        "materializes_class": "class.service",
                    },
                    "instance_data": {
                        "router_ref": "inst.router.ok",
                    },
                },
            ],
        },
    }
    (build_dir / "effective-topology.json").write_text(
        json.dumps(effective_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return build_dir / "effective-topology.json"


def _run_inspect(tmp_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=check,
    )


def test_summary_command_is_default_and_prints_group_counts(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "--effective", str(effective))

    assert "Topology Inspection Summary" in result.stdout
    assert "classes: 5" in result.stdout
    assert "objects: 5" in result.stdout
    assert "instances: 4" in result.stdout
    assert "instance groups: 2" in result.stdout
    assert "  - network: 2" in result.stdout
    assert "  - services: 2" in result.stdout


def test_summary_command_json_output_contract(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "summary", "--json", "--effective", str(effective))
    body = json.loads(result.stdout)

    assert body["schema_version"] == "adr0095.inspect.summary.v1"
    assert body["command"] == "summary"
    assert body["counts"]["classes"] == 5
    assert body["counts"]["objects"] == 5
    assert body["counts"]["instances"] == 4
    assert body["counts"]["instance_groups"] == 2
    assert body["instance_group_counts"]["network"] == 2
    assert body["instance_group_counts"]["services"] == 2


def test_summary_command_supports_layer_and_group_filters(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "summary",
        "--effective",
        str(effective),
        "--layer",
        "L5",
        "--group",
        "services",
    )

    assert "Topology Inspection Summary" in result.stdout
    assert "instances: 2" in result.stdout
    assert "instance groups: 1" in result.stdout
    assert "  - services: 2" in result.stdout
    assert "  - network: 2" not in result.stdout


def test_summary_command_json_respects_layer_and_group_filters(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "summary",
        "--json",
        "--effective",
        str(effective),
        "--layer",
        "L5",
        "--group",
        "services",
    )
    body = json.loads(result.stdout)

    assert body["counts"]["instances"] == 2
    assert body["counts"]["instance_groups"] == 1
    assert body["instance_group_counts"] == {"services": 2}


def test_classes_command_prints_current_inheritance_tree(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "classes", "--effective", str(effective))

    assert "Class Tree" in result.stdout
    assert "- class.infrastructure" in result.stdout
    assert "- class.router" in result.stdout
    assert "  - class.router.edge" in result.stdout
    assert "- class.service" in result.stdout
    assert "  - class.service.api" in result.stdout


def test_inheritance_command_prints_summary_when_class_not_provided(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "inheritance", "--effective", str(effective))

    assert "Class Inheritance Summary" in result.stdout
    assert "classes total: 5" in result.stdout
    assert "root classes: 3" in result.stdout
    assert "derived classes: 2" in result.stdout
    assert "Roots:" in result.stdout
    assert "  - class.infrastructure" in result.stdout
    assert "  - class.router" in result.stdout
    assert "  - class.service" in result.stdout


def test_inheritance_command_json_summary_contract(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "inheritance", "--json", "--effective", str(effective))
    body = json.loads(result.stdout)

    assert body["schema_version"] == "adr0095.inspect.inheritance.v1"
    assert body["command"] == "inheritance"
    assert body["scope"] == "summary"
    assert body["counts"]["classes_total"] == 5
    assert body["counts"]["root_classes"] == 3
    assert body["counts"]["derived_classes"] == 2
    assert "class.router" in body["roots"]


def test_inheritance_command_prints_focused_lineage_for_class(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "inheritance",
        "--effective",
        str(effective),
        "--class",
        "class.router",
    )

    assert "Class inheritance for: class.router" in result.stdout
    assert "Ancestors:" in result.stdout
    assert "  - none" in result.stdout
    assert "Direct children:" in result.stdout
    assert "  - class.router.edge" in result.stdout
    assert "All descendants:" in result.stdout
    assert "  - class.router.edge" in result.stdout


def test_inheritance_command_json_focused_lineage_contract(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "inheritance",
        "--json",
        "--effective",
        str(effective),
        "--class",
        "class.router",
    )
    body = json.loads(result.stdout)

    assert body["schema_version"] == "adr0095.inspect.inheritance.v1"
    assert body["command"] == "inheritance"
    assert body["scope"] == "class"
    assert body["class_ref"] == "class.router"
    assert body["ancestors"] == []
    assert body["direct_children"] == ["class.router.edge"]
    assert body["all_descendants"] == ["class.router.edge"]


def test_inheritance_command_returns_exit_code_2_for_unknown_class(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "inheritance",
        "--effective",
        str(effective),
        "--class",
        "class.unknown",
        check=False,
    )

    assert result.returncode == 2
    assert "Unknown class reference: class.unknown" in result.stdout


def test_inheritance_command_json_returns_error_for_unknown_class(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "inheritance",
        "--json",
        "--effective",
        str(effective),
        "--class",
        "class.unknown",
        check=False,
    )
    body = json.loads(result.stdout)

    assert result.returncode == 2
    assert body["schema_version"] == "adr0095.inspect.inheritance.v1"
    assert body["command"] == "inheritance"
    assert body["error"]["code"] == "unknown_class_reference"
    assert body["error"]["class_ref"] == "class.unknown"


def test_objects_command_groups_by_materialized_or_extended_class(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "objects", "--effective", str(effective))

    assert "Objects by Class" in result.stdout
    assert "total objects: 5" in result.stdout
    assert "- class.router (2)" in result.stdout
    assert "- class.router.edge (1)" in result.stdout
    assert "- class.service (1)" in result.stdout
    assert "- class.service.api (1)" in result.stdout
    assert "  - obj.router.bad" not in result.stdout


def test_objects_command_detailed_lists_object_rows(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "objects", "--detailed", "--effective", str(effective))

    assert "Objects by Class" in result.stdout
    assert "total objects: 5" in result.stdout
    assert "  - obj.router.bad" in result.stdout
    assert "  - obj.router.ok" in result.stdout
    assert "  - obj.router.gateway" in result.stdout
    assert "  - obj.service.worker" in result.stdout
    assert "  - obj.service.api" in result.stdout


def test_instances_command_groups_by_layer_with_object_and_class_binding(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "instances", "--effective", str(effective))

    assert "Instances by Layer" in result.stdout
    assert "total instances: 4" in result.stdout
    assert "- L3 (2)" in result.stdout
    assert "- L5 (2)" in result.stdout
    assert "inst.router.ok (source=rtr-ok, object=obj.router.ok, class=class.router)" not in result.stdout


def test_instances_command_supports_layer_and_group_filters(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "instances",
        "--effective",
        str(effective),
        "--layer",
        "L5",
        "--group",
        "services",
    )

    assert "Instances by Layer" in result.stdout
    assert "total instances: 2" in result.stdout
    assert "- L5 (2)" in result.stdout
    assert "- L3 (2)" not in result.stdout


def test_instances_command_detailed_lists_instance_rows(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "instances", "--detailed", "--effective", str(effective))

    assert "Instances by Layer" in result.stdout
    assert "total instances: 4" in result.stdout
    assert "- L3 (2)" in result.stdout
    assert "- L5 (2)" in result.stdout
    assert "inst.router.ok (source=rtr-ok, object=obj.router.ok, class=class.router)" in result.stdout
    assert (
        "inst.service.worker (source=svc-worker, object=obj.service.worker, class=class.service)" in result.stdout
    )


def test_search_command_matches_instance_fields_and_instance_data(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "search", "--effective", str(effective), "--query", "svc")

    assert "Search matches for pattern: svc" in result.stdout
    assert "- inst.router.ok (source=rtr-ok, layer=L3)" in result.stdout
    assert "- inst.service.api (source=svc-api, layer=L5)" in result.stdout
    assert "- inst.service.worker (source=svc-worker, layer=L5)" in result.stdout


def test_search_command_supports_layer_and_group_filters(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "search",
        "--effective",
        str(effective),
        "--query",
        "svc",
        "--group",
        "network",
        "--layer",
        "L3",
    )

    assert "Search matches for pattern: svc" in result.stdout
    assert "- inst.router.ok (source=rtr-ok, layer=L3)" in result.stdout
    assert "- inst.service.api (source=svc-api, layer=L5)" not in result.stdout


def test_deps_command_prints_direct_incoming_outgoing_transitive_and_unresolved(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "deps",
        "--effective",
        str(effective),
        "--instance",
        "rtr-ok",
        "--max-depth",
        "3",
    )

    assert "Dependencies for: inst.router.ok" in result.stdout
    assert "Outgoing (direct):" in result.stdout
    assert "  - inst.service.api [service_ref]" in result.stdout
    assert "Incoming (direct):" in result.stdout
    assert "  - inst.service.worker [router_ref]" in result.stdout
    assert "Transitive outgoing (depth <= 3):" in result.stdout
    assert "  - depth=1 inst.service.api" in result.stdout
    assert "  - depth=2 inst.gateway" in result.stdout
    assert "Unresolved refs:" in result.stdout
    assert "  - none" in result.stdout


def test_deps_command_json_output_contract(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "deps",
        "--effective",
        str(effective),
        "--instance",
        "rtr-ok",
        "--max-depth",
        "3",
        "--json",
    )
    body = json.loads(result.stdout)

    assert body["schema_version"] == "adr0095.inspect.deps.v1"
    assert body["command"] == "deps"
    assert body["resolved_instance_id"] == "inst.router.ok"
    assert body["instance_ref"] == "rtr-ok"
    assert body["max_depth"] == 3
    outgoing = {row["instance_id"]: row["labels"] for row in body["direct_outgoing"]}
    assert outgoing["inst.service.api"] == ["service_ref"]
    incoming = {row["instance_id"]: row["labels"] for row in body["direct_incoming"]}
    assert incoming["inst.service.worker"] == ["router_ref"]
    assert {"instance_id": "inst.service.api", "depth": 1} in body["transitive_outgoing"]
    assert {"instance_id": "inst.gateway", "depth": 2} in body["transitive_outgoing"]
    assert body["unresolved_refs"] == []


def test_deps_command_typed_shadow_prints_shadow_section(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "deps",
        "--effective",
        str(effective),
        "--instance",
        "rtr-ok",
        "--typed-shadow",
    )

    assert "Typed relation shadow (non-authoritative):" in result.stdout
    assert "outgoing inst.router.ok->inst.service.api: runtime" in result.stdout
    assert "incoming inst.service.worker->inst.router.ok: network" in result.stdout


def test_deps_command_json_typed_shadow_contract(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "deps",
        "--effective",
        str(effective),
        "--instance",
        "rtr-ok",
        "--max-depth",
        "3",
        "--json",
        "--typed-shadow",
    )
    body = json.loads(result.stdout)

    assert body["typed_shadow"]["schema_version"] == "adr0095.inspect.deps.typed-shadow.v1"
    outgoing = {row["edge"]: row["types"] for row in body["typed_shadow"]["direct_outgoing"]}
    incoming = {row["edge"]: row["types"] for row in body["typed_shadow"]["direct_incoming"]}
    assert outgoing["inst.router.ok->inst.service.api"] == ["runtime"]
    assert incoming["inst.service.worker->inst.router.ok"] == ["network"]


def test_deps_command_returns_exit_code_2_for_unknown_instance(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "deps",
        "--effective",
        str(effective),
        "--instance",
        "missing-instance",
        check=False,
    )

    assert result.returncode == 2
    assert "Unknown instance reference: missing-instance" in result.stdout


def test_deps_command_json_returns_error_payload_for_unknown_instance(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "deps",
        "--effective",
        str(effective),
        "--instance",
        "missing-instance",
        "--json",
        check=False,
    )
    body = json.loads(result.stdout)

    assert result.returncode == 2
    assert body["schema_version"] == "adr0095.inspect.deps.v1"
    assert body["command"] == "deps"
    assert body["error"]["code"] == "unknown_instance_reference"
    assert body["error"]["instance_ref"] == "missing-instance"


def test_deps_dot_writes_graph_with_edges_and_unresolved_nodes(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)
    output = tmp_path / "build" / "diagnostics" / "deps.dot"

    result = _run_inspect(tmp_path, "deps-dot", "--effective", str(effective), "--output", str(output))

    assert result.returncode == 0
    assert f"Wrote dependency graph: {output}" in result.stdout
    dot = output.read_text(encoding="utf-8")
    assert '"inst.router.ok" -> "inst.service.api";' in dot
    assert '"inst.service.api" -> "inst.gateway";' in dot
    assert '"inst.service.api" -> "unresolved::missing.ref" [style=dashed];' in dot


def test_capability_packs_inspection_prints_contract_matrix(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "capability-packs", "--effective", str(effective))

    stdout = result.stdout
    assert "Capability Packs Inspection" in stdout
    assert "pack.router.home_gateway" in stdout
    assert "Class -> Pack Dependencies" in stdout
    assert "obj.router.ok" in stdout
    assert "object enabled_packs missing in catalog: pack.router.missing" in stdout


def test_capabilities_command_prints_unified_summary(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "capabilities", "--effective", str(effective))

    out = result.stdout
    assert "Capability Relation Summary" in out
    assert "classes total: 5" in out
    assert "classes with required_capabilities: 2" in out
    assert "classes with optional_capabilities: 1" in out
    assert "classes with capability_packs: 1" in out
    assert "objects with enabled_capabilities: 2" in out
    assert "objects with enabled_packs: 2" in out
    assert "catalog packs: 1" in out
    assert "- class.router (required=1, optional=1, packs=1)" in out
    assert "- obj.router.ok (class=class.router, enabled_capabilities=1, enabled_packs=1)" in out


def test_capabilities_command_json_summary_contract(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(tmp_path, "capabilities", "--json", "--effective", str(effective))
    body = json.loads(result.stdout)

    assert body["schema_version"] == "adr0095.inspect.capabilities.v1"
    assert body["command"] == "capabilities"
    assert body["scope"] == "summary"
    assert body["counts"]["classes_total"] == 5
    assert body["counts"]["objects_total"] == 5
    assert body["counts"]["objects_with_enabled_capabilities"] == 2
    assert body["counts"]["objects_with_enabled_packs"] == 2
    assert any(row["class_ref"] == "class.router" for row in body["class_capability_intents"])


def test_capabilities_command_supports_focused_class_view(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "capabilities",
        "--effective",
        str(effective),
        "--class",
        "class.router",
    )

    out = result.stdout
    assert "Capabilities for class: class.router" in out
    assert "Required capabilities:" in out
    assert "  - cap.net.routing" in out
    assert "Optional capabilities:" in out
    assert "  - cap.net.vpn" in out
    assert "Capability packs:" in out
    assert "  - pack.router.home_gateway [ok]" in out
    assert "Bound objects:" in out
    assert "  - obj.router.ok" in out


def test_capabilities_command_json_focused_object_contract(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "capabilities",
        "--json",
        "--effective",
        str(effective),
        "--object",
        "obj.router.ok",
    )
    body = json.loads(result.stdout)

    assert body["schema_version"] == "adr0095.inspect.capabilities.v1"
    assert body["command"] == "capabilities"
    assert body["scope"] == "object"
    assert body["object_id"] == "obj.router.ok"
    assert body["class_ref"] == "class.router"
    assert body["enabled_capabilities"] == ["cap.net.routing"]
    assert body["enabled_packs"][0]["pack_id"] == "pack.router.home_gateway"
    assert body["enabled_packs"][0]["status"] == "ok"


def test_capabilities_command_returns_exit_code_2_for_unknown_object(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "capabilities",
        "--effective",
        str(effective),
        "--object",
        "obj.unknown",
        check=False,
    )

    assert result.returncode == 2
    assert "Unknown object reference: obj.unknown" in result.stdout


def test_capabilities_command_json_returns_error_for_unknown_object(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)

    result = _run_inspect(
        tmp_path,
        "capabilities",
        "--json",
        "--effective",
        str(effective),
        "--object",
        "obj.unknown",
        check=False,
    )
    body = json.loads(result.stdout)

    assert result.returncode == 2
    assert body["schema_version"] == "adr0095.inspect.capabilities.v1"
    assert body["command"] == "capabilities"
    assert body["error"]["code"] == "unknown_object_reference"
    assert body["error"]["object_id"] == "obj.unknown"


def test_missing_effective_topology_returns_exit_code_2_and_stderr_error(tmp_path: Path) -> None:
    missing = tmp_path / "build" / "missing-effective-topology.json"

    result = _run_inspect(tmp_path, "summary", "--effective", str(missing), check=False)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "[inspect][error] effective topology not found:" in result.stderr

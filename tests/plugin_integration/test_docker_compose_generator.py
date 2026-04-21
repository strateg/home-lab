#!/usr/bin/env python3
"""Integration tests for Docker Compose generator plugin (ADR 0087 Phase 6)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.generator.docker_compose"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_docker_compose_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _rows_to_compiled(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group rows by group key into compiled_json instances format."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        group = row.get("group", "default")
        groups.setdefault(group, []).append(row)
    return {"instances": groups}


def _context(tmp_path: Path, rows: list[dict[str, Any]]) -> PluginContext:
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        compiled_json=_rows_to_compiled(rows),
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    return ctx


def _stack_rows() -> list[dict[str, Any]]:
    """Stack with two Docker members."""
    return [
        {
            "group": "docker",
            "instance": "docker-prometheus",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-orangepi5",
                "runtime": {"image": "prom/prometheus:latest"},
            },
        },
        {
            "group": "docker",
            "instance": "docker-grafana",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-orangepi5",
                "runtime": {"image": "grafana/grafana:latest"},
            },
        },
        {
            "group": "docker",
            "instance": "stack-monitoring",
            "class_ref": "class.compute.workload.docker.stack",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-orangepi5",
                "stack_name": "monitoring",
                "compose_version": "3.8",
                "member_refs": ["docker-prometheus", "docker-grafana"],
                "shared_networks": [{"name": "monitoring", "driver": "bridge"}],
            },
        },
    ]


def test_docker_compose_generator_produces_compose_file(tmp_path: Path) -> None:
    """Test generator creates docker-compose.yaml for a stack."""
    registry = _registry()
    rows = _stack_rows()
    ctx = _context(tmp_path, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)
    assert result.status == PluginStatus.SUCCESS

    compose_path = tmp_path / "generated" / "docker-compose" / "srv-orangepi5" / "monitoring" / "docker-compose.yaml"
    assert compose_path.exists(), f"Expected {compose_path} to exist"

    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert compose["version"] == "3.8"
    assert "docker-prometheus" in compose["services"]
    assert "docker-grafana" in compose["services"]
    assert compose["services"]["docker-prometheus"]["image"] == "prom/prometheus:latest"
    assert compose["services"]["docker-grafana"]["image"] == "grafana/grafana:latest"


def test_docker_compose_generator_includes_networks(tmp_path: Path) -> None:
    """Test generator includes shared networks in compose file."""
    registry = _registry()
    ctx = _context(tmp_path, _stack_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)
    assert result.status == PluginStatus.SUCCESS

    compose_path = tmp_path / "generated" / "docker-compose" / "srv-orangepi5" / "monitoring" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert "monitoring" in compose.get("networks", {})


def test_docker_compose_generator_sets_restart_policy(tmp_path: Path) -> None:
    """Test generator defaults restart to unless-stopped."""
    registry = _registry()
    ctx = _context(tmp_path, _stack_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)
    assert result.status == PluginStatus.SUCCESS

    compose_path = tmp_path / "generated" / "docker-compose" / "srv-orangepi5" / "monitoring" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    for svc in compose["services"].values():
        assert svc.get("restart") == "unless-stopped"


def test_docker_compose_generator_skips_when_no_stacks(tmp_path: Path) -> None:
    """Test generator emits info and skips when no stack instances."""
    registry = _registry()
    rows = [
        {
            "group": "docker",
            "instance": "docker-app",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
        },
    ]
    ctx = _context(tmp_path, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)
    assert result.status == PluginStatus.SUCCESS
    assert any(d.code == "I7930" and "No Docker stack" in d.message for d in result.diagnostics)


def test_docker_compose_generator_warns_unresolvable_member(tmp_path: Path) -> None:
    """Test generator warns when member_ref doesn't resolve."""
    registry = _registry()
    rows = [
        {
            "group": "docker",
            "instance": "stack-test",
            "class_ref": "class.compute.workload.docker.stack",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "stack_name": "test",
                "member_refs": ["docker-missing"],
            },
        },
    ]
    ctx = _context(tmp_path, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)
    assert any(d.code == "W7931" for d in result.diagnostics)


def test_docker_compose_generator_handles_ports_and_volumes(tmp_path: Path) -> None:
    """Test generator includes ports and volumes from container config."""
    registry = _registry()
    rows = [
        {
            "group": "docker",
            "instance": "docker-web",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "runtime": {"image": "nginx:latest"},
                "network": {"ports": ["80:80", "443:443"]},
                "volumes": [
                    {"source": "/data/html", "target": "/usr/share/nginx/html"},
                ],
            },
        },
        {
            "group": "docker",
            "instance": "stack-web",
            "class_ref": "class.compute.workload.docker.stack",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "stack_name": "web",
                "member_refs": ["docker-web"],
            },
        },
    ]
    ctx = _context(tmp_path, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)
    assert result.status == PluginStatus.SUCCESS

    compose_path = tmp_path / "generated" / "docker-compose" / "srv-a" / "web" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    web_svc = compose["services"]["docker-web"]
    assert web_svc["ports"] == ["80:80", "443:443"]
    assert "/data/html:/usr/share/nginx/html" in web_svc["volumes"]


def test_docker_compose_generator_handles_environment(tmp_path: Path) -> None:
    """Test generator includes environment variables."""
    registry = _registry()
    rows = [
        {
            "group": "docker",
            "instance": "docker-app",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "runtime": {"image": "app:latest"},
                "environment": {"DB_HOST": "localhost", "DB_PORT": "5432"},
            },
        },
        {
            "group": "docker",
            "instance": "stack-app",
            "class_ref": "class.compute.workload.docker.stack",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "stack_name": "app",
                "member_refs": ["docker-app"],
            },
        },
    ]
    ctx = _context(tmp_path, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)
    assert result.status == PluginStatus.SUCCESS

    compose_path = tmp_path / "generated" / "docker-compose" / "srv-a" / "app" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    env = compose["services"]["docker-app"]["environment"]
    assert env["DB_HOST"] == "localhost"
    assert env["DB_PORT"] == "5432"


def test_docker_compose_generator_output_is_deterministic(tmp_path: Path) -> None:
    """Test generator produces identical output on repeated runs."""
    registry = _registry()
    rows = _stack_rows()

    ctx1 = _context(tmp_path / "run1", rows)
    result1 = registry.execute_plugin(PLUGIN_ID, ctx1, Stage.GENERATE)

    ctx2 = _context(tmp_path / "run2", rows)
    result2 = registry.execute_plugin(PLUGIN_ID, ctx2, Stage.GENERATE)

    assert result1.status == PluginStatus.SUCCESS
    assert result2.status == PluginStatus.SUCCESS

    path1 = tmp_path / "run1" / "generated" / "docker-compose" / "srv-orangepi5" / "monitoring" / "docker-compose.yaml"
    path2 = tmp_path / "run2" / "generated" / "docker-compose" / "srv-orangepi5" / "monitoring" / "docker-compose.yaml"
    assert path1.read_text() == path2.read_text()


def test_docker_compose_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    spec = _registry().specs[PLUGIN_ID]
    rel_entry, class_name = spec.entry.split(":", 1)
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / "plugins/compilers/instance_rows_compiler.py").as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": spec.kind.value,
                "entry": f"{(V5_TOOLS / "plugins" / rel_entry).as_posix()}:{class_name}",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": spec.phase.value,
                "order": spec.order,
                "depends_on": list(spec.depends_on),
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True}
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        compiled_json=_rows_to_compiled([]),
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)
    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)
    assert not ctx.get_published_keys(PLUGIN_ID)

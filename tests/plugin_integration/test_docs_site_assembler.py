#!/usr/bin/env python3
"""Integration checks for assemble-stage MkDocs site config emitter."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from kernel.plugin_registry import PluginRegistry
from plugins.assemblers.docs_site_assembler import DocsSiteAssembler

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test

PLUGIN_ID = "base.assembler.docs_site"
_SOURCE_PLUGINS = {
    "base.generator.docs",
    "base.generator.diagrams",
    "base.generator.topology_graph",
}


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _ctx(config: dict | None = None) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config=dict(config or {}),
    )


def _run_site(plugin: DocsSiteAssembler, ctx: PluginContext):
    return run_plugin_for_test(plugin, ctx, Stage.ASSEMBLE, consumes_keys=set(_SOURCE_PLUGINS))


def _seed_docs_tree(tmp_path: Path) -> tuple[Path, list[str], list[str]]:
    docs_root = tmp_path / "generated" / "docs"
    docs_files = [
        str(docs_root / "index.md"),
        str(docs_root / "overview.md"),
        str(docs_root / "vlan-topology.md"),
        str(docs_root / "_generated_files.txt"),
    ]
    diagram_files = [
        str(docs_root / "diagrams" / "index.md"),
        str(docs_root / "diagrams" / "network-topology.md"),
        str(docs_root / "diagrams" / "unified-topology.md"),
    ]
    for file_path in docs_files + diagram_files:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stub\n", encoding="utf-8")
    return docs_root, docs_files, diagram_files


def test_docs_site_assembler_emits_mkdocs_config(tmp_path: Path) -> None:
    docs_root, docs_files, diagram_files = _seed_docs_tree(tmp_path)

    ctx = _ctx()
    publish_for_test(ctx, "base.generator.docs", "generated_dir", str(docs_root))
    publish_for_test(ctx, "base.generator.docs", "docs_files", docs_files)
    publish_for_test(ctx, "base.generator.diagrams", "diagram_files", diagram_files[:2])
    publish_for_test(ctx, "base.generator.topology_graph", "topology_graph_files", diagram_files[2:])

    result = _run_site(DocsSiteAssembler(PLUGIN_ID), ctx)

    assert result.status == PluginStatus.SUCCESS
    config_path = docs_root.parent / "mkdocs.yml"
    assert result.output_data["docs_site_config"] == str(config_path)
    content = config_path.read_text(encoding="utf-8")
    assert "site_name: Topology Documentation" in content
    assert "docs_dir: docs" in content
    assert "name: material" in content
    assert "format: !!python/name:pymdownx.superfences.fence_code_format" in content
    assert "- Home: index.md" in content
    assert "- Overview: overview.md" in content
    assert "- Vlan Topology: vlan-topology.md" in content
    assert "- Index: diagrams/index.md" in content
    assert "- Unified Topology: diagrams/unified-topology.md" in content
    assert "_generated_files" not in content
    # diagrams index listed before other diagram pages
    assert content.index("diagrams/index.md") < content.index("diagrams/network-topology.md")


def test_docs_site_assembler_is_deterministic(tmp_path: Path) -> None:
    docs_root, docs_files, diagram_files = _seed_docs_tree(tmp_path)

    def _emit() -> str:
        ctx = _ctx()
        publish_for_test(ctx, "base.generator.docs", "generated_dir", str(docs_root))
        publish_for_test(ctx, "base.generator.docs", "docs_files", list(reversed(docs_files)))
        publish_for_test(ctx, "base.generator.diagrams", "diagram_files", list(reversed(diagram_files)))
        result = _run_site(DocsSiteAssembler(PLUGIN_ID), ctx)
        assert result.status == PluginStatus.SUCCESS
        return (docs_root.parent / "mkdocs.yml").read_text(encoding="utf-8")

    assert _emit() == _emit()


def test_docs_site_assembler_honors_site_name_config(tmp_path: Path) -> None:
    docs_root, docs_files, _ = _seed_docs_tree(tmp_path)

    ctx = _ctx({"site_name": "Home Lab"})
    publish_for_test(ctx, "base.generator.docs", "generated_dir", str(docs_root))
    publish_for_test(ctx, "base.generator.docs", "docs_files", docs_files)

    result = _run_site(DocsSiteAssembler(PLUGIN_ID), ctx)

    assert result.status == PluginStatus.SUCCESS
    content = (docs_root.parent / "mkdocs.yml").read_text(encoding="utf-8")
    assert "site_name: Home Lab" in content


def test_docs_site_assembler_skips_without_docs_output() -> None:
    ctx = _ctx()

    result = _run_site(DocsSiteAssembler(PLUGIN_ID), ctx)

    assert result.status == PluginStatus.SUCCESS
    assert any(diag.code == "I9871" and diag.severity == "info" for diag in result.diagnostics)
    assert result.output_data["docs_site_config"] == ""


def test_docs_site_manifest_registration() -> None:
    registry = _registry()

    spec = registry.specs[PLUGIN_ID]
    assert spec.phase == "run"
    assert spec.order == 415
    assert set(spec.depends_on) == _SOURCE_PLUGINS
    produced = {item["key"] for item in spec.produces if isinstance(item, dict)}
    assert {"docs_site_config", "docs_site_dir"}.issubset(produced)

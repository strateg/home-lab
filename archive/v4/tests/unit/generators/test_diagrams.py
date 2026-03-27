"""Unit tests for docs.docs_diagram.DiagramDocumentationGenerator."""

from pathlib import Path

import pytest
from jinja2 import DictLoader, Environment
from scripts.generators.docs.docs_diagram import DiagramDocumentationGenerator


class StubDocsGenerator:
    """Minimal docs generator stub for diagram tests."""

    def __init__(self, topology, output_dir: Path) -> None:
        self.topology = topology
        self.output_dir = output_dir
        self.generated_files = []
        self.mermaid_icons = True
        self.mermaid_icon_nodes = True
        self.icon_mode = "icon-nodes"
        self.jinja_env = Environment(
            loader=DictLoader(
                {
                    "docs/diagrams-index.md.j2": "Version: {{ topology_version }}",
                }
            )
        )

    def icon_runtime_hint(self) -> str:
        return "runtime hint"

    def transform_mermaid_icons_for_compat(self, content: str) -> str:
        return content

    def _register_generated_file(self, name: str) -> None:
        self.generated_files.append(name)

    def build_l1_storage_views(self):
        return {"rows_by_device": {}}


def _minimal_topology():
    return {
        "L0_meta": {"version": "4.0.0"},
        "L1_foundation": {
            "devices": {},
            "locations": {},
            "data_links": {},
        },
        "L2_network": {},
        "L3_data": {},
        "L4_platform": {},
        "L5_application": {},
    }


class TestDiagramHelpers:
    def test_summary_items(self):
        items = DiagramDocumentationGenerator.summary_items()
        assert isinstance(items, list)
        assert any("Mermaid" in item for item in items)

    def test_is_cloud_location(self):
        assert DiagramDocumentationGenerator.is_cloud_location("aws-eu-west-1") is True
        assert DiagramDocumentationGenerator.is_cloud_location("on-prem") is False

    def test_sort_dicts_with_dict(self):
        data = {
            "b": {"id": "b", "name": "B"},
            "a": {"id": "a", "name": "A"},
        }
        sorted_items = DiagramDocumentationGenerator._sort_dicts(data)
        assert [item["id"] for item in sorted_items] == ["a", "b"]

    def test_sort_dicts_with_list(self):
        data = [
            {"id": "b", "name": "B"},
            {"id": "a", "name": "A"},
        ]
        sorted_items = DiagramDocumentationGenerator._sort_dicts(data)
        assert [item["id"] for item in sorted_items] == ["a", "b"]

    def test_icon_for_default(self):
        icon = DiagramDocumentationGenerator._icon_for("not-a-dict", "type", {}, "mdi:default")
        assert icon == "mdi:default"


class TestDiagramRendering:
    def test_render_document_writes_file(self, tmp_path):
        topology = _minimal_topology()
        stub = StubDocsGenerator(topology, tmp_path)
        generator = DiagramDocumentationGenerator(stub)

        ok = generator._render_document("docs/diagrams-index.md.j2", "diagrams-index.md")
        assert ok is True

        output_path = tmp_path / "diagrams-index.md"
        assert output_path.exists()
        assert "Version: 4.0.0" in output_path.read_text(encoding="utf-8")
        assert "diagrams-index.md" in stub.generated_files

    def test_device_icon_cloud_vm(self, tmp_path):
        topology = _minimal_topology()
        stub = StubDocsGenerator(topology, tmp_path)
        generator = DiagramDocumentationGenerator(stub)

        icon = generator._device_icon({"type": "cloud-vm", "cloud": {"provider": "aws"}})
        assert icon == "si:amazonaws"

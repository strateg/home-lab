#!/usr/bin/env python3
"""Integration tests for base generator helpers."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator


class DummyGenerator(BaseGenerator):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.make_result([])


def _ctx(
    tmp_path: Path,
    *,
    artifacts_root: Path,
    templates_root: Path | None = None,
    project_id: str | None = None,
) -> PluginContext:
    config = {
        "generator_artifacts_root": str(artifacts_root),
    }
    if templates_root is not None:
        config["generator_templates_root"] = str(templates_root)
    if project_id is not None:
        config["project_id"] = project_id
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={"version": "5.0.0"},
        output_dir=str(tmp_path / "build"),
        config=config,
    )


def test_base_generator_uses_configured_artifacts_root(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    generator = DummyGenerator("dummy.generator")
    ctx = _ctx(tmp_path, artifacts_root=artifacts_root)

    output_path = generator.resolve_output_path(ctx, "terraform", "proxmox", "provider.tf")
    generator.write_text_atomic(output_path, "resource \"x\" \"y\" {}")

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "resource \"x\" \"y\" {}"
    assert not (output_path.parent / ".provider.tf.tmp").exists()


def test_base_generator_renders_template_from_configured_root(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    templates_root.mkdir(parents=True, exist_ok=True)
    (templates_root / "sample.j2").write_text("hello {{ name }}", encoding="utf-8")

    generator = DummyGenerator("dummy.generator")
    ctx = _ctx(tmp_path, artifacts_root=tmp_path / "artifacts", templates_root=templates_root)

    rendered = generator.render_template(ctx, "sample.j2", {"name": "home-lab"})
    assert rendered == "hello home-lab"


def test_base_generator_qualifies_artifacts_root_by_project(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    generator = DummyGenerator("dummy.generator")
    ctx = _ctx(tmp_path, artifacts_root=artifacts_root, project_id="home-lab")

    output_path = generator.resolve_output_path(ctx, "terraform", "proxmox", "provider.tf")
    generator.write_text_atomic(output_path, "resource \"x\" \"y\" {}")

    assert output_path == artifacts_root / "home-lab" / "terraform" / "proxmox" / "provider.tf"
    assert output_path.exists()

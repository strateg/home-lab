#!/usr/bin/env python3
"""Generate plugin reference documentation from manifest files.

This script parses all plugin manifests and generates comprehensive
markdown documentation including:
- Plugin catalog with descriptions
- Stage/kind groupings
- Configuration schemas
- Dependency graphs
- Produces/consumes contracts

Usage:
    python scripts/docs/generate_plugin_reference.py [--output-dir docs/generated]

Output:
    docs/generated/PLUGIN-REFERENCE.md
    docs/generated/PLUGIN-DEPENDENCY-GRAPH.md
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _discover_manifests(repo_root: Path) -> list[Path]:
    """Discover all plugin manifest files in deterministic order."""
    manifests = [repo_root / "topology-tools" / "plugins" / "plugins.yaml"]
    manifests.extend(sorted((repo_root / "topology" / "class-modules").rglob("plugins.yaml")))
    manifests.extend(sorted((repo_root / "topology" / "object-modules").rglob("plugins.yaml")))
    # Project manifests
    projects_root = repo_root / "projects"
    if projects_root.exists():
        for project_dir in sorted(projects_root.iterdir()):
            if project_dir.is_dir():
                manifests.extend(sorted(project_dir.rglob("plugins.yaml")))
    return [m for m in manifests if m.exists()]


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file safely."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_all_plugins(
    repo_root: Path,
    manifests: list[Path],
) -> list[tuple[dict[str, Any], Path]]:
    """Load all plugins from manifests with their source paths."""
    plugins: list[tuple[dict[str, Any], Path]] = []
    for manifest_path in manifests:
        manifest = _load_yaml(manifest_path)
        for plugin in manifest.get("plugins", []):
            plugins.append((plugin, manifest_path))
    return plugins


def _infer_kind_from_id(plugin_id: str) -> str:
    """Infer plugin kind from ID pattern."""
    parts = plugin_id.split(".")
    if len(parts) >= 2:
        kind_part = parts[-2] if len(parts) > 2 else parts[-1]
        if "discover" in kind_part:
            return "discoverer"
        if "compiler" in kind_part or "compile" in kind_part:
            return "compiler"
        if "validator" in kind_part or "validate" in kind_part:
            return "validator"
        if "generator" in kind_part or "generate" in kind_part:
            return "generator"
        if "assembler" in kind_part or "assemble" in kind_part:
            return "assembler"
        if "builder" in kind_part or "build" in kind_part:
            return "builder"
    return "unknown"


def generate_plugin_reference(
    plugins: list[tuple[dict[str, Any], Path]],
    repo_root: Path,
) -> str:
    """Generate main plugin reference markdown."""
    lines: list[str] = []

    # Header
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("# Plugin Reference")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Total Plugins:** {len(plugins)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Group by stage
    by_stage: dict[str, list[tuple[dict[str, Any], Path]]] = defaultdict(list)
    for plugin, path in plugins:
        plugin_id = plugin.get("id", "")
        kind = plugin.get("kind", _infer_kind_from_id(plugin_id))
        stage = _kind_to_stage(kind)
        by_stage[stage].append((plugin, path))

    stage_order = ["discover", "compile", "validate", "generate", "assemble", "build", "unknown"]

    # Table of contents
    lines.append("## Table of Contents")
    lines.append("")
    for stage in stage_order:
        if stage in by_stage:
            count = len(by_stage[stage])
            lines.append(f"- [{stage.capitalize()} Stage](#-stage) ({count} plugins)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Plugins by stage
    for stage in stage_order:
        if stage not in by_stage:
            continue

        stage_plugins = by_stage[stage]
        lines.append(f"## {stage.capitalize()} Stage")
        lines.append("")
        lines.append(f"**{len(stage_plugins)} plugins**")
        lines.append("")

        # Sort by order then by id
        sorted_plugins = sorted(
            stage_plugins,
            key=lambda x: (x[0].get("order", 999), x[0].get("id", "")),
        )

        for plugin, manifest_path in sorted_plugins:
            plugin_id = plugin.get("id", "<unknown>")
            description = plugin.get("description", "")
            order = plugin.get("order", "N/A")
            kind = plugin.get("kind", _infer_kind_from_id(plugin_id))
            execution_mode = plugin.get("execution_mode", "subinterpreter")
            api_version = plugin.get("api_version", "1.x")
            depends_on = plugin.get("depends_on", [])
            produces = plugin.get("produces", [])
            consumes = plugin.get("consumes", [])
            config_schema = plugin.get("config_schema", {})

            rel_manifest = manifest_path.relative_to(repo_root)

            lines.append(f"### `{plugin_id}`")
            lines.append("")
            if description:
                lines.append(f"> {description}")
                lines.append("")

            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            lines.append(f"| Kind | `{kind}` |")
            lines.append(f"| Order | {order} |")
            lines.append(f"| API Version | {api_version} |")
            lines.append(f"| Execution Mode | `{execution_mode}` |")
            lines.append(f"| Manifest | `{rel_manifest}` |")
            lines.append("")

            if depends_on:
                lines.append("**Dependencies:**")
                for dep in depends_on:
                    lines.append(f"- `{dep}`")
                lines.append("")

            if produces:
                lines.append("**Produces:**")
                for entry in produces:
                    if isinstance(entry, dict):
                        key = entry.get("key", "")
                        scope = entry.get("scope", "pipeline_shared")
                        lines.append(f"- `{key}` ({scope})")
                lines.append("")

            if consumes:
                lines.append("**Consumes:**")
                for entry in consumes:
                    if isinstance(entry, dict):
                        from_plugin = entry.get("from_plugin", "")
                        key = entry.get("key", "")
                        required = entry.get("required", True)
                        req_str = "required" if required else "optional"
                        lines.append(f"- `{key}` from `{from_plugin}` ({req_str})")
                lines.append("")

            if config_schema and config_schema.get("properties"):
                lines.append("**Configuration Schema:**")
                lines.append("")
                lines.append("```yaml")
                for prop_name, prop_def in config_schema.get("properties", {}).items():
                    prop_type = prop_def.get("type", "any")
                    default = prop_def.get("default", "")
                    default_str = f" (default: {default})" if default else ""
                    lines.append(f"{prop_name}: {prop_type}{default_str}")
                lines.append("```")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def generate_dependency_graph(
    plugins: list[tuple[dict[str, Any], Path]],
) -> str:
    """Generate dependency graph in Mermaid format."""
    lines: list[str] = []

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("# Plugin Dependency Graph")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Full Dependency Graph")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TD")

    # Build graph
    plugin_ids = {p.get("id") for p, _ in plugins if p.get("id")}
    edges: set[tuple[str, str]] = set()

    for plugin, _ in plugins:
        plugin_id = plugin.get("id", "")
        if not plugin_id:
            continue
        for dep in plugin.get("depends_on", []):
            if dep in plugin_ids:
                edges.add((dep, plugin_id))

    # Group by stage for styling
    stage_nodes: dict[str, list[str]] = defaultdict(list)
    for plugin, _ in plugins:
        plugin_id = plugin.get("id", "")
        if not plugin_id:
            continue
        kind = plugin.get("kind", _infer_kind_from_id(plugin_id))
        stage = _kind_to_stage(kind)
        stage_nodes[stage].append(plugin_id)

    # Output nodes with short IDs
    def short_id(full_id: str) -> str:
        parts = full_id.split(".")
        if len(parts) >= 3:
            return f"{parts[0][0]}.{parts[-2][:4]}.{parts[-1][:8]}"
        return full_id[:20]

    # Output edges
    for from_id, to_id in sorted(edges):
        safe_from = from_id.replace(".", "_")
        safe_to = to_id.replace(".", "_")
        lines.append(f"    {safe_from}[{short_id(from_id)}] --> {safe_to}[{short_id(to_id)}]")

    lines.append("```")
    lines.append("")

    # Stats
    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- Total plugins: {len(plugins)}")
    lines.append(f"- Total dependencies: {len(edges)}")
    lines.append("")

    # Plugins with most dependents
    dependent_count: dict[str, int] = defaultdict(int)
    for from_id, _ in edges:
        dependent_count[from_id] += 1

    if dependent_count:
        lines.append("## Most Depended-Upon Plugins")
        lines.append("")
        top_deps = sorted(dependent_count.items(), key=lambda x: -x[1])[:10]
        for plugin_id, count in top_deps:
            lines.append(f"- `{plugin_id}`: {count} dependents")
        lines.append("")

    return "\n".join(lines)


def _kind_to_stage(kind: str) -> str:
    """Map plugin kind to stage."""
    mapping = {
        "discoverer": "discover",
        "compiler": "compile",
        "validator": "validate",
        "validator_yaml": "validate",
        "validator_json": "validate",
        "generator": "generate",
        "assembler": "assemble",
        "builder": "build",
    }
    return mapping.get(kind, "unknown")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate plugin reference documentation."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: docs/generated)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()

    output_dir = args.output_dir or (repo_root / "docs" / "generated")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifests = _discover_manifests(repo_root)
    print(f"Found {len(manifests)} manifest files")

    plugins = load_all_plugins(repo_root, manifests)
    print(f"Loaded {len(plugins)} plugins")

    # Generate main reference
    reference_md = generate_plugin_reference(plugins, repo_root)
    reference_path = output_dir / "PLUGIN-REFERENCE.md"
    reference_path.write_text(reference_md, encoding="utf-8")
    print(f"Generated: {reference_path.relative_to(repo_root)}")

    # Generate dependency graph
    graph_md = generate_dependency_graph(plugins)
    graph_path = output_dir / "PLUGIN-DEPENDENCY-GRAPH.md"
    graph_path.write_text(graph_md, encoding="utf-8")
    print(f"Generated: {graph_path.relative_to(repo_root)}")

    print("Documentation generation complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Export ADR0096 rulebook assets as an MCP-style resource catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

RESOURCE_PREFIX = "home-lab://ai"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _resource(
    *,
    uri: str,
    title: str,
    description: str,
    path: str,
    mime_type: str,
    kind: str,
    source_adr: list[str] | None = None,
    always_load: bool = False,
) -> dict[str, Any]:
    return {
        "uri": uri,
        "title": title,
        "description": description,
        "path": path,
        "mime_type": mime_type,
        "kind": kind,
        "always_load": always_load,
        "source_adr": list(source_adr or []),
    }


def _base_resources(rule_map: dict[str, Any]) -> list[dict[str, Any]]:
    generated_from_adr = str(rule_map.get("generated_from_adr", "")).strip()
    return [
        _resource(
            uri=f"{RESOURCE_PREFIX}/rulebook",
            title="Universal AI Agent Rulebook",
            description="Compact always-load boot context for AI coding agents.",
            path="docs/ai/AGENT-RULEBOOK.md",
            mime_type="text/markdown",
            kind="rulebook",
            source_adr=[generated_from_adr],
            always_load=True,
        ),
        _resource(
            uri=f"{RESOURCE_PREFIX}/rule-map",
            title="ADR Rule Map",
            description="Machine-readable ADR0096 registry of rules, rule packs, and adapters.",
            path="docs/ai/ADR-RULE-MAP.yaml",
            mime_type="application/yaml",
            kind="rule-map",
            source_adr=[generated_from_adr],
            always_load=True,
        ),
        _resource(
            uri=f"{RESOURCE_PREFIX}/schemas/adr-rule-map",
            title="ADR Rule Map Schema",
            description="JSON schema for ADR-RULE-MAP.yaml compatibility validation.",
            path="schemas/adr-rule-map.schema.json",
            mime_type="application/json",
            kind="schema",
            source_adr=[generated_from_adr],
        ),
        _resource(
            uri=f"{RESOURCE_PREFIX}/adr/0096/status-report",
            title="ADR0096 Status Report",
            description="Implementation completion snapshot for ADR0096.",
            path="adr/0096-analysis/STATUS-REPORT.md",
            mime_type="text/markdown",
            kind="status-report",
            source_adr=[generated_from_adr],
        ),
        _resource(
            uri=f"{RESOURCE_PREFIX}/adr/0096/schema-policy",
            title="ADR0096 Schema Version Policy",
            description="Compatibility epoch and change-process policy for ADR-RULE-MAP consumers.",
            path="adr/0096-analysis/SCHEMA-VERSION-POLICY.md",
            mime_type="text/markdown",
            kind="schema-policy",
            source_adr=[generated_from_adr],
        ),
        _resource(
            uri=f"{RESOURCE_PREFIX}/adr/0096/swot-analysis",
            title="ADR0096 SWOT Analysis",
            description="Strategic review of rulebook strengths, weaknesses, opportunities, and threats.",
            path="adr/0096-analysis/SWOT-ANALYSIS.md",
            mime_type="text/markdown",
            kind="analysis",
            source_adr=[generated_from_adr],
        ),
    ]


def _rule_pack_resources(rule_map: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    packs = rule_map.get("rule_packs", {})
    if not isinstance(packs, dict):
        return resources
    for pack_name in sorted(packs):
        pack = packs.get(pack_name)
        if not isinstance(pack_name, str) or not isinstance(pack, dict):
            continue
        path = str(pack.get("path", "")).strip()
        resources.append(
            _resource(
                uri=f"{RESOURCE_PREFIX}/rules/{pack_name}",
                title=f"Rule Pack: {pack_name}",
                description=f"Scoped ADR-derived rule pack for {pack_name}.",
                path=path,
                mime_type="text/markdown",
                kind="rule-pack",
                source_adr=[str(item).strip() for item in pack.get("source_adr", []) if isinstance(item, str)],
            )
        )
    return resources


def _assert_resource_paths_exist(*, repo_root: Path, resources: list[dict[str, Any]]) -> None:
    missing = [resource["path"] for resource in resources if not (repo_root / resource["path"]).exists()]
    if missing:
        raise FileNotFoundError(f"Missing exported MCP resource paths: {', '.join(sorted(missing))}")


def _build_export(*, repo_root: Path, rule_map: dict[str, Any]) -> dict[str, Any]:
    resources = _base_resources(rule_map) + _rule_pack_resources(rule_map)
    _assert_resource_paths_exist(repo_root=repo_root, resources=resources)
    return {
        "schema_version": 1,
        "generated_from_adr": str(rule_map.get("generated_from_adr", "")).strip(),
        "catalog_kind": "mcp_resource_catalog",
        "resource_prefix": RESOURCE_PREFIX,
        "boot_resources": [
            f"{RESOURCE_PREFIX}/rulebook",
            f"{RESOURCE_PREFIX}/rule-map",
        ],
        "resource_count": len(resources),
        "resources": resources,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export ADR0096 rulebook assets as an MCP-style resource catalog.")
    parser.add_argument("--repo-root", default="", help="Optional repository root override.")
    parser.add_argument("--rule-map", default="docs/ai/ADR-RULE-MAP.yaml", help="Rule map path relative to repo root.")
    parser.add_argument("--output-json", default="", help="Optional path to write JSON export.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve() if str(args.repo_root).strip() else _repo_root()
    rule_map = _load_yaml(repo_root / args.rule_map)
    export = _build_export(repo_root=repo_root, rule_map=rule_map)

    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(export, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(export, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

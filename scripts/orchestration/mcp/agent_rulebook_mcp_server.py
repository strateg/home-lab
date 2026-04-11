#!/usr/bin/env python3
"""Serve ADR0096 rulebook assets as an MCP stdio resource server."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

SERVER_NAME = "home-lab-ai-rulebook"
SERVER_INSTRUCTIONS = (
    "Expose the ADR0096 universal rulebook, rule map, rule packs, and governance artifacts as MCP resources."
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_export_module():
    repo_root = _repo_root()
    module_path = repo_root / "scripts" / "validation" / "export_agent_rulebook_mcp_resources.py"
    spec = importlib.util.spec_from_file_location("export_agent_rulebook_mcp_resources", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load export module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_resource_catalog(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    export_mod = _load_export_module()
    rule_map = export_mod._load_yaml(root / "docs" / "ai" / "ADR-RULE-MAP.yaml")
    return export_mod._build_export(repo_root=root, rule_map=rule_map)


def _register_file_resource(
    server: FastMCP,
    *,
    repo_root: Path,
    entry: dict[str, Any],
) -> None:
    rel_path = str(entry["path"])
    abs_path = repo_root / rel_path
    title = str(entry.get("title", Path(rel_path).name))
    description = str(entry.get("description", "")).strip()
    mime_type = str(entry.get("mime_type", "text/plain")).strip() or "text/plain"
    meta = {
        "path": rel_path,
        "kind": entry.get("kind", ""),
        "always_load": bool(entry.get("always_load", False)),
        "source_adr": list(entry.get("source_adr", [])),
    }

    def _read_resource() -> str:
        return abs_path.read_text(encoding="utf-8")

    _read_resource.__name__ = f"resource_{Path(rel_path).stem.replace('-', '_')}"
    server.resource(
        str(entry["uri"]),
        name=Path(rel_path).name,
        title=title,
        description=description,
        mime_type=mime_type,
        meta=meta,
    )(_read_resource)


def build_server(repo_root: Path | None = None) -> FastMCP:
    root = repo_root or _repo_root()
    catalog = build_resource_catalog(root)
    server = FastMCP(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    for entry in catalog["resources"]:
        _register_file_resource(server, repo_root=root, entry=entry)
    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve ADR0096 rulebook assets as an MCP stdio server.")
    parser.add_argument("--check", action="store_true", help="Verify resource catalog and print a short summary.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check:
        catalog = build_resource_catalog()
        print(
            json.dumps(
                {
                    "server_name": SERVER_NAME,
                    "resource_prefix": catalog["resource_prefix"],
                    "resource_count": catalog["resource_count"],
                    "boot_resources": catalog["boot_resources"],
                },
                ensure_ascii=True,
            )
        )
        return 0

    build_server().run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

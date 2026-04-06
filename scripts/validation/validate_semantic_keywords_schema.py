#!/usr/bin/env python3
"""Validate topology/semantic-keywords.yaml against JSON schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "topology-tools"

import sys

sys.path.insert(0, str(TOOLS_ROOT))
from yaml_loader import load_yaml_file


DEFAULT_KEYWORDS_PATH = ROOT / "topology" / "semantic-keywords.yaml"
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "semantic-keywords.schema.json"


def load_schema(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"schema root must be mapping: {path}")
    return payload


def load_keywords(path: Path) -> dict[str, Any]:
    payload = load_yaml_file(path) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"semantic keywords root must be mapping: {path}")
    return payload


def validate_keywords(*, keywords_path: Path, schema_path: Path) -> None:
    schema = load_schema(schema_path)
    keywords = load_keywords(keywords_path)
    jsonschema.validate(instance=keywords, schema=schema)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate semantic keywords YAML against schema.")
    parser.add_argument("--keywords", type=Path, default=DEFAULT_KEYWORDS_PATH, help="Semantic keywords YAML path.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="JSON schema path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    keywords_path = args.keywords.resolve() if not args.keywords.is_absolute() else args.keywords
    schema_path = args.schema.resolve() if not args.schema.is_absolute() else args.schema

    try:
        validate_keywords(keywords_path=keywords_path, schema_path=schema_path)
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        print(f"[semantic-keywords-schema] ERROR: {exc}")
        return 1

    print(f"[semantic-keywords-schema] PASS: {keywords_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

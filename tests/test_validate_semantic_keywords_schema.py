#!/usr/bin/env python3
"""Contract tests for semantic keywords schema validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import jsonschema
import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "validation" / "validate_semantic_keywords_schema.py"
    spec = importlib.util.spec_from_file_location("validate_semantic_keywords_schema", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load validate_semantic_keywords_schema module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repository_semantic_keywords_schema_passes() -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    keywords_path = repo_root / "topology" / "semantic-keywords.yaml"
    schema_path = repo_root / "schemas" / "semantic-keywords.schema.json"
    mod.validate_keywords(keywords_path=keywords_path, schema_path=schema_path)


def test_invalid_semantic_keywords_payload_fails(tmp_path: Path) -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    schema_path = repo_root / "schemas" / "semantic-keywords.schema.json"
    payload = yaml.safe_load((repo_root / "topology" / "semantic-keywords.yaml").read_text(encoding="utf-8"))
    payload["registry"]["class_id"]["canonical"] = "class"

    bad_keywords = tmp_path / "semantic-keywords.yaml"
    bad_keywords.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    try:
        mod.validate_keywords(keywords_path=bad_keywords, schema_path=schema_path)
    except jsonschema.ValidationError:
        return
    raise AssertionError("Expected jsonschema.ValidationError for invalid semantic keywords payload.")

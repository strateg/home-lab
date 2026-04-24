#!/usr/bin/env python3
"""Contract tests for split-instance-bindings canonical shard output."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "topology-tools" / "utils" / "split-instance-bindings.py"
    spec = importlib.util.spec_from_file_location("split_instance_bindings", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load split-instance-bindings module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_write_shards_emits_canonical_semantic_keys(tmp_path: Path) -> None:
    mod = _load_module()
    output_root = tmp_path / "instances"
    bindings = {
        "instance_bindings": {
            "devices": [
                {
                    "instance": "inst.router.a",
                    "object_ref": "obj.router",
                    "layer": "L1",
                    "class_ref": "class.router",
                    "note": "preserved",
                }
            ]
        }
    }

    count, rewrite_map = mod._write_shards(
        bindings=bindings,
        output_root=output_root,
        drop_class_ref=True,
        sanitize_instance_ids=False,
        force=True,
    )

    assert count == 1
    assert rewrite_map == {}

    payload = yaml.safe_load((output_root / "devices" / "inst.router.a.yaml").read_text(encoding="utf-8")) or {}
    assert payload["@instance"] == "inst.router.a"
    assert payload["@extends"] == "obj.router"
    assert payload["@version"] == "1.0.0"
    assert payload["group"] == "devices"
    assert payload["note"] == "preserved"
    assert "layer" not in payload
    assert "class_ref" not in payload
    assert "object_ref" not in payload
    assert "instance" not in payload
    assert "version" not in payload


def test_write_shards_requires_non_empty_object_ref(tmp_path: Path) -> None:
    mod = _load_module()
    output_root = tmp_path / "instances"
    bindings = {
        "instance_bindings": {
            "devices": [
                {
                    "instance": "inst.router.a",
                    "layer": "L1",
                }
            ]
        }
    }

    try:
        mod._write_shards(
            bindings=bindings,
            output_root=output_root,
            drop_class_ref=True,
            sanitize_instance_ids=False,
            force=True,
        )
    except ValueError as exc:
        assert "missing non-empty 'object_ref'" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing object_ref.")


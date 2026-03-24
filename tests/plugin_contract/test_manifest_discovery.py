#!/usr/bin/env python3
"""Contract tests for module-level plugin manifest discovery policy (ADR 0063)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Add topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from compiler_runtime import discover_plugin_manifests


def _write_manifest(path: Path, *, plugin_id: str) -> None:
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": plugin_id,
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_discover_plugin_manifests_order_is_deterministic(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    instance_root = tmp_path / "instances"

    _write_manifest(base, plugin_id="base.validator.alpha")
    _write_manifest(class_root / "zeta" / "plugins.yaml", plugin_id="class.validator.zeta")
    _write_manifest(class_root / "alpha" / "plugins.yaml", plugin_id="class.validator.alpha")
    _write_manifest(object_root / "omega" / "plugins.yaml", plugin_id="object.validator.omega")
    _write_manifest(object_root / "beta" / "plugins.yaml", plugin_id="object.validator.beta")
    _write_manifest(instance_root / "site-b" / "plugins.yaml", plugin_id="instance.validator.site_b")
    _write_manifest(instance_root / "site-a" / "plugins.yaml", plugin_id="instance.validator.site_a")

    manifests = discover_plugin_manifests(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
        instance_manifests_root=instance_root,
    )

    assert manifests == [
        base.resolve(),
        (class_root / "alpha" / "plugins.yaml").resolve(),
        (class_root / "zeta" / "plugins.yaml").resolve(),
        (object_root / "beta" / "plugins.yaml").resolve(),
        (object_root / "omega" / "plugins.yaml").resolve(),
        (instance_root / "site-a" / "plugins.yaml").resolve(),
        (instance_root / "site-b" / "plugins.yaml").resolve(),
    ]


def test_discovery_keeps_base_manifest_first_even_if_missing(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    instance_root = tmp_path / "instances"

    _write_manifest(class_root / "a" / "plugins.yaml", plugin_id="class.validator.a")
    _write_manifest(object_root / "b" / "plugins.yaml", plugin_id="object.validator.b")
    _write_manifest(instance_root / "c" / "plugins.yaml", plugin_id="instance.validator.c")

    manifests = discover_plugin_manifests(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
        instance_manifests_root=instance_root,
    )

    assert manifests[0] == base.resolve()
    assert manifests[1:] == [
        (class_root / "a" / "plugins.yaml").resolve(),
        (object_root / "b" / "plugins.yaml").resolve(),
        (instance_root / "c" / "plugins.yaml").resolve(),
    ]

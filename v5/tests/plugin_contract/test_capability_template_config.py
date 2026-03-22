#!/usr/bin/env python3
"""Contract tests for capability-template externalization (ADR0078 WP9).

Verifies that generators use config-driven capability-template mappings
instead of hardcoded if-statements.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
OBJECT_MODULES_ROOT = V5_ROOT / "topology" / "object-modules"


def _get_generator_files() -> list[Path]:
    """Find all generator plugin files in object modules."""
    generators = []
    for obj_dir in OBJECT_MODULES_ROOT.iterdir():
        if not obj_dir.is_dir() or obj_dir.name.startswith("_"):
            continue
        plugins_dir = obj_dir / "plugins"
        if not plugins_dir.exists():
            continue
        for py_file in plugins_dir.glob("*_generator.py"):
            generators.append(py_file)
    return generators


def test_generators_do_not_hardcode_capability_template_mappings() -> None:
    """Verify generators don't hardcode capability-template if-statements.

    Allowed patterns:
    - Reading from config: ctx.config.get("capability_templates", ...)
    - Using _get_capability_templates() method
    - Default fallback constants (class-level _DEFAULT_CAPABILITY_TEMPLATES)

    Prohibited patterns:
    - Direct if-statements like: if has_qos: templates["qos.tf"] = ...
    - Direct if-statements like: if caps.get("has_wireguard"): templates[...] = ...
    """
    # Pattern for hardcoded capability checks that directly modify templates dict
    # Matches: if has_qos: templates["..."] = "..."
    # Matches: if has_wireguard: templates[...] = ...
    # Does NOT match: if capabilities.get(cap_key, False): result[...] = ...
    hardcoded_pattern = re.compile(
        r'if\s+(?:has_(?:qos|wireguard|containers|vpn)|'
        r'caps\.get\(["\']has_(?:qos|wireguard|containers|vpn)["\']\)):\s*\n'
        r'\s*templates\[',
        re.MULTILINE
    )

    violations = []
    for gen_file in _get_generator_files():
        content = gen_file.read_text(encoding="utf-8")
        matches = hardcoded_pattern.findall(content)
        if matches:
            violations.append(f"{gen_file.relative_to(V5_ROOT)}: hardcoded capability-template mapping")

    assert not violations, (
        "Generators with hardcoded capability-template mappings found.\n"
        "Use config-driven capability_templates instead.\n"
        "Violations:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def test_generators_have_capability_templates_in_config_or_fallback() -> None:
    """Verify generators that use capabilities have config or fallback.

    Generators that work with capabilities should either:
    1. Read capability_templates from ctx.config, OR
    2. Have a _DEFAULT_CAPABILITY_TEMPLATES fallback
    """
    for gen_file in _get_generator_files():
        content = gen_file.read_text(encoding="utf-8")

        # Skip generators that don't deal with capabilities
        if "capability" not in content.lower():
            continue

        # Check for proper config usage or fallback
        has_config_read = "capability_templates" in content
        has_fallback = "_DEFAULT_CAPABILITY_TEMPLATES" in content
        has_get_method = "_get_capability_templates" in content

        # Generators using capabilities should have proper externalization
        if "has_qos" in content or "has_wireguard" in content or "has_containers" in content:
            assert has_config_read or has_fallback or has_get_method, (
                f"{gen_file.relative_to(V5_ROOT)}: Uses capability flags but lacks "
                f"config-driven capability_templates or fallback mechanism"
            )


def test_capability_templates_schema_in_manifests() -> None:
    """Verify object module manifests define capability_templates schema."""
    import yaml

    manifests_with_generators = []
    for obj_dir in OBJECT_MODULES_ROOT.iterdir():
        if not obj_dir.is_dir() or obj_dir.name.startswith("_"):
            continue
        manifest_path = obj_dir / "plugins.yaml"
        if not manifest_path.exists():
            continue

        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        plugins = manifest.get("plugins", [])

        for plugin in plugins:
            if plugin.get("kind") == "generator":
                # Check if this generator uses capability templates
                config = plugin.get("config", {})
                if "capability_templates" in config:
                    # Verify schema is defined
                    schema = plugin.get("config_schema", {})
                    props = schema.get("properties", {})
                    assert "capability_templates" in props, (
                        f"{manifest_path}: generator {plugin.get('id')} has capability_templates "
                        f"in config but no schema definition"
                    )
                    manifests_with_generators.append(manifest_path)

    # At least mikrotik should have capability_templates
    mikrotik_manifest = OBJECT_MODULES_ROOT / "mikrotik" / "plugins.yaml"
    if mikrotik_manifest.exists():
        assert mikrotik_manifest in manifests_with_generators, (
            "mikrotik plugins.yaml should define capability_templates config"
        )

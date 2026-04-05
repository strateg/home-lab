#!/usr/bin/env python3
"""Guard L4 LXC instances against legacy inline resource blocks (W7888 closure)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from yaml_loader import load_yaml_file

LXC_ROOT = REPO_ROOT / "projects" / "home-lab" / "topology" / "instances" / "L4-platform" / "lxc"
PLUGIN_MANIFEST = REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml"
LXC_PLUGIN_ID = "base.validator.lxc_refs"


def _load_resource_profiles() -> set[str]:
    payload = yaml.safe_load(PLUGIN_MANIFEST.read_text(encoding="utf-8")) or {}
    for plugin in payload.get("plugins", []):
        if not isinstance(plugin, dict):
            continue
        if plugin.get("id") != LXC_PLUGIN_ID:
            continue
        config = plugin.get("config", {})
        if not isinstance(config, dict):
            return set()
        profiles = config.get("resource_profiles", {})
        if not isinstance(profiles, dict):
            return set()
        return {str(key) for key, value in profiles.items() if isinstance(key, str) and isinstance(value, dict)}
    return set()


def test_l4_lxc_instances_use_known_resource_profile_refs_without_inline_resources() -> None:
    known_profiles = _load_resource_profiles()
    assert known_profiles, "No resource profiles configured in base.validator.lxc_refs."

    violations: list[str] = []
    for path in sorted(LXC_ROOT.glob("*.yaml")):
        payload = load_yaml_file(path) or {}
        rel = path.relative_to(REPO_ROOT)
        if "resources" in payload:
            violations.append(f"{rel}: legacy top-level 'resources' is forbidden")
        profile_ref = payload.get("resource_profile_ref")
        if not isinstance(profile_ref, str) or not profile_ref.strip():
            violations.append(f"{rel}: missing non-empty resource_profile_ref")
            continue
        if profile_ref not in known_profiles:
            violations.append(f"{rel}: unknown resource_profile_ref '{profile_ref}'")

    assert not violations, "\n".join(violations)

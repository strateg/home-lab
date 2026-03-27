#!/usr/bin/env python3
"""Guard strict instance profiles against unresolved placeholder markers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_MANIFEST = REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml"
INSTANCE_ROOT = REPO_ROOT / "projects" / "home-lab" / "topology" / "instances"

TODO_MARKER_RE = re.compile(r"^<TODO_[A-Z0-9_]+>$")
ANNOTATION_RE = re.compile(r"^@[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)?$")


def _strict_policy() -> tuple[str, set[str]]:
    payload = yaml.safe_load(PLUGINS_MANIFEST.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins")
    if not isinstance(plugins, list):
        return "enforce", {"modeled", "mapped"}
    for plugin in plugins:
        if not isinstance(plugin, dict):
            continue
        if plugin.get("id") != "base.validator.instance_placeholders":
            continue
        config = plugin.get("config") or {}
        if not isinstance(config, dict):
            return "enforce", {"modeled", "mapped"}
        mode = str(config.get("enforcement_mode", "enforce")).strip().lower()
        statuses_cfg = config.get("gate_statuses")
        statuses: set[str] = {"modeled", "mapped"}
        if isinstance(statuses_cfg, list):
            parsed = {str(token).strip().lower() for token in statuses_cfg if isinstance(token, str) and token.strip()}
            if parsed:
                statuses = parsed
        return mode, statuses
    return "enforce", {"modeled", "mapped"}


def _is_strict_instance(mode: str, strict_statuses: set[str], payload: dict[str, Any]) -> bool:
    if mode == "enforce":
        return True
    if mode == "warn":
        return False
    status = payload.get("status")
    return isinstance(status, str) and status.strip().lower() in strict_statuses


def _find_placeholders(node: Any, path: tuple[Any, ...], out: list[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _find_placeholders(value, path + (key,), out)
        return
    if isinstance(node, list):
        for idx, value in enumerate(node):
            _find_placeholders(value, path + (idx,), out)
        return
    if not isinstance(node, str):
        return
    if TODO_MARKER_RE.fullmatch(node):
        out.append((_format_path(path), node))
        return
    if node.startswith("@@"):
        return
    if ANNOTATION_RE.fullmatch(node):
        out.append((_format_path(path), node))


def _format_path(path: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for item in path:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))
    return ".".join(parts)


def test_strict_instance_profiles_have_no_unresolved_placeholders() -> None:
    mode, strict_statuses = _strict_policy()
    violations: list[str] = []
    for instance_file in sorted(INSTANCE_ROOT.rglob("*.yaml")):
        payload = yaml.safe_load(instance_file.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            continue
        if not _is_strict_instance(mode, strict_statuses, payload):
            continue
        hits: list[tuple[str, str]] = []
        _find_placeholders(payload, (), hits)
        rel = instance_file.relative_to(REPO_ROOT)
        for value_path, marker in hits:
            violations.append(f"{rel}:{value_path} -> {marker}")

    assert not violations, "Unresolved placeholders in strict instance profiles:\n" + "\n".join(violations)

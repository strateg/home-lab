#!/usr/bin/env python3
"""Integration tests for semantic keyword registry defaults."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from semantic_keywords import load_semantic_keyword_registry, resolve_semantic_value


def test_default_semantic_registry_has_no_legacy_aliases() -> None:
    registry = load_semantic_keyword_registry(None)
    assert registry.get("class_id").aliases == ()
    assert registry.get("object_id").aliases == ()
    assert registry.get("instance_id").aliases == ()
    assert registry.get("parent_ref").aliases == ()
    assert registry.get("capability_id").aliases == ()


def test_default_semantic_registry_resolves_only_canonical_keys() -> None:
    registry = load_semantic_keyword_registry(None)
    canonical = resolve_semantic_value(
        {"@class": "class.router"},
        registry=registry,
        context="entity_manifest",
        token="class_id",
    )
    assert canonical.found
    assert canonical.value == "class.router"
    assert canonical.key == "@class"

    legacy = resolve_semantic_value(
        {"class": "class.router"},
        registry=registry,
        context="entity_manifest",
        token="class_id",
    )
    assert not legacy.found
    assert legacy.value is None
    assert legacy.present_keys == ()

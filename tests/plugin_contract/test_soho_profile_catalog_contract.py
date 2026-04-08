#!/usr/bin/env python3
"""Contract checks for ADR0089 canonical SOHO profile/bundle catalogs."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_soho_profile_catalog_exists_and_references_known_bundles() -> None:
    profile_path = REPO_ROOT / "topology" / "product-profiles" / "soho.standard.v1.yaml"
    bundles_root = REPO_ROOT / "topology" / "product-bundles"

    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    assert isinstance(profile, dict)

    available: set[str] = set()
    for path in sorted(bundles_root.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        assert isinstance(payload, dict), f"bundle contract must be mapping: {path}"
        bundle_id = payload.get("bundle_id")
        assert isinstance(bundle_id, str) and bundle_id.strip(), f"bundle_id missing in {path}"
        available.add(bundle_id.strip())

    assert available, "bundle catalog must not be empty"

    required = set(profile.get("core_required_bundles", []))
    classes = profile.get("deployment_classes", {})
    assert isinstance(classes, dict)
    for class_payload in classes.values():
        if isinstance(class_payload, dict):
            required.update(class_payload.get("required_bundles", []))

    assert required.issubset(available)

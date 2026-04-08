#!/usr/bin/env python3
"""Contract checks for ADR0089/ADR0091 SOHO schema files."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]


def _schema(name: str) -> dict:
    path = REPO_ROOT / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_product_profile_schema_accepts_soho_standard_payload() -> None:
    payload = {
        "profile_id": "soho.standard.v1",
        "deployment_class": "managed-soho",
        "site_class": "single-site",
        "user_band": "1-25",
        "operator_mode": "single-operator",
        "release_channel": "stable",
        "migration_state": "migrated-soft",
    }
    jsonschema.validate(payload, _schema("product-profile.schema.json"))


def test_operator_readiness_schema_accepts_minimal_payload() -> None:
    payload = {
        "schema_version": "1.0",
        "project_id": "home-lab",
        "status": "yellow",
        "evidence": {"backup-and-restore": "partial"},
        "diagnostics": [
            {"code": "W7942", "severity": "warning", "message": "missing one required bundle in soft mode"}
        ],
    }
    jsonschema.validate(payload, _schema("operator-readiness.schema.json"))

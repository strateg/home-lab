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


def test_backup_status_schema_accepts_minimal_payload() -> None:
    payload = {
        "schema_version": "1.0",
        "timestamp": "2026-04-09T00:00:00+00:00",
        "completeness_state": "complete",
    }
    jsonschema.validate(payload, _schema("backup-status.schema.json"))


def test_restore_readiness_schema_accepts_minimal_payload() -> None:
    payload = {
        "schema_version": "1.0",
        "timestamp": "2026-04-09T00:00:00+00:00",
        "completeness_state": "partial",
    }
    jsonschema.validate(payload, _schema("restore-readiness.schema.json"))


def test_support_bundle_manifest_schema_accepts_payload_with_self_report_entry() -> None:
    payload = {
        "schema_version": "1.0",
        "timestamp": "2026-04-09T00:00:00+00:00",
        "project_id": "home-lab",
        "profile_id": "soho.standard.v1",
        "deployment_class": "managed-soho",
        "artifacts": {
            "handover": {
                "SYSTEM-SUMMARY.md": {"present": True},
                "NETWORK-SUMMARY.md": {"present": True},
                "ACCESS-RUNBOOK.md": {"present": True},
                "BACKUP-RUNBOOK.md": {"present": True},
                "RESTORE-RUNBOOK.md": {"present": True},
                "UPDATE-RUNBOOK.md": {"present": True},
                "INCIDENT-CHECKLIST.md": {"present": True},
                "ASSET-INVENTORY.csv": {"present": True},
                "CHANGELOG-SNAPSHOT.md": {"present": True},
            },
            "reports": {
                "health-report.json": {"present": True},
                "drift-report.json": {"present": True},
                "backup-status.json": {"present": True},
                "restore-readiness.json": {"present": True},
                "support-bundle-manifest.json": {"present": True},
            },
        },
        "completeness_state": "complete",
    }
    jsonschema.validate(payload, _schema("support-bundle-manifest.schema.json"))

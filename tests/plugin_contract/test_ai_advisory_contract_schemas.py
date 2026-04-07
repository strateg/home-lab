#!/usr/bin/env python3
"""Contract checks for ADR0094 AI advisory input/output schemas."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_schema(name: str) -> dict:
    schema_path = REPO_ROOT / "schemas" / name
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_ai_input_contract_schema_accepts_valid_payload() -> None:
    schema = _load_schema("ai-input-contract.schema.json")
    payload = {
        "schema_version": "1.0",
        "artifact_family": "terraform.proxmox",
        "generation_context": {"mode": "advisory", "plugin_id": "object.proxmox.generator.terraform"},
        "effective_json": {"schema_version": 1},
        "stable_projection": {"instances": []},
        "artifact_plan": {"schema_version": "1.0", "planned_outputs": []},
        "redaction_summary": {"redacted_fields": 2, "placeholder_format": "<<REDACTED:{field_path}>>"},
        "input_hash": "sha256-" + ("a" * 64),
    }
    jsonschema.validate(payload, schema)


def test_ai_input_contract_schema_rejects_invalid_hash() -> None:
    schema = _load_schema("ai-input-contract.schema.json")
    payload = {
        "schema_version": "1.0",
        "artifact_family": "terraform.proxmox",
        "generation_context": {"mode": "advisory", "plugin_id": "object.proxmox.generator.terraform"},
        "effective_json": {},
        "stable_projection": {},
        "artifact_plan": {},
        "redaction_summary": {"redacted_fields": 0, "placeholder_format": "<<REDACTED:{field_path}>>"},
        "input_hash": "not-a-hash",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_ai_output_contract_schema_accepts_valid_payload() -> None:
    schema = _load_schema("ai-output-contract.schema.json")
    payload = {
        "schema_version": "1.0",
        "metadata": {
            "ai_model_id": "gpt-5.4",
            "ai_request_id": "req-123",
            "generation_timestamp": "2026-04-07T18:00:00+00:00",
            "input_hash": "sha256-" + ("b" * 64),
        },
        "advisory_recommendations": [
            {
                "path": "generated/home-lab/terraform/proxmox/provider.tf",
                "action": "suggest",
                "rationale": "Pin provider version.",
            }
        ],
        "confidence_scores": {"generated/home-lab/terraform/proxmox/provider.tf": 0.82},
    }
    jsonschema.validate(payload, schema)


def test_ai_output_contract_schema_rejects_missing_metadata() -> None:
    schema = _load_schema("ai-output-contract.schema.json")
    payload = {
        "schema_version": "1.0",
        "advisory_recommendations": [
            {"path": "generated/home-lab/terraform/proxmox/provider.tf", "action": "suggest", "rationale": "x"}
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)

#!/usr/bin/env python3
"""Runtime helper checks for ADR0094 AI advisory contracts."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_advisory_contract import (  # noqa: E402
    build_ai_input_payload,
    parse_ai_output_payload,
    validate_ai_contract_payloads,
)


def test_build_ai_input_payload_sets_deterministic_hash() -> None:
    payload = build_ai_input_payload(
        artifact_family="terraform.proxmox",
        mode="advisory",
        plugin_id="object.proxmox.generator.terraform",
        effective_json={"schema_version": 1},
        stable_projection={"instances": []},
        artifact_plan={"schema_version": "1.0", "planned_outputs": []},
        redaction_summary={"redacted_fields": 0, "placeholder_format": "<<REDACTED:{field_path}>>"},
    )
    assert isinstance(payload.get("input_hash"), str)
    assert str(payload["input_hash"]).startswith("sha256-")
    assert len(str(payload["input_hash"])) == 71


def test_validate_ai_contract_payloads_accepts_valid_payloads() -> None:
    ai_input = build_ai_input_payload(
        artifact_family="terraform.proxmox",
        mode="advisory",
        plugin_id="object.proxmox.generator.terraform",
        effective_json={"schema_version": 1},
        stable_projection={"instances": []},
        artifact_plan={"schema_version": "1.0", "planned_outputs": []},
        redaction_summary={"redacted_fields": 1, "placeholder_format": "<<REDACTED:{field_path}>>"},
    )
    ai_output = {
        "schema_version": "1.0",
        "metadata": {
            "ai_model_id": "gpt-5.4",
            "ai_request_id": "req-42",
            "generation_timestamp": "2026-04-07T18:00:00+00:00",
            "input_hash": ai_input["input_hash"],
        },
        "advisory_recommendations": [
            {"path": "generated/home-lab/docs/overview.md", "action": "suggest", "rationale": "Improve readability"}
        ],
    }
    assert validate_ai_contract_payloads(ai_input=ai_input, ai_output=ai_output) == []


def test_validate_ai_contract_payloads_rejects_unsupported_major_version() -> None:
    ai_input = {
        "schema_version": "2.0",
        "artifact_family": "terraform.proxmox",
    }
    errors = validate_ai_contract_payloads(ai_input=ai_input, ai_output=None)
    assert any("ai_input schema_version '2.0' is unsupported" in msg for msg in errors)


def test_parse_ai_output_payload_extracts_recommendations_and_scores() -> None:
    parsed = parse_ai_output_payload(
        {
            "metadata": {"ai_model_id": "gpt-5.4"},
            "advisory_recommendations": [
                {"path": "generated/home-lab/docs/overview.md", "action": "suggest", "rationale": "Shorten intro"}
            ],
            "confidence_scores": {"generated/home-lab/docs/overview.md": 0.73},
        }
    )
    assert parsed["metadata"]["ai_model_id"] == "gpt-5.4"
    assert len(parsed["recommendations"]) == 1
    assert parsed["confidence_scores"]["generated/home-lab/docs/overview.md"] == 0.73

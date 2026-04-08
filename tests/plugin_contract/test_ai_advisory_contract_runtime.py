#!/usr/bin/env python3
"""Runtime helper checks for ADR0094 AI advisory contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_advisory_contract import (  # noqa: E402
    build_ai_input_payload,
    parse_ai_output_payload,
    redact_sensitive_fields,
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
        generation_context_extra={"prompt_profile": "terraform_default"},
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
            "confidence_scores": {"generated/home-lab/docs/overview.md": 1.73},
        }
    )
    assert parsed["metadata"]["ai_model_id"] == "gpt-5.4"
    assert len(parsed["recommendations"]) == 1
    assert parsed["confidence_scores"]["generated/home-lab/docs/overview.md"] == 1.0


def test_redact_sensitive_fields_supports_paths_annotations_and_patterns() -> None:
    payload = {
        "effective_json": {
            "credentials": {"api_token": "secret-token"},
            "service_password": "p@ss",
        },
        "stable_projection": {"auth": {"private_key": "very-secret-key"}},
        "artifact_plan": {"planned_outputs": []},
    }
    redacted, summary = redact_sensitive_fields(
        payload,
        secret_paths=["stable_projection.auth.private_key"],
        annotation_secret_paths=["effective_json.credentials.api_token"],
    )
    assert redacted["effective_json"]["credentials"]["api_token"].startswith("<<REDACTED:")
    assert redacted["stable_projection"]["auth"]["private_key"].startswith("<<REDACTED:")
    assert redacted["effective_json"]["service_password"].startswith("<<REDACTED:")
    assert summary["redacted_fields"] == 3
    assert "effective_json.credentials.api_token" in summary["redacted_paths"]


def test_build_ai_input_payload_supports_extra_key_patterns() -> None:
    payload = build_ai_input_payload(
        artifact_family="terraform.proxmox",
        mode="advisory",
        plugin_id="object.proxmox.generator.terraform",
        effective_json={"device": {"serial_number": "ABC123"}},
        stable_projection={"instances": []},
        artifact_plan={"schema_version": "1.0", "planned_outputs": []},
        extra_key_patterns=(re.compile(r"serial_number", re.IGNORECASE),),
    )

    assert payload["effective_json"]["device"]["serial_number"].startswith("<<REDACTED:")


def test_redaction_coverage_is_at_least_99_percent_for_secret_markers() -> None:
    secret_source = {f"service_{index}_password": f"pw-{index}" for index in range(120)}
    secret_source.update({f"api_{index}_token": f"tok-{index}" for index in range(80)})
    payload = {
        "effective_json": secret_source,
        "stable_projection": {"note": "non-secret"},
        "artifact_plan": {"planned_outputs": []},
    }

    redacted, summary = redact_sensitive_fields(payload)
    total_secret_fields = 200
    redacted_fields = int(summary["redacted_fields"])
    coverage = redacted_fields / total_secret_fields

    assert coverage >= 0.99
    assert all(str(redacted["effective_json"][key]).startswith("<<REDACTED:") for key in secret_source)

#!/usr/bin/env python3
"""Compatibility checks for relocated AI runtime helper modules."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

MODULE_SYMBOLS = {
    "ai_advisory_contract": ("build_ai_input_payload", "parse_ai_output_payload", "validate_ai_contract_payloads"),
    "ai_ansible": ("build_ansible_input_adapter", "parse_ansible_output_candidates"),
    "ai_assisted": ("materialize_candidate_artifacts", "build_candidate_diff"),
    "ai_audit": ("AiAuditLogger", "verify_ai_audit_log_integrity", "EVENT_TYPES"),
    "ai_promotion": ("resolve_approvals", "promote_approved_candidates"),
    "ai_rollback": ("list_ai_promoted_artifacts", "rollback_ai_promoted_artifacts"),
    "ai_sandbox": ("sanitize_environment", "create_ai_sandbox_session", "enforce_sandbox_resource_limits"),
}


def test_legacy_ai_module_paths_reexport_canonical_symbols() -> None:
    for module_name, symbols in MODULE_SYMBOLS.items():
        legacy = importlib.import_module(f"plugins.generators.{module_name}")
        canonical = importlib.import_module(f"ai_runtime.{module_name}")
        for symbol in symbols:
            assert getattr(legacy, symbol) is getattr(canonical, symbol)

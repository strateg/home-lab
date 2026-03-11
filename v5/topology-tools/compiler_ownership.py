"""Ownership policy helpers for ADR0069 pipeline cutover."""

from __future__ import annotations


def validation_owner(*, enable_plugins: bool, pipeline_mode: str, rule_name: str) -> str:
    if not enable_plugins:
        return "core"
    if (
        rule_name in {"embedded_in", "model_lock", "references", "capability_contract"}
        and pipeline_mode == "plugin-first"
    ):
        return "plugin"
    return "core"


def compilation_owner(*, enable_plugins: bool, pipeline_mode: str, rule_name: str) -> str:
    if not enable_plugins:
        return "core"
    if (
        rule_name in {"module_maps", "model_lock_data", "instance_rows", "capability_contract_data"}
        and pipeline_mode == "plugin-first"
    ):
        return "plugin"
    return "core"


def artifact_owner(*, enable_plugins: bool, pipeline_mode: str, artifact_name: str) -> str:
    if not enable_plugins:
        return "core"
    if artifact_name == "effective_json" and pipeline_mode == "plugin-first":
        return "plugin"
    return "core"

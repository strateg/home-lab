#!/usr/bin/env python3
"""Validate AI agent rulebook consistency per ADR 0096.

Checks:
1. ADR-RULE-MAP.yaml conforms to JSON schema
2. All source_adr IDs exist in adr/REGISTER.md
3. All rule pack files exist
4. Rule IDs are unique
5. Adapter registry is declared in ADR-RULE-MAP.yaml
6. Adapter files reference the universal rulebook and rule map
7. Adapter files do not preserve stale plugin-boundary text superseded by ADR0086
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import yaml

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


STALE_ADAPTER_TOKENS = (
    "All AI agents must enforce a 4-level plugin boundary model",
    "Enforce the 4-level plugin architecture",
    "Class-level plugins MUST NOT reference",
    "Class-level plugins must not mention",
    "Object-level plugins MUST NOT reference",
    "Object-level plugins must not mention",
)


@dataclass
class ValidationResult:
    """Validation result container."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def load_yaml(path: Path) -> dict | None:
    """Load YAML file safely."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None


def load_json(path: Path) -> dict | None:
    """Load JSON file safely."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None


def extract_adr_numbers_from_register(register_path: Path) -> set[str]:
    """Extract all ADR numbers from REGISTER.md."""
    numbers: set[str] = set()
    pattern = re.compile(r"\|\s*\[(\d{4})\]")

    if not register_path.exists():
        return numbers

    for line in register_path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            numbers.add(match.group(1))

    return numbers


def validate_schema(rule_map: dict, schema_path: Path, result: ValidationResult) -> None:
    """Validate ADR-RULE-MAP against JSON schema."""
    if not HAS_JSONSCHEMA:
        result.add_warning("jsonschema not installed; skipping schema validation")
        return

    schema = load_json(schema_path)
    if schema is None:
        result.add_error(f"Cannot load schema: {schema_path}")
        return

    try:
        jsonschema.validate(instance=rule_map, schema=schema)
    except jsonschema.ValidationError as e:
        result.add_error(f"Schema validation failed: {e.message} at {list(e.absolute_path)}")
    except jsonschema.SchemaError as e:
        result.add_error(f"Invalid schema: {e.message}")


def validate_source_adr_exists(
    rule_map: dict,
    register_adrs: set[str],
    result: ValidationResult,
) -> None:
    """Check that all source_adr references exist in REGISTER.md."""
    # Collect all source_adr from rule_packs
    for pack_name, pack in rule_map.get("rule_packs", {}).items():
        for adr_num in pack.get("source_adr", []):
            if adr_num not in register_adrs:
                result.add_error(f"rule_packs.{pack_name}: source_adr {adr_num} not in REGISTER.md")

    # Collect all source_adr from rules
    for rule in rule_map.get("rules", []):
        rule_id = rule.get("id", "UNKNOWN")
        for adr_num in rule.get("source_adr", []):
            if adr_num not in register_adrs:
                result.add_error(f"rules.{rule_id}: source_adr {adr_num} not in REGISTER.md")


def validate_rule_pack_files_exist(
    rule_map: dict,
    repo_root: Path,
    result: ValidationResult,
) -> None:
    """Check that all rule pack files exist."""
    for pack_name, pack in rule_map.get("rule_packs", {}).items():
        pack_path = repo_root / pack.get("path", "")
        if not pack_path.exists():
            result.add_error(f"rule_packs.{pack_name}: file not found: {pack.get('path')}")


def validate_unique_rule_ids(rule_map: dict, result: ValidationResult) -> None:
    """Check that all rule IDs are unique."""
    seen: dict[str, int] = {}
    for idx, rule in enumerate(rule_map.get("rules", [])):
        rule_id = rule.get("id", f"UNKNOWN-{idx}")
        if rule_id in seen:
            result.add_error(f"Duplicate rule ID: {rule_id} (first at index {seen[rule_id]}, again at {idx})")
        else:
            seen[rule_id] = idx


def _load_adapter_registry(rule_map: dict) -> tuple[list[str], list[str]]:
    adapters = rule_map.get("adapters", {})
    if not isinstance(adapters, dict):
        return [], []
    files = [item.strip() for item in adapters.get("files", []) if isinstance(item, str) and item.strip()]
    required_refs = [
        item.strip() for item in adapters.get("required_refs", []) if isinstance(item, str) and item.strip()
    ]
    return files, required_refs


def validate_adapter_registry(rule_map: dict, result: ValidationResult) -> None:
    """Check that adapter registry is present even without schema validation."""
    adapter_files, required_refs = _load_adapter_registry(rule_map)
    if not adapter_files:
        result.add_error("adapters.files: missing or empty")
    if not required_refs:
        result.add_error("adapters.required_refs: missing or empty")


def validate_adapters_reference_rulebook(
    rule_map: dict,
    repo_root: Path,
    result: ValidationResult,
) -> None:
    """Check that adapter files route to the universal rulebook contract."""
    adapter_files, required_refs = _load_adapter_registry(rule_map)
    if not adapter_files or not required_refs:
        return

    for adapter_rel in adapter_files:
        adapter_path = repo_root / adapter_rel
        if not adapter_path.exists():
            result.add_warning(f"Adapter not found: {adapter_rel}")
            continue

        content = adapter_path.read_text(encoding="utf-8")
        for expected_ref in required_refs:
            if expected_ref not in content:
                result.add_error(f"Adapter {adapter_rel} does not reference {expected_ref}")

        for stale_token in STALE_ADAPTER_TOKENS:
            if stale_token in content:
                result.add_error(f"Adapter {adapter_rel} contains stale ADR0086-superseded token: {stale_token}")


def validate_rule_triggers_and_validators(rule_map: dict, result: ValidationResult) -> None:
    """Check that each rule has trigger and validate fields."""
    for rule in rule_map.get("rules", []):
        rule_id = rule.get("id", "UNKNOWN")

        trigger = rule.get("trigger", "")
        if not trigger or len(trigger) < 10:
            result.add_error(f"rules.{rule_id}: missing or too short trigger")

        validate = rule.get("validate", [])
        if not validate:
            result.add_error(f"rules.{rule_id}: missing validate field")


def validate_agent_rules(
    repo_root: Path,
    rule_map_path: Path,
    schema_path: Path,
    register_path: Path,
) -> ValidationResult:
    """Run all validation checks."""
    result = ValidationResult()

    # Load rule map
    rule_map = load_yaml(rule_map_path)
    if rule_map is None:
        result.add_error(f"Cannot load rule map: {rule_map_path}")
        return result

    # Load ADR register
    register_adrs = extract_adr_numbers_from_register(register_path)
    if not register_adrs:
        result.add_warning("No ADR numbers found in REGISTER.md")

    # Run validations
    validate_schema(rule_map, schema_path, result)
    validate_source_adr_exists(rule_map, register_adrs, result)
    validate_rule_pack_files_exist(rule_map, repo_root, result)
    validate_unique_rule_ids(rule_map, result)
    validate_adapter_registry(rule_map, result)
    validate_adapters_reference_rulebook(rule_map, repo_root, result)
    validate_rule_triggers_and_validators(rule_map, result)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate AI agent rulebook consistency per ADR 0096.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    parser.add_argument(
        "--rule-map",
        default="docs/ai/ADR-RULE-MAP.yaml",
        help="Path to ADR-RULE-MAP.yaml (relative to repo root)",
    )
    parser.add_argument(
        "--schema",
        default="schemas/adr-rule-map.schema.json",
        help="Path to JSON schema (relative to repo root)",
    )
    parser.add_argument(
        "--register",
        default="adr/REGISTER.md",
        help="Path to ADR register (relative to repo root)",
    )
    parser.add_argument(
        "--output-json",
        help="Optional JSON output path for diagnostics",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Return non-zero when warnings are present",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    rule_map_path = repo_root / args.rule_map
    schema_path = repo_root / args.schema
    register_path = repo_root / args.register

    result = validate_agent_rules(
        repo_root=repo_root,
        rule_map_path=rule_map_path,
        schema_path=schema_path,
        register_path=register_path,
    )

    # Output results
    if result.ok:
        print("Agent rules validation: OK")
    else:
        print("Agent rules validation: FAILED")

    for error in result.errors:
        print(f"ERROR {error}")

    for warning in result.warnings:
        print(f"WARN  {warning}")

    # Summary
    rule_map = load_yaml(rule_map_path)
    rule_count = len(rule_map.get("rules", [])) if rule_map else 0
    pack_count = len(rule_map.get("rule_packs", {})) if rule_map else 0

    print(f"Summary: errors={len(result.errors)} warnings={len(result.warnings)} rules={rule_count} packs={pack_count}")

    # Optional JSON output
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "status": "ok" if result.ok else "failed",
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "rules_count": rule_count,
                    "packs_count": pack_count,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if result.errors:
        return 1
    if result.warnings and args.fail_on_warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

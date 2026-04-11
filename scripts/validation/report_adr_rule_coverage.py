#!/usr/bin/env python3
"""Generate ADR-to-rule coverage diagnostics for ADR0096 rulebook sources."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _extract_register_adrs(register_path: Path) -> set[str]:
    numbers: set[str] = set()
    pattern = re.compile(r"\|\s*\[(\d{4})\]")
    if not register_path.exists():
        return numbers
    for line in register_path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            numbers.add(match.group(1))
    return numbers


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _build_report(*, rule_map: dict[str, Any], register_adrs: set[str]) -> dict[str, Any]:
    adr_index: dict[str, dict[str, list[str]]] = {}

    for pack_name, pack in rule_map.get("rule_packs", {}).items():
        if not isinstance(pack_name, str) or not isinstance(pack, dict):
            continue
        for adr in pack.get("source_adr", []):
            if not isinstance(adr, str) or not adr.strip():
                continue
            bucket = adr_index.setdefault(adr.strip(), {"rule_ids": [], "rule_packs": []})
            bucket["rule_packs"].append(pack_name.strip())

    for rule in rule_map.get("rules", []):
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("id", "")).strip()
        for adr in rule.get("source_adr", []):
            if not isinstance(adr, str) or not adr.strip():
                continue
            bucket = adr_index.setdefault(adr.strip(), {"rule_ids": [], "rule_packs": []})
            if rule_id:
                bucket["rule_ids"].append(rule_id)

    coverage_entries: list[dict[str, Any]] = []
    for adr in sorted(adr_index):
        rule_ids = _sorted_unique(adr_index[adr]["rule_ids"])
        rule_packs = _sorted_unique(adr_index[adr]["rule_packs"])
        coverage_entries.append(
            {
                "adr": adr,
                "rule_ids": rule_ids,
                "rule_packs": rule_packs,
                "rule_count": len(rule_ids),
                "rule_pack_count": len(rule_packs),
                "coverage_entries": len(rule_ids) + len(rule_packs),
                "in_register": adr in register_adrs,
            }
        )

    covered_adrs = set(adr_index)
    covered_register_adrs = covered_adrs & register_adrs
    uncovered_register_adrs = sorted(register_adrs - covered_adrs)
    orphaned_source_adrs = sorted(covered_adrs - register_adrs)
    register_count = len(register_adrs)
    coverage_percent = round((len(covered_register_adrs) / register_count) * 100, 2) if register_count else 0.0

    return {
        "schema_version": 1,
        "generated_from_adr": str(rule_map.get("generated_from_adr", "")).strip(),
        "purpose": "Reverse ADR-to-rule coverage report for the ADR0096 universal rulebook registry.",
        "rule_count": len(rule_map.get("rules", [])),
        "rule_pack_count": len(rule_map.get("rule_packs", {})),
        "register_adr_count": register_count,
        "covered_source_adr_count": len(covered_adrs),
        "covered_register_adr_count": len(covered_register_adrs),
        "uncovered_register_adr_count": len(uncovered_register_adrs),
        "coverage_percent_of_register": coverage_percent,
        "uncovered_register_adrs": uncovered_register_adrs,
        "orphaned_source_adrs": orphaned_source_adrs,
        "adr_coverage": coverage_entries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ADR-to-rule coverage diagnostics for ADR0096.")
    parser.add_argument("--repo-root", default="", help="Optional repository root override.")
    parser.add_argument("--rule-map", default="docs/ai/ADR-RULE-MAP.yaml", help="Rule map path relative to repo root.")
    parser.add_argument("--register", default="adr/REGISTER.md", help="ADR register path relative to repo root.")
    parser.add_argument("--output-json", default="", help="Optional path to write JSON report.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve() if str(args.repo_root).strip() else _repo_root()
    rule_map_path = repo_root / args.rule_map
    register_path = repo_root / args.register

    report = _build_report(
        rule_map=_load_yaml(rule_map_path),
        register_adrs=_extract_register_adrs(register_path),
    )

    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

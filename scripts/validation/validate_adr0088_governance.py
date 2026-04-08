#!/usr/bin/env python3
"""Validate ADR0088 governance policies (metadata, warnings, legacy boundaries)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

from yaml_loader import load_yaml_file

DEFAULT_POLICY_PATH = ROOT / "configs" / "quality" / "adr0088-governance-policy.yaml"
DEFAULT_DIAGNOSTICS_JSON = ROOT / "build" / "diagnostics" / "report.json"
DEFAULT_OUTPUT_JSON = ROOT / "build" / "diagnostics" / "adr0088-governance-report.json"
SUPPORTED_MODES = {"warn", "enforce"}


def _append(items: list[dict[str, str]], *, area: str, code: str, message: str) -> None:
    items.append({"area": area, "code": code, "message": message})


def _load_policy(path: Path) -> dict[str, Any]:
    payload = load_yaml_file(path) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"policy root must be mapping: {path}")
    return payload


def _iter_manifest_files(root: Path, *, filename_prefix: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.yaml") if path.is_file() and path.name.startswith(filename_prefix))


def _evaluate_metadata(
    *,
    repo_root: Path,
    policy: dict[str, Any],
    mode: str,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    metadata_cfg = policy.get("metadata")
    if not isinstance(metadata_cfg, dict):
        _append(errors, area="metadata", code="P1001", message="missing metadata policy block")
        return {}
    targets_cfg = metadata_cfg.get("targets")
    if not isinstance(targets_cfg, dict):
        _append(errors, area="metadata", code="P1002", message="metadata.targets must be mapping")
        return {}

    result: dict[str, Any] = {}
    for target_name, raw_cfg in targets_cfg.items():
        if not isinstance(raw_cfg, dict):
            _append(errors, area="metadata", code="P1003", message=f"target '{target_name}' must be object")
            continue
        root_raw = raw_cfg.get("root")
        prefix_raw = raw_cfg.get("filename_prefix")
        required_keys = raw_cfg.get("required_keys")
        min_coverage = raw_cfg.get("min_coverage")
        if not isinstance(root_raw, str) or not root_raw:
            _append(errors, area="metadata", code="P1004", message=f"target '{target_name}' missing root")
            continue
        if not isinstance(prefix_raw, str) or not prefix_raw:
            _append(errors, area="metadata", code="P1005", message=f"target '{target_name}' missing filename_prefix")
            continue
        if not isinstance(required_keys, list) or not all(isinstance(item, str) for item in required_keys):
            _append(errors, area="metadata", code="P1006", message=f"target '{target_name}' invalid required_keys")
            continue
        if not isinstance(min_coverage, dict):
            _append(errors, area="metadata", code="P1007", message=f"target '{target_name}' invalid min_coverage")
            continue

        files = _iter_manifest_files((repo_root / root_raw).resolve(), filename_prefix=prefix_raw)
        target_report: dict[str, Any] = {"files_total": len(files), "keys": {}}
        result[target_name] = target_report
        if not files:
            _append(errors, area="metadata", code="P1008", message=f"target '{target_name}' has no matching files")
            continue

        loaded_payloads: list[dict[str, Any]] = []
        parse_failed = False
        for file_path in files:
            try:
                payload = load_yaml_file(file_path) or {}
            except yaml.YAMLError as exc:
                rel = file_path.relative_to(repo_root).as_posix()
                _append(errors, area="metadata", code="P1009", message=f"YAML parse failed in {rel}: {exc}")
                parse_failed = True
                continue
            if not isinstance(payload, dict):
                rel = file_path.relative_to(repo_root).as_posix()
                _append(errors, area="metadata", code="P1010", message=f"YAML root must be mapping in {rel}")
                parse_failed = True
                continue
            loaded_payloads.append(payload)
        if parse_failed and not loaded_payloads:
            continue

        effective_total = len(loaded_payloads)
        for key in required_keys:
            threshold_raw = min_coverage.get(key)
            if not isinstance(threshold_raw, (int, float)):
                _append(
                    errors,
                    area="metadata",
                    code="P1011",
                    message=f"target '{target_name}' key '{key}' has invalid threshold",
                )
                continue
            threshold = float(threshold_raw)
            present_count = sum(1 for payload in loaded_payloads if key in payload)
            coverage = (present_count / effective_total) if effective_total else 0.0
            target_report["keys"][key] = {
                "present": present_count,
                "total": effective_total,
                "coverage": round(coverage, 4),
                "threshold": threshold,
            }
            if coverage < threshold:
                message = (
                    f"metadata coverage below target for '{target_name}' key '{key}': "
                    f"{coverage:.4f} < {threshold:.4f}"
                )
                if mode == "enforce":
                    _append(errors, area="metadata", code="G1101", message=message)
                else:
                    _append(warnings, area="metadata", code="G1101", message=message)
    return result


def _warning_code_counts(diagnostics_json: Path) -> Counter[str]:
    payload = json.loads(diagnostics_json.read_text(encoding="utf-8"))
    diagnostics = payload.get("diagnostics", [])
    if not isinstance(diagnostics, list):
        return Counter()
    counts: Counter[str] = Counter()
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        if str(item.get("severity")) != "warning":
            continue
        code = str(item.get("code", "")).strip()
        if code:
            counts[code] += 1
    return counts


def _evaluate_warning_governance(
    *,
    diagnostics_json: Path,
    policy: dict[str, Any],
    mode: str,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    cfg = policy.get("warning_governance")
    if not isinstance(cfg, dict):
        _append(errors, area="warning_governance", code="P2001", message="missing warning_governance policy block")
        return {}

    if not diagnostics_json.exists():
        _append(
            errors,
            area="warning_governance",
            code="P2002",
            message=f"diagnostics report not found: {diagnostics_json}",
        )
        return {}

    allowlist_raw = cfg.get("allowlist", [])
    max_counts_raw = cfg.get("max_counts", {})
    allowlist = {item for item in allowlist_raw if isinstance(item, str)}
    if not isinstance(max_counts_raw, dict):
        _append(
            errors, area="warning_governance", code="P2003", message="warning_governance.max_counts must be mapping"
        )
        max_counts_raw = {}

    counts = _warning_code_counts(diagnostics_json)
    for code in sorted(counts):
        if code in allowlist:
            continue
        message = f"warning code '{code}' is not allowlisted"
        if mode == "enforce":
            _append(errors, area="warning_governance", code="G2101", message=message)
        else:
            _append(warnings, area="warning_governance", code="G2101", message=message)

    for code, threshold_raw in max_counts_raw.items():
        if not isinstance(code, str):
            continue
        if not isinstance(threshold_raw, int) or threshold_raw < 0:
            _append(
                errors,
                area="warning_governance",
                code="P2004",
                message=f"warning_governance.max_counts.{code} must be non-negative integer",
            )
            continue
        observed = counts.get(code, 0)
        if observed <= threshold_raw:
            continue
        message = f"warning code '{code}' exceeds max count: observed={observed}, threshold={threshold_raw}"
        if mode == "enforce":
            _append(errors, area="warning_governance", code="G2102", message=message)
        else:
            _append(warnings, area="warning_governance", code="G2102", message=message)

    return {
        "allowlist": sorted(allowlist),
        "counts": dict(sorted(counts.items())),
        "max_counts": {str(k): int(v) for k, v in max_counts_raw.items() if isinstance(k, str) and isinstance(v, int)},
    }


def _scan_legacy_matches(*, base: Path, patterns: dict[str, re.Pattern[str]]) -> dict[str, int]:
    counts = {name: 0 for name in patterns}
    if not base.exists():
        return counts
    for file_path in base.rglob("*.yaml"):
        if not file_path.is_file():
            continue
        text = file_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            for name, regex in patterns.items():
                if regex.search(line):
                    counts[name] += 1
    return counts


def _evaluate_legacy_boundary(
    *,
    repo_root: Path,
    policy: dict[str, Any],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    cfg = policy.get("legacy_boundary")
    if not isinstance(cfg, dict):
        _append(errors, area="legacy_boundary", code="P3001", message="missing legacy_boundary policy block")
        return {}
    scan_root_raw = cfg.get("scan_root")
    active_root_raw = cfg.get("active_instances_root")
    exclude_globs_raw = cfg.get("exclude_globs", [])
    key_patterns_raw = cfg.get("key_patterns", {})
    if not isinstance(scan_root_raw, str) or not scan_root_raw:
        _append(
            errors, area="legacy_boundary", code="P3002", message="legacy_boundary.scan_root must be non-empty string"
        )
        return {}
    if not isinstance(active_root_raw, str) or not active_root_raw:
        _append(
            errors,
            area="legacy_boundary",
            code="P3003",
            message="legacy_boundary.active_instances_root must be non-empty string",
        )
        return {}
    if not isinstance(exclude_globs_raw, list) or not all(isinstance(item, str) for item in exclude_globs_raw):
        _append(errors, area="legacy_boundary", code="P3004", message="legacy_boundary.exclude_globs must be list[str]")
        exclude_globs_raw = []
    if not isinstance(key_patterns_raw, dict):
        _append(errors, area="legacy_boundary", code="P3005", message="legacy_boundary.key_patterns must be mapping")
        return {}

    patterns: dict[str, re.Pattern[str]] = {}
    for key, pattern_raw in key_patterns_raw.items():
        if not isinstance(key, str) or not isinstance(pattern_raw, str):
            continue
        try:
            patterns[key] = re.compile(pattern_raw)
        except re.error as exc:
            _append(
                errors, area="legacy_boundary", code="P3006", message=f"invalid regex for key pattern '{key}': {exc}"
            )
    if not patterns:
        _append(errors, area="legacy_boundary", code="P3007", message="no valid key_patterns configured")
        return {}

    scan_root = (repo_root / scan_root_raw).resolve()
    active_root = (repo_root / active_root_raw).resolve()
    exclude_globs = [item for item in exclude_globs_raw if isinstance(item, str) and item.strip()]

    total_counts = {name: 0 for name in patterns}
    excluded_counts = {name: 0 for name in patterns}
    included_counts = {name: 0 for name in patterns}

    if scan_root.exists():
        for file_path in scan_root.rglob("*.yaml"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(repo_root).as_posix()
            text = file_path.read_text(encoding="utf-8")
            current = {name: 0 for name in patterns}
            for line in text.splitlines():
                for name, regex in patterns.items():
                    if regex.search(line):
                        current[name] += 1
            if not any(current.values()):
                continue
            for name in patterns:
                total_counts[name] += current[name]
            excluded = any(fnmatch(rel, glob) for glob in exclude_globs)
            target = excluded_counts if excluded else included_counts
            for name in patterns:
                target[name] += current[name]

    active_counts = _scan_legacy_matches(base=active_root, patterns=patterns)

    in_scope_total = sum(included_counts.values())
    active_total = sum(active_counts.values())
    if active_total > 0:
        _append(
            errors,
            area="legacy_boundary",
            code="G3101",
            message=f"active instances root contains legacy semantic keys: total={active_total}",
        )
    if in_scope_total > 0:
        _append(
            errors,
            area="legacy_boundary",
            code="G3102",
            message=f"in-scope repository area contains legacy semantic keys: total={in_scope_total}",
        )

    return {
        "scan_root": scan_root_raw,
        "active_instances_root": active_root_raw,
        "exclude_globs": exclude_globs,
        "total_counts": total_counts,
        "excluded_counts": excluded_counts,
        "in_scope_counts": included_counts,
        "active_instances_counts": active_counts,
        "totals": {
            "all": sum(total_counts.values()),
            "excluded": sum(excluded_counts.values()),
            "in_scope": in_scope_total,
            "active_instances": active_total,
        },
    }


def run_governance(
    *,
    repo_root: Path,
    policy_path: Path,
    diagnostics_json: Path,
    mode: str,
) -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported mode: {mode}")

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    try:
        policy = _load_policy(policy_path)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        _append(errors, area="policy", code="P0001", message=f"failed to load policy: {exc}")
        policy = {}

    metadata_report = _evaluate_metadata(
        repo_root=repo_root,
        policy=policy,
        mode=mode,
        errors=errors,
        warnings=warnings,
    )
    warning_report = _evaluate_warning_governance(
        diagnostics_json=diagnostics_json,
        policy=policy,
        mode=mode,
        errors=errors,
        warnings=warnings,
    )
    legacy_report = _evaluate_legacy_boundary(
        repo_root=repo_root,
        policy=policy,
        errors=errors,
    )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "policy_path": str(policy_path),
        "diagnostics_json": str(diagnostics_json),
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "metadata": metadata_report,
        "warning_governance": warning_report,
        "legacy_boundary": legacy_report,
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate ADR0088 governance contracts.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH, help="Path to governance policy YAML.")
    parser.add_argument(
        "--diagnostics-json",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_JSON,
        help="Path to compiler diagnostics report JSON.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help="Path to governance output report JSON.",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(SUPPORTED_MODES),
        default="warn",
        help="Governance mode. warn keeps non-critical policy breaches as warnings; enforce makes them errors.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = ROOT.resolve()
    policy_path = args.policy.resolve() if not args.policy.is_absolute() else args.policy
    diagnostics_json = (
        args.diagnostics_json.resolve() if not args.diagnostics_json.is_absolute() else args.diagnostics_json
    )
    output_json = args.output_json.resolve() if not args.output_json.is_absolute() else args.output_json

    report = run_governance(
        repo_root=repo_root,
        policy_path=policy_path,
        diagnostics_json=diagnostics_json,
        mode=args.mode,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[adr0088-governance] report: {output_json}")

    for item in report["warnings"]:
        print(f"[adr0088-governance] WARN {item['code']}: {item['message']}")
    for item in report["errors"]:
        print(f"[adr0088-governance] ERROR {item['code']}: {item['message']}")

    if report["summary"]["errors"] > 0:
        print("[adr0088-governance] FAIL")
        return 1
    print("[adr0088-governance] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
